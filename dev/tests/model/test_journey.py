"""The journey's harness readings: what a step records of each comment, the records
each harness's session gives its turn phases, and how the Claude Code journey reads
its pane."""

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from interact_support import STATED_TIMEOUT
from playwright.sync_api import BrowserContext
from playwright.sync_api import Page as BrowserPage

from leaf import harness
from leaf.harness import NUDGE_WORDS
from leaf.hook_transport import INLINE_OPENING
from leaf.interaction_log import read_interactions
from leaf_dev import ROOT, journey_claude_code, journey_pi
from leaf_dev.commands import journey, journey_chart
from leaf_dev.page_fixtures import record_run_context
from leaf_dev.reply_phases import (
    LEAF_WAKE,
    claude_code_debug_records,
    claude_code_records,
    pickup_wait,
    reply_breakdown,
    turn_phases,
)
from leaf_dev.review_scenario import SLEEP


def at(seconds: float) -> str:
    return f"2026-10-08T09:00:{seconds:06.3f}+00:00"


def test_journey_declares_automation_after_a_user_preview_starts(
    page_dir, tmp_path, monkeypatch
):
    """Preview intent cannot make the journey's following synthetic input human."""
    record_run_context(page_dir, purpose="user-review", run=page_dir)
    evidence = tmp_path / "run-evidence"
    evidence.mkdir()
    place = journey.Isolation(
        tmp_path, tmp_path, tmp_path, page_dir, tmp_path, evidence
    )
    monkeypatch.setattr(journey, "running_server", lambda page: {"url": "http://page/"})
    with journey.user_at(None, place, journey.Terminal(), time.monotonic()):
        contexts = read_interactions(page_dir, types=("run_context",))
        assert [row["purpose"] for row in contexts] == ["user-review", "automated"]
        assert contexts[-1]["run"] == str(evidence)


def test_release_publication_requires_the_marker_in_board_markup():
    """A site embeds its release hash in asset URLs before an agent edits the board."""
    marker = "71b197da"

    class Response:
        ok = True

        def __init__(self, html):
            self.html = html

        def text(self):
            return self.html

    class Request:
        def __init__(self):
            self.html = ""

        def get(self, *args, **kwargs):
            return Response(self.html)

    request = Request()
    end = journey.BrowserEnd(
        cast(
            journey.Session,
            SimpleNamespace(
                context=SimpleNamespace(request=request),
                url="https://leaf.page/",
                pause=lambda _: None,
            ),
        )
    )
    active = {"url": "revisions/2.html"}
    request.html = (
        f'<head><script src="/_leaf-release/{marker}/leaf.js"></script></head>'
        "<body><main>Release board unchanged</main></body>"
    )
    assert not end.names(active, marker)
    request.html = request.html.replace(
        "Release board unchanged", f"Release {marker} passed"
    )
    assert end.names(active, marker)
    request.html = f'<main><lf-column label="Release {marker}"></lf-column></main>'
    assert end.names(active, marker)


def test_release_publication_ignores_rebased_resource_urls_in_board():
    from leaf.revision_delivery import rebase_document

    marker = "71b197da"
    authored = '<main><img src="/page/chart.svg" alt="Current chart"></main>'
    served = rebase_document(authored, lambda path: f"/_leaf-release/{marker}{path}")
    assert marker in served
    assert not journey.board_names_release(served, marker)


def test_release_publication_ignores_inline_script_and_style_text():
    marker = "71b197da"
    authored = (
        "<main>Release board unchanged"
        f"<script>const release = '{marker}'</script>"
        f"<style>.release {{ content: '{marker}' }}</style>"
        "</main>"
    )
    assert not journey.board_names_release(authored, marker)


