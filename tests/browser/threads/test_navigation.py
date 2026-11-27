"""Moving to and between threads by keyboard and pointer: the walks that reach a
thread and the history they leave, and leaving or re-entering a reply."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import THREAD_DIFF_PAGE, live_url, panel_comment
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    put_preview_away,
    resized,
    scroll_settled,
    select_words,
    told,
    without_end_room,
)

from browser.margin import CARD_AT_REST
from browser.threads import append_agent_reply, open_panel_thread, summarize_thread
from leaf.source.render_checks import wait_until_ready
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


def test_back_returns_from_a_thread_the_walk_travelled_to(browser, serve):
    """Each trip to a thread somewhere else adds a history entry where the user stood,
    so Back retraces the walk one thread at a time, back to where the user was reading,
    and Forward replays it."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back from a thread",
            "<h1>Back from a thread</h1>"
            "<section id=near><p>The first question sits at the top.</p></section>"
            f"<section id=above>{filler}</section>"
            "<section id=also><p>A second question sits halfway down.</p></section>"
            f"<section id=below>{filler}</section>",
        )
    )
    for section in ("near", "also"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": section},
                "text": f"A question about {section}.",
            },
        )
    page = open_page(browser, url)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("Shift+t")
    page.wait_for_function("() => document.activeElement?.closest('[data-lf-thread]')")
    # Focus reaches the card before its passage starts scrolling into view.
    expect(page.locator("#also p")).to_be_in_viewport()
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    first = page.evaluate(
        "document.activeElement.closest('[data-lf-thread]').dataset.lfThread"
    )
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-lf-thread]')?.dataset.lfThread"
        " !== first",
        arg=first,
    )
    expect(page.locator("#near p")).to_be_in_viewport()
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked < landed - 1000
    assert page.evaluate("history.length") == entries + 2

    for back, top in [
        (True, landed),
        (True, reading),
        (False, landed),
        (False, walked),
    ]:
        page.wait_for_function("navigation.transition === null")
        if back:
            page.go_back()
        else:
            page.go_forward()
        page.wait_for_function(
            "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=top
        )


@pytest.mark.parametrize(
    "left",
    [
        "page thread's link",
        "passage thread's link",
        "card's link",
        "walk",
        "Show on page",
    ],
)
def test_back_reopens_the_thread_its_departure_put_away(browser, serve, left):
    """Leaving a thread for a place its view would stand over puts the view away, and
    Back reopens the thread in the reader the user had it in, where they had read it
    to, with the user on what they left by, the thread or a link in it, and no other
    thread open: the panel for a thread they read there, about the whole page or a
    passage, and the margin card for one they read in the card. A `t` walk from the
    panel's thread to a card, and Show on page, read where the user was before the
    panel puts its view away. Forward lands on the place again and puts the view away
    again."""
    url = serve(LONG_PAGE)
    page_root = panel_comment(serve.page_dir, "Where does this end?")
    passage_root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    for root in (page_root, passage_root):
        # The link stands in the thread's first reply, above the replies the panel's
        # view opens at.
        for text in [
            "See [the last paragraph](#p59).",
            *(f"Reply {n}. " + "More of the explanation. " * 30 for n in range(6)),
        ]:
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
    page = open_page(browser, url)
    # The last paragraph ends a page with no room below it, so the view stands over it.
    without_end_room(page)
    card = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{passage_root}"]'
    )
    if left == "card's link":
        page.keyboard.press("t")
        thread = card
    else:
        root = (
            passage_root
            if left in ("passage thread's link", "Show on page")
            else page_root
        )
        open_panel_thread(page, root)
        if left in ("walk", "Show on page"):
            # From the page's foot, so going to the passage at its top moves the page.
            # Opening the passage's thread in the panel brought its passage into view.
            page.evaluate("scrollTo({top: 1e6, behavior: 'instant'})")
            scroll_settled(page)
        thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    left_by = thread
    if left == "walk":
        page.keyboard.press("Escape")
        expect(thread).to_be_focused()
        page.keyboard.press("t")
        destination = card
    elif left == "Show on page":
        # Back returns to the control the user left by, which the view draws again.
        left_by = page.locator(".lf-fp-head .lf-fp-on-page")
        left_by.click()
        # A press lands on the card's thread, its reply holding no words
        # (panel/floating-panel.js, `movedPart`).
        destination = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        )
    else:
        left_by = thread.get_by_role("link", name="the last paragraph")
        left_by.scroll_into_view_if_needed()
        read_to = thread.evaluate("view => view.scrollTop")
        left_by.click()
        destination = page.locator("#p59")
    expect(destination).to_be_focused()
    expect(thread).to_be_hidden()

    page.go_back()
    expect(left_by).to_be_focused()
    if left in ("page thread's link", "passage thread's link"):
        assert abs(thread.evaluate("view => view.scrollTop") - read_to) <= 2
    expect(
        page.locator(PANEL_THREAD if left == "card's link" else ".lf-margin-preview")
    ).to_be_hidden()
    # Forward to a card's reply box returns to the thread's passage instead, with the
    # panel's view still open: a reply's editing continuity carries it across a
    # revision (features/version.js), and a return carries no reply.
    if left != "Show on page":
        page.go_forward()
        expect(destination).to_be_focused()
        expect(thread).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("window", ["wide", "narrow"])
