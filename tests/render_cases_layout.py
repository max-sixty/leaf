"""Shared layout browser-integration cases and readings."""

import hashlib
import io
import math
import re
import struct
import zlib
from weakref import WeakKeyDictionary

import tinycss2
from axe_playwright_python.sync_playwright import Axe
from browser_sources import browser_function
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    leaf_page,
    panel_settled,
    rgb_pixel,
)

from leaf import render_checks as render_checks_model
from leaf.registry import storage as registry_storage
from leaf.registry.contract import element_declarations
from leaf.render_checks import rendered
from leaf.render_gate import scheme as render_gate_model

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
ARRIVAL_TRANSITIONS = """window.lfArrivalTransitions = [];
const lfSeenTransitions = new Set();
addEventListener("transitionrun", (event) => {
  if (document.body?.hasAttribute("data-lf-presented")) return;
  if (!(event.target instanceof Element) || !event.target.closest("main")) return;
  const id = event.target.id ? `#${event.target.id}` : "";
  const target = `${event.target.localName}${id}${event.pseudoElement ?? ""}`;
  const key = `${target}:${event.propertyName}`;
  if (lfSeenTransitions.has(key)) return;
  lfSeenTransitions.add(key);
  window.lfArrivalTransitions.push({
    target,
    property: event.propertyName,
  });
}, true);"""


def resize_notice_after_last_probe(page):
    """Schedule the notice for the rendering turn after the gate's last probe."""
    evaluate = page.evaluate

    def with_notice(expression, *args, **kwargs):
        if "requestFrame()" in expression:
            evaluate(
                "() => requestAnimationFrame(() => {"
                "if (matchMedia('(prefers-color-scheme: light)').matches) {"
                + RESIZE_LOOP_EVENT
                + "}})"
            )
        return evaluate(expression, *args, **kwargs)

    page.evaluate = with_notice


def user_view_restore_cases(page):
    """The return states declared by the runtime that restores them."""
    return render_checks_model.evaluate_probe(page, "userViewRestoreCases")


def apply_restore_case(page, restore_case):
    """Put exactly one declared return state into this user's stores."""
    render_checks_model.evaluate_probe(page, "applyRestoreCase", restore_case)


def arrival_transition_findings(page, arrival):
    return [
        f"[{arrival}] {transition['property']} transitioned on "
        f"{transition['target']} before presentation"
        for transition in page.evaluate("() => window.lfArrivalTransitions")
    ]


def arrival_findings(browser, url):
    """Whether a page comes up at all in each restore case a user can return to.

    The suite's, not `render_version`'s, and the line between them is whose fault a
    finding is. Everything the gate reads is something the page's author wrote and
    can change; a restore is the layer's, identical under every version, so an agent
    running the gate at handover would be paying for a verdict on code it did not
    write and cannot fix.

    What it reads: a fresh context holds nothing, so every other reading in the suite
    is of a first visit — design mode off, the annotations shown —
    and each of those is something a user turns on once and gets back on every load
    afterwards. That left the restores as the one road onto a page with nothing
    watching it, and a drawer someone had left open came up as a ReferenceError
    instead of a page: it was put up by code running while the runtime was still
    evaluating, which could reach almost nothing. It reached the user, who reported
    it.

    One page, reloaded into each restore case, which is what a returning user does:
    the store is written on the origin the page is already on and read while the next
    load evaluates. What comes back is completed presentation, any page transition that
    began before it, and the console. Boxes are not measured again: every shipped example
    was measured in each of these restore cases and none of them moved a box that a first
    visit didn't.
    """

    page = browser.new_page(
        viewport=render_checks_model.RENDER_VIEWPORT, color_scheme="light"
    )
    # A transition is transient, so preserve its own event through presentation.
    page.add_init_script(ARRIVAL_TRANSITIONS)
    errors = []
    notices = []

    def console_message(message):
        found = render_gate_model.console_finding(message, warnings=False)
        if found is not None:
            errors.append(found)

    def window_error(error):
        found = render_gate_model.window_finding(error)
        (notices if found.code == "resize-loop" else errors).append(found)

    page.on("console", console_message)
    render_gate_model.collect_page_exceptions(page, errors)
    render_checks_model.install_window_errors(page, window_error)
    found = []
    # A first visit, from which to read the restore cases. Reported
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
        # the former design-decision example, and buys this nothing.
        page.goto(url, wait_until="load")
        render_checks_model.wait_until_ready(page)
    except (PlaywrightTimeout, render_checks_model.PageNotReady):
        return [
            "[arrivals] the page never came up unarranged, so nothing could be "
            "arranged — "
            + (
                "; ".join(map(str, [*errors, *notices]))
                or "and no console error says why"
            )
        ]
    found += arrival_transition_findings(page, "first visit")
    for restore_case in user_view_restore_cases(page):
        apply_restore_case(page, restore_case)
        # A console the last restore case dirtied is not this one's news.
        errors.clear()
        notices.clear()
        try:
            page.reload(wait_until="load")
            render_checks_model.wait_until_ready(page)
        except (PlaywrightTimeout, render_checks_model.PageNotReady):
            found.append(
                f"[{restore_case['name']}] the page never finished coming up — "
                + (
                    "; ".join(map(str, [*errors, *notices]))
                    or "and no console error says why"
                )
            )
            continue
        found += arrival_transition_findings(page, restore_case["name"])
        # A ResizeObserver notice is the gate's to adjudicate over two attempts on
        # the same document; one seen here says nothing on its own.
        found += [f"[{restore_case['name']}] console: {e}" for e in errors]
    return found


