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
    BOTH_STAMPS,
    COMMAND_HUB_PACKAGE,
    DEEP_FOCUS,
    DEFINE_BOXES,
    DIFF_PAGE,
    EXAMPLES,
    LONG_PAGE,
    MANY_ASKS_PAGE,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    PANEL_DIFF_MARKUP,
    RENDERED,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    RING_NAMES,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SCROLLED,
    SUGGESTION_PAGE,
    TOKEN,
    UNBREAKABLE_PAGE,
    WIDE_DIFF_PAGE,
    CutOff,
    _publish,
    _traffic,
    _until,
    actions,
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
    select,
    serious_axe_violations,
    stamp_version_file,
    standing_ring,
    token_colour,
    told,
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
<lf-options id="stable-options" choose>
  <lf-option id="stable-choice-a" for="control-target">Keep A</lf-option>
  <lf-option id="stable-choice-b" for="control-target">Keep B</lf-option>
</lf-options>
<lf-tabs id="stable-tabs">
  <lf-tab id="stable-tab-a" label="First">First panel.</lf-tab>
  <lf-tab id="stable-tab-b" label="Second">Second panel.</lf-tab>
</lf-tabs>
""",
    head='<meta name="lf-review" content="sign-off">',
)

# The rendered control mechanisms whose rows must keep their geometry across a press.
# `coverage` classifies the mechanisms rendered by the composed gallery; `target` is
# the one causal transition that proves the mechanism's stability contract.
CONTROL_ARCHETYPES = (
    {
        "name": "banner",
        "coverage": ".lf-banner-actions > button",
        "target": ".lf-signoff",
    },
    {
        "name": "suggestion",
        "coverage": ".lf-sug-actions > [role=button]",
        "target": '[data-lf-for="stable-suggestion"] .lf-sug-accept',
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
        "title", "Approve this work; the page stays open for follow-up (L)"
    )
    expect(button).to_have_attribute("aria-keyshortcuts", "Shift+l")

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

        page.locator(".lf-comments").click()
        expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(button).to_be_enabled()
        assert errors == []
    finally:
        page.close()


def test_a_page_that_asks_nothing_carries_no_terminal_control(browser, serve):
    """A page that only informs ends at Comments and offers no terminal action.

    The slot the approve button takes on a sign-off page stays empty here rather than
    picking up a neutral control, which is the fact a reader can see: an informational
    page asks them for nothing, so it hands them nothing to press.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The banner is built in one pass, so a control standing in it is what makes the
    # absence beside it worth reading rather than a row that never rendered.
    expect(page.locator(".lf-comments")).to_be_visible()
    expect(page.locator(".lf-banner-actions > *").last).to_have_class(
        re.compile(r"\blf-comments\b")
    )
    assert page.locator(".lf-signoff").count() == 0
    # Approval takes the slot beside Comments where a page asks for one, so the absence
    # above is the whole fact: the row is a control short rather than a control longer.
    assert errors == []
    page.close()


