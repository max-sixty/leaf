"""Shared layout browser-integration cases and readings."""

import fcntl
import hashlib
import io
import math
import re
import struct
import zlib
from contextlib import ExitStack
from types import SimpleNamespace

import pytest
from axe_playwright_python.sync_playwright import Axe
from browser_sources import browser_function
from click.testing import CliRunner
from interact_support import record_claim, running_http_server
from leaf import cli as cli_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import machine as machine_model
from leaf import render_checks as render_checks_model
from leaf import server as server_model
from leaf import session_cleanup as cleanup_model
from leaf.registry import storage as registry_storage
from leaf.render_checks import rendered
from leaf.render_gate import scheme as render_gate_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    ASKS_PAGE,
)
from render_harness import (
    LONG_PAGE,
    SHELL_BOX,
    banner_control,
    leaf_page,
    stamp_page,
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
    is of a first visit — the thread panel shut, no drawer standing, design mode off —
    and each of those is something a user turns on once and gets back on every load
    afterwards. That left the restores as the one road onto a page with nothing
    watching it, and a drawer someone had left standing came up as a ReferenceError
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
        if message.type != "error":
            return
        target = (
            notices if render_gate_model.resize_observer_error(message.text) else errors
        )
        target.append(message.text)

    page.on("console", console_message)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    render_checks_model.install_window_errors(page)
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
            + ("; ".join([*errors, *notices]) or "and no console error says why")
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
                + ("; ".join([*errors, *notices]) or "and no console error says why")
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
    its reason: the banner's dot pulses for as long as the tab is open, and something
    that never ends never arrived anywhere. An unbounded iteration count cannot cross
    JSON, so the browser omits it, and that omission is the reading.

    A target is a backend node id, and the same drawer over two loads is two of them,
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
# shadow root hides. The markup then holds every word the entry promised and the user
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

# A block wider than the column and narrower than the window: 70% of 1200px is
# 840px against a 720px column, so it stands 120px out in the margin with
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
# resident holds — every one of which inherits the box its parent put out there. The
# compact posture has no margin for these synthetic residents, so it removes them.
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
# A scroller the page wrote and did not position, beside one it did. The commented
# words stand at the far end of the first, since a word laid out against the page from
# the near end lands inside the window and escapes nothing anyone can measure.
LOOSE_SCROLLER_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='loose' style='width: 300px; overflow-x: auto'>"
    "<div id='far' style='width: 700px; text-align: right'>A row wider than the box "
    "that scrolls it.</div></div>"
    "<div id='held' style='width: 300px; overflow-x: auto; position: relative'>"
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
    '<div id="unfolded"><div class="row">A row wider than the box that scrolls it.'
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
    "<div id='rolled' style='width: 300px; overflow-x: auto'>"
    "<div id='riding' style='width: 900px'>Where the content of a scrolled box "
    "starts.</div></div>\n</main>",
)
# The two edges the user draws, and what a reading of either has to know: a page that
# offers the region, what puts it up, the region's own selector, which side of the window
# it is held to, and the numbers the runtime holds it to. Two records rather than two
# tests, because the whole claim of `drawnEdge` is that the two are one piece of furniture
# reflected — a reading written for the panel alone would go on passing on the day the
# drawer's edge stopped working, and the drawer's edge exists precisely because the panel's
# did not have to be written a second time.
#
# `html` is a call rather than the markup, because the page the drawers need is declared
# with the other drawer readings a long way below here, and a parametrize list is read at
# import. `squeeze` is the
# window that has no room for what the user chose and the width the region stands at
# there, which is the window itself on either side.
EDGES = [
    SimpleNamespace(
        name="comments",
        html=lambda: LONG_PAGE,
        comments=1,
        stand=lambda page: page.locator(".lf-threads-toggle").click(),
        region=".lf-thread-panel",
        side="right",
        store="lf-thread-panel-width",
        wide=420,
        squeeze=(500, 500),
    ),
    SimpleNamespace(
        name="drawers",
        html=lambda: ASKS_PAGE,
        comments=0,
        stand=lambda page: banner_control(page, ".lf-asks").click(),
        region=".lf-asks-panel",
        side="left",
        store="lf-drawer-slot-width",
        wide=300,
        squeeze=(400, 400),
    ),
]
EDGE_IDS = [edge.name for edge in EDGES]


