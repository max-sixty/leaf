"""HTTP transport and state responses for one served page."""

import json
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .data import read_data
from .events import (
    AttemptConflict,
    AttemptExecution,
    _attempt_payload,
    append_event,
    now_iso,
    read_cursor,
    read_events,
    undo_error,
)
from .files import (
    list_versions,
    path_is_within,
    published_versions,
    read_json,
    version_name,
    version_num,
    write_json,
)
from .registry import RegistryError, layer_generation, load_registry
from .schema import (
    BINARY_TYPES,
    CONTENT_TYPES,
    KEY_COOKIE,
    NO_KEY,
    SERVED_PATH,
)
from .service import (
    PageTransaction,
    claim_is_active,
    claim_records,
    claim_update_sources,
    page_claim,
    running_server,
    state_home,
    unacknowledged,
    wait_is_live,
)
from .structure import parse_structure, parse_version, version_review_mode
from .validation import (
    action_contract_error,
    event_record_error,
    held_comment_error,
    visual_anchor_error,
)


def other_leaves(page_dir: Path) -> list:
    """The machine's other live leaves, for the banner's panel: each page
    whose server is up, as a title, its handover URL, and the same presence
    facts the page ships about itself — so a row there and the banner above it
    are the one judgment reading the one shape.

    Candidates are the conventional pages/ home and every claim record, which
    is what finds a page served from a session's scratch directory. Released
    and dead claims stay useful here as provenance. Liveness is the held
    server.lock lease, the same answer `running_server` gives everything else,
    and the URL is the one in durable service state, key included. The title is the
    newest published version's — the version that page's own root URL answers
    with — read the way `transcript` reads it.

    The whole scan runs on every /api/state; what it reads of each neighbour is
    kept per file, so a poll costs the scan and the presence reads rather than a
    parse of every live neighbour's page (`parse_version`)."""
    candidates = []
    pages = state_home() / "pages"
    if pages.is_dir():
        candidates += (d for d in pages.iterdir() if d.is_dir())
    candidates += (Path(claim["page"]) for claim in claim_records())
    others = []
    seen = {page_dir.resolve()}
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        # A neighbour's fault stays its own. This is the one read of state some
        # other page owns: a directory deleted mid-scan (stale pages are deleted
        # and made again) or a log a disk fault corrupted would otherwise 500
        # every open page's poll on the machine, blaming the page that asked.
        try:
            info = running_server(candidate)
            if not info:
                continue
            events = read_events(candidate)
            published = published_versions(candidate, events)
            # A server up before its page's first publish serves nothing to link.
            if not published:
                continue
            parser = parse_version(candidate, published[-1])
            present = presence(candidate, events)
        except Exception:  # noqa: BLE001, S112 - whatever shape its fault takes
            continue
        others.append(
            {
                "title": parser.title.strip() or candidate.name,
                "url": info["url"],
                **present,
            }
        )
    return sorted(others, key=lambda entry: entry["title"].lower())


def presence(page_dir: Path, events: list) -> dict:
    """What a seat showing this page says about it: the agent's claim, everything
    the directory holds that can answer for it, and where that agent is working.
    One gatherer for every such seat — `full_state` spreads it into the page's own
    poll answer, and `other_leaves` attaches it to each entry — so the runtime's one
    claim-against-proof judgment reads the same fields whichever page it judges,
    and the tray's account of a neighbour is the account this page gives of
    itself."""
    # A file that isn't there stands in as its whole record, so every read below
    # indexes rather than asking twice whether the field arrived.
    stored_status = read_json(page_dir / "status.json") or {
        "state": "idle",
        "detail": "",
        "ts": None,
    }
    status = {key: value for key, value in stored_status.items() if key != "work"}
    claim = page_claim(page_dir)
    active = claim if claim_is_active(claim) else None
    # What the wait owner has acknowledged after the complete batch reached its
    # next durable consumer. An action past this seq has not reached that point,
    # which lets the runtime carry it forward onto versions written without it.
    cursor = read_cursor(page_dir)
    return {
        "status": status,
        "claims": claim_update_sources(stored_status, events),
        "listening": wait_is_live(page_dir, active),
        "cursor": cursor,
        # The reader's number, not the watcher's: their own messages the agent
        # hasn't taken in. Reports ride the same cursor but are the agent's debt,
        # so the banner never tells a reader that a worker's news is waiting on them.
        "pending": sum(
            1 for e in unacknowledged(events, cursor) if e["author"] == "user"
        ),
        "agent": claim.get("agent", "Claude") if claim else "Claude",
        # The claimant's host program, for behavior that keys on it — the display
        # name above is anyone's to choose, so nothing may dispatch on it.
        "host": claim.get("host") if claim else None,
        # None when nothing claimed the page — interact.py run outside an agent host.
        "session_alive": active is not None if claim else None,
        # Which session the turn-closed evidence belongs to. Thread updates carry
        # their posting session too, so a delegate is not declared abandoned merely
        # because the orchestrator's turn ended under it.
        "claim_session": claim.get("id") if claim else None,
        # When the claiming session's last turn ended, or None while none has.
        # A `working` claim older than this is one that no turn and no delegate
        # renewed across the boundary — the same judgment the runtime's grace
        # makes, available at the moment it becomes true instead of a quarter of
        # an hour after it. Read with .get like the rest of the claim's fields,
        # since a record written before this existed is still a valid claim.
        "turn_closed": claim.get("turn_closed") if claim else None,
        # When a browser last polled the page (the server bumps viewed.json,
        # throttled), or None for a page nobody has ever opened — which used to
        # be indistinguishable from one the user studied and left.
        "viewed": (read_json(page_dir / "viewed.json") or {"t": None})["t"],
        # Where the claimant is working (claim_page), for the tray's hover: what
        # tells one leaf from another is the work behind it, and neither the title
        # nor the page directory says which that is. It outlives the session that
        # wrote it, as every other fact in this record does — a page the tray
        # calls unheld came out of somewhere, and that is still where it came from.
        # None for a page nothing ever claimed, which is the honest nothing.
        "session_cwd": claim.get("cwd") if claim else None,
    }


