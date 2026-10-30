"""What the page says the agent is doing: the floating panel's leaf and field, the tab's
mark, and each message's workflow, dated by the server's clock."""

import os
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare,
    declare_work,
    end_work,
    record_claim,
    working,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_layout import token_colour
from render_cases_navigation import TAB_AND_DOT, TAB_TONE, live_watcher
from render_harness import (
    LONG_PAGE,
    open_page,
    open_threads,
    panel_settled,
    panel_view,
    shown,
    ticked,
    told,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf import service as service_model
from leaf import state as cleanup_model

pytestmark = pytest.mark.shifts_unsurveyed

# Where the leaf's peek says the status's whole sentence.
PEEK = ".lf-fp-peek"
LEAF_DOT = ".lf-fp-leaf .lf-dot"


def expect_status_says(page, words):
    """Point at the leaf and read the status's whole sentence in its peek, which keeps
    what it opened with for one exposure (floating-panel.js), so the pointer leaves
    again and the next reading is a new exposure."""
    page.locator(".lf-fp-leaf").hover()
    expect(page.locator(PEEK)).to_have_text(words)
    page.mouse.move(5, 5)
    expect(page.locator(PEEK)).to_be_hidden()


def workflow_of(scope, message):
    """The workflow line on `message`'s head where `scope` draws it."""
    return scope.locator(
        f'.lf-msg[data-event="{message}"] > .lf-msg-head .lf-msg-sending'
    )


def thread_row_says(page, thread, resolved=False):
    """Open the panel's Threads and return what `thread`'s row says of where it stands,
    beside its name, among the open threads or, where `resolved`, under Resolved."""
    open_threads(page)
    state = "[data-resolved]" if resolved else ":not([data-resolved])"
    return page.locator(f'.lf-fp-thread[data-key="{thread}"]{state} .lf-fp-value')


def test_the_page_dates_a_claim_by_the_clock_that_wrote_it(browser, serve):
    """Every timestamp a seat reads out was written by the server; `Date.now()` is the
    machine holding the tab. A laptop an hour fast therefore called a claim made this
    minute an hour stale — on the leaf, on a roster row and under every question at
    once, always in the same direction, with nothing in the timestamp to give it away.
    The poll carries the server's own now, so the offset is measured rather than
    assumed.

    It is the user's clock that moves here, because that is the one of the two a page
    has to survive: the server writes the timestamps it later reads back and cannot
    disagree with itself, while the user's machine is not the page's to correct."""
    page = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir
    dot = page.locator(LEAF_DOT)

    def claim(detail):
        record_claim(d, id="s")
        declare_work(d, detail)
        told(page)

    claim("running the migration")
    expect_status_says(
        page,
        re.compile(r"^\s*running the migration \(just now\)\."),
    )

    # An hour fast. A fixed time rather than an installed clock, so the page's own
    # polling keeps running and the next reading is a real one.
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=1))
    # New words, so the line under test can only be one this user painted after the
    # clock moved: an unchanged sentence would pass on the render before it.
    claim("waiting on the shard")
    expect_status_says(
        page,
        re.compile(r"^\s*waiting on the shard \(just now\)\."),
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))


