"""A Leaf page of captures, as the commands that show Leaf's drawing case by case write
one: `leaf-dev placement pins` and `placement cards`, and `leaf-dev eval report`'s
before and after.

A capture is cut to the box around what a case is about (`frame`), the same box
on every arm so a pair lines up, and marks it (`marked`) before it reaches the page. The page
holds it under its content name (`media`), as `leaf page media` would, so a page built
from one run and copied into another keeps its images. Two arms' captures of one case
are an `lf-shot` pair, and one arm's an image (`shot`). The page around them is a
reading column (`page`), or another Layout, which a command's own styles widen where
its tiles need it.
"""

from collections.abc import Iterable
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw

from leaf.media import media_name


def media(directory: Path, data: bytes, suffix: str = ".png") -> str:
    """Write `data` into a page's media `directory` under its content name, and return
    the path the page reads it by."""
    name = media_name(data, suffix)
    (directory / name).write_bytes(data)
    return f"/media/{name}"


def shot(id: str, alt: str, before: str | None, after: str) -> str:
    """One case's captures: an `lf-shot` pair of the base's and this tree's, or this
    tree's alone as a linked image where no base ran."""
    alt = escape(alt, quote=True)
    if before is None:
        return f'<a href="{after}"><img src="{after}" alt="{alt}"></a>'
    return (
        f'<lf-shot id="{id}" before="{before}" after="{after}" alt="{alt}"></lf-shot>'
    )


def frame(
    boxes: Iterable[dict], pad: float, width: float, height: float
) -> tuple[float, float, float, float]:
    """The `(left, top, right, bottom)` box around `boxes`, each given as `{left, top,
    right, bottom}`, grown by `pad` on every side and kept inside a capture `width`
    by `height`."""
    boxes = list(boxes)
    return (
        max(0, min(box["left"] for box in boxes) - pad),
        max(0, min(box["top"] for box in boxes) - pad),
        min(width, max(box["right"] for box in boxes) + pad),
        min(height, max(box["bottom"] for box in boxes) + pad),
    )


def edges(rect: dict) -> dict:
    """A browser's `{x, y, width, height}` rectangle as `{left, top, right, bottom}`."""
    return {
        "left": rect["x"],
        "top": rect["y"],
        "right": rect["x"] + rect["width"],
        "bottom": rect["y"] + rect["height"],
    }


def marked(
    capture: Path | Image.Image,
    color: tuple[int, int, int],
    *,
    outlined: Iterable[dict],
    filled: Iterable[dict] = (),
    scale: int = 1,
) -> Image.Image:
    """The capture with each box of `outlined` ringed and each of `filled` tinted in
    `color`, boxes given in CSS pixels as `{left, top, right, bottom}` at `scale`
    device pixels to a CSS pixel."""
    image = (
        capture if isinstance(capture, Image.Image) else Image.open(capture)
    ).convert("RGBA")
    layer = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(layer)
    for box in filled:
        draw.rectangle(
            [
                scale * (box["left"] - 1),
                scale * box["top"],
                scale * (box["right"] + 1),
                scale * box["bottom"],
            ],
            fill=(*color, 70),
        )
    for box in outlined:
        draw.rounded_rectangle(
            [
                scale * (box["left"] - 4),
                scale * (box["top"] - 3),
                scale * (box["right"] + 4),
                scale * (box["bottom"] + 3),
            ],
            radius=4 * scale,
            outline=(*color, 255),
            width=3 * scale,
        )
    return Image.alpha_composite(image, layer).convert("RGB")


def page(
    title: str,
    description: str,
    body: str,
    *,
    head: str = "",
    layout: str = "layout-column",
) -> str:
    """A Leaf page titled `title` whose `main`, in `layout`'s classes, holds `body`,
    with `head`, such as a command's styles, in its head."""
    return f"""<!doctype html>
<html lang="en">
<head>
<title>{escape(title)}</title>
<meta name="description" content="{escape(description, quote=True)}">
{head}
</head>
<body>
<main class="{layout}">
{body}
</main>
</body>
</html>
"""
