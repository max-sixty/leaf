"""News arriving in the Threads panel, from agent replies, streams, claims and other
tabs, either waits behind a notice or lands without moving what the user is reading,
typing in or pressing."""

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, record_claim
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf.render_checks import one_frame, rendered
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    holding,
    nudge,
    open_page,
    panel_settled,
    round_trip,
    scroll_settled,
    told,
    write,
)

from browser.threads import (
    IN_LANDING_BAND,
    LANDING_WORDS,
    append_agent_reply,
    append_user_reply,
    focus_panel_thread,
    hold_visible_thread_presentation,
    open_threads_list,
    reply_by_keyboard,
    seed_panel_threads,
)

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
    root = panel_comment(serve.page_dir, "Keep this discussion open.")
    page = open_page(browser, url)
    page.emulate_media(reduced_motion=motion)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    focus_panel_thread(card)
    field = card.locator("leaf-text")
    words = "A thought to continue when I return."
    write(field, words)
    field.evaluate(
        "field => { field.setSelectionRange(8, 8); window.__returnEditor = field; }"
    )
    first = append_agent_reply(serve.page_dir, root, "An answer held during reading.")
    told(page)
    expect(card.locator(".lf-thread-news")).to_be_visible()
    first_message = card.locator(f'.lf-msg[data-mid="{first["id"]}"]')
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
    expect(card.locator(f'.lf-msg[data-mid="{second["id"]}"]')).to_have_count(0)
    held.pop().continue_()
    page.unroute("**/api/state*")
    told(page)
    rendered(page)
    expect(card.locator(f'.lf-msg[data-mid="{second["id"]}"]')).to_be_visible()
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    expect(field).to_have_js_property("value", words)
    expect(field).to_be_focused()
    assert field.evaluate("""field => field === window.__returnEditor
      && field.selectionStart === 8 && field.selectionEnd === 8""")

    third = append_agent_reply(serve.page_dir, root, "News after reading resumes.")
    told(page)
    rendered(page)
    expect(card.locator(".lf-thread-news")).to_be_visible()
    expect(card.locator(f'.lf-msg[data-mid="{third["id"]}"]')).to_have_count(0)


