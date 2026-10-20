"""Model-free checks of the developer-run Promptfoo integration, and of the deliveries
cases paste into their prompts.

Detailed grading, browser interaction and provider behavior are checked by running
an experiment while developing it, rather than maintaining regression matrices.
"""

import json

from click.testing import CliRunner
from leaf_dev.commands import eval as module


def test_catalog_builds_native_and_workflow_promptfoo_tests(tmp_path, monkeypatch):
    # Configuration copies the external login; no native provider is invoked.
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    cases = module.catalog()
    assert cases
    config = module.prepare(
        [
            "todo-outlasts-the-turn",
            "configuration",
            "dashboard/reader-clean",
            "parent-keeps-leaf-responsive/during-work",
            "page-reads-at-every-width/queue",
        ],
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
        "dashboard/reader-clean",
        "parent-keeps-leaf-responsive/during-work",
        "page-reads-at-every-width/queue",
    }
    assert all(
        provider["config"]["viewports"] == ["desktop"]
        for provider in config["providers"]
        if provider["label"].endswith("/workflow")
    )
    # A prompt may reuse another task's request by naming its file.
    queue = next(
        test
        for test in config["tests"]
        if test["metadata"]["case"] == "page-reads-at-every-width/queue"
    )
    assert "ESC-4107" in queue["vars"]["prompt"]


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
        [
            "--harness",
            "claude-code",
            "patch-review",
            "--viewport",
            "phone",
            "--viewport",
            "desktop",
            "--repeat",
            "3",
        ],
    )
    assert result.exit_code == 100, result.output
    assert calls.read_text().strip().endswith("--repeat 3")
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert config["providers"] and len(config["tests"]) == 1
    assert len(config["providers"]) == 1
    assert config["providers"][0]["config"]["viewports"] == ["phone", "desktop"]
    assert "--viewport" not in calls.read_text()


def test_every_pasted_delivery_is_the_envelope_leaf_writes():
    """A case that pastes a delivery scores the instructions against that envelope,
    so a change to `DELIVERY` fails here until the case is frozen again."""
    import yaml
    from leaf.delivery import DELIVERY
    from leaf.registry.schema import schema_error, with_leaf_resources
    from leaf_dev import ROOT

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict | list):
            for item in value.values() if isinstance(value, dict) else value:
                yield from strings(item)

    pasted = [
        (case.parent.name, json.loads(line))
        for case in sorted((ROOT / "evals").glob("*/case.yaml"))
        for text in strings(yaml.safe_load(case.read_text()))
        for line in text.splitlines()
        if line.lstrip().startswith('{"format"') and "leaf-delivery/" in line
    ]
    assert pasted
    for case, envelope in pasted:
        assert envelope.pop("format") == DELIVERY.format, case
        error = schema_error(with_leaf_resources(DELIVERY.schema), envelope)
        assert error is None, f"{case}: {error}"
