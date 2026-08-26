"""Board, suggestion, ask, and widget composition tests."""

import re
from pathlib import Path

import pytest
from leaf_interact import events as events_model
from leaf_interact import rendering as rendering_model
from playwright.sync_api import expect
from render_support import (
    ASK_ROW_SAYS,
    ASK_WITH_CONTEXT_PAGE,
    ASKS_IN_ORDER,
    ASKS_PAGE,
    BOARD_PAGE,
    BOTH_STAMPS,
    CHANGE_SHAPES_PAGE,
    COLLAPSED_PAGE,
    CONVERSATION_DIFF_PAGE,
    HOLD_MOTION,
    LONG_PAGE,
    MESSAGE_ROOM_PAGE,
    PROPOSED_PAGE,
    REBUILT_INLINE_PAGE,
    REPLY_HOST_PAGE,
    ROOM_HELD,
    ROOM_WIDGETS,
    ROOMS,
    SCROLL_SETTLE_MS,
    SCROLL_SETTLED,
    SHORT_SUGGESTION,
    STANDING_ASK,
    SUGGESTION_PAGE,
    SWAP_PAGE,
    CutOff,
    _until,
    actions,
    compare_with,
    open_page,
    panel_settled,
    refuse,
    resized,
    round_trip,
    select,
    told,
    undo,
)

pytestmark = pytest.mark.nightly


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
    whichever path forgets to restate its location or durable pending state."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Todo\"': ⠿\n"
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
            name="Move: Squirrel baffle — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        '- list "Done":\n'
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Done — awaiting next version\"': ⠿"
    )
    assert errors == []
    page.close()


def test_composer_grows_with_its_text_without_script(browser, serve):
    """The comment box fits its content, caps, and shrinks back — and no script
    touches its height. That last part is the point: sizing a textarea from JS
    means shrinking it to re-measure on every keystroke, and a box briefly too
    small for its own text flashes a scrollbar."""
    page, _ = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-comments").click()
    box = page.locator(".lf-general textarea")

    page.evaluate("""() => {
        const ta = document.querySelector('.lf-general textarea');
        window.__styled = 0;
        new MutationObserver(() => window.__styled++)
            .observe(ta, { attributes: true, attributeFilter: ['style'] });
    }""")

    def state():
        return box.evaluate("""ta => ({ h: Math.round(ta.getBoundingClientRect().height),
                                        scrollable: ta.scrollHeight > ta.clientHeight })""")

    empty = state()
    box.type("A comment long enough to wrap onto a second line and then a third.")
    grown = state()
    box.fill("x " * 900)  # far past the ceiling
    capped = state()
    box.fill("short again")
    shrunk = state()

    assert grown["h"] > empty["h"], "the box must grow with its content"
    assert not grown["scrollable"], "a box that fits its text must not be scrollable"
    # The ceiling is 50vh — the viewport's share, not a count of lines — measured
    # here in the suite's 900px-tall window.
    assert capped["h"] == 450, f"the box must stop at its ceiling, got {capped['h']}px"
    assert capped["scrollable"], (
        "past the ceiling the scrollbar is real and belongs there"
    )
    assert shrunk["h"] == empty["h"], "and it must shrink back"
    assert page.evaluate("window.__styled") == 0, "nothing may size the box from script"
    page.close()


def test_suggestion_controls_stay_out_of_the_column(browser, serve):
    """Suggestion chrome hangs in the page margin, so the prose keeps the full column
    and reads as it will once the change is settled. The row is the column's own
    child and takes its line from an anchor inside the change, so how deep the
    change sits costs it nothing: one inside a card — a positioned ancestor, which
    `left: 100%` used to resolve against, dropping the row back into the text —
    hangs in the rail beside its card like any other. What is left is a
    measurement no lint can make: a window with no margin to hold the row docks it
    into flow, under the block it decides rather than overlapping the page.

    The margin the row hangs in is reserved, not left over, and the posture that
    proves it is the one a user reads in: with the comment panel open, a
    centred column left too little beside it and every row docked — above the
    change it decides, which reads as the paragraph before's."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    assert errors == []
    column = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    box = "el => el.getBoundingClientRect()"

    margin_rows = page.locator(
        "[data-lf-for='sug-refill'], [data-lf-for='sug-thistle']"
    )
    assert margin_rows.count() == 2
    for i in range(2):
        assert margin_rows.nth(i).evaluate(box)["left"] > column, (
            "a control row overlapping the column re-wraps the prose it reviews"
        )
    # Two changes a line apart, so the rows would collide at their natural offsets.
    first, second = (margin_rows.nth(i).evaluate(box) for i in range(2))
    assert first["bottom"] <= second["top"], "control rows must not stack on each other"

    # The card is positioned and the change is three elements down inside it, and
    # the row still hangs in the rail on the line that change starts — which is
    # what the anchor buys, and what a static position never could.
    in_card = page.locator("[data-lf-for='sug-in-card']").evaluate(box)
    assert in_card["left"] > column and in_card["right"] <= room, (
        "a change inside a widget is still a change the user decides in the margin"
    )
    assert (
        abs(in_card["top"] - page.locator("#sug-in-card lf-old").evaluate(box)["top"])
        <= 4
    ), "the row must hang on the change's own line, not on the block it follows"

    # The panel takes the right of the window, and the rail survives it: the rows
    # keep their line, clear of the column on one side and of the panel on the
    # other. Measured after the layout has moved, since opening the panel resizes
    # the page and the rows re-place on the frame after that.
    page.locator(".lf-comments").click()
    panel_settled(page)
    page.wait_for_function(
        "() => [...document.querySelectorAll("
        "'[data-lf-for=sug-refill], [data-lf-for=sug-thistle]')]"
        ".every(r => !r.classList.contains('lf-docked'))"
    )
    narrowed = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    for i in range(2):
        rect = margin_rows.nth(i).evaluate(box)
        assert rect["left"] > narrowed and rect["right"] <= room, (
            "with the panel open the row must still hang between column and panel"
        )

    # No margin anywhere: every row docks, and nothing spills sideways. Docked is
    # the same box in flow where the row was hoisted to, so it reads as a control
    # line under the block holding the change and never as the one before's.
    page.get_by_role("button", name="Close comments").click()
    resized(page, 820, 900)
    page.wait_for_function(
        "() => [...document.querySelectorAll('.lf-sug-actions')]"
        ".every(r => r.classList.contains('lf-docked'))"
    )
    assert page.evaluate("() => document.body.scrollWidth <= document.body.clientWidth")
    for widget, block in [("sug-refill", "#replace"), ("sug-in-card", "#feeders")]:
        assert (
            page.locator(f"[data-lf-for='{widget}']").evaluate(box)["top"]
            >= page.locator(block).evaluate(box)["bottom"]
        ), "a docked row belongs under the block whose change it decides"
    page.close()


def test_a_copy_says_a_change_is_only_proposed(browser, serve, tmp_path):
    """Who says the change is still a proposal, in each medium the page reaches.

    On screen the ✓/✗ row hanging on the change's own line says it, and the word is
    for whoever is listening, so it stays clipped. A copy and paper have no row —
    both strip a control the page does not speak through, and a pending one says
    nothing yet, so it goes whole — and that left the two states saying opposite
    amounts: a decided change keeps its "✓ Accepted" in the copy, a pending one kept
    nothing at all, and the tints alone read as a change already made.

    The word also had to change to be worth showing. Pendingness was carried by the
    word's mere presence, which no reader can perceive — nothing sits alongside to
    compare it against — and `deletion` is ARIA's own name for the completed act, so
    a listener heard the change announced as made while the page was still asking."""
    url = serve(PROPOSED_PAGE)
    page, errors = open_page(browser, url)

    quiet = "lf-suggestion:not([data-lf-state]) > :is(lf-old, lf-new) > .lf-quiet"
    read = """(sel) => [...document.querySelectorAll(sel)].map(el => {
        const r = el.getBoundingClientRect();
        return {word: el.textContent, shown: el.checkVisibility(),
                w: Math.round(r.width), h: Math.round(r.height)};
    })"""
    live = page.evaluate(read, quiet)
    assert [q["word"] for q in live] == [
        "proposed deletion",
        "proposed insertion",
        "proposed insertion",
        "proposed deletion",
    ], live
    for q in live:
        assert q["w"] <= 1 and q["h"] <= 1, (
            f"on screen the row says it; `{q['word']}` must hold no room, got {q}"
        )
    # And the row is there to say it — the fact the copy is about to lose.
    expect(page.locator(".lf-sug-actions")).to_have_count(3)
    assert errors == []
    page.close()

    out = tmp_path / "standalone.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))
    copy = browser.new_page(viewport={"width": 1200, "height": 900})
    copy.goto(out.as_uri(), wait_until="load")
    assert copy.locator(".lf-sug-actions").count() == 0, (
        "the copy is only interesting because it has no controls left"
    )
    for medium in ("screen", "print"):
        copy.emulate_media(media=medium)
        shown = copy.evaluate(read, quiet)
        assert [q["word"] for q in shown] == [q["word"] for q in live], shown
        for q in shown:
            assert q["shown"] and q["w"] > 1, (
                f"[{medium}] with no row on the page, `{q['word']}` is the only thing "
                f"saying the change is unmade, and it is not on screen: {q}"
            )
    copy.close()


def test_a_moved_change_takes_its_controls_with_it(browser, serve):
    """The row is the column's child, not the change's, so the subtree a card
    travels in no longer carries it: a card dragged to another column, or moved by
    the replay of someone else's drag, leaves and re-enters the document with its
    row unhooked. Re-connection has to hang it again, or the user loses the
    only way to decide a change that is still plainly pending on the page. Replayed
    rather than dragged, because that is the same move with no gesture in the way."""
    url = serve(SUGGESTION_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "feeders",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-done", "index": 0},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = page.locator("[data-lf-for='sug-in-card']")
    expect(row).to_be_visible()
    change = page.locator("#sug-in-card lf-old").evaluate(box)
    assert abs(row.evaluate(box)["top"] - change["top"]) <= 4, (
        "the row must find the moved change's line again, not the one it left"
    )
    row.locator(".lf-sug-accept").click()
    expect(page.locator("#sug-in-card lf-old")).to_be_hidden()
    assert errors == []
    page.close()


# A change the reader hasn't opened yet. The row hangs off an anchor in the
# change, and a collapsed container reports its content's last rendered geometry
# rather than nothing at all — so a row that trusted a measurement would hang in
# the margin deciding a change nobody can see.
def test_a_terse_compare_keeps_its_side_by_side_grid(browser, serve):
    """An exhibition is looked across where a decision is read down: terse variants
    share a row while block content stacks the group. Which children count as block
    is the phrasing-set inversion, and its one hazard is an inline widget — a
    chip-led pair must not stack, which is why the stylesheet's list excludes the
    marker the runtime paints from x-inline and this reads the shipped page to prove
    the grid actually held. It is the whole chain in one assertion: a declaration
    unpainted, a marker unread, or a selector naming the wrong attribute all arrive
    here as two variants that stacked."""
    page, errors = open_page(
        browser,
        serve(
            (Path(__file__).parent.parent / "examples/design-decision.html").read_text()
        ),
    )
    top = "el => el.getBoundingClientRect().top"
    assert page.locator("#var-session-cookie").evaluate(top) == page.locator(
        "#var-fallback-cookie"
    ).evaluate(top), "chip-led terse variants must share a row"
    assert page.locator("#var-payments-regime").evaluate(top) != page.locator(
        "#var-sessions-regime"
    ).evaluate(top), "block-content variants must stack"
    assert errors == []
    page.close()


def test_a_rebuilt_widget_is_still_set_among_the_words(browser, serve):
    """Undo rebuilds a recordless decision from the version's own markup, and the
    marks the runtime paints from the registry are painted again onto the clone —
    the widget's own mark included, not only its descendants'. A suggestion is
    inline, so the exhibition holding it is looked across; unmarked after the
    rebuild it becomes block content, and taking back a decision about one case
    would silently restack the comparison it was made in.

    The reading straddles the rebuild rather than sampling after it, because the
    grid is what the page arrives at and a rule that never applied would look the
    same at the end."""
    page, errors = open_page(browser, serve(REBUILT_INLINE_PAGE))
    form = "() => getComputedStyle(document.getElementById('cmp-stores')).display"
    assert page.evaluate(form) == "grid", (
        "the exhibition stacked before anything was decided, so this proves nothing"
    )

    page.locator("[data-lf-for='sug-store'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-store lf-old")).to_be_hidden()
    undo(page)
    expect(page.locator("#sug-store lf-old")).to_be_visible()
    assert page.evaluate(form) == "grid", (
        "the rebuilt suggestion lost its inline mark, so the exhibition stacked"
    )
    assert errors == []
    page.close()


def test_a_block_change_emphasizes_the_words_that_moved(browser, serve):
    """A replacement's slots paint whole — which is all a dead copy keeps — and on
    the live page the words that differ deepen through the highlight registry, so
    the reader isn't left to eyeball-diff two paragraphs. Deciding clears the
    emphasis with the slot it retires: the survivor is plain prose."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    inside = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    refill = page.evaluate(inside, "sug-refill")
    assert refill["lf-sug-del"] >= 1 and refill["lf-sug-ins"] >= 1, (
        "an edited sentence must emphasize the words that moved, on both sides"
    )

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(inside, "sug-refill") == {
        "lf-sug-del": 0,
        "lf-sug-ins": 0,
    }, "deciding must clear the emphasis with the slot it retires"
    assert errors == []
    page.close()


