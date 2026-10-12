"""Opaque samples use ordinary native delivery and reconnect after a reload."""

import json
import re
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from interact_support import wait_for
from leaf import interaction_log as interaction_model
from leaf.render_checks import HANDOVER_DEADLINE_MS
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    open_page,
    take_browser_errors,
)
from test_render_controls import leaf_page


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
              const {recordInteraction} = await __lfRuntimeImport('/runtime/interaction-log.js');
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
        "presented",
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
        and row["phase"] == "presented"
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
    assert [row for row in reloaded if row["phase"] == "presented"][-1][
        "document"
    ] == documents[-1]["document"]
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
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


def test_sample_view_selection_waits_across_a_reload(browser, serve):
    """A selection the child's reload interrupts lands in the next document."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reloading sample",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample><h1>Practice page</h1></template>
</lf-sample>
""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
      registerSampleCommand('thread', () => {
        window.waitingCommand = true;
        return new Promise(() => {});
      });
    }""")
    # The examples' own call shape: a page that does not await its selection.
    sample.evaluate("""sample => {
      void sample.showThread('unawaited');
      window.selection = sample.showThread('missing').then(
        shown => ({shown}), error => ({error: error.name}));
    }""")
    child.wait_for_function("window.waitingCommand")
    with child.expect_navigation(wait_until="domcontentloaded"):
        child.evaluate("location.reload()")
    assert page.evaluate("window.selection") == {"shown": False}
    sample.evaluate("async sample => await sample.ready")
    assert take_browser_errors(page) == []


@pytest.mark.parametrize("response_type", ["json", "html"])
def test_sample_release_failure_records_the_retired_allocation(
    browser, serve, response_type
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Release failure",
                '<lf-sample id="practice">'
                '<template id="practice-source" data-sample><h1>Practice</h1></template>'
                "</lf-sample>",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    response = (
        {"json": {"error": "Release unavailable"}}
        if response_type == "json"
        else {"content_type": "text/html", "body": "<h1>Proxy unavailable</h1>"}
    )
    page.route("**/api/release", lambda route: route.fulfill(status=503, **response))
    assert sample.evaluate(
        "sample => sample.reset().catch(error => error.message)"
    ) == ("Release unavailable" if response_type == "json" else "sample: HTTP 503")
    records = sample_records(page, serve)
    assert records[-1]["phase"] == "failed"
    assert records[-1]["operation"] == "release"
    assert records[-1]["error"]["name"] == "Error"
    assert records[-1]["error"]["status"] == 503
    assert records[-1]["sample"] == next(
        row["sample"] for row in records if row["phase"] == "allocated"
    )
    assert records[-1]["error"]["body"] == (
        json.dumps(response["json"]) if response_type == "json" else response["body"]
    )
    assert records[-1]["allocation"] == 1
    assert records[-1]["document"] == next(
        row["document"] for row in records if row["phase"] == "connected"
    )
    consume_browser_errors(page, "503")


def test_sample_startup_exception_keeps_its_name_stack_and_document(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Child startup failure",
                """
<lf-sample id="practice">
  <template id="practice-source" data-sample>
    <h1>Practice</h1>
    <script defer crossorigin="anonymous" src="/page/startup-fault.js"></script>
  </template>
</lf-sample>""",
            ),
            page_files={
                "startup-fault.js": "function startPractice() { throw new TypeError('Sample startup failed'); } startPractice();"
            },
        ),
    )
    sample = page.locator("#practice")
    exception = sample.evaluate(
        "sample => sample.ready.catch(error => ({name: error.name, message: error.message, stack: error.stack}))"
    )
    assert exception["name"] == "TypeError"
    assert exception["message"] == "Sample startup failed"
    assert "startPractice" in exception["stack"]
    records = sample_records(page, serve)
    failure = next(row for row in records if row["phase"] == "failed")
    assert failure["error"]["name"] == exception["name"]
    assert failure["error"]["message"] == exception["message"]
    assert failure["error"]["stack"] == exception["stack"]
    assert failure["sample"] in exception["stack"]
    assert records[-1]["sample"] == failure["sample"]
    consume_browser_errors(page, "Sample startup failed")


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
    completed = [row for row in replacement if row["phase"] == "presented"][-1]
    assert completed["allocation"] == 2
    assert completed["document"]
    if status == 404:
        consume_browser_errors(page, "404", "The sample document did not start Leaf")


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
@pytest.mark.parametrize("navigation", ["form", "script"])
def test_sample_native_departure_keeps_destination_and_reset(
    request, serve, engine, navigation
):
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Native departure",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <form action="https://docs.example.invalid/reference.html" method="get">
      <input name="q" value="term"><button>Search docs</button>
    </form>
  </template>
