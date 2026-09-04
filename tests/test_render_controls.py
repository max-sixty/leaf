"""Control stability, browser shell, accessibility, and ring tests."""

import json
import re
import threading

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import schema as schema_model
from leaf.registry import storage as registry_storage
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    ADDRESSED_PAGE,
    BANNER_WATCH,
    BOARD_PAGE,
    BOTH_STAMPS,
    COMMAND_HUB_PACKAGE,
    DEEP_FOCUS,
    DEFINE_BOXES,
    DIFF_PAGE,
    EXAMPLES,
    FEATURE_GALLERY,
    HOLD_MOTION,
    LONG_PAGE,
    MANY_DECISIONS_PAGE,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    PAGE_FIXTURES,
    PANEL_DIFF_MARKUP,
    RENDERED,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    RING_NAMES,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SCROLLED,
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    SUGGESTION_PAGE,
    TOKEN,
    UNBREAKABLE_PAGE,
    WIDE_DIFF_PAGE,
    CutOff,
    _publish,
    _traffic,
    _until,
    actions,
    banner_address,
    displaced,
    held_stale,
    leaf_page,
    live_url,
    live_watcher,
    mark_edges,
    nudge,
    open_page,
    opened_tab,
    page_at_rest,
    page_registry,
    panel_comment,
    panel_settled,
    record_claim,
    resized,
    ring_faults,
    rings_drawn,
    round_trip,
    serious_axe_violations,
    stamp_version_file,
    standing_ring,
    token_colour,
    told,
    undo,
    watched,
)

pytestmark = pytest.mark.nightly


CONTROL_STABILITY_PAGE = leaf_page(
    "control stability",
    """
<h1 id="control-target">Control stability</h1>
<lf-suggestion id="stable-suggestion">
  <lf-old>Keep the broad sweep.</lf-old>
  <lf-new>Keep one causal case per control archetype.</lf-new>
</lf-suggestion>
<lf-decision id="stable-options-decision"><h2>Which control should stay?</h2>
<lf-options id="stable-options" choose>
  <lf-option id="stable-choice-a" for="control-target">Keep A</lf-option>
  <lf-option id="stable-choice-b" for="control-target">Keep B</lf-option>
</lf-options></lf-decision>
<lf-tabs id="stable-tabs">
  <lf-tab id="stable-tab-a" label="First">First panel.</lf-tab>
  <lf-tab id="stable-tab-b" label="Second">Second panel.</lf-tab>
</lf-tabs>
<lf-command id="stable-command" label="Ship the control proof" phase="today">
  <lf-agent id="stable-command-worker" state="working">
    <strong>Worker</strong> Proving the command header.
  </lf-agent>
  <lf-task id="stable-command-task" status="active">
    <strong>Keep every control row still</strong>
  </lf-task>
</lf-command>
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
""",
    head='<meta name="lf-review" content="sign-off">',
)

# The rendered control mechanisms whose rows must keep their geometry across a press.
# `coverage` classifies the mechanisms rendered by the composed corpus; `target` is
# the one causal transition that proves the mechanism's stability contract.
CONTROL_ARCHETYPES = (
    {
        "name": "banner",
        "coverage": ".lf-banner-actions > button",
        "target": ".lf-signoff",
    },
    {
        # Accept and Reject share the resting row. A thread adds the third Button that
        # puts the secondary choices behind `…`; opening it must leave Accept still.
        "name": "margin-action",
        "coverage": ".lf-margin-action",
        "target": '[data-lf-margin-for="stable-suggestion"] > .lf-margin-more',
    },
    {
        "name": "option-pick",
        "coverage": "lf-option > [role=checkbox]",
        "target": "#stable-choice-a .lf-pick",
    },
    {
        "name": "tab",
        "coverage": ".lf-tabstrip > [role=tab]",
        "target": "#stable-tabs .lf-tab-btn:nth-child(2)",
    },
    {
        "name": "command-view",
        "coverage": ".lf-command-facts > [role=button]",
        "target": '#stable-command .lf-command-facts > [data-lf-view="running"]',
    },
    {
        # The diff's own header: a filter, a count, the soft-wrap switch, and the
        # next-unreviewed press, standing in one row. The switch is what makes this a
        # row at all — before it the next-unreviewed press had no control beside it and
        # the sweep passed it over — and it is also the press with something to prove,
        # because wrapping rewrites the height of every line under the row it is in.
        # Pressed by its own words, which is where a reader aims and what a native label
        # activation does either way.
        "name": "diff-tools",
        "coverage": ":is(.lf-diff-tools > button, .lf-diff-tools .lf-diff-wrap)",
        "target": "#stable-diff .lf-diff-wrap-label",
    },
    {
        # The review press shares its file's summary line without being inside it, since
        # a disclosure is a control and anything focusable within one is a control nested
        # in a control. Sharing the line puts it in this sweep: its two labels are
        # different words of different lengths, and one width for both is what keeps the
        # summary beside it from reflowing when it is pressed.
        "name": "diff-review",
        "coverage": ".lf-diff-review",
        "target": "#stable-diff .lf-diff-review",
    },
)
CONTROL_ROW_PRESS = (
    "button, summary, select, "
    "input:is([type=button], [type=checkbox], [type=radio], [type=reset], [type=submit]), "
    ":is([role=button], [role=checkbox], [role=menuitem], [role=menuitemcheckbox], "
    "[role=menuitemradio], [role=option], [role=radio], [role=slider], "
    "[role=spinbutton], [role=switch], [role=tab], [role=treeitem])"
)
CONTROL_ROW_NEIGHBOUR = CONTROL_ROW_PRESS + ", a[href]"


def _touch_drag(cdp, x, y, *, dx=0, dy=0, steps=14):
    """Send the touch stream a device produces, through Chromium's input boundary."""
    x, y = round(x), round(y)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]},
    )
    for step in range(1, steps + 1):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {
                        "x": x + dx * step // steps,
                        "y": y + dy * step // steps,
                    }
                ],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def test_a_page_asking_for_sign_off_records_the_approval(browser, serve):
    """The declared ask puts the button there, and the press posts `done`.

    Drive the shipped browser through the real POST door, since a button that merely
    looks right says nothing about the event the agent's loop receives.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page, errors = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    _until(page, lambda traffic: traffic.sends == 1, "held the approval in the wire")
    expect(button).to_be_disabled()
    expect(button).to_have_attribute("aria-busy", "true")
    button.dispatch_event("click")
    assert _traffic(page).sends == 1, "one approval press became two log events"

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["version"]) == ("done", "user", 1)
    assert event["text"]
    expect(button).to_be_disabled()
    assert errors == []
    page.close()


def test_an_approval_can_be_taken_back_like_any_other_reader_gesture(browser, serve):
    """Sign-off was one press with no second step, and the heaviest press on the page.

    A reader who meant Threads and hit the button beside it had approved the work, and
    nothing on the page or in the log would take it back: `done` was outside
    UNDOABLE_KINDS, so the append door refused the undo and the offer never reached the
    key line. It is a mark rather than speech, the way a reaction is — the agent is told
    the version is approved, not told something — so the withdrawal is the whole of the
    correction, and it goes through the outbox and the `z` row every other reader gesture
    uses.

    Read at all three levels the fault sat in, because two of them were separately wrong:
    the key line has to offer the press, the log has to take the undo, and the projection
    the button reads has to stop counting an approval a reader withdrew — `done` was a
    raw filter over the whole log, so an accepted undo would have left the button reading
    "✓ Version approved" for ever.

    And the tooltip, which is the other half of the same fault: it said "Approve this
    work" whether or not the work had been approved, so the one surface that could tell a
    reader what the press would do next described one they had already made.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page, errors = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    button.click()
    round_trip(page)
    expect(button).to_have_text("✓ Version approved")
    expect(button).to_have_attribute(
        "title", "Approved. Press z to take it back while it is still your last gesture"
    )

    undo(page)
    expect(button).to_have_text("Approve version")
    expect(button).to_be_enabled()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    kinds = [e["kind"] for e in events_model.read_events(serve.page_dir)]
    assert kinds[-2:] == ["done", "undo"], (
        f"the withdrawal is not in the log as its own event: {kinds}"
    )

    # And the press is available again, which is what makes this a correction rather than
    # a page the reader has spent.
    button.click()
    round_trip(page)
    expect(button).to_have_text("✓ Version approved")
    assert [e["kind"] for e in events_model.read_events(serve.page_dir)][-1] == "done"
    assert errors == []
    page.close()


def test_sign_off_waits_for_the_page_while_comments_stay_live(browser, serve):
    """Approval belongs to the presented page; runtime discussion does not wait for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    held = []
    page = browser.new_page()
    errors = watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        with page.expect_request("**/api/state*"):
            page.goto(serve(html), wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        assert held, "the positive control did not hold the first state response"
        button = page.locator(".lf-signoff")
        expect(button).to_be_visible()
        expect(button).to_be_disabled()

        page.locator(".lf-threads-toggle").click()
        expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(button).to_be_enabled()
        assert errors == []
    finally:
        page.close()


def test_a_page_that_asks_nothing_carries_no_terminal_control(browser, serve):
    """A page that only informs ends at Threads and offers no terminal action.

    The slot the approve button takes on a sign-off page stays empty here rather than
    picking up a neutral control, which is the fact a reader can see: an informational
    page asks them for nothing, so it hands them nothing to press.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The banner is built in one pass, so a control standing in it is what makes the
    # absence beside it worth reading rather than a row that never rendered.
    expect(page.locator(".lf-threads-toggle")).to_be_visible()
    assert page.locator(".lf-banner").evaluate("element => element.localName") == (
        "header"
    )
    expect(page.locator(".lf-banner-actions > *").last).to_have_class(
        re.compile(r"\blf-threads-toggle\b")
    )
    assert page.locator(".lf-signoff").count() == 0
    # Approval takes the slot beside Threads where a page asks for one, so the absence
    # above is the whole fact: the row is a control short rather than a control longer.
    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [1440, 1600])
