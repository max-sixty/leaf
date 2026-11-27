"""Obligations: how options lay out and answers clear, the keyboard walk and its arrival, the
digit bindings and badges an obligation projects, and the ring around a decision."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    CURRENT_OBLIGATION,
    OBLIGATION_IN_A_CARD_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    OBLIGATIONS_IN_ORDER,
    OBLIGATIONS_PAGE,
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    SHORT_SUGGESTION,
    SUGGESTION_IN_CONTEXT_PAGE,
    answered_comment,
    live_url,
    serve_obligations,
)
from render_cases_layout import SHOT_SRC, SHOTS
from render_cases_navigation import BINDING_BADGE_PAGE, actions
from render_harness import (
    active_digit_bindings,
    available_commands,
    expect_comment_notes,
    expect_obligations_answered,
    holding,
    leaf_page,
    open_page,
    panel_control,
    resized,
    round_trip,
    scroll_settled,
    stamp_page,
    undo,
    wait_for_revision,
    write,
)

from browser.widgets import (
    expect_accept_all,
    observe_live_region,
)
from leaf.source.render_checks import rendered
from leaf_dev.browser import text_field
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


ACROSS_OBLIGATION = """
  <lf-group id="{id}" label="How long should logs be kept?">
    <hgroup><p>Retention</p><h3 id="{id}-h">How long should logs be kept?</h3></hgroup>
    <figure><table id="{id}-figure">
      <thead><tr><th>Store</th><th class="lf-numeric">Daily GB</th></tr></thead>
      <tbody><tr><td>Hot</td><td class="lf-numeric">40</td></tr>
        <tr><td>Warm</td><td class="lf-numeric">120</td></tr></tbody>
    </table></figure>
    <lf-options id="{id}-choice"{across}{width}>
      <lf-option id="{id}-7" label="7 days"><strong>7 days</strong> The cheapest.
        <lf-options id="{id}-nested">
          <lf-option id="{id}-hot" label="Hot only"><strong>Hot only</strong> Drop warm at once.</lf-option>
          <lf-option id="{id}-both" label="Both tiers"><strong>Both tiers</strong> Keep warm a week.</lf-option>
        </lf-options>
      </lf-option>
      <lf-option id="{id}-30" label="30 days"><strong>30 days</strong> Covers every incident review.</lf-option>
      <lf-option id="{id}-90" label="90 days"><strong>90 days</strong> Covers a quarter's audit.</lf-option>
    </lf-options>
    <p>Whichever you pick, the hot tier keeps a day.</p>
  </lf-group>
"""


ACROSS_OBLIGATION_PAGE = leaf_page(
    "options laid across",
    "<h1>Retention</h1>"
    + ACROSS_OBLIGATION.format(id="across", width="", across=" across")
    + ACROSS_OBLIGATION.format(id="down", width="", across=""),
)


ACROSS_WIDE_OPTIONS_PAGE = leaf_page(
    "options laid across the wide measure",
    "<div>"
    + ACROSS_OBLIGATION.format(id="wide", width=' data-width="wide"', across=" across")
    + "</div>",
    layout="sidebar",
)


PICTURED_OBLIGATION = """
  <lf-group id="{id}" label="Should each item say where it sits in the plan?">
    <h3 id="{id}-h">Should each item say where it sits in the plan?</h3>
    <lf-options id="{id}-choice"{width}>
      <lf-option id="{id}-yes" label="Show the goal and step"><strong>Show the goal and step</strong> A line over each item.
        <p><a href="#{id}-yes-picture"><svg id="{id}-yes-picture" class="lf-drawing"
          viewBox="0 0 480 240" width="480" height="240" role="img"
          aria-label="Items under their step">
          <rect width="480" height="240" fill="none" stroke="currentColor" /></svg></a></p>
      </lf-option>
      <lf-option id="{id}-no" label="Leave the list as it is"><strong>Leave the list as it is</strong> Items as today.
        <p><a href="#{id}-no-picture"><svg id="{id}-no-picture" class="lf-drawing"
          viewBox="0 0 480 240" width="480" height="240" role="img" aria-label="Items as today">
          <rect width="480" height="240" fill="none" stroke="currentColor" /></svg></a></p>
      </lf-option>
    </lf-options>
  </lf-group>
