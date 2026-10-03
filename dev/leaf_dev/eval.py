"""One task catalog and Promptfoo matrix for short replies and complete workflows.

Native tests keep native stateless providers. Tasks needing a directory or feedback
name an executor; it owns its steps and semantic checks, not matrix or reporting.
Contexts expand under task/context without dropping their distinct evidence. Host,
Leaf revision and HTML condition are independent: HTML is sampled once per host,
not once per Leaf revision. Every model sample has an isolated authenticated home.
"""

import fnmatch
import os
import re
import shutil
import sys
import tempfile
from importlib import import_module
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


def context_case(source: dict, address: str) -> dict:
    """A named diagnostic overrides the primary, inheriting its metadata."""
    primary = {key: value for key, value in source.items() if key != "variants"}
    if "/" not in address:
        return primary
    variant = source["variants"][address.split("/", 1)[1]]
    return {
        **primary,
        **variant,
        "metadata": {**primary["metadata"], **variant["metadata"]},
    }


def catalog() -> dict[str, dict]:
    """Expand named contexts, preserving each task's native Promptfoo test."""
    cases = {}
    for path in sorted((ROOT / "evals").glob("*/case.yaml")):
        source = yaml.safe_load(path.read_text())
        task = path.parent.name
        for address in [
            task,
            *(f"{task}/{name}" for name in source.get("variants", {})),
        ]:
            cases[address] = context_case(source, address)
    return cases


def select_cases(globs: tuple[str, ...]) -> list[str]:
    """Bare tasks select primary workflows; task/context selects a diagnostic."""
    cases = sorted(catalog())
    for pattern in globs:
        if not fnmatch.filter(cases, pattern):
            raise click.BadParameter(f"no case matches {pattern!r}", param_hint="CASE")
    return [
        case
        for case in cases
        if (not globs and "/" not in case)
        or any(fnmatch.fnmatch(case, g) for g in globs)
    ]


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
    *,
    out: Path | None = None,
    conditions: tuple[str, ...] = ("leaf",),
) -> dict:
    """Build only meaningful host/condition/revision cells for selected tasks."""
    definitions = catalog()
    tests, providers = [], []
    for address in cases:
        definition = definitions[address]
        task = address.split("/", 1)[0]
        declared = definition.get("metadata", {}).get("conditions", ["leaf"])
        for condition in conditions:
            if condition not in declared:
                continue
            selected_arms = arms if condition == "leaf" else {"html": arms["candidate"]}
            for arm, payload in selected_arms.items():
                source = context_case(
                    read_case(ROOT / "evals" / task / "case.yaml", payload), address
                )
                metadata = source.get("metadata", {})
                executor = metadata.get("executor")
                if executor:
                    module = import_module(executor)
                    owner_case = metadata["case"]
                    checks = module.expected_checks(owner_case, condition=condition)
                    if (
                        not checks
                        or "completed" not in checks
                        or len(checks) != len(set(checks))
                    ):
                        raise ValueError(
                            f"{address}: checks must be unique and include completed"
                        )
                    source["assert"] = [
                        {
                            "type": "javascript",
                            "value": "file://scenario-check.cjs",
                            "metric": check,
                            "config": {"check": check},
                        }
                        for check in checks
                    ]
                for assertion in source["assert"]:
                    value = assertion.get("value")
                    if isinstance(value, str) and value.startswith("file://"):
                        assertion["value"] = (
                            f"file://{ROOT / 'evals' / value.removeprefix('file://')}"
                        )
                for host in hosts:
                    if host not in metadata.get("hosts", HOSTS):
                        continue
                    for repetition in range(1, runs + 1):
                        label = f"{host}/{arm}/{address}/{repetition}"
                        work = scratch / "work" / host / arm / address / str(repetition)
                        work.mkdir(parents=True)
                        if executor:
                            evidence = (
                                (out or scratch)
                                / "samples"
                                / host
                                / arm
                                / address
                                / str(repetition)
                            )
                            configured = {
                                "id": f"file://{ROOT / 'dev/leaf_dev/scenario_provider.py'}",
                                "config": {
                                    "claude_config_dir": os.environ.get(
                                        "CLAUDE_CONFIG_DIR",
                                        str(Path.home() / ".claude"),
                                    ),
                                    "executor": executor,
                                    "host": host,
                                    "condition": condition,
                                    "payload": str(payload),
                                    "pythonExecutable": sys.executable,
                                    "workers": 1,
                                    "timeout": 1800000,
                                },
                            }
                            variables = {
                                "prompt": address,
                                "case": owner_case,
                                "work": str(evidence),
                            }
                        else:
                            images = pinned_copy(ROOT / "evals" / task)
                            if images is not None and images.is_dir():
                                shutil.copytree(
                                    images, work / "evals" / task, dirs_exist_ok=True
                                )
                            configured = provider(host, payload, work)
                            variables = {
                                **source["vars"],
                                "prompt": "Use the Leaf skill ($leaf in Codex; leaf:leaf in Claude Code).\n\n"
                                + source["vars"]["prompt"],
                            }
                        configured["label"] = label
                        providers.append(configured)
                        tests.append(
                            {
                                **source,
                                "vars": variables,
                                "providers": [label],
                                "metadata": {
                                    **metadata,
                                    "case": address,
                                    "host": host,
                                    "arm": arm,
                                    "condition": condition,
                                },
                            }
                        )
    if not tests:
        raise click.BadParameter(
            "selected cases have no requested host/condition",
            param_hint="--host/--condition",
        )
    return {
        "description": "Leaf tasks",
        "prompts": ["{{prompt}}"],
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


@click.command("eval")
@click.argument("case_globs", metavar="[CASE]...", nargs=-1)
@click.option("--base", help="Base ref; defaults to the merge base with main.")
@click.option(
    "--host", type=click.Choice([*HOSTS, "both"]), default="both", show_default=True
)
@click.option(
    "--condition",
    type=click.Choice(["leaf", "html", "both"]),
    default="leaf",
    show_default=True,
)
@click.option("--runs", type=click.IntRange(min=1), default=1, show_default=True)
def eval(
    case_globs: tuple[str, ...], base: str | None, host: str, condition: str, runs: int
):
    """Score CASE globs or task/context on both hosts and Leaf revisions."""
    cases = select_cases(case_globs)
    out = output_directory("eval")
    with tempfile.TemporaryDirectory(prefix="leaf-eval-") as temporary:
        scratch = Path(temporary)
        arms = {arm: scratch / arm for arm in ARMS}
        commits = {
            "base": build_arm(base_ref(base), arms["base"]),
            "candidate": build_arm(None, arms["candidate"]),
        }
        config = prepare(
            cases,
            arms,
            scratch,
            HOSTS if host == "both" else (host,),
            runs,
            out=out,
            conditions=("leaf", "html") if condition == "both" else (condition,),
        )
        click.echo(
            f"base {commits['base'][:9]}; candidate working tree on {commits['candidate'][:9]}"
        )
        click.echo(f"{len(config['tests'])} samples; results and log: {out}")
        result, status = run(config, out)
    report(result, status, out)
