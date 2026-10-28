"Board, suggestion, question, and widget composition tests."

import json
from pathlib import Path

import pytest
from interact_support import (
    wait_for,
)
from journeys.test_render_widgets import MOTION_SAMPLE_CONTENT
from playwright.sync_api import expect
from render_cases_interaction import (
    NESTED_PROPOSAL_PAGE,
    live_url,
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

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("destination", ["call", "patch"])
def test_focus_reactions_keep_a_projected_data_target(browser, serve, destination):
    """Light-DOM data and its shadow-DOM destination keep exact identity."""
    example = Path(__file__).parents[2] / "examples" / "pr-walkthrough.html"
    page = open_page(browser, live_url(serve(example)))
    page.get_by_role("tab", name="CallDiff").click()
    location = (
        page.locator("#pr-call-diagram")
        .get_by_role("link", name="src/summary.rs:259")
        .first
    )
    # Reach the real link through the browser's tab order. The source case reads
    # keyboard focus inside a generated datum, rather than focusing the datum directly.
    for _ in range(40):
        page.keyboard.press("Tab")
        if location.evaluate("node => node.matches(':focus')"):
            break
    expect(location).to_be_focused()
    assert location.evaluate("node => node.matches(':focus-visible')")
    target = location.locator("xpath=..")
    if destination == "patch":
        page.keyboard.press("Enter")
        target = page.locator(
            '#pr-exact-patch [data-lf-datum=\'["src/summary.rs","new",259]\']'
        )
        expect(target).to_be_focused()
        expect(page.locator(".lf-live")).to_have_text(
            "Opened src/summary.rs:259 in the exact patch"
        )
        expect(target).to_be_in_viewport()
    datum = target.get_attribute("data-lf-datum")
    owner = target.get_attribute("data-lf-projection")
    revision = target.get_attribute("data-lf-source-revision")
    assert datum and owner and revision
    page.keyboard.press("e")
    expect(
        page.locator('[data-lf-margin-entry-owner="responses"]:visible')
    ).not_to_have_count(0)
    page.keyboard.press("1")
    round_trip(page)
    reaction = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "comment" and event.get("token")
    )
    assert reaction["anchor"]["section"] == owner
    assert reaction["anchor"]["datum"] == datum
    assert reaction["anchor"]["source_revision"] == revision


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
    expect(live.locator("#sample-beta")).to_have_attribute("chosen", "")
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


def test_a_playground_dresses_each_sample_child_and_never_its_own_page(browser, serve):
    """A candidate that restyles a whole page lives in a sample's template and keys on
    that child's root. Each child the sample presents, the first and one a reset makes,
    wears the playground's values from its first paint, and the page around the
    playground keeps its own styling."""
    source = leaf_page(
        "sample playground",
        """
<h1>Tone playground</h1>
<p id="host-note">The page around the playground.</p>
<lf-ask id="tone-ask">
  <h2>Which tone?</h2>
  <lf-playground id="tone-playground">
    <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
      <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
      <lf-playground-choice value="loud" label="Loud"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-preview>
      <lf-sample id="tone-sample" label="tone sample">
        <template id="tone-page" data-sample>
          <style>:root[data-playground-tone="loud"] p { color: rgb(200, 0, 0); }</style>
          <h1 id="child-title">Child page</h1>
          <p id="child-note">The page the candidate restyles.</p>
          <lf-draft id="child-draft"><pre>A draft the candidate restyles too.</pre></lf-draft>
        </template>
      </lf-sample>
    </lf-playground-preview>
    <lf-playground-output id="tone-instruction">Use the
      <lf-playground-value for="tone"></lf-playground-value> tone.</lf-playground-output>
  </lf-playground>
</lf-ask>
""",
    )
    page = open_page(browser, serve(source))
    child = page.frame_locator("#tone-sample iframe")
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "quiet")

    page.get_by_role("radio", name="Quiet", exact=True).press("ArrowRight")
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "loud")
    expect(child.locator("#child-note")).to_have_css("color", "rgb(200, 0, 0)")
    assert (
        page.locator("#host-note").evaluate("note => getComputedStyle(note).color")
        != "rgb(200, 0, 0)"
    )

    # The reset child has an opaque origin. Collect its paints there, then request
    # the whole sequence after Reset completes across the browsing-context boundary.
    # The parent's answer to the child's connection is held for a few frames, as a
    # busy machine holds it: no frame the child shows meanwhile may be undressed,
    # including the draft's prepainted markdown, which makes itself visible.
    page.add_init_script("""(() => {
      if (window === top) return;
      const paints = [];
      let sampling = true;
      const tick = () => {
        for (const words of document.querySelectorAll('#child-note, #child-draft p'))
          if (words.checkVisibility({visibilityProperty: true, opacityProperty: true}))
            paints.push(getComputedStyle(words).color);
        if (sampling) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      window.addEventListener('message', event => {
        if (event.source !== parent || !event.ports.length || event.lfHeld) return;
        event.stopImmediatePropagation();
        setTimeout(() => {
          const held = new MessageEvent('message', {
            data: event.data, source: event.source, ports: [...event.ports],
          });
          held.lfHeld = true;
          window.dispatchEvent(held);
        }, 200);
      }, true);
      window.addEventListener('message', event => {
        if (event.source !== parent || event.data?.type !== 'lf-test-tone-read')
          return;
        requestAnimationFrame(() => {
          sampling = false;
          parent.postMessage({type: 'lf-test-tone-paints', paints}, '*');
        });
      });
    })()""")
    page.locator("#tone-sample").evaluate("sample => sample.reset()")
    page.locator("#tone-sample").evaluate("""sample => {
      window.lfTonePaints = null;
      const frame = sample.querySelector('iframe');
      const receive = event => {
        if (event.source !== frame.contentWindow
            || event.data?.type !== 'lf-test-tone-paints') return;
        window.lfTonePaints = event.data.paints;
        window.removeEventListener('message', receive);
      };
      window.addEventListener('message', receive);
      frame.contentWindow.postMessage({type: 'lf-test-tone-read'}, '*');
    }""")
    page.wait_for_function("window.lfTonePaints !== null")
    painted = page.evaluate("window.lfTonePaints")
    assert painted and set(painted) == {"rgb(200, 0, 0)"}
    expect(child.locator(":root")).to_have_attribute("data-playground-tone", "loud")


