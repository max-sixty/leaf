"""Suggestions: their margin controls and labels, accepting, rejecting and undoing a
change, folding a decided change away, and recovering from a refused decision."""

import re

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import (
    COLLAPSED_PAGE,
    HOLD_MOTION,
    PROPOSED_PAGE,
    REBUILT_INLINE_PAGE,
    SHORT_SUGGESTION,
    SUGGESTION_PAGE,
    SWAP_PAGE,
)
from render_cases_layout import unfolded_button
from render_cases_navigation import actions
from render_harness import (
    consume_browser_errors,
    expect_comment_notes,
    holding,
    http_error_console,
    leaf_page,
    margins_laid_out,
    open_page,
    painted_words,
    panel_field,
    panel_menu,
    refuse,
    resized,
    root_overflow,
    round_trip,
    sending,
    undo,
)

from browser.widgets import expect_accept_all
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def expect_no_notice(page, words):
    """Read that no passing notice says `words`: the panel says one in its empty
    field's place (floating-panel.js), so a decision the live region alone announces
    leaves the field saying something else."""
    expect(panel_field(page)).not_to_have_attribute("placeholder", re.compile(words))


def test_suggestions_sharing_a_block_keep_source_and_keyboard_order(browser, serve):
    """Decision rows keep source order in the margin layer, and so in the tab order,
    through upgrade and reconnection."""
    source = leaf_page(
        "suggestion-order",
        """
<h1>Release wording</h1>
<section id="shared-block">
  <p>First <lf-suggestion id="first-change"><lf-new>first proposal</lf-new></lf-suggestion>.</p>
  <p>Second <lf-suggestion id="second-change"><lf-new>second proposal</lf-new></lf-suggestion>.</p>
  <p>Third <lf-suggestion id="third-change"><lf-new>third proposal</lf-new></lf-suggestion>.</p>
</section>
""",
    )
    page = open_page(browser, serve(source))
    rows = page.locator(".lf-margin-cluster")
    expect(rows).to_have_count(3)
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.lfMarginFor)") == [
        "first-change",
        "second-change",
        "third-change",
    ]
    page.locator("#first-change").evaluate(
        "el => lfUnwatched(() => { const parent = el.parentNode; const next = el.nextSibling;"
        "        el.remove();"
        "        parent.insertBefore(el, next); })"
    )
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.lfMarginFor)") == [
        "first-change",
        "second-change",
        "third-change",
    ], "reconnecting the first suggestion moved its controls after later source rows"
    first_accept = page.locator("[data-lf-margin-for='first-change'] .lf-sug-accept")
    first_accept.evaluate(
        """control => lfUnwatched(() => {
          control.disabled = true;
          const widget = document.getElementById('first-change');
          const parent = widget.parentNode;
          const next = widget.nextSibling;
          widget.remove();
          parent.insertBefore(widget, next);
        })"""
    )
    expect(first_accept).to_be_enabled()
    page.locator("[data-lf-margin-for='first-change'] .lf-sug-accept").focus()
    walked = []
    for _ in range(3):
        walked.append(
            page.evaluate(
                "() => document.activeElement.closest('.lf-margin-cluster')"
                "?.dataset.lfMarginFor"
            )
        )
        # Each row has two decision controls, and the roving semantic marker now joins
        # them in the same item. Walk past whichever row currently owns that one stop.
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        # The rows stand after the page's content in the margin layer, so the last
        # row's Tab leaves the document.
        if page.evaluate("() => document.activeElement.matches('.lf-margin-marker')"):
            page.keyboard.press("Tab")
    assert walked == ["first-change", "second-change", "third-change"]


