"""The document's shared, semantic margin map."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    DECISION_PAGE,
    EXAMPLES,
    PANEL_PAGE,
    SUGGESTION_PAGE,
    _publish,
    compare_with,
    key_line,
    leaf_page,
    live_url,
    margins_laid_out,
    open_page,
    panel_settled,
    resized,
    round_trip,
    select,
    ticked,
    told,
    undo,
)

pytestmark = pytest.mark.nightly

COMMENT_ON_DECISION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check whether these jobs can share one visit.",
    "anchor": {"section": "bracket"},
}
OUTCOME_ON_DECISION = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "bracket",
    "action": "choose",
    "detail": {"options": ["br-steel"]},
    "generated": [],
}
COMMENT_ON_SUGGESTION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check this wording before accepting it.",
    "anchor": {"section": "sug-refill"},
}

PAGE_MAP_ITEM_HINT = '.lf-keyline .lf-key[data-lf-commands~="navigation.page-map-item"]'


def address_span(count):
    capped = min(count, 9)
    return f"1–{capped}" if capped > 1 else "1"


def expect_page_map_address(page, count, pressed):
    key_line(page)
    hint = page.locator(PAGE_MAP_ITEM_HINT)
    expect(hint).to_have_count(1)
    expect(hint).to_contain_text("page-map items")
    keys = hint.locator(".lf-key-sequence > kbd")
    assert keys.evaluate_all("keys => keys.map(key => key.textContent)") == [
        "g",
        "m",
        address_span(count),
    ]
    assert keys.evaluate_all("keys => keys.map(key => key.dataset.lfKeyState)") == [
        "pressed"
    ] * pressed + ["neutral"] * (3 - pressed)


def resized_shell(page, inline_size, height):
    """Resize by the container's own width, independent of scrollbar posture."""
    viewport_width = page.viewport_size["width"]
    resized(page, viewport_width, height)
    for _ in range(3):
        shell_width = page.evaluate("() => document.body.getBoundingClientRect().width")
        difference = inline_size - shell_width
        if abs(difference) <= 0.5:
            return
        viewport_width += round(difference)
        resized(page, viewport_width, height)
    assert page.evaluate(
        "() => document.body.getBoundingClientRect().width"
    ) == pytest.approx(inline_size, abs=0.5)


ACTION_PAGE = SUGGESTION_PAGE.replace(
    "<main>", '<main><section id="action-section">'
).replace(
    "</main>",
    """
<lf-draft id="draft-ops"><pre>
  Run the migration before deploying.
</pre></lf-draft>
<div style="height: 500px" aria-hidden="true"></div>
    </section></main>""",
)
UNID_SELECTION_PAGE = PANEL_PAGE.replace('<p id="how-cap">', "<p>")
PAGE_MAP_PAGE = leaf_page(
    "Twelve Page-map locations",
    "".join(
        f'<section id="map-{n}" style="min-height: 420px">'
        f"<h2>Location {n}</h2><p>Body {n}</p></section>"
        for n in range(1, 13)
    ),
)
PAGE_MAP_EVENTS = [
    {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": f"Map note {n}",
        "anchor": {"section": f"map-{n}"},
    }
    for n in range(1, 13)
]


def test_g_addresses_the_page_map_prefix_in_its_announced_order(browser, serve):
    """The first nine Page-map locations keep their announced position as address."""
    page, errors = open_page(browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS))
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="map-3"] > .lf-margin-marker')
    address = page.evaluate(
        """() => {
          const marker = [...document.querySelectorAll('.lf-margin-marker')]
            .find(candidate => candidate.lfEntry?.target?.id === 'map-3');
          const position = marker.getAttribute('aria-label').match(/(\\d+) of (\\d+)/);
          const mapCount = document.querySelector('.lf-living-margin')
            .getAttribute('aria-label').match(/(\\d+) locations/);
          const targetTop = document.querySelector('#map-3')
            .getBoundingClientRect().top;
          return {number: Number(position[1]), count: Number(position[2]),
            mapCount: Number(mapCount[1]), targetTop,
            viewportHeight: innerHeight};
        }"""
    )
    assert address["count"] == address["mapCount"]
    assert address["count"] == 12
    assert address["number"] <= 9
    assert address["targetTop"] > address["viewportHeight"], (
        "the target must begin off screen so this proves the address is page-wide"
    )
    marker.evaluate(
        """control => control.addEventListener('click', () => {
          control.dataset.activationClicks =
            String(Number(control.dataset.activationClicks || 0) + 1);
        })"""
    )

    def activation_state():
        return page.evaluate(
            """() => {
              const marker = document.querySelector(
                '[data-lf-margin-for="map-3"] > .lf-margin-marker'
              );
              return {
                focused: document.activeElement === marker,
                clicks: marker.dataset.activationClicks,
                open: document.querySelector('.lf-margin-preview')
                  .matches(':popover-open'),
                expanded: marker.getAttribute('aria-expanded'),
                target: document.querySelector('#map-3')
                  .classList.contains('lf-margin-target'),
              };
            }"""
        )

    marker.click()
    pointer_activation = activation_state()
    assert pointer_activation == {
        "focused": True,
        "clicks": "1",
        "open": True,
        "expanded": "true",
        "target": True,
    }
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.evaluate(
        """() => {
          document.body.focus();
          document.scrollingElement.scrollTo(0, 0);
          document.querySelector(
            '[data-lf-margin-for="map-3"] > .lf-margin-marker'
          ).dataset.activationClicks = '0';
        }"""
    )
    expect(marker).not_to_be_focused()

    page.keyboard.press("g")
    expect_page_map_address(page, address["count"], 1)
    page.keyboard.press("m")
    expect_page_map_address(page, address["count"], 2)
    page.keyboard.press(str(address["number"]))

    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("Map note 3")
    assert activation_state() == pointer_activation, (
        "the page-map address and the marker's click leave different state"
    )

    page.keyboard.press("Escape")
    resized(page, 390, 760)
    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press(str(address["number"]))
    compact_item = page.locator(".lf-page-map-sheet .lf-page-map-action").filter(
        has_text="Map note 3"
    )
    expect(page.locator(".lf-page-map-sheet")).to_be_visible()
    expect(compact_item).to_be_focused()
    expect(compact_item).to_be_in_viewport()
    page.keyboard.press("Escape")
    expect(page.locator("#map-3")).to_be_in_viewport()
    assert errors == []
    page.close()


