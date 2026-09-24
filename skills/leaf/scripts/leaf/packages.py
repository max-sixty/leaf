"""Package authoring commands and filesystem safety gates."""

import contextlib
import fcntl
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .files import fsync_parents, json_bytes, read_json, replace_files
from .layer import (
    LayerComposition,
    checked_inputs,
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_inputs,
    named_package,
)
from .locations import (
    located,
    location_is_within,
    locations_overlap,
    path_location,
    paths_same,
)
from .machine import package_store
from .schema import (
    ASSETS,
    BROWSER_DIRS,
    DEFAULT_PACKAGE,
    ELEMENT_ID,
    EVENTS_FILE,
    HTML_NAME,
    PACKAGE_DIRS,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SCRIPTS_DIR,
    VENDORED_FILES,
    WIDGET_NAME,
    WIDGET_NAME_RULE,
)


@contextlib.contextmanager
def package_write_lock(package: Path):
    """Serialize package mutations without creating a lock artifact beside the code.

    A directory inode is a stable process-shared lock on both supported host families.
    The filesystem root exists before any candidate package path, so two initializers
    choose the same inode even when the package's parent directories do not exist yet.
    Package writes are rare and short; one lock per filesystem also closes concurrent
    registry updates to different packages without inventing persistent state.
    """
    root = Path(package.absolute().anchor)
    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


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
                sys.exit(
                    f"package member {path.relative_to(package)} was created "
                    "while package init was running; nothing was replaced"
                )
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
            standing = path.stat(follow_symlinks=False)
            if (standing.st_dev, standing.st_ino) == (device, inode):
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
    """The registration and one-shot upgrade shared by behavioral widgets."""
    return (
        'import { once } from "/runtime/widget-api.js";\n\n'
        "customElements.define(\n"
        f'  "{tag}",\n'
        "  class extends HTMLElement {\n"
        "    connectedCallback() {\n"
        "      if (!once(this)) return;\n"
        "    }\n"
        "  },\n"
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
    located_protected = located(protected)
    overlap = next(
        (
            (target.resolve(), source)
            for target, target_at in located(targets)
            for source, source_at in located_protected
            if locations_overlap(target_at, source_at)
        ),
        None,
    )
    if overlap:
        target, source = overlap
        sys.exit(
            f"package target {target} overlaps another package {source}; "
            "package scopes must be separate"
        )


def initialized_page_owning(path: Path):
    """The initialized page that owns path, if there is one."""
    resolved = path.resolve()
    at = path_location(resolved)
    for root in (resolved, *resolved.parents):
        # The append-only event log is the successful-init marker. Disposable
        # runtime state cannot identify the page whose owned paths this gate protects.
        if not (
            (root / EVENTS_FILE).is_file()
            and all((root / name).is_file() for name in VENDORED_FILES)
            and all((root / name).is_dir() for name in BROWSER_DIRS)
        ):
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


def floor_error(specifier: SpecifierSet) -> str | None:
    """Why a version constraint is not a floor with no cap, or None."""
    operators = {spec.operator for spec in specifier}
    if operators != {">="}:
        return "must state a floor (>=) and nothing else"
    return None


def check_package_scripts(package: Path) -> None:
    """Refuse a script `package run` could not run apart from the caller's project.

    `uv run --script` builds an environment of its own only for a file that
    carries an inline `script` metadata block (PEP 723); a file without one runs in
    whatever project or virtual environment the caller's directory reaches, so a
    producer would depend on where the agent ran it. `--no-project` does not
    close that, since uv still finds the caller's `.venv` for a file with no block,
    so the block is the one guarantee: required here, where `package check` reports
    it and `package install` refuses it, and for bundled packages by the suite. Its
    constraints follow the project's dependency policy, a floor and no cap
    (AGENTS.md, "The install runs this tree"). A
    subdirectory of `scripts/` holds helpers and is not run.
    """
    scripts = package / SCRIPTS_DIR
    if not (scripts.exists() or scripts.is_symlink()):
        return
    if not scripts.is_dir():
        sys.exit(f"{scripts} must be a directory")
    for path in sorted(scripts.glob("*.py")):
        if not path.is_file():
            sys.exit(f"{path} must be a file")
        script_requirements(path)


def script_requirements(path: Path) -> list[Requirement]:
    """The dependencies one package script's inline metadata declares, held to the
    policy `check_package_scripts` states; a script that breaks it is refused."""
    blocks = [
        match
        for match in INLINE_METADATA.finditer(path.read_text(encoding="utf-8"))
        if match["type"] == "script"
    ]
    if len(blocks) != 1:
        sys.exit(
            f"{path} needs one inline `# /// script` metadata block (PEP 723) "
            "declaring its dependencies, so `leaf package run` runs it in an "
            "environment of its own"
        )
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in blocks[0]["content"].splitlines(keepends=True)
    )
    try:
        metadata = tomllib.loads(content)
        dependencies = metadata.get("dependencies", [])
        python = metadata.get("requires-python", ">=0")
        if not (
            isinstance(dependencies, list)
            and all(isinstance(value, str) for value in dependencies)
            and isinstance(python, str)
        ):
            raise ValueError(
                "dependencies must be a list of strings and requires-python a string"
            )
        requirements = [Requirement(value) for value in dependencies]
        python = SpecifierSet(python)
    except (ValueError, InvalidRequirement, InvalidSpecifier) as error:
        sys.exit(f"{path}: invalid script metadata ({error})")
    if error := floor_error(python):
        sys.exit(f"{path}: requires-python {error}")
    for requirement in requirements:
        if requirement.url is not None or (error := floor_error(requirement.specifier)):
            sys.exit(
                f"{path}: dependency {str(requirement)!r} "
                f"{error or 'must name a version floor, not a URL'}"
            )
    return requirements