@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_suggestion_controls_stay_out_of_the_column(browser, serve, reduced_motion):
    """Suggestion chrome hangs in the page margin, so the prose keeps the full column
    and reads as it will once the change is settled. The row takes its line
    from an anchor inside the change, so how deep the
    change sits costs it nothing: one inside a card — a positioned ancestor, which
    `left: 100%` used to resolve against, dropping the row back into the text —
    hangs in the rail beside its card like any other. What is left is a
    measurement no lint can make: where a row stands as a pin, it touches the change
    it decides, over none of the change's words, and stays on the page."""
    page = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.emulate_media(reduced_motion=reduced_motion)
    # main includes the grid's margins; this paragraph fills its prose track.
    column = page.locator("#replace").evaluate("el => el.getBoundingClientRect().right")
    box = "el => el.getBoundingClientRect()"

    margin_rows = page.locator(
        "[data-lf-margin-for='sug-refill'], [data-lf-margin-for='sug-thistle']"
    )
    assert margin_rows.count() == 2
    for i in range(2):
        assert margin_rows.nth(i).evaluate(box)["left"] > column, (
            "a control row overlapping the column re-wraps the prose it reviews"
        )
    # Two changes a line apart, so the rows would collide at their natural offsets.
    first, second = (margin_rows.nth(i).evaluate(box) for i in range(2))
    assert first["bottom"] <= second["top"], "control rows must not stack on each other"

    # The board grows past the rail, so the row pins near the change. Its seat can
    # move off the card when that is the nearest room that covers no words.
    in_card_row = page.locator("[data-lf-margin-for='sug-in-card']")
    expect(in_card_row).to_have_attribute("data-lf-place", "pin")
    stands_by = """(row, words) => {
      const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
      const change = row.lfTarget;
      const entries = [...row.querySelectorAll('.lf-margin-entry')]
        .filter((entry) => entry.checkVisibility())
        .map((entry) => edges(entry.getBoundingClientRect()));
      const hit = (a, b) => a.left < b.right && b.left < a.right
        && a.top < b.bottom && b.top < a.bottom;
      const r = row.getBoundingClientRect();
      const touches = [...change.getClientRects()].some(part =>
        Math.hypot(
          Math.max(0, r.left - part.right, part.left - r.right),
          Math.max(0, r.top - part.bottom, part.top - r.bottom)) <= 12);
      return {
        covers: entries.filter((e) => words.some((w) => hit(e, w))).length,
        touches,
        inPage: r.right <= document.body.getBoundingClientRect().right,
      };
    }"""
    placed = in_card_row.evaluate(stands_by, painted_words(page, "#sug-in-card"))
    assert placed == {
        "covers": 0,
        "touches": True,
        "inPage": True,
    }, f"a change inside a board is decided by its target: {placed}"

    # No rail: every row is a pin by its own change, and nothing spills sideways.
    resized(page, 820, 900)
    page.wait_for_function(
        "() => [...document.querySelectorAll('[data-lf-margin-for^=sug-]')]"
        ".every(r => r.dataset.lfPlace === 'pin')"
    )
    assert root_overflow(page) == 0
    for widget in ("sug-refill", "sug-in-card"):
        placed = page.locator(f"[data-lf-margin-for='{widget}']").evaluate(
            stands_by, painted_words(page, f"#{widget}")
        )
        assert placed == {
            "covers": 0,
            "touches": True,
            "inPage": True,
        }, f"a pin stands by the change it decides, over none of its words: {placed}"


def test_the_page_says_a_change_is_only_proposed(browser, serve):
    """Who says the change is still a proposal, in each medium the page reaches.

    On screen the ✓/✗ row hanging on the change's own line says it, and the word is
    for whoever is listening, so it stays clipped. Paper has no row, so each pending
    slot needs visible words distinguishing a proposal from ordinary settled content.

    The word also had to change to be worth showing. Pendingness was carried by the
    word's mere presence, which no user can perceive — nothing sits alongside to
    compare it against — and `deletion` is ARIA's own name for the completed act, so
    a listener heard the change announced as made while the page was still asking."""
    url = serve(PROPOSED_PAGE)
    page = open_page(browser, url)

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
    # And the row is there to say it — the fact paper is about to lose.
    expect(page.locator(".lf-margin-cluster")).to_have_count(3)

    page.emulate_media(media="print")
    shown = page.evaluate(read, quiet)
    assert [q["word"] for q in shown] == [q["word"] for q in live], shown
    for q in shown:
        assert q["shown"] and q["w"] > 1, (
            f"with no row on paper, `{q['word']}` is the only thing saying the "
            f"change is unmade, and it is not printed: {q}"
        )


