"""Write a Leaf page showing what an authored-task comparison produced.

`leaf-dev eval` keeps each `arrangement_eval` sample's screenshots, traces and
verdicts under `.tmp/eval/<run>/`, where the Promptfoo viewer shows them one sample
at a time. This command writes them to one page the user reads side by side: per
task, what each condition spent and wrote, and for each pair the final version's
screens at every width with the judges' verdicts and the defects they named. Pairs
and their verdicts come from `eval-pairs`; without its `pairs.json` the samples
are listed unpaired. Each run rewrites the page's `index.html`, so a later run's
page replaces the earlier one under the same comments.
"""

import json
import statistics
import subprocess
from html import escape
from pathlib import Path

import click

from leaf_dev import LEAF_COMMAND
from leaf_dev.arms import observed_sum
from leaf_dev.arrangement_eval import WIDTHS
from leaf_dev.authoring_score import sample_inputs
from leaf_dev.eval_pairs import final_shots, samples

LABELS = {"laptop": "Laptop", "narrow": "900px", "short": "900 × 600", "phone": "Phone"}

STYLE = """
.pair-shots { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: 1rem; }
.pair-shots > * { min-width: 0; overflow-wrap: anywhere; }
.pair-shots figure { margin: 0; }
.pair-shots img { width: 100%; height: auto; border: 1px solid var(--rule, #ccc); }
.pair-shots figcaption { font-weight: 600; }
.pair-shots details img { margin-top: .5rem; }
"""


def leaf(*args: str) -> str:
    return subprocess.run(
        [*LEAF_COMMAND, *args], check=True, capture_output=True, text=True
    ).stdout


def condition(column: str) -> str:
    if "/html/" in column:
        return "HTML"
    if "/base/" in column:
        return "Leaf (base)"
    if "/candidate/" in column:
        return "Leaf (candidate)"
    return column


def measures(sample: dict, subject: str) -> dict:
    """What a sample's author spent over its phases, the final version's code, and
    whether its decision was applied as chosen."""
    recorded = {
        int(key): value for key, value in sample["diagnostics"]["phases"].items()
    }
    selected = sample.get("phase") or max(recorded)
    session = [recorded[p]["trace"] for p in sorted(recorded) if p <= selected]
    final = recorded[selected]
    return {
        "minutes": observed_sum(p["minutes"] for p in session),
        "cost": observed_sum(p["cost_usd"] for p in session),
        "turns": sum(p["turns"] for p in session),
        "css": final.get("css_lines"),
        "script": final.get("script_lines"),
        "applied": (sample["checks"].get("decision-applied") is True)
        if selected >= 4
        and selected == max(recorded)
        and "decision-applied" in sample["checks"]
        else None,
    }


def screens(page: Path, sample: dict, subject: str) -> dict[str, list[str]]:
    """The final version's screens by width, as page media paths."""
    found = {
        name: [Path(path) for path in paths]
        for name, paths in final_shots(sample, subject).items()
    }
    files = [str(path) for paths in found.values() for path in paths]
    added = {}
    for start in range(0, len(files), 50):
        for line in leaf(
            "page", "media", str(page), *files[start : start + 50]
        ).splitlines():
            record = json.loads(line)
            added[record["source"]] = record["path"]
    return {name: [added[str(path)] for path in paths] for name, paths in found.items()}


def shot(path: str, alt: str, lazy: bool = False) -> str:
    loading = ' loading="lazy"' if lazy else ""
    return f'<a href="{path}"><img src="{path}" alt="{escape(alt)}"{loading}></a>'


def column_figure(label: str, sample: str, paths: list[str], width: str) -> str:
    if not paths:
        return f"<figure><figcaption>{label}</figcaption><p>No screens.</p></figure>"
    alt = f"{label} page, {LABELS[width]}"
    rest = "".join(
        shot(p, f"{alt}, screen {i}", True) for i, p in enumerate(paths[1:], 2)
    )
    more = (
        f"<details><summary>{len(paths) - 1} more screens</summary>{rest}</details>"
        if rest
        else ""
    )
    return (
        f"<figure><figcaption>{label} <code>{sample}</code></figcaption>"
        f"{shot(paths[0], alt + ', first screen')}{more}</figure>"
    )


def verdict_line(pair: dict) -> str:
    orders = [o["overall"] if o else "no verdict" for o in pair["orders"]]
    named = [condition(o) if "/" in o else o for o in orders]
    if pair["winner"]:
        if pair["winner"] == "tie":
            return "Tie in both orders"
        return f"{condition(pair['winner'])} preferred in both orders"
    if any(
        o is None or o["overall"] == "insufficient_evidence" for o in pair["orders"]
    ):
        return "Insufficient observation for a winner"
    return f"Split: {named[0]} in one order, {named[1]} in the other"


