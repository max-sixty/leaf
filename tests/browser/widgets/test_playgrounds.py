"""Playgrounds: first paint from authored defaults, the working state and contributor
drafts, sending a choice, quoted playgrounds, and their layout in a workspace."""

import re

import pytest
from interact_support import refused_on
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import actions
from render_harness import (
    ROOT,
    consume_browser_errors,
    displayed,
    holding,
    http_error_console,
    leaf_page,
    nudge,
    open_page,
    post_event,
    resized,
    round_trip,
    sending,
    stamp_page,
    told,
    undo,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from browser.widgets import (
    PLAYGROUND_PAGE,
)

pytestmark = pytest.mark.shifts_unsurveyed


CONTRIBUTOR_PAGE = leaf_page(
    "query configuration",
    """
<lf-ask id="query-ask"><h1>Choose the alert query</h1>
<lf-playground id="query-config">
  <lf-playground-control name="stream" label="Event stream" kind="choice" value="checkout">
    <lf-playground-choice value="checkout" label="Checkout"></lf-playground-choice>
    <lf-playground-choice value="billing" label="Billing"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preset label="Checkout stream">
    <lf-playground-setting for="stream" value="checkout"></lf-playground-setting>
  </lf-playground-preset>
  <lf-playground-preview>
    <label for="region-filter">Region filter</label>
    <input id="region-filter" type="text" value="eu-west-1">
  </lf-playground-preview>
  <lf-playground-output>Implement the selected query.</lf-playground-output>
</lf-playground></lf-ask>
<script type="module">
import {PAGE_INTERFACE} from "/runtime/widget-api.js";
document.addEventListener(PAGE_INTERFACE, event => {
  event.detail.present(Promise.resolve().then(() => {
    if (sessionStorage.getItem('delay-query-contributors')) return;
    const playground = document.querySelector('#query-config');
    const input = document.querySelector('#region-filter');
    const filters = playground.registerContributor('filters', {region: input.value});
    input.addEventListener('input', () => filters.set({region: input.value}));
    playground.subscribe(values => {
      if (input.value !== values.filters.region) input.value = values.filters.region;
    });
    playground.registerInstructionProvider(values =>
      `Implement ${values.stream} alerts for region ${values.filters.region}.`);
  }));
});
</script>
""",
)


def test_playground_authored_defaults_draw_before_its_behavior_loads(browser, serve):
    """The control declaration owns first paint, including text and attribute CSS."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    held = []
    page.route("**/widgets/lf-playground.js", lambda route: held.append(route))
    with page.expect_request("**/widgets/lf-playground.js"):
        page.goto(serve(PLAYGROUND_PAGE), wait_until="commit")
    displayed(page)
    assert held
    assert page.evaluate("() => !customElements.get('lf-playground')")
    card = page.locator("#playground-card")
    expect(card).to_have_css("border-radius", "12px")
    expect(card).to_have_css("border-top-color", "rgb(79, 118, 111)")
    expect(page.locator("#card-playground")).to_have_attribute(
        "data-playground-tone", "quiet"
    )
    assert (
        card.evaluate("e => getComputedStyle(e, '::before').content") == '"Field note"'
    )
    held.pop().continue_()
    wait_until_ready(page)
    expect(card).to_have_css("border-radius", "12px")


def test_a_playground_keeps_one_typed_working_state_until_the_user_chooses(
    browser, serve
):
    """The accent is typed in capitals, so the state the page keeps, writes into its
    instruction and sends is the colour's one lowercase spelling."""
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")
    before = len(events_model.read_events(serve.page_dir))
    changes = playground.evaluate(
        """root => {
          window.playgroundChanges = [];
          root.subscribe(values => window.playgroundChanges.push(values));
          return root.values;
        }"""
    )
    assert changes == {
        "accent": "#4f766f",
        "compact": False,
        "radius": 12,
        "title": "Field note",
        "tone": "quiet",
    }

    radius = playground.get_by_role("slider", name="Corner radius")
    for _ in range(5):
        radius.press("ArrowRight")
    playground.get_by_role("switch", name="Compact spacing").press("Space")
    playground.get_by_role("radio", name="Quiet", exact=True).press("ArrowRight")
    playground.get_by_label("Accent", exact=True).fill("#8B4A5F")
    page.locator('lf-playground-control[name="title"] input').fill("Ridge note; alert")

    assert len(events_model.read_events(serve.page_dir)) == before
    assert playground.evaluate("root => root.values") == {
        "accent": "#8b4a5f",
        "compact": True,
        "radius": 17,
        "title": "Ridge note; alert",
        "tone": "bold",
    }
    assert playground.evaluate("root => window.playgroundChanges.at(-1)")["title"] == (
        "Ridge note; alert"
    )
    expect(page.locator("#playground-card")).to_have_css("border-radius", "17px")
    expect(page.locator("#playground-card")).to_have_css("padding", "8px")
    assert (
        page.locator("#playground-card").evaluate(
            "element => getComputedStyle(element, '::before').content"
        )
        == '"Ridge note; alert"'
    )
    expect(page.locator("#card-instruction")).to_have_text(
        "Use a 17px radius, compact spacing set to true, a bold tone, #8b4a5f accents, "
        "and the title Ridge note; alert."
    )
    expect(page.locator("#card-instruction")).to_have_css(
        "font-family", 'system-ui, -apple-system, "Segoe UI", sans-serif'
    )
    expect(page.locator("#card-instruction")).to_have_css("font-size", "14px")

    with sending(page, "the playground configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    action = events_model.read_events(serve.page_dir)[-1]
    assert action["action"] == "choose"
    assert action["detail"] == {
        "values": {
            "accent": "#8b4a5f",
            "compact": True,
            "radius": 17,
            "title": "Ridge note; alert",
            "tone": "bold",
        },
        "instruction": (
            "Use a 17px radius, compact spacing set to true, a bold tone, #8b4a5f accents, "
            "and the title Ridge note; alert."
        ),
    }

    page.reload()
    wait_until_ready(page)
    expect(page.locator("#card-instruction")).to_contain_text("17px radius")
    assert playground.evaluate("root => root.values")["title"] == "Ridge note; alert"
    undo(page)
    expect(page.locator("#card-instruction")).to_contain_text("12px radius")
    assert playground.evaluate("root => root.values")["compact"] is False


def test_narrow_playground_keeps_complete_preset_labels_operable(browser, serve):
    label = "Recommended: 6 pages, 1 false, none missed"
    source = leaf_page(
        "Complete preset labels",
        f"""<h1>Tune alert policy</h1>
<lf-playground id="policy">
  <lf-playground-preset label="{label}">
    <lf-playground-setting for="threshold" value="6"></lf-playground-setting>
  </lf-playground-preset>
  <lf-playground-preview>
    <p>Six minutes catches the incident with time to act.</p>
    <lf-playground-control name="threshold" label="Threshold" kind="range"
      value="5" min="1" max="10"></lf-playground-control>
  </lf-playground-preview>
  <lf-playground-output>Use a <lf-playground-value for="threshold"></lf-playground-value> minute threshold.</lf-playground-output>
</lf-playground>""",
    )
    page = open_page(browser, serve(source))
    resized(page, 390, 844)
    preset = page.get_by_role("button", name=label, exact=True)
    reset = page.get_by_role("button", name="Reset", exact=True)
    for button in (preset, reset):
        reading = button.evaluate("""button => {
          const range = document.createRange();
          range.selectNodeContents(button);
          return {box: button.getBoundingClientRect().toJSON(),
                  lines: [...range.getClientRects()].map(line => line.toJSON())};
        }""")
        assert reading["lines"]
        for line in reading["lines"]:
            assert (
                reading["box"]["left"]
                <= line["left"]
                <= line["right"]
                <= reading["box"]["right"]
            )
            assert (
                reading["box"]["top"]
                <= line["top"]
                <= line["bottom"]
                <= reading["box"]["bottom"]
            )
    preset.click()
    expect(page.get_by_role("slider", name="Threshold")).to_have_value("6")
    reset.click()
    expect(page.get_by_role("slider", name="Threshold")).to_have_value("5")


def test_playground_keeps_contributor_drafts_until_reset_or_a_new_choice(
    browser, serve
):
    """An input edit updates the shared configuration immediately, and reading or
    acknowledging it never replaces the draft. A new choice or undo does."""
    page = open_page(browser, serve(CONTRIBUTOR_PAGE))
    playground = page.locator("#query-config")
    field = page.get_by_role("textbox", name="Region filter")
    field.fill("us-east-1")
    expect(playground.locator("lf-playground-output")).to_have_text(
        "Implement checkout alerts for region us-east-1."
    )
    field.press("ArrowLeft")
    playground.get_by_role("radio", name="Billing", exact=True).click()
    expect(field).to_be_focused()
    expect(field).to_have_value("us-east-1")
    assert field.evaluate("input => input.selectionStart") == len("us-east-")
    assert playground.evaluate("root => root.values.filters.region") == "us-east-1"

    field.fill("ap-south-1")
    # A later component registers while another component owns an unfinished edit.
    playground.evaluate("""root => {
      root.registerContributor('grouped', false);
    }""")
    expect(field).to_have_value("ap-south-1")
    assert playground.evaluate("root => root.values.filters.region") == "ap-south-1"

    field.fill("eu-north-1")
    playground.get_by_role("button", name="Checkout stream").click()
    expect(field).to_be_focused()
    expect(field).to_have_value("eu-north-1")
    assert playground.evaluate("root => root.values") == {
        "stream": "checkout",
        "filters": {"region": "eu-north-1"},
        "grouped": False,
    }

    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(field).to_have_value("eu-west-1")
    field.fill("chosen-region")
    # Programmatic activation leaves focus in the field: input alone has committed it.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        playground.get_by_role("button", name="Use these settings").evaluate(
            "button => button.click()"
        )
    holding(page, held, 1, "the query configuration")
    field.fill("unsent-region")
    field.press("ArrowLeft")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    choice = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "query-config" and event.get("action") == "choose"
    )
    assert choice["detail"]["values"] == {
        "stream": "checkout",
        "filters": {"region": "chosen-region"},
        "grouped": False,
    }
    expect(field).to_have_value("unsent-region")
    expect(field).to_be_focused()
    assert field.evaluate("input => input.selectionStart") == len("unsent-region") - 1
    nudge(serve.page_dir)
    told(page)
    expect(field).to_have_value("unsent-region")
    playground.evaluate("""root => lfUnwatched(() => {
      window.detachedQuery = {root, parent:root.parentNode, next:root.nextSibling};
      root.remove();
    })""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
    consume_browser_errors(
        page,
        {
            "code": "words-left-screen",
            "words": "unsent-region",
            "place": ["input#region-filter"],
        },
    )
    page.evaluate("""() => lfUnwatched(() => {
      const {root, parent, next} = window.detachedQuery;
      parent.insertBefore(root, next);
      delete window.detachedQuery;
    })""")
    rendered(page)
    expect(field).to_have_value("unsent-region")
    # Equal values do not make two choices the same gesture. Undoing the second
    # choice restores the first even when a later working edit differs from both.
    field.fill("chosen-region")
    with sending(page, "the query configuration"):
        playground.get_by_role("button", name="Use these settings").evaluate(
            "button => button.click()"
        )
    field.fill("later-draft")
    page.keyboard.press("Escape")
    undo(page)
    expect(field).to_have_value("chosen-region")
    page.reload()
    wait_until_ready(page)
    expect(field).to_have_value("chosen-region")

    # A refused choice restores the server's accepted slice instead of retaining
    # the local configuration that the server did not accept.
    def refuse_choice(route):
        if route.request.post_data_json.get("action") != "choose":
            route.continue_()
            return
        route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        )

    page.route("**/api/event", refuse_choice)
    field.fill("refused-region")
    with sending(page, "the refused query configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    expect(field).to_have_value("chosen-region")
    # Refusal deliberately restores accepted words; the generic words watch cannot
    # attribute this asynchronous replacement to the earlier submit gesture.
    consume_browser_errors(
        page,
        http_error_console(400),
        {
            "code": "words-left-screen",
            "words": "refused-region",
            "place": ["input#region-filter"],
        },
    )
    page.unroute("**/api/event")

    # An admitted aggregate can precede every page-module contributor. Each joining
    # contributor gets its slice; an undo replaces the pending snapshot as well.
    page.evaluate("sessionStorage.setItem('delay-query-contributors', 'true')")
    page.reload()
    wait_until_ready(page)
    assert playground.evaluate("root => root.values") == {"stream": "checkout"}
    assert (
        playground.evaluate("""root => {
      return root.registerContributor('grouped', true).get();
    }""")
        is False
    )
    undo(page)
    playground.evaluate("""root => {
      const input = document.querySelector('#region-filter');
      root.registerContributor('filters', {region:'eu-west-1'});
      root.subscribe(values => {
        if (input.value !== values.filters.region) input.value = values.filters.region;
      });
    }""")
    expect(field).to_have_value("eu-west-1")
    assert playground.evaluate("root => root.values") == {
        "stream": "checkout",
        "filters": {"region": "eu-west-1"},
        "grouped": True,
    }


def test_a_playground_reports_a_contributor_view_that_cannot_draw_its_edit(
    browser, serve
):
    """A required view's failed local draw belongs to its playground, just as a
    failed drawing of a restored choice does."""
    source = CONTRIBUTOR_PAGE.replace(
        "playground.subscribe(values => {",
        """playground.subscribe(values => {
      if (values.filters.region === 'broken-region')
        throw new Error('The query preview cannot draw broken-region');""",
    )
    page = open_page(browser, serve(source))
    field = page.get_by_role("textbox", name="Region filter")
    expect(page.locator("#query-config lf-playground-output")).to_have_text(
        "Implement checkout alerts for region eu-west-1."
    )
    with sending(page, "the playground drawing failure"):
        field.fill("broken-region")
    expect(page.locator("#query-config .lf-error")).to_contain_text(
        "The query preview cannot draw broken-region"
    )
    report = '<lf-playground id="query-config"> failed: '
    assert any(
        event["kind"] == "error" and event["text"].startswith(report)
        for event in events_model.read_events(serve.page_dir)
    )
    consume_browser_errors(page, report)


def test_inline_playground_keeps_evidence_and_long_instruction_reachable_in_a_short_workspace(
    browser, serve
):
    source = leaf_page(
        "Short alert workspace",
        '<lf-ask id="short-ask"><h1>Tune alert policies</h1>'
        '<lf-playground id="short-config" data-width="available">'
        "<lf-playground-preview><h2>Checkout latency</h2>"
        "<p>The last incident lasted seven minutes. Tune its alert beside this evidence.</p>"
        '<lf-playground-control name="latency" label="Latency window" kind="range" '
        'value="5" min="1" max="15" unit="min"></lf-playground-control>'
        "</lf-playground-preview><lf-playground-output>"
        + "Include alert evidence, validation, routing and deployment instructions. "
        * 100
        + '<span id="instruction-end">Finish with the rollback procedure.</span>'
        "</lf-playground-output></lf-playground></lf-ask>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 900, 500)
    playground = page.locator("#short-config")
    preview = playground.locator(".lf-playground-preview-body")
    instruction = playground.locator("lf-playground-output")
    expect(playground.locator(".lf-playground-controls-region")).to_have_count(0)
    split = playground.locator(".lf-playground-split").bounding_box()
    assert preview.bounding_box()["width"] == pytest.approx(split["width"], abs=1)
    assert instruction.evaluate("node => node.scrollHeight > node.clientHeight")
    instruction.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    body = instruction.bounding_box()
    last = page.locator("#instruction-end").bounding_box()
    assert body["y"] <= last["y"] < body["y"] + body["height"]
    slider = playground.get_by_role("slider", name="Latency window")
    slider.press("ArrowRight")
    expect(slider).to_have_value("6")
    view = preview.bounding_box()
    field = slider.bounding_box()
    assert view["y"] <= field["y"] < view["y"] + view["height"]
    submit = playground.get_by_role("button", name="Use these settings")
    submit.scroll_into_view_if_needed()
    action = submit.bounding_box()
    main = page.locator("main").bounding_box()
    assert action["y"] + action["height"] <= main["y"] + main["height"]
    with sending(page, "the short-workspace configuration"):
        submit.click()
    assert events_model.read_events(serve.page_dir)[-1]["detail"]["values"] == {
        "latency": 6
    }


def test_notification_playground_sets_regions_side_by_side_while_its_workspace_is_full_height(
    browser, serve
):
    """A playground is a workspace with its relationship declared: the preview is the
    stage, with the controls and the instruction they write in a rail beside it. While
    the root workspace fills the window each region scrolls on its own, the controls
    under their fixed presets and the instruction above its fixed actions; where it
    doesn't, the page scrolls, and a narrow one stacks the regions. Either way each is a
    named reading region."""
    source = ROOT / "examples" / "notification-playground.html"
    page = open_page(browser, serve(source))
    playground = page.locator("#notification-playground")
    controls = playground.locator(".lf-playground-controls")
    preview = playground.locator(".lf-playground-preview-body")
    presets = playground.get_by_role("group", name="Starting points")
    actions = playground.locator(".lf-playground-actions")
    reading = """async () => {
      const leaf = await window.__lfWidgetApi();
      const {readingRegionFor} = await window.__lfCheckApi();
      const playground = document.querySelector('#notification-playground');
      const controls = playground.querySelector('.lf-playground-controls');
      const preview = playground.querySelector('.lf-playground-preview-body');
      const instruction = playground.querySelector('lf-playground-output');
      const region = (body) => readingRegionFor(body);
      const controlsBox = region(controls).host.getBoundingClientRect();
      const previewBox = region(preview).host.getBoundingClientRect();
      const instructionBox = region(instruction).host.getBoundingClientRect();
      return {
        controlsId: region(controls).id,
        previewId: region(preview).id,
        instructionId: region(instruction).id,
        postures: [controls, preview, instruction].map((body) =>
          leaf.readingPosture(region(body))),
        scrollers: [controls, preview, instruction].map((body) =>
          leaf.scrollerFor(body) === body ? 'own' :
          leaf.scrollerFor(body) === document.scrollingElement ? 'page' : 'other'),
        sideBySide: Math.abs(previewBox.top - controlsBox.top) < 1
          && controlsBox.left >= previewBox.right
          && Math.abs(instructionBox.left - controlsBox.left) < 1
          && instructionBox.top >= controlsBox.bottom,
        stacked: controlsBox.top >= previewBox.bottom - 1,
        presetsHeadControls: controls.previousElementSibling
          === playground.querySelector('.lf-playground-presets'),
        controlsSize: [controls.clientHeight, controls.scrollHeight],
        pageScrolls: document.scrollingElement.scrollHeight > innerHeight,
        askDisplay: getComputedStyle(document.querySelector('#notification-ask')).display,
        authoredWords: leaf.wrote(playground).includes('Concurrent release events'),
        spokenWords: leaf.says(playground).includes('Concurrent release events'),
      };
    }"""

    resized(page, 1100, 700)
    expect(actions).to_be_visible()
    bounded = page.evaluate(reading)
    assert bounded == {
        **bounded,
        "controlsId": "lf-region:notification-playground:controls",
        "previewId": "lf-region:notification-playground:preview",
        "instructionId": "lf-region:notification-playground:instruction",
        "postures": ["bounded", "bounded", "bounded"],
        "scrollers": ["own", "own", "own"],
        "sideBySide": True,
        "presetsHeadControls": True,
        "pageScrolls": False,
        "askDisplay": "flex",
        "authoredWords": True,
        "spokenWords": True,
    }
    assert bounded["controlsSize"][1] > bounded["controlsSize"][0], bounded
    # The rail's two titles are one voice: the package draws its generated panes, and
    # the kernel's default pane header must not outrank the class that says so.
    voice = """node => {
      const style = getComputedStyle(node);
      return [style.fontFamily, style.fontSize, style.fontWeight];
    }"""
    assert playground.locator(".lf-playground-instruction-title").evaluate(
        voice
    ) == playground.locator(".lf-playground-presets-title").evaluate(voice)
    # The presets band heading the controls is ruled off from them, over the generic
    # region header's unruled box.
    assert playground.locator(".lf-playground-presets").evaluate(
        """node => {
          const style = getComputedStyle(node);
          return [style.borderBottomStyle, style.paddingBottom];
        }"""
    ) == ["solid", "14px"]
    first_control = playground.locator("lf-playground-control").first
    control_box = first_control.bounding_box()
    controls_box = controls.bounding_box()
    assert control_box["y"] >= controls_box["y"] and (
        control_box["y"] + control_box["height"]
        <= controls_box["y"] + controls_box["height"]
    ), f"the fixed presets left no complete control row: {bounded['controlsSize']}"
    assert controls.evaluate("body => body.scrollWidth === body.clientWidth"), (
        "native control margins must fit inside the allocated pane width"
    )
    presets_top = presets.bounding_box()["y"]
    controls.evaluate("body => body.scrollTop = body.scrollHeight")
    assert controls.evaluate("body => body.scrollTop") > 0
    expect(presets).to_be_visible()
    assert presets.bounding_box()["y"] == pytest.approx(presets_top, abs=1)
    expect(playground.get_by_role("button", name="Routine release")).to_be_visible()
    expect(playground.get_by_role("button", name="Needs attention")).to_be_visible()
    pressure = playground.get_by_role("slider", name="Concurrent release events")
    expect(pressure).to_have_value("2")
    expect(page.locator(".notification-demo-card-banner")).to_have_count(2)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(2)
    expect(page.locator(".notification-demo-strip-owner")).to_have_count(2)
    assert playground.evaluate(
        """owner => lfUnwatched(() => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          const nodes = [...owner.querySelectorAll('*')];
          const values = JSON.stringify(owner.values);
          owner.remove();
          parent.insertBefore(owner, next);
          return values === JSON.stringify(owner.values)
            && nodes.every((node, index) => owner.querySelectorAll('*')[index] === node);
        })"""
    )
    reattached = page.evaluate(reading)
    assert (reattached["controlsId"], reattached["previewId"]) == (
        "lf-region:notification-playground:controls",
        "lf-region:notification-playground:preview",
    )
    regular_strip_padding = page.locator(
        ".notification-demo-card-status-strip"
    ).first.evaluate("card => getComputedStyle(card).paddingTop")
    pressure.press("ArrowRight")
    pressure.press("ArrowRight")
    expect(page.locator(".notification-demo-card-banner")).to_have_count(4)
    expect(page.locator(".notification-demo-card-status-strip")).to_have_count(4)
    expect(page.locator(".notification-demo-candidate").first).to_contain_text(
        "4 cards · full detail"
    )
    expect(page.locator(".notification-demo-candidate").last).to_contain_text(
        "4 rows · compact summary"
    )
    playground.get_by_role("button", name="Needs attention").click()
    expect(pressure).to_have_value("4")
    expect(page.locator("#notification-simulator")).to_have_attribute(
        "data-compact", "true"
    )
    compact_strip_padding = page.locator(
        ".notification-demo-card-status-strip"
    ).first.evaluate("card => getComputedStyle(card).paddingTop")
    assert float(compact_strip_padding.removesuffix("px")) < float(
        regular_strip_padding.removesuffix("px")
    )
    playground.get_by_role("button", name="Routine release").click()
    expect(pressure).to_have_value("2")
    assert preview.evaluate("body => body.scrollTop") == 0
    action_box = actions.bounding_box()
    playground_box = playground.bounding_box()
    panel_box = page.locator(".lf-fp-row").bounding_box()
    assert (
        action_box["y"] + action_box["height"]
        <= playground_box["y"] + playground_box["height"] + 1
    )
    assert action_box["y"] + action_box["height"] <= panel_box["y"] + 1

    for width, height in [(1100, 300), (700, 500), (500, 900)]:
        resized(page, width, height)
        flow = page.evaluate(reading)
        assert flow == {
            **flow,
            "postures": ["flow", "flow", "flow"],
            "scrollers": ["page", "page", "page"],
            "pageScrolls": True,
            "askDisplay": "block",
        }, (width, height)
        # Too short to hold the regions is not too narrow to set them side by side.
        assert flow["stacked"] is (width < 1100), (width, height, flow)


def test_notification_playground_admits_only_its_exact_page_configuration(
    browser, serve
):
    source = ROOT / "examples" / "notification-playground.html"
    url = serve(source)
    page = open_page(browser, url)
    playground = page.locator("#notification-playground")
    values = playground.evaluate("root => root.values")
    assert set(values) == {
        "accent",
        "compact",
        "events",
        "format",
        "radius",
        "show-owner",
        "title",
        "tone",
    }

    refused = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "notification-playground",
            "action": "choose",
            "detail": {
                "values": {**values, "unknown": "not part of this page"},
                "instruction": "Build the notification.",
            },
        },
    )
    assert refused.status == 400
    unknown = refused_on(refused.json())
    assert (unknown.code, unknown.values["field"]) == ("invalid-detail", "/values")
    off_step = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "notification-playground",
            "action": "choose",
            "detail": {
                "values": {**values, "events": 2.5},
                "instruction": "Build the notification.",
            },
        },
    )
    assert off_step.status == 400
    assert refused_on(off_step.json()).values["field"] == "/values/events"
    assert actions(serve.page_dir) == []


def test_built_code_reader_design_comment_keeps_its_identity_after_revision(
    browser, serve
):
    """The shared comment loop carries a design request through a real reader revision.
    Design mode's keyboard and touch routes to a target are the aim tests'
    (`test_render_aim.py`); this picks the built reader's heading by pointer."""
    source_path = ROOT / "examples" / "code-comparison.html"
    source = source_path.read_text(encoding="utf-8")
    page = open_page(browser, live_url(serve(source_path)))
    page.locator("#target-reader-heading").scroll_into_view_if_needed()
    page.keyboard.press("l")
    page.locator("#target-reader-heading").click()
    field = page.locator(".lf-fab-input")
    write(field, "Keep the heading aligned with the reader's first line.")
    with sending(page, "the reader design comment"):
        page.locator(".lf-fab-bar .lf-compose-submit").click()
    event = next(
        e
        for e in reversed(events_model.read_events(serve.page_dir))
        if e["kind"] == "comment"
    )
    assert event["about"] == "design"
    assert event["anchor"] == {"section": "target-reader-heading"}
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    revised = source.replace("Reader sample", "Revised reader treatment")
    stamp = stamp_page(serve.page_dir, revised, "Align the reader treatment")
    wait_for_revision(page, stamp["revision"])
    expect(page.locator("#target-reader-heading")).to_have_text(
        "Revised reader treatment"
    )
    quote = open_panel_thread(page, event["id"]).locator(".lf-fp-quote")
    expect(quote).to_contain_text("target-reader-heading")
    expect(quote).not_to_have_class(re.compile(r"detached"))


def test_a_playground_sends_one_choice_while_the_first_press_is_in_flight(
    browser, serve
):
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")
    choose = playground.get_by_role("button", name="Use these settings")
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    with page.expect_request("**/api/event"):
        choose.press("Enter")
    holding(page, held, 1, "the playground choice")
    expect(choose).to_be_disabled()
    expect(choose).to_have_attribute("aria-busy", "true")
    expect(choose).to_be_focused()
    choose.press("Space")
    choose.dispatch_event("click")
    rendered(page)
    assert len(held) == 1

    held[0].continue_()
    round_trip(page)
    expect(choose).to_be_enabled()
    expect(choose).not_to_have_attribute("aria-busy", "true")
    expect(choose).to_be_focused()
    assert len(actions(serve.page_dir)) == 1


def test_a_playground_switch_and_copy_are_reachable_through_go_to(browser, serve):
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, serve(PLAYGROUND_PAGE), context=context)
    playground = page.locator("#card-playground")

    page.keyboard.press("g")
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]').length"
    )
    switch_hint = page.locator(
        '.lf-go-to-hint[data-lf-go-to-target="card-playground-compact-input"]'
    )
    expect(switch_hint).to_have_count(1)
    switch_code = switch_hint.get_attribute("data-lf-hint-code")
    assert switch_code
    page.keyboard.type(switch_code)
    expect(playground.get_by_role("switch", name="Compact spacing")).to_be_checked()

    playground.get_by_role(
        "button", name="Copy instruction"
    ).scroll_into_view_if_needed()

    page.keyboard.press("g")
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]').length"
    )
    hint_targets = page.locator(".lf-go-to-hint").evaluate_all(
        "els => els.map(el => [el.dataset.lfGoToTarget, el.dataset.lfGoToKind])"
    )
    assert hint_targets, hint_targets
    copy_hint = page.locator(
        '.lf-go-to-hint[data-lf-go-to-target="card-playground-copy"]'
    )
    expect(copy_hint).to_have_count(1)
    copy_code = copy_hint.get_attribute("data-lf-hint-code")
    assert copy_code

    page.keyboard.type(copy_code)
    assert "12px radius" in page.evaluate("navigator.clipboard.readText()")


