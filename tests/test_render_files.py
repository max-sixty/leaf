"""File editing stays quiet while saves, external changes and conflicts preserve work."""

import io

from leaf.file_bindings import bind_file
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import consume_browser_errors, leaf_page, open_page, primed


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
    page = open_page(primed(browser, lambda page: page.clock.install()), live_url(url))
    widget = page.locator("lf-file")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    status = widget.locator(".lf-file-status")
    expect(editor).to_have_attribute("aria-readonly", "false")
    expect(widget.get_by_role("button")).to_have_count(0)

    def replace(text):
        editor.click()
        editor.press("ControlOrMeta+a")
        page.keyboard.insert_text(text)

    def file_write(request):
        return request.method == "POST" and request.url.endswith("/api/files/notes")

    def receipt(text):
        return page.expect_response(
            lambda response: (
                file_write(response.request)
                and response.status == 200
                and response.request.post_data_json["text"] == text
            )
        )

    def caret_visible():
        page.wait_for_function(
            """() => {
              const root = document.querySelector('lf-file').shadowRoot;
              const caret = root.querySelector('.lf-file-edit .cm-cursor');
              if (!caret) return false;
              const cursor = caret.getBoundingClientRect();
              const port = root.querySelector('.lf-file-edit .cm-scroller').getBoundingClientRect();
              return cursor.top >= port.top && cursor.bottom <= port.bottom;
            }"""
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
    held = []

    def hold_writes(route):
        if route.request.method == "POST":
            held.append(route)
            page.evaluate("count => window.heldFileWrites = count", len(held))
        else:
            route.continue_()

    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(file_write):
        replace("# Pending\n")
        page.clock.run_for(600)
    page.wait_for_function("window.heldFileWrites === 1")
    expect(status).to_have_text("")
    page.clock.run_for(1100)
    expect(status).to_have_text("Saving changes…")
    page.keyboard.insert_text("More typing.\n")
    with page.expect_request(
        lambda request: (
            file_write(request)
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

    # An external clean update follows without replacing the editing owner.
    file.write_text("# External\n")
    page.clock.run_for(2100)
    expect(editor).to_contain_text("External")
    # These words were acknowledged on disk. This explicit external replacement
    # should update the clean editor; it is not an unsaved composition being lost.
    page.evaluate("lfWordsJudged()")
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "# PendingMore typing."',
    )

    # A failed write keeps the buffer editable, and Retry saves the newest text.
    def fail_write(route):
        route.abort() if route.request.method == "POST" else route.continue_()

    page.route("**/api/files/notes", fail_write)
    failed_draft = "\n" * 40 + "# Draft\n"
    replace(failed_draft)
    page.clock.run_for(600)
    retry = widget.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    expect(editor).to_have_attribute("aria-readonly", "false")
    caret_visible()
    page.keyboard.insert_text("Retained.\n")
    failed_draft += "Retained.\n"
    page.unroute("**/api/files/notes", fail_write)
    held.clear()
    page.evaluate("window.heldFileWrites = 0")
    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(file_write):
        retry.click()
    page.wait_for_function("window.heldFileWrites === 1")
    # A retry can become a conflict while the reader resumes typing. The existing
    # error pane grows into a comparison without clipping the active caret.
    editor.focus()
    file.write_text("# Changed during retry\n")
    held[0].continue_()
    page.clock.run_for(100)
    expect(
        widget.get_by_role("button", name="Use file version", exact=True)
    ).to_be_visible()
    expect(editor).to_be_focused()
    caret_visible()
    page.unroute("**/api/files/notes", hold_writes)

    # Keep the compared disk version stable until the reader chooses. A background
    # read must not occupy the save path and silently swallow that choice.
    def hold_reads(route):
        if route.request.method == "POST":
            route.continue_()

    page.route("**/api/files/notes", hold_reads)
    page.clock.run_for(2100)
    with receipt(failed_draft):
        widget.get_by_role("button", name="Save my version", exact=True).click()
    expect(status).to_have_text("")
    expect(editor).to_be_focused()
    assert file.read_text() == failed_draft
    page.unroute("**/api/files/notes", hold_reads)
    consume_browser_errors(page, "Failed to load resource: net::ERR_FAILED", "409 ")

    # Two versions remain available after a stale save. Explicit replacement
    # checks the displayed disk revision again instead of force-writing.
    held.clear()
    draft = "# My version\n" + "".join(f"Draft line {i}.\n" for i in range(40))
    page.evaluate("window.heldFileWrites = 0")
    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(file_write):
        replace(draft)
        page.clock.run_for(600)
    page.wait_for_function("window.heldFileWrites === 1")
    caret_visible()
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
    expect(editor).to_be_focused()
    caret_visible()
    page.keyboard.insert_text("Still typing.\n")
    draft += "Still typing.\n"
    expect(editor).to_contain_text("Still typing.")
    assert file.read_text() == "# Other version\n"
    page.unroute("**/api/files/notes", hold_writes)

    # A failed explicit replacement leaves recovery available. When its focused
    # Retry becomes another conflict, disappearing that button returns typing to
    # the retained editor rather than the document body.
    page.route("**/api/files/notes", fail_write)
    widget.get_by_role("button", name="Save my version", exact=True).click()
    expect(retry).to_be_visible()
    page.unroute("**/api/files/notes", fail_write)
    held.clear()
    page.evaluate("window.heldFileWrites = 0")
    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(file_write):
        retry.click()
    page.wait_for_function("window.heldFileWrites === 1")
    expect(retry).to_be_focused()
    file.write_text("# Changed again\n")
    held[0].continue_()
    page.clock.run_for(100)
    expect(retry).to_be_hidden()
    expect(editor).to_be_focused()
    caret_visible()
    page.keyboard.insert_text("Recovered.\n")
    draft += "Recovered.\n"
    page.unroute("**/api/files/notes", hold_writes)
    with receipt(draft):
        widget.get_by_role("button", name="Save my version", exact=True).click()
    expect(widget.get_by_role("button")).to_have_count(0)
    expect(status).to_have_text("")
    expect(editor).to_be_focused()
    assert file.read_text() == draft
    consume_browser_errors(
        page,
        "409 ",
        "Failed to load resource: net::ERR_FAILED",
    )


def test_file_editor_uses_package_typography_and_the_inherited_focus_ring(
    browser, serve, tmp_path
):
    """Provider defaults yield to package CSS and root inputs in a real bound editor."""
    file = tmp_path / "style.md"
    file.write_text("# A real file\n\nEditable words.\n")
    url = serve(
        leaf_page(
            "Editor theme",
            '<h1>Editor theme</h1><button id="change-theme">Change theme</button><lf-file id="styled-file" binding="style"></lf-file>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "style", file)
    page = open_page(browser, live_url(url))
    widget = page.locator("lf-file")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")
    size = editor.evaluate("node => getComputedStyle(node).fontSize")
    root_size = page.locator("html").evaluate(
        "node => parseFloat(getComputedStyle(node).fontSize)"
    )
    assert abs(float(size.removesuffix("px")) - root_size * 0.88) < 0.01

    page.evaluate("""() => document.querySelector('#change-theme').addEventListener('click', () => {
      const style = document.createElement('style');
      style.textContent = ':root { --focus-ring: 7px dashed magenta; --focus-ring-w: 7px; } lf-file { --lf-file-size: 30px; }';
      document.head.append(style);
    })""")
    page.get_by_role("button", name="Change theme", exact=True).click()
    page.keyboard.press("Tab")
    editor.focus()
    assert editor.evaluate("node => node.matches(':focus-visible')")
    assert editor.evaluate("node => getComputedStyle(node).fontSize") == "30px"
    ring = editor.evaluate("""node => {
      const style = getComputedStyle(node.closest('.cm-editor'), '::after');
      const content = getComputedStyle(node);
      const box = node.getBoundingClientRect();
      return {width: style.outlineWidth, style: style.outlineStyle,
        color: style.outlineColor, content: content.outlineStyle,
        visible: box.width > 0 && box.height > 0};
    }""")
    assert ring == {
        "width": "7px",
        "style": "dashed",
        "color": "rgb(255, 0, 255)",
        "content": "none",
        "visible": True,
    }
    # Computed outlines can be completely clipped by CodeMirror's scrollport.
    # Count the custom cue's actual painted pixels inside the editor frame.
    frame = widget.locator(".cm-editor")
    pixels = Image.open(io.BytesIO(frame.screenshot())).convert("RGB")
    width, height = pixels.size
    edges = (
        (0, 0, 7, height),
        (width - 7, 0, width, height),
        (0, 0, width, 7),
        (0, height - 7, width, height),
    )
    for edge in edges:
        assert (
            sum(
                red > 245 and green < 10 and blue > 245
                for red, green, blue in pixels.crop(edge).get_flattened_data()
            )
            > 100
        )
    page.keyboard.insert_text("Theme override works. ")
    expect(editor).to_contain_text("Theme override works.")
