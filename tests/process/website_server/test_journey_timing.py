"""The agent journey as a benchmark: its JSON sample per target, the chart of kept
samples, and how it times titles, progress and turn phases."""

import json
import time
from contextlib import contextmanager
from types import SimpleNamespace

from click.testing import CliRunner
from leaf_dev.commands import journey, journey_chart, verify_site

from process.website_server import (
    ROOT,
    TURN_LOG,
    _Read,
)


def test_the_journey_emits_one_json_sample_for_each_website_target(monkeypatch):
    """The gate's agent journey is also the benchmark: stdout is only its JSON sample,
    naming the harness and origin it ran on and the one step a website takes."""
    calls = []
    lifecycle = []

    @contextmanager
    def local():
        lifecycle.append("start")
        try:
            yield "http://127.0.0.1:8080", "a" * 40
        finally:
            lifecycle.append("stop")

    @contextmanager
    def worker():
        lifecycle.append("worker")
        yield verify_site.LocalWorker(
            "http://127.0.0.1:8787", "b" * 40, "test-worker", ROOT / ".tmp"
        )

    @contextmanager
    def browser():
        yield None

    closed = []

    class Context:
        def close(self):
            closed.append(True)

    def session(browser, release, *, origin, direct_agent):
        calls.append((origin, release, direct_agent))
        session = SimpleNamespace(context=Context(), url=origin, pause=time.sleep)
        return session, release or "served"

    monkeypatch.setattr(journey, "local_adapter", local)
    monkeypatch.setattr(journey, "local_worker", worker)
    monkeypatch.setattr(journey, "headless_shell", browser)
    monkeypatch.setattr(journey, "website_session", session)
    monkeypatch.setattr(
        journey,
        "run_journey",
        lambda end, version, records=None: {
            "version": version,
            "comment": {"eventIds": ["comment"]},
        },
    )
    runner = CliRunner()
    local_result = runner.invoke(journey.journey, ["website-adapter"])
    assert local_result.exit_code == 0, local_result.output
    sample = json.loads(local_result.stdout)
    [step] = sample.pop("steps")
    assert sample == {
        "target": "website-adapter",
        "harness": "website",
        "origin": "http://127.0.0.1:8080",
        "userEnd": "browser",
        "version": "a" * 40,
        "comment": {"eventIds": ["comment"]},
    }
    assert (step["step"], step["comments"]) == ("release", {})
    # A harness's options belong to its harness alone.
    refused = runner.invoke(journey.journey, ["website-adapter", "--http"])
    assert refused.exit_code == 2
    assert "a website's journey is its page in a browser" in refused.output
    refused = runner.invoke(journey.journey, ["website-adapter", "--hooks-module"])
    assert refused.exit_code == 2
    assert "--hooks-module is an option of claude-code" in refused.output
    for target in ("website-adapter", "claude-code", "pi"):
        refused = runner.invoke(journey.journey, [target, "--preview"])
        assert refused.exit_code == 2
        assert "--preview is an option of the codex targets" in refused.output
    # A remote journey needs no local build: the origin names its release.
    remote_result = runner.invoke(journey.journey, ["https://leaf-dev.example/"])
    assert remote_result.exit_code == 0, remote_result.output
    assert {
        key: value
        for key, value in json.loads(remote_result.stdout).items()
        if key in ("target", "harness", "origin", "version")
    } == {
        "target": "https://leaf-dev.example",
        "harness": "website",
        "origin": "https://leaf-dev.example",
        "version": "served",
    }
    # Through the local Worker the journey holds the container to the built release.
    worker_result = runner.invoke(journey.journey, ["website-worker"])
    assert worker_result.exit_code == 0, worker_result.output
    assert lifecycle == ["start", "stop", "worker"]
    # Each journey closes the browser context its session opened.
    assert closed == [True, True, True]
    assert calls == [
        ("http://127.0.0.1:8080", "a" * 40, True),
        ("https://leaf-dev.example", None, False),
        ("http://127.0.0.1:8787", "b" * 40, False),
    ]
    # Each sample is also kept on this machine, outside the checkout.
    kept = journey.samples_path().read_text().splitlines()
    assert [json.loads(line)["origin"] for line in kept] == [
        "http://127.0.0.1:8080",
        "https://leaf-dev.example",
        "http://127.0.0.1:8787",
    ]


