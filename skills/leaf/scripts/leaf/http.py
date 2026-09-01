"""HTTP transport and routes for one served page."""

import json
import secrets
import select
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import presence as presence_model
from .event_endpoint import EventEndpoint, event_rejection
from .event_log import read_events
from .files import (
    latest_revision,
    list_revisions,
    list_versions,
    published_versions,
    revision_num,
    revision_path,
    stamped_version,
    version_num,
    version_revisions,
    write_json,
)
from .locations import path_is_within
from .registry.storage import layer_metadata
from .render_checks import PROBE_SOURCES
from .revisioning import activate_source
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE,
    NO_KEY,
    SERVED_PATH,
)
from .served_state import reading as served_reading
from .served_state.service import PageStateService
from .server import preview_metadata
from .service import PageTransaction
from .structure import parse_structure

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
PRESENCE_S = 2.0


def runtime_document(source: str, revision: int, version: int | None = None) -> bytes:
    """Inject the exact immutable identity beside the canonical runtime script."""
    parsed = parse_structure(source)
    scripts = [
        script
        for script in parsed.external_scripts
        if script["attrs"] == {"src": "/leaf.js", "type": "module"}
    ]
    if len(scripts) != 1:
        raise ValueError("document has no canonical script")
    line, column = scripts[0]["position"]
    offset = sum(len(part) + 1 for part in source.split("\n")[: line - 1]) + column
    markers = f'<meta name="lf-revision" data-lf-runtime content="{revision}">' + (
        f'<meta name="lf-version" data-lf-runtime content="{version}">'
        if version is not None
        else ""
    )
    return (source[:offset] + markers + source[offset:]).encode()


