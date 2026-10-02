"""Promptfoo compares complete page, revision and feedback scenarios.

Each test is a whole trajectory rather than an isolated message. Scenario modules
declare fixed checks, including completion, and retain their execution evidence.
These existing scenarios use Claude Code; static instruction cases support both
Claude Code and Codex through their native providers.
"""

import fnmatch
import os
import sys
import tempfile
from importlib import import_module
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import base_ref, build_arm
from leaf_dev.promptfoo import output_directory, report, run

SUITES = ("usability", "arrangement", "delivery")


def select_cases(suite: str, globs: tuple[str, ...]) -> list[str]:
    cases = sorted(import_module(f"leaf_dev.{suite}_eval").CASES)
    for pattern in globs:
        if not fnmatch.filter(cases, pattern):
            raise click.BadParameter(f"no case matches {pattern!r}", param_hint="CASE")
    return [
        case
        for case in cases
        if not globs or any(fnmatch.fnmatch(case, g) for g in globs)
    ]


def prepare(
    suite: str, cases: list[str], arms: dict[str, Path], out: Path, runs: int
) -> dict:
    module = import_module(f"leaf_dev.{suite}_eval")
    providers, tests = [], []
    for arm, payload in arms.items():
        label = f"cc/{arm}"
        providers.append(
            {
                "id": f"file://{ROOT / 'dev/leaf_dev/scenario_provider.py'}",
                "label": label,
                "config": {
                    "claude_config_dir": os.environ.get(
                        "CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")
                    ),
                    "suite": suite,
                    "payload": str(payload),
                    "pythonExecutable": sys.executable,
                    "workers": 1,
                    "timeout": 1800000,
                },
            }
        )
    for case in cases:
        checks = module.expected_checks(case)
        if not checks or "completed" not in checks or len(checks) != len(set(checks)):
            raise ValueError(
                f"{suite}/{case}: checks must be unique and include completed"
            )
        for repetition in range(1, runs + 1):
            for arm in arms:
                label = f"cc/{arm}"
                work = out / "samples" / arm / case / str(repetition)
                tests.append(
                    {
                        "description": f"{suite}/{case} {arm} #{repetition}",
                        "providers": [label],
                        "metadata": {
                            "suite": suite,
                            "case": case,
                            "host": "cc",
                            "arm": arm,
                        },
                        "vars": {"case": case, "work": str(work)},
                        "assert": [
                            {
                                "type": "javascript",
                                "value": f"file://{ROOT / 'evals/scenario-check.cjs'}",
                                "metric": check,
                                "config": {"check": check},
                            }
                            for check in checks
                        ],
                    }
                )
    return {
        "description": f"Leaf {suite} scenarios",
        "prompts": ["{{case}}"],
        "providers": providers,
        "tests": tests,
    }


@click.command("scenario-eval")
@click.argument("suite", type=click.Choice(SUITES))
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", help="Base ref; defaults to the merge base with main.")
@click.option("--runs", type=click.IntRange(min=1), default=1, show_default=True)
def scenario_eval(suite: str, case_globs: tuple[str, ...], base: str | None, runs: int):
    """Score complete CASE trajectories in SUITE on base and working-tree Leaf."""
    cases = select_cases(suite, case_globs)
    out = output_directory("scenario-eval")
    with tempfile.TemporaryDirectory(prefix="leaf-scenarios-") as temporary:
        scratch = Path(temporary)
        arms = {arm: scratch / arm for arm in ("base", "candidate")}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        config = prepare(suite, cases, arms, out, runs)
        click.echo(
            f"base {commits['base'][:9]}; candidate working tree on {commits['candidate'][:9]}"
        )
        click.echo(f"{len(config['tests'])} samples; results and log: {out}")
        result, status = run(config, out)
    report(result, status, out)
