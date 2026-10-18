"""Write a Leaf page showing what an authored-task comparison produced.

`leaf-dev eval` keeps each `arrangement_eval` sample's screenshots, traces and
verdicts under `.tmp/eval/<run>/`, where the Promptfoo viewer shows them one sample
at a time. This command writes them to one page the user reads side by side: per
task, what each condition spent and wrote, and for each pair the final version's
screens at every width with the judges' verdicts and the defects they named. Pairs
and their verdicts come from `eval-pairs`; without its `pairs.json` the samples
are listed unpaired. Each sample supplies its frozen request, phases and review
sizes; the current catalog never changes a retained run. Exploratory observations are displayed
separately from pair outcomes. Each run rewrites the page's `index.html`, so a
later run's page replaces the earlier one under the same comments.
"""

import hashlib
import json
import statistics
import subprocess
from html import escape
from pathlib import Path

import click
from leaf.schema import MEDIA_TYPES
from PIL import Image

from leaf_dev import LEAF_COMMAND
from leaf_dev.arms import observed_sum
from leaf_dev.commands.eval_pairs import samples, saved_comparison

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
    return f"{'HTML' if '/html/' in column else 'Leaf'} · {column}"


def measures(sample: dict) -> dict:
    """What a sample's author spent over its phases. The live judge owns correctness."""
    recorded = sample["diagnostics"]["phases"]
    comparison = sample["diagnostics"]["comparison"]
    session = [
        recorded.get(str(p), {}).get("trace", {}) for p in comparison["author_phases"]
    ]
    initial = recorded.get("1", {}).get("trace", {})
    return {
        "initial_minutes": initial.get("minutes") if initial.get("completed") else None,
        "minutes": observed_sum(p.get("minutes") for p in session),
        "input_tokens": observed_sum(p.get("input_tokens") for p in session),
        "cost": observed_sum(p.get("cost_usd") for p in session),
        "turns": observed_sum(p.get("turns") for p in session),
    }