class Handler(BaseHTTPRequestHandler):
    page_dir = None
    token = None
    event_endpoint = None
    # Set by `authorized` when the key arrived in the query, cleared by the one
    # writer that spends it.
    set_cookie = False
    # The legacy stamped-version preview widens the public version window for one
    # render process. Exact mutable-source previews use `preview_source` instead.
    # Every server a user reaches exposes noted versions only.
    preview_upto = None
    preview_source = None

    def versions_live(self, events):
        if self.preview_upto is None:
            return published_versions(self.page_dir, events)
        return [
            version
            for version in list_versions(self.page_dir)
            if version <= self.preview_upto
        ]

    def _page_state(
        self,
        events: list,
        source_error: str | None = None,
        view_revision: int | None = None,
    ) -> dict:
        """The page's own state from a caller's transaction-consistent log."""
        return self._state_service()._full_state(
            events, source_error, view_revision=view_revision
        )

    def _state_service(self) -> PageStateService:
        return PageStateService(
            self.page_dir,
            layer=self.layer,
            preview_source=self.preview_source,
            layer_identity=self.layer_identity,
            preview=self.preview,
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
        return self._state_service().page_state(
            view_revision, full_state=self._page_state
        )

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
        try:
            revision = int(raw)
        except (TypeError, ValueError) as error:
            raise ValueError("view revision must be a positive integer") from error
        if revision < 1:
            raise ValueError("view revision must be a positive integer")
        return revision

    def requested_view_sequence(self) -> int:
        raw = parse_qs(urlsplit(self.path).query).get("through_seq", [None])[-1]
        if raw in (None, ""):
            raise ValueError("view sequence is required")
        try:
            sequence = int(raw)
        except (TypeError, ValueError) as error:
            raise ValueError("view sequence must be a non-negative integer") from error
        if sequence < 0:
            raise ValueError("view sequence must be a non-negative integer")
        return sequence

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

        The stream is also the one proof a browser holds the page open, and before
        it the poll was: a page nobody ever opened and one the user studied and left
        looked identical from the agent's side. A tab whose page has no news never
        asks again, so presence is written from here, throttled — it needs a
        recency, not a request log — and never from a preview, whose browser is the
        render gate's rather than the reader's.

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
                files = served_reading.page_reading(self.page_dir)
                # Presence is re-read on its own clock, and again whenever the files
                # move. The tab is about to ask, and the answer it gets is built from
                # fresh presence, so what this stream remembers saying has to be too:
                # said with a stale presence, a presence that then moved back before
                # the next look would leave the tab holding a reading this stream
                # never disagreed with, and never spoke again.
                if files != files_said or now - looked >= PRESENCE_S:
                    presence = presence_model.presence_reading(self.page_dir)
                    looked = now
                reading = f"{files}.{presence}"
                # Before the word goes out, so a listener that has heard the first
                # one is a browser the page already counts as holding it open.
                if (
                    self.preview_upto is None
                    and time.time() - getattr(cls, "viewed_at", 0) > 30
                ):
                    cls.viewed_at = time.time()
                    write_json(self.page_dir / "viewed.json", {"t": cls.viewed_at})
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
        try:
            super().handle()
        except ConnectionError:
            pass

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
            self.send_header("Leaf-Layer", self.layer)
            if fingerprint := self.layer_identity.get("fingerprint"):
                self.send_header("Leaf-Layer-Fingerprint", fingerprint)
        if self.set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{KEY_COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.set_cookie = False
        super().end_headers()

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(
            status, "application/json", json.dumps(obj, ensure_ascii=False).encode()
        )

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
        """The POSTed body as a dict, or the refusal it has already earned.

        Reading and parsing can fail in different ways, all before an append is
        possible. Naming those failures as final lets the outbox put the gesture back;
        an unexpected exception remains inside `_answer` and is therefore retryable.
        """
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        except (TypeError, ValueError, MemoryError):
            return {}, "invalid Content-Length"
        try:
            posted = json.loads(body)
        except (ValueError, RecursionError):
            return {}, "invalid JSON"
        if not isinstance(posted, dict):
            return {}, "event must be a JSON object"
        return posted, None

    def _refuse(self, error: str, status: int = 400) -> None:
        """Answer a refusal in the shape spoken by the route that produced it."""
        if self.command == "POST" and urlsplit(self.path).path == "/api/event":
            status, body = event_rejection(self.posted, error, status)
            self._json(body, status)
        else:
            self._json({"error": error}, status)

    def _answer(self, route, prepare=None) -> None:
        """One boundary for authorization, route preparation, and route faults.

        Unanswered, a fault
        drops the socket, socketserver buries the traceback in stderr nothing reads, and
        the banner says "Server offline" about a server that is up — so every
        fault becomes a 500 naming itself, which the banner can show to the one
        person still looking. The key is checked here for `end_headers`'s reason: every
        request passes through, so there is one gate rather than one per method, and a
        route added later cannot be the one that forgot to ask. POST preparation is
        deliberately after that gate, so an unknown peer cannot choose a body-read cost.
        """
        try:
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
            route()
        except Exception as error:  # noqa: BLE001 - the boundary answers, never buries
            # Not a refusal: a fault may have landed either side of the append, so the
            # browser must retry the same attempt instead of putting its gesture back.
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass  # the peer left mid-answer; nobody to tell

    def _serve_root(self) -> None:
        if self.preview_source is not None:
            events = read_events(self.page_dir)
            revision = self.preview_source["active"]["revision"]
            source = self.preview_source["data"].decode("utf-8")
            version = None
        else:
            with PageTransaction(self.page_dir) as page:
                activate_source(self.page_dir, page.events)
                events = page.events
            try:
                revision = latest_revision(self.page_dir)
            except SystemExit:
                self._json({"error": "no active revision; write index.html first"}, 404)
                return
            source = revision_path(self.page_dir, revision).read_text(encoding="utf-8")
            version = stamped_version(events, revision)
        try:
            projected = runtime_document(source, revision, version)
        except ValueError as error:
            self._json({"error": str(error)}, 500)
            return
        self._send(200, "text/html; charset=utf-8", projected)

    def _serve_page_path(self, path: str) -> bool:
        if path.startswith("/versions/"):
            version = version_num(Path(path).name)
            events = read_events(self.page_dir)
            mapping = version_revisions(events)
            if version not in self.versions_live(events) or version not in mapping:
                self._json(
                    {"error": "not stamped yet; run `leaf version stamp` first"},
                    404,
                )
                return True
            source = (self.page_dir / path.lstrip("/")).read_text(encoding="utf-8")
            self._send(
                200,
                "text/html; charset=utf-8",
                runtime_document(source, mapping[version], version),
            )
            return True
        if path.startswith("/revisions/"):
            name = Path(path).name
            revision = revision_num(name)
            if (
                revision not in list_revisions(self.page_dir)
                or revision_path(self.page_dir, revision).name != name
            ):
                self._json({"error": "unknown revision"}, 404)
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
            except ValueError as error:
                self._json({"error": str(error)}, 400)
                return
            self._json(state)
            return
        if path == "/api/view":
            try:
                revision = self.requested_view_revision()
                if revision is None:
                    raise ValueError("view revision is required")
                sequence = self.requested_view_sequence()
                browser = self.page_browser_view(revision, sequence)
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
        if SERVED_PATH.fullmatch(path) and self._serve_page_path(path):
            return
        self._json({"error": "not found"}, 404)

    def _post(self):
        if urlsplit(self.path).path != "/api/event":
            self._json({"error": "not found"}, 404)
            return
        # Preview requests have passed authentication and body preparation, so
        # their refusal can name the attempt without writing to the real log.
        if self.preview_upto is not None or self.preview_source is not None:
            self._refuse("the preview server is read-only", 403)
            return
        current_layer = self.layer
        if self.headers.get("Leaf-Layer") != current_layer:
            # Preparation already consumed the body. A stale runtime needs the
            # current generation, not a verdict in a vocabulary it no longer speaks.
            self._json({"layer": current_layer})
            return
        if self.posted_error:
            self._refuse(self.posted_error)
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
        status, answer = self.event_endpoint.accept(
            self.posted, lambda: self.page_state(view_revision)
        )
        self._json(answer, status)


def handler_for(
    page_dir: Path,
    token: str,
    preview_upto=None,
    preview_source=None,
    protocol_version="HTTP/1.0",
):
    """A request handler bound to one page, publication view, and key. The key has no
    default: every server over a page directory is reachable by whatever reached the
    machine, so there is no construction that should quietly go without one."""
    identity = layer_metadata(page_dir)
    return type(
        "PageHandler",
        (Handler,),
        {
            "page_dir": page_dir,
            "token": token,
            "preview_upto": preview_upto,
            "preview_source": preview_source,
            "protocol_version": protocol_version,
            "event_endpoint": EventEndpoint(page_dir),
            "layer": identity["generation"],
            "layer_identity": identity,
            "preview": preview_metadata(page_dir),
        },
    )
