"""The load diagnostic must not manufacture failures or change its candidate."""

import importlib
import os
import subprocess
import sys
from pathlib import Path
from threading import Thread

import pytest
from click.testing import CliRunner
from interact_support import STATED_TIMEOUT, wait_for


@pytest.mark.parametrize("scenario", ["output", "candidate"])
def test_flake_copies_share_a_snapshot_but_not_outputs(tmp_path, monkeypatch, scenario):
    flake = importlib.import_module("leaf_dev.commands.suite.flake")
    arms = importlib.import_module("leaf_dev.arms")
    suite = importlib.import_module("leaf_dev.commands.suite._runs")
    root = tmp_path / "candidate"
    root.mkdir()
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            root,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "Empty baseline",
        ],
        check=True,
    )
    # Untracked files and edits, rather than HEAD, are the candidate.
    (root / "input.txt").write_text("candidate")
    started = tmp_path / "started"
    # Each copy records whether it runs in macOS's background band.
    bands = tmp_path / "bands"
    (root / "test_candidate.py").write_text(
        "from pathlib import Path\nimport os, time\n"
        "def test_candidate():\n"
        " root = Path(__file__).parent\n"
        f" Path({str(started)!r}).touch()\n"
        + (
            f" open({str(bands)!r}, 'a').write("
            "str(os.getpriority(os.PRIO_DARWIN_PROCESS, 0)))\n"
            if sys.platform == "darwin"
            else ""
        )
        + (
            " output = root / '.tmp' / 'fixed-output'\n"
            " output.parent.mkdir(exist_ok=True)\n"
            " with output.open('x'):\n  time.sleep(0.3)\n"
            " output.unlink()\n"
            if scenario == "output"
            else " time.sleep(0.3)\n assert (root / 'input.txt').read_text() == 'candidate'\n"
        )
    )
    monkeypatch.setattr(flake, "ROOT", root)
    monkeypatch.setattr(arms, "ROOT", root)
    monkeypatch.setattr(suite, "ROOT", root)
    monkeypatch.setattr(flake, "OUT", root / ".tmp" / "flake")
    monkeypatch.setenv(
        "PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]
    )
    editor = None
    if scenario == "candidate":

        def edit():
            wait_for(started.exists, bool, failure=lambda: "test never started")
            (root / "input.txt").write_text("later edit")

        editor = Thread(target=edit)
        editor.start()
    try:
        result = CliRunner().invoke(
            flake.flake, ["--copies", "4", "--workers", "2", "test_candidate.py"]
        )
    finally:
        if editor:
            editor.join(timeout=STATED_TIMEOUT)
    assert result.exit_code == 0, result.output
    assert "| 4 | 0 | 0 | 0 | 0 |" in result.output
    if sys.platform == "darwin":
        assert bands.read_text() == "1111"
