"""What happened on a Leaf page and in the Claude Code sessions that held it, in time
order: the user's messages, Leaf's holds and forks, what Leaf handed each session and
when, the session's turns and commands, and the agent's words on the page, with a line
per message saying how long each step took after the user sent it.

    leaf-dev logs timeline PAGE... [--message ID] [--since ISO] [--until ISO] [--calls] [--json]

PAGE is a page directory, or any directory holding a page's `events.jsonl` and
`observations.jsonl`, as a journey's evidence directory does. The records it reads:

- the page's log and diagnostics (`leaf.interaction_log.read_interactions`): each
  message and the agent's words, pickups and receipts, and the records Leaf's hooks
  and commands leave: `fork_hold`, whether admission held a message for a fork and,
  where not, whether the session's fork lane was up; `fork_asked`, as Leaf gave a fork
  its question; `fork_reply`, what came of it (`leaf.forks`); `turn_end_check`, the
  clerk's fork (`leaf.clerk`); `leaf_command` and `watch`
  (`leaf.interaction_log.record_command`, `record_watch`); and the browser's own
  `event_submit` and `reply_visible`;
- each Claude Code session the page names: its transcript, from `claude/` in the PAGE
  directory, where a journey keeps it, or Claude Code's configuration directory
  (`CLAUDE_CONFIG_DIR`, else `~/.claude`), with its turns, the Leaf input its hooks
  carried, its `leaf` commands, and the subagents beside its transcript; and its debug
  log, `debug.log` in the PAGE directory or `debug/<session>.txt` in Claude Code's,
  which only a session started with `--debug` or `--debug-file` writes, with the hooks
  module's own lines (`Leaf: …`).

`--message ID` keeps one message's story: from its admission to its answer, or ten
minutes on where it has none, its thread's events and everything the sessions did
meanwhile. `--calls` adds every tool call and the agent's words in the terminal.

The line per message comes from `response_times.page_timings`, so it times each step
as `leaf-dev logs response-times` does: the fork and its outcome, the agent's first words
on the page, the session's pickup and what it waited on (`reply_phases.pickup_wait`),
its start and its answer, each in seconds after the message was admitted.
"""

import json
import os
from collections.abc import Set as AbstractSet
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path

import click

from leaf.event_log import read_stored_events
from leaf.events import is_answer
from leaf.interaction_log import interaction_time, read_interactions
from leaf.registry.kernel import kinds_declaring
from leaf.state import now_iso
from leaf.thread_context import thread_names
from leaf_dev.commands.logs.response_times import page_timings
from leaf_dev.reply_phases import (
    claude_code_debug_records,
    claude_code_records,
    claude_code_transcript_path,
    transcript_records,
)

# The page's records the timeline reads, besides its log's events.
DIAGNOSTICS = (
    "event",
    "fork_hold",
    "fork_asked",
    "fork_reply",
    "turn_end_check",
    "leaf_command",
    "watch",
    "event_submit",
    "reply_visible",
)
# Events no step of a message's story turns on.
QUIET = {"seen", "read", "reanchor", "receipt"}
# How long after a message `--message` reads where nothing answered it.
UNANSWERED_WINDOW = timedelta(minutes=10)
# The line a hook carries Leaf's input in, before the delivery's JSON
# (`hook_transport.INLINE_OPENING`).
DELIVERY_OPENING = "Leaf has new input"


def clip(text: str | None, width: int = 90) -> str:
    line = " ".join((text or "").split())
    return line if len(line) <= width else line[: width - 1] + "…"


def entry(at: str, source: str, what: str, **context) -> dict:
    return {"at": at, "source": source, "what": what, **context}