@pytest.mark.parametrize("end", ["http", "browser"])
def test_a_steps_comments_are_timed_from_the_log_and_in_a_browser_the_page(end):
    """Each step keeps the comments it sent, timed from the page's log on the
    server's clock from their admission, with the turn split from the session's
    records from the opened pickup on; in a browser, also from their send to their
    reply showing, as the page recorded it. A permission prompt the user answered
    marks its step's comments, and the release ask's, so a reading held up by one is
    told apart from those that were not."""
    events = [
        {"kind": "comment", "id": "c1", "ts": at(0)},
        {
            "kind": "pickup",
            "id": "p1",
            "phase": "opened",
            "events": ["c1"],
            "ts": at(1),
        },
        {
            "kind": "reply",
            "author": "agent",
            "id": "r1",
            "parent": "c1",
            "responds": "c1",
            "text": "Two items block it.",
            "ts": at(9),
        },
    ]
    records = [
        {"type": "user", "message": {"content": []}, "received_at": at(0.5)},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t", "name": "Bash", "input": {}}
                ]
            },
            "received_at": at(3),
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t"}]},
            "received_at": at(4),
        },
    ]
    terminal = journey.Terminal()
    terminal.trace = records
    shown = []

    class Page:
        """The page as the browser end reads it: when it showed a reply."""

        def evaluate(self, script, arg=None):
            assert script == "window.__leafVerifier.replyShownAt"
            assert arg is not None
            shown.append(arg["id"])
            # The row shows the reply first; its message comes into view a read later.
            message = 1_000_000 + 9_520 if len(shown) > 1 else None
            return {"at": 1_000_000 + 9_500, "by": "row", "message": message}

    url = "http://127.0.0.1:1/?t=token"
    user_end = (
        journey.BrowserEnd(
            journey.Session(
                cast(BrowserContext, None),
                cast(BrowserPage, Page()),
                [],
                url,
                url,
                {},
                {},
                None,
            )
        )
        if end == "browser"
        else journey.HttpEnd(url, Path("page"), time.sleep)
    )
    user = journey.User(user_end, "v", lambda: events, terminal, list)
    user.release_reading = {
        "version": "v",
        "comment": {
            "eventIds": ["c0"],
            "sinceAdmissionMs": {"replied": 12000},
            "sinceSendMs": {},
        },
    }
    terminal.approved.append("Do you want to make this edit to index.html?")
    user.passed("release", time.monotonic())
    profile = journey.AgentProfile()
    profile.ask_count = 1
    profile.event_ids = ["c1"]
    if end == "browser":
        profile.visible_reply_started_ms = 1_000_000
        profile.acknowledged = [0.04]
    user.ids["mid-turn"], user.profiles["mid-turn"] = "c1", profile
    user.sent = ["mid-turn"]
    terminal.approved.append("Do you want to proceed?")
    user.passed("mid-turn", time.monotonic() - 6)

    sample = user.sample()
    assert sample["userEnd"] == end
    assert sample["comment"]["approved"] == [
        "Do you want to make this edit to index.html?"
    ]
    release, step = sample["steps"]
    assert release["comments"] == {}
    assert step["step"] == "mid-turn"
    assert step["approved"] == ["Do you want to proceed?"]
    # The time a prompt held the session is the step's like any other.
    assert 5.9 <= step["seconds"] <= 6.5
    reading = step["comments"]["mid-turn"]
    assert reading["approved"] == ["Do you want to proceed?"]
    assert reading["sinceAdmissionMs"]["pickedUp"] == 1000
    assert reading["sinceAdmissionMs"]["replied"] == 9000
    if end == "browser":
        assert reading["sinceSendMs"]["responseVisible"] == 9500
        assert reading["responseShownBy"] == "row"
        assert reading["sinceSendMs"]["responseMessageVisible"] == 9520
        assert shown == ["r1", "r1"]
    else:
        assert "sinceSendMs" not in reading and shown == []
    # The record before the pickup is no delivery; the work after it is.
    assert [phase["phase"] for phase in reading["reply"]["phases"]] == [
        "delivery",
        "model",
        "tool",
        "model",
    ]
    assert reading["reply"]["phases"][0] == {
        "phase": "delivery",
        "startMs": 0,
        "ms": 1000,
    }
    assert terminal.approved == []
    prompted = {**sample, "target": "claude-code", "version": "old"}
    later = {
        **sample,
        "target": "claude-code",
        "comment": {**sample["comment"], "approved": []},
    }
    rows = journey_chart.chart_rows(
        [prompted, later, {**later, "comment": sample["comment"]}]
    )
    # The latest version is chosen before rows split by prompt, so a prompted run of
    # an older version leaves the chart once a newer one runs; each user end has rows
    # of its own.
    over = " over HTTP" if end == "http" else ""
    assert {row["row"] for row in rows} == {
        f"Claude Code{over} at v",
        f"Claude Code{over} after a permission prompt at v",
    }


