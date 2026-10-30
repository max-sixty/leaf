"""Render Promptfoo runs as one Leaf browser of scores, judgments and outputs.

Every native result remains visible, including single arms, unequal repetitions and
failed attempts. Identical native results appear once, with every source-run alias
retained; changed grades remain distinct. Execution checks, authoring grades, pairwise
preferences and exploratory observations retain their distinct meanings. An optional authored review names the
latest run group and experiment decisions; scores never infer either. Requests,
viewports and phases come from retained results, never today's catalog.
The assessment also supplies the current implementation summary and changes selected
for personal review. Native preferences remain per-order ordinal judgments; explicit
checkpoints label their sequence, while authored repair observations stay separate.
An optional journey separates each case's task, generated outputs and the report
author's assessment. Experiments appear in authored order; only explicitly selected
changes create review obligations.

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
from PIL import Image

from leaf.registry.storage import layer_packages
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
#review-views > lf-tab:not([hidden]) { padding-block-start: 0; }
.result-list { margin-block: .5rem; }
.result-list > div { display: flex; justify-content: space-between; gap: 1rem; padding-block: .35rem; border-bottom: 1px solid var(--border-2); }
.result-list dt { font-weight: 500; }
.result-list dd { margin: 0; text-align: right; }
.report-metadata { overflow-wrap: anywhere; }
.report-metadata dl { display: grid; grid-template-columns: auto 1fr; gap: .35rem 1.5rem; }
.report-metadata dd { margin: 0; }
.output-status { color: var(--muted); font-size: .875rem; }
.report-meta { color: var(--muted); font-size: .875rem; }
.journey-lane { margin-block: var(--sp-5); }
.journey-lane > p, .journey-steps > li > p, #report-introduction > section { max-width: 82ch; }
.journey-outputs { margin-block: var(--sp-3); }
.journey-outputs figure { margin: 0; }
.journey-steps { list-style: none; padding-inline-start: var(--sp-4); border-inline-start: 2px solid var(--rule); }
.journey-steps > li { margin-block: var(--sp-4); }
.journey-steps h4 { margin-block: 0 var(--sp-2); }
.journey-links { display: flex; flex-wrap: wrap; gap: var(--sp-2) var(--sp-4); }
.report-kind { font-family: var(--sans); font-size: .75rem; color: var(--muted); margin-block: 0 .5rem; }
.generated-output { border: 1px solid var(--rule); padding: var(--sp-3); }
.report-assessment { border-block-start: 1px solid var(--rule); padding-block-start: var(--sp-3); margin-block: var(--sp-3); }
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


def execution_status(response: dict) -> str:
    """Read native completion before interpreting checks on its authored output."""
    metadata = response.get("metadata") or {}
    checks = metadata.get("checks") or {}
    if (
        checks.get("completed") is False
        or (metadata.get("trace") or {}).get("completed") is False
    ):
        return "incomplete"
    if response.get("error"):
        return "error"
    if checks.get("page") is False or not response.get("output"):
        return "empty"
    return "complete"


def report_samples(runs: tuple[Path, ...]) -> dict:
    """Read every Promptfoo result, including failed attempts with no saved page."""
    found = defaultdict(lambda: defaultdict(list))
    retained: dict[str, dict] = {}
    for run in runs:
        results = json.loads((run / "results.json").read_text())["results"]["results"]
        for index, result in enumerate(results):
            # A copied native result is reusable; a revised grade is a new record.
            identity = hashlib.sha256(
                json.dumps(result, sort_keys=True).encode()
            ).hexdigest()
            if identity in retained:
                retained[identity]["runs"].append(run)
                continue
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
            sample = {
                "result_id": result["id"],
                "identity": identity,
                "sample": work.name,
                "subject": subject,
                "title": result.get("testCase", {}).get("description") or subject,
                "work": work,
                "diagnostics": diagnostics,
                "checks": metadata.get("checks") or {},
                "assertions": result.get("testCase", {}).get("assert", []),
                "execution": execution_status(response),
                "execution_error": response.get("error"),
                "shots": run / "screenshots" / work.name,
                "runs": [run],
                "gradingResult": result.get("gradingResult"),
                "error": result.get("error")
                or response.get("error")
                or (result.get("gradingResult") or {}).get("reason"),
            }
            retained[identity] = sample
            found[subject][result["provider"]["label"]].append(sample)
    for columns in found.values():
        for members in columns.values():
            for number, sample in enumerate(members, 1):
                sample["attempt"] = number
    return found


def task_anchor(subject: str) -> str:
    return "task-" + hashlib.sha256(subject.encode()).hexdigest()[:12]


def task_title(columns: dict) -> str:
    """Name the saved case and its run scope; ids still own grouping."""
    title = next(iter(columns.values()))[0]["title"]
    title = title[:1].upper() + title[1:]
    groups = {
        sample.get("run_group") for members in columns.values() for sample in members
    }
    if len(groups) == 1 and (group := next(iter(groups))):
        return f"{group} · {title}"
    return title


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
    if not paths:
        return f'<figure id="{anchor}">{heading}<p>No screens.</p></figure>'
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
        f'<figure id="{anchor}">{heading}'
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
    phases: list[str] | None = None,
) -> str:
    """Compare selected revisions at equal recorded viewport dimensions; default final."""
    captures = []
    for index, (label, sample) in enumerate(columns):
        comparison = sample["diagnostics"].get("comparison")
        if not comparison:
            return "<p>No saved comparison captures are available.</p>"
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
        tabs.append((f"{anchor}-{name}", name.capitalize(), contents))
    return (
        '<div class="report-flat-tabs">'
        + tab_group(f"{anchor}-widths", tabs)
        + "</div>"
    )


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
            "Recorded presentation orders appear above; an unscored order supplies no preference."
            if pair
            else "This pair has no repeated comparison judgment; any experiment assessment is under Changes to Leaf."
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
    return f"Revision {phase}"


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
        return (
            "Comparison only"
            if sample.get("comparisons")
            else "No individual assessment"
        )
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
                    f'<td data-label="Version">{escape(labels[column])}<small>Output {sample["attempt"]} · {escape(sample.get("run_group", ""))}</small></td>'
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
        for name, reason in sample["diagnostics"]["phases"][phase]
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
        "<details><summary>Checks and recorded reviews</summary>"
        "<h4>Execution and page checks</h4>"
        "<p>These checks establish execution and page validity.</p>"
        + result_list(check_results(sample))
        + (
            f"<p>{escape(sample['review_context'])}</p>"
            if sample.get("review_context")
            else ""
        )
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
        sources.append(f"<li>Revision {escape(phase)}: {source}</li>")
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
                f'<section id="{anchor}-p{phase}"><h3>{role} · revision {phase}</h3>'
                f"{content}</section>"
            )
        else:
            role = phase_label(sample, phase)
            title = f"Revision {phase}"
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
    execution = (
        f'<p class="output-status">{escape(grade_summary(sample))}.</p>'
        if quality_unavailable(sample)
        else ""
    )
    if sample["execution_error"]:
        execution += f"<p><strong>Execution error:</strong> {escape(sample['execution_error'])}</p>"
    return (
        f'<section id="{anchor}">'
        f'<p class="output-status">{escape(label)} · {escape(sample.get("run_group", ""))}</p>'
        f"{execution}"
        f"{phases_view}"
        f"{checks}"
        f'<details class="report-metadata"><summary>Request, sources and run details</summary>'
        "<p>Saved pages preserve the reviewed state and support local navigation. "
        "Leaf actions that record edits or decisions require a live page. "
        "No agent is connected to these copies.</p>"
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


def sample_for(samples: dict, reference: dict) -> dict:
    identity = (Path(reference["run"]).resolve(), reference["sample"])
    if identity not in samples:
        raise click.ClickException(
            f"Review sample not in supplied runs: {identity[0]} / {identity[1]}"
        )
    return samples[identity]


def reference_phase(sample: dict, reference: dict) -> str:
    roles = (sample["diagnostics"].get("comparison") or {}).get("phases", {})
    phase = str(reference.get("phase", roles.get("", "")))
    if "phase" in reference and phase not in sample["diagnostics"].get("phases", {}):
        raise click.ClickException(
            f"Review revision not in saved sample: {sample['sample']} / {phase}"
        )
    return phase


def journey_outputs(page: Path, step: dict, samples: dict) -> str:
    """Keep each output's captures and saved-page link on its authored revision."""
    selected = [
        (reference, sample_for(samples, reference))
        for reference in step.get("outputs", [])
    ]
    sizes = [
        list(map(tuple, sample["diagnostics"]["comparison"]["widths"].values()))
        for _, sample in selected
    ]
    common = (
        next(
            (size for size in sizes[0] if all(size in other for other in sizes[1:])),
            None,
        )
        if sizes
        else None
    )
    outputs = []
    for index, (reference, sample) in enumerate(selected, 1):
        phase = reference_phase(sample, reference)
        saved = bool(sample["diagnostics"]["phases"][phase].get("page"))
        details = sample_anchor(sample) + (f"-p{phase}" if saved else "")
        details_label = (
            f"{phase_label(sample, phase)} and details" if saved else "Attempt details"
        )
        condition = {"html": "HTML control", "leaf": "Leaf"}.get(
            sample["diagnostics"].get("condition"), "Generated page"
        )
        model = reference.get("model") or (
            f"{sample['diagnostics'].get('harness', 'Author')} · model not recorded"
        )
        provenance = f"{condition} · {model} · {phase_label(sample, phase) if saved else 'No saved page'}"
        anchor = f"{step['id']}-output-{index}"
        captures = screens(page, sample, phase)
        widths = sample["diagnostics"]["comparison"]["widths"]
        views = []
        for name, (width, height) in sorted(
            widths.items(), key=lambda item: tuple(item[1]) != common
        ):
            label = f"{width} × {height}"
            figure = column_figure(
                page,
                f"{anchor}-{name}",
                label,
                captures[name],
                f"{width} × {height}",
            )
            views.append(
                figure
                if not views
                else f"<details><summary>{escape(label)}</summary>{figure}</details>"
            )
        outputs.append(
            f'<section id="{anchor}" class="generated-output"><p class="report-kind">{"Generated output" if saved else "Author attempt"}</p>'
            f'<h5>{escape(reference["label"])}</h5><p class="report-meta">{escape(provenance)}</p>'
            '<p class="sample-links">'
            + sample.get("exports", {}).get(phase, "Saved output unavailable")
            + f'<a href="#{details}">{escape(details_label)}</a></p>'
            + capture_errors(sample, phase)
            + ("".join(views) or "<p>No screenshots recorded.</p>")
            + "</section>"
        )
    return (
        f'<div class="pair-shots journey-outputs">{"".join(outputs)}</div>'
        if outputs
        else ""
    )


