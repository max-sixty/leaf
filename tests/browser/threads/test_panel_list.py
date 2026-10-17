"""The Threads panel's list: what each row says, its order, the find box and narrowing
views, the threads waiting on the user, and one coherent reading when a list update
fails."""

import re
from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf import thread as thread_model
from playwright.sync_api import expect
from render_cases_interaction import (
    LIST_ORDER,
    PANEL_PAGE,
    PHOTO_THREAD,
    PROJECTOR_THREAD,
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    panel_comment,
)
from render_cases_layout import banner_control
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    expect_asks_answered,
    holding,
    open_page,
    panel_settled,
    resized,
    round_trip,
    said,
    sending,
    shortcut_bar_text,
    take_browser_errors,
    told,
    write,
)

from browser.threads import (
    OPEN_TITLE,
    focus_panel_thread,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_thread_rows_name_action_in_existing_status(browser, serve):
    page = open_page(
        browser, serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)
    )
    resized(page, 1440, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    asked = page.locator(f'.lf-thread[data-id="{PHOTO_THREAD}"]')
    expect(asked.locator(":scope > .lf-thread-summary .lf-thread-status")).to_have_text(
        "My turn to answer"
    )
    summary = asked.locator(":scope > .lf-thread-summary")
    recency = summary.locator(".lf-thread-recency")
    expect(recency).to_have_attribute("datetime", "2026-09-02T00:12:56-07:00")
    expect(recency).to_have_text(re.compile(r"^(now|\d+[mhd])$"))
    expect(summary.locator(".lf-thread-count")).to_have_count(0)
    regular = summary.evaluate(
        """summary => {
          const box = selector => summary.querySelector(selector).getBoundingClientRect();
          const topic = box('.lf-thread-topic');
          const status = box('.lf-thread-status');
          const trailing = box('.lf-thread-trailing');
          const center = rect => rect.top + rect.height / 2;
          return {
            panelWidth: summary.closest('.lf-thread-panel').getBoundingClientRect().width,
            statusBesideTopic: Math.abs(center(topic) - center(status)) < 2,
            timeBesideTopic: Math.abs(center(topic) - center(trailing)) < 2,
            statusBeforeTime: status.right <= trailing.left,
            timeAfterTopic: trailing.left >= topic.right,
          };
        }"""
    )
    assert regular["panelWidth"] > 400
    assert regular["statusBesideTopic"]
    assert regular["timeBesideTopic"]
    assert regular["statusBeforeTime"]
    assert regular["timeAfterTopic"]
    page.evaluate(
        "document.documentElement.style.setProperty('--lf-thread-panel-width', '320px')"
    )
    narrow = summary.evaluate(
        """summary => {
          const topic = summary.querySelector('.lf-thread-topic').getBoundingClientRect();
          const status = summary.querySelector('.lf-thread-status').getBoundingClientRect();
          const trailing = summary.querySelector('.lf-thread-trailing').getBoundingClientRect();
          const row = summary.getBoundingClientRect();
          const center = rect => rect.top + rect.height / 2;
          return {
            topicWidth: topic.width,
            statusBesideTopic: Math.abs(center(topic) - center(status)) < 2,
            topicBeforeStatus: topic.right <= status.left,
            statusBeforeTime: status.right <= trailing.left,
            trailingInside: trailing.right <= row.right,
          };
        }"""
    )
    assert narrow["topicWidth"] > 0
    assert narrow["statusBesideTopic"]
    assert narrow["topicBeforeStatus"]
    assert narrow["statusBeforeTime"]
    assert narrow["trailingInside"]
    asked.locator(":scope > .lf-thread-summary").focus()
    asked.locator(":scope > .lf-thread-summary").press("Enter")
    expect(asked).to_have_attribute("open", "")
    resolved = page.locator(f'.lf-thread[data-id="{PROJECTOR_THREAD}"]')
    expect(
        resolved.locator(":scope > .lf-thread-summary .lf-thread-status")
    ).to_have_text("✓ Resolved by Codex")


def test_a_failed_thread_list_update_keeps_one_coherent_reading(browser, serve):
    """A rejected list paint restores cards even after their child paint ran."""
    url = serve(LONG_PAGE, comments=2)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": roots[0]},
    )
    root = roots[1]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 open thread")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    page.evaluate(
        """async (id) => {
          const presentation = await window.__lfCheckApi();
          const list = document.querySelector('leaf-thread-list');
          const presentList = list.present.bind(list);
          let armed = true;
          list.present = async model => {
            const presented = await presentList(model);
            const child = model.rows.find(row => row.descriptor?.id === id)?.descriptor;
            if (armed && child && (child.folding || child.resolved)) {
              armed = false;
              window.threadChildFailed = true;
              throw new Error('injected thread-list failure after child paint');
            }
            return presented;
          };
          window.threadListPresentation = presentation;
          window.committedThread = document.querySelector(
            `.lf-thread[data-id="${id}"]`
          );
          window.committedMessage = committedThread.querySelector(
            `.lf-msg[data-mid="${id}"]`
          );
          window.committedEditor = committedThread.querySelector(
            ':scope > .lf-thread-reply leaf-text'
          );
          window.committedResolve = committedThread.querySelector(
            ':scope .lf-thread-meta-actions > .lf-resolve'
          );
        }""",
        root,
    )
    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    page.evaluate(
        'id => document.querySelector(`.lf-thread[data-id="${id}"] .lf-resolve`)'
        ".click()",
        root,
    )
    page.wait_for_function(
        "() => window.threadChildFailed && "
        "window.threadListPresentation.readApplicationPresentation().pending"
        ".includes('thread')",
    )

    recovered = page.locator(f'.lf-thread[data-id="{root}"]')
    expect(recovered).to_have_count(1)
    expect(recovered).to_be_visible()
    expect(recovered).to_have_attribute("data-resolved", "false")
    expect(recovered.locator("leaf-text")).to_have_count(1)
    expect(recovered.locator(".lf-reopen")).to_have_count(0)
    retained = page.evaluate(
        """id => {
          const thread = document.querySelector(`.lf-thread[data-id="${id}"]`);
          return {
            thread: thread === window.committedThread,
            message: thread.querySelector(`.lf-msg[data-mid="${id}"]`) === window.committedMessage,
            editor: thread.querySelector(':scope > .lf-thread-reply leaf-text') === window.committedEditor,
            resolve: thread.querySelector(':scope .lf-thread-meta-actions > .lf-resolve') === window.committedResolve,
          };
        }""",
        root,
    )
    assert all(retained[key] for key in ("thread", "message", "editor", "resolve")), (
        f"rollback replaced a retained card, message, editor, or control: {retained}"
    )
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 open thread")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: injected thread-list failure after child paint"
    ]

    holding(page, held_events, 2, "the gesture and the page's report of its failure")
    for route in held_events:
        route.continue_()
    page.unroute("**/api/event")
    round_trip(page)
    page.wait_for_function(
        "() => !window.threadListPresentation.readApplicationPresentation().pending.length"
    )
    expect(recovered).to_be_hidden()
    expect(recovered).to_have_attribute("data-resolved", "true")
    expect(recovered.locator("leaf-text")).to_have_count(0)
    expect(recovered.locator(".lf-reopen")).to_have_count(1)
    assert page.evaluate(
        'id => document.querySelector(`.lf-thread[data-id="${id}"]`) '
        "=== window.committedThread",
        root,
    ), "the next reading replaced the retained card"
    expect(page.locator(".lf-thread-view-summary")).to_have_text("0 open threads")
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 0")


