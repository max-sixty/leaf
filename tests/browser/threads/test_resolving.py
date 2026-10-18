"""Resolving and reopening threads: the immediate response to the press, refusals, where
focus goes, the fold that gives a resolved thread's room back, and resolutions made
elsewhere."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import thread as thread_model
from leaf.findings import Finding
from leaf.render_checks import one_frame, rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    FRAME_BY_FRAME,
    HOLD_MOTION,
    ITEM_PAGE,
    LIST_STATE,
    PANEL_PAGE,
    SEATED_ITEM_LAYER,
    SEATED_ITEM_PAGE,
    SEATED_ITEM_WIDGETS,
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    CutOff,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    primed,
    resized,
    round_trip,
    said,
    scroll_settled,
    sending,
    take_browser_errors,
    told,
    undo,
    write,
)

from browser.threads import (
    IN_LANDING_BAND,
    focus_panel_thread,
    hold_visible_thread_presentation,
    open_threads_list,
    seed_panel_threads,
)

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
            layer_registry=SEATED_ITEM_LAYER,
            layer_widgets=SEATED_ITEM_WIDGETS,
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
        ).to_have_attribute("aria-busy", "true")
        page.locator("#later").fill("Keep my later focus here.")
        held.pop().continue_()
        round_trip(page)
        expect(page.locator("#later")).to_be_focused()
    page.unroute("**/api/event")


@pytest.mark.parametrize("view", ["inline", "panel"])
def test_resolve_acknowledges_the_press_and_recovers_a_refusal(
    held_events, serve, view
):
    """Both thread views resolve immediately and restore a refused request."""
    browser, held = held_events
    page = open_page(
        browser,
        serve(
            ITEM_PAGE,
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
    if view == "inline":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        thread = page.locator(".lf-margin-thread")
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        thread = page.locator(f'.lf-thread[data-id="{root}"]')
        thread.locator(".lf-thread-summary").click()
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    expect(resolve).to_be_visible()
    resolve.scroll_into_view_if_needed()
    with page.expect_request("**/api/event"):
        resolve.click()
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    if view == "inline":
        expect(thread.get_by_role("button", name="Resolve thread")).to_have_count(0)
        expect(page.locator("#bracket")).to_be_focused()
    else:
        expect(page.locator(".lf-threads")).to_contain_text("No open threads.")
        expect(page.locator(".lf-threads")).to_be_focused()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    held.pop().fulfill(
        json={"ok": False, "final": True, "error": "Please retry."},
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    if view == "inline":
        # The margin card the resolve closed opens again, with the user back in it.
        thread = page.locator(".lf-margin-thread")
        expect(thread.locator(".lf-page-thread")).to_be_focused()
        resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    else:
        thread = page.locator(f'.lf-thread[data-id="{root}"]')
        resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
        expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(resolve).to_be_enabled()
    expect(resolve).not_to_have_attribute("aria-busy", "true")
    # Its command is live again, so the button says so to the keyboard as well.
    expect(resolve).not_to_have_attribute("aria-disabled", "true")
    expect(resolve).not_to_have_attribute("aria-keyshortcuts", re.compile(r".*x.*"))
    resolve.focus()
    with page.expect_request("**/api/event"):
        page.keyboard.press("Enter")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")
    if view == "panel":
        write(page_comment(page), "My next thought can keep its focus.")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == [root]
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')).to_be_hidden()
    if view == "inline":
        expect(page.locator(".lf-thread-panel")).not_to_have_class(
            re.compile(r"\bopen\b")
        )
        expect(page.locator("#bracket")).to_be_focused()
    else:
        expect(page.locator(".lf-general leaf-text")).to_be_focused()


@pytest.mark.parametrize("view", ["inline", "panel"])
def test_z_puts_the_user_back_in_the_thread_they_resolved(browser, serve, view):
    """Resolving takes the thread off the user's screen: the margin card closes, and
    Threads hands focus on. The log's state keeps no memory of where the thread was
    shown, so taking the resolve back reopens it where nobody is looking unless the
    withdrawal itself returns the user to it, by the route a refusal takes."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Check whether these jobs can share one visit.",
        "anchor": {"section": "bracket"},
    }
    page = open_page(browser, serve(ITEM_PAGE, events=[comment]))
    root = events_model.read_events(serve.page_dir)[0]["id"]
    resized(page, 1440, 900)
    if view == "inline":
        page.keyboard.press("Shift+t")
        card = page.locator(".lf-margin-thread .lf-page-thread")
        landed = card
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        card = page.locator(f'.lf-thread[data-id="{root}"]')
        focus_panel_thread(card)
        landed = card.locator(":scope > .lf-thread-summary")
    expect(landed).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    round_trip(page)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")
    expect(landed).not_to_be_focused()

    undo(page)
    round_trip(page)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    expect(landed).to_be_focused()
    expect(landed).to_be_in_viewport()


def test_z_leaves_the_user_in_a_seated_thread_they_resolved(browser, serve):
    """A thread seated on the page folds where it stands when resolved, so the user
    never left it, and taking the resolve back moves them nowhere either: not to
    Threads, and not to a margin card for the same thread."""
    url = serve(SEATED_ITEM_PAGE)
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
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")

    undo(page)
    round_trip(page)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    assert seated.evaluate("node => node.contains(document.activeElement)")
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()


def test_z_takes_a_reopen_back_to_the_resolved_list_it_came_from(browser, serve):
    """Reopening from the Resolved filter carries the user into the open thread; taking
    the reopen back resolves it again and returns them to the filter and thread they
    reopened it from, as a refusal of the reopen would."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Reopen this one, then think better of it.")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    resolved_filter = page.locator('[data-filter-value="resolved"]')
    resolved_filter.click()
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    focus_panel_thread(card)
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    round_trip(page)
    expect(card.locator(":scope > .lf-thread-reply leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")

    undo(page)
    round_trip(page)
    expect(resolved_filter).to_have_attribute("aria-pressed", "true")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()

    # A later input wins over the whole return, the filter as well as the focus.
    with sending(page, "the second reopen"):
        page.keyboard.press("r")
    round_trip(page)
    page.keyboard.press("Escape")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("undo")
    page.keyboard.press("z")
    holding(page, held, 1, "the undo")
    page.locator("#t").click()
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(resolved_filter).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")


@pytest.mark.parametrize("gesture", ["resolve", "reopen"])
def test_z_opens_no_surface_the_user_closed_after_settling(browser, serve, gesture):
    """Putting the user back is the settling surface's to do while it stands. With
    Threads closed since, taking the gesture back changes the thread and nothing else."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Settle this one, then think better of it.")
    if gesture == "reopen":
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
    page = open_page(browser, url)
    toggle = page.locator(".lf-threads-toggle")
    toggle.click()
    panel_settled(page)
    if gesture == "reopen":
        page.locator(".lf-thread-filter-toggle").click()
        page.locator('[data-filter-value="resolved"]').click()
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{root}"]'))
    with sending(page, f"the {gesture}"):
        page.keyboard.press("r")
    round_trip(page)
    toggle.focus()
    page.keyboard.press("Enter")
    panel_settled(page, open=False)

    undo(page)
    round_trip(page)
    expect(toggle).to_have_text(f"Threads: {1 if gesture == 'resolve' else 0}")
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(toggle).to_be_focused()


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
            ITEM_PAGE,
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
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
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
            ITEM_PAGE,
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


