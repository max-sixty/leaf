"""The floating panel: Leaf's one chrome, a box over the page's foot.

Each test is one journey a user takes through the panel: writing a page comment and replying in the same field, settling the thread, finding
threads and taking in news, answering obligations, travelling between versions, and
folding the panel to the leaf in the window's corner and back."""

import base64
import json
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare_idle,
    declare_work,
    record_claim,
    working,
)
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    live_url,
    panel_comment,
)
from render_cases_layout import page_at_rest, solid_png
from render_cases_navigation import UNDO_PAGE
from render_cases_widgets import PAGE_DECLARATION, PAGE_WIDGET
from render_harness import (
    EDITOR_ROOTS,
    FAKE_RECOGNITION,
    LONG_PAGE,
    PREVIEW,
    accessible_tree,
    clocked,
    close_panel_menu,
    consume_browser_errors,
    expect_panel_says,
    expect_preview_words,
    field_press,
    holding,
    http_error_console,
    open_page,
    open_threads,
    over_plain_http,
    panel_control,
    panel_menu,
    panel_settled,
    panel_view,
    preview_parts,
    preview_text,
    resized,
    rgb_pixels,
    round_trip,
    scroll_settled,
    select_words,
    sending,
    show_done,
    show_resolved,
    stamp_page,
    tab_onto,
    told,
    undo,
    wait_for_revision,
    watched,
    without_end_room,
    write,
)
from render_harness import leaf_page as titled_page

from browser.threads import dispatch_paste, paste_image
from leaf.agents import thread as thread_model
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.log import interaction_log as interaction_model
from leaf.records import transaction as transaction_model
from leaf.source.render_checks import one_frame, rendered, wait_until_ready
from leaf_dev import browser as dev_browser
from leaf_dev.browser import choose_threads_in_panel, open_on_me, panel_tab
from leaf_dev.panel_paint import ROUTES, ink_box, mark_colours, near, settled
from leaf_dev.rings import ring_faults, rings_drawn

OBLIGATION_PAGE = leaf_page(
    "obligation",
    """<h1 id="t">Ask</h1>
<lf-group id="schema-decision" label="How should the schema migrate?"><h3 id="schema-decision-h">How should the schema migrate?</h3>
<lf-options id="schema">
  <lf-option id="shim" label="Shim the old schema"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="stage" label="Migrate in stages"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options></lf-group>
<lf-group id="queue-decision" label="Which queue takes the retries?"><h3 id="queue-decision-h">Which queue takes the retries?</h3>
<lf-options id="queues">
  <lf-option id="fast" label="The fast queue"><strong>The fast queue</strong> Shared.</lf-option>
  <lf-option id="slow" label="The slow queue"><strong>The slow queue</strong> Its own.</lf-option>
</lf-options></lf-group>""",
)


def floating(browser, url):
    page = open_page(browser, url)
    expect(page.locator(".lf-floating-panel")).to_be_visible()
    return page


def field(page):
    """The editor standing in the panel's field now: the page's, or a thread's."""
    return page.locator(".lf-fp-field leaf-text")


def lead(page):
    """What stands before an open thread's reply in the field: whose turn it is, then a
    walk's position."""
    return page.locator(".lf-fp-field .lf-compose-placeholder-lead")


def test_one_field_starts_a_thread_takes_its_reply_and_settles_it(browser, serve):
    """The field clicked at rest is the field written in. Sending a page comment opens
    its new thread above the row and leaves the user on it, the same field now holding
    its reply, which `c` enters, and resolving the thread from its controls moves the
    user on to Threads, and ⌘Z takes them back to the thread, open again. The field
    says its word, Reply over the thread, whose name says which, and the key that
    enters it until it is focused. Escape, once the caret has left the field, puts the
    thread away."""
    page = floating(browser, serve(LONG_PAGE))
    write(field(page), "Could the rollback cover the weekend?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comment = events_model.read_events(serve.page_dir)[-1]
    assert (comment["kind"], comment["text"]) == (
        "comment",
        "Could the rollback cover the weekend?",
    )
    expect(page.locator(panel_view("thread"))).to_contain_text(
        "Could the rollback cover the weekend?"
    )
    expect(page.locator(panel_view("thread"))).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Reply… c"))
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Reply… ⏎"))

    write(field(page), "And the mobile cohort too.")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"]) == ("reply", comment["id"])
    # The reply the user just sent stands in the thread's view, which grew room for it.
    page.wait_for_function(
        """() => {
            const view = document.querySelector('.lf-fp-view[data-lf-route=thread]');
            const sent = [...view.querySelectorAll('.lf-msg')].find(m =>
                m.textContent.includes('And the mobile cohort too.'));
            if (!sent) return false;
            const v = view.getBoundingClientRect(), r = sent.getBoundingClientRect();
            return r.top >= v.top - 1 && r.bottom <= v.bottom + 1;
        }"""
    )
    # The box empties as the reply leaves, and the view's ✕ ends its head line.
    expect(page.locator(".lf-fp-field .lf-compose-submit")).to_be_hidden()
    expect(page.locator(".lf-fp-head .lf-fp-close")).to_be_visible()

    settle = page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
    with sending(page, "the resolve"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    # Resolving moves the user on: with no other thread open, back to Threads.
    expect(page.locator(panel_view("threads"))).to_be_visible()
    undo(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(page.locator(panel_view("thread"))).to_be_focused()
    expect(page.locator(panel_view("thread"))).to_have_attribute(
        "data-lf-thread", comment["id"]
    )
    expect(settle).to_have_accessible_name("Resolve thread")

    field(page).focus()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)


def test_escape_leaves_the_field_before_it_puts_a_view_away(browser, serve):
    """The caret in the field is the innermost thing open, so the first Escape takes it
    out of the field and leaves the view and the draft standing: a reply returns to its
    thread, the page's field to the leaf. The next Escape puts the view away. The field
    never swaps its editor under a caret, so words typed after an Escape never go
    somewhere the user did not choose."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    expect(thread).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
    page.keyboard.press("Escape")
    expect(thread).to_be_visible()
    expect(thread).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    # Putting the view away returns the user to the page.
    assert page.evaluate(
        "() => !document.querySelector('.lf-floating-panel').contains(document.activeElement)"
    )

    # A view a pointer opens names its keys as one a key opens does: the field its
    # Escape, and Threads its `/`.
    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    expect(inventory).to_be_visible()
    expect(page.locator(".lf-fp-editors")).to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )
    expect(page.locator(".lf-fp-opened")).to_have_attribute("aria-keyshortcuts", "/")
    field(page).click()
    page.keyboard.press("Escape")
    expect(inventory).to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(page.locator(".lf-fp-leaf")).not_to_be_focused()
    expect(page.locator(".lf-fp-editors")).not_to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )


def test_a_send_moves_the_panel_s_view_as_one_stream(browser, serve):
    """A send slides what the view shows up as one stream: the thread's name and every
    turn start the same distance below where they come to rest, whether the send opens
    the thread's view or adds a turn to it, so nothing the reader reads overtakes or
    swaps with anything else. Read at the motion's first frame, held, and again at
    rest."""
    page = floating(browser, serve(LONG_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    title = ".lf-fp-title"
    turns = ".lf-fp-view[data-lf-route=thread] .lf-msg"

    def offsets(count):
        """How far below its rest each of the name and the turns is drawn now."""
        page.wait_for_function(
            f"document.querySelectorAll('{turns}').length === {count}"
        )
        rendered(page)
        drawn = page.evaluate(
            """([title, turns]) => [title, ...document.querySelectorAll(turns)]
                .map(node => typeof node === 'string' ? document.querySelector(node) : node)
                .map(node => node.getBoundingClientRect().top)""",
            [title, turns],
        )
        page.evaluate(
            "() => window.__lfHeld.splice(0).forEach(motion => motion.finish())"
        )
        settled(page)
        rest = page.evaluate(
            """([title, turns]) => [document.querySelector(title),
                ...document.querySelectorAll(turns)]
                .map(node => node.getBoundingClientRect().top)""",
            [title, turns],
        )
        return [d - r for d, r in zip(drawn, rest, strict=True)]

    page.evaluate("() => {" + HOLD_MOTION + "}")
    write(field(page), "Could the rollback cover the weekend?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    opened = offsets(1)
    assert opened[0] > 10, f"the view opened in place: {opened}"
    assert max(opened) - min(opened) < 1, f"the opening view came apart: {opened}"

    write(field(page), "And the mobile cohort too.")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    replied = offsets(2)
    assert replied[0] > 10, f"the view grew in place: {replied}"
    assert max(replied) - min(replied) < 1, f"the stream came apart: {replied}"


def test_a_send_into_a_full_thread_view_starts_where_the_view_stood(browser, serve):
    """A two-line reply sent into a thread whose view is at its cap empties the field,
    which lowers the box's top, while the view scrolls to the new turn. At the motion's
    first frame the thread's name and every turn stand where they stood: the turns ride
    inside the view while the view itself is carried with the box's top, and neither
    carry counts the other's distance."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    for turn in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 == 0 else "user",
                **({"agent": "Claude"} if turn % 2 == 0 else {}),
                "parent": root,
                "revision": 1,
                "text": f"Turn {turn}. "
                + "Forty-eight hours covers the first cohort. " * 6,
            },
        )
    page = floating(browser, url)
    page.emulate_media(reduced_motion="no-preference")
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view).to_be_visible()
    assert view.evaluate("box => box.scrollHeight > box.clientHeight + 100")
    write(field(page), "And the mobile cohort too.\nAnd the weekend shift.")
    settled(page)
    read = """() => [document.querySelector('.lf-fp-title'),
        ...document.querySelectorAll('.lf-fp-view[data-lf-route=thread] .lf-msg')]
        .map(node => node.getBoundingClientRect().top)"""
    stood = page.evaluate(read)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function(
        "n => document.querySelectorAll('.lf-fp-view[data-lf-route=thread] .lf-msg').length"
        " === n",
        arg=len(stood),
    )
    rendered(page)
    drawn = page.evaluate(read)
    # A reading later in the send's rendering, as the user's landing on the view takes,
    # cancels the motion it carries on from; only the motions still running finish.
    page.evaluate(
        "() => window.__lfHeld.splice(0)"
        ".filter(motion => motion.playState !== 'idle')"
        ".forEach(motion => motion.finish())"
    )
    settled(page)
    assert drawn[: len(stood)] == pytest.approx(stood, abs=1), (stood, drawn)


def test_a_reaction_in_the_view_stands_as_its_chip_alone(browser, serve):
    """A reaction to the agent's reply shows once in the thread's view, as the pressed
    chip on the reply, as a card in Threads draws it: before the server answers and
    after, the view draws no message of its own for it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "Forty-eight hours covers the first cohort.",
        },
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    reply = thread.locator(".lf-msg[data-lf-author=agent]")
    reply.click()
    page.keyboard.press("e")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the reaction")
    pressed = reply.locator(".lf-react[aria-pressed=true]")
    expect(pressed).to_have_count(1)
    expect(thread.locator(".lf-msg")).to_have_count(2)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["emoji"]
    expect(pressed).to_have_count(1)
    expect(thread.locator(".lf-msg")).to_have_count(2)


def test_resolving_a_thread_from_threads_moves_on_to_the_next(browser, serve):
    """Resolving the thread open from Threads moves the user on to the next open
    thread, focused on its view, so a second `r` resolves that one, while the row says
    which thread was resolved, by name, beside the press that matters most next: the
    next open thread, with `t`, while one stands open, and once none does, the Undo
    that takes the Resolve back. A bare "Resolved the thread" would read as the thread
    now open. ⌘Z returns the user to the thread they resolved; with none left, the
    user is back at Threads and the field says that every thread is resolved. Escape
    there puts the view away and returns the user to the page."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    panel_comment(serve.page_dir, "Should the mobile cohort wait?")
    page = floating(browser, url)
    open_threads(page)
    page.locator(f"{panel_view('threads')} .lf-fp-thread").first.click()
    # The currently open thread: moving on to the next thread fades the one it leaves.
    thread = page.locator(panel_view("thread"))
    expect(thread).to_be_visible()
    first = page.locator(".lf-fp-head .lf-fp-title").inner_text()
    thread.focus()
    with sending(page, "the first resolve"):
        page.keyboard.press("r")
    expect(page.locator(".lf-fp-head .lf-fp-title")).not_to_have_text(first)
    expect(thread).to_be_visible()
    expect(thread).to_be_focused()
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )
    # The field says what was resolved, and its end the next open thread and its key,
    # where Comment or Reply and c stand at rest.
    hint = page.locator(".lf-fp-field .lf-compose-placeholder")
    expect(hint.locator(".lf-compose-placeholder-words")).to_have_text(
        f"Resolved “{first}”"
    )
    press = field_press(page)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next thread")
    expect(press.locator("kbd")).to_have_text("t")
    # A screen reader finds the field's one textbox empty, since its words are its
    # placeholder, and the press as a button beside that textbox rather than in it.
    field = accessible_tree(page.locator(".lf-fp-field leaf-text"))

    def within(node):
        for child in node["children"]:
            yield child
            yield from within(child)

    nodes = [field, *within(field)]
    [textbox] = [node for node in nodes if node["role"] == "textbox"]
    assert not textbox["value"].strip(), field
    assert "button" not in {node["role"] for node in within(textbox)}, field
    [button] = [node for node in nodes if node["role"] == "button"]
    assert button["name"].startswith("Next thread"), field
    second = page.locator(".lf-fp-head .lf-fp-title").inner_text()
    # Taking the first resolve back returns the user to the thread they resolved.
    undo(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(first)
    expect(thread).to_be_focused()
    with sending(page, "the second resolve"):
        page.keyboard.press("r")
    resolved = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "resolve"
    ]
    assert len(resolved) == 2
    # The second thread is the one open thread left, so the user moves to it.
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(second)
    with sending(page, "the last resolve"):
        page.keyboard.press("r")
    threads = page.locator(panel_view("threads"))
    expect(threads).to_be_visible()
    # The field marks the moment, in Threads' own words.
    expect(hint.locator(".lf-compose-placeholder-words")).to_have_text(
        "All threads resolved"
    )
    # The user stands on the list itself, and nothing in it wears a ring: its only row
    # is the folded Resolved, whose heading is no landing.
    expect(threads).to_be_focused()
    assert rings_drawn(page) == []
    # With no open thread left, the press takes the Resolve back.
    expect(press.locator(".lf-compose-press-word")).to_have_text("Undo")
    # The platform spells undo's chord: ⌘z on a Mac, Ctrl+z elsewhere.
    expect(press.locator("kbd")).to_have_text(re.compile(r"^(⌘z|Ctrl\+z)$"))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(page.locator(".lf-fp-leaf")).not_to_be_focused()


def test_a_resolve_s_notice_stands_for_that_resolve_alone(browser, serve):
    """The row's notice of a Resolve and its press name one gesture. A Resolve that
    leaves no thread open says so and, once the log has it, offers the Undo that takes
    it back. The log refusing that Resolve takes the notice away with it. The agent
    picking that Resolve up leaves the Undo standing, and once another gesture of the
    user's is the newest, the one ⌘Z would take, the notice keeps its words and offers
    no Undo: a press showing ⌘Z does what ⌘Z does."""
    url = serve(LONG_PAGE)
    roots = {
        text: panel_comment(serve.page_dir, text)
        for text in (
            "Is the window long enough?",
            "Should the mobile cohort wait?",
            "Who signs off the rollout?",
        )
    }
    # The user has resolved two of them already, so the third is the one left open.
    first, *others = roots
    for other in others:
        append_carried_log_record(
            serve.page_dir,
            {"kind": "resolve", "author": "user", "parent": roots[other]},
        )
    page = floating(browser, url)
    open_threads(page)
    page.locator(f"{panel_view('threads')} .lf-fp-thread").first.click()
    thread = page.locator(panel_view("thread"))
    title = page.locator(".lf-fp-head .lf-fp-title")
    expect(thread).to_be_visible()
    expect(title).to_have_text(first)
    said = page.locator(".lf-fp-field .lf-compose-placeholder-words")
    undo = field_press(page)

    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json.get("kind") == "resolve"
            else route.continue_()
        ),
    )
    thread.focus()
    page.keyboard.press("r")
    holding(page, held, 1, "the resolve")
    # ⌘Z takes back no gesture still on its way to the log, so the field's end offers
    # Undo only once the log has the Resolve.
    expect(field(page)).to_have_attribute("placeholder", "All threads resolved")
    expect(undo).to_have_count(0)
    # The refusal arrives as news once the Resolve's motion has ended, which can be
    # well after its rendering settles. Its thread rejoins Open in the Threads view as
    # that view leaves for the thread, which carries the Resolved heading under it
    # down: the one move the refusal makes without input, inside the panel
    # (browser/AGENTS.md, "The page holds still under the user's aim", allows a rare
    # path that move).
    page_at_rest(page)
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.unroute("**/api/event")
    expect(title).to_have_text(first)
    expect(undo).to_have_count(0)
    rendered(page)
    consume_browser_errors(
        page, {"code": "moved-without-input", "node": ["button.lf-fp-settled"]}
    )

    thread.focus()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    expect(said).to_have_text("All threads resolved")
    expect(undo).to_contain_text("Undo")
    # The agent picks that Resolve up, and the notice still offers to take it back.
    (resolved,) = (
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve" and event["parent"] == roots[first]
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "events": [resolved],
            "phase": "opened",
            "session": "s1",
            "turn": "t1",
        },
    )
    told(page)
    expect(undo).to_contain_text("Undo")
    # Another tab of the user's reopens one of the others, so ⌘Z would take that.
    append_carried_log_record(
        serve.page_dir,
        {"kind": "unresolve", "author": "user", "parent": roots[others[0]]},
    )
    told(page)
    expect(undo).to_have_count(0)
    expect(said).to_have_text("All threads resolved")


def test_resolve_opens_the_next_thread_as_tall_as_it_holds(browser, serve):
    """The next thread Resolve opens is a view of its own, as tall as what it holds, by
    a press on ✓ and by `r` alike: a longer one grows the view to show it whole and a
    shorter one shrinks it, its ✓ standing where that height puts it. Opening at the
    height the resolved one stood at, so ✓ stayed under the pointer, would show a
    longer thread cut off behind a scroll until the user's next turn. Each thread holds
    a reply the user reads as it opens, which gives the reading a new record of the
    thread: Resolve must not go back to Threads there, its thread no longer found among
    the open ones."""
    url = serve(LONG_PAGE)
    roots = [
        panel_comment(serve.page_dir, "Is the window long enough?"),
        panel_comment(
            serve.page_dir,
            "Should the mobile cohort wait? " * 12
            + "\n\nThe last release took a week to reach it, and the one before took two.",
        ),
        panel_comment(serve.page_dir, "Who watches the weekend?"),
    ]
    for root in roots:
        agent_said(serve.page_dir, root, "Noted.")
    page = floating(browser, url)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Is the window long enough?").click()
    title = page.locator(".lf-fp-head .lf-fp-title")
    expect(title).to_have_text("Is the window long enough?")
    thread = page.locator(panel_view("thread"))
    settle = page.locator(".lf-fp-head .lf-resolve")
    fits = "(view) => view.scrollHeight - view.clientHeight < 1"
    settled(page)
    short = thread.bounding_box()["height"]
    with sending(page, "the resolve"):
        settle.click()
    expect(title).to_contain_text("Should the mobile cohort wait?")
    settled(page)
    assert thread.evaluate(fits)
    assert thread.bounding_box()["height"] > short
    expect(thread).to_be_focused()
    with sending(page, "the second resolve"):
        page.keyboard.press("r")
    expect(title).to_have_text("Who watches the weekend?")
    settled(page)
    assert thread.evaluate(fits)
    assert thread.bounding_box()["height"] == short


def test_the_field_is_the_thread_s_reply_box(browser, serve):
    """The field a thread opens with is that thread's reply box, as a card's is: a rewrite
    ↑ opens from it is a rung below it, so Escape hands the caret back to the field,
    and Save leaves the user on the thread's view, as a send does; one opened on the
    message itself returns to its Edit control instead. ↑ from the
    empty field opens the rewrite of the user's last message, and ↑ from the start of
    an unchanged rewrite the message before. Resolve leaves the reply as a card's does,
    and the field says how to reopen the thread."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    for author, text in [
        ("agent", "Forty-eight hours covers the first cohort."),
        ("user", "What about the second cohort?"),
    ]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": author,
                **({"agent": "Claude"} if author == "agent" else {}),
                "parent": root,
                "revision": 1,
                "text": text,
            },
        )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    expect(thread).to_be_visible()
    rewrite = thread.locator(".lf-msg-editor leaf-text")

    # A rewrite opened on the message itself returns to the message's Edit control.
    second = thread.locator(".lf-msg", has_text="What about the second cohort?")
    second.locator(".lf-msg-body").dblclick()
    expect(rewrite).to_be_focused()
    page.keyboard.press("Escape")
    expect(rewrite).to_have_count(0)
    expect(second.locator(".lf-msg-edit")).to_be_focused()

    field(page).focus()
    page.keyboard.press("ArrowUp")
    expect(rewrite).to_be_focused()
    expect(rewrite).to_have_js_property("value", "What about the second cohort?")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowUp")
    expect(rewrite).to_be_focused()
    expect(rewrite).to_have_js_property("value", "Is the window long enough?")
    page.keyboard.press("Escape")
    expect(rewrite).to_have_count(0)
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")

    page.keyboard.press("ArrowUp")
    page.keyboard.press("End")
    page.keyboard.type(" And the third?")
    with sending(page, "the rewrite"):
        page.keyboard.press("Enter")
    edit = events_model.read_events(serve.page_dir)[-1]
    assert (edit["kind"], edit["text"]) == (
        "edit",
        "What about the second cohort? And the third?",
    )
    expect(thread).to_be_focused()

    page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)").focus()
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    expect(field(page)).to_have_attribute("name", "comment")


def test_a_notice_over_a_thread_s_field_ends_in_reply_and_its_key(browser, serve):
    """A notice offering no press of its own passes over an open thread's field as it
    does over the page's: its words, then Reply and the key that enters the field, as
    the page's field says Comment, rather than the key alone after the notice."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    expect(thread).to_be_visible()
    thread.focus()
    placeholder = page.locator(".lf-fp-field .lf-compose-placeholder")
    words = placeholder.locator(".lf-compose-placeholder-words")
    enters = placeholder.locator(".lf-compose-placeholder-enters")
    expect(words).to_have_text("")
    expect(enters).to_have_text("Reply…")
    page.keyboard.press("n")
    expect(words).to_have_text("No search to repeat")
    expect(enters).to_have_text("Reply…")
    expect(placeholder.locator(".lf-key-badge")).to_have_text("c")


def test_a_stance_entered_from_a_thread_owns_the_row_and_escape_ends_it_first(
    browser, serve
):
    """A stance entered while a thread stands open in the panel owns the row: its ✕
    takes the seat, the field's mode chip names it in a word right beside that ✕, as a
    search's chip names its scope, and the reply box takes no words, offering neither
    Reply nor its key; whose turn it is stays beside the leaf. Escape ends the stance
    before the thread, since it came last, and the ✕ ends it too, leaving the thread
    open with its Reply back."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    expect(thread).to_be_visible()
    thread.focus()
    page.keyboard.press("w")
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    name = page.locator(".lf-fp-mode")
    expect(name).to_have_text("Draw")
    expect(field(page)).to_have_attribute("data-lf-says", "turn")
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("Reply"))
    assert field(page).evaluate("el => el.readOnly")
    expect(lead(page)).not_to_have_text(re.compile("Draw"))
    leave = page.locator('.lf-fp-row > .lf-fp-exit[aria-label="Exit Draw mode"]')
    named, seat = name.bounding_box(), leave.bounding_box()
    assert named and seat
    assert 0 <= seat["x"] - (named["x"] + named["width"]) < 12, (named, seat)
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(thread).to_be_visible()
    expect(name).to_be_hidden()
    expect(leave).to_have_count(0)
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Reply"))
    assert not field(page).evaluate("el => el.readOnly")

    thread.focus()
    page.keyboard.press("w")
    leave.click()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(thread).to_be_visible()

    thread.focus()
    page.keyboard.press("g")
    expect(name).to_have_text("Go to")
    page.locator('.lf-fp-row > .lf-fp-exit[aria-label="Close Go to"]').click()
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    expect(thread).to_be_visible()


def test_the_thread_walk_stands_on_each_thread_it_opens(browser, serve):
    """`t` opens the next thread in the panel and stands on it, as the walk stands on a
    card's title in Threads, so `t` and `T` go on walking from there rather than typing
    into its reply; showing an answer waiting below its fold stands on the thread too."""
    url = serve(LONG_PAGE)
    first = panel_comment(serve.page_dir, "Is the window long enough?")
    panel_comment(serve.page_dir, "Should the rollout pause on Fridays?")
    page = floating(browser, url)
    view = page.locator(panel_view("thread"))
    title = page.locator(".lf-fp-title")
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(title).to_have_text("Is the window long enough?")
    expect(view).to_be_focused()
    page.keyboard.press("t")
    expect(title).to_have_text("Should the rollout pause on Fridays?")
    expect(view).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(title).to_have_text("Is the window long enough?")
    expect(view).to_be_focused()

    # An answer too long for the view waits below its fold behind New reply.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": first,
            "revision": 1,
            "text": "The window covers it. " * 300,
        },
    )
    news = view.locator(".lf-new-reply")
    expect(news).to_be_visible()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(news).to_be_focused()
    page.keyboard.press("Enter")
    expect(news).to_have_count(0)
    expect(view.get_by_text("The window covers it.").first).to_be_in_viewport()
    expect(view).to_be_focused()


def test_the_on_view_is_titled_by_its_tab_with_that_list_s_done_under_it(
    browser, serve
):
    """The On view has no name of its own: its title is the open tab's, On Me or On
    Claude, which the tabs beside it already show, so the title names the view to
    assistive tech alone. The agent's tab goes by the name the page gives the agent:
    on a page no session holds, the voice that last wrote there, so it says Claude
    where Claude's messages do. Under each list stands what left it, under Done. A
    reply the agent sent leaves its list, so it stands under On Claude's Done, said as
    sent. The On Me tab turns the view back to the user's list, and the ✕ in the mark's
    seat closes it. Done stands folded under its band until the user unfolds it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "Forty-eight hours covers the first cohort.",
        },
    )
    page = floating(browser, url)
    # Nothing waits on the user but the agent's unread reply, so the leaf opens Threads,
    # and On Me is its tab.
    page.locator(".lf-fp-leaf").click()
    title = page.locator(".lf-fp-title")
    expect(title).to_have_text("Threads")
    panel_tab(page, "On Me").click()
    expect(title).to_have_text("On Me")
    assert title.bounding_box()["width"] <= 1
    expect(page.locator(".lf-fp-filters button")).to_have_text(
        ["Menu", "On Me 0", "On Claude 0", "Threads 1"]
    )
    expect(
        page.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    ).to_have_count(0)
    page.locator(".lf-fp-filters button", has_text="On Claude").click()
    expect(title).to_have_text("On Claude")
    expect(page.locator(".lf-floating-panel .lf-rows-empty")).to_have_text(
        "Nothing waiting on Claude."
    )
    expect(
        page.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    ).to_have_text(re.compile(r"^\s*Done\s*1\s*$"))
    expect(page.locator(".lf-fp-on-item")).to_have_count(0)
    sent = show_done(page)
    expect(sent).to_have_count(1)
    expect(sent).to_contain_text("Forty-eight hours covers the first cohort.")
    expect(sent.locator(".lf-fp-on-says > .lf-fp-value")).to_have_text(
        re.compile(r"^Answered")
    )
    # The On Me tab turns the open view back to the user's list, and the ✕ closes it.
    panel_tab(page, "On Me").click()
    expect(title).to_have_text("On Me")
    page.locator(".lf-fp-controls .lf-fp-close").click()
    expect(title).to_have_count(0)


