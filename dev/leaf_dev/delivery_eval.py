"""Live agent feedback trajectories, graded through Promptfoo.

Idle posts two successive comments; mid-turn posts during the setup turn. Each
trajectory uses an isolated home, page and state directory, and retains streams
and the admitted event log. Every expected comment must be picked up, receive an
accepted start (`leaf task start`) and a reply in its handling turn, and complete that turn.
Latency and work before the start remain diagnostics: a Bash call can contain
several operations, so its trace alone cannot prove their internal order.
"""

import json
import re
from datetime import datetime
from functools import partial
from pathlib import Path

from leaf.event_log import read_events

from leaf_dev.arms import (
    accepted_starts,
    blocks,
    completed,
    hook_delivered,
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


def run_session(arm: Path, case: str, run: Path, *, harness: str = "cc") -> None:
    """Drive delivery timing through the same feedback loop as larger examples."""
    run.mkdir(parents=True, exist_ok=True)
    work = scratch()
    (run / "work-dir").write_text(f"{work}\n")
    page, state = work / "page", run / "state"
    prepare(arm, state, page)
    leaf = partial(run_leaf, arm, state)
    rounds = tuple(
        (dict(COMMENTS[n], kind="comment", attempt=attempt(n + 1)),)
        for n in range(len(CASES[case]))
    )
    scenario = Case(case, (REQUEST,), rounds=rounds, injection=CASES[case])
    execute_live(Run(case, arm, run, harness), scenario, work, page)
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
                for e in events
                if e["kind"] == "pickup"
                and e["phase"] == "opened"
                and comment["id"] in e["events"]
            ),
            None,
        )
        replies = [
            datetime.fromisoformat(e["ts"]).timestamp()
            for e in events
            if e["kind"] == "reply" and e.get("parent") == comment["id"]
        ]
        # From the post to the turn's end: what carried the comment in, what the
        # agent ran before claiming its work, and the claim.
        delivery, route, before_claim, claimed, ended = None, None, [], None, None
        turn_completed = False
        handling = False
        accepted = accepted_starts(stream, comment["id"])
        for record in stream[stream.index(marker) + 1 :]:
            handling = handling or any(
                b.get("type") == "tool_result" and b.get("tool_use_id") in accepted
                for b in blocks([record])
            )
            if record["type"] == "result" and handling:
                ended = moment(record)
                turn_completed = completed([record])
                break
            if not claimed:
                for block in blocks([record]):
                    if (
                        block.get("type") == "tool_result"
                        and block["tool_use_id"] in accepted
                    ):
                        claimed = moment(record)
                    elif (
                        block.get("type") == "tool_use" and block["id"] not in accepted
                    ):
                        before_claim += [block["input"].get("command") or block["name"]]
            if (
                record.get("subtype") == "task_notification"
                and record["tool_use_id"] in waits
                and not delivery
            ):
                delivery, route = record, "notification"
            elif (
                (stop_blocked(record) or hook_delivered(record))
                and route in (None, "notification")
                and not claimed
            ):
                # A hook that brings the comment in, or a Stop hook holding the turn
                # open with it unread, carried it, even after a notification.
                delivery, before_claim = record, []
                route = f"{record['hook_event'].lower()} hook".replace(
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
                "route": route,
                "woken_s": since(delivery and moment(delivery), start),
                # The page log stamps whole seconds.
                "pickup_s": since(pickup, posted),
                "claim_s": since(claimed, start),
                "reply_s": since(replies[0] if replies else None, posted),
                # No reply of a later turn falls at or before this one's end.
                "done_s": since(
                    max((r for r in replies if ended and r <= ended), default=None),
                    posted,
                ),
                "turn_s": since(ended, start),
                "before_claim": [short(c) for c in before_claim],
                "claim_commands": [
                    b["input"]["command"]
                    for b in blocks(stream)
                    if b.get("type") == "tool_use" and b["id"] in accepted
                ],
            }
        )
    return readings or [{"comment": None, "timed_out": timed_out}]


def since(t: float | None, origin: float) -> float | None:
    return None if t is None else round(t - origin, 1)


def short(ran: str) -> str:
    """One command with its directories dropped, so a table can show it."""
    return re.sub(r"(?<![\w$])/[^\s;&|]*/", "", ran)


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
        checks[f"replied-{n}"] = r["done_s"] is not None
        checks[f"turn-ended-{n}"] = r["turn_completed"]
    return checks


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = "cc",
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