def test_panel_settlement_moves_focus_with_optimistic_state_and_restores_a_refusal(
    held_events, serve
):
    """Panel focus follows the same optimistic Resolve/Reopen state as its cards.

    A refusal restores the thread the user was operating, and the prior lifecycle
    view while they have not acted since. A later accepted attempt keeps the
    optimistic destination rather than moving focus again when the server answers.
    """
    browser, held = held_events
    url = serve(LONG_PAGE)
    first = panel_comment(serve.page_dir, "Keep this first thread in view.")
    second = panel_comment(serve.page_dir, "The next thread receives focus.")
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    first_card = page.locator(f'.lf-thread[data-id="{first}"]')
    second_card = page.locator(f'.lf-thread[data-id="{second}"]')

    focus_panel_thread(first_card)
    page.keyboard.press("r")
    holding(page, held, 1, "the refused resolve")
    expect(second_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    expect(first_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("c")
    expect(first_card.locator(":scope > .lf-thread-reply leaf-text")).to_be_focused()
    page.keyboard.press("Escape")

    page.keyboard.press("r")
    holding(page, held, 1, "the accepted resolve")
    expect(second_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("c")
    second_reply = second_card.locator(":scope > .lf-thread-reply leaf-text")
    expect(second_reply).to_be_focused()
    held.pop().continue_()
    round_trip(page)
    expect(second_reply).to_be_focused()

    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    page.get_by_role("searchbox", name="Find in threads").fill("first thread")
    focus_panel_thread(first_card)
    expect(first_card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("r")
    holding(page, held, 1, "the refused reopen")
    pending_reply = first_card.locator(":scope > .lf-thread-reply leaf-text")
    expect(pending_reply).to_be_focused()
    write(pending_reply, "Keep this draft through the refusal.")
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)
    # The user acted since the reopen, so the refusal leaves the view they are working
    # in (#46 on the rewrite survey, the user's decision, 2026-10-07).
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    expect(pending_reply).to_be_focused()
    expect(pending_reply).to_have_js_property(
        "value", "Keep this draft through the refusal."
    )

    expect(first_card).to_be_visible()
    focus_panel_thread(first_card)
    page.keyboard.press("r")
    holding(page, held, 1, "the accepted reopen")
    reply = first_card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Keep this draft through the refusal.")
    held.pop().continue_()
    round_trip(page)
    expect(reply).to_be_focused()


def test_a_refused_reopen_preserves_a_filter_typed_during_its_reveal(
    held_events, serve
):
    """A later user search is not the transition state that refusal may restore."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Keep the later search in view.")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("later search")
    card = page.locator(f'.lf-thread[data-id="{root}"]:not([hidden])')
    expect(card).to_be_visible()
    card.locator(".lf-thread-summary").click()
    rendered(page)
    hold_visible_thread_presentation(page, root)

    card.get_by_role("button", name=re.compile(r"\bReopen(?: thread)?$")).click()
    holding(page, held, 1, "the refused reopen with a held reveal")
    page.wait_for_function("window.visibleThreadPresentationHeld === true")
    find.fill("newer user search")
    expect(find).to_be_focused()
    page.evaluate("releaseVisibleThreadPresentation()")
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    round_trip(page)

    expect(find).to_have_value("newer user search")
    expect(find).to_be_focused()
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )


def test_a_refused_reopen_preserves_a_filter_typed_during_restoration(
    held_events, serve
):
    """Restoration cannot overwrite user intent that arrives during its own reveal."""
    browser, held = held_events
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Keep the restoration search in view.")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    find = page.get_by_role("searchbox", name="Find in threads")
    find.fill("restoration search")
    card = page.locator(f'.lf-thread[data-id="{root}"]:not([hidden])')
    expect(card).to_be_visible()
    card.locator(".lf-thread-summary").click()
    rendered(page)

    card.get_by_role("button", name=re.compile(r"\bReopen(?: thread)?$")).click()
    holding(page, held, 1, "the refused reopen whose restoration will wait")
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(find).to_have_value("")

    hold_visible_thread_presentation(page, root)
    held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
    page.wait_for_function("window.visibleThreadPresentationHeld === true")
    find.fill("newer user search")
    expect(find).to_be_focused()
    page.evaluate("releaseVisibleThreadPresentation()")
    round_trip(page)

    expect(find).to_have_value("newer user search")
    expect(find).to_be_focused()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )


def test_settlement_controls_share_one_request_across_page_and_panel(
    held_events, serve
):
    """Mirrored controls share optimistic resolution, delivery, and reopening."""
    browser, held = held_events
    url = serve(SEATED_ITEM_PAGE)
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    panel = page.locator(f'.lf-thread[data-id="{root}"]')
    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Resolve thread", exact=True).click()
    page.locator("#jobs .lf-resolved-summary").click()
    pending = inline.get_by_role("button", name="Reopen", exact=True)
    expect(pending).to_be_disabled()
    expect(pending).to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-threads")).to_contain_text("No open threads.")
    pending.focus()
    page.keyboard.press("Enter")
    assert len(held) == 1
    held.pop().continue_()
    round_trip(page)
    expect(inline.get_by_role("button", name="Reopen")).to_be_visible()
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "resolve"
    ] == ["resolve"]
    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Reopen").click()
    for thread in (inline, panel):
        optimistic = thread.get_by_role(
            "button", name="Resolve thread", exact=True, include_hidden=True
        )
        expect(optimistic).to_be_disabled()
        expect(optimistic).to_have_attribute("aria-busy", "true")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    for thread in (inline, panel):
        expect(
            thread.get_by_role(
                "button", name="Resolve thread", exact=True, include_hidden=True
            )
        ).to_be_enabled()
    expect(inline.locator("leaf-text")).to_be_visible()
    expect(inline.locator("leaf-text")).to_be_focused()


def test_a_poll_accounted_settlement_repaints_before_its_post_response(
    held_events, serve
):
    """A poll may prove acceptance while the original POST response remains held.

    The poll paints and accounts the receipt first. Delivery then retires the already
    accounted ledger entry, which must invalidate the unchanged thread reading;
    otherwise every mirrored settlement control stays busy until an unrelated clock
    tick or state read.
    """
    browser, held = held_events
    url = serve(SEATED_ITEM_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Account this resolution from the complete reading.",
        },
    )["id"]
    page = open_page(browser, url)
    resized(page, 1920, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    panel = page.locator(f'.lf-thread[data-id="{root}"]')

    with page.expect_request("**/api/event"):
        inline.get_by_role("button", name="Resolve thread", exact=True).click()
    holding(page, held, 1, "the resolution whose response remains held")
    page.locator("#jobs .lf-resolved-summary").click()
    pending = inline.get_by_role("button", name="Reopen", exact=True)
    expect(pending).to_be_disabled()
    expect(pending).to_have_attribute("aria-busy", "true")

    # Let exactly the news-triggered state read through. Its receipt accounts the
    # gesture while the page's original POST still has no response, and refusing later
    # reads prevents another poll from hiding a missing local invalidation.
    reads = CutOff(lets_through=1).hold(page)
    route = held.pop()
    accepted = route.fetch()
    told(page)
    reads.cut()
    for settled in (
        inline.get_by_role("button", name="Reopen", exact=True),
        panel.get_by_role(
            "button", name=re.compile(r"\bReopen(?: thread)?$"), include_hidden=True
        ),
    ):
        expect(settled).to_be_enabled()
        expect(settled).not_to_have_attribute("aria-busy", "true")

    route.fulfill(response=accepted)
    page.unroute("**/api/event")
    round_trip(page)


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    for value in ("open", "resolved"):
        choice = page.locator(f'[data-filter-value="{value}"]')
        if choice.get_attribute("aria-pressed") == "true":
            choice.click()
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    if thread.get_attribute("open") is None:
        thread.locator(".lf-thread-summary").click()
    thread.get_by_role("button", name="Resolve thread").click()
    expect(thread).to_have_attribute("data-resolved", "true")
    round_trip(page)
    undo(page)
    told(page)
    expect(thread).to_have_attribute("data-resolved", "false")
    expect(thread.locator(".lf-thread-news")).to_have_count(0)


def test_resolving_an_early_thread_keeps_the_rest_in_place(browser, serve):
    """A thread can move, not just appear: resolving the first one hides it from the
    Open state while every surviving node stays put. The Resolved facet updates without
    changing the user's selected state."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    page.evaluate(
        """(id) => { window.__second = document.querySelector(`.lf-thread[data-id="${id}"]`); }""",
        c2,
    )

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-thread-summary').click()
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    # The resolved node took the pressed button with it; focus lands on the thread
    # that now holds its place rather than falling to body.
    expect(
        page.locator(f'.lf-thread[data-id="{c2}"] > .lf-thread-summary')
    ).to_be_focused()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(
        page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"][hidden]')
    ).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] leaf-text')).to_have_count(0)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    # The survivor stays the same node.
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply c"
    )
    assert page.evaluate(
        """(id) => window.__second === document.querySelector(`.lf-thread[data-id="${id}"]`)""",
        c2,
    ), "renumbering rebuilt the surviving thread"

    # A thread leaving mid-list puts every survivor one place forward. Standing still
    # there is the reconcile's own duty, not the browser's: a survivor reinserted at
    # its new place is the same element and passes any identity probe, but reinsertion
    # drops the caret typing in it.
    page.locator(f'.lf-thread[data-id="{c3}"] .lf-thread-summary').click()
    ta3 = page.locator(f'.lf-thread[data-id="{c3}"] leaf-text')
    ta3.click()
    ta3.type("held mid-sentence")
    page.evaluate("() => document.activeElement.setSelectionRange(4, 4)")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": c2}
    )
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (2)")
    expect(ta3).to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.value === 'held mid-sentence'"
        "   && document.activeElement.selectionStart === 4"
    ), "the thread after the one that resolved was reinserted under the typing"