def test_on_shows_an_obligation_as_its_message_and_reply_comes_back(browser, serve):
    """A question the agent asked in a thread reads in the On view as its message, drawn
    whole as the thread draws it, so what it introduces after a colon is there with it.
    Reply opens its thread with On behind it, where the back link returns to the card
    in its seat, answered in the thread though it is; left for Threads and opened
    again, On Me seats only what still waits, so a question answered meanwhile is gone."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir,
        "Which build should ship? These are the candidates:\n\n- #4813 schedule\n"
        "- #4812 manual",
        author="agent",
        obligation=True,
    )
    day = panel_comment(
        serve.page_dir, "Which day suits the launch?", author="agent", obligation=True
    )
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    card = page.locator(".lf-fp-on-item", has_text="Which build should ship?")
    expect(card.locator(".lf-msg")).to_have_count(1)
    expect(card.locator("li")).to_have_count(2)
    expect(card).to_contain_text("#4812 manual")

    card.locator(".lf-fp-answers button", has_text="Reply").click()
    expect(page.locator(panel_view("thread"))).to_be_visible()
    write(field(page), "Ship #4812.")
    with sending(page, "the answer"):
        page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    back = page.locator(".lf-fp-back")
    expect(back).to_have_attribute("aria-label", "Back to On Me")
    back.click()
    expect(page.locator(panel_view("queue"))).to_be_visible()
    expect(card).to_contain_text("Which build should ship?")
    panel_tab(page, "Threads").click()
    panel_settled(page, view="threads")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": day,
            "responds": day,
            "revision": 1,
            "text": "Thursday.",
        },
    )
    told(page)
    panel_tab(page, "On Me").click()
    panel_settled(page, view="queue")
    expect(page.locator(".lf-fp-on-item")).to_have_count(0)


def test_clicking_into_the_field_moves_none_of_an_open_view_s_controls(browser, serve):
    """An open view stands on its controls, and they stand right on the row, with no
    empty band between them. Clicking into the field shows nothing over it, since the
    keys that send are Send's hover name, and neither do words arriving, since the
    placeholder said where they go before they hid it, so its tabs and Close stay where
    the pointer may be about to press them."""
    page = floating(browser, serve(LONG_PAGE, comments=3))
    open_threads(page)
    view = page.locator(panel_view("threads"))
    expect(view).to_be_visible()
    settled(page)
    row = page.locator(".lf-fp-row")
    stands = view.bounding_box()
    controls = page.locator(".lf-fp-controls").bounding_box()
    for name, over, under in (
        ("the view and its controls", stands, controls),
        ("the controls and the row", controls, row.bounding_box()),
    ):
        band = under["y"] - (over["y"] + over["height"])
        assert abs(band) < 0.5, f"{band:.0f}px stand between {name}"
    close = page.locator(".lf-fp-close").bounding_box()
    tab = panel_tab(page, "Threads").bounding_box()
    field(page).click()
    settled(page)
    assert page.locator(".lf-fp-close").bounding_box() == close
    assert panel_tab(page, "Threads").bounding_box() == tab
    page.keyboard.type("Could")
    expect(page.locator(".lf-fp-send")).to_be_visible()
    # Send's preview names the key that sends from the box (annotations/preview.js).
    page.locator(".lf-fp-send").hover()
    expect(page.locator("#lf-preview")).to_be_visible()
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text("Send")
    # The key that sends, and where Return sends, the one that makes a new line, each
    # as the register spells it on this platform (dom/keyboard/bindings.js, `spell`), which
    # writes Shift as ⇧ on a Mac and as Shift+ elsewhere.
    send, line = page.evaluate(
        """async () => {
          const {spell} = await import('/runtime/dom/keyboard/bindings.js');
          return [spell('Enter'), spell('Shift+Enter')];
        }"""
    )
    expect(page.locator("#lf-preview kbd")).to_have_text([send, line])
    expect(page.locator("#lf-preview .lf-preview-detail")).to_have_text(
        f"New line {line}"
    )
    settled(page)
    assert page.locator(".lf-fp-close").bounding_box() == close
    assert view.bounding_box() == stands


# Where an open thread's name starts, over its view, and where each of its presses
# stands, on the same head line.
SEATS = """() => {
  const seat = (selector) => {
    const box = document.querySelector(selector)?.getBoundingClientRect();
    return box && [box.left, box.top, box.right, box.bottom];
  };
  const title = seat('.lf-fp-head .lf-fp-title');
  return {
    name: [title[0], title[1]],
    back: seat('.lf-fp-head .lf-fp-back'),
    on: seat('.lf-fp-head .lf-fp-on-page'),
    settle: seat('.lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)'),
    close: seat('.lf-fp-head .lf-fp-close'),
  };
}"""


def test_news_in_an_open_thread_moves_none_of_its_controls(browser, serve):
    """A thread's controls each stand where they stood while the thread changes. Retitled
    long or short, the name over the view gives or takes room at its own end, and Back,
    Show on page, Resolve and Close stay put; detached by a revision, Show on page leaves
    its seat empty; resolved by the agent, the thread holds the news, its Resolve and the
    field's words agreeing with it, and shown, Reopen takes Resolve's seat."""
    url = serve(LONG_PAGE, comments=3, anchored=[("p3", "Paragraph 3.")])
    root = events_model.read_events(serve.page_dir)[-1]["id"]
    page = floating(browser, url)
    choose_threads_in_panel(page)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="About this bit.").click()
    title = page.locator(".lf-fp-head .lf-fp-title")
    # Untitled, the name repeats the opening message, so only assistive tech hears it.
    expect(title).to_have_text("About this bit.")
    expect(title).to_have_class(re.compile(r"\blf-quiet\b"))
    settled(page)
    untitled = page.evaluate(SEATS)

    def agent(event):
        append_carried_log_record(
            serve.page_dir, {"author": "agent", "agent": "Claude", **event}
        )
        told(page)

    seats = None
    for name in [
        "Whether the third paragraph's filler should stay in the published draft",
        "Filler",
    ]:
        agent({"kind": "thread_title", "thread": root, "title": name})
        expect(title).to_have_text(name)
        settled(page)
        now = page.evaluate(SEATS)
        # A title showing for the first time moves none of the controls.
        assert {k: v for k, v in now.items() if k != "name"} == {
            k: v for k, v in untitled.items() if k != "name"
        }
        seats = seats or now
        assert all(seats.values()), seats
        assert now == seats

    # A revision that drops the passage detaches the thread: Show on page has nowhere
    # to go, and its seat stands empty while the view does.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reanchor",
            "author": "page",
            "revision": 1,
            "thread": root,
            "anchor": None,
        },
    )
    told(page)
    expect(page.locator(".lf-fp-head .lf-fp-on-page")).to_be_hidden()
    settled(page)
    assert page.evaluate(SEATS) == seats

    # Resolved by the agent while the user reads it, the thread holds the news behind
    # its notice, its Resolve and the field's words saying the thread as it stood, as a
    # card's do; shown, all three change together, and Reopen takes Resolve's seat.
    box = field(page)
    box.focus()
    words = page.locator(".lf-fp-field .lf-compose-placeholder-words")
    expect(words).to_have_text("Reply…")
    agent({"kind": "resolve", "parent": root})
    notice = page.locator(".lf-fp-news-outlet .lf-thread-news")
    expect_preview_words(notice, "Resolved")
    expect(page.locator(".lf-fp-head .lf-resolve")).to_be_visible()
    expect(words).to_have_text("Reply…")
    # Off the field, it says the thread's word before Reply, which isn't Resolved yet.
    page.locator(panel_view("thread")).focus()
    expect(lead(page)).not_to_contain_text("Resolved")
    expect(notice).to_be_visible()
    settled(page)
    assert page.evaluate(SEATS) == seats
    notice.click()
    expect(page.locator(".lf-fp-head .lf-reopen")).to_be_visible()
    # Who resolved it, which Reopen's name says only to a pointer resting on it.
    expect(lead(page)).to_contain_text(re.compile(r"Resolved by \w+"))
    box.focus()
    expect(words).to_have_text("Reply to reopen…")
    settled(page)
    assert page.evaluate(SEATS) == seats


# What news arriving must leave where it stood: the open thread's message, read word
# by word, and how much of its title the name over the view shows.
HELD_READING = """() => {
  const view = document.querySelector('.lf-fp-view[data-lf-route=thread]');
  const box = (node) => {
    const r = node.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom];
  };
  const title = document.querySelector('.lf-fp-head .lf-fp-title');
  return {
    message: [...view.querySelectorAll('.lf-msg-head > *, .lf-msg-body')].map(box),
    title: box(title),
  };
}"""


def test_on_a_phone_held_news_gives_way_before_close(browser, serve):
    """On a narrow phone a thread's head line holds its way back, Show on page, Resolve
    and Close beside its name. The name gives way first, and held news arriving there
    says its one count whole without pushing Close past the panel's edge."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which jobs should start first once the export and the reconciler have landed?",
        {"section": "p0"},
        author="agent",
    )
    context = browser.new_context(
        viewport={"width": 300, "height": 700}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Which jobs should start first").click()
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    expect(page.locator(".lf-fp-head .lf-fp-on-page")).to_be_visible()
    # A tap enters the reply, as a user's finger does, and moves the reply's word from
    # the line's end to its start.
    field(page).tap()
    write(field(page), "I think the export")
    for text in ("The export first.", "Then the reconciler."):
        agent_said(serve.page_dir, root, text)
    told(page)
    notice = page.locator(".lf-fp-head .lf-thread-news")
    expect(notice).to_be_visible()
    settled(page)
    head = page.locator(".lf-fp-head")
    assert head.evaluate("h => h.scrollWidth <= h.clientWidth"), head.evaluate(
        "h => [h.scrollWidth, h.clientWidth]"
    )
    card = page.locator(".lf-fp-card").bounding_box()
    close = page.locator(".lf-fp-head .lf-fp-close").bounding_box()
    assert close["x"] + close["width"] <= card["x"] + card["width"], (close, card)
    # The notice reads its count whole; it is never cut mid-word.
    expect(notice).to_have_text("2 new")
    assert notice.evaluate(
        "node => node.firstElementChild.scrollWidth <= node.firstElementChild.clientWidth + 1"
    )


def test_on_a_phone_a_thread_s_presses_take_a_line_beside_next_unread(browser, serve):
    """On a narrow phone, a thread offering Next unread and Show on page has more
    presses than its head line holds beside its way back. They take a line of their
    own under its name, Close still last, so every press stays inside the panel."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which jobs should start first once the export has landed?",
        {"section": "p0"},
        author="agent",
    )
    agent_said(
        serve.page_dir, root, "The export first. " + "The reports read it. " * 120
    )
    context = browser.new_context(
        viewport={"width": 300, "height": 700}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Which jobs should start first").click()
    expect(page.locator(".lf-fp-head .lf-next-unread")).to_be_visible()
    expect(page.locator(".lf-fp-head .lf-fp-on-page")).to_be_visible()
    settled(page)
    head = page.locator(".lf-fp-head")
    assert head.evaluate("h => h.scrollWidth <= h.clientWidth"), head.evaluate(
        "h => [h.scrollWidth, h.clientWidth]"
    )
    card = page.locator(".lf-fp-card").bounding_box()
    back, *presses = (
        page.locator(f".lf-fp-head {press}").bounding_box()
        for press in (
            ".lf-fp-back",
            ".lf-next-unread",
            ".lf-fp-on-page",
            ".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)",
            ".lf-fp-close",
        )
    )
    for box in (back, *presses):
        assert (
            card["x"] <= box["x"]
            and box["x"] + box["width"] <= card["x"] + card["width"]
        ), (box, card)
    middles = [box["y"] + box["height"] / 2 for box in presses]
    assert max(middles) - min(middles) < 1, presses
    assert presses[0]["y"] >= back["y"] + back["height"] - 1, (back, presses)
    assert [box["x"] for box in presses] == sorted(box["x"] for box in presses)


def test_on_a_phone_turning_on_s_tabs_moves_nothing(browser, serve, subtests):
    """On a phone the On view's four tabs keep their words whole, and turning between
    them moves no tab. At 390px they share their line with Close, giving up their
    insets to fit rather than sending Close to a line of its own; narrower, the presses
    may stand on a line over them. Close stays put on every tab."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-fp-leaf").tap()
    strip = page.locator(".lf-fp-controls .lf-fp-filters")
    close = page.locator(".lf-fp-controls .lf-fp-close")
    tabs = """() => [...document.querySelectorAll('.lf-fp-controls .lf-fp-filters button')]
      .map((el) => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width]; })"""
    for width in (390, 340):
        with subtests.test(width=width):
            page.set_viewport_size({"width": width, "height": 844})
            stood = closed = None
            for tab, view in (
                ("Menu", "menu"),
                ("On Me", "queue"),
                ("On Claude", "queue"),
                ("Threads", "threads"),
                ("Menu", "menu"),
            ):
                panel_tab(page, tab).tap()
                panel_settled(page, view=view)
                # A tapped button stays `:active` for a moment after the tap, scaled
                # by its press feedback; that is not the tab moving, so read once the
                # press lets go.
                page.wait_for_function(
                    "() => !document.querySelector('.lf-fp-controls :active')"
                )
                assert strip.evaluate("el => el.scrollWidth <= el.clientWidth"), tab
                now = page.evaluate(tabs)
                assert stood in (None, now), (tab, stood, now)
                stood = now
                box = close.bounding_box()
                assert closed in (None, box), (tab, closed, box)
                closed = box
                if width == 390:
                    line = strip.bounding_box()
                    middle = box["y"] + box["height"] / 2
                    assert line["y"] <= middle <= line["y"] + line["height"], (
                        f"Close left the tabs' line on {tab}",
                        line,
                        box,
                    )


def test_held_news_reads_whole_among_the_thread_s_controls(browser, serve):
    """News arriving while the user writes in an open thread waits behind a notice on
    the view's head line, before its presses. It reads whole, and no press and nothing
    in the messages moves; no message head carries it. Pressing it shows what was
    held inside the view, which holds its height, so the presses beside the notice stay
    under the pointer, and the first reply it held comes into sight."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which jobs should start first once the export and the reconciler have both "
        "landed on the new cluster?",
        author="agent",
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    write(field(page), "I think the export")
    settled(page)
    seats = page.evaluate(SEATS)
    reading = page.evaluate(HELD_READING)

    for text in (
        "The export job first, since the reports read it.",
        "Then the reconciler, once the export has landed.",
    ):
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
    told(page)
    notice = page.locator(".lf-fp-head .lf-thread-news")
    expect(notice).to_have_text("2 new")
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    assert page.evaluate(SEATS) == seats
    assert page.evaluate(HELD_READING) == reading
    expect(view.locator(".lf-msg-head .lf-thread-news")).to_have_count(0)

    notice.click()
    expect(view.locator(".lf-msg")).to_have_count(3)
    expect(notice).to_be_hidden()
    settled(page)
    assert page.evaluate(SEATS) == seats
    assert view.locator(".lf-msg", has_text="The export job first").evaluate(
        """message => {
            const seen = message.closest('.lf-fp-view').getBoundingClientRect();
            const box = message.getBoundingClientRect();
            return box.top < seen.bottom && box.bottom > seen.top;
        }"""
    )
    expect(field(page)).to_have_js_property("value", "I think the export")


def test_threads_is_as_tall_as_the_threads_it_shows(browser, serve):
    """Threads takes the height of what it lists, three open threads and a resolved
    fourth under Resolved, so no blank row stands under the last. Resolved stands
    folded to its heading and count, a row the arrows reach and Enter unfolds."""
    url = serve(LONG_PAGE, comments=3)
    settled_thread = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": settled_thread}
    )
    page = floating(browser, url)
    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    open_rows = inventory.locator(".lf-fp-thread:not([data-lf-resolved])")
    expect(open_rows).to_have_count(3)
    heading = inventory.locator(".lf-fp-settled")
    expect(heading).to_have_attribute("aria-expanded", "false")
    expect(heading).to_have_text(re.compile(r"^\s*Resolved\s*1\s*$"))
    expect(inventory.locator(".lf-fp-thread[data-lf-resolved]")).to_have_count(0)
    open_rows.last.focus()
    page.keyboard.press("ArrowDown")
    expect(heading).to_be_focused()
    page.keyboard.press("Enter")
    expect(heading).to_have_attribute("aria-expanded", "true")
    expect(show_resolved(page)).to_have_count(1)
    settled(page)
    below, row = inventory.evaluate(
        """view => {
          const last = [...view.querySelectorAll('.lf-fp-thread')].at(-1).getBoundingClientRect();
          return [view.getBoundingClientRect().bottom - last.bottom, last.height];
        }"""
    )
    assert below < row, f"{below:.0f}px stand empty under the last thread"


def test_copy_link_is_one_press_in_the_leaf_s_menu(browser, serve):
    """The page's link is copied from a row of the leaf's menu itself, in one press that
    puts the menu away and says in the field that the link was copied; its hover name
    says what the link grants. The rows that copy which Leaf or session runs the page
    stand in About this page alone, so the menu stays short."""
    page = floating(browser, serve(LONG_PAGE))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    menu = panel_menu(page)
    row = menu.locator('.lf-fp-item[data-lf-row="share"]')
    expect(row).to_have_text("Copy link")
    assert preview_parts(row)[-1].startswith("Grants access")
    expect(menu.locator('.lf-fp-item[data-lf-row="inspection"]')).to_have_count(1)
    expect(menu.locator('.lf-fp-item[data-lf-row="layer"]')).to_have_count(0)
    row.click()
    panel_settled(page, open=False)
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Link copied"))
    assert re.match(
        r"^http://.*[?&]t=", page.evaluate("navigator.clipboard.readText()")
    )


def test_a_refused_copy_leaves_the_link_to_select_in_about(browser, serve):
    """A clipboard that refuses the write leaves the user the link all the same: the
    press opens About on the link, as text they can select. The failure remains in Errors when the reader
    leaves About."""
    refuses = (
        "Clipboard.prototype.writeText = () => Promise.reject(new Error('refused'));"
    )
    page = open_page(browser, serve(LONG_PAGE), init_script=refuses)
    panel_menu(page).locator('.lf-fp-item[data-lf-row="share"]').click()
    about = page.get_by_role("dialog", name="About this page", exact=True)
    link = about.get_by_label("Link", exact=True)
    expect(link).to_contain_text(re.compile(r"^http://.*[?&]t="))
    expect(about.get_by_role("button", name="Copy Link", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    panel_menu(page).locator('[data-lf-row="errors"]').click()
    expect(page.locator(panel_view("errors")).locator(".lf-fp-error")).to_contain_text(
        "Link not copied · select it to copy"
    )


def test_page_search_stands_with_its_controls_at_the_panel(browser, serve):
    """Page search occupies the panel's main field, with an explicit search mode.
    Its up and down arrows
    move the count beside them and leave the query's field focused, so the next letter
    still edits it, and the query stays on the panel's bottom row at every width. A press on the
    marked match selects it."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("/")
    search = page.locator(".lf-page-search")
    expect(search).to_be_visible()
    expect(page.locator('.lf-fp-exit[aria-label="Close search"]')).to_be_visible()
    box = search.bounding_box()
    row = page.locator(".lf-fp-row").bounding_box()
    assert row["y"] <= box["y"] < box["y"] + box["height"] <= row["y"] + row["height"]
    expect(field(page)).to_be_hidden()
    expect(page.locator(".lf-fp-mode")).to_have_text("Search page")

    previous = page.get_by_role("button", name="Previous match")
    following = page.get_by_role("button", name="Next match")
    expect(following).to_have_attribute("aria-disabled", "true")
    # A query that arrives with no key, as a paste or a phone's suggestion does, offers
    # the arrows as soon as it matches.
    search.get_by_role("searchbox").fill("Paragraph 1")
    count = page.locator(".lf-page-search-status")
    expect(count).to_have_text("1 of 11")
    expect(following).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(".lf-fp-leaf")).to_be_visible()
    for width in (360, 390, 540, 1280):
        page.set_viewport_size({"width": width, "height": 800})
        settled(page)
        query = search.bounding_box()
        actions = page.locator(".lf-fp-actions").bounding_box()
        assert abs(query["y"] + query["height"] - actions["y"] - actions["height"]) < 1
        close = page.locator('.lf-fp-exit[aria-label="Close search"]').bounding_box()
        assert abs(query["y"] + query["height"] - close["y"] - close["height"]) < 1
        assert search.get_by_role("searchbox").bounding_box()["width"] >= 60
    following.click()
    expect(count).to_have_text("2 of 11")
    previous.click()
    previous.click()
    expect(count).to_have_text("11 of 11")
    page.keyboard.type("0")
    expect(count).to_have_text("1 of 1")
    # A press on the marked match selects it, as Enter does, even once focus has left
    # the box; a control painted over the words keeps its own press. The press aims at
    # the words, since the mark moves to them a frame after the count changes.
    at = page.evaluate(
        """() => {
          const text = document.querySelector("#p10").firstChild;
          const words = document.createRange();
          words.setStart(text, 0);
          words.setEnd(text, "Paragraph 10".length);
          const box = words.getBoundingClientRect();
          return [box.x + box.width / 2, box.y + box.height / 2];
        }"""
    )
    page.evaluate(
        """([x, y]) => {
          const cover = Object.assign(document.createElement("button"), { id: "cover" });
          Object.assign(cover.style, {
            position: "fixed", left: `${x - 4}px`, top: `${y - 4}px`, width: "8px",
            height: "8px",
          });
          cover.addEventListener("click", () => cover.toggleAttribute("data-pressed"));
          document.body.append(cover);
        }""",
        at,
    )
    page.mouse.click(*at)
    expect(page.locator("#cover")).to_have_attribute("data-pressed", "")
    expect(search).to_be_visible()
    page.locator("#cover").evaluate("el => el.remove()")
    page.mouse.click(*at)
    expect(search).to_be_hidden()
    assert page.evaluate("getSelection().toString()") == "Paragraph 10"


@pytest.mark.parametrize("touch", [False, True])
def test_whatever_the_field_holds_the_row_keeps_its_line(browser, serve, touch):
    """Page search, Threads' search and a thread's reply take turns with the page's
    comment field in one seat, so each stands in the one line the theme reserves for
    the row rather than sizing it. A page search box that brought its vendor's own
    control height would stand the row taller than the comment field it replaced."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=touch
    )
    page = open_page(browser, url, context=context)
    row = page.locator(".lf-fp-row")
    line = page.evaluate("""() => {
      const room = document.createElement('div');
      room.style.height = 'var(--lf-floating-row)';
      document.body.append(room);
      const line = room.getBoundingClientRect().height;
      room.remove();
      return line;
    }""")
    heights = {"rest": row.bounding_box()["height"]}

    page.locator("body").focus()
    page.keyboard.press("/")
    expect(page.locator(".lf-page-search")).to_be_visible()
    heights["page search"] = row.bounding_box()["height"]
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-search")).to_be_hidden()

    choose_threads_in_panel(page)
    rows = threads_rows(page)
    page.get_by_role("button", name="Find a thread or message").click()
    expect(page.locator("input.lf-fp-search")).to_be_visible()
    heights["threads search"] = row.bounding_box()["height"]
    page.keyboard.press("Escape")
    expect(page.locator("input.lf-fp-search")).to_be_hidden()

    rows.first.click()
    expect(page.locator(panel_view("thread"))).to_be_visible()
    expect(field(page)).to_be_visible()
    heights["thread reply"] = row.bounding_box()["height"]
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    heights["rest again"] = row.bounding_box()["height"]

    assert all(h == pytest.approx(line, abs=0.5) for h in heights.values()), (
        line,
        heights,
    )


@pytest.mark.parametrize(
    "destination, opening", [("page", "menu"), ("reply", "keyboard")]
)
def test_search_keeps_the_unfinished_comment_and_its_caret(
    browser, serve, destination, opening
):
    """Searching borrows the field's seat, never the comment's words or Send action.
    Returning keeps the same editor, insertion point and undo history for page comments
    and replies.
    """
    url = serve(LONG_PAGE)
    if destination == "reply":
        panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    if destination == "reply":
        page.keyboard.press("t")
    draft = "Keep this unfinished thought"
    write(field(page), draft)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    caret = field(page).evaluate("el => el.selectionStart")
    editor = field(page).element_handle()
    sent_before = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] in {"comment", "reply"}
    ]
    if opening == "keyboard":
        page.locator(panel_view("thread")).focus()
        page.keyboard.press("/")
    else:
        panel_control(page, "command:page.search.open", at="navigate").click()
    search = page.get_by_role("searchbox", name="Search page text")
    # fill() would focus it too, masking a broken handoff from the unfinished editor.
    expect(search).to_be_focused()
    search.fill("a phrase absent from the document")
    expect(page.locator(".lf-page-search-status")).to_have_attribute(
        "aria-label", "No matches"
    )
    expect(field(page)).to_be_hidden()
    expect(
        page.locator(".lf-fp-row").get_by_role("button", name="Send", exact=True)
    ).to_be_hidden()
    page.keyboard.press("Enter")
    expect(search).to_be_visible()
    if opening == "menu":
        page.get_by_role("button", name="Close search", exact=True).click()
    else:
        page.keyboard.press("Escape")
    expect(search).to_be_hidden()
    expect(field(page)).to_have_js_property("value", draft)
    assert field(page).evaluate("(el, original) => el === original", editor)
    assert field(page).evaluate("el => el.selectionStart") == caret
    for _ in range(12):
        if field(page).evaluate("el => el.matches(':focus')"):
            break
        page.keyboard.press("Tab")
    expect(field(page)).to_be_focused()
    page.keyboard.type("!")
    assert field(page).evaluate("el => el.value") == draft[:caret] + "!" + draft[caret:]
    page.keyboard.press("ControlOrMeta+z")
    expect(field(page)).to_have_js_property("value", draft)
    page.keyboard.press("ControlOrMeta+z")
    expect(field(page)).to_have_js_property("value", "")
    assert [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] in {"comment", "reply"}
    ] == sent_before


def test_threads_grow_in_place_and_hold_news_until_asked(browser, serve):
    """Threads fits the rows it lists, growing from its top edge as the user turns to it
    from On Me, so the Threads tab just pressed and Close, among the controls at its
    foot, stay under the pointer; a thread arriving after that moves none of its rows,
    waiting behind a notice. A reply that arrives while its thread is open
    waits behind the thread's notice."""
    url = serve(LONG_PAGE, comments=3)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "Forty-eight hours covers the first cohort.",
        },
    )
    page = floating(browser, url)
    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    panel_tab(page, "On Me").click()
    queue = page.locator(panel_view("queue"))
    expect(queue).to_be_visible()
    settled(page)
    short = queue.bounding_box()
    threads_tab = panel_tab(page, "Threads")
    close = page.locator(".lf-fp-close")
    before = threads_tab.bounding_box()
    closes = close.bounding_box()
    threads_tab.click()
    expect(inventory.locator(".lf-fp-thread")).to_have_count(4)
    settled(page)
    shown = inventory.bounding_box()
    assert shown["height"] > short["height"] + 40, (short, shown)
    assert shown["y"] + shown["height"] == short["y"] + short["height"]
    assert threads_tab.bounding_box() == before
    assert close.bounding_box() == closes
    rows = inventory.locator(".lf-fp-thread")
    tops = (
        "rows => rows.map(row => [row.dataset.lfKey, row.getBoundingClientRect().top])"
    )
    row_positions = rows.evaluate_all(tops)
    panel_comment(serve.page_dir, "Who watches the weekend?")
    told(page)
    joined = page.locator(".lf-fp-joined .lf-thread-news")
    expect_preview_words(joined, "1 new thread")
    settled(page)
    # The line starts on the words' edge, as the rows' marks do.
    assert page.locator(".lf-fp-joined").evaluate(
        """line => {
          const head = line.parentElement;
          return line.getBoundingClientRect().left - head.getBoundingClientRect().left
            - parseFloat(getComputedStyle(head).paddingLeft);
        }"""
    ) == pytest.approx(0, abs=0.5)
    expect(rows).to_have_count(4)
    assert rows.evaluate_all(tops) == row_positions
    assert threads_tab.bounding_box() == before
    assert close.bounding_box() == closes
    joined.click()
    expect(rows).to_have_count(5)
    expect(rows.filter(has_text="Who watches the weekend?")).to_be_visible()

    inventory.locator(".lf-fp-thread", has_text="Is the window long enough?").click()
    reader = page.locator(panel_view("thread"))
    expect(reader.locator(".lf-msg")).to_have_count(2)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "The weekend would need someone on call.",
        },
    )
    told(page)
    held = page.locator(".lf-fp-head .lf-thread-news:visible")
    expect(held).to_be_visible()
    expect(reader.locator(".lf-msg")).to_have_count(2)
    held.click()
    expect(reader.locator(".lf-msg")).to_have_count(3)


def test_threads_fades_out_where_it_stood(browser, serve):
    """A press on a row opens its thread while Threads fades out where it stood, with
    the rows it drew: the box takes the thread's height and loses the list's foot, a
    thread the list held behind its notice stays out, and a reply that would move a
    row up the list moves none while the fade lasts. Back from the thread takes its
    view away at once as Threads arrives, since the thread reader takes the thread's
    messages from it then, so it never fades out empty."""
    url = serve(LONG_PAGE, comments=3)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    open_threads(page)
    rows = page.locator(panel_view("threads")).locator(".lf-fp-thread")
    expect(rows).to_have_count(4)
    panel_comment(serve.page_dir, "Who watches the weekend?")
    told(page)
    expect_preview_words(page.locator(".lf-fp-joined .lf-thread-news"), "1 new thread")
    settled(page)
    places = """rows => rows.map(row =>
        [row.dataset.lfKey, Math.round(row.getBoundingClientRect().top)])"""
    drawn = rows.evaluate_all(places)
    hold_motion(page)
    rows.filter(has_text="Is the window long enough?").click()
    # The box's motion sets out in the press's first update, as the box's size is
    # delivered (dom/box-motion.js), and stands there while the motion is held.
    one_frame(page)
    leaving = page.locator(".lf-fp-view[data-lf-leaving]")
    expect(leaving).to_have_css("opacity", "1")
    fading = leaving.locator(".lf-fp-thread")
    assert fading.evaluate_all(places) == drawn
    oldest = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": oldest,
            "revision": 1,
            "text": "The first comment still stands.",
        },
    )
    told(page)
    assert fading.evaluate_all(places) == drawn
    finish_held(page)
    expect(leaving).to_have_count(0)
    expect(page.locator(panel_view("thread"))).to_be_visible()

    hold_motion(page)
    page.locator(".lf-fp-head .lf-fp-back").click()
    one_frame(page)
    expect(page.locator(panel_view("threads"))).to_be_attached()
    expect(leaving).to_have_count(0)
    finish_held(page)


# Whether the preview stands open clear of Threads' notice.
PREVIEW_CLEAR_OF_NOTICE = """() => {
  const tip = document.getElementById('lf-preview');
  const a = document.querySelector('.lf-fp-joined .lf-thread-news')?.getBoundingClientRect();
  const b = tip.getBoundingClientRect();
  return Boolean(a) && tip.matches(':popover-open') && (b.right <= a.left
    || b.left >= a.right || b.bottom <= a.top || b.top >= a.bottom);
}"""


def test_threads_holds_a_row_that_joins_or_moves_behind_a_notice(browser, serve):
    """A reply reopening a resolved thread would move its row from Resolved to the head
    of the list, a reply in the oldest open thread would move its row up, and a thread
    the agent starts would join among the open rows. None moves a row the user reads:
    the reopened and replied rows keep their places, the new one waits, and a notice
    says what joined or reopened. Enter on it lets the list settle, newest first, and
    lands on the first row it named, where K reads its preview. Later news holds the
    rows still behind the notice, and that preview keeps its corner, its words fitted
    to the room the notice leaves it (annotations/preview.js). A tab press draws the
    list whole, a row it held included."""
    url = serve(LONG_PAGE, comments=3)
    root = panel_comment(serve.page_dir, "Is the opening right?", {"section": "p0"})
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = floating(browser, url)
    show_resolved(page)
    rows = page.locator(panel_view("threads")).locator(".lf-fp-thread")
    returned = rows.filter(has_text="Is the opening right?")
    expect(rows).to_have_count(4)
    expect(returned).to_have_attribute("data-lf-resolved", "")
    settled(page)
    tops = (
        "rows => rows.map(row => [row.dataset.lfKey, row.getBoundingClientRect().top])"
    )
    before = rows.evaluate_all(tops)
    notice = page.locator(".lf-fp-joined .lf-thread-news")

    oldest = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )

    def agent_reply(parent, text):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": parent,
                "revision": 1,
                "text": text,
            },
        )

    agent_reply(oldest, "The first comment still stands.")
    panel_comment(serve.page_dir, "Should the close name the rollout?", author="agent")
    agent_reply(root, "The opening undersells the retry.")
    told(page)
    expect_preview_words(notice, "1 new thread · 1 thread reopened")
    settled(page)
    assert rows.evaluate_all(tops) == before

    notice.focus()
    page.keyboard.press("Enter")
    expect(notice).to_have_count(0)
    expect(rows.locator(".lf-fp-label")).to_have_text(
        [
            "Is the opening right?",
            "Should the close name the rollout?",
            re.compile("Comment 0"),
            re.compile("Comment 2"),
            re.compile("Comment 1"),
        ]
    )
    expect(returned).to_be_focused()
    # A landing previews nothing until the user asks (annotations/preview.js).
    expect(page.locator(PREVIEW)).to_be_hidden()
    page.keyboard.press("Shift+K")
    expect(page.locator(PREVIEW)).to_be_visible()
    settled(page)
    landed = rows.evaluate_all(tops)
    corner = page.locator(PREVIEW).bounding_box()

    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Claude", "parent": root},
    )
    told(page)
    expect_preview_words(notice, "1 thread resolved")
    settled(page)
    assert rows.evaluate_all(tops) == landed
    # The notice draws under the landed row's preview, and the room above the notice
    # holds a line of it, so the preview keeps its corner and its words are cut to
    # that room, and the watch reports no move.
    page.wait_for_function(PREVIEW_CLEAR_OF_NOTICE)
    held = page.locator(PREVIEW).bounding_box()
    assert (held["x"], held["y"]) == (corner["x"], corner["y"]), (corner, held)
    assert held["height"] < corner["height"], (corner, held)
    page.evaluate("() => window.lfShiftsJudged()")
    expect(rows.first).to_have_text(re.compile("Is the opening right?"))
    panel_tab(page, "Threads").click()
    expect(notice).to_have_count(0)
    expect(returned).to_have_attribute("data-lf-resolved", "")
    expect(rows.last).to_have_text(re.compile("Is the opening right?"))


