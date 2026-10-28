"""HTTP transport and routes for one served page.

The transport is starlette over uvicorn (`hosting.py` owns the server). This file
owns what a page means at that boundary: where a page and its revisions answer
(`revision_delivery` addresses what they name), the key, the layer gate, the `Leaf-*`
headers, and the finite freshness reading a visible tab asks for.

A document runs this process's browser runtime (`runtime_selection`), whose identity
addresses the resources a document loads and is named on every answer (`Leaf-Runtime`)
and on every write a tab sends, so a tab running another runtime reads and writes
nothing here. A website release already names its runtime, so a release answers by its release
alone.
"""

import hashlib
import json
import math
import re
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from urllib.parse import parse_qs

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import FileResponse, Response

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
from .findings import Rejected
from .interaction_log import admit_batch, append_interactions, client_records
from .layer import incompatible_layer, running_leaf
from .locations import path_is_within
from .media import MAX_MEDIA_UPLOAD_BYTES, MediaUploadError, store_uploaded_media
from .passages import SourceReading
from .refusals import Refused
from .registry.storage import layer_metadata, layer_record
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
    runtime_settings,
)
from .runtime_selection import executing, serving_runtime
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


def json_number(parse):
    """`parse` for a JSON number, refusing one past a double's range: a browser, and
    leaf.page's Worker, read it as infinity, which no schema here would refuse."""

    def read(text: str):
        value = parse(text)
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"JSON number {text} is past a double's range")
        return value

    return read


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
    probe: str | None = None,
    runtime_identity: str | None = None,
) -> Delivery:
    """How an HTTP host delivers a page's document: supervised before anything loads.

    The document is addressed at `page_root` and `asset_root` (`DeliveryAddress`),
    and starts under the import map its layer modules resolve through and the runtime
    bootstrap with its server incarnation probe, so historical
    sources inherit the current delivery boundary without carrying delivery markup
    themselves. A keyed top-level page declares its share address here, including
    on a bare-URL reload. Disposable samples and public website documents have no
    such address. `write_live_shell` delivers published documents the same way.

    `probe` is where a tab asks whether its source has moved on to another layer or
    release (`layer-client.js`, `sourceMovedOn`, and `bootstrap.js`'s startup
    recovery), so its answer must name the layer or release a fresh document would
    start under. It defaults to the page's `/registry.json`, whose answer names its
    release. `runtime_identity` is the runtime a host without a release serves the
    document with (`runtime_selection`), which the tab holds every answer to.
    """
    assets = asset_root if asset_root is not None else page_root
    address = DeliveryAddress(page_root, assets)
    runtime = runtime_settings(
        resources["/runtime/bootstrap.js"].data.decode(),
        layer=layer_id,
        page_root=page_root,
        entry=address("/leaf.js"),
        probe=probe or address("/registry.json"),
        declared={
            "data-lf-server": server_id,
            "data-lf-release": release_id,
            "data-lf-share-url": share_url,
            "data-lf-runtime-identity": runtime_identity,
        },
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
    is the page's own boundary — selection, the key, the layer gate, and the faults the
    page's status has to be able to show.
    """

    # Every answer that isn't an immutable revision resource may be stored but is asked
    # for again before each reuse. Document and state answers carry no validator, so
    # every load, Back included, shows the page as it is now. Storing is what lets
    # the browser keep the whole page in its back/forward cache, so Back restores it at
    # once and the runtime catches up from there. Chrome keeps no page whose document or
    # fetches said `no-store`, nor Firefox one whose document did. The disk copy holds
    # what the page directory already holds in plain files, for the same user. leaf.page
    # overrides it (`WebsitePageEndpoint`).
    cache_control = "no-cache"

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
        # ASGI already decoded the path; rebuilding a URL encodes literal ?/# again.
        self.path = request.scope["path"]
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
        # claim. Their panel reads this explicit presentation fact instead of mistaking
        # the deliberately unattended page for an abandoned ordinary Leaf.
        self.publication = publication
        # A website release spans its document, static layer and container image.
        # Ordinary page servers have no release boundary beyond their layer generation.
        self.release = release
        # Empty on the ordinary one-page server. A published site and a sample's child
        # serve beneath a prefix, and only Leaf-owned routes are rewritten under it.
        self.page_root = page_root
        # The generation this answer speaks: the tab's own once it is authorized
        # (`_answer`), narrowed by a route to the revision it actually served.
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
        self.retained_samples = []

    @property
    def samples(self) -> Samples:
        return self.server.samples.setdefault(self.page_dir, Samples())

    @property
    def layer(self) -> str:
        """The generation of the bound page's layer record.

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

    async def __call__(self, scope, receive, send) -> None:
        """Serve through Starlette, decorating its final headers and status once."""
        started = time.monotonic()
        response = await run_in_threadpool(self._response)

        async def deliver(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Cache-Control", self.cache_control)
                if headers.get("Content-Type", "").startswith("text/html"):
                    headers.setdefault("Content-Security-Policy", FRAME_ANCESTORS_CSP)
                headers.update(self._delivery_headers())
                if self.sample_request:
                    self._sample_headers(headers)
                await self._record_response(message["status"], started)
            elif self.method == "HEAD":
                message = {**message, "body": b""}
            await send(message)

        await response(scope, receive, deliver)

    def _response(self) -> Response:
        """Read and answer this request on the serving loop's worker thread."""
        if self.method in {"GET", "HEAD"}:
            return self._answer(self._get)
        if self.method == "OPTIONS":
            return self._answer(self._not_found)
        if self.method == "POST":
            return self._answer(self._post, prepare=self._read_posted)
        return self._json({"error": f"unsupported method {self.method}"}, 501)

    async def _record_response(self, status: int, started: float) -> None:
        # The request boundary sees successful answers and refusals alike. Keep
        # query strings (including the access key) and request bodies out of it.
        if (
            self.page_dir is not None
            and self.parent is None
            and not (self.housekeeping and status < 400)
        ):
            try:
                await run_in_threadpool(
                    append_interactions,
                    self.page_dir,
                    [
                        {
                            "source": "server",
                            "type": "request",
                            "method": self.method,
                            "path": self.path,
                            "status": status,
                            "durationMs": round((time.monotonic() - started) * 1000, 3),
                        }
                    ],
                )
            except OSError as error:
                # A diagnostic write must not turn an admitted gesture into a
                # transport failure: the browser would retry an action that landed.
                await run_in_threadpool(self.record_fault, error)

    def read_body(self, limit: int) -> bytes | None:
        """The request body, read from inside the route that has earned it, and
        kept only up to a bound the route states — `None` says the peer went past it.

        Deliberately not read on arrival: the key gate is upstream of every read
        here, so an unauthenticated peer can neither choose an allocation nor park
        a request on bytes it never sends. Past the bound the rest is read and
        discarded rather than refused unread: a close with bytes still arriving
        resets the connection, and a browser still sending its body reports the
        reset instead of the refusal.
        """

        async def read() -> bytes | None:
            kept: bytearray | None = bytearray()
            async for chunk in self.request.stream():
                if kept is not None:
                    kept += chunk
                    if len(kept) > limit:
                        kept = None
            return None if kept is None else bytes(kept)

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

        A tab names the data version it holds in `Leaf-Data-Version`, and an answer
        whose data is still that version leaves out its sources, which the tab
        restores from the reading it named (`completeData` in `layer-client.js`).
        Data moves only when an agent sets it, so without this every gesture's
        answer would carry back each source value the tab already holds.
        """
        state = self._state_service().page_state(view_revision)
        if self.headers.get("Leaf-Data-Version") == state["data"]["version"]:
            state["data"] = {"version": state["data"]["version"]}
        return state

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        """One revision projected at an exact already-observed log boundary."""
        return self._state_service().page_browser_view(view_revision, through_seq)

    def requested_view_revision(self) -> int | None:
        raw = self.query.get("revision", [None])[-1] or self.headers.get(
            "Leaf-View-Revision"
        )
        if raw in (None, ""):
            return None
        return _query_int(raw, "view revision", 1)

    def named_revision(self) -> int | None:
        """The revision the tab reads: the one it names, or the active one when it
        names none. None before the page has a revision; ValueError for a malformed
        revision or one the page lacks."""
        revision = self.requested_view_revision()
        if revision is None:
            return self.source.active_revision()
        if revision not in self.source.revision_names:
            raise ValueError(f"unknown view revision r{revision}")
        return revision

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
        view_revision = self.named_revision()
        registry = (
            self._registry(view_revision)
            if view_revision is not None
            else self.source.active_registry()
        )
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
        """
        self.housekeeping = True
        return self._content(
            200, "text/plain; charset=utf-8", self.source.news().encode()
        )

    @property
    def key_cookie(self) -> str:
        """Share a cookie across same-key listeners without overwriting other keys.

        Cookies distinguish hosts but ignore ports. The name is derived from the
        key rather than a listener, so a plain link to another page on this host
        works after one keyed arrival. Every same-host server receives the cookie
        regardless of its name; this does not isolate the key from other ports.
        """
        digest = hashlib.sha256(self.token.encode()).hexdigest()[:32]
        return f"lf_key_{digest}"

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
            if not secrets.compare_digest(
                self.request.cookies.get(self.key_cookie, ""), self.token
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
            else:
                headers["Leaf-Runtime"] = serving_runtime().identity
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
        return Response(body, status_code=status, headers={"Content-Type": ctype})

    def _resource_content(self, resource: Resource) -> Response:
        """Starlette streams backing files and owns their HEAD and range requests.

        An in-memory preview capture is already materialized and answers in full;
        HTTP permits ignoring Range. No second range parser lives beside Starlette's.
        """
        self.housekeeping = True
        ctype = resource.mime
        if ctype not in BINARY_TYPES:
            ctype += "; charset=utf-8"
        if isinstance(resource.content, Path):
            return FileResponse(resource.content, media_type=ctype)
        return self._content(200, ctype, resource.content)

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
        body = self.read_body(MAX_MEDIA_UPLOAD_BYTES)
        if body is None:
            return {}, "event exceeds the 10 MiB limit"
        try:
            posted = json.loads(
                body,
                parse_constant=reject_json_constant,
                parse_float=json_number(float),
                parse_int=json_number(int),
            )
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
        body = self.read_body(MAX_MEDIA_UPLOAD_BYTES)
        if body is None:
            return b"", "image exceeds the 10 MiB limit"
        if not body:
            return b"", "image body is empty"
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
            status, body = event_rejection(self.posted, Refused(error), status)
            return self._json(body, status)
        return self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> Response:
        """One boundary for page selection, authorization, preparation, and faults.

        Unanswered, a fault would reach the transport, which has no page to say it
        about — and the page's status would read "Server offline" about a server that is
        up. So every fault becomes a 500 naming itself, which the status can show to
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
            self.response_layer = self._named_layer()
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
        sample = self.samples.get(identity)
        if sample is None:
            return self._not_found()
        if self.method == "POST" and inside == "/api/release":
            self.read_body(MAX_MEDIA_UPLOAD_BYTES)
            self.samples.release(identity)
            return self._json({"released": True})
        child = SampleEndpoint(
            self.request,
            self.server,
            parent=self,
            path=inside or "/",
            asset_root=sample.asset_root,
            page_dir=sample.directory,
            layer_identity=sample.layer,
            page_root=f"{self.page_root}/api/samples/{segment}",
            sample=sample,
        )
        self.retained_samples.append(sample)
        answer = child._response()
        self.response_layer = child.response_layer
        self.housekeeping = child.housekeeping
        self.body_unread = child.body_unread
        return answer

    def _sample_headers(self, headers: MutableHeaders) -> None:
        """Every child-capability answer is readable without parent credentials.

        This includes revoked capabilities and faults: a late native request must
        receive the HTTP result rather than an opaque browser CORS failure.
        """
        headers.update(
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
        if headers.get("Content-Security-Policy") == FRAME_ANCESTORS_CSP:
            del headers["Content-Security-Policy"]

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

    def _named_layer(self) -> str:
        """The generation an answer speaks unless its route serves another revision.
        It is the one the tab reading `named_revision` speaks (`_revision_layer`), or
        the page's own layer when the tab names a revision the page lacks."""
        try:
            return self._revision_layer(self.named_revision())
        except ValueError:
            return self.layer

    def _revision_layer(self, revision: int | None) -> str:
        """The generation a tab reading `revision` speaks: that revision's layer, or
        the page's own when there is no revision.

        A tab whose page was re-initialized under it still holds a revision of the older
        layer, and can read an answer that carries nothing newer, such as a freshness
        token, in that layer. The newer layer reaches it as a revision whose executable
        changed, which the tab installs once the user is not in the middle of
        something (`version.js`). Named in the page's newer layer, the same answer
        would be refused and reload the tab at once (`layer-client.js`)."""
        if revision is None:
            return self.layer
        reading = self._reading(revision)
        return reading.registry["$layer"]["generation"]

    def _artifact_root(self, revision: int) -> str:
        return self._named_root(self._revision_name(revision).removesuffix(".html"))

    def _named_root(self, name: str) -> str:
        """Where a revision's resources answer as this process runs them: its capture
        and this runtime, each named by its identity, so the address names the same
        bytes for as long as a browser may cache it."""
        return (
            self.page_root.rstrip("/")
            + f"/revisions/{name}/{serving_runtime().identity}"
        )

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
        artifact = executing(artifact)
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
            probe=(
                self.page_root.rstrip("/") + "/registry.json"
                if self.release is None
                else None
            ),
            runtime_identity=(
                serving_runtime().identity if self.release is None else None
            ),
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
            rf"/revisions/(?P<name>{REVISION_NAME})/(?P<runtime>[0-9a-f]+)/(?P<resource>.+)",
            self.path,
        )
        if match is None:
            return None
        revision, name = int(match.group("revision")), match.group("name")
        if (
            self.source.revision_names.get(revision) != name + ".html"
            or match.group("runtime") != serving_runtime().identity
        ):
            return None
        response = self._revision_resource(
            revision, "/" + match.group("resource"), self._named_root(name)
        )
        if response is not None:
            # The revision name carries its manifest digest, the runtime's identity
            # names the runtime, and the address is in the URL, so these bytes never
            # change. Every document of one page shares this namespace: a gallery's
            # live samples are each a whole runtime importing the same modules, and
            # refetching each one per document queued them behind one another on the
            # origin's few connections for seconds.
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    def _revision_resource(
        self, revision: int, logical: str, root: str
    ) -> Response | None:
        """One resource of a revision as its documents run it, addressed at `root`
        (`runtime_selection.executing`), or None for a path the revision lacks."""
        artifact = executing(self._artifact(revision))
        self.response_layer = artifact.registry["$layer"]["generation"]
        resource = delivered_resource(
            artifact, logical, DeliveryAddress(self.page_root, root)
        )
        return None if resource is None else self._resource_content(resource)

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
        # boundary for a page directory edited or symlinked after `page init`.
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
                return self._json(None)
            try:
                return self._json(read_file(self.page_dir, match[1]))
            except FileBindingError as error:
                return self._refuse(str(error))
        if probe_source := serving_runtime().probes.get(path):
            return self._content(200, "text/javascript; charset=utf-8", probe_source)
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
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
            # Reading state activates the page's source, which may leave a newer
            # revision active than the one `_answer` resolved before the read.
            if revision is None and state["active"] is not None:
                revision = state["active"]["revision"]
            self.response_layer = self._revision_layer(revision)
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
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
            return self._json({"browser": browser})
        if path == "/api/inspect":
            from .page_inspection import inspect_artifact, inspection_views

            try:
                revision = self.requested_view_revision()
                if revision is None:
                    raise ValueError("view revision is required")
                if revision not in self.source.revision_names:
                    raise ValueError(f"unknown view revision r{revision}")
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
            artifact = self._artifact(revision)
            report = inspect_artifact(artifact, revision)
            report["views"] = inspection_views(self.page_dir, artifact.digest)
            self.response_layer = self._revision_layer(revision)
            return self._json(report)
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

    def _runtime_gate(self) -> Response | None:
        """Hold a write to the runtime the tab runs.

        A tab naming another runtime than this process's, as one from before a restart
        under an updated Leaf does, gets the answer the layer gate gives a stale tab,
        which names this runtime (`_delivery_headers`), so it reloads rather than
        writes. Every served document's runtime names its own (`layer-client.js`,
        `layerHeaders`); a client that runs none, such as a harness posting as the
        user, names none. A website release names its runtime, so its tabs name none.
        Every write route passes this first, whatever vocabulary it speaks, and so does
        a tab's view, which the agent reads as the user's (`user_views`); only the
        interaction log, diagnostics no reader acts on, does not."""
        runtime = self.headers.get("Leaf-Runtime")
        if (
            self.release is None
            and runtime is not None
            and runtime != serving_runtime().identity
        ):
            return self._json({"layer": self.response_layer})
        return None

    def _layer_gate(self) -> Response | None:
        """Hold a write to the vocabulary the tab speaks.

        The tab names the revision it reads (`named_revision`) and sends the layer
        generation it was built from. A stale runtime gets the generation it should
        speak (`_revision_layer`) instead of a verdict in a vocabulary it no longer
        speaks; the body was already read, so the connection stays reusable. The
        revision it held the write to is `layer_revision`, which a handler reads
        rather than resolving the active revision again after an activation may have
        moved it, and the generation is resolved from that same reading."""
        try:
            self.layer_revision = self.named_revision()
        except ValueError as error:
            return self._refuse(str(error))
        self.response_layer = self._revision_layer(self.layer_revision)
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
            return self._refuse("This request requires this page's origin.", 403)
        return None

    def _llm_gate(self) -> Response | None:
        if isinstance(self, SampleEndpoint) or not self.source.writable:
            return self._refuse("LLM access is available only in live pages.", 403)
        return None

    def _connection_gate(self) -> Response | None:
        if isinstance(self, SampleEndpoint) or not self.source.writable:
            return self._refuse(
                "HTTP connections are available only in live pages.", 403
            )
        return None

    def _fetch_connection(self, name: str) -> Response:
        from .http_connections import ConnectionError, fetch

        try:
            return self._json(fetch(self.page_dir, name, self.posted))
        except ConnectionError as error:
            return self._json(error.json(), error.status)

    def _generate(self) -> Response:
        # Keep inference off page startup and ordinary request paths.
        from .llm import LLMError, generate

        try:
            return self._json(generate(self.page_dir, self.posted))
        except LLMError as error:
            return self._json(error.json(), error.status)

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
        try:
            batch = admit_batch(self.posted)
        except ValueError as error:
            return self._refuse(str(error))
        # Every sample directory is temporary, including a nested sample's
        # parent. Retain all descendants in the authored page's trace, with
        # their complete root-relative addresses surviving ancestor release.
        owner = self.interaction_owner()
        page = (
            child_interaction_page(self.page_root, owner.page_root)
            if owner is not self
            else "/"
        )
        append_interactions(
            owner.page_dir, client_records(batch["session"], page, batch["entries"])
        )
        return self._content(204, "text/plain", b"")

    def _create_sample(self) -> Response:
        template = self.posted.get("template")
        if not isinstance(template, str) or not template:
            return self._refuse("sample requires a template id")
        message = self.posted.get("message")
        if message is not None and (not isinstance(message, str) or not message):
            return self._refuse("a sample's message must be a message id")
        revision = self.layer_revision
        if revision is None:
            return self._refuse("sample requires an active parent revision")
        try:
            # The parent reading is complete before allocation, which validates
            # and writes only the child's directory.
            artifact, events, data = self.source.sample_inputs(revision)
            asset_root = self._sample_asset_root(revision)
            identity = self.samples.create(
                self.page_dir,
                artifact,
                self._reading(revision).document,
                events,
                data,
                template,
                message,
                asset_root,
            )
        except (ValueError, Rejected) as error:
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
        view_revision = self.requested_view_revision()
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
        r"/api/connections/(?P<name>[^/]+)": PostRoute(
            _fetch_connection,
            (_runtime_gate, _connection_gate, _same_origin_gate, _body_gate),
        ),
        "/api/llm": PostRoute(
            _generate, (_runtime_gate, _llm_gate, _same_origin_gate, _body_gate)
        ),
        r"/api/files/(?P<name>[^/]+)": PostRoute(
            _save_file,
            (_runtime_gate, _live_files_gate, _same_origin_gate, _body_gate),
        ),
        "/api/user-view": PostRoute(_observe_user_view, (_runtime_gate, _body_gate)),
        "/api/interaction": PostRoute(_record_interactions, (_body_gate,)),
        "/api/samples": PostRoute(
            _create_sample, (_runtime_gate, _layer_gate, _body_gate)
        ),
        "/api/media": PostRoute(
            _store_media,
            (_writable_gate, _runtime_gate, _layer_gate, _body_gate),
            body="media",
        ),
        "/api/event": PostRoute(
            _accept_event,
            (_writable_gate, _runtime_gate, _layer_gate, _body_gate),
            events=True,
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
        sample,
        path: str,
        asset_root: str | None,
        **binding,
    ) -> None:
        super().__init__(request, server, **binding)
        self.parent = parent
        self.sample = sample
        self.retained_samples = parent.retained_samples
        # A child is stored on its parent's terms, which on leaf.page are the site's.
        self.cache_control = parent.cache_control
        # The address inside the child, below the capability its parent matched.
        self.path = path
        self.asset_root = asset_root

    def authorized(self) -> bool:
        return True

    @property
    def samples(self) -> Samples:
        return self.sample.children

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
        # the host releases it once it presents. Whether the child lays out as a
        # block or a window is its frame's to say (sample.js), which its bootstrap
        # asks before it paints.
        return replace(
            super()._delivery(artifact, revision),
            html_attributes={
                "data-lf-user-scope": self.page_root + "/",
                "data-lf-sample": "",
            },
            body_attributes={"inert": ""},
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
    request: they are facts about the layer record this server was started over. So
    is whether this Leaf can serve that page at all: every one-page server, durable
    or temporary, passes here before it binds, and refuses naming `page init` when
    the page's layer is one this Leaf cannot serve (`incompatible_layer`). A
    snapshot serves the revision it froze, which its capture already judged
    (`page_snapshot.capture_page_snapshot`).
    The key has no default: every server over a page directory is reachable by
    whatever reached the machine, so there is no construction that should quietly go
    without one."""
    if page_snapshot is None and (
        refusal := incompatible_layer(page_dir, layer_record(page_dir) or {})
    ):
        raise Rejected([refusal])
    identity = (
        page_snapshot.context.layer
        if page_snapshot is not None
        else layer_metadata(page_dir)
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
    log reads, atomic writes — so they run on the serving loop's worker threads.
    Each answer completes rather than keeping a per-document HTTP connection open.
    The Leaf the server runs, and the browser runtime it serves, are read here, as
    it is built, rather than at its first request, after which its checkout may have
    moved on (`layer.running_leaf`, `runtime_selection.serving_runtime`).
    """

    server.samples = {}
    running_leaf()
    serving_runtime()

    async def app(scope, receive, send) -> None:
        if scope["type"] != "http":
            raise ValueError(f"leaf serves HTTP, not {scope['type']}")
        answering = endpoint(Request(scope, receive), server)
        await answering(scope, receive, send)

    return app