@pytest.mark.watch_shifts
def test_returning_to_a_hidden_tab_applies_a_held_resolution_to_the_open_filter(
    browser, serve
):
    """A card kept in Open during reading leaves when that reading ends."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "This discussion will be settled elsewhere.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    focus_panel_thread(card)
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "agent", "parent": root}
    )
    told(page)
    rendered(page)
    expect(card.get_by_role("button", name="Resolved", exact=True)).to_be_visible()
    expect(card).to_have_attribute("data-resolved", "false")

    page.evaluate("""() => {
      window.__lfTestVisibility = 'hidden';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => window.__lfTestVisibility,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    with page.expect_request("**/api/news"):
        page.evaluate("""() => {
          window.__lfTestVisibility = 'visible';
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
    told(page)
    rendered(page)
    expect(card).to_be_hidden()
    expect(card).to_have_attribute("data-resolved", "true")


def test_an_arriving_reply_leaves_the_list_where_the_user_put_it(browser, serve):
    """News has no gesture behind it, so it may move nothing the user is looking at.
    The hard case is a reply landing in a thread above the fold: the list grows over
    the user's head, and what must hold still is the thread in front of them — their
    place as a box on screen, not as a scrollTop the browser's own scroll anchoring is
    free to adjust. The old rebuild restored the offset and let the content slide under
    it."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    held = page.evaluate("""() => {
        const box = document.querySelector('.lf-threads');
        box.scrollTop = 400;
        const b = box.getBoundingClientRect();
        window.__held = [...box.querySelectorAll(':scope > .lf-thread')]
            .find(n => n.getBoundingClientRect().top >= b.top);
        return { top: window.__held.getBoundingClientRect().top,
                 scrolled: box.scrollTop > 0 };
    }""")
    assert held["scrolled"], "the list doesn't scroll, so nothing here can move"

    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "News, not a gesture.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    after = page.evaluate(
        "() => ({ connected: window.__held.isConnected,"
        "          top: window.__held.getBoundingClientRect().top })"
    )
    assert after["connected"], "the held thread was replaced, so its box says nothing"
    assert abs(after["top"] - held["top"]) < 1, (
        f"the arriving reply moved the thread the user was on: {held} -> {after}"
    )


def test_an_arriving_reply_cannot_move_resolve_out_from_under_a_press(browser, serve):
    """A state read between the two halves of a mouse press must keep its target put.

    The reply grows the preceding card after the user has pressed Resolve on the next
    one. If reconciliation lets that next card move, mouseup lands on the list instead
    of the button and the browser emits no click at all. Drive the two halves separately
    so the ordering is the test's arrangement rather than a scheduling accident."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[12:14]
    page.locator(f'.lf-thread[data-id="{target}"] .lf-thread-summary').click()
    # Opening closes the card above, and the list's hold on the pressed title corrects
    # for that on the next render; the scroll below comes after it.
    rendered(page)
    page.locator(f'.lf-thread[data-id="{target}"]').evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    scroll = page.locator(".lf-threads").evaluate(
        "el => ({at: el.scrollTop, max: el.scrollHeight - el.clientHeight})"
    )
    assert 0 < scroll["at"] < scroll["max"], (
        f"the pressed card is at a scroll limit, so the list cannot hold it: {scroll}"
    )
    resolve = page.locator(f'.lf-thread[data-id="{target}"] .lf-resolve')
    box = resolve.bounding_box()
    point = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
    reading = """([x, y, id]) => {
      const button = document.querySelector(
        `.lf-thread[data-id="${id}"] .lf-resolve`
      );
      const hit = document.elementFromPoint(x, y);
      const list = document.querySelector('.lf-threads');
      return {
        same: hit === button,
        hit: hit && `${hit.tagName.toLowerCase()}.${hit.className}`,
        button: button.getBoundingClientRect().toJSON(),
        card: button.closest('.lf-thread').getBoundingClientRect().toJSON(),
        scrollTop: list.scrollTop,
      };
    }"""
    page.mouse.move(*point)
    page.mouse.down()
    began = page.evaluate(reading, [*point, target])
    assert began["same"], f"the press did not begin on Resolve: {began}"

    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": source,
            "text": "This arrived while Resolve was held down.",
        },
    )
    told(page)
    arrived = page.evaluate(reading, [*point, target])
    assert arrived["same"], (
        f"the arriving reply moved Resolve out from under the pointer: "
        f"{began} -> {arrived}"
    )

    with page.expect_request("**/api/event"):
        page.mouse.up()
    round_trip(page)
    assert any(
        event["kind"] == "resolve" and event["parent"] == target
        for event in events_model.read_events(serve.page_dir)
    ), "mouseup did not complete the Resolve press"
    # A folded card draws its title row alone, so it took the reply in at once.
    source_thread = page.locator(f'.lf-thread[data-id="{source}"]')
    source_thread.locator(".lf-thread-summary").click()
    expect(source_thread.locator(".lf-thread-news")).to_have_count(0)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_be_visible()


def test_a_work_claim_cannot_move_a_later_control_under_the_pointer(browser, serve):
    """A claim-only poll grows one card without reconciling the thread list itself.

    The work-line writer shares the list's hold so provisional news arriving above a
    control cannot move that control out from under a user who is aiming at it."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[2:4]
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    target_box = target_card.bounding_box()
    page.mouse.move(
        target_box["x"] + target_box["width"] / 2,
        target_box["y"] + target_box["height"] / 2,
    )
    before = target_card.evaluate("el => el.getBoundingClientRect().top")

    claimed = CliRunner().invoke(
        cli_model.cli,
        ["task", "start", str(serve.page_dir), source, "reading the traces"],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    expect(
        page.locator(f'.lf-thread[data-id="{source}"] .lf-thread-status')
    ).to_have_text("Working")
    after = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert after == pytest.approx(before, abs=1), (
        f"the work claim moved the later card from {before:.1f}px to {after:.1f}px"
    )


@pytest.mark.parametrize("contents", ["short", "long"])
def test_an_arrival_interrupts_nothing_the_user_holds(browser, serve, contents):
    """The nodes themselves survive the poll: the thread being typed in is the same
    element afterwards, still focused, caret where the typing left it — even when the
    arrival concerns that very thread. Short conversations hold news that would move
    the editor; a long conversation can show it above the pinned editor."""
    url = serve(LONG_PAGE, comments=1)
    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    if contents == "long":
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": first["id"],
                "revision": 1,
                "text": "\n\n".join(
                    ["Keep the conversation visible while writing."] * 20
                ),
            },
        )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{first["id"]}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    band = page.locator(".lf-threads").bounding_box()["height"]
    assert (thread.bounding_box()["height"] > band) is (contents == "long")
    ta = thread.locator("leaf-text")
    ta.click()
    ta.type("half a thought")
    page.evaluate("""() => {
        document.activeElement.setSelectionRange(4, 4);
        window.__heldEditor = document.activeElement;
        window.__probe = document.activeElement.closest('.lf-thread');
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
    arrived = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    if contents == "short":
        expect(
            thread.get_by_role("button", name="1 new reply", exact=True)
        ).to_be_visible()
        expect(arrived).to_have_count(0)
    else:
        expect(arrived).to_be_visible()
        expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    after = ta.bounding_box()
    for edge in before:
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)
    assert page.evaluate("""() => {
        const ta = document.activeElement;
        return ta.localName === 'leaf-text'
            && ta === window.__heldEditor
            && ta.closest('.lf-thread') === window.__probe
            && window.__probe === document.querySelector('.lf-threads > .lf-thread')
            && ta.value === 'half a thought'
            && ta.selectionStart === 4 && ta.selectionEnd === 4;
    }"""), "the poll replaced or disturbed the node the user was typing into"


