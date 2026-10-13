"""Durable user acknowledgement through the rendered Thread surfaces."""

import json
import re
import time

import pytest
from interact_support import append_carried_log_record, served_thread, wait_for
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.render_checks import (
    PROBE_POLL_MS,
    SERVED_TIMEOUT_MS,
    rendered,
    wait_until_ready,
)
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_cases_navigation import source_revision
from render_cases_widgets import LONG_LINE_DIFF_PAGE, MULTI_HUNK_PATCH
from render_harness import (
    Traffic,
    _traffic,
    holding,
    is_problem,
    leaf_page,
    open_page,
    panel_settled,
    round_trip,
    select,
    sending,
    take_browser_errors,
    told,
    write,
)


def _read_events(page_dir):
    return [
        event for event in events_model.read_events(page_dir) if event["kind"] == "read"
    ]


def _select_new_route(page):
    """Drag across "new route" on the diff's routes.py line 201, as a user selects it."""
    row = page.locator('lf-diff [data-lf-datum=\'["app/routes.py","new",201]\']')
    row.scroll_into_view_if_needed()
    points = row.evaluate("""element => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const nodes = [], starts = [];
      let text = '';
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        starts.push(text.length); nodes.push(node); text += node.data;
      }
      const start = text.indexOf('new route');
      if (start < 0) throw new Error('diff phrase missing');
      const glyph = offset => {
        const index = starts.findLastIndex(value => value <= offset);
        const range = document.createRange();
        range.setStart(nodes[index], offset - starts[index]);
        range.setEnd(nodes[index], offset - starts[index] + 1);
        return range.getBoundingClientRect();
      };
      const first = glyph(start), last = glyph(start + 'new route'.length - 1);
      return [[first.left, first.top + first.height / 2],
              [last.right, last.top + last.height / 2]];
    }""")
    select(page, *points)


def _agent_update_reply(page_dir, root, number, for_event=None):
    return thread_model.post_reply(
        page_dir,
        {"to": root, "for": for_event},
        f"Update {number}.\n\nCompleted steps: {number}.",
        settlement=thread_model.ProviderFinal("test-final"),
    )["id"]