def test_the_page_map_walk_stops_at_both_visible_edges(browser, serve):
    """The page map is a vertical list: its arrows stop at its first and last markers,
    while Home and End remain direct routes to those edges."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    markers = page.locator(".lf-margin-marker:visible")
    assert markers.count() > 1, "the page map has no pair of visible markers to walk"

    markers.first.focus()
    page.keyboard.press("Home")
    first = page.locator(":focus").get_attribute("aria-label")
    assert first and page.locator(":focus").evaluate(
        "node => node.matches('.lf-margin-marker')"
    )
    page.keyboard.press("ArrowUp")
    assert page.locator(":focus").get_attribute("aria-label") == first

    page.keyboard.press("End")
    last = page.locator(":focus").get_attribute("aria-label")
    assert last and last != first
    page.keyboard.press("ArrowDown")
    assert page.locator(":focus").get_attribute("aria-label") == last

    page.keyboard.press("Home")
    assert page.locator(":focus").get_attribute("aria-label") == first
    assert errors == []
    page.close()


def test_one_target_has_one_primary_button_and_inline_secondary_buttons(browser, serve):
    """A primary action acts; the ellipsis unfolds the remaining Buttons in place."""
    page, errors = open_page(
        browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION])
    )
    resized(page, 1440, 900)

    suggestion = page.locator("[data-lf-for='sug-refill'].lf-sug-actions")
    suggestion_item = suggestion.locator("xpath=..")
    expect(suggestion_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(suggestion_item.locator(".lf-sug-accept")).to_be_visible()
    expect(suggestion_item.locator(".lf-sug-reject")).to_be_hidden()
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    more = suggestion_item.locator(":scope > .lf-margin-more")
    expect(more).to_be_visible()
    for button in (suggestion_item.locator(".lf-sug-accept"), more):
        expect(button).to_have_class(re.compile(r"lf-margin-action"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_hidden()
    expect(suggestion_item.locator(".lf-sug-accept")).to_have_attribute(
        "data-lf-behavior", "action"
    )
    expect(suggestion_item.locator(".lf-sug-accept")).not_to_have_attribute(
        "aria-expanded", re.compile(".+")
    )
    expect(more).to_have_attribute("data-lf-behavior", "options")
    expect(more).to_have_attribute("aria-expanded", "false")

    more.click()
    preview = page.locator(".lf-margin-preview")
    options = suggestion_item.locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()
    expect(more).to_have_attribute("aria-expanded", "true")
    expect(more).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close options")
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-help")
    expect(reference).to_be_visible()
    back = reference.locator('.lf-help-command[data-lf-command="margin.back"]')
    expect(back).to_have_text("Fold the secondary page actions")
    back.click()
    expect(reference).to_be_hidden()
    expect(options).to_be_hidden()
    expect(more).to_be_focused()
    more.click()
    reject = options.get_by_role("button", name=re.compile(r"Reject"))
    expect(reject).to_be_visible()
    expect(options.get_by_role("button", name=re.compile(r"Ask for"))).to_be_visible()
    page.keyboard.press("Tab")
    expect(reject).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    draft_controls = page.locator("[data-lf-for='draft-ops'].lf-draft-controls")
    draft_item = draft_controls.locator("xpath=..")
    expect(draft_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    expect(draft_item.locator(".lf-draft-pencil")).to_be_visible()
    expect(draft_item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(draft_item.locator(".lf-draft-pencil")).to_have_class(
        re.compile(r"lf-margin-action")
    )
    expect(draft_item.locator(".lf-draft-pencil")).to_have_attribute(
        "data-lf-behavior", "disclosure"
    )
    expect(draft_item.locator(".lf-draft-pencil")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(draft_item.locator(".lf-draft-pencil .lf-margin-action-label")).to_have_text(
        "Edit…"
    )
    expect(page.locator(".lf-margin-action-cue")).to_have_count(0)
    expect(page.locator(".lf-margin-action[title]")).to_have_count(0)
    page.mouse.move(0, 0)
    page.evaluate("() => document.activeElement.blur()")
    accept = suggestion.locator(".lf-sug-accept")
    edit = draft_item.locator(".lf-draft-pencil")
    assert accept.evaluate(
        "el => getComputedStyle(el).backgroundColor"
    ) == edit.evaluate("el => getComputedStyle(el).backgroundColor"), (
        "actions and disclosures no longer share the same unfilled circle"
    )
    assert edit.evaluate("el => getComputedStyle(el).backgroundColor") == more.evaluate(
        "el => getComputedStyle(el).backgroundColor"
    ), "disclosure and overflow no longer share the same circular face"
    borders = [
        control.evaluate(
            "el => { const s = getComputedStyle(el); "
            "return [s.borderTopWidth, s.borderRightWidth, "
            "s.borderBottomWidth, s.borderLeftWidth]; }"
        )
        for control in (accept, edit, more)
    ]
    assert borders == [["2px"] * 4, ["1px"] * 4, ["1px"] * 4], (
        "the whole ring no longer distinguishes immediate actions from context"
    )

    before_hover = edit.bounding_box()
    edit.hover()
    expect(edit.locator(".lf-margin-action-label")).to_be_visible()
    assert edit.bounding_box() == before_hover, "the transient label moved its Button"
    page.mouse.move(0, 0)
    expect(edit.locator(".lf-margin-action-label")).to_be_hidden()

    draft_address = draft_item.evaluate(
        """item => {
          const position = item.querySelector(':scope > .lf-margin-marker')
            .getAttribute('aria-label').match(/(\\d+) of (\\d+)/);
          return {number: Number(position[1]), count: Number(position[2])};
        }"""
    )
    page.keyboard.press("g")
    expect_page_map_address(page, draft_address["count"], 1)
    page.keyboard.press("m")
    expect_page_map_address(page, draft_address["count"], 2)
    assert draft_address["number"] <= 9
    page.keyboard.press(str(draft_address["number"]))
    expect(draft_item.locator(".lf-draft-pencil")).to_be_focused()

    shapes = page.locator(
        ".lf-sug-accept:visible, .lf-draft-pencil:visible, .lf-margin-more:visible, "
        ".lf-margin-marker:visible"
    ).evaluate_all(
        "els => els.map(el => { const box = el.getBoundingClientRect(); "
        "const style = getComputedStyle(el); "
        "return [Math.round(box.width), Math.round(box.height), style.borderRadius]; })"
    )
    assert len({tuple(shape) for shape in shapes}) == 1, (
        "actions, disclosures, and overflow no longer share one Button shape"
    )

    rail_left = accept.evaluate(
        "el => el.closest('.lf-margin-item').getBoundingClientRect().left"
    )
    assert abs(edit.bounding_box()["x"] - rail_left) <= 1, (
        "the draft's resting Edit Button no longer shares the action rail's left edge"
    )
    edit.click()
    save = draft_item.get_by_role("button", name="Save", exact=True)
    expect(save).to_be_visible()
    assert abs(save.bounding_box()["x"] - rail_left) <= 1, (
        "the draft's Save Button no longer shares the action rail's left edge"
    )
    page.mouse.move(0, 0)
    assert save.evaluate(
        "el => { const s = getComputedStyle(el); "
        "return [s.backgroundColor, s.borderColor, s.borderTopWidth]; }"
    ) == accept.evaluate(
        "el => { const s = getComputedStyle(el); "
        "return [s.backgroundColor, s.borderColor, s.borderTopWidth]; }"
    ), "Save and Accept no longer share the canonical immediate-action ring"
    draft_item.locator(":scope > .lf-margin-more").click()
    draft_item.locator(":scope > .lf-margin-options").get_by_role(
        "button", name="Cancel", exact=True
    ).click()
    expect(edit).to_be_visible()

    accept.focus()
    # Reconciliation that does not change the target order leaves the complete item in
    # place, so a focused contribution remains focused.
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    expect(accept).to_be_focused()
    rail = page.locator("html").evaluate("el => el.style.getPropertyValue('--rail')")
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )
    page.keyboard.press("r")
    reactions = options.locator(".lf-margin-reactions")
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()
    expect(reactions.locator(".lf-react:visible")).to_have_count(6)
    expect(reactions.locator(":scope > .lf-fab")).to_have_class(
        re.compile(r"lf-margin-action")
    )
    expect(reactions.locator(".lf-react").first).to_have_class(
        re.compile(r"lf-margin-action")
    )
    ok = reactions.locator('.lf-react[data-token="ok"]')
    expect(ok).to_have_attribute("aria-label", "ok — settled — no change asked")
    expect(ok).not_to_have_attribute("title", re.compile(".+"))
    ok.hover()
    expect(ok.locator(".lf-margin-action-label")).to_have_text(
        "ok — settled — no change asked"
    )
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    assert (
        page.locator("html").evaluate("el => el.style.getPropertyValue('--rail')")
        == rail
    ), "temporary reaction choices permanently widened the page rail"
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "opening reaction choices moved the readable column"
    assert reactions.evaluate(
        "surface => surface.closest('.lf-margin-options') !== null"
    ), "r did not expand the target's canonical Button options"

    # Labels remain transient even with abundant room; options never widen the rail.
    resized(page, 2400, 900)
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_visible()
    page.evaluate("() => document.activeElement.blur()")
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_hidden()
    accept.hover()
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_visible()
    page.mouse.move(0, 0)
    accept.focus()
    page.keyboard.press("r")
    expect(reactions.locator(".lf-react:visible")).to_have_count(6)

    page.keyboard.press("Escape")
    more.click()
    thread_button = options.locator(
        '.lf-margin-reading-option[data-lf-kinds="comment"]'
    )
    expect(thread_button).to_be_visible()
    thread_button.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(options).to_be_visible()
    expect(page.locator(".lf-keyline")).to_contain_text("close thread")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(options).to_be_visible()
    expect(thread_button).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close options")
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    # The shared behavior belongs to the target item, not specifically to a
    # suggestion: focusing the draft's resting Edit action extends that same item.
    draft_controls.locator(".lf-draft-pencil").focus()
    page.keyboard.press("r")
    expect(
        draft_item.locator(".lf-margin-options .lf-margin-reactions .lf-react:visible")
    ).to_have_count(6)
    expect(draft_item.locator(":scope > .lf-margin-more")).to_be_visible()

    # On a narrow screen each item docks directly after the rendered block that owns its
    # target. It does not join every other action at the end of their common section, and
    # the desktop map marker leaves the compact action row to the Map sheet.
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement.blur()")
    resized(page, 390, 900)
    suggestion.locator(".lf-sug-accept").focus()
    expect(page.locator("#sug-refill")).to_be_in_viewport()
    assert suggestion_item.evaluate(
        "item => item.previousElementSibling === document.querySelector('#replace')"
    ), "the first proposal's controls were hoisted past later targets in its section"
    assert draft_item.evaluate(
        "item => item.previousElementSibling === document.querySelector('#draft-ops')"
    ), "the draft's Edit action no longer follows the draft"
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    page.keyboard.press("r")
    expect(reactions.locator(".lf-react:visible")).to_have_count(6)
    expect(suggestion_item).to_have_class(re.compile(r"lf-docked"))
    reactions.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "ok" and sent["anchor"] == {"section": "sug-refill"}

    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press(str(draft_address["number"]))
    expect(draft_item.locator(".lf-draft-pencil")).to_be_focused()
    expect(page.locator(".lf-page-map-sheet")).to_be_hidden()

    assert errors == []
    page.close()


def test_a_receipt_is_a_flat_button_and_an_active_claim_is_a_raised_one(browser, serve):
    """A Button's look states its promise, and a receipt promises nothing to press.

    The reader's move is already made: Sent, Waiting for pickup and Picked up report it,
    so that Button is sewn flat and leaves the accessibility tree as a status rather than
    a control. The walk still arrives, because the phase is what a reader listening came
    for. Only a real claim — work the reader can watch — raises the same Button back into
    a press, in the same seat, so the cluster's identity survives the change of promise.
    """
    page, errors = open_page(browser, serve(DECISION_PAGE))
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')

    page.locator("#job-mounts").click()
    round_trip(page)

    def face():
        return marker.evaluate(
            """node => {
              const style = getComputedStyle(node);
              return {
                behavior: node.dataset.lfBehavior,
                role: node.getAttribute('role'),
                glyph: node.querySelector(':scope > .lf-margin-action-glyph')
                  .textContent,
                word: node.querySelector(':scope > .lf-margin-action-label').textContent,
                tabIndex: node.tabIndex,
                cursor: style.cursor,
                background: style.backgroundColor,
                border: style.borderTopColor,
                ink: style.color,
              };
            }"""
        )

    muted = page.evaluate(
        "() => getComputedStyle(document.documentElement)"
        ".getPropertyValue('--muted').trim()"
    )
    sent = face()
    assert sent == {
        "behavior": "receipt",
        "role": "status",
        "glyph": "✓",
        "word": "Sent",
        "tabIndex": -1,
        "cursor": "default",
        "background": "rgba(0, 0, 0, 0)",
        "border": "rgba(0, 0, 0, 0)",
        "ink": sent["ink"],
    }
    assert sent["ink"] == page.evaluate(
        "muted => { const probe = document.createElement('span');"
        " probe.style.color = muted; document.body.append(probe);"
        " const read = getComputedStyle(probe).color; probe.remove(); return read; }",
        muted,
    ), "a receipt's check no longer stands in the same muted ink"
    # The pointer finds nothing to lift, and the seat keeps the cluster's own fitting.
    marker.hover()
    assert face() == sent
    assert marker.evaluate("node => getComputedStyle(node).width") == "32px"

    named = re.compile(r"^Sent,")
    expect(page.get_by_role("button", name=named)).to_have_count(0)
    expect(page.get_by_role("status", name=named)).to_have_count(1)
    assert page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.some(row => row.tabIndex === 0)"
    ), "no Button is left for Tab to enter the rail by"

    # The reader listening still reaches the phase by its numbered address.
    place = int(re.search(r"(\d+) of ", marker.get_attribute("aria-label")).group(1))
    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press(str(place))
    expect(marker).to_be_focused()

    # Standing there is not the same as being the way in. A repaint under the reader
    # leaves the rail's one stop on a Button that acts, and the receipt without one.
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame("
        "() => requestAnimationFrame(done)))"
    )
    expect(marker).to_be_focused()
    stops = page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.map(row => [row.dataset.lfBehavior, row.tabIndex])"
    )
    assert ["receipt", -1] in stops, stops
    assert [behavior for behavior, index in stops if index == 0] == ["disclosure"], (
        stops
    )

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the mounts",
            "--on",
            "jobs",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)

    active = face()
    assert active["behavior"] == "disclosure"
    assert active["role"] is None
    assert active["glyph"] == "●"
    assert active["cursor"] == "pointer"
    assert active["background"] != "rgba(0, 0, 0, 0)"
    assert active["border"] != "rgba(0, 0, 0, 0)"
    expect(page.get_by_role("button", name=re.compile(r"^Active,"))).to_have_count(1)

    assert errors == []
    page.close()


def test_a_buttons_walk_position_stays_out_of_its_visible_word(browser, serve):
    """Which location of how many, and how far down, is how a reader listening places a
    Button in the walk. Painted, the same words read as progress toward something, which
    is not what they say, so they belong to the accessible name alone."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    buttons = page.evaluate(
        """() => [...document.querySelectorAll('.lf-margin-action')].map(control => ({
          name: control.getAttribute('aria-label'),
          word: control.querySelector(':scope > .lf-margin-action-label').textContent,
        }))"""
    )
    placed = [button for button in buttons if re.search(r"\d+ of \d+", button["name"])]
    assert placed, "no Button announced where it stands in the walk"
    for button in placed:
        assert "percent down" in button["name"], button
    for button in buttons:
        assert not re.search(r"\d+ of \d+|percent down", button["word"]), button

    assert errors == []
    page.close()