def test_a_reply_row_at_its_thread_end_follows_an_arrival_as_a_pinned_one(
    browser, serve
):
    """A long thread scrolled to where its reply row stands on the list's foot line in
    its own place, the thread's very end, takes an agent's turn as a pinned row does.

    The turn grows the transcript above the row, which then sticks where it stood, so
    the list follows the turn: its words show above the editor at once, and the
    editor and the user's draft stay where they were. Read as unpinned, the turn would
    wait behind a notice or end under the row."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    append_agent_reply(
        serve.page_dir, root, "\n\n".join(["Keep the conversation visible."] * 30)
    )
    panel_comment(serve.page_dir, "A later conversation.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    focus_panel_thread(thread)
    field = thread.locator("leaf-text")
    write(field, "half a thought")
    rendered(page)
    # How far the row stands above its own place in the card (0 where it is there), and
    # how far its own place is past the list's foot line.
    place = """card => {
      const row = card.querySelector(':scope > .lf-thread-reply');
      const list = card.closest('.lf-threads');
      const edges = getComputedStyle(card);
      const own = card.getBoundingClientRect().bottom
        - parseFloat(edges.borderBottomWidth) - parseFloat(edges.paddingBottom);
      const foot = list.getBoundingClientRect().bottom
        - parseFloat(getComputedStyle(list).paddingBottom)
        - parseFloat(getComputedStyle(row).bottom);
      return {lifted: own - row.getBoundingClientRect().bottom, past: own - foot};
    }"""
    page.locator(".lf-threads").hover()
    for _ in range(3):
        past = thread.evaluate(place)["past"]
        if abs(past) < 0.5:
            break
        page.mouse.wheel(0, round(past))
        rendered(page)
    placed = thread.evaluate(place)
    assert abs(placed["lifted"]) < 0.5 and abs(placed["past"]) < 1, placed
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    before = field.bounding_box()
    reply = append_agent_reply(serve.page_dir, root, "Landing right above the box.")
    told(page)
    arrived = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    expect(arrived).to_be_visible()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    after = field.bounding_box()
    for edge in before:
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)
    assert arrived.bounding_box()["y"] + arrived.bounding_box()["height"] <= after["y"]
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "half a thought")


@pytest.mark.parametrize(
    ("contents", "finish"),
    [("short", "reveal"), ("long", "reveal"), ("short", "cancel")],
    ids=["short", "long", "canceled-short"],
)
def test_a_stream_growing_keeps_the_panel_editor_still(
    browser, serve, request, contents, finish
):
    """Growing an existing streamed turn holds the same boundary as a new reply.

    A short conversation keeps its painted body until the reader opens its notice;
    a pinned long conversation follows the latest words while retaining the editor.
    Opening held news reveals the latest body after more typing; canceling the stream
    removes its held notice as well as its words.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Answer me here", {"section": "h-how"})
    claim = record_claim(
        serve.page_dir, id="codex-thread", harness="codex", agent="Codex"
    )
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)
    attempt = service_model.delivery_reply_attempt("delivery-1")
    original = "Keep the conversation visible."
    if contents == "long":
        original = "\n\n".join([original] * 20)

    def stream(words):
        with service_model.PageTransaction(serve.page_dir) as transaction:
            transaction.set_status("waiting", "User feedback")
            transaction.set_stream_reply(
                "codex-thread", "leaf-turn", root, root, attempt, None, words, "active"
            )

    stream(original)
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    body = thread.locator(f'.lf-msg[data-attempt="{attempt}"] .lf-msg-text')
    expect(body).to_have_text(original)
    band = page.locator(".lf-threads").bounding_box()["height"]
    assert (thread.bounding_box()["height"] > band) is (contents == "long")
    field = thread.locator("leaf-text")
    write(field, "half a thought")
    field.evaluate("""field => {
      field.setSelectionRange(4, 4);
      window.__heldStreamEditor = field;
    }""")
    before = field.bounding_box()
    latest = original
    for paragraph in ("The next part of the answer.", "The completed thought follows."):
        latest += "\n\n" + paragraph
        stream(latest)
        told(page)
        if contents == "short":
            expect(
                thread.get_by_role("button", name="1 new reply", exact=True)
            ).to_be_visible()
            expect(body).to_have_text(original)
        else:
            expect(body).to_have_text(latest)
            expect(thread.locator(".lf-thread-news")).to_have_count(0)
        rendered(page)
        after = field.bounding_box()
        for edge in before:
            assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)
        assert field.evaluate("""field => field === window.__heldStreamEditor
          && field === document.activeElement && field.value === 'half a thought'
          && field.selectionStart === 4 && field.selectionEnd === 4""")
    if contents == "short":
        page.keyboard.insert_text(" newer")
        rendered(page)
        expect(body).to_have_text(original)
        expect(
            thread.get_by_role("button", name="1 new reply", exact=True)
        ).to_be_visible()
        assert field.evaluate("field => field.value") == "half newer a thought"
        if finish == "cancel":
            with service_model.PageTransaction(serve.page_dir) as transaction:
                transaction.clear_stream_reply("codex-thread", "leaf-turn")
            told(page)
            expect(body).to_have_count(0)
            expect(thread.locator(".lf-thread-news")).to_have_count(0)
            expect(field).to_be_focused()
        else:
            thread.get_by_role("button", name="1 new reply", exact=True).click()
            expect(body).to_have_text(latest)
        assert field.evaluate("""field => field === window.__heldStreamEditor
          && field.value === 'half newer a thought'""")