def test_a_comment_a_fork_decided_on_keeps_the_forks_record():
    """A comment a fork of the conversation answered carries the fork's outcome,
    time and tokens, and no breakdown of a reply the session spent nothing on; one
    the fork handed over carries both."""
    events = [
        {"kind": "comment", "id": "c1", "ts": at(0)},
        {
            "kind": "reply",
            "author": "agent",
            "id": "r1",
            "parent": "c1",
            "responds": "c1",
            "text": "You asked me to serve it for review.",
            "ts": at(4),
        },
        {"kind": "comment", "id": "c2", "ts": at(10)},
        {
            "kind": "pickup",
            "id": "p2",
            "phase": "opened",
            "events": ["c1", "c2"],
            "ts": at(20),
        },
        {
            "kind": "reply",
            "author": "agent",
            "id": "r2",
            "parent": "c2",
            "responds": "c2",
            "text": "Renamed it.",
            "ts": at(30),
        },
    ]
    usage = {"input_tokens": 12, "output_tokens": 80, "cache_read_input_tokens": 9000}
    forks = [
        {
            "type": "fork_reply",
            "thread": "c1",
            "inputs": ["c1"],
            "outcome": "reply",
            "reply": "r1",
            "text": "You asked me to serve it for review.",
            "elapsedMs": 3200.0,
            "usage": usage,
        },
        {
            "type": "fork_reply",
            "thread": "c2",
            "inputs": ["c2"],
            "outcome": "hand_over",
            "why": "it asks for a change",
            "elapsedMs": 2100.0,
        },
    ]
    end = journey.HttpEnd("http://127.0.0.1:1/?t=t", Path("page"), time.sleep)
    user = journey.User(
        end, "v", lambda: events, journey.Terminal(), list, lambda: forks
    )
    for name, comment in (("fork-idle", "c1"), ("fork-work", "c2")):
        profile = journey.AgentProfile()
        profile.event_ids = [comment]
        user.ids[name], user.profiles[name] = comment, profile
        user.sent.append(name)
    assert user.timing("fork-idle") == (
        "`fork-idle` picked up after 20.0 s, answered after 4.0 s; a fork's reply "
        "after 3200 ms on 12 in, 80 out, 9000 cache read tokens"
    )
    user.passed("forks", time.monotonic())

    [step] = user.sample()["steps"]
    answered, handed = step["comments"]["fork-idle"], step["comments"]["fork-work"]
    assert answered["fork"] == {"outcome": "reply", "elapsedMs": 3200.0, "usage": usage}
    assert "reply" not in answered
    assert handed["fork"] == {
        "outcome": "hand_over",
        "why": "it asks for a change",
        "elapsedMs": 2100.0,
    }
    assert "reply" in handed


PROMPT = """
 Bash command

   python3 -c 'import time; time.sleep(25.17)'
   Run the user's command

 Do you want to proceed?
 ❯ 1. Yes
   2. Yes, and don't ask again for python3 commands in /private/work
   3. No, and tell Claude what to do differently (esc)

 Esc to cancel · Tab to amend
"""


@pytest.mark.parametrize(
    "question",
    [
        "Do you want to proceed?",
        "Do you want to make this edit to index.html?",
        "Do you want to create notes.md?",
    ],
)
def test_an_approved_prompt_is_recorded_by_its_question(question):
    """Claude Code's record says when a dialog is open; the step records which one by
    the question its prompts for a command, an edit and a new file ask, the last on
    the screen, below any the agent's own words asked."""
    earlier = "⏺ I can make the change.\n  Do you want to rename it too?\n"
    screen = earlier + PROMPT.replace("Do you want to proceed?", question)
    assert journey_claude_code.asked(screen) == question


def test_the_users_command_is_found_only_among_the_panes_own_processes(spawn):
    """Journeys run side by side run the same command; each finds only its own, among
    its pane's descendants, so another journey's command is not this one's turn."""
    command = [sys.executable, "-c", f"import time; {SLEEP}"]
    pane = spawn(["sh", "-c", f"{subprocess.list2cmdline(command)}; true"])
    spawn(command)
    neighbour = spawn(["sh", "-c", "sleep 30; true"])
    deadline = time.monotonic() + STATED_TIMEOUT
    while not journey_claude_code.runs(pane.pid, SLEEP):
        assert time.monotonic() < deadline, "the pane's command never ran"
        time.sleep(0.1)
    assert not journey_claude_code.runs(neighbour.pid, SLEEP)


def test_claude_codes_transcript_gives_tool_and_turn_records(tmp_path):
    """Claude Code's transcript stamps each record as it writes it, and a prompt's
    content may be a bare string; the journey reads both, and nothing else, and a
    model response ends with the last record carrying its message id."""
    session = "6f1c"
    path = tmp_path / ".claude" / "projects" / "-private-work" / f"{session}.jsonl"
    path.parent.mkdir(parents=True)
    lines = [
        {
            "type": "user",
            "timestamp": at(1),
            "turnPosition": {"promptIndex": 1, "turnIndex": 1},
            # Claude Code writes U+2028 raw inside a string.
            "message": {"content": "Serve\u2028it."},
        },
        {"type": "attachment", "timestamp": at(1.5), "attachment": {}},
        {
            "type": "assistant",
            "timestamp": at(2),
            "message": {
                "id": "m1",
                "content": [
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {}}
                ],
                "usage": {"output_tokens": 120},
            },
        },
        {"type": "system", "timestamp": at(2.5), "subtype": "stop_hook_summary"},
        {"type": "system", "timestamp": at(3), "subtype": "turn_duration"},
        {
            "type": "user",
            "timestamp": at(4),
            "isCompactSummary": True,
            "turnPosition": {"promptIndex": 1, "turnIndex": 1},
            "message": {"content": "Summary."},
        },
    ]
    # Claude Code is still writing the last record, which is no record yet; its
    # bytes so far can end inside a character.
    path.write_bytes(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()
        + '{"type": "assistant", "text": "é'.encode()[:-1]
    )
    native = journey_claude_code.native_records(tmp_path, session)
    assert claude_code_records(native) == [
        {"type": "turn_start", "received_at": at(1)},
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "Serve\u2028it."}]},
            "received_at": at(1),
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {}}
                ]
            },
            "received_at": at(2),
        },
        {"type": "model_response", "received_at": at(2), "outputTokens": 120},
        {"type": "turn_end", "received_at": at(3)},
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "Summary."}]},
            "received_at": at(4),
        },
    ]


