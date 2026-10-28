"""Resolving and reopening threads: the immediate response to the press, refusals, where
focus goes, the fold that gives a resolved thread's room back, and resolutions made
elsewhere."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
    PANEL_PAGE,
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_PAGE,
    SEATED_OBLIGATION_WIDGETS,
    answered_comment,
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    expect_open_threads,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    sending,
    told,
    undo,
    write,
)

from browser.threads import (
    PANEL_NEWS,
    PANEL_REPLY,
    open_panel_thread,
)
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_inline_settlement_retains_focus_when_its_controls_are_replaced(browser, serve):
    """A page seat keeps focus through settlement when its controls are replaced."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Inline settlement",
                '<h1>Review the plan</h1><lf-verdict id="proposal" asks>'
                "Should these jobs share a visit?</lf-verdict>"
                '<label>Another thought <input id="later"></label>',
            ),
            layer_registry=SEATED_OBLIGATION_LAYER,
            layer_widgets=SEATED_OBLIGATION_WIDGETS,
        ),
    )
    first = page.locator("#proposal > .lf-thread-seat > .lf-say")
    write(first.locator("leaf-text"), "Please combine the jobs.")
    with sending(page, "the root comment"):
        first.get_by_role("button", name="Send", exact=True).click()
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(f'.lf-page-thread[data-thread="{root["id"]}"]')
    destination = thread.locator("leaf-text")
    expect(destination).to_have_count(1)
    thread.get_by_role("button", name="Resolve thread", exact=True).focus()
    page.keyboard.press("Enter")
    round_trip(page)
    # The resolved thread folds into the seat's Resolved disclosure, and the user with
    # it onto the disclosure's summary, which opens to its Reopen.
    summary = page.locator("#proposal .lf-resolved-summary")
    expect(summary).to_be_focused()
    page.keyboard.press("Enter")
    expect(thread.get_by_role("button", name="Reopen")).to_be_visible()
    thread.get_by_role("button", name="Reopen").click()
    round_trip(page)
    expect(destination).to_be_focused()

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    for action, optimistic in (
        ("Resolve thread", "Reopen"),
        ("Reopen", "Resolve thread"),
    ):
        if action == "Reopen":
            summary.click()
        with page.expect_request("**/api/event"):
            thread.get_by_role("button", name=action, exact=True).click()
        expect(
            thread.get_by_role(
                "button", name=optimistic, exact=True, include_hidden=True
            )
        ).to_be_attached()
        page.locator("#later").fill("Keep my later focus here.")
        held.pop().continue_()
        round_trip(page)
        expect(page.locator("#later")).to_be_focused()
    page.unroute("**/api/event")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("existing_neighbors", [False, True])
def test_inline_retirement_is_resolved_before_its_pixels_finish(
    engine, request, serve, existing_neighbors
):
    """The outgoing room is inert; open, undo and refusal interrupt it immediately.
    Firefox, without intrinsic-size interpolation, starts from the same room."""
    url = serve(
        SEATED_OBLIGATION_PAGE.replace(
            "</main>", '<label>Later thought <input id="later"></label></main>'
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )

    def comment(text):
        return append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": "jobs"},
                "text": text,
            },
        )["id"]

    if existing_neighbors:
        comment("Check the earlier job's timing.")
    root = comment("These jobs can share one visit.")
    if existing_neighbors:
        comment("Check the later job's timing.")
        settled = comment("The access arrangements are settled.")
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": settled}
        )
    page = open_page(request.getfixturevalue(engine), url)
    page.emulate_media(reduced_motion="no-preference")
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    summary = page.locator("#jobs .lf-resolved-summary")
    # Freeze the actual retirement when it becomes inert, so assertions cover the
    # interval before its natural finish without racing a wall-clock duration.
    thread.evaluate("""node => new MutationObserver(() => {
        if (!node.inert) return;
        const animation = node.getAnimations()[0];
        if (!animation || animation === window.retirement) return;
        window.retirement = animation;
        animation.pause();
        animation.currentTime = 0;
    }).observe(node, {attributeFilter: ['inert']})""")

    def resolve():
        if summary.count() and summary.evaluate("node => node.parentElement.open"):
            summary.press("Enter")
        thread.get_by_role("button", name="Resolve thread", exact=True).focus()
        before = thread.locator("..").bounding_box()["height"]
        page.keyboard.press("Enter")
        expect(thread).to_have_attribute("data-resolved", "true")
        expect(thread).to_have_attribute("inert", "")
        expect(summary).to_be_focused()
        expect(summary).to_contain_text(f"Resolved · {2 if existing_neighbors else 1}")
        assert thread.evaluate("node => node.parentElement.matches('.lf-thread-seat')")
        assert page.evaluate("window.retirement.effect.getTiming().duration") == 220
        assert abs(thread.locator("..").bounding_box()["height"] - before) < 1

    resolve()
    round_trip(page)
    expect_open_threads(page, 2 if existing_neighbors else 0)
    # The summary can reveal the real card while its old room is still departing.
    summary.press("Enter")
    expect(thread).not_to_have_attribute("inert", "")
    expect(thread.get_by_role("button", name="Reopen", exact=True)).to_be_visible()
    thread.get_by_role("button", name="Reopen", exact=True).click()
    round_trip(page)
    resolve()
    round_trip(page)
    undo(page)
    round_trip(page)
    expect(thread).not_to_have_attribute("inert", "")
    expect(
        thread.get_by_role("button", name="Resolve thread", exact=True)
    ).to_be_visible()
    assert page.evaluate("window.retirement.playState") == "idle"
    assert thread.evaluate("node => node.contains(document.activeElement)")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        resolve()
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    expect(thread).not_to_have_attribute("inert", "")
    # The refusal returns the user to the thread in its seat, not to another surface.
    page.wait_for_function(
        "node => node.contains(document.activeElement)", arg=thread.element_handle()
    )
    expect(
        thread.get_by_role("button", name="Resolve thread", exact=True)
    ).to_be_enabled()
    assert page.evaluate("window.retirement.playState") == "idle"
    page.unroute("**/api/event")

    resolve()
    round_trip(page)
    # Finishing the pixels must not reclaim focus from a subsequent user move.
    page.locator("#later").fill("Keep this thought here.")
    page.evaluate("window.retirement.currentTime = 219")
    before_finish = page.locator("#later").bounding_box()["y"]
    page.evaluate("window.retirement.play()")
    expect(thread).to_be_hidden()
    assert abs(page.locator("#later").bounding_box()["y"] - before_finish) < 1
    expect(thread).not_to_have_attribute("inert", "")
    expect(page.locator("#later")).to_be_focused()


