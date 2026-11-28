"""Boards: the column each card announces, keyboard moves that keep the card in view,
grips, narrow and phone layouts, releasing a detached board, and cards that show a
section's answer."""

import re
from itertools import pairwise

import pytest
from interact_support import append_command, stamp
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, live_url
from render_cases_navigation import actions
from render_cases_widgets import SQUEEZED_BOARD_PAGE
from render_harness import (
    BOARD_PAGE,
    PREVIEW,
    clocked,
    consume_browser_errors,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    tab_onto,
    told,
    undo,
    wait_for_check_api,
    wait_for_revision,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


TALL_BOARD_PAGE = leaf_page(
    "tall board",
    """
<h1 id="t">Sprint</h1>
<lf-board id="crowd">
  <lf-column id="sq-col-0" label="Lane 0">
"""
    + "".join(
        f"""    <lf-card id="sq-card-{i}" label="Perch {i}">    <strong>Perch {i}</strong> The warden has documented every reading she takes at dawn.</lf-card>
"""
        for i in range(8)
    )
    + """  </lf-column>
</lf-board>
""",
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("hand", ["pointer", "keyboard"])
def test_a_revision_waits_for_a_held_card(engine, hand, request, serve):
    """A revision that rewords a card replaces the board. One that arrives while the user
    holds a card, by the pointer or by the keyboard, waits until the card is put down:
    the board under the hand stays, the move is recorded, and the revision then arrives
    with the card where the user put it."""
    page = open_page(request.getfixturevalue(engine), live_url(serve(BOARD_PAGE)))
    page.locator("#sprint").evaluate("board => { window.heldBoard = board; }")
    grip = page.locator("#card-heater .lf-grip")
    if hand == "pointer":
        box = grip.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        done = page.locator("#col-done").bounding_box()
        page.mouse.move(
            done["x"] + done["width"] / 2, done["y"] + done["height"] / 2, steps=8
        )
    else:
        grip.focus()
        page.keyboard.press("Enter")
        page.keyboard.press("ArrowRight")
    wait_for_check_api(page, "(api) => api.dragHeld()")

    stamp_page(
        serve.page_dir,
        BOARD_PAGE.replace(
            "<strong>Squirrel baffle</strong>",
            "<strong>Squirrel baffle, reworded</strong>",
        ),
        "reword a card",
    )
    told(page)
    assert page.evaluate(
        "() => window.heldBoard.isConnected"
        " && document.querySelector('meta[name=lf-revision][data-lf-runtime]')"
        ".content === '1'"
    ), "the revision replaced the board under the user's hand"

    if hand == "pointer":
        page.mouse.up()
    else:
        page.keyboard.press("Enter")
    wait_for_revision(page, 2)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    expect(page.locator("#card-baffle")).to_contain_text("reworded")
    moves = [e for e in actions(serve.page_dir) if e["action"] == "move"]
    assert [(m["detail"]["unit"], m["detail"]["value"]) for m in moves] == [
        ("card-heater", "col-done")
    ]


def test_a_detached_board_releases_and_restores_its_lifecycle(browser, serve):
    """Version replacement releases board resources and restores pointer dragging."""
    context = browser.new_context(viewport={"width": 1000, "height": 800})
    context.add_init_script(
        """(() => {
          window.__lfMotionListeners = {added: 0, removed: 0};
          const add = MediaQueryList.prototype.addEventListener;
          const remove = MediaQueryList.prototype.removeEventListener;
          MediaQueryList.prototype.addEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.added++;
            return add.call(this, type, listener, options);
          };
          MediaQueryList.prototype.removeEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.removed++;
            return remove.call(this, type, listener, options);
          };
        })()"""
    )
    try:
        page = open_page(browser, serve(BOARD_PAGE), context=context)
        cdp = context.new_cdp_session(page)
        # The board's own specifier, which the document's import map sends to the
        # revision, so this is the instance the board constructs from.
        page.evaluate(
            """async () => {
              window.__lfSortablePrototype =
                (await window.__lfVendorImport("sortable.esm.js")).default.prototype;
            }"""
        )

        def sortable_count():
            # Keep the query handles in a disposable group. In particular, the probe
            # must not become the new owner of the DOM it is checking.
            group = "board-lifecycle-probe"
            prototype = cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "window.__lfSortablePrototype",
                    "returnByValue": False,
                    "objectGroup": group,
                },
            )["result"]["objectId"]
            try:
                objects = cdp.send(
                    "Runtime.queryObjects",
                    {"prototypeObjectId": prototype, "objectGroup": group},
                )["objects"]["objectId"]
                return cdp.send(
                    "Runtime.callFunctionOn",
                    {
                        "objectId": objects,
                        "functionDeclaration": "function () { return this.length; }",
                        "returnByValue": True,
                    },
                )["result"]["value"]
            finally:
                cdp.send("Runtime.releaseObjectGroup", {"objectGroup": group})

        before = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert sortable_count() == 2
        page.evaluate(
            """() => {
              window.__lfDetachedBoard = document.querySelector('lf-board');
              window.__lfDetachedBoard.remove();
            }"""
        )
        released = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert released["removed"] > before["removed"], (
            f"detaching the board retained its motion listener: {before=}, {released=}"
        )
        cdp.send("HeapProfiler.collectGarbage")
        assert sortable_count() == 0, (
            "detaching the board retained its Sortable instances"
        )
        page.evaluate(
            "() => document.querySelector('main').append(window.__lfDetachedBoard)"
        )
        restored = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert restored["added"] > before["added"], (
            f"reconnecting the board did not restore live motion changes: {restored=}"
        )
        assert sortable_count() == 2

        grip = page.locator("#card-heater .lf-grip").bounding_box()
        dest = page.locator("#col-done").bounding_box()
        page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            dest["x"] + dest["width"] / 2,
            dest["y"] + dest["height"] / 2,
            steps=15,
        )
        page.mouse.up()
        page.wait_for_selector("#col-done #card-heater")
    finally:
        if "cdp" in locals():
            cdp.detach()