def motions(events):
    """The settling motions the browser reported, keyed by the motion, not by its target.

    Settling and not living, which is the render gate's `moving` distinction and is here for
    its reason: the panel's status sheens for as long as the agent works, and something
    that never ends never arrived anywhere. An unbounded iteration count cannot cross
    JSON, so the browser omits it, and that omission is the reading.

    A target is a backend node id, and the same panel over two loads is two of them,
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
    attributes = dict(zip(pairs[::2], pairs[1::2], strict=True))
    name = described.get("localName") or described.get("nodeName")
    if attributes.get("id"):
        return f"{name}#{attributes['id']}"
    if attributes.get("class"):
        return f"{name}.{attributes['class'].replace(' ', '.')}"
    return name


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
# each name is written, and nothing else differs between the two pages below. The
# names run past ninety characters so that bare they hold the table open on any font:
# at seventy-nine the bare table scrolled by ten pixels on a Mac and fitted on CI's
# fonts, where the gate, rightly silent, read as broken.
def prose_beside_identifiers(held):
    rows = [
        (
            "Log shape",
            (
                "<code>token</code> in place of <code>text</code> on <code>comment</code>"
                " and <code>reply</code>; a record is one or the other, and a token rides"
                " no suggestion, hold, or markup."
            ),
            [
                "test_the_door_admits_a_reaction_only_as_a_token_the_layer_declares_and_refuses_one_it_does_not"
            ],
        ),
        (
            "In threads",
            (
                "A strip under each agent message; <code>settles</code> on the latest"
                " agent message ends the wait as a reading of the log, undo restores it."
            ),
            [
                "test_an_ok_on_the_agents_latest_reply_takes_the_thread_out_of_waiting_until_the_next_question",
                "test_a_reply_to_a_reaction_opens_a_thread_and_resolve_is_its_floor_whatever_the_version",
            ],
        ),
        (
            "Keyboard",
            (
                "<kbd>r</kbd> arms the bar with binding badges, 1–n in declared"
                " order; a stray key disarms and keeps its meaning."
            ),
            [
                "test_the_keyboard_arms_the_bar_with_digits_and_the_line_names_what_z_takes_back_when_pressed"
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

# A comparison of options in two-word cells, which a phone squeezes and neither fixed
# viewport does: at its longest words it stands about 414px wide, so it fits the 540px
# viewport with some 80px to spare, and at 360px it scrolls about 100px with every
# option's cells wrapped. An author's comparison table did this on a 390px phone and
# passed a gate that read only the fixed viewports. Both margins are wide enough that
# CI's fonts land on the same side of them.
PHONE_SQUEEZED_TABLE = """
<table id="options">
<thead><tr><th></th><th>Stay put</th><th>Move rows</th><th>Drop state</th>
<th>Split reads</th><th>Cache more</th></tr></thead>
<tbody>
<tr><th scope="row">Read time</th><td>fast reads</td><td>slower reads</td>
<td>no reads</td><td>mixed reads</td><td>warm reads</td></tr>
<tr><th scope="row">Logout</th><td>lags behind</td><td>at once</td>
<td>after expiry</td><td>at once</td><td>lags behind</td></tr>
<tr><th scope="row">Cost</th><td>contract renewal</td><td>near zero</td>
<td>near zero</td><td>some hosts</td><td>more memory</td></tr>
</tbody>
</table>
"""

# A block wider than the column and narrower than the window: 65% of 1280px is
# 832px against a 720px column, so it stands 112px out in the margin with
# the body not scrolling by a pixel. In vw rather than px because the static lint
# counts pixels and would have caught it before a browser ever saw it.
# 65vw passes the 720px column at the desktop viewport, and falls short of scrolling the
# page sideways at every width the gate sweeps: it would from about 2400px.
SPILLING_PAGE = LONG_PAGE.replace(
    "</main>", "<div id='too-wide' style='width: 65vw'>Wide.</div>\n</main>"
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
# margin element holds — every one of which inherits the box its parent put out there. The
# compact posture has no margin for these synthetic margin elements, so it removes them.
FLOATING_PAGE = LONG_PAGE.replace(
    "</main>",
    "<style>@media (max-width: 1199px) { .fixture-margin-float { display: none; } }</style>"
    "<div class='fixture-margin-float' id='in-the-margin' style='float: left; clear: left; width: 160px;"
    " margin-left: -184px'>Beside <code id='inner-word'>--flag</code>.</div>"
    "<div class='fixture-margin-float' id='half-out' style='float: left; clear: left; width: 180px;"
    " margin-left: -90px'>Across.</div>"
    "<div class='fixture-margin-float' id='logical' style='float: inline-start; clear: left; width: 160px;"
    " margin-left: -184px'>Beside.</div>"
    "<div class='fixture-margin-float' id='off-window' style='float: left; clear: left; width: 180px;"
    " margin-left: -900px'>Gone.</div>\n</main>",
)
SIDENOTE_IN_A_WIDGET = LONG_PAGE.replace(
    "</main>",
    """<lf-ask id="where-decision"><h2>Which option?</h2>
<lf-options id="where" choose>
  <lf-option id="opt-a"><strong>First</strong>
    <aside class="sidenote" id="boxed-note">Measured over a quarter.</aside>
    <p>An option carrying a note written inside it.</p>
  </lf-option>
  <lf-option id="opt-b"><strong>Second</strong> The other one.</lf-option>