def test_secondary_button_proxies_preserve_disabled_and_focus_contract(browser, serve):
    """Unfolded Buttons close coherently and never outlive their owner's state."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {offer, marginAction, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          const primary = marginAction(offer('button', ''), {
            glyph: 'A', label: 'Act', behavior: 'action'
          });
          const backup = marginAction(offer('button', ''), {
            glyph: 'B', label: 'Backup', behavior: 'action'
          });
          const locked = marginAction(offer('button', ''), {
            glyph: 'L', label: 'Locked', behavior: 'action'
          });
          const details = marginAction(offer('button', ''), {
            glyph: 'D', label: 'Details', behavior: 'disclosure'
          });
          details.setAttribute('aria-expanded', 'true');
          locked.setAttribute('aria-disabled', 'true');
          primary.onclick = () => window.lfPrimaryClicks += 1;
          backup.onclick = () => window.lfBackupClicks += 1;
          controls.append(primary, backup, locked, details);
          window.lfPrimaryClicks = 0;
          window.lfBackupClicks = 0;
          window.lfButtonFixture = {
            primary, backup, locked, details,
            registration: registerMarginItem({
              target: document.querySelector('#how-cap'), controls
            })
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    more.click()
    backup = options.get_by_role("button", name="Backup")
    expect(options.get_by_role("button", name="Locked")).to_be_disabled()
    expect(options.get_by_role("button", name="Details")).to_have_attribute(
        "aria-expanded", "true"
    )

    primary = item.locator("[data-lf-button-primary]")
    primary.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfPrimaryClicks") == 1
    expect(options).to_be_hidden()
    expect(primary).to_be_focused()

    more.click()
    backup.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfBackupClicks") == 1
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    more.click()
    backup.focus()
    page.evaluate(
        """() => {
          const fixture = window.lfButtonFixture;
          fixture.backup.hidden = true;
          fixture.locked.hidden = true;
          fixture.details.hidden = true;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(more).to_be_hidden()
    expect(primary).to_be_focused()

    assert errors == []
    page.close()


def test_a_secondary_thread_keeps_card_ownership_through_membership_and_posture(
    browser, serve
):
    """The semantic Thread Button owns its open card as a cluster reconfigures."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "First thread at this target.",
        "anchor": {"section": "how-cap"},
    }
    page, errors = open_page(browser, serve(PANEL_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginAction, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const primary = marginAction(offer('button', ''), {
            glyph: 'A', label: 'Act', behavior: 'action'
          });
          window.lfThreadOwner = {
            primary,
            registration: registerMarginItem({
              target: document.querySelector('#how-cap'), controls: primary, claim: true
            })
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    marker = item.locator(":scope > .lf-margin-marker")
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    more.click()
    thread = options.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    thread.evaluate("node => node.dataset.stableProof = 'same-thread-button'")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")

    thread.focus()
    page.evaluate(
        """() => {
          const fixture = window.lfThreadOwner;
          fixture.primary.hidden = true;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(marker).to_be_visible()
    expect(marker).to_be_focused()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    page.evaluate(
        """() => {
          const fixture = window.lfThreadOwner;
          fixture.primary.hidden = false;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(options).to_be_visible()
    expect(thread).to_be_focused()
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread).to_have_attribute("aria-expanded", "true")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "Second thread joined while the first card was open.",
            "anchor": {"section": "how-cap"},
        },
    )
    told(page)
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(2)
    expect(thread).to_have_attribute("aria-expanded", "true")

    resized(page, 1207, 900)
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(thread).to_have_attribute("aria-controls", "lf-threads")
    expect(thread).not_to_have_attribute("aria-expanded", re.compile(".+"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)

    resized(page, 1440, 900)
    expect(thread).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(thread).to_have_attribute("aria-expanded", "false")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(thread).to_be_focused()

    assert errors == []
    page.close()


def test_reaction_choices_and_their_receipt_share_an_unided_selected_block(
    browser, serve
):
    """The durable section coordinate does not pull the visible RHS item to its top."""
    page, errors = open_page(browser, serve(UNID_SELECTION_PAGE))
    resized(page, 1600, 900)
    paragraph = page.locator("#s-how > p:nth-of-type(2)")
    box = paragraph.bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=12,
    )
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    bar.locator(".lf-react-trigger").click()
    # The choices are the bar's own, raised on the selection where the reader is
    # pointing: an anchored response opens in place rather than docking a row of
    # options into the margin. What the margin holds for this block is the receipt.
    expect(bar).to_have_class(re.compile(r"\blf-react-open\b"))

    bar.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["anchor"]["section"] == "s-how" and sent["anchor"]["quote"]
    receipt = page.locator(".lf-margin-item").filter(
        has=page.get_by_role("button", name=re.compile(r"^ok — take it back$"))
    )
    expect(receipt).to_have_count(1)
    assert abs(receipt.bounding_box()["y"] - paragraph.bounding_box()["y"]) <= 6
    assert errors == []
    page.close()


def test_shadow_targets_keep_common_shape_identity_and_composed_order(browser, serve):
    """Nested, sibling, and slotted targets follow their rendered order."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    readings = page.evaluate(
        """async () => {
          const { marginAction, registerMarginItem } =
            await import('/runtime/living-margin.js');
          const makeRecord = label => {
            const shell = document.createElement('div');
            const root = shell.attachShadow({mode: 'open'});
            const target = document.createElement('p');
            target.textContent = `${label} target`;
            root.append(target);
            const controls = marginAction(document.createElement('button'), {
              glyph: '!', label: `${label} controls`
            });
            return {label, shell, target, controls};
          };
          const first = makeRecord('first');
          const nested = makeRecord('nested');
          first.shell.shadowRoot.append(nested.shell);
          const second = makeRecord('second');
          const slottedShell = document.createElement('div');
          const slottedRoot = slottedShell.attachShadow({mode: 'open'});
          slottedRoot.innerHTML = '<slot name="b"></slot><slot name="a"></slot>';
          const makeSlottedRecord = (label, slot) => {
            const target = document.createElement('p');
            target.slot = slot;
            target.textContent = `${label} target`;
            const controls = marginAction(document.createElement('button'), {
              glyph: '!', label: `${label} controls`
            });
            return {label, shell: slottedShell, target, controls};
          };
          const slotA = makeSlottedRecord('slot a', 'a');
          const slotB = makeSlottedRecord('slot b', 'b');
          slottedShell.append(slotA.target, slotB.target);
          const main = document.querySelector('main');
          main.append(first.shell, second.shell, slottedShell);
          const records = [slotA, nested, second, slotB, first];
          for (const record of records) {
            const {target, controls} = record;
            const margin = registerMarginItem({target, controls});
            record.margin = margin;
          }
          await new Promise(done =>
            requestAnimationFrame(() => requestAnimationFrame(done))
          );
          const readings = [first, nested, second, slotA, slotB].map(({shell, target, controls}) => ({
            ownsTarget: controls.parentElement?.lfEntry?.target === target,
            inDocument: controls.getRootNode() === document,
            itemCount: shell.shadowRoot.querySelectorAll('.lf-margin-item').length,
            commonAction: controls.matches('.lf-margin-action'),
            width: getComputedStyle(controls).width,
            minHeight: getComputedStyle(controls).minHeight,
            radius: getComputedStyle(controls).borderRadius,
            visibleWord: controls.querySelector('.lf-margin-action-label')?.textContent,
          }));
          const testTargets = new Set(records.map(({target}) => target));
          const itemOrder = [...main.querySelectorAll(':scope > .lf-margin-item')]
            .filter(item => testTargets.has(item.lfEntry?.target))
            .map(item => item.lfEntry.target.textContent);
          records.forEach(({margin, shell}) => { margin.unregister(); shell.remove(); });
          return {readings, itemOrder};
        }"""
    )
    assert readings == {
        "readings": [
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "first controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "nested controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "second controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "slot a controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "slot b controls",
            },
        ],
        "itemOrder": [
            "first target",
            "nested target",
            "second target",
            "slot b target",
            "slot a target",
        ],
    }
    assert errors == []
    page.close()


def test_one_information_button_does_not_raise_a_preview(browser, serve):
    """A single non-thread reading travels directly; cards are reserved for threads."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1600, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="decision"]').first
    expect(marker).not_to_have_attribute("aria-controls", re.compile(".+"))
    expect(marker).not_to_have_attribute("aria-expanded", re.compile(".+"))
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_hidden()

    assert errors == []
    page.close()


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location has one resting Button; its other readings unfold as peer Buttons."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_count(0)
    expect(marker).to_have_attribute("aria-label", re.compile(r"Thread, \d+ of"))
    expect(marker).not_to_have_attribute("aria-label", re.compile("Outcome"))
    expect(marker).not_to_have_attribute("title", re.compile(".+"))
    more = marker.locator("xpath=..").locator(":scope > .lf-margin-more")
    expect(more).to_be_visible()
    claim = marker.locator("xpath=..").evaluate(
        """item => {
          const style = getComputedStyle(item);
          const buttons = [...item.querySelectorAll(':scope > .lf-margin-action')]
            .filter(button => button.checkVisibility());
          const needed = buttons.reduce(
            (total, button) => total + button.getBoundingClientRect().width, 0
          ) + (parseFloat(style.columnGap || style.gap) || 0)
            * Math.max(0, buttons.length - 1)
            + (parseFloat(style.paddingLeft) || 0)
            + (parseFloat(style.paddingRight) || 0);
          return {
            needed,
            rail: parseFloat(document.documentElement.style.getPropertyValue('--rail'))
          };
        }"""
    )
    assert claim["rail"] >= claim["needed"] - 0.5, claim

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    marker.focus()
    expect(preview).to_be_hidden()

    marker.click()
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(preview).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))
    main_box = page.locator("main").bounding_box()
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= main_box["x"] + main_box["width"]
    assert preview_box["x"] >= 0
    assert preview_box["x"] + preview_box["width"] <= page.evaluate("innerWidth")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview).not_to_contain_text("options · choose")
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-keyline")).to_contain_text("close thread")
    expect(marker).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    held = marker.get_attribute("aria-label")
    page.keyboard.press("ArrowDown")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    assert page.evaluate("() => document.activeElement.matches('.lf-margin-marker')")
    assert page.locator(":focus").get_attribute("aria-label") != held

    more.click()
    options = marker.locator("xpath=..").locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    outcome = options.get_by_role("button", name=re.compile(r"Outcome for"))
    expect(outcome).to_be_visible()
    expect(preview).to_be_hidden()
    outcome.click()
    expect(options).to_be_hidden()
    expect(preview).to_be_hidden()

    assert errors == []
    page.close()


def test_design_mode_retires_and_suppresses_the_top_layer_margin_preview(
    browser, serve
):
    """Ordinary design paint never promises to rise above the browser's top layer."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()

    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    expect(preview).to_be_hidden()
    page.mouse.move(4, 200)
    page.locator("body").focus()
    marker.hover()
    expect(preview).to_be_hidden()
    page.locator("body").focus()
    marker.focus()
    expect(preview).to_be_hidden()
    page.keyboard.press("Enter")
    expect(preview).to_be_hidden()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))

    assert errors == []
    page.close()