def test_a_failed_reopen_reveal_still_processes_its_durable_answer(held_events, serve):
    """A follow-up presentation fault cannot reject the discarded click handler."""
    browser, held = held_events
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": root},
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    page.locator(".lf-thread:not([hidden]) .lf-thread-summary").click()
    rendered(page)
    page.evaluate(
        """() => {
          const list = document.querySelector('leaf-thread-list');
          const render = list.render.bind(list);
          let failures = 1;
          list.render = () => {
            const row = list.model.rows.find(({kind}) => kind === 'thread');
            if (row?.descriptor.visible && failures-- > 0)
              throw new Error('deliberate reveal failure');
            return render();
          };
        }"""
    )

    page.get_by_role("button", name=re.compile(r"\bReopen(?: thread)?$")).click()
    holding(page, held, 2, "the reopen and its presentation report")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expected = ["leaf: Presentation failed: deliberate reveal failure"]
    assert [said(error) for error in take_browser_errors(page)] == expected

    routes = {route.request.post_data_json["kind"]: route for route in held}
    held.clear()
    routes["error"].continue_()
    route = routes["unresolve"]
    route.fulfill(
        json={
            "ok": False,
            "final": True,
            "attempt": route.request.post_data_json["attempt"],
            "error": "Please retry.",
        }
    )
    round_trip(page)
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(f'.lf-thread[data-id="{root}"]')).to_be_visible()
    expect(
        page.get_by_role(
            "button", name=re.compile(r"\bReopen(?: thread)?$"), include_hidden=True
        )
    ).to_have_count(1)