</lf-options></lf-ask>
</main>""",
)


# A note written level with a change, which is the one restore case that puts two
# elements in the right margin on the same line.
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
    "<div id='scrolling' style='width: 300px; overflow-x: auto; padding-bottom: 15px'>"
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
    "<div id='html-drawing' style='--lf-drawing: 1; width: 120px; overflow: hidden'>"
    "<div id='drawing-pixels' style='width: 300px; height: 30px; background: coral'>"
    "</div><lf-test-drawing-control id='clipped-drawing'></lf-test-drawing-control>"
    "<lf-test-drawing-control id='clean-drawing'>"
    "</lf-test-drawing-control></div>"
    "<div id='drawing-holder' style='width: 120px; overflow: hidden'>"
    "<div id='outside-viewport' style='--lf-drawing: 1; width: 180px; overflow: hidden'>"
    "<div style='width: 300px; height: 30px; background: coral'></div></div></div>"
    "\n</main>",
).replace(
    "</head>",
    "<style>lf-test-drawing-control { display: block; width: 90px; }"
    "#clipped-drawing { width: 200px; }</style></head>",
)
_LOG_LINES = "\n".join(f"line {i}" for i in range(1, 41))
# Boxes that cut off content of their own, which has no box for a container to lose,
# beside boxes that cut on purpose and say so. A <pre> scrolls sideways only, so a
# max-height alone hides every line past it.
CUT_CONTENT = (
    f"<pre id='capped-log' style='max-height: 6rem'>{_LOG_LINES}</pre>"
    "<div id='short-box' style='height: 3rem; overflow: hidden'>"
    "<p>First of three.</p><p>Second of three.</p><p>Third of three.</p></div>"
    "<div id='unwrapped' style='width: 120px; overflow: hidden; white-space: nowrap'>"
    "A label written longer than its box</div>"
    f"<pre id='bounded-log' data-bound='start'>{_LOG_LINES}</pre>"
    "<details id='shut-log'><summary>The whole log</summary>"
    f"<pre id='shut-capped' style='max-height: 6rem'>{_LOG_LINES}</pre></details>"
    "<p id='clamped' style='display: -webkit-box; -webkit-box-orient: vertical; "
    "-webkit-line-clamp: 2; overflow: hidden'>"
    + "A clamped summary marks its own cut. "
    * 20
    + "</p><p id='tight-line' style='line-height: 1; height: 1em; overflow: hidden'>"
    "Descenders gyp</p>"
    "<span id='listening' style='position: absolute; width: 1px; height: 1px; "
    "overflow: hidden; clip-path: inset(50%); white-space: nowrap'>"
    "Words for whoever is listening</span>"
)
DRAWING_CONTROL_LAYER = {
    "lf-test-drawing-control": {
        "description": "A native offered control inside a drawing viewport.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-example": '<lf-test-drawing-control id="control"></lf-test-drawing-control>',
    }
}
DRAWING_CONTROL_WIDGETS = {
    "lf-test-drawing-control.js": """
import { once, offer } from '/runtime/widget-api.js';
customElements.define('lf-test-drawing-control', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const control = offer('button', 'drawing-control', 'Inspect');
    control.id = `${this.id}-control`;
    control.style.width = '100%';
    this.append(control);
  }
});
"""
}
# A scroller the page wrote and did not position, beside one it did. The commented
# words stand at the far end of the first, since a word laid out against the page from
# the near end lands inside the window and escapes nothing anyone can measure.
LOOSE_SCROLLER_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='loose' class='scroll' style='width: 300px; overflow-x: auto'>"
    "<div id='far' style='width: 700px; text-align: right'>A row wider than the box "
    "that scrolls it.</div></div>"
    "<div id='held' class='scroll' style='width: 300px; overflow-x: auto; position: relative'>"
    "<div style='width: 700px'>The same row, in a box that holds its own.</div></div>"
    "\n</main>",
)
# A box the page's own stylesheet makes scroll, standing in content the browser skips
# until it is shown: a closed disclosure, and a tab not chosen (`hidden="until-found"`).
# Each record is the page and the press that shows the box.
HIDDEN_SCROLLER_STYLE = """<style>
#unfolded { width: 240px; overflow-x: auto; }
.row { width: 700px; }
</style>"""
HIDDEN_SCROLLER_ROW = (
    '<div id="unfolded" class="scroll"><div class="row">A row wider than the box that scrolls it.'
    "</div></div>"
)
HIDDEN_SCROLLERS = {
    "disclosure": (
        leaf_page(
            "folded-scroller",
            f"""
<h1 id="t">Folded scroller</h1>
<details id="folded"><summary>Folded</summary>
{HIDDEN_SCROLLER_ROW}
</details>
""",
            head=HIDDEN_SCROLLER_STYLE,
        ),
        lambda page: page.locator("#folded > summary").click(),
    ),
    "tab": (
        leaf_page(
            "tabbed-scroller",
            f"""
<h1 id="t">Tabbed scroller</h1>
<lf-tabs id="views">
  <lf-tab id="tab-first" label="First"><p id="p-first">The tab shown first.</p></lf-tab>
  <lf-tab id="tab-wide" label="Wide">{HIDDEN_SCROLLER_ROW}</lf-tab>
