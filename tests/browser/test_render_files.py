"""File editing stays quiet while saves, external changes and conflicts preserve work."""

import io
from datetime import UTC, datetime, timedelta

from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    http_error_console,
    leaf_page,
    one_frame,
    open_page,
    primed,
    rendered,
    rgb_pixels,
    scroll_settled,
    wait_until_ready,
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
    # A heading wears the token theme's colour for one, so the file reads as Markdown.
    heading = editor.locator(".cm-line", has_text="A real file").locator("span").first
    expect(heading).to_have_css(
        "color",
        page.evaluate("""() => {
          const probe = document.body.appendChild(document.createElement("span"));
          probe.style.color = "var(--lf-syn-name)";
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        }"""),
    )
    size = editor.evaluate("node => getComputedStyle(node).fontSize")
    root_size = page.locator("html").evaluate(
        "node => parseFloat(getComputedStyle(node).fontSize)"
    )
    assert abs(float(size.removesuffix("px")) - root_size * 0.84375) < 0.01

    page.evaluate("""() => document.querySelector('#change-theme').addEventListener('click', () => {
      const style = document.createElement('style');
      style.textContent = ':root { --lf-focus-ring: 7px dashed magenta; --lf-focus-ring-w: 7px; --lf-syn-string: rgb(0, 85, 102); } lf-file-editor { --lf-code-size: 30px; }';
      document.head.append(style);
    })""")
    page.get_by_role("button", name="Change theme", exact=True).click()
    expect(editor.get_by_text("`literal`", exact=True)).to_have_css(
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


def test_a_file_tree_opens_each_file_the_editor_holds(browser, serve, tmp_path):
    """A navigator naming the editor lists its files by their paths, a file two
    bindings name once, and opens the one picked; leaving a file saves it at once, an
    agent's write to other lines of it meanwhile joins that save, and returning finds
    the file as left."""
    for folder in ("deploy", "docs"):
        (tmp_path / folder).mkdir()
    values = tmp_path / "deploy" / "values.yaml"
    values.write_text("replicas: 3\n\nautoscaling:\n  minReplicas: 3\n")
    runbook = tmp_path / "docs" / "runbook.md"
    runbook.write_text("# Runbook\n")
    url = serve(
        leaf_page(
            "Deploy files",
            '<h1>Deploy files</h1><p><a id="to-line" href="#config:values:3">values</a></p>'
            '<lf-file-tree id="files" for="config"></lf-file-tree>'
            '<lf-file-editor id="config" binding="values runbook notes">'
            "</lf-file-editor>",
        ),
        packages=["file-editor", "file-tree"],
    )
    bind_file(serve.page_dir, "values", values)
    bind_file(serve.page_dir, "runbook", runbook)
    bind_file(serve.page_dir, "notes", runbook)
    page = open_page(browser, live_url(url))
    tree = page.locator("lf-file-tree")
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    name = widget.locator(".lf-file-editor-name")
    expect(editor).to_contain_text("replicas: 3")
    expect(name).to_have_text("deploy/values.yaml")
    expect(tree.get_by_role("treeitem", name="values.yaml")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(tree.get_by_role("treeitem", name="runbook.md")).to_have_count(1)

    held = []

    def hold(route):
        if route.request.method == "POST":
            held.append(route)
            page.evaluate("window.heldFileWrites = true")
        else:
            route.continue_()

    page.route("**/api/files/values", hold)
    editor.click()
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text("4")
    tree.get_by_role("treeitem", name="runbook.md").click()
    page.wait_for_function("window.heldFileWrites")
    values.write_text("replicas: 3\n\nautoscaling:\n  minReplicas: 4\n")
    page.unroute("**/api/files/values", hold)
    merged = "replicas: 4\n\nautoscaling:\n  minReplicas: 4\n"
    with page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and response.status == 200
            and response.request.post_data_json["text"] == merged
        )
    ):
        held[0].continue_()
    assert values.read_text() == merged
    expect(name).to_have_text("docs/runbook.md")
    expect(editor).to_contain_text("# Runbook")
    expect(tree.get_by_role("treeitem", name="runbook.md")).to_have_attribute(
        "aria-selected", "true"
    )
    assert page.evaluate("location.hash") == "#config:runbook"

    tree.get_by_role("treeitem", name="values.yaml").click()
    expect(name).to_have_text("deploy/values.yaml")
    expect(editor).to_have_text("replicas: 4autoscaling:  minReplicas: 4")

    # A link naming a line of a file opens it there, ready to type.
    tree.get_by_role("treeitem", name="runbook.md").click()
    expect(name).to_have_text("docs/runbook.md")
    page.locator("#to-line").click()
    expect(name).to_have_text("deploy/values.yaml")
    expect(editor).to_be_focused()
    expect(editor.locator(".cm-activeLine")).to_have_text("autoscaling:")

    # A letter on a row searches the tree, its typeahead, though d pages the document
    # anywhere else.
    tree.get_by_role("treeitem", name="runbook.md").focus()
    page.keyboard.press("d")
    expect(tree.locator("input")).to_have_value("d")
    consume_browser_errors(page, http_error_console(409))


