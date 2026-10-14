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
from .locations import located, locations_overlap
from .machine import package_store
from .refusals import Refused
from .registry.contract import element_declarations, is_element_name
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
    LAYER_PLACEHOLDER,
    PACKAGE_DIRS,
    PLUGIN_ROOT,
    VENDORED_FILES,
)


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
        for name in VENDORED_FILES:
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
            for name in VENDORED_FILES
            if ((path := root / name).exists() or path.is_symlink())
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
    return next(
        (
            (left_root, left, right_root, right)
            for index, (left_root, left_paths) in enumerate(located_inputs)
            for right_root, right_paths in located_inputs[index + 1 :]
            for left, left_at in left_paths
            for right, right_at in right_paths
            if locations_overlap(left_at, right_at)
        ),
        None,
    )


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
# kernel, every package, and each widget module's adopted sheet (runtime/stylesheets.js)
# share one layer, so specificity, scope proximity, then order rank their rules.
# The kernel's Layouts sit above it, followed by semantic state: retirement must
# outrank a package's default box and a Layout's arrangement. The page's own sheet
# stays unlayered above these tiers, and inline widget motion outranks them too.
# The page's rules reach Leaf's own controls only where they name them
# (runtime/page-sheets.js). Chrome and apparatus marks stay unlayered to beat page
# and widget alike; runtime/stylesheets.js owns their precedence and defaults.
CASCADE_LAYERS = ("lf-reset", "lf-base", "lf-layouts", "lf-shadow", "lf-state")


def _sheet(source: Path) -> str:
    from .styles import css_syntax_errors

    try:
        css = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Refused(f"{source} must be UTF-8")
    if errors := css_syntax_errors(css, str(source)):
        raise Refused(str(errors[0]))
    return css if css.endswith("\n") else css + "\n"


def widget_confinement(root: Path) -> tuple[str, str] | None:
    """Native document and shadow scope roots for a package's declared widgets.

    The browser confines matching to each root and its descendants; authors name
    a root with :scope. A widget-free package is an unscoped page theme.
    """
    registry = root / "registry.json"
    tags = (
        sorted(element_declarations(json.loads(registry.read_text())))
        if registry.is_file()
        else []
    )
    if not tags:
        return None
    listed = ", ".join(tags)
    host = f":host(:is({listed}))"
    return f":is({listed})", host


# A root's own stylesheets, in the order the document's theme.css reads them.
ROOT_SHEETS = ("shadow.css", "theme.css")


def composed_sheets(inputs: list[Path]) -> dict[str, bytes]:
    """The layer's two stylesheets, each in layer precedence order.

    A root's shadow.css holds the rules a declared shadow tree has to see as well as
    the document: the stage copies the composed shadow.css into each tree, and the
    document's theme.css reads each root's shadow.css just ahead of its theme.css.

    In the document, every root's sheets are the `lf-base` cascade layer, and the
    kernel's layouts.css and state.css name their higher tiers and come last.
    Shared shadow rules use `lf-shadow` above adopted widget sheets (`lf-base`),
    preserving their precedence over vendor defaults. state.css ranks above both,
    so declared retirement has the same precedence in both trees. Authored
    unlayered styles and inline widget motion remain above it.

    Each widget package's sheet has one native @scope around its declared tags
    in the document, or around their :host in shadow trees. :scope names the root,
    ordinary selectors its descendants. CSS owns nested conditions and proximity;
    composition neither rewrites selectors nor adds specificity. Widget-free
    packages are unscoped themes that reach the page and every tree.
    """
    from .styles import scoped

    if not any((root / "theme.css").is_file() for root in inputs):
        raise Refused("the incoming layer has no theme.css")
    order = f"@layer {', '.join(CASCADE_LAYERS)};\n"
    theme = [order]
    shadow = [order]
    for position, root in enumerate(inputs):
        where = widget_confinement(root) if position else None
        for name in ROOT_SHEETS:
            source = root / name
            if not source.is_file():
                continue
            css = _sheet(source)
            placed = scoped(css, where[0]) if where else css
            if name == "shadow.css":
                shadow_css = scoped(css, where[1]) if where else css
                shadow.append(f"@layer lf-shadow {{\n{shadow_css}}}\n")
            theme.append(f"@layer lf-base {{\n{placed}}}\n")
    for name in ("layouts.css", "state.css"):
        if (source := inputs[0] / name).is_file():
            sheet = _sheet(source)
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
    """Private kernel paths packages cannot replace, before or after compilation.

    CI records the source paths in its prepared payload because compiled chunks no
    longer have those names. Both representations enforce the same package boundary.
    """
    manifest = PLUGIN_ROOT / "leaf-distribution.json"
    paths = {
        path.relative_to(ASSETS / "runtime").as_posix()
        for path in (ASSETS / "runtime").rglob("*.js")
    }
    if manifest.is_file():
        paths.update(json.loads(manifest.read_text())["runtime_paths"])
    return paths


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


