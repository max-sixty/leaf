"""Local website harnesses and Worker runs own the listeners they announce."""

import json
import os
import socket
import sys
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Thread

import leaf_website
from interact_support import wait_for
from leaf_dev import ROOT, verify_site


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
        assert scheduled.wait(10)
        harness._prewarm()

    worker = Thread(target=delayed)
    worker.start()
    try:
        harness.close()
    finally:
        scheduled.set()
        worker.join(timeout=10)
    assert not worker.is_alive()
    assert harness.process is None
    assert not harness.socket_path.parent.exists()


def test_local_worker_wrapper_announces_independent_bound_ports(tmp_path, spawn):
    """Use real Wrangler with tiny Workers; Docker is a separate release boundary."""
    roots = [tmp_path / "first", tmp_path / "second"]
    processes, origins = [], []
    with ExitStack() as stack:
        for root in roots:
            worker = root / "worker"
            (worker / "src").mkdir(parents=True)
            (worker / "node_modules").symlink_to(ROOT / "worker" / "node_modules")
            (worker / "package.json").write_text("{}")
            source = worker / "src" / "index.ts"
            source.write_text(
                'export default { fetch() { return new Response("'
                + root.name
                + '"); } };'
            )
            config = root / "wrangler.json"
            config.write_text(
                json.dumps(
                    {
                        "name": "local-" + root.name,
                        "main": str(source),
                        "compatibility_date": "2026-09-01",
                    }
                )
            )
            log = root / "server.log"
            output = stack.enter_context(log.open("w"))
            process = spawn(
                [
                    "node",
                    str(Path(verify_site.__file__).with_name("wrangler_server.mjs")),
                    str(root),
                    str(config),
                    str(root / "state"),
                ],
                stdout=output,
                stderr=output,
                cwd=worker,
                env={**os.environ, "WRANGLER_SEND_METRICS": "false"},
            )
            processes.append(process)

            def announced(process=process, log=log):
                assert process.poll() is None, log.read_text()
                return verify_site.announced_origin(log, "local_worker_ready")

            origins.append(wait_for(announced, bool, failure=log.read_text, timeout=60))
        assert origins[0] != origins[1]
        for origin, expected in zip(origins, (b"first", b"second"), strict=True):
            with urllib.request.urlopen(origin + "/") as response:
                assert response.read() == expected
        processes[0].terminate()
        processes[0].wait(timeout=30)
        with urllib.request.urlopen(origins[1] + "/") as response:
            assert response.read() == b"second"
        processes[1].terminate()
        processes[1].wait(timeout=30)
