"""A/B instruction cases refer to each payload's own package instruction files."""

import json
import re
from copy import deepcopy
from pathlib import Path

import click
import pytest
import yaml
from leaf_dev import ROOT
from leaf_dev.eval import (
    prepare,
    read_case,
)
from leaf_dev.promptfoo import summarize


@pytest.mark.parametrize("case_file", sorted((ROOT / "evals").glob("*/case.yaml")))
def test_library_cases_supply_a_task_and_native_promptfoo_assertions(case_file):
    case = read_case(case_file, ROOT)
    if case.get("metadata", {}).get("executor"):
        assert case["metadata"]["case"]
        assert case["metadata"]["conditions"]
        return
    assert case["vars"]["prompt"].strip()
    assert case["assert"]
    assert all(assertion["type"] and assertion["value"] for assertion in case["assert"])


@pytest.mark.parametrize(
    ("directories", "selected"),
    [
        (("instructions",), "instructions"),
        (("guidance",), "guidance"),
        (("instructions", "guidance"), "instructions"),
    ],
)
def test_case_paths_resolve_per_payload_without_changing_the_task_or_scoring(
    tmp_path, directories, selected
):
    source = ROOT / "evals" / "playground-presets-are-whole-designs" / "case.yaml"
    case = tmp_path / "evals" / "case.yaml"
    case.parent.mkdir()
    case.write_text(source.read_text())
    original = yaml.safe_load(case.read_text())
    instruction_files = []
    for directory in directories:
        path = (
            tmp_path
            / "skills"
            / "leaf"
            / "packages"
            / "playground"
            / directory
            / "author.md"
        )
        path.parent.mkdir(parents=True)
        path.write_text(f"This payload's {directory} instructions.\n")
        instruction_files.append(path)

    prepared = read_case(case, tmp_path)
    assert yaml.safe_load(case.read_text()) == original
    assert f"packages/playground/{selected}/author.md" in prepared["vars"]["prompt"]
    read_grader = next(
        grader for grader in prepared["assert"] if grader["metric"].startswith("reads-")
    )
    target = (
        tmp_path
        / "skills"
        / "leaf"
        / "packages"
        / "playground"
        / selected
        / "author.md"
    )
    assert re.search(read_grader["config"]["path"], str(target))

    # Only resource addresses change. In particular the judge measures the same
    # composed-design behavior, and both arms demand the same successful file read.
    expected = deepcopy(original)
    if selected == "guidance":
        expected["vars"]["prompt"] = expected["vars"]["prompt"].replace(
            "/instructions/", "/guidance/"
        )
        for grader in expected["assert"]:
            if grader["metric"].startswith("reads-"):
                grader["config"]["path"] = grader["config"]["path"].replace(
                    "/instructions/", "/guidance/"
                )
    assert prepared == expected
    for path in instruction_files:
        assert path.read_text() == f"This payload's {path.parent.name} instructions.\n"
    if selected == "guidance":
        assert not (
            tmp_path / "skills" / "leaf" / "packages" / "playground" / "instructions"
        ).exists()


def test_missing_instruction_reference_fails_preparation_without_rewriting_case(
    tmp_path,
):
    case = tmp_path / "case.yaml"
    source = "vars:\n  prompt: Read `packages/playground/instructions/author.md`.\n"
    case.write_text(source)
    with pytest.raises(
        click.ClickException, match="package instruction file .* is absent"
    ):
        read_case(case, tmp_path)
    assert case.read_text() == source


def test_native_matrix_isolates_every_host_arm_and_repetition(tmp_path, monkeypatch):
    login = tmp_path / "host-login"
    login.mkdir()
    (login / "auth.json").write_text('{"fixture": "local-login"}')
    monkeypatch.setenv("CODEX_HOME", str(login))
    claude_login = tmp_path / "claude-login"
    claude_login.mkdir()
    (claude_login / ".credentials.json").write_text('{"fixture": "claude-login"}')
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_login))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-config")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-enter-config")
    arms = {}
    for arm in ("base", "candidate"):
        payload = tmp_path / arm
        skill = payload / "skills" / "leaf"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"{arm} instructions")
        arms[arm] = payload
    config = prepare(
        ["brief-document-needs-no-outline"], arms, tmp_path, ("cc", "codex"), 2
    )
    assert len(config["tests"]) == len(config["providers"]) == 8
    labels = {provider["label"] for provider in config["providers"]}
    assert {test["providers"][0] for test in config["tests"]} == labels
    workspaces = {provider["config"]["working_dir"] for provider in config["providers"]}
    assert len(workspaces) == 8
    homes = []
    for provider in config["providers"]:
        host, arm, _, _ = provider["label"].split("/")
        settings = provider["config"]
        if host == "cc":
            homes.append(settings["env"]["HOME"])
            assert settings["plugins"][0]["path"] == str(arms[arm])
            assert settings["setting_sources"] == []
            private_config = Path(settings["env"]["HOME"]) / ".claude"
            assert private_config != claude_login
            assert json.loads((private_config / ".credentials.json").read_text()) == {
                "fixture": "claude-login"
            }
        else:
            homes.append(settings["cli_env"]["HOME"])
            skill = Path(settings["cli_env"]["CODEX_HOME"]) / "skills" / "leaf"
            assert skill.resolve() == arms[arm] / "skills" / "leaf"
            assert settings["persist_threads"] is False
    assert len(set(homes)) == 8
    assert "must-not-enter-config" not in json.dumps(config)
    for test in config["tests"]:
        assert "Build and Verification" in test["vars"]["prompt"]
        assert [assertion["metric"] for assertion in test["assert"]] == [
            "loads-leaf",
            "reads-page-authoring",
            "no-outline",
            "judgment",
        ]


