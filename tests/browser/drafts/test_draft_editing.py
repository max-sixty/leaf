"""Editing an lf-draft in place: opening it, caret and selection, exact Markdown source,
saving and its controls, Enter, and comparing versions."""

import re
import shutil

import pytest
from click.testing import CliRunner
from interact_support import append_command, response_reference
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_cases_navigation import DRAFT_DRAWN, JOURNEY_V1, _publish
from render_harness import (
    CHROME_ROOT,
    available_commands,
    compare_with,
    consume_browser_errors,
    draft_control,
    example_media,
    expect_panel_says,
    field_press,
    hold_selection,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    press_draft_control,
    resized,
    round_trip,
    scroll_settled,
    sending,
    undo,
    word_point,
    write,
)

from browser.margin import MARGIN_EDITOR_ROOTS
from browser.threads import open_panel_thread
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_double_clicking_a_draft_keeps_its_frame_and_selected_word(browser, serve):
    """The draft stays in place and double-click keeps the selected word on edit.

    The editor sets its words exactly where the prose stood, since the toolbar hovers
    over the border rather than taking room beside the caret. The frame's inset focus
    paint changes without reaching outside the reading box, and print keeps the saved
    body while dropping the shared editor."""
    page = open_page(browser, serve(JOURNEY_V1))
    metrics = """(sel) => {
      const el = document.querySelector('#draft-ops ' + sel), s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return [b.x + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              b.y + parseFloat(s.paddingTop) + parseFloat(s.borderTopWidth), b.width, b.height];
    }"""
    read = page.evaluate(metrics, ".lf-draft-body")
    host = page.locator("#draft-ops").bounding_box()
    # A 4px band above the box, and the box's own top-left corner. The band is where
    # the answer to "did the frame move" lives and no measurement of geometry can
    # reach it: an outset ring is paint, so every rect stayed exactly as asserted
    # below while the frame the user sees grew 2px on every side, corners
    # rounding wider to match. Bytes, not pixels — the same encoder over the same
    # content gives the same file, so identical files are identical paint. The band
    # stops at the box's middle, short of the toolbar that hovers over its top right.
    band = {
        "x": host["x"] - 4,
        "y": host["y"] - 4,
        "width": host["width"] / 2,
        "height": 4,
    }
    inside = {"x": host["x"], "y": host["y"], "width": 40, "height": 40}
    outside_before = page.screenshot(clip=band)
    inside_before = page.screenshot(clip=inside)

    # Aimed at where the browser actually drew the word, not at an offset from the
    # box's edge. A pixel count is a fact about one font: a change of face moves the
    # word a fixed offset lands in, so the test would read as "the editor opens on the
    # wrong word" when nothing about the gesture had changed.
    spot = page.evaluate(
        """(word) => {
            const body = document.querySelector('#draft-ops .lf-draft-body');
            const node = document.createTreeWalker(body, NodeFilter.SHOW_TEXT).nextNode();
            const at = node.data.indexOf(word);
            const r = document.createRange();
            r.setStart(node, at); r.setEnd(node, at + word.length);
            const b = r.getBoundingClientRect();
            return [b.x + b.width / 2, b.y + b.height / 2];
        }""",
        "migration",
    )
    page.mouse.dblclick(*spot)
    editor = page.locator("#draft-ops leaf-text")
    expect(editor).to_be_focused()
    pencil = draft_control(page, "edit", "draft-ops")
    assert page.screenshot(clip=band) == outside_before, (
        "opening the editor painted outside the box the draft already occupied"
    )
    assert page.screenshot(clip=inside) != inside_before, (
        "the open editor is indistinguishable from the read view at the box's edge"
    )
    edited = page.evaluate(metrics, "leaf-text")
    assert edited == read, (
        "the editor moved, narrowed or changed the height of the draft's words"
    )
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft changed shape under the pointer when the editor opened"
    )
    assert (
        page.evaluate(
            "() => getSelection().rangeCount > 0 && "
            "getSelection().containsNode(document.querySelector('#draft-ops .lf-draft-body'), true)"
        )
        is False
    ), "the gesture left the page's own words selected under the open editor"
    selected = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return t.value.slice(t.selectionStart, t.selectionEnd); }"
    )
    assert selected == "migration", (
        f"the box opened on {selected!r} rather than the word clicked"
    )

    # Closing states both properties in reverse, and the focus half is a question
    # only because the ✎ is CSS-hidden for as long as the editor is there: #close
    # reaches for it the instant the editor goes, so a style that hadn't caught up
    # would drop a keyboard user back at the top of the page.
    page.keyboard.press("Escape")
    expect(pencil).to_be_focused()
    expect(pencil).to_have_attribute("aria-expanded", "false")
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft came back from an edit a different shape than it went in"
    )

    # Reopened through the other door, because print is where the box has to be
    # gone and its words still there — and print emulation blurs the leaf-text it
    # hides, so an editor opened before this point is no longer one Escape closes.
    draft_control(page, "edit", "draft-ops").click()
    expect(page.locator("#draft-ops leaf-text")).to_be_visible()
    page.emulate_media(media="print")
    assert page.locator("#draft-ops").inner_text() == DRAFT_DRAWN, (
        "the printed page lost the draft's words to a box paper hasn't got"
    )
    page.emulate_media(media="screen")


@pytest.mark.parametrize(
    "in_pane, formatted",
    [(False, True), (True, False)],
    ids=["document-markdown", "pane-plain"],
)
def test_opening_a_visible_line_in_a_long_draft_preserves_the_reading_position(
    browser, serve, in_pane, formatted
):
    """Editing a visible word keeps it there even when the draft exceeds the window."""
    words = (
        "The **release note** remains `editable`."
        if formatted
        else "The release note remains editable."
    )
    text = "\n".join(f"Line {i}: {words}" for i in range(60))
    draft = f'<lf-draft id="long-draft"><pre>{text}</pre></lf-draft>'
    body = (
        "<header><h1>Release notes</h1></header>"
        f'<lf-pane id="reading" label="Notes">{draft}</lf-pane>'
        if in_pane
        else f"<h1>Release notes</h1>{draft}<p>Following words.</p>"
    )
    page = open_page(
        browser,
        serve(
            leaf_page("Long draft", body, layout="workspace" if in_pane else "column")
        ),
    )
    resized(page, 800, 900)
    # A letter of line 30, which the reader has scrolled to the window's middle.
    letter = """el => {
      const word = 'Line 30:', walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode()) && !node.data.includes(word)) {}
      const at = node.data.indexOf(word), range = document.createRange();
      range.setStart(node, at + 3); range.setEnd(node, at + 4);
      const b = range.getBoundingClientRect();
      return [b.x + b.width / 2, b.y + b.height / 2];
    }"""
    body_text = page.locator("#long-draft .lf-draft-body")
    page.locator("#long-draft").evaluate(
        "(el, y) => { const box = el.closest('lf-pane') ? el : document.scrollingElement;"
        " box.scrollTop += y - innerHeight / 2; }",
        body_text.evaluate(letter)[1],
    )
    scroll_settled(page)
    point = body_text.evaluate(letter)
    assert 60 < point[1] < 850, point
    reading = """() => ({
      page: document.scrollingElement.scrollTop,
      draft: document.querySelector('#long-draft').scrollTop,
      top: document.querySelector('#long-draft').getBoundingClientRect().top
    })"""
    before = page.evaluate(reading)
    page.mouse.click(*point)
    expect(page.locator("#long-draft leaf-text")).to_be_focused()
    assert page.evaluate(reading) == before
    editor = page.locator("#long-draft leaf-text")
    offset = editor.evaluate("el => el.selectionStart")
    assert text.index("Line 30:") <= offset <= text.index("Line 30:") + 8
    expect(editor).to_have_js_property("value", text)