# One Ask, so a page offers the Asks drawer.
ONE_ASK = (
    '<lf-ask id="go-decision"><h2>Ship it?</h2>'
    '<lf-options id="go" choose>'
    '<lf-option id="go-yes"><strong>Yes</strong></lf-option>'
    '<lf-option id="go-no"><strong>No</strong></lf-option>'
    "</lf-options></lf-ask>"
)


def with_one_ask(html):
    """The page with `ONE_ASK` at the foot of its main, where it moves nothing above it."""
    assert html.count("</main>") == 1, (
        "the fixture has no single main to add the Ask to"
    )
    return html.replace("</main>", ONE_ASK + "</main>")


def toggle_asks(page, open=True):
    """Open or close the Asks drawer from its banner control and wait for it to stand."""
    banner_control(page, ".lf-asks").click()
    drawer = expect(page.locator(".lf-asks-panel"))
    opened = re.compile(r"\bopen\b")
    if open:
        drawer.to_have_class(opened)
    else:
        drawer.not_to_have_class(opened)


def edge_settled(page, edge):
    """Wait for the region to stand, including its own arrival slide.

    The page makes room for it in the same pass as the state change, so the page needs
    no wait; the region's slide is the one motion left, and a geometry read during it is a
    read of a box still under a presentation offset. It is finished rather than waited
    out, because it is presentation over a layout the gesture already installed and
    finishing is the only thing that terminates when a test is holding the clock still.
    Polling, because the slide starts inside the gesture's own task and a finished fill
    leaves `getAnimations` a turn later.
    """
    expect(page.locator(edge.region)).to_be_visible()
    page.wait_for_function(
        """(region) => {
          const box = document.querySelector(region);
          for (const move of box.getAnimations()) move.finish();
          return box.getAnimations().length === 0;
        }""",
        arg=edge.region,
    )


def geometry(page, edge):
    """What the edge reads back as, and what the page has left beside it.

    The region stands over the page, so the page's edge is the window's whatever width
    the user draws the region to.
    """
    return page.evaluate(
        """([region, side, store]) => {
            const box = document.querySelector(region).getBoundingClientRect();
            const shell = """
        + SHELL_BOX
        + """;
            return {
                width: Math.round(box.width),
                edge: Math.round(side === 'right' ? box.left : box.right),
                page: Math.round(side === 'right' ? shell.right : shell.left),
                chosen: localStorage.getItem(store),
            };
        }""",
        [edge.region, edge.side, edge.store],
    )


def draw_edge(page, edge, by):
    """Draw the region's edge `by` pixels wider, as a hand on it would.

    Whole pixels, per `hold_selection`'s reason: a press on a fractional point
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


# Enough code for the roles to differ from each other and from the block: a comment, a
# keyword, a string, a name, a number.
CODE_BLOCK = """<pre id="snippet"><code class="language-python"># the ceiling doubles per approval
def ceiling(limit, approvals):
    return "over" if approvals > 12 else limit
</code></pre>"""

# A role that reads on the block and not on the tint one of its lines wears. The clean
# line comes first on purpose: a gate that stopped at a role's first span would take that
# line's reading, which clears the threshold, and never reach the one two lines down, and
# a walkthrough's hi band is the surface where a code line is most often set on something
# other than --pre-bg.
TINTED_CODE = """<lf-code id="tinted" language="python" hi="2"><pre>
first = "on the block's own colour"
second = "on the band"
</pre></lf-code>"""

# The same reading, in a shadow tree. lf-diff renders the page's words into one, so its
# spans are in no document.querySelectorAll. The fault page changes only its number role,
# so that role's finding and the population assertion prove the probe crossed the root.
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

# These bugs go back as CSS, which is the shape the regressions take for real: the
# attribute lands either way, and it is the stylesheet answering it that stops working.
# Each uses a different role, so one public-gate reading still attributes the faults
# independently. The media query keeps fixed fault colours out of the dark control half.
CODE_FAULT_PAGE = LONG_PAGE.replace(
    "</head>",
    """<style>
