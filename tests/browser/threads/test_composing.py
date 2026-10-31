"""Writing and sending a comment or reply: the draft box as it grows and shrinks, the
Send press, where a sent message lands, and its delivery receipt."""

import io
import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    page_comment,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)

from browser.threads import (
    THIRTY_LINES,
    bounded_seat_page,
    clear_of_the_panel,
    long_diff_thread,
    paste,
    pressed_send_surface,
    seated_page,
    thread_row,
    to_window_foot,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_refused_page_comment_respects_newer_reading_input(browser, serve):
    """A late refusal restores words without taking focus after a newer wheel gesture,
    or moving the page the wheel moved."""
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)
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
    page.mouse.move(300, 300)
    page.mouse.wheel(0, 350)
    page.wait_for_function("scrollY > 0")
    scroll_settled(page)
    place = page.evaluate("scrollY")
    held.pop().fulfill(
        status=400,
        json={"ok": False, "final": True, "error": "refused before append"},
    )
    expect(box).to_have_js_property("value", "Keep my place while delivery finishes.")
    expect(box).not_to_be_focused()
    rendered(page)
    assert page.evaluate("scrollY") == place
    page.unroute("**/api/event", hold)
    consume_browser_errors(page, http_error_console(400))


@pytest.mark.parametrize("surface", ["margin", "page"])
def test_a_refused_reply_folds_away_and_its_words_return_whole(browser, serve, surface):
    """A reply the log refuses leaves the thread at once and folds away where it
    stood, and the card gives its room back as it folds. The words come back to the
    reply box whole, grown as typing grows it, rather than into the room held from
    before Send (browser/AGENTS.md, "Stability is owed to the common path")."""
    if surface == "margin":
        url = serve(PANEL_PAGE)
        panel_comment(serve.page_dir, "Check the capacity.", {"section": "how-cap"})
        page = open_page(browser, url)
        page.locator('[data-lf-margin-for="how-cap"] .lf-margin-marker').click()
        card = page.locator(".lf-margin-preview .lf-page-thread")
    else:
        url, host = seated_page(serve, "verdict")
        page = open_page(browser, url)
        seat = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
        seat.scroll_into_view_if_needed()
        write(seat, "Check the capacity.")
        page.keyboard.press("Enter")
        round_trip(page)
        card = page.locator(f"{host} > .lf-thread-seat > .lf-page-thread")
    page.emulate_media(reduced_motion="no-preference")
    box = card.locator(".lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    expect(box).to_be_visible()
    # Freeze the fold as it starts, so the reading covers its interval rather than
    # racing its duration.
    card.evaluate("""node => new MutationObserver(() => {
        const folding = node.querySelector('.lf-msg[inert]');
        const animation = folding?.getAnimations()[0];
        if (!animation || animation === window.retirement) return;
        window.retirement = animation;
        animation.pause();
        animation.currentTime = 0;
    }).observe(node, {subtree: true, attributeFilter: ['inert']})""")
    held = []

    def hold(route):
        if route.request.post_data_json.get("kind") == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    words = "Hold the release for the capacity numbers."
    write(box, words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the reply")
    sent = card.locator('.lf-msg[data-event^="pending:"]')
    expect(sent).to_be_visible()
    rendered(page)
    space = card.locator(".lf-reply-space")

    def whole():
        return box.evaluate(
            "node => node.getBoundingClientRect().height + 0.5 >= node.naturalBlockSize"
        )

    # A margin card follows the send with its own motion (box-motion.js), which ends
    # before the card is read where it stands.
    page.wait_for_function(
        "() => !document.querySelector('.lf-margin-preview')?.getAnimations({subtree: true})"
        ".some(a => Number.isFinite(a.effect?.getComputedTiming().endTime))"
    )
    route = held.pop()
    route.fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": route.request.post_data_json["attempt"],
            "error": "refused before append",
            "final": True,
        },
    )
    expect(box).to_have_js_property("value", words)
    folding = card.locator(".lf-msg[inert]")
    expect(folding).to_have_count(1)
    expect(sent).to_have_count(0)
    assert folding.evaluate(
        "node => node.matches(':not([data-event], [data-message])')"
    )
    page.evaluate(
        "() => window.retirement.currentTime ="
        " window.retirement.effect.getTiming().duration / 2"
    )
    one_frame(page)
    assert 0 < folding.evaluate("node => node.getBoundingClientRect().height")
    assert space.evaluate("node => node.getBoundingClientRect().height") == 0
    assert whole()
    page.evaluate("() => window.retirement.play()")
    expect(folding).to_have_count(0)
    rendered(page)
    assert space.evaluate("node => node.getBoundingClientRect().height") == 0
    assert whole()
    page.unroute("**/api/event", hold)
    consume_browser_errors(page, http_error_console(400))


