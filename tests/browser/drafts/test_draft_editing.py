"""Editing an lf-draft in place: opening it, caret and selection, exact Markdown source,
saving and its controls, Enter, and comparing versions."""

import re
import shutil

import pytest
from click.testing import CliRunner
from interact_support import append_command, response_reference
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_cases_navigation import DRAFT_TEXT, JOURNEY_V1, _publish
from render_harness import (
    compare_with,
    consume_browser_errors,
    draft_control,
    example_media,
    hold_selection,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    resized,
    round_trip,
    scroll_settled,
    sending,
    write,
)

from browser.margin import MARGIN_EDITOR_ROOTS
from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

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
    # box's edge. A pixel count is a fact about one font: 60px into this line was
    # "migration" while the theme set drafts in 16px system-ui, and lands in "the"
    # now that it sets them in 17px Charter — so the test read as "the editor opens
    # on the wrong word" when nothing about the gesture had changed.
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
    assert page.locator("#draft-ops").inner_text() == DRAFT_TEXT, (
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
    page.locator("#long-draft").evaluate(
        """el => {
          const box = el.closest('lf-pane') ? el : document.scrollingElement;
          box.scrollTop = 600;
        }"""
    )
    scroll_settled(page)
    point = page.locator("#long-draft .lf-draft-body").evaluate(
        """el => {
          const word = 'Line 30:', walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode()) && !node.data.includes(word)) {}
          const at = node.data.indexOf(word), range = document.createRange();
          range.setStart(node, at + 3); range.setEnd(node, at + 4);
          const b = range.getBoundingClientRect();
          return [b.x + b.width / 2, b.y + b.height / 2];
        }"""
    )
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


Two blank lines stand before these words.

- one **bold** item
- a second with `inline`

```
leaf page init ./workshop
```

> ### Quoted
>
> Practice beats theory.
>

## Heading two

![Room layout](/media/051bee487bfb5d13.png)

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
  const editor = draft.querySelector(':scope > leaf-text');
  const root = editor ? window.marginEditorRoots.get(editor) : draft.querySelector('.lf-draft-body');
  const at = (node) => {
    const r = node.getBoundingClientRect();
    return [Math.round(r.left - box.left), Math.round(r.top - box.top), Math.round(r.width), Math.round(r.height)];
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
  found.height = Math.round(box.height);
  return found;
}"""


def test_a_draft_edits_where_it_reads(browser, serve):
    """A draft's editor drew its Markdown in a sent message's face: a heading at the
    words' size, a blank line for each gap between blocks, a picture as its source, a
    fence's lines at a code line each and no mark after a link that leaves the page.
    Opening a draft holding them moved the words below its first block. The words and
    picture now stay where the prose showed them, the editor taking each block's face
    and gaps from where it stands."""
    url = serve(
        leaf_page(
            "Draft faces",
            f'<h1>Draft faces</h1><lf-draft id="faces"><pre>{DRAFT_BLOCKS}</pre></lf-draft>'
            f'<lf-draft id="named"><pre>{NAMED_PICTURES}</pre></lf-draft>',
        )
    )
    (serve.page_dir / "media").mkdir(exist_ok=True)
    shutil.copy(
        example_media() / "051bee487bfb5d13.png",
        serve.page_dir / "media" / "051bee487bfb5d13.png",
    )
    page = open_page(browser, url, init_script=MARGIN_EDITOR_ROOTS)
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
        "Quoted",
        "Practice",
        "Heading",
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
    for part, place in shown.items():
        assert editing[part] == pytest.approx(place, abs=1), (part, shown, editing)
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
    # A picture a reference names is drawn from the reference, with its words; one
    # whose source spans lines stays source.
    page.keyboard.press("Escape")
    draft_control(page, "edit", "named").click()
    named = page.locator("#named leaf-text")
    expect(named).to_be_focused()
    rendered(page)
    pictures = named.evaluate("""field => [...window.marginEditorRoots.get(field)
      .querySelectorAll('img.lf-md-picture')].map(img => [img.getAttribute('src'), img.alt])""")
    assert len(pictures) == 1 and pictures[0][0] and pictures[0][1] == "Room layout", (
        pictures
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


def test_a_wrapped_draft_reads_and_edits_as_one_paragraph(browser, serve):
    """A draft drew a line break at each of its source's, so one wrapped for a wider
    editor showed a short line after each long one. It reads as a Markdown file now,
    a line break inside a paragraph a space, and its editor joins those lines too, so
    each word stays where the prose showed it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Wrapped draft",
                f'<h1>Wrapped draft</h1><lf-draft id="wrapped"><pre>{WRAPPED}</pre></lf-draft>',
            )
        ),
        init_script=MARGIN_EDITOR_ROOTS,
    )
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_arrow_keys_visit_every_blank_line_of_a_draft(engine, request, serve):
    """Up from a draft's last line visits every line on the way to its first. Blank
    lines that share the gap the prose leaves between two blocks each stand shorter
    than CodeMirror's vertical motion aims past, so the arrows skipped them."""
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
    draft_control(page, "cancel", "source").click()
    expect(draft.locator(".lf-draft-body strong")).to_have_count(3)
    draft_control(page, "edit", "source").click()
    expect(editor).to_have_js_property("value", text)
    saved = "Keep **this** and `that` exactly.\nA second line."
    write(editor, saved)
    draft_control(page, "save", "source").click()
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
    draft_control(page, "cancel", "q9-note").click()
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
        draft_control(page, "cancel", f"continuation-{i}").click()


