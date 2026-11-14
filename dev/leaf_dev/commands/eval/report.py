"""Render Promptfoo runs as one Leaf browser of scores, judgments and outputs.

Every native result remains visible, including single arms, unequal repetitions and
failed attempts. Identical native results appear once, with every source-run alias
retained; changed grades remain distinct. Execution checks, authoring grades, pairwise
preferences and exploratory observations retain their distinct meanings. Requests,
viewports and phases come from retained results, never today's catalog. Native
preferences remain per-order ordinal judgments.

A campaign author's review is Leaf markup (`evals/README.md`, "Render a report"), and
its tabs come before one holding the browser. Its one element of its own,
`lf-eval-cite`, reaches what an author can't write by hand: a saved output's captures
and links, or a retained file. The report replaces each citation with elements Leaf
already ships, so the page holds no citation and no widget of its own, and a citation
that names nothing the report can find stops it. Scores never infer a decision; only
the review's `lf-ask` makes one. Comparisons default to complete pairs; only an
`aligned` citation uses a before/after wipe.

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
from string import Template
from urllib.parse import quote

import click
import turbohtml
from PIL import Image

from leaf.event_log import initialized
from leaf.registry.storage import layer_packages
from leaf.schema import MEDIA_TYPES
from leaf_dev import LEAF_COMMAND, gallery
from leaf_dev.arms import observed_sum
from leaf_dev.eval_records import judgments, run_samples
from leaf_dev.regrade import ASPECTS, saved_comparison

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


# What a report needs without being asked: `lf-diff` for a cited patch, and `lf-diagram`
# for the review's campaign. Packages already on the page stay.
REQUIRED_PACKAGES = ["diff", "diagram"]

UNREVIEWED = '<h1 id="title">Authoring comparisons</h1>'

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
.comparison-views > details { margin-block: 1rem; }
.comparison-views > details > summary { font-weight: 600; }
.comparison-views > section > h4 { margin-block: .75rem; }
.pair-shots details img { margin-top: .5rem; }
.sample-links { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; }
.sample-table td { vertical-align: top; }
/* Keep metadata in its own formatting context: Chrome 156 crashes when this
   report reveals the table with ordinary block metadata; flow-root preserves it. */
.sample-table small { display: flow-root; max-inline-size: 20rem; overflow-wrap: anywhere; }
#report-views lf-tabs { margin-block: .75rem; }
@media (max-width: 640px) {
  .sample-table, .sample-table tbody { display: block; }
  .sample-table thead { display: none; }
  .sample-table tr { display: grid; grid-template-columns: 1fr 1fr; padding-block: .75rem; border-bottom: 1px solid var(--border-2); }
  .sample-table td { display: block; border: 0; min-width: 0; }
  .sample-table td::before { content: attr(data-label); display: block; font-size: .75rem; color: var(--muted); }
}
main > lf-tabs, #report-views { border-radius: 0; }
.result-list { margin-block: .5rem; }
.result-list > div { display: flex; justify-content: space-between; gap: 1rem; padding-block: .35rem; border-bottom: 1px solid var(--border-2); }
.result-list dt { font-weight: 500; }
.result-list dd { margin: 0; text-align: right; }
.report-metadata { overflow-wrap: anywhere; }
.report-metadata dl { display: grid; grid-template-columns: auto 1fr; gap: .35rem 1.5rem; }
.report-metadata dd { margin: 0; }
.output-status { color: var(--muted); font-size: .875rem; }
.capture-actions + .output-status { display: block; }
.report-meta { color: var(--muted); font-size: .875rem; }
main > lf-tabs:not(#report-views) > lf-tab:not(#all-results) :is(p, ul, ol, dl) { max-width: 82ch; }
"""


def tab_group(anchor: str, items: list[tuple[str, str, str]]) -> str:
    """Only alternatives need tabs; retain anchors when showing one item directly."""
    if len(items) == 1:
        item, label, content = items[0]
        return (
            f'<div id="{anchor}"><section id="{item}" aria-label="{escape(label)}">'
            f"{content}</section></div>"
        )
    return (
        f'<lf-tabs id="{anchor}" data-width="available">'
        + "".join(
            f'<lf-tab id="{item}" label="{escape(label)}">{content}</lf-tab>'
            for item, label, content in items
        )
        + "</lf-tabs>"
    )


def leaf(*args: str) -> str:
    return subprocess.run(
        [*LEAF_COMMAND, *args], check=True, capture_output=True, text=True
    ).stdout


def condition_labels(columns: dict) -> dict[str, str]:
    """Name the condition when it distinguishes arms, and the recorded arm otherwise."""
    names = {
        column: {"leaf": "Leaf", "html": "Plain HTML"}.get(
            members[0]["execution_metadata"]["condition"], column
        )
        for column, members in columns.items()
    }
    return {
        column: name if list(names.values()).count(name) == 1 else column
        for column, name in names.items()
    }


def task_anchor(subject: str) -> str:
    return "task-" + hashlib.sha256(subject.encode()).hexdigest()[:12]


def task_title(columns: dict) -> str:
    """Name the saved case; ids still own grouping."""
    title = next(iter(columns.values()))[0]["title"]
    return title[:1].upper() + title[1:]


