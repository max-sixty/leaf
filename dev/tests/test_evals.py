"""Model-free smoke checks for the developer-run Promptfoo integration.

Detailed grading, browser interaction and provider behavior are checked by running
an experiment while developing it, rather than maintaining regression matrices.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from leaf_dev.arms import private_program
from leaf_dev.commands import eval as module
from leaf_dev.eval_codex import records_for


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox profile")
def test_authoring_sandbox_isolates_files_including_children(tmp_path, monkeypatch):
    assert shutil.which("sandbox-exec"), "macOS evals require sandbox-exec"
    host = tmp_path / "host-config"
    plugins = host / "plugins"
    plugins.mkdir(parents=True)
    host_skill = plugins / "SKILL.md"
    host_skill.write_text("other installed instructions")
    login = host / "auth.json"
    login.write_text("test login")
    monkeypatch.setenv("CODEX_HOME", str(host))
    with tempfile.TemporaryDirectory(prefix="leaf-isolation-", dir="/tmp") as directory:
        root = Path(directory)
        home, work = root / "home's files", root / "owned work"
        home.mkdir()
        work.mkdir()
        stale = root / "other-sample.txt"
        stale.write_text("unrelated sample")
        probe = work / "probe.py"
        probe.write_text("""\
import subprocess
import sys
from pathlib import Path

mode, work, stale, host_skill, login = sys.argv[1:]
owned = Path(work) / mode
owned.write_text("own output")
assert owned.read_text() == "own output"
assert Path(login).read_text() == "test login"
for outside in (Path(stale), Path(host_skill)):
    for operation in (outside.read_text, lambda: outside.write_text("overwrite")):
        try:
            operation()
        except PermissionError:
            pass
        else:
            raise AssertionError("another sample's content was accessible")
if mode == "parent":
    subprocess.run([sys.executable, __file__, "child", work, stale, host_skill, login], check=True)
print("isolated")
""")
        launcher = private_program(Path(sys.executable), home, work)
        result = subprocess.run(
            [
                str(launcher),
                str(probe),
                "parent",
                str(work),
                str(stale),
                str(host_skill),
                str(login),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == ["isolated", "isolated"]
        assert stale.read_text() == "unrelated sample"
        assert host_skill.read_text() == "other installed instructions"


def test_codex_trace_keeps_subagent_activity_without_inventing_tool_calls():
    # Codex 0.163 sends each activity as item/started and item/completed. Its
    # activity identifies the child but does not expose the child's private brief.
    activities = [
        {
            "type": "subAgentActivity",
            "id": f"activity-{kind}",
            "kind": kind,
            "agentThreadId": "child-thread",
            "agentPath": "/root/panel_schematic",
            "model": "gpt-6.1-sol" if kind == "started" else None,
            "reasoningEffort": "medium" if kind == "started" else None,
        }
        for kind in ("started", "interacted", "completed")
    ]
    trace = [
        record
        for item in activities
        for method in ("item/started", "item/completed")
        for record in records_for(
            {"method": method, "params": {"item": item}}, "parent-thread", ""
        )
    ]
    assert trace == activities


def test_catalog_builds_native_and_workflow_promptfoo_tests(tmp_path, monkeypatch):
    # Configuration shares the external login; no native provider is invoked.
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    skill = tmp_path / "arm" / ".claude" / "skills" / "developing-leaf" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Maintainer instructions.")
    cases = module.catalog()
    assert cases
    config = module.prepare(
        [
            # Its provider takes instructions; the next case's provider takes none.
            "interaction-proof-follows-the-reader",
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
        "interaction-proof-follows-the-reader",
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