def test_a_pointer_press_on_a_playground_control_leaves_the_user_in_the_preview(
    browser, serve
):
    """A candidate can draw only on what the user is located at in the preview, such as a
    focus treatment inside a sample child, so clicking a choice, a toggle, a preset or
    Reset, or dragging a slider, changes the candidate without taking the user out of
    the preview. A text control takes focus to be typed in, and from anywhere else a
    click takes the user to the control, where the next key acts."""
    source = leaf_page(
        "focus playground",
        """
<h1>Ring playground</h1>
<lf-ask id="ring-ask">
  <h2>Which ring?</h2>
  <lf-playground id="ring-playground">
    <lf-playground-preset label="Wide">
      <lf-playground-setting for="width" value="4"></lf-playground-setting>
    </lf-playground-preset>
    <lf-playground-control name="ring" label="Ring" kind="choice" value="thin">
      <lf-playground-choice value="thin" label="Thin"></lf-playground-choice>
      <lf-playground-choice value="thick" label="Thick"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control name="width" label="Width" kind="range" value="2" min="1" max="4" step="1" unit="px"></lf-playground-control>
    <lf-playground-control name="dim" label="Dim" kind="toggle" value="false"></lf-playground-control>
    <lf-playground-control name="note" label="Note" kind="text" value="hi"></lf-playground-control>
    <lf-playground-preview>
      <button id="preview-button" type="button">A candidate button</button>
      <lf-sample id="ring-sample" label="ring sample">
        <template id="ring-page" data-sample>
          <p>The page the candidate restyles.</p>
          <button id="child-button" type="button">The current location</button>
        </template>
      </lf-sample>
    </lf-playground-preview>
    <lf-playground-output>Use the
      <lf-playground-value for="ring"></lf-playground-value> ring.</lf-playground-output>
  </lf-playground>
</lf-ask>
""",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#ring-playground")
    child_button = page.frame_locator("#ring-sample iframe").locator("#child-button")
    focused = "button => button.matches(':focus') && document.hasFocus()"

    def values():
        return playground.evaluate("root => root.values")

    child_button.focus()
    assert child_button.evaluate(focused)
    page.get_by_role("radio", name="Thick", exact=True).click()
    assert values()["ring"] == "thick"
    assert child_button.evaluate(focused)

    playground.get_by_role("switch", name="Dim").click()
    assert values()["dim"] is True
    assert child_button.evaluate(focused), "switch"
    page.get_by_role("button", name="Wide", exact=True).click()
    assert values()["width"] == 4
    assert child_button.evaluate(focused), "preset"
    # A range takes native focus to be dragged, and the sample's location comes back
    # through its port after the press, so the user is back once that answer lands.
    child = page.locator("#ring-sample iframe").element_handle().content_frame()
    back_in_sample = (
        "() => document.querySelector('#child-button').matches(':focus')"
        " && document.hasFocus()"
    )
    slider = playground.get_by_role("slider", name="Width").bounding_box()
    page.mouse.click(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    assert values()["width"] == 1
    child.wait_for_function(back_in_sample)
    page.mouse.move(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        slider["x"] + slider["width"] - 2,
        slider["y"] + slider["height"] / 2,
        steps=4,
    )
    page.mouse.up()
    assert values()["width"] == 4
    child.wait_for_function(back_in_sample)
    sample = page.locator("#ring-sample")
    sample.evaluate(
        """sample => {
          const restore = sample.restoreCurrentLocation;
          sample.restoreCurrentLocation = () => {
            window.releaseRestore = () => {
              window.restoreDone = restore.call(sample);
            };
            return Promise.resolve(false);
          };
        }"""
    )
    page.mouse.click(slider["x"] + 2, slider["y"] + slider["height"] / 2)
    note = page.get_by_role("textbox", name="Note")
    note.focus()
    expect(note).to_be_focused()
    page.evaluate("window.releaseRestore()")
    assert page.evaluate("() => window.restoreDone") is False
    expect(note).to_be_focused()
    sample.evaluate("sample => delete sample.restoreCurrentLocation")
    child_button.focus()
    playground.locator(".lf-playground-reset").click()
    assert values()["ring"] == "thin"
    assert child_button.evaluate(focused)

    # The same holds in the preview's own light DOM.
    preview_button = page.locator("#preview-button")
    preview_button.focus()
    page.get_by_role("radio", name="Thick", exact=True).click()
    expect(preview_button).to_be_focused()

    # A text control is operated from focus, so a press there takes it.
    note = page.get_by_role("textbox", name="Note")
    note.click()
    expect(note).to_be_focused()

    # From outside the preview, a click takes the user to the control, and the next
    # key acts there.
    thin = page.get_by_role("radio", name="Thin", exact=True)
    thin.click()
    expect(thin).to_be_focused()
    page.keyboard.press("ArrowRight")
    assert values()["ring"] == "thick"
    playground.get_by_role("switch", name="Dim").click()
    page.keyboard.press("Space")
    assert values()["dim"] is False

    # A sample whose page stands on nothing holds no one there.
    page.frame_locator("#ring-sample iframe").get_by_text(
        "The page the candidate"
    ).click()
    thin.click()
    expect(thin).to_be_focused()


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