def run_names(sample: dict) -> str:
    """The runs that hold a sample, by the directory names `eval report` was given."""
    return " · ".join(run.name for run in sample["runs"])


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
    paths: list[str],
    width: str,
    actions: str = "",
    *,
    caption: bool = True,
) -> str:
    heading = f"<figcaption>{escape(label)}</figcaption>" if caption else ""
    row = f'<div class="capture-actions-row">{actions}</div>' if actions else ""
    if not paths:
        return f'<figure id="{anchor}">{heading}{row}<p>No screens.</p></figure>'
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
        f'<figure id="{anchor}">{heading}{row}'
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
    aligned: bool = False,
    phases: list[str] | None = None,
) -> str:
    """Compare selected phases at equal recorded viewport dimensions; default final."""
    links = "".join(
        f"<div><strong>{escape(label)}</strong> {action}</div>"
        for (label, _), action in zip(columns, actions or [], strict=False)
    )
    captures = []
    for index, (label, sample) in enumerate(columns):
        comparison = sample["diagnostics"].get("comparison")
        if not comparison:
            return f"<p>No saved comparison captures are available.</p>{links}"
        phase = phases[index] if phases is not None else str(comparison["phases"][""])
        paths = screens(page, sample, phase)
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
        for name, size in sorted(
            columns[0][1]["diagnostics"]["comparison"]["widths"].items(),
            key=lambda item: item[0] != "desktop",
        )
        if all(tuple(size) in capture[2] for capture in captures)
    ]
    if not common:
        return f"<p>No matching captured viewports. Open each output to inspect it.</p>{links}"
    views = []
    for name, (width, height) in common:
        images = [paths[width, height] for _, _, paths in captures]
        if aligned and all(images):
            contents = gallery.shot(
                f"{anchor}-{name}-shot",
                f"Before and after at {width} × {height}",
                images[0][0],
                images[1][0],
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
                            paths[width, height][1:],
                            f"{width} × {height}",
                        )
                        for index, (label, sample, paths) in enumerate(captures, 1)
                    )
                    + "</div></details>"
                )
        else:
            contents = (
                f'<div id="{anchor}-{name}-shot" class="pair-shots">'
                + "".join(
                    column_figure(
                        page,
                        f"{anchor}-{name}-{index}",
                        label,
                        paths[width, height],
                        f"{width} × {height}",
                        actions[index - 1] if actions else "",
                    )
                    for index, (label, sample, paths) in enumerate(captures, 1)
                )
                + "</div>"
            )
        label = f"{name.capitalize()} · {width} × {height}"
        views.append(
            f'<section id="{anchor}-{name}"><h4>{escape(label)}</h4>{contents}</section>'
            if not views
            else f'<details id="{anchor}-{name}"><summary>{escape(label)}</summary>{contents}</details>'
        )
    return f'<div id="{anchor}-widths" class="comparison-views">{"".join(views)}</div>'


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
        f"The captures show the final saved phase, {versions['']}, "
        "before the judge's inspection actions."
    )
    if "_before_decision" in versions:
        phase_description += (
            " This phase follows the request to record the user's decisions as final. "
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
        f"{notes}"
        f"{comparison_screens(page, sid, [(label, sample) for label, _, sample in columns])}"
        f"{earlier}"
        f"<details><summary>Saved phases and run provenance</summary><p>{phase_description} "
        "Inspection actions and states, when judged, are retained in the judgment traces.</p>"
        "<p>A repeated comparison swaps the pages' left/right positions to check whether the judge's preference changes with presentation order. "
        + (
            "Recorded presentation orders appear above; an unscored order supplies no preference."
            if pair
            else "This pair has no repeated comparison judgment."
        )
        + "</p><p>Runs: "
        + escape(
            " / ".join(
                dict.fromkeys(run.name for _, _, s in columns for run in s["runs"])
            )
        )
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
    return "sample-" + sample["identity"][:12]


def phase_label(sample: dict, phase: str) -> str:
    """A scheduled final turn is not a final output when the author never finished."""
    saved = sample["diagnostics"].get("phases", {}).get(phase)
    if saved is None:
        return "Output unavailable"
    if saved.get("trace", {}).get("completed") is False:
        return "Saved output · author turn incomplete"
    roles = sample["diagnostics"]["comparison"]["phases"]
    if phase == "1":
        return "Initial output"
    if phase == roles.get("_before_decision"):
        return "Before decision"
    if phase == roles.get(""):
        return "Final output"
    return f"Phase {phase}"


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
    except (subprocess.CalledProcessError, OSError) as error:
        diagnostic = target.with_name("export-error.txt")
        diagnostic.write_text(
            error.stderr
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        detail = (
            f'<a href="{escape(output_url.rstrip("/") + "/" + slot + "/export-error.txt")}" target="_blank" rel="noopener">Export diagnostic</a>'
            if output_url
            else f"Export diagnostic not served: <code>{escape(str(diagnostic))}</code>"
        )
        return f"Saved-page export unavailable · {detail}"
    if output_url:
        href = output_url.rstrip("/") + "/" + slot + "/index.html"
        return f'<a href="{escape(href)}" target="_blank" rel="noopener">Open saved page</a>'
    return f"Output not served: <code>{escape(str(target))}</code>"


def check_results(sample: dict) -> list[tuple[str, str]]:
    labels = {
        "completed": "Author finished",
        "page": "Output saved",
        "page-valid": "Page validation",
    }
    asserted = {assertion.get("metric") for assertion in sample["assertions"]}
    return [
        (
            labels.get(name, name.replace("-", " ").capitalize()),
            (
                "Incomplete"
                if name == "completed" and sample["execution"] == "incomplete"
                else "Passed"
                if value
                else "Failed"
            ),
        )
        for name, value in sample["checks"].items()
        if name in asserted
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
    if sample["execution"] == "incomplete":
        return "Author did not finish"
    if sample["execution"] == "error":
        return "Execution unavailable"
    results = check_results(sample)
    if not results:
        return "Not checked"
    failed = [name for name, value in results if value == "Failed"]
    return (
        f"{len(failed)} of {len(results)} checks failed"
        if failed
        else f"{len(results)} checks passed"
    )


def quality_unavailable(sample: dict) -> str | None:
    """Execution evidence bounds which recorded grades can assess an output."""
    return {
        "incomplete": "Author did not finish",
        "error": "Execution unavailable",
        "empty": "No authored output",
    }.get(sample["execution"])


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
        model = metadata.get("judge", {}).get("metadata", {}).get("model")
        return "Live task review" + (f" · {model}" if model else "")
    if "page_defects" in metadata:
        return "Visual review"
    return (
        (result.get("assertion", {}).get("metric") or "Criterion")
        .replace("-", " ")
        .capitalize()
    )


def quality_status(result: dict, sample: dict) -> str:
    if unavailable := quality_unavailable(sample):
        return f"Not assessed — {unavailable.lower()}"
    metadata = result.get("metadata", {})
    if metadata.get("authoring_grade"):
        status = metadata["authoring_grade"]["status"]
        return {"pass": "Passed", "defect": "Defect found"}.get(
            status, status.replace("_", " ").capitalize()
        )
    if "page_defects" in metadata:
        reading = metadata["page_defects"]
        if reading["status"] == "unscored":
            return "Unscored"
        count = len(reading["defects"])
        return f"{count} defect{'s' if count != 1 else ''} found"
    return "Passed" if result.get("pass") else "Failed"


def grade_summary(sample: dict) -> str:
    if unavailable := quality_unavailable(sample):
        return f"No quality assessment — {unavailable.lower()}"
    results = quality_results(sample)
    if not results:
        return "No individual assessment"
    if len(results) == 1:
        return (
            quality_name(results[0]) + ": " + quality_status(results[0], sample).lower()
        )
    return "; ".join(
        f"{quality_name(result)}: {quality_status(result, sample).lower()}"
        for result in results
    )


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
                    f'<td data-label="Version">{escape(labels[column])}<small>Output {sample["attempt"]} · {escape(run_names(sample))}</small>'
                    f"<small>{escape(sample['execution_metadata']['author']['model'] or 'Model unavailable in retained run')}</small></td>"
                    f'<td data-label="Checks">{escape(check_summary(sample))}</td>'
                    f'<td data-label="Recorded reviews">{escape(grade_summary(sample))}</td>'
                    f'<td data-label="Output"><a href="#{anchor}">View output</a></td></tr>'
                )
    return (
        f'<table id="{table_id}" class="sample-table" data-width="available"><thead><tr>'
        '<th scope="col">Task</th><th scope="col">Version</th>'
        '<th scope="col">Checks</th><th scope="col">Recorded reviews</th>'
        '<th scope="col">Output</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def capture_errors(sample: dict, phase: str) -> str:
    return "".join(
        f"<p><strong>{escape(name.capitalize())} capture unavailable:</strong> {escape(reason)}</p>"
        for name, reason in sample["diagnostics"]
        .get("phases", {})
        .get(phase, {})
        .get("capture_errors", {})
        .items()
    )


def sample_section(page: Path, sample: dict, label: str, output_url: str | None) -> str:
    anchor = sample_anchor(sample)
    diagnostics = sample["diagnostics"]
    if not diagnostics.get("comparison"):
        result_link = " · ".join(
            linked_file(page, run / "results.json", output_url, run.name)
            for run in sample["runs"]
        )
        return (
            f'<section id="{anchor}"><h3>{escape(sample["title"][:1].upper() + sample["title"][1:])} · {escape(label)} · Output {sample.get("attempt", 1)}</h3>'
            + f'<p class="output-status">{escape(run_names(sample))}</p>'
            + f"<p>No saved page or frozen comparison was recorded. {escape(sample.get('error') or '')}</p>"
            f"<p>{escape(check_summary(sample))}. Quality: {escape(grade_summary(sample))}.</p><p>{result_link}</p></section>"
        )
    comparison = diagnostics["comparison"]
    grade = sample.get("gradingResult") or {}
    quality = quality_results(sample)
    assessment = (
        "".join(
            f'<section id="{anchor}-review-{index}"><h4>{escape(quality_name(result))} — {escape(quality_status(result, sample))}</h4>'
            f"<p>{escape(result.get('reason') or '')}</p>"
            + (
                f"<p><strong>Criterion:</strong> {escape(str(result['assertion']['value']))}</p>"
                if result.get("assertion", {}).get("type")
                in {"llm-rubric", "agent-rubric"}
                else ""
            )
            + "</section>"
            for index, result in enumerate(quality)
        )
        or "<p>No individual-output quality assessment was recorded.</p>"
    )
    if sample.get("citations"):
        assessment += (
            "<p>Cited in the review:</p><ul>"
            + "".join(
                f'<li><a href="#{escape(anchor)}">{escape(title)}</a></li>'
                for anchor, title in dict.fromkeys(sample["citations"])
            )
            + "</ul>"
        )
    checks = (
        "<details><summary>Checks and recorded reviews</summary>"
        "<h4>Execution and page checks</h4>"
        "<p>These checks establish execution and page validity.</p>"
        + result_list(check_results(sample))
        + assessment
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
        checks += (
            f'<section id="{anchor}-judge-{index}-record"><h4>Review evidence</h4>'
        )
        checks += discovery_evidence(
            page, directory, captures, f"{anchor}-judge-{index}"
        )
        checks += (
            "<p>"
            + " · ".join(
                linked_file(page, directory / name, output_url, f"Judge {name}")
                for name in ("prompt.txt", "stream.jsonl")
            )
            + "</p></section>"
        )
    checks += "</details>"
    widths = ", ".join(
        f"{name}: {w} × {h}" for name, (w, h) in comparison["widths"].items()
    )
    history = []
    sources = []
    final_view = ""
    final = str(comparison["phases"][""])
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
        sources.append(f"<li>Phase {escape(phase)}: {source}</li>")
        captures = screens(page, sample, phase)
        tabs = [
            (
                f"{anchor}-p{phase}-{name}",
                name.capitalize(),
                column_figure(
                    page,
                    f"{anchor}-p{phase}-{name}-shot",
                    label,
                    captures[name],
                    name,
                    caption=False,
                ),
            )
            for name in comparison["widths"]
        ]
        screens_view = "<p>No screenshots recorded.</p>"
        if tabs:
            primary, *additional = tabs
            screen_id, _, figure = primary
            screens_view = f'<div id="{anchor}-p{phase}-sizes"><section id="{screen_id}">{figure}</section>'
            if additional:
                screens_view += (
                    f"<details><summary>Other captured sizes ({len(additional)})</summary>"
                    + "".join(
                        f'<section id="{screen_id}"><h4>{escape(name)}</h4>{figure}</section>'
                        for screen_id, name, figure in additional
                    )
                    + "</details>"
                )
            screens_view += "</div>"
        content = f'<p class="sample-links">{exported}</p>{capture_errors(sample, phase)}{screens_view}'
        if phase == final:
            role = phase_label(sample, phase)
            final_view = (
                f'<section id="{anchor}-p{phase}"><h3>{role} · phase {phase}</h3>'
                f"{content}</section>"
            )
        else:
            role = phase_label(sample, phase)
            title = f"Phase {phase}"
            if role != title:
                title += f" · {role.lower()}"
            history.append(
                f'<details id="{anchor}-p{phase}"><summary>{escape(title)}</summary>'
                f"{content}</details>"
            )
    traces = [
        linked_file(page, path, output_url, path.relative_to(sample["work"]).as_posix())
        for path in sorted(sample["work"].glob("*"))
        if path.is_file() and path.suffix in {".json", ".jsonl", ".txt", ".log"}
    ]
    evidence = " · ".join(
        linked_file(page, run / "results.json", output_url, run.name)
        for run in sample["runs"]
    )
    metrics = measures(sample)
    phases_view = final_view + (
        f'<details id="{anchor}-phases"><summary>Earlier phases ({len(history)})</summary>'
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
    execution = f'<p class="output-status">{escape(grade_summary(sample))}.</p>'
    if sample["execution_error"]:
        execution += f"<p><strong>Execution error:</strong> {escape(sample['execution_error'])}</p>"
    return (
        f'<section id="{anchor}">'
        f'<p class="output-status">{escape(label)} · {escape(run_names(sample))}</p>'
        f"{execution}"
        f"{checks}"
        f"{phases_view}"
        f'<details class="report-metadata"><summary>Request, sources and run details</summary>'
        "<p>Saved pages preserve the reviewed state and support local navigation. "
        "Leaf actions that record edits or decisions require a live page. "
        "No agent is connected to these copies.</p>"
        f"<p>Author: {escape(sample['execution_metadata']['author']['model'] or 'Unavailable in retained run')} "
        f"via {escape(sample['execution_metadata']['author']['harness'])} · {escape(sample['execution_metadata']['kind'])}.</p>"
        f"<p>Selected viewport conditions: {escape(', '.join(sample['execution_metadata']['requested_viewports']))}.</p>"
        f"<p>Captured sizes: {escape(widths)}.</p><ul>{''.join(sources)}</ul>"
        f"<dl><dt>Case ID</dt><dd>{escape(sample['subject'])}</dd>"
        f"<dt>Result ID</dt><dd>{escape(sample['result_id'])}</dd>"
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
            (column, sample)
            for column, name in pair["samples"].items()
            if (sample := by_sample.get((column, name))) is not None
        ]
        if len(selected) != 2:
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
        for run in dict.fromkeys(run for sample in xs for run in sample["runs"]):
            left = [
                s for s in xs if run in s["runs"] and sample_anchor(s) not in compared
            ]
            right = [
                s for s in ys if run in s["runs"] and sample_anchor(s) not in compared
            ]
            for x, y in zip(left, right, strict=False):
                if (x, y) not in matches:
                    matches.append((x, y))
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
    items = (
        [(f"{task_anchor(subject)}-compare", "Compare", "".join(pair_sections))]
        if pair_sections
        else []
    )
    items.extend(
        (
            f"{task_anchor(subject)}-arm-{index}",
            labels[column],
            tab_group(
                f"{task_anchor(subject)}-arm-{index}-outputs",
                [
                    (
                        f"{sample_anchor(sample)}-view",
                        f"Output {sample.get('attempt', 1)}",
                        sample_section(page, sample, labels[column], output_url),
                    )
                    for sample in arm
                ],
            )
            if len(arm) > 1
            else sample_section(page, arm[0], labels[column], output_url),
        )
        for index, (column, arm) in enumerate(columns.items(), 1)
    )
    pair_notes = (
        "<p>Pairwise judgments: " + escape(outcome(subject, judged, labels)) + "</p>"
        if judged
        else ""
    )
    return (
        f'<section id="{task_anchor(subject)}"><h2>{escape(task_title(columns))}</h2>'
        f"{scope}{pair_notes}"
        + tab_group(f"{task_anchor(subject)}-arms", items)
        + "</section>"
    )


def discovery_section(
    page: Path,
    runs: tuple[Path, ...],
    output_url: str | None = None,
    found: dict | None = None,
) -> str:
    """Show exploratory observations separately from pair outcomes and score totals."""
    records = judgments(runs, "discovery")
    if not records:
        return ""
    identities = {
        sample["sample"]: sample_anchor(sample)
        for columns in (found or {}).values()
        for members in columns.values()
        for sample in members
    }
    attempts = []
    for run, result, recorded in records:
        anchor = "discovery-" + hashlib.sha256(result["id"].encode()).hexdigest()[:12]
        judge = recorded.get("metadata", {}).get("judge", {})
        output = judge.get("output")
        sample = result["testCase"]["metadata"]["saved"][0]["sample"]
        observations = []
        summaries = []
        if output:
            # The judge names its evidence relative to the directory it was given.
            directory = Path(judge["metadata"]["evidence"])
            status = output["status"].replace("_", " ")
            for index, observation in enumerate(output["observations"], 1):
                width, height = observation["viewport"]
                summaries.append(f"{width} × {height}: {observation['summary']}")
                steps = "".join(
                    f"<li>{escape(step)}</li>" for step in observation["steps"]
                )
                evidence = discovery_evidence(
                    page,
                    directory,
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
            remaining = f"<p>{escape(recorded.get('reason') or result.get('error') or 'No observation output returned.')}</p>"
        links = (
            f'<a href="#{identities[sample]}">View {escape(sample)}</a>'
            if sample in identities
            else ""
        )
        attempts.append(
            f'<details id="{anchor}"><summary>{escape(sample)}: {escape(" · ".join(summaries) or status)}</summary>'
            + (f"<p>{links}</p>" if links else "")
            + explored
            + ("".join(observations) or "<p>No observations recorded.</p>")
            + remaining
            + f"<p>{linked_file(page, run / 'results.json', output_url, 'Observation results')}"
            + "</p></details>"
        )
    return (
        '<section id="discovery"><h2>Exploratory observations</h2>'
        "<p>An agent chose these variations to find useful observations. These attempts "
        "are outside the fixed comparison; their counts are not benchmark rates.</p>"
        + "".join(attempts)
        + "</section>"
    )


def by_column(verdict: dict | None, columns: dict[str, str]) -> dict | None:
    """A verdict's winners named by column rather than position, or None where the
    judge gave no verdict."""
    if verdict is None:
        return None
    named = {**columns, "tie": "tie"}
    return {
        "status": verdict["status"],
        **{key: named[verdict[key]] for key in (*ASPECTS, "overall")},
        "margin": verdict["margin"],
        "defects": {columns[p]: verdict[f"defects_{p}"] for p in ("A", "B")},
        "reason": verdict["reason"],
    }


def pair_records(runs: tuple[Path, ...]) -> list[tuple[Path, dict]]:
    """Each saved pair's two presentation-order judgments from `eval run --judge pair`
    runs, with the results file holding them, once per Promptfoo repetition. A
    winner counts only where both completed orders name it."""
    pairs: dict[tuple, dict] = {}
    for run, result, recorded in judgments(runs, "pair"):
        test = result["testCase"]["metadata"]
        pair = pairs.setdefault(
            (run, test["subject"], test["pair"], result.get("repeatIndex", 0)),
            {"subject": test["subject"], "pair": test["pair"], "orders": {}},
        )
        pair["samples"] = {
            ref["column"]: ref["sample"]
            for ref in sorted(test["saved"], key=lambda ref: ref["column"])
        }
        pair["orders"][test["order"]] = by_column(
            recorded.get("metadata", {}).get("judge", {}).get("output"),
            {p: ref["column"] for p, ref in zip("AB", test["saved"], strict=True)},
        )
    records = []
    for (run, *_), pair in pairs.items():
        orders = [pair["orders"].get(order) for order in (1, 2)]
        complete = all(o and o["status"] == "complete" for o in orders)
        winners = {o["overall"] for o in orders if o}
        status = (
            "unscored"
            if not all(orders)
            else "insufficient_evidence"
            if not complete
            else "split"
            if len(winners) != 1
            else "tie"
            if winners == {"tie"}
            else "complete"
        )
        records.append(
            (
                run / "results.json",
                {
                    **pair,
                    "orders": orders,
                    "status": status,
                    "winner": winners.pop() if status == "complete" else None,
                },
            )
        )
    return records


def judge_preferences(
    page: Path,
    records: list[tuple[Path, dict]],
    found: dict,
    output_url: str | None,
) -> str:
    """Show native per-order format preferences."""
    categories = ["HTML clear", "HTML slight", "Tie", "Leaf slight", "Leaf clear"]
    points, rows = [], []
    html_uses = defaultdict(set)

    def participants(pair):
        result = {}
        for provider, identifier in pair["samples"].items():
            matches = [
                sample
                for sample in found.get(pair["subject"], {}).get(provider, [])
                if sample["sample"] == identifier
            ]
            conditions = {sample["diagnostics"].get("condition") for sample in matches}
            condition = next(iter(conditions)) if len(conditions) == 1 else None
            result[provider] = (condition, matches[0] if matches else None)
        return result

    for _, pair in records:
        for condition, sample in participants(pair).values():
            if condition == "html" and sample:
                html_uses[sample["work"].resolve()].add(
                    json.dumps(pair["samples"], sort_keys=True)
                )
    for source, pair in sorted(records, key=lambda record: record[1]["subject"]):
        subject = pair["subject"]
        members_by_column = participants(pair)
        conditions = [condition for condition, _ in members_by_column.values()]
        format_pair = len(conditions) == 2 and sorted(str(c) for c in conditions) == [
            "html",
            "leaf",
        ]
        samples_text = []
        for provider, identifier in pair["samples"].items():
            condition, sample = members_by_column[provider]
            name = {"html": "Plain HTML", "leaf": "Leaf"}.get(condition, provider)
            target = (
                f'<a href="#{sample_anchor(sample)}"><code>{escape(identifier)}</code></a>'
                if sample
                else f"<code>{escape(identifier)}</code>"
            )
            reused = (
                condition == "html"
                and sample
                and len(html_uses[sample["work"].resolve()]) > 1
            )
            samples_text.append(
                f"{escape(name)}: {target}" + (" (reused control)" if reused else "")
            )
        outcomes = []
        for number, order in enumerate(pair["orders"], 1):
            if not order or order["status"] != "complete":
                outcomes.append(
                    escape(order["status"].replace("_", " ") if order else "No verdict")
                )
                continue
            preferred = order["overall"]
            category = (
                "Tie"
                if preferred == "tie"
                else (
                    {"leaf": "Leaf", "html": "HTML"}[members_by_column[preferred][0]]
                    + " "
                    + order["margin"]
                    if format_pair
                    else preferred + " · " + order["margin"]
                )
            )
            outcomes.append(escape(category))
            if format_pair:
                points.append({"task": subject, "category": category, "order": number})
        rows.append(
            f'<tr><th scope="row">{escape(subject)}</th><td>{"<br>".join(samples_text)}</td>'
            + "".join(f"<td>{outcome}</td>" for outcome in outcomes)
            + f"<td>{linked_file(page, source, output_url, 'Native pair ' + str(pair['pair']))}</td></tr>"
        )
    chart = "<p>No completed Plain HTML/Leaf pair judgments are available to plot.</p>"
    if points:
        plotted_subjects = sorted({point["task"] for point in points})
        options = r"""({
          ariaLabel: "Overall Plain HTML versus Leaf preferences for both presentation orders, on five ordinal categories. Exact outcomes and sources follow in the table.",
          marginLeft: width < 650 ? 110 : 155, marginRight: 25,
          marginBottom: width < 650 ? 65 : 40,
          x: {type: "point", domain: $CATEGORIES, label: null,
            tickFormat: d => width < 650 ? d.replace(" ", "\n") : d},
          y: {type: "point", domain: $TASKS, label: null,
            tickFormat: d => d.replaceAll("-", width < 650 ? "\n" : " ")},
          marks: [
            Plot.ruleX(["Tie"], {stroke: "var(--rule)"}),
            Plot.dot($POINTS.filter(d => d.order === 1), {x: "category", y: "task", fill: "var(--series-1)", r: 5, dy: -5}),
            Plot.dot($POINTS.filter(d => d.order === 2), {x: "category", y: "task", fill: "var(--series-1)", r: 5, dy: 5})
          ]
        })"""
        values = {
            "CATEGORIES": categories,
            "TASKS": plotted_subjects,
            "POINTS": points,
        }
        options = Template(options).substitute(
            {key: json.dumps(value) for key, value in values.items()}
        )
        chart = f'<lf-chart id="format-preferences" data-height="{max(300, len(plotted_subjects) * 44 + 100)}"><pre>{escape(options)}</pre></lf-chart>'
    return (
        '<lf-tab id="judge-preferences" label="Judge preferences" group="Overview"><section id="preference-overview"><h2>Leaf and Plain HTML: judge preferences</h2>'
        '<p>The five categories are ordinal judgments, not continuous quality scores. Each dot is one completed presentation-order judgment; two orders are not two author replications. Only Plain HTML/Leaf pairs appear on this axis, and the comparisons are unordered. Absolute quality grades remain in the <a href="#scores">output index</a>.</p>'
        + chart
        + '<details open><summary>Exact native outcomes and sources</summary><table id="preference-outcomes"><thead><tr><th scope="col">Task</th><th scope="col">Saved samples</th><th scope="col">Order 1</th><th scope="col">Order 2</th><th scope="col">Source</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></details></section>"
        + "</lf-tab>"
    )


CITATION = "lf-eval-cite"


def citations(review: str) -> list[tuple[dict[str, str], slice]]:
    """Each of the review's citations in reading order: its attributes, an attribute
    written without a value reading as empty, and the review's text it occupies."""
    found = []
    for cite in turbohtml.parse_fragment(
        review, context="main", source_locations=True
    ).find_all(CITATION):
        if cite.text.strip() or cite.find(True):
            raise click.ClickException(
                f"A citation takes no content; close it with </{CITATION}>: {cite.html[:200]}"
            )
        location = cite.source_location
        assert location is not None
        end = location.end_tag or location.start_tag
        found.append(
            (
                {name: str(value or "") for name, value in cite.attrs.items()},
                slice(location.start_tag.start_offset, end.end_offset),
            )
        )
    return found


def citation_anchor(attributes: dict[str, str]) -> str:
    """A citation's own id, or one its attributes settle, so a regenerated report keeps
    its anchors. Citing the same thing twice needs an id, as any duplicate does."""
    return attributes.get("id") or (
        "cite-"
        + hashlib.sha256(json.dumps(attributes, sort_keys=True).encode()).hexdigest()[
            :12
        ]
    )


def cited_output(samples: dict, reference: str | None) -> tuple[dict, str]:
    """The sample and phase `RUN/SAMPLE[@PHASE]` names: the final phase unless it says
    which. A saved output the supplied runs don't hold stops the report, and one naming
    a phase its sample lacks says which it has."""
    run, _, name = (reference or "").rpartition("/")
    name, _, phase = name.partition("@")
    sample = samples.get((Path(run).name, name))
    if sample is None:
        raise click.ClickException(
            f"Citation names no saved output in the supplied runs: {reference}"
        )
    saved = sample["diagnostics"].get("phases", {})
    if phase and phase not in saved:
        raise click.ClickException(
            f"Citation names no saved phase: {reference}. It has: "
            + ", ".join(
                f"@{p} ({phase_label(sample, p)})"
                for p, _ in sorted(saved.items(), key=lambda item: int(item[0]))
            )
        )
    roles = (sample["diagnostics"].get("comparison") or {}).get("phases", {})
    return sample, phase or str(roles.get("", ""))


def cited_outputs(
    attributes: dict[str, str], samples: dict
) -> list[tuple[str, dict, str]]:
    """The label, sample and phase of each output a citation names. A label the
    review leaves out comes from what the saved output records."""
    sides = ("output",) if "output" in attributes else ("before", "after")
    chosen = {side: cited_output(samples, attributes.get(side)) for side in sides}
    names = {"html": "Plain HTML", "leaf": "Leaf"}
    conditions = {
        side: names.get(sample["diagnostics"].get("condition"))
        for side, (sample, _) in chosen.items()
    }
    named = len(sides) == 1 or set(conditions.values()) == set(names.values())
    outputs = []
    for side, (sample, phase) in chosen.items():
        kind = conditions[side] if named else side.capitalize()
        outputs.append(
            (
                attributes.get("label" if side == "output" else f"{side}-label")
                or f"{kind or 'Output'} · {phase_label(sample, phase)}",
                sample,
                phase,
            )
        )
    return outputs


def output_links(sample: dict, phase: str) -> str:
    """A cited phase's saved page, its place in the browser, and what it is: its
    condition, author model and phase."""
    author = sample["execution_metadata"]["author"]
    saved = sample["diagnostics"].get("phases", {}).get(phase, {}).get("page")
    role = phase_label(sample, phase) if saved else "No saved page"
    provenance = " · ".join(
        [
            {"html": "Plain HTML", "leaf": "Leaf"}.get(
                sample["diagnostics"].get("condition"), "Generated page"
            ),
            author["model"]
            or f"{author['harness']} · model unavailable in retained run",
            role,
        ]
    )
    details = sample_anchor(sample) + (f"-p{phase}" if saved else "")
    return (
        '<span class="capture-actions">'
        + sample.get("exports", {}).get(phase, "Saved output unavailable")
        + f'<a href="#{details}">{escape(f"{role} and details" if saved else "Attempt details")}</a></span>'
        + f'<small class="output-status">{escape(provenance)}</small>'
    )


def cite_outputs(page: Path, attributes: dict[str, str], samples: dict) -> str:
    """A cited output's captures at each recorded viewport, or a pair's side by side,
    or only its links where the review already shows what it needs."""
    outputs = cited_outputs(attributes, samples)
    anchor = escape(citation_anchor(attributes))
    if "links" in attributes:
        return (
            f'<span id="{anchor}">'
            + " · ".join(
                f"<strong>{escape(label)}</strong>: {output_links(sample, phase)}"
                for label, sample, phase in outputs
            )
            + "</span>"
        )
    screens = comparison_screens(
        page,
        anchor,
        [(label, sample) for label, sample, _ in outputs],
        [
            output_links(sample, phase) + capture_errors(sample, phase)
            for _, sample, phase in outputs
        ],
        aligned="aligned" in attributes,
        phases=[phase for _, _, phase in outputs],
    )
    return f'<div id="{anchor}">{screens}</div>'


def cite_file(page: Path, attributes: dict[str, str], output_url: str | None) -> str:
    """A retained file by what it is: an image in place, a patch in `lf-diff` beside its
    source link, and anything else a link, as is any file cited with `links`."""
    path = Path(attributes["file"])
    label = attributes.get("label", path.name)
    anchor = escape(citation_anchor(attributes))
    link = linked_file(page, path, output_url, label)
    image = MEDIA_TYPES.get(path.suffix.lower(), "").startswith("image/")
    if "links" in attributes or not (image or path.suffix == ".diff"):
        return f'<span id="{anchor}">{link}</span>'
    if image:
        return (
            f'<figure id="{anchor}"><figcaption>{escape(label)}</figcaption>'
            + shot(page, media_paths(page, [path])[path], label)
            + "</figure>"
        )
    # The widget owns parsing and per-file disclosure. Preserve every patch character,
    # including space-only context lines.
    patch = escape(path.read_text()).replace("\n ", "\n&#32;")
    return f'<p>{link}</p><lf-diff id="{anchor}" collapsed><pre>{patch}</pre></lf-diff>'


def resolved(page: Path, review: str, samples: dict, output_url: str | None) -> str:
    """The review with each citation replaced by the elements it names."""
    for attributes, place in reversed(citations(review)):
        markup = (
            cite_file(page, attributes, output_url)
            if "file" in attributes
            else cite_outputs(page, attributes, samples)
        )
        review = review[: place.start] + markup + review[place.stop :]
    return review


@click.command("report")
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
    help='Leaf markup of the campaign\'s review, with its saved outputs cited (evals/README.md, "Render a report").',
)
def eval_report(
    page: Path, runs: tuple[Path, ...], output_url: str | None, review: Path | None
):
    """Write PAGE, a Leaf page of the authored-task samples in RUNS.

    RUNS are run directories, such as those under `.tmp/eval/`, including any
    `eval run --from` runs that judged their samples. PAGE is created when absent, and its
    `index.html` is rewritten otherwise. Serve it with `leaf server start PAGE`.
    Serve PAGE/evidence with a static server and pass its URL as --output-url
    to open saved pages and raw evidence from the report. Without that URL the
    report names the exported files but does not claim they are reachable."""
    source = review.read_text() if review else UNREVIEWED
    heading = turbohtml.parse_fragment(source, context="main").find("h1")
    if heading is None:
        raise click.ClickException("The review needs an <h1>, the report's title.")
    packages = list(layer_packages(page)) if initialized(page) else []
    if any(name not in packages for name in REQUIRED_PACKAGES):
        leaf(
            "page",
            "init",
            str(page),
            *[
                argument
                for name in dict.fromkeys([*packages, *REQUIRED_PACKAGES])
                for argument in ("--package", name)
            ],
        )
    if len({run.name for run in runs}) < len(runs):
        raise click.ClickException("Each run directory needs a distinct name to cite.")
    found = run_samples(runs)
    samples = {
        (run.name, sample["sample"]): sample
        for columns in found.values()
        for members in columns.values()
        for sample in members
        for run in sample["runs"]
    }
    # The review owns the reader's sequence; input-file order carries no task meaning.
    # Reading every citation here also stops a report before its slow exports.
    task_order = {}
    for attributes, _ in citations(source):
        if "file" in attributes:
            if not Path(attributes["file"]).is_file():
                raise click.ClickException(
                    f"Citation names no file: {attributes['file']}"
                )
            continue
        outputs = cited_outputs(attributes, samples)
        for _, sample, _ in outputs:
            task_order.setdefault(sample["subject"], len(task_order))
            if "links" not in attributes:
                sample.setdefault("citations", []).append(
                    (
                        citation_anchor(attributes),
                        " and ".join(label for label, _, _ in outputs),
                    )
                )
    found = dict(
        sorted(
            found.items(),
            key=lambda item: (
                task_order.get(item[0], len(task_order)),
                task_title(item[1]).casefold(),
                item[0],
            ),
        )
    )
    records = pair_records(runs)
    pairs = [pair for _, pair in records]
    discovery = discovery_section(page, runs, output_url, found)
    runs_text = (
        "<ul>"
        + "".join(
            f"<li>{escape(run.name)}: "
            + linked_file(page, run / "results.json", output_url, "Results")
            + "</li>"
            for run in runs
        )
        + "</ul>"
    )
    count = sum(
        len(members) for columns in found.values() for members in columns.values()
    )
    # Each task's section exports its saved pages, which the review's citations link.
    browser = (
        '<lf-tabs id="report-views" data-width="available">'
        + (judge_preferences(page, records, found, output_url) if records else "")
        + '<lf-tab id="scores" label="Output index" group="Overview">'
        + f'<p class="report-meta">{len(found)} cases · {count} saved result records</p>'
        + overview(found)
        + f"<details><summary>Runs and score definitions</summary>{runs_text}"
        "<p>Checks are execution assertions. Quality shows recorded live, visual or text rubric "
        "judgments; the grading reasons identify their scope. It is not the aggregate assertion score. "
        "Pairwise preferences and exploratory observations "
        "are shown separately. Author time sums recorded phases; unavailable is not zero.</p></details></lf-tab>"
        + "".join(
            f'<lf-tab id="{task_anchor(subject)}-view" label="{escape(task_title(columns))}" group="Saved outputs">'
            + task_section(page, subject, columns, pairs, output_url)
            + "</lf-tab>"
            for subject, columns in found.items()
        )
        + (
            f'<lf-tab id="observations" label="Exploration" group="Further evidence">{discovery}</lf-tab>'
            if discovery
            else ""
        )
        + "</lf-tabs>"
    )
    written = resolved(page, source, samples, output_url)
    fragment = turbohtml.parse_fragment(written, context="main", source_locations=True)
    # What stands before the review's tab set is its title and lede, the page's
    # header. The browser is the set's last tab, or follows a review that has none.
    views = fragment.select_one(":scope > lf-tabs")
    at = end = len(written)
    if views:
        assert views.source_location
        at = views.source_location.start_tag.start_offset
        close = views.source_location.end_tag
        end = close.start_offset if close else end
        browser = f'<lf-tab id="all-results" label="Outputs">{browser}</lf-tab>'
    (page / "index.html").write_text(
        gallery.page(
            heading.text,
            "Saved authored pages side by side, with their original review conditions,"
            " costs and judgments.",
            f"<header>{written[:at]}</header>\n"
            f"{written[at:end]}{browser}{written[end:]}",
            head=f"<style>{STYLE}</style>",
            layout="layout-workspace density-working",
        )
    )
    click.echo(page / "index.html")
    click.echo(f"Saved outputs: {page / 'evidence'}")
