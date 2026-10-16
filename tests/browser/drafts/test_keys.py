"""The page's keys: control keys activating once, global shortcuts leaving browser keys
alone, the reading keys' steps and regions, and the comparison menu."""

import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_navigation import KEYS_PAGE, SMOOTH_LONG_PAGE, _publish
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    compare_with,
    draft_control,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_registered_control_keys_activate_once(browser, serve):
    """A native draft button activates without a Leaf binding. The selectable option
    mark is the explicit exception and owns its Space row.

    Activation happens once per press however long the key is held. A keydown listener
    hears repeats, and a mark that toggles per repeat posts a `choose` for each one. Repeats
    are dispatched rather than driven because no automation holds a key down; the browser
    delivers this event with `repeat` set."""
    page = open_page(browser, serve(KEYS_PAGE))

    pencil = draft_control(page, "edit", "draft-ops")
    assert pencil.evaluate("el => el.localName") == "button"
    expect(pencil).to_have_attribute("type", "button")
    pencil.focus()
    page.keyboard.press("Enter")
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    focus_paint = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          const hs = getComputedStyle(host), es = getComputedStyle(editor);
          return {
            host: {outline: hs.outlineStyle, width: parseFloat(hs.outlineWidth)},
            editor: {outline: es.outlineStyle, shadow: es.boxShadow},
          };
        }"""
    )
    assert focus_paint["host"]["outline"] != "none"
    assert focus_paint["host"]["width"] >= 2
    assert focus_paint["editor"] == {
        "outline": "none",
        "shadow": "none",
    }, "the draft's one editing surface acquired a second focus box"
    page.emulate_media(forced_colors="active")
    forced = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('leaf-text');
          return {
            host: getComputedStyle(host).outlineStyle,
            editor: getComputedStyle(editor).outlineStyle,
          };
        }"""
    )
    assert forced == {"host": "solid", "editor": "none"}
    page.emulate_media(forced_colors="none")
    page.keyboard.press("Escape")

    mark = page.locator("#opts .lf-pick").first
    mark.focus()
    page.keyboard.press(" ")
    expect(page.locator("#opts > lf-option[chosen]")).to_have_count(1)
    chosen = page.locator("#opts > lf-option[chosen]").get_attribute("id")
    mark.evaluate("""el => {
        for (let i = 0; i < 5; i++)
            el.dispatchEvent(new KeyboardEvent('keydown',
                {key: ' ', repeat: true, bubbles: true, cancelable: true}));
    }""")
    expect(page.locator(f"#{chosen}[chosen]")).to_have_count(1)
    # The mark paints its own press before the post answers, so the DOM leads the log:
    # read the file straight after and the first press's event may not be in it yet,
    # which reads exactly like a press that sent nothing. A press that sent nothing
    # satisfies this too, which is what makes it the right wait for both assertions —
    # the repeats below must add none of their own.
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)
    assert [e for e in sent if e.get("action") == "choose"] != [], (
        "the first press sent nothing, so the repeats below had nothing to duplicate"
    )
    assert len([e for e in sent if e.get("action") == "choose"]) == 1, (
        "a held key sent one decision per repeat"
    )


def test_global_shortcuts_leave_other_browser_navigation_keys_alone(browser, serve):
    """The document-level dispatcher owns a few character key shortcuts, not the
    keyboard. Space, arrows, Home/End, and PageUp/PageDown must still reach the browser
    when focus is in the authored page
    rather than a widget control.

    Observe `defaultPrevented` on real key events instead of asserting that Chrome
    happened to scroll: scrolling depends on viewport and focus geometry, while
    canceling the event is the runtime decision under test. `?` is the positive
    control proving this observer sees a key the dispatcher intentionally consumes."""
    page = open_page(browser, serve(KEYS_PAGE))
    keys = [
        " ",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "?",
    ]
    page.evaluate(
        """keys => {
          const pageContent = document.querySelector("main");
          pageContent.tabIndex = -1;
          pageContent.focus();
          window.lfObservedKeys = {};
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key))
              window.lfObservedKeys[event.key] = event.defaultPrevented;
          });
        }""",
        keys,
    )
    for key in keys:
        page.keyboard.press(key)

    observed = page.evaluate("() => window.lfObservedKeys")
    assert observed.pop("?") is True, (
        "the positive-control shortcut was not consumed, so the probe did not "
        "observe the runtime dispatcher"
    )
    assert observed == dict.fromkeys(keys[:-1], False)