</lf-tabs>
""",
            head=HIDDEN_SCROLLER_STYLE,
        ),
        lambda page: page.get_by_role("tab", name="Wide", exact=True).click(),
    ),
}
SCROLLED_CONTAINER = LONG_PAGE.replace(
    "</main>",
    "<div id='rolled' style='width: 300px; overflow-x: auto; padding-bottom: 15px'>"
    "<div id='riding' style='width: 900px'>Where the content of a scrolled box "
    "starts.</div></div>\n</main>",
)
# One obligation, so a page has something On me.
ONE_OBLIGATION = (
    '<lf-ask id="go-decision"><h2>Ship it?</h2>'
    '<lf-options id="go" choose>'
    '<lf-option id="go-yes"><strong>Yes</strong></lf-option>'
    '<lf-option id="go-no"><strong>No</strong></lf-option>'
    "</lf-options></lf-ask>"
)


def with_one_obligation(html):
    """The page with `ONE_OBLIGATION` at the foot of its main, where it moves nothing above it."""
    assert html.count("</main>") == 1, (
        "the fixture has no single main to add the obligation to"
    )
    return html.replace("</main>", ONE_OBLIGATION + "</main>")


def toggle_queue(page, open=True):
    """Open the panel's On me view from its mark, or close it from the same seat, where
    its ✕ stands while the view does, and wait for it to stand or go."""
    page.locator(".lf-fp-on-user" if open else ".lf-fp-close").click()
    panel_settled(page, open=open, view="queue" if open else None)


# Enough code for the colors to differ from each other and from the block: a comment, a
# keyword, a string, a name, a number.
CODE_BLOCK = """<pre id="snippet"><code class="language-python"># the ceiling doubles per approval
def ceiling(limit, approvals):
    return "over" if approvals > 12 else limit
</code></pre>"""

# A color that reads on the block and not on the tint one of its lines wears. The clean
# line comes first on purpose: a gate that stopped at a color's first span would take that
# line's reading, which clears the threshold, and never reach the one two lines down, and
# a walkthrough's hi band is the surface where a code line is most often set on something
# other than --pre-bg.
TINTED_CODE = """<lf-code id="tinted" language="python" hi="2"><pre>
first = "on the block's own colour"
second = "on the band"
</pre></lf-code>"""

# The same reading, in a shadow tree. lf-diff renders the page's words into one, so its
# spans are in no document.querySelectorAll. The fault page changes only its number color,
# so that color's finding and the population assertion prove the probe crossed the root.
# The token is what goes back rather than a rule: a custom property inherits through the
# boundary where a selector does not, which is both why this reaches the spans and why a
# project's own palette reaches them too, gate or no gate.
SHADOWED_DIFF_BODY = """<lf-diff id="{id}"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,2 +1,3 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals > 12 else limit
</pre></lf-diff>"""
SHADOWED_DIFF = SHADOWED_DIFF_BODY.format(id="shadowed") + "\n</main>"

# Palette overrides cross native theme spans and shadow boundaries. A comment using
# the surrounding ink is a valid theme choice; faint keywords, tinted strings and a
# dark diff's numbers still need contrast findings. The later function name has the
# same native style and background as its earlier readable control but inherits faint
# ink. The media query keeps fixed fault colors out of the dark control half.
CODE_FAULT_PAGE = LONG_PAGE.replace(
    "</head>",
    """<style>
