"""Shared layout browser-integration cases and readings."""

import fcntl
import hashlib
import io
import math
import struct
import threading
import zlib
from types import SimpleNamespace

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from conftest import interact
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    ASKS_PAGE,
)
from render_harness import (
    CARRIED_PAGE,
    LONG_PAGE,
    TOKEN,
    leaf_page,
    record_claim,
)

CUSTOM_WIDGET_PAGE = leaf_page(
    "custom widget",
    """
<h1 id="title">Project vocabulary</h1>
<lf-callout id="custom-note">
  <strong>Heads up</strong> This widget came from the project layer.
</lf-callout>
""",
)

RESIZE_LOOP_EVENT = """dispatchEvent(new ErrorEvent('error', {
  message: 'ResizeObserver loop completed with undelivered notifications.'
}));"""


def resize_notice_after_last_probe(page):
    """Schedule the notice for the rendering turn after the gate's last probe."""
    evaluate = page.evaluate

    def with_notice(expression, *args, **kwargs):
        result = evaluate(expression, *args, **kwargs)
        if expression == interact.RELATIVE_REPLAYS:
            evaluate("() => requestAnimationFrame(() => {" + RESIZE_LOOP_EVENT + "})")
        return result

    page.evaluate = with_notice


# What a returning reader's browser puts back before the page runs, declared by the
# runtime that puts it back (leaf.js, ARRANGEMENTS). Read from the page rather than
# listed here: which surfaces remember anything is the runtime's to say, and a list on
# this side would stop at the ones it was taught.
ARRANGEMENTS = "() => import('/leaf.js').then((leaf) => leaf.ARRANGEMENTS)"

# One arrangement and no other, written the way a reader's own browser holds it. Both
# stores are cleared first, so each arrival is the arrangement it names rather than that
# one plus whatever the last reload left. Nothing is caught: a browser that will not
# store is a browser this reading cannot make, and swallowing that would turn every
# arrival into a first visit and every arrival finding into a pass.
ARRANGE = """(a) => {
  localStorage.clear();
  sessionStorage.clear();
  (a.store === "session" ? sessionStorage : localStorage).setItem(a.key, a.value);
}"""


def arrival_findings(browser, url):
    """Whether a page comes up at all in each arrangement a reader can return to.

    The suite's, not `render_version`'s, and the line between them is whose fault a
    finding is. Everything the gate reads is something the page's author wrote and
    can change; a restore is the layer's, identical under every version, so an agent
    running the gate at handover would be paying for a verdict on code it did not
    write and cannot fix.

    What it reads: a fresh context holds nothing, so every other reading in the suite
    is of a first visit — the comment panel shut, no tray standing, design mode off —
    and each of those is something a reader turns on once and gets back on every load
    afterwards. That left the restores as the one road onto a page with nothing
    watching it, and a tray someone had left standing came up as a ReferenceError
    instead of a page: it was put up by code running while the runtime was still
    evaluating, which could reach almost nothing. It reached the reader, who reported
    it.

    One page, reloaded into each arrangement, which is what a returning reader does:
    the store is written on the origin the page is already on and read while the next
    load evaluates. What comes back is the upgrade stamp and the console and no more,
    because coming up is the whole question here. Boxes are not measured again: every
    shipped example was measured in each of these arrangements and none of them moved
    a box that a first visit didn't.
    """

    page = browser.new_page(viewport=interact.RENDER_VIEWPORT, color_scheme="light")
    errors = []
    notices = []

    def console_message(message):
        if message.type != "error":
            return
        target = notices if interact.resize_observer_error(message.text) else errors
        target.append(message.text)

    page.on("console", console_message)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    page.add_init_script(interact.WINDOW_ERRORS)
    found = []
    try:
        # A first visit, to be arranged from and to read the arrangements off. Reported
        # rather than raised when it doesn't arrive: this is the reading that says what
        # happens on a load, so a load it could not make is its own answer, and a page
        # that never came up has nothing to be arranged into.
        try:
            # `load`, where the gate's scheme passes wait for network quiet: those read
            # the served documents and want a page that has stopped asking for things,
            # while everything here is either the stamp below — which the page raises
            # for itself, and which is the stronger fact — or a console the handlers
            # above are already attached to. Network quiet costs 3.5x what the load
            # event does over the five navigations here, measured on
            # design-decision.html, and buys this nothing.
            page.goto(url, wait_until="load")
            page.wait_for_function(interact.UPGRADED)
        except PlaywrightTimeout:
            return [
                "[arrivals] the page never came up unarranged, so nothing could be "
                "arranged — "
                + ("; ".join([*errors, *notices]) or "and no console error says why")
            ]
        for arrangement in page.evaluate(ARRANGEMENTS):
            page.evaluate(ARRANGE, arrangement)
            # A console the last arrangement dirtied is not this one's news.
            errors.clear()
            notices.clear()
            try:
                page.reload(wait_until="load")
                page.wait_for_function(interact.UPGRADED)
            except PlaywrightTimeout:
                found.append(
                    f"[{arrangement['name']}] the page never finished coming up — "
                    + (
                        "; ".join([*errors, *notices])
                        or "and no console error says why"
                    )
                )
                continue
            # A ResizeObserver notice is the gate's to adjudicate over two attempts on
            # the same document; one seen here says nothing on its own.
            found += [f"[{arrangement['name']}] console: {e}" for e in errors]
    finally:
        page.close()
    return found


def motions(events):
    """The settling motions the browser reported, keyed by the motion, not by its target.

    Settling and not living, which is `interact.MOVING`'s distinction and is here for
    its reason: the banner's dot pulses for as long as the tab is open, and something
    that never ends never arrived anywhere. An unbounded iteration count cannot cross
    JSON, so the browser omits it, and that omission is the reading.

    A target is a backend node id, and the same tray over two loads is two of them,
    so an id cannot say whether the second load moved what the first one did. The kind
    of motion, the property or keyframes it plays and how long it runs are one string
    whichever load painted it, and that is the key. The id rides along beside it for
    the failure message alone: a person reading one wants the element, and that is the
    only place a name is worth a round trip.
    """
    found = {}
    for event in events:
        animation = event["animation"]
        source = animation.get("source") or {}
        if source.get("iterations") is None:
            continue
        key = (
            f"{animation['type']} {animation.get('name') or ''}"
            f" {source.get('duration')}ms"
        )
        found.setdefault(key, source.get("backendNodeId"))
    return found