def test_a_whole_swap_paints_no_emphasis(browser, serve):
    """An alignment that shares almost nothing is a replacement, not an edit, and
    emphasis over everything says nothing — the similarity gate every mature diff
    view applies. The whole-slot tints already say a swap is on offer."""
    page, errors = open_page(browser, serve(SWAP_PAGE))
    total = page.evaluate(
        "() => (CSS.highlights.get('lf-sug-del')?.size ?? 0)"
        " + (CSS.highlights.get('lf-sug-ins')?.size ?? 0)"
    )
    assert total == 0, "unrelated old and new text must not be word-marked"
    assert errors == []
    page.close()


def test_a_row_waits_for_the_change_it_decides_to_be_on_screen(browser, serve):
    """A change inside a collapsed container has no line for its row to hang on,
    and an anchor that isn't rendered is no anchor at all: the row falls back to
    the block it was hoisted to and hangs there in the margin, offering to decide
    something the reader can't see. It waits instead, and arrives on the change's
    own line the moment the container opens — a real click on the summary, because
    opening it is the reader's gesture and the reflow it causes is the point."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    waiting = page.locator("[data-lf-for='sug-boxes']")
    expect(page.locator("[data-lf-for='sug-now']")).to_be_visible()
    expect(waiting).to_be_hidden()

    page.locator("#sum").click()
    expect(waiting).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = waiting.evaluate(box)
    assert row["left"] > page.locator("main").evaluate(box)["right"], (
        "the row must arrive in the margin, not over the prose that just opened"
    )
    assert (
        abs(row["top"] - page.locator("#sug-boxes lf-new").evaluate(box)["top"]) <= 4
    ), "and on the line of the change it decides"
    assert errors == []
    page.close()


def test_the_ask_walk_lands_on_a_suggestion_the_reveal_just_opened(browser, serve):
    """Stepping the asks opens the closed <details> a change waits inside and
    focuses that change's control in the same task. The row un-waits on the
    runtime's reveal signal rather than at the observer's next frame: settled
    asynchronously, focus() fell on a display:none control and stayed where it
    was — on the previous ask's Accept — while the announce said otherwise, so
    Enter was aimed at a decision the reader had already seen."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    page.keyboard.press("n")
    expect(page.locator("[data-lf-for='sug-now'] .lf-sug-accept")).to_be_focused()
    page.keyboard.press("n")
    expect(page.locator("#later")).to_have_attribute("open", "")
    expect(page.locator("[data-lf-for='sug-boxes'] .lf-sug-accept")).to_be_focused()
    assert errors == []
    page.close()


