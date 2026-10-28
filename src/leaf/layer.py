"""Layer input resolution, composition, and content identity."""

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import NamedTuple

from .findings import Finding
from .locations import first_overlap, located
from .machine import package_store
from .refusals import Refused
from .registry.contract import is_element_name
from .registry.kernel import kernel_protocol
from .schema import (
    ASSETS,
    BROWSER_DIRS,
    BUNDLED_PACKAGES,
    DEFAULT_PACKAGE,
    EXTENSION_SCHEMA,
    HTML_NAME,
    INSTRUCTIONS_DIR,
    INSTRUCTIONS_FILE,
    JAVASCRIPT_SUFFIXES,
    KERNEL,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    RUNTIME_DIRS,
    RUNTIME_ENTRY,
    VENDORED_FILES,
)
from .state import PLUGIN_ROOT


def named_package(name: str) -> Path | None:
    """Select one installed snapshot or the bundled package with this name.

    Installed names are atomically replaced symlinks into immutable snapshots. Resolve
    the link once, so a reader keeps one complete package even when another install
    publishes that name. An installed package deliberately overrides a bundled one.
    """
    installed = package_store() / "names" / name
    if installed.is_symlink():
        return installed.resolve(strict=True)
    bundled = BUNDLED_PACKAGES / name
    return bundled if bundled.is_dir() else None


def resolve_packages(selected: tuple[str, ...]) -> list[Path]:
    """Resolve recorded package selections without changing their order.

    A bare name selects an installed or bundled package. Other relative paths
    are project-relative. A `~` path stays portable across the user's machines.
    Absolute paths are not recorded because
    `$layer.packages` is part of the page's public vendored registry.
    """
    packages = []
    for value in selected:
        if re.fullmatch(HTML_NAME, value):
            named = named_package(value)
            if named is None:
                raise Refused(
                    f"unknown package {value!r}; run `leaf package install` to add "
                    f"it, or use './{value}' for a project-relative package path"
                )
            if named != DEFAULT_PACKAGE:
                packages.append(named)
            continue
        package_path = Path(value)
        if package_path.is_absolute():
            raise Refused(
                f"package {value!r} is absolute; use a bundled name, "
                "explicit project-relative path, or ~ path so the vendored registry "
                "does not publish a machine path"
            )
        root = package_path.expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        if not (root.exists() or root.is_symlink()):
            raise Refused(f"package {value!r} is not a directory")
        packages.append(root)
    return packages


def layer_inputs(selected: tuple[str, ...] = ()) -> list[Path]:
    """The kernel, bundled default, and explicitly selected packages, in order."""
    return [ASSETS, DEFAULT_PACKAGE, *resolve_packages(selected)]


def checked_inputs(inputs: list[Path]) -> list[Path]:
    """Existing, structurally valid kernel and package roots.

    A path of the wrong kind is authored input, not an absent package.
    Refuse it here once so every merger can assume the public directory contract.
    """
    roots = []
    for root in inputs:
        if not (root.exists() or root.is_symlink()):
            continue
        if not root.is_dir():
            raise Refused(f"{root} must be a directory")
        for name in VENDORED_FILES if root == ASSETS else PACKAGE_FILES:
            path = root / name
            if (path.exists() or path.is_symlink()) and not path.is_file():
                raise Refused(f"{path} must be a file")
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            if not directory.is_dir():
                raise Refused(f"{directory} must be a directory")
            if sub == INSTRUCTIONS_DIR:
                for path in directory.iterdir():
                    if not path.is_file():
                        raise Refused(f"{path} must be a file")
                    if not INSTRUCTIONS_FILE.fullmatch(path.name):
                        raise Refused(f"{path} must be named <audience>.md")
                continue
            for path in directory.rglob("*"):
                if path.is_dir() and not path.is_symlink():
                    continue
                if not path.is_file():
                    raise Refused(f"{path} must be a file or real directory")
        roots.append(root)
    return roots