def test_a_board_says_which_column_each_card_is_in(browser, serve):
    """Which column a card sits in is the one fact about it that isn't in its own
    text, and columns are three boxes side by side — geometry, which the
    accessibility tree doesn't carry. Flat, this board would be its text runs and its
    Move buttons in a row: no boundary between the columns, and no button saying where
    its card was.

    Both halves are asserted from the tree itself rather than from the attributes
    behind it, because that is where they can be wrong: the column heading is CSS
    generated content, so the name reaching the tree once (as the list's) rather
    than twice depends on its alt text. Then a card moves, and the assertion is
    the second snapshot — a name set where the move happens goes stale on
    whichever path forgets to restate its location. The runtime's one quiet origin word
    remains on the card rather than being repeated in the Move control's name."""
    page = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"'\n"
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Todo\"'\n"
        '- list "Done"'  # empty, and still announced: it is a drop target
    )

    # Grab the second card and push it into the next column, the keyboard's path. The
    # grip's own Enter and Space grab it, which its preview names, and the grab tells a
    # listener where the card starts and which keys act on it now.
    tab_onto(board.get_by_role("button", name="Move: Squirrel baffle — Todo"))
    expect(page.locator(f"{PREVIEW} .lf-preview-keys")).to_have_text(["⏎", "space"])
    page.keyboard.press("Enter")
    expect(page.locator(".lf-live")).to_have_text(
        "Squirrel baffle grabbed — Todo, position 2 of 2 — "
        "arrows move, Enter or Space drop, Escape cancel the move"
    )
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    page.wait_for_selector("#col-done #card-baffle")
    expect(
        board.get_by_role(
            "button",
            name="Move: Squirrel baffle — Done",
            exact=True,
        )
    ).to_be_visible()
    expect(page.locator("#card-baffle > .lf-quiet")).to_have_text("my change")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"'\n"
        '- list "Done":\n'
        "  - listitem:\n"
        "    - text: my change\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Done\"'"
    )


# The width at which the eight-column board stands wider than 640px, so it scrolls
# sideways rather than stacking, and narrower than its columns' floor.
SIDEWAYS = 720


# Each scroller pairs with one motion setting: the board's own scrollport tracks the
# card's FLIP, and the document follows a move made at once. A column move on a
# stacked board travels the document too, down to the column below.
@pytest.mark.parametrize(
    ("axis", "source", "key", "steps", "reduced_motion", "width"),
    [
        pytest.param(
            "column",
            SQUEEZED_BOARD_PAGE,
            "ArrowRight",
            4,
            "no-preference",
            SIDEWAYS,
            id="columns",
        ),
        pytest.param("row", TALL_BOARD_PAGE, "ArrowDown", 7, "reduce", 390, id="rows"),
        pytest.param(
            "stacked",
            SQUEEZED_BOARD_PAGE,
            "ArrowRight",
            4,
            "no-preference",
            390,
            id="stacked",
        ),
    ],
)
def test_a_keyboard_move_keeps_the_card_in_view(
    browser, serve, reduced_motion, axis, source, key, steps, width
):
    """A move and its Escape return keep the focused card on screen."""
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion=reduced_motion)
    resized(page, width, 500)
    board = page.locator("#crowd")
    card = page.locator("#sq-card-0")
    grip = card.locator(".lf-grip")

    if axis == "column":
        assert board.evaluate("el => el.scrollWidth > el.clientWidth"), (
            "the board fits, so the keyboard move has no hidden column to reveal"
        )
    elif axis == "row":
        assert page.locator("#sq-card-7").evaluate(
            "el => el.getBoundingClientRect().bottom > innerHeight"
        ), "the lane fits, so the row move has no hidden destination to reveal"
    else:
        assert board.evaluate(
            """el => {
              const [first, second] = [...el.querySelectorAll(':scope > lf-column')]
                .map(column => column.getBoundingClientRect());
              return second.top >= first.bottom
                && el.querySelector('#sq-col-4').getBoundingClientRect().top > innerHeight;
            }"""
        ), "the board is not stacked past the window, so the move reveals nothing"

    def wait_for_placement(column, row):
        placement = """([column, row, axis]) => {
          const board = document.querySelector('#crowd');
          const card = board.querySelector('#sq-card-0');
          const cards = [...card.parentElement.querySelectorAll(':scope > lf-card')];
          const outer = board.getBoundingClientRect();
          const inner = card.getBoundingClientRect();
          const visible = axis === 'column'
            ? inner.left >= outer.left - 1 && inner.right <= outer.right + 1
            : inner.top >= -1 && inner.bottom <= innerHeight + 1;
          return card.parentElement.id === `sq-col-${column}`
            && cards.indexOf(card) === row && card.getAnimations().length === 0
            && visible;
        }"""
        where = [column, row, axis]
        page.wait_for_function(placement, arg=where)
        # A move along side-by-side columns travels the board's own scrollport; a move
        # down a column, or along stacked columns, travels the document.
        if axis == "column":
            scroll_settled(page, scroller="#crowd", axis="x")
        else:
            scroll_settled(page)
        page.wait_for_function(placement, arg=where)

    grip.focus()
    page.keyboard.press("Enter")
    for step in range(1, steps + 1):
        page.keyboard.press(key)
        # Each key gets its own rendered placement. Otherwise a later press can cancel
        # the prior FLIP before the test has exercised its scroll tracking.
        wait_for_placement(step if axis != "row" else 0, step if axis == "row" else 0)

    page.keyboard.press("Escape")
    wait_for_placement(0, 0)
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)
    expect(grip).to_be_focused()