def validate_package_dir(package: Path) -> list:
    if (package.exists() or package.is_symlink()) and not package.is_dir():
        sys.exit(f"{package} must be a directory")
    if package.is_dir():
        checked_inputs([package])
        check_package_scripts(package)
    protected = protected_package_paths(package)
    paths = input_paths([package]) if package.is_dir() else [package]
    if overlap := package_page_overlap(paths):
        target, page = overlap
        sys.exit(
            f"package path {target} is owned by initialized page {page}; "
            "packages must stay separate from page-owned paths, "
            "then run `page init` to re-vendor the page"
        )
    refuse_package_overlap(paths, protected)
    return protected


def package_layer_inputs(package: Path) -> list[Path]:
    """The composition context in which this package normally appears."""
    inputs = layer_inputs()
    for index, root in enumerate(inputs):
        if paths_same(package, root):
            return inputs[: index + 1]
    return [ASSETS, DEFAULT_PACKAGE, package]


def check_package(
    package: Path, *, require_exists: bool
) -> tuple[Path, list, LayerComposition]:
    """Validate one package through the same composition gate as a page."""
    package = package.expanduser().resolve()
    if require_exists and not package.is_dir():
        sys.exit(f"{package} is not a package directory")
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
    for name in VENDORED_FILES:
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
        sys.exit(f"invalid widget tag {widget!r}: {WIDGET_NAME_RULE}")
    module_name = f"{widget}.js"
    module_path = package / "widgets" / module_name
    if widget in composition.registry:
        sys.exit(f"widget tag <{widget}> already exists in the composed layer")
    if (
        module_path.exists()
        or module_path.is_symlink()
        or module_name in composition.directory_files["widgets"]
    ):
        sys.exit(
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
        [package, *(package / name for name in (*VENDORED_FILES, *PACKAGE_DIRS))],
        protected,
    )

    package.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_DIRS:
        (package / name).mkdir(exist_ok=True)
    creates = [(module_path, files[f"widgets/{module_name}"])]
    if not ((package / "theme.css").exists() or (package / "theme.css").is_symlink()):
        creates.append((package / "theme.css", b""))
    created = create_package_files(package, creates)
    try:
        replace_files([(registry_path, files["registry.json"], True)])
    except BaseException:
        rollback_package_files(created)
        raise


def cmd_package_init(package: Path, widget: str | None = None) -> Path:
    with package_write_lock(package):
        package, protected, composition = check_package(package, require_exists=False)
        if widget is not None:
            init_starter_widget(package, protected, composition, widget)
            print(f"initialized {package} with <{widget}>")
            return package

        refuse_package_overlap(
            [package, *(package / name for name in (*VENDORED_FILES, *PACKAGE_DIRS))],
            protected,
        )

        files = {
            "registry.json": b"{}\n",
            "theme.css": b"",
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
        print(f"initialized {package}")
        return package


def cmd_package_check(package: Path) -> Path:
    package, _, _ = check_package(package, require_exists=True)
    print(f"checked {package}")
    return package


def cmd_package_install(source: Path) -> Path:
    """Copy a checked package into the store a bare `--package` name reaches.

    The source directory's own name is the name pages select, so the install
    refuses one already answered by a bundled or installed package instead of
    changing which directory that name means.
    """
    store = package_store()
    with package_write_lock(store):
        package, _, _ = check_package(source, require_exists=True)
        name = package.name
        if re.fullmatch(HTML_NAME, name) is None:
            sys.exit(
                f"package directory {name!r} cannot be selected by name; rename "
                f"it to match {HTML_NAME} before installing it"
            )
        destination = store / name
        if standing := named_package(name):
            remedy = (
                "remove that directory to replace it"
                if standing == destination
                else "rename the source directory to install this one beside it"
            )
            sys.exit(f"package name {name!r} already resolves to {standing}; {remedy}")
        store.mkdir(exist_ok=True)
        # Stage beside the store rather than in it, so a half-copied package is
        # never a name `--package` can reach and never a directory the next
        # install has to recognize as debris.
        with tempfile.TemporaryDirectory(
            dir=store.parent, prefix="leaf-install-"
        ) as temporary:
            staged = Path(temporary) / name
            staged.mkdir()
            copy_package_contract(package, staged)
            os.rename(staged, destination)
        print(f"installed {destination}")
        return destination


def cmd_package_run(name: str, script: str, arguments: tuple[str, ...]) -> None:
    """Run one of a package's `scripts/` in the environment its header declares.

    The package is found by the lookup `page init --package NAME` resolves
    through, so a producer command in guidance names a package and a script
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
        sys.exit(
            f"unknown package {name!r}; name a bundled package or one "
            "`leaf package install` added"
        )
    scripts = package / SCRIPTS_DIR
    available = sorted(path.name for path in scripts.glob("*.py") if path.is_file())
    if script not in available:
        offered = ", ".join(available) or "none"
        sys.exit(f"package {name!r} has no script {script!r}; available: {offered}")
    command = ["uv", "run", "--quiet", "--script", str(scripts / script), *arguments]
    sys.stdout.flush()
    os.execvp(command[0], command)