def test_a_failed_narrowing_restore_has_one_owned_presentation_error(browser, serve):
    """A discarded filter repaint cannot turn its owned failure into pageerror."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate(
        """() => {
          const list = document.querySelector('leaf-thread-list');
          const render = list.render.bind(list);
          let failures = 2;
          list.render = () => {
            if (failures-- > 0) throw new Error('deliberate narrowing failure');
            return render();
          };
        }"""
    )

    page.get_by_role("searchbox", name="Find in threads").fill("comment")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )
    expected = [
        (
            "leaf: Presentation failed: Thread list presentation and retention failed: "
            "deliberate narrowing failure; deliberate narrowing failure"
        )
    ]
    assert [said(error) for error in take_browser_errors(page)] == expected

    page.get_by_role("searchbox", name="Find in threads").fill("")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )


def test_a_failed_narrowing_view_restores_its_committed_list_and_keeps_the_input(
    browser, serve
):
    """The narrowing face shares the list's checkpoint without owning native editing."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    view = page.locator("leaf-thread-narrowing")
    find = page.get_by_role("searchbox", name="Find in threads")
    page.evaluate(
        """() => {
          const view = document.querySelector('leaf-thread-narrowing');
          const present = view.present.bind(view);
          let failures = 2;
          view.present = model => {
            const result = present(model);
            if (model.summary === '1 of 2 open threads' && failures-- > 0)
              throw new Error('injected narrowing-view failure');
            return result;
          };
          window.__lfNarrowingBeforeFailure = {
            view,
            input: view.querySelector('.lf-find-box'),
            toggle: view.querySelector('.lf-thread-filter-toggle'),
            open: view.querySelector('[data-filter-value="open"]'),
          };
        }"""
    )

    find.evaluate(
        """input => {
          input.focus();
          input.value = 'Comment 0';
          input.setSelectionRange(2, 7);
          input.dispatchEvent(new InputEvent('input', {bubbles: true, composed: true}));
        }"""
    )
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return readApplicationPresentation().pending.includes('thread');
        }"""
    )

    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    expect(page.locator(".lf-thread-view-summary")).to_have_text("2 open threads")
    expect(page.locator('[data-filter-value="open"]')).to_have_text("Open (2)")
    expect(page.locator(".lf-thread-filter-toggle")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(find).to_have_value("Comment 0")
    expect(find).to_be_focused()
    assert find.evaluate("input => [input.selectionStart, input.selectionEnd]") == [
        2,
        7,
    ]
    assert view.evaluate(
        """view => {
          const before = window.__lfNarrowingBeforeFailure;
          return before.view === view &&
            before.input === view.querySelector('.lf-find-box') &&
            before.toggle === view.querySelector('.lf-thread-filter-toggle') &&
            before.open === view.querySelector('[data-filter-value="open"]');
        }"""
    )
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: injected narrowing-view failure"
    ]

    find.fill("")
    page.wait_for_function(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          return !readApplicationPresentation().pending.includes('thread');
        }"""
    )


