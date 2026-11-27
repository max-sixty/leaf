"""Code blocks and document readers: line references and excerpts in a code block, and
switching a document between its rendered and source readings as its source changes."""

import json
import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_cases_widgets import LONG_LINE_DIFF_PAGE
from render_harness import (
    ROOT,
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

from browser.threads import open_panel_thread
from leaf.log import event_log as events_model
from leaf.pages import exporting as exporting_model
from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, wait_until_ready

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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
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
    text = "**Fixed** a crash when `--config` names \\<missing> files.\n"
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


def test_a_written_markdown_source_keeps_its_box_until_shown_whole(browser, serve):
    """A written Markdown preview's Source tab takes the preview's height, so switching
    to it moves nothing that follows the document. Where that height cuts the source, a
    press shows every line and puts focus on them. Reloaded on the Source tab, the
    document first paints its source, and the module draws the tab where that paint
    stood."""
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
    press.click()
    expect(press).to_be_hidden()
    expect(document.locator(".lf-text-document-listing > pre")).to_be_focused()
    whole = document.locator("lf-tab:not([hidden])").evaluate(
        "tab => [tab.clientHeight, tab.scrollHeight]"
    )
    assert whole[0] == whole[1] and whole[0] > preview[0] - 80, (whole, preview)
    held = []
    page.route("**/leaf.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    page.locator("#after").wait_for(state="attached")
    holding(page, held, 1, "the runtime")
    first = page.evaluate(read)
    for route in held:
        route.continue_()
    page.unroute("**/leaf.js")
    wait_until_ready(page)
    expect(document.get_by_role("tab", name="Source", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    assert page.evaluate(read) == first


# Forty paragraphs, eighty lines: longer than a document's default bound in either
# reading.
LONG_RULES = "\n\n".join(f"Paragraph {n} of the quoted rules." for n in range(1, 41))


@pytest.mark.parametrize("preview", ["markdown", None], ids=["preview", "listing"])
def test_a_document_its_bound_cuts_shows_whole_on_a_press(browser, serve, preview):
    """A document longer than its bound stops at the bound, doesn't scroll, and folds
    the text it cuts off where find-in-page and travel reach it. Focusing its press
    changes nothing; pressing it shows the whole document, in every reading, and puts
    focus on the text it showed."""
    attribute = f' preview="{preview}"' if preview else ""
    url = serve(
        leaf_page(
            "Long quote",
            '<h1>Long quote</h1><lf-text-document id="rules" label="RULES.md"'
            f"{attribute}><pre>\n{LONG_RULES}\n</pre></lf-text-document>"
            '<p id="after">After the rules.</p>',
        )
    )
    page = open_page(browser, url)
    document = page.locator("#rules")
    shown = document.locator(
        "lf-tab:not([hidden])" if preview else ".lf-text-document-listing > pre"
    )
    units = document.locator(
        ".lf-text-document-preview > *" if preview else ".lf-text-document-run > *"
    )
    folded = document.locator(
        ".lf-text-document-preview > [hidden='until-found'],"
        " .lf-text-document-run > [hidden='until-found']"
    )
    bound = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).fontSize) * 28"
    )
    cut = shown.evaluate("box => box.getBoundingClientRect().height")
    assert cut <= bound + 1, (cut, bound)
    assert shown.evaluate("box => getComputedStyle(box).overflowY") == "clip"
    expect(units.last).to_have_attribute("hidden", "until-found")
    press = document.get_by_role("button", name="Show all 80 lines")
    press.focus()
    expect(press).to_be_focused()
    expect(press).to_be_visible()
    assert folded.count() > 0
    page.keyboard.press("Enter")
    expect(press).to_be_hidden()
    expect(shown).to_be_focused()
    expect(folded).to_have_count(0)
    assert shown.evaluate("box => getComputedStyle(box).overflowY") == "visible"
    assert shown.evaluate("box => box.getBoundingClientRect().height") > 2 * bound
    if not preview:
        return
    document.get_by_role("tab", name="Source", exact=True).click()
    expect(document.get_by_role("button", name=re.compile("^Show all"))).to_have_count(
        0
    )
    expect(folded).to_have_count(0)


def test_a_short_document_takes_its_text_s_height(browser, serve):
    """A document shorter than its bound takes its text's height, with no room under
    its last line and no press."""
    url = serve(
        leaf_page(
            "Short file",
            '<h1>Short file</h1><lf-text-document id="config" label="config.toml">'
            '<pre><code class="language-toml">a = 1\nb = 2\n</code></pre>'
            "</lf-text-document>",
        )
    )
    page = open_page(browser, url)
    listing = page.locator("#config .lf-text-document-listing > pre")
    rows = listing.evaluate(
        "pre => [pre.getBoundingClientRect().height, "
        "pre.querySelector('code').getBoundingClientRect().height]"
    )
    assert rows[0] == pytest.approx(rows[1], abs=1), rows
    expect(page.get_by_role("button", name=re.compile("^Show all"))).to_have_count(0)


def test_travel_to_a_comment_its_bound_cuts_off_shows_the_document_whole(
    browser, serve
):
    """A comment on words the bound cuts off stays reachable: opening its thread
    shows the whole document, with the words in view."""
    url = serve(
        leaf_page(
            "Long quote",
            '<h1>Long quote</h1><lf-text-document id="rules" label="RULES.md" '
            f'preview="markdown"><pre>\n{LONG_RULES}\n</pre></lf-text-document>'
            '<p id="after">After the rules.</p>',
        )
    )
    page = open_page(browser, url)
    document = page.locator("#rules")
    document.get_by_role("button", name="Show all 80 lines").click()
    select_words(page, "#rules p:nth-of-type(38)")
    write(page.locator(".lf-composer leaf-text"), "Does this one still hold?")
    with sending(page, "the comment on a late paragraph"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    root = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    page.close()
    page = open_page(browser, url)
    document = page.locator("#rules")
    expect(document.get_by_role("button", name="Show all 80 lines")).to_be_visible()
    joined = "&" if "?" in page.url else "?"
    page.goto(f"{page.url}{joined}thread={root['id']}")
    wait_until_ready(page)
    shown = document.locator("lf-tab:not([hidden])")
    expect(shown).to_have_attribute("data-lf-all", "")
    expect(document.get_by_role("button", name="Show all 80 lines")).to_be_hidden()
    scroll_settled(page)
    words = document.locator("p", has_text="Paragraph 38 of")
    assert words.evaluate(
        "p => { const r = p.getBoundingClientRect(); "
        "return r.top >= 0 && r.bottom <= innerHeight; }"
    )


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
def test_document_readings_share_one_height_and_fit_their_text(
    browser, serve, preview, height
):
    """Both readings of a document take the preview's height, up to the bound, so
    switching between them leaves the page in place. An HTML preview scrolls its own
    document in that box and keeps its place across a switch. A shorter text gives a
    Markdown preview a shorter box."""
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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", long)
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
    bound = height or page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).fontSize) * 28"
    )
    assert preview_height == pytest.approx(bound, abs=1)
    press = document.get_by_role("button", name=re.compile(r"^Show all \d+ lines$"))
    if preview == "html":
        frame = document.locator("iframe").element_handle().content_frame()
        frame.get_by_role("heading", name="Document title").click()
        page.keyboard.press("PageDown")
        frame.wait_for_function("() => document.scrollingElement.scrollTop > 0")
        scroll_settled(frame)
        preview_scroll = frame.evaluate("document.scrollingElement.scrollTop")
    else:
        expect(press).to_be_visible()
    assert page.evaluate(geometry) == before

    source_tab.click()
    expect(source_panel).to_be_visible()
    assert source_panel.bounding_box()["height"] == pytest.approx(preview_height, abs=1)
    assert page.evaluate(geometry) == before
    expect(press).to_be_visible()

    preview_tab.click()
    if preview == "html":
        assert frame.evaluate("document.scrollingElement.scrollTop") == preview_scroll
    assert page.evaluate(geometry) == before

    page_data_model.cmd_data_set(serve.page_dir, "document-text", short)
    told(page)
    rendered(page)
    assert document.locator("code").text_content() == short
    if preview == "markdown":
        expect(document.get_by_role("heading", name="Short document")).to_be_visible()
        expect(press).to_have_count(0)
        assert preview_panel.bounding_box()["height"] < preview_height / 2
    else:
        expect(frame.get_by_role("heading", name="Short document")).to_be_visible()
        assert page.evaluate(geometry) == before
    after = page.evaluate(geometry)
    source_tab.click()
    expect(source_panel).to_be_visible()
    assert page.evaluate(geometry) == after


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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
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
    `--lf-top`, where the document's strip sticks. Were the frame a scroll
    container, the strip would stick at that height inside the frame, below the caption
    and over the preview's first lines."""
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
        f'source="text-{at}" class="language-python"></lf-text-document></lf-tab>'
        for at in range(3)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    for at in range(3):
        words = [*lines, f"needle_{at} = {at}"]
        page_data_model.cmd_data_set(
            serve.page_dir, f"text-{at}", "\n".join(words) + "\n"
        )
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_opening_a_closed_tab_draws_only_the_lines_in_view(request, serve, engine):
    """Opening a tab nobody opened draws only the runs of its document's lines that are
    in view, in every frame from the press on. Firefox can take the runs under the
    closed tab for drawn and keep them so as it opens, drawing every line of a long
    document for the first frames and reading and colouring every one of them
    (notes/browser-support.md, "An `auto` box under a fold in Firefox")."""
    url = serve(
        leaf_page(
            "Documents",
            '<lf-tabs id="docs" list="side">'
            '<lf-tab id="tab-open" label="Open"><p>The open tab.</p></lf-tab>'
            '<lf-tab id="tab-long" label="Long"><lf-text-document id="log" '
            'source="log-text" class="language-python"></lf-text-document></lf-tab>'
            "</lf-tabs>",
        )
    )
    text = "".join(f"value_{line} = {line}  # line {line}\n" for line in range(4000))
    page_data_model.cmd_data_set(serve.page_dir, "log-text", text)
    page = open_page(request.getfixturevalue(engine), url)
    expect(page.locator("#log.lf-rendered")).to_have_count(1)
    runs = page.locator("#log .lf-text-document-run")
    assert runs.count() > 20
    # How many runs draw their lines in each of the 20 frames from the press.
    page.evaluate("""() => {
      const runs = [...document.querySelectorAll('#log .lf-text-document-run')];
      window.drawnRuns = [];
      const frame = () => {
        window.drawnRuns.push(runs.filter((run) =>
          run.firstElementChild.checkVisibility({contentVisibilityAuto: true})).length);
        if (window.drawnRuns.length < 20) requestAnimationFrame(frame);
      };
      addEventListener('pointerdown', () => requestAnimationFrame(frame),
        {capture: true, once: true});
    }""")
    page.get_by_role("tab", name="Long", exact=True).click()
    page.wait_for_function("() => window.drawnRuns.length >= 20")
    drawn = page.evaluate("window.drawnRuns")
    assert drawn[-1] > 0, drawn
    assert max(drawn) == drawn[-1], drawn


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_closed_tab_gives_up_its_document_s_colour_and_wears_it_as_it_opens(
    request, serve, engine
):
    """A document's syntax colour stands in highlights every document on the page
    shares, so a tab that closes takes its document's colour out of them. Kept, every
    tab a reader had opened would hold its ranges there, and each scroll's uncolouring,
    and in Chromium each change to the page, would cost more for each tab opened. Opened
    again,
    the document's lines in view wear their colour in the frame that shows them, as
    when the closed tab kept it, also after a rewrite while it was closed moved those
    lines into runs of their own: Firefox can show them uncoloured for a frame or two."""
    tabs = "".join(
        f'<lf-tab id="tab-{at}" label="Doc {at}"><lf-text-document id="doc-{at}" '
        f'source="text-{at}" class="language-python"></lf-text-document></lf-tab>'
        for at in range(2)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    lines = [f"value_{line} = 'text'  # line {line}" for line in range(1000)]
    for at in range(2):
        page_data_model.cmd_data_set(
            serve.page_dir, f"text-{at}", "\n".join(lines) + "\n"
        )
    page = open_page(request.getfixturevalue(engine), url)
    expect(page.locator("lf-text-document.lf-rendered")).to_have_count(2)
    page.locator("#doc-0 .lf-text-document-run > * >> nth=140").evaluate(
        "row => row.scrollIntoView({block: 'start'})"
    )
    rendered(page)
    page.wait_for_function(TOKENS_IN, arg="#doc-0 code")

    def reopened():
        """Doc 0's rows in view and those of them without colour, read as the frame that
        shows the reopened tab paints and in the three frames after. A size observer
        made now is told of the listing's box after the document's own observer and
        the work that one queued. Chromium draws no rows in the first frames, and
        Firefox draws them in the first."""
        page.evaluate(f"""() => {{
          window.opened = [];
          const listing = document.querySelector('#doc-0 .lf-text-document-listing');
          const read = () => opened.push(({ROWS_IN_VIEW})('#doc-0'));
          const told = new ResizeObserver(() => {{
            if (!listing.checkVisibility()) return;
            told.disconnect();
            read();
            const frame = () => {{ read(); if (opened.length < 4) requestAnimationFrame(frame); }};
            requestAnimationFrame(frame);
          }});
          told.observe(listing);
        }}""")
        page.get_by_role("tab", name="Doc 0", exact=True).click()
        page.wait_for_function("() => window.opened.length >= 4")
        readings = page.evaluate("window.opened")
        assert any(shown for shown, _ in readings), readings
        assert not any(bare for _, bare in readings), readings

    page.get_by_role("tab", name="Doc 1", exact=True).click()
    page.wait_for_function(TOKENS_IN, arg="#doc-1 code")
    page.wait_for_function(f"() => !({TOKENS_IN})('#doc-0 code')")
    reopened()
    # Lines added above the place shown, while the tab is closed, put new lines there
    # and move the rows that stood there into runs a split makes.
    page.get_by_role("tab", name="Doc 1", exact=True).click()
    page.wait_for_function(f"() => !({TOKENS_IN})('#doc-0 code')")
    grown = [*lines[:101], *(f"added_{at} = {at}" for at in range(200)), *lines[101:]]
    page_data_model.cmd_data_set(serve.page_dir, "text-0", "\n".join(grown) + "\n")
    told(page)
    expect(page.locator("#doc-0 code")).to_contain_text("added_199 = 199")
    reopened()


# The rows of a text document's listing in view, and how many of them hold no syntax
# colour, found at points down the listing's box.
ROWS_IN_VIEW = """selector => {
  const pre = document.querySelector(`${selector} pre`);
  const box = pre.getBoundingClientRect();
  const coloured = new Set();
  for (const [name, highlight] of CSS.highlights)
    if (name.startsWith('lf-token-'))
      for (const range of highlight) coloured.add(range.startContainer.parentElement);
  const rows = new Set();
  for (let y = box.top + 4; y < box.bottom; y += 12) {
    const row = document.elementFromPoint(box.left + box.width / 2, y)
      ?.closest('.lf-text-document-run > *');
    if (row) rows.add(row);
  }
  return [rows.size, [...rows].filter((row) => !coloured.has(row)).length];
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_opening_a_closed_tab_reads_none_of_its_document_s_lines_for_tab_stops(
    request, serve, engine
):
    """A document's listing is a code block, which is a Tab stop from the moment it is
    first seen, in a closed tab too. So the tab's opening asks none of the listing's
    lines whether they take a Tab stop, which it asked of every line on each reach paint
    while the stop waited for the listing to be drawn, and Tab reaches the listing by its
    own stop."""
    url = serve(
        leaf_page(
            "Documents",
            '<lf-tabs id="docs" list="side">'
            '<lf-tab id="tab-open" label="Open"><p>The open tab.</p></lf-tab>'
            '<lf-tab id="tab-long" label="Long"><lf-text-document id="log" '
            'source="log-text" class="language-python"></lf-text-document></lf-tab>'
            "</lf-tabs>",
        )
    )
    text = "".join(f"value_{line} = {line}  # line {line}\n" for line in range(2000))
    page_data_model.cmd_data_set(serve.page_dir, "log-text", text)
    page = open_page(request.getfixturevalue(engine), url)
    expect(page.locator("#log.lf-rendered")).to_have_count(1)
    # Every line asked for its `tabindex` from the press until the tab has settled.
    page.evaluate("""() => {
      const lines = new Set(document.querySelectorAll('#log .lf-text-document-run > *'));
      const read = Element.prototype.getAttribute;
      window.linesAsked = 0;
      Element.prototype.getAttribute = function (name) {
        if (name === 'tabindex' && lines.has(this)) window.linesAsked++;
        return read.call(this, name);
      };
    }""")
    page.get_by_role("tab", name="Long", exact=True).click()
    listing = page.locator("#log pre")
    expect(listing).to_be_visible()
    expect(listing).to_have_attribute("tabindex", "0")
    expect(page.locator(".lf-code-copy")).to_have_count(1)
    rendered(page)
    assert page.evaluate("window.linesAsked") == 0
    page.get_by_role("tab", name="Long", exact=True).focus()
    page.keyboard.press("Tab")
    expect(page.locator("#tab-long")).to_be_focused()
    page.keyboard.press("Tab")
    expect(listing).to_be_focused()


def test_the_page_presents_without_waiting_for_a_closed_tab_s_document(browser, serve):
    """A document in a tab nobody opened draws once the page has presented, each in a
    task of its own, so presentation waits only for the document in view. Drawn first,
    many long documents in tabs would hold presentation for seconds in Firefox, which
    can then restyle every row of every closed tab as the page presents. Each announces
    its draw (`drawn`, which stamps its data's provenance) as it draws, so a comment on
    its words stands on them without waiting for the documents after it."""
    tabs = "".join(
        f'<lf-tab id="tab-{at}" label="Doc {at}"><lf-text-document id="doc-{at}" '
        f'source="text-{at}"></lf-text-document></lf-tab>'
        for at in range(3)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    for at in range(3):
        page_data_model.cmd_data_set(
            serve.page_dir, f"text-{at}", f"document {at}\n" * 40
        )
    order = """(() => {
      window.order = [];
      document.addEventListener('drawn', ({target}) => order.push('announced ' + target.id),
                                {capture: true});
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
    expect(page.locator("#doc-2 figure")).to_have_attribute("data-lf-source", "text-2")
    assert page.evaluate("order") == [
        "announced doc-0",
        "doc-0",
        "presented",
        "announced doc-1",
        "doc-1",
        "announced doc-2",
        "doc-2",
    ]


# Closed tabs' documents draw once the page has presented, one a task after a
# zero-delay timeout (lf-text-document.js, `drawLater`). Stretching those timeouts from
# presentation on holds each document's draw back long enough to act while the queue
# runs.
HOLD_QUEUE = """(() => {
  const timeout = window.setTimeout;
  window.setTimeout = (fn, ms, ...rest) => timeout(fn,
    !ms && window.holdQueue && String(fn).includes('[native code]') ? window.holdQueue : ms,
    ...rest);
  new MutationObserver(() => {
    if (document.body?.hasAttribute('data-lf-presented') && window.holdQueue === undefined)
      window.holdQueue = 2000;
  }).observe(document, {attributes: true, subtree: true,
                        attributeFilter: ['data-lf-presented']});
})()"""


def closed_documents(serve, count):
    """A page of `count` tabs, each a document bound to its own source of distinct
    lines; Doc 0's tab is open."""
    tabs = "".join(
        f'<lf-tab id="tab-{at}" label="Doc {at}"><lf-text-document id="doc-{at}" '
        f'source="text-{at}"></lf-text-document></lf-tab>'
        for at in range(count)
    )
    url = serve(
        leaf_page("Documents", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )
    for at in range(count):
        lines = "".join(f"line {line} of document {at}\n" for line in range(40))
        page_data_model.cmd_data_set(serve.page_dir, f"text-{at}", lines)
    return url


def test_a_comment_on_a_closed_tab_s_document_never_reads_as_earlier_data(
    browser, serve
):
    """A comment on the text of a document in a closed tab stands on the document
    while the document has yet to report its draw, and says nothing about earlier
    data: the comment is on the data the document will draw. Read as a revision
    mismatch, it would say "Earlier data" for the seconds before the document drew."""
    url = closed_documents(serve, 3)
    comment = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is line 7 right?",
            "anchor": {
                "section": "doc-2",
                "datum": "document",
                "identity": "document",
                "source": "text-2",
                "source_revision": source_revision(serve.page_dir, "text-2"),
                "quote": "line 7 of document 2",
            },
        },
    )
    seen = """(() => {
      window.earlier = false;
      new MutationObserver(() => {
        for (const status of document.querySelectorAll('.lf-anchor-status'))
          if (status.textContent.includes('Earlier data')) window.earlier = true;
      }).observe(document, {childList: true, subtree: true, characterData: true});
    })()"""
    page = open_page(browser, url, init_script=HOLD_QUEUE + ";" + seen, upgraded=False)
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    quote = open_panel_thread(page, comment["id"]).locator(".lf-thread-quote")
    expect(quote).to_be_visible()
    expect(page.locator("#doc-2")).not_to_have_class("lf-rendered")
    expect(quote).not_to_contain_text("Earlier data")
    expect(page.locator("#doc-2 figure")).to_have_attribute("data-lf-source", "text-2")
    assert not page.evaluate("window.earlier")


def test_a_listing_s_scroll_mark_changes_nothing_its_rows_inherit(browser, serve):
    """The runtime marks a following document's listing as a box that scrolls once it
    has drawn, and the mark restarts the sticky-header slot. The listing states that
    restart from the first paint, so the mark changes nothing its rows inherit: Firefox
    styles the rows of runs it doesn't draw too, and a mark that changed inherited
    values would take a long frame on a long listing. The listing's `code`, which every
    row inherits from, computes the same style, custom properties included, with the
    mark and without it, whatever the mark's rule sets."""
    url = serve(
        leaf_page(
            "Log",
            '<lf-text-document id="log" source="log-text" data-bound="end">'
            "</lf-text-document>",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "a line\n" * 400)
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
    page_data_model.cmd_data_set(serve.page_dir, "first-text", "# First original\n")
    page_data_model.cmd_data_set(serve.page_dir, "second-text", "# Second original\n")
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
    page_data_model.cmd_data_set(serve.page_dir, "first-text", updated)
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
    page_data_model.cmd_data_set(serve.page_dir, "document-text", text)
    out = tmp_path / "document.html"
    exporting_model.cmd_export(serve.page_dir, out, None, runtime=True)
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
    page_data_model.cmd_data_set(serve.page_dir, "html-text", text)
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
    page_data_model.cmd_data_set(serve.page_dir, "html-text", updated)
    holding(page, held, 1, "the HTML preview's stylesheet")
    assert (
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness()"
        )
        is not None
    )
    # A rerun publishes a new receipt without changing its value revision, even
    # while the frame's stylesheet is loading. The reading keeps that load pending.
    page_data_model.cmd_data_set(serve.page_dir, "html-text", updated)
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
    plain document, in one whose tokens split the text into coloured spans, and in a
    Markdown preview's coloured code block or list."""
    tags = (
        '<lf-text-document id="plain-document" source="plain-text"></lf-text-document>'
        '<lf-text-document id="python-document" source="python-text" class="language-python">'
        "</lf-text-document>"
        '<lf-text-document id="markdown-document" source="markdown-text" '
        'label="NOTES.md" preview="markdown"></lf-text-document>'
        '<lf-text-document id="markdown-list" source="markdown-list" '
        'label="LIST.md" preview="markdown"></lf-text-document>'
    )
    source = LONG_LINE_DIFF_PAGE.replace(
        '<lf-diff id="patch" source="review-patch"></lf-diff>', tags
    )
    url = serve(source)
    for name in SELECTED_TEXTS:
        page_data_model.cmd_data_set(serve.page_dir, name, SELECTED_TEXTS[name][0])
    page = open_page(browser, url)
    for document, name in (
        ("#plain-document", "plain-text"),
        ("#python-document", "python-text"),
        ("#markdown-document .lf-text-document-preview", "markdown-text"),
        ("#markdown-list .lf-text-document-preview", "markdown-list"),
    ):
        refresh_keeps_selection(page, serve, document, name)


# Each source before and after a change beside its selected word.
CODE_TEXTS = ('first = "old"\nsecond = "selected"\n', 'first = "new beginning"\n')
SELECTED_TEXTS = {
    "plain-text": CODE_TEXTS,
    "python-text": CODE_TEXTS,
    "markdown-text": (
        'First, old.\n\n```python\nsecond = "selected"\n```\n',
        "First, new beginning.\n",
    ),
    "markdown-list": (
        '- First, old.\n- Second:\n\n  ```python\n  second = "selected"\n  ```\n',
        "- First, new beginning.\n",
    ),
}


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
    old, changed = SELECTED_TEXTS[name]
    page_data_model.cmd_data_set(serve.page_dir, name, changed + old.split("\n", 1)[1])
    told(page)
    rendered(page)
    expect(page.locator(document)).to_contain_text(changed.strip("-\n "))
    assert page.evaluate(reading) == before, document


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_text_document_update_keeps_a_selection_it_carries_into_another_run(
    request, serve, engine
):
    """Lines added above a selected row carry it from one run of rows into another, and
    it keeps its native selection: runs are a drawing boundary, not a row's identity.
    Reconciled run by run, one line added above the last row of a run can grow
    Chromium's selection to take in the row before it and clear Firefox's. The selected
    row keeps it too when its own line is edited, in place or as it moves, where a walk
    over the lines would take the edit for a new row. The numbers still count every
    row, read in Chromium off what it draws: a count started on each run's own box would
    number every run after the first from 1."""
    lines = [f"line {i}" for i in range(1, 279)]
    lines[127] = "selected passage"
    url = serve(
        leaf_page(
            "Run edges",
            '<h1>Run log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    page = open_page(request.getfixturevalue(engine), url)
    select_words(page, f"{ROWS} >> nth=127")
    selected = page.evaluate("() => getSelection().toString()")
    assert "selected passage" in selected
    for added, edit in ((1, ""), (0, ", edited"), (200, " twice")):
        at = next(i for i, line in enumerate(lines) if line.startswith("selected"))
        lines[at] += edit
        lines = [f"added {added} {i}" for i in range(added)] + lines
        page_data_model.cmd_data_set(
            serve.page_dir, "log-text", "\n".join(lines) + "\n"
        )
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


# What changes to the rows of `#log` since the last reading: the rows whose text
# changed, how many rows runs gained and lost, and how many runs did.
ROW_CHANGES = """() => {
  const code = document.querySelector('#log code');
  if (!window.rowChanges) {
    window.rowRecords = [];
    new MutationObserver((records) => rowRecords.push(...records))
      .observe(code, {childList: true, characterData: true, subtree: true});
    window.rowChanges = () => {
      const changes = {edited: new Set(), added: 0, removed: 0, runs: new Set()};
      for (const record of rowRecords.splice(0)) {
        if (record.target.parentElement === code) {
          changes.added += record.addedNodes.length;
          changes.removed += record.removedNodes.length;
          changes.runs.add(record.target);
        } else if (record.target !== code) {
          const row = record.target.nodeType === Node.ELEMENT_NODE
            ? record.target : record.target.parentElement;
          if (row?.isConnected) changes.edited.add(row.textContent);
        }
      }
      return {...changes, edited: [...changes.edited], runs: changes.runs.size};
    };
  }
  return window.rowChanges();
}"""


def test_a_text_document_rewrite_changes_only_the_rows_of_the_lines_it_changes(
    browser, serve
):
    """A new text changes only the rows of the lines it changes: an edited line's row
    keeps its node and takes the edit as its text's least change, and a line added or
    removed adds or removes its own row where it stands, leaving every other row in its
    run. The runs after it count their numbers on from where they now start. Reconciled
    over every row, a one-line rewrite of a long document would be slow, and lines added
    near the top would move as many rows across each later run's edge. The numbers
    still count every row, read in Chromium off what it draws, a line added at the head
    of a run the browser skips included: where rows move across runs' edges, a run after
    them could draw no number on its first row and count on from 1. A rewrite past the
    line walk's cap that moves and reindents every line keeps a selection on its words:
    with each row patched with the line at its place, the selected row would take
    another line's."""
    lines = [f"line {at}" for at in range(1, 1001)]
    url = serve(
        leaf_page(
            "Rewrites",
            '<h1>Run log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    page = open_page(browser, url)
    expect(page.locator("#log .lf-text-document-run")).to_have_count(8)
    page.evaluate(ROW_CHANGES)
    edited = [*lines]
    edited[500] = "line 501, edited"
    # At the head of the third run, which the browser skips.
    added = [*edited[:256], "added line", *edited[256:]]
    removed = [*added[:300], *added[301:]]
    grown = [*removed[:600], *[f"grown {at}" for at in range(100)], *removed[600:]]
    for text, changes in (
        (
            edited,
            {"edited": ["line 501, edited\n"], "added": 0, "removed": 0, "runs": 0},
        ),
        (added, {"edited": [], "added": 1, "removed": 0, "runs": 1}),
        (removed, {"edited": [], "added": 0, "removed": 1, "runs": 1}),
        (grown, {"edited": [], "added": 100, "removed": 0, "runs": 1}),
    ):
        page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(text) + "\n")
        told(page)
        rendered(page)
        assert page.locator("#log code").text_content() == "\n".join(text) + "\n"
        assert page.evaluate(ROW_CHANGES) == changes
    # A run filled to twice its rows splits, and the text stays whole.
    runs = page.locator("#log .lf-text-document-run").count()
    split = [*grown[:600], *[f"split {at}" for at in range(200)], *grown[600:]]
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(split) + "\n")
    told(page)
    rendered(page)
    assert page.locator("#log code").text_content() == "\n".join(split) + "\n"
    assert page.locator("#log .lf-text-document-run").count() > runs
    # The added line and the last lines, past every change, are numbered as their
    # places.
    for shown in (257, len(split)):
        page.locator(ROWS).nth(shown - 1).evaluate(
            "row => row.scrollIntoView({block: 'center'})"
        )
        rendered(page)
        drawn = drawn_numbers(page, "log")
        assert shown in dict(drawn), drawn
        assert all(text == str(line) for line, text in drawn), drawn
    # Past the walk's cap: a line added at the top and every line indented.
    select_words(page, f"{ROWS} >> nth=1000")
    selected = page.evaluate("() => getSelection().toString()").strip()
    assert selected == split[1000], selected
    indented = ["# added", *(f"    {line}" for line in split)]
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(indented) + "\n")
    told(page)
    rendered(page)
    assert page.locator("#log code").text_content() == "\n".join(indented) + "\n"
    assert page.evaluate("() => getSelection().toString()").strip() == selected
    # Past the cap again with every line in its place, so each run keeps its first
    # line and first row: the rows still count their places.
    reindented = [f"  {line}" for line in indented]
    page_data_model.cmd_data_set(
        serve.page_dir, "log-text", "\n".join(reindented) + "\n"
    )
    told(page)
    rendered(page)
    page.locator(ROWS).nth(1000).evaluate(
        "row => row.scrollIntoView({block: 'center'})"
    )
    rendered(page)
    drawn = drawn_numbers(page, "log")
    assert 1001 in dict(drawn), drawn
    assert all(text == str(line) for line, text in drawn), drawn


# The syntax colour of rows 250 to 262 of `#log`: for each, the highlights over its
# text and where each starts and ends in it.
ROW_COLOURS = """() => {
  const rows = [...document.querySelectorAll('#log .lf-text-document-run > *')].slice(250, 263);
  const found = rows.map(() => []);
  for (const [name, highlight] of CSS.highlights)
    for (const range of highlight) {
      const at = rows.indexOf(range.startContainer.parentElement);
      if (at >= 0) found[at].push([name, range.startOffset, range.endOffset]);
    }
  return found.map((row) => row.sort((a, b) => a[1] - b[1]));
}"""


def test_a_split_run_colours_from_its_own_grammar_state(browser, serve):
    """A run a rewrite splits is coloured from the grammar state its new parts start in,
    as a fresh load colours it: a triple-quoted string opened above the split and closed
    below it keeps its rows a string after an edit below the split. Kept by its place,
    the state of the run that stood second before the rewrite would colour the second
    part, which starts inside the string, as code."""
    lines = [f"value_{at} = {at}" for at in range(600)]
    url = serve(
        leaf_page(
            "Split colour",
            '<lf-text-document id="log" source="log-text" class="language-python">'
            "</lf-text-document>",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(lines) + "\n")
    page = open_page(browser, url)
    # 122 lines in the second run, which grows to 250 rows, with a string over lines
    # 250 to 260.
    block = [
        'doc = """opening'
        if at == 250
        else 'closing"""'
        if at == 260
        else f"inside the string {at}"
        if 250 < at < 260
        else f"item_{at} = {at}"
        for at in range(140, 262)
    ]
    grown = [*lines[:140], *block, *lines[140:]]
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(grown) + "\n")
    told(page)
    rendered(page)
    page.locator(ROWS).nth(258).evaluate("row => row.scrollIntoView({block: 'center'})")
    rendered(page)
    page.wait_for_function(f"() => ({ROW_COLOURS})()[8].length")
    # Ten lines added below the split point: the run splits at line 256, and the new
    # text's first change, at line 328, falls in its second part.
    split = [*grown[:328], *(f"added_{at} = {at}" for at in range(10)), *grown[328:]]
    page_data_model.cmd_data_set(serve.page_dir, "log-text", "\n".join(split) + "\n")
    told(page)
    rendered(page)
    fresh = open_page(browser, url)
    fresh.locator(ROWS).nth(258).evaluate(
        "row => row.scrollIntoView({block: 'center'})"
    )
    rendered(fresh)
    # Row 258 is a string's once its run is coloured from the state it starts in.
    fresh.wait_for_function(
        f"() => ({ROW_COLOURS})()[8].some(([name]) => name.includes('string'))"
    )
    expected = fresh.evaluate(ROW_COLOURS)
    page.wait_for_function(
        f"() => ({ROW_COLOURS})()[8].some(([name]) => name.includes('string'))"
    )
    assert page.evaluate(ROW_COLOURS) == expected


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


def test_an_excerpt_shows_and_answers_to_its_source_line_numbers(browser, serve):
    """An lf-code body with `lines` is a quotation from a longer file. What the user
    reads is the file's own numbering: the gutter counts from where the quote starts
    and jumps where it skips, each skip stands as an elided row saying how much is
    left out, and the gutter widens so four digits still leave a note's card under its
    line's first character. Everything that points into the block — `hi`, a note's `at`, a key
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
<lf-code id="walk" lines="1505-1507,1550-1552" hi="1550"><pre><code class="language-rust">
fn merge_sort()
{
    let len = v.len();
    while end &gt; 0 {
        let mut start = end - 1;
        start -= 1;
</code></pre>
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

    # The note on 1551 hangs from that line's first character, past its indent, so its
    # card's left edge stands under the `let` it explains.
    code_x, key_x, card_x = page.evaluate(
        """() => {
          const start = (node) => {
            const range = document.createRange();
            range.setStart(node.firstChild.firstChild ?? node.firstChild, 0);
            return range.getBoundingClientRect().left;
          };
          const line = document.querySelector('#walk [data-lf-line="1551"]');
          const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
          let key = null;
          for (let node = walker.nextNode(); node && !key; node = walker.nextNode()) {
            const at = node.data.search(/\\S/);
            if (at < 0) continue;
            key = document.createRange();
            key.setStart(node, at);
            key.setEnd(node, at + 1);
          }
          const note = document.querySelector('#walk pre > lf-note');
          const card = note.getBoundingClientRect().left
            + parseFloat(getComputedStyle(note, '::before').left);
          return [start(document.querySelector('#walk .lf-code-line')),
                  key.getBoundingClientRect().left, card];
        }"""
    )
    assert key_x > code_x + 1, (code_x, key_x)
    assert abs(card_x - key_x) < 1, (key_x, card_x)

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
<lf-code id="walk"><pre><code class="language-python">
def ceiling(limit):
{call}
{digest}
</code></pre></lf-code>
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


def test_a_reader_hides_a_blocks_notes_to_read_its_code_whole(browser, serve):
    """A block with notes offers a mark beside Copy in its toolbar, and `n` while the
    reader is on the block, so they can read the code without the cards between its
    lines. The toolbar takes no room and shows only while the pointer is on the block.
    A hidden note's line keeps its number in the accent, so the reader still sees where
    the notes were. The choice is the tab's reading state, as wrapping is: it holds
    across a reload, and paper shows the notes whatever the screen chose. A block
    without notes keeps Copy alone."""
    url = serve(
        leaf_page(
            "notes",
            """
<h1 id="t">Brackets</h1>
<lf-code id="walk"><pre><code class="language-python">
def bracket(temp):
    if temp &lt; 0:
        return "steel"
    return "cedar"
</code></pre>
<lf-note id="freeze" at="2">Freezing is the only threshold that matters.</lf-note>
</lf-code>
<lf-code id="plain"><pre><code class="language-python">
print("no notes")
</code></pre></lf-code>
""",
        ),
    )
    page = open_page(browser, url)
    bar = page.locator("#walk > .lf-code-bar")
    toggle = bar.locator(".lf-code-notes-toggle")
    note = page.locator("#freeze")
    number = page.locator('#walk [data-lf-line="2"]')
    # Notes first, Copy last, on one toolbar; a block without notes keeps Copy alone.
    expect(bar.locator(":scope > *")).to_have_count(2)
    assert bar.locator(":scope > *").evaluate_all(
        "marks => marks.map(m => m.getAttribute('aria-label'))"
    ) == ["Hide notes", "Copy"]
    expect(page.locator("#plain .lf-code-bar")).to_have_count(0)
    expect(page.locator("#plain .lf-code-copy")).to_have_count(1)
    expect(note).to_be_visible()
    page.mouse.move(0, 0)
    expect(bar).to_have_css("opacity", "0")
    shown = number.evaluate("line => getComputedStyle(line, '::before').color")

    page.locator("#walk pre").hover()
    expect(bar).to_have_css("opacity", "1")
    toggle.click()
    expect(toggle).to_have_attribute("aria-label", "Show 1 note")
    expect(note).to_be_hidden()
    assert number.evaluate("line => getComputedStyle(line, '::before').color") != shown

    page.locator("#walk pre").focus()
    page.keyboard.press("n")
    expect(toggle).to_have_attribute("aria-label", "Hide notes")
    expect(note).to_be_visible()

    page.keyboard.press("n")
    expect(note).to_be_hidden()
    # Copy, the toolbar's last mark, copies the code without the note's words.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator("#walk pre").hover()
    bar.get_by_role("button", name="Copy").click()
    assert page.evaluate("navigator.clipboard.readText()") == (
        'def bracket(temp):\n    if temp < 0:\n        return "steel"\n    return "cedar"'
    )
    page.reload()
    wait_until_ready(page)
    expect(page.locator("#walk .lf-code-notes-toggle")).to_have_attribute(
        "aria-label", "Show 1 note"
    )
    expect(page.locator("#freeze")).to_be_hidden()
    page.emulate_media(media="print")
    expect(page.locator("#freeze")).to_be_visible()
