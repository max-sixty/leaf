"""Delivery trajectories on the shared live eval session.

The YAML owns scenarios and comments; the repair fixture owns its result check.
All cases use LiveSession and the response-times query. A fixed observation window
keeps unanswered inputs in the evidence; latency is diagnostic, not a pass threshold.
Promptfoo owns arms, repetitions and reports. Native traces belong to LiveSession.
"""

import json
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.thread import successful_replies
from leaf_dev import ROOT
from leaf_dev.arms import LiveChild, LiveSession, PageClient, run_leaf, scratch
from leaf_dev.commands.response_times import distribution, page_timings
from leaf_dev.eval_cases import definition
from leaf_dev.review_scenario import prepare

DEFINITION = definition("delivery_eval")
CASES = DEFINITION["cases"]


def comments(case: str) -> list[dict]:
    inputs = CASES[case]["inputs"]
    return (
        DEFINITION["workload"]["comments"]
        if inputs.get("workload")
        else [
            dict(comment, name=str(n + 1), injection=injection)
            for n, (comment, injection) in enumerate(
                zip(
                    inputs.get("comments", DEFINITION["comments"]),
                    inputs["injection"],
                    strict=False,
                )
            )
        ]
    )


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    return [
        "injected",
        *[f"replied-{comment['name']}" for comment in comments(case)],
        *[f"reached-{c['name']}" for c in comments(case) if "during" in c],
        *(["task-correct"] if CASES[case]["inputs"].get("workload") else []),
    ]


def operation_times(task: Path) -> dict[str, float]:
    """When the workload fixture first logged each operation."""
    log = task / "operations.jsonl"
    rows = map(json.loads, log.read_text().splitlines()) if log.exists() else ()
    times = {}
    for row in rows:
        times.setdefault(row["operation"], row["at"])
    return times


