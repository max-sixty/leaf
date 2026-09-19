"""HTTP transport and routes for one served page.

The transport is starlette over uvicorn (`hosting.py` owns the server). This file
owns what a page means at that boundary: route scoping, the key, the layer gate,
the `Leaf-*` headers, and the news stream a tab listens on.
"""

import html
import json
import re
import secrets
import time
from collections.abc import Mapping
from functools import partial
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

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
from .revision_artifact import Resource, RevisionArtifact, read_artifact
from .revision_delivery import (
    deliver_document,
    deliver_resource,
    delivery_identity,
    delivery_sheets,
)
from .revisioning import activate_source
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE,
    NO_KEY,
    SERVED_PATH,
    VENDORED_FILES,
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


# A rooted path the page's own layer answers: its directories and its vendored files.
# A page served under a prefix has these rebased onto it wherever a script, a
# stylesheet or an attribute names one, so the list is the vendoring contract's.
_ROOTED_PATH = (
    rb"(?:api|page|runtime|widgets|vendor|media)/|(?:"
    + b"|".join(re.escape(name.encode()) for name in VENDORED_FILES)
    + rb")"
)
_ROOTED_SCRIPT_ROUTE = re.compile(rb'(?P<before>["\'`])/(?P<path>' + _ROOTED_PATH + rb")")
_ROOTED_STYLESHEET_ROUTE = re.compile(
    rb'(?P<before>["\'`(])/(?P<path>' + _ROOTED_PATH + rb")"
)

_ROOTED_PAGE_ATTRIBUTE = re.compile(
    rb'(?P<before>=\s*["\'])/(?P<path>' + _ROOTED_PATH + rb")", re.IGNORECASE
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


def _delivery_prelude(
    revision: int, version: int | None, executable: str | None, widgets: dict
) -> str:
    """Declare the delivery's encoding, then the immutable Leaf identity behind it."""
    return DELIVERY_ENCODING_META + delivery_identity(
        revision, version, executable, widgets
    )


def _runtime_assets(asset_root: str = "") -> tuple[str, str]:
    root = asset_root.rstrip("/")
    return (
        f'<link rel="stylesheet" href="{root}/theme.css" data-lf-runtime>',
        f'<script type="module" src="{root}/leaf.js" data-lf-runtime></script>',
    )


def authorize_inline_scripts(document: SourceDocument, nonce: str) -> str:
    """Mark every inline script this document arrived with as one delivery composed.

    Written from the parser's own start-tag spans, back to front so the earlier ones
    keep their offsets. An inline script that reaches the browser without the mark
    does not run. The mark keeps out markup written after delivery only while that
    markup cannot learn it, which holds for a nonce minted per response and not for a
    document written once and served many times (`live_shell`).
    """
    source = document.html
    for end in sorted(
        (script["start_tag_end"] for script in document.inline_scripts), reverse=True
    ):
        source = f'{source[: end - 1]} nonce="{nonce}"{source[end - 1 :]}'
    return source


def runtime_document(
    source: str,
    revision: int,
    executable: str | None,
    widgets: dict,
    version: int | None = None,
) -> bytes:
    """Give a clean authored document its runtime head and immutable identity.

    A document that goes on to run the layer needs the layer's stylesheets with it
    (`delivery_sheets`); this composes the head every delivery shares, and its callers
    differ on that, so each writes the sheets itself.
    """
    document = SourceDocument(source)
    offset = head_open_end_offset(document)
    theme_head, entry_head = _runtime_assets()
    runtime = (
        _delivery_prelude(revision, version, executable, widgets)
        + theme_head
        + entry_head
    )
    return (UTF8_BOM + source[:offset] + runtime + source[offset:]).encode()


def supervised_document(
    source: str,
    revision: int,
    version: int | None,
    *,
    executable: str | None,
    widgets: dict,
    server_id: str,
    layer_id: str,
    resources: Mapping[str, Resource],
    release_id: str | None = None,
    page_root: str = "",
    asset_root: str | None = None,
    before_runtime: str = "",
) -> bytes:
    """Supervise HTTP startup before the module graph or stylesheet can load.

    The served document receives the runtime assets, current layer CSP, this
    delivery's script nonce, and server incarnation probe, so historical sources
    inherit the current delivery boundary without carrying delivery markup
    themselves.

    It also names the page it belongs to. A page answers at three addresses — the
    live root, each stamped version, and each immutable revision — and every one
    of them serves this document, so the page root is the address that stands for
    all of them. The href is relative to the delivery, which has no origin to
    know: it resolves wherever the page directory is mounted.
    """
    source = scope_document_routes(
        source.encode(), page_root, asset_root=asset_root
    ).decode()
    parsed = SourceDocument(source)
    offset = head_open_end_offset(parsed)
    bootstrap = scope_script_routes(
        resources["/runtime/bootstrap.js"].data, page_root, asset_root=asset_root
    ).decode()
    # One nonce per delivery. The head's own scripts carry it as they are written;
    # the authored blocks are marked in place, after route scoping so the offsets
    # are the ones the browser will read.
    nonce = secrets.token_urlsafe(16)
    source = authorize_inline_scripts(parsed, nonce)
    csp = PAGE_CSP + f"; script-src 'self' 'nonce-{nonce}'"
    release = (
        f' data-lf-release="{html.escape(release_id, quote=True)}"'
        if release_id is not None
        else ""
    )
    public_root = f' data-lf-page-root="{html.escape(page_root, quote=True)}"'
    assets = asset_root if asset_root is not None else page_root
    theme_head, entry_head = _runtime_assets(assets)
    asset_path = assets.rstrip("/")
    bootstrap_head = (
        f'<script nonce="{nonce}" data-lf-runtime data-lf-server="{server_id}" '
        f'data-lf-layer="{layer_id}"{release}{public_root} '
        f'data-lf-entry="{asset_path}/leaf.js" '
        f'data-lf-theme="{asset_path}/theme.css" '
        f'data-lf-probe="{asset_path}/registry.json">{bootstrap}</script>'
    )
    supervised = (
        _delivery_prelude(revision, version, executable, widgets)
        + f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}">'
        + bootstrap_head
        + theme_head
        + delivery_sheets(
            resources,
            lambda css, _path: scope_stylesheet_routes(
                css.encode(), page_root, asset_root=asset_root
            ).decode(),
        )
        + before_runtime
        + entry_head
        + f'<link rel="canonical" href="{html.escape(page_root, quote=True)}/" data-lf-runtime>'
    )
    return (source[:offset] + supervised + source[offset:]).encode()


