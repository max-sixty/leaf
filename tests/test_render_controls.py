"""Control stability, aiming, design mode, and shell tests."""

import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import INTERACT_SCRIPT
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import registry as registry_model
from leaf import render_checks as render_checks_model
from leaf import rendering as rendering_model
from leaf import schema as schema_model
from leaf import validation as validation_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    AIM_CURSOR,
    AIM_PAINT_PAGE,
    AIM_POINT,
    AIM_SEAM,
    AIM_SEAM_PAGE,
    AIMED,
    BADGE_CHROME,
    BANNER_WATCH,
    BOTH_STAMPS,
    CARRIED_PAGE,
    COMMAND_HUB_PACKAGE,
    CORNER_PAGE,
    DEEP_FOCUS,
    DEFINE_BOXES,
    DIFF_PAGE,
    DRAFT_MARK,
    EDGES,
    EXAMPLE_MEDIA,
    EXAMPLES,
    FOCUS_IN_PAGE,
    INLINE_PAGE,
    LEGEND_TRUE,
    LONG_PAGE,
    MANY_ASKS_PAGE,
    NAMED,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    PAGE_MARKUP,
    PAINTED_IN_SILENCE_PAGE,
    PANEL_DIFF_MARKUP,
    PART_DIAGRAM_PAGE,
    PART_DIAGRAM_V2,
    PICTURE_PAGE,
    PRESS,
    PRINT_LOSS_PAGE,
    RENDERED,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    RING_NAMES,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SCROLLED,
    SETTLED_PAGE,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    SPECIMEN_MARKUP,
    SPECIMEN_PAGE,
    SPECIMEN_TEXT,
    SUGGESTION_PAGE,
    TOKEN,
    UNBREAKABLE_PAGE,
    UNPARSABLE_DIAGRAM,
    WIDE_DIFF_PAGE,
    CutOff,
    _publish,
    _traffic,
    _until,
    actions,
    aim_targets,
    author_test_widget,
    displaced,
    draw_edge,
    flip_point,
    geometry,
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
    panel_settled,
    primed,
    record_claim,
    resized,
    ring_faults,
    rings_drawn,
    round_trip,
    select,
    serious_axe_violations,
    shown_frames,
    solid_png,
    stamp_version_file,
    standing_ring,
    token_colour,
    told,
    watched,
)

pytestmark = pytest.mark.nightly


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
    """A page that only informs offers Comments without a terminal action.

    The slot the approve button takes on a sign-off page stays empty here rather than
    picking up a neutral control, which is the fact a reader can see: an informational
    page asks them for nothing, so it hands them nothing to press.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The banner is built in one pass, so a control standing in it is what makes the
    # absence beside it worth reading rather than a row that never rendered.
    expect(page.locator(".lf-comments")).to_be_visible()
    assert page.locator(".lf-signoff").count() == 0
    # Approval takes the slot beside Comments where a page asks for one, so the absence
    # above is the whole fact: the row is a control short rather than a control longer.
    assert errors == []
    page.close()


def test_a_covering_view_keeps_the_page_status_and_primary_actions_in_reach(
    browser, serve
):
    """The responsive shelf keeps the page's state, Comments, and approval visible.

    A covering viewport is not a cropped desktop toolbar. The secondary destinations may
    live in a horizontally scrollable row, but the two actions that complete the reading
    loop must be in the first view from a 320px phone through a small tablet, and the
    document itself must never become the scroller for that row.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page, errors = open_page(browser, url)

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
    page.keyboard.press("Tab")
    expect(page.locator(".lf-signoff")).to_be_focused()
    assert actions.evaluate("el => el.scrollLeft") == 0

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
    assert errors == []
    page.close()

    # A pinned wide page reserves the Latest chip before it first has news, but the same
    # invisible slot on a phone would be a blank stretch of the horizontal shelf. The next
    # real destination peeking into view is both the collapse witness and the overflow cue.
    page, errors = open_page(browser, url, pin=True)
    resized(page, 320, 844)
    expect(page.locator(".lf-latest-chip")).to_be_hidden()
    assert page.locator(".lf-latest-chip").evaluate("el => el.offsetWidth") == 0
    version = page.locator(".lf-version").evaluate(
        "el => { const r = el.getBoundingClientRect(); return {left: r.left, right: r.right}; }"
    )
    assert 0 < version["left"] < 320 < version["right"], (
        f"the next phone destination did not peek past the primary actions: {version}"
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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_a_press_leaves_its_neighbours_where_they_were(browser, serve, example):
    """A press may change the page; it may not move the controls next to the one pressed.

    A user works by pointing, and the line a control stands on is where their next
    gesture is already aimed. What a press changes below it is content — a tab shows a
    different panel, a fold opens, a suggestion resolves, and the page under it moves
    because the user asked it to. What must not move is the row itself, because
    nothing was asked of it and it is the one thing the user is still using.

    Three shipped controls broke this rule, each by changing a metric to say something:
    a selected tab set in 600 weight, since a bolder label is a wider one, so the strip
    reshuffled under the pointer that had just pressed it; the sign-off button, whose
    "✓ Version approved" is narrower than "Approve version", sliding the version
    chooser and the Comments button right; and a row-form pick mark, which took the room
    for the word it says on being pressed and dragged that row's § reference 54px left. None of
    them shows in a screenshot of either state, because every strip and every row lays
    out perfectly well on its own; it is the two states together that say anything.

    Two of the three are fixed by holding the widest word's room from the start. That
    room is measured at load rather than stated, because a number read once out of a
    browser covers the face it was read in and no other: the pick column's stood at 68px
    and went 2px short the first time this ran on Linux, whose system sans sets "your
    pick" wider than macOS's. This is what said so, and it says how late a stated number
    is caught — a platform late, and only where there is a second platform to run on.

    Driven over the corpus rather than per widget: a control this sweep has never heard
    of joins it by being pressable, which is the only property it reads.

    One press per page, because a press is a gesture made on the page as published and
    the state an earlier one leaves changes what a later one proves. Pressing straight
    down the document hid the sign-off button's 12px for exactly that reason: Comments
    comes first in the banner, and with the panel open the row is crowded enough that
    the status text takes up the slack instead of the buttons — a real regression,
    silently masked by the sweep's own previous gesture."""
    url = serve(example)
    page, errors = open_page(browser, url)
    page_at_rest(page)
    total = page.locator(PRESS).count()
    pressed, dirty = 0, False
    for i in range(total):
        if dirty:  # only a press dirties the page, and most of these indices skip
            # Reloading is not on its own a reset: the panel remembers whether it was
            # open and every unsent draft is the reader's (localStorage), while the
            # reading position is this tab's (sessionStorage) — all of them
            # deliberately. Left standing they decide what
            # the next press proves — an open panel crowds the banner enough that the
            # status text takes up a shrinking button's slack instead of the buttons, so
            # the sign-off regression this test was written for passed or failed
            # according to how many times the sweep had toggled Comments.
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            # `load`, the edge the first visit took (`open_page`): network silence is
            # not a readiness fact and the two lines below are the ones that are, so
            # waiting it out only added its own 500ms quiet window to every reload
            # this sweep makes — a sixth of the test on the gallery, 50s to 42s.
            page.goto(url, wait_until="load")
            # Both stamps, which the reload has to earn again: half these controls are
            # the runtime's own, and the last of them arrive with the log rather than
            # with the upgrade. A list read before that is a short list, and a short list
            # skips by index rather than failing, which is how this sweep quietly stopped
            # pressing the sign-off button between one run and the next. It is the count
            # below that says so out loud — refuse the first poll of each navigation here
            # and every one of the examples fails on it.
            page.wait_for_function(BOTH_STAMPS)
            page_at_rest(page)
            dirty = False
            assert page.locator(PRESS).count() == total, (
                f"{example.name} has a different set of controls after a reload, so the "
                "indices this sweep walks name different things on either side of one"
            )
        page.evaluate(DEFINE_BOXES)
        control = page.locator(PRESS).nth(i)
        # A control the user can't press has no gesture to disturb anything. Both
        # spellings, because a span press can only ever wear the attribute.
        if not control.is_visible() or not control.is_enabled():
            continue
        if control.get_attribute("aria-disabled") == "true":
            continue
        label = control.evaluate(
            "(el) => el.tagName.toLowerCase() + ' '"
            "        + JSON.stringify((el.textContent || '').trim().slice(0, 24))"
        )
        before = control.evaluate(NEIGHBOURHOOD, NEIGHBOUR)
        if not before["names"]:
            continue
        control.click()
        pressed, dirty = pressed + 1, True
        # The press's own effect is synchronous; what follows it is the round trip the
        # press started and whatever its answer repaints, which is as much part of
        # pressing as the frame before it. A press that sent nothing is already round
        # tripped, so both kinds take the same rendered edge.
        round_trip(page)
        page_at_rest(page)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"))
        assert not moved, (
            f"pressing {label} in {example.name} moved the controls beside it:\n  "
            + "\n  ".join(moved)
        )
    assert pressed, f"{example.name} pressed nothing, so it asserts nothing"
    assert errors == []
    page.close()


def test_the_catalog_sidenote_can_be_aimed_whole(browser, serve):
    """The sidenote authors copy carries the identity its advertised aim needs.

    A handwritten fixture would prove the runtime and leave the catalog free to
    regress to an id-less note that renders normally but gives Alt nothing to outline.
    Drive that example itself through the whole gesture, from outline to anchored
    composer."""
    registry = validation_model.incoming_registry(
        [
            schema_model.ASSETS,
            schema_model.DEFAULT_PACKAGE,
            COMMAND_HUB_PACKAGE,
        ]
    )
    sidenote = registry["$idioms"]["aside.sidenote"]["example"]
    html = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>\n{sidenote}'
    )
    page, errors = open_page(browser, serve(html))
    note = page.locator("#logout-frequency")

    note.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "logout-frequency")
    note.click()
    page.keyboard.up("Alt")

    # The press raises the bar on the note — the tokens, then Comment — and Comment is
    # the composer, on the whole note.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "logout-frequency"
    assert errors == []
    page.close()


