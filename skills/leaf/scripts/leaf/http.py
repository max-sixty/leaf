"""HTTP transport and routes for one served page."""

import base64
import contextlib
import hashlib
import html
import json
import re
import secrets
import select
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import presence as presence_model
from .data import DataError, data_fragment, read_data_fragment
from .data_contracts import valid_snapshot_id
from .event_endpoint import accept_event, event_rejection
from .event_log import read_events
from .files import (
    latest_revision,
    list_revisions,
    missing_revision,
    published_versions,
    revision_num,
    revision_path,
    stamped_version,
    version_num,
    version_revisions,
    write_json,
)
from .locations import path_is_within
from .media import MAX_MEDIA_UPLOAD_BYTES, MediaUploadError, store_uploaded_media
from .registry.storage import layer_metadata, require_registry
from .render_checks import PROBE_SOURCES
from .revision_artifact import RevisionArtifact, read_artifact
from .revision_delivery import deliver_document, deliver_resource
from .revisioning import activate_source
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE,
    NO_KEY,
    SERVED_PATH,
    VIEWED_FILE,
)
from .served_state import reading as served_reading
from .served_state.service import PageStateService
from .server import preview_metadata
from .service import PageTransaction
from .structure import (
    DELIVERY_ENCODING_META,
    FRAME_ANCESTORS_CSP,
    PAGE_CSP,
    UTF8_BOM,
    SourceDocument,
)

# How often an open news stream re-reads the page, and how long it may go without a
# word before saying it is still there. The look is a re-stat rather than an in-process
# signal because an append does not have to come from this process — `leaf reply` and
# every other command write these same files from outside it — so one mechanism covers
# a browser's POST and an agent's command alike. Measured at 70us a look, 0.14% of a
# core per open tab, against the full state read and log parse a timed poll cost every
# two seconds whether or not anything had happened. (The neighbour scan the poll also
# ran is still run, on `PRESENCE_S` below.)
LOOK_S = 0.05
ALIVE_S = 5.0
# How often the stream re-reads what no stamp shows. Three facts in a state come from
# somewhere other than the page's files: whether a wait lease is held is a lock, whether
# the claimant lives is a pid, and the neighbours are other pages' directories and
# servers. Each is cheap to read once and dear to read twenty times a second, and two
# seconds is the staleness the poll gave every fact, so it is the staleness these keep.
PRESENCE_S = presence_model.PRESENCE_CACHE_S


def reject_json_constant(value: str) -> None:
    """Reject Python's non-standard NaN and infinity JSON extensions."""
    raise ValueError(f"invalid JSON constant {value}")


def _query_int(raw, name: str, minimum: int) -> int:
    """One integer a request named, refused in the caller's own words."""
    bound = "positive" if minimum == 1 else "non-negative"
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a {bound} integer") from error
    if value < minimum:
        raise ValueError(f"{name} must be a {bound} integer")
    return value


_ROOTED_SCRIPT_ROUTE = re.compile(
    rb'(?P<before>["\'`])/(?P<path>'
    rb"(?:api|page|runtime|widgets|vendor|media)/|"
    rb"(?:registry\.json|theme\.css|icon\.svg|leaf\.js)"
    rb")"
)
_ROOTED_STYLESHEET_ROUTE = re.compile(
    rb'(?P<before>["\'`(])/(?P<path>'
    rb"(?:api|page|runtime|widgets|vendor|media)/|"
    rb"(?:registry\.json|theme\.css|icon\.svg|leaf\.js)"
    rb")"
)

