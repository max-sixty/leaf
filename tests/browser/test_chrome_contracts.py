"""Everyday browser contracts for shared chrome."""

import io
import json
from types import SimpleNamespace
from urllib.parse import urljoin

import pytest
from interact_support import append_carried_log_record
from leaf.media import store_uploaded_media
from leaf.render_checks import rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
    panel_comment,
)
from render_cases_layout import (
    toggle_queue,
    with_one_obligation,
)
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    resized,
    select,
    selection_field,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread


def test_another_threads_reply_keeps_the_selected_thread_in_place(browser, serve):
    """A reply arriving in another thread moves nothing in the thread open in the
    panel: its last message stays where the reader left it."""
    url = serve(LONG_PAGE)
    other = panel_comment(serve.page_dir, "An earlier thread.")
    selected = panel_comment(serve.page_dir, "The selected thread.")
    for index in range(14):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Selected answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    view = open_panel_thread(page, selected)
    last_selected = view.locator(".lf-msg").last
    last_selected.scroll_into_view_if_needed()
    rendered(page)
    before = last_selected.evaluate("el => el.getBoundingClientRect().top")

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": other,
            "text": "This belongs to the other thread. " * 5,
        },
    )
    told(page)
    rendered(page)
    expect(view).to_be_visible()
    assert last_selected.evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(before, abs=2)


class _ProblemPage:
    url = "https://leaf.test/example"
    context = SimpleNamespace(
        browser=SimpleNamespace(browser_type=SimpleNamespace(name="chromium"))
    )

    def add_init_script(self, **_):
        pass

    def expose_binding(self, *_):
        pass

    def on(self, *_):
        pass


def test_live_revision_retains_the_runtime_favicon(browser, serve):
    """In-place activation keeps the runtime-owned tab status surface."""
    second = LONG_PAGE.replace("<title>long</title>", "<title>second</title>")
    page = open_page(browser, live_url(serve(LONG_PAGE)))
    page.evaluate(
        "() => { window.__lfFavicon = document.querySelector('link[rel=icon]'); }"
    )

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("second")
    assert page.evaluate(
        """() => window.__lfFavicon ===
          document.querySelector('link[rel=icon][data-lf-runtime]')"""
    ), "in-place activation replaced or removed the runtime favicon"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_margin_reply_shares_its_threads_opaque_surface(browser, serve, scheme):
    """The reply surround stays continuous as focus enters and leaves the thread.

    An opaque shared surface also lets a pinned reply cover scrolled messages without
    introducing a differently colored band above its input.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, color_scheme=scheme)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    thread = preview.locator(".lf-page-thread")
    surround = thread.locator(".lf-thread-reply")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_visible()

    for state in ("resting", "editing", "outside"):
        if state == "editing":
            reply.click()
            expect(reply).to_be_focused()
        elif state == "outside":
            preview.get_by_role("button", name="Dismiss thread").focus()
        surface = thread.evaluate("""node => {
          const color = getComputedStyle(node).backgroundColor;
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 1;
          const paint = canvas.getContext('2d');
          paint.fillStyle = color;
          paint.fillRect(0, 0, 1, 1);
          return {color, alpha: paint.getImageData(0, 0, 1, 1).data[3]};
        }""")
        assert surface["alpha"] == 255, (scheme, state, surface)
        expect(surround).to_have_css("background-color", surface["color"])


def test_a_compact_comment_reserves_only_the_room_send_occupies(browser, serve):
    """At a narrow allocation, Space must not create a blank line while the
    words and Send still fit. The text's right inset already clears part of
    Send's hit box; reserving its full width again wasted eleven pixels."""
    page = open_page(
        browser,
        serve(
            leaf_page("Compact comment", '<p id="passage">A passage to comment on.</p>')
        ),
    )
    resized(page, 346, 900)
    page.locator("#passage").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.insert_text("this is a nice feature; is it in leaf, or you")
    rendered(page)
    before = field.bounding_box()
    page.keyboard.press("Space")
    rendered(page)
    after = field.bounding_box()
    assert after["height"] == pytest.approx(before["height"], abs=1)
    assert after["y"] == pytest.approx(before["y"], abs=1)
    reservation = field.evaluate("""el => {
      const style = getComputedStyle(el), box = el.getBoundingClientRect();
      const send = el.parentElement.querySelector('.lf-compose-submit').getBoundingClientRect();
      return {textEnd: box.right - parseFloat(style.borderInlineEndWidth)
        - parseFloat(style.paddingInlineEnd)
        - parseFloat(style.getPropertyValue('--lf-field-end-room')),
        sendStart: send.left};
    }""")
    assert reservation["textEnd"] == pytest.approx(reservation["sendStart"], abs=0.1)