def test_back_returns_to_the_card_a_later_open_in_panel_left(
    request, serve, engine, window
):
    """Back to an entry whose thread the user read in its card opens the card again,
    though a later Open in panel chose the panel for threads from then on: the entry's
    record names the view they stood in, which the choice doesn't (records/thread/address.js),
    as Back after Show on page returns to the panel's view. Where no card can stand by
    then, as on a window too narrow for the rail, the thread opens in the panel, as Leaf
    places it there whatever was chosen."""
    url = serve(LONG_PAGE)
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    cards = page.locator(".lf-margin-preview")
    card = cards.locator(".lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", second)
    # The card glides from the first passage's seat to the second's after the scroll
    # that brings it lands; a click issued mid-glide can land on the page beside it.
    scroll_settled(page)
    page.wait_for_function(CARD_AT_REST)
    cards.get_by_role("button", name="Open in panel", exact=True).click()
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{second}"]')).to_be_visible()
    expect(cards).to_be_hidden()
    if window == "narrow":
        resized(page, 700, 900)
    page.wait_for_function("navigation.transition === null")

    page.go_back()
    if window == "wide":
        expect(card).to_have_attribute("data-lf-thread", first)
        expect(page.locator(PANEL_THREAD)).to_have_count(0)
    else:
        expect(
            page.locator(f'{PANEL_THREAD}[data-lf-thread="{first}"]')
        ).to_be_visible()
        expect(cards).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_rewrite_written_in_a_card_back_returned_to_reopens_there(
    request, serve, engine
):
    """A rewrite of the user's message, written in the card Back returned them to after
    Open in panel chose the panel, comes back in that card after a reload: the entry's
    record says the thread stands in its card, and the rewrite's return fills the box
    of the view that return opened rather than opening the thread again where the
    choice of where threads open says."""
    url = serve(LONG_PAGE)
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    second = panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    cards = page.locator(".lf-margin-preview")
    card = cards.locator(".lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", second)
    # The card glides from the first passage's seat to the second's after the scroll
    # that brings it lands; a click issued mid-glide can land on the page beside it.
    scroll_settled(page)
    page.wait_for_function(CARD_AT_REST)
    cards.get_by_role("button", name="Open in panel", exact=True).click()
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{second}"]')).to_be_visible()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(card).to_have_attribute("data-lf-thread", first)
    # The card Back reopens is still moving into its seat when it names the thread;
    # a double-click issued mid-glide can land on the page beside it.
    scroll_settled(page)
    page.wait_for_function(CARD_AT_REST)
    card.locator(".lf-msg .lf-msg-text").first.dblclick()
    editor = card.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.press("End")
    page.keyboard.type(" Twice.")
    page.wait_for_function("navigation.transition === null")
    page.reload()
    wait_until_ready(page)
    expect(card).to_have_attribute("data-lf-thread", first)
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Why here? Twice.")
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_reopens_a_card_where_the_user_had_read_it_to(request, serve, engine):
    """Back to an entry whose card a trip put away opens the card again at the reply the
    user had read it to, standing where it stood in the card, rather than at the card's
    first unread reply, with the user on the link they left by."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    for n in range(7):
        text = f"Reply {n}. " + "More of the explanation. " * 30
        if n == 3:
            text += "See [the last paragraph](#p59)."
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
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    transcript = card.locator(".lf-thread-transcript")
    link = card.get_by_role("link", name="the last paragraph")
    link.scroll_into_view_if_needed()
    scroll_settled(page)
    read_to = transcript.evaluate("box => box.scrollTop")
    link.click()
    expect(page.locator("#p59")).to_be_focused()
    expect(card).to_be_hidden()
    page.wait_for_function("navigation.transition === null")

    page.go_back()
    expect(link).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    scroll_settled(page)
    assert abs(transcript.evaluate("box => box.scrollTop") - read_to) <= 2


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_reopens_a_card_read_to_a_folded_summary(request, serve, engine):
    """A card read to the summary that folds its earlier replies reopens on Back with
    that summary where it stood, though the replies it folds stand hidden under it."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    words = "More of the explanation. " * 30
    folded = [
        append_agent_reply(serve.page_dir, root, f"Folded {n}. {words}")
        for n in range(3)
    ]
    for n in range(4):
        append_agent_reply(serve.page_dir, root, f"Later {n}. {words}")
    summarize_thread(
        serve.page_dir, folded[0]["id"], folded[-1]["id"], "The first three, in short."
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    transcript = card.locator(".lf-thread-transcript")
    summary = card.locator(".lf-thread-checkpoint")
    expect(summary.locator(".lf-summary-expand")).to_have_attribute(
        "aria-expanded", "false"
    )
    # The summary at the top of the transcript, a little scrolled into.
    summary.evaluate(
        """node => {
          const box = node.closest('.lf-thread-transcript');
          box.scrollTop += node.getBoundingClientRect().top - box.getBoundingClientRect().top + 20;
        }"""
    )
    scroll_settled(page)
    read_to = transcript.evaluate("box => box.scrollTop")
    page.keyboard.press("t")
    expect(card).not_to_be_attached()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(card).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    scroll_settled(page)
    assert abs(transcript.evaluate("box => box.scrollTop") - read_to) <= 2


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_returns_to_a_named_control_in_a_message_the_agent_rewrote(
    request, serve, engine
):
    """A control the message names, as an option by its id, comes back by that name
    though the agent rewrote the message meanwhile and put another control before it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which way should we go?")
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )

    def ask(*options):
        return (
            'Pick one.\n\n<lf-group id="way" label="Which way?"><h3 id="way-h">Which way?'
            '</h3><lf-options id="way-pick">'
            + "".join(
                f'<lf-option id="{name}">{name.title()}</lf-option>' for name in options
            )
            + "</lf-options></lf-group>"
        )

    reply = append_agent_reply(serve.page_dir, root, ask("keep", "drop"))
    page = open_page(request.getfixturevalue(engine), url)
    thread = open_panel_thread(page, root)
    # The option's own control, which takes focus for it.
    keep = thread.locator('#keep [role="checkbox"]')
    keep.focus()
    expect(keep).to_be_focused()
    page.keyboard.press("t")
    expect(thread).to_be_hidden()
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest-summary",
            "message": reply["id"],
            "text": ask("new", "keep", "drop"),
        },
    )
    told(page)
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(thread.locator("#new")).to_be_attached()
    expect(keep).to_be_focused()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_forward_to_a_decision_in_a_message_returns_to_the_decision(
    request, serve, engine
):
    """Forward to the stop where `m` put the user on the choice an agent's reply asks
    in a card puts them on that choice again, drawn in the card, not on the message
    holding it."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Every node, or the hot shards?",
        {"section": "p40", "quote": "Paragraph 40."},
    )
    append_agent_reply(
        serve.page_dir,
        root,
        "Every node. Choose which budget to take it from.",
        '<lf-group id="budget" label="Which budget pays?"><h3 id="budget-h">Which budget'
        ' pays?</h3><lf-options id="budget-pick"><lf-option id="infra">Infrastructure'
        ' reserve</lf-option><lf-option id="team">The team\'s quarter</lf-option>'
        "</lf-options></lf-group>",
    )
    page = open_page(request.getfixturevalue(engine), url)
    decision = page.locator(".lf-margin-preview lf-options#budget-pick")
    page.keyboard.press("m")
    expect(decision).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(decision).not_to_be_focused()
    page.wait_for_function("navigation.transition === null")
    page.go_forward()
    expect(decision).to_be_focused()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("change", ["age", "edit", "copy", "gone"])