def test_the_journey_reads_claude_codes_status_as_it_is_now(tmp_path, monkeypatch):
    """Claude Code rewrites its registry record in place, which Leaf's reused
    listing doesn't notice within its time bucket; the journey's reading sees the
    rewrite at once, as a step that presses Escape and waits for the next turn
    needs."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "sessions").mkdir()
    record = tmp_path / "sessions" / f"{os.getpid()}.json"
    # Leaf's listing reads within one time bucket throughout.
    monkeypatch.setattr(harness.time, "monotonic", lambda: 0.0)

    def write(status: str, at: int) -> None:
        with record.open("w") as written:
            written.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "sessionId": "s",
                        "status": status,
                        "statusUpdatedAt": at,
                    }
                )
            )

    cc = journey_claude_code.ClaudeCode.__new__(journey_claude_code.ClaudeCode)
    cc.session = "s"
    write("idle", 1)
    live_turn_result = harness.ClaudeCodeHarness(
        session="s", agent="Claude"
    ).live_turn()
    assert live_turn_result is not None
    assert live_turn_result["state"] == "idle"
    assert cc.idle()
    write("busy", 2)
    live_turn_result_2 = harness.ClaudeCodeHarness(
        session="s", agent="Claude"
    ).live_turn()
    assert live_turn_result_2 is not None
    assert live_turn_result_2["state"] == "idle"
    assert cc.state() == "busy"


def test_a_delivered_update_waits_for_the_turn_it_opened_to_end():
    """The journey waits for the turn a delivery reached to end in the transcript;
    a turn that ended before the delivery doesn't count. Waiting on Claude Code's
    idle instead read the idle an Escape wrote before the delivery's turn started,
    and found the page's claim holding that running turn open."""
    delivery = {
        "format": "leaf-delivery/15",
        "batches": [{"events": [{"kind": "resolve", "id": "f4a21046"}]}],
    }
    records = [
        {"type": "system", "subtype": "turn_duration"},
        {"type": "user", "message": {"content": "<task-notification>"}},
        {
            "type": "attachment",
            "attachment": {
                "type": "hook_additional_context",
                "hookEvent": "UserPromptSubmit",
                "content": [INLINE_OPENING + "\n" + json.dumps(delivery)],
            },
        },
    ]
    assert not journey_claude_code.delivery_ended(records, "f4a21046")
    records.append({"type": "system", "subtype": "turn_duration"})
    assert journey_claude_code.delivery_ended(records, "f4a21046")
    assert not journey_claude_code.delivery_ended(records, "a-comment-never-sent")


def test_a_comment_picked_up_while_a_call_is_out_starts_in_that_tool_phase():
    """A comment sent mid-turn enters the turn while the agent's command still runs;
    the rest of that command's wait is tool time, not the model's."""

    def record(seconds: float, kind: str, part: dict) -> dict:
        return {
            "type": kind,
            "message": {"content": [part]},
            "received_at": at(seconds),
        }

    records = [
        record(
            1,
            "assistant",
            {
                "type": "tool_use",
                "id": "s",
                "name": "Bash",
                "input": {"command": "sleep 4"},
            },
        ),
        record(5, "user", {"type": "tool_result", "tool_use_id": "s"}),
    ]
    assert turn_phases(records, at(0), at(3), at(6)) == [
        {"phase": "delivery", "startMs": 0, "ms": 3000},
        {"phase": "tool", "startMs": 3000, "ms": 2000, "calls": ["sleep 4"]},
        {"phase": "model", "startMs": 5000, "ms": 1000},
    ]


