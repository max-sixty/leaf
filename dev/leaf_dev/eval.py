"""Run the eval catalog through Promptfoo on Claude Code and Codex.

This command does only what Promptfoo cannot: it builds each Leaf arm (the working
tree, and with `--base` a ref), gives each provider a home of its own seeded with the
harness's login, and expands the catalog's task/context addresses into Promptfoo tests.
Native probes install the complete arm as a plugin and read it in fresh sessions;
Codex shares one server per provider home while starting fresh ephemeral, read-only
threads for each test.
Promptfoo owns the rest: repetition, concurrency, assertions, the console table, and
the result database its viewer reads. Arguments after the cases go to `promptfoo eval`.

A provider is one column of the results: a harness on one arm (`claude-code/candidate`),
suffixed `/workflow` for the Python provider that runs complete tasks, and on arm `html`
for the plain HTML control. A workflow column names the Leaf transport its harness
session takes where the harness has more than one (`codex:app-server/base/workflow`),
since a workflow scores only that transport. A test is one catalog address under one
condition.
"""

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from importlib import import_module
from pathlib import Path

import click
import yaml
from leaf.harness import ClaudeCodeHarness

from leaf_dev import ROOT
from leaf_dev.arms import (
    HARNESSES,
    MODELS,
    TURN_LIMIT,
    WORKFLOW_LIMIT,
    base_ref,
    build_arm,
    child_class,
    claude_child,
    codex_home,
    environment,
)
from leaf_dev.leaf_assets import pinned_copy

PROMPTFOO = ROOT / "evals/node_modules/.bin/promptfoo"
RUNS = ROOT / ".tmp/eval"
SKILL_PREFIX = "Use the Leaf skill ($leaf in Codex; leaf:leaf in Claude Code).\n\n"


def codex_program() -> Path:
    """Resolve the host CLI used by Codex providers and plugin installation."""
    if (installed := shutil.which("codex")) is None:
        raise click.ClickException("Codex evals require the Codex CLI; install it")
    return Path(installed).resolve()


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


def native_provider(harness: str, payload: Path, work: Path) -> dict:
    """A read-only native agent with the arm installed as its complete plugin."""
    if harness == ClaudeCodeHarness.name:
        child = claude_child(work)
        return {
            "id": "anthropic:claude-agent-sdk",
            "config": {
                "model": MODELS[ClaudeCodeHarness.name],
                "apiKeyRequired": False,
                "working_dir": str(work),
                "persist_session": False,
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
    codex = codex_program()
    cli_env = {
        "HOME": str(home),
        "CODEX_HOME": str(config_home),
        "XDG_STATE_HOME": str(home / ".local/state"),
    }
    # The installer and provider use the same CLI. Installing the complete
    # plugin preserves discovery and skill references relative to the plugin root.
    for args in (
        ("plugin", "marketplace", "add", str(payload), "--json"),
        ("plugin", "add", "leaf@leaf", "--json"),
    ):
        installed = subprocess.run(
            [str(codex), *args],
            cwd=work,
            env=environment(**cli_env),
            capture_output=True,
            text=True,
            check=False,
        )
        if installed.returncode:
            raise click.ClickException(
                f"Codex plugin installation failed:\n{installed.stdout}{installed.stderr}"
            )
    return {
        "id": "openai:codex-app-server",
        "config": {
            "model": MODELS["codex"],
            "codex_path_override": str(codex),
            "model_reasoning_effort": "medium",
            "working_dir": str(work),
            "skip_git_repo_check": True,
            "turn_timeout_ms": TURN_LIMIT * 1000,
            "cli_env": cli_env,
        },
    }


def workflow_harness(harness: str) -> str:
    """The harness as a workflow column names it, with its session's transport."""
    transport = child_class(harness).transport
    return harness if transport is None else f"{harness}:{transport}"


def workflow_provider(
    harness: str, condition: str, payload: Path, samples: Path, screenshots: Path
) -> dict:
    """The Python provider that hands one complete task to its declared executor."""
    return {
        "id": f"file://{ROOT / 'dev/leaf_dev/scenario_provider.py'}",
        "config": {
            # `eval` drops CLAUDE_CONFIG_DIR from Promptfoo's environment, so native
            # providers can't read the user's settings; executors need it to find
            # the login (`claude_child`).
            "claude_config_dir": os.environ.get(
                "CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")
            ),
            "harness": harness,
            "condition": condition,
            "payload": str(payload),
            "samples": str(samples),
            "screenshots": str(screenshots),
            "pythonExecutable": sys.executable,
            "timeout": WORKFLOW_LIMIT * 1000,
        },
    }


def screenshot_judge(screenshots: Path, home: Path) -> dict:
    """The Codex grader for an executor's `agent-rubric`s, run under a home of its own.

    Its permission profile lets it read the run's screenshot tree and nothing else,
    so neither a page's source, the author's transcript, nor a path naming the arm
    reaches it. `:minimal` is the runtime paths tools need, which include the temp
    directories but not the repository. Codex starts its sandbox helper by executing
    itself, so the profile also grants the executable, run by its resolved path: a
    symlink's own location is refused. A profile replaces Codex's older sandbox
    settings, so the provider sets no `sandbox_mode`."""
    codex = codex_program()
    home.mkdir(mode=0o700, parents=True)
    profile = "\n".join(
        [
            'default_permissions = "screenshots"',
            "",
            "[permissions.screenshots.filesystem]",
            '":minimal" = "read"',
            f'{json.dumps(f"{screenshots}/**")} = "read"',
            f'{json.dumps(str(codex))} = "read"',
            "",
        ]
    )
    return {
        "id": "openai:codex-sdk",
        "config": {
            "model": MODELS["screenshots"],
            "codex_path_override": str(codex),
            "working_dir": str(home),
            "skip_git_repo_check": True,
            "cli_env": {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home(home / ".codex", profile)),
            },
        },
    }


