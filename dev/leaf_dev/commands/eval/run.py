"""Run the eval catalog through Promptfoo on Claude Code and Codex.

This command does only what Promptfoo cannot: it builds each Leaf arm (`head` from the
working tree, and with `--base` a `base` at the merge base or a ref, as
`choose_arms(payload=True)` copies them), gives each provider a home of its own seeded
with the harness's login, and expands the catalog's task/context addresses into
Promptfoo tests.
Native probes install the complete arm as a plugin and read it in fresh sessions;
short authoring cases use isolated tool-capable children and grade the saved page;
Codex shares one server per provider home while starting fresh ephemeral, read-only
threads for each test.
Promptfoo owns the rest: repetition, concurrency, assertions, the console table, and
the result database its viewer reads. Arguments after the cases go to `promptfoo eval`.

A provider is one column of the results: a harness on one arm (`claude-code/head`),
suffixed `/authoring` for tool-capable short cases or `/workflow` for complete
tasks, and on arm `html` for the plain HTML control. A workflow column names the
Leaf transport its harness session takes where the harness has more than one
(`codex:app-server/base/workflow`),
since a workflow scores only that transport. A test is one catalog address under one
condition.

`--from RUN` grades a retained run's saved outputs again instead of authoring:
each test replays one saved result in that result's column, graded by its case's
assertions as this checkout states them, and `--judge` names a judgment to make of
the saved samples instead (`regrade.py` owns the replay and the judgments). Its
results join Promptfoo's store and viewer like any other run's.
"""

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from copy import deepcopy
from datetime import datetime
from functools import cache, partial
from importlib import import_module
from pathlib import Path

import click
import yaml
from click.core import ParameterSource

from leaf.harness import ClaudeCodeHarness
from leaf_dev import ROOT
from leaf_dev.arms import (
    HARNESSES,
    JUDGE_MODELS,
    MODELS,
    TURN_LIMIT,
    WORKFLOW_LIMIT,
    base_option,
    child_class,
    choose_arms,
    claude_child,
    codex_home,
    codex_program,
    describe,
    environment,
    install_codex_plugin,
    instruction_context,
)
from leaf_dev.browser import WINDOWS
from leaf_dev.eval_cases import DEFAULT_VIEWPORTS, definition
from leaf_dev.eval_records import run_samples
from leaf_dev.leaf_assets import pinned_copy
from leaf_dev.regrade import REPLAY, judgment
from leaf_dev.screenshot_judge import screenshot_judge

PROMPTFOO = ROOT / "node_modules/.bin/promptfoo"
RUNS = ROOT / ".tmp/eval"
SKILL_PREFIX = definition("eval")["skill_prefix"]
NOW = definition("eval")["now"]


def context_case(source: dict, address: str) -> dict:
    """A named diagnostic overrides the primary, inheriting its metadata and vars."""
    primary = {key: value for key, value in source.items() if key != "variants"}
    if "/" not in address:
        return primary
    variant = source["variants"][address.split("/", 1)[1]]
    return {
        **primary,
        **variant,
        "metadata": {**primary["metadata"], **variant.get("metadata", {})},
        "vars": {**primary.get("vars", {}), **variant.get("vars", {})},
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
    harness: str, payload: Path, work: Path, model: str | None = None
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
    temporary = work / "tmp"
    temporary.mkdir()
    cli_env = {
        "HOME": str(home),
        "CODEX_HOME": str(config_home),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "TMPDIR": str(temporary),
        "TMPPREFIX": str(temporary / "zsh"),
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
            "model": model or MODELS["codex"],
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
    harness: str,
    condition: str,
    payload: Path,
    samples: Path,
    screenshots: Path,
    viewports: tuple[str, ...],
    model: str | None = None,
) -> dict:
    """The Python provider that hands one complete task to its declared executor."""
    return {
        "id": f"file://{ROOT / 'dev/leaf_dev/scenario_provider.py'}",
        "config": {
            # `eval run` drops CLAUDE_CONFIG_DIR from Promptfoo's environment, so native
            # providers can't read the user's settings; executors need it to find
            # the login (`claude_child`).
            "claude_config_dir": os.environ.get(
                "CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")
            ),
            "harness": harness,
            "model": model or MODELS[harness],
            "condition": condition,
            "payload": str(payload),
            "samples": str(samples),
            "screenshots": str(screenshots),
            "viewports": list(viewports),
            "pythonExecutable": sys.executable,
            "timeout": WORKFLOW_LIMIT * 1000,
            # A retry would replace a failed, side-effecting sample with a new one.
            "maxRetries": 0,
        },
    }