def test_progress_is_never_unread_and_reading_its_answer_leaves_it_folded(
    browser, serve
):
    """Pending progress pulls the user back to nothing; the answer that folds it is
    the thread's one unread message, and reading it unfolds nothing."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "An earlier conversation.")
    root = panel_comment(serve.page_dir, "Check the schedule.")
    progress = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "Checking mounts.", ephemeral=True
    )["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).not_to_have_attribute("open", "")
    expect(card.locator(".lf-thread-unread")).to_have_count(0)

    answer = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "Both mounts fit."
    )["id"]
    told(page)
    expect(card.locator(".lf-thread-unread")).to_have_text("1 unread")
    # A fresh transcript starts with completed progress folded, as on a later visit.
    page.reload()
    wait_until_ready(page)
    card.locator(":scope > .lf-thread-summary").click()
    expect(card.locator(f'.lf-msg[data-mid="{answer}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-mid="{progress}"]')).to_be_hidden()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    round_trip(page)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": answer, "version": answer}
    ]

    expand = card.get_by_role("button", name="Show 1 progress message", exact=True)
    expand.press("Enter")
    expect(card.get_by_text("Checking mounts.", exact=True)).to_be_visible()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    page.reload()
    wait_until_ready(page)
    expect(page.locator(".lf-first-unread")).to_be_hidden()


def test_first_unread_opens_the_exact_message_and_exposure_acknowledges_it(
    browser, serve
):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "An answer for the user.", author="agent")
    page = open_page(browser, url)

    expect(page.locator(".lf-first-unread")).to_have_text("Next unread")
    expect(page.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "1 unread message. Go to first unread message"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-label", "Open threads: 2, 1 unread thread"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "data-unread-threads", ""
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "title", "Show or hide the thread panel; 1 unread thread (g T)"
    )
    thread_control_width = page.locator(".lf-threads-toggle").bounding_box()["width"]
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card.locator(".lf-thread-unread")).to_have_text("1 unread")
    with sending(page, "first unread acknowledgement"):
        page.locator(".lf-first-unread").click()
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_focused()
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).not_to_have_class(
        re.compile(r"(^|\s)lf-unread(\s|$)")
    )
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "data-unread-threads", ""
    )
    expect(page.locator(".lf-threads-toggle")).not_to_have_attribute(
        "aria-label", re.compile("unread")
    )
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "title", "Show or hide the thread panel (g T)"
    )
    assert (
        abs(
            page.locator(".lf-threads-toggle").bounding_box()["width"]
            - thread_control_width
        )
        < 1
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    page.reload()
    expect(page.locator(".lf-first-unread")).to_be_hidden()


def test_oversized_message_needs_contiguous_traversal(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir,
        "\n\n".join(
            f"Paragraph {number}. " + "Complete content matters. " * 20
            for number in range(36)
        ),
        author="agent",
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-first-unread").click()
    body = page.locator(f'.lf-msg[data-mid="{root}"] .lf-msg-body')
    assert (
        body.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    )
    page.locator(".lf-threads").evaluate(
        "element => element.scrollTop = element.scrollHeight"
    )
    page.wait_for_timeout(100)
    assert _read_events(serve.page_dir) == []

    page.locator(".lf-threads").evaluate("element => element.scrollTop = 0")
    page.locator(".lf-threads").hover()
    list_height = page.locator(".lf-threads").evaluate(
        "element => element.clientHeight"
    )
    for _ in range(100):
        if page.locator(".lf-threads").evaluate(
            "element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1"
        ):
            break
        page.mouse.wheel(0, list_height / 4)
        page.wait_for_timeout(20)
    else:
        raise AssertionError("mouse wheel did not traverse the complete answer")
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_edit_reopens_only_its_new_content_version(browser, serve):
    url = serve(PANEL_PAGE)
    user = panel_comment(serve.page_dir, "The earlier user thread.")
    original = thread_model.cmd_comment(
        serve.page_dir, None, None, None, "Original answer.", None
    )
    root = original["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-first-unread").click()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    page.locator(f'.lf-thread[data-id="{user}"] > .lf-thread-summary').click()
    page.locator('.lf-thread-panel [aria-label="Close threads"]').click()

    [edit] = thread_model.cmd_edit(serve.page_dir, root, "Revised answer.")
    told(page)
    expect(page.locator(".lf-first-unread")).to_have_text("Next unread")
    page.locator(".lf-threads-toggle").click()
    with sending(page, "edited answer read"):
        page.locator(".lf-first-unread").click()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": edit["id"]}
    ]


def test_an_acknowledgement_neither_waits_for_nor_holds_up_a_gesture(browser, serve):
    """A read acknowledgement is bookkeeping: it creates no work, a gesture made while
    it is in flight goes out beside it, its failure is silent while the gesture's is
    reported, and resolving the thread is itself evidence the user took it in."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "Read this answer.", author="agent")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-first-unread").click()
    holding(page, held, 1, "automatic read")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    message = card.locator(f'.lf-msg[data-mid="{root}"]')
    expect(message).not_to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    expect(message.locator(".lf-msg-sending")).to_have_count(0)
    assert (
        json.loads(page.locator("html").get_attribute("data-lf-traffic"))["pending"]
        == []
    )
    assert page.evaluate(
        "async () => (await window.__lfCheckApi()).readApplication().unresolved.length === 0"
    )

    card.get_by_role("button", name="Resolve thread").click()
    holding(page, held, 2, "a resolve sent while the read is held")
    assert [route.request.post_data_json["kind"] for route in held] == [
        "read",
        "resolve",
    ]
    held[0].fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused before append"}
    )
    expect(message).to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    page.unroute("**/api/event")
    held[1].abort()
    expect(page.locator(".lf-notice")).to_contain_text("Connection lost")
    told(page)
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir) == []
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["author"] == "user"
    ] == ["comment", "resolve"]
    assert not any(
        "Couldn't send" in text
        for text in page.locator(".lf-notice").all_text_contents()
    )
    assert all(
        is_problem(error, "Failed to load")
        or (error.code == "failed-load" and "/api/event" in error.values["url"])
        for error in take_browser_errors(page)
    )


def test_visible_message_waits_for_whole_document_presentation(browser, serve):
    url = serve(PANEL_PAGE)
    # A long user opening pins the reply row, so the incoming answer can paint
    # immediately while the whole-document presentation proof is held below.
    root = panel_comment(
        serve.page_dir, "\n\n".join(["Please report the result with its context."] * 30)
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(":scope > .lf-thread-summary").click()
    assert (
        card.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    )
    page.evaluate("""() => {
      const list = document.querySelector('leaf-thread-list');
      const present = list.present.bind(list);
      let release;
      list.present = async model => {
        const candidate = await present(model);
        if (!window.__readHeld) {
          window.__readHeld = true;
          await new Promise(resolve => { release = resolve; });
        }
        return candidate;
      };
      window.__releaseReadPresentation = () => release();
    }""")
    reply = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The result is ready."
    )
    page.wait_for_function("window.__readHeld === true")
    body = card.locator(f'.lf-msg[data-mid="{reply["id"]}"] .lf-msg-body')
    expect(body).to_be_visible()
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    body.hover()
    page.wait_for_timeout(100)
    assert _read_events(serve.page_dir) == []

    page.evaluate("window.__releaseReadPresentation()")
    told(page)
    wait_for(
        lambda: _read_events(serve.page_dir),
        bool,
        failure="presented answer was not acknowledged",
    )
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


