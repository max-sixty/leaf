"""Code blocks and document readers: line references and excerpts in a code block, and
switching a document between its rendered and source readings as its source changes."""

import json
from base64 import b64encode

import pytest
from playwright.sync_api import expect
from render_cases_widgets import LONG_LINE_DIFF_PAGE
from render_harness import (
    ROOT,
    held_frames,
    holding,
    leaf_page,
    open_page,
    resized,
    round_trip,
    scroll_settled,
    select,
    select_words,
    sending,
    told,
    write,
)

from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

# The rows of the text document `#log`, one a line, in order across its runs.
ROWS = "#log .lf-text-document-run > *"

# A row's number, generated content standing in the row's padding: what it says and
# where it ends, beside where the row's words start, both from the row's left edge.
NUMBER = """row => {
  const number = getComputedStyle(row, '::before');
  const words = document.createRange();
  words.selectNodeContents(row);
  return {content: number.content,
          end: parseFloat(number.left) + parseFloat(number.width),
          words: words.getBoundingClientRect().left - row.getBoundingClientRect().left};
}"""


def test_a_markdown_document_switches_between_rendered_content_and_exact_source(
    browser, serve
):
    """Preview and source are two readings of one feed, reachable by press and key.
    The preview reads the file as a Markdown file reads: a line its editor wrapped
    still stands in one paragraph, which a triple-click selects whole."""
    text = (
        "# A rendered document\r\n\r"
        "Read [the details](https://example.com/details).\n\n"
        "- First item, which its editor\n  wrapped\n- Second item\n\n"
        "| Name | Value |\n| --- | --- |\n| Outcome | **Ready** |\n"
    )
    url = serve(
        leaf_page(
            "Document readings",
            '<h1>Document readings</h1><lf-text-document id="document" '
            'source="document-text" preview="markdown" label="Notes">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    page = open_page(browser, url)
    document = page.locator("#document")
    preview = document.get_by_role("tab", name="Preview", exact=True)
    source = document.get_by_role("tab", name="Source", exact=True)
    expect(preview).to_have_attribute("aria-selected", "true")
    expect(document.get_by_role("heading", name="A rendered document")).to_be_visible()
    expect(document.get_by_role("link", name="the details")).to_have_attribute(
        "href", "https://example.com/details"
    )
    items = document.get_by_role("listitem")
    expect(items).to_have_text(["First item, which its editor wrapped", "Second item"])
    expect(document.get_by_role("cell")).to_have_text(["Outcome", "Ready"])
    items.first.click(click_count=3)
    assert (
        page.evaluate("getSelection().toString()").strip()
        == "First item, which its editor wrapped"
    )

    source.click()
    expect(source).to_have_attribute("aria-selected", "true")
    expect(document.locator("pre")).to_be_visible()
    assert document.locator("code").text_content() == text
    # Numbering stays in its own visible column and outside the exact source text.
    number = document.locator(".lf-text-document-run > *").first.evaluate(NUMBER)
    assert number["content"] == 'counter(lf-line) / ""', number
    assert 0 < number["end"] < number["words"], number
    source.press("ArrowLeft")
    expect(preview).to_be_focused()
    expect(preview).to_have_attribute("aria-selected", "true")
    expect(document.get_by_role("heading", name="A rendered document")).to_be_visible()
    preview.press("End")
    expect(source).to_be_focused()
    expect(source).to_have_attribute("aria-selected", "true")


def test_a_written_markdown_passage_reads_rendered_over_its_exact_source(
    browser, serve
):
    """A passage the page writes in the document's <pre> needs no data source: the
    preview renders it, in a box as tall as its rendering rather than the bound a
    bound document keeps, and the Source tab holds it character for character."""
    text = "**Fixed** a crash when `--config` names <missing> files.\n"
    url = serve(
        leaf_page(
            "Written passage",
            '<h1>Written passage</h1><lf-text-document id="passage" '
            'label="CHANGELOG.md" preview="markdown"><pre>\n'
            + text.replace("<", "&lt;").replace(">", "&gt;")
            + "</pre></lf-text-document>",
        )
    )
    page = open_page(browser, url)
    document = page.locator("#passage")
    expect(document.locator("figcaption")).to_have_text("CHANGELOG.md")
    expect(document.locator("strong")).to_have_text("Fixed")
    expect(document.locator(".lf-text-document-preview code")).to_have_text("--config")
    expect(document.locator(".lf-text-document-preview")).to_contain_text(
        "names <missing> files."
    )
    view, rendering = document.evaluate(
        """host => [host.querySelector('lf-tab:not([hidden])'),
          host.querySelector('.lf-text-document-preview')]
          .map(box => box.getBoundingClientRect().height)"""
    )
    assert abs(view - rendering) < 1, (view, rendering)
    # The preview's padding is the visible inset, without the paragraph's margins.
    insets = document.locator(".lf-text-document-preview").evaluate(
        """box => {
          const paragraph = box.querySelector('p').getBoundingClientRect();
          const frame = box.getBoundingClientRect();
          const style = getComputedStyle(box);
          return [paragraph.top - frame.top, frame.bottom - paragraph.bottom,
                  parseFloat(style.paddingTop), parseFloat(style.paddingBottom)];
        }"""
    )
    assert insets[:2] == insets[2:], insets
    document.get_by_role("tab", name="Source", exact=True).click()
    assert document.locator(".lf-text-document-listing code").text_content() == text


def test_a_written_markdown_source_keeps_the_preview_height_until_shown_whole(
    browser, serve
):
    """A written Markdown preview's Source tab takes the preview's height, so neither
    switching to it nor reloading on it moves what follows the document. Where that
    height cuts the source, a press shows every line and puts focus on them."""
    links = "".join(f"[#{n}]: https://example.com/pull/{n}\n" for n in range(800, 812))
    text = (
        "## 2.4.0\n\n- Fixed a crash when `--config` is missing ([#800]).\n\n" + links
    )
    url = serve(
        leaf_page(
            "Release notes",
            '<h1>Release notes</h1><lf-text-document id="notes" '
            f'label="CHANGELOG.md" preview="markdown"><pre>\n{text}</pre>'
            '</lf-text-document><p id="after">After the notes.</p>',
        )
    )
    page = open_page(browser, url)
    document = page.locator("#notes")
    read = """() => [document.getElementById('notes').getBoundingClientRect().height,
      document.getElementById('after').getBoundingClientRect().top]"""
    preview = page.evaluate(read)
    document.get_by_role("tab", name="Source", exact=True).click()
    assert page.evaluate(read) == preview
    lines = len(text.split("\n"))
    press = document.get_by_role("button", name=f"Show all {lines} lines")
    expect(press).to_be_visible()
    held = []
    page.route("**/leaf.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    page.locator("#after").wait_for(state="attached")
    holding(page, held, 1, "the runtime")
    assert page.evaluate(read) == preview
    for route in held:
        route.continue_()
    page.unroute("**/leaf.js")
    wait_until_ready(page)
    expect(document.get_by_role("tab", name="Source", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(press).to_be_visible()
    assert page.evaluate(read) == preview
    press.click()
    expect(press).to_be_hidden()
    expect(document.locator(".lf-text-document-listing > pre")).to_be_focused()
    whole = document.locator("lf-tab:not([hidden])").evaluate(
        "tab => [tab.clientHeight, tab.scrollHeight]"
    )
    assert whole[0] == whole[1] and whole[0] > preview[0] - 80, (whole, preview)


def test_a_widget_document_updates_both_readings_and_keeps_the_selected_view(
    browser, serve
):
    """Widget output reaches both document readings at startup and on input."""
    companion = ROOT / "examples/developer/feature-gallery.page"
    declaration = json.loads((companion / "registry.json").read_text())[
        "lf-document-gallery"
    ]
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Widget document",
                "<h1>Widget document</h1>"
                '<lf-document-gallery id="producer"></lf-document-gallery>'
                '<lf-text-document id="document" for="producer" '
                'preview="markdown" label="Release note"></lf-text-document>',
            ),
            page_files={
                "registry.json": json.dumps({"lf-document-gallery": declaration}),
                "widgets/lf-document-gallery.js": (
                    companion / "widgets/lf-document-gallery.js"
                ).read_text(),
            },
        ),
    )
    document = page.locator("#document")
    source = document.get_by_role("tab", name="Source", exact=True)
    preview = document.get_by_role("tab", name="Preview", exact=True)
    expect(document.get_by_role("heading", name="Release note 1")).to_be_visible()
    source.click()
    page.get_by_role("button", name="Update document", exact=True).click()
    expect(source).to_have_attribute("aria-selected", "true")
    expect(document.locator("code")).to_have_text(
        "# Release note 2\n\nThe library opens on **Sunday**.\n"
    )
    source.press("Home")
    expect(preview).to_have_attribute("aria-selected", "true")
    expect(document.get_by_role("heading", name="Release note 2")).to_be_visible()
    page.get_by_role("button", name="Update document", exact=True).click()
    expect(preview).to_have_attribute("aria-selected", "true")
    expect(document.get_by_role("heading", name="Release note 3")).to_be_visible()
    preview.press("End")
    expect(document.locator("code")).to_have_text(
        "# Release note 3\n\nThe library opens on **Sunday**.\n"
    )


@pytest.mark.parametrize(
    "preview, height",
    [("markdown", None), ("html", 240)],
    ids=["markdown-default-height", "html-authored-height"],
)
def test_document_readings_share_a_stable_viewport_and_keep_their_scroll(
    browser, serve, preview, height
):
    """Changing readings or evidence length leaves the surrounding page in place."""
    paragraphs = [f"Evidence paragraph {i}: a passage to inspect." for i in range(70)]
    if preview == "markdown":
        long = "# Document title\n\n" + "\n\n".join(paragraphs)
        short = "# Short document\n\nOne paragraph.\n"
    else:
        long = (
            "<h1>Document title</h1>\n"
            + "\n".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
            + "\n"
        )
        short = "<h1>Short document</h1>\n<p>One paragraph.</p>\n"
    style = f"<style>#document {{ --lf-bound: {height}px; }}</style>" if height else ""
    url = serve(
        leaf_page(
            "Stable document readings",
            '<h1>Inspect evidence</h1><lf-text-document id="document" '
            f'source="document-text" preview="{preview}" label="Evidence">'
            '</lf-text-document><p id="following">The following passage.</p>',
            head=style,
        )
    )
    data_model.cmd_data_set(serve.page_dir, "document-text", long)
    page = open_page(browser, url)
    resized(page, 1280, 1000)
    document = page.locator("#document")
    preview_tab = document.get_by_role("tab", name="Preview", exact=True)
    source_tab = document.get_by_role("tab", name="Source", exact=True)
    source_panel = document.get_by_role("tabpanel", name="Source", exact=True)
    preview_panel = document.get_by_role("tabpanel", name="Preview", exact=True)
    geometry = """() => {
      const box = node => {
        const rect = node.getBoundingClientRect();
        return [rect.top + scrollY, rect.height];
      };
      const owner = document.querySelector('#document');
      return [box(owner), box(owner.querySelector('figcaption')),
              box(owner.querySelector('[role="tablist"]')),
              box(document.querySelector('#following')), scrollY];
    }"""
    before = page.evaluate(geometry)
    preview_height = preview_panel.bounding_box()["height"]
    if height:
        assert preview_height == pytest.approx(height, abs=1)

    if preview == "markdown":
        preview_tab.click()
        page.keyboard.press("Tab")
        expect(preview_panel).to_be_focused()
        page.keyboard.press("PageDown")
        page.wait_for_function(
            "() => document.querySelector('#document [role=tabpanel]:not([hidden])').scrollTop > 0"
        )
        scroll_settled(page, "#document [role=tabpanel]:not([hidden])")
        first_scroll = preview_panel.evaluate("el => el.scrollTop")
        page.keyboard.press("PageDown")
        page.wait_for_function(
            "at => document.querySelector('#document [role=tabpanel]:not([hidden])').scrollTop > at",
            arg=first_scroll,
        )
        scroll_settled(page, "#document [role=tabpanel]:not([hidden])")
        preview_scroll = preview_panel.evaluate("el => el.scrollTop")
    else:
        frame = document.locator("iframe").element_handle().content_frame()
        frame.get_by_role("heading", name="Document title").click()
        page.keyboard.press("PageDown")
        frame.wait_for_function("() => document.scrollingElement.scrollTop > 0")
        scroll_settled(frame)
        first_scroll = frame.evaluate("document.scrollingElement.scrollTop")
        page.keyboard.press("PageDown")
        frame.wait_for_function(
            "at => document.scrollingElement.scrollTop > at", arg=first_scroll
        )
        scroll_settled(frame)
        preview_scroll = frame.evaluate("document.scrollingElement.scrollTop")
    assert page.evaluate(geometry) == before

    source_tab.click()
    expect(source_panel).to_be_visible()
    assert source_panel.bounding_box()["height"] == pytest.approx(preview_height, abs=1)
    assert page.evaluate(geometry) == before
    page.keyboard.press("Tab")
    expect(source_panel).to_be_focused()
    page.keyboard.press("PageDown")
    page.wait_for_function(
        "() => document.querySelector('#document [role=tabpanel]:not([hidden])').scrollTop > 0"
    )
    scroll_settled(page, "#document [role=tabpanel]:not([hidden])")
    source_scroll = source_panel.evaluate("el => el.scrollTop")
    assert source_scroll != preview_scroll
    assert page.evaluate(geometry) == before

    preview_tab.click()
    if preview == "markdown":
        assert preview_panel.evaluate("el => el.scrollTop") == preview_scroll
    else:
        assert frame.evaluate("document.scrollingElement.scrollTop") == preview_scroll
    source_tab.click()
    assert source_panel.evaluate("el => el.scrollTop") == source_scroll
    assert page.evaluate(geometry) == before

    data_model.cmd_data_set(serve.page_dir, "document-text", short)
    told(page)
    rendered(page)
    assert document.locator("code").text_content() == short
    assert page.evaluate(geometry) == before
    source_tab.press("Home")
    expect(preview_tab).to_have_attribute("aria-selected", "true")
    assert page.evaluate(geometry) == before
    if preview == "markdown":
        expect(document.get_by_role("heading", name="Short document")).to_be_visible()
    else:
        expect(frame.get_by_role("heading", name="Short document")).to_be_visible()
    assert preview_panel.bounding_box()["height"] == pytest.approx(
        preview_height, abs=1
    )


def test_a_document_source_follows_appends_only_while_its_reader_is_at_the_end(
    browser, serve
):
    """A preview switch retains the source's declared end-following reading policy."""
    url = serve(
        leaf_page(
            "Following source evidence",
            '<h1>Evidence</h1><lf-text-document id="document" source="document-text" '
            'preview="markdown" data-bound="end"></lf-text-document>',
            head="<style>#document { --lf-bound: 240px; }</style>",
        )
    )
    text = "\n".join(f"Evidence line {i}" for i in range(80)) + "\n"
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    page = open_page(browser, url)
    document = page.locator("#document")
    source_tab = document.get_by_role("tab", name="Source", exact=True)
    source_tab.click()
    source = document.get_by_role("tabpanel", name="Source", exact=True)
    at_end = """el => el.scrollHeight > el.clientHeight &&
      el.scrollHeight - el.scrollTop - el.clientHeight <= 2"""
    page.wait_for_function(
        f"({at_end})(document.querySelector('#document [role=tabpanel]:not([hidden])'))"
    )
    text += "A newly appended line\n"
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    told(page)
    rendered(page)
    assert source.evaluate(at_end)
    page.keyboard.press("Tab")
    expect(source).to_be_focused()
    page.keyboard.press("PageUp")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('#document [role=tabpanel]:not([hidden])');
          return el.scrollHeight - el.scrollTop - el.clientHeight > 20;
        }"""
    )
    scroll_settled(page, "#document [role=tabpanel]:not([hidden])")
    position = source.evaluate("el => el.scrollTop")
    text += "Another newly appended line\n"
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    told(page)
    rendered(page)
    assert source.evaluate("el => el.scrollTop") == position
    assert not source.evaluate(at_end)
    document.get_by_role("tab", name="Preview", exact=True).click()
    source_tab.click()
    assert source.evaluate("el => el.scrollTop") == position


def test_a_hidden_document_preview_opens_at_its_fragment_without_resizing(
    browser, serve
):
    """A fragment naming a closed reading opens it without changing its fixed box."""
    url = serve(
        leaf_page(
            "Reveal document evidence",
            '<h1>Evidence</h1><p><a href="#document--preview">Read the preview</a></p>'
            '<lf-text-document id="document" source="document-text" preview="markdown" '
            '></lf-text-document><p id="following">Following.</p>',
            head="<style>#document { --lf-bound: 240px; }</style>",
        )
    )
    text = "# Document\n\n" + "A paragraph of evidence.\n\n" * 30
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    page = open_page(browser, url)
    document = page.locator("#document")
    document.get_by_role("tab", name="Source", exact=True).click()
    following = page.locator("#following").evaluate(
        "el => el.getBoundingClientRect().top + scrollY"
    )
    page.get_by_role("link", name="Read the preview").click()
    expect(document.get_by_role("tab", name="Preview", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    panel = document.get_by_role("tabpanel", name="Preview", exact=True)
    expect(panel).to_be_in_viewport()
    assert panel.bounding_box()["height"] == pytest.approx(240, abs=1)
    expect(document.get_by_role("heading", name="Document", exact=True)).to_be_visible()
    assert (
        page.locator("#following").evaluate(
            "el => el.getBoundingClientRect().top + scrollY"
        )
        == following
    )


def test_a_document_in_a_tab_set_keeps_its_strip_under_its_caption(
    browser, serve, subtests
):
    """A document's Preview/Source strip stands directly under its caption, however
    many tab strips stand over the document. Each strip passes its height on as
    `--lf-top`, where the document's strip sticks. While the frame was a scroll
    container, the strip stuck at that height inside the frame, below the caption and
    over the preview's first lines (issue #5017)."""
    url = serve(
        leaf_page(
            "Prompt and notes",
            '<lf-tabs id="sections" list="side"><lf-tab id="about" label="About">'
            '<lf-tabs id="views"><lf-tab id="prompt" label="Prompt">'
            '<lf-text-document id="document" label="prompt.md" preview="markdown">'
            "<pre>The prompt's first sentence.\n\nIts second paragraph.</pre>"
            '</lf-text-document></lf-tab><lf-tab id="notes" label="Notes">'
            "<p>Notes.</p></lf-tab></lf-tabs></lf-tab>"
            '<lf-tab id="method" label="Method"><p>Method.</p></lf-tab></lf-tabs>',
        )
    )
    page = open_page(browser, url)
    document = page.locator("#document")
    preview = document.get_by_role("tabpanel", name="Preview", exact=True)
    expect(preview.get_by_text("The prompt's first sentence.")).to_be_visible()
    for width in (1280, 390):
        with subtests.test(width=width):
            resized(page, width, 844)
            read = document.evaluate("""el => {
              const caption = el.querySelector('figcaption').getBoundingClientRect();
              const strip = el.querySelector('.lf-tabstrip').getBoundingClientRect();
              const panel = el.querySelector('[role=tabpanel]:not([hidden])');
              const top = panel.getBoundingClientRect();
              const hit = document.elementFromPoint(top.left + 24, top.top + 2);
              return {caption: caption.bottom, strip: strip.top,
                      panelOnTop: panel.contains(hit)};
            }""")
            assert read["strip"] == pytest.approx(read["caption"], abs=0.5), read
            assert read["panelOnTop"], read


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_find_reaches_the_text_of_a_document_in_a_tab_nobody_opened(
    request, serve, engine
):
    """Every document's whole text stands in the page, a closed tab's too, so the
    browser's Find reaches a word only an unopened tab's document holds, and finding
    it opens that tab, whose rows then stand numbered beside their lines. Firefox's
    `window.find` searches and opens folds as its
    find bar does; Chromium's searches no fold, so there the word is asked of the
    listing's text, which is what its find bar searches."""
    lines = [f"line {at}" for at in range(300)]
    tabs = "".join(
        f'<lf-tab id="tab-{at}" label="Doc {at}"><lf-text-document id="doc-{at}" '
        f'source="text-{at}" language="python"></lf-text-document></lf-tab>'
        for at in range(3)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    for at in range(3):
        words = [*lines, f"needle_{at} = {at}"]
        data_model.cmd_data_set(serve.page_dir, f"text-{at}", "\n".join(words) + "\n")
    page = open_page(request.getfixturevalue(engine), url)
    expect(page.locator("lf-text-document.lf-rendered")).to_have_count(3)
    closed = page.locator("#doc-2 code")
    assert closed.text_content().endswith("needle_2 = 2\n")
    tab = page.get_by_role("tab", name="Doc 2", exact=True)
    expect(tab).to_have_attribute("aria-selected", "false")
    if engine == "firefox_browser":
        assert page.evaluate("window.find('needle_2')")
        assert page.evaluate(
            "getSelection().anchorNode.parentElement.closest('lf-text-document').id"
        ) == ("doc-2")
        expect(tab).to_have_attribute("aria-selected", "true")
    else:
        tab.click()
    row = page.locator("#doc-2 .lf-text-document-run > *").first
    expect(row).to_be_visible()
    number = row.evaluate(NUMBER)
    assert number["content"] == 'counter(lf-line) / ""', number
    assert 0 < number["end"] < number["words"], number
    # The opened document's lines in view take their syntax colour; the tab nobody
    # opened takes none.
    page.wait_for_function(TOKENS_IN, arg="#doc-2 code")
    assert not page.evaluate(TOKENS_IN, "#doc-1 code")


def test_the_page_presents_without_waiting_for_a_closed_tab_s_document(browser, serve):
    """A document in a tab nobody opened draws once the page has presented, each in a
    task of its own, so presentation waits only for the document in view. Drawn first,
    30 tabs of 50,000 lines held presentation for 22 s in Firefox, which then restyled
    every row of every closed tab as the page presented, a 2.6 s frame."""
    tabs = "".join(
        f'<lf-tab id="tab-{at}" label="Doc {at}"><lf-text-document id="doc-{at}" '
        f'source="text-{at}"></lf-text-document></lf-tab>'
        for at in range(3)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    for at in range(3):
        data_model.cmd_data_set(serve.page_dir, f"text-{at}", f"document {at}\n" * 40)
    order = """(() => {
      window.order = [];
      new MutationObserver((records) => {
        for (const {target, attributeName} of records)
          if (attributeName === 'data-lf-presented') order.push('presented');
          else if (target.localName === 'lf-text-document'
                   && target.classList.contains('lf-rendered')
                   && !order.includes(target.id)) order.push(target.id);
      }).observe(document, {attributes: true, subtree: true,
                            attributeFilter: ['class', 'data-lf-presented']});
    })()"""
    page = open_page(browser, url, init_script=order)
    expect(page.locator("lf-text-document.lf-rendered")).to_have_count(3)
    assert page.evaluate("order") == ["doc-0", "presented", "doc-1", "doc-2"]


def test_a_listing_s_scroll_mark_changes_nothing_its_rows_inherit(browser, serve):
    """The runtime marks a document's listing as a box that scrolls once it has drawn,
    and the mark restarts the sticky-header slot. The listing states that restart from
    the first paint, so the mark changes nothing its rows inherit: Firefox styles the
    rows of runs it doesn't draw too, and a mark that changed three inherited values
    took a 250 to 570 ms frame on a listing of 97,000 rows. The listing's `code`, which
    every row inherits from, computes the same style, custom properties included, with
    the mark and without it, whatever the mark's rule sets."""
    url = serve(
        leaf_page(
            "Log", '<lf-text-document id="log" source="log-text"></lf-text-document>'
        )
    )
    data_model.cmd_data_set(serve.page_dir, "log-text", "a line\n" * 400)
    page = open_page(browser, url)
    pre = page.locator("#log pre")
    expect(pre).to_have_attribute("data-lf-scrolls", "")
    inherited = """pre => {
      const style = getComputedStyle(pre.querySelector('code'));
      return Object.fromEntries([...style].map((name) => [name, style.getPropertyValue(name)]));
    }"""
    marked = pre.evaluate(inherited)
    # The computed style lists custom properties, the slot's among them.
    assert "--lf-top-covered" in marked
    pre.evaluate("pre => pre.removeAttribute('data-lf-scrolls')")
    unmarked = pre.evaluate(inherited)
    changed = {
        name
        for name in marked.keys() | unmarked.keys()
        if marked.get(name) != unmarked.get(name)
    }
    assert not changed, changed


# How many syntax-colour ranges stand in the element `selector` names.
TOKENS_IN = """selector => {
  const box = document.querySelector(selector);
  let count = 0;
  for (const [name, highlight] of CSS.highlights)
    if (name.startsWith('lf-token-'))
      for (const range of highlight) if (box.contains(range.startContainer)) count++;
  return count;
}"""


def test_document_views_remember_independently_and_follow_live_source_updates(
    browser, serve
):
    """Reading choices survive reload and news without becoming decisions in the log."""
    url = serve(
        leaf_page(
            "Independent document readings",
            '<h1>Documents</h1><lf-text-document id="first" source="first-text" '
            'preview="markdown"></lf-text-document>'
            '<lf-text-document id="second" source="second-text" '
            'preview="markdown"></lf-text-document>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "first-text", "# First original\n")
    data_model.cmd_data_set(serve.page_dir, "second-text", "# Second original\n")
    page = open_page(browser, url)
    first = page.locator("#first")
    second = page.locator("#second")

    def decisions():
        return [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] in {"action", "report", "undo"}
        ]

    before = decisions()
    first.get_by_role("tab", name="Source", exact=True).click()
    expect(second.get_by_role("tab", name="Preview", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    page.reload()
    wait_until_ready(page)
    expect(first.get_by_role("tab", name="Source", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(second.get_by_role("tab", name="Preview", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    updated = "# First updated\n\nFresh **evidence**.\n"
    data_model.cmd_data_set(serve.page_dir, "first-text", updated)
    told(page)
    rendered(page)
    assert first.locator("code").text_content() == updated
    expect(first.get_by_role("tab", name="Source", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    first.get_by_role("tab", name="Preview", exact=True).click()
    expect(first.get_by_role("heading", name="First updated")).to_be_visible()
    expect(first.locator("strong")).to_have_text("evidence")
    expect(second.get_by_role("heading", name="Second original")).to_be_visible()
    round_trip(page)
    assert decisions() == before


def test_an_exported_markdown_document_keeps_its_preview_and_source_switch(
    browser, serve, tmp_path
):
    """The offline artifact carries both the source value and its renderers."""
    serve(
        leaf_page(
            "Offline document",
            '<h1>Offline document</h1><lf-text-document id="document" '
            'source="document-text" preview="markdown"></lf-text-document>',
        )
    )
    text = "# Captured heading\n\nA **captured** paragraph.\n"
    data_model.cmd_data_set(serve.page_dir, "document-text", text)
    out = tmp_path / "document.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = open_page(browser, out.as_uri())
    document = page.locator("#document")
    expect(document.get_by_role("heading", name="Captured heading")).to_be_visible()
    expect(document.locator("strong")).to_have_text("captured")
    source = document.get_by_role("tab", name="Source", exact=True)
    source.click()
    expect(document.locator("pre")).to_be_visible()
    assert document.locator("code").text_content() == text
    source.press("Home")
    expect(document.get_by_role("heading", name="Captured heading")).to_be_visible()
    page.keyboard.press("g")
    rendered(page)
    assert page.locator("body").get_attribute("data-lf-go-to-active") is None
    page.keyboard.press("?")
    rendered(page)
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.locator(".lf-chrome > #lf-media-viewer:not([open])")).to_have_count(1)
    expect(page.locator(".lf-floating-panel")).to_have_count(0)
    document.get_by_role("tab", name="Preview", exact=True).press("ArrowRight")
    expect(source).to_have_attribute("aria-selected", "true")


def test_an_html_document_previews_its_own_styles_and_refreshes_from_its_source(
    browser, serve
):
    """HTML keeps its document styling inside the preview and retains literal source."""
    text = (
        "<!doctype html><html><head><style>"
        "body { color: rgb(193, 2, 151); } h1 { font-size: 25px; }"
        "</style></head><body><h1>Isolated document</h1>"
        '<p id="execution"></p><p id="isolation"></p><script>'
        "document.querySelector('#execution').textContent = 'Script executed';"
        "try { parent.document.querySelector('#leaf-title').textContent = 'Changed';"
        "document.querySelector('#isolation').textContent = 'Parent document accessible';"
        "} catch { document.querySelector('#isolation').textContent = 'Parent document denied'; }"
        "</script></body></html>"
    )
    url = serve(
        leaf_page(
            "HTML evidence",
            '<h1 id="leaf-title">HTML evidence</h1><lf-text-document id="document" '
            'source="html-text" preview="html" label="HTML capture">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "html-text", text)
    page = open_page(browser, url)
    document = page.locator("#document")
    frame = document.frame_locator("iframe")
    heading = frame.get_by_role("heading", name="Isolated document")
    expect(heading).to_be_visible()
    expect(heading).to_have_css("color", "rgb(193, 2, 151)")
    expect(heading).to_have_css("font-size", "25px")
    expect(frame.locator("#execution")).to_have_text("Script executed")
    expect(frame.locator("#isolation")).to_have_text("Parent document denied")
    expect(page.locator("#leaf-title")).to_have_text("HTML evidence")
    assert (
        page.locator("#leaf-title").evaluate("el => getComputedStyle(el).color")
        != "rgb(193, 2, 151)"
    )
    source = document.get_by_role("tab", name="Source", exact=True)
    source.click()
    expect(document.locator("pre")).to_be_visible()
    assert document.locator("code").text_content() == text
    held = []
    page.route("**/preview-style.css", lambda route: held.append(route))
    updated = text.replace("Isolated document", "Updated document").replace(
        "</head>", '<link rel="stylesheet" href="/preview-style.css"></head>'
    )
    data_model.cmd_data_set(serve.page_dir, "html-text", updated)
    holding(page, held, 1, "the HTML preview's stylesheet")
    assert (
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness()"
        )
        is not None
    )
    # A rerun publishes a new receipt without changing its value revision, even
    # while the frame's stylesheet is loading. The reading keeps that load pending.
    data_model.cmd_data_set(serve.page_dir, "html-text", updated)
    answer = page.request.get(f"{page.evaluate('location.origin')}/api/state")
    assert answer.ok
    snapshot = answer.json()["data"]["sources"]["html-text"]
    revision = snapshot["revision"]
    # `wait_for_function` takes an async predicate's promise as its answer, so the
    # reading is installed first and waited on synchronously.
    page.evaluate(
        """async () => {
          window.__lfReadApplication = (await window.__lfCheckApi()).readApplication;
        }"""
    )
    page.wait_for_function(
        "run => window.__lfReadApplication().data.sources['html-text'].run === run",
        arg=snapshot["run"],
    )
    assert (
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness()"
        )
        is not None
    )
    # Acceptance precedes asynchronous syntax rendering. Wait for the displayed
    # snapshot's commit while the preview's resource load remains held.
    expect(document.locator("pre")).to_have_attribute(
        "data-lf-source-revision", revision
    )
    code = document.locator("code")
    ends = code.evaluate("""el => {
      const words = 'Updated document';
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const start = node.textContent.indexOf(words);
        if (start < 0) continue;
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + words.length);
        const box = range.getBoundingClientRect();
        return [[box.left, box.top + box.height / 2], [box.right, box.top + box.height / 2]];
      }
    }""")
    select(page, *ends)
    assert "Updated document" in page.evaluate("getSelection().toString()")
    captured = page.evaluate("""async () => {
      const {selectionAnchor} = await window.__lfCheckApi();
      const {readApplication} = await window.__lfCheckApi();
      return {anchor: selectionAnchor(getSelection()),
              revision: readApplication().data.sources['html-text'].revision};
    }""")
    assert captured["anchor"]["source_revision"] == captured["revision"] == revision
    assert captured["anchor"]["source"] == "html-text"
    assert captured["anchor"]["datum"] == "source"
    page.keyboard.press("c")
    composer = page.locator(".lf-composer leaf-text")
    expect(composer).to_be_focused()
    write(composer, "Comment captured while the preview loads.")
    held[0].fulfill(
        status=200,
        content_type="text/css",
        body="h1 { color: rgb(12, 93, 47); }",
    )
    told(page)
    rendered(page)
    with sending(page, "the source comment captured during preview loading"):
        composer.press("ControlOrMeta+Enter")
    comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
        and event.get("text") == "Comment captured while the preview loads."
    )
    assert comment["anchor"] == captured["anchor"]
    assert document.locator("code").text_content() == updated
    source.press("Home")
    expect(document.get_by_role("tab", name="Preview", exact=True)).to_be_focused()
    updated_heading = frame.get_by_role("heading", name="Updated document")
    expect(updated_heading).to_be_visible()
    expect(updated_heading).to_have_css("color", "rgb(12, 93, 47)")


def test_a_text_document_refresh_keeps_selection_in_unchanged_text(browser, serve):
    """Changing evidence beside a selected passage keeps its native selection, in a
    plain document and in one whose tokens split the text into coloured spans."""
    tags = (
        '<lf-text-document id="plain-document" source="plain-text"></lf-text-document>'
        '<lf-text-document id="python-document" source="python-text" language="python">'
        "</lf-text-document>"
    )
    source = LONG_LINE_DIFF_PAGE.replace(
        '<lf-diff id="patch" source="review-patch"></lf-diff>', tags
    )
    url = serve(source)
    for name in ("plain-text", "python-text"):
        data_model.cmd_data_set(
            serve.page_dir, name, 'first = "old"\nsecond = "selected"\n'
        )
    page = open_page(browser, url)
    for document, name in (
        ("#plain-document", "plain-text"),
        ("#python-document", "python-text"),
    ):
        refresh_keeps_selection(page, serve, document, name)


def refresh_keeps_selection(page, serve, document, name):
    """Select a word in `document`, change another line of its `name` source, and
    find the selection and the page's scroll where they were."""
    code = page.locator(f"{document} code")
    code.scroll_into_view_if_needed()
    ends = code.evaluate("""row => {
      const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const start = node.textContent.indexOf('selected');
        if (start < 0) continue;
        const range = document.createRange();
        range.setStart(node, start); range.setEnd(node, start + 'selected'.length);
        const box = range.getBoundingClientRect();
        return [[box.left, box.top + box.height / 2], [box.right, box.top + box.height / 2]];
      }
    }""")
    select(page, *ends)
    reading = "() => ({selection: getSelection().toString(), scroll: scrollY})"
    before = page.evaluate(reading)
    assert before["selection"] == "selected"
    data_model.cmd_data_set(
        serve.page_dir, name, 'first = "new beginning"\nsecond = "selected"\n'
    )
    told(page)
    rendered(page)
    expect(code).to_contain_text('first = "new beginning"')
    assert page.evaluate(reading) == before, document


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_text_document_update_keeps_a_selection_it_carries_into_another_run(
    request, serve, engine
):
    """Lines added above a selected row carry it from one run of rows into another, and
    it keeps its native selection: runs are a drawing boundary, not a row's identity.
    Reconciled run by run, one line added above the last row of a run grew Chromium's
    selection to take in the row before it and cleared Firefox's. The selected row
    keeps it too when its own line is edited, in place or as it moves, where a walk
    over the lines took the edit for a new row. The numbers still count every row, read
    in Chromium off what it draws: a count started on each run's own box numbered every
    run after the first from 1."""
    lines = [f"line {i}" for i in range(1, 279)]
    lines[127] = "selected passage"
    url = serve(
        leaf_page(
            "Run edges",
            '<h1>Run log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    page = open_page(request.getfixturevalue(engine), url)
    select_words(page, f"{ROWS} >> nth=127")
    selected = page.evaluate("() => getSelection().toString()")
    assert "selected passage" in selected
    for added, edit in ((1, ""), (0, ", edited"), (200, " twice")):
        at = next(i for i, line in enumerate(lines) if line.startswith("selected"))
        lines[at] += edit
        lines = [f"added {added} {i}" for i in range(added)] + lines
        data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
        told(page)
        rendered(page)
        row = page.locator(ROWS).nth(at + added)
        expect(row).to_have_text(lines[at + added])
        now = page.evaluate("() => getSelection().toString()")
        if not edit:
            assert now == selected, added
        else:
            assert "selected passage" in now and not {"line", "added"} & set(
                now.split()
            )
        if engine == "browser":
            row.evaluate("row => row.scrollIntoView({block: 'center'})")
            rendered(page)
            drawn = drawn_numbers(page, "log")
            assert at + added + 1 in dict(drawn), drawn
            assert all(text == str(line) for line, text in drawn), drawn


def drawn_numbers(page, document):
    """The number each drawn row of the text document `document` shows, as
    [(line, text)], read off Chromium's layout tree, since script can't read the text a
    counter draws. A row the browser skips draws no number and is left out."""
    snapshot = page.context.new_cdp_session(page).send(
        "DOMSnapshot.captureSnapshot", {"computedStyles": []}
    )
    strings = snapshot["strings"]
    nodes = snapshot["documents"][0]["nodes"]
    layout = snapshot["documents"][0]["layout"]
    parents = nodes["parentIndex"]
    names = [strings[name] for name in nodes["nodeName"]]
    attributes = [
        {
            strings[key]: strings[value]
            for key, value in zip(pairs[::2], pairs[1::2], strict=True)
        }
        for pairs in nodes["attributes"]
    ]

    def within(node):
        while node >= 0:
            if attributes[node].get("id") == document:
                return True
            node = parents[node]
        return False

    runs = {
        node
        for node, held in enumerate(attributes)
        if "lf-text-document-run" in held.get("class", "").split() and within(node)
    }
    rows = [
        node
        for node, parent in enumerate(parents)
        if parent in runs and names[node] == "DIV"
    ]
    line = {node: at + 1 for at, node in enumerate(rows)}
    drawn = {
        node: strings[text]
        for node, text in zip(layout["nodeIndex"], layout["text"], strict=True)
        if text >= 0
    }
    return [
        (line[parents[node]], drawn[node])
        for node in drawn
        if names[node] == "::before" and parents[node] in line
    ]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_long_text_document_draws_the_lines_in_view_and_keeps_the_rest_whole(
    request, serve, engine
):
    """A long text document draws only the runs of lines in view: styling every line on
    each change to the page took tens of seconds and gigabytes at a few megabytes of
    text. The lines out of view stay whole for the reader. The listing holds every
    line, its numbers stand in one column from the first run to the last, and a thread
    on a line far down jumps to the line drawn there. Each run is sized by the lines
    its rows fill: sized a line a row, Firefox drew the far line's run for a returning
    reader. A run drawn before the window narrows forgets the height it was drawn at:
    kept, it left a drag to the bottom short of the last line in both engines. Long
    tokens, which Firefox also breaks after a slash, fill more lines than the size
    says, and the run the travel lands in is drawn for the jump: left skipped,
    Firefox's jump stopped short and a second scroll followed. A second travel while
    the first still holds the run drawn jumps too: it glided."""
    # Long tokens stand in every run but the last, which the drag to the bottom draws:
    # Firefox draws more lines than the size says over them, and the drag would stop
    # short, a limit Leaf accepts.
    text = "".join(
        f"line {i} "
        + (
            b64encode(bytes((i * 31 + k * 101) % 256 for k in range(240))).decode()
            if i % 7 == 0 and i <= 7 * 128
            else "wrapping words " * 20
            if i % 3 == 0
            else "short"
        )
        + "\n"
        for i in range(1, 1001)
    )
    url = serve(
        leaf_page(
            "Long evidence",
            '<h1>Run log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "log-text", text)
    page = open_page(request.getfixturevalue(engine), url)
    assert page.locator("#log code").text_content() == text
    expect(page.locator("#log .lf-text-document-run")).to_have_count(8)
    first, far = page.locator(ROWS).nth(0), page.locator(ROWS).nth(879)
    # A run itself always has a box; the browser skips the lines inside it.
    drawn = "line => line.checkVisibility({contentVisibilityAuto: true})"
    assert first.evaluate(drawn)
    assert not far.evaluate(drawn)
    left = "line => line.getBoundingClientRect().left"
    first_left = first.evaluate(left)

    # The last run, drawn and then skipped, meets a narrower window.
    pre, last = page.locator("#log pre"), page.locator(ROWS).nth(999)
    width, height = page.viewport_size["width"], page.viewport_size["height"]
    bottom = "pre => { pre.scrollTop = pre.scrollHeight; }"
    for to, shown in ((bottom, "line"), ("pre => { pre.scrollTop = 0; }", "!line")):
        pre.evaluate(to)
        page.wait_for_function(
            f"line => {shown}.checkVisibility({{contentVisibilityAuto: true}})",
            arg=last.element_handle(),
        )
    resized(page, 560, height)
    rendered(page)
    pre.evaluate(bottom)
    rendered(page)
    below = last.evaluate(
        "line => line.getBoundingClientRect().bottom"
        " - line.closest('pre').getBoundingClientRect().bottom"
    )
    assert below <= 1
    resized(page, width, height)
    pre.evaluate("pre => { pre.scrollTop = 0; }")

    for line, words in ((840, "Where does this start?"), (880, "Why does it repeat?")):
        select_words(page, f"{ROWS} >> nth={line - 1}")
        write(page.locator(".lf-composer leaf-text"), words)
        with sending(page, f"the comment on line {line}"):
            page.keyboard.press("ControlOrMeta+Enter")
        page.keyboard.press("Escape")
    assert far.evaluate(left) == pytest.approx(first_left, abs=0.5)
    # The open card keeps its passage's run drawn; a returning reader finds it skipped.
    page.reload()
    wait_until_ready(page)
    assert not far.evaluate(drawn)
    # Each travel jumps: a glide across the runs drew each one it passed, for seconds.
    # The second leaves while the first still holds the run drawn, as a held `t` does:
    # the frames that would release it are held.
    page.locator("#log pre").evaluate(
        "pre => { window.steps = 0; pre.addEventListener('scroll', () => steps++); }"
    )
    with held_frames(page):
        page.keyboard.press("t")
        page.wait_for_function("() => steps > 0")
        page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    scroll_settled(page, "#log pre")
    assert page.evaluate("steps") == 2
    landed = far.evaluate("""line => {
      const box = line.closest('pre').getBoundingClientRect();
      const at = line.getBoundingClientRect();
      const hit = document.elementFromPoint(at.left + 30, at.top + 8);
      return {shown: at.top >= box.top && at.bottom <= box.bottom,
              hit: hit && [...line.closest('code').querySelectorAll('.lf-text-document-run > *')]
                .indexOf(hit.closest('.lf-text-document-run > *')) + 1,
              top: at.top - box.top};
    }""")
    assert landed == {"shown": True, "hit": 880, "top": landed["top"]}, landed


def test_an_excerpt_shows_and_answers_to_its_source_line_numbers(browser, serve):
    """An lf-code body with `lines` is a quotation from a longer file. What the user
    reads is the file's own numbering: the gutter counts from where the quote starts
    and jumps where it skips, each skip stands as an elided row saying how much is
    left out, and the gutter widens so four digits still leave the code in line with
    its notes. Everything that points into the block — `hi`, a note's `at`, a key
    another widget navigates to — names lines by those numbers. A left-out number
    addresses the elided row standing for it, so a note placed there is that row's
    caption, and a number outside the block addresses nothing. A body longer than its ranges goes on counting,
    and a note past either end stands at the block's foot rather than leaving the page.
    A range far longer than the body numbers only the body's lines.
    A copied excerpt is the quoted source and the authored notes, never the numbers or
    the elided rows' counts."""
    url = serve(
        leaf_page(
            "excerpt",
            """
<h1 id="t">Runs</h1>
<p id="lede">The loop that finds each run.</p>
<lf-code id="walk" language="rust" lines="1505-1507,1550-1552" hi="1550"><pre>
fn merge_sort()
{
    let len = v.len();
    while end &gt; 0 {
        let mut start = end - 1;
        start -= 1;
</pre>
<lf-note at="1551">One run per pass.</lf-note>
<lf-note id="gap" at="1520">Setup, left out.</lf-note>
</lf-code>
<lf-code id="short" lines="10-11"><pre>
one
two
three
</pre>
<lf-note id="far" at="99">Past the end.</lf-note>
</lf-code>
<lf-code id="vast" lines="1-999999999999"><pre>
only
</pre></lf-code>
""",
        ),
    )
    page = open_page(browser, url)
    rows = page.locator("#walk pre > *")
    expect(rows).to_have_count(8)
    assert rows.evaluate_all(
        """rs => rs.map(r => r.classList.contains('lf-code-elided')
                   ? ['elided', r.dataset.lfElided, r.textContent]
                   : r.localName === 'lf-note' ? ['note']
                   : [getComputedStyle(r, '::before').content, r.hasAttribute('data-lf-hi')])"""
    ) == [
        ['"1505"', False],
        ['"1506"', False],
        ['"1507"', False],
        ["elided", "42 lines", "Setup, left out."],
        ['"1550"', True],
        ['"1551"', False],
        ["note"],
        ['"1552"', False],
    ]
    short = page.locator("#short pre > *")
    expect(short).to_have_count(4)
    assert short.evaluate_all(
        """rs => rs.map(r => r.localName === 'lf-note' ? r.id
                   : getComputedStyle(r, '::before').content)"""
    ) == ['"10"', '"11"', '"12"', "far"]
    # A range far past the body numbers only the body's lines.
    vast = page.locator("#vast pre > .lf-code-line")
    expect(vast).to_have_count(1)
    assert vast.evaluate("r => getComputedStyle(r, '::before').content") == '"1"'

    code_x, note_x = page.evaluate(
        """() => {
          const start = (node) => {
            const range = document.createRange();
            range.setStart(node.firstChild.firstChild ?? node.firstChild, 0);
            return range.getBoundingClientRect().left;
          };
          return [start(document.querySelector('#walk .lf-code-line')),
                  start(document.querySelector('#walk pre > lf-note'))];
        }"""
    )
    assert abs(code_x - note_x) < 1, (code_x, note_x)

    # The caption sits after the gutter and the count, on the elided row's own line.
    gutter, caption = page.evaluate(
        """() => [document.querySelector('#walk .lf-code-line').getBoundingClientRect(),
                  document.querySelector('#gap').getBoundingClientRect()]
                 .map(r => [r.left, r.height])"""
    )
    assert caption[0] > code_x and caption[1] < 2 * gutter[1], (gutter, caption)

    # The rows a key addresses, as `navigateToDatum` reads them through lfElementsFor.
    addressed = """key => [...document.querySelector('#walk').lfElementsFor(key)]
        .map(l => l.dataset.lfLine ?? `${l.dataset.lfFrom}-${l.dataset.lfTo}`)"""
    assert page.evaluate(addressed, "1507-1550") == ["1507", "1508-1549", "1550"]
    assert page.evaluate(addressed, "1520") == ["1508-1549"]
    assert page.evaluate(addressed, "3") == []

    # The user drags from the excerpt's first word to its last.
    ends = page.locator("#walk pre").evaluate(
        """pre => {
          const walker = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT,
            (node) => node.data.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP);
          const texts = [];
          for (let node = walker.nextNode(); node; node = walker.nextNode()) texts.push(node);
          const glyph = (node, at) => {
            const range = document.createRange();
            range.setStart(node, at);
            range.setEnd(node, at + 1);
            return range.getBoundingClientRect();
          };
          const first = texts[0], last = texts.at(-1);
          const a = glyph(first, first.data.search(/\\S/));
          const b = glyph(last, last.data.trimEnd().length - 1);
          return [[a.left, a.top + a.height / 2], [b.right, b.top + b.height / 2]];
        }"""
    )
    select(page, *ends)
    copied = page.evaluate("() => getSelection().toString()")
    # The notes come along on lines of their own, as authored text; the numbers,
    # the elided mark and its count do not.
    assert copied == (
        "fn merge_sort()\n{\n    let len = v.len();\nSetup, left out.\n"
        "    while end > 0 {\n        let mut start = end - 1;\nOne run per pass.\n"
        "        start -= 1;"
    )


def test_a_code_line_longer_than_its_block_wraps_under_its_own_indent(browser, serve):
    """A line longer than its lf-code block wraps inside the frame rather than running
    past it behind a scrollbar, where a reader on a narrow window never saw its end. The
    rows after the first hang two characters past the line's own indent, so a wrapped
    call deep in a block stays under the code it belongs to, and the gutter stands the
    whole height of the line. What no line box can break, a hash, breaks anywhere."""
    call = "        return compute(" + ", ".join(f"arg_{i}" for i in range(40)) + ")"
    digest = "".join(f"{i:02x}" for i in range(100))
    url = serve(
        leaf_page(
            "wrap",
            f"""
<h1 id="t">Wrap</h1>
<lf-code id="walk" language="python"><pre>
def ceiling(limit):
{call}
{digest}
</pre></lf-code>
""",
        )
    )
    page = open_page(browser, url)
    expect(page.locator("#walk .lf-code-line")).to_have_count(3)
    reading = page.evaluate(
        """() => {
          const pre = document.querySelector('#walk pre');
          const [first, ...long] = pre.querySelectorAll('.lf-code-line');
          const glyph = document.createRange();
          const text = document.createTreeWalker(first, NodeFilter.SHOW_TEXT).nextNode();
          glyph.setStart(text, 0);
          glyph.setEnd(text, 1);
          const {left: codeX, width: ch} = glyph.getBoundingClientRect();
          // Each row's first painted glyph, in characters from the first line's first.
          const rows = (line) => {
            const range = document.createRange();
            range.selectNodeContents(line);
            const starts = new Map();
            for (const r of range.getClientRects()) {
              if (!r.width || !r.height) continue;
              const top = Math.round(r.top);
              starts.set(top, Math.min(starts.get(top) ?? Infinity, r.left));
            }
            return [...starts].sort(([a], [b]) => a - b)
              .map(([, left]) => Math.round((left - codeX) / ch));
          };
          return {
            scrolls: pre.scrollWidth > pre.clientWidth,
            rows: long.map(rows),
            gutterSpans: long.map((line) =>
              getComputedStyle(line, '::before').height ===
                `${line.getBoundingClientRect().height}px`),
          };
        }"""
    )
    assert reading["scrolls"] is False, reading
    call_rows, digest_rows = reading["rows"]
    # The call's leading spaces are text, so its first row starts at the code's edge.
    assert call_rows[0] == 0 and len(call_rows) > 1, reading
    assert set(call_rows[1:]) == {10}, reading
    assert digest_rows[0] == 0 and len(digest_rows) > 1, reading
    assert set(digest_rows[1:]) == {2}, reading
    assert reading["gutterSpans"] == [True, True], reading

    pre = page.locator("#walk pre")
    line = page.locator("#walk .lf-code-line").nth(1)
    # The page supplies the initial presentation; an explicit reader choice owns
    # wrapping even when the page declares its preference important.
    authored = page.add_style_tag(
        content="#walk .lf-code-line { white-space: pre; overflow-wrap: normal; }"
    )
    pre.focus()
    page.keyboard.press("w")
    expect(line).to_have_css("white-space", "pre")
    page.keyboard.press("w")
    expect(line).to_have_css("white-space", "pre-wrap")
    authored.evaluate(
        """node => node.textContent = '#walk .lf-code-line { '
          + 'white-space: pre-wrap !important; overflow-wrap: anywhere !important; }'"""
    )
    page.keyboard.press("w")
    expect(line).to_have_css("white-space", "pre")
    expect(line).to_have_css("overflow-wrap", "normal")
    pre.evaluate("node => node.scrollLeft = 80")
    horizontal = pre.evaluate("node => node.scrollLeft")
    assert horizontal > 0
    page.keyboard.press("w")
    expect(line).to_have_css("white-space", "pre-wrap")
    page.keyboard.press("w")
    rendered(page)
    assert pre.evaluate("node => node.scrollLeft") == horizontal
    page.emulate_media(media="print")
    expect(line).to_have_css("white-space", "pre-wrap")
    expect(line).to_have_css("overflow-wrap", "anywhere")
