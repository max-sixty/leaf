"""On me in the floating panel: the cards that name each open and answered obligation, their
identity and order, and what an answered one says."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_OBLIGATIONS_IN_ORDER,
    CHANGE_SHAPES_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    OBLIGATIONS_PAGE,
    ON_ITEM_SAYS,
    panel_comment,
)
from render_harness import (
    PANEL,
    expect_obligations_answered,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    post_event,
    resized,
    round_trip,
    sending,
    told,
    undo,
)

from browser.navigation import expect_walk_position
from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

ON_ME = panel_view("queue")


def open_on_me(page):
    """Open On me by its mark, unless it stands open, and return its view."""
    if page.locator(PANEL).get_attribute("data-open") != "queue":
        page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    return page.locator(ON_ME)


def on_card(page, at):
    """The On me card for the obligation `at` names, such as `widget:sug-refill`."""
    return page.locator(f'{ON_ME} .lf-fp-on-item[data-key=\'["widget","{at}"]\']')


def test_on_me_lists_open_and_answered_obligations(browser, serve):
    """The panel's On me mark lists every open obligation under On me, in document order, and
    every answered one under Done with its current answer, so the user can review and
    revise. A twelfth widget joins by declaring x-awaits.

    A closed view holds no cards at all: they are the open view's rendering, the mark's
    count is the closed view's, and a hidden list of buttons is a set of controls no
    user can press — which the press sweep sees as the page's control set changing
    under it."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))
    resized(page, 1920, 900)
    assert page.evaluate(ON_ITEM_SAYS) == [], "a closed view holds no cards"

    page.locator(".lf-fp-on-user").focus()
    page.keyboard.press("Enter")
    panel_settled(page, view="queue")
    cards = page.evaluate(ON_ITEM_SAYS)
    assert [(c["id"], c["list"]) for c in cards] == [
        *(
            (at, "you")
            for at in [
                "widget:live-question",
                "widget:sug-refill",
                "widget:t-baffles-review",
                "widget:t-bath-choice",
            ]
        ),
        ("widget:honored", "done"),
    ]
    for card in cards:
        assert card["kind"] == "widget", card
        if card["list"] == "you":
            assert card["w"] > 100 and card["h"] > 20, (
                f"{card['id']}'s card has no size"
            )

    # The obligation leads with its authored heading rather than the first option's answer.
    said = {c["id"]: c for c in cards}
    assert said["widget:live-question"]["prompt"].startswith(
        "Where should sessions live?"
    ), said
    assert said["widget:t-baffles-review"]["prompt"].startswith(
        "Are the baffles ready?"
    ), said
    assert said["widget:honored"]["said"].startswith("Answered: Two-tier gates"), said

    # Answered on the page, and the card moves to Done as the route back, saying its
    # current answer. The press on the page puts the view away; it opens on the same.
    page.locator("main #lq-token").click()
    expect_obligations_answered(page, "2/5")
    open_on_me(page)
    expect(page.locator(f"{ON_ME} .lf-fp-on-item")).to_have_count(5)
    answered = {c["id"]: c for c in page.evaluate(ON_ITEM_SAYS)}
    assert answered["widget:live-question"]["list"] == "done", answered
    assert answered["widget:live-question"]["said"].startswith(
        "Answered: Signed tokens"
    ), answered

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    open_on_me(page)
    suggestion = next(
        c for c in page.evaluate(ON_ITEM_SAYS) if c["id"] == "widget:sug-refill"
    )
    assert suggestion["list"] == "done", suggestion
    assert suggestion["said"].startswith("Answered: Accepted"), suggestion

    # And closing takes the rest with it, for the reason the docstring gives.
    page.locator(".lf-fp-on-user").focus()
    page.keyboard.press("Enter")
    panel_settled(page, open=False)
    assert page.evaluate(ON_ITEM_SAYS) == [], "a closed view keeps its cards"