@pytest.mark.parametrize("origin", ["page", "reference"])
def test_keyboard_first_unread_exposes_authored_reply(browser, serve, origin):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = thread_model.cmd_comment(
        serve.page_dir,
        None,
        None,
        None,
        "Choose the next step.",
        '<lf-ask id="read-decision"><h3>Which way?</h3>'
        '<lf-options id="read-choice" choose>'
        '<lf-option id="read-yes">Yes</lf-option>'
        '<lf-option id="read-no">No</lf-option>'
        "</lf-options></lf-ask>",
    )["id"]
    page = open_page(browser, url)
    if origin == "reference":
        page.keyboard.press("?")
        page.keyboard.press("?")
        page.get_by_role("combobox", name="Search commands").fill("g u")
        route = page.locator(
            '.lf-command-reference tr[data-lf-command="thread.unread.first"]'
        )
        expect(route.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "u"])
    with sending(page, "authored reply read"):
        if origin == "reference":
            route.get_by_role("button").click()
        else:
            page.keyboard.press("g")
            page.keyboard.press("u")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(card).to_have_attribute("open", "")
    expect(card.locator(f'.lf-msg[data-mid="{root}"]')).to_be_focused()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_read_converges_across_two_tabs(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "The shared user answer.", author="agent")
    first = open_page(browser, url)
    second = open_page(browser, url)
    expect(first.locator(".lf-first-unread")).to_have_text("Next unread")
    expect(second.locator(".lf-first-unread")).to_have_text("Next unread")
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    first.locator(".lf-first-unread").click()
    expect(first.locator(".lf-first-unread")).to_be_hidden()
    told(second)
    expect(second.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


SAMPLE_READER = "a1b2c3d4"


def _sample_reading_page(browser, serve, body, style):
    """A page holding one live sample whose child page is taller than the window and
    carries one agent message, so the thread panel it opens stands the message near the
    frame's top. `style` places the sample; the returned child is its page, which keeps
    a log and a ledger of trips of its own (`Traffic`)."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Sample reading practice",
                body.format(
                    sample=f"""<lf-sample id="read-practice" label="Read practice">
  <template id="read-source" data-sample data-sample-threads="{SAMPLE_READER}">
    <style>#child-rest {{ height: 3000px; }}</style>
    <h1>Child page</h1>
    <div id="child-rest"></div>
  </template>
</lf-sample>"""
                ),
                head=f"<style>{style}</style>",
            ),
            events=[
                {
                    "id": SAMPLE_READER,
                    "kind": "comment",
                    "author": "agent",
                    "agent": "Agent",
                    "revision": 1,
                    "text": "A framed answer for the user.",
                }
            ],
        ),
    )
    frame = page.locator("#read-practice iframe")
    child = frame.element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    expect(child.locator(".lf-first-unread")).to_have_attribute(
        "aria-label", "1 unread message. Go to first unread message"
    )
    return page, frame, child


def _message_body(child):
    return child.locator(f'.lf-msg[data-mid="{SAMPLE_READER}"] .lf-msg-body')


def _open_first_unread(page, child):
    """The user opens the sample's Threads from its focused toggle and goes to its first
    unread message by key. Once the panel's slide has ended, the message stands whole in
    the child's own viewport, so what the containing page shows of the frame is all that
    is left to keep it unread."""
    page.keyboard.press("Enter")
    expect(child.locator(".lf-threads")).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("u")
    expect(child.locator(f'.lf-thread[data-id="{SAMPLE_READER}"]')).to_have_attribute(
        "open", ""
    )
    panel_settled(child)
    assert _message_body(child).evaluate("""body => {
        const box = body.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= innerHeight
            && box.left >= 0 && box.right <= innerWidth;
    }"""), "the message is not whole in the child's own viewport"


def _settled(page, child):
    """Deliver the owner's viewport, then wait for the child's renderable work.

    An offscreen child has no paint to wait for. Its rendering owner declares such
    work settled until it becomes visible; a visible child drains its reading pass.
    """
    rendered(page)
    child.wait_for_function(
        "() => Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)",
        polling=PROBE_POLL_MS,
        timeout=SERVED_TIMEOUT_MS,
    )


def _still_unread(page, child):
    """Once both pages settle (`_settled`), a pass that read the message would have
    hidden Next unread and counted a send."""
    _settled(page, child)
    assert child.locator(".lf-first-unread").is_visible()
    assert _traffic(child).sends == 0


def _read_by_the_sample(page, child):
    """The control: the child sends the message read, and its server holds it read."""
    expect(child.locator(".lf-first-unread")).to_be_hidden()
    round_trip(child)
    state = page.request.get(f"{child.url}api/state").json()
    (thread,) = served_thread(state["browser"])["threads"]
    assert thread["id"] == SAMPLE_READER
    assert thread["unread"] == []


def test_clipped_sample_cannot_acknowledge_child_viewport(browser, serve):
    # On the first screen, inside a scrolling box that shows only its top, the sample's
    # own page shows the message and the containing page does not.
    page, _, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Practice page</h1><div id="read-clip">{sample}</div>',
        "#read-clip { height: 100px; overflow: auto; }",
    )
    child.locator(".lf-threads-toggle").focus()
    _open_first_unread(page, child)
    _still_unread(page, child)

    # Scrolling the box until the message stands 20px below its top shows it, and the
    # same message is read.
    top = _message_body(child).evaluate("body => body.getBoundingClientRect().top")
    page.locator("#read-clip").evaluate(
        """(clip, top) => clip.scrollBy(0, clip.querySelector('iframe')
            .getBoundingClientRect().top + top - clip.getBoundingClientRect().top - 20)""",
        top,
    )
    _read_by_the_sample(page, child)


def test_offscreen_sample_cannot_acknowledge_child_viewport(browser, serve):
    page, frame, child = _sample_reading_page(
        browser,
        serve,
        '<h1>Practice page</h1><div id="read-gap"></div>{sample}',
        "#read-gap { height: 2000px; }",
    )
    # Below the first screen it shows nothing: the user focuses its Threads toggle and
    # scrolls the containing page back to the top first.
    child.locator(".lf-threads-toggle").focus()
    page.evaluate("scrollTo(0, 0)")
    _open_first_unread(page, child)
    assert frame.bounding_box()["y"] > page.viewport_size["height"]
    _still_unread(page, child)

    # Taller than the window, the sample is read through the band the containing page
    # shows as it scrolls: its edge coming into view shows nothing, and a later scroll of
    # the containing page shows the message.
    page.evaluate("""() => {
        const top = document.querySelector('#read-practice iframe')
            .getBoundingClientRect().top;
        scrollBy(0, top - innerHeight + 20);
    }""")
    _still_unread(page, child)
    page.evaluate("scrollBy(0, 700)")
    _read_by_the_sample(page, child)


def test_a_sample_in_a_native_modal_escapes_inherited_inertness(browser, serve):
    page, _, child = _sample_reading_page(
        browser,
        serve,
        "<h1>Native owner boundary</h1><section inert>"
        '<dialog id="owner-modal" open>{sample}</dialog></section>',
        "#owner-modal { width: 900px; height: 750px; }",
    )
    page.locator("#owner-modal").evaluate(
        "dialog => { dialog.close(); dialog.showModal(); }"
    )
    child.locator(".lf-threads-toggle").focus()
    _open_first_unread(page, child)
    _read_by_the_sample(page, child)


def _framed_reader(browser, serve):
    """A Leaf page framed by its own origin, below the containing page's first screen,
    with its first unread message opened unseen. Returns the containing page, the
    frame's locator and the framed page, which keeps a ledger of trips of its own."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Framed reading",
                '<h1>Containing page</h1><div id="frame-gap"></div>',
                head="<style>#frame-gap { height: 2000px; }"
                " #framed-reader { display: block; width: 100%; height: 500px;"
                " border: 0; margin-bottom: 2000px; }</style>",
            ),
            events=[
                {
                    "id": SAMPLE_READER,
                    "kind": "comment",
                    "author": "agent",
                    "agent": "Agent",
                    "revision": 1,
                    "text": "A framed answer for the user.",
                }
            ],
        ),
    )
    # Below the first screen, the framed page opens its first unread message unseen.
    page.locator("#frame-gap").evaluate(
        """async (gap, url) => {
            const frame = document.createElement('iframe');
            frame.id = 'framed-reader';
            frame.src = url;
            const loaded = new Promise(resolve =>
                frame.addEventListener('load', resolve, {once: true}));
            gap.after(frame);
            await loaded;
        }""",
        page.url,
    )
    frame = page.locator("#framed-reader")
    child = frame.element_handle().content_frame()
    wait_until_ready(child)
    child.lf_traffic = Traffic(child)
    child.locator(".lf-threads-toggle").focus()
    page.evaluate("scrollTo(0, 0)")
    _open_first_unread(page, child)
    _still_unread(page, child)
    return page, frame, child