def test_a_playground_rejects_range_values_that_do_not_land_on_its_step(browser, serve):
    source = PLAYGROUND_PAGE.replace('value="12" min="0"', 'value="12.5" min="0"')
    page = open_page(browser, serve(source))

    expect(page.locator("#card-playground .lf-error")).to_contain_text(
        "control radius has a value off its step"
    )
    consume_browser_errors(
        page,
        "control radius has a value off its step",
    )


def test_a_playground_control_written_in_the_preview_stands_beside_its_item(
    browser, serve
):
    """The alert playground writes each alert's threshold and route beside that alert's
    replay, and the page budget as the playground's own child. The budget stands in the
    rail; each alert's controls are drawn where they are written, and a press there
    changes the playground's one configuration and the instruction it sends."""
    source = ROOT / "examples" / "alert-thresholds.html"
    page = open_page(browser, serve(source))
    playground = page.locator("#alert-playground")
    rail = playground.locator(".lf-playground-controls")
    expect(rail.locator("lf-playground-control")).to_have_count(2)
    expect(rail.get_by_role("slider", name="On-call page budget")).to_be_visible()

    latency = page.locator("#alert-latency-settings")
    evidence = page.locator("#alert-latency-evidence").bounding_box()
    settings = latency.bounding_box()
    assert settings["x"] > evidence["x"] + evidence["width"] - 1
    assert abs(settings["y"] - evidence["y"]) < 1

    latency.get_by_role("radio", name="over 1,200 ms").click()
    latency.get_by_role("radio", name="Ticket").click()
    values = playground.evaluate("root => root.values")
    assert values["latency-threshold"] == "1200ms"
    assert values["latency-route"] == "ticket"
    assert values["budget"] == 10
    expect(page.locator("#alert-latency-replay tr.chosen th")).to_have_text(
        "over 1,200 ms"
    )
    expect(page.locator('[data-total="oncall"] strong')).to_have_text("18")
    expect(page.locator("#alert-instruction")).to_contain_text(
        "payments-p99-latency over 1,200 ms, open a ticket"
    )

    # A press on a control in the preview takes focus as any control's does, so the
    # keyboard goes on from the control last pressed rather than an earlier one.
    rate = page.locator("#alert-rate-settings")
    rate.get_by_role("radio", name="over 2%").click()
    latency.get_by_role("radio", name="Page").click()
    page.keyboard.press("ArrowRight")
    values = playground.evaluate("root => root.values")
    assert (values["rate-threshold"], values["latency-route"]) == ("2%", "ticket")

    with sending(page, "the alert settings"):
        playground.get_by_role("button", name="Apply these settings").click()
    action = events_model.read_events(serve.page_dir)[-1]
    assert action["detail"]["values"]["latency-route"] == "ticket"


