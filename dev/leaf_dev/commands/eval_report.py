"""Render Promptfoo runs as one Leaf browser of scores, judgments and outputs.

Every sample remains visible, including single arms, unequal repetitions and failed
attempts. Execution checks, authoring grades, pairwise preferences and exploratory
observations retain their distinct meanings. An optional authored review names the
latest run group and experiment decisions; scores never infer either. Requests,
viewports and phases come from retained results, never today's catalog.

Saved Leaf phases export through the standard exporter on disposable copies, retaining
the page's layer and state. Plain HTML keeps its authored files. PAGE/evidence is
served separately with an ordinary static server; --output-url makes those pages,
source and traces reachable from the report without broadening Leaf's file access.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import quote

import click
from PIL import Image

from leaf.schema import MEDIA_TYPES
from leaf_dev import LEAF_COMMAND
from leaf_dev.arms import observed_sum
from leaf_dev.commands.eval_pairs import saved_comparison

# Run against the retained payload's Python APIs as well as its browser layer.
# Exporting an old capture with today's composer can silently change its runtime.
EXPORT_PHASE = """
from pathlib import Path
import sys
from leaf.event_log import read_events
from leaf.exporting import cmd_export
from leaf.files import stamped_version
from leaf.publishing import cmd_stamp
from leaf.revisioning import planned_activation
from leaf.validation.source import check_source
page, target = map(Path, sys.argv[1:])
events = read_events(page)
checked = check_source(page, events)
if checked.errors:
    raise ValueError("; ".join(map(str, checked.errors)))
version = stamped_version(events, planned_activation(page, checked).revision)
if version is None:
    version = cmd_stamp(page, "Capture saved evaluation phase for inspection.")["version"]
cmd_export(page, target, version)
"""


STYLE = """
.pair-shots { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr)); gap: 1rem; }
.pair-shots > * { min-width: 0; overflow-wrap: anywhere; }
/* Shared caption and image rows keep the captures aligned when actions wrap. */
.pair-shots > figure { display: grid; grid-template-rows: subgrid; grid-row: span 4; row-gap: 0; margin: 0; }
.pair-shots > figure > a { display: block; align-self: start; grid-row: 3; }
.pair-shots > figure > details { grid-row: 4; margin-block: .5rem 0; }
.capture-actions-row { grid-row: 2; margin-block: 0 .5rem; }
.comparison-output-links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; margin-block: .5rem 1rem; }
.comparison-output-links > div { min-width: 0; }
.comparison-output-links strong { display: block; margin-block-end: .25rem; }
.pair-shots img { display: block; box-sizing: border-box; max-width: 100%; height: auto; border: 1px solid var(--rule, #ccc); }
.pair-shots > figure > figcaption { display: flex; align-items: baseline; align-content: start; flex-wrap: wrap; gap: .35rem 1rem; margin-block: 0 .5rem; font-weight: 600; }
.capture-actions { display: inline-flex; flex-wrap: wrap; gap: .35rem .8rem; font-weight: 400; }
.report-flat-tabs > lf-tabs { border: 0; border-radius: 0; background: transparent; margin-block: .75rem; }
.report-flat-tabs > lf-tabs > lf-tab:not([hidden]) { padding: .75rem 0 0; }
.report-flat-tabs > lf-tabs > .lf-tabstrip { padding-inline: 0; border-radius: 0; background: transparent; }
.comparison-summary { margin-block: .25rem .75rem; font-family: var(--sans); font-size: .875rem; }
.pair-shots details img { margin-top: .5rem; }
.sample-links { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; }
.sample-table td { vertical-align: top; }
.sample-table small { display: block; max-inline-size: 20rem; overflow-wrap: anywhere; }
#report-views lf-tabs { margin-block: .75rem; }
@media (max-width: 640px) {
  .sample-table, .sample-table tbody { display: block; }
  .sample-table thead { display: none; }
  .sample-table tr { display: grid; grid-template-columns: 1fr 1fr; padding-block: .75rem; border-bottom: 1px solid var(--border-2); }
  .sample-table td { display: block; border: 0; min-width: 0; }
  .sample-table td::before { content: attr(data-label); display: block; font-size: .75rem; color: var(--muted); }
}
.experiment-heading h2 { margin-block: 0 .35rem; }
.experiment-recommendation { margin-block: 0; font-size: .875rem; }
.experiment-recommendation > span { color: var(--muted); }
.experiment-change { margin-block: .75rem; max-width: 72ch; }
#experiments, #report-views { border-radius: 0; }
@media (min-width: 640px) {
  #experiments, #report-views { grid-template-columns: minmax(0, 14rem) minmax(0, 1fr); }
}
#review-views > lf-tab:not([hidden]) { padding-block-start: 0; }
.report-assessment { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr)); gap: 1rem; margin-block: 1rem; }
.report-assessment > details { margin: 0; }
.result-list { margin-block: .5rem; }
.result-list > div { display: flex; justify-content: space-between; gap: 1rem; padding-block: .35rem; border-bottom: 1px solid var(--border-2); }
.result-list dt { font-weight: 500; }
.result-list dd { margin: 0; text-align: right; }
.report-metadata { overflow-wrap: anywhere; }
.report-metadata dl { display: grid; grid-template-columns: auto 1fr; gap: .35rem 1.5rem; }
.report-metadata dd { margin: 0; }
.output-status { color: var(--muted); font-size: .875rem; }
.report-meta { color: var(--muted); font-size: .875rem; }
"""


def leaf(*args: str) -> str:
    return subprocess.run(
        [*LEAF_COMMAND, *args], check=True, capture_output=True, text=True
    ).stdout


def condition_labels(columns: dict) -> dict[str, str]:
    """Keep a named arm intact; name the condition when it distinguishes arms."""
    names = {
        column: {"leaf": "Leaf", "html": "Plain HTML"}.get(
            members[0]["diagnostics"].get("condition"), column
        )
        for column, members in columns.items()
    }
    return {
        column: name if list(names.values()).count(name) == 1 else column
        for column, name in names.items()
    }


def report_samples(runs: tuple[Path, ...]) -> dict:
    """Read every Promptfoo result, including failed attempts with no saved page."""
    found = defaultdict(lambda: defaultdict(list))
    for run in runs:
        results = json.loads((run / "results.json").read_text())["results"]["results"]
        for index, result in enumerate(results):
            response = result.get("response") or {}
            metadata = response.get("metadata") or {}
            diagnostics = metadata.get("diagnostics") or {}
            subject = (
                diagnostics.get("subject")
                or result.get("testCase", {}).get("metadata", {}).get("case")
                or result.get("testCase", {}).get("description")
                or "Unfinished attempts"
            )
            work = (
                Path(metadata["work"])
                if metadata.get("work")
                else run / f"unsaved-{index}"
            )
            found[subject][result["provider"]["label"]].append(
                {
                    "sample": work.name,
                    "title": result.get("testCase", {}).get("description") or subject,
                    "work": work,
                    "diagnostics": diagnostics,
                    "checks": metadata.get("checks") or {},
                    "shots": run / "screenshots" / work.name,
                    "run": run,
                    "gradingResult": result.get("gradingResult"),
                    "error": result.get("error")
                    or response.get("error")
                    or (result.get("gradingResult") or {}).get("reason"),
                }
            )
    for columns in found.values():
        for members in columns.values():
            for number, sample in enumerate(members, 1):
                sample["attempt"] = number
    return found


def task_anchor(subject: str) -> str:
    return "task-" + hashlib.sha256(subject.encode()).hexdigest()[:12]


def task_title(columns: dict) -> str:
    """Use the saved case's human-facing description; ids still own grouping."""
    title = next(iter(columns.values()))[0]["title"]
    return title[:1].upper() + title[1:]


