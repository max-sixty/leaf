"""Everyday browser contracts for shared chrome."""

import io
import json
from itertools import pairwise
from types import SimpleNamespace
from urllib.parse import urljoin

import pytest
from interact_support import append_carried_log_record
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
from render_cases_navigation import source_revision
from render_harness import (
    LONG_PAGE,
    PANEL,
    CutOff,
    expect_panel_says,
    leaf_page,
    nudge,
    open_page,
    open_threads,
    page_comment,
    panel_field,
    panel_settled,
    panel_view,
    primed,
    resized,
    round_trip,
    select,
    selection_field,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.test_render_floating_panel import finish_held, held_motion, hold_motion
from browser.threads import open_panel_thread
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.media import store_uploaded_media
from leaf.render_checks import rendered


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
def test_a_margin_reply_stands_on_its_cards_face(browser, serve, scheme):
    """The thread and its reply row paint no ground of their own as focus enters and
    leaves the thread, so the card's opaque face shows behind them: no band above the
    field, no focus tint, and nothing over the field's ring while the card's surface
    draws it (box-motion.js).
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, color_scheme=scheme)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    face = preview.locator(".lf-margin-preview-card")
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
        alpha = face.evaluate("""node => {
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 1;
          const paint = canvas.getContext('2d');
          paint.fillStyle = getComputedStyle(node).backgroundColor;
          paint.fillRect(0, 0, 1, 1);
          return paint.getImageData(0, 0, 1, 1).data[3];
        }""")
        assert alpha == 255, (scheme, state)
        for part in (thread, surround):
            expect(part).to_have_css("background-color", "rgba(0, 0, 0, 0)")


def test_a_compact_comment_reserves_only_the_room_send_occupies(browser, serve):
    """Space adds no blank line when the words fit beside Send. The text keeps
    the shared comment inset before Send's hit box, without reserving its width
    a second time."""
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

    def resting_box():
        # Layout already has its final width while Send still rides the box's
        # growth (box-motion.js). Compare their geometry only once it rests.
        rendered(page)
        page.wait_for_function(
            """() => !document.querySelector('.lf-fab-bar')
              .getAnimations({subtree: true}).some(motion =>
                Number.isFinite(motion.effect?.getComputedTiming().endTime))"""
        )
        return field.bounding_box()

    page.keyboard.insert_text("this is a nice feature; is it in leaf, or you")
    before = resting_box()
    page.keyboard.press("Space")
    after = resting_box()
    assert after["height"] == pytest.approx(before["height"], abs=1)
    assert after["y"] == pytest.approx(before["y"], abs=1)
    reservation = field.evaluate("""el => {
      const style = getComputedStyle(el), box = el.getBoundingClientRect();
      const send = el.parentElement.querySelector('.lf-compose-submit');
      // The shared comment column keeps the action inset before Send, plus
      // the frame between the field and the action's containing box.
      const gap = parseFloat(getComputedStyle(send).insetInlineEnd)
        + send.parentElement.getBoundingClientRect().right - box.right;
      return {textEnd: box.right - parseFloat(style.borderInlineEndWidth)
        - parseFloat(style.paddingInlineEnd)
        - parseFloat(style.getPropertyValue('--lf-field-end-room')),
        textLimit: send.getBoundingClientRect().left - gap};
    }""")
    assert reservation["textEnd"] == pytest.approx(reservation["textLimit"], abs=0.1)


# The field's shadow root is closed, so the reading keeps each root as it is attached.
KEEP_ROOTS = """(() => {
  const attach = Element.prototype.attachShadow;
  const roots = (window.__lfRoots = new WeakMap());
  Element.prototype.attachShadow = function (init) {
    const root = attach.call(this, init);
    roots.set(this, root);
    return root;
  };
})()"""

# The caret's node and offset in the field. An offset between elements has no box; the
# caret after them ends their text, which is the text the browser draws it beside.
CARET_AT = """
  const root = window.__lfRoots.get(box);
  let [{startContainer: at, startOffset: offset}] = document
    .getSelection().getComposedRanges({shadowRoots: [root]});
  while (at.nodeType === Node.ELEMENT_NODE && offset > 0) {
    at = at.childNodes[offset - 1];
    offset = at.nodeType === Node.TEXT_NODE ? at.length : at.childNodes.length;
  }"""

# How far past the caret's offset the boxes clipping the field's words let paint run.
CARET_ROOM = rf"""box => {{{CARET_AT}
  const caret = document.createRange();
  caret.setStart(at, offset);
  let clip = Infinity;
  for (let node = at.parentElement; node; node = node.parentElement) {{
    const style = getComputedStyle(node);
    const right = node.getBoundingClientRect().right;
    if (style.overflowX === 'clip') {{
      const margin = parseFloat(style.overflowClipMargin) || 0;
      clip = Math.min(clip, right + margin);
    }}
    const inset = /^inset\(([^)]+)\)$/.exec(style.clipPath);
    if (inset) {{
      const sides = inset[1].trim().split(/\s+/).map(parseFloat);
      clip = Math.min(clip, right - (sides[1] ?? sides[0]));
    }}
  }}
  return clip - caret.getBoundingClientRect().right;
}}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_caret_at_a_lines_end_paints_inside_the_field(engine, request, serve):
    """The caret after a line's last character stands at the very end of the text
    column: in a box that grows with its words, and after a trailing space that fits
    beside Send. Firefox paints the caret a pixel wide from that offset onward, pulled
    inside only by a scroll container (nsCaret, `AdjustRectForClipping`), so a field
    clipping its words at the column's end hid it, and it read as gone under Send.
    Chromium and WebKit pull a line-end caret back inside the line's block, and WebKit
    has no `overflow-clip-margin` to read."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page("Compact comment", '<p id="passage">A passage to comment on.</p>')
        ),
        init_script=KEEP_ROOTS,
    )
    page.locator("#passage").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    hold_motion(page)
    # The box grows with its words, so the caret after the last word ends its column.
    page.keyboard.insert_text(
        "it's not really a feed as much as a list? I see a feed as"
    )
    rendered(page)
    held_motion(page, ".lf-fab-ground")
    # Read the final moving frame, before cleanup restores the field's resting clip.
    page.evaluate("""() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => {
      a.currentTime = Number(a.effect.getTiming().duration) - 0.01;
    })""")
    assert field.evaluate(CARET_ROOM) >= 1
    finish_held(page)
    # At a narrow allocation the trailing space fits beside Send (see above).
    resized(page, 346, 900)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text("this is a nice feature; is it in leaf, or you")
    page.keyboard.press("Space")
    rendered(page)
    assert field.evaluate(CARET_ROOM) >= 1


# The ink the browser draws the caret in, beside the ink of the field's words.
CARET_INK = f"""box => {{{CARET_AT}
  const holder = at.nodeType === Node.TEXT_NODE ? at.parentElement : at;
  return [getComputedStyle(holder).caretColor,
    getComputedStyle(holder.closest('.cm-content')).color];
}}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_caret_after_a_list_bullet_is_drawn(engine, request, serve):
    """A new list item shows its bullet with the caret just past the hidden source
    marker, so the browser places the caret inside the marker's text. The caret takes
    that text's ink, so hiding the marker's glyphs must leave the ink alone, however
    the caret arrived: continuing the list, deleting the marker's space, or arrows."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page("Compact comment", '<p id="passage">A passage to comment on.</p>')
        ),
        init_script=KEEP_ROOTS,
    )
    page.locator("#passage").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("- one")
    page.keyboard.press("Shift+Enter")
    expect(field).to_have_js_property("value", "- one\n- ")
    rendered(page)
    caret, words = field.evaluate(CARET_INK)
    assert caret == words
    page.keyboard.press("Backspace")
    expect(field).to_have_js_property("value", "- one\n-")
    rendered(page)
    caret, words = field.evaluate(CARET_INK)
    assert caret == words
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowRight")
    rendered(page)
    caret, words = field.evaluate(CARET_INK)
    assert caret == words


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
        """preview => ['.lf-margin-preview-expand', '.lf-resolve', '.lf-margin-preview-close']
          .map(selector => {
            const rect = preview.querySelector(selector).getBoundingClientRect();
            return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
          })"""
    )
    assert all(c["y"] == pytest.approx(centers[0]["y"], abs=1) for c in centers), (
        centers
    )
    assert centers[0]["x"] < centers[1]["x"] < centers[2]["x"], centers
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
    # Web Awesome inputs, and Safari zooms onto the field inside them.
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
    assert any(name.startswith("wa-input.") for name in sizes), sizes
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
        ' and ![Q&amp;A *chart* with [details](https://example.com/)](/chart.png "Sales &amp; revenue")'
        f" and ![A **media** chart]({media})",
        {"section": "p0"},
    )
    prepared = primed(
        browser,
        lambda page: page.route(
            "**/chart.png",
            lambda route: route.fulfill(
                content_type="image/png", body=pixels.getvalue()
            ),
        ),
    )
    page = open_page(prepared, url)
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
    elif open:
        open_threads(page)
    else:
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)


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
    region = page.locator(panel_view(surface))

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
    open_threads(page)
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
    toggle = page.locator(".lf-fp-on-user")
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
    expect(page.locator(panel_view("queue"))).to_be_visible()


# The words of the field's draft, row by row as the field draws them.
WORD_ROWS = """box => {
  const content = window.__lfRoots.get(box).querySelector('.cm-content');
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  const rows = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    for (const word of node.data.matchAll(/\\S+/g)) {
      const range = document.createRange();
      range.setStart(node, word.index);
      range.setEnd(node, word.index + word[0].length);
      const top = range.getClientRects()[0].top;
      const row = rows.find((r) => Math.abs(r.top - top) < 4);
      if (row) row.words.push(word[0]);
      else rows.push({top, words: [word[0]]});
    }
  }
  return rows.map((r) => r.words.join(" "));
}"""


# The comment whose words moved as it was typed in the panel's field.
REPORTED_DRAFT = (
    "great, let's go with the more square form. I don't have a strong view of which"
    " one is better, and the other parts of this thread can wait until later"
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_scrolling_draft_shows_the_caret_s_row_with_the_padding_beside_it(
    engine, request, serve
):
    """A line typed at the end of a draft that scrolls leaves nothing below it to scroll
    to, and the caret taken to the first line leaves nothing above. Revealing only the
    caret, as a native textarea does, left the field's padding out of view, and in
    Firefox the foot of the caret's row too."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    field = page_comment(page)
    hidden = """box => ({
      below: box.scrollHeight - box.clientHeight - box.scrollTop,
      above: box.scrollTop,
    })"""
    page.keyboard.type("line 0")
    for line in range(1, 40):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"line {line}")
        if field.evaluate("box => box.scrollHeight > box.clientHeight + 40"):
            break
    else:
        raise AssertionError("the draft never scrolled")
    for key in ("Shift+Enter", "w", "ControlOrMeta+Home"):
        page.keyboard.press(key)
        rendered(page)
        shown = field.evaluate(hidden)
        if key == "ControlOrMeta+Home":
            assert shown["above"] < 1, shown
        else:
            assert shown["below"] < 1, (key, shown)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_space_after_the_last_word_moves_no_word(engine, request, serve):
    """Where a draft's words wrap turns on the words alone, so a space typed after the
    last word leaves every word on its row, as in a textarea. With Send's room kept
    after the last word only, a word that fit only without the room rose to the row
    above when a space followed it; under CodeMirror's `break-spaces`, a word ending
    at the row's edge fell to the next row with the space."""
    page = open_page(
        request.getfixturevalue(engine), serve(LONG_PAGE), init_script=KEEP_ROOTS
    )
    field = page_comment(page)
    words = REPORTED_DRAFT.split()
    write(field, words[0])
    rendered(page)
    for end in range(2, len(words) + 1):
        draft = " ".join(words[:end])
        write(field, draft)
        rows = field.evaluate(WORD_ROWS)
        page.keyboard.press("Space")
        assert field.evaluate(WORD_ROWS) == rows, draft


