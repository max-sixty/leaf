"""Initial presentation, polling, presence, and projected-data tests."""

import json
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare_work,
    end_work,
    record_claim,
    wait_for,
)
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import user_views as user_views_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.served_state.reading import page_reading, source_readings
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_navigation import (
    data_projection_page,
    live_watcher,
)
from render_harness import (
    FEATURE_GALLERY,
    LONG_PAGE,
    TOKEN,
    _traffic,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    refuse,
    round_trip,
    select_words,
    sending,
    ticked,
    told,
    watched,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_startup import HELD_KEYS_PAGE, _hold_startup


def test_the_gallery_embeds_an_ordinary_stamped_page(browser, serve):
    """Authored iframe markup opens a durable version rather than a practice copy."""
    url = live_url(serve(FEATURE_GALLERY))
    page = open_page(browser, url + "#bg-durable-embedding")
    expect(page.locator("#bg-durable-embedding")).to_be_in_viewport()
    page.locator("#bg-durable-frame-open").click()
    frame = page.locator("#bg-durable-frame").element_handle().content_frame()
    wait_until_ready(frame)
    assert urlparse(frame.url).path == "/versions/v2.html"
    expect(frame.locator("#bg-choice-ask h3")).to_have_text(
        "Which map should the sample team carry?"
    )
    frame.locator(".lf-threads-toggle").click()
    expect(frame.locator(".lf-thread-panel")).to_be_visible()
    frame.goto(frame.url)
    wait_until_ready(frame)
    assert urlparse(frame.url).path == "/versions/v2.html"
    expect(frame.locator("#bg-choice-ask h3")).to_have_text(
        "Which map should the sample team carry?"
    )


def test_a_preview_names_its_checkout_and_copies_diagnostics(browser, serve):
    preview = {
        "kind": "example",
        "example": "triage-board",
        "checkout": "fb77",
        "commit": "26499ea1abcd",
        "dirty": True,
        "committed": (datetime.now().astimezone() - timedelta(days=3)).isoformat(
            timespec="seconds"
        ),
        "interaction": "user",
        "started": "2026-08-31T12:00:00+00:00",
    }
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(
        browser,
        serve(leaf_page("Preview", "<h1>Preview</h1>"), preview=preview),
        context=context,
    )
    badge = page.locator(".lf-preview")
    expect(badge).to_have_text("User · fb77@26499ea1abcd+ · 3d ago")
    expect(badge).to_have_attribute("aria-label", "Copy preview diagnostics")

    page.get_by_role("button", name="More page controls", exact=True).click()
    expect(badge).to_be_visible()
    badge.click()
    expect(page.locator(".lf-notice")).to_have_text("Copied preview diagnostics")
    expect(page.locator(".lf-notice")).to_have_text("Copied preview diagnostics")
    expect(page.locator(".lf-notice")).to_be_visible()
    diagnostics = page.evaluate("() => navigator.clipboard.readText()")
    assert "example: triage-board" in diagnostics
    assert "checkout: fb77" in diagnostics
    assert "interaction: user" in diagnostics
    assert "commit: 26499ea1abcd" in diagnostics
    assert "dirty: true" in diagnostics
    assert f"committed: {preview['committed']}" in diagnostics
    assert "layer generation:" in diagnostics
    assert "layer fingerprint: sha256:" in diagnostics
    assert "revision: 1" in diagnostics
    assert "event sequence: 1" in diagnostics
    assert "?t=" not in diagnostics
    page.close()

    ordinary = open_page(
        browser,
        serve(leaf_page("Ordinary", "<h1>Ordinary</h1>")),
        context=context,
    )
    expect(ordinary.locator(".lf-preview")).to_have_count(0)
    layer = json.loads((serve.page_dir / "registry.json").read_text())["$layer"]
    producer = layer.get("producer", {})
    identity = (
        producer["commit"][:8]
        if producer.get("commit")
        else "sha256:" + layer["fingerprint"].removeprefix("sha256:")[:12]
    )
    reference = ordinary.locator(".lf-layer-reference")
    dated = producer.get("committed") or producer.get("installed")
    expect(reference).to_have_text(
        re.compile(
            rf"^Leaf {re.escape(identity)}{re.escape('+') if producer.get('dirty') else ''}"
            + (r" · (just now|\d+[mhd] ago)$" if dated else "$")
        )
    )
    expect(reference.locator("code")).to_have_text(
        f"{identity}{'+' if producer.get('dirty') else ''}"
    )
    ordinary.get_by_role("button", name="More page controls", exact=True).click()
    expect(reference).to_be_visible()
    reference.click()
    expect(ordinary.locator(".lf-notice")).to_have_text("Copied Leaf version")
    diagnostics = ordinary.evaluate("() => navigator.clipboard.readText()")
    assert f"fingerprint: {layer['fingerprint']}" in diagnostics
    if producer.get("commit"):
        assert f"commit: {producer['commit']}" in diagnostics
    if producer.get("committed"):
        assert f"committed: {producer['committed']}" in diagnostics


def test_a_page_that_never_presents_lets_its_held_keys_go(browser, serve):
    """The hold is for a page on its way. One still unpresented ten seconds in has
    faulted, so what was held is dropped and later presses reach the page as they come
    rather than waiting on a presentation that is not arriving."""
    url = serve(HELD_KEYS_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, _ = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the runtime module")
    page.evaluate(
        "() => { window.heard = [];"
        " document.addEventListener('keydown', (e) => heard.push(e.key)); }"
    )
    page.keyboard.press("t")
    echo = page.locator(".lf-held-keys")
    expect(echo).to_be_visible()
    assert page.evaluate("heard") == [], "the positive control: the press was held"

    expect(echo).to_have_count(0)
    page.keyboard.press("x")
    assert page.evaluate("heard") == ["x"]


def test_opt_in_page_interface_joins_initial_widget_settlement(browser, serve):
    """Page interface preparation holds the first widget upgrade."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.add_init_script(
        """
        document.addEventListener('lf-page-interface', event => {
          event.detail.present(new Promise(resolve => {
            window.releaseHeldPageInterface = resolve;
          }));
        });
        """
    )
    page.goto(
        serve(leaf_page("Held interface", "<h1>Held interface</h1>")),
        wait_until="load",
    )
    page.wait_for_function("() => window.releaseHeldPageInterface !== undefined")
    page.evaluate(
        """async () => {
          const {nextFrame} = await window.__lfRuntimeImport('/runtime/rendering.js');
          await new Promise(resolve => nextFrame(() => nextFrame(resolve)));
        }"""
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-upgraded", "1")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    page.evaluate("releaseHeldPageInterface()")
    wait_until_ready(page)


def test_more_than_six_live_documents_share_an_origin_without_stalling(browser, serve):
    """Live feeds leave HTTP slots available for startup, gestures and revisions."""
    url = live_url(serve(LONG_PAGE))
    with browser.new_context() as context:
        pages = [open_page(browser, url, context=context) for _ in range(8)]
        last = pages[-1]
        write(page_comment(last), "All eight views are live.")
        with sending(last, "the eighth view's comment"):
            last.locator(".lf-page-comment-card .lf-general .lf-compose-submit").click()
        assert any(
            event.get("text") == "All eight views are live."
            for event in events_model.read_events(serve.page_dir)
        )
        (serve.page_dir / "index.html").write_text(
            LONG_PAGE.replace(">Long<", ">Updated across tabs<")
        )
        for page in pages:
            told(page)
            expect(page.locator("#t")).to_have_text("Updated across tabs")


@pytest.mark.parametrize("answer", ["ready", "offline"])
def test_slow_history_keeps_decisions_safe_and_status_honest(browser, serve, answer):
    """Presentation is not a state answer; every Decision route needs the same reading."""
    source = leaf_page(
        "Slow decision",
        '<h1>Slow decision</h1><lf-ask id="decision"><h2>Proceed?</h2>'
        '<lf-options id="pick" choose><lf-option id="yes">Proceed</lf-option>'
        '<lf-option id="no">Wait</lf-option></lf-options></lf-ask>',
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    posts = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            and request.post_data_json["kind"] == "action"
            else None
        ),
    )
    page.goto(serve(source), wait_until="load")
    holding(page, held, 1, "the unanswered private-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    # Cross the former ten-second presentation deadline with a read still in flight.
    # This is the interval that used to invent an offline answer and release choices.
    page.wait_for_function("performance.now() > 11_000", timeout=15_000)
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-status-text")).to_have_text("Loading saved state…")
    assert len(held) == 1
    if answer == "ready":
        # An ordinary error in a usable page must not start recovery that could
        # reload the document and discard an early comment while history waits.
        page.evaluate("setTimeout(() => { throw new Error('post-upgrade fault'); })")
        page.wait_for_timeout(50)
        expect(page.locator("html")).not_to_have_attribute("data-lf-startup-error")
        expect(page.get_by_text("Leaf couldn't start", exact=False)).to_have_count(0)
        consume_browser_errors(page, "post-upgrade fault")
    first = page.locator("#pick .lf-pick").first
    second = page.locator("#pick .lf-pick").nth(1)
    expect(first).to_have_attribute("aria-disabled", "true")
    first.focus()
    page.keyboard.press("Space")
    second.dispatch_event("click")
    page.keyboard.press("1")
    expect(page.locator(".lf-held-keys kbd")).to_have_text("1")
    expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
    expect(page.locator("#no")).not_to_have_attribute("chosen", "")
    assert posts == []
    page.unroute("**/api/state*")
    if answer == "offline":
        page.route("**/api/state*", refuse)
        for route in held:
            refuse(route)
        expect(page.locator(".lf-status-text")).to_contain_text("Server offline")
        expect(page.locator(".lf-held-keys")).to_have_count(0)
        expect(first).to_have_attribute("aria-disabled", "true")
        expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("Proceed")
        first.focus()
        page.keyboard.press("1")
        page.keyboard.press("Space")
        second.dispatch_event("click")
        expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
        expect(page.locator("#no")).not_to_have_attribute("chosen", "")
        assert posts == []
        page.unroute("**/api/state*")
        wait_until_ready(page, timeout_ms=15_000)
        first.focus()
        page.keyboard.press("1")
    else:
        for route in held:
            route.continue_()
        wait_until_ready(page, timeout_ms=15_000)
    expect(page.locator("#yes")).to_have_attribute("chosen", "")
    round_trip(page)
    assert len(posts) == 1, "the held or fresh digit should send exactly once"
    first.focus()
    page.keyboard.press("Space")
    round_trip(page)
    second.click()
    round_trip(page)
    assert [post["detail"] for post in posts] == [
        {"value": ["yes"]},
        {"value": []},
        {"value": ["no"]},
    ]


def test_offline_reaction_waits_for_its_saved_state(browser, serve):
    """An unknown saved state cannot invent an add; recovery toggles the actual saved event."""
    source = leaf_page(
        "Saved reaction", '<h1>Saved reaction</h1><button id="target">A target</button>'
    )
    saved = {
        "id": "saved-reaction",
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "keep",
        "anchor": {"section": "target"},
    }
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    posts = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            else None
        ),
    )
    page.route("**/api/state*", refuse)
    page.goto(serve(source, events=[saved]), wait_until="load")
    expect(page.locator(".lf-status-text")).to_contain_text("Server offline")
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    assert posts == []
    select_words(page, "#target")
    page.keyboard.press("c")
    page.keyboard.press("Tab")
    chip = page.locator('.lf-response-options .lf-react[data-token="keep"]')
    expect(chip).to_have_attribute("aria-disabled", "true")
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("react")
    chip.dispatch_event("click")
    chip.focus()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("choose")
    page.keyboard.press("Space")
    assert posts == []
    page.keyboard.press("Escape")
    page.unroute("**/api/state*")
    wait_until_ready(page, timeout_ms=15_000)
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    round_trip(page)
    assert [(post["kind"], post.get("undoes")) for post in posts] == [
        ("undo", "saved-reaction")
    ]


def test_a_page_hears_again_when_its_server_comes_back(browser, serve):
    """A server is stopped and started under an open tab whenever its layer is
    re-vendored, and the tab finds the new one on its own: its freshness read fails
    with the old server, and the browser keeps asking. The page says the server is
    gone while it is, and reads again when the server comes back, because the last
    thing it knew about the server is from before the silence."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    status = page.locator(".lf-status-detail")
    port = serve.httpd.server_address[1]
    next(server for server in serve.servers if server.httpd is serve.httpd).close()
    expect(status).to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )

    server = hosting_model.TemporaryPageServer(
        serve.page_dir, token=TOKEN, port=port
    ).start()
    serve.servers.append(server)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Back."},
    )
    told(page)
    expect(page.locator(".lf-thread", has_text="Back.")).to_have_count(1)
    expect(status).not_to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )
    # The requests that failed while the server was down are the one thing the
    # console may hold; a page fault of the runtime's own would say something else.
    consume_browser_errors(page, "net::ERR")