ITEM_MARKUP = (
    '<lf-ask id="held-question"><h3>Which answer should we use?</h3>'
    '<lf-options id="held-choice" choose>'
    '<lf-option id="held-first">The first answer</lf-option>'
    '<lf-option id="held-second">The second answer</lf-option>'
    "</lf-options></lf-ask>"
)


@pytest.mark.parametrize("destination", ["message", "item", "shown-ask"])
def test_explicit_navigation_reveals_held_panel_news(browser, serve, destination):
    """A direct message visit and the Ask walk can reach a held reply's contents.
    Walking from outside the thread to an Ask it already shows ("shown-ask") is an
    arrival at the thread too, so the reply held after it shows."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    if destination == "shown-ask":
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "parent": root,
                "text": "One question first.",
                "markup": ITEM_MARKUP,
            },
        )
    context = browser.new_context(reduced_motion="reduce")
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    field = thread.locator("leaf-text")
    write(field, "Keep this draft while visiting the answer.")
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "parent": root,
            "text": "This answer arrived while the draft was open.",
            **({"markup": ITEM_MARKUP} if destination == "item" else {}),
        },
    )
    told(page)
    message = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    expect(thread.get_by_role("button", name="1 new reply", exact=True)).to_be_visible()
    expect(message).to_have_count(0)
    if destination == "message":
        page.evaluate(
            """async id => {
              const {readThreads, threadActions} = await window.__lfWidgetApi();
              const thread = readThreads().threads.find(thread =>
                thread.msgs.some(message => message.id === id));
              const message = thread.msgs.find(message => message.id === id);
              await threadActions.open(thread.key, {message: message.key});
            }""",
            reply["id"],
        )
        expect(message).to_be_focused()
    else:
        # The Ask walk, not the drawer: opening the drawer covers the card, and a held
        # reply nobody can see shows anyway. The walk starts with the user standing
        # nowhere, so it arrives at the thread; from its reply box it would be a move
        # within the thread.
        field.evaluate("field => field.blur()")
        page.wait_for_function("document.activeElement === document.body")
        expect(
            thread.get_by_role("button", name="1 new reply", exact=True)
        ).to_be_visible()
        page.keyboard.press("m")
        expect(thread.locator("#held-question")).to_be_focused()
    expect(message).to_be_visible()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    assert field.evaluate("field => field.value") == (
        "Keep this draft while visiting the answer."
    )


@pytest.mark.parametrize(
    ("reply_count", "new_input", "walk"),
    [
        (1, None, "back"),
        (3, None, "back"),
        (3, "Tab", "back"),
        (3, "wheel", "back"),
        (3, "widget", "back"),
        (3, None, "onto"),
        (1, None, "return"),
        (1, None, "pressed"),
    ],
)
def test_walking_to_a_thread_shows_the_replies_it_held(
    browser, serve, reply_count, new_input, walk
):
    """Replies held while their thread stood open in front of the user show once the
    user walks away and back to that thread with t/T. The walk away closes the card and
    the walk back opens it, and an opening moves every card after it anyway, so the card
    opens with what it held, landed where the newest reply shows. Pressing onto the
    thread the user already stands in, the only one the walk has, moves them nowhere, so
    its news stays held; leaving the thread with Shift+Tab and walking back onto its
    card, which stood open throughout ("return"), arrives there, and shows it, as a
    press on its title from there does ("pressed"). One reply fits with the root;
    several require measuring the released transcript to land its end. Disclosure itself
    draws that body before a delayed public proof, so a newer Tab reaches its current
    controls and supersedes the older title's pending landing. A released reply's widget
    reads its frozen baseline and takes a new choice while that global proof is held;
    the later publication keeps the choice it sent."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    other = None
    if walk != "onto":
        other = panel_comment(serve.page_dir, "A thread to walk to. " * 30)
        for n in range(12):
            panel_comment(serve.page_dir, f"A later thread {n}. " * 8)
    context = browser.new_context(
        viewport={"width": 800, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    order = page.locator(".lf-threads > .lf-thread").evaluate_all(
        "cards => cards.map(card => card.dataset.id)"
    )
    assert order[:2] == ([root, other] if other else [root])
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    summary = thread.locator(".lf-thread-summary")
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    write(thread.locator("leaf-text"), "Keep this draft while reading replies.")
    thread.locator(".lf-thread-summary").focus()
    for turn in range(reply_count):
        reply = append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "parent": root,
                "text": f"Turn {turn}. This answer arrived while the thread stood open. "
                * 6,
                **(
                    {
                        "markup": '<lf-options id="held-choice" choose>'
                        '<lf-option id="held-first" chosen>The first answer</lf-option>'
                        '<lf-option id="held-second">The second answer</lf-option>'
                        "</lf-options>"
                    }
                    if new_input == "widget" and turn == reply_count - 1
                    else {}
                ),
            },
        )
    told(page)
    message = thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')
    notice = "1 new reply" if reply_count == 1 else f"{reply_count} new replies"
    expect(thread.get_by_role("button", name=notice, exact=True)).to_be_visible()
    expect(message).to_have_count(0)

    if walk == "back":
        page.keyboard.press("t")
        expect(
            page.locator(
                f'.lf-threads > .lf-thread[data-id="{other}"] .lf-thread-summary'
            )
        ).to_be_focused()
        expect(thread).not_to_have_attribute("open", "")
        # A closed card draws one title row, so it holds nothing back; its reply waits
        # unseen in the folded body.
        expect(message).to_be_hidden()
    if walk in ("return", "pressed"):
        page.keyboard.press("Shift+Tab")
        page.wait_for_function(
            "id => !document.activeElement?.closest?.(`[data-id='${id}']`)", arg=root
        )
        expect(thread).to_have_attribute("open", "")
        if walk == "pressed":
            summary.click()
        else:
            page.keyboard.press("t")
        expect(summary).to_be_focused()
        expect(message).to_be_visible()
        expect(thread.locator(".lf-thread-news")).to_have_count(0)
        return
    if new_input:
        rendered(page)
        hold_visible_thread_presentation(page, root)
    page.keyboard.press("Shift+t")
    expect(summary).to_be_focused()
    if walk == "onto":
        rendered(page)
        expect(thread.get_by_role("button", name=notice, exact=True)).to_be_visible()
        expect(message).to_have_count(0)
        return
    expect(message).to_be_visible()
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    if new_input:
        page.wait_for_function("window.visibleThreadPresentationHeld === true")
        reaction = thread.get_by_role("button", name="Add reaction", exact=True).first
        if new_input == "Tab":
            page.keyboard.press("Tab")
            expect(reaction).to_be_focused()
        elif new_input == "widget":
            choice = message.locator("#held-choice")
            first = choice.locator("#held-first").get_by_role("checkbox")
            second = choice.locator("#held-second").get_by_role("checkbox")
            expect(first).to_have_attribute("aria-checked", "true")
            expect(second).to_have_attribute("aria-checked", "false")
            with page.expect_request("**/api/event") as sent:
                second.click()
            assert sent.value.post_data_json["detail"]["value"] == ["held-second"]
            expect(first).to_have_attribute("aria-checked", "false")
            expect(second).to_have_attribute("aria-checked", "true")
        else:
            page.locator(".lf-threads").hover()
            page.mouse.wheel(0, 180)
            scroll_settled(page, ".lf-threads")
        control = thread.locator("leaf-text")
        before = control.evaluate("node => node.getBoundingClientRect().top")
        scroll = page.locator(".lf-threads").evaluate("node => node.scrollTop")
        page.evaluate("releaseVisibleThreadPresentation()")
        rendered(page)
        one_frame(page)
        assert control.evaluate("node => node.getBoundingClientRect().top") == (
            pytest.approx(before, abs=1)
        )
        assert page.locator(".lf-threads").evaluate("node => node.scrollTop") == (
            pytest.approx(scroll, abs=1)
        )
        if new_input == "Tab":
            expect(reaction).to_be_focused()
            page.keyboard.press("Shift+Tab")
            expect(thread.locator(".lf-thread-summary")).to_be_focused()
            page.keyboard.press("Tab")
            expect(reaction).to_be_focused()
        elif new_input == "widget":
            round_trip(page)
            expect(first).to_have_attribute("aria-checked", "false")
            expect(second).to_have_attribute("aria-checked", "true")
            assert any(
                event["kind"] == "action"
                and event.get("widget") == "held-choice"
                and event["detail"]["value"] == ["held-second"]
                for event in events_model.read_events(serve.page_dir)
            )
        return
    # The latest reply clears the sticky heading and reply row, not just the list box.
    one_frame(page)
    landing = message.evaluate(IN_LANDING_BAND)
    assert landing["inside"], landing


