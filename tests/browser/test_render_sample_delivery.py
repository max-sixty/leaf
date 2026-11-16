"""Opaque samples use ordinary native delivery and reconnect after a reload."""

import json

import pytest
from journeys.test_render_sample_delivery import sample_records
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    http_error_console,
    leaf_page,
    open_page,
    reported_browser_errors,
    take_browser_errors,
)


def test_a_reload_ends_a_sample_view_selection(browser, serve):
    """A selection the child's reload interrupts answers false, and the next document
    says it is ready, where the page reapplies its view."""
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
      const {registerSampleCommand} = await window.__lfCheckApi();
      registerSampleCommand('thread', () => {
        window.waitingCommand = true;
        return new Promise(() => {});
      });
    }""")
    # The examples' own call shape: a page that does not await its selection.
    sample.evaluate("""sample => {
      void sample.showThread('unawaited');
      window.selection = sample.showThread(undefined, {surface: 'panel'}).then(
        shown => ({shown}), error => ({error: error.name}));
    }""")
    child.wait_for_function("window.waitingCommand")
    sample.evaluate("""sample => {
      window.readyAgain = new Promise(resolve =>
        sample.addEventListener('lf-sample-ready', () => resolve(true), {once: true}));
    }""")
    with child.expect_navigation(wait_until="domcontentloaded"):
        child.evaluate("location.reload()")
    assert page.evaluate("window.selection") == {"shown": False}
    assert page.evaluate("window.readyAgain") is True
    assert take_browser_errors(page) == []


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


def test_a_page_cache_round_trip_keeps_the_sample_connected(browser, serve):
    """A persisted pagehide in the child is its containing page's, which the page cache
    brings back together with the child and their port: the host keeps the child's
    document and the child keeps watching where it stands. Playwright's browsers keep
    no page cache, so the child is handed the events a cached round trip delivers. The
    sample stands below the window but near it, so it starts unseen."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Cached sample",
                """
<h1>Containing page</h1>
<div style="height: 150vh"></div>
<lf-sample id="practice" label="Practice">
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
      const module = await window.__lfCheckApi();
      window.sampleIsVisible = () => module.frameVisibility().visible;
      for (const type of ['pagehide', 'pageshow'])
        window.dispatchEvent(new PageTransitionEvent(type, {persisted: true}));
    }""")
    # A departure would have left the host waiting for the child's next document.
    assert (
        sample.evaluate("""sample => Promise.race([
          sample.ready.then(() => 'presented'),
          new Promise(done => setTimeout(() => done('awaiting another document'), 2000)),
        ])""")
        == "presented"
    )
    sample.scroll_into_view_if_needed()
    child.wait_for_function("sampleIsVisible()")


def test_canceled_native_departure_keeps_fault_reporting(browser, serve):
    """Canceling beforeunload leaves genuine faults owned by the live document."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Canceled departure",
                '<h1>Still here</h1><button id="activate">Activate</button>'
                '<button id="fail">Report a fault</button>',
            )
        ),
    )
    page.locator("#activate").click()
    page.evaluate("""() => {
      window.addEventListener('beforeunload', event => { event.preventDefault(); event.returnValue = ''; });
      document.querySelector('#fail').onclick = () => { throw new Error('live fault after canceled departure'); };
    }""")
    page.once("dialog", lambda dialog: dialog.dismiss())
    with page.expect_event("dialog") as dialog:
        page.evaluate("location.reload()")
    assert dialog.value.type == "beforeunload"
    expect(page.get_by_role("heading", name="Still here")).to_be_visible()
    page.locator("#fail").click()
    reported_browser_errors(
        page,
        "live fault after canceled departure",
        "live fault after canceled departure",
    )


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
    body = records[-1]["error"]["body"]
    if response_type == "json":
        assert json.loads(body) == response["json"]
    else:
        assert body == response["body"]
    assert records[-1]["allocation"] == 1
    assert records[-1]["document"] == next(
        row["document"] for row in records if row["phase"] == "connected"
    )
    consume_browser_errors(page, http_error_console(503))
