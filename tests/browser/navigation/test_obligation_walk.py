"""The obligation walk with `m`: where it lands, how it reveals an obligation in tabs and scrollers,
and an obligation's digits and thread."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    answered_comment,
    live_url,
    panel_comment,
    serve_obligations,
)
from render_cases_layout import MARK, SHOT_SRC, SHOTS
from render_cases_navigation import (
    BINDING_BADGE_PAGE,
    CLIPPED_BY,
    INSIDE_ITS_OPTION,
    NOTED_PAGE,
    OVER_WORDS,
)
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    expect_obligations_answered,
    gesture_writes,
    held_frames,
    leaf_page,
    open_page,
    open_threads,
    pane_scroll_behavior,
    panel_field,
    panel_settled,
    regions_side_by_side,
    reported_browser_errors,
    resized,
    round_trip,
    scroll_settled,
    sending,
    suggestion_control,
)

from browser.navigation import expect_walk_position, walk_position
from browser.threads import open_panel_thread
from leaf.agents import thread as thread_model
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed

# The margin card a thread about a passage opens in.
CARD = ".lf-margin-preview"


@pytest.mark.parametrize(("nested_source", "reduced"), [(False, True), (True, False)])
def test_an_obligation_walk_glides_within_a_view_and_opens_other_tabs_at_the_question(
    browser, serve, reduced, nested_source
):
    """A disclosure extends one reading; a mutually exclusive tab opens at its question.

    Capture frames rather than just scroll events: a new panel must already show the
    question in its first painted frame, not appear elsewhere and glide afterwards.
    """

    def question(name):
        options = (
            f'<lf-options id="choice-{name}">'
            f'<lf-option id="yes-{name}">Yes</lf-option>'
            f'<lf-option id="no-{name}">No</lf-option></lf-options>'
        )
        if name == "first" and nested_source:
            options = (
                '<lf-tabs id="source-views"><lf-tab id="source-context" label="Context">'
                "<p>The evidence precedes the decision.</p></lf-tab>"
                '<lf-tab id="source-answer" label="Answer">'
                + options
                + "</lf-tab></lf-tabs>"
            )
        return f'<lf-group id="ask-{name}" label="Choose {name}?"><h2 id="ask-{name}-h">Choose {name}?</h2>{options}</lf-group>'

    first = question("first")
    if not nested_source:
        first = (
            '<details id="question-fold"><summary>First proposal</summary>'
            + first
            + "</details>"
        )
    source = leaf_page(
        "Ask travel across tabs",
        '<h1>Review the two proposals</h1><lf-tabs id="views" flow="page">'
        '<lf-tab id="first" label="First">'
        '<div style="height: 1800px"></div>'
        + first
        + '<div style="height: 1000px"></div></lf-tab>'
        '<lf-tab id="second" label="Second">'
        + question("second")
        + '<div style="height: 3800px"></div></lf-tab></lf-tabs>',
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")

    def landing_top(target):
        return page.locator(f"#ask-{target}").evaluate("""ask =>
          parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) +
          parseFloat(getComputedStyle(ask).scrollMarginTop)
        """)

    def start_trace():
        page.evaluate("""() => {
          window.obligationFrames = [];
          window.obligationTabCues = [];
          const record = () => {
            const tab = document.querySelector('#views > .lf-tabstrip [aria-selected="true"]');
            const selected = tab.getAttribute('aria-controls');
            const ask = document.getElementById(`ask-${selected}`);
            const source = document.querySelector('#source-views [aria-selected="true"]');
            obligationFrames.push({selected, scroll: scrollY,
                           source: source?.getAttribute('aria-controls'),
                           top: ask.getBoundingClientRect().top});
            window.obligationFrame = requestAnimationFrame(record);
          };
          window.obligationFrame = requestAnimationFrame(record);
          window.obligationTabObserver = new MutationObserver(records => {
            for (const {target} of records) {
              if (target.getAttribute('aria-selected') === 'true' &&
                  target.closest('lf-tabs').id === 'views') {
                const name = target.querySelector('.lf-tab-name');
                obligationTabCues.push(name.getAnimations().length);
              }
            }
          });
          obligationTabObserver.observe(document.querySelector('#views'), {
            subtree: true, attributes: true, attributeFilter: ['aria-selected']
          });
        }""")

    def finish_trace():
        return page.evaluate("""() => {
          cancelAnimationFrame(obligationFrame);
          obligationTabObserver.disconnect();
          return {frames: obligationFrames, cues: obligationTabCues};
        }""")

    # The obligation's source may switch an inner view even when its outer wrapper stays.
    # A disclosure, by contrast, extends the current view and preserves its glide.
    if nested_source:
        expect(
            page.locator('#source-views [aria-controls="source-context"]')
        ).to_have_attribute("aria-selected", "true")
    else:
        expect(page.locator("#question-fold")).not_to_have_attribute("open", "")
    before = page.evaluate("scrollY")
    start_trace()
    page.keyboard.press("m")
    expect(page.locator("#ask-first")).to_be_focused()
    if nested_source:
        expect(
            page.locator('#source-views [aria-controls="source-answer"]')
        ).to_have_attribute("aria-selected", "true")
    else:
        expect(page.locator("#question-fold")).to_have_attribute("open", "")
    expect(
        page.locator('#views > .lf-tabstrip [aria-controls="first"]')
    ).to_have_attribute("aria-selected", "true")
    scroll_settled(page)
    after = page.evaluate("scrollY")
    trace = finish_trace()
    assert after - before > 1000, (before, after)
    intermediate = [
        frame for frame in trace["frames"] if before + 50 < frame["scroll"] < after - 50
    ]
    assert bool(intermediate) == (not reduced and not nested_source), trace
    assert trace["cues"] == [], trace
    if nested_source:
        edge = landing_top("first")
        arrived = [
            frame for frame in trace["frames"] if frame["source"] == "source-answer"
        ]
        assert arrived, trace
        assert all(abs(frame["top"] - edge) <= 3 for frame in arrived), trace

    for key, target, tab in [("m", "second", "Second"), ("Shift+m", "first", "First")]:
        before = page.evaluate("scrollY")
        start_trace()
        page.keyboard.press(key)
        expect(page.locator(f"#ask-{target}")).to_be_focused()
        selected = page.locator("#views > .lf-tabstrip").get_by_role(
            "tab", name=tab, exact=True
        )
        expect(selected).to_have_attribute("aria-selected", "true")
        scroll_settled(page)
        after = page.evaluate("scrollY")
        trace = finish_trace()
        assert abs(after - before) > 1000, (before, after)
        edge = landing_top(target)
        arrived = [frame for frame in trace["frames"] if frame["selected"] == target]
        assert arrived, trace
        assert all(abs(frame["top"] - edge) <= 3 for frame in arrived), trace
        assert trace["cues"] == [0 if reduced else 1], trace
        top = page.locator(f"#ask-{target}").bounding_box()["y"]
        assert top == pytest.approx(edge, abs=3), (top, edge)

    # Leave the previous arrival entirely: the next navigation step must preserve this reading
    # as its own Back destination, including the tab that owned the outgoing offset.
    page.mouse.move(400, 400)
    page.mouse.wheel(0, 1100)
    expect(page.locator("#ask-first")).not_to_be_in_viewport()
    scroll_settled(page)
    reading = page.evaluate("scrollY")
    page.keyboard.press("m")
    expect(page.locator("#ask-second")).to_be_focused()
    scroll_settled(page)
    page.go_back()
    page.wait_for_function("navigation.transition === null")
    returned = page.evaluate("""() => ({
      scroll: scrollY, fragment: location.hash,
      selected: document.querySelector('#views > .lf-tabstrip [aria-selected="true"]')
        .getAttribute('aria-controls')
    })""")
    assert returned["selected"] == "first", {"reading": reading, "returned": returned}
    assert returned["scroll"] == pytest.approx(reading, abs=2), returned


def test_an_obligation_walk_reveals_the_owning_regions_horizontal_destination(
    browser, serve
):
    """Arrival keeps horizontal inspection reachable without snapping document Y."""
    source = leaf_page(
        "Ask in horizontal inspection",
        '<h1>Inspect the wide proposal</h1><div id="inspection" data-bound="start" '
        'style="width:220px; height:280px; overflow:auto">'
        '<div style="width:1600px; padding-left:900px; box-sizing:border-box">'
        '<lf-group id="wide-ask" label="Choose the wider plan?"><h2 id="wide-ask-h">Choose the wider plan?</h2>'
        '<lf-options id="wide-choice">'
        '<lf-option id="wide-yes">Yes</lf-option>'
        '<lf-option id="wide-no">No</lf-option></lf-options></lf-group>'
        "</div></div>",
    )
    page = open_page(browser, serve(source))
    inspection = page.locator("#inspection")
    assert inspection.evaluate("el => el.scrollLeft") == 0
    page.keyboard.press("m")
    expect(page.locator("#wide-ask")).to_be_focused()
    scroll_settled(page, "#inspection", axis="x")
    assert inspection.evaluate("el => el.scrollLeft") > 500
    visible = page.locator("#wide-ask").evaluate("""ask => {
      const box = ask.closest('#inspection').getBoundingClientRect();
      const target = ask.getBoundingClientRect();
      return target.left >= box.left && target.left < box.right;
    }""")
    assert visible


@pytest.mark.parametrize("clipped", [False, True])
def test_an_obligation_walk_reveals_its_scrollport_before_aligning_outside_context(
    browser, serve, clipped
):
    """Context above a bounded inspection never leaves its obligation clipped inside it."""
    source = leaf_page(
        "Ask with outside context",
        '<h1 id="context">Review the proposed edit</h1>'
        '<div id="inspection" data-bound="start" '
        'style="height:180px; overflow:auto">'
        '<div style="height:270px"></div>'
        '<p id="edit-context">The proposed amount is '
        '<lf-suggestion id="edit"><lf-old>ten</lf-old>'
        "<lf-new>twelve</lf-new></lf-suggestion>.</p>"
        '<div style="height:300px"></div></div>',
    )
    page = open_page(browser, serve(source))
    if clipped:
        page.locator("#inspection").evaluate("""box => {
          const ask = box.querySelector('#edit').getBoundingClientRect();
          box.scrollTop += ask.top - box.getBoundingClientRect().top + ask.height / 2;
        }""")
    page.keyboard.press("m")
    expect(page.locator("#edit")).to_be_focused()
    scroll_settled(page, "#inspection")
    scroll_settled(page)
    visible = page.locator("#edit").evaluate("""ask => {
      const box = ask.closest('#inspection').getBoundingClientRect();
      const target = ask.getBoundingClientRect();
      return {top: target.top, bottom: target.bottom, low: box.top, high: box.bottom};
    }""")
    assert visible["top"] >= visible["low"], visible
    assert visible["bottom"] <= visible["high"], visible


def test_keys_answer_an_obligation_from_its_marks(browser, serve):
    """The obligation's digits stay live while a mark adds only its control-local keys.

    One Tab enters the marks, where ↑/↓ walk the options and clamp at the ends, and
    Home and End reach them.
    Moving focus does not replace the obligation's numeric action context with a widget copy.
    """
    page = open_page(browser, serve_obligations(serve))
    nums = page.locator("#live-question > lf-option .lf-key-badge")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("m")
    expect_walk_position(page, "1 of 4 waiting on me")
    marks = page.locator("#live-question .lf-pick")
    # The arrival stands on the obligation, which wears its options' digits; the marks
    # are the next Tab stops.
    expect(
        page.locator("#live-question > lf-option .lf-key-badge[data-lf-binding-badge]")
    ).to_have_text(["1", "2"])
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfCheckApi();
          notice('Saved');
          dispatchEvent(new Event('resize'));
        }"""
    )
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )
    expect(
        page.locator("#live-question > lf-option .lf-key-badge[data-lf-binding-badge]")
    ).to_have_text(["1", "2"])
    page.keyboard.press("Tab")
    expect(marks.first).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me")
    expect(
        page.locator("#live-question > lf-option .lf-key-badge[data-lf-binding-badge]")
    ).to_have_text(["1", "2"])
    expect(nums.first).to_be_visible()
    expect(nums.nth(1)).to_have_text("2")
    assert marks.first.get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Home End Space 1"
    )
    assert marks.nth(1).get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Home End Space 2"
    )

    page.keyboard.press("ArrowUp")
    expect(marks.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    # Home and End reach the ends, as in every other list of rows. The options stand
    # whole around the ring, so their steps say no position, and the On Me walk that
    # brought the user here goes on saying theirs.
    page.keyboard.press("Home")
    expect(marks.first).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me")
    page.keyboard.press("End")
    expect(marks.nth(1)).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me")

    with sending(page, "the numbered pick"):
        page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("selected", "")
    # The pick's notice takes the panel's seat for passing words.
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )
    acts = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"value": ["lq-keep"]}