DRAFT_BLOCKS = """# Workshop

The morning starts at nine. Read the [setup guide](https://example.com/setup) first.

Two paragraphs stand a gap apart.

- one **bold** item
- a second with `inline`

```
leaf page init ./workshop
```

    pnpm install --frozen-lockfile

> ### Quoted
>
> Practice beats theory.
>
## Heading two

![Room layout](/media/051bee487bfb5d13.png)

| Room   | Chairs |
| ------ | -----: |
| `hall` |     40 |
| Annex  |     12 |

Tables seat four."""

# A picture named by a reference, and one whose source spans two lines.
NAMED_PICTURES = """![Room layout][room]

![Room
layout](/media/051bee487bfb5d13.png)

[room]: /media/051bee487bfb5d13.png"""

# Where a draft's words and picture stand, from its top: the first rendered glyph of
# each word and the picture, in its prose or its editor's closed root, skipping source
# syntax where the editor leaves it unseen.
DRAFT_AS_DRAWN = """(draft, words) => {
  const box = draft.getBoundingClientRect();
  const editor = draft.querySelector('leaf-text');
  const root = editor ? window.marginEditorRoots.get(editor) : draft.querySelector('.lf-draft-body');
  const at = (node) => {
    const r = node.getBoundingClientRect();
    return [r.left - box.left, r.top - box.top, r.width, r.height];
  };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const found = {};
  for (let node; (node = walker.nextNode()); ) {
    if (node.parentElement.closest('.lf-md-unseen, .lf-md-mark')) continue;
    for (const word of words) {
      const i = node.data.indexOf(word);
      if (i < 0 || word in found) continue;
      const range = document.createRange();
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      found[word] = at(range);
    }
  }
  const picture = root.querySelector('img:not(.cm-widgetBuffer)');
  if (picture) found.picture = at(picture);
  found.height = box.height;
  return found;
}"""


def test_a_draft_edits_where_it_reads(browser, serve, subtests):
    """A draft's editor that drew its Markdown in a sent message's face — a heading at
    the words' size, a blank line for each gap between blocks, a picture as its source,
    a fence's lines at a code line each and no mark after a link that leaves the page —
    would move the words below its first block on opening. The words and picture stay
    where the prose showed them, the editor taking each block's face and gaps from
    where it stands, an indented block's code as a fence's.

    A table drawn as its source's lines stood shorter or taller than the prose's table,
    moving every word below it. It is drawn as the prose's grid, its `|`s and delimiter
    row unseen until the caret reaches it, and shown then where they stand.

    A draft that drew a line break at each of its source's would show a short line after
    each long one when wrapped for a wider editor. It reads as a Markdown file, a line
    break inside a paragraph a space, and its editor joins those lines too, so each
    word stays where the prose showed it."""
    url = serve(
        leaf_page(
            "Draft faces",
            f'<h1>Draft faces</h1><lf-draft id="faces"><pre>{DRAFT_BLOCKS}</pre></lf-draft>'
            f'<lf-draft id="named"><pre>{NAMED_PICTURES}</pre></lf-draft>'
            f'<lf-draft id="wrapped"><pre>{WRAPPED}</pre></lf-draft>',
        )
    )
    (serve.page_dir / "media").mkdir(exist_ok=True)
    shutil.copy(
        example_media() / "051bee487bfb5d13.png",
        serve.page_dir / "media" / "051bee487bfb5d13.png",
    )
    page = open_page(browser, url, init_script=MARGIN_EDITOR_ROOTS)

    with subtests.test("a draft of every block"):
        draft = page.locator("#faces")
        words = [
            "Workshop",
            "morning",
            "guide",
            "first",  # The word after the link also catches room taken by its mark.
            "Two",
            "bold",
            "inline",
            "leaf",
            "pnpm",
            "Quoted",
            "Practice",
            "Heading",
            "Chairs",
            "hall",
            "Annex",
            "Tables",
        ]
        draft.locator(".lf-draft-body img").evaluate("image => image.decode()")
        shown = draft.evaluate(DRAFT_AS_DRAWN, words)
        draft_control(page, "edit", "faces").click()
        expect(draft.locator("leaf-text")).to_be_focused()
        page.wait_for_function(
            "draft => window.marginEditorRoots.get(draft.querySelector('leaf-text'))"
            "?.querySelector('img.lf-md-picture')?.complete",
            arg=draft.element_handle(),
        )
        rendered(page)
        editing = draft.evaluate(DRAFT_AS_DRAWN, words)
        # Exactly: a word moved by a fraction of a pixel still moves a device pixel on a
        # screen of two to the CSS pixel.
        assert editing == shown, (shown, editing)
        # The caret in a fence's code leaves the fence's lines standing for its padding.
        box = draft.bounding_box()
        page.mouse.click(
            box["x"] + editing["leaf"][0] + 2, box["y"] + editing["leaf"][1] + 5
        )
        rendered(page)
        assert draft.evaluate(DRAFT_AS_DRAWN, words)["Tables"] == editing["Tables"]
        # A press on the picture opens its source and leaves the picture drawn after it.
        page.mouse.click(
            box["x"] + editing["picture"][0] + 20, box["y"] + editing["picture"][1] + 20
        )
        rendered(page)
        opened = draft.evaluate(DRAFT_AS_DRAWN, words)
        assert opened["picture"][2:] == editing["picture"][2:], (opened, editing)
        assert opened["picture"][1] > editing["picture"][1]
        # The caret in a table's cell shows its `|`s and delimiter row where they stand,
        # moving no word of the table or after it, once the picture's source it leaves
        # goes.
        draft.evaluate(
            "(draft, y) => scrollBy(0, draft.getBoundingClientRect().top + y - 200)",
            opened["Annex"][1],
        )
        box = draft.bounding_box()
        page.mouse.click(
            box["x"] + opened["Annex"][0] + 2, box["y"] + opened["Annex"][1] + 5
        )
        expect(draft.locator("leaf-text")).to_be_focused()
        rendered(page)
        assert draft.evaluate(
            "draft => window.marginEditorRoots.get(draft.querySelector('leaf-text'))"
            ".querySelectorAll('.lf-md-pipe.lf-md-mark').length"
        ), "the caret in a cell shows the table's pipes"
        in_table = draft.evaluate(DRAFT_AS_DRAWN, words)
        for word in ("Chairs", "hall", "Annex", "Tables"):
            assert in_table[word] == editing[word], (word, in_table, editing)
        # A paragraph typed after the last one starts on the line it will stand on, the
        # blank line before it already standing as the gap.
        last_line = """draft => [...window.marginEditorRoots.get(draft.querySelector('leaf-text'))
          .querySelectorAll('.cm-line')].at(-1).getBoundingClientRect().top"""
        page.keyboard.press("ControlOrMeta+End")
        page.keyboard.press("Enter")
        page.keyboard.press("Enter")
        rendered(page)
        before = draft.evaluate(last_line)
        page.keyboard.type("N")
        rendered(page)
        assert draft.evaluate(last_line) == pytest.approx(before, abs=0.5)
        page.keyboard.press("Escape")

    with subtests.test("a picture a reference names"):
        # It is drawn from the reference, with its words; one whose source spans lines
        # stays source.
        draft_control(page, "edit", "named").click()
        named = page.locator("#named leaf-text")
        expect(named).to_be_focused()
        rendered(page)
        pictures = named.evaluate("""field => [...window.marginEditorRoots.get(field)
          .querySelectorAll('img.lf-md-picture')].map(img => [img.getAttribute('src'), img.alt])""")
        assert (
            len(pictures) == 1 and pictures[0][0] and pictures[0][1] == "Room layout"
        ), pictures
        page.keyboard.press("Escape")

    with subtests.test("a draft a file wrapped"):
        draft = page.locator("#wrapped")
        expect(draft.locator(".lf-draft-body blockquote")).to_be_visible()
        expect(draft.locator(".lf-draft-body br")).to_have_count(0)
        words = ["alpha", "stands", "delta", "bravo", "marker", "charlie", "hidden"]
        shown = draft.evaluate(DRAFT_AS_DRAWN, words)
        draft_control(page, "edit", "wrapped").click()
        expect(draft.locator("leaf-text")).to_be_focused()
        rendered(page)
        editing = draft.evaluate(DRAFT_AS_DRAWN, words)
        for word in words:
            assert editing[word] == pytest.approx(shown[word], abs=1), (
                word,
                shown,
                editing,
            )


