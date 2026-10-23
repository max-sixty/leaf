"""Control stability, browser shell, accessibility, and ring tests."""

import re
import socket
from urllib.parse import parse_qs, urlsplit

import pytest
from browser.threads import open_panel_thread
from interact_support import (
    append_carried_log_record,
    declare,
    record_claim,
    wait_for,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_layout import (
    DEFINE_BOXES,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    SHOT_SRC,
    SHOTS,
    displaced,
    overlapped_words,
    page_at_rest,
    ring_faults,
    rings_drawn,
    serious_axe_violations,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    _publish,
)
from render_harness import (
    BOARD_PAGE,
    EXAMPLES,
    FEATURE_GALLERY,
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    RELEASE_FOCUS,
    ROOT,
    CutOff,
    Traffic,
    _until,
    any_draft_control,
    held_frames,
    holding,
    leaf_page,
    open_page,
    open_versions,
    opened_tab,
    page_comment,
    panel_field,
    panel_menu,
    panel_settled,
    resized,
    root_overflow,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    told,
    write,
)

from journeys import expect_panel_says, panel_says
from leaf import event_log as events_model
from leaf import hosting as hosting_model
from leaf import presence as presence_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.schema import SERVICE_FILE

pytestmark = pytest.mark.shifts_unsurveyed

from browser.controls import (
    LIVE_SAMPLES_PAGE,
    RING_NEW_STOP,
    SAMPLE_STARTUP_FAILURE,
)
from browser_sources import browser_function
from render_cases_layout import ring_rules
from render_harness import CORPUS_SOURCES, any_owner_entry

VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


# One practice page, for the journeys that need no second child to compare against:
# each child is a whole page to load.
LIVE_SAMPLE_PAGE = re.sub(
    r'<lf-sample id="second-practice".*?</lf-sample>\n',
    "",
    LIVE_SAMPLES_PAGE,
    flags=re.DOTALL,
)
assert "second-practice" not in LIVE_SAMPLE_PAGE


def fail_sample_startup(route):
    """The real child reports its fixture's failure over the private bridge.

    Keep native document delivery: an intercepted synthetic response has no network
    address space, so Chromium refuses its opaque origin's real loopback resources.
    """
    route.fulfill(
        status=307, headers={"Location": route.request.url + "?startup-failure"}
    )


def _sample_containment_page():
    """A host can change a distant child's view; its passage needs two scrollports."""
    return leaf_page(
        "Contained practice",
        """
<h1>Contained practice</h1>
<div id="host-controls">
  <button id="show-page" type="button">Show page conversation</button>
  <button id="show-panel" type="button">Show panel conversation</button>
  <button id="reset-child" type="button">Restart conversation</button>
  <output id="completed">0</output>
</div>
<div style="height: 1400px"></div>
<lf-sample id="practice" label="Contained conversation" window>
  <template id="practice-source" data-sample data-sample-events="history">
    <h1>Child conversation</h1>
    <div style="height: 900px"></div>
    <div id="nested-reading" style="height: 240px; overflow: auto">
      <div style="height: 900px"></div>
      <p id="destination">Nested landing target.</p>
      <div style="height: 300px"></div>
    </div>
    <div style="height: 800px"></div>
  </template>
</lf-sample>
<div style="height: 1400px"></div>
""",
        head="""
<style>#host-controls { position: fixed; top: 90px; left: 20px; z-index: 2;
  background: white; padding: 8px; }</style>
<script id="history" type="application/json">
  [{"id":"question","kind":"comment","anchor":{"section":"destination"},
    "text":"Can you check the destination?"},
   {"kind":"reply","author":"agent","parent":"question","ephemeral":true,
    "text":"Checking the nested reading region."},
   {"kind":"reply","author":"agent","parent":"question",
    "text":"The destination is inside the nested reading region.",
    "markup":"<details><summary>Read the checks</summary><p>The reading region contains the destination.</p></details>"}]
</script>
<script type="module">
  const sample = document.querySelector('#practice');
  let surface = 'page';
  let completed = 0;
  for (const button of document.querySelectorAll('#host-controls button')) {
    button.addEventListener('click', async () => {
      if (button.id === 'reset-child') await sample.reset();
      else surface = button.id === 'show-page' ? 'page' : 'panel';
      const shown = await sample.showThread('question', {surface});
      document.querySelector('#completed').textContent =
        shown ? String(++completed) : 'cancelled';
    });
  }
</script>
""".replace(
            "Checking the nested reading region.",
            "Checking the nested reading region and its surrounding reading context. "
            * 50,
        ),
    )


CONTROL_STABILITY_PAGE = leaf_page(
    "control stability",
    """
<h1 id="control-target">Control stability</h1>
<lf-suggestion id="stable-suggestion">
  <lf-old>Keep the broad sweep.</lf-old>
  <lf-new>Keep one causal case per control archetype.</lf-new>
</lf-suggestion>
<lf-ask id="stable-options-decision"><h2>Which control should stay?</h2>
<lf-options id="stable-options" choose>
  <lf-option id="stable-choice-a" for="control-target">Keep A</lf-option>
  <lf-option id="stable-choice-b" for="control-target">Keep B</lf-option>
</lf-options></lf-ask>
<lf-tabs id="stable-tabs">
  <lf-tab id="stable-tab-a" label="First">First panel.</lf-tab>
  <lf-tab id="stable-tab-b" label="Second">Second panel.</lf-tab>
</lf-tabs>

<lf-ask id="stable-playground-decision"><h2>How should the release card look?</h2>
<lf-playground id="stable-playground" submit-label="Use these settings">
  <lf-playground-control name="radius" label="Corner radius" kind="range"
    value="12" min="0" max="24" step="1" unit="px"></lf-playground-control>
  <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
    <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
    <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview id="stable-playground-preview">
    <article id="stable-playground-card"><strong>Release card</strong><p>The ceiling doubles per approval.</p></article>
  </lf-playground-preview>
  <lf-playground-output id="stable-playground-instruction">Use a
    <lf-playground-value for="radius"></lf-playground-value> corner radius and a
    <lf-playground-value for="tone"></lf-playground-value> tone.
  </lf-playground-output>
</lf-playground></lf-ask>
<lf-diff id="stable-diff"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,2 +1,3 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals &gt; 12 else limit
</pre></lf-diff>
"""
    f"""<lf-shot id="stable-shot" alt="the release card"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
""",
)


LEAVES = '.lf-fp-view[data-view="leaves"]:not([data-leaving])'


# The rendered control mechanisms whose rows must keep their geometry across a press.
# `target` is the one causal transition that proves each mechanism's stability contract.
CONTROL_ARCHETYPES = (
    {
        # Accept and Reject share the resting row. A thread adds the third margin entry that
        # puts the secondary choices behind `…`; opening it must leave Accept still.
        "name": "margin-entry",
        "target": '[data-lf-margin-for="stable-suggestion"] > .lf-margin-more',
    },
    {
        "name": "option-pick",
        "target": "#stable-choice-a .lf-pick",
    },
    {
        "name": "tab",
        "target": "#stable-tabs .lf-tab-btn:nth-child(2)",
    },
    {
        # The playground's action row: Reset, Copy instruction, and the send beside each
        # other under the controls. The send is the press with something to prove — it
        # posts the configuration and comes back disabled, and a control that changes its
        # own paint on the press is where a neighbour moves.
        "name": "playground-actions",
        "target": "#stable-playground .lf-playground-submit",
    },
    {
        # Switching views must not move the buttons under the pointer.
        "name": "shot-view",
        "target": "#stable-shot .lf-shot-views button:nth-child(2)",
    },
    {
        "name": "visual-review-inspection",
        "source": VISUAL_REVIEW_GALLERY,
        "target": '.lf-vr-case[aria-hidden="false"] .lf-shot-views button:nth-child(2)',
    },
    {
        "name": "visual-review-approval",
        "source": VISUAL_REVIEW_GALLERY,
        "target": '.lf-vr-case[aria-hidden="false"] .lf-vr-approval',
    },
)


# The panel's own controls draw the ring with one rule (floating-panel.css); this is the
# part of its selector that makes the rule the panel's.
PANEL_RING = ".lf-fp-on-item)"


# The page the chrome's surfaces are sampled on: small, with a board's grips, and served
# with a second version so the versions menu has a comparison to offer.
RING_CHROME = "triage-board"


# A causal sample in each surface the keyboard reaches. Each case names its surface, the
# real keys that open it, the element whose focus state paints the ring, and the rule
# that paints it, as the part of its matched selector that makes the rule that
# control's own (`ring_rules`, render_cases_layout.py). A null selector means the
# opening keys themselves leave the required non-focusable carrier lit.
RING_CASES = (
    (
        "the page",
        (),
        {
            # The chrome's own surfaces stand on the smallest page that offers them all,
            # since every page carries the same chrome and each reading over a large
            # document costs seconds.
            RING_CHROME: (
                (".lf-grip", ".lf-grip"),
                (".lf-fp-leaf", PANEL_RING),
                (".lf-fp-threads", PANEL_RING),
                (".lf-fp-field leaf-text", ".lf-fp-field .lf-compose-field"),
            ),
            "feature-gallery": (
                (".lf-tab-btn", ".lf-tab-btn"),
                ("lf-option > .lf-pick", "lf-option:has(> .lf-pick"),
                (
                    any_owner_entry("suggestion", "accept") + ":visible",
                    "margin-entry",
                ),
                (".lf-draft-edit", ".lf-draft-edit"),
            ),
            "heat-loss": ((".lf-visual-action", ".lf-visual-action"),),
            # Working density, where a choice's gap is narrowest beside the next face.
            "notification-playground": (
                ("lf-playground input[type=radio]", ".choice:has"),
            ),
            "review-a-plan": (
                ("main details > summary", ":where([data-lf-focus-visible])"),
            ),
            "pr-walkthrough": (
                (
                    "#pr-flow-tab",
                    ".lf-rendered:has(> :is(lf-tab, lf-part)",
                ),
                ("lf-gloss:visible > .lf-gloss-mark", ".lf-gloss-mark"),
                (".lf-diff-search input", "wa-input::part"),
                ("lf-diff summary", ".lf-diff-file > details > summary"),
                ("lf-diff code", "code[data-code]"),
            ),
            "release-notes": (
                ("main p.lf-mark-el", ".lf-mark-el"),
                (
                    'lf-shot .lf-shotcomparison [part~="handle"]',
                    "wa-comparison::part(",
                ),
                (".lf-shot-views button", "button"),
            ),
            "wt-merge": (
                (
                    '[data-lf-reading-role="pane"] > [tabindex="0"]',
                    "[data-lf-reading-role=pane]",
                ),
            ),
        },
    ),
    ("a landed diff line", ("]",), {"pr-walkthrough": ((None, "[data-line]"),)}),
    (
        "an inline response",
        (),
        {"pr-walkthrough": (("leaf-text.lf-fab-input", ".lf-response-control"),)},
    ),
    # `g T` stands in Threads, on its view, and the walk's first step lands on a row.
    (
        "the Threads view",
        ("g", "Shift+t", "ArrowDown"),
        {RING_CHROME: ((None, PANEL_RING),)},
    ),
    # A resolved thread's view, whose controls offer Reopen.
    (
        "a resolved thread",
        (),
        {"ship-review": ((".lf-fp-controls .lf-fp-settle", PANEL_RING),)},
    ),
    # The same walk with the panel shut lands in the margin's thread view, on the
    # thread itself rather than a control inside it.
    ("an inline thread", ("t",), {"ship-review": ((None, ".lf-page-thread"),)}),
    (
        "passage search",
        ("/",),
        {RING_CHROME: ((".lf-page-search-box input:visible", "wa-input::part"),)},
    ),
    # Item hints, and the anchored bar the user answers a chosen item on. Both open the
    # same mode, and both step back and then forward through it, which lands on the last
    # item the window is showing whatever a page's count is: the browse wraps, so one step
    # back from a fresh open is the second from the end. That item is the lowest on
    # screen, which is where the layer has the least room to draw a band around a chip and
    # the least room to hang a bar under one.
    #
    # The Tab in front of both sequences is a stop, not a gesture in the mode: target hints
    # claim Tab for browsing themselves, so the sample below moves nothing once the mode
    # is open, and with the document under it the sample would stand on nothing and read no
    # page at all. Standing on a control first leaves the hint the keyboard is browsing on
    # screen for the sweep, which is where its band is read — the chips are a layer nothing
    # can focus, so the user's place in that mode is not a stop.
    (
        "target hints",
        ("Tab", "s", "Shift+Tab", "Tab"),
        {RING_CHROME: ((None, ".lf-key-hint.lf-current"),)},
    ),
    # Enter opens Comment on the item the keyboard is browsing and focuses its field.
    (
        "the response bar",
        ("Tab", "s", "Shift+Tab", "Tab", "Enter"),
        {RING_CHROME: ((".lf-fab-input", ".lf-response-control"),)},
    ),
    # These controls live behind exact page-owned view states: a settled group's
    # disclosure, and the options it puts away.
    (
        "a settled decision",
        (),
        {
            "current-proposed-comparison": (
                ("#comparison-policy > .lf-settled", ".lf-settled"),
            )
        },
    ),
    (
        "a settled option",
        (),
        {
            "current-proposed-comparison": (
                (
                    "#comparison-policy > lf-option > .lf-pick",
                    ":is(lf-option) .lf-pick",
                ),
            )
        },
    ),
    (
        "a contents link",
        (),
        {"feature-gallery": (("#bg-contents li a:visible", ":is(lf-toc) a"),)},
    ),
    # The reaction palette a message's strip opens. Its chips are the last boxes the
    # layer dresses in the chrome's chip face, and they are behind a press: the strip
    # shows a token nobody has pressed only while it is open, so a walk of the panel
    # that never opens one stands on the trigger and nothing under it.
    (
        "a reaction palette",
        (),
        {
            "ship-review": (
                (".lf-react-palette:popover-open .lf-react", "[data-lf-offer]"),
            )
        },
    ),
    # On me opens on its view; the walk's first step lands on a card.
    ("On me", ("ArrowDown",), {"ship-review": ((None, PANEL_RING),)}),
    ("All pages", ("g", "Shift+l", "ArrowDown"), {RING_CHROME: ((None, PANEL_RING),)}),
    # The leaf's menu, opened by its press; the walk's step lands on a row.
    ("the leaf's menu", ("ArrowDown",), {RING_CHROME: ((None, PANEL_RING),)}),
    # The menu's Versions, which `g V` opens standing on the version being read; the
    # walk's step lands on the earlier one.
    (
        "the versions menu",
        ("g", "Shift+v", "ArrowDown"),
        {RING_CHROME: ((None, PANEL_RING),)},
    ),
    (
        "the command reference",
        ("?",),
        {
            RING_CHROME: (
                (".lf-command-reference-search input:visible", "wa-input::part"),
                (".lf-command-reference-command", ".lf-command-reference-command"),
            )
        },
    ),
    # A Thread card and the Page Map dialog are two layers a Tab walk of the page cannot
    # open for itself. The card is a press on a thread margin entry; the sheet is `g P`.
    (
        "a thread card",
        (),
        {
            "ship-review": (
                (
                    ".lf-margin-preview .lf-resolve",
                    ".lf-page-thread :is(.lf-btn, summary)",
                ),
            )
        },
    ),
    # Media in a message the panel's thread view draws wears its own ring, as on the
    # page: the panel's rule leaves what Leaf's reader draws in its outlet alone.
    (
        "message media",
        (),
        {"feature-gallery": ((f"{PANEL} .lf-message-media", ".lf-media-open"),)},
    ),
    (
        "the Page Map dialog",
        ("g", "Shift+p"),
        {
            RING_CHROME: (
                (".lf-page-map-action:visible", ".lf-page-map-action"),
                (".lf-page-map-search input:visible", "wa-input::part"),
            )
        },
    ),
)


# The selected pages jointly load the core and optional package stylesheets.
RING_EXAMPLES = tuple(
    dict.fromkeys(name for _scope, _keys, cases in RING_CASES for name in cases)
)


# Every page the Tab walk visits, of which the ring cases sample a selection.
RING_EXAMPLE_FILES = {
    example.stem: example
    for example in (
        *EXAMPLES,
        FEATURE_GALLERY,
        ROOT / "tests/fixtures/pages/current-proposed-comparison.html",
    )
}


# Rings whose carrier is semantic state elsewhere in the page rather than the focused
# control or one of its ancestors. Mark the exact carrier before reading the composed
# paint so an unrelated ring drawn by the same rule cannot credit the sample.
RING_REMOTE_CARRIER = {
    ".lf-key-hint.lf-current": ".lf-target-picker-hint.lf-current",
    # A pane draws its focused body's band inset over the body's cell (theme.css).
    "[data-lf-reading-role=pane]": '[data-lf-reading-role="pane"]:has(> [data-lf-focus])',
}


# A surface must open before its sample can count.
RING_SCOPE_SURFACE = {
    "an inline response": (
        'lf-diff .lf-fab-bar[data-lf-presentation="inline"] .lf-composer[data-lf-open]'
    ),
    "the Threads view": '.lf-floating-panel[data-open="threads"]',
    "a resolved thread": PANEL_THREAD,
    "an inline thread": ".lf-margin-preview:not([hidden])",
    "a thread card": ".lf-margin-preview:not([hidden])",
    "the Page Map dialog": ".lf-page-map-dialog[open]",
    "passage search": ".lf-page-search:not([hidden])",
    # The hint the keyboard is browsing, and the field the chosen item's bar opens with.
    # Each is the mode's own state rather than a box that merely exists: the chips are
    # rebuilt from nothing on every open, and the bar is in the document from the first
    # frame and shows only for an anchor.
    "target hints": ".lf-target-picker-hint.lf-current",
    "the response bar": ".lf-fab-bar .lf-composer[data-lf-open]",
    "On me": '.lf-floating-panel[data-open="queue"]',
    "All pages": '.lf-floating-panel[data-open="leaves"]',
    "the leaf's menu": ".lf-floating-panel[data-menu]",
    "the versions menu": ".lf-floating-panel[data-menu]",
    "the command reference": ".lf-command-reference.open",
    "a reaction palette": ".lf-react-strip.lf-react-open",
}


RING_SCOPE_OPENER = {
    "an inline response": "#pr-exact-patch .lf-diff-file-comment",
    "On me": ".lf-fp-on-user",
    "the leaf's menu": ".lf-fp-leaf",
    "a thread card": '.lf-margin-marker[data-lf-kinds~="comment"]',
    "a reaction palette": f"{PANEL_THREAD} .lf-react-strip > .lf-react-trigger",
    # Any control inside the diff puts the user in its scope, where `]` lands a line.
    "a landed diff line": "#pr-exact-patch summary",
}


# The window a scope's own surface stands in, where that is not the page's own: the
# contents-link and thread-card samples use a wide window where their page-margin
# surfaces can stand beside the source. Every other scope is read at the width the page
# opened at.
RING_VIEWPORT = (1200, 900)


RING_SCOPE_WIDTH = {
    "a contents link": 1600,
    "an inline thread": 1600,
    "a thread card": 1600,
}


# Scopes whose samples stand in a thread's view of the panel: the view of the first
# thread whose view holds the selector (`open_panel_thread_holding`).
RING_SCOPE_THREAD = {
    "a resolved thread": ".lf-fp-controls .lf-fp-settle.lf-reopen",
    "a reaction palette": ".lf-react-strip > .lf-react-trigger",
    "message media": ".lf-message-media",
}


def open_panel_thread_holding(page, selector):
    """Open the panel's view of the first thread, open or resolved, whose view holds
    `selector`, walking Threads' rows in turn."""

    def threads_on(status):
        if page.locator(PANEL).get_attribute("data-open") is not None:
            page.locator(".lf-fp-close").click()
            panel_settled(page, open=False)
        page.locator(".lf-fp-threads").click()
        panel_settled(page, view="threads")
        page.locator(".lf-fp-filters button", has_text=status).click()

    for status in ("Open", "Resolved"):
        threads_on(status)
        keys = page.locator(".lf-fp-thread").evaluate_all(
            "rows => rows.map(row => row.dataset.key)"
        )
        for key in keys:
            threads_on(status)
            page.locator(f'.lf-fp-thread[data-key="{key}"]').click()
            panel_settled(page, view="thread")
            if page.locator(f"{PANEL} {selector}").count():
                return
    raise AssertionError(f"no thread's view holds {selector}")


# Focus put back at the document's start. A blur retains the previous sequential
# navigation position, which would make the opening key sequences depend on the last case.
RING_FOCUS_START = RELEASE_FOCUS


SEEN_STOP = browser_function("focus_rings.js", "seenStop", using="control_name.js")


# Both readings of a Tab's landing in one round trip: whether the stop is new, and for a
# new one, what it shows of where the keyboard is.
WALKED_STOP = f"""() => {{
  const stop = ({RING_NEW_STOP})();
  return [stop, stop === "new" ? ({SEEN_STOP})() : null];
}}"""


def seen_stop(page, seen=...):
    """The focused stop as the user would fail to find it, or None where they can.

    `seen` is a `SEEN_STOP` reading already taken. The rings off the stop itself that
    it leaves undecided answer only where a ring rule drew them (`ring_rules`)."""
    if seen is ...:
        seen = page.evaluate(SEEN_STOP)
    if seen is None:
        return None
    if any(ring_rules(page, [(pseudo, "outline") for pseudo in seen["carriers"]])):
        return None
    return seen["lost"]


def _tab_walk(page, stem):
    """Walk the page's whole ordinary Tab order and name every stop that shows nothing
    of where the keyboard is, and every ring a stop leaves cut or covered
    (`ring_faults`). A ring that stays lit across stops, such as a decision's for the
    control the user reached inside it, is named once."""
    page.evaluate("() => { window.__lfSeen = new WeakSet(); }")
    page.evaluate(RELEASE_FOCUS)
    unindicated, faults, faulted = [], [], set()
    empty = 0
    for _ in range(400):
        page.keyboard.press("Tab")
        stop, seen = page.evaluate(WALKED_STOP)
        lost = seen_stop(page, seen)
        if stop == "seen":
            break
        if stop == "empty":
            empty += 1
            assert empty <= 2, f"Tab never entered {stem}"
            continue
        empty = 0
        if lost:
            unindicated.append(f"{stem}: {lost}")
        drawn = [ring for ring in rings_drawn(page) if ring["who"] not in faulted]
        # The runtime's answer to the scroll Tab made, such as a pinned reply row taking
        # its place, can trail the landing, so a fault counts once the page is at rest.
        if ring_faults(drawn, stem):
            page_at_rest(page)
            drawn = [ring for ring in rings_drawn(page) if ring["who"] not in faulted]
        faulted.update(ring["who"] for ring in drawn if ring["cuts"] or ring["covers"])
        faults += ring_faults(drawn, f"tabbing through {stem}")
    else:
        raise AssertionError(f"Tab order never came round in {stem}")
    page.evaluate(RELEASE_FOCUS)
    return unindicated, faults


AIM_BOXES = browser_function("aims.js", "offeredAims")


# What the sweep has to have stood in front of before its answer means anything. Each is
# on a surface the walk has to open, and each was under the floor.
AIM_SURFACES = (
    ".lf-fp-settle",
    '[data-row="preview"]',
    ".lf-react-strip .lf-react",
    ".lf-fp-compare",
    ".lf-command-reference-command",
    ".lf-quote",
    ".lf-tab-btn",
    ".lf-grip",
)


def _each_aim_surface(page, page_dir):
    """Stand each surface up in turn, yielding at every stop.

    In turn rather than all at once, because they do not coexist: the reference is modal
    and takes the leaf's menu down as it opens, so a sweep that waited for the last of
    them would meet a page that had put two of the controls away again.
    """
    comment, answered = [
        e["id"] for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    ][:2]
    # A resolved thread, which is the only state that has a Reopen to aim at. Resolving
    # moves the user on to the next open thread, so the resolved one is opened again.
    open_panel_thread(page, comment)
    page.locator(".lf-fp-controls .lf-fp-settle").click()
    round_trip(page)
    open_panel_thread(page, comment)
    expect(page.locator(".lf-fp-controls .lf-fp-settle")).to_have_class(
        re.compile(r"\blf-reopen\b")
    )
    yield
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The agent's answer in the other thread, with its reaction palette open: its chips
    # show only while it stands.
    open_panel_thread(page, answered)
    page.locator(f"{PANEL_THREAD} .lf-react-strip > .lf-react-trigger").first.click()
    expect(
        page.locator(".lf-react-palette:popover-open .lf-react").first
    ).to_be_visible()
    yield
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The leaf's menu, which holds the preview's badge, and then its Versions, which
    # hold Compare.
    panel_menu(page)
    yield
    panel_menu(page, "versions")
    yield
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference-command").first).to_be_visible()
    yield


# Every kind of box AIM_SURFACES names, beside the widgets whose built controls the
# sweep reads at rest: tabs, a board's grips, a question with its own Done and field,
# and a suggestion's margin pair.
AIM_PAGE = leaf_page(
    "aims",
    """<h1 id="t">Aims</h1>
<p id="aim-lead">The first view holds the board and the question.</p>
<lf-tabs id="aim-views">
  <lf-tab id="aim-first" label="First">
    <lf-board id="aim-board">
      <lf-column id="aim-todo" label="Todo">
        <lf-card id="aim-card"><strong>Heated perch</strong></lf-card>
        <lf-card id="aim-other"><strong>Squirrel baffle</strong></lf-card>
      </lf-column>
      <lf-column id="aim-done" label="Done"></lf-column>
    </lf-board>
    <lf-ask id="aim-ask"><h2>Which jobs?</h2>
      <lf-options id="aim-jobs" choose multiple>
        <lf-option id="aim-mounts">Replace the mounts</lf-option>
        <lf-option id="aim-bath">Heat the bird bath</lf-option>
      </lf-options>
    </lf-ask>
    <p>Start at <lf-suggestion id="aim-change"><lf-old>nine.</lf-old><lf-new>ten.</lf-new>
    </lf-suggestion></p>
  </lf-tab>
  <lf-tab id="aim-second" label="Second"><p>The second view.</p></lf-tab>
</lf-tabs>""",
)


# The phone, whose settings sit behind their disclosure; the width changes nothing else.
@pytest.mark.parametrize("width", [390])
def test_merge_film_play_continues_from_the_displayed_moment(browser, serve, width):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    play = page.locator(".film-play")
    slider = page.locator(".film-scrub")
    # Read the first painted frame within the trusted click, before playback advances.
    play.evaluate(
        "button => button.addEventListener('click', () => {"
        "window.firstPlayPosition = document.querySelector('.film-scrub').value;"
        "})"
    )
    arrival = slider.input_value()
    assert float(arrival) > 0
    play.click()
    assert page.evaluate("window.firstPlayPosition") == arrival
    play.click()

    page.reload()
    wait_until_ready(page)
    if width < 560:
        page.locator(".film-settings summary").click()
    page.locator("input[name=film-flag-moved]").uncheck()
    play.evaluate(
        "button => button.addEventListener('click', () => {"
        "window.firstPlayPosition = document.querySelector('.film-scrub').value;"
        "})"
    )
    changed = slider.input_value()
    play.click()
    assert page.evaluate("window.firstPlayPosition") == changed
    play.click()
    slider.focus()
    page.keyboard.press("End")
    expect(play).to_have_text("Replay")
    play.click()
    assert page.evaluate("window.firstPlayPosition") == "0"
    play.click()


def test_live_sample_full_view_keeps_the_child_and_returns_after_inner_escape(
    browser, serve
):
    """Viewport inspection retains practice state and contains focus until return."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    child_url = child.url
    parent_before = events_model.read_events(serve.page_dir)
    full = sample.get_by_role("button", name="Full view", exact=True)
    sample.get_by_role("button", name="Reset", exact=True).focus()
    page.keyboard.press("Tab")
    expect(full).to_be_focused()
    next_top = page.locator("#second-practice").bounding_box()["y"]
    parent_scroll = page.evaluate("scrollY")
    page.keyboard.press("Enter")
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    expect(sample.get_by_role("dialog", name="First practice")).to_be_visible()
    assert abs(page.locator("#second-practice").bounding_box()["y"] - next_top) <= 1
    assert page.evaluate("scrollY") == parent_scroll
    assert (
        sample.locator("iframe").bounding_box()["height"]
        > page.viewport_size["height"] * 0.8
    )
    with sending(child, "the full view choice"):
        child.locator("#child-a .lf-pick").click()
    draft = page_comment(child)
    write(draft, "Keep this draft through Full view.")
    back.click()
    expect(full).to_be_focused()
    assert child.url == child_url
    expect(child.locator("#child-a .lf-pick")).to_have_attribute("aria-checked", "true")
    expect(draft).to_have_js_property("value", "Keep this draft through Full view.")

    full.click()
    resized(page, 390, 720)
    expect(back).to_be_in_viewport()
    assert root_overflow(page) <= 1
    # The held draft gives the field the quick chips' room. Open Threads through
    # the child's Go-to route while the same frame stands in Full view.
    child.locator("h1").click()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(child, view="threads")
    page.keyboard.press("Escape")
    panel_settled(child, open=False)
    expect(back).to_be_visible()
    page.keyboard.press("Escape")
    expect(full).to_be_focused()
    assert child.url == child_url
    expect(draft).to_have_js_property("value", "Keep this draft through Full view.")
    assert events_model.read_events(serve.page_dir) == parent_before
    expect(
        page.locator("#second-practice")
        .frame_locator("iframe")
        .locator("#child-a .lf-pick")
    ).to_have_attribute("aria-checked", "false")

    full.click()
    sample.get_by_role("button", name="Reset", exact=True).click()
    sample.evaluate("sample => sample.ready")
    expect(back).to_be_visible()
    expect(
        sample.frame_locator("iframe").locator("#child-a .lf-pick")
    ).to_have_attribute("aria-checked", "false")
    back.press("Escape")
    expect(full).to_be_focused()

    full.click()
    sample.evaluate("""sample => {
      const parent = sample.parentNode;
      const next = sample.nextSibling;
      sample.remove();
      parent.insertBefore(sample, next);
    }""")
    expect(full).to_be_visible()
    assert sample.locator("dialog").evaluate("view => !view.matches(':modal')")


def test_a_live_revision_mounts_and_resets_its_new_sample(browser, serve):
    """An arriving sample allocates from its own revision before that revision paints."""
    page = open_page(browser, live_url(serve(LIVE_SAMPLE_PAGE)))
    addition = """
<lf-sample id="arriving-practice" label="New practice">
  <template id="arriving-source" data-sample>
    <h1 id="arrival-heading">Practice added in the revision</h1>
  </template>
</lf-sample>
"""
    revised = LIVE_SAMPLE_PAGE.replace("</main>", addition + "</main>")
    with page.expect_request("**/api/samples") as allocation:
        _publish(serve.page_dir, 2, revised, "Add another practice page.")
    sample = page.locator("#arriving-practice")
    expect(sample.frame_locator("iframe").locator("#arrival-heading")).to_have_text(
        "Practice added in the revision"
    )
    wait_until_ready(page)
    child_url = sample.locator("iframe").get_attribute("src")

    # A later revision keeps this exact node and its template. Reset must retain
    # the source coordinate it arrived with rather than borrow the newer reading.
    _publish(
        serve.page_dir,
        3,
        revised.replace("Practice without changing this page", "Practice together"),
        "Revise the surrounding explanation.",
    )
    expect(page.locator("#host-heading")).to_have_text("Practice together")
    wait_until_ready(page)
    reset = sample.get_by_role("button", name="Reset", exact=True)
    with page.expect_request("**/api/samples") as replacement:
        reset.click()
    assert replacement.value.header_value("Leaf-View-Revision") == (
        allocation.value.header_value("Leaf-View-Revision")
    )
    expect(sample.locator("iframe")).not_to_have_attribute("src", child_url)
    expect(sample.frame_locator("iframe").locator("#arrival-heading")).to_have_text(
        "Practice added in the revision"
    )
    wait_until_ready(page)


def test_thread_panel_gallery_shows_independent_live_views(browser, serve):
    """Child pages hold independent panel and anchored views across sample Reset."""
    gallery = FEATURE_GALLERY.parent / "thread-panel-gallery.html"
    page = open_page(browser, serve(gallery))
    views = {
        "overview": page.frame_locator("#overview-sample iframe"),
        "you": page.frame_locator("#on-you-sample iframe"),
        "resolved": page.frame_locator("#resolved-sample iframe"),
        "summary": page.frame_locator("#summary-sample iframe"),
    }
    threads = '.lf-fp-view[data-view="threads"]:not([data-leaving])'
    for name in ("overview", "resolved"):
        expect(views[name].locator(PANEL)).to_have_attribute("data-open", "threads")
        expect(views[name].locator(f"{threads} .lf-fp-thread").first).to_be_visible()

    expect(views["overview"].locator(f"{threads} .lf-fp-thread")).to_have_count(3)
    anchored = views["you"].locator(".lf-margin-preview")
    expect(anchored).to_be_visible()
    expect(anchored).to_have_attribute(
        "aria-label", "Thread for Agenda and room photo."
    )
    expect(anchored.locator(".lf-msg")).to_have_count(3)
    expect(anchored.locator("leaf-text")).to_be_visible()
    expect(
        views["resolved"].locator(".lf-fp-filters button[aria-pressed=true]")
    ).to_have_text("Resolved")
    expect(views["resolved"].locator(f"{threads} .lf-fp-thread")).to_have_count(1)
    summary = views["summary"].locator(f'{PANEL_THREAD}[data-thread="c1a39980"]')
    expect(summary).to_be_visible()
    expect(views["summary"].locator(".lf-fp-title")).to_have_text("Afternoon workshop")

    page.locator("#overview-sample").evaluate(
        "sample => sample.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    views["overview"].locator(".lf-fp-close").click()
    expect(views["overview"].locator(PANEL)).not_to_have_attribute(
        "data-open", re.compile(".*")
    )
    expect(anchored).to_be_visible()
    reset = page.locator("#overview-sample").get_by_role(
        "button", name="Reset", exact=True
    )
    reset.click()
    expect(reset).to_be_enabled()
    expect(views["overview"].locator(PANEL)).to_have_attribute("data-open", "threads")
    expect(views["overview"].locator(f"{threads} .lf-fp-thread")).to_have_count(3)
    reset.focus()
    expect(reset).to_be_focused()
    assert (
        page.locator("#on-you-sample").evaluate(
            "sample => sample.showThread('98850286')"
        )
        is True
    )
    expect(reset).to_be_focused()
    expect(anchored).to_be_visible()

    # Parent view commands never borrow child focus, nor the field the child's user
    # stands in: a panel view would stand the thread's reply there, so it is declined.
    child_field = views["you"].locator(".lf-fp-field leaf-text")
    child_field.click()
    expect(child_field).to_be_focused()
    assert (
        page.locator("#on-you-sample").evaluate(
            "sample => sample.showThread('98850286', {surface: 'panel'})"
        )
        is False
    )
    expect(views["you"].locator(PANEL_THREAD)).to_have_count(0)
    expect(child_field).to_be_focused()


def test_sample_fixture_history_presents_before_ready_and_returns_on_reset(
    browser, serve
):
    """Shared authored history starts independent windows before host controls run."""
    source = leaf_page(
        "History study",
        """
        <h1>History study</h1><output id="arrivals">0</output>
        <lf-sample id="first-history" label="first treatment" window>
          <template id="first-history-page" data-sample data-sample-events="history">
            <h1>Weekend service</h1><p id="timetable">Trains run hourly.</p>
          </template>
        </lf-sample>
        <lf-sample id="second-history" label="second treatment" window>
          <template id="second-history-page" data-sample data-sample-events="history">
            <h1>Weekend service</h1><p id="timetable">Trains run hourly.</p>
          </template>
        </lf-sample>
        """,
        head="""
        <script id="history" type="application/json">
          [{"id":"question","kind":"comment","anchor":{"section":"timetable"},
            "text":"Does Sunday keep this timetable?"},
           {"kind":"reply","author":"agent","parent":"question",
            "text":"Yes, both weekend days use the same hourly service."}]
        </script>
        <script type="module">
          let arrivals = 0;
          document.addEventListener('lf-sample-ready', async event => {
            const sample = event.detail.sample;
            await sample.showThread('question', {surface: 'panel'});
            document.querySelector('#arrivals').textContent = String(++arrivals);
          });
        </script>
        """,
    )
    page = open_page(browser, serve(source))
    expect(page.locator("#arrivals")).to_have_text("2")
    parent_before = events_model.read_events(serve.page_dir)
    first = page.frame_locator("#first-history iframe")
    other = page.frame_locator("#second-history iframe")
    for frame in (first, other):
        expect(frame.locator(f'{PANEL_THREAD}[data-thread="question"]')).to_be_visible()
    first_state = first.locator("body").evaluate(
        "new URL('api/state', document.baseURI).href"
    )
    first.locator(".lf-fp-controls .lf-fp-settle").click()
    wait_for(
        lambda: [e["kind"] for e in page.request.get(first_state).json()["events"]],
        lambda kinds: "resolve" in kinds,
        failure="the first sample's Resolve never reached its own log",
    )
    other_events = page.request.get(
        other.locator("body").evaluate("new URL('api/state', document.baseURI).href")
    ).json()["events"]
    assert [event["kind"] for event in other_events if event["kind"] != "read"] == [
        "comment",
        "reply",
    ]
    assert events_model.read_events(serve.page_dir) == parent_before
    page.locator("#first-history").get_by_role(
        "button", name="Reset", exact=True
    ).click()
    expect(page.locator("#arrivals")).to_have_text("3")
    expect(first.locator(f'{PANEL_THREAD}[data-thread="question"]')).to_be_visible()
    state = page.request.get(
        first.locator("body").evaluate("new URL('api/state', document.baseURI).href")
    ).json()
    assert [event["kind"] for event in state["events"] if event["kind"] != "read"] == [
        "comment",
        "reply",
    ]
    assert state["events"][1]["parent"] == "question"
    assert events_model.read_events(serve.page_dir) == parent_before


def test_sample_host_view_changes_leave_its_scroll_and_keyboard_position(
    browser, serve
):
    """Page, panel and Reset arrive inside a child without moving its host reader."""
    page = open_page(browser, serve(_sample_containment_page()))
    resized(page, 1000, 720)
    sample = page.locator("#practice")
    sample.evaluate("async sample => { await sample.ready; }")
    frame = sample.locator("iframe")
    completed = 0
    for position in ("offscreen", "partial"):
        page.evaluate(
            """position => {
              const frame = document.querySelector('#practice iframe');
              scrollTo({top: position === 'offscreen' ? 0
                : scrollY + frame.getBoundingClientRect().top - 350,
                behavior: 'instant'});
            }""",
            position,
        )
        box = frame.bounding_box()
        if position == "offscreen":
            assert box["y"] > 720
        else:
            assert 0 < box["y"] < 720 < box["y"] + box["height"]
        for button_id, panel_open in (
            ("show-page", False),
            ("show-panel", True),
            ("reset-child", True),
        ):
            button = page.locator(f"#{button_id}")
            button.scroll_into_view_if_needed()
            before = page.evaluate("scrollY")
            button.click()
            completed += 1
            expect(page.locator("#completed")).to_have_text(str(completed))
            child = frame.element_handle().content_frame()
            expect(button).to_be_focused()
            assert page.evaluate("scrollY") == before
            if panel_open:
                expect(
                    child.locator(f'{PANEL_THREAD}[data-thread="question"]')
                ).to_be_visible()
            else:
                expect(
                    child.locator(".lf-margin-preview").get_by_text(
                        "Can you check the destination?", exact=True
                    )
                ).to_be_visible()
                # The page draws it, so the panel's view of it goes: it shows once.
                expect(child.locator(PANEL_THREAD)).to_have_count(0)


def test_sample_child_passage_and_reply_gestures_scroll_only_the_child(browser, serve):
    """Child navigation reveals nested reading regions; disclosure and typing stay local."""
    page = open_page(browser, serve(_sample_containment_page()))
    resized(page, 1000, 720)
    sample = page.locator("#practice")
    sample.evaluate("async sample => { await sample.ready; }")
    page.locator("#show-panel").click()
    expect(page.locator("#completed")).to_have_text("1")
    frame = sample.locator("iframe")
    page.evaluate(
        """() => scrollTo({top: scrollY +
          document.querySelector('#practice iframe').getBoundingClientRect().top - 150,
          behavior: 'instant'})"""
    )
    child = frame.element_handle().content_frame()
    # The thread's view goes to the passage it quotes with On the page.
    on_the_page = child.locator(".lf-fp-controls").get_by_role(
        "button", name="On the page"
    )
    on_the_page.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    root_before = child.evaluate("scrollY")
    on_the_page.click()
    scroll_settled(child)
    landing = child.evaluate(
        """() => {
          const target = document.querySelector('#destination').getBoundingClientRect();
          const pane = document.querySelector('#nested-reading').getBoundingClientRect();
          return {target:target.toJSON(), pane:pane.toJSON(), height:innerHeight,
            nested:document.querySelector('#nested-reading').scrollTop, root:scrollY};
        }"""
    )
    assert landing["target"]["top"] >= max(0, landing["pane"]["top"]) - 1, landing
    assert (
        landing["target"]["bottom"]
        <= min(landing["height"], landing["pane"]["bottom"]) + 1
    ), landing
    assert child.evaluate("scrollY") > root_before
    assert child.locator("#nested-reading").evaluate("box => box.scrollTop") > 0
    assert page.evaluate("scrollY") == before

    # A real child disclosure keeps its focused toggle in its own conversation.
    page.locator("#show-panel").click()
    expect(page.locator("#completed")).to_have_text("2")
    expand = child.locator(".lf-fp-view summary").filter(has_text="Read the checks")
    expand.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    expand.focus()
    expand.press("Enter")
    expect(child.locator(".lf-fp-view details")).to_have_attribute("open", "")
    expect(expand).to_be_focused()
    expect(expand).to_be_in_viewport()
    rendered(child)
    assert page.evaluate("scrollY") == before

    editor = child.locator('.lf-fp-field leaf-text[name="reply"]')
    editor.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    words = "\n".join(f"Line {i} of the reply" for i in range(30))
    write(editor, words)
    expect(editor).to_have_js_property("value", words)
    child.wait_for_function(
        """() => document.querySelector(
          '.lf-fp-field leaf-text[name="reply"]').scrollTop > 0"""
    )
    rendered(child)
    expect(editor).to_be_focused()
    assert page.evaluate("scrollY") == before


def test_sample_reset_keeps_the_keyboard_position_while_loading(browser, serve):
    """Reset keeps its stop through loading and failure, without reclaiming focus."""
    source = leaf_page(
        "Practice reset",
        """
<h1>Practice reset</h1>
<button id="continue-reading" type="button">Continue reading</button>
<lf-sample id="practice" label="Practice page">
  <template id="practice-source" data-sample><p>Start again here.</p></template>
</lf-sample>
""",
    )
    source = source.replace("</template>", SAMPLE_STARTUP_FAILURE + "</template>")
    page = open_page(browser, serve(source))
    sample = page.locator("#practice")
    reset = sample.get_by_role("button", name="Reset", exact=True)
    onward = page.locator("#continue-reading")
    expect(reset).to_be_enabled()
    held = []
    navigation = re.compile(r"/api/samples/[^/]+/$")
    page.route(
        navigation,
        lambda route: (
            held.append(route)
            if route.request.is_navigation_request()
            else route.continue_()
        ),
    )
    onward.focus()
    onward.press("Tab")
    expect(reset).to_be_focused()
    assert reset.evaluate("button => button.matches(':focus-visible')")
    scroll_before = page.evaluate("scrollY")

    reset.press("Enter")
    holding(page, held, 1, "the replacement practice page")
    expect(reset).to_be_disabled()
    expect(reset).to_be_focused()
    reset.press("Space")
    reset.press("Enter")
    rendered(page)
    assert len(held) == 1
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == scroll_before

    # Completion must leave a newer keyboard destination alone.
    reset.press("Shift+Tab")
    expect(onward).to_be_focused()
    held[0].continue_()
    expect(reset).to_be_enabled()
    expect(onward).to_be_focused()

    onward.press("Tab")
    reset.press("Space")
    holding(page, held, 2, "the failed replacement practice page")
    expect(reset).to_be_focused()
    fail_sample_startup(held[1])
    expect(sample.get_by_role("status")).to_have_text("Practice could not start")
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == scroll_before

    page.unroute(navigation)
    reset.press("Enter")
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    expect(
        sample.frame_locator("iframe").get_by_text("Start again here.")
    ).to_be_visible()


def test_live_samples_keep_real_gestures_and_drafts_inside_the_child(browser, serve):
    """A sample is a full page: its choices and comments reach only its own log."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    parent_before = events_model.read_events(serve.page_dir)
    first = page.locator("#first-practice")
    second = page.locator("#second-practice")
    reset = first.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    expect(second.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    # The host's controls stand with its label, outside the indented child page.
    controls = first.locator(".lf-sample-controls").bounding_box()
    frame = first.locator("iframe").bounding_box()
    assert abs(controls["x"] - first.bounding_box()["x"]) < 1
    assert controls["x"] < frame["x"]
    assert controls["y"] + controls["height"] <= frame["y"]
    child = first.locator("iframe").element_handle().content_frame()
    other = second.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    child_url = urlsplit(child.url)._replace(fragment="").geturl()
    assert child.url != other.url
    # A child's startup does not take focus from the page it arrives in.
    assert page.evaluate("document.activeElement.tagName") != "IFRAME"
    # Each frame takes its page's height, so the containing page scrolls it whole:
    # the child's viewport ends where its page does, the room the page keeps at its
    # foot for the panel's row included.
    for practice in (child, other):
        assert practice.evaluate(
            "Math.abs(document.body.getBoundingClientRect().bottom - innerHeight) <= 1"
        )

    # The first click lands on the child's control; there is no entry step.
    with sending(child, "the sample choice"):
        child.locator("#child-a .lf-pick").click()
    expect(child.locator("#child-a .lf-pick")).to_have_attribute("aria-checked", "true")
    expect(other.locator("#child-a .lf-pick")).to_have_attribute(
        "aria-checked", "false"
    )

    draft = page_comment(child)
    write(draft, "Keep this draft while I resize the page.")
    width_before = child.evaluate("innerWidth")
    page.set_viewport_size({"width": 720, "height": 900})
    child.wait_for_function("before => innerWidth < before", arg=width_before)
    expect(draft).to_have_js_property(
        "value", "Keep this draft while I resize the page."
    )
    expect(draft).to_be_focused()
    assert urlsplit(child.url)._replace(fragment="").geturl() == child_url
    with sending(child, "the sample comment"):
        draft.press("ControlOrMeta+Enter")
    # The send opens the new thread's view, as the field's page comment does.
    expect(child.locator(PANEL_THREAD)).to_contain_text("Keep this draft")
    child.locator(".lf-fp-close").click()
    panel_settled(child, open=False)
    state_response = page.request.get(child_url + "api/state")
    assert state_response.ok, state_response.text()
    state = state_response.json()
    assert [event["kind"] for event in state["events"]] == ["action", "comment"]
    assert state["events"][-1]["text"] == "Keep this draft while I resize the page."
    assert (
        page.request.get(
            other.evaluate("new URL('api/state', document.baseURI).href")
        ).json()["events"]
        == []
    )
    assert events_model.read_events(serve.page_dir) == parent_before

    write(page_comment(child), "Discard this unsent practice draft on reset.")
    page.evaluate("""() => {
        localStorage.setItem('parent-draft', 'retain');
        sessionStorage.setItem('parent-tab', 'retain');
    }""")
    parent_storage = page.evaluate(
        "[Object.keys(localStorage), Object.keys(sessionStorage)]"
    )
    # The child's panel stands at the foot of its frame, which the host scrolls to.
    second.evaluate(
        "sample => sample.scrollIntoView({block: 'end', behavior: 'instant'})"
    )
    write(page_comment(other), "Keep the other sample's draft.")
    reset.scroll_into_view_if_needed()
    reset_scroll = page.evaluate("scrollY")
    reset.click()
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == reset_scroll
    reset_child = first.locator("iframe").element_handle().content_frame()
    assert reset_child.url != child_url
    expect(reset_child.locator("#child-a .lf-pick")).to_have_attribute(
        "aria-checked", "false"
    )
    expect(reset_child.locator(".lf-thread")).to_have_count(0)
    expect(page_comment(reset_child)).to_have_js_property("value", "")
    assert page.request.get(child_url + "api/state").status == 404
    assert events_model.read_events(serve.page_dir) == parent_before
    assert (
        page.evaluate("[Object.keys(localStorage), Object.keys(sessionStorage)]")
        == parent_storage
    )
    assert page.evaluate(
        "localStorage.getItem('parent-draft') === 'retain' && "
        "sessionStorage.getItem('parent-tab') === 'retain'"
    )
    expect(other.locator('.lf-fp-field leaf-text[name="comment"]')).to_have_js_property(
        "value", "Keep the other sample's draft."
    )


def test_a_window_sample_is_a_whole_leaf_window_that_scrolls_inside(browser, serve):
    """A window sample presents its opening view, keeps full chrome, and scrolls inside."""
    filler = "".join(
        f'<p id="filler-{i}">Line {i} of a long page.</p>' for i in range(60)
    )
    source = leaf_page(
        "window sample",
        f"""
<h1>Window sample</h1>
<lf-sample id="window-sample" label="a whole window" window>
  <template id="window-page" data-sample>
    <script type="module">history.replaceState(null, "", "#first-view");</script>
    <h1>Child</h1>
    <lf-tabs id="child-views">
      <lf-tab id="first-view" label="Long view">{filler}</lf-tab>
      <lf-tab id="second-view" label="Short view"><p>Another view.</p></lf-tab>
    </lf-tabs>
  </template>
</lf-sample>
""",
    )
    page = open_page(browser, serve(source))
    sample = page.locator("#window-sample")
    reading = sample.evaluate("async sample => await sample.ready")
    child_frame = sample.locator("iframe").element_handle().content_frame()
    child = child_frame.evaluate(
        """() => ({
          block: document.documentElement.hasAttribute('data-lf-sample-block'),
          panel: getComputedStyle(document.querySelector('.lf-floating-panel')).display,
          page: document.documentElement.scrollHeight,
        })"""
    )
    assert reading["block"] == child["block"]
    assert not child["block"]
    assert child["panel"] != "none"
    frame = sample.locator("iframe")
    assert frame.bounding_box()["height"] < child["page"] / 2
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )

    box = frame.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    content = page.frame_locator("#window-sample iframe").locator(":root")
    scroll_before = content.evaluate("root => root.scrollTop")
    page.mouse.wheel(0, 300)
    expect(content).to_have_js_property("scrollTop", scroll_before + 300)
    assert frame.bounding_box()["height"] == box["height"]

    sample.get_by_role("button", name="Full view", exact=True).click()
    assert frame.bounding_box()["height"] > page.viewport_size["height"] * 0.8
    sample.get_by_role("button", name="Return to page", exact=True).click()
    expect(content).to_have_js_property("scrollTop", scroll_before + 300)
    assert frame.bounding_box()["height"] == box["height"]

    # A fragment set during startup must not prevent Reset or reload from presenting.
    reset = sample.get_by_role("button", name="Reset", exact=True)
    old_url = child_frame.url
    reset.click()
    expect(reset).to_be_enabled()
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url != old_url
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )
    page.reload()
    wait_until_ready(page)
    expect(reset).to_be_enabled()
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_sample_editor_focus_preserves_outer_scroll_and_the_caret(
    request, serve, engine
):
    """The editor owns focus policy even when its dependency's browser policy differs."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Editor focus containment",
                """
