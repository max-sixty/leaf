"""On Me in the floating panel: the cards that name each open and answered obligation, their
identity, grouping and order, and what an answered one says."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_OBLIGATIONS_IN_ORDER,
    CHANGE_SHAPES_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    ON_ITEM_SAYS,
    serve_obligations,
)
from render_cases_navigation import source_revision
from render_harness import (
    PANEL,
    expect_obligations_answered,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    post_event,
    preview_parts,
    refuse,
    resized,
    round_trip,
    sending,
    show_done,
    told,
    watched,
)

from browser.navigation import expect_walk_position
from leaf.log import event_log as events_model
from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.browser import open_on_me as open_on_me_by_pointer
from leaf_dev.browser import panel_tab

pytestmark = pytest.mark.shifts_unsurveyed

ON_ME = panel_view("queue")


def open_on_me(page):
    """Open On Me by pointer, unless it stands open, and return its view; another view
    standing open is put away first, by its ✕."""
    shown = page.locator(PANEL).get_attribute("data-lf-open")
    if shown not in (None, "menu", "queue", "threads"):
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
    open_on_me_by_pointer(page)
    panel_settled(page, view="queue")
    return page.locator(ON_ME)


def on_card(page, at):
    """The On Me card for the obligation `at` names, such as `widget:sug-refill`."""
    return page.locator(f"{ON_ME} .lf-fp-on-item[data-lf-key='{at}']")


def test_on_me_lists_open_and_answered_obligations(browser, serve):
    """The panel's On Me lists every open obligation, in document order, and
    every answered one folded under Done with its current answer, so the user can review
    and revise. A twelfth widget joins by declaring `awaits`.

    A closed view holds no cards at all: they are the open view's rendering, the mark's
    count is the closed view's, and a hidden list of buttons is a set of controls no
    user can press — which the press sweep sees as the page's control set changing
    under it."""
    page = open_page(browser, serve_obligations(serve))
    resized(page, 1920, 900)
    assert page.evaluate(ON_ITEM_SAYS) == [], "a closed view holds no cards"

    page.locator(".lf-fp-leaf").focus()
    page.keyboard.press("Enter")
    panel_settled(page, view="queue")
    show_done(page)
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
    show_done(page)
    expect(page.locator(f"{ON_ME} .lf-fp-on-item")).to_have_count(5)
    answered = {c["id"]: c for c in page.evaluate(ON_ITEM_SAYS)}
    assert answered["widget:live-question"]["list"] == "done", answered
    assert answered["widget:live-question"]["said"].startswith(
        "Answered: Signed tokens"
    ), answered

    page.locator(
        "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
    ).click()
    round_trip(page)
    open_on_me(page)
    show_done(page)
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
<lf-group id="note-ask" label="Is this release note right?"><h2 id="note-ask-h">Is this release note right?</h2>
<lf-draft id="note" required><pre>
Adds --dry-run to every mutating command.
</pre></lf-draft></lf-group>
<lf-group id="cache-ask" label="Which cache?"><h2 id="cache-ask-h">Which cache?</h2>
<lf-options id="cache">
  <lf-option id="cache-none" label="No cache"><strong>No cache</strong> Read through.</lf-option>
</lf-options></lf-group>
<lf-group id="tags-ask" label="Which tags?"><h2 id="tags-ask-h">Which tags?</h2>
<lf-options id="tags" multiple>
  <lf-option id="tag-alpha" label="Alpha" selected><strong>Alpha</strong></lf-option>
  <lf-option id="tag-beta" label="Beta"><strong>Beta</strong></lf-option>
</lf-options></lf-group>
<lf-group id="tone-ask" label="Which notification?"><h2 id="tone-ask-h">Which notification?</h2>
<lf-playground id="tone">
  <aside><fieldset id="format"><legend>Format</legend>
    <label id="format-banner"><input type="radio" name="format" value="banner" checked> Banner</label>
    <label id="format-strip"><input type="radio" name="format" value="strip"> Strip</label>
  </fieldset></aside>
  <p id="tone-preview">The notification.</p>
  <lf-playground-output>Build the <output for="format"></output>
  notification.</lf-playground-output>
</lf-playground></lf-group>
""",
        )
    )
    page = open_page(browser, url)
    door = url.rsplit("/versions/", 1)[0] + "/api/event"
    # Each with the word its widget sends: an added option, like a tune, answers
    # nothing until the pick or the choice that follows it.
    for widget, action, detail, answered in [
        ("note", "edit", {"value": "Adds --dry-run to every command."}, True),
        (
            "cache",
            "add",
            {"option": "cache-redis", "text": "**Redis** in front"},
            False,
        ),
        ("cache", "choose", {"value": ["cache-redis"]}, True),
        ("tags", "answer", {}, True),
        # The controls draw the tune in force, which submitting records first.
        ("tone", "tune", {"values": {"format": "strip"}}, False),
        (
            "tone",
            "choose",
            {"values": {"format": "strip"}, "instruction": "Build the strip one."},
            True,
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
                "answered": answered,
            },
        )
        assert posted.ok, posted.text()
    expect_obligations_answered(page, "4/4")
    output = page.locator("#tone lf-playground-output")
    expect(output).to_contain_text("strip")
    page.locator("#tone").get_by_role("radio", name="Banner").click()
    expect(output).to_contain_text("banner")
    open_on_me(page)
    show_done(page)
    answers = {
        "widget:note": "Adds --dry-run to every command.",
        "widget:cache": "Redis in front",
        "widget:tags": "Alpha",
        "widget:tone": "Build the strip one.",
    }
    for at, words in answers.items():
        expect(
            on_card(page, at).locator(".lf-fp-on-says > .lf-fp-value")
        ).to_contain_text(f"Answered: {words}")