def test_banner_reports_whether_anyone_is_attending(browser, serve, tmp_path, dead_pid):
    """The banner may claim no more than the page directory can prove. A watch that
    has stopped must read differently from a watch with nothing to report, because
    otherwise the user's only way to tell them apart is to ask.

    And a page nothing is behind must read differently from either, without reading as
    a fault: a persistent page spends the night that way, so the words are the plain
    computed fact and the dot is not the amber it wears for a session falling behind."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    d = serve.page_dir
    # The banner's own dot: the leaves panel mirrors this page as a row, so a
    # bare .lf-dot resolves to that row's copy too.
    text, dot = page.locator(".lf-status-detail"), page.locator(".lf-banner .lf-dot")
    summary = page.locator(".lf-status-text")
    UNHELD = (
        "No session holds this page. Updates are saved."
        " It picks up again when a session does."
    )

    def declare(
        state,
        detail="",
        *,
        agent="Claude",
        quiet_for=0,
        turn_ended=None,
        session_pid=None,
        claimed=True,
        stream=None,
    ):
        """`quiet_for` ages the declaration; `turn_ended` says how long ago the Stop
        hook watched the turn behind it end. Separate seconds, because the case the
        second exists for is a start that is not old at all. `working` is a start on
        the page's own task, in the claimant's voice, with a `waiting` status of the
        same age beside it; anything else ends that task and writes the status."""
        ts = datetime.now().astimezone() - timedelta(seconds=quiet_for)
        end_work(d)
        status = {
            "state": "waiting" if state == "working" else state,
            "detail": "" if state == "working" else detail,
            "ts": ts.isoformat(timespec="seconds"),
        }
        if stream is not None:
            # What a transport watched for itself, written the way an App Server
            # observer writes it: bound to this session and its live turn.
            status["stream"] = {
                "activity": {
                    "session": "s",
                    "turn": "turn-live",
                    "ts": ts.isoformat(timespec="seconds"),
                    "after": (
                        events_model.read_events(d)[-1]["seq"]
                        if events_model.read_events(d)
                        else 0
                    ),
                }
                | stream
            }
        if claimed:
            record_claim(
                d,
                id="s",
                pid=session_pid or os.getpid(),
                agent=agent,
                turn_closed=None
                if turn_ended is None
                else (
                    datetime.now().astimezone() - timedelta(seconds=turn_ended)
                ).isoformat(timespec="seconds"),
            )
        else:
            service_model.claim_path(d).unlink(missing_ok=True)
        cleanup_model.write_json(d / "status.json", status)
        if state == "working":
            declare_work(
                d,
                detail,
                ts=ts.isoformat(timespec="seconds"),
                **({"session": "s"} if claimed else {}),
            )
        told(page)

    declare("working", "revising the plan")
    expect(summary).to_have_text("Claude working — revising the plan")
    # The row's account of the agent's side is the queue count, not the delivery
    # count the disclosure keeps.
    expect(page.locator(".lf-status-queues")).to_have_text("Tasks: 2")
    expect(text).to_have_text(
        re.compile(
            r"^\s*Claude is working — revising the plan \(.+\)\. 1 response owed on updates awaiting delivery\."
            r" Waiting on Claude: 1 reply, 1 to-do \(Work on the page\)\.\s*$"
        )
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))
    # A claim still believed but minutes old is dated on the row itself, so a long step
    # and a quiet agent read differently without opening the disclosure.
    declare("working", "revising the plan", quiet_for=5 * 60)
    expect(summary).to_have_text("Claude working · 5m ago — revising the plan")
    expect(dot).to_have_class(re.compile(r"\bworking\b"))
    declare("working", "revising the plan")
    expect(summary).to_have_text("Claude working — revising the plan")

    [first_comment] = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(transaction, [first_comment], phase="queued")
    told(page)
    expect(text).to_have_text(
        re.compile(
            r"^\s*Claude is working — revising the plan \(.+\)\. "
            r"1 response owed on queued updates\. Waiting on Claude: 1 reply, 1 to-do \(Work on the page\)\.\s*$"
        )
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))

    # Picked up into the claimant's open turn before the agent has said anything: the
    # page is working, and the row names what the turn picked up rather than a bare
    # "working", while the disclosure says the agent's own words are still to come.
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(
            transaction, [first_comment], phase="opened", session="s", turn="turn-1"
        )
    declare("waiting", "your read on the plan")
    expect(summary).to_have_text("Claude working — picked up my comment")
    expect(text).to_have_text(
        re.compile(
            r"^\s*Claude picked up my comment and hasn't said what it's doing yet"
        )
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))

    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": first_comment["id"],
            "responds": first_comment["id"],
            "text": "Handled before the next turn.",
        },
    )
    with live_watcher(d, page):
        declare("working", "revising the plan")
        append_carried_log_record(
            d, {"kind": "comment", "author": "user", "text": "A later update."}
        )
        told(page)
        # A newer user input keeps its own pending delivery while the page's fresh
        # work declaration continues to describe what the agent is doing overall.
        expect(text).to_have_text(
            re.compile(
                r"^\s*Claude is working — revising the plan \(.+\)\. "
                r"1 response owed on updates awaiting delivery\. Waiting on Claude: 1 reply, 1 to-do \(Work on the page\)\.\s*$"
            )
        )
        expect(dot).to_have_class(re.compile(r"\bworking\b"))

        expect(summary).to_have_text("Claude working — revising the plan")

        # A transport that can watch the session's own steps reports one, and the agent
        # says what the work is. The row keeps the sentence written for the user; the
        # step stands beside it in the disclosure, proving the session is still moving.
        declare(
            "working",
            "revising the plan",
            stream={"kind": "tool", "detail": "Running the tests"},
        )
        expect(summary).to_have_text("Claude using a tool — revising the plan")
        expect(text).to_have_text(
            re.compile(
                r"^\s*Claude is using a tool — revising the plan \(.+\) · "
                r"Running the tests\. 1 response owed on updates awaiting delivery\. Waiting on Claude: 1 reply, 1 to-do \(Work on the page\)\.\s*$"
            )
        )
        expect(dot).to_have_class(re.compile(r"\bworking\b"))

        for stream, words in [
            ({"kind": "thinking"}, "thinking"),
            ({"kind": "awaiting_input"}, "waiting for input"),
            ({"kind": "awaiting_approval"}, "waiting for approval"),
            ({"kind": "replying"}, "replying"),
        ]:
            declare("working", "revising the plan", stream=stream)
            expect(summary).to_have_text(f"Claude {words} — revising the plan")

        # A claim of work that has gone quiet is still a claim of work, and a live
        # watcher does not turn it into one. This read "Claude awaits — select text to
        # comment" once, which invited the user to start something on a page already
        # mid-answer and dropped the only news it had: the agent had been holding the
        # question for twenty minutes and nothing on the page said so. The words are
        # the ones the branch with no watcher uses for the same silence, minus its
        # remedy — nobody needs to touch a terminal for a comment to reach a live wait.
        declare("working", "revising the plan", quiet_for=20 * 60)
        expect(text).to_have_text(
            "Claude last checked in 20m ago: revising the plan. Updates are saved."
            " Waiting on Claude: 1 reply, 1 to-do (Work on the page)."
        )
        expect(dot).to_have_class(re.compile(r"\baway\b"))

        expect(summary).to_have_text("Claude last checked in 20m ago")

        # The same silence reached by evidence rather than by the clock. A claim is
        # written by a model's turn, and a turn ends without running anything — so
        # nothing writes its close, and the page could only ever find an abandoned
        # claim by outwaiting the rope above. The Stop hook watches that ending, and a
        # claim written before it is one no later turn renewed across it. Dated by the
        # ending and not by the claim's own last word: "last checked
        # in just now" under an amber dot is the line arguing with the dot.
        declare("working", "revising the plan", quiet_for=6 * 60, turn_ended=5 * 60)
        expect(text).to_have_text(
            "Claude’s turn ended 5m ago: revising the plan."
            " Updates are saved. Waiting on Claude: 1 reply, 1 to-do (Work on the page)."
        )
        expect(dot).to_have_class(re.compile(r"\baway\b"))

        expect(summary).to_have_text("Claude’s turn ended 5m ago")

        # The agent's own last word about the work and the ending of the turn that
        # wrote it land in the same second, which is what an ordinary turn looks like:
        # written no later than the ending is written by the turn that ended, and
        # renewed by nothing after it.
        declare("working", "revising the plan", quiet_for=5 * 60, turn_ended=5 * 60)
        expect(text).to_have_text(
            "Claude’s turn ended 5m ago: revising the plan."
            " Updates are saved. Waiting on Claude: 1 reply, 1 to-do (Work on the page)."
        )

        # A turn that has only just ended still holds it. An agent that ends its turn
        # with work running can be back a minute later, woken by that work's result
        # or the user, and with no margin the page would report every such gap as
        # an abandonment and take it back again.
        declare("working", "revising the plan", quiet_for=60, turn_ended=30)
        expect(text).to_have_text(
            re.compile(r"^\s*Claude is working — revising the plan")
        )
        expect(dot).to_have_class(re.compile(r"\bworking\b"))

        # And a status written after the turn closed carries the claim past the ending
        # on its own, through the one command that writes both. The claim stops being
        # the closed turn's to answer for, and the rope above is what judges it from
        # there.
        declare("working", "revising the plan", quiet_for=60, turn_ended=5 * 60)
        expect(text).to_have_text(
            re.compile(r"^\s*Claude is working — revising the plan")
        )

        # What the page wants back, in the agent's words, where the user arrives.
        # The whole line is the tooltip too: it is the first thing on the row to be
        # clipped, and a narrow window must not be why the decision goes unread.
        declare("waiting", "pick a storage engine")
        expect(text).to_have_text(
            "Claude is listening — pick a storage engine. 1 response owed on updates awaiting delivery."
            " Waiting on Claude: 1 reply."
        )
        expect(page.locator(".lf-status-button")).to_have_attribute(
            "title",
            "Claude is listening — pick a storage engine. 1 response owed on updates awaiting delivery."
            " Waiting on Claude: 1 reply.",
        )

    # No watcher, but Claude checked in moments ago, so it is between turns.
    declare("waiting")
    expect(text).to_have_text(
        "Claude isn't watching right now. Updates are saved."
        " It picks them up next turn. Waiting on Claude: 1 reply."
    )

    expect(summary).to_have_text("Claude away")

    # With nobody listening and the turn over, an update that has only just arrived
    # still reads away: the session's next turn takes it, and a harness Leaf can
    # message was sent it as it arrived.
    declare("working", "running the migration", quiet_for=6 * 60, turn_ended=5 * 60)
    expect(text).to_have_text(
        "Claude isn't watching right now. Updates are saved."
        " It picks them up next turn. Waiting on Claude: 1 reply, 1 to-do (Work on the page)."
    )
    expect(dot).to_have_class(re.compile(r"\baway\b"))

    # Once an update has waited past the pickup grace with nothing to carry it, the
    # remedy is the user's, and the reading says since when nobody has been there.
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "text": "Still there?",
            "ts": (datetime.now().astimezone() - timedelta(minutes=3)).isoformat(
                timespec="seconds"
            ),
        },
    )
    declare("working", "running the migration", quiet_for=6 * 60, turn_ended=5 * 60)
    expect(text).to_have_text(
        "Claude’s turn ended 5m ago. Updates are saved."
        " Nothing is answering them, so nudge it in the terminal."
        " Waiting on Claude: 2 replies, 1 to-do (Work on the page)."
    )
    expect(summary).to_have_text("Nudge Claude in terminal")
    expect(dot).to_have_class(re.compile(r"\baway\b"))

    # Claude's own status gets a far longer rope: the same silence is just a long turn.
    # No turn has closed under this claim, so the rope is the whole of what judges it.
    declare("working", "running the migration", quiet_for=10 * 60)
    expect(text).to_have_text(
        re.compile(r"^\s*Claude is working — running the migration")
    )

    # A dead session needs no timeout at all — the owning pid is simply gone, so the
    # claim it left has nothing behind it however lately it was written.
    declare("working", "running the migration", session_pid=dead_pid)
    expect(text).to_have_text(
        UNHELD + " Waiting on Claude: 2 replies, 1 to-do (Work on the page)."
    )
    expect(summary).to_have_text("No session")
    # Grey, not the amber a session falling behind wears: nobody is on the line, which
    # is a page's reading arrangement rather than something for the user to chase.
    assert dot.evaluate("dot => [...dot.classList]") == ["lf-dot"]

    # Nothing ever claimed the page — a server started outside an agent harness. There is
    # no pid to ask after, so a claim made moments ago is evidence and still stands.
    declare("working", "running the migration", claimed=False)
    expect(text).to_have_text(
        re.compile(r"^\s*Agent is working — running the migration")
    )

    # Once that claim goes quiet there is nothing left holding the page, and an hour of
    # silence on a page that stands for weeks is not a fault to report.
    declare("working", "running the migration", quiet_for=60 * 60, claimed=False)
    expect(text).to_have_text(
        UNHELD + " Waiting on Agent: 2 replies, 1 to-do (Work on the page)."
    )

    declare("working", "revising the plan", agent="Codex")
    expect(text).to_have_text(re.compile(r"^\s*Codex is working — revising the plan"))

    declare("idle")
    expect(text).to_have_text("Page closed. Waiting on Claude: 2 replies.")


def test_thread_timestamps_age_without_new_state(browser, serve):
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    page.keyboard.press("c")
    timestamp = page.locator(".lf-msg-head time").first
    expect(timestamp).to_have_text("just now")
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    ticked(page)
    expect(timestamp).to_have_text("3h ago")


def test_an_idle_page_keeps_its_dom_and_data_subscriptions_at_rest(browser, serve):
    """An unchanged clock must not render state or redeliver an unchanged source.

    Observe mutations over two actual timer ticks instead of imposing a machine-speed
    budget. Clock aging has its own rendered-word test in the projection suite.
    """
    page = open_page(browser, data_projection_page(serve))
    ticked(page)
    page.evaluate(
        """async () => {
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          const {watchData} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          window.idleDeliveries = 0;
          window.stopIdleData = watchData(document.querySelector('lf-feed'), 'rows', () => {
            window.idleDeliveries++;
          });
          window.idleMutations = 0;
          window.idleObserver = new MutationObserver(records => window.idleMutations += records.length);
          window.idleObserver.observe(document.documentElement,
            {subtree: true, childList: true, attributes: true, characterData: true});
        }"""
    )
    ticked(page)
    ticked(page)
    assert page.evaluate(
        """() => {
          window.idleObserver.disconnect();
          window.stopIdleData();
          return {mutations: window.idleMutations, deliveries: window.idleDeliveries};
        }"""
    ) == {"mutations": 0, "deliveries": 1}


def test_failed_clock_paints_do_not_starve_other_widgets_or_restart_polling(
    browser, serve
):
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """async () => {
          const {clocked, clockValue} = await window.__lfRuntimeImport('/runtime/widget-api.js');
          window.clockVersion = 0;
          for (const stage of ['read', 'paint', 'async']) {
            const paint = clocked(document.body, () => {
              const version = clockValue(() => {
                if (stage === 'read' && window.clockVersion)
                  throw new Error('read broke');
                return window.clockVersion;
              });
              if (!version) return;
              if (stage === 'async') return Promise.reject(new Error('async broke'));
              throw new Error('paint broke');
            });
            paint();
          }
          clocked(document.body, () => {
            window.healthyClock = clockValue(() => window.clockVersion);
          })();
          window.clockVersion = 1;
        }"""
    )
    ticked(page)
    assert page.evaluate("window.healthyClock") == 1
    told(page)  # Error reports legitimately change the log and cause one state read.
    ticked(page)
    asked = _traffic(page).asked
    page.evaluate("window.clockVersion = 2")
    ticked(page)
    ticked(page)
    assert page.evaluate("window.healthyClock") == 2
    assert _traffic(page).asked == asked
    consume_browser_errors(page, "clock paint failed:")
    errors = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "error"
    ]
    assert {error.splitlines()[0] for error in errors} == {
        "clock paint failed: read broke",
        "clock paint failed: paint broke",
        "clock paint failed: async broke",
    }
    assert all("\n" in error for error in errors), errors


def test_user_view_context_waits_for_a_samples_viewport_allocation(browser, serve):
    """A connected sample reports real allocated views, never a zero-sized one."""
    source = leaf_page(
        "Sample view",
        """<h1>Sample view</h1>