"""


PLATE_PACKAGE = {
    "lf-plate": {
        "description": "A project package's picture, under a name the theme never sees.",
        "attributes": {
            "properties": {},
            "required": ["id"],
        },
        "content": "markup",
        "visual": "whole",
    }
}


PLATED_OPTION = """
      <lf-option id="plated-{side}" label="{title}">        <strong>{title}</strong> <lf-plate id="plated-{side}-picture"><p>{title} by week</p></lf-plate>
      </lf-option>"""


CAPTURED_OPTION = """
      <lf-option id="captured-{side}" label="{title}">        <strong>{title}</strong> <a href="{src}"><img id="captured-{side}-picture" src="{src}" alt="{title}"></a>
      </lf-option>"""


ROWED_OPTION = """
      <lf-option id="rowed-{side}">{title}
        <svg id="rowed-{side}-picture" class="lf-drawing" viewBox="0 0 300 60" width="300"
          height="60" role="img" aria-label="{title}">
          <rect width="300" height="60" fill="none" stroke="currentColor" /></svg>
      </lf-option>"""


PICTURED_OBLIGATION_PAGE = leaf_page(
    "options holding their pictures",
    "<h1>Plan context</h1>"
    + PICTURED_OBLIGATION.format(id="pictured", width="")
    + PICTURED_OBLIGATION.format(id="widened", width=' data-width="wide"')
    + PICTURED_OBLIGATION.format(id="across", width=' data-width="wide" across')
    + '<lf-group id="plated" label="Which latency?"><h3 id="plated-h">Which latency?</h3><lf-options id="plated-choice">'
    + PLATED_OPTION.format(side="yes", title="Backend")
    + PLATED_OPTION.format(side="no", title="Frontend")
    + "</lf-options></lf-group>"
    + '<lf-group id="captured" label="Which panel?"><h3 id="captured-h">Which panel?</h3><lf-options id="captured-choice">'
    + CAPTURED_OPTION.format(side="yes", title="Both lines", src=SHOT_SRC["before"])
    + CAPTURED_OPTION.format(side="no", title="One line", src=SHOT_SRC["after"])
    + "</lf-options></lf-group>"
    + '<lf-group id="rowed" label="Which route?"><h3 id="rowed-h">Which route?</h3><lf-options id="rowed-choice">'
    + ROWED_OPTION.format(side="yes", title="Along the fence")
    + ROWED_OPTION.format(side="no", title="Under the lawn")
    + "</lf-options></lf-group>"
    + '<lf-group id="worded" label="Which order?"><h3 id="worded-h">Which order?</h3><lf-options id="worded-choice">'
    + '<lf-option id="worded-yes" label="By owner"><strong>By owner</strong> Grouped.</lf-option>'
    + '<lf-option id="worded-no" label="By age"><strong>By age</strong> As today.</lf-option>'
    + "</lf-options></lf-group>",
)


def test_options_holding_pictures_stand_apart(browser, serve):
    """Joined into one control, a hairline would be the only boundary between one option's
    picture and the next option's title, so a live group whose options hold a picture
    draws them as standalone cards a gap apart, each framed, bare rows and the add field
    as well as titled cards, while a group of words stays one control with hairlines
    between its cells. A
    picture is a drawing, a capture or a widget whose entry declares it draws one
    (`visual`), wrapped in the link that opens it or not.

    The cards read down unless the author asks for `across`, so each picture stands at
    the size its author gave it, in the reading column or a group given `data-width`;
    laid across, the cards keep the same gap between them."""
    media = {SHOT_SRC[name]: data for name, data in SHOTS.items()}
    page = open_page(
        browser,
        serve(PICTURED_OBLIGATION_PAGE, layer_registry=PLATE_PACKAGE, media=media),
    )
    resized(page, 1440, 900)
    page.wait_for_function("[...document.images].every((i) => i.complete)")
    at = page.evaluate(
        """() => Object.fromEntries(
          ['pictured', 'widened', 'across', 'plated', 'captured', 'rowed', 'worded'].map((id) => {
            const el = (s) => document.getElementById(`${id}-${s}`);
            const edge = (node) => parseFloat(getComputedStyle(node).borderTopWidth);
            const [yes, no] = ['yes', 'no'].map((s) => el(s).getBoundingClientRect());
            const group = el('choice');
            return [id, {
              tops: [yes, no].map((r) => Math.round(r.top)),
              lefts: [yes, no].map((r) => Math.round(r.left)),
              gap: Math.round(
                no.top >= yes.bottom ? no.top - yes.bottom : no.left - yes.right),
              spacing: parseFloat(getComputedStyle(group).getPropertyValue('--lf-sp-3')),
              edges: {group: edge(group), options: ['yes', 'no'].map((s) => edge(el(s))),
                      add: edge(group.shadowRoot.querySelector('.lf-another'))},
              pictures: ['yes', 'no'].map((s) =>
                Math.round(el(`${s}-picture`)?.getBoundingClientRect().width ?? 0)),
            }];
          }))"""
    )
    pictured = ("pictured", "widened", "across", "plated", "captured", "rowed")
    for id in pictured:
        assert at[id]["edges"] == {"group": 0, "options": [1, 1], "add": 1}, (id, at)
        assert at[id]["gap"] == at[id]["spacing"], (id, at)
    assert at["worded"]["edges"] == {"group": 1, "options": [0, 0], "add": 0}, at
    assert at["worded"]["gap"] == 1, at
    for id in ("pictured", "widened", "plated", "captured", "rowed", "worded"):
        assert at[id]["tops"][0] < at[id]["tops"][1], (id, at)
        assert at[id]["lefts"][0] == at[id]["lefts"][1], (id, at)
    assert at["across"]["tops"][0] == at["across"]["tops"][1], at
    for id in ("pictured", "widened"):
        assert at[id]["pictures"] == [480, 480], at
    assert at["captured"]["pictures"] == [600, 600], at
    # Apart or joined changes only the frame: a pick fills and rings a card as it does
    # a cell, so it reads among pictures as plainly as among words.
    for id in ("pictured", "worded"):
        page.locator(f"#{id}-yes > strong").click()
        expect(page.locator(f"#{id}-yes")).to_have_attribute("selected", "")
    page.mouse.move(0, 0)
    face = """el => { const s = getComputedStyle(el);
                      return [s.backgroundColor, s.boxShadow]; }"""
    picked = page.locator("#pictured-yes").evaluate(face)
    assert picked == page.locator("#worded-yes").evaluate(face), picked
    assert picked != page.locator("#pictured-no").evaluate(face), picked


ACROSS_GEOMETRY = """(id) => {
  const box = (suffix) => document.getElementById(`${id}-${suffix}`).getBoundingClientRect();
  const cards = ['7', '30', '90'].map(box);
  return {
    figureBottom: box('figure').bottom,
    tops: cards.map((c) => Math.round(c.top)),
    lefts: cards.map((c) => Math.round(c.left)),
    widths: cards.map((c) => Math.round(c.width)),
    nested: ['hot', 'both'].map((s) => Math.round(box(s).top)),
    list: Math.round(box('choice').width),
    obligation: Math.round(document.getElementById(id).getBoundingClientRect().width),
  };
}"""


def test_options_marked_across_lay_across(browser, serve):
    """A group the author marks `across` sets its titled options side by side in columns
    of one width, under the figure before it, so the question, its figure and every
    option share a window. Where the row can't hold them all, they stack one to a row
    rather than leaving a card alone on a second. Where the heading sits, in an hgroup
    after an eyebrow, and a paragraph after the list change nothing. The arrangement
    belongs to the group marked: a group nested in one of its options keeps its options
    one to a row, and the same obligation, figure and all, keeps its cards reading down
    without `across`."""
    page = open_page(browser, serve(ACROSS_OBLIGATION_PAGE))
    resized(page, 1440, 900)
    wide = page.evaluate(ACROSS_GEOMETRY, "across")
    assert len(set(wide["tops"])) == 1, wide
    assert wide["tops"][0] >= wide["figureBottom"], wide
    assert wide["lefts"] == sorted(set(wide["lefts"])), wide
    assert wide["nested"][0] < wide["nested"][1], wide
    down = page.evaluate(ACROSS_GEOMETRY, "down")
    assert down["tops"] == sorted(set(down["tops"])), down
    assert len(set(down["lefts"])) == 1, down
    # Two of the three would fit across at this width.
    resized(page, 700, 900)
    middle = page.evaluate(ACROSS_GEOMETRY, "across")
    assert middle["tops"] == sorted(set(middle["tops"])), middle
    assert len(set(middle["lefts"])) == 1, middle


def chipped_obligation(id, cards):
    """An obligation framing a drawing, its titled cards laid across; each card is
    (chips, title, attributes), its chips written before its title."""
    options = "".join(
        f'<lf-option id="{id}-{n}" label="{title}"{attributes}>'
        + "".join(f'<small class="lf-tag">{chip}</small>' for chip in chips)
        + f"<strong>{title}</strong><p>Its consequence.</p></lf-option>"
        for n, (chips, title, attributes) in enumerate(cards)
    )
    return (
        f'<lf-group id="{id}" label="Which fix first?"><h3 id="{id}-h">Which fix first?</h3>'
        '<svg class="lf-drawing" viewBox="0 0 480 60" role="img" aria-label="Loss by fix">'
        '<rect width="480" height="60" fill="none" stroke="currentColor" /></svg>'
        f'<lf-options id="{id}-choice" across>{options}</lf-options></lf-group>'
    )


CHIPPED_CARDS_PAGE = leaf_page(
    "cards laid across opening with chips",
    "<h1>Heat loss</h1>"
    + chipped_obligation(
        "some",
        [
            ([], "Seal the hatch", " recommended"),
            ([], "Glaze the bay", ""),
            (["risky"], "Insulate the floor", " selected"),
        ],
    )
    + chipped_obligation(
        "all",
        [
            (
                ["£180", "one afternoon", "needs the installer"],
                "Seal the hatch",
                " recommended",
            ),
            (["£1,180"], "Glaze the bay", ""),
            (["risky"], "Insulate the floor", ""),
        ],
    ),
)


@pytest.mark.parametrize(
    ("engine", "rows"),
    [("browser", ("some",)), ("firefox_browser", ("some", "all"))],
)
def test_cards_laid_across_align_their_titles_whatever_chips_open_them(
    request, serve, engine, rows
):
    """Cards side by side read as one comparison, so each title stands on one line
    across the row whether its card opens with chips, with none, with the "selected"
    state beside them, or with the recommended badge in its corner. A card whose chips
    wrap to several lines moves its neighbours' contents down with it, which needs
    baseline content-alignment: Chromium lacks it, so there only chips that fit beside
    the state seat keep the row aligned (`notes/browser-support.md`)."""
    page = open_page(request.getfixturevalue(engine), serve(CHIPPED_CARDS_PAGE))
    resized(page, 1440, 900)
    at = page.evaluate(
        """(rows) => Object.fromEntries(rows.map((id) => {
          const cards = [...document.querySelectorAll(`#${id}-choice > lf-option`)];
          const top = (card, part) =>
            Math.round(card.querySelector(`:scope > ${part}`).getBoundingClientRect().top);
          return [id, {
            cards: cards.map((card) => Math.round(card.getBoundingClientRect().top)),
            titles: cards.map((card) => top(card, 'strong')),
          }];
        }))""",
        list(rows),
    )
    for id in rows:
        row = at[id]
        assert len(set(row["cards"])) == 1, f"{id}: the cards share a row: {row}"
        assert len(set(row["titles"])) == 1, f"{id}: titles misaligned: {row}"


def test_options_laid_across_fill_the_wide_measure_they_ask_for(browser, serve):
    """The column bounds a line of text, and no card's line is wider than its column, so
    options laid across and granted the wide measure lay their cards under all of it,
    inside the question's ring, rather than at the column beside an empty strip. Room
    for more columns than it has options holds no empty column beside them: the three
    cards share the whole row."""
    page = open_page(browser, serve(ACROSS_WIDE_OPTIONS_PAGE))
    resized(page, 1726, 900)
    at = page.evaluate(ACROSS_GEOMETRY, "wide")
    assert at["list"] > 720, at
    assert at["obligation"] >= at["list"], at
    assert len(set(at["tops"])) == 1, at
    # The group's frame takes 2px of its width, and each hairline between cards 1px.
    hairlines = len(at["widths"]) - 1
    assert abs(sum(at["widths"]) - (at["list"] - 2 - hairlines)) <= 2, at


def test_ideas_shortlist_survives_revision_and_can_reopen(browser, serve):
    """Ordinary choices retain the implementation set and a reversible Done."""
    example = named_source("ideas-to-implement")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, live_url(serve(example)), context=context)
    choices = page.locator("#ideas-shortlist")

    first = page.locator("#idea-shared-filters .lf-pick")
    first.focus()
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#idea-shared-filters")).to_have_attribute("selected", "")
    choices.get_by_text("Export the filtered table", exact=True).tap()
    round_trip(page)
    expect(page.locator("#idea-csv-export")).to_have_attribute("selected", "")

    done = choices.get_by_role(
        "button", name="Done: these picks are complete", exact=True
    )
    done.tap()
    round_trip(page)
    expect_obligations_answered(page, "1/1")

    revised = example.read_text().replace("One API", "A permission-checked API")
    wait_for_revision(
        page, stamp_page(serve.page_dir, revised, "Clarify export scope")["revision"]
    )
    expect(page.locator("#idea-shared-filters")).to_have_attribute("selected", "")
    expect(page.locator("#idea-csv-export")).to_have_attribute("selected", "")

    choices.get_by_role(
        "button", name="Take back Done: reopen these options", exact=True
    ).tap()
    round_trip(page)
    expect_obligations_answered(page, "0/1")
    choices.get_by_text("Export the filtered table", exact=True).tap()
    round_trip(page)
    expect(page.locator("#idea-csv-export")).not_to_have_attribute("selected", "")
    undo(page)
    round_trip(page)
    expect(page.locator("#idea-csv-export")).to_have_attribute("selected", "")
    done.tap()
    round_trip(page)
    expect_obligations_answered(page, "1/1")


def test_clearing_an_answer_reopens_its_obligation(browser, serve):
    """An answer verb with an empty recorded value leaves its obligation unanswered."""
    html = leaf_page(
        "obligation after a cleared pick",
        """