def test_a_playground_initial_drawing_leaves_quoted_controls_alone(browser, serve):
    """A quotation neither supplies controls nor yields its own value slots.

    Admission refuses a bare quoted control, so collection is exercised directly.
    Complete quoted playgrounds keep their own values as the surrounding one changes.
    """
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    drawing = page.evaluate(
        """source => {
          const template = document.createElement('template');
          template.innerHTML = source;
          const host = template.content.querySelector('#card-playground');
          host.id = 'quoted-controls-drawing';
          const quote = document.createElement('lf-sample');
          quote.setAttribute('data-lf-exhibit', '');
          quote.innerHTML = `
            <lf-playground-control name="tone" label="Quoted tone" kind="text"
              value="quoted"></lf-playground-control>
            <lf-playground-control name="quoted" label="Quoted toggle" kind="toggle"
              value="true"></lf-playground-control>`;
          host.querySelector('lf-playground-preview').append(quote);
          const quotedOutput = document.createElement('lf-sample');
          quotedOutput.setAttribute('data-lf-exhibit', '');
          quotedOutput.innerHTML = `
            <lf-playground id="quoted-output-drawing">
              <lf-playground-control name="tone" label="Quoted tone" kind="text"
                value="quoted"></lf-playground-control>
              <lf-playground-control name="inner-tone" label="Inner tone" kind="text"
                value="independent"></lf-playground-control>
              <lf-playground-preview><p>Inner preview</p></lf-playground-preview>
              <lf-playground-output><lf-playground-value for="tone"></lf-playground-value>
                <lf-playground-value for="inner-tone"></lf-playground-value>
              </lf-playground-output>
            </lf-playground>`;
          host.querySelector('lf-playground-output').append(quotedOutput);
          document.documentElement.lfInitial.paint(
            quotedOutput.querySelector('lf-playground'));
          const initial = document.documentElement.lfInitial.paint(host);
          initial.renderValues({...initial.values, tone: 'bold'});
          return {
            controls: initial.controls.map(control => control.getAttribute('name')),
            values: initial.values,
            quotedInputs: quote.querySelectorAll('input').length,
            outerTone: initial.output.querySelector(':scope > lf-playground-value[for="tone"]')
              .textContent,
            quotedValues: [...quotedOutput.querySelectorAll('lf-playground-value')]
              .map(slot => slot.textContent),
          };
        }""",
        PLAYGROUND_PAGE,
    )
    assert drawing == {
        "controls": ["radius", "compact", "tone", "accent", "title"],
        "values": {
            "radius": 12,
            "compact": False,
            "tone": "quiet",
            "accent": "#4f766f",
            "title": "Field note",
        },
        "quotedInputs": 0,
        "outerTone": "bold",
        "quotedValues": ["quoted", "independent"],
    }


