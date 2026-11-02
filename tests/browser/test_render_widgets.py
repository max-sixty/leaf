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


import re

import turbohtml
from interact_support import (
    _start,
)
from render_harness import (
    resized,
    sending,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.widgets import PLAYGROUND_PAGE
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import service as service_model
from leaf import thread as thread_model
from leaf.render_checks import wait_until_ready


@pytest.mark.shifts_unsurveyed
def test_notification_configuration_becomes_a_commentable_local_artifact(
    browser, serve
):
    """The example's instruction is a complete task through Leaf's existing loop.

    A playground action enters the ordinary event log, pickup and a work claim use the
    same delivery projection as an agent in a harness, and the agent writes a real local file.
    The page exposes that file through data, then a user comment changes the file and
    remains anchored on the revised result.
    """
    source_path = (
        Path(__file__).parents[2] / "examples" / "notification-playground.html"
    )
    source = source_path.read_text(encoding="utf-8")
    page = open_page(browser, live_url(serve(source_path)))
    playground = page.locator("#notification-playground")

    playground.get_by_role("button", name="Needs attention").click()
    playground.get_by_role("radio", name="Status strip", exact=True).click()
    page.locator('lf-playground-control[name="title"] input').fill(
        "Checkout needs attention"
    )
    expect(playground).to_have_attribute("data-playground-tone", "urgent")
    expect(playground).to_have_attribute("data-playground-compact", "true")
    expect(playground).to_have_attribute("data-playground-format", "status strip")
    expect(
        page.locator(".notification-demo-card-banner").first
    ).to_have_accessible_name("Checkout needs attention")
    expect(
        page.locator(".notification-demo-card-status-strip").first
    ).to_have_accessible_name("Checkout needs attention")
    with sending(page, "the notification configuration"):
        playground.get_by_role("button", name="Create notification").click()
    # The control says the configuration is sent, and offers to withdraw it.
    expect(playground.get_by_role("button", name="Undo choice")).to_be_enabled()
    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "notification-playground"
    )
    assert action["detail"]["values"] == {
        "accent": "#b6533c",
        "compact": True,
        "events": 4,
        "format": "status strip",
        "radius": 10,
        "show-owner": True,
        "title": "Checkout needs attention",
        "tone": "urgent",
    }
    assert action["detail"]["instruction"] == (
        "Build the status strip deployment notification as deployment-notification.html. "
        "Use urgent styling, 10px corners, #b6533c accents, compact spacing set to true, "
        "owner visibility set to true, and title it Checkout needs attention. Exercise 4 "
        "concurrent release events in its browser test, then show me the generated source "
        "here for review."
    )

    logged_action = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["id"] == action["id"]
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [logged_action],
            session="notification-agent",
            turn="create-artifact",
        )
    with (
        service_model.PageTransaction(serve.page_dir) as receipt_page,
        delivery_model.receive_batch(
            receipt_page,
            {"events": [{"seq": logged_action["seq"], "id": logged_action["id"]}]},
            session_id=None,
        ),
    ):
        pass
    started = _start(
        serve.page_dir, logged_action["id"], "creating deployment-notification.html"
    )
    assert started.exit_code == 0, started.output
    told(page)
    expect(
        page.locator('[data-lf-margin-for="notification-playground"] .lf-margin-marker')
    ).to_have_attribute(
        "aria-description", re.compile("creating deployment-notification")
    )

    artifact = serve.page_dir / "deployment-notification.html"
    first_artifact = """<!doctype html>
<html lang="en">
<title>Checkout needs attention</title>
<style>
body { font-family: system-ui, sans-serif; }
.notification { border-top: 5px solid #b6533c; border-radius: 10px; padding: 8px 12px; }
</style>
<article class="notification">
  <h1>Checkout needs attention</h1>
  <p>Version 2.8.0 changed the checkout service. Review the deployment run and current service health.</p>
  <p><strong>Owner:</strong> Payments platform</p>
</article>
</html>
"""
    artifact.write_text(first_artifact, encoding="utf-8")
    # The result is a document: the configuration folds away above the artifact, so
    # the page leaves the workspace Layout. Select the authored identities rather
    # than copying their class lists and source whitespace into this revision writer.
    result = turbohtml.parse(source)
    for control in result.select("#notification-playground lf-playground-control"):
        value = action["detail"]["values"][control.attrs["name"]]
        control.attrs["value"] = (
            str(value).lower() if isinstance(value, bool) else str(value)
        )
    workspace = result.select_one("#notification-workspace")
    assert workspace is not None
    workspace.attrs["class"] = "layout-column"
    artifact_section = result.select_one("#notification-artifact")
    configuration = turbohtml.E(
        "details",
        {"id": "notification-configuration", "open": ""},
        turbohtml.E("summary", "Original configuration"),
    )
    select_one_result = result.select_one("#notification-ask")
    assert select_one_result is not None
    select_one_result.wrap(configuration)
    configuration.insert_before(turbohtml.E("h1", "Review the deployment notification"))
    assert artifact_section is not None
    artifact_section.attrs.pop("hidden")
    select_one_result_2 = artifact_section.select_one("#notification-artifact-source")
    assert select_one_result_2 is not None
    select_one_result_2.attrs["label"] = "deployment-notification.html"
    workspace.append(artifact_section)
    result_source = result.serialize()
    assert "notification-configuration" in result_source
    assert "layout-workspace" not in result_source
    assert 'notification-artifact" hidden' not in result_source
    data_model.cmd_data_set(
        serve.page_dir,
        "notification-artifact",
        artifact.read_text(encoding="utf-8"),
    )
    first_result = stamp_page(
        serve.page_dir,
        result_source,
        "Created deployment-notification.html",
    )
    wait_for_revision(page, first_result["revision"])

    source_widget = page.locator("#notification-artifact-source")
    expect(source_widget).to_be_visible()
    assert source_widget.evaluate(
        "source => source.closest('lf-playground-preview') === null"
    )
    expect(source_widget.locator("code")).to_contain_text(
        "<title>Checkout needs attention</title>"
    )
    expect(
        page.locator('[data-lf-margin-for="notification-playground"]')
    ).to_have_count(0)

    configuration = page.locator("#notification-configuration")
    expect(configuration).to_have_attribute("open", "")
    expect(
        configuration.locator('lf-playground-control[name="title"] input')
    ).to_have_value("Checkout needs attention")
    configuration.locator(":scope > summary").click()
    expect(configuration).not_to_have_attribute("open", "")
    configuration.locator(":scope > summary").click()
    receipt_copy = page.locator(
        ".notification-demo-card-banner .notification-demo-detail"
    ).first
    expect(receipt_copy).to_be_visible()
    # The preview is its own scroller while the workspace fills the window, and a
    # user selects the receipt where that pane shows it.
    receipt_copy.scroll_into_view_if_needed()
    receipt_copy.select_text()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "Add a link to the deployment run without changing this receipt copy.",
    )
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    comment = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "comment"
    )
    assert comment["anchor"]["section"] == "notification-simulator"
    assert comment["anchor"]["quote"] == ("Version 2.8.0 passed all 18 release checks.")
    logged_comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["id"] == comment["id"]
    )

    with service_model.PageTransaction(serve.page_dir) as transaction:
        delivery_model.record_pickup(
            transaction,
            [logged_comment],
            session="notification-agent",
            turn="refine-artifact",
        )
    with (
        service_model.PageTransaction(serve.page_dir) as receipt_page,
        delivery_model.receive_batch(
            receipt_page,
            {"events": [{"seq": logged_comment["seq"], "id": logged_comment["id"]}]},
            session_id=None,
        ),
    ):
        pass
    second_artifact = first_artifact.replace(
        "</article>",
        '  <footer><a href="/deployments/2.8.0">Open deployment run</a></footer>\n'
        "</article>",
    )
    artifact.write_text(second_artifact, encoding="utf-8")
    data_model.cmd_data_set(
        serve.page_dir,
        "notification-artifact",
        artifact.read_text(encoding="utf-8"),
    )
    refined_source = result_source.replace(
        "<h1>Review the deployment notification</h1>",
        "<h1>Deployment notification revised</h1>",
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": comment["id"]},
        "Added the deployment-run link to the artifact.",
    )
    refined = stamp_page(
        serve.page_dir,
        refined_source,
        "Added the deployment-run link",
    )
    wait_for_revision(page, refined["revision"])

    expect(page.locator("#notification-artifact-source code")).to_contain_text(
        '<a href="/deployments/2.8.0">Open deployment run</a>'
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    marked = page.evaluate(
        "() => [...CSS.highlights.get('lf-mark')].map(range => range.toString()).join('')"
    )
    assert " ".join(marked.split()) == ("Version 2.8.0 passed all 18 release checks.")
    assert artifact.read_text(encoding="utf-8") == second_artifact


@pytest.mark.shifts_unsurveyed
def test_a_playground_preset_reset_copy_and_narrow_layout_share_the_same_state(
    browser, serve
):
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(PLAYGROUND_PAGE), context=context)
    playground = page.locator("#card-playground")
    expect(playground.get_by_role("group", name="Starting points")).to_be_visible()
    expect(playground.get_by_role("group", name="Controls")).to_be_visible()

    playground.get_by_role("button", name="Dense").click()
    expect(playground.get_by_role("button", name="Dense")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert playground.evaluate("root => root.values") == {
        "accent": "#4f766f",
        "compact": True,
        "radius": 4,
        "title": "Field note",
        "tone": "bold",
    }
    playground.get_by_role("slider", name="Corner radius").press("ArrowRight")
    expect(playground.get_by_role("button", name="Dense")).to_have_attribute(
        "aria-pressed", "false"
    )
    playground.get_by_role("button", name="Dense").click()
    # Copy is the code block's control, in the head of the popover the instruction
    # opens in.
    pane = playground.locator(".lf-playground-instruction-region")
    copy = pane.get_by_role("button", name="Copy instruction")
    pane.scroll_into_view_if_needed()
    pane.get_by_role("button", name="Show instruction").click()
    pane.hover()
    copy.click()
    assert page.evaluate("navigator.clipboard.readText()") == (
        "Use a 4px radius, compact spacing set to true, a bold tone, #4f766f accents, "
        "and the title Field note."
    )

    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values")["radius"] == 12
    pane.get_by_role("button", name="Show instruction").press("Enter")
    page.keyboard.press("Tab")
    expect(copy).to_be_focused()
    copy.press("Enter")
    assert "12px radius" in page.evaluate("navigator.clipboard.readText()")
    resized(page, 420, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 420
    assert " " not in playground.evaluate(
        "root => getComputedStyle(root).gridTemplateColumns"
    )


@pytest.mark.shifts_unsurveyed
def test_structured_data_explorer_keeps_one_aggregate_query_configuration(
    browser, serve
):
    source = Path(__file__).parents[2] / "examples" / "data-explorer.html"
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(source), context=context)
    playground = page.locator("#release-query-playground")
    rows = page.locator(".query-row")

    expect(rows).to_have_count(2)
    assert playground.evaluate("root => root.values") == {
        "filters": {
            "order": ["filter-1", "filter-2"],
            "rows": [
                {
                    "field": "region",
                    "id": "filter-1",
                    "operator": "is",
                    "value": "europe",
                },
                {
                    "field": "risk",
                    "id": "filter-2",
                    "operator": "above",
                    "value": "40",
                },
            ],
        },
        "limit": 4,
    }
    expect(page.locator(".query-result-count")).to_have_text("2 releases shown")

    rows.nth(1).get_by_label("Value").fill("80")
    expect(page.locator(".query-result-count")).to_have_text("1 release shown")
    # Moving a sibling row must retain the native field, caret and edit history.
    editor = page.locator('input[name="filter-1-value"]')
    editor.focus()
    editor.press("End")
    editor.press_sequentially("x")
    editor.press("ArrowLeft")
    rows.nth(1).get_by_role("button", name="Move filter 2 up").evaluate(
        "button => button.click()"
    )
    expect(editor).to_be_focused()
    assert editor.evaluate("input => input.selectionStart") == len("europe")
    editor.press("ControlOrMeta+z")
    expect(editor).to_have_value("europe")
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    page.get_by_role("button", name="Add filter").click()
    expect(rows).to_have_count(3)
    expect(rows.nth(2).get_by_label("Value")).to_be_focused()
    rows.nth(2).get_by_label("Value").fill("risk")
    expect(page.locator(".query-result-count")).to_have_text("1 release shown")
    rows.nth(2).get_by_role("button", name="Remove filter 3").click()
    expect(rows).to_have_count(2)

    playground.get_by_role("button", name="Up to 6 results").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_value("6")
    playground.get_by_role("button", name="Up to 4 results").click()
    expect(
        playground.locator('lf-playground-control[name="limit"]').get_by_role("slider")
    ).to_have_value("4")
    instruction = page.locator("#release-query-instruction")
    expect(instruction).to_contain_text("risk above 80 and region is europe")
    playground.get_by_role("button", name="Show instruction").click()
    playground.get_by_role("button", name="Copy instruction").click()
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied == instruction.inner_text()

    page.reload()
    wait_until_ready(page)
    expect(rows).to_have_count(2)
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-2",
        "filter-1",
    ]
    expect(instruction).to_contain_text("risk above 80 and region is europe")
    playground.get_by_role("button", name="Reset").click()
    assert playground.evaluate("root => root.values.filters.order") == [
        "filter-1",
        "filter-2",
    ]
    expect(instruction).to_contain_text("region is europe and risk above 40")
    rows.nth(1).get_by_role("button", name="Remove filter 2").click()
    rows.first.get_by_role("button", name="Remove filter 1").click()
    expect(rows).to_have_count(0)
    expect(instruction).to_contain_text("Apply no filters")
    expect(page.locator(".query-result-count")).to_have_text("4 releases shown")
    playground.get_by_role("button", name="Up to 6 results").click()
    expect(page.locator(".query-result-count")).to_have_text("6 releases shown")
    playground.get_by_role("button", name="Up to 4 results").click()
    expect(page.locator(".query-result-count")).to_have_text("4 releases shown")
    playground.get_by_role("button", name="Reset").click()
    rows.first.get_by_label("Value").fill("asia")
    expect(instruction).to_contain_text("region is asia and risk above 40")

    with sending(page, "the release query"):
        playground.get_by_role("button", name="Build query").click()
    action = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "release-query-playground"
    )
    assert action["detail"] == {
        "instruction": instruction.inner_text(),
        "values": playground.evaluate("root => root.values"),
    }
    page.reload()
    wait_until_ready(page)
    expect(rows.first.get_by_label("Value")).to_have_value("asia")
    expect(instruction).to_contain_text("region is asia and risk above 40")
    undo(page)
    expect(rows.first.get_by_label("Value")).to_have_value("asia")
    playground.get_by_role("button", name="Reset").click()
    expect(rows.first.get_by_label("Value")).to_have_value("europe")
    expect(instruction).to_contain_text("region is europe and risk above 40")
    resized(page, 480, 760)
    assert page.evaluate("document.documentElement.scrollWidth") == 480
    resized(page, 1100, 320)
    expect(page.locator("#release-query-ask")).to_be_visible()