def test_a_thread_can_be_answered_in_the_right_margin_without_opening_threads(
    browser, serve
):
    """The anchored thread is a complete conversation beside its source."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    expect(marker.locator(".lf-margin-action-glyph")).to_have_text("💬")
    first_frame = marker.evaluate(
        """async marker => {
          const card = document.querySelector('.lf-margin-preview');
          const painted = new Promise(resolve => requestAnimationFrame(() => {
            const box = card.getBoundingClientRect();
            resolve({open: card.matches(':popover-open'),
                     thread: card.hasAttribute('data-lf-thread'),
                     left: box.left,
                     top: box.top,
                     placedLeft: card.style.getPropertyValue('--lf-thread-left'),
                     placed: card.style.getPropertyValue('--lf-thread-top')});
          }));
          marker.focus();
          marker.click();
          return painted;
        }"""
    )
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread")
    reply = thread.locator("textarea")

    assert first_frame["open"] and first_frame["thread"], first_frame
    assert first_frame["placed"], first_frame
    assert first_frame["placedLeft"], first_frame
    assert first_frame["left"] == pytest.approx(
        float(first_frame["placedLeft"].removesuffix("px")), abs=0.5
    ), first_frame
    assert first_frame["top"] == pytest.approx(
        float(first_frame["placed"].removesuffix("px")), abs=0.5
    ), first_frame
    expect(thread.locator(".lf-conversation-body")).to_have_text(
        COMMENT_ON_DECISION["text"]
    )
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    expect(thread.locator(".lf-conversation-open")).to_have_count(0)
    geometry = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
            .getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainRight: main.right, markerRight: marker.right,
                  cardLeft: card.left, cardWidth: card.width};
        }"""
    )
    assert geometry["cardLeft"] == pytest.approx(
        geometry["markerRight"] + 8, abs=0.5
    ), geometry
    assert geometry["cardLeft"] >= geometry["mainRight"], geometry
    assert geometry["cardWidth"] >= 459, geometry
    expect(page.locator(".lf-keyline")).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    reply.fill("Yes. One visit can cover both jobs.")
    ticked(page)
    expect(reply).to_have_value("Yes. One visit can cover both jobs.")
    expect(reply).to_be_focused()
    thread.get_by_role("button", name="Send").click()
    round_trip(page)

    expect(thread.locator(".lf-conversation-thread")).to_contain_text(
        "Yes. One visit can cover both jobs."
    )
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(preview).to_be_visible()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    root_id = thread.locator(".lf-conversation-thread").get_attribute("data-thread")
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "reply" and event.get("parent") == root_id
    ]
    assert [event["text"] for event in replies] == [
        "Yes. One visit can cover both jobs."
    ]
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

    preview.evaluate(
        """card => {
          window.__openedMarginModes = [];
          card.addEventListener('toggle', event => {
            if (event.newState === 'open')
              window.__openedMarginModes.push(card.hasAttribute('data-lf-thread'));
          });
        }"""
    )
    marker.click()
    panel_settled(page, open=False)
    expect(preview).to_be_visible()
    assert page.evaluate("() => window.__openedMarginModes") == [True]

    assert errors == []
    page.close()


