"""Package authoring commands and filesystem safety gates."""

import sys
from pathlib import Path

from .files import replace_files
from .host import config_home
from .layer import (
    checked_inputs,
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_inputs,
)
from .locations import (
    located,
    location_is_within,
    locations_overlap,
    path_is_within,
    path_location,
    paths_same,
)
from .schema import (
    BROWSER_DIRS,
    DEFAULT_PACKAGE,
    KERNEL,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    VENDORED_FILES,
)


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
    at = path_location(resolved)
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
