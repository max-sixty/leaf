"""Layer input resolution, composition, and content identity."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from .host import config_home, package_store
from .locations import located, locations_overlap
from .schema import (
    ASSETS,
    BROWSER_DIRS,
    BUNDLED_PACKAGES,
    DEFAULT_PACKAGE,
    GUIDANCE_DIR,
    GUIDANCE_FILE,
    HTML_NAME,
    LAYER_PLACEHOLDER,
    PACKAGE_DIRS,
    PLUGIN_ROOT,
    VENDORED_FILES,
)
from .styles import css_syntax_errors
from .validation.compatibility import incoming_registry


def named_package(name: str) -> Path | None:
    """The one directory a bare package name selects, installed or bundled.

    `package install` refuses a name a bundled package already answers to, so the
    roots collide only where a later Leaf release ships a name someone installed
    before it existed. The installed copy wins there, because the pages selecting
    that name were written against it. Nothing downstream asks which root
    answered: an installed package is the same directory contract elsewhere.
    """
    roots = (package_store(), BUNDLED_PACKAGES)
    return next((root / name for root in roots if (root / name).is_dir()), None)


def resolve_packages(selected: tuple[str, ...]) -> list[Path]:
    """Resolve recorded package selections without changing their order.

    A bare name selects an installed or bundled package. Other relative paths
    are project-relative, like the implicit `.leaf/` package. A `~` path stays
    portable across the user's machines. Absolute paths are not recorded because
    `$layer.packages` is part of the page's public vendored registry.
    """
    packages = []
    for value in selected:
        if re.fullmatch(HTML_NAME, value):
            if value == DEFAULT_PACKAGE.name:
                sys.exit("package 'default' is already included in every page")
            named = named_package(value)
            if named is None:
                sys.exit(
                    f"unknown package {value!r}; run `leaf package install` to add "
                    f"it, or use './{value}' for a project-relative package path"
                )
            packages.append(named)
            continue
        package_path = Path(value)
        if package_path.is_absolute():
            sys.exit(
                f"package {value!r} is absolute; use a bundled name, "
                "explicit project-relative path, or ~ path so the vendored registry "
                "does not publish a machine path"
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
    return [ASSETS, *package_roots(selected)]


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
        for name in VENDORED_FILES:
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


def layer_fingerprint(composition: LayerComposition) -> str:
    """Identify the complete composed layer independently of its vendoring epoch."""
    files = {
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
    digest = hashlib.sha256()
    for name in sorted(files):
        encoded = name.encode()
        data = files[name]
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def payload_provenance(*, include_path: bool = False) -> dict:
    """Describe the Leaf payload that is running this command, when Git can."""
    provenance = {"path": str(PLUGIN_ROOT)} if include_path else {}
    git = ["git", "--no-optional-locks", "-C", str(PLUGIN_ROOT)]
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
    if len(lines) != 2 or Path(lines[0]).resolve() != PLUGIN_ROOT.resolve():
        return provenance
    provenance["commit"] = lines[1]
    try:
        dirty = subprocess.run(
            [*git, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return provenance
    if dirty.returncode == 0:
        provenance["dirty"] = bool(dirty.stdout)
    return provenance


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
    directory_files = {
        sub: {
            name: source.read_bytes() for name, source in directory_sources[sub].items()
        }
        for sub in BROWSER_DIRS
    }
    client = directory_files["runtime"].get("layer-client.js", b"")
    if client.count(LAYER_PLACEHOLDER) != 1:
        sys.exit(
            "the incoming runtime/layer-client.js must contain exactly one "
            "layer-generation placeholder"
        )
    directory_files[GUIDANCE_DIR] = composed_guidance(roots)
    return LayerComposition(incoming, top_files, directory_files)
