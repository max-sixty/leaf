"""Host-granted authenticated HTTPS reads for page-authored integrations.

The CLI alone selects an HTTPS origin and one credential header. Widgets name a
connection and an origin-relative path; they cannot select methods, headers or
credentials. The trusted bind command reads the credential from its environment
and stores it privately on the host, so ordinary server restarts retain access.
A grant authorizes every GET path on its origin: choosing a trustworthy origin and
credential scope belongs to the grantor, not to page-authored JavaScript.

Grants live under the state home, keyed by canonical page directory, outside page
files, revisions, exports and the event log. Copying a page grants nothing. A durable
request allowance is debited under a cross-process lock before I/O, including failed
requests; rebinding explicitly renews it. Responses are bounded to 1 MiB, requests
have a 15-second socket inactivity timeout, and redirects are never followed or
forwarded.
"""

import http.client
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .refusals import Refused
from .state import (
    STRING,
    Record,
    flocked,
    hold_mode,
    object_schema,
    page_key,
    replace_bytes,
    state_home,
)

MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 15
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
CONNECTIONS = Record(
    "http-connections",
    object_schema(
        {
            "page": STRING,
            "connections": {
                "type": "object",
                "additionalProperties": object_schema(
                    {
                        "origin": STRING,
                        "credential": STRING,
                        "header": STRING,
                        "prefix": STRING,
                        "remaining": {"type": "integer", "minimum": 0},
                    }
                ),
            },
        }
    ),
    since=19,
)


class ConnectionError(Refused):
    """A connection request the page's host grant cannot fulfill."""

    def __init__(self, reason: str, status: int = 400):
        super().__init__(reason)
        self.status = status


def _record_path(page_dir: Path) -> Path:
    directory = state_home() / "http-connections"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    hold_mode(directory, 0o700)
    return directory / f"{page_key(page_dir)}.json"


def _read(page_dir: Path, path: Path) -> dict:
    return CONNECTIONS.read(path) or {
        "page": str(page_dir.resolve()),
        "connections": {},
    }


def _write(path: Path, stored: dict) -> None:
    """Atomic secret storage with 0600 even if a previous file had wider access."""
    replace_bytes([(path, CONNECTIONS.encode(stored), False)])


def _name(name: str) -> None:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ConnectionError(
            "Connection names must start with a letter and use letters, digits, _ or -."
        )


def _origin(origin: str) -> str:
    try:
        url = urllib.parse.urlsplit(origin)
        valid = (
            url.scheme == "https"
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and url.path in ("", "/")
            and not url.query
            and not url.fragment
            and url.port != 0
            and not any(char.isspace() or ord(char) < 32 for char in origin)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ConnectionError(
            "Grant an HTTPS origin without credentials, path, query or fragment."
        )
    return urllib.parse.urlunsplit(("https", url.netloc, "", "", ""))


def bind(
    page_dir: Path,
    name: str,
    origin: str,
    *,
    credential_env: str,
    header: str = "Authorization",
    prefix: str = "Bearer ",
    max_requests: int = 200,
) -> dict:
    """Grant authenticated GET access and renew this connection's request allowance."""
    _name(name)
    origin = _origin(origin)
    if not ENV_NAME.fullmatch(credential_env):
        raise ConnectionError(
            "Credential environment variable must be a variable name."
        )
    if not HEADER_NAME.fullmatch(header) or header.lower() in {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "proxy-authorization",
    }:
        raise ConnectionError("Choose a credential header, not a transport header.")
    if any(ord(char) < 32 or ord(char) > 126 for char in prefix):
        raise ConnectionError("Credential prefix must contain printable ASCII only.")
    if max_requests < 1:
        raise ConnectionError("Request allowance must be positive.")
    credential = os.environ.get(credential_env)
    if not credential:
        raise ConnectionError(
            "The binding environment has no credential in that variable."
        )
    if any(ord(char) < 32 or ord(char) > 126 for char in credential):
        raise ConnectionError("The credential is not a valid header value.")
    grant = {
        "origin": origin,
        "credential": credential,
        "header": header,
        "prefix": prefix,
        "remaining": max_requests,
    }
    path = _record_path(page_dir)
    with flocked(path.with_suffix(".lock")):
        stored = _read(page_dir, path)
        stored["connections"][name] = grant
        _write(path, stored)
    return {
        "name": name,
        **{key: value for key, value in grant.items() if key != "credential"},
    }


def unbind(page_dir: Path, name: str) -> dict:
    """Withdraw a grant for future requests; an already-sent request may finish."""
    _name(name)
    path = _record_path(page_dir)
    with flocked(path.with_suffix(".lock")):
        stored = _read(page_dir, path)
        stored["connections"].pop(name, None)
        _write(path, stored)
    return {"name": name, "bound": False}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, _req, _fp, _code, _msg, _headers, _newurl):
        return None


def fetch(page_dir: Path, name: str, posted: dict) -> dict:
    """Read one granted path; return upstream status, selected headers and UTF-8 text."""
    _name(name)
    if not isinstance(posted, dict) or posted.keys() != {"path"}:
        raise ConnectionError("Connection requests accept only path.")
    relative = posted["path"]
    if (
        not isinstance(relative, str)
        or not relative.startswith("/")
        or relative.startswith("//")
        or "\\" in relative
        or "#" in relative
        or any(char.isspace() or ord(char) < 32 for char in relative)
    ):
        raise ConnectionError(
            "Request path must start with / and stay on the granted origin."
        )
    path = _record_path(page_dir)
    with flocked(path.with_suffix(".lock")):
        stored = _read(page_dir, path)
        grant = stored["connections"].get(name)
        if grant is None:
            raise ConnectionError("This page has no connection with that name.", 403)
        header_value = grant["prefix"] + grant["credential"]
        if grant["remaining"] == 0:
            raise ConnectionError(
                "Connection request allowance exhausted; bind it again to renew.", 429
            )
        grant["remaining"] -= 1
        _write(path, stored)
    request = urllib.request.Request(
        grant["origin"] + relative,
        headers={grant["header"]: header_value, "Accept": "application/json"},
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        try:
            response = opener.open(request, timeout=REQUEST_TIMEOUT)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if 300 <= response.status < 400:
                raise ConnectionError(
                    "The upstream response redirects; redirects are not allowed.", 502
                )
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ConnectionError("The upstream response exceeds 1 MiB.", 502)
            return {
                "status": response.status,
                "headers": {
                    name.lower(): value
                    for name, value in response.headers.items()
                    if name.lower()
                    in {"content-type", "link", "etag", "last-modified", "retry-after"}
                    or name.lower().startswith(("x-ratelimit-", "ratelimit"))
                },
                "body": body.decode("utf-8"),
            }
    except (OSError, ValueError, http.client.HTTPException) as error:
        # Transport exception text may contain headers or URLs; keep credentials
        # out of browser refusals while preserving the distinction from upstream status.
        raise ConnectionError("The upstream HTTPS read failed.", 502) from error