# Wrapped for an editor wider than the draft, as a passage copied from a hard-wrapped
# file is: a paragraph, a list item and a quote, each across two source lines.
WRAPPED = """A paragraph a file wraps for a wider editor than this box reads here as one, its line
alpha break a space, so each word after one stands where the prose puts it, in `a code
delta span` too.

- An item wrapped the same way keeps its words in the item's column after its line
  bravo break, and its marker where the list draws it.

> A quoted passage wrapped across two of its source lines joins as well, the quote's
> charlie marker hidden with the break before it."""


def test_a_draft_shows_each_blank_line_and_saves_one_per_gap(browser, serve):
    """Return between two paragraphs drew nothing until a word was typed, so the user
    pressed it again and wrote blank lines the prose dropped, and the draft then opened
    with its words moved. Each Return shows a line, a word typed after one stands where it
    will stand, and saving writes each run of blank lines between two blocks as the one
    gap the prose draws, so the draft reopens where it read; a code block keeps its
    blank lines. A draft written with a run, opened and saved untouched, records no
    edit."""
    url = serve(
        leaf_page(
            "Blank lines",
            '<h1>Blank lines</h1><lf-draft id="typed"><pre>Alpha.\n\nBravo.</pre></lf-draft>'
            '<lf-draft id="written"><pre>Alpha.\n\n\n\nBravo.</pre></lf-draft>',
        )
    )
    page = open_page(browser, url, init_script=MARGIN_EDITOR_ROOTS)
    draft = page.locator("#typed")
    editor = draft.locator("leaf-text")
    words = ["Alpha", "Bravo", "Charlie", "two"]
    draft_control(page, "edit", "typed").click()
    expect(editor).to_be_focused()
    rendered(page)
    opened = draft.evaluate(DRAFT_AS_DRAWN, words)
    editor.evaluate("field => field.setSelectionRange(6, 6)")
    editor.press("Enter")
    rendered(page)
    returned = draft.evaluate(DRAFT_AS_DRAWN, words)
    assert returned["Bravo"][1] > opened["Bravo"][1] + opened["Alpha"][3] / 2, (
        opened,
        returned,
    )
    page.keyboard.insert_text("Charlie.")
    rendered(page)
    typed = draft.evaluate(DRAFT_AS_DRAWN, words)
    assert typed["Bravo"][1] == pytest.approx(returned["Bravo"][1], abs=1), (
        returned,
        typed,
    )
    expect(editor).to_have_js_property("value", "Alpha.\n\nCharlie.\n\nBravo.")
    source = "Alpha.\n\n\n\nBravo.\n\n```\none\n\n\ntwo\n```"
    write(editor, source)
    press_draft_control(page, "save", "typed")
    round_trip(page)
    expect(editor).to_have_count(0)
    shown = draft.evaluate(DRAFT_AS_DRAWN, words)
    draft_control(page, "edit", "typed").click()
    expect(editor).to_be_focused()
    rendered(page)
    expect(editor).to_have_js_property(
        "value", "Alpha.\n\nBravo.\n\n```\none\n\n\ntwo\n```"
    )
    reopened = draft.evaluate(DRAFT_AS_DRAWN, words)
    for word in ["Alpha", "Bravo", "two"]:
        assert reopened[word] == pytest.approx(shown[word], abs=1), (shown, reopened)
    page.keyboard.press("Escape")
    draft_control(page, "edit", "written").click()
    expect(page.locator("#written leaf-text")).to_be_focused()
    press_draft_control(page, "save", "written")
    expect(page.locator("#written leaf-text")).to_have_count(0)
    edits = [
        event["detail"]["value"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert edits == ["Alpha.\n\nBravo.\n\n```\none\n\n\ntwo\n```"]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_arrow_keys_visit_every_blank_line_of_a_draft(engine, request, serve):
    """Up from a draft's last line visits every line on the way to its first. A blank
    line standing as the gap the prose leaves between two blocks can stand shorter
    than CodeMirror's vertical motion aims past, so the arrows skipped it."""
    source = "Alpha\n\nBravo\n\n\nCharlie\n\n\n\nDelta"
    url = serve(
        leaf_page(
            "Draft gaps",
            f'<h1>Draft gaps</h1><lf-draft id="gaps"><pre>{source}</pre></lf-draft>',
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    draft_control(page, "edit", "gaps").click()
    field = page.locator("#gaps leaf-text")
    expect(field).to_be_focused()
    rendered(page)
    page.keyboard.press("ControlOrMeta+End")
    last = source.count("\n")
    visited = []
    for _ in range(last):
        page.keyboard.press("ArrowUp")
        visited.append(
            field.evaluate(
                "f => f.value.slice(0, f.selectionStart).split('\\n').length - 1"
            )
        )
    assert visited == list(range(last - 1, -1, -1))


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_keys_at_the_edge_of_a_draft_s_words_act_on_what_it_shows(
    engine, request, serve
):
    """Home on a heading went before its hidden `# `, so typed words made the heading a
    paragraph; a double press on a bold first word selected the `**` the first press
    revealed beside it; two pasted paragraphs left the quote they were pasted into;
    and words typed in the gap between two paragraphs joined both. Each of these keys
    and gestures acts on the blocks the draft shows instead."""
    url = serve(
        leaf_page(
            "Keys at the edge",
            "<h1>Keys at the edge</h1>"
            '<lf-draft id="heading"><pre># Title here\n\nBody.</pre></lf-draft>'
            '<lf-draft id="bold"><pre>Some **bold words** here.</pre></lf-draft>'
            '<lf-draft id="quote"><pre>Before.\n\n&gt; Quoted here.\n\nAfter.</pre></lf-draft>'
            '<lf-draft id="gap"><pre>Alpha one two.\n\nBravo three four.</pre></lf-draft>',
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 900, "height": 1000})

    draft_control(page, "edit", "heading").click()
    editor = page.locator("#heading leaf-text")
    expect(editor).to_be_focused()
    editor.evaluate("field => field.setSelectionRange(6, 6)")
    page.keyboard.press("Home")
    page.keyboard.insert_text("My ")
    expect(editor).to_have_js_property("value", "# My Title here\n\nBody.")
    page.keyboard.press("Escape")

    spot = word_point(page.locator("#bold .lf-draft-body"), "bold")
    page.mouse.dblclick(spot["x"], spot["y"])
    editor = page.locator("#bold leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.insert_text("Big")
    expect(editor).to_have_js_property("value", "Some **Big words** here.")
    page.keyboard.press("Escape")

    page.evaluate(
        """text => { const scratch = document.createElement('textarea');
        scratch.id = 'scratch'; scratch.value = text; document.body.append(scratch);
        scratch.focus(); scratch.select(); }""",
        "First.\n\nSecond.",
    )
    page.keyboard.press("ControlOrMeta+c")
    page.evaluate("() => document.getElementById('scratch').remove()")
    draft_control(page, "edit", "quote").click()
    editor = page.locator("#quote leaf-text")
    expect(editor).to_be_focused()
    editor.evaluate("field => field.setSelectionRange(23, 23)")
    page.keyboard.press("ControlOrMeta+v")
    expect(editor).to_have_js_property(
        "value", "Before.\n\n> Quoted here.First.\n> \n> Second.\n\nAfter."
    )
    page.keyboard.press("Escape")

    paragraphs = page.locator("#gap .lf-draft-body p")
    above, below = paragraphs.nth(0).bounding_box(), paragraphs.nth(1).bounding_box()
    draft_control(page, "edit", "gap").click()
    editor = page.locator("#gap leaf-text")
    expect(editor).to_be_focused()
    rendered(page)
    page.mouse.click(above["x"] + 60, (above["y"] + above["height"] + below["y"]) / 2)
    page.keyboard.type("Zed")
    expect(editor).to_have_js_property(
        "value", "Alpha one two.\n\nZed\n\nBravo three four."
    )


def test_a_draft_uses_shared_editing_and_saves_exact_markdown_source(browser, serve):
    """Formatted reading retains exact Markdown through caret placement and editing, at
    a phone's width, where the formatted words wrap most."""
    text = (
        "A **bold invitation**, `literal code`, and [a link](https://example.com). " * 3
    ).strip()
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft source",
                f'<h1>Draft source</h1><lf-draft id="source"><pre>{text}</pre></lf-draft>'
                '<lf-sample id="quoted"><lf-draft id="exhibit"><pre>Read-only source.</pre></lf-draft></lf-sample>',
            )
        ),
    )
    resized(page, 390, 844)
    draft = page.locator("#source")
    point = draft.locator(".lf-draft-body").evaluate("""body => {
      const node=body.querySelector('code').firstChild;
      const r=new Range();r.setStart(node,3);r.setEnd(node,4);
      const b=r.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2];
    }""")
    expect(draft.locator(".lf-draft-body strong")).to_have_count(3)
    expect(draft.locator(".lf-draft-body code")).to_have_count(3)
    expect(draft.locator(".lf-draft-body a[href='https://example.com']")).to_have_count(
        3
    )
    page.mouse.click(point[0], point[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    # Named as the rest of the chrome names it, never by its id: nothing holding this
    # draft has a name, so by its word.
    expect(editor).to_have_attribute("aria-label", "Edit the draft")
    caret = editor.evaluate("el=>el.selectionStart")
    at = text.index("literal code")
    assert at <= caret <= at + len("literal code")
    page.keyboard.insert_text("changed ")
    expect(editor).to_have_js_property(
        "value", text[:caret] + "changed " + text[caret:]
    )
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_have_js_property("value", text)
    write(editor, "Discard **this**.")
    press_draft_control(page, "cancel", "source")
    expect(draft.locator(".lf-draft-body strong")).to_have_count(3)
    draft_control(page, "edit", "source").click()
    expect(editor).to_have_js_property("value", text)
    saved = "Keep **this** and `that` exactly.\nA second line."
    write(editor, saved)
    press_draft_control(page, "save", "source")
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body strong")).to_have_text("this")
    expect(draft.locator(".lf-draft-body code")).to_have_text("that")
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep this and that exactly. A second line.", use_inner_text=True
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [saved]
    page.locator("#exhibit .lf-draft-body").click()
    expect(page.locator("#exhibit leaf-text")).to_have_count(0)
    expect(page.locator("#exhibit .lf-draft-body")).to_have_text("Read-only source.")


def test_a_press_away_from_an_open_draft_saves_it(browser, serve):
    """On a phone the user types into a draft and taps elsewhere, expecting it kept, as
    a form keeps what was typed. A press away from the open draft saves it as Save does,
    and the edit names the draft as the chrome does, by its holder's heading here, not
    by its id. A press on the draft's own Discard stays a discard."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft notes",
                '<h1>Draft notes</h1><section id="landing"><h2>Landing the branches</h2>'
                '<lf-draft id="q9-note"><pre>\n</pre></lf-draft></section>'
                '<p id="elsewhere">Something else on the page.</p>',
            )
        ),
    )
    resized(page, 390, 844)
    draft = page.locator("#q9-note")
    draft.click()
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Only the pointer one.")
    press_draft_control(page, "cancel", "q9-note")
    expect(editor).to_have_count(0)
    draft.click()
    write(editor, "Land the pointer branch first.")
    page.locator("#elsewhere").click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Land the pointer branch first.", use_inner_text=True
    )
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [
        "Land the pointer branch first."
    ]
    expect(page.locator(".lf-live")).to_have_text("Edited “Landing the branches”")


def test_a_rendered_continuation_click_edits_the_exact_source_position(browser, serve):
    """Parser-expanded indentation keeps the native pointer's source coordinate."""
    sources = ["- first\n\tcontinued **target**", "1. first\n\tcontinued **target**"]
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Continuation carets",
                "<h1>Continuation carets</h1>"
                + "".join(
                    f'<lf-draft id="continuation-{i}"><pre>{source}</pre></lf-draft>'
                    for i, source in enumerate(sources)
                ),
            )
        ),
    )
    for i, source in enumerate(sources):
        draft = page.locator(f"#continuation-{i}")
        point = draft.locator(".lf-draft-body strong").evaluate("""strong => {
          const node=strong.firstChild, range=new Range();
          range.setStart(node,2);range.setEnd(node,3);
          const box=range.getBoundingClientRect(),x=box.x+0.01,y=box.y+box.height/2;
          return {x,y,offset:document.caretPositionFromPoint(x,y).offset};
        }""")
        page.mouse.click(point["x"], point["y"])
        editor = draft.locator("leaf-text")
        expect(editor).to_be_focused()
        at = source.index("target") + point["offset"]
        expect(editor).to_have_js_property("selectionStart", at)
        page.keyboard.insert_text("here")
        expect(editor).to_have_js_property("value", source[:at] + "here" + source[at:])
        press_draft_control(page, "cancel", f"continuation-{i}")


def test_a_click_on_a_reply_s_draft_opens_it_in_the_panel(browser, serve):
    """A draft an agent sends in a reply opens at a click on its words in the panel's
    thread, as one on the page does. The message the reader draws it in is Leaf's own
    surface, marked as generated chrome, and a draft that took that mark for a press
    of its own would leave the click to it, so only its ✎ would open it."""
    url = serve(leaf_page("Reply draft", "<h1>Reply draft</h1>"))
    question = panel_comment(serve.page_dir, "Could you draft the note?")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(serve.page_dir, question),
            "--title",
            "Note draft",
            "--text",
            "Here it is:"
            + "\n\n"
            + ('<lf-draft id="reply-draft">\n<pre>The note to send.</pre></lf-draft>'),
        ],
    )
    assert replied.exit_code == 0, replied.output
    page = open_page(browser, url)
    draft = open_panel_thread(page, question).locator("lf-draft")
    draft.locator(".lf-draft-body").get_by_text("The note to send.").click()
    expect(draft.locator("leaf-text")).to_be_focused()