def test_the_journey_chart_draws_each_targets_latest_version_from_kept_samples():
    """`journey-chart` charts the samples the journey kept, so a later reading needs
    no transcription: each target's latest version only, each sign a sample saw."""

    def sample(target, version, titled, picked_up, progress, replied, **named):
        comment = {
            "sinceAdmissionMs": {
                "queued": None,
                "pickedUp": picked_up,
                "started": None,
                "titled": titled,
                "progress": progress,
                "published": replied - 500,
                "replied": replied,
            },
            "sinceSendMs": {"responseVisible": replied + 1000},
        }
        return {
            "target": target,
            "harness": target.split("-")[0],
            **named,
            "version": version,
            "comment": comment,
            "steps": [{"step": "release", "seconds": replied / 1000, "comments": {}}],
        }

    old, new = "a" * 40, "b" * 40 + "+working-tree"
    adapter = "website-adapter"
    samples = [
        sample("claude-code", old, 1800, 7000, None, 17500),
        sample("codex-app-server", old, 4700, 200, None, 69600),
        sample("claude-code", new, 1300, 7000, 6900, 18600),
        sample("codex-app-server", old, 4600, 300, None, 102900),
        # The hooks module is a row of its own, at its own latest version.
        sample("claude-code", old, 1300, 7000, 6900, 15000, hooksModule=True),
        # Each local run serves on a port of its own, but is the same target.
        sample(adapter, old, 900, 300, None, 30000, origin="http://127.0.0.1:8080"),
        sample(adapter, new, 800, 300, None, 25000, origin="http://127.0.0.1:9090"),
    ]
    # A sample kept before the journey ran its steps is left out.
    unstepped = sample("codex", new, 900, 300, None, 9000)
    del unstepped["steps"]
    path = journey.samples_path()
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(s) + "\n" for s in [*samples, unstepped]))
    result = CliRunner().invoke(journey_chart.journey_chart)
    assert result.exit_code == 0, result.output
    markup = result.stdout
    assert markup.startswith('<lf-chart id="journey-signs"')
    rows = journey_chart.chart_rows([*samples, unstepped])
    assert {r["row"] for r in rows} == {
        "Claude Code at bbbbbbbb+working-tree",
        "Claude Code with the hooks module at aaaaaaaa",
        "Codex App Server at aaaaaaaa",
        "website-adapter at bbbbbbbb+working-tree",
    }
    # Older versions are left out; Codex's two runs of one version stay.
    assert sorted(r["s"] for r in rows if r["sign"] == "reply") == [
        15.0,
        18.6,
        25.0,
        69.6,
        102.9,
    ]
    # A step the run never reached draws no dot.
    assert [r["row"] for r in rows if r["sign"] == "progress"] == [
        "Claude Code at bbbbbbbb+working-tree",
        "Claude Code with the hooks module at aaaaaaaa",
    ]
    assert json.dumps(rows) in markup


