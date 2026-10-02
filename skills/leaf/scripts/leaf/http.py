"""HTTP transport and routes for one served page.

The transport is starlette over uvicorn (`hosting.py` owns the server). This file
owns what a page means at that boundary: where a page and its revisions answer
(`revision_delivery` addresses what they name), the key, the layer gate, the `Leaf-*`
headers, and the news stream a tab listens on.
"""

import html
import json
import re
import secrets
import sys
import time
from collections.abc import Mapping
from dataclasses import replace
from functools import partial
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from . import presence as presence_model
from .data import (
    DataError,
    StaleDataError,
    deferred_value,
    read_contracts,
    read_data,
    read_source,
)
from .event_endpoint import accept_event, event_fault, event_rejection
from .event_log import read_events
from .files import (
    LOOK_S,
    latest_revision,
    list_revisions,
    missing_revision,
    published_versions,
    revision_num,
    revision_path,
    stamped_version,
    version_num,
    version_revisions,
)
from .interaction_log import append_interactions, client_records, now_iso
from .layer import foreign_runtime
from .locations import path_is_within
from .media import MAX_MEDIA_UPLOAD_BYTES, MediaUploadError, store_uploaded_media
from .page_memory import PageMemory, holding
from .passages import SourceReading
from .registry.storage import layer_metadata, require_registry
from .render_checks import PROBE_SOURCES
from .revision_artifact import (
    Resource,
    RevisionArtifact,
    read_artifact,
    read_revision,
)
from .revision_delivery import (
    Delivery,
    DeliveryAddress,
    compose_document,
    deliver_resource,
    layer_import_map,
    rebase_document,
)
from .revisioning import activate_source
from .samples import Samples
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE,
    KEY_COOKIE_MAX_AGE,
    NO_KEY,
    REVISION_NAME,
    SERVED_PATH,
    VIEWED_FILE,
)
from .served_state import reading as served_reading
from .served_state.service import PageStateService
from .server import preview_metadata
from .service import PageTransaction
from .session_cleanup import write_json
from .structure import FRAME_ANCESTORS_CSP

# How long an open news stream, which re-reads the page every `LOOK_S`, may go without
# a word before saying it is still there.
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


