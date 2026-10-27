"""How the log and a new version's markup combine: restated widgets, user overrides,
what the diff marks, and the decision a thread follows."""

import re

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import (
    _CARD,
    DRAFT_EDITED,
    JOURNEY_V1,
    JOURNEY_V2,
    SUGGEST_BLOCK,
    _card_done,
    _draft_says,
    _publish,
    actions,
)
from render_harness import (
    RELEASE_FOCUS,
    compare_with,
    draft_control,
    leaf_page,
    open_page,
    open_threads,
    panel_menu,
    panel_settled,
    panel_view,
    round_trip,
    show_resolved,
    stamp_page,
    told,
    undo,
    wait_for_check_api,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


DRAG_HELD = "async () => (await window.__lfCheckApi()).dragHeld()"


def expect_resolved(page, thread_id, resolved=True):
    """Read whether the panel's Threads lists the thread `thread_id` under Resolved,
    rather than among the open threads."""
    open_threads(page)
    row = f"{panel_view('threads')} .lf-fp-thread[data-key='{thread_id}']"
    if resolved:
        show_resolved(page)
        expect(page.locator(f"{row}[data-resolved]")).to_have_count(1)
    else:
        expect(page.locator(f"{row}:not([data-resolved])")).to_have_count(1)


def test_restating_a_widget_is_how_a_version_takes_the_pen_back(browser, serve):
    """The other end of the rule that the log outranks the markup. Since it does, a
    version cannot revise a draft the user has rewritten — replay would paint
    their words straight back over it, and Claude's correction would reach nobody.
    `restated` is the one way markup wins: it retracts what came before it, so
    the new words render and the user sees the widget identified as one whose
    decision this version undid.

    It costs a word, where losing a decision used to cost nothing, which is the
    whole asymmetry: the failure that stays silent is now the one that needs
    saying out loud."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": DRAFT_EDITED},
        },
    )
    corrected = "Run the migration after deploying — it needs the new column."
    _publish(
        d,
        2,
        _draft_says(JOURNEY_V2, corrected, " restated"),
        "0041 needs the column; rewrote the draft",
    )

    page = open_page(browser, url.replace("v1.html", "v2.html"))
    body = page.locator("#draft-ops .lf-draft-body")
    expect(body).to_have_text(corrected)
    # And the user is told, rather than left to notice: their edit is gone, which
    # without a reading looks exactly like a draft they never touched. The draft's
    # existing controls keep their compact form; Page Map states the provenance,
    # and the target keeps the local quiet word.
    expect(page.locator("#draft-ops[data-lf-restated]")).to_have_count(1)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    rewritten = page.get_by_role(
        "button", name=re.compile(r"^Open rewritten: Rewritten")
    )
    expect(rewritten).to_be_visible()
    page.keyboard.press("Escape")
    assert (
        page.locator("#draft-ops").evaluate("el => getComputedStyle(el).outlineStyle")
        == "none"
    )
    assert "rewritten since the decision" in page.locator("#draft-ops").aria_snapshot()


def test_user_overrides_identify_state_that_differs_from_authored_inputs(
    browser, serve
):
    """Moves and edits retain their user origin across unrelated revisions.
    Incorporating that state into source clears the override reading, and the
    diff stays quiet about the user's own move."""
    page = open_page(browser, live_url(serve(JOURNEY_V1)))

    # A real drag — the pointer path, where the gesture gate and the poll meet.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    expect(page.locator("#card-x[data-lf-user-override]")).to_have_count(1)

    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), DRAFT_EDITED)
    draft_control(page, "save", "draft-ops").click()
    expect(page.locator("#draft-ops[data-lf-user-override]")).to_have_count(1)

    # Both actions must be in the log before the next version publishes, and the
    # page is what says so: it sent them, and counts what has come back.
    d = serve.page_dir
    round_trip(page)

    _publish(d, 2, JOURNEY_V2, "revise unrelated prose")
    wait_for_revision(page, 2)
    expect(page.locator("#card-x[data-lf-user-override]")).to_have_count(1)
    expect(page.locator("#draft-ops[data-lf-user-override]")).to_have_count(1)

    _publish(
        d,
        3,
        _card_done(_draft_says(JOURNEY_V2, DRAFT_EDITED)),
        "honors the move and the edit",
    )
    wait_for_revision(page, 3)
    page.wait_for_function(
        "() => document.querySelector('.lf-floating-panel') !== null"
    )
    wait_until_ready(page)
    expect(page.locator("[data-lf-user-override]")).to_have_count(0)

    # The diff's state half is quiet about the honored move: base state is the
    # base markup plus the fold as of it, which already has the card in Done.
    compare_with(page)
    # Versions says the comparison is on by its Compare standing pressed.
    expect(
        panel_menu(page, "versions").locator('.lf-fp-compare[aria-pressed="true"]')
    ).to_have_count(1)
    page.locator(".lf-fp-leaf").click()
    assert not page.evaluate(
        "document.getElementById('card-x').classList.contains('lf-ins-block')"
    ), "the user's own honored drag marked as a change"


