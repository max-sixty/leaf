"""The page's keys: control keys activating once, global shortcuts leaving browser keys
alone, the reading keys' steps, and the comparison's one door."""

import re

import pytest
from leaf_dev.browser import slow_cpu
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_navigation import KEYS_PAGE, SMOOTH_LONG_PAGE, _publish
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    available_commands,
    compare_with,
    draft_control,
    open_page,
    round_trip,
)

from leaf import event_log as events_model

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
            host: {outline: hs.outlineStyle, width: parseFloat(hs.outlineWidth),
              offset: hs.outlineOffset},
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
          const hs = getComputedStyle(host);
          const highlight = document.createElement('i');
          highlight.style.color = 'Highlight';
          host.append(highlight);
          const ink = getComputedStyle(highlight).color;
          highlight.remove();
          return {
            host: [hs.outlineStyle, parseFloat(hs.outlineWidth), hs.outlineOffset],
            ink: hs.outlineColor === ink,
            editor: getComputedStyle(editor).outlineStyle,
          };
        }"""
    )
    assert forced == {
        "host": ["solid", focus_paint["host"]["width"], focus_paint["host"]["offset"]],
        "ink": True,
        "editor": "none",
    }, "forced colors keep the draft's ring where it stands, in Highlight"
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
    control proving the capture observer sees a key the dispatcher intentionally
    consumes. Observe the navigation keys in bubble, after focused content has had
    a chance to cancel them."""
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
            if (event.key === "?") window.lfObservedKeys["?"] = event.defaultPrevented;
          }, {capture: true});
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key) && event.key !== "?")
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
    slow_cpu(page, 20)
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
    versions = page.locator('.lf-fp-menu[data-level="versions"]')
    # No key anywhere on the page marks changes: none of the commands the dispatcher
    # would run names `=`.
    assert not [
        command for command, keys in available_commands(page).items() if "=" in keys
    ]
    page.keyboard.press("=")
    expect(versions).to_be_hidden()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(versions).to_be_visible()
    page.keyboard.press("Escape")
    expect(versions).to_be_hidden()

    # The door, and it marks the same passage the key used to.
    compare_with(page)
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))