# Two threads put the card's navigation on the row too, which a finger's larger
# controls leave least room for.
@pytest.mark.parametrize(("touch", "thread_count"), [(False, 1), (True, 2)])
def test_page_thread_dismiss_and_resolve_share_the_metadata_row(
    browser, serve, thread_count, touch
):
    context = browser.new_context(
        viewport={"width": 900, "height": 844}, is_mobile=touch, has_touch=touch
    )
    url = serve(LONG_PAGE)
    for index in range(thread_count):
        panel_comment(serve.page_dir, f"Comment {index}.", {"section": "p0"})
    page = open_page(browser, url, context=context)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').first.click()
    preview = page.locator(".lf-margin-preview:not([hidden])")
    resolve = preview.get_by_role("button", name="Resolve thread")
    dismiss = preview.get_by_role("button", name="Dismiss thread view")
    expect(resolve).to_be_visible()
    expect(dismiss).to_be_visible()
    assert dismiss.evaluate(
        "button => button.closest('.lf-margin-thread-controls') !== null"
    )
    centers = preview.evaluate(
        """preview => ['.lf-resolve', '.lf-margin-preview-close'].map(selector => {
          const rect = preview.querySelector(selector).getBoundingClientRect();
          return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
        })"""
    )
    assert centers[0]["y"] == pytest.approx(centers[1]["y"], abs=1), centers
    assert centers[0]["x"] < centers[1]["x"]
    if thread_count == 2:
        row = preview.evaluate(
            """preview => {
              const actions = preview.querySelector('.lf-margin-thread-controls');
              const head = preview.querySelector('.lf-thread-transcript .lf-msg-head');
              const box = selector => preview.querySelector(selector)
                .getBoundingClientRect();
              const middle = selector => box(selector).y + box(selector).height / 2;
              return {
                nav: middle('.lf-margin-preview-nav'),
                author: middle('.lf-thread-transcript .lf-msg-head > b'),
                actions: middle('.lf-thread-meta-actions'),
                authorRight: head.getBoundingClientRect().right
                  - parseFloat(getComputedStyle(head).paddingInlineEnd),
                navLeft: box('.lf-margin-preview-nav').left,
                navRight: box('.lf-margin-preview-nav').right,
                resolveLeft: box('.lf-resolve').left,
                overflow: actions.scrollWidth - actions.clientWidth
                  + head.scrollWidth - head.clientWidth,
              };
            }"""
        )
        assert row["nav"] == pytest.approx(row["actions"], abs=1), row
        assert row["author"] == pytest.approx(row["actions"], abs=1), row
        assert row["authorRight"] < row["navLeft"], row
        assert row["navRight"] < row["resolveLeft"], row
        assert row["overflow"] == 0, row
    dismiss.focus()
    resized(page, 1000, 844)
    expect(dismiss).to_be_focused()
    resolve.focus()
    page.keyboard.press("Tab")
    expect(dismiss).to_be_focused()


PHONE_PAGE = leaf_page(
    "phone",
    "<h1 id='t'>Phone</h1><p id='p1'>Paragraph one. " + "Filler. " * 40 + "</p>",
)