def page_entries(page: Path, since, until) -> tuple[list[dict], set[str], dict]:
    """The page's events and diagnostics as timeline entries, the Claude Code sessions
    they name, and each message's thread."""
    events = read_stored_events(page)
    threads = thread_names(events)
    messages = kinds_declaring("message")
    rows = read_interactions(page, since=since, until=until, types=DIAGNOSTICS)
    lines = {
        row["line"] for row in rows if row["type"] == "fork_reply" and "line" in row
    }
    sessions: set[str] = set()
    out = []
    for row in rows:
        if row.get("session") and row.get("source") == "cli":
            sessions.add(row["session"])
        at, kind = row["ts"], row["type"]
        if kind == "event":
            event = row["event"]
            if session := event.get("session"):
                sessions.add(session)
            if (shown := event_entry(event, threads, messages, lines)) is not None:
                out.append(shown)
        elif kind == "fork_hold":
            out.append(
                entry(
                    at,
                    "fork",
                    f"{row['event']} held for a fork"
                    if row["held"]
                    else f"{row['event']} not held: "
                    + ("no fork lane" if row["lane"] is None else "with the session"),
                    thread=threads.get(row["event"]),
                )
            )
        elif kind == "fork_asked":
            running = ", ".join(row.get("running") or []) or "nothing"
            out.append(
                entry(
                    at,
                    "fork",
                    f"asked for {', '.join(row['inputs'])} (session running {running})",
                    thread=row["thread"],
                )
            )
        elif kind == "fork_reply":
            out.extend(fork_entries(row))
        elif kind == "turn_end_check":
            outcome = {k: row[k] for k in ("asks", "refused", "failed") if row.get(k)}
            out.append(
                entry(
                    at,
                    "clerk",
                    "turn-end check: "
                    + (
                        ", ".join(
                            f"{len(v)} {k}"
                            if isinstance(v, list)
                            else f"{k}: {clip(v, 60)}"
                            for k, v in outcome.items()
                        )
                        or "nothing to say"
                    ),
                )
            )
        elif kind == "leaf_command":
            out.append(
                entry(
                    row["started"],
                    "leaf",
                    f"leaf {row['command']} ({row['durationMs']:.0f} ms)",
                    session=row.get("session"),
                )
            )
        elif kind == "watch":
            out.append(
                entry(row["started"], "leaf", "watch started", session=row["session"])
            )
            out.append(
                entry(
                    at, "leaf", f"watch ended: {row['ended']}", session=row["session"]
                )
            )
        elif kind == "event_submit":
            out.append(entry(at, "browser", f"sent: {row.get('kind', 'a gesture')}"))
        elif kind == "reply_visible":
            out.append(
                entry(
                    at,
                    "browser",
                    f"agent's {row.get('presentation_kind')}"
                    + (f" on {row['input_id']}" if row.get("input_id") else "")
                    + f" visible in the {row.get('surface')}",
                    thread=threads.get(row.get("input_id")),
                )
            )
    return out, sessions, threads


def event_entry(
    event: dict, threads: dict, messages: AbstractSet[str], lines: set
) -> dict | None:
    kind, author, at = event["kind"], event.get("author"), event["ts"]
    identity = event["id"]
    thread = threads.get(identity)
    if kind in QUIET:
        return None
    if author == "user":
        if kind in messages | {"edit"} and event.get("attention"):
            return entry(
                at,
                "user",
                f"{kind} {identity}: “{clip(event.get('text'), 80)}”",
                thread=threads.get(event.get("message", identity)),
                message=identity,
            )
        if kind == "action":
            return entry(at, "user", f"{event['action']} on {event['widget']}")
        if kind == "resolve":
            return entry(at, "user", "resolved the thread", thread=thread)
        return entry(at, "user", kind, thread=thread)
    if kind == "pickup":
        turn = (event.get("turn") or "")[:8]
        return entry(
            at,
            "leaf",
            f"pickup {event['phase']} of {', '.join(event['events'])}"
            + (f" in turn {turn}" if turn else ""),
            session=event.get("session"),
        )
    if kind == "start":
        return entry(
            at,
            "agent",
            f"started {event['item']}: “{clip(event.get('text'), 70)}”",
            thread=threads.get(event["item"]),
        )
    if kind == "reply":
        if identity in lines:
            said = "fork's working line"
        elif event.get("ephemeral"):
            said = "working line"
        elif is_answer(event):
            said = f"answer to {event['responds']}"
        elif "failure" in event:
            said = "failure"
        else:
            said = "reply"
        return entry(
            at, "agent", f"{said}: “{clip(event.get('text'), 70)}”", thread=thread
        )
    if kind == "thread_title":
        return entry(
            at,
            "leaf",
            f"thread titled “{clip(event['title'], 60)}”",
            thread=event["thread"],
        )
    if kind == "activation":
        return entry(at, "leaf", f"revision {event['revision']} live")
    if kind == "status":
        return entry(at, "agent", f"status {event['state']}")
    if kind in ("comment", "note"):
        return entry(
            at,
            "agent",
            f"{kind}: “{clip(event.get('title') or event.get('text'), 70)}”",
        )
    if kind == "todo_end":
        return entry(at, "agent", f"ended {event['todo']}: {event['outcome']}")
    return entry(at, author or "page", kind, thread=thread)