@pytest.mark.parametrize(
    ("width", "panel_open"), [(760, False), (1000, True), (1440, False)]
)
def test_a_new_anchored_comment_opens_its_inline_thread(
    browser, serve, width, panel_open
):
    """A first message lands in its complete conversation at every page posture."""
    page, errors = open_page(browser, serve(DECISION_PAGE))
    resized(page, width, 900)
    if panel_open:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("Check the January failure mode.")
    page.keyboard.press("Enter")
    round_trip(page)

    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == (
        "comment",
        "Check the January failure mode.",
    )
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    thread = preview.locator(
        f'.lf-margin-thread .lf-conversation-thread[data-thread="{sent["id"]}"]'
    )
    expect(thread.locator(".lf-conversation-body")).to_have_text(sent["text"])
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(thread.locator("textarea")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close thread")
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= 0, preview_box
    assert preview_box["x"] + preview_box["width"] <= width, preview_box
    if width == 760:
        page.keyboard.press("Escape")
        expect(preview).to_be_hidden()
        expect(page.locator(".lf-page-map-toggle")).to_be_focused()

    assert errors == []
    page.close()


# What the card came out as, beside the two facts that decide how wide it was allowed to
# be: the posture the cascade granted, and the floor the theme declares. The floor is read
# from the root, where the theme states it, so the test cannot disagree with the layout
# about which number it is. Where the card stands is asked of the column rather than of
# the marker: the card is placed once, in the turn it opens, and a claim landing after
# that moves the marker without moving the card — a race of its own, and not this
# number's.
THREAD_CARD_GEOMETRY = """() => {
  const main = document.querySelector('main').getBoundingClientRect();
  const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
  const reply = document.querySelector('.lf-margin-thread textarea')
    .getBoundingClientRect();
  return {
    mainRight: main.right,
    cardLeft: card.left, cardRight: card.right, cardWidth: card.width,
    replyWidth: reply.width, innerWidth: window.innerWidth,
    beside: getComputedStyle(document.querySelector('main'))
      .getPropertyValue('--lf-thread-beside').trim(),
    floor: parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--thread-card-floor')),
  };
}"""


def send_anchored_comment(page, text):
    """The gesture the contract's sentence is about: a comment accepted on a passage."""
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill(text)
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)