def test_the_responsive_action_shelf_keeps_primary_actions_in_reach(browser, serve):
    """The action shelf keeps state and every destination reachable at any width.

    A narrow viewport is not a cropped desktop toolbar. Secondary destinations may live
    in a horizontally scrollable row, but the two actions that complete the reading loop
    must be in the first view from a 320px phone through a small tablet. Above the covering
    breakpoint the same row must keep every crowded destination reachable, and the
    document itself must never become its scroller.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page, errors = open_page(browser, url)

    button_widths = (
        "() => ['.lf-comments', '.lf-signoff'].map(selector => "
        "document.querySelector(selector).offsetWidth)"
    )
    resized(page, 1200, 844)
    wide_widths = page.evaluate(button_widths)
    resized(page, 320, 844)
    phone_widths = page.evaluate(button_widths)
    assert all(phone < wide for phone, wide in zip(phone_widths, wide_widths)), (
        "the covering shelf's tighter button padding was masked by wide reservations: "
        f"wide={wide_widths}, phone={phone_widths}"
    )
    resized(page, 1200, 844)
    assert page.evaluate(button_widths) == wide_widths, (
        "button reservations did not return to their wide measurements after the "
        "covering shelf was left"
    )

    def assert_primary_reach(width):
        resized(page, width, 844)
        boxes = page.evaluate(
            """() => Object.fromEntries(
              ['.lf-banner-status', '.lf-comments', '.lf-signoff'].map(selector => {
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
            assert boxes[".lf-comments"]["height"] >= 40
            assert boxes[".lf-signoff"]["height"] >= 40
        assert page.evaluate(
            "() => document.documentElement.scrollWidth"
            "   === document.documentElement.clientWidth"
        ), "the banner made the page itself scroll sideways"

    for width in (320, 390):
        assert_primary_reach(width)

    resized(page, 320, 844)
    actions = page.locator(".lf-banner-actions")
    actions.evaluate("el => { el.scrollLeft = 0; el.tabIndex = -1; el.focus(); }")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-comments")).to_be_focused()
    assert actions.evaluate("el => el.scrollLeft") == 0
    phone_focus_room = page.locator(".lf-comments").evaluate(
        """el => {
          const shelf = el.parentElement.getBoundingClientRect();
          const button = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
          return {top: button.top - outset - shelf.top,
                  left: button.left - outset - shelf.left,
                  bottom: shelf.bottom - button.bottom - outset};
        }"""
    )
    assert all(room >= -0.01 for room in phone_focus_room.values()), (
        f"the phone shelf clipped its focused control's ring: {phone_focus_room}"
    )
    page.keyboard.press("Tab")
    expect(page.locator(".lf-signoff")).to_be_focused()
    assert actions.evaluate("el => el.scrollLeft") == 0

    # The covering comments workspace locks the page behind it. Shelf overflow must not
    # become a side door around that lock when a wheel reaches the shelf's boundary.
    page.locator(".lf-comments").click()
    expect(page.locator(".lf-panel")).to_be_visible()
    locked = actions.evaluate(
        """actions => {
          actions.scrollLeft = actions.scrollWidth;
          document.body.scrollTop = 400;
          const before = document.body.scrollTop;
          const event = new WheelEvent('wheel', {
            bubbles: true, cancelable: true, deltaY: 120
          });
          actions.dispatchEvent(event);
          return {before, after: document.body.scrollTop,
                  overflow: getComputedStyle(document.body).overflowY};
        }"""
    )
    assert locked == {"before": 400, "after": 400, "overflow": "hidden"}, (
        f"the action shelf bypassed the covering panel's page lock: {locked}"
    )
    page.locator(".lf-comments").click()
    expect(page.locator(".lf-panel")).to_be_hidden()

    # Simulate the row's reachable busy state at the upper covering breakpoint. The
    # identities do not matter to the layout contract; the product controls all carry
    # this same class and can arrive asynchronously as comments, asks and page news do.
    page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          for (let i = 0; i < 5; i++) {
            const button = document.createElement('button');
            button.className = 'lf-ui lf-btn';
            button.textContent = `Secondary destination ${i + 1}`;
            actions.append(button);
          }
        }"""
    )
    assert_primary_reach(768)
    assert page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          return actions.scrollWidth > actions.clientWidth;
        }"""
    ), "the crowded tablet row had no independent horizontal shelf"

    # Just above the covering breakpoint the banner stays on one line, but its actions
    # still belong to a shelf when all their addresses do not fit. Focusing the last one
    # must bring it fully on screen rather than walking the keyboard through clipped UI.
    assert_primary_reach(900)
    actions.evaluate("el => { el.scrollLeft = 0; }")
    actions_box = actions.bounding_box()
    page.mouse.move(
        actions_box["x"] + actions_box["width"] / 2,
        actions_box["y"] + actions_box["height"] / 2,
    )
    page.mouse.wheel(0, 120)
    page.wait_for_function(
        "() => document.querySelector('.lf-banner-actions').scrollLeft > 0"
    )
    # Once the shelf has spent the part it can consume, Chromium will not naturally
    # chain the rest out of this overflow box. Leaf hands that remainder to its body
    # scroller, while a browser zoom gesture remains wholly the browser's.
    edge = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          actions.scrollLeft = actions.scrollWidth;
          document.body.scrollTop = 200;
          return {shelf: actions.scrollLeft, page: document.body.scrollTop};
        }"""
    )
    page.mouse.wheel(0, 120)
    page.wait_for_function(
        "(before) => document.body.scrollTop > before", arg=edge["page"]
    )
    assert actions.evaluate("el => el.scrollLeft") == edge["shelf"], (
        "the shelf moved past its end instead of handing the wheel to the page"
    )
    shifted_page = page.evaluate("() => document.body.scrollTop")
    page.keyboard.down("Shift")
    page.mouse.wheel(0, 120)
    page.keyboard.up("Shift")
    assert page.evaluate("() => document.body.scrollTop") == shifted_page, (
        "Shift+wheel at the shelf edge unexpectedly became vertical page scrolling"
    )
    page_delta = actions.evaluate(
        """actions => {
          actions.scrollLeft = actions.scrollWidth;
          document.body.scrollTop = 100;
          const before = document.body.scrollTop;
          const page = document.body.clientHeight;
          const limit = document.body.scrollHeight - page;
          actions.dispatchEvent(new WheelEvent('wheel', {
            bubbles: true, cancelable: true, deltaMode: WheelEvent.DOM_DELTA_PAGE,
            deltaY: 1
          }));
          return {before, after: document.body.scrollTop, page, limit};
        }"""
    )
    assert page_delta["after"] == pytest.approx(
        min(page_delta["limit"], page_delta["before"] + page_delta["page"]), abs=1
    ), f"a page-unit shelf remainder used the shelf's width: {page_delta}"
    zoom = actions.evaluate(
        """actions => {
          actions.scrollLeft = 0;
          const before = actions.scrollLeft;
          const event = new WheelEvent('wheel', {
            bubbles: true, cancelable: true, ctrlKey: true, deltaY: 120
          });
          const dispatched = actions.dispatchEvent(event);
          return {before, after: actions.scrollLeft,
                  prevented: !dispatched || event.defaultPrevented};
        }"""
    )
    assert zoom == {"before": 0, "after": 0, "prevented": False}, (
        f"the action shelf intercepted browser zoom: {zoom}"
    )
    last = actions.locator(":scope > .lf-btn").last
    actions.evaluate("el => { el.scrollLeft = 0; }")
    last.focus()
    page.wait_for_function(
        "() => document.querySelector('.lf-banner-actions').scrollLeft > 0"
    )
    last_box = last.evaluate(
        "el => { const r = el.getBoundingClientRect(); return {left: r.left, right: r.right}; }"
    )
    assert 0 <= last_box["left"] < last_box["right"] <= 900, (
        f"the wide action shelf focused a clipped destination: {last_box}"
    )
    focus_room = last.evaluate(
        """el => {
          const shelf = el.parentElement.getBoundingClientRect();
          const button = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
          return {top: button.top - outset - shelf.top,
                  right: shelf.right - button.right - outset,
                  bottom: shelf.bottom - button.bottom - outset};
        }"""
    )
    assert all(room >= -0.05 for room in focus_room.values()), (
        f"the action shelf clipped its focused control's ring: {focus_room}"
    )

    # Prepare the live half of one publication before opening its pinned witness below.
    # A composer deliberately defers activation; news inserted before the later
    # destinations must scroll the shelf by the same amount, keeping the keyboard's
    # current address visible and under its ring.
    heading = page.locator("#t")
    heading_box = heading.bounding_box()
    select(
        page,
        (heading_box["x"] + 2, heading_box["y"] + heading_box["height"] / 2),
        (
            heading_box["x"] + heading_box["width"] - 2,
            heading_box["y"] + heading_box["height"] / 2,
        ),
    )
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    last.focus()
    before_news = last.evaluate("el => el.getBoundingClientRect().left")
    live, live_errors, live_last = page, errors, last

    # A pinned wide page reserves the Latest chip before it first has news, but the same
    # invisible slot on a phone would be a blank stretch of the horizontal shelf. The next
    # real destination peeking into view is both the collapse witness and the overflow cue.
    pinned, pinned_errors = open_page(browser, url, pin=True)
    resized(pinned, 320, 844)
    expect(pinned.locator(".lf-latest-chip")).to_be_hidden()
    assert pinned.locator(".lf-latest-chip").evaluate("el => el.offsetWidth") == 0
    version = pinned.locator(".lf-version").evaluate(
        "el => { const r = el.getBoundingClientRect(); return {left: r.left, right: r.right}; }"
    )
    assert 0 < version["left"] < 320 < version["right"], (
        f"the next phone destination did not peek past the primary actions: {version}"
    )
    (serve.page_dir / "versions" / "v2.html").write_text(html)
    stamp_version_file(serve.page_dir, 2, "two")
    expect(pinned.locator(".lf-latest-chip")).to_be_visible()
    news_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth, className: el.className, "
        "        flex: getComputedStyle(el).flex, basis: el.style.width})"
    )
    assert news_size["shown"] >= news_size["needed"], (
        f"the shown phone news address clipped its words: {news_size}"
    )
    resized(pinned, 1200, 844)
    news_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth})"
    )
    assert news_size["shown"] >= news_size["needed"], (
        f"the shown desktop news address clipped its words: {news_size}"
    )

    expect(live.locator(".lf-latest-chip")).to_be_visible()
    expect(live_last).to_be_focused()
    after_news = live_last.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return {left: r.left, right: r.right}; }"
    )
    assert abs(after_news["left"] - before_news) <= 0.5, (
        f"version news moved the focused banner destination: {before_news} to {after_news}"
    )
    assert after_news["right"] <= 900, (
        f"version news left the focused banner destination clipped: {after_news}"
    )
    assert live_errors == []
    assert pinned_errors == []
    live.close()
    pinned.close()


def test_a_wide_banner_spends_status_copy_before_action_reach(
    browser, serve, other_leaf
):
    """At laptop width, status prose yields before the action shelf or its controls.

    The leaf mark still states status when its sentence ellipsizes. The complete real
    action set gets its intrinsic room first; if even that set outgrows the row, the shelf
    scrolls while each address keeps its words and the document keeps its width.
    """
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="claude")
    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    expect(page.locator(".lf-others")).to_be_visible()
    expect(page.locator(".lf-asks")).to_be_visible()
    expect(page.locator(".lf-answer-all")).to_be_visible()
    page.locator(".lf-status-text").evaluate(
        "el => { el.textContent = 'Claude is working — writing a deliberately long status sentence'; }"
    )
    layout = page.evaluate(
        """() => {
          const status = document.querySelector('.lf-status-text');
          const actions = document.querySelector('.lf-banner-actions');
          return {status: {shown: status.clientWidth, needed: status.scrollWidth},
                  actions: {shown: actions.clientWidth, needed: actions.scrollWidth}};
        }"""
    )
    assert layout["status"]["shown"] < layout["status"]["needed"], (
        f"the fixture put no pressure on the wide banner: {layout}"
    )
    assert layout["actions"]["shown"] == layout["actions"]["needed"], (
        f"the wide banner clipped actions before yielding status copy: {layout}"
    )

    # Make the same real action set ten pixels too wide for the remaining row: 28px of
    # banner padding, 24px of leaf mark and the 10px column gap leave the shelf 62px less
    # than the viewport. That is shelf overflow, not permission to compress a control or
    # widen the document. Derived from the live face so the contrast is the same on every
    # platform rather than depending on whether its font crosses 1200px by a few pixels.
    crowded_width = layout["actions"]["needed"] + 52
    resized(page, crowded_width, 900)
    crowded = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          return {
            actions: {shown: actions.clientWidth, needed: actions.scrollWidth},
            controls: [...actions.children]
              .filter(control => control.getClientRects().length)
              .map(control => ({name: control.textContent.trim(),
                                shown: control.clientWidth, needed: control.scrollWidth})),
            document: {shown: document.documentElement.clientWidth,
                       needed: document.documentElement.scrollWidth}
          };
        }"""
    )
    clipped = [
        control
        for control in crowded["controls"]
        if control["shown"] < control["needed"]
    ]
    assert crowded["actions"]["shown"] < crowded["actions"]["needed"], (
        f"the crowded fixture never overflowed its shelf at {crowded_width}px: {crowded}"
    )
    assert not clipped, f"the crowded shelf compressed its controls: {clipped}"
    assert crowded["document"]["shown"] == crowded["document"]["needed"], (
        f"the crowded shelf widened the document: {crowded}"
    )

    # The open panel and a version popup can overlap broadly. Once native focus leaves the
    # transient menu, it closes before painting over the next keyboard destination.
    page.locator(".lf-comments").click()
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
    page.locator(".lf-comments").click()
    panel_settled(page, open=False)
    assert errors == []
    page.close()

    # A pinned copy gains a real Latest destination after publication. Add the same class
    # of optional module-provided addresses exercised at the responsive boundary above,
    # then leave the final control only nine pixels beyond the shelf: the boundary at
    # which native focus scrolling is most likely to decide that nearly visible is enough.
    page, errors = open_page(browser, url, pin=True)
    resized(page, 1200, 900)
    (serve.page_dir / "versions" / "v2.html").write_text(html)
    stamp_version_file(serve.page_dir, 2, "two")
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    overflow = page.evaluate(
        """() => {
          const shelf = document.querySelector('.lf-banner-actions');
          const last = document.querySelector('.lf-others');
          for (let i = 0; i < 5; i++) {
            const button = document.createElement('button');
            button.className = 'lf-ui lf-btn';
            button.textContent = `Secondary destination ${i + 1}`;
            shelf.insertBefore(button, last);
          }
          const max = shelf.scrollWidth - shelf.clientWidth;
          shelf.scrollLeft = max - 9;
          return {max, at: shelf.scrollLeft};
        }"""
    )
    assert overflow["max"] > 9 and overflow["at"] == pytest.approx(
        overflow["max"] - 9, abs=0.5
    ), f"the partial-overflow fixture did not reach its boundary: {overflow}"
    ring_room = """el => {
      const shelf = el.parentElement.getBoundingClientRect();
      const button = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
      return {left: button.left - outset - shelf.left,
              right: shelf.right - button.right - outset,
              top: button.top - outset - shelf.top,
              bottom: shelf.bottom - button.bottom - outset};
    }"""
    last = page.locator(".lf-others")
    last.focus()
    room = last.evaluate(ring_room)
    assert all(space >= -0.01 for space in room.values()), (
        f"the partial wide shelf clipped its focused destination: {room}"
    )

    # A control that settles its own asks disappears while it still owns focus. Hand the
    # reader to the next standing destination instead of silently dropping them on body.
    answer_all = page.locator(".lf-answer-all")
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
    expect(answer_all).to_be_hidden()
    version = page.locator(".lf-version")
    expect(version).to_be_focused()
    room = version.evaluate(ring_room)
    assert all(space >= -0.01 for space in room.values()), (
        f"the focus transfer landed under the shelf edge: {room}"
    )
    assert errors == []
    page.close()