def measures(sample: dict) -> dict:
    """What a sample's author spent over its phases. The live judge owns correctness."""
    recorded = sample["diagnostics"].get("phases", {})
    comparison = sample["diagnostics"].get("comparison", {})
    session = [
        recorded.get(str(p), {}).get("trace", {})
        for p in comparison.get("author_phases", [])
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
    recorded = sample["diagnostics"]["phases"].get(str(version), {}).get("captures", {})
    found = {
        name: [
            path
            for path in (
                [Path(path) for path in recorded[name]]
                if name in recorded
                else sorted(
                    sample["shots"].glob(f"p{version}-{name}-*.png"),
                    key=lambda path: int(path.stem.rsplit("-", 1)[1]),
                )
            )
            if path.is_file()
        ]
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
    # With responsive height:auto, the explicit ratio reserves lazy-image space.
    return (
        f'<a href="{path}"><img src="{path}" alt="{escape(alt)}"'
        f' width="{width}" height="{height}" style="aspect-ratio: {width} / {height}"{loading}></a>'
    )


def column_figure(
    page: Path,
    anchor: str,
    label: str,
    sample: str,
    paths: list[str],
    width: str,
    actions: str = "",
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
        f'<figure id="{anchor}"><figcaption>{escape(label)}</figcaption>'
        + (f'<div class="capture-actions-row">{actions}</div>' if actions else "")
        + f"{shot(page, paths[0], alt + ', first screen')}{more}</figure>"
    )


def verdict_line(pair: dict, labels: dict[str, str]) -> str:
    if pair["status"] == "insufficient_evidence":
        return "Insufficient evidence for comparison"
    if pair["status"] == "unscored":
        return "Comparison unscored"
    if pair["status"] == "tie":
        return "Both orders judged the pages equal"
    orders = [o["overall"] for o in pair["orders"]]
    named = [labels.get(order, order) for order in orders]
    if pair["winner"]:
        return f"{labels.get(pair['winner'], pair['winner'])} preferred in both orders"
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


def comparison_screens(
    page: Path,
    anchor: str,
    columns: list[tuple[str, dict]],
    actions: list[str] | None = None,
    *,
    before_after: bool = False,
) -> str:
    """Compare final outputs only at equal recorded viewport dimensions."""
    captures = []
    for label, sample in columns:
        comparison = sample["diagnostics"].get("comparison")
        if not comparison:
            return "<p>No saved comparison captures are available.</p>"
        paths = screens(page, sample, str(comparison["phases"][""]))
        captures.append(
            (
                label,
                sample,
                {
                    tuple(size): paths[name]
                    for name, size in comparison["widths"].items()
                },
            )
        )
    common = [
        (name, tuple(size))
        for name, size in columns[0][1]["diagnostics"]["comparison"]["widths"].items()
        if all(tuple(size) in capture[2] for capture in captures)
    ]
    if not common:
        return "<p>No matching captured viewports. Open each output to inspect it.</p>"
    tabs = []
    for name, (width, height) in common:
        images = [paths[width, height] for _, _, paths in captures]
        if before_after and all(images):
            contents = (
                f'<lf-shot id="{anchor}-{name}-shot" before="{images[0][0]}" after="{images[1][0]}" '
                f'alt="Before and after at {width} × {height}"></lf-shot>'
            )
            if actions:
                contents += (
                    '<div class="comparison-output-links">'
                    + "".join(
                        f"<div><strong>{escape(label)}</strong>{action}</div>"
                        for (label, _, _), action in zip(captures, actions, strict=True)
                    )
                    + "</div>"
                )
            if any(len(paths) > 1 for paths in images):
                contents += (
                    '<details><summary>Later screens</summary><div class="pair-shots">'
                    + "".join(
                        column_figure(
                            page,
                            f"{anchor}-{name}-later-{index}",
                            label,
                            sample["sample"],
                            paths[width, height][1:],
                            f"{width} × {height}",
                        )
                        for index, (label, sample, paths) in enumerate(captures, 1)
                    )
                    + "</div></details>"
                )
        else:
            contents = (
                '<div class="pair-shots">'
                + "".join(
                    column_figure(
                        page,
                        f"{anchor}-{name}-{index}",
                        label,
                        sample["sample"],
                        paths[width, height],
                        f"{width} × {height}",
                        actions[index - 1] if actions else "",
                    )
                    for index, (label, sample, paths) in enumerate(captures, 1)
                )
                + "</div>"
            )
        tabs.append(
            f'<lf-tab id="{anchor}-{name}" label="{escape(name.capitalize())}">{contents}</lf-tab>'
        )
    tabs = "".join(tabs)
    return f'<div class="report-flat-tabs"><lf-tabs id="{anchor}-widths" data-width="available">{tabs}</lf-tabs></div>'


def pair_section(
    page: Path, subject: str, n: int, pair: dict | None, x, y, labels: dict[str, str]
) -> str:
    sid = f"{subject}-pair-{n}"
    columns = [(labels[c], c, s) for c, s in (x, y)]
    comparison = columns[0][2]["diagnostics"]["comparison"]
    versions = comparison["phases"]
    widths = {
        name: f"{width} × {height}"
        for name, (width, height) in comparison["widths"].items()
    }
    heading = verdict_line(pair, labels) if pair else "Compare the outputs"
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
        f"{comparison_screens(page, sid, [(label, sample) for label, _, sample in columns])}"
        f"{earlier}{notes}"
        f"<details><summary>Saved phases and run provenance</summary><p>{phase_description} "
        "Inspection actions and states, when judged, are retained in the judgment traces.</p>"
        "<p>A repeated comparison swaps the pages' left/right positions to check whether the judge's preference changes with presentation order. "
        + (
            "This pair was judged in both orders."
            if pair
            else "This pair has no repeated comparison judgment; any experiment assessment is under Changes tested."
        )
        + "</p><p>Runs: "
        + escape(" / ".join(dict.fromkeys(s["run"].name for _, _, s in columns)))
        + "</p></details></section>"
    )


def outcome(subject: str, pairs: list[dict], labels: dict[str, str]) -> str:
    judged = [p for p in pairs if p["subject"] == subject]
    wins = [p["winner"] for p in judged if p["winner"]]
    if not judged:
        return "not judged"
    counts = {
        status: sum(pair["status"] == status for pair in judged)
        for status in ("split", "tie", "insufficient_evidence", "unscored")
    }
    providers = sorted({column for pair in judged for column in pair["samples"]})
    return ", ".join(
        [f"{labels.get(column, column)} {wins.count(column)}" for column in providers]
        + [f"{status.replace('_', ' ')} {count}" for status, count in counts.items()]
    )


def shown(value, form: str, unit: str = "") -> str:
    return "unavailable" if value is None else unit + format(value, form)


def sample_anchor(sample: dict) -> str:
    return (
        "sample-"
        + hashlib.sha256(
            f"{sample.get('run', '')}:{sample['work']}".encode()
        ).hexdigest()[:12]
    )


def linked_file(page: Path, path: Path, output_url: str | None, label: str) -> str:
    """Copy exact evidence into the explicitly served report bundle."""
    if not path.is_file():
        return f"{escape(label)} unavailable"
    name = (
        hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12] + "-" + path.name
    )
    if path.suffix == ".html":
        name += ".txt"
    target = page / "evidence" / "raw" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    if output_url:
        return f'<a href="{escape(output_url.rstrip("/") + "/raw/" + quote(name))}" target="_blank" rel="noopener">{escape(label)}</a>'
    return f"{escape(label)} not served: <code>{escape(str(target))}</code>"


