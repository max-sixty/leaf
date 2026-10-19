"""What the page says the agent is doing: the banner, the leaves row, the tab's mark,
and each message's workflow, dated by the server's clock."""

import os
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare_work,
    end_work,
    record_claim,
    working,
)
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import service as service_model
from leaf import state as cleanup_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_layout import token_colour
from render_cases_navigation import TAB_AND_DOT, TAB_TONE, live_watcher
from render_harness import LONG_PAGE, open_page, panel_settled, shown, ticked, told

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_page_dates_a_claim_by_the_clock_that_wrote_it(browser, serve):
    """Every timestamp a seat reads out was written by the server; `Date.now()` is the
    machine holding the tab. A laptop an hour fast therefore called a claim made this
    minute an hour stale — on the banner, on a roster row and under every question at
    once, always in the same direction, with nothing in the timestamp to give it away.
    The poll carries the server's own now, so the offset is measured rather than
    assumed.

    It is the user's clock that moves here, because that is the one of the two a page
    has to survive: the server writes the timestamps it later reads back and cannot
    disagree with itself, while the user's machine is not the page's to correct."""
    page = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir
    text = page.locator(".lf-status-detail")
    dot = page.locator(".lf-banner .lf-dot")

    def claim(detail):
        record_claim(d, id="s")
        declare_work(d, detail)
        told(page)

    claim("running the migration")
    expect(text).to_have_text(
        re.compile(r"^\s*Claude is working — running the migration \(just now\)\.")
    )

    # An hour fast. A fixed time rather than an installed clock, so the page's own
    # polling keeps running and the next reading is a real one.
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=1))
    # New words, so the line under test can only be one this user painted after the
    # clock moved: an unchanged sentence would pass on the render before it.
    claim("waiting on the shard")
    expect(text).to_have_text(
        re.compile(r"^\s*Claude is working — waiting on the shard \(just now\)\.")
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))


