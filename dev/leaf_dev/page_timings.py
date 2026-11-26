"""Recorded and visible first feedback on a Leaf page, read from its logs: each
input's milestones (`page_timings`) and their spread over many inputs
(`distribution`). `leaf-dev logs response-times` summarises pages by it, and
`leaf-dev journey run` and the delivery eval time their inputs by it.

Each attention-bearing user message version is an input. Pickup, work starts and
failure receipts are separate milestones. Progress, published provisional words and
answers count as first replies; answer time does not claim the task is finished.
`titled` is when the input's thread got its first title, for an input admitted while
it had none. `published` is when the page published the revision the input's answer
stands on, where that came after the input. Nothing records which input a revision
serves, so one published while several inputs were open counts for each answer that
stands on it. It reads the revision files, so a directory holding only a log has none.

Diagnostics carry host receipt `ts` and browser `observed_at`; the cutoff uses
host time while visible elapsed time uses only the document's monotonic clock.
Rows retain missing observations and the cutoff used for them. Percentiles describe
observed replies only, alongside the full input and missing counts; missing is not
zero or proof of failure. Semantic milestones use the server's clock. The separate
send_to_visible milestone joins diagnostic event_submit and reply_visible records
on the originating document's monotonic clock. It measures agent-authored message
or working words in the viewport, not generic delivery indicators. Both observations
must be present in the same diagnostic session; no clocks are subtracted across tabs
or hosts. Diagnostics are best effort, so absent evidence is retained as missing.

Run context comes from explicit producer declarations before each input, not from
text or current preview files. Purpose describes the declared run, never proof that
a gesture is human. --exclude-purpose selects out known runs and keeps unknowns.
Each sample retains every recorded agent session and turn associated with its
exact input through pickup, start, progress, title or answer evidence. Missing turns remain
unknown; browser diagnostic sessions are separate identities. Captured context
identifies the harness and the provider of an explicitly recorded matching turn;
no current claim or timestamp proximity supplies this identity.

Every input a session answered carries the time the session's `leaf` commands
took on it (`leaf_commands_s`), from the `leaf_command` record each writes in the
page (`leaf.log.interaction_log.record_command`), on any harness: those that started
between the harness taking the input and the answer. Where the input has a reply
breakdown (below), the harness took it at the boundary the breakdown finds;
elsewhere at its opened pickup, else its admission, which leaves out a
command the agent ran before acknowledging a pointer it read itself. Where the
answering session's record can be read, the input also carries its reply's breakdown
(`reply`, `reply_phases.reply_breakdown`): the whole reply, Leaf's share of it
(delivery and those commands), the harness's other work before it took the input,
idle time between its turns, and the model's time and calls. Its case is `working`
where a turn was running at the admission, so the harness took the input at that
turn's next tool boundary or its end, else `waiting`. This command reads a Claude
Code session's transcript still in this machine's Claude Code projects
(`transcript_of`), which times no request or first output, so the
model's time stays unsplit; other harnesses' inputs carry no breakdown, and the
summary's reply rows count them missing. `leaf-dev journey run` reads the record of the
session it runs instead, on any harness (`_journey.User.sample`).

Each input whose opening session's record can be read also carries what its pickup
waited on (`pickup`, `reply_phases.pickup_wait`), and the `response-times` summary's `opened_*` rows
sort those waits by cause, each over its own inputs, with the seconds they add up
to.

Each input also carries the last line fork whose inputs name its message (`fork`: its
outcome, seconds, and why it posted no line where it didn't). A line fork's posted
line is the progress and first reply of its round's newest message. The
`response-times` summary's `delivered` row is how long an update read Delivered, from
its opened pickup to the session starting or answering it; `forked` times the first
reply over the inputs whose line fork posted its line, so a survey shows how soon
forks bring the agent's first words. A line under the table counts the line forks'
outcomes.

`prompted` waits are where nothing of Leaf's woke an idle session before the user
typed. The watch record says whether a watch ran and the protocol its Leaf spoke,
so one older than the page's could not read it; the transcript between admission
and pickup says the rest, such as a hook refusing a page a newer Leaf re-vendored.
"""