def defects(pair: dict, column: str) -> str:
    """The defects each order's judgment named, under that order, since the two
    judgments of one pair often name the same defect."""
    lists = [
        f"<p>Order {n}</p><ul>"
        + "".join(f"<li>{escape(d)}</li>" for d in o["defects"].get(column) or [])
        + "</ul>"
        for n, o in enumerate(pair["orders"], 1)
        if o and o["defects"].get(column)
    ]
    return "".join(lists) or "<p>None named.</p>"


def reasons(pair: dict) -> str:
    rows = "".join(
        f"<li>Order {n}: {escape(o.get('reason') or '')} "
        f"({escape(o.get('margin') or '')})</li>"
        for n, o in enumerate(pair["orders"], 1)
        if o
    )
    return f"<details><summary>Judge's reasons</summary><ul>{rows}</ul></details>"


def pair_section(page: Path, subject: str, n: int, pair: dict | None, x, y) -> str:
    sid = f"{subject}-pair-{n}"
    columns = [
        (condition(c), c, {**s, "phase": pair.get("phase") if pair else s.get("phase")})
        for c, s in (x, y)
    ]
    shots = {c: screens(page, s, subject) for _, c, s in columns}
    tabs = "".join(
        f'<lf-tab id="{sid}-{width}" label="{LABELS[width]}"><div class="pair-shots">'
        + "".join(
            column_figure(label, s["sample"], shots[c][width], width)
            for label, c, s in columns
        )
        + "</div></lf-tab>"
        for width in WIDTHS
    )
    heading = verdict_line(pair) if pair else "Not judged"
    if pair and pair.get("phase"):
        heading = f"Version {pair['phase']}: {heading}"
    notes = ""
    if pair:
        notes = (
            '<div class="pair-shots">'
            + "".join(
                f"<div><h4>{label}: defects the judge named</h4>{defects(pair, c)}</div>"
                for label, c, _ in columns
            )
            + f"</div>{reasons(pair)}"
        )
    return (
        f'<section id="{sid}"><h3>Pair {n}: {heading}</h3>'
        f'<lf-tabs id="{sid}-widths" data-width="available">{tabs}</lf-tabs>{notes}</section>'
    )


def outcome(subject: str, pairs: list[dict]) -> str:
    judged = [p for p in pairs if p["subject"] == subject]
    wins = [condition(p["winner"]) for p in judged if p["winner"]]
    if not judged:
        return "not judged"
    return ", ".join(
        [
            *(f"{c} {wins.count(c)}" for c in dict.fromkeys(wins)),
            f"no agreed winner {len(judged) - len(wins)}",
        ]
    )


def means(subject: str, members: list[dict]) -> dict:
    """Each measure's mean over the samples, unknown when any sample's is: a Codex
    turn reports no cost, which is not a cost of zero."""
    values = [measures(m, subject) for m in members]
    return {
        k: None
        if any(v[k] is None for v in values)
        else statistics.mean(v[k] for v in values)
        for k in values[0]
    }


def shown(value, form: str, unit: str = "") -> str:
    return "unavailable" if value is None else unit + format(value, form)