def test_obligation_cards_keep_identity_and_walk_order_when_the_live_dom_moves(
    browser, serve
):
    """A keyed card keeps its node and focus however the page's DOM moves, and stands
    where the `m` walk reaches its item: an item whose element leaves the page goes
    after those still on it, as the walk takes it last. That item leaves its place's
    group for the whole page's, so its card is drawn afresh in that group's box and
    keeps focus; every other card keeps its node."""
    page = open_page(browser, serve_obligations(serve))
    open_on_me(page)
    show_done(page)
    cards = page.locator(f"{ON_ME} .lf-fp-on-item")
    expect(cards).to_have_count(len(ALL_OBLIGATIONS_IN_ORDER))
    order = [
        "widget:live-question",
        "widget:sug-refill",
        "widget:t-baffles-review",
        "widget:t-bath-choice",
        "widget:honored",
    ]

    page.evaluate(
        """async () => {
          const {readApplicationPresentation, presentDocument} =
            await window.__lfCheckApi();
          window.__lfReadObligationPresentation = readApplicationPresentation;
          window.__lfPresentDocument = presentDocument;
          const cards = [...document.querySelectorAll(
            '.lf-fp-view[data-lf-route="queue"] .lf-fp-on-item')];
          window.__lfObligationCards = new Map(cards.map(card => [card.dataset.lfKey, card]));
          const honored = document.querySelector('#honored-decision');
          document.querySelector('#live-question-decision').before(honored);
          window.__lfObligationCards.get('widget:sug-refill').focus();
          await presentDocument();
        }"""
    )
    page.wait_for_function("__lfReadObligationPresentation().pending.length === 0")
    assert cards.evaluate_all("items => items.map(item => item.dataset.lfKey)") == order
    assert cards.evaluate_all(
        "items => items.every(item => window.__lfObligationCards.get(item.dataset.lfKey) === item)"
    )
    sug_refill = on_card(page, "widget:sug-refill")
    expect(sug_refill).to_be_focused()

    # Removing a presentation node does not rewrite the application inventory: the
    # keyed card stays, focus with it, and takes the walk's place for an item with no
    # place on the page, after the rest of the list, under the whole page's band.
    page.evaluate(
        """async () => {
          document.querySelector('#sug-refill').remove();
          await window.__lfPresentDocument();
        }"""
    )
    page.wait_for_function("__lfReadObligationPresentation().pending.length === 0")
    assert cards.evaluate_all("items => items.map(item => item.dataset.lfKey)") == [
        order[0],
        order[2],
        order[3],
        order[1],
        order[4],
    ]
    expect(sug_refill).to_be_focused()
    expect(
        sug_refill.locator(
            "xpath=ancestor::section[contains(@class, 'lf-rows-group')]"
        ).locator(":scope > .lf-rows-head .lf-row-main")
    ).to_have_text("The whole page")
    assert cards.evaluate_all(
        """items => items.every(item => item.dataset.lfKey === 'widget:sug-refill'
          || window.__lfObligationCards.get(item.dataset.lfKey) === item)"""
    )


