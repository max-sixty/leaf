"""Layer composition and package commands."""

import sys
from pathlib import Path
from typing import NamedTuple

from .files import (
    _path_location,
    located,
    location_is_within,
    locations_overlap,
    path_is_within,
    paths_same,
    replace_files,
)
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
from .service import config_home
from .styles import css_syntax_errors
from .validation import incoming_registry


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