PHONE_READING_PAGE = leaf_page(
    "phone reading",
    "<h1 id='t'>Phone</h1>"
    + "<aside class='sidenote'><lf-draft id='note'><pre>A draft set in the sidenote's"
    " type.</pre></lf-draft></aside>"
    + "".join(
        f"<p id='p{n}'>Paragraph {n}. "
        + "Filler words for the reading column. " * 8
        + "</p>"
        for n in range(12)
    ),
)


def test_a_phone_comment_field_keeps_its_passage_clear(iphone, serve):
    """Phone fields keep their text size and stand clear of a selected paragraph.

    Safari zooms the page onto a text field set under 16px as the field takes focus, and
    leaves it zoomed: tapping the field jumped the view, then left the user panning
    sideways across a page wider than the screen. So no field the page holds is smaller,
    and a draft, whose editor wears the words' own face, shows them on the same floor, or
    one set in a sidenote's smaller type opens a size larger than it showed.

    With too little room below, the field stands above without scrolling the page.
    This emulation cannot show the native iOS
    selection menu, whose placement needs actual-device verification."""
    page = open_page(None, serve(PHONE_READING_PAGE), context=iphone)
    # Every field in the composed tree, the vendored controls' own native fields in
    # their shadow roots included: the Threads find box and the Map's search are
    # native inputs, and Safari zooms onto smaller fields.
    sizes = page.evaluate("""() => {
      const sizes = {};
      const walk = (root) => {
        for (const node of root.querySelectorAll('*')) {
          if (node.matches('input, textarea, leaf-text, select')) {
            const host = node.getRootNode().host;
            const name = (host ?? node).localName + '.' + ((host ?? node).className || '');
            sizes[name] = Math.min(
              sizes[name] ?? Infinity, parseFloat(getComputedStyle(node).fontSize));
          }
          if (node.shadowRoot) walk(node.shadowRoot);
        }
      };
      walk(document);
      return sizes;
    }""")
    assert any(name.startswith("input.lf-search-field") for name in sizes), sizes
    assert min(sizes.values()) >= 16, sizes
    note = page.locator("#note")
    shown = note.locator(".lf-draft-body").evaluate(
        "body => parseFloat(getComputedStyle(body).fontSize)"
    )
    note.locator(".lf-draft-body").tap()
    editing = note.locator(".lf-draft-edit").evaluate(
        "field => parseFloat(getComputedStyle(field).fontSize)"
    )
    assert shown == editing >= 16, (shown, editing)
    page.keyboard.press("Escape")
    # Close returns focus to the persistent Edit control. Complete that handoff
    # before installing the next native selection, which WebKit focus collapses.
    expect(note.get_by_role("button", name="Edit", exact=True)).to_be_focused()

    page.locator("#p6").evaluate("""paragraph => {
      const box = paragraph.getBoundingClientRect();
      document.scrollingElement.scrollTop += box.bottom - (innerHeight - 20);
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph 6".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    # A finger's selection is quoted in the panel's field, a tap on which comments on
    # it.
    comment = selection_field(page)
    box = comment.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    before_scroll = page.evaluate("scrollY")
    comment.tap()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    placed = page.evaluate("""() => {
      const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
      const paragraph = document.getElementById('p6').getBoundingClientRect();
      return {barTop: bar.top, barBottom: bar.bottom, paragraphTop: paragraph.top};
    }""")
    assert page.evaluate("scrollY") == before_scroll
    assert placed["barBottom"] <= placed["paragraphTop"], placed
    assert placed["barTop"] >= 0, placed
    assert placed["barBottom"] <= page.evaluate("innerHeight"), placed


ORDERED_PAGE = leaf_page(
    "ordered",
    "<h1 id='t'>Ordered</h1><p id='p1'>One paragraph.</p>",
    head="""<script type="module">
import "/runtime/widget-api.js";
window.__leafReadyHeard = false;
document.addEventListener("DOMContentLoaded", () => {
  window.__leafReadyHeard = true;
});
</script>""",
)


def test_a_page_module_importing_the_widget_api_hears_dom_content_loaded(
    browser, serve
):
    """A page module runs before `DOMContentLoaded`, as every deferred module does.

    Pages wire their behavior on that event. The widget API sits over the runtime's
    stylesheets, so an await at module scope anywhere under it starts the page module
    after the event instead, and a listener like this one never hears it."""
    page = open_page(browser, serve(ORDERED_PAGE))
    assert page.evaluate("() => window.__leafReadyHeard")


def test_script_region_moves_reload_without_leaving_duplicate_nodes(browser, serve):
    """Retained scripts and main's patched scripts have distinct document lifetimes."""
    script = (
        '<script id="page-behavior" type="module">'
        "window.pageRuns = (window.pageRuns || 0) + 1;</script>"
    )
    source = leaf_page("Script lifetime", '<p id="words">Original words.</p>')
    head = source.replace("</head>", script + "</head>")
    main = source.replace("</main>", script + "</main>")
    tail = source.replace("</body>", script + "</body>")
    page = open_page(browser, live_url(serve(head)))
    origin = page.evaluate("performance.timeOrigin")
    for revision, html, region, reloads in [
        (2, main, "main", True),
        (3, main.replace(script, f"<div>{script}</div>"), "div", False),
        (4, tail, "body", True),
        (5, tail.replace("Original words.", "Revised words."), "body", False),
    ]:
        stamp_page(serve.page_dir, html, "Revise script placement or prose")
        wait_for_revision(page, revision)
        next_origin = page.evaluate("performance.timeOrigin")
        assert (next_origin != origin) == reloads
        origin = next_origin
        expect(page.locator("#page-behavior")).to_have_count(1)
        assert (
            page.locator("#page-behavior").evaluate("el => el.parentElement.localName")
            == region
        )
        assert page.evaluate("window.pageRuns") == 1
    expect(page.locator("#words")).to_have_text("Revised words.")


@pytest.mark.parametrize("mode", ["overlay", "page"])
def test_the_delivered_stylesheets_read_exactly_as_their_files_do(browser, serve, mode):
    """Delivered sheets parse like their captured files in document and shadow stages.

    Page mode carries and constructs no physical annotation sheet, while shared paint
    still reaches both trees. The selected overlay adds its actual annotation sheets.
    """
    page = open_page(
        browser, serve(LONG_PAGE.replace("<body>", f'<body data-annotations="{mode}">'))
    )
    layer = urljoin(
        page.url,
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').dataset.lfEntry"
        ),
    )
    files = {}
    names = ["chrome", "marks"]
    if mode == "overlay":
        names.extend(["annotation-chrome", "annotation-marks"])
    for name in names:
        directory = (
            "runtime/annotation-overlay"
            if name.startswith("annotation-")
            else "runtime"
        )
        answer = page.request.get(urljoin(layer, f"{directory}/{name}.css"))
        assert answer.ok, answer.status
        files[name] = answer.text()

    readings = page.evaluate(
        """async (files) => {
          const rules = (sheet) => [...sheet.cssRules].map((rule) => rule.cssText);
          const fromFile = (text) => {
            const sheet = new CSSStyleSheet();
            sheet.replaceSync(text);
            return rules(sheet);
          };
          const { chromeSheet: chrome, marksSheet: marks, annotationSheets,
            annotationMarkSheets } =
            await window.__lfCheckApi();
          if (![chrome, marks, ...annotationSheets].every(sheet => document.adoptedStyleSheets.includes(sheet)))
            throw new Error("The document did not adopt its chrome and marks sheets");
          const {shadowStage}=await window.__lfWidgetApi();
          const host=document.createElement('div'); document.querySelector('main').append(host);
          const root=shadowStage(host,[document.createTextNode('A declared shadow stage')]);
          if (![marks,...annotationMarkSheets].every(sheet=>root.adoptedStyleSheets.includes(sheet)))
            throw new Error('The shadow stage did not adopt its selected marks');
          if (annotationSheets.length !== (files['annotation-chrome'] ? 2 : 0) ||
              annotationMarkSheets.length !== (files['annotation-marks'] ? 1 : 0))
            throw new Error('The document constructed an unselected annotation sheet');
          const answer = {
            chrome: {delivered: rules(chrome), file: fromFile(files.chrome)},
            marks: {delivered: rules(marks), file: fromFile(files.marks)},
          };
          if (annotationSheets.length) {
            answer['annotation-chrome']={delivered:rules(annotationSheets[0]),file:fromFile(files['annotation-chrome'])};
            answer['annotation-marks']={delivered:rules(annotationMarkSheets[0]),file:fromFile(files['annotation-marks'])};
          }
          return answer;
        }""",
        files,
    )
    for name, reading in readings.items():
        assert reading["delivered"], f"the page adopted no {name} rules"
        assert reading["delivered"] == reading["file"], name
    carrier = page.locator("script[data-lf-sheets]").text_content()
    selected = json.loads(carrier)
    assert ("annotations" in selected) == (mode == "overlay")
    assert page.locator("style[data-lf-annotation-theme]").count() == (
        mode == "overlay"
    )
    if mode == "page":
        assert ".lf-margin-cluster" not in carrier
        assert ".lf-visual-mark {" not in carrier
        assert "::highlight(lf-mark)" not in carrier
        assert ".lf-margin-preview { position: fixed" not in carrier
    assert ".lf-aim {" in selected["chrome"]
    assert ".lf-target-trace {" in selected["chrome"]
    assert ".lf-drawing-mark path" in selected["chrome"]
    assert "::highlight(lf-version-insert)" in selected["marks"]


