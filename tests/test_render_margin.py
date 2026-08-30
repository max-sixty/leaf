"""The document's shared, semantic margin map."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_harness import EXAMPLES
from render_support import (
    DECISION_PAGE,
    PANEL_PAGE,
    SUGGESTION_PAGE,
    _publish,
    compare_with,
    live_url,
    open_page,
    panel_settled,
    resized,
    round_trip,
    select,
    ticked,
    told,
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
}

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


def test_g_addresses_the_shipped_page_map_in_its_announced_order(browser, serve):
    """Every page-map location has the number its informational marker announces."""
    example = next(page for page in EXAMPLES if page.stem == "ship-review")
    page, errors = open_page(browser, serve(example))
    address = page.evaluate(
        """() => {
          const marker = [...document.querySelectorAll('.lf-margin-marker')]
            .find(candidate => candidate.lfEntry?.target?.id === 'off-t-resync');
          const position = marker.getAttribute('aria-label').match(/(\\d+) of (\\d+)/);
          const mapCount = document.querySelector('.lf-living-margin')
            .getAttribute('aria-label').match(/(\\d+) locations/);
          const targetTop = document.querySelector('#off-t-resync')
            .getBoundingClientRect().top;
          return {number: Number(position[1]), count: Number(position[2]),
            mapCount: Number(mapCount[1]), targetTop,
            viewportHeight: innerHeight};
        }"""
    )
    assert address["count"] == address["mapCount"]
    assert address["targetTop"] > address["viewportHeight"], (
        "the target must begin off screen so this proves the address is page-wide"
    )

    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text(f"m 1–{address['count']}")
    page.keyboard.press("m")
    for digit in str(address["number"]):
        page.keyboard.press(digit)
    if address["number"] * 10 <= address["count"]:
        page.keyboard.press("Enter")

    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("One reconnect in forty is worse")
    expect(preview.locator(".lf-conversation-open")).to_be_focused()

    page.keyboard.press("Escape")
    resized(page, 390, 760)
    page.keyboard.press("g")
    page.keyboard.press("m")
    for digit in str(address["number"]):
        page.keyboard.press(digit)
    compact_item = page.locator(".lf-page-map-sheet .lf-page-map-action").filter(
        has_text="One reconnect in forty is worse"
    )
    expect(page.locator(".lf-page-map-sheet")).to_be_visible()
    expect(compact_item).to_be_focused()
    expect(compact_item).to_be_in_viewport()
    page.keyboard.press("Escape")
    expect(page.locator("#off-t-resync")).to_be_in_viewport()
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

    markers.first.click()
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


def test_one_margin_item_owns_a_targets_controls_information_and_more_actions(
    browser, serve
):
    """A target has one RHS surface; `r` extends that surface horizontally."""
    page, errors = open_page(browser, serve(ACTION_PAGE))
    resized(page, 1440, 900)

    suggestion = page.locator("[data-lf-for='sug-refill'].lf-sug-actions")
    suggestion_item = suggestion.locator("xpath=..")
    expect(suggestion_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(suggestion_item.locator(".lf-sug-accept")).to_be_visible()
    expect(suggestion_item.locator(".lf-sug-reject")).to_be_visible()
    for action in (
        suggestion_item.locator(".lf-sug-accept"),
        suggestion_item.locator(".lf-sug-reject"),
        suggestion_item.locator(":scope > .lf-margin-marker"),
    ):
        expect(action).to_have_class(re.compile(r"lf-margin-action"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_visible()
    expect(
        suggestion_item.locator(".lf-sug-reject .lf-margin-action-label")
    ).to_be_visible()

    draft_controls = page.locator("[data-lf-for='draft-ops'].lf-draft-controls")
    draft_item = draft_controls.locator("xpath=..")
    expect(draft_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    expect(draft_item.locator(".lf-draft-pencil")).to_be_visible()
    expect(draft_item.locator(".lf-draft-pencil")).to_have_class(
        re.compile(r"lf-margin-action")
    )
    expect(draft_item.locator(".lf-draft-pencil .lf-margin-action-label")).to_have_text(
        "Edit"
    )

    draft_address = draft_item.evaluate(
        """item => {
          const position = item.querySelector(':scope > .lf-margin-marker')
            .getAttribute('aria-label').match(/(\\d+) of (\\d+)/);
          return {number: Number(position[1]), count: Number(position[2])};
        }"""
    )
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text(f"m 1–{draft_address['count']}")
    page.keyboard.press("m")
    for digit in str(draft_address["number"]):
        page.keyboard.press(digit)
    if draft_address["number"] * 10 <= draft_address["count"]:
        page.keyboard.press("Enter")
    expect(draft_item.locator(".lf-draft-pencil")).to_be_focused()

    shapes = page.locator(
        ".lf-sug-accept, .lf-sug-reject, .lf-draft-pencil, "
        '[data-lf-margin-for="sug-refill"] > .lf-margin-marker'
    ).evaluate_all(
        "els => els.map(el => { const box = el.getBoundingClientRect(); "
        "const style = getComputedStyle(el); "
        "return [Math.round(box.height), style.borderRadius]; })"
    )
    assert len({tuple(shape) for shape in shapes}) == 1, (
        "Accept, Reject, Edit, and the information marker no longer share one shape"
    )

    accept = suggestion.locator(".lf-sug-accept")
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
    reactions = suggestion_item.locator(":scope > .lf-margin-reactions")
    expect(reactions.locator(".lf-react:visible")).to_have_count(6)
    expect(suggestion_item).to_have_class(re.compile(r"lf-condensed"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_hidden()
    expect(
        suggestion_item.locator(".lf-sug-reject .lf-margin-action-label")
    ).to_be_hidden()
    expect(reactions.locator(":scope > .lf-fab")).to_have_class(
        re.compile(r"lf-margin-action")
    )
    expect(reactions.locator(".lf-react").first).to_have_class(
        re.compile(r"lf-margin-action")
    )
    expect(reactions.locator(".lf-react .lf-margin-action-label").first).to_be_hidden()
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
        """surface => {
          const row = surface.parentElement.getBoundingClientRect();
          const controls = [...surface.parentElement.children]
            .filter(el => el.checkVisibility())
            .map(el => el.getBoundingClientRect());
          const center = row.y + row.height / 2;
          return controls.every(box => Math.abs(box.y + box.height / 2 - center) < 2)
            && controls.every((box, i) => !i || box.x >= controls[i - 1].right);
        }"""
    ), "r opened outside the target's horizontal margin item"

    # Condensation follows the complete row's available width, not a permanent compact
    # variant chosen by the suggestion or by `r`.
    resized(page, 2400, 900)
    expect(suggestion_item).not_to_have_class(re.compile(r"lf-condensed"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-action-label")
    ).to_be_visible()
    expect(
        suggestion_item.locator(".lf-sug-reject .lf-margin-action-label")
    ).to_be_visible()
    accept.focus()
    page.keyboard.press("r")
    expect(reactions.locator(".lf-react:visible")).to_have_count(6)
    expect(reactions.locator(".lf-react .lf-margin-action-label").first).to_be_visible()

    # The shared behavior belongs to the target item, not specifically to a
    # suggestion: focusing the draft's resting Edit action extends that same item.
    page.keyboard.press("Escape")
    draft_controls.locator(".lf-draft-pencil").focus()
    page.keyboard.press("r")
    expect(
        draft_item.locator(":scope > .lf-margin-reactions .lf-react:visible")
    ).to_have_count(6)

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
    for digit in str(draft_address["number"]):
        page.keyboard.press(digit)
    if draft_address["number"] * 10 <= draft_address["count"]:
        page.keyboard.press("Enter")
    expect(draft_item.locator(".lf-draft-pencil")).to_be_focused()
    expect(page.locator(".lf-page-map-sheet")).to_be_hidden()

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
    item = page.locator(".lf-margin-item").filter(
        has=page.locator(".lf-margin-reactions")
    )
    expect(item).to_have_count(1)
    assert abs(item.bounding_box()["y"] - paragraph.bounding_box()["y"]) <= 6

    item.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["anchor"]["section"] == "s-how" and sent["anchor"]["quote"]
    receipt = page.locator(".lf-margin-item").filter(has=page.locator(".lf-reacts"))
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
                "minHeight": "30px",
                "radius": "999px",
                "visibleWord": "first controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "minHeight": "30px",
                "radius": "999px",
                "visibleWord": "nested controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "minHeight": "30px",
                "radius": "999px",
                "visibleWord": "second controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "minHeight": "30px",
                "radius": "999px",
                "visibleWord": "slot a controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "minHeight": "30px",
                "radius": "999px",
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


def test_the_preview_stands_in_the_room_the_page_has_beside_the_panel(browser, serve):
    """An open panel takes its strip out of the page, so the margin's preview keeps to
    what is left. Placed against the window instead, a card the reader left open stands
    over the panel — and the box it covers first is the narrowing box at the top of it,
    whose ring then reads as a control the reader can see only half of."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 1600, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    preview_box = preview.bounding_box()
    panel_box = page.locator(".lf-panel").bounding_box()
    room_right = page.evaluate("() => document.body.getBoundingClientRect().right")
    assert panel_box["x"] < page.evaluate("innerWidth"), (
        f"the panel is not standing beside the page, so this reads nothing: {panel_box}"
    )
    assert preview_box["x"] + preview_box["width"] <= panel_box["x"] + 0.5, (
        f"the preview stands in the panel: {preview_box} against {panel_box}"
    )
    assert preview_box["x"] + preview_box["width"] <= room_right + 0.5, (
        f"the preview stands outside the page's room: {preview_box} of {room_right}"
    )
    assert preview_box["x"] >= 0, (
        f"the preview is off the left of the window: {preview_box}"
    )

    assert errors == []
    page.close()


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location is one marker, even when several kinds of work meet there.

    Hover and keyboard inspection are readings, not travel. They may preview and
    outline the destination, but must preserve the user's place in the document.
    """
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(marker).to_have_attribute(
        "aria-label", re.compile(r"Comment, Outcome, \d+ of")
    )

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))
    main_box = page.locator("main").bounding_box()
    preview_box = preview.bounding_box()
    assert preview_box["x"] < main_box["x"] + main_box["width"]
    assert preview_box["x"] >= 0
    assert preview_box["x"] + preview_box["width"] <= page.evaluate("innerWidth")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    marker.click()
    expect(marker).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview-action")).to_have_count(1)
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-thread textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-thread .lf-conversation-thread")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    held = marker.get_attribute("aria-label")
    page.keyboard.press("ArrowDown")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    assert page.evaluate("() => document.activeElement.matches('.lf-margin-marker')")
    assert page.locator(":focus").get_attribute("aria-label") != held

    assert errors == []
    page.close()


def test_a_thread_can_be_answered_in_the_margin_without_opening_threads(browser, serve):
    """The anchored thread is the margin's primary interaction surface."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.click()
    thread = page.locator(".lf-margin-thread")
    reply = thread.locator("textarea")

    expect(thread.locator(".lf-conversation-body")).to_have_text(
        COMMENT_ON_DECISION["text"]
    )
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
    root_id = thread.locator(".lf-conversation-thread").get_attribute("data-thread")
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "reply" and event.get("parent") == root_id
    ]
    assert [event["text"] for event in replies] == [
        "Yes. One visit can cover both jobs."
    ]

    assert errors == []
    page.close()


