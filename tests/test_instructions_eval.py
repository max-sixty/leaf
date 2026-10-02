"""A/B instruction cases refer to each payload's own package instruction files."""

import json
import re
from copy import deepcopy
from pathlib import Path

import click
import pytest
import yaml
from leaf_dev import ROOT
from leaf_dev.instructions_eval import (
    prepare,
    resolve_case_instruction_paths,
    summarize,
)


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

    resolve_case_instruction_paths(case, tmp_path)
    prepared = yaml.safe_load(case.read_text())
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
        resolve_case_instruction_paths(case, tmp_path)
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
                {"provider": {"label": "cc/base/example/1"}, "success": True},
                {
                    "provider": {"label": "cc/base/example/2"},
                    "success": False,
                    "failureReason": 1,
                },
                {
                    "provider": {"label": "codex/candidate/example/1"},
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
    import leaf_dev.instructions_eval as module

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
