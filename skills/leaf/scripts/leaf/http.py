"""HTTP transport and routes for one served page.

The transport is starlette over uvicorn (`hosting.py` owns the server). This file
owns what a page means at that boundary: where a page and its revisions answer
(`revision_delivery` addresses what they name), the key, the layer gate, the `Leaf-*`
headers, and the finite freshness reading a visible tab asks for.
"""

import html
import json
import re
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from .data import (
    DataError,
    StaleDataError,
    deferred_value,
)
from .event_endpoint import accept_event, event_fault, event_rejection
from .file_bindings import FileBindingError, StaleFileError, read_file, save_file
from .files import (
    missing_revision,
    revision_num,
    stamped_version,
    version_num,
    version_revisions,
)
from .interaction_log import append_interactions, client_records
from .layer import foreign_runtime
from .locations import path_is_within
from .media import MAX_MEDIA_UPLOAD_BYTES, MediaUploadError, store_uploaded_media
from .passages import SourceReading
from .refusals import Refused
from .registry.storage import layer_metadata
from .render_checks import PROBE_SOURCES
from .revision_artifact import (
    Resource,
    RevisionArtifact,
)
from .revision_delivery import (
    Delivery,
    DeliveryAddress,
    compose_document,
    deliver_resource,
    delivered_resource,
    layer_import_map,
    rebase_document,
)
from .samples import Samples
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE_MAX_AGE,
    NO_KEY,
    REVISION_NAME,
    SERVED_PATH,
)
from .served_state.service import LivePage, PageSource, PageStateService
from .server import preview_metadata
from .state import now_iso
from .structure import FRAME_ANCESTORS_CSP
from .user_views import observe_user_view

# How deeply a POSTed body may nest its arrays and objects. What reads a body after the
# parse recurses: schema validation runs into the interpreter's recursion limit a few
# hundred levels down, and a log line is parsed again by every later reader, on
# whatever stack that reader has. Past the bound one of them would raise rather than
# answer, which the browser reads as a retryable fault and re-posts for the life of the
# tab. Leaf's own events nest a handful of levels.
MAX_POSTED_DEPTH = 64
TOO_DEEP = f"event nests deeper than {MAX_POSTED_DEPTH} levels"


def reject_json_constant(value: str) -> None:
    """Reject Python's non-standard NaN and infinity JSON extensions."""
    raise ValueError(f"invalid JSON constant {value}")


def nests_deeper_than(value, limit: int) -> bool:
    """Whether parsed JSON holds an array or object more than `limit` levels down.

    Read a level at a time rather than by recursion, since the value has not been
    bounded yet."""
    level = [value]
    for _ in range(limit):
        level = [
            child
            for held in level
            if isinstance(held, (dict, list))
            for child in (held.values() if isinstance(held, dict) else held)
        ]
    return any(isinstance(held, (dict, list)) for held in level)


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


def scope_page_urls(value, page_root: str):
    """Address a state response's documents and message markup at a page root.

    A response carries version addresses and frozen message markup in their canonical,
    root-relative form; beneath a prefix both answer at the page root, as the live
    page's media does.
    """
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
            scoped[key] = rebase_document(item, DeliveryAddress(page_root, page_root))
        else:
            scoped[key] = scope_page_urls(item, page_root)
    return scoped


def child_interaction_page(page_root: str, owner_root: str) -> str:
    """The child identity relative to the durable diagnostic owner."""
    return page_root[len(owner_root) :]


def page_delivery(
    resources: Mapping[str, Resource],
    *,
    server_id: str,
    layer_id: str,
    release_id: str | None = None,
    page_root: str = "",
    asset_root: str | None = None,
    share_url: str | None = None,
) -> Delivery:
    """How an HTTP host delivers a page's document: supervised before anything loads.

    The document is addressed at `page_root` and `asset_root` (`DeliveryAddress`),
    and starts under the import map its layer modules resolve through and the runtime
    bootstrap with its server incarnation probe, so historical
    sources inherit the current delivery boundary without carrying delivery markup
    themselves. A keyed top-level page declares its share address here, including
    on a bare-URL reload. Disposable samples and public website documents have no
    such address. `write_live_shell` delivers published documents the same way.
    """
    assets = asset_root if asset_root is not None else page_root
    address = DeliveryAddress(page_root, assets)
    bootstrap = resources["/runtime/bootstrap.js"].data.decode()
    release = (
        f' data-lf-release="{html.escape(release_id, quote=True)}"'
        if release_id is not None
        else ""
    )
    share = (
        f' data-lf-share-url="{html.escape(share_url, quote=True)}"'
        if share_url is not None
        else ""
    )

    runtime = (
        f'<script data-lf-runtime data-lf-server="{server_id}" '
        f'data-lf-layer="{layer_id}"{release}{share} '
        f'data-lf-page-root="{html.escape(page_root, quote=True)}" '
        f'data-lf-entry="{html.escape(address("/leaf.js"), quote=True)}" '
        f'data-lf-probe="{html.escape(address("/registry.json"), quote=True)}">'
        f"{bootstrap}</script>"
    )

    return Delivery(
        address=address,
        import_map=layer_import_map(assets),
        runtime=runtime,
        page_root=page_root,
    )


