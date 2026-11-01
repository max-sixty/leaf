"""Control stability, browser shell, accessibility, and ring tests."""

import re
from urllib.parse import parse_qs, urlsplit

import pytest
from browser.threads import open_panel_thread
from interact_support import (
    append_carried_log_record,
    declare,
)
from playwright.sync_api import expect
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
    Traffic,
    any_draft_control,
    expect_panel_says,
    held_frames,
    leaf_page,
    open_page,
    open_versions,
    opened_tab,
    page_comment,
    panel_field,
    panel_menu,
    panel_says,
    panel_settled,
    panel_view,
    resized,
    root_overflow,
    round_trip,
    scroll_settled,
    sending,
    show_resolved,
    stamp_page,
    told,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

from browser.controls import (
    LIVE_SAMPLES_PAGE,
    RING_NEW_STOP,
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
  <lf-option id="stable-choice-b" for="stable-tabs">Keep B</lf-option>
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


LEAVES = panel_view("leaves")


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
        # Different destinations keep the reference beside the pick visible;
        # a shared destination intentionally has no reference to hold still.
        "name": "option-pick",
        "target": "#stable-choice-a .lf-pick",
    },
    {
        "name": "tab",
        "target": "#stable-tabs .lf-tab-btn:nth-child(2)",
    },
    {
        # The playground's action row: Reset and the send beside each other under the
        # controls. The send is the press with something to prove — it posts the
        # configuration and turns to Undo choice, and a control that changes its own
        # words on the press is where a neighbour moves.
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
        "target": ".lf-vr-case:not([hidden]) .lf-shot-views button:nth-child(2)",
    },
    {
        "name": "visual-review-approval",
        "source": VISUAL_REVIEW_GALLERY,
        "target": ".lf-vr-case:not([hidden]) .lf-vr-approval",
    },
)