def test_a_pointer_press_on_the_joined_notice_lands_the_walk_on_its_row(browser, serve):
    """A pointer's or a finger's press on the notice lands the list's walk on the first
    row it names, as Enter on it does. Where the user stood on a row of the list, or on
    the view itself, as Escape from Threads' search leaves them, focus goes with the
    walk, since the arrows walk from focus there. Where the caret is in the panel's
    field, the walk moves and the caret stays."""
    url = serve(LONG_PAGE, comments=3)
    page = floating(browser, url)
    dev_browser.go_to_threads(page)
    panel_settled(page, view="threads")
    rows = page.locator(panel_view("threads")).locator(".lf-fp-thread")
    expect(rows).to_have_count(3)
    page.keyboard.press("ArrowDown")
    stood = rows.nth(1)
    expect(stood).to_be_focused()
    notice = page.locator(".lf-fp-joined .lf-thread-news")

    panel_comment(serve.page_dir, "Should the close name the rollout?", author="agent")
    told(page)
    expect_preview_words(notice, "1 new thread")
    notice.click()
    joined = rows.filter(has_text="Should the close name the rollout?")
    expect(joined).to_be_focused()
    expect(joined).to_have_attribute("tabindex", "0")
    expect(stood).to_have_attribute("tabindex", "-1")

    page.keyboard.press("/")
    page.keyboard.press("Escape")
    expect(page.locator(panel_view("threads"))).to_be_focused()
    panel_comment(serve.page_dir, "Is the retry window documented?", author="agent")
    told(page)
    expect_preview_words(notice, "1 new thread")
    notice.click()
    searched = rows.filter(has_text="Is the retry window documented?")
    expect(searched).to_be_focused()
    expect(searched).to_have_attribute("tabindex", "0")

    field(page).click()
    panel_comment(serve.page_dir, "Does the summary need a date?", author="agent")
    told(page)
    expect_preview_words(notice, "1 new thread")
    notice.click()
    later = rows.filter(has_text="Does the summary need a date?")
    expect(later).to_have_attribute("tabindex", "0")
    expect(field(page)).to_be_focused()


def test_resolved_news_unfolds_resolved_to_land_on_its_row(browser, serve):
    """A thread resolved elsewhere while Threads stands with Resolved folded keeps its
    row in place behind the notice, with Open's band counting it out as the tab does,
    and Enter on the notice unfolds Resolved, where the row now stands, and lands on
    it."""
    url = serve(LONG_PAGE, comments=2)
    settling = panel_comment(serve.page_dir, "Is the opening right?", {"section": "p0"})
    page = floating(browser, url)
    open_threads(page)
    view = page.locator(panel_view("threads"))
    heading = view.locator(".lf-fp-settled")
    row = view.locator(".lf-fp-thread", has_text="Is the opening right?")
    expect(row).to_be_visible()
    notice = page.locator(".lf-fp-joined .lf-thread-news")

    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": settling}
    )
    told(page)
    expect_preview_words(notice, "1 thread resolved")
    expect(row).to_be_visible()
    expect(view.locator(".lf-rows-group > .lf-rows-head")).to_have_text(
        [re.compile(r"^\s*Open\s*2\s*$")]
    )

    notice.focus()
    page.keyboard.press("Enter")
    expect(notice).to_have_count(0)
    expect(heading).to_have_attribute("aria-expanded", "true")
    expect(heading).to_have_text(re.compile(r"^\s*Resolved\s*1\s*$"))
    expect(row).to_have_attribute("data-lf-resolved", "")
    expect(row).to_be_focused()


AGENDA_PAGE = titled_page(
    "agenda",
    """<h1 id="t">Workshop</h1>
<p id="agenda">The sample agenda has room for one more topic.</p>
<p id="lunch">The schedule leaves an hour at noon for lunch.</p>""",
)


def agenda_threads(page_dir):
    """Three threads in the log in the order they were started: one on the later
    passage, one on the page as a whole, then one on the earlier passage."""
    panel_comment(
        page_dir, "Is lunch provided?", {"section": "lunch", "quote": "schedule leaves"}
    )
    panel_comment(page_dir, "Who signs off?")
    panel_comment(
        page_dir, "Kickoff length", {"section": "agenda", "quote": "one more topic"}
    )


def threads_rows(page):
    open_threads(page)
    return page.locator(f"{panel_view('threads')} .lf-fp-thread")


HOVER_LIT = "() => [...(CSS.highlights.get('lf-mark-hover') ?? [])].map(String)"
MARKED_ROW = re.compile(r"\blf-mark-hover\b")


def test_a_thread_s_row_and_its_passage_light_each_other(browser, serve):
    """Threads lists its rows newest first rather than in the page's order `t` walks:
    the thread started last, on the earlier passage, leads, and the one started first,
    on the later passage, ends the list. The pointer on a thread's row lights the words
    it is about, as the pointer on those words does, and the pointer on those words, or
    on their margin entry, marks the row. Neither moves anything or takes focus."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    expect(rows.locator(".lf-fp-label")).to_have_text(
        ["Kickoff length", "Who signs off?", "Is lunch provided?"]
    )
    kickoff = rows.filter(has_text="Kickoff length")
    lunch = rows.filter(has_text="Is lunch provided?")
    expect(lunch).to_be_visible()
    settled(page)
    page.evaluate("() => { window.focusBefore = document.activeElement; }")
    boxes = "() => [...document.querySelectorAll('.lf-fp-thread, main p')].map(n => JSON.stringify(n.getBoundingClientRect()))"
    before = page.evaluate(boxes)

    kickoff.hover()
    page.wait_for_function(f"() => ({HOVER_LIT})().join() === 'one more topic'")
    expect(kickoff).to_have_class(MARKED_ROW)

    words = page.evaluate(
        """() => {
          const range = [...CSS.highlights.get('lf-mark')]
            .find((candidate) => String(candidate) === 'schedule leaves');
          const box = range.getClientRects()[0];
          return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
        }"""
    )
    page.mouse.move(words["x"], words["y"])
    expect(lunch).to_have_class(MARKED_ROW)
    expect(kickoff).not_to_have_class(MARKED_ROW)
    page.wait_for_function(f"() => ({HOVER_LIT})().join() === 'schedule leaves'")

    entry = page.evaluate(
        """() => {
          const passage = document.getElementById('agenda').getBoundingClientRect();
          const entry = [...document.querySelectorAll('.lf-margin-entry')]
            .map((node) => node.getBoundingClientRect())
            .find((box) => box.width && box.top < passage.bottom && box.bottom > passage.top);
          return { x: entry.left + entry.width / 2, y: entry.top + entry.height / 2 };
        }"""
    )
    page.mouse.move(entry["x"], entry["y"])
    expect(kickoff).to_have_class(MARKED_ROW)
    expect(lunch).not_to_have_class(MARKED_ROW)

    page.mouse.move(2, 2)
    expect(rows.and_(page.locator(".lf-mark-hover"))).to_have_count(0)
    page.wait_for_function(f"() => !({HOVER_LIT})().length")
    assert page.evaluate(boxes) == before
    assert page.evaluate("() => document.activeElement === window.focusBefore")


def test_threads_search_finds_a_thread_by_the_words_it_quotes(browser, serve):
    """Searching Threads finds a thread by the words it is about as well as by its
    name and messages: words only the passage holds find the thread on it. The search
    press stays under the pointer as the list's Close waits for the search's ✕."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    expect(rows).to_have_count(3)
    write(field(page), "Keep my page comment")
    editor = field(page).element_handle()
    find = page.get_by_role("button", name="Find a thread or message")
    settled(page)
    stood = find.bounding_box()
    find.click()
    expect(page.locator(".lf-fp-mode")).to_have_text("Search threads")
    expect(page.locator(".lf-fp-controls .lf-fp-close")).to_be_hidden()
    settled(page)
    assert find.bounding_box() == stood
    expect(field(page)).to_be_hidden()
    page.locator("input.lf-fp-search").fill("schedule leaves")
    expect(rows.locator(".lf-fp-label")).to_have_text(["Is lunch provided?"])
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(field(page)).to_have_js_property("value", "Keep my page comment")
    assert field(page).evaluate("(el, original) => el === original", editor)


def test_threads_search_reads_rendered_messages_and_summaries(browser, serve):
    """Words in formatted prose, embedded questions and a summary find the thread
    that shows them, even before the reader opens it."""
    from browser.threads import summarize_thread

    url = serve(AGENDA_PAGE)
    root = panel_comment(serve.page_dir, "Where should we meet?")
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The **room** photo.\n\n"
        '<lf-group id="crop" label="Should I reshoot it wider?">\n<h3 id="crop-h">Should I reshoot it wider?</h3>'
        '<lf-options id="crop-pick"><lf-option id="crop-wider">Wider</lf-option>'
        '<lf-option id="crop-same">As it is</lf-option></lf-options></lf-group>',
    )
    summarize_thread(serve.page_dir, root, reply["id"], "A **wider** view would help.")
    page = floating(browser, url)
    rows = threads_rows(page)
    page.get_by_role("button", name="Find a thread or message").click()
    search = page.locator("input.lf-fp-search")
    for words in ("room photo", "reshoot", "wider view"):
        search.fill(words)
        expect(rows.locator(".lf-fp-label")).to_have_text(["Where should we meet?"])
    rows.click()
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-summary-text")).to_have_text("A wider view would help.")
    expect(view.locator("#crop h3")).to_have_text("Should I reshoot it wider?")


def test_keys_in_threads_act_on_threads(browser, serve):
    """Go to Threads lands on its list's first row, where `/` finds threads and d and u
    page the list rather than the page under it."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    for n in range(12):
        panel_comment(serve.page_dir, f"Question {n} about the room")
    page = floating(browser, url)
    resized(page, 1440, 500)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    view = page.locator(panel_view("threads"))
    rows = view.locator(".lf-fp-thread")
    expect(rows.first).to_be_focused()
    assert view.evaluate("box => box.scrollHeight > box.clientHeight")
    document = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(document)
    page.keyboard.press("d")
    page.wait_for_function("box => box.scrollTop > 0", arg=view.element_handle())
    page.keyboard.press("u")
    page.wait_for_function("box => box.scrollTop === 0", arg=view.element_handle())
    assert page.evaluate(document) == before

    page.keyboard.press("/")
    expect(page.locator("input.lf-fp-search")).to_be_focused()
    expect(page.locator(".lf-page-search")).to_be_hidden()
    page.keyboard.type("schedule leaves")
    expect(rows.locator(".lf-fp-label")).to_have_text(["Is lunch provided?"])


def test_escape_from_threads_search_returns_to_threads(browser, serve):
    """Escape in Threads' search clears its words, then, with the box empty, closes the
    search and leaves the user in Threads, as a find box returns to its panel, where it
    put Threads away; the next Escape closes Threads."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    view = page.locator(panel_view("threads"))
    search = page.locator("input.lf-fp-search")
    page.get_by_role("button", name="Find a thread or message").click()
    search.fill("schedule leaves")
    expect(rows).to_have_count(1)
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(rows).to_have_count(3)
    page.keyboard.press("Escape")
    expect(search).to_be_hidden()
    expect(view).to_be_focused()
    page.keyboard.press("Escape")
    expect(view).to_have_count(0)


THREAD_FIT = """() => {
  const view = document.querySelector('.lf-fp-view[data-lf-route=thread]');
  const box = view.getBoundingClientRect();
  const messages = [...view.querySelectorAll('.lf-msg')];
  return {
    height: box.height,
    scrolls: view.scrollHeight > view.clientHeight + 1,
    below: box.bottom - messages.at(-1).getBoundingClientRect().bottom,
    gap: parseFloat(getComputedStyle(view).getPropertyValue('--lf-msg-gap')),
    first: messages[0].getBoundingClientRect().top,
    panel: document.querySelector('.lf-fp-card').getBoundingClientRect().top,
    window: window.innerHeight,
  };
}"""


def test_a_thread_s_view_is_as_tall_as_its_messages(browser, serve):
    """An opened view is as tall as what it holds. A page comment opens its thread one
    message tall, and a long thread reads in most of the window's height, leaving a band
    of the page above the panel, before it scrolls."""
    url = serve(LONG_PAGE)
    long_root = panel_comment(serve.page_dir, "Walk me through the whole rollout.")
    for step in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": long_root,
                "revision": 1,
                "text": f"Step {step}. "
                + "The cohort widens once the alarms hold. " * 4,
            },
        )
    page = floating(browser, url)
    write(field(page), "Could the rollback cover the weekend?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    short = page.evaluate(THREAD_FIT)
    assert not short["scrolls"]
    # Nothing stands under its message but a message's gap over the field.
    assert short["below"] - short["gap"] < 10, short

    page.keyboard.press("Escape")
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Walk me through the whole rollout.").click()
    expect(view.locator(".lf-msg")).to_have_count(9)
    settled(page)
    long = page.evaluate(THREAD_FIT)
    assert long["height"] > 600, long
    assert long["panel"] >= long["window"] * 0.1, long


# The field's place is its words': while the caret is in it, its slot runs out to the
# panel's edges for its ring, and the words stay put (floating-panel.css).
GROWTH = """() => {
  const view = document.querySelector('.lf-fp-view[data-lf-route=thread]');
  const box = (node) => node.getBoundingClientRect();
  const msgs = [...view.querySelectorAll('.lf-msg')];
  const turn = msgs.findLast((msg) => msg.querySelector('.lf-msg-head')?.textContent.includes('Me'));
  const foot = view.querySelector('.lf-awaited');
  return {
    view: box(view).top,
    height: box(view).height,
    cap: parseFloat(getComputedStyle(view.parentElement).maxHeight),
    bottom: box(view).bottom,
    field: box(document.querySelector('.lf-fp-field leaf-text')).top,
    turn: turn && [box(turn).top - box(view).top - parseFloat(getComputedStyle(view).paddingTop),
                   foot ? box(foot).top - box(turn).bottom : box(view).bottom - box(turn).bottom],
    foot: foot && box(foot).bottom,
  };
}"""


def risen(before, after, by):
    """Whether the thread's head line, its name and its presses (`SEATS`), stands moved
    `by` down the window, rising with a view that grows at its top."""

    def moved(name, seat):
        if name == "name":
            left, top = seat
            return [left, top + by]
        left, top, right, bottom = seat
        return [left, top + by, right, bottom + by]

    return all(
        (seat is None) == (after[name] is None)
        and (
            seat is None
            or all(
                abs(a - b) < 0.5
                for a, b in zip(after[name], moved(name, seat), strict=True)
            )
        )
        for name, seat in before.items()
    )


def test_new_reply_leads_to_the_reply_once_one_follows_the_work(browser, serve):
    """Work under way past the view's cap waits behind New message; the reply
    that follows it takes the press over, which then says New reply and brings the
    reply's start into sight, not the work before it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)

    def say(text, **kwargs):
        thread_model.post_reply(serve.page_dir, {"responds": root}, text, **kwargs)
        told(page)

    press = view.locator(".lf-new-reply")
    say("Reading the jobs, the mounts and the frost dates. " * 80, ephemeral=True)
    expect(press).to_have_text("New message")
    say("The mounts come first. " + "They need the frost to lift. " * 120)
    expect(press).to_have_text("New reply")
    press.click()
    expect(press).to_have_count(0)
    settled(page)
    reply = view.locator(".lf-msg", has_text="The mounts come first.")
    shown, box = reply.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)


def test_a_reply_that_lands_mid_carry_continues_it(browser, serve):
    """A reply that lands while the thread view still carries the work before it
    re-times that carry from where it is drawn; the watch credits the one trajectory
    from the step that began it, so the view's head and messages hold no motion of
    their own. The carry runs long, so the reply lands in it on any machine."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    page = floating(browser, url)
    page.add_style_tag(content=".lf-floating-panel { --lf-motion-box-resize: 1500ms }")
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    press = view.locator(".lf-new-reply")
    for text, kwargs, says in [
        (
            "Reading the jobs, the mounts and the frost dates. " * 80,
            {"ephemeral": True},
            "New message",
        ),
        (
            "The mounts come first. " + "They need the frost to lift. " * 120,
            {},
            "New reply",
        ),
    ]:
        thread_model.post_reply(serve.page_dir, {"responds": root}, text, **kwargs)
        told(page)
        expect(press).to_have_text(says)
    settled(page)


def test_a_streaming_answer_grows_the_view_until_it_outgrows_its_cap(
    browser, serve, request
):
    """An answer the user waits for that streams in grows the view at each step, the
    thread's name rising with it and the field and the controls staying put, with the
    answer's end in sight; a
    step past the view's cap, such as the durable answer completing it with longer
    words, leaves New reply at the view's foot."""
    # The threads suite imports this one, so its stream helpers come in at run time.
    from browser.threads import claim_for_codex, stream_reply

    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Record the release on the board: "
        + "which build shipped, which checks passed, and who signed it off. " * 3,
    )
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(1)
    settled(page)
    seats = page.evaluate(SEATS)
    stood = page.evaluate(GROWTH)

    def streamed(text):
        stream_reply(serve.page_dir, root, text)
        told(page)
        expect(messages.last.locator(".lf-msg-text")).to_have_text(text)
        settled(page)
        grown = page.evaluate(GROWTH)
        assert (grown["field"], grown["bottom"]) == (stood["field"], stood["bottom"])
        assert risen(seats, page.evaluate(SEATS), grown["view"] - stood["view"])
        shown, box = messages.last.bounding_box(), view.bounding_box()
        assert shown["y"] + shown["height"] <= box["y"] + box["height"] + 0.5
        return grown

    assert streamed("I'll")["view"] < stood["view"]
    streamed("I'll record it on the board now. " + "Then the totals. " * 12)
    expect(view.locator(".lf-new-reply")).to_have_count(0)

    # The durable answer completes the streamed message with longer words.
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Recorded the release on the board. " + "Then I checked the totals. " * 200,
        attempt="leaf-response-explicit",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with transaction_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(messages.last.locator(".lf-msg-text")).to_contain_text(
        "Recorded the release"
    )
    expect(view.locator(".lf-new-reply")).to_have_text("New reply")
    settled(page)
    capped = page.evaluate(GROWTH)
    assert abs(capped["height"] - capped["cap"]) < 1, capped
    assert capped["field"] == stood["field"]


def agent_said(page_dir, root, text, **fields):
    """One agent reply in `root`'s thread, written straight to the log."""
    return append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "revision": 1,
            "text": text,
            **fields,
        },
    )["id"]


