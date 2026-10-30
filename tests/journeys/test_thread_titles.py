"""Thread titles: the title a page server asks a model for as a thread's opening
comment arrives, under Claude Code and Codex alike, and the App Server it holds
open for one."""

import json
import os
import signal
import sys
import urllib.parse

import psutil
import pytest
from interact_support import PAGE, STATED_TIMEOUT, fetch, publish, wait_for

from leaf import server as server_model


@pytest.fixture(name="title_codex")
def title_codex_fixture(tmp_path, monkeypatch):
    """A `codex` first on PATH whose App Server binds its socket, writes its pid,
    and never answers, so the title thread opened on it holds it open."""
    programs = tmp_path / "title-codex"
    programs.mkdir()
    pid_file = tmp_path / "title-server.pid"
    program = programs / "codex"
    program.write_text(
        f"""#!{sys.executable}
import os, signal, socket, sys
if sys.argv[1] != "app-server":
    sys.exit(1)
server = socket.socket(socket.AF_UNIX)
server.bind(sys.argv[3].removeprefix("unix://"))
server.listen()
open({str(pid_file)!r}, "w").write(str(os.getpid()))
signal.pause()
"""
    )
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    yield pid_file
    if pid_file.exists() and psutil.pid_exists(pid := int(pid_file.read_text())):
        os.kill(pid, signal.SIGTERM)


def test_a_terminated_page_server_stops_its_title_server(
    title_codex, codex_claimed_page
):
    """A page server serving a Codex session's page starts a title App Server
    for a new comment. SIGTERM, as a logout or a user's kill sends, ends the
    page server as `server stop` does (`server.exit_serving`), so that App
    Server stops with it."""
    page = codex_claimed_page
    (page / "index.html").write_text(PAGE, encoding="utf-8")
    publish(page)
    server = server_model.running_server(page)
    assert server is not None
    event_url = (
        urllib.parse.urlsplit(server["url"])._replace(path="/api/event").geturl()
    )
    status, body = fetch(
        event_url,
        data=json.dumps(
            {"kind": "comment", "revision": 1, "text": "Name this new thread."}
        ).encode(),
        token=None,
    )
    assert status == 200, body
    title_server = int(
        wait_for(
            lambda: title_codex.read_text() if title_codex.exists() else "",
            bool,
            failure="the page server started no title server",
        )
    )
    [page_server] = [
        process
        for process in psutil.process_iter(["cmdline"])
        if "_serve" in (process.info["cmdline"] or [])
        and str(page) in process.info["cmdline"]
    ]
    page_server.terminate()
    page_server.wait(timeout=STATED_TIMEOUT)
    wait_for(
        lambda: not psutil.pid_exists(title_server),
        bool,
        failure="the title server outlived its page server",
    )