def test_a_workspace_lands_one_responsive_layout_and_carries_the_column_to_it(
    browser, serve, width
):
    """Opening Threads never makes the page visit intermediate responsive postures.

    The gallery composes a left sidebar with the right living margin. At 1440px the
    final shell withdraws the sidebar; at 1600px it withdraws the full conversation
    margin. Animating the shell's width crossed either breakpoint in mid-flight, which
    made the column jump or reverse direction.

    Hold the runtime motion and seek it deterministically. The shell should already
    have its final width and responsive state at the opening frame, while the column
    starts where the reader left it and travels monotonically to its final position.
    """
    page, errors = open_page(browser, serve(FEATURE_GALLERY), init_script=HOLD_MOTION)
    resized(page, width, 900)
    initial = page.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            x: main.getBoundingClientRect().x,
            claim: getComputedStyle(main).getPropertyValue('--claim-map').trim(),
            sidebar: getComputedStyle(document.querySelector('aside.sidebar'))
              .getPropertyValue('--lf-sidebar-posture').trim(),
          };
        }"""
    )

    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "opening the workspace did not produce one controllable column motion"
    )
    final_layout = page.evaluate(
        """() => {
          const main = document.querySelector('main');
          return {
            shell: document.body.getBoundingClientRect().width,
            claim: getComputedStyle(main).getPropertyValue('--claim-map').trim(),
            sidebar: getComputedStyle(document.querySelector('aside.sidebar'))
              .getPropertyValue('--lf-sidebar-posture').trim(),
          };
        }"""
    )
    assert final_layout["shell"] == width - 420
    assert (initial["claim"], initial["sidebar"]) != (
        final_layout["claim"],
        final_layout["sidebar"],
    ), "the fixture crossed no responsive posture, so it cannot expose the regression"

    positions = page.evaluate(
        """() => {
          const motion = window.__lfHeld[0];
          const duration = motion.effect.getComputedTiming().duration;
          return [0, .25, .5, .75, 1].map(part => {
            motion.currentTime = duration * part;
            return document.querySelector('main').getBoundingClientRect().x;
          });
        }"""
    )
    assert positions[0] == pytest.approx(initial["x"], abs=1)
    if positions[-1] < positions[0]:
        assert positions == sorted(positions, reverse=True), positions
    else:
        assert positions == sorted(positions), positions
    assert all(
        min(positions[0], positions[-1]) <= position <= max(positions[0], positions[-1])
        for position in positions
    ), f"the reading column overshot its two settled positions: {positions}"

    page.evaluate("() => window.__lfHeld[0].finish()")
    page.wait_for_function(
        "() => document.querySelector('body > main').getAnimations().length === 0"
    )
    assert errors == []
    page.close()


def test_the_responsive_action_row_keeps_primary_actions_in_reach(browser, serve):
    """The row keeps state and every destination reachable at any width.

    A narrow viewport is not a cropped desktop toolbar, and it is not a strip of one
    scrolled off the side of the screen either. The two actions that complete the reading
    loop are in the first view from a 320px phone through a small tablet; everything else
    the width cannot hold goes behind one door, in the row's one order, reachable from the
    keyboard. Above the covering breakpoint the same row folds on the same terms, and the
    document never gains horizontal overflow.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page, errors = open_page(browser, url)

    button_widths = (
        "() => ['.lf-threads-toggle', '.lf-signoff'].map(selector => "
        "document.querySelector(selector).offsetWidth)"
    )
    resized(page, 1200, 844)
    wide_widths = page.evaluate(button_widths)
    resized(page, 320, 844)
    phone_widths = page.evaluate(button_widths)
    assert all(phone < wide for phone, wide in zip(phone_widths, wide_widths)), (
        "the covering row's tighter button padding was masked by wide reservations: "
        f"wide={wide_widths}, phone={phone_widths}"
    )
    resized(page, 1200, 844)
    assert page.evaluate(button_widths) == wide_widths, (
        "button reservations did not return to their wide measurements after the "
        "covering row was left"
    )

    def assert_primary_reach(width):
        resized(page, width, 844)
        boxes = page.evaluate(
            """() => Object.fromEntries(
              ['.lf-banner-status', '.lf-threads-toggle', '.lf-signoff'].map(selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return [selector, {left: r.left, right: r.right, width: r.width,
                                   top: r.top, bottom: r.bottom, height: r.height}];
              }))"""
        )
        for selector, box in boxes.items():
            assert box["width"] > 0 and box["height"] > 0, (
                f"{selector} collapsed at {width}px: {box}"
            )
            assert box["left"] >= 0 and box["right"] <= width, (
                f"{selector} is outside the first {width}px view: {box}"
            )
        if width <= 840:
            assert boxes[".lf-threads-toggle"]["height"] >= 40
            assert boxes[".lf-signoff"]["height"] >= 40
        assert page.evaluate(
            "() => document.documentElement.scrollWidth"
            "   === document.documentElement.clientWidth"
        ), "the banner made the page itself scroll sideways"
        # Nothing hanging off the row's own edge either, at any width: a row that cannot
        # fit its addresses folds them rather than hiding them past a clipped boundary.
        assert page.evaluate(
            "() => { const actions = document.querySelector('.lf-banner-actions');"
            "        return actions.scrollWidth <= actions.clientWidth; }"
        ), f"the row at {width}px still hid an address off its own edge"

    for width in (320, 390, 768, 900, 1200):
        assert_primary_reach(width)

    # The keyboard walks the row it can see and reaches the door standing at its start,
    # and the reading loop is in front of the reader without opening anything.
    resized(page, 320, 844)
    actions = page.locator(".lf-banner-actions")
    actions.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    walk = []
    for _ in range(6):
        page.keyboard.press("Tab")
        here = page.evaluate(
            """() => {
              const el = document.activeElement;
              return el && el.closest('.lf-banner-actions') ? el.className : null;
            }"""
        )
        if here is None:
            break
        walk.append(here.split(" ").pop())
    assert "lf-threads-toggle" in walk and "lf-signoff" in walk, (
        f"a Tab walk across the phone row missed the reading loop: {walk}"
    )
    ring_room = """el => {
      const shelf = el.parentElement.getBoundingClientRect();
      const button = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
      return {top: button.top - outset - shelf.top,
              left: button.left - outset - shelf.left,
              right: shelf.right - button.right - outset,
              bottom: shelf.bottom - button.bottom - outset};
    }"""
    room = page.locator(".lf-threads-toggle").evaluate(ring_room)
    assert all(space >= -0.01 for space in room.values()), (
        f"the phone row clipped its focused control's ring: {room}"
    )

    # Every address a busy row cannot hold is behind the door, in the row's own order, and
    # the row itself still has nothing to scroll. The identities do not matter to the
    # layout contract; the product controls all carry this same class and can arrive
    # asynchronously as comments, asks and page news do.
    page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          const last = document.querySelector('.lf-signoff');
          for (let i = 0; i < 5; i++) {
            const button = document.createElement('button');
            button.className = 'lf-ui lf-btn';
            button.textContent = `Secondary destination ${i + 1}`;
            actions.insertBefore(button, last);
          }
        }"""
    )
    behind = {}
    for width in (768, 900, 1600):
        assert_primary_reach(width)
        behind[width] = page.locator(".lf-banner-menu > *").count()
        expect(page.locator(".lf-banner-more")).to_be_visible()
    # Compared inside one layout. Across the covering breakpoint the two are not
    # comparable: below it the status has a line of its own and the addresses get the
    # whole width, so a phone row can legitimately hold more of them than a small laptop.
    assert behind[1600] < behind[900], (
        f"a widening window did not hand addresses back to the row: {behind}"
    )
    # Take the crowd away and the row takes every one of its own back, door and all.
    page.evaluate(
        """() => {
          for (const control of document.querySelectorAll('.lf-btn'))
            if (control.textContent.startsWith('Secondary destination'))
              control.remove();
        }"""
    )
    resized(page, 1600, 844)
    expect(page.locator(".lf-banner-more")).to_be_hidden()
    expect(page.locator(".lf-banner-menu")).to_be_empty()

    # The covering comments workspace locks the page behind it, and the row is no longer a
    # side door around that lock: a wheel over it reaches the document scrollport, which
    # the covering sheet has already stopped.
    resized(page, 320, 844)
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-panel")).to_be_visible()
    locked = actions.evaluate(
        """actions => {
          document.scrollingElement.scrollTop = 400;
          const before = document.scrollingElement.scrollTop;
          const event = new WheelEvent('wheel', {
            bubbles: true, cancelable: true, deltaY: 120
          });
          actions.dispatchEvent(event);
          return {before, after: document.scrollingElement.scrollTop,
                  overflow: getComputedStyle(document.scrollingElement).overflowY,
                  scrolled: actions.scrollLeft};
        }"""
    )
    assert locked == {
        "before": 400,
        "after": 400,
        "overflow": "hidden",
        "scrolled": 0,
    }, f"the action row bypassed the covering panel's page lock: {locked}"
    page.get_by_role("button", name="Close threads").click()
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()

    # A pinned wide page reserves the Latest chip before it first has news, and the phone
    # row folds it away like any other address it cannot hold. The door says the page has
    # been replaced while it holds that one, because news nobody can see is not news.
    pinned, pinned_errors = open_page(browser, url, pin=True)
    resized(pinned, 320, 844)
    expect(pinned.locator(".lf-latest-chip")).to_be_hidden()
    assert pinned.locator(".lf-latest-chip").evaluate("el => el.offsetWidth") == 0
    # A control the page has taken away is taken away wherever it stands. The row's own
    # rules state display for its box, and a rule that states it without excluding the
    # hidden ones puts an absent destination back between the reader and a real one.
    expect(pinned.locator(".lf-page-map-toggle")).to_be_hidden()
    assert pinned.locator(".lf-page-map-toggle").evaluate("el => el.offsetWidth") == 0
    expect(pinned.locator(".lf-banner-more")).not_to_have_attribute(
        "data-lf-news", re.compile(r".*")
    )
    (serve.page_dir / ".fixture-versions" / "v2.html").write_text(html)
    stamp_version_file(serve.page_dir, 2, "two")
    expect(pinned.locator(".lf-latest-chip")).to_have_class(
        re.compile(r"lf-news-shown")
    )
    seen = pinned.evaluate(
        """() => {
          const chip = document.querySelector('.lf-latest-chip');
          const door = document.querySelector('.lf-banner-more');
          return {onTheRow: chip.checkVisibility({visibilityProperty: true}),
                  behindTheDoor: door.hasAttribute('data-lf-news'),
                  doorName: door.getAttribute('aria-label'),
                  shown: chip.offsetWidth, needed: chip.scrollWidth};
        }"""
    )
    assert seen["onTheRow"] or seen["behindTheDoor"], (
        f"the phone banner took its page news out of the reader's sight: {seen}"
    )
    pinned.locator(".lf-banner-more").click()
    expect(pinned.locator(".lf-banner-menu")).to_be_visible()
    chip_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth})"
    )
    assert chip_size["shown"] >= chip_size["needed"], (
        f"the folded phone news address clipped its words: {chip_size}"
    )
    pinned.keyboard.press("Escape")
    resized(pinned, 1200, 844)
    news_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth})"
    )
    assert news_size["shown"] >= news_size["needed"], (
        f"the shown desktop news address clipped its words: {news_size}"
    )
    assert pinned_errors == []
    pinned.close()


def test_a_wide_banner_spends_action_reach_before_status_copy(
    browser, serve, other_leaf
):
    """At laptop width, the row gives up addresses before the status gives up words.

    It used to be the other way round. At 1280 the addresses took their whole intrinsic
    room first and the sentence took whatever was left, which was 199px of a 497px line:
    "Claude last checked in 16m ago: W…". The offline line, the one that says what to do
    about the server being gone, came out as "Server offline — reconnectin…". A status
    readout that has stopped saying anything is worse than an address behind a menu, so
    the sentence has a floor of its own now and the row folds to respect it.

    The sentence may wrap to the two lines the banner has room for; what it may not do is
    lose its end. Above that floor the sentence takes every pixel the addresses leave, so
    a row with room to spare reads on one line.
    """
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    # The complete real action set, wherever the fold has put each of them: what this is
    # about is the pressure that set puts on the sentence beside it.
    on_the_row = page.evaluate(BANNER_ORDER)
    for wanted in ("All leaves", "Asks", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in on_the_row), (
            f"{wanted} was not on the row, so the fixture is short of the crowding this "
            f"test is about: {on_the_row}"
        )

    # Read the sentence, not a stand-in for it: these are the two longest lines the banner
    # writes, and the offline one is the whole reason this rule exists.
    fits = """(sentence) => {
      const status = document.querySelector('.lf-status-text');
      status.textContent = sentence;
      const actions = document.querySelector('.lf-banner-actions');
      const probe = document.createElement('span');
      probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap';
      probe.textContent = sentence;
      status.after(probe);
      const oneLine = probe.getBoundingClientRect().width;
      probe.remove();
      return {across: {shown: status.clientWidth, needed: status.scrollWidth},
              down: {shown: status.clientHeight, needed: status.scrollHeight},
              oneLine, shown: status.clientWidth,
              actions: {shown: actions.clientWidth, needed: actions.scrollWidth}};
    }"""
    for sentence in (
        "Claude last checked in 16m ago: Writing the page. Your comments are saved.",
        "Server offline — reconnecting. Keep this page open so pending changes can send.",
    ):
        read = page.evaluate(fits, sentence)
        # The pressure, said as the sentence outgrowing the box it is given rather than as
        # a ratio between them. The row's cap is the sentence's floor stated from the other
        # end (chrome-style), so a crowded row leaves the status its floor and no less —
        # a margin over that floor is a number the design will not pay, and the fixture's
        # own crowding is asserted where the row is read, below.
        assert read["oneLine"] > read["shown"], (
            f"the fixture put no pressure on the wide banner: {sentence!r} needs "
            f"{read['oneLine']}px on one line and the status box is {read['shown']}px, "
            "so the wrap this test is about never happened"
        )
        assert read["across"]["shown"] == read["across"]["needed"], (
            f"the wide banner cut {sentence!r} off its own edge: {read}"
        )
        assert read["down"]["shown"] >= read["down"]["needed"], (
            f"the wide banner clamped {sentence!r} past the lines it has: {read}"
        )
        assert read["actions"]["shown"] >= read["actions"]["needed"], (
            f"the row kept more addresses than it had room for: {read}"
        )

    # Above the floor the sentence is the row's, not a share of it: an address folding
    # away hands the whole of its room to the line rather than leaving a gap.
    room = page.evaluate(
        """() => {
          const status = document.querySelector('.lf-banner-status');
          const actions = document.querySelector('.lf-banner-actions');
          const banner = document.querySelector('.lf-banner');
          const style = getComputedStyle(banner);
          const inner = banner.clientWidth
            - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          return {inner, status: status.getBoundingClientRect().width,
                  actions: actions.getBoundingClientRect().width,
                  gap: parseFloat(style.columnGap)};
        }"""
    )
    assert room["status"] + room["actions"] + room["gap"] == pytest.approx(
        room["inner"], abs=1
    ), f"the banner left room standing between its status and its addresses: {room}"

    # The complete real action set still gets its words. Where it does not fit, the row
    # gives an address to its menu rather than squeezing the ones it keeps.
    crowded = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          const menu = document.querySelector('.lf-banner-menu');
          const more = document.querySelector('.lf-banner-more');
          const words = (control) => ({
            name: (control.getAttribute('aria-label') || control.textContent).trim(),
            shown: control.clientWidth, needed: control.scrollWidth});
          return {
            row: [...actions.children]
              .filter(c => c !== more && c.getClientRects().length).map(words),
            folded: menu.children.length,
            document: {shown: document.documentElement.clientWidth,
                       needed: document.documentElement.scrollWidth}};
        }"""
    )
    assert crowded["folded"], (
        "the wide row folded nothing, so it never reached the cap this test is about and "
        f"the sentence beside it was never competing for room: {crowded}"
    )
    clipped = [c for c in crowded["row"] if c["shown"] < c["needed"]]
    assert not clipped, f"the crowded row compressed the addresses it kept: {clipped}"
    assert crowded["document"]["shown"] == crowded["document"]["needed"], (
        f"the crowded row widened the document: {crowded}"
    )

    # The open panel and a version popup can overlap broadly. Once native focus leaves the
    # transient menu, it closes before painting over the next keyboard destination.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.keyboard.press("v")
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    needs = page.locator(".lf-needs")
    reached_needs = False
    for _ in range(20):
        if needs.evaluate("el => el === document.activeElement"):
            reached_needs = True
            break
        page.keyboard.press("Tab")
    assert reached_needs, "native Tab never reached the pending-reader panel control"
    expect(needs).to_be_focused()
    expect(menu).to_be_hidden()
    expect(page.locator(".lf-version")).to_have_attribute("aria-expanded", "false")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    assert errors == []
    page.close()

    # A control that settles its own decisions disappears while it still owns focus. Hand
    # the reader to the next standing address instead of silently dropping them on body.
    page, errors = open_page(browser, url, pin=True)
    resized(page, 1200, 900)
    (serve.page_dir / ".fixture-versions" / "v2.html").write_text(html)
    stamp_version_file(serve.page_dir, 2, "two")
    expect(page.locator(".lf-latest-chip")).to_have_class(re.compile(r"lf-news-shown"))
    answer_all = page.locator(".lf-answer-all")
    # The blanket answer decides its decisions one at a time, so the press owes one round
    # trip per decision the control counts. Read that number off the control's own face
    # rather than writing the fixture's arithmetic out here.
    owed = int(re.search(r"\((\d+)\)", answer_all.text_content()).group(1))
    assert owed > 1, (
        f"the fixture left the blanket answer a single trip, not a sequence: {owed}"
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    answer_all.focus()
    page.keyboard.press("Enter")
    _until(
        page, lambda traffic: traffic.sends == 1, "held the blanket answer in the wire"
    )
    expect(answer_all).to_have_attribute("aria-disabled", "true")
    expect(answer_all).to_be_focused()
    answer_all.dispatch_event("click")
    assert _traffic(page).sends == 1, "one blanket-answer press became two event runs"
    held[0].continue_()
    page.unroute("**/api/event")
    # Released, the press spends a whole trip on each remaining decision, so the last is
    # still in flight when the first has settled. Say so here rather than letting the
    # hide assertion absorb the transport: its budget is one repaint's worth, three
    # sequential trips outlast it on a loaded machine, and the red then reads as a
    # control that never went instead of a wait that was never stated.
    # `test_accept_all_decides_every_pending_suggestion` stages the same sequence through
    # each widget's own settle; this test is about where focus lands, so it names the
    # outbox instead.
    _until(
        page,
        lambda traffic: traffic.sends == owed and not traffic.pending,
        f"settled every one of the {owed} answers the blanket press owed",
    )
    expect(answer_all).to_be_hidden()
    landed = page.evaluate(
        """() => {
          const el = document.activeElement;
          return el && el.closest('.lf-banner-actions, .lf-banner-menu')
            ? el.className : (el && el.tagName);
        }"""
    )
    assert "lf-btn" in (landed or ""), (
        f"the focus transfer left the reader on {landed!r} rather than on an address"
    )
    assert errors == []
    page.close()


def test_the_versions_menu_hangs_from_the_chooser_that_opens_it(browser, serve):
    """An open versions menu keeps the two edges its anchor names, and no others.

    The rule states the menu's top under the button's bottom and its right against the
    button's right. The popover UA rule states the other two, `inset: 0` with
    `margin: auto`, and unless the rule takes those back the auto margins centre the box
    in the band between the anchored edges and the viewport's far corner: at 1200x900 a
    menu whose anchored top reads as satisfied still opened 400px further down the page
    and 450px in from the control that opened it. Both edges are therefore read against
    the button's own box rather than against numbers, because what the anchor promises is
    a relation and not a coordinate.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    chooser = page.locator(".lf-version")
    expect(chooser).to_be_enabled()
    chooser.click()
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    boxes = menu.evaluate(
        """menu => {
          const button = document.querySelector('.lf-version').getBoundingClientRect();
          const box = menu.getBoundingClientRect();
          return {button: {top: button.top, bottom: button.bottom, right: button.right},
                  menu: {top: box.top, right: box.right, left: box.left}};
        }"""
    )
    assert boxes["menu"]["top"] == pytest.approx(
        boxes["button"]["bottom"] + 6, abs=2
    ), f"the versions menu did not hang under the chooser's bottom edge: {boxes}"
    assert boxes["menu"]["right"] == pytest.approx(boxes["button"]["right"], abs=2), (
        f"the versions menu did not line up with the chooser's right edge: {boxes}"
    )
    assert boxes["menu"]["top"] >= boxes["button"]["bottom"], (
        f"the versions menu covered the chooser it hangs from: {boxes}"
    )
    assert errors == []
    page.close()


# The banner's addresses in the row's one order. The fold takes a run off the front of the
# row into the menu, so the menu's contents followed by the row's read straight through as
# that one order — which is the whole of what "one order" can be checked against, since a
# folded address is still on the row and still where the order says it is. The door itself
# is not an address, and a control the page has taken away is not one either.
BANNER_ORDER = """() => {
  const shelf = document.querySelector('.lf-banner-actions');
  const menu = document.querySelector('.lf-banner-menu');
  const more = document.querySelector('.lf-banner-more');
  return [...menu.children, ...shelf.children]
    .filter(control => control !== more &&
            getComputedStyle(control).display !== 'none' &&
            getComputedStyle(control).visibility !== 'hidden')
    .map(control => (control.getAttribute('aria-label') || control.textContent).trim());
}"""


def test_the_banner_reads_in_one_order_at_every_width(browser, serve, other_leaf):
    """The row says the same thing at 1440 that it says on a phone.

    It used to turn round at the covering breakpoint: Threads went from the far right of
    the banner to the far left, and approval — the page's one committing press — swapped
    ends with it, so a reader narrowing the window found every address somewhere else.
    What a narrow window may change is how many addresses stand on the row at once; the
    rest fold into the row's own menu, in this same order.

    Two things legitimately differ with width and neither is an order: the page map is a
    narrow window's stand-in for the margin's own markers, and a reserved news slot is not
    an address until it has news. So each width is held to being this one order with the
    addresses that width does not have taken out of it, rather than to a fixed list — a
    reversal fails that just as loudly, and a control appearing at the wrong seat fails it
    where a fixed list would only have said the list was different.
    """
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    expect(page.locator(".lf-signoff")).to_be_visible()
    expect(page.locator(".lf-answer-all")).to_be_visible()

    orders = {}
    for width in (1440, 860, 800, 390):
        resized(page, width, 900)
        orders[width] = page.evaluate(BANNER_ORDER)

    # One order, put as the thing it is: no two addresses ever swap. Held pair by pair
    # rather than against a list taken at one width, because the widths do not all show
    # the same addresses and a fixed list would then be failing about the page map rather
    # than about the order. A reversal breaks this on its first pair.
    first = {}
    for width, order in orders.items():
        for index, before in enumerate(order):
            for after in order[index + 1 :]:
                assert (after, before) not in first, (
                    f"{after!r} comes before {before!r} at {first[(after, before)]}px "
                    f"and after it at {width}px, so the banner reads in two orders: "
                    f"{orders}"
                )
                first.setdefault((before, after), width)
    assert len(first) >= 15, (
        f"too few addresses stood at these widths to have an order at all: {orders}"
    )

    # And the order it settled on: every address the page offers, with the reading loop
    # finishing the row beside the panel it opens.
    widest = max(orders.values(), key=len)
    for wanted in ("All leaves", "Asks", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in widest), (
            f"{wanted} was not on the row at all, so this order proves little: {widest}"
        )
    for width, order in orders.items():
        assert order[-1].startswith("Threads"), (
            f"the conversation no longer finishes the row at {width}px: {order}"
        )
    assert errors == []
    page.close()


def test_a_phone_banner_folds_its_addresses_into_one_menu(browser, serve, other_leaf):
    """A phone gets a menu, not a strip of row scrolled off the side of the screen.

    The row used to overflow horizontally with its scrollbar hidden, so four of its seven
    addresses were off a 390px screen with nothing but a half-clipped word to say they
    were there. Now the row folds: what does not fit goes behind one door, every address
    is reachable from the keyboard through it, and the row itself has nothing left to
    scroll."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
    page, errors = open_page(browser, url)
    resized(page, 390, 800)

    shelf = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          return {shown: actions.clientWidth, needed: actions.scrollWidth,
                  document: {shown: document.documentElement.clientWidth,
                             needed: document.documentElement.scrollWidth}};
        }"""
    )
    assert shelf["shown"] == shelf["needed"], (
        f"the phone row still hid addresses off its own edge: {shelf}"
    )
    assert shelf["document"]["shown"] == shelf["document"]["needed"], (
        f"the phone banner made the page itself scroll sideways: {shelf}"
    )
    more = page.locator(".lf-banner-more")
    expect(more).to_be_visible()
    folded = page.locator(".lf-banner-menu > *")
    assert folded.count() > 0, "nothing folded, so this test has no menu to walk"
    # The row keeps the reading loop and the door; everything else is behind it.
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    expect(page.locator(".lf-banner-actions > .lf-threads-toggle")).to_be_visible()

    # Every folded address, from the keyboard, through that one door. The press is the
    # popover's own invoker, so the menu opens and puts the reader on its first address
    # without anything here focusing it for them.
    want = folded.evaluate_all(
        """els => els.filter(el => getComputedStyle(el).display !== 'none' &&
                                   getComputedStyle(el).visibility !== 'hidden')
                     .map(el => (el.getAttribute('aria-label') || el.textContent).trim())"""
    )
    assert len(want) >= 2, f"only {want} folded, which walks nothing"
    more.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    expect(more).to_have_attribute("aria-expanded", "true")
    reached = []
    for _ in range(len(want) * 3):
        here = page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || !el.closest('.lf-banner-menu')) return null;
              return (el.getAttribute('aria-label') || el.textContent).trim();
            }"""
        )
        if here is None:
            break
        if here not in reached:
            reached.append(here)
        if len(reached) == len(want):
            break
        page.keyboard.press("Tab")
    assert reached == want, (
        f"a Tab walk through the phone banner's menu reached {reached}, not {want}"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(more).to_have_attribute("aria-expanded", "false")
    assert errors == []
    page.close()


def test_a_status_kind_change_is_announced_in_the_banners_own_words(browser, serve):
    """The dot going red is not an announcement.

    The banner flipped to the offline colour and rewrote its line while the live region
    went on holding whatever it last said, so a reader who is not watching the top of the
    window learned nothing. A kind changing — work starting, a turn ending, the server
    going — is what is worth interrupting for, and what it says is the banner's own
    sentence rather than a second account of it. The age moving and a count turning over
    are not kinds and stay out of the region."""
    url = serve(SUGGESTION_PAGE)
    page, errors = open_page(browser, url)
    live = page.locator(".lf-live")
    # The 503 below is deliberate, so the enriched status-and-URL entries `open_page`
    # collects are this test's own noise rather than a fault to assert the absence of.
    del errors
    expect(page.locator(".lf-banner .lf-dot.working")).to_be_visible()
    # The page arriving is the document's own announcement, not a change in it.
    assert live.text_content() == "", (
        f"the banner announced its first reading: {live.text_content()!r}"
    )

    held = []

    def refuse_state(route):
        held.append(route)
        route.fulfill(status=503, body="down")

    page.route("**/api/**", refuse_state)
    try:
        # A healthy page never asks without news, so give it one: the read that follows
        # is the one the route refuses.
        nudge(serve.page_dir)
        expect(page.locator(".lf-banner .lf-dot.offline")).to_be_visible()
        offline = page.locator(".lf-status-text").text_content()
        assert offline.startswith("Server offline"), (
            f"the banner's offline line has moved: {offline!r}"
        )
        expect(live).to_have_text(offline)
    finally:
        page.unroute("**/api/**")
    page.close()


def test_the_keyboard_reference_is_a_modal_tab_loop_and_returns_to_its_door(
    browser, serve
):
    """A dialog-shaped shortcut reference behaves like a dialog for the native Tab walk."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    door = page.locator(".lf-threads-toggle")
    door.focus()
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-help")
    expect(reference).to_be_visible()
    assert reference.evaluate("el => el.matches(':modal')"), (
        "the keyboard reference looked modal but left the page interactive behind it"
    )
    stops = reference.locator("input, button, [tabindex]:not([tabindex='-1'])")
    assert stops.count() >= 2, "the reference had no meaningful native Tab loop"
    for _ in range(stops.count() + 2):
        page.keyboard.press("Tab")
        assert reference.evaluate(
            "el => el.contains(document.activeElement)"
            "   || document.activeElement === document.body"
        ), "Tab escaped the keyboard reference onto the suspended page"
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(door).to_be_focused()
    assert errors == []
    page.close()


def test_motion_preference_changes_are_heard_without_reloading(browser, serve):
    """The JS motion contract follows a live media preference, like the CSS does."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    reading = """() => import('/runtime/motion.js').then(
      motion => ({reduced: motion.reducedMotion(), scroll: motion.scrollBehavior()}))"""
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate(reading) == {"reduced": True, "scroll": "instant"}
    step = page.evaluate(
        "() => (document.scrollingElement.clientHeight"
        " - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)) * 0.6"
    )
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the navigation factory kept its load-time motion preference"

    page.emulate_media(reduced_motion="no-preference")
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.evaluate(
        """() => {
          window.__lfFrames = [];
          window.requestAnimationFrame = callback =>
            (window.__lfFrames.push(callback), window.__lfFrames.length);
          window.cancelAnimationFrame = () => {};
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
        }"""
    )
    page.keyboard.press("d")
    assert page.evaluate("() => window.__lfFrames.length") > 0
    page.emulate_media(reduced_motion="reduce")
    page.evaluate(
        """() => {
          const frames = window.__lfFrames.splice(0);
          for (const callback of frames) callback(0);
        }"""
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "an active glide kept moving after the reader asked for reduced motion"
    assert errors == []
    page.close()


def test_coarse_pointer_chrome_gives_its_compact_controls_humane_aims(browser, serve):
    """Touch keeps Leaf's compact paint while expanding the boxes a finger works."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    try:
        page, errors = open_page(browser, serve(html, comments=1), context=context)
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
            "the touch fixture never reached Leaf's coarse-pointer rules"
        )

        primary = page.locator(".lf-threads-toggle, .lf-signoff")
        expect(primary).to_have_count(2)
        for index in range(primary.count()):
            box = primary.nth(index).bounding_box()
            assert box["height"] >= 43.9, f"a primary touch aim stayed at {box}"

        page.locator(".lf-threads-toggle").tap()
        panel_settled(page)
        # The key line is not among them: a touch device has no keyboard to advertise, so
        # the whole line stands down and takes its More control with it. That control used
        # to be half of what this counted, and the sheet's own foot is the honest other
        # half — a Send a finger presses, where More was a keyboard's way into a keyboard
        # reference.
        expect(page.locator(".lf-keyline")).to_be_hidden()
        compact = page.locator(
            ".lf-panel .lf-react:visible, .lf-panel-head .lf-btn:visible, "
            ".lf-panel-foot .lf-btn:visible"
        )
        assert compact.count() >= 2, (
            "the covering panel exposed no compact touch controls"
        )
        for index in range(compact.count()):
            box = compact.nth(index).bounding_box()
            assert box["width"] >= 43.9 and box["height"] >= 43.9, (
                f"a compact panel control kept a mouse-sized aim: {box}"
            )
        page.get_by_role("button", name="Close threads").tap()
        panel_settled(page, open=False)

        # Across the covering boundary the banner fits the same touch aims. Its shelf and
        # a keyboard ring remain inside the derived edge rather than centred through it.
        for width in (840, 841, 900, 1200, 1440):
            resized(page, width, 844)
            page.locator(".lf-threads-toggle").focus()
            geometry = page.locator(".lf-threads-toggle").evaluate(
                """control => {
                  const banner = control.closest('.lf-banner').getBoundingClientRect();
                  const shelf = control.parentElement.getBoundingClientRect();
                  const box = control.getBoundingClientRect();
                  const style = getComputedStyle(control);
                  const outset = parseFloat(style.outlineWidth) +
                    parseFloat(style.outlineOffset);
                  return {banner: {top: banner.top, bottom: banner.bottom},
                          shelf: {top: shelf.top, bottom: shelf.bottom},
                          ring: {top: box.top - outset, bottom: box.bottom + outset}};
                }"""
            )
            for item in ("shelf", "ring"):
                assert (
                    geometry[item]["top"] >= geometry["banner"]["top"] - 0.01
                    and geometry[item]["bottom"] <= geometry["banner"]["bottom"] + 0.01
                ), f"the wide coarse {item} escaped its banner at {width}px: {geometry}"

        # The browser's root is Leaf's page scrollport, and native touch beginning in
        # fixed chrome reaches it. The row itself has nothing to travel along: what it
        # cannot hold is behind its menu, so a finger dragged sideways across it moves
        # nothing rather than uncovering an address that was hiding off the edge.
        cdp = context.new_cdp_session(page)
        resized(page, 390, 700)
        page.wait_for_function(
            "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden'"
        )
        actions = page.locator(".lf-banner-actions")
        page.evaluate(
            """() => {
              const actions = document.querySelector('.lf-banner-actions');
              const last = document.querySelector('.lf-signoff');
              for (let i = 0; i < 3; i++) {
                const button = document.createElement('button');
                button.className = 'lf-ui lf-btn';
                button.textContent = `Secondary touch destination ${i + 1}`;
                actions.insertBefore(button, last);
              }
            }"""
        )
        crowded = actions.evaluate(
            "el => ({shown: el.clientWidth, needed: el.scrollWidth,"
            " folded: document.querySelector('.lf-banner-menu').children.length})"
        )
        assert crowded["folded"] >= 3 and crowded["shown"] == crowded["needed"], (
            f"the crowded touch row did not fold what it could not hold: {crowded}"
        )
        point = actions.bounding_box()
        x = point["x"] + point["width"] / 2
        y = point["y"] + point["height"] / 2
        page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
        _touch_drag(cdp, x, y, dy=-160)
        page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
        vertical = page.evaluate(
            "() => ({shelf: document.querySelector('.lf-banner-actions').scrollLeft,"
            " page: document.scrollingElement.scrollTop,"
            " overflow: getComputedStyle(document.scrollingElement).overflowY})"
        )
        assert (
            vertical["shelf"] == 0
            and vertical["page"] > 200
            and vertical["overflow"] != "hidden"
        ), f"a vertical touch over the row never reached the page: {vertical}"
        page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
        _touch_drag(cdp, x, y, dx=-160)
        horizontal = page.evaluate(
            "() => ({shelf: document.querySelector('.lf-banner-actions').scrollLeft,"
            " page: document.scrollingElement.scrollTop})"
        )
        assert horizontal["shelf"] == 0, (
            f"the row still had a strip of itself to drag along: {horizontal}"
        )

        resized(page, 1200, 700)
        status = page.locator(".lf-banner-status").bounding_box()
        page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
        _touch_drag(
            cdp,
            status["x"] + status["width"] / 2,
            status["y"] + status["height"] / 2,
            dy=-160,
        )
        page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
        assert page.evaluate("() => document.scrollingElement.scrollTop") > 200, (
            "the status half of the fixed banner remained a dead touch-scroll strip"
        )
        assert errors == []
    finally:
        context.close()