<h1>Containing page</h1><div style="height:1400px"></div>
<lf-sample id="practice" label="Editor practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1><button id="entry">Enter practice</button>
        <script type="module">
          import {focusDestination} from '/runtime/widget-api.js';
          window.placeEditor = () => focusDestination(document.querySelector('#editor'), 'move');
        </script>
  </template>
</lf-sample>
""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.evaluate("""async () => {
      const editor = document.createElement('leaf-text');
      editor.id = 'editor';
      editor.value = 'Words stay here';
      document.querySelector('main').append(editor);
      editor.setSelectionRange(6, 10);
    }""")
    child.locator("#entry").click()
    page.evaluate("scrollTo(0, 0)")
    scroll_settled(page)
    assert child.evaluate("document.hasFocus()")
    for _ in range(3):
        child.evaluate("placeEditor()")
        scroll_settled(page)
        assert page.evaluate("scrollY") == 0
        expect(child.locator("#editor")).to_be_focused()
        child.locator("#entry").click()
        page.evaluate("scrollTo(0, 0)")
        scroll_settled(page)
    child.evaluate("placeEditor()")
    # Real editing proves the arrival used the retained caret, not the browser's
    # initial caret. The browser may reveal its context for this deliberate input.
    page.keyboard.insert_text("remain")
    expect(child.locator("#editor")).to_have_js_property("value", "Words remain here")