def test_a_thread_s_view_hides_completed_progress_as_its_card_does(browser, serve):
    """A thread's view draws its messages as the thread's card on the page does
    (records/thread/transcript.js): steps the answer ended stay hidden, and the step on the
    user's follow-up stands as one dim working message at the transcript's foot rather
    than as a reply. What anyone wrote, messages and the working line alike, reads in
    Leaf's sans rather than the page's serif."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Can you check that the workshop fits the afternoon?"
    )
    for step in ("the total practice time", "the break and closing discussion"):
        agent_said(serve.page_dir, root, f"Checking {step}.", ephemeral=True)
    agent_said(
        serve.page_dir,
        root,
        "The workshop fits, including a fifteen-minute break.",
        responds=root,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "text": "Can the closing discussion run past five?",
        },
    )
    agent_said(
        serve.page_dir,
        root,
        "Checking whether the room stays free after five.",
        ephemeral=True,
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    shown = view.locator(".lf-msg:visible")
    expect(shown).to_have_count(3)
    expect(shown.nth(1)).to_contain_text("The workshop fits")
    working = view.locator(".lf-thread-working")
    expect(working).to_be_visible()
    expect(working).to_contain_text("Checking whether the room stays free after five")
    face = "(node) => getComputedStyle(node).fontFamily"
    leaf = page.locator(".lf-fp-head .lf-fp-title").evaluate(face)
    assert leaf != page.evaluate("getComputedStyle(document.body).fontFamily")
    for words in (
        shown.nth(1).locator(".lf-msg-body"),
        working.locator(".lf-thread-working-words"),
    ):
        assert words.evaluate(face) == leaf


def test_a_thread_s_view_opens_on_its_first_unread_reply(browser, serve):
    """A thread's view opens on its first unread reply, as its card does, with that
    reply's head and its New at the view's top rather than above it. A long reply
    shown only in part stays unread, so Next unread is offered; scrolling the view to
    its end shows the rest of it, and every reply then counts as read, so Next unread
    is no longer offered, though its seat stays."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(
        serve.page_dir,
        root,
        "The mounts come first. " + "The frost dates hold them. " * 150,
        responds=root,
    )
    agent_said(serve.page_dir, root, "Then the beds.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    long_reply = view.locator(".lf-msg", has_text="The mounts come first.")
    new = long_reply.locator(".lf-msg-head .lf-msg-new")
    unread = re.compile(r"(^|\s)lf-unread(\s|$)")
    expect(new).to_have_text("New")
    expect(new).to_be_in_viewport(ratio=1)
    settled(page)
    # Nothing in the view, such as its head, stands over the reply's New.
    assert new.evaluate(
        """(tag) => {
          const box = tag.getBoundingClientRect();
          return document.elementsFromPoint(box.x + box.width / 2, box.y + box.height / 2)
            .includes(tag);
        }"""
    )
    expect(long_reply).to_have_class(unread)
    press = page.locator(".lf-fp-head .lf-next-unread")
    expect(press).to_have_text("Next unread")

    # Read tracking needs a reply's whole extent shown (records/thread/read.js), so the wheel
    # steps by less than the view's height and each step draws before the next.
    scroller = view.element_handle()
    view.hover()
    with sending(page, "the replies read"):
        while not view.evaluate(
            "v => v.scrollTop + v.clientHeight >= v.scrollHeight - 1"
        ):
            stood = view.evaluate("v => v.scrollTop")
            page.mouse.wheel(0, 120)
            page.wait_for_function(
                "([v, stood]) => v.scrollTop > stood", arg=[scroller, stood]
            )
            page.evaluate(
                "() => new Promise((done) =>"
                " requestAnimationFrame(() => requestAnimationFrame(done)))"
            )
    expect(long_reply).not_to_have_class(unread)
    expect(view.locator(".lf-msg", has_text="Then the beds.")).not_to_have_class(unread)
    expect(press).to_be_hidden()
    expect(press).to_be_disabled()


# Where a press and the view's head, the thread's name standing on the view's top edge,
# stand once the frame after it has drawn, so the view's own reading of what the press
# grew has run.
PRESS_AND_HEAD = """(toggle) => new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => done({
    toggle: document.querySelector(toggle).getBoundingClientRect().top,
    head: document.querySelector('.lf-fp-head').getBoundingClientRect().top,
    page: scrollY,
  })))
)"""


def test_a_fold_pressed_in_a_thread_s_view_stays_under_the_press(browser, serve):
    """Opening a summary holds its toggle and the thread's head under the press,
    while earlier messages open inside the view."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Can you check that the workshop fits the afternoon?"
    )
    answered = agent_said(
        serve.page_dir,
        root,
        "The workshop fits, including a fifteen-minute break.",
        responds=root,
    )
    asked = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "revision": 1,
            "text": "And the room after five?",
        },
    )["id"]
    said = agent_said(
        serve.page_dir, root, "The room stays free until seven. " * 4, responds=asked
    )
    summarize_thread(
        serve.page_dir, answered, said, "It fits, and the room is free until seven."
    )
    agent_said(serve.page_dir, root, "Booked it for the afternoon.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    settled(page)
    toggle = ".lf-fp-view .lf-summary-checkpoint .lf-summary-expand"
    stood = page.evaluate(PRESS_AND_HEAD, toggle)
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "true")
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, toggle) == pytest.approx(stood, abs=0.5)
    expect(view.locator(".lf-msg:visible")).to_have_count(5)


def test_an_answer_the_user_waits_for_grows_the_view_after_a_press_on_its_words(
    browser, serve
):
    """A press that grows nothing holds nothing: the user clicking a message's words
    while waiting for the agent's answer still sees the answer grow the view, as it
    would without the click."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(2)
    write(field(page), "And then?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(3)
    settled(page)
    messages.first.locator(".lf-msg-text").click()
    page.wait_for_timeout(200)
    settled(page)
    stood = view.bounding_box()["height"]
    agent_said(
        serve.page_dir, root, "Then the beds. " + "The frost dates hold them. " * 4
    )
    told(page)
    expect(messages).to_have_count(4)
    settled(page)
    assert view.bounding_box()["height"] > stood + 40, stood


def test_closing_a_fold_keeps_its_press_and_the_head_in_place(browser, serve):
    """Closing a fold shrinks what the view holds below its press. After the user's turn
    has let go of the height opening it held, the view holds its height again for the
    close, so Collapse and the thread's name stay where they were rather than dropping
    as the view shrinks from its top edge."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which jobs come first?")
    first = agent_said(
        serve.page_dir, root, "The mounts come first. " * 6, responds=root
    )
    then = agent_said(serve.page_dir, root, "Then the beds, once the frost lifts. " * 6)
    summarize_thread(serve.page_dir, first, then, "Mounts, then beds.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    toggle = ".lf-fp-view .lf-summary-checkpoint .lf-summary-expand"
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "true")
    write(field(page), "And the paths?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(view.locator(".lf-msg", has_text="And the paths?")).to_be_visible()
    settled(page)
    view.evaluate("view => view.scrollTop = 0")
    stood = page.evaluate(PRESS_AND_HEAD, toggle)
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "false")
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, toggle) == pytest.approx(stood, abs=0.5)


def test_a_thread_s_view_opens_on_the_summary_holding_its_first_unread_reply(
    browser, serve
):
    """A first unread reply a closed summary folds away is reached through the
    summary, so the view opens on that summary rather than past it, at the long reply
    after it."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which jobs come first?")
    first = agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    then = agent_said(serve.page_dir, root, "Then the beds, once the frost lifts.")
    summarize_thread(serve.page_dir, first, then, "Mounts, then beds.")
    agent_said(
        serve.page_dir, root, "That is the order. " + "The frost dates hold. " * 150
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    summary = page.locator(".lf-fp-view .lf-summary-checkpoint .lf-summary-header")
    expect(summary).to_be_in_viewport(ratio=1)


def test_next_unread_into_a_closed_summary_stays_under_the_press(browser, serve):
    """Next unread reaching a reply a closed fold holds opens the fold in the view and
    lands on the reply inside it. The press stands on the view's head line, which the
    view's growth would carry, so the view holds its height, and the press and the head
    stay where they were while what opened goes on inside the view. The fold is taller
    than the view, since a fold seen whole reads the replies it folds."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which jobs come first?")
    first = agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    then = agent_said(serve.page_dir, root, "Then the beds, once the frost lifts.")
    summarize_thread(
        serve.page_dir, first, then, "\n\n".join(["The mounts, then the beds."] * 40)
    )
    agent_said(serve.page_dir, root, "That is the order.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    unread = ".lf-fp-head .lf-next-unread"
    press = page.locator(unread)
    expect(press).to_be_visible()
    settled(page)
    stood = page.evaluate(PRESS_AND_HEAD, unread)
    press.click()
    reply = page.locator(".lf-fp-view .lf-msg", has_text="The mounts come first.")
    expect(reply).to_be_focused()
    expect(reply).to_be_in_viewport(ratio=1)
    settled(page)
    after = page.evaluate(PRESS_AND_HEAD, unread)
    assert after == stood, (stood, after)


def test_next_unread_never_shows_for_a_reply_the_opening_reads(browser, serve):
    """Opening a thread whose one unread reply is short reads it as the view lands, so
    Next unread never shows on the view's head line, not even for the moment before
    the reply is read."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    page = floating(browser, url)
    page.evaluate("""() => {
      window.nextUnreadShown = false;
      new MutationObserver(() => {
        window.nextUnreadShown ||= Boolean(
          document.querySelector('.lf-next-unread:not([data-lf-unoffered])'));
      }).observe(document, {subtree: true, childList: true, attributes: true});
    }""")
    reply = page.locator(".lf-fp-view .lf-msg", has_text="The mounts come first.")
    with sending(page, "the reply read"):
        page.locator("body").focus()
        page.keyboard.press("t")
        expect(reply).to_be_visible()
    expect(reply).not_to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    round_trip(page)
    assert not page.evaluate("() => window.nextUnreadShown")
    expect(page.locator(".lf-next-unread")).to_have_count(0)


FOOT = """([parts, fromEnd]) => {
  const view = document.querySelector('.lf-fp-view:not([data-lf-leaving])');
  const part = [...view.querySelectorAll(parts)].at(-1 - fromEnd).getBoundingClientRect();
  const box = view.getBoundingClientRect();
  const press = view.querySelector('.lf-new-reply')?.getBoundingClientRect();
  return {
    below: box.bottom - part.bottom - parseFloat(getComputedStyle(view).paddingBottom),
    pad: parseFloat(getComputedStyle(view).paddingBottom),
    gap: parseFloat(getComputedStyle(view).getPropertyValue('--lf-msg-gap')),
    press: press && {over: press.top - part.bottom, under: box.bottom - press.bottom},
    said: [...document.querySelectorAll('.lf-fp-peek')]
      .filter((node) => node.checkVisibility())
      .map((node) => node.textContent),
  };
}"""


def test_an_open_view_covers_the_page_beneath_it(browser, serve):
    """The floating panel declares the one box it covers (dom/geometry.js, `declareCover`),
    and what a view open above the row covers is hidden from every reading of what the
    user sees: a paragraph in the band the view stands across reads as unseen while the
    view is open, though part of it stands beside the view, since the user sees it only
    in pieces there; and it reads whole again once the view is put away."""
    page = floating(browser, serve(LONG_PAGE, comments=12))
    seen = """async () => {
      const {seenRect} = await window.__lfCheckApi();
      const view = document.querySelector('.lf-fp-view').getBoundingClientRect();
      const under = [...document.querySelectorAll('main p')].find(p => {
        const box = p.getBoundingClientRect();
        return box.top > view.top + 20 && box.bottom < view.bottom - 20;
      });
      window.under = under;
      const box = under.getBoundingClientRect();
      return {view: {left: view.left, right: view.right},
              under: {left: box.left, right: box.right},
              shown: seenRect(under, new Map())};
    }"""
    open_threads(page)
    expect(page.locator(".lf-fp-thread")).to_have_count(12)
    settled(page)
    reading = page.evaluate(seen)
    view, under = reading["view"], reading["under"]
    assert under["left"] < view["left"] or under["right"] > view["right"], reading
    assert reading["shown"] is None, reading

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    # The box shrinks to the row after the view goes, and stands over the paragraph
    # for the start of that motion, so the paragraph reads whole once it rests.
    panel_settled(page, open=False)
    whole = page.evaluate(
        """async () => {
          const {seenRect} = await window.__lfCheckApi();
          const box = window.under.getBoundingClientRect();
          const shown = seenRect(window.under, new Map());
          return shown.right - shown.left >= box.width - 1;
        }"""
    )
    assert whole


def test_a_tab_into_a_popover_over_an_open_view_leaves_the_view_open(browser, serve):
    """The top layer paints over the panel, so a popover standing over an open view is
    in front of the user and the panel's cover takes none of it (dom/geometry.js,
    `covered`): a Tab's arrival there leaves the view open, as it does a stop the view
    stands clear of."""
    popover = (
        '<div id="pop" popover="manual" style="position:fixed;inset:auto 0 120px 0;'
        'margin:0 auto;width:360px"><button id="in-pop">Inside</button></div></main>'
    )
    page = floating(
        browser, serve(LONG_PAGE.replace("</main>", popover, 1), comments=12)
    )
    open_threads(page)
    expect(page.locator(".lf-fp-thread")).to_have_count(12)
    settled(page)
    reading = page.evaluate(
        """async () => {
          const {seenRect} = await window.__lfCheckApi();
          const {focusDestination} = await window.__lfWidgetApi();
          document.querySelector('#pop').showPopover();
          const button = document.querySelector('#in-pop');
          const view = document.querySelector('.lf-fp-view').getBoundingClientRect();
          const box = button.getBoundingClientRect();
          focusDestination(button, 'step');
          const seen = seenRect(button, new Map());
          return {over: box.top < view.bottom && box.bottom > view.top
                    && box.left < view.right && box.right > view.left,
                  whole: Boolean(seen) && seen.bottom - seen.top >= box.height - 0.5};
        }"""
    )
    assert reading == {"over": True, "whole": True}
    expect(page.locator("#in-pop")).to_be_focused()
    rendered(page)
    expect(page.locator(".lf-fp-view:not([data-lf-leaving])")).to_have_count(1)


def test_an_arrival_the_opening_view_will_cover_puts_it_away(browser, serve):
    """Whether the panel stands over an arrival is read where its box comes to rest, not
    where its motion has drawn it so far (dom/geometry.js, `covered`): a Tab's arrival at a
    stop at the page's foot while Threads is still opening over it puts the view away,
    as it does once the view stands open, and the stop ends in sight."""
    # The Tab leaves a stop the view never covers, above where it comes to rest: a key
    # pressed on a stop the user can't see lets go of it first (panel/page-keys/controller.js).
    foot = (
        '<p><button id="before">Before the foot</button></p>'
        '<div style="height:450px"></div>'
        '<p><button id="foot" style="width:100%">At the foot</button></p></main>'
    )
    page = floating(browser, serve(LONG_PAGE.replace("</main>", foot, 1), comments=12))
    # The page ends at its last stop, with no room kept below it.
    without_end_room(page)
    page.evaluate(
        "() => scrollTo({top: document.scrollingElement.scrollHeight,"
        " behavior: 'instant'})"
    )
    scroll_settled(page)
    page.locator(".lf-floating-panel").evaluate(
        """host => {
          for (const motion of ["--lf-motion-disclosure", "--lf-motion-box-resize",
                                "--lf-motion-view-in"])
            host.style.setProperty(motion, "3s");
        }"""
    )
    dev_browser.open_threads(page)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(page.locator("#foot")).to_be_focused()
    expect(page.locator(".lf-fp-view:not([data-lf-leaving])")).to_have_count(0)
    # The box shrinks only once the leaving view's fade ends (panel/floating-panel.js),
    # so wait for the panel to stand closed rather than for the motions playing now.
    panel_settled(page, open=False)
    seen = page.evaluate(
        """async () => {
          const {seenRect} = await window.__lfCheckApi();
          return Boolean(seenRect(document.querySelector('#foot'), new Map()));
        }"""
    )
    assert seen


def test_a_page_s_own_conversation_reader_takes_the_panel_s_threads(browser, serve):
    """A package that draws the page's conversations itself keeps that place under the
    panel (host/application.js, `registerThreadPresentation`, `yields`): the page starts
    without a fault, and a thread opened from the panel's Threads opens in the
    package's reader rather than above the row."""
    from render_cases_interaction import package_workspace

    page = floating(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    inventory.locator(".lf-fp-thread", has_text="Keep it concise.").click()
    expect(workspace.get_by_text("One paragraph.")).to_be_visible()
    expect(page.locator(panel_view("thread"))).to_have_count(0)
    expect(inventory).to_have_count(0)


def test_a_conversation_reader_arriving_later_takes_the_open_thread(browser, serve):
    """A page's own reader registered while the panel shows a thread takes that thread
    (host/application.js, `yielded`): the panel's view goes and the reader is asked to show
    it, at the message the user was located on, rather than the panel standing open on a
    conversation it no longer draws."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    # The user is located on a message, which goes with the panel's reader.
    view.get_by_role("button", name="Edit message").focus()
    stood_on = view.locator(".lf-msg").first.get_attribute("data-lf-message")
    assert stood_on
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          document.querySelector('main').append(host);
          window.revealed = [];
          api.registerThreadPresentation(host, {
            render: () => {},
            reveal: (key, request) => { window.revealed.push(request); },
          });
        }"""
    )
    expect(view).to_have_count(0)
    page.wait_for_function("() => window.revealed.length === 1")
    # It takes the user's place too: the message they stood on, with focus.
    asked = page.evaluate(
        "() => ({focus: window.revealed[0].focus, part: window.revealed[0].part,"
        " message: window.revealed[0].message})"
    )
    assert asked["focus"] is not False
    assert asked["part"] == "message"
    assert asked["message"] == stood_on


def test_a_package_s_whole_thread_takes_its_notice_where_a_card_does(browser, serve):
    """A package that names a whole thread and none of its head's places
    (`parts.thread`, no `head`): Leaf draws the thread, and news that would move it
    waits behind the notice beside its first message's head, as a card's does, which
    stands there from its first paint."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          host.id = 'reader';
          // Over the page, so drawing it moves none of the page's words.
          host.style = 'position: fixed; inset: 0 0 auto auto; width: 320px';
          document.querySelector('main').append(host);
          window.reader = api.registerThreadPresentation(host, {
            render: (collection, parts) => {
              for (const thread of collection.threads) {
                const outlet = document.createElement('div');
                host.replaceChildren(outlet);
                parts.thread(thread.key, outlet);
              }
            },
            reveal: () => {},
          });
          await window.reader.update();
        }"""
    )
    reader = page.locator("#reader")
    expect(reader.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    agent_said(serve.page_dir, root, "Forty-eight hours covers the first cohort.")
    told(page)
    expect(reader.locator(".lf-thread-content > .lf-thread-news")).to_have_text("1 new")
    expect(reader.locator(".lf-msg")).to_have_count(1)
    assert page.evaluate("() => window.reader.primary")


# A package's reader that stands a thread's head controls and reply box apart, in its
# own shadow tree, beside the outlet that holds the thread, and asks for its quote
# (`parts.thread`'s `head`, `reply` and `quote`).
APART_READER = """async (outside) => {
  const api = await window.__lfWidgetApi();
  const host = document.createElement('div');
  host.id = 'reader';
  host.style = 'position: fixed; inset: 0 0 auto auto; width: 320px';
  document.querySelector('main').append(host);
  const root = host.attachShadow({ mode: 'open' });
  const stray = document.createElement('span');
  document.body.append(stray);
  window.reader = api.registerThreadPresentation(host, {
    render: (collection, parts) => {
      for (const thread of collection.threads) {
        const news = document.createElement('span');
        const controls = document.createElement('span');
        const outlet = document.createElement('div');
        const reply = document.createElement('div');
        root.replaceChildren(news, controls, outlet, reply);
        parts.thread(thread.key, outlet, {
          head: { news: outside ? stray : news, controls },
          reply: { outlet: reply },
          quote: true,
        });
      }
    },
    reveal: () => {},
  });
  try {
    await window.reader.update();
    return 'drawn';
  } catch {
    return 'refused';
  }
}"""


def test_a_package_s_places_for_a_thread_s_parts_take_them_as_its_outlet_does(
    browser, serve
):
    """Every place a package names for a thread's parts is held to what its outlet is:
    one outside the widget refuses the update, and one in the widget's shadow tree takes
    the part through a slot, so the document's styles reach Resolve, the notice and the
    reply box as they reach the messages. The quote the package asks for reads as the
    panel's does, in three lines under the label that opens them whole. Reopen there
    lands in the reply box, wherever the package stands it, as a card's does."""
    url = serve(LONG_PAGE)
    words = "The earlier plan required a manual review before every rollout. " * 6
    panel_comment(
        serve.page_dir,
        "Is the window long enough?",
        {"section": "gone", "quote": words + "FINAL WORDS"},
    )
    page = floating(browser, url)
    assert page.evaluate(APART_READER, True) == "refused"
    # The refused reader gives its place back to Leaf's own.
    page.wait_for_function("() => !window.reader.primary")
    consume_browser_errors(
        page,
        "leaf: Presentation failed: A primary Thread outlet must remain inside its "
        "connected owner",
    )
    page.reload()
    wait_until_ready(page)
    assert page.evaluate(APART_READER, False) == "drawn"
    reader = page.locator("#reader")
    expect(reader.locator(".lf-msg")).to_have_count(1)
    # The parts stand in the widget's light tree, each slotted into its place.
    assert page.evaluate(
        """() => ['.lf-resolve', 'leaf-text', '.lf-msg'].map(
          (part) => Boolean(document.querySelector('#reader').querySelector(part)))"""
    ) == [True, True, True]
    quote = reader.locator(".lf-thread-quote")
    expect(quote).to_contain_text("FINAL WORDS")
    assert quote.evaluate("el => getComputedStyle(el).webkitLineClamp") == "3"
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    full = reader.locator(".lf-quote-label").get_by_role("button")
    expect(full).to_be_visible()
    full.click()
    expect(full).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    with sending(page, "the resolve"):
        reader.locator(".lf-resolve").click()
    with sending(page, "the reopen"):
        reader.locator(".lf-reopen").click()
    expect(reader.locator("leaf-text")).to_be_focused()


def test_a_reader_arriving_later_leaves_focus_the_user_moved_elsewhere(browser, serve):
    """The reader taking the panel's thread takes the user's place in it only where they
    stood in the panel: focus they moved to the page stays there."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(panel_view("thread"))).to_be_visible()
    page.evaluate(
        """async () => {
          const box = document.createElement('input');
          box.id = 'elsewhere';
          box.style.cssText = 'position: fixed; top: 8px; left: 8px';
          document.querySelector('main').prepend(box);
          box.focus();
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          document.querySelector('main').append(host);
          api.registerThreadPresentation(host, { render: () => {}, reveal: () => {} });
        }"""
    )
    expect(page.locator(panel_view("thread"))).to_have_count(0)
    expect(page.locator("#elsewhere")).to_be_focused()


@pytest.mark.parametrize("hidden_by", ["draft", "fold"])
def test_floating_status_records_feedback_only_when_its_words_show(
    browser, serve, request, hidden_by
):
    """Authored status words retain their exact source through the native placeholder
    slot and folded peek. A draft, focus, or folded panel cannot claim them visible.
    """
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    if hidden_by == "draft":
        write(field(page), "Keep my unfinished question")
    else:
        page.locator(".lf-fp-leaf").click()
        page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
        page.mouse.move(5, 5)
    progress = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Reading the diagnostic transport.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)

    def batch_has(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    def visible():
        return [
            row
            for row in interaction_model.read_interactions(serve.page_dir)
            if row["type"] == "reply_visible" and row.get("reply_id") == progress["id"]
        ]

    # A later acknowledged gesture flushes all observations of the hidden words.
    with page.expect_response(lambda response: batch_has(response, "click")):
        page.locator("h1").first.click()
    assert visible() == []
    if hidden_by == "draft":
        field(page).click()
        page.keyboard.press("ControlOrMeta+a")
        with page.expect_response(lambda response: batch_has(response, "keydown")):
            page.keyboard.press("Backspace")
        expect(field(page)).to_have_attribute("placeholder", re.compile("^Comment"))
        expect(
            field(page).locator(".lf-compose-placeholder > .lf-key-badge")
        ).to_have_text("⏎")
        assert visible() == []
    with page.expect_response(lambda response: batch_has(response, "reply_visible")):
        if hidden_by == "draft":
            page.locator("h1").first.click()
        else:
            page.locator(".lf-fp-leaf").hover()
            expect(page.locator(PREVIEW)).to_contain_text(
                "Reading the diagnostic transport"
            )
    rows = visible()
    assert len(rows) == 1
    assert rows[0]["input_id"] == root
    assert rows[0]["presentation_kind"] == "status_words"
    assert rows[0]["surface"] == "panel"
    assert "text" not in rows[0]


def test_only_the_folded_leaf_shows_a_status_peek(browser, serve):
    """The row's status and errors remain inline; its menu carries the full reading.
    The leaf's preview names what it opens and the key that presses it, and says the
    status under that only when the leaf is folded."""
    page = floating(browser, serve(LONG_PAGE))
    peek = page.locator(PREVIEW)
    leaf = page.locator(".lf-fp-leaf")
    seat = page.locator(".lf-fp-field")
    expect(field(page)).to_have_attribute("placeholder", re.compile(r"^Away\b"))
    assert seat.get_attribute("title") is None
    leaf.hover()
    expect(peek.locator(".lf-preview-word")).to_have_text("Page menu")
    expect(peek.locator(".lf-preview-keys")).to_have_text("o")
    expect(peek.locator(".lf-preview-detail")).to_have_count(0)
    seat.hover()
    rendered(page)
    expect(peek).to_be_hidden()

    leaf.click()
    expect(page.locator(panel_view("menu"))).to_contain_text("Updates are saved.")
    expect(peek).to_be_hidden()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    # Escape hands the keyboard back to the leaf, where the user didn't go, so it
    # previews nothing that would stand in front of their next Escape.
    expect(leaf).to_be_focused()
    expect(peek).to_be_hidden()
    page.locator("body").click(position={"x": 5, "y": 5})
    page.evaluate(
        "async text => (await window.__lfCheckApi()).raiseError(text)",
        "Couldn't save the draft",
    )
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    seat.hover()
    rendered(page)
    expect(peek).to_be_hidden()
    page.locator("body").click(position={"x": 5, "y": 5})
    page.keyboard.press(".")
    # The preview stands by the leaf, so it is read where the leaf comes to rest.
    panel_settled(page, open=False)
    leaf.hover()
    expect(peek).to_be_visible()
    expect(peek).to_contain_text("Away right now.")
    leaf.click()
    expect(peek).to_be_hidden()
    panel_settled(page, open=False)
    # The leaf travels to where the expanded row stands once its layout has settled, and
    # a preview stands by it on its way, so the keyboard reads it once it has arrived.
    rendered(page)
    panel_settled(page, open=False)
    # Tab back onto the expanded leaf: keyboard focus must not repeat the status.
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(leaf).to_be_focused()
    expect(peek.locator(".lf-preview-word")).to_have_text("Page menu")
    expect(peek.locator(".lf-preview-detail")).to_have_count(0)


# A status longer than the panel's field holds on its one line at any width.
CUT_STATUS = (
    "Editing the README for your 17 comments: cuts, headings, the checks and data"
    " line; checking what Claude Code's idle compaction and cache lifetime do"
)


def test_floating_menu_tracks_stalled_detail_hidden_by_a_draft(browser, serve, request):
    """The stalled summary carries no authored detail; its menu's Last said words do.
    A draft keeps the row's placeholder hidden, so that menu is their first exposure.
    """
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    write(field(page), "Keep my unfinished question")
    progress = declare_work(
        serve.page_dir,
        "Reading the diagnostic transport.",
        item=root,
        ts="2020-01-01T00:00:00+00:00",
        agent="Codex",
        session="codex-thread",
    )
    told(page)

    def traced(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    def feedback():
        return [
            row
            for row in interaction_model.read_interactions(serve.page_dir)
            if row["type"] == "reply_visible" and row.get("reply_id") == progress["id"]
        ]

    with page.expect_response(lambda response: traced(response, "click")):
        page.locator("h1").first.click()
    assert feedback() == []
    with page.expect_response(lambda response: traced(response, "reply_visible")):
        page.locator(".lf-fp-leaf").click()
        expect(page.locator(".lf-fp-explain")).to_contain_text(
            "Last said: Reading the diagnostic transport"
        )
    rows = feedback()
    assert len(rows) == 1
    assert rows[0]["input_id"] == root
    assert rows[0]["presentation_kind"] == "status_words"
    assert rows[0]["surface"] == "panel"
    assert "text" not in rows[0]


def test_the_empty_field_says_the_agent_s_status_until_the_caret_is_in(browser, serve):
    """At rest the empty field says what the agent is doing, in the status's words and
    dimmer than anything written there, and while the work runs it carries the one sheen
    that marks work under way, standing still under reduced motion and once the work
    ends, and never hiding the words under forced colours. Clicking in gives the
    placeholder to where the words go; words in the field need no additional line. It never names who reads them, since every word here goes
    to the one agent."""
    url = serve(LONG_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = open_page(browser, url, init_script=EDITOR_ROOTS)
    status = re.compile(r"Drafting the rollout")
    expect(field(page)).to_have_attribute("placeholder", status)
    # The sheen runs on the field's placeholder part, inside the field's closed tree,
    # where no animation list reaches: a moving mask dims the words, and the field reads
    # differently from one moment to the next.
    words = page.locator(".lf-fp-field .lf-compose-placeholder-words")
    ink = """node => getComputedStyle(node).color"""

    def sheen(running):
        page.wait_for_function(
            """running => {
              const host = document.querySelector('.lf-fp-field leaf-text');
              const part = window.editorRoots.get(host)
                .querySelector('[part~="placeholder"]');
              return (getComputedStyle(part).maskImage !== 'none') === running;
            }""",
            arg=running,
        )

    sheen(True)
    box = page.locator(".lf-fp-field").bounding_box()
    animation = field(page).evaluate_handle("""node => window.editorRoots.get(node)
      .querySelector('[part~="placeholder"]').getAnimations()
      .find(animation => animation.animationName === 'lf-sheen')""")
    assert animation.evaluate("animation => animation?.playState") == "running"
    # The highlight spends part of each sweep beyond this short line. Compare known
    # phases so two captures cannot both land on that unchanged part of the sweep.
    animation.evaluate("animation => { animation.pause(); animation.currentTime = 0; }")
    first = page.screenshot(clip=box)
    animation.evaluate("animation => animation.currentTime = 1000")
    assert page.screenshot(clip=box) != first, "the working status stands still"
    animation.evaluate("animation => animation.play()")
    animation.dispose()
    # Still under reduced motion, in a face well short of the ink words are written in.
    page.emulate_media(reduced_motion="reduce")
    sheen(False)
    match = re.search(r"/\s*([\d.]+)\)$", words.evaluate(ink))
    assert match is not None
    alpha = float(match.group(1))
    assert alpha < 0.7, f"the resting status reads at {alpha:.0%} of ink"
    page.emulate_media(reduced_motion="no-preference")
    sheen(True)
    # Forced colours drop the mask but keep the animation, so the words stay whole.
    page.emulate_media(forced_colors="active")
    sheen(False)
    page.emulate_media(forced_colors="none")
    sheen(True)

    field(page).click()
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Comment… ⏎"))
    sheen(False)
    page.keyboard.type("Could")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")

    page.mouse.click(5, 5)
    expect(field(page)).to_have_attribute("placeholder", status)
    sheen(True)
    declare_idle(serve.page_dir)
    told(page)
    expect(field(page)).not_to_have_attribute("placeholder", status)
    sheen(False)


def test_a_refused_key_is_an_error_the_field_says(browser, serve):
    """A report reads dimly in the field. A refused key asks the user to act, so
    the field says it as an error and the menu keeps the full status. Focus leaves
    the error in the field until the user writes."""
    url = serve(LONG_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    words = page.locator(".lf-fp-field .lf-compose-placeholder-words")
    peek = page.locator(".lf-fp-peek")

    def alpha():
        color = words.evaluate("node => getComputedStyle(node).color")
        found = re.search(r"/\s*([\d.]+)\)$", color)
        return float(found.group(1)) if found else 1.0

    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Drafting the rollout")
    )
    page.locator(".lf-fp-field").hover()
    expect(peek).to_be_hidden()

    page.route("**/api/state*", lambda route: route.fulfill(status=401, body="{}"))
    declare_idle(serve.page_dir)
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^This tab lost access")
    )
    assert alpha() > 0.6, "the refused key reads as dim as a report"
    expect(peek).to_be_hidden()
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(panel_view("menu"))).to_contain_text(
        "This tab lost access — open the link again"
    )
    page.keyboard.press("Escape")
    field(page).click()
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    expect(peek).to_be_hidden()
    # The refused reads recur on the page's clock until it closes.
    page.close()
    consume_browser_errors(page, http_error_console(401))


def test_nothing_passing_interrupts_the_user_writing(browser, serve):
    """A passing notice is said in the empty field's place. A draft keeps the field
    without opening a second line, whether or not it has focus. While writing:
    news goes unsaid but for the live region, there and over an open view, where the
    leaf's peek stays down. On a folded panel the peek says any notice."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    say = "async (text) => (await window.__lfCheckApi()).notice(text)"
    peek = page.locator(".lf-fp-peek")
    page.evaluate(say, "Saved for later")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Saved for later")
    )
    field(page).click()
    expect(field(page)).to_have_attribute("placeholder", re.compile(r"^Comment… ⏎"))
    write(field(page), "Could the rollback cover the weekend?")
    page.evaluate(say, "Saved for later")
    page.mouse.click(5, 5)
    expect(field(page)).to_have_js_property(
        "value", "Could the rollback cover the weekend?"
    )

    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(panel_view("thread"))).to_be_visible()
    write(field(page), "And the weekend?")
    page.evaluate(say, "2 agent messages in 2 threads")
    expect(peek).to_be_hidden()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Folded to the leaf, the panel has no field, and the leaf's peek says it.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    page.evaluate(say, "Reconnected")
    expect(peek).to_be_visible()
    expect(peek).to_have_text("Reconnected")


# An error's own Dismiss, beside the copy that names the same error.
DISMISS = re.compile(r"^Dismiss: ")


def test_an_error_stands_in_the_field_until_edited_then_waits_in_the_menu(
    browser, serve
):
    """An error the page raises stands in the field's status place while the field can
    say it: about its editor, or about nothing while the editor is empty, the newest of
    them. The user's first edit passes every error the field could say to Errors in the
    leaf's menu, where a dot on the leaf and on the menu's Errors marks each the field
    doesn't say until the list is opened, and each can be dismissed. Over
    words its editor holds, an error covers them until the first key there: an edit
    or a caret move lands in those words, and Enter only uncovers them, so nothing
    sends them unseen.
    An error the field cannot say, such as one about nothing while the user has words
    there, goes straight to the list."""
    url = serve(LONG_PAGE)
    page = floating(browser, url)
    raise_error = """async ([text, onField]) => {
      const subject = onField ? document.querySelector('.lf-fp-field leaf-text') : null;
      window.latestError = (await window.__lfCheckApi()).raiseError(text, { subject });
    }"""
    panel = page.locator(".lf-floating-panel")
    cover = page.locator(".lf-fp-field .lf-compose-error")
    dot = page.locator(".lf-fp-leaf .lf-fp-error-dot")
    value = "node => node.value"
    page.evaluate(raise_error, ["Couldn't load v1", False])
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    expect(dot).to_be_hidden()
    # A newer one takes the field, and the one it covers waits under the leaf's dot.
    page.evaluate(raise_error, ["That reaction target is no longer available", False])
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^That reaction target is no longer available")
    )
    expect(dot).to_be_visible()
    # Clicking in is no edit: the errors stay until the user writes, and the first
    # key passes both of them.
    field(page).click()
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    page.keyboard.type("Could")
    expect(field(page)).to_have_attribute("data-lf-says", "destination")
    expect(dot).to_be_visible()

    # Over words its editor holds, an error covers them, and Enter only uncovers
    # them, sending nothing, with the caret at their end for the next key.
    page.evaluate(raise_error, ["Could not add image — disk full", True])
    expect(cover).to_have_text("Could not add image — disk full")
    assert field(page).evaluate(value) == "Could"
    sent = len(events_model.read_events(serve.page_dir))
    page.keyboard.press("Enter")
    expect(cover).to_be_hidden()
    assert field(page).evaluate(value) == "Could"
    page.keyboard.type(" it")
    assert field(page).evaluate(value) == "Could it"
    # A caret key uncovers them too, moving the caret as it would.
    page.evaluate(raise_error, ["Could not add image — disk full", True])
    page.evaluate("() => { window.fieldError = window.latestError; }")
    expect(cover).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(cover).to_be_hidden()
    assert field(page).evaluate("node => node.selectionStart") == len("Could i")
    assert len(events_model.read_events(serve.page_dir)) == sent
    # One about nothing while the user has words goes straight to the list.
    page.evaluate(raise_error, ["Draw on or beside something on the page.", False])
    expect(cover).to_be_hidden()
    expect(field(page)).to_have_attribute("data-lf-says", "destination")

    # The menu's Errors wears the leaf's dot, so the row the dot leads to is plain.
    errors = panel_menu(page).locator('[data-lf-row="errors"]')
    expect(errors).to_contain_text("5")
    expect(errors.locator(".lf-fp-error-dot")).to_be_visible()
    errors.click()
    listed = page.locator(panel_view("errors")).locator(".lf-fp-error")
    expect(listed).to_have_count(5)
    expect(listed.first).to_contain_text("Draw on or beside something")
    expect(dot).to_be_hidden()
    listed.first.get_by_role("button", name=DISMISS).click()
    expect(listed).to_have_count(4)
    expect(listed.first.get_by_role("button", name=DISMISS)).to_be_focused()
    # News waits until the list is opened again, leaving the error being read and
    # its focused Dismiss in place. Only errors actually shown lose their dot.
    settled(page)
    reading = listed.first.get_by_role("button", name=DISMISS).element_handle()
    before = reading.bounding_box()
    one_frame(page)
    page.evaluate(raise_error, ["Another image could not be attached", False])
    one_frame(page)
    assert reading.bounding_box() == before
    assert reading.evaluate("node => node === document.activeElement")
    expect(listed).to_have_count(4)
    expect(dot).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    panel_menu(page).locator('[data-lf-row="errors"]').click()
    expect(listed).to_have_count(5)
    expect(listed.first).to_contain_text("Another image could not be attached")
    expect(dot).to_be_hidden()

    # A condition that ends clears its words immediately but keeps their space,
    # so the next error's Dismiss does not move under the reader.
    settled(page)
    reading = listed.nth(1).get_by_role("button", name=DISMISS).element_handle()
    reading.focus()
    before = reading.bounding_box()
    page.evaluate("() => window.latestError.clear()")
    one_frame(page)
    expect(listed.first).to_be_hidden()
    assert reading.bounding_box() == before
    assert reading.evaluate("node => node === document.activeElement")
    # Clearing the focused error also hands focus to the next live Dismiss, from its
    # copy press too, whose button stands in the copy control's own tree.
    listed.nth(1).get_by_role("button", name=re.compile(r"^Copy with page")).focus()
    page.evaluate("() => window.fieldError.clear()")
    expect(listed.nth(1)).to_be_hidden()
    expect(listed.nth(2).get_by_role("button", name=DISMISS)).to_be_focused()
    listed.nth(2).get_by_role("button", name=DISMISS).click()
    expect(listed.nth(2).get_by_role("button", name=DISMISS)).to_be_focused()
    # Escape steps back to the menu, and from it puts the view away.
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    expect(dot).to_be_hidden()

    # Folded, the panel says no error; the leaf's dot marks one raised there.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    page.evaluate(raise_error, ["That selected passage is unavailable", False])
    expect(dot).to_be_visible()


def test_an_error_copies_with_where_it_was_raised_and_which_leaf_ran(browser, serve):
    """Each error in the menu's Errors list copies itself with what a person or an
    agent needs to look into it: its words, when, on which revision and from which
    code it was raised, however the page has moved on since, and which Leaf runs the
    page, but never the page's link, which grants access."""
    url = serve(LONG_PAGE)
    page = floating(browser, live_url(url))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate(
        """async () => {
          const api = await window.__lfCheckApi();
          window.raisedFrom = () => api.raiseError('That writing place is unavailable');
          window.raisedFrom();
        }"""
    )
    field(page).click()
    page.keyboard.type("x")
    stamp_page(
        serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), "2"
    )
    wait_for_revision(page, 2)
    panel_menu(page).locator('[data-lf-row="errors"]').click()
    listed = page.locator(panel_view("errors")).locator(".lf-fp-error")
    listed.get_by_role(
        "button", name=re.compile(r"^Copy with page details: That writing place")
    ).click()
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Error copied"))
    raised, *details = page.evaluate("navigator.clipboard.readText()").split("\n\n")
    assert raised.startswith("Leaf error: That writing place is unavailable\nraised: ")
    assert "\nrevision: 1\n" in raised
    assert "raisedFrom" in raised
    layer = next(block for block in details if block.startswith("Leaf layer\n"))
    assert "\nrevision: 2\n" in layer
    assert not any(re.search(r"[?&]t=", block) for block in [raised, *details])