def test_coarse_pointer_resize_reach_stays_reachable_without_trapping_scroll(
    browser, serve
):
    """A touch edge is a reachable local grip, not a scroll-blocking invisible wall."""
    context = browser.new_context(
        viewport={"width": 390, "height": 800}, has_touch=True
    )
    try:
        page, errors = open_page(
            browser, serve(MANY_DECISIONS_PAGE, comments=12), context=context
        )
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
        cdp = context.new_cdp_session(page)

        def edge_geometry(region, edge):
            return page.evaluate(
                """([regionSelector, edgeSelector]) => {
                  const regionEl = document.querySelector(regionSelector);
                  const edgeEl = document.querySelector(edgeSelector);
                  const region = regionEl.getBoundingClientRect();
                  const edge = edgeEl.getBoundingClientRect();
                  const before = getComputedStyle(edgeEl, '::before');
                  const side = edgeEl.dataset.lfSide;
                  const lineWidth = parseFloat(before.width);
                  const lineCenter = side === 'right'
                    ? edge.left + parseFloat(before.left) + lineWidth / 2
                    : edge.right - parseFloat(before.right) - lineWidth / 2;
                  const seamCenter = side === 'right'
                    ? region.left + regionEl.clientLeft / 2
                    : region.right - parseFloat(getComputedStyle(regionEl).borderRightWidth) / 2;
                  const contentEdge = side === 'right'
                    ? region.left + regionEl.clientLeft
                    : region.right - parseFloat(getComputedStyle(regionEl).borderRightWidth);
                  return {region: {left: region.left, right: region.right},
                          edge: {left: edge.left, right: edge.right,
                                 top: edge.top, bottom: edge.bottom,
                                 width: edge.width, height: edge.height,
                                 hidden: edgeEl.hidden,
                                 min: Number(edgeEl.getAttribute('aria-valuemin')),
                                 max: Number(edgeEl.getAttribute('aria-valuemax')),
                                 now: Number(edgeEl.getAttribute('aria-valuenow'))},
                          contentEdge, lineCenter, seamCenter,
                          lineOpacity: Number(before.opacity),
                          viewport: document.documentElement.clientWidth};
                }""",
                [region, edge],
            )

        def swipe(x, y, *, dx=0, dy=-140):
            _touch_drag(cdp, x, y, dx=dx, dy=dy)

        def drag(edge, dx):
            x = round((edge["left"] + edge["right"]) / 2)
            y = round((edge["top"] + edge["bottom"]) / 2)
            _touch_drag(cdp, x, y, dx=dx, steps=1)
            page.wait_for_function(
                "() => !document.body.hasAttribute('data-lf-sizing')"
            )

        # At the product's 320px floor the comment sheet has no possible width to move
        # through, so it offers no inert separator. A reader standing on the grip lands on
        # its surviving close control before it disappears; the narrower tray still moves.
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        comments_edge = page.locator(".lf-panel > .lf-edge")
        comments_edge.focus()
        expect(comments_edge).to_be_focused()
        resized(page, 320, 800)
        assert comments_edge.evaluate("edge => edge.hidden")
        expect(page.locator(".lf-panel-head .lf-btn")).to_be_focused()
        assert comments_edge.get_attribute(
            "aria-valuemin"
        ) == comments_edge.get_attribute("aria-valuemax")
        threads = page.locator(".lf-threads")
        threads.evaluate("box => { box.scrollTop = 0; }")
        width_before = page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--lf-panel-w')"
        )
        panel_box = page.locator(".lf-panel").bounding_box()
        swipe(panel_box["x"] + panel_box["width"] / 2, 280)
        page.wait_for_function(
            "() => document.querySelector('.lf-threads').scrollTop > 0"
        )
        assert (
            page.evaluate(
                "() => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--lf-panel-w')"
            )
            == width_before
        )

        # The tray still has range at 320px, and its grip finishes sliding on screen.
        page.get_by_role("button", name="Close threads").click()
        panel_settled(page, open=False)
        banner_address(page, ".lf-decisions").click()
        panel_settled(page, open=False)
        expect(page.locator(".lf-decisions-panel")).to_have_class(
            re.compile(r"\bopen\b")
        )
        page_at_rest(page)
        narrow_decisions = edge_geometry(
            ".lf-decisions-panel", ".lf-decisions-panel > .lf-edge"
        )
        assert not narrow_decisions["edge"]["hidden"]
        assert narrow_decisions["edge"]["left"] >= -0.1, narrow_decisions
        assert (
            narrow_decisions["edge"]["right"] <= narrow_decisions["viewport"] + 0.1
        ), narrow_decisions

        # Exercise both mirrored owners in different layout postures. A swipe beside the
        # visible grip scrolls its list without moving the boundary; a horizontal drag on
        # the grip does move it and releases the sizing posture.
        for (
            name,
            width,
            open_button,
            region_selector,
            edge_selector,
            list_selector,
            dx,
        ) in (
            (
                "comments",
                390,
                ".lf-threads-toggle",
                ".lf-panel",
                ".lf-panel > .lf-edge",
                ".lf-threads",
                48,
            ),
            (
                "decisions",
                900,
                ".lf-decisions",
                ".lf-decisions-panel",
                ".lf-decisions-panel > .lf-edge",
                ".lf-decisions-panel .lf-tray-list",
                -36,
            ),
        ):
            resized(page, width, 800)
            page.locator(open_button).click()
            if name == "comments":
                panel_settled(page)
            else:
                panel_settled(page, open=False)
                expect(page.locator(region_selector)).to_have_class(
                    re.compile(r"\bopen\b")
                )
                page_at_rest(page)
            reading = edge_geometry(region_selector, edge_selector)
            edge = reading["edge"]
            assert edge["width"] >= 43.9 and edge["height"] >= 43.9, reading
            assert edge["left"] >= -0.1
            assert edge["right"] <= reading["viewport"] + 0.1
            if name == "comments":
                assert edge["left"] >= reading["contentEdge"] - 0.1, reading
            else:
                assert edge["right"] <= reading["contentEdge"] + 0.1, reading
            assert abs(reading["lineCenter"] - reading["seamCenter"]) <= 0.6, (
                f"the {name} grip's line left the panel seam: {reading}"
            )
            assert reading["lineOpacity"] > 0, f"the {name} touch grip was invisible"
            edge_control = page.locator(edge_selector)
            edge_control.evaluate("edge => edge.blur()")
            for _ in range(80):
                page.keyboard.press("Tab")
                if edge_control.evaluate("edge => document.activeElement === edge"):
                    break
            else:
                raise AssertionError(
                    f"the keyboard never reached the {name} touch grip"
                )
            standing = standing_ring(page)
            assert standing and not standing["cuts"] and not standing["covers"], (
                f"the {name} touch grip drew a clipped focus ring: {standing}"
            )
            mid_x = (edge["left"] + edge["right"]) / 2
            mid_y = (edge["top"] + edge["bottom"]) / 2
            assert page.evaluate(
                "([x, y]) => document.elementFromPoint(x, y)?.classList"
                ".contains('lf-edge')",
                [mid_x, mid_y],
            )
            assert not page.evaluate(
                "([x, y]) => document.elementFromPoint(x, y)?.classList"
                ".contains('lf-edge')",
                [mid_x, edge["top"] - 24],
            ), f"the {name} touch edge still trapped the whole sheet height"

            scroll_box = page.locator(list_selector)
            scroll_box.evaluate("box => { box.scrollTop = 0; }")
            assert scroll_box.evaluate("box => box.scrollHeight > box.clientHeight"), (
                f"the {name} list has no scroll range to exercise"
            )
            before = edge["now"]
            swipe(mid_x, edge["top"] - 24)
            page.wait_for_function(
                "selector => document.querySelector(selector).scrollTop > 0",
                arg=list_selector,
            )
            assert (
                int(page.locator(edge_selector).get_attribute("aria-valuenow"))
                == before
            )

            drag(edge, dx)
            after = int(page.locator(edge_selector).get_attribute("aria-valuenow"))
            assert edge["min"] <= after <= edge["max"]
            assert after < before, (
                f"the {name} grip did not narrow its region: {before} → {after}"
            )

        assert errors == []
    finally:
        context.close()


def test_forced_colors_restore_a_real_outline_to_shadow_focused_fields(browser, serve):
    """High-contrast mode does not erase the only visible sign of textarea focus."""
    context = browser.new_context(
        viewport={"width": 420, "height": 800}, forced_colors="active"
    )
    try:
        page, errors = open_page(browser, serve(LONG_PAGE), context=context)
        page.locator(".lf-threads-toggle").click()
        box = page.locator(".lf-general textarea")
        box.focus()
        expect(box).to_be_focused()
        focus = box.evaluate(
            "el => { const s = getComputedStyle(el);"
            " return {style: s.outlineStyle, width: s.outlineWidth}; }"
        )
        assert focus["style"] != "none" and focus["width"] != "0px", focus
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize(
    "archetype", CONTROL_ARCHETYPES, ids=lambda archetype: archetype["name"]
)
def test_each_control_archetype_holds_its_neighbours_still(browser, serve, archetype):
    """Each row mechanism holds its other controls still across its causal transition."""
    page, errors = open_page(
        browser,
        serve(
            CONTROL_STABILITY_PAGE,
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
    page.evaluate(DEFINE_BOXES)
    control = page.locator(archetype["target"])
    expect(control).to_be_visible()
    before = control.evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"], f"{archetype['name']} has no neighbouring control to hold"

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
    assert errors == []
    page.close()


def test_the_composed_corpus_declares_every_control_row_archetype(browser, serve):
    """The corpus keeps the declaration open to control mechanisms added later.

    The examples deliberately distribute those mechanisms across panels, so the sweep
    visits every outer tab rather than making the first page carry the whole vocabulary.
    """
    corpus = next(example for example in EXAMPLES if example.stem == "corpus")
    page, errors = open_page(browser, serve(corpus))
    page_at_rest(page)
    page.evaluate(DEFINE_BOXES)
    observed = set()
    undeclared = []
    labels = page.locator("#corpus > lf-tab").evaluate_all(
        "tabs => tabs.map(tab => tab.getAttribute('label'))"
    )
    assert labels, "the composed corpus has no panels to sweep"
    for tab_label in labels:
        page.get_by_role("tab", name=tab_label, exact=True).click()
        controls = page.locator(CONTROL_ROW_PRESS)
        for index in range(controls.count()):
            control = controls.nth(index)
            if not control.is_visible() or not control.is_enabled():
                continue
            if control.get_attribute("aria-disabled") == "true":
                continue
            neighbours = control.evaluate(NEIGHBOURHOOD, CONTROL_ROW_NEIGHBOUR)["names"]
            if not neighbours:
                continue
            matches = [
                archetype["name"]
                for archetype in CONTROL_ARCHETYPES
                if control.evaluate(
                    "(el, selector) => el.matches(selector)", archetype["coverage"]
                )
            ]
            label = control.evaluate(
                "(el) => el.tagName.toLowerCase() + ' '"
                "        + JSON.stringify((el.textContent || '').trim().slice(0, 24))"
            )
            if len(matches) != 1:
                undeclared.append(f"{tab_label}: {label}: {matches or 'no archetype'}")
            observed.update(matches)

    assert not undeclared, (
        "controls with neighbours need one archetype:\n  " + "\n  ".join(undeclared)
    )
    expected = {archetype["name"] for archetype in CONTROL_ARCHETYPES}
    assert observed == expected, (
        f"corpus reached {sorted(observed)}, expected {sorted(expected)}"
    )
    assert errors == []
    page.close()


def test_an_open_tab_reloads_before_posting_through_a_revendored_layer(browser, serve):
    """The layer epoch closes the gap between a stopped server and an open tab.

    Polls are refused so the stale click, not a preceding state read, discovers the
    change. Its old contract must append nothing and reload; the same real click then
    succeeds under the replacement contract.
    """
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)
    old_layer = page_registry(page)["$layer"]["generation"]
    cut = CutOff().hold(page)
    # A read that meets the cut-off, so the page's reads are known refused before the
    # server changes under it. The page reads when told the page moved, so tell it.
    with page.expect_request("**/api/state*"):
        nudge(serve.page_dir)

    old_server = serve.httpd
    address = old_server.server_address
    old_server.shutdown()
    old_server.server_close()
    project = serve.page_dir.parent / ".leaf"
    project.mkdir()
    (project / "theme.css").write_text(":root { --accent: rebeccapurple; }\n")
    initialized = CliRunner().invoke(
        cli_model.cli, ["page", "init", str(serve.page_dir)]
    )
    assert initialized.exit_code == 0, initialized.output
    new_layer = registry_storage.layer_generation(serve.page_dir)
    assert new_layer != old_layer
    replacement = hosting_model.LeafHTTPServer(
        address, http_model.handler_for(serve.page_dir, TOKEN)
    )
    threading.Thread(target=replacement.serve_forever, daemon=True).start()
    serve.servers.append(replacement)
    serve.httpd = replacement

    with page.expect_navigation(wait_until="load"):
        page.locator("#opt-stage").click()
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ] == []

    cut.restore()
    told(page)
    page.wait_for_function(BOTH_STAMPS)
    page.locator("#opt-stage").click()
    round_trip(page)
    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [(event["widget"], event["action"]) for event in actions] == [
        ("approach", "choose")
    ]
    assert errors == []
    page.close()


def test_a_self_eligibility_check_reads_state_before_its_optimistic_gesture(
    browser, serve, tmp_path, monkeypatch
):
    """The common send door must not mistake a gesture's paint for prior state."""
    monkeypatch.chdir(tmp_path)
    overlay = tmp_path / ".leaf"
    overlay.mkdir()
    standard = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())
    options = standard["lf-options"]
    options["x-state"]["choose"]["requires"] = {
        "target": "self",
        "awaiting": True,
    }
    (overlay / "registry.json").write_text(json.dumps({"lf-options": options}))
    url = serve(
        leaf_page(
            "self eligibility",
            '<h1 id="heading">Choose</h1><lf-decision id="pick-decision"><h2>Which option?</h2>'
            '<lf-options id="pick" choose>'
            '<lf-option id="pick-a">A</lf-option>'
            '<lf-option id="pick-b">B</lf-option></lf-options></lf-decision>',
        )
    )
    page, errors = open_page(browser, url)

    page.get_by_role("checkbox", name=re.compile(r"^choose one: A")).click()
    round_trip(page)

    expect(page.locator("#pick-a")).to_have_attribute("chosen", "")
    assert [event["action"] for event in actions(serve.page_dir)] == ["choose"]
    assert errors == []
    page.close()


def test_a_seat_conversation_leaves_the_pick_it_is_about_live(browser, serve):
    """The reader's own remark must not lock the control it is a remark about.

    A conversation standing in the widget's seat takes the decision off the reader's
    list — the banner stops counting it — but answers nothing, so the press that would
    answer it is still live. This is the browser half of the split, and the half the
    reader meets first: the POST door only sees a hand-posted event, while here
    `actionAvailable` paints the control and `sendAction` guards the press, and the
    module has already painted the answer by the time either runs. Reading the reader's
    list at this door therefore does not refuse the press so much as swallow it — the
    widget flips, nothing is logged, no notice fires, and the next poll puts it back with
    nothing anywhere saying why.

    The subject is the project widget SEATED_ASK_ENTRY declares rather than an entry out
    of the default package, because the pair the split needs — a visible ask and a seat
    of the widget's own — is a pair of declarations and not a tag. No shipped entry has
    carried both since 292de9c took `x-conversation` off `lf-options`, and the reading
    under test never asked which widget it was."""
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-decision id="pick-decision">'
            "<h2>Cap the retries?</h2>"
            '<lf-verdict id="pick" asks>Three attempts, then stop.</lf-verdict>'
            "</lf-decision>",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "pick"},
            "text": "neither — cap the retries instead",
        },
    )
    page, errors = open_page(browser, url)
    # Off the reader's list, which is the whole reason the two readings differ here.
    expect(page.locator(".lf-decisions")).to_have_text("Asks (0)")

    page.get_by_role("button", name="Accept").click()
    round_trip(page)

    expect(page.get_by_role("button", name="Accepted")).to_have_count(1)
    # The log is what holds this, and the control above cannot: the module paints the
    # answer before either guard runs, so with the wrong reading at this door the press
    # reads exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["settle"]
    assert errors == []
    page.close()


def test_a_runtime_cannot_adopt_a_new_registry_while_it_is_loading(browser, serve):
    """The runtime bytes and registry are one contract, even across a slow fetch."""
    url = serve(REPLAYED_PAGE)
    gate_registry_once = """
      if (!sessionStorage.getItem('lf-gated-registry')) {
        sessionStorage.setItem('lf-gated-registry', '1');
        const nativeFetch = window.fetch.bind(window);
        window.lfRegistryGate = new Promise(
          resolve => window.lfReleaseRegistry = resolve
        );
        window.fetch = (...args) => {
          const input = args[0];
          const requested = typeof input === 'string' ? input : input.url;
          if (new URL(requested, location.href).pathname === '/registry.json') {
            window.lfRegistryBlocked = true;
            return window.lfRegistryGate.then(() => nativeFetch(...args));
          }
          return nativeFetch(...args);
        };
      }
    """
    page, errors = open_page(
        browser,
        url,
        init_script=gate_registry_once,
        wait_until="domcontentloaded",
        upgraded=False,
    )
    page.wait_for_function("() => window.lfRegistryBlocked === true")
    old_layer = registry_storage.layer_generation(serve.page_dir)

    old_server = serve.httpd
    address = old_server.server_address
    old_server.shutdown()
    old_server.server_close()
    initialized = CliRunner().invoke(
        cli_model.cli, ["page", "init", str(serve.page_dir)]
    )
    assert initialized.exit_code == 0, initialized.output
    assert registry_storage.layer_generation(serve.page_dir) != old_layer
    replacement = hosting_model.LeafHTTPServer(
        address, http_model.handler_for(serve.page_dir, TOKEN)
    )
    threading.Thread(target=replacement.serve_forever, daemon=True).start()
    serve.servers.append(replacement)
    serve.httpd = replacement

    with page.expect_navigation(wait_until="load"):
        page.evaluate("() => window.lfReleaseRegistry()")
    page.wait_for_function(BOTH_STAMPS)
    assert page.evaluate("() => sessionStorage.getItem('lf-gated-registry')") == "1"
    assert errors == []
    page.close()