def test_sample_browser_boundary_contains_focus_scroll_and_parent_access(
    browser, serve
):
    """Leaf navigation stays local without changing authored native browser APIs."""
    filler = "".join(f"<p>Child passage {number}.</p>" for number in range(40))
    source = leaf_page(
        "Isolated sample",
        f"""
<h1>Review page</h1><button id="outer-control">Choose a conversation</button>
<div style="height:800px"></div>
<lf-sample id="isolated-practice" label="Isolated practice" window>
  <template id="isolated-source" data-sample>
    <h1>Practice page</h1><button id="child-control">Practice action</button>
    {filler}
    <div id="inner-scroll" tabindex="0" style="height:160px;overflow:auto">
      <div style="height:600px"></div><button id="deep-control">Nested action</button>
    </div>
    <svg><a id="svg-control" href="#child-control" tabindex="0"><text y="20">SVG action</text></a></svg>
    <dialog id="practice-modal"><input></dialog>
    <dialog id="practice-inner-modal"><input></dialog>
    <div id="practice-popover" popover><input></div>
    <iframe title="Authored embedded page" srcdoc="<p>Embedded content is allowed</p>"></iframe>
    <script type="module">
      import {{ closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer }} from '/runtime/widget-api.js';
      window.leafNavigation = {{ closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer }};
      for (const input of document.querySelectorAll('dialog input, [popover] input'))
        input.autofocus = true;
      window.leafFocusEvents = [];
      document.addEventListener('focusin', event => leafFocusEvents.push(event.target.id), true);
      window.addEventListener('message', event => {{
        if (event.data === 'close-child-modal') {{
          closeNativeLayer(document.querySelector('#practice-inner-modal'));
          closeNativeLayer(document.querySelector('#practice-modal'));
          parent.postMessage({{type: 'closed-child-modal', focused: document.hasFocus()}}, '*');
          return;
        }}
        if (event.data !== 'attempt-child-focus') return;
        leafFocusEvents.length = 0;
        document.dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}));
        scrollIntoView(document.querySelector('#deep-control'));
        focusDestination(document.querySelector('#deep-control'), 'move');
        focusDestination(document.querySelector('#svg-control'), 'move');
        const dialog = document.querySelector('#practice-modal');
        for (const modal of [true, false]) {{
          showNativeLayer(dialog, {{modal}});
          closeNativeLayer(dialog);
        }}
        const popover = document.querySelector('#practice-popover');
        showNativeLayer(popover);
        closeNativeLayer(popover);
        parent.postMessage({{
          type: 'attempted-child-focus', focused: document.hasFocus(),
          activated: navigator.userActivation.hasBeenActive, focusEvents: leafFocusEvents,
        }}, '*');
      }});
    </script>
  </template>
</lf-sample>
""",
    )
    page = open_page(browser, serve(source))
    sample = page.locator("#isolated-practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    assert child.evaluate(
        """() => {
          try { parent.document; return false; }
          catch (error) { return error.name === 'SecurityError'; }
        }"""
    )
    assert sample.locator("iframe").evaluate("frame => frame.contentDocument === null")
    # External data uses native CORS with the child's opaque origin, never the
    # containing page's authenticated relay. The route stands in for a remote API.
    remote = "https://cors.example.invalid/sample.json"
    external_requests = []

    def cors_response(route):
        external_requests.append(route.request.headers)
        route.fulfill(
            headers={"Access-Control-Allow-Origin": "*"},
            json={"reading": "external data"},
        )

    page.route(remote, cors_response)
    assert child.evaluate("async url => (await fetch(url)).json()", remote) == {
        "reading": "external data"
    }
    assert len(external_requests) == 1
    assert external_requests[0]["origin"] == "null"
    assert "cookie" not in external_requests[0]
    page.unroute(remote)
    # Scripts and nested embeds are still admitted; native methods are untouched.
    assert child.evaluate("""() =>
      [HTMLElement.prototype.focus, Element.prototype.scrollIntoView]
        .every(method => Function.prototype.toString.call(method).includes('[native code]'))
    """)
    expect(child.locator('iframe[title="Authored embedded page"]')).to_have_count(1)
    outer = page.locator("#outer-control")
    outer.click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("""() => {
      window.outerTransitions = [];
      for (const type of ['focusin', 'scroll'])
        document.addEventListener(type, event => outerTransitions.push(type), true);
    }""")
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer} = window.leafNavigation;
      leafFocusEvents.length = 0;
      focusDestination(document.querySelector('#child-control'), 'move');
      scrollIntoView(document.querySelector('#deep-control'));
      focusDestination(document.querySelector('#deep-control'), 'move');
      focusDestination(document.querySelector('#svg-control'), 'move');
      const dialog = document.querySelector('#practice-modal');
      showNativeLayer(dialog);
      closeNativeLayer(dialog);
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      closeNativeLayer(popover);
    }""")
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []
    assert child.evaluate("leafFocusEvents") == []
    assert child.evaluate("scrollY") > 0
    assert child.locator("#inner-scroll").evaluate("node => node.scrollTop") > 0

    # A deliberate pointer entry gets real child focus and ordinary local keys.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    expect(child.locator("#child-control")).to_be_focused()
    page.keyboard.press("Escape")
    expect(child.locator("#child-control")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(sample).to_be_focused()

    # Previous user entry cannot let later script calls take ownership back.
    outer.click()
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    before = page.evaluate("scrollY")
    page.evaluate("outerTransitions.length = 0")
    assert page.evaluate("""() => new Promise(resolve => {
      window.addEventListener('message', function report(event) {
        if (event.data?.type !== 'attempted-child-focus') return;
        window.removeEventListener('message', report);
        resolve({focused: event.data.focused, activated: event.data.activated, focusEvents: event.data.focusEvents});
      });
      document.querySelector('#isolated-practice iframe').contentWindow
        .postMessage('attempt-child-focus', '*');
    })""") == {"focused": False, "activated": True, "focusEvents": []}
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []

    # Native close remembers a previous focus target even after the parent has
    # reclaimed input. A return into another modal also escapes ancestor inertness.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    child.evaluate("""() => {
      const {focusDestination, showNativeLayer} = leafNavigation;
      for (const id of ['practice-modal', 'practice-inner-modal']) {
        const dialog = document.getElementById(id);
        showNativeLayer(dialog);
        focusDestination(dialog.querySelector('input'), 'move');
      }
    }""")
    expect(child.locator("#practice-inner-modal input")).to_be_focused()
    outer.click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("outerTransitions.length = 0")
    child.evaluate("leafFocusEvents.length = 0")
    assert (
        page.evaluate("""() => new Promise(resolve => {
      window.addEventListener('message', function report(event) {
        if (event.data?.type !== 'closed-child-modal') return;
        window.removeEventListener('message', report);
        resolve(event.data.focused);
      });
      document.querySelector('#isolated-practice iframe').contentWindow
        .postMessage('close-child-modal', '*');
    })""")
        is False
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []
    assert child.evaluate("leafFocusEvents") == []
    expect(
        child.locator("#practice-modal[open], #practice-inner-modal[open]")
    ).to_have_count(0)

    # A child-owned close preserves its ordinary opener return without native
    # scrolling, and a layer opened from nowhere releases its hidden editor.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, showNativeLayer} = leafNavigation;
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      focusDestination(popover.querySelector('input'), 'move');
      closeNativeLayer(popover);
    }""")
    expect(child.locator("#child-control")).to_be_focused()
    assert page.evaluate("scrollY") == before
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, showNativeLayer} = leafNavigation;
      focusDestination(document.body, 'move');
      document.body.blur();
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      focusDestination(popover.querySelector('input'), 'move');
      closeNativeLayer(popover);
    }""")
    assert child.evaluate("document.activeElement === document.body")
    assert page.evaluate("scrollY") == before


def test_live_samples_retire_before_navigation_and_coalesce_reset(browser, serve):
    """A held replacement navigation cannot keep a released child alive."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.practiceFrame = document.createElement('iframe');
        document.body.append(practiceFrame);
        window.practiceHost = await mountSample(practiceFrame, {template: 'first-source'});
        await practiceHost.ready;
    }""")
    previous = page.evaluate(
        "new URL(practiceFrame.src).origin + new URL(practiceFrame.src).pathname"
    )
    held = []
    released = []
    page.route(re.compile(r"/api/samples/[^/]+/$"), lambda route: held.append(route))
    page.on(
        "request",
        lambda request: (
            released.append(request.url)
            if request.url.endswith("/api/release")
            else None
        ),
    )
    page.evaluate("""() => {
        window.oldPracticeWindow = practiceFrame.contentWindow;
        const first = practiceHost.reset();
        const second = practiceHost.reset();
        window.samePracticeReset = first === second;
        window.practiceResult = Promise.allSettled([first, second]);
    }""")
    holding(page, held, 1, "the replacement sample document")
    assert page.evaluate("samePracticeReset && oldPracticeWindow.closed")
    assert page.request.get(previous + "api/state").status == 404
    replacement = held[0].request.url
    page.evaluate("practiceHost.destroy()")
    assert page.evaluate(
        "practiceResult.then(results => results.map(r => r.reason.name))"
    ) == ["AbortError", "AbortError"]
    assert page.evaluate(
        "practiceFrame.isConnected && !practiceFrame.hasAttribute('src')"
    )
    assert page.request.get(replacement + "api/state").status == 404
    assert released.count(previous + "api/release") == 1
    assert released.count(replacement + "api/release") == 1
    held[0].abort()
    page.unroute(re.compile(r"/api/samples/[^/]+/$"))

    # A failed presentation is retired too; Reset can then start a healthy child.
    page.route(re.compile(r"/api/samples/[^/]+/$"), fail_sample_startup)
    assert (
        page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.practiceHost = await mountSample(practiceFrame, {template: 'first-source'});
        return practiceHost.ready.catch(error => error.message);
    }""")
        == "Practice could not start"
    )
    assert page.evaluate("!practiceFrame.hasAttribute('src')")
    page.unroute(re.compile(r"/api/samples/[^/]+/$"))
    page.evaluate("practiceHost.reset().then(() => {})")
    replacement_frame = page.locator("iframe").last.element_handle().content_frame()
    expect(replacement_frame.locator("body[data-lf-presented]")).to_be_attached()
    page.evaluate("practiceHost.destroy()")