def test_the_browser_pages_the_document_with_space(browser, serve):
    """Space and Shift+Space are ordinary browser paging keys on authored content.

    Leaf does not prescribe a distance or animation. The browser chooses both; the
    contract here is simply that the document moves down and then back up without the
    runtime canceling either key."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.evaluate(RELEASE_FOCUS)

    def press_and_settle(key):
        page.evaluate("""() => {
          window.__lfScrollEnded = false;
          addEventListener('scrollend', () => { window.__lfScrollEnded = true; },
                           {once: true});
        }""")
        page.keyboard.press(key)
        page.wait_for_function("() => window.__lfScrollEnded")
        return page.evaluate("() => document.scrollingElement.scrollTop")

    down = press_and_settle("Space")
    assert down > 0, "the browser did not page the document down"
    up = press_and_settle("Shift+Space")
    assert up < down, "the browser did not page the document back up"


def test_the_reading_keys_accumulate_and_reverse(browser, serve):
    """d/u move 60% of the visible page; j/k take small steps through the same glide.
    The page sets scroll-behavior: smooth on the box, as an authored page may —
    a step whose writes ride that rule instead of stating `instant` never lands.

    Every phase waits on its destination, never on scrollend or a timer: the glide
    writes a frame at a time and Chrome answers each write with a scrollend, so
    "scrolling ended" is a fact about a frame, while the destination is the one
    position a glide approaching it never passes through early. A wrong step then
    reads as the wrong number, which says what happened.

    The second press follows the first with no wait between them, landing inside the
    first glide, so presses have to add up from the goal rather than from wherever
    the glide has got to. Taking the box mid-glide — programmatically, because the
    cancel reads positions and any hand looks the same to it, and this one lands at
    a number the assertion can hold — must stand the step down: the next press
    measures from where the user left the box, not from the goal it dropped, and a
    glide that ignored the taking presses on to that goal and fails both reads.
    Pressing on at the foot moves nothing and banks nothing, so u from there
    is one step back. Both pairs of keys walk the same page in turn, each from its top."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    assert page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight * 3"
    ), "the page is too short for these steps to be told apart"
    # A callback's frame timestamp may predate performance.now() in the key handler.
    # Make that browser timing deterministic: a negative first fraction used to write
    # above the page, get clamped to zero, then cancel the glide as if the user moved.
    page.evaluate(
        """downs => {
      const raf = requestAnimationFrame;
      let stale = false;
      addEventListener('keydown', event => {
        if (downs.includes(event.key)) stale = true;
      }, {capture: true});
      window.requestAnimationFrame = callback => {
        const firstAfterPress = stale;
        stale = false;
        return raf(now => callback(firstAfterPress ? -1 : now));
      };
    }""",
        ["d", "j"],
    )

    for down, up in (("d", "u"), ("j", "k")):
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
        )
        reading_keys_walk(page, down, up)


def reading_keys_walk(page, down, up):
    """Step, double-step, reverse, take the box mid-glide and press past the foot
    with `down` and `up`, from the top of the page."""
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => { const s = getComputedStyle(document.scrollingElement); return ("
            " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
            " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
        )
    )

    def rests_at(act, expected):
        """Position after `act`, awaited at `expected` and handed to the assertion:
        the bounded wait consumes the arrival, and the assert is what speaks when
        the step went somewhere else instead."""
        act()
        try:
            page.wait_for_function(
                "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
                arg=expected,
            )
        except PlaywrightTimeout:
            pass
        return page.evaluate("() => document.scrollingElement.scrollTop")

    assert rests_at(lambda: page.keyboard.press(down), step) == pytest.approx(
        step, abs=1
    )

    def twice():
        page.keyboard.down(down)
        page.keyboard.down(down)  # a held key emits a repeated keydown
        page.keyboard.up(down)

    assert rests_at(twice, step * 3) == pytest.approx(step * 3, abs=1), (
        "the second press measured from the glide in flight, so the two together "
        "moved less than their full distance"
    )
    assert rests_at(lambda: page.keyboard.press(up), step * 2) == pytest.approx(
        step * 2, abs=1
    )

    def taken():
        page.keyboard.press(down)
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 400, behavior: 'instant'})"
        )

    assert rests_at(taken, 400) == pytest.approx(400, abs=1), (
        "the glide pressed on to its goal after the user took the box"
    )
    assert rests_at(lambda: page.keyboard.press(down), 400 + step) == pytest.approx(
        400 + step, abs=1
    ), (
        "the press after the user took the box measured from the goal the taking "
        "had cancelled rather than from where they left it"
    )

    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert rests_at(
        lambda: page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1e9, behavior: 'instant'})"
        ),
        foot,
    ) == pytest.approx(foot, abs=1)
    for _ in range(4):
        page.keyboard.press(down)  # nothing left to move, and nothing banked either
    assert rests_at(lambda: page.keyboard.press(up), foot - step) == pytest.approx(
        foot - step, abs=1
    ), (
        "presses at the foot of the page ran the destination past it, and reversing spent "
        "itself paying that back"
    )


