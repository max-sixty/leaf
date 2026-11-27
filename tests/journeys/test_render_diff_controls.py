"""Diff controls share canonical fields and preserve the compact source reader."""

import re
from html import escape

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    leaf_page,
    open_page,
    scroll_settled,
    told,
    write,
)

from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.example_data import patch_manifest


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
            '<h1>Config change</h1><lf-diff id="patch" source="patch-data"></lf-diff>'
            f'<lf-diff id="native"><pre>{escape(patch)}</pre></lf-diff>',
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 390 if touch else 1280, "height": 844},
        has_touch=touch,
        is_mobile=touch,
    )
    page = open_page(browser, url, context=context)
    diff = page.locator("#patch")
    buttons = diff.locator(".lf-diff-line-comment")
    expect(buttons).to_have_count(4)

    def geometry():
        return buttons.evaluate_all("""buttons => buttons.map(button => {
          const ink = new Range(); ink.selectNodeContents(button);
          const plus = getComputedStyle(button, '::before');
          const box = button.getBoundingClientRect();
          return {right: box.left + parseFloat(plus.left) + parseFloat(plus.width), number: ink.getBoundingClientRect().left,
                  height: button.parentElement.getBoundingClientRect().height,
                  hitHeight: button.getBoundingClientRect().height,
                  background: getComputedStyle(button).backgroundColor,
                  opacity: plus.opacity};
        })""")

    before = geometry()
    for reading in before:
        assert reading["right"] <= reading["number"], reading
        assert reading["hitHeight"] == reading["height"], reading
        assert reading["opacity"] == "0", reading
    native = page.locator("#native .lf-diff-line").first
    assert before[0]["height"] == native.bounding_box()["height"]
    assert (
        buttons.first.bounding_box()["width"]
        == page.locator("#native .lf-diff-line-comment").first.bounding_box()["width"]
    )
    diff.locator(".lf-diff-line > [data-line]").first.hover()
    after = geometry()
    assert after[0]["opacity"] == "1"
    assert after[0]["background"] == "rgba(0, 0, 0, 0)"
    assert [{k: v for k, v in r.items() if k != "opacity"} for r in after] == [
        {k: v for k, v in r.items() if k != "opacity"} for r in before
    ]
    # Moving to the next line retires the previous gutter highlight.
    diff.locator(".lf-diff-line > [data-line]").nth(1).hover()
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
    """Response text, focus cues and Markdown reading survive source-widget seating.

    Sending the same Markdown on both sides additionally exercises the complete
    reading vocabulary installed in declared trees, including a table that must
    scroll within its message instead of widening the page.
    """
    patch = "diff --git a/config.py b/config.py\n--- a/config.py\n+++ b/config.py\n@@ -1 +1 @@\n-old\n+new\n"
    url = serve(
        leaf_page(
            "Review source and prose",
            '<h1>Review source and prose</h1><p id="subject">Discuss this paragraph.</p>'
            '<lf-diff id="patch" source="patch-data"></lf-diff>',
            head="""<style id="response-inset-override">
              :is(.lf-fab-bar, .lf-margin-preview, [data-lf-thread-surface]) {
                --lf-thread-text-pad-block: 12px !important;
                --lf-compose-action-inset: 16px !important;
              }
            </style>""",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
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
          const properties = ['font-family', 'font-size', 'line-height', 'color'];
          return Object.fromEntries(properties.map(name => [name, style.getPropertyValue(name)]));
        }""")

    def insets(field, card):
        """Where the field's words start and end, from the outer edge of its card."""
        return field.evaluate(
            """(field, card) => {
              const edge = field.closest(card).getBoundingClientRect();
              const box = field.getBoundingClientRect();
              const style = getComputedStyle(field);
              const side = name =>
                parseFloat(style[`border${name}Width`]) + parseFloat(style[`padding${name}`]);
              return {
                start: box.left + side('Left') - edge.left,
                end: edge.right - (box.right - side('Right')),
                top: box.top + side('Top') - edge.top,
              };
            }""",
            card,
        )

    def forced_ring(field):
        return field.evaluate("""field => {
          // A seated editor wears the ring; a floating editor draws it on a box laid
          // over its frame, which an error about the box would otherwise cover.
          const frame = field.closest('.lf-compose-field');
          for (const [node, pseudo] of [[field], [frame], [frame, '::after']]) {
            const style = getComputedStyle(node, pseudo);
            if (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0)
              return [style.outlineWidth, style.outlineStyle, style.outlineColor];
          }
          return null;
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
    # The floating box is the frame of the card it becomes, and a seated box stands
    # where its card will, so across the card each box's words stand where its card's
    # will. Above its field the floating frame also runs over the card's edge and
    # padding, where the card's first message will stand, so its words stand that
    # frame lower than a seated box's.
    frame = 1 + float(
        floating.evaluate(
            "node => getComputedStyle(node).getPropertyValue('--lf-thread-pad')"
        ).removesuffix("px")
    )
    physical_face = face(floating)
    physical_insets = insets(floating, ".lf-compose-field")
    assert physical_insets["top"] == frame + 12
    page.emulate_media(forced_colors="active")
    forced = forced_ring(floating)
    assert forced, "the floating response paints no focus ring in forced colors"
    page.emulate_media(forced_colors="none")
    write(floating, markdown)
    draft_face = face(floating)
    draft_insets = insets(floating, ".lf-compose-field")
    # Touch reserves Send's column; a mouse lets words use its free corner.
    text_end = f"{44 + 2 * 16 + 1}px" if touch else "8px"
    assert f"{draft_insets['end'] - frame:g}px" == text_end
    floating.press("Control+Enter" if touch else "Enter")
    physical_reading = reading(page.locator(".lf-margin-preview .lf-msg-body").first)
    sent_insets = page.locator(".lf-margin-preview .lf-msg-text").first.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return {block: style.paddingTop, end: style.paddingInlineEnd};
        }"""
    )
    assert sent_insets == {"block": "12px", "end": text_end}
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
    seated_insets = insets(inline, ".lf-fab-bar")
    assert seated_insets == physical_insets | {"top": 12}
    page.emulate_media(forced_colors="active")
    assert forced_ring(inline) == forced
    page.emulate_media(forced_colors="none")
    write(inline, markdown)
    assert face(inline) == draft_face
    # A seat is wider than a card, and its message keeps a card's width, so a seated
    # draft's words end where that message's will rather than at the field's end.
    seated_draft = insets(inline, ".lf-fab-bar")
    assert seated_draft | {"end": None} == draft_insets | {"top": 12, "end": None}
    inline.press("Control+Enter" if touch else "Enter")
    seated_message = diff.locator(".lf-msg-body").first
    assert reading(seated_message) == physical_reading
    assert insets(seated_message.locator(".lf-msg-text"), ".lf-page-thread")[
        "end"
    ] == pytest.approx(seated_draft["end"], abs=0.01)


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "dark")])
def test_diff_filter_has_one_frame_and_clears_with_its_count_inside(
    browser, serve, width, scheme
):
    """The canonical search owns the frame, count, and Clear; filtering owns the rows,
    and narrows them without pulling what follows the diff up into the window."""
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
                f'<h1>Changed files</h1><lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>'
                '<p id="after">After the diff.</p>',
            )
        ),
        context=context,
    )
    diff = page.locator("#patch")
    field = diff.locator(".lf-diff-search")
    editor = field.locator("input")
    count = diff.locator(".lf-diff-progress")
    rows = diff.locator(".lf-diff-file:not([hidden])")
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
    after = page.locator("#after")
    below = after.bounding_box()
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
        assert after.bounding_box()["y"] >= min(below["y"], 844)
    field.get_by_role("button", name="Clear").click()
    expect(editor).to_have_value("")
    expect(editor).to_be_focused()
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")
    assert field.bounding_box() == frame
    assert after.bounding_box() == below
    editor.fill("file-0")
    expect(rows).to_have_count(1)
    editor.press("ControlOrMeta+A")
    editor.press("Backspace")
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")