@dataclass(frozen=True)
class PostRoute:
    """One POST route: the gates it passes in order, then the handler that answers.

    A gate returns the refusal that answers the request, or None to pass it on; the
    handler takes what the route's path pattern captured. `body` names how the
    request is read before the first gate: an uploaded image's bytes (`media`) or
    one bounded JSON object. A route with `events` refuses and faults in the event
    door's shape, which names the attempt (`event_endpoint`)."""

    handler: Callable[..., Response]
    gates: tuple[Callable[["PageEndpoint"], Response | None], ...] = ()
    body: str = "json"
    events: bool = False


class PageEndpoint:
    """One request against one page, from its arrival to the response it becomes.

    `page_app` makes one per request and throws it away with it, so the routes below
    read the request off `self` and return the response they answer with. The transport
    underneath is uvicorn's: framing, keep-alive, the peer that closes mid-answer, and
    the body a route never asked for are its business, not this file's. What stays here
    is the page's own boundary — selection, the key, the layer gate, and the faults a
    banner has to be able to show.
    """

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
        # Empty on the ordinary one-page server. A published site and a sample's child
        # serve beneath a prefix, and only Leaf-owned routes are rewritten under it.
        self.page_root = page_root
        # The generation this answer speaks, which a route narrows to the revision it
        # actually served.
        self.response_layer = self.layer
        # The revision a POST's layer gate held it to (`_layer_gate`): the one the tab
        # named, or the active one when it named none. None until that gate runs.
        self.layer_revision: int | None = None
        # Set by `authorized` when the key arrived in the query.
        self.set_cookie = False
        # A declared body this request never drained. Those bytes would be read as the
        # next request line on a reused connection, so the answer has to end it.
        self.body_unread = False
        # Set by a route whose successful answer is housekeeping rather than
        # interaction history, which `respond` leaves out of the trace: an attention
        # check, which an untouched page makes four times a second, and a resource's
        # bytes, which a document load asks for a few hundred times. A refusal or
        # fault on either is still traced.
        self.housekeeping = False
        # Set when the route names a child capability, including a revoked one.
        # The opaque child must be able to read refusals and faults as HTTP too.
        self.sample_request = False
        # The endpoint a sample's child answers inside (`SampleEndpoint`); None for
        # the authored page.
        self.parent: PageEndpoint | None = None
        # A POST's body and the refusal reading it earned, which `_answer` reads only
        # once the request is authorized. Empty until then, so a fault met before
        # that still answers in the route's shape.
        self.posted = {}
        self.posted_error: str | None = None

    @property
    def layer(self) -> str:
        """The generation the bound page's vendored layer was composed at.

        Derived rather than stored, so binding a page in `_select_page` cannot leave
        a second copy of it behind. Empty until a multiplexed transport has bound one.
        """
        return self.layer_identity["generation"] if self.layer_identity else ""

    @property
    def source(self) -> PageSource:
        """The page every route reads: the capture this server was given, or the
        bound page directory, read anew.

        Derived rather than stored, like `layer`, because a multiplexed transport
        binds the page directory in `_select_page`, after construction."""
        if self.page_snapshot is not None:
            return self.page_snapshot
        return LivePage(self.page_dir, self.layer_identity)

    def interaction_owner(self) -> "PageEndpoint":
        """The durable authored page retaining every descendant sample's trace."""
        owner = self
        while owner.parent is not None:
            owner = owner.parent
        return owner

    def respond(self) -> Response:
        """Answer this request, on a worker thread of the serving loop's own pool."""
        started = time.monotonic()
        if self.method in {"GET", "HEAD"}:
            answer = self._answer(self._get)
        elif self.method == "OPTIONS":
            answer = self._answer(self._not_found)
        elif self.method == "POST":
            answer = self._answer(self._post, prepare=self._read_posted)
        else:
            answer = self._json({"error": f"unsupported method {self.method}"}, 501)
        if self.method == "HEAD":
            answer.body = b""
        answer.headers.update(self._delivery_headers())
        if self.sample_request:
            answer = self._sample_headers(answer)
        # The request boundary sees successful answers and refusals alike. Keep
        # query strings (including the access key) and request bodies out of it.
        if (
            self.page_dir is not None
            and self.parent is None
            and not (self.housekeeping and answer.status_code < 400)
        ):
            try:
                append_interactions(
                    self.page_dir,
                    [
                        {
                            "source": "server",
                            "ts": now_iso(),
                            "method": self.method,
                            "path": self.path,
                            "status": answer.status_code,
                            "durationMs": round((time.monotonic() - started) * 1000, 3),
                        }
                    ],
                )
            except OSError as error:
                # A diagnostic write must not turn an admitted gesture into a
                # transport failure: the browser would retry an action that landed.
                self.record_fault(error)
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
            source=self.source,
            preview=self.preview,
            publication=self.publication,
        )

    def page_state(self, view_revision: int | None = None) -> dict:
        """The current reading used by GET and accepted POST responses.

        The status a reading dates its activity by is meaningful only beside the log
        snapshot it was read with. Every response therefore keeps the page
        transaction through both files.

        The reading is taken after the activation this response performs and
        before any file the state is built from is read, and that order is the whole
        of its correctness. Taken after the reads, it could name a write this response
        does not carry, and a tab comparing it with the freshness answer would never
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

    def deferred_value(self) -> dict:
        """One contract-declared payload from the source revision the tab holds."""
        source = self.query.get("source", [None])[-1]
        revision = self.query.get("source_revision", [None])[-1]
        key = self.query.get("key", [None])[-1]
        for name, value in (
            ("source", source),
            ("source_revision", revision),
            ("key", key),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} is required")
        view_revision = self.requested_view_revision()
        if view_revision is not None:
            if view_revision not in self.source.revision_names:
                raise ValueError(f"unknown view revision r{view_revision}")
            registry = self._registry(view_revision)
        else:
            registry = self.source.active_registry()
        self.response_layer = registry["$layer"]["generation"]
        reading = self.source.data_source(source, registry)
        return deferred_value(
            reading, registry, source=source, revision=revision, key=key
        )

    def _news(self) -> Response:
        """A finite reading of the files and presence a visible page is watching.

        The browser compares this cheap token with the state it has applied, then
        asks for state only when they differ. Each request releases its HTTP slot,
        so live child pages cannot hold the origin's connections away from modules,
        gestures or revisions. Presence caches its process and lease observations;
        page files are read anew, including external data and authored dependencies.

        This explicit attention door renews the user lease, throttled to a recency.
        Ordinary state reads and captured previews do not prove a user is looking.
        """
        self.housekeeping = True
        return self._content(
            200, "text/plain; charset=utf-8", self.source.news().encode()
        )

    @property
    def key_cookie(self) -> str:
        """One cookie per served origin, using the bound port rather than Host.

        Cookies already distinguish hosts, but ignore ports and schemes. Naming
        those here keeps independent listeners' keys from overwriting each other;
        every same-host server still receives the cookies, so this is no access
        boundary against a malicious server on another port.
        """
        return f"lf_key_{self.request.url.scheme}_{self.server.server_address[1]}"

    def authorized(self) -> bool:
        """The key, from the handover URL or from the cookie an earlier request
        set out of it. One arrival is enough: the runtime's own fetches are
        relative and carry no query, and the bootstrap leaves only the bare
        address in the tab, which the cookie authorizes on reload or from a
        bookmark. Delivery also declares the key for the explicit Share control;
        ordinary page requests continue to use the cookie."""
        if secrets.compare_digest(self.query.get("t", [""])[0], self.token):
            self.set_cookie = True
        else:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            if self.key_cookie not in jar or not secrets.compare_digest(
                jar[self.key_cookie].value, self.token
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
                f"{self.key_cookie}={self.token}; Path=/; Max-Age={KEY_COOKIE_MAX_AGE}; "
                "HttpOnly; SameSite=Strict"
            )
        if self.body_unread:
            headers["Connection"] = "close"
        # Data and media are distinct from executable page source. Strict MIME
        # handling keeps a response from becoming code merely because authored
        # JavaScript tries to import it.
        headers["X-Content-Type-Options"] = "nosniff"
        return headers

    def _content(self, status: int, ctype: str, body: bytes) -> Response:
        """Encode a body whose producer has already addressed its dependencies."""
        is_html = ctype.startswith("text/html")
        headers = {"Content-Type": ctype, "Cache-Control": "no-store"}
        if is_html:
            headers["Content-Security-Policy"] = FRAME_ANCESTORS_CSP
        return Response(body, status_code=status, headers=headers)

    def _resource_content(self, resource: Resource) -> Response:
        """Serve exact resource bytes, with single byte ranges for native playback.

        The resource owner retains exact bytes or an immutable file. Both live and
        captured routes derive size and read only the selected span here; HEAD reads
        no body. RFC 9110 permits ignoring Range; unsupported
        units, malformed or multiple ranges, and If-Range without a validator get the
        complete representation. A valid unsatisfiable range earns 416.
        """
        self.housekeeping = True
        ctype = resource.mime
        if ctype not in BINARY_TYPES:
            ctype += "; charset=utf-8"
        size = resource.size
        status = 200
        window = slice(0, size)
        headers = (
            {"Accept-Ranges": "bytes"}
            if resource.mime.startswith(("video/", "audio/"))
            else {}
        )
        requested = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", requested)
        if (
            self.method == "GET"
            and "Accept-Ranges" in headers
            and not self.headers.get("If-Range")
            and match is not None
            and any(match.groups())
        ):
            first, last = (
                part.lstrip("0") or "0" if part else "" for part in match.groups()
            )

            # Bound decimal parsing by the representation's length; an arbitrarily
            # long numeral is still simply beyond that length.
            def offset(raw: str) -> int:
                return size + 1 if len(raw) > len(str(size)) else int(raw)

            start = offset(first) if first else max(0, size - offset(last))
            end = min(size, offset(last) + 1) if first and last else size
            if first and last and (len(last), last) < (len(first), first):
                pass  # An invalid range is ignored, rather than unsatisfiable.
            elif start >= end:
                status, window = 416, slice(0, 0)
                headers["Content-Range"] = f"bytes */{size}"
            else:
                status, window = 206, slice(start, end)
                headers["Content-Range"] = f"bytes {start}-{end - 1}/{size}"
        body = b"" if self.method == "HEAD" else resource.read(window)
        response = self._content(status, ctype, body)
        headers["Content-Length"] = str(size if self.method == "HEAD" else len(body))
        response.headers.update(headers)
        return response

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
        `_answer`, where the event outbox treats it as retryable. A path no route
        serves is never read, since `_post` answers it 404.
        """
        selected = self._post_route()
        if selected is None:
            return {}, None
        if selected[0].body == "media":
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
        except RecursionError:
            # The parser's own stack ran out, far deeper than the bound.
            return {}, TOO_DEEP
        except ValueError:
            return {}, "invalid JSON"
        if nests_deeper_than(posted, MAX_POSTED_DEPTH):
            return {}, TOO_DEEP
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

    def _speaks_events(self) -> bool:
        """Whether this request's route answers in the event door's shape."""
        if self.method != "POST":
            return False
        selected = self._post_route()
        return selected is not None and selected[0].events

    def _fault(self, error: str) -> Response:
        """Answer a fault in the shape spoken by the route that met it."""
        if self._speaks_events():
            status, body = event_fault(self.posted, error)
            return self._json(body, status)
        return self._json({"error": error}, 500)

    def _refuse(self, error: str, status: int = 400) -> Response:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self._speaks_events():
            status, body = event_rejection(self.posted, error, status)
            return self._json(body, status)
        return self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> Response:
        """One boundary for page selection, authorization, preparation, and faults.

        Unanswered, a fault would reach the transport, which has no page to say it
        about — and the banner would read "Server offline" about a server that is
        up. So every fault becomes a 500 naming itself, which the banner can show to
        the one person still looking, and `record_fault` keeps a copy for whoever
        else reads this host. This is the only place a 500 is written: a route that
        cannot answer raises rather than composing one of its own, so no fault
        reaches a browser without passing the record. Authorization lives here:
        a disposable child's unguessable path grants that child's routes; every
        parent route requires its handover key or cookie. A route added later
        cannot be the one that forgot to ask.
        POST preparation is deliberately after that gate, so an unknown peer cannot
        choose a body-read cost.

        A refused key answers 401 in one shape on every route, the event door
        included. It is no judgment of what was sent, which nobody read, and it
        holds only until the browser presents the key again: opening the printed
        link in any tab sets the cookie the next request carries. So it is never an
        event rejection, whose `final` would have the browser drop the gesture; the
        runtime keeps the gesture pending and names the link (`layer-client.js`).
        """
        prepared = False
        try:
            answered = self._select_page()
            if answered is not None:
                return answered
            sample_answer = self._sample_request()
            if sample_answer is not None:
                return sample_answer
            if not self.authorized():
                if prepare:
                    self.body_unread = True
                return self._json({"error": NO_KEY}, 401)
            if prepare:
                self.posted, self.posted_error = prepare()
                prepared = True
            return route()
        except Exception as error:  # noqa: BLE001 - the boundary answers, never buries
            # Not a refusal: a fault may have landed either side of the append, so the
            # browser must retry the same attempt instead of putting its gesture back.
            if prepare and not prepared:
                self.body_unread = True
            self.record_fault(error)
            return self._fault(f"{type(error).__name__}: {error}")

    def record_fault(self, error: Exception) -> None:
        """Keep a copy of the fault above for a reader other than this browser.

        The kernel has nowhere to keep one. A detached serve's streams go nowhere
        (`detached`), and a foreground serve's carry its URL and lifetime to
        whoever reads them, not a line per fault. The 500's own body is what Leaf
        says by default, and it reaches the one person still looking at the page. A host
        whose streams are read overrides this to keep the operator's copy too.
        """

    def _sample_request(self) -> Response | None:
        """An unguessable child path authorizes only that disposable page.

        Opaque frames cannot carry the parent cookie. Every native loader and API
        uses this same child capability, before the parent cookie gate.
        """
        match = re.fullmatch(
            r"/api/samples/([a-f0-9]{32}(?:~[a-f0-9]{64})?)(/.*)?", self.path
        )
        if match is None:
            return None
        self.sample_request = True
        # Preflight grants no page access. The actual request below checks the
        # capability, so a late read can receive its 404 even after revocation.
        if self.method == "OPTIONS":
            return self._content(204, "text/plain", b"")
        segment, inside = match.groups()
        identity = segment.split("~", 1)[0]
        sample = self.server.samples.get(self.page_dir, identity)
        if sample is None:
            return self._not_found()
        if self.method == "POST" and inside == "/api/release":
            self.read_body(MAX_MEDIA_UPLOAD_BYTES)
            self.server.samples.release(self.page_dir, identity)
            return self._json({"released": True})
        child = SampleEndpoint(
            self.request,
            self.server,
            parent=self,
            path=inside or "/",
            passive=sample.passive,
            asset_root=sample.asset_root,
            page_dir=sample.directory,
            layer_identity=sample.layer,
            page_root=f"{self.page_root}/api/samples/{segment}",
        )
        with sample.lock:
            if sample.closed:
                return self._not_found()
            answer = child.respond()
            self.response_layer = child.response_layer
            self.housekeeping = child.housekeeping
            return answer

    def _sample_headers(self, response: Response) -> Response:
        """Every child-capability answer is readable without parent credentials.

        This includes revoked capabilities and faults: a late native request must
        receive the HTTP result rather than an opaque browser CORS failure.
        """
        response.headers.update(
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
                "Access-Control-Allow-Headers": self.headers.get(
                    "Access-Control-Request-Headers", "*"
                ),
                "Access-Control-Expose-Headers": "*",
                "Referrer-Policy": "no-referrer",
            }
        )
        # An opaque parent is not expressible as a frame-ancestors source. Child
        # capabilities admit nested samples; parent documents keep their policy.
        if response.headers.get("Content-Security-Policy") == FRAME_ANCESTORS_CSP:
            del response.headers["Content-Security-Policy"]
        return response

    def _serve_root(self) -> Response:
        served = self.source.served_document()
        if served is None:
            return self._json({"error": missing_revision(self.page_dir)}, 404)
        return self._serve_document(*served)

    def _revision_name(self, revision: int) -> str:
        return self.source.revision_names[revision]

    def _artifact(self, revision: int) -> RevisionArtifact:
        return self.source.artifact(revision)

    def _reading(self, revision: int) -> SourceReading:
        """One revision's document under its captured vocabulary, without
        materializing its bundle."""
        return self.source.revision(revision)

    def _registry(self, revision: int) -> dict:
        return self._reading(revision).registry

    def _artifact_root(self, revision: int) -> str:
        name = self._revision_name(revision).removesuffix(".html")
        return self.page_root.rstrip("/") + f"/revisions/{name}"

    def _document_asset_root(self, revision: int) -> str:
        """The immutable dependency namespace selected for this document."""
        return self._artifact_root(revision)

    def _sample_asset_root(self, revision: int) -> str | None:
        """A host's public captured graph, or the child's own capability namespace."""
        return None

    def _serve_document(
        self, artifact: RevisionArtifact, revision: int, version: int | None
    ) -> Response:
        """Serve one immutable document under the current delivery boundary."""
        self.response_layer = artifact.registry["$layer"]["generation"]
        projected = compose_document(
            artifact.html.decode("utf-8"),
            revision,
            version,
            executable=artifact.executable,
            widgets=artifact.widgets,
            resources=artifact.resources,
            registry=artifact.registry,
            delivery=self._delivery(artifact, revision),
        )
        response = self._content(200, "text/html; charset=utf-8", projected.encode())
        response.headers["Leaf-Document"] = str(revision)
        return response

    def _delivery(self, artifact: RevisionArtifact, revision: int) -> Delivery:
        """How this transport delivers a document; a transport adds its own marks."""
        return page_delivery(
            artifact.resources,
            server_id=self.server.server_id,
            layer_id=artifact.registry["$layer"]["generation"],
            release_id=self.release,
            page_root=self.page_root,
            asset_root=self._document_asset_root(revision),
            share_url=(
                str(
                    self.request.url.replace(
                        path=f"{self.page_root}/", query=""
                    ).include_query_params(t=self.token)
                )
                if self.token is not None
                else None
            ),
        )

    def _serve_artifact_resource(self) -> Response | None:
        match = re.fullmatch(
            rf"/revisions/(?P<name>{REVISION_NAME})/(?P<resource>.+)",
            self.path,
        )
        if match is None:
            return None
        revision = int(match.group("revision"))
        if self.source.revision_names.get(revision) != match.group("name") + ".html":
            return None
        artifact = self._artifact(revision)
        self.response_layer = artifact.registry["$layer"]["generation"]
        logical = "/" + match.group("resource")
        resource = delivered_resource(
            artifact,
            logical,
            DeliveryAddress(self.page_root, self._artifact_root(revision)),
        )
        if resource is None:
            return None
        response = self._resource_content(resource)
        # The revision name carries its manifest digest and the address is in the URL,
        # so these bytes never change. Every document of one page shares this namespace:
        # a gallery's live samples are each a whole runtime importing the same modules,
        # and refetching each one per document queued them behind one another on the
        # origin's few connections for seconds.
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    def _serve_page_path(self) -> Response | None:
        path = self.path
        served = self._serve_artifact_resource()
        if served is not None:
            return served
        if path.startswith("/versions/"):
            version = version_num(Path(path).name)
            events = self.source.events()
            mapping = version_revisions(events)
            if version not in self.source.published_versions(events):
                return self._json(
                    {"error": "not stamped yet; run `leaf page stamp` first"},
                    404,
                )
            artifact = self._artifact(mapping[version])
            return self._serve_document(artifact, mapping[version], version)
        if path.startswith("/revisions/"):
            if re.fullmatch(rf"/revisions/{REVISION_NAME}\.html", path) is None:
                return self._json({"error": "unknown revision resource"}, 404)
            name = Path(path).name
            revision = revision_num(name)
            if self.source.revision_names.get(revision) != name:
                return self._json({"error": "unknown revision"}, 404)
            return self._serve_document(
                self._artifact(revision),
                revision,
                stamped_version(self.source.events(), revision),
            )
        if path == "/registry.json":
            revision = self.source.active_revision()
            if revision is None:
                return None
            registry = self._registry(revision)
            self.response_layer = registry["$layer"]["generation"]
            return self._json(registry)
        if (resource := self.source.data_resources.get(path)) is not None:
            return self._resource_content(resource)
        file = self.page_dir / path.lstrip("/")
        # The allowlist rejects traversal spellings; containment is the second
        # boundary for a page directory edited or symlinked after vendoring.
        if file.is_file() and path_is_within(file, self.page_dir):
            ctype = CONTENT_TYPES.get(Path(path).suffix, "application/octet-stream")
            resource = deliver_resource(
                Resource(file, ctype),
                path,
                DeliveryAddress(self.page_root, self.page_root),
            )
            return self._resource_content(resource)
        return None

    def _get(self) -> Response:
        path = self.path
        if match := re.fullmatch(r"/api/files/([^/]+)", path):
            if not self.source.writable:
                return self._refuse("Captured previews cannot read live files.", 403)
            try:
                return self._json(read_file(self.page_dir, match[1]))
            except FileBindingError as error:
                return self._refuse(str(error))
        if probe_source := PROBE_SOURCES.get(path):
            return self._content(
                200, "text/javascript; charset=utf-8", probe_source.read_bytes()
            )
        if path == "/":
            return self._serve_root()
        if path == "/api/news":
            return self._news()
        if path == "/api/user-view":
            return self._json(self.source.user_views())
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
        if path == "/api/deferred":
            try:
                deferred = self.deferred_value()
            except StaleDataError as error:
                return self._json({"error": str(error)}, 409)
            except (DataError, ValueError) as error:
                return self._json({"error": str(error)}, 400)
            return self._json(deferred)
        if path == "/api/view":
            try:
                revision = self.requested_view_revision()
                if revision is None:
                    raise ValueError("view revision is required")
                sequence = self.requested_view_sequence()
                browser = self.page_browser_view(revision, sequence)
                self.response_layer = self._registry(revision)["$layer"]["generation"]
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

    def _post(self) -> Response:
        """Answer a POST through the route its path selects: each of the route's
        gates in order, the first refusal answering, then its handler."""
        selected = self._post_route()
        if selected is None:
            return self._not_found()
        route, arguments = selected
        for gate in route.gates:
            if (refusal := gate(self)) is not None:
                return refusal
        return route.handler(self, **arguments)

    def _post_route(self) -> tuple["PostRoute", dict[str, str]] | None:
        """The route this POST's path names, with the arguments its pattern
        captured, or None for a path no route serves."""
        for pattern, route in self.POST_ROUTES.items():
            if match := re.fullmatch(pattern, self.path):
                return route, match.groupdict()
        return None

    def _writable_gate(self) -> Response | None:
        if not self.source.writable:
            return self._refuse("the preview server is read-only", 403)
        return None

    def _layer_gate(self) -> Response | None:
        """Hold a write to the vocabulary the tab speaks.

        The tab names the revision it reads in `Leaf-View-Revision`, or the active
        one by naming none, and sends the layer generation it was built from. A
        stale runtime gets the current generation instead of a verdict in a
        vocabulary it no longer speaks; the body was already read, so the
        connection stays reusable. The revision it held the write to is
        `layer_revision`, which a handler reads rather than resolving the active
        revision again after an activation may have moved it."""
        try:
            view_revision = self.requested_view_revision(header=True)
        except ValueError as error:
            return self._refuse(str(error))
        if view_revision is None:
            view_revision = self.source.active_revision()
        elif view_revision not in self.source.revision_names:
            return self._refuse(f"unknown view revision r{view_revision}")
        self.layer_revision = view_revision
        self.response_layer = (
            self._registry(view_revision)["$layer"]["generation"]
            if view_revision is not None
            else self.layer
        )
        if self.headers.get("Leaf-Layer") != self.response_layer:
            return self._json({"layer": self.response_layer})
        return None

    def _body_gate(self) -> Response | None:
        if self.posted_error:
            return self._refuse(self.posted_error)
        return None

    def _live_files_gate(self) -> Response | None:
        try:
            view_revision = self.requested_view_revision()
        except ValueError as error:
            return self._refuse(str(error))
        if not self.source.writable or (
            view_revision is not None and view_revision != self.source.active_revision()
        ):
            return self._refuse("This view cannot edit live files.", 403)
        return None

    def _same_origin_gate(self) -> Response | None:
        expected_origin = f"{self.request.url.scheme}://{self.request.url.netloc}"
        if self.headers.get("Origin") != expected_origin:
            return self._refuse("File saving requires this page's origin.", 403)
        return None

    def _save_file(self, name: str) -> Response:
        try:
            return self._json(save_file(self.page_dir, name, self.posted))
        except StaleFileError as error:
            return self._json({"error": str(error), "current": error.current}, 409)
        except (FileBindingError, UnicodeEncodeError) as error:
            return self._refuse(str(error))

    def _observe_user_view(self) -> Response:
        # Captured render previews are instruments, not the user's reading.
        if not self.source.writable:
            return self._content(204, "text/plain", b"")
        revision = self.posted.get("revision")
        revisions = self.source.revision_names
        if type(revision) is not int or revision not in revisions:
            return self._refuse("unknown user view revision")
        checks = self.posted.get("checks")
        if isinstance(checks, dict) and checks.get("revision") not in revisions:
            return self._refuse("unknown user view checks revision")
        try:
            observe_user_view(self.page_dir, self.posted)
        except ValueError as error:
            return self._refuse(str(error))
        return self._content(204, "text/plain", b"")

    def _record_interactions(self) -> Response:
        session = self.posted.get("session")
        entries = self.posted.get("entries")
        if not isinstance(session, str) or not session:
            return self._refuse("interaction requires a nonempty session")
        if (
            not isinstance(entries, list)
            or not entries
            or any(not isinstance(entry, dict) for entry in entries)
        ):
            return self._refuse("interaction requires a nonempty array of entries")
        # Every sample directory is temporary, including a nested sample's
        # parent. Retain all descendants in the authored page's trace, with
        # their complete root-relative addresses surviving ancestor release.
        owner = self.interaction_owner()
        page = (
            child_interaction_page(self.page_root, owner.page_root)
            if owner is not self
            else "/"
        )
        try:
            records = client_records(session, page, entries)
        except (TypeError, ValueError) as error:
            return self._refuse(str(error))
        append_interactions(owner.page_dir, records)
        return self._content(204, "text/plain", b"")

    def _create_sample(self) -> Response:
        template = self.posted.get("template")
        passive = self.posted.get("passive", False)
        if (
            not isinstance(template, str)
            or not template
            or not isinstance(passive, bool)
        ):
            return self._refuse(
                "sample requires a template id and a boolean passive value"
            )
        revision = self.layer_revision
        if revision is None:
            return self._refuse("sample requires an active parent revision")
        try:
            # The parent reading is complete before allocation, which validates
            # and writes only the child's directory.
            artifact, events, data = self.source.sample_inputs(revision)
            asset_root = self._sample_asset_root(revision)
            identity = self.server.samples.create(
                self.page_dir,
                artifact,
                self._reading(revision).document,
                events,
                data,
                template,
                passive,
                asset_root,
            )
        except ValueError as error:
            return self._refuse(str(error))
        root = f"{self.page_root}/api/samples/{identity}"
        return self._json(
            {
                "url": root + "/",
                "page": child_interaction_page(
                    root, self.interaction_owner().page_root
                ),
            }
        )

    def _store_media(self) -> Response:
        try:
            media_path = store_uploaded_media(
                self.page_dir,
                self.posted,
                self.headers.get("Content-Type", ""),
            )
        except MediaUploadError as error:
            return self._refuse(str(error))
        return self._json({"path": media_path})

    def _accept_event(self) -> Response:
        view_revision = self.requested_view_revision(header=True)
        status, answer = accept_event(
            self.page_dir, self.posted, lambda: self.page_state(view_revision)
        )
        return self._json(answer, status)

    # Every POST a page answers, by path pattern. A route lists its gates in the
    # order they refuse; its body is already read when the first one runs. File
    # writes are mechanical editing, outside event admission and layer vocabulary,
    # so only the mutable, same-origin page writes them. A sample allocates an
    # independent page from the frozen reading and writes nothing to its parent, so
    # a read-only preview creates one too.
    POST_ROUTES: Mapping[str, PostRoute] = {
        r"/api/files/(?P<name>[^/]+)": PostRoute(
            _save_file, (_live_files_gate, _same_origin_gate, _body_gate)
        ),
        "/api/user-view": PostRoute(_observe_user_view, (_body_gate,)),
        "/api/interaction": PostRoute(_record_interactions, (_body_gate,)),
        "/api/samples": PostRoute(_create_sample, (_layer_gate, _body_gate)),
        "/api/media": PostRoute(
            _store_media, (_writable_gate, _layer_gate, _body_gate), body="media"
        ),
        "/api/event": PostRoute(
            _accept_event, (_writable_gate, _layer_gate, _body_gate), events=True
        ),
    }


