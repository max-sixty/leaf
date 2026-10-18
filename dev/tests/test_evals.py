"""Two model-free smoke checks for the developer-run Promptfoo integration.

Detailed grading, browser interaction and provider behavior are checked by running
an experiment while developing it, rather than maintaining regression matrices.
"""

import json

from click.testing import CliRunner
from leaf_dev.commands import eval as module


def test_catalog_builds_native_and_workflow_promptfoo_tests(tmp_path):
    cases = module.catalog()
    assert cases
    config = module.prepare(
        ["todo-outlasts-the-turn", "configuration"],
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf", "html"),
        tmp_path / "samples",
    )
    assert config["providers"] and config["tests"]
    assert all(test["assert"] for test in config["tests"])
    assert {test["metadata"]["case"] for test in config["tests"]} == {
        "todo-outlasts-the-turn",
        "configuration",
    }


def test_eval_command_delegates_configuration_and_status_to_promptfoo(
    tmp_path, monkeypatch
):
    # Replace the external Promptfoo CLI; keep real catalog/configuration generation.
    promptfoo = tmp_path / "promptfoo"
    calls = tmp_path / "calls"
    promptfoo.write_text(f'#!/bin/sh\necho "$*" > {calls}\nexit 100\n')
    promptfoo.chmod(0o755)

    def build_arm(ref, destination):
        (destination / "skills" / "leaf").mkdir(parents=True)
        return "0123456789abcdef"

    monkeypatch.setattr(module, "PROMPTFOO", promptfoo)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(module, "build_arm", build_arm)
    result = CliRunner().invoke(
        module.eval,
        ["--harness", "claude-code", "todo-outlasts-the-turn", "--repeat", "3"],
    )
    assert result.exit_code == 100, result.output
    assert calls.read_text().strip().endswith("--repeat 3")
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert config["providers"] and len(config["tests"]) == 1