def test_indication_defaults_yield_to_widget_faces_in_document_and_shadow(
    browser, serve
):
    """A widget can choose its indication face in either kind of rendering root.

    Ordinary indicated elements still get the shared contour. The default must
    yield to layered widget rules, while action-target apparatus keeps its face.
    """
    page = open_page(
        browser, serve(leaf_page("indication-faces", '<h1 id="t">Indication</h1>'))
    )
    readings = page.evaluate(
        """async () => {
          const {shadowStage} = await window.__lfWidgetApi();
          const {inBaseLayer} = await window.__lfWidgetApi();
          const nodes = () => {
            const style = document.createElement('style');
            style.textContent = inBaseLayer('.custom-indication, .lf-action-target { outline: 4px dashed red; }');
            return [style, ...['default-indication', 'custom-indication', 'lf-action-target'].map(cls => {
              const p = document.createElement('p');
              p.className = cls;
              p.textContent = cls;
              p.setAttribute('data-lf-indicated', '');
              return p;
            })];
          };
          const main = document.querySelector('main');
          main.append(...nodes());
          const host = document.createElement('div');
          main.append(host);
          const shadow = shadowStage(host, nodes());
          return [main, shadow].map(root =>
            [...root.querySelectorAll('[data-lf-indicated]')].map(p => {
              const s = getComputedStyle(p);
              return [s.outlineStyle, s.outlineWidth];
            }));
        }"""
    )
    assert readings == [[["solid", "2px"], ["dashed", "4px"], ["solid", "1px"]]] * 2