def test_a_thread_says_what_the_agent_is_doing_about_it(
    browser, serve, tmp_path, dead_pid
):
    """An exact message workflow says which user question the agent is working on,
    beside the banner's account of the page as a whole.

    A user with three questions open and no replies under any of them cannot tell a
    question being worked from a question nobody has looked at, and the page holds the
    answer: the agent said so. What the log holds is what happened, so this is not in
    it — a sentence somebody rewrites every few minutes is a claim, painted as
    provisional news on the message while the answer is still owed.

    Nothing deletes the line directly. The agent's next reply answers the claim;
    resolution hides it while the thread is closed, and reopening reveals it
    again."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    d = serve.page_dir
    comments = [e for e in events_model.read_events(d) if e["kind"] == "comment"]
    held, other = comments[0]["id"], comments[1]["id"]
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    workflows = page.locator(".lf-msg-sending")
    held_thread = page.locator(f'.lf-thread[data-id="{held}"]')
    other_thread = page.locator(f'.lf-thread[data-id="{other}"]')
    held_workflow = held_thread.locator(
        f'.lf-msg[data-mid="{held}"] > .lf-msg-head .lf-msg-sending'
    )
    other_workflow = other_thread.locator(
        f'.lf-msg[data-mid="{other}"] > .lf-msg-head .lf-msg-sending'
    )
    expect(workflows).to_have_count(2)
    expect(held_workflow).to_have_text("Sent")
    held_workflow.evaluate("node => { node.dataset.identityProbe = 'kept' }")

    # The old page-wide start is deliberately stale: delivery into this exact turn,
    # rather than a fresh start, must be what changes the shared activity reading.
    record_claim(d, id="s", pid=os.getpid(), agent="Claude")
    declare_work(
        d,
        "the earlier task",
        ts=(datetime.now().astimezone() - timedelta(minutes=20)).isoformat(
            timespec="seconds"
        ),
    )
    # Durable delivery into the open turn advances the exact same row in place and
    # does not disturb another user move.
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(transaction, [comments[0]])
    told(page)
    expect(held_workflow).to_have_text("Picked up")
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(other_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    expect(held_workflow).to_have_attribute("data-identity-probe", "kept")
    expect(other_workflow).to_have_text("Sent")

    # The agent finishes the earlier task and waits on the user.
    end_work(d)
    latent_waiting = CliRunner().invoke(
        cli_model.cli, ["status", str(d), "waiting", "review the answer"]
    )
    assert latent_waiting.exit_code == 0, latent_waiting.output
    told(page)
    expect(held_workflow).to_have_text("Picked up")

    cleanup_model.close_session_turn("s")
    told(page)
    expect(held_workflow).to_have_text("Turn ended")
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    cleanup_model.open_session_turn("s")

    def start(item, line):
        started = CliRunner().invoke(
            cli_model.cli, ["task", "start", str(d), item, line]
        )
        assert started.exit_code == 0, started.output
        told(page)

    start(held, "reading the reconnect traces")
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(other_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    # One line, on the thread it names: a mark that stood on every open thread would
    # say only that the agent is busy, which the banner above already says.
    expect(workflows).to_have_count(2)
    expect(held_workflow).to_have_text("Working")
    expect(held_workflow).to_have_attribute(
        "title", "Working · reading the reconnect traces"
    )
    expect(held_workflow).to_have_attribute("data-identity-probe", "kept")
    expect(held_workflow).to_have_count(1)
    expect(other_workflow).to_have_count(1)
    expect(other_workflow).to_have_text("Sent")
    # The panel keeps one thread open. A folded row names the stage, since it shows no
    # message; the open one's message names it beside itself, so its summary does not
    # say it a second time.
    header_status = held_thread.locator(":scope > .lf-thread-summary .lf-thread-status")
    held_summary = held_thread.locator(":scope > .lf-thread-summary")
    expect(held_thread).to_have_js_property("open", True)
    expect(header_status).to_have_text("Working")
    expect(header_status).to_be_hidden()
    other_thread.locator(":scope > .lf-thread-summary").click()
    expect(held_thread).to_have_js_property("open", False)
    expect(header_status).to_be_visible()
    held_summary.click()
    expect(held_thread).to_have_js_property("open", True)
    expect(header_status).to_be_hidden()
    expect(held_workflow).to_be_visible()
    # The move's state is metadata on the exact outgoing message, closing that row
    # rather than taking a full-width row of its own. Resolve settles the thread, not
    # the message, so it stands in the thread's corner and the row ends here.
    expect(held_thread.locator(":scope > .lf-msg-sending")).to_have_count(0)
    assert held_workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    )

    # New words do not detach the claim from the comment that started the work.
    followup = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "user",
            "parent": held,
            "revision": 1,
            "text": "Also compare the retry after reconnecting.",
        },
    )
    told(page)
    followup_workflow = held_thread.locator(
        f'.lf-msg.user[data-mid="{followup["id"]}"] > .lf-msg-head .lf-msg-sending'
    )
    expect(held_workflow).to_have_text("Working")
    expect(followup_workflow).to_have_text("Sent")
    expect(held_thread.locator(":scope > .lf-msg-sending")).to_have_count(0)
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"

    # A later start on the page's own task is not an answer to the thread, so the
    # thread's line stands.
    working(d, "drafting v2")
    told(page)
    expect(held_workflow).to_have_count(1)
    expect(held_workflow).to_have_attribute(
        "title", "Working · reading the reconnect traces"
    )

    # The answer is what ends it.
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": held,
            "responds": followup["id"],
            "revision": 1,
            "text": "The traces say it is the vendor's timer, not ours.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-thread[data-id="{held}"] .lf-msg.agent')).to_have_count(1)
    expect(held_workflow).to_have_count(0)
    expect(workflows).to_have_count(1)

    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"

    # Once the answer has settled the input, renewed work is promised in a new
    # thread reply rather than opened without a message.
    promised = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(d),
            held,
            "--text",
            "I'll re-run it against the rolling deploy.",
            "--todo",
            "Re-run against the rolling deploy",
        ],
    )
    assert promised.exit_code == 0, promised.output
    working(d, "re-running it against the rolling deploy", subject=held)
    told(page)
    expect(held_workflow).to_have_count(0)
    expect(header_status).to_have_text("Working")
    # No message carries this work, so the open card's summary still says it.
    expect(header_status).to_be_visible()
    expect(held_thread.locator(":scope > .lf-msg-sending")).to_have_count(0)
    expect(workflows).to_have_count(1)

    # A thread the user has closed asks nothing: its card, closed from another tab,
    # stays where it stands, holding the resolution behind its notice, and its title
    # no longer says the agent is working on it.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": held})
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(held_thread.locator(".lf-thread-news")).to_have_text("Resolved")
    expect(held_thread.locator(".lf-thread-status")).to_have_count(0)
    expect(workflows).to_have_count(1)

    # Reopening restores the task, which no reply ends. Its start goes with the page
    # claim it is part of: once nothing holds the page, the task is open but nothing
    # runs on it under a banner that says nobody is there.
    append_carried_log_record(
        d, {"kind": "unresolve", "author": "user", "parent": held}
    )
    told(page)
    expect(held_thread.locator(".lf-thread-status")).to_have_text("Working")
    expect(workflows).to_have_count(1)
    record_claim(d, id="s", pid=dead_pid)
    told(page)
    expect(held_thread.locator(".lf-thread-status")).to_have_text("To-do open")
    expect(workflows).to_have_count(1)


def test_the_banner_and_the_leaves_row_say_the_served_activity(browser, serve):
    """The served activity reaches the banner's row, its disclosure and dot, and this
    page's row in the leaves drawer. What each says for every reading is
    `tests/runtime/activity-words.test.mjs`'s, and which reading a log and claim come
    to is `tests/model/test_activity.py`'s."""
    page = open_page(browser, serve(LONG_PAGE))
    record_claim(serve.page_dir, id="s", pid=os.getpid(), agent="Claude")
    declare_work(serve.page_dir, "Writing the page")
    told(page)
    expect(page.locator(".lf-status-text")).to_have_text(
        "Claude working — Writing the page"
    )
    expect(page.locator(".lf-status-detail")).to_have_text(
        re.compile(r"^\s*Claude is working — Writing the page \(just now\)\.")
    )
    expect(page.locator(".lf-banner .lf-dot")).to_have_class(re.compile(r"\bworking\b"))
    expect(page.locator(".lf-others-self .lf-others-line")).to_have_text(
        "Working — Writing the page"
    )