def test_worktree_disclosures_keep_diff_reading_state_and_unknown_totals(
    browser, serve
):
    """Several worktrees stay open independently, retaining each nested reader.

    Missing evidence remains visibly unknown beside known totals; neither an empty
    collection nor a fifth member needs a different browsing surface. A revision to a
    row's evidence edits it in place, and one that rebuilds the rows reopens each the
    reader opened.
    """
    head = "1234567890abcdef1234567890abcdef12345678"
    patch = "".join(
        f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for path in ("app.py", "tests.py")
    )
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "Review worktrees",
                    '<h1>Review worktrees</h1><lf-worktree-diffs id="trees">'
                    '<lf-worktree id="drafts" label="retain-drafts" '
                    'branch="codex/retain-drafts" path="/workspace/leaf.retain-drafts" '
                    f'head="{head}" status="changed" files="2" additions="2" deletions="2" open>'
                    "<p>Keep reply drafts keyed by thread</p>"
                    "<aside>Drafts survive changing the selected thread.</aside>"
                    "<details><summary>Snapshot details</summary>"
                    f"<p>Current commit <code>{head}</code></p></details>"
                    f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>'
                    '</lf-worktree><lf-worktree id="missing" label="missing checkout" '
                    'path="/workspace/missing" status="unavailable">'
                    "<p>The supplied checkout could not be read.</p></lf-worktree>"
                    + "".join(
                        f'<lf-worktree id="clean-{index}" label="clean {index}" '
                        f'path="/workspace/clean-{index}" status="clean" files="0" '
                        f'additions="0" deletions="0">'
                        "<p>No changes.</p></lf-worktree>"
                        for index in range(3)
                    )
                    + '</lf-worktree-diffs><lf-worktree-diffs id="empty"></lf-worktree-diffs>'
                    '<lf-file-tree id="files" for="patch"></lf-file-tree>',
                ),
                packages=("diff", "file-tree"),
            )
        ),
    )
    overview = page.locator("#trees .lf-worktree-overview")
    expect(overview).to_contain_text("5 worktrees")
    expect(overview).to_contain_text("2 files")
    expect(overview).to_contain_text("+2")
    expect(overview).to_contain_text("−2")
    expect(overview).to_contain_text("1 unavailable")
    expect(page.locator("#empty").get_by_text("No worktrees supplied")).to_be_visible()
    expect(
        page.locator("#empty").get_by_text("0 files", exact=True)
    ).not_to_be_visible()

    row = page.locator("#drafts .lf-worktree-disclosure")
    summary = row.locator(":scope > summary")
    expect(row).to_contain_text("/workspace/leaf.retain-drafts")
    expect(summary).to_contain_text(head[:8])
    # Counts say a row changed; a word names only what counts can't.
    expect(summary).not_to_contain_text("Changed")
    expect(page.locator("#clean-0 .lf-worktree-summary")).to_contain_text("Clean")
    snapshot = page.locator("#drafts").locator(
        "details", has=page.get_by_text("Snapshot details", exact=True)
    )
    snapshot.locator("summary").click()
    expect(snapshot.locator("code")).to_have_text(head)
    diff = page.locator("#patch")
    search = diff.get_by_label("Filter diff files")
    search.fill("app.py")
    file_summary = diff.locator("summary").filter(has_text="app.py")
    file_summary.click()
    expect(file_summary.locator("..")).not_to_have_attribute("open")

    summary.click()
    expect(search).not_to_be_visible()
    # Tab reaches the next worktree; Enter opens it independently of the first.
    page.keyboard.press("Tab")
    missing_summary = page.locator("#missing .lf-worktree-summary")
    expect(missing_summary).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text("The supplied checkout could not be read.")).to_be_visible()
    expect(missing_summary).to_contain_text("Unavailable")
    expect(missing_summary).not_to_contain_text("0 files")
    expect(missing_summary).not_to_contain_text("+0")

    summary.click()
    expect(search).to_have_value("app.py")
    expect(file_summary.locator("..")).not_to_have_attribute("open")
    expect(snapshot.locator("code")).to_be_visible()
    expect(page.get_by_text("The supplied checkout could not be read.")).to_be_visible()
    # Editing both the active row and its sibling retains nested reading state, even
    # where the edit changes the evidence's own elements: the row reads none of them.
    source = serve.page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace(
            "The supplied checkout could not be read.",
            "The supplied checkout is temporarily unavailable.",
        )
        .replace(
            "Keep reply drafts keyed by thread",
            "Keep reply drafts safely keyed by thread",
        )
        .replace("<aside>", '<aside title="Agent commentary">')
    )
    told(page)
    expect(
        page.get_by_text("The supplied checkout is temporarily unavailable.")
    ).to_be_visible()
    expect(page.get_by_text("Keep reply drafts safely keyed by thread")).to_be_visible()
    expect(page.locator("#drafts > aside")).to_have_attribute(
        "title", "Agent commentary"
    )
    expect(search).to_have_value("app.py")
    expect(file_summary.locator("..")).not_to_have_attribute("open")
    expect(snapshot.locator("code")).to_be_visible()
    file_summary.click()
    expect(diff.locator("[data-line]:visible").filter(has_text="new")).to_be_visible()
    fifth_summary = page.locator("#clean-2 .lf-worktree-summary")
    fifth_summary.click()
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()
    # A related navigator must reveal the worktree around its destination too.
    summary.click()
    expect(row).not_to_have_attribute("open")
    page.locator("#files").get_by_role("treeitem", name="app.py", exact=True).click()
    expect(row).to_have_attribute("open", "")
    expect(diff.locator("[data-line]:visible").filter(has_text="new")).to_be_visible()
    # A changed snapshot attribute rebuilds the rows; each keeps the reader's choice,
    # whether it closed an authored-open row or opened a closed one.
    summary.click()
    expect(row).not_to_have_attribute("open")
    source.write_text(
        source.read_text().replace(
            'path="/workspace/missing"', 'path="/workspace/gone"'
        )
    )
    told(page)
    expect(page.locator("#missing")).to_contain_text("/workspace/gone")
    expect(row).not_to_have_attribute("open")
    expect(
        page.get_by_text("The supplied checkout is temporarily unavailable.")
    ).to_be_visible()
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()
    # A fresh shadow tree restores both an authored-open row the reader closed
    # and an authored-closed row they opened, after startup observation has ended.
    page.reload()
    wait_until_ready(page)
    expect(page.locator("#drafts .lf-worktree-disclosure")).not_to_have_attribute(
        "open"
    )
    expect(page.locator("#clean-2").get_by_text("No changes.")).to_be_visible()