def test_the_aim_reads_the_pointer_where_the_press_is_dispatched_from(browser, serve):
    """The outline and the press ask one question of one point, down to the sub-pixel.

    The two readings of "what is under the pointer" come from different doors: the
    outline hit-tests the pointer record the runtime keeps, and the press takes the
    target the browser resolved for it. `mousemove` carries the pointer's place rounded
    to a whole pixel, so a record kept from one is an answer about a place the pointer is
    not — and within a pixel of a seam that place is a different item. It cost a corpus
    page a promise: ⌥ over a choose group outlined the option above the seam and the
    press commented on the one below it, which is the composer opening on an item the
    reader was never shown.

    So the aim is put within a quarter pixel of a seam, where the true point and its
    rounded twin name different items. Which of the two the true point is over depends on
    where in the pixel the seam fell, so the item the aim is held to is read off the point
    rather than named here; what is asserted first is that the two readings differ at all,
    since a seam that fell on a whole pixel would leave this proving that two agreeing
    readings agree."""
    page, errors = open_page(browser, serve(AIM_SEAM_PAGE))
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the aim point and the whole pixel it "
        "rounds to are not on the two items either side of it, so nothing here is under "
        f"test: {seam}"
    )

    page.mouse.move(seam["x"], seam["y"])
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", seam["at"])
    page.mouse.click(seam["x"], seam["y"])
    page.keyboard.up("Alt")

    # The press raises the bar on the item the aim held; Comment on it is the composer.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == seam["at"]
    assert errors == []
    page.close()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_aimed_press_does_only_what_the_outline_promised(browser, serve, example):
    """⌥-click takes the item under the pointer, and that is the whole of what it does.

    Holding ⌥ outlines what a click would take, which is a promise about the next press.
    The runtime used to read that press on the way back up, after every handler out on the
    page had already had it, so the press kept the promise and did something else besides:
    ⌥-clicking an option card opened the composer *and* picked the option, sending Claude a
    decision the user never made, while ⌥-clicking a tab's name aimed at the widget and
    switched the panel under it. Neither shows in the composer, which opens either way.

    So both halves are asserted together — the composer opens on the item that was
    outlined, and the page is exactly as it was, in its markup and in where its focus sits
    — over the corpus rather than over a case, because every widget that takes a press had
    this and none of them was ever told."""
    url = serve(example)
    page, errors = open_page(browser, url)
    # What the log already held. A shipped seed can carry a decision the reader made
    # before this page was opened, and what an aim may not do is add one of its own —
    # so the reading below is against this rather than against nothing.
    standing = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ]
    targets = aim_targets(serve.page_dir)
    total = page.locator(targets).count()
    pressed = aimed = 0
    for i in range(total):
        # A control inside a fold or behind an unopened tab is nowhere a user can aim,
        # which is the press sweep's reading of the same question, and a point the banner
        # or a neighbour covers is not this target's press at all.
        target = page.locator(targets).nth(i)
        if not target.is_visible():
            continue
        # A wrapper with no box of its own — one a page's style leaves
        # display: contents — is nowhere a user can aim (AIM_POINT finds no point
        # in it either), and
        # scroll_into_view can wait on its stability forever when it stands inside
        # a table box (a specimen). Its slots are their own targets.
        if not target.evaluate("el => el.getClientRects().length"):
            continue
        target.scroll_into_view_if_needed()
        point = target.evaluate(AIM_POINT)
        if not point:
            continue
        label = target.evaluate(NAMED)
        before = page.evaluate(PAGE_MARKUP)
        page.mouse.move(*point)
        page.keyboard.down("Alt")
        promised = page.evaluate(AIMED)
        # The cursor is the other half of the same promise, and it is derived from the
        # same value the outline is: the hand where a press takes something, the arrow
        # where it takes nothing. Read off body, which is where the aim declares it —
        # a widget's own control still states its resting cursor, and does so whether or
        # not the key is down.
        assert page.evaluate(AIM_CURSOR) == ("pointer" if promised else "default"), (
            f"holding ⌥ over {label} in {example.name} promised {promised} and pointed "
            f"a {page.evaluate(AIM_CURSOR)} cursor at it"
        )
        page.mouse.click(*point)
        page.keyboard.up("Alt")
        composer = page.locator(".lf-composer")
        bar = page.locator(".lf-fab-bar")
        if promised is None:
            # Nothing outlined is nothing to aim at — no item encloses this point — and an
            # armed press then acts on nothing rather than falling back to the page. A
            # suggestion's ✓ Accept is where that matters: its row hangs in the page's own
            # column, outside the element it decides, so nothing is above it to aim at and
            # a press let through would send Claude a decision.
            expect(bar).to_be_hidden()
            expect(composer).to_be_hidden()
        else:
            # The press raises the bar on the item; Comment on it is the composer.
            expect(bar).to_be_visible()
            page.locator(".lf-fab").click()
            expect(composer).to_be_visible()
            mark = page.evaluate(DRAFT_MARK)
            # A box a standing thread already outlines keeps the posted colour and takes
            # no pending class of its own: the draft claims whichever boxes are still
            # free (paintAnchors), so aiming at an element the log already marks keeps
            # the promise and paints nothing new. The other half of the press is read
            # either way — where the composer opened on something else, that element
            # wears the pending mark and this reads it there.
            if mark is None and page.locator(f"#{promised}.lf-mark-el").count():
                mark = promised
            assert mark == promised, (
                f"⌥-clicking {label} in {example.name} promised {promised} and "
                f"commented on {mark}"
            )
            # And the promise is kept where the reader can see it kept. An outline needs
            # a box, and an item that draws none — every suggestion is display: contents —
            # would take the mark to 0x0 at the document's origin, showing nothing. The
            # composer places itself off this same record, so it would go to the top of
            # the window along with it, beside a passage it is no longer beside.
            unshown = page.evaluate(
                """() => [...document.querySelectorAll('.lf-mark-el.lf-pending')]
                   .filter(e => { const b = e.getBoundingClientRect();
                                  return !(b.width && b.height); })
                   .map(e => e.tagName.toLowerCase())"""
            )
            assert not unshown, (
                f"⌥-clicking {label} in {example.name} outlined {unshown}, which draws "
                "no box, so the promise is invisible and the composer stands off a rect "
                "at the top of the document"
            )
            # Put the composer away before reading the page back: its own passage wears
            # the outline, which is the one mark an aim is supposed to leave.
            page.keyboard.press("Escape")
            expect(composer).to_be_hidden()
            aimed += 1
        assert page.evaluate(PAGE_MARKUP) == before, (
            f"⌥-clicking {label} in {example.name} changed the page, so a press the aim "
            "had taken reached a widget as well"
        )
        assert not page.evaluate(FOCUS_IN_PAGE), (
            f"⌥-clicking {label} in {example.name} left the focus on the page, so the "
            "press reached the control under it"
        )
        pressed += 1
    assert pressed, f"{example.name} pressed nothing, so it asserts nothing"
    # And that the outline is still painted at all: a preview that stopped appearing would
    # leave every press above asserting only that nothing happened, which is the shape of
    # vacuous pass this sweep is most exposed to.
    assert aimed, f"{example.name} outlined nothing, so no press was held to a promise"
    # The other half of "did nothing else", and the half the markup cannot show: a widget
    # that acts tells Claude so, and a decision the user never made is worse in the log
    # than on the page. The wait is the page's own sends coming back, so a stray one is in
    # the log to be read rather than still in flight.
    round_trip(page)
    assert [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == standing, (
        f"⌥-clicking through {example.name} left a decision in the log that the aim "
        "never promised"
    )
    assert errors == []
    page.close()


def test_an_aim_on_a_seam_promises_and_takes_the_same_item(browser, serve):
    """One reading, at the one place the pointer is.

    The cells of a joined group butt, so two of them share an edge with no gap between,
    and a pointer resting on it is inside both by the width of a rounding. The outline
    and the press each used to hit-test that point for themselves — elementFromPoint
    against the browser's own dispatch — and nothing makes two hit tests tie-break a
    shared edge alike. What a reader got was one option outlined and the next one
    commented on.

    The sweep over the corpus reaches this case only where the page happens to put a
    seam under the point it picks, which is a fact about font metrics: the same aim was
    a cell's interior on one platform and a seam on another, and the corpus said the
    promise was kept for a year on the machine where it was. So the seam is aimed at
    here rather than waited for, and the assertion is the platform-independent half —
    whichever way each reading rounds, both answer the same item."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    edge = page.evaluate(
        """() => {
            const above = document.querySelector('#l-shim').getBoundingClientRect();
            const below = document.querySelector('#l-stage').getBoundingClientRect();
            return {y: above.bottom, apart: Math.abs(below.top - above.bottom),
                    x: above.left + above.width / 2};
        }"""
    )
    assert edge["apart"] < 0.5, (
        f"the cells stand {edge['apart']}px apart, so this aims at a gap and not at the "
        "seam the two readings can differ over"
    )
    page.mouse.move(edge["x"], edge["y"])
    page.keyboard.down("Alt")
    promised = page.evaluate(AIMED)
    assert promised in ("l-shim", "l-stage"), (
        f"the aim promised {promised} on the seam between the two cells, so the reading "
        "under test never happened"
    )
    page.mouse.click(edge["x"], edge["y"])
    page.keyboard.up("Alt")
    # The press raises the bar on what it took, and Comment is the way from there into
    # the composer — the same route a selection takes.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == promised, (
        f"the outline promised {promised} on the seam and the press commented on "
        f"{page.evaluate(DRAFT_MARK)}"
    )
    assert errors == []
    page.close()


def test_a_key_still_reaches_its_control_after_an_aimed_press(browser, serve):
    """The aim holds its claim until the next press starts, and a key is not one.

    The option scope works its selection toggle by calling click(), so a control worked
    from the keyboard sends a click with no press behind it. Taken for the aim's own, it
    goes nowhere at all: the user presses Space on a pick mark and nothing is
    picked, on a page where the last thing they did with the mouse was aim."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    expect(page.locator(".lf-fab-bar")).to_be_visible()  # the press was the aim's
    page.locator(".lf-fab").click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    page.locator("#opt-shim .lf-pick").focus()
    page.keyboard.press(" ")
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(1)
    round_trip(page)
    assert [
        e["action"] for e in events_model.read_events(serve.page_dir) if "action" in e
    ] == ["choose"]
    assert errors == []
    page.close()


def test_the_aim_still_promises_while_a_composer_is_open(browser, serve):
    """An armed press with the box up re-anchors it, so the aim must still say where.

    claimPress acts whether or not a composer stands open, and openComposer carries the
    typed text onto the new anchor — so the aim standing down on composerOpen, as it did
    from its first commit, left exactly one press made blind: the one that moves a
    draft. Holding ⌥ over a second item raises its box beside the draft's own mark;
    two at once is the true state — where the draft stands, and where a press would
    move it — and the press then does what the box promised."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    composer.locator("textarea").fill("carried words")

    card = page.locator("#card-notes")
    card.hover()
    page.keyboard.down("Alt")
    promised = [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)]
    assert promised == ["card-notes", "t"], (
        f"holding ⌥ over a card with a draft open on the heading showed {promised} as "
        "[aim, draft], so the press that would move the draft is blind"
    )
    card.click()
    page.keyboard.up("Alt")
    # The bar comes up on the card over the open box; its Comment moves the box.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(composer).to_be_visible()
    expect(composer.locator("textarea")).to_have_value("carried words")
    assert [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)] == [
        None,
        "card-notes",
    ], "the press re-anchored the draft, so its new anchor alone should stand marked"
    round_trip(page)
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []
    assert errors == []
    page.close()


def test_a_reload_under_a_held_aim_rearms_on_the_first_move(browser, serve):
    """The arm survives what the keydown cannot.

    `aiming` is armed by an Alt keydown, and a page reloaded under a held key — the
    poll following a new version does exactly this — never hears one, while claimPress
    reads live modifier state: every press on the new page was claimed and none could
    be promised. Mouse events carry that same live state, so the first move re-derives
    the arm; this drives that move rather than a keydown the reload already ate."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)  # the latch is gone
    heading.hover()  # the first move under the still-held key
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
    page.keyboard.up("Alt")
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
    new_layer = registry_model.layer_generation(serve.page_dir)
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
    old_layer = registry_model.layer_generation(serve.page_dir)

    old_server = serve.httpd
    address = old_server.server_address
    old_server.shutdown()
    old_server.server_close()
    initialized = CliRunner().invoke(
        cli_model.cli, ["page", "init", str(serve.page_dir)]
    )
    assert initialized.exit_code == 0, initialized.output
    assert registry_model.layer_generation(serve.page_dir) != old_layer
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


def test_design_mode_comments_on_what_a_press_lands_on_and_nothing_else(browser, serve):
    """A press in design mode is a comment about the layer, and that is all it does.

    The mode is the ⌥ aim generalized: a press on a widget names the widget rather than
    working it, so a pick mark can be pointed at without picking. The comment posts
    with `about: "layer"`, which is how the agent tells "this control looks wrong" from
    a remark about the words — nothing about the anchor alone says which. Both halves
    are asserted: the log's event, and the page exactly as it was."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    option = page.locator("#opt-shim")
    before = page.evaluate(PAGE_MARKUP)
    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))

    # The mode shows what is on the page rather than waiting for the pointer: a legend
    # box on every item, and on every item but a widget's parts its name — the group
    # is named, its options wear the hairline alone and are named under the pointer.
    def box_of(element_id):
        return page.locator(f'.lf-legend-box[data-for="{element_id}"]')

    expect(box_of("t")).to_be_visible()
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
    ) == set(page.eval_on_selector_all("main [id]", "es => es.map(e => e.id)"))
    expect(box_of("approach").locator(".lf-legend-tag")).to_have_text(
        "lf-options · approach"
    )
    expect(box_of("t").locator(".lf-legend-tag")).to_have_text("heading · t")
    expect(box_of("opt-shim").locator(".lf-legend-tag")).to_have_count(0)
    page.wait_for_function(LEGEND_TRUE)
    # Hovering names the target — the tag and the id a fix is written against — and
    # draws the aim's own box on it, the promise about the next press.
    option.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-option · opt-shim")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "opt-shim")
    option.click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · lf-option · opt-shim"
    )
    # The press did nothing to the page: not a pick, not a focus, nothing in the markup
    # but the composer's own outline on the element it is about.
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(0)
    assert (
        page.evaluate(PAGE_MARKUP).replace(' class="lf-mark-el lf-pending"', "")
        == before
    )
    assert not page.evaluate(FOCUS_IN_PAGE)
    page.locator(".lf-composer textarea").fill("the ring reads too heavy")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    events = events_model.read_events(serve.page_dir)
    posted = [e for e in events if e["kind"] == "comment"]
    assert [(e["about"], e["anchor"]) for e in posted] == [
        ("layer", {"section": "opt-shim"})
    ]
    assert [e for e in events if e["kind"] == "action"] == []
    # The panel names the thread the same way the composer named the box, and the send
    # lands typing in that thread's reply box.
    expect(page.locator(".lf-thread .lf-quote")).to_have_text(
        "layer · lf-option · opt-shim"
    )
    expect(page.locator(".lf-thread textarea")).to_be_focused()
    # Escape backs out one rung at a time — the box, then the mode.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    expect(page.locator(".lf-inspect")).to_be_hidden()
    expect(page.locator(".lf-legend-box")).to_have_count(0)
    assert errors == []
    page.close()


def test_design_mode_reaches_the_chrome_and_names_the_control(browser, serve):
    """The banner, the panel, a control on either: what no comment could reach before.

    The anchor pass passes over the runtime's own layer, so a remark about the Comments
    button had nowhere to land. In design mode the press on it is a comment on it —
    anchored on the part the runtime named (`lf-banner`), naming the control the press
    landed on — and the button does not do what it does: the panel stays closed."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    comments = page.locator(".lf-banner .lf-comments")
    said = comments.inner_text()  # "Comments (0)" — the control's word is what it shows
    comments.hover()
    expect(page.locator(".lf-inspect")).to_have_text(f"{said} · banner")
    comments.click()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(f"layer · {said} · banner")
    expect(page.locator(".lf-panel")).to_be_hidden()
    page.locator(".lf-composer textarea").fill("reads dim against the wash")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    posted = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    ]
    assert [(e["about"], e["anchor"]) for e in posted] == [
        ("layer", {"section": "lf-banner", "part": said})
    ]
    # The thread's mark is the outline an element anchor wears, on the chrome too.
    expect(page.locator("#lf-banner")).to_have_class(re.compile(r"\blf-mark-el\b"))
    page.keyboard.press("Escape")

    # And the comment panel, which is the case where the aim's own geometry had nothing to
    # say. A fixed box is not clipped by the page's scroller, and body is that scroller
    # narrowed to the column standing beside the panel — so the panel measured through its
    # ancestors came back wholly clipped away, and a mode whose row promises a click on the
    # chrome drew nothing over the chrome. Wide enough for the panel to stand beside the
    # page, which is where body and the panel part company.
    resized(page, 1280, 800)
    page.locator(".lf-banner .lf-comments").click()
    expect(page.locator(".lf-panel")).to_be_visible()
    page.wait_for_function(
        "() => document.querySelector('.lf-panel').getBoundingClientRect().left"
        " >= document.body.clientWidth"
    )
    page.keyboard.press("i")
    box = page.locator(".lf-panel").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 30)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "lf-comments")
    assert page.evaluate(
        """() => {
             const aim = document.querySelector('.lf-aim').getBoundingClientRect();
             const panel = document.querySelector('.lf-panel').getBoundingClientRect();
             return Math.abs(aim.width - panel.width) < 3
                 && Math.abs(aim.left - panel.left) < 3;
           }"""
    ), "the aim's box does not stand on the panel it names"
    assert errors == []
    page.close()


