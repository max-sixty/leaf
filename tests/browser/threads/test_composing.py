"""Writing and sending a comment or reply: the draft box as it grows and shrinks, the
Send press, where a sent message lands, and its delivery receipt."""

import io
import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_layout import in_threads_scrollport
from render_harness import (
    LONG_PAGE,
    admit_before_presenting_comment,
    consume_browser_errors,
    example_media,
    hold_pending_thread_presentation,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import (
    IN_LANDING_BAND,
    THIRTY_LINES,
    bounded_seat_page,
    clear_of_the_bar,
    long_diff_thread,
    open_threads_list,
    paste,
    paste_image,
    pressed_send_surface,
    reply_by_keyboard,
    seated_page,
    seed_panel_threads,
    to_window_foot,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_sent_page_comment_closes_and_a_refusal_restores_its_draft(browser, serve):
    """Long comments and attachments leave no empty card after Send. Refusal restores
    the editor and its media while the send still owns the user's intent. The card
    hangs from the banner, so an attachment joins below the words, leaving them put."""
    page = open_page(browser, serve(LONG_PAGE))
    card = page.locator(".lf-page-comment-card")
    box = page_comment(page)
    send = card.locator(".lf-compose-submit")
    draft = "\n".join(f"Page comment line {n}" for n in range(14))
    write(box, draft)
    field = card.locator(".lf-compose-field")
    written = field.bounding_box()
    paste_image(box, (example_media() / "051bee487bfb5d13.png").read_bytes())
    expect(card.locator(".lf-composer-media img")).to_be_visible()
    shelf = card.locator(".lf-composer-media").bounding_box()
    attached = field.bounding_box()
    assert attached["y"] == written["y"], "the attachment moved the words"
    assert shelf["y"] >= attached["y"] + attached["height"], "the shelf is not below"
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") == "comment":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    send.click()
    holding(page, held, 1, "the page comment before refusal")
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    expect(box).to_have_js_property("value", "")
    held.pop().fulfill(
        status=400, json={"ok": False, "final": True, "error": "refused before append"}
    )
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", draft)
    expect(card.locator(".lf-composer-media img")).to_be_visible()
    # The words are back in front of the user, so the refusal names no address for them.
    expect(page.locator(".lf-notice")).to_have_text(
        "Couldn't send — refused before append"
    )
    page.unroute("**/api/event", hold)
    consume_browser_errors(page, http_error_console(400))

    with sending(page, "the retried comment with its image"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(card).to_be_hidden()
    page.keyboard.press("c")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "")
    expect(card.locator(".lf-composer-media img")).to_have_count(0)


def test_a_sent_comment_is_revealed_in_the_panel(browser, serve):
    """A send is the one gesture that produces a thread, so it gets the same answer a
    click on a page mark does: an open panel scrolls the new thread into its scrollport.
    On a list long enough to scroll, the old rebuild appended the comment below the
    fold and put the scroll back where it was — the user's own words landed out of
    sight, silently. Both send routes close the composer and return to its banner
    control; `c` opens it again, with the panel still open."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        "        return t.scrollTop === 0 && t.scrollHeight > t.clientHeight; }"
    ), "this list starts revealed or doesn't scroll, so it proves nothing"

    box = page_comment(page)
    write(box, "Where did my words go?")
    with sending(page, "the first comment"):
        page.locator(".lf-general .lf-compose-submit").click()
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == ("comment", "Where did my words go?")
    in_threads_scrollport(page, f'.lf-thread[data-id="{sent["id"]}"]')
    assert page.evaluate("() => document.querySelector('.lf-threads').scrollTop") > 0, (
        "the new thread was in view without scrolling, so the reveal proved nothing"
    )
    card = page.locator(".lf-page-comment-card")
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    expect(box).to_have_js_property("value", "")

    page.keyboard.press("c")
    expect(box).to_be_focused()
    write(box, "And the second thought lands the same way.")
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")  # the other route, same destination
    second = events_model.read_events(serve.page_dir)[-1]
    in_threads_scrollport(page, f'.lf-thread[data-id="{second["id"]}"]')
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))


def test_comment_on_the_page_starts_a_thread_from_a_card_under_the_banner(
    browser, serve
):
    """The banner's Comment on the page starts a page thread with Threads shut: a card
    hangs flush from the control, and its send closes it and flashes Threads,
    whose count takes the new thread, without opening the panel. `c` on the floor goes
    to the same card, with Threads open or shut."""
    page = open_page(browser, serve(LONG_PAGE))
    control = page.locator(".lf-banner-actions > .lf-page-comment")
    card = page.locator(".lf-page-comment-card")
    box = card.locator("leaf-text")
    toggle = page.locator(".lf-threads-toggle")
    is_open = "node => node.matches(':popover-open')"
    expect(control).to_have_attribute("title", "Comment on the page (c)")

    control.click()
    assert card.evaluate(is_open)
    expect(box).to_be_focused()
    hung = page.evaluate(
        """() => {
          const card = document.querySelector('.lf-page-comment-card')
            .getBoundingClientRect();
          const control = document.querySelector('.lf-banner-actions > .lf-page-comment')
            .getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return [card.top - banner.bottom, card.right - control.right];
        }"""
    )
    assert [round(edge) for edge in hung] == [0, 0], hung

    # The editor and Send share the only frame. The popover ends at that frame's
    # focused paint, rather than adding a padded box around the comment box.
    edges = card.evaluate("""el => {
      const card = el.getBoundingClientRect();
      const field = el.querySelector('.lf-compose-field');
      const box = field.getBoundingClientRect();
      const ring = parseFloat(getComputedStyle(field).outlineWidth);
      return [box.left - ring - card.left, box.right + ring - card.right,
              box.top - ring - card.top, box.bottom + ring - card.bottom];
    }""")
    assert edges == pytest.approx([0, 0, 0, 0]), edges

    # A crowded toolbar can put the anchor left of the space the card needs.
    # Native placement then uses the window, and returns to the anchor when it fits.
    original_viewport = page.viewport_size
    resized(page, 500, original_viewport["height"])
    assert control.evaluate("""el => el.getBoundingClientRect().right <
      document.querySelector('.lf-page-comment-card').getBoundingClientRect().width""")
    bounds = card.bounding_box()
    assert bounds["x"] >= 8 and bounds["x"] + bounds["width"] <= 500 - 8, bounds
    resized(page, original_viewport["width"], original_viewport["height"])
    assert card.evaluate("""el => Math.abs(el.getBoundingClientRect().right -
      document.querySelector('.lf-page-comment').getBoundingClientRect().right) < 1""")

    # Both axes stay usable when a real attachment and draft share a short window.
    draft = "\n".join(f"Page draft line {n}" for n in range(20))
    write(box, draft)
    paste_image(box, (example_media() / "051bee487bfb5d13.png").read_bytes())
    resized(page, 500, 240)
    bounds = card.bounding_box()
    assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 500, bounds
    assert bounds["y"] + bounds["height"] <= 240, bounds
    # The editor gives way first: its words scroll while the card around it does not.
    assert box.evaluate("el => el.scrollHeight > el.clientHeight")
    assert card.evaluate("el => el.scrollHeight <= el.clientHeight")
    resized(page, 500, 180)
    box.press("Tab")
    send_button = card.locator(".lf-compose-submit")
    expect(send_button).to_be_focused()
    assert send_button.evaluate("""el => {
      const b = el.getBoundingClientRect();
      return el.contains(document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2));
    }""")
    expect(box).to_have_js_property("value", draft)
    resized(page, original_viewport["width"], original_viewport["height"])
    card.get_by_role("button", name="Remove attached image 1", exact=True).click()

    count = toggle.get_attribute("data-lf-count")
    write(box, "Does the plan cover the self-hosted runners?")
    with sending(page, "the page comment"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"], sent.get("anchor")) == (
        "comment",
        "Does the plan cover the self-hosted runners?",
        None,
    )
    assert not card.evaluate(is_open)
    assert toggle.evaluate("t => t.getAnimations().length") == 1, (
        "Threads did not flash"
    )
    expect(toggle).to_have_attribute("data-lf-count", str(int(count) + 1))
    assert not page.locator(".lf-thread-panel").evaluate(
        "p => p.classList.contains('open')"
    )
    expect(control).to_be_focused()
    page.keyboard.press("c")
    expect(box).to_be_focused()
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    expect(control).to_be_focused()

    page.locator("main").click(position={"x": 4, "y": 4})
    page.keyboard.press("c")
    assert card.evaluate(is_open)
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "")
    page.keyboard.press("Escape")
    # Words typed straight after `c` land in the box rather than on the page's keys.
    page.keyboard.press("c")
    page.keyboard.type("Kept for later")
    expect(box).to_have_js_property("value", "Kept for later")
    page.keyboard.press("Escape")
    assert not card.evaluate(is_open)
    # A press elsewhere puts it away too, as the browser's light dismissal, keeping
    # the words.
    control.click()
    page.locator("main").click(position={"x": 4, "y": 4})
    assert not card.evaluate(is_open)
    expect(box).to_have_js_property("value", "Kept for later")
    # A second press on the control puts the card away, and it stays away: the press
    # is on the card's own opener, so it is not also a press outside the card that
    # closes it before the control's press opens it again.
    control.click()
    expect(box).to_be_focused()
    control.click()
    one_frame(page)
    assert not card.evaluate(is_open)
    expect(control).to_have_attribute("aria-expanded", "false")
    expect(control).to_be_focused()

    # A refused send restores the editor on the words it handed back.
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    # Pressed straight after the press that opens the card, Enter sends from its box.
    control.click()
    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Kept for later")
    assert card.evaluate(is_open)
    page.unroute("**/api/event")
    consume_browser_errors(page, http_error_console(400))
    page.keyboard.press("Escape")

    # With Threads open, the card is still where a page thread starts: it hangs over
    # the panel, holding the same draft.
    toggle.click()
    panel_settled(page)
    expect(page.locator(".lf-thread-panel .lf-general")).to_have_count(0)
    control.click()
    assert card.evaluate(is_open)
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Kept for later")


def test_a_refused_page_comment_respects_newer_reading_input(browser, serve):
    """A late refusal restores words without taking focus after a newer wheel gesture."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-page-comment").click()
    card = page.locator(".lf-page-comment-card")
    box = card.locator("leaf-text")
    write(box, "Keep my place while delivery finishes.")
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") == "comment":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the page comment before refusal")
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    page.mouse.move(300, 550)
    page.mouse.wheel(0, 350)
    page.wait_for_function("scrollY > 0")
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    held.pop().fulfill(
        status=400,
        json={"ok": False, "final": True, "error": "refused before append"},
    )
    expect(box).to_have_js_property("value", "Keep my place while delivery finishes.")
    expect(card).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()
    page.unroute("**/api/event", hold)
    consume_browser_errors(page, http_error_console(400))
    page.keyboard.press("c")
    expect(box).to_be_focused()


