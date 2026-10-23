"""Chart the latest journey samples kept on this machine, or tabulate their replies.

The chart draws when each sign of the release ask came. The table (`--replies`)
gives, for each target and case (`journey.CASES`, the harness waiting or working
when the release ask reaches it), the time of the whole reply and the parts it went
to (`reply_phases.reply_breakdown`), over the kept samples of the latest version
each target ran in each case, or with `--since` over every sample kept since then,
for a batch whose commits leave the plugin unchanged. The benchmark is the time;
the model calls and their output tokens only say where it went.
"""

import json
import re
import statistics
from datetime import datetime

import click

from leaf_dev.commands.journey import CASES, samples_path

# Exact-input milestones on the page server's clock, from comment admission.
SIGNS = (
    ("title", "sinceAdmissionMs", "titled", "var(--series-2)"),
    ("picked up", "sinceAdmissionMs", "pickedUp", "var(--series-5)"),
    ("work started", "sinceAdmissionMs", "started", "var(--series-1)"),
    ("progress", "sinceAdmissionMs", "progress", "var(--series-4)"),
    ("reply", "sinceAdmissionMs", "replied", "var(--series-3)"),
)
TARGET_NAMES = {
    "claude-code": "Claude Code",
    "codex-app-server": "Codex App Server",
    "codex-queue": "Codex queue",
    "pi": "Pi",
}
TICKS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500)
# Plot sizes no margin to its labels: about this many px a character at its font.
LABEL_PX = 5.5


def chart_target(sample: dict) -> str:
    """What a chart row names: the target, with the options it ran under and its
    user's end where that is not a browser."""
    return (
        TARGET_NAMES.get(sample["target"], sample["target"])
        + (" through a preview" if sample.get("preview") else "")
        + (" over HTTP" if sample.get("userEnd") == "http" else "")
    )


def latest(samples: list[dict]) -> list[dict]:
    """The samples of the latest version each chart row's target ran in each case.
    Samples kept before the journey ran its steps (`steps`) are left out: their
    targets had other names, and their Claude Code ran headless."""

    def row(sample: dict) -> tuple[str, str]:
        return chart_target(sample), sample.get("case", "waiting")

    samples = [sample for sample in samples if "steps" in sample]
    versions = {row(sample): sample["version"] for sample in samples}
    return [s for s in samples if s["version"] == versions[row(s)]]


def chosen(samples: list[dict], since: datetime | None) -> list[dict]:
    """The samples a chart or table reads: those kept since `since`, else the
    latest version's (`latest`)."""
    if since is None:
        return latest(samples)
    return [
        sample
        for sample in samples
        if "steps" in sample and datetime.fromisoformat(sample["at"]) >= since
    ]


# The parts of a reply (`reply_phases.reply_breakdown`) the table attributes it to,
# each moment once, in the order they come.
PARTS = (
    ("Harness busy first", "busyMs"),
    ("Delivery", "deliveryMs"),
    ("Leaf's commands", "leafCommandsMs"),
    ("Leaf's hooks", "leafHooksMs"),
    ("Harness", "harnessMs"),
    ("Model: wait", "waitMs"),
    ("Model: generation", "generationMs"),
    ("Model: unsplit", None),
    ("Other tools", "otherToolsMs"),
    ("Idle", "idleMs"),
)


def reply_table(samples: list[dict], since: datetime | None = None) -> str:
    """A Markdown table of where each target's replies in each case went: the whole
    reply's mean and range, in seconds, then each part's mean and its share of the
    whole, which add up to it. Model time a harness reports no first output for stays
    unsplit. Leaf's share, the model calls and their output tokens follow as
    diagnostics."""
    replies: dict[tuple[str, str], list[dict]] = {}
    for sample in chosen(samples, since):
        if "case" in sample and (reply := sample["comment"].get("reply")):
            key = (chart_target(sample), sample["case"])
            replies.setdefault(key, []).append(reply)
    groups = sorted(
        replies.items(), key=lambda item: (item[0][0], CASES.index(item[0][1]))
    )

    def part(reply: dict, key: str | None) -> float:
        if key is None:
            # Samples kept before the model's time was split have no parts.
            split = reply.get("waitMs", 0) + reply.get("generationMs", 0)
            return (reply["modelMs"] - split) / 1000
        return reply.get(key, 0) / 1000

    def row(name: str, cell) -> str:
        return f"| {name} | " + " | ".join(cell(group) for _, group in groups) + " |"

    def share(key: str | None):
        def cell(group: list[dict]) -> str:
            mean = statistics.fmean(part(reply, key) for reply in group)
            whole = statistics.fmean(reply["wholeMs"] / 1000 for reply in group)
            return f"{mean:.1f} ({mean / whole:.0%})"

        return cell

    def span(values: list[float], digits: int = 1) -> str:
        low, high = min(values), max(values)
        return (
            f"{low:.{digits}f}"
            if low == high
            else f"{low:.{digits}f}–{high:.{digits}f}"
        )

    def whole(less: str | None = None):
        """The whole reply's mean and range, less the `less` part."""

        def cell(group: list[dict]) -> str:
            values = [
                (reply["wholeMs"] - (reply[less] if less else 0)) / 1000
                for reply in group
            ]
            return f"**{statistics.fmean(values):.1f}** ({span(values)})"

        return cell

    def tokens(group: list[dict]) -> str:
        known = [r["outputTokens"] for r in group if r.get("outputTokens") is not None]
        return span(known, 0) if known else "–"

    lines = [
        "| Seconds, mean (share) | "
        + " | ".join(f"{target}, {case}" for (target, case), _ in groups)
        + " |",
        "| --- |" + " --: |" * len(groups),
        row("Runs", lambda group: str(len(group))),
        row("Whole reply (range)", whole()),
        row("After the boundary (range)", whole("busyMs")),
        *(row(name, share(key)) for name, key in PARTS),
        row("Leaf's share", share("leafMs")),
        row(
            "Model calls", lambda group: span([len(r["modelCalls"]) for r in group], 0)
        ),
        row("Output tokens", tokens),
    ]
    return "\n".join(lines)