def test_a_sideways_board_keeps_a_card_s_words_whole(browser, serve, subtests):
    """A board that runs past its width keeps each card's words whole: at its floor it
    scrolls rather than breaking them across lines, and Tab onto a grip brings the
    whole card in, where the browser's own scroll would stop at the grip."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))

    with subtests.test("at its floor it scrolls rather than breaking a word"):
        # A board lays its columns into whatever width it is given and scrolls once they
        # are as narrow as they go, which is the right order, but the floor has to know
        # what a column costs before it can say where narrow enough stops. Stated as the
        # column's own box, the floor would spend much of it on the column's inset and
        # border, the card's inset and border, and the column the drag grip hangs in,
        # leaving the card's prose narrower than an ordinary word of the page's own
        # serif, so the board would break ordinary words across lines the moment the
        # thread strip took its margin.
        #
        # The reading is the visible failure and not the number behind it. A word set
        # across two lines with no hyphen is what the user sees, and it is what the
        # page-wide `overflow-wrap` does with a box narrower than the word it has to
        # show. The premise is asserted first: the board must be at its floor and
        # scrolling for the rest, or a board that simply fitted would pass this while
        # proving nothing.
        measured = page.evaluate(
            """() => {
            const board = document.getElementById('crowd');
            const columns = [...board.querySelectorAll('lf-column')];
            // A word broken to fit lands on two lines with no break opportunity in it, so
            // the rects a range over it returns sit at two different tops. Ordinary words
            // only: a path or a sha has nowhere to break and breaking one is the page's
            // own bargain, not this floor's business.
            const range = document.createRange(), broken = [];
            for (const card of board.querySelectorAll('lf-card')) {
                const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
                for (let node = walker.nextNode(); node; node = walker.nextNode())
                    for (const m of node.textContent.matchAll(/[^\\s]+/g)) {
                        if (!/^[A-Za-z]+[.,;:]?$/.test(m[0])) continue;
                        range.setStart(node, m.index);
                        range.setEnd(node, m.index + m[0].length);
                        const rects = [...range.getClientRects()];
                        if (new Set(rects.map((r) => Math.round(r.top))).size > 1)
                            broken.push(m[0]);
                    }
            }
            const card = board.querySelector('lf-card');
            const style = getComputedStyle(card), box = card.getBoundingClientRect();
            const measure = box.width - parseFloat(style.paddingLeft)
                - parseFloat(style.paddingRight) - parseFloat(style.borderLeftWidth)
                - parseFloat(style.borderRightWidth);
            return { broken,
                     scrolls: board.scrollWidth - board.clientWidth,
                     widths: columns.map((c) => c.getBoundingClientRect().width),
                     measure,
                     titleMeasure: measure - parseFloat(getComputedStyle(card, '::before').width) };
        }"""
        )
        # The premise, read off the layout rather than off the property behind it: a grid
        # of `1fr` tracks that scrolls has every track at its minimum, so a board that
        # scrolls is a board at its floor whatever the floor is written as. A board with
        # room to spare would pass the reading below while asking it nothing.
        assert measured["scrolls"] > 1 and len(set(measured["widths"])) == 1, (
            f"this board is not at its floor, so its words prove nothing: {measured}"
        )
        # The default board promises 136px for title words beside the grip. Check that
        # available line measure directly: a particular long word may exceed it in
        # another platform's font even when the allocation is correct.
        assert measured["titleMeasure"] >= 136 - 1, measured
        assert measured["broken"] == [], (
            f"a board at its floor gave each card {measured['measure']:.0f}px of measure "
            f"and broke {', '.join(sorted(set(measured['broken'])))} across two lines"
        )

    with subtests.test("Tab onto a grip reveals its whole card"):
        # The browser scrolls a sideways board only far enough to show the focused 30px
        # grip, which at a narrow width left the card's words cut off at the board's edge.
        resized(page, SIDEWAYS, 500)
        assert page.locator("#crowd").evaluate(
            "el => el.scrollWidth > el.clientWidth"
        ), "the board fits, so Tab has no hidden card to reveal"
        # A restored focus is not an arrival: it leaves the board where the user put it.
        assert page.evaluate(
            """() => {
              const board = document.querySelector('#crowd');
              const before = board.scrollLeft;
              document.querySelector('#sq-card-5 .lf-grip').focus({preventScroll: true});
              return board.scrollLeft === before;
            }"""
        )
        page.locator("#sq-card-0 .lf-grip").focus()
        whole = """() => {
          const card = document.activeElement.closest('lf-card');
          const outer = card.closest('lf-board').getBoundingClientRect();
          const inner = card.getBoundingClientRect();
          return inner.left >= outer.left - 1 && inner.right <= outer.right + 1;
        }"""
        for i in range(1, 4):
            page.keyboard.press("Tab")
            expect(page.locator(f"#sq-card-{i} .lf-grip")).to_be_focused()
            page.wait_for_function(whole)
        # Grabbing it says so with the card's contour, not a shadow the dark paper hides.
        page.keyboard.press("Enter")
        card = page.locator("#sq-card-3")
        expect(card).to_have_class(re.compile(r"\blf-lift\b"))
        accent, border = card.evaluate(
            """el => [getComputedStyle(document.documentElement).getPropertyValue('--lf-accent'),
                      getComputedStyle(el).borderTopColor]"""
        )
        rest = page.locator("#sq-card-2").evaluate(
            "el => getComputedStyle(el).borderTopColor"
        )
        assert border != rest, (border, rest, accent)


def test_on_a_stacked_board_a_vertical_step_past_a_column_s_end_enters_the_next(
    browser, serve
):
    """Where the columns stack, the column below is the next slot the user sees, so Down
    past a column's last card enters it at its top and Up past a first card enters the
    column above at its end; side by side, the step past an end still does nothing."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 390, 500)
    card = page.locator("#sq-card-0")
    grip = card.locator(".lf-grip")

    def placed(column, row):
        expect(page.locator(f"#sq-col-{column} > #sq-card-0")).to_have_count(1)
        assert (
            card.evaluate(
                "el => [...el.parentElement.querySelectorAll(':scope > lf-card')].indexOf(el)"
            )
            == row
        )

    grip.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    placed(1, 0)
    page.keyboard.press("ArrowDown")
    placed(1, 1)
    page.keyboard.press("ArrowDown")
    placed(2, 0)
    page.keyboard.press("ArrowUp")
    placed(1, 1)
    page.keyboard.press("ArrowUp")
    placed(1, 0)
    page.keyboard.press("ArrowUp")
    placed(0, 0)
    page.keyboard.press("ArrowUp")
    placed(0, 0)
    page.keyboard.press("Escape")
    placed(0, 0)
    expect(grip).to_be_focused()

    resized(page, SIDEWAYS, 500)
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    placed(0, 0)
    page.keyboard.press("Escape")
    placed(0, 0)