#shadowed { --syn-number: #1c1b18; }
@media (prefers-color-scheme: light) {
  #snippet [data-lf-syn="cm"] { color: inherit; }
  #snippet [data-lf-syn="kw"] { color: #8b8577; }
  #tinted { --hi-tint: #6f6a60; }
}
</style>
</head>""",
).replace(
    "</main>",
    CODE_BLOCK + TINTED_CODE + SHADOWED_DIFF_BODY.format(id="shadowed") + "\n</main>",
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
# line, and on screen at both ends of the gesture. A target margin entry's row is its cluster;
# contribution and options wrappers do not split the visible row. The playground's action
# group can wrap in a narrow rail, but its controls still share that group. Other controls
# use their parent. Hold identity across the press, and measure relative to the group:
# content above may move the whole row without moving a neighbour within it.
#
# On screen is the load-bearing half. A control inside a fold the press opens was nowhere
# the user could aim, and one the press puts away — a suggestion's ✗ Reject, once ✓
# Accept has settled the pair — is not a control that moved. Both are the press doing what
# it was pressed for. `[hidden]` is asked separately because hidden="until-found", which is
# what a folded region wears, measures zero and still reports itself visible.
ON_SCREEN = "(n) => n.checkVisibility() && !n.closest('[hidden]') && n.offsetWidth > 0"
NAMED = browser_function("control_name.js", "named")
NEIGHBOURHOOD = f"""(el, sel) => {{
  const band = el.getBoundingClientRect();
  const sameLine = (n) => {{
    const r = n.getBoundingClientRect();
    return Math.min(r.bottom, band.bottom) - Math.max(r.top, band.top) > 1;
  }};
  window.__lfOnScreen = {ON_SCREEN};
  const cluster = el.closest('.lf-margin-cluster, .lf-diff-file, .lf-playground-actions');
  window.__lfOrigin = cluster || el.parentElement;
  const candidates = cluster ? [...cluster.querySelectorAll(sel)]
      : [...el.parentElement.children]
          .filter((n) => n !== el && !n.contains(el))
          .flatMap((n) => (n.matches(sel) ? [n] : [...n.querySelectorAll(sel)]));
  window.__lfNeighbours = candidates
      .filter((n) => n !== el && !n.contains(el) && !el.contains(n))
      .filter((n) => window.__lfOnScreen(n) &&
          (cluster?.matches('.lf-playground-actions') || sameLine(n)));
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# The same capture, of the banner rather than of one control's line: every control the
# chrome is showing, held by identity so the news can rewrite their words without
# changing who they are.
BANNER_WATCH = f"""(sel) => {{
  window.__lfOnScreen = {ON_SCREEN};
  window.__lfOrigin = null;
  window.__lfNeighbours = [...document.querySelector(".lf-banner").querySelectorAll(sel)]
      .filter(window.__lfOnScreen);
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# One reading, named once, so the rendered-frame wait and the assertion cannot measure
# differently. The words ride along so `displaced` can tell a box whose own content
# changed from one that was pushed.
DEFINE_BOXES = """() => { window.__lfBoxes = () => window.__lfNeighbours.map(
    (n) => {
      if (!window.__lfOnScreen(n)) return null;
      const box = n.getBoundingClientRect();
      const origin = window.__lfOrigin?.getBoundingClientRect();
      return [Math.round(box.left - (origin?.left || 0)),
              Math.round(box.top - (origin?.top || 0)),
              n.offsetWidth, n.offsetHeight, (n.textContent || '').trim()];
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


# The banner's controls in their one ranked order: fixed secondary menu seats followed
# by the primary row. The door itself and controls the page has taken away are omitted.
BANNER_ORDER = """() => {
  const toolbar = document.querySelector('.lf-banner-actions');
  const menu = document.querySelector('.lf-banner-menu');
  const more = document.querySelector('.lf-banner-more');
  return [...menu.children, ...toolbar.children]
    .filter(control => control !== more &&
            getComputedStyle(control).display !== 'none' &&
            getComputedStyle(control).visibility !== 'hidden')
    .map(control => (control.getAttribute('aria-label') || control.textContent).trim());
}"""


def page_at_rest(page):
    """Render the known edge, finish finite motion, then render its ending."""
    rendered(page)
    render_checks_model.wait_for_probe(page, "pageSettled")
    rendered(page)


def displaced(before, boxes, news=False):
    """Which of the watched controls are somewhere else, in the failure's own words.

    A control that has gone off screen reads None and is left out: it was put away
    rather than moved, which is a thing both sweeps below deliberately allow.

    `news` reads the rule for a change nobody gestured (`skills/leaf/assets/AGENTS.md`,
    "Stability"): a box whose own words changed may grow or shrink into free room, so its
    width is its own, but its place is not, and no other box may move or resize. A box
    that grew by pushing its neighbours still fails, as they do."""

    def moved(was, now):
        if now is None:
            return False
        grew = news and was[4] != now[4]
        return any(
            a != b
            for i, (a, b) in enumerate(zip(was[:4], now[:4]))
            if not (grew and i == 2)
        )

    return [
        f"{name} moved by "
        f"{[round(a - b, 1) for a, b in zip(now[:4], was[:4])]} (left, top, width, height)"
        for name, was, now in zip(before["names"], before["boxes"], boxes)
        if moved(was, now)
    ]


def aim_targets(page_dir):
    """Everything an ⌥-press can land on that something is waiting to answer.

    Every control however its widget built one, and every element of the vocabulary,
    whose handlers sit on the widget rather than on a control — an option is picked by
    clicking its prose. The vocabulary is read from the page's own registry rather than
    listed, so the twelfth widget is swept by existing. Prose has no handler at all, so
    one press into it proves what fifty would."""
    tags = ", ".join(
        t for t in registry_storage.load_registry(page_dir) if not t.startswith("$")
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
# and a clock is not a press: lf-agent's elapsed line re-renders on every poll, so the
# minute turning during a long sweep read as a press that had reached a widget. What the
# check is for survives untouched — a stray pick writes `chosen` on the option and a
# stray tab switch moves the panels' attributes, both of them authored rather than
# generated, and structure is compared either way.
# The page as a press leaves it. Where the pointer is resting and the projection Leaf
# paints above descendants are not authored state, so neither belongs in this reading.
PAGE_MARKUP = r"""() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => {
        const c = n.cloneNode(true);
        for (const g of c.querySelectorAll("[data-lf-gen]")) g.textContent = "";
        if (c.dataset && c.dataset.lfGen !== undefined) c.textContent = "";
        for (const el of [c, ...c.querySelectorAll("*")]) {
            el.classList?.remove("lf-mark-hover", "lf-projected-mark");
            // The name a margin row anchors by, which the layout writes on whatever
            // target a row comes to stand by, on its own schedule rather than a press's.
            if (el.style?.anchorName) {
                el.style.anchorName = el.style.anchorName.split(",")
                    .map((name) => name.trim())
                    .filter((name) => !/^--lf-a\d+$/.test(name)).join(", ");
                if (!el.getAttribute("style")) el.removeAttribute("style");
            }
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
  // The open thread panel stands over the right of the page, and a box is drawn for
  // what the page shows of its item, which ends at the panel's edge.
  const panel = document.querySelector('.lf-thread-panel');
  if (panel?.open) {
    const edge = panel.getBoundingClientRect().left;
    r = { left: r.left, top: r.top, height: r.height,
          width: Math.min(r.right, edge) - r.left };
  }
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
    fixture, because a drawer is a list and a walk down it needs somewhere to walk to."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    servers = ExitStack()
    held = []

    def go(name, title):
        d = machine_model.state_home() / "pages" / name
        result = CliRunner().invoke(cli_model.cli, ["page", "init", str(d)])
        assert result.exit_code == 0, result.output
        stamp_page(
            d,
            LONG_PAGE.replace("<title>long</title>", f"<title>{title}</title>"),
            "t",
        )
        cleanup_model.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "running the suite",
                "ts": cleanup_model.now_iso(),
            },
        )
        # A live leaf has a session behind it, and what the drawer's hover says about a
        # page is the work that session is doing it for — so the fixture's pages come
        # out of somewhere nameable rather than out of nowhere.
        record_claim(
            d,
            id=f"s-{name}",
            cwd=str(tmp_path / f"{name}-work"),
        )
        # Served under the machine's key, which the URL its neighbours link to
        # carries (`server.running_server`), as a real server is.
        httpd = hosting_model.LeafHTTPServer(
            ("127.0.0.1", 0), http_model.page_endpoint(d, server_model.host_key())
        )
        servers.enter_context(running_http_server(httpd))
        port = httpd.server_address[1]
        # Desired address and a held, contentless lease are the two facts a real
        # server exposes to neighbouring pages.
        cleanup_model.write_json(
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
    servers.close()
    for lease in held:
        lease.close()


@pytest.fixture
def other_leaf(live_leaf):
    return live_leaf("other", "The other leaf")


# Twenty-four things waiting, which is more than any shipped example asks and the point: the
# room a list reserves at its foot is invisible until the list is longer than the drawer.
MANY_ASKS_PAGE = leaf_page(
    "many decisions",
    """
<h1>Many decisions</h1>
<p>A drawer long enough to scroll.</p>
<lf-tasks id="plan">
"""
    + "\n".join(
        f'<lf-task id="t-{i}" status="review" owner="wren">'
        f"<strong>Waiting on you, item {i}</strong>"
        f'<lf-ask id="t-{i}-decision"><h2>Decision {i}</h2>'
        f'<lf-options id="t-{i}-choice" choose>'
        f'<lf-option id="t-{i}-yes"><strong>Approve</strong></lf-option>'
        f'<lf-option id="t-{i}-no"><strong>Request changes</strong></lf-option>'
        f"</lf-options></lf-ask></lf-task>"
        for i in range(24)
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
<div class="layout-tiles" id="numbers">
  <lf-metric id="m-token" value="a_very_long_unbroken_identifier">Bucket key</lf-metric>
</div>
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
    # The adapter injects only its document. Install axe in child documents too,
    # then let axe's frame traversal preserve the parent's accessibility boundary
    # and inspect exposed child documents without auditing hidden placeholders.
    axe = Axe()
    for frame in page.frames:
        frame.evaluate(axe.axe_script)
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
    }
    result = axe.run(page, options=options)
    violations = [
        {**violation, "document": page.url}
        for violation in result.response["violations"]
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
<lf-option id="x-tray"><lf-chip>£9</lf-chip>
<strong>Seed tray</strong> Catches the spill under the south pair.
</lf-option>
<lf-option id="x-dome"><lf-chip tone="ok">£15</lf-chip>
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


# A painted fact whose spoken copy is on the page and drawn nowhere. It is written into
# the markup because the gate reads the rendered page and cannot tell who suppressed
# the word. `kind` is x-paints, so the runtime writes a
# .lf-quiet span beside each of these; the style takes the box off both. One stands in
# the open and one behind a disclosure the user has not opened.
PAINTED_IN_SILENCE_PAGE = leaf_page(
    "silence",
    """
<h1 id="h">Transport</h1>
<lf-chronology id="open-group">
  <lf-chronology-entry id="p-seen" at="09:12" kind="failure"><strong>Feed stopped</strong></lf-chronology-entry>
</lf-chronology>
<details id="folded">
  <summary>Weighed in March</summary>
  <lf-chronology id="folded-group">
    <lf-chronology-entry id="p-folded" at="10:20" kind="failure"><strong>Feed stopped</strong></lf-chronology-entry>
  </lf-chronology>
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
# A diagram body the renderer refuses outright: a family it does not implement is
# refused at the header, which is where the widget fails soft on any page, gated or not.
UNPARSABLE_DIAGRAM = LONG_PAGE.replace(
    "</main>",
    "<lf-diagram id='d-broken'><pre>\nsankey-beta\n  Ada,Review,3\n</pre></lf-diagram>\n</main>",
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


RING_NAMES = browser_function("focus_rings.js", "ringNames", using="control_name.js")


RINGS_DRAWN = browser_function("focus_rings.js", "ringsDrawn", using="control_name.js")


COVERED_TOP = """() => {
  const el = document.activeElement;
  const box = document.querySelector('.lf-threads');
  if (!el || !box.contains(el)) return null;
  const r = el.getBoundingClientRect();
  const top = box.getBoundingClientRect().top + box.clientTop;
  if (r.top >= top - 0.5) return null;
  return `the list's top edge cuts it ${Math.round(top - r.top)}px in`;
}"""


def rings_drawn(page):
    """Every focus ring the page is drawing, each with what is wrong with it."""
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