def test_the_rail_survives_every_script_being_removed(browser, serve, tmp_path):
    """A standalone copy of a leaf page is its rendered DOM with the script tags
    dropped, and the pass that placed these rows is script. It doesn't have to run
    again: the row is a child of <main> in the serialized markup, and `left: 100%`
    against the column with `top: anchor(top)` against the change re-solve wherever
    the copy is opened and at whatever width. Including the change inside the card,
    whose positioned ancestor is exactly what a placement done in script would have
    had to correct for — and could not, with no script left to run."""
    page, _ = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("() => document.querySelectorAll('script').forEach(s => s.remove())")
    baked = page.evaluate("() => document.documentElement.outerHTML").replace(
        '<link rel="stylesheet" href="/theme.css">',
        "<style>" + (serve.page_dir / "theme.css").read_text() + "</style>",
    )
    page.close()

    standalone = tmp_path / "standalone.html"
    standalone.write_text(baked)
    loose = browser.new_page(viewport={"width": 1500, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    box = "el => el.getBoundingClientRect()"
    column = loose.locator("main").evaluate(box)["right"]
    for widget in ("sug-refill", "sug-in-card"):
        row = loose.locator(f"[data-lf-for='{widget}']").evaluate(box)
        assert row["left"] > column, f"{widget}'s row lost the rail without its script"
        assert (
            abs(row["top"] - loose.locator(f"#{widget} lf-old").evaluate(box)["top"])
            <= 4
        ), f"{widget}'s row lost its change's line without its script"
    loose.close()


def test_accepting_a_suggestion_settles_it_and_reaches_claude(browser, serve):
    """Accepting collapses the change to the proposal as ordinary prose — no
    tint, no strike — because the live view is the version plus the user's
    actions, and the honoring version only has to catch up.
    The outcome has to reach the log too: what the user sees settle and what
    Claude is told must be the same event.

    What stays is the row, saying what was done there. It used to clear itself in
    the same frame as the press, leaving a corner toast as the only evidence that
    anything had happened — and clearing a control is the one thing a press may not
    do to the line it was made on. Now the control the user pressed states the
    outcome where it stood and stops offering; its pair keeps its room and gives up
    only its ink, so nothing on the row is anywhere new."""
    page, _errors = open_page(browser, serve(SUGGESTION_PAGE))
    row = page.locator("[data-lf-for='sug-refill']")
    accept = row.locator(".lf-sug-accept")
    reject = row.locator(".lf-sug-reject")
    assert accept.get_attribute("aria-label").startswith(
        "Accept the suggested change: Refill a feeder when"
    ), "the button names the proposal, not the text being replaced"
    # Inside the row rather than on the page: the row is positioned, so a button's
    # offset box is its place on that row, and an inline change that reflows the
    # paragraph it sits in carries the whole row with it legitimately. What must not
    # move is one control against the other.
    box = "el => [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight]"
    before = [accept.evaluate(box), reject.evaluate(box)]
    # innerText throughout: what these assert is the visible word, and innerText is the
    # rendered text where textContent is the markup's.
    expect(accept).to_have_text("✓ Accept", use_inner_text=True)

    # A strike and two tints say which words are going and which are proposed, and say
    # it in no text at all: a reader listening got the sentence twice, the two readings
    # contradicting each other, with nothing to say either was a change.
    assert "deletion" in page.locator("#sug-refill lf-old").aria_snapshot()
    assert "insertion" in page.locator("#sug-refill lf-new").aria_snapshot()

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(accept).to_have_text("✓ Accepted", use_inner_text=True)
    assert accept.get_attribute("aria-label").startswith(
        "Accepted the suggested change: Refill a feeder when"
    ), "the record still offers the press it has already taken"
    assert accept.get_attribute("aria-disabled") == "true"
    assert [accept.evaluate(box), reject.evaluate(box)] == before, (
        "the row rearranged as it was decided, on the one line a press must leave alone"
    )
    assert reject.evaluate("el => getComputedStyle(el).visibility") == "hidden", (
        "the decision left both halves of the offer standing"
    )
    settled = page.locator("#sug-refill lf-new").evaluate(
        "el => getComputedStyle(el).textDecorationLine + ' ' + getComputedStyle(el).backgroundColor"
    )
    # And the word goes with the marks, the settled slot being ordinary prose now:
    # a reader listening is told about a change while there is one to decide.
    assert "insertion" not in page.locator("#sug-refill lf-new").aria_snapshot()
    assert "line-through" not in settled and "rgba(0, 0, 0, 0)" in settled, (
        f"settled text still wears a pending mark: {settled}"
    )
    # The banner's count follows the page: three pending, one decided.
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()

    page.wait_for_function(
        "() => fetch('/api/state').then(r => r.json())"
        ".then(s => s.events.some(e => e.kind === 'action' && e.action === 'accept'))"
    )
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"], e["author"]) for e in logged] == [
        ("sug-refill", "accept", "user")
    ]
    page.close()


@pytest.mark.parametrize(
    "outcome,verb", [("accept", "Accepted"), ("reject", "Rejected")]
)
def test_a_widget_naming_its_own_words_does_not_read_the_runtimes(
    browser, serve, outcome, verb
):
    """The line saying a block carries a comment goes in the block, and a block inside a
    widget is still a block — so `textContent` on a widget's own slot now returns the
    author's words with the runtime's appended. A suggestion labels itself from that slot,
    and offered to accept “Retry three times. 1 comment”. It reads the slot the way the
    page is read instead, which is what `says` is for — read before deciding, because a
    reject retires the very slot the label comes from, and a retired slot says nothing:
    the toast then named the widget's id instead of the words the user judged. Short
    on purpose: the label cuts at 48 characters, which hid this on every shipped example."""
    url = serve(SHORT_SUGGESTION, anchored=[("now", "Retry three times")])
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Vacuous otherwise: the line has to be inside the slot the label is read from.
    assert page.locator("lf-new #now > .lf-mark-note").count() == 1
    page.locator(f"[data-lf-for='sug'] .lf-sug-{outcome}").click()
    expect(page.locator(".lf-toast")).to_have_text(
        f"{verb} “Retry three times.” — sent to Claude"
    )
    assert errors == []
    page.close()


def test_a_decided_change_folds_away_rather_than_vanishing(browser, serve):
    """A decision may move the page; it may not teleport it.

    A block change is a struck old paragraph stacked over a tinted new one, and
    accepting used to drop the old one with `display: none` in the frame of the press —
    179 measured pixels out of the middle of the shipped design page, with everything
    below jumping up under the pointer that had just pressed. The rule this layer
    already carries is that a change the user asked for may move the page and must do
    it as motion, because motion is the form the eye can follow to where the sentence
    went.

    Held at its first frame rather than sampled mid-flight, which would be a race with
    the clock and would pass on a fast machine either way: the fold is read where it
    starts (the slot's own height, not zero), stepped to the middle, and then let go, so
    what the test proves is the shape of the motion and not how long the run took.

    An inline change is the test below: it has nothing to follow, and folding one would
    be the harm rather than the fix."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION), init_script=HOLD_MOTION)
    old = page.locator("#sug lf-old")
    after = page.locator("#after")
    tall = old.evaluate("el => el.getBoundingClientRect().height")
    assert tall > 0
    below = after.evaluate("el => el.getBoundingClientRect().top")

    page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
    # Awaited, because the state lands when the log takes the decision rather than in
    # the frame of the press. From that frame it is true everywhere at once — the log
    # carries it, the banner counts it, a second tab converging reads it — and the
    # pixels are the only thing still catching up, which is what the rest measures.
    expect(page.locator("#sug[data-lf-state='accept']")).to_have_count(1)
    held = page.evaluate(
        """() => window.__lfHeld.map((m) => [m.effect.target.tagName.toLowerCase(),
                                             m.effect.getTiming().duration])"""
    )
    assert [t for t, _ in held] == ["lf-old"], (
        f"the retired slot went without motion to follow: {held}"
    )
    at = "() => document.querySelector('#sug lf-old').getBoundingClientRect().height"
    assert page.evaluate(at) == pytest.approx(tall, abs=1), (
        "the fold begins somewhere other than where the paragraph was standing"
    )
    page.evaluate(
        "() => { const m = window.__lfHeld[0];"
        "        m.currentTime = m.effect.getTiming().duration / 2; }"
    )
    middle = page.evaluate(at)
    assert 0 < middle < tall, f"the fold's midpoint is not between its ends: {middle}"

    # The endpoint is part of the motion, not a scheduling gap the finish handler has
    # to beat. Read it synchronously at the exact duration: without a forwards fill the
    # effect has already stopped applying here and the slot springs back to its
    # unanimated height before cleanup gets its turn.
    endpoint = page.evaluate(
        """() => {
          const m = window.__lfHeld[0];
          m.currentTime = m.effect.getTiming().duration;
          return {
            height: m.effect.target.getBoundingClientRect().height,
            opacity: Number(getComputedStyle(m.effect.target).opacity),
            fill: m.effect.getTiming().fill,
          };
        }"""
    )
    assert endpoint["height"] == pytest.approx(0, abs=0.1), (
        f"the fold exposed its unanimated box at the endpoint: {endpoint}"
    )
    assert endpoint["opacity"] == pytest.approx(0, abs=0.001), (
        f"the fold exposed its unanimated ink at the endpoint: {endpoint}"
    )

    page.evaluate("() => window.__lfHeld[0].finish()")
    expect(old).to_be_hidden()
    page.wait_for_function(
        "() => document.querySelector('#sug lf-old').getAnimations().length === 0"
    )
    assert after.evaluate("el => el.getBoundingClientRect().top") < below, (
        "the page never gave back the room the retired paragraph was holding"
    )
    assert errors == []
    page.close()


def test_an_inline_change_is_swapped_rather_than_folded(browser, serve):
    """The other half of the rule above, and the half where folding would be the harm.

    A height to animate means a `display: block` held over the slot for the duration, so
    a few words swapped mid-sentence would open a paragraph break and close it again —
    motion answering a change that moved nothing. The shipped inline corpus is the case,
    and what it asserts is that nothing was started at all."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a few words swapped inside a line were given a fold, and a block box to do it in"
    )
    assert errors == []
    page.close()


def test_a_reader_who_asked_for_less_motion_gets_the_collapse_at_once(browser, serve):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the same bargain the board's own FLIP makes.

    Asked of the context rather than of the page, because the runtime reads the
    preference once as it loads: emulating it afterwards changes what the media query
    would answer and not what the module already recorded."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    try:
        page, errors = open_page(
            browser, serve(SHORT_SUGGESTION), context=context, init_script=HOLD_MOTION
        )
        page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
        expect(page.locator("#sug lf-old")).to_be_hidden()
        assert page.evaluate("() => window.__lfHeld.length") == 0, (
            "a reader who asked for less motion was given a fold to sit through"
        )
        assert errors == []
    finally:
        context.close()


