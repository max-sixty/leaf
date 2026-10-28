"""News arriving in a thread the user reads, from agent replies and other tabs, either
waits behind a notice or lands without moving what the user is reading or typing in."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    holding,
    nudge,
    open_page,
    resized,
    scroll_settled,
    told,
    write,
)

from browser.threads import (
    LANDING_WORDS,
    PANEL_NEWS,
    PANEL_REPLY,
    append_agent_reply,
    append_user_reply,
    open_panel_thread,
    reply_by_keyboard,
    seed_panel_threads,
)
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_returning_to_a_hidden_tab_reveals_held_and_refreshed_replies(browser, serve):
    """Returning catches up once, keeping the native draft and its caret.

    Losing focus during visible reading keeps the notice. A hidden interval ends
    that reading, including news admitted by the first asynchronous refresh; later
    arrivals protect the resumed reading again.
    """
    # The animated reveal is the path that could move the draft.
    motion = "no-preference"
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Keep this discussion open.", {"section": "how-store"}
    )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion=motion)
    # A passage's thread, in its margin card, holds news while the user writes there.
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    field = card.locator(":scope > .lf-thread-reply leaf-text")
    words = "A thought to continue when I return."
    write(field, words)
    field.evaluate(
        "field => { field.setSelectionRange(8, 8); window.__returnEditor = field; }"
    )
    first = append_agent_reply(serve.page_dir, root, "An answer held during reading.")
    told(page)
    expect(card.locator(".lf-thread-news")).to_be_visible()
    first_message = card.locator(f'.lf-msg[data-event="{first["id"]}"]')
    expect(first_message).to_have_count(0)

    page.evaluate("window.dispatchEvent(new Event('blur'))")
    rendered(page)
    expect(card.locator(".lf-thread-news")).to_be_visible()
    expect(first_message).to_have_count(0)

    page.evaluate("""() => {
      window.__lfTestVisibility = 'hidden';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => window.__lfTestVisibility,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    nudge(serve.page_dir)
    with page.expect_request("**/api/news"):
        page.evaluate("""() => {
          window.__lfTestVisibility = 'visible';
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
    holding(page, held, 1, "the first refresh after returning")
    expect(first_message).to_be_visible()
    second = append_agent_reply(serve.page_dir, root, "Another answer while away.")
    expect(card.locator(f'.lf-msg[data-event="{second["id"]}"]')).to_have_count(0)
    held.pop().continue_()
    page.unroute("**/api/state*")
    told(page)
    rendered(page)
    expect(card.locator(f'.lf-msg[data-event="{second["id"]}"]')).to_be_visible()
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    expect(field).to_have_js_property("value", words)
    expect(field).to_be_focused()
    assert field.evaluate("""field => field === window.__returnEditor
      && field.selectionStart === 8 && field.selectionEnd === 8""")

    third = append_agent_reply(serve.page_dir, root, "News after reading resumes.")
    told(page)
    rendered(page)
    expect(card.locator(".lf-thread-news")).to_be_visible()
    expect(card.locator(f'.lf-msg[data-event="{third["id"]}"]')).to_have_count(0)


def test_an_arrival_interrupts_nothing_the_user_holds(browser, serve):
    """The nodes themselves survive the poll: the reply being typed in the panel's
    field is the same element afterwards, still focused, caret where the typing left
    it, and where it stood, even when the arrival concerns that very thread."""
    url = serve(LONG_PAGE, comments=1)
    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    page = open_page(browser, url)
    open_panel_thread(page, first["id"])
    ta = page.locator(PANEL_REPLY)
    ta.click()
    ta.type("half a thought")
    page.evaluate("""() => {
        document.activeElement.setSelectionRange(4, 4);
        window.__heldEditor = document.activeElement;
    }""")
    before = ta.bounding_box()
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "Landing right above the box being typed in.",
        },
    )
    told(page)
    news = page.locator(f"{PANEL_NEWS}:not([hidden])")
    arrived = page.locator(f'.lf-fp-view .lf-msg[data-event="{reply["id"]}"]')
    expect(arrived.or_(news).first).to_be_visible()
    rendered(page)
    after = ta.bounding_box()
    for edge in before:
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)
    assert page.evaluate("""() => {
        const ta = document.activeElement;
        return ta.localName === 'leaf-text'
            && ta === window.__heldEditor
            && ta.value === 'half a thought'
            && ta.selectionStart === 4 && ta.selectionEnd === 4;
    }"""), "the poll replaced or disturbed the node the user was typing into"


def test_an_agent_turn_arriving_while_the_user_writes_keeps_their_box_in_view(
    browser, serve
):
    """An arriving turn preserves the visible writing box, draft and Send control."""
    # The short window, where the arriving turn has the least room.
    size = (800, 520)
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 4, long_index=2)[2]
    page = open_page(browser, url)
    resized(page, *size)
    view = reply_by_keyboard(page, root)
    draft = "Half a thought I am still typing"
    page.keyboard.type(draft)
    rendered(page)
    editor = page.locator(PANEL_REPLY)
    before = editor.bounding_box()
    send = page.locator(".lf-fp-field .lf-compose-submit")
    assert clear_of_the_window(send), "Send starts outside the window"
    arrived = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "An agent answer arrives. " + LANDING_WORDS,
        },
    )
    told(page)
    expect(
        view.locator(f'.lf-msg[data-event="{arrived["id"]}"]')
        .or_(page.locator(f"{PANEL_NEWS}:not([hidden])"))
        .first
    ).to_be_visible()
    rendered(page)
    expect(editor).to_be_focused()
    assert editor.evaluate("box => box.value") == draft
    assert editor.bounding_box() == before
    assert clear_of_the_window(send), "the arrival pushed Send out of the window"


def clear_of_the_window(locator):
    return locator.evaluate(
        """node => { const box = node.getBoundingClientRect();
          return box.height > 0 && box.top >= 0 && box.bottom <= innerHeight; }"""
    )


@pytest.mark.watch_shifts
def test_appended_replies_keep_the_panel_reading(browser, serve):
    """The open thread holds the reading while replies are appended to it: a reader
    scrolled back into a long thread keeps the message they read where it stood.
    Agent and other-tab user appends share the same rule."""
    url = serve(PANEL_PAGE)
    (root,) = seed_panel_threads(serve.page_dir, 1, long_index=0)
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    view.hover()
    page.mouse.wheel(0, -400)
    page.wait_for_function(
        "view => view.scrollHeight - view.scrollTop - view.clientHeight > 100",
        arg=view.element_handle(),
    )
    scroll_settled(page, PANEL_THREAD)
    page.mouse.move(100, 100)
    reference = view.locator(".lf-msg").nth(2)
    rendered(page)
    before = reference.bounding_box()
    for append in (append_agent_reply, append_user_reply):
        reply = append(
            serve.page_dir, root, "New material here.\n\nAnother paragraph follows."
        )
        told(page)
        arrived = view.locator(f'.lf-msg[data-event="{reply["id"]}"]')
        expect(
            arrived.or_(page.locator(f"{PANEL_NEWS}:not([hidden])")).first
        ).to_be_visible()
        rendered(page)
        assert reference.bounding_box() == before