def test_message_markdown_reads_a_link_scheme_as_the_attribute_resolves_it(
    browser, serve
):
    """The web-protocol guard reads the href the document will resolve, not its source.

    Character references in destinations must be interpreted before scheme
    admission. The parser's normalized attributes and flattened image alt are
    shared by message rendering and media inspection, including titles and
    autolink destinations. A refused destination retains its visible label.
    """
    url = serve(LONG_PAGE)
    pixels = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(pixels, format="PNG")
    media = store_uploaded_media(serve.page_dir, pixels.getvalue(), "image/png")
    root = panel_comment(
        serve.page_dir,
        "[press me](javascript&#58;window.leaked=true)"
        " ![blocked *image*](javascript&#58;window.leaked=true)"
        " beside [the page](https://example.com/?a=1&amp;b=2)"
        " and <https://example.com/?a=1&amp;b=2>"
        ' and ![Q&amp;A *chart* with [details](https://example.com/)](/icon.svg "Sales &amp; revenue")'
        f" and ![A **media** chart]({media})",
        {"section": "p0"},
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, root)

    prose = view.locator(".lf-msg-text").first
    # The prose goes on past these words, so they are read as a run inside it rather
    # than as the whole of its text.
    expect(prose).to_contain_text("press me blocked image beside the page")
    admitted = prose.evaluate(
        """node => [...node.querySelectorAll('a')].map(link => link.href)"""
    )
    assert admitted == [
        "https://example.com/?a=1&b=2",
        "https://example.com/?a=1&amp;b=2",
    ], admitted
    expect(prose.locator("img")).to_have_count(2)
    image = prose.locator("img").first
    expect(image).to_have_attribute("alt", "Q&A chart with details")
    expect(image).to_have_attribute("title", "Sales & revenue")

    media_button = prose.get_by_role("button", name="View A media chart", exact=True)
    expect(media_button.locator("img")).to_have_attribute("alt", "A media chart")
    media_button.focus()
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute("alt", "A media chart")
    page.keyboard.press("Escape")
    expect(media_button).to_be_focused()


