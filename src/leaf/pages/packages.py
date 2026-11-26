"""Package authoring commands and filesystem safety gates."""

import os
import re
import secrets
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from leaf.base.files import read_json, replace_files
from leaf.base.findings import Finding, Rejected
from leaf.base.locations import (
    first_overlap,
    located,
    location_is_within,
    path_location,
    path_lock,
    paths_same,
)
from leaf.base.machine import package_store
from leaf.base.refusals import Refused
from leaf.base.schema import (
    ASSETS,
    BUNDLED_PACKAGES,
    DEFAULT_PACKAGE,
    HTML_NAME,
    INSTRUCTIONS_DIR,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SCRIPTS_DIR,
    WIDGET_NAME,
    WIDGET_NAME_RULE,
)
from leaf.base.state import fsync_parents, json_bytes
from leaf.log.event_log import initialized
from leaf.source.layer import (
    LayerComposition,
    checked_inputs,
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_inputs,
    named_package,
    package_files,
    package_layer_inputs,
    selectable_packages,
)
from leaf.source.registry.contract import read_registry_declarations
from leaf.source.styles import set_properties, unguarded_reads


def package_write_lock(*packages: Path):
    """Serialize mutations only where their package contracts share destinations.

    Registry read/modify/write and shared member directories stay together. An
    install holds its source and destination in the same ordered lock set
    (`locations.path_lock`), so source init finishes before copying and destination
    init cannot race publication. Symlinked contract members use their resolved
    destinations. Independent packages never hold an exclusive lock in common.
    """
    return path_lock(
        *(
            package / name
            for package in packages
            for name in (*PACKAGE_FILES, *PACKAGE_DIRS, SCRIPTS_DIR)
        )
    )


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


# The starter `package init --widget` writes is one working widget, a yes-or-no choice,
# in the three parts a widget with behavior has: its declaration, its module and its
# style rule. It holds the widget protocol's one round trip and nothing else: Leaf sets
# `state`, the module draws it, and a press records an action. An author reads all of
# it and changes it into the widget they need, so each key of the declaration is one
# this widget uses, and `package check --render` finds nothing to advise in it. It is
# a plain custom element, as the protocol reference's opening example is
# (module-plain-elements.md). A `LeafElement` subclass would be shorter, but only by
# putting the event the starter is there to show behind `record()`.


def starter_element_declaration(tag: str) -> dict:
    """The starter's declaration: a `choose` verb recorded as the `choice` attribute,
    on an element that holds no authored content."""
    return {
        "description": "A yes-or-no choice the user makes with a press.",
        "attributes": {
            "properties": {"choice": {"enum": ["yes", "no"]}},
            "required": ["id"],
        },
        "content": "empty",
        "verbs": {"choose": {"record": {"attr": "choice"}}},
        "example": f'<{tag} id="{tag.removeprefix("lf-")}"></{tag}>',
    }


def starter_widget_module(tag: str) -> bytes:
    """The starter's module: the `state` setter draws a button for each value, and a
    press dispatches `lf-action`."""
    return f"""\
import {{ html, render }} from "/vendor/lit.js";

// The widget protocol: references/module-plain-elements.md in the Leaf skill.
customElements.define(
  "{tag}",
  class extends HTMLElement {{
    set state({{ choose }}) {{
      const button = (value, label) =>
        html`<button
          type="button"
          aria-pressed=${{choose.value === value}}
          aria-disabled=${{!choose.available}}
          @click=${{() => this.press(value)}}
        >
          ${{label}}
        </button>`;
      render([button("yes", "Yes"), button("no", "No")], this);
    }}

    press(value) {{
      const action = {{ verb: "choose", detail: {{ value }} }};
      this.dispatchEvent(new CustomEvent("lf-action", {{ detail: action }}));
    }}
  }},
);
""".encode()


def starter_widget_styles(tag: str) -> bytes:
    """The starter's style rule: the box the module's row of buttons takes, held from
    first paint."""
    return f"""\
/* The first box: references/packages.md, "Seeing it", in the Leaf skill. */
{tag} {{
  display: block;
  min-block-size: var(--lf-line);
}}
""".encode()


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
        # Disposable runtime state cannot identify the page whose owned paths this
        # gate protects.
        if not initialized(root):
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