def test_a_draft_in_an_obligation_takes_no_digits_and_answers_from_its_controls(
    browser, serve
):
    """A draft lends its obligation no digits, so a digit typed while focused on the obligation
    or in the editor is not a command; the user Tabs to Edit and saves with
    Mod+Enter. Edit shows before the pointer or a key reaches the box, since it is the
    way to answer."""
    original = "Keep **this** source editable."
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft in an Ask",
                '<h1>Release note</h1><lf-group id="note-decision" label="How should the note read?">'
                '<h2 id="note-decision-h">How should the note read?</h2>'
                f'<lf-draft id="note" required><pre>{original}</pre></lf-draft></lf-group>',
            )
        ),
    )
    question = page.locator("#note-decision")
    editor = page.locator("#note leaf-text")
    edit = draft_control(page, "edit", "note")
    expect(page.locator("#note .lf-draft-tools")).to_have_css("opacity", "1")

    page.keyboard.press("m")
    expect(question).to_be_focused()
    expect(edit).not_to_have_attribute("aria-keyshortcuts", re.compile(r"\d"))
    page.keyboard.press("1")
    rendered(page)
    expect(editor).to_have_count(0)
    page.keyboard.press("Tab")
    expect(edit).to_be_focused()
    page.keyboard.press("Enter")
    expect(editor).to_be_focused()
    write(editor, "Keep **these** digits: ")
    page.keyboard.type("12")
    saved = "Keep **these** digits: 12"
    expect(editor).to_have_js_property("value", saved)
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(page.locator("#note .lf-draft-body")).to_have_text("Keep these digits: 12")
    edits = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert [event["detail"]["value"] for event in edits] == [saved]