def test_a_thread_the_agent_closed_names_who_closed_it(browser, serve):
    """Either side can close a thread and the user watches only one of them happen.
    Their own press folds the thread under their hand and leaves the outcome on the
    control they pressed, so its Resolved state needs to say nothing more. An
    agent's resolve arrives on a poll with no gesture behind it, and that thread says
    who closed it beside the title, on the control that reopens it."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]

    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Indexer", "parent": c1},
    )
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    expect(page.locator(f'.lf-thread[data-id="{c1}"] .lf-thread-status')).to_have_text(
        "✓ Resolved by Indexer"
    )

    page.locator('[data-filter-value="open"]').click()
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c2}"]'))
    page.locator(f'.lf-thread[data-id="{c2}"] .lf-resolve').click()
    round_trip(page)
    page.locator('[data-filter-value="resolved"]').click()
    # The settled card is what says the fold is over, so the line's absence is read
    # from a thread that has arrived rather than one still on its way.
    expect(page.locator(f'.lf-thread[data-id="{c2}"]:not([hidden])')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c2}"] .lf-thread-status')).to_have_text(
        "Resolved"
    )


def test_a_resolved_thread_can_be_reopened(browser, serve):
    """Reopening is a logged transition: the thread returns to the open list with
    its reply and resolve controls, and the state facet returns to Open."""
    page = open_page(browser, serve(LONG_PAGE, comments=18))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comment = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{comment}"]'))
    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)
    # The round trip starts the fold; the retained resolved card finishes it.
    expect(page.locator(f'.lf-thread[data-id="{comment}"][hidden]')).to_have_count(1)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    with sending(page, "the reopen"):
        focus_panel_thread(page.locator(f'.lf-thread[data-id="{comment}"]'))
        page.locator(f'.lf-thread[data-id="{comment}"] .lf-reopen').click()

    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{comment}"]')
    expect(reopened).to_be_in_viewport()
    expect(reopened.locator("leaf-text")).to_be_focused()
    expect(reopened.locator("leaf-text")).to_have_count(1)
    expect(reopened.locator(".lf-resolve")).to_have_count(1)
    expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 18")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"


# Agent threads and a disclosure on the page: the thread an operation acts on (open, or
# resolved for a reopen), the open thread a resolve hands the user on to, and the two
# places a user can go while the operation's delivery is held.
COMPLETION_ROOTS = {"open": "c0", "next": "c1", "resolved": "c2", "later": "c3"}


COMPLETION_PAGE = leaf_page(
    "Held thread operations",
    """