def test_a_moved_change_takes_its_controls_with_it(browser, serve):
    """The row is the column's child, not the change's, so the subtree a card
    travels in no longer carries it: a card dragged to another column, or moved by
    the replay of someone else's drag, leaves and re-enters the document with its
    row unhooked. Re-connection has to hang it again, or the user loses the
    only way to decide a change that is still plainly pending on the page. Replayed
    rather than dragged, because that is the same move with no gesture in the way."""
    url = serve(SUGGESTION_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeders",
            "action": "move",
            "detail": {"unit": "card-heater", "value": "col-done", "rank": "0i"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_be_visible()
    page.locator("#col-done #card-heater").scroll_into_view_if_needed()
    margins_laid_out(page)
    box = "el => el.getBoundingClientRect()"
    row = page.locator("[data-lf-margin-for='sug-in-card']")
    expect(row).to_be_visible()
    # The row stands on the moved card. Clear-space seating may put it above the
    # changed words, but it must travel with the card and remain actionable.
    card = page.locator("#card-heater").evaluate(box)
    stands = row.evaluate(box)
    assert (
        card["top"] - 5 <= stands["top"] and stands["bottom"] <= card["bottom"] + 5
    ), "the row must travel with the moved card"
    assert card["left"] < stands["right"] <= card["right"] + 40, (stands, card)
    row.locator(".lf-sug-accept").click()
    expect(page.locator("#sug-in-card lf-old")).to_be_hidden()


# A change the user hasn't opened yet. The row hangs off an anchor in the
# change, and a collapsed container reports its content's last rendered geometry
# rather than nothing at all — so a row that trusted a measurement would hang in
# the margin deciding a change nobody can see.


def test_an_undone_suggestion_stays_inline_among_the_words(browser, serve):
    """A declared inline widget keeps suggestion slots inline, including after undo."""
    source = REBUILT_INLINE_PAGE.replace(
        "<lf-new>Valkey</lf-new>",
        '<lf-new><lf-gloss id="replacement-name" tip="A Redis-compatible store.">Valkey</lf-gloss></lf-new>',
    )
    page = open_page(browser, serve(source))
    form = "() => getComputedStyle(document.querySelector('#sug-store lf-new')).display"
    expect(page.locator("#replacement-name")).to_have_attribute("data-lf-inline", "")
    assert page.evaluate(form) == "inline"
    page.locator("[data-lf-margin-for='sug-store'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-store lf-old")).to_be_hidden()
    undo(page)
    expect(page.locator("#sug-store lf-old")).to_be_visible()
    assert page.evaluate(form) == "inline"


def test_a_whole_swap_paints_no_emphasis(browser, serve):
    """An alignment that shares almost nothing is a replacement, not an edit, and
    emphasis over everything says nothing — the similarity gate every mature diff
    view applies. The whole-slot tints already say a swap is on offer."""
    page = open_page(browser, serve(SWAP_PAGE))
    total = page.evaluate(
        "() => (CSS.highlights.get('lf-sug-del')?.size ?? 0)"
        " + (CSS.highlights.get('lf-sug-ins')?.size ?? 0)"
    )
    assert total == 0, "unrelated old and new text must not be word-marked"


def test_a_row_waits_for_the_change_it_decides_to_be_on_screen(browser, serve):
    """A change inside a collapsed container has no line for its row to hang on,
    and an anchor that isn't rendered is no anchor at all: the row falls back to
    the block it was hoisted to and hangs there in the margin, offering to decide
    something the user can't see. It waits instead, and arrives on the change's
    own line the moment the container opens — a real click on the summary, because
    opening it is the user's gesture and the reflow it causes is the point."""
    page = open_page(browser, serve(COLLAPSED_PAGE))
    waiting = page.locator("[data-lf-margin-for='sug-boxes']")
    expect(page.locator("[data-lf-margin-for='sug-now']")).to_be_visible()
    expect(waiting).to_be_hidden()

    page.locator("#sum").click()
    expect(waiting).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = waiting.evaluate(box)
    assert row["left"] > page.locator("#deferred").evaluate(box)["right"], (
        "the row must arrive in the margin, not over the prose that just opened"
    )
    assert (
        abs(row["top"] - page.locator("#sug-boxes lf-new").evaluate(box)["top"]) <= 5
    ), "and on the line of the change it decides"


def test_the_obligation_walk_lands_on_a_suggestion_the_reveal_just_opened(
    browser, serve
):
    """Stepping the obligations opens the closed <details> a change waits inside, and does
    it in the same task as the arrival. The row un-waits as the arrival lands rather than
    at the observer's next frame: settled asynchronously, the arrival landed
    on a display:none element and the user stayed where they were — at the previous
    decision — while the announce said otherwise, so Enter was aimed at a decision they
    had already seen."""
    page = open_page(browser, serve(COLLAPSED_PAGE))
    page.keyboard.press("m")
    expect(page.locator("#sug-now[data-lf-obligation]")).to_have_count(1)
    page.keyboard.press("m")
    expect(page.locator("#later")).to_have_attribute("open", "")
    expect(page.locator("#sug-boxes[data-lf-obligation]")).to_have_count(1)
    # The arrival stands on the suggestion; what the reveal has to have done is leave the
    # control that answers it a thing the user can reach, which a display:none control
    # is not.
    expect(
        page.locator("[data-lf-margin-for='sug-boxes'] .lf-sug-accept")
    ).to_be_visible()


def test_accepting_a_suggestion_settles_it_and_reaches_claude(browser, serve):
    """Accepting collapses the change to the proposal as ordinary prose — no
    tint, no strike — because the live view is the version plus the user's
    actions, and the honoring version only has to catch up.
    The outcome has to reach the log too: what the user sees settle and what
    Claude is told must be the same event.

    The resulting content and Undo control are sufficient visual confirmation. No
    status or transient notice repeats them, while the live region says the same
    decision for a user listening to the page.

    A replacement's slots paint whole — which is all a dead copy keeps — and on the live
    page the words that differ deepen through the highlight registry, so the user isn't
    left to eyeball-diff two paragraphs; deciding clears the emphasis with the slot it
    retires. And a few words swapped inside a line are swapped, not folded: a height to
    animate would hold a block box over the slot and open a paragraph break."""
    page = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    inside = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    refill = page.evaluate(inside, "sug-refill")
    assert refill["lf-sug-del"] >= 1 and refill["lf-sug-ins"] >= 1, (
        "an edited sentence must emphasize the words that moved, on both sides"
    )
    row = page.locator("[data-lf-margin-for='sug-refill']")
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
    before = accept.evaluate(box)
    # The verb is discovery chrome; at rest the margin entry is its icon alone.
    expect(accept.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "check"
    )

    # A strike and two tints say which words are going and which are proposed, and say
    # it in no text at all: a user listening got the sentence twice, the two readings
    # contradicting each other, with nothing to say either was a change.
    assert "deletion" in page.locator("#sug-refill lf-old").aria_snapshot()
    assert "insertion" in page.locator("#sug-refill lf-new").aria_snapshot()

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    assert page.evaluate(inside, "sug-refill") == {
        "lf-sug-del": 0,
        "lf-sug-ins": 0,
    }, "deciding must clear the emphasis with the slot it retires"
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a few words swapped inside a line were given a fold, and a block box to do it in"
    )
    expect(accept).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo_button.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "undo"
    )
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Accepted")
    assert undo_button.get_attribute("data-lf-said") is None
    expect(undo_button).to_be_enabled()
    expect(undo_button).to_be_focused()
    assert undo_button.evaluate(box) == before, (
        "Undo moved away from the press it replaces"
    )
    expect_no_notice(page, "Accepted")
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^Accepted suggested change: Refill a feeder when")
    )
    expect(reject).to_be_hidden()
    settled = page.locator("#sug-refill lf-new").evaluate(
        "el => getComputedStyle(el).textDecorationLine + ' ' + getComputedStyle(el).backgroundColor"
    )
    # And the word goes with the marks, the settled slot being ordinary prose now:
    # a user listening is told about a change while there is one to decide.
    assert "insertion" not in page.locator("#sug-refill lf-new").aria_snapshot()
    assert "line-through" not in settled and "rgba(0, 0, 0, 0)" in settled, (
        f"settled text still wears a pending mark: {settled}"
    )
    # The menu's count follows the page: three pending, one decided.
    expect_accept_all(page, 2)

    # The boundary before reading the shared log: what the press sent has to have a
    # definitive outcome first. The fetch this replaced proved nothing —
    # `wait_for_function` awaits the promise a predicate returns, but a falsy
    # resolution ends the wait instead of polling again, so it came back `False` on
    # the first poll and the read below ran unguarded.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"], e["author"]) for e in logged] == [
        ("sug-refill", "decide", "user")
    ]