def test_a_completed_obligation_persists_and_on_me_says_its_current_answer(
    browser, serve
):
    """Completion survives a reload, and On Me, opened from the keyboard, keeps the
    answered obligation folded under Done, a line saying its current answer, which
    follows a revision."""
    page = open_page(browser, serve(OBLIGATION_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    expect_obligations_answered(page, "0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect_obligations_answered(page, "1/1")

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_obligations_answered(page, "1/1")

    # With nothing on the user, the view opens on an empty list with Done folded under
    # it; ↓ enters Done's band, Enter unfolds it, and ↓ enters its first line, the
    # obligation's.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("ArrowDown")
    done = page.locator(f"{ON_ME} .lf-fp-settled")
    expect(done).to_be_focused()
    page.keyboard.press("Enter")
    expect(done).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowDown")
    card = on_card(page, "widget:storage-options")
    expect(card.locator(".lf-fp-on-line")).to_be_focused()
    expect(card).to_have_attribute("data-lf-list", "done")
    expect(card.locator(".lf-fp-on-says > .lf-fp-value")).to_contain_text(
        "Answered: Pause offline editing"
    )

    page.locator("#storage-evict").click()
    round_trip(page)
    expect(page.locator("#storage-evict")).to_have_attribute("selected", "")
    expect_obligations_answered(page, "1/1")
    open_on_me(page)
    show_done(page)
    expect(card.locator(".lf-fp-on-says > .lf-fp-value")).to_contain_text(
        "Answered: Drop the oldest documents"
    )


def test_an_answered_boxless_obligation_is_taken_back_from_its_card(browser, serve):
    """An accepted deletion leaves no box on the page to arrive at, so its line under On
    Me's Done is where the user takes the decision back: it says what was decided, and
    opened, its Undo restores the change to decide again."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    expect_obligations_answered(page, "0/4")

    page.locator(
        "[data-lf-margin-for='sug-delete'] [data-lf-margin-entry-key=accept]"
    ).click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect_obligations_answered(page, "1/4")

    open_on_me(page)
    show_done(page)
    card = on_card(page, "widget:sug-delete")
    expect(card).to_have_attribute("data-lf-list", "done")
    expect(card.locator(".lf-fp-on-says > .lf-fp-value")).to_contain_text(
        "Answered: Accepted"
    )
    card.locator(".lf-fp-on-line").click()
    card.get_by_role("button", name="Undo").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect_obligations_answered(page, "0/4")


def test_on_me_s_tabs_stand_where_a_view_names_itself(browser, serve):
    """On Me's tabs name its view, so the first starts its controls' line, its words on
    the panel's text line and its frame on the field's edge, rather than standing among
    the presses at their end; no name bar stands over the view, the heading naming it to
    assistive tech alone. The strip holding the tabs reaches past them for their focus
    ring, so the tab is read."""
    page = open_page(browser, serve_obligations(serve))
    resized(page, 1440, 900)
    open_on_me(page)
    start, words, frame, field = page.locator(".lf-floating-panel").evaluate(
        """p => {
          const c = p.querySelector('.lf-fp-controls');
          const tab = c.querySelector('.lf-fp-filters > .lf-fp-tab');
          return [c.getBoundingClientRect().left + parseFloat(getComputedStyle(c).paddingLeft),
            tab.querySelector('.lf-fp-tab-words').getBoundingClientRect().left,
            tab.getBoundingClientRect().left,
            p.querySelector('.lf-fp-field').getBoundingClientRect().left];
        }"""
    )
    assert words == start, (words, start)
    assert frame == field, (frame, field)
    assert page.locator(".lf-fp-head").bounding_box()["height"] == 0


def test_an_on_list_the_page_cannot_read_counts_nothing(browser, serve):
    """With the server's reading refused, On Me says it can't be had, and neither On
    list's tab gives a count, as Threads' doesn't: a 0 there would claim an empty list
    the page never read, on a page that asks the user for several decisions."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.route("**/api/state*", refuse)
    page.goto(serve_obligations(serve), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    on_me = open_on_me(page)
    expect(on_me.locator(".lf-rows-empty")).to_have_text(
        "On Me is unavailable while the server is offline."
    )
    for tab in ("On Me", "On the agent", "Threads"):
        expect(panel_tab(page, tab)).to_be_visible()
        expect(panel_tab(page, tab).locator(".lf-fp-count")).to_have_count(0)


def test_show_on_a_card_goes_where_m_arrives_and_only_where_that_is_elsewhere(
    browser, serve
):
    """Every On Me card whose item has somewhere to go offers Show, a question answered
    on its card included, and Show puts the user where `m` puts them."""
    url = serve(CHANGE_SHAPES_PAGE)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    # Where `m` arrives at the question: the fourth stop in page order.
    page.locator("#title").click()
    for _ in range(4):
        page.keyboard.press("m")
    expect_walk_position(page, "4 of 4 waiting on me")
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
        f'<lf-group id="ask-{n}" label="Bring item {n}?"><h2 id="ask-{n}-h">Bring item {n}?</h2>'
        f'<lf-options id="pick-{n}"><lf-option id="yes-{n}">Yes</lf-option>'
        f'<lf-option id="no-{n}">No</lf-option></lf-options></lf-group>'
        for n in range(1, 9)
    ),
)


def test_the_m_walk_brings_its_card_into_on_me_s_view_and_rings_it(browser, serve):
    """While On Me is open, `m` and Shift+`m` bring the card of the item they reach into
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
    expect_walk_position(page, "8 of 8 waiting on me")
    expect(page.locator("#ask-8")).to_be_focused()
    expect(view.locator(".lf-fp-on-item[data-lf-walked]")).to_have_count(1)
    expect(last).to_have_attribute("data-lf-walked", "")
    assert last.evaluate("card => getComputedStyle(card).outlineStyle") == "solid"
    assert shown(last)

    first = on_card(page, "widget:pick-1")
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 8 waiting on me")
    expect(first).to_have_attribute("data-lf-walked", "")
    expect(last).not_to_have_attribute("data-lf-walked", "")
    assert shown(first)


ORDERED_PAGE = leaf_page(
    "walk order",
    '<h1 id="title">Release</h1><p id="cadence">We publish a build every week.</p>'
    '<lf-group id="channel-ask" label="Which channel first?"><h2 id="channel-ask-h">Which channel first?</h2>'
    '<lf-options id="channel"><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-group>'
    '<p id="notes">Release notes come from merged titles.</p>',
)


def ask_in_thread(page_dir, section, question):
    """A question the agent asks the user in a thread of its own on `section`, as
    `leaf thread create --section --obligation` does."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "anchor": {"section": section},
            "text": question,
            "obligation": True,
        },
    )