def prepare(
    cases: list[str],
    arms: dict[str, Path],
    scratch: Path,
    harnesses: tuple[str, ...],
    conditions: tuple[str, ...],
    samples: Path,
) -> dict:
    """One test per selected address and condition, run on each column it applies to."""
    definitions = catalog()
    providers: dict[str, dict] = {}
    tests = []
    # Judged screenshots sit apart from the rest of the evidence, for the judge.
    screenshots = samples.with_name("screenshots")
    judge = None
    for address in cases:
        test = definitions[address]
        metadata = test.get("metadata", {})
        executor = metadata.get("executor")
        instructions = metadata.get("instructions")
        for condition in conditions:
            if condition not in metadata.get("conditions", ["leaf"]):
                continue
            columns = arms if condition == "leaf" else {"html": arms["candidate"]}
            labels = []
            for harness in harnesses:
                if harness not in metadata.get("harnesses", HARNESSES):
                    continue
                for arm, payload in columns.items():
                    label = (
                        f"{workflow_harness(harness)}/{arm}/workflow"
                        if executor
                        else f"{harness}/{arm}"
                        + ("/instructions" if instructions else "")
                    )
                    if label not in providers:
                        if executor:
                            configured = workflow_provider(
                                harness, condition, payload, samples, screenshots
                            )
                        else:
                            work = scratch / "work" / label
                            work.mkdir(parents=True)
                            configured = native_provider(harness, payload, work)
                            if instructions:
                                field = (
                                    "append_system_prompt"
                                    if harness == ClaudeCodeHarness.name
                                    else "developer_instructions"
                                )
                                configured["config"][field] = (
                                    payload / instructions
                                ).read_text()
                        providers[label] = {**configured, "label": label}
                    labels.append(label)
            if not labels:
                continue
            sample = deepcopy(test)
            task = address.split("/", 1)[0]
            if executor:
                module = import_module(executor)
                checks = module.expected_checks(
                    metadata["scenario"], condition=condition
                )
                rubrics = getattr(module, "rubrics", lambda _: [])(metadata["scenario"])
                if rubrics and judge is None:
                    judge = screenshot_judge(screenshots, scratch / "judge")
                sample["assert"] = [
                    *(
                        {
                            "type": "javascript",
                            "value": f"context.providerResponse.metadata?.checks?.[{json.dumps(check)}] === true",
                            "metric": check,
                        }
                        for check in checks
                    ),
                    # A judge's verdicts on the screenshots the sample lists.
                    *({**rubric, "provider": judge} for rubric in rubrics),
                ]
                sample["vars"] = {"prompt": address}
            else:
                sample["vars"] = {
                    **sample["vars"],
                    "prompt": ("" if instructions else SKILL_PREFIX)
                    + sample["vars"]["prompt"],
                }
                images = pinned_copy(ROOT / "evals" / task)
                if images is not None and images.is_dir():
                    for label in labels:
                        shutil.copytree(
                            images,
                            Path(providers[label]["config"]["working_dir"])
                            / "evals"
                            / task,
                            dirs_exist_ok=True,
                        )
            for assertion in sample["assert"]:
                value = assertion.get("value")
                if isinstance(value, str) and value.startswith("file://"):
                    assertion["value"] = (
                        f"file://{ROOT / 'evals' / value.removeprefix('file://')}"
                    )
            tests.append(
                {
                    **sample,
                    "description": address
                    + ("" if condition == "leaf" else f" ({condition})"),
                    "providers": labels,
                    "metadata": {**metadata, "case": address, "condition": condition},
                }
            )
    if not tests:
        raise click.BadParameter(
            "selected cases have no requested harness/condition",
            param_hint="--harness/--condition",
        )
    return {
        "prompts": ["{{prompt}}"],
        "providers": list(providers.values()),
        "tests": tests,
        "defaultTest": {
            "options": {
                "provider": {
                    "id": "anthropic:claude-agent-sdk",
                    "config": {
                        "model": MODELS["judge"],
                        "apiKeyRequired": False,
                        "persist_session": False,
                    },
                }
            }
        },
    }