def test_a_new_sent_message_does_not_hide_work_on_an_earlier_message(browser, serve):
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Check the capacity.", {"section": "how-cap"})
    active = CliRunner().invoke(
        cli_model.cli,
        ["task", "start", str(serve.page_dir), root, "--text", "checking capacity"],
    )
    assert active.exit_code == 0, active.output
    page = open_page(browser, url)
    expect(thread_row(page, root).locator(".lf-row-end")).to_have_text("On it")
    page.locator('[data-lf-margin-for="how-cap"] .lf-margin-marker').click()
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
    workflow = page.locator(
        f'.lf-margin-preview .lf-msg[data-event="{later["id"]}"] .lf-msg-sending'
    )
    expect(workflow).to_have_text(re.compile(r"^Queued for "))
    assert workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    ), "the message status did not follow its relative timestamp"
    # The time and the status stand on the writer's name's baseline, though the name
    # is set larger (surfaces.css, the name's strut).
    baselines = workflow.evaluate(
        """node => [...node.closest('.lf-msg-head').querySelectorAll(
          ':scope > b, :scope > .lf-msg-meta > time, [data-voice]')].map(words => {
          const mark = words.appendChild(document.createElement('span'));
          mark.style.cssText = 'display: inline-block; block-size: 0';
          const y = mark.getBoundingClientRect().top;
          mark.remove();
          return y;
        })"""
    )
    assert len(baselines) == 3 and max(baselines) - min(baselines) < 0.1, baselines
    expect(thread_row(page, root).locator(".lf-row-end")).to_have_text("On it")


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
    # A send keeps the caret in the box, so only the first reply clicks into it: a
    # click scrolls its target, ring room and all, into view, which no typing does.
    if not box.evaluate("box => box.matches(':focus')"):
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


@pytest.mark.watch_shifts
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


@pytest.mark.watch_shifts
def test_escape_from_a_box_leaves_it_where_it_stood(browser, serve):
    """Escape from a page thread's box, onto a thread that fits the window but whose
    head the user has scrolled above it, lands on the thread without scrolling: the box
    they left stays under their aim. Landing the thread nearest brought its head back
    into view and carried the box down with it."""
    url, root = long_seated_thread(serve)
    page = open_page(browser, url)
    resized(page, 1200, 560)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator("leaf-text")
    expect(box).to_be_visible()
    box.click()
    page.keyboard.type("draft")
    thread.evaluate(
        "thread => scrollBy({top: thread.getBoundingClientRect().top + 30,"
        " behavior: 'instant'})"
    )
    scroll_settled(page)
    assert thread.evaluate("thread => thread.getBoundingClientRect().top") < 0
    before = box.evaluate("box => box.getBoundingClientRect().top")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    rendered(page)
    assert box.evaluate("box => box.getBoundingClientRect().top") == before


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
        ("diff-reply", "keyboard"),
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
    nothing. A box that stays to take more keeps them in it, typing on, and so does a
    reply's, on a card, in a widget's thread and in the panel alike, where a card's and
    a widget's once left them on the thread. The comment that starts a thread finishes
    what they were writing: they stand on the thread's card or title, and `c` writes
    the follow-up."""
    page, box, send, after, reply = pressed_send_surface(browser, serve, surface)
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
    sent = events_model.read_events(serve.page_dir)
    assert any(event.get("text") == "Sent from the box.にほ" for event in sent), sent
    # The page comment's box the send emptied stays empty.
    expect(page_comment(page)).to_have_js_property("value", "")


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
    assert clear_of_the_panel(page, sent), "the sent message was left below the fold"
    # Where the send left the user: the box a task seat keeps, or the thread a verdict
    # seat gave its box up to.
    focused = page.locator(f"{host} :is(leaf-text, .lf-page-thread):focus")
    expect(focused).to_have_count(1)
    if kind == "task":
        assert clear_of_the_panel(page, focused), "the box went below the fold"


def shown_in(page, node, scroller):
    """Whether `node` shows whole inside `scroller`'s box and inside the window above
    the floating panel."""
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
            page.locator(".lf-fp-card").element_handle(),
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


def test_a_seat_box_grown_by_a_paste_keeps_its_send_above_the_panel(browser, serve):
    """The growth reveal lived in the reply wiring alone, so a seat's own box grew
    under the window's foot chrome, CodeMirror's caret scrolling knowing nothing of it."""
    url, host = seated_page(serve, "verdict")
    page = open_page(browser, url)
    box = page.locator(f"{host} > .lf-thread-seat > .lf-say leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    send = page.locator(f"{host} > .lf-thread-seat > .lf-say .lf-compose-submit")
    assert clear_of_the_panel(page, send)


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