def test_summary_distinguishes_host_arm_and_execution_errors():
    result = {
        "results": {
            "results": [
                {
                    "testCase": {
                        "metadata": {"host": "cc", "arm": "base", "case": "example"}
                    },
                    "success": True,
                },
                {
                    "testCase": {
                        "metadata": {"host": "cc", "arm": "base", "case": "example"}
                    },
                    "success": False,
                    "failureReason": 1,
                },
                {
                    "testCase": {
                        "metadata": {
                            "host": "codex",
                            "arm": "candidate",
                            "case": "example",
                        }
                    },
                    "success": False,
                    "failureReason": 2,
                },
            ]
        }
    }
    assert summarize(result) == [
        ("example", "cc", "base", "1/2"),
        ("example", "codex", "candidate", "0/1 (1 errors)"),
    ]


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
    payload = tmp_path / "payload"
    payload.mkdir()
    config = prepare(["example"], {"candidate": payload}, tmp_path, ("cc",), 1)
    assert [check["value"] for check in config["tests"][0]["assert"]] == [
        "output.includes('hello')",
        f"file://{tmp_path / 'evals' / 'custom.cjs'}:check",
    ]


def test_catalog_contexts_keep_complete_original_check_coverage():
    from importlib import import_module

    from leaf_dev.eval import catalog, select_cases

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
    for owner in ("usability", "arrangement", "delivery"):
        module = import_module(f"leaf_dev.{owner}_eval")
        covered = {
            definition["metadata"]["case"]
            for definition in definitions.values()
            if definition["metadata"].get("executor") == f"leaf_dev.{owner}_eval"
        }
        assert covered == set(module.CASES)
    with pytest.raises(click.BadParameter, match="no case matches"):
        select_cases(("no-such-task",))


def test_workflow_matrix_selects_meaningful_conditions_and_routes_fixed_checks(
    tmp_path,
):
    from leaf_dev.arrangement_eval import expected_checks

    arms = {arm: tmp_path / arm for arm in ("base", "candidate")}
    config = prepare(
        ["document"],
        arms,
        tmp_path,
        ("cc", "codex"),
        2,
        out=tmp_path / "results",
        conditions=("leaf", "html"),
    )
    assert len(config["tests"]) == 12
    assert len({test["vars"]["work"] for test in config["tests"]}) == 12
    for test in config["tests"]:
        metadata = test["metadata"]
        assert metadata["case"] == "document"
        assert metadata["arm"] in ("base", "candidate", "html")
        assert [check["metric"] for check in test["assert"]] == expected_checks(
            "document", condition=metadata["condition"]
        )
        metrics = {check["metric"] for check in test["assert"]}
        assert {"choice-reader-correct", "choice-preserved"}.issubset(metrics) == (
            metadata["condition"] == "leaf"
        )
        configured = next(
            p for p in config["providers"] if p["label"] == test["providers"][0]
        )["config"]
        assert configured["host"] == metadata["host"]
        assert configured["condition"] == metadata["condition"]
        assert Path(test["vars"]["work"]).is_relative_to(tmp_path / "results")
    assert sum(test["metadata"]["arm"] == "html" for test in config["tests"]) == 4
    with pytest.raises(click.BadParameter, match="no requested host/condition"):
        prepare(["reading"], arms, tmp_path, ("cc",), 1, conditions=("html",))


def test_python_provider_routes_host_condition_and_case_without_parsing_prompt(
    tmp_path,
    monkeypatch,
):
    from leaf_dev import scenario_provider

    observed = []

    class Executor:
        @staticmethod
        def execute_scenario(case, payload, out, *, host, condition):
            observed.append((case, payload, out, host, condition))
            return {"output": '{"checks":{"completed":true}}'}

    monkeypatch.setattr(scenario_provider, "import_module", lambda executor: Executor)
    options = {
        "config": {
            "executor": "leaf_dev.journey_eval",
            "payload": str(tmp_path / "payload"),
            "claude_config_dir": str(tmp_path / "login"),
            "host": "codex",
            "condition": "html",
        }
    }
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "login"))
    context = {"vars": {"case": "document", "work": str(tmp_path / "evidence")}}
    assert scenario_provider.call_api("uninterpreted prompt", options, context) == {
        "output": '{"checks":{"completed":true}}'
    }
    assert observed == [
        ("document", tmp_path / "payload", tmp_path / "evidence", "codex", "html")
    ]


def test_fixed_reader_calibration_compares_runtime_evidence_with_one_judge(tmp_path):
    arms = {arm: tmp_path / arm for arm in ("base", "candidate")}
    config = prepare(
        ["dashboard/reader"],
        arms,
        tmp_path,
        ("cc", "codex"),
        1,
        conditions=("leaf", "html"),
    )
    assert len(config["tests"]) == len(config["providers"]) == 2
    assert {test["metadata"]["host"] for test in config["tests"]} == {"cc"}
    assert {test["metadata"]["arm"] for test in config["tests"]} == {
        "base",
        "candidate",
    }
    with pytest.raises(click.BadParameter, match="no requested host/condition"):
        prepare(
            ["dashboard/reader"], arms, tmp_path, ("codex",), 1, conditions=("leaf",)
        )
