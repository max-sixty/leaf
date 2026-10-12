"""Diff controls share canonical fields and preserve the compact source reader."""

from html import escape

import pytest
from leaf import data as data_model
from leaf.render_checks import one_frame, rendered
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    reported_browser_errors,
    write,
)


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "dark")])
def test_diff_filter_has_one_frame_and_clears_with_its_count_inside(
    browser, serve, width, scheme
):
    """The canonical search owns the frame, count, and Clear; filtering owns the rows."""
    patch = "".join(
        f"diff --git a/src/file-{index}.py b/src/file-{index}.py\n"
        f"--- a/src/file-{index}.py\n+++ b/src/file-{index}.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for index in range(12)
    )
    context = browser.new_context(
        viewport={"width": width, "height": 844}, color_scheme=scheme
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Changed files",
                f'<h1>Changed files</h1><lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>',
            )
        ),
        context=context,
    )
    diff = page.locator("#patch")
    field = diff.locator(".lf-diff-search")
    editor = field.locator("input")
    count = diff.locator(".lf-diff-progress")
    rows = diff.locator(".lf-diff-file:not(.lf-diff-filtered)")
    expect(editor).to_have_accessible_name("Filter diff files")
    page.get_by_role("heading", name="Changed files").click()
    for _ in range(8):
        page.keyboard.press("Tab")
        if editor.evaluate("node => node === node.getRootNode().activeElement"):
            break
    expect(editor).to_be_focused()
    assert editor.evaluate("node => node.matches(':focus-visible')")
    field.scroll_into_view_if_needed()
    rendered(page)
    frame = field.bounding_box()
    assert diff.locator(".lf-diff-tools").bounding_box() == frame
    count_box = count.bounding_box()
    assert (
        frame["x"]
        <= count_box["x"]
        < count_box["x"] + count_box["width"]
        <= frame["x"] + frame["width"]
    )
    for query, matches in (("file-0", 1), ("no-match", 0)):
        editor.fill(query)
        expect(rows).to_have_count(matches)
        expect(count).to_have_text(f"{matches} of 12")
        expect(field.get_by_role("button", name="Clear")).to_be_visible()
        assert field.bounding_box() == frame
    field.get_by_role("button", name="Clear").click()
    expect(editor).to_have_value("")
    expect(editor).to_be_focused()
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")
    assert field.bounding_box() == frame
    editor.fill("file-0")
    expect(rows).to_have_count(1)
    editor.press("ControlOrMeta+A")
    editor.press("Backspace")
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")


