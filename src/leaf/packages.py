"""Package authoring commands and filesystem safety gates."""

import contextlib
import os
import re
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from .files import read_json, replace_files
from .layer import (
    LayerComposition,
    checked_inputs,
    checked_layer_inputs,
    compose_layer,
    imported_sheets,
    input_paths,
    layer_inputs,
    named_package,
)
from .locations import (
    first_overlap,
    located,
    location_is_within,
    path_location,
    path_lock_key,
    paths_same,
)
from .machine import package_store
from .refusals import Refused
from .schema import (
    ELEMENT_ID,
    HTML_NAME,
    LAYER_FILE,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SCRIPTS_DIR,
    WIDGET_NAME,
    WIDGET_NAME_RULE,
)
from .state import EVENTS_FILE, flocked, fsync_parents, json_bytes
from .themes import DEFAULT_THEME


@contextlib.contextmanager
def package_write_lock(*packages: Path):
    """Serialize mutations only where their package contracts share destinations.

    Registry read/modify/write and shared member directories stay together. An
    install holds its source and destination in the same ordered lock set, so source
    init finishes before copying and destination init cannot race publication.
    Symlinked contract members use their resolved destinations. Independent packages
    never hold an exclusive lock in common.

    The lock home is machine-local, independent of XDG_STATE_HOME and TMPDIR: two
    environments writing the same authored package still share its locks. Nothing
    is written beside authored code or inside a not-yet-validated package.
    """
    root = Path("/tmp") / f"leaf-package-locks-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    keys = {
        path_lock_key(package / name)
        for package in packages
        for name in (*PACKAGE_FILES, *PACKAGE_DIRS, SCRIPTS_DIR)
    }
    with contextlib.ExitStack() as held:
        for key in sorted(keys):
            held.enter_context(flocked(root / f"{key}.lock"))
        yield


def create_package_files(package: Path, files: list[tuple[Path, bytes]]) -> list:
    """Create new members with no-clobber semantics, returning rollback identities."""
    created = []
    try:
        for path, contents in files:
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                    0o666,
                )
            except FileExistsError:
                raise Refused(
                    f"package member {path.relative_to(package)} was created "
                    "while package init was running; nothing was replaced"
                ) from None
            with os.fdopen(descriptor, "wb") as stream:
                identity = os.fstat(stream.fileno())
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            created.append((path, identity.st_dev, identity.st_ino))
        fsync_parents(path for path, _contents in files)
        return created
    except BaseException:
        rollback_package_files(created)
        raise


def rollback_package_files(created: list) -> None:
    """Remove only members that are still the exact files this transaction created."""
    for path, device, inode in reversed(created):
        try:
            current = path.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (device, inode):
                path.unlink()
        except FileNotFoundError:
            pass


def starter_element_declaration(tag: str) -> dict:
    """One useful upgraded markup block, ready for a package author to specialize."""
    name = tag.removeprefix("lf-")
    label = name.replace("-", " ")
    title = label.capitalize()
    return {
        "description": (
            f"A dedicated block for {label} content. Use it to keep one technical "
            "point with its supporting evidence or rationale. Give the block a stable "
            "id."
        ),
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "pattern": f"^{ELEMENT_ID}$",
            }
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-verbatim": True,
        "x-example": (
            f'<{tag} id="{name}"><strong>{title}</strong> '
            "The retry budget is three attempts before manual review."
            f"</{tag}>"
        ),
    }


def starter_widget_module(tag: str) -> bytes:
    """The registration shared by behavioral widgets: a `LeafElement`
    (module-authoring.md, "Drawing what a widget reads").

    The layer paints what the declaration alone determines, settlement included, with
    no help from the module. A module that draws state adds `render()`, which reads
    `this.state` and is drawn again whenever it changes."""
    return (
        'import { LeafElement } from "/runtime/widget-api.js";\n\n'
        "customElements.define(\n"
        f'  "{tag}",\n'
        "  class extends LeafElement {},\n"
        ");\n"
    ).encode()


