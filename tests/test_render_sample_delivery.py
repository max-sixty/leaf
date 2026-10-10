"""Opaque samples use ordinary native delivery and reconnect after a reload."""

import re
from urllib.parse import urlsplit

import pytest
from leaf.render_checks import HANDOVER_DEADLINE_MS
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    open_page,
    take_browser_errors,
)
from test_render_controls import leaf_page


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
    page.unroute(navigation)
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice"
    )
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
      window.departedCall = sample.showThread('pending').then(
        () => 'completed', error => error.name);
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
    expect(child.get_by_role("heading")).to_have_text("External reference")
    assert page.evaluate("window.departedCall") == "AbortError"
    assert (
        sample.evaluate(
            "sample => sample.ready.then(() => 'ready', error => error.name)"
        )
        == "AbortError"
    )
    assert (
        sample.evaluate(
            "sample => sample.showThread('departed').then(() => 'completed', error => error.name)"
        )
        == "AbortError"
    )
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    sample.get_by_role("button", name="Full view", exact=True).click()
    expect(child.get_by_role("heading")).to_have_text("External reference")
    sample.get_by_role("button", name="Return to page", exact=True).click()
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice page"
    )
    replacement = sample.locator("iframe").element_handle().content_frame()
    # Only account for teardown refusals from the proven departing capability.
    # The replacement and the fresh revoked-capability probe below stay strict.
    departed = urlsplit(previous)
    cancellation_error = re.compile(
        rf".*{re.escape(departed.netloc + departed.path)}\S*"
        r" due to access control checks\."
    )
    departure_errors = take_browser_errors(page)
    assert all(cancellation_error.fullmatch(error) for error in departure_errors), (
        departure_errors
    )
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
