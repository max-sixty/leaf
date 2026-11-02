"""Widgets in threads: a widget an agent's message carries, a thread seated in or
anchored on a widget, an edited agent message, and the composer that writes a
comment."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    MESSAGE_ROOM_PAGE,
    ROOM_HELD,
    ROOM_WIDGETS,
    ROOMS,
    THREAD_DIFF_PAGE,
    live_url,
)
from render_harness import (
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    REPLY_HOST_PAGE,
    compare_with,
    open_page,
    page_comment,
    resized,
    select,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_composer_grows_caps_and_shrinks_with_its_text(browser, serve):
    """The comment box fits its content, scrolls at its cap, and shrinks back."""
    page = open_page(browser, serve(LONG_PAGE))
    box = page_comment(page)

    def state():
        return box.evaluate("""ta => ({ h: Math.round(ta.getBoundingClientRect().height),
                                        scrollable: ta.scrollHeight > ta.clientHeight })""")

    empty = state()
    box.type("A comment long enough to wrap onto a second line and then a third. " * 2)
    grown = state()
    write(box, "x " * 4000)  # far past the ceiling
    capped = state()
    panel_bottom = page.locator(PANEL).evaluate(
        "panel => panel.getBoundingClientRect().bottom"
    )
    write(box, "short again")
    shrunk = state()

    assert grown["h"] > empty["h"], "the box must grow with its content"
    assert not grown["scrollable"], "a box that fits its text must not be scrollable"
    # The field grows up from the panel's row, and the editor caps inside the window.
    assert capped["h"] > grown["h"], "the box must grow toward the field's room"
    assert panel_bottom <= page.viewport_size["height"] + 0.5, (
        f"the capped box carried the panel out of the window, to {panel_bottom}px"
    )
    assert capped["scrollable"], (
        "past the ceiling the scrollbar is real and belongs there"
    )
    assert shrunk["h"] == empty["h"], "and it must shrink back"


def test_a_widget_a_message_carries_holds_the_room_its_words_will_need(browser, serve):
    """A measurement is a measurement wherever the widget was built, or it is a zero.

    The shipped board takes a number off a live box at upgrade — the room a card keeps
    clear of its grip — because a constant goes stale in the next face. A widget
    upgrades wherever the runtime connects it, and one of those places is a message body
    inside a thread view nobody has opened: `display: none`, so every box under it is
    zero. `once` then refuses the second upgrade that would put it right and the body is
    cached for the life of the tab, so the zero is permanent.

    The reply is in the log before the page loads and the panel is shut, which is the
    only reading arrangement that reproduces it: a reply arriving into an open panel upgrades
    into boxes and was always right. Rooms are compared rather than named, because the
    number is the face's and this is about whether it was ever read.

    The board exercises `measure` through the same module in both places."""
    url = serve(MESSAGE_ROOM_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-room",
            "author": "user",
            "revision": 1,
            "text": "Anything else worth adding?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-room",
            "revision": 1,
            "text": "These, and who is on them:",
            "markup": ROOM_WIDGETS.format(id="mr-msg"),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    held = {}
    for suffix, prop in ROOMS:
        held[suffix] = page.evaluate(ROOM_HELD, [f"mr-page{suffix}", prop])
        # Against a page that stopped reserving anything, where this would pass on both
        # sides reading the same nothing.
        assert held[suffix] not in ("0px", "", None), (suffix, prop, held)

    open_panel_thread(page, "c-room")
    expect(page.locator("#mr-msg-b")).to_be_visible()
    # The re-measure is delivered with the layout that gave these their boxes, so the
    # reading waits for the rendering it queued to settle.
    rendered(page)
    for suffix, prop in ROOMS:
        assert page.evaluate(ROOM_HELD, [f"mr-msg{suffix}", prop]) == held[suffix], (
            suffix,
            prop,
        )


def test_a_drag_across_an_obligation_in_a_reply_is_not_a_passage_of_the_page(
    browser, serve
):
    """A selection made in the panel is not the page's words, whatever it looks like.

    `leaf thread create --section` refuses to anchor on a widget an agent sent, and it is the
    reading that is supposed to promise less than the browser's. The browser offered
    the 💬 over a question in a reply and wrote an anchor onto that widget's own id into
    an append-only log — naming a section no version holds, so it could never paint and
    never be found again.

    A declared label is the hole it came through: it is the page speaking inside the
    control it labels, so it answers the "are these the runtime's words" question for
    itself and the panel above it never got asked. That question was standing in for a
    second one nobody was putting — which document is this — and the drag needs both.

    The same drag on the page's own prose comes first and must raise the button. It is
    the control: this asserts an absence, and an absence proves nothing on a page where
    nothing was ever going to appear. The drags are real ones, so the mouseup guard is
    under test with the button.

    Then two turns of the macrotask queue, because the handler raises the button from a
    bare `setTimeout` — asserting straight after the drag reads the frame before the
    decision and passes whatever the decision would have been."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-store",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-store",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    def drag(locator):
        expect(locator).to_be_visible()
        box = locator.bounding_box()
        y = box["y"] + box["height"] / 2
        select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
        return page.evaluate("() => getSelection().toString()")

    # The control, taken with the panel's view still shut, so it covers none of these
    # words: the same gesture on the page's own words raises the button here.
    intro = page.locator("#intro")
    box = intro.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    expect(page.locator("#lf-composer-quote")).to_contain_text("signed-cookie")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    # Put it down again, so what follows is a rise and not a leftover.
    page.locator("#h").click()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    open_panel_thread(page, "c-store")
    assert "Which store" in drag(page.locator("#ps-decision-region > h3"))
    # Both turns the handler could have used: it defers with a bare setTimeout, and the
    # step it queues queues nothing further.
    for _ in range(2):
        page.evaluate("() => new Promise((r) => setTimeout(r))")
    expect(page.locator(".lf-fab-input")).to_be_hidden()


