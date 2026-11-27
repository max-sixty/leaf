"""Query recorded and visible first feedback from Leaf page logs.

    leaf-dev logs response-times PAGE... [--since ISO] [--until ISO] [--json]

Each input's milestones, and what its reply and pickup waited on, are as
`leaf_dev.page_timings`'s header says; this prints their spread over the pages'
inputs. A survey of every page touched in a week:

    leaf-dev logs response-times --since 2026-10-20T00:00-07:00 $(find
        ~/.local/state/leaf/pages -maxdepth 2 -name events.jsonl -mtime -7 |
        sed 's:/events.jsonl$::')
"""

import json
from collections import Counter
from pathlib import Path

import click

from leaf.base.state import now_iso
from leaf.log.event_log import initialized
from leaf.log.interaction_log import interaction_time
from leaf_dev.page_timings import distribution, page_timings, spread
from leaf_dev.reply_phases import WAIT_CAUSES


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
        if not initialized(page):
            raise click.ClickException(f"{page} is not an initialized page")
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
            "titled",
            "started",
            "progress",
            "first_reply",
            "send_to_visible",
            "published",
            "answered",
            "failure",
        )
    }
    # How long each update read Delivered: from the harness opening it into a turn
    # to the session starting or answering it.
    delivered = [row for row in rows if "opened" in row["milestones"]]
    summary["delivered"] = spread(
        delivered,
        [
            min(
                row["milestones"][name]["elapsed_s"]
                for name in ("started", "answered")
                if name in row["milestones"]
            )
            - row["milestones"]["opened"]["elapsed_s"]
            for row in delivered
            if {"started", "answered"} & row["milestones"].keys()
        ],
    )
    summary["forked"] = distribution(
        [row for row in rows if row["fork"] and row["fork"]["outcome"] == "posted"],
        "first_reply",
    )
    # What came of the line forks, over the inputs they decided.
    fork_counts = Counter(row["fork"]["outcome"] for row in rows if row["fork"])
    summary["leaf_commands"] = spread(
        rows,
        [row["leaf_commands_s"] for row in rows if row["leaf_commands_s"] is not None],
    )
    for cause in WAIT_CAUSES:
        waits = [
            row for row in rows if row["pickup"] and row["pickup"]["cause"] == cause
        ]
        summary[f"opened_{cause}"] = spread(
            waits, [row["pickup"]["ms"] / 1000 for row in waits]
        )
    for case in ("waiting", "working"):
        replies = [
            row["reply"]
            for row in rows
            if row["reply"] is not None and row["reply"]["case"] == case
        ]
        for name, key in (("whole", "wholeMs"), ("leaf_share", "leafMs")):
            summary[f"{name}_{case}"] = spread(
                rows, [reply[key] / 1000 for reply in replies]
            )
    if as_json:
        click.echo(
            json.dumps(
                {
                    "pages": [
                        {k: v for k, v in reading.items() if k != "samples"}
                        for reading in readings
                    ],
                    "summary": summary,
                    "forks": dict(fork_counts),
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
        "delivered runs from opened to the session's start or answer; forked is first_reply over the inputs whose line fork posted its working line."
    )
    click.echo(f"Line forks: {dict(fork_counts) or 'none'}")
    click.echo(
        "leaf_commands reads each command's own record on any harness; whole_* and leaf_share_* read Claude Code transcripts, so their missing includes every other input."
    )
    click.echo(
        "opened_* sorts each opened pickup a Claude Code transcript on this machine covers by what ended its wait (reply_phases.pickup_wait), over those inputs alone."
    )
    click.echo(
        "milestone           observed  missing  clock errors      p50      p90      p95      max     total"
    )
    for name, stats in summary.items():
        values = (
            " ".join(
                f"{stats[key]:8.1f}" if stats[key] is not None else f"{'—':>8}"
                for key in ("p50_s", "p90_s", "p95_s", "max_s")
            )
            + f" {stats['total_s']:9.0f}"
        )
        click.echo(
            f"{name:19} {stats['observed']:8} {stats['missing']:8} {stats['clock_errors']:12} {values}"
        )