def test_design_mode_takes_an_edge_rather_than_drawing_it(browser, serve):
    """The mode promises that a press comments on what it lands on and does nothing else,
    and a region's edge is the piece of chrome whose press moves the page rather than the
    page's content. A drag on it under the mode leaves the region where it was and opens a
    composer naming the edge, which is what a reader remarking on it has to be able to do.

    Neither half is anything the edge knows: the mode takes the press above the runtime's
    own handler, and the name comes of the platform's word for what the press landed on.
    So this is a reading of whether a new control joins the mode by being one — which is
    what it would stop doing the day an edge answered a press for itself. One edge is the
    whole reading, both being one handler (`drawnEdge`); what the second edge could break
    here it would break for the first too."""
    edge = EDGES[0]
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    resized(page, 1280, 800)
    page.locator(".lf-comments").click()
    panel_settled(page)
    standing = geometry(page, edge)
    page.keyboard.press("i")
    draw_edge(page, edge, 160)
    held = geometry(page, edge)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · Comment panel width · comments"
    )
    page.close()

    assert held["width"] == standing["width"], (
        f"the mode moved the edge it was asked to comment on: {standing} then {held}"
    )
    assert held["chosen"] is None, (
        f"a press the mode took was still recorded as the reader's width: {held}"
    )
    assert errors == []


