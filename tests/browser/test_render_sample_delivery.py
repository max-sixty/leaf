"""Opaque samples use ordinary native delivery and reconnect after a reload."""

from journeys.test_render_sample_delivery import sample_records
from render_harness import (
    consume_browser_errors,
    open_page,
    take_browser_errors,
)

from browser.test_render_controls import leaf_page


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
      window.selection = sample.showThread(undefined, {surface: 'panel'}).then(
        shown => ({shown}), error => ({error: error.name}));
    }""")
    child.wait_for_function("window.waitingCommand")
    with child.expect_navigation(wait_until="domcontentloaded"):
        child.evaluate("location.reload()")
    # Only the next document's own command can present the panel.
    assert page.evaluate("window.selection") == {"shown": True}
    sample.evaluate("async sample => await sample.ready")
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
