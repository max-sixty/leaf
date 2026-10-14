"""The catalog expands into Promptfoo tests run on one column per harness and arm."""

import json
import os
import subprocess
import sys
from pathlib import Path

import click
import pytest
import yaml
from leaf_dev.eval import catalog, native_provider, prepare, select_cases
from leaf_dev.review_detection_eval import grading, summarize


@pytest.mark.usefixtures("codex_cli")
def test_ui_review_judge_has_no_run_wide_evidence_grant(tmp_path, monkeypatch):
    """Only the assertion's per-sample profile grants evidence access."""
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text('{"fixture": "local-login"}')
    monkeypatch.setenv("CODEX_HOME", str(login))
    output = tmp_path / "run"
    output.mkdir()
    settings = grading(output, tmp_path / "judge")["metadata"]
    provider = settings["graderProvider"]["config"]
    profile = (Path(provider["cli_env"]["CODEX_HOME"]) / "config.toml").read_text()
    assert [line for line in profile.splitlines() if line.endswith('"read"')] == [
        '":minimal" = "read"',
        f'"{provider["codex_path_override"]}" = "read"',
    ]
    assert str(output) not in profile


def test_ui_review_summary_keeps_execution_and_grading_failures_unscored(tmp_path):
    """Promptfoo errors must not become misses or inflate control denominators."""
    rows = []
    for variant, detection, alarm, error in (
        ("timeline-defect", 2, None, None),
        ("shift-defect", 0, None, None),
        ("timeline-control", None, 0, None),
        ("shift-control", None, 1, None),
        ("timeline-defect", None, None, "provider transport failed"),
        ("timeline-control", None, None, "invalid judge JSON"),
    ):
        grade = {
            "scorable": True,
            "target_detection": detection,
            "target_false_alarm": alarm,
            "unsupported_observations": [],
        }
        rows.append(
            {
                "testCase": {
                    "metadata": {
                        "privateCase": "recording-times"
                        if variant.startswith("timeline")
                        else "recording-stepping",
                        "privateVariant": variant,
                    }
                },
                "provider": {"label": "anonymous/no-tools"},
                "response": {"metadata": {"evidenceDir": "sample"}},
                "gradingResult": {
                    "componentResults": []
                    if error
                    else [{"metadata": {"grade": grade}}]
                },
                "error": error,
            }
        )
    (tmp_path / "results.json").write_text(json.dumps({"results": {"results": rows}}))
    summary = summarize(tmp_path)
    assert {key: value for key, value in summary.items() if key != "rows"} == {
        "samples": 6,
        "scored": 4,
        "unscored": 2,
        "defects": 2,
        "detected": 1,
        "concerns": 0,
        "missed": 1,
        "controls": 2,
        "target_false_alarms": 1,
        "unsupported_observations": 0,
    }
    assert [row["grade"] for row in summary["rows"][-2:]] == [None, None]
    assert [row["error"] for row in summary["rows"][-2:]] == [
        "provider transport failed",
        "invalid judge JSON",
    ]
    assert json.loads((tmp_path / "grading-summary.json").read_text()) == summary


@pytest.fixture
def codex_cli(monkeypatch):
    """Use the eval dependency's real CLI for model-free installation checks;
    the suite otherwise puts a failing harness stub ahead of installed programs."""
    programs = Path(__file__).parents[2] / "node_modules/.bin"
    assert (programs / "codex").is_file(), (
        "Install eval dependencies with pnpm install --frozen-lockfile"
    )
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")


def arms(tmp_path, *names):
    payloads = {}
    for arm in names:
        skill = tmp_path / arm / "skills" / "leaf"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"{arm} instructions")
        payload = tmp_path / arm
        for name in (".agents/plugins/marketplace.json", ".codex-plugin/plugin.json"):
            target = payload / name
            target.parent.mkdir(parents=True)
            target.write_bytes((Path(__file__).parents[2] / name).read_bytes())
        (payload / "bin").mkdir()
        (payload / "bin" / "leaf").write_text(f"{arm} launcher")
        (skill / "assets").mkdir()
        (skill / "assets" / "registry.json").write_text(json.dumps({"arm": arm}))
        payloads[arm] = tmp_path / arm
    return payloads