def input_paths(inputs: list[Path]) -> list[Path]:
    """Every path a layer input reads, including nested symlink targets."""
    paths = []
    for root in inputs:
        paths.append(root.resolve())
        paths.extend(
            path.resolve()
            for name in (VENDORED_FILES if root == ASSETS else PACKAGE_FILES)
            if ((path := root / name).exists() or path.is_symlink())
        )
        paths.extend(
            imported
            for sheet in sorted(root.glob("*.css"))
            for imported in imported_sheets(sheet, root)
        )
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            paths.append(directory.resolve())
            if directory.is_dir():
                entries = (
                    directory.iterdir()
                    if sub == INSTRUCTIONS_DIR
                    else directory.rglob("*")
                )
                paths.extend(path.resolve() for path in entries)
    return paths


def overlapping_inputs(inputs: list[Path]):
    """The first resolved path shared by two precedence scopes."""
    located_inputs = [(root, located(input_paths([root]))) for root in inputs]
    for index, (left_root, left_paths) in enumerate(located_inputs):
        for right_root, right_paths in located_inputs[index + 1 :]:
            if overlap := first_overlap(left_paths, right_paths):
                left, right = overlap
                return left_root, left, right_root, right
    return None


def composed_dir_files(inputs: list[Path], sub: str) -> dict[str, Path]:
    """The winning input for every file in one composed directory."""
    winners = {}
    for root in inputs:
        source_dir = root / sub
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                winners[path.relative_to(source_dir).as_posix()] = path
    return winners


# The document's cascade tiers, lowest first. The chrome's form-control clearing
# (`lf-reset`, runtime/chrome.css) stays below everything that chooses a face. The
# kernel, every widget package, and each widget module's adopted sheet
# (runtime/base-layer.js) share one layer, so specificity, then order, rank their
# rules. The kernel's Layouts sit above it. Theme contributions
# sit above those defaults and the Layouts (`lf-theme`), so a package
# styles every page the way the page's own sheet styles one.
# Semantic state follows: retirement must outrank a theme's or package's default box
# and a Layout's arrangement. The page's own sheet stays unlayered above these tiers,
# and inline widget motion outranks them too. Chrome and apparatus marks stay
# unlayered to beat page and widget alike; runtime/stylesheets.js owns their
# precedence and defaults. `lf-shadow` holds shared shadow rules and is read only in
# shadow trees, where it sits above adopted widget sheets and below theme contributions.
CASCADE_LAYERS = (
    "lf-reset",
    "lf-base",
    "lf-layouts",
    "lf-shadow",
    "lf-theme",
    "lf-state",
)

# tinycss2 currently decodes surrogate escapes to lone surrogates. CSS requires
# U+FFFD instead; keep its serialization valid UTF-8 until its tokenizer is fixed.
_CSS_SURROGATES = dict.fromkeys(range(0xD800, 0xE000), 0xFFFD)


def stylesheet(source: Path, root: Path) -> str:
    """One sheet as a page receives it: validated, its EOF recovery completed, its
    comments dropped, and each `@import` replaced by the sheet it names.

    A sheet's sources are what an author edits, so a sheet split into files needs no
    build and can never be served older than its parts. An import names a file inside
    `root`, relative to the importing sheet, optionally with `layer(name)`; its rules
    stand where the import stood, so a relative `url()` in them resolves against the
    page's copy of the importing sheet. The page then receives complete sheets and asks
    for no import, which an adopted sheet couldn't make anyway. A dependency's sheet,
    which an install has no `node_modules` to read, is bundled into a file beside its
    importer (`build/styles.mjs`).
    """
    return _stylesheet(source, root, ())


def _stylesheet(source: Path, root: Path, opened: tuple[Path, ...]) -> str:
    """`stylesheet`, inside the imports of `opened`."""
    import tinycss2

    from .styles import css_stylesheet, css_syntax_errors

    opened = (*opened, source.resolve())
    try:
        css = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Refused(f"{source} must be UTF-8")
    if errors := css_syntax_errors(css, str(source)):
        raise Refused(str(errors[0]))
    parts = []
    for node in css_stylesheet(css):
        if _is_import(node):
            path, layer = _import(node, source, root, opened)
            sheet = _stylesheet(path, root, opened)
            parts.append(f"@layer {layer} {{\n{sheet}}}\n" if layer else sheet)
        else:
            parts.append(tinycss2.serialize([node]))
    serialized = "".join(parts).translate(_CSS_SURROGATES)
    return serialized if serialized.endswith("\n") else serialized + "\n"