def test_an_approval_made_elsewhere_reaches_the_panel_and_the_banner(browser, serve):
    """An accepted approval is a semantic fact, so it moves the epoch on its own.

    Nothing else about this state read changes: no thread, no Ask, no widget state, no
    pending gesture of this user's. The approval is another tab's, so there is no
    receipt to account and no ledger entry to remove — the two paints that show it have
    only the published fold to hear it from.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    approve = page.locator(".lf-signoff")
    expect(approve).to_have_text("Approve version")
    expect(page.locator(".lf-threads")).not_to_contain_text("Approved")
    thread = page.locator(".lf-threads > .lf-thread")
    # The chrome's separator, --rule, resolved where the panel's rules resolve it.
    separator = page.locator(".lf-thread-panel").evaluate(
        """panel => {
          const probe = document.createElement('i');
          probe.style.color = 'var(--rule)';
          panel.append(probe);
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        }"""
    )
    assert (
        thread.evaluate("node => getComputedStyle(node).borderBottomColor") != separator
    )

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "done",
            "author": "user",
            "version": 1,
        },
    )
    told(page)

    expect(page.locator(".lf-threads")).to_contain_text("Approved")
    expect(approve).to_have_text("✓ Version approved")
    assert (
        thread.evaluate("node => getComputedStyle(node).borderBottomColor") == separator
    )


def test_the_thread_clock_reopens_its_same_epoch_ticket(browser, serve):
    """A system-row age is presented mechanically without advancing semantic time."""
    # The approval age is mechanical. An unanswered comment would also cross its
    # server-owned workflow deadline, correctly requesting a fresh semantic reading.
    url = serve(LONG_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "done",
            "author": "user",
            "version": 1,
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    system = page.locator(".lf-threads > .lf-system")
    expect(system).to_have_text("✓ Approved just now")
    before = page.evaluate(
        """async () => {
          const list = document.querySelector('leaf-thread-list');
          const present = list.present.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.present = async model => {
            if (!armed) return present(model);
            armed = false;
            window.threadClockHeld = true;
            await held;
            window.threadClockStaleFailed = true;
            throw new Error('superseded thread preparation failed');
          };
          window.releaseThreadClock = release;
          window.threadClockHeld = false;
          window.threadClockStaleFailed = false;
          const now = Date.now.bind(Date);
          window.threadClockAdvance = 0;
          Date.now = () => now() + threadClockAdvance;
          window.threadPresentation = await window.__lfCheckApi();
          return threadPresentation.readApplicationPresentation();
        }"""
    )
    page.evaluate("window.threadClockAdvance = 60_000")
    page.wait_for_function("threadClockHeld")
    held = page.evaluate(
        """() => {
          window.threadClockReady = false;
          threadPresentation.whenApplicationPresented().then(() => {
            window.threadClockReady = true;
          });
          const reading = threadPresentation.readApplicationPresentation();
          return {
            pending: reading.pending,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
            ready: threadClockReady,
          };
        }"""
    )
    assert "thread" in held["pending"]
    assert held["semanticEpoch"] == before["semanticEpoch"]
    assert held["presentedEpoch"] == before["presentedEpoch"]
    assert held["ready"] is False

    # A second age change while preparation is held claims another pass. Its proof
    # cannot be acknowledged by the old reading, and it need not await that package.
    page.evaluate("window.threadClockAdvance = 120_000")
    page.wait_for_function("threadClockReady")
    expect(system).to_have_text("✓ Approved 2m ago")
    page.evaluate("releaseThreadClock()")
    page.wait_for_function("threadClockStaleFailed")
    expect(system).to_have_text("✓ Approved 2m ago")
    assert take_browser_errors(page) == []
    after = page.evaluate("threadPresentation.readApplicationPresentation()")
    assert after["semanticEpoch"] == before["semanticEpoch"]
    assert after["presentedEpoch"] == before["presentedEpoch"]


def test_the_panel_reads_the_thread_in_the_pages_own_order(browser, serve):
    """The list is the page's order, not the log's. A user walking a long
    thread walks it the way they walk the prose it is about, and every other
    reading of these threads already does: the marks down the page and the t/T walk. So
    the threads are written here in the reverse of the page's order and
    the panel is asked for its own, which is only the page's if something sorted it.

    A thread with nowhere in the page to be — a comment about the whole of it — comes
    after the ones that have somewhere, rather than at the moment it happened to be
    written. The list is threads alone: no heading stands among them."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    whole = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "about": "design",
            "text": "The middle third is too long.",
        },
    )["id"]
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})
    cap = panel_comment(d, "Is forty enough?", {"section": "how-cap"})
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    assert page.evaluate(LIST_ORDER) == [
        lede,
        cap,
        merge,
        whole,
    ], "the panel is not reading in the page's order"
    expect(page.locator(".lf-threads > :not(.lf-thread)")).to_have_count(0)

    # A design comment about the page as a whole has an address to show but no passage
    # to return to. It is a static label, not a broken anchored-thread control.
    whole_label = page.locator(f'.lf-thread[data-id="{whole}"] .lf-quote')
    expect(whole_label).to_have_text("design · the page")
    expect(whole_label).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(whole_label).not_to_have_attribute("role", "button")

    expect(page.locator(f'.lf-thread[data-id="{lede}"] leaf-text')).to_have_attribute(
        "placeholder", "Reply"
    )
    # From no place on the page the walk starts at the list's first thread; a caret a
    # click leaves is a place, as it is for `m`.
    page.evaluate(
        "() => { document.activeElement?.blur(); getSelection().removeAllRanges(); }"
    )
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()