@pytest.mark.parametrize("address", sorted(catalog()))
def test_library_cases_supply_a_task_and_native_promptfoo_assertions(address):
    case = catalog()[address]
    if case.get("metadata", {}).get("executor"):
        assert case["metadata"]["scenario"]
        return
    assert case["vars"]["prompt"].strip()
    assert case["assert"]
    assert all(assertion["type"] and assertion["value"] for assertion in case["assert"])


def test_catalog_rejects_execution_modes_conflicting_after_variant_inheritance(
    tmp_path, monkeypatch
):
    from leaf_dev import eval as module

    path = tmp_path / "evals" / "example" / "case.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "metadata": {"authoring": True},
                "variants": {
                    "workflow": {"metadata": {"executor": "leaf_dev.arrangement_eval"}}
                },
            }
        )
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    with pytest.raises(
        click.ClickException, match="eval case example/workflow:.*declare only one"
    ):
        catalog()


def test_authoring_instruction_sources_stay_per_sample_with_the_task(
    tmp_path, monkeypatch
):
    from leaf_dev import eval as module

    sources = {
        "first": ".claude/skills/developing-leaf/SKILL.md",
        "second": ".claude/skills/ui-sweep/SKILL.md",
    }
    monkeypatch.setattr(
        module,
        "catalog",
        lambda: {
            address: {
                "metadata": {"authoring": True, "instructions": source},
                "vars": {"prompt": f"{address} task"},
                "assert": [{"type": "javascript", "value": "true"}],
            }
            for address, source in sources.items()
        },
    )
    config = prepare(
        list(sources),
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf",),
        tmp_path / "samples",
    )
    assert len(config["providers"]) == 1
    for test in config["tests"]:
        address = test["metadata"]["case"]
        assert test["metadata"]["instructions"] == sources[address]
        assert test["vars"]["prompt"] == f"{address} task"