def protected_package_paths(package: Path) -> list:
    """Resolved paths owned by the kernel and bundled default package."""
    paths = []
    for other in layer_inputs():
        if paths_same(other, package):
            continue
        paths.append(other.resolve())
        if other.is_dir():
            paths.extend(input_paths([other]))
    return paths


def refuse_package_overlap(targets: list, protected: list) -> None:
    """Refuse package paths that would write over another package."""
    if overlap := first_overlap(located(targets), located(protected)):
        target, source = overlap
        target = target.resolve()
        raise Refused(
            f"package target {target} overlaps another package {source}; "
            "package scopes must be separate"
        )


def initialized_page_owning(path: Path):
    """The initialized page that owns path, if there is one."""
    resolved = path.resolve()
    at = path_location(resolved)
    for root in (resolved, *resolved.parents):
        # The append-only event log is the successful-init marker, beside the layer
        # record init writes. Disposable runtime state cannot identify the page whose
        # owned paths this gate protects.
        if not ((root / EVENTS_FILE).is_file() and (root / LAYER_FILE).is_file()):
            continue
        if (
            at == path_location(root)
            or any(at == path_location(root / name) for name in PAGE_OWNED_FILES)
            or any(
                location_is_within(at, path_location(root / name))
                for name in PAGE_OWNED_DIRS
            )
        ):
            return root
    return None


def package_page_overlap(paths: list):
    for path in paths:
        resolved = path.resolve()
        if page := initialized_page_owning(resolved):
            return resolved, page
    return None


# PEP 723's reference reading of an inline metadata block.
INLINE_METADATA = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def check_package_scripts(package: Path) -> None:
    """Refuse a script `package run` could not run apart from the caller's project.

    `uv run --script` builds an environment of its own only for a file that
    carries an inline `script` metadata block (PEP 723); a file without one runs in
    whatever project or virtual environment the caller's directory reaches, so a
    producer would depend on where the agent ran it. `--no-project` does not
    close that, since uv still finds the caller's `.venv` for a file with no block,
    so the block is the one guarantee: required here, where `package check` reports
    it and `package install` refuses it, and for bundled packages by the suite. What
    the block declares is uv's to read: a malformed block fails `package run` with
    uv's own error. A subdirectory of `scripts/` holds helpers and is not run.
    """
    scripts = package / SCRIPTS_DIR
    if not (scripts.exists() or scripts.is_symlink()):
        return
    if not scripts.is_dir():
        raise Refused(f"{scripts} must be a directory")
    for path in sorted(scripts.glob("*.py")):
        if not path.is_file():
            raise Refused(f"{path} must be a file")
        if not any(
            match["type"] == "script"
            for match in INLINE_METADATA.finditer(path.read_text(encoding="utf-8"))
        ):
            raise Refused(
                f"{path} needs an inline `# /// script` metadata block (PEP 723) "
                "declaring its dependencies, so `leaf package run` runs it in an "
                "environment of its own"
            )


def validate_package_dir(package: Path) -> list:
    if (package.exists() or package.is_symlink()) and not package.is_dir():
        raise Refused(f"{package} must be a directory")
    if package.is_dir():
        checked_inputs([package])
        check_package_scripts(package)
    protected = protected_package_paths(package)
    paths = input_paths([package]) if package.is_dir() else [package]
    if overlap := package_page_overlap(paths):
        target, page = overlap
        raise Refused(
            f"package path {target} is owned by initialized page {page}; "
            "packages must stay separate from page-owned paths, "
            "then run `page init` again"
        )
    refuse_package_overlap(paths, protected)
    return protected


def package_layer_inputs(package: Path) -> list[Path]:
    """The layer a new page selecting this package composes: the mandatory layer and
    Leaf's default theme before this package when it is not already in it."""
    inputs = layer_inputs()
    theme = named_package(DEFAULT_THEME)
    if theme is not None and not any(paths_same(theme, root) for root in inputs):
        inputs.append(theme)
    if not any(paths_same(package, root) for root in inputs):
        inputs.append(package)
    return inputs


