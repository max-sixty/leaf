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
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import registry as registry_model
from leaf import render_checks as render_checks_model
from leaf import rendering as rendering_model
from leaf import service as service_model
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
        if expression == render_checks_model.RELATIVE_REPLAYS:
            evaluate("() => requestAnimationFrame(() => {" + RESIZE_LOOP_EVENT + "})")
        return result

    page.evaluate = with_notice


# What a returning reader's browser puts back before the page runs, declared by the
# runtime that puts it back (leaf.js, ARRANGEMENTS). Read from the page rather than
# listed here: which surfaces remember anything is the runtime's to say, and a list on
# this side would stop at the ones it was taught.
ARRANGEMENTS = (
    "() => import('/runtime/widget-api.js').then((leaf) => leaf.ARRANGEMENTS)"
)

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

    page = browser.new_page(
        viewport=render_checks_model.RENDER_VIEWPORT, color_scheme="light"
    )
    errors = []
    notices = []

    def console_message(message):
        if message.type != "error":
            return
        target = (
            notices if rendering_model.resize_observer_error(message.text) else errors
        )
        target.append(message.text)

    page.on("console", console_message)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    page.add_init_script(rendering_model.WINDOW_ERRORS)
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
            page.wait_for_function(rendering_model.UPGRADED)
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
                page.wait_for_function(rendering_model.UPGRADED)
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

    Settling and not living, which is `rendering.MOVING`'s distinction and is here for
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


# Prose beside identifiers, which is the table a plan or a PR walkthrough writes: a row's
# name, its mechanism in words, and the test that holds it. A test name is one word to
# the line breaker and most of the measure long, so whether it can break is the whole
# difference between the theme's second case and a squeezed table — `held` says how
# each name is written, and nothing else differs between the two pages below.
#
# The longest name is longer than the 720px measure on its own, and that is the fixture
# rather than a flourish. Every width here is the font's, and the measure is not: with a
# 79-character name — this repo's own longest — the three columns asked for 699px of the
# 720px on the CI fallback serif and 775px on macOS Charter, so the bare page scrolled
# where the author read it and fitted with 21px to spare where CI did, and the squeeze
# the gate is supposed to report was never on the page to report. The name below asks
# for 753px on that same narrow font, more than the whole measure by itself, and the
# three columns together for 955px of the 720px — a third more than there is. Every one
# of those widths is the font's, so they shrink together: it takes a serif a quarter
# narrower than the narrowest in play to give this table a way to fit.
def prose_beside_identifiers(held):
    rows = [
        (
            "Log shape",
            (
                "<code>token</code> in place of <code>text</code> on <code>comment</code>"
                " and <code>reply</code>; a record is one or the other, and a token rides"
                " no suggestion, hold, or markup."
            ),
            ["test_the_door_admits_a_reaction_only_as_a_token_the_layer_declares"],
        ),
        (
            "In threads",
            (
                "A strip under each agent message; <code>settles</code> on the latest"
                " agent message ends the wait as a reading of the log, undo restores it."
            ),
            [
                "test_an_ok_on_the_agents_latest_reply_takes_the_thread_out_of_waiting",
                "test_a_reply_to_a_reaction_opens_a_thread_and_resolve_is_its_floor",
            ],
        ),
        (
            "Keyboard",
            (
                "<kbd>r</kbd> arms the bar with address-chip digits, 1–n in declared"
                " order; a stray key disarms and keeps its meaning."
            ),
            [
                "test_the_keyboard_arms_the_bar_with_address_chip_digits_in_declared_order_and_a_stray_key_disarms_it_and_keeps_its_meaning"
            ],
        ),
    ]
    body = "".join(
        f'<tr><th scope="row">{name}</th><td>{how}</td>'
        f"<td>{', '.join(held(t) for t in tests)}</td></tr>"
        for name, how, tests in rows
    )
    return leaf_page(
        "held",
        f"""
<h1 id="t">The plan</h1>
<p id="p">Each item, the mechanism that carries it, and the test that holds it.</p>
<table id="held">
<thead><tr><th>Plan item</th><th>Mechanism</th><th>Held by</th></tr></thead>
<tbody>{body}</tbody>
</table>
""",
    )


