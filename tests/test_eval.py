"""The catalog expands into Promptfoo tests run on one column per harness and arm."""

import json
import os
from pathlib import Path

import click
import pytest
import yaml
from leaf_dev.eval import catalog, native_provider, prepare, select_cases


@pytest.fixture
def codex_cli(monkeypatch):
    """Use the eval dependency's real CLI for model-free installation checks;
    the suite otherwise puts a failing harness stub ahead of installed programs."""
    programs = Path(__file__).parents[1] / "evals/node_modules/.bin"
    assert (programs / "codex").is_file(), "Install eval dependencies with npm ci"
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
            target.write_bytes((Path(__file__).parents[1] / name).read_bytes())
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


def test_native_columns_isolate_each_harness_and_arm(tmp_path, monkeypatch, codex_cli):
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
        ["brief-document-needs-no-outline", "shot-pair-outlined"],
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
        # Cases that show images find them under the column's own workspace.
        assert (
            Path(settings["working_dir"]) / "evals/shot-pair-outlined/captures"
        ).is_dir()
        if harness == "claude-code":
            homes.append(settings["env"]["HOME"])
            assert settings["plugins"][0]["path"] == str(payloads[arm])
            assert settings["setting_sources"] == []
            private_config = Path(settings["env"]["HOME"]) / ".claude"
            assert json.loads((private_config / ".credentials.json").read_text()) == {
                "fixture": "claude-login"
            }
        else:
            homes.append(settings["cli_env"]["HOME"])
            home = Path(settings["cli_env"]["CODEX_HOME"])
            skill = next(home.glob("plugins/cache/leaf/leaf/*/skills/leaf/SKILL.md"))
            assert skill.read_text() == f"{arm} instructions"
            assert settings["persist_threads"] is False
    assert len(set(homes)) == 4
    assert "must-not-enter-config" not in json.dumps(config)
    brief = config["tests"][0]
    assert brief["description"] == "brief-document-needs-no-outline"
    assert brief["vars"]["prompt"].startswith("Use the Leaf skill")
    assert [assertion["metric"] for assertion in brief["assert"]] == [
        "loads-leaf",
        "reads-page-authoring",
        "no-outline",
        "judgment",
    ]


def test_native_codex_discovers_the_complete_arm_with_root_relative_access(
    tmp_path, monkeypatch, codex_cli
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
    provider = native_provider("codex", payloads["candidate"], work)
    settings = provider["config"]
    home = Path(settings["cli_env"]["CODEX_HOME"])
    registry = next(home.rglob("registry.json"), None)
    assert registry is not None, f"No registry installed under {home}"
    assert json.loads(registry.read_text()) == {"arm": "candidate"}
    skill = registry.parent.parent
    assert (skill / "SKILL.md").read_text() == "candidate instructions"
    assert (skill / "../../bin/leaf").read_text() == "candidate launcher"
    assert settings["sandbox_mode"] == "read-only"


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
    from leaf_dev.arrangement_eval import expected_checks, rubrics

    cases = catalog()
    task = "sidebar-page-at-900px"
    assert cases[task]["metadata"]["executor"] == "leaf_dev.arrangement_eval"
    assert not any(check.startswith("choice-") for check in expected_checks(task))
    assert any("completed rollout" in rubric["value"] for rubric in rubrics(task))
    for variant in ("instructions", "live"):
        case = cases[f"{task}/{variant}"]
        assert case["metadata"]["executor"] is None
        assert "page directory is not reachable" in case["vars"]["prompt"]
        assert case["assert"]


def test_workflows_run_declared_conditions_harnesses_and_fixed_checks(
    tmp_path, monkeypatch
):
    from leaf_dev.arrangement_eval import expected_checks, rubrics

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
            *(rubric["metric"] for rubric in rubrics("document")),
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
        rubrics = staticmethod(lambda scenario: [])

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
            "metadata": {
                "case": "document/resume",
                "executor": "leaf_dev.usability_eval",
                "scenario": "resume",
            }
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
    # A judged executor's screenshots go to the judge's tree, beside nothing else.
    context["test"]["metadata"]["executor"] = "leaf_dev.reader_eval"
    response = scenario_provider.call_api("", options, context)
    assert (
        observed[-1]
        == tmp_path / "screenshots" / Path(response["metadata"]["work"]).name
    )


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

    result = run("task-outlasts-the-turn", "--repeat", "3")
    assert result.exit_code == 100, result.output
    assert built == [None]
    assert calls.read_text().strip().endswith("--repeat 3 key=none")
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert [p["label"] for p in config["providers"]] == ["claude-code/candidate"]
    assert config["description"].endswith(
        "(working tree on 012345678): task-outlasts-the-turn"
    )

    built.clear()
    # A named ref, since CI's checkout has no local main to take a merge base from.
    assert run("task-outlasts-the-turn", "--base", "HEAD").exit_code == 100
    assert built == ["HEAD", None]

    built.clear()
    result = run("--base", "task-outlasts-the-turn")
    assert result.exit_code == 2 and "put cases before --base" in result.output
    assert built == []
