"""Every focus ring a page draws, and what cuts or covers it: the reading the ring tests
and `leaf-dev stills` share, so a ring a change newly cuts reads the same in both.

`rings_drawn` asks the page which boxes paint the ring (`focus_rings.js`,
`ringCandidates`), asks Chromium's DevTools protocol which rule drew each, and then
measures each ring against the clips around it and the boxes in front of it
(`ringsDrawn`), confirming covers against a screenshot. It reads Chromium only, as
the protocol does. `ring_faults` puts a reading's faults in a failure's words.
"""

import io
import re
from pathlib import Path
from typing import cast
from weakref import WeakKeyDictionary

import tinycss2
from PIL import Image

from leaf.source.render_checks import rendered
from leaf_dev.browser import CHECK_API, page_function, screenshot

HERE = Path(__file__).parent
CONTROL_NAME = (HERE / "control_name.js").read_text()
FOCUS_RINGS = (HERE / "focus_rings.js").read_text()
# What to call a control in a failure message (`control_name.js`).
NAMED = page_function(CONTROL_NAME, "named")


def ring_script(function: str) -> str:
    """A page function calling `focus_rings.js`'s `function`, as `page_function` makes
    one, for a reading a test makes of focus beside the rings: `newStop`, `seenStop`."""
    return page_function(FOCUS_RINGS, function, helpers=CONTROL_NAME)


RING_CANDIDATES = ring_script("ringCandidates")
# `ringsDrawn` measures against the page's own check API, as its runtime has it.
RINGS_DRAWN = f"async (rectangles) => ({ring_script('ringsDrawn')})(rectangles, await {CHECK_API})"


# Which focus ring a box wears is which rule drew it, and the browser says so: the
# DevTools protocol's matched styles for a node already resolve nesting, `@scope`,
# shadow trees, adopted sheets and pseudo-elements, the cases a test re-matching the
# layer's selectors got wrong one after another. So a rule draws a ring and names none,
# and a test asks the browser which rule drew the one it sees. Chromium only.
#
# A ring is identified by its winning rule's selector as matched: the one selector of
# the rule's list that matched the box, under the nesting and `@scope` it sits in.
# That survives what leaves the ring alone (another declaration, a reordered sheet,
# another selector added to the list, the rule moving file) and changes when what
# selects the ring does. Tests assert on the part of it that makes the rule the
# control's own, such as `.lf-grip`, rather than on the whole text.
# Read the browser's serialized selector list, not each selector's source range:
# formatting is not part of a ring's identity. Only top-level commas divide the
# list; commas and whitespace within functions or strings keep their meaning.
#
# Only a declaration that draws with the ring's own token is a ring rule: `--lf-focus-ring`
# for an outline, `--lf-focus-shadow` for the band cast as a shadow, or the mark a box
# draws round itself (`--lf-band-ink`, surfaces.css), which is the ring wherever it is
# whole: the location ring, the proxy ring and a comment's focus state. Its brackets,
# a gesture's mark, are never read as a ring (`bracketed`, focus_rings.js). A contour
# written out as `2px solid var(--lf-accent)`, such as an element mark's pointer feedback,
# paints the same pixels and is not one.
RING_CARRIERS = {
    "outline": ("outline", "outline-style"),
    "box-shadow": ("box-shadow",),
}
RING_TOKEN = {
    "outline": re.compile(r"--lf-(?:focus-ring|band-ink)(?![\w-])"),
    "box-shadow": re.compile(r"--lf-focus-shadow(?![\w-])"),
}
_ring_sessions = WeakKeyDictionary()


def _ring_session(page):
    cdp = _ring_sessions.get(page)
    if cdp is None:
        cdp = _ring_sessions[page] = page.context.new_cdp_session(page)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
    return cdp


def _matched_selector(match):
    rule = match["rule"]
    if rule["origin"] == "inline":
        return "style attribute"
    selectors = [[]]
    for token in tinycss2.parse_component_value_list(rule["selectorList"]["text"]):
        if token.type == "literal" and token.value == ",":
            selectors.append([])
        else:
            selectors[-1].append(token)
    said = ", ".join(
        tinycss2.serialize(selectors[i]).strip() for i in match["matchingSelectors"]
    )
    context = [f"@scope {scope['text']}" for scope in rule.get("scopes", [])]
    context += reversed(rule.get("nestingSelectors", []))
    return " { ".join([*context, said])