@pytest.mark.usefixtures("codex_cli")
def test_native_columns_isolate_each_harness_and_arm(tmp_path, monkeypatch):
    login = tmp_path / "harness-login"
    login.mkdir()
    (login / "auth.json").write_text('{"fixture": "local-login"}')
    monkeypatch.setenv("CODEX_HOME", str(login))
    claude_login = tmp_path / "claude-login"
    claude_login.mkdir()
    (claude_login / ".credentials.json").write_text('{"fixture": "claude-login"}')
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_login))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-config")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-enter-config")
    payloads = arms(tmp_path, "base", "candidate")
    config = prepare(
        ["brief-document-needs-no-outline", "options-stay-words-for-wording"],
        payloads,
        tmp_path / "scratch",
        ("claude-code", "codex"),
        ("leaf",),
        tmp_path / "samples",
    )
    labels = [
        "claude-code/base",
        "claude-code/candidate",
        "codex/base",
        "codex/candidate",
    ]
    assert [provider["label"] for provider in config["providers"]] == labels
    assert [test["providers"] for test in config["tests"]] == [labels, labels]
    homes = []
    for provider in config["providers"]:
        harness, arm = provider["label"].split("/")
        settings = provider["config"]
        assert Path(settings["working_dir"]).is_dir()
        if harness == "claude-code":
            homes.append(settings["env"]["HOME"])
            assert settings["plugins"][0]["path"] == str(payloads[arm])
            private_config = Path(settings["env"]["HOME"]) / ".claude"
            assert json.loads((private_config / ".credentials.json").read_text()) == {
                "fixture": "claude-login"
            }
        else:
            homes.append(settings["cli_env"]["HOME"])
            home = Path(settings["cli_env"]["CODEX_HOME"])
            skill = next(home.glob("plugins/cache/leaf/leaf/*/skills/leaf/SKILL.md"))
            assert skill.read_text() == f"{arm} instructions"
    assert len(set(homes)) == 4
    assert "must-not-enter-config" not in json.dumps(config)
    brief = config["tests"][0]
    assert brief["description"] == "brief-document-needs-no-outline"
    assert brief["vars"]["prompt"].startswith("Use the Leaf skill")
    assert [assertion["metric"] for assertion in brief["assert"]] == ["judgment"]

    # Exercise Promptfoo's actual Python prompt loader and provider selection
    # without a model. Echo retains the native input exactly as rendered.
    config["providers"] = [{"id": "echo", "label": label} for label in labels]
    config.pop("defaultTest")
    for test in config["tests"]:
        test["assert"] = [{"type": "javascript", "value": "true"}]
    config_path = tmp_path / "promptfoo.json"
    config_path.write_text(json.dumps(config))
    results = tmp_path / "results.json"
    root = Path(__file__).parents[2]
    subprocess.run(
        [
            str(root / "node_modules/.bin/promptfoo"),
            "eval",
            "-c",
            str(config_path),
            "--no-cache",
            "--no-share",
            "-o",
            str(results),
        ],
        env={
            **os.environ,
            "PROMPTFOO_PYTHON": sys.executable,
            "PROMPTFOO_DISABLE_TELEMETRY": "1",
            "PROMPTFOO_DISABLE_UPDATE_CHECK": "1",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    rows = json.loads(results.read_text())["results"]["results"]
    assert len(rows) == len(labels) * len(config["tests"])
    for row in rows:
        label = row["provider"]["label"]
        output = row["response"]["output"]
        address = row["testCase"]["metadata"]["case"]
        task = catalog()[address]["vars"]["prompt"]
        if label.startswith("codex/"):
            skill, text = json.loads(output)
            assert skill == {
                "type": "skill",
                "name": "leaf",
                "path": config["prompts"][0]["config"]["leaf_skills"][label],
            }
            assert (
                Path(skill["path"]).read_text() == f"{label.split('/')[1]} instructions"
            )
            assert text == {"type": "text", "text": task}
        else:
            assert output.endswith(task)
            assert output.startswith("Use the Leaf skill")


@pytest.mark.usefixtures("codex_cli")
def test_authoring_columns_keep_case_assertions_and_create_no_shared_workspace(
    tmp_path,
    monkeypatch,
):
    """Authoring scores saved pages through each arm, retaining the case's criteria."""
    addresses = ["proposals-show-what-they-change", "visual-change-uses-captures"]
    payloads = arms(tmp_path, "base", "candidate")
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    scratch = tmp_path / "scratch"
    config = prepare(
        addresses,
        payloads,
        scratch,
        ("claude-code", "codex"),
        ("leaf",),
        tmp_path / "samples",
    )
    labels = [
        "claude-code/base/authoring",
        "claude-code/candidate/authoring",
        "codex:app-server/base/authoring",
        "codex:app-server/candidate/authoring",
    ]
    assert [provider["label"] for provider in config["providers"]] == labels
    for provider in config["providers"]:
        settings = provider["config"]
        harness, arm, _ = provider["label"].split("/")
        assert settings["harness"] == harness.split(":")[0]
        assert settings["payload"] == str(payloads[arm])
        assert "working_dir" not in settings
    assert not (scratch / "work").exists()
    for address, test in zip(addresses, config["tests"], strict=True):
        assert test["providers"] == labels
        assert test["metadata"]["authoring"] is True
        assert [check["metric"] for check in test["assert"][:2]] == [
            "completed",
            "page-valid",
        ]
        # File helpers are resolved for Promptfoo; that does not change the criteria.
        asset_prefix = f"file://{Path(__file__).parents[2] / 'evals'}/"
        assertions = [
            {
                **{key: value for key, value in check.items() if key != "provider"},
                "value": check["value"].replace(asset_prefix, "file://", 1),
            }
            for check in test["assert"][2:]
        ]
        assert assertions == catalog()[address]["assert"]
        for check in test["assert"][2:]:
            if check["type"].endswith("agent-rubric"):
                judge = check["provider"]["config"]
                profile = (
                    Path(judge["cli_env"]["CODEX_HOME"]) / "config.toml"
                ).read_text()
                assert f'"{tmp_path / "screenshots"}/**" = "read"' in profile
                assert str(tmp_path / "samples") not in profile
            else:
                assert "provider" not in check
        assert test["vars"]["prompt"].endswith(catalog()[address]["vars"]["prompt"])


@pytest.mark.parametrize(
    "address",
    [
        "review-shows-the-change",
        "interaction-proof-follows-the-reader/comparison",
        "visible-outcome-before-handoff/shared-identity",
    ],
)
@pytest.mark.usefixtures("codex_cli")
def test_internal_instruction_cases_receive_their_arms_source(
    tmp_path, monkeypatch, address
):
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    payloads = arms(tmp_path, "base", "candidate")
    source = ".claude/skills/developing-leaf/SKILL.md"
    for arm, payload in payloads.items():
        path = payload / source
        path.parent.mkdir(parents=True)
        path.write_text(f"{arm} maintainer instructions")
    config = prepare(
        [address],
        payloads,
        tmp_path / "scratch",
        ("claude-code", "codex"),
        ("leaf",),
        tmp_path / "samples",
    )
    for provider in config["providers"]:
        harness, arm, _ = provider["label"].split("/", 2)
        field = (
            "append_system_prompt"
            if harness == "claude-code"
            else "developer_instructions"
        )
        injected = provider["config"][field]
        assert str(payloads[arm] / source) in injected
        assert injected.endswith(f"{arm} maintainer instructions")
    assert [check["type"] for check in config["tests"][0]["assert"]] == ["llm-rubric"]
    assert config["tests"][0]["vars"]["prompt"] == catalog()[address]["vars"]["prompt"]
    assert config["prompts"][0]["config"]["leaf_skills"] == {}


def test_instruction_cases_selected_together_each_receive_their_own_source(tmp_path):
    payloads = arms(tmp_path, "candidate")
    addresses = {
        "review-shows-the-change": ".claude/skills/developing-leaf/SKILL.md",
        "review-shows-the-change/capture-first-reading": ".claude/skills/ui-sweep/SKILL.md",
    }
    for source in addresses.values():
        path = payloads["candidate"] / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{source} instructions")
    config = prepare(
        list(addresses),
        payloads,
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf",),
        tmp_path / "samples",
    )
    providers = {p["label"]: p for p in config["providers"]}
    for test in config["tests"]:
        source = addresses[test["metadata"]["case"]]
        for label in test["providers"]:
            injected = providers[label]["config"]["append_system_prompt"]
            assert injected.endswith(f"{source} instructions")


@pytest.mark.usefixtures("codex_cli")
def test_native_codex_discovers_the_complete_arm_with_root_relative_access(
    tmp_path, monkeypatch
):
    """Use Codex's real installer without running a model. A skill-only symlink
    hides the registry from ordinary discovery and loses its plugin-root launcher."""
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    payloads = arms(tmp_path, "candidate")
    work = tmp_path / "work"
    work.mkdir()
    provider, installed_skill = native_provider("codex", payloads["candidate"], work)
    settings = provider["config"]
    home = Path(settings["cli_env"]["CODEX_HOME"])
    registry = next(home.rglob("registry.json"), None)
    assert registry is not None, f"No registry installed under {home}"
    assert json.loads(registry.read_text()) == {"arm": "candidate"}
    skill = registry.parent.parent
    assert (skill / "SKILL.md").read_text() == "candidate instructions"
    assert installed_skill == skill / "SKILL.md"
    assert (skill / "../../bin/leaf").read_text() == "candidate launcher"


def test_native_javascript_assertions_and_asset_addresses_survive_preparation(
    tmp_path, monkeypatch
):
    import leaf_dev.eval as module

    case = tmp_path / "evals" / "example" / "case.yaml"
    case.parent.mkdir(parents=True)
    case.write_text(
        yaml.safe_dump(
            {
                "description": "example",
                "metadata": {},
                "vars": {"prompt": "Task"},
                "assert": [
                    {"type": "javascript", "value": "output.includes('hello')"},
                    {"type": "javascript", "value": "file://custom.cjs:check"},
                ],
            }
        )
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    config = prepare(
        ["example"],
        arms(tmp_path, "candidate"),
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf",),
        tmp_path / "samples",
    )
    assert [check["value"] for check in config["tests"][0]["assert"]] == [
        "output.includes('hello')",
        f"file://{tmp_path / 'evals' / 'custom.cjs'}:check",
    ]


def test_catalog_contexts_keep_complete_original_check_coverage():
    from importlib import import_module

    definitions = catalog()
    assert all("/" not in address for address in select_cases(()))
    assert {
        "document",
        "dashboard",
        "queue",
        "reading",
        "disposable-report",
        "short-chat-answer",
        "unknown-package",
    } <= set(select_cases(()))
    assert select_cases(("reading",)) == ["reading"]
    assert select_cases(("reading/plain",)) == ["reading/plain"]
    assert len(select_cases(("reading/*",))) == 7
    for owner in ("usability", "arrangement", "delivery", "reader"):
        module = import_module(f"leaf_dev.{owner}_eval")
        covered = {
            definition["metadata"]["scenario"]
            for definition in definitions.values()
            if definition["metadata"].get("executor") == f"leaf_dev.{owner}_eval"
        }
        assert covered == set(module.CASES)
    with pytest.raises(click.BadParameter, match="no case matches"):
        select_cases(("no-such-task",))


def test_sidebar_primary_scores_rendered_work_and_retains_instruction_diagnostics():
    from leaf_dev.arrangement_eval import expected_checks
    from leaf_dev.eval_cases import definition

    cases = catalog()
    task = "sidebar-page-at-900px"
    assert cases[task]["metadata"]["executor"] == "leaf_dev.arrangement_eval"
    assert not any(check.startswith("choice-") for check in expected_checks(task))
    assert any(
        "completed rollout" in rubric["value"]
        for rubric in definition("arrangement_eval")["cases"][task]["assert"]
    )
    for variant in ("instructions", "live"):
        case = cases[f"{task}/{variant}"]
        assert case["metadata"]["executor"] is None
        assert "page directory is not reachable" in case["vars"]["prompt"]
        assert case["assert"]


def test_workflows_run_declared_conditions_harnesses_and_fixed_checks(
    tmp_path, monkeypatch
):
    from leaf_dev.arrangement_eval import expected_checks
    from leaf_dev.eval_cases import definition

    login = tmp_path / "harness-login"
    login.mkdir()
    (login / "auth.json").write_text('{"fixture": "local-login"}')
    monkeypatch.setenv("CODEX_HOME", str(login))
    codex = tmp_path / "package" / "codex"
    codex.parent.mkdir()
    codex.write_text("#!/bin/sh\n")
    codex.chmod(0o755)
    # Installed as a symlink beside the user's files, as Homebrew does.
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "codex").symlink_to(codex)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:/usr/bin:/bin")
    payloads = {arm: tmp_path / arm for arm in ("base", "candidate")}
    config = prepare(
        ["dashboard/reader-seeded", "document"],
        payloads,
        tmp_path / "scratch",
        ("claude-code", "codex"),
        ("leaf", "html"),
        tmp_path / "samples",
    )
    tests = {test["description"]: test for test in config["tests"]}
    # The judge calibration runs on Claude Code; the HTML control has no base. A
    # Codex workflow column names the one Leaf transport its session takes.
    assert {name: test["providers"] for name, test in tests.items()} == {
        "dashboard/reader-seeded": [
            "claude-code/base/workflow",
            "claude-code/candidate/workflow",
        ],
        "document": [
            "claude-code/base/workflow",
            "claude-code/candidate/workflow",
            "codex:app-server/base/workflow",
            "codex:app-server/candidate/workflow",
        ],
        "document (html)": [
            "claude-code/html/workflow",
            "codex:app-server/html/workflow",
        ],
    }
    for condition, test in (
        ("leaf", tests["document"]),
        ("html", tests["document (html)"]),
    ):
        assert test["metadata"]["executor"] == "leaf_dev.arrangement_eval"
        assert test["vars"] == {"prompt": "document"}
        assert [check["metric"] for check in test["assert"]] == [
            *expected_checks("document", condition=condition),
            *(
                rubric["metric"]
                for rubric in definition("arrangement_eval")["cases"]["document"][
                    "assert"
                ]
            ),
        ]
        # The screenshot judge may read the run's screenshots and nothing else
        # outside the runtime and its own executable.
        judge = test["assert"][-1]["provider"]["config"]
        assert "sandbox_mode" not in judge
        profile = (Path(judge["cli_env"]["CODEX_HOME"]) / "config.toml").read_text()
        assert [line for line in profile.splitlines() if line.endswith('"read"')] == [
            '":minimal" = "read"',
            f'"{tmp_path / "screenshots"}/**" = "read"',
            f'"{codex.resolve()}" = "read"',
        ]
        assert judge["codex_path_override"] == str(codex.resolve())
    assert "tools" not in config["defaultTest"]["options"]["provider"]["config"]
    html = next(
        provider["config"]
        for provider in config["providers"]
        if provider["label"] == "codex:app-server/html/workflow"
    )
    assert (html["harness"], html["condition"], html["payload"], html["samples"]) == (
        "codex",
        "html",
        str(payloads["candidate"]),
        str(tmp_path / "samples"),
    )
    assert html["screenshots"] == str(tmp_path / "screenshots")
    with pytest.raises(click.BadParameter, match="no requested harness/condition"):
        prepare(
            ["dashboard/reader-seeded"],
            payloads,
            tmp_path / "other",
            ("codex",),
            ("leaf",),
            tmp_path / "samples",
        )


def test_python_provider_gives_each_call_its_own_evidence(tmp_path, monkeypatch):
    from leaf_dev import scenario_provider

    observed = []

    class Executor:
        @staticmethod
        def execute_scenario(case, payload, work, *, harness, condition):
            observed.append((case, payload, work, harness, condition))
            return {"output": "{}"}

    class Judged:
        @staticmethod
        def execute_scenario(case, payload, work, *, shots, harness, condition):
            observed.append(shots)
            return {"output": "{}"}

    executors = {"leaf_dev.usability_eval": Executor, "leaf_dev.reader_eval": Judged}
    monkeypatch.setattr(scenario_provider, "import_module", executors.__getitem__)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "login"))
    options = {
        "config": {
            "payload": str(tmp_path / "payload"),
            "samples": str(tmp_path / "samples"),
            "screenshots": str(tmp_path / "screenshots"),
            "claude_config_dir": str(tmp_path / "login"),
            "harness": "codex",
            "condition": "html",
        }
    }
    context = {
        "vars": {"prompt": "document/resume"},
        "test": {
            "assert": [],
            "metadata": {
                "case": "document/resume",
                "executor": "leaf_dev.usability_eval",
                "scenario": "resume",
            },
        },
    }
    responses = [scenario_provider.call_api("", options, context) for _ in range(2)]
    assert [response["metadata"]["work"] for response in responses] == [
        str(work) for _, _, work, _, _ in observed
    ]
    first, second = observed
    assert first[2] != second[2]
    for case, payload, work, harness, condition in observed:
        assert (case, payload, harness, condition) == (
            "resume",
            tmp_path / "payload",
            "codex",
            "html",
        )
        assert work.parent == tmp_path / "samples"
        assert work.name.startswith("document-resume-")
    # Capture setup belongs to the executor's API; removing its screenshot rubric
    # still supplies the directory it requires. A grader reads that same tree.
    context["test"]["metadata"]["executor"] = "leaf_dev.reader_eval"
    for assertions in ([], [{"type": "agent-rubric"}]):
        context["test"]["assert"] = assertions
        response = scenario_provider.call_api("", options, context)
        assert (
            observed[-1]
            == tmp_path / "screenshots" / Path(response["metadata"]["work"]).name
        )