IDENTIFIERS_IN_CODE_PAGE = prose_beside_identifiers(lambda name: f"<code>{name}</code>")
BARE_IDENTIFIERS_PAGE = prose_beside_identifiers(lambda name: name)

# The honest third case with every line an author can write and no wrap: a token split
# around an inline <code>, which is set smaller and stands 3px lower on the same line
# (a reading of rect tops called it a wrap and told the author to write <code>); a
# <br>; a newline under <pre>; loose words either side of a nested table. Each is a
# line the author drew, and none stands shorter with soft wrapping off.
AUTHORED_LINES_PAGE = (
    WIDE_TABLE_PAGE.replace("<td>value_number_7</td>", "<td>value <code>7</code></td>")
    .replace("<td>value_number_6</td>", "<td>value<br>six</td>")
    .replace("<td>value_number_5</td>", "<td><pre>def go():\n    return 5</pre></td>")
    .replace(
        "<td>value_number_4</td>",
        "<td>before <table><tr><td>four</td></tr></table> after</td>",
    )
)

# The squeeze written entirely in inline elements: eight single-token columns hold the
# table open, and the ninth is a run of owners as links, one word each, so every wrap
# in it falls between two nodes and never inside one — set at line-height 1, where the
# glyph boxes of two lines overlap and a reading of line boxes lost the second line.
# WIDE_TABLE_PAGE with the column added, so the two differ in nothing but the run.
LINKED_CELLS_PAGE = WIDE_TABLE_PAGE.replace(
    "</th></tr></thead>", "</th><th>Owners</th></tr></thead>"
).replace(
    "</td></tr></tbody>",
    '</td><td style="line-height: 1">'
    + ", ".join(
        f'<a href="#t">{w}</a>' for w in ["alpha", "bravo", "charlie", "delta", "echo"]
    )
    + "</td></tr></tbody>",
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
    page.wait_for_function(f"() => ({rendering_model.MOVING})().length === 0")
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
        t for t in registry_model.load_registry(page_dir) if not t.startswith("$")
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
# The page as a press leaves it. Where the pointer is resting is not that: the runtime
# paints .lf-mark-hover on a marked element under the cursor, so a reading taken with the
# pointer still on an item reports the hover as a change the press made. It shows up only
# on an element some thread already marks, which is why nothing saw it until a shipped
# log carried a comment on a widget.
PAGE_MARKUP = """() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => {
        const c = n.cloneNode(true);
        for (const g of c.querySelectorAll("[data-lf-gen]")) g.textContent = "";
        if (c.dataset && c.dataset.lfGen !== undefined) c.textContent = "";
        for (const el of [c, ...c.querySelectorAll("*")])
            el.classList?.remove("lf-mark-hover");
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
        d = service_model.state_home() / "pages" / name
        result = CliRunner().invoke(cli_model.cli, ["page", "init", str(d)])
        assert result.exit_code == 0, result.output
        (d / "versions" / "v1.html").write_text(
            LONG_PAGE.replace("<title>long</title>", f"<title>{title}</title>")
        )
        events_model.append_event(
            d, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
        )
        files_model.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "running the suite",
                "ts": events_model.now_iso(),
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
        httpd = hosting_model.LeafHTTPServer(
            ("127.0.0.1", 0), http_model.handler_for(d, TOKEN)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        port = httpd.server_address[1]
        # Desired address and a held, contentless lease are the two facts a real
        # server exposes to neighbouring pages.
        files_model.write_json(
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


DEEP_FOCUS = """() => {
  let e = document.activeElement;
  while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
  return e;
}"""


# Every rule in this page's own composed layer that draws the here ring, read out of the
# CSSOM. The layer is where the population lives — a list kept beside it is a second
# statement of what the theme says, and the one that was kept here in prose went stale
# the moment a rule moved. Twelve of the twenty-three had never been stood on when this
# was written, and nothing said so, because the gate only ever asked about rules it had
# happened to meet.
#
# Nesting is resolved the way the spec defines it — `&` is `:is(parent)`, and a nested
# selector naming no `&` is a descendant of it — because the two texts joined by hand
# give a string no engine will take. `querySelectorAll` throws on one, and a throw
# swallowed here reads exactly like a rule nothing on the page matches: the option
# group's own ring was invisible to this for that reason alone.
RING_RULES = """() => {
  const rules = new Map();
  const eaten = new Set();
  const eat = (sheet, shadow) => {
    if (!sheet || eaten.has(sheet)) return;
    eaten.add(sheet);
    let list;
    try { list = sheet.cssRules; } catch { return; }  // a sheet from another origin
    const walk = (from, outer) => {
      for (const rule of from) {
        // A rule that carries no selector of its own is one of three things, and the
        // three are not interchangeable. A condition — @media, @supports — decides
        // whether its contents apply at all, and one that does not hold here is left
        // out of the population rather than passed through: this gate reads one colour
        // scheme and no print stylesheet, and a rule it cannot make the page paint is a
        // rule it must not then credit off a neighbour's ring. @scope is a selector
        // constraint wearing a condition's shape — eleven of the layer's ring rules sit
        // under `@scope (.lf-chrome)` — so its root joins the selector. Anything else
        // (@layer) passes its parent's selector through untouched.
        if (!rule.selectorText) {
          if (rule.media && !matchMedia(rule.media.mediaText).matches) continue;
          if (rule.conditionText !== undefined && !rule.media
              && !CSS.supports(rule.conditionText)) continue;
          const root = rule.start;  // CSSScopeRule
          // A declaration written after a nested rule in the same block: Chrome hoists
          // it into a CSSNestedDeclarations, which has a style and no selector, so a
          // walk that asks for both drops it and the rule leaves the population on an
          // ordinary reorder.
          if (rule.style) keep(rule, outer, outer);
          if (rule.cssRules)
            walk(rule.cssRules, root ? `${outer ? `${outer} ` : ''}${root}` : outer);
          continue;
        }
        const own = rule.selectorText;
        const whole = !outer
          ? own
          : own.includes('&')
            ? own.replaceAll('&', `:is(${outer})`)
            : `:is(${outer}) ${own}`;
        keep(rule, whole, outer);
        if (rule.cssRules?.length) walk(rule.cssRules, whole);
      }
    };
    // Which root a rule was met in is structure, not something to infer back from its
    // text later: the same theme file is both linked at document level and adopted into
    // every shadow tree, and a shadow rule written without :host is a plain selector
    // that must still be queried in its own root.
    const keep = (rule, whole, outer) => {
      if (!/outline\\s*:[^;}]*--here-ring/.test((rule.cssText || '').split('{')[1] || ''))
        return;
      rules.set(whole, [
        outer && outer !== whole ? `${whole.slice(outer.length).trim()} (in ${outer})`
                                 : whole,
        (rules.get(whole)?.[1] ?? false) || shadow,
      ]);
    };
    walk(list, '');
  };
  for (const sheet of document.styleSheets) eat(sheet, false);
  for (const sheet of document.adoptedStyleSheets) eat(sheet, false);
  for (const el of document.querySelectorAll('*'))
    if (el.shadowRoot) {
      for (const sheet of el.shadowRoot.styleSheets) eat(sheet, true);
      for (const sheet of el.shadowRoot.adoptedStyleSheets) eat(sheet, true);
    }
  return [...rules].map(([whole, [said, shadow]]) => [whole, said, shadow]);
}"""


# Every here ring the page is showing right now, and what is wrong with each.
#
# Asked of the elements the layer's ring rules match rather than of the focused one.
# The two are not the same set: four rules draw
# the ring on something other than the control holding focus — a thread card wears it
# for anything focused inside it, an ask wears it for whichever of its controls the
# reader reached, a joined option group wears the one its picks give up, and an element
# a focused thread is anchored to wears it with no focus of its own — and a reading that
# asks only `getComputedStyle(activeElement)` returns `no ring here` for every one. A 2px
# cut planted on `.lf-thread:focus-within` passed all ten examples.
#
# The focused element is a candidate too, whatever paints its outline, so a ring the
# platform draws and the theme never named is still measured.
RINGS_DRAWN = f"""async () => {{
  // shownBand, rather than a fourth reading of what a box clips to. Its own comment
  // carries why: version check --render imports it so the band a handover is refused
  // against and the band the page paints to are one reading, and written twice they
  // disagreed twice. This was the third copy and it was wrong in both of the ways that
  // comment names — it asked only about overflow, so paint containment and
  // content-visibility clipped a ring away with nothing said, and it measured the
  // padding box with the scrollbar's gutter still in it.
  const {{ shownBand }} = await import('/runtime/widget-api.js');
  const named = {NAMED};
  const holds = (a, b) => {{
    for (let n = b; n; n = n.parentNode || n.host) if (n === a) return true;
    return false;
  }};
  // The layer's rules are the page's for its whole life, so they are read once. What
  // matches them is asked afresh every time, because that is the part that moves.
  const rules = (window.__lfRingRules ??= ({RING_RULES})());
  const roots = [];
  for (const el of document.querySelectorAll('*'))
    if (el.shadowRoot) roots.push(el.shadowRoot);
  // `:host(X) rest` is only meaningful inside a shadow root, and the parentheses are
  // matched rather than split at the first `)` — `:host(:not(.x))` would otherwise be
  // cut in half and take the rest of the selector with it.
  const hosted = (sel) => {{
    if (!sel.startsWith(':host')) return null;
    if (!sel.startsWith(':host(')) return {{ host: '*', rest: sel.slice(5).trim() }};
    let depth = 0;
    for (let i = 5; i < sel.length; i++) {{
      if (sel[i] === '(') depth++;
      else if (sel[i] === ')' && !--depth)
        return {{ host: sel.slice(6, i), rest: sel.slice(i + 1).trim() }};
    }}
    return null;
  }};
  const claimed = new Map();
  for (const [sel, , shadow] of rules) {{
    const host = hosted(sel);
    const where = [
      ...(host ? [] : [document]),
      ...(shadow
        ? roots.filter((root) => !host || root.host.matches(host.host))
        : []),
    ];
    for (const root of where)
      // `:host(X)` with nothing after it styles the widget's own box, so what it
      // matches is the host and there is no selector left to run inside the root —
      // `querySelectorAll('')` throws, and the throw takes the whole reading down
      // naming a line of JavaScript rather than a ring.
      for (const el of host && !host.rest
        ? [root.host]
        : root.querySelectorAll(host ? host.rest : sel)) {{
        if (!claimed.has(el)) claimed.set(el, []);
        claimed.get(el).push(sel);
      }}
  }}
  const focused = ({DEEP_FOCUS})();
  if (focused && focused !== document.body && focused !== document.documentElement
      && !claimed.has(focused)) claimed.set(focused, []);
  // Whether the outline on this element is the layer's ring: `--here-ring` is
  // `var(--here-ring-w) solid var(--accent)`, so its width and style are what the
  // element computes them to and both sides of the comparison are computed values.
  // The colour is not usable for this — a custom property serializes as it was
  // written and `outline-color` as it resolved, which agree for `#2f5480` and for
  // nothing more exotic. `color-mix()` or `light-dark()` in a package's accent turned
  // every rule in the layer uncredited and the whole gate red on a page drawing every
  // ring correctly. An element wearing some other outline is still measured, since a
  // visible outline cut in half is a fault whoever drew it.
  const isHereRing = (cs) =>
    cs.outlineStyle === 'solid'
    && cs.outlineWidth === cs.getPropertyValue('--here-ring-w').trim();
  const answers = [];
  for (const [el, matched] of claimed) {{
    // A ring on something the browser is not rendering is not on screen, and its box is
    // whatever the last layout left behind. An inactive lf-tab is the case: it carries
    // `hidden="until-found"`, so the UA gives it `content-visibility: hidden`, its
    // contents are skipped, and the ask inside one still answers a stale rect three
    // thousand pixels from the band its own panel now reports.
    if (!el.checkVisibility({{
      contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true,
    }})) continue;
    // Straight off the computed style, which holds because no ring in this layer moves.
    // A ring on its way somewhere reads as wherever it has got to — mid-transition the
    // platform reports the animated value, which early on is the value the property is
    // leaving — and this once read every ring that way, because the theme's
    // reduced-motion guard shortened transitions rather than removing them and
    // `transition-property` is `all`, so a ring arriving was a ring in transit for two
    // frames on every page. That is fixed where it was made (theme.css). A layer that
    // deliberately animates a ring owes this reading a wait on `getAnimations()`; one
    // written here now would wait on nothing, in front of the reading it is meant to
    // protect.
    const cs = getComputedStyle(el);
    const w = cs.outlineStyle === 'none' ? 0 : parseFloat(cs.outlineWidth) || 0;
    if (!w) continue;
    const grow = w + (parseFloat(cs.outlineOffset) || 0);
    const b = el.getBoundingClientRect();
    const ring = {{ top: b.top - grow, left: b.left - grow,
                   bottom: b.bottom + grow, right: b.right + grow }};
    const at = (r) => [r.left, r.top, r.right, r.bottom].map(Math.round).join();
    // A ring drawn inside its control's box — twelve of the layer's rules inset theirs —
    // cannot leave it, so `cuts` is empty for those by geometry and the covers half is
    // the whole of what this says about them.
    const cuts = [];
    let scrolled = false;
    const above = (n) => n.parentElement || n.getRootNode().host || null;
    // One side, one message, named for the innermost box that took it. A scroll region's
    // edge is often the window's to the pixel — .lf-threads' right edge is .lf-panel's is
    // innerWidth — and one ring reported twice reads as two defects. The innermost box is
    // the more useful of the two answers anyway: it is the box the control lives in.
    const taken = {{}};
    const took = (band, who) => {{
      // Only the sides where this box is showing the control's own edge, which is the
      // claim a box can be held to: where the control can be seen, so can the ring
      // around it. Asked of the edge rather than of the size, because the two answers
      // differ for everything not focused — a code block taller than the window hangs
      // out of it however the browser scrolls; an ask wears its ring for a control the
      // reader reached near its top and its own foot is below the fold; a thread's
      // element mark is painted on a widget nobody has scrolled to at all. None of
      // those is a ring drawn outside its box, and a size test excuses the first and
      // reports the other two.
      //
      // What it gives up in exchange: a control whose own box its holder clips gets no
      // ring reading on that side, where a size test would have reported one. That is
      // a control drawn where no reader can reach it rather than a ring leaving its
      // box, and CLIPPED_CONTROLS is the reading that owns it.
      //
      // Asked of the control's border box and not of its ring, because a ring is the one
      // thing a box is asked to find room for beyond what it holds: a control filling its
      // scroller to the pixel excused itself from every reading it should have answered.
      const shows = {{
        top: b.top >= band.top - 0.5,
        bottom: b.bottom <= band.bottom + 0.5,
        left: b.left >= band.left - 0.5,
        right: b.right <= band.right + 0.5,
      }};
      for (const [side, by] of Object.entries({{
        top: band.top - ring.top,
        left: band.left - ring.left,
        bottom: ring.bottom - band.bottom,
        right: ring.right - band.right,
      }}))
        if (!taken[side] && by > 0.5 && shows[side])
          taken[side] =
            `its ${{side}} edge is ${{Math.round(by * 10) / 10}}px outside ` + who
            + ` (ring ${{at(ring)}} vs band ${{at(band)}})`;
    }};
    // `clipped` in anchors.js is this walk, and this is its shape: from the box itself
    // rather than its parent, skipping the box's own band because an element is not clipped
    // by its own overflow, and stopping at the first fixed box. Its comment records what
    // starting at the parent cost — "the question of every ancestor of a fixed box and
    // never of the box" — which is the bug this reading had too.
    for (let a = el; a; a = above(a)) {{
      if (a !== el) {{
        if (a.scrollHeight > a.clientHeight) scrolled = true;
        const band = shownBand(a);
        if (band) took(band, named(a));
      }}
      if (getComputedStyle(a).position === 'fixed') break;
    }}
    // The window last, so an inner box that shares an edge with it is the one named, and
    // unconditionally, because the walk above may have stopped at a fixed box and every
    // box stops somewhere. It is the outermost clip there is: a fixed subtree is laid out
    // against it, and everything else reaches it through body, which is this page's
    // scroller. Not a claim that nothing else could clip a fixed box — a containing block
    // established by transform, filter or containment is a real case, and .lf-banner's
    // backdrop-filter is one such generator — but the walk covers that case now by asking
    // every box on the way up instead of branching on the focused one's own position.
    took({{ top: 0, left: 0, bottom: innerHeight, right: innerWidth }}, 'the window');
    for (const side of ['top', 'left', 'bottom', 'right'])
      if (taken[side]) cuts.push(taken[side]);
    const paints = (n) => {{
      const s = getComputedStyle(n);
      return s.backgroundImage !== 'none'
        || !/^(transparent$|rgba\\(.*,\\s*0\\))/.test(s.backgroundColor);
    }};
    const mid = (x, y) => (x + y) / 2;
    const covers = [];
    // Whether this reading has an order to read at all. It works by hit-testing the ring's
    // own pixels and taking whatever comes back as standing over them — but an outline is
    // painted by its control, at its control's level, and an outline's pixels are not
    // hit-testable. A pixel of ring outside the control's box therefore returns whatever
    // is beneath, and beneath is where the answer would have to come from.
    //
    // That is sound while the control's own surface takes hits, because then the ring's
    // sample either lands on the control's line or lands somewhere the line does not
    // reach. It stops being sound inside a surface declaring `pointer-events: none`: the
    // key line stands over the page at z-index 8940 and takes no hits, so its More button
    // is topmost where it lives and every line of code under the ring's top run read as
    // standing over it. `cuts` is geometry and still answers for these; this half says
    // nothing rather than saying the opposite of what the page shows.
    let ordered = true;
    for (let a = el; a; a = above(a))
      if (getComputedStyle(a).pointerEvents === 'none') {{ ordered = false; break; }}
    // Whether a fixed surface standing over this ring is worth reporting. Tab scrolls
    // the control it lands on clear of the banner — that is what the document's
    // scroll-padding is for — so a fixed bar over the focused control's ring is a
    // promise broken. Over a ring some ancestor wears it is not: nobody scrolled that
    // box, and where its top edge comes to rest a pixel under the bar is the reader's
    // scroll position rather than the layer's doing. An option group 2261px tall, whose
    // pick the walk had landed on, is the case.
    const fixedOver = (n) => {{
      for (let a = n; a; a = above(a))
        if (getComputedStyle(a).position === 'fixed') return true;
      return false;
    }};
    const scrolledTo = el === focused;
    // Each run sampled in the middle of the part of it that is on screen, rather than in
    // the middle of the whole run. They differ for anything taller or wider than the
    // window, and then the plain midpoint is a point the reader cannot see: an option
    // group 1791px tall was sampled 22px down the window, which is inside the banner,
    // and the banner's status dot came back as standing over its ring.
    const runX = [Math.max(ring.left, 0), Math.min(ring.right, innerWidth)];
    const runY = [Math.max(ring.top, 0), Math.min(ring.bottom, innerHeight)];
    const shownRun = runX[0] <= runX[1] && runY[0] <= runY[1];
    for (const [side, x, y] of ordered && shownRun ? [
      ['top', mid(...runX), ring.top + 0.5],
      ['bottom', mid(...runX), ring.bottom - 0.5],
      ['left', ring.left + 0.5, mid(...runY)],
      ['right', ring.right - 0.5, mid(...runY)],
    ] : []) {{
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      for (const over of document.elementsFromPoint(x, y)) {{
        if (over === el || holds(el, over) || holds(over, el)) break;
        if (!paints(over)) continue;
        if (!scrolledTo && fixedOver(over)) break;
        // Is the control itself under this too? Where a control stands partly behind
        // something, the ring's run on that side is behind whatever the control is behind,
        // which is a fact about where the control was put rather than about the ring being
        // drawn outside its box. The claim worth making is the other one: where the control
        // can be seen, so can the ring that names it. Stated without a case on purpose —
        // the one this was written for was the tray's edge handle running the whole height
        // of the window under the banner, which stopped being true in 3a8f16f0, the commit
        // that added this comment and the handle's top inset together.
        //
        // The step in has to clear the ring's own band, and `grow + w` from the ring's
        // edge is what lands `w + 1` inside the box whichever side of it the ring is
        // drawn on. Written as `grow + 1` it cleared an outward ring, where grow is
        // already at least w, and landed inside an inset one, where grow is nought:
        // every covered inset ring answered that the control was behind the same thing
        // and was dropped without a word. The rings the panel's own list draws are all
        // inset, so this went blind in the same commit that made them so — a thread
        // lying two pixels under its stuck run heading is a card with three sides, and
        // the gate written to catch exactly that reported nothing.
        const step = grow + w + 1;
        const inx = x + (side === 'left' ? step : side === 'right' ? -step : 0);
        const iny = y + (side === 'top' ? step : side === 'bottom' ? -step : 0);
        if (document.elementsFromPoint(inx, iny).includes(over)) break;
        const o = over.getBoundingClientRect();
        covers.push(`its ${{side}} edge is under ` + named(over)
                    + ` (ring ${{at(ring)}} vs ${{at(o)}}, sampled ${{Math.round(x)}},`
                    + `${{Math.round(y)}})`);
        break;
      }}
    }}
    answers.push({{
      who: named(el),
      rules: isHereRing(cs) ? matched : [],
      focused: el === focused,
      scrolled,
      cuts,
      covers,
    }});
  }}
  return answers;
}}"""


COVERED_TOP = """() => {
  const el = document.activeElement;
  const box = document.querySelector('.lf-threads');
  if (!el || !box.contains(el)) return null;
  const r = el.getBoundingClientRect();
  const over = document.elementsFromPoint((r.left + r.right) / 2, r.top + 1)
    .find((n) => n !== el && !el.contains(n) && !n.contains(el)
                 && n.classList.contains('lf-pinned'));
  if (!over) return null;
  const o = over.getBoundingClientRect();
  return `${over.textContent.trim().slice(0, 32)} covers it down to `
         + `${Math.round(o.bottom - r.top)}px in`;
}"""


def ring_rules(page):
    """The layer's ring rules, as the reading itself holds them.

    Through the reading's own memo rather than a second evaluation, so the
    population a coverage floor divides by is the one the credits were counted
    against. Two evaluations are two moments, and a stylesheet arriving between
    them — design mode, a module loading late — makes the floor report a rule
    that was never checkable or hide one that was.
    """
    return page.evaluate(f"() => (window.__lfRingRules ??= ({RING_RULES})())")


def rings_drawn(page):
    """Every here ring the page is drawing, each with what is wrong with it."""
    return page.evaluate(RINGS_DRAWN)


def standing_ring(page):
    """The ring on the control the keyboard is standing on, or None if it wears none."""
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