def test_a_title_written_after_the_reply_is_still_timed(tmp_path):
    """The page server titles a thread beside the agent's turn, so the title can land
    after the reply that ended the turn's wait; the journey reads on for it rather
    than reporting the title as never written. The state it reads is the one a page
    server serves, since the journey reads titles from it."""
    from leaf.event_log import append_event
    from leaf.thread import title_event
    from leaf_dev.arms import PageClient, serving
    from leaf_dev.review_scenario import prepare

    state, page_dir = tmp_path / "state", tmp_path / "page"
    prepare(ROOT, state, page_dir)
    with serving(ROOT, state, page_dir) as url:
        client = PageClient(url)
        client.post(
            {
                "kind": "comment",
                "revision": client.state()["active"]["revision"],
                "attempt": "journey-title-wait",
                "text": "Is the release recorded?",
            }
        )
        untitled = client.state()
        [comment] = [
            e for e in untitled["events"] if e.get("attempt") == "journey-title-wait"
        ]
        assert journey.title(untitled["events"], comment["id"]) is None
        paused = []

        def pause(seconds):
            # The title lands while the journey waits on, as the page server's does.
            if not paused:
                append_event(
                    page_dir,
                    title_event(
                        comment["id"],
                        "Release recorded",
                        {"agent": "Agent", "session": "journey-title"},
                    ),
                )
            paused.append(seconds)

        class Context:
            request = SimpleNamespace(get=lambda *args, **kwargs: _Read(client.state()))

        session = journey.Session(
            Context(), None, [], url, url, untitled, {}, None, pause=pause
        )
        events = journey.await_title(
            journey.BrowserEnd(session), comment["id"], untitled
        )["events"]
    assert paused == [1]
    assert journey.title(events, comment["id"]) == "Release recorded"
    steps = journey.recorded_steps(events, comment, None)
    assert steps["titled"] is not None and steps["titled"] > 0
    assert steps["published"] is None


def test_a_progress_update_is_timed_apart_from_the_answer():
    """Transport and work milestones name this exact input; unrelated earlier
    pickups and starts cannot count. Ephemeral progress is timed separately from
    the durable reply that answers."""
    comment, _title, reply = TURN_LOG
    progress = {
        "kind": "reply",
        "author": "agent",
        "id": "test-progress",
        "parent": comment["id"],
        "text": "Recording the release on the board.",
        "ephemeral": True,
        "ts": "2026-10-04T12:00:03.000-07:00",
    }
    assert journey.deployment_answer([progress], comment["id"]) is None
    assert journey.deployment_answer([progress, reply], comment["id"]) is reply
    published = {"activated_at": "2026-10-04T19:00:12+00:00"}
    transport = [
        {
            "kind": "pickup",
            "events": ["other-input"],
            "phase": "opened",
            "ts": "2026-10-04T12:00:00.500-07:00",
        },
        {"kind": "start", "item": "other-input", "ts": "2026-10-04T12:00:00.750-07:00"},
        {
            "kind": "pickup",
            "events": [comment["id"]],
            "phase": "queued",
            "ts": "2026-10-04T12:00:01.000-07:00",
        },
        {
            "kind": "pickup",
            "events": [comment["id"]],
            "phase": "opened",
            "ts": "2026-10-04T12:00:02.000-07:00",
        },
        {"kind": "start", "item": comment["id"], "ts": "2026-10-04T12:00:02.500-07:00"},
    ]
    for index, event in enumerate(transport):
        event["id"] = f"transport-{index}"
    assert journey.recorded_steps(
        [comment, *transport, progress, reply], comment, published
    ) == {
        "queued": 1.0,
        "pickedUp": 2.0,
        "started": 2.5,
        "titled": None,
        "progress": 3.0,
        "published": 12.0,
        "replied": 12.5,
    }

    # Addressed progress takes the input in hand atomically in the current log.
    inline = {**progress, "start": {"item": comment["id"]}}
    # Progress on another input, in that input's own thread.
    other = {**comment, "id": "other-input", "ts": "2026-10-04T12:00:00.900-07:00"}
    unrelated = {
        **inline,
        "id": "other-progress",
        "parent": "other-input",
        "start": {"item": "other-input"},
        "ts": "2026-10-04T12:00:01.000-07:00",
    }
    assert journey.recorded_steps(
        [comment, other, unrelated, inline, reply], comment, published
    ) == {
        "queued": None,
        "pickedUp": None,
        "started": 3.0,
        "titled": None,
        "progress": 3.0,
        "published": 12.0,
        "replied": 12.5,
    }


