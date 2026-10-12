"""Local website harnesses and Worker runs own the listeners they announce."""

import socket
import sys
from threading import Event, Thread

import leaf_website
from interact_support import STATED_TIMEOUT


def test_default_website_harnesses_keep_independent_app_servers(tmp_path, monkeypatch):
    monkeypatch.setenv("LEAF_SITE_ROOT", str(tmp_path))
    executable = tmp_path / "codex"
    executable.write_text(
        f"""#!{sys.executable}
import socket, sys, time
listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
listener.bind(sys.argv[sys.argv.index('--listen') + 1].removeprefix('unix://'))
listener.listen()
while True:
    time.sleep(3600)
"""
    )
    executable.chmod(0o755)
    first = leaf_website.WebsiteCodexHarness(str(executable))
    second = leaf_website.WebsiteCodexHarness(str(executable))
    try:
        first_process = first._ensure_server()
        second_process = second._ensure_server()
        assert first.endpoint != second.endpoint
        assert first.log_path != second.log_path
        assert first.socket_path.parent.stat().st_mode & 0o777 == 0o700
        assert second.socket_path.parent.stat().st_mode & 0o777 == 0o700
        first.close()
        assert first_process.poll() is not None
        assert second_process.poll() is None
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(second.socket_path))
    finally:
        first.close()
        second.close()
    assert not first.socket_path.parent.exists()
    assert not second.socket_path.parent.exists()


def test_a_delayed_prewarm_cannot_revive_a_closed_website_harness():
    harness = leaf_website.WebsiteCodexHarness("unused")
    scheduled = Event()

    def delayed():
        assert scheduled.wait(STATED_TIMEOUT)
        harness._prewarm()

    worker = Thread(target=delayed)
    worker.start()
    try:
        harness.close()
    finally:
        scheduled.set()
        worker.join(timeout=STATED_TIMEOUT)
    assert not worker.is_alive()
    assert harness.process is None
    assert not harness.socket_path.parent.exists()