def test_design_mode_leaves_prose_to_the_selection(browser, serve):
    """Words are still the way to point at words: a drag on prose selects, and the
    comment it raises is about the layer; a plain click on prose comments on the block.

    The mode takes presses on widgets, controls and the chrome at the press, ahead of the
    page. Prose it leaves to the browser, or "this heading is too small" would have no
    way to quote the heading."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    heading = page.locator("#t")
    box = heading.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
    )
    fab = page.locator(".lf-fab")
    expect(fab).to_be_visible()
    fab.click()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · heading · t · “Rollout”"
    )
    page.keyboard.press("Escape")  # the composer, draft kept; the mode still stands
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    heading.click(position={"x": 4, "y": 4})
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text("layer · heading · t")
    assert errors == []
    page.close()


def test_design_mode_survives_the_reload_a_new_version_brings(browser, serve):
    """A version landing mid-batch reloads the document, and a reader put out of the
    mode by news they never asked for is a mode error the page made — so the mode is
    this tab's working state, kept the way the panel's open state is."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    expect(page.locator('.lf-legend-box[data-for="approach"]')).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    assert errors == []
    page.close()


def test_the_legend_follows_the_page_it_is_a_reading_of(browser, serve):
    """A legend box kept from a previous reading is a claim about a page that has moved.

    Three of the doors that move it: the page scrolling (items come on screen with no
    box yet, and the boxes are drawn in document space), the panel opening (the column
    re-centres, every block reflows, and no scroll or replay says so — each item's own
    resize does), and the name under the pointer, which is drawn beside the box in the
    same space: it sat in viewport space once, with the scroll added on top, and stood a
    screen below its box on any page scrolled at all. The aim is one more of the
    chrome's promises over the same page, so the reflow doors repaint it too
    (pageShifted): it once kept its old coordinates through the panel's slide, a box
    and name floating half a panel to the right of the element they claimed."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("i")
    page.wait_for_function(LEGEND_TRUE)
    page.locator("body").evaluate("b => { b.scrollTop = 1200; }")
    p = page.locator("#p20")
    expect(p).to_be_in_viewport()
    expect(page.locator('.lf-legend-box[data-for="p20"]')).to_be_visible()
    page.wait_for_function(LEGEND_TRUE)
    # The name floats where the box's tag stood, over the item's corner — on a scrolled
    # page as on a fresh one.
    p.hover()
    expect(page.locator(".lf-inspect")).to_have_text("paragraph · p20")
    box = page.locator(".lf-aim").bounding_box()
    name = page.locator(".lf-inspect").bounding_box()
    assert abs(name["y"] + name["height"] - box["y"]) < 4, (name, box)
    assert abs(name["x"] - box["x"]) < 4, (name, box)
    # The panel takes a strip from the page and every block moves; the legend moves
    # with them, off the resize each item reports. Opened by key: in the mode a press
    # on the Comments button is a comment about the button.
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()
    page.wait_for_function(
        "() => document.body.getAnimations().every(a => a.playState !== 'running')"
    )
    page.wait_for_function(LEGEND_TRUE)
    # The legend's repaint above consumed the reflow's edge, and the aim was refreshed
    # in the same pageShifted, so one plain read is the settled answer: the pointer
    # still rests in p20, and the promise is about where p20 stands now.
    aim = page.evaluate(
        """() => {
      const b = document.querySelector('.lf-aim');
      const it = document.getElementById(b.dataset.for);
      const r = it.getBoundingClientRect();
      const bb = b.getBoundingClientRect();
      return { on: b.dataset.for, dx: bb.left - r.left, dy: bb.top - r.top };
    }"""
    )
    assert aim["on"] == "p20" and abs(aim["dx"]) < 2 and abs(aim["dy"]) < 2, aim
    assert errors == []
    page.close()


def test_two_names_at_one_corner_step_apart(browser, serve):
    """A block whose top-left corner is also its container's — the paragraph's margin
    collapses out of the section, exactly the shape a suggestion and the block it wraps
    make — wrote both tags onto one spot, and the longer peeked out past the shorter at
    both ends as fragments of a word nobody wrote. The later tag steps away by tag
    heights until it stands clear."""
    page, errors = open_page(browser, serve(CORNER_PAGE))
    page.keyboard.press("i")
    expect(
        page.locator('.lf-legend-box[data-for="wrap"] .lf-legend-tag')
    ).to_be_visible()
    expect(
        page.locator('.lf-legend-box[data-for="inner"] .lf-legend-tag')
    ).to_be_visible()
    clash = page.evaluate(
        """() => {
      const rs = [...document.querySelectorAll('.lf-legend-tag')]
        .map(t => t.getBoundingClientRect()).filter(r => r.width);
      for (let i = 0; i < rs.length; i++)
        for (let j = i + 1; j < rs.length; j++) {
          const a = rs[i], b = rs[j];
          if (a.left < b.right - 1 && b.left < a.right - 1 &&
              a.top < b.bottom - 1 && b.top < a.bottom - 1)
            return [a, b].map(r => [r.left, r.top, r.width, r.height]);
        }
      return null;
    }"""
    )
    assert clash is None, clash
    assert errors == []
    page.close()


def test_a_picture_is_one_item_however_many_ids_its_renderer_coined(browser, serve):
    """The aim over a diagram's node named the node — `root-1`, an id mermaid minted and
    the next render may not — where a plain click already anchored the widget. The
    entry says which (x-visual: the click's anchor is the widget rather than a generated
    part inside it), so the aim and the legend both stop at the widget."""
    page, errors = open_page(browser, serve(PICTURE_PAGE))
    node = page.locator("#flow svg g[id]").first
    expect(node).to_be_visible()
    node.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "flow")
    page.keyboard.up("Alt")
    page.keyboard.press("i")
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
    ) == {"t", "p", "flow", "tree"}
    node.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-diagram · flow")
    assert errors == []
    page.close()


def test_a_declared_flowchart_node_keeps_its_comment_across_renderings(browser, serve):
    """The authored Mermaid id, rather than its generated SVG id, is the anchor.

    An unlisted node is the control: it still takes the whole diagram. A listed node
    outlines only its current SVG group, while the diagram holds the accessible note
    and the panel place. Reloading makes Mermaid generate the SVG again and proves the
    stable token resolves to that new box.
    """
    page, errors = open_page(browser, live_url(serve(PART_DIAGRAM_PAGE)))
    diagram = page.locator("#flow")

    unlisted = diagram.locator('g[id^="flowchart-U-"]')
    unlisted.click()
    page.locator(".lf-fab").click()
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    page.get_by_role("button", name="Cancel").click()

    start = diagram.locator('g[id^="flowchart-S-"]')
    start.click()
    page.locator(".lf-fab").click()
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    page.locator(".lf-composer textarea").fill("name the retry path here")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "flow", "visual": "node:S"}
    ]
    expect(page.locator(".lf-thread .lf-quote")).to_have_text(
        "§ diagram · Start request"
    )
    expect(diagram.locator(":scope > .lf-mark-note")).to_have_count(1)
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b"))

    (serve.page_dir / "versions" / "v2.html").write_text(PART_DIAGRAM_V2)
    stamp_version_file(serve.page_dir, 2, "reordered")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    expect(diagram.locator('g[id^="flowchart-S-"]')).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(diagram.locator(":scope > .lf-mark-note")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_linked_flowchart_node_uses_the_item_aim_for_its_comment(browser, serve):
    """A link keeps plain navigation while Alt-click claims only the node comment."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    handler = diagram.locator('g[id^="flowchart-H-"]')
    expect(handler.locator("xpath=ancestor::*[local-name()='a'][1]")).to_have_count(1)

    handler.click(modifiers=["Alt"])
    expect(handler).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    page.locator(".lf-composer textarea").fill("keep this linked step visible")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "flow", "visual": "node:H"}
    ]
    assert errors == []
    page.close()