def test_comment_on_the_page_stands_in_more_on_a_phone(browser, serve):
    """A phone's banner keeps one row, so Comment on the page is a row of More in its
    words; its press takes More down and opens the card across the window."""
    context = browser.new_context(
        is_mobile=True, has_touch=True, viewport={"width": 390, "height": 844}
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    expect(page.locator(".lf-banner-actions > .lf-page-comment")).to_have_count(0)
    page.get_by_role("button", name="More page controls", exact=True).click()
    page.locator(".lf-banner-menu .lf-page-comment").click()
    card = page.locator(".lf-page-comment-card")
    assert card.evaluate("node => node.matches(':popover-open')")
    assert not page.locator(".lf-banner-menu").evaluate(
        "node => node.matches(':popover-open')"
    )

    write(card.locator("leaf-text"), "A page comment from the phone.")
    with sending(page, "the phone page comment"):
        card.locator(".lf-compose-submit").tap()
    expect(card).to_be_hidden()
    expect(
        page.get_by_role("button", name="More page controls", exact=True)
    ).to_be_focused()
    page.keyboard.press("c")
    expect(card.locator("leaf-text")).to_be_focused()
    box = card.bounding_box()
    assert round(box["x"]) == 8 and round(box["width"]) == 390 - 16, box

    # `c` with More open takes More down too, rather than opening the card inside it.
    page.keyboard.press("Escape")
    page.get_by_role("button", name="More page controls", exact=True).click()
    page.keyboard.press("c")
    assert card.evaluate("node => node.matches(':popover-open')")
    assert not page.locator(".lf-banner-menu").evaluate(
        "node => node.matches(':popover-open')"
    )


def test_a_new_sent_message_does_not_hide_work_on_an_earlier_message(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Check the capacity.", {"section": "how-cap"})
    active = CliRunner().invoke(
        cli_model.cli,
        ["task", "start", str(serve.page_dir), root, "checking capacity"],
    )
    assert active.exit_code == 0, active.output
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    status = page.locator(f'.lf-thread[data-id="{root}"] .lf-thread-status')
    expect(status).to_have_text("Working")
    later = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": root,
            "text": "Also consider slower devices.",
        },
    )
    told(page)
    workflow = page.locator(f'.lf-msg[data-mid="{later["id"]}"] .lf-msg-sending')
    expect(workflow).to_have_text("Sent")
    assert workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    ), "the message status did not follow its relative timestamp"
    expect(status).to_have_text("Working")