def moved_at(cdp, node):
    """Where a reported motion was, named the way the rest of the suite names elements."""
    if node is None:
        return "an element the browser did not identify"
    # The node map is the inspector's own and is populated by asking for the document;
    # a describeNode on a fresh document without it is refused outright.
    cdp.send("DOM.getDocument", {"depth": 1})
    described = cdp.send("DOM.describeNode", {"backendNodeId": node})["node"]
    pairs = described.get("attributes", [])
    attributes = dict(zip(pairs[::2], pairs[1::2]))
    name = described.get("localName") or described.get("nodeName")
    if attributes.get("id"):
        return f"{name}#{attributes['id']}"
    if attributes.get("class"):
        return f"{name}.{attributes['class'].replace(' ', '.')}"
    return name


# The host case of the same failure: the declarations are on the element that stages the
# tree, so both passes find it — it is in the document — and write into a light DOM the
# shadow root hides. The markup then holds every word the entry promised and the reader
# gets none of them, which is why the gate reads the rendered page rather than the markup.
SHADOW_HOST_PAGE = CUSTOM_WIDGET_PAGE.replace(
    '<lf-callout id="custom-note">',
    '<lf-callout id="custom-note" label="Escalated" urgent>',
)
# Every cell one unbreakable token, so no amount of wrapping gets this table
# inside the column and the third of the theme's three cases is the one on trial.
WIDE_TABLE_PAGE = leaf_page(
    "wide",
    """
<h1 id="t">Sessions</h1>
<p id="p">One row, and more of it than the measure holds.</p>
<table id="sessions">
<thead><tr>{heads}</tr></thead>
<tbody><tr>{cells}</tr></tbody>
</table>
""",
).format(
    heads="".join(f"<th>heading_number_{i}</th>" for i in range(8)),
    cells="".join(f"<td>value_number_{i}</td>" for i in range(8)),
)

# A block wider than the column and narrower than the window: 70% of 1200px is
# 840px against a 720px column, so it stands 120px out in the margin with
# the body not scrolling by a pixel. In vw rather than px because the static lint
# counts pixels and would have caught it before a browser ever saw it.
SPILLING_PAGE = LONG_PAGE.replace(
    "</main>", "<div id='too-wide' style='width: 70vw'>Wide.</div>\n</main>"
)
# Two wrappers that generate no box, differing only in whether anything inside them does.
# `#veiled` is the shape the vocabulary shipped while a suggestion was display: contents,
# and any page can still write in a line — it is the control: the gate must not report
# it, or it reports every page that styles a wrapper away. `#ghost` is the same wrapper
# with its words loose inside it, where there is nothing at all for a mark to hang on.
UNMARKABLE_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='veiled' style='display: contents'>"
    "<p id='seen'>Words in a box of their own.</p></div>"
    "<div id='ghost' style='display: contents'>Words in no box at all.</div>\n</main>",
)
# The shapes a float takes at the column's edge. The first three are laid out from the
# same left content edge, so the only difference is how far each one's own negative
# margin carries it: far enough and the whole box is out in the margin, which is what a
# sidenote is; not far enough and the box straddles the edge, which is a spill. The
# fourth says the same side in the logical spelling, and the fifth is the run of prose a
# resident holds — every one of which inherits the box its parent put out there.
FLOATING_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='in-the-margin' style='float: left; clear: left; width: 180px;"
    " margin-left: -204px'>Beside <code id='inner-word'>--flag</code>.</div>"
    "<div id='half-out' style='float: left; clear: left; width: 180px;"
    " margin-left: -90px'>Across.</div>"
    "<div id='logical' style='float: inline-start; clear: left; width: 180px;"
    " margin-left: -204px'>Beside.</div>"
    "<div id='off-window' style='float: left; clear: left; width: 180px;"
    " margin-left: -900px'>Gone.</div>\n</main>",
)
SIDENOTE_IN_A_WIDGET = LONG_PAGE.replace(
    "</main>",
    """<lf-options id="where" choose>
  <lf-option id="opt-a"><strong>First</strong>
    <aside class="sidenote" id="boxed-note">Measured over a quarter.</aside>
    <p>An option carrying a note written inside it.</p>
  </lf-option>
  <lf-option id="opt-b"><strong>Second</strong> The other one.</lf-option>
</lf-options>
</main>""",
)


