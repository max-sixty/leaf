"""Local website harnesses and Worker runs own the listeners they announce."""

import json
import os
import socket
import subprocess
import sys
import urllib.request
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Thread

import leaf_website
import pytest
from interact_support import STATED_TIMEOUT, wait_for
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


def test_failed_worker_retains_container_state_and_both_log_streams(
    tmp_path, monkeypatch, capsys
):
    """Docker's two streams survive even when the diagnostic command itself fails."""
    executable = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    executable.write_text(
        f"""#!{sys.executable}
import json, sys
from pathlib import Path
with Path({str(calls)!r}).open('a') as output:
    output.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'ps':
    print('owned-page')
    print('owned-other')
elif sys.argv[1] == 'inspect':
    print('{{"Running":true,"ExitCode":0}}')
else:
    print('restoring saved page record')
    print('restore request stalled', file=sys.stderr)
    sys.stderr.buffer.write(bytes([255]))
    sys.exit(1)
"""
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    worker = verify_site.LocalWorker("unused", "release", "isolated", tmp_path)
    failure = RuntimeError("saved-state write did not finish")
    with pytest.raises(RuntimeError) as propagated:
        try:
            raise failure
        except RuntimeError:
            worker.diagnose()
            raise
    assert propagated.value is failure
    evidence_path = tmp_path / "containers.log"
    evidence = evidence_path.read_text(errors="replace")
    assert b"\xff" in evidence_path.read_bytes()
    assert "\ufffd" in evidence
    assert '"Running":true' in evidence
    assert "restoring saved page record" in evidence
    assert "restore request stalled" in evidence
    assert evidence == capsys.readouterr().err
    assert [json.loads(line) for line in calls.read_text().splitlines()] == [
        ["ps", "--all", "--quiet", "--filter", "name=^workerd-isolated-"],
        ["inspect", "--format", "{{json .State}}", "owned-page"],
        ["logs", "--timestamps", "--tail", "200", "owned-page"],
        ["inspect", "--format", "{{json .State}}", "owned-other"],
        ["logs", "--timestamps", "--tail", "200", "owned-other"],
    ]
    real_run = subprocess.run

    def timeout_first_inspection(command, **kwargs):
        if command[1] == "inspect" and command[-1] == "owned-page":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return real_run(command, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", timeout_first_inspection)
        worker.diagnose()
    evidence = evidence_path.read_text(errors="replace")
    assert "timed out after 10 seconds" in evidence
    assert "docker logs --timestamps --tail 200 owned-other" in evidence
    assert evidence.count("restore request stalled") == 2
    assert evidence == capsys.readouterr().err
    # The verifier enters this helper while propagating its original failure.
    # An unusable evidence destination must not turn that into a filesystem error.
    blocked = tmp_path / "blocked"
    blocked.write_text("regular file, not a directory")
    worker = verify_site.LocalWorker("unused", "release", "isolated", blocked)
    with pytest.raises(RuntimeError) as propagated:
        try:
            raise failure
        except RuntimeError:
            worker.diagnose()
            raise
    assert propagated.value is failure
    assert "Container diagnostics:" in capsys.readouterr().err


def test_local_worker_wrapper_announces_independent_bound_ports(tmp_path, spawn):
    """Use real Wrangler with tiny Workers; Docker is a separate release boundary."""
    roots = [tmp_path / "first", tmp_path / "second"]
    processes, origins = [], []
    with ExitStack() as stack:
        for root in roots:
            worker = root / "worker"
            (worker / "src").mkdir(parents=True)
            (root / "node_modules").symlink_to(ROOT / "node_modules")
            (root / "package.json").write_text("{}")
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

            origins.append(wait_for(announced, bool, failure=log.read_text))
        assert origins[0] != origins[1]
        for origin, expected in zip(origins, (b"first", b"second"), strict=True):
            with urllib.request.urlopen(origin + "/") as response:
                assert response.read() == expected
        processes[0].terminate()
        processes[0].wait(timeout=STATED_TIMEOUT)
        with urllib.request.urlopen(origins[1] + "/") as response:
            assert response.read() == b"second"
        processes[1].terminate()
        processes[1].wait(timeout=STATED_TIMEOUT)