def test_a_marked_element_wears_the_same_stroke_on_every_side(browser, serve):
    """The mark is drawn in the one band of an element nobody else paints in.

    Both sides of an element's edge belong to somebody. Outside it, the mark is at
    the mercy of whatever encloses the element — a board is a scroller, so a mark
    drawn outside a column flush against its padding box was clipped down to the one
    vertical line that fell in the gutter. Inside it, the mark is at the mercy of
    what the element paints over itself: an outline is painted before positioned
    descendants, so a choose group's cells, which are relative and carry a
    background, wipe out whatever of it reaches past the group's own border.

    Neither failure moves anything, so no geometry read finds either — and both
    reach the reader as an uneven box rather than as a missing one, which is how
    this arrived: 2px two pixels in came out a hairline on a group's top and sides
    and stayed 2px along its bottom, where the last cell stops short, and what was
    reported was that the box was thicker at the bottom than the top.

    One page carries both shapes, because a fix for either alone passes half of
    this: the group is the element that paints over its own mark, the column the
    element something else clips.

    The colour is asserted here rather than assumed by the measurement, since the
    scans have to be told what to look for and taking that off the element makes the
    test blind to the one thing it is measuring in.

    The viewport is an odd number of pixels wide so that the horizontal scans are asked
    a real question. The page column is centred, so an even window puts every box on a
    whole x and both side scans then measure from exactly the padding they were handed —
    which is the one value `mark_edges` used to assume for all four sides, so half of
    what it now derives would never have run against a number that differed."""
    context = browser.new_context(
        viewport={"width": 1201, "height": 900},
        color_scheme="light",
        device_scale_factor=2,
    )
    url = serve(REPLAYED_PAGE)
    for ident in ("approach", "col-doing"):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Say more about this.",
                "anchor": {"section": ident},
            },
        )
    page, errors = open_page(browser, url, context=context)
    expect(page.locator("#approach.lf-mark-el")).to_have_count(1)
    expect(page.locator("#col-doing.lf-mark-el")).to_have_count(1)
    ink = token_colour(page, "--mark-ink")
    for ident in ("approach", "col-doing"):
        # The root scrollport changes the page's reading position directly. Centre each
        # specimen before taking the viewport-bounded pixel clip so this paint test does
        # not depend on both fixtures happening to fit at the initial scroll position.
        page.locator(f"#{ident}").evaluate(
            "node => node.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'})"
        )
        painted = page.evaluate(
            "(id) => getComputedStyle(document.getElementById(id)).outlineColor", ident
        )
        assert painted == ink, (
            f"the mark on #{ident} is painted {painted}, not the comment layer's own "
            f"--mark-ink ({ink})"
        )
        edges = mark_edges(page, ident, tuple(int(n) for n in re.findall(r"\d+", ink)))
        widths = {side: sorted(seen) for side, seen in edges.items()}
        assert all(len(seen) == 1 for seen in edges.values()), (
            f"the mark on #{ident} changes width along a side: {widths}"
        )
        stroke = {next(iter(seen)) for seen in edges.values()}
        assert 0 not in stroke, f"the mark on #{ident} is missing from a side: {widths}"
        assert len(stroke) == 1, (
            f"the mark on #{ident} is not the same stroke on every side: {widths}"
        )
    assert errors == []
    page.close()
    context.close()


def test_the_poll_leaves_the_banner_where_it_was(browser, serve):
    """The other half of the same rule, for the changes nobody asked for.

    A press has a line — the row the pressed control stands on, where the next gesture
    is already aimed — and below it the page is content and may move. News arriving on
    the poll has no gesture at all, so there is no line to draw: the user was
    somewhere else entirely, and every control in the chrome is an address they are
    holding. The document may still change under them, because a fact arriving is what
    they are here to see; the address it arrives at may not.

    The banner is where all of it lands, and it is packed to the right against a spacer,
    which decides who pays. A control that grows moves itself and everything to its
    *left*; everything to its right keeps its place. So `Threads (9)` becoming
    `Threads (10)` — a comment posted from the terminal while the user reads —
    slid the version chooser 6px left, and the Accept all a second tab's decision puts
    away took the New-version chip with it.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so the Accept all count has somewhere to go before it
    # runs out; sign-off asked, so the row is the full one; nine comments already, so the
    # tenth crosses a digit; and pinned, so a v2 landing leaves the page where it is and
    # offers the chip rather than following it.
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html, comments=9)
    d = serve.page_dir
    page, errors = open_page(browser, url, pin=True)
    comments = ".lf-banner .lf-threads-toggle"
    accept_all = '.lf-banner [title^="Accept every"]'
    page.wait_for_function(
        f"() => document.querySelector('{comments}').textContent === 'Threads (9)'"
    )
    page_at_rest(page)

    def publish_v2():
        (d / ".fixture-versions" / "v2.html").write_text(html)
        stamp_version_file(d, 2, "two")

    # The same events a second tab's presses would have posted, which is the only way one
    # user's browser hears about another's decisions.
    def decide(*widgets):
        for widget in widgets:
            events_model.append_event(
                d,
                {
                    "kind": "action",
                    "author": "user",
                    "revision": 1,
                    "widget": widget,
                    "action": "accept",
                    "detail": {},
                },
            )

    for what, drive, arrived in [
        (
            "a tenth comment arrives",
            lambda: events_model.append_event(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "A tenth.",
                },
            ),
            f"() => document.querySelector('{comments}').textContent === 'Threads (10)'",
        ),
        (
            "a new version is published",
            publish_v2,
            # Legible wherever the fold has put it: on the row in its own words, or behind
            # the door with the door saying there is something there.
            (
                "() => { const chip = document.querySelector('.lf-latest-chip');"
                "  const door = document.querySelector('.lf-banner-more');"
                "  return chip.checkVisibility({visibilityProperty: true})"
                "    || (chip.classList.contains('lf-news-shown')"
                "        && door.hasAttribute('data-lf-news')); }"
            ),
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            (
                f"() => document.querySelector('{accept_all}')"
                ".textContent === 'Accept all (1)'"
            ),
        ),
        (
            "another tab decides the last one",
            lambda: decide("sug-in-card"),
            # Gone, asked the way it is now gone: a control that has stood on this row keeps
            # its room, so its box is exactly what must not have changed here.
            (
                f"() => !document.querySelector('{accept_all}')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
    ]:
        page.evaluate(DEFINE_BOXES)
        before = page.evaluate(BANNER_WATCH, NEIGHBOUR)
        assert len(before["names"]) >= 4, (
            f"before {what} the banner was showing only {before['names']}, which is "
            "fewer controls than it always has — this step asserts almost nothing"
        )
        drive()
        page.wait_for_function(arrived)
        page_at_rest(page)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"))
        assert not moved, f"{what} and the banner moved:\n  " + "\n  ".join(moved)

    # A reservation keeps its promise even when the row no longer has room. Every address
    # that is still on the row keeps every one of its words, instead of collapsing into a
    # padding-width box containing none of them: the row gives up whole addresses to its
    # menu rather than taking the room out of the ones it keeps.
    holds_its_width = (
        "(names) => Object.fromEntries(names.map((s) => "
        "  [s, document.querySelector('.lf-banner-actions > ' + s)?.offsetWidth ?? null]))"
    )
    named = [
        ".lf-latest-chip",
        ".lf-version",
        ".lf-threads-toggle",
        ".lf-signoff",
        ".lf-answer-all",
        ".lf-decisions",
    ]
    wide = page.evaluate(holds_its_width, named)
    # Narrowed, but not past the covering breakpoint: that row deliberately spends less
    # padding, so its controls are legitimately a few pixels narrower and a comparison
    # across it would read that as the collapse this is about.
    resized(page, 900, 900)
    # Out of room, witnessed independently of the controls whose widths are the subject:
    # the door is standing and there is an address behind it.
    page.wait_for_function(
        "() => !document.querySelector('.lf-banner-more').hidden"
        "      && document.querySelector('.lf-banner-menu').children.length > 0"
    )
    narrow = page.evaluate(holds_its_width, named)
    stayed = {name: width for name, width in narrow.items() if width is not None}
    assert len(stayed) >= 2, (
        f"the row folded away all but {stayed}, so it holds nothing to have kept whole"
    )
    assert stayed == {name: wide[name] for name in stayed}, (
        "a banner with no room left took it out of a control it kept instead of giving "
        f"an address to its menu: {stayed} against {wide}"
    )
    assert errors == []
    page.close()


def test_a_recorded_move_is_acknowledged_in_the_banner_and_nowhere_else(browser, serve):
    """The page has one place for news. A gesture's acknowledgement used to arrive twice
    — a count in the banner and, at the same moment, a toast in the opposite corner —
    two places for the reader to watch. The status line says it now: "Moved to Done —
    recorded" stands in for the line's own words while it lasts, the live region hears
    the same sentence, and the line's words return when the notice fades. No toast node
    exists to be the second place."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")
    status = page.locator(".lf-status-text")
    notice = page.locator(".lf-banner-status .lf-notice")
    expect(status).to_be_visible()
    expect(notice).to_be_hidden()

    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(notice).to_have_text("Moved to Done — recorded")
    expect(notice).to_be_visible()
    expect(status).to_be_hidden()
    expect(page.locator(".lf-live")).to_have_text("Moved to Done — recorded")
    assert page.locator(".lf-toast").count() == 0, "a second surface says the news"
    round_trip(page)

    # The line's own words come back once the notice has had its moment.
    expect(status).to_be_visible(timeout=6_000)
    expect(notice).to_be_hidden()
    assert errors == []
    page.close()


def test_the_banner_opens_a_panel_of_the_machines_leaves(
    browser, serve, other_leaf, tmp_path
):
    """The leaves panel, end to end: the banner counts the machine's live pages,
    this one included, a press slides out a left tray headed by this page's own
    marked, unlinked row, each neighbour is a link named by its title and saying what
    that page is doing — the same judgment its own banner would show, from the same facts — and a
    link opens that page in a tab of its own, leaving this one where it was, panel
    standing. Esc is the panel's rung on the ladder. On a machine serving nothing
    else the button never appears, which every other test here shows for free."""
    other_url, _ = other_leaf
    url = serve(LONG_PAGE)
    # This page has a session behind it too, so its own row can say the same thing a
    # neighbour's does.
    record_claim(
        serve.page_dir,
        id="s-self",
        cwd=str(tmp_path / "self-work"),
    )
    page, errors = open_page(browser, url)
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (2)")
    btn.click()
    others_panel = page.locator(".lf-others-panel")
    expect(others_panel).to_be_visible()
    # This page heads the list, marked and never a link: the panel reads as the
    # whole machine, and this page is where the reader already is.
    self_row = others_panel.locator(".lf-others-self")
    expect(self_row.locator(".lf-pill")).to_have_text("this page")
    expect(self_row.locator(".lf-others-title")).to_have_text("long")
    link = others_panel.locator("a.lf-others-row")
    expect(link.locator(".lf-others-title")).to_have_text("The other leaf")
    # The fixture's page claims working with a fresh ts and nothing contradicts it,
    # so the row says so — dot and words both the banner's own vocabulary.
    expect(link.locator(".lf-others-line")).to_have_text("Working — running the suite")
    expect(link.locator(".lf-dot")).to_have_class(re.compile(r"\bworking\b"))
    # Every row is cut to the panel's width, so the hover holds the whole account —
    # and the fact no row draws is the work behind the page, which is what tells two
    # rows apart when the titles somebody wrote for them are alike. Both rows carry it,
    # from the one gatherer that answers for this page and for its neighbours
    # (`presence`): the tray's account of a neighbour is the account that page gives
    # of itself.
    expect(self_row).to_have_attribute(
        "title", re.compile(rf"^long\n{re.escape(str(tmp_path / 'self-work'))}\n")
    )
    expect(link).to_have_attribute(
        "title",
        f"The other leaf\n{tmp_path / 'other-work'}\nWorking — running the suite",
    )
    destination = link.get_attribute("href")
    tab = opened_tab(page, link.click)
    # The new tab keeps the other page's live root, authorized by the key its link
    # carried, rather than being redirected onto one stamped version.
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    expect(tab).to_have_url(destination)
    # The press left this tab alone, tray still standing.
    expect(others_panel).to_be_visible()
    page.keyboard.press("Escape")
    expect(others_panel).not_to_be_visible()
    expect(btn).to_be_visible()  # closing the panel keeps the standing button
    expect(btn).to_have_text("All leaves (2)")  # and the count
    # The count's reservation, swept here because this is the one test that ever
    # renders the button — every other page here runs under an isolated state home, so
    # neither the press sweep nor the poll test can reach it. The widest label
    # below a thousand must not move the control.
    before, widest = page.evaluate(
        """() => { const b = document.querySelector('.lf-others');
                   const before = b.offsetWidth;
                   b.textContent = 'All leaves (999)';
                   return [before, b.offsetWidth]; }"""
    )
    assert widest == before, (
        f"'All leaves (999)' grew the button {before}px -> {widest}px: its "
        "reserve list no longer names the widest label renderOthers writes"
    )
    assert errors == []
    page.close()


def test_the_banner_uses_the_page_mark_and_puts_each_edge_by_its_panel(
    browser, serve, other_leaf
):
    """The status glyph is the page's own replaceable icon, not a second approximation
    of it. All leaves begins the action row beside the left tray it opens and Threads ends
    it beside the right panel, at every width — `test_the_banner_reads_in_one_order_at_
    every_width` is the order itself; this is the two ends of it standing where their
    panels are. Crossing into a narrow window does not throw away the control in focus:
    an address the fold has taken hands the reader the door it went behind, which is
    where pressing on would find it again."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page, errors = open_page(browser, serve(html))
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    expect(page.locator(".lf-signoff")).to_be_visible()

    mark = page.locator(".lf-banner .lf-dot")
    mask = mark.evaluate("el => getComputedStyle(el).maskImage")
    assert "/icon.svg" in mask, f"the banner mark came from {mask!r}, not icon.svg"
    page.emulate_media(forced_colors="active")
    forced = mark.evaluate(
        """el => ({mark: getComputedStyle(el).backgroundColor,
                    banner: getComputedStyle(el.closest('.lf-banner')).backgroundColor})"""
    )
    assert forced["mark"] != forced["banner"], (
        "the masked page mark disappears into the forced-colors banner"
    )
    page.emulate_media(forced_colors="none")

    def actions():
        return page.locator(".lf-banner-actions > *").evaluate_all(
            """els => els.map(el =>
                 [['others', 'lf-others'], ['latest', 'lf-latest-chip'],
                  ['decisions', 'lf-decisions'], ['version', 'lf-version'],
                  ['comments', 'lf-threads-toggle'], ['signoff', 'lf-signoff']]
                   .find(([, cls]) => el.classList.contains(cls))?.[0])
                 .filter(Boolean)"""
        )

    wide = actions()
    assert wide == ["others", "latest", "decisions", "version", "signoff", "comments"]
    others_x = page.locator(".lf-others").bounding_box()["x"]
    comments = page.locator(".lf-threads-toggle").bounding_box()
    assert others_x < page.viewport_size["width"] / 2, (
        "the control for the left tray is still sitting in the right half of the banner"
    )
    assert comments["x"] + comments["width"] > page.viewport_size["width"] * 0.9, (
        "the control for the right panel is not standing against that edge"
    )

    version = page.locator(".lf-version")
    assert version.bounding_box()["width"] < 100, (
        "the closed version address still reserved the menu's full draft account"
    )
    version.focus()
    resized(page, 390, 900)
    # The row narrows by folding rather than by turning round, and what it folds it hands
    # over rather than drops: the reader is left standing on the address they had, or on
    # the door it went behind, which is the press that finds it again.
    #
    # Which of those two the version is at 390px is a font-width fact rather than this
    # test's subject, and the two cannot both be pinned: the assertion #209 shipped
    # reads the version still on the row, and this suite's fonts fold it away. So
    # the reading follows the address to wherever the fold put it, over a row that has
    # been made to fold something — refold() hands focus to the door only for a control
    # that went behind it, and refocuses the control itself otherwise.
    # `test_a_phone_banner_folds_its_addresses_into_one_menu` is the other half: what goes
    # behind the door, and that there is only ever one door.
    assert page.locator(".lf-banner-menu > *").count() > 0, (
        "the 390px row folded nothing at all, so nothing here crossed into a fold"
    )
    behind = page.locator(".lf-banner-menu > .lf-version").count() == 1
    expect(page.locator(".lf-banner-more" if behind else ".lf-version")).to_be_focused()

    resized(page, 1200, 900)
    # Back on the wide row, with every folded address back on it and back at its start,
    # and the door quiet again because there is nothing behind it.
    expect(page.locator(".lf-banner-actions > .lf-others")).to_have_count(1)
    expect(page.locator(".lf-banner-more")).to_be_hidden()
    expect(page.locator(".lf-banner-menu")).to_be_empty()
    page.locator(".lf-others").focus()
    assert page.evaluate(
        "document.activeElement === document.querySelector('.lf-others')"
    )
    assert actions()[0] == "others" and actions()[-1] == "comments", (
        f"the two edge addresses left their edges: {actions()}"
    )
    assert errors == []
    page.close()


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, dead_pid, tmp_path
):
    """The panel is a status surface, not a snapshot: a neighbour's state changing on
    disk repaints its row at the next poll, in place — and a neighbour whose claimant
    has exited reads as unheld, the computed fact its own banner would state, not the
    claim its status file still makes. The row's hover follows it too, being the same
    account written where there is room for it whole."""
    _, other_dir = other_leaf
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The key is live once the list has arrived, which the button's count states.
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    row = page.locator("a.lf-others-row")
    expect(row.locator(".lf-others-line")).to_have_text("Working — running the suite")
    files_model.write_json(
        other_dir / "status.json",
        {
            "state": "working",
            "detail": "recording the demo",
            "ts": events_model.now_iso(),
        },
    )
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Working — recording the demo")
    # A neighbour waiting on its own reader says so in this seat's shorter words, and
    # in the same term its banner uses: one word per state across the product, or a
    # user reading both surfaces has to work out whether they mean the same thing.
    # Its own watcher has to be live for that, which is what the neighbour's held lease
    # proves — judged from the same evidence its banner judges itself on.
    files_model.write_json(
        other_dir / "status.json",
        {"state": "waiting", "detail": "", "ts": events_model.now_iso()},
    )
    with live_watcher(other_dir, page):
        expect(row.locator(".lf-others-line")).to_have_text("Awaits")
        # And what it is waiting for, because the panel is where a reader picks which
        # page to go to: the row that says a page needs them carries the decision, the way
        # the working row above carries what its agent is doing. The hover holds it
        # whole, with the rest of the account, since the line ellipsizes at the panel's
        # width — and it is the row's hover and not the line's, the innermost title
        # winning where two overlap: a title on the line would answer the hover most
        # likely to be asking for the rest, a reader pointing at the words that ran out
        # of room, with the one part of the account they can already read.
        files_model.write_json(
            other_dir / "status.json",
            {
                "state": "waiting",
                "detail": "pick a storage engine",
                "ts": events_model.now_iso(),
            },
        )
        told(page)
        line = row.locator(".lf-others-line")
        expect(line).to_have_text("Awaits — pick a storage engine")
        expect(row).to_have_attribute(
            "title",
            f"The other leaf\n{tmp_path / 'other-work'}\nAwaits — pick a storage engine",
        )
        assert line.get_attribute("title") is None, (
            "the line carries a tooltip of its own again, which wins under the pointer "
            "over the row's whole account"
        )
        # A leaf holding words of the reader's that nobody has read is a reason to go
        # to it, and no row draws that either: the banner says this number for the page
        # it stands on, and the tray says it for every page on the machine.
        events_model.append_event(
            other_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Mine."},
        )
        told(page)
        expect(row).to_have_attribute(
            "title",
            f"The other leaf\n{tmp_path / 'other-work'}\nAwaits — pick a storage engine"
            "\n1 update waiting",
        )
    # The claim still says waiting; its claimant is gone. The row reports what the
    # directory can prove, exactly as the neighbour's own banner would.
    record_claim(other_dir, id="s", pid=dead_pid)
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Unheld")
    expect(row.locator(".lf-dot")).not_to_have_class(re.compile(r"\bworking\b"))
    assert errors == []
    page.close()


def test_a_closed_leaf_clears_itself_off_the_tray(browser, serve, other_leaf):
    """A closed leaf leaves the tray on the poll that says so. Its server stays
    up — a standing one for good — so the row would otherwise stand forever and the
    count a reader glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a reader
    looking at a closed page is still looking at it — so a tray with nothing live
    left on it still says where the reader is, and the count says (1) for it."""
    _, other_dir = other_leaf
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    expect(rows).to_have_count(1)
    files_model.write_json(
        other_dir / "status.json",
        {"state": "idle", "detail": "", "ts": events_model.now_iso()},
    )
    told(page)
    expect(rows).to_have_count(0)
    expect(btn).to_have_text("All leaves (1)")
    expect(page.locator(".lf-others-self .lf-others-title")).to_have_text("long")
    # The open panel remains a destination after its last link leaves. Its own nav is
    # the fallback landing, and it promises no row walk while there is nothing to walk.
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("All leaves panel")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_be_focused()
    expect(page.locator(".lf-keyline")).not_to_contain_text("walk the leaves")
    assert page.locator(".lf-others-panel").get_attribute("aria-keyshortcuts") is None
    # Two presses in, two Escapes out. The second `g L` entered a tray that was already
    # standing, so its own Escape gives that press back and leaves the workspace it
    # found; the tray the first press stood up closes on the one after. Nothing live left
    # to open: the button stands while the panel does and stands down with it, which is
    # the count's other half.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    told(page)
    expect(btn).not_to_be_visible()
    assert errors == []
    page.close()


def test_the_leaves_tray_takes_the_keyboard(browser, serve, live_leaf):
    """The tray is a list, and a reader walks it without reaching for the mouse: g L
    opens it and lands on the first neighbour, up and down step between them and clamp
    at the ends, Enter opens the focused one in its own tab, and Esc gives that press
    back — the reader is returned to the reading place they pressed `g L` from, not left
    holding the button that names the tray. The go-to menu names the panel, and the key line names
    the tray's own keys once focus is inside it — the promise and the press being one
    scene — and the "?" reference carries the same rows."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(page.locator(".lf-others-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown"
    )
    expect(page.locator("a.lf-others-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter"
    )
    expect(btn).to_have_text("All leaves (3)")
    keyline = page.locator(".lf-keyline")
    # The go-to menu carries the panel only while there is another leaf to show.
    page.keyboard.press("g")
    expect(keyline).to_contain_text("All leaves panel")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    # Titles order the tray, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-others-title")).to_have_text("A second leaf")
    expect(rows.first).to_be_focused()
    expect(keyline).to_contain_text("walk the leaves")
    expect(keyline).to_contain_text("open it in a tab")
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped at the end, never wrapped to the top
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    # Enter is the browser's own on a link, which is why the row is one.
    page.keyboard.press("ArrowDown")
    destination = rows.nth(1).get_attribute("href")
    tab = opened_tab(page, lambda: page.keyboard.press("Enter"))
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    expect(tab).to_have_url(destination)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    # One press in, one Escape out, and what the Escape gives back is exactly what the
    # press took: the reading place `g L` was pressed from. Landing on the tray's own
    # button instead would leave a reader who never touched it holding a control, one
    # press from reopening what they had just put down.
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_contain_text("In the leaves tray")
    expect(help_el).to_contain_text("Previous leaf")
    expect(help_el).to_contain_text("Next leaf")
    assert errors == []
    page.close()


def test_a_page_nobody_has_touched_scrolls_from_the_keyboard(browser, serve):
    """A fresh page gives ordinary keyboard scrolling to the browser's root scrollport.

    Space, PageDown, and arrows work before a reader has clicked anywhere. Leaf still
    places focus on body so there is a stable page location to return to after chrome,
    but scrolling no longer depends on teaching the browser about a non-root box.

    All three keys, because they are one fact about which box the browser is scrolling
    rather than three rows in a table — a fix that reached only the key this test named
    would read as a working page here and a dead one to the reader. The somewhere is
    asserted as well as the scrolling, and `body` is where focus sits by default: what
    that pins is the page itself as the place to stand, rather than a box built to hold
    the reader, which would have a ring to draw and a Tab stop to spend."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    assert page.evaluate("() => document.activeElement === document.body")
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "the page wears a focus ring before the reader has pressed anything"

    for key in ("Space", "PageDown", "ArrowDown"):
        # Programmatic, so the page is still one nobody has put themselves in: a click
        # to get back to the top would be the very thing this test says is not needed.
        page.evaluate("() => { document.scrollingElement.scrollTop = 0; }")
        page.keyboard.press(key)
        try:
            page.wait_for_function(SCROLLED)
        except PlaywrightTimeout:
            # The console with it: the press can move nothing because the runtime
            # threw, and the `errors == []` below never runs once this fires.
            pytest.fail(
                f"{key} moved nothing on a page nobody had clicked in: {errors}"
            )
        # And then the rest of the glide, so the next key's reset lands on a scroll
        # that is over rather than on one still on its way somewhere.
        page.wait_for_function(SCROLL_STILL, arg=SCROLL_SETTLE_MS)
    assert errors == []
    page.close()


def test_esc_hands_the_page_back_after_it_has_closed_the_last_panel(browser, serve):
    """Closing the panel lands focus on the toggle on purpose, since dropping it on
    `<body>` loses a keyboard reader's place with nothing said. The bill for that lands
    on the reader who opened the panel with the pointer and never asked for a keyboard
    place at all: the press that closes is a keypress, so the browser rings a control
    they did not choose, and their next Space is that button rather than the page's
    scroll — the panel they just dismissed comes back and nothing says why.

    Both halves are asserted, because the ring alone reads as cosmetic and the reopening
    alone reads as a stray press. The rung answers both, and it is Escape because the
    reader is already holding it: the same key that unwound the chrome takes them out
    of it.

    The scroll is what the rung has to hand back. Root scrolling is native now, but a
    focused button still owns Space; focus therefore returns to the page rather than
    merely blurring to nowhere."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    toggle = page.locator(".lf-threads-toggle")
    panel = page.locator(".lf-panel")
    ringed = (
        "() => document.querySelector('.lf-threads-toggle').matches(':focus-visible')"
    )
    top = "() => document.scrollingElement.scrollTop"

    # A reader reading: native Space still pages through the document from body.
    page.keyboard.press("Space")
    page.wait_for_function(SCROLLED)
    page.wait_for_function(SCROLL_STILL, arg=SCROLL_SETTLE_MS)
    was = page.evaluate(top)

    # Opened with the pointer, the button holds focus and the browser withholds the ring.
    toggle.click()
    expect(panel).to_be_visible()
    expect(toggle).to_be_focused()
    assert not page.evaluate(ringed)

    # Closed with the key, the ring comes on — the reader's report, and the smaller half.
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    expect(toggle).to_be_focused()
    assert page.evaluate(ringed), "the control the reader is standing on says nothing"

    # The larger half: the same press that scrolled a moment ago is now the button's.
    page.keyboard.press("Space")
    expect(panel).to_be_visible()
    assert page.evaluate(top) == was, "the page scrolled as well as reopening"
    page.keyboard.press("Escape")

    # The rung, and what it is worth: off the chrome, and Space is the page's again.
    expect(page.locator(".lf-keyline")).to_contain_text("back to the page")
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    assert not page.evaluate(ringed)
    # And body wears no ring of its own, which is the thing a focus does that a blur
    # cannot: the reader has to be somewhere, and the somewhere must not be drawn.
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "landing on the page drew a ring around it"
    page.keyboard.press("Space")
    expect(panel).to_be_hidden()
    page.wait_for_function(
        "(was) => document.scrollingElement.scrollTop > was", arg=was
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [500, 1200])
def test_workspaces_replace_each_other_and_name_the_open_one(
    browser, serve, other_leaf, width
):
    """Threads and trays are alternate workspaces at every width.

    The open workspace keeps its semantic expanded state and also wears the banner's
    active face. Its peers return to rest as it takes their place, so the tint names
    exactly the workspace the reader can see rather than merely the last one pressed.
    """
    page, errors = open_page(browser, serve(MANY_DECISIONS_PAGE))
    resized(page, width, 700)
    decisions = page.locator(".lf-decisions-panel")
    comments = page.locator(".lf-panel")
    controls = {
        "leaves": page.locator(".lf-others"),
        "decisions": page.locator(".lf-decisions"),
        "threads": page.locator(".lf-threads-toggle"),
    }

    def face(control):
        return control.evaluate(
            """el => { const style = getComputedStyle(el); return [
              style.borderColor, style.color, style.backgroundColor
            ]; }"""
        )

    active = [
        token_colour(page, "--accent"),
        token_colour(page, "--accent"),
        token_colour(page, "--chip"),
    ]
    resting = {name: face(control) for name, control in controls.items()}
    for control in controls.values():
        expect(control).to_have_class(re.compile(r"\blf-workspace\b"))
    expect(
        page.locator(".lf-version.lf-workspace, .lf-banner-more.lf-workspace")
    ).to_have_count(0)

    def expect_open(name):
        page.mouse.move(0, page.viewport_size["height"] - 1)
        for peer, control in controls.items():
            expect(control).to_have_attribute(
                "aria-expanded", "true" if peer == name else "false"
            )
            assert face(control) == (active if peer == name else resting[peer])

    page.locator(".lf-decisions").click()
    expect(decisions).to_have_class(re.compile(r"\bopen\b"))
    expect_open("decisions")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(decisions).not_to_have_class(re.compile(r"\bopen\b"))
    expect_open("threads")

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect_open("leaves")

    page.locator(".lf-decisions").click()
    panel_settled(page, open=False)
    expect(decisions).to_have_class(re.compile(r"\bopen\b"))
    expect(comments).not_to_have_class(re.compile(r"\bopen\b"))
    expect_open("decisions")
    assert errors == []
    page.close()


def test_a_walk_down_the_tray_stops_clear_of_the_key_line(browser, serve, live_leaf):
    """The tray is the page's other scroll region and the key line stands over its
    bottom-left corner, so the tray reserves the line's room — for the walk, which
    scrolls no further than it must, and for the wheel, which runs to the end. Both
    are asserted because they take their room from different places, and the walk's
    clearance without one is only however far the browser happens to overshoot: a
    fact about row height rather than about the line standing there."""
    names = [f"Leaf {i}" for i in range(6)]
    for i, title in enumerate(names):
        live_leaf(f"n{i}", title)
    page, errors = open_page(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-others")).to_have_text(f"All leaves ({len(names) + 1})")
    # Short enough that the rows overflow the tray, which is the only shape in which
    # the reservation is the difference between a clear last row and a covered one.
    resized(page, 900, 320)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    for _ in names:
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    tray = page.locator(".lf-others-panel .lf-tray-list")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-others-panel .lf-tray-list');"
        "        return b.scrollHeight > b.clientHeight; }"
    ), "the tray never overflowed, so the walk had nothing to scroll and proves nothing"
    last = rows.last.bounding_box()
    line = page.locator(".lf-keyline").bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"the walk parked the last row at {last} under the key line at {line}"
    )
    # And a reader who scrolls the tray to its end by hand lands in the same place:
    # scroll-padding answers the walk, the padding under it answers the wheel.
    tray.evaluate("(b) => b.scrollTo({top: b.scrollHeight})")
    last = rows.last.bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"scrolled to its end the tray put its last row at {last}, under the key "
        f"line at {line}"
    )
    assert errors == []
    page.close()