def test_cancelling_a_keyboard_move_stops_its_scroll(browser, serve):
    """Escape supersedes a reveal still travelling toward the abandoned placement."""
    page = open_page(browser, serve(TALL_BOARD_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 390, 500)
    card = page.locator("#sq-card-0")
    grip = card.locator(".lf-grip")

    grip.focus()
    page.keyboard.press("Enter")
    for _ in range(7):
        page.keyboard.press("ArrowDown")
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)
    assert (
        card.evaluate(
            "el => [...el.parentElement.querySelectorAll(':scope > lf-card')].indexOf(el)"
        )
        == 7
    )
    # Cancel once native reveal has started; the old origin can already be offscreen.
    page.wait_for_function("scrollY > 0")
    page.keyboard.press("Escape")

    # Read only once the document has held one position. Without cancellation, the
    # abandoned smooth reveal continues past Escape and settles with the restored,
    # focused card above the viewport.
    scroll_settled(page)
    page.wait_for_function(
        "() => document.querySelector('#sq-card-0').getAnimations().length === 0"
    )
    reading = card.evaluate(
        """el => {
          const cards = [...el.parentElement.querySelectorAll(':scope > lf-card')];
          const box = el.getBoundingClientRect();
          return {index: cards.indexOf(el), top: box.top, bottom: box.bottom,
                  viewport: innerHeight};
        }"""
    )
    assert reading["index"] == 0, reading
    assert reading["top"] >= -1 and reading["bottom"] <= reading["viewport"] + 1, (
        reading
    )
    expect(grip).to_be_focused()


@pytest.mark.parametrize("route", ["keyboard", "reading"])
def test_reversing_a_move_continues_from_the_painted_card(browser, serve, route):
    """A superseding move starts where the old animation currently paints."""
    page = open_page(browser, serve(BOARD_PAGE), init_script=HOLD_MOTION)
    page.emulate_media(reduced_motion="no-preference")
    card = page.locator("#card-heater")

    def place(key, column):
        if route == "keyboard":
            page.keyboard.press(key)
        else:
            card.evaluate(
                """(el, column) => void el.closest('lf-board').record(
                  'move',
                  {unit: el.id, value: column, rank: '0i'},
                  {says: 'Moved card'},
                )""",
                column,
            )
        expect(page.locator(f"#{column} #card-heater")).to_have_count(1)

    if route == "keyboard":
        card.locator(".lf-grip").focus()
        page.keyboard.press("Enter")
    place("ArrowRight", "col-done")
    first = card.evaluate(
        """el => {
          el.getAnimations()[0].currentTime = 75;
          const box = el.getBoundingClientRect();
          return {x: box.x, y: box.y};
        }"""
    )
    place("ArrowLeft", "col-todo")
    reverse = card.bounding_box()
    assert abs(reverse["x"] - first["x"]) < 1, (first, reverse)
    assert abs(reverse["y"] - first["y"]) < 1, (first, reverse)
    page.keyboard.press("Escape")


@pytest.mark.parametrize(
    "cancels",
    [("Escape", "pointercancel"), ("touchcancel",)],
    ids=["pointer-listeners", "touch-fallback"],
)
def test_cancelling_a_pointer_drag_restores_the_card_without_a_move(
    browser, serve, subtests, cancels
):
    """Cancelling tears down the drag; a later release cannot record its old preview."""
    # Safari uses Sortable's mouse/touch fallback instead of its pointer listeners.
    context = (
        browser.new_context(user_agent="Version/26.0 Safari/605.1.15")
        if "touchcancel" in cancels
        else None
    )
    page = open_page(browser, serve(BOARD_PAGE), context=context)
    posts = []
    page.on(
        "request",
        lambda request: posts.append(request) if "/api/event" in request.url else None,
    )
    for cancel in cancels:
        with subtests.test(cancel=cancel):
            grip = page.locator("#card-heater .lf-grip").bounding_box()
            dest = page.locator("#col-done").bounding_box()
            page.mouse.move(
                grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2
            )
            page.mouse.down()
            page.mouse.move(
                dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
            )
            expect(page.locator("#col-done #card-heater")).to_have_count(1)
            if cancel == "Escape":
                page.keyboard.press("Escape")
            else:
                page.evaluate(
                    "type => document.dispatchEvent(type === 'pointercancel' ? new PointerEvent(type) : new TouchEvent(type))",
                    cancel,
                )
            expect(page.locator("#col-todo #card-heater")).to_have_count(1)
            expect(page.locator(".lf-ghost, .lf-lift, .lf-inhand")).to_have_count(0)
            page.mouse.up()
            # The card glides home, and the next drag presses its grip where it rests.
            page.wait_for_function(
                "() => !document.querySelector('#card-heater').getAnimations().length"
            )
    page.reload()
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    assert not posts