#shadowed { --syn-number: #1c1b18; }
@media (prefers-color-scheme: light) {
  #snippet { --syn-comment: var(--code-ink); }
  #snippet { --syn-keyword: #8b8577; }
  #snippet-faint-name { --syn-name: #8b8577; }
  #tinted { --hi-tint: #6f6a60; }
}
</style>
</head>""",
).replace(
    "</main>",
    CODE_BLOCK
    + CODE_BLOCK.replace('id="snippet"', 'id="snippet-faint-name"')
    + TINTED_CODE
    + SHADOWED_DIFF_BODY.format(id="shadowed")
    + "\n</main>",
)

# The shipped dark comment ink must clear the add-line tint behind it. A large real patch
# put enough comments on that surface for the former 4.4:1 contrast gap to become visible.
CODE_CONTROL_PAGE = LONG_PAGE.replace(
    "</main>",
    CODE_BLOCK + SHADOWED_DIFF_BODY.format(id="default-shadow") + "\n</main>",
)
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
# pressing nothing at all, the shape of vacuous pass AGENTS.md is about. A link is a
# user's control and its press is a scroll, so it belongs to the set above and has
# nothing here to disturb.
PRESS = "[data-lf-offer], [role=tab], [role=button], .lf-btn, .lf-pick, button, summary"

# The controls a press is aimed *past*: the ones sharing its row, standing on the same
# line, and rendered at both ends of the gesture. A target margin entry's row is its cluster;
# contribution and options wrappers do not split the visible row. The playground's action
# group can wrap in a narrow rail, but its controls still share that group. Other controls
# use their parent. Hold identity across the press and measure on the screen: moving
# the containing row carries every neighbour out from under the user's aim too.
#
# Being rendered is the load-bearing half. A control inside a fold the press opens was nowhere
# the user could aim, and one the press puts away — a suggestion's ✗ Reject, once ✓
# Accept has settled the pair — is not a control that moved. Both are the press doing what
# it was pressed for. `[hidden]` is asked separately because hidden="until-found", which is
# what a folded region wears, measures zero and still reports itself visible.
RENDERED = "(n) => n.checkVisibility() && !n.closest('[hidden]') && n.offsetWidth > 0"
NAMED = browser_function("control_name.js", "named")
NEIGHBOURHOOD = f"""(el, sel) => {{
  const band = el.getBoundingClientRect();
  const sameLine = (n) => {{
    const r = n.getBoundingClientRect();
    return Math.min(r.bottom, band.bottom) - Math.max(r.top, band.top) > 1;
  }};
  window.__lfRendered = {RENDERED};
  const cluster = el.closest('.lf-margin-cluster, .lf-diff-file, .lf-playground-actions');
  const candidates = cluster ? [...cluster.querySelectorAll(sel)]
      : [...el.parentElement.children]
          .filter((n) => n !== el && !n.contains(el))
          .flatMap((n) => (n.matches(sel) ? [n] : [...n.querySelectorAll(sel)]));
  window.__lfNeighbours = candidates
      .filter((n) => n !== el && !n.contains(el) && !el.contains(n))
      .filter((n) => window.__lfRendered(n) &&
          (cluster?.matches('.lf-playground-actions') || sameLine(n)));
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# The same capture, of the floating panel rather than of one control's line: every
# control the chrome is showing, held by identity so the news can rewrite their words
# without changing who they are.
CHROME_WATCH = f"""(sel) => {{
  window.__lfRendered = {RENDERED};
  window.__lfNeighbours = [...document.querySelector(".lf-floating-panel")
      .querySelectorAll(sel)].filter(window.__lfRendered);
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# One reading, named once, so the rendered-frame wait and the assertion cannot measure
# differently. The words ride along so `displaced` can tell a box whose own content
# changed from one that was pushed. Read every dimension from the screen rectangle;
# ancestor movement and transforms are part of what the user sees, not an origin to
# subtract. A rendered control carried beyond the viewport still moved.
DEFINE_BOXES = """() => { window.__lfBoxes = () => window.__lfNeighbours.map(
    (n) => {
      if (!window.__lfRendered(n)) return null;
      const box = n.getBoundingClientRect();
      return [Math.round(box.left), Math.round(box.top),
              Math.round(box.width), Math.round(box.height),
              (n.textContent || '').trim()];
    }); }"""


def unfolded_button(control):
    """Return a secondary margin entry, opening `…` only for a larger peer set.

    A single peer is already visible. In either posture the contribution's real
    control stays with its owner and the visible proxy forwards the user's press.
    Asking this helper for a primary still fails: it has no secondary proxy.
    """
    item = control.locator(
        "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '),"
        " ' lf-margin-cluster ')][1]"
    )
    more = item.locator(":scope > .lf-margin-more")
    if more.is_visible():
        more.click()
    options = item.locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    return options.get_by_role(
        "button", name=control.get_attribute("aria-label"), exact=True
    )


def page_at_rest(page):
    """Render the known edge, finish finite motion, then render its ending."""
    rendered(page)
    render_checks_model.wait_for_probe(page, "pageSettled")
    rendered(page)


def displaced(before, boxes, news=False):
    """Which of the watched controls are somewhere else, in the failure's own words.

    A control that is hidden or removed reads None and is left out: it was put away
    rather than moved, which is a thing both sweeps below deliberately allow.

    `news` reads the rule for a change nobody gestured (`browser/AGENTS.md`,
    "Stability"): a box whose own words changed may grow or shrink into free room, so its
    width is its own, but its place is not, and no other box may move or resize. The
    free room may lie on either side: a box packed against the run to its right grows
    leftward into the room before it, and the edge that holds still is its place. A box that grew by pushing its neighbours still fails, as
    they do."""

    def moved(was, now):
        if now is None:
            return False
        if news and was[4] != now[4]:
            held = was[0] == now[0] or was[0] + was[2] == now[0] + now[2]
            return not held or was[1] != now[1] or was[3] != now[3]
        return any(a != b for a, b in zip(was[:4], now[:4], strict=True))

    return [
        f"{name} moved by "
        f"{[round(a - b, 1) for a, b in zip(now[:4], was[:4], strict=True)]} (left, top, width, height)"
        for name, was, now in zip(before["names"], before["boxes"], boxes, strict=True)
        if moved(was, now)
    ]


def aim_targets(page_dir):
    """Everything an ⌥-press can land on that something is waiting to answer.

    Every control however its widget built one, and every element of the vocabulary,
    whose handlers sit on the widget rather than on a control — an option is picked by
    clicking its prose. The vocabulary is read from the page's own registry rather than
    listed, so the twelfth widget is swept by existing. Prose has no handler at all, so
    one press into it proves what fifty would."""
    tags = ", ".join(element_declarations(registry_storage.load_registry(page_dir)))
    return f":is({PRESS}, {tags}):not(.lf-chrome *)"


# Where in a target to aim, asked of the rendered page rather than assumed: near its
# leading corner, since the middle of a container is usually one of its children, and only
# where the point is really the target's — an element under the panel or clipped to
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
# layer carries the aimed element's id (data-for, refreshAim's one write of it). The
# composer's own mark then stands on that same item once the press is made, so the box's
# answer before the press and the draft's after it agreeing is the promise being kept.
AIMED = """() => document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null"""
# The item the draft stands on, which is not always the element wearing the outline: a
# mark hangs on the boxes its element shows through, and a display: contents wrapper shows
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
# and a clock is not a press: lf-test-worker's elapsed line re-renders on every poll, so the
# minute turning during a long sweep read as a press that had reached a widget. What the
# check is for survives untouched — a stray pick writes `chosen` on the option and a
# stray tab switch moves the panels' attributes, both of them authored rather than
# generated, and structure is compared either way.
# The page as a press leaves it. Where the pointer is resting, the projection Leaf
# paints above descendants, and the generated binding seat are not authored state,
# so none belongs in this reading.
PAGE_MARKUP = r"""() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => {
        const c = n.cloneNode(true);
        for (const g of c.querySelectorAll("[data-lf-gen]")) g.textContent = "";
        if (c.dataset && c.dataset.lfGen !== undefined) c.textContent = "";
        for (const el of [c, ...c.querySelectorAll("*")]) {
            el.classList?.remove("lf-mark-hover", "lf-projected-mark", "lf-binding-seat");
            // Anchor naming is presentation state. The layout may copy a name
            // from a stylesheet into inline style while positioning a comment.
            el.style?.removeProperty("anchor-name");
            if (!el.getAttribute("style")) el.removeAttribute("style");
        }
        return c.outerHTML;
    })
    .join("").replaceAll(' class=""', "")"""
# Every legend box stands on its addressable element: same corner, one pixel out, for every element wholly
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
<lf-ask id="cards-decision"><h2>Which card?</h2>
<lf-options id="cards" choose>
  <lf-option id="card-plain"><strong>Plain</strong> The first card's argument.</lf-option>
  <lf-option id="card-star" ><strong>Starred</strong> A border already the accent.</lf-option>
</lf-options></lf-ask>
<lf-ask id="rows-decision"><h2>Should we ship?</h2>
<lf-options id="rows" choose>
  <lf-option id="row-ship">Ship it as is</lf-option>
  <lf-option id="row-hold">Hold for the backfill</lf-option>
</lf-options></lf-ask>
""",
)
# Two items meeting at a seam the browser puts between two whole pixels, held there by a
# fixed box rather than by flow, so the fraction is the stylesheet's number on every
# machine instead of whatever the fonts above it came to. Here the seam falls at .31 of a
# pixel, so a pointer just below it is over the lower item and rounds to a whole pixel
# over the upper one, which is the disagreement AIM_SEAM below goes looking for.
AIM_SEAM_PAGE = leaf_page(
    "aim seam",
    """
<h1 id="t">Aim seam</h1>
<div id="seam-stack">
  <p id="seam-upper">The item above the seam.</p>
  <p id="seam-lower">The item below the seam.</p>
</div>
""",
    head="""<style>
  #seam-stack { position: fixed; top: 300.3px; left: 40px; width: 220px; }
  #seam-stack > p { margin: 0; height: 20px; }
</style>""",
)
# Where the browser's own hit test stops answering the upper item and starts answering the
# lower one, and a point beside that seam whose whole-pixel rounding lands on the other
# side of it. The rounding is not this reading's invention: `mousemove` carries clientX and
# clientY rounded to whole pixels, so a pointer record kept from one answers about a place
# the pointer is not, while the press is dispatched against the position it was rounded
# from. The seam is searched for rather than computed, because a box's hit region is not
# always its border box — a neighbour's hairline border hit-tests as the cell below it.
AIM_SEAM = """([above, below]) => {
  const a = document.getElementById(above), b = document.getElementById(below);
  const box = a.getBoundingClientRect();
  const x = Math.round(box.left + box.width / 2) + 0.5;
  const at = (y) => document.elementFromPoint(x, y)?.closest("[id]")?.id ?? null;
  let lo = box.top + 1, hi = b.getBoundingClientRect().bottom - 1;
  if (at(lo) !== above || at(hi) !== below) return null;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (at(mid) === above) lo = mid; else hi = mid;
  }
  // Halfway between the seam and the whole-pixel boundary rounding turns at, which puts
  // the point and its rounded twin on opposite sides of the seam. Which of them is over
  // which item follows where in the pixel the seam fell: under .5 the point is over
  // `below` and the twin over `above`, and from .5 up the two swap. So the caller reads
  // the item to hold the aim to off `at` rather than naming one, and requires the pair to
  // differ — a seam that landed on a whole pixel leaves the two agreeing and proves
  // nothing.
  const y = (hi + Math.floor(hi) + 0.5) / 2;
  return { x, y, at: at(y), rounded: at(Math.round(y)) };
}"""
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


