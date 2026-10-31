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

`reply_breakdown` attributes the whole reply, the time a reply budget reads, to
where it went, each moment once:

- Leaf's share: delivery, the time Leaf's own commands took, which each `leaf`
  command records in the page it acted on (`leaf.interaction_log.record_command`),
  and Leaf's hooks where the harness times them;
- `harness`: the part of each model phase before the harness sent the request, as
  its other hooks ran, where the record has the request;
- the model's `wait`, from the request, or the phase's start where the record has
  none, to the response's first output, and its `generation`, from that output to
  the phase's end, reasoning included; model time without a first output stays
  unsplit;
- the agent's own reads and edits (`otherTools`), the harness's busy time and idle
  time.

It also groups the model phases into the model calls the harness made, each with
its parts, its output tokens where the harness reports them, and the calls it
issued, which say what a slow reply spent its time on.

`pickup_wait` reads the same records for the wait before the reply's first phase
that a user sees, from the comment's admission to its opened pickup, and names
what ended it, so a survey of real sessions can sort the slow ones by cause. The
journey runs only the causes a harness should produce; the others, such as a watch
that never woke the session, show only in long real sessions.

The records are the journey's normalized form, each stamped `received_at`:
`assistant` and `user` records whose content holds `tool_use` and `tool_result`
parts; a `model_response` where each model response ended, at its last tool call or
after the calls it started returned, as the harness reports it, with the response's
`outputTokens` where reported; `turn_start` and `turn_end` where the harness began
and finished a turn, the start with the `origin` of what began it where the harness
names one; and, where the harness reports them, a `request` where it sent
the model a request, a `first_output` where a response's first output arrived, and
a `leaf_hook` where one of Leaf's hooks ended, with its `ms`. A harness that streams
its session stamps a record when the journey hears it; Claude Code's transcript
stamps each record itself (`claude_code_records`), and its debug log each request,
first byte and hook (`claude_code_debug_records`).
"""

import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path

from leaf.harness import NUDGE_WORDS
from leaf_dev import ROOT

# The directory change an agent puts before a command, which says nothing of it.
CD_PREFIX = re.compile(r"^cd \S+ && ")
# The summary of the task notification Leaf's watch wakes Claude Code with.
LEAF_WAKE = next(
    hook["rewakeSummary"]
    for group in json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"][
        "Stop"
    ]
    for hook in group["hooks"]
    if "rewakeSummary" in hook
)
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
    commands: list[dict], start: float, end: float
) -> list[tuple[float, float]]:
    """When Leaf's `commands` records ran on a reply: each that started after
    `start`, the comment's admission or the boundary where a working harness took
    it, and before `end`, the reply's admission, up to that admission, since the
    command that replies exits after it. A command running from before, as a page
    server does or the harness's other work did, is no part of it."""
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


def leaf_commands_ms(commands: list[dict], since: str, replied: str) -> int:
    """The elapsed time Leaf's commands took on a reply from `since`, where the
    harness took the comment (`command_spans`)."""
    spans = command_spans(commands, instant(since), instant(replied))
    return round(covered(spans) * 1000)