def test_agent_reply_arrivals_keep_open_panel_drafts_and_summarize_batches(
    browser, serve
):
    """Unread replies announce once each, whether they arrive while the page is open or
    were waiting when it opened, regardless of the panel's disclosure. The user keeps
    a draft open in a thread no reply lands in, so exposure acknowledges none of them."""
    url = serve(leaf_page("Reply arrivals", "<h1>Reply arrivals</h1>"))
    directory = serve.page_dir
    drafting, a, b = (
        append_carried_log_record(
            directory,
            {"kind": "comment", "author": "user", "revision": 1, "text": text},
        )
        for text in ("Draft here", "A", "B")
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "Earlier",
        },
    )
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    expect(live).to_have_text("Earlier")

    open_panel_thread(page, drafting["id"])
    draft = panel_field(page)
    write(draft, "Keep this draft")
    draft.focus()
    page.evaluate(
        """() => {
          window.__lfReplyAnnouncements = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfReplyAnnouncements.push(words);
          }).observe(document.querySelector('.lf-live'), {childList: true, subtree: true});
        }"""
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "For B",
        },
    )
    told(page)
    expect(live).to_have_text("For B")
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property("value", "Keep this draft")

    reads = CutOff().hold(page)
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "More for A",
        },
    )
    append_carried_log_record(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "More for B",
        },
    )
    reads.restore()
    told(page)
    expect(live).to_have_text("2 replies in 2 threads")
    expect(draft).to_be_focused()
    expect(draft).to_have_js_property("value", "Keep this draft")

    # A fresh server snapshot of unchanged content makes no fresh announcement;
    # a fresh document announces what the user has still not read. Moving the
    # freshness token ensures this actually admits another read.
    nudge(directory)
    told(page)
    round_trip(page)
    expect(live).to_have_text("2 replies in 2 threads")
    assert page.evaluate("() => window.__lfReplyAnnouncements") == [
        "For B",
        "2 replies in 2 threads",
    ]
    page.reload()
    expect(page.locator(".lf-live")).to_have_text("4 replies in 2 threads")


