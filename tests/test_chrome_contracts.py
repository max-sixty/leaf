"""Everyday browser contracts for shared chrome."""

import io
import json
import re
import time
from urllib.parse import urljoin

import pytest
from leaf import event_log as events_model
from leaf.media import store_uploaded_media
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    BANNER_ORDER,
    banner_control,
    button_radius,
    toggle_asks,
    token_colour,
    with_one_ask,
)
from render_cases_navigation import _publish
from render_harness import (
    LONG_PAGE,
    RENDERED,
    CutOff,
    Traffic,
    _until,
    clean_browser,
    compare_with,
    consume_browser_errors,
    leaf_page,
    open_page,
    open_versions,
    panel_settled,
    resized,
    sending,
    told,
    watched,
)


def test_agent_reply_arrivals_keep_open_panel_drafts_and_summarize_batches(
    browser, serve
):
    """Unread replies announce once each, whether they arrive while the page is open or
    were waiting when it opened, regardless of the panel's disclosure. The user keeps
    a draft open in a thread no reply lands in, so exposure acknowledges none of them."""
    url = serve(leaf_page("Reply arrivals", "<h1>Reply arrivals</h1>"))
    directory = serve.page_dir
    drafting, a, b = (
        events_model.append_event(
            directory,
            {"kind": "comment", "author": "user", "revision": 1, "text": text},
        )
        for text in ("Draft here", "A", "B")
    )
    events_model.append_event(
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
    notice = page.locator(".lf-notice")
    expect(live).to_have_text("Codex replied")
    expect(notice).to_have_text("Codex replied")
    expect(notice).not_to_have_class(re.compile(r"\bshow\b"), timeout=10_000)

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(f'.lf-thread[data-id="{drafting["id"]}"]')).to_have_attribute(
        "open", ""
    )
    draft = page.locator(f'.lf-thread[data-id="{drafting["id"]}"] textarea')
    draft.fill("Keep this draft")
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
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": b["id"],
            "text": "For B",
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    expect(live).to_have_text("Codex replied")
    expect(notice).to_have_text("Codex replied")
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    reads = CutOff().hold(page)
    events_model.append_event(
        directory,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": a["id"],
            "text": "More for A",
        },
    )
    events_model.append_event(
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
    expect(notice).to_have_text("2 replies in 2 threads", timeout=5_000)
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/notifications.js')).holdStatus(10000)"
    )
    for parent in (a["id"], b["id"]):
        events_model.append_event(
            directory,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": parent,
                "text": "Another answer",
            },
        )
        page.evaluate(
            "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
        )
    page.wait_for_function(
        "() => window.__lfReplyAnnouncements.filter(words => words === 'Codex replied').length === 3"
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/notifications.js')).holdStatus(1)"
    )
    expect(notice).to_have_text("4 replies in 2 threads")
    expect(notice).to_be_visible()
    expect(draft).to_be_focused()
    expect(draft).to_have_value("Keep this draft")

    # A duplicate read makes no fresh announcement; a fresh document announces what
    # the user has still not read.
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    page.wait_for_timeout(100)
    assert page.evaluate("() => window.__lfReplyAnnouncements") == [
        "Codex replied",
        "2 replies in 2 threads",
        "Codex replied",
        "Codex replied",
    ]
    page.reload()
    expect(page.locator(".lf-live")).to_have_text("6 replies in 2 threads")


def test_incoming_reply_follows_a_thread_at_its_latest_message(browser, serve):
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Start this conversation.")
    for index in range(14):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    page.locator(".lf-thread[open] .lf-compose textarea").fill("A short follow-up.")
    assert threads.evaluate("el => el.scrollHeight > el.clientHeight")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    threads.evaluate("el => el.scrollTop -= 40")
    near_end = threads.evaluate("el => el.scrollTop")

    newest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "The new answer should come into view. " * 5,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    message = page.locator(f'.lf-msg[data-mid="{newest["id"]}"]')
    expect(message).to_be_visible()
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before",
        arg=near_end,
    )
    assert threads.evaluate("el => el.scrollTop") > near_end
    page.wait_for_function(
        """id => {
          const list = document.querySelector('.lf-threads');
          const message = list.querySelector(`[data-mid="${id}"]`);
          const bottom = list.getBoundingClientRect().bottom -
            parseFloat(getComputedStyle(list).scrollPaddingBottom);
          return message.getBoundingClientRect().bottom <= bottom + 2;
        }""",
        arg=newest["id"],
    )

    for length in (20, 40, 120):
        before_growth = threads.evaluate("el => el.scrollTop")
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "edit",
                "author": "agent",
                "agent": "Codex",
                "message": newest["id"],
                "text": "The answer grows while the user is following it. " * length,
            },
        )
        page.evaluate(
            "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
        )
        page.wait_for_function(
            "before => document.querySelector('.lf-threads').scrollTop > before",
            arg=before_growth,
        )
        page.wait_for_function(
            """id => {
              const list = document.querySelector('.lf-threads');
              const message = list.querySelector(`[data-mid="${id}"]`);
              const bottom = list.getBoundingClientRect().bottom -
                parseFloat(getComputedStyle(list).scrollPaddingBottom);
              return Math.abs(message.getBoundingClientRect().bottom - bottom) <= 2;
            }""",
            arg=newest["id"],
        )

    threads.evaluate("el => el.scrollTop -= 160")
    earlier_place = threads.evaluate("el => el.scrollTop")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "Later answer must not pull the user away from history.",
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    assert threads.evaluate("el => el.scrollTop") == pytest.approx(earlier_place, abs=2)