def test_a_walk_says_its_position_in_the_panel(browser, serve):
    """A walk's position is said where the panel says whatever passes, not against the
    window: in the empty field's place, as a notice is. The room the page shows (dom/geometry.js, `shownWindow`) runs from the window's
    head to the panel's row whether or not a walk is under way. The position goes
    unsaid once the caret is in the field, though its moment has not passed, and stays
    unsaid once the comment's thread opens over the row and the send leaves the user
    on it: on the line over the field, and in the leaf's peek, which would lie on the
    thread's last words."""
    heading = "<h3>How should the schema migrate?</h3>"
    tall = "<p>The old schema has three tables, each a year of records.</p>" * 30
    page = floating(browser, serve(OBLIGATION_PAGE.replace(heading, heading + tall)))
    room = """async () => {
      const shown = (await window.__lfWidgetApi()).shownWindow();
      return {top: shown.top, bottom: shown.bottom};
    }"""
    foot = page.locator(".lf-fp-row").bounding_box()["y"]
    before = page.evaluate(room)
    assert before["bottom"] == pytest.approx(foot, abs=1)

    page.locator("body").focus()
    page.keyboard.press("m")
    expect(field(page)).to_have_attribute("data-lf-says", "notice")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("1 of 2 waiting on me")
    )
    assert page.evaluate(room) == before

    # Once the landing's scroll has stopped, the obligation is the block being read.
    page.wait_for_function(
        """() => new Promise((done) => {
          const y = scrollY;
          requestAnimationFrame(() => requestAnimationFrame(() => done(scrollY === y)));
        })"""
    )
    field(page).click()
    write(field(page), "Is this the one?")
    page.keyboard.press("Enter")
    expect(page.locator(panel_view("thread"))).to_be_focused()
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Reply… c"))
    expect(page.locator(".lf-fp-peek")).to_be_hidden()


def test_a_walk_s_position_gives_the_field_back_to_the_status(browser, serve):
    """A walk's position answers its step for a notice's moment, and then the field
    says the agent's status again, though the walk still stands where it landed, so
    the agent's updates show while the user reads there. Each step says its own
    position for a moment of its own."""
    page = floating(clocked(browser), serve(OBLIGATION_PAGE))
    page.locator("body").focus()
    page.keyboard.press("m")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^1 of 2 waiting on me")
    )
    rendered(page)
    page.clock.run_for(
        page.evaluate("async () => (await window.__lfCheckApi()).NOTICE_MS")
    )
    expect(field(page)).to_have_attribute("data-lf-says", "status")
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("waiting on"))
    position = page.evaluate(
        "async () => (await window.__lfCheckApi()).walkPosition()?.position"
    )
    assert position == 1
    page.keyboard.press("m")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^2 of 2 waiting on me")
    )


# A widget's step saying its place on a paragraph of the long page (`lf-walk`), among
# three stops whose first and last are the paragraphs `ends` names.
SAY_PLACE = """([stop, position, ends]) => document.getElementById(stop).dispatchEvent(
  new CustomEvent('lf-walk', {bubbles: true, composed: true, detail: {
    noun: 'Stop', position, total: 3,
    list: ends.map((end) => document.getElementById(end))}}))"""


def test_a_widget_s_place_goes_with_its_moment_or_the_user_s_next_step(browser, serve):
    """The field says the place a widget's step says for the step's moment, as it says
    a walk of Leaf's own, but the widget gives no reader to keep the place true, so
    none stands after the moment. A next step that says none, its stops all standing in
    view, takes the last step's place with it rather than leaving it over a stop the
    user has left."""
    page = floating(clocked(browser), serve(LONG_PAGE))
    walk = "async () => (await window.__lfCheckApi()).walkPosition()?.text ?? null"
    page.evaluate(SAY_PLACE, ["p0", 1, ["p0", "p59"]])
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Stop 1 of 3"))
    page.evaluate(SAY_PLACE, ["p1", 2, ["p0", "p1"]])
    # Read at once: the first step's moment, which would also end its place, runs on.
    assert page.evaluate(walk) is None
    expect(field(page)).to_have_attribute("data-lf-says", "status")

    page.evaluate(SAY_PLACE, ["p0", 1, ["p0", "p59"]])
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Stop 1 of 3"))
    rendered(page)
    page.clock.run_for(
        page.evaluate("async () => (await window.__lfCheckApi()).NOTICE_MS")
    )
    expect(field(page)).to_have_attribute("data-lf-says", "status")
    assert page.evaluate(walk) is None


def test_a_thread_s_field_says_its_reply_beside_the_walk_s_position(browser, serve):
    """A thread open in the panel keeps saying that its field takes the reply, with the
    key that enters it, when the thread walk stands on it: the walk's place stands
    before the reply, beside the leaf, and Reply and its key stand at the field's end,
    where `c` writes."""
    page = floating(browser, serve(LONG_PAGE))
    write(field(page), "Could the rollback cover the weekend?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    view = page.locator(panel_view("thread"))
    expect(view).to_be_visible()
    view.focus()
    page.keyboard.press("t")
    expect(lead(page)).to_contain_text(re.compile(r"\b1 of 1$"))
    expect(field(page)).to_have_attribute("data-lf-says", "turn")
    expect(field(page)).to_have_attribute("placeholder", re.compile(r"^Reply\b.* c$"))
    key = page.locator(".lf-fp-field .lf-compose-placeholder kbd")
    expect(key).to_have_text("c")
    expect(key).to_be_visible()
    hint = page.locator(".lf-fp-field .lf-compose-placeholder").bounding_box()
    assert key.bounding_box()["x"] > hint["x"] + hint["width"] / 2, (
        "Reply ends the field"
    )
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    expect(lead(page)).to_be_hidden()


def test_an_open_thread_s_reply_stands_only_while_its_key_enters_the_field(
    browser, serve
):
    """An open thread's field ends in Reply and the key that enters it only while that
    key enters it, as the page's field ends in Comment and its key: once a walk goes on
    to a stop the thread's view leaves in sight, `c` writes there, and Reply goes with
    its key, leaving the walk's place alone beside the leaf."""
    url = serve(OBLIGATION_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view).to_be_visible()
    placeholder = page.locator(".lf-fp-field .lf-compose-placeholder")
    reply = placeholder.locator(".lf-compose-placeholder-enters")
    key = placeholder.locator("kbd")
    expect(reply).to_have_text("Reply…")
    expect(key).to_have_text("c")
    expect(field(page)).to_have_attribute("placeholder", "Reply… c")

    page.keyboard.press("m")
    expect(lead(page)).to_have_text("1 of 2 waiting on me")
    expect(view).to_be_visible()
    expect(placeholder).not_to_contain_text("Reply")
    expect(key).to_have_text("")
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("Reply"))

    view.focus()
    expect(reply).to_have_text("Reply…")
    expect(key).to_have_text("c")


END_KEY = """() => {
  const keys = [...document.querySelectorAll('.lf-fp-field kbd')].filter(
    (k) => k.textContent && k.checkVisibility({ visibilityProperty: true }));
  return keys.length ? keys.at(-1).getBoundingClientRect().right : null;
}"""


def test_the_field_s_end_press_stands_one_place_beside_the_leaf(browser, serve):
    """The empty field's end press, its word and key, stands as far from the leaf in an
    open thread as on the page, and as far once the user has written in the thread's
    reply and stepped out of it: the field keeps the room of its corner only while
    Dictate or Send stands there, which is never beside the end press."""
    url = serve(OBLIGATION_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    on_page = page.evaluate(END_KEY)
    assert on_page is not None, "the page's field ends in a press and its key"
    page.keyboard.press("t")
    expect(field(page)).to_have_attribute("placeholder", "Reply… c")
    assert page.evaluate(END_KEY) == on_page, "Reply stands where the page's press does"
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(field(page)).not_to_be_focused()
    expect(field(page)).to_have_attribute("placeholder", "Reply… c")
    assert page.evaluate(END_KEY) == on_page, (
        "Reply stands there once the user has stepped out of the reply"
    )


def test_the_leaf_s_menu_stays_in_the_window_over_a_tall_view(browser, serve):
    """The leaf opens its menu in the place of the view open above the row, however
    tall that stood, above the leaf, and within a short window it keeps every row
    reachable."""
    page = floating(browser, serve(LONG_PAGE, comments=20))
    page.set_viewport_size({"width": 1280, "height": 360})
    open_threads(page)
    expect(page.locator(panel_view("threads"))).to_be_visible()
    settled(page)
    menu = panel_menu(page)
    expect(menu.locator(".lf-fp-item").first).to_be_visible()
    box = menu.bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    assert box["y"] >= 0, f"the menu's top stands {-box['y']:.0f}px above the window"
    assert box["y"] + box["height"] <= leaf["y"], "the menu covers the leaf"
    last = menu.locator(".lf-fp-item").last
    last.scroll_into_view_if_needed()
    expect(last).to_be_in_viewport()


def test_a_toggle_s_notice_shows_only_where_no_standing_words_say_it(browser, serve):
    """Annotations hidden is where the user stands, which the page field's standing
    words say at once. Hiding them offers Show annotations, the press that brings them
    back, which those words don't, so its notice shows there too, with the press and
    its key at the field's end, and a click on the press shows them; showing them
    again only undoes what the field said, so the field leaves its notice to them.
    Folded, the leaf's peek says no standing words, so it shows both."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    hidden = page.locator(".lf-chrome[data-lf-annotations-hidden]")
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect_panel_says(page, "Annotations hidden · Show annotations g H")
    expect(page.locator(".lf-live")).to_have_text("Annotations hidden")
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    # Read once the press has drawn, while its notice's moment still stands.
    rendered(page)
    assert field(page).get_attribute("data-lf-says") == "status"
    assert "Annotations" not in (field(page).get_attribute("placeholder") or "")
    expect(page.locator(".lf-live")).to_have_text("Annotations shown")
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(hidden).to_have_count(1)
    page.locator(".lf-fp-field .lf-compose-press").click()
    expect(hidden).to_have_count(0)
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect_panel_says(page, "Annotations hidden")
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect_panel_says(page, "Annotations shown")


def test_on_a_touchscreen_hiding_annotations_offers_no_press(browser, serve):
    """A touchscreen shows no keys, and a press's word alone at the field's end reads as
    status rather than a control, so hiding the annotations from the menu offers no
    Show annotations there, and the field's standing words say where the user stands,
    with no notice repeating them."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
    page.locator(".lf-fp-leaf").tap()
    panel_tab(page, "Menu").tap()
    page.locator(".lf-fp-item", has_text="Annotations").first.tap()
    page.locator(".lf-fp-item", has_text="Hide annotations").tap()
    expect(page.locator(".lf-chrome[data-lf-annotations-hidden]")).to_have_count(1)
    expect_panel_says(page, "Annotations hidden")
    rendered(page)
    expect(field(page)).to_have_attribute("data-lf-says", "status")
    expect(page.locator(".lf-fp-field .lf-compose-press")).to_have_count(0)


def test_a_gesture_s_notice_with_a_press_stays_until_the_next_input(browser, serve):
    """Hiding the annotations answers the user's own gesture with a press, Show
    annotations, so its notice stands its time and then until the user's next input:
    an input within its time leaves it standing, and the first one after takes it."""
    page = floating(clocked(browser), serve(LONG_PAGE, comments=1))
    offered = page.locator(
        ".lf-fp-field .lf-compose-press", has_text="Show annotations"
    )
    moment = page.evaluate("async () => (await window.__lfCheckApi()).NOTICE_MS")
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+H")
    expect(offered).to_have_count(1)
    page.keyboard.press("ArrowDown")
    page.clock.run_for(moment * 2)
    rendered(page)
    expect(field(page)).to_have_attribute("data-lf-says", "notice")
    expect(offered).to_have_count(1)
    page.keyboard.press("ArrowDown")
    expect(offered).to_have_count(0)


def test_a_refused_resolve_takes_next_thread_from_under_the_pointer(held_events, serve):
    """A Resolve's notice stands no longer than its gesture does. A Resolve the log
    refuses puts the user back on its thread, so Next thread, which would walk them
    away from it, leaves the field's end, though the pointer rests on the panel."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    for words in ("Is the window long enough?", "Who watches the weekend?"):
        agent_said(serve.page_dir, panel_comment(serve.page_dir, words), "Noted.")
    page = floating(browser, url)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Is the window long enough?").click()
    next_thread = page.locator(".lf-fp-field .lf-compose-press", has_text="Next thread")
    with page.expect_request("**/api/event"):
        page.locator(".lf-fp-head .lf-resolve").click()
    expect(next_thread).to_have_count(1)
    [resolve] = [r for r in held if r.request.post_data_json["kind"] == "resolve"]
    resolve.fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    expect_panel_says(page, "Please retry")
    expect(next_thread).to_have_count(0)


def test_the_panel_folds_to_the_leaf_and_stays_folded(browser, serve):
    """Folding to the leaf, from the leaf's menu or its key, is a choice the panel
    keeps across a reload, until the leaf is pressed again; `c` still reaches the
    page's field, and Go-to's Threads door opens the panel's own Threads. Folded, the
    leaf stands as far from the window's right edge as from its foot."""
    url = serve(LONG_PAGE, comments=1)
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    expect(page.locator(".lf-fp-field")).to_be_hidden()
    settled(page)
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    window = page.viewport_size
    right = window["width"] - (leaf["x"] + leaf["width"])
    foot = window["height"] - (leaf["y"] + leaf["height"])
    assert right == pytest.approx(foot, abs=0.5), (right, foot)

    page.reload()
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    page.locator(".lf-fp-leaf").click()
    expect(panel).to_have_attribute("data-lf-rest", "row")
    expect(panel).not_to_have_attribute("data-lf-open", re.compile("."))

    page.locator("body").focus()
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(panel_view("threads"))).to_be_visible()