def test_live_samples_release_pending_allocations_and_can_reconnect(browser, serve):
    """Destroy releases every startup phase; a detached widget can reconnect."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    sample = page.locator("#first-practice")
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    sample.get_by_role("button", name="Full view", exact=True).click()
    previous = (
        urlsplit(sample.locator("iframe").get_attribute("src"))
        ._replace(fragment="")
        .geturl()
    )
    page.evaluate("""() => {
        window.detachedPractice = document.querySelector('#first-practice');
        detachedPractice.remove();
    }""")
    page.wait_for_function(
        "!detachedPractice.querySelector('iframe').hasAttribute('src')"
    )
    page.evaluate("document.querySelector('main').append(detachedPractice)")
    expect(reset).to_be_enabled()
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_visible()
    assert sample.locator("iframe").get_attribute("src") != previous
    assert page.request.get(previous + "api/state").status == 404

    held = []
    page.route("**/api/samples", lambda route: held.append(route))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingFrame = document.createElement('iframe');
        document.body.append(pendingFrame);
        window.pendingHost = await mountSample(pendingFrame, {template: 'first-source'});
        window.pendingResult = pendingHost.ready.catch(error => error.name);
    }""")
    holding(page, held, 1, "the child allocation")
    page.evaluate("() => { window.pendingDestroy = pendingHost.destroy(); }")
    response = held[0].fetch()
    allocated = response.json()["url"]
    held[0].fulfill(response=response)
    page.evaluate("pendingDestroy")
    assert page.evaluate("pendingResult") == "AbortError"
    allocated_url = page.evaluate("url => new URL(url, location.href).href", allocated)
    assert page.request.get(allocated_url + "api/state").status == 404
    page.unroute("**/api/samples")

    held.clear()
    page.route(re.compile(r"/api/samples/[^/]+/$"), lambda route: held.append(route))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingHost = await mountSample(pendingFrame, {template: 'first-source'});
        window.pendingResult = pendingHost.ready.catch(error => error.name);
    }""")
    holding(page, held, 1, "a child detached before its document arrives")
    held_release = []
    page.route("**/api/release", lambda route: held_release.append(route))
    page.evaluate("pendingFrame.remove()")
    assert page.evaluate("pendingResult") == "AbortError"
    holding(page, held_release, 1, "the detached child's allocation release")
    assert page.request.get(held[0].request.url + "api/state").status == 200
    held_release[0].continue_()
    page.evaluate("pendingHost.destroy()")
    assert page.request.get(held[0].request.url + "api/state").status == 404
    held[0].abort()
    page.unroute("**/api/release")

    # A destroyed queue entry cannot wait for unrelated children to load. It is
    # removed without consuming the next slot a surviving queued child needs.
    held.clear()
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingResults = [];
        window.pendingHosts = await Promise.all(Array.from({length: 5}, async (_, index) => {
            const frame = document.createElement('iframe');
            document.body.append(frame);
            const host = await mountSample(frame, {template: 'first-source'});
            host.ready.then(
                () => { pendingResults[index] = 'ready'; },
                error => { pendingResults[index] = error.name; });
            return host;
        }));
    }""")
    holding(page, held, 3, "three occupied sample admission slots")
    page.evaluate("""() => {
        window.queuedDestroyDone = false;
        pendingHosts[3].destroy().then(() => { queuedDestroyDone = true; });
    }""")
    page.wait_for_function("queuedDestroyDone && pendingResults[3] === 'AbortError'")
    assert len(held) == 3
    page.evaluate("() => { void pendingHosts[0].destroy(); }")
    holding(page, held, 4, "the surviving queued sample's admission")
    page.evaluate("""() => {
        window.allPendingDestroyed = false;
        Promise.all(pendingHosts.map(host => host.destroy()))
            .then(() => { allPendingDestroyed = true; });
    }""")
    page.wait_for_function("allPendingDestroyed")
    assert page.evaluate("pendingResults") == ["AbortError"] * 5
    for route in held:
        assert page.request.get(route.request.url + "api/state").status == 404
        route.abort()


