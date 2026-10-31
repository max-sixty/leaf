"""On me in the floating panel: the cards that name each open and answered obligation, their
identity, grouping and order, and what an answered one says."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_OBLIGATIONS_IN_ORDER,
    CHANGE_SHAPES_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    OBLIGATIONS_PAGE,
    ON_ITEM_SAYS,
)
from render_harness import (
    PANEL,
    expect_obligations_answered,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    post_event,
    resized,
    round_trip,
    told,
)

from browser.navigation import expect_walk_position, walk_position
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

ON_ME = panel_view("queue")


def open_on_me(page):
    """Open On me by its mark, unless it stands open, and return its view; another
    view standing open is put away first, by the ✕ in the mark's seat."""
    shown = page.locator(PANEL).get_attribute("data-open")
    if shown not in (None, "queue"):
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
    if shown != "queue":
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
    page.locator("#lq-token").click()
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
    page.locator(".lf-fp-close").focus()
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

    page.locator("#storage-evict").click()
    round_trip(page)
    expect(page.locator("#storage-evict")).to_have_attribute("chosen", "")
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
    expect(cards.locator(".lf-fp-prompt")).to_have_text(
        ["Check the cadence", "Which channel first?", "Check the notes"]
    )

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


GROUPED_PAGE = leaf_page(
    "grouped asks",
    '<h1 id="title">Release</h1>'
    '<section><h2 id="impl">Implementation</h2>'
    '<lf-ask id="exit-ask"><h3>Which exit code?</h3>'
    '<lf-options id="exit" choose><lf-option id="e75">75</lf-option>'
    '<lf-option id="e124">124</lf-option></lf-options></lf-ask>'
    '<p id="reap">Reap every process under the sandbox user.</p></section>'
    '<section><h2 id="rollout">Rollout</h2>'
    '<lf-ask id="runner-ask"><h3>Include self-hosted runners?</h3>'
    '<lf-options id="runners" choose><lf-option id="r-yes">Yes</lf-option>'
    '<lf-option id="r-no">No</lf-option></lf-options></lf-ask></section>',
)


def put_fork_todo(page_dir):
    """A to-do on the user about the Implementation section's paragraph."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "grouped",
            "owner": "user",
            "subject": {"kind": "element", "id": "reap"},
            "title": "Try the sandboxed run on a fork",
        },
    )


def test_the_chosen_grouping_orders_on_me_and_the_m_walk_alike(browser, serve):
    """With no plan, On me groups its cards by the part of the page each item stands
    in, under its heading, and its cards leave that part unsaid. The chooser at its
    foot regroups the list by what each item is, the cards then naming their part
    instead, and the browser keeps the choice across a reload. Either way `m` steps
    through the items in the order the list shows them, rather than in page order."""
    url = serve(GROUPED_PAGE)
    put_fork_todo(serve.page_dir)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    view = open_on_me(page)
    chooser = page.get_by_role("combobox", name="Group On me")
    expect(chooser).to_have_value("place")
    # A group of two has a heading; the card alone in its group says its name.
    groups = view.locator(".lf-fp-on-list > .lf-rows-head")
    expect(groups).to_have_text([re.compile(r"^\s*Implementation\s*2\s*$")])
    cards = view.locator(".lf-fp-on-item")
    expect(cards.locator(".lf-fp-prompt")).to_have_text(
        [
            "Which exit code?",
            "Try the sandboxed run on a fork",
            "Include self-hosted runners?",
        ]
    )
    # Under a heading a card says nothing over its question; alone, only its place.
    expect(cards.locator(".lf-fp-on-place")).to_have_text(["Rollout"])
    # Its choices stand on the card, answered with one press.
    expect(
        on_card(page, "widget:exit").get_by_role("button", name="75")
    ).to_be_visible()

    chooser.select_option("kind")
    expect(groups).to_have_text([re.compile(r"^\s*Options\s*2\s*$")])
    page.reload()
    wait_until_ready(page)
    view = open_on_me(page)
    expect(page.get_by_role("combobox", name="Group On me")).to_have_value("kind")
    cards = view.locator(".lf-fp-on-item")
    expect(cards.locator(".lf-fp-prompt")).to_have_text(
        [
            "Which exit code?",
            "Include self-hosted runners?",
            "Try the sandboxed run on a fork",
        ]
    )
    expect(cards.locator(".lf-fp-on-place")).to_have_text(
        ["Implementation", "Rollout", "To-do · Implementation"]
    )

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


TABBED_PAGE = leaf_page(
    "tabbed asks",
    '<h1 id="title">Every plan</h1><lf-tabs id="plans">'
    '<lf-tab id="tab-first" label="First plan">'
    '<header><h1 id="first-title">Move the runs into one sandbox</h1></header>'
    '<section><h2 id="first-context">What needs to change</h2>'
    "<p>The checkout stays fixed.</p></section>"
    '<section><lf-ask id="first-ask"><h3>Include self-hosted runners?</h3>'
    '<lf-options id="first-q" choose><lf-option id="first-yes">Yes</lf-option>'
    '<lf-option id="first-no">No</lf-option></lf-options></lf-ask></section></lf-tab>'
    '<lf-tab id="tab-second" label="Second plan">'
    '<lf-ask id="second-ask"><h3>Ship on Tuesday?</h3>'
    '<lf-options id="second-q" choose><lf-option id="second-yes">Yes</lf-option>'
    '<lf-option id="second-no">No</lf-option></lf-options></lf-ask></lf-tab>'
    "</lf-tabs>",
)


def test_on_me_places_an_item_by_its_tab_s_title_or_label(browser, serve):
    """By place names the part of the page an item stands in from where it stands on:
    in a tab whose page keeps its title in a header, that title heads its untitled
    last section too, rather than the title of the page holding the tabs; and in a tab
    with no heading over the item, selected or not, the tab's own label names it."""
    page = open_page(browser, serve(TABBED_PAGE))
    resized(page, 1440, 900)
    view = open_on_me(page)
    expect(view.locator(".lf-fp-on-place")).to_have_text(
        ["Move the runs into one sandbox", "Second plan"]
    )