def test_a_failed_obligation_reveal_does_not_register_an_arrival(browser, serve):
    """A rejected reveal neither advances nor marks the existing obligation walk."""
    page = open_page(browser, serve_obligations(serve))
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 4 waiting on me")
    page.evaluate(
        """async () => {
          const {PendingTaskEvent} = await window.__lfLibImport('pending-task.js');
          const source = document.querySelector('#sug-refill');
          // Revealing the suggestion waits for its update, which the test holds.
          source.hidden = 'until-found';
          source.addEventListener('beforematch', () => {
            const {promise: ready, reject} = Promise.withResolvers();
            window.rejectObligationReveal = reject;
            ready.then(() => {}, () => { window.obligationRevealRejected = true; });
            // Said from inside the suggestion, the work is its preparation.
            source.querySelector('lf-new').dispatchEvent(new PendingTaskEvent(ready));
            Object.defineProperty(source, 'updateComplete', {value: ready, configurable: true});
            queueMicrotask(() => delete source.updateComplete);
            window.obligationRevealStarted = true;
          }, {once: true});
        }"""
    )
    page.keyboard.press("m")
    page.wait_for_function("window.obligationRevealStarted === true")
    expect(page.locator("#live-question-decision")).to_be_focused()
    page.evaluate(
        "() => { rejectObligationReveal(new Error('obligation reveal probe')); }"
    )
    page.wait_for_function("window.obligationRevealRejected === true")
    rendered(page)
    assert walk_position(page)["text"] == "1 of 4 waiting on me"
    expect(page.locator("#live-question-decision")).to_be_focused()
    reported_browser_errors(page, "leaf: Presentation failed: obligation reveal probe")
    round_trip(page)


def test_a_delayed_obligation_reveal_yields_to_programmatic_user_focus(browser, serve):
    """A completed old reveal cannot steal accessibility focus or register an arrival."""
    page = open_page(browser, serve_obligations(serve))
    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me")
    page.evaluate(
        """() => {
          const held = new Promise(resolve => { window.releaseObligationReveal = resolve; });
          held.then(() => { window.obligationRevealSettled = true; });
          const source = document.querySelector('#sug-refill');
          // Revealing the suggestion waits for its update, which the test holds.
          source.hidden = 'until-found';
          source.addEventListener('beforematch', () => {
            Object.defineProperty(source, 'updateComplete', {value: held, configurable: true});
            queueMicrotask(() => delete source.updateComplete);
            window.obligationRevealStarted = true;
          }, {once: true});
        }"""
    )

    page.keyboard.press("m")
    page.wait_for_function("window.obligationRevealStarted === true")
    # Assistive technology and focus-management code can move the user without a
    # pointer, key, or input event. The retained navigation must read focus itself.
    page.locator(".lf-fp-leaf").focus()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.evaluate("releaseObligationReveal()")
    page.wait_for_function("window.obligationRevealSettled === true")
    rendered(page)

    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    # The user left the walk, so it says nothing more; it never says the next arrival.
    position = walk_position(page)
    assert (position or {}).get("text") in (None, "1 of 4 waiting on me")


def test_a_selected_tab_enters_the_obligation_it_controls(browser, serve):
    """A controlled panel can itself be an obligation; selecting its tab hasn't entered it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A tab opening an ask",
                '<h1>Decisions</h1><div role="tablist">'
                '<button role="tab" aria-selected="true" aria-controls="second-decision">'
                "Second</button></div>"
                + "".join(
                    f'<lf-group id="{key}-decision" label="Pick {key}"><h2 id="{key}-decision-h">Pick {key}</h2>'
                    f'<lf-options id="{key}"><lf-option id="{key}-a">'
                    "Alpha</lf-option></lf-options></lf-group>"
                    for key in ("first", "second")
                ),
            )
        ),
    )
    page.get_by_role("tab", name="Second").click()
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#first-decision")).to_be_focused()


def test_an_obligations_digits_are_drawn_whole(browser, serve):
    """A binding badge arrives into room its option already holds, and lands on nothing.

    A placement that borrows that room instead shows it. On the cell's outer corner the
    chip would be half outside a group that clips itself, and in a bare-label group the
    first digit a sliver. Out in the page margin beside the group it would be whole and
    in the neighbouring card's prose, because a middle column's margin is another cell.
    Neither shows up as a failure: a clipped element still reports its whole box and
    still answers `to_be_visible`, and a chip drawn over words breaks no rule anybody
    had written.

    So the cell holds a place for it, and this asks the two questions that place
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them. Rows reserve a leading gutter;
    titled cards share their trailing header-state slot with the same obligation-owned binding badge
    that temporarily replaces status.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one number, it is level with one row size and too high at another with
    the gate still green — because what the gate reads is the number the theme states,
    and the claim beside it, that a row's digit is level with its words, is checked by
    nothing.

    How far in it stands is each form's own relation: edge, digit, then prose for a row;
    prose opening, then digit, then edge for a card. The two forms deliberately don't
    claim one rail, while every option within a form still claims one stable seat."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    seats = {"card": {}, "row": {}}
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "card"),
        (["r-now", "r-later"], "row"),
    ]:
        page.keyboard.press("m")
        # The arrival stands on the obligation; the digits are drawn once a mark holds the
        # focus, one Tab in.
        page.keyboard.press("Tab")
        for id_ in options:
            chip = page.locator(f"#{id_} .lf-key-badge")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it, and never in either neighbour's room. Rows put the binding badge in
            # the leading gutter; cards put it in their trailing header-state slot.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            if sitting == "card":
                assert 0 < sits["opens"] < sits["x"] < sits["ends"] < sits["width"], (
                    f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a card whose "
                    f"words open at {sits['opens']} and whose far edge is "
                    f"{sits['width']}, so it is not in the trailing state slot"
                )
                assert round(sits["y"]) == 8, (
                    f"{id_}'s digit sits {sits['y']} down from its option's top, not in "
                    "the card's header-state corner"
                )
            else:
                assert 0 < sits["x"] < sits["ends"] < sits["opens"], (
                    f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a row whose "
                    f"words open at {sits['opens']}, so its leading gutter is holding "
                    "one of the two in the other's room"
                )
                assert abs(sits["level"]) <= 0.5, (
                    f"{id_}'s digit is {sits['level']}px off the middle of its row's own "
                    "words"
                )
            seats[sitting].setdefault(round(sits["x"], 1), []).append(id_)
            assert sits["past"] <= 0, (
                f"{id_}'s digit hangs past its own option and onto the next"
            )
            # Asked of the words rather than of the numbers, because the numbers are
            # only right for as long as the column the theme reserves is.
            on = chip.evaluate(OVER_WORDS, id_)
            assert on is None, f"{id_}'s digit is drawn over the words “{on}”"
    assert all(len(form) == 1 for form in seats.values()), (
        f"the digits move between seats within one form: {seats}"
    )


