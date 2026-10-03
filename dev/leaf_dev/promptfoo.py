"""Run Leaf's native Promptfoo configs with local account authentication.

The case catalog stages its inputs. This module owns
dependency discovery, report directories, execution, and result summaries. Runs
never share, cache, or write to Promptfoo's result database.
"""

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import environment


def output_directory(suite: str) -> Path:
    executable = ROOT / "evals/node_modules/.bin/promptfoo"
    if not executable.is_file():
        raise click.ClickException(
            "Install eval dependencies first: npm ci --prefix evals"
        )
    parent = ROOT / ".tmp" / suite
    parent.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(
            prefix=f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-", dir=parent
        )
    )


def run(config: dict, out: Path) -> tuple[dict, int]:
    """Execute a prepared matrix; retain failures and errors in native results."""
    (out / "node_modules").symlink_to(ROOT / "evals/node_modules")
    config_file = out / "promptfooconfig.json"
    config_file.write_text(json.dumps(config, indent=2) + "\n")
    env = environment(
        PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE_CHECK="1"
    )
    # Local-login evals must not silently switch to ambient API billing.
    for key in (
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_API_KEY",
        "CLAUDE_CONFIG_DIR",
    ):
        env.pop(key, None)
    with (out / "run.log").open("w") as log:
        completed = subprocess.run(
            [
                str(ROOT / "evals/node_modules/.bin/promptfoo"),
                "eval",
                "-c",
                str(config_file),
                "--no-cache",
                "--no-share",
                "--no-write",
                "--max-concurrency",
                "2",
                "-o",
                str(out / "results.json"),
                "-o",
                str(out / "report.html"),
            ],
            cwd=ROOT / "evals",
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    if not (out / "results.json").is_file():
        raise click.ClickException(f"Promptfoo wrote no results; see {out / 'run.log'}")
    return json.loads((out / "results.json").read_text()), completed.returncode


def summarize(result: dict) -> list[tuple[str, str, str, str]]:
    """Group by declared provenance; keep execution errors distinct from failures."""
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in result["results"]["results"]:
        metadata = row["testCase"]["metadata"]
        key = (metadata["case"], metadata["host"], metadata["arm"])
        grouped.setdefault(key, []).append(row)
    rows = []
    for (case, host, arm), samples in sorted(grouped.items()):
        passed = sum(sample["success"] for sample in samples)
        errors = sum(sample.get("failureReason") == 2 for sample in samples)
        count = f"{passed}/{len(samples)}"
        rows.append(
            (case, host, arm, count + (f" ({errors} errors)" if errors else ""))
        )
    return rows


def report(result: dict, status: int, out: Path) -> None:
    for case, host, arm, count in summarize(result):
        click.echo(f"{case}  {host}  {arm}  {count}")
    click.echo(f"report: file://{out / 'report.html'}")
    if status:
        raise click.ClickException(f"Evaluation has failures; see {out / 'run.log'}")