GRIPPED_CARD_PAGE = leaf_page(
    "Gripped card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a" label="Webhook retries ignore the Retry-After header">      <strong>Webhook retries ignore the Retry-After header</strong> Three partners rate limit us during their own deploys, and we back off on a fixed
      schedule that ignores what they asked for.</lf-card>
  </lf-column>
  <lf-column id="col-b" label="Defer">
    <lf-card id="plain" label="Plain"><strong>Plain</strong> The importer is wired.</lf-card>
    <lf-card id="element" label="Element"><strong>Element</strong> The <em>importer</em> is wired.</lf-card>
    <lf-card id="paragraph" label="Paragraph"><strong>Paragraph</strong> <p>The importer is wired.</p></lf-card>
  </lf-column>
  <lf-column id="col-c" label="Repro"></lf-column>
</lf-board>
""",
    # Justified, so each full line ends where the card lets it rather than at a word.
    head="<style>#card-a { text-align: justify; }</style>",
)


def test_a_card_s_title_clears_its_grip_and_its_prose_starts_under_it(
    browser, serve, subtests
):
    """Below the title a card's prose reads alike, however the author wrote it, and runs
    the card's whole width."""
    page = open_page(browser, serve(GRIPPED_CARD_PAGE))

    with subtests.test("only the title clears the grip"):
        # The grip stands at the card's top corner and the lines beside it, the title's,
        # stop short of it; the prose below runs the card's whole width, rather than in a
        # column that keeps clear of the grip down the card's full height. No
        # line stands under the grip's box, so a press there is always the grip's.
        measured = page.locator("#card-a").evaluate(
            """(card) => {
            const grip = card.querySelector(':scope > .lf-grip').getBoundingClientRect();
            const range = document.createRange(), lines = [];
            const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                if (node.parentElement.closest('.lf-grip') || !node.textContent.trim()) continue;
                range.selectNodeContents(node);
                for (const r of range.getClientRects())
                    lines.push({title: node.parentElement.matches('strong'),
                                top: r.top, bottom: r.bottom, right: r.right});
            }
            const beside = (l) => l.top < grip.bottom && l.bottom > grip.top;
            return {
                under: lines.filter((l) => beside(l) && l.right > grip.left).length,
                titleBeside: lines.some((l) => l.title && beside(l)),
                // Past the grip's left edge is the room the column held back.
                prose: lines.filter((l) => !l.title && !beside(l)).slice(0, -1)
                    .map((l) => Math.round(l.right - grip.left)),
            };
        }"""
        )
        assert measured["titleBeside"], measured
        assert measured["under"] == 0, measured
        # Every full line of prose below the grip runs into the room beneath it.
        assert measured["prose"] and all(d > 0 for d in measured["prose"]), measured

    with subtests.test("the prose starts under its title in every shape"):
        # Authors follow a card's title with a plain sentence, one holding an inline
        # element, or a paragraph, and each card reads alike: the title's margin set a
        # sentence holding an element 2px lower than a plain one, and a paragraph's
        # margin set it 13px lower.
        gaps = page.evaluate(
            """() => Object.fromEntries(['plain', 'element', 'paragraph'].map((id) => {
              const card = document.getElementById(id);
              const title = card.querySelector(':scope > strong');
              const walk = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
              walk.currentNode = title.lastChild;
              let text = walk.nextNode();
              while (!text.data.trim()) text = walk.nextNode();
              const range = document.createRange();
              range.selectNodeContents(text);
              return [id, range.getClientRects()[0].top - title.getBoundingClientRect().bottom];
            }))"""
        )
        for shape in ("element", "paragraph"):
            assert gaps[shape] == pytest.approx(gaps["plain"], abs=1), gaps


GRIPPED_BLOCK_CARD_PAGE = leaf_page(
    "Gripped block card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a" label="Retries ignore Retry-After">      <strong>Retries ignore Retry-After</strong> <pre id="card-a-code">retry(after=fixed(30))</pre>
      <p id="card-a-note">Three partners rate limit us during their own deploys.</p>
    </lf-card>
  </lf-column>
</lf-board>
""",
)


def test_a_grip_taller_than_its_title_leaves_the_blocks_under_it_their_width(
    browser, serve
):
    """The grip, a symbol's face tall, reaches past a one-line title. A block after the
    title that lays itself out on its own (a pre), set beside the grip's room for its
    whole height, would be narrower than the card; a block after the title clears the
    grip and takes the card's width, and nothing stands under the grip's box."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(GRIPPED_BLOCK_CARD_PAGE), context=context)
    measured = page.locator("#card-a").evaluate(
        """(card) => {
        const grip = card.querySelector(':scope > .lf-grip').getBoundingClientRect();
        const s = getComputedStyle(card), box = card.getBoundingClientRect();
        const content = box.width - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)
            - parseFloat(s.borderLeftWidth) - parseFloat(s.borderRightWidth);
        const title = card.querySelector(':scope > strong')
            .getBoundingClientRect();
        const blocks = ['#card-a-code', '#card-a-note'].map((id) =>
            card.querySelector(id).getBoundingClientRect());
        const under = (b) => b.top < grip.bottom && b.bottom > grip.top
            && b.right > grip.left;
        return {grip: Math.round(grip.height), title: Math.round(title.height),
                widths: blocks.map((b) => Math.round(content - b.width)),
                under: blocks.filter(under).length};
    }"""
    )
    # The premise: the grip reaches past the title's one line.
    assert measured["grip"] > measured["title"], measured
    assert measured["widths"] == [0, 0], measured
    assert measured["under"] == 0, measured


def test_a_phone_board_stacks_its_columns_and_moves_a_card_by_its_destination_buttons(
    browser, serve
):
    """A phone stacks the board's columns, each the board's width and its own height,
    and moves a card without a distant drop target.

    The board paged sideways here, one column wide with a sliver of the next as the
    cue, which left one column on screen, every other behind a sideways swipe nothing
    else on the page asks for, and each column stretched to the tallest one's height.
    Stacked, every column is a scroll down away, and a card still cannot be dragged to a
    distant column under a finger, so the phone offers every other column on the card
    and a move follows the card to where it landed.
    """
    context = browser.new_context(
        viewport={"width": 390, "height": 900}, has_touch=True
    )
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE), context=context)
    columns_of = """board => {
        const box = board.getBoundingClientRect();
        const columns = [...board.querySelectorAll(':scope > lf-column')]
          .map(column => column.getBoundingClientRect());
        return {board: box, columns,
                scrolls: board.scrollWidth > board.clientWidth};
    }"""
    measured = page.locator("#crowd").evaluate(columns_of)
    board = measured["board"]
    columns = measured["columns"]
    assert len(columns) == 8, measured
    for column in columns:
        assert abs(column["left"] - board["left"]) <= 1, measured
        assert abs(column["right"] - board["right"]) <= 1, measured
    for above, below in pairwise(columns):
        assert above["bottom"] <= below["top"], measured
    assert not measured["scrolls"], measured

    card = page.locator("#sq-card-0")
    expect(card.locator(".lf-grip")).to_be_visible()
    to_lane_1 = card.get_by_role("button", name="Move Perch 0 to Lane 1")
    expect(to_lane_1).to_be_visible()
    with sending(page, "the phone category move"):
        to_lane_1.tap()
    expect(page.locator("#sq-col-1 > #sq-card-0")).to_have_count(1)
    expect(card.locator(".lf-grip")).to_be_focused()
    # The move carries the view to the card where it landed, among its new neighbours.
    page.wait_for_function(
        """() => {
          const moved = document.querySelector('#sq-card-0');
          if (moved.getAnimations().length) return false;
          const card = moved.getBoundingClientRect();
          return card.top >= 0 && card.bottom <= innerHeight;
        }"""
    )
    # Each column is its own height: the emptied lane stands at its floor above the lane
    # now holding two cards.
    after = page.locator("#crowd").evaluate(columns_of)
    emptied, filled = after["columns"][:2]
    assert emptied["height"] < filled["height"], after
    assert emptied["bottom"] <= filled["top"], after

    to_lane_0 = card.get_by_role("button", name="Move Perch 0 to Lane 0")
    expect(to_lane_0).to_be_visible()
    with sending(page, "the phone return move"):
        to_lane_0.tap()
    expect(page.locator("#sq-col-0 > #sq-card-0")).to_have_count(1)