<lf-group id="release-decision" label="Ship this release?"><h1 id="release-decision-h">Ship this release?</h1>
  <lf-options id="release-options">
    <lf-option id="release-ship">Ship it</lf-option>
    <lf-option id="release-hold">Hold it</lf-option>
  </lf-options>
</lf-group>
""",
    )
    page = open_page(browser, serve(html))
    pick = page.locator("#release-ship .lf-pick")

    pick.click()
    round_trip(page)
    expect_obligations_answered(page, "1/1")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    pick.click()
    holding(page, held, 1, "the cleared selection")
    # The pick clears under the user at once; whether that leaves the obligation unanswered
    # is the log's reading.
    expect(page.locator("#release-ship")).not_to_have_attribute("selected", "")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_obligations_answered(page, "0/1")


def test_the_obligation_reading_counts_completed_obligations_against_the_active_total(
    browser, serve
):
    """Two semantic readings, collected from declarations rather than from any tag.

    A count that queried `lf-suggestion:not([data-lf-state])` would be perfect for
    suggestions, and silently nothing for every other thing a page waits on. What
    makes an instance an obligation is the entry's own attribute condition, and the entry
    explicitly names which state verbs answer it — so this page's five active obligations are
    one the user's logged pick answers, a live question, a change nobody has decided, and
    two explicit questions nested in tasks.

    The rest of the page is every way of not being one, and each is a way of getting
    it wrong: a group the author has settled, one that takes no picks at all, an
    exhibited decision inside a lf-sample, and a milestone at `blocked`, which is the same
    word on a widget whose entry does not declare it."""
    page = open_page(browser, serve_obligations(serve))
    expect_obligations_answered(page, "1/5")
    # The blanket answer counts the same list, narrowed to the one kind that declares
    # a verb for it, so the two numbers cannot describe different sets.
    expect_accept_all(page, 1)

    # Answering advances the numerator without erasing the denominator. A pick is state
    # the page itself carries, so the count follows the click; the suggestion's outcome
    # is in the log alone, so that one follows the round trip.
    page.locator("#lq-token").click()
    expect_obligations_answered(page, "2/5")
    page.locator(
        "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
    ).click()
    expect_obligations_answered(page, "3/5")
    expect_accept_all(page, 0)

    # And clearing the pick asks again: an empty answer is no answer, which only a
    # reading of what the page carries can say.
    page.locator("#lq-token").click()
    expect_obligations_answered(page, "2/5")


def test_a_key_walks_the_page_s_open_obligations(browser, serve, subtests):
    """t/T step the open threads; m/M step the things the page is waiting on the user
    for. The category letter stays under one finger: lowercase advances and Shift goes
    back. Both walks repeat when held because walking often takes several presses.
    Both come round from either end to the other, so a press past the last obligation carries
    on from the first.

    The landing is marked on the obligation and stands the user on it, which is the same
    element the scroll has just brought to the top of the window — a walk that landed
    the control instead would put them on whatever the decision's context and evidence
    had pushed off the bottom of the screen. Its contributed actions are directly
    addressable there; the controls themselves remain the next Tab stops."""
    page = open_page(browser, serve_obligations(serve))
    expect_obligations_answered(page, "1/5")

    with subtests.test("the obligation stood on survives the window losing focus"):
        # Another app taking key focus for a moment, such as macOS verifying a newly
        # installed binary, blurs the obligation the user is located on but leaves it the
        # document's focused area, and the browser puts them back on it when the window
        # returns. The tab stop the walk lent the obligation is held through that blur.
        # Taking it back would make the obligation unfocusable while focused, the browser
        # would drop the user to the body, and the window would return without preserving
        # their current location.
        #
        # Headless Playwright cannot take system focus from its window, so the test
        # delivers the platform's blur at the obligation while it stays the focused area,
        # which is what the window losing focus does.
        first = page.locator(f"#{OBLIGATIONS_IN_ORDER[0]}")
        page.keyboard.press("m")
        expect(first).to_be_focused()
        first.evaluate("ask => ask.dispatchEvent(new FocusEvent('blur'))")
        expect(first).to_be_focused()
        expect(first).to_have_attribute("tabindex", "-1")

        # Moving off within the page still gives the stop back.
        page.keyboard.press("m")
        expect(page.locator(f"#{OBLIGATIONS_IN_ORDER[1]}")).to_be_focused()
        expect(first).not_to_have_attribute("tabindex", re.compile(".*"))

    # Off the walk and back at the page's start, so it starts from its first stop.
    page.locator("#h").click()
    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    expect(page.locator(CURRENT_OBLIGATION)).to_have_count(0)

    walked = []
    for expected in [*OBLIGATIONS_IN_ORDER, OBLIGATIONS_IN_ORDER[0]]:
        page.keyboard.press("m")
        # The ring is painted from the focus, in the frame after the press, so waiting
        # for it on the obligation this press stepped to is both the wait and the assertion —
        # a bare count would pass on the ring an earlier press left in place.
        expect(page.locator(f"#{expected}[data-lf-obligation]")).to_have_count(1)
        # And exactly one decision wears it, the user located in one place at a time.
        expect(page.locator(CURRENT_OBLIGATION)).to_have_count(1)
        # Walking changes the ring and not the durable progress count.
        expect_obligations_answered(page, "1/5")
        walked.append(page.evaluate("document.activeElement.id"))
    assert walked == [
        *OBLIGATIONS_IN_ORDER,
        OBLIGATIONS_IN_ORDER[0],
    ], f"the walk landed on something else: {walked}"

    # And back from the first, round past its edge to the last. The step off a suggestion is
    # measured from the suggestion rather than from the ✓ Accept holding the focus —
    # that row is hoisted out into the page margin as a sibling of the block it decides,
    # so a walk reading it where it hangs would step back onto the change the user is
    # located on.
    for expected in reversed(OBLIGATIONS_IN_ORDER):
        page.keyboard.press("Shift+m")
        expect(page.locator(f"#{expected}[data-lf-obligation]")).to_have_count(1)
        expect(page.locator(CURRENT_OBLIGATION)).to_have_count(1)
        expect_obligations_answered(page, "1/5")

    # Every request has an answering control, so the walk never has to leave a borrowed
    # tab stop on an obligation it has left. A generated custom element may be the public
    # role-bearing control itself, so a dash in its tag doesn't mean authored widget
    # paint. Obligation ids are the exact ownership boundary this assertion is about; the
    # current obligation alone may retain the stop that focus is using.
    expect(page.locator(CURRENT_OBLIGATION)).to_have_count(1)
    assert (
        page.evaluate(
            "ids => ids.filter(id => {"
            "  const ask = document.getElementById(id);"
            "  return ask.hasAttribute('tabindex') && !ask.hasAttribute('data-lf-obligation');"
            "})",
            OBLIGATIONS_IN_ORDER,
        )
        == []
    ), "a lent tab stop was left on a decision the user has walked off"

    # The overlay and the dispatcher offer it because there is something to reach.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text("Next On Me")
    page.keyboard.press("Escape")
    assert "m" in available_commands(page).get("queue.walk", [])

    # Leaving the obligation takes the place off the count the way it takes the ring off the
    # page: a click into the prose is the user located nowhere in the list.
    page.locator("#h").click()
    expect(page.locator(CURRENT_OBLIGATION)).to_have_count(0)
    expect_obligations_answered(page, "1/5")

    # An answered decision leaves the walk: deciding the change on its own control is where
    # the user now stands, and the next press reaches what followed it rather than the
    # change they have just settled. The control the user answered from keeps the
    # focus. It leaves the open walk while the completed/total count advances.
    page.locator(
        "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
    ).click()
    expect_obligations_answered(page, "2/5")
    page.keyboard.press("m")
    expect(page.locator("#t-baffles-decision[data-lf-obligation]")).to_have_count(1)
    expect(page.locator("#t-baffles-decision")).to_be_focused()
    expect_obligations_answered(page, "2/5")


def test_an_obligation_arrival_starts_with_the_context_that_frames_it(browser, serve):
    """The decision is the question's whole reading region, not only its answer control.

    Were an options group both the state owner and the navigation target, then when the
    heading, premise, and evidence stood immediately above it, `m` would centre the
    options and make the user scroll backward before they could answer. The group the
    author names round the question encodes that broader unit while the nested
    `awaits` widget still owns the action: the walk rings the region, aligns its
    opening at the window's head, and stands the user on it.

    On it, and not on the control that answers it. The scroll puts the region's opening
    at the top of the window and the answering control is as far down as the context
    and evidence are long, so a walk landing on the control would tell the user to look
    at one thing while located on another they could not see, and their next Space
    would work it. The picks are the next Tab stops instead, which is what a
    stop at `tabindex: -1` on the region buys: it keeps its place in document order and
    everything inside the decision comes after it.
    """
    page = open_page(browser, serve(OBLIGATION_WITH_CONTEXT_PAGE))
    # Short enough that even the pick in the card's compact header falls under the
    # panel's band at the window's foot once the decision's opening is at its head,
    # which is the shape the fault has: the walk cannot both show the question and
    # stand the user on its answer.
    resized(page, 900, 230)

    # The options really do begin below context, and enough page follows the region for
    # aligning its start to be possible. Without either condition, centring the inner
    # widget could happen to look like the requested arrival.
    before = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          return {context: options.top - ask.top,
                  room: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight};
        }"""
    )
    assert before["context"] > 100, (
        "the fixture has no meaningful context above the options"
    )
    assert before["room"] > 500, "the page has no room to put the decision at its start"

    page.keyboard.press("m")
    expect(page.locator("#storage-decision")).to_be_focused()
    expect(page.locator("#storage-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )
    expect(page.locator("#storage-options")).not_to_have_attribute(
        "data-lf-obligation", "1"
    )
    scroll_settled(page)
    # Where the user was left is on the screen the walk has just arranged, and the pick
    # the walk could stand them on instead is the measurement that says the two cannot
    # both be.
    position = page.evaluate(
        """async () => {
          const box = document.activeElement.getBoundingClientRect();
          const pick = document.querySelector('#storage-options > lf-option')
            .shadowRoot.querySelector('.lf-pick')
            .getBoundingClientRect();
          const foot = (await window.__lfWidgetApi()).landingInsets(document.scrollingElement).bottom;
          return {top: box.top, pick: pick.top, height: innerHeight - foot};
        }"""
    )
    assert position["pick"] > position["height"], (
        f"the first pick is on screen at this size, so focusing it would have been no "
        f"worse than focusing the obligation and nothing below is evidence: {position}"
    )
    assert 0 <= position["top"] < position["height"], (
        f"the walk left the user located off the screen it had just scrolled: "
        f"{position}"
    )
    landed = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          const clear = parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)
            + parseFloat(getComputedStyle(document.getElementById('storage-decision'))
              .scrollMarginTop);
          return {obligation: ask.top, options: options.top, clear};
        }"""
    )
    assert abs(landed["obligation"] - landed["clear"]) <= 2, (
        f"the obligation starts at {landed['obligation']:.1f}px instead of the landing band's top and its "
        f"ring's room at {landed['clear']:.1f}px"
    )
    assert landed["options"] > landed["obligation"] + 100, (
        "the arrival did not leave the obligation's context above its options"
    )

    # Tab remains the complementary route into the widget's controls. Read after the
    # landing above, because a Tab onto a control below the fold scrolls to it and would
    # take the arrival's own geometry with it. The obligation action context remains the same;
    # its key badges may move to the shared chrome when Linux font metrics leave a local
    # badge clipped, but the controls retain the same semantic routes.
    page.keyboard.press("Tab")
    expect(page.locator("#storage-options .lf-pick").first).to_be_focused()
    picks = page.locator("#storage-options .lf-pick")
    expect(picks.nth(0)).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 1"
    )
    expect(picks.nth(1)).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 2"
    )

    # And nothing of the borrowed stop is left behind: PAGE_PAINT_ATTRIBUTES is the whole
    # of what the runtime may leave on an author's element, and `tabindex` is not in it.
    page.keyboard.press("Escape")
    expect(page.locator("#storage-decision")).not_to_have_attribute("tabindex", "-1")


def test_the_obligation_itself_binds_each_contributed_action(browser, serve):
    """m lands semantic focus on the obligation; digits work its exact action list there.

    The list is contributed by the decision widget rather than inferred from generated
    descendants: options own controls inside the obligation, while a suggestion's margin entries are
    hoisted into the shared margin. Each widget declares the aliases forwarded by
    the keyboard layer; a digit activates the original command without first moving
    focus into the widget.
    """
    page = open_page(browser, serve_obligations(serve))
    resized(page, 900, 900)

    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    expect(
        page.locator(
            "#live-question > lf-option .lf-key-badge[data-lf-binding-badge]"
        )
    ).to_have_text(["1", "2"])

    page.keyboard.press("2")
    expect(page.locator("#lq-token")).to_have_attribute("selected", "")
    round_trip(page)
    expect_obligations_answered(page, "2/5")

    page.keyboard.press("m")
    expect(page.locator("#sug-refill")).to_be_focused()
    assert active_digit_bindings(page) == "1–2"
    expect(
        page.locator(
            "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
        )
    ).to_have_attribute("aria-keyshortcuts", "1")
    expect(
        page.locator(
            "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=reject]"
        )
    ).to_have_attribute("aria-keyshortcuts", "2")
    page.keyboard.press("2")
    round_trip(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")


def test_obligation_contextual_bindings_are_independent_of_widget_bindings(
    browser, serve
):
    """An obligation digit aliases a command without replacing its focused widget binding."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
          const suggestion = document.getElementById('sug');
          const source = document.createElement('span');
          const inspect = document.createElement('button');
          inspect.id = 'inspect-action';
          inspect.textContent = 'Inspect';
          source.append(inspect);
          suggestion.append(source);
          source.lfCommands = { title: 'Suggestion action', rows: [
            {
              id: 'test.inspect',
              keys: ['x', 'y'], contextKeys: ['3'],
              control: inspect, bindingBadge: null,
              label: 'I',
              decision: true,
              title: 'Inspect',
              line: 'Inspect',
              run: () => { inspect.dataset.activated = '1'; },
            },
          ] };
          source.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
        }"""
    )

    # The source scope keeps its intrinsic presentation in the global reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    inspect_reference = page.locator(
        '.lf-command-reference [role=option][data-lf-command="test.inspect"]'
    )
    expect(inspect_reference.locator("kbd")).to_have_text("I")
    expect(inspect_reference.locator(".lf-binding-sequence")).to_have_attribute(
        "aria-label", "I"
    )
    page.keyboard.press("Escape")

    inspect = page.get_by_role("button", name="Inspect")
    page.keyboard.press("m")
    expect(page.locator("#sug")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    expect(inspect).to_have_attribute("aria-keyshortcuts", "3")
    rendered(page)
    assert sorted(
        page.locator(
            ".lf-command-binding-badges .lf-command-binding-badge"
        ).all_text_contents()
    ) == ["1", "2", "3"]

    # The obligation's third route invokes the original command. Once the command's own control
    # is focused, both equivalent intrinsic bindings and the independent obligation digit remain
    # reachable routes to that command.
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    inspect.focus()
    rendered(page)
    assert set(inspect.get_attribute("aria-keyshortcuts").split()) == {"x", "y", "3"}
    assert {"x", "y"} <= set(available_commands(page)["test.inspect"])
    rendered(page)
    assert sorted(
        page.locator(
            ".lf-command-binding-badges .lf-command-binding-badge"
        ).all_text_contents()
    ) == ["1", "2", "3"]
    page.keyboard.press("y")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")

    # A nearer dead declaration removes only x. The route snapshot keeps y rather than
    # collapsing the command's equivalent bindings into whichever one came first.
    page.evaluate(
        """async () => {
          const inspect = document.getElementById('inspect-action');
          inspect.lfCommands = { title: 'Inspect control', rows: [{
            id: 'test.dead-local-x', keys: ['x'],
            title: 'Run an unavailable local command',
            line: 'unavailable local command', when: () => false,
            run: () => { inspect.dataset.deadLocalX = '1'; },
          }] };
          inspect.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
        }"""
    )
    rendered(page)
    assert set(inspect.get_attribute("aria-keyshortcuts").split()) == {"y", "3"}
    reaching = set(available_commands(page)["test.inspect"])
    assert "y" in reaching and "x" not in reaching, reaching
    page.keyboard.press("x")
    expect(inspect).not_to_have_attribute("data-dead-local-x", "1")
    expect(inspect).not_to_have_attribute("data-activated", "1")
    page.keyboard.press("y")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-activated", "1")

    # The complete reference preserves the command's keycap override while its
    # contextual and intrinsic bindings still refer to one command identity.
    page.keyboard.press("?")
    page.keyboard.press("?")
    focused_inspect = page.locator(
        '.lf-command-reference [role=option][data-lf-command="test.inspect"]'
    )
    expect(focused_inspect.locator("kbd")).to_have_text("I")


def test_a_widget_digit_shadows_only_the_matching_obligation_alias(browser, serve):
    """A focused widget digit suppresses its obligation alias without taking other digits.
    A command whose computed title is not text is refused in that command's name."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    page.evaluate(
        """async () => {
          const suggestion = document.getElementById('sug');
          const inspect = document.createElement('button');
          inspect.textContent = 'Inspect';
          suggestion.append(inspect);
          inspect.lfCommands = { title: 'Inspect control', rows: [
            {
              id: 'test.inspect', keys: ['1'], contextKeys: ['3'], control: inspect, label: 'I',
              decision: true, title: 'Inspect', line: 'Inspect',
              run: () => { inspect.dataset.activated = '1'; },
            },
            {
              id: 'test.local-three', keys: ['3'],
              title: 'Run the local third command', line: 'local three',
              run: () => { inspect.dataset.localThree = '1'; },
            },
          ] };
          inspect.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
        }"""
    )

    inspect = page.get_by_role("button", name="Inspect")
    page.keyboard.press("m")
    # The control's own scope names its keys wherever the user is located; the obligation adds
    # the widget's explicitly declared digit that reaches it from the obligation.
    expect(inspect).to_have_attribute("aria-keyshortcuts", "1 3")
    inspect.focus()
    expect(inspect).to_have_attribute("aria-keyshortcuts", "1 3")
    expect(
        page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    ).to_have_text(["2"])
    page.keyboard.press("1")
    expect(inspect).to_have_attribute("data-activated", "1")
    inspect.evaluate("control => delete control.dataset.activated")
    page.keyboard.press("3")
    expect(inspect).to_have_attribute("data-local-three", "1")
    expect(inspect).not_to_have_attribute("data-activated", "1")