# Paragraphs that give a page length before the thread it is about.
LEAD = "".join(
    f"<p>Paragraph {n}, there to give the page length.</p>" for n in range(30)
)


def long_seated_thread(serve):
    """Serve a widget seating a thread in the page's flow, with the page's length around
    it, and a user's thread on the seat; return the page's URL and the thread's id."""
    url = serve(
        leaf_page(
            "a seated thread",
            f'<h1 id="title">Bracket order</h1>{LEAD}'
            '<lf-test-plan id="cd-command" label="Bracket extras">'
            '<lf-test-task id="cd-q" status="active" talk>'
            "<strong>Which extras go in?</strong>"
            "<p>Choose between a seed tray and a second pole.</p>"
            f"</lf-test-task></lf-test-plan>{LEAD}",
        )
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )["id"]
    return url, root


# Where a reply row's foot stands, where Send and the caret are, on screen and below
# the top of the thread it grows in, and whether the thread is taller than the window.
ROW_FOOT = """box => {
  const row = box.closest('.lf-thread-reply');
  const thread = row.parentElement;
  const foot = row.getBoundingClientRect().bottom;
  return {foot, within: foot - thread.getBoundingClientRect().top,
    tall: thread.getBoundingClientRect().height > innerHeight};
}"""


def send_reply(page, thread, box, words):
    """Type `words` into the thread's reply box, its lines on Shift+Enter, and send
    them; return where the row's foot stood before the send and after it drew."""
    box.click()
    for at, line in enumerate(words.split("\n")):
        if at:
            page.keyboard.press("Shift+Enter")
        page.keyboard.type(line)
    turns = thread.locator(".lf-msg").count()
    before = box.evaluate(ROW_FOOT)
    page.keyboard.press("Enter")
    expect(thread.locator(".lf-msg")).to_have_count(turns + 1)
    rendered(page)
    return before, box.evaluate(ROW_FOOT)


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
@pytest.mark.parametrize(("seat", "lines"), [("widget", 1), ("diff", 1), ("diff", 4)])
def test_sends_from_a_page_threads_box_hold_its_foot_at_the_bands(
    engine, seat, lines, request, serve
):
    """Each send from a thread's box at the reading band's foot, where typing brings
    it, leaves the box's foot there, where Send and the caret stand, through the send
    that makes the thread taller than the band.

    The send landed the whole thread while it fitted and the reply row once it did
    not, and the thread, focused by the send, took its focus ring's room at its foot.
    So the first send lifted the box by that room and the thread's padding, and the
    send that made the thread too tall dropped it back by the same. Held by its top
    instead, a box emptied of several lines lifted its foot by the lines it lost."""
    browser = request.getfixturevalue(engine)
    url, root = (
        long_seated_thread(serve) if seat == "widget" else long_diff_thread(serve, LEAD)
    )
    page = open_page(browser, url)
    resized(page, 1200, 560)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    box = thread.locator("leaf-text")
    # The box's foot just past the landing band's, where the first keystroke lands it.
    box.evaluate(
        """box => scrollBy({top: box.getBoundingClientRect().bottom - innerHeight
          + parseFloat(getComputedStyle(document.documentElement).scrollPaddingBottom)
          - 12, behavior: 'instant'})"""
    )
    rendered(page)
    sends = []
    while not sends or not sends[-1][1]["tall"]:
        assert len(sends) < 8, sends
        words = "\n".join(f"Reply {len(sends)}, line {n}" for n in range(lines))
        sends.append(send_reply(page, thread, box, words))
    for before, after in sends:
        assert abs(after["foot"] - before["foot"]) < 1, sends


