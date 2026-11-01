"""The publish gate's socket evidence must reach stderr without credentials."""

import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import Error, sync_playwright

from leaf_dev import ROOT
from leaf_dev.commands.verify_site import read_state


@pytest.mark.parametrize("failure", ["single_reset", "repeated_reset", "http500"])
def test_state_transport_recovers_only_one_reset_and_records_it_without_secrets(
    monkeypatch, capfd, failure
):
    state_attempts = 0

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            nonlocal state_attempts
            if self.path == "/state":
                state_attempts += 1
            if self.path == "/state" and (
                failure == "repeated_reset"
                or (failure == "single_reset" and state_attempts == 1)
            ):
                self.connection.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                )
                self.close_connection = True
                return
            body = b'{"revision":"current"}'
            self.send_response(
                500 if self.path == "/state" and failure == "http500" else 200
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("cf-ray", "a5154cdb1f254a77-LHR")
            self.send_header("Set-Cookie", "credential=secret-response-cookie")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "NODE_OPTIONS", f"--require={ROOT / 'dev/leaf_dev/http_transport.cjs'}"
    )
    try:
        with sync_playwright() as playwright:
            context = playwright.request.new_context()
            origin = f"http://127.0.0.1:{server.server_port}"
            headers = {"Authorization": "Bearer secret-auth", "Cookie": "secret-cookie"}
            for _ in range(2):
                response = context.get(
                    origin + "/secret-path?token=secret-query", headers=headers
                )
                assert response.json() == {"revision": "current"}
            if failure == "single_reset":
                assert read_state(
                    context, origin + "/state", headers=headers
                ).json() == {"revision": "current"}
            elif failure == "repeated_reset":
                with pytest.raises(Error, match="Failed after 2 attempt"):
                    read_state(context, origin + "/state", headers=headers)
            else:
                with pytest.raises(RuntimeError, match="returned 500"):
                    read_state(context, origin + "/state", headers=headers)
            assert state_attempts == (1 if failure == "http500" else 2)
            context.dispose()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    stderr = capfd.readouterr().err
    assert "secret-" not in stderr
    records = [
        json.loads(line)
        for line in stderr.splitlines()
        if line.startswith('{"component":"leaf-http-transport"')
    ]
    assert any(row["event"] == "enabled" for row in records)
    responses = [row for row in records if row["event"] == "response"]
    assert len(responses) == (2 if failure == "repeated_reset" else 3)
    assert responses[1]["socket"] == responses[0]["socket"]
    assert responses[1]["reused"]
    assert responses[1]["ray"] == "a5154cdb1f254a77-LHR"
    assert any(
        row["event"] == "connect" and row["remotePort"] == server.server_port
        for row in records
    )
    assert (
        sum(
            row["event"] == "request-error" and row["code"] == "ECONNRESET"
            for row in records
        )
        == {"single_reset": 1, "repeated_reset": 2, "http500": 0}[failure]
    )