def screens(page: Path, sample: dict, version: str) -> dict[str, list[str]]:
    """One saved version's screens by width, as page media paths."""
    found = {
        name: sorted(
            sample["shots"].glob(f"p{version}-{name}-*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[1]),
        )
        for name in sample["diagnostics"]["comparison"]["widths"]
    }
    added = media_paths(page, [path for paths in found.values() for path in paths])
    return {name: [added[path] for path in paths] for name, paths in found.items()}


def media_paths(page: Path, files: list[Path]) -> dict[Path, str]:
    """Register captures through the page's media door and return their served paths."""
    added = {}
    for start in range(0, len(files), 50):
        for line in leaf(
            "page", "media", str(page), *map(str, files[start : start + 50])
        ).splitlines():
            record = json.loads(line)
            added[Path(record["source"])] = record["path"]
    return added


def discovery_evidence(page: Path, attempt: Path, paths: list[str], anchor: str) -> str:
    """Embed exact image paths; retain unavailable and supplemental evidence explicitly."""
    images = []
    supplements = []
    for value in paths:
        path = Path(value)
        if not path.is_absolute():
            path = attempt / path
        path = path.resolve()
        if not path.is_file():
            reason = "File is missing"
        elif not MEDIA_TYPES.get(path.suffix.lower(), "").startswith("image/"):
            reason = "Supplementary evidence; not an image"
        else:
            images.append(path)
            continue
        supplements.append(f"<li><code>{escape(str(path))}</code>: {reason}.</li>")
    added = media_paths(page, images)
    figures = "".join(
        f'<figure id="{anchor}-capture-{index}"><figcaption>{escape(path.name)}</figcaption>'
        + shot(page, added[path], f"Discovery evidence: {path.name}", lazy=True)
        + "</figure>"
        for index, path in enumerate(images, 1)
    )
    return (
        (
            f"<details><summary>Screenshot evidence ({len(images)})</summary>"
            f'<div class="pair-shots">{figures}</div></details>'
            if images
            else ""
        )
        + (f"<ul>{''.join(supplements)}</ul>" if supplements else "")
        + ("<p>No evidence paths recorded.</p>" if not paths else "")
    )


def shot(page: Path, path: str, alt: str, lazy: bool = False) -> str:
    with Image.open(page / path.lstrip("/")) as image:
        width, height = image.size
    loading = ' loading="lazy"' if lazy else ""
    return (
        f'<a href="{path}"><img src="{path}" alt="{escape(alt)}"'
        f' width="{width}" height="{height}"{loading}></a>'
    )


def column_figure(
    page: Path, anchor: str, label: str, sample: str, paths: list[str], width: str
) -> str:
    if not paths:
        return f'<figure id="{anchor}"><figcaption>{escape(label)}</figcaption><p>No screens.</p></figure>'
    alt = f"{label} page, {width}"
    rest = "".join(
        shot(page, p, f"{alt}, screen {i}", True) for i, p in enumerate(paths[1:], 2)
    )
    more = (
        f"<details><summary>{len(paths) - 1} more screens</summary>{rest}</details>"
        if rest
        else ""
    )
    return (
        f'<figure id="{anchor}"><figcaption>{escape(label)} <code>{escape(sample)}</code></figcaption>'
        f"{shot(page, paths[0], alt + ', first screen')}{more}</figure>"
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
    comparison = columns[0][2]["diagnostics"]["comparison"]
    versions = comparison["phases"]
    widths = {
        name: f"{width} × {height}"
        for name, (width, height) in comparison["widths"].items()
    }
    shots = {c: screens(page, s, versions[""]) for _, c, s in columns}
    tabs = "".join(
        f'<lf-tab id="{sid}-{width}" label="{widths[width]}"><div class="pair-shots">'
        + "".join(
            column_figure(
                page,
                f"{sid}-{width}-{index}",
                label,
                s["sample"],
                shots[c][width],
                widths[width],
            )
            for index, (label, c, s) in enumerate(columns, 1)
        )
        + "</div></lf-tab>"
        for width in widths
    )
    heading = verdict_line(pair) if pair else "Not judged"
    earlier = ""
    phase_description = (
        f"The tabs show the final saved revision (phase {versions['']}), "
        "before the judge's inspection actions."
    )
    if "_before_decision" in versions:
        phase_description += (
            " This revision follows the request to record the user's decisions as final. "
            f"The earlier screenshots below show phase {versions['_before_decision']}, before "
            "the decision; judges operate decision controls on live copies of that phase."
        )
        before = {
            c: screens(page, s, versions["_before_decision"]) for _, c, s in columns
        }
        before_width = next(iter(widths))
        earlier = (
            f"<details><summary>Before the decision: controls at {widths[before_width]}</summary>"
            '<div class="pair-shots">'
            + "".join(
                column_figure(
                    page,
                    f"{sid}-before-{index}",
                    label,
                    s["sample"],
                    before[c][before_width],
                    widths[before_width],
                )
                for index, (label, c, s) in enumerate(columns, 1)
            )
            + "</div></details>"
        )
    notes = ""
    if pair:
        notes = (
            '<div class="pair-shots">'
            + "".join(
                f"<div><h4>{escape(label)}: defects the judge named</h4>{defects(pair, c)}</div>"
                for label, c, _ in columns
            )
            + f"</div>{reasons(pair)}"
        )
    return (
        f'<section id="{sid}"><h3>Pair {n}: {escape(heading)}</h3>'
        f"<p>{phase_description} Inspection actions and states are retained "
        "in each judgment's traces.</p>"
        f'<lf-tabs id="{sid}-widths" data-width="available">{tabs}</lf-tabs>'
        f"{earlier}{notes}</section>"
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
    providers = sorted({column for pair in judged for column in pair["samples"]})
    return ", ".join(
        [f"{condition(column)} {wins.count(condition(column))}" for column in providers]
        + [f"{status.replace('_', ' ')} {count}" for status, count in counts.items()]
    )


def means(members: list[dict]) -> dict:
    """Each measure's mean over the samples, unknown when any sample's is: a Codex
    turn reports no cost, which is not a cost of zero."""
    values = [measures(m) for m in members]
    return {
        k: None
        if any(v[k] is None for v in values)
        else statistics.mean(v[k] for v in values)
        for k in values[0]
    }


def shown(value, form: str, unit: str = "") -> str:
    return "unavailable" if value is None else unit + format(value, form)


def overview(found: dict, pairs: list[dict]) -> str:
    """One row per task's pairwise outcome; accounting follows with its samples."""
    rows = []
    for subject in sorted(found):
        rows.append(
            f"<tr><td><a href='#task-{subject}'>{subject}</a></td>"
            f"<td>{escape(outcome(subject, pairs))}</td></tr>"
        )
    return (
        '<table id="overview"><thead><tr><th scope="col">Task</th>'
        '<th scope="col">Pair outcomes</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def task_section(page: Path, subject: str, columns: dict, pairs: list[dict]) -> str:
    try:
        comparison = saved_comparison(
            [s for members in columns.values() for s in members]
        )
    except ValueError as error:
        return (
            f'<section id="task-{subject}"><h2>{escape(subject.capitalize())}</h2>'
            f"<p>Unscored: {escape(str(error))}</p></section>"
        )
    judged = {p["pair"]: p for p in pairs if p["subject"] == subject}
    measured = [
        (condition(column), {**means(members), "samples": len(members)})
        for column, members in sorted(columns.items())
    ]
    metrics = [
        ("samples", "Samples", ".0f", ""),
        ("initial_minutes", "Initial author completion (min)", ".1f", ""),
        ("minutes", "All author phases (min)", ".1f", ""),
        ("input_tokens", "Input tokens, including cached", ",.0f", ""),
        ("cost", "Reported author cost", ".2f", "$"),
        ("turns", "Author turns", ".0f", ""),
    ]
    rows = [
        f'<tr><th scope="row">{label}</th>'
        + "".join(
            f'<td class="num">{shown(mean[key], form, unit)}</td>'
            for _, mean in measured
        )
        + "</tr>"
        for key, label, form, unit in metrics
    ]
    table = (
        f'<table id="{subject}-measures"><thead><tr><th scope="col">Measure</th>'
        + "".join(
            f'<th scope="col"><code>{escape(label)}</code></th>'
            for label, _ in measured
        )
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        + "<p>Means across samples. Initial completion ends when the author answers; "
        "it does not measure first usability. An unfinished initial turn is unavailable. "
        "Token totals include cached input; "
        "unreported cost is unavailable, not zero.</p>"
    )
    first, second = sorted(columns)
    sections = "".join(
        pair_section(page, subject, n, judged.get(n), (first, x), (second, y))
        for n, (x, y) in enumerate(zip(columns[first], columns[second]), 1)
    )
    return (
        f'<section id="task-{subject}"><h2>{subject.capitalize()}: pair outcomes, '
        f"{escape(outcome(subject, pairs))}</h2>{table}"
        "<details><summary>The request and the user's later messages</summary>"
        f'<pre id="{subject}-request">{escape(comparison["brief"])}</pre>'
        f"</details>{sections}</section>"
    )


def discovery_section(page: Path, runs: tuple[Path, ...]) -> str:
    """Show exploratory observations separately from pair outcomes and score totals."""
    responses = [
        path
        for run in runs
        for path in sorted((run / "discovery").glob("*/attempt-*/response.json"))
    ]
    if not responses:
        return ""
    attempts = []
    for path in responses:
        anchor = "discovery-" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
        response = json.loads(path.read_text())
        output = response.get("output")
        sample = response["sample"]
        observations = []
        if output:
            status = output["status"].replace("_", " ")
            for index, observation in enumerate(output["observations"], 1):
                width, height = observation["viewport"]
                steps = "".join(
                    f"<li>{escape(step)}</li>" for step in observation["steps"]
                )
                evidence = discovery_evidence(
                    page,
                    path.parent,
                    observation["evidence"],
                    f"{anchor}-observation-{index}",
                )
                observations.append(
                    f"<h4>{escape(observation['kind'].capitalize())}: {escape(observation['summary'])}</h4>"
                    f"<p>{escape(observation['impact'])}</p>"
                    f"<p>Viewport: {width} × {height}</p><ol>{steps}</ol>"
                    f"{evidence}"
                    f"<p>Next: {escape(observation['next'])}</p>"
                )
            explored = f"<p>{escape(output['explored'])}</p>"
            unverified = "".join(
                f"<li>{escape(item)}</li>" for item in output["unverified"]
            )
            remaining = f"<p>Unverified:</p><ul>{unverified}</ul>" if unverified else ""
        else:
            status = "unscored"
            explored = ""
            remaining = f"<p>{escape(response.get('error') or 'No observation output returned.')}</p>"
        attempts.append(
            f'<section id="{anchor}"><h3>{escape(sample)} · {escape(path.parent.name)}: {status}</h3>'
            + explored
            + ("".join(observations) or "<p>No observations recorded.</p>")
            + remaining
            + f"<p>Response (native traces are beside it): <code>{escape(str(path))}</code></p></section>"
        )
    return (
        '<section id="discovery"><h2>Exploratory observations</h2>'
        "<p>An agent chose these variations to find useful observations. These attempts "
        "are outside the fixed comparison; their counts are not benchmark rates.</p>"
        + "".join(attempts)
        + "</section>"
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
    body = (
        overview(found, pairs)
        + "".join(
            task_section(page, subject, columns, pairs)
            for subject, columns in sorted(found.items())
        )
        + discovery_section(page, runs)
    )
    runs_text = ", ".join(f"<code>{run.name}</code>" for run in runs)
    (page / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<title>Authoring comparisons</title>
<meta name="description" content="Saved authored pages side by side, with their original review conditions, costs and judgments.">
<style>{STYLE}</style>
</head>
<body>
<main class="layout-column">
<hgroup id="title"><p class="eyebrow">Runs {runs_text}</p>
<h1>Authoring comparisons</h1></hgroup>
<p class="lede" id="lede">Each task's saved pages appear side by side at the sizes recorded for that run,
with each condition's mean spend and the pairwise judge's verdict and named defects.
Saved requests and screen sizes retain their original scope; a run authored for a
narrow window does not become a fullscreen benchmark when viewed here. Select a screen to zoom it to full size.</p>
<aside class="sidebar" id="contents-sidebar"><lf-toc id="contents" max-level="3"></lf-toc></aside>
{body}
</main>
</body>
</html>
"""
    )
    click.echo(page / "index.html")
