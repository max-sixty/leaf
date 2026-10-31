"""Comment-panel ordering, narrowing, and thread-motion tests."""

import io
import re

import pytest
from interact_support import (
    append_carried_log_record,
)
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    PANEL_THREAD,
    consume_browser_errors,
    example_media,
    expect_panel_says,
    http_error_console,
    open_page,
    panel_field,
    resized,
    rgb_pixel,
    round_trip,
    sending,
    told,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

from browser.threads import (
    CHANGE_HEAD,
    capture_page,
    open_capture_area,
    open_panel_thread,
    paste_image,
    pressed_send_surface,
)
from render_harness import leaf_page

# The same page with the change taken out of it, for the arm that carries the change
# in a message instead: the two must differ in which document holds it and in nothing
# else.
BARE_PAGE = leaf_page("doc-change", CHANGE_HEAD)


CAPTURE_SAMPLE_PAGE = leaf_page(
    "Capture a live sample",
    """<h1>Capture a live sample</h1>
<lf-sample id="capture-sample" label="practice">
  <template id="capture-sample-page" data-sample>
    <h1>Practice</h1>
    <section id="child-paint" style="height:200px;background:rgb(200,40,40)"></section>
  </template>
</lf-sample>""",
)


def test_a_diff_outlet_keeps_the_shared_attachment_controls(browser, serve):
    """An attachment keeps its face and keyboard routes inside a widget tree."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "pr-walkthrough"))
    )
    page.locator("#pr-exact-patch .lf-diff-file-comment").first.click()
    bar = page.locator('lf-diff .lf-fab-bar[data-lf-presentation="inline"]')
    field = bar.locator("leaf-text")
    field_width = field.bounding_box()["width"]
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    image_open = bar.get_by_role("button", name="View attached image 1", exact=True)
    remove = bar.get_by_role("button", name="Remove attached image 1", exact=True)
    expect(image_open.locator("img")).to_be_visible()
    # The shelf takes a line above the field rather than the field's width, and its
    # removal stays inside the box rather than over the file row above.
    picture, words = image_open.bounding_box(), field.bounding_box()
    assert picture["y"] + picture["height"] <= words["y"], (picture, words)
    assert remove.bounding_box()["y"] >= bar.bounding_box()["y"]
    assert words["width"] == pytest.approx(field_width, abs=1)
    # The shelf's face, its picture alone with a small removal on its corner, reaches
    # the widget's tree too (response.css).
    expect(image_open).to_have_css("border-radius", "6px")
    expect(remove).to_have_css("border-radius", "3px")
    expect(image_open).to_have_css("cursor", "zoom-in")
    assert remove.evaluate("""button => {
      const box = button.getBoundingClientRect();
      const root = button.getRootNode();
      return [box.top + 1, box.bottom - 1].every(y =>
        button.contains(root.elementFromPoint(box.left + box.width / 2, y)));
    }"""), "the whole removal control must accept a press inside the scrolling shelf"
    field.press("Shift+Tab")
    expect(remove).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(image_open).to_be_focused()
    expect(image_open).to_have_css("outline-style", "solid")
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    rendered(page)
    expect(image_open).to_be_focused()
    image_open.click()
    expect(viewer).to_be_visible()
    viewer.get_by_role("button", name="Close image preview", exact=True).click()
    expect(viewer).to_be_hidden()
    rendered(page)
    expect(image_open).to_be_focused()
    page.keyboard.press("Tab")
    expect(remove).to_be_focused()
    page.keyboard.press("Enter")
    expect(bar.locator(".lf-composer-media")).to_be_hidden()
    expect(field).to_be_focused()
    field.press("Tab")
    expect(bar.locator(".lf-response-options")).to_be_visible()
    page.keyboard.press("Escape")
    expect(field).to_be_focused()
    action = bar.get_by_role("button", name="Other responses", exact=True)
    action.focus()
    expect(action).to_be_focused()
    page.keyboard.press("Escape")
    expect(bar).to_be_hidden()

    page.locator("#pr-exact-patch .lf-diff-file-comment").first.click()
    paste_image(field, pixels)
    with sending(page, "the image in a file comment"):
        field.press("ControlOrMeta+Enter")
    sent = page.locator("#pr-exact-patch .lf-message-media img")
    expect(sent).to_be_visible()
    sizing = sent.evaluate("""image => {
      const box = image.getBoundingClientRect();
      return {width: box.width, height: box.height, ratio:
        image.naturalWidth / image.naturalHeight, ceiling: Math.min(innerHeight * .6, 480)};
    }""")
    assert sizing["height"] <= sizing["ceiling"]
    assert sizing["width"] == pytest.approx(sizing["height"] * sizing["ratio"], abs=1)
    sent.click()
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()


def test_a_phone_editor_inside_a_marked_widget_keeps_pointer_entry(browser, serve):
    """Inspecting an attachment and pressing its editor cannot activate the page mark."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser,
        serve(next(p for p in EXAMPLES if p.stem == "pr-walkthrough")),
        context=context,
    )
    comment = page.locator("#pr-exact-patch .lf-diff-file-comment").first
    comment.click()
    field = page.get_by_role("textbox", name=re.compile(r"^Comment on .+ · file$"))
    expect(field).to_be_focused()
    page.keyboard.type("Earlier file comment.")
    with sending(page, "the earlier file comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    first = events_model.read_events(serve.page_dir)[-1]

    comment.click()
    expect(field).to_be_focused()
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    paste_image(field, pixels)
    page.get_by_role("button", name="View attached image 1", exact=True).click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    field.click()
    expect(field).to_be_focused()
    words = "Phone final review: image and greeting checked."
    page.keyboard.type(words)
    expect(field).to_have_js_property("value", words)
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    with sending(page, "the file comment after image inspection"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"] == first["anchor"]
    assert sent["text"] == words + "\n\n![Attached image](/media/051bee487bfb5d13.png)"
    assert "about" not in sent


def test_a_pasted_image_survives_the_reply_draft_and_renders_from_the_message(
    browser, serve
):
    """Every thread text box shares one paste path, exercised through a reply.

    The binary body becomes page media before its Markdown reference enters the normal
    draft generation. Reload and Send then prove the existing durable-text path owns the
    rest of the loop, down to the exact pixels the rendered message reads back.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Can you show me the rendering fault?",
        {"section": "how-store"},
        "agent",
    )
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    # The thread's reply is the panel's field, which holds its draft's media too.
    field = page.locator(".lf-fp-field")
    reply = panel_field(page)
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()

    paste_image(reply, pixels)

    image_markdown = "![Attached image](/media/051bee487bfb5d13.png)"
    expect(reply).to_have_js_property("value", "")
    draft_image = page.locator(".lf-fp-card .lf-composer-media-item img")
    expect(draft_image).to_be_visible()
    expect(draft_image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    remove = page.locator(".lf-fp-card .lf-composer-media-remove")
    expect(remove).to_have_css("border-radius", "3px")
    expect(field.get_by_role("button", name="Send", exact=True)).to_have_attribute(
        "aria-disabled", "false"
    )

    page.reload()
    wait_until_ready(page)
    thread = open_panel_thread(page, root)
    reply = panel_field(page)
    expect(reply).to_have_js_property("value", "")
    expect(page.locator(".lf-fp-card .lf-composer-media-item img")).to_be_visible()
    # Mirroring compares the complete draft rather than the text box's projection. A
    # local keystroke must therefore keep the caret where the user put it even while
    # hidden image Markdown rides beside the visible words.
    write(reply, "Fault here")
    reply.evaluate("box => box.setSelectionRange(6, 6)")
    reply.press_sequentially("is ")
    expect(reply).to_have_js_property("value", "Fault is here")

    with sending(page, "the reply containing the pasted image"):
        field.get_by_role("button", name="Send", exact=True).click()
    saved = events_model.read_events(serve.page_dir)[-1]
    assert (saved["kind"], saved["parent"], saved["text"]) == (
        "reply",
        root,
        f"Fault is here\n\n{image_markdown}",
    )
    image = thread.locator(".lf-msg.user .lf-msg-body img")
    expect(image).to_have_attribute("src", "/media/051bee487bfb5d13.png")
    media_open = image.locator("xpath=..")
    expect(media_open).to_have_attribute(
        "data-lf-media-url", "/media/051bee487bfb5d13.png"
    )
    page.wait_for_function(
        "image => image.naturalWidth > 0", arg=image.element_handle()
    )
    url_before = page.url
    media_open.click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    assert viewer.evaluate("dialog => dialog.matches(':modal')")
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    assert page.url == url_before
    # The modal viewer holds the keyboard: a page command does not reach the page.
    page.keyboard.press("w")
    expect(viewer).to_be_visible()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    close = viewer.get_by_role("button", name="Close image preview", exact=True)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    close.click()
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    media_open.click()
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    expect(viewer.locator("img")).to_have_attribute("alt", "Attached image")
    # Native close notification arrives after its gesture. An image opened before that
    # notification belongs to the new opening and keeps both its pixels and focus.
    reopened = media_open.evaluate(
        """trigger => new Promise(resolve => {
          const viewer = document.querySelector('#lf-media-viewer');
          viewer.addEventListener('close', () => resolve({
            open: viewer.open,
            image: viewer.querySelector('img')?.getAttribute('src') ?? null,
            focused: viewer.contains(document.activeElement),
          }), {once: true});
          // The sensor sees one task ending where it began as an unchanged `open`
          // write; here the two native transitions deliberately exercise that race.
          window.lfUnwatched(() => {
            viewer.close();
            trigger.click();
          });
        })"""
    )
    assert reopened == {
        "open": True,
        "image": "/media/051bee487bfb5d13.png",
        "focused": True,
    }
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    assert (serve.page_dir / "media" / "051bee487bfb5d13.png").read_bytes() == pixels


def test_firefox_paints_the_author_and_words_in_the_same_send_flash(
    firefox_browser, serve
):
    """A natural send fades its sticky author and words together in actual frames.

    Pausing the animation or repeatedly reading styles invalidates Firefox's paint
    and conceals a stale inherited background. Native screencast frames observe its
    ordinary compositor path, including the receipt repaint, without those reads.
    """
    page, _box, send, _after, _reply = pressed_send_surface(
        firefox_browser, serve, "card"
    )
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate(
        """() => {
          window.__sendFlash = new Promise((resolve, reject) => {
            const root = document.querySelector('.lf-margin-preview');
            const observer = new MutationObserver(() => {
              const message = [...root.querySelectorAll('.lf-msg')].find(node =>
                node.textContent.includes('Sent from the box.'));
              if (!message) return;
              observer.disconnect();
              const cue = message.getAnimations()[0];
              if (!cue) {
                reject(new Error('the sent message has no arrival cue'));
                return;
              }
              cue.finished.then(() => {
                const head = message.querySelector('.lf-msg-head').getBoundingClientRect();
                const body = message.querySelector('.lf-msg-body').getBoundingClientRect();
                // Clear of the card's actions, whose controls stand beside the heads
                // of the messages they are level with.
                const actions = root.querySelector('.lf-margin-thread-controls')
                  ?.getBoundingClientRect();
                const beside = actions && actions.top < head.bottom
                  && actions.bottom > head.top;
                const x = Math.min(head.left + head.width * 0.7,
                  beside ? actions.left - 6 : Infinity);
                // The card's own edge on the same two rows, which says whether a frame
                // drew the card there at all.
                const edge = root.getBoundingClientRect().right - 1.5;
                resolve({head: [x, head.top + 3], body: [x, body.bottom - 3],
                  headEdge: [edge, head.top + 3], bodyEdge: [edge, body.bottom - 3]});
              }, reject);
            });
            observer.observe(root, {subtree: true, childList: true});
          });
        }"""
    )
    frames = []
    with page.screencast.start(
        on_frame=lambda frame: frames.append(frame),
        quality=100,
        size=page.viewport_size,
    ):
        send.click()
        points = page.evaluate("() => window.__sendFlash")
    readings = []
    for frame in frames:
        pixels = Image.open(io.BytesIO(frame["data"])).convert("RGB")
        colours = {
            name: rgb_pixel(pixels, tuple(round(coordinate) for coordinate in point))
            for name, point in points.items()
        }
        # Headless Firefox's capture without the classic bars now and then hands over a
        # frame with the page drawn across the card in a band, the card's edge gone
        # there as well (main's own panel chrome shows it too). Such a frame says
        # nothing about the message's two grounds, so it is read only where the
        # card's edge stands the same on both rows.
        drawn = (
            max(
                abs(a - b)
                for a, b in zip(colours["headEdge"], colours["bodyEdge"], strict=True)
            )
            <= 6
        )
        if drawn:
            readings.append(colours)
    # The light card fades from yellow (#fff8c5) to paper. Require an actual
    # sequence of intermediate colours: a discrete jump, or the constant .5
    # pending opacity blending yellow with paper, must not pass as a fade.
    fading = [
        reading
        for reading in readings
        if reading["body"][0] > 245 and 205 < reading["body"][2] < 240
    ]
    assert fading, readings
    blues = {reading["body"][2] for reading in fading}
    assert len(blues) >= 3 and max(blues) - min(blues) >= 12, fading
    assert all(
        max(abs(a - b) for a, b in zip(reading["head"], reading["body"], strict=True))
        <= 3  # Native JPEG rounding of otherwise uniform ground.
        for reading in fading
    ), fading


def test_a_rewrite_never_replaces_words_it_did_not_see(browser, serve):
    """Another tab holding a message's old words behind its news notice opened a rewrite
    on them, and its save silently took the place of the rewrite the first tab had made.
    A rewrite opened before the words changed is refused, its words kept; opened again,
    it shows the other's words on the message and is written over them."""
    url = serve(THREAD_DIFF_PAGE)
    mine = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    context = browser.new_context()
    tabs = []
    for _ in range(2):
        tab = open_page(browser, url, context=context)
        resized(tab, 1200, 900)
        open_panel_thread(tab, mine["id"])
        tabs.append(tab)
    a, b = tabs
    in_a, in_b = (
        tab.locator(f'{PANEL_THREAD} .lf-msg[data-message="{mine["id"]}"]')
        for tab in tabs
    )
    expect(in_a).to_be_visible()
    expect(in_b).to_be_visible()
    # B opens a rewrite before A's lands.
    in_b.locator(".lf-msg-text").dblclick()
    expect(in_b.locator(".lf-msg-editor leaf-text")).to_be_focused()
    a.bring_to_front()
    in_a.locator(".lf-msg-text").dblclick()
    a.keyboard.press("ControlOrMeta+a")
    a.keyboard.type("Saved in A.")
    a.keyboard.press("Enter")
    round_trip(a)
    b.bring_to_front()
    in_b.locator(".lf-msg-editor leaf-text").focus()
    b.keyboard.press("ControlOrMeta+a")
    b.keyboard.type("Saved in B.")
    b.keyboard.press("Enter")
    round_trip(b)
    consume_browser_errors(b, http_error_console(400))
    # Refused, B's words wait as its rewrite.
    expect(in_b.locator(".lf-msg-editor")).to_have_count(0)
    expect(in_b.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    told(b)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [e["text"] for e in edits] == ["Saved in A."]
    # Opened again, the rewrite shows A's words on the message and is written over them.
    in_b.locator(".lf-msg-text").dblclick()
    editor = in_b.locator(".lf-msg-editor leaf-text")
    expect(editor).to_have_js_property("value", "Saved in B.")
    expect(in_b.locator(".lf-edited")).to_have_attribute(
        "title", re.compile("Before, it said: “Fit the north bracket.”")
    )
    b.keyboard.press("Enter")
    round_trip(b)
    edits = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "edit"]
    assert [(e["text"], e["base"]) for e in edits] == [
        ("Saved in A.", mine["id"]),
        ("Saved in B.", edits[0]["id"]),
    ]


def test_a_region_capture_keeps_scrolled_shadow_pixels_and_its_comment_anchor(
    browser, serve
):
    page = capture_page(browser, serve)
    target = page.locator("#capture-target").bounding_box()
    left, top = int(target["x"]) + 10, int(target["y"]) + 10
    surface = open_capture_area(page)
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(left + 360, top + 180, steps=5)
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.mouse.up()
    expect(surface).to_be_hidden()
    attachment = page.locator(".lf-composer-media-item img")
    expect(attachment).to_be_visible()
    media_url = attachment.get_attribute("src")
    pixels = (serve.page_dir / media_url.lstrip("/")).read_bytes()
    image = Image.open(io.BytesIO(pixels)).convert("RGB")
    assert image.size == (720, 360)
    assert rgb_pixel(image, (40, 80)) == (30, 80, 240)
    assert rgb_pixel(image, (440, 280)) == (10, 150, 30)
    field = page.locator(".lf-fab-bar leaf-text")
    expect(field).to_be_focused()
    write(field, "Inspect this captured diagram.")
    with sending(page, "the anchored screenshot comment"):
        field.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment"
    assert sent["anchor"]["section"] == "capture-target"
    assert media_url in sent["text"]
    assert "Inspect this captured diagram." in sent["text"]
    page.reload()
    wait_until_ready(page)
    thread = open_panel_thread(page, sent["id"])
    expect(thread.locator(".lf-message-media img")).to_have_attribute("src", media_url)
    assert (serve.page_dir / media_url.lstrip("/")).read_bytes() == pixels


def test_a_region_capture_draws_live_samples_and_survives_removed_links(browser, serve):
    """The parent cannot read a sample's opaque frame, so a capture without the child's
    own image showed a placeholder box where the user saw the practice page. An image
    SnapDOM cannot read attaches the capture anyway, with a notice: SnapDOM draws the
    whole element that holds the crop and cannot say whether the image fell inside
    it. A capture
    also leaves SnapDOM watching mutations, and a removed link's subtree once threw from
    that observer as an uncaught page error."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, device_scale_factor=2
    )
    page = open_page(browser, serve(CAPTURE_SAMPLE_PAGE), context=context)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    warnings = []
    page.on("console", lambda message: warnings.append(message.text))
    page.evaluate("document.querySelector('#capture-sample').ready")
    # Another origin without CORS: visible to the reader, unreadable to SnapDOM.
    page.evaluate("""() => new Promise(resolve => {
        const image = document.createElement('img');
        image.id = 'unreadable';
        image.src = new URL('icon.svg', location.href).href
            .replace('127.0.0.1', 'localhost');
        image.onload = image.onerror = resolve;
        document.querySelector('#capture-sample').before(image);
    })""")
    frame = page.locator("#capture-sample iframe").bounding_box()
    # The area takes in the unreadable image above the sample, so the element the
    # capture draws holds it (`captureRoot`, composing/page-image.js).
    unreadable = page.locator("#unreadable").bounding_box()
    surface = open_capture_area(page)
    left, top = int(unreadable["x"]) + 1, int(unreadable["y"]) + 1
    page.mouse.move(left, top)
    page.mouse.down()
    page.mouse.move(
        int(frame["x"] + frame["width"]) - 1, int(frame["y"]) + 260, steps=5
    )
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.mouse.up()
    expect(surface).to_be_hidden()
    media_url = page.locator(".lf-composer-media-item img").get_attribute("src")
    image = Image.open(
        io.BytesIO((serve.page_dir / media_url.lstrip("/")).read_bytes())
    ).convert("RGB")
    paint = page.locator("#capture-sample iframe").content_frame.locator("#child-paint")
    inside = paint.bounding_box()
    at = (round((inside["x"] + 20 - left) * 2), round((inside["y"] + 20 - top) * 2))
    assert rgb_pixel(image, at) == (200, 40, 40)
    assert not [text for text in warnings if "cross-origin iframe" in text]
    expect_panel_says(page, "An image near this area could not be drawn")
    consume_browser_errors(page, "localhost", "ERR_FAILED")

    page.evaluate("""() => new Promise(resolve => {
        const link = document.createElement('a');
        link.href = 'http://127.0.0.1:9/elsewhere';
        const label = link.appendChild(document.createElement('span'));
        document.querySelector('main').append(link);
        setTimeout(() => {
            label.setAttribute('data-moved', '');
            link.remove();
            setTimeout(resolve, 50);
        });
    })""")
    assert errors == []