def test_slow_sample_state_does_not_hold_up_other_child_loads(browser, serve):
    """A child waiting for state releases its load slot for the next sample."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    held = []
    page.route(
        re.compile(r"/api/samples/[^/]+/api/state$"),
        lambda route: held.append(route),
    )
    page.evaluate("""async () => {
      const {mountSample} = await window.__lfWidgetApi();
      window.practiceHosts = await Promise.all(Array.from({length: 4}, () => {
        const frame = document.createElement('iframe');
        document.body.append(frame);
        return mountSample(frame, {template: 'first-source'});
      }));
    }""")
    holding(page, held, 4, "four sample state reads")
    for route in held:
        route.continue_()
    page.evaluate("Promise.all(practiceHosts.map(host => host.ready))")
    page.evaluate("Promise.all(practiceHosts.map(host => host.destroy()))")


def test_live_samples_preserve_optimistic_refusal_and_child_escape(browser, serve):
    """Delivery rollback and nested Escape remain the ordinary child's behavior."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    sample = page.locator("#first-practice")
    expect(sample.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    held = []
    event_url = child.evaluate("new URL('api/event', document.baseURI).href")
    page.route(event_url, lambda route: held.append(route))
    choice = child.locator("#child-a .lf-pick")
    choice.click()
    holding(page, held, 1, "the child's held choice")
    expect(choice).to_have_attribute("aria-checked", "true")
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This practice choice was refused.",
            "final": True,
        }
    )
    round_trip(child)
    expect(choice).to_have_attribute("aria-checked", "false")
    assert (
        page.request.get(
            child.evaluate("new URL('api/state', document.baseURI).href")
        ).json()["events"]
        == []
    )
    page.unroute(event_url)

    child.locator(".lf-fp-threads").click()
    panel_settled(child, view="threads")
    page.keyboard.press("Escape")
    panel_settled(child, open=False)
    page.keyboard.press("Escape")
    expect(sample).to_be_focused()