def test_the_reading_page_step_never_paints_behind_where_it_started(browser, serve):
    """The step's own frames, read at real speed from the middle of the page where the
    box clamps nothing: d may not paint the page above where the press found it. A rAF
    tick carries its frame's own start, so a press handled inside a frame already under
    way is stamped after the tick it schedules, and an ease reading that as elapsed time
    walks back out through its own start (stepReading says the rest). At the ends of the box
    that write is one the box clamps, and what the clamp does to the press is a resting
    position the test above reads; in the middle every write lands, the glide arrives
    exactly where it promised, and the user is thrown up to most of a page the wrong
    way on the route — which no resting position can see.

    Whether a press loses that race is the platform's to say, so the window is stated
    rather than run for: a throttled CPU is a longer frame, and a longer frame is a wider
    gap between its start and the press dispatched inside it. Unfloored, this machine
    flicked on one press in ten at its own speed and on eight in ten throttled, where a
    floored clock flicks on none of either. The injection buys the record, not the wait,
    which is still the destination's."""
    page = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 20}
    )
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    start = round(step * 2)
    page.evaluate("""() => {
        window.lfFrames = [];
        const sample = () => {
            window.lfFrames.push(document.scrollingElement.scrollTop);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
    }""")
    for _ in range(5):
        page.evaluate(
            "at => document.scrollingElement.scrollTo({top: at, behavior: 'instant'})",
            start,
        )
        page.wait_for_function(
            "at => document.scrollingElement.scrollTop === at", arg=start
        )
        page.evaluate("() => (window.lfFrames = [])")
        page.keyboard.press("d")
        page.wait_for_function(
            "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
            arg=start + step,
        )
        assert min(page.evaluate("() => window.lfFrames")) >= start - 1, (
            "the step painted the page above where the press found it"
        )


def test_the_reading_keys_jump_under_reduced_motion(browser, serve):
    """Both reading distances jump immediately under reduced motion."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(browser, serve(SMOOTH_LONG_PAGE), context=context)
    for down, up in (("d", "u"), ("j", "k")):
        step = (
            60
            if down == "j"
            else page.evaluate(
                "() => { const s = getComputedStyle(document.scrollingElement); return ("
                " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
                " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
            )
        )
        page.keyboard.press(down)
        assert page.evaluate(
            "() => document.scrollingElement.scrollTop"
        ) == pytest.approx(step, abs=1), (
            down,
            "the step had not reached its destination when the press returned",
        )
        page.keyboard.press(up)
        assert page.evaluate(
            "() => document.scrollingElement.scrollTop"
        ) == pytest.approx(0, abs=1), up


def test_the_reading_page_keys_move_the_region_the_user_is_scrolling(browser, serve):
    """Two scroll regions, so d has to pick the one the user is looking at. Beside the
    page the panel is a column of its own and the keys are the document's. Under the
    breakpoint the sheet covers the page and the page hands scrolling over with it — one
    gesture moves one region, and while the sheet is up that region is its thread list.
    A key is no different from a wheel there: a page scrolling behind the sheet shows
    the user nothing, so the key reads as dead, and the document is somewhere else
    when the sheet closes."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Put the user on the page before asking which reading region the page gesture chooses.
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    def press_down():
        """Both offsets once a region answers the press — the glide's first write is
        already the answer to which region moved, and movement is the fact waited on
        because movement is the question. Scrollend was the wait here while a press
        could die outright, which read as the platform withholding the event; it
        withholds nothing, answering the step's frame-at-a-time writes seven times to
        the press on Linux, and a press that moves no region states neither fact.
        Waiting on whichever region speaks makes the wrong one answering two numbers
        to compare rather than half a minute of silence and a timeout."""
        was = offsets()
        page.keyboard.press("d")
        page.wait_for_function(
            "w => { const t = document.querySelector('.lf-threads');"
            " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
            arg=was,
        )
        return was, offsets()

    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert threads_now == threads_was, "the panel took a key aimed at the document"
    assert page_now > page_was, "the document did not move for a key of its own"
    scroll_settled(page)

    resized(page, 400, 600)
    panel_settled(page)
    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert page_now == page_was, (
        "the page moved behind the covering sheet, where the user cannot see it"
    )
    assert threads_now > threads_was, "the sheet did not move for the key it now owns"