def journey_view(page: Path, lanes: list[dict], samples: dict) -> str:
    """Render each attempt beside its retained outputs, then link supporting decisions."""
    if not lanes:
        return ""
    sections = []
    for lane in lanes:
        steps = "".join(
            f'<li id="{escape(step["id"])}">'
            + f'<p class="report-kind">{"Author attempt" if step.get("outputs") else "Supporting observation"}</p>'
            + f"<h4>{escape(step['title'])}</h4>"
            + journey_outputs(page, step, samples)
            + f'<aside id="{escape(step["id"])}-assessment" class="report-assessment">'
            + f'<p class="report-kind">Assessment · {escape(step.get("assessment_by", "Report author"))}</p>'
            + f"<p>{escape(step['body'])}</p>"
            + '<p class="journey-links">'
            + "".join(
                f'<a href="{escape(link["target"])}">{escape(link["label"])}</a>'
                for link in step["links"]
            )
            + "</p></aside></li>"
            for step in lane["steps"]
        )
        sections.append(
            f'<section id="{escape(lane["id"])}" class="journey-lane">'
            '<p class="report-kind">Case · Task given to the author</p>'
            f"<h3>{escape(lane['title'])}</h3><p>{escape(lane['summary'])}</p>"
            f'<ol class="journey-steps">{steps}</ol></section>'
        )
    return (
        '<lf-tab id="run-story" label="Cases" group="Overview"><h2>Cases and generated outputs</h2>'
        '<nav aria-label="Journey sections"><ul>'
        + "".join(
            f'<li><a href="#{escape(lane["id"])}">{escape(lane["title"])}</a></li>'
            for lane in lanes
        )
        + "</ul></nav>"
        + "".join(sections)
        + "</lf-tab>"
    )