def test_thread_widget_obligation_walk_orders_by_its_threads_page_passage(
    browser, serve
):
    """A materialized thread source keeps its thread's authored page order."""
    page = open_page(browser, serve(named_source("ship-review")))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    page.locator("h1").focus()
    page.keyboard.press("m")
    expect(page.locator(f"{CARD} lf-group[data-lf-obligation]")).to_be_focused()


def test_an_obligation_walk_leaves_the_card_it_reached_through(browser, serve):
    """`m` from the page reaches an obligation in a reply to a thread about a passage
    through that thread's margin card, which draws the reply's widgets, so the press
    opens the card on the way and leaves the panel shut. Escape puts the card away,
    leaving the user beside the passage."""
    page = open_page(browser, serve(named_source("ship-review")))
    page.keyboard.press("m")
    item = page.locator(f"{CARD} lf-group[data-lf-obligation]")
    expect(item).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(CARD)).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")


def test_an_absent_walk_destination_returns_to_the_callers_fallback(browser, serve):
    """A missing visual destination leaves the caller's announcement path live."""
    url = serve(NOTED_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A page-level thread.",
        },
    )
    page = open_page(browser, url)
    open_threads(page)
    expect(page.locator(".lf-fp-thread")).to_have_count(1)
    page.get_by_role("button", name="Find a thread or message").click()
    page.locator("input.lf-fp-search").fill("no matching thread")
    expect(page.locator(".lf-fp-thread")).to_have_count(0)
    page.get_by_role("button", name="Close search").click()
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.evaluate(RELEASE_FOCUS)
    fallback = page.evaluate(
        """async () => {
          const {beginWalk} = await window.__lfCheckApi();
          return beginWalk('thread', 'Thread', () => null) ?? 'Thread 1 of 1';
        }"""
    )
    assert fallback == "Thread 1 of 1"
    expect_walk_position(page, None)

    page.keyboard.press("t")
    expect(page.locator(".lf-live")).to_contain_text("Thread 1 of 1")