def test_resolve_acknowledges_the_press_and_recovers_a_refusal(held_events, serve):
    """A thread's card resolves immediately and restores a refused request."""
    browser, held = held_events
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    root = events_model.read_events(serve.page_dir)[0]["id"]
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    thread = page.locator(".lf-margin-thread")
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_visible()
    resolve.scroll_into_view_if_needed()
    with page.expect_request("**/api/event"):
        resolve.click()
    expect_open_threads(page, 0)
    expect(thread.get_by_role("button", name="Resolve thread")).to_have_count(0)
    expect(page.locator("#bracket")).to_be_focused()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    held.pop().fulfill(
        json={"ok": False, "final": True, "error": "Please retry."},
    )
    expect_open_threads(page, 1)
    # The margin card the resolve closed opens again, with the user back in it.
    thread = page.locator(".lf-margin-thread")
    expect(thread.locator(".lf-page-thread")).to_be_focused()
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_enabled()
    expect(resolve).not_to_have_attribute("aria-keyshortcuts", re.compile(r".*x.*"))
    resolve.focus()
    with page.expect_request("**/api/event"):
        page.keyboard.press("Enter")
    expect_open_threads(page, 0)
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == [root]
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    expect(page.locator("#bracket")).to_be_focused()


def test_z_puts_the_user_back_in_the_thread_they_resolved(browser, serve):
    """Resolving takes the thread off the user's screen: the margin card closes. The log's state keeps no memory of where the thread was
    shown, so taking the resolve back reopens it where nobody is looking unless the
    withdrawal itself returns the user to it, by the route a refusal takes."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Check whether these jobs can share one visit.",
        "anchor": {"section": "bracket"},
    }
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.keyboard.press("Shift+t")
    landed = page.locator(".lf-margin-thread .lf-page-thread")
    expect(landed).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    round_trip(page)
    expect_open_threads(page, 0)
    expect(landed).not_to_be_focused()

    undo(page)
    round_trip(page)
    expect_open_threads(page, 1)
    expect(landed).to_be_focused()
    expect(landed).to_be_in_viewport()


def test_z_leaves_the_user_in_a_seated_thread_they_resolved(browser, serve):
    """A thread seated on the page folds where it stands when resolved, so the user
    never left it, and taking the resolve back moves them nowhere either: not to
    Threads, and not to a margin card for the same thread."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "These jobs can share one visit.",
        },
    )["id"]
    page = open_page(browser, url)
    resized(page, 1920, 900)
    seated = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    seated.get_by_role("button", name="Resolve thread", exact=True).focus()
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    round_trip(page)
    expect_open_threads(page, 0)

    undo(page)
    round_trip(page)
    expect_open_threads(page, 1)
    assert seated.evaluate("node => node.contains(document.activeElement)")
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()


