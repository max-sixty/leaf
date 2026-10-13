"""An eval child's sandbox keeps samples from sharing files in `/tmp`."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from leaf_dev.arms import URL, claude_child


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS sandbox only")
def test_a_child_writes_its_own_directories_and_no_shared_tmp_name():
    """A child placed under `/tmp` still owns its workspace and home; a fixed name
    another sample could also write is refused; Claude Code's own per-user
    directory stays writable."""
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="leaf-sandbox-") as root:
        cwd = Path(root) / "cwd"
        cwd.mkdir()
        spec = claude_child(cwd, "")
        assert spec["args"][0] == "sandbox-exec"
        profile = spec["args"][2]
        shared = Path(f"/tmp/leaf-sandbox-shared-{os.getpid()}")
        claude = Path(f"/tmp/claude-{os.getuid()}")

        def writes(path: Path) -> bool:
            return (
                subprocess.run(
                    ["sandbox-exec", "-p", profile, "/bin/sh", "-c", f": > '{path}'"],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )

        try:
            assert writes(cwd / "tmp" / "scratch.py")
            assert writes(Path(spec["env"]["HOME"]) / "note")
            assert not writes(shared)
            assert not shared.exists()
            claude.mkdir(exist_ok=True)
            assert writes(claude / f"leaf-sandbox-{os.getpid()}")
        finally:
            (claude / f"leaf-sandbox-{os.getpid()}").unlink(missing_ok=True)


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS sandbox only")
def test_child_denies_launchservices_opening_but_preserves_served_url_handoff(tmp_path):
    """Query native permission without opening a desktop application.

    The same isolated child binds and reads a local HTTP server, then emits its
    keyed address through stdout for the driver's existing URL discovery.
    Removing the LaunchServices rule makes the permission assertion fail.
    """
    import json

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    spec = claude_child(cwd, "")
    profile = spec["args"][2]
    program = """\
import ctypes
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.request import urlopen

sandbox = ctypes.CDLL('/usr/lib/libsandbox.1.dylib')
sandbox.sandbox_check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
sandbox.sandbox_check.restype = ctypes.c_int
denied = sandbox.sandbox_check(os.getpid(), b'lsopen', 0)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'page')
    def log_message(self, *args):
        pass

with HTTPServer(('127.0.0.1', 0), Handler) as server:
    url = f'http://127.0.0.1:{server.server_port}/?t=sample-token'
    worker = Thread(target=server.handle_request)
    worker.start()
    with urlopen(url, timeout=5) as response:
        body = response.read().decode()
    worker.join()
    print(json.dumps({'lsopen_denied': denied, 'url': url, 'body': body}))
"""
    result = subprocess.run(
        ["sandbox-exec", "-p", profile, sys.executable, "-c", program],
        cwd=cwd,
        env=spec["env"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    observed = json.loads(result.stdout)
    assert observed["lsopen_denied"] == 1
    assert observed["body"] == "page"
    assert URL.search(result.stdout)[0] == observed["url"]