def test_accept_all_decides_every_pending_suggestion(browser, serve):
    """The banner's button is a shortcut for the user who has read the page
    and wants all of it, so it has to reach the ones their eye didn't: the
    suggestion inside a widget, whose controls dock in flow rather than hang in
    the margin. Each is decided individually, so the log records what was
    consented to one change at a time rather than one blanket yes."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.get_by_role("button", name="Accept all (3)").click()

    for widget in ("sug-refill", "sug-thistle", "sug-in-card"):
        expect(page.locator(f"#{widget} lf-new")).to_be_visible()
        # Waited for, not read once: each is decided by its own round trip, so the
        # last of them is still in flight when the first has settled.
        expect(page.locator(f"[data-lf-for='{widget}'] .lf-sug-accept")).to_have_text(
            "✓ Accepted", use_inner_text=True
        )
    for widget in (
        "sug-refill",
        "sug-in-card",
    ):  # the two that replace rather than insert
        expect(page.locator(f"#{widget} lf-old")).to_be_hidden()
    # Nothing left to accept, so the button says nothing rather than saying zero.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()

    # The controls settle from their individual authoritative answers. Wait for the
    # whole outbox as well: the rows are asserted one at a time above, while this is
    # the boundary before reading the shared log as a sequence.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"]) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]
    assert errors == []
    page.close()


def test_a_key_gives_every_blanket_answer_the_banner_offers(browser, serve):
    """A is the banner's blanket answers in a press — the same controls, so the log
    records each decision one at a time exactly as a click does. Neither the key nor
    its legend names a verb: which verbs a page offers is the registry's answer
    (x-awaits.all), so the reference states the words the banner is writing at the
    moment it is opened. A sentence written into the table would have said "accept" in
    core, and gone on saying it for the second widget to declare a verb of its own.

    The shift is part of the key rather than decoration, and the walk beside it is
    spelled in directions (n/p) rather than in this letter, so the letter is this
    press's alone — and stands for nothing unshifted, an unshifted `a` that settled
    every change on the page being a press far too cheap for what it does. Caps lock is
    where reading the glyph instead of asking for the modifier fails in both
    directions: it writes an uppercase key out of a bare press, which must not end the
    matter, and a lowercase one out of the shifted press that must."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    help_el = page.locator(".lf-help")

    page.keyboard.press("?")
    expect(help_el).to_contain_text("Accept all 3 waiting on you")
    page.keyboard.press("Escape")

    # A decision taken on its own control leaves two, and the legend says two: it is
    # read when the reference opens rather than held from when the table was written.
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Accept all 2 waiting on you")
    page.keyboard.press("Escape")

    # An unshifted uppercase press is what caps lock sends, and the dispatcher refuses
    # it: dispatched at the protocol level, which is the only place that press exists.
    cdp = page.context.new_cdp_session(page)
    for kind in ("keyDown", "keyUp"):
        cdp.send(
            "Input.dispatchKeyEvent",
            {
                "type": kind,
                "key": "A",
                "code": "KeyA",
                "windowsVirtualKeyCode": 65,
                "text": "A" if kind == "keyDown" else "",
            },
        )
    told(page)
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()

    page.keyboard.press("Shift+A")
    for widget in ("sug-thistle", "sug-in-card"):
        expect(page.locator(f"[data-lf-for='{widget}'] .lf-sug-accept")).to_have_text(
            "✓ Accepted", use_inner_text=True
        )
    # Nothing left to answer, so the control goes and the key goes with it.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("Accept all")

    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"]) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ], "the key's decisions have to reach the log one at a time, like the button's"
    assert errors == []
    page.close()


def test_a_decision_the_server_never_took_never_shows_as_taken(browser, serve):
    """A decision is painted when the log takes it, never before, so a send the
    server refuses leaves the page exactly as it was. Settling first and putting it
    back on failure said the same thing in the end and flickered on the way: the
    press against a closed session painted one frame of "✓ Accepted" over a folding
    slot before rewinding it."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))

    def refuse_attempt(route):
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse_attempt)
    # Watch the attribute across every frame, not just after: a rewind is only
    # visible while it is happening, and the end state is the same either way.
    page.evaluate(
        """() => {
          window.__settled = [];
          new MutationObserver(() => {
            window.__settled.push(
              document.getElementById('sug-refill').dataset.lfState ?? null);
          }).observe(document.getElementById('sug-refill'),
                     {attributes: true, attributeFilter: ['data-lf-state']});
        }"""
    )
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()

    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.locator("#sug-refill").get_attribute("data-lf-state") is None
    assert page.evaluate("() => window.__settled") == [], (
        "the refused decision must never have been on the element at all"
    )
    # The row is the record of a decision, so a decision that was never taken must not
    # be standing in it: both controls offering again, neither of them past tense.
    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    reject = page.locator("[data-lf-for='sug-refill'] .lf-sug-reject")
    expect(accept).to_have_text("✓ Accept", use_inner_text=True)
    expect(reject).to_be_visible()
    assert accept.get_attribute("aria-disabled") == "false"
    # And the page's own count is derived from that, so it comes back too.
    expect(page.get_by_role("button", name="Accept all (3)")).to_be_visible()
    expect(page.locator(".lf-toast")).to_contain_text("Couldn't send")
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []

    # The retry is a second click, not a reload: a definitive refusal made the widget
    # pending again, and the new press carries a fresh attempt of its own.
    page.unroute("**/api/event")
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    logged = actions(serve.page_dir)
    assert [(event["widget"], event["action"]) for event in logged] == [
        ("sug-refill", "accept")
    ]
    assert logged[0]["attempt"]
    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert errors and all("400" in error for error in errors)
    page.close()


def test_an_ambiguous_decision_stays_one_gesture_while_retrying(browser, serve):
    """Losing an accepted action answer keeps the original press busy and retries
    that exact attempt. Repeating the press cannot mint a second decision that one
    undo would merely uncover."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    requests = []
    accepted = []

    def lose_first_answer(route):
        requests.append(route.request.post_data_json)
        if len(requests) == 1:
            accepted.append(route.fetch().status)
            refuse(route)
        else:
            route.continue_()

    # Force recovery through the outbox rather than letting a periodic read observe
    # the accepted attempt first. Both are valid recovery paths; this one proves the
    # retry reuses the identity whose answer was lost.
    page.route("**/api/state*", refuse)
    page.route("**/api/event", lose_first_answer)
    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        accept.click()
    expect(page.locator("#sug-refill")).to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-toast")).to_contain_text("retrying your change")

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert accepted == [200]
    assert len(requests) == 2
    assert len({request["attempt"] for request in requests}) == 1
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [("sug-refill", "accept")]

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert errors == []
    page.close()


def test_a_second_press_inside_the_round_trip_adds_no_second_decision(browser, serve):
    """One press, one decision — and the element's own state is no longer what makes
    that true. The decided state used to be written in the frame of the press, so a
    control pressed twice refused itself on the second; it now lands with the log's
    answer, leaving a whole round trip in which both controls are still offering.
    Presses made in that gap would each be a line in the log for one act, and an
    accept followed by a reject would resolve the thread the accept answers and then
    record the opposite outcome over it.

    Neither of those presses can be caught in the wire: `post` sends one action at a
    time, so they queue behind the held one instead of reaching the route. What they
    would leave is a line each in the log once the queue drains, and that is where
    this reads them."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    row = page.locator("[data-lf-for='sug-refill']")
    row.locator(".lf-sug-accept").click()
    _until(page, lambda traffic: traffic.sends == 1, "held the decision in the wire")
    row.locator(".lf-sug-accept").click()
    row.locator(".lf-sug-reject").click()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    assert [
        (e["widget"], e["action"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("sug-refill", "accept")]
    assert errors == []
    page.close()


def test_a_wait_the_reader_would_notice_says_so_and_a_short_one_says_nothing(
    browser, serve
):
    """The press paints nothing until the log answers, so a wait long enough to
    notice has to say it is waiting — and a wait too short to notice must not, or the
    look would flash on and off exactly where the settle-then-rewind flicker used to
    be. One delayed rule covers both, and it is keyed on aria-busy rather than on any
    tag, so lf-draft's own busy word is painted by it too.

    Held in the wire rather than timed against a real answer: the delay is measured
    from the press either way, and a send that never lands is the only way to read
    both sides of it without racing the machine the suite is on."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    resting = page.locator("[data-lf-for='sug-refill']").bounding_box()
    # Pressed and sampled inside the page, on the browser's own clock: what painted
    # and when is not a fact the browser reports outward, and a reading taken over a
    # CDP round trip would be racing the delay rather than measuring it. The window is
    # the rule's own — 200ms of delay and 140ms of fade — with room after it, since a
    # send held in the wire states no fact to wait on.
    frames = page.evaluate(
        """async () => {
          const el = document.getElementById('sug-refill');
          const out = [];
          const t0 = performance.now();
          let stop = false;
          const tick = (t) => {
            out.push([t - t0, Number(getComputedStyle(el).opacity)]);
            if (!stop) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          document.querySelector("[data-lf-for='sug-refill'] .lf-sug-accept").click();
          await new Promise((r) => setTimeout(r, 500));
          stop = true;
          return out;
        }"""
    )
    early = [o for t, o in frames if t < 150]
    late = [o for t, o in frames if t > 400]
    assert early and set(early) == {1}, (
        f"the wait was announced before it was one: {early}"
    )
    assert late and set(late) == {0.5}, f"a wait worth noticing said nothing: {late}"
    expect(page.locator("#sug-refill")).to_have_attribute("aria-busy", "true")
    # And it says it without moving the line the press was made on: the row the reader
    # just pressed stands where it stood, so a second press has the same target.
    assert page.locator("[data-lf-for='sug-refill']").bounding_box() == resting

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    assert errors == []
    page.close()