def test_a_walk_down_the_decisions_tray_stops_clear_of_the_key_line(browser, serve):
    """The leaves tray's reading above, made of the tray beside it. The room is one
    fact — the key line stands in the corner both lists reach — and it was written to one
    list, so the decisions tray's walk parked its last row 47px under the line. Nothing said
    so, because no example ships enough Decisions to fill a tray and the walk that would have
    shown it had only ever been made down the other one.

    So the two lists reserve it together (`trayLists`), and this is the half of that the
    leaves reading could not cover: a fact stated per tray is a fact the second tray
    goes without, and the second tray is the one nobody looks at."""
    page, errors = open_page(browser, serve(MANY_DECISIONS_PAGE))
    resized(page, 900, 420)
    page.locator(".lf-decisions").click()
    rows = page.locator("button.lf-decisions-row")
    expect(rows).to_have_count(24)
    rows.first.focus()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    for _ in range(24):
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    tray = page.locator(".lf-decisions-panel .lf-tray-list")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-decisions-panel .lf-tray-list');"
        "        return b.scrollHeight > b.clientHeight; }"
    ), "the tray never overflowed, so the walk had nothing to scroll and proves nothing"
    last = rows.last.bounding_box()
    line = page.locator(".lf-keyline").bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"the walk parked the last row at {last} under the key line at {line}"
    )
    # And a reader who scrolls the tray to its end by hand lands in the same place:
    # scroll-padding answers the walk, the padding under it answers the wheel.
    tray.evaluate("(b) => b.scrollTo({top: b.scrollHeight})")
    last = rows.last.bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"scrolled to its end the tray put its last row at {last}, under the key "
        f"line at {line}"
    )
    assert errors == []
    page.close()


def test_a_run_with_nothing_to_break_on_stays_inside_the_box_holding_it(browser, serve):
    """Text that cannot wrap does not stop at the edge of its box; it paints straight on
    over whatever the layout put beside it, and nothing about the boxes says so — every
    rect is exactly where it should be. A twelve-character metric value ran 287px out of a
    138px card, and a phone's 372px column is narrower than half the paths this product's
    prose is made of.

    Told it may break a word, the browser will also break one that was never meant to come
    apart: the tree's module spaces its badges by margin and writes no whitespace between
    them, so a line is one word to the breaker, and it split a two-character badge down the
    middle and drew half the pill on each line. Read at a phone's width, where the column
    has the least to give and each of the three is at its worst."""
    page, errors = open_page(browser, serve(UNBREAKABLE_PAGE))
    resized(page, 420, 900)
    inside = """(id) => {
                  const el = document.getElementById(id);
                  const inner = el.querySelector("[data-lf-said='value']") ?? el;
                  const range = document.createRange();
                  range.selectNodeContents(inner);
                  const style = getComputedStyle(el);
                  return range.getBoundingClientRect().right -
                         (el.getBoundingClientRect().right - parseFloat(style.paddingRight));
                }"""
    assert page.evaluate(inside, "m-token") <= 0, (
        "a metric's value paints outside its card"
    )
    assert page.evaluate(inside, "p-token") <= 0, (
        "a path in prose paints outside the column"
    )
    torn = """() => [...document.querySelectorAll('.lf-tree-badge')]
                      .map((b) => b.getClientRects().length)"""
    assert page.evaluate(torn) == [1, 1], "a badge is one pill, and it was drawn as two"
    assert errors == []
    page.close()


def test_a_scroll_box_inside_a_widgets_shadow_tree_takes_the_keyboard(browser, serve):
    """Anything a mouse can scroll, a keyboard can reach — including the box a widget
    renders inside its own shadow tree. `reachScrollers` walks the tree it is handed,
    and `querySelectorAll` stops dead at a shadow boundary, so a diff was the one
    scrolling box on a page that a keyboard user had no way into: no tab stop of its
    own, and unlike a board no control inside to borrow one from. The axe sweep says
    so too, and only while some example's diff happens to carry a line this long; this
    is the same rule asked of the widget rather than of the corpus."""
    page, errors = open_page(browser, serve(WIDE_DIFF_PAGE))
    resized(page, 420, 900)
    measured = page.locator("#wide-diff").evaluate(
        """(d) => {
        const viewport = d.shadowRoot.querySelector('code[data-code]');
        return { scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
                 tab: viewport.tabIndex };
    }"""
    )
    # The reach, then that there was anything to reach: a diff narrow enough to fit
    # takes no tab stop and is right not to, which would pass the first assertion
    # while saying nothing about the rule.
    assert measured["scrolls"] > 0, "this diff fits, so it proves nothing"
    assert measured["tab"] == 0, "a diff that scrolls is unreachable from the keyboard"
    assert errors == []
    page.close()

    page, errors = open_page(browser, serve(DIFF_PAGE))
    resized(page, 1200, 900)
    fitted = page.locator("#patch").evaluate(
        """(d) => [...d.shadowRoot.querySelectorAll('code[data-code]')].map(viewport => ({
          scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
          tab: viewport.tabIndex,
        }))"""
    )
    assert fitted and all(item["scrolls"] == 0 for item in fitted), fitted
    assert all(item["tab"] == -1 for item in fitted), (
        "a diff that fits added a keyboard stop with nowhere to scroll"
    )
    assert errors == []
    page.close()


