"""The item walk with `m`: where it lands, how it reveals an item in tabs and scrollers,
and an item's digits and thread."""

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    ITEMS_PAGE,
    answered_comment,
    live_url,
    panel_comment,
)
from render_cases_layout import SHOT_SRC, SHOTS
from render_cases_navigation import (
    BINDING_BADGE_PAGE,
    CLIPPED_BY,
    INSIDE_ITS_OPTION,
    NOTED_PAGE,
    OVER_WORDS,
)
from render_harness import (
    PANEL_THREAD,
    RELEASE_FOCUS,
    ROOT,
    leaf_page,
    open_page,
    pane_posture,
    panel_settled,
    regions_side_by_side,
    resized,
    round_trip,
    said,
    scroll_settled,
    sending,
    suggestion_control,
    take_browser_errors,
)

from browser.navigation import expect_walk_position, walk_position
from browser.threads import open_panel_thread

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize(("nested_source", "reduced"), [(False, True), (True, False)])
def test_an_item_walk_glides_within_a_view_and_opens_other_tabs_at_the_question(
    browser, serve, reduced, nested_source
):
    """A disclosure extends one reading; a mutually exclusive tab opens at its lf-ask.

    Capture frames rather than just scroll events: a new panel must already show the
    question in its first painted frame, not appear elsewhere and glide afterwards.
    """

    def question(name):
        options = (
            f'<lf-options id="choice-{name}" choose>'
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
        return f'<lf-ask id="ask-{name}"><h2>Choose {name}?</h2>{options}</lf-ask>'

    first = question("first")
    if not nested_source:
        first = (
            '<details id="question-fold"><summary>First proposal</summary>'
            + first
            + "</details>"
        )
    source = leaf_page(
        "Ask travel across tabs",
        '<h1>Review the two proposals</h1><lf-tabs id="views">'
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

    def start_trace():
        page.evaluate("""() => {
          window.itemFrames = [];
          window.itemTabCues = [];
          const record = () => {
            const tab = document.querySelector('#views > .lf-tabstrip [aria-selected="true"]');
            const selected = tab.getAttribute('aria-controls');
            const ask = document.getElementById(`ask-${selected}`);
            const source = document.querySelector('#source-views [aria-selected="true"]');
            itemFrames.push({selected, scroll: scrollY,
                           source: source?.getAttribute('aria-controls'),
                           top: ask.getBoundingClientRect().top});
            window.itemFrame = requestAnimationFrame(record);
          };
          window.itemFrame = requestAnimationFrame(record);
          window.itemTabObserver = new MutationObserver(records => {
            for (const {target} of records) {
              if (target.getAttribute('aria-selected') === 'true' &&
                  target.closest('lf-tabs').id === 'views') {
                const name = target.querySelector('.lf-tab-name');
                itemTabCues.push(name.getAnimations().length);
              }
            }
          });
          itemTabObserver.observe(document.querySelector('#views'), {
            subtree: true, attributes: true, attributeFilter: ['aria-selected']
          });
        }""")

    def finish_trace():
        return page.evaluate("""() => {
          cancelAnimationFrame(itemFrame);
          itemTabObserver.disconnect();
          return {frames: itemFrames, cues: itemTabCues};
        }""")

    # The item's source may switch an inner view even when its outer wrapper stays.
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
        edge = page.evaluate(
            "parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"
        )
        arrived = [
            frame for frame in trace["frames"] if frame["source"] == "source-answer"
        ]
        assert arrived, trace
        assert all(abs(frame["top"] - (edge + 5)) <= 3 for frame in arrived), trace

    for key, target, tab in [("m", "second", "Second"), ("Shift+m", "first", "First")]:
        before = page.evaluate("scrollY")
        start_trace()
        if target == "second":
            # A revealed view may finish presentation later than its new geometry.
            # Record its first painted frame while that completion is held.
            page.evaluate("""() => {
              const held = new Promise(resolve => { window.releaseItemTabLayout = resolve; });
              document.querySelector('#views').addEventListener('lf-layout', event => {
                event.detail.present(held);
                window.itemTabLayoutStarted = true;
              }, {once: true});
            }""")
            try:
                page.keyboard.press(key)
                page.wait_for_function("window.itemTabLayoutStarted === true")
                one_frame(page)
            finally:
                page.evaluate("releaseItemTabLayout()")
        else:
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
        edge = page.evaluate(
            "parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)"
        )
        arrived = [frame for frame in trace["frames"] if frame["selected"] == target]
        assert arrived, trace
        assert all(abs(frame["top"] - (edge + 5)) <= 3 for frame in arrived), trace
        assert trace["cues"] == [0 if reduced else 1], trace
        top = page.locator(f"#ask-{target}").bounding_box()["y"]
        assert top == pytest.approx(edge + 5, abs=3), (top, edge)

    # Leave the previous arrival entirely: the next trip must preserve this reading
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


def test_an_item_walk_reveals_the_owning_regions_horizontal_destination(browser, serve):
    """Arrival keeps horizontal inspection reachable without snapping document Y."""
    source = leaf_page(
        "Ask in horizontal inspection",
        '<h1>Inspect the wide proposal</h1><div id="inspection" data-bound="start" '
        'style="width:220px; height:280px; overflow:auto">'
        '<div style="width:1600px; padding-left:900px; box-sizing:border-box">'
        '<lf-ask id="wide-ask"><h2>Choose the wider plan?</h2>'
        '<lf-options id="wide-choice" choose>'
        '<lf-option id="wide-yes">Yes</lf-option>'
        '<lf-option id="wide-no">No</lf-option></lf-options></lf-ask>'
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
def test_an_item_walk_reveals_its_scrollport_before_aligning_outside_context(
    browser, serve, clipped
):
    """Context above a bounded inspection never leaves its item clipped inside it."""
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


def test_keys_answer_an_item_from_its_marks(browser, serve):
    """The item's digits stay live while a mark adds only its control-local keys.

    One Tab enters the marks, where ↑/↓ walk the options and clamp at the ends, and
    Home and End reach them.
    Moving focus does not replace the item's numeric action context with a widget copy.
    """
    page = open_page(browser, serve(ITEMS_PAGE))
    nums = page.locator("#live-question > lf-option > .lf-key-badge")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("m")
    expect_walk_position(page, "1 of 4 waiting on me · Options")
    marks = page.locator("#live-question .lf-pick")
    # The arrival stands on the item, which wears its options' digits; the marks
    # are the next Tab stops.
    expect(
        page.locator(
            "#live-question > lf-option > .lf-key-badge[data-lf-binding-badge]"
        )
    ).to_have_text(["1", "2"])
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfWidgetApi();
          notice('Saved — sent');
          dispatchEvent(new Event('resize'));
        }"""
    )
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-says", "notice"
    )
    expect(
        page.locator(
            "#live-question > lf-option > .lf-key-badge[data-lf-binding-badge]"
        )
    ).to_have_text(["1", "2"])
    page.keyboard.press("Tab")
    expect(marks.first).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me · Options")
    expect(
        page.locator(
            "#live-question > lf-option > .lf-key-badge[data-lf-binding-badge]"
        )
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
    # Home and End reach the ends, as in every other list of rows.
    page.keyboard.press("Home")
    expect(marks.first).to_be_focused()
    expect_walk_position(page, "Option 1 of 2")
    page.keyboard.press("End")
    expect(marks.nth(1)).to_be_focused()
    expect_walk_position(page, "Option 2 of 2")

    with sending(page, "the numbered pick"):
        page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")
    # The pick's notice takes the panel's seat for passing words, and focus never left
    # the second option, so the walk's reading stands behind it rather than retiring.
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-says", "notice"
    )
    assert (
        page.evaluate(
            """async () => (await window.__lfCheckApi())
                .walkPosition()?.text"""
        )
        == "Option 2 of 2"
    )
    acts = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"value": ["lq-keep"]}


def test_a_failed_item_reveal_does_not_register_an_arrival(browser, serve):
    """A rejected reveal neither advances nor marks the existing item walk."""
    page = open_page(browser, serve(ITEMS_PAGE))
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 4 waiting on me · Options")
    page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          const source = document.querySelector('#sug-refill');
          source.addEventListener('lf-reveal', event => {
            const {promise: ready, reject} = Promise.withResolvers();
            window.rejectItemReveal = reject;
            ready.then(() => {}, () => { window.itemRevealRejected = true; });
            widgetController(source).present(ready);
            event.detail.present(ready);
            window.itemRevealStarted = true;
          }, {once: true});
        }"""
    )
    page.keyboard.press("m")
    page.wait_for_function("window.itemRevealStarted === true")
    expect(page.locator("#live-question-decision")).to_be_focused()
    page.evaluate("() => { rejectItemReveal(new Error('item reveal probe')); }")
    page.wait_for_function("window.itemRevealRejected === true")
    rendered(page)
    position = walk_position(page)
    assert position["text"] == "1 of 4 waiting on me · Options"
    assert not position["boundary"]
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: item reveal probe"
    ]
    round_trip(page)