def test_an_answer_in_on_me_keeps_its_groups_and_the_m_walk_in_one_order(
    browser, serve
):
    """An item answered in On me keeps its seat, and the groups keep their order, read
    from everything On me has held rather than from what remains, so the list and the
    `m` walk, which steps over the answered item, still agree. Grouped by kind, the
    first question answered leaves Options above To-do, as the walk goes; its group
    keeps its heading, two cards still under it, and counts what still waits."""
    url = serve(GROUPED_PAGE)
    put_fork_todo(serve.page_dir)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    view = open_on_me(page)
    page.get_by_role("combobox", name="Group On me").select_option("kind")
    exit_code = on_card(page, "widget:exit")
    exit_code.get_by_role("button", name="75").click()
    round_trip(page)
    expect(exit_code.locator(".lf-fp-said")).to_contain_text("Answered: 75")
    groups = view.locator(".lf-fp-on-list > .lf-rows-head")
    expect(groups).to_have_text([re.compile(r"^\s*Options\s*1\s*$")])
    runners = on_card(page, "widget:runners")
    # Where the first `m` lands depends on the reading position, so it may take a
    # second; read the ring only once the press's repaint has landed.
    for _ in range(2):
        page.keyboard.press("m")
        rendered(page)
        if runners.get_attribute("data-walked") is not None:
            break
    expect(runners).to_have_attribute("data-walked", "")
    expect_walk_position(page, "1 of 2 waiting on me · Options")
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me · To-do")


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


# Card-shaped options as the registry lays them out: tags, the recommended tag, a title,
# the sentence saying what choosing it gives, inline or as a paragraph, then a picture;
# and a label-only option.
CARD_OPTIONS_PAGE = leaf_page(
    "card options",
    """<h1 id="title">Sidebar</h1>
<lf-ask id="stick-ask"><h2>How should a long sidebar stick?</h2>
<lf-options id="stick" choose>
  <lf-option id="stick-box"><small class="tag">two days</small>
    <small class="tag ok">recommended</small><strong>Wrap the blocks in one box</strong>
    One mechanism for any number of <em>blocks</em>.
    <svg class="drawing" viewBox="0 0 10 10"><text x="1" y="8">fig</text></svg></lf-option>
  <lf-option id="stick-aside"><strong>Stick the aside itself</strong> It covers the
    footer.</lf-option>
  <lf-option id="stick-rule"><strong>Keep the one-block rule</strong>
    <p>Authors keep writing one block.</p></lf-option>
  <lf-option id="stick-none">Leave it</lf-option>
</lf-options></lf-ask>""",
)


