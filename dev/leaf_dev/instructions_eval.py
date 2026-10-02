"""Promptfoo scores the same instruction cases on Claude Code and Codex.

Cases are native Promptfoo tests; this module only stages Leaf's base/candidate
payloads and isolated authenticated homes. Every host/arm/repetition has its own
cwd and home, outside any repository. Models receive the same task and shipped
skill. Static authoring cases do not exercise plugin discovery or hooks; the
terminal task verification owns those boundaries.
"""

import fnmatch
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click
import yaml

from leaf_dev import ROOT
from leaf_dev.harness import base_ref, build_arm, claude_child, codex_home, environment
from leaf_dev.leaf_assets import pinned_copy

OUT = ROOT / ".tmp" / "instructions-eval"
ARMS = ("base", "candidate")
HOSTS = ("cc", "codex")
PACKAGE_INSTRUCTION_PATH = re.compile(
    r"packages/[a-z][a-z0-9-]*/instructions/[a-z][a-z0-9-]*(?:\\)?\.md"
)


def select_cases(globs: tuple[str, ...]) -> list[str]:
    """Select current cases, so a new case also scores the historical payload."""
    cases = sorted(path.parent.name for path in (ROOT / "evals").glob("*/case.yaml"))
    for glob in globs:
        if not fnmatch.filter(cases, glob):
            raise click.BadParameter(f"no case matches {glob!r}", param_hint="CASE")
    return [c for c in cases if not globs or any(fnmatch.fnmatch(c, g) for g in globs)]


def read_case(case_file: Path, payload: Path) -> dict:
    """Use each historical payload's own package instruction addresses.

    The task and assertions remain identical apart from the directory rename.
    Missing resources fail preparation before spending any model calls.
    """
    source = case_file.read_text()

    def resolved(match: re.Match) -> str:
        reference = match[0]
        path = reference.replace(r"\.", ".")
        if (payload / "skills" / "leaf" / path).is_file():
            return reference
        historical = path.replace("/instructions/", "/guidance/")
        if (payload / "skills" / "leaf" / historical).is_file():
            return reference.replace("/instructions/", "/guidance/")
        raise click.ClickException(
            f"{case_file}: package instruction file {path} is absent from "
            f"{payload} (also checked {historical})"
        )

    return yaml.safe_load(PACKAGE_INSTRUCTION_PATH.sub(resolved, source))


def provider(host: str, payload: Path, work: Path) -> dict:
    """Native providers; only the supplied skill and local account login are shared."""
    if host == "cc":
        child = claude_child(work)
        return {
            "id": "anthropic:claude-agent-sdk",
            "config": {
                "model": "opus",
                "apiKeyRequired": False,
                "working_dir": str(work),
                "persist_session": False,
                "setting_sources": [],
                "strict_mcp_config": True,
                "plugins": [{"type": "local", "path": str(payload)}],
                "additional_directories": [str(payload)],
                "tools": ["Skill", "Read"],
                "custom_allowed_tools": ["Skill", "Read"],
                "permission_mode": "dontAsk",
                "max_turns": 24,
                "settings": {"autoMemoryEnabled": False},
                "env": {
                    "XDG_STATE_HOME": str(Path(child["env"]["HOME"]) / ".local/state"),
                    **{
                        key: child["env"][key]
                        for key in (
                            "HOME",
                            "TMPDIR",
                            "UV_CACHE_DIR",
                            "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
                        )
                    },
                },
            },
        }
    home = work.with_name(f"{work.name}-home")
    home.mkdir(mode=0o700)
    config_home = codex_home(home / ".codex")
    (config_home / "skills").mkdir()
    (config_home / "skills" / "leaf").symlink_to(payload / "skills" / "leaf")
    return {
        "id": "openai:codex-app-server",
        "config": {
            "model": "gpt-6.1-sol",
            "model_reasoning_effort": "medium",
            "working_dir": str(work),
            "skip_git_repo_check": True,
            "sandbox_mode": "read-only",
            "approval_policy": "never",
            "persist_threads": False,
            "ephemeral": True,
            "reuse_server": False,
            "turn_timeout_ms": 300000,
            "cli_env": {
                "HOME": str(home),
                "CODEX_HOME": str(config_home),
                "XDG_STATE_HOME": str(home / ".local/state"),
            },
        },
    }