def test_an_answered_obligations_words_are_its_widgets_semantic_state(browser, serve):
    """Each family names its answer from the state it was answered with.

    A draft says its current words, a playground the instruction it sent rather than
    whatever its controls show now, and an option the user added is named by the
    rendered words its `add` carried. A `multiple` group answered by Done with no pick
    of the user's names its authored choice."""
    url = serve(
        leaf_page(
            "answer words",
            """
<h1 id="h">Answers</h1>
<lf-ask id="note-ask"><h2>Is this release note right?</h2>
<lf-draft id="note" needed><pre>
Adds --dry-run to every mutating command.
</pre></lf-draft></lf-ask>
<lf-ask id="cache-ask"><h2>Which cache?</h2>
<lf-options id="cache" choose>
  <lf-option id="cache-none"><strong>No cache</strong> Read through.</lf-option>
</lf-options></lf-ask>
<lf-ask id="tags-ask"><h2>Which tags?</h2>
<lf-options id="tags" choose multiple>
  <lf-option id="tag-alpha" chosen><strong>Alpha</strong></lf-option>
  <lf-option id="tag-beta"><strong>Beta</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="tone-ask"><h2>Which notification?</h2>
<lf-playground id="tone">
  <lf-playground-control name="format" label="Format" kind="choice" value="banner">
    <lf-playground-choice value="banner" label="Banner"></lf-playground-choice>
    <lf-playground-choice value="strip" label="Strip"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview><p id="tone-preview">The notification.</p></lf-playground-preview>
  <lf-playground-output>Build the <lf-playground-value for="format"></lf-playground-value>
  notification.</lf-playground-output>
</lf-playground></lf-ask>
""",
        )
    )
    page = open_page(browser, url)
    door = url.rsplit("/versions/", 1)[0] + "/api/event"
    for widget, action, detail in [
        ("note", "edit", {"value": "Adds --dry-run to every command."}),
        ("cache", "add", {"option": "cache-redis", "text": "**Redis** in front"}),
        ("cache", "choose", {"value": ["cache-redis"]}),
        ("tags", "answer", {}),
        (
            "tone",
            "choose",
            {"values": {"format": "strip"}, "instruction": "Build the strip one."},
        ),
    ]:
        posted = post_event(
            page,
            door,
            data={
                "kind": "action",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
        assert posted.ok, posted.text()
    expect_obligations_answered(page, "4/4")
    output = page.locator("#tone lf-playground-output")
    expect(output).to_contain_text("strip")
    page.locator("#tone").get_by_role("radio", name="Banner").click()
    expect(output).to_contain_text("banner")
    open_on_me(page)
    answers = {
        "widget:note": "Adds --dry-run to every command.",
        "widget:cache": "Redis in front",
        "widget:tags": "Alpha",
        "widget:tone": "Build the strip one.",
    }
    for at, words in answers.items():
        expect(on_card(page, at).locator(".lf-fp-said")).to_contain_text(
            f"Answered: {words}"
        )


def test_obligation_cards_keep_identity_and_walk_order_when_the_live_dom_moves(
    browser, serve
):
    """A keyed card keeps its node and focus however the page's DOM moves, and stands
    where the `m` walk reaches its item: an item whose element leaves the page goes
    after those still on it, as the walk takes it last."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))
    open_on_me(page)
    cards = page.locator(f"{ON_ME} .lf-fp-on-item")
    expect(cards).to_have_count(len(ALL_OBLIGATIONS_IN_ORDER))
    order = [
        '["widget","widget:live-question"]',
        '["widget","widget:sug-refill"]',
        '["widget","widget:t-baffles-review"]',
        '["widget","widget:t-bath-choice"]',
        '["widget","widget:honored"]',
    ]

    page.evaluate(
        """async () => {
          const {readApplicationPresentation, presentDocument} =
            await window.__lfCheckApi();
          window.__lfReadObligationPresentation = readApplicationPresentation;
          window.__lfPresentDocument = presentDocument;
          const cards = [...document.querySelectorAll(
            '.lf-fp-view[data-view="queue"] .lf-fp-on-item')];
          window.__lfObligationCards = new Map(cards.map(card => [card.dataset.key, card]));
          const honored = document.querySelector('#honored-decision');
          document.querySelector('#live-question-decision').before(honored);
          window.__lfObligationCards.get('["widget","widget:sug-refill"]').focus();
          await presentDocument();
        }"""
    )
    page.wait_for_function("__lfReadObligationPresentation().pending.length === 0")
    assert cards.evaluate_all("items => items.map(item => item.dataset.key)") == order
    assert cards.evaluate_all(
        "items => items.every(item => window.__lfObligationCards.get(item.dataset.key) === item)"
    )
    sug_refill = on_card(page, "widget:sug-refill")
    expect(sug_refill).to_be_focused()

    # Removing a presentation node does not rewrite the application inventory: the
    # keyed card stays, focus with it, and takes the walk's place for an item with no
    # place on the page, after the rest of the list.
    page.evaluate(
        """async () => {
          document.querySelector('#sug-refill').remove();
          await window.__lfPresentDocument();
        }"""
    )
    page.wait_for_function("__lfReadObligationPresentation().pending.length === 0")
    assert cards.evaluate_all("items => items.map(item => item.dataset.key)") == [
        order[0],
        order[2],
        order[3],
        order[1],
        order[4],
    ]
    expect(sug_refill).to_be_focused()
    assert cards.evaluate_all(
        "items => items.every(item => window.__lfObligationCards.get(item.dataset.key) === item)"
    )


def test_a_completed_obligation_persists_and_on_me_says_its_current_answer(
    browser, serve
):
    """Completion survives a reload, and On me, opened from the keyboard, keeps the
    answered obligation under Done saying its current answer, which follows a revision."""
    page = open_page(browser, serve(OBLIGATION_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    expect_obligations_answered(page, "0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect_obligations_answered(page, "1/1")

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_obligations_answered(page, "1/1")

    # With nothing on the user, the view opens on an empty list with Done under it; ↓
    # enters the first card there, the obligation's.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("ArrowDown")
    card = on_card(page, "widget:storage-options")
    expect(card).to_be_focused()
    expect(card).to_have_attribute("data-list", "done")
    expect(card.locator(".lf-fp-said")).to_contain_text(
        "Answered: Pause offline editing"
    )

    page.locator("main #storage-evict").click()
    round_trip(page)
    expect(page.locator("main #storage-evict")).to_have_attribute("chosen", "")
    expect_obligations_answered(page, "1/1")
    open_on_me(page)
    expect(card.locator(".lf-fp-said")).to_contain_text(
        "Answered: Drop the oldest documents"
    )


def test_an_answered_boxless_obligation_is_taken_back_from_its_card(browser, serve):
    """An accepted deletion leaves no box on the page to arrive at, so On me's Done card
    is where the user takes the decision back: it says what was decided, and its Undo
    restores the change to decide again."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    expect_obligations_answered(page, "0/4")

    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect_obligations_answered(page, "1/4")

    open_on_me(page)
    card = on_card(page, "widget:sug-delete")
    expect(card).to_have_attribute("data-list", "done")
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered: Accepted")
    card.get_by_role("button", name="Undo").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect_obligations_answered(page, "0/4")


def test_on_me_s_tabs_stand_where_a_view_names_itself(browser, serve):
    """On me's tabs name its view, so they start its controls, where another view's way
    back stands, rather than standing among the presses at their end; no name bar
    stands over the view, the heading naming it to assistive tech alone."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))
    resized(page, 1440, 900)
    open_on_me(page)
    start, tabs = page.locator(".lf-fp-controls").evaluate(
        """c => [c.getBoundingClientRect().left
            + parseFloat(getComputedStyle(c).paddingLeft),
          c.querySelector('.lf-fp-filters').getBoundingClientRect().left]"""
    )
    assert tabs == start, (tabs, start)
    assert page.locator(".lf-fp-head").bounding_box()["height"] == 0


def test_each_on_me_card_names_its_kind_as_the_walk_does(browser, serve):
    """Each card in On me says what its item is, in the word the field says after `m`:
    a suggestion is an Insertion, a Deletion or a Rewrite by its shape, and a widget's
    question its widget's word. The word stays once the card is answered."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 1440, 900)
    open_on_me(page)
    kinds = {
        "sug-rewrite": "Rewrite",
        "sug-insert": "Insertion",
        "sug-delete": "Deletion",
        "shapes-q": "Options",
    }
    for at, word in kinds.items():
        expect(on_card(page, f"widget:{at}").locator(".lf-fp-on-kind")).to_have_text(
            word
        )
    card = on_card(page, "widget:sug-insert")
    card.get_by_role("button", name="Accept").click()
    round_trip(page)
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered: Accepted")
    expect(card.locator(".lf-fp-on-kind")).to_have_text("Insertion")


def test_show_on_a_card_goes_where_m_arrives_and_only_where_that_is_elsewhere(
    browser, serve
):
    """Every On me card whose item has somewhere to go offers Show, a question answered
    on its card included, and Show puts the user where `m` puts them."""
    url = serve(CHANGE_SHAPES_PAGE)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    # Where `m` arrives at the question: the fourth stop in page order.
    page.locator("#title").click()
    for _ in range(4):
        page.keyboard.press("m")
    expect_walk_position(page, "4 of 4 waiting on me · Options")
    landed = page.evaluate("() => document.activeElement.id")
    page.locator("#title").click()

    open_on_me(page)

    def show(card):
        return card.get_by_role("button", name="Show", exact=True)

    for at in ("sug-rewrite", "sug-insert", "sug-delete", "shapes-q"):
        expect(show(on_card(page, f"widget:{at}"))).to_have_count(1)

    show(on_card(page, "widget:shapes-q")).click()
    expect(page.locator(f"#{landed}")).to_be_focused()


WALKED_PAGE = leaf_page(
    "many asks",
    '<h1 id="title">Kit list</h1>'
    + "".join(
        f'<lf-ask id="ask-{n}"><h2>Bring item {n}?</h2>'
        f'<lf-options id="pick-{n}" choose><lf-option id="yes-{n}">Yes</lf-option>'
        f'<lf-option id="no-{n}">No</lf-option></lf-options></lf-ask>'
        for n in range(1, 9)
    ),
)


def test_the_m_walk_brings_its_card_into_on_me_s_view_and_rings_it(browser, serve):
    """While On me is open, `m` and Shift+`m` bring the card of the item they reach into
    the list's view, scrolling it either way, and that card alone wears a focused
    card's ring, while focus stands at the item on the page."""
    page = open_page(browser, serve(WALKED_PAGE))
    resized(page, 1000, 560)
    view = open_on_me(page)
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(8)
    assert view.evaluate("view => view.scrollHeight > view.clientHeight + 40")

    def shown(card):
        return card.evaluate(
            """(card) => {
              const box = card.getBoundingClientRect();
              const view = card.closest('.lf-fp-view').getBoundingClientRect();
              return box.top >= view.top - 1 && box.bottom <= view.bottom + 1;
            }"""
        )

    last = on_card(page, "widget:pick-8")
    assert not shown(last)
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "8 of 8 waiting on me · Options")
    expect(page.locator("#ask-8")).to_be_focused()
    expect(view.locator(".lf-fp-on-item[data-walked]")).to_have_count(1)
    expect(last).to_have_attribute("data-walked", "")
    assert last.evaluate("card => getComputedStyle(card).outlineStyle") == "solid"
    assert shown(last)

    first = on_card(page, "widget:pick-1")
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 8 waiting on me · Options")
    expect(first).to_have_attribute("data-walked", "")
    expect(last).not_to_have_attribute("data-walked", "")
    assert shown(first)


ORDERED_PAGE = leaf_page(
    "walk order",
    '<h1 id="title">Release</h1><p id="cadence">We publish a build every week.</p>'
    '<lf-ask id="channel-ask"><h2>Which channel first?</h2>'
    '<lf-options id="channel" choose><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-ask>'
    '<p id="notes">Release notes come from merged titles.</p>',
)


def test_on_me_lists_its_cards_in_the_order_m_walks_them(browser, serve):
    """On me lists its cards in the order `m` reaches their items, by where each is on
    the page, rather than the server's order, which puts what the page asks before
    to-dos. So successive presses of `m` outline successive cards."""
    url = serve(ORDERED_PAGE)
    for subject, title in (
        ("cadence", "Check the cadence"),
        ("notes", "Check the notes"),
    ):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "todo",
                "author": "agent",
                "agent": "Agent",
                "session": "walk-order",
                "owner": "user",
                "subject": {"kind": "element", "id": subject},
                "title": title,
            },
        )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    view = open_on_me(page)
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(3)
    expect(cards.locator(".lf-fp-on-kind")).to_have_text(["To-do", "Options", "To-do"])
    expect(cards.nth(0)).to_contain_text("Check the cadence")
    expect(cards.nth(2)).to_contain_text("Check the notes")

    def walked():
        expect(view.locator(".lf-fp-on-item[data-walked]")).to_have_count(1)
        return cards.evaluate_all(
            "cards => cards.findIndex((card) => card.hasAttribute('data-walked'))"
        )

    page.keyboard.press("m")
    first = walked()
    for step in (1, 2, 3):
        page.keyboard.press("m")
        expect(cards.nth((first + step) % 3)).to_have_attribute("data-walked", "")