MARKDOWN = (
    "Words, `inline code`, **strong**, *emphasis*, ~~struck~~ and a"
    " [link](https://example.com/).\n\n> A quoted line\n\n## A heading\n\n"
    "```\nfenced(code)\n```\n\nend"
)
# Each construct as the sent message draws it, and as the draft draws the same source.
# The draft is set in the box's type and the message in the body's, so sizes are
# compared as a share of each one's container; the rest is the face itself.
FACES = {
    "inline code": ("p code", "code"),
    "strong": ("strong", "strong"),
    "emphasis": ("em", "em"),
    "strikethrough": ("s", "s"),
    "link": ("a", ".lf-md-link"),
    "quote": ("blockquote", ".lf-md-quote"),
    "heading": ("h2", ".lf-md-heading"),
    "code block": ("pre", ".lf-md-code-block"),
}
FACE = [
    "font-family",
    "font-style",
    "font-weight",
    "color",
    "background-color",
    "padding-left",
    "border-top-left-radius",
    "border-left-width",
    "border-left-style",
    "border-left-color",
    "text-decoration-line",
    "text-decoration-color",
    "text-underline-offset",
]


def test_words_in_a_threaded_page_element_stay_selectable_beside_threads(
    browser, serve
):
    """Selecting annotated page text outranks the panel's selected thread.

    The panel's thread highlight must not reclaim focus during a native drag. The
    resulting passage, rather than that selected thread, is what c comments on.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Discuss this paragraph.", {"section": "p0"})
    page = open_page(browser, url)
    resized(page, 1440, 900)
    open_panel_thread(page, root)
    paragraph = page.locator("#p0")
    rect = paragraph.bounding_box()
    select(
        page,
        (rect["x"] + 2, rect["y"] + 8),
        (rect["x"] + min(rect["width"] - 2, 250), rect["y"] + 8),
    )
    selected = page.evaluate("getSelection().toString()")
    assert selected.strip() and selected in paragraph.inner_text()
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer leaf-text")).to_be_focused()
    expect(page.locator("#lf-composer-quote")).to_contain_text(selected)


# A wide page of a body and its side track: a long body beside a short side track, which
# a surface standing over the page must leave where its Layout put it.
WIDE_PAGE = leaf_page(
    "wide page",
    """
<header><h1 id="t">Wide page</h1></header>
<div id="body">{paras}</div>
<aside id="side">
  <section class="panel" id="rail"><h2>Rail</h2><p>Counts beside the body.</p></section>