def grading(test: dict, condition: str, judge: Callable[[], dict]) -> dict:
    """A case's assertions and grading options under one condition, for a sample
    authored now or one saved earlier.

    `judge` returns the screenshot judge an agent rubric uses, made on first use.
    """
    metadata = test.get("metadata", {})
    executor = metadata.get("executor")
    options = {}
    if executor:
        checks = (
            []
            if "providerOutput" in test
            else import_module(executor).expected_checks(
                metadata["scenario"], condition=condition
            )
        )
    elif metadata.get("authoring"):
        checks = ["completed", "page-valid"]
    else:
        checks = []
        options = {
            "options": {
                "rubricPrompt": definition("eval")["source_grading_prompt"],
                **test.get("options", {}),
            }
        }
    assertions = [
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
                    {"provider": judge()}
                    if rubric["type"].endswith("agent-rubric")
                    else {}
                ),
            }
            for rubric in deepcopy(test["assert"])
        ),
    ]
    for assertion in assertions:
        value = assertion.get("value")
        if isinstance(value, str) and value.endswith("/authoring_assertion.mjs"):
            assert isinstance(assertion["config"], dict)
            assertion["config"]["judge"] = {
                "id": f"python:{ROOT / 'dev/leaf_dev/arrangement_eval.py'}",
                "config": {
                    "pythonExecutable": sys.executable,
                    # Allow setup and retirement around the native judge's
                    # 20-minute turn, for workflows and short authoring alike.
                    "timeout": 30 * 60 * 1000,
                },
            }
        if isinstance(value, str) and value.startswith("file://"):
            assertion["value"] = (
                f"file://{ROOT / 'evals' / value.removeprefix('file://')}"
            )
    return {"assert": assertions, **options}


def prepare(
    cases: list[str],
    arms: dict[str, Path],
    scratch: Path,
    harnesses: tuple[str, ...],
    conditions: tuple[str, ...],
    samples: Path,
    viewports: tuple[str, ...] = DEFAULT_VIEWPORTS,
    model: str | None = None,
) -> dict:
    """One test per selected address and condition, run on each column it applies to."""
    definitions = catalog()
    providers: dict[str, dict] = {}
    skills = {}
    tests = []
    # Judged screenshots sit apart from the rest of the evidence, for the judge.
    screenshots = samples.with_name("screenshots")
    judge = cache(lambda: screenshot_judge(screenshots, scratch / "judge-login"))
    for address in cases:
        test = definitions[address]
        metadata = test.get("metadata", {})
        executor = metadata.get("executor")
        authoring = metadata.get("authoring", False)
        instructions = metadata.get("instructions")
        for condition in conditions:
            if condition not in metadata.get("conditions", ["leaf"]):
                continue
            columns = arms if condition == "leaf" else {condition: arms["head"]}
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
                                harness,
                                condition,
                                payload,
                                samples,
                                screenshots,
                                viewports,
                                model,
                            )
                        else:
                            # One flat directory per label: a nested one would
                            # sit inside the plain arm's ("claude-code/base").
                            work = scratch / "work" / label.replace("/", "--")
                            work.mkdir(parents=True)
                            configured, skill = native_provider(
                                harness, payload, work, model
                            )
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
            sample = {**deepcopy(test), **grading(test, condition, judge)}
            task = address.split("/", 1)[0]
            if executor:
                sample["vars"] = {"prompt": address}
            else:
                # A prompt may reuse another task's request, named under `evals/`.
                prompt = sample["vars"]["prompt"]
                if prompt.startswith("file://"):
                    prompt = (
                        ROOT / "evals" / prompt.removeprefix("file://")
                    ).read_text()
                # An authoring agent's page dates its events by the real clock, so only
                # a reading probe is told the time its fixtures were written at.
                now = sample["vars"].pop("now", NOW)
                if not authoring:
                    prompt = f"It is now {now}.\n\n{prompt}"
                sample["vars"] = {
                    **sample["vars"],
                    "prompt": (
                        "" if instructions or condition == "html" else SKILL_PREFIX
                    )
                    + prompt,
                }
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
            tests.append(
                {
                    **sample,
                    "providers": labels,
                    "metadata": {**metadata, "case": address, "condition": condition},
                }
            )
    if not tests:
        raise click.BadParameter(
            "selected cases have no requested harness/condition",
            param_hint="--harness/--condition",
        )
    return promptfoo_config(list(providers.values()), tests, skills)