import statistics
from bisect import bisect_right
from collections.abc import Callable
from datetime import datetime
from functools import cache
from pathlib import Path

from leaf.base.files import list_revisions
from leaf.log.events import is_answer
from leaf.log.interaction_log import interaction_time, read_interactions
from leaf.log.thread_context import thread_names
from leaf.records.todos import start_reading
from leaf.source.registry.kernel import kinds_declaring
from leaf.source.revision_artifact import read_revision
from leaf_dev.reply_phases import (
    claude_code_records,
    claude_code_transcript,
    leaf_commands_ms,
    pickup_wait,
    reply_breakdown,
)


def visible_feedback(
    diagnostics: list[dict],
    input_attempts: dict[str, str],
    reply_inputs: dict[str, str],
) -> dict[str, dict]:
    """Pair submission and visible words in the same originating document.

    Retry copies are removed by read_interactions. The first observed submit for
    an attempt in one tab anchors that tab's measurement; a viewer in another tab
    cannot provide its endpoint. Stream attempts resolve through publication markers
    or a subsequently admitted answer. Streams without an exact input remain unjoined.
    """
    browser = sorted(
        (
            row
            for row in diagnostics
            if row["source"] == "client" and row["page"] == "/"
        ),
        key=lambda row: (row["session"], row["sequence"]),
    )
    origins = {}
    submitted = set()
    for row in browser:
        identity = input_attempts.get(row.get("attempt"))
        if row["type"] != "event_submit" or identity is None:
            continue
        key = (row["session"], identity)
        if key in submitted:
            continue
        submitted.add(key)
        origin = origins.get(identity)
        if origin is None or interaction_time(row["ts"]) < interaction_time(
            origin["ts"]
        ):
            origins[identity] = row
    result: dict[str, dict] = {}
    for row in browser:
        if row["type"] != "reply_visible" or row["visibility"] != "visible":
            continue
        identity = (
            row.get("input_id")
            or reply_inputs.get(row.get("reply_id"))
            or reply_inputs.get(row.get("attempt"))
        )
        origin = origins.get(identity)
        if origin is None or row["session"] != origin["session"]:
            continue
        assert identity is not None
        result.setdefault(
            identity,
            {
                "event_id": row.get("reply_id"),
                "at": row["observed_at"],
                "elapsed_s": (row["monotonic_ms"] - origin["monotonic_ms"]) / 1000,
                "session": row["session"],
                "clock": "browser_monotonic",
                "submit_sequence": origin["sequence"],
                "submit_monotonic_ms": origin["monotonic_ms"],
                "visible_sequence": row["sequence"],
                "visible_monotonic_ms": row["monotonic_ms"],
                "submit_visibility": origin["visibility"],
                "presentation_kind": row["presentation_kind"],
                "reply_kind": row["reply_kind"],
                "surface": row["surface"],
            },
        )
    return result


# What reads the record of the session that marked a milestone, in `reply_phases`'
# form, or returns None where it cannot.
type Records = Callable[[dict], list[dict] | None]


@cache
def session_records(session: str) -> list[dict] | None:
    """The Claude Code session's transcript records, read once a run, since a page
    holds many inputs a session took."""
    native = claude_code_transcript(session)
    return None if native is None else claude_code_records(native)


def transcript_of(milestone: dict) -> list[dict] | None:
    """The records of the Claude Code session that marked `milestone`, from its
    transcript on this machine (`session_records`), or None for another harness's
    session or one whose transcript is not here."""
    if milestone["harness"] != "claude-code" or not milestone["session"]:
        return None
    return session_records(milestone["session"])