def test_an_item_arriving_above_takes_its_walk_place_and_moves_no_card_read(
    browser, serve
):
    """An item that joins On me while it is open takes its place in the walk's order,
    so a to-do arriving at the page's head is the first card as `m` reaches it first.
    The list scrolled to a later card keeps that card where it stood on screen: the
    browser's scroll anchoring holds it as the new card grows the list above."""
    url = serve(WALKED_PAGE)
    page = open_page(browser, url)
    resized(page, 1000, 560)
    view = open_on_me(page)
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(8)
    view.evaluate("view => { view.scrollTop = view.scrollHeight; }")
    read = on_card(page, "widget:pick-7")
    before = read.bounding_box()
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "walk-order",
            "owner": "user",
            "subject": {"kind": "element", "id": "title"},
            "title": "Check the title",
        },
    )
    told(page)
    expect(cards).to_have_count(9)
    expect(cards.first).to_contain_text("Check the title")
    # Scroll anchoring restores the offset to the scroller's subpixel precision.
    after = read.bounding_box()
    assert after["y"] == pytest.approx(before["y"], abs=1), (before, after)


# Design C (prototype): a widget that draws a form for On me's card draws itself there,
# bound to its source's state (runtime obligations/seat.js).
SEATS_PAGE = leaf_page(
    "seats",
    """
<h1 id="h">Seats</h1>
<lf-ask id="store-ask"><h2>What should a full store do?</h2>
<lf-options id="store" choose>
  <lf-option id="store-evict"><strong>Drop the oldest</strong> Editing continues.</lf-option>
  <lf-option id="store-stop"><strong>Pause editing</strong> Nothing leaves.</lf-option>
</lf-options></lf-ask>
<lf-approval id="publish"><h3>Publish this report?</h3><p>To the team.</p></lf-approval>
<lf-ask id="name-ask"><p>What should the release be called?</p></lf-ask>
""",
)
WEEK_REPLY = (
    '<lf-ask id="week-ask"><h3>Which week?</h3><lf-options id="week" choose>'
    '<lf-option id="this-week">This week</lf-option>'
    '<lf-option id="next-week">Next week</lf-option></lf-options></lf-ask>'
)


