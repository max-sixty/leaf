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
from leaf_dev.arrangement_eval import CASES, TASKS, WIDTHS, later_messages, phases
from leaf_dev.commands.eval_pairs import samples

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
    return "HTML" if "/html/" in column else "Leaf"


def measures(sample: dict, subject: str) -> dict:
    """What a sample's author spent over its phases, the final version's code, and
    whether its decision was applied as chosen."""
    recorded = sample["diagnostics"]["phases"]
    session = [recorded[str(p)]["trace"] for p in phases(subject) if str(p) in recorded]
    final = recorded.get(str(phases(subject)[-1]), {})
    return {
        "minutes": observed_sum(p["minutes"] for p in session),
        "cost": observed_sum(p["cost_usd"] for p in session),
        "turns": sum(p["turns"] for p in session),
        "css": final.get("css_lines"),
        "script": final.get("script_lines"),
        "applied": sample["checks"].get("decision-applied") is True,
    }


def screens(page: Path, sample: dict, subject: str) -> dict[str, list[str]]:
    """The final version's screens by width, as page media paths."""
    version = phases(subject)[-1]
    found = {
        name: sorted(
            sample["shots"].glob(f"p{version}-{name}-*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[1]),
        )
        for name in WIDTHS
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
    if pair["status"] == "insufficient_evidence":
        return "Insufficient evidence for comparison"
    if pair["status"] == "unscored":
        return "Comparison unscored"
    if pair["status"] == "tie":
        return "Both orders judged the pages equal"
    orders = [o["overall"] for o in pair["orders"]]
    named = [condition(o) if "/" in o else o for o in orders]
    if pair["winner"]:
        return f"{condition(pair['winner'])} preferred in both orders"
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
    columns = [(condition(c), c, s) for c, s in (x, y)]
    columns.sort(key=lambda item: item[0] != "Leaf")
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
        "<p>These screens show authored arrival. The judges explore separate live "
        "copies; their actions and inspected states are retained in each judgment's traces.</p>"
        f'<lf-tabs id="{sid}-widths" data-width="available">{tabs}</lf-tabs>{notes}</section>'
    )


def outcome(subject: str, pairs: list[dict]) -> str:
    judged = [p for p in pairs if p["subject"] == subject]
    wins = [condition(p["winner"]) for p in judged if p["winner"]]
    if not judged:
        return "not judged"
    counts = {
        status: sum(pair["status"] == status for pair in judged)
        for status in ("split", "tie", "insufficient_evidence", "unscored")
    }
    return (
        ", ".join(f"{c} {wins.count(c)}" for c in ("Leaf", "HTML"))
        + ", "
        + ", ".join(
            f"{status.replace('_', ' ')} {count}" for status, count in counts.items()
        )
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
    for subject, columns in sorted(found.items()):
        cost = {condition(c): means(subject, m)["cost"] for c, m in columns.items()}
        rows.append(
            f"<tr><td><a href='#task-{subject}'>{subject}</a></td>"
            f"<td>{outcome(subject, pairs)}</td>"
            f"<td class='num'>{shown(cost.get('Leaf'), '.2f', '$')}</td>"
            f"<td class='num'>{shown(cost.get('HTML'), '.2f', '$')}</td></tr>"
        )
    return (
        '<table id="overview"><thead><tr><th>Task</th><th>Pairs won</th>'
        "<th>Leaf cost</th><th>HTML cost</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def task_section(page: Path, subject: str, columns: dict, pairs: list[dict]) -> str:
    judged = {p["pair"]: p for p in pairs if p["subject"] == subject}
    rows = []
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
                f"<td class='num'>{mean['applied']:.0%}</td>"
                if CASES[subject].decision
                else ""
            )
            + "</tr>"
        )
    table = (
        f'<table id="{subject}-measures"><thead><tr><th>Condition</th><th>Samples</th>'
        "<th>Minutes</th><th>Cost</th><th>Turns</th><th>CSS lines</th>"
        "<th>Script lines</th>"
        + ("<th>Decision applied</th>" if CASES[subject].decision else "")
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    request = (TASKS / subject / "request.md").read_text()
    first, second = sorted(columns)
    sections = "".join(
        pair_section(page, subject, n, judged.get(n), (first, x), (second, y))
        for n, (x, y) in enumerate(zip(columns[first], columns[second]), 1)
    )
    return (
        f'<section id="task-{subject}"><h2>{subject.capitalize()}: pairs won, '
        f"{outcome(subject, pairs)}</h2>{table}"
        "<details><summary>The request and the user's later messages</summary>"
        f'<pre id="{subject}-request">{escape(request)}</pre>'
        + "".join(f"<p>{escape(line)}</p>" for line in later_messages(subject) if line)
        + f"</details>{sections}</section>"
    )


@click.command()
@click.argument("page", type=click.Path(file_okay=False, path_type=Path))
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
def eval_report(page: Path, runs: tuple[Path, ...]):
    """Write PAGE, a Leaf page of the authored-task samples in RUNS.

    RUNS are run directories under `.tmp/eval/`; `eval-pairs` on the same runs
    supplies the pairing and verdicts. PAGE is created when absent, and its
    `index.html` is rewritten otherwise. Serve it with `leaf server start PAGE`."""
    if not (page / "events.jsonl").exists():
        leaf("page", "init", str(page))
    found = samples(list(runs))
    pairs = next(
        (
            json.loads((run / "pairs.json").read_text())
            for run in runs
            if (run / "pairs.json").exists()
        ),
        [],
    )
    found = {s: c for s, c in found.items() if len(c) == 2}
    body = overview(found, pairs) + "".join(
        task_section(page, subject, columns, pairs)
        for subject, columns in sorted(found.items())
    )
    runs_text = ", ".join(f"<code>{run.name}</code>" for run in runs)
    (page / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<title>Leaf against plain HTML: eval outputs</title>
<meta name="description" content="Each authored task's final pages from Leaf and plain HTML side by side, with what each cost and what the judges said.">
<style>{STYLE}</style>
</head>
<body>
<main class="layout-column">
<hgroup id="title"><p class="eyebrow">Runs {runs_text}</p>
<h1>Leaf against plain HTML: eval outputs</h1></hgroup>
<p class="lede" id="lede">Each task's final pages from both conditions, side by side at every
width the judges saw, with each condition's mean spend and the pairwise judge's
verdict and named defects. Select a screen to zoom it to full size.</p>
<aside class="sidebar" id="contents-sidebar"><lf-toc id="contents" max-level="3"></lf-toc></aside>
{body}
</main>
</body>
</html>
"""
    )
    click.echo(page / "index.html")