def test_the_keyboard_reference_is_a_modal_tab_loop_and_returns_to_its_door(
    browser, serve
):
    """A dialog-shaped shortcut reference behaves like a dialog for the native Tab walk."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    door = page.locator(".lf-comments")
    door.focus()
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
    half = page.evaluate(
        "() => (document.body.clientHeight"
        " - parseFloat(getComputedStyle(document.body).scrollPaddingTop)) / 2"
    )
    page.evaluate("() => document.body.scrollTo({top: 0, behavior: 'instant'})")
    page.keyboard.press("d")
    assert page.evaluate("() => document.body.scrollTop") == pytest.approx(
        half, abs=1
    ), "the navigation factory kept its load-time motion preference"

    page.emulate_media(reduced_motion="no-preference")
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.evaluate(
        """() => {
          window.__lfFrames = [];
          window.requestAnimationFrame = callback =>
            (window.__lfFrames.push(callback), window.__lfFrames.length);
          window.cancelAnimationFrame = () => {};
          document.body.scrollTo({top: 0, behavior: 'instant'});
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
    assert page.evaluate("() => document.body.scrollTop") == pytest.approx(
        half, abs=1
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

        primary = page.locator(".lf-comments, .lf-signoff")
        expect(primary).to_have_count(2)
        for index in range(primary.count()):
            box = primary.nth(index).bounding_box()
            assert box["height"] >= 43.9, f"a primary touch aim stayed at {box}"

        page.locator(".lf-comments").tap()
        panel_settled(page)
        compact = page.locator(
            ".lf-panel .lf-react:visible, .lf-panel-head .lf-btn:visible, "
            ".lf-key-more:visible"
        )
        assert compact.count() >= 2, (
            "the covering panel exposed no compact touch controls"
        )
        for index in range(compact.count()):
            box = compact.nth(index).bounding_box()
            assert box["width"] >= 43.9 and box["height"] >= 43.9, (
                f"a compact panel control kept a mouse-sized aim: {box}"
            )
        page.locator(".lf-comments").tap()
        panel_settled(page, open=False)

        # Across the covering boundary the banner fits the same touch aims. Its shelf and
        # a keyboard ring remain inside the derived edge rather than centred through it.
        for width in (840, 841, 900, 1200, 1440):
            resized(page, width, 844)
            page.locator(".lf-comments").focus()
            geometry = page.locator(".lf-comments").evaluate(
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

        # Body is Leaf's durable page scroller. Touch beginning in fixed chrome needs an
        # explicit vertical bridge to it, while a horizontal shelf gesture stays native.
        cdp = context.new_cdp_session(page)
        resized(page, 390, 700)
        page.wait_for_function(
            "() => getComputedStyle(document.body).overflowY !== 'hidden'"
        )
        actions = page.locator(".lf-banner-actions")
        page.evaluate(
            """() => {
              const actions = document.querySelector('.lf-banner-actions');
              for (let i = 0; i < 3; i++) {
                const button = document.createElement('button');
                button.className = 'lf-ui lf-btn';
                button.textContent = `Secondary touch destination ${i + 1}`;
                actions.append(button);
              }
            }"""
        )
        assert actions.evaluate("el => el.scrollWidth > el.clientWidth")
        point = actions.bounding_box()
        x = point["x"] + point["width"] / 2
        y = point["y"] + point["height"] / 2
        page.evaluate(
            "() => { const shelf = document.querySelector('.lf-banner-actions');"
            " shelf.scrollLeft = 0; document.body.scrollTop = 200; }"
        )
        _touch_drag(cdp, x, y, dy=-160)
        page.wait_for_function("() => document.body.scrollTop > 200")
        vertical = page.evaluate(
            "() => ({shelf: document.querySelector('.lf-banner-actions').scrollLeft,"
            " page: document.body.scrollTop,"
            " overflow: getComputedStyle(document.body).overflowY})"
        )
        assert (
            vertical["shelf"] == 0
            and vertical["page"] > 200
            and vertical["overflow"] != "hidden"
        ), f"a vertical touch over the shelf never reached the page: {vertical}"
        page.evaluate(
            "() => { const shelf = document.querySelector('.lf-banner-actions');"
            " shelf.scrollLeft = 0; document.body.scrollTop = 200; }"
        )
        _touch_drag(cdp, x, y, dx=-160)
        page.wait_for_function(
            "() => document.querySelector('.lf-banner-actions').scrollLeft > 0"
        )
        horizontal = page.evaluate(
            "() => ({shelf: document.querySelector('.lf-banner-actions').scrollLeft,"
            " page: document.body.scrollTop})"
        )
        assert horizontal["shelf"] > 0 and horizontal["page"] == 200, (
            f"the touch shelf lost its native horizontal pan: {horizontal}"
        )

        resized(page, 1200, 700)
        status = page.locator(".lf-banner-status").bounding_box()
        page.evaluate("() => { document.body.scrollTop = 200; }")
        _touch_drag(
            cdp,
            status["x"] + status["width"] / 2,
            status["y"] + status["height"] / 2,
            dy=-160,
        )
        page.wait_for_function("() => document.body.scrollTop > 200")
        assert page.evaluate("() => document.body.scrollTop") > 200, (
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
            browser, serve(MANY_ASKS_PAGE, comments=12), context=context
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
        page.locator(".lf-comments").click()
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
        swipe(12, 280)
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
        page.locator(".lf-asks").click()
        panel_settled(page, open=False)
        expect(page.locator(".lf-asks-panel")).to_have_class(re.compile(r"\bopen\b"))
        page_at_rest(page)
        narrow_asks = edge_geometry(".lf-asks-panel", ".lf-asks-panel > .lf-edge")
        assert not narrow_asks["edge"]["hidden"]
        assert narrow_asks["edge"]["left"] >= -0.1, narrow_asks
        assert narrow_asks["edge"]["right"] <= narrow_asks["viewport"] + 0.1, (
            narrow_asks
        )

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
                ".lf-comments",
                ".lf-panel",
                ".lf-panel > .lf-edge",
                ".lf-threads",
                48,
            ),
            (
                "asks",
                900,
                ".lf-asks",
                ".lf-asks-panel",
                ".lf-asks-panel > .lf-edge",
                ".lf-asks-panel .lf-tray-list",
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
        page.locator(".lf-comments").click()
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
    page, errors = open_page(browser, serve(CONTROL_STABILITY_PAGE))
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


def test_the_composed_gallery_declares_every_control_row_archetype(browser, serve):
    """The gallery keeps the declaration open to control mechanisms added later."""
    gallery = next(example for example in EXAMPLES if example.stem == "gallery")
    page, errors = open_page(browser, serve(gallery))
    page_at_rest(page)
    page.evaluate(DEFINE_BOXES)
    observed = set()
    undeclared = []
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
            undeclared.append(f"{label}: {matches or 'no archetype'}")
        observed.update(matches)

    assert not undeclared, (
        "controls with neighbours need one archetype:\n  " + "\n  ".join(undeclared)
    )
    expected = {archetype["name"] for archetype in CONTROL_ARCHETYPES}
    assert observed == expected, (
        f"gallery reached {sorted(observed)}, expected {sorted(expected)}"
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
            '<h1 id="heading">Choose</h1><lf-options id="pick" choose>'
            '<lf-option id="pick-a">A</lf-option>'
            '<lf-option id="pick-b">B</lf-option></lf-options>',
        )
    )
    page, errors = open_page(browser, url)

    page.get_by_role("checkbox", name=re.compile(r"^choose one: A")).click()
    round_trip(page)

    expect(page.locator("#pick-a")).to_have_attribute("chosen", "")
    assert [event["action"] for event in actions(serve.page_dir)] == ["choose"]
    assert errors == []
    page.close()


def test_a_seat_conversation_leaves_the_pick_it_is_about_live(
    browser, serve, tmp_path, monkeypatch
):
    """The reader's own remark must not lock the control it is a remark about.

    A conversation standing in the group's seat takes the request off the reader's
    list — the banner stops counting it — but answers nothing, so the pick that
    would answer it is still live. This is the browser half of the split, and the
    half the reader meets first: the POST door only sees a hand-posted event, while
    here `actionAvailable` paints the control and `sendAction` guards the press, and
    `lf-options` has already painted the pick by the time either runs. Reading the
    reader's list at this door therefore does not refuse the press so much as
    swallow it — the option flips, nothing is logged, no toast fires, and the next
    poll puts it back with nothing anywhere saying why."""
    monkeypatch.chdir(tmp_path)
    overlay = tmp_path / ".leaf"
    overlay.mkdir()
    standard = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())
    options = standard["lf-options"]
    options["x-state"]["choose"]["requires"] = {"target": "self", "awaiting": True}
    (overlay / "registry.json").write_text(json.dumps({"lf-options": options}))
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-options id="pick" choose>'
            '<lf-option id="pick-a">A</lf-option>'
            '<lf-option id="pick-b">B</lf-option></lf-options>',
        )
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
    expect(page.locator(".lf-asks")).to_have_text("Asks (0)")

    page.get_by_role("checkbox", name=re.compile(r"^choose one: A")).click()
    round_trip(page)

    expect(page.locator("#pick-a")).to_have_attribute("chosen", "")
    # The log is what holds this, and the attribute above cannot: the module paints
    # the pick before either guard runs, so with the wrong reading at this door the
    # option wears `chosen` exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["choose"]
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
    *left*; everything to its right keeps its place. So `Comments (9)` becoming
    `Comments (10)` — a comment posted from the terminal while the user reads —
    slid the version chooser 6px left, and the ✓ Accept all a second tab's decision puts
    away took the New-version chip with it.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so the ✓ Accept all count has somewhere to go before it
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
    comments = ".lf-banner .lf-comments"
    accept_all = '.lf-banner [title^="Accept every"]'
    page.wait_for_function(
        f"() => document.querySelector('{comments}').textContent === 'Comments (9)'"
    )
    page_at_rest(page)

    def publish_v2():
        (d / "versions" / "v2.html").write_text(html)
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
            f"() => document.querySelector('{comments}').textContent === 'Comments (10)'",
        ),
        (
            "a new version is published",
            publish_v2,
            (
                "() => document.querySelector('.lf-latest-chip')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            (
                f"() => document.querySelector('{accept_all}')"
                ".textContent === '\\u2713 Accept all (1)'"
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
    # stays legible and the action shelf owns the overflow, instead of collapsing one
    # control into a padding-width box containing none of its words.
    holds_its_width = (
        "() => ['.lf-latest-chip', '.lf-version', '.lf-comments', '.lf-signoff', "
        "       '.lf-answer-all', '.lf-asks']"
        ".map((s) => document.querySelector('.lf-banner ' + s).offsetWidth)"
    )
    wide = page.evaluate(holds_its_width)
    resized(page, 900, 900)
    # Out of room, witnessed independently of the controls whose widths are the subject.
    page.wait_for_function(
        "() => { const actions = document.querySelector('.lf-banner-actions');"
        "        return actions.scrollWidth > actions.clientWidth; }"
    )
    assert page.evaluate(holds_its_width) == wide, (
        "a banner with no room left took it out of a control instead of giving the "
        "overflow to its action shelf"
    )
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
    # carried, rather than being redirected onto one immutable version.
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
    of it. On a desk, All leaves begins the action row beside the left tray and Comments
    ends it beside the right panel. A phone keeps the primary Comments loop first, where
    it is initially reachable, and the DOM itself changes order so the keyboard follows
    the visible route. Crossing that boundary does not throw away the control in focus."""
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
                  ['asks', 'lf-asks'], ['version', 'lf-version'],
                  ['comments', 'lf-comments'], ['signoff', 'lf-signoff']]
                   .find(([, cls]) => el.classList.contains(cls))?.[0])
                 .filter(Boolean)"""
        )

    wide = actions()
    assert wide == ["others", "latest", "asks", "version", "signoff", "comments"]
    others_x = page.locator(".lf-others").bounding_box()["x"]
    comments = page.locator(".lf-comments").bounding_box()
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
    assert page.evaluate(
        "document.activeElement === document.querySelector('.lf-version')"
    )
    covering = actions()
    assert covering == ["comments", "signoff", "latest", "asks", "version", "others"]

    page.locator(".lf-others").focus()
    resized(page, 1200, 900)
    assert page.evaluate(
        "document.activeElement === document.querySelector('.lf-others')"
    )
    assert actions() == [
        "others",
        "latest",
        "asks",
        "version",
        "signoff",
        "comments",
    ]
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
    page.keyboard.press("l")
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
        # page to go to: the row that says a page needs them carries the ask, the way
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
    record_claim(other_dir, pid=dead_pid)
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
    page.keyboard.press("l")
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
    page.keyboard.press("l")
    expect(page.locator(".lf-others-panel")).to_be_focused()
    expect(page.locator(".lf-keyline")).not_to_contain_text("walk the leaves")
    assert page.locator(".lf-others-panel").get_attribute("aria-keyshortcuts") is None
    # Nothing live left to open: the button stands while the panel does and stands
    # down with it, which is the count's other half.
    page.keyboard.press("Escape")
    told(page)
    expect(btn).not_to_be_visible()
    assert errors == []
    page.close()


def test_the_leaves_tray_takes_the_keyboard(browser, serve, live_leaf):
    """The tray is a list, and a reader walks it without reaching for the mouse: g l
    opens it and lands on the first neighbour, up and down step between them and clamp
    at the ends, Enter opens the focused one in its own tab, and Esc hands focus back
    to the button that opened it. The go-to menu names the panel, and the key line names
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
    page.keyboard.press("l")
    rows = page.locator("a.lf-others-row")
    # Titles order the tray, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-others-title")).to_have_text("A second leaf")
    expect(rows.first).to_be_focused()
    expect(keyline).to_contain_text("walk the leaves")
    expect(keyline).to_contain_text("open it in a tab")
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
    # Closing while focus is inside would drop the reader on the body; it lands on
    # the one control that reopens what just closed.
    expect(btn).to_be_focused()
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_contain_text("In the leaves tray")
    expect(help_el).to_contain_text("Previous leaf")
    expect(help_el).to_contain_text("Next leaf")
    assert errors == []
    page.close()


def test_a_page_nobody_has_touched_scrolls_from_the_keyboard(browser, serve):
    """`html` is `overflow: hidden` here so the document scrolls in `body`, and the
    browser scrolls whichever box it last saw the reader put themselves in. On a fresh
    load that is none of them, so Space, PageDown and the arrows did nothing whatever
    until the reader happened to click somewhere in the page — while the runtime's own
    d and u worked from the first frame, which is what kept it hidden: the keys leaf
    names were live and the keys every reader already knows were dead, which reads as a
    page that has no keyboard scrolling rather than as a page with a bug.

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
        page.evaluate("() => { document.body.scrollTop = 0; }")
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

    The scroll is what the rung has to hand back, and handing it back means naming a
    box again: the document scrolls in `body` rather than in the viewport here, so the
    browser needs to have seen the reader put themselves somewhere. A blur names
    nowhere, and from `document.activeElement` the two are the same answer. The page
    names one at load, which is the test above, and this one is about losing it to the
    chrome and getting it back."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    toggle = page.locator(".lf-comments")
    panel = page.locator(".lf-panel")
    ringed = "() => document.querySelector('.lf-comments').matches(':focus-visible')"
    top = "() => document.body.scrollTop"

    # A reader reading: Space is the page's own scroll, which is the browser's rather
    # than the runtime's (`d`/`u` are the rows; this key has none).
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
    expect(panel).to_be_hidden()
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
    page.wait_for_function("(was) => document.body.scrollTop > was", arg=was)
    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [500, 1200])