def test_foreign_state_draws_beside_a_live_drag(browser, serve):
    """A poll may finish while Sortable owns the dragged card. The board's gesture holds
    only the board's drawing (`defer`); another widget draws the foreign edit at once,
    even one above the board that grows, and the card still lands where it is dropped."""
    draft = JOURNEY_V1.index('<lf-draft id="draft-ops">')
    draft_end = JOURNEY_V1.index("</lf-draft>", draft) + len("</lf-draft>")
    board = JOURNEY_V1.index('<lf-board id="board">')
    html = (
        JOURNEY_V1[:board]
        + JOURNEY_V1[draft:draft_end]
        + "\n"
        + JOURNEY_V1[board:draft]
        + JOURNEY_V1[draft_end:]
    )
    page = open_page(browser, serve(html))
    grip = page.locator("#card-x .lf-grip").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    done = page.locator("#col-done").bounding_box()
    page.mouse.move(
        done["x"] + done["width"] / 2, done["y"] + done["height"] / 2, steps=8
    )
    wait_for_check_api(page, "(api) => api.dragHeld()")
    before = page.locator("#draft-ops").bounding_box()["height"]

    foreign = "\n\n".join(
        f"Foreign paragraph {n} held beside the drag." for n in range(6)
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": foreign},
        },
    )
    told(page)
    expect(page.locator("#draft-ops .lf-draft-body")).to_contain_text(
        "Foreign paragraph 5"
    )
    assert page.evaluate(DRAG_HELD), "the foreign edit ended the drag"
    assert page.locator("#draft-ops").bounding_box()["height"] > before + 50, (
        "the draft above the board did not grow, so nothing moved under the drag"
    )

    page.mouse.up()
    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    moves = [e for e in actions(serve.page_dir) if e["action"] == "move"]
    assert [(m["detail"]["unit"], m["detail"]["value"]) for m in moves] == [
        ("card-x", "col-done")
    ]


