"""An entry's record across a reload and a return from another document: the user
comes back where they left the entry, as Back within the page brings them."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import (
    LONG_PAGE,
    open_page,
    open_threads,
    panel_view,
    scroll_settled,
    select_words,
)

from browser.test_render_drawing import draw_over
from leaf.render_checks import wait_until_ready
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed

ENGINES = ["browser", "firefox_browser"]

# Whether focus stands on nothing, or on something the window shows.
FOCUS_SEEN = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  if (!at || at === document.body) return true;
  const box = at.getBoundingClientRect();
  return box.bottom > 0 && box.top < innerHeight && box.right > 0 && box.left < innerWidth;
}"""

# The caret of the field focus stands in, as [start, end].
CARET = """() => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement && at.selectionStart === undefined)
    at = at.shadowRoot.activeElement;
  return at && at.selectionStart !== undefined ? [at.selectionStart, at.selectionEnd] : null;
}"""


def reload(page):
    page.wait_for_function("navigation.transition === null")
    page.reload()
    wait_until_ready(page)


def long_card(serve, extra=""):
    """A passage thread with replies long enough to scroll its card, one reply holding a
    link to the last paragraph, and `extra` words in the fourth."""
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    for n in range(7):
        text = f"Reply {n}. " + "More of the explanation. " * 30
        if n == 3:
            text += extra or "See [the last paragraph](#p59)."
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": text,
            },
        )
    return root


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_a_thread_in_the_reader_it_showed(request, serve, engine):
    """A thread about a passage the user opened in the floating panel, from Threads, is
    there again after a reload, rather than in a card beside a passage the window
    doesn't show, and focus stands only on what the window shows."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    open_threads(page)
    page.locator(".lf-fp-thread").first.click()
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(view).to_be_visible()
    reload(page)
    expect(view).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    assert page.evaluate(FOCUS_SEEN)


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_where_a_card_was_read_to(request, serve, engine):
    """A card read partway reopens after a reload at the reply the user had read it to,
    not at its first unread reply or its end."""
    url = serve(LONG_PAGE)
    root = long_card(serve)
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    transcript = card.locator(".lf-thread-transcript")
    card.get_by_role("link", name="the last paragraph").scroll_into_view_if_needed()
    scroll_settled(page)
    read_to = transcript.evaluate("box => box.scrollTop")
    reload(page)
    expect(card).to_be_visible()
    scroll_settled(page)
    assert abs(transcript.evaluate("box => box.scrollTop") - read_to) <= 2


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("where", ["reply", "rewrite", "comment"])
def test_a_reload_keeps_the_caret_in_words_being_written(request, serve, engine, where):
    """Words being written, a reply in a card, a rewrite of the user's own message or a
    new comment, come back after a reload with the caret where the user left it inside
    them, not at their end."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    if where in {"reply", "rewrite"}:
        page.keyboard.press("t")
        card = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        )
        expect(card).to_be_focused()
        if where == "reply":
            page.keyboard.press("c")
        else:
            card.locator(f'.lf-msg[data-lf-message="{root}"] .lf-msg-text').dblclick()
            page.wait_for_function(f"() => ({CARET})() !== null")
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.press("Delete")
    else:
        select_words(page, "#p3")
        page.keyboard.press("c")
    page.wait_for_function(f"() => ({CARET})() !== null")
    page.keyboard.type("Take it from the infrastructure reserve")
    for _ in range(8):
        page.keyboard.press("ArrowLeft")
    page.wait_for_function(f"() => ({CARET})()?.[0] === 31")
    reload(page)
    page.wait_for_function(f"() => JSON.stringify(({CARET})()) === '[31,31]'")


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_the_list_the_panel_showed(request, serve, engine):
    """Threads, open in the floating panel, is open again after a reload."""
    url = serve(LONG_PAGE)
    for n in (1, 2):
        panel_comment(
            serve.page_dir,
            f"Question {n}?",
            {"section": f"p{n}", "quote": f"Paragraph {n}."},
        )
    page = open_page(request.getfixturevalue(engine), url)
    open_threads(page)
    expect(page.locator(panel_view("threads"))).to_be_visible()
    reload(page)
    expect(page.locator(panel_view("threads"))).to_be_visible()


@pytest.mark.parametrize("engine", ENGINES)
def test_back_from_another_document_returns_to_the_link_followed(
    request, serve, engine
):
    """A link in a card to another document, followed and come Back from, leaves the
    user on that link in the card again, as Back within the page does."""
    url = serve(LONG_PAGE)
    # The page itself, loaded afresh: another document, as any page elsewhere is.
    root = long_card(serve, "See [the elsewhere page](v1.html).")
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    link = card.get_by_role("link", name="the elsewhere page")
    link.scroll_into_view_if_needed()
    scroll_settled(page)
    page.wait_for_function("navigation.transition === null")
    with page.expect_navigation():
        link.click()
    page.go_back()
    wait_until_ready(page)
    expect(link).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_leaves_a_kept_draft_shut(request, serve, engine):
    """A new comment the user put away with Escape stays put away after a reload that
    finds them elsewhere: focus doesn't go into it, so the next key is a command, not a
    word added to the draft."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir, "Why here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    select_words(page, "#p3")
    page.keyboard.press("c")
    page.wait_for_function(f"() => ({CARET})() !== null")
    page.keyboard.type("Is this the overnight scan")
    page.keyboard.press("Escape")
    page.wait_for_function(f"() => ({CARET})() === null")
    page.evaluate("document.activeElement?.blur?.()")
    page.evaluate(
        "scrollTo({top: document.getElementById('p20').offsetTop, behavior: 'instant'})"
    )
    scroll_settled(page)
    reload(page)
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert page.evaluate(CARET) is None
    assert page.evaluate(FOCUS_SEEN)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_reload_keeps_focus_on_a_control_in_a_comment_box(request, serve, engine):
    """Focus on a control in a new comment's box, as its drawing's Undo, comes back to
    that control after a reload, with the box and its drawing open again."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    draw_over(page, page.locator("#p3"))
    undo = page.get_by_role("button", name="Undo last stroke")
    undo.focus()
    expect(undo).to_be_focused()
    reload(page)
    expect(undo).to_be_focused()


@pytest.mark.parametrize("engine", ENGINES)
def test_a_tab_discarded_while_hidden_comes_back_where_it_was_left(
    request, serve, engine
):
    """A tab the browser discards while hidden, as a phone or a desktop's memory saver
    does, unloads without `beforeunload`; the record written as it was hidden brings
    the user's selection back when it loads again."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    page.evaluate("""() => {
      const text = document.getElementById('p20').firstChild;
      getSelection().setBaseAndExtent(text, 0, text, 'Paragraph 20.'.length);
    }""")
    page.evaluate("""() => {
      Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});
      document.dispatchEvent(new Event('visibilitychange'));
      // The discard, which runs no unload handler.
      addEventListener('beforeunload', (event) => event.stopImmediatePropagation(), {capture: true});
    }""")
    reload(page)
    page.wait_for_function("() => getSelection().toString() === 'Paragraph 20.'")