def test_a_pointer_decision_announces_without_needing_button_focus(browser, serve):
    """The live result is independent of browsers focusing a clicked margin entry."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    assert page.evaluate("document.activeElement === document.body")

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").evaluate(
        "button => button.click()"
    )

    assert page.evaluate("document.activeElement === document.body")
    expect(page.locator(".lf-live")).to_have_text(
        re.compile(r"^Accepted suggested change: Refill a feeder when")
    )
    expect_no_notice(page, "Accepted")


def test_a_settled_deletion_keeps_undo_on_the_containing_passage(browser, serve):
    """A pure deletion leaves no suggestion box, but Undo remains reachable."""
    page = open_page(browser, serve(PROPOSED_PAGE))
    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()

    expect(page.locator("#sug-delete")).to_be_hidden()
    undo = page.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo).to_be_visible()
    expect(
        undo.locator("xpath=ancestor::*[contains(@class, 'lf-margin-cluster')]")
    ).not_to_have_class(re.compile(r"\blf-withheld\b"))
    expect(page.locator(".lf-margin-receipt")).to_have_count(0)


def test_a_settled_boxless_suggestion_keeps_its_own_margin_identity(browser, serve):
    """A `display: contents` suggestion still paints through its children; settling it
    must not re-perch Undo on the containing section and change the map target."""
    styled = SHORT_SUGGESTION.replace(
        "</head>", "<style>#sug { display: contents; }</style>\n</head>"
    )
    page = open_page(browser, serve(styled))
    item = page.locator("[data-lf-margin-for='sug']")
    assert item.evaluate("row => row.lfTarget.id") == "sug"

    item.locator(".lf-sug-accept").click()
    expect(
        item.get_by_role("button", name=re.compile(r"^Undo accepting"))
    ).to_be_visible()
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    assert item.evaluate("row => row.lfTarget.id") == "sug"


def test_a_refused_undo_keeps_the_outcome_and_its_undo(browser, serve):
    """Reject leaves an active Undo, never a dead circle or a second status. A refused
    Undo restores the outcome and leaves Undo to press again, without inventing a
    counter-decision."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    row = page.locator("[data-lf-margin-for='sug']")
    reject = row.locator(".lf-sug-reject")
    with sending(page, "the decision to be withdrawn"):
        unfolded_button(reject).click()
    expect(reject).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo rejecting"))
    expect(undo_button).to_have_attribute("data-lf-margin-entry-primary", "")
    expect(row.locator(".lf-sug-accept")).to_be_hidden()
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Rejected")
    decision = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["detail"]["outcome"] == "reject"
    )
    refused = []

    def refuse_undo(route):
        event = route.request.post_data_json
        if event["kind"] != "undo":
            route.continue_()
            return
        refused.append(event)
        route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        )

    page.route("**/api/event", refuse_undo)
    with sending(page, "the refused withdrawal"):
        row.get_by_role("button", name=re.compile(r"^Undo rejecting")).click()
    assert [(event["kind"], event["undoes"]) for event in refused] == [
        ("undo", decision["id"])
    ]
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "reject")
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("Couldn't take this")
    )
    consume_browser_errors(page, http_error_console(400))
    page.unroute("**/api/event")
    with sending(page, "the repeated withdrawal"):
        row.get_by_role("button", name=re.compile(r"^Undo rejecting")).click()
    expect(page.locator("#sug")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    expect(page.locator("[data-lf-margin-for='sug'] .lf-sug-accept")).to_be_visible()
    logged = events_model.read_events(serve.page_dir)
    assert [event["undoes"] for event in logged if event["kind"] == "undo"] == [
        decision["id"]
    ]


def test_a_widget_naming_its_own_words_does_not_read_the_runtimes(browser, serve):
    """The line saying a block carries a comment goes in the block, and a block inside a
    widget is still a block — so `textContent` on a widget's own slot now returns the
    author's words with the runtime's appended. A suggestion labels itself from that slot,
    and offered to accept “Retry three times. 1 comment”. It reads the slot the way the
    page is read instead, which is what `says` is for — read before deciding, because a
    reject retires the very slot the label comes from, and a retired slot says nothing:
    the announcement then named the widget's id instead of the words the user judged. Short
    on purpose: the label cuts at 48 characters, which hid this on every shipped example."""
    url = serve(SHORT_SUGGESTION, anchored=[("now", "Retry three times")])
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Vacuous otherwise: the slot the label is read from has to carry the comment.
    expect_comment_notes(page, "lf-new #now", 1)
    # Accept rests in the rail as the target's primary margin entry, and reject is one
    # press behind `…`; an undo between them hands the decision back.
    for outcome, verb, folded in (
        ("accept", "Accepted", False),
        ("reject", "Rejected", True),
    ):
        control = page.locator(f"[data-lf-margin-for='sug'] .lf-sug-{outcome}")
        (unfolded_button(control) if folded else control).click()
        expect(page.locator(".lf-live")).to_have_text(
            f"{verb} suggested change: Retry three times."
        )
        if outcome == "accept":
            expect_no_notice(page, verb)
        else:
            # The undo before it said so in the notice; the decision says nothing there.
            expect_no_notice(page, verb)
        round_trip(page)
        if outcome == "accept":
            undo(page)
            expect(page.locator("#sug")).not_to_have_attribute(
                "data-lf-state", re.compile(".+")
            )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_decided_change_folds_away_rather_than_vanishing(engine, request, serve):
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
    be the harm rather than the fix.

    Firefox, which interpolates neither `calc-size()` nor `display`, folds from the
    slot's measured height and keeps the retired slot drawn without the animation."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(SHORT_SUGGESTION),
        init_script=HOLD_MOTION,
    )
    old = page.locator("#sug lf-old")
    after = page.locator("#after")
    tall = old.evaluate("el => el.getBoundingClientRect().height")
    assert tall > 0
    below = after.evaluate("el => el.getBoundingClientRect().top")

    page.locator("[data-lf-margin-for='sug'] .lf-sug-accept").click()
    # The state lands in the frame of the press. Its fold then carries the pixels toward
    # that already-current reading while the outbox carries it toward the log.
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

    # Undo during a later fold returns the same ordinary box, with no filled effect
    # or temporary sizing style keeping the retired presentation alive.
    round_trip(page)
    undo(page)
    expect(old).to_be_visible()
    page.locator("[data-lf-margin-for='sug'] .lf-sug-accept").click()
    round_trip(page)
    page.evaluate(
        "() => { const m = window.__lfHeld.at(-1);"
        " m.currentTime = m.effect.getTiming().duration / 2; }"
    )
    assert 0 < page.evaluate(at) < tall
    undo(page)
    expect(old).to_be_visible()
    assert page.evaluate(at) == pytest.approx(tall, abs=1)
    assert old.evaluate("el => el.getAnimations().length") == 0