ANSWERS_BOARD_PAGE = leaf_page(
    "proposals",
    """
<h1 id="t">Proposals</h1>
<lf-group id="rail-section" label="Keep the rail beside the text">
  <h2 id="rail-section-h">Keep the rail beside the text</h2>
  <lf-options id="rail">
    <lf-option id="rail-next" value="next">Next</lf-option>
    <lf-option id="rail-later" value="later" selected>Later</lf-option>
  </lf-options>
</lf-group>
<lf-board id="plan">
  <lf-column id="col-open" label="Undecided"></lf-column>
  <lf-column id="col-next" label="Next" value="next"></lf-column>
  <lf-column id="col-later" label="Later" value="later">
    <lf-card id="card-rail" label="Keep the rail" shows="rail"><strong>Keep the rail</strong></lf-card>
  </lf-column>
</lf-board>
""",
)


def test_a_section_and_a_board_answer_one_decision(browser, serve):
    """The card shows the section's answer and changes it through the section's own
    command, so a pick and a drop are one fact at one coordinate, and both views follow
    its undo, its refusal and a version that rewrites the picked option, which takes
    the pick back and leaves the card undecided."""
    page = open_page(browser, live_url(serve(ANSWERS_BOARD_PAGE)))
    grip = page.locator("#card-rail .lf-grip")

    def stands(column, option):
        expect(page.locator(f"#{column} > #card-rail")).to_have_count(1)
        chosen = page.locator("#rail > lf-option[selected]")
        if option:
            expect(chosen).to_have_attribute("id", option)
        else:
            expect(chosen).to_have_count(0)

    def drop(key):
        grip.focus()
        for press in ("Enter", key, "Enter"):
            page.keyboard.press(press)

    def picks():
        return [
            (event["widget"], event["action"], event["detail"])
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "action"
        ]

    with sending(page, "the pick"):
        page.locator("#rail-next").click()
    stands("col-next", "rail-next")
    with sending(page, "the drop"):
        drop("ArrowLeft")
    stands("col-open", None)
    assert picks() == [
        ("rail", "choose", {"value": ["rail-next"]}),
        ("rail", "choose", {"value": []}),
    ]

    page.locator("#rail-section").scroll_into_view_if_needed()
    undo(page)
    stands("col-next", "rail-next")
    # The options record the drop under the card's words, so Undo names the move.
    expect(page.locator(".lf-live")).to_have_text(
        "Undone: Moved “Keep the rail” to Undecided just now"
    )

    (serve.page_dir / "index.html").write_text(
        ANSWERS_BOARD_PAGE.replace(
            '<lf-option id="rail-next" value="next">',
            '<lf-option id="rail-next" value="next" restated>',
        )
    )
    assert stamp(serve.page_dir, "Ask again").exit_code == 0
    told(page)
    stands("col-open", None)

    def refuse(route):
        attempt = route.request.post_data_json["attempt"]
        body = {"ok": False, "attempt": attempt, "error": "refused", "final": True}
        route.fulfill(status=400, json=body)

    page.route("**/api/event", refuse)
    with page.expect_response(lambda response: "/api/event" in response.url):
        drop("ArrowRight")
    stands("col-open", None)
    page.unroute("**/api/event")
    consume_browser_errors(page, http_error_console(400))
    assert len(picks()) == 2


def test_a_card_offers_the_columns_its_choice_takes_once_the_choice_arrives(
    browser, serve
):
    """A board can set up before the question's choice reaches its card, as when the
    options' module loads last. A card the markup already stands in its choice's
    column then still offers a button for each other column the choice takes, once
    the choice arrives."""
    page = open_page(browser, live_url(serve(ANSWERS_BOARD_PAGE)))
    held = []
    page.route("**/widgets/lf-options.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    holding(page, held, 1, "the options module")
    expect(page.locator("#card-rail .lf-grip")).to_be_attached()
    held[0].continue_()
    page.unroute("**/widgets/lf-options.js")
    wait_until_ready(page)
    expect(page.locator("#col-later > #card-rail")).to_have_count(1)
    for column, offered in (
        ("col-open", True),
        ("col-next", True),
        ("col-later", False),
    ):
        expect(
            page.locator(f'#card-rail [data-lf-board-target="{column}"]')
        ).to_have_js_property("hidden", not offered)


@pytest.mark.parametrize(
    ("rewritten", "step", "asked"),
    [
        # Leaf has bound the card to `rail`, so the drop asks `rail`.
        ("once the card has drawn", "ArrowLeft", "rail"),
        # Leaf binds the card to `other`, so the drop asks `other`.
        ("as the card's class is defined", "ArrowRight", "other"),
    ],
)
def test_a_drop_asks_the_widget_whose_choice_the_card_shows(
    browser, serve, rewritten, step, asked
):
    """The card's binding names both the choice it shows and the widget its drop asks,
    whenever a script rewrites `shows`: the drop asks the widget whose choice the card
    stands by."""
    source = ANSWERS_BOARD_PAGE.replace(
        '<lf-board id="plan">',
        '<lf-group id="other-section" label="Keep the other rail?">'
        '<h2 id="other-section-h">Keep the other rail?</h2><lf-options id="other">'
        '<lf-option id="other-next" value="next">Next</lf-option>'
        '<lf-option id="other-later" value="later">Later</lf-option>'
        '</lf-options></lf-group><lf-board id="plan">',
    )
    rewrite = "document.getElementById('card-rail').setAttribute('shows', 'other')"
    context = browser.new_context()
    if rewritten.startswith("as"):
        context.add_init_script(
            f"customElements.whenDefined('lf-card').then(() => {rewrite});"
        )
    page = open_page(browser, live_url(serve(source)), context=context)
    if rewritten.startswith("once"):
        expect(page.locator("#col-later > #card-rail")).to_have_count(1)
        page.evaluate(rewrite)

    with sending(page, "the drop"):
        page.locator("#card-rail .lf-grip").focus()
        for press in ("Enter", step, "Enter"):
            page.keyboard.press(press)
    expect(page.locator("#col-next > #card-rail")).to_have_count(1)
    assert [
        (event["widget"], event["action"], event["detail"])
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ] == [(asked, "choose", {"value": [f"{asked}-next"]})]


def test_a_card_with_shows_never_stands_by_a_board_move(browser, serve):
    """The append door admits a board move of a card with `shows`, which the board's
    module never sends. Such a move in the log leaves the card in the column its
    choice names."""
    page = open_page(browser, live_url(serve(ANSWERS_BOARD_PAGE)))
    expect(page.locator("#col-later > #card-rail")).to_have_count(1)

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan",
            "action": "move",
            "detail": {"unit": "card-rail", "value": "col-next", "rank": "i"},
        },
    )
    told(page)
    expect(page.locator("#col-later > #card-rail")).to_have_count(1)


