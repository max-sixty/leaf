"""Playgrounds: first paint from authored defaults, the working state and contributor
drafts, sending a choice, quoted playgrounds, and their layout in a workspace."""

import re

import pytest
from interact_support import wait_for
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import actions
from render_harness import (
    consume_browser_errors,
    displayed,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    post_event,
    put_preview_away,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    undo,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from browser.widgets import (
    PLAYGROUND_PAGE,
)
from leaf.log import event_log as events_model
from leaf.source.render_checks import wait_until_ready
from leaf_dev.browser import text_field
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


CONTRIBUTOR_PAGE = leaf_page(
    "query configuration",
    """
<lf-group id="query-ask" label="Choose the alert query"><h1 id="query-ask-h">Choose the alert query</h1>
<lf-playground id="query-config">
  <aside>
  <fieldset id="stream"><legend>Event stream</legend><label id="stream-checkout"><input type="radio" name="stream" value="checkout" checked /> Checkout</label><label id="stream-billing"><input type="radio" name="stream" value="billing" /> Billing</label></fieldset>
  </aside>
  <lf-playground-preset id="preset-checkout-stream" label="Checkout stream">
    <lf-playground-setting for="stream" value="checkout"></lf-playground-setting>
  </lf-playground-preset>
  <div id="query-editor">
  <label for="region-filter">Region filter</label>
  <input id="region-filter" type="text" value="eu-west-1">
  </div>
  <lf-playground-output>Implement the selected query.</lf-playground-output>
</lf-playground></lf-group>
<script type="module">
document.addEventListener("lf-page-interface", event => {
  event.detail.present(Promise.resolve().then(() => {
    if (sessionStorage.getItem('delay-query-contributors')) return;
    const playground = document.querySelector('#query-config');
    const input = document.querySelector('#region-filter');
    const filters = playground.registerContributor(
      'filters', {region: input.value}, document.querySelector('#query-editor'));
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


# Whether a node stands whole in the window.
IN_WINDOW = """node => {
  const box = node.getBoundingClientRect();
  return box.top >= 0 && box.left >= 0 && box.bottom <= innerHeight
    && box.right <= innerWidth;
}"""
# Whether nothing stands over a node, the floating panel included, at four points
# inside its box.
UNCOVERED = """node => {
  const box = node.getBoundingClientRect();
  return [box.left + box.width / 4, box.right - box.width / 4].every(x =>
    [box.top + box.height / 4, box.bottom - box.height / 4].every(y =>
      node.contains(document.elementFromPoint(x, y))));
}"""


def test_playground_contributor_needs_no_field(browser, serve):
    """Native preview inputs own the configuration; the provider's plain-text task
    keeps its lines when shown, copied and submitted."""
    start = CONTRIBUTOR_PAGE.index("  <aside>")
    end = CONTRIBUTOR_PAGE.index('  <div id="query-editor">')
    source = (
        (CONTRIBUTOR_PAGE[:start] + CONTRIBUTOR_PAGE[end:])
        .replace("${values.stream}", "checkout")
        .replace(
            "alerts for region ${values.filters.region}.",
            "alerts.\\n\\nRegion: ${values.filters.region}"
            "\\n  Keep the stable release available.",
        )
    )
    url = serve(source)
    page = open_page(browser, url)
    playground = page.locator("#query-config")
    field = page.get_by_role("textbox", name="Region filter")

    # An edit no event ends, as the caret still in its field, is recorded once input
    # pauses, so a reload keeps it.
    field.fill("us-east-1")
    wait_for(
        lambda: [
            event["detail"]["values"]
            for event in events_model.read_events(serve.page_dir)
            if event.get("action") == "tune"
        ],
        lambda tunes: tunes[-1:] == [{"filters": {"region": "us-east-1"}}],
        failure="the paused edit was never recorded",
    )
    page.reload()
    wait_until_ready(page)
    expect(field).to_have_value("us-east-1")
    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(field).to_have_value("eu-west-1")

    field.fill("ap-south-1")
    instruction = (
        "Implement checkout alerts.\n\nRegion: ap-south-1"
        "\n  Keep the stable release available."
    )
    playground.get_by_role("button", name="Show instruction").click()
    output = playground.locator("lf-playground-output")
    expect(output).to_be_visible()
    assert output.inner_text() == instruction
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    playground.get_by_role("button", name="Copy instruction").click()
    expect(
        page.get_by_role("region", name="Leaf").get_by_text(
            "Instruction copied", exact=True
        )
    ).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == instruction
    page.keyboard.press("Escape")
    with sending(page, "the contributor-only configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    assert actions(serve.page_dir)[-1]["detail"] == {
        "values": {"filters": {"region": "ap-south-1"}},
        "instruction": instruction,
    }
    playground.get_by_role("button", name="Undo choice").click()
    expect(playground.get_by_role("button", name="Use these settings")).to_be_visible()
    expect(field).to_have_value("ap-south-1")


def test_playground_controls_take_focus_from_editors_and_keep_candidate_focus(
    browser, serve, subtests
):
    """Moving from a native preview editor to a slider leaves the next key on that
    slider, rather than silently changing the contributor the user just left."""
    source = CONTRIBUTOR_PAGE.replace(
        "  </aside>",
        """  <label id="limit">Maximum results <input type="range" name="limit" min="1" max="6" value="4" /></label>
  </aside>""",
    ).replace(
        '  <input id="region-filter" type="text" value="eu-west-1">',
        """  <input id="region-filter" type="text" value="eu-west-1">
    <label>Native range<input id="native-range" type="range"></label>
    <label>Region choice<select id="native-select"><option>Europe</option><option>Asia</option></select></label>
    <label>Include archived<input id="native-checkbox" type="checkbox"></label>
    <label>All regions<input id="native-radio" type="radio"></label>
    <label>Notes<textarea id="native-textarea">Keep the stable release.</textarea></label>
    <div id="native-editable" contenteditable="true" aria-label="Description"><span>Release report</span></div>
    <button id="editor-button" type="button">Add filter</button>
    </div><div>
    <label>Candidate input<input id="candidate-input" value="Compare this focus ring"></label>
    <button id="candidate-button" type="button">Candidate button</button>
    <input id="candidate-input-button" type="button" value="Candidate input button">
    <input id="candidate-input-submit" type="submit" value="Candidate submit">
    <input id="candidate-input-reset" type="reset" value="Candidate reset">
    <input id="candidate-input-image" type="image" alt="Candidate image button">""",
    )
    source = source.replace(
        "</head>",
        "<style>#candidate-input:focus {outline: 4px solid violet}</style></head>",
    )
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000}, has_touch=True
    )
    page = open_page(browser, serve(source), context=context)
    slider = page.get_by_role("slider", name="Maximum results")
    field = page.get_by_role("textbox", name="Region filter")
    for route in ("click", "tap"):
        for selector in (
            "#region-filter",
            "#native-range",
            "#native-select",
            "#native-checkbox",
            "#native-radio",
            "#native-textarea",
            "#native-editable span",
            "#editor-button",
        ):
            with subtests.test(route=route, editor=selector):
                getattr(page.locator(selector), route)()
                if selector == "#native-select":
                    page.keyboard.press("Escape")
                if route == "tap":
                    box = slider.bounding_box()
                    slider.tap(position={"x": 2, "y": box["height"] / 2})
                    expect(slider).to_have_value("1")
                    slider.tap(position={"x": box["width"] - 2, "y": box["height"] / 2})
                    expect(slider).to_have_value("6")
                else:
                    slider.click()
                    page.keyboard.press("Home")
                    page.keyboard.press("ArrowRight")
                    expect(slider).to_have_value("2")
                    expect(slider).to_be_focused()
                expect(field).to_have_value("eu-west-1")
    # A keyboard arrival, rather than a pointer press, likewise operates the range.
    page.get_by_role("button", name="Checkout stream", exact=True).click()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(slider).to_be_focused()
    page.keyboard.press("End")
    expect(slider).to_have_value("6")
    # Focus belongs to the candidate's purpose, including an input's focus treatment.
    for selector in (
        "#candidate-input",
        "#candidate-button",
        "#candidate-input-button",
        "#candidate-input-submit",
        "#candidate-input-reset",
        "#candidate-input-image",
    ):
        with subtests.test(candidate=selector):
            candidate = page.locator(selector)
            candidate.click()
            slider.click()
            assert candidate.evaluate("button => button.matches(':focus')")
            if selector == "#candidate-input":
                assert (
                    candidate.evaluate("input => getComputedStyle(input).outlineWidth")
                    == "4px"
                )


@pytest.mark.parametrize(
    "browser_fixture", ["browser", "firefox_browser", "webkit_browser"]
)
def test_playground_range_preserves_preview_focus_without_cancelling_native_drag(
    request, browser_fixture, serve, subtests
):
    source = CONTRIBUTOR_PAGE.replace(
        "  </aside>",
        """  <label id="limit">Maximum results <input type="range" name="limit" min="1" max="6" value="1" /></label>
  </aside>""",
    ).replace(
        "  <lf-playground-output>",
        """  <label>Candidate<input id="candidate-input" value="Focus treatment"></label>
  <lf-sample id="candidate-sample" label="Sample candidate">
    <template id="candidate-document" data-sample>
      <input id="sample-input" value="Sample focus treatment">
    </template>
  </lf-sample>
  <lf-playground-output>""",
    )
    page = open_page(request.getfixturevalue(browser_fixture), serve(source))

    def expect_focused(target):
        node = target.element_handle()
        node.owner_frame().wait_for_function(
            "element => element.matches(':focus')", arg=node
        )

    slider = page.get_by_role("slider", name="Maximum results")
    editor = page.get_by_role("textbox", name="Region filter")
    candidate = page.locator("#candidate-input")
    sample = page.frame_locator("#candidate-sample iframe").locator("#sample-input")
    # Operate the fresh sample before keyboard focus has visited any parent control.
    sample.click()
    page.wait_for_function("document.querySelector('#candidate-sample').focusedContent")
    box = slider.bounding_box()
    slider.click(position={"x": box["width"] - 2, "y": box["height"] / 2})
    expect(slider).to_have_value("6")
    expect_focused(sample)
    sample.element_handle().owner_frame().wait_for_function("document.hasFocus()")
    for target in (candidate, sample):
        with subtests.test(candidate="sample" if target is sample else "input"):
            slider.focus()
            page.keyboard.press("Home")
            target.click()
            if target is sample:
                page.wait_for_function(
                    "document.querySelector('#candidate-sample').focusedContent",
                )
            expect_focused(target)
            box = slider.bounding_box()
            slider.click(position={"x": box["width"] - 2, "y": box["height"] / 2})
            expect(slider).to_have_value("6")
            expect_focused(target)
            slider.focus()
            page.keyboard.press("Home")
            target.click()
            if target is sample:
                page.wait_for_function(
                    "document.querySelector('#candidate-sample').focusedContent",
                )
            page.mouse.move(box["x"] + 8, box["y"] + box["height"] / 2)
            page.mouse.down()
            expect_focused(target)
            page.mouse.move(
                box["x"] + box["width"] - 8, box["y"] + box["height"] / 2, steps=5
            )
            expect(slider).to_have_value("6")
            expect_focused(target)
            page.mouse.move(box["x"] + box["width"] + 20, box["y"] + box["height"] / 2)
            page.mouse.up()
            expect_focused(target)
            if target is sample:
                target.element_handle().owner_frame().wait_for_function(
                    "document.hasFocus()"
                )
                for _ in range(10):
                    page.keyboard.press("Shift+Tab")
                    if editor.evaluate("e => e.matches(':focus')"):
                        break
            else:
                editor.click()
            edited = "sample-value" if target is sample else "native-value"
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.type(edited)
            expect(editor).to_be_focused()
            expect(editor).to_have_value(edited)
            if target is sample:
                # An already queued restore delivered after the user leaves cannot
                # reactivate its child window or reclaim the editor's focus.
                assert not page.locator("#candidate-sample").evaluate(
                    "e => e.restoreCurrentLocation()"
                )
                expect(editor).to_be_focused()
    # A cancelled native default can leave the preview in place. Neither a cancelled
    # press nor replacing its candidate may claim a later deliberate editor arrival.
    for ending in ("cancel", "replace"):
        with subtests.test(ending=ending):
            candidate.click()
            slider.evaluate(
                "e => e.addEventListener('mousedown', event => event.preventDefault(), {once:true})"
            )
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            if ending == "cancel":
                # Through a handle: a role locator's `dispatch_event` reads the
                # slider's `aria-labelledby` in the page's world as well as Playwright's
                # own, which crashes Firefox (microsoft/playwright#43967).
                slider.element_handle().dispatch_event("pointercancel")
            else:
                candidate.evaluate(
                    "e => {const replacement=e.cloneNode(true);replacement.setAttribute('value','Second candidate');e.replaceWith(replacement)}"
                )
            page.mouse.up()
            editor.click()
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.type(ending)
            expect(editor).to_be_focused()
            expect(editor).to_have_value(ending)


def test_keyboard_can_take_a_range_while_the_preview_preserving_press_is_held(
    browser, serve
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Keyboard during a range press",
                """
<lf-group id="ring-ask" label="Choose a ring"><h1 id="ring-ask-h">Choose a ring</h1>
<lf-playground id="ring">
  <aside><label id="width">Width <input type="range" name="width" min="1" max="4" value="2" /></label></aside>
  <label>Candidate<input value="Focus treatment"></label>
  <lf-playground-output>Width <output for="width"></output></lf-playground-output>
</lf-playground></lf-group>
""",
            )
        ),
    )
    candidate = page.get_by_role("textbox", name="Candidate")
    slider = page.get_by_role("slider", name="Width")
    candidate.click()
    box = slider.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    expect(candidate).to_be_focused()
    page.keyboard.press("Tab")
    expect(slider).to_be_focused()
    page.mouse.up()
    expect(slider).to_be_focused()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    expect(slider).to_have_value("2")


def test_authored_playground_copies_and_sends_its_instruction_blocks(browser, serve):
    script = CONTRIBUTOR_PAGE.index('<script type="module">')
    end = CONTRIBUTOR_PAGE.index("</script>", script) + len("</script>")
    source = CONTRIBUTOR_PAGE[:script] + CONTRIBUTOR_PAGE[end:]
    source = source.replace(
        "Implement the selected query.",
        """<p>Implement <output for="stream"></output> alerts.</p>
        <ul><li>Region: eu-west-1</li><li>Keep the stable release available.</li></ul>
        <p>Record these settings.<br>Show me the config diff.</p>
        <pre>mode: stable
  </pre>""",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#query-config")
    playground.get_by_role("button", name="Show instruction").click()
    instruction = (
        "Implement checkout alerts.\nRegion: eu-west-1\nKeep the stable release available."
        "\nRecord these settings.\nShow me the config diff.\nmode: stable"
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    playground.get_by_role("button", name="Copy instruction").click()
    expect(
        page.get_by_role("region", name="Leaf").get_by_text(
            "Instruction copied", exact=True
        )
    ).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == instruction
    page.keyboard.press("Escape")
    with sending(page, "the authored configuration"):
        playground.get_by_role("button", name="Use these settings").click()
    assert actions(serve.page_dir)[-1]["detail"]["instruction"] == instruction


def test_playground_select_keeps_the_same_working_configuration(browser, serve):
    """A select uses the native picker and the playground's one restoration and
    decision path, including withdrawal of a submitted choice."""
    start = CONTRIBUTOR_PAGE.index('  <fieldset id="stream">')
    end = CONTRIBUTOR_PAGE.index("  </aside>")
    source = (
        CONTRIBUTOR_PAGE[:start]
        + '<label id="stream">Event stream <select name="stream">'
        '<option value="checkout" selected>Checkout</option>'
        '<option value="billing">Billing</option></select></label>\n'
        + CONTRIBUTOR_PAGE[end:]
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#query-config")
    stream = playground.get_by_role("combobox", name="Event stream")
    expect(stream).to_have_value("checkout")
    page.get_by_role("textbox", name="Region filter").focus()
    stream.click()
    expect(stream).to_be_focused()
    stream.press("Escape")
    stream.press("b")
    expect(stream).to_have_value("billing")
    expect(playground.locator("lf-playground-output")).to_have_text(
        "Implement billing alerts for region eu-west-1."
    )
    page.reload()
    wait_until_ready(page)
    expect(stream).to_have_value("billing")
    playground.get_by_role("button", name="Checkout stream").click()
    expect(stream).to_have_value("checkout")
    stream.select_option("billing")
    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(stream).to_have_value("checkout")
    stream.select_option("billing")
    with sending(page, "the chosen event stream"):
        playground.get_by_role("button", name="Use these settings").click()
    round_trip(page)
    choice = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "query-config" and event.get("action") == "choose"
    )
    assert choice["detail"]["values"]["stream"] == "billing"
    assert choice["detail"]["instruction"] == (
        "Implement billing alerts for region eu-west-1."
    )
    undo(page)
    expect(stream).to_have_value("billing")


def test_a_multiple_select_sends_and_restores_every_option_it_selects(browser, serve):
    """A `<select multiple>` holds every option it selects: the instruction and the
    choice name each pick, a reload selects them all again, and a preset that names its
    options in any order selects them and still reads as pressed after a reload."""
    source = leaf_page(
        "Rollout regions",
        '<lf-group id="rollout-q" label="Which regions?"><lf-playground id="rollout">'
        '<aside><label id="regions">Regions <select name="regions" multiple>'
        '<option value="eu-west" selected>EU West</option>'
        '<option value="us-east">US East</option>'
        '<option value="ap-south">AP South</option></select></label></aside>'
        '<lf-playground-preset id="preset-east" label="East">'
        '<lf-playground-setting for="regions" value="ap-south us-east">'
        "</lf-playground-setting></lf-playground-preset><p>Preview</p>"
        '<lf-playground-output>Roll out to <output for="regions"></output>.'
        "</lf-playground-output></lf-playground></lf-group>",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#rollout")
    regions = playground.get_by_role("listbox", name="Regions")
    regions.select_option(["eu-west", "ap-south"])
    expect(playground.locator("lf-playground-output")).to_have_text(
        "Roll out to eu-west, ap-south."
    )
    expect(playground).to_have_attribute("data-playground-regions", "eu-west ap-south")
    with sending(page, "the chosen regions"):
        playground.get_by_role("button", name="Use these settings").click()
    choice = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("widget") == "rollout" and event.get("action") == "choose"
    )
    assert choice["detail"]["values"] == {"regions": ["eu-west", "ap-south"]}
    page.reload()
    wait_until_ready(page)
    expect(regions).to_have_values(["eu-west", "ap-south"])
    east = playground.get_by_role("button", name="East", exact=True)
    with sending(page, "the preset's regions"):
        east.click()
    expect(regions).to_have_values(["us-east", "ap-south"])
    page.reload()
    wait_until_ready(page)
    expect(regions).to_have_values(["us-east", "ap-south"])
    expect(east).to_have_attribute("aria-pressed", "true")


def test_playground_preview_stays_readable_until_its_controls_load(browser, serve):
    """Authored content is readable while loading; upgrade applies control defaults."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    held = []
    page.route("**/widgets/lf-playground.js", lambda route: held.append(route))
    with page.expect_request("**/widgets/lf-playground.js"):
        page.goto(serve(PLAYGROUND_PAGE), wait_until="commit")
    displayed(page)
    assert held
    assert page.evaluate("() => !customElements.get('lf-playground')")
    card = page.locator("#playground-card")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Card preview")
    expect(card).to_contain_text("Open until dusk.")
    held.pop().continue_()
    wait_until_ready(page)
    expect(card).to_have_css("border-radius", "12px")
    expect(card).to_have_css("border-top-color", "rgb(79, 118, 111)")
    expect(page.locator("#card-playground")).to_have_attribute(
        "data-playground-tone", "quiet"
    )
    assert (
        card.evaluate("e => getComputedStyle(e, '::before').content") == '"Field note"'
    )


def playground_values(page):
    return page.locator("#card-playground").evaluate("root => ({...root.values})")


def test_a_playground_keeps_one_typed_working_state_until_the_user_chooses(
    browser, serve
):
    """The accent is typed in capitals, so the state the page keeps, writes into its
    instruction and sends is the colour's one lowercase spelling, the colour field's
    own."""
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
    page.locator('input[name="title"]').fill("Ridge note; alert")
    page.keyboard.press("Tab")
    round_trip(page)

    # Each committed edit records the settings, asking nothing of the agent.
    tunes = events_model.read_events(serve.page_dir)[before:]
    assert {event["action"] for event in tunes} == {"tune"}
    assert not any(event["attention"] for event in tunes)
    assert tunes[-1]["detail"]["values"] == playground.evaluate("root => root.values")
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
    playground.get_by_role("button", name="Show instruction").click()
    assert "\n" not in page.locator("#card-instruction").inner_text()
    page.keyboard.press("Escape")

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

    expect(playground.get_by_role("button", name="Undo choice")).to_be_visible()

    page.reload()
    wait_until_ready(page)
    expect(page.locator("#card-instruction")).to_contain_text("17px radius")
    assert playground.evaluate("root => root.values")["title"] == "Ridge note; alert"
    expect(playground.get_by_role("button", name="Undo choice")).to_be_visible()
    title = playground.get_by_label("Title", exact=True)
    title.fill("Another title")
    expect(playground.get_by_role("button", name="Use these settings")).to_be_visible()
    title.fill("Ridge note; alert")
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    with sending(page, "the refused withdrawal"):
        playground.get_by_role("button", name="Undo choice").click()
    expect(playground.get_by_role("button", name="Undo choice")).to_be_visible()
    consume_browser_errors(page, http_error_console(400))
    page.unroute("**/api/event")
    with sending(page, "withdraw the playground choice"):
        playground.get_by_role("button", name="Undo choice").click()
    assert events_model.read_events(serve.page_dir)[-1]["undoes"] == action["id"]
    expect(playground.get_by_role("button", name="Use these settings")).to_be_visible()
    expect(title).to_have_value("Ridge note; alert")


def test_narrow_playground_keeps_complete_preset_labels_operable(browser, serve):
    label = "Recommended: 6 pages, 1 false, none missed"
    source = leaf_page(
        "Complete preset labels",
        f"""<h1>Tune alert policy</h1>
<lf-group id="policy-q" label="Which alert policy?"><lf-playground id="policy">
  <lf-playground-preset id="policy-preset" label="{label}">
    <lf-playground-setting for="threshold" value="6"></lf-playground-setting>
  </lf-playground-preset>
  <p>Six minutes catches the incident with time to act.</p>
  <label id="threshold">Threshold <input type="range" name="threshold" min="1" max="10" value="5" /></label>
  <lf-playground-output>Use a <output for="threshold"></output> minute threshold.</lf-playground-output>
</lf-playground></lf-group>""",
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


SHORT_WORKSPACE_PLAYGROUND = leaf_page(
    "Short alert workspace",
    '<header><h1 id="tune-h">Tune alert policies</h1>'
    "<p>Compare the last month of incidents before setting the latency window. "
    "Keep every real incident visible while reducing unnecessary pages for the "
    "on-call engineer.</p></header>"
    '<lf-group id="tune" label="Tune alert policies">'
    '<lf-playground id="short-config" data-width="available">'
    '<lf-playground-preset id="preset-suggested-window" label="Suggested window">'
    '<lf-playground-setting for="latency" value="5"></lf-playground-setting>'
    "</lf-playground-preset>"
    "<h2>Checkout latency</h2>"
    "<p>The last incident lasted seven minutes. Tune its alert beside this evidence.</p>"
    '<label id="latency">Latency window, min <input type="range" name="latency" min="1" max="15" value="5" /></label>'
    "<lf-playground-output>"
    + "Include alert evidence, validation, routing and deployment instructions. "
    * 100
    + '<span id="instruction-end">Finish with the rollback procedure.</span>'
    "</lf-playground-output></lf-playground></lf-group>",
    layout="workspace",
)


def test_inline_playground_keeps_half_a_short_workspace_for_its_stage(browser, serve):
    """With its controls on the stage, a playground in a short workspace keeps at least
    half the window for the stage. Presets stay visible and Tab brings its actions into
    the window: where the floating panel's row would stand over all of one at the
    window's foot, the panel folds to the leaf, so the next Tab moves on from it rather
    than letting go of a control out of sight. A long instruction scrolls inside its
    popover."""
    page = open_page(browser, serve(SHORT_WORKSPACE_PLAYGROUND))
    resized(page, 900, 500)
    panel = page.locator(".lf-floating-panel")
    playground = page.locator("#short-config")
    preview = playground.locator(".lf-playground-preview-body")
    expect(
        playground.get_by_role("button", name="Suggested window")
    ).to_be_in_viewport()
    split = playground.locator(".lf-playground-split").bounding_box()
    assert preview.bounding_box()["width"] == pytest.approx(split["width"], abs=1)
    stage = playground.locator(".lf-playground-preview-region").bounding_box()
    assert stage["height"] >= 500 / 2 - 0.5
    submit = playground.get_by_role("button", name="Use these settings")
    slider = playground.get_by_role("slider", name="Latency window")
    slider.press("ArrowRight")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    reset = playground.get_by_role("button", name="Reset", exact=True)
    reveal = playground.get_by_role("button", name="Show instruction")
    for key, target in [("Tab", reset), ("Tab", reveal), ("Shift+Tab", reset)]:
        page.keyboard.press(key)
        expect(target).to_be_focused()
        expect(panel).to_have_attribute("data-lf-rest", "mark")
        scroll_settled(page, "#tune")
        assert target.evaluate(UNCOVERED), (
            f"{key} left {target.get_attribute('aria-label')} covered"
        )
    page.keyboard.press("Enter")
    expect(slider).to_have_value("5")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    body = playground.locator(".lf-playground-instruction-body")
    assert body.evaluate("node => node.scrollHeight > node.clientHeight + 1")
    end = page.locator("#instruction-end")
    end.scroll_into_view_if_needed()
    expect(end).to_be_in_viewport()
    page.keyboard.press("Escape")
    slider.press("ArrowRight")
    expect(slider).to_have_value("6")
    view = preview.bounding_box()
    field = slider.bounding_box()
    assert view["y"] <= field["y"] < view["y"] + view["height"]
    action = submit.bounding_box()
    main = page.locator("main").bounding_box()
    assert action["y"] + action["height"] <= main["y"] + main["height"]
    with sending(page, "the short-workspace configuration"):
        submit.click()
    assert events_model.read_events(serve.page_dir)[-1]["detail"]["values"] == {
        "latency": 6
    }


def test_a_playground_in_a_short_page_tab_keeps_its_actions_in_reach(browser, serve):
    """A page tab that is one block, a playground's question group, passes the window's
    height to the playground, and where the window is shorter than the playground's
    stage and bar the tab keeps the playground's height, so the tab set scrolls to the
    bar, and Tab brings each action into the window. Were the tab to shrink to the
    window, the group would run past it and the set would never bring Reset in."""
    source = leaf_page(
        "Alert tabs",
        '<header><h1 id="tabs-h">Tune alert policies</h1></header>'
        '<lf-tabs id="views" flow="page"><lf-tab id="t-tune" label="Tune">'
        '<lf-group id="tune" label="Which latency window?">'
        '<h2 id="tune-q">Which latency window?</h2>'
        '<lf-playground id="tab-config" data-width="available">'
        '<lf-playground-preset id="tab-preset" label="Suggested window">'
        '<lf-playground-setting for="latency" value="5"></lf-playground-setting>'
        "</lf-playground-preset>"
        "<p>The last incident lasted seven minutes.</p>"
        '<label id="latency">Latency window, min <input type="range" name="latency"'
        ' min="1" max="15" value="5" /></label>'
        '<lf-playground-output>Use a <output for="latency"></output> minute window.'
        "</lf-playground-output></lf-playground></lf-group></lf-tab>"
        '<lf-tab id="t-notes" label="Notes"><p>Notes.</p></lf-tab></lf-tabs>',
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 900, 500)
    playground = page.locator("#tab-config")
    slider = playground.get_by_role("slider", name="Latency window")
    slider.press("ArrowRight")
    for target in [
        playground.get_by_role("button", name="Reset", exact=True),
        playground.get_by_role("button", name="Show instruction"),
        playground.get_by_role("button", name="Use these settings"),
    ]:
        page.keyboard.press("Tab")
        expect(target).to_be_focused()
        assert target.evaluate(IN_WINDOW), (
            f"{target.get_attribute('aria-label')} is out of the window"
        )


@pytest.mark.parametrize("over", ["stage", "presets"])
def test_the_wheel_takes_a_short_workspace_to_its_playgrounds_send(
    browser, serve, over
):
    """In a short workspace that scrolls to the playground's Send, a wheel over the
    stage, once the stage is at its end, or over the presets scrolls the workspace and
    brings Send into view. Chromium kept that wheel in the region under the pointer,
    which left only a wheel over the premise to reach Send."""
    page = open_page(browser, serve(SHORT_WORKSPACE_PLAYGROUND))
    resized(page, 900, 500)
    playground = page.locator("#short-config")
    submit = playground.get_by_role("button", name="Use these settings")
    expect(submit).not_to_be_in_viewport(ratio=1)
    region = playground.locator(
        ".lf-playground-preview-body" if over == "stage" else ".lf-playground-presets"
    )
    region.evaluate("body => { body.scrollTop = body.scrollHeight; }")
    box = region.bounding_box()
    page.mouse.move(box["x"] + box["width"] - 40, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 400)
    expect(submit).to_be_in_viewport(ratio=1)


def test_a_playground_followed_by_a_note_keeps_its_actions_off_the_note(browser, serve):
    # From the bad-pages eval (notes/agent-usability-evals.md): two of three authors
    # put an open note after the playground, and the pane of its actions drew over it
    # at 900px.
    source = leaf_page(
        "Alert workspace with a note",
        '<lf-group id="noted-ask" label="Tune alert policies"><h1 id="noted-ask-h">Tune alert policies</h1>'
        '<lf-playground id="noted-config" data-width="available">'
        + "<p>Checkout latency fired seven times last month.</p>"
        * 12
        + '<label id="latency">Latency window, min <input type="range" name="latency" min="1" max="15" value="5" /></label>'
        "<lf-playground-output>"
        "Apply the chosen latency window.</lf-playground-output></lf-playground>"
        '<details id="tally-note" open><summary>How the tally counts</summary>'
        + "<p>Each firing counts once per alert.</p>" * 6
        + "</details></lf-group>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 900, 700)
    actions = page.locator("#noted-config .lf-playground-instruction-region")
    note = page.locator("#tally-note")
    assert (
        actions.bounding_box()["y"] + actions.bounding_box()["height"]
        <= note.bounding_box()["y"] + 0.5
    )
    note.scroll_into_view_if_needed()
    expect(note.get_by_text("How the tally counts")).to_be_in_viewport()


def test_a_small_playground_keeps_its_controls_next_to_its_content(browser, serve):
    """In document flow, a small preview ends at its content, so the controls and
    instruction below it aren't separated from the evidence by an empty well."""
    source = leaf_page(
        "Small configuration",
        '<lf-group id="small-playground-q" label="Which configuration?"><lf-playground id="small-playground">'
        '<aside><fieldset id="priority"><legend>Priority</legend>'
        '<label id="priority-normal"><input type="radio" name="priority" value="normal" checked> Normal</label>'
        '<label id="priority-urgent"><input type="radio" name="priority" value="urgent"> Urgent</label>'
        "</fieldset></aside>"
        "<table><tbody><tr><th>Daily export</th><td>Ready</td></tr>"
        "<tr><th>Weekly digest</th><td>Ready</td></tr></tbody></table>"
        "<lf-playground-output>Run the two jobs.</lf-playground-output>"
        "</lf-playground></lf-group>",
    )
    page = open_page(browser, serve(source))
    for width in (640, 390):
        resized(page, width, 844)
        room = page.locator(".lf-playground-stage").evaluate(
            """stage => stage.getBoundingClientRect().bottom
              - parseFloat(getComputedStyle(stage).paddingBottom)
              - parseFloat(getComputedStyle(stage).borderBottomWidth)
              - stage.lastElementChild.getBoundingClientRect().bottom"""
        )
        assert room == pytest.approx(0, abs=1)
        expect(page.get_by_role("radio", name="Urgent")).to_be_in_viewport()
        expect(page.locator(".lf-playground-actions")).to_be_in_viewport()


def test_an_artifact_that_changes_height_leaves_the_stage_where_it_stands(
    browser, serve
):
    """The stage starts its artifacts at its top, so an artifact a control shrinks or
    grows moves nothing above or beside it, even where the rail holds the stage taller
    than what stands on it."""
    source = leaf_page(
        "Stage",
        '<lf-group id="stage-ask" label="Choose a density"><h1 id="stage-ask-h">Choose a density</h1>'
        '<lf-playground id="stage-playground">'
        '<aside><label id="rows">Rows <input type="range" name="rows" min="1" max="8" value="4" /></label>'
        '<fieldset id="mode"><legend>Mode</legend>'
        '<label id="mode-a"><input type="radio" name="mode" value="a" checked> A</label>'
        '<label id="mode-b"><input type="radio" name="mode" value="b"> B</label>'
        "</fieldset></aside>"
        '<div id="first">First</div>'
        '<div id="artifact" style="height: 200px">Artifact</div>'
        "<lf-playground-output>Use the chosen density.</lf-playground-output>"
        "</lf-playground></lf-group>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 900)
    first = page.locator("#first")
    before = first.bounding_box()["y"]
    page.locator("#artifact").evaluate("node => { node.style.height = '40px'; }")
    assert first.bounding_box()["y"] == before


def test_notification_playground_sets_regions_side_by_side_while_its_workspace_is_full_height(
    browser, serve
):
    """A playground is a workspace with its relationship declared: the preview is the
    stage, with the controls and the instruction they write in a rail beside it. While
    the root workspace fills the window the preview and controls scroll on their own,
    the controls under their fixed presets, while the actions scroll with their holder; where it
    doesn't, the page scrolls all three, and a narrow one stacks the regions. A window
    shorter than 480px keeps the rail beside the stage but doesn't hold it in view,
    since the rail would show a few lines and its actions only by scrolling inside it.
    Either way each is a named reading region."""
    source = named_source("notification-playground")
    page = open_page(browser, serve(source))
    playground = page.locator("#notification-playground")
    controls = playground.locator(".lf-playground-controls-region > aside")
    preview = playground.locator(".lf-playground-preview-body")
    presets = playground.get_by_role("group", name="Starting points")
    actions = playground.locator(".lf-playground-actions")
    reading = """async () => {
      const leaf = await Promise.all([window.__lfWidgetApi(), window.__lfCheckApi()]).then(parts => Object.assign({}, ...parts));
      const {readingRegionFor} = leaf;
      const playground = document.querySelector('#notification-playground');
      const controls = playground.querySelector('.lf-playground-controls-region > aside');
      const preview = playground.querySelector('.lf-playground-preview-body');
      const instruction = playground.querySelector('.lf-playground-actions');
      const region = (body) => readingRegionFor(body);
      const controlsBox = region(controls).host.getBoundingClientRect();
      const previewBox = region(preview).host.getBoundingClientRect();
      const instructionBox = region(instruction).host.getBoundingClientRect();
      return {
        controlsId: region(controls).id,
        previewId: region(preview).id,
        instructionId: region(instruction).id,
        scroll_behaviors: [controls, preview, instruction].map((body) =>
          leaf.regionScrollBehavior(region(body))),
        scrollers: [controls, preview, instruction].map((body) =>
          leaf.scrollerFor(body) === body ? 'own' :
          leaf.scrollerFor(body) === document.scrollingElement ? 'page' :
          leaf.scrollerFor(body) === playground.querySelector('.lf-playground-rail')
            ? 'rail' : leaf.scrollerFor(body).contains(body) ? 'ancestor' : 'unrelated'),
        sideBySide: Math.abs(previewBox.top - controlsBox.top) < 1
          && controlsBox.left >= previewBox.right
          && Math.abs(instructionBox.left - controlsBox.left) < 1
          && instructionBox.top >= controlsBox.bottom,
        stacked: controlsBox.bottom <= previewBox.top + 1,
        presetsHeadControls: controls.previousElementSibling
          === playground.querySelector('.lf-playground-presets'),
        controlsSize: [controls.clientHeight, controls.scrollHeight],
        pageScrolls: document.scrollingElement.scrollHeight > innerHeight,
        obligationDisplay: getComputedStyle(document.querySelector('#notification-ask')).display,
        authoredWords: leaf.named(playground).includes('Concurrent release events'),
        spokenWords: leaf.says(playground).includes('Concurrent release events'),
      };
    }"""

    # Without a Controls label or a Starting points label over them, the list fits
    # at 600px tall; 530 still runs it past the rail's foot, so it scrolls.
    resized(page, 1100, 530)
    expect(actions).to_be_visible()
    bounded = page.evaluate(reading)
    assert bounded == {
        **bounded,
        "controlsId": "lf-region:notification-playground:controls",
        "previewId": "lf-region:notification-playground:preview",
        "instructionId": "lf-region:notification-playground:instruction",
        "scroll_behaviors": ["bounded", "bounded", "flow"],
        "scrollers": ["own", "own", "ancestor"],
        "sideBySide": True,
        "presetsHeadControls": True,
        "pageScrolls": False,
        "obligationDisplay": "flex",
        "authoredWords": True,
        "spokenWords": True,
    }
    assert bounded["controlsSize"][1] > bounded["controlsSize"][0], bounded
    # The band is its buttons alone; "Starting points" only names the group.
    expect(presets).to_have_text(
        re.compile(r"^\s*Routine release\s*Needs attention\s*$")
    )
    # The presets band heading the controls is ruled off from them, over the generic
    # region header's unruled box.
    assert playground.locator(".lf-playground-presets").evaluate(
        """node => {
          const style = getComputedStyle(node);
          return [style.borderBottomStyle, style.paddingBottom];
        }"""
    ) == ["solid", "14px"]
    first_control = controls.locator(":scope > *").first
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
    assert (
        action_box["y"] + action_box["height"]
        <= playground_box["y"] + playground_box["height"] + 1
    )

    for width, height in [(1100, 300), (700, 500), (500, 900)]:
        resized(page, width, height)
        flow = page.evaluate(reading)
        # Too short to hold the regions is not too narrow to set them side by side.
        assert flow["stacked"] is (width < 1100), (width, height, flow)
        assert flow == {
            **flow,
            "scroll_behaviors": ["flow", "flow", "flow"]
            if width == 1100
            else ["bounded", "flow", "flow"],
            "scrollers": ["page", "page", "page"]
            if width == 1100
            else ["own", "page", "page"],
            "pageScrolls": True,
            "obligationDisplay": "block",
        }, (width, height)


def test_a_playground_opens_its_instruction_over_the_page(browser, serve):
    """The instruction pane is a bar of Reset, the instruction's reveal and the
    submission. The reveal opens the instruction in a popover over the page, so reading
    it moves nothing the user set or pressed; a second press, or Escape, closes it and
    leaves the user on the reveal. Tab goes on from the reveal to the copy."""
    source = leaf_page(
        "Instruction popover",
        '<button id="outside">Before playground</button>'
        '<lf-group id="fold-ask" label="Choose a density"><h1 id="fold-ask-h">Choose a density</h1>'
        '<lf-playground id="fold-playground" data-width="available">'
        '<aside><label id="rows">Rows <input type="range" name="rows" min="1" max="8" value="4" /></label></aside>'
        "<p>Rows of the report.</p>"
        '<button id="preview-action">Preview action</button>'
        '<lf-playground-output>Use <output for="rows">'
        "</output> rows in the weekly report and show me its "
        "rendered page.</lf-playground-output>"
        "</lf-playground></lf-group>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 800)
    playground = page.locator("#fold-playground")
    instruction = playground.locator("lf-playground-output")
    reveal = playground.get_by_role("button", name="Show instruction")
    expect(playground.get_by_role("button", name="Reset")).to_be_visible()
    expect(instruction).to_be_hidden()
    rail = playground.locator(".lf-playground-rail").bounding_box()
    pressed = reveal.bounding_box()

    page.locator("#outside").click()
    reveal.click()
    expect(reveal).to_have_attribute("aria-expanded", "true")
    expect(instruction).to_contain_text("Use 4 rows")
    expect(instruction).to_be_visible()
    assert reveal.bounding_box() == pytest.approx(pressed, abs=0.5)
    assert playground.locator(".lf-playground-rail").bounding_box() == rail
    reveal.click()
    expect(instruction).to_be_hidden()
    expect(reveal).to_have_attribute("aria-expanded", "false")

    reveal.press("Enter")
    expect(instruction).to_be_visible()
    page.keyboard.press("Tab")
    expect(playground.get_by_role("button", name="Copy instruction")).to_be_focused()
    # The Tab showed Copy's preview, which the first Escape puts away.
    put_preview_away(page)
    page.keyboard.press("Escape")
    expect(instruction).to_be_hidden()
    expect(reveal).to_be_focused()

    preview = playground.get_by_role("button", name="Preview action")
    preview.click()
    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(preview).to_be_focused()
    reveal.click()
    expect(instruction).to_be_visible()
    expect(reveal).to_be_focused()
    reveal.click()
    expect(instruction).to_be_hidden()


def test_built_code_reader_design_comment_keeps_its_identity_after_revision(
    browser, serve
):
    """The shared comment loop carries a design request through a real reader revision.
    Design mode's keyboard and touch routes to a target are the aim tests'
    (`test_render_aim.py`); this picks the built reader's heading by pointer."""
    source_path = named_source("code-comparison")
    source = source_path.read_text(encoding="utf-8")
    page = open_page(browser, live_url(serve(source_path)))
    page.get_by_role("tab", name="Comment on the reader").click()
    page.locator("#target-reader-heading").scroll_into_view_if_needed()
    page.keyboard.press("l")
    page.locator("#target-reader-heading").click()
    field = page.locator(".lf-fab-input")
    write(field, "Keep the heading aligned with the reader's first line.")
    send = page.locator(".lf-fab-bar .lf-compose-submit")
    # Over the draft's words, Send takes a press only after the pointer rests
    # in its corner. Move there before click's actionability check.
    corner = send.bounding_box()
    assert corner is not None
    page.mouse.move(
        corner["x"] + corner["width"] / 2, corner["y"] + corner["height"] / 2
    )
    expect(page.locator(".lf-fab-bar .lf-compose-field")).to_have_attribute(
        "data-lf-send-armed", ""
    )
    with sending(page, "the reader design comment"):
        send.click()
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
    head = open_panel_thread(page, event["id"]).locator(".lf-thread-quote-head")
    expect(head).to_contain_text("target-reader-heading")
    expect(head).not_to_have_attribute("data-lf-detached", "")


def test_a_press_in_flight_does_what_the_playground_button_says(browser, serve):
    """The press draws its result at once and leaves the button as it was, neither
    busy nor disabled, so the next press acts on what the button now says."""
    page = open_page(browser, serve(PLAYGROUND_PAGE))
    playground = page.locator("#card-playground")
    choose = playground.locator(".lf-playground-submit")
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    with page.expect_request("**/api/event"):
        choose.press("Enter")
    holding(page, held, 1, "the playground choice")
    expect(choose).to_have_text("Undo choice")
    expect(choose).to_be_enabled()
    expect(choose).not_to_have_attribute("aria-busy", "true")
    expect(choose).to_be_focused()
    choose.press("Space")
    expect(choose).to_have_text("Use these settings")
    expect(choose).to_be_enabled()

    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect(choose).to_have_text("Use these settings")
    expect(choose).to_be_focused()
    chosen = actions(serve.page_dir)
    assert len(chosen) == 1
    assert [
        e["undoes"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "undo"
    ] == [chosen[0]["id"]]


def test_playgrounds_keep_their_own_radios_from_the_first_paint(browser, serve):
    """Until a playground's drawing puts its radios in a form of its own, they share a
    group with every same-named radio no form holds, so a second playground's checked
    default unchecks the first's as the page parses. Each still shows and sends its own
    default. A radio a page's form claims by its `form` attribute is that form's, so it
    joins no playground's configuration and keeps apart from both."""

    def playground(ident, checked):
        radios = "".join(
            f'<label id="{ident}-{value}"><input type="radio" name="mode"'
            f' value="{value}"{" checked" if value == checked else ""}> {value}</label>'
            for value in "ab"
        )
        return (
            f'<lf-group id="{ident}-q" label="Which mode?"><lf-playground id="{ident}"><aside><fieldset><legend>Mode</legend>'
            f"{radios}</fieldset>"
            f'<label id="{ident}-kept"><input type="radio" name="kept" value="x"'
            ' form="outer"> Kept apart</label></aside><p>Preview</p>'
            f'<lf-playground-output id="{ident}-task">Use'
            ' <output for="mode"></output>.</lf-playground-output></lf-playground></lf-group>'
        )

    source = leaf_page(
        "Two playgrounds",
        '<form id="outer">'
        + playground("first", "a")
        + playground("second", "b")
        + "</form>",
    )
    page = open_page(browser, serve(source))
    for ident, checked in (("first", "a"), ("second", "b")):
        playground = page.locator(f"#{ident}")
        expect(page.locator(f"#{ident}-{checked} input")).to_be_checked()
        expect(page.locator(f"#{ident}-task")).to_have_text(f"Use {checked}.")
        assert playground.evaluate("root => root.values") == {"mode": checked}
    page.locator("#second-a input").check()
    expect(page.locator("#first-a input")).to_be_checked()
    assert page.locator("#first").evaluate("root => root.values") == {"mode": "a"}
    assert page.locator("#second").evaluate("root => root.values") == {"mode": "a"}


def test_reset_and_a_preset_rewrite_the_fields_they_set(browser, serve):
    """Reset writes a number field the user cleared back to its authored value, which
    is what it sends, and a preset may write a colour in capitals, which its field holds
    lowercase."""
    source = leaf_page(
        "Number and colour",
        '<lf-group id="tuned-q" label="Which number and colour?"><lf-playground id="tuned"><aside>'
        '<label id="count">Count <input type="number" name="count" value="5"></label>'
        '<label id="accent">Accent <input type="color" name="accent"'
        ' value="#4f766f"></label></aside>'
        '<lf-playground-preset id="preset-plum" label="Plum">'
        '<lf-playground-setting for="accent" value="#8B4A5F"></lf-playground-setting>'
        "</lf-playground-preset><p>Preview</p>"
        '<lf-playground-output>Use <output for="count"></output>.</lf-playground-output>'
        "</lf-playground></lf-group>",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#tuned")
    count = playground.get_by_role("spinbutton", name="Count")
    count.fill("")
    playground.get_by_role("button", name="Reset", exact=True).click()
    expect(count).to_have_value("5")
    playground.get_by_role("button", name="Plum", exact=True).click()
    expect(playground.get_by_label("Accent", exact=True)).to_have_value("#8b4a5f")
    assert playground.evaluate("root => root.values") == {
        "count": 5,
        "accent": "#8b4a5f",
    }


def test_a_playground_refuses_a_preset_its_field_cannot_hold(browser, serve):
    """A preset's setting must be a value its field can hold, as the browser
    sanitizes the field's values; a radius past the slider's max fails the playground
    where the page's checks read failures, rather than leaving a preset that never
    shows pressed."""
    source = PLAYGROUND_PAGE.replace(
        '<lf-playground-setting for="radius" value="4">',
        '<lf-playground-setting for="radius" value="40">',
    )
    assert source != PLAYGROUND_PAGE
    page = open_page(browser, serve(source))
    refusal = "preset Dense sets radius to 40, which it can't hold"
    expect(page.locator("#card-playground .lf-error")).to_contain_text(refusal)
    consume_browser_errors(page, refusal)


def test_a_playground_field_written_in_the_preview_stands_beside_its_item(
    browser, serve
):
    """The alert playground writes each alert's threshold and route beside that alert's
    replay, and the page budget in its aside. The budget stands in the rail; each
    alert's fields stand where they are written, and a press there changes the
    playground's one configuration and the instruction it sends."""
    source = named_source("alert-thresholds")
    page = open_page(browser, serve(source))
    playground = page.locator("#alert-playground")
    rail = playground.locator(".lf-playground-controls-region > aside")
    expect(rail.locator("input")).to_have_count(2)
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


PAGE_ACTIONS_PAGE = leaf_page(
    "page-drawn playground",
    """
<style>tile-tool button { font-size: 19px; }</style>
<lf-group id="tile-ask" label="Choose the tile size"><h1 id="tile-ask-h">Choose the tile size</h1>
<lf-playground id="tile-config">
  <tile-tool><button type="submit" class="tile-save">Keep this size</button>
    <button type="reset">Reset</button></tile-tool>
  <lf-playground-output>Keep the tile size.</lf-playground-output>
</lf-playground></lf-group>
<script type="module">
import {whileInterfaceConnected} from "/runtime/widget-api.js";
import {once} from "/runtime/lib/once.js";
customElements.define("tile-tool", class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const button = (text) => {
      const node = document.createElement("button");
      node.type = "button";
      if (text) node.textContent = text;
      return node;
    };
    const grow = button("Grow");
    const save = this.querySelector(".tile-save"), reset = this.querySelector('[type="reset"]');
    const tools = document.createElement("div");
    tools.setAttribute("data-lf-gen", "1");
    tools.toggleAttribute("data-lf-said", true);
    tools.append(grow, save, reset);
    this.append(tools);
    const playground = this.closest("lf-playground");
    whileInterfaceConnected(this, {
      declare: () => {
        const tile = playground.registerContributor("tile", {size: 2}, tools);
        playground.registerInstructionProvider(v => `Make tiles ${v.tile.size} units.`);
        grow.addEventListener("click", () => tile.set({size: tile.get().size + 1}));
      },
      connect: () => playground.subscribe(() => {}),
    });
  }
});
</script>
""",
)


def test_a_page_draws_the_actions_of_a_playground_without_controls(browser, serve):
    """A preview's contributor and instruction make a whole playground. With a
    submit button of the page's own, which a script may move, Leaf draws no rail or
    bar; the page's buttons, which its CSS styles, submit, undo and reset, by pointer
    and by the playground's keys."""
    page = open_page(browser, serve(PAGE_ACTIONS_PAGE))
    playground = page.locator("#tile-config")
    save = playground.locator(".tile-save")
    expect(save).to_have_text("Keep this size")
    expect(
        playground.locator(".lf-playground-rail, .lf-playground-actions")
    ).to_have_count(0)
    assert save.evaluate("button => getComputedStyle(button).fontSize") == "19px"

    playground.get_by_role("button", name="Grow").click()
    with sending(page, "the tile size"):
        save.click()
    choice = events_model.read_events(serve.page_dir)[-1]
    assert choice["detail"] == {
        "values": {"tile": {"size": 3}},
        "instruction": "Make tiles 3 units.",
    }
    expect(save).to_have_text("Undo choice")

    # The playground's digit presses the page's button: here it withdraws the choice.
    save.focus()
    with sending(page, "the withdrawal"):
        page.keyboard.press("1")
    assert events_model.read_events(serve.page_dir)[-1]["undoes"] == choice["id"]
    expect(save).to_have_text("Keep this size")
    assert playground.evaluate("root => root.values.tile.size") == 3

    playground.get_by_role("button", name="Reset", exact=True).click()
    assert playground.evaluate("root => root.values.tile.size") == 2
    playground.get_by_role("button", name="Grow").click()
    page.keyboard.press("Alt+0")
    assert playground.evaluate("root => root.values.tile.size") == 2


def test_a_page_drawn_preset_sets_its_whole_slice_as_one_gesture(browser, serve):
    """The shadow scale's presets are the page's own buttons over its contributor
    slice. A press, by pointer or key, sets all three elevations at once and shows
    pressed; the playground records it as one gesture, so Undo restores the scale the
    preset replaced."""
    page = open_page(browser, serve(named_source("shadow-scale")))
    playground = page.locator("#shadow-playground")
    presets = playground.get_by_role("group", name="Start from")
    soft, deep, flat = (
        presets.get_by_role("button", name=name, exact=True)
        for name in ("Soft", "Deep", "Flat")
    )
    layers = playground.locator(".ws-row span")
    expect(soft).to_have_attribute("aria-pressed", "true")
    expect(layers).to_have_text("3 of 4")
    soft_scale = playground.evaluate("root => root.values.scale")

    def tunes():
        return [
            event["detail"]["values"]["scale"]
            for event in events_model.read_events(serve.page_dir)
            if event.get("action") == "tune"
        ]

    deep.click()
    expect(deep).to_have_attribute("aria-pressed", "true")
    expect(soft).to_have_attribute("aria-pressed", "false")
    expect(layers).to_have_text("2 of 4")
    deep_scale = playground.evaluate("root => root.values.scale")
    assert len(deep_scale["overlay"]) == 4 and deep_scale != soft_scale
    wait_for(tunes, lambda found: found == [deep_scale], failure="Deep never recorded")

    flat.focus()
    page.keyboard.press("Enter")
    expect(flat).to_have_attribute("aria-pressed", "true")
    expect(layers).to_have_text("1 of 4")
    wait_for(tunes, lambda found: len(found) == 2, failure="Flat never recorded")

    undo(page)
    expect(deep).to_have_attribute("aria-pressed", "true")
    assert playground.evaluate("root => root.values.scale") == deep_scale
    undo(page)
    expect(soft).to_have_attribute("aria-pressed", "true")
    expect(layers).to_have_text("3 of 4")
    assert playground.evaluate("root => root.values.scale") == soft_scale


def test_a_playground_rail_stays_in_view_beside_a_tall_stage(browser, serve):
    """The alert playground's stage, an alert per section with its controls beside it,
    runs past the window. While the user works down it, the rail beside it, the page
    budget, the instruction and the submit button, stays in the window, so the user
    sends what they set where they set it. In a window shorter than 480px the rail
    flows with the page, which scrolls to its submit button, and stacked at phone width
    its shared controls stay above the stage while the instruction follows it."""
    page = open_page(browser, serve(named_source("alert-thresholds")))
    resized(page, 1024, 768)
    playground = page.locator("#alert-playground")
    stage = playground.locator(".lf-playground-preview-region")
    budget = playground.get_by_role("slider", name="On-call page budget")
    submit = playground.get_by_role("button", name="Apply these settings")
    # The window the page shows ends where Leaf's floating row begins.
    floor = page.locator(".lf-fp-row").bounding_box()["y"]

    def within_window(locator):
        box = locator.bounding_box()
        return 0 <= box["y"] and box["y"] + box["height"] <= floor

    assert stage.bounding_box()["height"] > 2 * 768
    last = playground.locator(".lf-playground-stage fieldset").last
    last.scroll_into_view_if_needed()
    last.get_by_role("radio").last.click()
    assert stage.bounding_box()["y"] < -768
    assert within_window(budget) and within_window(submit)
    budget.press("ArrowRight")
    assert within_window(submit)

    # Bounded to a window shorter than 480px, the rail would show a few lines and its
    # submit button only by scrolling inside it, so there it flows and the page scrolls
    # to the button.
    resized(page, 844, 390)
    track = playground.locator(".lf-playground-rail")
    submit.scroll_into_view_if_needed()
    floor = page.locator(".lf-fp-row").bounding_box()["y"]
    assert within_window(submit)
    assert track.evaluate("rail => rail.scrollTop") == 0

    resized(page, 390, 844)
    page.evaluate("document.scrollingElement.scrollTop = 0")
    rail = playground.locator(".lf-playground-controls-region").bounding_box()
    shown = stage.bounding_box()
    assert rail["y"] + rail["height"] <= shown["y"]
    last.scroll_into_view_if_needed()
    floor = page.locator(".lf-fp-row").bounding_box()["y"]
    assert within_window(budget)
    last_box = last.bounding_box()
    controls_box = playground.locator(".lf-playground-controls-region").bounding_box()
    assert last_box["y"] >= controls_box["y"] + controls_box["height"]
    budget.press("ArrowRight")
    expect(budget).to_have_value("12")


def test_a_rail_taller_than_the_window_keeps_its_bar_whole_under_its_controls(
    browser, serve
):
    """A rail holding more controls than the window shows keeps its bar of actions
    whole at its foot and scrolls the controls in their pane, as a full-height
    workspace does. Scrolling as a whole, it cut the bar off at the window's foot
    behind a second scroll."""
    controls = "".join(
        f'<fieldset id="setting-{n}"><legend>Setting {n}</legend>'
        + "".join(
            f'<label id="setting-{n}-{value}"><input type="radio"'
            f' name="setting-{n}" value="{value}"{" checked" if value == "a" else ""}>'
            f" Choice {value}</label>"
            for value in "abcd"
        )
        + "</fieldset>"
        for n in range(6)
    )
    source = leaf_page(
        "Tall rail",
        '<h1>Tall rail</h1><lf-group id="tall-rail-q" label="Which settings?"><lf-playground id="tall-rail" data-width="available">'
        + f"<aside>{controls}</aside>"
        + "<p>The stage runs past the window.</p>" * 60
        + "<lf-playground-output>Use these settings.</lf-playground-output></lf-playground></lf-group>",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 700)
    rail = page.locator("#tall-rail .lf-playground-rail")
    reading = rail.evaluate("""rail => {
      const controls = rail.querySelector('.lf-playground-controls-region > aside');
      const bar = rail.querySelector('.lf-playground-instruction-region');
      return {
        bounded: getComputedStyle(rail).maxBlockSize !== 'none',
        railScrolls: rail.scrollHeight > rail.clientHeight,
        controlsScroll: controls.scrollHeight > controls.clientHeight,
        barWhole: bar.getBoundingClientRect().bottom
          <= rail.getBoundingClientRect().bottom + 0.5,
      };
    }""")
    assert reading == {
        "bounded": True,
        "railScrolls": False,
        "controlsScroll": True,
        "barWhole": True,
    }


def test_a_quoted_playground_shows_its_markup_with_its_fields_disabled(browser, serve):
    """A quotation takes no input and sends nothing: its fields show the values
    it quotes, disabled, and it draws no regions, presets or actions."""
    source = PLAYGROUND_PAGE.replace(
        '<lf-group id="card-playground-ask" label="How should the card look?">',
        '<lf-sample id="playground-example" label="card playground">',
    ).replace("</lf-group>", "</lf-sample>")
    page = open_page(browser, serve(source))
    playground = page.locator("#card-playground")

    expect(playground.get_by_role("button")).to_have_count(0)
    expect(playground.locator("input")).to_have_count(6)
    expect(playground.locator("input:enabled")).to_have_count(0)
    expect(playground.get_by_role("slider", name="Corner radius")).to_have_value("12")
    expect(playground.locator("lf-playground-preset:visible")).to_have_count(0)
    expect(playground.locator("#playground-card")).to_be_visible()
    expect(playground.locator("#card-instruction")).to_contain_text("12px radius")
    assert playground.evaluate("root => root.values")["compact"] is False
    assert playground.evaluate(
        """async root => {
          const {readingRegionFor} = await window.__lfCheckApi();
          return readingRegionFor(root.querySelector('#playground-card')) === undefined
            && !root.querySelector('[data-lf-reading-role]');
        }"""
    )


def test_a_comment_names_the_playground_member_it_points_at(browser, serve, subtests):
    """A field, an option and a preset are each a target of their own, so the aim
    takes the one whose id its label, fieldset or box carries rather than the
    playground around it. An option in the rail is its whole line, as far as the
    aside's right edge, and an option in the preview is its whole candidate. The
    comment records the id and names the member."""
    source = leaf_page(
        "Pick a word",
        """<lf-group id="word-ask" label="Which word should a box say?"><h2 id="word-ask-h">Which word should a box say?</h2>
<lf-playground id="word-playground">
  <lf-playground-preset id="start-today" label="Start from today">
    <lf-playground-setting for="word" value="today"></lf-playground-setting>
  </lf-playground-preset>
  <aside><fieldset id="word"><legend>At rest</legend><label id="word-today"><input type="radio" name="word" value="today" checked /> Reply, and Comment beside a target</label><label id="word-verb"><input type="radio" name="word" value="verb" /> Reply, Comment</label></fieldset></aside>
    <fieldset id="shape"><legend>Shape</legend>
      <div id="shape-round"><label><input type="radio" name="shape" value="round" checked /> Round</label>
        <p>A round box.</p>
      </div>
      <div id="shape-square"><label><input type="radio" name="shape" value="square" /> Square</label>
        <p>A square box.</p>
      </div>
    </fieldset>
  <lf-playground-output>
    Say <output for="word"></output>.
  </lf-playground-output>
</lf-playground></lf-group>""",
    )
    page = open_page(browser, serve(source))
    line = page.locator("#word-verb")
    aimed = page.locator("[data-lf-aimed]")
    aimed_member = "element => element.closest('[id]').id"
    page.keyboard.down("Alt")
    for member, reach in (
        ("word-verb", lambda: page.get_by_text("Reply, Comment", exact=True).hover()),
        (
            "word-verb",
            lambda: line.hover(
                position={"x": line.bounding_box()["width"] - 4, "y": 8}
            ),
        ),
        ("shape-square", lambda: page.get_by_text("A square box.", exact=True).hover()),
        ("word", lambda: page.get_by_text("At rest", exact=True).hover()),
        ("start-today", lambda: page.locator("#start-today > button").hover()),
    ):
        with subtests.test(member=member):
            reach()
            expect(aimed).to_have_count(1)
            assert aimed.evaluate(aimed_member) == member
    page.keyboard.up("Alt")
    # The line reaches past its words, or the second case above proved nothing.
    words_end = line.evaluate(
        """label => {
          const words = document.createRange();
          words.selectNodeContents(label.lastChild);
          return words.getBoundingClientRect().right;
        }"""
    )
    box = line.bounding_box()
    assert box["x"] + box["width"] - 4 > words_end

    page.get_by_text("Reply, Comment", exact=True).hover()
    page.keyboard.down("Alt")
    page.mouse.down()
    page.mouse.up()
    page.keyboard.up("Alt")
    field = text_field(page, name=re.compile(r"^Comment on .* · Reply, Comment$"))
    expect(field).to_be_focused()
    page.keyboard.type("Could this say less?")
    with sending(page, "the comment on the option"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["anchor"]) == ("comment", {"section": "word-verb"})
    expect(page.get_by_role("radio", name="Reply, Comment")).not_to_be_checked()


def test_playground_candidates_keep_previews_operable_and_submit_one_choice(
    browser, serve
):
    source = leaf_page(
        "Choose the notification",
        """<lf-group id="candidates-q" label="Which notification?">
<lf-playground id="candidates">
  <aside><label id="radius">Corner radius <input type="range" name="radius" min="0" max="24" value="10" /></label></aside>
    <fieldset id="format"><legend>Notification</legend>
      <div id="format-banner"><label><input type="radio" name="format" value="banner" checked /> Banner</label>
        <p>Checkout deployed.</p>
      </div>
      <div id="format-strip"><label><input type="radio" name="format" value="strip" /> Status strip</label>
        <p>Checkout · deployed · 18 checks passed</p>
        <label>Preview title <input id="preview-title" value="Checkout"></label>
        <details><summary>Open preview</summary><p>Preview details</p></details>
      </div>
    </fieldset>
  <lf-playground-output>Build the <output for="format"></output>.</lf-playground-output>
</lf-playground></lf-group>""",
    )
    page = open_page(browser, serve(source))
    playground = page.locator("#candidates")
    preview = page.locator("#preview-title")
    before = len(events_model.read_events(serve.page_dir))
    page.get_by_text("Open preview", exact=True).click()
    expect(page.get_by_text("Preview details", exact=True)).to_be_visible()
    preview.fill("Release complete")
    assert playground.evaluate("root => root.values") == {
        "radius": 10,
        "format": "banner",
    }
    page.get_by_role("radio", name="Banner", exact=True).press("ArrowRight")
    expect(page.get_by_role("radio", name="Status strip", exact=True)).to_be_checked()
    expect(preview).to_have_value("Release complete")
    round_trip(page)
    assert [
        (event["action"], event["detail"]["values"])
        for event in events_model.read_events(serve.page_dir)[before:]
    ] == [("tune", {"radius": 10, "format": "strip"})]
    page.reload()
    wait_until_ready(page)
    expect(page.get_by_role("radio", name="Status strip", exact=True)).to_be_checked()
    page.get_by_role("button", name="Reset", exact=True).click()
    expect(page.get_by_role("radio", name="Banner", exact=True)).to_be_checked()
    page.get_by_text("Checkout · deployed · 18 checks passed", exact=True).click()
    expect(page.get_by_role("radio", name="Status strip", exact=True)).to_be_checked()
    expect(page.get_by_role("radio", name="Status strip", exact=True)).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(page.get_by_role("radio", name="Banner", exact=True)).to_be_checked()
    page.keyboard.press("ArrowRight")
    with sending(page, "the selected candidate"):
        page.get_by_role("button", name="Use these settings").click()
    choice = events_model.read_events(serve.page_dir)[-1]
    assert choice["detail"] == {
        "values": {"radius": 10, "format": "strip"},
        "instruction": "Build the strip.",
    }
    quoted = source.replace(
        '<lf-playground id="candidates">',
        '<lf-sample id="quoted-candidates" label="Notification comparison">'
        '<lf-playground id="candidates">',
    ).replace("</lf-playground>", "</lf-playground></lf-sample>")
    page = open_page(browser, serve(quoted))
    expect(page.get_by_role("radio")).to_have_count(2)
    expect(page.locator("#candidates input[name]:enabled")).to_have_count(0)
    expect(page.get_by_text("Banner", exact=True)).to_be_visible()
    expect(page.get_by_text("Status strip", exact=True)).to_be_visible()
    expect(
        page.get_by_text("Checkout · deployed · 18 checks passed", exact=True)
    ).to_be_visible()


def test_a_choice_made_while_the_settings_hold_a_retired_field_reads_as_chosen(
    browser, serve
):
    """Settings the log holds for a name no control of this revision draws, such as a
    field an earlier revision had, stay out of what a choice records, so the page's
    contract still admits it, and the button then offers to undo the choice rather
    than send the same settings again."""
    url = serve(named_source("notification-playground"))
    page = open_page(browser, url)
    playground = page.locator("#notification-playground")
    choose = playground.locator(".lf-playground-submit")
    values = playground.evaluate("root => ({...root.values})")
    response = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": events_model.read_events(serve.page_dir)[-1]["revision"],
            "widget": "notification-playground",
            "action": "tune",
            "detail": {"values": {**values, "retired": "kept"}},
        },
    )
    assert response.ok
    wait_for(
        lambda: playground.evaluate(
            "root => root.state?.tune?.detail?.values?.retired"
        ),
        lambda retired: retired == "kept",
        failure="the page never read the other tab's settings",
    )

    choose.press("Enter")
    expect(choose).to_have_text("Undo choice")
    round_trip(page)
    expect(choose).to_have_text("Undo choice")
    assert actions(serve.page_dir)[-1]["detail"]["values"] == values
