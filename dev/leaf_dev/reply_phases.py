"""Where the time from a user's comment to the agent's reply went, read from the page's
log and the harness's record of the session.

A reply is timed from the comment's admission to the reply's, both on the page
server's clock. The harness's record splits that span into phases (`turn_phases`):

- `busy`: the harness was in a turn at the admission, on other work, until that
  turn's next tool boundary, where every call out has returned, or its end, where
  the harness can take the comment. Only a comment that arrives while the harness
  works has it;
- `delivery`: Leaf handing the comment over, until the harness records it in the
  agent's context (its opened pickup), whether that opened a turn or entered a
  running one. Where the agent runs tools before that pickup, the harness handed it
  a pointer that it read and acknowledged itself, as on Codex App Server, so
  delivery ends at the boundary where the harness took it (the busy turn's tool
  boundary, or the start of the turn that took it) and that work is the agent's;
- then `model`, from a turn's start or the last tool result to the next tool call
  or the turn's end; `tool`, from that call until every call it started has
  returned, each naming its calls; and `idle`, from a turn's end to the next turn's
  start, as where the agent waits on a background task before replying.

`reply_breakdown` sums them into the two numbers a reply budget reads: the whole
reply, and Leaf's share of it, delivery plus the time Leaf's own commands took,
which each `leaf` command records in the page it acted on
(`leaf.interaction_log.record_command`). The rest is the harness's other work, the
model, the agent's own reads and edits, and idle time. It also groups the model phases into the model calls the
harness made, each with the calls it issued, since a model call is the unit a
shorter reply would have to save.

The records are the journey's normalized form, each stamped `received_at`:
`assistant` and `user` records whose content holds `tool_use` and `tool_result`
parts; a `model_response` where each model response ended, at its last tool call or
after the calls it started returned, as the harness reports it; and `turn_start` and
`turn_end` where the harness began and finished a turn. A harness that streams its
session stamps a record when the journey hears it; Claude Code's transcript stamps
each record itself (`claude_code_records`).
"""

import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path

# The directory change an agent puts before a command, which says nothing of it.
CD_PREFIX = re.compile(r"^cd \S+ && ")
# How much of each call a reading keeps.
SHOWN = 200