def test_share_copies_access_after_a_bare_reload(browser, serve):
    """The copied address opens the viewed version and passage in a fresh browser."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url + "&view=reading#p30")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    expect(page).not_to_have_url(re.compile(r"[?&]t="))
    page.reload()
    wait_until_ready(page)
    panel_menu(page).get_by_role("menuitem", name="Copy link").click()
    expect_panel_says(page, "Link copied")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert parse_qs(urlsplit(copied).query) == {
        "t": parse_qs(urlsplit(url).query)["t"],
        "view": ["reading"],
    }
    assert urlsplit(copied).path == urlsplit(url).path
    assert urlsplit(copied).fragment == "p30"
    with browser.new_context() as context:
        recipient = open_page(browser, copied, context=context)
        expect(recipient.locator("#p30")).to_be_in_viewport()
        expect(recipient).not_to_have_url(re.compile(r"[?&]t="))


@pytest.mark.parametrize(
    "archetype", CONTROL_ARCHETYPES, ids=lambda archetype: archetype["name"]
)
def test_each_control_archetype_holds_its_neighbours_still(browser, serve, archetype):
    """Each row mechanism holds its other controls still across its causal transition."""
    # The synthetic page composes every mechanism a page can author, and carries the
    # existing comment the margin entry's row is made of. An archetype naming another
    # source is one whose causal state cannot coexist with that composed page, or whose
    # mechanism lives only in a shipped gallery or under a page-wide opt-in.
    source = archetype.get("source")
    page = open_page(
        browser,
        serve(source)
        if source
        else serve(
            CONTROL_STABILITY_PAGE,
            media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Does the narrower proof still cover every control?",
                    "anchor": {"section": "stable-suggestion"},
                }
            ],
        ),
    )
    page_at_rest(page)
    if disclosure := archetype.get("open"):
        page.locator(disclosure).click()
    page.evaluate(DEFINE_BOXES)
    control = page.locator(archetype["target"])
    expect(control).to_be_visible()
    # Playwright's click may scroll its target into view. Finish that navigation
    # before holding the positions the press itself must preserve.
    control.scroll_into_view_if_needed()
    page_at_rest(page)
    before = control.evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"], f"{archetype['name']} has no neighbouring control to hold"

    if option := archetype.get("option"):
        control.click()
        page.get_by_role("option", name=option, exact=False).click()
    else:
        control.click()
    round_trip(page)
    page_at_rest(page)
    after = page.evaluate("() => window.__lfBoxes()")
    assert any(box is not None for box in after), (
        f"{archetype['name']} leaves no neighbouring control to measure after its press"
    )
    moved = displaced(before, after)
    assert not moved, (
        f"pressing the {archetype['name']} control moved its neighbours:\n  "
        + "\n  ".join(moved)
    )


def test_a_recorded_move_is_acknowledged_in_the_panel_and_nowhere_else(browser, serve):
    """The page has one place for brief news. A gesture's acknowledgement used to arrive
    as both a count and a toast in the opposite corner. The panel's field says it now:
    "Moved to Done — sent" stands in for its words while it lasts, the live region hears
    the same sentence, and the field's own words return when it fades."""
    page = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")
    assert "Moved to Done" not in panel_says(page)

    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect_panel_says(page, "Moved to Done — sent")
    expect(page.locator(".lf-live")).to_have_text("Moved to Done — sent")
    assert page.locator(".lf-toast").count() == 0, "a second surface says the news"
    round_trip(page)

    # The field's own words come back once the notice has had its moment.
    expect_panel_says(page, "Moved to Done", shown=False)


def test_all_pages_opens_a_neighbour_in_a_tab_of_its_own(
    browser, serve, other_leaf, one_user, tmp_path
):
    """A neighbour's row in All pages opens that page in a tab of its own, at its live
    root, leaving this one where it was, All pages open. This page's own row carries the
    work behind it, which is what tells two rows apart when their titles are alike."""
    other_url, _ = other_leaf
    url = serve(LONG_PAGE)
    record_claim(
        serve.page_dir,
        id="s-self",
        cwd=str(tmp_path / "self-work"),
    )
    page = open_page(browser, url, context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    pages = page.locator(LEAVES)
    self_row = pages.locator(".lf-fp-page:not([href])")
    expect(self_row).to_have_attribute(
        "title", re.compile(rf"^long\n{re.escape(str(tmp_path / 'self-work'))}\n")
    )
    link = pages.locator("a.lf-fp-page", has_text="The other leaf")
    destination = link.get_attribute("href")
    # The new tab keeps the other page's live root, authorized by the key its link
    # carried, rather than being redirected onto one stamped version.
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    tab = opened_tab(page, destination, link.click)
    # The arrival leaves the key in the cookie and the bare address in the tab.
    expect(tab).to_have_url(f"{other_url}/")
    tab.close()
    expect(pages).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)


def test_leaves_keep_focus_through_reordering_and_stay_in_the_list_on_removal(
    browser, serve, live_leaf, one_user
):
    """Keyed rows preserve a surviving link, and a removed link leaves the user in All
    pages, where the walk goes on from the list."""
    second_url, _ = live_leaf("second", "Middle leaf")
    _, other_dir = live_leaf("other", "The other leaf")
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    rows = page.locator(f"{LEAVES} a.lf-fp-page")
    expect(rows).to_have_count(2)
    rows.nth(1).focus()
    page.evaluate("window.focusedLeaf = document.activeElement")

    live_leaf("first", "A first leaf")
    told(page)
    expect(rows).to_have_count(3)
    expect(rows.nth(2).locator(".lf-fp-label")).to_have_text("The other leaf")
    assert page.evaluate(
        "focusedLeaf === document.activeElement && focusedLeaf.isConnected"
    )

    declare(other_dir, "idle")
    told(page)
    expect(rows).to_have_count(2)
    expect(rows.nth(1).locator(".lf-fp-label")).to_have_text("Middle leaf")
    assert page.locator(LEAVES).evaluate(
        "view => view.contains(document.activeElement)"
    ), "the leaving row dropped the user out of All pages"
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    destination = rows.nth(1).get_attribute("href")
    assert destination is not None and destination.startswith(f"{second_url}/?t=")
    opened_tab(page, destination, lambda: page.keyboard.press("Enter"))


def test_a_leaf_served_at_a_new_address_keeps_its_row_and_focus(
    browser, serve, other_leaf, one_user
):
    """A row is the page it names, and its link is wherever that page is served now. A
    neighbour whose server restarts on another port keeps its row and the focus on it,
    and Enter opens the page at the new address. Keyed by address, the restart read as
    one page leaving and another arriving: the focused link was removed and focus fell
    back to the drawer."""
    old_url, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    row = page.locator(f"{LEAVES} a.lf-fp-page")
    expect(row).to_have_count(1)
    row.focus()
    page.evaluate("window.focusedLeaf = document.activeElement")

    # The page hears nothing from the old server stopping until the new one has
    # published its row, so its next reading moves the neighbour from one address to
    # the other.
    reads = CutOff().hold(page)
    _until(
        page,
        lambda traffic: traffic.asked == traffic.heard,
        "heard every state read it asked before the cut",
    )
    # The recovery a taken port's refusal names: with the service record deleted, the
    # restarted server derives its address again, and binds past the port still taken.
    hosting_model.cmd_stop(other_dir)
    (other_dir / SERVICE_FILE).unlink()
    with socket.create_server(("127.0.0.1", urlsplit(old_url).port)):
        new_url = hosting_model.start_server(
            other_dir, persistent=True, harness=None
        ).url.split("?")[0]
    assert urlsplit(new_url).port != urlsplit(old_url).port
    wait_for(
        lambda: [entry["url"] for entry in presence_model.other_leaves(serve.page_dir)],
        lambda urls: [url.split("?")[0] for url in urls] == [new_url],
        failure="the restarted neighbour never published its row",
    )
    reads.restore()
    told(
        page,
        until=lambda state: (
            [entry["url"].split("?")[0] for entry in state["others"]] == [new_url]
        ),
    )

    destination = row.get_attribute("href")
    assert destination is not None and destination.startswith(f"{new_url}?t=")
    assert page.evaluate(
        "focusedLeaf === document.activeElement && focusedLeaf.isConnected"
    ), "the restarted page's row lost its node or its focus"
    opened_tab(page, destination, lambda: page.keyboard.press("Enter"))