def overview(found: dict, pairs: list[dict]) -> str:
    """One row per task: the pairwise outcome and each condition's mean cost."""
    rows = []
    labels = sorted(
        {condition(column) for columns in found.values() for column in columns}
    )
    for subject, columns in sorted(found.items()):
        compared = {
            p.get("phase") for p in pairs if p["subject"] == subject and p.get("phase")
        }
        selected = next(iter(compared), None) if len(compared) <= 1 else None
        columns = {
            column: [{**sample, "phase": selected} for sample in members]
            for column, members in columns.items()
        }
        cost = {condition(c): means(subject, m)["cost"] for c, m in columns.items()}
        rows.append(
            f"<tr><td><a href='#task-{subject}'>{subject}</a></td>"
            f"<td>{outcome(subject, pairs)}</td>"
            + "".join(
                f"<td class='num'>{shown(cost.get(label), '.2f', '$')}</td>"
                for label in labels
            )
            + "</tr>"
        )
    return (
        '<table id="overview"><thead><tr><th>Task</th><th>Pairs won</th>'
        + "".join(f"<th>{escape(label)} cost</th>" for label in labels)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def task_section(page: Path, subject: str, columns: dict, pairs: list[dict]) -> str:
    judged = {p["pair"]: p for p in pairs if p["subject"] == subject}
    compared = {p.get("phase") for p in judged.values() if p.get("phase")}
    if len(compared) > 1:
        raise click.ClickException(
            f"{subject}: pair judgments compare different versions; make a report per version"
        )
    selected = next(iter(compared), None)
    columns = {
        column: [{**sample, "phase": selected} for sample in members]
        for column, members in columns.items()
    }
    rows = []
    decision = any(
        measures(sample, subject)["applied"] is not None
        for members in columns.values()
        for sample in members
    )
    for column, members in sorted(columns.items()):
        mean = means(subject, members)
        rows.append(
            f"<tr><td>{condition(column)}</td><td class='num'>{len(members)}</td>"
            f"<td class='num'>{shown(mean['minutes'], '.1f')}</td>"
            f"<td class='num'>{shown(mean['cost'], '.2f', '$')}</td>"
            f"<td class='num'>{shown(mean['turns'], '.0f')}</td>"
            f"<td class='num'>{shown(mean['css'], '.0f')}</td>"
            f"<td class='num'>{shown(mean['script'], '.0f')}</td>"
            + (
                f"<td class='num'>{shown(mean['applied'], '.0%')}</td>"
                if decision
                else ""
            )
            + "</tr>"
        )
    table = (
        f'<table id="{subject}-measures"><thead><tr><th>Condition</th><th>Samples</th>'
        "<th>Minutes</th><th>Cost</th><th>Turns</th><th>CSS lines</th>"
        "<th>Script lines</th>"
        + ("<th>Decision applied (model-assisted)</th>" if decision else "")
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    sample = next(iter(columns.values()))[0]
    recorded_inputs = sample_inputs(sample["metadata"], sample["run"], selected)
    request = recorded_inputs["request"]
    first, second = sorted(columns)
    if len(columns[first]) != len(columns[second]):
        raise click.ClickException(
            f"{subject}: report columns have unequal sample counts"
        )
    if any(n < 1 or n > len(columns[first]) for n in judged):
        raise click.ClickException(
            f"{subject}: verdict names a pair absent from this report"
        )
    for n, (a, b) in enumerate(zip(columns[first], columns[second]), 1):
        if n in judged and judged[n]["samples"] != {
            first: a["sample"],
            second: b["sample"],
        }:
            raise click.ClickException(
                f"{subject} pair {n}: verdict names different samples from this report"
            )
    sections = "".join(
        pair_section(page, subject, n, judged.get(n), (first, x), (second, y))
        for n, (x, y) in enumerate(zip(columns[first], columns[second]), 1)
    )
    return (
        f'<section id="task-{subject}"><h2>{subject.capitalize()}: pairs won, '
        f"{outcome(subject, pairs)}</h2>{table}"
        "<details><summary>The request and the user's later messages</summary>"
        f'<pre id="{subject}-request">{escape(request)}</pre>'
        + "".join(f"<p>{escape(line)}</p>" for line in recorded_inputs["messages"])
        + f"</details>{sections}</section>"
    )


@click.command("eval-report")
@click.argument("page", type=click.Path(file_okay=False, path_type=Path))
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--pairs",
    "pair_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="The explicit pairs.json from a new eval-pairs run.",
)
def eval_report(page: Path, runs: tuple[Path, ...], pair_file: Path | None):
    """Write PAGE, a Leaf page of the authored-task samples in RUNS.

    RUNS are run directories under `.tmp/eval/`; `eval-pairs` on the same runs
    supplies the pairing and verdicts. PAGE is created when absent, and its
    `index.html` is rewritten otherwise. Serve it with `leaf server start PAGE`."""
    if not (page / "events.jsonl").exists():
        leaf("page", "init", str(page))
    found = samples(list(runs))
    pairs = (
        json.loads(pair_file.read_text())
        if pair_file
        else next(
            (
                json.loads((run / "pairs.json").read_text())
                for run in runs
                if (run / "pairs.json").exists()
            ),
            [],
        )
    )
    found = {s: c for s, c in found.items() if len(c) == 2}
    if any(pair["subject"] not in found for pair in pairs):
        raise click.ClickException("Verdict names a task absent from this report")
    body = overview(found, pairs) + "".join(
        task_section(page, subject, columns, pairs)
        for subject, columns in sorted(found.items())
    )
    runs_text = ", ".join(f"<code>{run.name}</code>" for run in runs)
    (page / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<title>Authoring evaluation outputs</title>
<meta name="description" content="Matched authoring outputs side by side with recorded evidence, spend and model judgments.">
<style>{STYLE}</style>
</head>
<body>
<main class="layout-column">
<hgroup id="title"><p class="eyebrow">Runs {runs_text}</p>
<h1>Authoring evaluation outputs</h1></hgroup>
<p class="lede" id="lede">The recorded versions from both columns, side by side at every
width the judges saw, with each column's mean spend and the pairwise model's
judgment and named defects. Select a screen to zoom it to full size.</p>
<aside class="sidebar" id="contents-sidebar"><lf-toc id="contents" max-level="3"></lf-toc></aside>
{body}
</main>
</body>
</html>
"""
    )
    click.echo(page / "index.html")
