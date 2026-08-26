"""Layer composition, page vendoring, and package commands."""

import json
import secrets
import sys
from pathlib import Path
from typing import NamedTuple

from .data import data_contract_errors, page_data_bindings, read_data_store
from .events import flocked, now_iso, read_events
from .files import (
    _path_location,
    json_bytes,
    located,
    location_is_within,
    locations_overlap,
    path_is_within,
    paths_same,
    published_versions,
    read_json,
    replace_files,
    version_path,
    write_json,
)
from .projection import page_projection
from .schema import (
    BROWSER_DIRS,
    DEFAULT_PACKAGE,
    GUIDANCE_DIR,
    GUIDANCE_FILE,
    KERNEL,
    LAYER_PLACEHOLDER,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    VENDORED_FILES,
)
from .service import (
    PageTransaction,
    claim_path,
    config_home,
    init_lock_path,
    lock_is_held,
    transition_lock,
)
from .styles import css_syntax_errors
from .validation import incoming_registry, vocabulary_gaps
from .work import widget_work_without_seats


def resolve_packages(selected: tuple[str, ...]) -> list[Path]:
    """Resolve recorded package paths without changing their order.

    Relative paths are project-relative, like the implicit `.leaf/` package. A `~`
    path stays portable across the user's machines. Absolute paths are not recorded
    because `$layer.packages` is part of the page's public vendored registry.
    """
    packages = []
    for value in selected:
        package_path = Path(value)
        if package_path.is_absolute():
            sys.exit(
                f"package {value!r} is absolute; use a project-relative or ~ path "
                "so the vendored registry does not publish a machine path"
            )
        root = package_path.expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        if not (root.exists() or root.is_symlink()):
            sys.exit(f"package {value!r} is not a directory")
        packages.append(root)
    return packages


def package_roots(selected: tuple[str, ...] = ()) -> list[Path]:
    """Packages in composition order, from the bundled default to the project."""
    return [
        DEFAULT_PACKAGE,
        *resolve_packages(selected),
        config_home(),
        Path.cwd() / ".leaf",
    ]


def layer_inputs(selected: tuple[str, ...] = ()) -> list[Path]:
    """The kernel followed by every package, in layer precedence order."""
    return [KERNEL, *package_roots(selected)]


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
            sys.exit(f"{root} must be a directory")
        for name in PACKAGE_FILES:
            path = root / name
            if (path.exists() or path.is_symlink()) and not path.is_file():
                sys.exit(f"{path} must be a file")
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            if not directory.is_dir():
                sys.exit(f"{directory} must be a directory")
            if sub == GUIDANCE_DIR:
                for path in directory.iterdir():
                    if not path.is_file():
                        sys.exit(f"{path} must be a file")
                    if not GUIDANCE_FILE.fullmatch(path.name):
                        sys.exit(f"{path} must be named <audience>.md")
                continue
            for path in directory.rglob("*"):
                if path.is_dir() and not path.is_symlink():
                    continue
                if not path.is_file():
                    sys.exit(f"{path} must be a file or real directory")
        roots.append(root)
    return roots