def capture_measurements(page: Path, injections: list[dict], until: datetime) -> dict:
    """Select the scenario's exact inputs from the canonical timing query."""
    ids = {row["input_id"] for row in injections}
    timings = page_timings(page, since=None, until=until)
    recorded = {row["input_id"]: row for row in timings["samples"]}
    samples = [
        recorded.get(
            row["input_id"],
            {"input_id": row["input_id"], "milestones": {}, "observed_for_s": None},
        )
        for row in injections
    ]
    return {
        "observed_until": until.isoformat(),
        "samples": samples,
        "unrecorded_inputs": sorted(ids - recorded.keys()),
        "first_reply": distribution(samples, "first_reply"),
        "answered": distribution(samples, "answered"),
    }


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    moves = comments(case)
    workload = DEFINITION["workload"] if CASES[case]["inputs"].get("workload") else None
    observation = (workload or DEFINITION)["observation_seconds"]
    checks = dict.fromkeys(expected_checks(case), False)
    diagnostics, texts, injections = {}, {}, []
    state = work / "state"
    with scratch(payload, state=state) as cwd:
        page = cwd / "page"
        prepare(payload, state, page)
        if workload:
            source = ROOT / "evals" / workload["fixture"]
            shutil.copytree(source, cwd / "suite_lab")
        cutoff = datetime.now(UTC)
        try:
            with LiveSession(
                LiveChild(
                    cwd,
                    DEFINITION["prompts"]["initial"],
                    "--plugin-dir",
                    str(payload),
                    stderr=work / "stderr.txt",
                    limit=300 + observation,
                    timed_out=work / "timed-out",
                    dirs=[payload],
                    env={"XDG_STATE_HOME": str(state)},
                    harness=harness,
                ),
                work / "stream.jsonl",
                watch=(payload, state, page),
            ) as live:
                try:
                    preparing = True
                    started = None
                    setup_deadline = time.monotonic() + 300
                    for record in live.records(idle=0.1):
                        if started is None and time.monotonic() >= setup_deadline:
                            raise TimeoutError(
                                "The scenario never reached its injection condition"
                            )
                        if not live.url:
                            continue
                        if workload and preparing:
                            if record and record.get("type") == "result":
                                live.send(workload["prompt"])
                                preparing = False
                            continue
                        if started is None:
                            ready = (
                                (cwd / "suite_lab/operations.jsonl").exists()
                                if workload
                                else live.running or live.answered > 0
                            )
                            if not ready:
                                continue
                            started = time.monotonic()
                            cutoff = datetime.now(UTC) + timedelta(seconds=observation)
                        elapsed = time.monotonic() - started
                        if elapsed >= observation:
                            break
                        if len(injections) == len(moves):
                            continue
                        move = moves[len(injections)]
                        ready = (
                            (
                                move["during"][0] in operation_times(cwd / "suite_lab")
                                if "during" in move
                                else elapsed >= move["after_seconds"]
                            )
                            if workload
                            else (
                                live.running
                                if move["injection"] == "running"
                                else not live.running
                                and time.monotonic() - live.heard >= 3
                                and (
                                    not injections
                                    or successful_replies(
                                        read_events(page), injections[-1]["input_id"]
                                    )
                                )
                            )
                        )
                        if not ready:
                            continue
                        client = PageClient(live.url)
                        # The log admits a retry key of 16 to 128 characters, and a
                        # comment's name may be a single character.
                        attempt = f"delivery-eval-comment-{move['name']}"
                        current = client.post(
                            {
                                "kind": "comment",
                                "revision": client.state()["active"]["revision"],
                                "attempt": attempt,
                                "text": move["text"],
                                **(
                                    {"anchor": move["anchor"]}
                                    if "anchor" in move
                                    else {}
                                ),
                            }
                        )
                        event = next(
                            e for e in current["events"] if e.get("attempt") == attempt
                        )
                        injection = {
                            "name": move["name"],
                            "input_id": event["id"],
                            "turn_active": live.running,
                        }
                        injections.append(injection)
                        live.note(
                            {
                                "type": "eval_post",
                                **injection,
                                "received_at": event["ts"],
                            }
                        )
                finally:
                    cutoff = min(cutoff, datetime.now(UTC))
                    shutil.copy(page / "index.html", work / "index.html")
                    texts["page"] = (work / "index.html").read_text()
                    if workload:
                        shutil.copytree(cwd / "suite_lab", work / "task")
                        diagnostics["task_snapshot_at"] = datetime.now(UTC).isoformat()
        except BaseException as error:
            diagnostics["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            try:
                diagnostics["injections"] = injections
                diagnostics["timings"] = capture_measurements(page, injections, cutoff)
                checks["injected"] = len(injections) == len(moves) and all(
                    workload is not None
                    or row["turn_active"] == (move["injection"] == "running")
                    for row, move in zip(injections, moves, strict=False)
                )
                events = [
                    e
                    for e in read_events(page)
                    if datetime.fromisoformat(e["ts"]) <= cutoff
                ]
                opened = {
                    sample["input_id"]: sample["milestones"].get("opened")
                    for sample in diagnostics["timings"]["samples"]
                }
                for row, move in zip(injections, moves, strict=False):
                    replies = successful_replies(events, row["input_id"])
                    texts[row["name"]] = "\n\n".join(reply["text"] for reply in replies)
                    checks[f"replied-{row['name']}"] = bool(replies)
                    if "during" in move:
                        # The agent took the comment before the operation it was
                        # posted during had ended.
                        ended = operation_times(work / "task").get(move["during"][1])
                        at = opened[row["input_id"]]
                        checks[f"reached-{row['name']}"] = at is not None and (
                            ended is None
                            or datetime.fromisoformat(at["at"]).timestamp() < ended
                        )
                for name in ("events.jsonl", "observations.jsonl"):
                    if (page / name).exists():
                        shutil.copy(page / name, work / name)
                if workload:
                    checked = subprocess.run(
                        [
                            "python3",
                            str(source.parent / "check.py"),
                            str(work / "task"),
                            str(cutoff.timestamp()),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    checks["task-correct"] = checked.returncode == 0
                    diagnostics["task_result"] = {
                        "exit_code": checked.returncode,
                        "stdout": checked.stdout,
                        "stderr": checked.stderr,
                    }
            finally:
                (work / "diagnostics.json").write_text(
                    json.dumps(diagnostics, indent=2)
                )
                run_leaf(payload, state, "server", "stop", str(page))
    return {
        "output": json.dumps(texts),
        "metadata": {"checks": checks, "diagnostics": diagnostics, "texts": texts},
    }