def last_event(serve):
    event = events_model.read_events(serve.page_dir)[-1]
    return {key: event.get(key) for key in ("kind", "widget", "action", "detail")}


def seat(page, at):
    """The widget On me's card for `at` draws, such as `store`."""
    return on_card(page, f"widget:{at}").locator(f'[data-lf-seat="card"]#{at}')


def test_a_card_draws_its_options_and_answers_them_as_the_page_does(browser, serve):
    """An options card holds the group itself, in its card form, so a press on an
    option there is the widget's own pick: the same admitted action a press on the page
    records, which the page's group then shows. The card's Undo takes it back, and the
    group's own digits work in the card, its own mark taking the press."""
    page = open_page(browser, serve(SEATS_PAGE))
    resized(page, 1280, 900)
    open_on_me(page)
    options = seat(page, "store")
    expect(options.locator("lf-option")).to_have_count(2)
    expect(options.locator("lf-option-control")).to_have_count(2)

    with sending(page, "the pick in the card"):
        options.locator("#store-evict lf-option-control").click()
    assert last_event(serve) == {
        "kind": "action",
        "widget": "store",
        "action": "choose",
        "detail": {"value": ["store-evict"]},
    }
    expect(page.locator("main #store-evict")).to_have_attribute("chosen", "")
    card = on_card(page, "widget:store")
    expect(card).to_have_attribute("data-list", "done")
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered: Drop the oldest")

    with sending(page, "the card's undo"):
        card.get_by_role("button", name="Undo").click()
    assert last_event(serve)["kind"] == "undo"
    expect(page.locator("main #store-evict")).not_to_have_attribute("chosen", "")

    open_on_me(page)
    page.evaluate(
        """() => { window.pressed = [];
          for (const mark of document.querySelectorAll('#store lf-option-control'))
            mark.addEventListener('click', () => pressed.push(
              (mark.closest('.lf-chrome') ? 'card:' : 'page:') + mark.parentElement.id)); }"""
    )
    options.locator("#store-evict lf-option-control").focus()
    with sending(page, "the digit"):
        page.keyboard.press("2")
    assert last_event(serve)["detail"] == {"value": ["store-stop"]}
    assert page.evaluate("pressed") == ["card:store-stop"]
    expect(page.locator("main #store-stop")).to_have_attribute("chosen", "")


