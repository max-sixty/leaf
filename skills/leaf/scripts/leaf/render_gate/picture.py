"""The picture of a drawing comment, as the user saw it.

A drawing's ink replays scaled to its element's current box, so once the page reflows
the agent cannot tell from the page in front of it what the user's strokes crossed.
The record holds what reproduces the moment: the comment's immutable `revision`, and
the `viewport` and `scheme` of the window it was drawn in. `leaf page picture` serves
that revision with the log as it stood once the comment was appended, opens it in the
host's browser at that viewport and scheme, and lets the runtime paint the comment's
ink as it paints every posted drawing. It scrolls the drawing's element into view,
inside any pane holding it, since the user's scroll positions are not recorded. The PNG is cropped to the ink and `CONTEXT`
pixels of the page around it, inside the window, at one image pixel per CSS pixel, so
its coordinates are the drawing's own scale.

Two inputs are not the user's. `data/` sources are not versioned, so a widget drawn
from data shows the data as it stands now; and the host's fonts can differ from those
on the user's device, which moves words under the ink.

The file goes to the state home's `pictures/` directory for the page, named for the
comment, since a file in the page directory would count as activity on the page.
"""

import sys
from pathlib import Path

from leaf.event_log import read_events
from leaf.render_checks import PageNotReady, rendered, wait_until_ready
from leaf.revision_artifact import read_revision

from .command import in_browser
from .preview import preview_server
from .scheme import served
from .screens import page_files

# How much of the page around the ink the picture keeps, in CSS pixels on each side.
CONTEXT = 120

# An anchored drawing's ink stands against its element, which may sit in a pane that
# scrolls on its own and opens scrolled elsewhere: the element is scrolled into view
# through every scroller holding it, and then the window centers the ink, which can
# reach past the element. A page drawing stands against the document and needs only the
# window. The element is the one whose inline anchor name the ink's `position-anchor`
# names (`anchor-names.js`).
CENTER = """(el, anchored) => {
  if (anchored) {
    const name = el.style.positionAnchor;
    const holder = [...document.querySelectorAll("[style]")].find((node) =>
      node.style.anchorName.split(",").some((part) => part.trim() === name));
    holder.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
  }
  const box = el.getBoundingClientRect();
  const { clientWidth, clientHeight } = document.documentElement;
  scrollBy({
    left: box.left + box.width / 2 - clientWidth / 2,
    top: box.top + box.height / 2 - clientHeight / 2,
    behavior: "instant",
  });
}"""

CLIP = """(el, context) => {
  const box = el.getBoundingClientRect();
  const { clientWidth, clientHeight } = document.documentElement;
  const x = Math.max(0, Math.floor(box.left - context));
  const y = Math.max(0, Math.floor(box.top - context));
  const right = Math.min(clientWidth, Math.ceil(box.right + context));
  const bottom = Math.min(clientHeight, Math.ceil(box.bottom + context));
  return right > x && bottom > y
    ? { x, y, width: right - x, height: bottom - y }
    : null;
}"""


def cmd_picture(page_dir: Path, message: str) -> int:
    """Write the picture of drawing comment `message` and print its path."""
    comment = next(
        (event for event in read_events(page_dir) if event["id"] == message), None
    )
    if comment is None:
        sys.exit(f"{page_dir} has no message {message}")
    if "drawing" not in comment:
        sys.exit(f"message {message} carries no drawing")
    out = page_files("pictures", page_dir) / f"{message}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    revision = comment["revision"]
    with preview_server(
        page_dir,
        read_revision(page_dir, revision).document,
        revision,
        through_seq=comment["seq"],
    ) as url:
        ran = in_browser(
            "picture", lambda browser: _picture(browser, url, comment, out)
        )
    if ran is None:
        return 1
    refused, _ = ran
    if refused:
        sys.exit(f"message {message}: {refused}")
    print(out)
    return 0


def _picture(browser, url: str, comment: dict, out: Path) -> str | None:
    """Draw `comment` at `url` into `out`, or say why its ink cannot be pictured."""
    from playwright.sync_api import Error as PlaywrightError

    drawing = comment["drawing"]
    width, height = drawing["viewport"]
    page = browser.new_page(
        viewport={"width": width, "height": height},
        color_scheme=drawing["scheme"],
        reduced_motion="reduce",
    )
    try:
        page.goto(url)
        wait_until_ready(page, served(page, url, "/api/state").json())
        rendered(page)
        ink = page.locator(f'.lf-drawing-posted[data-thread="{comment["id"]}"]')
        if not ink.count():
            return _no_ink(page, comment)
        ink.evaluate(CENTER, "anchor" in comment)
        rendered(page)
        clip = ink.evaluate(CLIP, CONTEXT)
        if clip is None:
            return "its ink lies outside the window it was drawn in"
        page.screenshot(path=out, clip=clip)
        return None
    except PageNotReady as error:
        return str(error)
    except PlaywrightError as error:
        # A wait that timed out names what never arrived.
        return str(error).strip().splitlines()[0]
    finally:
        page.close()


def _no_ink(page, comment: dict) -> str:
    """Why the runtime painted no ink for `comment`."""
    if page.evaluate("document.body.dataset.annotations") == "page":
        return "this page presents its own annotations, which draw no Leaf ink"
    # A page drawing has no element to lose, so its ink always stands.
    section = comment["anchor"]["section"]
    window = "x".join(map(str, comment["drawing"]["viewport"]))
    return (
        f"its element #{section} does not resolve on r{comment['revision']} at {window}"
    )