def test_a_delayed_item_reveal_yields_to_programmatic_user_focus(browser, serve):
    """A completed old reveal cannot steal accessibility focus or register an arrival."""
    page = open_page(browser, serve(ITEMS_PAGE))
    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_be_focused()
    expect_walk_position(page, "1 of 4 waiting on me · Options")
    page.evaluate(
        """() => {
          const held = new Promise(resolve => { window.releaseItemReveal = resolve; });
          held.then(() => { window.itemRevealSettled = true; });
          document.querySelector('#sug-refill').addEventListener('lf-reveal', event => {
            event.detail.present(held);
            window.itemRevealStarted = true;
          }, {once: true});
        }"""
    )

    page.keyboard.press("m")
    page.wait_for_function("window.itemRevealStarted === true")
    # Assistive technology and focus-management code can move the user without a
    # pointer, key, or input event. The retained navigation must read focus itself.
    page.locator(".lf-fp-threads").focus()
    expect(page.locator(".lf-fp-threads")).to_be_focused()
    page.evaluate("releaseItemReveal()")
    page.wait_for_function("window.itemRevealSettled === true")
    rendered(page)

    expect(page.locator(".lf-fp-threads")).to_be_focused()
    # The user left the walk, so it says nothing more; it never says the next arrival.
    position = walk_position(page)
    assert (position or {}).get("text") in (None, "1 of 4 waiting on me · Options")