def prepare(
    cases: list[str],
    arms: dict[str, Path],
    scratch: Path,
    hosts: tuple[str, ...],
    runs: int,
) -> dict:
    """Produce native Promptfoo config, giving every evaluated cell a fresh session."""
    tests, providers = [], []
    for arm, payload in arms.items():
        for case in cases:
            source = read_case(ROOT / "evals" / case / "case.yaml", payload)
            images = pinned_copy(ROOT / "evals" / case)
            for assertion in source["assert"]:
                value = assertion.get("value")
                if isinstance(value, str) and value.startswith("file://"):
                    assertion["value"] = (
                        f"file://{ROOT / 'evals' / value.removeprefix('file://')}"
                    )
            for host in hosts:
                for repetition in range(runs):
                    label = f"{host}/{arm}/{case}/{repetition + 1}"
                    work = scratch / label.replace("/", "-")
                    work.mkdir()
                    if images is not None and images.is_dir():
                        shutil.copytree(
                            images, work / "evals" / case, dirs_exist_ok=True
                        )
                    configured = provider(host, payload, work)
                    configured["label"] = label
                    providers.append(configured)
                    tests.append(
                        {
                            **source,
                            "providers": [label],
                            "metadata": {
                                **source["metadata"],
                                "host": host,
                                "arm": arm,
                            },
                        }
                    )
    return {
        "description": "Leaf instruction comparison",
        "prompts": [
            "Use the Leaf skill ($leaf in Codex; leaf:leaf in Claude Code).\n\n{{prompt}}"
        ],
        "providers": providers,
        "tests": tests,
        "defaultTest": {
            "options": {
                "provider": {
                    "id": "anthropic:claude-agent-sdk",
                    "config": {
                        "model": "sonnet",
                        "apiKeyRequired": False,
                        "setting_sources": [],
                        "persist_session": False,
                    },
                }
            }
        },
    }


def summarize(result: dict) -> list[tuple[str, str, str, str]]:
    """Keep host and arm separate; execution errors are not instruction failures."""
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in result["results"]["results"]:
        host, arm, case, _ = row["provider"]["label"].split("/")
        grouped.setdefault((case, host, arm), []).append(row)
    rows = []
    for (case, host, arm), samples in sorted(grouped.items()):
        passed = sum(sample["success"] for sample in samples)
        errors = sum(sample.get("failureReason") == 2 for sample in samples)
        count = f"{passed}/{len(samples)}"
        rows.append(
            (case, host, arm, count + (f" ({errors} errors)" if errors else ""))
        )
    return rows


@click.command("instructions-eval")
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", help="Base ref; defaults to the merge base with main.")
@click.option(
    "--host", type=click.Choice([*HOSTS, "both"]), default="both", show_default=True
)
@click.option("--runs", type=click.IntRange(min=1), default=1, show_default=True)
def instructions_eval(
    case_globs: tuple[str, ...], base: str | None, host: str, runs: int
):
    """Score CASE globs (or all cases), on base and working-tree instructions."""
    executable = ROOT / "evals" / "node_modules" / ".bin" / "promptfoo"
    if not executable.is_file():
        raise click.ClickException(
            "Install eval dependencies first: npm ci --prefix evals"
        )
    cases = select_cases(case_globs)
    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(
        tempfile.mkdtemp(
            prefix=f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-", dir=OUT
        )
    )
    with tempfile.TemporaryDirectory(prefix="leaf-promptfoo-") as temporary:
        scratch = Path(temporary)
        (out / "node_modules").symlink_to(ROOT / "evals" / "node_modules")
        arms = {arm: scratch / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        config = prepare(
            cases, arms, scratch, HOSTS if host == "both" else (host,), runs
        )
        config_file = out / "promptfooconfig.json"
        config_file.write_text(json.dumps(config, indent=2) + "\n")
        click.echo(
            f"base {commits['base'][:9]}; candidate working tree on {commits['candidate'][:9]}"
        )
        click.echo(f"{len(config['tests'])} samples; results and log: {out}")
        env = environment(
            PROMPTFOO_DISABLE_TELEMETRY="1", PROMPTFOO_DISABLE_UPDATE_CHECK="1"
        )
        # Native local-login evals must not silently switch to ambient API billing.
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
                    str(executable),
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
    for case, selected_host, arm, count in summarize(
        json.loads((out / "results.json").read_text())
    ):
        click.echo(f"{case}  {selected_host}  {arm}  {count}")
    click.echo(f"report: file://{out / 'report.html'}")
    if completed.returncode:
        raise click.ClickException(f"Evaluation has failures; see {out / 'run.log'}")