_ROOTED_PAGE_ATTRIBUTE = re.compile(
    rb'(?P<before>=\s*["\'])/(?P<path>'
    rb"(?:api|page|runtime|widgets|vendor|media)/|"
    rb"(?:registry\.json|theme\.css|icon\.svg|leaf\.js)"
    rb")",
    re.IGNORECASE,
)
_HTML_START_TAG = re.compile(rb"<[A-Za-z](?:[^<>\"']|\"[^\"]*\"|'[^']*')*>", re.DOTALL)
_STYLE_ATTRIBUTE = re.compile(
    rb'(?P<before>\bstyle\s*=\s*)(?P<quote>["\'])(?P<value>.*?)(?P=quote)',
    re.IGNORECASE | re.DOTALL,
)
_STYLE_ELEMENT = re.compile(
    rb"(?P<open><style\b(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>)"
    rb"(?P<value>.*?)(?P<close></style\s*>)",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_ELEMENT = re.compile(
    rb"(?P<open><script\b(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>)"
    rb"(?P<value>.*?)(?P<close></script\s*>)",
    re.IGNORECASE | re.DOTALL,
)


def _scope_routes(
    pattern: re.Pattern[bytes],
    body: bytes,
    page_root: str,
    *,
    asset_root: str | None = None,
) -> bytes:
    if not page_root and not asset_root:
        return body
    page = page_root.rstrip("/").encode()
    assets = (asset_root if asset_root is not None else page_root).rstrip("/").encode()
    return pattern.sub(
        lambda match: (
            match.group("before")
            + (page if match.group("path").startswith((b"api/", b"media/")) else assets)
            + b"/"
            + match.group("path")
        ),
        body,
    )


def scope_script_routes(
    body: bytes, page_root: str, *, asset_root: str | None = None
) -> bytes:
    """Scope Leaf routes at the start of JavaScript string literals."""
    return _scope_routes(_ROOTED_SCRIPT_ROUTE, body, page_root, asset_root=asset_root)


def scope_stylesheet_routes(
    body: bytes, page_root: str, *, asset_root: str | None = None
) -> bytes:
    """Scope Leaf routes in quoted CSS values and unquoted url() values."""
    return _scope_routes(
        _ROOTED_STYLESHEET_ROUTE, body, page_root, asset_root=asset_root
    )


def scope_document_routes(
    body: bytes, page_root: str, *, asset_root: str | None = None
) -> bytes:
    """Scope only route-bearing HTML attributes in an authored document.

    Authored prose is also the anchorable record. A route-looking phrase in that
    prose must therefore remain byte-for-byte identical to the immutable revision,
    while actual browser addresses still need the process page capability.
    """
    if not page_root and not asset_root:
        return body
    page = page_root.rstrip("/").encode()
    assets = (asset_root if asset_root is not None else page_root).rstrip("/").encode()

    def route_root(match: re.Match) -> bytes:
        return page if match.group("path").startswith(b"api/") else assets

    def scope_start_tag(tag_match: re.Match) -> bytes:
        tag = _ROOTED_PAGE_ATTRIBUTE.sub(
            lambda match: (
                match.group("before") + route_root(match) + b"/" + match.group("path")
            ),
            tag_match.group(),
        )
        return _STYLE_ATTRIBUTE.sub(
            lambda match: (
                match.group("before")
                + match.group("quote")
                + scope_stylesheet_routes(
                    match.group("value"), page_root, asset_root=asset_root
                )
                + match.group("quote")
            ),
            tag,
        )

    scoped = _HTML_START_TAG.sub(scope_start_tag, body)
    scoped = _STYLE_ELEMENT.sub(
        lambda match: (
            match.group("open")
            + scope_stylesheet_routes(
                match.group("value"), page_root, asset_root=asset_root
            )
            + match.group("close")
        ),
        scoped,
    )
    return _SCRIPT_ELEMENT.sub(
        lambda match: (
            match.group("open")
            + scope_script_routes(
                match.group("value"), page_root, asset_root=asset_root
            )
            + match.group("close")
        ),
        scoped,
    )


def scope_page_urls(value, page_root: str):
    """Scope the canonical version addresses in a multiplexed state response."""
    if not page_root:
        return value
    if isinstance(value, list):
        return [scope_page_urls(item, page_root) for item in value]
    if not isinstance(value, dict):
        return value
    scoped = {}
    for key, item in value.items():
        if (
            key == "url"
            and isinstance(item, str)
            and item.startswith(("/versions/", "/revisions/"))
        ):
            scoped[key] = page_root.rstrip("/") + item
        elif key == "markup" and isinstance(item, str):
            scoped[key] = scope_document_routes(item.encode(), page_root).decode()
        else:
            scoped[key] = scope_page_urls(item, page_root)
    return scoped


def head_open_end_offset(document: SourceDocument) -> int:
    """Locate the first byte inside head, before authored executable content."""
    if document.head_open_end is None:
        raise ValueError("document has no explicit <head>")
    return document.head_open_end


def _delivery_prelude(revision: int, version: int | None) -> str:
    """Declare the delivery's encoding and immutable Leaf identity first."""
    identity = f'<meta name="lf-revision" data-lf-runtime content="{revision}">'
    return (
        DELIVERY_ENCODING_META
        + identity
        + (
            f'<meta name="lf-version" data-lf-runtime content="{version}">'
            if version is not None
            else ""
        )
    )


def _runtime_assets(asset_root: str = "") -> tuple[str, str]:
    root = asset_root.rstrip("/")
    return (
        f'<link rel="stylesheet" href="{root}/theme.css" data-lf-runtime>',
        f'<script type="module" src="{root}/leaf.js" data-lf-runtime></script>',
    )


def script_hash(body: str) -> str:
    """One CSP source expression for the exact text an inline script executes."""
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    return f"'sha256-{digest}'"


def runtime_document(source: str, revision: int, version: int | None = None) -> bytes:
    """Give a clean authored document its runtime head and immutable identity."""
    document = SourceDocument(source)
    offset = head_open_end_offset(document)
    theme_head, entry_head = _runtime_assets()
    runtime = _delivery_prelude(revision, version) + theme_head + entry_head
    return (UTF8_BOM + source[:offset] + runtime + source[offset:]).encode()


def supervised_document(
    source: str,
    revision: int,
    version: int | None,
    *,
    server_id: str,
    layer_id: str,
    bootstrap: str,
    release_id: str | None = None,
    page_root: str = "",
    asset_root: str | None = None,
    before_runtime: str = "",
) -> bytes:
    """Supervise HTTP startup before the module graph or stylesheet can load.

    The served document receives the runtime assets, current layer CSP, exact
    bootstrap hash, and server incarnation probe, so historical sources inherit
    the current delivery boundary without carrying delivery markup themselves.

    It also names the page it belongs to. A page answers at three addresses — the
    live root, each stamped version, and each immutable revision — and every one
    of them serves this document, so the page root is the address that stands for
    all of them. The href is relative to the delivery, which has no origin to
    know: it resolves wherever the page directory is mounted.
    """
    # Scope authored routes before hashing: CSP authorizes the bytes the browser
    # receives, including rewritten imports inside authored module blocks.
    source = scope_document_routes(
        source.encode(), page_root, asset_root=asset_root
    ).decode()
    parsed = SourceDocument(source)
    offset = head_open_end_offset(parsed)
    bootstrap = scope_script_routes(
        bootstrap.encode(), page_root, asset_root=asset_root
    ).decode()
    hashes = [script_hash(bootstrap)]
    hashes.extend(script_hash(script["body"]) for script in parsed.inline_scripts)
    csp = PAGE_CSP + "; script-src 'self' " + " ".join(dict.fromkeys(hashes))
    release = (
        f' data-lf-release="{html.escape(release_id, quote=True)}"'
        if release_id is not None
        else ""
    )
    public_root = (
        f' data-lf-page-root="{html.escape(page_root, quote=True)}"'
        if release_id is not None
        else ""
    )
    assets = asset_root if asset_root is not None else page_root
    theme_head, entry_head = _runtime_assets(assets)
    asset_path = assets.rstrip("/")
    bootstrap_head = (
        f'<script data-lf-runtime data-lf-server="{server_id}" '
        f'data-lf-layer="{layer_id}"{release}{public_root} '
        f'data-lf-entry="{asset_path}/leaf.js" '
        f'data-lf-theme="{asset_path}/theme.css" '
        f'data-lf-probe="{asset_path}/registry.json">{bootstrap}</script>'
    )
    supervised = (
        _delivery_prelude(revision, version)
        + f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}">'
        + bootstrap_head
        + theme_head
        + before_runtime
        + entry_head
        + f'<link rel="canonical" href="{html.escape(page_root, quote=True)}/" data-lf-runtime>'
    )
    return (source[:offset] + supervised + source[offset:]).encode()