def test_a_thread_seated_in_a_widget_is_not_a_change_to_the_document(browser, serve):
    """What a user and an agent said to each other is not something the page changed.

    A widget declaring x-thread-seat grows a seat on the page, and the layer fills it
    from the log — messages the runtime built, wearing `.lf-ui` and `data-lf-gen`, and
    standing inside the widget out in `<main>`. The version diff walks every block the
    page holds and keys each by `wrote`, which is exactly the reading that leaves
    generated words out, so those blocks key to nothing and are skipped.

    They stopped being skipped when `wrote` was bounded at the element handed in: a
    reading can start *inside* generated chrome, and rooted at one of those `<p>`s the
    box above it was no longer over the reading. The base version is parsed unupgraded
    and holds no thread at all, so every message became an insertion — the
    user's own comment and the agent's reply painted as changes to the document, and
    the count in the version note inflated by both.

    The bound is the widget the reading belongs to now, and a thread seat is
    inside its widget, so the box is between the words and their frame either way."""
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "cd-thread",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "cd-thread",
            "revision": 1,
            "text": "It does, with the wider plate.",
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    # The seat is filled before the diff runs, or this asserts over a page that never
    # had the blocks in question.
    expect(page.locator("#cd-q .lf-msg")).to_have_count(2)

    stamp_page(
        d,
        THREAD_DIFF_PAGE.replace(
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>',
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>\n'
            '<p id="cd-new">The north pair waits on brackets.</p>',
        ),
        "two",
    )
    wait_for_revision(page, 2)
    expect(page.locator("#cd-q .lf-msg")).to_have_count(2)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map((e) => e.id)"
    ) == ["cd-new"], "the diff read the thread as words the base version lacked"


def test_an_agent_message_edit_updates_the_panel_and_its_inline_thread(browser, serve):
    """The edit is one log arrival and both views fold it onto the original message.

    Neither view gains a second message. Their existing message nodes survive the
    arrival, so an edit cannot disturb a user working elsewhere in the same thread;
    only the prose inside changes, and both heads disclose that it changed.
    """
    url = serve(THREAD_DIFF_PAGE)
    d = serve.page_dir
    message = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "edited-agent-message",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "revision": 1,
            "text": "The north bracket fit.",
            "anchor": {"section": "cd-q"},
            "markup": (
                '<lf-options id="edited-message-choice" choose>'
                '<lf-option id="edited-message-now">Fit it now</lf-option>'
                "</lf-options>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-msg[data-event="{message["id"]}"]')
    expect(inline.locator(".lf-msg-text")).to_have_text("The north bracket fit.")
    panel_thread = open_panel_thread(page, "edited-agent-message")
    panel = panel_thread.locator(f'.lf-msg[data-event="{message["id"]}"]')
    expect(panel.locator(".lf-msg-text")).to_have_text("The north bracket fit.")
    page.evaluate(
        """([message]) => {
          window.__editedInline = document.querySelector(
            `#cd-q .lf-msg[data-event="${message}"]`);
          window.__editedPanel = document.querySelector(
            `.lf-fp-view .lf-msg[data-event="${message}"]`);
          window.__editedWidget = document.querySelector('#edited-message-choice');
        }""",
        [message["id"]],
    )

    revision = append_carried_log_record(
        d,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "message": message["id"],
            "text": (
                "The north bracket fits.\n\n"
                "```python\n"
                "def fitted():\n"
                "    return True\n"
                "```"
            ),
        },
    )
    told(page)
    # Revealing the edit in either view settles the thread's shared unread state.
    page.locator(".lf-fp-head").get_by_role(
        "button", name="1 message edited", exact=True
    ).click()

    expect(inline.locator(".lf-msg-body")).to_contain_text("The north bracket fits.")
    expect(panel.locator(".lf-msg-text")).to_contain_text("The north bracket fits.")
    expect(panel.locator("pre code [data-lf-syn]").first).to_have_text("def")
    # Editing updates the original message's disclosure in both views.
    expect(inline.locator(":scope > .lf-msg-head .lf-edited")).to_have_text("edited")
    expect(panel.locator(":scope > .lf-msg-head .lf-edited")).to_have_text("edited")
    expect(page.locator(f'.lf-msg[data-event="{revision["id"]}"]')).to_have_count(0)
    assert page.evaluate(
        f"""() => window.__editedInline === document.querySelector(
          '#cd-q .lf-msg[data-event="{message["id"]}"]')
          && window.__editedPanel === document.querySelector(
            '.lf-fp-view .lf-msg[data-event="{message["id"]}"]')
          && window.__editedWidget === document.querySelector('#edited-message-choice')"""
    ), "the edit replaced an existing message or its frozen widget"
    assert (
        next(
            event
            for event in events_model.read_events(d)
            if event["id"] == message["id"]
        )["text"]
        == "The north bracket fit."
    )