def test_design_mode_keeps_its_control_label_on_a_part_visual(browser, serve):
    """A design-control label is not reinterpreted as a semantic visual token."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    handler = diagram.locator('g[id^="flowchart-H-"]')
    page.keyboard.press("i")
    handler.click()

    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · Handle request · lf-diagram · flow"
    )
    page.locator(".lf-composer textarea").fill("the link needs a stronger affordance")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["about"], event["anchor"]) for event in posted] == [
        ("layer", {"section": "flow", "part": "Handle request"})
    ]
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(handler).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    assert errors == []
    page.close()


def test_visual_parts_refuse_a_mermaid_type_the_adapter_cannot_address(browser, serve):
    """An unsupported promise is visible instead of producing detached anchors later."""
    unsupported = leaf_page(
        "unsupported diagram parts",
        """
<h1 id="t">Exchange</h1>
<lf-diagram id="exchange" parts="node:A"><pre>
sequenceDiagram
  A->>B: Request
</pre></lf-diagram>
""",
    )
    page, _ = open_page(browser, serve(unsupported))

    expect(page.locator("#exchange .lf-error")).to_contain_text(
        "commentable flowchart nodes not found: node:A"
    )
    page.close()


def test_a_scroll_under_a_held_aim_moves_the_promise_with_the_page(browser, serve):
    """What a press would take can change with no mouse event to say so.

    Only a pointer move used to re-ask the aim, so scrolling under a held key left the
    outline on the item that had been under the pointer while a press took the one now
    there — the paint answering an old page, the claim the current one. The scroll
    listener re-asks; this scrolls the page under a parked pointer and requires the
    promise to answer for where the page now stands."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.mouse.move(600, 300)
    page.keyboard.down("Alt")
    first = page.evaluate(AIMED)
    assert first, "nothing promised under the parked pointer, so nothing is being aimed"
    # Three whole paragraphs of scroll, measured off the page: the paragraphs are
    # identical, so the pointer's offset into the outlined one becomes the same offset
    # into the one three later, never the margin between two. body is the page's
    # scroller, and scrollBy fires the same scroll events a wheel does.
    page.evaluate(
        """() => document.body.scrollBy(0, 3 *
          (document.getElementById("p3").getBoundingClientRect().top -
           document.getElementById("p2").getBoundingClientRect().top))"""
    )
    page.wait_for_function(
        """(first) => {
      const promised = document.querySelector(".lf-aim")?.getAttribute("data-for");
      const at = document.elementFromPoint(600, 300)?.closest("[id]:not(.lf-ui)");
      return Boolean(promised) && promised === at?.id && promised !== first;
    }""",
        arg=first,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_a_replay_under_a_held_aim_repaints_the_promise(browser, serve):
    """A pass that runs paints the truth, whatever ran it.

    A replay of another tab's action moves content and repaints the marks where they
    now belong — and the aim used to ride that pass as an answer latched from the last
    mouse event, so the pass itself painted a promise about a card no longer there.
    The aimed item is derived inside the pass now, and the events only decide when a
    pass is worth running. Nothing here moves the mouse after the arm: the page moves
    instead, and the box must follow or clear."""
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)
    spot = page.locator("#card-importer").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + 8]; }"
    )
    page.mouse.move(*spot)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-importer")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "work",
            "action": "move",
            "detail": {"card": "card-importer", "to": "col-done", "index": 0},
        },
    )
    told(page)
    expect(page.locator("#col-done #card-importer")).to_have_count(1)
    page.wait_for_function(
        """([x, y]) => {
      const promised =
        document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null;
      const at = document.elementFromPoint(x, y)?.closest("[id]:not(.lf-ui)") ?? null;
      return promised === (at?.id ?? null) && promised !== "card-importer";
    }""",
        arg=spot,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_the_aims_box_is_what_the_page_shows_of_the_item(browser, serve):
    """The promise paints in the chrome's layer, and claims what the page shows.

    The aim used to wear the mark's hairline, and the mark's band is one pixel at the
    border edge — the one band of an element nobody else paints in, and exactly where a
    widget draws a border of its own. Over a recommended option, whose border is
    already the accent, arming changed nothing a reader could see, and what was
    reported was no box at all. So the aim paints in the layer above the page, which no
    widget can reach; the pixel diff here is armed against unarmed with the pointer
    held still, so the widget's own hover wash is in both frames and the difference is
    the promise alone.

    A layer no widget can paint over is also one no ancestor's clip can reach, so the
    second half holds the box to the page's own showing of the item: a row's table box
    runs on under its group's overflow: hidden, and a box drawn from the raw rect
    would claim pixels the page has refused, over whatever stands in them."""
    from PIL import Image, ImageChops  # a dev dependency already, for the demo recorder

    page, errors = open_page(browser, serve(AIM_PAINT_PAGE))
    card = page.locator("#card-star")
    card.hover()
    # The wash and the lift a card answers the pointer with are transitions, and a
    # frame taken mid-glide would bill the arm for pixels the hover was still moving.
    page.wait_for_function(
        """() => document.getElementById("card-star")
                 .getAnimations({subtree: true}).length === 0"""
    )
    box = card.bounding_box()
    clip = {"x": math.floor(box["x"]), "y": math.floor(box["y"])}
    clip |= {"width": math.floor(box["width"]), "height": math.floor(box["height"])}
    quiet = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-star")
    armed = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    assert quiet.size == armed.size
    geometry = page.evaluate("""() => {
        const item = document.getElementById("card-star").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return [box.left - item.left, box.top - item.top,
                box.width - item.width, box.height - item.height].map(Math.abs);
    }""")
    assert max(geometry) < 1, f"the box missed the card it promises by {geometry}"
    pixels = zip(*[iter(ImageChops.difference(quiet, armed).tobytes())] * 3)
    changed = sum(max(p) >= 6 for p in pixels) / (armed.size[0] * armed.size[1])
    assert changed > 0.5, (
        f"arming changed {changed:.0%} of the card's pixels — the promise is not "
        "something a reader can see over the widget's own paint"
    )

    row = page.locator("#row-ship")
    row.hover()
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "row-ship")
    edges = page.evaluate("""() => {
        const group = document.getElementById("rows").getBoundingClientRect();
        const row = document.getElementById("row-ship").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return { box: box.right, shown: Math.min(row.right, group.right),
                 raw: row.right };
    }""")
    assert abs(edges["box"] - edges["shown"]) < 1, (
        f"the box ends at {edges['box']} where the page shows the row to "
        f"{edges['shown']} (its unclipped box runs to {edges['raw']}): a clip the "
        "page enforces went unhonoured"
    )
    page.keyboard.up("Alt")
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