def exported_output(
    page: Path, sample: dict, phase: str, output_url: str | None
) -> str:
    """Export the exact saved phase using its layer, without changing the evidence.

    Stamp a disposable copy so an unstamped draft exports instead of the preceding
    stamped version. This uses Leaf's export; it adds no host transport capability.
    """
    source = Path(sample["diagnostics"]["phases"][phase]["page"])
    slot = f"{sample_anchor(sample)}-p{phase}"
    target = page / "evidence" / slot / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not source.is_dir():
        return "Saved output is missing."
    try:
        if sample["diagnostics"]["condition"] == "html":
            shutil.copytree(source, target.parent, dirs_exist_ok=True)
        else:
            with tempfile.TemporaryDirectory(prefix="leaf-eval-export-") as temporary:
                copied = Path(temporary) / "page"
                shutil.copytree(source, copied)
                subprocess.run(
                    [
                        "uv",
                        "run",
                        "--no-dev",
                        "--project",
                        sample["diagnostics"]["payload"],
                        "python",
                        "-c",
                        EXPORT_PHASE,
                        str(copied),
                        str(target.resolve()),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
    except subprocess.CalledProcessError as error:
        return f"Output export unavailable: {escape(error.stderr.strip())}"
    except OSError as error:
        return f"Output export unavailable: {escape(str(error))}"
    if output_url:
        href = output_url.rstrip("/") + "/" + slot + "/index.html"
        return f'<a href="{escape(href)}" target="_blank" rel="noopener">Open interactive output</a>'
    return f"Output not served: <code>{escape(str(target))}</code>"


def check_results(sample: dict) -> list[tuple[str, str]]:
    labels = {
        "completed": "Author finished",
        "page": "Output saved",
        "page-valid": "Page validation",
    }
    return [
        (
            labels.get(name, name.replace("-", " ").capitalize()),
            "Passed" if value else "Failed",
        )
        for name, value in sample["checks"].items()
    ]


def result_list(results: list[tuple[str, str]]) -> str:
    return (
        '<dl class="result-list">'
        + "".join(
            f"<div><dt>{escape(name)}</dt><dd>{escape(value)}</dd></div>"
            for name, value in results
        )
        + "</dl>"
    )


def check_summary(sample: dict) -> str:
    results = check_results(sample)
    if not results:
        return "Not checked"
    failed = [name for name, value in results if value == "Failed"]
    return (
        f"{len(failed)} of {len(results)} checks failed"
        if failed
        else f"{len(results)} checks passed"
    )


def quality_results(sample: dict) -> list[dict]:
    """Keep model judgments separate from execution assertions."""
    return [
        result
        for result in (sample.get("gradingResult") or {}).get("componentResults", [])
        if result.get("metadata", {}).get("authoring_grade")
        or "page_defects" in result.get("metadata", {})
        or result.get("assertion", {}).get("type") in {"llm-rubric", "agent-rubric"}
    ]


def quality_name(result: dict) -> str:
    metadata = result.get("metadata", {})
    if metadata.get("authoring_grade"):
        return "Live task review"
    if "page_defects" in metadata:
        return "Visual review"
    return (
        (result.get("assertion", {}).get("metric") or "Criterion")
        .replace("-", " ")
        .capitalize()
    )


def quality_status(result: dict) -> str:
    metadata = result.get("metadata", {})
    if metadata.get("authoring_grade"):
        status = metadata["authoring_grade"]["status"]
        return {"pass": "Passed", "defect": "Defect found"}.get(
            status, status.replace("_", " ").capitalize()
        )
    if "page_defects" in metadata:
        return f"{len(metadata['page_defects']['defects'])} defects found"
    return "Passed" if result.get("pass") else "Failed"


def grade_summary(sample: dict) -> str:
    results = quality_results(sample)
    if not results:
        return (
            "Comparison only"
            if sample.get("comparisons")
            else "No individual assessment"
        )
    if len(results) == 1:
        return quality_name(results[0]) + ": " + quality_status(results[0]).lower()
    passed = sum(result.get("pass", False) for result in results)
    return f"{passed} of {len(results)} criteria passed"


def overview(found: dict, *, table_id: str = "overview") -> str:
    """Every sample is reachable, including single arms and uneven repetitions."""
    rows = []
    for subject, columns in found.items():
        labels = condition_labels(columns)
        for column, members in columns.items():
            for sample in members:
                anchor = sample_anchor(sample)
                rows.append(
                    f'<tr><td data-label="Task"><a href="#{task_anchor(subject)}">{escape(task_title(columns))}</a></td>'
                    f'<td data-label="Version">{escape(labels[column])}<small>Output {sample["attempt"]} · {escape(sample.get("run_group", ""))}</small></td>'
                    f'<td data-label="Checks">{escape(check_summary(sample))}</td>'
                    f'<td data-label="Quality">{escape(grade_summary(sample))}</td>'
                    f'<td data-label="Output"><a href="#{anchor}">View output</a></td></tr>'
                )
    return (
        f'<table id="{table_id}" class="sample-table" data-width="available"><thead><tr>'
        '<th scope="col">Task</th><th scope="col">Version</th>'
        '<th scope="col">Checks</th><th scope="col">Quality</th>'
        '<th scope="col">Output</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def sample_section(page: Path, sample: dict, label: str, output_url: str | None) -> str:
    anchor = sample_anchor(sample)
    diagnostics = sample["diagnostics"]
    if not diagnostics.get("comparison"):
        result_link = linked_file(
            page, sample["run"] / "results.json", output_url, "Recorded result"
        )
        return (
            f'<section id="{anchor}"><h3>{escape(sample["title"][:1].upper() + sample["title"][1:])} · {escape(label)} · Output {sample.get("attempt", 1)}</h3>'
            + (
                f'<p class="output-status">{escape(sample.get("run_group", ""))}</p>'
                if sample.get("run_group")
                else ""
            )
            + f"<p>No saved page or frozen comparison was recorded. {escape(sample.get('error') or '')}</p>"
            f"<p>{escape(check_summary(sample))}. Quality: {escape(grade_summary(sample))}.</p><p>{result_link}</p></section>"
        )
    comparison = diagnostics["comparison"]
    grade = sample.get("gradingResult") or {}
    quality = quality_results(sample)
    assessment = (
        "".join(
            f"<details><summary>{escape(quality_name(result))} — {escape(quality_status(result))}</summary>"
            f"<p>{escape(result.get('reason') or '')}</p>"
            + (
                f"<p><strong>Criterion:</strong> {escape(str(result['assertion']['value']))}</p>"
                if result.get("assertion", {}).get("type")
                in {"llm-rubric", "agent-rubric"}
                else ""
            )
            + "</details>"
            for result in quality
        )
        or "<p>No individual-output quality assessment was recorded.</p>"
    )
    if sample.get("comparisons"):
        assessment += (
            "<p>Assessed relative to another output:</p><ul>"
            + "".join(
                f'<li><a href="#{escape(anchor)}">{escape(title)}</a></li>'
                for anchor, title in sample["comparisons"]
            )
            + "</ul>"
        )
    checks = (
        '<div class="report-assessment"><details><summary>Checks · '
        + escape(check_summary(sample))
        + "</summary><p>Execution and page validity; these do not establish design quality.</p>"
        + result_list(check_results(sample))
        + "</details><details><summary>Quality · "
        + escape(grade_summary(sample))
        + "</summary>"
        + assessment
        + "</details></div>"
    )
    for index, result in enumerate(grade.get("componentResults", [])):
        judge = result.get("metadata", {}).get("judge", {}).get("metadata", {})
        if not judge.get("evidence"):
            continue
        directory = Path(judge["evidence"])
        captures = [
            str(path)
            for path in sorted(directory.glob("*"))
            if path.is_file()
            and MEDIA_TYPES.get(path.suffix.lower(), "").startswith("image/")
        ]
        checks += "<details><summary>Review evidence</summary>"
        checks += discovery_evidence(
            page, directory, captures, f"{anchor}-judge-{index}"
        )
        checks += (
            "<p>"
            + " · ".join(
                linked_file(page, directory / name, output_url, f"Judge {name}")
                for name in ("prompt.txt", "stream.jsonl")
            )
            + "</p></details>"
        )
    widths = ", ".join(
        f"{name}: {w} × {h}" for name, (w, h) in comparison["widths"].items()
    )
    history = []
    final_view = ""
    final = str(comparison["phases"][""])
    before_decision = comparison["phases"].get("_before_decision")
    for phase, saved in sorted(
        diagnostics["phases"].items(), key=lambda item: int(item[0])
    ):
        if not saved.get("page"):
            continue
        exported = exported_output(page, sample, phase, output_url)
        sample.setdefault("exports", {})[phase] = exported
        source = linked_file(
            page, Path(saved["page"]) / "index.html", output_url, "View HTML source"
        )
        captures = screens(page, sample, phase)
        tabs = "".join(
            f'<lf-tab id="{anchor}-p{phase}-{name}" label="{escape(name.capitalize())}">'
            + column_figure(
                page,
                f"{anchor}-p{phase}-{name}-shot",
                label,
                sample["sample"],
                captures[name],
                name,
            )
            + "</lf-tab>"
            for name, (w, h) in comparison["widths"].items()
        )
        screens_view = (
            f'<lf-tabs id="{anchor}-p{phase}-sizes">{tabs}</lf-tabs>'
            if tabs
            else "<p>No screenshots recorded.</p>"
        )
        content = (
            f'<p class="sample-links">{exported}</p>'
            f"{screens_view}"
            "<details><summary>Output details</summary>"
            "<p>This is a saved interactive copy. Controls and navigation work locally; no agent is connected and edits stay in this browser.</p>"
            f"<p>{source} — the markup that produced this output.</p>"
            f"<p>Captured sizes: {escape(widths)}.</p></details>"
        )
        if phase == final:
            final_view = (
                f'<section id="{anchor}-p{phase}"><h4>Final output · revision {phase}</h4>'
                f"{content}</section>"
            )
        else:
            role = (
                " · before decisions"
                if phase == before_decision
                else " · initial output"
                if phase == "1"
                else ""
            )
            history.append(
                f'<details id="{anchor}-p{phase}"><summary>Revision {phase}{role}</summary>'
                f"{content}</details>"
            )
    traces = [
        linked_file(page, path, output_url, path.relative_to(sample["work"]).as_posix())
        for path in sorted(sample["work"].glob("*"))
        if path.is_file() and path.suffix in {".json", ".jsonl", ".txt", ".log"}
    ]
    evidence = linked_file(
        page, sample["run"] / "results.json", output_url, "Promptfoo results"
    )
    metrics = measures(sample)
    phases_view = final_view + (
        f'<details id="{anchor}-phases"><summary>Earlier revisions ({len(history)})</summary>'
        "<p>Successive turns with the same author, in chronological order. "
        "The frozen request below records the feedback and decisions.</p>"
        + "".join(history)
        + "</details>"
        if history
        else ""
    )
    if not phases_view:
        phases_view = (
            f"<p>No saved page was recorded. {escape(sample.get('error') or '')}</p>"
        )
    return (
        f'<section id="{anchor}"><h3>{escape(sample["title"][:1].upper() + sample["title"][1:])} · {escape(label)} · Output {sample.get("attempt", 1)}</h3>'
        f'<p class="output-status">{escape(sample.get("run_group", ""))}</p>'
        f"{checks}"
        f"{phases_view}"
        f'<details class="report-metadata"><summary>Run details and original request</summary>'
        f"<dl><dt>Run</dt><dd>{escape(str(sample['run']))}</dd>"
        f"<dt>Output ID</dt><dd>{escape(sample['sample'])}</dd>"
        f"<dt>Author time</dt><dd>{shown(metrics['minutes'], '.1f')} minutes</dd>"
        f"<dt>Input tokens</dt><dd>{shown(metrics['input_tokens'], ',.0f')}</dd>"
        f"<dt>Cost</dt><dd>{shown(metrics['cost'], '.2f', '$')}</dd></dl><p>{evidence}</p>"
        f'<pre id="{anchor}-request">{escape(comparison["brief"])}</pre><ul>'
        + "".join(f"<li>{trace}</li>" for trace in traces)
        + "</ul></details></section>"
    )


def task_section(
    page: Path,
    subject: str,
    columns: dict,
    pairs: list[dict],
    output_url: str | None = None,
) -> str:
    labels = condition_labels(columns)
    scope = ""
    comparable = [
        sample
        for arm in columns.values()
        for sample in arm
        if sample["diagnostics"].get("comparison")
    ]
    if comparable:
        try:
            saved_comparison(comparable)
        except ValueError as error:
            scope = f"<p>{escape(str(error))} Each output retains its own request and viewport.</p>"
    judged = [pair for pair in pairs if pair["subject"] == subject]
    by_sample = {
        (column, s["sample"]): s for column, arm in columns.items() for s in arm
    }
    pair_sections = []
    compared = set()
    for number, pair in enumerate(judged, 1):
        selected = [
            (column, by_sample.get((column, name)))
            for column, name in pair["samples"].items()
        ]
        if len(selected) != 2 or any(sample is None for _, sample in selected):
            pair_sections.append(
                f"<p>Pair {number}: saved samples unavailable; {escape(verdict_line(pair, labels))}.</p>"
            )
            continue
        try:
            saved_comparison([sample for _, sample in selected])
        except ValueError as error:
            pair_sections.append(
                f"<p>Pair {number}: {escape(str(error))} The recorded judgment is retained in the raw results.</p>"
            )
            continue
        pair_sections.append(
            pair_section(page, task_anchor(subject), number, pair, *selected, labels)
        )
        compared.update(sample_anchor(sample) for _, sample in selected)
    if len(columns) == 2:
        (first, xs), (second, ys) = columns.items()
        # Unjudged outputs from a newer run remain comparable when older runs
        # already have judgments. Match within a run, never across its revisions.
        matches = []
        for run in dict.fromkeys(sample["run"] for sample in xs):
            left = [
                s for s in xs if s["run"] == run and sample_anchor(s) not in compared
            ]
            right = [
                s for s in ys if s["run"] == run and sample_anchor(s) not in compared
            ]
            matches.extend(zip(left, right))
        for number, (x, y) in enumerate(matches, len(judged) + 1):
            try:
                saved_comparison([x, y])
            except (KeyError, ValueError):
                continue
            pair_sections.append(
                pair_section(
                    page,
                    task_anchor(subject),
                    number,
                    None,
                    (first, x),
                    (second, y),
                    labels,
                )
            )
        if len(xs) != len(ys):
            pair_sections.append(
                "<p>Unmatched samples remain in their arm tabs and the score table.</p>"
            )
    comparison_tab = (
        f'<lf-tab id="{task_anchor(subject)}-compare" label="Compare">'
        + "".join(pair_sections)
        + "</lf-tab>"
        if pair_sections
        else ""
    )
    sample_tabs = "".join(
        f'<lf-tab id="{task_anchor(subject)}-arm-{index}" label="{escape(labels[column])}">'
        + (
            f'<lf-tabs id="{task_anchor(subject)}-arm-{index}-outputs">'
            + "".join(
                f'<lf-tab id="{sample_anchor(sample)}-view" label="Output {sample.get("attempt", 1)}">'
                + sample_section(page, sample, labels[column], output_url)
                + "</lf-tab>"
                for sample in arm
            )
            + "</lf-tabs>"
            if len(arm) > 1
            else sample_section(page, arm[0], labels[column], output_url)
        )
        + "</lf-tab>"
        for index, (column, arm) in enumerate(columns.items(), 1)
    )
    pair_notes = (
        "<p>Pairwise judgments: " + escape(outcome(subject, judged, labels)) + "</p>"
        if judged
        else ""
    )
    return (
        f'<section id="{task_anchor(subject)}"><h2>{escape(task_title(columns))}</h2>'
        f"<details><summary>About this case</summary><p>Case ID: <code>{escape(subject)}</code>. "
        "Each output is a separate author attempt at this task; revisions are turns within that attempt.</p>"
        f"{scope}{pair_notes}</details>"
        f'<lf-tabs id="{task_anchor(subject)}-arms" data-width="available">{comparison_tab}{sample_tabs}</lf-tabs></section>'
    )


def discovery_section(
    page: Path,
    runs: tuple[Path, ...],
    output_url: str | None = None,
    found: dict | None = None,
) -> str:
    """Show exploratory observations separately from pair outcomes and score totals."""
    responses = [
        path
        for run in runs
        for path in sorted((run / "discovery").glob("*/attempt-*/response.json"))
    ]
    if not responses:
        return ""
    identities = {
        sample["sample"]: sample_anchor(sample)
        for columns in (found or {}).values()
        for members in columns.values()
        for sample in members
    }
    attempts = []
    for path in responses:
        anchor = "discovery-" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
        response = json.loads(path.read_text())
        output = response.get("output")
        sample = response["sample"]
        observations = []
        summaries = []
        if output:
            status = output["status"].replace("_", " ")
            for index, observation in enumerate(output["observations"], 1):
                width, height = observation["viewport"]
                summaries.append(f"{width} × {height}: {observation['summary']}")
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
                    f"<h3>{escape(observation['kind'].capitalize())}: {escape(observation['summary'])}</h3>"
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
        links = " · ".join(
            f'<a href="#{identities[name]}">View {escape(name)}</a>'
            for name in response.get("samples", [sample])
            if name in identities
        )
        attempts.append(
            f'<details id="{anchor}"><summary>{escape(sample)}: {escape(" · ".join(summaries) or status)}</summary>'
            + (f"<p>{links}</p>" if links else "")
            + explored
            + ("".join(observations) or "<p>No observations recorded.</p>")
            + remaining
            + f"<p>{linked_file(page, path, output_url, 'Observation response')}"
            + (
                " · "
                + linked_file(
                    page, Path(response["source"]), output_url, "Original judgment"
                )
                if response.get("source")
                else ""
            )
            + "</p></details>"
        )
    return (
        '<section id="discovery"><h2>Exploratory observations</h2>'
        "<p>An agent chose these variations to find useful observations. These attempts "
        "are outside the fixed comparison; their counts are not benchmark rates.</p>"
        + "".join(attempts)
        + "</section>"
    )


def review_sections(
    page: Path, review: dict, found: dict, output_url: str | None
) -> str:
    """Render the agent's explicit experiment assessment beside its retained evidence."""
    samples = {
        (sample["run"].resolve(), sample["sample"]): sample
        for columns in found.values()
        for members in columns.values()
        for sample in members
    }

    def sample_for(reference: dict) -> dict:
        identity = (Path(reference["run"]).resolve(), reference["sample"])
        if identity not in samples:
            raise click.ClickException(
                f"Review sample not in supplied runs: {identity[0]} / {identity[1]}"
            )
        return samples[identity]

    def output_link(sample: dict, label: str = "") -> str:
        final = str(
            sample["diagnostics"].get("comparison", {}).get("phases", {}).get("", "")
        )
        return (
            (f"<strong>{escape(label)}</strong>: " if label else "")
            + '<span class="capture-actions">'
            + sample.get("exports", {}).get(final, "Saved output unavailable")
            + f'<a href="#{sample_anchor(sample)}">Inspect results</a></span>'
        )

    def evidence_links(paths: list[str], anchor: str, label: str) -> str:
        images = [
            value
            for value in paths
            if MEDIA_TYPES.get(Path(value).suffix.lower(), "").startswith("image/")
        ]
        links = " · ".join(
            linked_file(page, Path(path), output_url, Path(path).name)
            for path in paths
            if path not in images
        )
        captures = ""
        if images:
            added = media_paths(page, [Path(value) for value in images])
            captures = (
                '<div class="pair-shots">'
                + "".join(
                    f'<figure id="{anchor}-capture-{index}"><figcaption>{escape(Path(value).stem.replace("-", " "))}</figcaption>'
                    + shot(page, added[Path(value)], Path(value).stem, True)
                    + "</figure>"
                    for index, value in enumerate(images, 1)
                )
                + "</div>"
            )
        return captures + (
            f"<details><summary>{label}</summary><p>{links}</p></details>"
            if links
            else ""
        )

    latest = review["latest"]
    latest_runs = {Path(run).resolve() for run in latest["runs"]}
    missing = latest_runs - {run for run, _ in samples}
    if missing:
        raise click.ClickException(
            "Latest review runs not in supplied results: "
            + ", ".join(map(str, sorted(missing)))
        )
    selected = {
        subject: {
            column: [s for s in members if s["run"].resolve() in latest_runs]
            for column, members in columns.items()
        }
        for subject, columns in found.items()
    }
    selected = {
        subject: {column: members for column, members in columns.items() if members}
        for subject, columns in selected.items()
    }
    selected = {subject: columns for subject, columns in selected.items() if columns}
    findings = []
    for finding in latest["findings"]:
        sample = sample_for(finding)
        if sample["run"].resolve() not in latest_runs:
            raise click.ClickException(
                f"Latest finding is outside the latest run group: {finding['sample']}"
            )
        findings.append(
            f"<li><p>{escape(finding['finding'])}</p><p>{output_link(sample, sample['title'])}</p></li>"
        )
    experiments = []
    for experiment in review["experiments"]:
        anchor = "experiment-" + experiment["id"]
        comparisons = []
        for index, comparison in enumerate(experiment["comparisons"], 1):
            before, after = (
                sample_for(comparison["before"]),
                sample_for(comparison["after"]),
            )
            comparisons.append(
                f'<lf-tab id="{anchor}-comparison-{index}" label="{escape(comparison.get("label", comparison["title"]))}">'
                + (
                    f'<p class="comparison-summary">{escape(comparison["summary"])}</p>'
                    if comparison.get("summary")
                    else ""
                )
                + comparison_screens(
                    page,
                    f"{anchor}-comparison-{index}",
                    [("Before", before), ("After", after)],
                    [output_link(before), output_link(after)],
                    before_after=True,
                )
                + f"<details><summary>Comparison assessment</summary><p>{escape(comparison['finding'])}</p></details>"
                + evidence_links(
                    comparison["evidence"],
                    f"{anchor}-comparison-{index}-evidence",
                    "Judgment record",
                )
                + "</lf-tab>"
            )
        comparisons_view = (
            f'<div class="report-flat-tabs"><lf-tabs id="{anchor}-comparisons" data-width="available">'
            + "".join(comparisons)
            + "</lf-tabs></div>"
            if comparisons
            else ""
        )
        experiments.append(
            f'<lf-tab id="{anchor}" label="{escape(experiment.get("label", experiment["title"]))}" summary="{escape(experiment["recommendation"])}">'
            '<div class="experiment-heading">'
            f"<h2>{escape(experiment['title'])}</h2>"
            f'<p class="experiment-recommendation"><span>Recommendation:</span> <strong>{escape(experiment["recommendation"])}</strong></p></div>'
            f'<p class="experiment-change">{escape(experiment["change"])}</p>'
            f"<p><strong>What the evidence supports.</strong> {escape(experiment['reason'])}</p>"
            + comparisons_view
            + evidence_links(
                experiment["evidence"], f"{anchor}-evidence", "Change sources"
            )
            + f"<details><summary>Scope and limitations</summary><p>{escape(experiment['period'])}</p><p>{escape(experiment['limits'])}</p></details>"
            + "</lf-tab>"
        )
    return (
        '<lf-tab id="changes-tested" label="Changes tested">'
        '<lf-tabs id="experiments" list="side" data-width="available">'
        + "".join(experiments)
        + "</lf-tabs></lf-tab>"
        + f'<lf-tab id="latest-run" label="Latest outputs"><h2>{escape(latest["title"])}</h2>'
        + f"<p>{escape(latest['summary'])}</p>"
        + overview(selected, table_id="latest-overview")
        + f"<details><summary>Review findings</summary><ul>{''.join(findings)}</ul></details>"
        + "</lf-tab>"
    )


@click.command()
@click.argument("page", type=click.Path(file_okay=False, path_type=Path))
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--output-url", help="HTTP URL serving PAGE/evidence, for saved pages and traces."
)
@click.option(
    "--review",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON review naming the latest run group, tested changes and recommendations.",
)
def eval_report(
    page: Path, runs: tuple[Path, ...], output_url: str | None, review: Path | None
):
    """Write PAGE, a Leaf page of the authored-task samples in RUNS.

    RUNS are run directories under `.tmp/eval/`; `eval-pairs` on the same runs
    supplies the pairing and verdicts. PAGE is created when absent, and its
    `index.html` is rewritten otherwise. Serve it with `leaf server start PAGE`.
    Serve PAGE/evidence with a static server and pass its URL as --output-url
    to open saved pages and raw evidence from the report. Without that URL the
    report names the exported files but does not claim they are reachable."""
    if not (page / "events.jsonl").exists():
        leaf("page", "init", str(page))
    found = report_samples(runs)
    assessment = json.loads(review.read_text()) if review else None
    if assessment:
        latest_runs = {Path(run).resolve() for run in assessment["latest"]["runs"]}
        comparison_links = defaultdict(list)
        for experiment in assessment["experiments"]:
            for index, comparison in enumerate(experiment["comparisons"], 1):
                link = (
                    f"experiment-{experiment['id']}-comparison-{index}",
                    f"{experiment.get('label', experiment['title'])} · {comparison.get('label', comparison['title'])}",
                )
                for side in ("before", "after"):
                    reference = comparison[side]
                    comparison_links[
                        Path(reference["run"]).resolve(), reference["sample"]
                    ].append(link)
        for columns in found.values():
            for members in columns.values():
                for sample in members:
                    sample["comparisons"] = comparison_links[
                        sample["run"].resolve(), sample["sample"]
                    ]
                    sample["run_group"] = (
                        "Latest run"
                        if sample["run"].resolve() in latest_runs
                        else "Earlier run"
                    )
    pairs = list(
        {
            json.dumps(pair, sort_keys=True): pair
            for run in runs
            if (run / "pairs.json").exists()
            for pair in json.loads((run / "pairs.json").read_text())
        }.values()
    )
    discovery = discovery_section(page, runs, output_url, found)
    runs_text = (
        "<ul>"
        + "".join(
            f"<li>{escape(run.name)}: "
            + linked_file(page, run / "results.json", output_url, "Results")
            + (
                " · "
                + linked_file(page, run / "pairs.json", output_url, "Pair judgments")
                if (run / "pairs.json").exists()
                else ""
            )
            + "</li>"
            for run in runs
        )
        + "</ul>"
    )
    body = (
        '<lf-tabs id="report-views" list="side" data-width="available">'
        '<lf-tab id="scores" label="Outputs">'
        + overview(found)
        + f"<details><summary>Runs and score definitions</summary>{runs_text}"
        "<p>Checks are execution assertions. Quality shows recorded live, visual or text rubric "
        "judgments; the grading reasons identify their scope. It is not the aggregate assertion score. "
        "Pairwise preferences and exploratory observations "
        "are shown separately. Author time sums recorded phases; unavailable is not zero.</p></details></lf-tab>"
        + "".join(
            f'<lf-tab id="{task_anchor(subject)}-view" label="{escape(task_title(columns))}">'
            + task_section(page, subject, columns, pairs, output_url)
            + "</lf-tab>"
            for subject, columns in found.items()
        )
        + (
            f'<lf-tab id="observations" label="Exploration">{discovery}</lf-tab>'
            if discovery
            else ""
        )
        + "</lf-tabs>"
    )
    title = "Authoring comparisons"
    if assessment:
        title = assessment["title"]
        body = (
            '<lf-tabs id="review-views" data-width="available">'
            + review_sections(page, assessment, found, output_url)
            + f'<lf-tab id="all-results" label="All outputs">{body}</lf-tab></lf-tabs>'
        )
    (page / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<title>{escape(title)}</title>
<meta name="description" content="Saved authored pages side by side, with their original review conditions, costs and judgments.">
<style>{STYLE}</style>
</head>
<body>
<main class="layout-workspace density-working">
<header><h1 id="title">{escape(title)}</h1></header>
{body}
</main>
</body>
</html>
"""
    )
    click.echo(page / "index.html")
    click.echo(f"Saved outputs: {page / 'evidence'}")