def input_paths(inputs: list[Path]) -> list[Path]:
    """Every path a layer input reads, including nested symlink targets."""
    paths = []
    for root in inputs:
        paths.append(root.resolve())
        paths.extend(
            path.resolve()
            for name in PACKAGE_FILES
            if ((path := root / name).exists() or path.is_symlink())
        )
        for sub in PACKAGE_DIRS:
            directory = root / sub
            if not (directory.exists() or directory.is_symlink()):
                continue
            paths.append(directory.resolve())
            if directory.is_dir():
                entries = (
                    directory.iterdir() if sub == GUIDANCE_DIR else directory.rglob("*")
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


def composed_theme(inputs: list[Path]) -> str:
    """One stylesheet whose input order is the layer precedence."""
    stylesheets = [
        root / "theme.css" for root in inputs if (root / "theme.css").is_file()
    ]
    if not stylesheets:
        sys.exit("the incoming layer has no theme.css")
    parts = []
    for source in stylesheets:
        try:
            css = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            sys.exit(f"{source} must be UTF-8")
        if errors := css_syntax_errors(css, str(source)):
            sys.exit(errors[0])
        parts.append(css if css.endswith("\n") else css + "\n")
    return "".join(parts)


def composed_guidance(inputs: list[Path]) -> dict[str, bytes]:
    """Package guidance joined by audience in layer precedence order."""
    parts: dict[str, list[str]] = {}
    for root in inputs:
        directory = root / GUIDANCE_DIR
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            try:
                guidance = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                sys.exit(f"{path} must be UTF-8")
            if guidance.strip():
                parts.setdefault(path.name, []).append(guidance.rstrip() + "\n")
    return {name: "\n".join(passages).encode() for name, passages in parts.items()}


def checked_layer_inputs(inputs: list[Path]) -> list[Path]:
    """Structurally valid, non-overlapping inputs in composition order."""
    roots = checked_inputs(inputs)
    if overlap := overlapping_inputs(roots):
        left_root, left, right_root, right = overlap
        sys.exit(
            f"layer inputs {left_root} and {right_root} overlap at {left} and "
            f"{right}; package scopes must be separate"
        )
    return roots


class LayerComposition(NamedTuple):
    registry: dict
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]


def compose_layer(roots: list[Path]) -> LayerComposition:
    """Read and validate the complete layer produced by checked inputs."""
    incoming = incoming_registry(roots)
    directory_sources = {sub: composed_dir_files(roots, sub) for sub in BROWSER_DIRS}
    missing_modules = sorted(
        tag
        for tag, entry in incoming.items()
        if tag.startswith("lf-")
        and entry["x-upgrade"]
        and f"{tag}.js" not in directory_sources["widgets"]
    )
    if missing_modules:
        sys.exit(
            "the incoming registry marks widgets as upgraded but their modules "
            "are missing:\n"
            + "\n".join(f"  - widgets/{tag}.js" for tag in missing_modules)
        )

    top_files = {"theme.css": composed_theme(roots).encode()}
    for name in VENDORED_FILES:
        if name == "registry.json" or name in top_files:
            continue
        source = next(
            (source / name for source in reversed(roots) if (source / name).is_file()),
            None,
        )
        if source is None:
            sys.exit(f"the incoming layer has no {name}")
        top_files[name] = source.read_bytes()
    if top_files["leaf.js"].count(LAYER_PLACEHOLDER) != 1:
        sys.exit(
            "the incoming leaf.js must contain exactly one layer-generation placeholder"
        )
    directory_files = {
        sub: {
            name: source.read_bytes() for name, source in directory_sources[sub].items()
        }
        for sub in BROWSER_DIRS
    }
    directory_files[GUIDANCE_DIR] = composed_guidance(roots)
    return LayerComposition(incoming, top_files, directory_files)