def test_obligations_sharing_context_keep_their_source_identity(browser, serve):
    """Shared prompt context keeps each widget's travel, digits and answer distinct."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Shared Question context",
                '<h1>Shared Question context</h1><lf-group id="shared" label="Choose both releases">'
                '<h2 id="shared-h">Choose both releases</h2>'
                '<lf-options id="first">'
                '<lf-option id="first-a">Alpha</lf-option>'
                '<lf-option id="first-b">Beta</lf-option></lf-options>'
                '<div style="height:1200px">Evidence between decisions</div>'
                '<lf-options id="second">'
                '<lf-option id="second-a">Gamma</lf-option>'
                '<lf-option id="second-b">Delta</lf-option></lf-options></lf-group>',
            )
        ),
    )

    # The widgets' own obligations; a pick also publishes the update's, the version
    # the agent then owes.
    def questions():
        return page.evaluate(
            """async () => (await window.__lfWidgetApi())
              .readObligations().all.filter((item) => item.source.kind === "widget")"""
        )

    initial = questions()
    assert [question["id"] for question in initial] == [
        "widget:first",
        "widget:second",
    ]
    assert [question["prompt"]["target"] for question in initial] == [
        "shared",
        "shared",
    ]
    page.keyboard.press("m")
    expect(page.locator("#first")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#second")).to_be_focused()
    rendered(page)
    assert (
        page.evaluate("""async () => {
      const {heldObligation} = await window.__lfCheckApi();
      return heldObligation()?.id;
    }""")
        == "second"
    )
    scroll_settled(page)
    assert page.locator("#second").bounding_box()["y"] >= 0
    assert (
        page.locator("#second").bounding_box()["y"]
        + page.locator("#second").bounding_box()["height"]
        <= page.locator(".lf-fp-row").bounding_box()["y"]
    )
    expect(page.locator("#second")).to_have_attribute("data-lf-obligation", "1")
    expect(page.locator("#shared")).not_to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("Shift+m")
    expect(page.locator("#first")).to_be_focused()
    page.keyboard.press("1")
    # Whether a pick answers an obligation is the server's reading, which the page
    # applies after the pick's send comes back.
    expect_obligations_answered(page, "1/2")
    first, second = questions()
    assert first["answered"]
    assert first["answer"]["value"] == ["first-a"]
    assert second["answer"] is None
    page.keyboard.press("m")
    expect(page.locator("#second")).to_be_focused()
    page.keyboard.press("2")
    expect_obligations_answered(page, "2/2")
    assert questions()[1]["answer"]["value"] == ["second-b"]
    page.keyboard.press("Escape")
    for source in ("first", "second"):
        assert page.evaluate(
            """async id => (await window.__lfWidgetApi())
              .obligationActions.open('widget:' + id)""",
            source,
        )
        expect(page.locator(f"#{source}")).to_be_focused()


def test_digits_leave_an_obligation_the_user_scrolled_away_from(browser, serve):
    """Focus stays in an ask the user has scrolled off screen, but a key pressed there
    lets go of it first: scrolled away, `2` chooses nothing, and back in view the ask's
    digits stay gone until the user goes to it again, when `2` chooses."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "An ask scrolled away",
                '<h1>An ask scrolled away</h1><lf-group id="route" label="Which route?"><h2 id="route-h">Which route?</h2>'
                '<lf-options id="routes">'
                '<lf-option id="left">Take the left route</lf-option>'
                '<lf-option id="right">Take the right route</lf-option>'
                '</lf-options></lf-group><div style="height:4000px">Reading on</div>',
            )
        ),
    )

    def answer():
        return page.evaluate(
            """async () => (await window.__lfWidgetApi()).readObligations().all
              .find((item) => item.id === "widget:routes").answer?.value ?? null"""
        )

    def scroll(down):
        page.mouse.move(400, 400)
        page.mouse.wheel(0, 3000 if down else -3000)
        page.wait_for_function(
            "(down) => (down ? scrollY > 2000 : scrollY === 0)", arg=down
        )
        scroll_settled(page)

    page.keyboard.press("m")
    page.keyboard.press("Tab")
    digit = page.locator("#right .lf-key-badge")
    expect(digit).to_be_visible()
    scroll(down=True)
    expect(page.locator("#routes")).not_to_be_in_viewport()
    page.keyboard.press("2")
    rendered(page)
    assert answer() is None
    assert page.evaluate(
        "() => !document.getElementById('route').matches(':focus-within')"
    )
    scroll(down=False)
    rendered(page)
    expect(digit).to_be_hidden()
    page.keyboard.press("2")
    rendered(page)
    assert answer() is None
    page.keyboard.press("m")
    page.keyboard.press("Tab")
    expect(digit).to_be_visible()
    with sending(page, "the answer"):
        page.keyboard.press("2")
    assert answer() == ["right"]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_digit_shows_on_its_choice_as_a_scroll_brings_the_choice_into_view(
    engine, request, serve
):
    """With focus on an ask, a choice a scroll brings back into the window wears its
    digit from the frame it enters, while the scroll still moves, as it would once the
    scroll ends (command-hints.js). The choice enters at the window's top, clear of
    the panel's row, and the choice after it keeps the ask in sight meanwhile."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "A long ask",
                '<h1>A long ask</h1><lf-group id="route" label="Which route?"><h2 id="route-h">Which route?</h2>'
                '<lf-options id="routes">'
                '<lf-option id="left">Take the left route<div style="height:1600px"></div></lf-option>'
                '<lf-option id="right">Take the right route</lf-option>'
                '<lf-option id="back">Go back<div style="height:1600px"></div></lf-option>'
                '</lf-options></lf-group><div style="height:4000px">Reading on</div>',
            )
        ),
    )
    page.keyboard.press("m")
    expect(page.locator("#left .lf-key-badge")).to_be_visible()
    gesture_writes(page, 2600)
    expect(page.locator("#right")).not_to_be_in_viewport()
    _, _, samples = gesture_writes(
        page,
        -1200,
        sample="""() => {
          const choice = document.getElementById('right');
          const digit = choice.shadowRoot.querySelector('.lf-key-badge');
          const top = choice.getBoundingClientRect().top;
          return {
            seen: top >= 0 && top < innerHeight / 2,
            worn: Boolean(digit?.checkVisibility({opacityProperty: true}))
              && digit.textContent.trim() === '2',
          };
        }""",
    )
    seen = [sample["read"] for sample in samples if sample["read"]["seen"]]
    assert len(seen) >= 3, samples
    assert all(read["worn"] for read in seen), samples


def test_keys_pressed_while_the_page_moves_act_as_if_it_had_landed(browser, serve):
    """Keys typed while the page still moves add up as if each motion had landed: `m u`
    typed quickly ends where it ends typed slowly, `d m` lands the ask, `m Shift+m`
    returns to the ask `m` set off from, `j m` beside an ask `j` leaves in view
    moves no further than `j`, Back after `m m` returns to where the first `m` lands,
    `d`, or `d d`, pressed while the browser's own PageDown still moves the page, or
    before it has, steps on from where PageDown lands, and `m` pressed then lands where
    it lands alone; PageDown pressed before `d` has moved the page pages on from where
    `d` lands. Each ends where the same keys typed slowly end.
    Home pressed before `d` has moved the page keeps it at the top, though at the top
    Home itself moves nothing."""
    asks = "".join(
        f'<div style="height:3000px">Reading on</div><lf-group id="ask-{index}" label="Which route?">'
        f'<h2 id="ask-{index}-h">Which route?</h2><lf-options id="routes-{index}">'
        f'<lf-option id="left-{index}">Take the left route</lf-option>'
        f'<lf-option id="right-{index}">Take the right route</lf-option>'
        "</lf-options></lf-group>"
        for index in (1, 2)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Two asks far down",
                f'<h1>Two asks far down</h1>{asks}<div style="height:3000px"></div>',
            )
        ),
    )
    first = page.locator("#ask-1")

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    def from_the_top():
        page.evaluate(RELEASE_FOCUS)
        page.evaluate("() => scrollTo({top: 0, behavior: 'instant'})")
        scroll_settled(page)

    page.keyboard.press("m")
    expect(first).to_be_focused()
    landing = settled()
    page.keyboard.press("u")
    paged = settled()

    from_the_top()
    page.keyboard.press("m")
    page.keyboard.press("u")
    assert settled() == pytest.approx(paged, abs=2)

    from_the_top()
    page.keyboard.press("d")
    page.keyboard.press("m")
    expect(first).to_be_focused()
    assert settled() == pytest.approx(landing, abs=2)

    page.keyboard.press("m")
    page.keyboard.press("Shift+m")
    expect(first).to_be_focused()
    assert settled() == pytest.approx(landing, abs=2)

    page.keyboard.press("k")
    page.keyboard.press("k")
    above = settled()
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("j")
    page.keyboard.press("m")
    expect(first).to_be_focused()
    assert settled() == pytest.approx(above + 60, abs=2)

    # The second `m` leaves while the first still glides, so the entry it adds records
    # where the first is headed, not wherever its glide had reached.
    from_the_top()
    page.keyboard.press("m")
    expect(first).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#ask-2")).to_be_focused()
    settled()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    page.wait_for_function("navigation.transition === null")
    expect(first).to_be_focused()
    assert settled() == pytest.approx(landing, abs=2)

    from_the_top()
    page.keyboard.press("PageDown")
    paged_down = settled()
    from_the_top()
    page.keyboard.press("d")
    step = settled()
    # Pressed before PageDown's scroll has moved the page, as a typed pair is: the
    # browser's first scroll event comes a frame or more after the key.
    from_the_top()
    page.keyboard.press("PageDown")
    page.keyboard.press("d")
    assert settled() == pytest.approx(paged_down + step, abs=2)
    from_the_top()
    page.keyboard.press("PageDown")
    page.keyboard.press("d")
    # Two frames of PageDown's scroll between the presses, as a typed pair gets.
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    page.keyboard.press("d")
    assert settled() == pytest.approx(paged_down + 2 * step, abs=2)
    # `m` lands where it lands alone, though no instant write stops PageDown's scroll.
    from_the_top()
    page.keyboard.press("PageDown")
    page.wait_for_function("scrollY > 0")
    page.keyboard.press("m")
    expect(first).to_be_focused()
    assert settled() == pytest.approx(landing, abs=2)
    # The other way round: PageDown pressed before `d` has moved the page pages on from
    # where `d` lands, and a `d` after it still waits for PageDown's scroll.
    from_the_top()
    with held_frames(page):
        page.keyboard.press("d")
        page.keyboard.press("PageDown")
        page.keyboard.press("d")
    assert settled() == pytest.approx(2 * step + paged_down, abs=2)

    from_the_top()
    with held_frames(page):
        page.keyboard.press("d")
        page.keyboard.press("Home")
    rendered(page)
    assert settled() == 0


def test_m_pressed_while_a_glide_carries_asks_past_steps_on_from_where_it_lands(
    browser, serve
):
    """`m` pressed while the page still glides steps on from where the glide lands, as
    it does pressed once the glide has landed: an ask the glide carries through the
    window to end above it is not one the reader sees there."""
    asks = "".join(
        f'<lf-group id="ask-{index}" label="Question {index}">'
        f'<h2 id="ask-{index}-h">Question {index}: which route?</h2>'
        f"<p>Premise {index}, long enough to read as a line of the page.</p>"
        f'<lf-options id="routes-{index}"><lf-option id="left-{index}">Left</lf-option>'
        f'<lf-option id="right-{index}">Right</lf-option></lf-options></lf-group>'
        for index in range(80)
    )
    page = open_page(
        browser, serve(leaf_page("Many asks", f"<h1>Many asks</h1>{asks}"))
    )
    reached = []
    for landed in (False, True):
        page.evaluate(RELEASE_FOCUS)
        page.evaluate(
            "() => document.querySelector('#ask-40-h')"
            ".scrollIntoView({block: 'start', behavior: 'instant'})"
        )
        scroll_settled(page)
        for _ in range(12):
            page.keyboard.press("d")
        if landed:
            scroll_settled(page)
        page.keyboard.press("m")
        scroll_settled(page)
        reached.append(
            page.evaluate("() => document.activeElement?.closest('lf-group')?.id")
        )
    assert reached[0] == reached[1]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_m_pressed_while_the_page_glides_lands_an_ask_in_a_sticky_track_where_it_lands_alone(
    request, serve, engine
):
    """`d m` typed quickly, on a sidebar page whose stuck track holds the ask, ends where
    the same keys typed slowly end: `d`'s glide carries the track up only until it
    sticks, so the ask stands in the window where the glide leaves it and `m` moves the
    page nowhere `d` doesn't. Counted as riding the whole glide, the ask read as leaving
    the window above, and `m` pulled the page back most of the way to the top."""
    paragraphs = "".join(
        f"<p>Body paragraph {n} of the review, long enough to fill a line.</p>"
        for n in range(120)
    )
    source = leaf_page(
        "An ask in the track",
        '<aside id="route"><div class="layout-track" id="track">'
        '<lf-group id="ask" label="Which route?"><h2 id="ask-h">Which route?</h2>'
        '<lf-options id="routes"><lf-option id="left">Take the left route</lf-option>'
        '<lf-option id="right">Take the right route</lf-option></lf-options></lf-group>'
        "<p>Notes beside the ask.</p></div></aside>"
        f'<article class="layout-column"><h1>Release review</h1>{paragraphs}</article>',
        layout="sidebar",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1400, 700)
    ask = page.locator("#ask")
    track_top = "document.getElementById('track').getBoundingClientRect().top"

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    standing = page.evaluate(track_top)
    page.keyboard.press("d")
    paged = settled()
    stuck = page.evaluate(track_top)
    # The track rode the start of `d`'s glide, short of the whole of it.
    assert 1 < standing - stuck < paged, (standing, stuck, paged)
    page.keyboard.press("m")
    expect(ask).to_be_focused()
    assert settled() == pytest.approx(paged, abs=2)

    page.evaluate(RELEASE_FOCUS)
    page.evaluate("() => scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    # `m` pressed before `d`'s glide has moved the page, on any host.
    with held_frames(page) as step:
        page.keyboard.press("d")
        page.keyboard.press("m")
        step()
    expect(ask).to_be_focused()
    assert settled() == pytest.approx(paged, abs=2)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_m_pressed_as_g_g_glides_back_lands_an_ask_its_released_track_carries_down(
    request, serve, engine
):
    """`g g m` typed quickly, on a sidebar page whose stuck track holds the ask just
    above the window's foot, ends where the same keys typed slowly end. `g g`'s glide to
    the top takes the track's own place back past the line it sticks at, so the track
    comes down with the page and carries the ask past the foot, and `m` brings it back.
    Read as staying stuck, the ask stood whole where the glide leaves it, and `m` left
    it under the foot."""
    paragraphs = "".join(
        f"<p>Body paragraph {n} of the review, long enough to fill a line.</p>"
        for n in range(120)
    )
    source = leaf_page(
        "An ask a released track carries",
        '<aside id="route"><div class="layout-track" id="track">'
        '<div id="before" style="height: 300px"></div>'
        '<lf-group id="ask" label="Which route?"><h2 id="ask-h">Which route?</h2>'
        '<lf-options id="routes"><lf-option id="left">Take the left route</lf-option>'
        '<lf-option id="right">Take the right route</lf-option></lf-options></lf-group>'
        "</div></aside>"
        f'<article class="layout-column"><h1>Release review</h1>{paragraphs}</article>',
        layout="sidebar",
    )
    page = open_page(request.getfixturevalue(engine), serve(source))
    resized(page, 1400, 700)
    ask = page.locator("#ask")

    def settled():
        scroll_settled(page)
        return page.evaluate("scrollY")

    def foot_gap():
        """How far the ask's foot stands above the window's, which no chrome covers
        beside the page's column."""
        return page.evaluate(
            "document.documentElement.clientHeight"
            " - document.getElementById('ask').getBoundingClientRect().bottom"
        )

    page.evaluate("() => scrollTo({top: 600, behavior: 'instant'})")
    settled()
    # Stand the ask, in the stuck track, 12px above the window's foot.
    page.evaluate(
        "gap => { const before = document.getElementById('before');"
        " before.style.height = `${before.offsetHeight + gap - 12}px`; }",
        foot_gap(),
    )
    settled()
    assert foot_gap() == pytest.approx(12, abs=1)
    page.keyboard.press("g")
    page.keyboard.press("g")
    assert settled() == 0
    # Released, the track came down past the window's foot with the ask.
    assert foot_gap() < 0
    page.keyboard.press("m")
    expect(ask).to_be_focused()
    slowly = settled()
    assert foot_gap() >= 0

    page.evaluate(RELEASE_FOCUS)
    page.evaluate("() => scrollTo({top: 600, behavior: 'instant'})")
    settled()
    with held_frames(page) as step:
        page.keyboard.press("g")
        page.keyboard.press("g")
        page.keyboard.press("m")
        step()
    expect(ask).to_be_focused()
    assert settled() == pytest.approx(slowly, abs=2)