def test_on_me_lists_its_cards_in_the_order_m_walks_them(browser, serve):
    """On Me lists its cards in the order `m` reaches their items, by where each is on
    the page, rather than the server's order, which puts what the page asks before
    the questions asked in threads. So successive presses of `m` outline successive
    cards."""
    url = serve(ORDERED_PAGE)
    ask_in_thread(serve.page_dir, "cadence", "Can you check the cadence?")
    ask_in_thread(serve.page_dir, "notes", "Can you check the notes?")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    view = open_on_me(page)
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(3)
    expect(cards).to_have_text(
        [
            re.compile("Can you check the cadence"),
            re.compile("Which channel first"),
            re.compile("Can you check the notes"),
        ]
    )

    def walked():
        expect(view.locator(".lf-fp-on-item[data-lf-walked]")).to_have_count(1)
        return cards.evaluate_all(
            "cards => cards.findIndex((card) => card.hasAttribute('data-lf-walked'))"
        )

    page.keyboard.press("m")
    first = walked()
    for step in (1, 2, 3):
        page.keyboard.press("m")
        expect(cards.nth((first + step) % 3)).to_have_attribute("data-lf-walked", "")


GROUPED_PAGE = leaf_page(
    "grouped asks",
    '<h1 id="title">Release</h1>'
    '<section><h2 id="impl">Implementation</h2>'
    '<lf-group id="exit-ask" label="Which exit code?"><h3 id="exit-ask-h">Which exit code?</h3>'
    '<lf-options id="exit"><lf-option id="e75">75</lf-option>'
    '<lf-option id="e124">124</lf-option></lf-options></lf-group>'
    '<p id="reap">Reap every process under the sandbox user.</p></section>'
    '<section><h2 id="rollout">Rollout</h2>'
    '<lf-group id="runner-ask" label="Include self-hosted runners?"><h3 id="runner-ask-h">Include self-hosted runners?</h3>'
    '<lf-options id="runners"><lf-option id="r-yes">Yes</lf-option>'
    '<lf-option id="r-no">No</lf-option></lf-options></lf-group></section>',
)


FORK_QUESTION = "Can you try the sandboxed run on a fork?"


def test_the_chosen_grouping_orders_on_me_and_the_m_walk_alike(browser, serve):
    """With no plan, On Me groups its cards by the part of the page each item stands
    in, each group under its band, one card alone included, and its cards leave that
    part unsaid. The chooser at its foot regroups the list by what each item is, the
    cards then naming their part instead, and the browser keeps the choice across a
    reload. Either way `m` steps
    through the items in the order the list shows them, rather than in page order."""
    url = serve(GROUPED_PAGE)
    ask_in_thread(serve.page_dir, "reap", FORK_QUESTION)
    page = open_page(browser, url)
    # Tall enough that each stop stands above the open On Me view, which covers the
    # window's foot: a key at a stop the view hides lets go of it, so `m` would go on
    # from what the user reads rather than from the stop.
    resized(page, 1440, 1400)
    view = open_on_me(page)
    chooser = page.get_by_role("combobox", name="Group On Me")
    expect(chooser).to_have_value("place")
    # Every group has its band, the card alone in its group included.
    groups = view.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    expect(groups).to_have_text(
        [
            re.compile(r"^\s*Implementation\s*2\s*$"),
            re.compile(r"^\s*Rollout\s*1\s*$"),
        ]
    )
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_text(
        [
            re.compile("Which exit code"),
            re.compile(re.escape(FORK_QUESTION)),
            re.compile("Include self-hosted runners"),
        ]
    )
    # Under its place's band a card says nothing over its question.
    expect(cards.locator(".lf-fp-on-place")).to_have_count(0)
    # Its choices stand on the card, answered with one press.
    expect(
        on_card(page, "widget:exit").get_by_role("button", name="75")
    ).to_be_visible()

    chooser.select_option("kind")
    expect(groups).to_have_text(
        [re.compile(r"^\s*Options\s*2\s*$"), re.compile(r"^\s*Reply\s*1\s*$")]
    )
    page.reload()
    wait_until_ready(page)
    view = open_on_me(page)
    expect(page.get_by_role("combobox", name="Group On Me")).to_have_value("kind")
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_text(
        [
            re.compile("Which exit code"),
            re.compile("Include self-hosted runners"),
            re.compile(re.escape(FORK_QUESTION)),
        ]
    )
    expect(cards.locator(".lf-fp-on-place")).to_have_text(
        ["Implementation", "Rollout", "Implementation"]
    )

    def walked():
        expect(view.locator(".lf-fp-on-item[data-lf-walked]")).to_have_count(1)
        return cards.evaluate_all(
            "cards => cards.findIndex((card) => card.hasAttribute('data-lf-walked'))"
        )

    page.keyboard.press("m")
    first = walked()
    for step in (1, 2, 3):
        page.keyboard.press("m")
        expect(cards.nth((first + step) % 3)).to_have_attribute("data-lf-walked", "")