def describe(base: str | None, head: str, globs: tuple[str, ...]) -> str:
    """The run's name in Promptfoo's viewer: branch, arms and the cases asked for."""
    branch = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    arms = f"working tree on {head[:9]}"
    if base:
        arms = f"base {base[:9]} vs {arms}"
    return f"{branch} ({arms}): {' '.join(globs) or 'all tasks'}"


@click.command(
    "eval",
    context_settings={"ignore_unknown_options": True},
)
@click.argument("args", metavar="[CASE]... [PROMPTFOO_OPTION]...", nargs=-1)
@click.option(
    "--base",
    is_flag=False,
    flag_value="",
    default=None,
    help="Also run the merge base with main, or the ref given.",
)
@click.option(
    "--harness",
    type=click.Choice([*HARNESSES, "both"]),
    default="both",
    show_default=True,
)
@click.option(
    "--condition",
    type=click.Choice(["leaf", "html", "both"]),
    default="leaf",
    show_default=True,
)
def eval(args: tuple[str, ...], base: str | None, harness: str, condition: str):
    """Score CASE globs or task/context addresses on the working tree.

    Options Promptfoo takes follow the cases, such as `--repeat 3` or `-j 4`.
    `npm run view --prefix evals` opens the results.
    """
    split = next((i for i, arg in enumerate(args) if arg.startswith("-")), len(args))
    globs, promptfoo_args = args[:split], args[split:]
    cases = select_cases(globs)
    conditions = ("leaf", "html") if condition == "both" else (condition,)
    # Only the Leaf condition runs on more than the working tree.
    if base is not None and "leaf" in conditions:
        base = base_ref(base)
        # An optional value takes the next word, so `--base CASE` names a ref.
        if subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--verify", "-q", f"{base}^{{commit}}"],
            capture_output=True,
            check=False,
        ).returncode:
            raise click.BadParameter(
                f"no commit {base!r}; put cases before --base", param_hint="--base"
            )
    else:
        base = None
    if not PROMPTFOO.is_file():
        raise click.ClickException(
            "Install eval dependencies first: npm ci --prefix evals"
        )
    RUNS.mkdir(parents=True, exist_ok=True)
    out = Path(
        tempfile.mkdtemp(
            prefix=f"{datetime.now().astimezone():%Y%m%d-%H%M%S}-", dir=RUNS
        )
    )
    with tempfile.TemporaryDirectory(prefix="leaf-eval-") as temporary:
        scratch = Path(temporary)
        refs = {"base": base} if base else {}
        refs["candidate"] = None
        commits = {arm: build_arm(ref, scratch / arm) for arm, ref in refs.items()}
        config = prepare(
            cases,
            {arm: scratch / arm for arm in commits},
            scratch,
            HARNESSES if harness == "both" else (harness,),
            conditions,
            out / "samples",
        )
        config["description"] = describe(
            commits.get("base"), commits["candidate"], globs
        )
        config_file = out / "promptfooconfig.json"
        config_file.write_text(json.dumps(config, indent=2) + "\n")
        # Promptfoo resolves the agent SDK packages from the config's directory.
        (out / "node_modules").symlink_to(ROOT / "evals/node_modules")
        click.echo(config["description"])
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
        status = subprocess.run(
            [
                str(PROMPTFOO),
                "eval",
                "-c",
                str(config_file),
                "--no-cache",
                "--no-share",
                "--max-concurrency",
                "2",
                "-o",
                str(out / "results.json"),
                *promptfoo_args,
            ],
            cwd=ROOT / "evals",
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        ).returncode
    click.echo(f"evidence: {out}\nview: npm run view --prefix evals")
    sys.exit(status)