def test_recent_order_lists_threads_by_their_latest_message(browser, serve):
    """Order is the panel's own view, not a filter. Recent puts the thread spoken in
    last at the top. The View control keeps one label whatever is
    chosen, and a narrowed summary arriving never moves the choices under the press.
    Reset clears refinements but keeps the order, and with the panel shut t/T still
    walk the page's order."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    now = datetime.now().astimezone()

    def comment(text, anchor, days_ago):
        event = {"kind": "comment", "author": "user", "revision": 1, "text": text}
        if anchor:
            event["anchor"] = anchor
        event["ts"] = (now - timedelta(days=days_ago)).isoformat(timespec="seconds")
        return append_carried_log_record(d, event)["id"]

    lede = comment("Six weeks reads long.", {"section": "lede"}, 10)
    cap = comment("Is forty enough?", {"section": "how-cap"}, 3)
    whole = comment("The whole thing needs a summary.", None, 12)
    # A reply today makes the oldest thread the most recent one.
    thread_model.post_reply(d, {"to": whole, "for": whole}, "Added one at the top.")

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    order = page.get_by_role("group", name="Order", exact=True)
    expect(order.get_by_role("button", name="Page")).to_have_attribute(
        "aria-pressed", "true"
    )
    toggle = page.locator(".lf-thread-filter-toggle")
    expect(toggle).to_have_text("View")
    order.get_by_role("button", name="Recent").click()
    expect(toggle).to_have_text("View")
    assert page.evaluate(LIST_ORDER) == [whole, cap, lede]

    # Order hides nothing, so it is not part of what Reset puts back. The summary
    # stands below the choices, not above them, so what a press changes in it moves
    # none of them.
    anchored = page.get_by_role("group", name="Location", exact=True).get_by_role(
        "button", name=re.compile(r"^Anchored")
    )
    before = anchored.bounding_box()
    reset = page.get_by_role("button", name="Reset thread filters")
    expect(reset).to_be_hidden()
    anchored.click()
    expect(reset).to_be_visible()
    assert anchored.bounding_box() == before, "the summary moved the choices"
    shown = LIST_ORDER.replace(".map(", ".filter((n) => !n.hidden).map(", 1)
    assert page.evaluate(shown)[:1] == [cap]
    page.get_by_role("button", name="Reset thread filters").click()
    assert page.evaluate(shown)[:1] == [whole]
    expect(order.get_by_role("button", name="Recent")).to_have_attribute(
        "aria-pressed", "true"
    )

    # The panel's walk follows the list it shows: after the first thread comes the one
    # under it, where page order would wrap round to the lede.
    page.locator(f'.lf-thread[data-id="{whole}"] > .lf-thread-summary').focus()
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()

    # Page order restores the page's order.
    order.get_by_role("button", name="Page").click()
    assert page.evaluate(LIST_ORDER) == [lede, cap, whole]

    # The page's walk is the page's order whatever the panel shows.
    # From no place on the page, which is where the walk starts from its first thread:
    # a caret a click leaves is a place, as it is for `m`.
    order.get_by_role("button", name="Recent").click()
    page.locator(".lf-threads-toggle").click()
    page.evaluate(
        "() => { document.activeElement?.blur(); getSelection().removeAllRanges(); }"
    )
    page.keyboard.press("t")
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    assert (
        page.evaluate(
            "() => document.activeElement.closest('[data-thread]').dataset.thread"
        )
        == lede
    )


def test_finding_narrows_the_list_and_says_how_much_of_it_is_left(browser, serve):
    """A search box is what every panel with a long list has, and the trap every one of
    them has too: the list goes quiet about the threads it is hiding. So the head says
    how much of the thread is in front of the user for as long as a narrowing
    stands, and a thread asked for by name — a mark on the page, a send that landed —
    lets the narrowing go rather than declining to appear.

    The narrowing reads the words, the part of the page, and nothing else: the count in
    the banner is the log's and does not move."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Review: six weeks reads long.", {"section": "lede"})
    cap = panel_comment(d, "Review: is forty megabytes enough?", {"section": "how-cap"})
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page = open_page(browser, url)
    # Slash belongs to the nearest search scope. Out on the prose it opens page search;
    # Escape returns to the prose, and `g T` is the route into the panel, where the same
    # press opens that list's own search instead. Read the two landings against each other.
    #
    # A plain paragraph rather than the body's own middle, which is a widget on this
    # page: `c` goes to the box belonging to whatever the user is standing in, so a
    # press made from the diff opens the composer on the diff and never reaches the panel
    # at all. Standing on prose is what "out on the prose" was always describing — and an
    # uncommented one, a click on a mark opening the thread it carries, which would be the
    # panel arriving ahead of the press that is meant to open it.
    page.locator("#how-store").click()
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    expect(page.locator(OPEN_TITLE)).to_be_focused()
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_be_focused()

    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{cap}"]')).to_have_count(1)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("1 of 3 open threads")
    # The page's own count is the log's and says so throughout.
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 3")

    # The part of the page a thread is on is one of its words: a user looking for the
    # merge rule finds the thread in that section without its message saying so.
    page.get_by_role("searchbox", name="Find in threads").fill("merge rule")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{merge}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{lede}"]:not([hidden])')).to_have_count(0)

    # Enter accepts the filtered list's first result. From there, the same n/N grammar
    # as page search walks forward and backward through only the threads found.
    page.get_by_role("searchbox", name="Find in threads").fill("review")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    page.keyboard.press("Enter")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    search_line = shortcut_bar_text(page)
    assert re.search(r"n / N\s*search matches", search_line), search_line
    assert "show all" not in search_line
    # Search has one canonical walk in this scope; the page-level thread walk stands
    # down rather than leaving t/T as aliases for the same two movements.
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("n")
    expect(
        page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    ).to_be_focused()
    page.keyboard.press("Shift+n")
    expect(
        page.locator(f'.lf-thread[data-id="{lede}"] > .lf-thread-summary')
    ).to_be_focused()
    # Leaving the panel leaves n/N's scope. Escape becomes the useful compact action
    # again because the narrowing still stands and can be cleared from the page.
    page.locator("#how-store").click()
    assert re.search(r"esc\s*show all", shortcut_bar_text(page))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)
    page.get_by_role("searchbox", name="Find in threads").fill("merge rule")

    # Asked for a thread the narrowing hides, the panel shows it rather than nothing:
    # the press came from the page, where no narrowing was ever visible.
    page.locator("#lede").click()
    expect(page.locator(f'.lf-thread[data-id="{lede}"]')).to_have_count(1)
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)

    # Escape leaves typing first, so the search remains useful for keyboard navigation.
    search = page.get_by_role("searchbox", name="Find in threads")
    search.click()
    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("back to list")
    # Back on the list is on the one thread the narrowing left, and from that thread
    # the panel's own rungs follow: the narrowing clears, then the panel closes.
    page.keyboard.press("Escape")
    cap_title = page.locator(f'.lf-thread[data-id="{cap}"] > .lf-thread-summary')
    expect(cap_title).to_be_focused()
    expect(search).to_have_value("megabytes")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(3)
    expect(cap_title).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()


