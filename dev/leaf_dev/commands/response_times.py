"""Query recorded and visible first feedback from Leaf page logs.

    leaf-dev response-times PAGE... [--since ISO] [--until ISO] [--json]

Each attention-bearing user message version is an input. Pickup, work starts and
failure receipts are separate milestones. Progress and answers both count as first
replies; answer time does not claim the task is finished.

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
exact input through pickup, start, progress or answer evidence. Missing turns remain
unknown; browser diagnostic sessions are separate identities. Captured context
identifies the harness and the provider of an explicitly recorded matching turn;
no current claim or timestamp proximity supplies this identity.
"""

import json
import statistics
from bisect import bisect_right
from collections import Counter
from datetime import datetime
from pathlib import Path

import click
from leaf.interaction_log import interaction_time, read_interactions
from leaf.schema import MESSAGE_KINDS
from leaf.state import now_iso
from leaf.thread import is_answer
from leaf.todos import start_reading


def visible_feedback(
    diagnostics: list[dict],
    input_attempts: dict[str, str],
    reply_inputs: dict[str, str],
) -> dict[str, dict]:
    """Pair submission and visible words in the same originating document.

    Retry copies are removed by read_interactions. The first observed submit for
    an attempt in one tab anchors that tab's measurement; a viewer in another tab
    cannot provide its endpoint. Stream attempts may resolve through a subsequently
    admitted answer. Uncommitted streams without an exact input remain unjoined.
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
    result = {}
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


def page_timings(page: Path, *, since: datetime | None, until: datetime) -> dict:
    """Measure exact inputs and their feedback from recorded events.

    Events follow admission order even under wall-clock skew. Context declarations
    use host time; browser feedback uses its tab's clock. Every attention-bearing
    input version stays in the denominator, including missing feedback.
    """
    page = page.resolve()
    observations = read_interactions(
        page,
        until=until,
        types=("event", "event_submit", "reply_visible", "run_context"),
    )
    contexts = [
        row
        for row in observations
        if row["source"] == "developer" and row["type"] == "run_context"
    ]
    context_times = [interaction_time(row["ts"]) for row in contexts]
    semantic = sorted(
        (row for row in observations if row["source"] == "semantic"),
        key=lambda row: row["event_seq"],
    )
    rows = {}
    admitted_times = {}
    input_attempts = {}
    reply_inputs = {}
    unlinked = []
    for observation in semantic:
        event = observation["event"]
        stamp = interaction_time(event["ts"])
        in_cohort = since is None or stamp >= since
        identity, kind = event["id"], event["kind"]
        if event["author"] == "user" and kind in MESSAGE_KINDS | {"edit"}:
            if kind == "edit" and event["base"] in rows:
                rows[event["base"]]["superseded_by_edit"] = identity
            if not event.get("attention") or not in_cohort:
                continue
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
        inputs, names, reply_kind = [], (), None
        start = start_reading(event)
        if kind == "pickup":
            inputs = event["events"]
            names = ("failure" if event["phase"] == "failed" else event["phase"],)
        elif start is not None:
            inputs, names = [start["item"]], ("started",)
            if kind == "reply" and event.get("ephemeral"):
                names += ("progress", "first_reply")
                reply_kind = "progress"
        elif is_answer(event):
            inputs, names, reply_kind = (
                [event["responds"]],
                ("answered", "first_reply"),
                "answer",
            )
        elif kind == "reply" and "failure" in event:
            inputs, names = [event["responds"]], ("failure",)
        elif (
            kind == "reply"
            and event["author"] == "agent"
            and not event.get("responds")
            and in_cohort
        ):
            unlinked.append(identity)
        if not names:
            continue
        if reply_kind is not None:
            reply_inputs[identity] = inputs[0]
            if "attempt" in event:
                reply_inputs[event["attempt"]] = inputs[0]
        context = observation["context"] or {}
        turn = event.get("turn", start.get("turn") if start is not None else None)
        actor = {
            "session": event.get("session"),
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
        for input_id in inputs:
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
            if reply_kind is not None and "first_reply" not in row["milestones"]:
                row["first_reply_kind"] = reply_kind
                row["first_reply_agent"] = event.get("agent")
            for name in names:
                row["milestones"].setdefault(name, milestone)
    for identity, observation in visible_feedback(
        observations, input_attempts, reply_inputs
    ).items():
        rows[identity]["milestones"]["send_to_visible"] = observation
    return {
        "page": str(page),
        "unlinked_agent_replies": unlinked,
        "samples": list(rows.values()),
    }


def distribution(rows: list[dict], milestone: str) -> dict:
    """Observed elapsed seconds, with missing and invalid-clock evidence counted.

    Percentiles use the standard library's inclusive interpolation. Negative
    intervals cannot describe response times and remain explicit clock errors.
    """
    observed = [
        row["milestones"][milestone]["elapsed_s"]
        for row in rows
        if milestone in row["milestones"]
    ]
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
    }


@click.command()
@click.argument(
    "pages",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--since", help="Include inputs from this timezone-qualified ISO timestamp."
)
@click.option("--until", help="Exclusive input/evidence cutoff; defaults to now.")
@click.option(
    "--exclude-purpose",
    multiple=True,
    help="Exclude a declared run purpose (repeatable); unmarked inputs stay unknown.",
)
@click.option(
    "--json", "as_json", is_flag=True, help="Keep every sample and its exact evidence."
)
def response_times(
    pages: tuple[Path, ...],
    since: str | None,
    until: str | None,
    exclude_purpose: tuple[str, ...],
    as_json: bool,
):
    """Distribution from user message versions to first progress or answer in PAGE logs.

    Declared run purposes can select out test/automated runs; an unmarked input
    remains unknown. Missing observations remain in the denominator. No input text
    is printed. --until fixes both the cohort and its observation cutoff.
    """
    try:
        beginning = interaction_time(since) if since else None
        cutoff = interaction_time(until or now_iso())
    except (TypeError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    if beginning is not None and beginning >= cutoff:
        raise click.ClickException("--since must precede --until")
    paths = sorted({page.resolve() for page in pages})
    for page in paths:
        if not (page / "events.jsonl").is_file():
            raise click.ClickException(f"No events.jsonl in {page}")
    readings = [page_timings(page, since=beginning, until=cutoff) for page in paths]
    rows = [row for reading in readings for row in reading["samples"]]
    before = len(rows)
    purposes = Counter(
        row["provenance"]["purpose"] if row["provenance"] is not None else "unknown"
        for row in rows
    )
    rows = [
        row
        for row in rows
        if row["provenance"] is None
        or row["provenance"]["purpose"] not in exclude_purpose
    ]
    selection = {
        "inputs_before_filter": before,
        "excluded_inputs": before - len(rows),
        "exclude_purpose": list(exclude_purpose),
        "declared_purposes": dict(purposes),
    }
    summary = {
        name: distribution(rows, name)
        for name in (
            "queued",
            "opened",
            "started",
            "progress",
            "first_reply",
            "send_to_visible",
            "answered",
            "failure",
        )
    }
    if as_json:
        click.echo(
            json.dumps(
                {
                    "pages": [
                        {k: v for k, v in reading.items() if k != "samples"}
                        for reading in readings
                    ],
                    "summary": summary,
                    "selection": selection,
                    "samples": rows,
                },
                indent=2,
            )
        )
        return
    click.echo(
        f"{len(rows)} user message versions across {len(paths)} pages; observed until {cutoff.isoformat()}"
    )
    click.echo(
        "Seconds from server admission, except send_to_visible uses one browser's monotonic clock."
    )
    click.echo(
        f"Declared run purposes: {dict(purposes)}; excluded inputs: {before - len(rows)}"
    )
    click.echo(
        "Percentiles cover observed milestones only; visibility diagnostics are best effort."
    )
    click.echo(
        f"Unlinked agent replies: {sum(len(reading['unlinked_agent_replies']) for reading in readings)}; missing means no exact-linked observation."
    )
    click.echo(
        "milestone       observed  missing  clock errors      p50      p90      p95      max"
    )
    for name, stats in summary.items():
        values = " ".join(
            f"{stats[key]:8.1f}" if stats[key] is not None else f"{'—':>8}"
            for key in ("p50_s", "p90_s", "p95_s", "max_s")
        )
        click.echo(
            f"{name:15} {stats['observed']:8} {stats['missing']:8} {stats['clock_errors']:12} {values}"
        )