</aside>
""",
    layout="sidebar",
).format(
    paras="\n".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 40 + "</p>" for i in range(40)
    )
)


SURFACE_PAGES = {
    "threads-column": ("threads", lambda: LONG_PAGE),
    "threads-wide-page": ("threads", lambda: WIDE_PAGE),
    "queue": ("queue", lambda: with_one_obligation(LONG_PAGE)),
}


def toggle_surface(page, surface, open=True):
    if surface == "queue":
        toggle_queue(page, open)
    else:
        page.locator(".lf-fp-threads").click()
        panel_settled(page, open, "threads" if open else None)


@pytest.mark.parametrize(
    ("case", "width"),
    [
        ("threads-column", 900),
        ("threads-wide-page", 1440),
        ("queue", 1440),
    ],
)
def test_an_auxiliary_surface_stands_over_the_page_and_moves_none_of_it(
    browser, serve, case, width
):
    """Opening Threads or On me in the panel never moves the page: each view stands over
    it, so the reading column keeps its place, its width and its wrapping, a wide page's
    side track stays where its Layout put it, and the document neither grows nor
    scrolls under it."""
    surface, html = SURFACE_PAGES[case]
    page = open_page(browser, serve(html(), comments=2))
    resized(page, width, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 900")
    shape = """() => {
      const main = document.querySelector('body > main').getBoundingClientRect();
      const rail = document.querySelector('#rail')?.getBoundingClientRect();
      return {
        left: main.left, width: main.width, rail: rail ? rail.left : null,
        scroll: document.scrollingElement.scrollTop,
        tall: document.documentElement.scrollHeight,
        shell: document.body.clientWidth,
      };
    }"""
    before = page.evaluate(shape)
    region = page.locator(f'.lf-fp-view[data-view="{surface}"]')

    toggle_surface(page, surface)
    expect(region).to_be_visible()
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)

    toggle_surface(page, surface, open=False)
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)


def test_the_page_paints_beneath_leaf_and_rises_only_through_the_top_layer(
    browser, serve
):
    """A box the page writes stacks beneath every surface Leaf lifts over the page,
    whatever its z-index: `main` is one stacking context at 0, so the panel with Threads
    open paints over a page overlay at the largest z-index there is, and
    `stackLevel`, which paint, chips and landings ask where a node stacks, reads the
    overlay beneath the panel. The page's way over Leaf is the top layer: its own modal
    dialog paints over the panel, and reads above it."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1440, 900)
    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")
    stacking = page.evaluate(
        """async () => {
          const { stackLevel } = await window.__lfCheckApi();
          const main = document.querySelector('main');
          const overlay = main.appendChild(document.createElement('div'));
          overlay.id = 'page-overlay';
          overlay.style.cssText = `position: fixed; inset: 0; z-index: 2147483647;
            background: rgb(255 0 0 / 0.3);`;
          const panel = document.querySelector('.lf-floating-panel');
          const at = (el) => {
            const r = el.getBoundingClientRect();
            const hit = document.elementFromPoint(
              r.left + r.width / 2, r.top + r.height / 2);
            return hit === overlay ? 'page' : el.contains(hit) ? 'leaf' : hit?.localName;
          };
          const panelLevel = stackLevel(panel);
          const read = {
            panel: at(panel),
            overlayBeneath: stackLevel(overlay) < panelLevel,
          };
          overlay.remove();
          const dialog = main.appendChild(document.createElement('dialog'));
          dialog.style.cssText = 'width: 100vw; height: 100vh; max-width: none; max-height: none;';
          dialog.showModal();
          const box = panel.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
          read.dialog = dialog.contains(hit);
          read.dialogAbove = stackLevel(dialog) > panelLevel;
          dialog.close();
          return read;
        }"""
    )
    assert stacking == {
        "panel": "leaf",
        "overlayBeneath": True,
        "dialog": True,
        "dialogAbove": True,
    }