TABBED_PAGE = leaf_page(
    "tabbed asks",
    '<h1 id="title">Every plan</h1><lf-tabs id="plans">'
    '<lf-tab id="tab-first" label="First plan">'
    '<header><h1 id="first-title">Move the runs into one sandbox</h1></header>'
    '<section><h2 id="first-context">What needs to change</h2>'
    "<p>The checkout stays fixed.</p></section>"
    '<section><lf-group id="first-ask" label="Include self-hosted runners?"><h3 id="first-ask-h">Include self-hosted runners?</h3>'
    '<lf-options id="first-q"><lf-option id="first-yes">Yes</lf-option>'
    '<lf-option id="first-no">No</lf-option></lf-options></lf-group></section></lf-tab>'
    '<lf-tab id="tab-second" label="Second plan">'
    '<lf-group id="second-ask" label="Ship on Tuesday?"><h3 id="second-ask-h">Ship on Tuesday?</h3>'
    '<lf-options id="second-q"><lf-option id="second-yes">Yes</lf-option>'
    '<lf-option id="second-no">No</lf-option></lf-options></lf-group></lf-tab>'
    "</lf-tabs>",
)


def test_on_me_places_an_item_by_its_tab_s_title_or_label(browser, serve):
    """By place, each group's band names the part of the page its items stand in from
    where they stand: in a tab whose page keeps its title in a header, that title heads
    its untitled last section too, rather than the title of the page holding the tabs;
    and in a tab with no heading over the item, selected or not, the tab's own label
    names it."""
    page = open_page(browser, serve(TABBED_PAGE))
    resized(page, 1440, 900)
    view = open_on_me(page)
    expect(view.locator(".lf-rows-group > .lf-rows-head .lf-row-main")).to_have_text(
        ["Move the runs into one sandbox", "Second plan"]
    )


PARTS_PAGE = leaf_page(
    "two parts",
    '<h1 id="title">Two parts</h1>'
    '<section><h2 id="first-h">First part</h2>'
    '<lf-group id="ask-a" label="Question A"><h3 id="ask-a-h">Question A</h3>'
    '<lf-options id="a"><lf-option id="a-yes">Yes</lf-option>'
    '<lf-option id="a-no">No</lf-option></lf-options></lf-group></section>'
    '<section><h2 id="second-h">Second part</h2>'
    '<lf-group id="ask-b" label="Question B"><h3 id="ask-b-h">Question B</h3>'
    '<lf-options id="b"><lf-option id="b-yes">Yes</lf-option>'
    '<lf-option id="b-no">No</lf-option></lf-options></lf-group>'
    '<div id="inner"><lf-group id="ask-c" label="Question C"><h3 id="ask-c-h">Question C</h3>'
    '<lf-options id="c"><lf-option id="c-yes">Yes</lf-option>'
    '<lf-option id="c-no">No</lf-option></lf-options></lf-group></div></section>',
)


def test_on_me_follows_a_name_or_an_id_the_page_changes(browser, serve):
    """On Me reads where its items stand again whenever the page changes what names a
    part or which element an id names, though neither changes the page's words: a box
    that gains an `aria-label` heads a group of its own, and two questions whose groups
    swap ids swap places in the list."""
    page = open_page(browser, serve(PARTS_PAGE))
    resized(page, 1440, 900)
    view = open_on_me(page)
    heads = view.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head .lf-row-main")
    cards = view.locator(".lf-fp-on-item")
    expect(heads).to_have_text(["First part", "Second part"])

    page.evaluate(
        """async () => {
          document.querySelector('#inner').setAttribute('aria-label', 'Third part');
          await (await window.__lfCheckApi()).presentDocument();
        }"""
    )
    expect(heads).to_have_text(["First part", "Second part", "Third part"])

    page.evaluate(
        """async () => {
          const first = document.querySelector('#ask-a');
          const last = document.querySelector('#ask-c');
          first.id = 'ask-swap';
          last.id = 'ask-a';
          first.id = 'ask-c';
          await (await window.__lfCheckApi()).presentDocument();
        }"""
    )
    expect(cards).to_have_count(3)
    page.wait_for_function(
        """() => [...document.querySelectorAll(
          '.lf-fp-view[data-lf-route="queue"] .lf-fp-on-item')].map(card => card.dataset.lfKey)
          .join() === 'widget:c,widget:b,widget:a'"""
    )


def test_an_answer_in_on_me_keeps_its_groups_and_the_m_walk_in_one_order(
    browser, serve
):
    """An item answered in On Me keeps its seat, and the groups keep their order, read
    from everything On Me has held rather than from what remains, so the list and the
    `m` walk, which steps over the answered item, still agree. Grouped by kind, the
    first question answered leaves Options above Reply, as the walk goes; its group
    keeps its band, two cards still under it, and counts what still waits."""
    url = serve(GROUPED_PAGE)
    ask_in_thread(serve.page_dir, "reap", FORK_QUESTION)
    page = open_page(browser, url)
    # Tall enough that each stop stands above the open On Me view, which covers the
    # window's foot: a key at a stop the view hides lets go of it, so `m` would go on
    # from what the user reads rather than from the stop.
    resized(page, 1440, 1400)
    view = open_on_me(page)
    page.get_by_role("combobox", name="Group On Me").select_option("kind")
    exit_code = on_card(page, "widget:exit")
    exit_code.get_by_role("button", name="75").click()
    round_trip(page)
    expect(exit_code.locator(".lf-fp-said")).to_contain_text("Answered: 75")
    groups = view.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    expect(groups).to_have_text(
        [re.compile(r"^\s*Options\s*1\s*$"), re.compile(r"^\s*Reply\s*1\s*$")]
    )
    runners = on_card(page, "widget:runners")
    # Where the first `m` lands depends on the reading position, so it may take a
    # second; read the ring only once the press's repaint has landed.
    for _ in range(2):
        page.keyboard.press("m")
        rendered(page)
        if runners.get_attribute("data-lf-walked") is not None:
            break
    expect(runners).to_have_attribute("data-lf-walked", "")
    expect_walk_position(page, "1 of 2 waiting on me")
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me")


