"""Personal theme selection, recorded with a page's packages.

Themes are ordinary named packages. The user's TOML catalogue chooses which ones
agents may select and one optional default; the package's author instructions
describe its intended uses. A page records its selection separately from content
packages, so replacing one never silently retains the previous theme. Existing
pages keep their recorded selection, including none, until explicitly changed.

A page records the theme's name, and whichever Leaf reads the page composes that
package as it finds it, as it does every package the page selects
(`layer.selected_layer`). Applying the catalogue's current default to existing
pages can be reconsidered when that use appears; it does not require changing the
selection interface.
"""

import os
import tomllib
from pathlib import Path
from typing import Literal

from jsonschema import Draft202012Validator

from .layer import named_package
from .refusals import Refused
from .schema import HTML_NAME

type ThemeChoice = str | Literal[False] | None

_CATALOGUE = Draft202012Validator(
    {
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
)


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
    if error := next(_CATALOGUE.iter_errors(config), None):
        raise Refused(f"{path}: {error.message}")
    if (default := config.get("default")) is not None and default not in config[
        "themes"
    ]:
        raise Refused(f"{path}: default {default!r} must be in themes")
    return path, config


def cmd_list() -> dict:
    """Discover named themes and their package-owned authoring instructions."""
    path, config = catalogue()
    themes = []
    for name in config["themes"]:
        root = named_package(name)
        instructions = root / "instructions/author.md" if root else None
        themes.append(
            {
                "name": name,
                "default": name == config.get("default"),
                "available": root is not None,
                "instructions": instructions.read_text()
                if instructions and instructions.is_file()
                else "",
            }
        )
    return {"config": str(path), "themes": themes}


def selected_theme(page_dir: Path, choice: ThemeChoice, *, fresh: bool) -> dict | None:
    """Resolve an explicit choice, a captured choice, or a fresh page's default.

    False is the CLI's `--no-theme` or `--no-packages`: remove the selected theme. None
    means preserve an existing capture, or consult the default for a fresh page.
    A captured selection needs no catalogue entry: removing it from the catalogue
    affects future authoring, while its package is resolved wherever the page is read.
    """
    if choice is False:
        return None
    if choice is None and not fresh:
        from .registry.storage import layer_record

        return (layer_record(page_dir) or {}).get("theme")
    path, config = catalogue()
    name = choice if choice is not None else config.get("default")
    if name is None:
        return None
    if name not in config["themes"]:
        raise Refused(
            f"theme {name!r} is not in {path}; run `leaf theme list` to see the choices"
        )
    return {"name": name, "source": "explicit" if choice is not None else "default"}


def with_theme(packages: tuple[str, ...], theme: dict | None) -> tuple[str, ...]:
    """The selected theme composes last, once, after the content packages."""
    if theme is None:
        return packages
    return (*[name for name in packages if name != theme["name"]], theme["name"])
