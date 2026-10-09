"""Live agent feedback trajectories, graded through Promptfoo.

Idle posts two successive comments; mid-turn posts during the setup turn. Each
trajectory uses an isolated home, page and state directory, and retains streams
and the admitted event log. Every expected comment must be picked up, receive an
accepted start (`leaf task start`) and a successful exact-input reply. The native
session must complete its work.
Latency remains diagnostic. Starts and replies come from the admitted page log;
native observations establish turn completion, not whether a command wrote an event.
"""

import json
from datetime import datetime
from functools import partial
from pathlib import Path

from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.thread import successful_replies

from leaf_dev.arms import (
    completed,
    hook_delivered,
    progress_start,
    read_trace,
    run_leaf,
    scratch,
    waits_started,
)
from leaf_dev.review_scenario import REQUEST, prepare
from leaf_dev.usability_eval import Case, Run, execute_live

# When each of a case's comments is posted: `idle` at the end of a turn, `running`
# once the setup turn has the page's URL.
CASES = {"idle": ("idle", "idle"), "mid-turn": ("running",)}
COMMENTS = (
    {
        "text": "Cut this paragraph to two sentences; the second one repeats the first.",
        "anchor": {"section": "triage-lede"},
    },
    {
        "text": "Rename this heading to ‘Why the migration blocks alone’.",
        "anchor": {"section": "triage-why"},
    },
)


def attempt(n: int) -> str:
    return f"delivery-eval-{n:04d}-attempt"


def moment(record: dict) -> float:
    return datetime.fromisoformat(record["received_at"]).timestamp()


def stop_blocked(record: dict) -> bool:
    """Whether one stream record is the Stop hook holding a turn open: any output
    it gives does, whether through a block or Claude Code's non-error context."""
    return (
        record.get("subtype") == "hook_response"
        and record["hook_event"] == "Stop"
        and bool(record["output"].strip())
    )


def run_session(
    arm: Path, case: str, run: Path, *, harness: str = ClaudeCodeHarness.name
) -> None:
    """Drive delivery timing through the same feedback loop as larger examples."""
    run.mkdir(parents=True, exist_ok=True)
    with scratch() as work:
        (run / "work-dir").write_text(f"{work}\n")
        page, state = work / "page", run / "state"
        prepare(arm, state, page)
        leaf = partial(run_leaf, arm, state)
        rounds = tuple(
            (dict(COMMENTS[n], kind="comment", attempt=attempt(n + 1)),)
            for n in range(len(CASES[case]))
        )
        scenario = Case(case, (REQUEST,), rounds=rounds, injection=CASES[case])
        try:
            execute_live(Run(case, arm, run, harness), scenario, work, page)
        finally:
            (run / "events.jsonl").write_text(
                leaf("page", "events", str(page), check=True).stdout
            )


def score(run: Path) -> list[dict]:
    """Read one run's page log and stream into one reading per comment it was sent."""
    events = read_events(run)
    stream = read_trace(run / "stream-1.jsonl")
    waits = {wait for r in stream for wait in waits_started(r)}
    timed_out = (run / "timed-out").exists()
    turns = [record for record in stream if record["type"] == "result"]
    session_completed = bool(turns) and all(completed([turn]) for turn in turns)
    readings = []
    for marker in (r for r in stream if r["type"] == "eval_post"):
        number = marker["round"]
        comment = next(e for e in events if e.get("attempt") == attempt(number))
        posted = datetime.fromisoformat(comment["ts"]).timestamp()
        pickup = next(
            (
                datetime.fromisoformat(e["ts"]).timestamp()
                for e in pickup_receipts(events, phase="opened", input_id=comment["id"])
            ),
            None,
        )
        progress = progress_start(events, comment["id"])
        replies = [
            datetime.fromisoformat(e["ts"]).timestamp()
            for e in successful_replies(events, comment["id"])
        ]
        claimed = (
            datetime.fromisoformat(progress["ts"]).timestamp() if progress else None
        )
        delivery, transport, ended = None, None, None
        turn_completed = False
        for record in stream[stream.index(marker) + 1 :]:
            if (
                record["type"] == "result"
                and claimed is not None
                and (
                    record.get("turn_id") == progress["turn"]
                    if progress.get("turn") and record.get("turn_id")
                    else moment(record) >= claimed
                )
            ):
                ended = moment(record)
                turn_completed = completed([record])
                break
            if (
                record.get("subtype") == "task_notification"
                and record["tool_use_id"] in waits
                and delivery is None
            ):
                delivery, transport = record, "notification"
            elif (stop_blocked(record) or hook_delivered(record)) and transport in (
                None,
                "notification",
            ):
                delivery = record
                transport = f"{record['hook_event'].lower()} hook".replace(
                    "userpromptsubmit", "prompt"
                )
        start = moment(marker)
        readings.append(
            {
                "comment": number,
                "injection": marker["injection"],
                "active_turn": marker["active_turn"],
                "after_completion": any(
                    record["type"] == "result"
                    for record in stream[: stream.index(marker)]
                ),
                "timed_out": timed_out,
                "turn_completed": turn_completed,
                "session_completed": session_completed,
                "transport": transport,
                "woken_s": since(delivery and moment(delivery), start),
                "pickup_s": since(pickup, posted),
                "claim_s": since(claimed, start),
                "reply_s": since(replies[0] if replies else None, posted),
                "turn_s": since(ended, start),
            }
        )
    return readings or [{"comment": None, "timed_out": timed_out}]


def since(t: float | None, origin: float) -> float | None:
    return None if t is None else round(t - origin, 1)


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    return [
        "completed",
        *[
            f"{check}-{n}"
            for n in range(1, len(CASES[case]) + 1)
            for check in (
                "injected-as-requested",
                "picked-up",
                "claimed",
                "replied",
                "turn-ended",
            )
        ],
    ]


def grade(case: str, readings: list[dict]) -> dict[str, bool]:
    """Missing or partial comments fail the same fixed checks as complete runs."""
    by_comment = {r["comment"]: r for r in readings if r["comment"] is not None}
    expected = set(range(1, len(CASES[case]) + 1))
    checks = {name: False for name in expected_checks(case)}
    checks["completed"] = (
        set(by_comment) == expected
        and len(readings) == len(expected)
        and all(
            not r["timed_out"] and r["turn_completed"] and r["session_completed"]
            for r in readings
        )
    )
    for n in expected:
        if n not in by_comment:
            continue
        r = by_comment[n]
        injection = CASES[case][n - 1]
        checks[f"injected-as-requested-{n}"] = (
            r["injection"] == injection
            and (r["after_completion"] is (injection == "idle"))
            and bool(r["active_turn"]) is (injection == "running")
        )
        checks[f"picked-up-{n}"] = r["pickup_s"] is not None
        checks[f"claimed-{n}"] = r["claim_s"] is not None
        checks[f"replied-{n}"] = r["reply_s"] is not None
        checks[f"turn-ended-{n}"] = r["turn_completed"]
    return checks


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    run_session(payload, case, work, harness=harness)
    readings = score(work)
    return {
        "output": json.dumps(readings),
        "metadata": {
            "checks": grade(case, readings),
            "diagnostics": {"comments": readings},
        },
    }
