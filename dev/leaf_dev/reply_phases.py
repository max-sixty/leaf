"""Where the time from a user's comment to the agent's reply went, read from the page's
log and the harness's record of the session.

A reply is timed from the comment's admission to the reply's, both on the page
server's clock. The harness's record splits that span into phases (`turn_phases`):

- `busy`: the harness was in a turn at the admission, on other work, until that
  turn's first tool boundary or its end, where the harness can take the comment.
  Only a comment that arrives while the harness works has it;
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
reply, and Leaf's share of it, delivery plus the tool phases that ran a `leaf`
command. The rest is the harness's other work, the model, the agent's own reads and
edits, and idle time. It also groups the model phases into the model calls the
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

# A shell command that names Leaf's launcher anywhere in it: bare, by its path
# (including where it assigns the path to a variable the command then runs), or as
# `$LEAF`, the variable a harness that sets one gives it (`SKILL.md`).
LEAF_COMMAND = re.compile(r"(?:^|[\s;&|(/'\"=])leaf(?:[\s;&|)'\"]|$)|\$\{?LEAF\b")
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


def leaf_call(call: str) -> bool:
    """Whether a call (`call_label`) ran a `leaf` command."""
    return bool(LEAF_COMMAND.search(call))


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

    turns = [
        record["type"]
        for at, record in timed
        if at <= start and record["type"] in ("turn_start", "turn_end")
    ]
    phases: list[tuple[str, float, float, list[str]]] = []
    boundary = start
    if turns[-1:] == ["turn_start"]:
        boundary = first(start, began, "tool_result", "turn_end") or start
        if boundary > start:
            phases.append(("busy", start, boundary, []))
        took = boundary if boundary > start else None
    else:
        took = first(start, began, "turn_start")
    if took is not None and first(took, began, "tool_use") is not None:
        # The agent worked before its pickup, so it had the comment from where the
        # harness took it.
        if took > boundary:
            phases.append(("delivery", boundary, took, []))
        began = took
    else:
        phases.append(("delivery", boundary, began, []))
    # The calls still out when the comment was picked up.
    out: dict[str, str] = {}
    for at, record in timed:
        if at > began or record["type"] not in ("assistant", "user"):
            continue
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                out[part["id"]] = call_label(part)
            elif part["type"] == "tool_result":
                out.pop(part["tool_use_id"], None)
    phase = "tool" if out else "model"
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


def reply_breakdown(
    records: list[dict], admitted: str, picked_up: str | None, replied: str
) -> dict | None:
    """The whole reply, Leaf's share of it, and its model calls, in milliseconds.

    A tool phase counts toward Leaf's share when any of its calls names `leaf`, so a
    batch mixing a read with a `leaf` command counts whole, as does one shell command
    that runs `leaf` among slower work: Leaf's share is an upper bound, close where
    the agent runs `leaf` on its own, as the journey's agents do. A model call is the run
    of model phases that the same `model_response` is the first to follow: they were
    one response, whose tool calls ran while it still streamed. Each call names the
    tool calls it led to. Returns None for a comment never picked up."""
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

    def total(*kinds: str, leaf: bool | None = None) -> int:
        return ms(
            sum(
                until - since
                for phase, since, until, calls in phases
                if phase in kinds
                and (leaf is None or any(map(leaf_call, calls)) == leaf)
            )
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
    leaf_commands = total("tool", leaf=True)
    return {
        "wholeMs": ms(instant(replied) - instant(admitted)),
        "leafMs": delivery + leaf_commands,
        "busyMs": total("busy"),
        "deliveryMs": delivery,
        "leafCommandsMs": leaf_commands,
        "otherToolsMs": total("tool", leaf=False),
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
    content blocks as records of their own, sharing its message id. A turn starts
    with input that is no tool's result and ends with a response that stops on
    `end_turn`."""
    records = []
    responses: dict[str, str] = {}
    for record in native:
        if record.get("type") not in ("user", "assistant") or "message" not in record:
            continue
        message, at = record["message"], record["timestamp"]
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if record["type"] == "user" and not any(
            part["type"] == "tool_result" for part in content
        ):
            records.append({"type": "turn_start", "received_at": at})
        records.append(
            {"type": record["type"], "message": {"content": content}, "received_at": at}
        )
        if record["type"] == "assistant" and "id" in message:
            responses[message["id"]] = at
        if message.get("stop_reason") == "end_turn":
            records.append({"type": "turn_end", "received_at": at})
    records.extend(
        {"type": "model_response", "received_at": at} for at in responses.values()
    )
    return sorted(records, key=lambda record: instant(record["received_at"]))