def test_a_user_who_asked_for_less_motion_gets_the_collapse_at_once(browser, serve):
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
    page = open_page(
        browser, serve(SHORT_SUGGESTION), context=context, init_script=HOLD_MOTION
    )
    page.locator("[data-lf-margin-for='sug'] .lf-sug-accept").click()
    expect(page.locator("#sug lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a user who asked for less motion was given a fold to sit through"
    )


def test_accept_all_decides_every_pending_suggestion(browser, serve):
    """The menu's Accept all is a shortcut for the user who has read the page
    and wants all of it, so it has to reach the ones their eye didn't: the
    suggestion inside a widget, whose controls stand on the widget as a pin rather
    than in the rail. Each is decided individually, so the log records what was
    consented to one change at a time rather than one blanket yes."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    expect_accept_all(page, 3)

    # A press after a semantic change resolves the current open inventory rather than
    # replaying the list from an earlier reading.
    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    expect(
        page.locator("[data-lf-margin-for='sug-refill']").get_by_role(
            "button", name=re.compile(r"^Undo accepting")
        )
    ).to_be_enabled()
    expect_accept_all(page, 2)
    panel_menu(page).locator('.lf-fp-item[data-row="blanket:accept"]').click()

    for widget in ("sug-refill", "sug-thistle", "sug-in-card"):
        expect(page.locator(f"#{widget} lf-new")).to_be_visible()
        # Waited for, not read once: each is decided by its own round trip, so the
        # last of them is still in flight when the first has settled. Undo stands
        # disabled while the decision it takes back is in the wire, so an enabled
        # one is this row's own answer come back.
        undo_button = page.locator(f"[data-lf-margin-for='{widget}']").get_by_role(
            "button", name=re.compile(r"^Undo accepting")
        )
        expect(undo_button).to_be_visible()
        expect(undo_button).to_be_enabled()
        expect(
            page.locator(f"[data-lf-margin-for='{widget}'] .lf-margin-receipt")
        ).to_have_count(0)
    for widget in (
        "sug-refill",
        "sug-in-card",
    ):  # the two that replace rather than insert
        expect(page.locator(f"#{widget} lf-old")).to_be_hidden()
    # Nothing left to accept, so the menu offers nothing rather than saying zero.
    expect_accept_all(page, 0)

    # Every decision above is settled; this is the boundary for a stray post the
    # sequence below would otherwise read as absent.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["detail"].get("outcome", e["action"])) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]


def test_a_refused_decision_returns_to_pending(held_events, serve):
    """The reversible result paints immediately, then a refusal restores the offer:
    the server's state comes back with Accept and Reject, and pressing Accept again is
    the retry."""
    browser, held = held_events
    page = open_page(browser, serve(SUGGESTION_PAGE))
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    item.locator(".lf-sug-accept").click()

    holding(page, held, 1, "the accepted suggestion")
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item.get_by_text("Accepted", exact=True)).to_have_count(0)

    held.pop(0).fulfill(
        status=400,
        json={
            "ok": False,
            "error": "refused before append",
            "final": True,
        },
    )
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.locator("#sug-refill").get_attribute("data-lf-state") is None
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item.locator(".lf-sug-accept")).to_be_visible()
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    # And the page's own count is derived from that, so it comes back too.
    expect_accept_all(page, 3)
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("Couldn't take this")
    )
    assert actions(serve.page_dir) == []

    page.unroute("**/api/event")
    item.locator(".lf-sug-accept").click()
    round_trip(page)
    logged = actions(serve.page_dir)
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in logged
    ] == [("sug-refill", "accept")]
    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    consume_browser_errors(page, http_error_console(400))


def test_an_ambiguous_decision_stays_one_gesture_while_retrying(browser, serve):
    """Losing an accepted action answer retries that exact attempt, and the decided
    face offers no second Accept that could mint a decision one undo would merely
    uncover."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
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
    accept = page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept")
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()

    expect(accept).to_have_count(0)
    expect(
        page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-reject")
    ).to_have_count(0)
    holding(page, requests, 2, "the retried decision")
    assert accepted == [200]
    assert len(requests) == 2
    assert len({request["attempt"] for request in requests}) == 1
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in actions(serve.page_dir)
    ] == [("sug-refill", "accept")]

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()