def test_back_returns_words_selected_in_a_message(request, serve, engine, change):
    """Words the user selected in a card's message are selected again when Back from
    the next thread reopens the card, though the message's age in its head reads
    differently by then, as it does once a minute passes, or the agent has rewritten
    the words before them, a copy of them among those words included; where the
    rewrite took the words out, nothing is selected."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    reply = append_agent_reply(
        serve.page_dir, root, "The importer reads the cache before the scan begins."
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    words = card.get_by_text("The importer reads the cache before the scan begins.")
    words.evaluate(
        """node => {
          const text = [...node.childNodes].find((n) => n.nodeType === 3 && n.data.includes('cache'));
          const at = text.data.indexOf('the cache');
          getSelection().setBaseAndExtent(text, at, text, at + 'the cache '.length);
        }"""
    )
    if change == "age":
        words.evaluate(
            """node => {
              for (const age of node.closest('.lf-msg').querySelectorAll('time span'))
                age.textContent = '9m ago';
            }"""
        )
    page.keyboard.press("t")
    expect(card).not_to_be_attached()
    if change != "age":
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "edit",
                "author": "agent",
                "agent": "Codex",
                "session": "pytest-summary",
                "message": reply["id"],
                "text": {
                    "edit": "Extra prefix. The importer reads the cache before the scan begins.",
                    # A copy of the words where they stood before the rewrite.
                    "copy": "Elsewhere it reads the cache too. The importer reads the cache"
                    " before the scan begins.",
                    "gone": "The importer reads its files before the scan begins.",
                }[change],
            },
        )
        told(page)
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(card).to_be_attached()
    if change == "gone":
        expect(card.get_by_text("reads its files")).to_be_visible()
        assert page.evaluate("getSelection().toString()") == ""
    else:
        page.wait_for_function("() => getSelection().toString() === 'the cache '")
        # The words the user selected, not a copy of them standing where they stood.
        assert page.evaluate("""() => {
          const range = getSelection().getRangeAt(0);
          const before = document.createRange();
          before.setStart(range.startContainer.parentElement.closest('.lf-msg-body'), 0);
          before.setEnd(range.startContainer, range.startOffset);
          return before.toString();
        }""").endswith("importer reads ")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_to_a_kept_draft_stop_reopens_its_editor(request, serve, engine):
    """A `t` walk that stopped at a comment the user had put away, standing on its open
    box, is a stop Back returns to: the box opens again, holding the words, with the
    user on it."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    page = open_page(request.getfixturevalue(engine), url)
    select_words(page, "#p3")
    page.keyboard.press("c")
    composer = page.locator(".lf-composer leaf-text")
    expect(composer).to_be_focused()
    page.keyboard.type("Is this the overnight scan")
    page.keyboard.press("Escape")
    if composer.is_visible():
        page.keyboard.press("Escape")
    expect(composer).to_be_hidden()
    page.evaluate(
        "document.activeElement?.blur?.(); scrollTo({top: 0, behavior: 'instant'})"
    )
    on_box = """() => {
      const box = document.querySelector('.lf-composer leaf-text');
      const at = document.activeElement;
      return Boolean(box && at && at !== document.body &&
        (at === box || at.contains(box) || at.closest('.lf-composer')));
    }"""
    page.keyboard.press("t")
    page.wait_for_function(on_box)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    page.wait_for_function(on_box)
    expect(composer).to_have_js_property("value", "Is this the overnight scan")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_returns_to_the_message_the_user_was_on(request, serve, engine):
    """A walk that lands on a message, as the first unread one, leaves the user on that
    message, and Back from the next stop returns them to it rather than to its thread."""
    url = serve(LONG_PAGE)
    first = panel_comment(
        serve.page_dir, "Why here?", {"section": "p10", "quote": "Paragraph 10."}
    )
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": first,
            "revision": 1,
            "text": "Because the importer reads it first.",
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("g")
    page.keyboard.press("u")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-msg[data-lf-message]')"
    )
    key = page.evaluate("document.activeElement.dataset.lfMessage")
    page.keyboard.press("t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-lf-thread]')?.dataset.lfThread"
        " !== first",
        arg=first,
    )
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(page.locator(f'.lf-msg[data-lf-message="{key}"]')).to_be_focused()