def button_radius(page):
    """Resolve the shared margin entry corner through the page's own theme token."""
    return page.evaluate(
        """() => {
        const probe = document.createElement('span');
        probe.style.borderRadius = 'var(--r)';
        document.body.append(probe);
        const seen = getComputedStyle(probe).borderRadius;
        probe.remove();
        return seen;
    }"""
    )


def glyph_action_face(control):
    """What a user sees of a glyph action, as one reading both its tests share.

    Send and Add option are the same face: a bare glyph in the action's own ink over a
    28px disc that stays clear at rest and takes the action's tint under the pointer.
    The press paints nothing of its own in either state, so `press` is the claim that
    the disc is the whole of the paint and `discWidth` is why it does not grow with the
    hit box around it.
    """
    return control.evaluate(
        """el => {
             const press = getComputedStyle(el);
             const disc = getComputedStyle(el, '::before');
             return {
               press: press.backgroundColor,
               glyph: press.color,
               disc: disc.backgroundColor,
               discWidth: disc.width,
               discRadius: disc.borderRadius,
             };
           }"""
    )


def mark_edges(page, ident, ink, outset=None):
    """How wide the mark is painted on each side of an element, in device pixels.

    `outset` names, in CSS px, how far out from the element's edge the mark's outer
    edge stands on each side it doesn't start at the edge, as a region's ring does at
    its room (base.css); each scan then starts there and counts in.

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
    outset = outset or {}
    pad = MARK_PAD + max(outset.values(), default=0)
    box = page.locator(f"#{ident}").bounding_box()
    clip = {"x": math.floor(box["x"] - pad), "y": math.floor(box["y"] - pad)}
    clip["width"] = math.ceil(box["x"] + box["width"] + pad) - clip["x"]
    clip["height"] = math.ceil(box["y"] + box["height"] + pad) - clip["y"]
    fits = page.evaluate(
        """([x, y, w, h]) => x >= 0 && y >= 0
             && x + w <= innerWidth && y + h <= innerHeight""",
        [clip["x"], clip["y"], clip["width"], clip["height"]],
    )
    assert fits, (
        f"#{ident} is not wholly on screen with the {pad}px around it this squares "
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
    lead = {
        "top": box["y"] - clip["y"] - outset.get("top", 0),
        "left": box["x"] - clip["x"] - outset.get("left", 0),
    }
    trail = {
        "bottom": clip["y"]
        + clip["height"]
        - box["y"]
        - box["height"]
        - outset.get("bottom", 0),
        "right": clip["x"]
        + clip["width"]
        - box["x"]
        - box["width"]
        - outset.get("right", 0),
    }
    edge = {s: round(math.floor(g + 0.5) * scale) for s, g in lead.items()}
    edge |= {s: round(math.ceil(g - 0.5) * scale) for s, g in trail.items()}

    def stroke(scan, at):
        """Mark-coloured pixels contiguous with the element's edge, and no others."""
        inked = [
            all(abs(a - b) <= MARK_NEAR for a, b in zip(pixel, ink, strict=True))
            for pixel in scan
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

    columns = [
        [rgb_pixel(image, (x, y)) for y in range(height)] for x in quarters(width)
    ]
    rows = [[rgb_pixel(image, (x, y)) for x in range(width)] for y in quarters(height)]
    return {
        "top": {stroke(c, edge["top"]) for c in columns},
        "bottom": {stroke(c[::-1], edge["bottom"]) for c in columns},
        "left": {stroke(r, edge["left"]) for r in rows},
        "right": {stroke(r[::-1], edge["right"]) for r in rows},
    }


# Native values and prose paths must remain readable in a narrow column.
UNBREAKABLE_PAGE = leaf_page(
    "unbreakable",
    """
<h1 id="h">Nothing to break on</h1>
<div class="layout-tiles" id="numbers">
  <dl id="m-token" class="metric"><dt>Bucket key</dt><dd><strong>a_very_long_unbroken_identifier</strong></dd></dl>
</div>
<p id="p-token">The one it fails on is
gateway_middleware_authentication_token_bucket_refill_strategy.py, every time.</p>
<pre id="tree">
gateway/
  middleware/
    authentication/
      token_bucket_refill_strategy.py    +6 -2
</pre>
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
@@ -18 +18 @@ export function merge(base: Doc, mine: Edit[], theirs: Edit[]): Doc {
-  return apply(base, [...theirs, ...mine]);
+  const clash = theirs.find((t) =&gt; t.field === edit.field &amp;&amp; t.at &gt; edit.at);
</pre></lf-diff>
""",
)
# The same diff, arriving the other way a widget reaches a user: on a reply, into a
# column narrower than any page's.
PANEL_DIFF_MARKUP = WIDE_DIFF_PAGE[
    WIDE_DIFF_PAGE.index("<lf-diff") : WIDE_DIFF_PAGE.index("</lf-diff>")
    + len("</lf-diff>")
].replace('id="wide-diff"', 'id="rp-diff"')


def serious_axe_violations(page):
    """Serious/critical WCAG A/AA findings in accessible documents, with a report."""
    axe = Axe()
    options = {
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
        "iframes": False,
    }
    violations = [
        {**violation, "document": frame.url}
        for frame in accessible_documents(page)
        for violation in axe.run(frame, options=options).response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ]
    report = "\n\n".join(
        f"{violation['document']}: {violation['id']} ({violation['impact']}): {violation['help']}\n"
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


def accessible_documents(page):
    """The root and visible child documents Axe must inspect individually.

    Parent-to-child messages warn on sandboxed frames with opaque origins. Running
    each exposed frame directly reads it without that cross-origin message path.
    """

    def exposed(frame):
        yield frame
        for child in frame.child_frames:
            element = child.frame_element()
            if element.is_visible() and element.evaluate(
                """element => {
                  for (let current = element; current; current = current.getRootNode().host) {
                    if (current.closest('[aria-hidden="true"], [inert]')) return false;
                  }
                  return true;
                }"""
            ):
                yield from exposed(child)

    yield from exposed(page.main_frame)


# The element at an axe target's selector within one document: a list is a chain of
# shadow roots, one selector per root.
AXE_TARGET = """(selector) => {
  let el = document;
  for (const hop of [].concat(selector)) el = (el.shadowRoot ?? el).querySelector(hop);
  return el;
}"""
# Whether boxes that paint nothing are all that stand over these words: no background
# colour or image, border, shadow, or replaced content. Axe finds what stands over words
# by geometry and ignores pointer-events, so such a box hides words from it that no
# reader loses. A painted box over words, as a scroller's edge fade or a margin pin is,
# covers them for the reader too, where the layer's own rules put it.
UNDER_EMPTY_BOXES = r"""(el) => {
  const paints = (box) => {
    if (/^(img|svg|canvas|video|iframe|object|embed)$/i.test(box.localName)) return true;
    const s = getComputedStyle(box);
    const seen = (colour) => !/^(transparent|rgba\(.*,\s*0\)|color\(.* \/ 0\))$/.test(colour);
    return seen(s.backgroundColor) || s.backgroundImage !== 'none' || s.boxShadow !== 'none'
      || s.filter.includes('drop-shadow')
      || ['Top', 'Right', 'Bottom', 'Left'].some((side) =>
        parseFloat(s[`border${side}Width`]) > 0 && s[`border${side}Style`] !== 'none'
        && seen(s[`border${side}Color`]));
  };
  axe.setup();
  try {
    const over = axe.commons.dom.getTextElementStack(el).flatMap((stack) =>
      stack.slice(0, stack.indexOf(el)).filter((box) => !box.contains(el)));
    return over.length > 0 && !over.some(paints);
  } finally {
    axe.teardown();
  }
}"""


def overlapped_words(page):
    """Words axe read no contrast for because a box that paints nothing stands over them.

    Axe answers these as incomplete, not as violations, so a sweep keeping violations
    alone passes words it never measured. A window-sized transparent layer over the
    first screen hid every word under it this way (#2559). The run reads the same
    exposed documents as `serious_axe_violations`."""
    axe = Axe()
    unread = []
    for frame in accessible_documents(page):
        result = axe.run(
            frame,
            options={
                "runOnly": {"type": "rule", "values": ["color-contrast"]},
                "resultTypes": ["incomplete"],
                "iframes": False,
            },
        )
        for rule in result.response["incomplete"]:
            for node in rule["nodes"]:
                if not any(
                    isinstance(check.get("data"), dict)
                    and check["data"].get("messageKey") == "bgOverlap"
                    for check in node["any"]
                ):
                    continue
                words = node["target"]
                if frame.evaluate(
                    UNDER_EMPTY_BOXES, frame.evaluate_handle(AXE_TARGET, words)
                ):
                    unread.append(f"{frame.url}: {' >>> '.join(words)}")
    return unread


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
<lf-ask id="extras-decision"><h2>Which extras should we add?</h2>
<lf-options id="extras" choose multiple>
<lf-option id="x-tray"><lf-gloss tip="Price">£9</lf-gloss>
<strong>Seed tray</strong> Catches the spill under the south pair.
</lf-option>
<lf-option id="x-dome"><lf-gloss tip="Price">£15</lf-gloss>
<strong>Weather dome</strong> Keeps the seed dry through a wet week.
</lf-option>
</lf-options></lf-ask>
""",
)


def solid_png(width: int, height: int, rgb: tuple, patch: tuple = ()) -> bytes:
    """A solid-colour PNG, written here rather than committed, so the pair a shot
    test flips between is two files whose only difference is the one the test made.
    `patch` is `(x, y, width, height, rgb)`, a rectangle painted in another colour."""
    rows = [bytearray(bytes(rgb) * width) for _ in range(height)]
    if patch:
        x, y, w, h, colour = patch
        for row in rows[y : y + h]:
            row[x * 3 : (x + w) * 3] = bytes(colour) * w
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

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


# A module making the mistake the scaffold's own header warns about: words injected
# into the widget wearing the chrome face, with nothing said about whose they are.
# It has to be a module, because a page may not author `.lf-ui` — `reserved_marker_errors`
# refuses it at the door — and no shipped widget makes the mistake, the gate being green.
BADGE_CHROME = """      const row = document.createElement("div");
      row.className = "lf-ui";
      row.textContent = "Sent by the reviewer";
      this.append(row);"""
# A diagram body the renderer refuses outright: a family it does not implement is
# refused at the header, which is where the widget fails soft on any page, gated or not.
UNPARSABLE_DIAGRAM = LONG_PAGE.replace(
    "</main>",
    "<lf-diagram id='d-broken'><pre>\nleaf-unsupported\n  Ada,Review,3\n</pre></lf-diagram>\n</main>",
)


RINGS_DRAWN = browser_function("focus_rings.js", "ringsDrawn", using="control_name.js")
RING_CANDIDATES = browser_function(
    "focus_rings.js", "ringCandidates", using="control_name.js"
)


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
# Only a declaration that draws with the ring's own token is a ring rule: `--focus-ring`
# for an outline, `--focus-shadow` for the band cast as a shadow. A contour written out
# as `2px solid var(--accent)`, such as an element mark's pointer feedback, paints the
# same pixels and is not one.
RING_CARRIERS = {
    "outline": ("outline", "outline-style"),
    "box-shadow": ("box-shadow",),
}
RING_TOKEN = {
    "outline": re.compile(r"--focus-ring(?![\w-])"),
    "box-shadow": re.compile(r"--focus-shadow(?![\w-])"),
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
    hits, and drop the samples, ink and rectangle from each answer.

    The screenshot is taken a round trip after the reading, so a caller reads a page at
    rest (`rendered`); one still repainting can read a ring where it no longer is."""
    sampled = [seen for seen in answers if seen["runs"]]
    if sampled:
        points = [p for seen in sampled for run in seen["runs"] for p in run["points"]]
        # Whole CSS pixels, since Chrome truncates a clip to them before it scales.
        left = math.floor(min(x for x, _ in points))
        top = math.floor(min(y for _, y in points))
        clip = {
            "x": left,
            "y": top,
            "width": math.floor(max(x for x, _ in points)) + 1 - left,
            "height": math.floor(max(y for _, y in points)) + 1 - top,
        }
        image = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
        scale = image.width / clip["width"]
    for seen in answers:
        runs, ink, ring = seen.pop("runs"), seen.pop("ink"), seen.pop("ringAt")
        for run in runs:
            painted = [
                sum(
                    abs(a - b)
                    for a, b in zip(
                        rgb_pixel(
                            image,
                            (
                                min(int((x - left) * scale), image.width - 1),
                                min(int((y - top) * scale), image.height - 1),
                            ),
                        ),
                        ink,
                        strict=True,
                    )
                )
                < RUN_INK
                for x, y in run["points"]
            ]
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
