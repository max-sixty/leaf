"""How a thread folds earlier messages under an agent summary or behind an answer's
progress, and how a direct reply link reveals what a fold hides."""

import io
import re

import pytest
from interact_support import append_carried_log_record, append_command
from leaf import thread as thread_model
from leaf.render_checks import one_frame, rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, SEATED_ASK_PAGE, panel_comment
from render_harness import (
    PANEL_THREAD,
    open_page,
    panel_settled,
    resized,
    sending,
    told,
)

from browser.threads import (
    append_agent_reply,
    append_user_reply,
    summarize_thread,
)

pytestmark = pytest.mark.shifts_unsurveyed


def show_held_news(card):
    """Show what the card holds behind its notice, by a press that leaves focus where
    the user stands."""
    notice = card.locator(".lf-thread-news")
    expect(notice).to_be_visible()
    notice.evaluate("node => node.click()")
    expect(notice).to_have_count(0)


def open_margin_card(page, root):
    """Open the margin card of the passage thread `root`, by its marker, and return it."""
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    expect(card).to_be_visible()
    return card


def assert_arrival_returns_to_own_fill(page, destination):
    """The last painted cue frame equals the same box without its animation.

    Hold the endpoint so a wrong fill cannot hide behind the effect's removal.
    Reading pixels also covers transparent message ground over its thread surface.
    """
    destination.evaluate(
        """node => {
          const cue = node.getAnimations().find(a => a.animationName?.endsWith('-flash'));
          if (!cue) throw new Error('the destination has no arrival cue');
          cue.pause();
          cue.effect.updateTiming({fill: 'forwards'});
          cue.currentTime = cue.effect.getComputedTiming().endTime;
        }"""
    )
    one_frame(page)
    endpoint = Image.open(io.BytesIO(destination.screenshot())).convert("RGB")
    destination.evaluate("node => node.getAnimations().forEach(a => a.cancel())")
    one_frame(page)
    resting = Image.open(io.BytesIO(destination.screenshot())).convert("RGB")
    assert endpoint.size == resting.size
    # Empty ground beside the prose; independent title animation can keep running.
    for point in [
        (2, endpoint.height // 2),
        (endpoint.width - 3, endpoint.height // 2),
    ]:
        assert endpoint.getpixel(point) == resting.getpixel(point), {
            "point": point,
            "endpoint": endpoint.getpixel(point),
            "resting": resting.getpixel(point),
        }


@pytest.mark.parametrize("resolved", [False, True])
def test_an_inline_reply_link_reveals_its_thread(browser, serve, resolved):
    """A direct reply link opens and cues the exact message, even in a long thread or
    in the Resolved state. The surrounding card can span more than a viewport,
    so using it as the arrival flash obscures the destination the link named."""
    url = serve(SEATED_ASK_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    reply = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Choose the first job.",
        '<lf-ask id="first-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="first-job" choose>'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
    )
    for i in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if i % 2 else "user",
                "parent": root,
                "revision": 1,
                "text": f"Follow-up {i}. " + "This exchange needs its context. " * 5,
            },
        )
    if resolved:
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
    page = open_page(browser, url)
    # A passage's thread opens in the panel for one of its messages, which the
    # panel's reader draws whole.
    thread = page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')
    destination = page.locator(f'.lf-fp-view .lf-msg[data-event="{reply["id"]}"]')
    if resolved:
        page.locator(".lf-resolved-summary").click()
    destination_selector = f'.lf-fp-view .lf-msg[data-event="{reply["id"]}"]'
    page.locator(".lf-page-thread-open").evaluate(
        """(open, selector) => open.addEventListener(
          'click',
          () => {
            window.__arrival = null;
            const arrived = (event) => {
              if (!event.target.matches?.(selector)) return;
              window.__arrival = event.animationName;
              event.target.getAnimations()
                .find(a => a.animationName === event.animationName).pause();
              document.removeEventListener('animationstart', arrived, true);
            };
            document.addEventListener('animationstart', arrived, true);
          },
          {capture: true, once: true},
        )""",
        destination_selector,
    )
    page.locator(".lf-page-thread-open").click()
    panel_settled(page, view="thread")
    page.wait_for_function("() => window.__arrival !== null")
    arrival = page.evaluate("() => window.__arrival")
    assert arrival.endswith("-flash"), arrival
    expect(thread).to_be_visible()
    expect(destination.locator("#first-job")).to_be_in_viewport()
    expect(destination).to_be_focused()
    expect(thread).not_to_have_class(re.compile(r"\bflash\b"))
    expect(destination).to_have_class(re.compile(r"\bflash\b"))
    assert_arrival_returns_to_own_fill(page, destination)
    sizes = page.evaluate(
        """([thread, destination]) => ({
          thread: thread.scrollHeight,
          destination: destination.getBoundingClientRect().height,
          shown: thread.clientHeight,
        })""",
        [thread.element_handle(), destination.element_handle()],
    )
    assert sizes["thread"] > sizes["shown"], sizes
    assert sizes["destination"] < sizes["shown"], sizes
    page.keyboard.press("Tab")
    expect(page.locator("#mounts [role=checkbox]")).to_be_focused()


