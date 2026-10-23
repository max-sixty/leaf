"""Comment-panel ordering, narrowing, and thread-motion tests."""

import io
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
)
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    panel_comment,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    PANEL_THREAD,
    RELEASE_FOCUS,
    consume_browser_errors,
    example_media,
    http_error_console,
    open_page,
    panel_field,
    panel_settled,
    resized,
    round_trip,
    sending,
    told,
    write,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

from browser.threads import (
    CHANGE_HEAD,
    CHANGE_PAGE,
    IN_LANDING_BAND,
    REPLY_CHANGE,
    append_agent_reply,
    capture_page,
    claim_for_codex,
    open_capture_area,
    open_panel_thread,
    paste_image,
    pressed_send_surface,
    seed_panel_threads,
    seed_reply,
    stream_reply,
)
from render_harness import leaf_page

from journeys import detached_threads, expect_panel_says

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


@pytest.mark.watch_shifts
def test_a_reply_sent_while_the_agent_streams_moves_nothing_when_accepted(
    browser, serve, request
):
    """The user's message joins the thread above the reply still streaming, where the
    log will take that reply's answer, so the log accepting it moves nothing, and the
    stream's growth in the same readings is its arrival, not an edit.

    The panel drew the user's pending message below the streaming reply, and the
    accepted reading, whose live reply stands after every logged message, moved the
    reply below it.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Record the release", {"section": "h-how"})
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "First words")

    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    streamed = thread.locator(".lf-msg.agent")
    expect(streamed.locator(".lf-msg-text")).to_have_text("First words")
    write(panel_field(page), "And note the date")
    # The shift watch holds the acceptance to moving nothing; the order is where the
    # send drew it.
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    told(page)
    messages = thread.locator(".lf-msg")
    expect(messages).to_have_count(3)
    expect(messages.nth(1)).to_contain_text("And note the date")
    expect(messages.nth(2)).to_contain_text("First words")

    page.evaluate(RELEASE_FOCUS)
    stream_reply(serve.page_dir, root, "First words and more of them")
    told(page)
    expect(streamed.locator(".lf-msg-text")).to_have_text(
        "First words and more of them"
    )
    expect(page.locator(".lf-fp-controls .lf-thread-news:visible")).to_have_count(0)


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
    # The shelf's face, its picture alone with a round removal on its corner, reaches
    # the widget's tree too (response.css).
    expect(image_open).to_have_css("border-radius", "8px")
    expect(remove).to_have_css("border-radius", "50%")
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
    action = bar.locator(".lf-compose-field > button:visible")
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
    expect(remove).to_have_css("border-radius", "50%")
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


@pytest.mark.watch_shifts
@pytest.mark.parametrize("reply_size", ["short", "tall"])
def test_an_idle_open_panel_thread_shows_appended_replies(browser, serve, reply_size):
    """An append to a thread open in the panel, with no reply being written, shows at
    once below the messages the user reads, which keep their place.

    Even an answer taller than the view must leave the previous reading in place."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    page.evaluate(RELEASE_FOCUS)
    message = thread.locator(".lf-msg").first
    rendered(page)
    before = {
        "offset": message.evaluate(
            "m => m.getBoundingClientRect().top"
            " - m.closest('.lf-fp-view').getBoundingClientRect().top"
        ),
        "scroll": thread.evaluate("view => view.scrollTop"),
    }
    words = "The answer arrived without another click."
    if reply_size == "tall":
        words = "\n\n".join([words] * 30)
    reply = append_agent_reply(serve.page_dir, root, words)
    told(page)
    expect(thread.locator(f'.lf-msg[data-event="{reply["id"]}"]')).to_be_visible()
    expect(page.locator(".lf-fp-controls .lf-thread-news:visible")).to_have_count(0)
    rendered(page)
    # The view grows to hold the answer, the message keeping its place within it.
    assert message.evaluate(
        "m => m.getBoundingClientRect().top"
        " - m.closest('.lf-fp-view').getBoundingClientRect().top"
    ) == pytest.approx(before["offset"], abs=0.5)
    assert thread.evaluate("view => view.scrollTop") == before["scroll"]