def test_a_reply_taken_while_working_splits_into_leaf_share_and_model_calls():
    """A comment sent while the harness works waits for the tool boundary, which is
    the harness's time, not Leaf's; Leaf's share is the delivery after it and the
    time each `leaf` command recorded, from its start after the comment until the
    reply. Model phases with no response ending between them are one model call,
    whose tool calls ran while it still streamed."""

    def use(seconds: float, id: str, command: str) -> dict:
        part = {"type": "tool_use", "id": id, "name": "Bash", "input": {}}
        if command != "Edit":
            part["input"]["command"] = command
        else:
            part["name"] = "Edit"
        return {
            "type": "assistant",
            "message": {"content": [part]},
            "received_at": at(seconds),
        }

    def result(seconds: float, id: str) -> dict:
        part = {"type": "tool_result", "tool_use_id": id}
        return {
            "type": "user",
            "message": {"content": [part]},
            "received_at": at(seconds),
        }

    def responded(seconds: float) -> dict:
        return {"type": "model_response", "received_at": at(seconds)}

    records = [
        {"type": "turn_start", "received_at": at(0.2)},
        use(0.5, "s", "sleep 4"),
        result(5, "s"),
        use(7, "a", "leaf task start . c1"),
        use(7, "b", "cat index.html"),
        responded(7),
        result(7.4, "a"),
        result(7.5, "b"),
        use(9, "c", "Edit"),
        result(9.1, "c"),
        use(9.3, "d", "/x/bin/leaf page check ."),
        responded(9.35),
        result(10, "d"),
        responded(12),
        use(12, "e", "leaf thread reply c1"),
    ]

    def ran(started: float, ended: float) -> dict:
        return {"started": at(started), "ts": at(ended)}

    # The watch running from before the comment and a command of the harness's
    # other work while it was busy are no part of the reply, commands running
    # together count once, and the reply's own command counts until the reply is
    # admitted.
    commands = [
        ran(0, 20),
        ran(2, 4),
        ran(7, 7.4),
        ran(7.1, 7.3),
        ran(9.3, 10),
        ran(12, 12.8),
    ]
    reply = reply_breakdown(records, commands, at(1), at(5.2), at(12.5))
    assert reply is not None
    # With no requests or first outputs in the record, the model's time is unsplit.
    assert {key: value for key, value in reply.items() if key != "phases"} == {
        "wholeMs": 11500,
        "leafMs": 1800,
        "busyMs": 4000,
        "deliveryMs": 200,
        "leafCommandsMs": 1600,
        "leafHooksMs": 0,
        "harnessMs": 0,
        "modelMs": 5500,
        "waitMs": 0,
        "generationMs": 0,
        "otherToolsMs": 200,
        "idleMs": 0,
        "outputTokens": None,
        "modelCalls": [
            {"ms": 1800, "calls": ["leaf task start . c1", "cat index.html"]},
            {"ms": 1700, "calls": ["Edit", "/x/bin/leaf page check ."]},
            {"ms": 2000, "calls": ["leaf thread reply c1"]},
        ],
    }
    assert [phase["phase"] for phase in reply["phases"][:3]] == [
        "busy",
        "delivery",
        "model",
    ]
    assert reply_breakdown(records, [], at(1), None, at(12.5)) is None
    # Where the agent works before the pickup, the boundary handed it a pointer it
    # read and acknowledged itself, and the delivery ended at that boundary.
    acknowledged = reply_breakdown(records, [], at(1), at(9.2), at(12.5))
    assert acknowledged is not None
    assert (acknowledged["busyMs"], acknowledged["deliveryMs"]) == (4000, 0)
    assert acknowledged["modelMs"] == 5700
    # A busy turn that ends before the agent takes the comment leaves the harness
    # idle until the turn that reads it starts.
    ended = [
        {"type": "turn_start", "received_at": at(0)},
        {"type": "turn_end", "received_at": at(2)},
        {"type": "turn_start", "received_at": at(32)},
        use(33, "r", "leaf delivery read c1"),
        result(33.5, "r"),
    ]
    later = reply_breakdown(ended, [], at(1), at(34), at(35))
    assert later is not None
    assert (later["busyMs"], later["idleMs"], later["modelMs"]) == (1000, 30000, 2500)
    # Calls out together at the admission hold the harness until the last returns.
    batch = [
        {"type": "turn_start", "received_at": at(0)},
        use(0.5, "a", "sleep 2"),
        use(0.5, "b", "sleep 10"),
        result(2, "a"),
        result(10, "b"),
    ]
    drained = reply_breakdown(batch, [], at(1), at(10.2), at(12))
    assert drained is not None
    assert (drained["busyMs"], drained["deliveryMs"]) == (9000, 200)
    # A call an interrupted turn left without a result holds no later turn.
    interrupted = [
        {"type": "turn_start", "received_at": at(0)},
        use(1, "x", "sleep 60"),
        {"type": "turn_end", "received_at": at(2)},
        {"type": "turn_start", "received_at": at(3)},
        use(4, "y", "sleep 2"),
        result(6, "y"),
    ]
    later = reply_breakdown(interrupted, [], at(5), at(6.2), at(8))
    assert later is not None
    assert (later["busyMs"], later["deliveryMs"]) == (1000, 200)
    assert later["phases"][2]["phase"] == "model"