# A note written level with a change, which is the one arrangement that puts two
# residents of the right margin on the same line.
NOTE_BESIDE_A_CHANGE = LONG_PAGE.replace(
    "</main>",
    """<aside class="sidenote" id="level-note">Measured over a quarter, and the number
moved twice inside it.</aside>
<lf-suggestion id="sug-level">
  <lf-old><p id="old-level">About three thousand writes a second at peak.</p></lf-old>
  <lf-new><p>3,400 writes a second at p99, over the last quarter.</p></lf-new>
</lf-suggestion>
</main>""",
)
# Boxes over their container, differing only in what holds them and how. The first two
# are the rule and neither alone proves it: a page that named both would refuse every
# wide table the theme puts in a scroller, and one that named neither is the gate before
# it could see a clipped box at all. The third says which box holds this one — it is
# written inside a clipping box and placed against the column, so the markup and the
# containing blocks answer differently and only one of them paints. The fourth is that
# question the other way up: containment makes a static box the containing block of what
# it then cuts, while the overflow every gate before this one read computes `visible`.
# The fifth is a box that says it cuts. The sixth is where the cut falls: a border hides
# what is drawn under it, and a border box says nothing about that. The last pair is why
# the report is suppressed per container rather than per subtree — nested, and lost out
# of two different boxes by two very different amounts.
OVER_ITS_CONTAINER = LONG_PAGE.replace(
    "</main>",
    "<div id='clipping' style='width: 300px; overflow: hidden'>"
    "<div id='eaten' style='width: 420px'>Nobody sees the end of this.</div></div>"
    "<div id='scrolling' style='width: 300px; overflow-x: auto'>"
    "<div id='reachable' style='width: 420px'>This one scrolls into view.</div></div>"
    "<div id='holding' style='width: 300px; height: 40px; overflow: hidden'>"
    "<div id='hung' style='position: absolute; width: 420px'>Placed, so this one "
    "holds it not at all.</div></div>"
    "<div id='contained' style='width: 300px; height: 40px; contain: paint'>"
    "<div id='cut-by-paint' style='position: absolute; width: 420px'>Containment cuts "
    "this one while overflow says visible.</div></div>"
    "<div id='telling' style='width: 300px; overflow: hidden; "
    "text-overflow: ellipsis; white-space: nowrap'>"
    "<span id='told'>A line long enough to run past the end of the box it is written "
    "inside, which says so with an ellipsis.</span></div>"
    "<div id='bordered' style='width: 300px; border-left: 20px solid #888; "
    "overflow: hidden'>"
    "<div id='under-border' style='margin-left: -20px; width: 300px'>The first 20px of "
    "this are behind the border.</div></div>"
    "<svg id='drawn' width='300' height='60' xmlns='http://www.w3.org/2000/svg'>"
    "<foreignObject width='120' height='40'>"
    "<div xmlns='http://www.w3.org/1999/xhtml' style='width: 128px'>The drawing's own "
    "accounting.</div></foreignObject></svg>"
    "<div id='barely' style='width: 300px; overflow: hidden'>"
    "<div id='over-by-three' style='width: 303px'>Three pixels over this one."
    "<div id='inner-box' style='position: relative; width: 200px; height: 40px; "
    "overflow: hidden'>"
    "<div id='over-by-far' style='position: absolute; left: 0; width: 600px'>Four "
    "hundred over that one.</div></div></div></div>"
    "\n</main>",
)
SCROLLED_CONTAINER = LONG_PAGE.replace(
    "</main>",
    "<div id='rolled' style='width: 300px; overflow-x: auto'>"
    "<div id='riding' style='width: 900px'>Where the content of a scrolled box "
    "starts.</div></div>\n</main>",
)
# The two edges the reader draws, and what a reading of either has to know: a page that
# offers the region, what puts it up, the region's own selector, which side of the window
# it is held to, and the numbers the runtime holds it to. Two records rather than two
# tests, because the whole claim of `drawnEdge` is that the two are one piece of furniture
# reflected — a reading written for the panel alone would go on passing on the day the
# tray's edge stopped working, and the tray's edge exists precisely because the panel's
# did not have to be written a second time.
#
# `html` is a call rather than the markup, because the page the trays need is declared
# with the other tray readings a long way below here, and a parametrize list is read at
# import. `squeeze` is the window that has no room for what the reader chose and the width
# the region stands at there — per edge, because each is capped against its own half of a
# window and covers the page at a different one.
EDGES = [
    SimpleNamespace(
        name="comments",
        html=lambda: LONG_PAGE,
        comments=1,
        stand=lambda page: page.locator(".lf-comments").click(),
        region=".lf-panel",
        side="right",
        store="lf-panel-width",
        wide=420,
        squeeze=(1000, 500),
    ),
    SimpleNamespace(
        name="trays",
        html=lambda: ASKS_PAGE,
        comments=0,
        stand=lambda page: page.keyboard.press("a"),
        region=".lf-asks-panel",
        side="left",
        store="lf-tray-width",
        wide=300,
        squeeze=(800, 400),
    ),
]
EDGE_IDS = [edge.name for edge in EDGES]


def edge_settled(page, edge):
    """Wait for the region to stand and for the page to finish making room for it.

    Two animations, on two elements, and `panel_settled`'s reasoning covers both: the
    strip the page yields is a transition on body, and the region's arrival is its own
    slide. A geometry read between them is a read of a box still under a transform.
    """
    expect(page.locator(edge.region)).to_be_visible()
    page.wait_for_function(
        "(region) => document.body.getAnimations().length === 0"
        " && document.querySelector(region).getAnimations().length === 0",
        arg=edge.region,
    )


def geometry(page, edge):
    """What the edge reads back as, and what the page has left beside it.

    The two numbers are one fact asked from both sides: the strip is body's margin and
    the region's own box, and the whole point of the width being the reader's is that
    nothing may hold a copy of it their gesture doesn't reach.
    """
    return page.evaluate(
        """([region, side, store]) => {
            const box = document.querySelector(region).getBoundingClientRect();
            const body = document.body.getBoundingClientRect();
            return {
                width: Math.round(box.width),
                edge: Math.round(side === 'right' ? box.left : box.right),
                page: Math.round(side === 'right' ? body.right : body.left),
                chosen: localStorage.getItem(store),
            };
        }""",
        [edge.region, edge.side, edge.store],
    )


def draw_edge(page, edge, by):
    """Draw the region's edge `by` pixels wider, as a hand on it would.

    Whole pixels, per `select`'s reason (tests/CLAUDE.md): a press on a fractional point
    is a press the browser is free to round somewhere else. In steps, because one jump
    from press to release is a drag with no `pointermove` between its ends, and the move
    is the whole of what this gesture is made of. Wider is away from the side the region
    is held to, which is the reading the runtime makes of the same gesture.
    """
    box = page.locator(f"{edge.region} .lf-edge").bounding_box()
    x, y = math.floor(box["x"] + box["width"] / 2), math.floor(box["y"] + 200)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + (by if edge.side == "left" else -by), y, steps=8)
    page.mouse.up()
    # The slide stands down for the length of a drag and comes back at its end, so what
    # is waited on is the page holding still rather than a transition finishing — which
    # `panel_settled` reads the same way, and which is empty here on both counts.
    page.wait_for_function("() => document.body.getAnimations().length === 0")


# The room, sampled every frame for as long as a slide lasts. A property is asked of the
# root rather than of any element that spends it, because it is the fact and an exhibit is
# one reader of it.
ROOM_EVERY_FRAME = """(frames) => {
  window.__room = [];
  // The first sample is taken now rather than on the first frame, so the width before the
  // press is always in the trace: a frame is free to land after the keypress that follows
  // this call, and a trace that opens after the strip is taken has one value in it and
  // nothing to compare.
  const tick = () => {
    window.__room.push(
      getComputedStyle(document.documentElement).getPropertyValue('--lf-room'));
    if (window.__room.length < frames) requestAnimationFrame(tick);
  };
  tick();
}"""
# Enough code for the roles to differ from each other and from the block: a comment, a
# keyword, a string, a name, a number.
COLORED_CODE_PAGE = LONG_PAGE.replace(
    "</main>",
    """<pre id="snippet"><code class="language-python"># the ceiling doubles per approval
def ceiling(limit, approvals):
    return "over" if approvals > 12 else limit
</code></pre>
</main>""",
)