def page_delivery(
    resources: Mapping[str, Resource],
    *,
    server_id: str,
    layer_id: str,
    release_id: str | None = None,
    page_root: str = "",
    asset_root: str | None = None,
) -> Delivery:
    """How an HTTP host delivers a page's document: supervised before anything loads.

    The document is addressed at `page_root` and `asset_root` (`DeliveryAddress`),
    and starts under the import map its layer modules resolve through and the runtime
    bootstrap with its server incarnation probe, so historical
    sources inherit the current delivery boundary without carrying delivery markup
    themselves. `write_live_shell` delivers published documents the same way.
    """
    assets = asset_root if asset_root is not None else page_root
    address = DeliveryAddress(page_root, assets)
    bootstrap = resources["/runtime/bootstrap.js"].data.decode()
    release = (
        f' data-lf-release="{html.escape(release_id, quote=True)}"'
        if release_id is not None
        else ""
    )

    runtime = (
        f'<script data-lf-runtime data-lf-server="{server_id}" '
        f'data-lf-layer="{layer_id}"{release} '
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


class PageEndpoint:
    """One request against one page, from its arrival to the response it becomes.

    `page_app` makes one per request and throws it away with it, so the routes below
    read the request off `self` and return the response they answer with. The transport
    underneath is uvicorn's: framing, keep-alive, the peer that closes mid-answer, and
    the body a route never asked for are its business, not this file's. What stays here
    is the page's own boundary — selection, the key, the layer gate, and the faults a
    banner has to be able to show.
    """

    # A page refuses every frame; `SampleEndpoint` answers into its parent page's.
    frame_ancestors_policy = FRAME_ANCESTORS_CSP

    def __init__(
        self,
        request: Request,
        server,
        *,
        page_dir: Path | None = None,
        memory: PageMemory | None = None,
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
        # The page this request is against, and the memory its owner keeps of it
        # (`page_memory`). A one-page server binds both here for the life of the
        # server, through `page_endpoint`; a multiplexed transport binds each request
        # in `_select_page`, from the address it arrived at. A request bound to no
        # owner's memory keeps its readings for itself alone.
        self.page_dir = page_dir
        self.memory = memory or PageMemory()
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
        started = time.monotonic()
        if self.method == "GET":
            answer = self._answer(self._get)
        elif self.method == "POST":
            answer = self._answer(self._post, prepare=self._read_posted)
        else:
            answer = self._json({"error": f"unsupported method {self.method}"}, 501)
        answer.headers.update(self._delivery_headers())
        # The request boundary sees successful answers and refusals alike. Keep
        # query strings (including the access key) and request bodies out of it.
        if self.page_dir is not None and getattr(self, "parent", None) is None:
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
            revisions = (
                set(self.page_snapshot.artifacts)
                if self.page_snapshot is not None
                else set(list_revisions(self.page_dir))
            )
            if view_revision not in revisions:
                raise ValueError(f"unknown view revision r{view_revision}")
            registry = self._registry(view_revision)
        elif self.page_snapshot is not None:
            registry = self.page_snapshot.context.registry
        else:
            registry = require_registry(self.page_dir)
        self.response_layer = registry["$layer"]["generation"]
        if self.page_snapshot is not None:
            reading = self.page_snapshot.context.data["sources"].get(source)
        elif contract := read_contracts(self.page_dir).get(source):
            reading = read_source(self.page_dir, source, contract, registry)
        else:
            reading = None
        return deferred_value(
            reading, registry, source=source, revision=revision, key=key
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
        a preview, whose browser is the render gate's rather than the user's.

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
                    files = served_reading.reading_files(reading)
                else:
                    # Bound per look rather than around the stream, since a binding
                    # must not span the awaits between looks.
                    with holding(self.page_dir, self.memory):
                        files = served_reading.page_reading(self.page_dir)
                        # Presence is re-read on its own clock, and again whenever the
                        # files move. The state answer and this token must describe
                        # the same view.
                        if files != files_said or now - looked >= PRESENCE_S:
                            presence = presence_model.presence_reading(self.page_dir)
                            looked = now
                    reading = served_reading.join_reading(files, presence)
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
        relative and carry no query, and the bootstrap leaves only the bare
        address in the tab, which the cookie authorizes on reload or from a
        bookmark. So nothing has to thread the key through the page, and
        `leaf.js` never learns there is one."""
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
                f"{KEY_COOKIE}={self.token}; Path=/; Max-Age={KEY_COOKIE_MAX_AGE}; "
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

    def _fault(self, error: str) -> Response:
        """Answer a fault in the shape spoken by the route that met it."""
        if self.method == "POST" and self.path == "/api/event":
            status, body = event_fault(self.posted, error)
            return self._json(body, status)
        return self._json({"error": error}, 500)

    def _refuse(self, error: str, status: int = 400) -> Response:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self.method == "POST" and self.path == "/api/event":
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
        reaches a browser without passing the record. The key is checked here for `_delivery_headers`'s
        reason: every request passes through, so there is one gate rather than one
        per method, and a route added later cannot be the one that forgot to ask.
        POST preparation is deliberately after that gate, so an unknown peer cannot
        choose a body-read cost. Everything after selection reads the page through
        its owner's memory.
        """
        prepared = False
        try:
            answered = self._select_page()
            if answered is not None:
                return answered
            with holding(self.page_dir, self.memory):
                if prepare:
                    self.posted, self.posted_error = {}, None
                if not self.authorized():
                    if prepare:
                        self.body_unread = True
                    return self._refuse(NO_KEY, 403)
                sample_answer = self._sample_request()
                if sample_answer is not None:
                    return sample_answer
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
        """Enter a child only after its parent transport has authorized this request."""
        match = re.fullmatch(r"/api/samples/([a-f0-9]{32})(/.*)?", self.path)
        if match is None:
            return None
        identity, inside = match.groups()
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
            page_dir=sample.directory,
            memory=sample.memory,
            layer_identity=sample.layer,
            page_root=f"{self.page_root}/api/samples/{identity}",
        )
        child.path = inside or "/"
        child.parent = self
        child.passive = sample.passive
        child.asset_root = sample.asset_root
        with sample.lock:
            if sample.closed:
                return self._not_found()
            answer = child.respond()
            self.response_layer = child.response_layer
            return answer

    def _serve_root(self) -> Response:
        if self.page_snapshot is not None:
            revision = self.page_snapshot.context.active["revision"]
            artifact = self.page_snapshot.artifacts[revision]
            version = self.page_snapshot.context.active["version"]
        else:
            with PageTransaction(self.page_dir) as page:
                activate_source(self.page_dir)
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

    def _reading(self, revision: int) -> SourceReading:
        """One revision's document under its captured vocabulary, without
        materializing its bundle."""
        if self.page_snapshot is not None:
            return self.page_snapshot.context.revision(revision)
        return read_revision(self.page_dir, revision)

    def _registry(self, revision: int) -> dict:
        return self._reading(revision).registry

    def _artifact_root(self, revision: int) -> str:
        name = self._revision_name(revision).removesuffix(".html")
        return self.page_root.rstrip("/") + f"/revisions/{name}"

    def _document_asset_root(self, revision: int) -> str:
        """The immutable dependency namespace selected for this document."""
        return self._artifact_root(revision)

    def _sample_asset_root(self, revision: int) -> str:
        """Capture the parent's resource provenance when creating a child."""
        return self._document_asset_root(revision)

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
        return self._content(200, "text/html; charset=utf-8", projected.encode())

    def _delivery(self, artifact: RevisionArtifact, revision: int) -> Delivery:
        """How this transport delivers a document; a transport adds its own marks."""
        return page_delivery(
            artifact.resources,
            server_id=self.server.server_id,
            layer_id=artifact.registry["$layer"]["generation"],
            release_id=self.release,
            page_root=self.page_root,
            asset_root=self._document_asset_root(revision),
        )

    def _serve_artifact_resource(self) -> Response | None:
        match = re.fullmatch(
            rf"/revisions/(?P<name>{REVISION_NAME})/(?P<resource>.+)",
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
                200, "text/javascript; charset=utf-8", probe_source.read_bytes()
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
        body = deliver_resource(
            resource,
            source,
            DeliveryAddress(self.page_root, self._artifact_root(revision)),
        )
        ctype = resource.mime
        if ctype not in BINARY_TYPES:
            ctype += "; charset=utf-8"
        return self._content(200, ctype, body)

    def _serve_page_path(self) -> Response | None:
        path = self.path
        served = self._serve_artifact_resource()
        if served is not None:
            return served
        if path.startswith("/versions/"):
            version = version_num(Path(path).name)
            events = (
                list(self.page_snapshot.context.events)
                if self.page_snapshot is not None
                else read_events(self.page_dir)
            )
            mapping = version_revisions(events)
            published = (
                {item["version"] for item in self.page_snapshot.context.versions}
                if self.page_snapshot is not None
                else set(published_versions(self.page_dir, events))
            )
            if version not in published:
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
            revisions = (
                self.page_snapshot.context.revisions
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
                list(self.page_snapshot.context.events)
                if self.page_snapshot is not None
                else read_events(self.page_dir)
            )
            return self._serve_document(
                artifact, revision, stamped_version(events, revision)
            )
        if path == "/registry.json":
            revision = (
                self.page_snapshot.context.active["revision"]
                if self.page_snapshot is not None
                else latest_revision(self.page_dir)
            )
            if revision is None:
                return None
            registry = self._registry(revision)
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
            body = deliver_resource(
                Resource(file.read_bytes(), ctype.partition(";")[0]),
                path,
                DeliveryAddress(self.page_root, self.page_root),
            )
            return self._content(200, ctype, body)
        return None

    def _get(self) -> Response:
        path = self.path
        if probe_source := PROBE_SOURCES.get(path):
            return self._content(
                200, "text/javascript; charset=utf-8", probe_source.read_bytes()
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
        path = self.path
        if path not in {
            "/api/event",
            "/api/media",
            "/api/samples",
            "/api/interaction",
        }:
            return self._json({"error": "not found"}, 404)
        if path == "/api/interaction":
            if self.posted_error:
                return self._refuse(self.posted_error)
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
            # A sample's directory is temporary. Keep its trace in the owning
            # page, with the scoped address identifying which child produced it.
            owner = getattr(self, "parent", None)
            directory = owner.page_dir if owner is not None else self.page_dir
            page = self.page_root[len(owner.page_root) :] if owner is not None else "/"
            append_interactions(directory, client_records(session, page, entries))
            return self._content(204, "text/plain", b"")
        # Preview requests have passed authentication and body preparation. An event
        # refusal can therefore name its attempt; media uses the route's generic shape.
        # A sample allocates an independent page from the frozen reading; it does
        # not write to the preview's parent.
        if self.page_snapshot is not None and path != "/api/samples":
            return self._refuse("the preview server is read-only", 403)
        try:
            view_revision = self.requested_view_revision(header=True)
        except ValueError as error:
            return self._refuse(str(error))
        revisions = (
            self.page_snapshot.artifacts
            if self.page_snapshot is not None
            else list_revisions(self.page_dir)
        )
        if view_revision is not None and view_revision not in revisions:
            return self._refuse(f"unknown view revision r{view_revision}")
        if view_revision is not None:
            current_layer = self._registry(view_revision)["$layer"]["generation"]
        else:
            active_revision = (
                self.page_snapshot.context.active["revision"]
                if self.page_snapshot is not None
                else latest_revision(self.page_dir)
            )
            current_layer = (
                self._registry(active_revision)["$layer"]["generation"]
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
        if path == "/api/samples":
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
            revision = view_revision or active_revision
            if revision is None:
                return self._refuse("sample requires an active parent revision")
            try:
                if self.page_snapshot is not None:
                    artifact = self._artifact(revision)
                    events = list(self.page_snapshot.context.events)
                    data = self.page_snapshot.context.data
                    asset_root = self._sample_asset_root(revision)
                else:
                    with PageTransaction(self.page_dir) as page:
                        artifact = self._artifact(revision)
                        events = page.events
                        data = read_data(self.page_dir, artifact.registry)
                        asset_root = self._sample_asset_root(revision)
                # Allocation validates and writes only the child's directory.
                # Its parent reading is complete before releasing the log lease.
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
            return self._json({"url": f"{self.page_root}/api/samples/{identity}/"})
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


class SampleEndpoint(PageEndpoint):
    """A normal child page whose parent route already checked access."""

    # Drawn in a frame on its parent page, which is the same origin.
    frame_ancestors_policy = "frame-ancestors 'self'"

    def authorized(self) -> bool:
        return True

    def record_fault(self, error: Exception) -> None:
        # `_sample_request` builds this child, not the host that chose the parent's
        # class, so wherever the host keeps its copy of a fault is reachable from the
        # parent alone. Recording there also names the address the browser asked at
        # rather than the path inside the child, which is the request an operator
        # reading the fault is looking for.
        self.parent.record_fault(error)

    def _document_asset_root(self, revision: int) -> str:
        return self.asset_root

    def _delivery(self, artifact: RevisionArtifact, revision: int) -> Delivery:
        # Every child arrives inert, so its startup cannot take focus from the page;
        # the host releases a live one once it presents. A passive replay never takes
        # input. Whether the child lays out as a block or a window is its frame's to
        # say (sample.js), which its bootstrap asks before it paints.
        return replace(
            super()._delivery(artifact, revision),
            html_attributes={"data-lf-user-scope": self.page_root + "/"},
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
    request: they are facts about the vendored page this server was started over. The
    page's memory is made here too, so the server keeps what it reads of the page for
    as long as it serves it, and no longer (`page_memory`). So
    is whether this Leaf can serve that page at all: every one-page server, durable
    or temporary, passes here before it binds, and exits naming the re-vendor when
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
        sys.exit(refusal)
    return partial(
        endpoint,
        page_dir=page_dir,
        memory=PageMemory(),
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

    server.samples = Samples()

    async def app(scope, receive, send) -> None:
        if scope["type"] != "http":
            raise ValueError(f"leaf serves HTTP, not {scope['type']}")
        answering = endpoint(Request(scope, receive), server)
        response = await run_in_threadpool(answering.respond)
        await response(scope, receive, send)

    return app