</lf-sample>
""",
            )
        ),
    )
    page.route(
        "https://docs.example.invalid/**",
        lambda route: route.fulfill(
            content_type="text/html", body="<!doctype html><h1>External reference</h1>"
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    previous = child.url
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
      registerSampleCommand('thread', () => {
        window.waitingCommand = true;
        return new Promise(() => {});
      });
    }""")
    sample.evaluate("""sample => {
      sample.showThread('pending').then(
        shown => (window.departedCall = shown), error => (window.departedCall = error.name));
    }""")
    child.wait_for_function("window.waitingCommand")
    assert take_browser_errors(page) == []
    # Exercise departure while the real feed has a native read outstanding.
    # WebKit stops the old document's loads when navigation starts, before
    # pagehide. Reads during that interval are logged as access-control refusals.
    held = []
    page.route(previous + "api/news", lambda route: held.append(route))
    holding(page, held, 1, "the departing document's freshness read")
    with page.expect_event(
        "requestfailed", predicate=lambda request: request == held[0].request
    ):
        if navigation == "form":
            child.get_by_role("button", name="Search docs").click()
        else:
            child.evaluate(
                "location.assign('https://docs.example.invalid/reference.html')"
            )
    # The native request has failed, but Playwright still owns its held route.
    # Resolve that route before the next interaction probe sends another request.
    held[0].abort()
    expect(child.get_by_role("heading")).to_have_text("External reference")
    departed_records = sample_records(page, serve)
    departed_record = next(
        row for row in departed_records if row["phase"] == "departed"
    )
    assert departed_record["document"] == next(
        row["document"] for row in departed_records if row["phase"] == "presented"
    )
    # The selection and `ready` wait for a next document, which only Reset brings here.
    assert page.evaluate("window.departedCall") is None
    assert (
        sample.evaluate(
            """sample => Promise.race([
              sample.ready.then(() => 'ready', error => error.name),
              new Promise(resolve => setTimeout(resolve, 50, 'waiting'))])"""
        )
        == "waiting"
    )
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    sample.get_by_role("button", name="Full view", exact=True).click()
    expect(child.get_by_role("heading")).to_have_text("External reference")
    sample.get_by_role("button", name="Return to page", exact=True).click()
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    assert page.evaluate("window.departedCall") is False
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice page"
    )
    replacement = sample.locator("iframe").element_handle().content_frame()
    reset_records = sample_records(page, serve)
    assert (
        next(row for row in reset_records if row["phase"] == "retired")["reason"]
        == "reset"
    )
    completed = [row for row in reset_records if row["phase"] == "presented"][-1]
    assert completed["allocation"] == 2
    assert completed["document"] != departed_record["document"]
    # Only account for teardown refusals from the proven departing capability.
    # The replacement and the fresh revoked-capability probe below stay strict.
    departed = urlsplit(previous)
    cancellation_error = re.compile(
        rf".*{re.escape(departed.netloc + departed.path)}\S*"
        r" due to access control checks\."
    )
    departure_errors = take_browser_errors(page)
    assert all(
        cancellation_error.fullmatch(error.splitlines()[0])
        for error in departure_errors
    ), departure_errors
    # A fresh header forces a new native preflight rather than reusing the old
    # document's cached one. Revocation must remain an HTTP refusal in both engines.
    assert (
        replacement.evaluate(
            """async previous => {
          const response = await fetch(new URL('api/state', previous), {
            headers: {'X-Leaf-Revocation-Probe': 'fresh'},
          });
          return response.status;
        }""",
            previous,
        )
        == 404
    )
    consume_browser_errors(page, "404 " + previous + "api/state")