def test_a_narrow_margin_gives_the_inline_thread_the_page_not_a_sliver(browser, serve):
    """An accepted comment opens a conversation the reader can answer, at any width.

    The card is placed off its marker and takes whatever room the window leaves to the
    right of that edge. On a page whose left strip is already spoken for, that room runs
    out while the marker is still on screen, and nothing was asking how much was left:
    the shipped pr-walkthrough gave a 72px thread and a 22px reply box at 1200, the quote
    wrapping one word to a line and the placeholder one character. The theme's
    --thread-card-floor is where the margin stops being a margin — under it the card comes
    off its marker and covers the page, which is the posture an accepted comment's thread
    is already allowed (skills/leaf/CLAUDE.md, "Chrome, conversations, and text input").
    It does not hand the reader to the Threads panel instead, so a card is what both
    halves of this test read.

    The second half is the other edge of the same number: where the cascade did grant the
    conversation margin, the floor must change nothing, or a fix for the narrow page would
    have taken the margin posture away from the wide one.

    Both halves open on a page that already carries a comment, so the conversation margin
    is claimed and the column has stopped moving before the gesture. Sent into a page
    claiming that strip for the first time, the card is placed against a marker the claim
    then slides, and what the read catches is that race rather than this floor.
    """
    sidebar_page = DECISION_PAGE.replace(
        "<main>", '<main><aside class="sidebar">Page reference</aside>', 1
    )
    page, errors = open_page(browser, serve(sidebar_page, events=[COMMENT_ON_DECISION]))
    resized(page, 1200, 900)
    send_anchored_comment(page, "Check the January failure mode.")

    narrow = page.evaluate(THREAD_CARD_GEOMETRY)
    assert narrow["beside"] == "0", narrow
    assert narrow["cardWidth"] >= narrow["floor"] - 0.5, narrow
    assert narrow["replyWidth"] >= 160, narrow
    assert narrow["cardLeft"] >= 0, narrow
    assert narrow["cardRight"] <= narrow["innerWidth"] + 0.5, narrow
    # No margin was reserved at this width, so the room came out of the page.
    assert narrow["cardLeft"] < narrow["mainRight"], narrow

    assert errors == []
    page.close()

    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    send_anchored_comment(page, "Check the January failure mode.")

    wide = page.evaluate(THREAD_CARD_GEOMETRY)
    assert wide["beside"] == "1", wide
    # Beside the column at the card's own width: the floor took nothing away here.
    assert wide["cardLeft"] >= wide["mainRight"], wide
    assert wide["cardWidth"] >= 459, wide

    assert errors == []
    page.close()