def test_an_unpicked_move_says_it_is_waiting_after_the_short_grace(browser, serve):
    """Silence changes the wording, not the durable phase or the interaction seat."""
    url = serve(LONG_PAGE)
    d = serve.page_dir
    old = (datetime.now().astimezone() - timedelta(minutes=3)).isoformat(
        timespec="seconds"
    )
    comment = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Did this reach anyone?",
            "ts": old,
        },
    )
    page = open_page(browser, url)
    page.keyboard.press("c")
    workflow = page.locator(
        f'.lf-thread[data-id="{comment["id"]}"] .lf-msg[data-mid="{comment["id"]}"] > .lf-msg-head .lf-msg-sending'
    )
    expect(workflow).to_have_text("Waiting for pickup")
    expect(workflow).to_have_attribute("title", "Waiting for pickup")


def test_a_message_workflow_changes_phase_in_place_and_then_stands_still(
    browser, serve
):
    """A phase change updates message metadata without moving or replacing it.

    The workflow belongs beside the outgoing message's relative time. Heartbeats leave
    it alone, while a semantic transition changes its words in place.
    Re-inserting the node would lose its identity and could replay presentation."""
    url = serve(LONG_PAGE)
    d = serve.page_dir
    comment = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Did this reach anyone?",
        },
    )
    record_claim(d)
    page = open_page(browser, url)
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    thread = page.locator(f'.lf-thread[data-id="{comment["id"]}"]')
    workflow = thread.locator(
        f'.lf-msg[data-mid="{comment["id"]}"] > .lf-msg-head .lf-msg-sending'
    )
    thread.locator(".lf-thread-summary").click()
    expect(workflow).to_be_visible()
    expect(workflow).to_have_text("Sent")
    assert workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    )
    expect(workflow.locator("time")).to_have_count(0)
    expect(thread.locator(":scope > .lf-msg-sending")).to_have_count(0)
    workflow.evaluate(
        """node => {
          node.dataset.identityProbe = 'kept';
          window.__workflowMoves = 0;
          new MutationObserver((records) => {
            for (const record of records)
              if ([...record.removedNodes].includes(node)) window.__workflowMoves += 1;
          }).observe(node.parentElement, { childList: true });
        }"""
    )
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(transaction, [comment])
    told(page)
    expect(workflow).to_have_text("Picked up")
    expect(thread.locator(".lf-thread-status")).to_have_text("Picked up")
    active = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(d),
            comment["id"],
            "comparing the replacement against every narrow thread surface",
        ],
    )
    assert active.exit_code == 0, active.output
    page.set_viewport_size({"width": 340, "height": 800})
    told(page)
    expect(workflow).to_have_text("Working")
    expect(workflow).to_have_attribute(
        "title",
        "Working · comparing the replacement against every narrow thread surface",
    )
    header_reading = workflow.evaluate(
        """node => {
          const head = node.closest('.lf-msg-head');
          const author = head.querySelector(':scope > b');
          const metadata = head.querySelector(':scope > .lf-msg-meta');
          const time = metadata.querySelector(':scope > time');
          const contains = (outer, inner) => {
            const bounds = outer.getBoundingClientRect();
            const part = inner.getBoundingClientRect();
            return part.width > 0 && part.height > 0
              && part.left >= bounds.left - 0.5 && part.right <= bounds.right + 0.5;
          };
          return {
            authorVisible: contains(head, author),
            timeVisible: contains(head, time) && contains(metadata, time),
            timeFixed: getComputedStyle(time).flexShrink === '0',
          };
        }"""
    )
    assert all(header_reading.values()), header_reading
    ticked(page)
    ticked(page)
    expect(workflow).to_have_attribute("data-identity-probe", "kept")
    assert page.evaluate("() => window.__workflowMoves") == 0
    assert (
        workflow.evaluate("node => node.getAnimations({ subtree: true }).length") == 0
    )