def reply_breakdown(
    records: list[dict],
    commands: list[dict],
    admitted: str,
    picked_up: str | None,
    replied: str,
) -> dict | None:
    """Where the whole reply went, in milliseconds (the module's header lists the
    parts), from the session's `records` and the `leaf_command` records of the
    session's `leaf` commands (`command_spans`). Leaf's share is the time delivery,
    a command or one of Leaf's hooks covered, each moment once; `leafHooksMs` is the
    hooks' time beyond delivery and the commands, which the harness and tool parts
    leave out. A model call is the run of model phases that the same
    `model_response` is the first to follow: they were one response, whose tool
    calls ran while it still streamed, so a later phase of a call is generation.
    Each call names the tool calls it led to. Returns None for a comment never
    picked up."""
    if picked_up is None:
        return None
    phases = _phases(records, admitted, picked_up, replied)

    def times(kind: str) -> list[float]:
        return sorted(
            instant(record["received_at"])
            for record in records
            if record["type"] == kind
        )

    requests, outputs = times("request"), times("first_output")
    tokens = {
        instant(record["received_at"]): record.get("outputTokens")
        for record in records
        if record["type"] == "model_response"
    }
    ends = sorted(tokens)

    def ms(seconds: float) -> int:
        return round(seconds * 1000)

    def total(*kinds: str) -> int:
        return ms(
            sum(until - since for phase, since, until, _ in phases if phase in kinds)
        )

    took = next(
        (until for phase, _, until, _ in phases if phase == "busy"), instant(admitted)
    )
    spans = command_spans(commands, took, instant(replied))
    hooks = [
        (end - record["ms"] / 1000, end)
        for record in records
        if record["type"] == "leaf_hook"
        and took <= (end := instant(record["received_at"])) <= instant(replied)
    ]

    def uncovered(since: float, until: float, by: list[tuple[float, float]]) -> float:
        """The seconds of [since, until] that none of `by` covers."""
        inside = [
            (max(a, since), min(b, until)) for a, b in by if a < until and b > since
        ]
        return (until - since) - covered(inside)

    def free(since: float, until: float) -> float:
        """The seconds of [since, until] none of Leaf's hooks took."""
        return uncovered(since, until, hooks)

    harness = wait = generation = unsplit = 0.0
    model_calls: list[dict] = []
    response: float | None = None
    for phase, since, until, calls in phases:
        if phase == "model":
            ended = next((at for at in ends if at >= until), None)
            if model_calls and ended is not None and ended == response:
                call = model_calls[-1]
                if "generationMs" in call:
                    call["generationMs"] += ms(free(since, until))
                    generation += free(since, until)
                else:
                    unsplit += free(since, until)
            else:
                call: dict = {"ms": 0}
                sent = next((at for at in requests if since < at <= until), None)
                start = sent if sent is not None else since
                first = next((at for at in outputs if start < at <= until), None)
                if sent is not None:
                    call["harnessMs"] = ms(free(since, sent))
                    harness += free(since, sent)
                if first is None:
                    unsplit += free(start, until)
                else:
                    call["waitMs"] = ms(free(start, first))
                    call["generationMs"] = ms(free(first, until))
                    wait += free(start, first)
                    generation += free(first, until)
                if ended is not None and tokens[ended] is not None:
                    call["outputTokens"] = tokens[ended]
                call["calls"] = []
                model_calls.append(call)
            call["ms"] += ms(until - since)
            response = ended
        elif phase == "tool" and model_calls:
            model_calls[-1]["calls"].extend(call[:SHOWN] for call in calls)
    delivering = [
        (since, until) for phase, since, until, _ in phases if phase == "delivery"
    ]
    # The tool time Leaf's commands and hooks didn't cover, phase by phase.
    other_tools = sum(
        uncovered(since, until, spans + hooks)
        for phase, since, until, _ in phases
        if phase == "tool"
    )
    leaf = covered(spans + hooks + delivering)
    produced = [call["outputTokens"] for call in model_calls if "outputTokens" in call]
    return {
        "wholeMs": ms(instant(replied) - instant(admitted)),
        "leafMs": ms(leaf),
        "busyMs": total("busy"),
        "deliveryMs": total("delivery"),
        "leafCommandsMs": ms(covered(spans)),
        "leafHooksMs": ms(leaf - covered(spans + delivering)),
        "harnessMs": ms(harness),
        "modelMs": ms(wait + generation + unsplit),
        "waitMs": ms(wait),
        "generationMs": ms(generation),
        "otherToolsMs": ms(other_tools),
        "idleMs": total("idle"),
        "outputTokens": sum(produced) if produced else None,
        "modelCalls": model_calls,
        "phases": turn_phases(records, admitted, picked_up, replied),
    }


