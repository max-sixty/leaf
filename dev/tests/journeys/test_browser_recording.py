"""The probe records real Leaf and ordinary web journeys, including failures."""

import io
import json
import os
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from zipfile import ZipFile

import pytest
from interact_support import running_http_server
from leaf_dev.arms import environment
from PIL import Image


@pytest.fixture(name="trace_launch_guard")
def trace_launch_guard_fixture(tmp_path):
    """Intercept Node's process-launch boundary instead of opening the desktop.

    The real viewer still runs. A launch records its attempted command and fails
    before affecting the user's machine; the legacy CLI is the positive control.
    The environment is the one eval agents receive, without harness detection.
    """
    attempted = tmp_path / "launches.jsonl"
    guard = tmp_path / "launch-guard.cjs"
    guard.write_text(
        'const fs = require("node:fs");\n'
        'const child = require("node:child_process");\n'
        'for (const name of ["spawn", "spawnSync", "exec", "execSync", '
        '"execFile", "execFileSync", "fork"]) {\n'
        "  child[name] = (...args) => {\n"
        f"    fs.appendFileSync({json.dumps(str(attempted))}, "
        'JSON.stringify({name, args}) + "\\n");\n'
        '    throw new Error("desktop launch intercepted");\n'
        "  };\n"
        "}\n"
    )
    env = environment()
    for key in ("CLAUDECODE", "COPILOT_CLI"):
        env.pop(key, None)
    env["NODE_OPTIONS"] = (
        f"{os.environ.get('NODE_OPTIONS', '')} --require {json.dumps(str(guard))}"
    ).strip()
    return env, attempted


@pytest.mark.parametrize(
    "outcome", ["success", "checkpoints", "assertion", "closed-page"]
)
def test_recorded_web_journey_keeps_evidence_on_success_and_failure(tmp_path, outcome):
    fails = outcome in {"assertion", "closed-page"}
    (tmp_path / "index.html").write_text(
        "<button onclick=\"this.textContent='Done'\">Start</button><input>"
    )
    journey = tmp_path / "journey.py"
    journey.write_text(
        "from playwright.sync_api import expect\n"
        "def run(page):\n"
        "    page.get_by_role('button', name='Start').click()\n"
        "    page.locator('input').fill('A saved journey')\n"
        "    page.keyboard.press('ArrowLeft')\n"
        "    expect(page.locator('input')).to_have_value('A saved journey')\n"
        + ("    page.close()\n" if outcome == "closed-page" else "")
        + (
            "    assert False\n"
            if fails
            else "    return page.locator('input').input_value()\n"
        )
    )
    output = tmp_path / "capture"
    if outcome == "closed-page":
        previous = output / "worktree"
        previous.mkdir(parents=True)
        (previous / "video.webm").write_bytes(b"a video from the previous run")
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), handler)) as httpd:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "leaf_dev",
                "probe",
                f"http://127.0.0.1:{httpd.server_port}/",
                "--journey",
                str(journey),
                "--record",
                str(output),
                "--gif",
                "--actions",
                "--viewport",
                "640x480",
                *(["--checkpoint-images"] if outcome == "checkpoints" else []),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == int(fails), result.stdout + result.stderr
    reading = json.loads(result.stdout.splitlines()[0])
    if fails:
        assert reading["failed"] == "journey: AssertionError"
    else:
        assert reading["journey"] == "A saved journey"
    recorded = output / "worktree"
    assert reading["recording"] == str(recorded)
    with ZipFile(recorded / "trace.zip") as trace:
        assert trace.testzip() is None
        assert trace.namelist()
        records = [
            json.loads(line)
            for name in trace.namelist()
            if name.endswith(".trace")
            for line in trace.read(name).splitlines()
        ]
        assert "aria-snapshot" in {row["type"] for row in records}
        screenshots = [row for row in records if row["type"] == "screenshot"]
        if outcome == "checkpoints":
            expectation = next(
                row
                for row in records
                if row["type"] == "before" and row.get("method") == "expect"
            )
            image = next(
                row
                for row in screenshots
                if row["callId"] == expectation["callId"] and row["phase"] == "after"
            )
            with Image.open(io.BytesIO(trace.read(image["file"]))) as png:
                assert png.format == "PNG"
                assert png.size == (640, 480)
        else:
            assert not screenshots
    if outcome == "closed-page":
        assert not (recorded / "video.webm").exists()
    else:
        assert (recorded / "video.webm").stat().st_size > 1000
    with Image.open(recorded / "recording.gif") as gif:
        assert gif.size == (640, 480)
        assert gif.n_frames > 1


def test_recorded_leaf_source_still_uses_its_readiness_contract(tmp_path):
    output = tmp_path / "capture"
    previous = output / "worktree"
    previous.mkdir(parents=True)
    (previous / "recording.gif").write_bytes(b"a GIF from the previous run")
    (previous / "notes.txt").write_text("Keep notes beside the capture")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "leaf_dev",
            "probe",
            "review-a-plan",
            "--do",
            "press:Tab",
            "--record",
            str(output),
            "--js",
            "matchMedia('(prefers-reduced-motion: reduce)').matches",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reading = json.loads(result.stdout)
    assert "startup" in reading
    assert reading["errors"] == []
    assert reading["result"] is False
    assert (output / "worktree" / "trace.zip").is_file()
    assert (output / "worktree" / "video.webm").stat().st_size > 1000
    assert not (previous / "recording.gif").exists()
    assert (previous / "notes.txt").read_text() == "Keep notes beside the capture"