def _framed_message_box(child):
    return _message_body(child).evaluate(
        "body => { const box = body.getBoundingClientRect();"
        " return {top: box.top, height: box.height}; }"
    )


def _place_frame(frame, top):
    """Scroll the containing page until the frame's top stands `top` down its window."""
    frame.evaluate(
        "(frame, at) => scrollBy(0, frame.getBoundingClientRect().top - at)", top
    )


def _framed_read(serve, child):
    expect(child.locator(".lf-first-unread")).to_be_hidden()
    round_trip(child)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": SAMPLE_READER, "version": SAMPLE_READER}
    ]


def _box_height(locator):
    return locator.evaluate("node => node.getBoundingClientRect().height")


@pytest.mark.parametrize("opening", ["notice", "return"])
def test_a_reply_held_in_a_diff_thread_is_read_once_the_keyboard_opens_it(
    browser, serve, opening
):
    """A reply landing in the diff thread the user had just written grew the thread at
    its foot, on screen, and everything after the diff moved down the page. It waits
    behind a notice in the thread's control row, which appears without changing the
    thread's height, and stays unread while none of it has shown. The keyboard reaches
    the notice from the thread and opens it, and the reply's body, drawn inside the
    widget's shadow tree, is read once shown. Leaving the thread for the file's header
    before it and walking back with t ("return") arrives at the thread, so it shows
    there too: both moves stay inside the widget's shadow tree, where the document hears
    no focus event. The browser fixture's shift watch holds the rest: the reply is
    news."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    # Selection opening is outstanding rendering when the native release returns,
    # even if a loaded event loop has not yet stood its response field.
    page.evaluate("""() => {
      window.selectionRelease = [];
      document.addEventListener('mouseup', event => {
        if (!event.composedPath().some(node => node.matches?.('lf-diff'))) return;
        queueMicrotask(() => selectionRelease.push({
          words: getSelection().toString(),
          settled: Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean),
        }));
      }, {once: true});
    }""")
    _select_new_route(page)
    assert page.evaluate("window.selectionRelease") == [
        {"words": "new route", "settled": False}
    ]
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    height = _box_height(thread)
    reply = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The route-line answer is ready."
    )
    told(page)
    news = thread.locator(
        ":scope > .lf-thread-content > .lf-thread-controls"
    ).get_by_role("button", name="1 new reply")
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)
    assert not _read_events(serve.page_dir)

    # A press into the reply box asks for the box, so the reply stays held under it.
    thread.locator(":scope > .lf-thread-reply leaf-text").click()
    expect(news).to_be_visible()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    if opening == "return":
        page.keyboard.press("Shift+Tab")
        assert thread.evaluate(
            """thread => {
              const at = thread.getRootNode().activeElement;
              return Boolean(at) && !thread.contains(at);
            }"""
        ), "Shift+Tab left the widget's shadow tree, so the return proves nothing"
        expect(news).to_be_visible()
        opens = "t"
    else:
        page.keyboard.press("Tab")
        expect(news).to_be_focused()
        opens = "Enter"
    with sending(page, "opened diff reply read"):
        page.keyboard.press(opens)
        expect(news).to_have_count(0)
        if opening == "notice":
            expect(thread).to_be_focused()
        body = thread.locator(f'.lf-msg[data-event="{reply["id"]}"] .lf-msg-body')
        expect(body).to_be_visible()
        assert body.evaluate("element => element.getRootNode() instanceof ShadowRoot")
        body.scroll_into_view_if_needed()
    expect(page.locator(".lf-first-unread")).to_be_hidden()
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": reply["id"], "version": reply["id"]}
    ]


def test_a_walk_to_a_thread_a_diff_line_holds_lands_in_its_outlet(browser, serve):
    """A second thread the agent starts on a diff line the user's thread stands on waits
    behind that thread's notice, undrawn. A t walk to it shows it in the line's outlet
    and lands there, rather than opening Threads for a thread the page has no node
    for."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comment = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{comment["id"]}"]')
    expect(thread).to_be_visible()
    second = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "And should the alias warn?",
            "anchor": comment["anchor"],
        },
    )["id"]
    told(page)
    news = thread.locator(
        ":scope > .lf-thread-content > .lf-thread-controls"
    ).get_by_role("button", name="1 new thread")
    expect(news).to_be_visible()
    landed = page.locator(f'lf-diff .lf-page-thread[data-thread="{second}"]')
    expect(landed).to_have_count(0)
    page.keyboard.press("t")
    expect(landed).to_be_visible()
    assert landed.evaluate(
        "thread => thread.contains(thread.getRootNode().activeElement)"
    ), "the walk did not land in the outlet"
    expect(page.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(news).to_have_count(0)


# A task whose seat stands past a screen of prose, with more prose after it for a
# thread's growth to move.
def _seat_filler(name):
    return "".join(
        f"<p id='{name}-{n}'>Filler paragraph {n}, long enough to take a line.</p>"
        for n in range(30)
    )


TASK_SEAT_PAGE = leaf_page(
    "seat",
    f"<h1 id='h'>Three jobs</h1>{_seat_filler('lead')}<lf-test-plan id='hub' "
    "label='Before the frost'><lf-test-task id='jobs' status='active' talk>"
    f"<strong>Which jobs are worth starting?</strong></lf-test-task></lf-test-plan>"
    f"{_seat_filler('tail')}",
)


# Scrolling the thread away releases held news the same way here as on a diff line,
# whose case scrolls it.
@pytest.mark.parametrize("end", ["opened", "walked", "onto", "replied"])
def test_replies_held_in_a_page_seat_show_when_the_user_turns_to_them(
    browser, serve, end
):
    """Replies landing while a seated thread's foot is on screen wait behind one
    notice that counts them, and show together, in the order they came: when the user
    presses the notice, when a t press walks them to the thread, when they send a turn
    of their own, which answers the replies and so follows them. A t press
    onto the thread they already stand in ("onto") is a stay, and the replies wait on.
    Nothing before the ending is input, so the browser fixture's shift watch also checks
    that holding the replies moved nothing."""
    url = serve(TASK_SEAT_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which of these can wait until spring?",
            "anchor": {"section": "jobs"},
        },
    )["id"]
    page = open_page(browser, url)
    thread = page.locator(f'.lf-thread-seat .lf-page-thread[data-thread="{root}"]')
    thread.evaluate(
        """thread => document.scrollingElement.scrollBy({
          top: thread.getBoundingClientRect().top - innerHeight / 3,
          behavior: 'instant'})"""
    )
    if end == "onto":
        # The key before the focus makes the shortcut bar's redraw an answer to input.
        page.keyboard.press("Shift")
        thread.focus()
    height = _box_height(thread)
    replies = []
    for n in (1, 2):
        replies.append(
            append_carried_log_record(
                serve.page_dir,
                {
                    "kind": "reply",
                    "author": "agent",
                    "agent": "Codex",
                    "parent": root,
                    "revision": 1,
                    "text": f"Answer {n}: the gutters can wait, the roof cannot.",
                },
            )["id"]
        )
        told(page)
    news = thread.locator(
        ":scope > .lf-thread-content > .lf-thread-controls"
    ).get_by_role("button", name="2 new replies")
    expect(news).to_be_visible()
    expect(thread.locator(".lf-msg")).to_have_count(1)
    assert _box_height(thread) == pytest.approx(height, abs=0.5)

    if end == "opened":
        news.click()
    elif end == "walked":
        page.keyboard.press("t")
    elif end == "onto":
        page.keyboard.press("t")
        # The walk lands on the thread in the margin's card, which is the same thread.
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        expect(card).to_be_focused()
        rendered(page)
        expect(news).to_be_visible()
        expect(thread.locator(".lf-msg")).to_have_count(1)
        return
    elif end == "replied":
        write(
            thread.locator(":scope > .lf-thread-reply leaf-text"),
            "Then the roof first.",
        )
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    shown = thread.locator(".lf-msg")
    expect(shown).to_have_count(4 if end == "replied" else 3)
    expect(news).to_have_count(0)
    events = shown.evaluate_all("turns => turns.map(turn => turn.dataset.event)")
    assert events[:3] == [root, *replies]
    if end == "replied":
        expect(shown.last).to_contain_text("Then the roof first.")