def test_an_obligation_alias_runs_the_original_command_in_its_own_scope(browser, serve):
    """A projected digit enters through the widget command's own declaration, and the
    layer it opens declares its own way out.

    Nothing records which press opened the layer: Escape reads the layer standing in
    front of the user, so the widget owning it owns the step that takes it off, and
    that step is the same one whether the digit, the control, or a Tab put the user
    inside."""
    page = open_page(browser, serve(SHORT_SUGGESTION))

    page.evaluate(
        """async () => {
          const suggestion = document.getElementById('sug');
          const control = document.createElement('button');
          control.textContent = 'Configure';
          const layer = document.createElement('div');
          layer.id = 'test-command-layer';
          layer.hidden = true;
          const inside = document.createElement('button');
          inside.textContent = 'Inside configuration';
          layer.append(inside);
          suggestion.append(control, layer);
          control.lfCommands = { title: 'Configuration action', rows: [{
            id: 'test.configure', keys: [], contextKeys: ['3'], control,
            decision: true, title: 'Configure', line: 'configure',
            run: () => { layer.hidden = false; inside.focus(); },
          }] };
          control.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
          inside.lfCommands = { title: 'In the configuration layer', rows: [{
            id: 'test.configure.close', keys: ['Escape'],
            title: 'Close configuration', line: 'close configuration',
            run: () => { layer.hidden = true; control.focus(); },
          }] };
          inside.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
        }"""
    )

    page.keyboard.press("m")
    expect(page.locator("#sug")).to_be_focused()
    page.keyboard.press("3")
    expect(page.get_by_role("button", name="Inside configuration")).to_be_focused()
    assert available_commands(page).get("test.configure.close") == ["Escape"]
    page.keyboard.press("Escape")
    expect(page.locator("#test-command-layer")).to_be_hidden()
    expect(page.get_by_role("button", name="Configure")).to_be_focused()