def test_a_decision_travels_between_tabs_and_the_log_has_the_last_word(browser, serve):
    """Two windows on one page are two views of one log, not two documents. A
    decision taken in either arrives in the other by the same replay that keeps a
    reload's drag, and the record it leaves in the margin has to arrive with it: the
    tab that receives one settles it without the click that settled the tab that sent
    it, and a row still offering the press is a window disagreeing with the log about
    what has already been decided. Where the two disagree, the later entry in the log
    is what both end on."""
    url = serve(SUGGESTION_PAGE)
    first, first_errors = open_page(browser, url)
    second, second_errors = open_page(browser, url)

    # A tab that did not click has only its own poll to learn from.
    first.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    told(second)
    expect(second.locator("#sug-refill lf-old")).to_be_hidden()
    expect(second.locator("#sug-refill lf-new")).to_be_visible()
    # Nothing left to decide, and the row says which way it went — written by the
    # replay here rather than by a press, which is the only place that path is driven.
    accepted = second.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    expect(accepted).to_have_text("✓ Accepted", use_inner_text=True)
    assert accepted.get_attribute("aria-disabled") == "true"
    expect(second.locator("[data-lf-for='sug-refill'] .lf-sug-reject")).to_be_hidden()
    expect(second.get_by_role("button", name="Accept all (2)")).to_be_visible()

    # Now the race the controls make possible: a window cut off from the log still
    # shows both buttons, so the user can decide the other way there. Two
    # decisions on one change, and the log's order — not either tab's belief —
    # settles it for both once the cut-off one catches up.
    third, third_errors = open_page(browser, url)
    cut = CutOff().hold(third)
    first.locator("[data-lf-for='sug-thistle'] .lf-sug-accept").click()
    # In the log before the reject is clicked, so which one is later is this test's
    # to decide rather than the network's.
    told(second)
    expect(second.get_by_role("button", name="Accept all (1)")).to_be_visible()
    third.locator("[data-lf-for='sug-thistle'] .lf-sug-reject").click()
    cut.restore()
    # The reject went out over a live channel, so every tab has to read it back —
    # the cut-off one included, which is where it stops being its own local click.
    for tab in (first, second, third):
        told(tab)
        expect(tab.locator("#sug-thistle lf-new")).to_be_hidden()
    assert first_errors == [] and second_errors == [] and third_errors == []
    for tab in (first, second, third):
        tab.close()


def test_the_banner_counts_what_the_page_is_still_asking(browser, serve):
    """One list, collected from what the registry declares rather than from any tag.

    The count used to be a query for `lf-suggestion:not([data-lf-state])`: perfect for
    suggestions, and silently nothing for every other thing a page waits on. What
    makes an instance an ask is now the entry's own attribute condition, and the entry
    explicitly names which state verbs answer it — so this page's four are
    a question with no pick, a change nobody has decided, and the two tasks whose
    status says they are waiting.

    The rest of the page is every way of not being one, and each was a way of getting
    it wrong: a group whose pick the version already carries (`chosen`, with nothing in
    the log — a fold-only reading counts it as open on every shipped example), one the
    author has settled, one that takes no picks at all, an exhibited decision inside a
    lf-specimen, and a milestone at `blocked`, which is the same word on a widget whose
    entry does not declare it."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (4)")
    # The blanket answer counts the same list, narrowed to the one kind that declares
    # a verb for it, so the two numbers cannot describe different sets.
    expect(page.locator(".lf-answer-all")).to_have_text("✓ Accept all (1)")

    # Answering one takes it out. A pick is state the page itself carries, so the
    # count follows the click; the suggestion's outcome is in the log alone, so that
    # one follows the round trip.
    page.locator("#lq-token").click()
    expect(asks).to_have_text("Asks (3)")
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(asks).to_have_text("Asks (2)")
    expect(page.locator(".lf-answer-all")).to_be_hidden()

    # And clearing the pick asks again: an empty answer is no answer, which only a
    # reading of what the page carries can say.
    page.locator("#lq-token").click()
    expect(asks).to_have_text("Asks (3)")
    assert errors == []
    page.close()


def test_a_key_walks_the_page_s_open_asks(browser, serve):
    """j/k step the open threads; n/p step the things the page is waiting on the reader
    for. Every walk here is a borrowed pair naming its direction rather than what it
    walks — vim's list, less's half page, next and previous — which is what left `a`
    free for the tray that shows the list they walk (⇧A is the answer that takes all of
    them at once).
    It wraps rather than clamping, because an ask leaves the list as soon as it is
    answered — forward is the direction with somewhere to go, and one key that stopped
    at the last one would strand the reader there.

    The landing is marked on the ask and focused on the control that answers it, so
    the reader can see what they were brought to and Tab straight into working it —
    on a suggestion that control is the ✓ Accept hoisted into the page margin, and
    the walk follows it out there."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    walked = []
    for expected in [*ASKS_IN_ORDER, ASKS_IN_ORDER[0]]:  # one past the end: it wraps
        page.keyboard.press("n")
        # The ring is painted from the focus, in the frame after the press, so waiting
        # for it on the ask this press stepped to is both the wait and the assertion —
        # a bare count would pass on the ring an earlier press left standing.
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        # And exactly one ask wears it, the reader standing in one place at a time.
        expect(page.locator(STANDING_ASK)).to_have_count(1)
        walked.append(
            page.evaluate(
                "() => document.activeElement.tagName.toLowerCase()"
                "      + ' ' + document.activeElement.className"
            )
        )
    assert walked == [
        "span lf-pick lf-ui",  # the question: its first pick mark
        "span lf-pill lf-sug-accept lf-ui",  # ✓ Accept, in the margin
        "lf-task ",  # a task holds no control, so it takes the focus itself
        "lf-task ",
        "span lf-pick lf-ui",
    ], f"the walk landed on something else: {walked}"

    # And back, from where the last press left them: p wraps at this end too, and the
    # step off a suggestion is measured from the suggestion rather than from the ✓ Accept
    # holding the focus — that row is hoisted out into the page margin as a sibling of the
    # block it decides, so a walk reading it where it hangs would step back onto the
    # change the reader is standing on.
    for expected in reversed(ASKS_IN_ORDER):
        page.keyboard.press("p")
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        expect(page.locator(STANDING_ASK)).to_have_count(1)

    # The stop the walk lends an ask that holds nothing to work goes back when it moves
    # on. The two tasks here are one after the other, which is what makes the leak
    # reachable at all: the stop is paint on the author's element, and one left standing
    # is a tab stop no author wrote in a page the replay signature reads attribute by
    # attribute.
    expect(page.locator(STANDING_ASK)).to_have_count(1)
    # Asked of the tag's dash, the platform's own mark of a widget element, which is what
    # the export's own sweep for stray stops asks (BAKE).
    assert (
        page.evaluate(
            "() => [...document.querySelectorAll('main [tabindex]')]"
            "  .filter(el => el.tagName.includes('-') && !el.hasAttribute('data-lf-ask'))"
            "  .map(el => el.tagName.toLowerCase() + '#' + el.id)"
        )
        == []
    ), "a lent tab stop was left on an ask the reader has walked off"

    # The overlay and the key line offer it because there is something to reach.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("waiting on you for")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-keyline")).to_contain_text("asks")

    # An answered ask leaves the walk: deciding the change on its own control is where
    # the reader now stands, and the next press reaches what followed it rather than the
    # change they have just settled.
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator(".lf-asks")).to_have_text("Asks (3)")
    page.keyboard.press("n")
    expect(page.locator("#t-baffles")).to_be_focused()
    assert errors == []
    page.close()


def test_an_ask_arrival_starts_with_the_context_that_frames_it(browser, serve):
    """The ask is the question's whole reading region, not only its answer control.

    An options group used to be both the state owner and the navigation target. When
    the heading, premise, and evidence stood immediately above it, `n` centred the
    options and made the reader scroll backward before they could answer. `lf-ask`
    encodes that broader unit while the nested x-awaits widget still owns the action:
    the walk focuses the first answering control, rings the region, and aligns the
    region's opening below the banner.
    """
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    resized(page, 900, 500)

    # The options really do begin below context, and enough page follows the region for
    # aligning its start to be possible. Without either condition, centring the inner
    # widget could happen to look like the requested arrival.
    before = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-ask').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          return {context: options.top - ask.top,
                  room: document.body.scrollHeight - document.body.clientHeight};
        }"""
    )
    assert before["context"] > 100, (
        "the fixture has no meaningful context above the options"
    )
    assert before["room"] > 500, "the page has no room to put the ask at its start"

    page.keyboard.press("n")
    expect(page.locator("#storage-options .lf-pick").first).to_be_focused()
    expect(page.locator("#storage-ask")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("#storage-options")).not_to_have_attribute("data-lf-ask", "1")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    landed = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-ask').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          const clear = parseFloat(getComputedStyle(document.body).scrollPaddingTop);
          return {ask: ask.top, options: options.top, clear};
        }"""
    )
    assert abs(landed["ask"] - landed["clear"]) <= 2, (
        f"the Ask starts at {landed['ask']:.1f}px instead of below the banner at "
        f"{landed['clear']:.1f}px"
    )
    assert landed["options"] > landed["ask"] + 100, (
        "the arrival did not leave the Ask's context above its options"
    )
    assert errors == []
    page.close()