<h1 id="t">Held thread operations</h1>
<p id="p-open">An open thread stands on this paragraph.</p>
<p id="p-next">The thread a resolve hands on to stands on this one.</p>
<p id="p-resolved">A resolved thread stands on this one.</p>
<p id="p-later">The user moves on to the thread on this paragraph.</p>
<details id="d-page"><summary>More on the page</summary><p>Opened.</p></details>
""",
)


COMPLETION_EVENTS = (
    *(
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "id": root,
            "text": f"A {name} thread.",
            "anchor": {"section": f"p-{name}"},
        }
        for name, root in COMPLETION_ROOTS.items()
    ),
    {
        "kind": "resolve",
        "author": "user",
        "revision": 1,
        "parent": COMPLETION_ROOTS["resolved"],
    },
)


# Each operation and each destination at least once; a reopen's arrival is the one
# that could open Threads again, so it goes to the page.
@pytest.mark.parametrize(
    ("kind", "destination"),
    [
        ("unresolve", "page"),
        ("resolve", "stay"),
        ("reply", "thread"),
        ("resolve", "page"),
    ],
)
def test_a_thread_completion_keeps_the_users_later_destination(
    browser, serve, kind, destination
):
    """A held thread operation's delivery leaves the user where they went meanwhile:
    where the operation itself left them (`stay`), on the page with Threads closed
    (`page`, which a reopen's arrival must not open again), or typing in another
    thread (`thread`)."""
    held = []

    def hold_operation(route):
        if route.request.post_data_json["kind"] == "read":
            route.continue_()
        else:
            held.append(route)

    page = open_page(
        primed(browser, lambda page: page.route("**/api/event", hold_operation)),
        serve(COMPLETION_PAGE, events=COMPLETION_EVENTS),
    )
    resized(page, 390, 700)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    root = COMPLETION_ROOTS["resolved" if kind == "unresolve" else "open"]
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    if kind == "unresolve":
        page.locator(".lf-thread-filter-toggle").click()
        page.locator('[data-filter-value="resolved"]').click()
    focus_panel_thread(thread)
    if kind == "reply":
        write(thread.locator("leaf-text"), "A reply whose delivery is held.")

    thread.get_by_role(
        "button",
        name={
            "unresolve": re.compile(r"\bReopen thread$"),
            "resolve": "Resolve thread",
            "reply": "Send",
        }[kind],
        exact=True,
    ).click()
    holding(page, held, 1, "the thread operation")

    later_thread = page.locator(f'.lf-thread[data-id="{COMPLETION_ROOTS["later"]}"]')
    later = later_thread.locator("leaf-text")
    changes = page.locator("#d-page summary")
    if destination == "page":
        page.get_by_role("button", name="Close threads", exact=True).click()
        changes.click()
    elif destination == "thread":
        if kind == "unresolve":
            # Reopen has already selected Open while its delivery is held.
            expect(page.locator('[data-filter-value="open"]')).to_have_attribute(
                "aria-pressed", "true"
            )
        focus_panel_thread(later_thread)
        later.click()
        write(later, "The user is working here now.")

    delivered = held.pop(0)
    attempt = delivered.request.post_data_json["attempt"]
    delivered.continue_()
    page.unroute("**/api/event")
    round_trip(page)
    told(page)
    rendered(page)
    assert (
        next(
            event
            for event in events_model.read_events(serve.page_dir)
            if event.get("attempt") == attempt
        )["kind"]
        == kind
    )
    if destination == "page":
        assert not page.get_by_role("dialog").is_visible()
        expect(changes).to_be_focused()
        expect(page.locator("#d-page")).to_have_attribute("open", "")
    elif destination == "thread":
        expect(later).to_be_focused()
        expect(later).to_have_js_property("value", "The user is working here now.")
    elif kind == "unresolve":
        expect(thread.locator("leaf-text")).to_be_focused()
    elif kind == "reply":
        # The send left the user on the thread's title, and its delivery keeps them there.
        expect(thread.locator(".lf-thread-summary")).to_be_focused()
    else:
        # Resolve handed the user on to the next open thread.
        expect(
            page.locator(
                f'.lf-thread[data-id="{COMPLETION_ROOTS["next"]}"] > .lf-thread-summary'
            )
        ).to_be_focused()


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
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    expect(thread).to_be_hidden()
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
    expect(thread).to_be_visible()
    thread.locator(".lf-thread-summary").press("Enter")
    expect(thread.locator(".lf-msg.agent")).to_be_visible()
    expect(
        thread.get_by_role("button", name=re.compile(r"\bReopen(?: thread)?$"))
    ).to_have_count(0)
    page.reload()
    told(page)
    expect(thread).to_be_visible()
    expect(thread).to_have_attribute("data-resolved", "false")


def test_a_resolved_thread_gives_its_room_back_as_motion(browser, serve):
    """Resolving a thread empties its place in the list over a fifth of a second,
    not in the frame of the press.

    The node used to go the moment the log settled it: the ✓ Resolve the user had
    just pressed took itself off the page, and every thread under it arrived
    somewhere else with no path between the two — the same pair of failures the
    suggestion's decided slot was already fixed for, in the panel this time. So the
    thread stays where it stood, states on the pressed control what was done to it,
    and folds; the retained Resolved state gets it when the fold is over.

    What the log says is true from that first frame regardless — Threads counts down
    and Resolved counts up while the pixels catch up — and a thread on its way out is
    out of the t/T walk from the same frame rather than remaining a destination that is
    about to disappear.

    Held at its first frame rather than sampled mid-flight, the way the suggestion's
    own fold is read: mid-flight is a race with the clock that passes on a fast
    machine whatever the code does, where the held frame is the fold's opening state
    for as long as the assertions need it."""
    page = open_page(browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-thread-summary').click()
    first = page.locator(f'.lf-thread[data-id="{c1}"]').bounding_box()
    stood = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    # The room the first thread holds, the gap under it included, which is what its
    # neighbour rises by once the fold has given it back.
    room = stood["y"] - first["y"]
    action = page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().toJSON()"
    )

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    reply = page.locator(f'[data-id="{c1}"] .lf-thread-reply')
    expect(reply).to_be_visible()
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    outcome = page.locator(f'[data-id="{c1}"] .lf-resolve')
    expect(outcome).to_have_attribute("aria-label", "Resolved")
    expect(outcome.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(reply).to_be_hidden()
    resolved = page.locator(f'[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().toJSON()"
    )
    assert (resolved["top"], resolved["right"]) == (
        pytest.approx(action["top"], abs=1),
        pytest.approx(action["right"], abs=1),
    ), "the outcome moved from where the user pressed Resolve"
    held = page.evaluate(LIST_STATE)
    assert held["listed"] == [c1, c2, c3], (
        "the resolved thread gave up its place in the frame it was resolved in, so "
        f"the list stood as {held['listed']} with the fold still to play"
    )
    assert held["walkable"] == [c2, c3], (
        "a thread on its way out is still walkable by t/T, so a "
        f"key can land on room that is about to go: the list offered {held['walkable']}"
    )
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "the room went back without motion carrying it"
    )
    now = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert now["y"] == stood["y"], (
        f"the thread below stood at {stood} and reads {now} in the frame the outcome "
        "was stated, so the fold started from somewhere other than the box the user "
        "was looking at"
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(page.locator(f'[data-id="{c1}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    expect(page.locator(f'.lf-thread[data-id="{c2}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply c"
    )

    # Half way down, the outcome still stands on its metadata row: the fold clips it
    # where it stood rather than carrying it.
    page.evaluate("() => window.__lfHeld.forEach((m) => (m.currentTime = 110))")
    says = page.locator(f'[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().top"
    )
    assert says == pytest.approx(action["top"], abs=1), (
        f"the outcome moved from {action['top']:.0f} to {says:.0f} as the fold ran"
    )

    # And the far end: the thread becomes a retained hidden result, once, and the room it held
    # has gone back to the threads under it.
    page.evaluate("() => window.__lfHeld.forEach((m) => m.finish())")
    expect(page.locator(f'.lf-thread[data-id="{c1}"][hidden]')).to_have_count(1)
    expect(page.locator(f'[data-id="{c1}"]')).to_have_count(1)
    risen = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert stood["y"] - risen["y"] == pytest.approx(room, abs=1), (
        f"the thread below rose {stood['y'] - risen['y']:.1f}px where the resolved "
        f"thread held {room:.1f}px"
    )


def test_a_folding_thread_keeps_the_card_under_the_pointer_put(browser, serve):
    """A remote resolution may fold a card scrolled past, above the one the user aims
    inside. A card any of which shows stays where news leaves it (thread-list-view.js),
    so the folding card stands wholly above the list's window.

    Hold the fold so its midpoint and completion are stable states the test can inspect.
    The target card must keep the same viewport position through both; otherwise the
    animation carries new controls under a stationary pointer for its whole duration."""
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[5], roots[16]
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    setup = page.evaluate(
        "([source, target]) => {"
        " const list = document.querySelector('.lf-threads');"
        ' const a = document.querySelector(`.lf-thread[data-id="${source}"]`)'
        "   .getBoundingClientRect();"
        ' const b = document.querySelector(`.lf-thread[data-id="${target}"]`)'
        "   .getBoundingClientRect();"
        " const view = list.getBoundingClientRect();"
        " return {scrollTop: list.scrollTop, source: a.toJSON(), target: b.toJSON(),"
        "   sourceAbove: a.bottom <= view.top};"
        "}",
        [source, target],
    )
    assert setup["sourceAbove"], "the card to fold shows, so news keeps it in place"
    assert setup["scrollTop"] > setup["source"]["height"], (
        "the list cannot compensate for the fold before reaching its top edge"
    )
    point = [
        setup["target"]["x"] + setup["target"]["width"] / 2,
        setup["target"]["y"] + setup["target"]["height"] / 2,
    ]
    page.mouse.move(*point)
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, target],
    ), "the pointer did not begin over the target card"

    before = page.evaluate("() => window.__lfHeld.length")
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": source},
    )
    told(page)
    expect(page.locator(f'.lf-going[data-id="{source}"]')).to_have_count(1)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1, (
        "the remote resolution did not start a fold"
    )
    assert (
        page.locator(".lf-threads").evaluate(
            "el => getComputedStyle(el).overflowAnchor"
        )
        == "none"
    ), "native anchoring still has a second claim on the held fold"
    started = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert started == pytest.approx(setup["target"]["top"], abs=1)

    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)
    halfway = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert halfway == pytest.approx(setup["target"]["top"], abs=1), (
        f"the fold carried the target card from {setup['target']['top']:.1f}px "
        f"to {halfway:.1f}px under a stationary pointer"
    )

    # The hold owns reflow, not scrolling. A wheel gesture during the held animation
    # must move the user by the distance the browser accepts and stay there on the
    # next animation frame instead of being mistaken for another fold delta.
    threads = page.locator(".lf-threads")
    scroll_before = threads.evaluate("el => el.scrollTop")
    page.mouse.wheel(0, 40)
    one_frame(page)
    scroll_after = threads.evaluate("el => el.scrollTop")
    assert scroll_after > scroll_before, "the fold undid the user's wheel scroll"
    scrolled_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert scrolled_top == pytest.approx(
        halfway - (scroll_after - scroll_before), abs=1
    ), "the scroll hold changed the distance the user deliberately travelled"
    threads.evaluate("(el, top) => { el.scrollTop = top; }", scroll_before)
    one_frame(page)
    restored = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert restored == pytest.approx(setup["target"]["top"], abs=1)

    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(setup["target"]["top"], abs=1), (
        f"removing the folded card moved the target from "
        f"{setup['target']['top']:.1f}px to {finished:.1f}px"
    )
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, target],
    ), "the fold left another card under the stationary pointer"
    assert (
        page.locator(".lf-threads").evaluate(
            "el => getComputedStyle(el).overflowAnchor"
        )
        == "auto"
    ), "the manual hold disabled native anchoring after its mutation ended"


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_a_fold_frame_by_frame_keeps_the_card_below_on_its_pixel(
    engine, request, serve
):
    """A card folding above the reader shrinks a little each frame, and each frame's
    correction lands within the pixel the engine rounds a scroll offset to. The next
    frame corrects from where the last one aimed, so the card the reader looks at
    ends where it began rather than a rounding further per frame."""
    browser = request.getfixturevalue(engine)
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[5], roots[16]
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    one_frame(page)
    start = target_card.evaluate("el => el.getBoundingClientRect().top")
    before = page.evaluate("() => window.__lfHeld.length")
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": source},
    )
    told(page)
    if not page.evaluate('CSS.supports("block-size", "calc-size(auto, size)")'):
        # Engines without intrinsic-size interpolation retire the thread in one
        # paint; there are no frames to step through or hold for inspection.
        expect(page.locator(f'.lf-going[data-id="{source}"]')).to_have_count(0)
        assert target_card.evaluate(
            "el => el.getBoundingClientRect().top"
        ) == pytest.approx(start, abs=1)
        return
    expect(page.locator(f'.lf-going[data-id="{source}"]')).to_have_count(1)
    steps = 30
    for step in range(1, steps):
        page.evaluate(
            "([i, part]) => { const motion = window.__lfHeld[i];"
            " motion.currentTime = motion.effect.getComputedTiming().duration * part; }",
            [before, step / steps],
        )
        one_frame(page)
    tops = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert tops == pytest.approx(start, abs=1)


def test_a_folding_reference_hands_its_hold_to_the_next_card(browser, serve):
    """When the aimed-at card is itself leaving, its successor inherits the hold.

    A folding node remains connected until the end of its animation, so connectedness
    alone cannot identify a usable reference. The next live card must stay put from the
    first shrinking frame through the final reconciliation."""
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[15:17]
    source_card = page.locator(f'.lf-thread[data-id="{source}"]')
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    source_box = source_card.bounding_box()
    target_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    scroll_top = page.locator(".lf-threads").evaluate("el => el.scrollTop")
    assert scroll_top > source_box["height"], (
        "the list cannot compensate for the fold before reaching its top edge"
    )
    point = [
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    ]
    page.mouse.move(*point)
    assert page.evaluate(
        "([x, y, id]) => document.elementFromPoint(x, y)"
        "?.closest('.lf-thread')?.dataset.id === id",
        [*point, source],
    ), "the pointer did not begin over the card that will fold"

    before = page.evaluate("() => window.__lfHeld.length")
    # The user resolves the card through a package's control, which moves no pointer:
    # a card news resolves stays where it stands (thread-list-view.js), and their own
    # settlement folds it.
    page.evaluate(
        "async key => (await window.__lfWidgetApi()).threadActions.resolve(key)",
        source,
    )
    round_trip(page)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1
    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)
    halfway = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert halfway == pytest.approx(target_top, abs=1), (
        f"the disappearing reference moved its successor from {target_top:.1f}px "
        f"to {halfway:.1f}px"
    )

    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(target_top, abs=1)


def test_a_render_arriving_mid_fold_keeps_the_place_the_fold_is_holding(browser, serve):
    """A fold owns the list's place until it ends; a render landing inside it joins.

    The list slides both ways around a folding card: the room closes under the cards
    below it, and the cards above come down into it as the hold gives back the scroll.
    So what is under the pointer stops naming where the user is standing the moment
    the motion starts, and a hold that reads it again mid-fold pins a card above the
    fold while everything past it — the successor the user was aiming at among it —
    goes on moving. The arrival here is another thread's reply, which is one of several:
    the two-second heartbeat repaints the receipts under the same hold, and so does a
    narrowing.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=30), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    source, target = roots[15:17]
    source_card = page.locator(f'.lf-thread[data-id="{source}"]')
    target_card = page.locator(f'.lf-thread[data-id="{target}"]')
    target_card.evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    source_box = source_card.bounding_box()
    target_top = target_card.evaluate("el => el.getBoundingClientRect().top")
    point = [
        source_box["x"] + source_box["width"] / 2,
        source_box["y"] + source_box["height"] / 2,
    ]
    page.mouse.move(*point)

    before = page.evaluate("() => window.__lfHeld.length")
    # The user resolves the card through a package's control, which moves no pointer:
    # a card news resolves stays where it stands (thread-list-view.js), and their own
    # settlement folds it.
    page.evaluate(
        "async key => (await window.__lfWidgetApi()).threadActions.resolve(key)",
        source,
    )
    round_trip(page)
    assert page.evaluate("() => window.__lfHeld.length") == before + 1
    page.evaluate(
        "i => { window.__lfHeld[i].currentTime = "
        "window.__lfHeld[i].effect.getComputedTiming().duration / 2; }",
        before,
    )
    one_frame(page)

    # Far enough down the list that its own card cannot move the target, so what the
    # arrival costs is the hold and nothing else.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": roots[5],
            "text": "Noted, and still looking.",
        },
    )
    told(page)
    one_frame(page)
    joined = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert joined == pytest.approx(target_top, abs=1), (
        f"the arriving render moved the held card from {target_top:.1f}px "
        f"to {joined:.1f}px"
    )
    page.evaluate("i => window.__lfHeld[i].finish()", before)
    expect(page.locator(f'.lf-thread[data-id="{source}"][hidden]')).to_have_count(1)
    rendered(page)
    finished = target_card.evaluate("el => el.getBoundingClientRect().top")
    assert finished == pytest.approx(target_top, abs=1), (
        f"the fold's last frame moved the held card from {target_top:.1f}px "
        f"to {finished:.1f}px"
    )