@pytest.mark.parametrize("touch", [False, True])
def test_diff_thread_controls_leave_line_numbers_readable(browser, serve, touch):
    """A hover mark fits the native margin without changing its reading geometry.

    Measuring the number's ink catches an overlay even when the gutter's own box
    contains both the number and the button. Hover must preserve that separation.
    """
    patch = """diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -998,3 +998,3 @@
 before = True
-enabled = False
+enabled = True
 after = True
"""
    patch = patch.replace(
        " after = True", " after = True  # " + "long-source-value" * 20
    )
    url = serve(
        leaf_page(
            "Config change",
            '<h1>Config change</h1><lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>'
            f'<lf-diff id="native"><pre>{escape(patch)}</pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 390 if touch else 1280, "height": 844},
        has_touch=touch,
        is_mobile=touch,
    )
    page = open_page(browser, url, context=context)
    diff = page.locator("#patch")
    buttons = diff.locator(".lf-diff-line-comment")
    expect(buttons).to_have_count(4)
    expect(diff.locator(".lf-diff-wrap, .lf-diff-review, .lf-diff-next")).to_have_count(
        0
    )

    def geometry():
        return buttons.evaluate_all("""buttons => buttons.map(button => {
          const number = button.parentElement.querySelector('[data-line-number-content]');
          const ink = new Range(); ink.selectNodeContents(number);
          const bounds = button.querySelector('.lf-diff-line-plus').getBoundingClientRect();
          return {right: bounds.right, number: ink.getBoundingClientRect().left,
                  height: button.parentElement.getBoundingClientRect().height,
                  hitHeight: button.getBoundingClientRect().height,
                  background: getComputedStyle(button).backgroundColor,
                  opacity: getComputedStyle(button).opacity};
        })""")

    before = geometry()
    for reading in before:
        assert reading["right"] <= reading["number"], reading
        assert reading["hitHeight"] == reading["height"], reading
        assert reading["opacity"] == "0", reading
    native = page.locator("#native [data-gutter] > [data-line-index]").first
    assert before[0]["height"] == native.bounding_box()["height"]
    assert (
        diff.locator("[data-gutter]").bounding_box()["width"]
        == page.locator("#native [data-gutter]").bounding_box()["width"]
    )
    diff.locator("[data-content] > [data-line]").first.hover()
    after = geometry()
    assert after[0]["opacity"] == "1"
    assert after[0]["background"] == "rgba(0, 0, 0, 0)"
    assert [{k: v for k, v in r.items() if k != "opacity"} for r in after] == [
        {k: v for k, v in r.items() if k != "opacity"} for r in before
    ]
    # Moving to the next line retires the previous gutter highlight.
    diff.locator("[data-content] > [data-line]").nth(1).hover()
    assert geometry()[0]["opacity"] == "0"
    assert geometry()[1]["opacity"] == "1"
    buttons.first.hover()
    assert geometry()[0] == after[0]
    assert buttons.first.get_attribute("title") is None
    expect(buttons.first.locator('[data-lf-icon="comment"]')).to_have_count(0)
    expect(
        diff.locator('.lf-diff-file-comment [data-lf-icon="comment"]')
    ).to_have_count(1)

    buttons.nth(2).click()
    editor = diff.locator(".lf-fab-input")
    expect(editor).to_be_visible()
    expect(editor).to_be_focused()
    reader = diff.locator("code[data-code]")

    def conversation_fits():
        viewport = reader.bounding_box()
        box = diff.locator(".lf-diff-thread-outlet").bounding_box()
        assert viewport["x"] <= box["x"], (viewport, box)
        assert box["x"] + box["width"] <= viewport["x"] + viewport["width"] + 1, (
            viewport,
            box,
        )

    conversation_fits()
    write(editor, "Does this affect existing settings?")
    editor.press("Control+Enter" if touch else "Enter")
    expect(diff.locator(".lf-page-thread")).to_contain_text(
        "Does this affect existing settings?"
    )
    reader.evaluate("node => node.scrollLeft = 200")
    conversation_fits()


@pytest.mark.parametrize("touch,scheme", [(False, "light"), (True, "dark")])
def test_response_and_message_reading_keep_their_face_across_shadow_seating(
    browser, serve, touch, scheme
):
    """Moving the response into a source widget changes placement, not its face.

    Sending the same Markdown on both sides additionally exercises the complete
    reading vocabulary installed in declared trees, including a table that must
    scroll within its message instead of widening the page.
    """
    patch = "diff --git a/config.py b/config.py\n--- a/config.py\n+++ b/config.py\n@@ -1 +1 @@\n-old\n+new\n"
    url = serve(
        leaf_page(
            "Review source and prose",
            '<h1>Review source and prose</h1><p id="subject">Discuss this paragraph.</p>'
            '<lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
            head="""<style id="response-inset-override">
              :is(.lf-fab-bar, .lf-margin-preview) {
                --lf-thread-text-pad-block: 12px !important;
                --lf-comment-text-pad-end: 19px !important;
                --lf-comment-send-room: 41px !important;
              }
            </style>""",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 390 if touch else 1280, "height": 900},
        has_touch=touch,
        is_mobile=touch,
        color_scheme=scheme,
    )
    page = open_page(browser, url, context=context)
    markdown = (
        "| First | Second | Third | Fourth | Fifth | Sixth |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 123456789012345678901234 | 234567890123456789012345 | 345678901234567890123456 "
        "| 456789012345678901234567 | 567890123456789012345678 | 678901234567890123456789 |\n\n"
        "- Keep the first item.\n- Keep the second item.\n\n---\n\nKeep the conclusion."
    )

    def face(field):
        return field.evaluate("""node => {
          const style = getComputedStyle(node);
          const properties = ['font-family', 'font-size', 'line-height', 'color',
            'min-height', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
            'border-top-width', 'border-top-color', 'border-radius', 'box-shadow'];
          return Object.fromEntries(properties.map(name => [name, style.getPropertyValue(name)]));
        }""")

    def reading(message):
        expect(message.locator("table")).to_be_visible()
        expect(message.locator("ul")).to_be_visible()
        expect(message.locator("hr")).to_be_visible()
        return message.evaluate("""message => {
          const properties = {
            table: ['display', 'overflow-x', 'border-collapse', 'font-family', 'font-size'],
            td: ['padding-top', 'padding-left', 'border-bottom-width', 'border-bottom-color'],
            ul: ['padding-left'], hr: ['border-top-width', 'border-top-style', 'border-top-color']
          };
          const table = message.querySelector('table');
          const body = message.getBoundingClientRect();
          const box = table.getBoundingClientRect();
          if (box.width > body.width + 1 || table.scrollWidth <= table.clientWidth)
            throw new Error('Wide table must scroll inside its message');
          return Object.fromEntries(Object.entries(properties).map(([selector, names]) => {
            const style = getComputedStyle(message.querySelector(selector));
            return [selector, Object.fromEntries(names.map(name => [name, style.getPropertyValue(name)]))];
          }));
        }""")

    page.locator("#subject").click(modifiers=["Alt"])
    floating = page.locator(".lf-fab-input:visible").first
    expect(floating).to_be_focused()
    physical_face = face(floating)
    assert float(physical_face["padding-top"].removesuffix("px")) + 1 == 12
    assert float(physical_face["padding-right"].removesuffix("px")) + 1 == 19
    assert (
        floating.evaluate(
            "node => getComputedStyle(node).getPropertyValue('--lf-field-end-room').trim()"
        )
        == "41px"
    )
    page.emulate_media(forced_colors="active")
    forced = floating.evaluate(
        "node => [getComputedStyle(node).outlineWidth, "
        "getComputedStyle(node).outlineStyle, getComputedStyle(node).outlineColor]"
    )
    assert forced[1] != "none"
    page.emulate_media(forced_colors="none")
    write(floating, markdown)
    floating.press("Control+Enter" if touch else "Enter")
    physical_reading = reading(page.locator(".lf-margin-preview .lf-msg-body").first)
    sent_insets = page.locator(".lf-margin-preview .lf-msg-text").first.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return {block: style.paddingTop, end: style.paddingInlineEnd,
            last: getComputedStyle(node.lastElementChild, '::after').width};
        }"""
    )
    assert sent_insets["block"] == "12px"
    assert sent_insets["end"] == ("60px" if touch else "19px")
    if not touch:
        assert sent_insets["last"] == "41px"
    page.keyboard.press("Escape")
    diff = page.locator("#patch")
    # An author can dress a declared tree too. Install the same inputs before
    # opening its field, so the test does not reflow a focused editor itself.
    diff.evaluate("""node => {
      node.shadowRoot.append(document.querySelector('#response-inset-override').cloneNode(true));
    }""")
    diff.locator(".lf-diff-line-comment").last.click()
    inline = diff.locator(".lf-fab-input")
    expect(inline).to_be_focused()
    assert inline.evaluate("node => node.getRootNode() instanceof ShadowRoot")
    assert face(inline) == physical_face
    page.emulate_media(forced_colors="active")
    assert (
        inline.evaluate(
            "node => [getComputedStyle(node).outlineWidth, "
            "getComputedStyle(node).outlineStyle, getComputedStyle(node).outlineColor]"
        )
        == forced
    )
    page.emulate_media(forced_colors="none")
    write(inline, markdown)
    inline.press("Control+Enter" if touch else "Enter")
    assert reading(diff.locator(".lf-msg-body").first) == physical_reading


@pytest.mark.parametrize("bound", [False, True], ids=["inline", "bound"])
def test_a_patch_that_failed_stays_failed_when_its_diff_returns(browser, serve, bound):
    """A refusal stands while its patch is unchanged: a diff that leaves the page and
    returns, as document reconciliation moves it, renders its patch again only when
    the departure cut that rendering short, and does not tell the author twice. A bound
    patch returns through its data subscription, an inline one through the widget."""
    one = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-x\n+y\n"
    diff = (
        '<lf-diff id="d-bad" source="bad-patch"><pre></pre></lf-diff>'
        if bound
        else f'<lf-diff id="d-bad"><pre>\n{one}{one}</pre></lf-diff>'
    )
    url = serve(leaf_page("bad diff", f'<h1 id="t">Bad</h1>\n{diff}'))
    if bound:
        data_model.cmd_data_set(serve.page_dir, "bad-patch", one + one)
    page = open_page(browser, url)
    expect(page.locator("#d-bad .lf-error")).to_contain_text("repeats file path")
    returned = page.evaluate("""async () => {
        const diff = document.getElementById('d-bad');
        const failure = diff.querySelector('.lf-error');
        const parent = diff.parentNode;
        const next = diff.nextSibling;
        diff.remove();
        await new Promise((resolve) => setTimeout(resolve));
        parent.insertBefore(diff, next);
        for (let i = 0; i < 3; i++) await new Promise(requestAnimationFrame);
        return diff.querySelector('.lf-error') === failure;
    }""")
    assert returned, "the returning diff rendered its refused patch again"
    errors = consume_browser_errors(page, '<lf-diff id="d-bad"> failed: ')
    assert len(errors) == 1, errors


def test_an_expanded_diff_file_can_retry_its_failed_chunk_in_place(browser, serve):
    """A recovered network has a visible route to retry the expanded file."""
    url = serve(
        leaf_page(
            "Retry a file diff",
            '<h1>Retry a file diff</h1><lf-diff id="patch" source="review-patch" '
            'collapsed><pre></pre></lf-diff><button id="after" '
            'style="position:fixed;right:1rem;bottom:1rem">After diff</button>',
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest("""diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1 +1 @@
-enabled = False
+enabled = True
"""),
    )
    page = open_page(browser, url)
    attempts = []
    pending = []

    def fail_until_success(route):
        attempts.append(route.request.url)
        if len(attempts) == 1:
            route.abort("failed")
        elif len(attempts) < 4:
            pending.append(route)
        else:
            route.continue_()

    page.route("**/api/deferred*", fail_until_success)
    summary = page.locator("lf-diff summary")
    with page.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        summary.click()
    assert failed.value.failure == "net::ERR_FAILED"
    expect(page.locator("lf-diff .lf-error")).to_contain_text(
        "That file's diff failed to load: Failed to fetch"
    )
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    assert len(attempts) == 1

    retry = page.get_by_role("button", name="Retry")
    assert retry.count() == 1, "the expanded file needs an in-place retry control"

    # A native Enter retry stays focused while in flight. Another Enter is ignored
    # until it resolves, so it cannot start a parallel deferred request.
    page.keyboard.press("Tab")
    expect(retry).to_be_focused()
    page.keyboard.press("Enter")
    holding(page, pending, 1, "the first deferred retry")
    assert len(attempts) == 2 and len(pending) == 1
    expect(retry).to_have_attribute("aria-disabled", "true")
    expect(retry).to_be_focused()
    page.keyboard.press("Enter")
    assert len(attempts) == 2 and len(pending) == 1
    with page.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        pending.pop().abort("failed")
    assert failed.value.failure == "net::ERR_FAILED"
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    retry = page.get_by_role("button", name="Retry")
    # Network failure precedes the new error paint. The old pending button can
    # still hold focus, so wait for the replacement to accept another activation.
    expect(retry).not_to_have_attribute("aria-disabled", "true")
    expect(retry).to_be_focused()

    # If the user tabs away during another pending retry, its failure must leave
    # focus at the newer control instead of restoring the old Retry button.
    page.keyboard.press("Enter")
    holding(page, pending, 1, "the second deferred retry")
    assert len(attempts) == 3 and len(pending) == 1
    expect(retry).to_have_attribute("aria-disabled", "true")
    page.keyboard.press("Tab")
    after = page.get_by_role("button", name="After diff")
    expect(after).to_be_focused()
    with page.expect_event(
        "requestfailed", lambda request: "/api/deferred" in request.url
    ) as failed:
        pending.pop().abort("failed")
    assert failed.value.failure == "net::ERR_FAILED"
    reported_browser_errors(page, "Failed to load resource: net::ERR_FAILED")
    expect(page.get_by_role("button", name="Retry")).not_to_have_attribute(
        "aria-disabled", "true"
    )
    expect(after).to_be_focused()

    # A successful retry falls back to the file disclosure when its error control
    # is replaced by rendered source.
    retry = page.get_by_role("button", name="Retry")
    page.keyboard.press("Shift+Tab")
    expect(retry).to_be_focused()
    with page.expect_response(
        lambda response: "/api/deferred" in response.url and response.status == 200
    ):
        page.keyboard.press("Enter")
    expect(
        page.locator('lf-diff [data-lf-datum=\'["config.py","new",1]\']')
    ).to_contain_text("enabled = True")
    expect(page.locator("lf-diff summary")).to_be_focused()
    assert len(attempts) == 4


@pytest.mark.parametrize("defer_first", [False, True])
def test_phone_diff_headers_keep_distinguishing_parent_folder_readable(
    browser, serve, defer_first
):
    """Repeated basenames remain identifiable before tapping their source rows."""
    names = ("dispatch", "improving-instructions", "todos")
    patch = "".join(
        f"diff --git a/.claude/skills/{name}/CLAUDE.md b/.claude/skills/{name}/CLAUDE.md\n"
        f"--- a/.claude/skills/{name}/CLAUDE.md\n+++ b/.claude/skills/{name}/CLAUDE.md\n"
        "@@ -1 +1 @@\n-old = True\n+new = True\n"
        for name in names
    )
    url = serve(
        leaf_page(
            "Identify sources",
            "<h1>Identify sources</h1>"
            '<lf-diff id="patch" source="patch-data" collapsed><pre></pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 360, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.evaluate("document.fonts.ready")
    if defer_first:
        # Hold the first file's preparation after the native disclosure opens.
        # This orders insertion after the tap's settled frame without a delay.
        page.evaluate("""() => {
      const diff = document.querySelector('#patch');
      const original = diff.prepareEntry;
      let release;
      window.lfDiffPreparation = {
        release: () => release(),
      };
      diff.prepareEntry = async function(...args) {
        if (args[1].path.endsWith('/dispatch/CLAUDE.md')) {
          const held = new Promise(resolve => { release = resolve; });
          window.lfDiffPreparationStarted = true;
          await held;
        }
        return original.apply(this, args);
      };
    }""")
    headers = page.locator("#patch .lf-diff-head")
    expect(headers).to_have_count(3)
    for head, name in zip(headers.all(), names, strict=True):
        reading = head.evaluate("""head => {
          const parent = head.querySelector('.lf-diff-dir-parent');
          const base = head.querySelector('.lf-diff-base');
          const prefix = new Range();
          prefix.setStart(parent.firstChild, 0);
          prefix.setEnd(parent.firstChild, Math.min(3, parent.textContent.length - 1));
          const ink = prefix.getBoundingClientRect();
          const box = parent.getBoundingClientRect();
          return {text: parent.textContent, shown: getComputedStyle(parent).opacity,
            prefix: ink.width + parseFloat(getComputedStyle(parent, '::before').width), room: box.width,
            base: base.textContent, baseCut: base.scrollWidth > base.clientWidth};
        }""")
        assert reading["text"] == name + "/"
        assert reading["shown"] == "1"
        assert reading["room"] >= reading["prefix"], reading
        assert reading["base"] == "CLAUDE.md" and not reading["baseCut"], reading
        head.tap()
        file = head.locator("..")
        expect(file).to_have_attribute("open", "")
        if defer_first and name == "dispatch":
            page.wait_for_function("window.lfDiffPreparationStarted === true")
            one_frame(page)
            page.evaluate("window.lfDiffPreparation.release()")
        expect(file.locator("[data-line]").last).to_contain_text("new = True")
        head.tap()
        expect(file).not_to_have_attribute("open", "")


def test_opening_diff_keeps_rendering_pending_until_lazy_source_arrives(browser, serve):
    """A disclosure's registered source preparation is part of its gesture's render."""
    patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-old
+new
diff --git a/other.md b/other.md
--- a/other.md
+++ b/other.md
@@ -1 +1 @@
-old
+new
"""
    url = serve(
        leaf_page(
            "Lazy source",
            '<lf-diff id="patch" source="patch-data" collapsed><pre></pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    page = open_page(browser, url)
    held = []
    page.route("**/vendor/syntax/markdown.js", lambda route: held.append(route))
    head = page.locator(".lf-diff-head").first
    head.click()
    holding(page, held, 1, "the lazy Markdown grammar")
    try:
        one_frame(page)
        assert not page.evaluate(
            "Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
        ), "registered source preparation must keep rendering pending"
    finally:
        held[0].continue_()
    rendered(page)
    expect(head.locator("..").locator("[data-line]").last).to_contain_text("new")


PATH_PARTS = """head => {
  const path = head.querySelector('.lf-diff-path');
  const room = path.getBoundingClientRect();
  return [...path.querySelectorAll('.lf-diff-dir, .lf-diff-base')].map(part => {
    const words = new Range();
    words.selectNodeContents(part);
    const own = part.getBoundingClientRect();
    return {text: part.textContent, shown: getComputedStyle(part).opacity !== '0',
      whole: [...words.getClientRects()].every(ink =>
        ink.left >= Math.max(own.left, room.left) - 0.5
        && ink.right <= Math.min(own.right, room.right) + 0.5)};
  });
}"""


def test_printed_diff_rows_hold_their_whole_paths(browser, serve):
    """Paper gives no title, focus or press back to a cut path, so a printed file row
    wraps to show every folder and the whole name; the screen row still cuts them."""
    paths = (
        "plugins/worktrunk/skills/worktrunk/references/configuration/hooks/README.md",
        "src/picker/snapshots/wt__commands__picker__items__tests__unified_diff.snap",
    )
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for path in paths
    )
    url = serve(
        leaf_page(
            "Printed paths",
            f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>',
        )
    )
    # A5's printable width under the print dialog's default margins.
    context = browser.new_context(viewport={"width": 483, "height": 800})
    page = open_page(browser, url, context=context)
    page.evaluate("document.fonts.ready")
    heads = page.locator("#patch .lf-diff-head")
    expect(heads).to_have_count(len(paths))
    screen = [head.evaluate(PATH_PARTS) for head in heads.all()]
    assert all(
        not all(part["shown"] and part["whole"] for part in parts) for parts in screen
    ), f"each path must be cut on screen, or print proves nothing: {screen}"
    page.emulate_media(media="print")
    one_frame(page)
    for head, path in zip(heads.all(), paths, strict=True):
        parts = head.evaluate(PATH_PARTS)
        assert "".join(part["text"] for part in parts) == path
        assert all(part["shown"] and part["whole"] for part in parts), (path, parts)
