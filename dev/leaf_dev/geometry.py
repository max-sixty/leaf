"""The geometry faults a tab shows, read so that two versions of a state can be
compared: the reading `leaf-dev stills` takes of each arm beside its stills, and
reports where the head adds a fault the base doesn't have.

Two readings, each a list of findings:

- edges: a box Leaf draws that nearly meets its frame's edge, crosses it or is cut by
  it, and a round mark closer to the edge than `--lf-clear` (browser/AGENTS.md, "A box
  inside a frame either meets its edge or stands clear of it"; `geometry.js`);
- rings, in Chromium: a focus ring a clip cuts or a box covers (`rings.py`).

A finding is keyed by its kind, side, box and frame (or the rule that drew the ring),
never by a length, so the same fault reads alike on both arms and a change that moves
a fault without mending it adds nothing. A page has faults it has always had; the
comparison keeps a change's report to the faults it causes.

Rejected: a third reading, of two of Leaf's boxes crossing each other. Leaf's boxes
cross on purpose far more often than by mistake, as a picture's removal mark stands on
its corner, Copy over its code block and a chart's marks over its gridlines, and the
crossings that were defects were either a single pixel deep, as a seam is, or on a
page no state shows.
"""

import json
from pathlib import Path

from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.browser import CHECK_API
from leaf_dev.rings import rings_drawn

READING = (Path(__file__).parent / "geometry.js").read_text()
GEOMETRY = (
    f"async (options) => {{ const reading = {READING}\n"
    f"return reading(options, await {CHECK_API}); }}"
)
# The `lf-` classes an author may write, which mark the author's boxes rather than
# Leaf's: the registry's class idioms (browser/AGENTS.md, "Leaf's elements wear only
# Leaf's names").
IDIOMS = sorted(
    {
        key.split(".", 1)[1].split(" ")[0].split("[")[0]
        for key in json.loads((ROOT / "browser" / "registry.json").read_text())
        if ".lf-" in key
    }
)


def read(page, *, running: bool = True) -> list[dict]:
    """The edge and ring findings of the settled tab `page`. A tab that takes no script
    with arguments, as the iOS simulator's Safari doesn't, has none. Rings are read in
    Chromium alone, whose protocol names the rule that drew each, and only where the
    runtime is `running`: a state holding its entry module shows the authored layout
    (`State.activated`), which draws no ring."""
    if not isinstance(page, Page):
        return []
    findings = page.evaluate(GEOMETRY, {"idioms": IDIOMS})
    chromium = page.context.browser.browser_type.name == "chromium"
    for seen in rings_drawn(page) if running and chromium else ():
        faults = seen["cuts"] + seen["covers"]
        if faults:
            findings.append(
                {
                    "kind": "ring",
                    "side": "",
                    "box": seen["who"],
                    "frame": seen["rule"],
                    "said": "; ".join(faults),
                }
            )
    return findings


def key(finding: dict) -> tuple[str, str, str, str]:
    """A finding as it reads on either arm: kind, side, box, and frame."""
    return finding["kind"], finding["side"], finding["box"], finding["frame"]


def added(base: list[dict], head: list[dict]) -> list[dict]:
    """The findings of `head` that `base` has none of, once each."""
    seen = {key(finding) for finding in base}
    fresh = {}
    for finding in head:
        if key(finding) not in seen:
            fresh.setdefault(key(finding), finding)
    return list(fresh.values())


def said(finding: dict) -> str:
    """A finding as one line of a report."""
    if finding["kind"] == "ring":
        return f"ring on {finding['box']}: {finding['said']}"
    return (
        f"{finding['kind']} {finding['side']} {finding['gap']}px: {finding['box']}"
        f" in {finding['frame']}"
    )