def test_authoring_provider_preserves_per_call_evidence_and_the_original_prompt(
    tmp_path, monkeypatch
):
    from leaf_dev import authoring_eval, scenario_provider

    observed = []

    def execute(prompt, payload, evidence, metadata, *, harness, shots):
        # Replace only the executor here; the integration test runs its real tools.
        observed.append((prompt, payload, evidence, metadata, harness, shots))
        (evidence / "authored.html").write_text(prompt)
        return {"output": prompt, "metadata": {"checks": {"page-valid": True}}}

    monkeypatch.setattr(authoring_eval, "execute", execute)
    options = {
        "config": {
            "payload": str(tmp_path / "payload"),
            "samples": str(tmp_path / "samples"),
            "screenshots": str(tmp_path / "screenshots"),
            "claude_config_dir": str(tmp_path / "login"),
            "harness": "claude-code",
        }
    }
    metadata = {"authoring": True, "case": "visual-change-uses-captures"}
    context = {"test": {"metadata": metadata}}
    prompt = "Use the captures and write the Leaf page."
    responses = [scenario_provider.call_api(prompt, options, context) for _ in range(2)]
    assert observed[0][2] != observed[1][2]
    for observed_call, response in zip(observed, responses, strict=True):
        request, payload, evidence, received_metadata, harness, shots = observed_call
        assert (request, payload, received_metadata, harness) == (
            prompt,
            tmp_path / "payload",
            metadata,
            "claude-code",
        )
        assert evidence.parent == tmp_path / "samples"
        assert shots == tmp_path / "screenshots" / evidence.name
        assert (evidence / "authored.html").read_text() == prompt
        assert response["metadata"] == {
            "checks": {"page-valid": True},
            "work": str(evidence),
        }


