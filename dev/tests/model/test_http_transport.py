"""The publish gate's socket evidence must reach stderr without credentials."""

import json
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from leaf_dev import ROOT
from playwright.sync_api import Error, sync_playwright


def test_playwright_transport_records_reuse_reset_and_ray_without_secrets(
    monkeypatch, capfd
):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            if self.path.startswith("/reset"):
                self.connection.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
                )
                self.close_connection = True
                return
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.send_header("cf-ray", "a5154cdb1f254a77-LHR")
            self.send_header("Set-Cookie", "credential=secret-response-cookie")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
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
                assert response.text() == "ok"
            with pytest.raises(Error, match="ECONNRESET"):
                context.get(origin + "/reset", headers=headers, max_retries=0)
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
    assert len(responses) == 2
    assert responses[1]["socket"] == responses[0]["socket"]
    assert responses[1]["reused"]
    assert responses[1]["ray"] == "a5154cdb1f254a77-LHR"
    assert any(
        row["event"] == "connect" and row["remotePort"] == server.server_port
        for row in records
    )
    assert any(
        row["event"] == "request-error" and row["code"] == "ECONNRESET"
        for row in records
    )