@pytest.mark.parametrize("gesture", ["resolve", "reopen"])
def test_z_shows_a_settlement_the_user_left_before_taking_it(browser, serve, gesture):
    """A settlement's landing arms `z` to take it back in one press only until the
    user acts. With the panel closed since and a press on the page, the thread is
    out of view like any other gesture's place: the first `z` opens it and takes
    nothing, and the second takes the gesture back there."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Settle this one, then think better of it.")
    if gesture == "reopen":
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
    page = open_page(browser, url)
    open_panel_thread(page, root).focus()
    with sending(page, f"the {gesture}"):
        page.keyboard.press("r" if gesture == "resolve" else "Enter")
    round_trip(page)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.locator("h1").first.click()

    page.keyboard.press("z")
    expect(page.locator(PANEL_THREAD)).to_have_attribute("data-thread", root)
    expect(page.locator(".lf-live")).to_contain_text("Press again to undo")
    undo(page)
    round_trip(page)
    expect_open_threads(page, 1 if gesture == "resolve" else 0)
    expect(page.locator(PANEL_THREAD)).to_have_attribute("data-thread", root)


def test_resolving_one_of_two_threads_leaves_the_user_in_the_card(browser, serve):
    """Resolving a thread the card outlives keeps focus in the card.

    Only the last thread at an anchor closes its margin card, and only that closure hands
    focus back to the anchor. With a second thread present, the card stays up showing
    it, so the user stays in the card rather than being carried out to the text.
    """
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "anchor": {"section": "bracket"},
    }
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                {**comment, "text": "Check whether these jobs can share one visit."},
                {**comment, "text": "And whether the second visit needs a permit."},
            ],
        ),
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    card = page.locator(".lf-margin-preview")
    resolve = card.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_visible()
    resolve.focus()
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect_open_threads(page, 1)
    expect(card).to_be_visible()
    expect(
        card.get_by_role("button", name="Resolve thread", exact=True)
    ).to_be_visible()
    focus = page.evaluate(
        """() => {
          const active = document.activeElement;
          return {
            inCard: document.getElementById("lf-margin-preview").contains(active),
            on: active?.outerHTML.slice(0, 80),
          };
        }"""
    )
    assert focus["inCard"], (
        f"resolving a thread the card outlives left focus on {focus}"
    )


def test_a_card_repaint_keeps_the_user_on_the_control_they_reached(browser, serve):
    """A repaint of an open card leaves the user's press where they aimed it.

    An open margin card repaints for reasons the user never asked for — a relative
    timestamp ageing, a receipt phase landing, a margin contribution changing — and each
    one re-runs the whole thread render. Nothing in that render is a reason to take the
    user off the control they have reached, so the control they were about to press
    has to still be the one the next key reaches.

    `lf-actions` is the margin's own repaint door, and its render runs inside this call,
    so the state the press reads is stated rather than waited out.
    """
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    root = events_model.read_events(serve.page_dir)[0]["id"]
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const insertBefore = Node.prototype.insertBefore;
          Node.prototype.insertBefore = function(node, before) {
            if (
              this.matches?.('.lf-margin-preview-list') &&
              node.matches?.('.lf-margin-thread')
            ) {
                  window.__lfDetachedThread = Boolean(
                    node.querySelector('.lf-page-thread')
                  );
            }
            return insertBefore.call(this, node, before);
          };
        }"""
    )
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    assert page.evaluate("() => window.__lfDetachedThread"), (
        "the detached margin card reached display before its thread rendered"
    )
    resolve = page.locator(".lf-margin-thread").get_by_role(
        "button", name="Resolve thread", exact=True
    )
    expect(resolve).to_be_visible()
    resolve.focus()
    expect(resolve).to_be_focused()
    page.evaluate("() => document.dispatchEvent(new Event('lf-actions'))")
    expect(resolve).to_be_focused()
    with sending(page, "the resolve the repaint could have unseated"):
        page.keyboard.press("Enter")
    round_trip(page)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == [root]


def test_a_settlement_in_flight_leaves_its_opposite_live(held_events, serve):
    """While a Resolve travels, the Reopen it leaves is live at once: it wears no busy
    or unavailable face, and a press sends the unresolve after the resolve, as the
    ledger orders them, rather than being swallowed."""
    browser, held = held_events
    url = serve(SEATED_OBLIGATION_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Resolve this and change my mind before the page answers.",
        },
    )["id"]
    page = open_page(browser, url)
    resized(page, 1920, 900)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')

    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Resolve thread", exact=True).click()
    holding(page, held, 1, "the resolve")
    page.locator("#jobs .lf-resolved-summary").click()
    reopen = inline.get_by_role("button", name="Reopen", exact=True)
    expect(reopen).to_be_enabled()
    expect(reopen).not_to_have_attribute("aria-busy", "true")
    reopen.click()
    resolve = inline.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_enabled()
    expect(resolve).not_to_have_attribute("aria-busy", "true")

    with page.expect_request("**/api/event"):
        held.pop().continue_()
    holding(page, held, 1, "the unresolve sent after the resolve")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("parent") == root
    ] == ["resolve", "unresolve"]
    expect(resolve).to_be_visible()