# What can end a pickup wait (`pickup_wait`), and the ones a turn's origin names
# where no turn running at the admission took the comment.
WAIT_CAUSES = ("working", "woken", "nudged", "prompted", "other", "started")
ORIGIN_CAUSES = {"leaf_wake": "woken", "leaf_nudge": "nudged", "human": "prompted"}


def pickup_wait(records: list[dict], admitted: str, picked_up: str) -> dict:
    """What a comment waited on from its admission to its opened pickup, from the
    session's `records`, with the wait in milliseconds and the `missedTurns` that
    ended in it without taking the comment. The `cause` is:

    - `working`: a turn was running at the admission and took the comment at a
      tool boundary, after the `calls` out in the wait;
    - `woken`: Leaf's watch woke the idle session;
    - `nudged`: Leaf's nudge started the turn, or resumed a background job whose
      worker had retired;
    - `prompted`: the user's own prompt started the turn, so nothing of Leaf's
      woke the session first;
    - `other`: something else started the turn, such as a background task ending;
    - `started`: the session's records begin after the admission, so a session
      that took the page later picked it up.
    """
    start, end = instant(admitted), instant(picked_up)
    timed = [(instant(record["received_at"]), record) for record in records]
    turns = [
        (at, record)
        for at, record in timed
        if record["type"] in ("turn_start", "turn_end")
    ]
    missed = sum(
        record["type"] == "turn_end" for at, record in turns if start < at < end
    )
    took = next((record for at, record in reversed(turns) if at <= end), None)
    running = [record for at, record in turns if at <= start][-1:]
    wait = {"ms": round((end - start) * 1000), "missedTurns": missed}
    if not timed or timed[0][0] > start:
        return {**wait, "cause": "started"}
    if running and running[0]["type"] == "turn_start" and not missed:
        # The calls out at any moment of the wait.
        out: dict[str, str] = {}
        calls = []
        for at, record in timed:
            if at > end or record["type"] not in ("assistant", "user"):
                continue
            for part in record["message"]["content"]:
                if part["type"] == "tool_use":
                    out[part["id"]] = call_label(part)[:SHOWN]
                elif part["type"] == "tool_result" and part["tool_use_id"] in out:
                    label = out.pop(part["tool_use_id"])
                    if at >= start:
                        calls.append(label)
        calls.extend(out.values())
        return {**wait, "cause": "working", "calls": calls}
    origin = took["origin"] if took and took["type"] == "turn_start" else None
    return {**wait, "cause": ORIGIN_CAUSES.get(origin, "other"), "origin": origin}


def claude_code_transcript(session: str) -> list[dict] | None:
    """Claude Code's transcript of `session`, from its configuration directory's
    projects, or None where it is not on disk. Leaf's session record keeps no path
    to it."""
    config = os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"
    found = sorted(Path(config).glob(f"projects/*/{session}.jsonl"))
    if not found:
        return None
    return transcript_records(found[0])


def transcript_records(path: Path) -> list[dict]:
    """The records of the Claude Code transcript at `path`, one JSON object a line.
    Lines split only at the newline Claude Code writes after each record: its strings
    can hold U+2028 and U+2029 raw, which `splitlines` would split on. A record it
    is still writing is no record yet, so the bytes after the last newline, which
    can end inside a character, are left out."""
    written, _, _ = path.read_bytes().rpartition(b"\n")
    return [json.loads(line) for line in written.decode().split("\n") if line]


def ends_turn(record: dict) -> bool:
    """Whether a Claude Code transcript record ends a turn: a `turn_duration` record
    ends one once its Stop hooks let it stop, and an interruption's record
    (`interruptedMessageId`) ends one that writes none."""
    return record.get("subtype") == "turn_duration" or "interruptedMessageId" in record