def test_an_unpinned_preview_leaves_with_keyboard_focus(browser, serve):
    """A preview reached from the margin is a stop on the page's Tab walk, not a layer
    left over the control the reader reaches next."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    preview = page.locator(".lf-margin-preview")

    marker.focus()
    expect(preview).to_be_visible()
    page.locator(".lf-margin-preview-close").focus()
    expect(page.locator(".lf-margin-preview-close")).to_be_focused()
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()

    expect(toggle).to_be_focused()
    assert preview.is_hidden()
    expect(page.locator("#bracket")).not_to_have_class(re.compile(r"lf-margin-target"))
    assert errors == []
    page.close()


def test_only_a_page_with_threads_reserves_the_conversation_margin(browser, serve):
    """Other map meanings keep their narrow rail until a thread needs the card."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION])
    )

    def padding_right():
        return page.locator("body").evaluate(
            "body => getComputedStyle(body).paddingRight"
        )

    assert padding_right() == "57px"

    events_model.append_event(serve.page_dir, COMMENT_ON_DECISION)
    told(page)
    assert padding_right() == "384px"

    assert errors == []
    page.close()


def test_the_margin_keeps_its_page_coordinate_while_the_reader_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    target = page.locator("#bracket")

    def offset():
        return marker.bounding_box()["y"] - target.bounding_box()["y"]

    before = offset()
    page.evaluate(
        "() => document.scrollingElement.scrollBy({top: 320, behavior: 'instant'})"
    )
    page.evaluate(
        "() => import('/runtime/margin-layout.js').then(({layoutMarginRows}) => layoutMarginRows())"
    )
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

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    toggle.click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
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
    ).to_have_text("3")
    expect(actions).to_have_count(5)
    expect(actions.first).to_be_focused()

    assert errors == []
    page.close()


def test_an_open_desktop_preview_reconciles_arriving_meanings(browser, serve):
    """A pinned marker card stays current while its semantic location is retained."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    actions = page.locator(".lf-margin-preview-action")
    expect(actions).to_have_count(1)
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
    expect(marker.locator(".lf-margin-count")).to_have_text("3")
    expect(actions).to_have_count(1)
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
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    action = page.locator(".lf-margin-preview-action")
    action.focus()
    expect(action).to_be_focused()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    (serve.page_dir / "index.html").write_text(
        DECISION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(action).to_be_focused()
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