def fork_entries(row: dict) -> list[dict]:
    """A `fork_reply` record as its fork's start, where its time says when, and its
    end."""
    at, thread = row["ts"], row["thread"]
    elapsed = row.get("elapsedMs")
    out = []
    if elapsed is not None:
        began = (interaction_time(at) - timedelta(milliseconds=elapsed)).isoformat()
        out.append(entry(began, "fork", "forked the conversation", thread=thread))
    said = (
        f"line “{clip(row['text'], 60)}”"
        if "line" in row
        else row.get("why") or row.get("refused") or ""
    )
    took = f" in {elapsed / 1000:.1f} s" if elapsed is not None else ""
    out.append(entry(at, "fork", f"{row['outcome']}{took}: {said}", thread=thread))
    return out


def claude_directory() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def transcript_path(page: Path, session: str) -> Path | None:
    """Where `session`'s transcript is: beside a journey's evidence, else in Claude
    Code's projects."""
    kept = page / "claude" / f"{session}.jsonl"
    return kept if kept.exists() else claude_code_transcript_path(session)


def debug_log(page: Path, session: str) -> str:
    """`session`'s debug log: a journey's, beside its evidence with the transcript of
    the one session it ran, else Claude Code's own for the session, which only a
    session started with `--debug` writes."""
    kept = page / "debug.log"
    for path in (
        kept if (page / "claude" / f"{session}.jsonl").exists() else None,
        claude_directory() / "debug" / f"{session}.txt",
    ):
        if path is not None and path.exists():
            return path.read_text(errors="replace")
    return ""


@cache
def native(path: Path) -> list[dict]:
    return transcript_records(path)


def told(text: str) -> list[str]:
    """What one context a Leaf hook gave the session says: the delivery it carried, by
    event id, and each line Leaf's clerk queued after it (`clerk.queued`)."""
    if not text.startswith(DELIVERY_OPENING):
        return [
            f"said “{clip(line, 90)}”" for line in text.splitlines() if line.strip()
        ]
    start = text.find("{")
    try:
        delivery, end = json.JSONDecoder().raw_decode(text, start)
    except ValueError:
        return [f"said “{clip(text, 90)}”"]
    ids = [
        event["id"]
        for batch in delivery.get("batches", [])
        for event in batch.get("events", [])
    ]
    return [
        f"carried delivery {delivery.get('id')}: {', '.join(ids) or 'no events'}",
        *told(text[end:].strip()),
    ]


def session_entries(path: Path, session: str, *, calls: bool) -> list[dict]:
    """The session's turns, the Leaf input its hooks carried, its tool calls that ran
    `leaf` or started an agent, and with `calls` every call and its words, from its
    transcript; and each subagent beside it, as its start and end."""
    short = session[:8]
    out = []
    for record in claude_code_records(native(path)):
        at = record["received_at"]
        if record["type"] == "turn_start":
            out.append(
                entry(
                    at,
                    "session",
                    f"turn started ({record.get('origin', 'prompt')})",
                    session=short,
                )
            )
        elif record["type"] == "turn_end":
            out.append(entry(at, "session", "turn ended", session=short))
        elif record["type"] == "assistant":
            for part in record["message"]["content"]:
                if part.get("type") == "tool_use":
                    shown = tool_call(part, calls=calls)
                    if shown:
                        out.append(entry(at, "session", shown, session=short))
                elif (
                    calls
                    and part.get("type") == "text"
                    and part.get("text", "").strip()
                ):
                    out.append(
                        entry(
                            at,
                            "session",
                            f"says “{clip(part['text'], 80)}”",
                            session=short,
                        )
                    )
    for record in native(path):
        attachment = record.get("attachment") or {}
        if attachment.get("type") == "hook_additional_context":
            for text in attachment.get("content") or []:
                if not text.startswith(DELIVERY_OPENING) and "Leaf" not in text[:200]:
                    continue
                out.extend(
                    entry(
                        record["timestamp"],
                        "session",
                        f"{attachment.get('hookEvent')} hook {line}",
                        session=short,
                    )
                    for line in told(text)
                )
        elif (
            record.get("type") == "queue-operation"
            and record.get("operation") == "enqueue"
        ):
            content = record.get("content") or ""
            if "<agent-message" in content or "Leaf" in content[:300]:
                out.append(
                    entry(
                        record["timestamp"],
                        "session",
                        f"queued “{clip(content, 80)}”",
                        session=short,
                    )
                )
    subagents = path.with_suffix("") / "subagents"
    for meta in sorted(subagents.glob("*.meta.json")) if subagents.exists() else []:
        out.extend(subagent_entries(meta, short))
    return out


