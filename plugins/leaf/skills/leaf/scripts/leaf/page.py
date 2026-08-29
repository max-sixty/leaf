"""Vendored page guidance and vocabulary catalog."""

import json
import sys
from pathlib import Path

from .registry.storage import require_registry
from .schema import GUIDANCE_DIR

CATALOG_PREAMBLE = """\
# Widget vocabulary, vendored for this page — `version check` validates against it.
#
# Widgets are lf-* elements in the authored HTML; attributes carry scalars
# (enums, flags), children carry prose, and an item's title is a leading
# <strong> child. Every lf-* element takes an explicit end tag — never
# <lf-foo/>. Ids are authored (lowercase kebab), unique, stable across
# versions. Each entry is JSON Schema over the attributes, plus the x- keys
# that say how the layer treats the tag — what each of those means is printed
# after the entries ($keys).
"""


# Familiar layer-wide facts get a sentence saying what an author reads them for.
# Package-defined `$` facts print afterward under their own names, so extending the
# vocabulary needs no catalog branch. `$events` and `$layer` stay absent: they are the
# runtime contract and vendoring record, not declarations an author writes markup from.
CATALOG_FACTS = (
    ("$keys", "The x- keys an entry may declare, and what each one means."),
    (
        "$restated",
        "`restated` — the one attribute that spans widgets; read it before revising one.",
    ),
    ("$state", "x-state's fields — the facet, fold unit, and record forms."),
    ("$report", "x-report's fields — how a version answers a standing report."),
    ("$awaits", "x-awaits' fields — local Decisions, answers, and nested rollups."),
    (
        "$languages",
        "The languages this page colors, in a code block's class or an x-language attribute.",
    ),
    ("$tones", "The tones this page's layer paints, on any x-tone attribute."),
    (
        "$series",
        "The categorical steps a chart's series are painted in, and how many there are.",
    ),
    (
        "$reactions",
        (
            "The one-press reactions a reader can put on a passage, an element, a "
            "message, or the page — each `token`'s glyph, meaning, and effect."
        ),
    ),
    (
        "$idioms",
        "Theme idioms — shapes the theme styles directly; no registry entry, no JS.",
    ),
)
CATALOG_INTERNAL_FACTS = {"$events", "$layer"}


def page_guidance(page_dir: Path, registry: dict | None = None) -> dict[str, str]:
    """Compose package-wide, contract, and widget guidance by audience."""
    parts = {}
    directory = page_dir / GUIDANCE_DIR
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.setdefault(path.stem, []).append(text)
    registry = registry if registry is not None else require_registry(page_dir)
    for contract, declaration in sorted(
        registry.get("$data", {}).get("contracts", {}).items()
    ):
        for audience, text in sorted(declaration.get("guidance", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Data contract `{contract}`\n\n{text.strip()}"
            )
    for tag, entry in sorted(registry.items()):
        if not tag.startswith("lf-"):
            continue
        for audience, text in sorted(entry.get("x-guidance", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Widget `<{tag}>`\n\n{text.strip()}"
            )
    return {
        audience: "\n\n".join(sections).rstrip() + "\n"
        for audience, sections in sorted(parts.items())
    }


def cmd_guidance(page_dir: Path, audience: str | None) -> None:
    require_registry(page_dir)
    guides = page_guidance(page_dir)
    if audience is None:
        if guides:
            print("\n".join(guides))
        return
    if text := guides.get(audience):
        print(text, end="" if text.endswith("\n") else "\n")
        return
    available = ", ".join(guides) or "none"
    sys.exit(f"guidance audience {audience!r} is not available; available: {available}")


def cmd_catalog(page_dir: Path) -> None:
    reg = require_registry(page_dir)
    print(CATALOG_PREAMBLE)
    print(
        json.dumps(
            {k: v for k, v in reg.items() if not k.startswith("$")},
            indent=2,
            ensure_ascii=False,
        )
    )
    printed = set()
    for key, heading in CATALOG_FACTS:
        if fact := reg.get(key):
            print(f"\n# {heading}\n")
            print(json.dumps(fact, indent=2, ensure_ascii=False))
            printed.add(key)
    for key in sorted(set(reg) - printed - CATALOG_INTERNAL_FACTS):
        if key.startswith("$"):
            print(f"\n# {key}, declared by this layer.\n")
            print(json.dumps(reg[key], indent=2, ensure_ascii=False))
    guidance = page_guidance(page_dir, reg).get("author")
    if guidance and (text := guidance.strip()):
        print("\n# Guidance for authors\n")
        print(text)