class SampleEndpoint(PageEndpoint):
    """A normal child page authorized by its scoped, unguessable route."""

    def __init__(
        self,
        request: Request,
        server,
        *,
        parent: PageEndpoint,
        path: str,
        passive: bool,
        asset_root: str | None,
        **binding,
    ) -> None:
        super().__init__(request, server, **binding)
        self.parent = parent
        # The address inside the child, below the capability its parent matched.
        self.path = path
        self.passive = passive
        self.asset_root = asset_root

    def authorized(self) -> bool:
        return True

    def _document_asset_root(self, revision: int) -> str:
        return self.asset_root or super()._document_asset_root(revision)

    def _sample_asset_root(self, revision: int) -> str | None:
        return self.asset_root

    def record_fault(self, error: Exception) -> None:
        # `_sample_request` builds this child, not the host that chose the parent's
        # class, so wherever the host keeps its copy of a fault is reachable from the
        # parent alone. Recording there also names the address the browser asked at
        # rather than the path inside the child, which is the request an operator
        # reading the fault is looking for.
        self.parent.record_fault(error)

    def _delivery(self, artifact: RevisionArtifact, revision: int) -> Delivery:
        # Every child arrives inert, so its startup cannot take focus from the page;
        # the host releases a live one once it presents. A passive replay never takes
        # input. Whether the child lays out as a block or a window is its frame's to
        # say (sample.js), which its bootstrap asks before it paints.
        return replace(
            super()._delivery(artifact, revision),
            html_attributes={
                "data-lf-user-scope": self.page_root + "/",
                "data-lf-sample": "",
            },
            body_attributes={"inert": ""}
            | ({"data-lf-sample-passive": ""} if self.passive else {}),
        )