def promptfoo_config(
    providers: list[dict], tests: list[dict], skills: dict[str, str]
) -> dict:
    """A Promptfoo config of these columns and tests, with the pinned text judge."""
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
        "providers": providers,
        "tests": tests,
        "defaultTest": {
            "options": {
                "provider": {
                    "id": "anthropic:claude-agent-sdk",
                    "config": {
                        "model": JUDGE_MODELS[ClaudeCodeHarness.name],
                        "apiKeyRequired": False,
                        "persist_session": False,
                    },
                }
            }
        },
    }


def saved_config(
    runs: tuple[Path, ...],
    globs: tuple[str, ...],
    judge: str | None,
    out: Path,
    scratch: Path,
) -> dict:
    """Tests that grade RUNS' saved outputs again, each replaying the saved results it
    names: by its case's current assertions, or by the named judgment."""
    selected: dict[str, dict[str, list[dict]]] = {}
    unjudged = 0
    matched = set()
    for subject, columns in run_samples(runs).items():
        for column, members in columns.items():
            for sample in members:
                case = sample["result"]["testCase"]["metadata"]["case"]
                patterns = {g for g in globs if fnmatch.fnmatch(case, g)}
                if globs and not patterns:
                    continue
                matched |= patterns
                if judge and "comparison" not in sample["diagnostics"]:
                    unjudged += 1
                else:
                    selected.setdefault(subject, {}).setdefault(column, []).append(
                        sample
                    )
    for pattern in globs:
        if pattern not in matched:
            raise click.BadParameter(
                f"no saved output matches {pattern!r}", param_hint="CASE"
            )
    if unjudged:
        click.echo(f"{unjudged} results saved no task for a judge")
    evidence = out / "judgments"
    tests: list[dict] = []
    if judge == "pair":
        for subject, (first, x), (second, y), number in saved_pairs(selected):
            orders = (((first, x), (second, y)), ((second, y), (first, x)))
            for order, members in enumerate(orders, 1):
                tests.append(
                    {
                        "description": f"{subject} · pair {number} · order {order}",
                        "vars": x["result"]["testCase"]["vars"],
                        "assert": [judgment("pair", evidence)],
                        "providers": [f"{first} vs {second}"],
                        "metadata": {
                            "judgment": "pair",
                            "subject": subject,
                            "pair": number,
                            "order": order,
                            "saved": [saved(s, column) for column, s in members],
                        },
                    }
                )
    else:
        definitions = catalog()
        # An agent rubric's judge may read only the screenshots of the sample's run.
        judges = cache(
            lambda shots: screenshot_judge(
                shots, Path(tempfile.mkdtemp(dir=scratch)) / "login"
            )
        )
        for subject, columns in selected.items():
            for column, members in columns.items():
                for sample in members:
                    test = sample["result"]["testCase"]
                    if judge is None:
                        case = test["metadata"]["case"]
                        if case not in definitions:
                            raise click.ClickException(
                                f"{case} is no longer in the catalog; select other "
                                "cases to grade by their current assertions"
                            )
                        metadata = test["metadata"]
                        graded = grading(
                            definitions[case],
                            metadata["condition"],
                            partial(judges, sample["shots"].parent),
                        )
                    else:
                        metadata = {"judgment": judge, "subject": subject}
                        graded = {"assert": [judgment(judge, evidence)]}
                    tests.append(
                        {
                            "description": f"{test.get('description') or subject}"
                            f" · {sample['sample']}",
                            "vars": test["vars"],
                            **graded,
                            "providers": [column],
                            "metadata": {**metadata, "saved": [saved(sample, column)]},
                        }
                    )
    if not tests:
        raise click.ClickException("the saved runs hold nothing to grade")
    providers = [
        {"id": REPLAY, "label": label}
        for label in dict.fromkeys(test["providers"][0] for test in tests)
    ]
    return promptfoo_config(providers, tests, {})


def saved(sample: dict, column: str) -> dict:
    """What a test records of a saved result it replays."""
    return {
        "run": str(sample["runs"][0]),
        "result": sample["result_id"],
        "column": column,
        "sample": sample["sample"],
    }