def test_the_obligation_walk_uses_the_visible_reading_after_its_focus_is_released(
    browser, serve
):
    """Letting go leaves the user at the obligation they left, so the walk returns to
    it, either way; scrolling it away starts the walk where they now read, at the
    obligation there rather than past it."""
    items = "".join(
        f"""
<lf-group id="question-{index}" label="Question {index}: which route should we take?"><h2 id="question-{index}-h">Question {index}: which route should we take?</h2>
<lf-options id="routes-{index}">
  <lf-option id="route-{index}-left">Take the left route</lf-option>
  <lf-option id="route-{index}-right">Take the right route</lf-option>
</lf-options></lf-group>
<div style="height: 1200px"></div>
"""
        for index in range(1, 5)
    )
    page = open_page(
        browser, serve(leaf_page("a resumed ask walk", f"<h1>Routes</h1>{items}"))
    )
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press("m")
    expect(page.locator("#question-1")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#question-2")).to_be_focused()
    for back in ("m", "Shift+m"):
        page.keyboard.press("Escape")
        page.keyboard.press(back)
        expect(page.locator("#question-2")).to_be_focused()
    # Opened by a key, On Me stands on its first row, question 1, and the walk steps on
    # from it.
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("m")
    expect(page.locator("#question-2")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#question-1")).to_be_focused()
    page.keyboard.press("Escape")
    rendered(page)
    assert page.evaluate(
        "() => document.activeElement === document.body && getSelection().focusNode === null"
    )

    third = page.locator("#question-3 h2")
    goal = page.evaluate(
        "() => parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop) + 8"
    )
    page.mouse.move(220, 450)
    page.mouse.wheel(0, third.bounding_box()["y"] - goal)
    page.wait_for_function(
        "([heading, goal]) => Math.abs(heading.getBoundingClientRect().top - goal) < 2",
        arg=[third.element_handle(), goal],
    )
    scroll_settled(page)
    expect(third).to_be_in_viewport()

    page.keyboard.press("m")
    expect(page.locator("#question-3")).to_be_focused()


def test_the_obligation_walk_reaches_a_question_in_view_whatever_its_words(
    browser, serve
):
    """With nothing focused the walk starts from what the window shows, and a question
    on screen ahead of the first paragraph there is where the user is, though its
    options make no paragraph: `m` at the top of a page opening with options alone
    reaches them, and so does `m` with a question's options at the window's top and its
    heading scrolled away above. A question in view in the column beside the one the
    reader's pointer is over is not where they are, as a block there is not."""
    asks = "".join(
        f"""
<lf-group id="ask-{index}" label="Question {index}"><h2 id="ask-{index}-h">Question {index}: which route should we take?</h2>
<p>The premise of question {index}, long enough to read as a line of the page.</p>
<lf-options id="routes-{index}">
  <lf-option id="routes-{index}-left">Take the left route through the valley</lf-option>
  <lf-option id="routes-{index}-right">Take the right route over the ridge</lf-option>
  <lf-option id="routes-{index}-wait">Wait for better weather before choosing</lf-option>
</lf-options></lf-group>
<div style="height: 200px"></div>"""
        for index in range(1, 4)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "a question of options alone",
                f"""<lf-group id="ask-0" label="Question 0"><lf-options id="routes-0">
  <lf-option id="routes-0-left">Take the left route</lf-option>
  <lf-option id="routes-0-right">Take the right route</lf-option>
</lf-options></lf-group>{asks}
<div id="columns" style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem">
<div><lf-group id="beside-ask" label="Beside"><lf-options id="beside-routes">
  <lf-option id="beside-left">Go left beside</lf-option>
  <lf-option id="beside-right">Go right beside</lf-option>
</lf-options></lf-group></div>
<div><p id="read">The words the reader is reading run on in this column, long enough to wrap.</p>
<lf-group id="read-ask" label="Read"><h2 id="read-ask-h">The question in the column read</h2>
<lf-options id="read-routes">
  <lf-option id="read-left">Go left here</lf-option>
  <lf-option id="read-right">Go right here</lf-option>
</lf-options></lf-group></div>
</div><div style="height: 1200px"></div>""",
            )
        ),
    )
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press("m")
    expect(page.locator("#ask-0")).to_be_focused()
    page.keyboard.press("Escape")

    options = page.locator("#routes-2")
    page.mouse.move(220, 450)
    page.mouse.wheel(0, options.bounding_box()["y"] - 40)
    page.wait_for_function(
        "options => Math.abs(options.getBoundingClientRect().top - 40) < 2",
        arg=options.element_handle(),
    )
    scroll_settled(page)
    expect(page.locator("#ask-2-h")).not_to_be_in_viewport()
    expect(page.locator("#ask-3-h")).to_be_in_viewport()
    page.keyboard.press("m")
    expect(page.locator("#ask-2")).to_be_focused()
    page.keyboard.press("Escape")

    columns = page.locator("#columns")
    page.mouse.wheel(0, columns.bounding_box()["y"] - 80)
    page.wait_for_function(
        "columns => Math.abs(columns.getBoundingClientRect().top - 80) < 2",
        arg=columns.element_handle(),
    )
    scroll_settled(page)
    expect(page.locator("#beside-ask")).to_be_in_viewport()
    read = page.locator("#read").bounding_box()
    page.mouse.move(read["x"] + read["width"] / 2, read["y"] + 4)
    page.keyboard.press("m")
    expect(page.locator("#read-ask")).to_be_focused()