def test_an_answer_naming_no_one_column_stands_with_the_undecided(browser, serve):
    """A card stands in the first column without a `value` while its answer names no
    one column: a pick whose value no column holds, or the picks of a `multiple`
    question that name different values."""
    source = (
        ANSWERS_BOARD_PAGE.replace(
            '<lf-option id="rail-later" value="later" selected>Later</lf-option>',
            '<lf-option id="rail-later" value="later" selected>Later</lf-option>'
            '<lf-option id="rail-someday" value="someday">Someday</lf-option>',
        )
        .replace(
            '<lf-board id="plan">',
            '<lf-group id="pager-section" label="Page the on-call">'
            '<h2 id="pager-section-h">Page the on-call</h2>'
            '<lf-options id="pager" multiple>'
            '<lf-option id="pager-next" value="next">Next</lf-option>'
            '<lf-option id="pager-later" value="later">Later</lf-option>'
            '</lf-options></lf-group><lf-board id="plan">',
        )
        .replace(
            '<lf-column id="col-open" label="Undecided"></lf-column>',
            '<lf-column id="col-open" label="Undecided">'
            '<lf-card id="card-pager" label="Page the on-call" shows="pager">'
            "<strong>Page the on-call</strong></lf-card></lf-column>",
        )
    )
    page = open_page(browser, live_url(serve(source)))
    expect(page.locator("#col-later > #card-rail")).to_have_count(1)
    with sending(page, "the pick"):
        page.locator("#rail-someday").click()
    expect(page.locator("#col-open > #card-rail")).to_have_count(1)

    with sending(page, "the pick"):
        page.locator("#pager-next").click()
    expect(page.locator("#col-next > #card-pager")).to_have_count(1)
    with sending(page, "the pick"):
        page.locator("#pager-later").click()
    expect(page.locator("#col-open > #card-pager")).to_have_count(1)


def test_an_option_without_a_value_answers_with_its_id(browser, serve):
    """An option that carries no `value` answers with its id, so a column whose `value`
    is that id holds the card while the option is picked, and a drop there picks it. A
    card whose `shows` is empty shows no answer, and is the board's own to move."""
    source = (
        ANSWERS_BOARD_PAGE.replace(' value="next">Next<', ">Next<")
        .replace(' value="later" selected>Later<', " selected>Later<")
        .replace('label="Next" value="next"', 'label="Next" value="rail-next"')
        .replace('label="Later" value="later"', 'label="Later" value="rail-later"')
        .replace(
            '<lf-column id="col-open" label="Undecided"></lf-column>',
            '<lf-column id="col-open" label="Undecided">'
            '<lf-card id="card-own" label="Own" shows="">'
            "<strong>Own</strong></lf-card></lf-column>",
        )
    )
    assert source.count(' value="rail-') == 2
    page = open_page(browser, live_url(serve(source)))
    expect(page.locator("#col-later > #card-rail")).to_have_count(1)

    with sending(page, "the drop"):
        page.locator("#card-rail .lf-grip").focus()
        for press in ("Enter", "ArrowLeft", "Enter"):
            page.keyboard.press(press)
    expect(page.locator("#col-next > #card-rail")).to_have_count(1)
    expect(page.locator("#rail-next")).to_have_attribute("selected", "")

    with sending(page, "the move"):
        page.locator("#card-own .lf-grip").focus()
        for press in ("Enter", "ArrowRight", "Enter"):
            page.keyboard.press(press)
    expect(page.locator("#col-next > #card-own")).to_have_count(1)
    assert [
        (event["widget"], event["action"], event["detail"].get("unit"))
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ] == [("rail", "choose", None), ("plan", "move", "card-own")]


