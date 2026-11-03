"""Boards: the column each card announces, keyboard moves that keep the card in view,
grips, narrow and phone layouts, releasing a detached board, and cards that show a
section's answer."""

import re
from itertools import pairwise

import pytest
from interact_support import stamp
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, live_url
from render_cases_widgets import SQUEEZED_BOARD_PAGE
from render_harness import (
    BOARD_PAGE,
    consume_browser_errors,
    http_error_console,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    sending,
    told,
    undo,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


TALL_BOARD_PAGE = leaf_page(
    "tall board",
    """
<h1 id="t">Sprint</h1>
<lf-board id="crowd">
  <lf-column id="sq-col-0" label="Lane 0">
"""
    + "".join(
        f"""    <lf-card id="sq-card-{i}"><strong>Perch {i}</strong>
    The warden has documented every reading she takes at dawn.</lf-card>
"""
        for i in range(8)
    )
    + """  </lf-column>
</lf-board>
""",
)


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
    accessibility tree doesn't carry. Flat, this board was six text runs and two
    Move buttons in a row: no boundary between the columns, and no button saying
    where its card was.

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

    # Grab the second card and push it into the next column, the keyboard's path.
    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
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
        "    - strong: Squirrel baffle\n"
        "    - text: my change\n"
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


def test_tabbing_to_a_grip_reveals_its_whole_card(browser, serve):
    """The browser scrolls a sideways board only far enough to show the focused 30px
    grip, which at a narrow width left the card's words cut off at the board's edge."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))
    resized(page, SIDEWAYS, 500)
    assert page.locator("#crowd").evaluate("el => el.scrollWidth > el.clientWidth"), (
        "the board fits, so Tab has no hidden card to reveal"
    )
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
        """el => [getComputedStyle(document.documentElement).getPropertyValue('--accent'),
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
                """(el, column) => el.closest('lf-board').controller.dispatch({
                  kind: 'action', verb: 'move',
                  detail: {unit: el.id, value: column, rank: '0i'},
                  says: 'Moved card',
                })""",
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


@pytest.mark.parametrize("cancel", ["Escape", "pointercancel", "touchcancel"])
def test_cancelling_a_pointer_drag_restores_the_card_without_a_move(
    browser, serve, cancel
):
    """Cancelling tears down the drag; a later release cannot record its old preview."""
    # Safari uses Sortable's mouse/touch fallback instead of its pointer listeners.
    context = (
        browser.new_context(user_agent="Version/26.0 Safari/605.1.15")
        if cancel == "touchcancel"
        else None
    )
    page = open_page(browser, serve(BOARD_PAGE), context=context)
    posts = []
    page.on(
        "request",
        lambda request: posts.append(request) if "/api/event" in request.url else None,
    )
    grip = page.locator("#card-heater .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
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
    page.reload()
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    assert not posts


def test_a_board_at_its_floor_scrolls_rather_than_breaking_a_card_s_words(
    browser, serve
):
    """A board lays its columns into whatever width it is given and scrolls once they
    are as narrow as they go, which is the right order — but the floor has to know what
    a column costs before it can say where narrow enough stops. Stated as the column's
    own box (10rem), 70 of those 160 pixels were the column's inset and border, the
    card's inset and border, and the column the drag grip hangs in, and the card's prose
    got 90: `documented` is 92px of the page's own serif, so the shipped board broke
    ordinary words across lines the moment the thread strip took its margin.

    The reading is the visible failure and not the number behind it. A word set across
    two lines with no hyphen is what the user sees, and it is what the page-wide
    `overflow-wrap` does with a box narrower than the word it has to show — the bargain
    leaf makes for paths and shas, arriving here on an English sentence. The premise is
    asserted first: the board must be at its floor and scrolling for the rest, or a
    board that simply fitted would pass this while proving nothing."""
    page = open_page(browser, serve(SQUEEZED_BOARD_PAGE))
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
    # The premise, read off the layout rather than off the property behind it: a grid of
    # `1fr` tracks that scrolls has every track at its minimum, so a board that scrolls
    # is a board at its floor whatever the floor is written as. A board with room to
    # spare would pass the reading below while asking it nothing.
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


GRIPPED_CARD_PAGE = leaf_page(
    "Gripped card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a"><strong>Webhook retries ignore the Retry-After header</strong>
      Three partners rate limit us during their own deploys, and we back off on a fixed
      schedule that ignores what they asked for.</lf-card>
  </lf-column>
  <lf-column id="col-b" label="Defer"></lf-column>
  <lf-column id="col-c" label="Repro"></lf-column>
</lf-board>
""",
    # Justified, so each full line ends where the card lets it rather than at a word.
    head="<style>#card-a { text-align: justify; }</style>",
)


def test_only_a_card_s_title_clears_its_grip(browser, serve):
    """The grip stands at the card's top corner and the lines beside it, the title's,
    stop short of it; the prose below runs the card's whole width, where it used to be
    set in a column that kept clear of the grip down the card's full height. No line
    stands under the grip's box, so a press there is always the grip's."""
    page = open_page(browser, serve(GRIPPED_CARD_PAGE))
    measured = page.locator("#card-a").evaluate(
        """(card) => {
        const grip = card.querySelector(':scope > .lf-grip').getBoundingClientRect();
        const range = document.createRange(), lines = [];
        const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (node.parentElement.closest('.lf-grip') || !node.textContent.trim()) continue;
            range.selectNodeContents(node);
            for (const r of range.getClientRects())
                lines.push({title: node.parentElement.localName === 'strong',
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


GRIPPED_BLOCK_CARD_PAGE = leaf_page(
    "Gripped block card",
    """
<h1 id="t">Release triage</h1>
<lf-board id="gripped">
  <lf-column id="col-a" label="Fix in 2.4.1">
    <lf-card id="card-a"><strong>Retries ignore Retry-After</strong>
      <pre id="card-a-code">retry(after=fixed(30))</pre>
      <p id="card-a-note">Three partners rate limit us during their own deploys.</p>
    </lf-card>
  </lf-column>
</lf-board>
""",
)


def test_a_finger_s_taller_grip_leaves_the_blocks_under_a_title_their_width(
    browser, serve
):
    """Under a finger the grip is the aim floor tall, so it reaches past a one-line
    title. A block after the title that lays itself out on its own (a pre) was set
    beside the grip's room for its whole height, 30px narrower than the card; a block
    after the title now clears the grip and takes the card's width, and nothing stands
    under the grip's box."""
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
        const title = card.querySelector('strong').getBoundingClientRect();
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
    assert measured["grip"] == 44 and measured["title"] < 30, measured
    assert measured["widths"] == [0, 0], measured
    assert measured["under"] == 0, measured


def test_a_card_s_prose_starts_under_its_title_in_every_shape(browser, serve):
    """Authors follow a card's title with a plain sentence, one holding an inline
    element, or a paragraph, and each card reads alike: the title's margin set a
    sentence holding an element 2px lower than a plain one, and a paragraph's margin
    set it 13px lower."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "card shapes",
                '<h1>Sprint</h1><lf-board id="shapes"><lf-column id="col" label="Now">'
                '<lf-card id="plain"><strong>Plain</strong> The importer is wired.</lf-card>'
                '<lf-card id="element"><strong>Element</strong> The <em>importer</em> '
                "is wired.</lf-card>"
                '<lf-card id="paragraph"><strong>Paragraph</strong>'
                "<p>The importer is wired.</p></lf-card>"
                "</lf-column></lf-board>",
            )
        ),
    )
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
<section id="rail-section">
  <h2>Keep the rail beside the text</h2>
  <lf-options id="rail" choose>
    <lf-option id="rail-next" value="next">Next</lf-option>
    <lf-option id="rail-later" value="later" chosen>Later</lf-option>
  </lf-options>
</section>
<lf-board id="plan">
  <lf-column id="col-open" label="Undecided"></lf-column>
  <lf-column id="col-next" label="Next" value="next"></lf-column>
  <lf-column id="col-later" label="Later" value="later">
    <lf-card id="card-rail" shows="rail"><strong>Keep the rail</strong></lf-card>
  </lf-column>
</lf-board>
""",
)


def test_a_section_and_a_board_answer_one_decision(browser, serve):
    """The card shows the section's answer and changes it through the section's own
    command, so a pick and a drop are one fact at one coordinate, and both views follow
    its undo, its refusal and a version's retraction (`shown_answers.py`)."""
    page = open_page(browser, live_url(serve(ANSWERS_BOARD_PAGE)))
    grip = page.locator("#card-rail .lf-grip")

    def stands(column, option):
        expect(page.locator(f"#{column} > #card-rail")).to_have_count(1)
        chosen = page.locator("#rail > lf-option[chosen]")
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

    (serve.page_dir / "index.html").write_text(
        ANSWERS_BOARD_PAGE.replace(
            '<lf-options id="rail" choose>', '<lf-options id="rail" choose restated>'
        )
    )
    assert stamp(serve.page_dir, "Ask again").exit_code == 0
    told(page)
    stands("col-later", "rail-later")

    def refuse(route):
        attempt = route.request.post_data_json["attempt"]
        body = {"ok": False, "attempt": attempt, "error": "refused", "final": True}
        route.fulfill(status=400, json=body)

    page.route("**/api/event", refuse)
    with page.expect_response(lambda response: "/api/event" in response.url):
        drop("ArrowLeft")
    stands("col-later", "rail-later")
    page.unroute("**/api/event")
    consume_browser_errors(page, http_error_console(400))
    assert len(picks()) == 2