def test_a_click_on_a_reply_s_draft_opens_it_in_the_panel(browser, serve):
    """A draft an agent sends in a reply opens at a click on its words in the panel's
    thread, as one on the page does. The message the reader draws it in is Leaf's own
    surface, marked as generated chrome, and the draft once took that mark for a press
    of its own and left the click to it, so only its ✎ opened it."""
    url = serve(leaf_page("Reply draft", "<h1>Reply draft</h1>"))
    question = panel_comment(serve.page_dir, "Could you draft the note?")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(serve.page_dir, question),
            "--text",
            "Here it is:",
            "--markup",
            '<lf-draft id="reply-draft"><pre>The note to send.</pre></lf-draft>',
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
                '<h1>Release note</h1><lf-ask id="note-decision">'
                "<h2>How should the note read?</h2>"
                f'<lf-draft id="note" needed><pre>{original}</pre></lf-draft></lf-ask>',
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


def test_the_draft_box_is_its_own_door(browser, serve):
    """A draft is the one block on a page whose whole purpose is that the user rewrites
    it, and until now the only thing that said so was a pencil in the margin 45px away.
    The block itself ignored a press. The gesture that did open it in place was a
    double-click, which is a thing you have to already know.

    So the box is the door, and the caret lands where the press did. Which is a door that
    has to be opened carefully, because the same words are the page's words: a user
    drawing across them to quote them ends that drag with a mouseup inside the box, and
    opening on it would throw the selection away at the moment it was finished. That is
    the question `reachedForWords` answers for every other press on the page's own words,
    asked here rather than answered again. The drag runs through the harness's own
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
    expect(body).to_have_text(DRAFT_TEXT, use_inner_text=True)

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
    expect(draft_control(page, "retry", "rn-cli")).to_be_visible()
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
    before = page.locator("#following").bounding_box()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft_control(page, "save", "first-draft").click()
    holding(page, held, 1, "the refused first draft Save")
    expect(draft.locator(".lf-draft-body")).to_have_text("Changed words.")
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused first edit"}
    )
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Changed words.")
    expect(draft.locator(".lf-draft-body")).to_have_text("Original words.")
    expect(draft_control(page, "retry", "first-draft")).to_be_visible()
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
    edit = draft_control(page, "edit", "local")
    edit.click()
    editor = draft.locator("leaf-text")
    write(editor, "Unsent `source`.")
    page.keyboard.press("Tab")
    expect(draft_control(page, "save", "local")).to_be_focused()
    page.keyboard.press("o")
    expect(page.locator("html")).to_have_attribute("data-lf-annotations", "hidden")
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
    draft_control(page, "cancel", "local").click()
    expect(edit).to_be_focused()
    edit.click()
    expect(editor).to_have_js_property("value", "Saved **source**.")
    page.keyboard.press("Escape")
    copy.click()
    assert page.evaluate("navigator.clipboard.readText()") == "Saved **source**."


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
    draft_control(page, "save", "walk").click()
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
    # Between its words, Return writes a hard break in place of the space, which the
    # draft shows as a line.
    editor.evaluate("field => field.setSelectionRange(29, 29)")
    editor.press("Enter")
    exact = "First **paragraph**.\n\nSecond\\\n`paragraph`."
    expect(editor).to_have_js_property("value", exact)
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    with sending(page, "the exact source edit"):
        editor.press("ControlOrMeta+Enter")
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body > p")).to_have_count(2)
    expect(draft.locator(".lf-draft-body > p br")).to_have_count(1)
    expect(draft.locator(".lf-draft-body strong")).to_have_text("paragraph")
    expect(draft.locator(".lf-draft-body code")).to_have_text("paragraph")
    edits = [
        e for e in events_model.read_events(serve.page_dir) if e.get("action") == "edit"
    ]
    assert [e["detail"]["value"] for e in edits] == [exact]


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


def test_a_finger_copies_a_draft_from_anywhere_in_copy_s_reach(browser, serve):
    """Copy runs on its shadow button's press, so its reach is the button's: under a
    finger, a press just past its face copies. A reach on the host would stand over the
    button and take every press from it."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Copied draft",
                '<h1>Release note</h1><lf-draft id="note"><pre>Keep `this` note.</pre></lf-draft>',
            )
        ),
        context=context,
    )
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


def test_a_finger_on_the_last_line_writes_there_rather_than_discarding(browser, serve):
    """Under a finger the toolbar stands on the box's bottom border, and each mark's
    reach half a finger's floor above it. The box's padding keeps that reach off the
    words, so a press at the end of the last line puts the caret there. The padding was
    10px, so the press 3px above the field's foot under Discard discarded the edit."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Finger draft",
                '<h1>Release note</h1><lf-draft id="note"><pre>Keep this note.</pre></lf-draft>',
            )
        ),
        context=context,
    )
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
        before = controls.evaluate_all(
            "ns => ns.map(n=>({action:n.dataset.lfDraftAction,box:n.getBoundingClientRect().toJSON()}))"
        )
        button = draft_control(page, action, "note")
        box = button.bounding_box()
        x = box["x"] + (2 if edge == "left" else box["width"] - 2)
        page.mouse.move(x, box["y"] + box["height"] / 2)
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
    page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    scroll_settled(page)
    before = draft.bounding_box()["height"]
    scroll_before = page.evaluate("scrollY")
    draft_control(page, "cancel", "copy").click()
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
    draft_control(page, "cancel", "copy").click()
    assert draft.evaluate("d=>d.getAnimations().length") == 0