def test_the_diff_marks_a_card_the_author_relocated(browser, serve):
    """A pure state change has no text of its own, so the content diff was blind
    to it: a card in a new column read as nothing changed. The state half
    compares declared state, so the author moving a card between versions —
    with no user action behind it — marks the card itself. The card alone:
    an id'd element nested inside it rode along rather than changing columns,
    and marking it too would double-tint one move."""
    noted = _CARD.replace(
        "</lf-card>", '<p id="card-x-note">A nested aside.</p></lf-card>'
    )
    v1 = JOURNEY_V1.replace(_CARD, noted)
    url = serve(v1)
    d = serve.page_dir
    _publish(
        d, 2, _card_done(JOURNEY_V1).replace(_CARD, noted), "moved the card to Done"
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    page.wait_for_function(
        "() => document.getElementById('card-x').classList.contains('lf-ins-block')"
    )
    assert not page.evaluate(
        "document.getElementById('card-x-note').classList.contains('lf-ins-block')"
    ), "the card's passenger marked as its own move"


SCRIPT_WORDS = leaf_page(
    "Script words",
    """
<h1 id="title">Script words</h1>
<p id="readout">Counting…</p>
<section id="tally"><p id="tally-note">The script appends a paragraph here.</p></section>
<div id="listed"></div>
<p id="glossed">Plain words around a <lf-gloss id="term" tip="A term.">term</lf-gloss>.</p>
<p id="cloned">Words a script copies.</p>
<p id="outro">The last authored paragraph.</p>
""",
    head="""<script type="module">
import { html, render } from "/runtime/widget-api.js";
document.getElementById("readout").textContent = "42 items counted by the script.";
const cloned = document.getElementById("cloned");
const copy = cloned.cloneNode(true);
copy.className = "copied";
cloned.replaceWith(copy);
const added = document.createElement("p");
added.textContent = "A paragraph the script appended.";
document.getElementById("tally").append(added);
render(html`<ul><li>Item alpha</li><li>Item beta</li></ul>`,
  document.getElementById("listed"));
</script>""",
)


def test_the_diff_marks_what_the_author_changed_and_no_word_a_script_wrote(
    browser, serve
):
    """A plain page script writes words into the page without marking them: a
    readout's `textContent`, a paragraph it appends, a list lit-html renders. None of
    them is in either version's source, so the arriving version tints only the blocks
    the author changed, and comparing versions marks only those, on the version that
    arrived live and on a fresh load of it.

    The author rewrote the readout's placeholder too, so it is marked. On the fresh
    load the words it shows are the script's, so it offers no inline diff, which would
    paint the source's words over the script's, while the rewritten closing paragraph
    offers one. A paragraph holding a gloss is one block, so rewording the words around
    the gloss marks it; a paragraph the script swapped for a copy is found by its id."""
    url = live_url(serve(SCRIPT_WORDS))
    page = open_page(browser, url)
    stamp_page(
        serve.page_dir,
        SCRIPT_WORDS.replace("Counting…", "Tallying…")
        .replace("The last authored paragraph.", "The closing authored paragraph.")
        .replace("Plain words around", "Reworded words around")
        .replace("Words a script copies.", "Reworded words a script copies."),
        "reworded four paragraphs",
    )
    wait_for_revision(page, 2)
    # The revision lands with the arrival tint on the blocks it changed, and only those.
    tinted = page.wait_for_function(
        """() => {
          const tinted = [...document.querySelectorAll("main *")]
            .filter((node) => node.getAnimations().length)
            .map((node) => node.id || node.localName);
          return tinted.length ? tinted : null;
        }"""
    ).json_value()
    assert tinted == ["readout", "glossed", "cloned", "outro"]
    fresh = open_page(browser, url)
    for shown in (page, fresh):
        compare_with(shown, 1)
        marked = shown.locator("main .lf-ins-block")
        expect(marked).to_have_count(4)
        assert marked.evaluate_all("blocks => blocks.map(b => b.id)") == [
            "readout",
            "glossed",
            "cloned",
            "outro",
        ]

    def change(block):
        return fresh.locator(
            f'[data-lf-margin-for="{block}"] [data-lf-kinds~="change"]'
        )

    expect(fresh.locator("#readout")).to_have_text("42 items counted by the script.")
    expect(change("outro")).to_have_attribute("aria-expanded", "false")
    expect(change("readout")).not_to_have_attribute("aria-expanded", re.compile(".*"))


KEPT_BOARD = leaf_page(
    "Kept board",
    """
<h1 id="title">Kept board</h1>
<lf-board id="board">
  <lf-column id="col-todo" label="To do">
    <lf-card id="card-x"><strong>Review</strong> Old words.</lf-card>
    <lf-card id="card-y"><strong>Ship</strong> Steady words.</lf-card>
  </lf-column>
</lf-board>
<p id="note">First note.</p>
""",
)


def test_a_change_inside_a_widget_a_later_revision_kept_marks_its_block(browser, serve):
    """Live revisions keep a widget the author left alone, controller and all. Its
    blocks still stand for their live nodes afterwards, so a comparison reaching back
    past that revision marks the card the author rewrote, not the whole board."""
    url = live_url(serve(KEPT_BOARD))
    page = open_page(browser, url)
    second = KEPT_BOARD.replace("Old words.", "New words.")
    stamp_page(serve.page_dir, second, "rewrote a card")
    wait_for_revision(page, 2)
    stamp_page(serve.page_dir, second.replace("First note.", "Second note."), "a note")
    wait_for_revision(page, 3)
    compare_with(page, 1)
    marked = page.locator("main .lf-ins-block")
    expect(marked).to_have_count(2)
    assert marked.evaluate_all("blocks => blocks.map(b => b.id)") == [
        "card-x",
        "note",
    ]


def test_a_comparison_reads_nothing_from_a_server_running_another_runtime(
    browser, serve
):
    """A comparison asks the server for the older version's reading. Right after a
    restart under another Leaf, that server's runtime is not this tab's, and its state
    is not this tab's code to read, so the comparison refuses it rather than mark the
    page with it: the comparison fails, and the tab asks its source whether to reload,
    as for any refused answer.

    Only the comparison's answer names another runtime here, so the tab's other reads
    are admitted and may take down the wait the refusal raised; the failed comparison
    stands in the Errors list either way."""
    url = serve(JOURNEY_V1)
    _publish(serve.page_dir, 2, _card_done(JOURNEY_V1), "moved the card to Done")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    asked = []

    def another_runtime(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            headers={**response.headers, "Leaf-Runtime": "0123456789abcdef"},
        )

    def source(route):
        asked.append(route.request.url)
        route.continue_()

    page.route("**/api/view*", another_runtime)
    page.route("**/registry.json", source)
    compare_with(page)
    # Compare starts an asynchronous read. Wait for its refusal before opening the
    # menu, whose rows deliberately stay as they were when it opened.
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "placeholder", re.compile("Couldn't load v1")
    )
    menu = panel_menu(page)
    menu.locator('.lf-fp-item[data-row="errors"]').click()
    expect(
        menu.locator(".lf-fp-error-words b").filter(has_text="Couldn't load v1")
    ).to_have_count(1)
    expect(page.locator("main .lf-ins-block")).to_have_count(0)
    assert asked, "the refused reading asked no source whether it moved"