def test_obligation_action_binding_badges_use_the_available_card_action_seats(
    browser, serve
):
    """The draft route borrows an empty Add seat and moves beside a live Add press.

    The cards share one trailing column. An empty draft has only the route into its
    field, so that badge stands over the hidden Add press, in the digit column every
    card's badge shares. Once content reveals Add and
    focus leaves the field, both actions are available and the route takes the inner
    seat. The field reserves both seats before either face appears.
    """
    page = open_page(browser, serve_obligations(serve))
    resized(page, 900, 900)

    page.keyboard.press("m")
    # Each option's badge in its own shadow root, and the add field's in the group's.
    selector = (
        "#live-question :is(lf-option > [data-lf-form], .lf-another) "
        "> .lf-key-badge[data-lf-binding-badge]"
    )
    item = page.locator(selector)
    expect(item).to_have_count(3)
    # In the order they stand down the group, which the trees they stand in don't keep.
    centers = """nodes => nodes.map(node => {
          const box = node.getBoundingClientRect();
          return {x: box.left + box.width / 2, y: box.top + box.height / 2 + scrollY,
                  right: box.right, text: node.textContent};
        }).sort((a, b) => a.y - b.y)"""
    obligation_centers = item.evaluate_all(centers)
    assert [point["text"] for point in obligation_centers] == ["1", "2", "3"]
    addition = page.locator("#live-question .lf-another")
    submit = addition.locator(".lf-compose-submit")
    empty_submit = submit.evaluate(
        """el => { const box = el.getBoundingClientRect();
                    return {x: box.left + box.width / 2, left: box.left,
                            right: box.right}; }"""
    )
    assert obligation_centers[-1]["x"] == pytest.approx(
        obligation_centers[0]["x"], abs=0.5
    )
    assert empty_submit["left"] < obligation_centers[-1]["x"] < empty_submit["right"]

    page.keyboard.press("Tab")
    focused = page.locator(selector)
    expect(focused).to_have_count(3)
    focused_centers = focused.evaluate_all(centers)
    assert [point["text"] for point in focused_centers] == ["1", "2", "3"]
    assert len(obligation_centers) == len(focused_centers) == 3
    assert len({round(point["x"], 1) for point in obligation_centers[:-1]}) == 1
    for obligation_point, focused_point in zip(
        obligation_centers, focused_centers, strict=True
    ):
        assert obligation_point["x"] == pytest.approx(focused_point["x"], abs=0.5)
        assert obligation_point["y"] == pytest.approx(focused_point["y"], abs=0.5)

    # Add must be ready before the next frame and the next keyboard gesture.
    # Lit may commit in a microtask after the input event has finished bubbling.
    page.evaluate("""() => {
      window.__addEmptyBeforeFrame = new Promise(resolve => {
        document.addEventListener('input', () => requestAnimationFrame(() => {
          resolve(document.querySelector(
            '#live-question .lf-compose-submit').hasAttribute('data-lf-empty'));
        }), {once: true});
      });
    }""")
    write(text_field(addition, name="Another option"), "A fourth option")
    page.keyboard.press("Tab")
    expect(submit).to_be_focused()
    assert page.evaluate("window.__addEmptyBeforeFrame") is False
    binding_badge = addition.locator("> .lf-key-badge[data-lf-binding-badge]")
    expect(binding_badge).to_be_visible()
    expect(submit).to_be_visible()
    badge_box = binding_badge.bounding_box()
    submit_box = submit.bounding_box()
    assert badge_box is not None
    assert submit_box is not None
    # The press remains in the seat the empty badge borrowed. With both actions now live,
    # the write badge takes the adjacent seat at the form's declared action gap.
    assert submit_box["x"] + submit_box["width"] > obligation_centers[0]["right"]
    assert submit_box["x"] + submit_box["width"] / 2 == pytest.approx(
        empty_submit["x"], abs=0.5
    )
    gap = submit_box["x"] - badge_box["x"] - badge_box["width"]
    expected_gap = page.locator("html").evaluate(
        "el => parseFloat(getComputedStyle(el).getPropertyValue('--lf-sp-2'))"
    )
    assert gap == pytest.approx(expected_gap, abs=0.5)
    expect(
        page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    ).to_have_count(0)