def test_a_file_reads_in_the_colours_of_a_code_block_of_it(browser, serve, tmp_path):
    """The editor colours a file by the tokenizer and theme a code block of the same
    file is coloured by, so a YAML number, boolean, null, key, string and comment, and a
    Markdown heading, each wear in the editor what they wear in the block."""
    yaml = "# Worker\nreplicas: 3\nenabled: true\nceiling: null\nowner: 'oncall'\n"
    markdown = "# Runbook\n\nThe queue grows when **every** slot is busy.\n"
    (tmp_path / "values.yaml").write_text(yaml)
    (tmp_path / "runbook.md").write_text(markdown)
    url = serve(
        leaf_page(
            "Colours",
            '<h1>Colours</h1><p><a id="to-runbook" href="#config:runbook">runbook</a></p>'
            '<lf-file-editor id="config" binding="values runbook"></lf-file-editor>'
            f'<pre><code class="language-yaml">{yaml}</code></pre>'
            f'<pre><code class="language-markdown">{markdown}</code></pre>',
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "values", tmp_path / "values.yaml")
    bind_file(serve.page_dir, "runbook", tmp_path / "runbook.md")
    page = open_page(browser, live_url(url))
    editor = page.locator("lf-file-editor").get_by_role(
        "textbox", name="File contents", exact=True
    )
    # The face each word wears, in the editor and in the code block of its language.
    faces = """([words, lang]) => {
      const face = (root) => Object.fromEntries(words.map((word) => {
        const texts = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        for (let text = texts.nextNode(); text; text = texts.nextNode())
          if (text.data.trim() === word) {
            const style = getComputedStyle(text.parentElement);
            return [word, [style.color, style.fontStyle, style.fontWeight]];
          }
        return [word, null];
      }));
      return [
        face(document.querySelector("lf-file-editor").shadowRoot.querySelector(".cm-content")),
        face(document.querySelector(`pre code.language-${lang}`)),
      ];
    }"""
    for words, lang, shown in (
        (["# Worker", "replicas", "3", "true", "null", "'oncall'"], "yaml", "ceiling"),
        (["# Runbook"], "markdown", "Runbook"),
    ):
        if lang == "markdown":
            page.locator("#to-runbook").click()
        expect(editor).to_contain_text(shown)
        page.wait_for_function(
            """() => document.querySelector("lf-file-editor").shadowRoot
                .querySelector(".cm-content span[class]")"""
        )
        in_editor, in_block = page.evaluate(faces, [words, lang])
        assert all(in_block.values()), in_block
        assert in_editor == in_block, (in_editor, in_block)


def test_file_editor_takes_in_an_outside_write_to_other_lines(browser, serve, tmp_path):
    """An agent's write to one part of the file while the reader's edit to another is
    still unsaved joins the draft, and both reach the file, as a line merge would."""
    file = tmp_path / "values.yaml"
    file.write_text("replicas: 3\n\nautoscaling:\n  minReplicas: 3\n")
    url = serve(
        leaf_page(
            "Values",
            '<h1>Values</h1><lf-file-editor id="values-file" binding="values">'
            "</lf-file-editor>",
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "values", file)
    page = open_page(browser, live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    expect(editor).to_have_attribute("aria-readonly", "false")
    held = []

    def hold(route):
        if route.request.method == "POST":
            held.append(route)
            page.evaluate("window.heldFileWrites = true")
        else:
            route.continue_()

    page.route("**/api/files/values", hold)
    editor.click()
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text("4")
    page.wait_for_function("window.heldFileWrites")
    file.write_text("replicas: 3\n\nautoscaling:\n  minReplicas: 4\n")
    page.unroute("**/api/files/values", hold)
    merged = "replicas: 4\n\nautoscaling:\n  minReplicas: 4\n"
    with page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and response.status == 200
            and response.request.post_data_json["text"] == merged
        )
    ):
        held[0].continue_()
    assert file.read_text() == merged
    expect(widget.locator(".lf-file-editor-status")).to_have_text(
        "", use_inner_text=True
    )
    # The agent's line is marked as written elsewhere, and the reader's is not.
    written = editor.locator(".cm-line.lf-written")
    expect(written).to_have_text(["  minReplicas: 4"])
    # A later write with nothing unsaved moves the mark to the line it changed, and
    # the reader's edit there takes it off.
    file.write_text("replicas: 4\n\nautoscaling:\n  minReplicas: 2\n")
    expect(written).to_have_text(["  minReplicas: 2"])
    written.click()
    page.keyboard.press("End")
    page.keyboard.insert_text("0")
    expect(written).to_have_count(0)
    # The agent's line changed inside the region the reader was typing in; their own
    # words stayed where they typed them.
    page.evaluate("lfWordsJudged()")
    consume_browser_errors(
        page,
        http_error_console(409),
        {
            "code": "words-left-screen",
            "words": "replicas: 4autoscaling:  minReplicas: 3",
        },
    )


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
      // Capturing, since the key that lets go of the editor scrolled away stops there.
      document.addEventListener('keydown', event => {
        if (event.key !== 'F2') return;
        event.preventDefault();
        document.querySelector('#file').style.setProperty(
          '--lf-file-editor-height', `${height}px`);
        height -= 40;
      }, true);
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
    # The status says why it can't save when pointed at (preview.js). It is chrome,
    # not a control, so those words are the preview's only line.
    child.locator(".lf-file-editor-status").hover()
    expect(child.locator("#lf-preview")).to_have_text("No file is bound as 'notes'.")
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
    assert (
        child.evaluate(
            "document.querySelector('#file').style"
            ".getPropertyValue('--lf-file-editor-height')"
        )
        == "220px"
    )
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


def test_a_first_read_that_waits_a_second_says_the_file_is_loading(
    browser, serve, tmp_path
):
    """A file's first read can wait seconds, as a first visit's does on leaf.page while
    the visitor's container starts. Once it has waited a second, the empty editor says
    the file is loading, in the line it already shows; a read answered sooner, as a
    local page's is, shows no word."""
    files = {name: tmp_path / f"{name}.md" for name in ("notes", "plan", "todo")}
    for name, file in files.items():
        file.write_text(f"{name.title()}.\n")
    url = serve(
        leaf_page(
            "Notes",
            '<p><a href="#notes-file:plan">Plan</a> <a href="#notes-file:todo">To do</a></p>'
            '<lf-file-editor id="notes-file" binding="notes plan todo"></lf-file-editor>',
        ),
        packages=["file-editor"],
    )
    for name, file in files.items():
        bind_file(serve.page_dir, name, file)
    page = open_page(browser, live_url(url))
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    placeholder = widget.locator(".cm-placeholder")
    expect(editor).to_have_text("Notes.")

    def editor_room():
        return widget.evaluate(
            """host => {
              const edit = host.shadowRoot.querySelector('.lf-file-editor-edit');
              const box = edit.getBoundingClientRect();
              return [box.top - host.getBoundingClientRect().top, box.height];
            }"""
        )

    room = editor_room()
    widget.evaluate(
        """host => {
          window.placeholdersShown = [];
          new MutationObserver(() => {
            const shown = host.shadowRoot.querySelector('.cm-placeholder');
            if (shown) window.placeholdersShown.push(shown.textContent);
          }).observe(host.shadowRoot, {childList: true, subtree: true});
        }"""
    )
    # The page starts on the browser's own time. From here on only the test moves it, so
    # a read the server answers slowly still answers within the page's first second.
    page.clock.install()
    page.clock.pause_at(datetime.now(UTC) + timedelta(seconds=1))
    page.get_by_role("link", name="Plan").click()
    page.clock.run_for(100)
    expect(editor).to_have_text("Plan.")
    assert page.evaluate("window.placeholdersShown") == []

    held = []
    page.route("**/api/files/todo", lambda route: held.append(route))
    page.get_by_role("link", name="To do").click()
    page.clock.run_for(900)
    expect(placeholder).to_have_count(0)
    page.clock.run_for(200)
    expect(placeholder).to_have_text("Loading file…")
    assert editor_room() == room
    held[0].continue_()
    expect(editor).to_have_text("Todo.")
    expect(placeholder).to_have_count(0)
    assert editor_room() == room


def test_a_page_presents_without_a_file_whose_first_read_has_waited_a_second(
    browser, serve, tmp_path
):
    """The page waits for the file it opens with, but not past a second: on leaf.page a
    first visit's read waits for the visitor's container to start. The page then
    presents with the editor saying the file is loading, and the text lands when the
    read answers."""
    notes = tmp_path / "notes.md"
    notes.write_text("Notes.\n")
    url = serve(
        leaf_page(
            "Notes", '<lf-file-editor id="notes-file" binding="notes"></lf-file-editor>'
        ),
        packages=["file-editor"],
    )
    bind_file(serve.page_dir, "notes", notes)
    held = []

    def hold_read(page):
        page.route("**/api/files/notes", lambda route: held.append(route))

    page = open_page(primed(browser, hold_read), live_url(url), upgraded=False)
    widget = page.locator("lf-file-editor")
    editor = widget.get_by_role("textbox", name="File contents", exact=True)
    placeholder = widget.locator(".cm-placeholder")
    expect(page.locator("body[data-lf-presented]")).to_have_count(1)
    expect(placeholder).to_have_text("Loading file…")
    expect(editor).to_have_attribute("aria-readonly", "true")
    held[0].continue_()
    expect(editor).to_have_text("Notes.")
    expect(placeholder).to_have_count(0)
    wait_until_ready(page)
