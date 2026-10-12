"""The probe records real Leaf and ordinary web journeys, including failures."""

import json
import select
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import urlopen

import pytest
from interact_support import STATED_TIMEOUT, wait_for
from journeys.test_browser_recording import (
    trace_launch_guard_fixture,  # noqa: F401 (fixtures)
)
from leaf.render_gate.scheme import collect_page_exceptions
from playwright._impl._driver import compute_driver_executable
from playwright.sync_api import expect


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
    collect_page_exceptions(page, errors)
    page.goto(address)
    expect(page.get_by_text("Click", exact=True).first).to_be_visible()
    assert errors == []
    assert attempted.read_text() == before
    assert server.poll() is None
    assert control.poll() is None