def test_all_pages_takes_the_keyboard(browser, serve, live_leaf, one_user):
    """All pages is a list, and a user walks it without reaching for the mouse: g L
    opens it, up and down step between its links and clamp at the ends, Home and End
    reach the ends, Enter opens the focused one in its own tab, and Esc gives that press
    back — the user is returned to the reading place they pressed `g L` from."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    rows = page.locator(f"{LEAVES} a.lf-fp-page")
    # Titles order the list, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-fp-label")).to_have_text("A second leaf")
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped at the end, never wrapped to the top
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    # Enter is the browser's own on a link, which is why the row is one.
    page.keyboard.press("ArrowDown")
    destination = rows.nth(1).get_attribute("href")
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    tab = opened_tab(page, destination, lambda: page.keyboard.press("Enter"))
    expect(tab).to_have_url(f"{other_url}/")
    tab.close()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    # One press in, one Escape out, and what the Escape gives back is exactly what the
    # press took: the reading place `g L` was pressed from.
    assert page.evaluate("() => document.activeElement === document.body")


@pytest.mark.watch_shifts
def test_a_newer_wheel_supersedes_a_panel_resize_landing(browser, serve):
    """A focused Threads row belongs to the reader's newer scroll while resize waits.

    Native scroll keeps focus on the row. Hold the actual frame handoff so the
    resize starts with that title visible and the wheel moves it away before the
    correction runs; wheel-before-resize exercises a different ownership order.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=24))
    resized(page, 1000, 640)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    threads = page.locator('.lf-fp-view[data-view="threads"]:not([data-leaving])')
    for _ in range(6):
        page.keyboard.press("ArrowDown")
    title = threads.locator(".lf-fp-thread").nth(5)
    rendered(page)
    expect(title).to_be_focused()
    with held_frames(page):
        page.evaluate(
            "addEventListener('resize', () => { window.panelResizeObserved = true; }, "
            "{once: true})"
        )
        page.set_viewport_size({"width": 1100, "height": 640})
        page.wait_for_function("window.panelResizeObserved === true", polling=50)
        box = threads.bounding_box()
        assert box
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        start = threads.evaluate("node => node.scrollTop")
        page.mouse.wheel(0, 2000)
        page.wait_for_function(
            "start => document.querySelector("
            "'.lf-fp-view[data-view=threads]').scrollTop > start + 20",
            arg=start,
            polling=50,
        )
        away = threads.evaluate("node => node.scrollTop")
        assert title.evaluate(
            "node => node.getBoundingClientRect().bottom < "
            "node.closest('.lf-fp-view').getBoundingClientRect().top"
        ), "the native wheel did not move the focused title out of view"
        expect(title).to_be_focused()
    rendered(page)
    assert threads.evaluate("node => node.scrollTop") == pytest.approx(away, abs=1)
    expect(title).to_be_focused()


