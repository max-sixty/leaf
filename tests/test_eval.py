"""The catalog expands into Promptfoo tests run on one column per host and arm."""

import json
from pathlib import Path

import click
import pytest
import yaml
from leaf_dev.eval import catalog, prepare, select_cases


def arms(tmp_path, *names):
    payloads = {}
    for arm in names:
        skill = tmp_path / arm / "skills" / "leaf"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"{arm} instructions")
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


def test_native_columns_isolate_each_host_and_arm(tmp_path, monkeypatch):
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
    payloads = arms(tmp_path, "base", "candidate")
    config = prepare(
        ["brief-document-needs-no-outline", "shot-pair-outlined"],
        payloads,
        tmp_path / "scratch",
        ("cc", "codex"),
        ("leaf",),
        tmp_path / "samples",
    )
    labels = ["cc/base", "cc/candidate", "codex/base", "codex/candidate"]
    assert [provider["label"] for provider in config["providers"]] == labels
    assert [test["providers"] for test in config["tests"]] == [labels, labels]
    homes = []
    for provider in config["providers"]:
        host, arm = provider["label"].split("/")
        settings = provider["config"]
        # Cases that show images find them under the column's own workspace.
        assert (
            Path(settings["working_dir"]) / "evals/shot-pair-outlined/captures"
        ).is_dir()
        if host == "cc":
            homes.append(settings["env"]["HOME"])
            assert settings["plugins"][0]["path"] == str(payloads[arm])
            assert settings["setting_sources"] == []
            private_config = Path(settings["env"]["HOME"]) / ".claude"
            assert json.loads((private_config / ".credentials.json").read_text()) == {
                "fixture": "claude-login"
            }
        else:
            homes.append(settings["cli_env"]["HOME"])
            skill = Path(settings["cli_env"]["CODEX_HOME"]) / "skills" / "leaf"
            assert skill.resolve() == payloads[arm] / "skills" / "leaf"
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
        ("cc",),
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
    for owner in ("usability", "arrangement", "delivery"):
        module = import_module(f"leaf_dev.{owner}_eval")
        covered = {
            definition["metadata"]["scenario"]
            for definition in definitions.values()
            if definition["metadata"].get("executor") == f"leaf_dev.{owner}_eval"
        }
        assert covered == set(module.CASES)
    with pytest.raises(click.BadParameter, match="no case matches"):
        select_cases(("no-such-task",))


def test_workflows_run_declared_conditions_hosts_and_fixed_checks(tmp_path):
    from leaf_dev.arrangement_eval import expected_checks

    payloads = {arm: tmp_path / arm for arm in ("base", "candidate")}
    config = prepare(
        ["dashboard/reader", "document"],
        payloads,
        tmp_path / "scratch",
        ("cc", "codex"),
        ("leaf", "html"),
        tmp_path / "samples",
    )
    tests = {test["description"]: test for test in config["tests"]}
    # The fixed reader is a Claude calibration; the HTML control has no base.
    assert {name: test["providers"] for name, test in tests.items()} == {
        "dashboard/reader": ["cc/base/workflow", "cc/candidate/workflow"],
        "document": [
            "cc/base/workflow",
            "cc/candidate/workflow",
            "codex/base/workflow",
            "codex/candidate/workflow",
        ],
        "document (html)": ["cc/html/workflow", "codex/html/workflow"],
    }
    for condition, test in (
        ("leaf", tests["document"]),
        ("html", tests["document (html)"]),
    ):
        assert test["metadata"]["executor"] == "leaf_dev.arrangement_eval"
        assert test["vars"] == {"prompt": "document"}
        assert [check["metric"] for check in test["assert"]] == expected_checks(
            "document", condition=condition
        )
    html = next(
        provider["config"]
        for provider in config["providers"]
        if provider["label"] == "codex/html/workflow"
    )
    assert (html["host"], html["condition"], html["payload"], html["samples"]) == (
        "codex",
        "html",
        str(payloads["candidate"]),
        str(tmp_path / "samples/codex/html/workflow"),
    )
    with pytest.raises(click.BadParameter, match="no requested host/condition"):
        prepare(
            ["dashboard/reader"],
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
        def execute_scenario(case, payload, work, *, host, condition):
            observed.append((case, payload, work, host, condition))
            return {"output": "{}"}

    monkeypatch.setattr(scenario_provider, "import_module", lambda executor: Executor)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "login"))
    options = {
        "config": {
            "payload": str(tmp_path / "payload"),
            "samples": str(tmp_path / "samples"),
            "claude_config_dir": str(tmp_path / "login"),
            "host": "codex",
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
    for _ in range(2):
        assert scenario_provider.call_api("", options, context) == {"output": "{}"}
    first, second = observed
    assert first[2] != second[2]
    for case, payload, work, host, condition in observed:
        assert (case, payload, host, condition) == (
            "resume",
            tmp_path / "payload",
            "codex",
            "html",
        )
        assert work.parent == tmp_path / "samples"
        assert work.name.startswith("document-resume-")