def test_a_thread_says_what_the_agent_is_doing_about_it(
    browser, serve, tmp_path, dead_pid
):
    """An exact message workflow says which user question the agent is working on,
    beside the leaf's account of the page as a whole.

    A user with three questions open and no replies under any of them cannot tell a
    question being worked from a question nobody has looked at, and the page holds the
    answer: the agent said so. What the log holds is what happened, so this is not in
    it — a sentence somebody rewrites every few minutes is a claim, painted as
    provisional news on the message while the answer is still owed.

    Nothing deletes the line directly. The agent's next reply answers the claim;
    resolution hides it while the thread is closed, and reopening reveals it
    again. The thread's view in the panel draws the line on its message, and Threads
    names the stage on the thread's row."""
    page = open_page(browser, serve(LONG_PAGE, comments=2))
    d = serve.page_dir
    comments = [e for e in events_model.read_events(d) if e["kind"] == "comment"]
    held, other = comments[0]["id"], comments[1]["id"]
    view = open_panel_thread(page, held)
    held_workflow = workflow_of(view, held)
    expect(view.locator(".lf-msg-sending")).to_have_count(1)
    expect(held_workflow).to_have_text(re.compile(r"^Queued for "))
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
    # Durable delivery into the open turn advances the exact same row in place.
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(transaction, [comments[0]])
    told(page)
    expect(held_workflow).to_have_text("Delivered")
    expect(held_workflow).to_have_attribute("data-identity-probe", "kept")

    # The agent finishes the earlier task and waits on the user.
    end_work(d)
    latent_waiting = CliRunner().invoke(cli_model.cli, ["page", "open", str(d)])
    assert latent_waiting.exit_code == 0, latent_waiting.output
    told(page)
    expect(held_workflow).to_have_text("Delivered")

    cleanup_model.close_session_turn("s")
    told(page)
    expect(held_workflow).to_have_text("Stopped")
    cleanup_model.open_session_turn("s")

    def start(item, line):
        started = CliRunner().invoke(
            cli_model.cli, ["task", "start", str(d), item, "--text", line]
        )
        assert started.exit_code == 0, started.output
        told(page)

    start(held, "reading the reconnect traces")
    # One line, on the thread it names: a mark that stood on every open thread would
    # say only that the agent is busy, which the leaf already says.
    expect(held_workflow).to_have_text("On it")
    expect(held_workflow).to_have_attribute(
        "title", "On it · reading the reconnect traces"
    )
    expect(held_workflow).to_have_attribute("data-identity-probe", "kept")
    expect(held_workflow).to_have_count(1)
    # The move's state is metadata on the exact outgoing message, closing that row
    # rather than taking a full-width row of its own.
    expect(view.locator(":scope > .lf-msg-sending")).to_have_count(0)
    assert held_workflow.evaluate(
        "node => node.parentElement.matches('.lf-msg-meta') "
        "&& node.previousElementSibling.matches('time')"
    )
    # Threads names the stage on each row, the held thread's and not the other's.
    expect(thread_row_says(page, held)).to_contain_text("On it")
    expect(thread_row_says(page, other)).to_contain_text("Queued for ")

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
    view = open_panel_thread(page, held)
    held_workflow = workflow_of(view, held)
    followup_workflow = workflow_of(view, followup["id"])
    expect(held_workflow).to_have_text("On it")
    expect(followup_workflow).to_have_text(re.compile(r"^Queued for "))
    expect(view.locator(":scope > .lf-msg-sending")).to_have_count(0)

    # A later start on the page's own task is not an answer to the thread, so the
    # thread's line stands.
    working(d, "drafting v2")
    told(page)
    expect(held_workflow).to_have_count(1)
    expect(held_workflow).to_have_attribute(
        "title", "On it · reading the reconnect traces"
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
    expect(view.locator(".lf-msg.agent")).to_have_count(1)
    expect(held_workflow).to_have_count(0)
    # The answer responds to the follow-up, whose line goes with it.
    expect(view.locator(".lf-msg-sending")).to_have_count(0)

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
    # No message carries this work, so the thread's row still says it.
    expect(thread_row_says(page, held)).to_contain_text("On it")

    # A thread the user has closed asks nothing: its row no longer says the agent is
    # working on it.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": held})
    told(page)
    expect(thread_row_says(page, held, resolved=True)).not_to_contain_text("On it")

    # Reopening restores the task, which no reply ends. Its start goes with the page
    # claim it is part of: once nothing holds the page, the task is open but nothing
    # runs on it under a leaf that says nobody is there.
    append_carried_log_record(
        d, {"kind": "unresolve", "author": "user", "parent": held}
    )
    told(page)
    expect(thread_row_says(page, held)).to_contain_text("On it")
    record_claim(d, id="s", pid=dead_pid)
    told(page)
    expect(thread_row_says(page, held)).to_contain_text("Still to do")


def test_the_leaf_and_all_pages_say_the_served_activity(browser, serve, other_leaf):
    """The served activity reaches the leaf's name, its peek and dot, and this page's
    row in All pages. What each says for every reading is
    `tests/runtime/activity-words.test.mjs`'s, and which reading a log and claim come
    to is `tests/model/test_activity.py`'s."""
    page = open_page(browser, serve(LONG_PAGE))
    record_claim(serve.page_dir, id="s", pid=os.getpid(), agent="Claude")
    declare_work(serve.page_dir, "Writing the page")
    told(page)
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", "Page menu · Writing the page"
    )
    expect_status_says(
        page,
        re.compile(r"^\s*Writing the page \(just now\)\."),
    )
    expect(page.locator(LEAF_DOT)).to_have_class(re.compile(r"\bworking\b"))
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    this_page = page.locator(f"{panel_view('leaves')} .lf-fp-page").first
    expect(this_page).to_contain_text("This page")
    # The row names the page; what its agent is doing is said whole on hover.
    expect(this_page).to_have_attribute("title", re.compile("\nWriting the page$"))


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
    workflow = workflow_of(open_panel_thread(page, comment["id"]), comment["id"])
    expect(workflow).to_have_text(re.compile(r"^Still queued for "))
    expect(workflow).to_have_attribute("title", re.compile(r"^Still queued for "))


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
    thread = open_panel_thread(page, comment["id"])
    workflow = workflow_of(thread, comment["id"])
    expect(workflow).to_be_visible()
    expect(workflow).to_have_text(re.compile(r"^Queued for "))
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
    expect(workflow).to_have_text("Delivered")
    active = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(d),
            comment["id"],
            "--text",
            "comparing the replacement against every narrow thread surface",
        ],
    )
    assert active.exit_code == 0, active.output
    page.set_viewport_size({"width": 340, "height": 800})
    told(page)
    expect(workflow).to_have_text("On it")
    expect(workflow).to_have_attribute(
        "title",
        "On it · comparing the replacement against every narrow thread surface",
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
    start on the page's own task keeps the leaf working. Starting the move again
    restores On it; a closed turn matters only when it belongs to the session that
    started it."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p1", "Paragraph 1.")]))
    d = serve.page_dir
    held = next(e for e in events_model.read_events(d) if e["kind"] == "comment")["id"]
    work_line = workflow_of(open_panel_thread(page, held), held)
    work_button = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    page_work = re.compile(r"^\s*rerunning the failing shard")

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
    expect(work_line).to_have_text("On it")
    expect(work_button).to_have_count(1)
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")

    quiet_ts = (datetime.now().astimezone() - timedelta(minutes=40)).isoformat(
        timespec="seconds"
    )
    claim(quiet_ts)
    expect(work_line).to_have_text("Gone quiet")
    expect(work_line).to_have_attribute(
        "title", "Gone quiet · reading the reconnect traces"
    )
    expect(work_line.locator("time")).to_have_count(0)
    expect(work_button).not_to_have_attribute(
        "data-lf-agent-workflow", re.compile(".+")
    )
    expect(work_line).to_have_css("color", token_colour(page, "--muted"))
    # The page's own line is as fresh as it was, which is the whole case: this is one
    # claim going quiet beside a live one, not a page that has gone quiet all over.
    expect_status_says(page, page_work)
    expect(thread_row_says(page, held)).to_contain_text("Gone quiet")

    # The exact claim is stale when its own turn has ended, even while the newer page
    # declaration remains active.
    work_line = workflow_of(open_panel_thread(page, held), held)
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
    expect(work_line).to_have_text("Gone quiet")
    expect(work_line.locator("time")).to_have_count(0)
    assert work_line.evaluate("node => getComputedStyle(node).color") == token_colour(
        page, "--muted"
    )
    expect_status_says(page, page_work)

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
    expect(work_line).to_have_text("On it")
    expect(work_line.locator("time")).to_have_count(0)
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")

    # And it goes when the claim is kept again, so the word tracks the claim rather
    # than latching on the first time it is late.
    record_claim(d, id="s")
    claim(cleanup_model.now_iso())
    expect(work_line).to_have_text("On it")
    expect(work_line).to_have_count(1)
    expect(work_button).to_have_attribute("data-lf-agent-workflow", "working")
    # The semantic Target button carries the workflow; the thread card it opens does
    # not repeat it as a decorative gutter.
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    work_button.click()
    inline = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{held}"]')
    expect(inline).to_be_visible()
    expect(inline).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    assert inline.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    claim(quiet_ts)
    expect(inline.locator(".lf-msg-sending")).to_have_text("Gone quiet")
    expect(inline).not_to_have_attribute("data-lf-agent-workflow", re.compile(".+"))
    assert inline.evaluate("node => getComputedStyle(node).boxShadow") == "none"
    expect(inline.locator(".lf-msg-sending")).to_have_css(
        "color", token_colour(page, "--muted")
    )


def test_the_tab_wears_what_the_leaf_says(browser, serve, tmp_path, dead_pid):
    """The judgment's third seat, and the only one a user with six leaves open in a
    row of tabs can see without opening any. The mark is the vendored icon.svg and the
    runtime paints the element it declares in whatever colour the dot is wearing, so the
    tab and the leaf are one fact read twice: a palette written out again for the tab
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
                f"the tab never said {why} as the leaf does: {found}\n"
                + shown(page.lf_errors)
            )

    declare_work(d, "Writing the page")
    told(page)
    working = tone("working", "working")
    end_work(d)
    declare(d)
    told(page)
    with live_watcher(d, page):
        awaits = tone("listening", "awaits")
    # The distinctness is the half agreement alone can't prove: a tab painted once and
    # never again agrees with a dot that never moved either, and the two states a user
    # is choosing between — this page wants me, that one is busy — are exactly the pair
    # that would collapse.
    assert awaits != working, (
        f"a page awaiting its user wears the same tab as one that is working ({awaits})"
    )

    # The claimant is gone, so nothing is behind the page: grey on the leaf, and grey
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