def test_typing_puts_the_toolbar_away_until_the_pointer_comes_to_it(browser, serve):
    """The toolbar stands over the first line's last words, so typing puts it away at
    once, the pointer resting where it opened the editor or not, and the pointer coming
    to it brings it back. Put away, it takes no press: a press that hasn't moved
    places the caret in the words rather than pressing a Discard the user can't see, and
    the toolbar takes presses again once the pointer rests on it or Tab reaches it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Draft toolbar",
                '<h1>Release note</h1><lf-group id="note-decision" label="How should the note read?">'
                '<h2 id="note-decision-h">How should the note read?</h2>'
                '<lf-draft id="note" required><pre>Keep this source editable.</pre></lf-draft></lf-group>',
            )
        ),
    )
    tools = page.locator("#note .lf-draft-tools")
    editor = page.locator("#note leaf-text")
    page.locator("#note .lf-draft-body").click()
    expect(editor).to_be_focused()
    expect(tools).to_have_css("opacity", "1")
    box = draft_control(page, "save", "note").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.keyboard.type(" Now")
    expect(tools).to_have_css("opacity", "0")
    page.mouse.down()
    page.mouse.up()
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Keep this source editable. Now")
    # A move over the words leaves it away; the pointer coming to it brings it back.
    words = page.locator("#note").bounding_box()
    page.mouse.move(words["x"] + 30, words["y"] + words["height"] / 2)
    assert tools.evaluate("el => getComputedStyle(el).opacity") == "0"
    page.mouse.move(box["x"] + box["width"] / 2 + 2, box["y"] + box["height"] / 2)
    expect(tools).to_have_css("opacity", "1")
    expect(tools).to_have_css("pointer-events", "auto")

    page.keyboard.type(" Then")
    expect(tools).to_have_css("opacity", "0")
    page.keyboard.press("Tab")
    expect(draft_control(page, "save", "note")).to_be_focused()
    expect(tools).to_have_css("opacity", "1")
    expect(tools).to_have_css("pointer-events", "auto")


def test_the_draft_box_is_its_own_door(browser, serve):
    """A draft is the one block on a page whose whole purpose is that the user rewrites
    it, which a pencil in the margin says only from beside it, and a block that ignored
    a press would leave a double-click, which is a thing you have to already know, as
    the gesture that opens it in place.

    So the box is the door, and the caret lands where the press did. Which is a door that
    has to be opened carefully, because the same words are the page's words: a user
    drawing across them to quote them ends that drag with a mouseup inside the box, and
    opening on it would throw the selection away at the moment it was finished. That is
    the question Leaf answers for every other press on the page's own words, asked here
    through `aimedAt` rather than answered again. The drag runs through the harness's own
    `hold_selection`, which floors the press - a fractional start point loses the
    selection outright, and an empty one would read exactly like the door swallowing it -
    and the words are read while the drag is still held, because the runtime re-seats the
    selection on a timer after the release and a read in that gap comes back empty.

    And the door is exactly the box - not the chrome inside it. `offer` writes its marker
    on everything a widget builds, controls row and edit box included, and only names a
    kind for the things to press; the guard reads that, so a press on the row does not
    reopen the editor and the row does not wear a hand it has no use for."""
    page = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    body = draft.locator(".lf-draft-body")
    expect(body).to_have_text(DRAFT_DRAWN, use_inner_text=True)

    # A drag across the words takes the words. Read as the selection the user is left
    # holding, which is the thing the door would have destroyed.
    box = body.bounding_box()
    line = box["y"] + 8
    # Keep the release over the draft's words. The box's far edge lies beside the
    # text and makes the browser end the selection in the following page content.
    hold_selection(
        page, (box["x"] + 2, line), (box["x"] + min(150, box["width"] / 2), line)
    )
    held = page.evaluate("() => getSelection().toString()")
    assert held.strip() != "", (
        f"the drag selected nothing, so this says nothing about the door: {held!r}"
    )
    page.mouse.up()
    expect(draft.locator("leaf-text")).to_have_count(0)

    # A press opens it, with the caret where the press landed rather than at the top.
    page.evaluate("() => getSelection().removeAllRanges()")
    at = page.evaluate(
        """(word) => {
            const node = document.createTreeWalker(
              document.querySelector('#draft-ops .lf-draft-body'),
              NodeFilter.SHOW_TEXT).nextNode();
            const start = node.data.indexOf(word);
            const range = document.createRange();
            range.setStart(node, start); range.setEnd(node, start + word.length);
            const r = range.getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2, start, word.length];
        }""",
        "migration",
    )
    page.mouse.click(at[0], at[1])
    editor = draft.locator("leaf-text")
    expect(editor).to_be_focused()
    caret = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops leaf-text');"
        "        return [t.selectionStart, t.selectionEnd]; }"
    )
    assert caret[0] == caret[1], (
        f"one press selected a range rather than placing a caret: {caret}"
    )
    assert at[2] <= caret[0] <= at[2] + at[3], (
        f"the box opened with the caret at {caret[0]}, not in the word pressed "
        f"({at[2]}..{at[2] + at[3]})"
    )

    # The chrome inside the box is not the door, and does not dress as one. The controls
    # row and the edit box are both things `offer` built and neither names a kind.
    inside = page.evaluate(
        """() => [...document.querySelectorAll('#draft-ops [data-lf-offer=""]')]
             .filter(el => !el.closest("button"))
        .map((el) => [el.localName, getComputedStyle(el).cursor])"""
    )
    assert inside, "the draft built no generated chrome, so this proves nothing"
    assert all(cursor != "pointer" for _tag, cursor in inside), (
        f"generated chrome inside the draft dresses as a press: {inside}"
    )

    # And the pencil is still there, still the keyboard's way in.
    page.keyboard.press("Escape")
    pencil = draft_control(page, "edit", "draft-ops")
    expect(pencil).to_be_focused()
    pencil.click()
    expect(draft.locator("leaf-text")).to_be_visible()


def test_a_refused_save_from_a_press_away_leaves_the_focus_where_it_went(
    browser, serve
):
    """The user leaves one draft by pressing Edit on the next, which saves the first.
    When that save is refused, the first reopens with Retry, and the user keeps typing
    in the second rather than having the focus pulled back."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Two drafts",
                "<h1>Two drafts</h1>"
                '<lf-draft id="rn-cli"><pre>CLI notes.</pre></lf-draft>'
                '<lf-draft id="rn-api"><pre>API notes.</pre></lf-draft>',
            )
        ),
    )
    first, second = page.locator("#rn-cli"), page.locator("#rn-api")
    draft_control(page, "edit", "rn-cli").click()
    write(first.locator("leaf-text"), "Changed CLI notes.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft_control(page, "edit", "rn-api").click()
    holding(page, held, 1, "the first draft's save on a press away")
    expect(second.locator("leaf-text")).to_be_focused()
    held[0].fulfill(status=400, json={"ok": False, "final": True, "error": "refused"})
    expect(draft_control(page, "retry", "rn-cli")).to_have_accessible_name(
        re.compile(r"\bRetry\b")
    )
    expect(second.locator("leaf-text")).to_be_focused()
    consume_browser_errors(page, http_error_console(400))


def test_first_draft_save_and_refusal_keep_the_local_editor_controls(browser, serve):
    """A failed first save retains exact source and usable controls without empty history."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "First draft refusal",
                "<h1>First draft refusal</h1>"
                '<lf-draft id="first-draft"><pre>Original words.</pre></lf-draft>'
                '<p id="following">The following passage stays where the reader found it.</p>',
            )
        ),
    )
    draft = page.locator("#first-draft")
    draft_control(page, "edit", "first-draft").click()
    write(draft.locator("leaf-text"), "Changed words.")
    # The open editor defers the draft's own drawing, which is no hold of the user's
    # on the page.
    assert not page.evaluate("async () => (await window.__lfCheckApi()).dragHeld()")
    before = page.locator("#following").bounding_box()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    press_draft_control(page, "save", "first-draft")
    holding(page, held, 1, "the refused first draft Save")
    expect(draft.locator(".lf-draft-body")).to_have_text("Changed words.")
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused first edit"}
    )
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Changed words.")
    expect(draft.locator(".lf-draft-body")).to_have_text("Original words.")
    expect(draft_control(page, "retry", "first-draft")).to_have_accessible_name(
        re.compile(r"\bRetry\b")
    )
    expect(draft_control(page, "cancel", "first-draft")).to_be_visible()
    assert page.locator("#following").bounding_box() == before
    consume_browser_errors(page, http_error_console(400))


def test_draft_controls_survive_hiding_annotations_and_escape_discards(browser, serve):
    """Editing operations stay in their box while the annotation layer is hidden.

    The toolbar offers Save and Discard, and Escape discards as the button does, so a
    closed box holds no unsent words. The box's Copy control copies the Markdown source
    the box shows, the open editor's while it stands."""
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Local draft controls",
                "<h1>Local draft controls</h1>"
                '<lf-draft id="local"><pre>Saved **source**.</pre></lf-draft>',
            )
        ),
        context=context,
    )
    draft = page.locator("#local")
    # Hidden before the box opens: Go-to doesn't arm over a box that claims Escape.
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )
    edit = draft_control(page, "edit", "local")
    edit.click()
    editor = draft.locator("leaf-text")
    write(editor, "Unsent `source`.")
    page.keyboard.press("Tab")
    expect(draft_control(page, "save", "local")).to_be_focused()
    expect(draft_control(page, "save", "local")).to_be_visible()
    expect(draft_control(page, "cancel", "local")).to_be_visible()
    expect(draft.locator("[data-lf-draft-action]:visible")).to_have_count(2)
    copy = draft.get_by_role("button", name="Copy Markdown")
    copy.click()
    assert page.evaluate("navigator.clipboard.readText()") == "Unsent `source`."
    draft_control(page, "save", "local").focus()
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    expect(edit).to_be_focused()
    edit.press("Enter")
    expect(editor).to_have_js_property("value", "Saved **source**.")
    write(editor, "Changed again.")
    press_draft_control(page, "cancel", "local")
    expect(edit).to_be_focused()
    edit.click()
    expect(editor).to_have_js_property("value", "Saved **source**.")
    page.keyboard.press("Escape")
    copy.click()
    assert page.evaluate("navigator.clipboard.readText()") == "Saved **source**."
    expect(editor).to_have_count(0)