def test_a_scroll_box_in_a_panel_reply_takes_the_keyboard(browser, serve):
    """The panel holds the same scroll boxes the page does — a reply carries whatever
    widget markup the gate allows — and its column is the narrower of the two, so a box
    that scrolls anywhere scrolls here.

    The sweep that was supposed to cover this stood where each message body is built,
    and needed two things it did not have: that body is not in the document yet, where
    `getComputedStyle` answers "" for every property, and the widget in it has not
    rendered, where the look a scroll box has arrives with the class its module sets on
    the way out. It read an empty overflow off everything it walked and had tagged
    nothing since it was written, which reads as coverage and is the only reason it
    lasted.

    The reply arrives while the panel is already open, because that is the case with
    exactly one reconcile in it. A diff renders asynchronously, so a sweep run where the
    panel inserts its nodes walks a host whose shadow root is still null, and the panel
    does not reconcile on a timer to fix it later: `renderPanel` runs on an open, on a
    fold finishing, and on a new event. Seeding the reply before the page loads gives
    two reconciles and hides all of that."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "user",
            "revision": 1,
            "text": "What does the change look like?",
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.wait_for_selector(".lf-thread")  # the panel is open and reconciled once
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-diff",
            "revision": 1,
            "text": "The one line that decides it:",
            "markup": PANEL_DIFF_MARKUP,
        },
    )
    page.wait_for_function(
        """() => {
        const d = document.querySelector('#rp-diff');
        const viewport = d && d.shadowRoot
          && d.shadowRoot.querySelector('code[data-code]');
        return Boolean(viewport) && viewport.tabIndex === 0;
    }"""
    )
    scrolls = page.locator("#rp-diff").evaluate(
        "(d) => { const viewport = d.shadowRoot.querySelector('code[data-code]');"
        " return Math.round(viewport.scrollWidth - viewport.clientWidth); }"
    )
    assert scrolls > 0, "this diff fits the panel, so it proves nothing"
    assert errors == []
    page.close()


@pytest.mark.parametrize("page_fixture", PAGE_FIXTURES, ids=lambda p: p.stem)
def test_page_fixtures_have_no_serious_wcag_a_or_aa_violations(
    browser, serve, page_fixture
):
    """Axe covers semantic failures the render gate cannot see: an unnamed control,
    an invalid role relationship, or a contrast failure can occupy a perfectly good
    box and still shut a user out. Keep the scope to WCAG A/AA and actionable
    serious/critical findings; layout and accessibility-tree snapshots belong to
    specific regressions, not a corpus baseline that changes with every restyle.

    A phone's width because what a box does there is a different question and not a
    smaller one: the column is 372px, so a block that had room at a desk starts
    scrolling, and a scrolling box with no way into it from the keyboard is a user
    reading half of every line of code. Nothing at 1200 says a word about it."""
    url = serve(page_fixture)
    findings = []
    for color_scheme in ("light", "dark"):
        page, errors = open_page(browser, url, color_scheme=color_scheme)
        for width in (1200, 420):
            resized(page, width, 900)
            violations, report = serious_axe_violations(page)
            if violations:
                findings.append(f"[{width}px {color_scheme}]\n{report}")
        if errors:
            findings.append(f"[{color_scheme}] browser errors: {errors}")
        page.close()

    assert findings == [], "\n\n".join(findings)


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1200, 420])
def test_the_chrome_a_key_opens_has_no_serious_violations(
    browser, serve, other_leaf, color_scheme, width
):
    """The corpus sweep above reads every example, and reads all of them with the chrome
    shut: it never presses a key, so the thread panel, its box, the trays, the versions
    menu, the keyboard reference and the chord's chips are surfaces forty readings pass
    straight over. A `role="list"` whose children are run headings and threads shipped
    through it, green every time.

    One page rather than the corpus, because the chrome is the same on all of them: what
    varies between examples is the document, which the sweep above already reads. What
    varies here is which of the chrome's own surfaces is standing — and the scheme and the
    width, which are the two axes that sweep carries and this one has to carry too. Dropped,
    they cost this test the dark palette entirely: the token these very sweeps caught was
    left failing on the dark half, because nothing here ever rendered it.

    Each surface is opened by its own key, which is also the assertion that it can be, and
    each is proved standing before axe reads it — a sweep over a surface that never opened
    is a green that means nothing, which is the shape `tests/CLAUDE.md` names."""
    page, errors = open_page(browser, serve(ADDRESSED_PAGE, comments=1))
    resized(page, width, 900)
    page.emulate_media(color_scheme=color_scheme)
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")

    def sweep(where):
        violations, report = serious_axe_violations(page)
        assert violations == [], f"{where}: {report}"

    sweep("the page as it arrives")

    # The panel, and then its list — which is where `g T` lands the reader; `c` there
    # enters its page comment box.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    sweep("standing on the comment list")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    sweep("standing in the general box")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()

    # A tray on the far edge, which the sweep above never opens either. Waited out rather
    # than pressed past: the close is animated, so the next surface would otherwise be read
    # with this one still sliding away behind it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile("open"))
    sweep("standing in the leaves tray")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile("open"))

    # The versions menu, including the first-version case browser Escape now dismisses.
    page.keyboard.press("v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    sweep("in the versions menu")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-version-menu")).not_to_be_visible()

    # The keyboard reference, which is a dialog and owes the most of any of them.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    sweep("in the keyboard reference")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()

    # And the chord's chips, which are painted over the page rather than in it. Narrow to
    # hyperlinks so every visible chip belongs to the surface under test.
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(".lf-addresses > .lf-address").first).to_be_visible()
    sweep("with the chord aimed at the hyperlinks")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_page_and_panel_scroll_in_separate_regions(browser, serve):
    """The browser root scrolls the document and the panel keeps its own scrollport.

    Body is the yielding layout shell rather than a third scroll region: beside a wide
    panel its right edge ends where the panel begins, while native document scrolling
    remains rooted in html."""
    page, _ = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    geom = page.evaluate("""() => {
        const box = el => el.getBoundingClientRect();
        const body = document.body, threads = document.querySelector('.lf-threads');
        return { rootIsScroller: document.scrollingElement === document.documentElement,
                 rootScrolls: document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight,
                 bodyOverflow: getComputedStyle(body).overflowY,
                 threadsScroll: threads.scrollHeight > threads.clientHeight,
                 bodyRight: box(body).right, threadsLeft: box(threads).left };
    }""")

    assert geom["rootIsScroller"] and geom["rootScrolls"]
    assert geom["bodyOverflow"] == "visible", geom
    assert geom["threadsScroll"], "the panel did not establish its own scrollport"
    assert geom["bodyRight"] <= geom["threadsLeft"], (
        f"scroll regions overlap: the page ends at {geom['bodyRight']}px, "
        f"the thread list starts at {geom['threadsLeft']}px"
    )
    page.close()


def test_covering_panel_takes_the_page_scroll_with_it(browser, serve):
    """Under 720px the panel covers the page instead of squeezing it, and the
    covered page gives up scrolling with its width: a wheel moves the sheet's
    thread list and never the page behind it. A quote is a promise to show a passage,
    so pressing one dismisses the covering sheet and lands on visible paper. The
    resize path reaches the same states, the posture being a
    media query's and the panel stating only that it is open."""
    page, _ = open_page(
        browser, serve(LONG_PAGE, comments=12, anchored=[("p40", "Paragraph 40.")])
    )
    resized(page, 500, 600)

    # A reading position first, so surviving the sheet is observable.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    before = page.evaluate("() => document.scrollingElement.scrollTop")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # One wheel over the page's visible sliver, one over the sheet. Waiting on the
    # second proves both were processed — input stays in order — so the first
    # having moved nothing is a real outcome rather than a race.
    page.mouse.move(60, 300)
    page.mouse.wheel(0, 400)
    page.mouse.move(400, 300)
    page.mouse.wheel(0, 400)
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "the page scrolled behind the covering sheet"
    )

    # Navigation closes the covering workspace before it positions the page. Doing the
    # same scroll behind the lock produces the right numbers and the wrong product: the
    # promised passage remains invisible.
    #
    # The document says where it came to rest as it comes to rest there, which is the
    # only thing that separates arriving from still travelling: the glide below reaches
    # its destination a frame or more before the browser calls it over, and a wheel sent
    # inside that window cancels the animation instead of scrolling — the reader's notch
    # is spent stopping a glide that had already stopped moving.
    page.evaluate("""() => {
        window.lfRestedAt = null;
        addEventListener("scrollend", event => {
            if (event.target === document)
                window.lfRestedAt = document.scrollingElement.scrollTop;
        });
    }""")
    page.locator(".lf-quote", has_text="Paragraph 40").click()
    panel_settled(page, open=False)
    # Arrived where it was aimed, which is the only thing about this the page states. A
    # text-passage destination reveals nested scrollports without writing the document,
    # then makes one smooth document glide to centre the painted range. Centring is what
    # the runtime aimed for, so the mark reaching the middle is arrival, and a glide that
    # approaches it passes through no earlier position that could be taken for one.
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return Math.abs(m.top + m.height / 2 - innerHeight / 2) < 1; }"""
    )
    # Centred, and the glide that centred it over: scrollend names the document's final
    # resting position rather than a sampled frame near it.
    page.wait_for_function(
        "() => window.lfRestedAt === document.scrollingElement.scrollTop"
    )
    at_mark = page.evaluate("() => document.scrollingElement.scrollTop")
    assert at_mark != before

    # Scrolling belongs to the visible page again immediately after that navigation.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.scrollingElement.scrollTop > {at_mark}")

    # The resize path: narrowing onto an open panel locks, widening unlocks.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    resized(page, 1000, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden' && getComputedStyle(document.body).marginRight !== '0px'"
    )
    resized(page, 500, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY === 'hidden' && getComputedStyle(document.body).marginRight === '0px'"
    )
    page.close()


def test_a_covering_sheet_lifts_the_key_line_over_all_of_its_foot(browser, serve):
    """Over a covering panel the key line stands on the sheet, lifted clear of what the
    sheet keeps standing at its foot. That foot is two rows once the page offers
    reactions: the general composer, and the page's own reaction strip above it. A lift
    measured off the composer alone put the line's More on the strip's ellipsis — 8.8px
    of clear space between two things to press, and the reader aiming at the reaction
    got the keyboard reference.

    The list above the foot scrolls, so it takes the line's room the way the trays' lists
    and the document do: reserved at its end, and given back when the panel steps beside
    the page and the line is capped clear of it instead."""
    page, errors = open_page(browser, serve(ADDRESSED_PAGE, comments=1))
    resized(page, 420, 900)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-page-strip .lf-react-trigger")).to_be_visible()

    def boxes():
        return page.evaluate("""() => {
            const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
                        height: r.height};
            };
            const list = document.querySelector(".lf-threads");
            const style = getComputedStyle(list);
            return {keyline: rect(".lf-keyline"), foot: rect(".lf-panel-foot"),
                    general: rect(".lf-general"), list: rect(".lf-threads"),
                    trigger: rect(".lf-page-strip .lf-react-trigger"),
                    listPad: parseFloat(style.paddingBottom),
                    listScrollPad: parseFloat(style.scrollPaddingBottom)};
        }""")

    covering = boxes()
    # The foot is taller than its composer, or the lift below would be the same
    # measurement either way and the test would prove nothing.
    assert covering["foot"]["height"] > covering["general"]["height"] + 1, (
        f"the panel's foot carried no strip to be lifted over: {covering}"
    )
    assert covering["keyline"]["bottom"] <= covering["foot"]["top"], (
        f"the key line stood on the sheet's foot: {covering}"
    )
    assert covering["keyline"]["bottom"] <= covering["trigger"]["top"], (
        f"the key line stood on the page's reaction strip: {covering}"
    )
    # The line reaches back over the list, so the list reserves at least as much of its
    # own end as the line stands on — spent the wheel's way and the walk's way both.
    covered = covering["list"]["bottom"] - covering["keyline"]["top"]
    assert covered > 0, f"the line no longer reaches the list at all: {covering}"
    assert covering["listPad"] >= covered, (
        f"the sheet's list left its last thread under the key line: {covering}"
    )
    assert covering["listScrollPad"] >= covered, (
        f"a walk to the last thread would stop under the key line: {covering}"
    )

    # Beside the page the line is capped left of the panel, so the list keeps the inset
    # the stylesheet gives it rather than room for a line that never reaches it.
    resized(page, 1200, 900)
    page.wait_for_function(
        """() => parseFloat(
            getComputedStyle(document.querySelector('.lf-threads')).paddingBottom
        ) < 20"""
    )
    beside = boxes()
    assert beside["keyline"]["right"] <= beside["foot"]["left"] + 1, (
        f"the line crossed into the panel it stands beside: {beside}"
    )
    assert errors == []
    page.close()


def test_dynamic_chrome_offsets_keep_the_safe_area_in_their_arithmetic(browser, serve):
    """Runtime layout writes preserve the inset tokens stated by the stylesheet."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    resized(page, 500, 700)
    insets = {"left": 17, "right": 31, "bottom": 23}
    page.evaluate(
        """insets => {
          for (const [side, value] of Object.entries(insets))
            document.body.style.setProperty(`--lf-safe-${side}`, `${value}px`);
        }""",
        insets,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-keyline")).to_be_visible()
    page.wait_for_function(
        """insets => Math.abs(
          document.querySelector('.lf-keyline').getBoundingClientRect().left
          - (18 + insets.left)
        ) < 1""",
        arg=insets,
    )
    boxes = page.evaluate(
        """() => {
          const rect = selector => {
            const r = document.querySelector(selector).getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
          };
              return {keyline: rect('.lf-keyline'), footer: rect('.lf-panel-foot'),
                      width: innerWidth, height: innerHeight};
        }"""
    )
    footer_height = boxes["footer"]["bottom"] - boxes["footer"]["top"]
    assert (
        abs(
            boxes["keyline"]["bottom"]
            - (boxes["height"] - footer_height - 14 - insets["bottom"])
        )
        < 1
    )
    assert abs(boxes["keyline"]["left"] - (18 + insets["left"])) < 1
    assert boxes["keyline"]["right"] <= boxes["width"] - insets["right"] + 1
    assert errors == []
    page.close()


def test_a_covering_composer_keeps_its_controls_inside_the_safe_area(browser, serve):
    """The sheet's worked footer stays above and inside unsafe viewport edges."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    resized(page, 500, 700)
    insets = {"right": 31, "bottom": 23}
    page.evaluate(
        """insets => {
          for (const [side, value] of Object.entries(insets))
            document.body.style.setProperty(`--lf-safe-${side}`, `${value}px`);
        }""",
        insets,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    boxes = page.evaluate(
        """() => {
          const rect = selector => {
            const r = document.querySelector(selector).getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
          };
          return {footer: rect('.lf-general'), send: rect('.lf-general button'),
                  viewport: {width: innerWidth, height: innerHeight}};
        }"""
    )
    assert boxes["footer"]["bottom"] <= boxes["viewport"]["height"] - 23 + 1, (
        f"the covering composer sat under the bottom safe area: {boxes}"
    )
    assert boxes["send"]["right"] <= boxes["viewport"]["width"] - 31 + 1, (
        f"the covering composer's primary action sat under the side safe area: {boxes}"
    )
    assert errors == []
    page.close()


def test_a_stale_package_widget_uses_recursive_parent_eligibility(
    browser, serve, one_reader, tmp_path, monkeypatch
):
    """A project widget gets honest controls and authoritative stale rejection.

    A fresh tab projects a nested stopped plan and disables Increase. A deliberately
    stale tab still offers it, so its real press reaches POST; the same registry
    prerequisite must reject it there. A separate absolute `decrease` action remains
    available while the parent is blocked.
    """
    monkeypatch.chdir(tmp_path)
    overlay = tmp_path / ".leaf"
    (overlay / "widgets").mkdir(parents=True)
    task = json.loads((COMMAND_HUB_PACKAGE / "registry.json").read_text())["lf-task"]
    task["x-awaits"]["rollup"] = True
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "lf-task": task,
                "lf-quota": {
                    "description": "A project-defined absolute scalar control.",
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "slots": {"type": "string", "pattern": "^[0-9]+$"},
                        "restated": {"type": "boolean"},
                    },
                    "required": ["id", "slots"],
                    "additionalProperties": False,
                    "x-parent": ["lf-task"],
                    "x-content": "none",
                    "x-upgrade": True,
                    "x-state": {
                        "move": {
                            "detail": {
                                "type": "object",
                                "properties": {
                                    "to": {"type": "string"},
                                    "index": {"type": "integer", "minimum": 0},
                                },
                                "required": ["to", "index"],
                                "additionalProperties": False,
                            },
                            "facet": "placement",
                            "unit": "widget",
                            "record": {
                                "kind": "position",
                                "within": "lf-task",
                                "value": "to",
                                "order": "index",
                            },
                        },
                        "increase": {
                            "detail": {
                                "type": "object",
                                "properties": {
                                    "slots": {
                                        "type": "string",
                                        "pattern": "^[0-9]+$",
                                    }
                                },
                                "required": ["slots"],
                                "additionalProperties": False,
                            },
                            "facet": "capacity",
                            "unit": "widget",
                            "record": {
                                "kind": "value",
                                "attr": "slots",
                                "value": "slots",
                            },
                            "requires": {
                                "target": "parent",
                                "awaiting": False,
                            },
                        },
                        "decrease": {
                            "detail": {
                                "type": "object",
                                "properties": {
                                    "slots": {
                                        "type": "string",
                                        "pattern": "^[0-9]+$",
                                    }
                                },
                                "required": ["slots"],
                                "additionalProperties": False,
                            },
                            "facet": "capacity",
                            "unit": "widget",
                            "record": {
                                "kind": "value",
                                "attr": "slots",
                                "value": "slots",
                            },
                        },
                    },
                    "x-example": (
                        '<lf-tasks id="quota-example-tasks">'
                        '<lf-task id="quota-example-task" status="active">'
                        "<strong>Task</strong>"
                        '<lf-quota id="quota-example" slots="1"></lf-quota>'
                        '<lf-task id="quota-example-child" status="active">'
                        "<strong>Child</strong></lf-task>"
                        "</lf-task></lf-tasks>"
                    ),
                },
            }
        )
    )
    (overlay / "widgets" / "lf-quota.js").write_text(
        """\
import { actionAvailable, offer, once, sendAction } from "/runtime/widget-api.js";

const detail = (quota, delta) => ({
  slots: String(Number(quota.getAttribute("slots")) + delta),
});

const paint = quota => {
  for (const [name, delta] of [["decrease", -1], ["increase", 1]])
    quota.querySelector(`[data-lf-quota="${name}"]`)?.setAttribute(
      "aria-disabled",
      String(!actionAvailable(quota, name)),
    );
};

async function change(quota, delta) {
  const action = delta > 0 ? "increase" : "decrease";
  const next = detail(quota, delta);
  if (!actionAvailable(quota, action)) return;
  const previous = quota.getAttribute("slots");
  quota.setAttribute("slots", next.slots);
  paint(quota);
  if (!await sendAction(quota, action, next)) quota.setAttribute("slots", previous);
  paint(quota);
}

customElements.define("lf-quota", class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const decrease = offer("button", "lf-btn", "Decrease");
    decrease.dataset.lfQuota = "decrease";
    decrease.addEventListener("click", () => void change(this, -1));
    const increase = offer("button", "lf-btn", "Increase");
    increase.dataset.lfQuota = "increase";
    increase.addEventListener("click", () => void change(this, 1));
    this.append(decrease, increase);
    document.addEventListener("lf-actions", () => paint(this));
    paint(this);
    document.getElementById("destination")?.append(this);
  }
  applyAction(action, detail) {
    if (action === "move") document.getElementById(detail.to)?.append(this);
    else if (["increase", "decrease"].includes(action))
      this.setAttribute("slots", detail.slots);
    paint(this);
  }
});
"""
    )
    quota_v1 = leaf_page(
        "quota",
        '<h1 id="heading">Quota</h1><lf-tasks id="tasks">'
        '<lf-task id="task" status="active"><strong>Task</strong>'
        '<lf-quota id="quota" slots="1"></lf-quota>'
        '<lf-decision id="quota-intervention-decision"><h2>Proceed?</h2>'
        '<lf-options id="quota-intervention" choose>'
        '<lf-option id="quota-ready" chosen>Ready</lf-option></lf-options></lf-decision>'
        '<lf-task id="child" status="active"><strong>Child</strong>'
        '<lf-decision id="quota-child-decision"><h2>Is the child ready?</h2>'
        '<lf-options id="quota-child-review" choose>'
        '<lf-option id="quota-child-ready" chosen>Ready</lf-option>'
        "</lf-options></lf-decision></lf-task>"
        "</lf-task>"
        '<lf-task id="destination" status="active">'
        "<strong>Destination</strong></lf-task>"
        "</lf-tasks>",
    )
    url = serve(quota_v1)
    stale_held = held_stale(one_reader)
    stale, stale_errors = open_page(browser, url, context=stale_held)
    current, current_errors = open_page(browser, live_url(url), context=one_reader)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "task",
            "action": "status",
            "detail": {"status": "blocked"},
        },
    )
    told(current)
    expect(current.locator("#task")).to_have_attribute("status", "blocked")
    # Status describes work only, so reports cannot create a reader prerequisite.
    expect(current.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "false"
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "child",
            "action": "status",
            "detail": {"status": "blocked"},
        },
    )
    told(current)
    expect(current.locator("#child")).to_have_attribute("status", "blocked")
    expect(current.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "false"
    )
    # The direct intervention remains answered. Reopening the child request alone
    # makes the parent aggregate await and closes capacity in the current tab.
    current.locator("#quota-child-ready").click()
    round_trip(current)
    expect(current.locator("#quota-child-ready")).not_to_have_attribute("chosen", "")
    expect(current.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(current.get_by_role("button", name="Decrease")).to_have_attribute(
        "aria-disabled", "false"
    )

    # A live activation imports fresh element identities. The module reparents quota
    # while upgrading, but eligibility still reads v2's pristine authored parent.
    quota_v2 = (
        quota_v1.replace(
            '<lf-task id="task" status="active">',
            '<lf-task id="task" status="blocked">',
        )
        .replace(
            '<lf-task id="child" status="active">',
            '<lf-task id="child" status="blocked">',
        )
        .replace('id="quota-ready" chosen', 'id="quota-ready"')
    )
    (serve.page_dir / ".fixture-versions" / "v2.html").write_text(quota_v2)
    stamp_version_file(serve.page_dir, 2, "same plan")
    told(current)
    expect(current.locator(".lf-version")).to_contain_text("v2")
    expect(current.locator("#task")).not_to_have_attribute("data-lf-reported", "1")
    expect(current.locator("#child")).not_to_have_attribute("data-lf-reported", "1")
    expect(current.locator("#destination > #quota")).to_have_count(1)
    expect(current.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "true"
    )

    expect(stale.locator("#task")).to_have_attribute("status", "active")
    expect(stale.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "false"
    )
    stale.get_by_role("button", name="Increase").click()
    round_trip(stale)

    assert [event["action"] for event in actions(serve.page_dir)] == ["choose"]
    stale_held.restore()
    told(stale)
    expect(stale.locator("#quota")).to_have_attribute("slots", "1")
    expect(stale.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "true"
    )

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "quota",
            "action": "move",
            "detail": {"to": "destination", "index": 0},
        },
    )
    told(current)
    expect(current.locator("#destination > #quota")).to_have_count(1)
    expect(current.get_by_role("button", name="Increase")).to_have_attribute(
        "aria-disabled", "false"
    )

    current.get_by_role("button", name="Decrease").click()
    round_trip(current)
    expect(current.locator("#quota")).to_have_attribute("slots", "0")
    assert [event["action"] for event in actions(serve.page_dir)] == [
        "choose",
        "move",
        "decrease",
    ]
    assert current_errors == []
    assert stale_errors and all("400" in error for error in stale_errors)
    stale.close()
    current.close()


def test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge(
    browser, serve
):
    """Overflow is one of three, and the other two leave `overflow` computing `visible`.

    The gate below reports a cut ring by asking each box on the way up what band it
    shows. A reading that knows only `overflow` answers "nothing is wrong" for a box that
    clips by paint containment or by `content-visibility`, and answers it in the same
    words it uses when nothing is wrong — which is why the corpus staying green could not
    have told anyone. `shownBand` is the product's own reading and names all three; this
    holds the probe to it rather than to a copy free to drift from it again.

    One control, one ring pushed out past its box, three parents differing only in how
    they clip. The first case is the control: without it a reading that reported at every
    stop would pass the other three and prove nothing.
    """
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page, errors = open_page(browser, url)
    page.locator(".lf-sug-accept").first.focus()
    # The probe's control must begin clear of the viewport edge. Its subject is each
    # ancestor's clipping behavior, not where the corpus happened to place this button.
    page.evaluate("document.activeElement.scrollIntoView({block: 'center'})")

    plant = """(how) => {
      const el = document.activeElement;
      const p = el.parentElement;
      p.style.overflow = p.style.contain = p.style.contentVisibility = '';
      // The ring past the parent's edge with the control still inside it. Moving the
      // control out instead takes its own edge out of the box too, and a box is held to
      // a ring only on the sides where it is showing the control's own edge — so all
      // three cases below would be declined for the reason the control case is.
      el.style.outlineOffset = '8px';
      if (how === 'overflow') p.style.overflow = 'hidden';
      if (how === 'contain') p.style.contain = 'paint';
      if (how === 'content-visibility') p.style.contentVisibility = 'auto';
      const s = getComputedStyle(p);
      return `${s.overflowX}/${s.contain}/${s.contentVisibility}`;
    }"""

    clean = page.evaluate(plant, "none")
    assert standing_ring(page)["cuts"] == [], (
        f"the displaced ring is reported cut with nothing clipping it ({clean}), so the "
        "cases below would only be repeating whatever this reading always says"
    )
    for how in ("overflow", "contain", "content-visibility"):
        style = page.evaluate(plant, how)
        cuts = standing_ring(page)["cuts"]
        assert any("left edge" in c for c in cuts), (
            f"a parent clipping by {how} ({style}) drew the ring away and the reading "
            f"said {cuts}"
        )

    assert errors == []
    page.close()


def test_the_ring_reading_tells_a_ring_from_the_layers_other_outlines(browser, serve):
    """The reading sweeps for boxes painting the ring, so it has to know one on sight.

    Style and width do not say. The layer draws three other outlines at exactly the
    ring's weight: `[data-lf-restated]` and `[data-lf-pending]` are 2px solid over a
    `color-mix`, and a mark under the pointer takes the ring's own width while keeping
    the mark's hue. A sweep asking style and width alone claims all three and then
    reports the page painting a ring no rule named — a complaint with no answer, since
    naming them puts them in a population the keyboard can never light.

    Nothing in the corpus paints one of the three during the walk today, so the walk
    going green says nothing about this. What it turns on is which example is written
    next and where the walk last left the pointer, and neither is a decision anybody
    would make knowing it decided this.

    The colour is what separates them, and it has to be resolved on both sides: a custom
    property serializes as it was written, `outline-color` as it resolved, and a package
    writing `color-mix()` for its accent once left every rule in the layer uncredited.

    The real ring goes last, as the control: without it a reading that claimed nothing at
    all would pass the three cases above and prove only that it was silent."""
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page, errors = open_page(browser, url)
    page.locator(".lf-sug-accept").first.focus()

    plant = """(how) => {
      const box = document.querySelector('main p');
      box.classList.add('probe-target');
      box.removeAttribute('data-lf-restated');
      box.removeAttribute('data-lf-pending');
      box.classList.remove('lf-mark-el', 'lf-mark-hover');
      box.style.outline = '';
      if (how === 'restated') box.setAttribute('data-lf-restated', '');
      if (how === 'pending') box.setAttribute('data-lf-pending', '');
      if (how === 'mark') box.classList.add('lf-mark-el', 'lf-mark-hover');
      if (how === 'the ring itself') box.style.outline = 'var(--here-ring)';
      const cs = getComputedStyle(box);
      return [cs.outlineStyle, cs.outlineWidth, cs.outlineColor];
    }"""

    def claimed():
        """Whether the reading calls this one box a ring.

        Asked of the box rather than of how many rings the page has: the runtime
        repaints the panel on its own schedule, so two whole-page counts taken a moment
        apart differ for reasons that have nothing to do with what was planted here.
        """
        return [
            seen["who"]
            for seen in rings_drawn(page)
            if seen["here"] and "probe-target" in seen["who"]
        ]

    page.evaluate(plant, "none")
    assert not claimed(), "the box is called a ring before anything is painted on it"
    standing = standing_ring(page)
    assert standing and standing["here"], (
        "no ring is painted with the keyboard on a control, so the reading is silent "
        "here and would pass this test however it behaved"
    )

    for how in ("restated", "pending", "mark"):
        style, width, colour = page.evaluate(plant, how)
        # Non-vacuity: the lookalike has to actually be painted, at the ring's own
        # weight, or the reading was never given the chance to mistake it for one.
        assert (style, width) == ("solid", "2px"), (
            f"{how} drew {style} {width}, not the 2px solid this is written against, so "
            "the reading was never offered anything to confuse with a ring"
        )
        assert not claimed(), (
            f"the reading counted {how} ({colour}) as a here ring: {claimed()}"
        )

    style, width, colour = page.evaluate(plant, "the ring itself")
    assert claimed(), (
        f"a box wearing the layer's own ring ({colour}) was not counted, so the three "
        "cases above prove only that this reading is silent"
    )

    assert errors == []
    page.close()


def test_the_ring_reading_still_sees_what_is_painted_over_a_ring(browser, serve):
    """The half that answers by hit test, held to firing where it can and not where it

    cannot. It takes whatever the ring's own pixels hit as standing over them, and an
    outline is painted by its control at its control's level while an outline's pixels
    are not hit-testable — so a sample outside the control's box returns whatever is
    beneath. That is sound while the control's surface takes hits and unsound inside one
    that does not, where the answer comes back inverted: the key line stands over the
    page at z-index 8940 with `pointer-events: none`, and the code under its More button
    read as standing over it.

    So the reading declines inside such a surface, and that is a way for it to go quiet
    everywhere by accident. The plant is the population assertion: thin enough to lie
    over the ring and not over the control, because a cover across the control's own body
    is excused on purpose — a control put where something stands over it is a fact about
    where it was put, not about its ring leaving its box.
    """
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator("body").click()
    # A real press, because `.focus()` alone never raises `:focus-visible` and a control
    # with no ring is a control with nothing to report about one.
    page.locator(".lf-threads .lf-btn").first.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    assert standing_ring(page), "no ring is drawn, so nothing is covered"

    assert standing_ring(page)["covers"] == [], (
        "the control is reported covered before anything is put over it"
    )
    page.evaluate(
        """() => {
          const b = document.activeElement.getBoundingClientRect();
          const d = document.createElement('div');
          // Over the ring's top run and clear of the control's own box.
          d.style.cssText = `position: fixed; z-index: 99999; background: red;
            left: ${b.left - 8}px; top: ${b.top - 5}px;
            width: ${b.width + 16}px; height: 4px;`;
          document.body.append(d);
        }"""
    )
    assert any("top edge is under" in c for c in standing_ring(page)["covers"]), (
        "a band laid over the ring's top run was not reported, so this reading answers "
        "nothing and the pages it passes are not evidence"
    )

    assert errors == []
    page.close()


def test_a_reader_who_asked_for_no_motion_gets_a_ring_that_does_not_arrive(
    browser, serve
):
    """A duration is a way of keeping an animation and no way at all of keeping a
    transition. An animation is declared and named, and the layer reads `animationend`
    to know one has run, so the guard's near-zero duration keeps that event and spends
    no time on it. A transition is declared by nobody — `transition-property` is `all`
    until something says otherwise — so the same duration over every element made a
    transition out of every property that changed on any of them.

    None of which anybody wrote or listened for, and none of which was free: a ring is
    `outline-width`, `outline-offset` and `outline-color` all changing at once, so a
    reader who asked for no motion got a medium currentColor ring at offset nought
    animating into the real one, on every focus, on every page. It is also what a
    computed-style reading of a ring taken in those frames was told, which is how
    `RINGS_DRAWN` came to invent one.

    So this asks the reader's own question — is anything moving — of the control they
    just landed on, in the one setting where the answer has to be no."""
    url = serve(LONG_PAGE, comments=3)
    context = browser.new_context(reduced_motion="reduce")
    try:
        page, errors = open_page(browser, url, context=context)
        assert page.evaluate(
            "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
        ), "the context did not ask for reduced motion, so the guard under test is off"
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        page.locator(".lf-threads > .lf-thread").first.focus()

        seen = page.evaluate(
            """() => {
          const el = document.activeElement;
          const cs = getComputedStyle(el);
          return {
            moving: el.getAnimations().map(
              (a) => a.transitionProperty || a.animationName || 'animation'),
            ring: [cs.outlineWidth, cs.outlineStyle, cs.outlineOffset],
            want: cs.getPropertyValue('--here-ring').trim(),
          };
        }"""
        )
        assert seen["moving"] == [], (
            f"the ring is still arriving under reduced motion: {seen['moving']} are "
            "running, so what the reader sees and what any reading of this control gets "
            "is a value on its way rather than the one the rule states"
        )
        # Non-vacuity: a control with no ring has nothing that could have transitioned.
        assert seen["ring"][:2] == [seen["want"].split()[0], "solid"], (
            f"the thread reads {seen['ring']} where its ring is {seen['want']}, so "
            "nothing here was ever going to move"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_the_ring_reading_sees_a_neighbour_paint_over_a_ring_drawn_inside_its_box(
    browser, serve
):
    """The same half asked of the other shape of ring, and the shape it was quiet about.
    A cover is excused where the control is under the same thing — a control put under a
    fixed bar is where it was put, not a ring leaving its box — and how far in the
    reading looks to ask that is the ring's own band.

    Which is inside the box when the ring is. The test above plants over a ring drawn
    outside its control, where the band is outside too and any step in clears it; asked
    one pixel in, as it was, the same question over an inset ring lands on the ring
    rather than past it, so every covered inset ring answered that the control was under
    the same thing and the reading returned what it returns when nothing is wrong. The
    panel's own threads are inset rings to the last one, so this was the half of the
    reading that watches them.

    So: a thread, which draws its ring inside itself, under a band exactly as deep as
    that ring. The control case first, because a reading that reports over any thread
    would pass the planted one without seeing it.
    """
    url = serve(LONG_PAGE, comments=6)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-threads > .lf-thread").first.focus()
    page.evaluate(RENDERED)

    inset = page.evaluate(
        """() => {
      const s = getComputedStyle(document.activeElement.closest('.lf-thread'));
      return [parseFloat(s.outlineWidth), parseFloat(s.outlineOffset)];
    }"""
    )
    assert inset[1] <= -inset[0], (
        f"the thread's ring is {inset[0]}px at offset {inset[1]}px, which is not drawn "
        "inside its box, so this holds nothing about a reading of one that is"
    )

    # A band of the panel's own paper over the card's top run, and nothing else of it.
    # Fixed and outside the card, because the reading passes over an ancestor or a
    # descendant of the control by design — a widget painting its own edge is not a
    # neighbour.
    plant = """(depth) => {
      document.querySelector('.lf-ring-plant')?.remove();
      if (!depth) return null;
      const card = document.activeElement.closest('.lf-thread');
      const r = card.getBoundingClientRect();
      const over = document.documentElement.appendChild(
        document.createElement('div'));
      over.className = 'lf-ring-plant';
      Object.assign(over.style, {
        position: 'fixed', zIndex: '9999',
        background: getComputedStyle(card).backgroundColor === 'rgba(0, 0, 0, 0)'
          ? '#fff' : getComputedStyle(document.body).backgroundColor || '#fff',
        left: `${r.left}px`, top: `${r.top}px`,
        width: `${r.width}px`, height: `${depth}px`,
      });
      return over.getBoundingClientRect().height;
    }"""

    page.evaluate(plant, 0)
    assert standing_ring(page)["covers"] == [], (
        "the thread is reported covered with nothing over it, so the planted case below "
        "would only be repeating whatever this reading always says"
    )

    laid = page.evaluate(plant, inset[0])
    covers = standing_ring(page)["covers"]
    assert any("top edge" in c for c in covers), (
        f"a {laid}px band over the whole of the card's {inset[0]}px inset ring, with the "
        f"rest of the card in full view, and the reading said {covers}"
    )

    assert errors == []
    page.close()


# Where a here ring can be drawn, and the keys the register already declares for
# reaching each. Scopes rather than rooms because this layer spends "room" on space —
# `--here-ring-room` is the band a scroller reserves — and these are places the reader
# stands. A tray, the versions menu and the reference hold controls that do not exist
# until their entry control opens them, so the Tab order alone never reaches one: twelve of the
# layer's ring rules stood in that position when this was written.
RING_WALKS = (
    (
        "the page",
        (),
        (
            "corpus",
            "design-decision",
            "postmortem",
            "pr-walkthrough",
            "release-notes",
            "triage-board",
            "ship-review",
        ),
    ),
    ("passage search", ("/",), ("corpus",)),
    ("the comments", ("c",), ("ship-review",)),
    ("the decisions tray", (), ("ship-review",)),
    ("the leaves tray", ("g", "Shift+l"), ("corpus",)),
    # The menu's own walk after the key that opens it: an open lands on the version being
    # read, which is the last row, and the comparison press beside a row is a Tab forward
    # from the row above it. The walk is clamped, so a second press at the top moves
    # nothing and the pair covers a menu of any length this corpus can hold.
    ("the versions menu", ("v", "ArrowUp", "ArrowUp"), ("corpus",)),
    ("the reference", ("?", "?"), ("corpus",)),
    ("design mode", ("i",), ("corpus",)),
    # A Thread card and the compact Page-map sheet are the two layers a Tab walk of the
    # page cannot open for itself. The card is a press on a Thread Button; the sheet is a
    # press on a Map control the wide posture does not draw at all, so its walk asks for
    # the narrow window the control lives in.
    ("a thread card", (), ("ship-review",)),
    ("the page map sheet", (), ("corpus",)),
)
# The corpus is the open-ended page and design-mode anchor. The authored pages now
# give each interaction family a focused page, so the page walk names those owners:
# Design contributes settled and joined options, Postmortem a visual target, PR source
# and code, Release drafts and a shot, Triage a card grip, and Ship the log-hosted
# widgets and element mark. Chrome with no page-owned contents is walked on the corpus.
RING_WALK_EXAMPLES = tuple(
    dict.fromkeys(name for _scope, _keys, corpus in RING_WALKS for name in corpus)
)


# Whether the page is offering a banner address at all, which is not the same question as
# whether the reader can see it standing on the row. A control with nothing to show is
# drawn away by the banner's own presence writer (paintPresence, display: none), while one
# the row had no width for is alive behind the fold's menu — and asking a folded address
# whether it is visible answers no for a page that is offering it perfectly well, which
# read as a scope no example reached rather than as a window too narrow to show it.
def offered(page, selector):
    return page.locator(selector).evaluate_all(
        "els => els.some(el => getComputedStyle(el).display !== 'none')"
    )


# What each scope has to have opened before its walk means anything, and what the page
# shows while its entry is available. A control with nothing to show is absent by
# declaration — Asks on a page waiting on nobody, `L` where the machine has one leaf — so
# the surface is asked for only where the page is offering it, and the corpus answers for
# the rest. Without this a key that stops working leaves the walk re-walking the page and
# contributing nothing, which the coverage floor catches only where that scope is a
# rule's sole home: one guard over seven setup steps. The page and the comments raise no
# surface of their own; `g T` lands on the Threads list, which the walk's own first stop
# reads, while page `c` enters its comment box and is exercised separately.
RING_SCOPE_SURFACE = {
    "a thread card": (".lf-margin-preview:popover-open", None),
    "the page map sheet": (".lf-page-map-sheet[open]", None),
    "passage search": (".lf-target-search:not([hidden])", None),
    "the decisions tray": (".lf-decisions-panel.open", ".lf-decisions"),
    "the leaves tray": (".lf-others-panel.open", ".lf-others"),
    "the versions menu": (".lf-version-menu:popover-open", None),
    "the reference": (".lf-help.open", None),
    "design mode": ("body.lf-design", None),
}
RING_SCOPE_CONTROL = {
    "the decisions tray": (".lf-decisions", ".lf-decisions-row"),
    "a thread card": (
        '.lf-margin-marker[data-lf-kinds~="comment"]',
        ".lf-margin-preview",
    ),
    "the page map sheet": (".lf-page-map-toggle", ".lf-page-map-action"),
}
# The window a scope's own surface stands in, where that is not the walk's own. Both
# entries are a floor the layer states rather than a preference: the Map control is drawn
# under the margin's breakpoint and nowhere else, and a Thread Button builds its card only
# where the document leaves room beside the source and opens Threads otherwise. That room
# is the wider of the two floors here, because the card's walk is ship review and ship
# review stands a contents map: a page with a sidebar waits for 1472px of shell rather
# than 1208px (theme.css). Every other scope is read at the width the page opened at.
RING_WALK_VIEWPORT = (1200, 900)
# The one scope whose surface the standing panel takes the place of.
RING_SCOPES_WITHOUT_PANEL = {"a thread card"}
RING_SCOPE_WIDTH = {"a thread card": 1600, "the page map sheet": 760}
# Focus put back at the document's start. `document.body.focus()` and not a blur: a blur
# leaves the sequential focus navigation starting point where the blurred control stood,
# so the next Tab carries on from the chrome, runs off the end of the order and never
# enters the page. Twelve stops instead of thirty-three, with every ring the page's own
# widgets draw unread and the walk reporting itself complete.
RING_WALK_START = "() => document.body.focus()"
# What the walk is standing on, read on a rendered frame: a stop it has not stood on, one
# it has, or nothing at all. Held by identity, since two buttons in a row can say the same
# words at the same scroll and are still two stops. The three answers are one reading
# rather than two, because only the middle one ends a walk and a boolean spelt the other
# two the same way.
RING_NEW_STOP = f"""async () => {{
  await ({RENDERED})();
  const e = ({DEEP_FOCUS})();
  if (!e || e === document.body || e === document.documentElement) return "empty";
  if (window.__lfSeen.has(e)) return "seen";
  window.__lfSeen.add(e);
  return "new";
}}"""


# A stop the reader cannot find, or null when they can. The walk stands on every control
# a page has; this asks, at each one, whether anything on screen says so.
#
# Four answers count, because the layer leaves "here" drawn in four ways and every one of
# them is the reader seeing the same thing.
#
# The platform's own ring (`outline-style: auto`) is the first and the commonest. Leaf
# restyles the controls it draws and leaves that ring on the rest — an authored link, a
# `summary`, a widget's own native control — and replacing it everywhere would be a
# change to how the product looks rather than a thing this test is owed.
#
# The layer's here ring is the second, on the stop or on an ancestor: a `choose` group
# takes the ring for the pick mark inside it, whose own rule states `outline: none`
# exactly so the two do not both draw, and the reader sees the group.
#
# What this cannot see, said out loud so a green is not read as more than it is. A
# joined `lf-options` carrying log news — restated, pending, reported — deliberately
# stands its ring down, because an element takes one outline and the log has claimed it;
# the layer's own comment (packages/default/theme.css) names the carriers that stand in
# its place as the washed cell and the address chips, and neither is an outline nor an
# accent shadow. That is a fifth way of drawing "here" and this reading has no honest
# test for it: accepting a background would pass every stop on a tinted page. No corpus
# example reaches the state — none carries `restated`, the one shipped log carries no
# report, and the walk makes no gesture — so nothing here is being excused today. A
# reading of the wash has to come with the corpus case that shows it.
#
# `.lf-mark-here` is a smaller one of the same kind: it paints the accent ring on a box a
# standing thread is anchored to, with no focus of its own, so a stop inside such a box
# is credited to it. Today the corpus anchors one element comment, to a diagram, which
# has nothing focusable inside it.
#
# The mark's own ink is the third. A box carrying an element comment already wears a
# hairline in --mark-ink, and the layer ranks its states in that one property: 1px
# posted, 2px indicated, 2px accent stood in. Focus indicates, so a marked box answers
# the keyboard at the indicated weight in its own ink. Width is what keeps this from
# passing everything: a mark that is merely posted is a hairline, and a hairline is not
# an answer to where the keyboard is.
#
# An accent shadow is the fourth. Every box the reader types into is drawn that way: the
# chrome's textarea rule takes the outline off and puts the shadow in its place, and a
# box drawn like that is as found as one drawn with a ring. Read on the stop itself and
# never on an ancestor, and only in the accent, since a card's decorative drop shadow is
# no answer to where the keyboard is and accepting any shadow from any ancestor would
# pass every stop on a page that has one shadowed box anywhere above it.
#
# Both colours are resolved through a swatch rather than compared as written, and the
# accent is resolved twice: `outline-color` serializes as the browser resolved it, and a
# `color-mix` resolves into a different space than a plain token does, so the ring's
# `rgb(...)` and the shadow's `color(srgb ...)` are the same colour written two ways and
# each needs the browser to say so.
SEEN_STOP = f"""() => {{
  const e = ({DEEP_FOCUS})();
  if (!e) return null;
  const swatch = document.createElement('span');
  swatch.style.cssText = 'outline: 1px solid var(--accent)';
  document.head.append(swatch);
  const accent = getComputedStyle(swatch).outlineColor;
  swatch.style.outlineColor = 'var(--mark-ink)';
  const markInk = getComputedStyle(swatch).outlineColor;
  swatch.style.outlineColor = 'color-mix(in srgb, var(--accent) 100%, transparent)';
  const mixed = getComputedStyle(swatch).outlineColor
    .match(/color\\(srgb ([\\d.]+ [\\d.]+ [\\d.]+)/)?.[1];
  swatch.remove();
  const shown = (el) => {{
    const cs = getComputedStyle(el);
    if (cs.outlineStyle === 'auto') return true;
    return cs.outlineStyle === 'solid'
      && cs.outlineWidth === cs.getPropertyValue('--here-ring-w').trim()
      && (cs.outlineColor === accent || cs.outlineColor === markInk);
  }};
  // An ancestor answers only for a ring whose rule named it. Every ancestor on this
  // chain contains the focus by construction, so containing it says nothing; what
  // separates a ring drawn because the reader is here from one drawn for another
  // reason is that the layer's focus rules say which ring they are and the pointer's
  // do not. `.lf-mark-hover` is the case: a resting mouse over a marked box paints the
  // indicated weight in the mark's own ink, and unnamed it no longer answers the
  // keyboard's question for every stop underneath it.
  const named = (el) =>
    getComputedStyle(el).getPropertyValue('--lf-here-ring').trim() !== 'none';
  if (shown(e)) return null;
  for (let el = e.parentElement ?? e.getRootNode().host ?? null; el;
       el = el.parentElement ?? el.getRootNode().host ?? null)
    if (shown(el) && (getComputedStyle(el).outlineStyle === 'auto' || named(el)))
      return null;
  const shadow = getComputedStyle(e).boxShadow;
  if (mixed && shadow.includes(mixed)) return null;
  const cls = typeof e.className === 'string' && e.className.trim()
    ? '.' + e.className.trim().split(/\\s+/).join('.') : '';
  return e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + cls
    + ' [outline ' + getComputedStyle(e).outlineStyle + ', shadow ' + shadow + ']';
}}"""


def test_the_stop_reading_names_a_control_with_nothing_drawn_on_it(browser, serve):
    """The reach half of the stop reading, which the corpus walk cannot supply.

    The walk asserts that no stop goes unseen, and a reading that had gone blind returns
    exactly what a clean corpus returns. Every other reading in that test says how far it
    reaches — the ring population is asserted before it is divided by, the scopes are
    asserted opened and walked, and the fault reading has two plants of its own — and
    this one arrived with none. The direction that goes quiet is `shown` answering true
    too often: one future rule putting `outline-style: auto` on a chrome wrapper would
    answer for every stop beneath it, and the walk would stay green reporting a clean
    corpus.

    So: a real control, reached by a real Tab, with its indication taken away. The
    control case first and in the same run, because a reading that named every button
    would name the planted one without seeing it."""
    url = serve(LONG_PAGE, comments=2)
    page, errors = open_page(browser, url)
    page.evaluate(RING_WALK_START)
    for _ in range(60):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => Boolean(document.activeElement?.matches('.lf-threads-toggle'))"
        ):
            break
    else:
        raise AssertionError("Tab never reached the banner's comments button")
    page.evaluate(RENDERED)

    assert page.evaluate(SEEN_STOP) is None, (
        "a banner button wearing the layer's own ring reads as a stop nothing draws, so "
        "the walk's whole assertion is about a reading that answers for every control"
    )

    page.evaluate("""() => {
        const style = document.createElement('style');
        style.textContent =
          '.lf-threads-toggle:focus-visible { outline: none !important;'
          + ' box-shadow: none !important; }';
        document.head.append(style);
    }""")
    page.evaluate(RENDERED)
    lost = page.evaluate(SEEN_STOP)
    assert lost and "lf-threads-toggle" in lost, (
        "the ring was taken off a focused control and the reading still called it seen "
        f"({lost}), so the walk cannot report a stop the reader cannot find"
    )

    page.close()
    assert errors == [], errors


def test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus(
    browser, serve, live_leaf
):
    """The invariant asked of the whole layer and its causal corpus at once. Neither
    half is evidence without the other: a clean walk says nothing about a rule it never
    met, and a rule the walk met says nothing if the reading excused every side of it.

    The population is the rings the layer declares (`RING_NAMES`), read out of the
    page's own composed stylesheets rather than kept in a list beside them, for the
    reason the runtime reads the merged registry: a twelfth widget must not need a
    handwritten list updated, and the list that was here in prose was already wrong.
    What is credited is the name the cascade handed the box, so a ring is lit by the
    rule the reader is looking at rather than by every rule whose selector reached it.

    Two halves guard the naming itself, because neither can see what the other does. The
    scan reaches a rule the corpus never paints and cannot tell a ring drawn some other
    way from no ring at all; the sweep is the reverse of both, and says when a box paints
    a ring nothing named. And the population is asserted before it is divided by, since
    an empty one makes every line above vacuous while reporting what a clean corpus does.

    Tab, because that is the walk every page has and it reaches the page's own controls
    and the runtime's chrome in one order. The scopes are what Tab alone cannot reach. A
    settled group is opened for the same reason — its options are behind a disclosure,
    and the pick's own ring is the one the joined group form takes away, so it is only
    ever drawn in a group that has been settled.

    Two things this walk cannot take from an example, each set up the way the product
    makes it: a second version, so the versions menu has a comparison to offer, and a
    neighbouring leaf, so the leaves tray has a row. Neither can live in the corpus — an
    example's markup is v1 and nothing revises it, and a live leaf is state under the
    state home rather than page content.
    """
    live_leaf("other", "The other leaf")
    # The reader's default motion. No ring in this layer moves under either setting —
    # the reduced-motion guard removes transitions rather than shortening them
    # (theme.css), which is what `test_a_reader_who_asked_for_no_motion_gets_a_ring_
    # that_does_not_arrive` holds — so a walk that reads two frames after a press reads
    # the ring the rule states.
    rings, lit, faults, seen_faults = {}, set(), [], set()
    unseen = set()
    unnamed = set()
    opened, walked_in, errors = set(), set(), []
    stops = 0
    examples = {example.stem: example for example in EXAMPLES}
    assert not (missing := set(RING_WALK_EXAMPLES) - set(examples)), (
        "the ring walk names examples that no longer exist: "
        + ", ".join(sorted(missing))
    )
    for name in RING_WALK_EXAMPLES:
        example = examples[name]
        # The path, not the markup: the fixture lays in the log the example ships, and a
        # thread and the widgets a message carries are controls this walk has to stand
        # on. One of those threads is anchored to an element rather than a passage,
        # which is the only way a ring is painted on the page for a focus held in the
        # panel.
        url = serve(example, comments=2)
        # A version to compare against, published the way a page gets one. Serving v2
        # rather than letting the open page follow keeps the walk out of an activation.
        _publish(serve.page_dir, 2, example.read_text(), "Same page, said twice.")
        page, console = open_page(browser, url.replace("/v1.html", "/v2.html"))
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        # Opened, not pressed for a decision: a settled group's disclosure is this
        # reader's view state and no version carries it. One in an exhibit is quoted,
        # so its marks are spans with nothing to focus, and one in a shut panel has no
        # box — neither is a place a ring can be drawn, and neither can be clicked.
        for row in page.locator("lf-options[settled] > .lf-settled").all():
            if row.is_visible():
                row.click()
        # And the resolved threads, for the same reason and with the same shape: a
        # closed thread's Reopen is behind this disclosure, so a walk that leaves it
        # shut reaches every control in the panel except the one on the far side of an
        # answered conversation.
        resolved = page.locator(".lf-details > summary")
        if resolved.count() and resolved.is_visible():
            resolved.click()
        page_at_rest(page)

        for scope, keys, corpus in RING_WALKS:
            if name not in corpus:
                continue
            # The posture the scope's own surface stands in, read after the panel below
            # has settled and put back afterwards, so the next scope walks the page this
            # one was handed. Before the panel, the room a floor is measured against is
            # the room the panel was still taking.
            posture = RING_SCOPE_WIDTH.get(scope)
            # Three rungs, because a scope can be three deep: a tray, menu, or narrowing
            # over the panel, then the panel, then the page. The panel is reopened below,
            # so every scope starts from the same page.
            for _ in range(3):
                page.keyboard.press("Escape")
            # A draft editor and captured source are conditional chrome: Tab can stand
            # on them only after their explicit doors have opened. Do that after the
            # scope reset, whose Escape presses would otherwise put the draft away.
            if scope == "the page":
                pencil = page.locator(".lf-draft-controls .lf-draft-pencil").first
                if pencil.count() and pencil.is_visible():
                    pencil.click()
                source = page.locator("details:has(lf-source)").first
                if (
                    source.count()
                    and source.is_visible()
                    and not source.get_attribute("open")
                ):
                    source.locator(":scope > summary").click()
            page.evaluate(RING_WALK_START)
            # Threads and a target's own Thread card are one surface offered two ways:
            # with the panel standing, a Thread Button sends the reader there instead of
            # building the card, so the card's walk is the one scope that starts with the
            # panel shut. Every other scope starts from the same open-panel page.
            if scope in RING_SCOPES_WITHOUT_PANEL:
                if page.locator(".lf-panel.open").count():
                    page.get_by_role("button", name="Close threads").click()
                    panel_settled(page, open=False)
                    page.evaluate(RING_WALK_START)
            elif not page.locator(".lf-panel.open").count():
                page.locator(".lf-threads-toggle").click()
                panel_settled(page)
                page.evaluate(RING_WALK_START)
            if posture:
                resized(page, posture, RING_WALK_VIEWPORT[1])
                page_at_rest(page)
            if control := RING_SCOPE_CONTROL.get(scope):
                opener, arrival = control
                # The first, because a page map has one Thread Button per commented
                # target and the walk wants a card rather than a particular one.
                page.locator(opener).first.click()
                page.locator(arrival).first.focus()
                # A press opened the scope and a script placed the reader in it, and
                # neither is the keyboard: `:focus-visible` answers the input device, so
                # a control arrived at that way wears no ring and reads exactly like one
                # whose rule is missing. Step out and back so the walk's first stop is a
                # keyboard stop like every stop after it.
                #
                # These two are read on a rendered frame rather than on the settled page
                # the walk below presses against, and they carry the same exposure: the
                # scroll the opening click caused may still be being answered when the
                # Shift+Tab lands, so it can be answered in a stale order. What that
                # costs is bounded, which is why the weaker wait is left here — the
                # `page_at_rest` below runs before the first stop is read, and the walk
                # runs until the order comes round, so a stale step out and back moves
                # where the walk starts rather than what it covers.
                page.keyboard.press("Tab")
                page.evaluate(RENDERED)
                page.keyboard.press("Shift+Tab")
            else:
                # Each press read on a rendered frame, rather than on the settled page
                # every Tab below it is pressed against: what the next key of the
                # sequence needs is the focus the last press left, and the scope's own
                # arrival is waited for once below before the first stop is read. A
                # key that opens a layer hands the reader their place in it from the
                # platform's own event rather than from the press — a popover lands focus
                # on a row from `toggle`, which is queued — so the next key of the
                # sequence arrives at whatever the press left focus on, and the scope's
                # own keys, bound inside the layer, never see it.
                for key in keys:
                    page.keyboard.press(key)
                    page.evaluate(RENDERED)
            page_at_rest(page)
            surface, offers = RING_SCOPE_SURFACE.get(scope, (None, None))
            if surface and (offers is None or offered(page, offers)):
                assert page.locator(surface).count() == 1, (
                    f"{RING_SCOPE_CONTROL.get(scope, (' '.join(keys),))[0]} did not open "
                    f"{scope} on {example.stem}, which "
                    "offers it, so this walk is the page's over again"
                )
                opened.add(scope)

            # The tab order comes back round, so the walk ends when it reaches a control
            # it has already stood on. The cap is a backstop against a page whose order
            # never repeats.
            page.evaluate("() => { window.__lfSeen = new WeakSet(); }")
            where = f"in {scope} of {example.stem}"
            walked, empty, came_round = 0, 0, False
            for _ in range(400):
                if walked or empty:
                    # On the settled page, not merely on a rendered frame. Standing on a
                    # control scrolls the page to it, and the living margin answers that
                    # scroll by re-placing its clusters — which moves the page's own
                    # Buttons, since a widget's Button is contributed to a cluster rather
                    # than left where the widget built it. A Tab pressed while that is in
                    # flight is answered in the order the previous frame had, so the
                    # walk's next stop is read off one arrangement and its next press
                    # made against another: measured under the suite's own load, the
                    # order stepped over the whole of lf-shot — its transparent flip and
                    # the keyboard proxy beside it — and the walk stood on the shot's
                    # Button instead, leaving the `shot` ring painted nowhere the corpus
                    # could be walked to while every control involved was focusable
                    # before the press and after it.
                    page_at_rest(page)
                    page.keyboard.press("Tab")
                stop = page.evaluate(RING_NEW_STOP)
                if stop == "seen":
                    came_round = True
                    break
                if stop == "empty":
                    # Nothing to stand on, which is two different things and neither of
                    # them the end of the walk. The key that opened the scope may have
                    # landed focus on nothing; and the tab order runs off the end of the
                    # document and comes back in through it, so a scope the walk joins
                    # part-way down its own order — the Page-map sheet, which it enters at
                    # the list — keeps the stops above its starting point on the far side
                    # of that crossing. Walking through it is how they are reached at all;
                    # the order still ends where it comes round to a stop already stood
                    # on. Two in a row is the cap, not four hundred: a walk that never
                    # starts should say so rather than read as a slow test.
                    empty += 1
                    if empty > 2:
                        came_round = True
                        break
                    continue
                empty = 0
                walked, stops = walked + 1, stops + 1
                if (lost := page.evaluate(SEEN_STOP)) is not None:
                    unseen.add(f"{where}: {lost}")
                drawn = rings_drawn(page)
                for ring in drawn:
                    if not ring["here"]:
                        continue
                    if ring["ring"]:
                        lit.add(ring["ring"])
                    else:
                        unnamed.add(ring["who"])
                # One standing defect is one finding, not one per stop: a ring worn by
                # something the walk is not moving — a decision's mark, a thread's element
                # mark — is read again at every stop it survives.
                for fault in ring_faults(drawn, where):
                    if fault not in seen_faults:
                        seen_faults.add(fault)
                        faults.append(fault)
            # A control the runtime replaces on repaint is a new element at every Tab, so
            # the walk never meets a repeat and runs the cap out: sixteen times the work
            # and no message, which reads as a hang rather than as the fault it is.
            assert came_round, (
                f"the walk {where} never came back round to a control it had already "
                f"stood on, so it ran its cap out at {walked} stops"
            )
            if walked:
                walked_in.add(scope)
            elif surface and scope in opened:
                raise AssertionError(
                    f"{scope} opened on {example.stem} and the walk stood on nothing "
                    "in it"
                )
            if posture:
                for _ in range(3):
                    page.keyboard.press("Escape")
                resized(page, *RING_WALK_VIEWPORT)
                page_at_rest(page)

        for declared in page.evaluate(RING_NAMES):
            seen = rings.setdefault(declared["name"], [])
            for said in declared["said"]:
                if said not in seen:
                    seen.append(said)
        errors += [f"{example.stem}: {e}" for e in console]
        page.close()

    assert not unseen, (
        "the walk stood on a control and nothing on screen said where the keyboard was, "
        "so a reader arriving by Tab has no way to tell: "
        f"{sorted(unseen)}"
    )
    assert not errors, errors
    # Across the causal walk, because a scope can be dead on a page with nothing to put
    # in it. What cannot happen is a scope no selected example ever opens or walks: then its
    # keys are unread and everything below is silent about the controls behind them.
    missing = [s for s in RING_SCOPE_SURFACE if s not in opened] + [
        f"{s} (walked nothing)"
        for s, _keys, _corpus in RING_WALKS
        if s not in walked_in
    ]
    assert not missing, "no selected example reached " + ", ".join(sorted(missing))
    assert not faults, "\n  ".join(
        [f"{len(faults)} faults over {stops} stops:"] + faults
    )
    # A ring nobody named, said from either side. The scan reaches a rule the corpus
    # never paints and cannot tell a ring drawn some other way from no ring at all; the
    # sweep is the reverse of both. Neither half is the whole claim, and a name is worth
    # nothing to the floor below until both agree it stands for one drawn ring.
    unnamed_rules = rings.pop("", [])
    assert not unnamed_rules, (
        f"{len(unnamed_rules)} rules draw the here ring and name none of them, so the "
        "floor below divides by a population short of them and says nothing about "
        "it — declare --lf-here-ring in the rule that draws the ring:\n  "
        + "\n  ".join(sorted(unnamed_rules))
    )
    assert not unnamed, (
        "the corpus paints a here ring on boxes no rule named, so no reading can say "
        "which rule drew it: " + ", ".join(sorted(unnamed))
    )
    # Both halves of the division, before it is taken. An empty population makes every
    # line below vacuous and silent about it, and a name painted that the scan never
    # declared is the scan's own blind spot showing: it reads the `outline` shorthand for
    # the layer's token, so a rule that draws the ring some other way and still names it
    # paints a credit for a name no population holds.
    assert rings, (
        "the layer declares no rings, so this floor divided by nothing and the walk "
        "above is evidence about no rule at all"
    )
    assert not lit - set(rings), (
        "the corpus painted rings the layer's own reading does not declare: "
        + ", ".join(sorted(lit - set(rings)))
    )
    unlit = [
        f"{name} ({', '.join(said)})"
        for name, said in sorted(rings.items())
        if name not in lit
    ]
    assert not unlit, (
        f"{len(unlit)} of the layer's {len(rings)} rings are painted nowhere the "
        f"corpus can be walked to, so nothing above is evidence about them:\n  "
        + "\n  ".join(unlit)
    )


# Every declaration in the page's composed layer that lifts a box off the page: a
# box-shadow with a blur radius. A ring is `0 0 0 Npx` and an inset band is `inset …`, so
# the reading asks for a third length that is not nought — which is the one thing that
# separates elevation from the other two uses of the property, and is decidable from the
# declaration where "is this a shadow" is not.
#
# Flat and condition-blind for the reasons RING_NAMES gives next door: nothing re-runs a
# selector, and a shadow painted only in some other medium is one this reading should say
# nothing about.
ELEVATION_SHADOWS = """() => {
  const found = [];
  const eaten = new Set();
  const eat = (sheet) => {
    if (!sheet || eaten.has(sheet)) return;
    eaten.add(sheet);
    let list;
    try { list = sheet.cssRules; } catch { return; }  // a sheet from another origin
    const walk = (from) => {
      for (const rule of from) {
        for (const property of ['box-shadow', '--lf-lift', '--lf-ring']) {
          const value = rule.style?.getPropertyValue(property)?.trim();
          if (!value || value === 'none') continue;
          // The blur, which is the third length of a layer, past the two offsets. A ring
          // writes `0 0 0 Npx` and has none; an inset band is not a lift at all. Read per
          // layer, because a control may state its ring and its lift in one declaration.
          const lifts = value.split(/,(?![^(]*\\))/).filter((layer) => {
            if (/(^|\\s)inset(\\s|$)/.test(layer)) return false;
            const lengths = layer.trim().split(/\\s+/)
              .filter((token) => /^-?(\\d*\\.)?\\d+(px)?$/.test(token));
            return lengths.length >= 3 && parseFloat(lengths[2]) !== 0;
          });
          if (!lifts.length) continue;
          const own = rule.selectorText;
          const up = rule.parentRule?.selectorText;
          found.push({
            said: own && up ? `${up} { ${own}` : (own ?? up ?? '(a declaration)'),
            property,
            value: lifts.map((layer) => layer.trim()).join(', '),
          });
        }
        if (rule.cssRules) walk(rule.cssRules);
      }
    };
    walk(list);
  };
  const roots = [document];
  for (const root of roots) {
    for (const sheet of root.styleSheets) eat(sheet);
    for (const sheet of root.adoptedStyleSheets) eat(sheet);
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) roots.push(el.shadowRoot);
  }
  return found;
}"""


def test_every_shadow_the_layer_lifts_a_box_with_is_cast_in_the_scheme_s_own_ink(
    browser, serve
):
    """A drop shadow written as rgba(0,0,0,α) can only be right about one ground.

    At .12 over the light paper a menu lifts its ground by 10 L*. The same declaration
    over the dark paper lifts it by 1.4, which is a shadow that is in the stylesheet and
    not on the screen — and nine of the layer's twelve elevation shadows were written that
    way, each with an alpha of its own between .12 and .24. --shade is the ink, stated once
    per scheme, and depth is left to the offsets and the blur that were already saying it.

    Asked of the declarations rather than of the paint, because that is where the fault
    is: on the dark ground the difference between the value that reads and the value that
    does not is 4 L*, which no screenshot of a blurred edge will tell you about reliably,
    while "does this name the token" is exact. The two schemes are then asked for
    different answers from the token itself, which is the whole of what one hard-coded
    colour could not do.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    lifted = page.evaluate(ELEVATION_SHADOWS)
    assert len(lifted) >= 10, (
        f"the layer declares {len(lifted)} elevation shadows, which is fewer than it "
        f"ships: this reading has stopped finding them and the assertion below is "
        f"about nothing"
    )
    raw = [shadow for shadow in lifted if "var(--shade)" not in shadow["value"]]
    assert not raw, (
        f"{len(raw)} of the layer's {len(lifted)} elevation shadows are cast in a "
        f"colour of their own rather than in --shade, so the dark scheme cannot answer "
        f"for them:\n  "
        + "\n  ".join(f"{s['said']} — {s['property']}: {s['value']}" for s in raw)
    )
    light = page.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--shade')"
    )
    assert errors == []
    page.close()

    dark, dark_errors = open_page(browser, serve(LONG_PAGE), color_scheme="dark")
    shade = dark.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--shade')"
    )
    assert shade.strip() and shade.strip() != light.strip(), (
        f"both schemes cast their shadows in {shade!r}, so routing them through a token "
        f"bought the dark page nothing it did not already have"
    )
    assert dark_errors == []
    dark.close()


