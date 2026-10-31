"""File editing stays quiet while saves, external changes and conflicts preserve work."""

import io

from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    leaf_page,
    one_frame,
    open_page,
    primed,
    rendered,
    rgb_pixels,
    scroll_settled,
)

from browser.test_render_gate import AIM_BOXES, aim_selectors
from leaf.file_bindings import bind_file


def test_file_editor_page_navigation_preserves_the_caret_position(
    browser, serve, tmp_path
):
    """PageDown aligns the next page at the caret's retained viewport offset."""
    file = tmp_path / "notes.md"
    file.write_text("\n".join(f"Line {number}" for number in range(1, 301)) + "\n")
    url = serve(
        leaf_page(
            "Notes",
            '<h1>Notes</h1><lf-file-editor id="notes-file" binding="notes"></lf-file-editor>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(browser, live_url(url))
    editor = page.locator("lf-file-editor").get_by_role(
        "textbox", name="File contents", exact=True
    )
    editor.click()
    page.keyboard.press("ControlOrMeta+Home")
    for _ in range(10):
        page.keyboard.press("ArrowDown")
    rendered(page)

    def reading():
        return editor.evaluate("""editor => {
          const root = editor.getRootNode();
          const port = root.querySelector('.cm-scroller');
          const caret = root.querySelector('.cm-cursor-primary, .cm-cursor');
          return {scroll: port.scrollTop,
            offset: caret.getBoundingClientRect().top - port.getBoundingClientRect().top};
        }""")

    initial = reading()
    previous = initial["scroll"]
    for _ in range(3):
        page.keyboard.press("PageDown")
        rendered(page)
        current = reading()
        assert abs(current["offset"] - initial["offset"]) <= 1
        assert current["scroll"] > previous
        previous = current["scroll"]

    for _ in range(3):
        page.keyboard.press("PageUp")
        rendered(page)
        current = reading()
        assert abs(current["offset"] - initial["offset"]) <= 1
        assert current["scroll"] < previous
        previous = current["scroll"]


def test_paper_keeps_the_files_words_and_drops_the_editors_controls(
    browser, serve, tmp_path
):
    """The editor's controls leave paper by the one print rule every offer meets, from
    inside its shadow tree; the file it shows is content, so its name and lines stay."""
    file = tmp_path / "notes.md"
    file.write_text("Words worth printing.\n")
    url = serve(
        leaf_page(
            "Printed files",
            '<h1>Printed files</h1><lf-file-editor id="notes-file" binding="notes">'
            '</lf-file-editor><lf-file-editor id="missing-file" binding="missing">'
            "</lf-file-editor>",
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(browser, live_url(url))
    bound = page.locator("#notes-file")
    retry = page.locator("#missing-file").get_by_role("button", name="Retry")
    expect(bound.locator(".cm-line", has_text="Words worth printing.")).to_be_visible()
    expect(retry).to_be_visible()
    page.emulate_media(media="print")
    expect(retry).to_be_hidden()
    expect(bound.get_by_text("notes.md", exact=True)).to_be_visible()
    expect(bound.locator(".cm-line", has_text="Words worth printing.")).to_be_visible()


def test_file_editor_uses_package_typography_and_the_inherited_focus_ring(
    browser, serve, tmp_path
):
    """Provider defaults yield to package CSS and root inputs in a real bound editor,
    which reads a `.markdown` file as Markdown, as `$languages.paths` says."""
    file = tmp_path / "style.markdown"
    file.write_text("# A real file\n\nEditable words and `literal` evidence.\n")
    url = serve(
        leaf_page(
            "Editor theme",
            '<h1>Editor theme</h1><button id="change-theme">Change theme</button><lf-file-editor id="styled-file" binding="style"></lf-file-editor>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "style", file)
    page = open_page(browser, live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")
    heading = editor.locator(".cm-line", has_text="A real file").locator("span").first
    expect(heading).to_have_css("font-weight", "650")
    size = editor.evaluate("node => getComputedStyle(node).fontSize")
    root_size = page.locator("html").evaluate(
        "node => parseFloat(getComputedStyle(node).fontSize)"
    )
    assert abs(float(size.removesuffix("px")) - root_size * 0.88) < 0.01

    page.evaluate("""() => document.querySelector('#change-theme').addEventListener('click', () => {
      const style = document.createElement('style');
      style.textContent = ':root { --focus-ring: 7px dashed magenta; --focus-ring-w: 7px; --syn-string: rgb(0, 85, 102); } lf-file-editor { --lf-file-editor-size: 30px; }';
      document.head.append(style);
    })""")
    page.get_by_role("button", name="Change theme", exact=True).click()
    expect(editor.get_by_text("literal", exact=True)).to_have_css(
        "color", "rgb(0, 85, 102)"
    )
    page.keyboard.press("Tab")
    editor.focus()
    assert editor.evaluate("node => node.matches(':focus-visible')")
    assert editor.evaluate("node => getComputedStyle(node).fontSize") == "30px"
    focus_paint = """node => {
      const style = getComputedStyle(node.closest('.cm-editor'), '::after');
      const content = getComputedStyle(node);
      const box = node.getBoundingClientRect();
      return {width: style.outlineWidth, style: style.outlineStyle,
        color: style.outlineColor, content: content.outlineStyle,
        visible: box.width > 0 && box.height > 0};
    }"""
    ring = editor.evaluate(focus_paint)
    assert ring == {
        "width": "7px",
        "style": "dashed",
        "color": "rgb(255, 0, 255)",
        "content": "none",
        "visible": True,
    }
    page.get_by_role("button", name="Change theme", exact=True).focus()
    editor.click()
    expect(editor).to_be_focused()
    assert editor.evaluate(focus_paint) == ring
    assert widget.evaluate("node => getComputedStyle(node).outlineStyle") == "none", (
        "retargeting editor focus to its shadow host drew a second ring"
    )
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
                for red, green, blue in rgb_pixels(pixels.crop(edge))
            )
            > 100
        )
    page.keyboard.insert_text("Theme override works. ")
    expect(editor).to_contain_text("Theme override works.")


def test_file_editor_keeps_the_user_typing_through_a_move(browser, serve, tmp_path):
    """A move of the editor while the user types, as a container re-placing its
    children with `setChildren` makes, leaves the buffer, the caret and the focus where
    they were, so the next key lands where the user left off. The editor moves past an
    empty sibling, so nothing on screen moves."""
    file = tmp_path / "notes.md"
    file.write_text("Original.\n")
    url = serve(
        leaf_page(
            "Notes",
            '<h1>Notes</h1><section id="editing"><lf-file-editor id="notes-file" '
            'binding="notes"></lf-file-editor></section>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(browser, live_url(url))
    editor = page.locator("lf-file-editor").get_by_role(
        "textbox", name="File contents", exact=True
    )
    expect(editor).to_have_attribute("aria-readonly", "false")
    editor.click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.type("Half")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    page.evaluate(
        """async () => {
          const { setChildren } = await import('/runtime/widget-api.js');
          const section = document.querySelector('#editing');
          const editor = section.querySelector('lf-file-editor');
          const empty = document.createElement('span');
          section.prepend(empty);
          setChildren(section, [editor, empty]);
        }"""
    )
    rendered(page)
    expect(editor).to_be_focused()
    page.keyboard.type("X")
    expect(editor).to_have_text("Original.HaXlf")


def test_file_editor_adopted_text_starts_undo_history_and_save_retries(
    browser, serve, tmp_path
):
    """Undo belongs to the adopted version; the save shortcut retries failed writes."""
    file = tmp_path / "notes.md"
    file.write_text("Baseline notes.\n")
    url = serve(
        leaf_page(
            "Notes", '<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>'
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(primed(browser, lambda page: page.clock.install()), live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")

    def receipt(text):
        return page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/files/notes")
                and response.status == 200
                and response.request.post_data_json["text"] == text
            )
        )

    def fail_write(route):
        route.abort() if route.request.method == "POST" else route.continue_()

    page.route("**/api/files/notes", fail_write)
    editor.click()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.insert_text("Draft.")
    page.clock.run_for(600)
    retry = widget.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    page.unroute("**/api/files/notes", fail_write)
    with receipt("Baseline notes.\nDraft."):
        page.keyboard.press("ControlOrMeta+s")
    expect(retry).to_be_hidden()

    # A clean refresh replaces earlier acknowledged editing history too.
    file.write_text("Latest file version.\n")
    page.clock.resume()
    expect(editor).to_contain_text("Latest file version.")
    page.keyboard.press("ControlOrMeta+z")
    rendered(page)
    expect(editor).to_have_text("Latest file version.")
    assert file.read_text() == "Latest file version.\n"

    # Editing after adoption still has its ordinary undo and redo.
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.insert_text("New draft.")
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_have_text("Latest file version.")
    with receipt("Latest file version.\nNew draft."):
        page.keyboard.press("ControlOrMeta+Shift+z")
        page.keyboard.press("ControlOrMeta+s")
    page.evaluate("lfWordsJudged()")
    consume_browser_errors(
        page,
        "Failed to load resource: net::ERR_FAILED",
        {"code": "words-left-screen", "words": "Baseline notes.Draft."},
    )


def test_file_editor_long_filename_keeps_the_phone_editable(browser, serve, tmp_path):
    """The full filename scrolls within its line, leaving the editor its room."""
    file = tmp_path / ("research-notes-" * 16 + ".md")
    file.write_text("Editable on a phone.\n")
    url = serve(
        leaf_page(
            "Notes", '<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>'
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)
    page = open_page(
        primed(
            browser, lambda page: page.set_viewport_size({"width": 320, "height": 740})
        ),
        live_url(url),
    )
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")
    name = widget.locator(".lf-file-editor-name")
    expect(name).to_have_text(file.name)
    expect(name).to_have_attribute("tabindex", "0")
    assert widget.locator(".lf-file-editor-edit").bounding_box()["height"] > 300
    assert widget.locator(".lf-file-editor-head").bounding_box()["width"] < 320
    editor.click()
    expect(editor).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(name).to_be_focused()


def test_file_editor_status_controls_take_a_finger_on_a_phone(browser, serve, tmp_path):
    """Retry and the conflict menu are words in a one-line header, so their press is the
    header's whole height, and the header has to be tall enough for a finger: at 390px
    under touch both stood 32px tall. Each is pressed in its own state."""
    file = tmp_path / "notes.md"
    file.write_text("Original.\n")
    url = serve(
        leaf_page(
            "Notes", '<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>'
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", file)

    # A finger from the start: the floor changes the header's height, and a page that
    # met the finger only when it was measured would shift as the finger arrived.
    def phone(page):
        page.clock.install()
        page.set_viewport_size({"width": 390, "height": 844})
        page.context.new_cdp_session(page).send(
            "Emulation.setTouchEmulationEnabled", {"enabled": True}
        )

    page = open_page(primed(browser, phone), live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")

    def short_aims(control):
        expect(widget.locator(control)).to_be_visible()
        return widget.evaluate_all(AIM_BOXES, aim_selectors())["short"]

    def fail_write(route):
        route.abort() if route.request.method == "POST" else route.continue_()

    page.route("**/api/files/notes", fail_write)
    editor.click()
    page.keyboard.insert_text("Draft.\n")
    page.clock.run_for(600)
    assert short_aims(".lf-file-editor-retry") == []
    page.unroute("**/api/files/notes", fail_write)
    file.write_text("Changed on disk.\n")
    widget.get_by_role("button", name="Retry", exact=True).click()
    page.clock.run_for(100)
    assert short_aims(".lf-file-editor-conflict") == []
    consume_browser_errors(
        page,
        "Failed to load resource: net::ERR_FAILED",
        "Failed to load resource: the server responded with a status of 409 (Conflict)",
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
    expect(child.locator(".cm-placeholder")).to_have_text(
        "No file is bound as 'notes'."
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


def test_an_exported_file_editor_stays_unavailable_without_starting_a_read(
    browser, serve
):
    """A captured page cannot read files; its editor shows that refusal without a busy transition."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Captured file",
                '<h1>File</h1><lf-file-editor id="file" binding="notes"></lf-file-editor>',
            ),
            packages=["file-editor"],
        ),
    )
    editor = page.locator("lf-file-editor")
    expect(editor.locator(".lf-file-editor-status")).to_contain_text("Unavailable")
    expect(
        editor.get_by_role("textbox", name="File contents", exact=True)
    ).to_have_attribute("aria-readonly", "true")
    expect(editor.get_by_role("button", name="Retry")).to_be_hidden()
