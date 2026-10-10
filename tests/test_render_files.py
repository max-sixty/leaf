"""File editing stays quiet while saves, external changes and conflicts preserve work."""

from leaf.file_bindings import bind_file
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import consume_browser_errors, leaf_page, open_page


def test_file_editor_saves_quietly_and_preserves_inflight_edits(
    browser, serve, tmp_path
):
    file = tmp_path / "notes.md"
    file.write_text("# Notes\n\nOriginal.\n")
    url = serve(
        leaf_page(
            "Notes",
            '<h1>Notes</h1><p>Changes save automatically.</p><lf-file id="notes-file" binding="notes"></lf-file>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(browser, live_url(url))
    widget = page.locator("lf-file")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    status = widget.locator(".lf-file-status")
    expect(editor).to_have_attribute("aria-readonly", "false")
    expect(widget.get_by_role("button")).to_have_count(0)

    def replace(text):
        editor.click()
        editor.press("ControlOrMeta+a")
        page.keyboard.insert_text(text)

    def receipt(text):
        return page.expect_response(
            lambda response: (
                response.url.endswith("/api/files/notes")
                and response.request.method == "POST"
                and response.status == 200
                and response.request.post_data_json["text"] == text
            )
        )

    # Observe the actual visible status through an ordinary fast save.
    status.evaluate(
        "node => { window.fileStatusWords = []; new MutationObserver(() => window.fileStatusWords.push(node.textContent)).observe(node, {childList:true, subtree:true, characterData:true}); }"
    )
    with receipt("# First edit\n"):
        replace("# First edit\n")
    assert file.read_text() == "# First edit\n"
    expect(status).to_have_text("")
    assert page.evaluate("window.fileStatusWords.every(text => text === '')")

    # Hold one real request; its old receipt must not erase later typing or clear
    # slow-save feedback while the following snapshot is still pending.
    page.clock.install()
    held = []

    def hold_writes(route):
        if route.request.method == "POST":
            held.append(route)
            page.evaluate("count => window.heldFileWrites = count", len(held))
        else:
            route.continue_()

    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(
        lambda request: (
            request.method == "POST" and request.url.endswith("/api/files/notes")
        )
    ):
        replace("# Pending\n")
        page.clock.run_for(600)
    page.wait_for_function("window.heldFileWrites === 1")
    expect(status).to_have_text("")
    page.clock.run_for(1100)
    expect(status).to_have_text("Saving changes…")
    page.keyboard.insert_text("More typing.\n")
    with page.expect_request(
        lambda request: (
            request.method == "POST"
            and request.post_data_json["text"] == "# Pending\nMore typing.\n"
        )
    ):
        held[0].continue_()
        page.clock.run_for(100)
    page.wait_for_function("window.heldFileWrites === 2")
    expect(editor).to_be_focused()
    expect(status).to_have_text("Saving changes…")
    with receipt("# Pending\nMore typing.\n"):
        held[1].continue_()
    expect(status).to_have_text("")
    assert file.read_text() == "# Pending\nMore typing.\n"
    page.unroute("**/api/files/notes", hold_writes)
    page.clock.resume()

    # A failed write keeps the buffer editable, and Retry saves the newest text.
    def fail_write(route):
        route.abort() if route.request.method == "POST" else route.continue_()

    page.route("**/api/files/notes", fail_write)
    replace("# Draft\n")
    page.clock.run_for(600)
    retry = widget.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    expect(editor).to_have_attribute("aria-readonly", "false")
    page.keyboard.insert_text("Retained.\n")
    page.unroute("**/api/files/notes", fail_write)
    with receipt("# Draft\nRetained.\n"):
        retry.click()
    expect(status).to_have_text("")
    expect(editor).to_be_focused()
    assert file.read_text() == "# Draft\nRetained.\n"
    consume_browser_errors(page, "Failed to load resource: net::ERR_FAILED")

    # An external clean update follows without replacing the editing owner.
    file.write_text("# External\n")
    page.clock.run_for(2100)
    expect(editor).to_contain_text("External")
    # These words were acknowledged on disk. This explicit external replacement
    # should update the clean editor; it is not an unsaved composition being lost.
    page.evaluate("lfWordsJudged()")
    consume_browser_errors(
        page, 'typed words left the screen without a key or press: "# DraftRetained."'
    )

    # Two versions remain available after a stale save. Explicit replacement
    # checks the displayed disk revision again instead of force-writing.
    held.clear()
    page.evaluate("window.heldFileWrites = 0")
    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(lambda request: request.method == "POST"):
        replace("# My version\n")
        page.clock.run_for(600)
    page.wait_for_function("window.heldFileWrites === 1")
    file.write_text("# Other version\n")
    held[0].continue_()
    page.clock.run_for(100)
    expect(
        widget.get_by_role("button", name="Use file version", exact=True)
    ).to_be_visible()
    comparison = widget.get_by_role("textbox", name="Compare versions", exact=True)
    expect(comparison).to_have_attribute("aria-readonly", "true")
    expect(widget.locator(".cm-deletedText")).to_contain_text("Other")
    expect(comparison).to_contain_text("version")
    expect(editor).to_have_text("# My version")
    assert file.read_text() == "# Other version\n"
    page.unroute("**/api/files/notes", hold_writes)
    with receipt("# My version\n"):
        widget.get_by_role("button", name="Save my version", exact=True).click()
    expect(widget.get_by_role("button")).to_have_count(0)
    expect(status).to_have_text("")
    expect(editor).to_be_focused()
    assert file.read_text() == "# My version\n"
    consume_browser_errors(
        page,
        "409 ",
    )