# Both bugs go back as CSS, which is the shape the regression takes for real: the
# attribute lands either way, and it is the stylesheet answering it that stops working.
# A rule at document level with the theme's own specificity, so the later one wins.
UNANSWERED_CODE_PAGE = COLORED_CODE_PAGE.replace(
    "</head>", "<style>[data-lf-syn] { color: inherit; }</style>\n</head>"
)
# What --syn-comment carried until this gate was written: 3.3:1 on --pre-bg, and the
# reading a user reported as the highlighting being gone.
FAINT_CODE_PAGE = COLORED_CODE_PAGE.replace(
    "</head>", '<style>[data-lf-syn="cm"] { color: #8b8577; }</style>\n</head>'
)

# A role that reads on the block and not on the tint one of its lines wears. The clean
# line comes first on purpose: a gate that stopped at a role's first span would take the
# 7.9:1 reading and never reach the 1.6:1 one two lines down, and a walkthrough's hi band
# is the surface where a code line is most often set on something other than --pre-bg.
TINTED_LINE_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --hi-tint: #6f6a60; }</style>\n</head>"
).replace(
    "</main>",
    """<lf-code id="tinted" language="python" hi="2"><pre>
first = "on the block's own colour"
second = "on the band"
</pre></lf-code>
</main>""",
)

# The same reading, in a shadow tree. lf-diff renders the page's words into one, so its
# spans are in no document.querySelectorAll — and the page carries no other code, so a
# probe that stopped at the boundary would sweep this and find nothing to say. The token
# is what goes back rather than a rule: a custom property inherits through the boundary
# where a selector does not, which is both why this reaches the spans and why a project's
# own palette reaches them too, gate or no gate.
SHADOWED_DIFF = """<lf-diff id="shadowed"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,3 +1,4 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals > 12 else limit
</pre></lf-diff>
</main>"""
SHADOW_CODE_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --syn-comment: #8b8577; }</style>\n</head>"
).replace("</main>", SHADOWED_DIFF)

# The other half of the boundary: what is painted behind a shadowed span is on the
# elements above the host, and a span at the top of a root has no parentElement to climb
# to. Today's theme hides that — the box a diff renders into carries an opaque --card, so
# a composite that stopped at the boundary would land on the same colour — which is a
# coincidence of the palette and not a reason to read the light tree. Flattening that one
# surface is all it takes to part them: the paper under it is what the reader has behind
# the comment, and against the white a stalled climb falls back to, a dark page's ink
# reads as either a pass or a failure that isn't on the screen.
FLAT_SHADOW_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --card: transparent; }</style>\n</head>"
).replace("</main>", SHADOWED_DIFF)
# Two sets, because pointing at a control and pressing it are different questions.
#
# What must hold still is everything a user aims at, however the widget that built
# one made it: the runtime's real buttons and selects, the spans `offer` builds, a tab, a
# pick mark, a reference. Naming the ways a control is constructed rather than the widgets
# that construct them is what lets a twelfth widget's join this sweep without editing it.
NEIGHBOUR = (
    "[data-lf-offer], [role=tab], [role=button], .lf-btn, .lf-pick, "
    "button, select, summary, a[href]"
)
# What this sweep presses is narrower, and both exclusions are about the press landing
# rather than about the control. A <select> opens a native popup the page cannot see and
# the next click closes instead of pressing — which is how this sweep first passed while
# pressing nothing at all, the shape of vacuous pass CLAUDE.md is about. A link is a
# user's control and its press is a scroll, so it belongs to the set above and has
# nothing here to disturb.
PRESS = "[data-lf-offer], [role=tab], [role=button], .lf-btn, .lf-pick, button, summary"

# The controls a press is aimed *past*: the ones sharing its parent, standing on the same
# line, and on screen at both ends of the gesture. Held in a JS array rather than looked
# up again afterwards, because identity has to survive a press that adds or removes a
# sibling; measured with offset*, which is the layout box before any transform, so a card
# still lifted under the pointer reads as the nothing it is.
#
# On screen is the load-bearing half. A control inside a fold the press opens was nowhere
# the user could aim, and one the press puts away — a suggestion's ✗ Reject, once ✓
# Accept has settled the pair — is not a control that moved. Both are the press doing what
# it was pressed for. `[hidden]` is asked separately because hidden="until-found", which is
# what a folded region wears, measures zero and still reports itself visible.
ON_SCREEN = "(n) => n.checkVisibility() && !n.closest('[hidden]') && n.offsetWidth > 0"
# What to call a control in a failure message. Its words are in it because they are
# usually the whole of what distinguishes one button in a row from the next — and out of
# the key it is looked up by, since a control that rewrites them (a count gaining a
# digit) is the same control saying something new.
NAMED = """(n) => n.tagName.toLowerCase()
    + (typeof n.className === 'string' && n.className.trim()
       ? '.' + n.className.trim().split(/\\s+/).join('.') : '')
    + ' ' + JSON.stringify((n.textContent || '').trim().slice(0, 24))"""
