"""Promptfoo scores the same instruction cases on Claude Code and Codex.

Cases are native Promptfoo tests; this module only stages Leaf's base/candidate
payloads and isolated authenticated homes. Every host/arm/repetition has its own
cwd and home, outside any repository. Models receive the same task and shipped
skill. Static authoring cases do not exercise plugin discovery or hooks; the
terminal task verification owns those boundaries.
"""

import fnmatch
import re
import shutil
import tempfile
from pathlib import Path

import click
import yaml

from leaf_dev import ROOT
from leaf_dev.harness import base_ref, build_arm, claude_child, codex_home
from leaf_dev.leaf_assets import pinned_copy
from leaf_dev.promptfoo import output_directory, report, run

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
                                "case": case,
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
    cases = select_cases(case_globs)
    out = output_directory("instructions-eval")
    with tempfile.TemporaryDirectory(prefix="leaf-promptfoo-") as temporary:
        scratch = Path(temporary)
        arms = {arm: scratch / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        config = prepare(
            cases, arms, scratch, HOSTS if host == "both" else (host,), runs
        )
        click.echo(
            f"base {commits['base'][:9]}; candidate working tree on {commits['candidate'][:9]}"
        )
        click.echo(f"{len(config['tests'])} samples; results and log: {out}")
        result, status = run(config, out)
    report(result, status, out)