def payload_server_inputs(root: Path) -> list[Path]:
    """The serving code and dependency manifests an init must restart to adopt."""
    return [
        *sorted((root / "skills/leaf/scripts").rglob("*.py")),
        root / "pyproject.toml",
        root / "uv.lock",
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
    the number was declared names none, and is refused too. A key renamed or removed
    since the page was vendored is the same kind of fact: this Leaf would read the
    key's new name, find nothing, and drop what the page's layer declares under the
    old one, so the page is refused rather than misread. The check is one-sided: a
    key this Leaf added and an older layer lacks refuses nothing. Every page server,
    the gate's and the website's included (`http.page_endpoint`,
    `leaf_website.page_binding`), the one append door and the writers that ask it
    first (`event_contracts.write_refusal`), and `page check` refuse on this one
    reading, each naming the re-vendor that repairs the page; the holding session's
    commands and hooks make that re-vendor first for a page vendored at an older
    number (`vendoring.renew_layer`). So does the source
    check (`validation.source.check_source`), so activation writes no revision under
    the layer and `page state` reports the refusal as `source.error`. A revision the
    page saved before its last re-vendor is judged on its own registry
    (`incompatible_revision`).
    """
    if (vendored := _foreign_protocol(registry)) is not None:
        return Finding(
            "foreign-layer",
            values={
                "page": str(page_dir),
                "vendored": vendored,
                "leaf": str(PLUGIN_ROOT),
                "protocol": kernel_protocol(),
            },
        )
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


def incompatible_revision(revision: int, registry: dict) -> Finding | None:
    """Why this Leaf can neither serve one of a page's revisions nor admit input made
    against it, given the registry that revision captured: it was saved at another
    protocol, or its vocabulary uses an x- key this Leaf no longer admits, the two
    refusals `incompatible_layer` makes of the page's layer. None when it may.

    Each revision captures the runtime and registry it was saved with, and a
    re-vendor leaves existing revisions as they were, so a page re-vendored across a
    bump still holds revisions saved before it. Served, one would run its own runtime
    against this Leaf's server, which is the break the protocol announces. The
    document server and the append door ask this of the revision they would serve or
    admit under; readings of the log keep reading every revision's registry, so
    history still projects. Serving the page saves its source as a revision first,
    so its live revision is one of these only where the source no longer saves.
    A revision whose vocabulary uses a retired key is refused for the reason the
    layer is: this Leaf would read the key's new name there, find nothing, and draw
    the revision without what it declares, such as a framed ask's prompt.
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
    declared = registry.get("$events", {}).get("protocol")
    if type(declared) is int and declared == kernel_protocol():
        return None
    return declared if declared is not None else "none"


def payload_provenance(*, include_path: bool = False, root: Path | None = None) -> dict:
    """Describe the Leaf payload that is running this command, when its source can.

    Beside the commit, one of two dates says how old the payload is: `committed`,
    the commit's committer date, where Git can read it; or `installed`, when a harness
    copied the payload into its plugin cache without `.git`. Both are ISO 8601 with
    an offset. Developer preparations can pass `root` to read another checkout
    through the same provenance rules.
    """
    source = (
        Path(__file__) if root is None else root / "skills/leaf/scripts/leaf/layer.py"
    )
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

    `+` marks uncommitted changes, as the page banner does.
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
    """Read and validate the complete layer produced by checked inputs."""
    from .revision_artifact import (
        dependency_path,
        javascript_imports,
    )
    from .validation.composition import incoming_registry

    protected = kernel_runtime_paths()
    private_modules = {"/leaf.js", *(f"/runtime/{name}" for name in protected)} - {
        "/runtime/widget-api.js"
    }
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
                    dependency = dependency_path(specifier, path, module=True)
                    if dependency in private_modules:
                        raise Refused(
                            f"{module} imports private kernel module {specifier!r}; "
                            "use /runtime/widget-api.js"
                        )
    incoming = incoming_registry(roots)
    directory_sources = {sub: composed_dir_files(roots, sub) for sub in BROWSER_DIRS}
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
    client = directory_files["runtime"].get("layer-generation.js", b"")
    if client.count(LAYER_PLACEHOLDER) != 1:
        raise Refused(
            "the incoming runtime/layer-generation.js must contain exactly one "
            "layer-generation placeholder"
        )
    directory_files[INSTRUCTIONS_DIR] = composed_instructions(roots)
    return LayerComposition(incoming, top_files, directory_files)