def check_package(
    package: Path, *, require_exists: bool
) -> tuple[Path, list, LayerComposition]:
    """Validate one package through the same composition gate as a page."""
    package = package.expanduser().resolve()
    if require_exists and not package.is_dir():
        raise Refused(f"{package} is not a package directory")
    protected = validate_package_dir(package)
    roots = checked_layer_inputs(package_layer_inputs(package))
    composition = compose_layer(roots)
    return package, protected, composition


def copy_package_contract(package: Path, staged: Path) -> None:
    """Copy exactly what a layer input reads, and the package's scripts, into an
    empty directory.

    The rest of the source directory — a README, the author's own tests, `.git` —
    belongs to the author rather than to the package, so it reaches neither a
    staged candidate nor the store. Absent package directories are created empty,
    as `package init` creates them; `scripts/` is copied only when it exists,
    since most packages ship none.
    """
    for name in PACKAGE_FILES:
        source = package / name
        if source.is_file():
            shutil.copy2(source, staged / name)
    for name in PACKAGE_DIRS:
        source = package / name
        target = staged / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.mkdir()
    if (package / SCRIPTS_DIR).is_dir():
        shutil.copytree(package / SCRIPTS_DIR, staged / SCRIPTS_DIR)
    # A sheet's imports are part of it (`layer.stylesheet`), wherever in the package
    # they stand; one inside a directory copied above is already staged.
    for name in PACKAGE_FILES:
        if not name.endswith(".css") or not (package / name).is_file():
            continue
        for imported in imported_sheets(package / name, package):
            target = staged / imported.relative_to(package.resolve())
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(imported, target)


def validate_starter_candidate(package: Path, files: dict[str, bytes]) -> None:
    """Compose the complete package candidate without changing its destination."""
    with tempfile.TemporaryDirectory(prefix="leaf-package-") as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        copy_package_contract(package, staged)
        for relative, contents in files.items():
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)

        roots = [
            staged if paths_same(root, package) else root
            for root in package_layer_inputs(package)
        ]
        compose_layer(checked_layer_inputs(roots))