def test_an_item_arriving_above_takes_its_walk_place_and_moves_no_card_read(
    browser, serve
):
    """An item that joins On Me while it is open takes its place in the walk's order,
    so a question asked on the page's title is the first card as `m` reaches it first.
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
    ask_in_thread(serve.page_dir, "title", "Can you check the title?")
    told(page)
    expect(cards).to_have_count(9)
    expect(cards.first).to_contain_text("Can you check the title?")
    # Scroll anchoring restores the offset to the scroller's subpixel precision.
    after = read.bounding_box()
    assert after["y"] == pytest.approx(before["y"], abs=1), (before, after)


# Card-shaped options as the registry lays them out: a label, tags, a title, the
# sentence saying what choosing it gives, inline or as a paragraph, then a picture; one
# recommended; and a compact option.
CARD_OPTIONS_PAGE = leaf_page(
    "card options",
    """<h1 id="title">Sidebar</h1>
<lf-group id="stick-ask" label="How should a long sidebar stick?"><h2 id="stick-ask-h">How should a long sidebar stick?</h2>
<lf-options id="stick">
  <lf-option id="stick-box" label="Wrap the blocks in one box" recommended><small class="lf-tag">two days</small> <strong>Wrap the blocks in one box</strong>
    One mechanism for any number of <em>blocks</em>.
    <svg class="lf-drawing" viewBox="0 0 10 10"><text x="1" y="8">fig</text></svg></lf-option>
  <lf-option id="stick-aside" label="Stick the aside itself"><strong>Stick the aside itself</strong> It covers the
    footer.</lf-option>
  <lf-option id="stick-rule" label="Keep the one-block rule">    <strong>Keep the one-block rule</strong> <p>Authors keep writing one block.</p></lf-option>
  <lf-option id="stick-none">Leave it</lf-option>
</lf-options></lf-group>""",
)


def test_an_option_s_choice_on_its_card_is_its_name(browser, serve):
    """An On Me card's choice for an option is its name, a card's `label` or a compact
    option's words, and wears `recommended` where the page advises it, so the user
    answers there without Show. The card's own words, tags and picture stay on the
    page, since Leaf picks no sentence out of the author's markup. A press there picks
    the option, and Undo puts the choices back."""
    page = open_page(browser, serve(CARD_OPTIONS_PAGE))
    resized(page, 390, 844)
    open_on_me(page)
    card = on_card(page, "widget:stick")
    choices = card.locator(".lf-fp-answer[aria-pressed]")
    expect(choices).to_have_count(5)  # and Another option
    box, aside, rule, none = (choices.nth(i) for i in range(4))
    expect(box.locator(".lf-fp-choice-name")).to_have_text("Wrap the blocks in one box")
    expect(box.locator(".lf-fp-choice-tag")).to_have_text("recommended")
    expect(card.locator(".lf-fp-choice-says")).to_have_count(0)
    expect(box).to_have_accessible_description("")
    for choice in (aside, rule, none):
        expect(choice).not_to_have_attribute("data-lf-told", "")
    expect(aside).to_have_text("Stick the aside itself")
    expect(rule).to_have_text("Keep the one-block rule")
    expect(none).to_have_text("Leave it")

    aside.click()
    round_trip(page)
    expect(page.locator("#stick-aside")).to_have_attribute("selected", "")
    card.get_by_role("button", name="Undo").click()
    round_trip(page)
    expect(page.locator("#stick-aside")).not_to_have_attribute("selected", "")
    expect(card.locator(".lf-fp-answer[data-lf-told]")).to_have_count(1)


def test_a_group_s_done_on_its_card_commits_rather_than_reading_as_a_choice(
    browser, serve
):
    """A `multiple` group's Done stands on its On Me card as the press that commits the
    picks, not as one more described choice: its name alone, what it does as its
    tooltip, and as wide as its word while a described choice, such as the
    recommended one, takes the line. A press there answers the group as Done on the
    page does."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "done on its card",
                """<h1 id="title">Tags</h1>
<lf-group id="tags-ask" label="Which tags?"><h2 id="tags-ask-h">Which tags?</h2>
<lf-options id="tags" multiple>
  <lf-option id="tag-alpha" label="Alpha" recommended selected><strong>Alpha</strong> The first tag.</lf-option>
  <lf-option id="tag-beta" label="Beta"><strong>Beta</strong> The second tag.</lf-option>
</lf-options></lf-group>""",
            )
        ),
    )
    open_on_me(page)
    card = on_card(page, "widget:tags")
    told = card.locator(".lf-fp-answer[data-lf-told]")
    expect(told).to_have_count(1)
    done = card.get_by_role("button", name="Done", exact=True)
    expect(done).to_have_text("Done")
    assert preview_parts(done) == ["Done", "Finish choosing options"]
    assert done.bounding_box()["width"] < told.first.bounding_box()["width"] / 3

    done.click()
    round_trip(page)
    expect(page.locator("#tags .lf-done")).to_have_attribute("aria-pressed", "true")