def page_timings(
    page: Path,
    *,
    since: datetime | None,
    until: datetime,
    records: Records = transcript_of,
) -> dict:
    """Measure exact inputs and their feedback from recorded events.

    Events follow admission order even under wall-clock skew. Context declarations
    use host time; browser feedback uses its tab's clock. Every attention-bearing
    input version stays in the denominator, including missing feedback. `records`
    reads the session records the reply breakdown and pickup wait need.
    """
    page = page.resolve()
    observations = read_interactions(
        page,
        until=until,
        types=(
            "event",
            "event_submit",
            "reply_visible",
            "reply_stream_words",
            "run_context",
            "leaf_command",
            "watch",
            "fork_outcome",
        ),
    )
    contexts = [
        row
        for row in observations
        if row["source"] == "developer" and row["type"] == "run_context"
    ]
    context_times = [interaction_time(row["ts"]) for row in contexts]
    semantic = sorted(
        (row for row in observations if row["source"] == "semantic"),
        key=lambda row: row["event"]["seq"],
    )
    rows: dict[str, dict] = {}
    admitted_times = {}
    input_attempts = {}
    reply_inputs = {}
    unlinked = []
    # The working line each line fork posted, by the line's id: progress on its
    # round's newest message, which takes nothing in hand and so names no input of
    # its own (`leaf.agents.forks`).
    fork_lines = {
        row["line"]: row["inputs"][-1]
        for row in observations
        if row["type"] == "fork_outcome" and "line" in row
    }
    messages = kinds_declaring("message")
    threads = thread_names([observation["event"] for observation in semantic])
    titled: set[str] = set()
    # The inputs admitted to each thread while it had no title.
    untitled: dict[str, list[str]] = {}
    # Each input's first answer, which names the revision it stands on.
    answers: dict[str, dict] = {}
    for observation in semantic:
        event = observation["event"]
        stamp = interaction_time(event["ts"])
        in_cohort = since is None or stamp >= since
        identity, kind = event["id"], event["kind"]
        if event["author"] == "user" and kind in messages | {"edit"}:
            if kind == "edit" and event["base"] in rows:
                rows[event["base"]]["superseded_by_edit"] = identity
            if not event.get("attention") or not in_cohort:
                continue
            thread = threads[event["message"] if kind == "edit" else identity]
            if thread not in titled:
                untitled.setdefault(thread, []).append(identity)
            # The last declaration at or before admission wins a timestamp tie.
            index = bisect_right(context_times, stamp) - 1
            context = contexts[index] if index >= 0 else None
            admitted_times[identity] = stamp
            if "attempt" in event:
                input_attempts[event["attempt"]] = identity
            rows[identity] = {
                "page": str(page),
                "input_id": identity,
                "input_kind": kind,
                "message_id": event["message"] if kind == "edit" else identity,
                "superseded_by_edit": None,
                "admitted_at": event["ts"],
                "observed_until": until.isoformat(),
                "observed_for_s": (until - stamp).total_seconds(),
                "provenance": {
                    key: context[key]
                    for key in ("purpose", "run", "authored_source", "test")
                    if key in context
                }
                if context is not None
                else None,
                "milestones": {},
                "agent_sessions": {},
                "first_reply_kind": None,
                "first_reply_agent": None,
            }
            continue
        # The milestones this event marks, by the input each is of.
        marks: dict[str, tuple[str, ...]] = {}
        reply_kind = None
        start = start_reading(event)
        if kind == "pickup":
            phase = "failure" if event["phase"] == "failed" else event["phase"]
            marks = dict.fromkeys(event["events"], (phase,))
        elif identity in fork_lines:
            marks[fork_lines[identity]] = ("progress", "first_reply")
            reply_kind = "progress"
        elif start is not None:
            marks[start["item"]] = ("started",)
            if kind == "reply" and event.get("ephemeral"):
                marks[start["item"]] += ("progress", "first_reply")
                reply_kind = "progress"
        elif is_answer(event):
            marks[event["responds"]] = ("answered", "first_reply")
            reply_kind = "answer"
            answers.setdefault(event["responds"], event)
        elif kind == "reply" and "failure" in event:
            marks[event["responds"]] = ("failure",)
        elif (
            kind == "reply"
            and event["author"] == "agent"
            and not event.get("responds")
            and in_cohort
        ):
            unlinked.append(identity)
        if reply_kind is not None:
            [replied] = marks
            reply_inputs[identity] = replied
            if "attempt" in event:
                reply_inputs[event["attempt"]] = replied
        # A thread's first title, from the page server or in the agent's own message
        # (`events.build_threads`), titles each input that waited for one.
        named = (
            event["thread"]
            if kind == "thread_title"
            else threads[identity]
            if kind in messages and "title" in event
            else None
        )
        if named is not None and named not in titled:
            titled.add(named)
            for input_id in untitled.pop(named, ()):
                marks[input_id] = (*marks.get(input_id, ()), "titled")
        if not marks:
            continue
        context = observation["context"] or {}
        turn = event.get("turn", start.get("turn") if start is not None else None)
        actor = _agent_context(event.get("session"), turn, context)
        for input_id, marked in marks.items():
            if input_id not in rows:
                continue
            row = rows[input_id]
            row["agent_sessions"][identity] = actor
            milestone = {
                "event_id": identity,
                "at": event["ts"],
                "elapsed_s": (stamp - admitted_times[input_id]).total_seconds(),
                **actor,
                "clock": "server_wall",
            }
            if "first_reply" in marked and "first_reply" not in row["milestones"]:
                row["first_reply_kind"] = reply_kind
                row["first_reply_agent"] = event.get("agent")
            for name in marked:
                row["milestones"].setdefault(name, milestone)
    # When the page published each revision this directory holds.
    activated = {
        revision: read_revision(page, revision).activated_at
        for revision in list_revisions(page)
    }
    for input_id, answer in answers.items():
        if input_id not in rows or answer.get("revision") not in activated:
            continue
        at = activated[answer["revision"]]
        elapsed = (interaction_time(at) - admitted_times[input_id]).total_seconds()
        if 0 <= elapsed < rows[input_id]["observed_for_s"]:
            rows[input_id]["milestones"]["published"] = {
                "event_id": answer["id"],
                "revision": answer["revision"],
                "at": at,
                "elapsed_s": elapsed,
                **rows[input_id]["agent_sessions"][answer["id"]],
                "clock": "server_wall",
            }
    for observation in observations:
        if (
            observation["source"] != "server"
            or observation["type"] != "reply_stream_words"
        ):
            continue
        input_id = observation["input_id"]
        if input_id not in rows:
            continue
        row = rows[input_id]
        identity = observation["attempt"]
        stamp = interaction_time(observation["ts"])
        actor = _agent_context(
            observation["session"], observation["turn"], observation["context"] or {}
        )
        row["agent_sessions"].setdefault(identity, actor)
        reply_inputs[identity] = input_id
        previous = row["milestones"].get("first_reply")
        if previous is None or stamp < interaction_time(previous["at"]):
            row["milestones"]["first_reply"] = {
                "event_id": None,
                "attempt": identity,
                "at": observation["ts"],
                "elapsed_s": (stamp - admitted_times[input_id]).total_seconds(),
                **actor,
                "clock": "server_wall",
            }
            row["first_reply_kind"] = "stream"
            row["first_reply_agent"] = observation["agent"]
    for identity, observation in visible_feedback(
        observations, input_attempts, reply_inputs
    ).items():
        rows[identity]["milestones"]["send_to_visible"] = observation
    commands = [
        row
        for row in observations
        if row["source"] == "cli" and row["type"] == "leaf_command"
    ]
    watches = [
        row for row in observations if row["source"] == "cli" and row["type"] == "watch"
    ]
    forks = [row for row in observations if row["type"] == "fork_outcome"]
    # The last line fork made for a message is its own: a message that joins its
    # round before the line goes in forks again for them all, and the earlier fork's
    # line drops.
    decided = {message: fork for fork in forks for message in fork["inputs"]}
    for row in rows.values():
        fork = decided.get(row["message_id"])
        row["fork"] = (
            None
            if fork is None
            else {
                "outcome": fork["outcome"],
                "elapsed_s": fork["elapsedMs"] / 1000 if "elapsedMs" in fork else None,
                # Why no line went in, where none did.
                "why": fork.get("why"),
            }
        )
        answered = row["milestones"].get("answered")
        mine = [
            command
            for command in commands
            if answered is not None and command["session"] == answered["session"]
        ]
        row["reply"] = breakdown(row, mine, records)
        row["pickup"] = waited(row, watches, records)
        # From where the harness took the input, so a working harness's
        # commands for the work it was busy with stay out.
        took = row["milestones"].get("opened", {}).get("at", row["admitted_at"])
        row["leaf_commands_s"] = (
            None
            if answered is None
            else row["reply"]["leafCommandsMs"] / 1000
            if row["reply"] is not None
            else leaf_commands_ms(mine, took, answered["at"]) / 1000
        )
    return {
        "page": str(page),
        "unlinked_agent_replies": unlinked,
        "samples": list(rows.values()),
    }