def test_a_pickup_wait_names_what_ended_it():
    """A comment that arrives in a running turn waits on that turn's calls; one that
    arrives between turns waits on whatever starts the next, read from Claude Code's
    own turn origins: Leaf's wake, Leaf's nudge, or the user's prompt where nothing
    of Leaf's woke the session, past any turn that ended without taking the comment. A session
    whose transcript begins after the comment took the page later."""

    def native(seconds: float, origin: str, text: str) -> dict:
        return {
            "type": "user",
            "timestamp": at(seconds),
            "turnPosition": {"promptIndex": 1, "turnIndex": 1},
            "turnOrigin": origin,
            "message": {"content": text},
        }

    def call(seconds: float, id: str, command: str) -> dict:
        part = {"type": "tool_use", "id": id, "name": "Bash"}
        return {
            "type": "assistant",
            "timestamp": at(seconds),
            "message": {"content": [{**part, "input": {"command": command}}]},
        }

    def returned(seconds: float, id: str) -> dict:
        part = {"type": "tool_result", "tool_use_id": id}
        return {
            "type": "user",
            "timestamp": at(seconds),
            "message": {"content": [part]},
        }

    def ended(seconds: float) -> dict:
        return {"type": "system", "subtype": "turn_duration", "timestamp": at(seconds)}

    records = claude_code_records(
        [
            native(0, "human", "Serve the page."),
            call(1, "t", "pnpm test"),
            returned(9, "t"),
            ended(10),
            native(12, "task_notification", f"<summary>{LEAF_WAKE}</summary>"),
            ended(14),
            native(20, "task_notification", "<summary>Agent done</summary>"),
            ended(22),
            native(30, "human", "check the leaf"),
            ended(32),
            # A background job Leaf resumed, its nudge as the prompt.
            native(40, "human", f"leaf: /page {NUDGE_WORDS}"),
        ]
    )
    working = pickup_wait(records, at(2), at(9.2))
    assert working == {
        "ms": 7200,
        "missedTurns": 0,
        "cause": "working",
        "calls": ["pnpm test"],
    }
    assert pickup_wait(records, at(11), at(12.3))["cause"] == "woken"
    prompted = pickup_wait(records, at(15), at(30.5))
    assert (prompted["cause"], prompted["missedTurns"]) == ("prompted", 1)
    assert pickup_wait(records[2:], at(0.5), at(12.3))["cause"] == "started"
    assert pickup_wait(records, at(33), at(40.4))["cause"] == "nudged"