def test_obligation_actions_replace_unusable_package_binding_badge_faces(
    browser, serve
):
    """Disconnected, shared, covered, and clipped faces use core binding badges."""
    page = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
           const source = document.getElementById('sug');
           const face = (id, top) => {
             const bindingBadge = document.createElement('span');
             bindingBadge.id = id;
             bindingBadge.className = 'lf-key-badge';
             bindingBadge.style.cssText = `position: fixed; left: 90px; top: ${top}px;`;
             return bindingBadge;
           };
           let nextKey = 3;
           const add = (id, top, bindingBadge) => {
             const control = document.createElement('button');
            control.id = id;
            control.textContent = id;
            control.style.cssText = `position: fixed; left: 560px; top: ${top}px;`;
            source.append(control);
            control.lfCommands = { title: id, rows: [{
               id: `test.${id}`, keys: [], contextKeys: [String(nextKey++)], control, bindingBadge,
              decision: true, title: `Activate ${id}`, line: id,
              run: () => { control.dataset.activated = '1'; },
            }] };
            control.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
          };

           add('disconnected-face', 220, face('detached-binding-badge', 100));
           const shared = face('shared-binding-badge', 120);
          source.append(shared);
          add('shared-face-one', 300, shared);
          add('shared-face-two', 380, shared);
           const covered = face('covered-binding-badge', 200);
          source.append(covered);
          const cover = document.createElement('span');
           cover.id = 'binding-badge-cover';
          cover.style.cssText =
            'position: fixed; left: 90px; top: 200px; width: 24px; height: 24px;' +
            ' z-index: 2; background: black;';
          source.append(cover);
          add('covered-face', 460, covered);
          const clip = document.createElement('span');
          clip.id = 'binding-badge-clip';
          clip.style.cssText =
            'position: fixed; left: 90px; top: 240px; width: 24px; height: 8px;' +
            ' overflow: hidden;';
          const clipped = document.createElement('span');
          clipped.id = 'clipped-binding-badge';
          clipped.className = 'lf-key-badge';
          clipped.style.cssText = 'position: absolute; left: 0; top: 0;';
          clip.append(clipped);
          source.append(clip);
          add('clipped-face', 540, clipped);
        }"""
    )

    # The obligation's bindings are chrome, painted on the frame after the press that enters it.
    page.keyboard.press("m")
    for control, binding in (
        ("#disconnected-face", "3"),
        ("#shared-face-one", "4"),
        ("#shared-face-two", "5"),
        ("#covered-face", "6"),
        ("#clipped-face", "7"),
    ):
        expect(page.locator(control)).to_have_attribute("aria-keyshortcuts", binding)
    expect(page.locator("#shared-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    expect(page.locator("#covered-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    expect(page.locator("#clipped-binding-badge[data-lf-binding-badge]")).to_have_count(
        0
    )
    for binding in ("3", "4", "5", "6", "7"):
        expect(
            page.locator(
                ".lf-command-binding-badges .lf-command-binding-badge",
                has_text=binding,
            )
        ).to_have_count(1)
    # A covered or clipped face's chip takes the face's place, which the widget chose,
    # rather than its control's corner, where a field's chip covered its first words.
    for face, binding in (
        ("#covered-binding-badge", "6"),
        ("#clipped-binding-badge", "7"),
    ):
        seat = page.locator(face).bounding_box()
        chip = page.locator(
            ".lf-command-binding-badges .lf-command-binding-badge", has_text=binding
        ).bounding_box()
        assert abs(chip["x"] + chip["width"] / 2 - seat["x"] - seat["width"] / 2) <= 1
        assert abs(chip["y"] + chip["height"] / 2 - seat["y"] - seat["height"] / 2) <= 1


def test_obligation_binding_badges_do_not_cover_their_key_line(browser, serve):
    """A binding badge that reaches the floating panel's row yields to it."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    # Narrow enough that the panel's row, which stands centred at the window's foot,
    # spans the leading edge the badges stand at.
    resized(page, 480, 520)

    # The first obligation uses titled cards, whose trailing binding badges cannot meet the
    # panel's row. Step to the compact row obligation, where both occupy the leading edge.
    #
    # The walk arrives and then travels, in that order and in one task, so the arrival is
    # the fact each stillness reading is taken behind. Stillness on its own answers the
    # same for a page that has finished travelling and one whose asynchronous reveal has
    # not started it, and the second answer is the one that loses this test: the geometry
    # below is measured where the walk began, the scroll it computes is issued there, and
    # the travel then lands on top of it with the badge back above the bar.
    page.keyboard.press("m")
    expect(page.locator("#cards-decision")).to_be_focused()
    scroll_settled(page)
    page.keyboard.press("m")
    expect(page.locator("#rows-decision")).to_be_focused()
    scroll_settled(page)
    expect(
        page.locator("#rows > lf-option .lf-key-badge[data-lf-binding-badge]")
    ).to_have_text(["1", "2"])
    # Put the second row's badge one pixel into the panel row's band. The first stays a
    # row above it, so a placement pass that reserves the legend keeps one and removes
    # the other. Calculate the scroll from their current boxes rather than pinning the
    # fixture to today's spacing.
    page.evaluate(
        """() => {
          const badges = [...document.querySelectorAll('#rows > lf-option')]
            .map((option) => option.shadowRoot.querySelector(
              '.lf-key-badge[data-lf-binding-badge]'))
            .filter(Boolean);
          const last = badges[badges.length - 1].getBoundingClientRect();
          const line = document.querySelector('.lf-fp-row').getBoundingClientRect();
          scrollTo(0, scrollY + last.top - line.top - 1);
        }"""
    )
    scroll_settled(page)
    expect(
        page.locator("#rows > lf-option .lf-key-badge[data-lf-binding-badge]")
    ).to_have_count(1)
    geometry = page.evaluate(
        """() => {
          const read = node => {
            const box = node.getBoundingClientRect();
            return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
          };
          return {
            line: read(document.querySelector('.lf-fp-row')),
            chips: [...document.querySelectorAll(
              '.lf-command-binding-badges .lf-command-binding-badge, [data-lf-binding-badge]'
            )].filter(node => node.checkVisibility({visibilityProperty: true})).map(read),
          };
        }"""
    )
    assert geometry["chips"], (
        "the fixture did not leave an obligation binding badge on screen"
    )
    assert all(
        chip["right"] <= geometry["line"]["left"]
        or geometry["line"]["right"] <= chip["left"]
        or chip["bottom"] <= geometry["line"]["top"]
        or geometry["line"]["bottom"] <= chip["top"]
        for chip in geometry["chips"]
    ), geometry


def walked_to(page, key, target):
    """Press `key`, then wait for the walk to put focus on `target` and its travel to end.

    The arrival focuses and issues its smooth scroll in one task, but the page's scroll
    position first moves frames later, and `scroll_settled` counts those frames as
    stillness. So the travel must be seen to start before its end is waited for, which
    holds only for a destination the arrival moves the page to.
    """
    before = page.evaluate("document.scrollingElement.scrollTop")
    page.keyboard.press(key)
    expect(page.locator(target)).to_be_focused()
    page.wait_for_function(
        "(before) => document.scrollingElement.scrollTop !== before", arg=before
    )
    scroll_settled(page)