def test_an_agent_turn_splits_into_delivery_model_and_tool_phases():
    """A harness journey splits the turn it ran into the phases a reader adds up:
    the wait for the turn to start, each model call, and each tool phase with its
    calls, which end only when every call started together has returned."""

    def at(seconds: float) -> str:
        return f"2026-10-04T12:00:{seconds:06.3f}-07:00"

    def call(seconds: float, *uses: tuple[str, str]) -> dict:
        content = [
            {"type": "tool_use", "id": id, "name": "Bash", "input": {"command": cmd}}
            for id, cmd in uses
        ]
        return {
            "type": "assistant",
            "message": {"content": content},
            "received_at": at(seconds),
        }

    def result(seconds: float, id: str) -> dict:
        content = [{"type": "tool_result", "tool_use_id": id}]
        return {
            "type": "user",
            "message": {"content": content},
            "received_at": at(seconds),
        }

    comment, _, reply = TURN_LOG
    stream = [
        {"type": "system", "subtype": "hook_response", "received_at": at(0.2)},
        result(0.3, "running"),
        {"type": "system", "subtype": "init", "received_at": at(0.5)},
        {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": ""}]},
            "received_at": at(2.0),
        },
        call(4.0, ("start", "leaf task start . c1 x"), ("read", "cat threads.md")),
        result(4.1, "read"),
        result(5.0, "start"),
        call(7.0, ("edit", "leaf page check .")),
        result(8.0, "edit"),
        call(12.0, ("reply", "leaf response reply 62af9e31:0:test-comment")),
    ]
    # Delivery ends at the opened pickup, not at the first record the harness sends
    # after admission: a tool result of a turn already running is no delivery.
    assert journey.turn_phases(stream, comment["ts"], at(0.5), reply["ts"]) == [
        {"phase": "delivery", "startMs": 0, "ms": 500},
        {"phase": "model", "startMs": 500, "ms": 3500},
        {
            "phase": "tool",
            "startMs": 4000,
            "ms": 1000,
            "calls": ["leaf task start . c1 x", "cat threads.md"],
        },
        {"phase": "model", "startMs": 5000, "ms": 2000},
        {"phase": "tool", "startMs": 7000, "ms": 1000, "calls": ["leaf page check ."]},
        {"phase": "model", "startMs": 8000, "ms": 4000},
        {
            "phase": "tool",
            "startMs": 12000,
            "ms": 500,
            "calls": ["leaf response reply 62af9e31:0:test-comment"],
        },
    ]
    assert journey.turn_phases(stream, comment["ts"], None, reply["ts"]) == []


def test_journey_reads_and_times_inline_message_title():
    comment, _title, reply = TURN_LOG
    titled_reply = {**reply, "title": "Release recorded"}
    assert journey.title([comment, titled_reply], comment["id"]) == "Release recorded"
    assert (
        journey.recorded_steps(
            [comment, titled_reply], comment, {"activated_at": reply["ts"]}
        )["titled"]
        == 12.5
    )
    titled_comment = {**comment, "title": "Initial release"}
    assert (
        journey.recorded_steps(
            [titled_comment, titled_reply],
            titled_comment,
            {"activated_at": reply["ts"]},
        )["titled"]
        == 0
    )


def test_journey_title_timing_accepts_admitted_action_dependencies():
    comment, _title, reply = TURN_LOG
    action = {
        "kind": "action",
        "id": "test-pick",
        "widget": "options",
        "action": "choose",
        "revision": 1,
        "ts": "2026-10-04T12:00:01.000-07:00",
        "meaning": {"unit": "options", "depends": ["child"], "scope": "page"},
    }
    events = [comment, action, {**reply, "title": "Release recorded"}]
    assert (
        journey.recorded_steps(events, comment, {"activated_at": reply["ts"]})["titled"]
        == 12.5
    )
