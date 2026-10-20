"""Where the time from a user's comment to the agent's reply went, read from the page's
log and the harness's record of the session.

A reply is timed from the comment's admission to the reply's, both on the page
server's clock. The harness's record splits that span into phases (`turn_phases`):

- `busy`: the harness was on other work, a turn already running, until the tool
  boundary at which it took the comment. Only a comment that arrives while the
  harness works has it;
- `delivery`: Leaf handing the comment over, until the harness records it in the
  agent's context (its opened pickup), whether that opened a turn or entered a
  running one;
- then alternating `model`, from the last tool result to the next tool call, and
  `tool`, from that call until every call it started has returned, each naming its
  calls.

`reply_breakdown` sums them into the two numbers a reply budget reads: the whole
reply, and Leaf's share of it, delivery plus the tool phases that ran a `leaf`
command. The rest is the harness's other work, the model, and the agent's own reads
and edits. It also groups the model phases into the model calls the harness made,
each with the calls it issued, since a model call is the unit a shorter reply would
have to save.

The records are the journey's normalized form: `assistant` and `user` records whose
content holds `tool_use` and `tool_result` parts, and a `model_response` record where
each model response ended, each stamped `received_at`. A harness that streams its
session stamps a record when the journey hears it; Claude Code's transcript stamps
each record itself (`claude_code_records`).
"""

import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path

# A shell command that runs Leaf's launcher, bare or by its path, anywhere in it.
LEAF_COMMAND = re.compile(r"(?:^|[\s;&|(/'\"])leaf\s")


def instant(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def call_label(part: dict) -> str:
    """What a `tool_use` part ran: its shell command, the `leaf` words a Leaf MCP tool
    ran, or the tool's name."""
    arguments = part["input"]
    if "command" in arguments:
        label = arguments["command"]
    elif part["name"].startswith("mcp__leaf__") and "args" in arguments:
        label = shlex.join(["leaf", *arguments["args"]])
    else:
        label = part["name"]
    return label[:200]


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
        and record["type"] in ("assistant", "user")
    ]
    phases: list[tuple[str, float, float, list[str]]] = []
    # The harness was busy where a call returned between the admission and the
    # pickup: it took the comment at that tool boundary.
    boundary = max(
        (
            at
            for at, record in timed
            if start < at <= began
            and any(p["type"] == "tool_result" for p in record["message"]["content"])
        ),
        default=start,
    )
    if boundary > start:
        phases.append(("busy", start, boundary, []))
    phases.append(("delivery", boundary, began, []))
    # The calls still out when the comment was picked up.
    out: dict[str, str] = {}
    for at, record in timed:
        if at > began:
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
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                if phase == "model":
                    phases.append(("model", since, at, []))
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
            **({"calls": calls} if phase == "tool" else {}),
        }
        for phase, since, until, calls in _phases(records, admitted, picked_up, replied)
    ]


def reply_breakdown(
    records: list[dict], admitted: str, picked_up: str | None, replied: str
) -> dict | None:
    """The whole reply, Leaf's share of it, and its model calls, in milliseconds.

    A tool phase counts toward Leaf's share when any of its calls ran `leaf`, so a
    batch mixing a read with a `leaf` command counts whole. A model call is the run
    of model phases up to the harness's next `model_response`: phases with no
    response ending after one began and by the next were one response, whose tool
    calls ran while it still streamed. Each call names the tool calls it led to. Returns None for a
    comment never picked up."""
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
    previous: float | None = None
    for phase, since, until, calls in phases:
        if phase == "model":
            if previous is not None and not any(previous < e <= since for e in ends):
                model_calls[-1]["ms"] += ms(until - since)
            else:
                model_calls.append({"ms": ms(until - since), "calls": []})
            previous = since
        elif phase == "tool" and model_calls:
            model_calls[-1]["calls"].extend(calls)
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
    content blocks as records of their own, sharing its message id."""
    records = []
    responses: dict[str, str] = {}
    for record in native:
        if record.get("type") not in ("user", "assistant") or "message" not in record:
            continue
        content = record["message"]["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        records.append(
            {
                "type": record["type"],
                "message": {"content": content},
                "received_at": record["timestamp"],
            }
        )
        if record["type"] == "assistant" and "id" in record["message"]:
            responses[record["message"]["id"]] = record["timestamp"]
    records.extend(
        {"type": "model_response", "received_at": at} for at in responses.values()
    )
    return sorted(records, key=lambda record: instant(record["received_at"]))
