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

import pytest
from interact_support import STATED_TIMEOUT
from leaf.interaction_log import read_interactions
from leaf_dev import journey_claude_code, journey_pi
from leaf_dev.commands import journey, journey_chart
from leaf_dev.page_fixtures import record_run_context
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
        SimpleNamespace(
            context=SimpleNamespace(request=request),
            url="https://leaf.page/",
            pause=lambda _: None,
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
            shown.append(arg["id"])
            # The row shows the reply first; its message comes into view a read later.
            message = 1_000_000 + 9_520 if len(shown) > 1 else None
            return {"at": 1_000_000 + 9_500, "by": "row", "message": message}

    url = "http://127.0.0.1:1/?t=token"
    user_end = (
        journey.BrowserEnd(journey.Session(None, Page(), [], url, url, {}, {}, None))
        if end == "browser"
        else journey.HttpEnd(url, Path("page"), time.sleep)
    )
    user = journey.User(user_end, "v", lambda: events, terminal)
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
    assert [phase["phase"] for phase in reading["turn"]] == [
        "delivery",
        "model",
        "tool",
        "model",
    ]
    assert reading["turn"][0] == {"phase": "delivery", "startMs": 0, "ms": 1000}
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
    content may be a bare string; the journey reads both, and nothing else."""
    session = "6f1c"
    path = tmp_path / ".claude" / "projects" / "-private-work" / f"{session}.jsonl"
    path.parent.mkdir(parents=True)
    lines = [
        {"type": "user", "timestamp": at(1), "message": {"content": "Serve it."}},
        {"type": "attachment", "timestamp": at(1.5), "attachment": {}},
        {
            "type": "assistant",
            "timestamp": at(2),
            "message": {
                "content": [
                    {"type": "tool_use", "id": "b", "name": "Bash", "input": {}}
                ]
            },
        },
        {"type": "system", "timestamp": at(2.5), "subtype": "stop_hook_summary"},
    ]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert journey_claude_code.transcript(tmp_path, session) == [
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "Serve it."}]},
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
    ]


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
    assert journey.turn_phases(records, at(0), at(3), at(6)) == [
        {"phase": "delivery", "startMs": 0, "ms": 3000},
        {"phase": "tool", "startMs": 3000, "ms": 2000, "calls": ["sleep 4"]},
        {"phase": "model", "startMs": 5000, "ms": 1000},
    ]


def test_pis_events_give_the_turn_phases(monkeypatch):
    """Pi reports its runs and tool calls as RPC events; the journey keeps its tool
    calls as the records `turn_phases` reads, and tracks the shell commands
    running."""
    seconds = count(3)
    monkeypatch.setattr(journey_pi, "now", lambda: at(next(seconds)))
    pi = journey_pi.Pi.__new__(journey_pi.Pi)
    journey.Terminal.__init__(pi)
    pi.running, pi.settled, pi.closed_watches = False, 0, 0
    for event in (
        {"type": "agent_start"},
        {
            "type": "tool_execution_start",
            "toolCallId": "s",
            "toolName": "bash",
            "args": {"command": "sleep 1"},
        },
        {"type": "tool_execution_end", "toolCallId": "s"},
        {"type": "leaf_watch_closed", "code": 0},
        {"type": "agent_settled"},
    ):
        pi._hear(event)
    assert pi.commands == ["sleep 1"] and pi.running_commands == {}
    assert (pi.settled, pi.closed_watches, pi.idle()) == (1, 1, True)
    phases = journey.turn_phases(pi.records(), at(0), at(2), at(6))
    assert phases == [
        {"phase": "delivery", "startMs": 0, "ms": 2000},
        {"phase": "model", "startMs": 2000, "ms": 1000},
        {"phase": "tool", "startMs": 3000, "ms": 1000, "calls": ["sleep 1"]},
        {"phase": "model", "startMs": 4000, "ms": 2000},
    ]


def test_the_release_ask_over_http_is_the_shared_check(tmp_path):
    """Over HTTP the release ask is posted as the page's tab posts one, and the same
    check as in a browser waits on its turn, title and answer, requiring a published
    revision naming the release; it reads nothing a browser would. A step's comment
    is posted on its section."""
    from leaf.event_log import append_event, read_events
    from leaf.thread import post_reply, title_event
    from leaf_dev import ROOT
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
            {"to": comment["id"], "for": comment["id"]},
            "Recorded.",
            identity=agent,
        )

    with serving(ROOT, state, page) as url:
        reading = journey.run_journey(journey.HttpEnd(url, page, pause), version)
        step = post(url, "mid-turn")
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
    def target_session(browser, target, release, *, hooks_module, sandbox, preview):
        entered.append(browser)
        end = (
            journey.HttpEnd("http://127.0.0.1:1/?t=t", Path("page"), time.sleep)
            if browser is None
            else journey.BrowserEnd(
                journey.Session(None, None, [], "u", "u", {}, {}, None)
            )
        )
        end.close = lambda: None
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