@pytest.mark.parametrize("earlier_cards,later_cards", [(0, 0), (1, 0), (0, 3)])
def test_incoming_reply_follows_when_the_panel_has_unfilled_room(
    browser, serve, earlier_cards, later_cards
):
    url = serve(LONG_PAGE)
    for index in range(earlier_cards):
        panel_comment(serve.page_dir, f"An earlier conversation {index}.")
    root = panel_comment(serve.page_dir, "A short conversation.")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "A short first answer.",
        },
    )
    for index in range(later_cards):
        panel_comment(serve.page_dir, f"A later conversation {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    if earlier_cards:
        page.locator(f'.lf-thread[data-id="{root}"] .lf-thread-summary').click()
        expect(page.locator(f'.lf-thread[data-id="{root}"]')).to_have_attribute(
            "open", ""
        )
    threads = page.locator(".lf-threads")
    assert threads.evaluate("el => el.scrollHeight - el.clientHeight") == 0

    newest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "A long answer should bring its newest words into view. " * 120,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    message = page.locator(f'.lf-msg[data-mid="{newest["id"]}"]')
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert message.evaluate("el => el.getBoundingClientRect().bottom") == pytest.approx(
        threads.evaluate(
            "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom)"
        ),
        abs=2,
    )


def test_incoming_reply_follows_a_visible_composer_below_earlier_words(browser, serve):
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "A conversation with a draft.")
    for index in range(14):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    card.locator(".lf-compose textarea").fill(("A draft line.\n" * 8).strip())
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    before = threads.evaluate("el => el.scrollTop")
    prior = card.locator(".lf-msg").last
    fold = threads.evaluate(
        "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom)"
    )
    assert prior.evaluate("el => el.getBoundingClientRect().bottom") < fold - 80
    assert prior.evaluate("el => el.getBoundingClientRect().bottom") > threads.evaluate(
        "el => el.getBoundingClientRect().top"
    )

    newest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "This reply grows below the older words and above the draft. " * 20,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before", arg=before
    )
    assert card.locator(f'.lf-msg[data-mid="{newest["id"]}"]').evaluate(
        "el => el.getBoundingClientRect().bottom"
    ) == pytest.approx(fold, abs=2)


def test_another_threads_reply_keeps_the_selected_thread_in_place(browser, serve):
    url = serve(LONG_PAGE)
    other = panel_comment(serve.page_dir, "An earlier conversation.")
    selected = panel_comment(serve.page_dir, "The selected conversation.")
    for index in range(14):
        events_model.append_event(
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    threads = page.locator(".lf-threads")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    last_selected = card.locator(".lf-msg").last
    before = last_selected.evaluate("el => el.getBoundingClientRect().top")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": other,
            "text": "This belongs to the other conversation. " * 5,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    expect(card).to_have_attribute("open", "")
    assert last_selected.evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(before, abs=2)


@pytest.mark.parametrize("later_cards", [4, 30])
def test_incoming_reply_follows_a_selected_thread_before_later_cards(
    browser, serve, later_cards
):
    url = serve(LONG_PAGE)
    selected = panel_comment(serve.page_dir, "The conversation I am reading.")
    for index in range(14):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Selected answer {index}. " * 5,
            },
        )
    for index in range(later_cards):
        panel_comment(serve.page_dir, f"A later conversation {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    card.locator(".lf-msg").last.evaluate(
        "el => el.scrollIntoView({block: 'end', behavior: 'instant'})"
    )
    threads = page.locator(".lf-threads")
    before = threads.evaluate("el => el.scrollTop")
    assert (
        threads.evaluate("el => el.scrollHeight - el.clientHeight - el.scrollTop") > 80
    )

    newest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "This new answer belongs to the selected conversation. " * 5,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before",
        arg=before,
    )
    assert card.locator(f'.lf-msg[data-mid="{newest["id"]}"]').evaluate(
        "el => el.getBoundingClientRect().bottom"
    ) == pytest.approx(
        threads.evaluate(
            "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom)"
        ),
        abs=2,
    )

    card.locator(".lf-msg").last.evaluate(
        "el => el.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    reading_later = threads.evaluate("el => el.scrollTop")
    also_visible = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "This short answer is already visible while I read later cards.",
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    arriving = card.locator(f'.lf-msg[data-mid="{also_visible["id"]}"]')
    expect(arriving).to_be_visible()
    assert threads.evaluate("el => el.scrollTop") == pytest.approx(reading_later, abs=2)
    assert arriving.evaluate(
        "el => el.getBoundingClientRect().bottom"
    ) < threads.evaluate(
        "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom)"
    )

    if later_cards == 30:
        threads.evaluate("el => el.scrollTop += 160")
        reading_later = threads.evaluate("el => el.scrollTop")
        assert card.evaluate(
            "el => el.getBoundingClientRect().bottom"
        ) < threads.evaluate(
            "el => el.getBoundingClientRect().bottom - parseFloat(getComputedStyle(el).scrollPaddingBottom) - 80"
        )
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": "A long answer must not pull me back to this conversation. "
                * 120,
            },
        )
        page.evaluate(
            "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
        )
        assert threads.evaluate("el => el.scrollTop") == pytest.approx(
            reading_later, abs=2
        )