def test_a_choice_asked_in_a_thread_answers_on_its_card(browser, serve):
    """A choice the agent asks in a thread that isn't drawn stands on its On Me card,
    in the message that asks it. With the card focused, digits pick its options, and
    the pick is the same action a pick in the thread records. Done then names the
    option, after the view is put away and after a reload, while the thread stays
    undrawn."""
    url = serve(leaf_page("ship plan", '<h1 id="title">Ship plan</h1>'))
    # As `leaf thread create` writes a message holding HTML.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "text": "Ship on Friday?\n\n"
            '<lf-options id="ship">'
            '<lf-option id="ship-friday" label="Ship Friday"><strong>Ship Friday</strong></lf-option>'
            '<lf-option id="ship-wait" label="Wait a week"><strong>Wait a week</strong></lf-option>'
            "</lf-options>",
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#ship")).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("ArrowDown")
    card = on_card(page, "widget:ship")
    expect(card).to_be_focused()
    expect(card.locator("#ship-friday .lf-key-badge")).to_have_text("1")
    expect(card.locator("#ship-wait .lf-key-badge")).to_have_text("2")
    # The options themselves, with no second set of choices beside them.
    rendered(page)
    expect(card.locator(".lf-fp-answer:visible")).to_have_count(0)
    with sending(page, "the pick"):
        page.keyboard.press("1")
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["widget"], event["action"]) == (
        "action",
        "ship",
        "choose",
    ), event
    assert event["detail"]["value"] == ["ship-friday"], event
    expect(card.locator(".lf-fp-said")).to_have_text("Answered: Ship Friday")

    def done_says():
        open_on_me(page)
        show_done(page)
        expect(card).to_have_attribute("data-lf-list", "done")
        expect(card.locator(".lf-fp-on-says > .lf-fp-value")).to_have_text(
            "Answered: Ship Friday"
        )

    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    done_says()
    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(page.locator("#ship")).to_have_count(0)
    done_says()