def pair_records(runs: tuple[Path, ...]) -> list[tuple[Path, dict]]:
    """Read native judgments once, retaining a source for each distinct record."""
    records = {}
    for run in runs:
        source = run / "pairs.json"
        if source.exists():
            for pair in json.loads(source.read_text()):
                records.setdefault(json.dumps(pair, sort_keys=True), (source, pair))
    return list(records.values())


def judge_preferences(
    page: Path,
    records: list[tuple[Path, dict]],
    found: dict,
    review: dict | None,
    output_url: str | None,
) -> str:
    """Show native per-order format preferences and separately authored repair outcomes."""
    categories = ["HTML clear", "HTML slight", "Tie", "Leaf slight", "Leaf clear"]
    checkpoints = (review or {}).get("preference_checkpoints", [])
    groups = []
    selected = []
    for checkpoint in checkpoints:
        members = []
        for reference in checkpoint["pairs"]:
            source = Path(reference["run"]) / "pairs.json"
            matches = [
                pair
                for pair in json.loads(source.read_text())
                if pair["subject"] == reference["subject"]
                and pair["pair"] == reference["pair"]
            ]
            if len(matches) != 1 or not any(matches[0] == pair for _, pair in records):
                raise click.ClickException(
                    f"Pair reference must identify one loaded native judgment: {reference}"
                )
            members.append((source, matches[0]))
            selected.append(matches[0])
        groups.append((checkpoint["label"], members))
    unassigned = [(source, pair) for source, pair in records if pair not in selected]
    if unassigned:
        groups.append(
            (
                "No checkpoint assigned" if checkpoints else "Unordered comparisons",
                unassigned,
            )
        )
    subjects = sorted({pair["subject"] for _, pair in records})
    labels = [label for label, _ in groups]
    symbols = ["circle", "diamond", "square", "triangle", "cross", "star", "wye"]
    glyphs = ["●", "◆", "■", "▲", "+", "★", "Y"]
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
    for subject in subjects:
        for label, members in groups:
            matches = [
                (source, pair) for source, pair in members if pair["subject"] == subject
            ]
            if not matches and checkpoints:
                rows.append(
                    f'<tr><th scope="row">{escape(subject)}</th><td>{escape(label)}</td><td>—</td><td colspan="2">Not compared at this checkpoint</td><td>—</td></tr>'
                )
            for source, pair in matches:
                members_by_column = participants(pair)
                conditions = [condition for condition, _ in members_by_column.values()]
                format_pair = len(conditions) == 2 and sorted(
                    str(c) for c in conditions
                ) == ["html", "leaf"]
                samples_text = []
                for provider, identifier in pair["samples"].items():
                    condition, sample = members_by_column[provider]
                    name = {"html": "Plain HTML", "leaf": "Leaf"}.get(
                        condition, provider
                    )
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
                        f"{escape(name)}: {target}"
                        + (" (reused control)" if reused else "")
                    )
                outcomes = []
                for number, order in enumerate(pair["orders"], 1):
                    if not order or order["status"] != "complete":
                        outcomes.append(
                            escape(
                                order["status"].replace("_", " ")
                                if order
                                else "No verdict"
                            )
                        )
                        continue
                    preferred = order["overall"]
                    category = (
                        "Tie"
                        if preferred == "tie"
                        else (
                            {"leaf": "Leaf", "html": "HTML"}[
                                members_by_column[preferred][0]
                            ]
                            + " "
                            + order["margin"]
                            if format_pair
                            else preferred + " · " + order["margin"]
                        )
                    )
                    outcomes.append(escape(category))
                    if format_pair:
                        points.append(
                            {
                                "task": subject,
                                "checkpoint": label,
                                "category": category,
                                "order": number,
                            }
                        )
                rows.append(
                    f'<tr><th scope="row">{escape(subject)}</th><td>{escape(label)}</td><td>{"<br>".join(samples_text)}</td>'
                    + "".join(f"<td>{outcome}</td>" for outcome in outcomes)
                    + f"<td>{linked_file(page, source, output_url, 'Native pair ' + str(pair['pair']))}</td></tr>"
                )
    chart = "<p>No completed Plain HTML/Leaf pair judgments are available to plot.</p>"
    if points:
        options = r"""({
          ariaLabel: "Overall Plain HTML versus Leaf preferences for both presentation orders, on five ordinal categories. Exact outcomes and sources follow in the table.",
          marginLeft: width < 650 ? 110 : 155, marginRight: 25,
          marginBottom: width < 650 ? 65 : 40,
          x: {type: "point", domain: $CATEGORIES, label: null,
            tickFormat: d => width < 650 ? d.replace(" ", "\n") : d},
          y: {type: "point", domain: $TASKS, label: null,
            tickFormat: d => d.replaceAll("-", width < 650 ? "\n" : " ")},
          color: {domain: $LABELS, range: $COLORS},
          symbol: {domain: $LABELS, range: $SYMBOLS},
          marks: [
            Plot.ruleX(["Tie"], {stroke: "var(--rule)"}),
            Plot.dot($POINTS.filter(d => d.order === 1), {x: "category", y: "task", symbol: "checkpoint", fill: "checkpoint", r: 5, dy: -5}),
            Plot.dot($POINTS.filter(d => d.order === 2), {x: "category", y: "task", symbol: "checkpoint", fill: "checkpoint", r: 5, dy: 5})
          ]
        })"""
        values = {
            "CATEGORIES": categories,
            "TASKS": subjects,
            "LABELS": labels,
            "COLORS": [f"var(--series-{i % 5 + 1})" for i in range(len(labels))],
            "SYMBOLS": [symbols[i % len(symbols)] for i in range(len(labels))],
            "POINTS": points,
        }
        options = Template(options).substitute(
            {key: json.dumps(value) for key, value in values.items()}
        )
        legend = " · ".join(
            f"{glyphs[i % len(glyphs)]} {escape(label)}"
            for i, label in enumerate(labels)
        )
        chart = f'<p>{legend}</p><lf-chart id="format-preferences" data-height="{max(300, len(subjects) * 44 + 100)}"><pre>{escape(options)}</pre></lf-chart>'
    repairs = (review or {}).get("repair_comparisons", [])
    repair_table = ""
    if repairs:
        repair_rows = "".join(
            f'<tr id="repair-{escape(item["id"])}"><th scope="row">{escape(item["title"])}</th><td>{escape(item["before"])}</td><td>{escape(item["after"])}</td><td>'
            + " · ".join(
                linked_file(page, Path(path), output_url, f"Evidence {i}")
                for i, path in enumerate(item["evidence"], 1)
            )
            + "</td></tr>"
            for item in repairs
        )
        repair_table = (
            '<section id="repair-outcomes"><h3>Same-source implementation comparisons</h3><p>These report-author observations compare the same page before and after a change to Leaf. They are separate from format preferences and carry no numeric score.</p><table><thead><tr><th scope="col">Change</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Evidence</th></tr></thead><tbody>'
            + repair_rows
            + "</tbody></table></section>"
        )
    return (
        '<lf-tab id="judge-preferences" label="Judge preferences" group="Overview"><section id="preference-overview"><h2>Leaf and Plain HTML: judge preferences</h2>'
        '<p>The five categories are ordinal judgments, not continuous quality scores. Each dot is one completed presentation-order judgment; two orders are not two author replications. Only Plain HTML/Leaf pairs appear on this axis. Absolute quality grades remain in the <a href="#scores">output index</a>.</p>'
        + (
            f"<p>{escape(review['preference_summary'])}</p>"
            if review is not None and review.get("preference_summary")
            else ""
        )
        + (
            "<p>Checkpoint labels and their order come from the assessment. Missing comparisons are explicit below. Different author samples and reused controls do not establish the effect of a change to Leaf.</p>"
            if checkpoints
            else "<p>No checkpoints were supplied. These are unordered retained comparisons.</p>"
        )
        + chart
        + '<details open><summary>Exact native outcomes and sources</summary><table id="preference-outcomes"><thead><tr><th scope="col">Task</th><th scope="col">Checkpoint</th><th scope="col">Saved samples</th><th scope="col">Order 1</th><th scope="col">Order 2</th><th scope="col">Source</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></details></section>"
        + repair_table
        + "</lf-tab>"
    )


