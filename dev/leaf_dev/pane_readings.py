"""Measure a served workspace's regions for a live judge, before it explores.

A judge exploring a workspace by screenshots sees each pane's first screen, and
can't tell from one how much of a pane its content fills, what a pane holds past
its own scroll, or whether the keyboard reaches it. This module reads those
directly at each viewport the judge is given: every region Leaf scrolls inside a
`layout-workspace` shown on arrival (the reading-region inventory,
`reading-regions.js`), with its box, whether it scrolls itself and how many of its
own screens it holds, the share of its visible box farther than 16px from any text
or drawn element, at its top and at its end, and the Tab press that first puts
focus in it. A page with no workspace shown on arrival, such as one whose
workspace is a later part, reads as `workspace: false` and adds nothing, and so
does a screen an author built from its own grid CSS, whose scroll boxes are no
reading regions. `judge_pages` reads them only when every page it judges is a Leaf
page, so a Leaf/HTML pair judge never sees measurements of one side alone.

The render check's `readViewChecks` (`render-checks/view.js`) also reads a
full-height workspace's overflowing regions, but only the panes the page wrote and
the Layout's body. A widget's own regions, such as a queue's list and its selected
ticket, are outside it, and they are most of what a workspace's reader scrolls.

The readings are evidence beside the judge's own observation, never a verdict:
an empty share counts gaps a design may want, and a pane Tab never reaches may
have another key route or need none. `judge_pages` writes them to the judgment's
evidence and its metadata, so a run's pane readings tabulate from `results.json`.
"""

import json

from leaf_dev.browser import headless_shell, load, tab

# Each region's reading on arrival. The empty share counts the 16px cells of its
# visible box with no text or drawn element within a cell of them, so the gaps
# between lines and words of a block read as filled and margins and blank tracks
# as empty.
READINGS = """async () => {
  const { readingRegions, readingRegionFor, shownRegionBounds } = await import(
    "/runtime/check-api.js"
  );
  const { regionScrollBehavior } = await import("/runtime/widget-api.js");
  const workspaces = [...document.querySelectorAll(".layout-workspace")].filter(
    (box) => box.checkVisibility(),
  );
  if (!workspaces.length) return { workspace: false, regions: [] };
  const CELL = 16;
  // Every node the reader sees as content: text, and boxes drawn as a whole.
  const DRAWN =
    "img, svg, canvas, video, iframe, input, select, textarea, button, hr, progress, meter";
  const contentRects = (root) => {
    const rects = [];
    const walk = (node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.data.trim()) return;
        const range = document.createRange();
        range.selectNodeContents(node);
        rects.push(...range.getClientRects());
        return;
      }
      if (node.nodeType === Node.ELEMENT_NODE) {
        if (!node.checkVisibility()) return;
        // A drawing's own parts are inside its box already.
        if (node.matches(DRAWN)) return void rects.push(node.getBoundingClientRect());
        if (node.shadowRoot) walk(node.shadowRoot);
      }
      for (const child of node.childNodes) walk(child);
    };
    walk(root);
    return rects;
  };
  const emptyShare = (body, box) => {
    const left = Math.max(box.left, 0);
    const top = Math.max(box.top, 0);
    const right = Math.min(box.right, innerWidth);
    const bottom = Math.min(box.bottom, innerHeight);
    const columns = Math.floor((right - left) / CELL);
    const rows = Math.floor((bottom - top) / CELL);
    if (columns <= 0 || rows <= 0) return null;
    const covered = new Uint8Array(columns * rows);
    for (const r of contentRects(body)) {
      if (r.width === 0 || r.height === 0) continue;
      const c0 = Math.max(0, Math.floor((r.left - CELL - left) / CELL));
      const c1 = Math.min(columns - 1, Math.floor((r.right + CELL - left) / CELL));
      const r0 = Math.max(0, Math.floor((r.top - CELL - top) / CELL));
      const r1 = Math.min(rows - 1, Math.floor((r.bottom + CELL - top) / CELL));
      for (let row = r0; row <= r1; row++)
        for (let column = c0; column <= c1; column++) covered[row * columns + column] = 1;
    }
    const filled = covered.reduce((sum, cell) => sum + cell, 0);
    return Math.round((1 - filled / covered.length) * 100) / 100;
  };
  const label = (host) =>
    host.getAttribute("label") ||
    host.getAttribute("aria-label") ||
    host.querySelector("h1, h2, h3, h4, summary")?.textContent.trim().slice(0, 60) ||
    host.id ||
    host.localName;
  const regions = readingRegions()
    .filter((region) => workspaces.some((box) => box.contains(region.host)))
    .flatMap((region) => {
      const bounds = shownRegionBounds(region);
      if (!bounds || bounds.right - bounds.left < 1 || bounds.bottom - bounds.top < 1)
        return [];
      const { body } = region;
      const bounded = regionScrollBehavior(region) === "bounded";
      const reading = {
        id: region.id,
        label: label(region.host),
        inside: readingRegionFor(region.host.parentNode)?.id ?? null,
        box: [
          bounds.left,
          bounds.top,
          bounds.right - bounds.left,
          bounds.bottom - bounds.top,
        ].map(Math.round),
        scroll: bounded ? "own" : "carried",
        screens: bounded
          ? Math.round((body.scrollHeight / body.clientHeight) * 10) / 10
          : null,
        empty_at_top: emptyShare(body, bounds),
      };
      if (bounded && body.scrollHeight > body.clientHeight + 1) {
        const before = body.scrollTop;
        body.scrollTop = body.scrollHeight;
        reading.empty_at_end = emptyShare(body, shownRegionBounds(region));
        body.scrollTop = before;
      }
      return [reading];
    });
  return {
    workspace: true,
    window: [innerWidth, innerHeight],
    page_scrolls: document.scrollingElement.scrollHeight > innerHeight + 1,
    regions,
  };
}"""
# Enough presses to cross the chrome and every pane of a dense workspace; a walk
# that returns to its first stop has seen every stop.
TABS = 150
FOCUSED = """async () => {
  const { readingRegionFor } = await import("/runtime/check-api.js");
  let el = document.activeElement;
  while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
  if (!el || el === document.body) return { region: null, wrapped: false };
  const stops = (globalThis.__lfTabStops ??= []);
  const wrapped = stops.length > 1 && stops[0] === el;
  stops.push(el);
  return { region: readingRegionFor(el)?.id ?? null, wrapped };
}"""