def test_folding_from_the_menu_draws_the_panel_folded_at_once(browser, serve):
    """The menu's Fold row folds as `.` does, and the leaf's dot is written once: the
    menu's put-away stands the empty field in the row, which says an error about
    nothing in the dot's place, and the fold then gives the dot back, so a press that
    drew the row's posture at each step would take the dot away and put it back. The
    browser fixture fails the test on that restated write (write_watch.js)."""
    page = floating(browser, serve(LONG_PAGE))
    page.evaluate(
        "async () => (await window.__lfCheckApi()).raiseError('Link not copied')"
    )
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    dot = page.locator(".lf-fp-leaf .lf-fp-error-dot")
    expect(dot).to_be_hidden()
    page.locator(".lf-fp-leaf").click()
    expect(dot).to_be_visible()
    panel_menu(page).locator(".lf-fp-item", has_text="Fold to the leaf").click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    expect(dot).to_be_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_leaf_travels_with_its_fold_and_reverses_from_where_it_stands(
    browser, serve, scheme
):
    """The mark rides the box into its corner and back, while the row's words come out
    of the box's leading edge clear of it; its button receives focus at once. Reversing starts from where it
    is drawn, and reduced motion takes the endpoint."""
    from io import BytesIO

    from PIL import Image

    page = floating(browser, serve(LONG_PAGE, comments=1))
    resized(page, 675, 898)
    page.emulate_media(reduced_motion="no-preference", color_scheme=scheme)
    field(page).click()
    # A picture wide enough to reach beyond the unfolding box's horizontal cut
    # exercises whether its top can hang above that box throughout the reveal.
    paste_image(field(page), solid_png(240, 120, (255, 128, 64)))
    shelf = page.locator(".lf-fp-box .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    expect(shelf.locator("img")).to_have_js_property("complete", True)
    page.keyboard.press("Escape")
    settled(page)
    # The panel's surface must expose its measured box before the first motion;
    # an opaque motion root leaves the ground clipped away behind the controls.
    expect(page.locator(".lf-fp-ground > .lf-box-fill").first).not_to_have_css(
        "clip-path", "inset(50%)"
    )
    page.evaluate("() => {" + HOLD_MOTION + "}")
    panel = page.locator(".lf-floating-panel")
    leaf = page.locator(".lf-fp-leaf")
    mark = panel.locator(".lf-fp-leaf > svg[data-lf-icon=leaf]")

    def reading():
        return mark.evaluate("""node => {
          const box = node.getBoundingClientRect();
          let opacity = 1;
          for (let at = node; at; at = at.parentElement)
            opacity *= Number(getComputedStyle(at).opacity);
          return {x: box.x + box.width / 2, y: box.y + box.height / 2, opacity};
        }""")

    def seek(at):
        page.evaluate(
            "at => __lfHeld.filter(a => a.playState !== 'idle')"
            ".forEach(a => { if (at >= a.effect.getTiming().duration) a.finish();"
            " else a.currentTime = at; })",
            at,
        )
        one_frame(page)
        return reading()

    def paints():
        pixels = Image.open(BytesIO(page.screenshot(clip=mark.bounding_box()))).convert(
            "L"
        )
        low, high = pixels.getextrema()
        assert isinstance(low, (int, float)) and isinstance(high, (int, float))
        assert high - low > 32, (low, high)

    def words_follow_box():
        # The field's words come out of the box's leading edge as it grows from the
        # leaf's side, and never stand under the leaf. The attachment hanging over the
        # field's start, across that edge, shows meanwhile, cut by no edge of it.
        edges = field(page).evaluate("""editor => {
          let cut = editor;
          while (getComputedStyle(cut).clipPath === 'none') cut = cut.parentElement;
          const sides = getComputedStyle(cut).clipPath.match(/[-\\d.]+px/g);
          const box = cut.getBoundingClientRect();
          return {words: box.left + parseFloat(sides[3]),
            end: box.right - parseFloat(sides[1]),
            leaf: document.querySelector('.lf-fp-leaf').getBoundingClientRect().left};
        }""")
        assert edges["end"] <= edges["leaf"] + 0.5, edges
        attachment = shelf.bounding_box()
        assert (
            attachment["x"] < edges["words"] < attachment["x"] + attachment["width"]
        ), ("the fixture must straddle the reveal edge", attachment, edges)
        pixels = Image.open(BytesIO(page.screenshot(clip=attachment))).convert("RGB")
        # Match the picture itself: subpixel text on the page can also be orange.
        assert any((r, g, b) == (255, 128, 64) for r, g, b in rgb_pixels(pixels))

    row = reading()
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    one_frame(page)
    first = seek(0)
    assert first == pytest.approx(row, abs=0.5)
    middle = seek(80)
    paints()
    folded = seek(300)
    target = leaf.bounding_box()
    assert row["x"] < middle["x"] < folded["x"]
    assert middle["opacity"] == folded["opacity"] == 1
    assert folded["x"] == pytest.approx(target["x"] + target["width"] / 2, abs=0.5)

    leaf.focus()
    page.keyboard.press("Enter")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    one_frame(page)
    assert seek(0) == pytest.approx(folded, abs=0.5)
    paints()
    seek(80)
    words_follow_box()
    assert seek(300) == pytest.approx(row, abs=0.5)
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    one_frame(page)

    # Turn back before arrival. The new tween's first frame is the old one's current
    # drawing, not either resting position, while focus takes its new target.
    middle = seek(80)
    leaf.focus()
    page.keyboard.press("Enter")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    one_frame(page)
    assert seek(0) == pytest.approx(middle, abs=0.5)
    paints()
    expect(leaf).to_be_focused()
    back = seek(80)
    paints()
    words_follow_box()
    assert row["x"] < back["x"] < middle["x"]
    assert back["opacity"] == 1
    assert seek(300) == pytest.approx(row, abs=0.5)

    # Finish what still moves. A motion the page cancelled when the fold reversed stays
    # in the held list (HOLD_MOTION), and finishing it would play it again to an end
    # frame `motion()` no longer releases.
    page.evaluate(
        "() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => a.finish())"
    )
    settled(page)
    expect(shelf).to_be_visible()
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    one_frame(page)
    target = leaf.bounding_box()
    assert reading()["x"] == pytest.approx(target["x"] + target["width"] / 2, abs=0.5)
    assert not page.evaluate(
        "() => ['.lf-floating-panel', '.lf-fp-ground'].some(s =>"
        " document.querySelector(s).getAnimations({subtree: true}).length)"
    )


def test_the_folded_leaf_keeps_its_badge_and_face_through_motion(browser, serve):
    """The count travels as part of the leaf, including a reversed fold, and finishing
    the motion does not replace the leaf's contour with a different resting shape."""
    from io import BytesIO

    from PIL import Image, ImageChops

    page = floating(browser, serve(OBLIGATION_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    leaf = page.locator(".lf-fp-leaf")
    write(
        field(page),
        "A tall draft\nwith several\nlines to keep\nwhile the panel\nfolds away.",
    )
    # Tab walks from the field past its presses to the leaf at the row's end.
    for _ in range(4):
        page.keyboard.press("Tab")
        if leaf.evaluate("node => node === document.activeElement"):
            break
    expect(leaf).to_be_focused()
    settled(page)
    page.evaluate("() => {" + HOLD_MOTION + "}")

    def shape():
        return page.evaluate("""() => {
          const fill = document.querySelector('.lf-fp-ground > .lf-box-fill');
          const room = fill.getBoundingClientRect();
          const sides = getComputedStyle(fill).clipPath.match(/[-\\d.]+px/g).map(parseFloat);
          const surface = {left: room.left + sides[3], top: room.top + sides[0],
            right: room.right - sides[1], bottom: room.bottom - sides[2]};
          return {surface, leaf: document.querySelector('.lf-fp-leaf').getBoundingClientRect().toJSON(),
            target: document.querySelector('.lf-fp-card').getBoundingClientRect().toJSON()};
        }""")

    def seek(progress):
        page.evaluate(
            "progress => __lfHeld.filter(a => a.playState !== 'idle').forEach(a =>"
            " a.currentTime = a.effect.getTiming().duration * progress)",
            progress,
        )
        one_frame(page)

    def attachment():
        return page.locator(".lf-fp-badge").evaluate("""badge => {
          const mark = document.querySelector('.lf-fp-leaf').getBoundingClientRect();
          const count = badge.getBoundingClientRect();
          return {x: count.right - mark.right, y: count.top - mark.top};
        }""")

    page.keyboard.press(".")
    expect(page.locator(".lf-fp-badge")).to_have_text("2")
    seek(0.2)
    offset = attachment()
    first = leaf.bounding_box()["x"]
    sample = shape()
    for edge in ("left", "top"):
        assert sample["leaf"][edge] >= sample["surface"][edge] - 0.5, sample
    for edge in ("right", "bottom"):
        assert sample["leaf"][edge] <= sample["surface"][edge] + 0.5, sample
    seek(0.55)
    sample = shape()
    assert sample["surface"]["right"] - sample["surface"]["left"] == pytest.approx(
        sample["target"]["width"], abs=0.5
    ), sample
    assert sample["surface"]["left"] < sample["target"]["left"] - 10, sample
    seek(0.8)
    assert attachment() == pytest.approx(offset, abs=0.25)
    assert leaf.bounding_box()["x"] > first
    page.keyboard.press("Enter")
    seek(0.3)
    page.keyboard.press(".")
    seek(0.2)
    assert attachment() == pytest.approx(offset, abs=0.25)
    seek(1 - 1e-4)
    assert attachment() == pytest.approx(offset, abs=0.25)
    clip = leaf.bounding_box()
    before = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")
    # Finish what still moves, leaving the motions the reversals cancelled (as above).
    page.evaluate(
        "() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => a.finish())"
    )
    settled(page)
    after = Image.open(BytesIO(page.screenshot(clip=clip))).convert("RGB")
    difference = ImageChops.difference(before, after)
    extrema = difference.getextrema()
    assert all(isinstance(channel, tuple) for channel in extrema)
    assert max(channel[1] for channel in extrema if isinstance(channel, tuple)) <= 8


def test_the_leaf_paints_inside_its_focus_ring_after_folding(browser, serve):
    """Pointer and keyboard folds finish with a visible mark at the control's
    centre, inside its keyboard ring. Motion sampling is a probe journey
    (`leaf_dev.panel_paint`); receiving an intermediate screencast frame is not a
    functional guarantee."""
    from io import BytesIO

    from PIL import Image

    page = floating(browser, serve(leaf_page("fold", '<h1 id="title">Fold</h1>')))
    page.emulate_media(reduced_motion="no-preference")
    leaf = page.locator(".lf-fp-leaf")
    colours = mark_colours(leaf)
    # Authored words can share the mark's colour; only the panel's pixels count.
    page.locator("#title").evaluate(
        "(node, colour) => node.style.color = colour", f"rgb{colours['mark']}"
    )

    for route, action in ROUTES:
        if action == ".lf-fp-minimize":
            card = page.locator(".lf-fp-card").bounding_box()
            page.mouse.move(card["x"] + 20, card["y"] + 6)
        if route == "keyboard" and action == ".":
            field(page).click()
            # Past the field's control in its corner, to the row's end.
            page.keyboard.press("Tab")
            page.keyboard.press("Tab")
            expect(leaf).to_be_focused()
            colours["ring"] = mark_colours(leaf)["ring"]
        if route == "keyboard":
            page.keyboard.press(action)
        else:
            page.locator(action).click()
        settled(page)
        expect(leaf).to_be_focused()
        expect(page.locator(".lf-floating-panel")).to_have_attribute(
            "data-lf-rest", "mark" if action in (".", ".lf-fp-minimize") else "row"
        )
        box = leaf.bounding_box()
        top = page.viewport_size["height"] - 70
        pixels = (
            Image.open(BytesIO(page.screenshot()))
            .convert("RGB")
            .crop((0, top, page.viewport_size["width"], page.viewport_size["height"]))
        )
        box["y"] -= top
        mark = ink_box(pixels, near(colours["mark"]))
        assert mark is not None, (route, action)
        mark_center = ((mark[0] + mark[2]) / 2, (mark[1] + mark[3]) / 2)
        assert mark_center == pytest.approx(
            (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2), abs=2
        ), (route, action, mark, box)
        if route == "keyboard":
            ring = ink_box(pixels, near(colours["ring"]))
            assert ring is not None, action
            assert ring[0] <= mark[0] < mark[2] <= ring[2], (action, mark, ring)
            assert ring[1] <= mark[1] < mark[3] <= ring[3], (action, mark, ring)
            ring_center = ((ring[0] + ring[2]) / 2, (ring[1] + ring[3]) / 2)
            assert mark_center == pytest.approx(ring_center, abs=2), (
                action,
                mark,
                ring,
            )


def test_a_new_line_past_the_field_s_height_scrolls_into_view(browser, serve):
    """Shift+Enter at the field's height limit scrolls the new, empty line into view,
    as typing a character does, rather than leaving the caret below the field."""
    page = floating(browser, serve(LONG_PAGE))
    box = field(page)
    box.click()
    page.keyboard.type("line")
    for _ in range(20):
        page.keyboard.press("Shift+Enter")
    page.wait_for_function(
        # Within a line of the end: the reveal keeps the field's scroll padding.
        """box => box.scrollHeight > box.clientHeight
            && box.scrollTop + box.clientHeight >= box.scrollHeight - 10""",
        arg=box.element_handle(),
    )


def test_a_pointer_folds_the_panel_from_its_corner(browser, serve):
    """A round button on the box's top-left corner folds the panel, shown only while
    the pointer is near that corner, so the resting row, and the row under a pointer
    passing over the field, is the row alone; it takes no Tab stop, since the menu's
    row and `.` fold from the keyboard."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    minimize = page.locator(".lf-fp-minimize")
    page.mouse.move(5, 5)
    expect(minimize).to_be_hidden()
    expect(minimize).to_have_attribute("tabindex", "-1")
    card = page.locator(".lf-fp-card").bounding_box()
    page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
    expect(minimize).to_be_hidden()
    # Nor on the leaf, whose count badge holds the box's other top corner.
    page.locator(".lf-fp-leaf").hover()
    expect(minimize).to_be_hidden()
    page.mouse.move(card["x"] + 20, card["y"] + 6)
    expect(page.get_by_role("button", name="Fold to the leaf")).to_be_visible()
    button = minimize.bounding_box()
    # It rides the corner, standing out past it as every corner mark does.
    overhang = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--lf-mark-overhang'))"
    )
    assert button["x"] == pytest.approx(card["x"] - overhang, abs=1)
    assert button["y"] == pytest.approx(card["y"] - overhang, abs=1)
    # A view opening carries the corner up, away from the still pointer, and the
    # button with it goes; putting the view away brings the corner back to it.
    page.locator("body").focus()
    for keys in ("g", "Shift+t"):
        page.keyboard.press(keys)
    expect(page.locator(".lf-fp-view")).to_have_attribute("data-lf-route", "threads")
    expect(minimize).to_be_hidden()
    for keys in ("g", "Shift+t"):
        page.keyboard.press(keys)
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(minimize).to_be_visible()
    # It presses the fold command, as the menu's row does, so the press is announced
    # and logged like any other.
    page.evaluate(
        """() => document.addEventListener('lf-command-invoked',
            ({detail}) => { window.invoked = detail.id }, {once: true})"""
    )
    minimize.click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    expect(minimize).to_be_hidden()
    assert page.evaluate("window.invoked") == "panel.floating.fold"


def test_obligations_are_answered_where_they_are_read_on_me(browser, serve):
    """On Me lists what waits on the user, and each obligation takes its answer there, by the
    widget's own choice: the event is the widget's action. The answered card keeps its
    place and height, so the next obligation does not move under the pointer, and
    Undo takes the answer back."""
    page = floating(browser, serve(OBLIGATION_PAGE))
    leaf = page.locator(".lf-fp-leaf")
    expect(leaf.locator(".lf-fp-badge")).to_have_text("2")
    leaf.click()
    view = page.locator(panel_view("queue"))
    # While the view stands, its On Me tab carries the count the leaf does.
    owed = panel_tab(page, "On Me").locator(".lf-fp-count")
    expect(owed).to_have_text("2")
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(2)
    expect(cards.first).to_contain_text("How should the schema migrate?")
    settled(page)
    first, second = cards.first.bounding_box(), cards.nth(1).bounding_box()
    show = cards.first.locator(".lf-fp-show")
    shown = show.bounding_box()
    with sending(page, "the answer"):
        cards.first.locator(".lf-fp-answer", has_text="Shim").click()
    answer = events_model.read_events(serve.page_dir)[-1]
    assert (answer["kind"], answer["widget"]) == ("action", "schema")
    expect(cards.first.locator(".lf-fp-said")).to_have_text(
        re.compile(r"^Answered: Shim the old schema")
    )
    expect(owed).to_have_text("1")
    assert cards.first.bounding_box() == first
    assert cards.nth(1).bounding_box() == second
    assert show.bounding_box() == shown

    with sending(page, "the undo"):
        cards.first.get_by_role("button", name="Undo").click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(cards.first.locator(".lf-fp-answer", has_text="Shim")).to_be_visible()
    expect(owed).to_have_text("2")
    assert show.bounding_box() == shown
    # The pressed Undo is gone, and Escape still puts the view away.
    page.keyboard.press("Escape")
    expect(view).to_have_count(0)


def test_on_me_groups_by_the_plan_and_the_plan_heads_on_claude(browser, serve):
    """While the agent's plan gives the user a step, On Me groups by it until the user
    picks another grouping: under each goal's band the items its steps name, in step
    order, and those no goal names last, each card saying its item's place. On Claude
    opens with the goal and its steps over its list, which leaves out what the plan
    names; a finished step says what its end said, and a step waiting on the user
    turns the view to On Me, and focus with it."""
    url = serve(OBLIGATION_PAGE)

    def leaf(*args) -> dict:
        written = CliRunner().invoke(cli_model.cli, [*args], input=None)
        assert written.exit_code == 0, written.output
        return json.loads(written.output.splitlines()[-1])

    steps = [
        {"depth": 0, "title": "Ship the migration"},
        {"depth": 1, "todo": "Read the old schema"},
        {"depth": 1, "todo": "Ask the DBA"},
        {"depth": 1, "item": "widget:schema"},
        {"depth": 1, "todo": "Write the note"},
        {"depth": 0, "todo": "Tidy the changelog"},
    ]
    written = CliRunner().invoke(
        cli_model.cli, ["task", "plan", str(serve.page_dir)], input=json.dumps(steps)
    )
    assert written.exit_code == 0, written.output
    reading, asking, _, _, tidying = json.loads(written.output.splitlines()[-1])[
        "steps"
    ][1:]
    page_dir = str(serve.page_dir)
    leaf("task", "end", page_dir, reading["item"], "done", "--text", "Notes in #old")
    leaf("task", "end", page_dir, asking["item"], "dropped", "--text", "Not needed")
    tidied = "Tidied in " + "https://example.com/changelog/" * 4
    leaf("task", "end", page_dir, tidying["item"], "done", "--text", tidied)
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    view = page.locator(panel_view("queue"))
    expect(page.get_by_role("combobox", name="Group On Me")).to_have_value("plan")
    # Each goal holds one item under its band, and each card says its place, and no
    # kind.
    expect(
        view.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    ).to_have_text(
        [
            re.compile(r"^\s*Ship the migration\s*1\s*$"),
            re.compile(r"^\s*Not in the plan\s*1\s*$"),
        ]
    )
    expect(view.locator(".lf-fp-on-place")).to_have_text(["Ask", "Ask"])

    tabs = page.locator(".lf-fp-filters button")
    expect(tabs).to_have_text(["Menu", "On Me 2", "On Claude 1", "Threads 0"])
    panel_tab(page, "On Claude").click()
    expect(page.locator(".lf-fp-title")).to_have_text("On Claude")
    expect(page.locator(".lf-fp-plan-goal")).to_have_text(
        re.compile(r"Ship the migration\s*1 of 3")
    )
    plan_steps = page.locator(".lf-fp-plan").first.locator(
        ":scope > .lf-fp-plan-steps > .lf-fp-plan-step"
    )
    expect(plan_steps).to_have_count(4)
    expect(plan_steps.nth(0).get_by_role("img")).to_have_accessible_name("Done")
    expect(plan_steps.nth(0).locator(".lf-fp-plan-detail")).to_have_text(
        "Notes in #old"
    )
    # The open to-do stands in the plan only.
    expect(view.locator(".lf-fp-on-item")).to_have_count(0)
    # A to-do at the top is drawn as a step, and the words its end gave read whole.
    tidy = page.locator(".lf-fp-plan").nth(1).locator(".lf-fp-plan-step")
    expect(tidy.get_by_role("img")).to_have_accessible_name("Done")
    detail = tidy.locator(".lf-fp-plan-detail")
    expect(detail).to_have_text(tidied)
    assert detail.evaluate("el => el.scrollWidth <= el.clientWidth")
    plan_steps.nth(2).locator(".lf-fp-plan-tag").click()
    expect(page.locator(".lf-fp-title")).to_have_text("On Me")
    expect(panel_tab(page, "On Me")).to_be_focused()


def test_only_an_open_thread_says_new_in_threads(browser, serve):
    """Threads marks the row with the news dot, which says New to assistive tech, only
    on an open thread the user hasn't read, as the leaf's dot counts: a resolved
    thread's unread message, under the Resolved heading, says nothing new."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?", author="agent")
    closed = panel_comment(serve.page_dir, "Is the room booked?", author="agent")
    thread_model.cmd_resolve(serve.page_dir, closed)
    page = floating(browser, url)
    open_threads(page)
    view = page.locator(panel_view("threads"))
    open_row = view.locator(".lf-fp-thread:not([data-lf-resolved])")
    expect(open_row.locator(".lf-fp-news-mark")).to_have_text("New")
    expect(open_row).to_have_attribute("data-lf-unread", "")
    resolved = show_resolved(page)
    expect(resolved).to_contain_text("Is the room booked?")
    expect(resolved.locator(".lf-fp-news-mark")).to_have_text("")
    expect(resolved).not_to_have_attribute("data-lf-unread", "")


def test_on_claude_lists_its_work_in_hand_queued_and_done_or_says_it(browser, serve):
    """On Claude is the agent's work list: what it has in hand, what is queued behind
    that, what waits on something the agent named, and what it finished, a line each
    with its stage and how long it has stood there, and under the work in hand, what its running step wrote. The chooser at its foot shows the same work as a summary instead, a choice
    the browser keeps across a reload."""
    url = serve(LONG_PAGE)
    page_dir = serve.page_dir
    record_claim(page_dir)

    def task(*args):
        done = CliRunner().invoke(cli_model.cli, ["task", *args])
        assert done.exit_code == 0, done.output
        return json.loads(done.output.strip().splitlines()[-1])

    drafting = task(
        "create", str(page_dir), "page", "--title", "Draft the release note"
    )
    task("create", str(page_dir), "page", "--title", "Check the rollout")
    task(
        "create",
        str(page_dir),
        "page",
        "--title",
        "Merge the release",
        "--waiting-on",
        "its review",
    )
    tidied = task("create", str(page_dir), "page", "--title", "Tidy the wording")
    task("end", str(page_dir), tidied["id"], "done")
    task(
        "start",
        str(page_dir),
        drafting["id"],
        "--text",
        "Drafting the note's first line",
    )
    page = floating(browser, url)
    open_on_me(page)
    page.locator(".lf-fp-filters button", has_text="On Claude").click()
    view = page.locator(panel_view("queue"))
    show_done(page)
    expect(
        view.locator(".lf-fp-on-list > .lf-rows-group > .lf-rows-head")
    ).to_have_text(
        [
            re.compile(r"^\s*In hand\s*1\s*$"),
            re.compile(r"^\s*Up next\s*1\s*$"),
            re.compile(r"^\s*Waiting\s*1\s*$"),
            re.compile(r"^\s*Done\s*1\s*$"),
        ]
    )
    lines = view.locator(".lf-fp-on-line")
    expect(lines.locator(".lf-fp-label")).to_have_text(
        [
            "Draft the release note",
            "Check the rollout",
            "Merge the release",
            "Tidy the wording",
        ]
    )
    expect(lines.locator(".lf-fp-on-says > .lf-fp-value")).to_have_text(
        [
            re.compile(r"^On it \S+$"),
            re.compile(r"^Still to do \S+$"),
            re.compile(r"^Waiting on its review \S+$"),
            re.compile(r"^Done \S+$"),
        ]
    )
    # Only the work in hand says what its running step wrote, under its name, and its
    # card opened shows that line rather than a second copy.
    expect(lines.locator(".lf-fp-running")).to_have_text(
        ["Drafting the note's first line"]
    )
    lines.first.click()
    expect(view.locator(".lf-fp-on-item[data-lf-open] .lf-fp-running")).to_have_text(
        "Drafting the note's first line"
    )
    expect(view.locator(".lf-fp-answers .lf-fp-said")).to_have_count(0)

    chooser = page.get_by_role("combobox", name="Show On Claude as")
    expect(chooser).to_have_value("list")
    chooser.select_option("summary")
    summary = view.locator(".lf-fp-work-summary")
    # Leaf says the summary, and the agent's own words, its line and a to-do's title,
    # stand in its own face within it.
    expect(summary).to_contain_text(
        "Working on 1; 1 up next, 1 waiting. Now: Drafting the note's first line."
    )
    expect(summary).to_contain_text("Last done: Tidy the wording")
    # Its age is a time, which says when to a pointer, as every age the panel shows:
    # its weekday, date, year, time of day and zone, as the browser writes them.
    assert re.fullmatch(
        r"\w{3},? .+ \d{4}, \d{1,2}:\d{2}.* .+",
        preview_text(summary.locator("time")),
    )
    expect(summary.locator('[data-lf-voice="agent"]')).to_have_text(
        ["Drafting the note's first line", "Tidy the wording"]
    )
    expect(view.locator(".lf-fp-on-line")).to_have_count(0)

    page.reload()
    wait_until_ready(page)
    open_on_me(page)
    page.locator(".lf-fp-filters button", has_text="On Claude").click()
    expect(page.get_by_role("combobox", name="Show On Claude as")).to_have_value(
        "summary"
    )
    expect(view.locator(".lf-fp-work-summary")).to_be_visible()


def test_versions_travel_opens_in_the_panel(browser, serve):
    """Version travel opens Versions over the leaf's menu, whatever route asks for it:
    the menu's row, which names the key as keys, apart from its value, and that key.
    It lists each version with its note, marks the one shown, and travels to another."""
    url = serve(LONG_PAGE)
    stamp_page(
        serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    page = floating(browser, url)
    view = page.locator(panel_view("versions"))
    menu = panel_menu(page)
    row = menu.locator('.lf-fp-item[data-lf-row="versions"]')
    expect(row.locator(".lf-fp-value")).to_have_text(re.compile(r"^v\d+$"))
    keys = row.locator(".lf-binding-sequence")
    expect(keys.locator("kbd.lf-key-badge")).to_have_text(["g", "V"])
    expect(keys).to_have_attribute("aria-label", "g then V")
    # Versions has an arrow after its shortcut; direct actions do not. Both
    # shortcuts end in one column, with copy icons and arrows in the next one.
    ends = menu.locator(".lf-binding-sequence:visible").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().right)"
    )
    assert len(ends) >= 2
    assert max(ends) - min(ends) <= 0.5, ends
    icons = menu.locator(
        ".lf-fp-end > :is(.lf-fp-chevron, .lf-fp-copy-icon):visible"
    ).evaluate_all(
        "nodes => nodes.map(node => {const box = node.getBoundingClientRect(); "
        "return box.x + box.width / 2;})"
    )
    assert len(icons) >= 2
    assert max(icons) - min(icons) <= 0.5, icons
    row.click()
    expect(view).to_be_visible()
    expect(page.locator(".lf-fp-head .lf-fp-back")).to_have_accessible_name(
        "Back to Menu"
    )
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(view).to_be_visible()
    expect(view.locator(".lf-fp-version")).to_have_count(2)
    expect(view.locator(".lf-fp-version[data-lf-current]")).to_contain_text("Showing")
    # Each version says the note its stamp gave it after its name, whole on hover, and a
    # listener hears the name and the note as two words, the note once.
    expect(view.locator(".lf-fp-note")).to_have_text(["two", "t"])
    expect_preview_words(view.locator(".lf-fp-note").first, "two")
    first = view.locator(".lf-fp-version .lf-fp-item").first
    expect(first).to_have_accessible_name("v2 (latest version) two")
    expect(first).to_have_accessible_description("")
    # Opened by its key, the view stands on the version the page shows, the tab's v1,
    # wherever pressed; its list is one stop for Tab, which the arrows walk.
    versions = view.locator(".lf-fp-version > .lf-fp-item")
    expect(versions.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(versions.first).to_be_focused()
    page.keyboard.press("End")
    expect(versions.nth(1)).to_be_focused()
    expect(view.locator("[tabindex='0']")).to_have_count(1)

    other = view.locator(".lf-fp-version:not([data-lf-current]) .lf-fp-label")
    match_2 = re.search(r"v\d+", other.inner_text())
    assert match_2 is not None
    number = match_2.group(0)
    other.click()
    expect(page).to_have_url(re.compile(rf"/versions/{number}\b"))


def test_a_finger_reads_a_version_s_note_whole(browser, serve):
    """A row cuts a version's note to its end, whole on hover, which a finger never
    has, so under one each note stands whole on the lines under its version's name."""
    url = serve(LONG_PAGE)
    note = (
        "Moved the rollout decision into its own section and reordered shutdown so "
        "cleanup runs after the supervisor collects output"
    )
    stamp_page(
        serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), note
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    words = panel_menu(page, "versions", touch=True).locator(
        ".lf-fp-note", has_text="supervisor"
    )
    expect(words).to_have_text(note)
    assert words.evaluate("""note => {
      const row = note.closest('.lf-fp-label').getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(note);
      return [...range.getClientRects()].every(
        (line) => line.right <= row.right + 0.5 && line.bottom <= row.bottom + 0.5);
    }""")


def test_versions_rests_the_page_s_keys_and_takes_a_version_s_number(browser, serve):
    """While Versions holds focus the page's keys rest, where d and j scrolled the page
    under it and c left it for the field. A version's number shows that version, not
    the row in that place, and `?` lists the numbers among the panel's keys."""
    url = serve(LONG_PAGE)
    for words, note in (("Paragraph zero.", "two"), ("Paragraph nought.", "three")):
        stamp_page(serve.page_dir, LONG_PAGE.replace("Paragraph 0.", words), note)
    page = floating(browser, url)
    view = page.locator(panel_view("versions"))
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(view.locator(".lf-fp-version")).to_have_count(3)
    document = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(document)
    for key in "djc":
        page.keyboard.press(key)
    one_frame(page)
    assert page.evaluate(document) == before
    # The tab shows v1, the last row, which the key stands on.
    shown = view.locator(".lf-fp-version[data-lf-current] > .lf-fp-item")
    expect(shown).to_have_accessible_name(re.compile(r"^v1\b"))
    expect(shown).to_be_focused()

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(
        reference.locator(
            '[role=option][data-lf-command="panel.floating.versions.pick"] kbd'
        )
    ).to_have_text(["1–3"])
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()

    # The reference closes back onto Versions, which stood under it, and the number
    # names the version, not the row in that place.
    expect(shown).to_be_focused()
    page.keyboard.press("1")
    expect(page).to_have_url(re.compile(r"/versions/v1\b"))


def test_a_failed_save_is_an_error_until_the_next_valid_one(browser, serve):
    """When the agent's latest save fails its check, the page keeps the last one that
    passed, and that stands as an error: the field says it and Errors in the leaf's
    menu lists it, and Versions says what the check found. It leaves both with the next
    valid save."""
    first = titled_page("Save status", '<p id="saved-text">First valid save.</p>')
    second = first.replace("First valid save.", "Next valid save.")
    page = open_page(browser, live_url(serve(first)))
    (serve.page_dir / "index.html").write_text(second.replace("</main>", ""))
    told(page)
    expect(field(page)).to_have_attribute("data-lf-says", "error")
    expect(page.locator("#saved-text")).to_have_text("First valid save.")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Latest edit not shown")
    )
    menu = panel_menu(page)
    expect(menu.locator('[data-lf-row="errors"]')).to_contain_text("1")
    menu.locator('.lf-fp-item[data-lf-row="versions"]').click()
    failed = page.locator(panel_view("versions")).locator(".lf-fp-failed")
    expect(failed).to_contain_text("Latest edit couldn't be shown")
    expect(failed.locator(".lf-fp-failed-error")).not_to_be_empty()
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page.locator("#saved-text")).to_have_text("Next valid save.")
    expect(field(page)).not_to_have_attribute("data-lf-says", "error")
    expect(panel_menu(page).locator('[data-lf-row="errors"]')).to_have_count(0)


def test_a_website_copy_says_who_revises_it_and_where_leaf_comes_from(browser, serve):
    """On Leaf's website the agent is on call: the leaf wears listening's tone and the
    field invites the comment that starts it, and the leaf's menu keeps the
    introduction with its links."""
    page = floating(
        browser,
        serve(
            leaf_page("Website example", "<h1>Website example</h1>"),
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        ),
    )
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Ready — comment to revise this copy")
    )
    expect(page.locator(".lf-fp-leaf")).to_have_attribute("data-lf-tone", "listening")
    links = panel_menu(page).locator(".lf-fp-state a")
    expect(links).to_have_count(2)
    assert links.evaluate_all("as => as.map(a => a.getAttribute('href'))") == [
        "/examples/",
        "/#install",
    ]


def test_a_mode_entered_from_the_panel_owns_the_row(browser, serve):
    """Annotations, a row of the leaf's menu, opens a list whose Draw mode takes the
    row: the field says the status and takes no words, its end offers Close and esc,
    the mode's way out, rather than Next On Me, and its mode chip names the mode in a
    word beside the ✕, which stands a symbol wide at the field's end, as far off the
    leaf as the field stood, the leaf keeping its place; the ✕ leaves the mode.
    A press on the field leaves the caret where it was and moves neither the field nor
    its ✕, and `c`, which would write there, leaves it too. A thread opened in the mode,
    as Threads is, closes before the mode on Escape, since it came last. Annotations
    also lists Select mode for a mouse, with the `s` that reaches it from the keyboard,
    since selecting words picks no widget or picture. The row previews nothing: it
    shows its words and key whole, and how the mode works is the command reference's
    to say."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    settled(page)
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    at_rest = page.locator(".lf-fp-field").bounding_box()
    gutter = leaf["x"] - (at_rest["x"] + at_rest["width"])
    annotations = panel_menu(page, "annotate")
    expect(annotations.locator(".lf-fp-item", has_text="Capture area")).to_be_visible()
    pick = annotations.locator('.lf-fp-item[data-lf-row="command:target.picker.open"]')
    expect(pick).to_contain_text("Select mode")
    expect(pick.locator("kbd")).to_have_text("s")
    tab_onto(pick)
    rendered(page)
    assert not page.locator(PREVIEW).is_visible(), page.locator(PREVIEW).inner_text()
    annotations.locator(".lf-fp-item", has_text="Draw mode").click()
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(field(page)).to_have_attribute("data-lf-says", "status")
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("Draw|Next"))
    close = field_press(page)
    expect(close.locator(".lf-compose-press-word")).to_have_text("Close")
    expect(close.locator("kbd")).to_have_text("esc")
    assert field(page).evaluate("el => el.readOnly")
    expect(page.locator(".lf-fp-mode")).to_have_text("Draw")
    exit_step = page.locator('.lf-fp-row > .lf-fp-exit[aria-label="Exit Draw mode"]')
    expect(exit_step).to_be_visible()
    settled(page)
    assert page.locator(".lf-fp-leaf").bounding_box() == leaf
    way_out = exit_step.bounding_box()
    assert (way_out["y"], way_out["height"]) == (leaf["y"], leaf["height"])
    box = page.locator(".lf-fp-field").bounding_box()
    assert leaf["x"] - (way_out["x"] + way_out["width"]) == pytest.approx(
        gutter, abs=0.5
    )
    assert way_out["x"] > box["x"] + box["width"]
    assert way_out["width"] == pytest.approx(way_out["height"], abs=0.5)
    stood = [box, way_out]
    field(page).click()
    expect(field(page)).not_to_be_focused()
    settled(page)
    assert [
        page.locator(".lf-fp-field").bounding_box(),
        exit_step.bounding_box(),
    ] == stood

    page.locator("body").focus()
    page.keyboard.press("c")
    rendered(page)
    expect(field(page)).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(panel_view("threads"))).to_have_count(0)
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(close.locator("kbd")).to_have_text("esc")
    exit_step.click()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
    expect(exit_step).to_have_count(0)
    expect(field(page)).to_have_attribute("data-lf-says", "status")


def test_the_leaf_s_menu_marks_what_opens_a_list_and_leaves_key_conveniences_out(
    browser, serve
):
    """The row holds the field and the leaf, and the leaf's menu holds the rest. A menu row that opens a list of its own ends in a chevron, a Leaf icon like
    any other: drawn in the row's muted ink rather than filled in the browser's black,
    and at one size whatever its row ends with, so the chevrons stand in one column.
    Navigate lists where a reader goes from a menu; the keyboard's conveniences for
    where they stand (Page Map beside the margin's rail, Resume writing, Restore
    selection, Align current item at top) keep their keys, and the menu leaves them
    out."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    expect(page.locator(".lf-fp-row > button:not(.lf-fp-expand)")).to_have_count(1)
    menu = panel_menu(page)
    drawn = menu.locator(".lf-fp-chevron").evaluate_all(
        """chevrons => chevrons.map(c => {
            const style = getComputedStyle(c), box = c.getBoundingClientRect();
            return {fill: style.fill, stroke: style.stroke, width: box.width,
                    right: Math.round(box.right)};
        })"""
    )
    assert len(drawn) >= 3, drawn
    assert all(c["fill"] == "none" and c["stroke"] != "none" for c in drawn), drawn
    assert {(c["width"], c["right"]) for c in drawn} == {(12, drawn[0]["right"])}, drawn
    for opens in ("Navigate", "Annotations"):
        expect(
            menu.locator(".lf-fp-item[data-lf-opens]", has_text=opens)
        ).to_have_count(1)
    expect(
        menu.locator(".lf-fp-item[data-lf-opens]", has_text="Keyboard shortcuts")
    ).to_have_count(0)
    listed = panel_menu(page, "navigate").locator(".lf-fp-item .lf-fp-label")
    expect(listed.filter(has_text="Search page")).to_have_count(1)
    assert set(listed.all_inner_texts()) <= {"All pages", "Search page"}


def test_a_list_the_menu_leads_to_opens_over_it_and_goes_back(browser, serve):
    """A menu row that opens a list opens it as a view over the menu, with its way back
    to Menu, a ‹ before its name, where every view's way back stands; it
    returns to the menu. Opened by a key, the list stands the user on its first row;
    Escape steps back to the menu, onto the row that opened the list, in view in a
    window too short to show the whole menu, and from the menu back to the leaf,
    putting the view away. A row's press takes its row away with
    the menu, so the user is located on the leaf that opened it: a row in a list the
    menu turned to does too, and folding stands on the folded leaf."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    view = page.locator(panel_view("group"))
    back = page.locator(".lf-fp-head .lf-fp-back")
    annotations = page.locator(panel_view("menu")).locator(
        ".lf-fp-item[data-lf-row='group:annotate']"
    )
    panel_menu(page, "annotate")
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text("Annotations")
    expect(back).to_have_accessible_name("Back to Menu")
    expect(view.locator(".lf-fp-item", has_text="Draw mode")).to_be_visible()
    back.click()
    panel_settled(page, view="menu")
    expect(annotations).to_be_visible()

    page.set_viewport_size({"width": 800, "height": 400})
    annotations.focus()
    page.keyboard.press("Enter")
    panel_settled(page, view="group")
    expect(view.locator(".lf-fp-item").first).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, view="menu")
    expect(annotations).to_be_focused()
    expect(annotations).to_be_in_viewport(ratio=1)
    page.set_viewport_size({"width": 1200, "height": 900})
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    leaf = page.locator(".lf-fp-leaf")
    expect(leaf).to_be_focused()

    panel_menu(page, "annotate").locator(".lf-fp-item").first.click()
    panel_settled(page, open=False)
    expect(leaf).to_be_focused()

    panel_menu(page).locator(".lf-fp-item", has_text="Fold to the leaf").click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    expect(leaf).to_be_focused()


def test_a_double_click_on_the_way_back_goes_back_once(browser, serve):
    """The menu is taller than a list over it, so the ‹ at the list's head stands where
    one of the menu's rows comes; a triple click's second and third clicks on it press
    nothing there, Undo included, nor take focus from the row the list came from, so
    the next Enter can't undo either, and the user's choice stands."""
    page = floating(browser, serve(UNDO_PAGE))
    with sending(page, "the pick"):
        page.locator("#opt-a").click()
    panel_menu(page, "annotate")
    box = page.locator(".lf-fp-head .lf-fp-back").bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.click(*point, click_count=3)
    panel_settled(page, view="menu")
    assert page.evaluate(
        "([x, y]) => Boolean(document.elementFromPoint(x, y)?.closest('.lf-fp-item'))",
        list(point),
    ), "the double-click must aim at a menu row once it goes back"
    expect(page.locator('.lf-fp-item[data-lf-row="group:annotate"]')).to_be_focused()
    expect(page.locator("lf-option[selected]")).to_have_attribute("id", "opt-a")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] != "undo"


def test_the_menu_s_search_finds_rows_threads_and_commands(browser, serve):
    """While the menu stands the field is its search. Words narrow the menu to the rows they name, a list's rows
    included, and the threads they name, ending in a press that hands them to the
    command reference, a list ahead of the rows it holds. Enter presses the first row
    found, and `/` among the rows returns to the search; Escape clears the words, then
    puts the menu away. A thread found opens over the menu, its way back returning to
    the words."""
    url = serve(LONG_PAGE)
    # The agent's, since the menu's Undo row names the user's newest comment by its
    # words, so a search for a thread of the user's finds that row first.
    panel_comment(serve.page_dir, "Is the window long enough?", author="agent")
    page = floating(browser, url)
    search = page.get_by_role("searchbox", name="Search menu")
    menu = panel_menu(page)
    expect(page.locator(".lf-floating-panel")).to_have_attribute(
        "data-lf-search", "menu"
    )
    # The agent's comment is news, so the leaf opened Threads and the Menu tab, which
    # keeps the user on it, turned the view to the menu.
    search.click()
    expect(search).to_be_focused()
    annotations = menu.locator('.lf-fp-item[data-lf-row="group:annotate"]')
    expect(annotations).to_be_visible()
    page.keyboard.type("draw")
    draw = menu.locator('.lf-fp-item[data-lf-row="command:draw.mode.enter"]')
    expect(draw).to_be_visible()
    expect(annotations).to_have_count(0)
    expect(menu.locator(".lf-fp-item").last).to_have_text("Search commands for “draw”")
    page.keyboard.press("ArrowDown")
    expect(search).not_to_be_focused()
    page.keyboard.press("/")
    expect(search).to_be_focused()
    expect(search).to_have_value("draw")
    search.fill("annotations")
    expect(menu.locator(".lf-fp-item").first).to_have_attribute(
        "data-lf-row", "group:annotate"
    )
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(annotations).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    panel_menu(page)
    search.click()
    page.keyboard.type("window long")
    expect(menu.locator(".lf-fp-item").first).to_contain_text("Is the window long")
    page.keyboard.press("Enter")
    panel_settled(page, view="thread")
    back = page.locator(".lf-fp-head .lf-fp-back")
    expect(back).to_have_accessible_name("Back to Menu")
    back.click()
    panel_settled(page, view="menu")
    expect(search).to_have_value("window long")
    close_panel_menu(page)

    panel_menu(page)
    page.keyboard.type("undo")
    menu.locator(".lf-fp-item").last.click()
    expect(page.get_by_role("combobox", name="Search commands")).to_have_value("undo")


@pytest.mark.parametrize("reduce_motion", [False, True])
def test_the_leaf_s_menu_is_one_tab_stop_its_keys_walk(browser, serve, reduce_motion):
    """Opened by a press, the leaf's menu stands the user in its search, from which ↓
    enters its rows, which the arrows, Home and End walk as one stop for Tab: Tab goes
    on past them to the view's tabs. On the leaf, as Escape leaves the user, the
    page's two-key Go-to still answers."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.emulate_media(reduced_motion="reduce" if reduce_motion else "no-preference")
    leaf = page.locator(".lf-fp-leaf")
    leaf.click()
    expect(page.locator(".lf-fp-search")).to_be_focused()
    menu = page.locator(panel_view("menu"))
    rows = menu.locator(".lf-fp-item:not(:disabled)")
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.last).to_be_focused()
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    expect(menu.locator("button[tabindex='0']")).to_have_count(1)
    page.keyboard.press("Tab")
    expect(panel_tab(page, "Menu")).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    threads = page.locator(panel_view("threads"))
    leaf.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(threads).to_be_visible()
    page.keyboard.press("Escape")
    expect(threads).to_have_count(0)


