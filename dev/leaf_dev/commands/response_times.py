"""Query recorded and visible first feedback from retained Leaf page logs.

    leaf-dev response-times PAGE... [--since ISO] [--until ISO] [--json]

Each attention-bearing user message or edit is an input, regardless of its wording. Progress names
its exact input through `start.item`; an answer through `responds`. A thread parent
only locates presentation and cannot associate a reply with a later user message.
Pickup, work starts, titles, and failure receipts are separate milestones, not
agent replies. Answers can promise further work, so answer time is not task time.

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
JSON is also an analytical export for history that must outlive source pages.
"""

import json
import statistics
from bisect import bisect_right
from collections import Counter
from datetime import datetime
from pathlib import Path

import click
from leaf.event_log import read_events
from leaf.interaction_log import interaction_time, read_interactions
from leaf.schema import MESSAGE_KINDS
from leaf.state import now_iso
from leaf.thread import is_answer
from leaf.todos import start_reading


def visible_feedback(
    diagnostics: list[dict], messages: dict[str, dict], reply_inputs: dict[str, str]
) -> dict[str, dict]:
    """Pair submission and visible words in the same originating document.

    Retry copies are removed by read_interactions. The first observed submit for
    an attempt in one tab anchors that tab's measurement; a viewer in another tab
    cannot provide its endpoint. Stream attempts may resolve through a subsequently
    admitted answer. Uncommitted streams without an exact input remain unjoined.
    """
    attempts = {
        message["attempt"]: identity
        for identity, message in messages.items()
        if "attempt" in message
    }
    browser = sorted(
        (
            row
            for row in diagnostics
            if row["source"] == "client" and row["page"] == "/"
        ),
        key=lambda row: row["sequence"],
    )
    submissions = {}
    for row in browser:
        if row["type"] == "event_submit" and row.get("attempt") in attempts:
            submissions.setdefault((row["session"], row["attempt"]), row)
    origins = {}
    for (_, attempt), row in sorted(
        submissions.items(), key=lambda item: interaction_time(item[1]["ts"])
    ):
        origins.setdefault(attempts[attempt], row)
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
    """One row per admitted user message version in [since, until), observed until cutoff.

    Evidence comes from this page's semantic and diagnostic logs. Repeated delivery receipts or progress
    updates retain their first timestamp. Unaddressed replies are never guessed
    from their parent or their proximity to an input.
    """
    page = page.resolve()
    events = [
        event for event in read_events(page) if interaction_time(event["ts"]) < until
    ]
    messages = {
        event["id"]: event
        for event in events
        if event["author"] == "user"
        and event["kind"] in MESSAGE_KINDS | {"edit"}
        and event["attention"]
        and (since is None or interaction_time(event["ts"]) >= since)
    }
    diagnostics = read_interactions(
        page, until=until, types=("event_submit", "reply_visible", "run_context")
    )
    contexts = [
        row
        for row in diagnostics
        if row["source"] == "developer" and row["type"] == "run_context"
    ]
    rows = {}
    for identity, message in messages.items():
        admitted = interaction_time(message["ts"])
        # Declarations precede their inputs; the last appended context wins a tie.
        context_index = (
            bisect_right(
                contexts, admitted, key=lambda row: interaction_time(row["ts"])
            )
            - 1
        )
        context = contexts[context_index] if context_index >= 0 else None
        rows[identity] = {
            "page": str(page),
            "input_id": identity,
            "input_kind": message["kind"],
            "message_id": message["message"] if message["kind"] == "edit" else identity,
            "superseded_by_edit": None,
            "admitted_at": message["ts"],
            "observed_until": until.isoformat(),
            "observed_for_s": (until - admitted).total_seconds(),
            "provenance": {
                key: context[key]
                for key in ("purpose", "run", "authored_source", "test")
                if key in context
            }
            if context is not None
            else None,
            "milestones": {},
            "first_reply_kind": None,
            "first_reply_agent": None,
        }
    reply_inputs = {}
    unlinked = []

    def record(identity: str, names: tuple[str, ...], event: dict) -> None:
        if identity not in rows:
            return
        row = rows[identity]
        milestone = {
            "event_id": event["id"],
            "at": event["ts"],
            "elapsed_s": (
                interaction_time(event["ts"]) - interaction_time(row["admitted_at"])
            ).total_seconds(),
            "session": event.get("session"),
            "clock": "server_wall",
        }
        if "first_reply" in names and "first_reply" not in row["milestones"]:
            row["first_reply_kind"] = "progress" if event.get("ephemeral") else "answer"
            row["first_reply_agent"] = event.get("agent")
        for name in names:
            row["milestones"].setdefault(name, milestone)

    for event in events:
        response_input = None
        if (
            event["kind"] == "edit"
            and event["author"] == "user"
            and event["base"] in rows
        ):
            rows[event["base"]]["superseded_by_edit"] = event["id"]
        if event["kind"] == "pickup":
            for identity in event["events"]:
                record(identity, (event["phase"],), event)
        if started := start_reading(event):
            record(started["item"], ("started",), event)
            if event["kind"] == "reply" and event.get("ephemeral"):
                record(started["item"], ("progress", "first_reply"), event)
                response_input = started["item"]
        if is_answer(event):
            record(event["responds"], ("answered", "first_reply"), event)
            response_input = event["responds"]
        elif event["kind"] == "reply" and "failure" in event:
            record(event["responds"], ("failure",), event)
        if response_input is not None:
            reply_inputs[event["id"]] = response_input
            if "attempt" in event:
                reply_inputs[event["attempt"]] = response_input
        if (
            event["kind"] == "reply"
            and event["author"] == "agent"
            and not event.get("responds")
            and not event.get("start")
            and (since is None or interaction_time(event["ts"]) >= since)
        ):
            unlinked.append(event["id"])

    for identity, observation in visible_feedback(
        diagnostics, messages, reply_inputs
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