def _winning_declaration(matches, carrier):
    """The match and value of the declaration that wins `carrier` among `matches`,
    which the protocol lists in cascade order. Important beats normal; within each,
    the later wins. Important declarations in different cascade layers would reverse
    that order, which no ring rule in the layer meets."""
    won = {}
    for match in matches:
        style = match["rule"]["style"]
        # The longhands the protocol expands a shorthand into carry no source text, so
        # the declarations are the properties that do. A sheet whose source the protocol
        # has not read lists none with text, and names its shorthands only among
        # `shorthandEntries`: Chromium on CI's Linux runner listed the chrome sheet's
        # target hint rule that way.
        props = [prop for prop in style["cssProperties"] if "text" in prop] or [
            *style["cssProperties"],
            *style.get("shorthandEntries", []),
        ]
        for prop in props:
            if (
                prop["name"] in RING_CARRIERS[carrier]
                and not prop.get("disabled")
                and prop.get("parsedOk", True)
            ):
                won[bool(prop.get("important"))] = (match, prop["value"])
    return won.get(True) or won.get(False)


def _read_ring_boxes(page, wants, *, geometry=False):
    """For each box the last probe stashed (`stash`, focus_rings.js), the selector of
    the rule that drew its ring with the ring's token, or "" where none did.

    `wants` holds one `(pseudo, carrier)` pair per box: the pseudo-element the ring is
    on, if any, and whether it is an outline or a box shadow. With `geometry`, also
    return pseudo border rectangles from the browser's layout, aligned with `wants`."""
    if not wants:
        return []
    cdp = _ring_session(page)
    cdp.send("DOM.getDocument", {"depth": 0})
    group = {"objectGroup": "lf-rings"}
    boxes = cdp.send(
        "Runtime.evaluate", {"expression": "globalThis.__lfRingBoxes", **group}
    )["result"]["objectId"]
    cdp.send("Runtime.evaluate", {"expression": "delete globalThis.__lfRingBoxes"})
    listed = cdp.send(
        "Runtime.getProperties", {"objectId": boxes, "ownProperties": True}
    )["result"]
    ids = {
        int(p["name"]): p["value"]["objectId"] for p in listed if p["name"].isdigit()
    }
    rules = []
    rectangles = []
    for index, (pseudo, carrier) in enumerate(wants):
        node = cdp.send("DOM.requestNode", {"objectId": ids[index]})["nodeId"]
        styles = cdp.send("CSS.getMatchedStylesForNode", {"nodeId": node})
        if pseudo:
            matches = next(
                entry["matches"]
                for entry in styles["pseudoElements"]
                if entry["pseudoType"] == pseudo
            )
            if geometry:
                described = cdp.send("DOM.describeNode", {"nodeId": node})["node"]
                pseudo_node = next(
                    entry
                    for entry in described["pseudoElements"]
                    if entry["pseudoType"] == pseudo
                )
                border = cdp.send(
                    "DOM.getBoxModel",
                    {"backendNodeId": pseudo_node["backendNodeId"]},
                )["model"]["border"]
                rectangles.append(
                    {
                        "left": min(border[::2]),
                        "right": max(border[::2]),
                        "top": min(border[1::2]),
                        "bottom": max(border[1::2]),
                    }
                )
        else:
            matches = list(styles["matchedCSSRules"])
            if inline := styles.get("inlineStyle"):
                matches.append({"rule": {"origin": "inline", "style": inline}})
        if geometry and not pseudo:
            rectangles.append(None)
        won = _winning_declaration(matches, carrier)
        drew = won and RING_TOKEN[carrier].search(won[1])
        rules.append(_matched_selector(won[0]) if drew else "")
    cdp.send("Runtime.releaseObjectGroup", group)
    return (rules, rectangles) if geometry else rules


def ring_rules(page, wants):
    """The winning ring selector for each stashed box and `(pseudo, carrier)` pair."""
    return _read_ring_boxes(page, wants)


def ring_rule(target, pseudo=None, carrier="outline"):
    """The selector of the rule drawing the ring on `target`, a locator, as
    `ring_rules` reads it."""
    target.evaluate("(box) => { globalThis.__lfRingBoxes = [box]; }")
    return ring_rules(target.page, [(pseudo, carrier)])[0]