def test_a_selected_tab_enters_the_item_it_controls(browser, serve):
    """A controlled panel can itself be an item; selecting its tab hasn't entered it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "A tab opening an ask",
                '<h1>Decisions</h1><div role="tablist">'
                '<button role="tab" aria-selected="true" aria-controls="second-decision">'
                "Second</button></div>"
                + "".join(
                    f'<lf-ask id="{key}-decision"><h2>Pick {key}</h2>'
                    f'<lf-options id="{key}" choose><lf-option id="{key}-a">'
                    "Alpha</lf-option></lf-options></lf-ask>"
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


def test_an_items_digits_are_drawn_whole(browser, serve):
    """A binding badge arrives into room its option already holds, and lands on nothing.

    Every earlier placement borrowed that room instead, and each borrow showed. On the
    cell's outer corner the chip was half outside a group that clips itself, so no
    binding badge the product drew had ever been whole — seven of its seventeen pixels gone,
    and in a bare-label group the first digit was a sliver.
    Out in the page margin beside the group it was whole and it was in the neighbouring
    card's prose, because a middle column's margin is another cell. Neither showed up
    as a failure: a clipped element still reports its whole box and still answers
    `to_be_visible`, and a chip drawn over words breaks no rule anybody had written.

    So the cell holds a place for it, and this asks the two questions that place
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them. Rows reserve a leading gutter;
    titled cards share their trailing header-state slot with the same item-owned binding badge
    that temporarily replaces status.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one 8px it was level with a 15px row, and the day the row went to the
    page's own 17px it was two pixels too high with the gate still green — because what
    the gate read was the number the theme stated, and the claim beside it, that a row's
    digit is level with its words, was checked by nothing.

    How far in it stands is each form's own relation: edge, digit, then prose for a row;
    prose opening, then digit, then edge for a card. The two forms deliberately no longer
    claim one rail, while every option within a form still claims one stable seat."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    seats = {"card": {}, "row": {}}
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "card"),
        (["r-now", "r-later"], "row"),
    ]:
        page.keyboard.press("m")
        # The arrival stands on the item; the digits are drawn once a mark holds the
        # focus, one Tab in.
        page.keyboard.press("Tab")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-key-badge")
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