def test_a_discarded_draft_edit_comes_back(browser, serve):
    """A press on Discard can be a stray one, aimed at the words under the toolbar, so
    it loses nothing for good: ⌘Z takes it back as it takes back any gesture of the
    user's, opening the draft again on the discarded words and sending nothing. The
    discard's notice offers that Undo at the panel field's end, and leaves once the
    words are back. After a newer gesture, ⌘Z takes that one back first, then the
    discard. Discarding words the draft already says leaves nothing to take back."""
    url = serve(
        leaf_page(
            "Discarded draft",
            "<h1>Discarded draft</h1>"
            '<lf-draft id="note"><pre>Saved words.</pre></lf-draft>'
            '<lf-draft id="other"><pre>Other words.</pre></lf-draft>',
        )
    )
    page = open_page(browser, url)
    editor = page.locator("#note leaf-text")
    edit = draft_control(page, "edit", "note")
    typed = "Words typed, then thrown away."

    def edits():
        return [
            e["detail"]["value"]
            for e in events_model.read_events(serve.page_dir)
            if e.get("action") == "edit"
        ]

    # By pointer: Discard, then the notice's Undo.
    page.locator("#note .lf-draft-body").click()
    write(editor, typed)
    press_draft_control(page, "cancel", "note")
    expect(editor).to_have_count(0)
    expect(page.locator("#note .lf-draft-body")).to_have_text("Saved words.")
    expect_panel_says(page, "Edit discarded")
    press = field_press(page)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Undo")
    expect(press.locator("kbd")).to_have_text(re.compile(r"^(⌘z|Ctrl\+z)$"))
    press.click()
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", typed)
    # Named as the rest of the chrome names the draft: nothing holding it has a name.
    expect_panel_says(page, "Undone: discarded an edit of the draft")
    expect_panel_says(page, "Edit discarded", says=False)

    # By keyboard: Escape, then ⌘Z from the Edit control it lands on.
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    expect(edit).to_be_focused()
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", typed)
    assert edits() == []

    # A newer gesture takes ⌘Z, so ⌘Z takes that one back first, then the discard.
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    other = page.locator("#other leaf-text")
    draft_control(page, "edit", "other").click()
    write(other, "Other words, saved.")
    with sending(page, "the save"):
        press_draft_control(page, "save", "other")
    expect(page.locator("#other .lf-draft-body")).to_have_text("Other words, saved.")
    edit.focus()
    undo(page)
    expect(page.locator("#other .lf-draft-body")).to_have_text("Other words.")
    expect(editor).to_have_count(0)
    page.keyboard.press("ControlOrMeta+z")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", typed)

    write(editor, "Saved words.")
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    assert "history.undo" not in available_commands(page)