<lf-sample id="practice" label="Practice">
  <template id="practice-source" data-sample>
    <h2>Contained page</h2><p>Read this in its allocated viewport.</p>
  </template>
</lf-sample>""",
    )
    page = open_page(browser, serve(source))
    element = page.locator("#practice iframe")
    frame = element.element_handle().content_frame()
    wait_until_ready(frame)
    rendered(frame)
    view_url = urljoin(frame.url, "api/user-view")
    reports = []
    page.on(
        "request",
        lambda request: (
            reports.append(request.post_data_json) if request.url == view_url else None
        ),
    )

    def accepted(response):
        return response.url == view_url and response.status == 204

    with page.expect_response(accepted) as first:
        element.evaluate(
            """frame => {
              frame.style.setProperty('width', '650px', 'important');
              frame.style.setProperty('height', '400px', 'important');
            }"""
        )
    initial = first.value.request.post_data_json
    assert initial["viewport"]["width"] > 0
    assert initial["viewport"]["height"] > 0
    assert initial["visual_viewport"]["width"] > 0
    assert initial["visual_viewport"]["height"] > 0
    saved_style = element.evaluate("frame => frame.style.cssText")
    before = len(reports)
    element.evaluate(
        """frame => {
          for (const property of ['width', 'height', 'min-width', 'min-height', 'border-width'])
            frame.style.setProperty(property, '0px', 'important');
        }"""
    )
    # Zero width is the state that stays: the sample sizes its frame to its content, so
    # one frame later a zero-wide document stands as tall as its words wrapped one per
    # line. Either axis at zero is unallocated (user-view.js).
    frame.wait_for_function(
        """() => document.documentElement.clientWidth === 0 &&
          visualViewport.width === 0"""
    )
    # The sample has an opaque origin, so its window.frameElement is null; the
    # parent can still verify that the iframe itself remains connected.
    assert element.evaluate("frame => frame.isConnected")
    # Cover the observer's 10-second heartbeat and 300ms resize quiet interval.
    page.wait_for_timeout(11_000)
    assert reports[before:] == [], "the unallocated sample sent a user view"

    with page.expect_response(accepted) as restored:
        element.evaluate(
            "(frame, style) => { frame.style.cssText = style; }", saved_style
        )
    recovered = restored.value.request.post_data_json
    assert recovered["session"] == initial["session"]
    assert recovered["sequence"] > initial["sequence"]
    assert recovered["viewport"]["width"] > 0
    assert recovered["viewport"]["height"] > 0
    assert recovered["visual_viewport"]["width"] > 0
    assert recovered["visual_viewport"]["height"] > 0
    assert element.evaluate("frame => frame.isConnected")


def test_user_view_context_follows_real_tabs_without_changing_the_page(browser, serve):
    """Agent context names each actual document and its checks, even when a tab
    keeps an earlier revision. Observations never become decisions or freshness
    changes, and hidden reports release their own view without hiding another."""
    source = leaf_page(
        "View observation",
        '<h1 id="view-heading">Service capacity</h1>'
        '<svg id="capacity-drawing" class="drawing" viewBox="0 0 1200 80">'
        '<text x="20" y="40" font-size="12">Ten thousand requests</text></svg>',
    )
    url = serve(source)
    directory = serve.page_dir
    first = open_page(browser, url)

    def views():
        return user_views_model.read_user_views(
            directory, files_model.latest_revision(directory)
        )["sessions"]

    seen = wait_for(
        views,
        lambda records: len(records) == 1 and records[0]["checks"] is not None,
        failure="the live document never reported its view and checks",
    )
    identity = seen[0]["session"]
    assert seen[0]["visible"] and seen[0]["freshness"] == "fresh"
    assert seen[0]["checks"]["matches_view"]
    assert seen[0]["checks"]["reading"]["checks"]["shrunk_labels"]["drawings"]
    file_reading = page_reading(directory)
    source_reading = source_readings(directory)
    asked = _traffic(first).asked

    first.set_viewport_size({"width": 600, "height": 720})
    first.emulate_media(color_scheme="dark", reduced_motion="reduce")
    changed = wait_for(
        views,
        lambda records: (
            records[0]["viewport"]["width"] == 600
            and records[0]["color_scheme"] == "dark"
            and records[0]["checks"]["matches_view"]
        ),
        failure="resizing and changing scheme did not reach the agent view",
    )[0]
    assert changed["session"] == identity
    assert changed["reduced_motion"]
    assert changed["checks"]["viewport"] == {"width": 600, "height": 720}
    assert page_reading(directory) == file_reading
    assert source_readings(directory) == source_reading
    assert _traffic(first).asked == asked

    second = open_page(browser, live_url(url))
    seen = wait_for(
        views,
        lambda records: len(records) == 2 and all(r["checks"] for r in records),
        failure="the second document replaced the first view",
    )
    assert len({r["session"] for r in seen}) == 2
    assert {r["viewport"]["width"] for r in seen} == {
        600,
        second.viewport_size["width"],
    }
    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(directory)])
    assert state.exit_code == 0, state.output
    assert len(json.loads(state.output)["user_views"]["sessions"]) == 2
    assert "user_views" not in second.evaluate(
        "async () => await (await fetch(new URL('api/state', document.querySelector('link[rel=canonical]').href))).json()"
    )

    # Headless Chrome cannot naturally hide one tab, so deliver the platform
    # lifecycle input used by the existing news visibility regression above.
    first.evaluate(
        """() => {
          Object.defineProperty(document, 'visibilityState', {
            configurable: true, value: 'hidden',
          });
          document.dispatchEvent(new Event('visibilitychange'));
        }"""
    )
    hidden = wait_for(
        views,
        lambda records: any(
            r["session"] == identity and not r["visible"] for r in records
        ),
        failure="hiding one document did not release its view",
    )
    assert sum(r["visible"] for r in hidden) == 1

    (directory / "index.html").write_text(
        source.replace("Service capacity", "Updated capacity")
    )
    told(second)
    seen = wait_for(
        views,
        lambda records: any(
            r["revision"] == 2 and r["checks"] and r["checks"]["matches_view"]
            for r in records
        ),
        failure="the new revision never reached its visible document's reading",
    )
    old = next(r for r in seen if r["session"] == identity)
    current = next(r for r in seen if r["session"] != identity)
    assert old["revision"] == 1 and not old["matches_active_revision"]
    assert current["revision"] == 2 and current["matches_active_revision"]


def test_bad_shadow_words_after_upgrade_keep_the_page_usable(browser, serve):
    entry = {
        "description": "Late shadow words.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-shadow": True,
        "x-example": '<lf-probe id="probe"></lf-probe>',
    }
    widget = """import {once, shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-probe',class extends HTMLElement {connectedCallback(){if(!once(this))return;const p=document.createElement('p');p.textContent='Good words';shadowStage(this,[p]);}});"""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.set_default_timeout(10_000)
    held = []
    page.route("**/api/state*", lambda r: held.append(r))
    page.goto(
        serve(
            leaf_page(
                "Late shadow", '<h1>Late shadow</h1><lf-probe id="probe"></lf-probe>'
            ),
            layer_registry={"lf-probe": entry},
            layer_widgets={"lf-probe.js": widget},
        ),
        wait_until="load",
    )
    expect(page.locator("body")).to_have_attribute(
        "data-lf-upgraded", "1", timeout=5_000
    )
    page.evaluate(
        """async()=>{const host=document.querySelector('lf-probe');host.shadowRoot.append(document.createTextNode('Broken author words'));const {textNodesUnder}=await __lfRuntimeImport('/runtime/passages.js');[...textNodesUnder(document.body)];}"""
    )
    assert page.evaluate("document.documentElement.hasAttribute('data-lf-interactive')")
    expect(
        page.get_by_role("status").filter(has_text="Leaf couldn't start")
    ).to_have_count(0)
    consume_browser_errors(page, "staged bare text")
    page.unroute("**/api/state*")
    for r in held:
        r.continue_()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    select_words(page, "h1")
    page.keyboard.press("c")
    write(page_comment(page), "Still usable.")
    expect(page_comment(page)).to_have_js_property("value", "Still usable.")
    page.close()


@pytest.mark.parametrize("answer", ["ready", "offline"])
@pytest.mark.parametrize("focus", ["sample", "chrome"])
def test_first_history_answer_keeps_an_open_quote_draft(browser, serve, answer, focus):
    """Presentation applies saved facts without re-deciding the user's open composer."""
    source = leaf_page(
        "Uninterrupted draft",
        '<h1>Uninterrupted draft</h1><p id="passage">The prototype needs a mobile check.</p>'
        '<lf-sample id="practice" label="Practice" window>'
        '<template id="practice-source" data-sample>'
        '<h1>Practice</h1><button id="inspect">Inspect</button>'
        "</template></lf-sample>",
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.set_default_timeout(8_000)
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(source), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    select_words(page, "#passage")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused(timeout=3_000)
    write(field, "Keep these words.")
    field.evaluate("field => field.setSelectionRange(7, 7)")
    if focus == "sample":
        child = page.locator("#practice iframe").element_handle().content_frame()
        child.locator("#inspect").click()
    else:
        page.locator(".lf-status-button").focus()
        page.evaluate("getSelection().removeAllRanges()")
    expect(field).to_be_visible(timeout=3_000)
    page.unroute("**/api/state*")
    for route in held:
        if answer == "ready":
            route.continue_()
        else:
            route.abort("internetdisconnected")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(field).to_be_visible(timeout=3_000)
    expect(field).to_have_js_property("value", "Keep these words.")
    assert field.evaluate("field => [field.selectionStart, field.selectionEnd]") == [
        7,
        7,
    ]
    expect(page.get_by_role("status").filter(has_text="Draft kept")).to_have_count(0)
    if answer == "offline":
        consume_browser_errors(page, "net::ERR_INTERNET_DISCONNECTED")
    page.close()


@pytest.mark.parametrize("started", [False, True], ids=["untouched", "commenting"])
def test_saved_pages_arrival_yields_to_newer_input(browser, serve, live_leaf, started):
    """Saved chrome restores a visit, but cannot cover a comment begun meanwhile."""
    live_leaf("second", "A second leaf")
    url = serve(
        leaf_page(
            "Saved Pages",
            '<h1>Saved Pages</h1><p id="passage">The prototype needs a mobile check.</p>',
        )
    )
    context = browser.new_context(viewport={"width": 480, "height": 900})
    try:
        prior = context.new_page()
        prior.goto(url, wait_until="load")
        wait_until_ready(prior)
        prior.keyboard.press("g")
        prior.keyboard.press("Shift+l")
        expect(prior.locator("#lf-leaves")).to_be_visible()
        prior.close()

        held = []
        page = context.new_page()
        watched(page)
        page.route("**/api/state*", lambda route: held.append(route))
        page.goto(url, wait_until="load")
        expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
        assert held
        expect(page.locator("#lf-leaves")).to_be_hidden()
        if started:
            select_words(page, "#passage")
            expect(page.locator(".lf-fab-bar")).to_be_visible()
            page.keyboard.press("c")
            field = page.locator(".lf-fab-input")
            write(field, "Keep these words.")
            page.keyboard.press("Home")
            for _ in range(7):
                page.keyboard.press("ArrowRight")
            expect(field).to_be_focused()
        for route in held:
            route.continue_()
        page.unroute("**/api/state*")
        wait_until_ready(page)
        if started:
            expect(page.locator("#lf-leaves")).to_be_hidden()
            expect(field).to_be_visible()
            expect(field).to_be_focused()
            expect(field).to_have_js_property("value", "Keep these words.")
            assert field.evaluate("f => [f.selectionStart, f.selectionEnd]") == [7, 7]
            expect(page.locator("html")).not_to_have_attribute(
                "data-lf-covering-surface", "lf-leaves"
            )
        else:
            expect(page.locator("#lf-leaves")).to_be_visible()
            expect(page.locator("html")).to_have_attribute(
                "data-lf-covering-surface", "lf-leaves"
            )
    finally:
        context.close()