def test_an_exact_workflow_reports_stale_work_beside_a_live_page_claim(
    browser, serve, tmp_path
):
    """A stale exact-input workflow says so beside its message even while a fresh
    start on the page's own task keeps the banner working. Starting the move again
    restores Working; a closed turn matters only when it belongs to the session that
    started it."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p1", "Paragraph 1.")]))
    d = serve.page_dir
    held = next(e for e in events_model.read_events(d) if e["kind"] == "comment")["id"]
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    work_line = page.locator(
        f'.lf-thread[data-id="{held}"] .lf-msg[data-mid="{held}"] > .lf-msg-head .lf-msg-sending'
    )
    work_button = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    held_thread = page.locator(f'.lf-thread[data-id="{held}"]')

    def claim(claim_ts, session="s"):
        """A start on the comment last renewed whenever, beside a start on the page's
        own task made now."""
        declare_work(
            d,
            "reading the reconnect traces",
            item=held,
            ts=claim_ts,
            agent="Claude",
            session=session,
            turn="turn-1",
        )
        declare_work(d, "rerunning the failing shard")
        told(page)

    claim(cleanup_model.now_iso())
    # A claim somebody is keeping says nothing about silence.
    expect(work_line).to_have_count(1)
    expect(work_line).to_have_text("Working")
    expect(work_button).to_have_count(1)
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")

    quiet_ts = (datetime.now().astimezone() - timedelta(minutes=40)).isoformat(
        timespec="seconds"
    )
    claim(quiet_ts)
    expect(held_thread.locator(".lf-thread-status")).to_have_text("Update stale")
    # The page's own line is as fresh as it was, which is the whole case: this is one
    # claim going quiet beside a live one, not a page that has gone quiet all over.
    expect(page.locator(".lf-status-detail")).to_have_text(
        re.compile(r"^\s*Claude is working — rerunning the failing shard")
    )
    expect(work_line).to_have_text("Update stale")
    expect(work_line).to_have_attribute(
        "title", "Update stale · reading the reconnect traces"
    )
    expect(work_line.locator("time")).to_have_count(0)
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(work_button).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    assert held_thread.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    expect(work_line).to_have_css("color", token_colour(page, "--muted"))

    # The exact claim is stale when its own turn has ended, even while the newer page
    # declaration remains active.
    record_claim(
        d,
        id="s",
        turn_closed=(datetime.now().astimezone() - timedelta(minutes=5)).isoformat(
            timespec="seconds"
        ),
    )
    claim(
        (datetime.now().astimezone() - timedelta(minutes=6)).isoformat(
            timespec="seconds"
        )
    )
    expect(page.locator(".lf-status-detail")).to_have_text(
        re.compile(r"^\s*Claude is working — rerunning the failing shard")
    )
    expect(work_line).to_have_text("Update stale")
    expect(work_line.locator("time")).to_have_count(0)
    assert work_line.evaluate("node => getComputedStyle(node).color") == token_colour(
        page, "--muted"
    )

    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )

    # Turn closure belongs to one exact session. When a Codex watcher task holds the
    # page, its turn ending is no evidence that the page task, which wrote this claim,
    # has abandoned it.
    record_claim(
        d,
        id="watcher",
        turn_closed=(datetime.now().astimezone() - timedelta(minutes=5)).isoformat(
            timespec="seconds"
        ),
    )
    claim(
        (datetime.now().astimezone() - timedelta(minutes=6)).isoformat(
            timespec="seconds"
        ),
        session="page-task",
    )
    expect(work_line).to_have_text("Working")
    expect(work_line.locator("time")).to_have_count(0)
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")

    # And it goes when the claim is kept again, so the word tracks the claim rather
    # than latching on the first time it is late.
    record_claim(d, id="s")
    claim(cleanup_model.now_iso())
    expect(work_line).to_have_text("Working")
    expect(work_line).to_have_count(1)
    expect(held_thread).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")
    # The semantic Target button carries the workflow; the thread card does not repeat it
    # as a decorative gutter in either presentation.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    work_button.click()
    inline = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{held}"]')
    expect(inline).to_be_visible()
    expect(inline).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    assert inline.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    claim(quiet_ts)
    expect(held_thread.locator(".lf-thread-status")).to_have_text("Update stale")
    expect(inline.locator(".lf-msg-sending")).to_have_text("Update stale")
    expect(inline).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    assert inline.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    expect(inline.locator(".lf-msg-sending")).to_have_css(
        "color", token_colour(page, "--muted")
    )


def test_the_tab_wears_what_the_banner_says(browser, serve, tmp_path, dead_pid):
    """The judgment's third seat, and the only one a user with six leaves open in a
    row of tabs can see without opening any. The mark is the vendored icon.svg and the
    runtime paints the element it declares in whatever colour the dot is wearing, so the
    tab and the banner are one fact read twice: a palette written out again for the tab
    would be free to drift from the theme the day a project overrode a token, and drift
    silently, since a tab nobody is watching closely is exactly the case this is for.

    What a copy does with all of it is the export section's
    (test_a_copy_wears_the_mark_and_claims_no_session)."""
    page = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir

    def tone(want, why):
        try:
            return page.wait_for_function(TAB_TONE, arg=want).json_value()
        except PlaywrightTimeout:
            # The console with it: a mark the runtime refuses reads here as a tab with
            # no tone on it, and the reason it refused is the only thing that says why.
            found = page.evaluate(TAB_AND_DOT, want)
            pytest.fail(
                f"the tab never said {why} as the banner does: {found}\n"
                + shown(page.lf_errors)
            )

    def declare(state, **status):
        cleanup_model.write_json(
            d / "status.json",
            {"state": state, "ts": cleanup_model.now_iso(), **status},
        )
        told(page)

    declare_work(d, "Writing the page")
    told(page)
    working = tone("working", "working")
    end_work(d)
    declare("waiting")
    with live_watcher(d, page):
        awaits = tone("listening", "awaits")
    # The distinctness is the half agreement alone can't prove: a tab painted once and
    # never again agrees with a dot that never moved either, and the two states a user
    # is choosing between — this page wants me, that one is busy — are exactly the pair
    # that would collapse.
    assert awaits != working, (
        f"a page awaiting its user wears the same tab as one that is working ({awaits})"
    )

    # The claimant is gone, so nothing is behind the page: grey in the banner, and grey
    # in the tab, which is the whole of what the user can see of it from a tab strip.
    record_claim(d, id="s", pid=dead_pid)
    unheld = tone("", "unheld")
    assert unheld not in (
        working,
        awaits,
    ), f"a page nothing holds wears a tab claiming a session ({unheld})"

    # And the mark itself is an image the browser will render, which is the one thing
    # a string comparison above cannot say: an SVG this file mangles decodes to nothing
    # and shows as a blank tab, with no error anywhere to find it by.
    page.evaluate("""() => {
        const img = new Image();
        globalThis.__lfTabMarkWidth = null;
        globalThis.__lfTabMarkImage = img;
        const done = (width) => {
          globalThis.__lfTabMarkWidth = width;
          delete globalThis.__lfTabMarkImage;
        };
        img.onload = () => done(img.naturalWidth);
        img.onerror = () => done(0);
        img.src = document.querySelector('link[rel=icon]').getAttribute('href');
    }""")
    page.wait_for_function(
        "() => globalThis.__lfTabMarkWidth !== null",
        timeout=render_checks_model.SERVED_TIMEOUT_MS,
    )
    drawn = page.evaluate("() => globalThis.__lfTabMarkWidth")
    assert drawn > 0, "the tab's mark is not an image the browser can decode"