def test_an_optimistic_decision_stays_plain_while_delivery_waits(held_events, serve):
    """A held send leaves the settled content legible and its Undo in place. One press
    replaces both verdicts and records the accepted decision once."""
    browser, held = held_events
    page = open_page(browser, serve(SUGGESTION_PAGE))
    row = page.locator("[data-lf-margin-for='sug-refill']")
    accept = row.locator(".lf-sug-accept")
    resting = accept.bounding_box()
    accept.click()
    holding(page, held, 1, "the accepted suggestion")
    expect(row.locator(".lf-sug-accept")).to_have_count(0)
    expect(row.locator(".lf-sug-reject")).to_have_count(0)
    assert len(held) == 1

    suggestion = page.locator("#sug-refill")
    expect(suggestion.locator("lf-old")).to_be_hidden()
    expect(suggestion.locator("lf-new")).to_be_visible()
    expect(suggestion).not_to_have_attribute("aria-busy", "true")
    expect(suggestion).to_have_css("opacity", "1")
    pending_undo = page.locator("[data-lf-margin-for='sug-refill']").get_by_role(
        "button", name=re.compile(r"^Undo accepting")
    )
    assert pending_undo.bounding_box() == resting
    expect(pending_undo).to_be_enabled()
    expect(pending_undo).not_to_have_attribute("aria-busy", "true")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    assert [
        (e["widget"], e["detail"].get("outcome", e["action"]))
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("sug-refill", "accept")]
