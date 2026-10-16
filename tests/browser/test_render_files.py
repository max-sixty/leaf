"""File editing stays quiet while saves, external changes and conflicts preserve work."""

import io

from leaf.file_bindings import bind_file
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    leaf_page,
    open_page,
    rendered,
)


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
    file.write_text("# A real file\n\nEditable words.\n")
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
      style.textContent = ':root { --focus-ring: 7px dashed magenta; --focus-ring-w: 7px; } lf-file-editor { --lf-file-editor-size: 30px; }';
      document.head.append(style);
    })""")
    page.get_by_role("button", name="Change theme", exact=True).click()
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
                for red, green, blue in pixels.crop(edge).get_flattened_data()
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
