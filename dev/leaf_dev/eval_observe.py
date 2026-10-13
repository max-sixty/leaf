"""Reobserve saved authored versions into a fresh run without reauthoring them.

The original request, user messages, authored bytes and vendored browser runtime
stay fixed. Only observation changes: the shared collector serves disposable copies
through an explicitly identified server payload. New run metadata points to the
original sample and new captures, so eval-score, eval-pairs and eval-report consume
the same canonical evidence path. No model runs during this browser batch.
"""

import copy
import json
import sys
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arrangement_eval import Run, capture_phase
from leaf_dev.authoring_score import digest, sample_inputs, write_json
from leaf_dev.eval_provenance import files_identity, runtime_identity, tree_identity


def observe_sample(
    metadata: dict,
    source_run: Path,
    output: Path,
    payload: Path,
    phase: int | None,
    destinations: tuple[str, ...],
) -> dict:
    """Replace observation metadata only; never substitute current task inputs."""
    inputs = sample_inputs(metadata, source_run, phase)
    selected = inputs["phase"]
    work = Path(metadata["work"])
    page = work / f"page-phase{selected}"
    if not (page / "index.html").is_file():
        raise click.ClickException(f"Saved authored version is missing: {page}")
    recorded_targets = [
        state["action"]["target"]
        for width in (inputs["observations"] or {}).get("widths", {}).values()
        for state in width["states"]
        if state["action"].get("type") == "destination"
    ]
    targets = tuple(dict.fromkeys((*recorded_targets, *destinations)))
    observation = Run(
        subject=metadata["diagnostics"]["subject"],
        payload=payload,
        directory=work,
        shots=output / "screenshots" / work.name,
        condition="leaf" if (page / "leaf.js").exists() else "html",
    )
    captures = capture_phase(observation, selected, page, destinations=targets)
    input_limits = (inputs["observations"] or {}).get("input_limitations")
    if input_limits:
        path = observation.shots / f"p{selected}-observation.json"
        reading = json.loads(path.read_text())
        write_json(path, {**reading, "input_limitations": input_limits})
    result = copy.deepcopy(metadata)
    result["authoring_inputs"] = {
        "request": inputs["request"],
        "phases": {str(selected): {"messages": inputs["messages"]}},
    }
    phases = result["diagnostics"]["phases"]
    recorded = phases.get(str(selected), phases.get(selected))
    result["diagnostics"]["phases"] = {
        **{
            str(number): value
            for number, value in phases.items()
            if int(number) < selected
        },
        str(selected): {
            **recorded,
            "captures": captures,
            "runtime": runtime_identity(page),
            "artifact": tree_identity(page),
        },
    }
    result["provenance"] = {
        **(result.get("provenance") or {}),
        "reobservation": {
            "source_run": str(source_run.resolve()),
            "source_results_sha256": digest(source_run / "results.json"),
            "source_inputs": inputs["provenance"],
            "phase": selected,
            "destinations": targets,
            "server_payload": str(payload) if observation.leaf_condition else None,
            "server": {
                "kind": "leaf",
                **files_identity(
                    [
                        *(payload / "skills").rglob("*"),
                        payload / "bin/leaf",
                        payload / "pyproject.toml",
                        payload / "uv.lock",
                    ],
                    payload,
                ),
            }
            if observation.leaf_condition
            else {
                "kind": "python-static-http",
                "python": sys.version,
                "implementation": files_identity(
                    [ROOT / "dev/leaf_dev/arrangement_plain.py"], ROOT
                ),
            },
            "collector": files_identity(
                [
                    ROOT / "dev/leaf_dev" / name
                    for name in (
                        "eval_observe.py",
                        "arrangement_eval.py",
                        "authoring_observation.py",
                        "arrangement_plain.py",
                        "browser.py",
                        "arms.py",
                    )
                ],
                ROOT,
            ),
        },
    }
    return result


@click.command("eval-observe")
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--output", required=True, type=click.Path(file_okay=False, path_type=Path)
)
@click.option(
    "--phase", type=click.IntRange(min=1), help="Default: last recorded version."
)
@click.option(
    "--server-payload",
    default=ROOT,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    help="Compatible Leaf server tree; saved browser assets are never re-vendored.",
)
@click.option(
    "--destination",
    multiple=True,
    help="Additional labeled task destination to inspect, applied to every sample.",
)
def eval_observe(runs, output, phase, server_payload, destination):
    """Observe saved RUNS serially into new evidence for eval-score/pairs/report.

    Uses recorded destination hints, plus explicit --destination values, never
    today's task definitions. Coordinate the browser batch with other experiments.
    """
    output = output.resolve()
    if output.exists():
        raise click.ClickException(f"Output already exists: {output}")
    output.mkdir(parents=True)
    rows, seen = [], set()
    for run in runs:
        for original in json.loads((run / "results.json").read_text())["results"][
            "results"
        ]:
            metadata = (original.get("response") or {}).get("metadata") or {}
            phases = (metadata.get("diagnostics") or {}).get("phases") or {}
            if not phases or not metadata.get("work"):
                continue
            if phase is not None and str(phase) not in phases and phase not in phases:
                continue
            work = Path(metadata["work"]).resolve()
            if work in seen or any(Path(p).name == work.name for p in seen):
                raise click.ClickException(f"Duplicate sample identity: {work}")
            seen.add(work)
            row = copy.deepcopy(original)
            row["response"]["metadata"] = observe_sample(
                metadata, run, output, server_payload, phase, destination
            )
            # Old model verdicts concern the old observation, never this one.
            for field in (
                "gradingResult",
                "success",
                "score",
                "namedScores",
                "failureReason",
            ):
                row.pop(field, None)
            rows.append(row)
            click.echo(f"observed: {work.name}")
    write_json(output / "results.json", {"results": {"results": rows}})
    if not rows:
        raise click.ClickException("No samples contain the requested recorded phase.")
    click.echo(f"observed run: {output}")