def test_a_settlement_in_a_reply_leaves_its_own_anchor_on_the_page(browser, serve):
    """A decided change keeps whatever of itself is still showing, wherever it stands.

    `settledAway` asks whether a decision emptied an element: every child now a retired
    slot or the runtime's own apparatus, with no words of its own left. Asked about the
    page that test is right; asked about a change an agent sent in a reply it was asked
    the wrong way round, because the panel holding it is itself the runtime's apparatus
    and so every child of it answered yes. One accepted slot then emptied a change whose
    other half was on screen: the anchor a user had put on it stopped resolving, the
    outline came off, and the thread stood detached beside the words it was about.

    The same change on the page is the control, and the two must agree."""
    for where, markup, wid in (
        ("the page", CHANGE_PAGE, "tv-doc-sug"),
        ("a reply", BARE_PAGE, "tv-msg-sug"),
    ):
        url = serve(markup)
        d = serve.page_dir
        if wid.startswith("tv-msg"):
            seed_reply(d, REPLY_CHANGE, wid)
        else:
            append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "id": "tv-on-it",
                    "author": "user",
                    "revision": 1,
                    "text": "Why ninety?",
                    "anchor": {"section": wid},
                },
            )
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": wid,
                "action": "decide",
                "detail": {"outcome": "accept"},
            },
        )
        page = open_page(browser, url)
        resized(page, 1280, 900)
        if wid.startswith("tv-msg"):
            open_panel_thread(page, "tv-decisioned")
            rendered(page)
        settled = page.evaluate(
            """(wid) => {
                 const el = document.getElementById(wid);
                 return { state: el?.dataset.lfState,
                          retired: [...(el?.querySelectorAll('[data-lf-retired]') ?? [])].length,
                          marked: Boolean(el?.classList.contains('lf-mark-el')) };
               }""",
            wid,
        )
        # The panel shows one thread at a time, so opening the anchored thread there
        # to read its quote would take down the reply holding the change it is about:
        # in a reply the outline (`marked`) is what says the anchor still resolves.
        settled["detached"] = wid.startswith("tv-doc") and "tv-on-it" in (
            detached_threads(page, ["tv-on-it"])
        )
        assert settled["state"] == "accept" and settled["retired"] == 1, (
            f"{where}: the change did not settle, so nothing here is being read "
            f"({settled})"
        )
        assert not settled["detached"] and settled["marked"], (
            f"{where}: the accepted change took its own anchor off the page "
            f"({settled}) — its other half is still showing"
        )