class Handler(BaseHTTPRequestHandler):
    page_dir = None
    token = None
    server_id = secrets.token_hex(16)
    # Set by `authorized` when the key arrived in the query, cleared by the one
    # writer that spends it.
    set_cookie = False
    page_snapshot = None
    # Empty on the ordinary one-page server. The MCP delivery server sets this to
    # an unguessable `/p/<capability>` prefix and rewrites only Leaf-owned routes.
    page_root = ""
    # Published website pages use the complete server contract without a Leaf work
    # claim. Their banner reads this explicit presentation fact instead of mistaking
    # the deliberately unattended page for an abandoned ordinary Leaf.
    publication = None
    # A website release spans its document, static layer and container image. Ordinary
    # page servers have no release boundary beyond their vendored layer.
    release = None
    frame_ancestors_policy = FRAME_ANCESTORS_CSP

    def _state_service(self) -> PageStateService:
        return PageStateService(
            self.page_dir,
            page_snapshot=self.page_snapshot,
            layer_identity=self.layer_identity,
            preview=self.preview,
            publication=self.publication,
        )

    def page_state(self, view_revision: int | None = None) -> dict:
        """The current reading used by GET and accepted POST responses.

        A claim's ``log_floor`` is meaningful only beside the same log snapshot it
        followed. Every response therefore keeps the page transaction through both
        files.

        The reading is taken after the activation this response performs and
        before any file the state is built from is read, and that order is the whole
        of its correctness. Taken after the reads, it could name a write this response
        does not carry, and a tab comparing it with what the stream says would never
        ask for that write — the one way a reading like this loses an update rather
        than merely repeating one. Taken before the activation, it would miss the
        write this response itself made, and the tab would be told to ask again for
        what it was just handed. Between the two, the worst case is a token already
        stale on arrival, which costs one more request and no news.
        """
        return self._state_service().page_state(view_revision)

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        """One revision projected at an exact already-observed log boundary."""
        return self._state_service().page_browser_view(view_revision, through_seq)

    def requested_view_revision(self, *, header: bool = False) -> int | None:
        raw = (
            self.headers.get("Leaf-View-Revision")
            if header
            else parse_qs(urlsplit(self.path).query).get("revision", [None])[-1]
            or self.headers.get("Leaf-View-Revision")
        )
        if raw in (None, ""):
            return None
        return _query_int(raw, "view revision", 1)

    def requested_view_sequence(self) -> int:
        raw = parse_qs(urlsplit(self.path).query).get("through_seq", [None])[-1]
        if raw in (None, ""):
            raise ValueError("view sequence is required")
        return _query_int(raw, "view sequence", 0)

    def data_fragment(self) -> dict:
        """One contract-declared payload from the data revision the tab holds."""
        query = parse_qs(urlsplit(self.path).query)
        data_revision = _query_int(
            query.get("data_revision", [None])[-1], "data_revision", 0
        )
        source = query.get("source", [None])[-1]
        key = query.get("key", [None])[-1]
        snapshot = query.get("snapshot", [None])[-1]
        if not isinstance(source, str) or not source:
            raise ValueError("source is required")
        if not isinstance(key, str) or not key:
            raise ValueError("key is required")
        if snapshot is not None and not valid_snapshot_id(snapshot):
            raise ValueError("snapshot must be a positive decimal revision")
        if self.page_snapshot is not None:
            return data_fragment(
                self.page_snapshot.data,
                self.page_snapshot.registry,
                data_revision=data_revision,
                source=source,
                key=key,
                snapshot_id=snapshot,
            )
        with PageTransaction(self.page_dir):
            return read_data_fragment(
                self.page_dir,
                require_registry(self.page_dir),
                data_revision=data_revision,
                source=source,
                key=key,
                snapshot_id=snapshot,
            )

    def log_message(self, *args):
        pass

    def _news(self):
        """The page's reading, named on an open stream each time it changes.

        What a tab listens on instead of asking on a timer. The stream carries no
        state: it says the page has a new reading, and the tab then asks
        `/api/state` the way it always did — so everything that reads, stubs, or
        counts a state request, in the page or in a test standing outside it, keeps
        its meaning, and a caller that never learns this door reads the page as
        before. A look is `LOOK_S` of stat calls per open tab. The reading is said
        again every `ALIVE_S` whether or not it moved: that keeps a quiet page
        distinguishable from a dead stream, and it puts right a tab whose reading came
        to differ from what this stream last said — an answer that crossed another,
        a presence that moved between a word here and the read it prompted.

        The stream is also the one proof a browser has the page visible, and before
        it the poll was: a page nobody ever viewed and one the user studied and left
        looked identical from the agent's side. A hidden tab releases its stream and
        a visible tab whose page has no news never asks again, so presence is written
        from here, throttled — it needs a recency, not a request log — and never from
        a preview, whose browser is the render gate's rather than the reader's.

        Ends on the server stopping, or on the peer going: a closed tab makes the
        socket readable with nothing to read, which the wait between looks sees at
        once rather than on the next write into it.
        """
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        cls = type(self)
        said = files_said = presence = None
        looked = spoke = 0.0
        try:
            while not self.server.stopping:
                now = time.monotonic()
                if self.page_snapshot is not None:
                    reading = self.page_snapshot.reading
                    files = reading
                    presence = ""
                else:
                    files = served_reading.page_reading(self.page_dir)
                    # Presence is re-read on its own clock, and again whenever the files
                    # move. The state answer and this token must describe the same view.
                    if files != files_said or now - looked >= PRESENCE_S:
                        presence = presence_model.presence_reading(self.page_dir)
                        looked = now
                    reading = f"{files}.{presence}"
                # Before the word goes out, so a listener that has heard the first
                # one is a browser the page already counts as holding it open.
                if (
                    self.page_snapshot is None
                    and time.time() - getattr(cls, "viewed_at", 0) > 30
                ):
                    cls.viewed_at = time.time()
                    write_json(self.page_dir / VIEWED_FILE, {"t": cls.viewed_at})
                if reading != said or now - spoke >= ALIVE_S:
                    self.wfile.write(f"data: {reading}\n\n".encode())
                    said, files_said, spoke = reading, files, now
                readable, _, _ = select.select([self.connection], [], [], LOOK_S)
                if readable and not self.connection.recv(1024):
                    return
        except (FileNotFoundError, NotADirectoryError):
            # The page directory going away under an open tab ends the stream, as a
            # peer going away does. The answer boundary this runs inside would
            # otherwise write a status line and a JSON fault into the middle of it.
            # A peer gone mid-write is `handle`'s, and any other fault is a fault.
            return

    def handle(self):
        """The exchange, ending quietly when the reader is no longer there.

        A reader who closes the tab mid-response leaves the handler writing into a
        socket the kernel answers with a reset, and `socketserver` prints the
        `BrokenPipeError` as a twenty-five-line traceback naming this file — a
        server fault, by every appearance, for the one thing a page is most
        certain to do. Closing a tab is not an error and there is nothing to
        answer with, the peer being gone; every read and write on the connection
        passes through here, so this is where it ends. `ConnectionError` is the
        whole of that case: its other subclass, a refused connection, cannot
        reach a socket the server already accepted."""
        with contextlib.suppress(ConnectionError):
            super().handle()

    def authorized(self) -> bool:
        """The key, from the handover URL or from the cookie an earlier request
        set out of it. One arrival is enough: the runtime's own fetches are
        relative and carry no query, and a reader who reloads or bookmarks the bare
        address is the same reader. So nothing has to thread the key through the
        page, and `leaf.js` never learns there is one."""
        if secrets.compare_digest(
            parse_qs(urlsplit(self.path).query).get("t", [""])[0], self.token
        ):
            self.set_cookie = True
        else:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            if KEY_COOKIE not in jar or not secrets.compare_digest(
                jar[KEY_COOKIE].value, self.token
            ):
                return False
        return True

    def end_headers(self):
        # Every response ends here — answered, redirected, or refused — so the
        # cookie has one writer rather than one per path that sends a header.
        path = urlsplit(self.path).path
        if path.startswith(("/api/", "/versions/", "/revisions/")) or path in {
            "/registry.json",
            "/",
        }:
            self.send_header("Leaf-Layer", getattr(self, "response_layer", self.layer))
            self.send_header("Leaf-Server", self.server_id)
            if self.release is not None:
                self.send_header("Leaf-Release", self.release)
        if self.set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{KEY_COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.set_cookie = False
        # Data and media are distinct from executable page source. Strict MIME
        # handling keeps a response from becoming code merely because authored
        # JavaScript tries to import it.
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        is_html = ctype.startswith("text/html")
        if is_html:
            body = scope_document_routes(body, self.page_root)
        elif ctype.startswith("text/css"):
            body = scope_stylesheet_routes(body, self.page_root)
        elif ctype.startswith(("text/javascript", "application/javascript")):
            body = scope_script_routes(body, self.page_root)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if is_html and self.frame_ancestors_policy:
            self.send_header("Content-Security-Policy", self.frame_ancestors_policy)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(
            status,
            "application/json",
            json.dumps(
                scope_page_urls(obj, self.page_root), ensure_ascii=False
            ).encode(),
        )

    def _select_page(self) -> bool | None:
        """Bind this request to a page before entering its HTTP boundary.

        A one-page server is already bound by its handler class. Multiplexed
        transports override this hook and return false for an unknown route, or
        ``None`` after answering a transport-owned route such as a health check.
        """
        return True

    def _not_found(self) -> None:
        # An unread body makes an HTTP/1.1 connection unsafe to reuse.
        if self.headers.get("Content-Length") or self.headers.get("Transfer-Encoding"):
            self.close_connection = True
        self._json({"error": "not found"}, 404)

    def do_GET(self):
        self._answer(self._get)

    def do_POST(self):
        # The body is route preparation: inside the answer boundary, but after the one
        # shared key gate. An unauthenticated peer therefore cannot choose an allocation
        # or park a handler in a body read. Its refusal names no attempt because no body
        # was trusted enough to read one from; the browser accepts that attempt-less
        # final answer because the refusal happened before any append could have begun.
        self._answer(self._post, prepare=self._read_posted)

    def _read_posted(self) -> tuple:
        """The route's POSTed body, or the refusal it has already earned.

        Reading and parsing can fail in different ways, all before a write is possible.
        Each earns a deterministic refusal; an unexpected exception remains inside
        `_answer`, where the event outbox treats it as retryable.
        """
        if urlsplit(self.path).path == "/api/media":
            return self._read_uploaded_media()
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        except (TypeError, ValueError, MemoryError):
            return {}, "invalid Content-Length"
        try:
            posted = json.loads(body, parse_constant=reject_json_constant)
        except (ValueError, RecursionError):
            return {}, "invalid JSON"
        if not isinstance(posted, dict):
            return {}, "event must be a JSON object"
        return posted, None

    def _read_uploaded_media(self) -> tuple[bytes, str | None]:
        """Read one bounded image body without allocating from an untrusted length."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except (TypeError, ValueError):
            self.close_connection = True
            return b"", "invalid Content-Length"
        if length < 1:
            self.close_connection = True
            return b"", "image body is empty"
        if length > MAX_MEDIA_UPLOAD_BYTES:
            self.close_connection = True
            return b"", "image exceeds the 10 MiB limit"
        try:
            body = self.rfile.read(length)
        except (MemoryError, OSError):
            self.close_connection = True
            return b"", "could not read image body"
        if len(body) != length:
            self.close_connection = True
            return b"", "incomplete image body"
        return body, None

    def _refuse(self, error: str, status: int = 400) -> None:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self.command == "POST" and urlsplit(self.path).path == "/api/event":
            status, body = event_rejection(self.posted, error, status)
            self._json(body, status)
        else:
            self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> None:
        """One boundary for page selection, authorization, preparation, and faults.

        Unanswered, a fault
        drops the socket, socketserver buries the traceback in stderr nothing reads, and
        the banner says "Server offline" about a server that is up — so every
        fault becomes a 500 naming itself, which the banner can show to the one
        person still looking. The key is checked here for `end_headers`'s reason: every
        request passes through, so there is one gate rather than one per method, and a
        route added later cannot be the one that forgot to ask. POST preparation is
        deliberately after that gate, so an unknown peer cannot choose a body-read cost.
        """
        prepared = False
        self.response_layer = self.layer
        try:
            selected = self._select_page()
            if selected is None:
                return
            if not selected:
                self._not_found()
                return
            if prepare:
                self.posted, self.posted_error = {}, None
            if not self.authorized():
                # HTTP/1.1 cannot reuse a connection whose declared request body was
                # never consumed: those bytes would be parsed as the next request.
                if prepare:
                    self.close_connection = True
                self._refuse(NO_KEY, 403)
                return
            if prepare:
                self.posted, self.posted_error = prepare()
                prepared = True
            route()
        except Exception as error:  # noqa: BLE001 - the boundary answers, never buries
            # Not a refusal: a fault may have landed either side of the append, so the
            # browser must retry the same attempt instead of putting its gesture back.
            if prepare and not prepared:
                self.close_connection = True
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass  # the peer left mid-answer; nobody to tell

    def _serve_root(self) -> None:
        if self.page_snapshot is not None:
            revision = self.page_snapshot.active["revision"]
            artifact = self.page_snapshot.artifacts[revision]
            version = self.page_snapshot.active["version"]
        else:
            with PageTransaction(self.page_dir) as page:
                activate_source(self.page_dir, page.events)
                events = page.events
            revision = latest_revision(self.page_dir)
            if revision is None:
                self._json({"error": missing_revision(self.page_dir)}, 404)
                return
            artifact = read_artifact(self.page_dir, revision)
            version = stamped_version(events, revision)
        self._send_document(artifact, revision, version)

    def _revision_name(self, revision: int) -> str:
        if self.page_snapshot is not None:
            return self.page_snapshot.revision_names[revision]
        return revision_path(self.page_dir, revision).name

    def _artifact(self, revision: int) -> RevisionArtifact:
        if self.page_snapshot is not None:
            return self.page_snapshot.artifacts[revision]
        return read_artifact(self.page_dir, revision)

    def _artifact_root(self, revision: int) -> str:
        name = self._revision_name(revision).removesuffix(".html")
        return self.page_root.rstrip("/") + f"/revisions/{name}"

    def _send_document(
        self, artifact: RevisionArtifact, revision: int, version: int | None
    ) -> None:
        """Serve one immutable document under the current delivery boundary."""
        try:
            self.response_layer = artifact.registry["$layer"]["generation"]
            projected = supervised_document(
                deliver_document(
                    artifact.html.decode("utf-8"), self._artifact_root(revision)
                ),
                revision,
                version,
                server_id=self.server_id,
                layer_id=artifact.registry["$layer"]["generation"],
                bootstrap=artifact.resources["/runtime/bootstrap.js"].data.decode(
                    "utf-8"
                ),
                release_id=self.release,
                page_root=self.page_root,
                asset_root=self._artifact_root(revision),
                before_runtime=self._document_head(),
            )
        except ValueError as error:
            self._json({"error": str(error)}, 500)
            return
        self._send(200, "text/html; charset=utf-8", projected)

    def _serve_artifact_resource(self, path: str) -> bool:
        match = re.fullmatch(
            r"/revisions/(?P<name>r(?P<revision>[1-9][0-9]*)-[a-f0-9]{16})/"
            r"(?P<resource>.+)",
            path,
        )
        if match is None:
            return False
        revision = int(match.group("revision"))
        revisions = (
            set(self.page_snapshot.artifacts)
            if self.page_snapshot is not None
            else set(list_revisions(self.page_dir))
        )
        if revision not in revisions:
            return False
        expected = self._revision_name(revision).removesuffix(".html")
        if match.group("name") != expected:
            return False
        artifact = self._artifact(revision)
        self.response_layer = artifact.registry["$layer"]["generation"]
        logical = "/" + match.group("resource")
        if probe_source := PROBE_SOURCES.get(logical):
            self._send(
                200,
                "text/javascript; charset=utf-8",
                scope_script_routes(
                    probe_source.read_bytes(),
                    self.page_root,
                    asset_root=self._artifact_root(revision),
                ),
            )
            return True
        source = logical
        widget = re.fullmatch(r"/widgets/(?P<tag>lf-[a-z0-9-]+)\.js", logical)
        if widget is not None:
            implementation = artifact.implementations.get(widget.group("tag"))
            if implementation is not None:
                source = implementation["path"]
        resource = artifact.resources.get(source)
        if resource is None:
            return False
        root = self._artifact_root(revision)
        body = deliver_resource(resource, source, root)
        if resource.mime == "application/javascript" and not source.startswith(
            "/page/"
        ):
            body = scope_script_routes(body, self.page_root, asset_root=root)
        elif resource.mime == "text/css" and not source.startswith("/page/"):
            body = scope_stylesheet_routes(body, self.page_root, asset_root=root)
        ctype = resource.mime
        if ctype not in BINARY_TYPES:
            ctype += "; charset=utf-8"
        self._send(200, ctype, body)
        return True

    def _document_head(self) -> str:
        """Transport-specific delivery metadata inserted before the runtime entry."""
        return ""

    def _serve_page_path(self, path: str) -> bool:
        if self._serve_artifact_resource(path):
            return True
        if path.startswith("/versions/"):
            version = version_num(Path(path).name)
            events = (
                list(self.page_snapshot.events)
                if self.page_snapshot is not None
                else read_events(self.page_dir)
            )
            mapping = version_revisions(events)
            published = (
                {item["version"] for item in self.page_snapshot.versions}
                if self.page_snapshot is not None
                else set(published_versions(self.page_dir, events))
            )
            if version not in published:
                self._json(
                    {"error": "not stamped yet; run `leaf version stamp` first"},
                    404,
                )
                return True
            artifact = self._artifact(mapping[version])
            self._send_document(artifact, mapping[version], version)
            return True
        if path.startswith("/revisions/"):
            if (
                re.fullmatch(r"/revisions/r[1-9][0-9]*-[a-f0-9]{16}\.html", path)
                is None
            ):
                self._json({"error": "unknown revision resource"}, 404)
                return True
            name = Path(path).name
            revision = revision_num(name)
            revisions = (
                set(self.page_snapshot.documents)
                if self.page_snapshot is not None
                else set(list_revisions(self.page_dir))
            )
            if revision not in revisions:
                self._json({"error": "unknown revision"}, 404)
                return True
            expected_name = (
                self.page_snapshot.revision_names.get(revision)
                if self.page_snapshot is not None
                else revision_path(self.page_dir, revision).name
            )
            if expected_name != name:
                self._json({"error": "unknown revision"}, 404)
                return True
            artifact = self._artifact(revision)
            events = (
                list(self.page_snapshot.events)
                if self.page_snapshot is not None
                else read_events(self.page_dir)
            )
            self._send_document(artifact, revision, stamped_version(events, revision))
            return True
        if path == "/registry.json":
            revision = (
                self.page_snapshot.active["revision"]
                if self.page_snapshot is not None
                else latest_revision(self.page_dir)
            )
            if revision is None:
                return False
            registry = self._artifact(revision).registry
            self.response_layer = registry["$layer"]["generation"]
            self._json(registry)
            return True
        file = self.page_dir / path.lstrip("/")
        # The allowlist rejects traversal spellings; containment is the second
        # boundary for a page directory edited or symlinked after vendoring.
        if file.is_file() and path_is_within(file, self.page_dir):
            ctype = CONTENT_TYPES.get(Path(path).suffix, "application/octet-stream")
            # charset describes an encoding, so it rides on the types that
            # have one. On a PNG it is noise.
            if ctype not in BINARY_TYPES:
                ctype += "; charset=utf-8"
            self._send(200, ctype, file.read_bytes())
            return True
        return False

    def _get(self):
        path = urlsplit(self.path).path
        if probe_source := PROBE_SOURCES.get(path):
            self._send(
                200,
                "text/javascript; charset=utf-8",
                probe_source.read_bytes(),
            )
            return
        if path == "/":
            self._serve_root()
            return
        if path == "/api/news":
            self._news()
            return
        if path == "/api/state":
            # Versions pass through the handler's own view, so a preview state
            # agrees with the version it serves.
            try:
                revision = self.requested_view_revision()
                state = self.page_state(revision)
                self.response_layer = state["layer"]["generation"]
            except ValueError as error:
                self._json({"error": str(error)}, 400)
                return
            self._json(state)
            return
        if path == "/api/data":
            try:
                fragment = self.data_fragment()
            except (DataError, ValueError) as error:
                status = 409 if " is stale; current revision is " in str(error) else 400
                self._json({"error": str(error)}, status)
                return
            self._json(fragment)
            return
        if path == "/api/view":
            try:
                revision = self.requested_view_revision()
                if revision is None:
                    raise ValueError("view revision is required")
                sequence = self.requested_view_sequence()
                browser = self.page_browser_view(revision, sequence)
                self.response_layer = self._artifact(revision).registry["$layer"][
                    "generation"
                ]
            except ValueError as error:
                self._json({"error": str(error)}, 400)
                return
            self._json({"browser": browser})
            return
        # Browsers ask for this unprompted, and go on asking where nothing in the
        # markup names an icon — the runtime's link is written as the chrome is built,
        # which is after the parse. Answering "no content" rather than letting it fall
        # through to 404 keeps the console clean, which is what makes an empty console
        # worth asserting on (the browser render suite).
        if path == "/favicon.ico":
            self._send(204, "image/x-icon", b"")
            return
        if (
            path.startswith("/revisions/") or SERVED_PATH.fullmatch(path)
        ) and self._serve_page_path(path):
            return
        self._json({"error": "not found"}, 404)

    def _post(self):
        path = urlsplit(self.path).path
        if path not in {"/api/event", "/api/media"}:
            self._json({"error": "not found"}, 404)
            return
        # Preview requests have passed authentication and body preparation. An event
        # refusal can therefore name its attempt; media uses the route's generic shape.
        if self.page_snapshot is not None:
            self._refuse("the preview server is read-only", 403)
            return
        try:
            view_revision = self.requested_view_revision(header=True)
        except ValueError as error:
            self._refuse(str(error))
            return
        if view_revision is not None and view_revision not in list_revisions(
            self.page_dir
        ):
            self._refuse(f"unknown view revision r{view_revision}")
            return
        if view_revision is not None:
            current_layer = self._artifact(view_revision).registry["$layer"][
                "generation"
            ]
        else:
            active_revision = latest_revision(self.page_dir)
            current_layer = (
                self._artifact(active_revision).registry["$layer"]["generation"]
                if active_revision is not None
                else self.layer
            )
        self.response_layer = current_layer
        if self.headers.get("Leaf-Layer") != current_layer:
            # Preparation already consumed the body. A stale runtime needs the
            # current generation, not a verdict in a vocabulary it no longer speaks.
            self._json({"layer": current_layer})
            return
        if self.posted_error:
            self._refuse(self.posted_error)
            return
        if path == "/api/media":
            try:
                media_path = store_uploaded_media(
                    self.page_dir,
                    self.posted,
                    self.headers.get("Content-Type", ""),
                )
            except MediaUploadError as error:
                self._refuse(str(error))
                return
            self._json({"path": media_path})
            return
        status, answer = accept_event(
            self.page_dir, self.posted, lambda: self.page_state(view_revision)
        )
        self._json(answer, status)


def handler_for(
    page_dir: Path,
    token: str,
    page_snapshot=None,
    protocol_version="HTTP/1.0",
    publication=None,
):
    """A request handler bound to one page, publication view, and key. The key has no
    default: every server over a page directory is reachable by whatever reached the
    machine, so there is no construction that should quietly go without one."""
    identity = (
        page_snapshot.layer if page_snapshot is not None else layer_metadata(page_dir)
    )
    return type(
        "PageHandler",
        (Handler,),
        {
            "page_dir": page_dir,
            "token": token,
            "server_id": secrets.token_hex(16),
            "bootstrap": (page_dir / "runtime" / "bootstrap.js").read_text(
                encoding="utf-8"
            ),
            "page_snapshot": page_snapshot,
            "protocol_version": protocol_version,
            "layer": identity["generation"],
            "layer_identity": identity,
            "preview": preview_metadata(page_dir),
            "publication": publication,
        },
    )
