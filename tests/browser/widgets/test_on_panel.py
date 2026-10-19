"""On me in the floating panel: the cards that name each open and answered item, their
identity and order, and what an answered one says."""

import pytest
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_ITEMS_IN_ORDER,
    CHANGE_SHAPES_PAGE,
    ITEM_WITH_CONTEXT_PAGE,
    ITEMS_PAGE,
    ON_ITEM_SAYS,
)
from render_harness import (
    PANEL,
    expect_items_answered,
    leaf_page,
    open_page,
    panel_settled,
    post_event,
    resized,
    round_trip,
)

pytestmark = pytest.mark.shifts_unsurveyed

ON_ME = '.lf-fp-view[data-view="queue"]:not([data-leaving])'


def open_on_me(page):
    """Open On me by its mark, unless it stands open, and return its view."""
    if page.locator(PANEL).get_attribute("data-open") != "queue":
        page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    return page.locator(ON_ME)


def on_card(page, at):
    """The On me card for the item `at` names, such as `widget:sug-refill`."""
    return page.locator(f'{ON_ME} .lf-fp-on-item[data-key=\'["widget","{at}"]\']')


def test_on_me_lists_open_and_answered_items(browser, serve):
    """The panel's On me mark lists every open item under On me, in document order, and
    every answered one under Done with its current answer, so the user can review and
    revise. A twelfth widget joins by declaring x-awaits.

    A closed view holds no cards at all: they are the open view's rendering, the mark's
    count is the closed view's, and a hidden list of buttons is a set of controls no
    user can press — which the press sweep sees as the page's control set changing
    under it."""
    page = open_page(browser, serve(ITEMS_PAGE))
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

    # The item leads with its authored heading rather than the first option's answer.
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
    expect_items_answered(page, "2/5")
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


def test_an_answered_items_words_are_its_widgets_semantic_state(browser, serve):
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
    expect_items_answered(page, "4/4")
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


def test_item_cards_keep_identity_and_publisher_order_when_the_live_dom_moves(
    browser, serve
):
    """A keyed card follows the published document, not later presentation DOM edits."""
    page = open_page(browser, serve(ITEMS_PAGE))
    open_on_me(page)
    cards = page.locator(f"{ON_ME} .lf-fp-on-item")
    expect(cards).to_have_count(len(ALL_ITEMS_IN_ORDER))
    order = [
        '["widget","widget:live-question"]',
        '["widget","widget:sug-refill"]',
        '["widget","widget:t-baffles-review"]',
        '["widget","widget:t-bath-choice"]',
        '["widget","widget:honored"]',
    ]

    page.evaluate(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          window.__lfReadItemPresentation = readApplicationPresentation;
          const cards = [...document.querySelectorAll(
            '.lf-fp-view[data-view="queue"] .lf-fp-on-item')];
          window.__lfItemCards = new Map(cards.map(card => [card.dataset.key, card]));
          const honored = document.querySelector('#honored-decision');
          document.querySelector('#live-question-decision').before(honored);
          window.__lfItemCards.get('["widget","widget:sug-refill"]').focus();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadItemPresentation().pending.length === 0")
    assert cards.evaluate_all("items => items.map(item => item.dataset.key)") == order
    assert cards.evaluate_all(
        "items => items.every(item => window.__lfItemCards.get(item.dataset.key) === item)"
    )
    sug_refill = on_card(page, "widget:sug-refill")
    expect(sug_refill).to_be_focused()

    # Removing a presentation node does not rewrite the application inventory. The
    # route and its keyed card remain exactly as they were published.
    page.evaluate(
        """() => {
          document.querySelector('#sug-refill').remove();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadItemPresentation().pending.length === 0")
    expect(sug_refill).to_be_focused()
    assert cards.evaluate_all("items => items.map(item => item.dataset.key)") == order
    assert cards.evaluate_all(
        "widgets => items.every(item => window.__lfItemCards.get(item.dataset.key) === item)"
    )


def test_a_completed_item_persists_and_on_me_says_its_current_answer(browser, serve):
    """Completion survives a reload, and On me, opened from the keyboard, keeps the
    answered item under Done saying its current answer, which follows a revision."""
    page = open_page(browser, serve(ITEM_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    expect_items_answered(page, "0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect_items_answered(page, "1/1")

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_items_answered(page, "1/1")

    # With nothing on the user, the view opens on an empty list with Done under it; ↓
    # enters the first card there, the item's.
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
    expect_items_answered(page, "1/1")
    open_on_me(page)
    expect(card.locator(".lf-fp-said")).to_contain_text(
        "Answered: Drop the oldest documents"
    )


def test_an_answered_boxless_item_is_taken_back_from_its_card(browser, serve):
    """An accepted deletion leaves no box on the page to arrive at, so On me's Done card
    is where the user takes the decision back: it says what was decided, and its Undo
    restores the change to decide again."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    expect_items_answered(page, "0/4")

    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect_items_answered(page, "1/4")

    open_on_me(page)
    card = on_card(page, "widget:sug-delete")
    expect(card).to_have_attribute("data-list", "done")
    expect(card.locator(".lf-fp-said")).to_contain_text("Answered: Accepted")
    card.get_by_role("button", name="Undo").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect_items_answered(page, "0/4")