@pytest.mark.parametrize("finish", ["send", "clear", "filter", "refused"])
def test_an_external_resolution_keeps_a_panel_reply_until_it_is_sent(
    browser, serve, finish
):
    """Settlement changes the thread, not the visible draft or its editing lifetime.

    The resolution from elsewhere waits behind the card's notice, so the card keeps
    its reply box and Resolve; sending the reply is the user's gesture in the thread,
    which shows what it holds."""
    page = open_page(browser, serve(LONG_PAGE, comments=1), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    card = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    focus_panel_thread(card)
    reply = card.locator("leaf-text")
    words = "This draft survives the other actor settling its thread."
    write(reply, words)
    reply.evaluate("ta => ta.setSelectionRange(8, 8)")
    expect(reply).to_be_focused()

    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "parent": root["id"]},
    )
    told(page)
    rendered(page)
    notice = card.get_by_role("button", name="Resolved", exact=True)
    expect(notice).to_be_visible()
    expect(card).to_have_attribute("data-resolved", "false")
    expect(card).not_to_have_attribute("inert", "")
    expect(card).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)
    assert reply.evaluate("ta => [ta.selectionStart, ta.selectionEnd]") == [8, 8]
    assert page.evaluate("() => window.__lfHeld.length") == 0

    if finish == "clear":
        # Clearing the words is no gesture in the thread, so the card still holds the
        # resolution, and stands as it did until the user moves on.
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        rendered(page)
        expect(card).to_be_visible()
        expect(notice).to_be_visible()
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", "")
        return
    if finish == "filter":
        withdrawn_words = Finding(
            "words-left-screen",
            values={
                "words": words,
                "place": reply.evaluate("field => window.lfPlace(field)"),
            },
        )
        find = page.get_by_role("searchbox", name="Find in threads")
        find.click()
        find.fill("No such discussion")
        rendered(page)
        expect(card).to_be_hidden()
        # The real Find press ends this composition before narrowing hides its
        # retained words. That later inactive withdrawal is the fixture's intent.
        page.evaluate("lfWordsJudged()")
        errors = take_browser_errors(page)
        assert errors in ([], [withdrawn_words]), errors
        find.fill("")
        rendered(page)
        expect(reply).to_have_count(0)
        page.locator(".lf-thread-filter-toggle").click()
        page.locator('[data-filter-value="resolved"]').click()
        expect(card).to_be_visible()
        with sending(page, "reopen the deliberately dismissed reply"):
            card.get_by_role(
                "button", name=re.compile(r"\bReopen(?: thread)?$")
            ).click()
        expect(reply).to_have_js_property("value", words)
        return

    page.keyboard.type(" still")
    sent_words = "This dra stillft survives the other actor settling its thread."
    expect(reply).to_have_js_property("value", sent_words)
    if finish == "refused":
        held = []
        page.route("**/api/event", lambda route: held.append(route))
        page.keyboard.press("Control+Enter")
        holding(page, held, 1, "the refused reply")
        expect(card).to_have_attribute("data-resolved", "false")
        held.pop().fulfill(json={"ok": False, "final": True, "error": "Please retry."})
        page.unroute("**/api/event")
        round_trip(page)
        rendered(page)
        expect(card).to_have_attribute("data-resolved", "true")
        expect(card).to_be_visible()
        expect(reply).to_have_js_property("value", sent_words)
        return
    with sending(page, "the reply"):
        page.keyboard.press("Control+Enter")
    told(page)
    expect(card).to_have_attribute("data-resolved", "false")
    expect(card.locator(".lf-msg", has_text=sent_words)).to_be_visible()
    expect(reply).to_have_js_property("value", "")
    assert any(
        event["kind"] == "reply" and event.get("text") == sent_words
        for event in events_model.read_events(serve.page_dir)
    )