def test_the_leaf_s_menu_says_the_agent_s_state_once(browser, serve):
    """The menu's head says the agent's state in its one line, and under that only what
    the status's disclosure adds to the line: while the agent works, the disclosure's
    sentence restates the line, so it adds nothing. What waits on each side is counted
    on the tabs at the menu's foot, so the head leaves it out. The line names the state
    itself, so no word for it stands above, and a line that only reports, as work under
    way does, reads in ink, as the row's status does."""
    url = serve(OBLIGATION_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    line = re.compile(r"^Drafting the rollout")
    head = panel_menu(page).locator(".lf-fp-state")
    summary = head.locator("> .lf-fp-summary")
    expect(summary).to_have_text(line)
    expect(panel_tab(page, "On Me").locator(".lf-fp-count")).to_have_text("2")
    expect(panel_tab(page, "On Claude").locator(".lf-fp-count")).to_have_text("1")
    expect(head.locator("> *")).to_have_count(1)
    assert summary.evaluate(
        """line => {
          const ink = document.createElement('span');
          ink.hidden = true;
          ink.style.color = 'var(--lf-ink)';
          line.append(ink);
          const worn = getComputedStyle(ink).color === getComputedStyle(line).color;
          ink.remove();
          return worn;
        }"""
    )


def test_news_under_the_open_menu_moves_nothing_in_it(browser, serve):
    """The leaf's menu grows upward from the row, so while it stands it holds what it
    showed: a status that wraps to more lines, or fewer, re-wraps inside the lines its
    head first took, and a row a revision offers joins at the next opening, so neither
    the head's words nor the rows move. The shift watch holds the words; the boxes are
    read here."""
    page = floating(browser, serve(LONG_PAGE))
    menu = panel_menu(page)
    head = menu.locator(".lf-fp-state")
    expect(head.locator(".lf-fp-summary")).to_have_text("Away")
    settled(page)
    boxes = (
        "() => [...document.querySelectorAll('.lf-fp-menu > *')]"
        ".map(n => { const r = n.getBoundingClientRect(); return [r.top, r.height]; })"
    )
    before = page.evaluate(boxes)
    page.wait_for_function("() => !lfInputRenderingOpen()")
    for line in (
        "Drafting the rollout plan for the schema migration across every cluster",
        "Checking",
    ):
        working(serve.page_dir, line)
        expect(head.locator("span").first).to_contain_text(line)
        assert page.evaluate(boxes) == before

    source = (serve.page_dir / "index.html").read_text()
    stamp_page(serve.page_dir, source.replace("Filler.", "Filler!", 1), "revised")
    newer = re.compile("New page available → open v2")
    told(page)
    assert page.evaluate(boxes) == before
    close_panel_menu(page)
    expect(panel_menu(page).locator(".lf-fp-item", has_text=newer)).to_be_visible()


def test_each_view_s_list_is_one_tab_stop_its_keys_walk(browser, serve):
    """Threads and On are walked as the leaf's menu is: one stop for Tab, which the
    arrows, Home and End move, and from the view the leaf's press or Go-to opened, ↓
    enters its first row. Threads' rows leave out the open state every row there
    shares, its tab counts the open threads, and the leaf that opens On names what it
    opens and what it counts."""
    url = serve(OBLIGATION_PAGE)
    for text in ("Is the window long enough?", "Who watches the weekend?"):
        panel_comment(serve.page_dir, text)
    page = floating(browser, url)
    on_mark = page.locator(".lf-fp-leaf")
    expect(on_mark).to_have_attribute(
        "aria-label", re.compile(r"^On Me · 2 waiting on me · ")
    )

    on_mark.click()
    queue = page.locator(panel_view("queue"))
    expect(queue).to_be_focused()
    # Each tab is named by the words it shows: its list and its count.
    expect(page.get_by_role("button", name="On Me 2", exact=True)).to_be_visible()
    threads = page.get_by_role("button", name="Threads 2", exact=True)
    expect(threads.locator(".lf-fp-count")).to_have_text("2")
    cards = queue.locator(".lf-fp-on-item")
    expect(cards).to_have_count(2)
    page.keyboard.press("ArrowDown")
    expect(cards.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(cards.nth(1)).to_be_focused()
    expect(cards.first).to_have_attribute("tabindex", "-1")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    view = page.locator(panel_view("threads"))
    rows = view.locator(".lf-fp-thread")
    expect(rows).to_have_count(2)
    expect(view.locator(".lf-fp-value", has_text="Open")).to_have_count(0)
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.last).to_be_focused()
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    expect(view.locator("[tabindex='0']")).to_have_count(1)
    expect(rows.nth(1)).to_have_attribute("tabindex", "0")


def test_threads_arrows_move_on_from_a_row_scrolled_out_of_the_list(browser, serve):
    """Wheeling Threads' list until its focused row leaves the list's view doesn't take
    the user off that row, though keys skip a place scrolled off screen: the panel still
    shows the list, so ↓ moves on to the next row and brings it into view."""
    page = floating(browser, serve(LONG_PAGE, comments=30))
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    rows = page.locator(panel_view("threads")).locator(".lf-fp-thread")
    expect(rows.first).to_be_focused()
    box = rows.nth(3).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 3000)
    scroll_settled(page)
    expect(rows.first).not_to_be_in_viewport()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    expect(rows.nth(1)).to_be_in_viewport()


def test_a_layer_a_menu_row_opened_closes_back_to_the_leaf(browser, serve):
    """The command reference a menu row opens records the leaf as where it was opened
    from, since the row went with the menu, so Escape returns the user there. The menu
    took the place of the thread open under it, whose unfinished reply waits in the
    thread for the user's return."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.keyboard.press("t")
    write(field(page), "An unfinished reply")
    panel_menu(page).locator('.lf-fp-item[data-lf-row="keyboard"]').click()
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(panel_view("thread"))).to_be_visible()
    expect(field(page)).to_have_js_property("value", "An unfinished reply")


def test_tab_from_the_field_reaches_dictate(browser, serve):
    """Dictate stands beside the field while the user writes in it and is gone at rest,
    and Tab from the field lands on it rather than hiding it as the field lets go.
    """
    page = floating(browser, serve(LONG_PAGE))
    dictate = page.locator(".lf-fp-box .lf-compose-dictate")
    expect(dictate).to_be_hidden()
    field(page).click()
    expect(dictate).to_be_visible()
    page.keyboard.press("Tab")
    # The field's letting go repaints the box a frame later; Dictate is still there.
    page.evaluate(
        "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    expect(dictate).to_be_visible()
    expect(dictate).to_be_focused()


def test_stop_stands_while_its_dictation_runs(browser, serve):
    """A dictation running in the field is writing there, wherever focus goes on to:
    its Stop keeps the corner, and the field keeps saying where the words go rather
    than offering a press at its end beside Stop."""
    page = open_page(browser, serve(LONG_PAGE), init_script=FAKE_RECOGNITION)
    dictate = page.locator(".lf-fp-field .lf-compose-dictate")
    field(page).click()
    page.keyboard.press("Tab")
    expect(dictate).to_be_focused()
    page.keyboard.press("Enter")
    expect(dictate).to_have_attribute("aria-pressed", "true")
    in_panel = "() => document.querySelector('.lf-floating-panel').contains(document.activeElement)"
    for _ in range(4):
        page.keyboard.press("Tab")
        if not page.evaluate(in_panel):
            break
    assert not page.evaluate(in_panel), "Tab took focus out of the panel"
    expect(dictate).to_be_visible()
    expect(dictate).to_have_attribute("aria-pressed", "true")
    expect(field(page)).to_have_attribute("data-lf-says", "destination")


def test_words_another_tab_writes_bring_no_send_under_a_resting_pointer(browser, serve):
    """Words another tab writes in the page's empty field bring no Send into its corner,
    where a pointer may rest, until the user's own move: a press there places the caret
    in the words rather than sending them (browser/AGENTS.md, "Controls stay where the
    user aims"), and Send stands once they write there."""
    url = serve(LONG_PAGE)
    page = floating(browser, url)
    other = floating(browser, url)
    box = field(page).bounding_box()
    page.mouse.move(box["x"] + box["width"] - 12, box["y"] + box["height"] / 2)
    write(field(other), "Written in the other tab")
    expect(field(page)).to_have_js_property("value", "Written in the other tab")
    send = page.locator(".lf-fp-field .lf-compose-submit")
    expect(send).to_be_hidden()
    page.mouse.down()
    page.mouse.up()
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_js_property("value", "Written in the other tab")
    expect(page.locator(".lf-fp-opened")).to_be_hidden()
    expect(send).to_be_visible()


def test_closing_a_view_leaves_dictate_beside_the_caret(browser, serve):
    """A pointer on an open view's Close leaves the caret in the page's field, which
    the user is still writing in, so Dictate keeps its corner."""
    page = open_page(browser, serve(OBLIGATION_PAGE), init_script=FAKE_RECOGNITION)
    dictate = page.locator(".lf-fp-field .lf-compose-dictate")
    page.locator("body").focus()
    page.keyboard.press("o")
    close = page.locator(".lf-fp-close").first
    expect(close).to_be_visible()
    field(page).click()
    expect(field(page)).to_be_focused()
    expect(dictate).to_be_visible()
    close.click()
    expect(close).to_be_hidden()
    expect(field(page)).to_be_focused()
    expect(dictate).to_be_visible()


ROW_CENTRES = """() => {
  const centre = (selector) => {
    const node = document.querySelector(selector);
    if (!node || !node.getClientRects().length) return null;
    const box = node.getBoundingClientRect();
    return (box.top + box.bottom) / 2;
  };
  const text = document.querySelector('.lf-fp-field leaf-text').getBoundingClientRect();
  return {
    leaf: centre('.lf-fp-leaf > svg[data-lf-icon=leaf]'),
    line: text.bottom - 16,
    dictate: centre('.lf-fp-field .lf-compose-dictate svg'),
    send: centre('.lf-fp-field .lf-compose-submit svg'),
    field: text.right,
    press: document.querySelector('.lf-fp-field .lf-compose-submit')
      ?.getBoundingClientRect().toJSON(),
  };
}"""


def test_a_long_draft_leaves_an_open_view_its_head(browser, serve):
    """A long draft and an open view share the window: the view takes what the field
    leaves and scrolls inside it, so its name, over it, stays in the window, and its
    controls stand between it and the field. Stacked at their own full heights, the
    two would put the view's head above the window's top."""
    url = serve(LONG_PAGE)
    for n in range(30):
        panel_comment(serve.page_dir, f"Page comment {n}")
    page = floating(browser, url)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    view = page.locator(panel_view("threads"))
    expect(view).to_be_visible()
    field(page).click()
    page.keyboard.insert_text("".join(f"Line {n} of a long draft\n" for n in range(40)))
    page.get_by_role("button", name="More room to write", exact=True).click()
    settled(page)
    head = page.locator(".lf-fp-head").bounding_box()
    shown = view.bounding_box()
    controls = page.locator(".lf-fp-controls").bounding_box()
    words = page.locator(".lf-fp-field").bounding_box()
    assert head["y"] >= 0, head
    assert shown["y"] + shown["height"] <= controls["y"] + 0.5, (shown, controls)
    assert controls["y"] + controls["height"] <= words["y"] + 0.5, (controls, words)
    assert view.evaluate("v => v.scrollHeight > v.clientHeight")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_wheel_as_the_thread_gives_up_room_moves_it_as_far_as_without(
    engine, request, serve
):
    """A wheel up the open thread's view, as the view gives up room at its top in the
    same moment, as it does to a reply that gains a line or to a draft from another tab,
    moves the thread as far as the wheel moves it alone, and the view gives way too
    (dom/scrolling.js, `keepFoot`). Firefox applies the wheel's scroll a frame or more after
    the wheel, and the view's own move made meanwhile cancelled it: with 100px of room
    taken from 300, a wheel of 200px up left the view 100px further down the thread
    rather than 100px further up it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The mounts come first. " * 120
    )
    page = floating(request.getfixturevalue(engine), url)
    # The view opens 300px tall, so the room it gives up below is a share of its own.
    page.add_style_tag(
        content="leaf-floating-panel .lf-fp-view[data-lf-route='thread']"
        " { max-height: 300px }"
    )
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(2)
    assert view.evaluate("v => v.clientHeight") == 300
    # The room the view gives up stands in for a reply's new line, taken as the wheel
    # is heard, before the browser applies its scroll.
    view.evaluate("""v => v.addEventListener('wheel', () => {
      if (v.dataset.giving) v.style.maxHeight = `${v.clientHeight - 100}px`;
    }, {passive: true})""")
    settled(page)
    view.hover()
    moved = {}
    for giving in (False, True):
        view.evaluate("v => { v.scrollTop = 400; }")
        settled(page)
        # The wheel's scroll ends once, the move the view owes made at that end.
        stood = view.evaluate(
            """async (v, giving) => {
              if (giving) v.dataset.giving = '1';
              const { watchScrollEnds } = await window.__lfCheckApi();
              window.lfEnded = false;
              window.lfHeard = 0;
              const heard = () => { window.lfHeard += 1; };
              v.addEventListener('scroll', heard, {passive: true});
              const stop = watchScrollEnds((box) => {
                if (box !== v) return;
                stop();
                v.removeEventListener('scroll', heard);
                window.lfEnded = true;
              });
              return v.scrollTop; }""",
            giving,
        )
        page.mouse.wheel(0, -200)
        page.wait_for_function("() => window.lfEnded")
        if not page.evaluate("() => window.lfHeard"):
            # The box's sequence ended with no scroll heard in it: the quiet spell ran
            # out before the browser applied the wheel, as a Firefox starved of CPU
            # does, and the move the view owed, made at that end, cancelled the wheel.
            # That loss is accepted as a corner case (dom/arrivals.js, `SETTLE_MS`): no
            # event says the browser won't scroll. The move this test guards against,
            # made at the wheel, scrolls the box before its sequence ends.
            pytest.xfail("the browser applied the wheel after the reader's wait ended")
        moved[giving] = stood - view.evaluate("v => v.scrollTop")
    assert moved[False] > 100, moved
    assert moved[True] == pytest.approx(moved[False] - 100, abs=2), moved


@pytest.mark.parametrize("touch", [False, True])
def test_the_panel_s_foot_room_is_as_tall_as_the_row_stands_up(browser, serve, touch):
    """The room the panel's row takes at the window's foot (`--lf-foot-room`), which
    caps how tall a view opens and pads a block sample below its last block, is the
    row with the gap it stands above the window's edge again above it, and no more. A
    room stated as a number of its own can stand taller than the row, under a mouse and
    under a finger alike."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=touch
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch
    at = page.evaluate("""() => {
      const room = document.createElement('div');
      room.style.height = 'var(--lf-foot-room)';
      document.body.append(room);
      const foot = room.getBoundingClientRect().height;
      room.remove();
      const row = document.querySelector('.lf-fp-row').getBoundingClientRect();
      return {foot, row: row.height, below: innerHeight - row.bottom};
    }""")
    assert at["foot"] == pytest.approx(at["row"] + 2 * at["below"], abs=0.5), at


@pytest.mark.parametrize("touch", [False, True])
def test_a_press_arriving_in_a_line_of_answers_moves_nothing(browser, serve, touch):
    """A line of answers holding only words is already a press tall, so the Undo a
    reading brings later moves nothing beside it. Under a finger the panel's presses
    are the row's 34px line, so a line keeping the mouse's 28px would grow as a press
    arrived."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Should the rollout wait?")
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Which week suits?\n\n"
        '<lf-group id="week" label="Which week?">\n<h3 id="week-h">Which week?</h3><lf-options id="week-choice">'
        '<lf-option id="this">This week</lf-option>'
        '<lf-option id="next">Next week</lf-option></lf-options></lf-group>',
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=touch
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-fp-leaf").click()
    answers = page.locator(f"{panel_view('queue')} .lf-fp-answers").first
    expect(answers).to_be_visible()
    heights = answers.evaluate("""line => {
      line.replaceChildren('Answered.');
      const words = line.getBoundingClientRect().height;
      const press = document.createElement('button');
      press.type = 'button';
      press.className = 'lf-btn lf-fp-reply lf-ui lf-ui-face';
      press.dataset.lfOffer = 'button';
      press.textContent = 'Undo';
      line.append(press);
      return [words, line.getBoundingClientRect().height];
    }""")
    assert heights[1] == pytest.approx(heights[0], abs=0.5), heights


def test_a_count_arriving_moves_no_mark_under_a_finger(browser, serve):
    """The leaf's count stands on a badge over its corner, under a finger as under a
    mouse, so a question arriving in a reply shows On Me's count there and moves
    nothing beside it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Should the rollout wait?")
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    field_box = page.locator(".lf-fp-field")
    on_me = page.locator(".lf-fp-leaf")
    expect(on_me.locator(".lf-fp-badge")).to_have_text("")
    before = [box.bounding_box() for box in (field_box, on_me)]
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Which week suits?\n\n"
        '<lf-group id="week" label="Which week?">\n<h3 id="week-h">Which week?</h3><lf-options id="week-choice">'
        '<lf-option id="this">This week</lf-option>'
        '<lf-option id="next">Next week</lf-option></lf-options></lf-group>',
    )
    told(page)
    expect(on_me.locator(".lf-fp-badge")).to_have_text("1")
    assert [box.bounding_box() for box in (field_box, on_me)] == before


def test_a_finger_finds_the_keyboard_s_conveniences_under_navigate(browser, serve):
    """Where no keyboard is there to reach them, the conveniences the desk's menu leaves
    to their keys stand under Navigate, so a finger keeps a way to each."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    listed = panel_menu(page, "navigate").locator(".lf-fp-item .lf-fp-label")
    expect(listed.filter(has_text="Search page")).to_have_count(1)
    expect(listed.filter(has_text="Align current item at top")).to_have_count(1)


def test_copy_link_is_one_press_over_plain_http(browser, serve):
    """A page another machine reads over plain HTTP has no Clipboard API, and the leaf's
    menu still offers Copy link there, since the copy control copies through the
    browser's selection command (transport/copy-control.js, `canCopy`)."""
    local_url = live_url(serve(LONG_PAGE))
    context, remote_url = over_plain_http(browser, local_url)
    page = open_page(browser, remote_url, context=context)
    assert page.evaluate("!isSecureContext && navigator.clipboard === undefined")
    row = panel_menu(page).locator('.lf-fp-item[data-lf-row="share"]')
    expect(row).to_have_text("Copy link")
    row.click()
    panel_settled(page, open=False)
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Link copied"))
    page.goto(local_url)
    assert re.match(
        r"^http://.*[?&]t=", page.evaluate("navigator.clipboard.readText()")
    )


PAGE_ANNOTATED = LONG_PAGE.replace("<body>", '<body data-annotations="page">', 1)


def test_a_thread_the_page_draws_nowhere_opens_in_the_panel(browser, serve):
    """On a page that draws no margin (`data-annotations="page"`), a thread about a
    passage has nowhere on the page to open, so the panel is its home: `m` arrives at
    the agent's question there, as `t` does at a thread, drawn by Leaf's reader in the
    panel's thread view."""
    url = serve(PAGE_ANNOTATED)
    panel_comment(
        serve.page_dir,
        "Should the rollout pause on Fridays?",
        anchor={"section": "p3", "quote": "Paragraph 3."},
        author="agent",
        obligation=True,
    )
    page = floating(browser, url)
    reader = page.locator(panel_view("thread"))
    page.locator("body").focus()
    page.keyboard.press("m")
    expect(reader.locator(".lf-msg")).to_contain_text("Should the rollout pause")
    page.keyboard.press("Escape")
    expect(reader).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(reader.locator(".lf-msg")).to_contain_text("Should the rollout pause")


def test_a_reply_s_widget_stands_in_its_card(browser, serve):
    """A thread's card beside its passage draws a reply carrying a widget whole, widget
    and all, and the panel stays shut."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which job should come first?",
        {"section": "p3", "quote": "Paragraph 3."},
    )
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Choose the first job.\n\n"
        '<lf-group id="first-job-decision" label="Which job first?">\n<h3 id="first-job-decision-h">Which job first?</h3>'
        '<lf-options id="first-job">'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-group>",
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview #first-job")).to_be_visible()
    expect(page.locator(panel_view("thread"))).to_have_count(0)


def test_a_thread_s_messages_read_alike_in_its_card_and_the_panel(browser, serve):
    """What anyone wrote in a thread reads in one face wherever the thread stands, its
    card beside the passage and its view in the panel, and a rewrite types in it."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir,
        "Which job should come first?",
        {"section": "p3", "quote": "Paragraph 3."},
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    face = "(node) => getComputedStyle(node).font"
    card = page.locator(".lf-margin-thread-body .lf-msg")
    expect(card).to_contain_text("Which job should come first?")
    message = card.locator(".lf-msg-body").evaluate(face)
    card.locator(".lf-msg-edit").click()
    assert card.locator(".lf-msg-editor leaf-text").evaluate(face) == message
    card.locator(".lf-msg-edit-cancel").click()
    page.locator(".lf-margin-preview").get_by_role(
        "button", name="Open in panel"
    ).click()
    reader = page.locator(f"{panel_view('thread')} .lf-msg")
    expect(reader).to_contain_text("Which job should come first?")
    assert reader.locator(".lf-msg-body").evaluate(face) == message


def test_a_page_comment_sent_before_the_first_reading_stands_in_the_panel(
    browser, serve
):
    """A page comment sent while the page still waits for its saved state is the thread
    the user opened: its view draws it at once, Threads lists it above the line saying
    the saved threads are still loading, and `t` walks to it once the view is put away.
    A panel that read threads only from a settled reading would have its view say the
    thread was not on the page, Threads list nothing, and `t` dropped."""
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    page.route("**/api/event", lambda route: held.append(route))
    page.goto(serve(LONG_PAGE), wait_until="load")
    holding(page, held, 1, "the first state read")
    wait_until_ready(page, through="upgraded")
    words = "Sent before the page heard back."
    write(field(page), words)
    page.keyboard.press("Enter")
    view = page.locator(panel_view("thread"))
    expect(view).to_contain_text(words)

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    open_threads(page)
    threads = page.locator(panel_view("threads"))
    expect(threads.locator(".lf-fp-thread")).to_have_text([re.compile(words)])
    expect(threads.locator(".lf-rows-empty")).to_have_text("Loading current threads…")

    page.locator(".lf-fp-close").click()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(view).to_contain_text(words)
    expect(view).to_be_focused()


def test_a_refused_page_comment_hands_its_words_back_to_the_field(browser, serve):
    """A page comment the server refuses takes back the thread its send opened in the
    panel, which the server never held, so the field stands for the page again with
    the words in it and the caret in them, ready to send again."""
    page = floating(browser, serve(LONG_PAGE))

    def refuse(route):
        attempt = route.request.post_data_json["attempt"]
        route.fulfill(
            status=400,
            json={"ok": False, "attempt": attempt, "error": "refused", "final": True},
        )

    page.route("**/api/event", refuse)
    write(field(page), "Is the window long enough?")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(field(page)).to_have_js_property("value", "Is the window long enough?")
    expect(field(page)).to_be_focused()
    consume_browser_errors(page, http_error_console(400))


def test_a_thread_whose_words_are_gone_keeps_its_quotation_in_the_panel(browser, serve):
    """A thread about words the page no longer holds opens in the panel, where the
    quotation it kept stands over its messages in three lines, under the word that
    says the page has no place for it, which a finger reads as a pointer does; Full
    quote shows the rest, as a card's head does."""
    url = serve(LONG_PAGE)
    words = "The earlier plan required a manual review before every rollout. " * 6
    panel_comment(
        serve.page_dir,
        "Does this still apply?",
        {"section": "gone", "quote": words + "FINAL WORDS"},
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_contain_text("Does this still apply?")
    quote = view.locator(".lf-thread-quote")
    expect(quote).to_contain_text("FINAL WORDS")
    expect(view.locator(".lf-thread-quote-head")).to_have_attribute(
        "data-lf-detached", ""
    )
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    status = view.locator(".lf-quote-label .lf-anchor-status")
    expect(status).to_have_text("Not found")
    expect(status).to_be_visible()
    disclosure = view.locator(".lf-quote-label").get_by_role("button")
    expect(disclosure).to_be_visible()
    disclosure.click()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


def test_a_thread_s_words_start_on_its_head_s_edge(browser, serve):
    """In a thread's view the quote's words and each message's start on one edge, the
    quote's rule standing left of it, and the way back on the head line stands on the
    rule's edge, the thread's name after it. A rewrite's frame reaches back only as far
    as that rule, so its words keep the message's and its frame stays clear of the
    panel's edge."""
    url = serve(PAGE_ANNOTATED)
    root = panel_comment(
        serve.page_dir,
        "Is the window long enough?",
        anchor={"section": "p3", "quote": "Paragraph 3."},
    )
    # Untitled threads hide the repeated heading; measure an actual thread title.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "agent": "Claude",
            "thread": root,
            "title": "Window length",
        },
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_be_visible()
    settled(page)
    starts = """() => {
      const edge = document.querySelector('.lf-fp-card').getBoundingClientRect().left;
      const words = (node) => {
        const text = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
          acceptNode: (t) => (t.textContent.trim() ? 1 : 3),
        }).nextNode();
        const range = document.createRange();
        range.selectNodeContents(text);
        return range.getClientRects()[0].left - edge;
      };
      const view = document.querySelector('.lf-fp-view[data-lf-route=thread]');
      const quote = view.querySelector('.lf-thread-quote');
      const frame = view.querySelector('.lf-msg-editor .lf-compose-field');
      const text = frame?.querySelector('leaf-text');
      const back = document.querySelector('.lf-fp-head .lf-fp-back').getBoundingClientRect();
      return {
        head: words(document.querySelector('.lf-fp-head .lf-fp-title')),
        back: back.left - edge,
        backEnd: back.right - edge,
        quote: words(quote),
        message: words(view.querySelector('.lf-msg')),
        rule: quote.getBoundingClientRect().left - edge,
        frame: frame && frame.getBoundingClientRect().left - edge,
        rewrite: text && text.getBoundingClientRect().left - edge
          + parseFloat(getComputedStyle(text).paddingLeft),
      };
    }"""
    at = page.evaluate(starts)
    assert at["message"] == pytest.approx(at["quote"], abs=0.5), at
    assert 0 < at["rule"] < at["quote"] - 4, at
    assert at["back"] == pytest.approx(at["rule"], abs=0.5), at
    assert at["backEnd"] <= at["head"], at

    view.locator(".lf-msg-body").dblclick()
    expect(view.locator(".lf-msg-editor leaf-text")).to_be_focused()
    at = page.evaluate(starts)
    assert at["rewrite"] == pytest.approx(at["message"], abs=0.5), at
    assert at["frame"] == pytest.approx(at["rule"], abs=0.5), at


def test_the_go_to_doors_open_the_panel_s_views(browser, serve):
    """`g T` and `g M` open Threads and On Me in the panel, and the same keys put them
    away again."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    view = page.locator(".lf-fp-view:not([data-lf-leaving])")
    page.locator("body").focus()
    for keys, shown in (("Shift+t", "threads"), ("Shift+m", "queue")):
        page.keyboard.press("g")
        page.keyboard.press(keys)
        expect(view).to_have_attribute("data-lf-route", shown)
        page.keyboard.press("g")
        page.keyboard.press(keys)
        expect(view).to_have_count(0)


def test_a_comment_on_words_where_the_page_draws_no_margin_is_written_in_the_row(
    browser, serve
):
    """On a page that draws its own annotations and gives the comment box no seat, the
    box for a comment on selected words stands in the field's place in the panel's row
    while it is open, holding the caret. Its
    comment sent, the panel opens the thread it started, which the page draws
    nowhere, and the field is back in the row."""
    page = open_page(browser, serve(PAGE_ANNOTATED), init_script=FAKE_RECOGNITION)
    response = page.locator(".lf-fp-response")
    row = page.locator(".lf-fp-row")
    rest = row.bounding_box()["height"]
    select_words(page, "#p3")
    page.keyboard.press("c")
    box = response.locator("leaf-text")
    expect(box).to_be_visible()
    expect(box).to_be_focused()
    assert row.bounding_box()["height"] == pytest.approx(rest, abs=0.5)
    expect(page.locator(".lf-fp-field")).to_be_hidden()
    # The box keeps its own corner, Dictate while it is empty, as every comment box
    # does, rather than the panel field's.
    expect(response.locator(".lf-compose-dictate")).to_be_visible()
    page.keyboard.type("Is this paragraph needed?")
    # Send stands in the field's end corner, as in every comment box, not on a line
    # of its own under the field.
    send = response.locator(".lf-compose-submit").bounding_box()
    words = box.bounding_box()
    assert words["y"] <= send["y"] and send["y"] + send["height"] <= (
        words["y"] + words["height"]
    ), (send, words)
    assert words["x"] + words["width"] / 2 < send["x"], (send, words)
    assert send["x"] + send["width"] <= words["x"] + words["width"], (send, words)
    # An image it is given hangs over the panel as the field's does, so the box and
    # its words stay where they are.
    card = page.locator(".lf-fp-card")
    before = (card.bounding_box(), box.bounding_box())
    paste_image(box, solid_png(40, 30, (255, 128, 64)))
    picture = response.locator(".lf-composer-media-open")
    expect(picture).to_have_count(1)
    assert (card.bounding_box(), box.bounding_box()) == before
    tile = picture.bounding_box()
    assert tile["y"] + tile["height"] <= before[0]["y"], (tile, before)
    page.keyboard.press("Enter")
    reader = page.locator(panel_view("thread"))
    expect(reader.locator(".lf-msg")).to_contain_text("Is this paragraph needed?")
    expect(response).to_be_hidden()


def test_an_image_pasted_in_the_page_s_field_hangs_above_the_panel(browser, serve):
    """An image pasted into the page's field hangs just over the panel's top edge from
    its start edge, outside its box, so attaching grows the panel by nothing and leaves
    the field its width; its thumbnail is the paste's result, so no notice says it was
    added. A view opening gives it a band over the box, which a search closes."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    card = page.locator(".lf-fp-card")
    before = card.bounding_box()
    paste_image(field(page), solid_png(40, 30, (255, 128, 64)))
    shelf = page.locator(".lf-fp-box .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    assert card.bounding_box() == before
    assert field(page).bounding_box()["width"] > 300
    tile = shelf.bounding_box()
    assert tile["y"] + tile["height"] <= before["y"], (tile, before)
    assert tile["x"] == pytest.approx(before["x"], abs=1), (tile, before)
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("Image added"))
    # With a view open the panel opens a band for the picture, and closes it while a
    # search takes the field's place and so hides the picture.
    open_threads(page)
    row = page.locator(".lf-fp-row")
    expect(shelf).to_be_visible()
    expect(row).not_to_have_css("margin-top", "0px")
    page.get_by_role("button", name="Find a thread or message").click()
    expect(page.locator("input.lf-fp-search")).to_be_visible()
    expect(shelf).to_be_hidden()
    expect(row).to_have_css("margin-top", "0px")