def test_letting_go_of_an_obligation_on_screen_leaves_the_user_beside_it(
    browser, serve
):
    """With several obligations in view, letting go of the second leaves the user beside
    it rather than at the top of the view: `m` returns to it, and Tab carries on into
    it."""
    asks = "".join(
        f"""<lf-group id="ask-{index}" label="Question {index}"><h2 id="ask-{index}-h">Question {index}</h2>
<lf-options id="pick-{index}">
  <lf-option id="pick-{index}-yes">Yes</lf-option>
  <lf-option id="pick-{index}-no">No</lf-option>
</lf-options></lf-group>"""
        for index in range(1, 4)
    )
    page = open_page(
        browser,
        serve(leaf_page("asks in view", f"<h1>Asks</h1><p>Three asks.</p>{asks}")),
    )
    page.keyboard.press("m")
    expect(page.locator("#ask-1")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#ask-2")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("m")
    expect(page.locator("#ask-2")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    expect(page.locator("#pick-2 .lf-pick").first).to_be_focused()


def test_the_obligation_walk_measures_from_chrome_only_where_the_chrome_holds_an_obligation(
    browser, serve
):
    """The user's place has to be a place in the walk's own ordered space. The chrome is
    appended after the whole page, so a user located on a thread in the panel would
    measure as past every obligation there is.

    The route runs through the chrome all the same: a widget in a reply is an
    obligation the walk visits, and a user working its controls is located in the space the
    step measures. So the question is which obligations the layer holds and not whether the
    layer is chrome.

    The backward press follows a walk down to the first page obligation, but focus has since
    moved into the reply's obligation. That current focus supplies the step's origin."""
    url = serve(
        leaf_page(
            "asks over a panel",
            """
<h1 id="h">Open questions</h1>
<lf-group id="first-decision" label="Where should the feeders go?"><h2 id="first-decision-h">Where should the feeders go?</h2>
<lf-options id="first">
  <lf-option id="fi-hedge" label="Along the hedge"><strong>Along the hedge</strong></lf-option>
  <lf-option id="fi-lawn" label="Out on the lawn"><strong>Out on the lawn</strong></lf-option>
</lf-options></lf-group>
<lf-group id="second-decision" label="Who fills them?"><h2 id="second-decision-h">Who fills them?</h2>
<lf-options id="second">
  <lf-option id="se-rota" label="A rota"><strong>A rota</strong></lf-option>
  <lf-option id="se-camera" label="Whoever the camera calls"><strong>Whoever the camera calls</strong></lf-option>
</lf-options></lf-group>
""",
        ),
        comments=2,
    )
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "And one for you in here.\n\n"
            '<lf-group id="reply-decision" label="Which baffle?">\n<h3 id="reply-decision-h">Which baffle?</h3>'
            '<lf-options id="reply-ask">'
            '<lf-option id="re-dome" label="A dome"><strong>A dome</strong></lf-option>'
            '<lf-option id="re-cone" label="A cone"><strong>A cone</strong></lf-option>'
            "</lf-options></lf-group>",
        },
    )
    page = open_page(browser, live_url(url))

    # A thread is chrome holding no obligation, so the walk starts from the page.
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#first-decision")).to_be_focused()

    # The reply's obligation is in the route. Walking off it and back down to the first must
    # not leave a remembered origin that overrides a later focus on the reply's obligation.
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#reply-decision")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#first-decision")).to_be_focused()

    # Travel put away the view covering the page obligations. Reopen the reply
    # before locating its control; the next step still measures from that obligation.
    panel_settled(page, open=False)
    expect(page.locator("#reply-decision")).to_have_count(0)
    open_panel_thread(page, reply["id"])
    pick = page.locator("#reply-decision .lf-pick").first
    pick.focus()
    expect(pick).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()


OBLIGATION_THREAD_PAGE = leaf_page(
    "an ask and its thread",
    """<h1>Cache review</h1>
<p id="lead">The budget note covers latency budgets for the cache.</p>
<lf-group id="cache-ask" label="Which cache should we keep?">
  <h2 id="cache-ask-h">Which cache should we keep?</h2>
  <lf-options id="cache">
    <lf-option id="cache-disk">Keep the disk cache</lf-option>
    <lf-option id="cache-memory">Keep the memory cache</lf-option>
  </lf-options>
</lf-group>
<lf-group id="ship-ask" label="Ship on Friday?">
  <h2 id="ship-ask-h">Ship on Friday?</h2>
  <lf-options id="ship">
    <lf-option id="ship-friday">Ship Friday</lf-option>
    <lf-option id="ship-wait">Wait a week</lf-option>
  </lf-options>
</lf-group>
<lf-test-tasks id="tasks">
  <lf-test-task id="retry" status="review" owner="infra">
    <strong>Retry budget</strong> The retry budget doubles under load.
    <lf-group id="retry-ask" label="Raise the retry budget?">
      <h3 id="retry-ask-h">Raise the retry budget?</h3>
      <lf-options id="retry-pick">
        <lf-option id="retry-raise">Raise it</lf-option>
        <lf-option id="retry-keep">Keep it</lf-option>
      </lf-options>
    </lf-group>
  </lf-test-task>
</lf-test-tasks>""",
)


TALL_OBLIGATION_THREAD_PAGE = OBLIGATION_THREAD_PAGE.replace(
    "<h2>Which cache should we keep?</h2>",
    "<h2>Which cache should we keep?</h2>"
    + "<p>Compare the memory and disk constraints carefully.</p>" * 14,
)


def test_walking_to_an_obligation_shows_its_discussion_clear_of_its_choices(
    browser, serve
):
    """`m` lands on a tall obligation and its thread comes up in the card, which stands clear
    of the obligation's choices, so a digit still answers and `c` continues the thread
    rather than starting another."""
    url = serve(TALL_OBLIGATION_THREAD_PAGE)
    root = answered_comment(
        serve.page_dir, "The disk cache costs more.", {"section": "cache-ask"}
    )
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 900})
    page.keyboard.press("m")
    expect(page.locator("#cache-ask")).to_be_focused()
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
    )
    expect(thread).to_be_visible()
    rendered(page)
    card = page.locator(".lf-margin-preview").bounding_box()
    for option in page.locator("#cache-ask lf-option").all():
        box = option.bounding_box()
        assert (
            box["x"] >= card["x"] + card["width"]
            or card["x"] >= box["x"] + box["width"]
            or box["y"] >= card["y"] + card["height"]
            or card["y"] >= box["y"] + box["height"]
        ), (card, box)
    page.keyboard.press("1")
    expect(page.locator("#cache-disk")).to_have_attribute("selected", "")
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_be_hidden()


def test_walking_to_an_obligation_on_a_phone_continues_its_discussion_in_the_panel(
    browser, serve
):
    """A phone's window has no room for a margin card, so `m` leaves the obligation's
    choices uncovered, a digit answers, and `c` continues its thread in the floating panel
    rather than starting another (records/thread/destination.js)."""
    url = serve(TALL_OBLIGATION_THREAD_PAGE)
    root = answered_comment(
        serve.page_dir, "The disk cache costs more.", {"section": "cache-ask"}
    )
    page = open_page(browser, url)
    page.set_viewport_size({"width": 390, "height": 900})
    page.keyboard.press("m")
    expect(page.locator("#cache-ask")).to_be_focused()
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_have_count(0)
    page.keyboard.press("1")
    expect(page.locator("#cache-disk")).to_have_attribute("selected", "")
    page.keyboard.press("c")
    thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(thread).to_be_visible()
    expect(panel_field(page)).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_be_hidden()


@pytest.mark.parametrize("family", ["decision", "suggestion"])
def test_walking_to_an_obligation_opens_its_discussion(browser, serve, family):
    """`m` selects an obligation and its thread comes up beside it, as at any target the user
    stands at, taking over from the passage's card. Working the obligation's controls keeps it
    there, and `c` continues it."""
    if family == "decision":
        item = '<lf-group id="work" label="Keep the plan?"><h2 id="work-h">Keep the plan?</h2><lf-options id="decision"><lf-option id="yes">Yes</lf-option><lf-option id="no">No</lf-option></lf-options></lf-group>'
    else:
        item = '<lf-suggestion id="work"><lf-old>Old plan</lf-old><lf-new>New plan</lf-new></lf-suggestion>'
    source = leaf_page(
        "Work and discussion",
        '<p id="passage" tabindex="0">Read this background before deciding.</p>' + item,
    )
    url = serve(source)
    passive = panel_comment(
        serve.page_dir, "Remember the background.", {"section": "passage"}
    )
    root = answered_comment(
        serve.page_dir, "Please compare the alternatives.", {"section": "work"}
    )
    page = open_page(browser, url)
    card = page.locator(".lf-margin-preview")
    discussion = card.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    page.keyboard.press("Shift")
    page.locator("#passage").focus()
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{passive}"]')).to_be_visible()
    page.keyboard.press("m")
    expect(page.locator("#work")).to_be_focused()
    expect(discussion).to_be_visible()
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{passive}"]')).to_have_count(
        0
    )
    if family == "decision":
        page.keyboard.press("Tab")
    else:
        suggestion_control(page, "work", "accept").focus()
    assert (
        page.evaluate("async () => (await window.__lfCheckApi()).heldObligation()?.id")
        == "work"
    )
    rendered(page)
    expect(discussion).to_be_visible()
    page.keyboard.press("c")
    expect(discussion.locator("leaf-text")).to_be_focused()