def test_a_dialog_handing_the_user_back_to_a_thread_is_no_arrival(browser, serve):
    """A layer that closes hands the user back to where they stood. The command
    reference opened from a thread with an unfinished draft, and closed with Escape, returns
    them to the thread's title, which they never left, so the reply stays held behind
    its notice."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    summary = thread.locator(".lf-thread-summary")
    if thread.get_attribute("open") is None:
        summary.click()
    write(thread.locator("leaf-text"), "An unfinished reply.")
    summary.focus()
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "parent": root,
            "text": "This answer arrived while the thread stood open.",
        },
    )
    told(page)
    notice = thread.get_by_role("button", name="1 new reply", exact=True)
    expect(notice).to_be_visible()
    # The first press opens the shortcut bar, the second the command reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator("dialog:modal")
    expect(reference).to_be_visible()
    page.keyboard.press("Escape")
    expect(reference).to_have_count(0)
    expect(summary).to_be_focused()
    rendered(page)
    expect(notice).to_be_visible()
    expect(thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(0)


def test_a_delayed_accordion_reveal_yields_to_the_users_new_thread(browser, serve):
    """A filtered Ask arrival cannot open its old target over a later row selection."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    target = question.locator(
        "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' lf-thread ')][1]"
    )
    target_id = target.get_attribute("data-id")
    page.get_by_role("searchbox", name="Find in threads").fill("stay blocked")
    expect(target).to_have_attribute("hidden", "")
    hold_visible_thread_presentation(page, target_id)
    page.locator(".lf-threads").focus()
    # The thread the list shows asks the user a question too, so focus on the list is
    # standing on that item of their queue; the hidden Ask stands before it on the page.
    page.keyboard.press("Shift+m")
    page.wait_for_function("window.visibleThreadPresentationHeld === true")
    later = page.locator(".lf-thread:not([hidden])").first
    later_id = later.get_attribute("data-id")
    assert later_id != target_id
    later = page.locator(f'.lf-thread[data-id="{later_id}"]')
    later.locator(".lf-thread-summary").click()
    expect(later).to_have_attribute("open", "")
    page.evaluate("releaseVisibleThreadPresentation()")
    rendered(page)
    expect(later.locator(".lf-thread-summary")).to_be_focused()
    expect(later).to_have_attribute("open", "")
    expect(target).not_to_have_attribute("open", "")