def test_the_ask_walk_starts_from_where_the_reader_is(browser, serve):
    """The walk measures from the reader, the way d/u measure from the scroll position
    and j/k from the focused thread. It kept an id of its own instead, so every walk
    the reader had not made with this key started at the top of the page: scroll
    halfway down and press `n` and you were taken back past everything you had read,
    and so was anyone who had just selected a paragraph to comment on.

    Three readings of where they are, and the page is left in each state in turn: what
    they are reading, when they have pointed at nothing; what they have selected; and
    where the walk itself last left off, once the walk is what last moved them. The
    banner's button is no place — pressing it opens the tray and leaves the focus on
    itself, so a walk measured from the focus after it would restart on every press, and
    the ring is gone from the page by then, the reader being in the banner."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    # A window short enough that reading down the page leaves the top of it behind,
    # which is the whole of what the reader has to do to be somewhere.
    resized(page, 900, 400)

    # Scrolled to the change with nothing selected and nothing focused: the ask after
    # it, not the question above it. They are standing *in* that suggestion, which is
    # why it is the ask they step off rather than the one they step to.
    page.locator("#refill-now").evaluate("el => el.scrollIntoView({block: 'center'})")
    page.keyboard.press("n")
    expect(page.locator("#t-baffles")).to_have_attribute("data-lf-ask", "1")

    # The banner's press opens the tray and keeps the focus, so the walk after it
    # measures from where the reader stands in the page and steps on rather than
    # restarting — the button being no place to measure from.
    page.locator(".lf-asks").click()
    page.keyboard.press("n")
    expect(page.locator("#t-bath")).to_have_attribute("data-lf-ask", "1")

    # A selection outranks the mark, because it is the reader saying where they are
    # since the walk last moved them: from a task above the two the walk has just been
    # through, forward is the first of them and back is the change before it. Measured
    # after each landing, because the landing scrolled the page under the coordinates.
    def drag_over_the_done_task():
        page.locator("#t-mounts strong").scroll_into_view_if_needed()
        box = page.locator("#t-mounts strong").bounding_box()
        y = box["y"] + box["height"] / 2
        select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))

    drag_over_the_done_task()
    page.keyboard.press("n")
    expect(page.locator("#t-baffles")).to_have_attribute("data-lf-ask", "1")
    drag_over_the_done_task()
    page.keyboard.press("p")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")
    assert errors == []
    page.close()


def test_the_asks_tray_names_an_ask_a_message_carries(browser, serve):
    """An ask carried by a reply is an ask, and the tray has to name it in its words.

    The page holds none of its own, so the one row here is the question Claude put in
    the conversation — the AskUserQuestion shape, which reaches a reader through the
    panel and through this tray and nowhere else. It is read here exactly as a group
    on the page is read: the ask's own words, its label first, run together and cut at
    the row's cap. `startswith` for that reason — the cut is the tray's business and
    this is about which words reach it, which is the whole of what the row asserts for
    a page-borne ask two tests below.

    It read `rp-ask` before, and then read the label alone: a veto on chrome threw the
    reading away, and lifting it left the panel over the widget standing in for the
    widget's own chrome, so only a declared label got out. The reading is rooted at the
    ask now, so the layer above it is nobody's apparatus and the words underneath are
    the widget's own."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-which",
            "author": "user",
            "version": 1,
            "text": "Either would do. Which are you leaning towards?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-which",
            "version": 1,
            "text": "The second, but the cost lands on you either way:",
            "markup": (
                '<lf-options id="rp-ask" choose '
                'label="Which should I write up first?">'
                '<lf-option id="rp-now">The migration</lf-option>'
                '<lf-option id="rp-later">The rollback</lf-option>'
                "</lf-options>"
            ),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)
    assert len(rows) == 1, rows
    assert rows[0]["at"] == "rp-ask", rows
    assert rows[0]["says"].startswith("Which should I write up first?"), rows
    assert errors == []
    page.close()


def test_a_widget_a_message_carries_holds_the_room_its_words_will_need(browser, serve):
    """A measurement is a measurement wherever the widget was built, or it is a zero.

    Three shipped widgets take a number off a live box at upgrade — the room a pick
    mark's word will need, the room a card keeps clear of its grip, the width of a
    roster's state column — because a constant goes stale in the next face. A widget
    upgrades wherever the runtime connects it, and one of those places is a message body
    inside a comment panel nobody has opened: `display: none`, so every box under it is
    zero. `once` then refuses the second upgrade that would put it right and the body is
    cached for the life of the tab, so the zero is permanent.

    Nothing said so. The pick column collapsed to nothing, and the room arrived under
    the reader's pointer at the moment they pressed — the mark 17px wide, then 67, the
    row jumping 50px sideways as it gained the word "your pick".

    The reply is in the log before the page loads and the panel is shut, which is the
    only arrangement that reproduces it: a reply arriving into an open panel upgrades
    into boxes and was always right. Rooms are compared rather than named, because the
    number is the face's and this is about whether it was ever read.

    All three of them, because `measure` is the primitive and each module's wiring to it
    is its own line. Two of the three have no other reading anywhere that would notice
    one coming out."""
    url = serve(MESSAGE_ROOM_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-room",
            "author": "user",
            "version": 1,
            "text": "Anything else worth adding?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-room",
            "version": 1,
            "text": "These, and who is on them:",
            "markup": ROOM_WIDGETS.format(id="mr-msg"),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    held = {}
    for suffix, prop in ROOMS:
        held[suffix] = page.evaluate(ROOM_HELD, [f"mr-page{suffix}", prop])
        # Against a page that stopped reserving anything, where this would pass on both
        # sides reading the same nothing.
        assert held[suffix] not in ("0px", "", None), (suffix, prop, held)

    page.locator(".lf-comments").click()
    expect(page.locator("#mr-msg-q")).to_be_visible()
    # The re-measure is delivered with the layout that gave these their boxes, so the
    # reading waits for a frame that has been through one.
    page.evaluate(
        "() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    for suffix, prop in ROOMS:
        assert page.evaluate(ROOM_HELD, [f"mr-msg{suffix}", prop]) == held[suffix], (
            suffix,
            prop,
        )
    assert errors == []
    page.close()


def test_a_drag_across_a_question_in_a_reply_is_not_a_passage_of_the_page(
    browser, serve
):
    """A selection made in the panel is not the page's words, whatever it looks like.

    `leaf comment --section` refuses to anchor on a widget an agent sent, and it is the
    reading that is supposed to promise less than the browser's. The browser offered
    the 💬 over a question in a reply and wrote an anchor onto that widget's own id into
    an append-only log — naming a section no version holds, so it could never paint and
    never be found again.

    A declared label is the hole it came through: it is the page speaking inside the
    control it labels, so it answers the "are these the runtime's words" question for
    itself and the panel above it never got asked. That question was standing in for a
    second one nobody was putting — which document is this — and the drag needs both.

    The same drag on the page's own prose comes first and must raise the button. It is
    the control: this asserts an absence, and an absence proves nothing on a page where
    nothing was ever going to appear. The drags are real ones, so the mouseup guard is
    under test with the button.

    Then two turns of the macrotask queue, because the handler raises the button from a
    bare `setTimeout` — asserting straight after the drag reads the frame before the
    decision and passes whatever the decision would have been."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-store",
            "author": "user",
            "version": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-store",
            "version": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-options id="ps-ask" choose label="Which store should I write up?">'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options>"
            ),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    def drag(locator):
        expect(locator).to_be_visible()
        box = locator.bounding_box()
        y = box["y"] + box["height"] / 2
        select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
        return page.evaluate("() => getSelection().toString()")

    # The control, taken with the panel still shut: the same gesture on the page's own
    # words raises the button here. Opening the panel slides the document over, and a
    # drag run across that reads a box from the frame before and selects nothing — the
    # panel's own contents are fixed and stay where they are read.
    assert "signed-cookie" in drag(page.locator("#intro"))
    expect(page.locator(".lf-fab")).to_be_visible()
    # Put it down again, so what follows is a rise and not a leftover.
    page.locator("#h").click()
    expect(page.locator(".lf-fab")).to_be_hidden()

    page.locator(".lf-comments").click()
    assert "Which store" in drag(page.locator("#ps-ask [data-lf-said]").first)
    # Both turns the handler could have used: it defers with a bare setTimeout, and the
    # step it queues queues nothing further.
    for _ in range(2):
        page.evaluate("() => new Promise((r) => setTimeout(r))")
    expect(page.locator(".lf-fab")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_conversation_seated_in_a_widget_is_not_a_change_to_the_document(
    browser, serve
):
    """What a reader and an agent said to each other is not something the page changed.

    A widget declaring x-conversation grows a seat on the page, and the layer fills it
    from the log — messages the runtime built, wearing `.lf-ui` and `data-lf-gen`, and
    standing inside the widget out in `<main>`. The version diff walks every block the
    page holds and keys each by `wrote`, which is exactly the reading that leaves
    generated words out, so those blocks key to nothing and are skipped.

    They stopped being skipped when `wrote` was bounded at the element handed in: a
    reading can start *inside* generated chrome, and rooted at one of those `<p>`s the
    box above it was no longer over the reading. The base version is parsed unupgraded
    and holds no conversation at all, so every message became an insertion — the
    reader's own comment and the agent's reply painted as changes to the document, and
    the count in the version note inflated by both.

    The bound is the widget the reading belongs to now, and a conversation seat is
    inside its widget, so the box is between the words and their frame either way."""
    url = serve(CONVERSATION_DIFF_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "cd-thread",
            "author": "user",
            "version": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "cd-thread",
            "version": 1,
            "text": "It does, with the wider plate.",
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)
    # The seat is filled before the diff runs, or this asserts over a page that never
    # had the blocks in question.
    expect(page.locator("#cd-q .lf-conversation-msg")).to_have_count(2)

    (d / "versions" / "v2.html").write_text(
        CONVERSATION_DIFF_PAGE.replace(
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>',
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>\n'
            '<p id="cd-new">The north pair waits on brackets.</p>',
        )
    )
    events_model.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    expect(page.locator("#cd-q .lf-conversation-msg")).to_have_count(2)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map((e) => e.id)"
    ) == ["cd-new"], "the diff read the conversation as words the base version lacked"
    assert errors == []
    page.close()


def test_a_thread_on_a_widget_an_agent_sent_names_it_and_stands_apart(browser, serve):
    """A question the agent asked is not one of the runtime's own buttons.

    Design mode lets a reader comment on anything the layer draws, so a thread can be
    anchored on a widget that arrived in a reply. Two things were then said about it and
    both were wrong. The panel filed it under "The page's own layer", which groups the
    agent's question with the composer and the version chooser — the layer's parts wear
    the runtime's id namespace, which authored markup may not take, and that is what
    tells one from the other. And the thread's label read `§ ps-ask`, the bare id.

    The label is the part with the mechanism worth naming. An element anchor is labelled
    with its item's opening words, read when the node is built — and on the reconcile
    that first builds this node, the message body carrying the widget has not been
    connected yet, so the item did not exist and the reading came back empty. A node the
    reconcile keeps is never built again, so nothing asked a second time. It is repainted
    with the quote now, which is the pass that already exists for records whose subject
    the reconcile has just written."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-sent",
            "author": "user",
            "version": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-sent",
            "version": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-options id="ps-ask" choose label="Which store should I write up?">'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options>"
            ),
        },
    )
    # The shape design mode writes: an element anchor naming a widget no version holds.
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-on-sent",
            "author": "user",
            "version": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": "ps-ask"},
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-comments").click()

    thread = page.locator('.lf-thread[data-id="c-on-sent"]')
    expect(thread).to_be_visible()
    label = thread.locator(".lf-quote").inner_text()
    assert "Which store should I write up?" in label, label
    assert "ps-ask" not in label, label
    # The heading over it, and the layer's own name kept for the layer's own parts.
    groups = page.evaluate(
        "() => [...document.querySelectorAll('.lf-group')].map((g) => g.textContent)"
    )
    assert "Sent in the conversation" in groups, groups
    assert "The page's own layer" not in groups, groups
    assert errors == []
    page.close()