def test_an_approval_card_approves_and_the_page_takes_it_back(browser, serve):
    """An approval card holds the request's action alone, the card naming what it asks.
    Approve there records the widget's approval, the page's request says Approved, and
    an undo on the page brings Approve back to the card."""
    page = open_page(browser, serve(SEATS_PAGE))
    resized(page, 1280, 900)
    open_on_me(page)
    approval = seat(page, "publish")
    expect(approval.locator("h3")).to_be_hidden()
    with sending(page, "the approval"):
        approval.get_by_role("button", name="Approve").click()
    assert last_event(serve) == {
        "kind": "action",
        "widget": "publish",
        "action": "approve",
        "detail": {},
    }
    expect(page.locator("main #publish .lf-approval-status")).to_have_text("Approved")
    open_on_me(page)
    expect(approval.get_by_role("button", name="Undo approval")).to_be_visible()

    page.locator("main #publish button").focus()
    undo(page)
    assert last_event(serve)["kind"] == "undo"
    open_on_me(page)
    expect(approval.get_by_role("button", name="Approve")).to_be_visible()
    expect(page.locator("main #publish .lf-approval-status")).to_have_text(
        "Awaiting approval"
    )


def test_a_question_in_words_is_answered_from_its_card(browser, serve):
    """A question answered in words takes its answer in its card: one on the page with
    no thread from a box that starts the thread anchored at it, one an agent asked in a
    thread from that thread's own reply box under the question. Each answer is the
    user's message, and the card says it."""
    url = serve(SEATS_PAGE)
    panel_comment(
        serve.page_dir,
        "Release naming",
        author="agent",
        question="<p>Which codename?</p>",
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    open_on_me(page)

    on_card(page, "widget:name-ask").locator(".lf-fp-seat leaf-text").click()
    page.keyboard.type("Call it Larch")
    with sending(page, "the answer"):
        page.keyboard.press("Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["text"], event["anchor"]) == (
        "comment",
        "Call it Larch",
        {"section": "name-ask"},
    )
    expect(on_card(page, "widget:name-ask").locator(".lf-fp-said")).to_contain_text(
        "Answered: Call it Larch"
    )

    asked = page.locator(f"{ON_ME} .lf-fp-on-item", has_text="Which codename?")
    asked.locator(".lf-fp-asked-reply leaf-text").click()
    page.keyboard.type("Spruce")
    with sending(page, "the reply"):
        page.keyboard.press("Enter")
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["text"]) == (
        "reply",
        "user",
        "Spruce",
    )
    expect(asked.locator(".lf-fp-said")).to_contain_text("Answered: Spruce")