def test_an_inline_reply_link_finishes_a_resolution_fold(browser, serve):
    """A direct jump uses the resolved card, even before its outgoing fold ends."""
    url = serve(SEATED_ITEM_PAGE)
    root = panel_comment(serve.page_dir, "Which job first?", {"section": "jobs"})
    reply = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Pick the first job.",
        '<lf-ask id="first-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="first-job" choose>'
        '<lf-option id="mounts">Mounts</lf-option>'
        '<lf-option id="camera">Camera</lf-option>'
        "</lf-options></lf-ask>",
    )
    page = open_page(browser, url, init_script=HOLD_MOTION)
    resized(page, 1920, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    inline = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    inline.get_by_role("button", name="Resolve thread", exact=True).click()
    round_trip(page)
    expect(page.locator(f'.lf-going[data-id="{root}"]')).to_have_count(1)

    page.locator("#jobs .lf-resolved-summary").click()
    inline.get_by_role("button", name="Open interactive reply").click()
    expect(page.locator(f'.lf-going[data-id="{root}"]')).to_have_count(0)
    message = page.locator(
        f'.lf-thread:not([hidden]) .lf-msg[data-mid="{reply["id"]}"]'
    )
    expect(message).to_be_focused()
    expect(message.locator("#first-job")).to_be_in_viewport()
    # Its old animation completion must leave the canonical revealed card in place.
    page.evaluate("window.__lfHeld.forEach(animation => animation.finish())")
    expect(message).to_be_visible()
    expect(page.locator(f'.lf-thread[data-id="{root}"]')).to_have_count(1)


def test_the_fold_never_paints_a_frame_that_undoes_the_last(browser, serve):
    """A fold is a sequence, and every other check here reads a state.

    The gap that leaves is a frame that puts back what the frames before it took:
    a Web Animations effect stops applying at the end of its own interval, so
    anything holding the collapsed box open — a removal that slips a frame past
    the finish, a fill the helper stopped stating — paints the whole thread back
    at full height and full opacity for a frame before it goes. Held frames can't
    see it; each one is correct on its own. This watches the real fold at real
    speed and asks the only question a sequence can be wrong about, which is
    whether any frame is taller than the one before it.

    It is also what the first recording of this fold got wrong, in the other
    direction: sampled at exactly the duration, an animation is already past its
    own interval and reads as the element it never was."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    # Open disclosure before recording, then watch from before Resolve so the
    # frames it holds still are in the record alongside the ones that move.
    page.evaluate(FRAME_BY_FRAME, f'.lf-threads > [data-id="{c1}"]')
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    # The outgoing node becoming a retained hidden card is the fold's end and the
    # browser's own statement, so the wait is that rather than the sampler's flag.
    page.wait_for_selector(f'.lf-threads > [data-id="{c1}"]', state="hidden")
    seen = page.evaluate("() => window.__seen")

    grew = [
        (i, seen[i - 1], seen[i]) for i in range(1, len(seen)) if seen[i] > seen[i - 1]
    ]
    assert not grew, (
        "the fold painted a frame taller than the one before it: "
        + ", ".join(f"frame {i} went {was:.0f}px → {now:.0f}px" for i, was, now in grew)
    )
    # And it folded rather than vanishing between two samples, which would pass the
    # line above by having nothing to compare.
    assert any(0 < h < seen[0] for h in seen), (
        f"no frame caught the fold part way down (heights: {seen}), so a thread that "
        "went in one frame would read the same as one that folded"
    )


def test_a_user_who_asked_for_less_motion_gets_the_resolved_thread_at_once(
    browser, serve
):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the bargain the suggestion's own fold already makes, asked
    again here because the thread's is the path with somewhere to be left stranded:
    the node stays in the list until its fold ends, so a fold that never starts is a
    node that has to reach its retained resolved state by the same render that declined to play
    one."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page = open_page(
        browser,
        serve(LONG_PAGE, comments=2),
        context=context,
        init_script=HOLD_MOTION,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1, c2 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    expect(page.locator(f'.lf-thread[data-id="{c1}"][hidden]')).to_have_count(1)
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a user who asked for less motion was given a fold to sit through"
    )
    assert page.evaluate(LIST_STATE) == {
        "listed": [c2],
        "walkable": [c2],
    }, "the thread that declined its fold was left in the list"


def test_a_thread_reopened_mid_fold_folds_again_when_it_settles(browser, serve):
    """A fold is a claim about a node in the list, and the user can take
    that node out from under it: `z` reopens the thread the fold is carrying away, and
    the render that puts the thread back drops the folding node. Held past that, the
    record would hand the spent node back the next time the thread settled — the fold
    would be over before it started, and what stood in the list for its duration would
    be the thread as it read before it reopened, one message short.

    Reachable in the product, not only here: resolve, `z` and resolve are three round
    trips through the real server in 78ms measured, against a fold of 220ms, so the
    window is the user's typing speed and nothing else. Holding the motion is what
    makes it a state instead of a race — a paused animation never settles `finished`,
    so the record stays exactly as long as the assertions need it."""
    page = open_page(browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    going = page.locator(f'.lf-threads > .lf-going[data-id="{c1}"]')

    before = page.evaluate("window.__lfHeld.length")
    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going).to_have_count(1)
    folds = page.evaluate("window.__lfHeld.length")
    assert folds == before + 1, "the press drew something other than its one fold"

    undo(page)
    expect(thread).to_have_count(1)
    expect(going).to_have_count(0)
    # News the thread takes while it is open again, which the node the first fold was
    # carrying away has never held — so what folds the second time says which node it is.
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": c1,
            "text": "Reopened, and answered.",
        },
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(2)

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{c1}"]'))
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("window.__lfHeld.length") > folds, (
        "the second settlement drew no fold of its own"
    )

    # And the first fold runs out, which is the other half of two folds pending at
    # once: its node left the list when the thread reopened, and the record it must
    # not clear on its way is the live fold's. Cleared, the thread is pulled out of
    # the list in the middle of the motion carrying it away.
    # The await states its own end. `page.evaluate` takes no timeout in any binding, so
    # an animation that never settles `finished` is a wait nothing bounds: this one
    # didn't, and what should have been this test failing under its own name was the
    # job's whole 45-minute step, spent here, with the share of the suite already handed
    # to this worker never run. `SERVED_TIMEOUT_MS` is the patience the payload's own
    # probes give a promise they await inside `evaluate`, and the rejection comes back
    # through `evaluate` naming the motion that stopped and the bound it passed.
    page.evaluate(
        "async ([i, ranOutMs]) => { const m = window.__lfHeld[i];"
        " m.play(); m.currentTime = m.effect.getComputedTiming().duration;"
        " let timer;"
        " try {"
        "   await Promise.race([m.finished, new Promise((_, ranOut) => {"
        "     timer = setTimeout(() => ranOut(new Error("
        "       `held fold ${i} did not finish within ${ranOutMs}ms`)), ranOutMs); })]);"
        " } finally { clearTimeout(timer); } }",
        [before, render_checks_model.SERVED_TIMEOUT_MS],
    )
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)


def test_resolving_a_long_thread_lands_the_next_thread_in_view(browser, serve):
    """The landing of the thread focus moved on to was measured while the resolved
    thread still stood open above it, and the fold then took that room away under a
    smooth scroll: the next thread ended above the list."""
    # Both routes run the same resolve and the same landing.
    how = "r"
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 8, long_index=3)
    page = open_page(browser, url)
    open_threads_list(page, 800, 520)
    card = page.locator(f'.lf-thread[data-id="{roots[3]}"]')
    title = card.locator(":scope > .lf-thread-summary")
    title.click()
    rendered(page)
    title.focus()
    with sending(page, "the resolve"):
        if how == "r":
            page.keyboard.press("r")
        else:
            card.locator(".lf-resolve").click()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    following = page.locator(f'.lf-thread[data-id="{roots[4]}"]')
    expect(following.locator(":scope > .lf-thread-summary")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    landed = following.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)
    assert landed["inside"], f"the thread landed outside the list's band: {landed}"


def test_a_wheel_during_a_resolution_fold_outranks_the_landing_after_it(browser, serve):
    """The landing of the next title waits for the fold, and a user who scrolls the
    list meanwhile has taken it somewhere else: the deferred landing pulled the list
    back toward the title once the fold ended. Enough threads follow that the list's
    end doesn't clamp the wheeled position as the fold shrinks it."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 12, long_index=3)
    page = open_page(browser, url, init_script=HOLD_MOTION)
    # Short enough that the wheel stops short of the list's end once the fold has shrunk
    # it, so a clamp at the end cannot stand in for the landing this is about.
    open_threads_list(page, 800, 474)
    title = page.locator(f'.lf-thread[data-id="{roots[3]}"] > .lf-thread-summary')
    title.click()
    rendered(page)
    title.focus()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    following = page.locator(f'.lf-thread[data-id="{roots[4]}"] > .lf-thread-summary')
    expect(following).to_be_focused()
    page.wait_for_function("() => window.__lfHeld.length > 0")
    threads = page.locator(".lf-threads")
    threads.hover()
    page.mouse.wheel(0, 300)
    scroll_settled(page, ".lf-threads")
    wheeled = threads.evaluate("list => list.scrollTop")
    page.evaluate("() => window.__lfHeld.slice().forEach(motion => motion.finish())")
    rendered(page)
    scroll_settled(page, ".lf-threads")
    expect(following).to_be_focused()
    assert threads.evaluate("list => list.scrollHeight - list.clientHeight") > wheeled
    assert threads.evaluate("list => list.scrollTop") == pytest.approx(wheeled, abs=2)