def breakdown(row: dict, commands: list[dict], records: Records) -> dict | None:
    """The answered input's reply breakdown, with its case, where `records` reads
    the answering session's record; `commands` are its session's `leaf_command`
    records."""
    milestones = row["milestones"]
    if "answered" not in milestones or "opened" not in milestones:
        return None
    answered = milestones["answered"]
    read = records(answered)
    if read is None:
        return None
    reply = reply_breakdown(
        read,
        commands,
        row["admitted_at"],
        milestones["opened"]["at"],
        answered["at"],
    )
    return (
        {**reply, "case": "working" if reply["busyMs"] else "waiting"}
        if reply is not None
        else None
    )


def waited(row: dict, watches: list[dict], records: Records) -> dict | None:
    """What the input waited on before its opened pickup (`pickup_wait`), where
    `records` reads the record of the session that opened it, with the `watch`
    record of that session's watch running at the admission
    (`leaf.log.interaction_log.record_watch`), or None where none recorded one."""
    opened = row["milestones"].get("opened")
    if opened is None:
        return None
    read = records(opened)
    if read is None:
        return None
    admitted = interaction_time(row["admitted_at"])
    watch = next(
        (
            watch
            for watch in watches
            if watch["session"] == opened["session"]
            and interaction_time(watch["started"])
            <= admitted
            <= interaction_time(watch["ts"])
        ),
        None,
    )
    return {**pickup_wait(read, row["admitted_at"], opened["at"]), "watch": watch}