@pytest.mark.parametrize("intent", ["focus", "pointer"])
def test_a_later_cards_reader_stays_at_the_list_end(browser, serve, intent):
    url = serve(LONG_PAGE)
    selected = panel_comment(serve.page_dir, "The conversation above.")
    for index in range(14):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": selected,
                "text": f"Earlier answer {index}. " * 5,
            },
        )
    for index in range(4):
        panel_comment(serve.page_dir, f"A later conversation {index}.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{selected}"]')
    card.locator(".lf-thread-summary").click()
    expect(card).to_have_attribute("open", "")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    threads = page.locator(".lf-threads")
    threads.evaluate("el => el.scrollTop = el.scrollHeight")
    before = threads.evaluate("el => el.scrollTop")
    assert before > 0
    later_card = threads.locator(":scope > .lf-thread:not([hidden])").last
    if intent == "focus":
        later_card.locator(".lf-thread-summary").focus()
    else:
        later_card.locator(".lf-thread-summary").hover()
    later_top = later_card.evaluate("el => el.getBoundingClientRect().top")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": selected,
            "text": "A long answer should not pull me from the later cards. " * 120,
        },
    )
    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/application.js')).readAndApply()"
    )
    assert later_card.evaluate("el => el.getBoundingClientRect().top") == pytest.approx(
        later_top, abs=2
    )


def test_interrupted_background_notice_keeps_the_newer_version(browser, serve):
    """An older visible notice cannot replace a newer one already waiting."""
    page = open_page(browser, serve(leaf_page("Notice order", "<h1>Notice order</h1>")))
    page.evaluate(
        """async () => {
          const {notice} = await window.__lfRuntimeImport('/runtime/notifications.js');
          notice('Updated to v3', {background: true});
          notice('Updated to v4', {background: true});
          notice('Saved — sent');
        }"""
    )
    shown = page.locator(".lf-notice")
    expect(shown).to_have_text("Saved — sent")
    expect(shown).to_have_text("Updated to v4", timeout=5_000)


class _ProblemPage:
    url = "https://leaf.test/example"

    def add_init_script(self, **_):
        pass

    def on(self, *_):
        pass


def test_browser_health_rejects_an_unconsumed_problem():
    """A forgotten per-test assertion cannot turn a browser fault green."""

    with (
        pytest.raises(
            AssertionError, match="https://leaf.test/example: unexpected browser fault"
        ),
        clean_browser(),
    ):
        watched(_ProblemPage()).append("unexpected browser fault")


def test_consuming_browser_problems_accounts_for_every_entry():
    """Naming one expected fault cannot consume an unrelated one."""

    with clean_browser():
        page = _ProblemPage()
        watched(page).extend(["expected fault", "unrelated fault"])
        with pytest.raises(AssertionError, match="unrelated fault"):
            consume_browser_errors(page, "expected fault")


def test_live_revision_retains_the_runtime_favicon(browser, serve):
    """In-place activation keeps the banner's runtime-owned tab status surface."""
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
def test_a_margin_reply_shares_its_conversations_opaque_surface(browser, serve, scheme):
    """The reply surround stays continuous as focus enters and leaves the conversation.

    An opaque shared surface also lets a pinned reply cover scrolled messages without
    introducing a differently colored band above its input.
    """
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, color_scheme=scheme)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    thread = preview.locator(".lf-conversation-thread")
    surround = thread.locator(".lf-say")
    reply = preview.get_by_role("button", name="Reply", exact=True)
    editor = preview.locator("textarea")
    expect(reply).to_be_visible()

    for state in ("collapsed", "editing", "outside"):
        if state == "editing":
            reply.click()
            expect(editor).to_be_focused()
        elif state == "outside":
            preview.get_by_role("button", name="Dismiss conversation").focus()
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