def full_state(
    page_dir: Path,
    events: list,
    versions: list,
    layer: str | None = None,
) -> dict:
    return {
        "layer": layer or layer_generation(page_dir),
        # The clock every timestamp below was written by. A seat dating one reads
        # `Date.now()`, which is the reader's own machine: a laptop an hour out
        # calls a claim made this minute an hour stale, on every seat at once, and
        # neither side can tell from the timestamp alone. Sent so the reading is
        # against the writer's clock rather than the reader's.
        "now": now_iso(),
        "versions": versions,
        "data": read_data(page_dir),
        **presence(page_dir, events),
        # As logged: a message's text is Markdown the page's vendored runtime renders,
        # and its markup is the fragment the CLI gate validated. The wire adds nothing,
        # so the only vocabulary a page's frozen layer has to keep speaking is the
        # log's own, which $events already stamps.
        "events": events,
    }


class Handler(BaseHTTPRequestHandler):
    page_dir = None
    token = None
    event_attempts = None
    event_attempts_lock = None
    # Set by `authorized` when the key arrived in the query, cleared by the one
    # writer that spends it.
    set_cookie = False
    # The render gate previews a version before its `note` publishes it —
    # refusing the note is the gate's whole job. Set to that version's number,
    # the handler exposes on-disk versions up to it, previewed one included as
    # latest, so the runtime neither 404s the preview nor follows the published
    # latest away from it mid-check. None — every server a user reaches —
    # exposes noted versions only.
    preview_upto = None

    def versions_live(self, events):
        if self.preview_upto is None:
            return published_versions(self.page_dir, events)
        return [
            version
            for version in list_versions(self.page_dir)
            if version <= self.preview_upto
        ]

    def _page_state(self, events: list) -> dict:
        """The page's own state from a caller's transaction-consistent log."""
        state = full_state(
            self.page_dir,
            events,
            self.versions_live(events),
            layer=self.layer,
        )
        return state

    def page_state(self) -> dict:
        """The current reading used by GET and accepted POST responses.

        A claim's ``log_floor`` is meaningful only beside the same log snapshot it
        followed. Every response therefore keeps the page transaction through both
        files.
        """
        with PageTransaction(self.page_dir) as page:
            state = self._page_state(page.events)
        # Every URL in `others` carries the machine key (`host_key`), so the list
        # reaches neighbouring pages without creating another authorization path.
        # Scan neighbours after releasing this page's lease: they are independent
        # snapshots, and one slow neighbour must not block this page's writers.
        state["others"] = other_leaves(self.page_dir)
        return state

    def log_message(self, *args):
        pass

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
        if path.startswith(("/api/", "/versions/")) or path in {"/registry.json", "/"}:
            self.send_header("Leaf-Layer", self.layer)
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
            status, body = self.event_rejection(self.posted, error, status)
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

    def _get(self):
        path = urlsplit(self.path).path
        if path == "/":
            versions = self.versions_live(read_events(self.page_dir))
            if not versions:
                self._json({"error": "no published versions yet"}, 404)
                return
            version = versions[-1]
            source = (self.page_dir / "versions" / version_name(version)).read_text(
                encoding="utf-8"
            )
            # The live address serves one immutable version but does not become that
            # version's address. The marker tells the runtime exactly which file this
            # response projected; deriving it from the next state poll would race a
            # publish between the document response and that poll.
            parsed = parse_structure(source)
            scripts = [
                script
                for script in parsed.external_scripts
                if script["attrs"] == {"src": "/leaf.js", "type": "module"}
            ]
            if len(scripts) != 1:
                self._json({"error": "published version has no canonical script"}, 500)
                return
            line, column = scripts[0]["position"]
            # Match `_StructParser`, which counts only "\n"; splitlines() also treats
            # Unicode separators and form feeds as lines, shifting the marker.
            offset = sum(len(part) + 1 for part in source.split("\n")[: line - 1])
            offset += column
            marker = f'<meta name="lf-version" data-lf-runtime content="{version}">'
            projected = (source[:offset] + marker + source[offset:]).encode()
            self._send(200, "text/html; charset=utf-8", projected)
            return
        if path == "/api/state":
            # A poll is the one proof a browser holds the page open, and before
            # this nothing recorded it: a page nobody ever opened and one the
            # user studied and left looked identical from the agent's side.
            # Throttled — presence needs a recency, not a request log. Never
            # from a preview: the render gate's own browser is not the reader,
            # and its polls would leave no page "never opened" again.
            cls = type(self)
            if (
                self.preview_upto is None
                and time.time() - getattr(cls, "viewed_at", 0) > 30
            ):
                cls.viewed_at = time.time()
                write_json(self.page_dir / "viewed.json", {"t": cls.viewed_at})
            # Versions pass through the handler's own view, so a preview state
            # agrees with the version it serves.
            self._json(self.page_state())
            return
        # Browsers ask for this unprompted, and go on asking where nothing in the
        # markup names an icon — the runtime's link is written as the chrome is built,
        # which is after the parse. Answering "no content" rather than letting it fall
        # through to 404 keeps the console clean, which is what makes an empty console
        # worth asserting on (the browser render suite).
        if path == "/favicon.ico":
            self._send(204, "image/x-icon", b"")
            return
        if SERVED_PATH.fullmatch(path):
            if path.startswith("/versions/"):
                version = version_num(Path(path).name)
                if version not in self.versions_live(read_events(self.page_dir)):
                    self._json(
                        {
                            "error": "not published yet; run `leaf version publish` first"
                        },
                        404,
                    )
                    return
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
                return
        self._json({"error": "not found"}, 404)

    @staticmethod
    def event_rejection(event: dict, error: str, status: int = 400) -> tuple:
        """A final answer proving that this execution appended no event."""
        body = {"ok": False, "error": error, "final": True}
        if event.get("attempt"):
            body["attempt"] = event["attempt"]
        return status, body

    def accepted_state(self) -> tuple:
        return 200, {"ok": True, "state": self.page_state()}

    def coordinate_event(self, event: dict) -> tuple:
        """Run one copy of an attempt and share its outcome with concurrent copies."""
        attempt = event.get("attempt")
        if not attempt:
            return self.execute_event(event)
        payload = _attempt_payload(event)
        with self.event_attempts_lock:
            execution = self.event_attempts.get(attempt)
            if execution is None:
                execution = AttemptExecution(payload)
                self.event_attempts[attempt] = execution
                owner = True
            else:
                owner = False
                if execution.payload != payload:
                    return self.event_rejection(
                        event,
                        f"attempt {attempt!r} already belongs to another event",
                        409,
                    )
        if not owner:
            execution.done.wait()
            return execution.result
        try:
            result = self.execute_event(event)
        except Exception as error:  # noqa: BLE001 - every waiter needs an outcome
            # A fault may occur after append. Withholding `final` makes the next
            # identical request find the accepted event or execute the attempt again.
            result = (
                500,
                {
                    "ok": False,
                    "attempt": attempt,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
        finally:
            execution.result = result
            execution.done.set()
            # Waiters retain the execution object. Acceptance is durable in the log;
            # every other outcome must be evaluated again if it is posted later.
            with self.event_attempts_lock:
                if self.event_attempts.get(attempt) is execution:
                    del self.event_attempts[attempt]
        return result

    def execute_event(self, event: dict) -> tuple:
        """Validate mutable page state and append as one log transaction.

        `_post` checks the payload's declared shape before attempt coordination. A
        re-vendor can replace that declaration before this transaction is acquired,
        so an action's contract is deliberately read again inside the lease: this
        reading, not the admission reading, is the one allowed to append beside the
        page's current vocabulary.
        """
        kind = event["kind"]
        # Every decision whose validity depends on the log stays under the append
        # lock through the write. In particular, two tabs cannot both validate an
        # undo against the same standing target and append after either lock is gone.
        accepted = False
        with PageTransaction(self.page_dir) as page:
            # Acceptance outranks mutable state validation. A retry for an accepted
            # attempt asks for its state; it does not repeat the gesture.
            if "attempt" in event:
                event["author"] = "user"
                try:
                    existing = page.matching_attempt(event)
                except AttemptConflict as error:
                    return self.event_rejection(event, str(error), 409)
                if existing:
                    accepted = True
            if not accepted:
                events = page.events
                if "version" in event:
                    live_versions = self.versions_live(events)
                    if event["version"] not in live_versions:
                        return self.event_rejection(
                            event, f"{kind} version must be one of {live_versions}"
                        )
                if kind == "done":
                    mode = version_review_mode(self.page_dir, event["version"])
                    if mode != "sign-off":
                        return self.event_rejection(
                            event,
                            f"version {event['version']} does not declare "
                            '<meta name="lf-review" content="sign-off">, so it has no '
                            "approval to record",
                        )
                if kind == "action":
                    # This is not the static admission read in `_post`: re-vendoring and
                    # this transaction have now chosen an order, so only this registry
                    # can authorize an action that will be appended under the same lease.
                    try:
                        registry = load_registry(self.page_dir)
                    except RegistryError as error:
                        return self.event_rejection(event, str(error))
                    if registry is None:
                        return self.event_rejection(
                            event, "the page has no registry.json"
                        )
                    if error := action_contract_error(
                        self.page_dir,
                        event,
                        events,
                        registry,
                    ):
                        return self.event_rejection(event, error)
                anchor = event.get("anchor") or {}
                if kind == "comment" and (event.get("holds") or anchor.get("visual")):
                    try:
                        registry = load_registry(self.page_dir)
                    except RegistryError as error:
                        return self.event_rejection(event, str(error))
                    if registry is None:
                        return self.event_rejection(
                            event, "the page has no registry.json"
                        )
                    page_by_id = parse_version(self.page_dir, event["version"]).by_id
                    for error in (
                        held_comment_error(event, page_by_id, registry),
                        visual_anchor_error(event, page_by_id, registry),
                    ):
                        if error:
                            return self.event_rejection(event, error)
                if "parent" in event and event["parent"] not in {
                    e["id"] for e in events if e["kind"] in {"comment", "reply"}
                }:
                    return self.event_rejection(
                        event, f"unknown parent {event['parent']!r}"
                    )
                if kind == "undo" and (error := undo_error(event, events)):
                    return self.event_rejection(event, error)
                event["author"] = "page" if kind == "error" else "user"
                append_event(page, event)
        return self.accepted_state()

    def _post(self):
        if urlsplit(self.path).path != "/api/event":
            self._json({"error": "not found"}, 404)
            return
        # Preview requests have passed authentication and body preparation, so
        # their refusal can name the attempt without writing to the real log.
        if self.preview_upto is not None:
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
        event = self.posted
        try:
            registry = load_registry(self.page_dir)
        except RegistryError as error:
            self._refuse(str(error))
            return
        if registry is None:
            self._refuse("the page has no registry.json")
            return
        contracts = registry["$events"]["kinds"]
        browser_kinds = sorted(
            name for name, contract in contracts.items() if "browser" in contract
        )
        kind = event.get("kind")
        if not isinstance(kind, str) or kind not in browser_kinds:
            self._refuse(f"kind must be one of {browser_kinds}")
            return
        # The server owns the record envelope and agent identity. Removing client
        # copies before validation prevents them from entering attempt identity too.
        for field in ("id", "author", "agent", "session", "ts", "seq"):
            event.pop(field, None)
        if error := event_record_error(contracts[kind], event, browser=True):
            self._refuse(f"{kind} event is invalid: {error}")
            return
        status, answer = self.coordinate_event(event)
        self._json(answer, status)


def handler_for(
    page_dir: Path, token: str, preview_upto=None, protocol_version="HTTP/1.0"
):
    """A request handler bound to one page, publication view, and key. The key has no
    default: every server over a page directory is reachable by whatever reached the
    machine, so there is no construction that should quietly go without one."""
    return type(
        "PageHandler",
        (Handler,),
        {
            "page_dir": page_dir,
            "token": token,
            "preview_upto": preview_upto,
            "protocol_version": protocol_version,
            "event_attempts": {},
            "event_attempts_lock": threading.Lock(),
            "layer": layer_generation(page_dir),
        },
    )