def thread_on_a_sent_widget(serve):
    """Serve a page whose thread `c-sent` has an agent's reply carrying a widget,
    `ps-decision-region`, and a second thread, `c-on-sent`, anchored on that widget."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-sent",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-sent",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    # The shape design mode writes: an element anchor naming a widget no version holds.
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-on-sent",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": "ps-decision-region"},
        },
    )
    return url


def test_a_detached_thread_on_a_widget_an_agent_sent_stays_detached(browser, serve):
    """An anchor captured detached names no passage the user selected, so finding the
    widget its section names in a message identifies nothing: the thread still reads as
    detached, with no Show in message to offer."""
    url = thread_on_a_sent_widget(serve)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-lost",
            "author": "user",
            "revision": 1,
            "text": "This bit, whatever it was.",
            "anchor": {"section": "ps-decision-region", "detached": True},
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = open_panel_thread(page, "c-lost")
    expect(thread.locator(".lf-fp-quote")).to_have_class(re.compile(r"\bdetached\b"))
    expect(
        page.locator(".lf-fp-aux").get_by_role("button", name="Show in message")
    ).to_have_count(0)


def test_a_thread_on_a_widget_an_agent_sent_names_it_and_stands_apart(browser, serve):
    """A question the agent asked is not one of the runtime's own buttons.

    Design mode lets a user comment on anything the layer draws, so a thread can be
    anchored on a widget that arrived in a reply. Two things were then said about it and
    both were wrong. The panel filed it under "The page's own layer", which groups the
    agent's question with the composer and the version picker — the layer's parts wear
    the runtime's id namespace, which authored markup may not take, and that is what
    tells one from the other. And the thread's label read `§ ps-decision`, the bare id.

    The label is the part with the mechanism worth naming. An element anchor is labelled
    with its element's opening words, read when the node is built — and on the reconcile
    that first builds this node, the message body carrying the widget has not been
    connected yet, so the element did not exist and the reading came back empty. A node the
    reconcile keeps is never built again, so nothing asked a second time. It is repainted
    with the quote now, which is the pass that already exists for records whose subject
    the reconcile has just written."""
    url = thread_on_a_sent_widget(serve)
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = open_panel_thread(page, "c-on-sent")
    label = thread.locator(".lf-fp-quote").inner_text()
    assert "Which store should I write up?" in label, label
    assert "ps-decision-region" not in label, label


def test_a_thread_on_a_widget_an_agent_sent_stands_in_its_message(browser, serve):
    """A thread about a widget an agent sent stands in the message that carried it.

    The panel draws a message's widgets only while it has their thread open, and anchor
    placement looked for the widget only among the nodes the page held, so whenever that
    thread was closed the thread about the widget read as detached ("can't be
    identified") and had no way to what it was about. Placement now finds the widget in
    the message that keeps it: the head quotes it as found, and Show in message opens the
    message's thread on the widget and lands there."""
    url = thread_on_a_sent_widget(serve)
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = open_panel_thread(page, "c-on-sent")
    quote = thread.locator(".lf-fp-quote")
    expect(quote).to_contain_text("Which store should I write up?")
    expect(quote).not_to_have_class(re.compile(r"\bdetached\b"))

    page.locator(".lf-fp-aux").get_by_role(
        "button", name="Show in message", exact=True
    ).click()
    held = page.locator(f'{PANEL_THREAD}[data-thread="c-sent"]')
    expect(held).to_be_visible()
    widget = held.locator("#ps-decision-region")
    expect(widget).to_be_in_viewport()
    expect(widget).to_be_focused()