def imported_sheets(source: Path, root: Path) -> list[Path]:
    """Every file `stylesheet(source, root)` reads besides `source`, for a reader that
    follows a sheet's inputs. An import composition would refuse is left out, since
    composing reports it."""
    return _imported_sheets(source, root, ())


def _imported_sheets(source: Path, root: Path, opened: tuple[Path, ...]) -> list[Path]:
    from .styles import css_stylesheet

    opened = (*opened, source.resolve())
    found = []
    try:
        rules = css_stylesheet(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return found
    for node in filter(_is_import, rules):
        try:
            path, _ = _import(node, source, root, opened)
        except Refused:
            continue
        found += [path, *_imported_sheets(path, root, opened)]
    return found


def _is_import(node) -> bool:
    return node.type == "at-rule" and node.lower_at_keyword == "import"


def _import(
    rule, source: Path, root: Path, opened: tuple[Path, ...]
) -> tuple[Path, str | None]:
    """The file one `@import` in `source` names, and the cascade layer it asks for.
    `opened` is the chain of sheets importing it, `source` last."""
    import tinycss2

    target, *conditions = [t for t in rule.prelude if t.type != "whitespace"] or [None]
    if target is not None and target.type == "function" and target.lower_name == "url":
        target = next((t for t in target.arguments if t.type == "string"), None)
    layer = None
    if conditions and getattr(conditions[0], "lower_name", None) == "layer":
        layer = tinycss2.serialize(conditions[0].arguments).strip() or None
    unplaced = conditions[1:] if layer else conditions
    if target is None or target.type not in ("string", "url") or unplaced:
        raise Refused(
            f"{source}: `@import {tinycss2.serialize(rule.prelude).strip()}` takes a "
            "file's relative path and at most `layer(name)`; wrap the imported rules in "
            "@media or @supports inside that file"
        )
    path = (source.parent / target.value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise Refused(f"{source} imports {target.value!r}, which is no file in {root}")
    if path in opened:
        cycle = [*opened[opened.index(path) :], path]
        raise Refused("stylesheets import each other: " + " -> ".join(map(str, cycle)))
    return path, layer


def composed_sheets(inputs: list[Path]) -> dict[str, bytes]:
    """The layer's two stylesheets: each contribution in its role's cascade tier,
    in input order. Leaf places sheets and rewrites none of their rules.

    A sheet's filename sets its role. widgets.css holds a package's defaults in
    lf-base. widget-shadow.css holds rules for both trees, in lf-base in the
    document and lf-shadow in every declared shadow tree. Leaf adds no scope around
    either, so each names the widgets it styles: by tag in the document, and by
    `:host(tag)` in a shadow tree, where a rule reaches everything the tree holds,
    including core views placed there, such as a diff's threads. theme.css is
    lf-theme. A theme reaches shadow trees through the custom properties they inherit. Each sheet is
    read with its relative imports (`stylesheet`).

    The kernel supplies the base and shared shadow defaults. Its Layouts and semantic
    state retain their own tiers. Page CSS remains unlayered.
    """
    if not any((root / "theme.css").is_file() for root in inputs):
        raise Refused("the incoming layer has no theme.css")
    order = f"@layer {', '.join(CASCADE_LAYERS)};\n"
    theme = [order]
    shadow = [order]

    def place(sheets, tier, root, name):
        source = root / name
        if source.is_file():
            sheets.append(f"@layer {tier} {{\n{stylesheet(source, root)}}}\n")

    kernel, *packages = inputs
    place(theme, "lf-base", kernel, "shadow.css")
    place(shadow, "lf-shadow", kernel, "shadow.css")
    place(theme, "lf-base", kernel, "theme.css")
    for root in packages:
        place(theme, "lf-base", root, "widget-shadow.css")
        place(shadow, "lf-shadow", root, "widget-shadow.css")
        place(theme, "lf-base", root, "widgets.css")
        place(theme, "lf-theme", root, "theme.css")
    for name in ("layouts.css", "state.css"):
        if (source := kernel / name).is_file():
            sheet = stylesheet(source, kernel)
            theme.append(sheet)
            if name == "state.css":
                shadow.append(sheet)
    return {
        "theme.css": "".join(theme).encode(),
        "shadow.css": "".join(shadow).encode(),
    }


def composed_instructions(inputs: list[Path]) -> dict[str, bytes]:
    """Package instructions joined by audience in layer precedence order.

    Each package's passage opens under a heading naming its package, so a guide
    file starts with its first rule rather than a title of its own, and one
    package's text never reads as part of the package before it.
    """
    parts: dict[str, list[str]] = {}
    for root in inputs:
        directory = root / INSTRUCTIONS_DIR
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            try:
                instructions = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise Refused(f"{path} must be UTF-8")
            if instructions.strip():
                parts.setdefault(path.name, []).append(
                    f"# Package `{root.name}`\n\n{instructions.strip()}\n"
                )
    return {name: "\n".join(passages).encode() for name, passages in parts.items()}


def checked_layer_inputs(inputs: list[Path]) -> list[Path]:
    """Structurally valid, non-overlapping inputs in composition order."""
    roots = checked_inputs(inputs)
    if overlap := overlapping_inputs(roots):
        left_root, left, right_root, right = overlap
        raise Refused(
            f"layer inputs {left_root} and {right_root} overlap at {left} and "
            f"{right}; package scopes must be separate"
        )
    return roots


def kernel_runtime_paths() -> set[str]:
    """Private kernel paths packages cannot replace: the source modules and the
    compiled kernel's, so one boundary holds whichever a page runs."""
    return {
        path.relative_to(root / "runtime").as_posix()
        for root in (ASSETS, KERNEL)
        for path in (root / "runtime").rglob("*.js")
    }


class LayerComposition(NamedTuple):
    registry: dict
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]


def files_identity(files: dict[str, bytes]) -> str:
    """Identify a set of named bytes, unambiguously across names and contents."""
    digest = hashlib.sha256()
    for name in sorted(files):
        encoded = name.encode()
        data = files[name]
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def layer_fingerprint(composition: LayerComposition) -> str:
    """Identify the complete composed layer independently of its vendoring epoch."""
    return files_identity(
        {
            **composition.top_files,
            "registry.json": json.dumps(
                composition.registry,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
            **{
                f"{directory}/{name}": data
                for directory, entries in composition.directory_files.items()
                for name, data in entries.items()
            },
        }
    )


def payload_python_inputs(root: Path) -> list[Path]:
    """Code, schemas and dependencies a running Python process has loaded."""
    return [
        *sorted(path for path in (root / "src").rglob("*.py") if path.is_file()),
        *sorted(path for path in (root / "src").rglob("*.json") if path.is_file()),
        root / "browser/registry.json",
        root / "pyproject.toml",
        root / "uv.lock",
    ]


def payload_server_inputs(root: Path) -> list[Path]:
    """The serving code, the browser runtime it serves (`runtime_selection`), and the
    dependency manifests an init must restart to adopt."""
    runtime = [
        root / "browser" / RUNTIME_ENTRY,
        *(root / "browser" / name for name in RUNTIME_DIRS),
        root / "dist/kernel",
        root / "src/leaf/render-checks",
    ]
    served = sorted(
        path
        for top in runtime
        for path in ([top] if top.is_file() else top.rglob("*"))
        if path.is_file()
    )
    return [
        *payload_python_inputs(root),
        *served,
        *(
            sheet
            for path in served
            if path.suffix == ".css"
            for sheet in imported_sheets(path, root / "browser")
        ),
    ]


def payload_server_fingerprint() -> str:
    """Identify serving inputs independently of a Git commit or Python build.

    A site builds pages on the CI host and serves them from a container with a
    different interpreter. The vendored event contract depends on the payload's
    files, not that interpreter's version string.
    """
    return files_identity(
        {
            path.relative_to(PLUGIN_ROOT).as_posix(): path.read_bytes()
            for path in payload_server_inputs(PLUGIN_ROOT)
        }
    )


def incompatible_layer(page_dir: Path, registry: dict) -> Finding | None:
    """Why this Leaf can neither serve a page nor write its log, given the registry it
    would serve the page under; None when it may. Either the registry's `$events`
    were vendored at another `protocol` than this Leaf's own
    (`registry.kernel.kernel_protocol`), or its `$keys` document an x- key this Leaf
    no longer admits (`schema.EXTENSION_SCHEMA`).

    A Leaf serves and writes any page vendored at its own number, whichever Leaf
    vendored it, so a plugin update leaves open pages working. A page vendored before
    the number was declared names none, and is refused too. A page vendored at a
    higher number is refused as `newer-layer`, naming the Leaf that vendored it,
    since its repair is a newer Leaf: this one does not re-vendor it down
    (`vendoring._plan_page`). A key renamed or removed since the page was vendored
    is the same kind of fact: this Leaf would read the key's new name, find nothing,
    and drop what the page's layer declares under the old one, so the page is
    refused rather than misread. The check is one-sided: a key this Leaf added and
    an older layer lacks refuses nothing. Every server of the page's live files, the
    website's included (`http.page_endpoint`, `leaf_website.page_binding`), the one
    append door and the writers that ask it first (`event_contracts.write_refusal`),
    and `page check` refuse on this one reading, each naming its repair. For a page
    vendored at an older number, the holding session's prompt and Stop hooks, and
    each of its commands that names the page, make that re-vendor first
    (`vendoring.renew_layer`). So does the source
    check (`validation.source.check_source`), so activation writes no revision under
    the layer and `page state` reports the refusal as `source.error`. A revision the
    page saved before its last re-vendor is judged on its own registry
    (`incompatible_revision`). The vendored layer's reader asks the protocol half
    (`protocol_refusal`) before it validates the layer's shape
    (`registry.storage.load_registry`).
    """
    if refusal := protocol_refusal(page_dir, registry):
        return refusal
    if retired := _retired_keys(registry):
        return Finding(
            "retired-layer",
            values={
                "page": str(page_dir),
                "retired": retired,
                "leaf": str(PLUGIN_ROOT),
            },
        )
    return None


def protocol_refusal(page_dir: Path, registry: dict) -> Finding | None:
    """The half of `incompatible_layer` that reads only the page protocol a registry's
    `$events` declare. It reads `$events` and `$layer` only where they are objects,
    so it may run on a layer before this Leaf validates what its entries hold
    (`registry.storage.load_registry`): that shape is this Leaf's protocol's, which a
    layer vendored at another one need not have."""
    if (vendored := _foreign_protocol(registry)) is not None:
        if type(vendored) is int and vendored > kernel_protocol():
            return Finding(
                "newer-layer",
                values={
                    "page": str(page_dir),
                    "vendored": vendored,
                    "vendored_by": provenance_label(_producer(registry)),
                    "leaf": str(PLUGIN_ROOT),
                    "protocol": kernel_protocol(),
                },
            )
        return Finding(
            "foreign-layer",
            values={
                "page": str(page_dir),
                "vendored": vendored,
                "leaf": str(PLUGIN_ROOT),
                "protocol": kernel_protocol(),
            },
        )
    return None


def incompatible_revision(revision: int, registry: dict) -> Finding | None:
    """Why this Leaf can neither serve one of a page's revisions nor admit input made
    against it, given the registry that revision captured: it was saved at another
    protocol, or its vocabulary uses an x- key this Leaf no longer admits, the two
    refusals `incompatible_layer` makes of the page's layer. None when it may.

    Each revision captures the runtime and registry it was saved with, and a
    re-vendor leaves existing revisions as they were, so a page re-vendored across a
    bump still holds revisions saved before it. Served, one would run its own runtime
    against this Leaf's server, which is the break the protocol announces. The
    document server, a snapshot's capture (`page_snapshot.capture_page_snapshot`),
    and the append door ask this of the revision they would serve or admit under;
    readings of the log keep reading every revision's registry, so history still
    projects. Serving the page saves its source as a revision first,
    so its live revision is one of these only where the source no longer saves.
    A revision whose vocabulary uses a retired key is refused for the reason the
    layer is: this Leaf would read the key's new name there, find nothing, and draw
    the revision without what it declares, such as a framed obligation's prompt.
    """
    if (saved := _foreign_protocol(registry)) is not None:
        return Finding(
            "foreign-revision",
            values={
                "revision": revision,
                "saved": saved,
                "protocol": kernel_protocol(),
            },
        )
    if retired := _retired_keys(registry):
        return Finding(
            "retired-revision", values={"revision": revision, "retired": retired}
        )
    return None


def _retired_keys(registry: dict) -> list[str]:
    """The x- keys a vocabulary documents in `$keys` or declares on an entry that
    this Leaf no longer admits (`schema.EXTENSION_SCHEMA`), in order; none where it
    uses only admitted ones. One-sided: a key this Leaf added and the vocabulary
    lacks is not among them."""
    admitted = set(EXTENSION_SCHEMA["properties"])
    keys = registry.get("$keys")
    used = set(keys if isinstance(keys, dict) else ()) - {"description"}
    for name, entry in registry.items():
        if not name.startswith("$") and isinstance(entry, dict):
            used |= {key for key in entry if key.startswith("x-")}
    return sorted(used - admitted)


def _foreign_protocol(registry: dict) -> int | str | None:
    """The protocol a registry's `$events` declare where this Leaf does not speak
    it, `"none"` where they declare none, or None where it is this Leaf's own."""
    events = registry.get("$events")
    declared = events.get("protocol") if isinstance(events, dict) else None
    if type(declared) is int and declared == kernel_protocol():
        return None
    return declared if declared is not None else "none"


def _producer(registry: dict) -> dict:
    """The provenance a registry's `$layer` records, or none where a layer of
    another shape records it elsewhere."""
    layer = registry.get("$layer")
    producer = layer.get("producer") if isinstance(layer, dict) else None
    return producer if isinstance(producer, dict) else {}


def payload_provenance(*, include_path: bool = False, root: Path | None = None) -> dict:
    """Describe the Leaf payload that is running this command, when its source can.

    Beside the commit, one of two dates says how old the payload is: `committed`,
    the commit's committer date, where Git can read it; or `installed`, when a harness
    copied the payload into its plugin cache without `.git`. Both are ISO 8601 with
    an offset. Developer preparations can pass `root` to read another checkout
    through the same provenance rules.
    """
    source = Path(__file__) if root is None else root / "src/leaf/layer.py"
    root = PLUGIN_ROOT if root is None else root.resolve()
    provenance = {"path": str(root)} if include_path else {}
    distribution = root / "leaf-distribution.json"
    if distribution.is_file():
        published = json.loads(distribution.read_text())
        provenance.update(published["producer"])
        return provenance
    # Claude Code copies a marketplace plugin without its .git directory into a cache
    # whose final component is the resolved plugin version. Leaf leaves its manifest
    # version unset, so that component is the source commit SHA. The default root
    # follows this module: a newer sibling cannot change the running copy's identity.
    parents = root.parents
    if (
        len(parents) >= 4
        and root.parent.name == "leaf"
        and parents[2].name == "cache"
        and parents[3].name == "plugins"
        and re.fullmatch(r"[0-9a-f]{7,40}", root.name)
    ):
        # The copy stamps every file with the time it was made, and Leaf never
        # rewrites its own modules. A harness copies only the marketplace's newest
        # commit, one update sweep after it lands, so this dates the commit to
        # within that sweep; the commit date itself left with `.git`.
        installed = datetime.fromtimestamp(source.stat().st_mtime, UTC)
        provenance.update(
            commit=root.name,
            dirty=False,
            installed=installed.astimezone().isoformat(timespec="seconds"),
        )
        return provenance

    git = ["git", "--no-optional-locks", "-C", str(root)]
    try:
        identity = subprocess.run(
            [*git, "rev-parse", "--show-toplevel", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return provenance
    if identity.returncode != 0:
        return provenance
    lines = identity.stdout.splitlines()
    if len(lines) != 2 or Path(lines[0]).resolve() != root.resolve():
        return provenance
    provenance["commit"] = lines[1]
    provenance["committed"] = subprocess.run(
        [*git, "show", "--no-patch", "--format=%cI", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        dirty = subprocess.run(
            [
                *git,
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                ".",
                ":(top,exclude).codex-marketplace-install.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return provenance
    if dirty.returncode == 0:
        provenance["dirty"] = bool(dirty.stdout)
    return provenance


@cache
def running_leaf() -> dict:
    """`payload_provenance` read once for this process, by its first page server as
    that server is built (`http.page_app`): the Leaf whose code the process runs,
    however its checkout moves on afterwards."""
    return payload_provenance()


def same_leaf(one: dict, other: dict) -> bool:
    """Whether two provenances, as `payload_provenance` reads them, name one source:
    the same commit, whichever abbreviates it, and the same dirty bit. Two with no
    commit have nothing to tell apart."""
    first, second = one.get("commit"), other.get("commit")
    if not (first and second):
        return first == second
    return (first.startswith(second) or second.startswith(first)) and one.get(
        "dirty"
    ) == other.get("dirty")


def provenance_label(provenance: dict) -> str:
    """One line naming a payload's commit and date, as `payload_provenance` read it.

    `+` marks uncommitted changes, as the leaf's menu does.
    """
    commit = provenance.get("commit")
    if not commit:
        return "unknown source"
    label = commit + ("+" if provenance.get("dirty") else "")
    for kind in ("committed", "installed"):
        if kind in provenance:
            return f"{label}, {kind} {provenance[kind]}"
    return label


def compose_layer(roots: list[Path]) -> LayerComposition:
    """Read and validate the complete layer produced by checked inputs.

    The kernel's own runtime, `leaf.js` and its `runtime/` and `vendor/` files, is
    not part of it: the Leaf serving a page supplies that (`runtime_selection`), so
    the layer holds what packages add beside it, and the registry, theme and widgets
    every root contributes."""
    from .revision_artifact import (
        PUBLIC_MODULES,
        dependency_reference,
        javascript_imports,
    )
    from .validation.composition import incoming_registry

    protected = kernel_runtime_paths()
    private_modules = {"/leaf.js", *(f"/runtime/{name}" for name in protected)} - set(
        PUBLIC_MODULES
    )
    for root in roots:
        if root.resolve() == ASSETS.resolve():
            continue
        replacements = [
            f"runtime/{path.relative_to(root / 'runtime').as_posix()}"
            for path in (root / "runtime").rglob("*.js")
            if path.relative_to(root / "runtime").as_posix() in protected
        ]
        if (root / "leaf.js").exists():
            replacements.append("leaf.js")
        if replacements:
            raise Refused(
                f"package {root} replaces private kernel modules: "
                + ", ".join(sorted(replacements))
                + "; use /runtime/widget-api.js and package-owned modules"
            )
        for sub in BROWSER_DIRS:
            for module in (root / sub).rglob("*"):
                if not module.is_file() or module.suffix not in JAVASCRIPT_SUFFIXES:
                    continue
                path = "/" + module.relative_to(root).as_posix()
                for _, _, specifier in javascript_imports(module.read_bytes(), path):
                    dependency = dependency_reference(specifier, path, module=True)
                    if dependency is not None and dependency[0] in private_modules:
                        raise Refused(
                            f"{module} imports private kernel module {specifier!r}; "
                            "use /runtime/widget-api.js"
                        )
    incoming = incoming_registry(roots)
    directory_sources = {
        sub: composed_dir_files(
            [
                root
                for root in roots
                if sub not in RUNTIME_DIRS or root.resolve() != ASSETS.resolve()
            ],
            sub,
        )
        for sub in BROWSER_DIRS
    }
    missing_modules = sorted(
        tag
        for tag, entry in incoming.items()
        if is_element_name(tag)
        and entry["x-upgrade"]
        and f"{tag}.js" not in directory_sources["widgets"]
    )
    if missing_modules:
        raise Refused(
            "the incoming registry marks widgets as upgraded but their modules "
            "are missing:\n"
            + "\n".join(f"  - widgets/{tag}.js" for tag in missing_modules)
        )

    top_files = composed_sheets(roots)
    for name in VENDORED_FILES:
        if name == "registry.json" or name in top_files:
            continue
        source = next(
            (source / name for source in reversed(roots) if (source / name).is_file()),
            None,
        )
        if source is None:
            raise Refused(f"the incoming layer has no {name}")
        top_files[name] = source.read_bytes()
    directory_files = {
        sub: {
            name: source.read_bytes() for name, source in directory_sources[sub].items()
        }
        for sub in BROWSER_DIRS
    }
    directory_files[INSTRUCTIONS_DIR] = composed_instructions(roots)
    return LayerComposition(incoming, top_files, directory_files)