def test_a_summary_folds_originals_and_a_direct_reply_link_reveals_them(browser, serve):
    """A checkpoint shortens only its admitted range and remains a route to originals.

    The messages before and after the range are controls: hiding either would mean the
    presentation collapsed by position rather than by the summary's declared ids.
    """
    url = serve(SEATED_ASK_PAGE)
    root = panel_comment(
        serve.page_dir, "Keep the opening question visible.", {"section": "jobs"}
    )
    first = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "The first job establishes the dependency.",
    )
    middle = append_user_reply(
        serve.page_dir, root, "Does that still hold for the camera?"
    )
    last = append_agent_reply(
        serve.page_dir,
        root,
        "Yes. The measured result supports it.",
        "<p>The measured result is 18 minutes.</p>",
    )
    latest = append_user_reply(
        serve.page_dir, root, "Then keep the latest exception visible."
    )
    summary = summarize_thread(
        serve.page_dir,
        first["id"],
        last["id"],
        "Checkpoint digest: the **dependency** remains and the measurement took "
        "`18 minutes`.",
    )

    page = open_page(browser, url)
    card = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    checkpoint = card.locator(
        f'.lf-thread-checkpoint[data-summary-id="{summary["id"]}"]'
    )
    expand = checkpoint.locator(".lf-summary-expand")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(expand).to_have_accessible_name("Show 3 earlier messages")
    expect(checkpoint.locator(".lf-summary-label")).to_have_text("Earlier discussion")
    label_box = checkpoint.locator(".lf-summary-label").bounding_box()
    control_box = expand.bounding_box()
    assert label_box["x"] + label_box["width"] <= control_box["x"]
    assert control_box["y"] <= label_box["y"] < control_box["y"] + control_box["height"]
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "Checkpoint digest: the dependency remains and the measurement took 18 minutes."
    )
    expect(checkpoint.locator(".lf-summary-text strong")).to_have_text("dependency")
    expect(checkpoint.locator(".lf-summary-text code")).to_have_text("18 minutes")
    assert (
        checkpoint.locator(".lf-summary-text").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    assert (
        checkpoint.locator(".lf-summary-text code").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    expect(card.locator(f'.lf-msg[data-event="{root}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{latest["id"]}"]')).to_be_visible()
    for message in (first, middle, last):
        expect(card.locator(f'.lf-msg[data-event="{message["id"]}"]')).to_be_hidden()

    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "true")
    for message in (first, middle, last):
        expect(card.locator(f'.lf-msg[data-event="{message["id"]}"]')).to_be_visible()
    expect(checkpoint.locator(".lf-summary-refold")).to_have_count(0)
    expect(expand).to_have_accessible_name("Collapse 3 earlier messages")
    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(card.locator(f'.lf-msg[data-event="{last["id"]}"]')).to_be_hidden()

    # The direct reply link opens the message in the panel, its fold open there.
    card.get_by_role("button", name="Show 3 earlier messages", exact=True).click()
    page.locator(".lf-page-thread-open").click()
    destination = page.locator(f'.lf-fp-view .lf-msg[data-event="{last["id"]}"]')
    expect(destination).to_be_visible()
    expect(destination).to_be_focused()


def test_previous_progress_messages_can_fold_without_summary_prose(browser, serve):
    """The same disclosure keeps progress available without an authored digest."""
    # The disclosure is the same at any width; the narrow one has the least room.
    width = 390
    url = serve(SEATED_ASK_PAGE)
    root = panel_comment(
        serve.page_dir, "Please check the schedule.", {"section": "jobs"}
    )
    first = append_agent_reply(serve.page_dir, root, "Checking the dependency.")
    last = append_agent_reply(serve.page_dir, root, "Checking the camera.")
    answer = append_agent_reply(serve.page_dir, root, "The schedule works.")
    summary = summarize_thread(
        serve.page_dir, first["id"], last["id"], "", label="Previous progress messages"
    )

    page = open_page(browser, url)
    resized(page, width, 900)
    card = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    checkpoint = card.locator(
        f'.lf-thread-checkpoint[data-summary-id="{summary["id"]}"]'
    )
    label = checkpoint.locator(".lf-summary-label")
    expand = checkpoint.get_by_role("button", name="Show 2 earlier messages")
    expect(label).to_have_text("Previous progress messages")
    expect(checkpoint.locator(".lf-summary-text")).to_have_count(0)
    expect(card.locator(f'.lf-msg[data-event="{answer["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{first["id"]}"]')).to_be_hidden()
    label_box = label.bounding_box()
    control_box = expand.bounding_box()
    assert label_box["x"] + label_box["width"] <= control_box["x"]
    assert control_box["y"] <= label_box["y"] < control_box["y"] + control_box["height"]
    expand.focus()
    page.keyboard.press("Enter")
    expect(card.locator(f'.lf-msg[data-event="{first["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{last["id"]}"]')).to_be_visible()
    checkpoint.get_by_role("button", name="Collapse 2 earlier messages").click()
    expect(card.locator(f'.lf-msg[data-event="{first["id"]}"]')).to_be_hidden()


@pytest.mark.parametrize("interleaved", [True, False])
def test_ephemeral_progress_folds_when_its_held_completion_is_revealed(
    browser, serve, interleaved
):
    """The answer and its fold arrive together; originals remain a keyboard route.
    Pending progress stands hidden behind the working message. In the page thread the
    answer would grow the thread's foot under the reader, so it waits behind the
    thread's notice."""
    url = serve(SEATED_ASK_PAGE)
    root = panel_comment(serve.page_dir, "Check the schedule.", {"section": "jobs"})
    progress = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Checking the camera.",
        ephemeral=True,
    )
    owed = root
    if interleaved:
        intervening = append_command(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "user",
                "parent": root,
                "text": "Check the mount too.",
            },
        )
        owed = intervening["id"]
        thread_model.post_reply(
            serve.page_dir,
            {"to": owed, "for": owed},
            "Checking the mount.",
            ephemeral=True,
        )

    def show(page):
        resized(page, 390, 844)
        return page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')

    page = open_page(browser, url)
    card = show(page)
    identity = "data-event"
    original = card.locator(f'.lf-msg[{identity}="{progress["id"]}"]')
    expect(original).to_be_hidden()
    runs = 2 if interleaved else 1
    expect(card.locator(".lf-thread-checkpoint")).to_have_count(runs)
    expect(card.locator(".lf-thread-working").get_by_role("button")).to_have_count(0)

    answer = thread_model.post_reply(
        serve.page_dir, {"to": owed, "for": owed}, "The schedule works."
    )
    told(page)
    card.get_by_role("button", name="1 new reply", exact=True).click()
    expect(card.locator(f'.lf-msg[{identity}="{answer["id"]}"]')).to_be_visible()
    checkpoint = card.locator(".lf-thread-checkpoint")
    expect(checkpoint.locator(".lf-summary-label")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-text")).to_have_count(0)

    # A fresh reading starts folded, independent of the live reader's protected focus.
    fresh = open_page(browser, url)
    fresh_card = show(fresh)
    fresh_original = fresh_card.locator(f'.lf-msg[{identity}="{progress["id"]}"]')
    expect(fresh_original).to_be_hidden()
    count = 2 if interleaved else 1
    noun = "messages" if interleaved else "message"
    expand = fresh_card.get_by_role(
        "button", name=f"Show {count} progress {noun}", exact=True
    )
    answer_header = fresh_card.locator(
        f'.lf-msg[{identity}="{answer["id"]}"] > .lf-msg-head'
    )
    expect(answer_header.get_by_role("button")).to_have_count(1)
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(fresh_card.locator(".lf-summary-label")).to_have_count(0)
    time_box = answer_header.locator("time").bounding_box()
    control_box = expand.bounding_box()
    assert time_box is not None
    header_box = answer_header.bounding_box()
    assert header_box["x"] <= control_box["x"]
    assert (
        control_box["x"] + control_box["width"] <= header_box["x"] + header_box["width"]
    )
    if interleaved:
        expect(
            fresh_card.get_by_text("Check the mount too.", exact=True)
        ).to_be_visible()
    expand.focus()
    fresh.keyboard.press("Shift+Tab")
    fresh.keyboard.press("Tab")
    expect(expand).to_be_focused()
    assert expand.evaluate("node => node.matches(':focus-visible')")
    fresh.keyboard.press("Enter")
    expect(fresh_original).to_be_visible()
    expect(fresh_original).to_contain_text("Checking the camera.")
    if interleaved:
        expect(
            fresh_card.get_by_text("Checking the mount.", exact=True)
        ).to_be_visible()
    collapse = fresh_card.get_by_role(
        "button", name=f"Hide {count} progress {noun}", exact=True
    )
    expect(collapse).to_be_in_viewport()
    collapse.press("Enter")
    expect(fresh_original).to_be_hidden()
    if interleaved:
        expect(fresh_card.get_by_text("Checking the mount.", exact=True)).to_be_hidden()


@pytest.mark.parametrize(("width", "touch"), [(390, False), (311, True)])
def test_progress_disclosure_keeps_its_words_visible_beside_margin_paging(
    browser, serve, width, touch
):
    """A narrow floating card keeps the full disclosure beside shared-target controls."""
    url = serve(PANEL_PAGE)
    roots = [
        panel_comment(serve.page_dir, text, {"section": "lede"})
        for text in ("Check the schedule.", "Check the camera.", "Check the mount.")
    ]
    root = roots[0]
    progress = [
        thread_model.post_reply(
            serve.page_dir, {"to": root, "for": root}, text, ephemeral=True
        )
        for text in (
            "I'm checking the afternoon schedule against the break.",
            "The three sessions take two hours. I'm checking whether the discussion still fits.",
            "The room is available until five. That leaves enough time for the break.",
        )
    ]
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Three sessions, a fifteen-minute break, and the closing discussion fit before five.",
    )
    context = browser.new_context(
        viewport={"width": width, "height": 670}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    card = preview.locator(f'.lf-page-thread[data-thread="{root}"]')
    for _ in roots[1:]:
        if card.count():
            break
        preview.get_by_role("button", name="Previous thread", exact=True).click()
    expect(card).to_be_visible()
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("1/3")

    def expect_headers_clear_actions():
        geometry = card.evaluate("""card => ({
          actions: card.querySelector('.lf-margin-thread-controls').getBoundingClientRect().left,
          heads: [...card.querySelectorAll('.lf-msg-head')]
            .filter(head => head.checkVisibility())
            .map(head => head.getBoundingClientRect().right)
        })""")
        assert geometry["heads"], geometry
        assert all(right <= geometry["actions"] + 0.5 for right in geometry["heads"]), (
            geometry
        )

    expect_headers_clear_actions()
    originals = [
        card.locator(f'.lf-msg[data-event="{message["id"]}"]') for message in progress
    ]
    for original in originals:
        expect(original).to_be_hidden()

    def expect_unclipped_words(control):
        expect(control).to_be_visible()
        expect(control).to_be_in_viewport(ratio=1)
        geometry = control.evaluate("""control => {
          const range = document.createRange();
          range.selectNodeContents(control);
          const words = [...range.getClientRects()].filter(box => box.width && box.height);
          const clipped = [];
          for (let node = control; node; node = node.parentElement) {
            if (!/^(hidden|clip|auto|scroll)$/.test(getComputedStyle(node).overflowX)) continue;
            const box = node.getBoundingClientRect();
            if (words.some(word => word.left < box.left - 1 || word.right > box.right + 1))
              clipped.push({class: node.className, left: box.left, right: box.right});
          }
          return {words: words.length, clipped};
        }""")
        assert geometry["words"] > 0, geometry
        assert geometry["clipped"] == [], geometry

    expand = card.get_by_role("button", name="Show 3 progress messages", exact=True)
    expect_unclipped_words(expand)
    expand.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(expand).to_be_focused()
    assert expand.evaluate("node => node.matches(':focus-visible')")
    page.keyboard.press("Enter")
    for original in originals:
        expect(original).to_be_visible()
    expect_headers_clear_actions()
    collapse = card.get_by_role("button", name="Hide 3 progress messages", exact=True)
    expect(collapse).to_be_focused()
    expect_unclipped_words(collapse)
    page.keyboard.press("Enter")
    for original in originals:
        expect(original).to_be_hidden()
    expect(expand).to_be_focused()
    expect_unclipped_words(expand)

    # A newer reading gesture supersedes that landing even while focus stays on Hide.
    page.keyboard.press("Enter")
    expect_unclipped_words(collapse)
    transcript = card.locator(":scope > .lf-thread-transcript")
    transcript.hover()
    page.mouse.wheel(0, -1000)
    expect(transcript).to_have_js_property("scrollTop", 0)
    expect(collapse).to_be_focused()
    resized(page, width, 650)
    expect(card.locator(".lf-msg").first).to_be_in_viewport()
    expect(collapse).to_be_focused()
    expect(originals[0]).to_be_in_viewport()


def test_a_summary_gathering_the_message_the_user_is_on_keeps_them_on_it(
    browser, serve
):
    """A checkpoint arriving over the message the user stands on opens around it.

    The message moves into the checkpoint's originals, and the user moves with it
    rather than dropping to the page. The summary waits behind the thread's notice
    until the user shows it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    first = append_agent_reply(serve.page_dir, root, "The constraint still applies.")
    held = append_user_reply(serve.page_dir, root, "It holds for the camera too.")
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")

    page = open_page(browser, url)
    resized(page, 1440, 600)
    card = open_margin_card(page, root)
    message = card.locator(f'.lf-msg[data-event="{held["id"]}"]')
    message.focus()
    expect(message).to_be_focused()

    summary = summarize_thread(
        serve.page_dir, first["id"], held["id"], "The constraint was confirmed."
    )
    told(page)
    show_held_news(card)
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(
        checkpoint.locator(
            f'.lf-summary-originals > .lf-msg[data-event="{held["id"]}"]'
        )
    ).to_be_visible()
    expect(message).to_be_focused()


def test_a_summary_folding_a_message_keeps_its_frame_loaded(browser, serve):
    """A message gathered into a checkpoint moves there whole, framed document and all.

    A frame in a reply holds a document of its own. When a summary folds the reply,
    the message moves from the transcript into the checkpoint's originals; a move
    that detached it on the way would reload that document and lose whatever the
    user had done in it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Show me the practice board.", {"section": "how-store"}
    )
    first = append_agent_reply(
        serve.page_dir,
        root,
        "Here it is:",
        markup='<iframe id="folded-frame" title="Practice board"'
        ' srcdoc="&lt;p&gt;Practice&lt;/p&gt;"></iframe>',
    )
    last = append_agent_reply(serve.page_dir, root, "Try a move on it.")
    page = open_page(browser, url)
    card = open_margin_card(page, root)
    page.frame_locator("#folded-frame").locator("p").wait_for()
    card.locator("#folded-frame").evaluate(
        "frame => { window.frameLoads = 0;"
        " frame.addEventListener('load', () => window.frameLoads++); }"
    )

    summary = summarize_thread(
        serve.page_dir, first["id"], last["id"], "The board was shown."
    )
    told(page)
    card.locator(".lf-thread-news").filter(has_text="1 summary changed").click()
    expect(
        card.locator(
            f'[data-summary-id="{summary["id"]}"] .lf-summary-originals #folded-frame'
        )
    ).to_be_attached()
    rendered(page)
    assert page.evaluate("window.frameLoads") == 0, "the fold reloaded the frame"

    # An edit inside the range retracts the summary, releasing the message again.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest-summary",
            "message": last["id"],
            "text": "Try a different move on it.",
        },
    )
    told(page)
    card.locator(".lf-thread-news").filter(
        has_text="1 message edited · 1 summary changed"
    ).click()
    expect(card.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(
        card.locator(f'.lf-msg[data-event="{first["id"]}"] #folded-frame')
    ).to_be_attached()
    rendered(page)
    assert page.evaluate("window.frameLoads") == 0, "the release reloaded the frame"


@pytest.mark.parametrize(
    ("width", "touch", "count"), [(1440, False, 2), (320, True, 10)]
)
def test_a_root_summary_keeps_thread_actions_outside_its_fold(
    browser, serve, width, touch, count
):
    """A checkpoint may cover the root turn without hiding thread actions.

    A narrow touch header wraps its disclosure while keeping its context label
    readable beside the complete header.
    An edit that retracts the checkpoint waits behind the card's notice while the user
    reads it, and drawn once they show it, leaves them on Resolve."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    reply = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The constraint still applies."
    )
    end = reply["id"]
    for number in range(count - 2):
        end = append_agent_reply(serve.page_dir, root, f"Earlier detail {number}.")[
            "id"
        ]
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")
    summary = summarize_thread(
        serve.page_dir, root, end, "The constraint was confirmed."
    )
    context = browser.new_context(
        viewport={"width": width, "height": 600}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, url, context=context)
    resized(page, width, 600)

    def activate(control):
        control.tap() if touch else control.click()

    activate(page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker'))
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(card.get_by_role("button", name="Resolve thread")).to_be_visible()
    alignment = card.evaluate("""card => {
      const headerNode = card.querySelector('.lf-summary-header');
      const header = headerNode.getBoundingClientRect();
      const labelNode = headerNode.querySelector('.lf-summary-label');
      const label = labelNode.getBoundingClientRect();
      const disclosure = headerNode.querySelector('.lf-summary-expand').getBoundingClientRect();
      const resolve = card.querySelector('.lf-resolve').getBoundingClientRect();
      return {headerCenter: header.top + header.height / 2,
        resolveCenter: resolve.top + resolve.height / 2,
        labelLines: label.height / parseFloat(getComputedStyle(labelNode).lineHeight),
        disclosureRight: disclosure.right,
        contentRight: header.right - parseFloat(getComputedStyle(headerNode).paddingInlineEnd)};
    }""")
    assert alignment["labelLines"] <= 1.1, alignment
    assert alignment["disclosureRight"] <= alignment["contentRight"] + 0.5, alignment
    expect(card.get_by_role("button", name="Close thread")).to_have_count(0)
    controls = card.locator(":scope > .lf-thread-content > .lf-thread-controls")
    assert controls.evaluate("node => !node.closest('.lf-summary-originals')"), (
        "thread actions entered the collapsible originals"
    )
    root_message = checkpoint.locator(f'.lf-msg[data-event="{root}"]')
    expect(root_message.locator(":scope > .lf-msg-head")).to_be_hidden()
    expect(root_message.locator(":scope > .lf-msg-body")).to_be_hidden()
    activate(checkpoint.locator(".lf-summary-expand"))
    expect(root_message.locator(":scope > .lf-msg-head")).to_be_visible()
    expect(root_message.locator(":scope > .lf-msg-body")).to_be_visible()
    expect(card.get_by_role("button", name="Resolve thread")).to_be_visible()
    activate(checkpoint.locator(".lf-summary-expand"))
    resolve = card.get_by_role("button", name="Resolve thread")
    resolve.focus()

    def edit_root(text):
        append_carried_log_record(
            serve.page_dir,
            {"kind": "edit", "author": "user", "message": root, "text": text},
        )
        told(page)

    edit_root("Start with the corrected measured constraint.")
    expect(
        card.get_by_role(
            "button", name="1 message edited · 1 summary changed", exact=True
        )
    ).to_be_visible()
    expect(checkpoint).to_have_count(1)
    expect(resolve).to_be_focused()

    card.locator(".lf-thread-news").evaluate("node => node.click()")
    expect(checkpoint).to_have_count(0)
    expect(resolve).to_be_focused()

    with sending(page, "resolve after the root summary is retracted"):
        activate(resolve)
    expect(card).to_be_hidden()


def test_a_later_summary_replaces_its_overlap_and_an_edit_restores_originals(
    browser, serve
):
    """The browser follows the canonical summary fold as the transcript changes.

    Each change to the fold of a card the user is reading waits behind its notice, with
    the words it would change; shown, a summary opens around the messages being read."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    first = thread_model.post_reply(
        serve.page_dir, {"to": root, "for": root}, "The first constraint."
    )
    second = append_agent_reply(serve.page_dir, root, "The second constraint.")
    third = append_agent_reply(serve.page_dir, root, "The third constraint.")
    old = summarize_thread(
        serve.page_dir,
        first["id"],
        second["id"],
        "Two constraints were established.",
    )
    page = open_page(browser, url)
    card = open_margin_card(page, root)
    old_checkpoint = card.locator(f'[data-summary-id="{old["id"]}"]')
    expect(old_checkpoint).to_be_visible()
    old_checkpoint.locator(".lf-summary-expand").click()
    standing = card.locator(f'.lf-msg[data-event="{second["id"]}"]')
    standing.focus()
    expect(standing).to_be_focused()

    replacement = summarize_thread(
        serve.page_dir,
        first["id"],
        third["id"],
        "All three constraints now form one decision.",
    )
    told(page)
    notice = card.locator(".lf-thread-news").filter(has_text="1 summary changed")
    expect(notice).to_be_visible()
    expect(old_checkpoint).to_be_visible()
    expect(standing).to_be_focused()
    notice.click()
    expect(card.locator(f'[data-summary-id="{old["id"]}"]')).to_have_count(0)
    checkpoint = card.locator(f'[data-summary-id="{replacement["id"]}"]')
    expect(checkpoint.locator(".lf-summary-expand")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(standing).to_be_visible()
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "All three constraints now form one decision."
    )

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest-summary",
            "message": second["id"],
            "text": "The corrected second constraint.",
        },
    )
    told(page)
    expect(checkpoint).to_be_visible()
    card.locator(".lf-thread-news").filter(
        has_text="1 message edited · 1 summary changed"
    ).click()
    expect(card.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(card.locator(f'.lf-msg[data-event="{first["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{second["id"]}"]')).to_contain_text(
        "The corrected second constraint."
    )
    expect(card.locator(f'.lf-msg[data-event="{third["id"]}"]')).to_be_visible()


def test_a_summary_cannot_hide_an_active_ask(browser, serve):
    """A checkpoint with a user obligation is context, never a closed cover."""
    url = serve(SEATED_ASK_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    question = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Choose the first job.",
        '<lf-ask id="summary-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="summary-job" choose>'
        '<lf-option id="summary-mounts">Put the mounts back</lf-option>'
        '<lf-option id="summary-camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
    )
    summary = summarize_thread(
        serve.page_dir,
        root,
        question["id"],
        "The discussion narrowed the work to two jobs.",
    )

    page = open_page(browser, url)
    card = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    checkpoint = card.locator(f'[data-summary-id="{summary["id"]}"]')
    expect(checkpoint).to_have_attribute("data-expanded", "true")
    expect(checkpoint.locator(".lf-summary-required")).to_have_text(
        "Messages kept open · current work"
    )
    expect(card.locator("#summary-job")).to_be_visible()
    expect(checkpoint.locator(".lf-summary-expand")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-refold")).to_have_count(0)
    originals = checkpoint.locator(".lf-summary-originals")
    widths = originals.evaluate(
        "originals => ({"
        "available: originals.getBoundingClientRect().width, "
        "message: originals.querySelector('.lf-msg').getBoundingClientRect().width"
        "})"
    )
    assert widths["available"] - widths["message"] < 20, widths