def test_workspaces_replace_each_other_instead_of_stacking(browser, serve, width):
    """Comments and trays are alternate workspaces at every width."""
    page, errors = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, width, 700)
    asks = page.locator(".lf-asks-panel")
    comments = page.locator(".lf-panel")

    page.locator(".lf-asks").click()
    expect(asks).to_have_class(re.compile(r"\bopen\b"))
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(asks).not_to_have_class(re.compile(r"\bopen\b"))

    page.locator(".lf-asks").click()
    panel_settled(page, open=False)
    expect(asks).to_have_class(re.compile(r"\bopen\b"))
    expect(comments).not_to_have_class(re.compile(r"\bopen\b"))
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
    page.keyboard.press("l")
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


def test_a_walk_down_the_asks_tray_stops_clear_of_the_key_line(browser, serve):
    """The leaves tray's reading above, made of the tray beside it. The room is one
    fact — the key line stands in the corner both lists reach — and it was written to one
    list, so the asks tray's walk parked its last row 47px under the line. Nothing said
    so, because no example ships enough asks to fill a tray and the walk that would have
    shown it had only ever been made down the other one.

    So the two lists reserve it together (`trayLists`), and this is the half of that the
    leaves reading could not cover: a fact stated per tray is a fact the second tray
    goes without, and the second tray is the one nobody looks at."""
    page, errors = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, 900, 420)
    page.locator(".lf-asks").click()
    rows = page.locator("button.lf-asks-row")
    expect(rows).to_have_count(12)
    rows.first.focus()
    for _ in range(12):
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    tray = page.locator(".lf-asks-panel .lf-tray-list")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-asks-panel .lf-tray-list');"
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
    page.locator(".lf-comments").click()
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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_examples_have_no_serious_wcag_a_or_aa_violations(browser, serve, example):
    """Axe covers semantic failures the render gate cannot see: an unnamed control,
    an invalid role relationship, or a contrast failure can occupy a perfectly good
    box and still shut a user out. Keep the scope to WCAG A/AA and actionable
    serious/critical findings; layout and accessibility-tree snapshots belong to
    specific regressions, not a corpus baseline that changes with every restyle.

    A phone's width because what a box does there is a different question and not a
    smaller one: the column is 372px, so a block that had room at a desk starts
    scrolling, and a scrolling box with no way into it from the keyboard is a user
    reading half of every line of code. Nothing at 1200 says a word about it."""
    url = serve(example)
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
    shut: it never presses a key, so the comment panel, its box, the trays, the versions
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

    # The panel, and then its list — which is where `c` lands the reader, and the box it
    # used to land in is one press further in.
    page.keyboard.press("c")
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
    page.keyboard.press("l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile("open"))
    sweep("standing in the leaves tray")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile("open"))

    # The versions menu, whose way out this branch made live on a first version.
    page.keyboard.press("v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    sweep("in the versions menu")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-version-menu")).not_to_be_visible()

    # The keyboard reference, which is a dialog and owes the most of any of them.
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
    """The document scrolls its own column, not the viewport. If it scrolled the
    viewport, its scrollbar would be drawn at the window's right edge — over the
    panel, in the same pixels as the thread list's own — and the two thumbs would
    stack. The regions must not share an edge."""
    page, _ = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-comments").click()
    panel_settled(page)

    geom = page.evaluate("""() => {
        const box = el => el.getBoundingClientRect();
        const body = document.body, threads = document.querySelector('.lf-threads');
        return { viewportScrolls: document.documentElement.scrollHeight > document.documentElement.clientHeight,
                 bodyScrolls: body.scrollHeight > body.clientHeight,
                 threadsScroll: threads.scrollHeight > threads.clientHeight,
                 bodyRight: box(body).right, threadsLeft: box(threads).left };
    }""")

    assert not geom["viewportScrolls"], (
        "the viewport is scrolling the document, so its scrollbar is drawn at the "
        "window's right edge — on top of the panel"
    )
    assert geom["bodyScrolls"] and geom["threadsScroll"], (
        "both regions must overflow for this test to mean anything"
    )
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
    page.wait_for_function("() => document.body.scrollTop > 0")
    before = page.evaluate("() => document.body.scrollTop")

    page.locator(".lf-comments").click()
    panel_settled(page)

    # One wheel over the page's visible sliver, one over the sheet. Waiting on the
    # second proves both were processed — input stays in order — so the first
    # having moved nothing is a real outcome rather than a race.
    page.mouse.move(60, 300)
    page.mouse.wheel(0, 400)
    page.mouse.move(400, 300)
    page.mouse.wheel(0, 400)
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert page.evaluate("() => document.body.scrollTop") == before, (
        "the page scrolled behind the covering sheet"
    )

    # Navigation closes the covering workspace before it positions the page. Doing the
    # same scroll behind the lock produces the right numbers and the wrong product: the
    # promised passage remains invisible.
    page.locator(".lf-quote", has_text="Paragraph 40").click()
    panel_settled(page, open=False)
    # Arrived where it was aimed, which is the only thing about this the page states. The
    # click scrolls twice — instantly, to bring the passage's own box into view, then
    # smoothly to centre the painted range — and the browser fires a scrollend for each,
    # so the first statement it makes comes 232px short of the rest position. "On screen"
    # is true there too, and so is stillness sampled between the two, which reads exactly
    # as it does after both (tests/CLAUDE.md, "A wait consumes a fact the system states");
    # the hold that used to cover the gap was a duration guessed at. Centring is what the
    # runtime aimed for, so the mark reaching the middle is arrival, and a glide that
    # approaches it passes through no earlier position that could be taken for one.
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return Math.abs(m.top + m.height / 2 - innerHeight / 2) < 1; }"""
    )
    at_mark = page.evaluate("() => document.body.scrollTop")
    assert at_mark != before

    # Scrolling belongs to the visible page again immediately after that navigation.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.body.scrollTop > {at_mark}")

    # The resize path: narrowing onto an open panel locks, widening unlocks.
    page.locator(".lf-comments").click()
    panel_settled(page)
    resized(page, 1000, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.body).overflowY !== 'hidden' && getComputedStyle(document.body).marginRight !== '0px'"
    )
    resized(page, 500, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.body).overflowY === 'hidden' && getComputedStyle(document.body).marginRight === '0px'"
    )
    page.close()


def test_covering_panel_keeps_toasts_on_screen_and_clear_of_the_footer(browser, serve):
    """A covering panel has no beside-panel space for a toast: on a viewport no
    wider than the sheet, the wide layout's panel-width offset puts the whole
    message past the left edge. The toast stays inside that sheet instead, above
    its persistent composer even when that composer grows under a live toast,
    then returns beside it at the first width where the panel stops covering."""
    page, _ = open_page(browser, serve(LONG_PAGE))
    resized(page, 320, 600)
    page.locator(".lf-comments").click()
    page.locator(".lf-general textarea").fill("The unsent comment stays here.")

    message = (
        "Couldn't send this detailed comment to Claude — the complete draft "
        "is still here and ready to retry."
    )
    page.evaluate(
        """async message => {
            const {toast} = await import("/runtime/widget-api.js");
            toast(message);
        }""",
        message,
    )
    expect(page.locator(".lf-toast")).to_have_text(message)

    def geometry():
        return page.evaluate("""() => {
            const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {left: r.left, top: r.top, right: r.right, bottom: r.bottom};
            };
            return {
                width: innerWidth,
                height: innerHeight,
                panel: rect(".lf-panel"),
                footer: rect(".lf-general"),
                toast: rect(".lf-toast"),
            };
        }""")

    narrow = geometry()
    assert (
        narrow["toast"]["left"] >= 17
        and narrow["toast"]["right"] <= narrow["width"] - 17
    ), f"the toast left the covering viewport: {narrow}"
    assert narrow["toast"]["bottom"] <= narrow["footer"]["top"] - 17, (
        f"the toast covered the panel's persistent composer: {narrow}"
    )

    resized(page, 841, 600)
    page.wait_for_function("""() => {
        const toast = document.querySelector(".lf-toast").getBoundingClientRect();
        const panel = document.querySelector(".lf-panel").getBoundingClientRect();
        return Math.abs(toast.right - (panel.left - 18)) < 1
            && Math.abs(toast.bottom - (innerHeight - 18)) < 1;
    }""")

    wide = geometry()
    assert wide["toast"]["left"] >= 0, (
        f"the long toast left the viewport beside the wide panel: {wide}"
    )
    assert abs(wide["toast"]["right"] - (wide["panel"]["left"] - 18)) < 1, (
        f"the wide toast no longer sits beside the panel: {wide}"
    )
    assert abs(wide["toast"]["bottom"] - (wide["height"] - 18)) < 1, (
        f"the wide toast no longer sits in its original bottom corner: {wide}"
    )

    resized(page, 320, 600)
    page.wait_for_function("""() => {
        const toast = document.querySelector(".lf-toast").getBoundingClientRect();
        const footer = document.querySelector(".lf-general").getBoundingClientRect();
        return toast.left >= 17 && toast.right <= innerWidth - 17
            && toast.bottom <= footer.top - 17;
    }""")
    before_growth = geometry()
    page.locator(".lf-general textarea").fill(
        "The whole unsent comment stays here.\n" * 4
    )
    page.wait_for_function(
        """beforeTop => {
            const toast = document.querySelector(".lf-toast").getBoundingClientRect();
            const footer = document.querySelector(".lf-general").getBoundingClientRect();
            return footer.top < beforeTop - 1
                && toast.bottom <= footer.top - 17;
        }""",
        arg=before_growth["footer"]["top"],
    )
    expanded = geometry()
    assert expanded["footer"]["top"] < before_growth["footer"]["top"] - 1, (
        f"the composer did not grow under the already-visible toast: "
        f"{before_growth=}, {expanded=}"
    )
    assert expanded["toast"]["bottom"] <= expanded["footer"]["top"] - 17, (
        f"the growing composer rose through an already-visible toast: {expanded}"
    )
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
    page.locator(".lf-comments").click()
    panel_settled(page)
    page.evaluate(
        """async () => {
          const {toast} = await import('/runtime/widget-api.js');
          toast('Inset proof');
        }"""
    )
    expect(page.locator(".lf-keyline")).to_be_visible()
    page.wait_for_function(
        """insets => Math.abs(
          document.querySelector('.lf-toast').getBoundingClientRect().right
          - (innerWidth - 18 - insets.right)
        ) < 1""",
        arg=insets,
    )
    boxes = page.evaluate(
        """() => {
          const rect = selector => {
            const r = document.querySelector(selector).getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
          };
              return {toast: rect('.lf-toast'), keyline: rect('.lf-keyline'),
                      footer: rect('.lf-general'), width: innerWidth, height: innerHeight,
                      toastRight: getComputedStyle(document.querySelector('.lf-toast')).right};
        }"""
    )
    assert abs(boxes["toast"]["right"] - (boxes["width"] - 18 - insets["right"])) < 1, (
        boxes
    )
    footer_height = boxes["footer"]["bottom"] - boxes["footer"]["top"]
    assert (
        abs(
            boxes["toast"]["bottom"]
            - (boxes["height"] - footer_height - 18 - insets["bottom"])
        )
        < 1
    )
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
    page.locator(".lf-comments").click()
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
        '<lf-options id="quota-intervention" choose label="Proceed?">'
        '<lf-option id="quota-ready" chosen>Ready</lf-option></lf-options>'
        '<lf-task id="child" status="active"><strong>Child</strong></lf-task>'
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
    # The answered direct intervention takes precedence over the nested task, so
    # changing the child alone does not close capacity.
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
    current.locator("#quota-ready").click()
    round_trip(current)
    expect(current.locator("#quota-ready")).not_to_have_attribute("chosen", "")
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
    (serve.page_dir / "versions" / "v2.html").write_text(quota_v2)
    stamp_version_file(serve.page_dir, 2, "same plan")
    told(current)
    expect(current.locator(".lf-version")).to_contain_text("v2")
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
    url = serve(example.read_text(), comments=2)
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
    url = serve(example.read_text(), comments=2)
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
    page.locator(".lf-comments").click()
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
        page.locator(".lf-comments").click()
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
    page.locator(".lf-comments").click()
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
    ("the page", (), ("gallery", "design-decision", "ship-review")),
    ("the comments", ("c",), ("ship-review",)),
    ("the asks tray", (), ("ship-review",)),
    ("the leaves tray", ("g", "l"), ("gallery",)),
    # The menu's own walk after the key that opens it: an open lands on the version being
    # read, which is the last row, and the comparison press beside a row is a Tab forward
    # from the row above it. The walk is clamped, so a second press at the top moves
    # nothing and the pair covers a menu of any length this corpus can hold.
    ("the versions menu", ("v", "ArrowUp", "ArrowUp"), ("gallery",)),
    ("the reference", ("?",), ("gallery",)),
    ("design mode", ("i",), ("gallery",)),
)
# The gallery is the open-ended page and design-mode anchor: every authored widget family
# joins it. Design decision contributes settled and joined options plus a glossary mark.
# Ship review contributes the panel's log-hosted widgets, element mark and run-heading
# mark, and therefore carries the shared comments and asks chrome. The remaining chrome
# has no page-owned contents and is walked once on the gallery.
RING_WALK_EXAMPLES = tuple(
    dict.fromkeys(name for _scope, _keys, corpus in RING_WALKS for name in corpus)
)
# What each scope has to have opened before its walk means anything, and what the page
# shows while its entry is available. A control with nothing to show is absent by
# declaration — Asks on a page waiting on nobody, `l` where the machine has one leaf — so
# the surface is asked for only where the page is offering it, and the corpus answers for
# the rest. Without this a key that stops working leaves the walk re-walking the page and
# contributing nothing, which the coverage floor catches only where that scope is a
# rule's sole home: one guard over seven setup steps. The page and the comments raise no
# surface of their own; `c` and `g c` land on the list, which the walk's own first stop
# reads.
RING_SCOPE_SURFACE = {
    "the asks tray": (".lf-asks-panel.open", ".lf-asks"),
    "the leaves tray": (".lf-others-panel.open", ".lf-others"),
    "the versions menu": (".lf-version-menu.open", None),
    "the reference": (".lf-help.open", None),
    "design mode": ("body.lf-design", None),
}
RING_SCOPE_CONTROL = {"the asks tray": (".lf-asks", ".lf-asks-row")}
# Focus put back at the document's start. `document.body.focus()` and not a blur: a blur
# leaves the sequential focus navigation starting point where the blurred control stood,
# so the next Tab carries on from the chrome, runs off the end of the order and never
# enters the page. Twelve stops instead of thirty-three, with every ring the page's own
# widgets draw unread and the walk reporting itself complete.
RING_WALK_START = "() => document.body.focus()"
# A new stop, read on a rendered frame. Held by identity, since two buttons in a row can
# say the same words at the same scroll and are still two stops.
RING_NEW_STOP = f"""async () => {{
  await ({RENDERED})();
  const e = ({DEEP_FOCUS})();
  if (!e || e === document.body || e === document.documentElement) return false;
  if (window.__lfSeen.has(e)) return false;
  window.__lfSeen.add(e);
  return true;
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
            "() => Boolean(document.activeElement?.matches('.lf-comments'))"
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
          '.lf-comments:focus-visible { outline: none !important;'
          + ' box-shadow: none !important; }';
        document.head.append(style);
    }""")
    page.evaluate(RENDERED)
    lost = page.evaluate(SEEN_STOP)
    assert lost and "lf-comments" in lost, (
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
    reason `page catalog` reads the merged registry: a twelfth widget must not need a
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
        page.locator(".lf-comments").click()
        panel_settled(page)
        # Opened, not pressed for a decision: a settled group's disclosure is this
        # reader's view state and no version carries it. One in an exhibit is quoted,
        # so its marks are spans with nothing to focus, and one in a shut panel has no
        # box — neither is a place a ring can be drawn, and neither can be clicked.
        for row in page.locator("lf-options[settled] > .lf-settled").all():
            if row.is_visible():
                row.click()
        page_at_rest(page)

        for scope, keys, corpus in RING_WALKS:
            if name not in corpus:
                continue
            # Three rungs, because a scope can be three deep: a tray, menu, or narrowing
            # over the panel, then the panel, then the page. The panel is reopened below,
            # so every scope starts from the same page.
            for _ in range(3):
                page.keyboard.press("Escape")
            # A draft editor is conditional chrome: Tab can stand on it only after its
            # explicit Edit door has opened it. Open one after the scope reset, which
            # would otherwise close it with its first Escape, so the page walk proves
            # the inset editor ring the way a reader actually reaches it.
            if scope == "the page":
                pencil = page.locator("lf-draft .lf-draft-pencil").first
                if pencil.count() and pencil.is_visible():
                    pencil.click()
            page.evaluate(RING_WALK_START)
            if not page.locator(".lf-panel.open").count():
                page.locator(".lf-comments").click()
                panel_settled(page)
                page.evaluate(RING_WALK_START)
            if control := RING_SCOPE_CONTROL.get(scope):
                opener, arrival = control
                page.locator(opener).click()
                page.locator(arrival).first.focus()
            else:
                for key in keys:
                    page.keyboard.press(key)
            page_at_rest(page)
            surface, offers = RING_SCOPE_SURFACE.get(scope, (None, None))
            if surface and (offers is None or page.locator(offers).is_visible()):
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
                    page.keyboard.press("Tab")
                if not page.evaluate(RING_NEW_STOP):
                    # The key that opened the scope may have landed focus on nothing, so
                    # the first read is allowed to come back empty; a repeat after the
                    # walk has started is the order having come round. Two, not the cap:
                    # a walk that never starts otherwise spends four hundred frames
                    # saying so and reads as a slow test rather than a broken one.
                    empty += 1
                    if walked or empty > 2:
                        came_round = True
                        break
                    continue
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
                # something the walk is not moving — an ask's mark, a thread's element
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