@pytest.mark.parametrize("scroller", ["pane", "document"])
def test_file_tree_lands_at_the_file_start_after_reading_down(browser, serve, scroller):
    """File activation reveals its first line in document and nested scrollports,
    including a return to the current file after reading further down."""

    def patch(path, lines=100):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,{lines} +1,{lines} @@\n"
            + "".join(f"-old line {line}\n+new line {line}\n" for line in range(lines))
        )

    pane = scroller == "pane"
    tree_markup = '<lf-file-tree id="files" for="patch"></lf-file-tree>'
    evidence_markup = (
        '<div id="evidence"><p>Inspect the changes in each file.</p>'
        '<lf-diff id="patch" source="change" view="file"></lf-diff>'
        "</div>"
    )
    regions = (
        '<lf-pane id="files-pane" label="Files"><header>Files</header>'
        + tree_markup
        + '</lf-pane><lf-pane id="patch-pane" label="Patch"><header>Patch</header>'
        + evidence_markup
        + "</lf-pane>"
        if pane
        else '<aside id="files-pane">' + tree_markup + "</aside>" + evidence_markup
    )
    url = serve(
        leaf_page(
            "Navigate a long patch",
            '<header><h1>Review files</h1></header><div id="regions">'
            + regions
            + "</div>"
            + ("" if pane else '<p style="min-height:1200px">Review context</p>'),
            head="""<style>
              #regions { display:grid; grid-template-columns:240px minmax(0,1fr); }
              #files { --lf-pane-top:0px; margin:0; padding:0; }
              #patch { margin:0; }
              aside#files-pane { position:sticky; top:var(--lf-top); align-self:start; }
              aside #files { --lf-file-tree-height:250px; }
            </style>""",
            layout="workspace" if pane else "column",
        )
    )
    page_data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(
            patch("first.md")
            + patch("second.md")
            + patch("third.md", 3)
            + "diff --git a/z-mode.sh b/z-mode.sh\nold mode 100644\nnew mode 100755\n"
        ),
    )
    context = browser.new_context(viewport={"width": 810, "height": 990})
    page = open_page(browser, url, context=context)
    tree = page.locator("#files")
    evidence = page.locator("#evidence")
    visible = page.locator("#patch .lf-diff-fold:visible")
    expect(visible).to_contain_text("first.md")
    tree_box = tree.bounding_box()
    if pane:
        pane_box = page.locator("#files-pane").bounding_box()
        border = page.locator("#files-pane").evaluate(
            "node => parseFloat(getComputedStyle(node).borderBottomWidth)"
        )
        assert tree_box["y"] + tree_box["height"] == pytest.approx(
            pane_box["y"] + pane_box["height"] - border, abs=0.5
        ), "the navigator must fill the pane without an authored height override"
    second = tree.get_by_role("treeitem", name="second.md", exact=True)

    def scroll_into_file():
        evidence.hover()
        page.mouse.wheel(0, 900)
        page.wait_for_function(
            "document.getElementById('evidence').scrollTop > 400"
            if pane
            else "scrollY > 400"
        )
        scroll_settled(page)

    def starts_below_header():
        page.wait_for_function("""() => {
          const body = document.getElementById('evidence');
          const fold = [...document.getElementById('patch').shadowRoot
            .querySelectorAll('.lf-diff-fold')].find(node => node.checkVisibility());
          const summary = fold?.querySelector('summary');
          const firstLine = fold?.querySelector('.lf-diff-line > [data-line]');
          if (!summary || !firstLine?.textContent.includes('old line 0')) return false;
          const top = summary.getBoundingClientRect().top;
          const pane = body.closest('lf-pane');
          const edge = pane ? body.getBoundingClientRect().top + body.clientTop : 0;
          const bottom = pane ? body.getBoundingClientRect().bottom : innerHeight;
          const line = firstLine.getBoundingClientRect();
          return top >= edge - 1
            && line.top >= summary.getBoundingClientRect().bottom - 1
            && line.bottom <= bottom;
        }""")

    scroll_into_file()
    second.click()
    expect(visible).to_contain_text("second.md")
    starts_below_header()
    expect(second).to_be_focused()
    # A file already selected still has a route back to the start after reading down.
    scroll_into_file()
    second.click()
    starts_below_header()
    expect(second).to_be_focused()
    # Keyboard selection of a much shorter file must reveal its first line too;
    # its pinned heading alone is not evidence that the beginning is visible.
    scroll_into_file()
    second.press("ArrowDown")
    third = tree.get_by_role("treeitem", name="third.md", exact=True)
    expect(third).to_be_focused()
    page.keyboard.press("Enter")
    expect(visible).to_contain_text("third.md")
    starts_below_header()
    expect(third).to_be_focused()
    # A mode-only file has a commentable metadata row, without a textual body.
    third.press("ArrowDown")
    mode = tree.get_by_role("treeitem", name="z-mode.sh", exact=True)
    expect(mode).to_be_focused()
    page.keyboard.press("Enter")
    metadata = page.locator("#patch .lf-diff-metadata:visible")
    expect(metadata).to_contain_text("z-mode.sh")
    expect(metadata).to_be_in_viewport(ratio=1)
    expect(visible).to_have_count(0)
    expect(mode).to_be_focused()