def test_a_shared_passage_keeps_all_of_its_threads_in_one_quiet_card(browser, serve):
    """Several roots need no repeated category label or local panel handoff."""
    second_comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Keep the second conversation separate.",
        "anchor": {"section": "bracket"},
    }
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[COMMENT_ON_DECISION, second_comment])
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")

    expect(preview.locator(".lf-margin-thread")).to_have_count(2)
    expect(preview.locator(".lf-conversation-open")).to_have_count(0)
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-thread.flash")).to_have_count(0)

    assert errors == []
    page.close()


def test_the_shipped_long_thread_opens_beside_its_source_in_the_right_margin(
    browser, serve
):
    """The shipped exchange stays beside its source without covering the document."""
    example = next(page for page in EXAMPLES if page.stem == "ship-review")
    page, errors = open_page(browser, serve(example))
    resized(page, 1440, 900)
    marker = page.get_by_role(
        "group", name=re.compile(r"Page actions for task · iOS reconnect stall")
    ).locator(":scope > .lf-margin-marker")
    expect(marker).to_have_count(1)
    marker.evaluate(
        "marker => scrollBy(0, marker.getBoundingClientRect().top - innerHeight + 52)"
    )

    marker.click()
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread", has_text="One reconnect in forty")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-margin-preview-title")).to_have_text(
        "iOS reconnect stall"
    )
    expect(thread.locator(".lf-conversation-msg.user").first).to_be_visible()
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    expect(thread.locator(".lf-conversation-open")).to_have_count(0)
    geometry = marker.evaluate(
        """markerNode => {
          const main = document.querySelector('main').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const marker = markerNode.getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const title = document.querySelector('.lf-margin-preview-title')
            .getBoundingClientRect();
          const cardStyle = getComputedStyle(document.querySelector('.lf-margin-preview'));
          return {bannerBottom: banner.bottom, mainRight: main.right,
                  markerRight: marker.right,
                  markerMiddle: (marker.top + marker.bottom) / 2,
                  cardLeft: card.left, cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  borderLeft: cardStyle.borderLeftWidth,
                  borderRight: cardStyle.borderRightWidth,
                  titleLeft: title.left, titleTop: title.top,
                  cardScroll: document.querySelector('.lf-margin-preview').scrollTop,
                  panelOpen: document.querySelector('.lf-panel').classList.contains('open')};
        }"""
    )
    assert geometry["cardLeft"] >= geometry["markerRight"] - 0.5, geometry
    assert geometry["cardLeft"] >= geometry["mainRight"], geometry
    assert geometry["cardRight"] <= 1440, geometry
    assert geometry["cardWidth"] >= 459, geometry
    assert geometry["cardTop"] >= geometry["bannerBottom"] + 7, geometry
    assert geometry["cardBottom"] <= 892, geometry
    assert geometry["cardTop"] <= geometry["markerMiddle"] <= geometry["cardBottom"], (
        geometry
    )
    assert geometry["cardScroll"] == 0, geometry
    assert geometry["borderLeft"] == geometry["borderRight"] == "1px", geometry
    assert geometry["titleLeft"] == pytest.approx(geometry["cardLeft"] + 13, abs=0.5)
    assert not geometry["panelOpen"], geometry

    send = preview.get_by_role("button", name="Send")
    send.focus()
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    expect(send).to_be_focused()

    resized(page, 1440, 480)
    capped = preview.evaluate(
        """card => {
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const box = card.getBoundingClientRect();
          return {bannerBottom: banner.bottom, top: box.top, bottom: box.bottom,
                  clientHeight: card.clientHeight, scrollHeight: card.scrollHeight};
        }"""
    )
    assert capped["top"] >= capped["bannerBottom"] + 7, capped
    assert capped["bottom"] <= 472.5, capped
    assert capped["scrollHeight"] > capped["clientHeight"], capped
    resized(page, 1440, 900)

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-decisions-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.keyboard.press("Escape")

    marker.click()
    expect(preview).to_be_visible()

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()
    expect(marker).to_be_focused()

    resized_shell(page, 1208, 900)
    beside = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
            .getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainRight: main.right, markerRight: marker.right, cardLeft: card.left,
                  cardRight: card.right, cardWidth: card.width,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    assert beside["mainRight"] <= beside["cardLeft"] + 0.5, beside
    assert beside["cardLeft"] == pytest.approx(beside["markerRight"] + 8, abs=0.5)
    assert beside["cardRight"] <= beside["shellWidth"] - 8 + 0.5, beside
    assert beside["cardWidth"] >= 447, beside

    resized(page, 1207, 900)
    expect(preview).to_be_hidden()
    expect(marker).to_have_attribute("aria-controls", "lf-threads")
    expect(marker).not_to_have_attribute("aria-expanded", re.compile(".+"))
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    marker.hover()
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

    assert errors == []
    page.close()


def test_focusing_a_thread_button_does_not_open_its_card(browser, serve):
    """Walking the Page map never inserts an unrequested thread into the Tab order."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    preview = page.locator(".lf-margin-preview")

    marker.focus()
    expect(preview).to_be_hidden()
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()

    expect(toggle).to_be_focused()
    expect(preview).to_be_hidden()
    expect(page.locator("#bracket")).not_to_have_class(re.compile(r"lf-margin-target"))
    assert errors == []
    page.close()


def test_only_a_page_with_threads_reserves_the_conversation_margin(browser, serve):
    """Other map meanings keep their narrow rail until a thread needs the card."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION])
    )
    resized(page, 1440, 900)

    # The strip is a claim main resolves from the shell, so it is read off main rather
    # than off body's padding. A custom property computes to its unresolved expression,
    # so the reading is taken from a probe the layout actually sizes.
    def strip_right():
        return page.evaluate(
            """() => {
              const main = document.querySelector('main');
              const probe = document.createElement('i');
              probe.style.cssText = 'position:fixed;visibility:hidden;height:0;'
                + 'padding:0;border:0;width:var(--strip-r)';
              main.append(probe);
              const width = probe.getBoundingClientRect().width;
              probe.remove();
              return width;
            }"""
        )

    assert strip_right() == 59

    events_model.append_event(serve.page_dir, COMMENT_ON_DECISION)
    told(page)
    assert strip_right() == 520

    assert errors == []
    page.close()