def test_command_passes_promptfoo_options_and_status_without_api_keys(
    tmp_path, monkeypatch
):
    """The command's own edges: case/option split, the optional base arm, the
    environment Promptfoo gets, and its exit status."""
    from click.testing import CliRunner
    from leaf_dev import eval as module

    promptfoo = tmp_path / "promptfoo"
    calls = tmp_path / "calls"
    promptfoo.write_text(
        f'#!/bin/sh\necho "$* key=${{OPENAI_API_KEY:-none}}" >> {calls}\nexit 100\n'
    )
    promptfoo.chmod(0o755)
    built = []

    def build_arm(ref, dest):
        (dest / "skills" / "leaf").mkdir(parents=True)
        built.append(ref)
        return "0123456789abcdef"

    monkeypatch.setattr(module, "PROMPTFOO", promptfoo)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(module, "build_arm", build_arm)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-promptfoo")

    def run(*args):
        return CliRunner().invoke(module.eval, ["--harness", "claude-code", *args])

    result = run("todo-outlasts-the-turn", "--repeat", "3")
    assert result.exit_code == 100, result.output
    assert built == [None]
    assert calls.read_text().strip().endswith("--repeat 3 key=none")
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert [p["label"] for p in config["providers"]] == ["claude-code/candidate"]
    assert config["description"].endswith(
        "(working tree on 012345678): todo-outlasts-the-turn"
    )

    built.clear()
    # A named ref, since CI's checkout has no local main to take a merge base from.
    assert run("todo-outlasts-the-turn", "--base", "HEAD").exit_code == 100
    assert built == ["HEAD", None]

    built.clear()
    result = run("--base", "todo-outlasts-the-turn")
    assert result.exit_code == 2 and "put cases before --base" in result.output
    assert built == []


def test_reading_semantics_use_the_text_judge_without_a_screenshot_home(tmp_path):
    config = prepare(
        ["reading", "reading/view"],
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf",),
        tmp_path / "samples",
    )
    for test in config["tests"]:
        assert test["assert"][0]["metric"] == "completed"
        answers = test["assert"][1:]
        assert len(answers) == (7 if test["description"] == "reading" else 1)
        assert all(a["type"] == "llm-rubric" and "provider" not in a for a in answers)
        view = next(a for a in answers if a["metric"] == "answer_view")
        assert "acknowledge uncertainty" in view["value"]
        assert "Current attempt is only the default" in view["value"]
    assert not (tmp_path / "scratch" / "judge").exists()