def test_an_arrival_on_a_change_takes_in_the_words_that_explain_it_and_stops_there(
    browser, serve, subtests
):
    """A change to a phrase declares no group, so the block holding it is its region.

    A question's group is its arrival: its name, the context, then the control. A
    suggestion stands mid-sentence, named by its own words, so no group holds it
    (`inline`). Arriving on the change alone would put its own top edge at the
    window's head and take the sentence with it, leaving the user on the change with
    nothing on screen saying what they would be accepting. Leaf reads no heading for
    it: the section's heading stays above the window.
    """
    page = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)

    # The change is below the fold and the page can scroll, or standing still would look
    # like the arrival this asks for.
    assert page.evaluate(
        """() => {
          const box = document.getElementById('sc-sug').getBoundingClientRect();
          const se = document.scrollingElement;
          return box.top > se.clientHeight && se.scrollHeight - se.clientHeight > 500;
        }"""
    ), "the fixture already shows the change on the first screen"

    walked_to(page, "m", "#sc-sug")

    landed = page.evaluate(
        """() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            heading: at('sc-api-heading').top,
            sentence: at('sc-api-why').top,
            change: at('sc-sug').top,
            foot: at('sc-sug').bottom,
            view: document.scrollingElement.clientHeight,
            clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          };
        }"""
    )
    assert abs(landed["sentence"] - landed["clear"]) <= 2, (
        f"the arrival put the sentence holding this change at {landed['sentence']:.1f}px "
        f"rather than at the landing band's top at {landed['clear']:.1f}px"
    )
    assert landed["heading"] < landed["clear"] <= landed["change"], (
        "the arrival reached past the block holding the change to the heading over it"
    )
    assert landed["foot"] <= landed["view"], "the change itself ran off the screen"

    with subtests.test(
        "an obligation already in front of the user is not travelled to"
    ):
        # The press moves the ring and the focus and leaves the page where it stands.
        # Rebuilding a view the user is already looking at is motion that says nothing,
        # and it costs them whatever adjustment they had made within it. The gate reads
        # what the page shows of the obligation rather than what its own box claims.
        #
        # The walk above is the control: it did travel, from a page that opens above
        # the change, so a second press standing still is this gate rather than a walk
        # that never moves the page at all.
        arrived = page.evaluate("() => document.scrollingElement.scrollTop")
        assert arrived > 0, "the walk did not travel to the obligation at all"

        # A little above that arrival: the region's start is still in the window and
        # the change's foot is still on screen, so this is the same view with the user's
        # own adjustment in it.
        page.evaluate("() => document.scrollingElement.scrollBy(0, -40)")
        scroll_settled(page)
        held = page.evaluate("() => document.scrollingElement.scrollTop")
        assert held == arrived - 40, "the page did not take the user's own adjustment"

        # The press's own announcement is the edge this absence stands behind.
        # `goToObligation` travels before it announces, so a live region that has spoken
        # again is a press whose travel has already been decided and begun. Waiting on
        # the scroll alone cannot say that: frames held still before a glide starts read
        # the same as a page that never moved, and only the announcement puts the read
        # behind the decision.
        observe_live_region(page)
        page.keyboard.press("m")  # one obligation, so the walk stays on it
        page.wait_for_function(
            "() => window.__lfLiveRegionChanges.some("
            "words => words.includes('waiting on me'))"
        )
        expect(page.locator(".lf-live")).to_have_text(re.compile(r"waiting on me"))
        assert "" in page.evaluate("window.__lfLiveRegionChanges")
        expect(page.locator("#sc-sug")).to_be_focused()
        scroll_settled(page)
        assert page.evaluate("() => document.scrollingElement.scrollTop") == held, (
            "the walk travelled to an obligation the user could already see"
        )

    with subtests.test("the region an arrival takes in fits above the floating panel"):
        # The region is measured against the landing band. The floating panel's row
        # stands over the window's foot, so a region measured against the whole window
        # would put the sentence at the top of the screen and the change it is chosen
        # for under the row. The window is sized so the sentence fits in the window but not
        # above the panel's band: the arrival lands on the change alone, and the change
        # stays where the user can read it.
        measure = """async () => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          const style = getComputedStyle(document.scrollingElement);
          return {
            span: at('sc-sug').bottom - at('sc-api-why').top,
            foot: at('sc-sug').bottom,
            view: document.scrollingElement.clientHeight,
            top: parseFloat(style.scrollPaddingTop),
            bottom: (await window.__lfWidgetApi()).landingInsets(document.scrollingElement).bottom,
          };
        }"""
        before = page.evaluate(measure)
        assert before["bottom"] > 0, "the fixture has no panel band to land clear of"
        # The region misses the room above the band by a few pixels; the change alone
        # fits.
        resized(page, 900, round(before["span"] + before["top"] + before["bottom"] - 8))
        # Off the change and back to the page's start, so the walk travels again.
        page.locator("#sc-h").click()
        page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
        scroll_settled(page)

        walked_to(page, "m", "#sc-sug")

        landed = page.evaluate(measure)
        assert landed["span"] == pytest.approx(before["span"], abs=1), (
            "the resize reflowed the region, so the window no longer falls between the "
            "two readings of the room"
        )
        assert landed["foot"] <= landed["view"] - landed["bottom"] + 0.5, (
            f"the arrival put the change's foot at {landed['foot']:.1f}px, under the "
            f"foot band that starts at {landed['view'] - landed['bottom']:.1f}px"
        )


def test_an_obligation_inside_a_card_is_brought_into_that_card(browser, serve):
    """The arrival places its group out on the page; the answer may be in a box of its own.

    The placement moves whichever scroller the group belongs to, and for a group on the
    page that is never the card's. So the answer's own box comes into view first, which
    is the one pass that moves a nested scroller. Handing the placement the group alone
    would leave the answer unscrolled in its card, with the ring on a question whose
    control the user can't see, and the walk's next press would repeat the same
    non-arrival.
    """
    page = open_page(browser, serve(OBLIGATION_IN_A_CARD_PAGE))
    resized(page, 900, 500)

    # The card hides the answer to begin with, or the reveal has nothing to do.
    assert page.evaluate(
        """() => {
          const card = document.getElementById('ac-card');
          const box = document.getElementById('ac-pick').getBoundingClientRect();
          return card.scrollHeight > card.clientHeight &&
                 box.top > card.getBoundingClientRect().bottom;
        }"""
    ), "the fixture's card shows the answer already"

    page.keyboard.press("m")
    expect(page.locator("#ac-section")).to_be_focused()
    scroll_settled(page)

    seen = page.evaluate(
        """() => {
          const box = document.getElementById('ac-pick').getBoundingClientRect();
          const card = document.getElementById('ac-card').getBoundingClientRect();
          const view = document.scrollingElement.clientHeight;
          return {
            insideCard: box.top >= card.top - 0.5 && box.bottom <= card.bottom + 0.5,
            onScreen: box.top >= 0 && box.bottom <= view,
          };
        }"""
    )
    assert seen["insideCard"], (
        "the answer is still outside its card's own band, so the card was never scrolled"
    )
    assert seen["onScreen"], "the answer is in its card's band but off the window"