def test_an_open_edit_back_to_the_authored_text_survives_reload(browser, serve):
    """An open editor's words come back on reload whenever they differ from the
    current text, words that walk a saved edit back to the authored text included."""
    url = serve(
        leaf_page(
            "Walk back",
            '<h1>Walk back</h1><lf-draft id="walk"><pre>Authored words.</pre></lf-draft>',
        )
    )
    page = open_page(browser, url)
    draft = page.locator("#walk")
    draft_control(page, "edit", "walk").click()
    write(draft.locator("leaf-text"), "Saved words.")
    press_draft_control(page, "save", "walk")
    round_trip(page)
    draft_control(page, "edit", "walk").click()
    write(draft.locator("leaf-text"), "Authored words.")
    page.reload()
    wait_until_ready(page)
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Authored words.")
    expect(draft.locator(".lf-draft-body")).to_have_text("Saved words.")


@pytest.mark.parametrize("android", [False, True])
def test_document_edit_enter_adds_a_line_and_modified_enter_saves_exact_source(
    browser, serve, android
):
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/155.0.8059.12 Mobile Safari/537.36"
        )
        if android
        else None,
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Markdown source editing",
                "<h1>Markdown source editing</h1>"
                '<lf-draft id="source"><pre>Original **source**.</pre></lf-draft>',
            )
        ),
        context=context,
    )
    draft = page.locator("#source")
    draft_control(page, "edit", "source").click()
    editor = draft.locator("leaf-text")
    write(editor, "First **paragraph**.")
    editor.press("End")
    # After a paragraph's last words, Return begins a new paragraph.
    editor.press("Enter")
    expect(editor).to_have_js_property("value", "First **paragraph**.\n\n")
    page.keyboard.insert_text("Second `paragraph`.")
    # Between its words, Return writes a hard break, which the draft shows as a line,
    # and keeps the space, so Backspace on the new line gives the words back.
    editor.evaluate("field => field.setSelectionRange(29, 29)")
    editor.press("Enter")
    expect(editor).to_have_js_property(
        "value", "First **paragraph**.\n\nSecond \\\n`paragraph`."
    )
    # At a hard break, between its backslash and its line's end, Return begins the
    # line after it.
    editor.evaluate("field => field.setSelectionRange(30, 30)")
    editor.press("Enter")
    exact = "First **paragraph**.\n\nSecond \\\n\\\n`paragraph`."
    expect(editor).to_have_js_property("value", exact)
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    with sending(page, "the exact source edit"):
        editor.press("ControlOrMeta+Enter")
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body > p")).to_have_count(2)
    expect(draft.locator(".lf-draft-body > p br")).to_have_count(2)
    expect(draft.locator(".lf-draft-body strong")).to_have_text("paragraph")
    expect(draft.locator(".lf-draft-body code")).to_have_text("paragraph")
    edits = [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    assert [e["detail"]["value"] for e in edits] == [exact]


def test_return_beside_a_paragraph_leaves_the_caret_where_words_stand_alone(
    browser, serve
):
    """Words on a line touching a paragraph join it, and Return there then writes hard
    breaks, so Return on a blank line or before a paragraph's first words leaves the
    caret with a blank line on each side."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Return beside a paragraph",
                "<h1>Return beside a paragraph</h1>"
                '<lf-draft id="source"><pre>Alpha.</pre></lf-draft>',
            )
        ),
    )
    draft_control(page, "edit", "source").click()
    editor = page.locator("#source leaf-text")
    write(editor, "Alpha.\n\nBravo.")
    # On the one blank line between two paragraphs.
    editor.evaluate("field => field.setSelectionRange(7, 7)")
    editor.press("Enter")
    page.keyboard.insert_text("x")
    expect(editor).to_have_js_property("value", "Alpha.\n\nx\n\nBravo.")
    # Before a paragraph's first words.
    editor.evaluate("field => field.setSelectionRange(11, 11)")
    editor.press("Enter")
    page.keyboard.insert_text("y")
    expect(editor).to_have_js_property("value", "Alpha.\n\nx\n\ny\n\nBravo.")


def test_draft_comparison_detects_format_changes_but_not_the_same_current_edit(
    browser, serve
):
    first = leaf_page(
        "Markdown revision comparison",
        "<h1>Markdown revision comparison</h1>"
        '<lf-draft id="source"><pre>Keep **these** words.</pre></lf-draft>'
        '<p id="following">Following passage.</p>',
    )
    url = serve(first)
    _publish(
        serve.page_dir, 2, first.replace("**these**", "*these*"), "Change emphasis"
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    expect(page.locator("#source")).to_have_class(re.compile(r"lf-ins-block"))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 2,
            "widget": "source",
            "action": "edit",
            "detail": {"value": "Current **edit**."},
            "facts": {"answered": True},
        },
    )
    _publish(
        serve.page_dir,
        3,
        first.replace("**these**", "*these*").replace(
            "Following passage.", "Revised following passage."
        ),
        "Revise following prose",
    )
    page.goto(url.replace("v1.html", "v3.html"))
    wait_until_ready(page)
    compare_with(page)
    expect(page.locator("#following")).to_have_class(re.compile(r"lf-ins-block"))
    expect(page.locator("#source")).not_to_have_class(re.compile(r"lf-ins-block"))
    expect(page.locator("#source .lf-draft-body strong")).to_have_text("edit")


def test_a_finger_s_reach_on_a_draft_copies_past_copy_and_stops_short_of_the_words(
    browser, serve, subtests
):
    """Copy runs on its shadow button's press, so its reach is the button's: under a
    finger, a press just past its face copies. A reach on the host would stand over the
    button and take every press from it.

    Under a finger the toolbar stands on the box's bottom border, and each mark's reach
    half a finger's floor above it. The box's padding keeps that reach off the words, so
    a press at the end of the last line puts the caret there. With less padding, the
    press 3px above the field's foot under Discard would discard the edit."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Finger draft",
                '<h1>Release note</h1><lf-draft id="note"><pre>Keep `this` note.</pre></lf-draft>',
            )
        ),
        context=context,
    )
    with subtests.test("a press on the last line under Discard"):
        draft_control(page, "edit", "note").tap()
        field = page.locator("#note .lf-draft-edit")
        expect(field).to_be_visible()
        discard = draft_control(page, "cancel", "note").bounding_box()
        words = field.bounding_box()
        # A mouse press, which Chrome's touch adjustment doesn't move.
        page.mouse.click(
            discard["x"] + discard["width"] / 2, words["y"] + words["height"] - 3
        )
        expect(field).to_be_focused()
        expect(draft_control(page, "cancel", "note")).to_be_visible()
        page.keyboard.press("Escape")
    with subtests.test("a press just past Copy"):
        copy = page.locator("#note .lf-draft-tools > wa-copy-button")
        copy.evaluate(
            """c => { c.presses = 0;
            for (const t of ['wa-copy', 'wa-error']) c.addEventListener(t, () => c.presses++); }"""
        )
        x, top, bottom = copy.evaluate(
            """c => { const b = c.shadowRoot.querySelector('[part~="button"]')
              .getBoundingClientRect();
            return [b.left + b.width / 2, b.top, b.bottom]; }"""
        )
        assert bottom - top < 44, "the face already meets a finger's floor"
        # A mouse press, which Chrome's touch adjustment doesn't move onto the button.
        page.mouse.click(x, top - 4)
        page.wait_for_function(
            "() => document.querySelector('#note .lf-draft-tools > wa-copy-button')"
            ".presses === 1"
        )
        expect(page.locator("#note .lf-draft-edit")).to_have_count(0)


