"""Run the eval catalog through Promptfoo on Claude Code and Codex.

This command does only what Promptfoo cannot: it builds each Leaf arm (the working
tree, and with `--base` a ref), gives each provider a home of its own seeded with the
harness's login, and expands the catalog's task/context addresses into Promptfoo tests.
Native probes install the complete arm as a plugin and read it in fresh sessions;
short authoring cases use isolated tool-capable children and grade the saved page;
Codex shares one server per provider home while starting fresh ephemeral, read-only
threads for each test.
Promptfoo owns the rest: repetition, concurrency, assertions, the console table, and
the result database its viewer reads. Arguments after the cases go to `promptfoo eval`.

A provider is one column of the results: a harness on one arm (`claude-code/candidate`),
suffixed `/authoring` for tool-capable short cases or `/workflow` for complete
tasks, and on arm `html` for the plain HTML control. A workflow column names the
Leaf transport its harness session takes where the harness has more than one
(`codex:app-server/base/workflow`),
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
    codex_program,
    environment,
    install_codex_plugin,
    instruction_context,
)
from leaf_dev.eval_cases import definition
from leaf_dev.leaf_assets import pinned_copy

PROMPTFOO = ROOT / "node_modules/.bin/promptfoo"
RUNS = ROOT / ".tmp/eval"
SKILL_PREFIX = definition("eval")["skill_prefix"]


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
            case = context_case(source, address)
            metadata = case.get("metadata", {})
            if metadata.get("authoring") and metadata.get("executor"):
                raise click.ClickException(
                    f"eval case {address}: metadata.authoring and metadata.executor "
                    "select different execution modes; declare only one"
                )
            if executor := metadata.get("executor"):
                case["assert"] = definition(executor.rsplit(".", 1)[1])["cases"][
                    case["metadata"]["scenario"]
                ]["assert"]
            cases[address] = case
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


def native_provider(
    harness: str, payload: Path, work: Path
) -> tuple[dict, Path | None]:
    """A read-only native agent and its explicitly invocable installed skill."""
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
        }, None
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
    try:
        installed = install_codex_plugin(
            codex, payload, cwd=work, env=environment(**cli_env)
        )
    except subprocess.CalledProcessError as error:
        raise click.ClickException(
            f"Codex plugin installation failed:\n{error.stdout}{error.stderr}"
        ) from error
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
    }, installed / "skills/leaf/SKILL.md"


def render_prompt(context: dict) -> str | list[dict]:
    """Use native skill input on Codex shipped-skill probes, keeping one table row."""
    prompt = context["vars"]["prompt"]
    skill = context["config"]["leaf_skills"].get(context["provider"]["label"])
    if skill is None:
        return prompt
    return [
        {"type": "skill", "name": "leaf", "path": skill},
        {"type": "text", "text": prompt.removeprefix(SKILL_PREFIX)},
    ]


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


def screenshot_judge(screenshots: Path | None, home: Path) -> dict:
    """The Codex visual grader for `agent-rubric`s, run under a home of its own.

    Its permission profile lets it read the run's screenshot tree and nothing else,
    so only copied images are available as filesystem evidence. An assertion may
    supply authored HTML to identify image references; transcripts and paths naming
    the arm remain outside the judge's input. Passing None leaves evidence access
    to each call's isolated profile,
    so an assertion can grant exactly one sample instead of the run's whole tree.
    `:minimal` is the runtime paths tools need, which include the temp
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
            *([f'{json.dumps(f"{screenshots}/**")} = "read"'] if screenshots else []),
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
    skills = {}
    tests = []
    # Judged screenshots sit apart from the rest of the evidence, for the judge.
    screenshots = samples.with_name("screenshots")
    judge = None
    for address in cases:
        test = definitions[address]
        metadata = test.get("metadata", {})
        executor = metadata.get("executor")
        authoring = metadata.get("authoring", False)
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
                        else f"{workflow_harness(harness)}/{arm}/authoring"
                        if authoring
                        else f"{harness}/{arm}"
                        + (f"/instructions:{instructions}" if instructions else "")
                    )
                    if label not in providers:
                        if executor or authoring:
                            configured = workflow_provider(
                                harness, condition, payload, samples, screenshots
                            )
                        else:
                            work = scratch / "work" / label
                            work.mkdir(parents=True)
                            configured, skill = native_provider(harness, payload, work)
                            if skill is not None and not instructions:
                                skills[label] = str(skill)
                            if instructions:
                                field = (
                                    "append_system_prompt"
                                    if harness == ClaudeCodeHarness.name
                                    else "developer_instructions"
                                )
                                configured["config"][field] = instruction_context(
                                    payload, instructions
                                )
                        providers[label] = {**configured, "label": label}
                    labels.append(label)
            if not labels:
                continue
            sample = deepcopy(test)
            task = address.split("/", 1)[0]
            if executor:
                module = import_module(executor)
                checks = (
                    []
                    if "providerOutput" in test
                    else module.expected_checks(
                        metadata["scenario"], condition=condition
                    )
                )
                rubrics = test["assert"]
                if (
                    any(r["type"].endswith("agent-rubric") for r in rubrics)
                    and judge is None
                ):
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
                    # Semantic answer rubrics and rendered screenshot rubrics.
                    *(
                        {
                            **rubric,
                            **(
                                {
                                    "config": {
                                        **rubric["config"],
                                        "judge": {
                                            "id": f"python:{ROOT / 'dev/leaf_dev/arrangement_eval.py'}",
                                            "config": {
                                                "pythonExecutable": sys.executable,
                                                # Allow setup and retirement around
                                                # the native judge's 20-minute turn.
                                                "timeout": 30 * 60 * 1000,
                                            },
                                        },
                                    }
                                }
                                if isinstance(rubric.get("value"), str)
                                and rubric["value"].endswith("/authoring_assertion.mjs")
                                else {"provider": judge}
                                if rubric["type"].endswith("agent-rubric")
                                else {}
                            ),
                        }
                        for rubric in rubrics
                    ),
                ]
                sample["vars"] = {"prompt": address}
            else:
                sample["vars"] = {
                    **sample["vars"],
                    "prompt": ("" if instructions else SKILL_PREFIX)
                    + sample["vars"]["prompt"],
                }
                if authoring:
                    for assertion in sample["assert"]:
                        if assertion["type"].endswith("agent-rubric"):
                            if judge is None:
                                judge = screenshot_judge(screenshots, scratch / "judge")
                            assertion["provider"] = judge
                    sample["assert"] = [
                        *(
                            {
                                "type": "javascript",
                                "value": f"context.providerResponse.metadata?.checks?.[{json.dumps(check)}] === true",
                                "metric": check,
                            }
                            for check in ("completed", "page-valid")
                        ),
                        *sample["assert"],
                    ]
                images = None if authoring else pinned_copy(ROOT / "evals" / task)
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
        "prompts": [
            {
                "id": f"file://{Path(__file__)}:{render_prompt.__name__}",
                "label": "task",
                # Promptfoo merges a prompt's config into every provider's, so its
                # key must be one no provider reads: the Agent SDK takes `skills`.
                "config": {"leaf_skills": skills},
            }
        ],
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
    required=True,
    help="The harness the motivating failure came from, or the one you work in.",
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
    `pnpm run eval:view` opens the results.
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
            "Install development dependencies first: pnpm install --frozen-lockfile"
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
        # Live regrading and pair comparisons must serve the original runtime
        # after this invocation's private configuration directory is retired.
        payloads = {arm: out / "arms" / arm for arm in refs}
        commits = {arm: build_arm(ref, payloads[arm]) for arm, ref in refs.items()}
        config = prepare(
            cases,
            payloads,
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
        (out / "node_modules").symlink_to(ROOT / "node_modules")
        click.echo(config["description"])
        env = environment(
            PROMPTFOO_DISABLE_TELEMETRY="1",
            PROMPTFOO_DISABLE_UPDATE_CHECK="1",
            PROMPTFOO_ASSERTIONS_MAX_CONCURRENCY="1",
            PROMPTFOO_PYTHON=sys.executable,
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
                "1",
                "-o",
                str(out / "results.json"),
                *promptfoo_args,
            ],
            cwd=ROOT / "evals",
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        ).returncode
    click.echo(f"evidence: {out}\nview: pnpm run eval:view")
    sys.exit(status)