def test_an_option_s_choice_on_its_card_says_what_it_gives(browser, serve):
    """An On me card's choice for a card-shaped option names it over the sentence saying
    what choosing it gives, written inline or as a paragraph, and wears `recommended` where the page advises it, so the
    user answers there without Show; the option's other tags and its picture stay on the
    page. A label-only option's choice is its name alone. A press there picks the
    option, and Undo puts the choices back."""
    page = open_page(browser, serve(CARD_OPTIONS_PAGE))
    resized(page, 390, 844)
    open_on_me(page)
    card = on_card(page, "widget:stick")
    choices = card.locator(".lf-fp-answer[aria-pressed]")
    expect(choices).to_have_count(5)  # and Another option
    box, aside, rule, none = (choices.nth(i) for i in range(4))
    expect(box.locator(".lf-fp-choice-name")).to_have_text("Wrap the blocks in one box")
    expect(box.locator(".lf-fp-choice-tag")).to_have_text("recommended")
    expect(box.locator(".lf-fp-choice-says")).to_have_text(
        "One mechanism for any number of blocks."
    )
    expect(aside.locator(".lf-fp-choice-says")).to_have_text("It covers the footer.")
    expect(aside.locator(".lf-fp-choice-tag")).to_have_count(0)
    expect(rule.locator(".lf-fp-choice-says")).to_have_text(
        "Authors keep writing one block."
    )
    expect(none).not_to_have_attribute("data-told", "")
    expect(none).to_have_text("Leave it")

    aside.click()
    round_trip(page)
    expect(page.locator("#stick-aside")).to_have_attribute("chosen", "")
    card.get_by_role("button", name="Undo").click()
    round_trip(page)
    expect(page.locator("#stick-aside")).not_to_have_attribute("chosen", "")
    expect(card.locator(".lf-fp-answer[data-told]")).to_have_count(3)


def test_a_group_s_done_on_its_card_commits_rather_than_reading_as_a_choice(
    browser, serve
):
    """A `multiple` group's Done stands on its On me card as the press that commits the
    picks, not as one more described choice: its name alone, what it does as its
    tooltip, and as wide as its word while each described choice takes the line. A
    press there answers the group as Done on the page does."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "done on its card",
                """<h1 id="title">Tags</h1>
<lf-ask id="tags-ask"><h2>Which tags?</h2>
<lf-options id="tags" choose multiple>
  <lf-option id="tag-alpha" chosen><strong>Alpha</strong> The first tag.</lf-option>
  <lf-option id="tag-beta"><strong>Beta</strong> The second tag.</lf-option>
</lf-options></lf-ask>""",
            )
        ),
    )
    open_on_me(page)
    card = on_card(page, "widget:tags")
    told = card.locator(".lf-fp-answer[data-told]")
    expect(told).to_have_count(2)
    done = card.get_by_role("button", name="Done", exact=True)
    expect(done).to_have_text("Done")
    expect(done).to_have_attribute("title", "Finish choosing options")
    assert done.bounding_box()["width"] < told.first.bounding_box()["width"] / 3

    done.click()
    round_trip(page)
    expect(page.locator("#tags .lf-done")).to_have_attribute("aria-pressed", "true")


# Two decisions, the first under a heading a thread can be anchored on.
TWO_DECISIONS_PAGE = leaf_page(
    "two decisions",
    """<h1 id="title">Review</h1>
<section id="timeline-ask"><h2>Land the timeline prototype?</h2>
<lf-options id="timeline" choose>
  <lf-option id="tl-land">Land it</lf-option>
  <lf-option id="tl-keep">Keep it on its branch</lf-option>
</lf-options></section>
<lf-ask id="ship-ask"><h2>Ship on Friday?</h2>
<lf-options id="ship" choose>
  <lf-option id="ship-friday">Ship Friday</lf-option>
  <lf-option id="ship-wait">Wait a week</lf-option>
</lf-options></lf-ask>""",
)


def thread_about_the_timeline(d):
    """The user's comment on the timeline decision, and the agent's answer, which leaves
    the user the next move."""
    root = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "These need previews.",
            "anchor": {"section": "timeline-ask"},
        },
    )["id"]
    reply = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root,
            "responds": root,
            "text": "Previews added; try each before deciding.",
            "obligation": True,
        },
    )["id"]
    return root, reply


def test_an_answer_about_a_decision_rides_on_the_decisions_card(browser, serve):
    """An agent's answer that leaves the user a move, in a thread about a decision, is
    one place with the decision: `m` stops there once and On me draws one card, the
    decision's, carrying the answer. Choosing on the card keeps the answer there with
    its Reply, rather than moving it to a card of its own above."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    for decision, at in [("timeline", 1), ("ship-ask", 2), ("timeline", 1)]:
        page.keyboard.press("m")
        expect_walk_position(page, f"{at} of 2 waiting on me · Options")
        expect(page.locator(f"#{decision}")).to_be_focused()
    view = open_on_me(page)
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(2)
    carrier = on_card(page, "widget:timeline")
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")
    before = on_card(page, "widget:ship").bounding_box()
    carrier.get_by_role("button", name="Land it").click()
    expect(carrier.locator(".lf-fp-said")).to_have_text("Answered: Land it")
    expect(carrier.get_by_role("button", name="Reply")).to_be_visible()
    told(page)
    expect(cards).to_have_count(2)
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")
    assert on_card(page, "widget:ship").bounding_box()["y"] == pytest.approx(
        before["y"], abs=1
    )
    # Opened afresh, the answer stands on its own card, until the user replies.
    page.keyboard.press("Escape")
    view = open_on_me(page)
    expect(
        view.locator(f'.lf-fp-on-item[data-key=\'["message","message:{reply}"]\']')
    ).to_be_visible()