def test_a_draft_button_keeps_its_target_when_pointerdown_focuses_it(browser, serve):
    """Raw pointer down must not move the button before the matching up arrives. Either
    edge detects a button that moves under the press, so each action, pressed in turn
    on one draft, takes one."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Stable draft",
                '<h1>Release note</h1><lf-draft id="note"><pre>Keep `this` note.</pre></lf-draft>',
            )
        ),
    )
    draft = page.locator("#note")
    # Save keeps its words; cancel discards theirs.
    saved = "Keep this note."
    for action, edge in (
        ("edit", "left"),
        ("save", "right"),
        ("cancel", "left"),
    ):
        if action != "edit":
            draft_control(page, "edit", "note").click()
            write(
                draft.locator("leaf-text"),
                f"Keep `the corrected` note before {action}.",
            )
        # The pointer rests off the box; a press there would save the open draft.
        page.get_by_role("heading", name="Release note").hover()
        rendered(page)
        controls = draft.locator("[data-lf-draft-action]:visible")
        button = draft_control(page, action, "note")
        box = button.bounding_box()
        x = box["x"] + (2 if edge == "left" else box["width"] - 2)
        page.mouse.move(x, box["y"] + box["height"] / 2)
        # Typing put the toolbar away, and it takes presses once the pointer has
        # rested on it (draft.css).
        expect(draft.locator(".lf-draft-tools")).to_have_css("pointer-events", "auto")
        rendered(page)
        before = controls.evaluate_all(
            "ns => ns.map(n=>({action:n.dataset.lfDraftAction,box:n.getBoundingClientRect().toJSON()}))"
        )
        page.mouse.down()
        expect(button).to_be_focused()
        rendered(page)
        assert (
            controls.evaluate_all(
                "ns => ns.map(n=>({action:n.dataset.lfDraftAction,box:n.getBoundingClientRect().toJSON()}))"
            )
            == before
        ), action
        page.mouse.up()
        if action == "edit":
            expect(draft.locator("leaf-text")).to_be_focused()
            page.keyboard.press("Escape")
            expect(draft.locator("leaf-text")).to_have_count(0)
        else:
            expect(draft.locator("leaf-text")).to_have_count(0)
            round_trip(page)
        if action == "save":
            saved = "Keep the corrected note before save."
        expect(draft.locator(".lf-draft-body")).to_have_text(saved)
        round_trip(page)
        edits = [
            e
            for e in events_model.read_events(serve.page_dir)
            if e.get("action") == "edit"
        ]
        assert len(edits) == (0 if saved == "Keep this note." else 1), action


def test_pointer_cancel_returns_draft_room_without_delaying_reading_or_focus(
    browser, serve
):
    from render_cases_interaction import HOLD_MOTION

    page = open_page(
        browser,
        serve(
            leaf_page(
                "Cancel draft",
                '<h1>Review</h1><div style="height:1100px"></div>'
                '<lf-draft id="copy"><pre>Original short text.</pre></lf-draft>'
                '<p id="after">Next section</p>',
            )
        ),
        init_script=HOLD_MOTION,
    )
    page.emulate_media(reduced_motion="no-preference")
    draft = page.locator("#copy")
    rest = draft.bounding_box()["height"]
    draft_control(page, "edit", "copy").click()
    editor = draft.locator("leaf-text")
    editor.focus()
    editor.evaluate("e=>e.select()")
    page.keyboard.insert_text("\n\n".join(["A longer paragraph in the draft."] * 8))
    # The page scrolled until what follows the draft stands at the window's foot.
    page.locator("#after").evaluate("p => p.scrollIntoView({block: 'end'})")
    scroll_settled(page)
    before = draft.bounding_box()["height"]
    scroll_before = page.evaluate("scrollY")
    press_draft_control(page, "cancel", "copy")
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("Original short text.")
    expect(draft_control(page, "edit", "copy")).to_be_focused()
    assert draft.bounding_box()["height"] == pytest.approx(before, abs=1)
    assert page.evaluate("scrollY") == pytest.approx(scroll_before, abs=1)
    draft.evaluate("d=>d.getAnimations()[0].currentTime=90")
    middle = draft.bounding_box()["height"]
    assert rest < middle < before
    draft_control(page, "edit", "copy").click()
    expect(editor).to_be_focused()
    assert draft.evaluate("d=>d.getAnimations().length") == 0
    page.keyboard.insert_text("\n" * 8)
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    assert draft.evaluate("d=>d.getAnimations().length") == 0
    page.emulate_media(reduced_motion="reduce")
    draft_control(page, "edit", "copy").click()
    page.keyboard.insert_text("\n" * 8)
    press_draft_control(page, "cancel", "copy")
    assert draft.evaluate("d=>d.getAnimations().length") == 0