def test_a_panel_send_with_room_below_moves_only_the_box(browser, serve):
    """A send from a Threads panel card with room below its box draws the turn where
    the box stood and moves the box down by it, and the list stays where it is: the
    card's transcript is an append region, whose earlier turns stay put."""
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 2)[0]
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, root)
    box = card.locator("leaf-text")
    list_top = "() => document.querySelector('.lf-threads').scrollTop"
    scrolled = page.evaluate(list_top)
    before, after = send_reply(page, card, box, "Reply with room below")
    scroll_settled(page, ".lf-threads")
    assert page.evaluate(list_top) == scrolled
    grew = after["within"] - before["within"]
    assert grew > 0 and abs(after["foot"] - before["foot"] - grew) < 1, (before, after)


def test_a_growing_panel_reply_keeps_the_previous_turn_visible(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "A question with a reply.")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "The last answer remains useful while composing a response.",
        },
    )
    page = open_page(browser, url)
    resized(page, 800, 520)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(".lf-thread-summary").click()
    reply = card.locator("leaf-text")
    write(reply, "A reply that grows.\n" * 30)
    latest = card.locator(".lf-msg.agent").last
    visible = latest.evaluate(
        """message => {
          const list = document.querySelector('.lf-threads');
          const band = list.getBoundingClientRect();
          const style = getComputedStyle(list);
          return {
            tail: message.getBoundingClientRect().bottom,
            top: band.top + parseFloat(style.scrollPaddingTop),
            editor: list.querySelector('.lf-thread[open] leaf-text').getBoundingClientRect().top,
          };
        }"""
    )
    assert visible["tail"] >= visible["top"] + 20, visible
    assert visible["tail"] < visible["editor"], visible
    assert reply.evaluate("input => input.scrollTop > 0")
    in_threads_scrollport(page, f'.lf-thread[data-id="{root}"] .lf-thread-send')


@pytest.mark.parametrize("edit", ["backspace", "replace"])
def test_a_panel_reply_keeps_its_first_line_when_the_draft_shrinks(
    browser, serve, edit
):
    """A short reply grows and shrinks below its first line, including after paint.

    Message continuity must not turn a draft's former height into space above it.
    Backspace removes the lines the user just added; replacing the draft exercises
    the same layout through a single native input instead of repeated key presses.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "A short thread with room below its reply.")
    page = open_page(browser, url)
    open_threads_list(page, 1400, 900)
    card = reply_by_keyboard(page, root)
    editor = card.locator("leaf-text")
    page.keyboard.type("First line")
    rendered(page)
    first = editor.bounding_box()
    for _ in range(4):
        page.keyboard.press("Shift+Enter")
        rendered(page)
    grown = editor.bounding_box()
    assert grown["height"] > first["height"] + 50, (first, grown)
    assert grown["y"] == pytest.approx(first["y"], abs=0.5), (first, grown)

    if edit == "backspace":
        for _ in range(4):
            page.keyboard.press("Backspace")
            rendered(page)
            now = editor.bounding_box()
            assert now["y"] == pytest.approx(first["y"], abs=0.5), (first, now)
    else:
        write(editor, "First line")
        rendered(page)
    shrunk = editor.bounding_box()
    assert shrunk["height"] == pytest.approx(first["height"], abs=0.5), (first, shrunk)
    assert shrunk["y"] == pytest.approx(first["y"], abs=0.5), (first, shrunk)
    expect(editor).to_have_js_property("value", "First line")
    expect(editor).to_be_focused()


def test_a_page_comment_sent_beside_open_threads_lands_in_view(browser, serve):
    """The list's place hold finishing a render cancelled the smooth landing already
    under way, leaving the new thread below the list's foot."""
    # The short window, where the landing has the furthest to go.
    size = (800, 520)
    url = serve(PANEL_PAGE)
    seed_panel_threads(serve.page_dir, 8 if size[1] < 600 else 20, long_index=0)
    page = open_page(browser, url)
    open_threads_list(page, *size)
    page.locator(".lf-threads").evaluate("list => list.scrollTop = list.scrollHeight")
    scroll_settled(page, ".lf-threads")
    write(page_comment(page), "What the general box says.")
    with sending(page, "the page comment"):
        page.keyboard.press("Enter")
    rendered(page)
    scroll_settled(page, ".lf-threads")
    sent = events_model.read_events(serve.page_dir)[-1]
    card = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    landed = card.locator(":scope > .lf-thread-summary").evaluate(IN_LANDING_BAND)
    assert landed["inside"], f"the new thread was left outside the band: {landed}"
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    expect(page.locator(".lf-page-comment")).to_be_focused()