def init_starter_widget(
    package: Path,
    protected: list,
    composition: LayerComposition,
    widget: str,
) -> None:
    """Add one checked upgraded-content starter without replacing package members."""
    if re.fullmatch(WIDGET_NAME, widget) is None:
        raise Refused(f"invalid widget tag {widget!r}: {WIDGET_NAME_RULE}")
    module_name = f"{widget}.js"
    module_path = package / "widgets" / module_name
    if widget in composition.registry:
        raise Refused(f"widget tag <{widget}> already exists in the composed layer")
    if (
        module_path.exists()
        or module_path.is_symlink()
        or module_name in composition.directory_files["widgets"]
    ):
        raise Refused(
            f"widget module widgets/{module_name} already exists in the composed layer"
        )

    registry_path = package / "registry.json"
    registry = read_json(registry_path) or {}
    registry[widget] = starter_element_declaration(widget)
    files = {
        "registry.json": json_bytes(registry, indent=2),
        f"widgets/{module_name}": starter_widget_module(widget),
    }
    validate_starter_candidate(package, files)
    refuse_package_overlap(
        [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
        protected,
    )

    package.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_DIRS:
        (package / name).mkdir(exist_ok=True)
    creates = [(module_path, files[f"widgets/{module_name}"])]
    if not (
        (package / "defaults.css").exists() or (package / "defaults.css").is_symlink()
    ):
        creates.append((package / "defaults.css", b""))
    created = create_package_files(package, creates)
    try:
        replace_files([(registry_path, files["registry.json"], True)])
    except BaseException:
        rollback_package_files(created)
        raise


def cmd_package_init(package: Path, widget: str | None = None) -> dict:
    with package_write_lock(package):
        package, protected, composition = check_package(package, require_exists=False)
        if widget is not None:
            init_starter_widget(package, protected, composition, widget)
            return {"package": str(package), "widget": widget}

        refuse_package_overlap(
            [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
            protected,
        )

        files = {
            "registry.json": b"{}\n",
            "overrides.css": b"",
        }
        package.mkdir(parents=True, exist_ok=True)
        for name in PACKAGE_DIRS:
            (package / name).mkdir(exist_ok=True)
        creates = [
            (package / name, contents)
            for name, contents in files.items()
            if not ((package / name).exists() or (package / name).is_symlink())
        ]
        create_package_files(package, creates)
        return {"package": str(package)}


def cmd_package_check(package: Path, render: bool = False) -> dict:
    """Check the package, and with `render` its widgets' worked examples in the
    host's browser, and report one object in `page check`'s shape: `status`, the exit
    status; `findings`, each finding as a record: the findings a refusal carries, such
    as a registry's, any other refusal as one `package` record, or the widget quality
    findings; and `browser`, what the browser gate ran in or why none could, null
    where none was asked for or the package check refused."""
    from .findings import Finding, Rejected

    def reported(status, findings=(), browser=None):
        return {
            "status": status,
            "findings": [finding.json() for finding in findings],
            "browser": browser,
        }

    try:
        package, _, _ = check_package(package, require_exists=True)
    except Refused as error:
        found = (
            error.findings
            if isinstance(error, Rejected)
            else [Finding("package", values={"text": str(error)})]
        )
        return reported(1, found)
    if not render:
        return reported(0)
    from .render_gate.command import widget_quality

    check = widget_quality(package)
    return reported(check.status, check.findings, check.json())


def cmd_package_install(source: Path) -> dict:
    """Publish a checked immutable snapshot under its source directory's name.

    The lexical name changes atomically after all copied bytes validate. Existing
    readers retain their resolved snapshot; subsequent readers use the replacement.
    Installed packages may replace installed or bundled names on the same terms.
    """
    store = package_store()
    source = source.expanduser().resolve()
    # This destination is a stable synthetic lock coordinate, never the symlink
    # whose target installation replaces. Resolve aliases of the source separately.
    with package_write_lock(source, store / "locks" / source.name):
        package, _, _ = check_package(source, require_exists=True)
        name = package.name
        if re.fullmatch(HTML_NAME, name) is None:
            raise Refused(
                f"package directory {name!r} cannot be selected by name; rename "
                f"it to match {HTML_NAME} before installing it"
            )
        # A failed copy or check creates no selectable name and preserves an earlier
        # installation. Staging is outside the published store.
        with tempfile.TemporaryDirectory(
            dir=store.parent, prefix="leaf-install-"
        ) as temporary:
            staged = Path(temporary) / name
            staged.mkdir()
            copy_package_contract(package, staged)
            check_package(staged, require_exists=True)
            names = store / "names"
            snapshot = store / "snapshots" / secrets.token_hex(16)
            names.mkdir(parents=True, exist_ok=True)
            snapshot.mkdir(parents=True)
            published = snapshot / name
            os.rename(staged, published)
            pointer = Path(temporary) / "selection"
            pointer.symlink_to(
                os.path.relpath(published, names), target_is_directory=True
            )
            destination = names / name
            os.replace(pointer, destination)
            fsync_parents([published, destination])
        return {"package": str(published)}


def cmd_package_run(name: str, script: str, arguments: tuple[str, ...]) -> None:
    """Run one of a package's `scripts/` in the environment its header declares.

    The package is found by the lookup `page init --package NAME` resolves
    through, so a producer command in instructions names a package and a script
    rather than a path on this machine, and an installed package's tools run on
    the same terms as a bundled one's. Each script is a Python file whose inline
    metadata (PEP 723) declares its dependencies; `uv run --script` builds that
    environment, apart from Leaf's own. The run replaces this process, so the
    script owns stdin, stdout, stderr, and the exit status.
    """
    if (
        re.fullmatch(HTML_NAME, name) is None
        or (package := named_package(name)) is None
    ):
        raise Refused(
            f"unknown package {name!r}; name a bundled package or one "
            "`leaf package install` added"
        )
    scripts = package / SCRIPTS_DIR
    available = sorted(path.name for path in scripts.glob("*.py") if path.is_file())
    if script not in available:
        offered = ", ".join(available) or "none"
        raise Refused(
            f"package {name!r} has no script {script!r}; available: {offered}"
        )
    command = ["uv", "run", "--quiet", "--script", str(scripts / script), *arguments]
    sys.stdout.flush()
    os.execvp(command[0], command)