def test_the_chrome_keeps_its_presses_while_the_page_is_armed(browser, serve):
    """What ⌥ arms is the page, and the line around it is the chrome's container.

    An aim that reached in there would take the panel, the composer and the banner away
    from a user who happens to be holding the key — and there is nothing in the layer
    to aim at anyway, since an anchor names an element of the page."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    comments = page.locator(".lf-comments")
    comments.hover()
    page.keyboard.down("Alt")
    comments.click()
    page.keyboard.up("Alt")
    panel_settled(page)
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert errors == []
    page.close()


def test_the_armed_cursor_says_whether_a_press_would_take_anything(browser, serve):
    """The chord's cost is that it is invisible, and the cursor pays part of it.

    Holding ⌥ used to draw a plain arrow over the whole page: it said "not a text
    selection" and nothing else, which leaves the one question the outline can't answer
    for a reader who hasn't looked yet — would this click do anything at all? An armed
    press takes the item under it and acts on nothing where there is none (claimPress),
    so the hand and the arrow are those two states, and the hand is exactly as good as
    the outline beside it because both are read off the same value.

    Read where the reader's pointer is rather than off body, since the aim declares it
    on body and everything on the page inherits it — the promise is only kept if it
    arrives at the glyphs. The margin beside the column is the page's own gap: no
    element there carries an id, so an armed press has nothing to take.

    `auto` is the resting state, and it is the whole point of the arrow: unarmed, the
    browser decides from what is under the pointer and draws an I-beam over words, so
    naming a cursor at all is the runtime saying those words are not a selection now."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    at_pointer = """([x, y]) =>
        getComputedStyle(document.elementFromPoint(x, y)).cursor"""
    on_item = page.locator("#p2").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + 20, r.top + r.height / 2]; }"
    )
    # Beside the column, level with the same paragraph: body's own margin, which the
    # centred 720px column leaves on a 1200px viewport.
    in_gap = [40, on_item[1]]
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "an unarmed page already named a cursor, so the arm has nothing left to say"
    )

    page.mouse.move(*on_item)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    assert page.evaluate(at_pointer, on_item) == "pointer", (
        "the aim boxed the paragraph and the cursor declined to promise the press"
    )

    page.mouse.move(*in_gap)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, in_gap) == "default", (
        "the aim had nothing to take and the hand promised a press anyway"
    )

    # Back on the item, so the arm coming off is read from the state that promises most.
    page.mouse.move(*on_item)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    page.keyboard.up("Alt")
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "the key came up and the page went on offering the aim's press"
    )
    assert errors == []
    page.close()


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

    # A reservation is a promise the row can keep only while it has the room, and a row
    # out of room takes it from whatever will give. Every control up there is a .lf-btn,
    # floored at its own words by nowrap, so none of them is what gives: what does is the
    # status text and the chip, which is where the spacer's slack was — both left of
    # everything else on the row, so what they give up moves nothing. The chooser was the
    # exception while it was a <select> stating a width against unbounded notes: it was
    # the one control that could give, so it did, dropping under the width it states and
    # putting every arrival above back in play on any window narrow enough. It says the
    # version alone now, so it is floored like the rest and this list covers the whole row.
    holds_its_width = (
        "() => ['.lf-version', '.lf-comments', '.lf-signoff', '.lf-answer-all', '.lf-asks']"
        ".map((s) => document.querySelector('.lf-banner ' + s).offsetWidth)"
    )
    wide = page.evaluate(holds_its_width)
    resized(page, 900, 900)
    # Out of room, and something has visibly given: no spacer left, and the chip showing
    # less than it holds. Without both, a window that still had slack would assert nothing.
    page.wait_for_function(
        "() => { const chip = document.querySelector('.lf-latest-chip');"
        "        return document.querySelector('.lf-spacer').offsetWidth === 0"
        "               && chip.offsetWidth < chip.scrollWidth; }"
    )
    assert page.evaluate(holds_its_width) == wide, (
        "a banner with no room left took it out of the controls that hold their width, "
        "which is what leaves them free to move on the next thing that arrives"
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
    page.keyboard.press("l")  # the key opens the panel like the button does
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
    # Nothing live left to open: the button stands while the panel does and stands
    # down with it, which is the count's other half.
    page.keyboard.press("Escape")
    told(page)
    expect(btn).not_to_be_visible()
    assert errors == []
    page.close()


def test_the_leaves_tray_takes_the_keyboard(browser, serve, live_leaf):
    """The tray is a list, and a reader walks it without reaching for the mouse: l
    opens it and lands on the first neighbour, up and down step between them and clamp
    at the ends, Enter opens the focused one in its own tab, and Esc hands focus back
    to the button that opened it. The key line names l before it is pressed and the
    tray's own keys while focus is inside it — the promise and the press being one
    scene — and the "?" reference carries the same rows."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (3)")
    keyline = page.locator(".lf-keyline")
    # A shortcut no surface names is a shortcut nobody finds: the line carries l for
    # exactly as long as there is a tray to open.
    expect(keyline).to_contain_text("leaves")
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
    expect(help_el).to_contain_text("Walk the leaves")
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
    page.keyboard.press("a")
    rows = page.locator("button.lf-asks-row")
    expect(rows).to_have_count(12)
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
@pytest.mark.parametrize("color_scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1200, 420])
def test_examples_have_no_serious_wcag_a_or_aa_violations(
    browser, serve, example, color_scheme, width
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
    page, errors = open_page(browser, serve(example))
    resized(page, width, 900)
    page.emulate_media(color_scheme=color_scheme)
    violations, report = serious_axe_violations(page)
    assert violations == [], report
    assert errors == []
    page.close()


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1200, 420])
def test_the_chrome_a_key_opens_has_no_serious_violations(
    browser, serve, other_leaf, color_scheme, width
):
    """The corpus sweep above reads every example, and reads all of them with the chrome
    shut: it never presses a key, so the comment panel, its box, the trays, the versions
    menu, the keyboard reference and the chord's chips are surfaces forty parametrisations
    pass straight over. A `role="list"` whose children are run headings and threads shipped
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
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
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

    # And the chord's chips, which are painted over the page rather than in it — so the
    # letter as well as the `g`, because arming alone paints none.
    page.keyboard.press("g")
    page.keyboard.press("c")
    expect(page.locator(".lf-addresses > .lf-address").first).to_be_visible()
    sweep("with the chord aimed at the comments")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """The gate refuses words under `.lf-ui` inside a widget, because a widget reaching for
    that marker is how a user ends up unable to comment on a heading they can see. The
    line saying how many comments are on a passage wears the same marker and sits wherever
    the passage does — inside the widget, when that is where the comment was made. Unless
    the gate knows the difference, one comment on an option is a page nobody can hand over,
    and every page the sweep above renders is a page with no comments on it.

    The pass hunting words drawn on other words has to know the same difference, and
    knows it as a float the runtime hangs over the page. That line is clipped to nothing
    and checkVisibility answers for display, visibility and opacity, so it reads as drawn,
    and its characters fall down the document through the paragraphs under the passage.
    Holding it out is the only thing keeping this page clean, so the reading is taken
    twice: once as the gate runs it, and once with the hold defeated, where it has to
    report.

    The hold is the float predicate rather than a class named in the skip list, which is
    what the second reading has to reach for now: the line is out-of-flow chrome like a
    suggestion's controls, so one rule answers for both and a name beside it would be the
    same guarantee kept twice."""
    # The last option, because the unheld half below needs the line to land on words:
    # the note is the holder's last child, so its characters fall from the end of the
    # option's own prose, and from a mid-group option they fall through the whitespace
    # tails of the shorter cells below and are spent before any paragraph. From the
    # group's last option they cross straight into #p, whose full-width lines have a
    # word at any x the option's prose can end on.
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page, errors = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that has the line on it.
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-mark-note').length === 1"
    )
    # The same reading with the hold defeated, taken while the page is up.
    reported = render_checks_model.evaluate_probe(
        page, "coveredWords", {"holdFloating": False}
    )
    assert errors == []
    page.close()
    assert rendering_model.render_version(browser, url) == []
    assert any("1 comment" in found for found in reported), (
        "the line falls on nobody, so a gate that never looked would pass this too"
    )


def test_the_gate_passes_a_page_whose_collapsed_cards_lie_on_each_other(browser, serve):
    """Words drawn on other words is a question about the screen, and a collapse is the
    page being asked to take words off it. The cards behind a settled row wear
    hidden="until-found" so find-in-page still reaches them, which is content-visibility
    rather than display, and checkVisibility answers for neither: they read as drawn, and
    each reports the box it last laid out in, so all three land on one another. That is
    the collapse working, and COVERED_WORDS says why it is held out.

    On a fresh load whether they report at all is a coin, which is no basis for a test.
    Opening the row and closing it again settles it: the cards lay out for real, and the
    boxes they keep afterwards are that layout."""
    url = serve(SETTLED_PAGE)
    page, errors = open_page(browser, url)
    row = page.locator("#transport .lf-settled")
    card = page.locator("#transport #opt-lax")

    row.click()
    expect(card).to_be_visible()
    row.click()
    expect(card).to_be_hidden()

    # The gate's own reading, taken here rather than left to render_version: that opens a
    # fresh page, which is the coin again, and this page is the one holding the layout the
    # cards kept. Then the same named reading with its collapsed-content hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(page, "coveredWords", {"holdHidden": False}),
    )
    assert errors == []
    assert held == []
    assert any("opt-" in found for found in reported), (
        "the cards fell on nobody, so a gate that never looked would pass this too"
    )
    page.close()
    assert rendering_model.render_version(browser, url) == []


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A chip is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a chip saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one. A suggestion swapping one short word is the same case in a second tag,
    there because the gate dispatches on the declaration: the day the wrapper took a box
    it stood in front of this floor, and only x-inline says whose floor is whose.

    The floor a chip does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page, errors = open_page(browser, url)
    widths = page.locator("lf-chip").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert errors == []
    assert widths and max(widths) < 40, (
        f"these chips are {widths}px, so they clear the floor and prove nothing"
    )
    sug_width = page.locator("#sug-flag").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert sug_width < 40, (
        f"the suggestion is {sug_width}px, so it clears the floor and proves nothing"
    )

    # Asked without the declaration, the same floor flags it — so what passes the page
    # is the declaration, not a floor gone missing.
    undeclared = json.loads(json.dumps(page_registry(page)))
    del undeclared["lf-suggestion"]["x-inline"]
    assert [
        box
        for box in render_checks_model.evaluate_probe(page, "tinyBoxes", undeclared)
        if box["tag"] == "lf-suggestion"
    ], (
        "with x-inline stripped the gate stays quiet, so the floor is gone rather than declared"
    )

    # Flattened, the same chips are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-chip { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = render_checks_model.evaluate_probe(
        page, "tinyBoxes", page_registry(page)
    )
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-chip"], (
        "a chip with no height left reports nothing, so the floor is gone rather than declared"
    )
    assert rendering_model.render_version(browser, url) == []


def test_check_render_refuses_what_only_a_browser_can_see(serve):
    """`version check --render` end to end, as the agent runs it: the static lint
    passes both sources, and only one renders clean. The broken source is deliberately
    unstamped — refusing it before `version stamp` names it is the gate's whole job,
    so the preview server has to expose the exact candidate without activating it."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*args):
        return subprocess.run(
            [
                sys.executable,
                str(INTERACT_SCRIPT),
                "version",
                "check",
                str(d),
                "--render",
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
        )

    ok = gate()
    assert ok.returncode == 0, ok.stderr
    assert "renders clean" in ok.stdout

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "index.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate()
    assert broken.returncode == 1
    assert "scrolls sideways" in broken.stderr


def test_an_installed_payload_passes_its_real_browser_gate(tmp_path):
    """Exercise the copied artifact a host installs, never an import from this checkout."""
    root = Path(__file__).parent.parent
    installed = tmp_path / "host" / "plugins" / "leaf"
    shutil.copytree(root / "plugins" / "leaf", installed)
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    (page_dir / "index.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(EXAMPLE_MEDIA, page_dir / "media", dirs_exist_ok=True)
    stamp = subprocess.run(
        [
            launcher,
            "version",
            "stamp",
            page_dir,
            "--text",
            "installed-payload smoke",
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert stamp.returncode == 0, stamp.stderr

    rendered = subprocess.run(
        [launcher, "version", "check", page_dir, "--render"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "renders clean" in rendered.stdout


def test_render_reports_a_word_the_printed_page_loses(browser, serve):
    """A user prints the page, or saves it to PDF for someone who wasn't in the
    loop, and whatever the screen said had better still be there. Ways it isn't, all
    silent: a control that is a statement as well as a thing to press (the pick mark,
    which is the only place a group says which option it carries) and a rule that
    hides page content in print, inside a widget or in plain prose. The gate reads
    the page in both media and reports what the second one drops.

    A control declared an offer is exempt, since paper has nothing to press: the same
    page's pick mark reads "chosen" and goes unreported either way."""
    assert rendering_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "a page whose print rendering keeps its words has nothing to report"
    )

    lost = rendering_model.render_version(browser, serve(PRINT_LOSS_PAGE))
    assert [f for f in lost if f.startswith("[print]")] == [
        (
            '[print] <p id=lede> drops "Where the decision stands, for the recor", '
            "which it says on screen"
        ),
        '[print] <lf-option id=c-bearer> drops "Bearer header", which it says on screen',
        (
            '[print] <lf-option id=c-bearer> drops "Suits the mobile client;\\n  '
            'puts the id w", which it says on screen'
        ),
    ], lost


def test_a_shot_shows_one_frame_and_flips_between_them(browser, serve):
    """The comparison lf-shot makes is a flip: two registered frames in one grid cell,
    one of them showing. What the gate covers on the way past is the rest of the
    widget's bargain — the captions naming each frame are the page's words and stay
    selectable, the switch is chrome and takes no space in the user's reading, and
    a printed copy keeps both frames and both captions.

    The image is the target, so both presses land on one point and the pointer never
    moves: a comparison is many alternations, and the whole worth of a flip is that
    the eye can hold still through them. Pressing the switch instead would assert the
    state swaps while saying nothing about what it costs to swap it."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    assert rendering_model.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    assert shown_frames(page) == ["before"]
    at = flip_point(page)
    page.mouse.click(*at)
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    page.mouse.click(*at)
    expect(page.locator('.lf-shotframe[data-lf-state="before"]')).to_be_visible()
    assert shown_frames(page) == ["before"]
    # The keyboard's handle, which the label over the image cannot be.
    page.locator("lf-shot input[type=checkbox]").focus()
    page.keyboard.press(" ")
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert errors == []
    page.close()


def test_a_shot_still_flips_with_every_script_removed(browser, serve, tmp_path):
    """Which is the whole reason the control is a checkbox and a label. A copy is the
    rendered DOM with the scripts dropped and every press a handler answered taken out
    with them — the upgrade has already run, so the frames are there, and this switch
    survives that pass because the browser is what works it. A slider would have
    frozen at whatever the reader left it on; `:has(:checked)` is CSS, and the browser
    owns a checkbox's state — label activation included, so the image goes on being
    the target in a file with nothing running.

    Through `version export` rather than a copy the test makes itself, which is what
    puts the widget's bargain in front of the code that could break it: a hand-rolled
    one dropped the script tags and nothing else, so it went on passing however the
    real export treated a control.

    What it pins is no longer that a state serializes. Setting `checked` as a property
    left no attribute behind, so the copy opened with neither frame chosen and both of
    them stacked in the one cell — a fault the frames' own default has since made
    unrepresentable, the after frame being hidden until something checks the box rather
    than until something checks the other box. So the state needs nothing serialized at
    all, and what is left to lose is the gesture: `for` is a reflected attribute where
    `checked` was not, and a copy that dropped it would keep every frame and every word
    and answer no click on the image."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )

    standalone = tmp_path / "standalone.html"
    standalone.write_text(rendering_model.export_page(browser, url, serve.page_dir))
    loose = browser.new_page(viewport={"width": 1200, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    assert shown_frames(loose) == ["before"]
    loose.mouse.click(*flip_point(loose))
    assert shown_frames(loose) == ["after"]
    loose.close()


def test_a_shot_refuses_a_pair_shot_at_two_widths(browser, serve):
    """Both frames render at the frame's width, so a pair captured at two viewports is
    scaled by two different factors and every line in it lands somewhere new — the flip
    then reports that the whole page changed, convincingly and with nothing on screen
    to say otherwise. The one failure worth an error box rather than a caveat."""
    narrow = solid_png(400, 300, (235, 215, 205))
    page_html = SHOT_PAGE.replace(
        SHOT_SRC["after"], f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    )
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    url = serve(
        page_html,
        media={SHOT_SRC["before"]: SHOTS["before"], narrow_src: narrow},
    )

    assert [
        f
        for f in rendering_model.render_version(browser, url)
        if "600px" in f and "400px" in f
    ], "the gate has to hear about a mismatch, since nobody else will"


def test_render_reports_words_a_widget_puts_out_of_reach(browser, serve):
    """The user's half of the gate. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported here.

    The second one no marker can fix, which is why it reads differently: a word inside a
    form control is unselectable in every engine, so a widget that reaches for <button>
    has put its label somewhere the user cannot go. `offer` builds a press as a span
    for exactly this reason, and this is what says so when a widget doesn't use it."""
    assert rendering_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "the same page without the two mistakes has nothing to report"
    )

    def put_native_link(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const link = document.createElement('a');
              link.className = 'lf-ui';
              link.href = '#h';
              link.textContent = 'Read context';
              document.getElementById('c-lax').prepend(link);
            }, {once: true});"""
        )

    assert (
        rendering_model.render_version(
            primed(browser, put_native_link), serve(CARRIED_PAGE)
        )
        == []
    ), "a native link's words label its browser-owned control rather than the page"

    def put_words_out_of_reach(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const option = document.getElementById('c-lax');
              const row = document.createElement('div');
              row.className = 'lf-ui';
              row.innerHTML = '<strong>Session cookies</strong>';
              const button = document.createElement('button');
              button.setAttribute('data-lf-said', '');
              button.textContent = 'Lax, host-only';
              option.prepend(row, button);
            }, {once: true});"""
        )

    found = rendering_model.render_version(
        primed(browser, put_words_out_of_reach), serve(CARRIED_PAGE)
    )
    assert sorted({f.split("] ", 1)[1] for f in found}) == [
        (
            '<lf-option id=c-lax> puts "Session cookies" under .lf-ui, where no comment '
            "can reach it"
        ),
        (
            '<lf-option id=c-lax> says "Lax, host-only" inside a form control, where no '
            "selection can reach it"
        ),
    ], found


def test_render_reports_a_painted_fact_whose_word_was_drawn_nowhere(browser, serve):
    """The x-paints half of the same gate, and the line it draws between two silences.

    A widget may paint a fact — `recommended` is a corner mark and no text node —
    and it owes a reader who is listening the same fact in words. The runtime
    writes that word, so what is left to check is whether anything drew it. Asking
    is asking for a box, and only an element that is being laid out has one to give:
    a disclosure nobody opened, a tab nobody switched to and a shut comment panel
    all lay out nothing, and their emptiness is the ancestor's answer rather than
    the widget's.

    So the two silences part here, and this holds one of them: a word drawn nowhere
    on a page that is on screen is reported, and the same widget behind a fold is
    not, there being nothing to measure and the fold being the reader's to open.
    That exemption is what lets a widget riding a message out, in
    `test_render_leaves_a_widget_riding_a_reply_out_of_that_reading`.

    The other silence — a word the runtime never wrote, which is a fault wherever
    the element stands — no fixture can stage: `quietFacts` returns the attribute's
    own value or its name, so a declared paint always gets its word, and the branch
    is reachable only by a regression in `renderQuiet` itself. What holds it is the
    corpus with that regression put back: silence `renderQuiet` and every painted
    option in the examples is reported, a `parallel-workstreams` option in a tab
    nobody opened among them. Skipping the unrendered element before asking whether
    a word exists is what drops that one, so the order of the two questions here is
    the contract, and this test does not pin it."""
    found = [
        f.split("] ", 1)[1]
        for f in rendering_model.render_version(browser, serve(PAINTED_IN_SILENCE_PAGE))
    ]
    assert sorted(set(found)) == [
        (
            '<lf-option id=p-seen> paints recommended="" and says nothing a reader '
            "listening can hear"
        )
    ], found


def test_render_reads_a_reply_widgets_own_chrome_and_not_the_panel_around_it(
    browser, serve, tmp_path, monkeypatch
):
    """The same reading, asked where the nesting turns over.

    A widget's chrome is a `.lf-ui` the widget put inside itself. A widget in a
    message is the other way up: the runtime's own layer is above it and the
    widget has none of its own, so every word it holds sits under a `.lf-ui`
    with nothing wrong. Asking whether the *words* stand in a widget cannot tell
    those apart and accuses the second. Asking whose the `.lf-ui` is can.

    Both halves, because either alone is half a claim. One reply carries three
    widgets: a question, an exhibit beside it, and a badge whose module injects
    unmarked words under the chrome face. The panel around all three says
    nothing; the badge's own chrome is read exactly as it would be on a page.

    Nothing here had ever been rendered. No example shipped a widget in its log
    until one did, and every fixture that put one in a reply asked about the
    panel rather than about the gate — while the gate walks text nodes rather
    than boxes, so it had been reading the panel all along with the panel shut.
    It would have refused the first page that carried a question in a reply,
    which is a shape the vocabulary describes and `leaf reply --markup` posts."""
    monkeypatch.chdir(tmp_path)
    package = author_test_widget(tmp_path, "lf-badge", upgrade=True)
    module = package / "widgets" / "lf-badge.js"
    module.write_text(
        module.read_text().replace(
            "      if (!once(this)) return;",
            "      if (!once(this)) return;\n" + BADGE_CHROME,
        )
    )

    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    found = sorted(
        {f.split("] ", 1)[1] for f in rendering_model.render_version(browser, url)}
    )
    assert found == [
        (
            '<lf-badge id=rp-badge> puts "Sent by the reviewer" under .lf-ui, where no '
            "comment can reach it"
        )
    ], found


def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it finds the script from its location rather than the cwd,
    and on `--render` it supplies the Playwright the PEP 723 header deliberately
    omits. Running it from an unrelated directory exercises both.

    The version under it carries a mermaid body that doesn't parse — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and the browser half is what sees
    the error box, which is why the gate is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir
    assert (
        CliRunner().invoke(cli_model.cli, ["version", "check", str(d)]).exit_code == 0
    )

    shim = Path(__file__).parent.parent / "plugins" / "leaf" / "bin" / "leaf"
    run = subprocess.run(
        [str(shim), "version", "check", str(d), "--render"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
    assert "failed soft" in run.stderr and "Parse error" in run.stderr


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
# until a key opens them, so the Tab order alone never reaches one: twelve of the
# layer's ring rules stood in that position when this was written.
RING_SCOPES = (
    ("the page", ()),
    ("the comments", ("c",)),
    ("the asks tray", ("a",)),
    ("the leaves tray", ("l",)),
    # The menu's own walk after the key that opens it: an open lands on the version being
    # read, which is the last row, and the comparison press beside a row is a Tab forward
    # from the row above it. The walk is clamped, so a second press at the top moves
    # nothing and the pair covers a menu of any length this corpus can hold.
    ("the versions menu", ("v", "ArrowUp", "ArrowUp")),
    ("the reference", ("?",)),
    ("design mode", ("i",)),
)
# What each scope has to have opened before its walk means anything, and what the page
# shows while the key that opens it is live. A key with nothing to show is dead by
# declaration — `a` on a page waiting on nobody, `l` where the machine has one leaf — so
# the surface is asked for only where the page is offering it, and the corpus answers for
# the rest. Without this a key that stops working leaves the walk re-walking the page and
# contributing nothing, which the coverage floor catches only where that scope is a
# rule's sole home: one guard over seven setup steps. The page and the comments raise no
# surface of their own; `c` lands on the list, which the walk's own first stop reads.
RING_SCOPE_SURFACE = {
    "the asks tray": (".lf-asks-panel.open", ".lf-asks"),
    "the leaves tray": (".lf-others-panel.open", ".lf-others"),
    "the versions menu": (".lf-version-menu.open", None),
    "the reference": (".lf-help.open", None),
    "design mode": ("body.lf-design", None),
}
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
    """The invariant asked of the whole layer and the whole corpus at once. Neither half
    is evidence without the other: a clean walk says nothing about a rule it never met,
    and a rule the walk met says nothing if the reading excused every side of it.

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
    for example in EXAMPLES:
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

        for scope, keys in RING_SCOPES:
            # Three rungs, because a scope can be three deep: a menu or narrowing inside
            # the panel, then the panel, then the page. The panel is reopened below, so
            # every scope starts from the same page.
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
            for key in keys:
                page.keyboard.press(key)
            page_at_rest(page)
            surface, offers = RING_SCOPE_SURFACE.get(scope, (None, None))
            if surface and (offers is None or page.locator(offers).is_visible()):
                assert page.locator(surface).count() == 1, (
                    f"{' '.join(keys)} did not open {scope} on {example.stem}, which "
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
    # Corpus-wide, because a scope can be dead on a page with nothing to put in it. What
    # cannot happen is a scope no example in the corpus ever opens or walks: then its
    # keys are unread and everything below is silent about the controls behind them.
    missing = [s for s in RING_SCOPE_SURFACE if s not in opened] + [
        f"{s} (walked nothing)" for s, _ in RING_SCOPES if s not in walked_in
    ]
    assert not missing, "no example in the corpus reached " + ", ".join(sorted(missing))
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