# Every box the layer promises a press on, wherever it stands. Not a list of class names:
# what makes something a target is that the runtime built it (data-lf-offer) or that it
# stands in the runtime's own layer, and that the page under the pointer says a press
# lands there. A twelfth control joins by being one, which is how the six this first
# reported were found.
#
# The reading takes the element's box together with any absolutely positioned pseudo it
# hangs, because an aim need not be the thing the reader sees: a mark six pixels wide set
# in a line of prose cannot grow without opening the line, so it carries a box of its own.
#
# Inline boxes are out, and that is the target-size exception rather than an excuse: a
# link inside a sentence is sized by the words around it, and nothing can be done about
# that which does not damage the sentence.
AIM_BOXES = """(floor) => {
  const found = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(
    '[data-lf-offer], .lf-chrome button, .lf-chrome [role="button"],' +
    ' .lf-chrome [role="checkbox"], .lf-chrome [role="tab"], .lf-chrome .lf-btn,' +
    ' .lf-chrome .lf-pill, .lf-chrome .lf-quote'
  )) {
    if (seen.has(el)) continue;
    seen.add(el);
    const style = getComputedStyle(el);
    if (!['pointer', 'grab'].includes(style.cursor)) continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
    if (style.display === 'inline') continue;
    // The option mark is the one control held out, and it is a handover rather than an
    // exemption: its box is being rewritten alongside the group's pressable rule, and
    // this line goes with that change. It stands at 11x11 today.
    if (el.classList.contains('lf-pick')) continue;
    const box = el.getBoundingClientRect();
    if (!box.width || !box.height) continue;
    let [w, h] = [box.width, box.height];
    for (const pseudo of ['::before', '::after']) {
      const at = getComputedStyle(el, pseudo);
      if (at.content === 'none' || at.position !== 'absolute') continue;
      w = Math.max(w, parseFloat(at.width) || 0);
      h = Math.max(h, parseFloat(at.height) || 0);
    }
    const name = (el.className || el.tagName).toString().trim().split(/\\s+/)[0];
    if (Math.min(w, h) < floor - 0.5)
      found.push(`${name} at ${w.toFixed(1)}x${h.toFixed(1)}`);
  }
  return found;
}"""