@lru_cache(maxsize=1)
def _runtime_properties() -> tuple[frozenset[str], tuple[str, ...]]:
    """The custom properties this install's browser runtime and server set by name,
    which no layer composes: the runtime's modules and sheets, and what a delivery
    writes (`styles.set_properties`)."""
    sources = (ASSETS, Path(__file__).parents[1])
    return set_properties(
        path.read_text(encoding="utf-8", errors="replace")
        for root in sources
        for path in sorted(root.rglob("*"))
        if path.suffix in {".css", ".js", ".py"} and path.is_file()
    )


def unset_properties(package: Path, composition: LayerComposition) -> list:
    """An `unset-property` advice for each custom property the package's own sheets
    read with no fallback that nothing sets: no sheet or module of Leaf's runtime, of
    the layer a page selecting the package composes, or of the package itself. Such a
    read is usually a token Leaf renamed, and the declaration computes to nothing with
    no error anywhere. It is advice, since a page may set the property itself, as a
    package's instructions can ask it to."""
    names, prefixes = _runtime_properties()
    composed, built = set_properties(
        data.decode("utf-8", errors="replace")
        for path, data in composition.files.items()
        if path.endswith((".css", ".js"))
    )
    names, prefixes = names | composed, (*prefixes, *built)
    found = []
    for path, data in package_files(package).items():
        if not path.endswith(".css") or "vendor" in Path(path).parts:
            continue
        rows = {}
        for name, row in unguarded_reads(
            data.decode("utf-8", errors="replace"),
            lambda name: name in names or name.startswith(prefixes),
        ):
            rows.setdefault(name, []).append(row)
        found += [
            Finding(
                "unset-property",
                values={"sheet": str(package / path), "property": name, "rows": lines},
            )
            for name, lines in sorted(rows.items())
        ]
    return found


def copy_package_contract(package: Path, staged: Path) -> None:
    """Copy exactly what a layer input reads (`layer.package_files`), and the
    package's scripts, into an empty directory.

    The rest of the source directory — a README, the author's own tests, `.git` —
    belongs to the author rather than to the package, so it reaches neither a
    staged candidate nor the store. Absent package directories are created empty;
    `scripts/` is copied only when it exists, since most packages ship none.
    """
    for path, data in package_files(package).items():
        target = staged / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in PACKAGE_DIRS:
        (staged / name).mkdir(exist_ok=True)
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