@pytest.mark.parametrize("by", ["key", "menu", "menu-after-send"])
def test_an_image_pasted_in_an_open_thread_stands_between_the_thread_and_the_box(
    browser, serve, by
):
    """With a thread open, an image pasted into its reply stands where the page's field
    stands one, just over the box from the panel's start edge, in a band the panel opens
    between the thread's view and the box: it covers neither, the box stays where the
    user types, and the thread's last message stays beside the reply throughout, though
    the panel already reached the window's top and the band takes its room from the
    view. That holds for a paste from a menu too, which comes with no key: the band
    then reads as news, which leaves the thread's messages where its scroll puts them,
    since it changed none of them, even just after a reply the user sent rode into the
    view, whose ride a reading may have caught mid-way."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Walk me through the whole rollout.")
    for step in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": f"Step {step}. "
                + "The cohort widens once the alarms hold. " * 4,
            },
        )
    page = floating(browser, url)
    open_threads(page)
    page.locator(".lf-fp-thread", has_text="Walk me through the whole rollout.").click()
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(9)
    # The user answers the last message, so the view stands at its end.
    view.evaluate("view => { view.scrollTop = view.scrollHeight; }")
    field(page).click()
    settled(page)
    if by == "menu-after-send":
        page.emulate_media(reduced_motion="no-preference")
        count = view.locator(".lf-msg").count()
        page.keyboard.insert_text("And the weekend?")
        with sending(page, "the reply"):
            page.keyboard.press("Enter")
        expect(view.locator(".lf-msg")).to_have_count(count + 1)
        settled(page)
    last = view.locator(".lf-msg").last

    def foot():
        """How far the last message stands above the view's foot, and the view's height."""
        shown, message = view.bounding_box(), last.bounding_box()
        return (
            shown["y"] + shown["height"] - message["y"] - message["height"],
            shown["height"],
        )

    before = foot()
    assert before[0] >= 0, before
    words = field(page).bounding_box()
    # The band opens on the panel's tween: its first frame shows the last message
    # beside the reply already, rather than carrying it from where it stood, under the
    # band, up into the view.
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("() => {" + HOLD_MOTION + "}")
    picture = solid_png(240, 120, (255, 128, 64))
    if by == "key":
        # The user's paste key hands the field the picture after the watches have
        # heard the key, as the browser's paste comes after its listeners, so the
        # upload and the thumbnail are that key's rendering.
        page.evaluate(
            """encoded => document.addEventListener('keydown', function paste(event) {
              if (event.key !== 'v') return;
              document.removeEventListener('keydown', paste, true);
              event.preventDefault();
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
              document.querySelector('.lf-fp-field leaf-text').dispatchEvent(
                new ClipboardEvent('paste', {
                  bubbles: true, cancelable: true, clipboardData: transfer,
                }));
            }, true)""",
            base64.b64encode(picture).decode(),
        )
        with page.expect_response(lambda response: response.url.endswith("/api/media")):
            page.keyboard.press("ControlOrMeta+v")
    else:
        paste_image(field(page), picture)
    shelf = page.locator(".lf-fp-field .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    page.wait_for_function("() => __lfHeld.length > 0")
    one_frame(page)
    assert foot()[0] == pytest.approx(before[0], abs=1), (before, foot())
    page.evaluate("() => __lfHeld.forEach(motion => motion.finish())")
    expect(shelf.locator("img")).to_have_js_property("complete", True)
    settled(page)
    tile, shown = shelf.bounding_box(), view.bounding_box()
    card = page.locator(".lf-fp-card").bounding_box()
    row = page.locator(".lf-fp-row").bounding_box()
    assert field(page).bounding_box() == words
    assert shown["y"] + shown["height"] <= tile["y"], (shown, tile)
    assert tile["y"] + tile["height"] <= row["y"], (tile, row)
    assert tile["x"] == pytest.approx(card["x"], abs=1), (tile, card)
    after = foot()
    assert after[1] < before[1], "the fixture must take the band from the view"
    assert after[0] == pytest.approx(before[0], abs=1), (before, after)
    if by != "key":
        # A menu's paste reaches the page with no key or press the hold-still watch can
        # credit, so the band moving the view's head up reads to it as news.
        consume_browser_errors(page, {"code": "moved-without-input"})


def test_a_pasted_image_s_thumbnail_arrives_at_its_picture_s_size(browser, serve):
    """A pasted image's thumbnail is drawn first at its picture's own size, however
    late the picture's bytes come back, so the shelf above the panel never steps as
    the picture decodes."""
    page = floating(browser, serve(LONG_PAGE))
    held = []
    page.route(re.compile(r"/media/[^/]+\.png$"), lambda route: held.append(route))
    page.evaluate(
        """() => {
          // Each frame's size of the thumbnail, from the frame it is first drawn.
          window.tileSizes = [];
          const SELECTOR = '.lf-fp-box .lf-composer-media-item > .lf-composer-media-open';
          const find = (root) => {
            const found = root.querySelector(SELECTOR);
            if (found) return found;
            for (const host of root.querySelectorAll('*'))
              if (host.shadowRoot) {
                const inner = find(host.shadowRoot);
                if (inner) return inner;
              }
            return null;
          };
          const read = () => {
            const tile = find(document);
            if (tile) {
              const {width, height} = tile.getBoundingClientRect();
              const last = tileSizes.at(-1);
              if (!last || last[0] !== width || last[1] !== height)
                tileSizes.push([width, height]);
            }
            requestAnimationFrame(read);
          };
          requestAnimationFrame(read);
        }"""
    )
    field(page).click()
    dispatch_paste(field(page), solid_png(40, 30, (255, 128, 64)))
    holding(page, held, 1, "the picture's bytes")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    for route in held:
        route.continue_()
    expect(field(page)).not_to_have_attribute("aria-busy", "true")
    shelf = page.locator(".lf-fp-box .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    settled(page)
    assert page.evaluate("tileSizes") == [[40, 30]]


def test_a_line_the_field_gives_up_rides_the_box_s_top_edge(browser, serve):
    """The field giving up a line moves the box's top edge down over the field's
    tween, and what that line moved rides the edge rather than jumping ahead of it:
    the tween's first frame shows the panel as it stood, attachment, words and the
    field's ring included, and midway the attachment keeps its distance from the
    edge."""
    from io import BytesIO

    from PIL import Image, ImageChops

    page = floating(browser, serve(LONG_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    field(page).click()
    page.keyboard.type("A first line")
    page.keyboard.press("Shift+Enter")
    paste_image(field(page), solid_png(40, 30, (255, 128, 64)))
    shelf = page.locator(".lf-fp-box .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    # The thumbnail takes its picture's width once the picture decodes, a frame after
    # which the box reads it.
    expect(shelf.locator("img")).to_have_js_property("complete", True)
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    settled(page)
    card, tile = page.locator(".lf-fp-card").bounding_box(), shelf.bounding_box()
    region = {
        "x": card["x"] - 8,
        "y": tile["y"] - 8,
        "width": card["width"] + 16,
        "height": card["y"] + card["height"] - tile["y"] + 16,
    }
    gaps = r"""() => {
      const top = Number.parseFloat(
        /inset\(([-\d.]+)px/.exec(
          getComputedStyle(document.querySelector('.lf-fp-ground > .lf-box-fill')).clipPath,
        )[1],
      );
      return Math.round(document.querySelector('.lf-fp-box .lf-composer-media-item')
        .getBoundingClientRect().top - top);
    }"""
    resting = page.evaluate(gaps)
    stood = Image.open(BytesIO(page.screenshot(clip=region))).convert("L")
    page.keyboard.press("Backspace")
    page.wait_for_function(
        "() => document.querySelector('.lf-fp-ground').getAnimations({subtree: true})"
        ".some(motion => motion.playState === 'running')"
    )
    seek = "at => document.getAnimations().forEach(motion => {"
    seek += " motion.pause(); motion.currentTime = at; })"
    page.evaluate(seek, 0)
    first = Image.open(BytesIO(page.screenshot(clip=region))).convert("L")
    moved = ImageChops.difference(stood, first).point(lambda v: 255 if v > 16 else 0)
    # Linux rasterizes the riding words and ring a little differently from the
    # words at rest (~200 px); a shelf or line that jumped ahead moves thousands.
    assert moved.histogram()[255] < 300, moved.getbbox()
    page.evaluate(seek, 120)
    assert page.evaluate(gaps) == resting
    page.evaluate("() => document.getAnimations().forEach(motion => motion.play())")
    settled(page)
    assert page.locator(".lf-fp-card").bounding_box()["height"] < card["height"] - 15
    assert page.evaluate(gaps) == resting


def test_a_ring_the_field_comes_back_to_mid_tween_waits_for_its_end(browser, serve):
    """The panel's field wears its ring on its ::after (floating-panel.css), which
    exists only while the focus paint marks the field's row. The field is a part of the
    box that moves, and focus leaving it and coming back while a line it gave up still
    travels makes that ::after anew. Its ring waits for the tween's end, as the one the
    motion drew from the tween's start does (dom/box-motion.js): drawn at once, it would
    stand at the field's rest size inside a box still travelling."""
    page = floating(browser, serve(LONG_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    field(page).click()
    page.keyboard.type("A first line")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("x")
    settled(page)
    box = page.locator(".lf-fp-field")
    ring = "node => getComputedStyle(node, '::after').outlineColor"
    content = "node => getComputedStyle(node, '::after').content"
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(field(page)).to_be_focused()
    worn = box.evaluate(ring)
    assert box.evaluate(content) != "none"
    assert worn != "rgba(0, 0, 0, 0)", worn
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("Backspace")
    page.keyboard.press("Backspace")
    page.wait_for_function(
        "() => __lfHeld.some(motion => motion.effect?.target?.matches?.('.lf-fp-ground'))"
    )
    page.keyboard.press("Tab")
    expect(field(page)).not_to_be_focused()
    assert box.evaluate(content) == "none"
    page.keyboard.press("Shift+Tab")
    expect(field(page)).to_be_focused()
    assert page.evaluate("() => __lfHeld.some(motion => motion.playState === 'paused')")
    assert box.evaluate(ring) == "rgba(0, 0, 0, 0)"
    page.evaluate("() => __lfHeld.splice(0).forEach(motion => motion.finish())")
    assert box.evaluate(ring) == worn


# How far the field's first line of words and the more-room mark stand below the box's
# top edge as drawn, and how opaque the mark is.
BELOW_THE_EDGE = r"""() => {
  const ground = document.querySelector('.lf-fp-ground');
  const cut = /inset\(([-\d.]+)px/.exec(
    getComputedStyle(ground.querySelector('.lf-box-fill')).clipPath,
  )[1];
  const edge = ground.getBoundingClientRect().top + Number.parseFloat(cut);
  const host = document.querySelector('.lf-fp-field leaf-text');
  const words = window.editorRoots.get(host).querySelector('.cm-line');
  const mark = document.querySelector('.lf-fp-expand');
  return {
    words: words.getBoundingClientRect().top - edge,
    mark: mark.getBoundingClientRect().top - edge,
    opacity: Number(getComputedStyle(mark).opacity),
  };
}"""
# Held motion: each motion the panel starts is held at its first frame (`HOLD_MOTION`)
# once the fixture is set up, so a reading of a frame doesn't depend on how fast the
# page runs.
# A motion a later reading cancelled stays cancelled.
SEEK_HELD = (
    "at => __lfHeld.filter(motion => motion.playState !== 'idle')"
    ".forEach(motion => { motion.currentTime = at; })"
)


def held_motion(page, part=".lf-fp-ground"):
    """Wait until a held motion moves `part`, as the box's own tween does."""
    page.wait_for_function(
        "part => __lfHeld.some(motion => motion.effect?.target?.matches?.(part))",
        arg=part,
    )


def hold_motion(page):
    """Hold each motion the page starts from now on at its first frame."""
    page.evaluate(
        "() => { window.__lfAnimate = Element.prototype.animate;" + HOLD_MOTION + "}"
    )


def finish_held(page):
    """Stop holding, finish what is held and wait for the panel to settle."""
    page.evaluate(
        "() => { Element.prototype.animate = window.__lfAnimate;"
        " __lfHeld.splice(0).filter(motion => motion.playState !== 'idle')"
        ".forEach(motion => motion.finish()); }"
    )
    settled(page)


def ink_rows(image):
    """The rows of `image` holding words, which a line cut off or jumping changes,
    while antialiasing, which differs between engines, and the caret's thin stroke
    do not."""
    width, height = image.size
    pixels = image.load()
    return {
        y for y in range(height) if sum(pixels[x, y] < 110 for x in range(width)) >= 3
    }


def test_the_field_s_words_and_mark_keep_to_its_top_edge_both_ways(browser, serve):
    """A line added raises the box's top edge in the frame the key lands, the field's
    words and the more-room mark with it, as a textarea's would; a line removed carries
    the words down with that edge over the tween, the mark riding its corner (box-
    dom/motion.js, "Whose change it is"). The mark fades in with the fourth line and out
    with it. The words don't jump to their place on removal while the edge travels,
    nor does the mark stand still while the rising edge uncovers it. The removal's
    first frame shows the field's words where they stood, so no line is cut off where
    the field's box no longer reaches."""
    from io import BytesIO

    from PIL import Image

    def picture(region):
        return Image.open(BytesIO(page.screenshot(clip=region))).convert("L")

    page = open_page(browser, serve(LONG_PAGE), init_script=EDITOR_ROOTS)
    page.emulate_media(reduced_motion="no-preference")
    field(page).click()
    page.keyboard.type("The first line of a draft")
    for line in ("and its second line", "and its third"):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(line)
    settled(page)
    three = page.evaluate(BELOW_THE_EDGE)
    assert three["opacity"] == 0, three
    top = page.locator(".lf-fp-field").bounding_box()["y"]
    hold_motion(page)
    page.keyboard.press("Shift+Enter")
    page.wait_for_function(
        "top => document.querySelector('.lf-fp-field').getBoundingClientRect().top"
        " < top - 10",
        arg=top,
    )
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => r()))")
    drawn = page.evaluate(BELOW_THE_EDGE)
    assert not page.evaluate(
        "() => __lfHeld.some(motion => motion.effect?.target?.matches?.('.lf-fp-ground'))"
    )
    assert [drawn["words"], drawn["mark"]] == pytest.approx(
        [three["words"], three["mark"]], abs=1
    ), drawn
    finish_held(page)
    assert page.evaluate(BELOW_THE_EDGE)["opacity"] == 1
    hold_motion(page)
    # The words inside the field's ring as it stood, short of Send.
    box = page.locator(".lf-fp-field").bounding_box()
    region = {
        "x": box["x"] + 3,
        "y": box["y"] + 3,
        "width": box["width"] - 40,
        "height": box["height"] - 6,
    }
    stood = picture(region)
    page.keyboard.press("Backspace")
    held_motion(page)
    page.evaluate(SEEK_HELD, 0)
    assert ink_rows(picture(region)) == ink_rows(stood)
    for at in (0, 60, 150):
        page.evaluate(SEEK_HELD, at)
        drawn = page.evaluate(BELOW_THE_EDGE)
        assert [drawn["words"], drawn["mark"]] == pytest.approx(
            [three["words"], three["mark"]], abs=1
        ), (at, drawn)
    finish_held(page)
    rest = page.evaluate(BELOW_THE_EDGE)
    assert [rest["words"], rest["mark"]] == pytest.approx(
        [three["words"], three["mark"]], abs=1
    ), rest
    assert rest["opacity"] == 0, rest


def test_a_send_s_reply_field_takes_the_row_s_seat_where_it_stands(browser, serve):
    """Sending a page comment of several lines opens its thread above the row, and the
    thread's reply field takes the page field's seat in the row from the tween's first
    frame. A field that rose from below the window with the box's top edge would leave
    the row showing no field until the tween's last frames."""
    page = floating(browser, serve(LONG_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    field(page).click()
    page.keyboard.type("A comment")
    for line in ("that opens", "its thread"):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(line)
    settled(page)
    hold_motion(page)
    page.keyboard.press("Enter")
    # The box's tween as the thread's view opens over the row.
    held_motion(page, ".lf-fp-opened")
    reply = page.locator(".lf-fp-reply-outlet")
    drawn = (
        "reply => [reply.getBoundingClientRect().top, getComputedStyle(reply).clipPath]"
    )
    first = reply.evaluate(drawn)
    finish_held(page)
    assert first == reply.evaluate(drawn), first


def test_looking_at_an_attached_image_keeps_the_draft_where_it_stands(browser, serve):
    """The image viewer opened from a draft's attachment stands over the panel, and
    Escape hands the user back to the attachment: they never left what they were
    writing, so the page's field keeps Send in its corner and the counts aside, behind
    the viewer, after it and as they press back into the words, and a rewrite keeps
    its thread view's height. The draft's picture stands above the box's top-left
    corner, so the panel's fold, which a pointer at that corner shows, stands clear of
    the picture, and a pointer on the picture shows no fold."""
    page = floating(browser, serve(LONG_PAGE))
    viewer = page.locator("dialog.lf-media-viewer")

    def look_at(picture):
        # Its foot's start, clear of the removal mark on its top corner.
        picture.click(position={"x": 3, "y": picture.bounding_box()["height"] - 3})
        expect(viewer).to_be_visible()
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()
        expect(picture).to_be_focused()

    write(field(page), "A draft long enough to wrap once the counts stand beside it")
    paste_image(field(page), solid_png(40, 30, (255, 128, 64)))
    send = page.locator(".lf-fp-field .lf-compose-submit")
    expect(send).to_be_visible()
    words = field(page).bounding_box()
    picture = page.locator(".lf-fp-box .lf-composer-media-open")
    fold = page.locator(".lf-fp-minimize")
    card = page.locator(".lf-fp-card").bounding_box()
    page.mouse.move(card["x"] + 20, card["y"] + 6)
    expect(fold).to_be_visible()
    foot = picture.bounding_box()
    assert picture.evaluate(
        "(picture, [x, y]) => picture.contains(document.elementFromPoint(x, y))",
        [foot["x"] + 3, foot["y"] + foot["height"] - 1],
    )
    page.mouse.move(foot["x"] + 3, foot["y"] + foot["height"] - 3)
    expect(fold).to_be_hidden()
    look_at(picture)
    expect(send).to_be_visible()
    assert field(page).bounding_box() == words
    field(page).click()
    assert field(page).bounding_box() == words

    page.keyboard.press("Enter")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_contain_text("A draft long enough")
    settled(page)
    view.locator(".lf-msg-body").dblclick()
    rewrite = view.locator(".lf-msg-editor leaf-text")
    expect(rewrite).to_be_focused()
    paste_image(rewrite, solid_png(40, 30, (64, 128, 255)))
    settled(page)
    stood = view.bounding_box()
    look_at(view.locator(".lf-msg-editor .lf-media-open").last)
    settled(page)
    assert view.bounding_box() == stood


def test_a_draft_draws_a_list_as_the_message_will(browser, serve):
    """A draft's list items stand where the sent message's do: their words at the same
    inset and height, a wrapped line under the words, under the same platform marker,
    nested as the message nests it, and the message as tall as the draft, a line apart
    only where the draft left a blank line and a code block's fences keeping their
    room. An item's source marker shows instead while the caret touches it, and its
    words stay where they stood."""
    page = open_page(browser, serve(LONG_PAGE), init_script=EDITOR_ROOTS)
    # The renderer the draft is read by loads lazily, and its arrival redraws a field
    # already holding words; load it first, so the list is drawn as it is typed.
    page.evaluate(
        "async () => (await import('/runtime/lib/markdown.js')).loadMarkdown()"
    )
    field(page).click()
    # The first item wraps to two lines both in the field and in the sent message's
    # wider column, so the two hold the same lines.
    page.keyboard.insert_text(
        "Notes:\n- "
        + "an item long enough to wrap in the field " * 2
        + "\n- parent\n      deeper\n    - child\n\n1. one\n\n       indented"
        + "\n\n```\ncode\n```\nend"
    )
    # The field grows to hold the draft; let it come to rest before reading it.
    settled(page)
    # Where a word stands in a box: "deeper", on a line continuing the parent's, and
    # "indented", the code an item holds.
    seen = """(box, word) => {
      const walk = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) {
        const at = walk.currentNode.data.indexOf(word);
        if (at < 0) continue;
        const words = document.createRange();
        words.setStart(walk.currentNode, at);
        words.setEnd(walk.currentNode, at + word.length);
        return Math.round(words.getBoundingClientRect().left - box.getBoundingClientRect().left);
      }
    }"""
    words = ("deeper", "indented")

    def drafted():
        return field(page).evaluate(
            """host => {
              const root = window.editorRoots.get(host);
              const content = root.querySelector('.cm-content').getBoundingClientRect();
              const items = root.querySelectorAll('.cm-line:has(.lf-md-marker)');
              return [...items].map((line) => {
                const mark = line.querySelector('.lf-md-marker');
                const words = document.createRange();
                words.setStartAfter(mark);
                words.setEnd(line, line.childNodes.length);
                const rows = [...words.getClientRects()];
                // The marker is the item's box's, the nearest list item holding the line.
                let item = line;
                while (item && getComputedStyle(item).display !== 'list-item')
                  item = item.parentElement?.closest('.cm-content *') ?? null;
                const style = item && getComputedStyle(item);
                return {
                  words: rows[0].left - content.left,
                  top: rows[0].top - content.top,
                  wrapped: rows.at(-1).left - content.left,
                  marker: style && style.listStyleType !== 'none' ? style.listStyleType : null,
                  source: getComputedStyle(mark).webkitTextFillColor !== 'rgba(0, 0, 0, 0)',
                  height: content.height,
                };
              });
            }"""
        )

    away = drafted()
    drafted_words = [
        field(page).evaluate(
            f"(host, word) => ({seen})("
            "window.editorRoots.get(host).querySelector('.cm-content'), word)",
            word,
        )
        for word in words
    ]
    assert [item["marker"] for item in away] == ["disc", "disc", "circle", "decimal"]
    assert not any(item["source"] for item in away), away
    assert away[0]["wrapped"] == away[0]["words"], away
    page.keyboard.press("ControlOrMeta+Home")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowLeft")
    near = drafted()
    assert (near[0]["marker"], near[0]["source"]) == (None, True), near
    assert near[0]["words"] == away[0]["words"]

    page.keyboard.press("ControlOrMeta+Enter")
    sent = page.locator(f"{panel_view('thread')} .lf-msg-text")
    expect(sent.locator("li")).to_have_count(4)
    shown = sent.evaluate(
        """text => {
          const box = text.getBoundingClientRect();
          return [...text.querySelectorAll('li')].map((li) => {
            const words = document.createRange();
            const walk = document.createTreeWalker(li, NodeFilter.SHOW_TEXT);
            while (walk.nextNode() && !walk.currentNode.data.trim());
            words.selectNodeContents(walk.currentNode);
            const row = words.getClientRects()[0];
            return {
              words: row.left - box.left,
              top: row.top - box.top,
              marker: getComputedStyle(li).listStyleType,
              height: box.height,
            };
          });
        }"""
    )

    def placed(items):
        return [
            {key: round(item[key]) if key != "marker" else item[key] for key in keys}
            for item in items
        ]

    keys = ("words", "top", "marker", "height")
    assert placed(away) == placed(shown)
    assert drafted_words == [sent.evaluate(seen, word) for word in words]
    assert drafted_words[0] == round(away[1]["words"])


def test_send_stands_in_the_field_s_corner_while_the_field_holds_a_draft(
    browser, serve
):
    """Opening the field moves nothing in the row, so the field's end and the corner's
    action stand where typing will leave them, the leaf beside them; typing puts Send in
    that corner, wearing every composer's accent arrow rather than the panel's own press
    face, and the field runs to the room the leaf's badges hang into; a line break is a
    draft as a word is. A press
    that takes the caret away leaves the draft as it stands, Send and every line in
    place, and so does a press back into it."""
    page = floating(browser, serve(LONG_PAGE))
    leaf = page.locator(".lf-fp-leaf")
    settled(page)
    beside = leaf.bounding_box()
    field(page).click()
    settled(page)
    assert leaf.bounding_box() == beside
    opened = field(page).bounding_box()
    send = page.locator(".lf-fp-send")
    page.keyboard.press("Shift+Enter")
    page.keyboard.press("Backspace")
    settled(page)
    assert field(page).bounding_box() == opened
    page.keyboard.type("Could the rollback cover the weekend, and the Monday after it?")
    expect(send).to_be_visible()
    accent = page.evaluate(
        "() => { const probe = document.createElement('span'); probe.style.color = 'var(--lf-accent)';"
        " document.body.append(probe); const seen = getComputedStyle(probe).color;"
        " probe.remove(); return seen; }"
    )
    expect(send).to_have_css("color", accent)
    settled(page)
    short = page.evaluate(
        "() => document.querySelector('.lf-fp-leaf').getBoundingClientRect().left"
        " - document.querySelector('.lf-fp-field').getBoundingClientRect().right"
    )
    assert short <= 8, f"the drafted field stops {short}px short of the leaf"
    assert leaf.bounding_box() == beside
    words = field(page).bounding_box()
    page.mouse.click(5, 5)
    expect(field(page)).not_to_be_focused()
    settled(page)
    expect(send).to_be_visible()
    assert field(page).bounding_box() == words
    field(page).click()
    settled(page)
    assert field(page).bounding_box() == words
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    page.mouse.click(5, 5)
    settled(page)
    assert leaf.bounding_box() == beside


def test_writing_reaches_the_field_however_the_panel_stands(browser, serve):
    """Asking to write reaches the panel's field from any state it stands in: `c`
    unfolds a panel folded to the leaf and makes the field the box the words go in, out
    to the panel's top, left and bottom edges with its ring just inside them and a
    ground lighter than the panel's, so the move shows; and Resume writing comes back to
    a reply left unsent in a thread the user has since closed, in the same field."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-lf-rest", "mark")
    page.locator("body").focus()
    page.keyboard.press("c")
    expect(panel).to_have_attribute("data-lf-rest", "row")
    expect(field(page)).to_be_focused()
    face = page.locator(".lf-fp-field").evaluate(
        """box => {
          const ring = getComputedStyle(box, '::after');
          const card = document.querySelector('.lf-fp-card');
          const at = box.getBoundingClientRect(), edge = card.getBoundingClientRect();
          return [ring.outlineStyle, ring.outlineWidth, ring.outlineOffset,
            getComputedStyle(box).backgroundColor !== getComputedStyle(card).backgroundColor,
            [at.top - edge.top, at.left - edge.left, edge.bottom - at.bottom]
              .map(Math.round)];
        }"""
    )
    assert face == ["solid", "2px", "-2px", True, [0, 0, 0]], (
        f"the field holding the caret wears {face}"
    )
    page.keyboard.press("Escape")

    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(panel_view("thread"))).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
    page.locator(".lf-fp-close").click()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(panel_view("thread"))).to_be_visible()
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    # The resume has drawn whatever it decided, an error included.
    rendered(page)
    expect(page.get_by_text("That writing place is unavailable")).to_have_count(0)


def test_the_field_s_ring_stands_over_what_covers_its_words(browser, serve):
    """The ring the field wears while it holds the caret stands one band inside the
    box's edge, where Send stands, so what paints the field's paper over the words
    leaves it whole: Send shown over words that run under its corner, under a resting
    pointer, and an error about the field."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    for word in ("the words run on toward the corner where Send stands " * 4).split():
        page.keyboard.insert_text(f"{word} ")
        rendered(page)
        if field(page).evaluate("(node) => node.matches(':state(corner-taken)')"):
            break
    else:
        raise AssertionError("the words never reached Send's corner")
    send = page.locator(".lf-fp-field .lf-compose-submit").bounding_box()
    assert send is not None
    page.mouse.move(send["x"] + send["width"] / 2, send["y"] + send["height"] / 2)
    expect(page.locator(".lf-fp-field .lf-compose-field")).to_have_attribute(
        "data-lf-send-armed", ""
    )
    rendered(page)
    assert not (faults := ring_faults(rings_drawn(page), "with Send over the words")), (
        "\n".join(faults)
    )

    field(page).evaluate(
        "async (subject) => (await window.__lfCheckApi())"
        ".raiseError('That writing place is unavailable', {subject})"
    )
    expect(page.locator(".lf-fp-field .lf-compose-error")).to_be_visible()
    rendered(page)
    assert not (faults := ring_faults(rings_drawn(page), "under an error")), "\n".join(
        faults
    )


def test_a_press_inside_the_field_s_ring_keeps_its_words_focused(browser, serve):
    """Holding the caret, the field's slot runs to the panel's edges and wears the ring
    one band inside them, so a press between the ring and the words' box is a press on
    the field, and the words keep the focus."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    page.keyboard.insert_text("A comment being written")
    slot = page.locator(".lf-fp-field").bounding_box()
    words = page.locator(".lf-fp-field .lf-compose-field").bounding_box()
    assert slot is not None and words is not None
    # The band the slot's padding holds, beside the words' box and above and below it.
    for x, y in (
        (slot["x"] + 3, slot["y"] + slot["height"] / 2),
        (words["x"] + words["width"] / 2, slot["y"] + 3),
        (words["x"] + words["width"] / 2, slot["y"] + slot["height"] - 3),
    ):
        assert words["x"] > x or y < words["y"] or y > words["y"] + words["height"]
        page.mouse.click(x, y)
        expect(field(page)).to_be_focused()


def test_the_comment_box_seated_in_the_row_keeps_its_line(browser, serve):
    """The comment box that stands in the field's place on a page drawing its own
    annotations takes turns with the field, so it is the row's line tall too. Its own
    resting height, the pointer's floor, would stand the row taller under a
    finger."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, serve(PAGE_ANNOTATED), context=context)
    row = page.locator(".lf-fp-row")
    rest = row.bounding_box()["height"]
    select_words(page, "#p3")
    page.keyboard.press("c")
    expect(page.locator(".lf-fp-response leaf-text")).to_be_focused()
    assert row.bounding_box()["height"] == pytest.approx(rest, abs=0.5)


def test_an_answer_superseded_during_widget_preparation_keeps_its_arrival(
    browser, serve
):
    """An answer painted while its widget prepares is still arriving when another
    publication supersedes that paint; accepting it must offer its overflowing words."""
    url = serve(
        LONG_PAGE,
        page_files={
            "registry.json": json.dumps(PAGE_DECLARATION),
            "widgets/lf-local.js": PAGE_WIDGET,
        },
    )
    root = panel_comment(serve.page_dir, "Which job comes first?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    page.evaluate("""async () => {
      const presentation = await window.__lfCheckApi();
      window.readLeafPresentation = presentation.readApplicationPresentation;
      const pending = new Promise(resolve => { window.releaseAnswer = resolve; });
      window.__heldLocalPresentations = new Map([['thread-local', pending]]);
    }""")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": root,
            "text": "The mounts come first.\n\n<p>"
            + "The mounts come first. " * 300
            + "</p>"
            '<lf-local id="thread-local" choice="idle"></lf-local>',
        },
    )
    page.wait_for_function("""() => {
      const pending = readLeafPresentation().pending;
      return document.querySelector('.lf-floating-panel #thread-local') &&
        pending.includes('thread') && pending.includes('widget:thread-local:preparation');
    }""")
    # The answer is already drawn: its geometry must not wait on widget preparation.
    expect(view.locator(".lf-new-reply")).to_have_text("New reply")
    # The feed waits for presentation before reading again, but a local gesture
    # publishes immediately while this answer's widget is still preparing.
    page.evaluate("""async () => {
      const api = await window.__lfWidgetApi();
      api.threadActions.create({attempt: crypto.randomUUID(), text: 'Another question.'});
    }""")
    page.evaluate("releaseAnswer()")
    told(page)
    press = view.locator(".lf-new-reply")
    expect(press).to_have_text("New reply")
    settled(page)
    press.click()
    expect(press).to_have_count(0)
    settled(page)
    shown, box = view.locator(".lf-msg").last.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)


import pytest
from render_harness import (
    LONG_PAGE,
)