def test_a_reply_is_attributed_to_leaf_the_harness_and_the_models_wait_and_output():
    """Claude Code's debug log times each request, its first byte and Leaf's hooks:
    a call splits into the harness's part before its request, the model's wait for
    its first output and its generation, and Leaf's hooks count as Leaf's share,
    out of the harness's and the tools' time. A first byte is the main thread's
    where the request it names is; a call without one stays unsplit. The parts add
    up to the whole reply."""

    def logged(seconds: float, rest: str) -> str:
        return f"{at(seconds)} [DEBUG] {rest}"

    def request(seconds: float, source: str = "repl_main_thread") -> str:
        return logged(seconds, f"[API REQUEST] /v1/messages x=1 source={source}")

    def first_byte(seconds: float, after: float) -> str:
        return logged(seconds, f"[API:timing] first byte after {after * 1000:.0f}ms")

    def hook(seconds: float, event: str, ms: int, plugin: str = "leaf@inline") -> str:
        return logged(
            seconds,
            f'Hooks: {event} ["/x/bin/leaf" hook || exit 1] (plugin {plugin}) '
            f"finished with status 0 ({ms}ms)",
        )

    log = "\n".join(
        [
            request(0.6),
            first_byte(1.6, 1),
            hook(4.2, "PreToolUse:Bash", 150),
            hook(4.75, "PostToolBatch", 200),
            # Another plugin's hook is the harness's.
            hook(4.75, "PostToolBatch", 300, plugin="other@inline"),
            # A prompt suggestion's stream answers first, and the main thread's
            # first byte is unlogged, so its call stays unsplit.
            request(4.7, "prompt_suggestion"),
            request(4.8),
            first_byte(5.5, 0.8),
            hook(7.3, "PostToolBatch", 200),
            request(7.3),
            first_byte(8.3, 1),
        ]
    )

    def part(seconds: float, kind: str, block: dict) -> dict:
        return {
            "type": kind,
            "message": {"content": [block]},
            "received_at": at(seconds),
        }

    def use(seconds: float, id: str, command: str) -> dict:
        return part(
            seconds,
            "assistant",
            {
                "type": "tool_use",
                "id": id,
                "name": "Bash",
                "input": {"command": command},
            },
        )

    def result(seconds: float, id: str) -> dict:
        return part(seconds, "user", {"type": "tool_result", "tool_use_id": id})

    def responded(seconds: float, tokens: int) -> dict:
        return {
            "type": "model_response",
            "received_at": at(seconds),
            "outputTokens": tokens,
        }

    records = [
        {"type": "turn_start", "received_at": at(0.5)},
        use(4, "a", "leaf thread reply c1 --ephemeral"),
        responded(4, 200),
        result(4.5, "a"),
        use(7, "b", "Edit"),
        responded(7, 300),
        result(7.05, "b"),
        use(10, "c", "leaf thread reply c1 --done"),
        responded(10, 150),
        *claude_code_debug_records(log),
    ]
    records.sort(key=lambda record: record["received_at"])
    commands = [
        {"started": at(4.2), "ts": at(4.5)},
        {"started": at(10), "ts": at(10.4)},
    ]
    reply = reply_breakdown(records, commands, at(0), at(0.5), at(10.3))
    assert reply is not None
    parts = {key: value for key, value in reply.items() if key != "phases"}
    assert parts == {
        "wholeMs": 10300,
        "leafMs": 1650,
        "busyMs": 0,
        "deliveryMs": 500,
        "leafCommandsMs": 600,
        "leafHooksMs": 550,
        "harnessMs": 250,
        "modelMs": 8300,
        "waitMs": 2000,
        "generationMs": 4100,
        "otherToolsMs": 100,
        "idleMs": 0,
        "outputTokens": 650,
        "modelCalls": [
            {
                "ms": 3500,
                "harnessMs": 100,
                "waitMs": 1000,
                "generationMs": 2400,
                "outputTokens": 200,
                "calls": ["leaf thread reply c1 --ephemeral"],
            },
            {"ms": 2500, "harnessMs": 100, "outputTokens": 300, "calls": ["Edit"]},
            {
                "ms": 2950,
                "harnessMs": 50,
                "waitMs": 1000,
                "generationMs": 1700,
                "outputTokens": 150,
                "calls": ["leaf thread reply c1 --done"],
            },
        ],
    }
    unsplit = parts["modelMs"] - parts["waitMs"] - parts["generationMs"]
    assert unsplit == 2200
    assert parts["wholeMs"] == unsplit + sum(
        parts[key]
        for key in (
            "deliveryMs",
            "leafCommandsMs",
            "leafHooksMs",
            "harnessMs",
            "waitMs",
            "generationMs",
            "otherToolsMs",
        )
    )


def test_pis_events_give_the_turn_phases(monkeypatch):
    """Pi reports its runs, responses and tool calls as RPC events; the journey
    keeps its tool calls, each response's first output and its output tokens as the
    records `turn_phases` and `reply_breakdown` read, and tracks the shell commands
    running."""
    seconds = count(3)
    monkeypatch.setattr(journey_pi, "now", lambda: at(next(seconds)))
    pi = journey_pi.Pi.__new__(journey_pi.Pi)
    journey.Terminal.__init__(pi)
    pi.running, pi.settled, pi.closed_watches = False, 0, 0
    pi.output_tokens = None
    assistant = {"role": "assistant", "usage": {"output": 90}}
    for event in (
        {"type": "agent_start"},
        {"type": "message_start", "message": {"role": "user"}},
        {"type": "message_start", "message": assistant},
        {"type": "message_end", "message": assistant},
        {
            "type": "tool_execution_start",
            "toolCallId": "s",
            "toolName": "bash",
            "args": {"command": "sleep 1"},
        },
        {"type": "tool_execution_end", "toolCallId": "s"},
        {"type": "turn_end"},
        {"type": "leaf_watch_closed", "code": 0},
        {"type": "agent_settled"},
    ):
        pi._hear(event)
    assert pi.commands == ["sleep 1"] and pi.running_commands == {}
    assert (pi.settled, pi.closed_watches, pi.idle()) == (1, 1, True)
    assert [record["type"] for record in pi.records()] == [
        "turn_start",
        "first_output",
        "assistant",
        "user",
        "model_response",
        "turn_end",
    ]
    phases = turn_phases(pi.records(), at(0), at(2), at(9))
    assert phases == [
        {"phase": "delivery", "startMs": 0, "ms": 2000},
        {"phase": "model", "startMs": 2000, "ms": 3000},
        {"phase": "tool", "startMs": 5000, "ms": 1000, "calls": ["sleep 1"]},
        {"phase": "model", "startMs": 6000, "ms": 2000},
        {"phase": "idle", "startMs": 8000, "ms": 1000},
    ]
    call, after = reply_breakdown(pi.records(), [], at(0), at(2), at(9))["modelCalls"]
    assert call == {
        "ms": 3000,
        "waitMs": 2000,
        "generationMs": 1000,
        "outputTokens": 90,
        "calls": ["sleep 1"],
    }
    # The phase after the tool's result had no response end by the reply.
    assert after == {"ms": 2000, "calls": []}