def saved_pairs(
    selected: dict[str, dict[str, list[dict]]],
) -> Iterator[tuple[str, tuple[str, dict], tuple[str, dict], int]]:
    """Each task's Nth sample in one column beside its Nth in the other, in the order
    the runs and their results list them."""
    for subject, columns in sorted(selected.items()):
        if len(columns) != 2:
            click.echo(f"{subject}: {len(columns)} columns, not 2; not paired")
            continue
        (first, xs), (second, ys) = sorted(columns.items())
        if len(xs) != len(ys):
            click.echo(
                f"{subject}: {first} has {len(xs)} samples and {second} has "
                f"{len(ys)}; the extra ones are not paired"
            )
        for number, (x, y) in enumerate(zip(xs, ys, strict=False), 1):
            yield subject, (first, x), (second, y), number


def run_name(scope: str, globs: tuple[str, ...]) -> str:
    """The run's name in Promptfoo's viewer: branch, what it grades and the cases."""
    branch = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{branch} ({scope}): {' '.join(globs) or 'all tasks'}"


@click.command("run", context_settings={"ignore_unknown_options": True})
@click.argument("args", metavar="[CASE]... [PROMPTFOO_OPTION]...", nargs=-1)
@click.option(
    "--from",
    "runs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
    help="Grade this run's saved outputs again instead of authoring; repeat to add runs.",
)
@click.option(
    "--judge",
    type=click.Choice(["pair", "discovery"]),
    help="Judge the --from samples pairwise, or explore each for observations, "
    "instead of grading them by their cases' current assertions.",
)
@base_option()
@click.option(
    "--harness",
    type=click.Choice([*HARNESSES, "both"]),
    help="The harness the motivating failure came from, or the one you work in.",
)
@click.option(
    "--model",
    help="Codex author model for this run; all selected conditions use the same model.",
)
@click.option(
    "--condition",
    type=click.Choice(["leaf", "html", "both"]),
    default="leaf",
    show_default=True,
)
@click.option(
    "--viewport",
    "viewports",
    type=click.Choice(list(WINDOWS)),
    multiple=True,
    default=DEFAULT_VIEWPORTS,
    show_default=True,
    help="Window size for all authored-task comparisons in this run; repeat to check more.",
)
@click.pass_context
def eval(
    context: click.Context,
    args: tuple[str, ...],
    runs: tuple[Path, ...],
    judge: str | None,
    base: str | None,
    harness: str | None,
    model: str | None,
    condition: str,
    viewports: tuple[str, ...],
):
    """Score CASE globs or task/context addresses on the working tree, or grade a
    saved run's outputs again with --from.

    Options Promptfoo takes follow the cases, such as `--repeat 3` or `-j 4`.
    `pnpm run eval:view` opens the results.
    """
    split = next((i for i, arg in enumerate(args) if arg.startswith("-")), len(args))
    globs, promptfoo_args = args[:split], args[split:]
    if runs:
        # Every other option chooses what to author.
        authoring = [
            option.opts[0]
            for option in context.command.params
            if isinstance(option, click.Option)
            and option.name not in {"runs", "judge"}
            and context.get_parameter_source(option.name) is not ParameterSource.DEFAULT
        ]
        if authoring:
            raise click.UsageError(
                f"{', '.join(authoring)} choose what to author; --from grades "
                "saved outputs"
            )
    elif judge is not None:
        raise click.UsageError(
            "--judge grades saved outputs; name their runs with --from"
        )
    elif harness is None:
        raise click.UsageError("Missing option '--harness'.")
    else:
        cases = select_cases(globs)
        harnesses = HARNESSES if harness == "both" else (harness,)
        if model is not None and harness != "codex":
            raise click.BadParameter(
                "--model currently requires --harness codex", param_hint="--model"
            )
        conditions = ("leaf", "html") if condition == "both" else (condition,)
        # Only the Leaf condition runs on more than the working tree.
        if "leaf" not in conditions:
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
    click.echo(f"evidence: {out}")
    with tempfile.TemporaryDirectory(prefix="leaf-eval-") as temporary:
        scratch = Path(temporary)
        if runs:
            config = saved_config(runs, globs, judge, out, scratch)
            graded = f"{judge} judgment" if judge else "current assertions"
            config["description"] = run_name(
                f"{graded} of saved {' '.join(run.name for run in runs)}", globs
            )
        else:
            # Grading again with --from must serve the original runtime after this
            # invocation's private configuration directory is retired.
            arms = choose_arms(base, out, payload=True)
            config = prepare(
                cases,
                {name: arm.directory for name, arm in arms.items()},
                scratch,
                harnesses,
                conditions,
                out / "samples",
                viewports,
                model,
            )
            config["description"] = run_name(describe(arms), globs) + (
                f" [{model}]" if model else ""
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
    click.echo("view: pnpm run eval:view")
    sys.exit(status)
