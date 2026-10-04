"""The probe records real Leaf and ordinary web journeys, including failures."""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from zipfile import ZipFile

import pytest
from click.testing import CliRunner
from PIL import Image

from leaf_dev.probe import probe
from leaf_dev.recording import write_gif
from interact_support import running_http_server


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


@pytest.mark.parametrize("outcome", ["success", "assertion", "closed-page"])
def test_recorded_web_journey_keeps_evidence_on_success_and_failure(tmp_path, outcome):
    fails = outcome != "success"
    (tmp_path / "index.html").write_text(
        "<button onclick=\"this.textContent='Done'\">Start</button><input>"
    )
    journey = tmp_path / "journey.py"
    journey.write_text(
        "def run(page):\n"
        "    page.get_by_role('button', name='Start').click()\n"
        "    page.locator('input').fill('A saved journey')\n"
        "    page.keyboard.press('ArrowLeft')\n"
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
        result = CliRunner().invoke(
            probe,
            [
                f"http://127.0.0.1:{httpd.server_port}/",
                "--journey",
                str(journey),
                "--record",
                str(output),
                "--gif",
                "--actions",
                "--viewport",
                "640x480",
            ],
        )
    assert result.exit_code == int(fails), result.output
    reading = json.loads(result.output.splitlines()[0])
    if fails:
        assert reading["failed"] == "journey: AssertionError"
    else:
        assert reading["journey"] == "A saved journey"
    recorded = output / "worktree"
    assert reading["recording"] == str(recorded)
    with ZipFile(recorded / "trace.zip") as trace:
        assert trace.testzip() is None
        assert trace.namelist()
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
    result = CliRunner().invoke(
        probe,
        [
            "review-a-plan",
            "--do",
            "press:Tab",
            "--record",
            str(output),
            "--js",
            "matchMedia('(prefers-reduced-motion: reduce)').matches",
        ],
    )
    assert result.exit_code == 0, result.output
    reading = json.loads(result.output)
    assert "startup" in reading
    assert reading["errors"] == []
    assert reading["result"] is False
    assert (output / "worktree" / "trace.zip").is_file()
    assert (output / "worktree" / "video.webm").stat().st_size > 1000
    assert not (previous / "recording.gif").exists()
    assert (previous / "notes.txt").read_text() == "Keep notes beside the capture"