def page_endpoint(
    page_dir: Path,
    token: str,
    page_snapshot=None,
    publication=None,
    endpoint: type[PageEndpoint] = PageEndpoint,
) -> partial[PageEndpoint]:
    """Bind one page, publication view, and key to the endpoint each request becomes.

    The layer identity and the preview reading are read once here rather than per
    request: they are facts about the vendored page this server was started over. So
    is whether this Leaf can serve that page at all: every one-page server, durable
    or temporary, passes here before it binds, and refuses naming the re-vendor when
    the page's runtime came from another Leaf (`foreign_runtime`).
    The key has no default: every server over a page directory is reachable by
    whatever reached the machine, so there is no construction that should quietly go
    without one."""
    identity = (
        page_snapshot.context.layer
        if page_snapshot is not None
        else layer_metadata(page_dir)
    )
    if refusal := foreign_runtime(page_dir, identity):
        raise Refused(refusal)
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
    log reads, atomic writes — so they run on the serving loop's worker threads.
    Each answer completes rather than keeping a per-document HTTP connection open.
    """

    server.samples = Samples()

    async def app(scope, receive, send) -> None:
        if scope["type"] != "http":
            raise ValueError(f"leaf serves HTTP, not {scope['type']}")
        answering = endpoint(Request(scope, receive), server)
        response = await run_in_threadpool(answering.respond)
        await response(scope, receive, send)

    return app
