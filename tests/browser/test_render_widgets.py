"Board, suggestion, question, and widget composition tests."

import json

import pytest
from interact_support import (
    wait_for,
)
from journeys.test_render_widgets import MOTION_SAMPLE_CONTENT
from playwright.sync_api import expect
from render_cases_interaction import (
    NESTED_PROPOSAL_PAGE,
)
from render_cases_navigation import (
    actions,
)
from render_cases_widgets import (
    BAD_CHARTS,
)
from render_harness import (
    BOARD_PAGE,
    consume_browser_errors,
    leaf_page,
    open_page,
    round_trip,
    undo,
    write,
)

from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("route", ["pointer", "keyboard"])
def test_board_moves_preserve_live_sample_and_control_state(browser, serve, route):
    """A preview names the move; only the original document and widgets stay live."""
    source = BOARD_PAGE.replace(
        "<strong>Heated perch</strong>",
        "<strong>Heated perch</strong>" + MOTION_SAMPLE_CONTENT,
    )
    page = open_page(browser, serve(source))
    live = page.frame_locator("#card-sample iframe")
    live.locator("#sample-beta").click()
    live.locator("#sample-draft .lf-draft-body").click()
    editor = live.locator("#sample-draft leaf-text")
    write(editor, "Edited sample draft")
    frame = page.locator("#card-sample iframe")
    frame.evaluate("frame => window.originalSampleDocument = frame.contentDocument")
    sample_url = frame.evaluate("frame => frame.src").rstrip("/")
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    card = page.locator("#card-heater")
    original = card.element_handle()
    card.evaluate("""card => {
      const radio = document.createElement('input');
      radio.type = 'radio'; radio.name = 'retained'; radio.checked = true;
      radio.dataset.lfGen = '1'; card.append(radio);
    }""")
    grip = card.locator(":scope > .lf-grip")
    grip.focus()
    page.keyboard.press("Space")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Escape")
    expect(page.locator("#col-todo > #card-heater")).to_have_count(1)
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    assert not actions(serve.page_dir)

    if route == "keyboard":
        grip.focus()
        page.keyboard.press("Space")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Space")
    else:
        grip.scroll_into_view_if_needed()
        page.evaluate("""async () => {
          const {default: Sortable} = await window.__lfVendorImport("sortable.esm.js");
          window.previewAllocations = 0;
          for (const column of document.querySelectorAll('#sprint > lf-column')) {
            const owner = Sortable.get(column), produce = owner.option('cloneElement');
            owner.option('cloneElement', card => {
              window.previewAllocations++; return produce(card);
            });
          }
          window.previewFirstPaint = false;
          window.boardDragInput = [];
          // Keep the actual hit and moving geometry: a later snapshot cannot tell
          // whether a coordinate press reached the grip or Sortable cancelled it.
          const grip = document.querySelector('#card-heater > .lf-grip');
          for (const type of ['pointerdown', 'pointermove', 'pointerup', 'pointercancel']) {
            document.addEventListener(type, event => {
              window.boardDragInput.push({
                type, at: event.timeStamp, x: event.clientX, y: event.clientY,
                target: [event.target.tagName, event.target.id, event.target.getAttribute('class')],
                gripHit: event.composedPath().includes(grip),
                ...(type === 'pointerdown' ? {
                  grip: grip.getBoundingClientRect().toJSON(), scroll: [scrollX, scrollY],
                } : {}),
              });
            }, {capture: true});
          }
          new MutationObserver((records, observer) => {
            const preview = document.querySelector('.lf-motion-preview.lf-inhand');
            if (!preview) return;
            observer.disconnect();
            requestAnimationFrame(() => window.previewFirstPaint =
              preview.textContent === 'Heated perch' && preview.getBoundingClientRect().height > 0);
          }).observe(document.body, {childList: true, subtree: true});
        }""")
        box = grip.bounding_box()
        source_box = card.bounding_box()
        assert box and source_box
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 20, y + 35, steps=8)
        preview = page.locator(".lf-motion-preview.lf-inhand")
        try:
            expect(preview).to_have_text("Heated perch")
        except AssertionError as error:
            error.add_note(
                "Board drag input: "
                + json.dumps(page.evaluate("window.boardDragInput"))
            )
            raise
        expect(page.locator(".lf-motion-preview")).to_have_count(1)
        assert page.evaluate("window.previewAllocations") == 2
        expect(page.locator("#col-todo > lf-card")).to_have_count(2)
        expect(preview.locator("*")).to_have_count(0)
        expect(preview).to_have_attribute("inert", "")
        page.wait_for_function("window.previewFirstPaint")
        bounds = preview.bounding_box()
        assert bounds and bounds["height"] <= 56
        assert bounds["width"] == pytest.approx(source_box["width"], abs=0.02)
        assert bounds["x"] <= x + 20 <= bounds["x"] + bounds["width"]
        expect(card.locator("input[type=radio]")).to_be_checked()
        expect(
            page.locator("#card-code, #card-tree, #card-sample iframe")
        ).to_have_count(3)
        destination = page.locator("#col-done").bounding_box()
        assert destination
        page.mouse.move(
            destination["x"] + destination["width"] / 2, destination["y"] + 40, steps=15
        )
        page.mouse.up()
        expect(preview).to_have_count(0)
    expect(page.locator("#col-done > #card-heater")).to_have_count(1)
    round_trip(page)
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    expect(live.locator("#sample-beta")).to_have_attribute("selected", "")
    card.click(position={"x": 10, "y": 10})
    undo(page)
    expect(page.locator("#col-todo > #card-heater")).to_have_count(1)
    assert original.evaluate("card => card === document.querySelector('#card-heater')")
    assert frame.evaluate(
        "frame => frame.contentDocument === window.originalSampleDocument"
    )
    expect(editor).to_have_js_property("value", "Edited sample draft")
    assert not [
        url
        for url in requests
        if url.rstrip("/") == sample_url or url.rstrip("/").endswith("/api/samples")
    ]