def test_interrupted_background_notice_keeps_the_newer_version(browser, serve):
    """An older visible notice cannot replace a newer one already waiting."""
    page = open_page(browser, serve(leaf_page("Notice order", "<h1>Notice order</h1>")))
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfWidgetApi();
          notice('Updated to v3', {background: true});
          notice('Updated to v4', {background: true});
          notice('Saved');
        }"""
    )
    expect_panel_says(page, "Saved")
    expect_panel_says(page, "Updated to v4")


@pytest.mark.parametrize("viewport", [None, "width=device-width, initial-scale=1"])
def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve, viewport):
    """The runtime starts in WebKit; the panel's field offers to comment on a selection.

    A module feature WebKit lacks fails the whole module graph before the runtime runs:
    CSS module scripts did, and an iPhone user saw only that Leaf could not start. A
    long press that selects words hands the page no mouseup, and Playwright cannot make
    one, so the selection is placed with no pointer gesture at all."""
    source = PHONE_PAGE
    if viewport:
        source = source.replace(
            "<head>", f'<head><meta name="viewport" content="{viewport}">'
        )
    page = open_page(None, serve(source), context=iphone)
    assert page.evaluate("innerWidth") == page.viewport_size["width"]
    metas = page.locator('meta[name="viewport"]')
    expect(metas).to_have_count(1)
    expect(metas).to_have_attribute(
        "content", viewport or "width=device-width, initial-scale=1, viewport-fit=cover"
    )
    page.locator("#p1").evaluate("""paragraph => {
      const range = document.createRange();
      range.setStart(paragraph.firstChild, 0);
      range.setEnd(paragraph.firstChild, "Paragraph one".length);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_hidden()
    # The panel's field quotes the selection, where the finger that made it finds it,
    # and the On me mark keeps its seat; the leaf's menu stays shut.
    comment = selection_field(page)
    expect(comment).to_have_attribute("placeholder", "“Paragraph one”")
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")
    expect(page.locator(".lf-fp-on-user")).to_be_visible()
    box = comment.bounding_box()
    assert box["x"] + box["width"] <= page.evaluate("innerWidth"), box
    comment.tap()
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")
    expect(field).to_be_focused()
    write(field, "From a phone")
    with sending(page, "the comment"):
        page.locator(".lf-fab-bar").get_by_role(
            "button", name="Comment", exact=True
        ).tap()
    [comment] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert comment["text"] == "From a phone"
    assert comment["anchor"]["quote"] == "Paragraph one", comment


@pytest.mark.parametrize(
    "surface, scheme",
    [
        *((surface, "light") for surface in ("general", "panel", "margin", "outlet")),
        ("outlet", "dark"),
    ],
)
def test_a_draft_wears_the_faces_its_sent_message_wears(
    browser, serve, surface, scheme
):
    """The composer's Markdown preview draws each construct the way the message will.

    The preview stands in the field's closed shadow root, where the theme's element
    rules do not reach, so it reads the faces from the theme's tokens instead of
    stating its own. It had stated its own from birth: a quote drafted upright with a
    heavy dark rule was sent italic with a light one, and code sat a size and a chip
    shape away from how it arrived. DevTools reads the closed root, as it reads any.
    """
    if surface == "outlet":
        url = serve(
            leaf_page(
                "Draft faces",
                "<h1>Draft faces</h1>"
                '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>',
            )
        )
        data_model.cmd_data_set(
            serve.page_dir,
            "review-patch",
            """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
        )
        anchor = {
            "section": "patch",
            "datum": '["app.py","new",1]',
            "source": "review-patch",
            "source_revision": source_revision(serve.page_dir, "review-patch"),
        }
    else:
        url = serve(LONG_PAGE)
        anchor = {"section": "p0"}
    panel_comment(serve.page_dir, MARKDOWN, anchor)
    page = open_page(browser, url, color_scheme=scheme)
    if surface == "outlet":
        thread = page.locator("#patch .lf-page-thread")
        box_selector = "#patch .lf-thread-reply leaf-text"
    elif surface == "margin":
        resized(page, 1440, 900)
        page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
        thread = page.locator(".lf-margin-preview .lf-page-thread")
        box_selector = ".lf-margin-preview .lf-thread-reply leaf-text"
    else:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        thread = open_panel_thread(page, root)
        box_selector = '.lf-fp-field leaf-text[name="reply"]'
    body = thread.locator(".lf-msg-body").first
    expect(body.locator("blockquote")).to_be_visible()
    # A source renderer can leave the code's colors correct while turning an inline
    # phrase into a separate block. Read its line beside the preceding prose too.
    flow = body.locator("p code").evaluate("""code => {
      const words = document.createRange();
      words.selectNode(code.previousSibling);
      return {words: words.getBoundingClientRect().top,
              code: code.getBoundingClientRect().top};
    }""")
    assert flow["code"] == pytest.approx(flow["words"], abs=4), flow
    # Read first: the page's general box stands in the panel's field with no view open,
    # the one place a page thread starts, so writing there puts the thread's view away.
    sent = body.evaluate(
        """(body, [faces, face]) => Object.fromEntries(Object.entries(faces)
          .map(([name, [selector]]) => {
            const style = getComputedStyle(body.querySelector(selector));
            return [name, Object.fromEntries(
              [...face, "font-size"].map((p) => [p, style.getPropertyValue(p)]))];
          }))""",
        [FACES, FACE],
    )
    sent_size = body.evaluate("body => getComputedStyle(body).fontSize")
    box = page_comment(page) if surface == "general" else page.locator(box_selector)
    if surface == "outlet":
        # Reply rests as a press; open it by user input before write() focuses it.
        box.click()
    write(box, MARKDOWN)
    box.evaluate("box => box.id = 'draft-face-editor'")
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    document = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})["root"]

    def find(node):
        attrs = node.get("attributes", [])
        if dict(zip(attrs[::2], attrs[1::2])).get("id") == "draft-face-editor":
            return node
        for child in node.get("children", []) + node.get("shadowRoots", []):
            if found := find(child):
                return found
        return None

    root = find(document)["shadowRoots"][0]["nodeId"]

    def drawn(selector):
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})
        assert node["nodeId"], f"the draft draws no {selector}"
        style = {
            entry["name"]: entry["value"]
            for entry in cdp.send(
                "CSS.getComputedStyleForNode", {"nodeId": node["nodeId"]}
            )["computedStyle"]
        }
        return {name: style[name] for name in [*FACE, "font-size"]}

    draft = {name: drawn(selector) for name, (_, selector) in FACES.items()}

    # Inline constructs are sized against the words around them, and the draft's words
    # are the box's type where the message's are the body's; a code block is set at the
    # code size whatever holds it. A draft marks a heading by weight alone, at the size
    # of its words, so a heading's size is left out.
    def px(value):
        return float(value.removesuffix("px"))

    size = {
        "draft": box.evaluate("box => getComputedStyle(box).fontSize"),
        "sent": sent_size,
    }
    for face, which in ((draft, "draft"), (sent, "sent")):
        del face["heading"]["font-size"]
        for name in FACES.keys() - {"heading", "code block"}:
            share = px(face[name]["font-size"]) / px(size[which])
            face[name]["font-size"] = round(share, 3)
    differ = {
        name: {
            k: (v, sent[name][k]) for k, v in draft[name].items() if v != sent[name][k]
        }
        for name in FACES
    }
    assert not any(differ.values()), differ


# Quotes holding quotes, code and a list, and a fence its quote ends, each line ending in
# a word.
NESTED = (
    "> alpha\n> > beta\n> gamma\n\n> ```\n> delta\n> ```\n\n"
    "> ```\n> zeta\nomega\n\n> - kappa\n> - lambda"
)
# Where each word stands in a root's content box: its left edge, its top, the left edge
# of each ruled or framed box holding it, innermost first, and how many list items,
# each drawing its marker, hold it. The source the editor leaves unseen is not a word.
WORDS_AND_RULES = """(root, words) => {
  const style = getComputedStyle(root);
  const origin = root.getBoundingClientRect().left + parseFloat(style.borderLeftWidth)
    + parseFloat(style.paddingLeft);
  const top = root.getBoundingClientRect().top;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const found = {};
  for (let node; (node = walker.nextNode()); ) {
    if (node.parentElement.closest('.lf-md-unseen')) continue;
    for (const word of words) {
      const at = node.data.indexOf(word);
      if (at < 0 || word in found) continue;
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + word.length);
      const r = range.getBoundingClientRect();
      const rules = [];
      let items = 0;
      for (let el = node.parentElement; el !== root; el = el.parentElement) {
        const style = getComputedStyle(el);
        if (parseFloat(style.borderLeftWidth) > 0)
          rules.push(Math.round(el.getBoundingClientRect().left - origin));
        if (style.display === 'list-item') items++;
      }
      found[word] = {x: Math.round(r.left - origin), y: r.top - top, rules, items};
    }
  }
  return found;
}"""


def test_a_draft_nests_its_blocks_as_its_sent_message_does(browser, serve):
    """A quote inside a quote, and code inside a quote, stand in the draft where they will
    in the message, each beside its quote's rule. The preview drew every quoted line with
    one class, which CodeMirror merged, so a nested quote showed one rule at one inset and
    a lazy line seemed back at the first level; a code block's frame replaced its quote's
    rule and inset, and indented code in a quote showed its four spaces. A fence its quote
    ended lacked the code's padding below it, so the next block rose on sending. A list
    in a quote kept its source markers as words, where the message draws bullets."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, NESTED, {"section": "p0"})
    page = open_page(browser, url, init_script=KEEP_ROOTS)
    view = open_panel_thread(page, root)
    words = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "zeta",
        "omega",
        "kappa",
        "lambda",
    ]
    sent = view.locator(".lf-msg-text").first.evaluate(WORDS_AND_RULES, words)
    box = page.locator('.lf-fp-field leaf-text[name="reply"]')
    # The caret stays after the last word, away from every container's source.
    write(box, NESTED)
    rendered(page)
    draft = box.evaluate(
        f"""(box, words) => ({WORDS_AND_RULES})(
          window.__lfRoots.get(box).querySelector('.cm-content'), words)""",
        words,
    )
    # Each word's line is read from the word above it, so one gap flags once.
    step = {
        name: [round(read[b]["y"] - read[a]["y"]) for a, b in pairwise(read)]
        for name, read in (("sent", sent), ("draft", draft))
    }
    assert step["draft"] == pytest.approx(step["sent"], abs=1), step
    for read in (sent, draft):
        for place in read.values():
            del place["y"]
    assert draft == sent


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    "lines",
    [["```", "one", ""], ["- item", "  ```", "  one", "  "]],
    ids=["draft", "item"],
)
def test_a_new_line_in_an_open_fence_starts_in_its_code(engine, lines, request, serve):
    """A line begun at the end of a fence not yet closed is a line of its code from the
    start, in the draft or in a list item, its indent unseen as the message drops it.
    The parser's reading of the fence stops before the draft's blank last line, so the
    preview drew that line, with the caret on it, below the code's frame as prose, and
    moved it into the frame on the first key; in an item, the code then showed the
    item's indent."""
    page = open_page(
        request.getfixturevalue(engine), serve(LONG_PAGE), init_script=KEEP_ROOTS
    )
    field = page_comment(page)
    for at, text in enumerate(lines):
        if at:
            # A user retyping the line takes back what continuing the list put there.
            before = field.evaluate("box => box.value")
            page.keyboard.press("Shift+Enter")
            while len(field.evaluate("box => box.value")) > len(before) + 1:
                page.keyboard.press("Backspace")
        page.keyboard.type(text)
    expect(field).to_have_js_property("value", "\n".join(lines))
    # The last line's box from the fence's, which the field's growth carries with it,
    # and where the words of each line start.
    last_line = r"""box => {
      const lines = [...window.__lfRoots.get(box).querySelectorAll('.cm-line')];
      const fence = lines.find(line => line.textContent.includes('```'))
        .getBoundingClientRect();
      const r = lines.at(-1).getBoundingClientRect();
      const style = getComputedStyle(lines.at(-1));
      const words = lines.slice(-2).map(line => {
        const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
        for (let node; (node = walker.nextNode()); ) {
          const at = node.data.search(/\S/);
          if (node.parentElement.closest('.lf-md-unseen') || at < 0) continue;
          const range = document.createRange();
          range.setStart(node, at);
          range.setEnd(node, at + 1);
          return range.getBoundingClientRect().left;
        }
      });
      return {box: [r.left - fence.left, r.top - fence.top, r.width],
        face: [style.fontFamily, style.backgroundColor], words};
    }"""
    rendered(page)
    empty = field.evaluate(last_line)
    page.keyboard.type("two")
    expect(field).to_have_js_property("value", "\n".join(lines) + "two")
    rendered(page)
    typed = field.evaluate(last_line)
    assert typed["box"] == pytest.approx(empty["box"], abs=0.5), (empty, typed)
    assert typed["face"] == empty["face"]
    one, two = typed["words"]
    assert two == pytest.approx(one, abs=0.5), typed