def implementation_summary(
    page: Path, implementation: dict | None, output_url: str | None
) -> str:
    """Present the author's implementation assessment and personal-review selection."""
    if implementation is None:
        return ""
    review = implementation["human_review"]
    changes = []
    for change in review["changes"]:
        evidence = []
        for number, name in enumerate(change["evidence"], 1):
            path = Path(name)
            evidence.append(linked_file(page, path, output_url, path.name))
            if path.suffix == ".diff" and path.is_file():
                # The inline widget owns parsing and per-file disclosure. Preserve
                # every patch character, including space-only context lines.
                patch = escape(path.read_text()).replace("\n ", "\n&#32;")
                evidence.append(
                    f'<lf-diff id="human-review-{escape(change["id"])}-diff-{number}" collapsed><pre>{patch}</pre></lf-diff>'
                )
        links = " · ".join(
            f'<a href="{escape(link["target"])}">{escape(link["label"])}</a>'
            for link in change.get("links", [])
        )
        changes.append(
            f'<section id="human-review-{escape(change["id"])}">'
            f"<h4>{escape(change['title'])}</h4>"
            f"<p><strong>Before.</strong> {escape(change['before'])}</p>"
            f"<p><strong>After.</strong> {escape(change['after'])}</p>"
            f"<p><strong>Why review it.</strong> {escape(change['reason'])}</p>"
            + (f'<p class="sample-links">{links}</p>' if links else "")
            + "".join(evidence)
            + "</section>"
        )
    return (
        '<section id="implementation-summary"><h2>What the current code changes</h2>'
        + "".join(f"<p>{escape(text)}</p>" for text in implementation["summary"])
        + '<section id="human-review"><h3>For your review</h3>'
        + (
            "<p>No material changes selected for personal review.</p>"
            if not changes
            else ""
        )
        + f"<p>{escape(review['summary'])}</p>"
        + "".join(changes)
        + "</section>"
        + f"<h3>Weaknesses</h3><p>{escape(implementation['weaknesses'])}</p>"
        + f"<h3>What merging would leave undone</h3><p>{escape(implementation['remaining'])}</p>"
        + "</section>"
    )