def test_an_obligation_and_its_thread_are_one_current_target(browser, serve):
    """An obligation and the thread its card shows are one place held from two sides
    (glossary, Current target). From the obligation, `c` continues that thread; from its
    thread in the card, the obligation keeps its ring and its digits.
    A thread about an enclosing block holds the decision inside it with the agent, so
    On Me skips that decision. From an element with no thread, `t` measures from its
    place in the document, as `m` does."""
    url = serve(OBLIGATION_THREAD_PAGE)
    d = serve.page_dir
    panel_comment(
        d, "Budgets are tight.", {"section": "lead", "quote": "latency budgets"}
    )
    about_obligation = answered_comment(
        d, "The disk cache costs more.", {"section": "cache-ask"}
    )
    about_task = panel_comment(
        d,
        "Doubling is a lot.",
        {"section": "retry", "quote": "The retry budget doubles under load."},
    )
    page = open_page(browser, url)
    card = page.locator(".lf-margin-preview")
    item = page.locator("#cache-ask")
    obligation_thread = card.locator(
        f'.lf-page-thread[data-lf-thread="{about_obligation}"]'
    )

    # `m` lands on the obligation and its thread comes up in the card beside it, which `c`
    # continues rather than starting a second one.
    page.keyboard.press("m")
    expect(item).to_be_focused()
    expect(obligation_thread).to_be_visible()
    page.keyboard.press("c")
    expect(obligation_thread.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(obligation_thread).to_be_focused()
    expect(item).to_have_attribute("data-lf-obligation", "1")
    # Leaving the card releases the target beside the ask; it does not focus the ask.
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    # A walk from beside a released target returns to it before advancing.
    page.keyboard.press("m")
    expect(item).to_be_focused()
    expect(obligation_thread).to_be_visible()

    # From an obligation with no thread, `t` goes to the next thread after it in the document,
    # which is the task's. Back from there is the obligation's own thread, where, in the card,
    # the obligation is still the current location.
    page.keyboard.press("m")
    expect(page.locator("#ship-ask")).to_be_focused()
    page.keyboard.press("t")
    expect(
        card.locator(f'.lf-page-thread[data-lf-thread="{about_task}"]')
    ).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(obligation_thread).to_be_focused()
    expect(item).to_have_attribute("data-lf-obligation", "1")

    # The thread on the task holds its nested decision with the agent. On Me therefore
    # cycles past that decision until the agent answers the thread.
    page.keyboard.press("m")
    expect(page.locator("#ship-ask")).to_be_focused()
    page.keyboard.press("m")
    expect(item).to_be_focused()


def test_c_continues_the_card_beside_an_obligation_in_a_commented_block(browser, serve):
    """The card a block's thread opens beside an obligation inside the block is the
    thread the user is at, so `c` writes in its reply. Closing that card and opening a
    box on the obligation would answer a reply with a new thread."""
    url = serve(
        leaf_page(
            "calls",
            """<h1>Review</h1>
<section id="calls"><h2>Judgment calls</h2>
<lf-group id="mark-ask" label="Cut the mark?"><h3 id="mark-ask-h">Cut the mark?</h3>
<lf-options id="mark">
  <lf-option id="mark-keep">Keep it</lf-option>
  <lf-option id="mark-cut">Remove it</lf-option>
</lf-options></lf-group></section>""",
        )
    )
    root = answered_comment(
        serve.page_dir, "Need better choices.", {"section": "calls"}
    )
    page = open_page(browser, url)
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
    )
    page.keyboard.press("m")
    expect(page.locator("#mark-ask")).to_be_focused()
    expect(thread).to_be_visible()
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()


def test_c_from_a_shot_in_a_questions_group_comments_on_the_question(browser, serve):
    """A question's group holds what it asks about, so a press on a control there is the
    user reading the question. After `m`, a click that flips the shot or drags its divider
    puts focus on the shot's own controls, which would move `c` onto the shot, while
    a press on its Pixels button would leave `c` on the question, and once the question
    was answered every press would name the shot. The control is the same press on a shot
    outside any question, where `c` names the shot."""
    shot = (
        f'alt="the board before and after" before="{SHOT_SRC["before"]}" '
        f'after="{SHOT_SRC["after"]}"></lf-shot>'
    )
    url = serve(
        leaf_page(
            "calls",
            f"""<h1>Review</h1>
<section id="calls"><h2>Judgment calls</h2>
<lf-group id="count-ask" label="Show the card count?"><h3 id="count-ask-h">Show the card count?</h3>
<lf-shot id="count-shot" {shot}
<lf-options id="count">
  <lf-option id="count-keep">Keep it</lf-option>
  <lf-option id="count-cut">Remove it</lf-option>
</lf-options></lf-group></section>
<section id="loose"><h2>Loose</h2><lf-shot id="loose-shot" {shot}</section>""",
        ),
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    page = open_page(browser, url)
    composer = page.locator(".lf-composer")

    def comment_after_flipping(shot_id):
        comparison = page.locator(f"#{shot_id} wa-comparison")
        comparison.scroll_into_view_if_needed()
        box = comparison.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.3, box["y"] + box["height"] / 2)
        page.keyboard.press("c")
        expect(composer).to_be_visible()

    page.keyboard.press("m")
    expect(page.locator("#count-ask")).to_be_focused()
    comment_after_flipping("count-shot")
    expect(composer).to_contain_text("group · Show the card count?")
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    # Answered, the frame still holds what the question is about.
    option = page.locator("#count-keep")
    option.click()
    expect(option).to_have_attribute("selected", "")
    comment_after_flipping("count-shot")
    expect(composer).to_contain_text("group · Show the card count?")
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    comment_after_flipping("loose-shot")
    expect(composer).to_contain_text("shot")
    expect(composer).not_to_contain_text("question")


def test_an_obligation_in_a_reply_is_where_the_user_stands_once_answered(
    browser, serve
):
    """An obligation in a reply sits in a thread about a page question. Located in the
    reply's obligation keeps that location whether or not it is answered, so a user back
    on the answered option does not have the page obligation's ring and digits. A
    contributed control for a widget in the reply stands where that widget does: in no
    obligation, it stands where the thread's view does, at the page obligation the thread
    is about. While the reply's question is open, the control is in it, as the whole view
    is, so that question wears the ring and takes the digits, and `m` from it steps on
    past it. Once it is answered, the thread asks nothing, and the page question wears
    the ring and takes the digits."""
    url = serve(
        OBLIGATION_THREAD_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    d = serve.page_dir
    about_obligation = panel_comment(
        d, "Which one lasts longer?", {"section": "cache-ask"}
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": about_obligation,
            "responds": about_obligation,
            "text": "One question first.\n\n"
            '<lf-group id="follow-ask" label="Measure it first?">\n<h3 id="follow-ask-h">Measure it first?</h3>'
            '<lf-options id="follow">'
            '<lf-option id="follow-yes">Measure first</lf-option>'
            '<lf-option id="follow-no">Decide now</lf-option>'
            "</lf-options></lf-group>"
            f'<lf-shot id="follow-shot" alt="the cache before and after" '
            f'before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>',
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, about_obligation)
    page.evaluate(
        """async (thread) => {
      const {registerContribution} =
        await window.__lfWidgetApi();
      registerContribution({key: 'reply-capture',
        target: document.querySelector(`${thread} lf-shot`),
        read: () => ({entries: [{key: 'review', glyph: 'R',
          label: 'Review reply capture'}]}), activate: () => {},
      });
    }""",
        PANEL_THREAD,
    )
    contributed = page.locator(PANEL_THREAD).get_by_role(
        "button", name="Review reply capture", exact=True
    )
    expect(contributed).to_be_visible()
    contributed.focus()
    assert (
        contributed.evaluate(
            "async (control) => (await window.__lfCheckApi()).placeOf(control)?.id"
        )
        == "cache-ask"
    ), "a control on a widget in a reply does not stand where its thread is about"
    expect(page.locator("#follow-ask")).to_have_attribute("data-lf-obligation", "1")
    expect(page.locator("#cache-ask")).not_to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("m")
    expect(page.locator("#ship-ask")).to_be_focused()
    open_panel_thread(page, about_obligation)
    option = page.locator("#follow-yes")
    option.click()
    expect(option).to_have_attribute("selected", "")
    # Back on the answered option, the user is located in the reply's question.
    round_trip(page)
    option.locator(".lf-pick").focus()
    expect(page.locator("#cache-ask")).not_to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#cache-disk")).not_to_have_attribute("selected", "")

    # That digit took the pick back, so from the control on the reply's widget the
    # reply's question, open again, wears the ring and takes the digits.
    expect(option).not_to_have_attribute("selected", "")
    contributed.focus()
    expect(page.locator("#follow-ask")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("1")
    round_trip(page)
    expect(option).to_have_attribute("selected", "")

    # Answered, the thread asks nothing, and the control stands at the page question: its
    # digit answers it, and the answered obligation keeps its ring there: the control is a
    # review route to it, as an On card is.
    expect(page.locator("#cache-ask")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#cache-disk")).to_have_attribute("selected", "")
    expect(page.locator("#follow-yes")).to_have_attribute("selected", "")
    expect(contributed).to_be_focused()
    expect(page.locator("#cache-ask")).to_have_attribute("data-lf-obligation", "1")


def test_a_thread_takes_the_digits_of_the_questions_it_asks_in_turn(browser, serve):
    """A thread whose agent's latest message asks questions is in the first still open:
    `t` lands on the thread, that question wears the ring and its options their digits,
    and a digit picks one there, leaving the question an earlier message asked alone and
    the user on the thread. The thread then moves on to the next, as a form does, and
    the panel's view of the thread answers it too. Once both are answered the thread asks
    nothing, so a further digit revises neither answer."""
    source = leaf_page(
        "Release charts",
        '<section id="release"><h2 id="release-h">The release page</h2>'
        "<p>It draws ten charts as images.</p></section>",
    )
    events = [
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "id": "ask",
            "anchor": {"section": "release"},
            "text": "Should the charts stay images?\n\n"
            '<lf-options id="first"><lf-option id="first-keep">Keep them</lf-option>'
            '<lf-option id="first-inline">Inline them</lf-option></lf-options>',
        },
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "id": "why",
            "parent": "ask",
            "text": "What would inlining take?",
        },
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": "ask",
            "responds": "why",
            "text": "A script the release page's session runs. Who should run it?\n\n"
            '<lf-options id="second"><lf-option id="second-send">Its session</lf-option>'
            '<lf-option id="second-here">This session</lf-option></lf-options>\n\n'
            "And when?\n\n"
            '<lf-options id="third"><lf-option id="third-now">Now</lf-option>'
            '<lf-option id="third-later">After the release</lf-option></lf-options>',
        },
    ]
    page = open_page(browser, serve(source, events=events))
    page.keyboard.press("t")
    thread = page.locator(f'{CARD} .lf-page-thread[data-lf-thread="ask"]')
    expect(thread).to_be_focused()
    expect(page.locator("#second")).to_have_attribute("data-lf-obligation", "1")
    expect(page.locator("#second-here .lf-key-badge")).to_have_text("2")
    page.keyboard.press("2")
    expect(page.locator("#second-here")).to_have_attribute("selected", "")
    round_trip(page)
    expect(page.locator("#first lf-option[selected]")).to_have_count(0)
    expect(thread).to_be_focused()
    expect(page.locator("#third")).to_have_attribute("data-lf-obligation", "1")

    # The panel's view of the thread draws its reply row apart from its messages, and a
    # digit from that row's Dictate answers the same question.
    open_panel_thread(page, "ask")
    expect(panel_field(page)).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator(".lf-fp-field .lf-compose-dictate")).to_be_focused()
    page.keyboard.press("1")
    expect(page.locator("#third-now")).to_have_attribute("selected", "")
    round_trip(page)
    page.keyboard.press("2")
    round_trip(page)
    expect(page.locator("lf-option[selected]")).to_have_count(2)
    expect(page.locator("#second-here")).to_have_attribute("selected", "")
    expect(page.locator("#third-now")).to_have_attribute("selected", "")