def test_taking_back_a_resolve_is_the_users_own_gesture(browser, serve):
    """`z` after the user's own Resolve reopens the thread at once, as the Resolve
    closed it: an undo stands in the thread of the gesture it takes back, so it is no
    news to hold behind a notice."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep the discussion here.")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "revision": 1,
            "parent": root,
            "text": "An answer.",
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, root)
    with sending(page, "the resolve"):
        page.locator(".lf-fp-settle").click()
    expect_open_threads(page, 0)
    undo(page)
    told(page)
    expect_open_threads(page, 1)
    expect(page.locator(PANEL_NEWS)).to_be_hidden()


def test_a_resolved_thread_can_be_reopened(browser, serve):
    """Reopening is a logged transition: the thread returns to the open list with
    its reply and resolve controls, and the caret in its reply, so what the user types
    next is their reply."""
    page = open_page(browser, serve(LONG_PAGE, comments=18))
    comment = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    open_panel_thread(page, comment)
    with sending(page, "the resolve"):
        page.locator(".lf-fp-settle").click()
    expect_open_threads(page, 17)
    view = open_panel_thread(page, comment)
    settle = page.locator(".lf-fp-settle")
    expect(settle).to_have_accessible_name("Reopen")
    with sending(page, "the reopen"):
        settle.click()
    expect(view).to_be_visible()
    expect(settle).to_have_accessible_name("Resolve thread")
    reply = page.locator(PANEL_REPLY)
    expect(reply).to_be_focused()
    page.keyboard.type("Back to this.")
    expect(reply).to_have_js_property("value", "Back to this.")
    expect_open_threads(page, 18)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"


def test_a_late_reply_reopens_its_resolved_thread(browser, serve):
    """New spoken content returns to Open Threads, including after a reload."""
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    page = open_page(browser, url)
    expect_open_threads(page, 0)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": root["id"],
            "responds": root["id"],
            "text": "This arrived after resolution.",
        },
    )
    told(page)
    expect_open_threads(page, 1)
    view = open_panel_thread(page, root["id"])
    expect(view.locator(".lf-msg.agent")).to_be_visible()
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Resolve thread")
    page.reload()
    told(page)
    expect_open_threads(page, 1)


ATTACHED_THREAD_PAGE = leaf_page(
    "an element and its thread",
    """<h1>Cache review</h1>
<p id="passage" tabindex="0">The budget note covers latency budgets for the cache.</p>
<lf-ask id="cache-ask">
  <h2>Which cache should we keep?</h2>
  <lf-options id="cache" choose>
    <lf-option id="cache-disk">Keep the disk cache</lf-option>
    <lf-option id="cache-memory">Keep the memory cache</lf-option>
  </lf-options>
</lf-ask>""",
)


@pytest.mark.parametrize("arrival", ["walk", "focus"])
def test_r_settles_the_thread_shown_for_the_element_the_user_stands_on(
    browser, serve, arrival
):
    """An element and the thread its card shows are one place (glossary, Current
    target), so `r` on the element settles that thread as it does from the card: on
    the obligation `m` lands on, or on any element the keyboard stands on. The card
    closes and the user stays on the element. Leaf's panel stands at no place, so `r`
    there leaves the card's thread alone though the card stays up."""
    section = "cache-ask" if arrival == "walk" else "passage"
    url = serve(ATTACHED_THREAD_PAGE)
    root = answered_comment(
        serve.page_dir, "The disk cache costs more.", {"section": section}
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    element = page.locator(f"#{section}")
    card = page.locator(".lf-margin-preview")

    def arrive():
        if arrival == "walk":
            page.keyboard.press("m")
        else:
            page.keyboard.press("Shift")
            element.focus()
        expect(element).to_be_focused()
        expect(card.locator(f'.lf-page-thread[data-thread="{root}"]')).to_be_visible()

    arrive()
    page.locator(".lf-fp-on-user").focus()
    page.keyboard.press("r")
    rendered(page)
    expect(card).to_be_visible()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] != "resolve"
    arrive()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    round_trip(page)
    expect_open_threads(page, 0)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(card).to_be_hidden()
    expect(element).to_be_focused()