def test_a_change_says_which_of_the_three_it_is(browser, serve):
    """A row names its ask by kind and then by the ask's own opening words, and for a
    change those opening words are whichever half comes first — the current text, where
    there is one. So a deletion arrived on the tray under the words it was proposing to
    remove, with nothing to tell it from the insertion above it, which was proposing to
    add its own. Three shapes, one tag, one word for all of them.

    The tag is the right word wherever one tag is one kind of thing, which is every
    other widget here, so the fix is not to teach the tray about suggestions: the entry
    declares that this tag's word comes from its module (x-word), and the module reads
    it off the slots it holds. The group below is in this page to hold the other half of
    that — a widget declaring nothing still gets its tag, and would go on getting it if
    the declaration were dropped."""
    page, errors = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 1200, 900)

    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)

    assert {r["at"]: r["kind"] for r in rows} == {
        "sug-rewrite": "rewrite",
        "sug-insert": "insertion",
        "sug-delete": "deletion",
        "shapes-q": "options",
    }
    # The words beside the kind are still the element's own, and the two changes that
    # keep a current paragraph still open on it — the reading did not move, only what
    # is said about it.
    said = {r["at"]: r["says"] for r in rows}
    assert said["sug-delete"].startswith("Retries are logged"), said
    assert said["sug-insert"].startswith("Parked jobs"), said
    assert errors == []
    page.close()


def test_a_opens_a_tray_of_what_the_page_is_waiting_for(browser, serve):
    """`a` shows the list n/p walk, which until now the reader could only see by
    walking it: there was no way to tell what a page wanted without visiting each ask
    in turn, and no way to take them in any order but the page's.

    The rows are openAsks() and nothing else — the same list the banner counts — so
    they arrive in document order and a twelfth widget joins the tray by declaring
    x-awaits. Each says what kind of thing is asking and then the ask's own opening
    words, which is why the question here carries a `label`: without one, a group holds
    no part of the question it asks and its row reads as its first option instead. That
    is the whole reason the attribute exists, and this is the surface that shows it.

    A closed tray holds no rows at all. That is not tidiness: they are the open
    tray's rendering, the banner's count is the closed tray's, and a hidden list of
    buttons is a set of controls no reader can press — which the press sweep sees as
    the page's control set changing under it."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    tray = page.locator(".lf-asks-panel")
    expect(tray).to_be_hidden()
    assert page.evaluate(ASK_ROW_SAYS) == [], "a closed tray holds no rows"

    page.keyboard.press("a")
    expect(tray).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)
    assert [r["at"] for r in rows] == ASKS_IN_ORDER, (
        "the tray is openAsks() in document order, the list n/p walk"
    )
    for row in rows:
        assert row["w"] > 100 and row["h"] > 20, f"{row['at']}'s row has no usable size"
        assert row["kind"], f"{row['at']}'s row does not say what kind of thing asks"

    # The labelled group leads with its question. Before `label` there was nothing on a
    # group to read, and this row said "Keep the store Sessions stay where they are" —
    # the first option's case, which answers a question it never states.
    said = {r["at"]: r["says"] for r in rows}
    assert said["live-question"].startswith("Where should sessions live?"), said[
        "live-question"
    ]
    # A task's title is its own words already, so it needs no label to read out of
    # context — which is what says the row reads the element rather than the attribute.
    assert said["t-baffles"].startswith("Fit squirrel baffles"), said["t-baffles"]

    # Answered, and the row goes with the ask. The tray emptying is the progress, so
    # what is left on it is what is left to do — never a burn-down of everything done.
    page.locator("#lq-token").click()
    expect(page.locator(".lf-asks")).to_have_text("Asks (3)")
    expect(page.locator("button.lf-asks-row")).to_have_count(3)
    assert "live-question" not in [r["at"] for r in page.evaluate(ASK_ROW_SAYS)], (
        "an answered ask keeps a row on the tray"
    )

    # And closing takes the rest with it, for the reason the docstring gives: a tray
    # that is down is not a list, so it holds nothing to reach and nothing to press.
    page.keyboard.press("a")
    expect(tray).to_be_hidden()
    assert page.evaluate(ASK_ROW_SAYS) == [], "a closed tray keeps its rows"
    assert errors == []
    page.close()


def test_a_tray_the_reader_left_standing_comes_back_standing(browser, serve):
    """Reloading is not resetting: a tray someone stood up to watch stays stood, the
    rule the comment panel already keeps. Which makes the reload the one moment a
    tray is put up by something other than a press, and that is where it broke — the
    restore ran while the module was still evaluating and filled the tray from a
    reading of the page's open asks declared further down the file, so the reader who
    had left it open got a ReferenceError instead of a page.

    Nothing static could have caught it and neither could the render gate, which
    presses no keys and so never has a tray to restore. It took a reader with the
    tray open pressing reload, which is what this now is."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    page.keyboard.press("a")
    tray = page.locator(".lf-asks-panel")
    expect(tray).to_be_visible()
    expect(page.locator("button.lf-asks-row")).to_have_count(len(ASKS_IN_ORDER))

    page.reload(wait_until="networkidle")
    page.wait_for_function(BOTH_STAMPS)
    expect(tray).to_be_visible()
    expect(page.locator("button.lf-asks-row")).to_have_count(len(ASKS_IN_ORDER))
    # And the room it takes comes back with it, or the tray returns lying over the
    # column it is meant to stand beside.
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft !== '0px'"""
    )
    assert errors == [], errors
    page.close()


def test_a_row_stands_the_reader_on_the_control_that_answers_it(browser, serve):
    """Pressing a row does what `n` does — one function does both, so the tray can
    never drift into a second way of arriving at an ask. It scrolls there, rings the
    ask, and puts the focus on the control that answers it, which is what lets the
    reader answer in the page beside the words arguing for it rather than in the list.

    The ring lands in two places for one reason: the ask on the page and its row on the
    tray are two surfaces showing where the reader is standing, painted from the one
    reading of it (markHere), so neither can say something the other doesn't."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 620)
    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()

    # The last of the four, which a short window leaves well off screen.
    on_screen = """() => {
      const r = document.querySelector('#t-bath').getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight;
    }"""
    assert not page.evaluate(on_screen), (
        "the fixture must start with #t-bath off screen"
    )

    page.locator("button.lf-asks-row[data-lf-at='t-bath']").click()
    page.wait_for_function(on_screen)
    # A blocked task has no control of its own to answer it, so the ask itself takes the
    # focus — the landing is a place to stand either way.
    expect(page.locator("#t-bath")).to_be_focused()
    expect(page.locator("#t-bath")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("button.lf-asks-row[data-lf-at='t-bath']")).to_have_attribute(
        "data-lf-ask", "1"
    )
    # And one ask is standing, not two: the row is another box the same ask shows
    # through, never a second answer to where the reader is.
    marked = page.evaluate(
        """() => [...document.querySelectorAll('[data-lf-ask]')]
             .map((e) => e.id || e.getAttribute('data-lf-at'))"""
    )
    assert sorted(set(marked)) == ["t-bath"], marked
    assert errors == []
    page.close()


