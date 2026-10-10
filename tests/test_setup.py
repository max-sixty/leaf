"""Development setup coordinates real callers around external installer commands."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from interact_support import STATED_TIMEOUT, wait_for


@pytest.fixture
def setup_process(tmp_path, spawn):
    """Replace network/package installers, retaining CLI, processes and native locks.

    Installers acknowledge entry before reading the worker-owned stdin pipe. A
    release byte lets one finish; worker death closes the pipe and frees all of
    them. The CLI wrapper observes actual lock contention before the native wait,
    using the same nonblocking acquisition as `lock_contention` does in-process.
    """
    tools = tmp_path / "tools"
    tools.mkdir()
    installer = (
        f"#!{sys.executable}\n"
        + """
import json
import os
import sys
from pathlib import Path

tool = Path(sys.argv[0]).name
args = sys.argv[1:]
if tool == "npm":
    key = "npm-" + (args[-1] if "--prefix" in args else "root")
elif "fetch-assets" in args:
    key = "assets"
else:
    key = "chrome" if args[-1] == "chrome" else "browsers"
events = Path(os.environ["SETUP_EVENTS"])
(events / (key + ".started")).write_text(json.dumps([tool, *args]))
hold = os.environ["SETUP_HOLD"]
if hold == key or hold == "npm" and tool == "npm":
    os.read(0, 1)
(events / (key + ".finished")).touch()
sys.exit(17 if os.environ["SETUP_FAIL"] == key else 0)
"""
    )
    for tool in ("uv", "npm"):
        path = tools / tool
        path.write_text(installer)
        path.chmod(0o755)
    caller = tmp_path / "caller.py"
    caller.write_text("""
import fcntl
import sys
from pathlib import Path

import leaf_dev

leaf_dev.ROOT = Path(sys.argv[1])
contended = Path(sys.argv[2])
native_flock = fcntl.flock

def observed_flock(fd, operation):
    if operation == fcntl.LOCK_EX:
        try:
            return native_flock(fd, operation | fcntl.LOCK_NB)
        except BlockingIOError:
            contended.touch()
    return native_flock(fd, operation)

fcntl.flock = observed_flock
from leaf_dev.cli import cli
cli(["setup"])
""")

    def start(name, *, checkout=None, hold="", fail=""):
        events = tmp_path / name
        events.mkdir()
        checkout = checkout or tmp_path / "checkout"
        checkout.mkdir(exist_ok=True)
        contended = events / "contended"
        process = spawn(
            [sys.executable, str(caller), str(checkout), str(contended)],
            cwd=checkout,
            env={
                **os.environ,
                "PATH": str(tools) + os.pathsep + os.environ["PATH"],
                "SETUP_EVENTS": str(events),
                "SETUP_HOLD": hold,
                "SETUP_FAIL": fail,
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return process, events

    return start


def entered(events: Path, *keys: str) -> None:
    wait_for(
        lambda: {path.stem for path in events.glob("*.started")},
        lambda started: started.issuperset(keys),
        failure=f"installers never entered {keys}",
    )


def completed(process, *, success=True):
    output, error = process.communicate(timeout=STATED_TIMEOUT)
    assert (process.returncode == 0) == success, output + error
    return output + error


def test_foreground_setup_waits_for_background_install_in_another_checkout(
    tmp_path, setup_process
):
    background, first = setup_process("background", hold="assets")
    entered(first, "assets")
    foreground, second = setup_process("foreground", checkout=tmp_path / "other")
    wait_for(
        lambda: (second / "contended").exists(),
        bool,
        failure="the foreground caller never waited on the background setup lock",
    )
    assert not list(second.glob("*.started"))
    assert background.poll() is None
    assert foreground.poll() is None

    background.stdin.write("x")
    background.stdin.flush()
    completed(background)
    completed(foreground)
    assert {path.stem for path in second.glob("*.finished")} == {
        "assets",
        "browsers",
        "chrome",
        "npm-root",
        "npm-worker",
        "npm-evals",
    }


def test_setup_runs_npm_trees_concurrently_and_waits_for_all_of_them(setup_process):
    process, events = setup_process("npm", hold="npm")
    entered(events, "npm-root", "npm-worker", "npm-evals")
    assert not list(events.glob("npm-*.finished"))
    assert process.poll() is None
    process.stdin.write("xxx")
    process.stdin.flush()
    completed(process)
    assert len(list(events.glob("npm-*.finished"))) == 3
    commands = {
        tuple(json.loads(path.read_text())) for path in events.glob("npm-*.started")
    }
    assert commands == {
        ("npm", "ci"),
        ("npm", "ci", "--prefix", "worker"),
        ("npm", "ci", "--prefix", "evals"),
    }


@pytest.mark.parametrize("installer", ["assets", "npm-evals"])
def test_setup_reports_installer_failure_and_releases_lock_for_retry(
    setup_process, installer
):
    failed, _ = setup_process("failed", fail=installer)
    assert "exited with status 17" in completed(failed, success=False)
    retry, events = setup_process("retry")
    completed(retry)
    assert len(list(events.glob("*.finished"))) == 6
