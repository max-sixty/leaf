"""Page-authored HTTPS requests stay within host grants and bounded allowances."""

import http.client
import json
import stat
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from click.testing import CliRunner
from interact_support import TOKEN, fetch, publish, running_http_server

from leaf.cli import cli
from leaf.http_connections import ConnectionError, bind, unbind
from leaf.http_connections import fetch as connection_fetch
from leaf.state import state_home


@pytest.fixture
def upstream(monkeypatch):
    """Use real HTTP framing and redirects; replace only TLS for this loopback peer."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/leak")
                self.end_headers()
                return
            self.send_response(429 if self.path == "/limited" else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-RateLimit-Remaining", "7")
            self.send_header("Set-Cookie", "must-not-forward=1")
            self.end_headers()
            self.wfile.write(
                b"x" * (1024 * 1024 + 1)
                if self.path == "/large"
                else b'{"items":["hello"]}'
            )

        def log_message(self, *args):
            pass

    def cleartext_tls(handler, request):
        return handler.do_open(http.client.HTTPConnection, request)

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", cleartext_tls)
    monkeypatch.setenv("CONNECTION_TEST_TOKEN", "host-secret")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    with running_http_server(httpd):
        yield f"https://127.0.0.1:{httpd.server_port}", requests


def test_cli_grant_authenticates_reads_and_stays_outside_page(
    server, page_dir, upstream, monkeypatch
):
    origin, requests = upstream
    before = (page_dir / "index.html").read_bytes()
    result = CliRunner().invoke(
        cli,
        [
            "connection",
            "bind",
            str(page_dir),
            "source",
            origin,
            "--credential-env",
            "CONNECTION_TEST_TOKEN",
            "--max-requests",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "host-secret" not in result.output
    assert (page_dir / "index.html").read_bytes() == before
    assert not list(page_dir.glob("*connection*"))
    [record] = (state_home() / "http-connections").glob("*.json")
    assert "host-secret" in record.read_text()
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert stat.S_IMODE(record.parent.stat().st_mode) == 0o700
    monkeypatch.delenv("CONNECTION_TEST_TOKEN")
    assert all(
        b"host-secret" not in item.read_bytes()
        for item in page_dir.rglob("*")
        if item.is_file()
    )

    def read(path):
        status, raw = fetch(
            server + "/api/connections/source",
            data=json.dumps({"path": path}).encode(),
            headers={"Origin": server},
        )
        return status, json.loads(raw)

    status, answer = read("/items?page=2")
    assert status == 200, answer
    assert answer == {
        "status": 200,
        "headers": {"content-type": "application/json", "x-ratelimit-remaining": "7"},
        "body": '{"items":["hello"]}',
    }
    assert requests[0][0] == "/items?page=2"
    assert requests[0][1]["Authorization"] == "Bearer host-secret"
    status, answer = read("/limited")
    assert status == 200 and answer["status"] == 429
    assert read("/items")[0] == 429
    assert len(requests) == 2
    unbind(page_dir, "source")
    assert read("/items")[0] == 403


def test_connections_refuse_ungranted_requests_and_unsafe_paths(
    server, page_dir, upstream, subtests, monkeypatch
):
    origin, requests = upstream
    bind(page_dir, "source", origin, credential_env="CONNECTION_TEST_TOKEN")
    for body in (
        {"path": "//other.invalid/"},
        {"path": "https://other.invalid/"},
        {"path": "/\\other.invalid/"},
        {"path": "/#fragment"},
        {"path": "/\r\nInjected: value"},
        {"path": "/", "method": "POST"},
        {"path": "/", "headers": {"Authorization": "mine"}},
    ):
        with subtests.test(body=body), pytest.raises(ConnectionError):
            connection_fetch(page_dir, "source", body)
    for headers in ({}, {"Origin": "https://other.invalid"}):
        with subtests.test(headers=headers):
            assert (
                fetch(
                    server + "/api/connections/source",
                    data=b'{"path":"/"}',
                    headers=headers,
                )[0]
                == 403
            )
    assert (
        fetch(
            server + "/api/connections/source",
            data=b'{"path":"/"}',
            headers={"Origin": server},
            token=None,
        )[0]
        == 401
    )
    monkeypatch.delenv("CONNECTION_TEST_TOKEN")
    with pytest.raises(ConnectionError, match="binding environment has no credential"):
        bind(page_dir, "missing", origin, credential_env="CONNECTION_TEST_TOKEN")
    assert not requests


def test_connections_never_follow_redirects_and_bound_responses(page_dir, upstream):
    origin, requests = upstream
    bind(page_dir, "source", origin, credential_env="CONNECTION_TEST_TOKEN")
    with pytest.raises(ConnectionError, match="redirect"):
        connection_fetch(page_dir, "source", {"path": "/redirect"})
    assert [path for path, _ in requests] == ["/redirect"]
    with pytest.raises(ConnectionError, match="exceeds 1 MiB"):
        connection_fetch(page_dir, "source", {"path": "/large"})


def test_connections_validate_host_grants(page_dir, subtests):
    for origin in (
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/path",
        "https://example.com?query",
        "https://example.com/#fragment",
        "https://example.com:bad",
    ):
        with subtests.test(origin=origin), pytest.raises(ConnectionError):
            bind(page_dir, "source", origin, credential_env="TOKEN")


def test_connections_redact_transport_failures(server, page_dir, upstream, monkeypatch):
    origin, _ = upstream
    bind(page_dir, "source", origin, credential_env="CONNECTION_TEST_TOKEN")

    def fail(*args, **kwargs):
        raise http.client.BadStatusLine("host-secret")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fail)
    # Call the domain boundary directly because the same stdlib opener is also
    # used by the test's HTTP client.
    with pytest.raises(ConnectionError) as error:
        connection_fetch(page_dir, "source", {"path": "/"})
    assert error.value.status == 502
    assert "host-secret" not in str(error.value)


def test_connections_are_unavailable_in_read_only_previews(page_dir, upstream):
    from leaf.files import latest_revision
    from leaf.hosting import TemporaryPageServer
    from leaf.page_snapshot import capture_page_snapshot
    from leaf.revision_artifact import read_revision

    origin, requests = upstream
    bind(page_dir, "source", origin, credential_env="CONNECTION_TEST_TOKEN")
    publish(page_dir)
    revision = latest_revision(page_dir)
    snapshot = capture_page_snapshot(
        page_dir, read_revision(page_dir, revision).document, revision, url="test"
    )
    with TemporaryPageServer(
        page_dir, token=TOKEN, page_options={"page_snapshot": snapshot}
    ) as preview:
        assert (
            fetch(
                preview.origin + "/api/connections/source",
                data=b'{"path":"/"}',
                headers={"Origin": preview.origin},
            )[0]
            == 403
        )
    assert not requests