def test_the_diff_marks_the_card_the_author_reordered_and_no_other(browser, serve):
    """A card moved within its column changes no words and no column, and the state
    half still marks it. Only the card whose move explains the new order is marked:
    the cards it passed kept their order among themselves."""
    cards = {
        name: f'<lf-card id="card-{name}"><strong>{name.title()}</strong></lf-card>'
        for name in ("y", "z")
    }
    v1 = JOURNEY_V1.replace(_CARD, _CARD + cards["y"] + cards["z"])
    url = serve(v1)
    _publish(
        serve.page_dir,
        2,
        JOURNEY_V1.replace(_CARD, cards["y"] + cards["z"] + _CARD),
        "moved card x to the end",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    page.wait_for_function(
        "() => document.getElementById('card-x').classList.contains('lf-ins-block')"
    )
    assert (
        page.evaluate(
            "['card-y', 'card-z'].filter(id =>"
            " document.getElementById(id).classList.contains('lf-ins-block'))"
        )
        == []
    )


def test_accepting_a_suggestion_resolves_its_thread_in_one_event(browser, serve):
    """Accepting answers the thread the change was written for, and the answer
    rides the accept itself — the wrapper holding the `resolves` mapping is
    retired by the honoring version, and a second POST could fail alone, leaving
    the outcome and the resolution disagreeing with no repair path. One event,
    read by both thread builders."""
    url = serve(
        JOURNEY_V1.replace('<h2 id="notes">', SUGGEST_BLOCK + '<h2 id="notes">'),
        events=(
            {
                "kind": "comment",
                "id": "c1",
                "author": "user",
                "revision": 1,
                "text": "does this take downtime?",
            },
        ),
    )
    d = serve.page_dir
    page = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Accept the suggested change")).click()
    expect_resolved(page, "c1")
    events = events_model.read_events(d)
    accept = next(e for e in events if e.get("kind") == "action")
    assert accept["action"] == "decide" and accept["detail"] == {"outcome": "accept"}
    assert accept["meaning"]["answer"] == "c1"
    assert not any(e.get("kind") == "resolve" for e in events)


def test_the_thread_follows_the_decision_that_still_stands(browser, serve):
    """The panel reports where the question currently stands, not that it was once
    answered. A second tab can reject a suggestion the first has already accepted —
    the controls are gone in the tab that decided, not in the one that hasn't
    polled — and the user who turned the fix down would otherwise find their
    question filed away as answered by it, while the suggestion beside it read as
    rejected. Both readings come off the same log; here is where they have to
    agree in front of the user.

    Then the same rule read the other way: `z` takes the reject back, the accept it
    superseded is the widget's answer once more, and the thread closes under it. The
    two ways an answer stops being in force compose, and nothing is written down to say so:
    an `unresolve` posted where the thread reopened would be a second record of the
    same fact, and taking the reject back would leave it in force against the accept."""
    url = serve(
        JOURNEY_V1.replace('<h2 id="notes">', SUGGEST_BLOCK + '<h2 id="notes">'),
        events=(
            {
                "kind": "comment",
                "id": "c1",
                "author": "user",
                "revision": 1,
                "text": "does this take downtime?",
            },
        ),
    )
    d = serve.page_dir
    page = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Accept the suggested change")).click()
    expect_resolved(page, "c1")

    # What the other tab's press leaves in the log, made against the same version:
    # its own accept and reject controls are still shown, because it has not
    # heard about this one's decision yet.
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-fix",
            "action": "decide",
            "detail": {"outcome": "reject"},
        },
    )
    told(page)
    expect(page.locator("#sug-fix")).to_have_attribute("data-lf-state", "reject")
    # Threads was already open: incoming news keeps its rows in place until the
    # reader asks to settle them. The row's reading changes before its section does.
    row = page.locator(f"{panel_view('threads')} .lf-fp-thread[data-key='c1']")
    expect(row).not_to_have_attribute("data-resolved", "")
    notice = page.locator(".lf-fp-joined .lf-thread-news")
    expect(notice).to_have_attribute("title", "1 thread reopened")
    notice.click()
    expect_resolved(page, "c1", resolved=False)
    open_panel_thread(page, "c1")
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Resolve thread")

    # Offered here because the log says the user made the reject; which tab they
    # were in is not something the log records, and not something a withdrawal
    # could turn on. The widget goes back to the markup and the surviving log is
    # replayed onto it, so what the press restores is the accept, not a blank slate.
    page.evaluate(RELEASE_FOCUS)
    undo(page)
    expect(page.locator("#sug-fix")).to_have_attribute("data-lf-state", "accept")
    # The open thread says it is resolved, and Threads lists it under Resolved.
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Reopen")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect_resolved(page, "c1")
    # What the log holds is the three gestures and not one word about the thread:
    # it was reopened and closed again by that log being read.
    assert [
        e["detail"]["outcome"] if e["kind"] == "action" else e["kind"]
        for e in events_model.read_events(d)
        if e["kind"] in ("action", "undo", "resolve", "unresolve")
    ] == ["accept", "reject", "undo"]