def tool_call(part: dict, *, calls: bool) -> str | None:
    tool, given = part["name"], part.get("input") or {}
    if tool == "Bash":
        command = given.get("command", "")
        if calls or " leaf " in f" {command} " or "bin/leaf" in command:
            return f"runs `{clip(command, 90)}`"
        return None
    if tool in ("Agent", "Task", "SendMessage"):
        about = given.get("description") or given.get("to") or ""
        return f"{tool} {clip(about, 60)}"
    return f"{tool} {clip(json.dumps(given), 70)}" if calls else None


def subagent_entries(meta: Path, session: str) -> list[dict]:
    """A subagent as its first and last record: its kind, what it was for, its tool
    calls and how it ended."""
    about = json.loads(meta.read_text())
    records = native(meta.with_name(meta.name.removesuffix(".meta.json") + ".jsonl"))
    dated = [record for record in records if record.get("timestamp")]
    if not dated:
        return []
    name = f"{about.get('agentType', 'agent')} “{clip(about.get('description'), 50)}”"
    tools = sum(
        1
        for record in dated
        if record.get("type") == "assistant"
        for part in record["message"]["content"]
        if isinstance(part, dict)
        and part.get("type") == "tool_use"
        # The call a plugin spawned the agent with opens its transcript.
        and not part.get("id", "").startswith("toolu_plugin_")
    )
    last = next(
        (
            part.get("text", "")
            for record in reversed(dated)
            if record.get("type") == "assistant"
            for part in record["message"]["content"]
            if isinstance(part, dict) and part.get("type") == "text"
        ),
        "",
    )
    return [
        entry(dated[0]["timestamp"], "subagent", f"{name} started", session=session),
        entry(
            dated[-1]["timestamp"],
            "subagent",
            # Its last record, which ended it only where Claude Code says so.
            f"{name} {'ended' if about.get('finished') else 'last wrote'} after "
            f"{tools} tool calls: “{clip(last, 60)}”",
            session=session,
        ),
    ]


def debug_entries(log: str, session: str, *, calls: bool) -> list[dict]:
    """The hooks module's own lines from a debug log, and with `calls` how long each
    of Leaf's hooks took."""
    short = session[:8]
    out = []
    for line in log.splitlines():
        if "$.ui.log" in line and "Leaf:" in line:
            at = line.split(" ", 1)[0]
            out.append(
                entry(at, "module", clip(line.split("Leaf:", 1)[1], 100), session=short)
            )
    for record in claude_code_debug_records(log) if calls else []:
        if record["type"] == "leaf_hook":
            out.append(
                entry(
                    record["received_at"],
                    "module",
                    f"{record['event']} hook took {record['ms']} ms",
                    session=short,
                )
            )
    return out


def message_line(row: dict, holds: dict) -> str:
    """One message's steps, in seconds after its admission: whether admission held
    it (`holds`, its `fork_hold` notes), what its fork did, and the page's and the
    session's steps on it (`row`, `page_timings`' reading of it)."""
    marks = row["milestones"]

    def at(name: str) -> str:
        mark = marks.get(name)
        return "—" if mark is None else f"{mark['elapsed_s']:.1f}s"

    hold = holds.get(row["message_id"])
    told = (
        ""
        if hold is None
        else "held · "
        if hold["held"]
        else "not held (no fork lane) · "
        if hold["lane"] is None
        else "not held (with the session) · "
    )
    if (fork := row["fork"]) is not None:
        took = f" {fork['elapsed_s']:.1f}s" if fork["elapsed_s"] is not None else ""
        told += f"fork {fork['outcome']}{took}" + (
            f" ({clip(fork['why'], 50)})" if fork["why"] else ""
        )
    elif hold is None or hold["held"]:
        told += "no fork"
    pickup = row.get("pickup") or {}
    cause = (
        f" ({pickup['cause']}"
        + (f": {clip(', '.join(pickup['calls']), 50)}" if pickup.get("calls") else "")
        + ")"
        if pickup.get("cause")
        else ""
    )
    return (
        f"{row['input_id']} {row['input_kind']:8} {told.removesuffix(' · ')} · first "
        f"words {at('first_reply')} ({row.get('first_reply_kind') or '—'}) · picked "
        f"up {at('opened')}{cause} · started {at('started')} · answered {at('answered')}"
    )