def test_walking_the_threads_lands_each_on_its_latest_message(browser, serve):
    """`t` and `T` open each thread in the panel on its latest message, as a direct
    arrival does, so a user walking back to a conversation taller than the view
    reads its newest turn without scrolling to it."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    resized(page, 800, 520)
    page.evaluate(RELEASE_FOCUS)

    def walk(key, root):
        page.keyboard.press(key)
        view = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
        expect(view).to_be_focused()
        panel_settled(page, view="thread")
        rendered(page)
        return view.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)

    forward = {root: walk("t", root) for root in roots[:7]}
    back = [walk("Shift+t", root) for root in (roots[5], roots[4], roots[3])][-1]

    assert all(landed["inside"] for landed in forward.values()), forward
    assert back["inside"], back
    assert page.locator(f'{PANEL_THREAD}[data-thread="{roots[3]}"]').evaluate(
        "view => view.scrollHeight > view.clientHeight"
    ), "the long thread fits its view, so landing its latest message proves nothing"


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
                // Clear of the card's actions, whose own ground stands beside the
                // heads of the messages they are level with.
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
            name: pixels.getpixel(tuple(round(coordinate) for coordinate in point))
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


def test_agent_titles_update_without_losing_the_users_draft(browser, serve):
    url = serve(PANEL_PAGE)
    opening = "I was wondering which space would be easier for everyone to find."
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    other = panel_comment(serve.page_dir, "Keep the filter rows compact.")
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    title = page.locator(".lf-fp-head .lf-fp-title")
    editor = panel_field(page)
    write(editor, "Keep this unfinished reply")
    for name in ("Workshop venue", "Terrace accessibility"):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(serve.page_dir),
                root,
                "--title",
                name,
            ],
        )
        assert result.exit_code == 0, result.output
        told(page)
        expect(title).to_have_text(name)
        expect(editor).to_have_js_property("value", "Keep this unfinished reply")
        expect(thread.get_by_text(opening, exact=True)).to_be_visible()
    # Threads finds the thread by the title the agent gave it.
    page.locator(".lf-fp-back").click()
    panel_settled(page, view="threads")
    page.get_by_role("button", name="Find a thread or message").click()
    page.locator("input.lf-fp-search").fill("Terrace accessibility")
    expect(page.locator(f'.lf-fp-thread[data-key="{other}"]')).to_have_count(0)
    expect(page.locator(f'.lf-fp-thread[data-key="{root}"]')).to_be_visible()
    page.locator("input.lf-fp-search").fill("")
    expect(page.locator(f'.lf-fp-thread[data-key="{other}"]')).to_be_visible()
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, root)
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(
        "Terrace accessibility"
    )


def test_the_user_rewrites_their_own_message_where_it_stands(browser, serve):
    """A double click, or ↑ from the thread's empty reply box, opens the user's own
    words in place. Enter sends the rewrite; Escape and Cancel leave the message as it
    was and discard the words, so one Escape undoes the ↑ (the user's decision,
    2026-10-06). Words a rewrite still holds when the page goes, as on a reload, wait
    for the next opening, which Resume writing reaches.

    The rewrite draws on the message in the gesture, labelled edited, and reaches the
    log as one `edit` naming the message. The agent's words offer no rewrite, and the
    same message in the page's seat stays as it reads while the panel edits it.
    """
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    mine = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "rewritten",
            "author": "user",
            "revision": 1,
            "text": "Fit the north bracket.",
            "anchor": {"section": "cd-q"},
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "parent": mine["id"],
            "responds": mine["id"],
            "text": "Fitted.",
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = open_panel_thread(page, mine["id"])
    message = thread.locator(f'.lf-msg[data-message="{mine["id"]}"]')
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    expect(thread.locator(".lf-msg.agent .lf-msg-edit")).to_have_count(0)

    message.locator(".lf-msg-text").dblclick()
    editor = message.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    seat = page.locator(f'#cd-q .lf-msg[data-event="{mine["id"]}"]')
    expect(seat.locator(".lf-msg-text")).to_have_text("Fit the north bracket.")
    expect(seat.locator(".lf-msg-editor")).to_have_count(0)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Fit the south bracket.")
    page.keyboard.press("Enter")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")
    expect(message.locator(".lf-edited")).to_have_text("edited")
    round_trip(page)
    edits = [e for e in events_model.read_events(d) if e["kind"] == "edit"]
    assert [(e["author"], e["message"], e["text"]) for e in edits] == [
        ("user", mine["id"], "Fit the south bracket.")
    ]

    reply = panel_field(page)
    reply.focus()
    page.keyboard.press("ArrowUp")
    expect(editor).to_be_focused()
    page.keyboard.type(" Or not.")
    page.keyboard.press("Escape")
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-text")).to_have_text("Fit the south bracket.")
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    # Escape steps back up one rung, to the reply box ↑ came from.
    expect(reply).to_be_focused()
    message.locator(".lf-msg-text").dblclick()
    expect(editor).to_have_js_property("value", "Fit the south bracket.")
    page.keyboard.type(" Or the east.")
    # Words a rewrite holds when the page goes wait for its next opening.
    page.reload()
    wait_until_ready(page)
    open_panel_thread(page, mine["id"])
    expect(message.locator(".lf-msg-kept")).to_have_text("unsaved edit")
    # The thread opens with the caret in its reply; Escape stands on the thread.
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Fit the south bracket. Or the east.")
    message.get_by_role("button", name="Discard").click()
    expect(message.locator(".lf-msg-editor")).to_have_count(0)
    expect(message.locator(".lf-msg-kept")).to_have_count(0)
    round_trip(page)
    assert len([e for e in events_model.read_events(d) if e["kind"] == "edit"]) == 1


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
    assert image.getpixel((40, 80)) == (30, 80, 240)
    assert image.getpixel((440, 280)) == (10, 150, 30)
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
    SnapDOM cannot read attaches the capture anyway, with a notice: SnapDOM reads a
    margin beyond the crop and cannot say whether the image fell inside it. A capture
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
        image.src = new URL('icon.svg', location.href).href
            .replace('127.0.0.1', 'localhost');
        image.onload = image.onerror = resolve;
        document.querySelector('#capture-sample').before(image);
    })""")
    sample = page.locator("#capture-sample").bounding_box()
    frame = page.locator("#capture-sample iframe").bounding_box()
    surface = open_capture_area(page)
    left, top = int(sample["x"]) + 1, int(sample["y"]) + 1
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
    assert image.getpixel(at) == (200, 40, 40)
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