# The layer's focus floor (surfaces.css), which rings every box holding visible focus
# where no carrier wears the ring for it: the panel's own controls and rows among them.
FLOOR_RING = "[data-lf-focus-visible]:not(.lf-projected-mark)"


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
                (".lf-grip", FLOOR_RING),
                (".lf-fp-leaf", FLOOR_RING),
                (".lf-fp-on-user", FLOOR_RING),
                (".lf-fp-field leaf-text", ".lf-fp-field .lf-compose-field"),
            ),
            "feature-gallery": (
                (".lf-tab-btn", ".lf-tab-btn"),
                ("lf-option > .lf-pick", "lf-option:has(> .lf-pick"),
                (
                    any_owner_entry("suggestion", "accept") + ":visible",
                    FLOOR_RING,
                ),
                (".lf-draft-edit", ".lf-draft-edit"),
            ),
            "heat-loss": ((".lf-visual-action", FLOOR_RING),),
            # Working density, where a choice's gap is narrowest beside the next face.
            "notification-playground": (
                ("lf-playground input[type=radio]", ".choice:has"),
            ),
            "pr-walkthrough": (
                ("#pr-path-tree > summary", ".lf-visual-mark"),
                (
                    "#pr-flow-tab",
                    ".lf-rendered:has(> :is(lf-tab, lf-part)",
                ),
                ("lf-gloss:visible > .lf-gloss-mark", ".lf-gloss-mark"),
                (".lf-diff-search input", "wa-input::part"),
                ("lf-diff summary", FLOOR_RING),
                ("lf-diff code", ".lf-diff-frame"),
            ),
            "release-notes": (
                ("main p.lf-mark-el", ".lf-visual-mark"),
                (
                    'lf-shot .lf-shotcomparison [part~="handle"]',
                    "wa-comparison::part(",
                ),
                (".lf-shot-views button", FLOOR_RING),
            ),
            "wt-merge": (
                (
                    '[data-lf-reading-role="pane"] > [tabindex="0"]',
                    '[data-lf-reading-role="pane"]',
                ),
            ),
        },
    ),
    ("a landed diff line", ("]",), {"pr-walkthrough": ((None, FLOOR_RING),)}),
    (
        "an inline response",
        (),
        {"pr-walkthrough": (("leaf-text.lf-fab-input", ".lf-response-control"),)},
    ),
    # `g T` stands in Threads, on its view, and the walk's first step lands on a row.
    (
        "the Threads view",
        ("g", "Shift+t", "ArrowDown"),
        {RING_CHROME: ((None, FLOOR_RING),)},
    ),
    # A resolved thread's view, whose controls offer Reopen.
    (
        "a resolved thread",
        (),
        {"ship-review": ((".lf-fp-head .lf-fp-settle", FLOOR_RING),)},
    ),
    # The same walk with the panel shut lands in the margin's thread view, on the
    # thread itself rather than a control inside it.
    ("an inline thread", ("t",), {"ship-review": ((None, ".lf-page-thread"),)}),
    (
        "passage search",
        ("/",),
        {RING_CHROME: ((".lf-page-search-box input:visible", ".lf-fp-field"),)},
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
    # page at all. Located on a control first leaves the hint the keyboard is browsing on
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
        {RING_CHROME: ((".lf-fab-input", ".lf-compose-field"),)},
    ),
    # These controls live behind exact page-owned view states: a settled group's
    # disclosure, and the options it puts away.
    (
        "a settled decision",
        (),
        {
            "current-proposed-comparison": (
                ("#comparison-policy > .lf-settled", FLOOR_RING),
            )
        },
    ),
    (
        "a settled option",
        (),
        {
            "current-proposed-comparison": (
                ("#comparison-policy > lf-option > .lf-pick", FLOOR_RING),
            )
        },
    ),
    (
        "a contents link",
        (),
        {"feature-gallery": (("#bg-contents li a:visible", FLOOR_RING),)},
    ),
    # The reaction palette a message's strip opens. Its chips are the last boxes the
    # layer dresses in the chrome's chip face, and they are behind a press: the strip
    # shows a token nobody has pressed only while it is open, so a walk of the panel
    # that never opens one stands on the trigger and nothing under it.
    (
        "a reaction palette",
        (),
        {"ship-review": ((".lf-react-palette:popover-open .lf-react", FLOOR_RING),)},
    ),
    # On me opens on its view; the walk's first step lands on a card.
    ("On me", ("ArrowDown",), {"ship-review": ((None, FLOOR_RING),)}),
    ("All pages", ("g", "Shift+l", "ArrowDown"), {RING_CHROME: ((None, FLOOR_RING),)}),
    # The leaf's menu, opened by its press into its search; ↓ lands on a row.
    ("the leaf's menu", ("ArrowDown",), {RING_CHROME: ((None, FLOOR_RING),)}),
    # The menu's Versions, which `g V` opens holding focus itself; the walk's step
    # lands on its first row.
    (
        "the versions menu",
        ("g", "Shift+v", "ArrowDown"),
        {RING_CHROME: ((None, FLOOR_RING),)},
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
        {"ship-review": ((".lf-margin-preview .lf-resolve", FLOOR_RING),)},
    ),
    # Media in a message the panel's thread view draws stands its ring where it does on
    # the page: the panel insets only its own faces, not what Leaf's reader draws in its
    # outlet.
    (
        "message media",
        (),
        {"feature-gallery": ((f"{PANEL} .lf-message-media", FLOOR_RING),)},
    ),
    (
        "the Page Map dialog",
        ("g", "Shift+p"),
        {
            RING_CHROME: (
                (".lf-page-map-action:visible", FLOOR_RING),
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
    ".lf-diff-frame": "lf-diff code[data-lf-focus-visible] + .lf-diff-frame",
    # A pane draws its focused body's band inset over the body's cell (base.css).
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
    "the leaf's menu": '.lf-floating-panel[data-open="menu"]',
    "the versions menu": '.lf-floating-panel[data-open="versions"]',
    "the command reference": ".lf-command-reference[open]",
    "a reaction palette": ".lf-react-strip:has(> .lf-react-palette:popover-open)",
}


RING_SCOPE_OPENER = {
    "an inline response": "#pr-exact-patch .lf-diff-file-comment",
    "On me": ".lf-fp-on-user",
    "the leaf's menu": ".lf-fp-leaf",
    "a thread card": '.lf-margin-marker[data-lf-kinds~="comment"]',
    "a reaction palette": f"{PANEL_THREAD} .lf-msg-controls > .lf-react-trigger",
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
    "a resolved thread": ".lf-fp-head .lf-fp-settle.lf-reopen",
    "a reaction palette": ".lf-msg-controls > .lf-react-trigger",
    "message media": ".lf-message-media",
}


def open_panel_thread_holding(page, selector):
    """Open the panel's view of the first thread, open or resolved, whose view holds
    `selector`, walking Threads' rows in turn, the folded resolved ones unfolded."""
    show_resolved(page)
    keys = page.locator(".lf-fp-thread").evaluate_all(
        "rows => rows.map(row => row.dataset.key)"
    )
    for key in keys:
        show_resolved(page)
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
        # The stop's reading and the styles `seen_stop` asks for are two reads of
        # carriers the runtime may still be replacing, so both wait for its render.
        rendered(page)
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

    In turn rather than all at once, because they do not coexist: the panel stands one
    view at a time, the leaf's menu among them, and the reference is modal, so a sweep
    that waited for the last of them would meet a page that had put the others away.
    """
    comment, answered = [
        e["id"] for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    ][:2]
    # A resolved thread, which is the only state that has a Reopen to aim at. Resolving
    # moves the user on to the next open thread, so the resolved one is opened again.
    open_panel_thread(page, comment)
    page.locator(".lf-fp-head .lf-fp-settle").click()
    round_trip(page)
    open_panel_thread(page, comment)
    expect(page.locator(".lf-fp-head .lf-fp-settle")).to_have_class(
        re.compile(r"\blf-reopen\b")
    )
    yield
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The agent's answer in the other thread, with its reaction palette open: its chips
    # show only while it stands.
    open_panel_thread(page, answered)
    page.locator(f"{PANEL_THREAD} .lf-msg-controls > .lf-react-trigger").first.click()
    expect(
        page.locator(".lf-react-palette:popover-open .lf-react").first
    ).to_be_visible()
    yield
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The leaf's menu, and then its Versions, which hold Compare.
    panel_menu(page)
    yield
    panel_menu(page, "versions")
    yield
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

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
    threads = panel_view("threads")
    for name in ("overview", "resolved"):
        expect(views[name].locator(PANEL)).to_have_attribute("data-open", "threads")
    expect(views["overview"].locator(f"{threads} .lf-fp-thread").first).to_be_visible()

    expect(views["overview"].locator(f"{threads} .lf-fp-thread")).to_have_count(3)
    anchored = views["you"].locator(".lf-margin-preview")
    expect(anchored).to_be_visible()
    expect(anchored).to_have_attribute(
        "aria-label", "Thread for Agenda and room photo."
    )
    expect(anchored.locator(".lf-msg")).to_have_count(3)
    expect(anchored.locator("leaf-text")).to_be_visible()
    expect(views["resolved"].locator(f"{threads} .lf-fp-settled")).to_have_text(
        re.compile(r"^\s*Resolved\s*1\s*$")
    )
    expect(views["resolved"].locator(f"{threads} .lf-fp-settled")).to_have_attribute(
        "aria-expanded", "false"
    )
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
    # The thread's view goes to the passage it quotes with Show on page.
    show_on_page = child.locator(".lf-fp-head").get_by_role(
        "button", name="Show on page"
    )
    show_on_page.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    root_before = child.evaluate("scrollY")
    show_on_page.click()
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


def test_share_copies_access_after_a_bare_reload(browser, serve):
    """The copied address opens the viewed version and passage in a fresh browser."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url + "&view=reading#p30")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    expect(page).not_to_have_url(re.compile(r"[?&]t="))
    page.reload()
    wait_until_ready(page)
    panel_menu(page).locator('.lf-fp-item[data-row="share"]').click()
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


def test_a_recorded_move_is_announced_and_shown_only_where_it_was_made(browser, serve):
    """A widget's gesture shows where the user made it, and the margin's receipt says
    it was saved, so no passing notice repeats it: the live region alone hears "Moved
    to Done", and neither the panel's field nor a toast says it."""
    page = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")
    assert "Moved to Done" not in panel_says(page)

    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-live")).to_have_text("Moved to Done")
    round_trip(page)
    assert "Moved to Done" not in panel_says(page), "the panel's field repeats the move"
    assert page.locator(".lf-toast").count() == 0, "a second surface says the news"


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
    threads = page.locator(panel_view("threads"))
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
        unread = overlapped_words(page)
        assert unread == [], (
            f"{where}: no contrast read under a box that paints nothing: {unread}"
        )

    sweep("the page as it arrives")

    # Threads, and then the thread a walk of it opens, whose view puts the user in its
    # reply box.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    # Read mid-slide, the panel's words stand past the window's edge, where axe reads no
    # contrast for them and the sweep passes them unread.
    panel_settled(page, view="threads")
    sweep("focused in Threads")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    panel_settled(page, view="thread")
    expect(panel_field(page)).to_be_focused()
    sweep("focused in a thread's reply box")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The page comment, which `c` puts the user in with nothing on the page to comment on.
    page.keyboard.press("c")
    expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()
    sweep("focused in the page comment")
    page.keyboard.press("Escape")

    # All pages and On me, the panel's other views. Waited out rather than pressed past:
    # the close is animated, so the next surface would otherwise be read with this one
    # still leaving behind it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    sweep("focused in All pages")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    sweep("focused in On me")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The leaf's menu, and its Versions, each read once its fade has finished.
    panel_menu(page)
    sweep("in the leaf's menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    open_versions(page)
    panel_settled(page, view="versions")
    sweep("in the versions menu")
    # Escape steps back to the menu, and then puts it away.
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

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

    Reach a control by Shift+Tab, verify its real indication, then remove that
    indication. A tab's label supplies the distinct case where a box inside the focused
    stop carries its ring. The walk runs backward because the mark steps aside while
    the caret is in the panel's field, which a forward walk passes first.
    """
    url = serve(LONG_PAGE, comments=2)
    page = open_page(browser, url)
    page.evaluate(RING_FOCUS_START)
    for _ in range(60):
        page.keyboard.press("Shift+Tab")
        if page.evaluate(
            "() => Boolean(document.activeElement?.matches('.lf-fp-on-user'))"
        ):
            break
    else:
        raise AssertionError("Tab never reached the panel's On me mark")
    rendered(page)

    assert seen_stop(page) is None, (
        "a panel button wearing the layer's own ring reads as a stop nothing draws, so "
        "the sample floor cannot trust this reading"
    )

    page.evaluate("""() => {
        const style = document.createElement('style');
        style.id = 'lf-ring-negative-control';
        style.textContent =
          '.lf-fp-on-user:focus { outline: none !important;'
          + ' box-shadow: none !important; }';
        document.head.append(style);
    }""")
    rendered(page)
    lost = seen_stop(page)
    assert lost and "lf-fp-on-user" in lost, (
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
            match = re.search(r"/v(\d+)\.html", url)
            assert match is not None
            current_version = int(match.group(1))
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
                row.focus()
                page.keyboard.press("Enter")
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
                    page.locator("#pr-exact-patch .lf-diff-line > [data-line]:focus")
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