def test_an_agent_turn_arriving_while_the_user_writes_keeps_their_box_in_view(
    browser, serve
):
    """An arriving turn preserves the visible writing box, draft and Send control."""
    # The short window, where the arriving turn has the least room.
    size = (800, 520)
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 4, long_index=2)[2]
    page = open_page(browser, url)
    open_threads_list(page, *size)
    card = reply_by_keyboard(page, root)
    draft = "Half a thought I am still typing"
    page.keyboard.type(draft)
    rendered(page)
    editor = card.locator("leaf-text")
    before = editor.bounding_box()
    send = card.locator(".lf-thread-send")
    assert send.evaluate(IN_LANDING_BAND)["inside"], "Send starts outside the band"
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
    expect(card.locator(".lf-msg")).to_have_count(13)
    rendered(page)
    scroll_settled(page, ".lf-threads")
    expect(editor).to_be_focused()
    assert editor.evaluate("box => box.value") == draft
    assert editor.bounding_box() == before
    held = send.evaluate(IN_LANDING_BAND)
    assert held["inside"], f"the arrival pushed Send out of the list's band: {held}"
    expect(card.locator(f'.lf-msg[data-mid="{arrived["id"]}"]')).to_contain_text(
        "An agent answer arrives."
    )


def test_reaching_news_a_card_holds_keeps_the_view(browser, serve):
    """A card news takes out of the view stays where it stood (thread-list-view.js,
    `keeping`), and reaching that news, as Next unread does, lands on it there. Only a
    card drawn for the user's own words on their way makes an arrival choose another
    view."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    asked = panel_comment(d, "Is forty enough?", {"section": "how-cap"})
    other = panel_comment(d, "Where does it live?", {"section": "how-store"})
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{asked}"]')
    beside = page.locator(f'.lf-thread[data-id="{other}"]')
    card.locator(":scope > .lf-thread-summary").click()
    answer = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": asked,
            "text": "Forty is enough.",
        },
    )
    append_carried_log_record(
        d, {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": asked}
    )
    told(page)
    rendered(page)
    expect(card).to_be_visible()
    page.locator(".lf-first-unread").click()
    expect(card.locator(f'.lf-msg[data-mid="{answer["id"]}"]')).to_be_focused()
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(beside).to_be_visible()


@pytest.mark.watch_shifts
def test_appended_replies_keep_the_panel_reading_when_the_open_title_is_clipped(
    browser, serve
):
    """The open transcript holds the reading while replies are appended to it.

    A card-level anchor chosen only from visible titles instead scrolls old messages
    away to hold the next title. Agent and other-tab user appends share the same rule.
    """
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "\n\n".join(["Reading the existing conversation."] * 5)
    )
    for i in range(18):
        panel_comment(serve.page_dir, f"Later conversation {i}.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    focus_panel_thread(thread)
    listing = page.locator(".lf-threads")
    listing.hover()
    page.mouse.wheel(0, 90)
    scroll_settled(page)
    page.mouse.move(100, 100)
    reference = thread.locator(".lf-msg").first
    rendered(page)
    band = listing.bounding_box()
    original = thread.locator(".lf-msg").first.bounding_box()
    assert thread.bounding_box()["y"] < band["y"]
    assert original["y"] + original["height"] > band["y"]
    editor = thread.locator("leaf-text").bounding_box()
    assert editor["y"] + editor["height"] < band["y"] + band["height"] - 1
    before = reference.bounding_box()
    for append in (append_agent_reply, append_user_reply):
        reply = append(
            serve.page_dir, root, "New material here.\n\nAnother paragraph follows."
        )
        told(page)
        expect(thread.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
        expect(thread.locator(".lf-thread-news")).to_have_count(0)
        rendered(page)
        assert reference.bounding_box() == before