def test_the_release_ask_over_http_is_the_shared_check(tmp_path):
    """Over HTTP the release ask is posted as the page's tab posts one, and the same
    check as in a browser waits on its turn, title and answer, requiring a published
    revision naming the release; it reads nothing a browser would. A step's comment
    is posted on its section."""
    from leaf.event_log import append_event, read_events
    from leaf.thread import post_reply, title_event
    from leaf_dev.arms import run_leaf, serving
    from leaf_dev.review_scenario import post, prepare

    state, page = tmp_path / "state", tmp_path / "page"
    prepare(ROOT, state, page)
    version = "abcd1234" + "0" * 32
    agent = {"agent": "The agent", "session": "journey-release"}
    paused = []

    def pause(seconds):
        """The agent, as the journey waits: it records the release, titles the
        thread and answers."""
        paused.append(seconds)
        if len(paused) > 1:
            return
        [comment] = [e for e in read_events(page) if e["kind"] == "comment"]
        index = page / "index.html"
        index.write_text(
            index.read_text().replace(
                "</main>", "<p>Release abcd1234 passed.</p></main>"
            )
        )
        run_leaf(
            ROOT, state, "page", "stamp", str(page), "--text", "Recorded.", check=True
        )
        append_event(page, title_event(comment["id"], "Release recorded", agent))
        post_reply(
            page,
            {"parent": comment["id"], "responds": comment["id"]},
            "Recorded.",
            identity=agent,
        )

    with serving(ROOT, state, page) as url:
        reading = journey.run_journey(journey.HttpEnd(url, page, pause), version)
        step = post(url, "ending")
    assert reading["change"] == {
        "marker": "abcd1234",
        "revision": 2,
        "reply": "Recorded.",
    }
    assert set(reading) == {"version", "comment", "change"}
    milestones = reading["comment"]["sinceAdmissionMs"]
    assert None not in (
        milestones["titled"],
        milestones["published"],
        milestones["replied"],
    )
    assert "sinceSendMs" not in reading["comment"]
    [asked] = [
        e for e in read_events(page) if e.get("attempt") == "journey-step-release"
    ]
    assert "anchor" not in asked or asked["anchor"].get("section") is None
    [anchored] = [e for e in read_events(page) if e["id"] == step]
    assert anchored["anchor"]["section"] == "triage-why"


def test_a_harness_journey_over_http_starts_no_browser(monkeypatch):
    """Without `--browser` a harness target's user posts its comments, and no
    browser is launched; with it the user is in one."""
    from click.testing import CliRunner

    launched = []

    @contextmanager
    def headless_shell():
        launched.append(True)
        yield "browser"

    entered = []

    @contextmanager
    def target_session(browser, target, release, *, sandbox, preview, forks):
        entered.append(browser)
        end = (
            journey.HttpEnd("http://127.0.0.1:1/?t=t", Path("page"), time.sleep)
            if browser is None
            else journey.BrowserEnd(
                journey.Session(
                    cast(BrowserContext, None),
                    cast(BrowserPage, None),
                    [],
                    "u",
                    "u",
                    {},
                    {},
                    None,
                )
            )
        )
        monkeypatch.setattr(end, "close", lambda: None)
        yield journey.User(end, "v"), {"target": target}, lambda: None

    monkeypatch.setattr(journey, "headless_shell", headless_shell)
    monkeypatch.setattr(journey, "target_session", target_session)
    monkeypatch.setattr(journey, "samples_path", lambda: Path(os.devnull))
    runner = CliRunner()
    result = runner.invoke(journey.journey, ["claude-code"])
    assert result.exit_code == 0, result.output
    assert (launched, entered) == ([], [None])
    assert json.loads(result.stdout)["userEnd"] == "http"
    result = runner.invoke(journey.journey, ["claude-code", "--browser"])
    assert result.exit_code == 0, result.output
    assert (launched, entered) == ([True], [None, "browser"])
    assert json.loads(result.stdout)["userEnd"] == "browser"