def test_the_panel_can_show_only_what_is_waiting_on_the_user(browser, serve):
    """Which threads the user still owes an answer to is a question the log already
    answers: an agent's question waits on them until they answer it. So the panel reads the log rather than keeping a record of what this user
    has read — nothing to go stale in a second tab, and nothing to remember across a
    reload.

    The count is the whole page's; the list is the ones it names."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    mine = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    theirs = panel_comment(
        d, "Is forty enough?", {"section": "how-cap"}, "agent", question="Forty?"
    )

    page = open_page(browser, url)
    # The key belongs to the panel, not to the page: a list the user is not looking at
    # is not a thing to narrow. Out on the prose the line never offers it and the press
    # does nothing — read against the same press landing a few lines below, which is what
    # makes the silence a rule rather than a page that happened not to react.
    #
    # A plain paragraph rather than the body's own middle, which is a widget here: `c`
    # below goes to the box belonging to whatever the user is standing in, and a press
    # made from the diff would open the composer on the diff rather than reach the panel
    # at all. Uncommented, too: a click on a mark opens the thread it carries.
    page.locator("#how-store").click()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("waiting on me")
    page.keyboard.press("w")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()

    # `g T` stands the user on the open thread in the list, where the key is live and the
    # line says so. The control names it, off the row, so the two cannot come to spell it
    # differently.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    expect(page.locator(OPEN_TITLE)).to_be_focused()
    expect(page.locator(".lf-needs")).to_have_text("Me (1)")
    expect(page.locator(".lf-needs")).to_have_attribute("title", re.compile(r"\(w\)$"))
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("waiting on me")
    # `c` from that thread enters its reply box, and there `w` is a character like any
    # other — the typing scope claims what types one, so the row stands down and the line
    # drops it. Escaping out onto the thread makes it live again. Both directions,
    # because a key that were live in the box would type nothing and read as a dead
    # keyboard.
    page.keyboard.press("c")
    expect(
        page.locator(".lf-threads > .lf-thread:not([hidden])[open] leaf-text")
    ).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("waiting on me")
    page.keyboard.press("Escape")
    expect(page.locator(OPEN_TITLE)).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("waiting on me")
    page.keyboard.press("w")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{theirs}"]')).to_have_count(1)
    # The narrowing hid the thread the user stood on, so they stand on the one it left.
    theirs_title = page.locator(f'.lf-thread[data-id="{theirs}"] > .lf-thread-summary')
    expect(theirs_title).to_be_focused()
    # Waiting-on-user is a filter, not a text search. It does not claim search-repeat
    # keys merely because the result list happens to be narrowed.
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("search matches")
    page.keyboard.press("n")
    expect(theirs_title).to_be_focused()
    # The card the narrowing hides keeps its node. A widget an agent sent in a reply is
    # instantiated once, in that card, and the Ask reading and the On panel find it by
    # id in the document — hidden is the list's business, gone would be a claim about the
    # log (test_a_narrowing_hides_a_thread_without_taking_its_ask_off_the_page).
    expect(
        page.locator(f'.lf-threads > .lf-thread[hidden][data-id="{mine}"]')
    ).to_have_count(1)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 2 open threads · On me"
    )
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")

    # Closing the owning surface retires both its narrowing frame and the g T frame below
    # it. The narrowing itself stays set for a later reopen, but Escape on the page must
    # neither advertise nor mutate a filter the user cannot see.
    page.get_by_role("button", name="Close threads", exact=True).click()
    panel_settled(page, False)
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("show all")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    page.keyboard.press("w")
    page.keyboard.press("w")

    # Escape unwinds the narrowing before it closes the panel, from wherever the user
    # is standing: a list that is not the whole thread is a layer they put on.
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("show all")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("w")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)

    # Answering the agent's comment takes it out of the user's list and hands the
    # next word to the agent; the user goes with the thread into the view that holds
    # it, standing on it as a sent reply leaves them (#46 on the rewrite survey).
    page.locator(f'.lf-thread[data-id="{theirs}"] .lf-thread-summary').click()
    reply = page.locator(f'.lf-thread[data-id="{theirs}"] leaf-text')
    reply.click()
    reply.type("Forty is plenty.")
    page.locator(f'.lf-thread[data-id="{theirs}"] .lf-thread-send').click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("Me (0)")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    expect(
        page.locator(f'.lf-thread[data-id="{theirs}"] > .lf-thread-summary')
    ).to_be_focused()
    expect(page.locator(".lf-needs")).to_be_disabled()
    expect(page.locator(".lf-needs")).to_have_attribute(
        "title", "Nothing shown is waiting on me"
    )


def test_an_agent_reply_says_when_the_user_owes_an_answer(browser, serve):
    """An open thread and a request to its user are different facts. A complete
    answer stays available for follow-up without entering the waiting list; a reply
    carrying an explicit prose ask enters it until the user answers. A widget ask
    needs no duplicate flag: its own current projection enters and leaves the list."""
    url = serve(PANEL_PAGE)
    answered = panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    asked = panel_comment(serve.page_dir, "What remains?", {"section": "how-store"})
    thread_model.post_reply(
        serve.page_dir,
        {"to": answered, "for": answered},
        "Forty is what the slowest supported device can hold.",
    )
    thread_model.post_reply(
        serve.page_dir,
        {"to": asked, "for": asked},
        "One choice remains.",
        markup='<lf-ask id="store-owner">Which store should own the result?</lf-ask>',
    )
    page = open_page(
        browser,
        url,
        init_script="""(() => {
          const counts = window.__replyListeners = {drafts: 0};
          const add = Document.prototype.addEventListener;
          Document.prototype.addEventListener = function(type, ...args) {
            if (this === document && type === "lf-drafts") counts.drafts += 1;
            return add.call(this, type, ...args);
          };
          const define = customElements.define.bind(customElements);
          customElements.define = (name, ctor, options) => {
            if (name === "lf-options") {
              const connected = ctor.prototype.connectedCallback;
              ctor.prototype.connectedCallback = function() {
                if (this.id === "backend") {
                  const message = this.closest(".lf-msg");
                  window.__backendContext ??= {
                    message: Boolean(message),
                    thread: this.closest(".lf-thread")?.dataset.id ?? null,
                    saidAt: message?.querySelector("time")?.dateTime ?? null,
                  };
                }
                return connected?.call(this);
              };
            }
            return define(name, ctor, options);
          };
        })()""",
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-needs")).to_have_text("Me (1)")
    expect(page.locator(".lf-thread")).to_have_count(2)
    expect(
        page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-status')
    ).to_have_text("My turn to answer")
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"] .lf-thread-status')
    ).to_have_count(0)

    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-thread:not([hidden])")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{asked}"]')).to_have_count(1)
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"]:not([hidden])')
    ).to_have_count(0)

    listeners = page.evaluate("() => ({...window.__replyListeners})")
    find = page.get_by_role("searchbox", name="Find in threads")
    for key in ("r", "e", "Backspace", "Backspace"):
        find.press(key)
    assert page.evaluate("() => ({...window.__replyListeners})") == listeners, (
        "reconciling a hidden thread registered another reply-box listener"
    )
    expect(find).to_have_value("")

    # The completed thread is absent under the narrowing. A later structured ask must
    # still be projected before the filter decides whether to admit that thread, or the
    # question can never render itself into the list that would discover it.
    widget_reply = thread_model.post_reply(
        serve.page_dir,
        {"to": answered},
        "Choose the backend here.",
        '<lf-ask id="backend-decision"><h3>Which backend?</h3>'
        '<lf-options id="backend" choose>'
        '<lf-option id="backend-sqlite"><strong>SQLite</strong></lf-option>'
        '<lf-option id="backend-postgres"><strong>Postgres</strong></lf-option>'
        "</lf-options></lf-ask>",
    )
    told(page)
    expect(page.locator(".lf-needs")).to_have_text("Me (2)")
    expect(page.locator(f'.lf-thread[data-id="{answered}"]')).to_have_count(1)
    assert page.evaluate("() => window.__backendContext") == {
        "message": True,
        "thread": answered,
        "saidAt": widget_reply["ts"],
    }

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{answered}"]'))
    page.locator("#backend-sqlite").click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("Me (1)")
    expect(
        page.locator(f'.lf-thread[data-id="{answered}"]:not([hidden])')
    ).to_have_count(0)

    focus_panel_thread(page.locator(f'.lf-thread[data-id="{asked}"]'))
    reply = page.locator(f'.lf-thread[data-id="{asked}"] leaf-text')
    write(reply, "SQLite should own it.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-send').click()
    holding(page, held, 1, "the answer to the prose Ask")
    # The answer shows as sent at once; whether it answers the Ask is the server's
    # reading, so the thread stays on the user until that arrives.
    status = page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-status')
    expect(status).to_have_attribute("title", "My turn to answer · Sending")
    expect(reply).to_have_js_property("value", "")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    # The reading takes the thread off the user, and the user goes with it out of
    # "Waiting on me" (thread-card.js, `#speak`).
    expect(page.locator('[data-filter-value="user"]')).to_have_text("Me (0)")
    expect(page.locator('[data-filter-value="user"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(".lf-needs")).to_have_text("Me (0)")
    expect(page.locator(f'.lf-thread[data-id="{asked}"]')).to_be_visible()


def test_a_narrowing_hides_a_thread_without_taking_its_ask_off_the_page(browser, serve):
    """Thread narrowing changes presentation, not the admitted ask inventory.

    After both asks are answered, hiding a thread with the On you filter keeps
    both canonical records in Done and preserves the page-wide completion count.
    """
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread:not([hidden]) .lf-thread-summary").first.click()
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    question.locator("lf-option:not([chosen]) > .lf-pick").first.click()
    round_trip(page)
    question.locator(".lf-done").click()
    round_trip(page)
    expect_asks_answered(page, "2/2")
    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    expect(page.locator(".lf-thread-view-summary")).to_have_text(
        "1 of 2 open threads · On me"
    )
    expect(
        page.locator('.lf-threads > .lf-thread[hidden][data-resolved="false"]')
    ).to_have_count(1)
    expect_asks_answered(page, "2/2")
    banner_control(page, ".lf-queue").click()
    page.locator(".lf-queue-done > summary").click()
    done = page.locator(".lf-queue-done .lf-queue-row[data-lf-kind='ask']")
    expect(done).to_have_count(2)
    assert set(done.evaluate_all("rows => rows.map(row => row.dataset.lfAt)")) == {
        "widget:off-workaround-review",
        "widget:off-slip",
    }


def test_a_reply_that_takes_its_card_out_of_the_view_takes_the_user_with_it(
    browser, serve
):
    """The user's own reply answers the question, so "Waiting on me" no longer holds
    the thread. Their turn widens the view to show it and leaves them standing on it,
    as a sent reply does, rather than dropping them on the list once the log answers
    (the user's decision, 2026-10-07, #46 on the rewrite survey)."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    theirs = panel_comment(
        d, "Is forty enough?", {"section": "how-cap"}, "agent", question="Forty?"
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator(".lf-needs").click()
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    card = page.locator(f'.lf-thread[data-id="{theirs}"]')
    card.locator(".lf-thread-summary").click()
    box = card.locator("leaf-text")
    write(box, "Forty is enough.")
    expect(box).to_be_focused()
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "false")
    expect(card).to_be_visible()
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()