def centre(locator):
    box = locator.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def test_a_column_two_options_name_takes_no_drop(browser, serve, subtests):
    """Two options carrying one `value` land a card in the same column, and a pick of
    either stands it there. A drop names only the value, not which of the two the user
    picks, so the column takes no drop of that card: it offers no button, a pointer
    drag opens no slot in it, the grip's arrow passes over it, and no pick of both
    options reaches the log. A card that no other column takes has nothing to offer:
    its grip is disabled and it shows no destinations."""
    source = (
        ANSWERS_BOARD_PAGE.replace(
            '<lf-option id="rail-next" value="next">Next</lf-option>',
            '<lf-option id="rail-next" value="next">Next</lf-option>'
            '<lf-option id="rail-soon" value="next">Soon</lf-option>',
        )
        .replace(
            '<lf-board id="plan">',
            '<lf-group id="pager-section" label="Page the on-call">'
            '<h2 id="pager-section-h">Page the on-call</h2>'
            '<lf-options id="pager">'
            '<lf-option id="pager-now" value="next">Now</lf-option>'
            '<lf-option id="pager-soon" value="next">Soon</lf-option>'
            '<lf-option id="pager-q3" value="later">Third quarter</lf-option>'
            '<lf-option id="pager-q4" value="later">Fourth quarter</lf-option>'
            '</lf-options></lf-group><lf-board id="plan">',
        )
        .replace(
            '<lf-column id="col-open" label="Undecided"></lf-column>',
            '<lf-column id="col-open" label="Undecided">'
            '<lf-card id="card-pager" label="Page the on-call" shows="pager">'
            "<strong>Page the on-call</strong></lf-card></lf-column>",
        )
    )
    assert source.count(' value="next"') == 5 and 'shows="pager"' in source
    # Sortable asks a column whether it takes the card on a 50 ms loop, which the test
    # runs forward itself.
    page = open_page(clocked(browser), live_url(serve(source)))

    def picks():
        return [
            (event["widget"], event["action"], event["detail"])
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "action"
        ]

    with subtests.test(card="one no other column takes"):
        # Each column with a value is named by two of the question's options, and the
        # card stands with the undecided.
        pager = page.locator("#card-pager")
        expect(page.locator("#col-open > #card-pager")).to_have_count(1)
        expect(pager.locator(".lf-grip")).to_have_attribute("aria-disabled", "true")
        expect(pager.locator(".lf-board-destinations")).to_have_js_property(
            "hidden", True
        )
        # Once a pick stands it in a column, the undecided column takes it back.
        with sending(page, "the pick"):
            page.locator("#pager-now").click()
        expect(page.locator("#col-next > #card-pager")).to_have_count(1)
        expect(pager.locator(".lf-grip")).to_have_attribute("aria-disabled", "false")
        expect(pager.locator(".lf-board-destinations")).to_have_js_property(
            "hidden", False
        )
        expect(pager.locator('[data-lf-board-target="col-open"]')).to_have_js_property(
            "hidden", False
        )
        assert picks() == [("pager", "choose", {"value": ["pager-now"]})]

    with subtests.test(card="one a column two options name"):
        card = page.locator("#card-rail")
        expect(page.locator("#col-later > #card-rail")).to_have_count(1)
        expect(card.locator('[data-lf-board-target="col-open"]')).to_have_js_property(
            "hidden", False
        )
        expect(card.locator('[data-lf-board-target="col-next"]')).to_have_js_property(
            "hidden", True
        )

        # A pointer drag resting over the column opens no slot there. The drag is live
        # once the card wears the slot's class, and the loop reads the pointer's last
        # move after that.
        page.mouse.move(*centre(card.locator(".lf-grip")))
        page.mouse.down()
        over_next = centre(page.locator("#col-next"))
        page.mouse.move(*over_next, steps=5)
        expect(card).to_have_class(re.compile(r"\blf-ghost\b"))
        page.mouse.move(over_next[0] + 2, over_next[1])
        page.clock.run_for(120)
        assert card.evaluate("card => card.parentElement.id") == "col-later"
        # The same drag still drops where a column takes the card.
        page.mouse.move(*centre(page.locator("#col-open")), steps=5)
        page.clock.run_for(120)
        expect(page.locator("#col-open > #card-rail")).to_have_count(1)
        with sending(page, "the pointer drop"):
            page.mouse.up()
        expect(page.locator("#col-open > #card-rail")).to_have_count(1)
        expect(page.locator("#rail > lf-option[selected]")).to_have_count(0)

        # The grip's arrow passes over the column on its way to the next that takes it.
        with sending(page, "the keyboard drop"):
            card.locator(".lf-grip").focus()
            for press in ("Enter", "ArrowRight", "Enter"):
                page.keyboard.press(press)
        expect(page.locator("#col-later > #card-rail")).to_have_count(1)
        with sending(page, "the pick"):
            page.locator("#rail-soon").click()
        expect(page.locator("#col-next > #card-rail")).to_have_count(1)
        assert picks()[1:] == [
            ("rail", "choose", {"value": []}),
            ("rail", "choose", {"value": ["rail-later"]}),
            ("rail", "choose", {"value": ["rail-soon"]}),
        ]


TWO_BOARDS_PAGE = leaf_page(
    "two boards",
    """
<h1 id="t">Two sprints</h1>
<lf-board id="a">
  <lf-column id="a-todo" label="Todo">
    <lf-card id="card-a" label="Heated perch"><strong>Heated perch</strong></lf-card>
  </lf-column>
  <lf-column id="a-done" label="Done"></lf-column>
</lf-board>
<lf-board id="b">
  <lf-column id="b-todo" label="Todo">
    <lf-card id="card-b" label="Squirrel baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="b-done" label="Done"></lf-column>
</lf-board>
""",
)


def test_a_card_stays_in_its_own_board(browser, serve):
    """A pointer drag resting over another board's column opens no slot there, and the
    same drag still drops in a column of the card's own board."""
    page = open_page(clocked(browser), live_url(serve(TWO_BOARDS_PAGE)))
    card = page.locator("#card-a")

    page.mouse.move(*centre(card.locator(".lf-grip")))
    page.mouse.down()
    over_other = centre(page.locator("#b-todo"))
    page.mouse.move(*over_other, steps=5)
    expect(card).to_have_class(re.compile(r"\blf-ghost\b"))
    page.mouse.move(over_other[0] + 2, over_other[1])
    page.clock.run_for(120)
    assert card.evaluate("card => card.parentElement.id") == "a-todo"

    page.mouse.move(*centre(page.locator("#a-done")), steps=5)
    page.clock.run_for(120)
    expect(page.locator("#a-done > #card-a")).to_have_count(1)
    with sending(page, "the pointer drop"):
        page.mouse.up()
    expect(page.locator("#a-done > #card-a")).to_have_count(1)
    expect(page.locator("lf-board#b lf-card")).to_have_count(1)
