"""Package authoring commands and filesystem safety gates."""

import contextlib
import fcntl
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from .files import json_bytes, read_json, replace_files
from .host import config_home, package_store
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
    path_is_within,
    path_location,
    paths_same,
)
from .schema import (
    BROWSER_DIRS,
    DEFAULT_PACKAGE,
    ELEMENT_ID,
    EVENTS_FILE,
    HTML_NAME,
    KERNEL,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    VENDORED_FILES,
    WIDGET_NAME,
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
        for parent in {path.parent for path, _contents in files}:
            descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
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


def starter_widget_entry(tag: str) -> dict:
    """One useful upgraded prose block, ready for a package author to specialize."""
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
        "x-content": "prose",
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
    """Copy exactly what a layer input reads into an empty directory.

    The rest of the source directory — a README, the author's own tests, `.git` —
    belongs to the author rather than to the package, so it reaches neither a
    staged candidate nor the store. Absent package directories are created empty,
    as `package init` creates them.
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
        sys.exit(f"widget tag {widget!r} must match {WIDGET_NAME}")
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
    registry[widget] = starter_widget_entry(widget)
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
            [package, *(package / name for name in (*PACKAGE_FILES, *PACKAGE_DIRS))],
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