def test_frozen_widget_item_walk_orders_by_its_threads_page_passage(browser, serve):
    """A materialized frozen source in chrome keeps its thread's authored page order."""
    page = open_page(browser, serve(ROOT / "examples" / "ship-review.html"))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    page.locator("h1").focus()
    page.keyboard.press("m")
    expect(page.locator(f"{PANEL_THREAD} lf-ask[data-lf-item]")).to_be_focused()


def test_an_item_walk_leaves_the_panel_it_reached_through(browser, serve):
    """`m` from the page reaches an item seated in a thread through the panel, so the
    press opens its thread there on the way. The walk is lateral — it moves the user
    from item to item rather than down a level — and Escape puts the view away. No step
    depends on which press opened the view."""
    page = open_page(browser, serve(ROOT / "examples" / "ship-review.html"))
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    page.keyboard.press("m")
    item = page.locator(f"{PANEL_THREAD} lf-ask[data-lf-item]")
    expect(item).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
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
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
    expect(page.locator(".lf-fp-thread")).to_have_count(1)
    page.get_by_role("button", name="Find a thread or message").click()
    page.locator("input.lf-fp-search").fill("no matching thread")
    expect(page.locator(".lf-fp-thread")).to_have_count(0)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.evaluate(RELEASE_FOCUS)
    fallback = page.evaluate(
        """async () => {
          const {beginWalk} = await window.__lfWidgetApi();
          return beginWalk('thread', 'Thread', () => null) ?? 'Thread 1 of 1';
        }"""
    )
    assert fallback == "Thread 1 of 1"
    expect_walk_position(page, None)

    page.keyboard.press("t")
    expect(page.locator(".lf-live")).to_contain_text("Thread 1 of 1")


def test_items_sharing_context_keep_their_source_identity(browser, serve):
    """Shared prompt context keeps each widget's travel, digits and answer distinct."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Shared Question context",
                '<h1>Shared Question context</h1><lf-ask id="shared">'
                "<h2>Choose both releases</h2>"
                '<lf-options id="first" choose>'
                '<lf-option id="first-a">Alpha</lf-option>'
                '<lf-option id="first-b">Beta</lf-option></lf-options>'
                '<div style="height:1200px">Evidence between decisions</div>'
                '<lf-options id="second" choose>'
                '<lf-option id="second-a">Gamma</lf-option>'
                '<lf-option id="second-b">Delta</lf-option></lf-options></lf-ask>',
            )
        ),
    )

    def questions():
        return page.evaluate(
            """async () => (await window.__lfWidgetApi())
              .readItems().all"""
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
      const {heldItem} = await window.__lfCheckApi();
      return heldItem()?.id;
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
    expect(page.locator("#second")).to_have_attribute("data-lf-item", "1")
    expect(page.locator("#shared")).not_to_have_attribute("data-lf-item", "1")
    page.keyboard.press("Shift+m")
    expect(page.locator("#first")).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    first, second = questions()
    assert first["status"] == "answered"
    assert first["answer"]["value"] == ["first-a"]
    assert second["answer"] is None
    page.keyboard.press("m")
    expect(page.locator("#second")).to_be_focused()
    page.keyboard.press("2")
    round_trip(page)
    assert questions()[1]["answer"]["value"] == ["second-b"]
    page.keyboard.press("Escape")
    for source in ("first", "second"):
        assert page.evaluate(
            """async id => (await window.__lfWidgetApi())
              .itemActions.open('widget:' + id)""",
            source,
        )
        expect(page.locator(f"#{source}")).to_be_focused()


def test_the_item_walk_uses_the_visible_reading_after_its_focus_is_released(
    browser, serve
):
    """Letting go and scrolling starts a new walk where the user is now reading."""
    items = "".join(
        f"""