def test_back_reopens_a_card_on_the_side_it_opened_on(browser, serve):
    """Back to an entry whose card a `t` walk put away opens the card again where it
    stood, above its words, once the page stands where the entry left it, rather than
    on a side chosen against the page being left, from which it covered its words."""
    url = serve(
        LONG_PAGE, anchored=[("p10", "Paragraph 10."), ("p40", "Paragraph 40.")]
    )
    page = open_page(browser, url)
    resized(page, 1400, 900)
    page.locator("#p10").evaluate(
        "p => scrollTo({top: p.getBoundingClientRect().top + scrollY - 500,"
        " behavior: 'instant'})"
    )
    scroll_settled(page)
    page.locator("leaf-margin-cluster").first.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    side = card.get_attribute("data-lf-thread-placement")
    first = card.locator(".lf-page-thread").get_attribute("data-lf-thread")
    # Out of the reply box the press left the user in, onto the thread.
    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(card.locator(".lf-page-thread")).not_to_have_attribute(
        "data-lf-thread", first
    )
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{first}"]')).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    expect(card).to_have_attribute("data-lf-thread-placement", side)


def test_a_marker_opens_a_thread_holding_a_reply_where_the_user_stands(browser, serve):
    """A press on a passage's margin marker opens its thread where the user stands, a
    view opened in place that adds no Back step, though the thread holds a reply the
    user wrote and left unsent, which the press opens it on."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3.")])
    page = open_page(browser, url)
    resized(page, 1400, 900)
    marker = page.locator("leaf-margin-cluster").first
    card = page.locator(".lf-margin-preview")
    reply = card.locator(".lf-thread-reply leaf-text")
    marker.click()
    expect(reply).to_be_focused()
    page.keyboard.type("Half a thought")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    page.wait_for_function("navigation.transition === null")
    entries = page.evaluate("history.length")
    marker.click()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Half a thought")
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("history.length") == entries


def test_escape_from_a_seated_reply_send_returns_to_its_thread(browser, serve):
    """Escape leaves a reply's whole composition row, its Send control included, onto
    the thread the reply belongs to. On a thread seated in the page's flow the page's
    let-go answered Send first, since it deferred only to a box that takes letters, so
    the press dropped the user onto the page with the draft left behind."""
    url = serve(THREAD_DIFF_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    thread = page.locator("#cd-q .lf-page-thread")
    thread.focus()
    page.keyboard.press("c")
    box = thread.locator("leaf-text")
    expect(box).to_be_focused()
    page.keyboard.type("draft")
    page.keyboard.press("Tab")
    expect(thread.locator(".lf-thread-send")).to_be_focused()
    # The Tab showed Send's preview, Escape's first step (WCAG 1.4.13).
    put_preview_away(page)
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "draft")


def test_a_click_survives_an_element_whose_id_shadows_a_dom_method(browser, serve):
    """A click's composed path ends at the document and the window, and an element with
    `id="matches"` puts itself at `window.matches`, where a reader of that path expects
    Element's method. A handoff page with a "matches" section threw on every click."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "named access",
                '<h1 id="title">Pairs</h1><h2 id="matches">A pair that matches</h2>'
                "<p id='body'>Words to click.</p>",
            )
        ),
    )
    page.locator("#matches").click()
    page.locator("#body").click()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_returns_one_of_two_like_passages_selected_in_a_message(
    request, serve, engine
):
    """Words a message says twice, among neighbours alike for a stretch on both sides,
    come back as the copy the user selected when Back reopens the card: the words told
    apart by as much of their neighbours as it takes."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    panel_comment(
        serve.page_dir, "And here?", {"section": "p40", "quote": "Paragraph 40."}
    )
    append_agent_reply(
        serve.page_dir,
        root,
        "Alpha writes: the same long phrase stands here before needle and after it."
        " Beta writes: the same long phrase stands here before needle and after it.",
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("t")
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_focused()
    card.get_by_text("Alpha writes").evaluate(
        """node => {
          const text = [...node.childNodes].find((n) => n.nodeType === 3 && n.data.includes('needle'));
          const at = text.data.lastIndexOf('needle');
          getSelection().setBaseAndExtent(text, at, text, at + 'needle'.length);
        }"""
    )
    page.keyboard.press("t")
    expect(card).not_to_be_attached()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(card).to_be_attached()
    page.wait_for_function("() => getSelection().toString() === 'needle'")
    assert "Beta writes" in page.evaluate("""() => {
      const range = getSelection().getRangeAt(0);
      const before = document.createRange();
      before.setStart(range.startContainer.parentElement.closest('.lf-msg-body'), 0);
      before.setEnd(range.startContainer, range.startOffset);
      return before.toString();
    }""")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_card_reopened_on_its_thread_draws_the_decision_it_closed_on(
    request, serve, engine
):
    """A card closed while `m` had the user on the choice an agent's reply asks, then
    opened on that thread again by `m`, draws the choice and puts the user on it."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Every node, or the hot shards?",
        {"section": "p40", "quote": "Paragraph 40."},
    )
    append_agent_reply(
        serve.page_dir,
        root,
        "Every node. Choose which budget to take it from.",
        '<lf-group id="budget" label="Which budget pays?"><h3 id="budget-h">Which budget'
        ' pays?</h3><lf-options id="budget-pick"><lf-option id="infra">Infrastructure'
        ' reserve</lf-option><lf-option id="team">The team\'s quarter</lf-option>'
        "</lf-options></lf-group>",
    )
    page = open_page(request.getfixturevalue(engine), url)
    decision = page.locator(".lf-margin-preview lf-options#budget-pick")
    page.keyboard.press("m")
    expect(decision).to_be_focused()
    page.keyboard.press("Escape")
    expect(decision).not_to_be_visible()
    page.keyboard.press("m")
    expect(decision).to_be_focused()
