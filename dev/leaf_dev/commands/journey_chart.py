"""Chart the latest journey samples kept on this machine, or tabulate their replies.

The chart draws when each sign of the release ask came. The table (`--replies`)
gives, for each target and case (`journey.CASES`), the whole reply and Leaf's share
of it, beside the harness's other work before it took the comment and the model
calls the reply took (`reply_phases.reply_breakdown`), as ranges over the kept
samples of the latest version each target ran.
"""

import json
import re

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
        + (" with the hooks module" if sample.get("hooksModule") else "")
        + (" through a preview" if sample.get("preview") else "")
        + (" over HTTP" if sample.get("userEnd") == "http" else "")
    )


def latest(samples: list[dict]) -> list[dict]:
    """The samples of the latest version each chart row's target ran. Samples kept
    before the journey ran its steps (`steps`) are left out: their targets had
    other names, and their Claude Code ran headless."""
    samples = [sample for sample in samples if "steps" in sample]
    versions = {chart_target(sample): sample["version"] for sample in samples}
    return [s for s in samples if s["version"] == versions[chart_target(s)]]


def reply_table(samples: list[dict]) -> str:
    """A Markdown table of each target's replies in each case, in seconds."""
    replies: dict[tuple[str, str], list[dict]] = {}
    for sample in latest(samples):
        readings = {"release": sample["comment"]} | {
            name: reading
            for step in sample["steps"]
            for name, reading in step["comments"].items()
        }
        for case, name in sample.get("cases", {}).items():
            if reply := readings[name].get("reply"):
                replies.setdefault((chart_target(sample), case), []).append(reply)

    def span(values: list[float]) -> str:
        low, high = min(values), max(values)
        return (
            f"{low:.1f}" if f"{low:.1f}" == f"{high:.1f}" else f"{low:.1f}–{high:.1f}"
        )

    def seconds(group: list[dict], key: str) -> str:
        return span([reply[key] / 1000 for reply in group])

    lines = [
        (
            "| Target | Case | Runs | Whole reply | Leaf's share | Harness busy first "
            "| Model calls | Model time |"
        ),
        "| --- | --- | --: | --: | --: | --: | --: | --: |",
    ]
    for (target, case), group in sorted(
        replies.items(), key=lambda item: (item[0][0], list(CASES).index(item[0][1]))
    ):
        calls = [len(reply["modelCalls"]) for reply in group]
        lines.append(
            f"| {target} | {case} | {len(group)} | {seconds(group, 'wholeMs')} "
            f"| {seconds(group, 'leafMs')} | {seconds(group, 'busyMs')} "
            f"| {min(calls)}–{max(calls)} | {seconds(group, 'modelMs')} |"
        )
    return "\n".join(lines)


def chart_rows(samples: list[dict]) -> list[dict]:
    """One dot per sign each sample's release ask saw, for the latest version each
    target ran, with its options. A release ask the user answered a permission
    prompt during has a row of its own, since the prompt held the session for as
    long as it stood (`latest` says which samples it reads)."""
    rows = []
    for sample in latest(samples):
        name = chart_target(sample)
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
    help="Print a Markdown table of each target's replies in each case instead.",
)
def journey_chart(replies: bool) -> None:
    """Print an `lf-chart` of recorded delivery and work milestones, for
    the latest code version each target ran in this machine's kept samples."""
    path = samples_path()
    if not path.exists():
        raise click.ClickException(f"no samples kept in {path}; run `leaf-dev journey`")
    samples = [json.loads(line) for line in path.read_text().splitlines()]
    print(reply_table(samples) if replies else chart_markup(chart_rows(samples)))