@pytest.mark.parametrize("touch", [False, True], ids=["desktop", "touch"])
def test_contextual_messages_share_text_spacing_through_send_and_reopen(
    browser, serve, touch
):
    """Every contextual turn uses the same header and paragraph spacing.

    Opening a pre-existing thread misses the comment-to-message handoff. Measure
    the actual first text line, since the retained viewport can pad inside a body
    whose outer gap is already correct.
    """
    context = browser.new_context(has_touch=touch, is_mobile=touch)
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Message spacing",
                '<h1>Review</h1><p id="target">A passage to discuss.</p>',
            )
        ),
        context=context,
    )
    resized(page, 390 if touch else 1440, 900)
    page.locator("#target").click(modifiers=["Alt"])
    box = page.locator(".lf-fab-input")
    box.click()
    text = "First paragraph.\nIts second line.  \nIts third line.\n\nSecond paragraph.\n\n# A heading"
    write(box, text)
    with sending(page, "the opening comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    preview = page.locator(".lf-margin-preview")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    write(reply, text)
    with sending(page, "the follow-up reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(preview.locator(".lf-msg")).to_have_count(2)
    for paragraph in preview.locator(".lf-msg-text > p:first-child").all():
        assert paragraph.inner_text() == text.split("\n\n")[0].replace("  \n", "\n")
    for message in preview.locator(".lf-msg").all():
        body = message.locator(".lf-msg-body")
        for property in ("font-size", "line-height"):
            expect(message.locator("h1")).to_have_css(
                property,
                body.evaluate("(node, key) => getComputedStyle(node)[key]", property),
            )
    rendered(page)
    preview.locator(".lf-thread-transcript").evaluate("node => { node.scrollTop = 0; }")
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    measure_gaps = """messages => messages.map(message => {
      const name = message.querySelector('.lf-msg-head b').getBoundingClientRect();
      const paragraphs = message.querySelectorAll('.lf-msg-text p');
      const range = document.createRange();
      range.selectNodeContents(paragraphs[0]);
      const firstLine = range.getClientRects()[0].top;
      range.selectNodeContents(paragraphs[1]);
      return [firstLine - name.bottom, range.getClientRects()[0].top - firstLine];
    })"""
    gaps = preview.locator(".lf-msg").evaluate_all(measure_gaps)
    assert gaps[0] == pytest.approx(gaps[1], abs=0.1), gaps
    page.locator(".lf-margin-preview-close").click()
    expect(preview).to_be_hidden()
    page.locator(".lf-margin-marker").click()
    expect(preview).to_be_visible()
    reopened = preview.locator(".lf-msg").evaluate_all(measure_gaps)
    for before, after in zip(gaps, reopened, strict=True):
        assert after == pytest.approx(before, abs=0.1), (gaps, reopened)


# The floating card, whose ground the pixel reading checks, the panel, and a thread
# in a widget's shadow root.
@pytest.mark.parametrize("surface", ["card", "panel", "composer-widget"])
def test_sending_flashes_only_the_new_message(browser, serve, surface):
    """Sending cues the words in every surface, including a shadow-root thread.
    Sticky authors share the words' fade. Admission and subsequent repaint do not
    restart the cue or wash the card."""
    page, _box, send, _after, _reply = pressed_send_surface(browser, serve, surface)
    # Capture the first painted cue, before driver latency can consume its duration.
    page.evaluate(
        """surface => {
          window.__sendPaint = null;
          const root = ["card", "composer"].includes(surface)
            ? document.querySelector(".lf-margin-preview")
            : document.querySelector("#patch")?.shadowRoot ?? document;
          const observer = new MutationObserver(() => {
            const message = [...root.querySelectorAll('.lf-msg')].find(node =>
              node.textContent.includes('Sent from the box.')
            );
            if (!message) return;
            observer.disconnect();
            const cue = message.getAnimations().find(animation =>
              animation.effect.getKeyframes().some(frame => frame['--lf-msg-arrival'])
            );
            window.__sendPaint = {cue: Boolean(cue), message};
            if (cue) { cue.pause(); cue.currentTime = 0; }
          });
          observer.observe(root, {subtree: true, childList: true, attributes: true});
        }""",
        surface,
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    send.click()
    holding(page, held, 1, "the highlighted send")
    page.wait_for_function("() => window.__sendPaint !== null")
    assert page.evaluate("() => window.__sendPaint.cue"), surface
    assert page.evaluate(
        """() => {
          const message = window.__sendPaint.message;
          return getComputedStyle(message).backgroundColor !== 'rgba(0, 0, 0, 0)';
        }"""
    )
    if surface in {"card", "composer"}:
        message = page.locator(
            ".lf-margin-preview .lf-msg", has_text="Sent from the box."
        )
        # Compare painted ground, rather than just the inherited computed colour:
        # a second translucent layer can have the same colour and paint darker.
        for time in [0, 600, 1199]:
            message.evaluate(
                "(node, time) => node.getAnimations()[0].currentTime = time", time
            )
            one_frame(page)
            pixels = Image.open(io.BytesIO(message.screenshot())).convert("RGB")
            # The scrollport can clip the message's top edge. Sample inside the
            # sticky header's visible paint, clear of its words and controls.
            head_point = message.evaluate(
                """node => {
                  const box = node.getBoundingClientRect();
                  const head = node.querySelector('.lf-msg-head').getBoundingClientRect();
                  return [Math.round(head.right - box.left) - 2,
                    Math.round(head.top + head.height / 2 - box.top)];
                }"""
            )
            assert pixels.getpixel(tuple(head_point)) == pixels.getpixel(
                (head_point[0], pixels.height - 4)
            )
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert page.evaluate(
        """() => {
          const message = window.__sendPaint.message;
          const thread = message.closest('.lf-thread, .lf-page-thread');
          return !thread.getAnimations({subtree: true}).some(animation =>
            animation.effect.target !== message &&
            animation.effect.getKeyframes().some(frame =>
              frame.background || frame.backgroundColor || frame['--lf-msg-arrival'])
          );
        }"""
    ), "the surrounding card flashed on admission"
    page.evaluate(
        "() => window.__sendPaint.message.getAnimations().forEach(a => a.finish())"
    )
    one_frame(page)
    assert page.evaluate("() => window.__sendPaint.message.getAnimations().length") == 0


@pytest.mark.parametrize(
    ("surface", "how"),
    # Every surface once, the two routes alternating where both reach Send. The
    # anchored composer's Tab from its field opens its response options
    # (`comment.options`), so its Send takes no keyboard press; Enter is that route. `pause` stands one
    # Tab past Send, which the keyboard route proves.
    [
        ("card", "pointer"),
        ("panel", "keyboard"),
        ("general", "pointer"),
        ("pause", "keyboard"),
        ("handoff", "pointer"),
        ("composer", "pointer"),
        ("composer-widget", "pointer"),
        ("composer-panel", "pointer"),
    ],
)
def test_a_pressed_send_leaves_the_user_where_enter_does(browser, serve, surface, how):
    """Pressing a box's submit control is its send key pressed from the box, so it leaves
    the user where Enter would, never on the button, where the next letters fall on
    nothing. A box that stays to take more keeps them in it, typing on. A reply, or the
    comment that starts a thread, finishes what they were writing: they stand on the
    thread's card or title on every surface, and `c` writes the follow-up."""
    page, box, send, after, reply = pressed_send_surface(browser, serve, surface)
    if surface.startswith("composer"):
        hold_pending_thread_presentation(page)
    if how == "keyboard":
        # Tab reaches the control from the box; `Send & pause` stands one past `Send`.
        for _ in range(2 if surface == "pause" else 1):
            page.keyboard.press("Tab")
        expect(send).to_be_focused()
        with sending(page, "the keyboard-pressed send"):
            page.keyboard.press("Space")
    else:
        send.scroll_into_view_if_needed()
        at = send.bounding_box()
        page.mouse.move(at["x"] + at["width"] / 2, at["y"] + at["height"] / 2)
        with sending(page, "the pointer-pressed send"):
            page.mouse.down()
            # The press never takes the focus, so the box never hears it leave.
            expect(box).to_be_focused()
            page.mouse.up()
    if surface.startswith("composer"):
        sent = admit_before_presenting_comment(
            page, serve.page_dir, "Sent from the box."
        )
        thread = page.locator(
            f'.lf-thread[data-id="{sent["id"]}"]'
            if surface == "composer-panel"
            else f'.lf-page-thread[data-thread="{sent["id"]}"]'
        )
        expect(thread).to_be_visible()
        if surface == "composer-widget":
            # Exact message navigation belongs to Threads, not the local reply box.
            assert page.evaluate(
                """async id => {
                  const {surfaceFocusTarget} = await window.__lfCheckApi();
                  return surfaceFocusTarget(id, {part: 'message'}) === null;
                }""",
                sent["id"],
            )
    rendered(page)
    expect(after).to_be_focused()
    expect(after).to_be_visible()
    if after != reply:
        page.keyboard.press("c")
        expect(reply).to_be_focused()
    page.keyboard.type("ok")
    expect(reply).to_have_js_property("value", "ok")
    expect(page.locator("html")).not_to_have_attribute("data-lf-annotations", "hidden")
    sent = events_model.read_events(serve.page_dir)
    assert any(event.get("text") == "Sent from the box." for event in sent), sent


def test_a_pointer_send_finishes_the_words_an_input_method_holds(browser, serve):
    """A press on Send while an input method holds unfinished words takes the focus, as
    leaving the box is what finishes them: the send carries the finished words, and the
    box it empties stays empty. Held in the box, the words went out unfinished and the
    input method's commit afterwards wrote them back into the emptied box."""
    page, box, send, after, _ = pressed_send_surface(browser, serve, "general")
    ended = box.evaluate_handle(
        """box => {
          const ended = {count: 0};
          box.addEventListener('compositionend', () => (ended.count += 1));
          return ended;
        }"""
    )
    ime = page.context.new_cdp_session(page)
    ime.send(
        "Input.imeSetComposition",
        {"text": "にほ", "selectionStart": 2, "selectionEnd": 2},
    )
    expect(box).to_have_js_property("value", "Sent from the box.にほ")
    at = send.bounding_box()
    page.mouse.move(at["x"] + at["width"] / 2, at["y"] + at["height"] / 2)
    with sending(page, "the send pressed mid-composition"):
        page.mouse.down()
        page.mouse.up()
    rendered(page)
    assert ended.evaluate("ended => ended.count") == 1
    expect(after).to_be_focused()
    expect(box).to_have_js_property("value", "")
    sent = events_model.read_events(serve.page_dir)
    assert any(event.get("text") == "Sent from the box.にほ" for event in sent), sent


def test_a_seat_send_puts_the_user_on_the_thread_it_started(browser, serve):
    """A seat that gives its box up to the thread its first message starts took the
    focus with it, dropping the user on the page. They stand on the thread instead,
    where any send leaves them."""
    url, host = seated_page(serve, "verdict")
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First thought.")
    with sending(page, "the first message"):
        page.keyboard.press("Enter")
    thread = page.locator(f"{host} > .lf-thread-seat > .lf-page-thread")
    expect(thread).to_have_count(1)
    expect(thread).to_be_focused()


@pytest.mark.parametrize("kind", ["task", "verdict"])
def test_a_seat_send_at_the_window_foot_shows_the_thread_it_started(
    browser, serve, kind
):
    url, host = seated_page(serve, kind)
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First thought.")
    to_window_foot(page, box, 60)
    with sending(page, "the first message"):
        page.keyboard.press("Enter")
    rendered(page)
    scroll_settled(page)
    sent = page.locator(f"{host} .lf-page-thread .lf-msg").last
    expect(sent).to_contain_text("First thought.")
    assert clear_of_the_bar(page, sent), "the sent message was left below the fold"
    # Where the send left the user: the box a task seat keeps, or the thread a verdict
    # seat gave its box up to.
    focused = page.locator(f"{host} :is(leaf-text, .lf-page-thread):focus")
    expect(focused).to_have_count(1)
    if kind == "task":
        assert clear_of_the_bar(page, focused), "the box went below the fold"


def shown_in(page, node, scroller):
    """Whether `node` shows whole inside `scroller`'s box and inside the window above
    the shortcut bar."""
    return page.evaluate(
        """([node, box, bar]) => {
          const at = node.getBoundingClientRect();
          const holder = box.getBoundingClientRect();
          const foot = bar ? bar.getBoundingClientRect().top : innerHeight;
          return at.height > 0 && at.top >= holder.top - 0.5
            && at.bottom <= holder.bottom + 0.5 && at.top >= 0 && at.bottom <= foot + 0.5;
        }""",
        [
            node.element_handle(),
            scroller.element_handle(),
            page.locator(".lf-shortcut-bar").element_handle(),
        ],
    )


@pytest.mark.parametrize("bound", ["end", "start"])
def test_a_seat_send_in_a_bounded_block_moves_the_block_and_not_the_page(
    browser, serve, bound
):
    """A block that bounds its own height scrolls a seat inside it, so each send
    landed its thread by scrolling the page too, and the block went out of the window
    after two sends. The block is the reading region the seat stands in."""
    page = open_page(browser, serve(bounded_seat_page(6, bound)))
    resized(page, 1280, 700)
    hub = page.locator("#hub")
    assert hub.evaluate("hub => hub.scrollHeight > hub.clientHeight + 100")
    # The block stands in the middle of the window, its seat scrolled into its view.
    page.evaluate(
        """hub => { const at = hub.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        hub.element_handle(),
    )
    hub.evaluate("hub => hub.scrollTop = hub.scrollHeight")
    scroll_settled(page)
    box = page.locator("#jobs > .lf-thread-seat > .lf-say leaf-text")
    for n, words in enumerate(["First thought.", "Second thought."]):
        write(box, words)
        before = page.evaluate("() => document.scrollingElement.scrollTop")
        with sending(page, f"message {n + 1}"):
            page.keyboard.press("Enter")
        sent = page.locator("#jobs .lf-page-thread .lf-msg").last
        expect(sent).to_contain_text(words)
        rendered(page)
        scroll_settled(page)
        scroll_settled(page, "#hub")
        after = page.evaluate("() => document.scrollingElement.scrollTop")
        assert after == pytest.approx(before, abs=1), (
            f"send {n + 1} moved the page {after - before}px"
        )
        assert shown_in(page, sent, hub), f"send {n + 1} left its turn out of view"
        focused = page.locator("#jobs leaf-text:focus")
        expect(focused).to_have_count(1)
        assert shown_in(page, focused, hub), f"send {n + 1} left the box out of view"


def test_a_seat_box_grown_by_a_paste_keeps_its_send_above_the_bar(browser, serve):
    """The growth reveal lived in the reply wiring alone, so a seat's own box grew
    under the shortcut bar, CodeMirror's caret scrolling knowing nothing of it."""
    url, host = seated_page(serve, "verdict")
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    send = page.locator(f"{host} > .lf-thread-seat > .lf-say .lf-compose-submit")
    assert clear_of_the_bar(page, send)


def annotation_mode_source(mode):
    return leaf_page(
        "Mode switch",
        '<h1>Mode switch</h1><p id="subject">A passage with stable words.</p>',
    ).replace("<body>", f'<body data-annotations="{mode}">')


@pytest.mark.parametrize(
    "initial,next_mode", [("overlay", "page"), ("page", "overlay")]
)
def test_actual_mode_switch_carries_native_composer(browser, serve, initial, next_mode):
    root = "0123456789abcdef0123456789abcdef"
    event = {
        "id": root,
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "A current thread",
        "anchor": {"section": "subject"},
    }
    page = open_page(
        browser, live_url(serve(annotation_mode_source(initial), events=[event]))
    )
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(":scope > summary").click()
    editor = thread.locator(".lf-thread-reply leaf-text")
    editor.click()
    expect(editor).to_be_focused()
    editor.evaluate("el=>el.setSelectionRange(0,0,'none')")
    birth = page.evaluate("performance.timeOrigin")
    stamp_page(
        serve.page_dir,
        annotation_mode_source(next_mode),
        "Change actual annotation mode",
    )
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin") != birth
    expect(editor).to_be_focused()
    assert editor.evaluate(
        "el=>[el.value,el.selectionStart,el.selectionEnd,el.selectionDirection]"
    ) == ["", 0, 0, "none"]
    assert page.locator(".lf-margin-projection").count() == (next_mode == "overlay")


@pytest.mark.parametrize("surface", ["composer-widget", "composer-panel"])
def test_pending_messages_stay_readable_through_admission(browser, serve, surface):
    """Delivery receipts distinguish sends without fading their readable content.

    Hold both user messages before admission, then admit each separately. Headers
    and bodies stay fully opaque in ordinary and shadow-root threads while each
    message's busy state follows its own admission.
    """
    page, _box, send, _after, reply = pressed_send_surface(browser, serve, surface)
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") in {"comment", "reply"}:
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    send.click()
    holding(page, held, 1, "the unconfirmed root comment")
    expect(reply).to_be_visible()
    write(reply, "A second unconfirmed message.")
    page.keyboard.press("Enter")
    rendered(page)
    region = (
        page.locator("lf-diff .lf-page-thread")
        if surface == "composer-widget"
        else page.locator(".lf-margin-preview .lf-page-thread")
        if surface == "composer"
        else page.locator(".lf-threads > .lf-thread", has_text="Sent from the box.")
    )
    expect(region.locator(".lf-msg")).to_have_count(2)
    assert region.locator(".lf-msg-head").evaluate_all(
        "heads => heads.every(head => head.parentElement.matches('.lf-msg'))"
    ), "a message header was moved outside its message"
    assert region.evaluate(
        """root => {
          const head = root.querySelector('.lf-msg-head').getBoundingClientRect();
          const action = root.querySelector('.lf-resolve').getBoundingClientRect();
          const center = action.top + action.height / 2;
          return head.top <= center && center <= head.bottom && head.right <= action.left;
        }"""
    ), "keeping the header inside its message gave thread actions a separate row"

    def reading():
        return region.evaluate(
            """root => {
              const opacity = node => {
                let value = 1;
                for (; node && node !== root; node = node.parentElement)
                  value *= Number(getComputedStyle(node).opacity);
                return value;
              };
              return {
                headers: [...root.querySelectorAll('.lf-msg-head')].map(opacity),
                bodies: [...root.querySelectorAll('.lf-msg-body')].map(opacity),
                pending: [...root.querySelectorAll('.lf-msg')].map(node =>
                  node.getAttribute('aria-busy') === 'true'),
                pendingCursors: [...root.querySelectorAll('.lf-msg[aria-busy="true"] .lf-msg-body')]
                  .map(node => getComputedStyle(node).cursor),
              };
            }"""
        )

    assert reading() == {
        "headers": [1, 1],
        "bodies": [1, 1],
        "pending": [True, True],
        "pendingCursors": ["progress", "progress"],
    }
    held.pop().continue_()
    holding(page, held, 1, "the reply following its admitted root")
    rendered(page)
    assert reading() == {
        "headers": [1, 1],
        "bodies": [1, 1],
        "pending": [False, True],
        "pendingCursors": ["progress"],
    }
    held.pop().continue_()
    page.unroute("**/api/event", hold)
    round_trip(page)
    assert reading() == {
        "headers": [1, 1],
        "bodies": [1, 1],
        "pending": [False, False],
        "pendingCursors": [],
    }