@pytest.mark.parametrize("view", ["patch", "file"])
def test_file_tree_opens_current_diff_files_by_pointer_and_keyboard(
    browser, serve, view
):
    """A separately mounted navigator follows a diff's output and travels through
    the ordinary datum route, including reactivation and updated source evidence."""

    def patch(path, value):
        return (
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{value}\n"
        )

    url = serve(
        leaf_page(
            "Browse patch files",
            "<h1>Review the importer</h1>"
            '<lf-file-tree id="files" for="patch" data-height="250"></lf-file-tree>'
            f'<lf-diff id="patch" source="change" view="{view}" collapsed></lf-diff>',
        )
    )
    page_data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(
            patch("src/importer.py", "keep_names = True")
            + patch("tests/importer.py", "assert keep_names")
        ),
    )
    page = open_page(browser, url)
    tree = page.locator("#files")
    row = tree.get_by_role("treeitem", name=re.compile(r"importer\.py")).first
    expect(row).to_be_visible()
    folds = page.locator("#patch .lf-diff-fold")
    if view == "patch":
        expect(folds.first).not_to_have_attribute("open", "")
    else:
        expect(page.locator("#patch .lf-diff-search")).to_have_count(0)
        expect(folds.first).to_have_attribute("open", "")
    # Search narrows the navigator until a file is opened.
    search = tree.get_by_role("textbox")
    search.fill("importer")
    row.click()
    expect(search).to_have_value("")
    expect(row).to_be_focused()
    expect(folds.first).to_have_attribute("open", "")
    expect(folds.first.locator("pre")).to_contain_text("keep_names = True")
    # The same selected file still has an activation route after its patch closes.
    folds.first.locator("summary").click()
    row.click()
    expect(folds.first).to_have_attribute("open", "")
    # A released pointer activation keeps this navigator's keyboard ownership.
    # The tree's folders remain part of its ordinary arrow-key traversal.
    expect(row).to_be_focused()
    search.fill("")
    search.press("Tab")
    expect(row).to_be_focused()
    folder = tree.get_by_role("treeitem", name="src", exact=True)
    page.keyboard.press("ArrowLeft")
    expect(folder).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(folder).to_have_attribute("aria-expanded", "false")
    page.keyboard.press("ArrowRight")
    expect(folder).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowDown")
    expect(row).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(tree.get_by_role("treeitem", name="tests", exact=True)).to_be_focused()
    page.keyboard.press("ArrowDown")
    other = tree.get_by_role("treeitem", name=re.compile(r"importer\.py")).last
    expect(other).to_be_focused()
    page.keyboard.press("Enter")
    expect(folds.last).to_have_attribute("open", "")
    expect(folds.last.locator("pre")).to_contain_text("assert keep_names")
    expect(other).to_be_focused()
    if view == "file":
        expect(folds.first).not_to_be_visible()
        expect(folds.last).to_be_visible()
        expect(other).to_have_attribute("aria-selected", "true")
        # Enter in search chooses its first match's row; the row opens its file.
        for path, visible in [
            ("src/importer.py", folds.first),
            ("tests/importer.py", folds.last),
        ]:
            search.fill(path)
            search.press("ArrowDown")
            search.press("Enter")
            expect(search).to_have_value("")
            expect(tree.locator(f'[data-item-path="{path}"]')).to_be_focused()
            page.keyboard.press("Enter")
            expect(visible).to_be_visible()
        folds.last.locator("summary").press("{")
        expect(folds.first).to_be_visible()
        expect(folds.last).not_to_be_visible()
        expect(row).to_have_attribute("aria-selected", "true")
        expect(other).to_have_attribute("aria-selected", "false")
        # Preparing new evidence does not take ownership of a selection made while
        # that preparation is in flight. Hold one boundary to make the ordering exact.
        page.evaluate("""() => {
          const diff = document.getElementById('patch');
          const prepareEntry = diff.prepareEntry.bind(diff);
          const held = new Promise(resolve => window.releaseEvidence = resolve);
          diff.prepareEntry = async (...args) => {
            window.evidenceHeld = true;
            await held;
            return prepareEntry(...args);
          };
        }""")
        page_data_model.cmd_data_set(
            serve.page_dir,
            "change",
            patch_manifest(
                patch("src/importer.py", "new_names = True")
                + patch("tests/importer.py", "assert new_names")
            ),
        )
        page.wait_for_function("window.evidenceHeld === true")
        folds.first.locator("summary").press("}")
        page.evaluate("window.releaseEvidence()")
        expect(folds.last.locator("pre")).to_contain_text("assert new_names")
        expect(folds.last).to_be_visible()
        expect(folds.first).not_to_be_visible()
        expect(other).to_have_attribute("aria-selected", "true")
        expect(row).to_have_attribute("aria-selected", "false")
    search.fill("")
    # A source update replaces the producer inventory, rather than leaving stale rows.
    page_data_model.cmd_data_set(
        serve.page_dir,
        "change",
        patch_manifest(patch("src/reader.py", "preserve_case = True")),
    )
    next_row = tree.get_by_role("treeitem", name=re.compile(r"reader\.py"))
    expect(next_row).to_be_visible()
    expect(
        tree.get_by_role("treeitem", name=re.compile(r"importer\.py"))
    ).to_have_count(0)
    next_row.click()
    expect(page.locator("#patch pre")).to_contain_text("preserve_case = True")
    # Clearing the input clears the derived inventory too.
    page_data_model.cmd_data_clear(serve.page_dir, "change")
    expect(tree.get_by_role("treeitem")).to_have_count(0)