def rings_drawn(page):
    """Every focus ring the page is drawing, each with the rule that drew it (`rule`,
    as `ring_rules` reads it) and what is wrong with it.

    A non-focused element mark painting the band with no ring rule behind it is the
    pointer's feedback contour rather than a ring, so it is left out.

    It reads once the runtime has rendered what the input so far asked for. The probe
    and the browser's matched styles are two reads, and a carrier the runtime replaces
    between them, such as the projected focus mark after a focus move, has no styles
    left to read."""
    rendered(page)
    candidates = page.evaluate(RING_CANDIDATES)
    if not candidates:
        return []
    rules, rectangles = _read_ring_boxes(
        page,
        [(seen["pseudo"], seen["carrier"]) for seen in candidates],
        geometry=True,
    )
    answers = page.evaluate(RINGS_DRAWN, rectangles)
    _read_ring_pixels(page, answers)
    drawn = []
    for seen, rule in zip(answers, rules, strict=True):
        if seen.pop("mark") and not seen["focused"] and not rule:
            continue
        seen["rule"] = rule
        drawn.append(seen)
    return drawn


# The share of a run's samples the ring's colour must cover. A run hit testing found
# clear but painted over, or never painted, reads near nought.
RUN_DRAWN = 0.9
# The fewest unpainted samples, 4px apart, that count: a neighbour's edge blending into
# a short run's end sample is one.
RUN_MISSED = 3
# How far a sample's channels may stray from the ring's, summed: a band on a fractional
# edge blends a little of the ground into its middle pixel, and ground or text that
# covers it differs by far more.
RUN_INK = 90


def _read_ring_pixels(page, answers):
    """Add to each ring's `covers` the runs its colour is missing from in a screenshot,
    at the samples `ringsDrawn` (focus_rings.js) found nothing in front of that takes
    hits. Confirm candidate covers at their sampled pixel too: an outline is not a
    hit surface, so hit testing alone can mistake a box beneath it for a cover.
    Drop the samples, ink and rectangle from each answer.

    The screenshot is taken a round trip after the reading, so a caller reads a page at
    rest (`rendered`); one still repainting can read a ring where it no longer is. It is
    the whole window's, as every capture is (`browser.screenshot`)."""
    if any(seen["runs"] or seen["coverPoints"] for seen in answers):
        image = Image.open(io.BytesIO(screenshot(page))).convert("RGB")
        scale = image.width / page.viewport_size["width"]
    for seen in answers:
        runs, ink, ring = seen.pop("runs"), seen.pop("ink"), seen.pop("ringAt")

        def painted_at(point, ink=ink):
            x, y = point
            # An RGB image's pixel, which Pillow's mode-dependent return type can't say.
            pixel = cast(
                tuple[int, int, int],
                image.getpixel(
                    (
                        min(max(int(x * scale), 0), image.width - 1),
                        min(max(int(y * scale), 0), image.height - 1),
                    ),
                ),
            )
            return sum(abs(a - b) for a, b in zip(pixel, ink, strict=True)) < RUN_INK

        visible = {
            c["index"] for c in seen.pop("coverPoints") if painted_at(c["point"])
        }
        seen["covers"] = [c for i, c in enumerate(seen["covers"]) if i not in visible]
        for run in runs:
            painted = [painted_at(point) for point in run["points"]]
            share = sum(painted) / len(painted)
            if share < RUN_DRAWN and painted.count(False) >= RUN_MISSED:
                seen["covers"].append(
                    f"its {run['side']} edge shows the ring at {share:.0%} of its "
                    f"{len(painted)} samples where nothing in front takes hits: paint "
                    f"hit testing can't see is over it, or it isn't painted (ring {ring})"
                )


def current_location_ring(page):
    """The ring on the control at the current keyboard location, or None if it wears none."""
    return next((seen for seen in rings_drawn(page) if seen["focused"]), None)


def ring_faults(drawn, where):
    """The complaints about a page's rings, in the failure's own words.

    Takes a reading rather than a page: a caller that also wants what the rings
    credit would otherwise sweep the page twice and describe two instants of it.
    """
    return [
        f"{where}, the ring on {seen['who']} is not all there: "
        + "; ".join(seen["cuts"] + seen["covers"])
        for seen in drawn
        if seen["cuts"] or seen["covers"]
    ]
