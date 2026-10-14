"""File editing stays quiet while saves, external changes and conflicts preserve work."""

import os

from leaf.file_bindings import bind_file
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    leaf_page,
    one_frame,
    open_page,
    primed,
    rendered,
    scroll_settled,
)


def test_file_editor_saves_quietly_and_preserves_inflight_edits(
    browser, serve, tmp_path
):
    file = tmp_path / "notes.md"
    file.write_text("# Notes\n\nOriginal.\n")
    url = serve(
        leaf_page(
            "Notes",
            '<h1>Notes</h1><p>Changes save automatically.</p><lf-file-editor id="notes-file" binding="notes"></lf-file-editor>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(primed(browser, lambda page: page.clock.install()), live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    status = widget.locator(".lf-file-editor-status")
    conflict = widget.get_by_role("button", name="Changed on disk", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")
    expect(widget.get_by_role("button")).to_have_count(0)

    def choose(name, role="menuitem"):
        conflict.click()
        widget.get_by_role(role, name=name, exact=True).click()

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
              const root = document.querySelector('lf-file-editor').shadowRoot;
              const caret = root.querySelector('.lf-file-editor-edit .cm-cursor');
              if (!caret) return false;
              const cursor = caret.getBoundingClientRect();
              const port = root.querySelector('.lf-file-editor-edit .cm-scroller').getBoundingClientRect();
              return cursor.top >= port.top && cursor.bottom <= port.bottom;
            }"""
        )

    # The editor's room, measured from the widget's top: a failure and a conflict
    # each say so in the header's status, and neither moves the editor until the
    # reader opens the comparison.
    def editor_room():
        return widget.evaluate(
            """host => {
              const edit = host.shadowRoot.querySelector('.lf-file-editor-edit');
              const box = edit.getBoundingClientRect();
              return [box.top - host.getBoundingClientRect().top, box.height];
            }"""
        )

    resting_room = editor_room()

    # Observe the actual visible status through an ordinary fast save.
    status.evaluate(
        "node => { window.fileStatusWords = []; new MutationObserver(() => window.fileStatusWords.push(node.innerText)).observe(node, {childList:true, subtree:true, characterData:true, attributes:true}); }"
    )
    with receipt("# First edit\n"):
        replace("# First edit\n")
    assert file.read_text() == "# First edit\n"
    expect(status).to_have_text("", use_inner_text=True)
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
    expect(status).to_have_text("", use_inner_text=True)
    page.clock.run_for(1100)
    expect(status).to_have_text("Saving changes…", use_inner_text=True)
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
    expect(status).to_have_text("Saving changes…", use_inner_text=True)
    with receipt("# Pending\nMore typing.\n"):
        held[1].continue_()
    expect(status).to_have_text("", use_inner_text=True)
    assert file.read_text() == "# Pending\nMore typing.\n"
    page.unroute("**/api/files/notes", hold_writes)
    page.clock.resume()

    # An external clean update follows without replacing the editing owner. The
    # page's news names the write; nothing reads the file on a timer.
    file.write_text("# External\n")
    expect(editor).to_contain_text("External")
    # These words were acknowledged on disk. This explicit external replacement
    # should update the clean editor; it is not an unsaved composition being lost.
    page.evaluate("lfWordsJudged()")
    consume_browser_errors(
        page,
        {"code": "words-left-screen", "words": "# PendingMore typing."},
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
    expect(status).to_have_text("Not saved · Retry", use_inner_text=True)
    expect(status).to_have_attribute("title", "The page's server did not answer.")
    expect(retry).to_have_accessible_description("The page's server did not answer.")
    assert editor_room() == resting_room
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
    # A retry can become a conflict while the reader resumes typing. The status
    # says so in place, leaving the editor and its active caret where they were.
    editor.focus()
    file.write_text("# Changed during retry\n")
    held[0].continue_()
    page.clock.run_for(100)
    expect(conflict).to_be_visible()
    expect(status).to_have_text("Changed on disk", use_inner_text=True)
    assert editor_room() == resting_room
    expect(editor).to_be_focused()
    caret_visible()
    page.unroute("**/api/files/notes", hold_writes)

    # Keep the compared disk version stable until the reader chooses. A background
    # read must not occupy the save path and silently swallow that choice, even when
    # the page stamps the file anew.
    held_reads = []

    def hold_reads(route):
        if route.request.method == "POST":
            route.continue_()
        else:
            held_reads.append(route)

    page.route("**/api/files/notes", hold_reads)
    with page.expect_response(lambda response: response.url.endswith("/api/state")):
        os.utime(file)
    assert not held_reads
    with receipt(failed_draft):
        choose("Save draft")
    expect(status).to_have_text("", use_inner_text=True)
    expect(editor).to_be_focused()
    assert file.read_text() == failed_draft
    page.unroute("**/api/files/notes", hold_reads)
    # The save moved the stamp too; the read that follows it is answered now.
    for route in held_reads:
        route.continue_()
    consume_browser_errors(
        page,
        "Failed to load resource: net::ERR_FAILED",
        {"code": "failed-load", "status": 409},
    )

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
    expect(conflict).to_be_visible()
    expect(editor).to_be_focused()
    caret_visible()
    page.keyboard.insert_text("Still typing.\n")
    draft += "Still typing.\n"
    expect(editor).to_contain_text("Still typing.")
    assert file.read_text() == "# Other version\n"
    page.unroute("**/api/files/notes", hold_writes)

    # The conflict's choices are a menu the keyboard walks, and Escape puts it away
    # onto the control that opened it.
    conflict.focus()
    page.keyboard.press("Enter")
    menu = widget.get_by_role("menu", name="The file changed on disk")
    expect(menu).to_be_visible()
    expect(widget.get_by_role("menuitemcheckbox", name="Compare")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(widget.get_by_role("menuitem", name="Save draft")).to_be_focused()
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(conflict).to_be_focused()
    # Tab puts it away too, moving on from the control that opened it.
    page.keyboard.press("Enter")
    expect(widget.get_by_role("menuitemcheckbox", name="Compare")).to_be_focused()
    page.keyboard.press("Tab")
    expect(menu).to_be_hidden()
    expect(conflict).not_to_be_focused()
    assert widget.evaluate(
        "host => host.shadowRoot.activeElement?.closest('.lf-file-editor-edit') != null"
    )

    # Compare opens both versions below the editor, on the reader's press alone.
    comparison = widget.get_by_role("textbox", name="Compare versions", exact=True)
    expect(comparison).to_have_count(0)
    choose("Compare", "menuitemcheckbox")
    expect(comparison).to_have_attribute("aria-readonly", "true")
    expect(widget.locator(".cm-deletedText")).to_contain_text("Other")
    expect(comparison).to_contain_text("version")
    expect(conflict).to_be_focused()
    expect(widget.locator("[role=menuitemcheckbox]")).to_have_attribute(
        "aria-checked", "true"
    )
    # The two share the editing room, each scrolling inside its own half.
    halves = widget.evaluate(
        """host => ['.lf-file-editor-edit', '.lf-file-editor-comparison'].map(
             name => host.shadowRoot.querySelector(name).getBoundingClientRect().height)"""
    )
    assert min(halves) > 100, halves

    # A failed explicit replacement leaves recovery available. When its focused
    # Retry becomes another conflict, disappearing that button returns typing to
    # the retained editor rather than the document body.
    page.route("**/api/files/notes", fail_write)
    choose("Save draft")
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
        choose("Save draft")
    expect(widget.get_by_role("button")).to_have_count(0)
    expect(comparison).to_have_count(0)
    assert editor_room() == resting_room
    expect(status).to_have_text("", use_inner_text=True)
    expect(editor).to_be_focused()
    assert file.read_text() == draft

    # A file that moves again while the reader compares versions is read once they
    # take the file version, rather than leaving the editor on the compared one.
    held.clear()
    page.evaluate("window.heldFileWrites = 0")
    page.route("**/api/files/notes", hold_writes)
    with page.expect_request(file_write):
        replace("# Mine\n")
        page.clock.run_for(600)
    page.wait_for_function("window.heldFileWrites === 1")
    file.write_text("# Compared\n")
    held[0].continue_()
    page.clock.run_for(100)
    expect(conflict).to_be_visible()
    page.unroute("**/api/files/notes", hold_writes)
    with page.expect_response(lambda response: response.url.endswith("/api/state")):
        file.write_text("# Newest\n")
    choose("Use file version")
    expect(editor).to_contain_text("Newest")
    consume_browser_errors(
        page,
        {"code": "failed-load", "status": 409},
        "Failed to load resource: net::ERR_FAILED",
    )


def test_sample_file_editor_resize_keeps_classic_scrollbars_inside_its_document(
    scrollbar_browser, serve
):
    """A desktop horizontal scrollbar must not invoke a cross-frame mobile reveal."""
    page = open_page(
        scrollbar_browser,
        serve(
            leaf_page(
                "File editor containment",
                """
<h1>Containing page</h1><button id="owner">Containing owner</button>
<div style="height:1400px"></div>
<lf-sample id="practice" label="File practice" window>
  <template id="practice-source" data-sample>
    <style>
      html { overflow-x:scroll !important; }
      ::-webkit-scrollbar { width:16px; height:16px; background:#ddd; }
      ::-webkit-scrollbar-thumb { background:#888; }
    </style>
    <script type="module">
      let height = 220;
      document.addEventListener('keydown', event => {
        if (event.key !== 'F2') return;
        event.preventDefault();
        document.querySelector('#file').style.setProperty(
          '--lf-file-editor-height', `${height}px`);
        height -= 40;
      });
    </script>
    <h1>File practice</h1><div style="width:3000px;height:4px"></div>
    <lf-file-editor id="file" binding="notes"></lf-file-editor>
    <div style="height:3000px"></div>
  </template>
</lf-sample>
<div style="height:1400px"></div>
""",
            ),
            packages=["file-editor"],
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()
    editor = child.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "true")
    expect(child.locator(".lf-file-editor-status")).to_have_attribute(
        "title", "No file is bound as 'notes'."
    )
    editor.click()
    expect(editor).to_be_focused()
    assert child.evaluate("innerHeight - visualViewport.height") > 1

    # Scroll the active editor away, then resize it while its child document is
    # outside the parent's viewport. CodeMirror defers this layout until visible.
    child.evaluate("scrollTo(0, 2000)")
    page.evaluate("scrollTo(0, 0)")
    scroll_settled(page)
    page.keyboard.press("F2")
    top = frame.evaluate("frame => frame.getBoundingClientRect().top + scrollY")
    before = round(top - page.viewport_size["height"] + 100)
    page.evaluate("y => scrollTo(0, y)", before)
    scroll_settled(page)
    rendered(child)
    # Visibility delivers the deferred observer and its editor measurement.
    one_frame(child)
    rendered(child)
    assert page.evaluate("scrollY") == before

    page.keyboard.press("F2")
    rendered(child)
    one_frame(child)
    rendered(child)
    assert page.evaluate("scrollY") == before
    expect(editor).to_be_focused()