def test_the_reading_page_keys_follow_the_user_into_the_panel(browser, serve):
    """Which region the keys move is where the user is standing, and covering is only
    one of the two ways they come to be standing in the list. Beside the page — the wide
    window, where the page beside the panel stays live — a user working down a long
    thread presses d and the page behind them steps instead, which is the same
    nothing the covering case was written to prevent: the region they are reading does
    not move, and the document is somewhere else when they look back at it.

    One factor separates the two halves here. The window, the layout, the panel and the
    list are the same at both presses; only where the focus stands changes. So the first
    press is the control that says the layout is beside — the user stands on the page,
    outside the panel, and the document is theirs to step — and the second is the subject.
    The Go-to sequence then supplies the neighboring
    contrast: focus changes which region d/u page through, but `g g` still names the
    document's edge while both regions have somewhere observable to move."""
    page = open_page(browser, serve(LONG_PAGE, comments=40))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate(RELEASE_FOCUS)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    # The control, and the wait that makes the subject's baseline a resting one: the
    # document's own step is a glide, and the position it is going to is the one place
    # it does not pass through early (the reading-page test says the rest).
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
        arg=step,
    )
    page_now, threads_now = offsets()
    assert page_now > page_was, (
        "the document did not move for a key pressed from outside the panel, so the "
        "panel is not beside the page here and the case below is not the one named"
    )
    assert threads_now == threads_was, "the panel took a key aimed at the document"

    # Into the panel, standing on its open thread's title rather than in a box — `g T`'s
    # landing, which travels nothing, so the baseline below is the one the control left.
    # The address toggles the panel it names, so from the open one the first
    # completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(
        page.locator(
            ".lf-threads > .lf-thread:not([hidden])[open] > .lf-thread-summary"
        )
    ).to_be_focused()
    # Focus lands as the panel starts its slide in, while the list still stands past the
    # window's edge; a step there has nothing shown to move.
    panel_settled(page)

    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
        arg=[page_was, threads_was],
    )
    thread_step = page.locator(".lf-threads").evaluate(
        "t => { const s = getComputedStyle(t); return (t.clientHeight"
        " - parseFloat(s.scrollPaddingTop) - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return Math.abs(t.scrollTop - w[0]) < 1"
        " || Math.abs(document.scrollingElement.scrollTop - w[1]) >= 1; }",
        arg=[thread_step, page_was],
    )
    page_now, threads_now = offsets()
    assert threads_now > threads_was, (
        "the list the user is standing in did not move for the key they pressed"
    )
    assert page_now == pytest.approx(page_was, abs=1), (
        "the page stepped behind a user who was working down the comment list"
    )

    # Both regions now stand away from their top edge. A correct g g returns the page;
    # the shared-scroller regression returns the panel instead. Wait for either answer so
    # the failure reports both offsets rather than timing out while expecting only one.
    assert page_now > 0 and threads_now > 0
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function(
        "() => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop < 1 || t.scrollTop < 1; }",
    )
    edge_page, edge_threads = offsets()
    assert edge_page == pytest.approx(0, abs=1), (
        f"g g left the page at {edge_page} and moved the panel to {edge_threads}"
    )
    assert edge_threads == pytest.approx(threads_now, abs=1), (
        f"g g moved the panel from {threads_now} to {edge_threads}"
    )


def test_the_page_has_one_door_to_a_comparison(browser, serve):
    """`=` marked what changed since the previous version from anywhere on the page, and
    the case for it was that it named no version — "since the last one I saw" is a
    question a user has without opening anything. Naming no version is also naming
    nothing to check, and the two are not the same question: on a page that ships a
    version whenever the work moves, a user back after a week got v(n-1) and no way to
    see that they had. So the door is the menu, where every base says which one it is.

    Pressed rather than read off the table, on both sides: a key bound to nothing looks
    exactly like one that works in the command reference dialog, which is how the removal would go
    unnoticed here and the marks would go unnoticed on the page."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    line = page.locator(".lf-shortcut-bar")
    # The door is a go-to destination rather than a bare letter, so the line names it
    # once the sequence is armed. The word that must not be anywhere is read behind that
    # arrival, so the absence is taken off a line the press has already repainted.
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    expect(line).not_to_contain_text("mark changes")
    page.keyboard.press("Escape")
    page.keyboard.press("=")
    expect(page.locator(".lf-version-menu")).to_be_hidden()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    page.keyboard.press("Shift+v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.keyboard.press("Escape")

    # The door, and it marks the same passage the key used to.
    compare_with(page)
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))
