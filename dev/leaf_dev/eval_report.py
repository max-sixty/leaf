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
from leaf_dev.arms import read_trace, resumed, trace_summary
from leaf_dev.arrangement_eval import CASES, TASKS, WIDTHS, phases
from leaf_dev.eval_pairs import samples

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
    """What a sample spent over its phases, and the final version's code."""
    names = [str(p) for p in phases(subject)]
    session = resumed(
        [trace_summary(read_trace(sample["work"] / f"stream-{n}.jsonl")) for n in names]
    )
    final = sample["diagnostics"]["phases"][names[-1]]
    return {
        "minutes": sum(p["minutes"] or 0 for p in session),
        "cost": sum(p["cost_usd"] or 0 for p in session),
        "turns": sum(p["turns"] for p in session),
        "css": final.get("css_lines"),
        "script": final.get("script_lines"),
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
    orders = [o["overall"] if o else "no verdict" for o in pair["orders"]]
    named = [condition(o) if "/" in o else o for o in orders]
    if pair["winner"]:
        return f"{condition(pair['winner'])} preferred in both orders"
    return f"Split: {named[0]} in one order, {named[1]} in the other"


def defects(pair: dict, column: str) -> str:
    items = [
        f"<li>{escape(d)}</li>"
        for o in pair["orders"]
        if o
        for d in (o["defects"].get(column) or [])
    ]
    return f"<ul>{''.join(items)}</ul>" if items else "<p>None named.</p>"


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
        f'<lf-tabs id="{sid}-widths" data-width="available">{tabs}</lf-tabs>{notes}</section>'
    )


def task_section(page: Path, subject: str, columns: dict, pairs: list[dict]) -> str:
    judged = {p["pair"]: p for p in pairs if p["subject"] == subject}
    wins = [condition(p["winner"]) for p in judged.values() if p["winner"]]
    outcome = (
        ", ".join(f"{c} {wins.count(c)}" for c in ("Leaf", "HTML"))
        + f", split {len(judged) - len(wins)}"
        if judged
        else "not judged"
    )
    rows = []
    for column, members in sorted(columns.items()):
        values = [measures(m, subject) for m in members]
        mean = {k: statistics.mean(v[k] or 0 for v in values) for k in values[0]}
        rows.append(
            f"<tr><td>{condition(column)}</td><td class='num'>{len(values)}</td>"
            f"<td class='num'>{mean['minutes']:.1f}</td>"
            f"<td class='num'>${mean['cost']:.2f}</td>"
            f"<td class='num'>{mean['turns']:.0f}</td>"
            f"<td class='num'>{mean['css']:.0f}</td>"
            f"<td class='num'>{mean['script']:.0f}</td></tr>"
        )
    table = (
        f'<table id="{subject}-measures"><thead><tr><th>Condition</th><th>Samples</th>'
        "<th>Minutes</th><th>Cost</th><th>Turns</th><th>CSS lines</th>"
        "<th>Script lines</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    request = (TASKS / subject / "request.md").read_text()
    comment = CASES[subject].comment
    first, second = sorted(columns)
    sections = "".join(
        pair_section(page, subject, n, judged.get(n), (first, x), (second, y))
        for n, (x, y) in enumerate(zip(columns[first], columns[second]), 1)
    )
    return (
        f'<section id="task-{subject}"><h2>{subject.capitalize()}: pairs won, '
        f"{outcome}</h2>{table}"
        f"<details><summary>The request, the width preference and the comment</summary>"
        f'<pre id="{subject}-request">{escape(request)}</pre>'
        + (
            f"<p>Comment: on {escape(comment.target)}: {escape(comment.text)}</p>"
            if comment
            else ""
        )
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
    body = "".join(
        task_section(page, subject, columns, pairs)
        for subject, columns in sorted(found.items())
        if len(columns) == 2
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
verdict and named defects.</p>
<aside class="sidebar" id="contents-sidebar"><lf-toc id="contents" max-level="3"></lf-toc></aside>
{body}
</main>
</body>
</html>
"""
    )
    click.echo(page / "index.html")