class PageEndpoint:
    """One request against one page, from its arrival to the response it becomes.

    `page_app` makes one per request and throws it away with it, so the routes below
    read the request off `self` and return the response they answer with. The transport
    underneath is uvicorn's: framing, keep-alive, the peer that closes mid-answer, and
    the body a route never asked for are its business, not this file's. What stays here
    is the page's own boundary — selection, the key, the layer gate, and the faults a
    banner has to be able to show.
    """

    # One value for the whole transport rather than a per-request binding: the MCP
    # delivery server clears it, because it serves into a frame it cannot name.
    frame_ancestors_policy = FRAME_ANCESTORS_CSP

    def __init__(
        self,
        request: Request,
        server,
        *,
        page_dir: Path | None = None,
        token: str | None = None,
        layer_identity: dict | None = None,
        preview: dict | None = None,
        page_snapshot=None,
        publication=None,
        release: str | None = None,
        page_root: str = "",
    ) -> None:
        self.request = request
        self.server = server
        self.method = request.method
        self.headers = request.headers
        # Path and query apart, because `_select_page` rewrites the path: a multiplexed
        # transport strips its own prefix there and every route below reads the page's
        # own address, while the query it arrived with is untouched either way.
        self.path = request.url.path
        self.query = parse_qs(request.url.query)
        # The page this request is against. A one-page server binds it here for the
        # life of the server, through `page_endpoint`; a multiplexed transport binds
        # each request in `_select_page`, from the address it arrived at.
        self.page_dir = page_dir
        self.token = token
        self.layer_identity = layer_identity
        self.preview = preview
        self.page_snapshot = page_snapshot
        # Published website pages use the complete server contract without a Leaf work
        # claim. Their banner reads this explicit presentation fact instead of mistaking
        # the deliberately unattended page for an abandoned ordinary Leaf.
        self.publication = publication
        # A website release spans its document, static layer and container image.
        # Ordinary page servers have no release boundary beyond their vendored layer.
        self.release = release
        # Empty on the ordinary one-page server. The MCP delivery server sets this to
        # an unguessable `/p/<capability>` prefix and rewrites only Leaf-owned routes.
        self.page_root = page_root
        # The generation this answer speaks, which a route narrows to the revision it
        # actually served.
        self.response_layer = self.layer
        # Set by `authorized` when the key arrived in the query.
        self.set_cookie = False
        # A declared body this request never drained. Those bytes would be read as the
        # next request line on a reused connection, so the answer has to end it.
        self.body_unread = False

    @property
    def layer(self) -> str:
        """The generation the bound page's vendored layer was composed at.

        Derived rather than stored, so binding a page in `_select_page` cannot leave
        a second copy of it behind. Empty until a multiplexed transport has bound one.
        """
        return self.layer_identity["generation"] if self.layer_identity else ""

    def respond(self) -> Response:
        """Answer this request, on a worker thread of the serving loop's own pool."""
        if self.method == "GET":
            answer = self._answer(self._get)
        elif self.method == "POST":
            answer = self._answer(self._post, prepare=self._read_posted)
        else:
            answer = self._json({"error": f"unsupported method {self.method}"}, 501)
        if answer is None:
            # A route that returned without answering. Nothing sensible is left to
            # say, and the peer is owed a status rather than a dropped connection.
            return Response(b"", status_code=500)
        answer.headers.update(self._delivery_headers())
        return answer

    def read_body(self, limit: int | None = None) -> bytes | None:
        """The request body, read from inside the route that has earned it, and
        never past a bound the route states — `None` says the peer went past it.

        Deliberately not read on arrival: the key gate is upstream of every read
        here, so an unauthenticated peer can neither choose an allocation nor park
        a request on bytes it never sends. The bound belongs to the read rather
        than to `Content-Length`, which a chunked body does not carry at all.
        """

        async def read() -> bytes | None:
            body = bytearray()
            async for chunk in self.request.stream():
                body += chunk
                if limit is not None and len(body) > limit:
                    return None
            return bytes(body)

        return anyio.from_thread.run(read)

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
            else self.query.get("revision", [None])[-1]
            or self.headers.get("Leaf-View-Revision")
        )
        if raw in (None, ""):
            return None
        return _query_int(raw, "view revision", 1)

    def requested_view_sequence(self) -> int:
        raw = self.query.get("through_seq", [None])[-1]
        if raw in (None, ""):
            raise ValueError("view sequence is required")
        return _query_int(raw, "view sequence", 0)

    def data_fragment(self) -> dict:
        """One contract-declared payload from the data revision the tab holds."""
        data_revision = _query_int(
            self.query.get("data_revision", [None])[-1], "data_revision", 0
        )
        source = self.query.get("source", [None])[-1]
        key = self.query.get("key", [None])[-1]
        snapshot = self.query.get("snapshot", [None])[-1]
        if not isinstance(source, str) or not source:
            raise ValueError("source is required")
        if not isinstance(key, str) or not key:
            raise ValueError("key is required")
        if snapshot is not None and not valid_snapshot_id(snapshot):
            raise ValueError("snapshot must be a positive decimal revision")
        view_revision = self.requested_view_revision()
        if view_revision is not None:
            revisions = (
                set(self.page_snapshot.artifacts)
                if self.page_snapshot is not None
                else set(list_revisions(self.page_dir))
            )
            if view_revision not in revisions:
                raise ValueError(f"unknown view revision r{view_revision}")
            registry = self._artifact(view_revision).registry
        elif self.page_snapshot is not None:
            registry = self.page_snapshot.registry
        else:
            registry = require_registry(self.page_dir)
        self.response_layer = registry["$layer"]["generation"]
        if self.page_snapshot is not None:
            return data_fragment(
                self.page_snapshot.data,
                registry,
                data_revision=data_revision,
                source=source,
                key=key,
                snapshot_id=snapshot,
            )
        with PageTransaction(self.page_dir):
            return read_data_fragment(
                self.page_dir,
                registry,
                data_revision=data_revision,
                source=source,
                key=key,
                snapshot_id=snapshot,
            )

    def _news(self) -> StreamingResponse:
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

        Ends on the server stopping; a tab that closes cancels the response, which the
        transport reports without this loop watching the socket for it. `ALIVE_S` is
        the whole of the keepalive, so the stream carries no comment frames beside it.
        """
        return StreamingResponse(
            self._readings(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store"},
        )

    async def _readings(self):
        """Every reading this stream owes its listener, as each becomes true."""
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
                    and time.time() - self.server.viewed_at > 30
                ):
                    self.server.viewed_at = time.time()
                    write_json(
                        self.page_dir / VIEWED_FILE, {"t": self.server.viewed_at}
                    )
                if reading != said or now - spoke >= ALIVE_S:
                    yield f"data: {reading}\n\n"
                    said, files_said, spoke = reading, files, now
                await anyio.sleep(LOOK_S)
        except (FileNotFoundError, NotADirectoryError):
            # The page directory going away under an open tab ends the stream, as a
            # peer going away does. The response has already begun, so there is no
            # status left to say it with.
            return

    def authorized(self) -> bool:
        """The key, from the handover URL or from the cookie an earlier request
        set out of it. One arrival is enough: the runtime's own fetches are
        relative and carry no query, and a reader who reloads or bookmarks the bare
        address is the same reader. So nothing has to thread the key through the
        page, and `leaf.js` never learns there is one."""
        if secrets.compare_digest(self.query.get("t", [""])[0], self.token):
            self.set_cookie = True
        else:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            if KEY_COOKIE not in jar or not secrets.compare_digest(
                jar[KEY_COOKIE].value, self.token
            ):
                return False
        return True

    def _delivery_headers(self) -> dict[str, str]:
        """What every response carries, whichever route it came from.

        Answered or refused, a response passes through here exactly once, so the
        delivery identity and the key cookie have one writer rather than one per
        route that remembers them.
        """
        headers = {}
        if self.path.startswith(
            ("/api/", "/versions/", "/revisions/")
        ) or self.path in {"/registry.json", "/"}:
            headers["Leaf-Layer"] = self.response_layer
            headers["Leaf-Server"] = self.server.server_id
            if self.release is not None:
                headers["Leaf-Release"] = self.release
        if self.set_cookie:
            headers["Set-Cookie"] = (
                f"{KEY_COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict"
            )
        if self.body_unread:
            headers["Connection"] = "close"
        # Data and media are distinct from executable page source. Strict MIME
        # handling keeps a response from becoming code merely because authored
        # JavaScript tries to import it.
        headers["X-Content-Type-Options"] = "nosniff"
        return headers

    def _content(self, status: int, ctype: str, body: bytes) -> Response:
        """One body, its Leaf routes rewritten for wherever this page is mounted."""
        is_html = ctype.startswith("text/html")
        if is_html:
            body = scope_document_routes(body, self.page_root)
        elif ctype.startswith("text/css"):
            body = scope_stylesheet_routes(body, self.page_root)
        elif ctype.startswith(("text/javascript", "application/javascript")):
            body = scope_script_routes(body, self.page_root)
        headers = {"Content-Type": ctype, "Cache-Control": "no-store"}
        if is_html and self.frame_ancestors_policy:
            headers["Content-Security-Policy"] = self.frame_ancestors_policy
        return Response(body, status_code=status, headers=headers)

    def _json(self, obj, status: int = 200) -> Response:
        return self._content(
            status,
            "application/json",
            json.dumps(
                scope_page_urls(obj, self.page_root), ensure_ascii=False
            ).encode(),
        )

    def _select_page(self) -> Response | None:
        """Bind this request to a page before entering its HTTP boundary.

        A one-page server is bound already, by the constructor `page_endpoint` binds.
        Multiplexed transports override this hook and answer instead of binding: with
        the refusal an unknown route has earned, or with a transport-owned route's own
        response, such as a health check.
        """
        return None

    def _not_found(self) -> Response:
        # An unread body makes the connection unsafe to reuse.
        if self.headers.get("Content-Length") or self.headers.get("Transfer-Encoding"):
            self.body_unread = True
        return self._json({"error": "not found"}, 404)

    def _read_posted(self) -> tuple:
        """The route's POSTed body, or the refusal it has already earned.

        Reading and parsing can fail in different ways, all before a write is possible.
        Each earns a deterministic refusal; an unexpected exception remains inside
        `_answer`, where the event outbox treats it as retryable.
        """
        if self.path == "/api/media":
            return self._read_uploaded_media()
        # A declared length the door will not take, refused before the read rather
        # than after it: an event is prose, markup and passages, and a body past this
        # bound is a peer choosing what this process waits for and holds in memory.
        # A chunked body declares no length, so the read carries the same bound.
        body = None
        if int(self.headers.get("Content-Length", 0)) <= MAX_MEDIA_UPLOAD_BYTES:
            body = self.read_body(MAX_MEDIA_UPLOAD_BYTES)
        if body is None:
            self.body_unread = True
            return {}, "event exceeds the 10 MiB limit"
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
            self.body_unread = True
            return b"", "invalid Content-Length"
        if length < 1:
            self.body_unread = True
            return b"", "image body is empty"
        if length > MAX_MEDIA_UPLOAD_BYTES:
            self.body_unread = True
            return b"", "image exceeds the 10 MiB limit"
        body = self.read_body()
        if len(body) != length:
            self.body_unread = True
            return b"", "incomplete image body"
        return body, None

    def _refuse(self, error: str, status: int = 400) -> Response:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self.method == "POST" and self.path == "/api/event":
            status, body = event_rejection(self.posted, error, status)
            return self._json(body, status)
        return self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> Response | None:
        """One boundary for page selection, authorization, preparation, and faults.

        Unanswered, a fault would reach the transport, which has no page to say it
        about — and the banner would read "Server offline" about a server that is
        up. So every fault becomes a 500 naming itself, which the banner can show to
        the one person still looking. The key is checked here for `_delivery_headers`'s
        reason: every request passes through, so there is one gate rather than one
        per method, and a route added later cannot be the one that forgot to ask.
        POST preparation is deliberately after that gate, so an unknown peer cannot
        choose a body-read cost.
        """
        prepared = False
        try:
            answered = self._select_page()
            if answered is not None:
                return answered
            if prepare:
                self.posted, self.posted_error = {}, None
            if not self.authorized():
                if prepare:
                    self.body_unread = True
                return self._refuse(NO_KEY, 403)
            if prepare:
                self.posted, self.posted_error = prepare()
                prepared = True
            return route()
        except Exception as error:  # noqa: BLE001 - the boundary answers, never buries
            # Not a refusal: a fault may have landed either side of the append, so the
            # browser must retry the same attempt instead of putting its gesture back.
            if prepare and not prepared:
                self.body_unread = True
            return self._json({"error": f"{type(error).__name__}: {error}"}, 500)

    def _serve_root(self) -> Response:
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
                return self._json({"error": missing_revision(self.page_dir)}, 404)
            artifact = read_artifact(self.page_dir, revision)
            version = stamped_version(events, revision)
        return self._serve_document(artifact, revision, version)

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

    def _serve_document(
        self, artifact: RevisionArtifact, revision: int, version: int | None
    ) -> Response:
        """Serve one immutable document under the current delivery boundary."""
        try:
            self.response_layer = artifact.registry["$layer"]["generation"]
            projected = supervised_document(
                deliver_document(
                    artifact.html.decode("utf-8"), self._artifact_root(revision)
                ),
                revision,
                version,
                executable=artifact.executable,
                widgets=artifact.widgets,
                server_id=self.server.server_id,
                layer_id=artifact.registry["$layer"]["generation"],
                resources=artifact.resources,
                release_id=self.release,
                page_root=self.page_root,
                asset_root=self._artifact_root(revision),
                before_runtime=self._document_head(),
            )
        except ValueError as error:
            return self._json({"error": str(error)}, 500)
        return self._content(200, "text/html; charset=utf-8", projected)

    def _serve_artifact_resource(self) -> Response | None:
        match = re.fullmatch(
            r"/revisions/(?P<name>r(?P<revision>[1-9][0-9]*)-[a-f0-9]{16})/"
            r"(?P<resource>.+)",
            self.path,
        )
        if match is None:
            return None
        revision = int(match.group("revision"))
        revisions = (
            set(self.page_snapshot.artifacts)
            if self.page_snapshot is not None
            else set(list_revisions(self.page_dir))
        )
        if revision not in revisions:
            return None
        expected = self._revision_name(revision).removesuffix(".html")
        if match.group("name") != expected:
            return None
        artifact = self._artifact(revision)
        self.response_layer = artifact.registry["$layer"]["generation"]
        logical = "/" + match.group("resource")
        if probe_source := PROBE_SOURCES.get(logical):
            return self._content(
                200,
                "text/javascript; charset=utf-8",
                scope_script_routes(
                    probe_source.read_bytes(),
                    self.page_root,
                    asset_root=self._artifact_root(revision),
                ),
            )
        source = logical
        widget = re.fullmatch(r"/widgets/(?P<tag>lf-[a-z0-9-]+)\.js", logical)
        if widget is not None:
            implementation = artifact.implementations.get(widget.group("tag"))
            if implementation is not None:
                source = implementation["path"]
        if source != logical:
            target = json.dumps(self._artifact_root(revision) + source)
            return self._content(
                200,
                "application/javascript; charset=utf-8",
                f"export * from {target};\n".encode(),
            )
        resource = artifact.resources.get(source)
        if resource is None:
            return None
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
        return self._content(200, ctype, body)

    def _document_head(self) -> str:
        """Transport-specific delivery metadata inserted before the runtime entry."""
        return ""

    def _serve_page_path(self) -> Response | None:
        path = self.path
        served = self._serve_artifact_resource()
        if served is not None:
            return served
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
                return self._json(
                    {"error": "not stamped yet; run `leaf version stamp` first"},
                    404,
                )
            artifact = self._artifact(mapping[version])
            return self._serve_document(artifact, mapping[version], version)
        if path.startswith("/revisions/"):
            if (
                re.fullmatch(r"/revisions/r[1-9][0-9]*-[a-f0-9]{16}\.html", path)
                is None
            ):
                return self._json({"error": "unknown revision resource"}, 404)
            name = Path(path).name
            revision = revision_num(name)
            revisions = (
                set(self.page_snapshot.documents)
                if self.page_snapshot is not None
                else set(list_revisions(self.page_dir))
            )
            if revision not in revisions:
                return self._json({"error": "unknown revision"}, 404)
            expected_name = (
                self.page_snapshot.revision_names.get(revision)
                if self.page_snapshot is not None
                else revision_path(self.page_dir, revision).name
            )
            if expected_name != name:
                return self._json({"error": "unknown revision"}, 404)
            artifact = self._artifact(revision)
            events = (
                list(self.page_snapshot.events)
                if self.page_snapshot is not None
                else read_events(self.page_dir)
            )
            return self._serve_document(
                artifact, revision, stamped_version(events, revision)
            )
        if path == "/registry.json":
            revision = (
                self.page_snapshot.active["revision"]
                if self.page_snapshot is not None
                else latest_revision(self.page_dir)
            )
            if revision is None:
                return None
            registry = self._artifact(revision).registry
            self.response_layer = registry["$layer"]["generation"]
            return self._json(registry)
        file = self.page_dir / path.lstrip("/")
        # The allowlist rejects traversal spellings; containment is the second
        # boundary for a page directory edited or symlinked after vendoring.
        if file.is_file() and path_is_within(file, self.page_dir):
            ctype = CONTENT_TYPES.get(Path(path).suffix, "application/octet-stream")
            # charset describes an encoding, so it rides on the types that
            # have one. On a PNG it is noise.
            if ctype not in BINARY_TYPES:
                ctype += "; charset=utf-8"
            return self._content(200, ctype, file.read_bytes())
        return None

    def _get(self) -> Response | None:
        path = self.path
        if probe_source := PROBE_SOURCES.get(path):
            return self._content(
                200,
                "text/javascript; charset=utf-8",
                probe_source.read_bytes(),
            )
        if path == "/":
            return self._serve_root()
        if path == "/api/news":
            return self._news()
        if path == "/api/state":
            # Versions pass through the endpoint's own view, so a preview state
            # agrees with the version it serves.
            try:
                revision = self.requested_view_revision()
                state = self.page_state(revision)
                self.response_layer = state["layer"]["generation"]
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
            return self._json(state)
        if path == "/api/data":
            try:
                fragment = self.data_fragment()
            except (DataError, ValueError) as error:
                status = 409 if " is stale; current revision is " in str(error) else 400
                return self._json({"error": str(error)}, status)
            return self._json(fragment)
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
                return self._json({"error": str(error)}, 400)
            return self._json({"browser": browser})
        # Browsers ask for this unprompted, and go on asking where nothing in the
        # markup names an icon — the runtime's link is written as the chrome is built,
        # which is after the parse. Answering "no content" rather than letting it fall
        # through to 404 keeps the console clean, which is what makes an empty console
        # worth asserting on (the browser render suite).
        if path == "/favicon.ico":
            return self._content(204, "image/x-icon", b"")
        if path.startswith("/revisions/") or SERVED_PATH.fullmatch(path):
            served = self._serve_page_path()
            if served is not None:
                return served
        return self._json({"error": "not found"}, 404)

    def _post(self) -> Response | None:
        path = self.path
        if path not in {"/api/event", "/api/media"}:
            return self._json({"error": "not found"}, 404)
        # Preview requests have passed authentication and body preparation. An event
        # refusal can therefore name its attempt; media uses the route's generic shape.
        if self.page_snapshot is not None:
            return self._refuse("the preview server is read-only", 403)
        try:
            view_revision = self.requested_view_revision(header=True)
        except ValueError as error:
            return self._refuse(str(error))
        if view_revision is not None and view_revision not in list_revisions(
            self.page_dir
        ):
            return self._refuse(f"unknown view revision r{view_revision}")
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
            return self._json({"layer": current_layer})
        if self.posted_error:
            return self._refuse(self.posted_error)
        if path == "/api/media":
            try:
                media_path = store_uploaded_media(
                    self.page_dir,
                    self.posted,
                    self.headers.get("Content-Type", ""),
                )
            except MediaUploadError as error:
                return self._refuse(str(error))
            return self._json({"path": media_path})
        status, answer = accept_event(
            self.page_dir, self.posted, lambda: self.page_state(view_revision)
        )
        return self._json(answer, status)


def page_endpoint(
    page_dir: Path,
    token: str,
    page_snapshot=None,
    publication=None,
    endpoint: type[PageEndpoint] = PageEndpoint,
) -> partial[PageEndpoint]:
    """Bind one page, publication view, and key to the endpoint each request becomes.

    The layer identity and the preview reading are read once here rather than per
    request: they are facts about the vendored page this server was started over. The
    key has no default: every server over a page directory is reachable by whatever
    reached the machine, so there is no construction that should quietly go without
    one."""
    identity = (
        page_snapshot.layer if page_snapshot is not None else layer_metadata(page_dir)
    )
    return partial(
        endpoint,
        page_dir=page_dir,
        token=token,
        layer_identity=identity,
        preview=preview_metadata(page_dir),
        page_snapshot=page_snapshot,
        publication=publication,
    )


def page_app(endpoint, server):
    """The ASGI application one bound endpoint serves, on one server's behalf.

    Every request becomes its own `PageEndpoint` and nothing else: no state crosses
    between two of them. The routes are ordinary blocking code — page transactions,
    log reads, atomic writes — so they run on the serving loop's worker threads, and
    an open news stream is the one response that stays on the loop itself.
    """

    async def app(scope, receive, send) -> None:
        if scope["type"] != "http":
            raise ValueError(f"leaf serves HTTP, not {scope['type']}")
        answering = endpoint(Request(scope, receive), server)
        response = await run_in_threadpool(answering.respond)
        await response(scope, receive, send)

    return app