def test_the_obligation_walk_starts_from_where_the_user_is(browser, serve):
    """The walk measures from the user, the way Space page travel measures from the scroll position
    and t/T from the focused thread. A walk that kept an id of its own would start every
    walk the user had not made with this key at the top of the page: scroll halfway
    down and press `m` and you would be taken back past everything you had read, and so
    would anyone who had just selected a paragraph to comment on.

    Reading an obligation is being at it without being on it, so the walk arrives
    there. The panel's On Me tab is no place: pressing it opens On Me and leaves the
    focus in the panel, which holds the user's place on the page, so the walk after it
    steps on from the obligation they stood on rather than restarting. A selected
    passage enters its comment field immediately; while that field stands, letters
    are text rather than page-navigation keys."""
    page = open_page(browser, serve_obligations(serve))

    # A window short enough that reading down the page leaves the top of it behind,
    # which is the whole of what the user has to do to be somewhere.
    resized(page, 900, 400)

    # Scrolled to the change with nothing selected and nothing focused: the change
    # itself, not the question above it nor the decision after it.
    page.locator("#refill-was").evaluate("el => el.scrollIntoView({block: 'start'})")
    page.keyboard.press("m")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-obligation", "1")
    scroll_settled(page)

    # The tab's press opens On Me and takes the focus into the panel, which holds the
    # suggestion as the user's place, so the walk steps on rather than restarting.
    panel_control(page, "queue").click()
    page.keyboard.press("m")
    expect(page.locator("#t-baffles-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )


def test_the_ring_is_one_box_around_the_whole_change(browser, serve):
    """A suggestion is one decision, so it wears one ring, whatever its slots are made of.

    A wrapper that generated no box — the same "take the form your content takes" with
    the box left out — would measure (0,0) at the document's origin, as an element with
    none does, which is not a degenerate answer but a wrong one. Everything that asked
    the wrapper where it was would believe it, so the travel would centre the top of the
    document and a page whose open decisions were all suggestions would answer `m` by
    appearing to do nothing at all.

    Hanging the ring on the pieces instead covers that and says the wrong thing about
    the change: two outlines meeting down the middle of a sentence, or stacked across
    two block slots, read as two boxes touching rather than as the one decision the user is
    located in. So what is asserted here is that the user is taken to the change, and
    that the wrapper alone wears the mark, in one box reaching round both slots."""
    page = open_page(browser, serve_obligations(serve))

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

    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )
    # Where the user now stands, which is what the next press is measured against. The
    # bug takes them to the document's origin, so a scroll that ends *below* where they
    # started is the whole of what says they were carried to the change instead.
    #
    # Said that way rather than as "the change was off screen before the press": that
    # would be true by only a few dozen pixels, a fact about how tall the blocks above the
    # change happen to be, so one more line above it would stop the precondition holding,
    # with nothing wrong anywhere.
    scroll_settled(page)
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the user must have somewhere to have come from"

    page.keyboard.press("m")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-obligation", "1")

    # The condition everything below rests on, stated rather than assumed: put
    # display: contents back on the wrapper and it measures (0,0), the mark paints
    # nothing, and the count further down passes on an element no user can see.
    box = page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    )
    assert box[0] > 40 and box[1] > 10, f"the wrapper drew no box to ring: {box}"

    # The travel is a glide, so the fact to wait on is that it has finished. Both
    # assertions are then about the landing: measured from the wrapper's own rect the
    # change sits at the document's origin, so the user is carried to the top of the
    # page — up from where they stood, with the change still below the fold.
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # What wears the mark: the wrapper, which carries the id every reader of the mark
    # obligations after. Not the slots, and not the empty span the widget prepends to itself to
    # anchor its controls from — a 2px mark of its own beside the change is not the
    # promise.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-obligation]')].map(e => {
      return { what: e.id || e.tagName, fragments: e.getClientRects().length,
               ring: e.hasAttribute('data-lf-projected-location')
                 && getComputedStyle(e).outlineStyle === 'solid' };
    })""")
    assert [m["what"] for m in marks] == ["sug-refill"]
    assert marks[0]["ring"]
    # One fragment, so the outline closes round the change once. An inline box broken
    # around block children has three and draws no visible edge on any of them, which is
    # what a wrapper that only says `inline` gets for a change made of paragraphs.
    assert marks[0]["fragments"] == 1, marks

    # And the box reaches round both slots, which a ring on the pieces could not promise:
    # the user is located in the change, not in half of it.
    assert page.evaluate("""() => {
      const w = document.getElementById('sug-refill').getBoundingClientRect();
      return ['refill-was', 'refill-now'].every(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return r.top >= w.top - 1 && r.bottom <= w.bottom + 1
            && r.left >= w.left - 1 && r.right <= w.right + 1; });
    }"""), "the wrapper's box does not reach round both slots"


def test_the_walk_travels_to_an_obligation_a_page_left_boxless(browser, serve):
    """`display: contents` is one line of CSS, and a page or a project layer can put it
    on anything. Nothing in the shipped vocabulary carries it now, so this case only
    reaches the runtime from outside — which is where the reading has to hold, because
    an element generating no box measures (0,0) at the document's origin and every
    consumer that believes it travels to the top of the page.

    The travel reads where the content paints (shownBox), and the ring hangs on the
    boxes the decision shows through (shownParts) — the same answer an element-anchored
    comment's outline gives, so the walk's mark and the thread's cannot disagree about
    where a boxless decision is. The outermost mark still names the decision, one place for the
    user to be located."""
    # Keep the boxless element's slots in one prose cell. As direct children of
    # main they become separate grid items, so the fixture no longer describes
    # one decision below the preceding question.
    styled = (
        OBLIGATIONS_PAGE.replace(
            '<lf-suggestion id="sug-refill">', '<div><lf-suggestion id="sug-refill">'
        )
        .replace("</lf-suggestion>", "</lf-suggestion></div>", 1)
        .replace(
            "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
        )
    )
    page = open_page(browser, serve(styled))
    resized(page, 900, 400)

    # Asked of what the change paints, since the wrapper itself no longer says: this is
    # the reading the runtime has to take for the travel to land anywhere real. Whole in
    # the window because merely overlapping it is a state the glide passes through.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )
    scroll_settled(page)
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the user must have somewhere to have come from"

    page.keyboard.press("m")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-obligation", "1")
    assert page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    ) == [0, 0], "the page's own style no longer takes the wrapper's box away"
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # The decision and the boxes it shows through wear the mark, the decision outermost — one
    # place to stand, painted where the user can see it.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-obligation]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the mark went somewhere else than the decision and its shown boxes: {marks}"
    expect(page.locator(CURRENT_OBLIGATION)).to_have_count(1)
    # The decision draws no box, so each box it shows through draws the location ring
    # round itself (readings/target-paint.js, `paintLocation`).
    rings = page.evaluate("""() => ['lf-old', 'lf-new'].map(tag => {
      const slot = document.querySelector(`#sug-refill > ${tag}`);
      return slot.hasAttribute('data-lf-projected-location')
        && getComputedStyle(slot).outlineStyle === 'solid'; })""")
    assert rings == [True, True], f"a slot of the decision wears no ring: {rings}"


def test_a_commented_obligation_does_not_wear_its_ring_on_the_runtime_s_own_note(
    browser, serve
):
    """The boxes a decision shows through are the page's, never the runtime's.

    The paint pass writes one hidden line per block holding a comment, saying how many
    it holds, and for an element anchor that line lands inside the element the anchor
    names. It is clipped to a pixel, so it has a box — and a wrapper that draws none of
    its own then has two children with area, its slot and the runtime's word about the
    page. Area alone keeps the wrong ones out only by luck: the family's control line
    happens to be zero-wide, and this one is not.

    The order hides it. The note is written after the marks are placed,
    so the first paint of a page sees no note and the ring is right; it moves onto the
    pixel on the next pass — which the On Me walk always is, the user having pressed a
    key. So the fault needs a comment on the page *and* a repaint, and shows as a 1px
    ring beside the change instead of on it.

    The shipped wrapper draws a box of its own, so the page supplies the boxless
    one here — the line of CSS any page can write is what keeps this reachable."""
    url = serve(
        OBLIGATIONS_PAGE.replace(
            "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
        )
    )
    answered_comment(
        serve.page_dir,
        "Does this hold when the camera is offline?",
        {"section": "sug-refill"},
    )
    page = open_page(browser, url)
    # The note is what this test is about, so its presence is stated rather than assumed:
    # without it every assertion below holds for the wrong reason.
    expect_comment_notes(page, "#sug-refill", 1)

    page.keyboard.press("m")
    page.keyboard.press("m")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-obligation", "1")

    # By tag rather than by class: the slots are wearing the comment's own outline too,
    # this decision being the one that carries the comment, and a class would read that back
    # instead of naming the element.
    marks = page.evaluate("""() => [...document.querySelectorAll('[data-lf-obligation]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the ring reached past the page's own boxes: {marks}"


def test_a_seat_thread_leaves_the_pick_it_is_about_live(browser, serve):
    """The user's own remark must not lock the control it is a remark about.

    A thread standing in the widget's seat takes the decision off the user's
    list — On Me stops counting it — but answers nothing, so the press that would
    answer it is still live. This is the browser half of the split, and the half the
    user meets first: the POST door only sees a hand-posted event, while here
    the controller reading paints the control and its dispatcher guards the press, and
    the module has already painted the answer by the time either runs. Reading the
    user's list at this door therefore does not refuse the press so much as swallow
    it — the widget flips, nothing is logged, no notice fires, and the next poll puts it
    back with nothing anywhere saying why.

    The subject is the project widget SEATED_OBLIGATION_ENTRY declares, whose seat is where a
    user most often starts such a thread; any thread anchored on an obligation splits it the
    same way, and the reading under test never asks which widget it is."""
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-group id="pick-decision" label="Cap the retries?">'
            '<h2 id="pick-decision-h">Cap the retries?</h2>'
            '<lf-verdict id="pick" asks>Three attempts, then stop.</lf-verdict>'
            "</lf-group>",
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "pick"},
            "text": "neither — cap the retries instead",
        },
    )
    page = open_page(browser, url)
    # Off the user's list, which is the whole reason the two readings differ here.
    expect_obligations_answered(page, "0/1")

    page.get_by_role("button", name="Accept").click()
    round_trip(page)

    expect(page.get_by_role("button", name="Accepted")).to_have_count(1)
    # The log is what holds this, and the control above cannot: the module paints the
    # answer before either guard runs, so with the wrong reading at this door the press
    # reads exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["settle"]