def tab_reach(view, regions: list[dict]) -> None:
    """Press Tab from the top of the page, and give each region the press that
    first put focus inside it, or none: a region holds its own descendants'
    stops, so reaching a nested region reaches the regions around it."""
    within = {region["id"]: region["inside"] for region in regions}
    reached: dict[str, int] = {}
    for press in range(1, TABS + 1):
        view.keyboard.press("Tab")
        focused = view.evaluate(FOCUSED)
        if focused["wrapped"]:
            break
        region = focused["region"]
        while region is not None:
            reached.setdefault(region, press)
            region = within.get(region)
    for region in regions:
        region["first_tab"] = reached.get(region["id"])


def read(url: str, widths: dict) -> dict:
    """Each viewport's readings of the page at `url`, at `widths` as either judge
    names them: a size, or a size under `viewport`."""
    readings = {}
    with headless_shell() as browser:
        for name, size in widths.items():
            viewport = tuple(size["viewport"] if isinstance(size, dict) else size)
            with tab(browser, viewport=viewport, touch=name == "phone") as view:
                load(view, url)
                reading = view.evaluate(READINGS)
                if reading["workspace"]:
                    tab_reach(view, reading["regions"])
                readings[name] = reading
    return readings


def judge_note(readings: dict) -> str:
    """The readings as the judge's instructions carry them, or nothing for pages
    without a workspace."""
    if not any(
        reading["workspace"] for page in readings.values() for reading in page.values()
    ):
        return ""
    return f"""
Measured workspace regions: a script's reading of each page on arrival at each
viewport, before your exploration. For each region Leaf scrolls inside the
workspace: its box [left, top, width, height] in CSS pixels; `scroll` "own" when it
scrolls itself, with `screens` its content's height in its own visible heights, or
"carried" when an enclosing box scrolls it; `inside`, the region holding it;
`empty_at_top` and `empty_at_end`, the share of its visible box farther than 16px
from any text or drawn element, scrolled to its top and to its end; and
`first_tab`, the Tab press from the page's top that first put focus inside it, or
null when {TABS} presses never did. These are measurements to weigh with what you
observe, not verdicts: an empty share counts gaps a design may want, and a pane
Tab never reaches may have another key route, or need none when it neither
scrolls nor holds a control.
{json.dumps(readings, indent=1)}
"""