def test_a_moved_card_keeps_its_title_beside_its_grip(browser, serve):
    """A card the user moved says so to a screen reader with a word written before its
    title, and the title still stands where it stood, level with the grip, rather than
    dropping below the grip's room and pushing every card under it down."""
    page = open_page(browser, serve(BOARD_PAGE))
    title_top = """card => card.querySelector(':scope > strong').getBoundingClientRect().top
      - card.getBoundingClientRect().top"""
    card = page.locator("#card-heater")
    before = card.evaluate(title_top)
    card.locator(".lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(card.locator(":scope > .lf-quiet")).to_have_text("my change")
    assert card.evaluate(title_top) == before


def test_suggestion_emphasis_skips_generated_interface_between_changed_words(
    browser, serve
):
    """A changed span may cross a nested widget without painting its generated UI."""
    page = open_page(browser, serve(NESTED_PROPOSAL_PAGE))
    page.locator('[data-lf-margin-for="route-ask"] .lf-margin-marker').click()
    page.locator("#route .lf-pick").first.focus()
    badges = page.locator("#route > lf-option > .lf-key-badge")
    expect(
        page.locator("#route > lf-option > .lf-key-badge[data-lf-binding-badge]")
    ).to_have_count(2)
    expect(badges).to_have_text(["1", "2"])

    assert page.locator("#nested-change > lf-new > p").evaluate(
        """node => [...(CSS.highlights.get('lf-sug-ins') ?? [])]
          .some(range => range.intersectsNode(node.firstChild))"""
    ), "the proposal has to carry word-level insertion emphasis"
    assert badges.evaluate_all(
        """nodes => {
          const ranges = [...(CSS.highlights.get('lf-sug-ins') ?? [])];
          return nodes.map(node =>
            ranges.some(range => range.intersectsNode(node.firstChild)));
        }"""
    ) == [
        False,
        False,
    ], (
        "the authored change's emphasis crossed into the obligation's generated key hints"
    )


def test_a_body_the_module_cannot_draw_says_why_over_its_source(browser, serve):
    """The body is the author's, and the author is the only party who can fix it, so a
    refusal says what is wrong and keeps the source under it: code that does not parse,
    in the parser's own words, a chart with no name for a user who cannot see it, a call
    to something Plot does not export, a drawing Plot already made, which is how Plot's
    own examples end, a height the page could not have laid out before the chart
    drew, and an offset given per datum where Plot takes one number. The author hears the same words as the page's
    `error` event, naming the chart, since the user seeing the box is not the author
    seeing it."""
    said = {
        "bad-syntax": "Unexpected token",
        "bad-label": "ariaLabel",
        "bad-mark": "Plot.barz is not a function",
        "bad-drawn": "rather than Plot.plot(...)",
        "bad-height": "as data-height on the element",
        "bad-offset": "marks[0] (text) has a dy that is not a number",
    }
    # Each refusal is the chart's own, so every bad body stands on one page.
    source = leaf_page(
        "bad charts",
        '<h1 id="t">Bad</h1>\n'
        + "\n".join(
            f'<lf-chart id="{chart_id}"><pre>\n{body}\n</pre></lf-chart>'
            for chart_id, body in BAD_CHARTS.items()
        ),
    )
    page = open_page(browser, serve(source))
    reports = {chart_id: f'<lf-chart id="{chart_id}"> failed: ' for chart_id in said}
    for chart_id, words in said.items():
        expect(page.locator(f"#{chart_id} .lf-error")).to_contain_text(words)
        # The source stays under the message: a refusal the user cannot check is half a
        # refusal.
        expect(page.locator(f"#{chart_id} .lf-error pre")).to_contain_text("marks")
    reported = wait_for(
        lambda: [
            event["text"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ],
        lambda texts: len(texts) >= len(said),
        failure="not every refused chart reached the log as an error",
    )
    consume_browser_errors(page, *reports.values())
    for chart_id, words in said.items():
        mine = [text for text in reported if text.startswith(reports[chart_id])]
        assert len(mine) == 1 and words in mine[0], (chart_id, reported)
    assert len(reported) == len(said), reported