def instant(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def call_label(part: dict) -> str:
    """What a `tool_use` part ran: its shell command after any leading directory
    change, the `leaf` words a Leaf MCP tool ran, or the tool's name."""
    arguments = part["input"]
    if "command" in arguments:
        return CD_PREFIX.sub("", arguments["command"])
    if part["name"].startswith("mcp__leaf__") and "args" in arguments:
        return shlex.join(["leaf", *arguments["args"]])
    return part["name"]


def _phases(
    records: list[dict], admitted: str, picked_up: str, replied: str
) -> list[tuple[str, float, float, list[str]]]:
    """The phases as (phase, since, until, calls) in seconds since the epoch."""
    start, began, end = instant(admitted), instant(picked_up), instant(replied)
    timed = [
        (instant(record["received_at"]), record)
        for record in records
        if instant(record["received_at"]) <= end
    ]

    def holds(record: dict, kind: str) -> bool:
        return record["type"] in ("assistant", "user") and any(
            part["type"] == kind for part in record["message"]["content"]
        )

    def first(after: float, until: float, *kinds: str) -> float | None:
        return next(
            (
                at
                for at, record in timed
                if after < at <= until
                and (record["type"] in kinds or any(holds(record, k) for k in kinds))
            ),
            None,
        )

    def drained(after: float, until: float) -> float:
        """The first tool boundary after `after` and by `until` where no call is
        out, or the turn's end, whichever comes first; `after` where neither does."""
        out: set[str] = set()
        for at, record in timed:
            if at > until:
                break
            if after < at and record["type"] == "turn_end":
                return at
            if record["type"] in ("turn_start", "turn_end"):
                # A call an interrupted turn left out is no longer running.
                out.clear()
            if record["type"] not in ("assistant", "user"):
                continue
            for part in record["message"]["content"]:
                if part["type"] == "tool_use":
                    out.add(part["id"])
                elif part["type"] == "tool_result":
                    out.discard(part["tool_use_id"])
                    if after < at and not out:
                        return at
        return after

    def turns_until(until: float) -> list[str]:
        return [
            record["type"]
            for at, record in timed
            if at <= until and record["type"] in ("turn_start", "turn_end")
        ]

    phases: list[tuple[str, float, float, list[str]]] = []
    boundary = start
    if turns_until(start)[-1:] == ["turn_start"]:
        boundary = drained(start, began)
        if boundary > start:
            phases.append(("busy", start, boundary, []))
        took = boundary if boundary > start else None
    else:
        took = first(start, began, "turn_start")
    idle = False
    if took is not None and first(took, began, "tool_use") is not None:
        # The agent worked before its pickup, so it had the comment from where the
        # harness took it, which may be the end of the busy turn.
        if took > boundary:
            phases.append(("delivery", boundary, took, []))
        began = took
        idle = turns_until(began)[-1:] == ["turn_end"]
    else:
        phases.append(("delivery", boundary, began, []))
    # The calls still out when the comment was picked up.
    out: dict[str, str] = {}
    for at, record in timed:
        if at > began:
            continue
        if record["type"] in ("turn_start", "turn_end"):
            out.clear()
        if record["type"] not in ("assistant", "user"):
            continue
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                out[part["id"]] = call_label(part)
            elif part["type"] == "tool_result":
                out.pop(part["tool_use_id"], None)
    phase = "idle" if idle else "tool" if out else "model"
    since, pending, calls = began, set(out), list(out.values())
    for at, record in timed:
        if at <= began:
            continue
        if record["type"] == "turn_end" and phase != "idle":
            phases.append((phase, since, at, calls if phase == "tool" else []))
            phase, since, pending = "idle", at, set()
        elif record["type"] == "turn_start" and phase == "idle":
            phases.append(("idle", since, at, []))
            phase, since = "model", at
        if record["type"] not in ("assistant", "user"):
            continue
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                if phase != "tool":
                    phases.append((phase, since, at, []))
                    phase, since, calls = "tool", at, []
                pending.add(part["id"])
                calls.append(call_label(part))
            elif part["type"] == "tool_result" and part["tool_use_id"] in pending:
                pending.remove(part["tool_use_id"])
                if not pending:
                    phases.append(("tool", since, at, calls))
                    phase, since = "model", at
    phases.append((phase, since, end, calls if phase == "tool" else []))
    return phases


def turn_phases(
    records: list[dict], admitted: str, picked_up: str | None, replied: str
) -> list[dict]:
    """The agent's work on a comment from its admission to its reply, as consecutive
    phases in milliseconds from the admission (the module's header lists them). A
    comment that enters a running turn while a call is out starts in a tool phase
    from its pickup until those calls return. A comment never picked up has no
    phases."""
    if picked_up is None:
        return []
    start = instant(admitted)
    return [
        {
            "phase": phase,
            "startMs": round((since - start) * 1000),
            "ms": round((until - since) * 1000),
            **({"calls": [call[:SHOWN] for call in calls]} if phase == "tool" else {}),
        }
        for phase, since, until, calls in _phases(records, admitted, picked_up, replied)
    ]


def command_spans(
    commands: list[dict], admitted: str, replied: str
) -> list[tuple[float, float]]:
    """When Leaf's `commands` records ran on a reply: each that started after the
    comment's admission and before the reply's, up to the reply's admission, since
    the command that replies exits after it. A command running from before the
    comment, as a page server does, is no part of it."""
    start, end = instant(admitted), instant(replied)
    return [
        (began, min(instant(command["ts"]), end))
        for command in commands
        if start <= (began := instant(command["started"])) < end
    ]


def covered(spans: list[tuple[float, float]]) -> float:
    """The seconds the union of `spans` covers, so overlapping ones count once."""
    total, reached = 0.0, float("-inf")
    for since, until in sorted(spans):
        if until > reached:
            total += until - max(since, reached)
            reached = until
    return total


def leaf_commands_ms(commands: list[dict], admitted: str, replied: str) -> int:
    """The elapsed time Leaf's commands took on a reply (`command_spans`)."""
    return round(covered(command_spans(commands, admitted, replied)) * 1000)


def reply_breakdown(
    records: list[dict],
    commands: list[dict],
    admitted: str,
    picked_up: str | None,
    replied: str,
) -> dict | None:
    """The whole reply, Leaf's share of it, and its model calls, in milliseconds,
    from the session's `records` and the `leaf_command` records of the session's `leaf`
    commands (`command_spans`). Leaf's share is the time delivery or a command
    covered, each moment once. The tool time that isn't Leaf's is the agent's own
    reads and edits. A model call is the run of model phases that the same
    `model_response` is the first to follow: they were one response, whose tool
    calls ran while it still streamed. Each call names the tool calls it led to.
    Returns None for a comment never picked up."""
    if picked_up is None:
        return None
    phases = _phases(records, admitted, picked_up, replied)
    ends = sorted(
        instant(record["received_at"])
        for record in records
        if record["type"] == "model_response"
    )

    def ms(seconds: float) -> int:
        return round(seconds * 1000)

    def total(*kinds: str) -> int:
        return ms(
            sum(until - since for phase, since, until, _ in phases if phase in kinds)
        )

    model_calls: list[dict] = []
    response: float | None = None
    for phase, since, until, calls in phases:
        if phase == "model":
            ended = next((at for at in ends if at >= until), None)
            if model_calls and ended is not None and ended == response:
                model_calls[-1]["ms"] += ms(until - since)
            else:
                model_calls.append({"ms": ms(until - since), "calls": []})
            response = ended
        elif phase == "tool" and model_calls:
            model_calls[-1]["calls"].extend(call[:SHOWN] for call in calls)
    delivery = total("delivery")
    spans = command_spans(commands, admitted, replied)
    leaf_commands = ms(covered(spans))
    delivering = [
        (since, until) for phase, since, until, _ in phases if phase == "delivery"
    ]
    return {
        "wholeMs": ms(instant(replied) - instant(admitted)),
        "leafMs": ms(covered(spans + delivering)),
        "busyMs": total("busy"),
        "deliveryMs": delivery,
        "leafCommandsMs": leaf_commands,
        "otherToolsMs": max(total("tool") - leaf_commands, 0),
        "modelMs": total("model"),
        "idleMs": total("idle"),
        "modelCalls": model_calls,
        "phases": turn_phases(records, admitted, picked_up, replied),
    }


def claude_code_transcript(session: str) -> list[dict] | None:
    """Claude Code's transcript of `session`, from its configuration directory's
    projects, or None where it is not on disk. Leaf's session record keeps no path
    to it."""
    config = os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"
    found = sorted(Path(config).glob(f"projects/*/{session}.jsonl"))
    if not found:
        return None
    return [json.loads(line) for line in found[0].read_text().splitlines()]


def claude_code_records(native: list[dict]) -> list[dict]:
    """Claude Code's transcript records (`native`) as tool and turn records stamped
    `received_at` with the time Claude Code wrote on each, and a `model_response`
    where each response's last record was written: Claude Code writes a response's
    content blocks as records of their own, sharing its message id. Claude Code marks
    its own turns: the input that starts one carries `turnPosition`, which a
    compaction's summary copies from the turn before without starting one; a
    `turn_duration` record ends a turn once its Stop hooks let it stop, and an
    interruption's record (`interruptedMessageId`) ends one that writes none."""
    records = []
    responses: dict[str, str] = {}
    for record in native:
        if record.get("subtype") == "turn_duration" or "interruptedMessageId" in record:
            records.append({"type": "turn_end", "received_at": record["timestamp"]})
        if record.get("type") not in ("user", "assistant") or "message" not in record:
            continue
        message, at = record["message"], record["timestamp"]
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if "turnPosition" in record and not record.get("isCompactSummary"):
            records.append({"type": "turn_start", "received_at": at})
        records.append(
            {"type": record["type"], "message": {"content": content}, "received_at": at}
        )
        if record["type"] == "assistant" and "id" in message:
            responses[message["id"]] = at
    records.extend(
        {"type": "model_response", "received_at": at} for at in responses.values()
    )
    return sorted(records, key=lambda record: instant(record["received_at"]))