def test_a_page_that_can_grow_a_button_reserves_its_rail_before_the_first_gesture(
    browser, serve
):
    """The reader's first move must not be the gesture that pays for the margin.

    Moving a card raises an acknowledgement Button at the page edge. Reserved only while
    that Button stood, the strip arrived with the move and left again with the undo, and
    the column moved 29px each way — for a control the page had always been going to
    offer. So the reservation is read off what the page declares, a tag whose registry
    entry has an action or work channel, and the column stands where it will stand
    before the reader touches anything.

    Measured on the shipped board rather than a fixture, because the strip is only worth
    reserving where a real page's width, its claims and its exhibits meet; a fixture
    built to make those agree would prove nothing about any page a reader opens."""
    example = next(page for page in EXAMPLES if page.stem == "triage-board")
    page, errors = open_page(browser, live_url(serve(example)))
    margins_laid_out(page)
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )

    page.locator("#card-ie .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator("#col-fixed #card-ie")).to_have_count(1)
    margins_laid_out(page)
    # Without a Button in the margin the readings below would agree for the wrong reason.
    expect(page.locator(".lf-margin-item")).to_have_count(1)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "raising the acknowledgement Button moved the readable column"

    undo(page)
    expect(page.locator("#col-wont #card-ie")).to_have_count(1)
    margins_laid_out(page)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "withdrawing the move handed the strip back and moved the column with it"

    assert errors == []
    page.close()


def test_the_full_thread_posture_follows_the_page_container_and_left_claims(
    browser, serve
):
    """A tray or authored sidebar spends room before the contextual thread does."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    page.locator(".lf-decisions").click()
    expect(page.locator("body")).to_have_attribute("data-lf-tray", "decisions")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    if page.locator("body").get_attribute("data-lf-tray") == "decisions":
        page.locator(".lf-decisions").click()
    expect(page.locator("body")).not_to_have_attribute("data-lf-tray", "decisions")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    assert errors == []
    page.close()

    sidebar_page = DECISION_PAGE.replace(
        "<main>", '<main><aside class="sidebar">Page reference</aside>', 1
    )
    page, errors = open_page(
        browser,
        serve(sidebar_page, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    resized_shell(page, 1472, 900)
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    composition = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainWidth: main.width - 48, mainRight: main.right,
                  cardLeft: card.left, cardRight: card.right,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    assert composition["mainWidth"] >= 639.5, composition
    assert composition["mainRight"] <= composition["cardLeft"] + 0.5, composition
    assert composition["cardRight"] <= composition["shellWidth"] + 0.5, composition

    assert errors == []
    page.close()


def test_the_margin_keeps_its_page_coordinate_while_the_reader_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    target = page.locator("#bracket")

    def offset():
        return marker.bounding_box()["y"] - target.bounding_box()["y"]

    before = offset()
    page.evaluate(
        "() => document.scrollingElement.scrollBy({top: 320, behavior: 'instant'})"
    )
    margins_laid_out(page)
    assert offset() == pytest.approx(before, abs=1)

    assert errors == []
    page.close()


def test_the_small_screen_map_is_a_complete_accessible_sheet(browser, serve):
    """The rail becomes a touch-sized index when the margin no longer exists."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    toggle = page.locator(".lf-page-map-toggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_text(re.compile(r"Map \(\d+\)"))
    assert toggle.evaluate(
        "button => button.previousElementSibling.matches('.lf-signoff, .lf-threads-toggle')"
    ), "the small-screen map is not beside the primary feedback controls"
    text_insets = page.locator(".lf-banner-actions > .lf-btn:visible").evaluate_all(
        """buttons => buttons.map(button => {
          const box = button.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(button);
          const text = range.getBoundingClientRect();
          return {label: button.textContent.trim(),
                  above: text.top - box.top, below: box.bottom - text.bottom};
        })"""
    )
    assert text_insets
    for inset in text_insets:
        assert inset["above"] == pytest.approx(inset["below"], abs=1.5), (
            f"{inset['label']} is not vertically centred in the compact banner: {inset}"
        )

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("Page map")
    page.keyboard.press("Shift+m")
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.get_by_role("button", name="Close")).to_be_focused()
    expect(sheet.locator(".lf-page-map-action").first).to_have_css("min-height", "44px")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []

    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    expect(toggle).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    assert errors == []
    page.close()


def test_crossing_to_the_small_screen_retires_the_desktop_preview(browser, serve):
    """A responsive posture exposes one map surface, never both at once."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    expect(page.locator(".lf-page-map-toggle")).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    assert errors == []
    page.close()


def test_crossing_to_the_wide_screen_retires_the_small_screen_sheet(browser, serve):
    """The restored desktop rail replaces, rather than layers under, the mobile map."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()

    resized(page, 1200, 900)
    expect(page.locator(".lf-living-margin")).to_be_visible()
    expect(page.locator(".lf-page-map-toggle")).to_be_hidden()
    expect(sheet).to_be_hidden()

    assert errors == []
    page.close()


def test_an_open_small_screen_map_reconciles_arriving_meanings(browser, serve):
    """The open sheet is a live projection, not a snapshot from its opening press."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    actions = sheet.locator(".lf-page-map-action")
    expect(actions).to_have_count(4)
    page.keyboard.press("Tab")
    expect(actions.first).to_be_focused()

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the map was open.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]').locator(
            ".lf-margin-count"
        )
    ).to_have_text("2")
    expect(actions).to_have_count(5)
    expect(actions.first).to_be_focused()

    assert errors == []
    page.close()


def test_an_open_desktop_preview_reconciles_arriving_meanings(browser, serve):
    """A pinned marker card stays current while its semantic location is retained."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the preview was pinned.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(2)
    expect(page.locator(".lf-margin-thread").last).to_contain_text(
        "A second reading arrived while the preview was pinned."
    )

    assert errors == []
    page.close()


def test_a_live_version_keeps_the_reader_on_the_same_margin_location(browser, serve):
    """Replacing authored main must not discard focus held by retained map chrome."""
    version_url = serve(
        DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION]
    )
    page, errors = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.focus()
    expect(marker).to_be_focused()

    (serve.page_dir / "index.html").write_text(
        DECISION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(marker).to_be_focused()

    assert errors == []
    page.close()


def test_a_live_version_retargets_an_open_margin_preview(browser, serve):
    """A retained preview must outline the new document's matching destination."""
    version_url = serve(
        DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION]
    )
    page, errors = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    close = page.locator(".lf-margin-preview-close")
    close.focus()
    expect(close).to_be_focused()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    (serve.page_dir / "index.html").write_text(
        DECISION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(close).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    assert errors == []
    page.close()


def test_a_version_comparison_joins_the_same_map_and_leaves_with_it(browser, serve):
    """Comparison marks are another projection, not DOM scraped by the map."""
    url = serve(DECISION_PAGE)
    _publish(
        serve.page_dir,
        2,
        DECISION_PAGE.replace("Three jobs", "Four jobs"),
        "The heading now names four jobs.",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))

    compare_with(page, 1)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="change"]')
    ).not_to_have_count(0)
    page.locator(".lf-version").click()
    page.locator('.lf-version-diff[data-lf-version="1"]').click()
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="change"]')).to_have_count(0)

    assert errors == []
    page.close()