@pytest.mark.watch_shifts
def test_the_feature_gallery_has_no_serious_wcag_a_or_aa_violations(browser, serve):
    """Axe covers semantic failures the render gate cannot see: an unnamed control,
    an invalid role relationship, or a contrast failure can occupy a perfectly good
    box and still shut a user out. Keep the scope to WCAG A/AA and actionable
    serious/critical findings; layout and accessibility-tree snapshots belong to
    specific regressions, not a baseline that changes with every restyle. The feature
    gallery is the authored page with the broadest real UI. The specialist package
    pages get one 420px Axe reading in the exported corpus; focused tests own the live
    chrome surfaces this page does not open.

    A phone's width because what a box does there is a different question and not a
    smaller one: the column is 372px, so a block that had room at a desk starts
    scrolling, and a scrolling box with no way into it from the keyboard is a user
    reading half of every line of code. Nothing at 1200 says a word about it."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    findings = []
    for color_scheme in ("light", "dark"):
        page.emulate_media(color_scheme=color_scheme)
        for width in (1200, 420):
            resized(page, width, 900)
            violations, report = serious_axe_violations(page)
            if violations:
                findings.append(f"[{width}px {color_scheme}]\n{report}")
            if unread := overlapped_words(page):
                findings.append(
                    f"[{width}px {color_scheme}] no contrast read under a box that paints "
                    "nothing: " + ", ".join(unread)
                )

    assert findings == [], "\n\n".join(findings)


# Each scheme and each width once: a contrast failure belongs to a scheme and a
# scrolling box to a width, and neither has been seen to need the other.
@pytest.mark.parametrize(("width", "color_scheme"), [(1200, "light"), (420, "dark")])
def test_the_chrome_a_key_opens_has_no_serious_violations(
    browser, serve, other_leaf, color_scheme, width
):
    """The feature-gallery sweep above reads broad authored UI with the chrome shut: it
    never presses a key, so the panel's views, its field, the leaf's menu and its
    Versions, the command reference and the sequence's chips are surfaces four readings
    pass straight over. A `role="list"` whose children were not all list obligations shipped
    through it, green every time.

    One page because the chrome is the same on every document. What varies here is which
    of the chrome's own surfaces is open — and the scheme and the
    width, which are the two axes that sweep carries and this one has to carry too. Dropped,
    they cost this test the dark palette entirely: the token these very sweeps caught was
    left failing on the dark half, because nothing here ever rendered it.

    Each surface is opened by its own key, which is also the assertion that it can be, and
    each is proved open before axe reads it — a sweep over a surface that never opened
    is a green that means nothing, which is the shape `tests/AGENTS.md` names."""
    url = serve(ADDRESSED_PAGE, comments=1)
    stamp_page(serve.page_dir, ADDRESSED_PAGE, "two")
    page = open_page(browser, url)
    resized(page, width, 900)
    page.emulate_media(color_scheme=color_scheme)
    told(page, until=lambda state: bool(state["others"]))

    def sweep(where):
        violations, report = serious_axe_violations(page)
        assert violations == [], f"{where}: {report}"

    sweep("the page as it arrives")

    # Threads, and then the thread a walk of it opens, whose view puts the user in its
    # reply box.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    # Read mid-slide, the panel's words stand past the window's edge, where axe reads no
    # contrast for them and the sweep passes them unread.
    panel_settled(page, view="threads")
    sweep("standing in Threads")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    panel_settled(page, view="thread")
    expect(panel_field(page)).to_be_focused()
    sweep("standing in a thread's reply box")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The page comment, which `c` puts the user in with nothing on the page to comment on.
    page.keyboard.press("c")
    expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()
    sweep("standing in the page comment")
    page.keyboard.press("Escape")

    # All pages and On me, the panel's other views. Waited out rather than pressed past:
    # the close is animated, so the next surface would otherwise be read with this one
    # still leaving behind it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    sweep("standing in All pages")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    sweep("standing in On me")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The leaf's menu, and its Versions, each read once its fade has finished.
    panel_menu(page)
    panel_settled(page, open=False)
    sweep("in the leaf's menu")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    open_versions(page)
    expect(page.locator(".lf-fp-version").first).to_be_visible()
    panel_settled(page, open=False)
    sweep("in the versions menu")
    # Escape steps back to the menu's root, and then puts the menu away.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-menu")).to_be_hidden()

    # The command reference, which is a dialog and owes the most of any of them.
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    search = page.locator(".lf-command-reference-search input")
    assert search.evaluate(
        "input => input.ariaControlsElements?.[0] === document.querySelector('.lf-command-reference-results')"
    )
    # The editor is inside Web Awesome's shadow root while its grid is outside it.
    # Chromium exposes the element-reference relationship to assistive technology;
    # axe reads only an aria-controls IDREF attribute, which cannot name across roots.
    cdp = page.context.new_cdp_session(page)
    try:
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()
    combobox = next(
        node
        for node in nodes
        if node.get("role", {}).get("value") == "combobox"
        and node.get("name", {}).get("value") == "Search commands"
    )
    assert any(
        prop["name"] == "controls"
        and [related.get("idref") for related in prop["value"].get("relatedNodes", [])]
        == ["lf-command-reference-results"]
        for prop in combobox["properties"]
    )
    violations, report = serious_axe_violations(page)
    violations = [
        violation
        for violation in violations
        if not (
            violation["id"] == "aria-required-attr"
            and len(violation["nodes"]) == 1
            and violation["nodes"][0]["target"]
            == [[".lf-command-reference-search", "#input"]]
            and [check.get("data") for check in violation["nodes"][0]["any"]]
            == [["aria-controls"]]
        )
    ]
    assert violations == [], f"in the command reference: {report}"
    page.keyboard.press("Escape")
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    page_at_rest(page)

    # And the sequence's generated target hints, painted over the visible page rather than
    # inserted into it.
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hints .lf-go-to-hint").first).to_be_visible()
    sweep("with the visible-target sequence armed")
    page.keyboard.press("Escape")


def test_the_stop_reading_names_a_control_with_nothing_drawn_on_it(browser, serve):
    """The stop reading distinguishes a real ring from a missing one.

    Reach a control by Tab, verify its real indication, then remove that indication. A
    tab's label supplies the distinct case where a box inside the focused stop carries its
    ring.
    """
    url = serve(LONG_PAGE, comments=2)
    page = open_page(browser, url)
    page.evaluate(RING_FOCUS_START)
    for _ in range(60):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => Boolean(document.activeElement?.matches('.lf-fp-threads'))"
        ):
            break
    else:
        raise AssertionError("Tab never reached the panel's Threads")
    rendered(page)

    assert seen_stop(page) is None, (
        "a panel button wearing the layer's own ring reads as a stop nothing draws, so "
        "the sample floor cannot trust this reading"
    )

    page.evaluate("""() => {
        const style = document.createElement('style');
        style.id = 'lf-ring-negative-control';
        style.setAttribute('data-controls', '');
        style.textContent =
          '.lf-fp-threads:focus { outline: none !important;'
          + ' box-shadow: none !important; }';
        document.head.append(style);
    }""")
    rendered(page)
    lost = seen_stop(page)
    assert lost and "lf-fp-threads" in lost, (
        "the ring was taken off a focused control and the reading still called it seen "
        f"({lost}), so the sample floor cannot report a missing indication"
    )

    # A tab's label carries focus inside its larger click target. Removing that child
    # ring must still report the focused tab, rather than crediting selection's fill.
    page = open_page(browser, serve(ROOT / "tests/fixtures/pages/root-tabs.html"))
    page.keyboard.press("Tab")
    page.locator(".lf-tab-btn").first.focus()
    assert seen_stop(page) is None
    name = page.locator(".lf-tab-name").first
    for property, value in (
        ("display", "none"),
        ("visibility", "hidden"),
        ("opacity", "0"),
    ):
        name.evaluate(
            "(node, [property, value]) => node.style.setProperty(property, value)",
            [property, value],
        )
        lost = seen_stop(page)
        assert lost and "lf-tab-btn" in lost, (property, lost)
        name.evaluate(
            "(node, property) => node.style.removeProperty(property)", property
        )
    page.evaluate("""() => {
        const style = document.createElement('style');
        style.setAttribute('data-controls', '');
        style.textContent =
          '.lf-tab-btn > .lf-tab-name { outline: none !important; }';
        document.head.append(style);
    }""")
    lost = seen_stop(page)
    assert lost and "lf-tab-btn" in lost, lost


def test_each_sampled_focus_ring_is_shown_whole_in_its_surface(
    browser, serve, live_leaf
):
    """Where the keyboard stands in each surface a key opens, the user sees its ring
    whole: not cut by a box that clips it, and not under a neighbour. And every stop
    in every example's ordinary Tab order, the feature gallery's included, shows
    keyboard focus with its rings whole, read by walking it once on arrival.

    `RING_CASES` walks the layer's surfaces by their real keys and stands on a sample in
    each; every ring drawn there is measured, not only the sample's. Which rings get a
    sample is the cases' choice rather than a census of the layer's rules, so a new ring
    needs no sample of its own; what every ring rule must do is draw with the ring's
    token, so the browser's answer for which rule drew a ring can tell it from a
    contour (`ring_rules`).
    A second version and a neighbouring leaf provide the two runtime states authored
    examples cannot carry themselves.
    """

    live_leaf("other", "The other leaf")
    # No ring moves under the default motion setting, so a settled sample reads the
    # value its rule declares. The reduced-motion case has a focused test above.
    faults, seen_faults = [], set()
    unseen = set()
    undrawn = set()
    opened = set()
    stops = 0
    unindicated = []
    assert not (missing := set(RING_EXAMPLES) - set(RING_EXAMPLE_FILES)), (
        "the ring cases name examples that no longer exist: "
        + ", ".join(sorted(missing))
    )
    for name, example in RING_EXAMPLE_FILES.items():
        # Serving the path lays in the example's shipped log and message widgets.
        # The chrome's page also carries a passage's thread, which the Page Map lists.
        anchored = [("triage-lede", "Migration 0041")] if name == RING_CHROME else ()
        url = serve(example, comments=2, anchored=anchored)
        if name == RING_CHROME:
            current_version = int(re.search(r"/v(\d+)\.html", url).group(1))
            next_version = current_version + 1
            _publish(
                serve.page_dir,
                next_version,
                example.read_text(),
                "Same page, said twice.",
            )
            url = url.replace(f"/v{current_version}.html", f"/v{next_version}.html")
        page = open_page(browser, url)
        walked_unindicated, walked_faults = _tab_walk(page, example.stem)
        unindicated += walked_unindicated
        faults += walked_faults
        if name not in RING_EXAMPLES:
            page.close()
            continue
        if name == "wt-merge":
            # The shipped steps now contain buttons, so the scrollable body needs no
            # stop of its own. Make this ring specimen prose-only; it still overflows
            # and must then lend the body a keyboard stop and its pane ring.
            resized(page, 1200, 600)
            page.locator("#merge-steps-pane button").evaluate_all(
                "buttons => buttons.forEach(button => "
                "button.replaceWith(document.createTextNode(button.textContent)))"
            )
            page.evaluate(
                """async () => {
                  const { reachScrollers } = await window.__lfCheckApi();
                  reachScrollers(document.body);
                }"""
            )
            expect(page.locator('#merge-steps-pane > [tabindex="0"]')).to_have_count(1)
        if name == "release-notes":
            page.locator("lf-shot").get_by_role(
                "button", name="Slider", exact=True
            ).click()
            # Ordinary element marks need a focusable sample for their conditional ring.
            page.locator("main p").first.evaluate(
                "node => { node.classList.add('lf-mark-el'); node.tabIndex = 0; }"
            )
        # Settled choices are user view state, so expose their focusable controls.
        for row in page.locator("lf-options[settled] > .lf-settled").all():
            if row.is_visible():
                row.click()
        page_at_rest(page)

        for scope, keys, cases in RING_CASES:
            if (samples := cases.get(name)) is None:
                continue
            # The posture the scope's own surface stands in, put back afterwards, so
            # the next scope reads the page this one was handed.
            posture = RING_SCOPE_WIDTH.get(scope)
            # Three rungs, because a scope can be three deep: a field or palette in a
            # view of the panel, then the view, then the page, so every scope starts
            # from the same page.
            for _ in range(3):
                page.keyboard.press("Escape")
            panel_settled(page, open=False)
            # A draft editor and captured source are conditional chrome: Tab can stand
            # on them only after their explicit doors have opened. Do that after the
            # scope reset, whose Escape presses would otherwise put the draft away.
            if scope in {"a settled decision", "a settled option"}:
                settled = page.locator("#comparison-policy[settled] > .lf-settled")
                expect(settled).to_be_visible()
                if settled.get_attribute("aria-expanded") != "true":
                    settled.click()
            if scope == "the page":
                pencil = any_draft_control(page, "edit").first
                if pencil.count() and pencil.is_visible():
                    pencil.click()
                # A source can sit behind nested disclosures. Open each visible ancestor
                # in document order so the innermost source becomes a real Tab stop.
                for source in page.locator("details:has(lf-text-document)").all():
                    if source.is_visible() and not source.get_attribute("open"):
                        source.locator(":scope > summary").click()
            page.evaluate(RING_FOCUS_START)
            if posture:
                resized(page, posture, RING_VIEWPORT[1])
                page_at_rest(page)
            if holding := RING_SCOPE_THREAD.get(scope):
                open_panel_thread_holding(page, holding)
            if opener := RING_SCOPE_OPENER.get(scope):
                page.locator(opener).first.click()
            for key in keys:
                page.keyboard.press(key)
                rendered(page)
            if scope == "a landed diff line":
                # Opening a collapsed file and loading its hunk finish after the key
                # handler returns. Read the ring once the walk has actually landed.
                expect(
                    page.locator("#pr-exact-patch [data-content] > [data-line]:focus")
                ).to_have_count(1)
            page_at_rest(page)
            if surface := RING_SCOPE_SURFACE.get(scope):
                assert page.locator(surface).count() == 1, (
                    f"{RING_SCOPE_OPENER.get(scope, ' '.join(keys))} did not open "
                    f"{scope} on {example.stem}, which "
                    "offers it"
                )
                opened.add(scope)

            where = f"in {scope} of {example.stem}"
            for selector, expected in samples:
                expected = {expected} if isinstance(expected, str) else set(expected)
                if selector:
                    target = page.locator(selector).first
                    # A sample can stand inside a container that is closed on arrival —
                    # the gallery holds its sections in tabs, and only one panel is open.
                    # Nothing inside a hidden panel is focusable, so the ring would read
                    # as undrawn for a control that paints it perfectly well. Ask the
                    # runtime's own disclosure route, so the surface a sample needs is
                    # derived from where it sits rather than from a page's tab order.
                    # `reveal` takes the intent its caller's gesture retained, and
                    # has no default (runtime/user-intent.js). This arrangement is
                    # not a user's delayed work that a later input may supersede —
                    # it is the test saying what the page must show next — so the
                    # intent it hands over is the one that always holds.
                    target.evaluate(
                        """async node => {
                          const elements = await window.__lfCheckApi();
                          await elements.reveal(node, () => true);
                        }"""
                    )
                    rendered(page)
                    page.keyboard.press("Tab")
                    target.focus()
                    # A note on the details shelf is reached from the element that
                    # names it (details-shelf.js), never by Tab, and is focused here as
                    # a screen reader moving to it would focus it.
                    assert target.evaluate(
                        "node => node.tabIndex >= 0"
                        " || node.closest('.lf-details-shelf') !== null"
                    ), f"{selector} {where} is not in sequential keyboard navigation"
                    expect(target).to_be_focused()
                    # A text field's focus is always visible, as a textarea's is, but
                    # Chrome gives `:focus-visible` to the node inside a delegating
                    # host and never to the host; its rings read `:focus`.
                    assert target.evaluate(
                        "node => node.matches(':focus-visible, leaf-text:focus')"
                    ), f"{selector} {where} did not inherit keyboard-visible focus"
                    page_at_rest(page)
                    if (lost := seen_stop(page)) is not None:
                        unseen.add(f"{where}: {lost}")
                for rule in expected & RING_REMOTE_CARRIER.keys():
                    page.locator(RING_REMOTE_CARRIER[rule]).evaluate(
                        "node => node.setAttribute('data-lf-ring-sample', '')"
                    )
                drawn = rings_drawn(page)
                page.locator("[data-lf-ring-sample]").evaluate_all(
                    "nodes => nodes.forEach(node => "
                    "node.removeAttribute('data-lf-ring-sample'))"
                )
                lit = [ring for ring in drawn if ring["here"]]
                undrawn.update(ring["who"] for ring in lit if not ring["rule"])
                found = {
                    rule
                    for rule in expected
                    for ring in lit
                    if ring["sample"] and rule in ring["rule"]
                }
                # One lasting defect is one finding, not one per stop: a ring worn by
                # something the sample is not moving — a decision's mark, a thread's element
                # mark — is read again at every stop it survives.
                for fault in ring_faults(drawn, where):
                    if fault not in seen_faults:
                        seen_faults.add(fault)
                        faults.append(fault)
                stops += 1
                assert found == expected, (
                    f"{selector or scope} {where} did not exhibit "
                    + ", ".join(sorted(expected - found))
                    + "; the rings drawn: "
                    + "; ".join(
                        f"{ring['who']} (rule {ring['rule']!r}, here {ring['here']}, "
                        f"sample {ring['sample']})"
                        for ring in drawn
                    )
                )
            if posture:
                for _ in range(3):
                    page.keyboard.press("Escape")
                panel_settled(page, open=False)
                resized(page, *RING_VIEWPORT)
                page_at_rest(page)

        page.close()

    assert not unindicated, "keyboard stops with no visible indication: " + "; ".join(
        unindicated
    )
    assert not unseen, (
        "a sample stood on a control and nothing on screen said where the keyboard was, "
        "so a user arriving by Tab has no way to tell: "
        f"{sorted(unseen)}"
    )
    # Across the causal cases, because a scope can be dead on a page with nothing to put
    # in it. What cannot happen is a scope no selected example ever opens or exercises: then its
    # keys are unread and everything below is silent about the controls behind them.
    expected_surfaces = {
        scope for scope, _keys, _cases in RING_CASES if scope in RING_SCOPE_SURFACE
    }
    missing = expected_surfaces - opened
    assert not missing, "no selected example reached " + ", ".join(sorted(missing))
    assert not faults, "\n  ".join(
        [f"{len(faults)} faults over {stops} samples:"] + faults
    )
    # Every ring the corpus paints is drawn by a rule using the ring's token. The samples
    # above, and every reading that credits a ring an ancestor wears, rest on telling a
    # ring rule from a contour that paints the same pixels.
    assert not undrawn, (
        "the corpus paints a focus ring on boxes no rule draws with --focus-ring or "
        "--focus-shadow, so no reading can tell it from pointer feedback: "
        + ", ".join(sorted(undrawn))
    )


@pytest.mark.parametrize("touch", (False, True))
def test_every_control_the_layer_offers_is_a_box_the_user_can_hit(
    browser, serve, touch
):
    """A press the user cannot land on is a capability the page does not have.

    Measured before --aim-floor existed, at 1200x900: a thread's Reopen and the panel's
    reaction chips stood at 20 and 22 pixels tall, the old banner's page preview at 23, and a
    version's Compare, a command in the reference, and a quote at around twelve by seven.
    Three controls reached the coarse-pointer block and the rest reached neither floor,
    so the same presses were small under a finger too.

    The sweep names no control. What makes a box an aim is that the runtime built it or
    stands in the runtime's own layer, and that the page under the pointer says a press
    lands there — so the next control the layer grows is held to this without anybody
    adding it to a list. Both pointers are asked, from the one token that states the
    floor, because a control comfortable under one and not the other is the fault this is
    about rather than a lesser version of it.

    The surfaces have to be opened for any of it to mean anything: seven of the eight
    controls at issue exist only inside a panel, a menu, a resolved thread or the
    reference, and a sweep of the page at rest would report a clean layer while every one
    of them was still six pixels tall. AIM_SURFACES is that assertion.
    """
    context = (
        browser.new_context(viewport={"width": 1200, "height": 900}, has_touch=True)
        if touch
        else None
    )
    # A preview record, because the badge it puts in the menu is one of the aims and
    # exists on no page that was not served by the preview script. The comment anchored
    # on a quote puts a quote in its thread.
    served = serve(
        AIM_PAGE,
        comments=2,
        anchored=[("aim-lead", "first view")],
        preview={
            "example": "corpus",
            "checkout": "fb77",
            "interaction": "user",
            "started": "2026-08-31T12:00:00+00:00",
            "input": {"source": "corpus", "authored": "fb77"},
        },
    )
    # An agent's answer on a thread the walk leaves open carries a reaction strip,
    # whose chips are aims. The walk resolves the first thread.
    second = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ][1]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": second,
            "text": "An answer to react to.",
        },
    )
    # A second version, published the way a page gets one and read from, so the versions
    # menu has an earlier version to compare against and Compare exists to be aimed at.
    _publish(serve.page_dir, 2, AIM_PAGE, "Same page, said twice.")
    page = open_page(browser, served.replace("/v1.html", "/v2.html"), context=context)
    floor = 44 if touch else 24
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch, (
        "the fixture did not reach the pointer medium this run is about, so the floor "
        "below is the other one's"
    )
    small, stood = [], set()
    for _ in _each_aim_surface(page, serve.page_dir):
        page_at_rest(page)
        small += page.evaluate(AIM_BOXES, floor)
        stood |= {s for s in AIM_SURFACES if page.locator(s).count()}
    assert not (missed := set(AIM_SURFACES) - stood), (
        f"the walk never stood {', '.join(sorted(missed))} up, so a clean answer would "
        f"be about a layer with those controls missing rather than about their size"
    )
    assert not small, (
        f"{len(set(small))} of the layer's controls are under the {floor}px floor a "
        f"{'coarse' if touch else 'fine'} pointer asks for:\n  "
        + "\n  ".join(sorted(set(small)))
    )