<lf-ask id="question-{index}"><h2>Question {index}: which route should we take?</h2>
<lf-options id="routes-{index}" choose>
  <lf-option id="route-{index}-left">Take the left route</lf-option>
  <lf-option id="route-{index}-right">Take the right route</lf-option>
</lf-options></lf-ask>
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
    expect(page.locator("#question-4")).to_be_focused()


def test_the_item_walk_measures_from_chrome_only_where_the_chrome_holds_an_item(
    browser, serve
):
    """The user's place has to be a place in the walk's own ordered space. The chrome is
    appended after the whole page, so a user standing on a thread in the panel would
    measure as past every item there is.

    The route runs through the chrome all the same: a widget frozen into a reply is an
    item the walk visits, and a user working its controls is standing in the space the
    step measures. So the question is which items the layer holds and not whether the
    layer is chrome.

    The backward press follows a walk down to the first page item, but focus has since
    moved into the reply's item. That current focus supplies the step's origin."""
    url = serve(
        leaf_page(
            "asks over a panel",
            """
<h1 id="h">Open questions</h1>
<lf-ask id="first-decision"><h2>Where should the feeders go?</h2>
<lf-options id="first" choose>
  <lf-option id="fi-hedge"><strong>Along the hedge</strong></lf-option>
  <lf-option id="fi-lawn"><strong>Out on the lawn</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="second-decision"><h2>Who fills them?</h2>
<lf-options id="second" choose>
  <lf-option id="se-rota"><strong>A rota</strong></lf-option>
  <lf-option id="se-camera"><strong>Whoever the camera calls</strong></lf-option>
</lf-options></lf-ask>
""",
        ),
        comments=2,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "And one for you in here.",
            "markup": '<lf-ask id="reply-decision"><h3>Which baffle?</h3>'
            '<lf-options id="reply-ask" choose>'
            '<lf-option id="re-dome"><strong>A dome</strong></lf-option>'
            '<lf-option id="re-cone"><strong>A cone</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    page = open_page(browser, live_url(url))

    # A thread is chrome holding no item, so the walk starts from the page.
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#first-decision")).to_be_focused()

    # The reply's item is in the route. Walking off it and back down to the first must
    # not leave a remembered origin that overrides a later focus on the reply's item.
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#reply-decision")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#first-decision")).to_be_focused()

    # Standing in that item is standing in the space, so the step measures from it.
    pick = page.locator("#reply-decision .lf-pick").first
    pick.focus()
    expect(pick).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#second-decision")).to_be_focused()


ITEM_THREAD_PAGE = leaf_page(
    "an ask and its thread",
    """<h1>Cache review</h1>
<p id="lead">The budget note covers latency budgets for the cache.</p>
<lf-ask id="cache-ask">
  <h2>Which cache should we keep?</h2>
  <lf-options id="cache" choose>
    <lf-option id="cache-disk">Keep the disk cache</lf-option>
    <lf-option id="cache-memory">Keep the memory cache</lf-option>
  </lf-options>
</lf-ask>
<lf-ask id="ship-ask">
  <h2>Ship on Friday?</h2>
  <lf-options id="ship" choose>
    <lf-option id="ship-friday">Ship Friday</lf-option>
    <lf-option id="ship-wait">Wait a week</lf-option>
  </lf-options>
</lf-ask>
<lf-test-tasks id="tasks">
  <lf-test-task id="retry" status="review" owner="infra">
    <strong>Retry budget</strong> The retry budget doubles under load.
    <lf-ask id="retry-ask">
      <h3>Raise the retry budget?</h3>
      <lf-options id="retry-pick" choose>
        <lf-option id="retry-raise">Raise it</lf-option>
        <lf-option id="retry-keep">Keep it</lf-option>
      </lf-options>
    </lf-ask>
  </lf-test-task>
</lf-test-tasks>""",
)


@pytest.mark.parametrize("width", [390, 1200])
def test_walking_to_an_item_shows_its_discussion_clear_of_its_choices(
    browser, serve, width
):
    """`m` lands on a tall item and its thread comes up in the card, which stands clear
    of the item's choices at either width, so a digit still answers and `c` continues
    the thread rather than starting another."""
    source = ITEM_THREAD_PAGE.replace(
        "<h2>Which cache should we keep?</h2>",
        "<h2>Which cache should we keep?</h2>"
        + "<p>Compare the memory and disk constraints carefully.</p>" * 14,
    )
    url = serve(source)
    root = answered_comment(
        serve.page_dir, "The disk cache costs more.", {"section": "cache-ask"}
    )
    page = open_page(browser, url)
    page.set_viewport_size({"width": width, "height": 900})
    page.keyboard.press("m")
    expect(page.locator("#cache-ask")).to_be_focused()
    thread = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
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
    expect(page.locator("#cache-disk")).to_have_attribute("chosen", "")
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_be_hidden()


@pytest.mark.parametrize("family", ["decision", "suggestion"])
def test_walking_to_an_item_opens_its_discussion(browser, serve, family):
    """`m` selects an item and its thread comes up beside it, as at any target the user
    stands at, taking over from the passage's card. Working the item's controls keeps it
    there, and `c` continues it."""
    if family == "decision":
        item = '<lf-ask id="work"><h2>Keep the plan?</h2><lf-options id="decision" choose><lf-option id="yes">Yes</lf-option><lf-option id="no">No</lf-option></lf-options></lf-ask>'
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
    discussion = card.locator(f'.lf-page-thread[data-thread="{root}"]')
    page.keyboard.press("Shift")
    page.locator("#passage").focus()
    expect(card.locator(f'.lf-page-thread[data-thread="{passive}"]')).to_be_visible()
    page.keyboard.press("m")
    expect(page.locator("#work")).to_be_focused()
    expect(discussion).to_be_visible()
    expect(card.locator(f'.lf-page-thread[data-thread="{passive}"]')).to_have_count(0)
    if family == "decision":
        page.keyboard.press("Tab")
    else:
        suggestion_control(page, "work", "accept").focus()
    assert (
        page.evaluate("async () => (await window.__lfCheckApi()).heldItem()?.id")
        == "work"
    )
    rendered(page)
    expect(discussion).to_be_visible()
    page.keyboard.press("c")
    expect(discussion.locator("leaf-text")).to_be_focused()


def test_an_item_and_its_thread_are_one_standing_target(browser, serve):
    """An item and the thread its card shows are one place held from two sides
    (glossary, Standing target). From the item, `c` continues that thread and `t` steps
    on past it; from its thread in the card, the item keeps its ring and its digits. A thread about an enclosing block is that block's, so an item
    inside the block still starts a thread of its own. From an element with no thread,
    `t` measures from its place in the document, as `m` does."""
    url = serve(ITEM_THREAD_PAGE)
    d = serve.page_dir
    panel_comment(
        d, "Budgets are tight.", {"section": "lead", "quote": "latency budgets"}
    )
    about_item = answered_comment(
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
    item_thread = card.locator(f'.lf-page-thread[data-thread="{about_item}"]')

    # `m` lands on the item and its thread comes up in the card beside it, which `c`
    # continues rather than starting a second one.
    page.keyboard.press("m")
    expect(item).to_be_focused()
    expect(item_thread).to_be_visible()
    page.keyboard.press("c")
    expect(item_thread.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(item).to_be_focused()

    # From an item with no thread, `t` goes to the next thread after it in the document,
    # which is the task's. Back from there is the item's own thread, where, in the card,
    # the item is still where the user stands.
    page.keyboard.press("m")
    expect(page.locator("#ship-ask")).to_be_focused()
    page.keyboard.press("t")
    expect(card.locator(f'.lf-page-thread[data-thread="{about_task}"]')).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(item_thread).to_be_focused()
    expect(item).to_have_attribute("data-lf-item", "1")

    # The nested item's card shows its task's thread, which is about the task, so `c`
    # still starts the item a thread of its own.
    page.keyboard.press("m")
    expect(page.locator("#ship-ask")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#retry-ask")).to_be_focused()
    expect(card.locator(f'.lf-page-thread[data-thread="{about_task}"]')).to_be_visible()


def test_an_item_in_a_reply_is_where_the_user_stands_once_answered(browser, serve):
    """An item frozen into a reply sits in a thread about a page lf-ask. Standing in the
    reply's item is standing there whether or not it is answered: the thread leads to
    its page item only from a node inside no item, so a user back on the answered option
    does not have the page item's ring and digits. A contributed control for a widget in
    the reply stands nowhere, since its widget is chrome in no item, so `m` from it
    starts where the reader is rather than behind every item on the page."""
    url = serve(
        ITEM_THREAD_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    d = serve.page_dir
    about_item = panel_comment(d, "Which one lasts longer?", {"section": "cache-ask"})
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": about_item,
            "responds": about_item,
            "text": "One question first.",
            "markup": '<lf-ask id="follow-ask"><h3>Measure it first?</h3>'
            '<lf-options id="follow" choose>'
            '<lf-option id="follow-yes">Measure first</lf-option>'
            '<lf-option id="follow-no">Decide now</lf-option>'
            "</lf-options></lf-ask>"
            f'<lf-shot id="follow-shot" alt="the cache before and after" '
            f'before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>',
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, about_item)
    page.evaluate(
        """async (thread) => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      registerContribution({key: 'reply-capture',
        target: document.querySelector(`${thread} lf-shot`),
        read: () => ({entries: [contributionEntry({key: 'review', glyph: 'R',
          label: 'Review reply capture'})]}), activate: () => {},
      });
    }""",
        PANEL_THREAD,
    )
    contributed = page.locator(PANEL_THREAD).get_by_role(
        "button", name="Review reply capture", exact=True
    )
    expect(contributed).to_be_visible()
    contributed.focus()
    page.keyboard.press("m")
    expect(page.locator("#cache-ask")).to_be_focused()
    option = page.locator("#follow-yes")
    option.click()
    expect(option).to_have_attribute("chosen", "")
    # Back on the answered option, the user stands in the reply's lf-ask. Answering moves
    # focus to the message, which is inside no item and so does stand at the page lf-ask.
    round_trip(page)
    option.locator(".lf-pick").focus()
    expect(page.locator("#cache-ask")).not_to_have_attribute("data-lf-item", "1")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#cache-disk")).not_to_have_attribute("chosen", "")


ITEM_IN_A_PANE_PAGE = leaf_page(
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
        <lf-ask id="pane-decision">
          <h3>How should the probe page?</h3>
          <lf-options id="pane-choice" choose>
            <lf-option id="pane-a"><strong>Require three failures</strong> Quieter.</lf-option>
            <lf-option id="pane-b"><strong>Keep one failure</strong> Louder.</lf-option>
          </lf-options>
        </lf-ask>
        <div style="height: 900px"></div>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("ask-split"),
    layout="workspace",
)


def test_an_item_landed_in_a_pane_keeps_its_ring_inside_the_pane(browser, serve):
    """An item walk lands the decision at the start of the pane that scrolls it, and the
    item wears the ring outside its box. The landing keeps the ring's room at the pane's
    edge, as the browser's own landing does for a box asking for it: the item stood
    flush with the pane's top, the top of its ring cut off under the pane's header
    rule."""
    page = open_page(browser, serve(ITEM_IN_A_PANE_PAGE))
    resized(page, 1440, 900)
    pane_posture(page, page.locator("#ask-detail"), "bounded")
    page.keyboard.press("m")
    item = page.locator("#pane-decision")
    expect(item).to_be_focused()
    expect(item).to_have_attribute("data-lf-item", "1")
    scroll_settled(page, "#ask-detail > :not(header, footer)")
    reading = item.evaluate(
        """ask => {
          const body = ask.closest('lf-pane').querySelector(':scope > :not(header, footer)');
          const style = getComputedStyle(ask);
          const ring = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
          return {ringTop: ask.getBoundingClientRect().top - ring,
                  paneTop: body.getBoundingClientRect().top + body.clientTop};
        }"""
    )
    assert reading["ringTop"] >= reading["paneTop"] - 0.5, reading