def test_a_walk_to_an_ask_the_narrowing_hides_widens_the_list(browser, serve):
    """A card the narrowing hid keeps its node, so the `m` walk can still name the
    question in it — and arriving there has to show it, the way showThread does:
    focus on a card with no box is a no-op and the announcement would say "1 of 2"
    over a list that shows something else. The thread the list shows asks the user a
    question too, so focus on the list stands on that item, and the hidden Ask stands
    before it on the page."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    question = page.locator(".lf-thread-panel lf-options[choose]").first
    card = question.locator(
        "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' lf-thread ')][1]"
    )
    page.get_by_role("searchbox", name="Find in threads").fill("stay blocked")
    expect(card).to_have_attribute("hidden", "")
    page.locator(".lf-threads").focus()
    page.keyboard.press("Shift+m")
    expect(card).not_to_have_attribute("hidden", "")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value("")
    assert page.evaluate(
        "() => document.activeElement.closest('.lf-thread') !== null"
    ), "the walk landed outside the card it named"


def test_an_answer_without_a_title_leaves_the_opening_words(browser, serve):
    """A thread waits for its title only while it waits on the agent: an answer that
    names nothing leaves the row on the opening words rather than on a placeholder
    nothing will replace."""
    url = serve(PANEL_PAGE)
    opening = "Which room is the workshop in?"
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    topic = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"] .lf-thread-topic')
    expect(topic).to_have_text("Generating title")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root,
            "responds": root,
            "text": "The terrace room.",
        },
    )
    told(page)
    expect(topic).to_have_text(opening)
    expect(topic).not_to_have_attribute("data-lf-pending-title", "")
    assert not take_browser_errors(page)


def test_a_thread_nobody_picked_up_reads_its_opening_words(browser, serve):
    """A comment no agent has picked up past the pickup grace has nothing naming
    it, so its row reads the comment rather than a placeholder."""
    url = serve(PANEL_PAGE)
    opening = "Is the workshop room accessible?"
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": opening,
            "ts": "2026-01-01T09:00:00-08:00",
        },
    )["id"]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]')
    expect(thread.locator(".lf-thread-status")).to_have_text("Waiting for pickup")
    expect(thread.locator(".lf-thread-topic")).to_have_text(opening)
    assert not take_browser_errors(page)


def test_typing_a_search_moves_nothing_under_the_find_box(browser, serve):
    """The view's summary and Reset stand in every view, so the first letter typed
    into the find box changes the summary's words and Reset's paint, never the list's
    place. The row used to arrive with that letter and push the list 35px down under
    the user typing above it. A search matching nothing says so where a thread's title
    would start."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    reset = page.get_by_role("button", name="Reset thread filters")
    expect(reset).to_be_hidden()
    top = page.locator(".lf-threads").evaluate("el => el.getBoundingClientRect().top")
    title = page.locator(".lf-thread-topic").first.evaluate(
        "el => el.getBoundingClientRect().left"
    )
    find = page.get_by_role("searchbox", name="Find in threads")
    search_field = page.locator(".lf-find-box")
    before_search = search_field.bounding_box()
    find.click()
    page.keyboard.type("zq")
    expect(page.locator(".lf-thread-view-summary")).to_have_text("0 of 2 open threads")
    expect(reset).to_be_visible()
    assert page.locator(".lf-threads").evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(top, abs=0.5), "the search moved the list"
    empty = page.locator(".lf-threads > .lf-empty")
    expect(empty).to_be_visible()
    words = empty.evaluate(
        """el => {
          const range = document.createRange();
          range.selectNodeContents(el);
          return range.getBoundingClientRect().left;
        }"""
    )
    assert words == pytest.approx(title, abs=0.5), (words, title)
    assert search_field.bounding_box() == before_search
    search_field.get_by_role("button", name="Clear entry").click()
    expect(find).to_have_value("")
    expect(find).to_be_focused()
    expect(page.locator(".lf-thread-view-summary")).to_have_text("2 open threads")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    assert search_field.bounding_box() == before_search
    assert page.locator(".lf-threads").evaluate(
        "el => el.getBoundingClientRect().top"
    ) == pytest.approx(top, abs=0.5), "clearing the search moved the list"
