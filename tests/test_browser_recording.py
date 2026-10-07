"""The probe records real Leaf and ordinary web journeys, including failures."""

import io
import json
import os
import select
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import urlopen
from zipfile import ZipFile

import pytest
from interact_support import STATED_TIMEOUT, running_http_server, wait_for
from leaf_dev.arms import environment
from leaf_dev.recording import write_gif
from PIL import Image
from playwright._impl._driver import compute_driver_executable
from playwright.sync_api import expect


@pytest.fixture
def trace_launch_guard(tmp_path):
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


def test_trace_handoff_serves_the_native_viewer_without_desktop_launches(
    tmp_path, browser, spawn, trace_launch_guard
):
    """Both eval arms' old command opens the desktop; serving a trace is separate.

    Exercise the native viewer and archive routes, including paths needing URL
    encoding and rejection of files outside the recording's directory.
    """
    archive_dir = tmp_path / "record"
    archive_dir.mkdir()
    trace = archive_dir / "gesture # & é.zip"
    context = browser.new_context()
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    recorded = context.new_page()
    recorded.goto("data:text/html,<button>Recorded button</button>")
    recorded.get_by_role("button", name="Recorded button").click()
    context.tracing.stop(path=trace)
    context.close()

    env, attempted = trace_launch_guard
    node, driver = compute_driver_executable()
    control = spawn(
        [node, driver, "show-trace", "--host", "127.0.0.1", "--port", "0", str(trace)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        attempted.exists,
        bool,
        failure="legacy trace command never attempted a desktop launch",
    )
    launches = [json.loads(line) for line in attempted.read_text().splitlines()]
    assert launches, "the launch interceptor must see the legacy command's side effect"
    # Keep the control's evidence: any launch from the new server appends a line.
    before = attempted.read_text()

    server = spawn(
        [sys.executable, "-m", "leaf_dev", "trace-server", str(trace)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert select.select([server.stdout], [], [], STATED_TIMEOUT)[0], (
        "trace server never printed its URL"
    )
    address = server.stdout.readline().strip()
    assert address.startswith("http://127.0.0.1:"), address
    with urlopen(address, timeout=STATED_TIMEOUT) as response:
        viewer = response.read()
        parameters = parse_qs(urlsplit(response.url).query)
    assert b"<html" in viewer
    assert parameters["trace"] == [f"file?path={quote(str(trace), safe='')}"]
    with urlopen(
        f"{address}/trace/{parameters['trace'][0]}", timeout=STATED_TIMEOUT
    ) as response:
        assert response.read() == trace.read_bytes()
    private = tmp_path / "private.txt"
    private.write_text("outside the recording")
    with pytest.raises(HTTPError) as denied:
        urlopen(
            f"{address}/trace/file?path={quote(str(private), safe='')}",
            timeout=STATED_TIMEOUT,
        )
    assert denied.value.code == 403

    # The dependency's React viewer does not follow Leaf's DOM-write invariants.
    # Check its loading and uncaught errors without Leaf's runtime diagnostics.
    page = browser.unwatched.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(address)
    expect(page.get_by_text("Click", exact=True).first).to_be_visible()
    assert errors == []
    assert attempted.read_text() == before
    assert server.poll() is None
    assert control.poll() is None


def test_gif_retains_the_viewport_when_startup_frame_dimensions_change(tmp_path):
    output = tmp_path / "startup.gif"
    write_gif(
        [Image.new("RGB", (390, 338), "white"), Image.new("RGB", (390, 520), "red")],
        [100, 200],
        output,
    )
    with Image.open(output) as gif:
        assert gif.size == (390, 520)
        gif.seek(1)
        assert gif.convert("RGB").getpixel((389, 519)) == (255, 0, 0)


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