def test_a_card_answers_a_widget_in_an_unopened_thread_message(browser, serve):
    """A widget in a thread message nobody has opened draws itself in its card from the
    message's markup, so the user picks there without opening the thread, and Show then
    opens the thread at the one instance the message holds, showing the pick."""
    url = serve(SEATS_PAGE)
    root = panel_comment(serve.page_dir, "Should the rollout wait?")
    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "Which week suits?", WEEK_REPLY
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    open_on_me(page)
    week = seat(page, "week")
    expect(week.locator("lf-option-control")).to_have_count(2)
    with sending(page, "the pick"):
        week.locator("#next-week lf-option-control").click()
    assert last_event(serve) == {
        "kind": "action",
        "widget": "week",
        "action": "choose",
        "detail": {"value": ["next-week"]},
    }
    card = on_card(page, "widget:week")
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered: Next week")
    card.get_by_role("button", name="Show", exact=True).click()
    panel_settled(page, view="thread")
    expect(page.locator('[id="week"]')).to_have_count(1)
    expect(page.locator(f"{panel_view('thread')} #next-week")).to_have_attribute(
        "chosen", ""
    )


HELD_PAGE_APPROVAL_PENDING = """async () => {
  const {readApplicationPresentation} = await window.__lfCheckApi();
  const request = document.querySelector('main #publish');
  const release = request.controller.defer();
  const sent = request.controller.dispatch(
    {kind: 'action', verb: 'approve', detail: {}, says: 'Approved'});
  const pending = [...readApplicationPresentation().pending];
  await sent.delivery;
  release();
  return pending;
}"""


@pytest.mark.parametrize("card", ["open", "closed"])
def test_a_card_s_widget_leaves_its_source_s_presentation_to_the_source(
    browser, serve, card
):
    """The card's widget presents in a region of its own, so the page's widget keeps
    its own while the card stands and after it goes: a draw the page's widget holds back
    still holds the page's presentation. Sharing the source's region, the card took it
    over, and its departure deleted it, so the page's draws held nothing."""
    page = open_page(browser, serve(SEATS_PAGE))
    resized(page, 1280, 900)
    open_on_me(page)
    expect(seat(page, "publish")).to_have_count(1)
    if card == "closed":
        page.locator(".lf-fp-on-user").click()
        panel_settled(page, open=False)
    assert "widget:publish:render" in page.evaluate(HELD_PAGE_APPROVAL_PENDING)