def cmd_init(page_dir: Path, selected: tuple[str, ...] | None = None) -> None:
    # Before the directory exists there is no comments log for PageTransaction
    # to lock. This one external lease covers that missing first instant through
    # the complete vendoring, so two public inits cannot both observe freshness
    # and the earlier one cannot later erase the page the other created.
    path = init_lock_path(page_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(path), flocked(transition_lock(page_dir)):
        _init_page(page_dir, selected)


def _init_page(page_dir: Path, selected: tuple[str, ...] | None) -> None:
    service = read_json(page_dir / "service.json")
    server_live = lock_is_held(page_dir / "server.lock")
    if server_live or (service and service["enabled"]):
        sys.exit(
            f"cannot re-vendor {page_dir} while its service is enabled. "
            f"Run `leaf server stop {page_dir}` first."
        )
    # Successful init creates the append-only log's stable inode. A directory
    # the caller prepared is still a fresh page until that marker exists: it
    # keeps the caller's chosen mode, takes no PageTransaction yet, and a failed
    # validation leaves it untouched.
    fresh = not (page_dir / "comments.jsonl").is_file()
    if selected is None and fresh:
        selected = ()
    elif selected is None:
        recorded = (
            (read_json(page_dir / "registry.json") or {})
            .get("$layer", {})
            .get("packages", [])
        )
        if (
            not isinstance(recorded, list)
            or not all(
                isinstance(selection, str) and selection for selection in recorded
            )
            or len(set(recorded)) != len(recorded)
        ):
            sys.exit(
                f"{page_dir / 'registry.json'}: $layer.packages must be a unique "
                "list of non-empty package paths"
            )
        selected = tuple(recorded)
    inputs = layer_inputs(selected)
    page_target = page_dir.resolve()
    # Refuse a package before PageTransaction opens the page log:
    # this directory is not a page, and a rejected init must not put page state
    # inside an input it was trying to protect.
    if package := next(
        (root for root in inputs if path_is_within(page_target, root)),
        None,
    ):
        sys.exit(f"{page_dir} is inside package {package}, not a page directory")
    if fresh:
        _vendor_page(
            page_dir,
            fresh=True,
            inputs=inputs,
            page_target=page_target,
            selected=selected,
        )
        return
    # The init lease serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the vocabulary check
    # and contract commit one order against every browser append. No path takes
    # the page transaction and then the init lease, so this order cannot invert.
    with PageTransaction(page_dir):
        _vendor_page(
            page_dir,
            fresh=False,
            inputs=inputs,
            page_target=page_target,
            selected=selected,
        )


def _vendor_page(
    page_dir: Path,
    *,
    fresh: bool,
    inputs: list[Path],
    page_target: Path,
    selected: tuple[str, ...],
) -> None:
    # Re-vendoring is the one moment a page's vocabulary changes hands, so it is
    # where drift has to be caught: a tag or verb the new layer omits, or a
    # detail schema that no longer accepts an old payload, makes a recorded
    # action foreign on the first reload — the lost-decision bug reintroduced
    # through vocabulary drift instead of version-scoping.
    roots = checked_layer_inputs(inputs)
    destinations = [
        *(page_target / name for name in PACKAGE_FILES),
        *(page_target / sub for sub in ("versions", *PACKAGE_DIRS)),
    ]
    located_destinations = located(destinations)
    if overlap := next(
        (
            (package, destination)
            for package, package_at in located(input_paths(roots))
            for destination, destination_at in located_destinations
            if locations_overlap(package_at, destination_at)
        ),
        None,
    ):
        package, destination = overlap
        sys.exit(
            f"package {package} overlaps page destination "
            f"{destination}; package and page paths must be separate"
        )
    composition = compose_layer(roots)
    incoming = composition.registry
    events = read_events(page_dir)
    gaps = vocabulary_gaps(page_dir, events, incoming)
    if gaps:
        sys.exit(
            "this page's log holds vocabulary the incoming layer no longer speaks:\n"
            + "\n".join(f"  - {g}" for g in gaps)
            + "\nre-vendoring would silently stop these replaying — the user's"
            " recorded decisions among them."
        )
    stored_data = read_data_store(page_dir)
    # The outgoing registry is historical input, not a contract arriving at the
    # current code's boundary. It may legitimately predate a new kernel invariant;
    # validating it with today's rules would prevent `page init` from replacing the
    # exact older layer it exists to migrate. Binding discovery only reads x-data.
    if current := read_json(page_dir / "registry.json"):
        standing_bindings, standing_errors = page_data_bindings(
            page_dir, current, events
        )
        incoming_bindings, incoming_errors = page_data_bindings(
            page_dir, incoming, events
        )
        binding_errors = list(dict.fromkeys(standing_errors + incoming_errors))
        binding_changes = [
            (
                f"source {source!r} loses its contract {contract!r}"
                if source not in incoming_bindings
                else f"source {source!r} changes from contract {contract!r} to "
                f"{incoming_bindings[source]!r}"
            )
            for source, contract in standing_bindings.items()
            if incoming_bindings.get(source) != contract
        ]
        if binding_errors or binding_changes:
            sys.exit(
                "this page's immutable documents do not keep one meaning for each "
                "data source:\n"
                + "\n".join(
                    f"  - {error}" for error in binding_errors + binding_changes
                )
                + "\nuse a new source id for a new contract before re-vendoring."
            )
    if data_errors := data_contract_errors(stored_data, incoming):
        sys.exit(
            "this page holds external data the incoming layer no longer speaks:\n"
            + "\n".join(f"  - {error}" for error in data_errors)
            + "\nclear those sources with `leaf data clear` before re-vendoring."
        )
    published = published_versions(page_dir, events)
    if published:
        version = published[-1]
        html = version_path(page_dir, version).read_text(encoding="utf-8")
        projection, parser, _spk = page_projection(html, events, incoming, version)
        unseated = widget_work_without_seats(
            html,
            parser,
            projection,
            events,
            read_json(page_dir / "status.json") or {},
            incoming,
        )
        if unseated:
            sys.exit(
                "the incoming layer would remove the local seat for active widget "
                "work on "
                + ", ".join(repr(widget) for widget in unseated)
                + "; publish a later version with --completes for that work before "
                "re-vendoring"
            )

    # Resolve and read the complete incoming layer before the first page write.
    # A bad late package must not leave the registry newer than the theme or its
    # modules.
    top_files = composition.top_files
    # `page init` is the contract transition, even when its input bytes happen to
    # match the last run. The browser carries this epoch on every write so an open
    # tab cannot post through a runtime whose server contract was re-vendored under it.
    generation = secrets.token_hex(16)
    incoming["$layer"] = {"generation": generation, "packages": list(selected)}
    runtime = top_files["leaf.js"]
    top_files["leaf.js"] = runtime.replace(
        LAYER_PLACEHOLDER, json.dumps(generation).encode()
    )
    # The registry makes the theme and modules live, so it commits last.
    top_files["registry.json"] = json_bytes(incoming)
    directory_files = composition.directory_files

    # Resolve every destination conflict before touching the page. A directory
    # where one vendored file belongs must not leave the top-level layer newer
    # than its modules.
    if (page_dir.exists() or page_dir.is_symlink()) and not page_dir.is_dir():
        sys.exit(f"{page_dir} must be a directory")
    file_targets = [
        *(page_dir / name for name in top_files),
        *(
            page_dir / sub / name
            for sub in PACKAGE_DIRS
            for name in directory_files[sub]
        ),
    ]
    directories = {
        page_dir / "versions",
        *(page_dir / sub for sub in PACKAGE_DIRS),
    }
    for target in file_targets:
        for parent in target.parents:
            if parent == page_dir:
                break
            directories.add(parent)
    located_files = [(target, _path_location(target)) for target in file_targets]
    located_directories = [
        (directory, _path_location(directory)) for directory in directories
    ]
    if collision := next(
        (
            (left, right)
            for index, (left, left_at) in enumerate(located_files)
            for right, right_at in located_files[index + 1 :]
            if left_at == right_at
        ),
        None,
    ):
        left, right = collision
        sys.exit(f"the incoming layer maps both {left} and {right} to one file")
    if collision := next(
        (
            (file, directory)
            for file, file_at in located_files
            for directory, directory_at in located_directories
            if file_at == directory_at
        ),
        None,
    ):
        file, directory = collision
        sys.exit(
            f"the incoming layer maps {file} as a file and {directory} as a directory"
        )
    for destination in sorted(directories, key=lambda path: len(path.parts)):
        if destination.is_symlink():
            sys.exit(f"{destination} must be a real directory, not a symlink")
        if (
            destination.exists() or destination.is_symlink()
        ) and not destination.is_dir():
            sys.exit(f"{destination} must be a directory")
    for target in file_targets:
        if (target.exists() or target.is_symlink()) and not target.is_file():
            sys.exit(f"{target} must be a file")

    # Owner-only when this call creates it: the directory holds the discussion
    # and service state whose URL carries the machine key. A directory the
    # caller already made keeps the mode they chose.
    if fresh:
        # A page's claim lives outside its directory. Recreating a deleted path
        # creates a new page, so it must not inherit the deleted page's owner.
        # Re-vendoring an existing page preserves that page and its claim.
        claim_path(page_dir).unlink(missing_ok=True)
    page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        directory.mkdir(exist_ok=True)
    # Stage the whole layer together. The registry is the declaration that
    # makes every other file live, so it is the final replacement.
    writes = [
        (page_dir / name, data, False)
        for name, data in top_files.items()
        if name != "registry.json"
    ]
    writes.extend(
        (page_dir / sub / name, data, False)
        for sub in PACKAGE_DIRS
        for name, data in directory_files[sub].items()
    )
    writes.append((page_dir / "registry.json", top_files["registry.json"], False))
    replace_files(writes)

    for sub in PACKAGE_DIRS:
        destination = page_dir / sub
        wanted = set(directory_files[sub])
        for stale in sorted(
            destination.rglob("*"), key=lambda path: len(path.parts), reverse=True
        ):
            relative = stale.relative_to(destination).as_posix()
            if relative not in wanted and (stale.is_symlink() or stale.is_file()):
                stale.unlink()
            elif stale.is_dir():
                try:
                    stale.rmdir()
                except OSError:
                    pass
    if not (page_dir / "status.json").exists():
        # Fresh creation holds the init lease; re-vendoring holds both it and
        # the page transaction. Calling cmd_status would try to re-enter the
        # latter's comments-log flock for an existing directory missing status.
        write_json(
            page_dir / "status.json",
            {"state": "working", "detail": "Writing the page", "ts": now_iso()},
        )
    # The append-only log's stable inode is also the successful-init marker and
    # the page transaction lease. Publish it only after the layer and initial
    # status commit, so a failed first write still takes the fresh-init path.
    with open(page_dir / "comments.jsonl", "a", encoding="utf-8"):
        pass
    print(f"initialized {page_dir}")


def protected_package_paths(package: Path) -> list:
    """Resolved paths owned by the kernel and every other package."""
    paths = []
    implicit = {config_home(), Path.cwd() / ".leaf"}
    independent = package not in implicit
    for other in layer_inputs():
        if other == package:
            continue
        # A standalone package repository naturally contains the project's future
        # `.leaf/` package. There is no second package until that directory exists; if
        # it later does, page init's ordinary overlap gate refuses composing both.
        # Keep protecting existing implicit packages and
        # every future peer scope, but do not make an absent child reserve its parent.
        if (
            independent
            and other in implicit
            and not (other.exists() or other.is_symlink())
            and path_is_within(other, package)
        ):
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
    at = _path_location(resolved)
    for root in (resolved, *resolved.parents):
        # Runtime state is disposable and regenerated; it cannot identify the
        # page whose owned paths this gate protects.
        if not (
            (root / "versions").is_dir()
            and all((root / name).is_file() for name in VENDORED_FILES)
            and all((root / name).is_dir() for name in BROWSER_DIRS)
        ):
            continue
        if (
            at == _path_location(root)
            or any(at == _path_location(root / name) for name in PAGE_OWNED_FILES)
            or any(
                location_is_within(at, _path_location(root / name))
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


def validate_package_dir(package: Path) -> list:
    if (package.exists() or package.is_symlink()) and not package.is_dir():
        sys.exit(f"{package} must be a directory")
    if package.is_dir():
        checked_inputs([package])
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
    return [KERNEL, DEFAULT_PACKAGE, package]


def check_package(package: Path, *, require_exists: bool) -> tuple[Path, list]:
    """Validate one package through the same composition gate as a page."""
    package = package.expanduser().resolve()
    if require_exists and not package.is_dir():
        sys.exit(f"{package} is not a package directory")
    protected = validate_package_dir(package)
    roots = checked_layer_inputs(package_layer_inputs(package))
    compose_layer(roots)
    return package, protected


def cmd_package_init(package: Path) -> Path:
    package, protected = check_package(package, require_exists=False)
    refuse_package_overlap(
        [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
        protected,
    )

    files = {
        "registry.json": b"{}\n",
        "theme.css": b"",
    }
    writes = [
        (package / name, contents, False)
        for name, contents in files.items()
        if not ((package / name).exists() or (package / name).is_symlink())
    ]
    package.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_DIRS:
        (package / name).mkdir(exist_ok=True)
    replace_files(writes)
    print(f"initialized {package}")
    return package


def cmd_package_check(package: Path) -> Path:
    package, _ = check_package(package, require_exists=True)
    print(f"checked {package}")
    return package