def test_the_asks_tray_takes_room_rather_than_covering_the_column(browser, serve):
    """A leaf's row is a way out of this page and an ask's row is a way around it, so
    pressing one sends the reader into the document — and a tray lying over the
    document would be hiding the thing it just sent them to. At a 720px column the two
    overlap on any window under about 1320px, which is most of them, so the strip comes
    out of the page the way the comment panel's does on the other side.

    Below twice the tray's own width there is no strip to take, and it covers instead —
    the same bargain at the same ratio the panel strikes, so a reader who has learned
    one edge has learned the other."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    geometry = """() => ({
      column: Math.round(document.querySelector('main').getBoundingClientRect().left),
      tray: Math.round(
        document.querySelector('.lf-asks-panel').getBoundingClientRect().right),
      sideways: document.documentElement.scrollWidth
                - document.documentElement.clientWidth,
    })"""

    resized(page, 1200, 800)
    page.keyboard.press("a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft !== '0px'"""
    )
    wide = page.evaluate(geometry)
    assert wide["column"] >= wide["tray"], (
        f"the tray covers the column: it ends at {wide['tray']} and the column "
        f"begins at {wide['column']}"
    )
    assert wide["sideways"] == 0, "the page scrolls sideways with the tray up"

    # Narrow enough and the strip is more than the page can give, so it covers.
    resized(page, 560, 800)
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft === '0px'"""
    )
    assert page.evaluate(geometry)["sideways"] == 0
    assert errors == []
    page.close()


def test_one_tray_stands_on_the_left_edge_at_a_time(browser, serve, other_leaf):
    """Both trays want the edge, so opening either closes the other. Which one is up
    is one fact in one place: a boolean per tray would be one guarantee written twice,
    and the two would first disagree the day a third surface opened one without closing
    the other — leaving two trays over one edge with the lower unreachable.

    Escape names whichever is up rather than saying "close the tray" over two of
    them, which is the rung the reader is actually holding.

    The `other_leaf` fixture is the whole reason the leaves tray has anything to show:
    a tray of one — the page the reader is already on — is not worth a control, so
    without a neighbour `l` is dead and there is no second tray to be exclusive with."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    asks, leaves = page.locator(".lf-asks-panel"), page.locator(".lf-others-panel")

    page.keyboard.press("a")
    expect(asks).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("l")
    expect(leaves).to_be_visible()
    expect(asks).to_be_hidden()
    # The page has its room back the moment the asks tray goes down.
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft === '0px'"""
    )

    page.keyboard.press("a")
    expect(asks).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("Escape")
    expect(asks).to_be_hidden()
    expect(leaves).to_be_hidden()
    assert errors == []
    page.close()


def test_the_ring_is_one_box_around_the_whole_change(browser, serve):
    """A suggestion is one ask, so it wears one ring, whatever its slots are made of.

    The wrapper generated no box once — the same "take the form your content takes" with
    the box left out — and an element with none measures (0,0) at the document's origin,
    which is not a degenerate answer but a wrong one. Everything that asked the wrapper
    where it was believed it, so the travel centred the top of the document and a page
    whose open asks were all suggestions answered `n` by appearing to do nothing at all.

    Hanging the ring on the pieces instead covered that and said the wrong thing about
    the change: two outlines meeting down the middle of a sentence, or stacked across
    two block slots, read as two boxes touching rather than as the one ask the reader is
    standing in. So what is asserted here is that the reader is taken to the change, and
    that the wrapper alone wears the mark, in one box reaching round both slots."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    # Short enough that reaching the change is travel rather than a press with the
    # change already on screen.
    resized(page, 900, 400)

    # Where the change stands, which is where its contents paint — the wrapper's own
    # rect answers this question wrongly, which is the whole subject here. Whole in the
    # window rather than merely overlapping it: the bug leaves the change a little below
    # the fold, so "some part of it showing" is a bar the wrong answer can clear.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("n")
    expect(page.locator("#live-question")).to_have_attribute("data-lf-ask", "1")
    # Where the reader now stands, which is what the next press is measured against. The
    # bug takes them to the document's origin, so a scroll that ends *below* where they
    # started is the whole of what says they were carried to the change instead.
    #
    # Said that way rather than as "the change was off screen before the press": that was
    # true by a few dozen pixels, which made it a fact about how tall the blocks above the
    # change happened to be. Giving the question above it a label set one more line and
    # the precondition stopped holding, with nothing wrong anywhere.
    was = page.evaluate("() => document.body.scrollTop")
    assert was > 0, "the reader must have somewhere to have come from"

    page.keyboard.press("n")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # The condition everything below rests on, stated rather than assumed: put
    # display: contents back on the wrapper and it measures (0,0), the mark paints
    # nothing, and the count further down passes on an element no reader can see.
    box = page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    )
    assert box[0] > 40 and box[1] > 10, f"the wrapper drew no box to ring: {box}"

    # The travel is a glide, so the fact to wait on is that it has finished. Both
    # assertions are then about the landing: measured from the wrapper's own rect the
    # change sits at the document's origin, so the reader is carried to the top of the
    # page — up from where they stood, with the change still below the fold.
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    assert page.evaluate("() => document.body.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # What wears the mark: the wrapper, which carries the id every reader of the mark
    # asks after. Not the slots, and not the empty span the widget prepends to itself to
    # anchor its controls from — a 2px mark of its own beside the change is not the
    # promise.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')].map(e => {
      return { what: e.id || e.tagName, fragments: e.getClientRects().length,
               ring: getComputedStyle(e).outlineStyle !== 'none' };
    })""")
    assert [m["what"] for m in marks] == ["sug-refill"]
    assert marks[0]["ring"]
    # One fragment, so the outline closes round the change once. An inline box broken
    # around block children has three and draws no visible edge on any of them, which is
    # what a wrapper that only says `inline` gets for a change made of paragraphs.
    assert marks[0]["fragments"] == 1, marks

    # And the box reaches round both slots, which a ring on the pieces could not promise:
    # the reader is standing in the change, not in half of it.
    assert page.evaluate("""() => {
      const w = document.getElementById('sug-refill').getBoundingClientRect();
      return ['refill-was', 'refill-now'].every(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return r.top >= w.top - 1 && r.bottom <= w.bottom + 1
            && r.left >= w.left - 1 && r.right <= w.right + 1; });
    }"""), "the wrapper's box does not reach round both slots"

    assert errors == []
    page.close()


def test_the_walk_travels_to_an_ask_a_page_left_boxless(browser, serve):
    """`display: contents` is one line of CSS, and a page or a project layer can put it
    on anything. Nothing in the shipped vocabulary carries it now, so this case only
    reaches the runtime from outside — which is where the reading has to hold, because
    an element generating no box measures (0,0) at the document's origin and every
    consumer that believes it travels to the top of the page.

    The travel reads where the content paints (shownBox), and the ring hangs on the
    boxes the ask shows through (shownParts) — the same answer an element-anchored
    comment's outline gives, so the walk's mark and the thread's cannot disagree about
    where a boxless ask is. The outermost mark still names the ask, one place for the
    reader to be standing."""
    styled = ASKS_PAGE.replace(
        "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
    )
    page, errors = open_page(browser, serve(styled))
    resized(page, 900, 400)

    # Asked of what the change paints, since the wrapper itself no longer says: this is
    # the reading the runtime has to take for the travel to land anywhere real. Whole in
    # the window because merely overlapping it is a state the glide passes through.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("n")
    expect(page.locator("#live-question")).to_have_attribute("data-lf-ask", "1")
    was = page.evaluate("() => document.body.scrollTop")
    assert was > 0, "the reader must have somewhere to have come from"

    page.keyboard.press("n")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")
    assert page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    ) == [0, 0], "the page's own style no longer takes the wrapper's box away"
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    assert page.evaluate("() => document.body.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # The ask and the boxes it shows through wear the mark, the ask outermost — one
    # place to stand, painted where the reader can see it.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the mark went somewhere else than the ask and its shown boxes: {marks}"
    expect(page.locator(STANDING_ASK)).to_have_count(1)

    assert errors == []
    page.close()


def test_a_commented_ask_does_not_wear_its_ring_on_the_runtime_s_own_note(
    browser, serve
):
    """The boxes an ask shows through are the page's, never the runtime's.

    The paint pass writes one hidden line per block holding a comment, saying how many
    it holds, and for an element anchor that line lands inside the element the anchor
    names. It is clipped to a pixel, so it has a box — and a wrapper that draws none of
    its own then had two children with area, its slot and the runtime's word about the
    page. Area alone kept the wrong ones out only by luck: the family's control line
    happens to be zero-wide, and this one is not.

    The order is why nothing caught it. The note is written after the marks are placed,
    so the first paint of a page sees no note and the ring is right; it moves onto the
    pixel on the next pass — which the ask walk always is, the reader having pressed a
    key. So the fault needs a comment on the page *and* a repaint, and shows as a 1px
    ring beside the change instead of on it.

    The shipped wrapper draws a box of its own now, so the page supplies the boxless
    one here — the line of CSS any page can write is what keeps this reachable."""
    url = serve(
        ASKS_PAGE.replace(
            "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
        )
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "Does this hold when the camera is offline?",
            "anchor": {"section": "sug-refill"},
        },
    )
    page, errors = open_page(browser, url)
    # The note is what this test is about, so its presence is stated rather than assumed:
    # without it every assertion below holds for the wrong reason.
    note = page.locator("#sug-refill .lf-mark-note")
    expect(note).to_have_count(1)

    page.keyboard.press("n")
    page.keyboard.press("n")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # By tag rather than by class: the slots are wearing the comment's own outline too,
    # this ask being the one that carries the comment, and a class would read that back
    # instead of naming the element.
    marks = page.evaluate("""() => [...document.querySelectorAll('[data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the ring reached past the page's own boxes: {marks}"
    expect(page.locator("#sug-refill .lf-mark-note[data-lf-ask]")).to_have_count(0)
    assert errors == []
    page.close()