def _agent_context(session: str | None, turn: str | None, context: dict) -> dict:
    """Project captured native context only for the explicitly matching turn."""
    return {
        "session": session,
        "turn": turn,
        "harness": context.get("harness"),
        "turn_provider": ("native" if context["provider"] else "leaf")
        if turn is not None
        and context.get("turn") == turn
        and context.get("provider") is not None
        else None,
        "cwd": context.get("cwd"),
        "transcript_path": context.get("transcript_path"),
    }


def distribution(rows: list[dict], milestone: str) -> dict:
    """Observed elapsed seconds from admission to `milestone` (`spread`)."""
    return spread(
        rows,
        [
            row["milestones"][milestone]["elapsed_s"]
            for row in rows
            if milestone in row["milestones"]
        ],
    )


def spread(rows: list[dict], observed: list[float]) -> dict:
    """Observed seconds of `rows`, with missing and invalid-clock evidence counted.

    Percentiles use the standard library's inclusive interpolation. Negative
    intervals cannot describe response times and remain explicit clock errors.
    """
    valid = [value for value in observed if value >= 0]
    percentiles = (
        statistics.quantiles(valid, n=100, method="inclusive")
        if len(valid) > 1
        else valid * 99
    )
    return {
        "inputs": len(rows),
        "observed": len(valid),
        "missing": len(rows) - len(observed),
        "clock_errors": len(observed) - len(valid),
        "p50_s": statistics.median(valid) if valid else None,
        "p90_s": percentiles[89] if valid else None,
        "p95_s": percentiles[94] if valid else None,
        "max_s": max(valid) if valid else None,
        "total_s": sum(valid),
    }