def init_starter_widgets(
    package: Path,
    protected: list,
    composition: LayerComposition,
    widgets: tuple[str, ...],
) -> None:
    """Add each tag's starter widget: its declaration to `registry.json`, its rule to
    the end of `defaults.css`, and its module, which replaces no file the package
    holds. Every tag and the whole candidate are checked before any file changes.
    The registry is written last, so a write that fails leaves no declaration without
    its module, and at most the new rules, which no declaration then names."""
    registry_path = package / "registry.json"
    styles_path = package / "defaults.css"
    registry = read_json(registry_path) or {}
    styles = [styles_path.read_bytes().rstrip()] if styles_path.is_file() else []
    modules = {}
    for widget in widgets:
        if re.fullmatch(WIDGET_NAME, widget) is None:
            raise Refused(f"invalid widget tag {widget!r}: {WIDGET_NAME_RULE}")
        module_name = f"{widget}.js"
        module_path = package / "widgets" / module_name
        if widget in composition.vocabulary.registry:
            raise Refused(f"widget tag <{widget}> already exists in the composed layer")
        if (
            module_path.exists()
            or module_path.is_symlink()
            or module_name in composition.vocabulary.widgets
        ):
            raise Refused(
                f"widget module widgets/{module_name} already exists in the "
                "composed layer"
            )
        registry[widget] = starter_element_declaration(widget)
        styles.append(starter_widget_styles(widget).rstrip())
        modules[module_path] = starter_widget_module(widget)

    replaces = {
        styles_path: b"\n\n".join(filter(None, styles)) + b"\n",
        registry_path: json_bytes(registry, indent=2),
    }
    validate_starter_candidate(
        package,
        {
            path.relative_to(package).as_posix(): contents
            for path, contents in (replaces | modules).items()
        },
    )
    refuse_package_overlap(
        [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
        protected,
    )

    (package / "widgets").mkdir(parents=True, exist_ok=True)
    created = create_package_files(package, list(modules.items()))
    try:
        replace_files([(path, contents, True) for path, contents in replaces.items()])
    except BaseException:
        rollback_package_files(created)
        raise


def cmd_package_init(package: Path, widgets: tuple[str, ...] = ()) -> dict:
    with package_write_lock(package):
        package, protected, composition = check_package(package, require_exists=False)
        if widgets:
            # A tag named twice means it once.
            widgets = tuple(dict.fromkeys(widgets))
            init_starter_widgets(package, protected, composition, widgets)
            return {"package": str(package), "widgets": list(widgets)}

        refuse_package_overlap(
            [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
            protected,
        )

        # A CSS-only widget's rules go in defaults.css, beside the
        # registry that declares the widget; anything else a package holds, the
        # author adds when there is something to put in it.
        files = {
            "registry.json": b"{}\n",
            "defaults.css": b"",
        }
        package.mkdir(parents=True, exist_ok=True)
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
    as a registry's, any other refusal as one `package` record, or else what its
    declarations advise (`authored_checks.declarations.layer_advice`), the advice
    `unset_properties` gives and the widget quality findings; and `browser`, what the
    browser gate ran in or why none could, null
    where none was asked for or the package check refused."""

    def reported(status, findings=(), browser=None):
        return {
            "status": status,
            "findings": [finding.json() for finding in findings],
            "browser": browser,
        }

    try:
        package, _, composition = check_package(package, require_exists=True)
    except Refused as error:
        found = (
            error.findings
            if isinstance(error, Rejected)
            else [Finding("package", values={"text": str(error)})]
        )
        return reported(1, found)
    from leaf.records.authored_checks.declarations import layer_advice

    advice = [
        *layer_advice([package], composition.vocabulary.registry),
        *unset_properties(package, composition),
    ]
    if not render:
        return reported(0, advice)
    from leaf.pages.render_gate.command import widget_quality

    check = widget_quality(package)
    return reported(check.status, [*advice, *check.findings], check.json())


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


def cmd_package_list() -> dict:
    """List the packages `page init --package NAME` can select by name
    (`selectable_packages`), leaving out `default`, which every page composes.

    A package is described in its own words, so one installed under a name of its own
    reaches an author as a bundled one does: its `description` is the first paragraph
    of its author instructions, which says when to select it, and `entries` maps each
    of its registry keys to that entry's description. `installed` says whether the
    name resolves to the user's package store rather than to one Leaf ships."""
    # Reading Markdown pulls in the page parser, which no other package command needs.
    from leaf.source.passages import markdown_dialect

    packages = []
    for name, root in selectable_packages().items():
        if name == DEFAULT_PACKAGE.name:
            continue
        author = root / INSTRUCTIONS_DIR / "author.md"
        text = author.read_text(encoding="utf-8") if author.is_file() else ""
        tokens = markdown_dialect(message=False, html=True).parse(text)
        opening = next(
            (
                tokens[index + 1].content
                for index, token in enumerate(tokens)
                if token.type == "paragraph_open" and token.level == 0
            ),
            "",
        )
        entries = read_registry_declarations(root / "registry.json") or {}
        packages.append(
            {
                "name": name,
                "installed": not paths_same(root, BUNDLED_PACKAGES / name),
                "description": " ".join(opening.split()),
                "entries": {
                    key: entry["description"]
                    for key, entry in entries.items()
                    if not key.startswith("$")
                },
            }
        )
    return {"packages": packages}


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
            f"unknown package {name!r}; `leaf package list` prints the names "
            "this machine can select"
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