NEIGHBOURHOOD = f"""(el, sel) => {{
  const band = el.getBoundingClientRect();
  const sameLine = (n) => {{
    const r = n.getBoundingClientRect();
    return Math.min(r.bottom, band.bottom) - Math.max(r.top, band.top) > 1;
  }};
  window.__lfOnScreen = {ON_SCREEN};
  window.__lfNeighbours = [...el.parentElement.children]
      .filter((n) => n !== el && !n.contains(el))
      .flatMap((n) => (n.matches(sel) ? [n] : [...n.querySelectorAll(sel)]))
      .filter((n) => window.__lfOnScreen(n) && sameLine(n));
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# The same capture, of the banner rather than of one control's line: every control the
# chrome is showing, held by identity so the news can rewrite their words without
# changing who they are.
BANNER_WATCH = f"""(sel) => {{
  window.__lfOnScreen = {ON_SCREEN};
  window.__lfNeighbours = [...document.querySelector(".lf-banner").querySelectorAll(sel)]
      .filter(window.__lfOnScreen);
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# One reading, named once, so the rendered-frame wait and the assertion cannot measure
# differently.
DEFINE_BOXES = """() => { window.__lfBoxes = () => window.__lfNeighbours.map(
    (n) => window.__lfOnScreen(n)
      ? [n.offsetLeft, n.offsetTop, n.offsetWidth, n.offsetHeight] : null); }"""
# Nested animation-frame callbacks have one complete rendering turn between them, so
# this states rendered progress rather than elapsed time between two frame polls.
RENDERED = "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"


def page_at_rest(page):
    """Render the known edge, finish finite motion, then render its ending."""
    page.evaluate(RENDERED)
    page.wait_for_function(f"() => ({interact.MOVING})().length === 0")
    page.evaluate(RENDERED)


def displaced(before, boxes):
    """Which of the watched controls are somewhere else, in the failure's own words.

    A control that has gone off screen reads None and is left out: it was put away
    rather than moved, which is a thing both sweeps below deliberately allow."""
    return [
        f"{name} moved by "
        f"{[round(a - b, 1) for a, b in zip(now, was)]} (left, top, width, height)"
        for name, was, now in zip(before["names"], before["boxes"], boxes)
        if now is not None and was != now
    ]


def aim_targets(page_dir):
    """Everything an ⌥-press can land on that something is waiting to answer.

    Every control however its widget built one, and every element of the vocabulary,
    whose handlers sit on the widget rather than on a control — an option is picked by
    clicking its prose. The vocabulary is read from the page's own registry rather than
    listed, so the twelfth widget is swept by existing. Prose has no handler at all, so
    one press into it proves what fifty would."""
    tags = ", ".join(
        t for t in interact.load_registry(page_dir) if not t.startswith("$")
    )
    return f":is({PRESS}, {tags}):not(.lf-chrome *)"


# Where in a target to aim, asked of the rendered page rather than assumed: near its
# leading corner, since the middle of a container is usually one of its children, and only
# where the point is really the target's — an element under the banner or clipped to
# nothing is somewhere no aim can land, which is a skip rather than a failure.
AIM_POINT = """(el) => {
  const r = el.getBoundingClientRect();
  const spots = [[r.left + Math.min(8, r.width / 2), r.top + Math.min(8, r.height / 2)],
                 [r.left + r.width / 2, r.top + r.height / 2]];
  for (const [x, y] of spots) {
    const at = document.elementFromPoint(x, y);
    if (at && (at === el || el.contains(at))) return [x, y];
  }
  return null;
}"""
# The promise itself, read where the runtime states it: the aim's box in the chrome's
# layer carries the aimed item's id (data-for, refreshAim's one write of it). The
# composer's own mark then stands on that same item once the press is made, so the box's
# answer before the press and the draft's after it agreeing is the promise being kept.
AIMED = """() => document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null"""
# The item the draft stands on, which is not always the element wearing the outline: a
# mark hangs on the boxes its item shows through, and a display: contents wrapper shows
# through its slots. Reading the raw id said the promise was broken for every suggestion
# on every example — while the reading that had passed all along was the vacuous one, the
# outline sitting on a wrapper that draws nothing.
DRAFT_MARK = """() =>
  document.querySelector(".lf-mark-el.lf-pending")?.closest("[id]")?.id ?? null"""
# What the arm says about the next press, in the one property that is on screen before
# the box is read. Asked of body, where the aim declares it and from where it is
# inherited by everything on the page that doesn't state a cursor of its own.
AIM_CURSOR = """() => getComputedStyle(document.body).cursor"""
# Where focus ended up, which is the effect a press has that leaves no mark in the markup:
# `offer` gives every press it builds a tabindex, so a press the page received lands on
# the control, where the aim's own leaves focus to the composer it opened.
FOCUS_IN_PAGE = """() => {
  const at = document.activeElement;
  return !!at && at !== document.body && !at.closest(".lf-chrome");
}"""
# The page as against the layer over it, which is where an effect nobody asked for shows.
# Read as markup because a widget acting states itself there however it renders — an
# attribute picked, a panel hidden, an editor opened — and a sweep that knew which to look
# for would be a sweep that stops at the widgets it was taught.
#
# Except for an emptied class attribute, which is the outline coming off an element that
# had no class of its own: DOMTokenList leaves `class=""` behind, and that is a residue of
# the runtime's paint rather than anything the page says.
# Generated text is blanked before the compare, because a widget may render a clock
# and a clock is not a press: lf-agent's elapsed line re-renders on every poll, so the
# minute turning during a long sweep read as a press that had reached a widget. What the
# check is for survives untouched — a stray pick writes `chosen` on the option and a
# stray tab switch moves the panels' attributes, both of them authored rather than
# generated, and structure is compared either way.
PAGE_MARKUP = """() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => {
        const c = n.cloneNode(true);
        for (const g of c.querySelectorAll("[data-lf-gen]")) g.textContent = "";
        if (c.dataset && c.dataset.lfGen !== undefined) c.textContent = "";
        return c.outerHTML;
    })
    .join("").replaceAll(' class=""', "")"""
# Every legend box stands on its item: same corner, one pixel out, for every item wholly
# on screen. Items partly off it are clipped to the scroller (shownRect) and are not
# compared, and items off it have no box shown at all. An item with no box of its own —
# one a page styles display: contents — reads as what its contents paint, mirroring
# shownRect's fallback: its host rect is 0×0 at the origin, which would otherwise count
# as "wholly on screen" and fail every off-screen one for its rightly hidden box.
LEGEND_TRUE = """() => [...document.querySelectorAll('.lf-legend-box')].every(b => {
  const it = document.getElementById(b.dataset.for);
  let r = it.getBoundingClientRect();
  if (!r.width && !r.height) {
    const contents = document.createRange();
    contents.selectNodeContents(it);
    r = contents.getBoundingClientRect();
  }
  if (r.top < 0 || r.bottom > innerHeight) return true;
  if (b.style.display === 'none') return false;
  const bb = b.getBoundingClientRect();
  return Math.abs(bb.left + 1 - r.left) < 1.5 && Math.abs(bb.top + 1 - r.top) < 1.5
    && Math.abs(bb.width - 2 - r.width) < 1.5 && Math.abs(bb.height - 2 - r.height) < 1.5;
})"""
CORNER_PAGE = leaf_page(
    "corner",
    """
<h1 id="t">Corner</h1>
<section id="wrap"><p id="inner">The section's first block starts at its corner.</p></section>
""",
)
AIM_PAINT_PAGE = leaf_page(
    "aim paint",
    """
<h1 id="t">Aim paint</h1>
<lf-options id="cards" choose>
  <lf-option id="card-plain"><strong>Plain</strong> The first card's argument.</lf-option>
  <lf-option id="card-star" recommended><strong>Starred</strong> A border already the accent.</lf-option>
</lf-options>
<lf-options id="rows" choose>
  <lf-option id="row-ship">Ship it as is</lf-option>
  <lf-option id="row-hold">Hold for the backfill</lf-option>
</lf-options>
""",
)
MARK_PAD = 6  # CSS px of ground kept around the element in the clip
MARK_NEAR = 12  # per channel, wide enough for the stroke's antialiased shoulder only


def token_colour(page, name):
    """What a theme token resolves to on this page, as the browser serializes it.

    The mark's own reading is no reading at all: taken off the marked element's
    `outlineColor`, every measurement below is against whatever that rule happens to
    say, so pointing `.lf-mark-el` at the accent leaves the gate green. The token is
    the thing the rule is supposed to name, so the colour comes from there and the
    rule is checked against it."""
    return page.evaluate(
        """(name) => {
        const probe = document.createElement('span');
        probe.style.color = `var(${name})`;
        document.body.append(probe);
        const seen = getComputedStyle(probe).color;
        probe.remove();
        return seen;
    }""",
        name,
    )


def mark_edges(page, ident, ink):
    """How wide the mark is painted on each side of an element, in device pixels.

    Geometry can't answer this and neither can the computed style: the mark is an
    outline, so every rect is identical whether the stroke survived or something
    painted over it, and `outlineWidth` is what was asked for rather than what
    landed. Pixels are the only reading — the same recourse the draft's focus ring
    needed, one screenshot up from a byte comparison because the four sides have to
    be compared with each other rather than with an earlier frame.

    Each scan starts at the element's own edge and stops at the first pixel that
    isn't the mark's colour, because the first draft counted the first ink-coloured
    run *anywhere* along the scanline: an accent status dot sitting in the clip's own
    padding reported 26 device pixels of "mark" on a side the mark never reached, and
    a marked code block would have counted its identifiers. What follows from that is
    the tolerance too — ±12 per channel admits the stroke's antialiased shoulder and
    nothing else, where ±40 reached both --accent and --syn-name.

    Three samples a side, returned as a set rather than a majority. A majority is a
    vote for the mark being intact when part of the edge has been painted over, which
    is the failure this exists to catch; a disagreement is the finding, so the caller
    sees {1, 0} rather than 1.

    The clip is squared off to whole CSS pixels first, and each side is then asked for
    its own ground, because a leaf page's boxes do not land on whole pixels — 17px of
    body serif at a line-height of 1.6 is 27.2px a line, so a widget's height is a stack
    of fractions. A clip is asked for in CSS pixels and answered in device ones, and
    Chrome truncates the rect to whole CSS pixels before it scales: asked for the board
    column 101.578px tall on this page, it dropped that 0.578 and took all of it off the
    bottom, which put the element's own edge two device pixels from where MARK_PAD said
    it was — outside the window below — and a stroke painted whole on all four sides was
    read as half of one along the bottom. Squaring the clip is what makes that loss
    nothing to model rather than something to allow for.

    The edge is then snapped in CSS space and scaled, in that order, because that is the
    order Blink paints in: the painted edge lands at `floor(ground + 0.5) * scale`, and it
    was multiplying first that made `round(gap * scale)` disagree with it — by a pixel the
    window below covers, until a scale of 4 makes it two. The window is kept for a device
    pixel of engine drift either side."""
    from PIL import Image  # a dev dependency already, for the demo recorder

    box = page.locator(f"#{ident}").bounding_box()
    clip = {"x": math.floor(box["x"] - MARK_PAD), "y": math.floor(box["y"] - MARK_PAD)}
    clip["width"] = math.ceil(box["x"] + box["width"] + MARK_PAD) - clip["x"]
    clip["height"] = math.ceil(box["y"] + box["height"] + MARK_PAD) - clip["y"]
    fits = page.evaluate(
        """([x, y, w, h]) => x >= 0 && y >= 0
             && x + w <= innerWidth && y + h <= innerHeight""",
        [clip["x"], clip["y"], clip["width"], clip["height"]],
    )
    assert fits, (
        f"#{ident} is not wholly on screen with the {MARK_PAD}px around it this squares "
        f"off, and a screenshot clip is the viewport's: scroll it in and size the "
        f"viewport to it first, or the scans measure a truncated image"
    )
    image = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    width, height = image.size
    scale = page.evaluate("() => devicePixelRatio")
    # The image is the squared clip and nothing else — asserted rather than assumed,
    # because the trailing scans count in from the far edge, so a single row of slack
    # there reads as a stroke a pixel thin and names the element rather than the shot.
    assert (width, height) == (clip["width"] * scale, clip["height"] * scale), (
        f"the clip asked for {clip['width']}x{clip['height']} CSS px at dpr {scale} and "
        f"came back {width}x{height} device px: every scan below counts from an edge "
        f"this arithmetic no longer locates"
    )
    # Each side's own ground, since squaring the clip is not symmetric: MARK_PAD plus
    # whatever that side's rounding added. Snapped in CSS space and then scaled, per the
    # docstring — and a trailing side counts in from the far end of a clip whose width is
    # a whole number, which flips the half, so the two directions round opposite ways.
    lead = {"top": box["y"] - clip["y"], "left": box["x"] - clip["x"]}
    trail = {
        "bottom": clip["y"] + clip["height"] - box["y"] - box["height"],
        "right": clip["x"] + clip["width"] - box["x"] - box["width"],
    }
    edge = {s: round(math.floor(g + 0.5) * scale) for s, g in lead.items()}
    edge |= {s: round(math.ceil(g - 0.5) * scale) for s, g in trail.items()}

    def stroke(scan, at):
        """Mark-coloured pixels contiguous with the element's edge, and no others."""
        inked = [
            all(abs(a - b) <= MARK_NEAR for a, b in zip(pixel, ink)) for pixel in scan
        ]
        start = next((i for i in range(at - 1, at + 2) if inked[i]), None)
        if start is None:
            return 0
        seen = 0
        while start + seen < len(inked) and inked[start + seen]:
            seen += 1
        return seen

    def quarters(size):
        return (size // 4, size // 2, 3 * size // 4)

    columns = [[image.getpixel((x, y)) for y in range(height)] for x in quarters(width)]
    rows = [[image.getpixel((x, y)) for x in range(width)] for y in quarters(height)]
    return {
        "top": {stroke(c, edge["top"]) for c in columns},
        "bottom": {stroke(c[::-1], edge["bottom"]) for c in columns},
        "left": {stroke(r, edge["left"]) for r in rows},
        "right": {stroke(r[::-1], edge["right"]) for r in rows},
    }


@pytest.fixture
def live_leaf(tmp_path, monkeypatch):
    """Stands up a live leaf for the banner's panel to find: published, served by
    a real handler, and written down under the state home the way `server run` writes
    it — which is the whole of how one page learns another exists. Each claims to be
    working, freshly, so its row has a judged state to show. A factory rather than one
    fixture, because a tray is a list and a walk down it needs somewhere to walk to."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    servers = []
    held = []

    def go(name, title):
        d = interact.state_home() / "pages" / name
        result = CliRunner().invoke(interact.cli, ["page", "init", str(d)])
        assert result.exit_code == 0, result.output
        (d / "versions" / "v1.html").write_text(
            LONG_PAGE.replace("<title>long</title>", f"<title>{title}</title>")
        )
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
        )
        interact.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "running the suite",
                "ts": interact.now_iso(),
            },
        )
        # A live leaf has a session behind it, and what the tray's hover says about a
        # page is the work that session is doing it for — so the fixture's pages come
        # out of somewhere nameable rather than out of nowhere.
        record_claim(
            d,
            id=f"s-{name}",
            cwd=str(tmp_path / f"{name}-work"),
        )
        httpd = interact.LeafHTTPServer(
            ("127.0.0.1", 0), interact.handler_for(d, TOKEN)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        port = httpd.server_address[1]
        # Desired address and a held, contentless lease are the two facts a real
        # server exposes to neighbouring pages.
        interact.write_json(
            d / "service.json",
            {
                "host": "127.0.0.1",
                "bind": "127.0.0.1",
                "port": port,
                "enabled": True,
                "lifetime": "standing",
            },
        )
        lease = open(d / "server.lock", "a+b")  # noqa: SIM115 - held, see above
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.append(lease)
        return f"http://127.0.0.1:{port}", d

    yield go
    for httpd in servers:
        httpd.shutdown()
    for lease in held:
        lease.close()


@pytest.fixture
def other_leaf(live_leaf):
    return live_leaf("other", "The other leaf")


# The page's scroll after it has stopped moving. A native Space is a smooth scroll, so
# reading straight after the press reads a frame of the glide and calls it the answer —
# which is the whole of what CLAUDE.md's wait norm is about.
SCROLL_SETTLE_MS = 50
SCROLL_STILL = """(hold) => {
  const at = document.body.scrollTop;
  if (at !== window.__lfScrollAt) {
    window.__lfScrollAt = at;
    window.__lfScrollSince = performance.now();
    return false;
  }
  return performance.now() - window.__lfScrollSince > hold;
}"""
# Twelve things waiting, which is more than any shipped example asks and the point: the
# room a list reserves at its foot is invisible until the list is longer than the tray.
MANY_ASKS_PAGE = leaf_page(
    "many asks",
    """
<h1>Many asks</h1>
<p>A tray long enough to scroll.</p>
<lf-tasks id="plan">
"""
    + "\n".join(
        f'<lf-task id="t-{i}" status="review" owner="wren">'
        f"<strong>Waiting on you, item {i}</strong>"
        f"<p>Something to decide about item {i}.</p></lf-task>"
        for i in range(12)
    )
    + """
</lf-tasks>
""",
)
# A run with nothing to break on, in the three places a page puts one: a metric's headline,
# where the box is a fixed 138px and the value is whatever the number turned out to be;
# ordinary prose, which is where a page about code keeps its paths; and a tree, whose module
# writes the name and its badges with no whitespace between them at all.
UNBREAKABLE_PAGE = leaf_page(
    "unbreakable",
    """
<h1 id="h">Nothing to break on</h1>
<lf-metrics id="numbers">
  <lf-metric id="m-token" value="a_very_long_unbroken_identifier">Bucket key</lf-metric>
</lf-metrics>
<p id="p-token">The one it fails on is
gateway_middleware_authentication_token_bucket_refill_strategy.py, every time.</p>
<lf-tree id="tree"><pre>
gateway/
  middleware/
    authentication/
      token_bucket_refill_strategy.py    +6 -2
</pre></lf-tree>
""",
)
# One line past any phone column, so the box a diff renders in has to scroll and the
# rule is the one on trial rather than the fit.
WIDE_DIFF_PAGE = leaf_page(
    "wide diff",
    """
<h1 id="t">A diff wider than the column</h1>
<lf-diff id="wide-diff"><pre>
diff --git a/client/offline/merge.ts b/client/offline/merge.ts
--- a/client/offline/merge.ts
+++ b/client/offline/merge.ts
@@ -18,2 +18,2 @@ export function merge(base: Doc, mine: Edit[], theirs: Edit[]): Doc {
-  return apply(base, [...theirs, ...mine]);
+  const clash = theirs.find((t) =&gt; t.field === edit.field &amp;&amp; t.at &gt; edit.at);
</pre></lf-diff>
""",
)
# The same diff, arriving the other way a widget reaches a reader: on a reply, into a
# column narrower than any page's.
PANEL_DIFF_MARKUP = WIDE_DIFF_PAGE[
    WIDE_DIFF_PAGE.index("<lf-diff") : WIDE_DIFF_PAGE.index("</lf-diff>")
    + len("</lf-diff>")
].replace('id="wide-diff"', 'id="rp-diff"')


def serious_axe_violations(page):
    """WCAG A/AA violations at serious or critical, as (violations, report) — the
    one reading both the live sweep and the exported copy's gate assert on."""
    result = Axe().run(
        page,
        options={
            "runOnly": {
                "type": "tag",
                "values": [
                    "wcag2a",
                    "wcag2aa",
                    "wcag21a",
                    "wcag21aa",
                    "wcag22a",
                    "wcag22aa",
                ],
            },
            "resultTypes": ["violations"],
        },
    )
    violations = [
        violation
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ]
    report = "\n\n".join(
        f"{violation['id']} ({violation['impact']}): {violation['help']}\n"
        + "\n".join(
            "  {}: {}".format(
                ", ".join(
                    # A target inside a shadow tree arrives as a selector chain
                    # (a list), one hop per root.
                    sel if isinstance(sel, str) else " >>> ".join(sel)
                    for sel in node["target"]
                ),
                node["failureSummary"],
            )
            for node in violation["nodes"]
        )
        for violation in violations
    )
    return violations, report


# Chips whose words are a price and nothing else, which is two or three characters and
# about 30px — and an inline suggestion swapping one letter for another, about the same.
# Nothing else on the page is unusual, so these are the only things on it that a floor
# written for widgets laying out a region could catch.
SHORT_CHIP_PAGE = leaf_page(
    "chips",
    """
<h1 id="t">Feeder extras</h1>
<p id="p">The bracket order goes in on Friday and there is room in it. Change the
rack flag from <lf-suggestion id="sug-flag"><lf-old>x</lf-old><lf-new>y</lf-new></lf-suggestion>
before it ships.</p>
<lf-options id="extras" choose multiple>
<lf-option id="x-tray"><lf-chip>£9</lf-chip>
<strong>Seed tray</strong> Catches the spill under the south pair.
</lf-option>
<lf-option id="x-dome"><lf-chip tone="ok">£15</lf-chip>
<strong>Weather dome</strong> Keeps the seed dry through a wet week.
</lf-option>
</lf-options>
""",
)
# A page that says one of its words on screen only. The rule is the page's own, which is
# the point: the gate asks what the printed page still says, not who took the words away.
PRINT_LOSS_PAGE = CARRIED_PAGE.replace(
    "</head>",
    "<style>@media print { #lede, #c-bearer { display: none } }</style></head>",
)


def solid_png(width: int, height: int, rgb: tuple) -> bytes:
    """A solid-colour PNG, written here rather than committed, so the pair a shot
    test flips between is two files whose only difference is the one the test made."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


SHOTS = {
    "before": solid_png(600, 300, (210, 220, 235)),
    "after": solid_png(600, 300, (235, 215, 205)),
}
SHOT_SRC = {
    k: f"/media/{hashlib.sha256(v).hexdigest()[:16]}.png" for k, v in SHOTS.items()
}
SHOT_PAGE = LONG_PAGE.replace(
    "</main>",
    f"""<p id="lede">What moved, in words, because the picture cannot say it.</p>
<lf-shot id="shot-nav" alt="the navigation rail"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
</main>""",
)


def shown_frames(page):
    return page.evaluate("""() => [...document.querySelectorAll('.lf-shotframe')]
        .filter(f => getComputedStyle(f).visibility === 'visible')
        .map(f => f.dataset.lfState)""")


def flip_point(page, sel="lf-shot"):
    """The middle of a shot's frame — where a reader comparing would have the pointer.

    Returned rather than clicked, because what the widget is for is alternating from
    one place: a helper that clicked would let a test press two different points and
    still pass, which is the property the old radios failed at.

    Scrolled to first, because `bounding_box` answers in viewport coordinates for an
    element that may be past the fold — on the long page the shot sits on, the point
    comes back below the window and `mouse.click` presses whatever is there instead,
    which reads as the widget refusing the gesture rather than as the test missing it.
    """
    frame = page.locator(f"{sel} .lf-shotframe").first
    frame.scroll_into_view_if_needed()
    box = frame.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


# Two ways a widget leaves words on screen that no comment can land on, written into the
# markup because the gate reads the rendered page and cannot tell who put them there — a
# page-local module is where both actually happen, and standing one up here would test the
# module loader rather than the gate. First: a heading inside a chrome-looking row, with
# nothing said about whose words it is. Second: the words declared the page's, and put
# inside a form control, where no pointer can select them however they are marked.
OUT_OF_REACH_PAGE = CARRIED_PAGE.replace(
    '<lf-option id="c-lax" chosen>',
    '<lf-option id="c-lax" chosen><div class="lf-ui"><strong>Session cookies</strong>'
    "</div><button data-lf-said>Lax, host-only</button>",
)
# A painted fact whose spoken copy is on the page and drawn nowhere, written into the
# markup for the same reason the two above are: the gate reads the rendered page and
# cannot tell who suppressed the word. `recommended` is x-paints, so the runtime writes
# a .lf-quiet span beside each of these; the style takes the box off both. One stands in
# the open and one behind a disclosure the reader has not opened.
PAINTED_IN_SILENCE_PAGE = leaf_page(
    "silence",
    """
<h1 id="h">Transport</h1>
<lf-options id="open-group">
  <lf-option id="p-seen" recommended><strong>Lax cookie</strong> Host-only.</lf-option>
  <lf-option id="p-other"><strong>Bearer header</strong> Every script reads it.</lf-option>
</lf-options>
<details id="folded">
  <summary>Weighed in March</summary>
  <lf-options id="folded-group">
    <lf-option id="p-folded" recommended><strong>Signed URL</strong> Expires.</lf-option>
    <lf-option id="p-spare"><strong>Nothing</strong> Leave it.</lf-option>
  </lf-options>
</details>
""",
    head="<style>.lf-quiet { display: none }</style>",
)
# A module making the mistake the scaffold's own header warns about: words injected
# into the widget wearing the chrome face, with nothing said about whose they are.
# It has to be a module, because a page may not author `.lf-ui` — `reserved_marker_errors`
# refuses it at the door — and no shipped widget makes the mistake, the gate being green.
BADGE_CHROME = """      const row = document.createElement("div");
      row.className = "lf-ui";
      row.textContent = "Sent by the reviewer";
      this.append(row);"""
UNPARSABLE_DIAGRAM = LONG_PAGE.replace(
    "</main>",
    "<lf-diagram id='d-broken'><pre>\nflowchart LR\n  A[Start --&gt; B{{{ ]]] broken\n</pre></lf-diagram>\n</main>",
)
# The thread list is reconciled, not rebuilt, and the tests below are its faces: a
# send is a gesture and reveals what it made; an arrival is news and moves nothing; a
# resolution moves a thread without remaking its neighbours; and all of it holds
# because the nodes survive the poll instead of being replaced by lookalikes. The old
# rebuild passed a lookalike test easily — same markup, fresh nodes — which is why
# these pin identity (a probed element) and geometry (a held thread's own box), not
# appearance.


def in_threads_scrollport(page, selector):
    """Whether the node is fully inside the panel list's scrollport — waited for,
    because the reveal scrolls smoothly and only the arrival is the fact."""
    page.wait_for_function(
        """(sel) => {
            const box = document.querySelector('.lf-threads');
            const node = document.querySelector(sel);
            if (!node) return false;
            const b = box.getBoundingClientRect(), n = node.getBoundingClientRect();
            return n.top >= b.top && n.bottom <= b.bottom;
        }""",
        arg=selector,
    )
