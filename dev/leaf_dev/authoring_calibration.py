"""Observe and grade fixed authoring controls, with a separate private oracle.

Fixtures are standalone, hash-pinned native HTML. Capture is serialized through
one browser; model grading starts only after it closes and may run concurrently.
The judge receives tasks and observations, never expectation files or split labels.
Arrival-only runs reuse the same fixtures to measure the effect of missing states.
The captured packet pins the fixture, browser and evaluator independently.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.authoring_observation import observe
from leaf_dev.authoring_score import digest, evaluate, stage_packet, write_json
from leaf_dev.browser import chrome, tab
from leaf_dev.eval_provenance import files_identity

FIXTURES = ROOT / "evals/authoring-calibration"


def capture_controls(manifest: Path, output: Path, *, arrival_only=False) -> list[Path]:
    """Verify fixed artifact bytes, then observe each using the same collector.

    Only the public manifest is read. Expectations remain unavailable to capture
    and judging; an independent comparison reads them after the grades are fixed.
    """
    cases = json.loads(manifest.read_text())
    packets = []
    with chrome() as browser:
        for number, case in enumerate(cases["cases"], 1):
            source = manifest.parent / case["artifact"]
            if digest(source) != case["sha256"]:
                raise click.ClickException(
                    f"Frozen calibration artifact changed: {source}"
                )
            work = output / f"observation-{number:03}"
            work.mkdir(parents=True)
            captures, widths = {}, {}
            destinations = [
                r["target"] for r in case["routes"] if r["action"] == "click"
            ]
            with arrangement_plain.serving(manifest.parent) as origin:
                for viewport in case["viewports"]:
                    size = (viewport["width"], viewport["height"])
                    name = f"{size[0]}x{size[1]}"
                    with tab(browser, viewport=size, touch=size[0] < 500) as page:
                        arrangement_plain.load(page, f"{origin}{case['artifact']}")
                        observed = observe(
                            page,
                            work,
                            name,
                            arrangement_plain.settle,
                            destinations=destinations,
                        )
                        if arrival_only:
                            states = [
                                s
                                for s in observed["states"]
                                if s["action"]["type"] == "arrival"
                            ]
                            images = list(
                                dict.fromkeys(p for s in states for p in s["images"])
                            )
                            observed = {
                                **observed,
                                "states": states,
                                "captures": images,
                                "limitations": [
                                    "Only arrival evidence supplied. Later inspection states withheld."
                                ],
                            }
                        captures[name] = observed["captures"]
                        widths[name] = observed
            observations = {"version": 1, "widths": widths, "browser": browser.version}
            write_json(work / "observations.json", observations)
            packet = stage_packet(
                output / f"packet-{number:03}",
                request=case["request"],
                messages=case["messages"],
                captures=captures,
                observations=observations,
                provenance={
                    "authoring": {
                        "revision": cases["provenance"]["authoring_revision"],
                        "method": cases["provenance"]["authoring_method"],
                        "artifact_sha256": digest(source),
                    },
                    "runtime": {
                        "kind": "native-html",
                        "browser": browser.version,
                        "artifact_sha256": digest(source),
                    },
                    "observation": files_identity(
                        [
                            ROOT / "dev/leaf_dev" / name
                            for name in (
                                "authoring_observation.py",
                                "authoring_calibration.py",
                                "browser.py",
                                "arrangement_plain.py",
                            )
                        ],
                        ROOT,
                    ),
                },
            )
            packets.append(packet)
    write_json(
        output / "cases.json",
        [{"case": c["id"], "packet": str(p)} for c, p in zip(cases["cases"], packets)],
    )
    return packets


@click.command("eval-calibrate")
@click.option(
    "--split", type=click.Choice(["development", "heldout"]), default="development"
)
@click.option(
    "--output", required=True, type=click.Path(path_type=Path, file_okay=False)
)
@click.option(
    "--prepare-only",
    is_flag=True,
    help="Capture fixed controls without calling a judge.",
)
@click.option(
    "--arrival-only",
    is_flag=True,
    help="Supply arrival views only, holding fixture bytes fixed.",
)
def eval_calibrate(split: str, output: Path, prepare_only: bool, arrival_only: bool):
    """Calibrate the authoring scorer on fixed controls; browsers run serially."""
    output = output.resolve()
    if output.exists():
        raise click.ClickException(f"Output already exists: {output}")
    output.mkdir(parents=True)
    packets = capture_controls(
        FIXTURES / split / "manifest.json", output, arrival_only=arrival_only
    )
    if not prepare_only:
        with ThreadPoolExecutor(max_workers=2) as models:
            grades = list(models.map(evaluate, packets))
        write_json(output / "scores.json", grades)
        for number, grade in enumerate(grades, 1):
            click.echo(f"{number}: {grade['status']}")
    click.echo(f"evidence: {output}")