def test_m_steps_off_a_decision_its_threads_card_stands_beside(browser, serve):
    """A to-do in a thread about a decision is a stop of its own, though the thread's card
    stands beside the decision: standing at the decision is being on the decision, so
    `m` steps on from each to the next and reaches all three."""
    url = serve(TWO_DECISIONS_PAGE)
    root, _ = thread_about_the_timeline(serve.page_dir)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Claude",
            "session": "previews",
            "owner": "user",
            "subject": {"kind": "thread", "id": root},
            "title": "Try the previews",
        },
    )
    page = open_page(browser, url)
    reached = [None]
    for _ in range(3):
        page.keyboard.press("m")
        walk_position(page)
        page.wait_for_function(
            "said => (window.__lfWalkPosition()?.text ?? null) !== said",
            arg=reached[-1],
        )
        reached.append(walk_position(page)["text"])
    reached = reached[1:]
    assert reached is not None
    assert all(isinstance(position, str) for position in reached)
    assert sorted(position for position in reached if position is not None) == [
        "1 of 3 waiting on me · To-do",
        "2 of 3 waiting on me · Options",
        "3 of 3 waiting on me · Options",
    ], reached


def test_a_decision_answered_on_the_page_keeps_the_answer_it_carries_listed(
    browser, serve
):
    """Answered on the page, a decision keeps its row, and the agent's answer it
    carries, until the server's reading of the choice moves them: the browser keeps a
    widget record's status as the server last read it, so nothing it carried drops off
    On me in between."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    expect(page.locator(".lf-fp-on-user")).to_have_text("2")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#tl-land").click()
    holding(page, held, 1, "the held choice")
    on_me = """async () => (await window.__lfWidgetApi()).readQueues().on_user
      .map((row) => [row.id, row.also])"""
    assert sorted(page.evaluate(on_me)) == [
        ["widget:ship", []],
        ["widget:timeline", [f"message:{reply}"]],
    ]
    expect(page.locator(".lf-fp-on-user")).to_have_text("2")
    held[0].continue_()
    page.unroute("**/api/event")


def test_an_answer_about_two_decisions_stays_on_the_card_that_carried_it(
    browser, serve
):
    """A thread about a section holding two decisions rides on the first; once that one
    is answered the server moves it to the second, but the open view keeps it on the
    card the user answered, drawn once."""
    source = TWO_DECISIONS_PAGE.replace(
        '<lf-ask id="ship-ask">', '<section id="both-asks"><lf-ask id="ship-ask">'
    ).replace("</lf-ask>", "</lf-ask></section>")
    source = source.replace(
        '<section id="timeline-ask">',
        '<section id="both-outer"><section id="timeline-ask">',
    ).replace('</section>\n<section id="both-asks">', "</section>\n")
    url = serve(source)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Both need previews.",
            "anchor": {"section": "both-outer"},
        },
    )["id"]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root,
            "responds": root,
            "text": "Previews added for both.",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    view = open_on_me(page)
    carrier = on_card(page, "widget:timeline")
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")
    carrier.get_by_role("button", name="Land it").click()
    told(page)
    expect(on_card(page, "widget:ship").locator(".lf-fp-asked")).to_have_count(0)
    expect(view.locator(".lf-fp-asked")).to_have_count(1)
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")


def test_a_carried_answer_the_agent_ends_stays_on_its_card_not_in_done(browser, serve):
    """Once the user answers a decision on its card, the agent may end the question it
    carries as settled (`waiting`). The open view keeps the question on that card and
    lists it in Done no second time, so its message is drawn once."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    view = open_on_me(page)
    carrier = on_card(page, "widget:timeline")
    carrier.get_by_role("button", name="Land it").click()
    told(page)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Claude",
            "todo": f"message:{reply}",
            "outcome": "done",
            "detail": "The pick settles it.",
        },
    )
    told(page)
    expect(view.locator(".lf-fp-asked")).to_have_count(1)
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")
