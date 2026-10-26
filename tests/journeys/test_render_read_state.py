"""Durable user acknowledgement through the rendered Thread surfaces."""

import pytest
from interact_support import append_carried_log_record, served_thread
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    PANEL_THREAD,
    Traffic,
    _traffic,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    round_trip,
    select,
    sending,
    told,
)

from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.render_checks import (
    PROBE_POLL_MS,
    SERVED_TIMEOUT_MS,
    rendered,
)


def _read_events(page_dir):
    return [
        event for event in events_model.read_events(page_dir) if event["kind"] == "read"
    ]


# The panel's control at rest, which a test focuses to stand the user in the panel.
def _on_me_mark(page):
    return page.locator(".lf-fp-on-user")


# The page's one standing sign of unread messages: a dot on the On me mark, whose name
# counts the threads holding news, and on the folded leaf. The leaf's dot stands
# whatever view is open, where the view's ✕ takes the mark's seat, so it is read here.
def _expect_news(page, news=True):
    dot = page.locator(".lf-fp-news-dot")
    if news:
        expect(dot).to_have_attribute("data-shown", "")
    else:
        expect(dot).not_to_have_attribute("data-shown", "")


def _has_news(page):
    return page.locator(".lf-fp-news-dot").get_attribute("data-shown") is not None


def _first_unread(page):
    """Go to the first unread message the way the keyboard does, `g u`."""
    page.keyboard.press("g")
    page.keyboard.press("u")


# What the panel's chrome says now: the line over the field and the leaf's peek.
def _said(page):
    return " ".join(page.locator(".lf-fp-context, .lf-fp-peek").all_text_contents())


def _thread_row(page, thread):
    return page.locator(f'{panel_view("threads")} .lf-fp-thread[data-key="{thread}"]')


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
        {"parent": root, "responds": for_event},
        f"Update {number}.\n\nCompleted steps: {number}.",
        settlement=thread_model.ProviderFinal("test-final"),
    )["id"]


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
        page.get_by_role("combobox", name="Search commands").fill("g u")
        route = page.locator(
            '.lf-command-reference [role=row][data-lf-command="thread.unread.first"]'
        )
        expect(route.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "u"])
    with sending(page, "authored reply read"):
        if origin == "reference":
            route.get_by_role("button").click()
        else:
            page.keyboard.press("g")
            page.keyboard.press("u")
    card = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    expect(card).to_be_visible()
    expect(card.locator(f'.lf-msg[data-message="{root}"]')).to_be_focused()
    _expect_news(page, False)
    assert _read_events(serve.page_dir)[-1]["messages"] == [
        {"message": root, "version": root}
    ]


def test_read_converges_across_two_tabs(browser, serve):
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "The earlier user thread.")
    root = panel_comment(serve.page_dir, "The shared user answer.", author="agent")
    first = open_page(browser, url)
    second = open_page(browser, url)
    _expect_news(first)
    _expect_news(second)
    _first_unread(first)
    _expect_news(first, False)
    told(second)
    _expect_news(second, False)
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
    _expect_news(child)
    return page, frame, child


def _message_body(child):
    return child.locator(
        f'{PANEL_THREAD} .lf-msg[data-message="{SAMPLE_READER}"] .lf-msg-body'
    )


def _open_first_unread(page, child):
    """The user opens the sample's Threads from its focused mark and goes to its first
    unread message by key. Once the panel's motion has ended, the message stands whole in
    the child's own viewport, so what the containing page shows of the frame is all that
    is left to keep it unread."""
    page.keyboard.press("Enter")
    expect(child.locator(panel_view("threads"))).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("u")
    expect(
        child.locator(f'{PANEL_THREAD}[data-thread="{SAMPLE_READER}"]')
    ).to_be_visible()
    panel_settled(child, view="thread")
    assert _message_body(child).evaluate("""body => {
        const box = body.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= innerHeight
            && box.left >= 0 && box.right <= innerWidth;
    }"""), "the message is not whole in the child's own viewport"


def _scroll_to_message(page, child, scroller):
    """Scroll `scroller`, in the containing page, until the sample's message stands
    in the middle of what it shows. The sample's frame is as tall as its page, and its
    panel stands at its foot, so the message stands near the frame's foot."""
    top = _message_body(child).evaluate("body => body.getBoundingClientRect().top")
    page.evaluate(
        """([scroller, top]) => {
          const box = scroller === document.scrollingElement
            ? {top: 0, height: innerHeight} : scroller.getBoundingClientRect();
          const frame = document.querySelector('#read-practice iframe')
            .getBoundingClientRect().top;
          scroller.scrollBy(0, frame + top - box.top - box.height / 2);
        }""",
        [page.evaluate_handle(scroller), top],
    )


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
    taken the news off the sample's Threads mark and counted a send."""
    _settled(page, child)
    assert _has_news(child)
    assert _traffic(child).sends == 0


def _read_by_the_sample(page, child):
    """The control: the child sends the message read, and its server holds it read."""
    _expect_news(child, False)
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
    _on_me_mark(child).focus()
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
    # Below the first screen it shows nothing: the user focuses its On me mark and
    # scrolls the containing page back to the top first.
    _on_me_mark(child).focus()
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
    _scroll_to_message(page, child, "document.scrollingElement")
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
    _on_me_mark(child).focus()
    _open_first_unread(page, child)
    _scroll_to_message(page, child, "document.querySelector('#owner-modal')")
    _read_by_the_sample(page, child)


def _box_height(locator):
    return locator.evaluate("node => node.getBoundingClientRect().height")


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


ROUTE_LINE = '["app/routes.py","new",201]'


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