def chart_rows(samples: list[dict], since: datetime | None = None) -> list[dict]:
    """One dot per sign each sample's release ask saw, for the latest version each
    target ran, with its options. A release ask the user answered a permission
    prompt during has a row of its own, since the prompt held the session for as
    long as it stood (`latest` says which samples it reads)."""
    rows = []
    for sample in chosen(samples, since):
        name = chart_target(sample) + (
            " while working" if sample.get("case") == "working" else ""
        )
        version = re.sub(r"[0-9a-f]{32,}", lambda sha: sha[0][:8], sample["version"])
        prompted = (
            " after a permission prompt" if sample["comment"].get("approved") else ""
        )
        row = f"{name}{prompted} at {version}"
        for sign, clock, step, _ in SIGNS:
            if (ms := sample["comment"][clock].get(step)) is not None:
                rows.append({"row": row, "sign": sign, "s": round(ms / 1000, 2)})
    return rows


def chart_markup(rows: list[dict]) -> str:
    """An `lf-chart` element drawing `rows` on a log axis of seconds."""
    seconds = [r["s"] for r in rows]
    domain = [min(seconds) / 1.5, max(seconds) * 1.5]
    shown = [entry for entry in SIGNS if any(r["sign"] == entry[0] for r in rows)]
    described = "; ".join(
        f"{row}: "
        + ", ".join(f"{r['sign']} {r['s']} s" for r in rows if r["row"] == row)
        for row in dict.fromkeys(r["row"] for r in rows)
    )
    # Plot's options are JavaScript, so the tick format can be a function: its log
    # axis otherwise labels in SI units, 100m for 0.1 s.
    body = f"""{{
  ariaLabel: {json.dumps(f"Seconds after the comment until each sign. {described}.")},
  x: {{
    type: "log",
    domain: {json.dumps(domain)},
    ticks: {json.dumps([t for t in TICKS if domain[0] <= t <= domain[1]])},
    tickFormat: (d) => String(d),
    grid: true,
    label: "seconds after the comment (log scale)",
  }},
  y: {{label: null}},
  color: {{
    legend: true,
    domain: {json.dumps([sign for sign, *_ in shown])},
    range: {json.dumps([color for *_, color in shown])},
  }},
  symbol: {{domain: {json.dumps([sign for sign, *_ in shown])}}},
  marginLeft: {LABEL_PX * max(len(r["row"]) for r in rows) + 16},
  marks: [
    Plot.dot({json.dumps(rows)}, {{x: "s", y: "row", fill: "sign", symbol: "sign", r: 6}}),
  ],
}}"""
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<lf-chart id="journey-signs" data-height="240"><pre>\n{escaped}\n</pre></lf-chart>'


@click.command()
@click.option(
    "--replies",
    is_flag=True,
    help="Print a Markdown table of where each target's replies went in each case "
    "instead.",
)
@click.option(
    "--since",
    type=datetime.fromisoformat,
    help="Read every sample kept since this ISO time, with its zone, rather than "
    "the latest version's.",
)
def journey_chart(replies: bool, since: datetime | None) -> None:
    """Print an `lf-chart` of recorded delivery and work milestones, for
    the latest code version each target ran in this machine's kept samples."""
    path = samples_path()
    if not path.exists():
        raise click.ClickException(f"no samples kept in {path}; run `leaf-dev journey`")
    if since is not None and since.tzinfo is None:
        raise click.BadParameter("give a time zone, as in 2026-10-20T18:10-07:00")
    samples = [json.loads(line) for line in path.read_text().splitlines()]
    print(
        reply_table(samples, since)
        if replies
        else chart_markup(chart_rows(samples, since))
    )