def local(at: str) -> datetime:
    return datetime.fromisoformat(at).astimezone()


@click.command()
@click.argument(
    "pages",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--message", help="Keep one message's story, from its admission to its answer."
)
@click.option("--since", help="Start at this timezone-qualified ISO time.")
@click.option(
    "--until", help="Stop before this timezone-qualified ISO time; defaults to now."
)
@click.option(
    "--calls", is_flag=True, help="Add every tool call and the agent's words."
)
@click.option(
    "--json", "as_json", is_flag=True, help="Print the entries as JSON lines."
)
def timeline(
    pages: tuple[Path, ...],
    message: str | None,
    since: str | None,
    until: str | None,
    calls: bool,
    as_json: bool,
):
    """A page's and its Claude Code sessions' records in one time-ordered timeline."""
    beginning = interaction_time(since) if since else None
    cutoff = interaction_time(until or now_iso())
    for page in pages:
        page = page.resolve()
        if not (page / "events.jsonl").exists():
            raise click.ClickException(f"{page} holds no events.jsonl")
        if message is None:
            show(page, None, beginning, cutoff, calls=calls, as_json=as_json)
            continue
        events = {event["id"]: event for event in read_stored_events(page)}
        if message not in events:
            raise click.ClickException(f"{page} has no event {message}")
        admitted = interaction_time(events[message]["ts"])
        answered = next(
            (
                interaction_time(event["ts"])
                for event in events.values()
                if is_answer(event) and event["responds"] == message
            ),
            admitted + UNANSWERED_WINDOW,
        )
        margin = timedelta(seconds=5)
        show(
            page,
            (message, admitted),
            admitted - margin,
            answered + margin,
            calls=calls,
            as_json=as_json,
        )


def show(
    page: Path,
    focus: tuple[str, datetime] | None,
    beginning: datetime | None,
    cutoff: datetime,
    *,
    calls: bool,
    as_json: bool,
) -> None:
    """Print `page`'s timeline between `beginning` and `cutoff`, kept to the thread of
    the message `focus` names where it names one."""
    found, sessions, threads = page_entries(page, beginning, cutoff)
    paths = {session: transcript_path(page, session) for session in sorted(sessions)}

    def records(milestone: dict) -> list[dict] | None:
        path = paths.get(milestone.get("session") or "")
        return None if path is None else claude_code_records(native(path))

    timings = page_timings(page, since=beginning, until=cutoff, records=records)
    rows = [
        row
        for row in timings["samples"]
        if focus is None or row["input_id"] == focus[0]
    ]
    holds = {
        row["event"]: row
        for row in read_interactions(page, until=cutoff, types=("fork_hold",))
        if row["type"] == "fork_hold"
    }
    for session, path in paths.items():
        if path is not None:
            found.extend(session_entries(path, session, calls=calls))
        found.extend(debug_entries(debug_log(page, session), session, calls=calls))
    thread = threads.get(focus[0]) if focus else None
    shown = sorted(
        (
            item
            for item in found
            if (beginning is None or interaction_time(item["at"]) >= beginning)
            and interaction_time(item["at"]) < cutoff
            and (thread is None or item.get("thread") in (None, thread))
        ),
        key=lambda item: interaction_time(item["at"]),
    )
    if as_json:
        for item in shown:
            click.echo(json.dumps(item))
        return
    click.echo(f"{page}")
    for session, path in paths.items():
        log = "debug log" if debug_log(page, session) else "no debug log"
        click.echo(f"  session {session}: {path or 'no transcript here'}; {log}")
    for row in rows:
        click.echo("  " + message_line(row, holds))
    click.echo()
    sent = focus[1] if focus else None
    for item in shown:
        stamp = interaction_time(item["at"])
        if item["source"] == "user" and item.get("message") and focus is None:
            sent = stamp
        offset = (
            f"+{(stamp - sent).total_seconds():6.1f}s"
            if sent and stamp >= sent
            else " " * 8
        )
        who = item["source"] + (
            f":{item['session'][:8]}"
            if item.get("session")
            and item["source"] in ("session", "subagent", "module")
            else ""
        )
        click.echo(
            f"{local(item['at']):%H:%M:%S.%f}"[:12]
            + f" {offset}  {who:17} {item['what']}"
        )