def test_a_choice_in_a_thread_the_page_shows_stays_there_with_on_me_open(
    browser, serve
):
    """Where the page shows the thread asking a choice, as a thread on a diff's line
    does, opening On Me leaves the choice in that thread, so nothing below it moves.
    The card draws the message's words and answers with the choice's options, and `1`
    there picks in the thread."""
    url = serve(
        leaf_page(
            "diff choice",
            '<h1 id="title">Review the changed line</h1>'
            '<lf-diff id="patch" source="review-patch"></lf-diff>'
            '<p id="tail">The rollout can proceed once the line is reviewed.</p>',
        )
    )
    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-return "old"\n+return "new"\n',
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
            "text": "Ship on Friday?\n\n"
            '<lf-options id="ship">'
            '<lf-option id="ship-friday" label="Ship Friday"><strong>Ship Friday</strong></lf-option>'
            '<lf-option id="ship-wait" label="Wait a week"><strong>Wait a week</strong></lf-option>'
            "</lf-options>",
        },
    )
    page = open_page(browser, url)
    thread = page.locator("#patch .lf-page-thread")
    expect(thread.locator("#ship")).to_be_visible()
    tail = page.locator("#tail").bounding_box()["y"]
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("ArrowDown")
    card = on_card(page, "widget:ship")
    expect(card).to_be_focused()
    # The card has drawn the message, which is when it could take the choice.
    expect(card.locator(".lf-fp-asked .lf-msg")).to_contain_text("Ship on Friday?")
    expect(card.locator("#ship")).to_have_count(0)
    expect(thread.locator("#ship")).to_be_visible()
    assert page.locator("#tail").bounding_box()["y"] == tail
    expect(card.get_by_role("button", name="Ship Friday", exact=True)).to_be_visible()
    with sending(page, "the pick"):
        page.keyboard.press("1")
    expect(thread.locator("#ship-friday")).to_have_attribute("selected", "")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_thread_choice_s_card_shows_the_choice_once_as_its_thread_opens_and_closes(
    request, serve, engine
):
    """While On Me stands open, a margin card opening on the thread that asks a choice
    takes the choice from On Me's card, and closing it may leave the choice there. The
    card shows the choice once throughout: the options themselves while its drawing of
    the message holds them, else its choices, never both and never neither. Firefox can
    keep the choices hidden after the choice leaves the card under a rule asking where
    the choice stands (notes/browser-support.md, "A `:has()` subject left unrestyled when
    its match moves out, in Firefox")."""
    url = serve(
        leaf_page(
            "anchored choice",
            '<h1 id="title">Ship plan</h1>'
            '<p id="risk">The migration has run on staging twice without a failure.</p>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "anchor": {"section": "risk"},
            "text": "Ship on Friday?\n\n"
            '<lf-options id="ship">'
            '<lf-option id="ship-friday" label="Ship Friday"><strong>Ship Friday</strong></lf-option>'
            '<lf-option id="ship-wait" label="Wait a week"><strong>Wait a week</strong></lf-option>'
            "</lf-options>",
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1440, 900)
    view = open_on_me(page)
    card = on_card(page, "widget:ship")
    margin = page.locator(".lf-margin-preview")

    def shown():
        return card.evaluate("""card => ({
          options: Boolean(card.querySelector('#ship')?.checkVisibility()),
          choices: [...card.querySelectorAll('.lf-fp-answer')]
            .filter((choice) => choice.checkVisibility()).length,
        })""")

    expect(card.locator("#ship")).to_be_visible()
    rendered(page)
    assert shown() == {"options": True, "choices": 0}
    # The walk opens the thread's margin card beside the passage, On Me still open.
    page.keyboard.press("m")
    expect(margin.locator("#ship")).to_be_visible()
    expect(view).to_be_visible()
    assert shown() == {"options": False, "choices": 2}
    page.keyboard.press("Escape")
    expect(margin.locator("#ship")).to_be_hidden()
    expect(view).to_be_visible()
    assert shown() in (
        {"options": True, "choices": 0},
        {"options": False, "choices": 2},
    ), shown()


# Two decisions, the first under a heading a thread can be anchored on.
TWO_DECISIONS_PAGE = leaf_page(
    "two decisions",
    """<h1 id="title">Review</h1>
<lf-group id="timeline-ask" label="Land the timeline prototype?"><h2 id="timeline-ask-h">Land the timeline prototype?</h2>
<lf-options id="timeline">
  <lf-option id="tl-land">Land it</lf-option>
  <lf-option id="tl-keep">Keep it on its branch</lf-option>
</lf-options></lf-group>
<lf-group id="ship-ask" label="Ship on Friday?"><h2 id="ship-ask-h">Ship on Friday?</h2>
<lf-options id="ship">
  <lf-option id="ship-friday">Ship Friday</lf-option>
  <lf-option id="ship-wait">Wait a week</lf-option>
</lf-options></lf-group>""",
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
    one place with the decision: `m` stops there once and On Me draws one card, the
    decision's, carrying the answer. Choosing on the card keeps the answer there with
    its Reply, rather than moving it to a card of its own above."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    for decision, at in [("timeline-ask", 1), ("ship-ask", 2), ("timeline-ask", 1)]:
        page.keyboard.press("m")
        expect_walk_position(page, f"{at} of 2 waiting on me")
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
        view.locator(f".lf-fp-on-item[data-lf-key='message:{reply}']")
    ).to_be_visible()


def test_a_decision_answered_on_the_page_keeps_the_answer_it_carries_listed(
    browser, serve
):
    """Answered on the page, a decision moves off On Me in the press's own task, and its
    row keeps the agent's answer it carries until the server's reading of the choice
    moves that answer, so nothing it carried drops out of the queues in between."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    expect(page.locator(".lf-fp-leaf .lf-fp-badge")).to_have_text("2")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#tl-land").click()
    holding(page, held, 1, "the held choice")
    queues = """async () => {
      const queues = (await window.__lfWidgetApi()).readQueues();
      const rows = (list) => list.map((row) => [row.id, row.also]);
      return {on_user: rows(queues.on_user), done: rows(queues.done)};
    }"""
    held_queues = page.evaluate(queues)
    assert held_queues["on_user"] == [["widget:ship", []]]
    assert ["widget:timeline", [f"message:{reply}"]] in held_queues["done"]
    expect(page.locator(".lf-fp-leaf .lf-fp-badge")).to_have_text("1")
    held[0].continue_()
    page.unroute("**/api/event")


def test_an_answer_about_two_decisions_stays_on_the_card_that_carried_it(
    browser, serve
):
    """A thread about a section holding two decisions rides on the first; once that one
    is answered the server moves it to the second, but the open view keeps it on the
    card the user answered, drawn once."""
    source = TWO_DECISIONS_PAGE.replace(
        '<lf-group id="timeline-ask"',
        '<section id="both-outer"><lf-group id="timeline-ask"',
    ).replace(
        "Wait a week</lf-option>\n</lf-options></lf-group>",
        "Wait a week</lf-option>\n</lf-options></lf-group></section>",
    )
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
    """Once the user answers a decision on its card, the agent may resolve the thread
    of the question it carries as settled (`waiting`). The open view keeps the
    question on that card and lists it in Done no second time, so its message is
    drawn once."""
    url = serve(TWO_DECISIONS_PAGE)
    _, reply = thread_about_the_timeline(serve.page_dir)
    page = open_page(browser, url)
    view = open_on_me(page)
    carrier = on_card(page, "widget:timeline")
    carrier.get_by_role("button", name="Land it").click()
    told(page)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Claude", "parent": reply},
    )
    told(page)
    expect(view.locator(".lf-fp-asked")).to_have_count(1)
    expect(carrier.locator(".lf-fp-asked")).to_contain_text("Previews added")