@pytest.mark.parametrize("width", [320, 800])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_thread_keeps_submit_in_its_field_and_resolve_with_its_metadata(
    browser, serve, width, scheme
):
    """Submit belongs to the field while Resolve stands with the root metadata.

    Growing the field carries Submit with it and leaves Resolve fixed. Draft words
    begin at the sent message's edge and leave room for Submit in the same row.
    Resolve aligns with the root author and time instead of the quoted target. The
    same layout holds at narrow and wide panel widths in both palettes."""
    context = browser.new_context(
        viewport={"width": width, "height": 720}, color_scheme=scheme
    )
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    thread.locator(".lf-thread-summary").click()
    compose = thread.locator(".lf-compose")
    textarea = compose.locator("textarea")
    send = thread.get_by_role("button", name="Send", exact=True)
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    close = page.get_by_role("button", name="Close threads", exact=True)
    expect(send).to_be_visible()
    expect(resolve).to_be_visible()
    expect(send.locator('svg[data-lf-icon="send"]')).to_have_count(1)
    expect(resolve.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    expect(thread.get_by_role("button", name="Close thread", exact=True)).to_have_count(
        0
    )
    expect(send).to_have_text("")
    expect(resolve).to_have_text("")
    expect(close).to_have_text("")

    def geometry():
        return thread.evaluate(
            """thread => {
                  const rect = sel => {
                    const r = thread.querySelector(sel).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height,
                            right: r.right, bottom: r.bottom};
                  };
                  const own = thread.getBoundingClientRect();
                  const inputStyle = getComputedStyle(thread.querySelector('textarea'));
                  const messageStyle = getComputedStyle(thread.querySelector('.lf-msg-body'));
                  const padding = parseFloat(inputStyle.paddingInlineEnd);
                  const radius = (selector, pseudo = null) => getComputedStyle(
                    selector.startsWith('.lf-thread-panel')
                      ? document.querySelector(selector)
                      : thread.querySelector(selector), pseudo).borderRadius;
                  return {thread: {x: own.x, y: own.y, width: own.width,
                                   height: own.height, right: own.right, bottom: own.bottom},
                          compose: rect('.lf-compose'), field: rect('.lf-compose-field'),
                          textarea: rect('.lf-compose textarea'),
                          metadata: rect('.lf-thread-root-meta'),
                          metadataActions: rect('.lf-thread-meta-actions'),
                          send: rect('.lf-thread-send'), resolve: rect('.lf-resolve'),
                          closeBorder: getComputedStyle(document.querySelector(
                            '.lf-thread-panel-head [aria-label="Close threads"]')).borderTopWidth,
                          resolveBorder: getComputedStyle(thread.querySelector(
                            '.lf-resolve'), '::before').borderTopWidth,
                          sendBorder: getComputedStyle(thread.querySelector(
                            '.lf-thread-send'), '::before').borderTopWidth,
                          radii: {
                            send: radius('.lf-thread-send'),
                            sendFill: radius('.lf-thread-send', '::before'),
                            resolve: radius('.lf-resolve'),
                            resolveFill: radius('.lf-resolve', '::before'),
                            close: radius('.lf-thread-panel-head [aria-label="Close threads"]'),
                          },
                          message: rect('.lf-msg-body'),
                          messageFont: messageStyle.font,
                          inputFont: inputStyle.font,
                          textStart: rect('.lf-compose textarea').x +
                            parseFloat(inputStyle.borderInlineStartWidth) +
                            parseFloat(inputStyle.paddingInlineStart),
                          textEnd: rect('.lf-compose textarea').right -
                            parseFloat(inputStyle.borderInlineEndWidth) - padding,
                          padding,
                          overflow: thread.scrollWidth - thread.clientWidth};
                }"""
        )

    short = geometry()
    assert short["field"]["x"] == pytest.approx(short["compose"]["x"], abs=1)
    assert short["message"]["x"] - short["field"]["x"] == pytest.approx(8, abs=1)
    assert short["field"]["x"] - short["thread"]["x"] == pytest.approx(
        short["thread"]["right"] - short["field"]["right"], abs=1
    )
    assert short["textarea"]["right"] == pytest.approx(short["field"]["right"], abs=1)
    assert short["send"]["right"] < short["textarea"]["right"]
    assert short["textarea"]["y"] < short["send"]["y"]
    assert short["send"]["bottom"] < short["textarea"]["bottom"]
    assert short["textEnd"] <= short["send"]["x"]
    assert short["field"]["height"] < 50
    assert short["resolve"]["y"] == pytest.approx(short["metadata"]["y"], abs=1)
    assert short["metadataActions"]["right"] == pytest.approx(
        short["message"]["right"], abs=1
    )
    assert short["resolve"]["right"] == pytest.approx(
        short["metadataActions"]["right"], abs=1
    )
    assert short["metadata"]["x"] == pytest.approx(short["message"]["x"], abs=1)
    assert short["resolve"]["bottom"] <= short["metadata"]["bottom"] + 1
    assert float(short["closeBorder"][:-2]) == 0
    assert float(short["resolveBorder"][:-2]) == 0
    assert float(short["sendBorder"][:-2]) == 0
    assert set(short["radii"].values()) == {button_radius(page)}
    assert short["overflow"] == 0

    textarea.focus()
    focused = geometry()
    assert focused["send"] == short["send"]
    assert focused["resolve"] == short["resolve"]

    textarea.fill("First line.\nSecond line.\nThird line.\nFourth line.")
    grown = geometry()
    assert grown["inputFont"] == grown["messageFont"]
    assert grown["textStart"] == pytest.approx(grown["message"]["x"], abs=1)
    assert grown["textEnd"] <= grown["send"]["x"]
    assert grown["padding"] == pytest.approx(short["padding"], abs=1)
    assert grown["send"]["bottom"] < grown["textarea"]["bottom"]
    assert grown["send"]["x"] == pytest.approx(short["send"]["x"], abs=1)
    assert grown["send"]["y"] > short["send"]["y"]
    assert grown["metadataActions"] == short["metadataActions"]
    assert grown["resolve"] == short["resolve"]
    assert grown["overflow"] == 0

    textarea.fill("A long draft remains readable while scrolling. " * 120)
    assert textarea.evaluate("el => el.scrollHeight > el.clientHeight")
    for position in (0, 80, 99999):
        textarea.evaluate("(el, top) => el.scrollTop = top", position)
        scrolling = geometry()
        assert scrolling["send"]["bottom"] < scrolling["textarea"]["bottom"]
        assert scrolling["textStart"] == pytest.approx(scrolling["message"]["x"], abs=1)
        assert scrolling["textEnd"] <= scrolling["send"]["x"]


@pytest.mark.parametrize("thread_count", [1, 2])
@pytest.mark.parametrize("touch", [False, True])
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
    dismiss = preview.get_by_role("button", name="Dismiss conversation view")
    expect(resolve).to_be_visible()
    expect(dismiss).to_be_visible()
    assert dismiss.evaluate("button => button.closest('.lf-thread-root-meta') !== null")
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
              const meta = preview.querySelector('.lf-thread-root-meta');
              const middle = selector => {
                const box = meta.querySelector(selector).getBoundingClientRect();
                return box.y + box.height / 2;
              };
              return {
                nav: middle('.lf-margin-preview-nav'),
                author: middle('.lf-conversation-head > b'),
                actions: middle('.lf-thread-meta-actions'),
                authorRight: meta.querySelector('.lf-conversation-head')
                  .getBoundingClientRect().right,
                navLeft: meta.querySelector('.lf-margin-preview-nav')
                  .getBoundingClientRect().left,
                navRight: meta.querySelector('.lf-margin-preview-nav')
                  .getBoundingClientRect().right,
                resolveLeft: meta.querySelector('.lf-resolve')
                  .getBoundingClientRect().left,
                overflow: meta.scrollWidth - meta.clientWidth,
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
    dismiss.focus()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread-summary:focus")).to_have_count(1)


STATE_PAINT = """el => {
  const style = getComputedStyle(el);
  return {background: style.backgroundColor, shadow: style.boxShadow};
}"""


def test_signoff_enabled_face_is_readable(browser, serve):
    """The banner's committing action carries the accent as ink on the ordinary
    card, never as a solid accent fill."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_enabled()
    paint = button.evaluate(
        "el => ({ink: getComputedStyle(el).color, "
        "        fill: getComputedStyle(el).backgroundColor})"
    )
    assert paint == {
        "ink": token_colour(page, "--accent"),
        "fill": token_colour(page, "--card"),
    }, f"the banner's primary action lost its readable face: {paint}"


def test_a_menu_comparison_keeps_its_active_paint(browser, serve):
    """A standing comparison remains legible in its fixed menu seat."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    _publish(serve.page_dir, 2, html, "reworded the suggestion")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    chooser = page.locator(".lf-version")
    expect(chooser).to_be_enabled()

    resized(page, 1440, 900)
    compare_with(page, 1)
    expect(chooser).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
    banner_control(page, ".lf-version")
    page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    box = chooser.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    active = chooser.evaluate(STATE_PAINT)
    assert (
        active["shadow"] != "none" and "rgba(0, 0, 0, 0)" not in active["background"]
    ), f"the comparison stood in the menu with nothing but ink: {active}"

    resized(page, 320, 844)
    expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
    banner_control(page, ".lf-version")
    assert chooser.evaluate(STATE_PAINT) == active
    chooser.click()
    versions = page.locator(".lf-version-menu")
    expect(versions).to_be_visible()
    box = versions.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    open_versions(page)
    expect(versions).to_be_visible()
    box = versions.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    # The door's news is the shelf's to state, and it restates it on every paint. A
    # newer version puts the urgent latest chip in the menu, so the accent the door
    # takes is the one the page arrived at rather than one the test wrote on it.
    door = page.locator(".lf-banner-more")
    _publish(serve.page_dir, 3, html, "reworded the suggestion again")
    told(page)
    expect(door).to_have_attribute("aria-label", "More page controls, new")
    expect(door).to_have_css("border-top-color", token_colour(page, "--accent"))


def test_the_banner_reads_in_one_order_at_every_width(browser, serve, other_leaf):
    """The fixed menu and primary row keep one reading order at every width."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    expect(page.locator(".lf-signoff")).to_be_disabled()
    expect(page.locator(".lf-signoff")).to_have_attribute(
        "title", "Answer every Ask before approving this work"
    )
    banner_control(page, ".lf-answer-all")

    orders = {}
    for width in (1440, 860, 800, 390):
        resized(page, width, 900)
        orders[width] = page.evaluate(BANNER_ORDER)

    first = {}
    for width, order in orders.items():
        for index, before in enumerate(order):
            for after in order[index + 1 :]:
                assert (after, before) not in first, (
                    f"{after!r} comes before {before!r} at {first[(after, before)]}px "
                    f"and after it at {width}px: {orders}"
                )
                first.setdefault((before, after), width)
    assert len(first) >= 15, (
        f"too few controls stood at these widths to have an order at all: {orders}"
    )

    # And the order it settled on: every banner control the page offers, with the reading loop
    # finishing the row beside the panel it opens.
    widest = max(orders.values(), key=len)
    for wanted in ("All leaves", "Asks", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in widest), (
            f"{wanted} was not on the row at all, so this order proves little: {widest}"
        )
    for width, order in orders.items():
        assert order[-1].startswith("Threads"), (
            f"the conversation no longer finishes the row at {width}px: {order}"
        )
    resized(page, 500, 900)
    control = banner_control(page, ".lf-others")
    control.click()
    page.mouse.move(0, page.viewport_size["height"] - 1)
    expect(control).to_have_attribute("aria-expanded", "true")
    expect(control).to_have_css("background-color", token_colour(page, "--chip"))


def test_notices_stay_at_the_visible_pages_right_edge(browser, serve):
    """A notice keeps the page's right corner through panel and viewport changes."""
    page = open_page(browser, serve(LONG_PAGE))
    notice = page.locator(".lf-notice")
    for width, panel_open in [
        (1200, False),
        (1200, True),
        (390, True),
        (320, True),
        (390, False),
    ]:
        resized(page, width, 800)
        if panel_open != page.locator(".lf-thread-panel").is_visible():
            if panel_open:
                page.locator(".lf-threads-toggle").click()
            else:
                page.get_by_role("button", name="Close threads", exact=True).click()
            panel_settled(page, open=panel_open)
        page.evaluate("""async () => {
          const {notice} = await window.__lfRuntimeImport('/runtime/notifications.js');
          notice('Update recorded');
        }""")
        expect(notice).to_be_visible()
        geometry = page.locator(".lf-bottom-status").evaluate("""status => {
          const box = status.getBoundingClientRect();
          const panel = document.querySelector('.lf-thread-panel').getBoundingClientRect();
          const beside = panel.width > 0 && innerWidth > 840;
          return {right: box.right, left: box.left, bottom: box.bottom, top: box.top,
            availableRight: beside ? panel.left : innerWidth};
        }""")
        assert geometry["right"] == pytest.approx(
            geometry["availableRight"] - 18, abs=1
        ), (width, panel_open, geometry)
        assert geometry["left"] >= 0, (width, panel_open, geometry)
        assert geometry["bottom"] <= 800 - 14, (width, panel_open, geometry)
        if panel_open and width <= 840:
            foot = page.locator(".lf-thread-panel-foot").bounding_box()
            assert geometry["bottom"] == pytest.approx(foot["y"] - 14, abs=1)
        pixels = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        accent = tuple(map(int, re.findall(r"\d+", token_colour(page, "--accent"))))
        assert (
            pixels.getpixel(
                (
                    round(geometry["left"] + 5),
                    round((geometry["top"] + geometry["bottom"]) / 2),
                )
            )
            == accent
        ), (width, panel_open, "the notice is covered by the panel or its scrim")


PHONE_PAGE = leaf_page(
    "phone",
    "<h1 id='t'>Phone</h1><p id='p1'>Paragraph one. " + "Filler. " * 40 + "</p>",
)


@pytest.mark.parametrize("viewport", [None, "width=device-width, initial-scale=1"])
def test_a_phone_starts_the_page_and_comments_on_a_selection(iphone, serve, viewport):
    """The runtime starts in WebKit; selection offers an explicit Comment action.

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
    # The selection's next step stands on the row in the reading loop's place, where
    # the finger that made the selection finds it; More stays shut.
    comment = page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    )
    expect(comment).to_be_visible()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(page.locator(".lf-threads-toggle")).to_be_hidden()
    box = comment.bounding_box()
    assert box["x"] + box["width"] <= page.evaluate("innerWidth"), box
    comment.tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(field).to_be_focused()
    field.fill("From a phone")
    with sending(page, "the comment"):
        page.locator(".lf-fab-bar").get_by_role("button", name="Comment").tap()
    [comment] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert comment["text"] == "From a phone"
    assert comment["anchor"]["quote"] == "Paragraph one", comment


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
    """Phone fields keep their text size and stand below a selected paragraph.

    Safari zooms the page onto a text field set under 16px as the field takes focus, and
    leaves it zoomed: tapping the field jumped the view, then left the user panning
    sideways across a page wider than the screen. So no field the page holds is smaller,
    and a draft, whose editor wears the words' own face, shows them on the same floor, or
    one set in a sidenote's smaller type opens a size larger than it showed.

    The field goes below this paragraph even though it has more room above and too
    little below: the page makes the room. This emulation cannot show the native iOS
    selection menu, whose placement needs actual-device verification."""
    page = open_page(None, serve(PHONE_READING_PAGE), context=iphone)
    # Every field in the composed tree, the vendored controls' own native fields in
    # their shadow roots included: the Threads find box and the Map's search are
    # Web Awesome inputs, and Safari zooms onto the field inside them.
    sizes = page.evaluate("""() => {
      const sizes = {};
      const walk = (root) => {
        for (const node of root.querySelectorAll('*')) {
          if (node.matches('input, textarea, select')) {
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
    comment = page.locator(".lf-banner-actions").get_by_role(
        "button", name="Comment on selection"
    )
    box = comment.bounding_box()
    assert box and 0 <= box["y"] < page.evaluate("innerHeight"), box
    comment.tap()
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    placed = page.evaluate("""() => {
      const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
      const paragraph = document.getElementById('p6').getBoundingClientRect();
      return {barTop: bar.top, barBottom: bar.bottom, paragraphBottom: paragraph.bottom};
    }""")
    assert placed["barTop"] >= placed["paragraphBottom"], placed
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


def test_the_delivered_stylesheets_read_exactly_as_their_files_do(browser, serve):
    """Delivery drops the sheets' comments and re-serializes what is left, so what a page
    adopts is not the file's own bytes. The two have to say the same thing to the browser:
    a stylesheet oddity the serializer repairs would change the rules every page runs
    under, and no parser here would report it."""
    page = open_page(browser, serve(LONG_PAGE))
    layer = urljoin(
        page.url,
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').dataset.lfEntry"
        ),
    )
    files = {}
    for name in ("chrome", "marks"):
        answer = page.request.get(urljoin(layer, f"runtime/{name}.css"))
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
          const { chromeSheet: chrome, marksSheet: marks } =
            await window.__lfRuntimeImport("/runtime/stylesheets.js");
          if (![chrome, marks].every(sheet => document.adoptedStyleSheets.includes(sheet)))
            throw new Error("The document did not adopt its chrome and marks sheets");
          return {
            chrome: {delivered: rules(chrome), file: fromFile(files.chrome)},
            marks: {delivered: rules(marks), file: fromFile(files.marks)},
          };
        }""",
        files,
    )
    for name, reading in readings.items():
        assert reading["delivered"], f"the page adopted no {name} rules"
        assert reading["delivered"] == reading["file"], name


def test_a_traffic_wait_stops_when_repaints_outlive_its_deadline(monkeypatch):
    """A page that repaints its ledger forever cannot keep a false fact alive forever."""

    class BusyPage:
        reads = 0

        def evaluate(self, _script):
            self.reads += 1
            return json.dumps(
                {"sends": self.reads, "acked": 0, "asked": 0, "heard": 0, "pending": []}
            )

        def wait_for_function(self, *_args, **_kwargs):
            raise AssertionError("the expired wait listened for another paint")

    page = BusyPage()
    page.lf_traffic = Traffic(page)
    times = iter((0, 31, 31, 31))
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    with pytest.raises(AssertionError, match="never reached a false fact"):
        _until(page, lambda _traffic: False, "reached a false fact")


def test_message_markdown_reads_a_link_scheme_as_the_attribute_resolves_it(
    browser, serve
):
    """The web-protocol guard reads the href the document will resolve, not its source.

    marked hands a renderer the authored destination with its character references
    undecoded, and an href attribute decodes them when that markup lands. A guard
    reading the authored text sees `javascript&#58;` as a relative path, admits it,
    and the user gets a live script link out of ordinary message prose. Reading the
    destination as the document will refuses that link, and the same reading is what
    keeps an ordinary `&amp;` reaching the query it names rather than landing in it.

    Marked owns each field's rendering, including flattened inline alt text, titles,
    and the literal character references in autolinks. Page-media inspection must use
    that same image alt for its accessible name.
    """
    url = serve(LONG_PAGE)
    pixels = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(pixels, format="PNG")
    media = store_uploaded_media(serve.page_dir, pixels.getvalue(), "image/png")
    panel_comment(
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    prose = page.locator(".lf-msg-text").first
    # The surviving link carries the chrome's external-link note, so the words are read
    # as a run inside the prose rather than as the whole of its text.
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

    page.locator(".lf-thread-summary").first.click()
    media_button = prose.get_by_role("button", name="View A media chart", exact=True)
    expect(media_button.locator("img")).to_have_attribute("alt", "A media chart")
    media_button.focus()
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute("alt", "A media chart")
    page.keyboard.press("Escape")
    expect(media_button).to_be_focused()


@pytest.mark.parametrize("width", [900, 1400])
def test_threads_cover_the_page_and_leave_its_column_where_it_was(
    browser, serve, width
):
    """Opening Threads never moves the page: the panel stands over the right of the
    window at every width, so the reading column keeps its place, its width and its
    wrapping, and the document neither grows nor scrolls under it. The page beside the
    panel stays live rather than going inert behind a covering boundary."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    resized(page, width, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 900")
    shape = """() => {
      const main = document.querySelector('body > main').getBoundingClientRect();
      return {
        left: main.left, width: main.width,
        scroll: document.scrollingElement.scrollTop,
        tall: document.documentElement.scrollHeight,
        shell: document.body.clientWidth,
      };
    }"""
    before = page.evaluate(shape)

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)
    panel = page.locator(".lf-thread-panel").bounding_box()
    assert panel["x"] + panel["width"] == pytest.approx(width, abs=1)
    assert not page.locator("main").evaluate("el => el.inert")
    expect(page.locator(".lf-thread-panel")).not_to_have_attribute("aria-modal", "true")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    assert page.evaluate(shape) == pytest.approx(before, abs=0.5)


# A sheet laid on one set of tracks: a long body beside a short rail, the rail being the
# part of a sheet a panel standing over the window's right edge would cover.
SHEET_PAGE = leaf_page(
    "sheet",
    """
<h1 id="t">Sheet</h1>
<lf-grid id="tracks" columns="2fr 1fr">
  <lf-grid id="body" columns="1">{paras}</lf-grid>
  <lf-grid id="side" columns="1">
    <section class="panel" id="rail"><h2>Rail</h2><p>Counts beside the body.</p></section>
  </lf-grid>
</lf-grid>
""",
    width="available",
).format(
    paras="\n".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 40 + "</p>" for i in range(40)
    )
)


def test_a_sheet_yields_the_open_panel_its_room_where_the_window_leaves_one(
    browser, serve
):
    """On a sheet the open panel takes its room from the page rather than covering the
    rail: the sheet narrows and its tracks reflow beside the panel, and the page stays
    live. Where the window would leave less than a usable page, the panel covers it as
    it does any page, and the sheet keeps the whole window underneath."""
    page = open_page(browser, serve(SHEET_PAGE))
    resized(page, 1440, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(".lf-thread-panel").bounding_box()
    rail = page.locator("#rail").bounding_box()
    assert panel["x"] + panel["width"] == pytest.approx(1440, abs=1)
    assert rail["x"] + rail["width"] <= panel["x"]
    assert rail["y"] < page.locator("#p1").bounding_box()["y"], "the rail left the body"
    assert not page.locator("main").evaluate("el => el.inert")
    expect(page.locator(".lf-thread-panel")).not_to_have_attribute("aria-modal", "true")

    resized(page, 700, 900)
    expect(page.locator(".lf-thread-panel")).to_have_attribute("aria-modal", "true")
    main = page.locator("main").bounding_box()
    assert (
        main["x"] + main["width"] > page.locator(".lf-thread-panel").bounding_box()["x"]
    )
    assert page.locator("main").evaluate("el => el.inert")


def test_the_sheets_strip_for_the_panel_leaves_the_user_on_the_same_words(
    browser, serve
):
    """The strip a sheet yields the open panel reflows the page, and the user stays on
    the words they were on — carried by the browser's scroll anchoring, as across the
    Asks tray's strip (the test below says what that rests on)."""
    page = open_page(browser, serve(SHEET_PAGE))
    resized(page, 1440, 900)
    page.evaluate("() => document.scrollingElement.scrollTop = 1500")
    at_the_top = """
    () => {
      const edge = Number.parseFloat(
        getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0;
      const p = [...document.querySelectorAll('main p')]
        .find((p) => p.getBoundingClientRect().bottom > edge);
      return p && { id: p.id, top: p.getBoundingClientRect().top };
    }
    """
    reading = page.evaluate(at_the_top)
    assert reading, "the fixture put no paragraph under the top of the window"
    tall = page.evaluate("() => document.documentElement.scrollHeight")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate("() => document.documentElement.scrollHeight") > tall, (
        "the strip reflowed nothing, so nothing is proved"
    )
    opened = page.evaluate(at_the_top)
    assert opened["id"] == reading["id"]
    assert opened["top"] == pytest.approx(reading["top"], abs=2)

    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    assert page.evaluate("() => document.documentElement.scrollHeight") == tall
    closed = page.evaluate(at_the_top)
    assert closed["id"] == reading["id"]
    assert closed["top"] == pytest.approx(reading["top"], abs=2)


def test_taking_the_asks_trays_strip_leaves_the_user_on_the_same_words(browser, serve):
    """The Asks tray's strip reflows the page; the user stays on the words they were on.

    Narrowing the shell narrows the reading column inside it, so the text re-wraps and
    the document grows above wherever the user is standing. The browser's scroll
    anchoring absorbs that, and nothing in the runtime does: this passes with no script
    holding the user's place. That is what makes it the guard. Anchoring is suppressed
    for any frame in which a box on the anchor's ancestor chain changes a property on the
    suppression list — `margin`, `padding`, `width`, an inset, a transform — so the strip
    is a border and the column does not glide (theme.css, at the body strip), and the
    tray renders on either side of the frame the shell write lands in, never inside it
    (`takeShell`, chrome-layout.js). The day any of these regresses, this goes red.

    A re-wrap moves every paragraph by a different amount, so only one of them can be
    held. The one the user's place means is the block under the top of the window,
    which is the block the platform's own anchoring would have chosen; what is further
    down has grown taller and is expected to have moved.
    """
    page = open_page(browser, serve(with_one_ask(LONG_PAGE)))
    # Narrow enough that the strip's share of the shell re-wraps this fixture's
    # paragraphs, and wide enough that the tray stands beside the page rather than
    # covering it: the assertions below say so rather than trusting the width.
    resized(page, 700, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 900")
    # The user's place: the page's own block under the window's visible top edge, which
    # the root states as scroll-padding for native focus navigation.
    at_the_top = """
    () => {
      const edge = Number.parseFloat(
        getComputedStyle(document.scrollingElement).scrollPaddingTop) || 0;
      const p = [...document.querySelectorAll('main p')]
        .find((p) => p.getBoundingClientRect().bottom > edge);
      return p && { id: p.id, top: p.getBoundingClientRect().top };
    }
    """
    reading = page.evaluate(at_the_top)
    assert reading, "the fixture put no paragraph under the top of the window"
    tall = page.evaluate("() => document.documentElement.scrollHeight")

    toggle_asks(page)
    expect(page.locator(".lf-asks-panel")).not_to_have_attribute("aria-modal", "true")
    assert page.evaluate("() => document.documentElement.scrollHeight") > tall, (
        "the window is wide enough that the strip reflowed nothing, so nothing is proved"
    )
    opened = page.evaluate(at_the_top)
    assert opened["id"] == reading["id"]
    assert opened["top"] == pytest.approx(reading["top"], abs=2)

    toggle_asks(page, open=False)
    assert page.evaluate("() => document.documentElement.scrollHeight") == tall
    closed = page.evaluate(at_the_top)
    assert closed["id"] == reading["id"]
    assert closed["top"] == pytest.approx(reading["top"], abs=2)


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
          const {marginEntry, registerMarginContribution} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const contribute = (key, target, label) => registerMarginContribution({
            key, target,
            read: () => ({entries: [marginEntry({key: 'action', icon: 'dot', label})]}),
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
    page.keyboard.press("Shift+m")
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
    on the page rather than on a guessed number of frames."""
    url = serve(leaf_page("Settled", '<h1 id="h">Settled</h1><p id="p">Words.</p>'))
    page = open_page(browser, url)
    settled = (
        "() => document.querySelector('script[data-lf-entry]').lfRenderingSettled()"
    )
    assert page.evaluate(settled), "a page handed over by open_page is settled"

    assert (
        page.evaluate(
            """() => {
              document.querySelector('.lf-threads-toggle').click();
              return document.querySelector('script[data-lf-entry]').lfRenderingSettled();
            }"""
        )
        is False
    )
    page.evaluate(RENDERED)
    assert page.evaluate(settled)
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
