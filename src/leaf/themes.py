"""Theme selection, recorded with a page's packages.

A theme is a page's look: an ordinary named package composed right after Leaf's default
package and before the content packages, so a project package can restate what the theme
declares. Leaf bundles one, `reading` (`DEFAULT_THEME`), which a new page takes unless
the user's TOML catalogue names another default; the catalogue lists the personal themes
agents may select, and each package's author instructions describe its intended uses. A
page that takes none starts from the browser's defaults and Leaf's tokens. A page
records its selection separately from content packages, so replacing one never silently
retains the previous theme. Existing pages keep their recorded selection, including
none, until explicitly changed.

A theme either stands alone or builds on another theme it names as its base, in its
registry's `$theme` (`theme_base`). Leaf composes the base, after any base that one
names, and then the theme (`with_theme`), so a theme that wants `reading` with three
other colours states only those. Leaf composes no theme the page or its theme didn't
name. The user chose this: `reading` is a choice a theme may modify or replace, not a
base every theme sits on. Composing `reading` under every theme would leave a theme no
way to replace it. A theme loses nothing by standing alone, since the idioms
an author writes, such as a tag or a callout, are Leaf's own (browser/registry.json)
and draw on every page.

A page records the theme's name, and whichever Leaf reads the page composes that
package, and the bases it names, as it finds them, as it does every package the page
selects (`layer.selected_layer`). Applying the catalogue's current default to existing
pages can be reconsidered when that use appears; it does not require changing the
selection interface.
"""

import os
import tomllib
from pathlib import Path
from typing import Literal

from .layer import named_package
from .refusals import Refused
from .registry.schema import json_validator
from .schema import HTML_NAME

type ThemeChoice = str | Literal[False] | None

# The look a new page takes when the user names no default: the bundled package that
# holds Leaf's reading look.
DEFAULT_THEME = "reading"

_CATALOGUE_SCHEMA = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            "uniqueItems": True,
        },
        "default": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["themes"],
    "additionalProperties": False,
}
# A theme's `$theme` declaration: the installed theme it builds on.
_BASE_SCHEMA = {
    "type": "object",
    "properties": {"base": {"type": "string", "pattern": f"^{HTML_NAME}$"}},
    "required": ["base"],
    "additionalProperties": False,
}


def catalogue() -> tuple[Path, dict]:
    """Read the one user-authored catalogue; absence means no personal themes."""
    path = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "leaf/themes.toml"
    )
    try:
        with path.open("rb") as source:
            config = tomllib.load(source)
    except FileNotFoundError:
        return path, {"themes": []}
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise Refused(f"{path}: {error}") from None
    if error := next(iter(json_validator(_CATALOGUE_SCHEMA).iter_errors(config)), None):
        raise Refused(f"{path}: {error.message}")
    if (default := config.get("default")) is not None and default not in config[
        "themes"
    ]:
        raise Refused(f"{path}: default {default!r} must be in themes")
    return path, config


def cmd_list() -> dict:
    """Discover named themes and their package-owned authoring instructions: Leaf's
    own, then the catalogue's."""
    path, config = catalogue()
    default = config.get("default", DEFAULT_THEME)
    themes = []
    for name in dict.fromkeys((DEFAULT_THEME, *config["themes"])):
        root = named_package(name)
        instructions = root / "instructions/author.md" if root else None
        themes.append(
            {
                "name": name,
                "default": name == default,
                "available": root is not None,
                "instructions": instructions.read_text()
                if instructions and instructions.is_file()
                else "",
            }
        )
    return {"config": str(path), "themes": themes}


def selected_theme(page_dir: Path, choice: ThemeChoice, *, fresh: bool) -> dict | None:
    """Resolve an explicit choice, a captured choice, or a fresh page's default.

    False is the CLI's `--no-theme`: take none. None means preserve an existing
    capture, or take the default for a fresh page: the catalogue's, else Leaf's own.
    A captured selection needs no catalogue entry: removing it from the catalogue
    affects future authoring, while its package is resolved wherever the page is read.
    """
    if choice is False:
        return None
    if choice is None and not fresh:
        from .registry.storage import layer_record

        return (layer_record(page_dir) or {}).get("theme")
    path, config = catalogue()
    name = choice if choice is not None else config.get("default", DEFAULT_THEME)
    if name != DEFAULT_THEME and name not in config["themes"]:
        raise Refused(
            f"theme {name!r} is not in {path}; run `leaf theme list` to see the choices"
        )
    return {"name": name, "source": "explicit" if choice is not None else "default"}


def with_theme(packages: tuple[str, ...], theme: dict | None) -> tuple[str, ...]:
    """The packages a selection composes, in order: the recorded theme after the bases
    it builds on (`base_chain`), then the content packages, each once. A page that
    takes no theme composes none. A theme that is not installed is left for resolving
    the selection to refuse, as any package is (`layer.resolve_packages`)."""
    if theme is None:
        return packages
    name = theme["name"]
    root = named_package(name)
    bases = base_chain(root) if root is not None else ()
    return tuple(dict.fromkeys((*bases, name, *packages)))


def base_chain(root: Path) -> tuple[str, ...]:
    """The themes the package at `root` builds on, the base-most first: the base its
    registry names (`theme_base`), after the base that one names, and so on. Refused
    where a base is not installed or the bases name each other."""
    chain: tuple[str, ...] = ()
    while base := theme_base(root):
        if base in chain:
            raise Refused(
                "themes build on each other: " + " -> ".join((*reversed(chain), base))
            )
        if (found := named_package(base)) is None:
            raise Refused(
                f"{root.name!r} builds on theme {base!r}, which is not installed"
            )
        chain, root = (base, *chain), found
    return chain


def theme_base(root: Path) -> str | None:
    """The theme the package at `root` builds on, as its registry's `$theme.base`
    names it, or None for a package that stands alone."""
    from .registry.contract import read_registry_declarations

    declared = (read_registry_declarations(root / "registry.json") or {}).get("$theme")
    if declared is None:
        return None
    if error := next(iter(json_validator(_BASE_SCHEMA).iter_errors(declared)), None):
        raise Refused(f"{root / 'registry.json'}: $theme: {error.message}")
    return declared["base"]