def report_introduction(found: dict, latest: str) -> str:
    """Keep the opening to the result, with evidence in the views it describes."""
    count = sum(
        len(members) for columns in found.values() for members in columns.values()
    )
    return (
        '<lf-tab id="report-introduction" label="Introduction">'
        + latest
        + f'<p class="report-meta">{len(found)} cases · {count} saved result records</p>'
        + '<p class="sample-links"><a href="#changes-tested">Review changes to Leaf</a>'
        ' · <a href="#all-results">Inspect cases and outputs</a></p></lf-tab>'
    )


def review_sections(
    page: Path, review: dict, samples: dict, output_url: str | None
) -> tuple[str, str]:
    """Render the agent's explicit experiment assessment beside its retained evidence."""

    def output_link(sample: dict, label: str = "", phase: str | None = None) -> str:
        selected = (
            phase
            if phase is not None
            else str(
                sample["diagnostics"]
                .get("comparison", {})
                .get("phases", {})
                .get("", "")
            )
        )
        return (
            (f"<strong>{escape(label)}</strong>: " if label else "")
            + '<span class="capture-actions">'
            + sample.get("exports", {}).get(selected, "Saved output unavailable")
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
                    + shot(page, added[Path(value)], Path(value).stem)
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
    findings = []
    for finding in latest["findings"]:
        sample = sample_for(samples, finding)
        if not latest_runs.intersection(run.resolve() for run in sample["runs"]):
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
                sample_for(samples, comparison["before"]),
                sample_for(samples, comparison["after"]),
            )
            reference_comparison = {
                before["diagnostics"].get("condition"),
                after["diagnostics"].get("condition"),
            } == {"html", "leaf"}
            phases = []
            labels = []
            for side, sample in (("before", before), ("after", after)):
                phase = reference_phase(sample, comparison[side])
                phases.append(phase)
                role = phase_label(sample, phase)
                condition = {"html": "Plain HTML", "leaf": "Leaf"}.get(
                    sample["diagnostics"].get("condition")
                )
                labels.append(
                    f"{condition if reference_comparison else side.capitalize()} · {role}"
                )
            comparisons.append(
                (
                    f"{anchor}-comparison-{index}",
                    comparison.get("label", comparison["title"]),
                    (
                        '<p class="comparison-summary"><strong>Reference evidence:</strong> '
                        "Plain HTML compared with Leaf.</p>"
                        if reference_comparison
                        else ""
                    )
                    + (
                        f'<p class="comparison-summary">{escape(comparison["summary"])}</p>'
                        if comparison.get("summary")
                        else ""
                    )
                    + comparison_screens(
                        page,
                        f"{anchor}-comparison-{index}",
                        [
                            (labels[0], before),
                            (labels[1], after),
                        ],
                        [
                            output_link(before, phase=phases[0]),
                            output_link(after, phase=phases[1]),
                        ],
                        before_after=not reference_comparison,
                        phases=phases,
                    )
                    + f"<p>{escape(comparison['finding'])}</p>"
                    + evidence_links(
                        comparison["evidence"],
                        f"{anchor}-comparison-{index}-evidence",
                        "Judgment record",
                    ),
                )
            )
        comparisons_view = (
            '<div class="report-flat-tabs">'
            + tab_group(f"{anchor}-comparisons", comparisons)
            + "</div>"
            if comparisons
            else ""
        )
        selected = experiment.get("review", False)
        kind = experiment.get("kind", "Experiment")
        content = (
            '<header class="experiment-heading">'
            f'<p class="report-kind">{escape(kind)}</p>'
            f"<h2>{escape(experiment['title'])}</h2>"
            f'<p class="experiment-recommendation"><span>Recommendation:</span> <strong>{escape(experiment["recommendation"])}</strong></p></header>'
            f'<p class="experiment-change">{escape(experiment["change"])}</p>'
            + comparisons_view
            + evidence_links(
                experiment["evidence"], f"{anchor}-evidence", "Change sources"
            )
            + (
                f'<lf-options id="{anchor}-approval" choose>'
                f'<lf-option id="{anchor}-approve" value="approved"><strong>Approve change</strong></lf-option>'
                f'<lf-option id="{anchor}-revisit" value="revisit"><strong>Revisit change</strong></lf-option>'
                "</lf-options>"
                if selected
                else ""
            )
            + f'<aside id="{anchor}-assessment" class="report-assessment"><p class="report-kind">Assessment · Report author</p>'
            + f"<p>{escape(experiment['reason'])}</p></aside>"
            + f"<details><summary>Scope and limitations</summary><p>{escape(experiment['period'])}</p><p>{escape(experiment['limits'])}</p></details>"
        )
        if selected:
            content = f'<lf-ask id="{anchor}-question">{content}</lf-ask>'
        experiments.append(
            f'<lf-tab id="{anchor}" label="{escape(experiment.get("label", experiment["title"]))}" summary="{escape(experiment["recommendation"])}">'
            + content
            + "</lf-tab>"
        )
    implementation = implementation_summary(
        page, review.get("implementation"), output_url
    )
    return (
        '<lf-tab id="changes-tested" label="Changes to Leaf">'
        + (
            '<lf-tabs id="experiments" data-width="available">'
            + "".join(experiments)
            + "</lf-tabs>"
            if experiments
            else "<p>No experiments recorded.</p>"
        )
        + (
            '<details id="implementation-record"><summary>Implementation and validation record</summary>'
            + implementation
            + "</details>"
            if implementation
            else ""
        )
        + "</lf-tab>",
        f'<section id="latest-run"><h2>{escape(latest["title"])}</h2>'
        + f"<p>{escape(latest['summary'])}</p>"
        + f"<details><summary>Review findings</summary><ul>{''.join(findings)}</ul></details>"
        + "</section>",
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
    help="JSON assessment of run groups, tested changes, current implementation and personal-review guidance.",
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
    packages = list(layer_packages(page)) if (page / "events.jsonl").exists() else []
    if "diff" not in packages:
        leaf(
            "page",
            "init",
            str(page),
            *[
                argument
                for name in [*packages, "diff"]
                for argument in ("--package", name)
            ],
        )
    found = report_samples(runs)
    assessment = json.loads(review.read_text()) if review else None
    # The story owns the reader's sequence; input-file order carries no task meaning.
    subjects_by_sample = {
        (run.resolve(), sample["sample"]): subject
        for subject, columns in found.items()
        for members in columns.values()
        for sample in members
        for run in sample["runs"]
    }
    task_order = {}
    for lane in (assessment or {}).get("journey", []):
        for step in lane["steps"]:
            for reference in step.get("outputs", []):
                subject = subjects_by_sample[
                    Path(reference["run"]).resolve(), reference["sample"]
                ]
                task_order.setdefault(subject, len(task_order))
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
                    sample["review_context"] = assessment.get("review_context", "")
                    sample["comparisons"] = list(
                        dict.fromkeys(
                            link
                            for run in sample["runs"]
                            for link in comparison_links[
                                run.resolve(), sample["sample"]
                            ]
                        )
                    )
                    sample["run_group"] = (
                        "Latest run"
                        if latest_runs.intersection(
                            run.resolve() for run in sample["runs"]
                        )
                        else "Reference output"
                    )
    records = pair_records(runs)
    pairs = [pair for _, pair in records]
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
    task_views = "".join(
        f'<lf-tab id="{task_anchor(subject)}-view" label="{escape(task_title(columns))}" group="Saved outputs">'
        + task_section(page, subject, columns, pairs, output_url)
        + "</lf-tab>"
        for subject, columns in found.items()
    )
    samples = {
        (run.resolve(), sample["sample"]): sample
        for columns in found.values()
        for members in columns.values()
        for sample in members
        for run in sample["runs"]
    }
    changes, introduction = (
        review_sections(page, assessment, samples, output_url)
        if assessment
        else ("", "")
    )
    story = (
        journey_view(page, assessment.get("journey", []), samples) if assessment else ""
    )
    index_label = "Output index" if story else "Overview"
    body = (
        '<lf-tabs id="report-views" data-width="available">'
        + story
        + judge_preferences(page, records, found, assessment, output_url)
        + f'<lf-tab id="scores" label="{index_label}" group="Overview">'
        + overview(found)
        + f"<details><summary>Runs and score definitions</summary>{runs_text}"
        "<p>Checks are execution assertions. Quality shows recorded live, visual or text rubric "
        "judgments; the grading reasons identify their scope. It is not the aggregate assertion score. "
        "Pairwise preferences and exploratory observations "
        "are shown separately. Author time sums recorded phases; unavailable is not zero.</p></details></lf-tab>"
        + task_views
        + (
            f'<lf-tab id="observations" label="Exploration" group="Further evidence">{discovery}</lf-tab>'
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
            + report_introduction(found, introduction)
            + f'<lf-tab id="all-results" label="Cases &amp; outputs">{body}</lf-tab>'
            + changes
            + "</lf-tabs>"
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
