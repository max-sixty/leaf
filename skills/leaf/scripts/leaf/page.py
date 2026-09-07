"""Vendored page guidance."""

import sys
from pathlib import Path

from .registry.storage import require_registry
from .schema import GUIDANCE_DIR


def page_guidance(page_dir: Path) -> dict[str, str]:
    """Compose package-wide, contract, and widget guidance by audience."""
    parts = {}
    directory = page_dir / GUIDANCE_DIR
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.setdefault(path.stem, []).append(text)
    registry = require_registry(page_dir)
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
    guides = page_guidance(page_dir)
    if audience is None:
        # A layer with no audiences is a real answer, and silence reads as a
        # command that did nothing. Say which it was.
        print("\n".join(guides) if guides else "no guidance audiences")
        return
    if text := guides.get(audience):
        print(text, end="" if text.endswith("\n") else "\n")
        return
    available = ", ".join(guides) or "none"
    sys.exit(f"guidance audience {audience!r} is not available; available: {available}")
