"""Run the controlled no-tools format experiment; design lives beside its briefs."""

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.arms import environment
from leaf_dev.widget_format_eval import FIXTURES, MODEL, check


@click.command()
@click.option("--repeat", default=3, type=click.IntRange(1, 3), show_default=True)
@click.option(
    "--smoke",
    is_flag=True,
    help="One form response per format; excluded from retained batch.",
)
@click.option(
    "--preflight",
    is_flag=True,
    help="Check equivalent known fixtures without model calls.",
)
@click.option(
    "--repair",
    type=click.Path(path_type=Path, exists=True),
    multiple=True,
    help="Failed initial sample directory; one standardized repair, with optional semantic-feedback.txt.",
)
def eval_widget_formats(
    repeat: int, smoke: bool, preflight: bool, repair: tuple[Path, ...]
):
    """Compare raw HTML fragments with nested JSON trees using identical components."""
    root = ROOT / ".tmp/eval"
    root.mkdir(parents=True, exist_ok=True)
    run = Path(
        tempfile.mkdtemp(
            prefix=f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-controlled-", dir=root
        )
    )
    if preflight:
        for case in ("form", "choice"):
            for condition in ("html", "json"):
                work = run / f"{case}-{condition}"
                work.mkdir()
                fixture = (
                    FIXTURES / f"controlled-fixture-{case}.{condition}"
                ).read_text()
                result = check(fixture, condition, case, work)
                click.echo(json.dumps({"case": case, "condition": condition, **result}))
                if not all(result["checks"].values()):
                    raise click.ClickException("Preflight fixture failed")
        return
    providers = [
        {
            "id": f"python:{ROOT / 'dev/leaf_dev/widget_format_eval.py'}",
            "label": condition,
            "config": {
                "condition": condition,
                "samples": str(run / "samples"),
                "pythonExecutable": sys.executable,
                "timeout": 10 * 60 * 1000,
                "stage": "repair" if repair else "smoke" if smoke else "initial",
            },
        }
        for condition in ("html", "json")
    ]
    tests = []
    schedule = []
    if repair:
        for original in repair:
            metadata = json.loads((original / "sample.json").read_text())
            if metadata["stage"] == "repair":
                raise click.ClickException("A repair cannot receive a second repair")
            semantic = original / "semantic-feedback.txt"
            diagnostics = metadata["diagnostics"] + (
                "\n" + semantic.read_text() if semantic.exists() else ""
            )
            request = (
                (original / "prompt.txt").read_text()
                + "\n\nYour previous response:\n"
                + (original / "response.txt").read_text()
                + "\n\nIndependent check diagnostics:\n"
                + diagnostics
                + "\n\nReturn a complete corrected response under the same output contract. Fix the diagnosed failures and preserve the requested facts and behavior."
            )
            schedule.append(
                (
                    metadata["case"],
                    metadata["condition"],
                    metadata["repetition"],
                    request,
                )
            )
    else:
        for repetition in range(1, (1 if smoke else repeat) + 1):
            cases = ["form"] if smoke else ["status", "choice", "form"]
            if not smoke:
                shift = (repetition - 1) % len(cases)
                cases = cases[shift:] + cases[:shift]
            for case in cases:
                order = (
                    ("html", "json")
                    if (["status", "choice", "form"].index(case) + repetition) % 2
                    else ("json", "html")
                )
                request = (FIXTURES / f"{case}.md").read_text()
                schedule.extend(
                    (case, condition, repetition, request) for condition in order
                )
    for index, (case, condition, repetition, request) in enumerate(schedule):
        tests.append(
            {
                "description": f"{index + 1:02d} {case} r{repetition} {condition}",
                "vars": {
                    "prompt": request,
                    "case": case,
                    "repetition": repetition,
                    **({"repairOf": str(repair[index].resolve())} if repair else {}),
                },
                "providers": [condition],
                "assert": [
                    {
                        "type": "javascript",
                        "metric": key,
                        "value": f"context.providerResponse.metadata.checks[{json.dumps(key)}] === true",
                    }
                    for key in (
                        "completed",
                        "no-tool-use",
                        "format-valid",
                        "page-valid",
                        "interaction-proven",
                    )
                ],
            }
        )
    config = {
        "description": f"controlled widget syntax / {MODEL} medium / {'repair' if repair else 'smoke' if smoke else 'initial'}",
        "prompts": ["{{prompt}}"],
        "providers": providers,
        "tests": tests,
        "evaluateOptions": {"maxConcurrency": 1},
    }
    (run / "schedule.json").write_text(
        json.dumps(
            [{"case": c, "condition": a, "repetition": r} for c, a, r, _ in schedule],
            indent=2,
        )
    )
    config_path = run / "promptfooconfig.json"
    config_path.write_text(json.dumps(config, indent=2))
    for source in FIXTURES.glob("controlled-*.md"):
        (run / source.name).write_text(source.read_text())
    click.echo(f"Run: {run}")
    env = environment(
        PROMPTFOO_DISABLE_TELEMETRY="1",
        PROMPTFOO_DISABLE_UPDATE_CHECK="1",
        PROMPTFOO_PYTHON=sys.executable,
    )
    status = subprocess.run(
        [
            str(ROOT / "node_modules/.bin/promptfoo"),
            "eval",
            "-c",
            str(config_path),
            "--no-cache",
            "--max-concurrency",
            "1",
            "--output",
            str(run / "results.json"),
        ],
        cwd=ROOT,
        env=env,
        check=False,
    ).returncode
    click.echo("view: pnpm run eval:view")
    sys.exit(status)
