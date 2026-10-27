"""Opaque samples use ordinary native delivery and reconnect after a reload."""

import json
import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from interact_support import wait_for
from playwright.sync_api import expect
from render_harness import (
    PANEL,
    consume_browser_errors,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    page_comment,
    scroll_settled,
    take_browser_errors,
    write,
)

from leaf import interaction_log as interaction_model
from leaf.render_checks import HANDOVER_DEADLINE_MS


@pytest.mark.parametrize("surface", ["panel", "page"])
@pytest.mark.parametrize("newer_input", [False, True])
def test_sample_upgrade_does_not_wait_for_child_saved_state(
    browser, serve, surface, newer_input
):
    """A saved-thread request waits for history and yields to a newer child draft, and
    in the panel to any draft in the field its view would take."""
    source = leaf_page(
        "Independent sample startup",
        '<h1>Independent sample startup</h1><p id="outer">Parent passage.</p>'
        '<lf-sample id="practice" label="Practice" window>'
        '<template id="practice-source" data-sample data-sample-events="history">'
        '<h1>Practice</h1><p id="inner">Child passage.</p>'
        "</template></lf-sample>",
        head="""<script id="history" type="application/json">
          [{"id":"saved-thread","kind":"comment","anchor":{"section":"inner"},
            "text":"A saved child conversation."}]
        </script>""",
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    route_pattern = re.compile(r"/api/samples/[^/]+/api/state")
    page.route(route_pattern, lambda route: held.append(route))
    page.goto(serve(source), wait_until="load")
    holding(page, held, 1, "the child's unanswered saved-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    expect(child.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    expect(child.locator("body")).not_to_have_attribute("inert")
    expect(child.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(child.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", "Page menu · Loading comments and choices…"
    )
    # The page's own panel floats over the window's foot, where the sample's stands
    # too until the page is scrolled to the foot room it keeps clear of its chrome.
    page.evaluate("scrollTo(0, document.scrollingElement.scrollHeight)")
    scroll_settled(page)
    outer_box = page_comment(page)
    write(outer_box, "Parent draft")
    page.keyboard.press("Escape")
    inner_box = page_comment(child)
    write(inner_box, "Child draft")
    page.keyboard.press("Escape")
    child.evaluate("""() => {
      window.sampleRequestReceived = false;
      document.documentElement.lfSample.receive(({method}) => {
        if (method === 'thread') window.sampleRequestReceived = true;
      });
    }""")
    sample.evaluate(
        """(sample, surface) => {
      window.sampleSelected = false;
      sample.showThread('saved-thread', {surface}).then(result => {
        window.sampleSelectionResult = result;
        window.sampleSelected = true;
      });
    }""",
        surface,
    )
    # The child has received this command before newer input supersedes it.
    child.wait_for_function("window.sampleRequestReceived")
    assert page.evaluate("window.sampleSelected") is False
    child_words = "Child draft"
    if newer_input:
        inner_box = page_comment(child)
        child_words = "A newer child draft owns this view"
        write(inner_box, child_words)
    expect(outer_box).to_have_js_property("value", "Parent draft")
    expect(inner_box).to_have_js_property("value", child_words)
    page.unroute(route_pattern)
    for route in held:
        route.continue_()
    page.wait_for_function("window.sampleSelected")
    # The panel's view of a thread would stand its reply in the field the child's words
    # stand in, so it yields to them as it does to newer input; the page's card doesn't.
    shown = not newer_input and surface == "page"
    assert page.evaluate("window.sampleSelectionResult") is shown
    expect(child.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(outer_box).to_have_js_property("value", "Parent draft")
    expect(inner_box).to_have_js_property("value", child_words)
    if newer_input:
        expect(inner_box).to_be_focused()
    if not shown:
        expect(child.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
        return
    expect(
        child.locator(".lf-page-thread").get_by_text(
            "A saved child conversation.", exact=True
        )
    ).to_be_visible()


def interaction_records(page, page_dir, *, document=None):
    """Read the persisted stream after this document's preceding records were sent."""
    checkpoint = uuid4().hex
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry.get("checkpoint") == checkpoint
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        (document or page).evaluate(
            """async checkpoint => {
              const {recordInteraction} = await window.__lfCheckApi();
              recordInteraction('test-checkpoint', {checkpoint});
            }""",
            checkpoint,
        )
    return [
        json.loads(line)
        for line in (page_dir / interaction_model.INTERACTIONS_FILE)
        .read_text()
        .splitlines()
    ]


def sample_records(page, serve, *, wait_phase=None):
    interaction_records(page, serve.page_dir)

    def read():
        return [
            row
            for line in (serve.page_dir / interaction_model.INTERACTIONS_FILE)
            .read_text()
            .splitlines()
            if (row := json.loads(line)).get("type") == "sample"
            and row["template"] == "practice-source"
        ]

    return (
        read()
        if wait_phase is None
        else wait_for(
            read,
            lambda records: any(row["phase"] == wait_phase for row in records),
            failure=f"the persisted sample {wait_phase} transition",
        )
    )


def test_samples_keep_native_loaders_forms_and_reload(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native sample delivery",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <link rel="stylesheet" href="/page/native.css">
    <img src="/page/native.svg" alt="Native resource">
    <form id="form"><button id="submit">Submit</button></form>
    <button id="popup">Open window</button>
    <lf-sample id="nested" label="Nested practice" window>
      <template id="nested-source" data-sample><h1>Nested page</h1></template>
    </lf-sample>
    <script type="module" src="/page/native.js"></script>
  </template>
</lf-sample>
""",
            ),
            page_files={
                "native.css": "h1 { color: rgb(12, 34, 56); }",
                "native.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20"/></svg>',
                "native.js": """
window.nativeModuleUrl = import.meta.url;
window.nativeXhr = () => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', new URL('native.css', import.meta.url));
  xhr.onload = () => resolve({status: xhr.status, text: xhr.responseText});
  xhr.onerror = reject;
  xhr.send();
});
window.nativeImage = () => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image.naturalWidth);
  image.onerror = reject;
  image.src = new URL('native.svg', import.meta.url);
});
document.querySelector('#form').addEventListener('submit', event => {
  event.preventDefault();
  window.submitted = true;
});
document.querySelector('#popup').addEventListener('click', () => {
  window.open('about:blank', '_blank');
});
""",
            },
        ),
    )
    sample = page.locator("#practice")
    sample.locator("iframe").wait_for(state="attached")
    child = sample.locator("iframe").element_handle().content_frame()
    child.wait_for_function(
        "document.body?.hasAttribute('data-lf-presented')", timeout=HANDOVER_DEADLINE_MS
    )
    sample.evaluate("async sample => await sample.ready")
    initial = sample_records(page, serve, wait_phase="loaded")
    assert {row["phase"] for row in initial} == {
        "queued",
        "allocating",
        "allocated",
        "admission",
        "loading",
        "loaded",
        "connected",
        "upgraded",
    }
    assert {row["allocation"] for row in initial} == {1}
    child_records = interaction_records(page, serve.page_dir, document=child)
    child_page = [row for row in child_records if row.get("type") == "test-checkpoint"][
        -1
    ]["page"]
    assert {row["sample"] for row in initial if row["sample"] is not None} == {
        child_page
    }
    assert {row["revision"] for row in initial} == {1}
    assert len({row["host"] for row in initial}) == 1
    assert all(row["elapsed"] >= 0 for row in initial)
    assert [row["elapsed"] for row in initial] == sorted(
        row["elapsed"] for row in initial
    )
    assert (
        next(row for row in initial if row["phase"] == "admission")["leafDocument"]
        == "1"
    )
    child.wait_for_function("!!window.nativeXhr")
    assert child.evaluate("nativeModuleUrl").startswith("http:")
    assert child.evaluate("nativeXhr()") == {
        "status": 200,
        "text": "h1 { color: rgb(12, 34, 56); }",
    }
    assert child.evaluate("nativeImage()") == 20
    expect(child.locator("h1").first).to_have_css("color", "rgb(12, 34, 56)")
    child.locator("#submit").click()
    assert child.evaluate("submitted")
    with page.expect_popup() as popup:
        child.locator("#popup").click()
    popup.value.close()
    nested = child.locator("#nested")
    nested.evaluate("async sample => await sample.ready")
    grandchild = nested.locator("iframe").element_handle().content_frame()
    expect(grandchild.locator("h1")).to_have_text("Nested page")
    child_records = interaction_records(page, serve.page_dir, document=child)
    nested_identity = next(
        row["sample"]
        for row in child_records
        if row.get("type") == "sample"
        and row["template"] == "nested-source"
        and row["phase"] == "upgraded"
    )
    grandchild_records = interaction_records(page, serve.page_dir, document=grandchild)
    grandchild_page = [
        row for row in grandchild_records if row.get("type") == "test-checkpoint"
    ][-1]["page"]
    assert nested_identity == grandchild_page
    assert grandchild_page.startswith(child_page + "/api/samples/")
    child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      const response = await fetch('api/event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Leaf-Layer': state.layer.generation},
        body: JSON.stringify({kind: 'comment', revision: 1, text: 'Keep through reload', attempt: 'native-reload-comment'}),
      });
      if (!response.ok) throw new Error(await response.text());
    }""")
    # Reload again as soon as parsing finishes, before waiting for presentation.
    for _ in range(2):
        with child.expect_navigation(wait_until="domcontentloaded"):
            child.evaluate("location.reload()")
    child.wait_for_function("document.body?.hasAttribute('data-lf-presented')")
    expect(child.locator("h1").first).to_have_text("Practice page")
    child.wait_for_function("!!window.nativeXhr")
    sample.evaluate("async sample => await sample.ready")
    assert child.evaluate("nativeXhr()")["status"] == 200
    assert child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      return state.events.some(event => event.text === 'Keep through reload');
    }""")
    reloaded = sample_records(page, serve)
    documents = [row for row in reloaded if row["phase"] == "connected"]
    assert documents[0]["reloading"] is False
    assert documents[-1]["reloading"] is True
    assert documents[0]["document"] != documents[-1]["document"]
    assert {row["allocation"] for row in reloaded} == {1}
    assert [row for row in reloaded if row["phase"] == "upgraded"][-1][
        "document"
    ] == documents[-1]["document"]
    child.evaluate("""async () => {
      const {registerSampleCommand} = await window.__lfCheckApi();
      registerSampleCommand('thread', function rejectSampleCommand() {
        throw new RangeError('Sample command failed');
      });
    }""")
    command_error = sample.evaluate(
        "sample => sample.showThread('fault').catch(error => ({name: error.name, message: error.message, stack: error.stack}))"
    )
    assert command_error["name"] == "RangeError"
    assert command_error["message"] == "Sample command failed"
    assert "rejectSampleCommand" in command_error["stack"]
    sample.evaluate("sample => sample.remove()")
    destroyed = sample_records(page, serve)
    assert destroyed[-2]["phase"] == "destroyed"
    assert destroyed[-1]["phase"] == "retired"
    assert destroyed[-1]["reason"] == "destroyed"
    persisted = interaction_records(page, serve.page_dir)
    assert any(row.get("page") == grandchild_page for row in persisted)


def test_reload_swap_retires_pending_sample_faults(browser, serve):
    """A swap cancels old startup work without retiring the replacement allocation."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reload during startup",
                '<h1>Parent</h1><lf-sample id="practice" window>'
                '<template id="practice-source" data-sample><h1>Practice</h1></template>'
                "</lf-sample>",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    document_url = child.url
    stylesheets = []
    stylesheet_pattern = re.compile(
        re.escape(urlsplit(document_url).path) + r"revisions/[^/]+/[^/]+/theme.css$"
    )
    page.route(stylesheet_pattern, lambda route: stylesheets.append(route))
    with child.expect_navigation(wait_until="commit"):
        child.evaluate("location.reload()")
    holding(page, stylesheets, 1, "the middle document's pending stylesheet")
    page.unroute(stylesheet_pattern)
    destination = []
    page.route(document_url, lambda route: destination.append(route))
    child.evaluate("location.reload()")
    holding(page, destination, 1, "the replacement before its document swap")
    # The old realm remains alive while the server holds the destination. A native
    # task checkpoint cannot be mistaken for the document's actual departure.
    assert child.evaluate(
        "() => new Promise(resolve => setTimeout(() => resolve(document.body.isConnected), 0))"
    )
    assert sample.evaluate("sample => sample.isConnected")
    assert not [row for row in sample_records(page, serve) if row["phase"] == "failed"]
    with child.expect_navigation(wait_until="domcontentloaded"):
        destination[0].continue_()
    page.unroute(document_url)
    sample.evaluate("async sample => await sample.ready")
    expect(child.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(child.get_by_role("heading", name="Practice", exact=True)).to_be_visible()
    records = sample_records(page, serve)
    assert {row["allocation"] for row in records} == {1}
    assert not [row for row in records if row["phase"] in {"failed", "retired"}]
    assert len([row for row in records if row["phase"] == "departed"]) == 2
    assert len([row for row in records if row["phase"] == "connected"]) == 3
    assert take_browser_errors(page) == []


@pytest.mark.parametrize("status", [404, 200])
@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_sample_document_without_bootstrap_retires_and_can_reset(
    request, serve, status, engine
):
    """Initial admission rejects a non-Leaf response and permits immediate Reset."""
    url = serve(
        leaf_page(
            "Sample document failure",
            '<h1>Sample document failure</h1><lf-sample id="practice">'
            '<template id="practice-source" data-sample><h1>Practice</h1></template>'
            "</lf-sample>",
        )
    )
    page = request.getfixturevalue(engine).new_page()
    held = []
    navigation = re.compile(r"/api/samples/[^/]+/$")
    page.route(navigation, lambda route: held.append(route))
    page.goto(url, wait_until="domcontentloaded")
    sample = page.locator("#practice")
    holding(page, held, 1, "the failed sample document")
    failed_url = held[0].request.url
    held[0].fulfill(
        status=status,
        content_type="text/html",
        body="<html><body>Unavailable</body></html>",
    )
    expect(sample.locator(".lf-sample-status")).to_have_text(
        "The sample document did not start Leaf"
    )
    assert (
        sample.evaluate(
            "sample => sample.ready.then(() => null, error => error.message)"
        )
        == "The sample document did not start Leaf"
    )
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    assert page.request.get(failed_url + "api/state").status == 404
    records = sample_records(page, serve)
    assert [row["phase"] for row in records] == [
        "queued",
        "allocating",
        "allocated",
        "admission",
        "failed",
        "retired",
    ]
    assert records[3]["status"] == status
    assert records[3]["leafDocument"] is None
    assert records[4]["error"]["message"] == "The sample document did not start Leaf"
    assert records[5]["reason"] == "failure"
    page.unroute(navigation)
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice"
    )
    replacement = sample_records(page, serve)
    assert {row["host"] for row in replacement} == {records[0]["host"]}
    completed = [row for row in replacement if row["phase"] == "upgraded"][-1]
    assert completed["allocation"] == 2
    assert completed["document"]
    if status == 404:
        consume_browser_errors(
            page,
            http_error_console(404),
            "The sample document did not start Leaf",
        )