OBLIGATION_IN_A_PANE_PAGE = leaf_page(
    "ask in a pane",
    """
  <header><h1>Decisions</h1></header>
  <div id="ask-split">
    <lf-pane id="ask-notes" label="Notes">
      <header><h2>Notes</h2></header>
      <div><p>Notes that hold still while the decision pane scrolls.</p></div>
    </lf-pane>
    <lf-pane id="ask-detail" label="Decision">
      <header><h2>Evidence and decision</h2></header>
      <div>
        <p>Evidence the user reads before the question.</p>
        <div style="height: 700px"></div>
        <lf-group id="pane-decision" label="How should the probe page?">
          <h3 id="pane-decision-h">How should the probe page?</h3>
          <lf-options id="pane-choice">
            <lf-option id="pane-a" label="Require three failures"><strong>Require three failures</strong> Quieter.</lf-option>
            <lf-option id="pane-b" label="Keep one failure"><strong>Keep one failure</strong> Louder.</lf-option>
          </lf-options>
        </lf-group>
        <div style="height: 900px"></div>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("ask-split"),
    layout="workspace",
)


def test_an_obligation_landed_in_a_pane_keeps_its_ring_inside_the_pane(browser, serve):
    """An obligation walk lands the decision at the start of the pane that scrolls it, and the
    obligation wears the ring outside its box. The landing keeps the ring's room at the pane's
    edge, as the browser's own landing does for a box asking for it, where otherwise the
    obligation would stand flush with the pane's top, the top of its ring cut off under
    the pane's header rule."""
    page = open_page(browser, serve(OBLIGATION_IN_A_PANE_PAGE))
    resized(page, 1440, 900)
    pane_scroll_behavior(page, page.locator("#ask-detail"), "bounded")
    page.keyboard.press("m")
    item = page.locator("#pane-decision")
    expect(item).to_be_focused()
    expect(item).to_have_attribute("data-lf-obligation", "1")
    scroll_settled(page, "#ask-detail > :not(header, footer)")
    expect(item).to_have_attribute("data-lf-projected-location", "")
    ring = item.evaluate(MARK)
    pane_top = item.evaluate(
        """ask => {
          const body = ask.closest('lf-pane').querySelector(':scope > :not(header, footer)');
          return body.getBoundingClientRect().top + body.clientTop;
        }"""
    )
    assert ring["ring"]["top"] >= pane_top - 0.5, (ring, pane_top)


ASK_WORDS = """() => {
  const words = document.createRange();
  words.selectNodeContents(document.querySelector('#rollout h2'));
  return {words: words.getClientRects()[0].left};
}"""


def test_the_ring_round_a_question_stands_clear_of_its_words(browser, serve):
    """The ring the user stands in goes round a question outside its box, as every
    obligation's does, so it does not run over the first letter of each line. A
    question that is a full-height workspace's body has only the workspace's gutter
    round it, so its ring stands at a control's gap (layouts.css), inside the window
    on top and at the sides: inside the question it would run over the heading's first
    letter and under the panes the question holds."""
    ask = (
        '<lf-group id="rollout" label="Include self-hosted runners?"><h2 id="rollout-h">Include self-hosted runners?</h2>'
        "<p>They need administrator-configured namespaces.</p>"
        '<lf-options id="rollout-options">'
        '<lf-option id="include">Include them</lf-option>'
        '<lf-option id="later">Later</lf-option></lf-options></lf-group>'
    )
    page = open_page(browser, serve(leaf_page("a question", ask)))
    resized(page, 1280, 800)
    page.keyboard.press("m")
    question = page.locator("#rollout")
    expect(question).to_have_attribute("data-lf-projected-location", "")
    ring, column = question.evaluate(MARK), page.evaluate(ASK_WORDS)
    assert ring["ring"]["left"] + ring["width"] < column["words"], (ring, column)
    page.close()

    page = open_page(browser, serve(leaf_page("a question", ask, layout="workspace")))
    resized(page, 1280, 800)
    page.keyboard.press("m")
    question = page.locator("#rollout")
    expect(question).to_have_attribute("data-lf-projected-location", "")
    ring, workspace = question.evaluate(MARK), page.evaluate(ASK_WORDS)
    assert ring["offset"] > 0, ring
    assert ring["ring"]["top"] >= 0 and ring["ring"]["left"] >= 0, ring
    assert ring["ring"]["left"] + ring["width"] < workspace["words"], (ring, workspace)


@pytest.mark.parametrize("where", ["margin", "panel"])
def test_an_m_walk_between_thread_asks_is_a_back_step_naming_the_thread_it_left(
    browser, serve, where
):
    """`m` from the question one thread asks to the one another asks is a Back step,
    as every walk's stop is, whether the threads open in margin cards or in the
    floating panel, and the entry it leaves still names the thread it left."""
    url = serve(LONG_PAGE)
    threads = []
    for n, section in enumerate(("p3", "p41")):
        comment = {"kind": "comment", "author": "user", "revision": 1, "text": f"Q{n}?"}
        if where == "margin":
            comment["anchor"] = {
                "section": section,
                "quote": f"Paragraph {section[1:]}.",
            }
        root = append_carried_log_record(serve.page_dir, comment)["id"]
        # A question the reply's widget asks, which `m` draws before it lands there.
        thread_model.post_reply(
            serve.page_dir,
            {"parent": root},
            f'Pick one.\n\n<lf-group id="ask-{n}" label="Which {n}?">\n'
            f'<h3 id="ask-{n}-h">Which {n}?</h3><lf-options id="pick-{n}">'
            f'<lf-option id="pick-{n}-a">Alpha</lf-option>'
            f'<lf-option id="pick-{n}-b">Beta</lf-option></lf-options></lf-group>',
        )
        threads.append(root)
    page = open_page(browser, url)
    page.keyboard.press("m")
    page.wait_for_function(f"({IN_THREAD})() !== null")
    first = page.evaluate(IN_THREAD)
    page.wait_for_function("navigation.transition === null")
    entries = page.evaluate("history.length")
    page.keyboard.press("m")
    page.wait_for_function(f"(({IN_THREAD})() ?? {first!r}) !== {first!r}")
    assert page.evaluate(IN_THREAD) in threads
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("history.length") == entries + 1
    left = page.evaluate(
        "new URL(navigation.entries()[navigation.currentEntry.index - 1].url)"
        ".searchParams.get('thread')"
    )
    assert left == first


# The thread the focused node is in, across shadow roots, or null.
IN_THREAD = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at?.closest('[data-lf-thread]')?.dataset.lfThread ?? null;
}"""