# What the sweep has to have stood in front of before its answer means anything. Each is
# on a surface the walk has to open, and each was under the floor.
AIM_SURFACES = (
    ".lf-thread-action",
    ".lf-preview",
    ".lf-pill",
    ".lf-version-diff",
    ".lf-help-command",
    ".lf-quote",
    ".lf-gloss-mark",
    ".lf-tab-btn",
    ".lf-grip",
)


def _each_aim_surface(page, page_dir):
    """Stand each surface up in turn, yielding at every stop.

    In turn rather than all at once, because they do not coexist: the reference is modal
    and takes the version menu down as it opens, so a sweep that waited for the last of
    them would meet a page that had put two of the controls away again.
    """
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comment = next(
        e["id"] for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    )
    # A resolved thread, which is the only state that has a Reopen to aim at.
    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)
    expect(page.locator(".lf-details summary")).to_have_count(1)
    page.locator(".lf-details summary").click()
    expect(page.locator(".lf-reopen")).to_have_count(1)
    yield

    page.locator(".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    yield
    page.keyboard.press("Escape")

    # Twice: the first press unfolds the shelf, the second opens the reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help-command").first).to_be_visible()
    yield


@pytest.mark.parametrize("touch", (False, True))
def test_every_control_the_layer_offers_is_a_box_the_reader_can_hit(
    browser, serve, touch
):
    """A press the reader cannot land on is a capability the page does not have.

    Measured before --aim-floor existed, at 1200x900: a thread's Reopen and the panel's
    reaction pills stood at 20 and 22 pixels tall, the banner's page preview at 23, and a
    version's Δ, a command in the reference, a quote and a gloss mark at around twelve by
    seven. Three controls reached the coarse-pointer block and the rest reached neither
    floor, so the same presses were small under a finger too.

    The sweep names no control. What makes a box an aim is that the runtime built it or
    stands in the runtime's own layer, and that the page under the pointer says a press
    lands there — so the next control the layer grows is held to this without anybody
    adding it to a list. Both pointers are asked, from the one token that states the
    floor, because a control comfortable under one and not the other is the fault this is
    about rather than a lesser version of it.

    The surfaces have to be opened for any of it to mean anything: seven of the nine
    controls at issue exist only inside a panel, a menu, a resolved disclosure or the
    reference, and a sweep of the page at rest would report a clean layer while every one
    of them was still six pixels tall. AIM_SURFACES is that assertion.
    """
    context = (
        browser.new_context(viewport={"width": 1200, "height": 900}, has_touch=True)
        if touch
        else None
    )
    example = next(e for e in EXAMPLES if e.stem == "corpus")
    # A preview record, because the badge it puts in the banner is one of the aims and
    # exists on no page that was not served by the preview script.
    served = serve(
        example,
        comments=2,
        preview={
            "kind": "example",
            "example": "corpus",
            "checkout": "fb77",
            "started": "2026-08-31T12:00:00+00:00",
        },
    )
    # A second version, published the way a page gets one and read from, so the versions
    # menu has an earlier version to compare against and its Δ exists to be aimed at.
    _publish(serve.page_dir, 2, example.read_text(), "Same page, said twice.")
    page, errors = open_page(
        browser, served.replace("/v1.html", "/v2.html"), context=context
    )
    floor = 44 if touch else 24
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch, (
        "the fixture did not reach the pointer medium this run is about, so the floor "
        "below is the other one's"
    )
    small, stood = [], set()
    for _ in _each_aim_surface(page, serve.page_dir):
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
    assert errors == []
    page.close()
    if context:
        context.close()