def claude_code_records(native: list[dict]) -> list[dict]:
    """Claude Code's transcript records (`native`) as tool and turn records stamped
    `received_at` with the time Claude Code wrote on each, and a `model_response`
    where each response's last record was written: Claude Code writes a response's
    content blocks as records of their own, sharing its message id. Claude Code marks
    its own turns: the input that starts one carries `turnPosition`, which a
    compaction's summary copies from the turn before without starting one, and
    `ends_turn` says which records end one. A response's records carry its usage,
    whose output the `model_response` keeps: the response's whole output, thinking
    included, by its last record. A turn's start carries Claude Code's
    `turnOrigin` as its `origin` (`human` for a prompt, `peer` for another
    session's message, `task_notification`), with `leaf_wake` for the task
    notification Leaf's watch wakes the session with and `leaf_nudge` for Leaf's
    nudge, whether it came through the session's socket or as the prompt of a
    background job it resumed."""
    records = []
    responses: dict[str, dict] = {}
    for record in native:
        if ends_turn(record):
            records.append({"type": "turn_end", "received_at": record["timestamp"]})
        if record.get("type") not in ("user", "assistant") or "message" not in record:
            continue
        message, at = record["message"], record["timestamp"]
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if "turnPosition" in record and not record.get("isCompactSummary"):
            start = {"type": "turn_start", "received_at": at}
            text = "".join(part.get("text", "") for part in content)
            if f"<summary>{LEAF_WAKE}</summary>" in text:
                start["origin"] = "leaf_wake"
            elif NUDGE_WORDS in text:
                start["origin"] = "leaf_nudge"
            elif origin := record.get("turnOrigin"):
                start["origin"] = origin
            records.append(start)
        records.append(
            {"type": record["type"], "message": {"content": content}, "received_at": at}
        )
        if record["type"] == "assistant" and "id" in message:
            responses[message["id"]] = {"type": "model_response", "received_at": at}
            if (usage := message.get("usage")) is not None:
                responses[message["id"]]["outputTokens"] = usage["output_tokens"]
    records.extend(responses.values())
    return sorted(records, key=lambda record: instant(record["received_at"]))


# Claude Code's debug log: a request it sent, with its source; the first byte of a
# stream, with how long after its request it came; and a plugin hook it ran, with
# the hook event and how long it took.
REQUEST_LINE = re.compile(r"^(\S+) \[DEBUG\] \[API REQUEST\] \S+ .*source=(\S+)")
FIRST_BYTE_LINE = re.compile(
    r"^(\S+) \[DEBUG\] \[API:timing\] first byte after (\d+)ms"
)
LEAF_HOOK_LINE = re.compile(
    r"^(\S+) \[DEBUG\] Hooks: (\S+) .*\(plugin leaf@[^)]*\) finished with status "
    r"\d+ \((\d+)ms\)"
)
MAIN_THREAD = "repl_main_thread"
# How far apart, in seconds, a first byte's stated request and a logged one may be.
SAME_REQUEST = 0.02


def claude_code_debug_records(log: str) -> list[dict]:
    """The main thread's requests and their first outputs, and Leaf's hooks, from
    Claude Code's debug log (`--debug-file`), stamped with the time Claude Code
    wrote on each line. Requests of other sources, such as a prompt suggestion,
    run beside the main thread's, so a first byte is the main thread's where the
    request it says it answers is one of the main thread's."""
    records, sent = [], []
    for line in log.splitlines():
        if match := REQUEST_LINE.match(line):
            if match[2] == MAIN_THREAD:
                sent.append(instant(match[1]))
                records.append({"type": "request", "received_at": match[1]})
        elif match := FIRST_BYTE_LINE.match(line):
            asked = instant(match[1]) - int(match[2]) / 1000
            if any(abs(at - asked) <= SAME_REQUEST for at in sent):
                records.append({"type": "first_output", "received_at": match[1]})
        elif match := LEAF_HOOK_LINE.match(line):
            records.append(
                {
                    "type": "leaf_hook",
                    "event": match[2],
                    "ms": int(match[3]),
                    "received_at": match[1],
                }
            )
    return records