def test_a_quoted_playground_is_a_static_preview_with_its_authored_output(
    browser, serve
):
    source = PLAYGROUND_PAGE.replace(
        '<lf-ask id="card-playground-ask">',
        '<lf-sample id="playground-example" label="card playground">',
    ).replace("</lf-ask>", "</lf-sample>")
    page = open_page(browser, serve(source))
    playground = page.locator("#card-playground")

    expect(playground.get_by_role("button")).to_have_count(0)
    expect(playground.locator("lf-playground-control:visible")).to_have_count(0)
    expect(playground.locator("lf-playground-preset:visible")).to_have_count(0)
    expect(playground.locator("#playground-card")).to_be_visible()
    expect(playground.locator("#card-instruction")).to_contain_text("12px radius")
    assert playground.evaluate("root => root.values")["compact"] is False
    assert playground.evaluate(
        """async root => {
          const {readingRegionFor} = await window.__lfCheckApi();
          return readingRegionFor(root.querySelector('lf-playground-preview')) === undefined
            && !root.querySelector('[data-lf-reading-role]');
        }"""
    )


def test_playground_labels_can_be_selected_without_changing_the_controls(
    browser, serve
):
    """A label is readable text even while the preview holds focus. Dragging its
    words selects them; clicking the switch or pressing Space still changes it."""
    source = PLAYGROUND_PAGE.replace(
        "<p>Open until dusk.</p>",
        '<p>Open until dusk.</p><button id="preview-focus">Try the card</button>',
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#card-playground")
    toggle = playground.get_by_role("switch", name="Compact spacing")

    for in_preview in (False, True):
        for name, words in (
            ("compact", "Compact spacing"),
            ("radius", "Corner radius"),
        ):
            page.evaluate("getSelection().removeAllRanges()")
            if in_preview:
                page.locator("#preview-focus").click()
            else:
                page.locator("h1").click()
            before = playground.evaluate("root => root.values")
            label = playground.locator(
                f'lf-playground-control[name="{name}"] .lf-playground-control-label'
            )
            label.scroll_into_view_if_needed()
            box = label.evaluate("""label => {
                const range = document.createRange();
                range.selectNodeContents(label);
                return range.getBoundingClientRect().toJSON();
            }""")
            y = box["y"] + box["height"] / 2
            page.mouse.move(box["x"] + 0.5, y)
            page.mouse.down()
            page.mouse.move(box["right"] - 0.5, y, steps=12)
            page.mouse.up()
            assert page.evaluate("getSelection().toString()") == words
            assert playground.evaluate("root => root.values") == before

    # Selecting a word with a double-click must not operate the switch either.
    label = playground.locator(
        'lf-playground-control[name="compact"] .lf-playground-control-label'
    )
    label.dblclick(position={"x": 5, "y": 5})
    assert page.evaluate("getSelection().toString()") == "Compact"
    expect(toggle).not_to_be_checked()

    # The control face keeps the preview focused and remains usable after selecting
    # its label. Reading that label does not change the control.
    preview = page.locator("#preview-focus")
    preview.click()
    assert page.evaluate("getSelection().toString()") == "Compact"
    toggle.click()
    expect(toggle).to_be_checked()
    expect(preview).to_be_focused()
    label.click()
    expect(toggle).to_be_checked()
    toggle.press("Space")
    expect(toggle).not_to_be_checked()