def test_a_page_map_update_keeps_the_row_the_user_was_on(browser, serve):
    """A state update re-rendering the open Page Map leaves the user's rows in place.

    A group arriving above the rows in view pushes them down in the list's content by
    its own height. The place the user had is the rows they were looking at, so the
    list follows them by the same amount rather than standing at the scroll offset it
    had, which would show them one group further down.
    """
    fixture = leaf_page(
        "Page Map place",
        "".join(f'<p id="place-{index}">Target {index}</p>' for index in range(30)),
    )
    page = open_page(browser, serve(fixture))
    resized(page, 1280, 600)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const contribute = (key, target, label) => registerContribution({
            key, target,
            read: () => ({entries: [contributionEntry({key: 'action', icon: 'dot', label})]}),
            activate: () => {},
          });
          for (let index = 0; index < 29; index++)
            contribute(`place-${index}`, document.querySelector(`#place-${index}`),
              `Action ${index}`);
          let at = 29;
          const moving = contribute(
            'moving', () => document.querySelector(`#place-${at}`), 'Moving action');
          window.lfMoveToTop = () => {
            at = 0;
            moving.update({immediate: true});
          };
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    row = dialog.get_by_role("button", name="Action 15", exact=True)
    row.evaluate("node => node.scrollIntoView({block: 'center'})")
    top = row.evaluate("node => node.getBoundingClientRect().top")
    room = dialog.locator(".lf-page-map-list").evaluate(
        "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    )
    moving = dialog.get_by_role("button", name="Moving action", exact=True)
    grown = moving.evaluate(
        "node => node.closest('.lf-page-map-group').getBoundingClientRect().height"
    )
    assert room > grown, "the list cannot follow the rows without passing its end"

    page.evaluate("() => window.lfMoveToTop()")
    first = dialog.locator(".lf-page-map-action-label-word").first
    expect(first).to_have_text("Moving action")
    assert row.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        top, abs=1
    )


def test_a_repaint_unsettles_the_rendering_until_it_lands(browser, serve):
    """The settled reading turns false in the same turn as a gesture that queues a
    repaint, and true once that repaint has landed, so a reader after the gesture waits
    on the page rather than on a guessed number of frames. The fold itself — chained
    work, observer deliveries, cancellation — is tests/runtime/rendering.test.mjs."""
    url = serve(leaf_page("Settled", '<h1 id="h">Settled</h1><p id="p">Words.</p>'))
    page = open_page(browser, url)
    toggle = page.locator(".lf-fp-threads")
    toggle.hover()
    rendered(page)
    # Read before dispatch: an earlier pointerdown capture listener may already have
    # queued the repaint by the time a listener installed here receives the event.
    assert page.evaluate(
        "() => Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
    )
    # Once the click has passed every listener, its repaint is pending.
    page.evaluate(
        """() => {
          const state = document.querySelector('script[data-lf-entry]').lfRenderingState;
          const settled = () => Object.values(state()).every(Boolean);
          window.__lfPress = [];
          const read = () => window.__lfPress.push(settled());
          addEventListener('click', read, {once: true});
        }"""
    )
    toggle.click()
    assert page.evaluate("window.__lfPress") == [False]
    rendered(page)
    # Completion is the reading rendered waited on. A later slide-end scan can
    # queue new work, so a second reading need not still be settled.
    expect(page.locator('.lf-fp-view[data-view="threads"]')).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_send_room_moves_to_every_line_only_while_the_field_scrolls(
    engine, request, serve
):
    """The field holds Send's room after its last words until its words scroll, and on
    every line while they do, in an engine without CSS scroll-state queries as in
    Chromium. Keyed on the query alone, WebKit and Firefox held it on every line
    always, so the change never reached them."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    field = page_comment(page)
    scrolls = "el => el.scrollHeight > el.clientHeight"

    write(field, "First line.\nSecond line.")
    assert not field.evaluate(scrolls)
    expect(field).to_have_js_property("endRoom", "last-line")
    write(field, "A long draft scrolls inside its field. " * 120)
    assert field.evaluate(scrolls)
    expect(field).to_have_js_property("endRoom", "every-line")
    # Let its scroll and size observers land before replacing the draft; a second
    # edit during that layout pass tests the editor's transition, not Send's room.
    rendered(page)
    write(field, "Short again.")
    expect(field).to_have_js_property("endRoom", "last-line")
