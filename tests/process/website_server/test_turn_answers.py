"""What a finished hosted turn leaves on the page: the agent's reply, a correction for a
rejected one, and a receipt for each move it left unanswered."""

import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    activity_reading,
    append_command,
    owed_answers,
    page_state,
    publish,
    running_http_server,
)
from interact_support import append_carried_log_record as append_event

import leaf_website as website_server
from leaf.codex import delivery_records
from leaf.delivery import current_responses
from leaf.event_log import read_events
from leaf.hosting import LeafHTTPServer
from leaf.service import PageTransaction, read_stream
from leaf.state import session_record
from process.website_server import (
    accept_in_turn,
    get,
    hosted_follower,
    post,
    write_manifest,
)


def test_a_turn_that_completes_without_an_answer_is_still_receipted(
    page_dir, monkeypatch
):
    """A turn can end well and still leave the user with nothing.

    App Server reports a turn completed whether or not it wrote a final answer, so
    the move it was given can outlive it settled by nobody. The follower that took
    it is the only writer the pickup leaves, and it reads the same question at
    every ending: is this move still owed a reply.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [],
                        },
                    },
                }
            )

        def close(self):
            self.closed = True

    harness = website_server.WebsiteCodexHarness("codex")
    interrupts = []
    monkeypatch.setattr(
        harness,
        "_interrupt",
        lambda *args, **kwargs: interrupts.append(args),
    )
    hosted_follower(harness, page_dir, prepared, Socket()).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    # The turn ended by itself, so there is nothing to stop.
    assert interrupts == []
    claim_record = website_server.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["turn_closed"] is not None
    assert owed_answers(page_dir) == []


def _page_pick(page_dir: Path) -> dict:
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    )
    publish(page_dir)
    return append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["backfill-first"]},
        },
    )


def _message(page_dir: Path) -> dict:
    publish(page_dir)
    return append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Add the camera as the first job.",
        },
    )


@pytest.mark.parametrize(
    ("answer", "owed_move"),
    (("markup", _page_pick), ("reply", _message)),
)
def test_a_failed_turn_hands_every_kind_of_owed_move_back(
    page_dir, monkeypatch, answer, owed_move
):
    """A turn that ends without answering settles what it was given, whatever it was.

    The hosted site starts a turn for every move that owes an answer: a message or
    an answer to a page obligation. Each takes the failure its own answer takes, and each
    leaves the next step with the user, so none stays owed with no turn coming for
    it. A pick stays in force on the page, and the workflow says it was
    not answered until the user answers again. A message is told in its own
    thread.
    """
    move = owed_move(page_dir)
    assert current_responses(page_dir, read_events(page_dir))[move["id"]]["kind"] == (
        answer
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        def recv(self, timeout):
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [],
                        },
                    },
                }
            )

        def close(self):
            pass

    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(harness, "_interrupt", lambda *args, **kwargs: None)
    hosted_follower(harness, page_dir, prepared, Socket()).follow()

    events = read_events(page_dir)
    state = page_state(page_dir)
    assert owed_answers(page_dir) == []
    assert website_server.next_unaccepted_agent_event(page_dir) is None
    returned = [
        workflow for workflow in state["workflows"] if workflow["input"] == move["id"]
    ]
    if answer == "markup":
        [gave_up] = [
            event
            for event in events
            if event["kind"] == "pickup" and event["phase"] == "failed"
        ]
        assert (gave_up["events"], gave_up["failure"]) == ([move["id"]], "turn_failed")
    else:
        [reply] = [event for event in events if event["kind"] == "reply"]
        assert (reply["responds"], reply["failure"]) == (move["id"], "turn_failed")
    [workflow] = returned
    assert workflow["condition"] == {"kind": "failed", "operation": "response"}
    [record] = [
        item
        for item in state["browser"]["views"][str(state["active"]["revision"])][
            "obligations"
        ]
        if item["id"] == workflow["obligation"]
    ]
    assert record["next_actor"] == "user"
    assert owed_answers(page_dir) == []


def test_a_harness_failure_receipt_answers_a_gesture_on_its_thread(page_dir):
    """The Worker's last-resort receipt reaches a widget gesture too, twice over.

    `/_leaf/agent/fail` is what the Worker calls when it is rate limited or its
    dispatch throws, with whatever event `/api/event` accepted — which can be a
    gesture on a widget frozen into thread markup. That is answered on the
    thread holding it, so addressing the receipt at the gesture refuses the
    one write whose whole job is to leave the user something.

    The Worker repeats that request, so the second call has to answer with the first
    receipt. Once the first has settled the gesture, nothing outside the log can say
    where its reply went: an address worked out ahead of the write reads the settled
    page, gets the gesture back, and refuses its own earlier receipt as another
    event's. The durable attempt is the answer, and the writer reads it first.
    """
    website_server.activate_source(page_dir)
    asked = append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="region" choose>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "region",
            "action": "choose",
            "detail": {"value": ["east"]},
        },
    )

    reply = website_server.WebsiteCodexHarness("codex").failure_receipt(
        page_dir, chose["id"], "startup_failed"
    )

    assert reply is not None
    assert (reply["parent"], reply["responds"]) == (asked["id"], chose["id"])
    assert reply["failure"] == "startup_failed"

    repeated = website_server.WebsiteCodexHarness("codex").failure_receipt(
        page_dir, chose["id"], "startup_failed"
    )
    # The same event, which is what the door hands back (`accepted["id"]`); the log
    # read carries a `seq` the freshly appended record does not.
    assert repeated is not None and repeated["id"] == reply["id"]
    assert repeated["parent"] == asked["id"]
    assert (
        website_server.WebsiteCodexHarness("codex").attach(page_dir, chose["id"])
        is None
    )
    assert [
        event["id"] for event in read_events(page_dir) if event["kind"] == "reply"
    ] == [reply["id"]]


def test_an_unanswered_widget_gesture_is_receipted_on_its_thread(page_dir, monkeypatch):
    """A receipt is addressed where the gesture is answered, not at the gesture.

    A widget frozen into thread markup is answered on the thread holding it,
    so the address a reply is written to and the move it settles are two different
    events. Writing the receipt at the gesture refuses instead of settling it. The
    turn below starts, takes the gesture, and then loses its stream, which is the
    ending that owes this receipt.
    """
    website_server.activate_source(page_dir)
    asked = append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-ask id="region-ask"><h3>Which region?</h3>'
            '<lf-options id="region" choose>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            '<lf-option id="west"><strong>West</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "region",
            "action": "choose",
            "detail": {"value": ["east"]},
        },
    )
    with website_server.PageTransaction(page_dir) as page:
        page.set_status("idle")
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(
        harness, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
    )

    class LostSocket:
        def recv(self, timeout):
            raise OSError("connection lost")

        def close(self):
            pass

    follow = harness._start_turn(
        LostSocket(),
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    assert follow.reply_target is not None
    assert follow.reply_target["parent"] != follow.reply_target["responds"]

    monkeypatch.setattr(harness, "_interrupt", lambda *args, **kwargs: None)
    follow.follow()
    harness.close()

    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert (receipt["parent"], receipt["responds"]) == (asked["id"], chose["id"])
    assert receipt["failure"] == "turn_failed"


def test_an_empty_final_is_not_logged_as_visible_reply(page_dir, capsys):
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        def __init__(self):
            self.closed = False
            self.messages = iter(
                [
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turnId": "app-server-turn",
                            "startedAtMs": 1,
                            "completedAtMs": 2,
                            "item": {
                                "id": "empty-answer",
                                "type": "agentMessage",
                                "phase": "final_answer",
                                "text": "",
                            },
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "app-server-turn",
                                "status": "completed",
                                "items": [],
                            },
                        },
                    },
                ]
            )

        def recv(self, timeout):
            return json.dumps(next(self.messages))

        def close(self):
            self.closed = True

    socket = Socket()
    harness = website_server.WebsiteCodexHarness("codex")
    hosted_follower(harness, page_dir, prepared, socket).follow()

    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert "turn_reply_first_text_published" not in {record["event"] for record in logs}
    assert socket.closed


def test_a_native_final_message_never_becomes_a_leaf_reply(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    accept_in_turn("hosted-thread")
    website_server.WebsiteCodexHarness("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        {"id": "app-server-turn", "status": "completed", "error": None},
        expected=session_record("hosted-thread"),
    )

    events = read_events(page_dir)
    assert not any(event["kind"] == "reply" for event in events)
    claim = website_server.page_claim(page_dir)
    assert claim is not None
    assert claim["turn"] == "app-server-turn"
    assert claim["turn_closed"] is not None
    assert [
        obligation["input"] for obligation in activity_reading(page_dir)["obligations"]
    ] == [comment["id"]]


@pytest.mark.parametrize(
    "restart", ["started", "refused", "offline", "transferred", "reacquired"]
)
def test_a_rejected_streamed_reply_starts_a_website_correction(
    page_dir, monkeypatch, restart
):
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            # The turn's own work left the page unopenable, which is what the
            # commit below meets when it tries to close the turn on it.
            (page_dir / "index.html").write_text("<main>unfinished")
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [
                                {
                                    "id": "answer",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Done.",
                                }
                            ],
                        },
                    },
                }
            )

        def close(self):
            self.closed = True

    socket = Socket()
    harness = website_server.WebsiteCodexHarness("codex")
    restarted = []

    def server():
        if restart == "offline":
            raise RuntimeError("provider unavailable")
        return SimpleNamespace(pid=os.getpid())

    monkeypatch.setattr(harness, "_ensure_server", server)

    def resume(target, session, process, event_id):
        repair = website_server.prepare_codex_delivery(
            target, website_server.website_harness(session, process.pid)
        )
        restarted.append(repair.payload)
        return restart == "started"

    if restart not in {"transferred", "reacquired"}:
        monkeypatch.setattr(harness, "_resume_and_start", resume)
    else:
        monkeypatch.setattr(
            harness,
            "_request",
            lambda *_: (Socket(), {"thread": {"status": {"type": "idle"}}}, []),
        )

        def send(socket, method, params, pending):
            restarted.append(json.loads(params["toolOutput"]["output"]))
            return {"turn": {"id": "repair-turn"}}

        monkeypatch.setattr(harness, "_send", send)
        monkeypatch.setattr(harness, "_follow", lambda *_: None)
    turn = hosted_follower(harness, page_dir, prepared, socket)
    if restart in {"transferred", "reacquired"}:
        follow = turn.follow

        def transfer_after_final():
            follow()
            assert turn.correction is not None
            session = "successor" if restart == "transferred" else "hosted-thread"
            with website_server.PageTransaction(page_dir) as page:
                page.take_claim(website_server.website_harness(session, os.getpid()))
            replacement.append(website_server.page_claim(page_dir))

        replacement = []
        monkeypatch.setattr(turn, "follow", transfer_after_final)
    harness.following_threads.add("hosted-thread")
    harness._run_follow_turn(turn)
    if restart in {"transferred", "reacquired"}:
        claim = website_server.page_claim(page_dir)
        replacement_claim = replacement[0]
        assert claim is not None and replacement_claim is not None
        assert all(
            claim[key] == replacement_claim[key]
            for key in ("id", "generation", "acquisition")
        )
        assert restarted == []
        assert delivery_records("hosted-thread") == []
        assert socket.closed
        return
    if restart != "offline":
        [repair] = restarted
        assert repair["correction"]["delivery"] == prepared.payload["id"]
        assert "unclosed tags" in repair["correction"]["diagnostic"]
        assert website_server.stream_reply_target(repair) == turn.reply_target

    claim = website_server.page_claim(page_dir)
    assert claim is not None
    assert claim["turn_closed"] is not None
    reply = read_stream(page_dir)["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "failed",
        "Done.",
        False,
    )
    replies = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    if restart == "started":
        # A rejected final remains outstanding while its correction runs.
        assert replies == []
    else:
        assert len(replies) == 1
        assert replies[0]["failure"] == "turn_failed"
        assert delivery_records("hosted-thread") == []
    assert socket.closed


@pytest.mark.parametrize("phase", ["queued", "opened", "failed"])
@pytest.mark.parametrize("owed_move", [_page_pick, _message])
def test_a_harness_receipt_does_not_answer_input_an_agent_turn_already_claimed(
    page_dir,
    phase,
    owed_move,
):
    from leaf.delivery import record_pickup

    move = owed_move(page_dir)
    harness = website_server.website_harness("hosted-thread", os.getpid())
    website_server.prepare_codex_delivery(page_dir, harness)
    with PageTransaction(page_dir) as page:
        record_pickup(
            page,
            [move],
            phase=phase,
            session="hosted-thread",
            failure="delivery_failed" if phase == "failed" else None,
        )
    before = read_events(page_dir)

    reply = website_server.write_failure_receipt(page_dir, move["id"], "startup_failed")

    assert reply is None
    assert read_events(page_dir) == before


def test_a_harness_receipt_survives_an_invalid_candidate_source(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    (page_dir / "index.html").write_text("<main>unfinished")

    reply = website_server.WebsiteCodexHarness("codex").failure_receipt(
        page_dir, comment["id"], "startup_failed"
    )

    assert reply is not None
    assert reply["responds"] == comment["id"]


def test_a_receipt_waits_for_external_turn_acceptance_to_be_recorded(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    turn_started = threading.Event()
    record_acceptance = threading.Event()
    receipt_waiting = threading.Event()

    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            if self.lock.locked():
                receipt_waiting.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    monkeypatch.setattr(harness, "lock", ObservedLock())
    monkeypatch.setattr(harness, "_ensure_server", lambda: process)

    def start_thread(page, process, event_id):
        website_server.prepare_codex_delivery(
            page, website_server.website_harness("hosted-thread", process.pid)
        )
        turn_started.set()
        record_acceptance.wait(timeout=STATED_TIMEOUT)
        accept_in_turn("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(harness, "_start_thread", start_thread)

    with ThreadPoolExecutor(max_workers=2) as pool:
        attached = pool.submit(harness.attach, page_dir, comment["id"])
        assert turn_started.wait(timeout=STATED_TIMEOUT), (
            "the attach never started its turn"
        )
        settled = pool.submit(
            harness.failure_receipt,
            page_dir,
            comment["id"],
            "startup_failed",
        )

        assert receipt_waiting.wait(timeout=STATED_TIMEOUT), (
            "the receipt never waited on the harness lock"
        )
        record_acceptance.set()
        assert attached.result(timeout=STATED_TIMEOUT) == "hosted-thread"
        assert settled.result(timeout=STATED_TIMEOUT) is None
    assert not any(
        event["kind"] == "reply" and event.get("parent") == comment["id"]
        for event in read_events(page_dir)
    )


def test_an_agent_reply_is_dropped_when_a_newer_user_turn_overtakes_it(
    page_dir, tmp_path
):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = LeafHTTPServer(("127.0.0.1", 0), website_server.site_endpoint(site))
    root = f"http://127.0.0.1:{httpd.server_address[1]}/examples/decision"
    with running_http_server(httpd):
        state = json.loads(get(f"{root}/api/state")[0])
        headers = {"Leaf-Layer": state["layer"]["generation"]}
        post(
            f"{root}/api/event",
            {
                "kind": "comment",
                "revision": state["active"]["revision"],
                "text": "First question",
                "attempt": "first-question-01",
            },
            headers,
        )
        first = read_events(published)[-1]
        post(
            f"{root}/api/event",
            {
                "kind": "reply",
                "parent": first["id"],
                "revision": state["active"]["revision"],
                "text": "A more specific follow-up",
                "attempt": "second-question-1",
            },
            headers,
        )

        answer, _ = post(
            f"{root}/_leaf/agent/fail",
            {"event": first["id"], "failure": "rate_limited"},
        )

        assert answer == {"status": "settled"}
        stale = website_server.FAILURE_RECEIPTS["rate_limited"]
        assert all(event.get("text") != stale for event in read_events(published))