def _seat_comment(page_dir, author, text):
    event = {
        "kind": "comment",
        "author": author,
        "revision": 1,
        "text": text,
        "anchor": {"section": "jobs"},
    }
    if author == "agent":
        event["agent"] = "Codex"
    return append_carried_log_record(page_dir, event)["id"]


def _agent_turn(page_dir, root, text):
    return append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "revision": 1,
            "text": text,
        },
    )["id"]


def _to_upper_third(locator):
    """Scroll the page, without input, so the element's top stands a third of the way
    down the window and the page after it is on screen."""
    locator.evaluate(
        """node => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - innerHeight / 3,
          behavior: 'instant'})"""
    )


# The keyboard's native summary activation, and a script setting `open` with no
# summary press at all; Space and a pointer press reach the same native toggle.
@pytest.mark.parametrize("opening", ["Enter", "programmatic"])
def test_a_reopening_in_a_folded_diff_thread_waits_in_its_summary(
    browser, serve, opening
):
    """A resolved diff thread stands folded in its outlet's Resolved disclosure. An
    agent's reply that reopened it unfolded it under the reader, and every diff line
    after it moved down by the whole thread. It stays folded, the disclosure's summary
    says what is waiting, and the keyboard, which the resolve left on that summary,
    opens it to the thread, open in the disclosure's place, with the new turn."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    resolved = page.locator("lf-diff .lf-resolved-threads")
    summary = resolved.locator(":scope > summary")
    # The send leaves the user on the thread, and Resolve is its first stop.
    page.keyboard.press("Tab")
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(summary).to_be_focused()
    expect(summary).to_have_text("Resolved · 1")
    expect(thread).to_be_hidden()
    _to_upper_third(resolved)
    height = _box_height(resolved)
    # Resolving answered the comment, so the agent's turn is one nothing asked for.
    reply = thread_model.post_reply(serve.page_dir, {"to": root}, "The route stays.")
    told(page)
    expect(summary).to_have_text("Resolved · 1 · Reopened · 1 new reply")
    expect(resolved).not_to_have_attribute("open", "")
    assert _box_height(resolved) == pytest.approx(height, abs=0.5)

    # A native open-attribute checkpoint runs before paint. The first opened body
    # must already draw the released news, the thread reopened in the disclosure's
    # place, rather than the older resolved layout inside it.
    resolved.evaluate("""node => {
      window.openedResolved = null;
      new MutationObserver(() => {
        if (!node.open || window.openedResolved) return;
        window.openedResolved = {
          shown: node.isConnected,
          threads: node.querySelectorAll('.lf-page-thread').length,
        };
      }).observe(node, {attributeFilter:['open']});
    }""")
    if opening == "programmatic":
        resolved.evaluate("""node => {
          const open = document.createElement('button');
          open.textContent = 'Open disclosure';
          open.style.cssText = 'position:fixed;left:0;top:80px;z-index:9999';
          open.onclick = () => {node.open = true};
          document.body.append(open);
        }""")
        page.get_by_role("button", name="Open disclosure", exact=True).click()
    else:
        page.keyboard.press(opening)
    assert page.evaluate("openedResolved") == {"shown": False, "threads": 0}
    expect(resolved).to_have_count(0)
    if opening == "Enter":
        expect(thread).to_be_focused()
    expect(thread.locator(".lf-msg")).to_have_count(2)
    expect(thread.locator(f'.lf-msg[data-event="{reply["id"]}"]')).to_be_visible()
    expect(thread.locator(":scope > .lf-thread-reply leaf-text")).to_be_visible()


ROUTE_LINE = '["app/routes.py","new",201]'


@pytest.mark.parametrize(
    "end",
    [
        "keyboard",
        "settled",
        "replied",
        "started",
        "left",
        "standing",
        "selecting",
        "returned",
    ],
)
def test_a_thread_the_agent_starts_on_a_bare_diff_line_waits_at_its_margin_marker(
    browser, serve, end
):
    """A thread the agent starts on a diff line with no thread opened a new outlet under
    the line, and every line and paragraph after it moved down under the reader. No row
    the diff draws can say it waits, so the diff does not draw it: it stands in the
    margin, as any thread the diff does not place does, and its marker is the notice.
    Clicking or pressing Enter on the marker shows the thread under its line
    and lands on it, and the marker stays its notice when the agent settles it. It also
    shows when the user replies in it from the margin's card, when they start a
    thread on the same line, which shows after it, and when
    they scroll the line below the window, unless they stand in its card, writing there
    or holding a selection of its words, which stays with them. Returning from a hidden tab reveals current messages while
    preserving that composing margin card. The news lands well past Chrome's half
    second of recent input, so the shift watch checks that holding the thread moved
    nothing."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    line = page.locator(f"lf-diff [data-lf-datum='{ROUTE_LINE}']")
    _to_upper_third(line)
    after = page.locator("#tail-0")
    top = after.evaluate("node => node.getBoundingClientRect().top")
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )
    held = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "text": "Should the old route name stay as an alias?",
            "anchor": {
                "section": "patch",
                "datum": ROUTE_LINE,
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    told(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    expect(marker).to_be_visible()
    outlet = page.locator("lf-diff .lf-diff-thread-outlet")
    expect(outlet).to_have_count(0)
    assert after.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        top, abs=0.5
    )

    if end == "settled":
        # The agent settling its thread is news too, and the marker stays its notice.
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": held,
                "revision": 1,
            },
        )
        told(page)
        expect(outlet).to_have_count(0)
        expect(marker).to_be_visible()
        marker.click()
    elif end == "returned":
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        box = card.locator(":scope > .lf-thread-reply leaf-text")
        words = "Only if the old name stays usable."
        write(box, words)
        box.evaluate("""box => {
          box.setSelectionRange(8, 8);
          window.__returnDiffEditor = box;
        }""")
        page.evaluate("""() => {
          window.__lfTestVisibility = 'hidden';
          Object.defineProperty(document, 'visibilityState', {
            configurable: true, get: () => window.__lfTestVisibility,
          });
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        answer = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "parent": held,
                "text": "The old name will stay usable.",
            },
        )
        with page.expect_request("**/api/news"):
            page.evaluate("""() => {
              window.__lfTestVisibility = 'visible';
              document.dispatchEvent(new Event('visibilitychange'));
            }""")
        told(page)
        rendered(page)
        expect(outlet).to_have_count(0)
        expect(card.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_be_visible()
        expect(card.locator(".lf-thread-news")).to_have_count(0)
        expect(box).to_be_focused()
        expect(box).to_have_js_property("value", words)
        assert box.evaluate("""field => field === window.__returnDiffEditor
          && field.selectionStart === 8 && field.selectionEnd === 8""")
        return
    elif end == "standing":
        # A user writing in the margin's card keeps it as they scroll the line away.
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        box = card.locator(":scope > .lf-thread-reply leaf-text")
        write(box, "Only if")
        line.evaluate(
            """line => document.scrollingElement.scrollBy({
              top: line.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
        page.evaluate(
            "() => new Promise(done => requestAnimationFrame("
            "() => requestAnimationFrame(done)))"
        )
        expect(box).to_be_focused()
        expect(outlet).to_have_count(0)
        # A second thread on the line, off screen, shows; the one the user writes in
        # stays with them in the card.
        second = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "text": "And should the alias warn?",
                "anchor": {
                    "section": "patch",
                    "datum": ROUTE_LINE,
                    "source": "review-patch",
                    "source_revision": source_revision(serve.page_dir, "review-patch"),
                },
            },
        )["id"]
        told(page)
        expect(outlet.locator(".lf-page-thread")).to_have_count(1)
        expect(outlet.locator(".lf-page-thread")).to_have_attribute(
            "data-thread", second
        )
        expect(box).to_be_focused()
        return
    elif end == "selecting":
        # A selection of the card's words is standing there too, with focus left on a
        # control elsewhere.
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        words = card.locator(".lf-msg-text").first
        words.evaluate(
            """node => { const range = document.createRange();
            range.selectNodeContents(node); const selection = getSelection();
            selection.removeAllRanges(); selection.addRange(range); }"""
        )
        page.locator(".lf-threads-toggle").focus()
        # The user scrolls the line away, a gesture of theirs the page answers.
        page.mouse.move(40, 400)
        page.mouse.wheel(
            0,
            line.evaluate(
                "line => line.getBoundingClientRect().top - innerHeight - 400"
            ),
        )
        page.wait_for_function(
            "line => line.getBoundingClientRect().top > innerHeight",
            arg=line.element_handle(),
        )
        page.evaluate(
            "() => new Promise(done => requestAnimationFrame("
            "() => requestAnimationFrame(done)))"
        )
        expect(outlet).to_have_count(0)
        assert page.evaluate("getSelection().toString()") == (
            "Should the old route name stay as an alias?"
        )
        return
    elif end == "keyboard":
        # The marker as the rail's Tab stop, in keyboard modality. The key before the
        # focus makes the shortcut bar's redraw for the stop an answer to input.
        page.keyboard.press("Shift")
        marker.focus()
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(marker).to_be_focused()
        assert marker.evaluate("marker => marker.matches(':focus-visible')")
        page.keyboard.press("Enter")
    elif end == "replied":
        page.keyboard.press("t")
        card = page.locator(f'.lf-margin-thread .lf-page-thread[data-thread="{held}"]')
        expect(card).to_be_focused()
        write(
            card.locator(":scope > .lf-thread-reply leaf-text"), "Yes, for one release."
        )
        with sending(page, "the user's reply"):
            page.keyboard.press("Enter")
    elif end == "started":
        _select_new_route(page)
        write(page.locator(".lf-composer leaf-text"), "And the handler's name?")
        with sending(page, "the user's thread"):
            page.keyboard.press("ControlOrMeta+Enter")
    else:
        line.evaluate(
            """line => document.scrollingElement.scrollBy({
              top: line.getBoundingClientRect().top - innerHeight - 400,
              behavior: 'instant'})"""
        )
    threads = outlet.locator(".lf-page-thread")
    expect(threads).to_have_count(2 if end == "started" else 1)
    expect(threads.first).to_have_attribute("data-thread", held)
    expect(marker).to_have_count(0)
    if end == "started":
        expect(threads.last).to_contain_text("And the handler's name?")
    if end == "replied":
        expect(threads.first).to_contain_text("Yes, for one release.")
    if end in ("keyboard", "settled"):
        # The marker goes with what it held, and the user lands on the thread it showed,
        # a settled one in its outlet's Resolved disclosure, which opens to show it.
        expect(threads.first).to_be_focused()
    if end == "settled":
        expect(outlet.locator(".lf-resolved-threads")).to_have_attribute("open", "")


@pytest.mark.parametrize(("width", "under_panel"), [(900, True), (1920, False)])
def test_a_page_seat_the_open_panel_stands_over_is_not_read(
    browser, serve, width, under_panel
):
    """Exposure counts a message read once all of it has been shown. The open Threads
    panel stands over the right of the page, so an answer in a page-side seat that
    reaches under it has not been shown whole, however much of it is clear: at 900px
    the diff's thread outlet runs under the panel and earns no receipt until the panel
    closes. At 1920px the panel stands over empty margin and the same answer is read
    with the panel open. The panel's list is narrowed to no card, so the page seat is the
    only copy in view."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page = open_page(browser, url)
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_function("document.querySelector('lf-diff.lf-rendered') !== null")
    _select_new_route(page)
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Can this route stay?")
    with sending(page, "diff comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # A find that matches nothing narrows the panel's list to no card, so the page seat
    # is the one copy of the answer in view.
    find = page.get_by_role("searchbox", name="Find in threads")
    find.focus()
    page.keyboard.type("nothing matches this")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(0)
    find.blur()
    reply = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The route-line answer is ready."
    )
    told(page)
    # The answer landed on screen, so the user opens it where it waits.
    page.locator("lf-diff .lf-page-thread").get_by_role(
        "button", name="1 new reply"
    ).click()
    body = page.locator(
        f'lf-diff .lf-diff-thread-outlet .lf-msg[data-event="{reply["id"]}"]'
        " .lf-msg-body"
    )
    expect(body).to_be_visible()
    body.scroll_into_view_if_needed()
    read = [{"message": reply["id"], "version": reply["id"]}]

    def receipt():
        return any(event["messages"] == read for event in _read_events(serve.page_dir))

    body_right = body.evaluate("element => element.getBoundingClientRect().right")
    panel_left = page.locator(".lf-thread-panel").bounding_box()["x"]
    assert (body_right > panel_left) == under_panel, (
        f"the fixture put the seat's right edge at {body_right} against the panel's "
        f"{panel_left}, so it does not test what it names"
    )
    if under_panel:
        # Long enough for an observation pass to have sent a receipt had it counted.
        page.wait_for_timeout(1500)
        assert not receipt(), "a message partly under the open panel was marked read"
        # With the shortcut bar gone, as under a finger, no other chrome changes size
        # as the panel goes, so only the panel's own announcement sets off the pass that
        # reads the answer, before the page settles. An unrelated pass would read it some
        # 40s on, so waiting for the receipt proves nothing.
        page.locator(".lf-shortcut-bar").evaluate(
            "bar => { bar.style.display = 'none'; }"
        )
        page.get_by_role("button", name="Close threads").click()
        panel_settled(page, open=False)
        rendered(page)
        round_trip(page)
        assert receipt(), "the panel closing off the answer set off no reading"
        return
    deadline = time.monotonic() + SERVED_TIMEOUT_MS / 1000
    while not receipt() and time.monotonic() < deadline:
        page.wait_for_timeout(100)
    assert receipt(), "the answer shown whole was never marked read"


# Every element box in a card, keyed by the element itself, so a later reading
# compares exactly the nodes that survived.
_CARD_BOXES = """card => {
  const boxes = new Map();
  for (const element of [card, ...card.querySelectorAll("*")]) {
    const box = element.getBoundingClientRect();
    boxes.set(element, [box.x, box.y, box.width, box.height].map(Math.round));
  }
  return boxes;
}"""
