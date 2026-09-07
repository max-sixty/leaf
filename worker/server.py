"""Serve leaf.page through Leaf's canonical HTTP handler.

The Cloudflare Worker selects one container filesystem per browser session. This
adapter selects the product or example page directory behind a clean public route,
then hands the request to the same Handler and EventEndpoint as a locally served Leaf.
Agent input comes from Leaf's shared projections; this adapter owns no parallel state
store or event semantics.
"""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from leaf.conversation import cmd_reply
from leaf.document_reading import read_document
from leaf.event_endpoint import EventEndpoint
from leaf.events import build_threads, spoken_turns
from leaf.files import latest_revision, revision_path
from leaf.hosting import server_at
from leaf.http import Handler, canonical_script_offset
from leaf.passages import enclosing_of
from leaf.projection import page_projection
from leaf.registry.storage import layer_metadata, require_registry
from leaf.revisioning import activate_source
from leaf.server import preview_metadata
from leaf.service import PageTransaction
from leaf.thread_context import thread_roots

PORT = 8080
WEBSITE_AGENT = "Leaf guide"
WEBSITE_AGENT_SESSION = "leaf-website-agent"
PUBLICATION = {
    "agent": WEBSITE_AGENT,
    "install_url": "/#install",
}
EXAMPLE_ROUTE = re.compile(r"^/examples/(?P<slug>[a-z0-9-]+)(?P<inside>/.*)?$")
PRODUCT_ROUTES = {
    "/": "index",
    "/examples": "examples",
    "/how-it-works": "how-it-works",
    "/packages": "packages",
    "/registry": "registry",
}
PAGE_RESOURCE = re.compile(
    r"^/(?:api|guidance|media|revisions|runtime|vendor|versions|widgets)(?:/|$)"
    r"|^/(?:icon\.svg|leaf\.js|registry\.json|theme\.css)$"
)
AGENT_EVENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
AGENT_TURN_PATH = "/_leaf/agent/turn"
AGENT_REPLY_PATH = "/_leaf/agent/reply"


@cache
def page_binding(page_dir: Path) -> tuple[EventEndpoint, dict, str, dict | None]:
    """Read immutable delivery metadata once per published page and process."""
    return (
        EventEndpoint(page_dir),
        layer_metadata(page_dir),
        (page_dir / "runtime" / "bootstrap.js").read_text(encoding="utf-8"),
        preview_metadata(page_dir),
    )


def with_sitenote(document: bytes, page_root: str) -> bytes:
    """Insert website chrome at the canonical runtime boundary."""
    source = document.decode()
    offset = canonical_script_offset(source, page_root)
    site_script = (
        f'<script type="module" src="{page_root}/sitenote.js" data-lf-site></script>'
    )
    return (source[:offset] + site_script + source[offset:]).encode()


def agent_attempt(event_id: str) -> str:
    """The durable reply attempt owned by one reader message."""
    return f"website-agent-{event_id}"


def _message_reading(message: dict) -> dict:
    reading = {
        "id": message["id"],
        "speaker": message.get("agent", "agent")
        if message["author"] == "claude"
        else "reader",
    }
    for field in ("text", "token", "markup"):
        if field in message:
            reading[field] = message[field]
    if "drawing" in message:
        reading["drawing"] = "attached"
    return reading


def agent_turn(page_dir: Path, event_id: str) -> dict | None:
    """Read one still-pending reader turn from Leaf's canonical page state."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        if activation.error:
            raise ValueError(activation.error)
        events = page.events
        if any(event.get("attempt") == agent_attempt(event_id) for event in events):
            return None

        target = next((event for event in events if event["id"] == event_id), None)
        if target is None or target["kind"] not in {"comment", "reply"}:
            return None
        root_id = thread_roots(events).get(event_id)
        if root_id is None:
            return None

        revision = latest_revision(page_dir)
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        registry = require_registry(page_dir)
        prepared = page_projection(html, events, registry, revision)
        threads = build_threads(events, enclosing_of(prepared[2]))
        thread = threads.get(root_id)
        turns = spoken_turns(thread) if thread else []
        if (
            not thread
            or thread["resolved"]
            or not turns
            or turns[-1]["author"] != "user"
            or turns[-1]["id"] != event_id
            or (thread["root"].get("response") or {}).get("kind") == "version"
        ):
            return None

        document = read_document(
            html,
            events,
            registry,
            revision,
            threads,
            prepared=prepared,
        )
        decisions = [
            {
                "widget": coordinate[0],
                "unit": coordinate[1],
                "facet": coordinate[2],
                "action": source["action"],
                "detail": source["detail"],
            }
            for coordinate, (source, _spec) in sorted(
                document.projection.actions.items()
            )
        ]
        return {
            "page": {
                "title": document.parser.title.strip(),
                "visible_text": document.passages.text,
                "displayed_data": document.passages.shown,
                "authored_html": html,
                "standing_decisions": decisions,
            },
            "conversation": {
                "anchor": thread["anchor"],
                "messages": [_message_reading(message) for message in thread["msgs"]],
            },
            "reply_to": event_id,
        }


def _agent_event(posted: dict, *, with_text: bool) -> tuple[str, str | None]:
    expected = {"event", "text"} if with_text else {"event"}
    if set(posted) != expected:
        raise ValueError(f"agent request fields must be {sorted(expected)}")
    event_id = posted["event"]
    if not isinstance(event_id, str) or not AGENT_EVENT_ID.fullmatch(event_id):
        raise ValueError("agent event must be a Leaf event id")
    if not with_text:
        return event_id, None
    text = posted["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("agent reply text must be non-empty")
    return event_id, text


def published_page(site_root: Path, path: str) -> tuple[Path, str, str, str] | None:
    """Resolve a public URL to its independent page directory and inside route."""
    if path in {"/", ""} or path.startswith("/_leaf/agent/"):
        inside = "/" if path in {"/", ""} else path
        return site_root / "_leaf" / "pages" / "index", "", inside, "product"

    for route, name in PRODUCT_ROUTES.items():
        if route in {"/", "/examples"}:
            continue
        if path in {route, f"{route}/"}:
            return site_root / "_leaf" / "pages" / name, route, "/", "product"
        if path.startswith(f"{route}/"):
            return (
                site_root / "_leaf" / "pages" / name,
                route,
                path[len(route) :],
                "product",
            )

    if path in {"/examples", "/examples/"}:
        return (
            site_root / "_leaf" / "pages" / "examples",
            "/examples",
            "/",
            "product",
        )
    if path.startswith("/examples/"):
        inside_catalog = path[len("/examples") :]
        if PAGE_RESOURCE.match(inside_catalog) or inside_catalog.startswith(
            "/_leaf/agent/"
        ):
            return (
                site_root / "_leaf" / "pages" / "examples",
                "/examples",
                inside_catalog,
                "product",
            )
        match = EXAMPLE_ROUTE.fullmatch(path)
        if match is not None:
            slug = match.group("slug")
            return (
                site_root / "examples" / slug,
                f"/examples/{slug}",
                match.group("inside") or "/",
                "example",
            )

    if PAGE_RESOURCE.match(path):
        return site_root / "_leaf" / "pages" / "index", "", path, "product"
    return None


class WebsitePageHandler(Handler):
    """Bind every clean website route to one initialized page directory."""

    site_root: Path
    sitenote: bytes
    protocol_version = "HTTP/1.1"
    layer = ""

    def authorized(self) -> bool:
        # The outer Worker has already selected this browser's isolated container.
        return True

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        if (
            status == 200
            and ctype.startswith("text/html")
            and self.publication
            and self.publication["kind"] == "example"
        ):
            body = with_sitenote(body, self.page_root)
        super()._send(status, ctype, body)

    def _get(self) -> None:
        if urlsplit(self.path).path == "/sitenote.js":
            self._send(200, "text/javascript; charset=utf-8", self.sitenote)
            return
        super()._get()

    def _post(self) -> None:
        path = urlsplit(self.path).path
        if path not in {AGENT_TURN_PATH, AGENT_REPLY_PATH}:
            super()._post()
            return
        if self.posted_error:
            self._json({"error": self.posted_error}, 400)
            return
        try:
            event_id, text = _agent_event(
                self.posted, with_text=path == AGENT_REPLY_PATH
            )
        except ValueError as error:
            self._json({"error": str(error)}, 400)
            return
        if path == AGENT_TURN_PATH:
            turn = agent_turn(self.page_dir, event_id)
            if turn is None:
                self._json({"status": "settled"})
                return
            self._json({"status": "ready", "turn": turn})
            return

        try:
            accepted = cmd_reply(
                self.page_dir,
                event_id,
                text,
                "",
                attempt=agent_attempt(event_id),
                only_if_pending=True,
            )
        except SystemExit as error:
            self._json({"error": str(error)}, 400)
            return
        if accepted is None:
            self._json({"status": "settled"})
            return
        self._json({"status": "appended", "event": accepted["id"]})

    def _select_page(self) -> bool:
        external = urlsplit(self.path)
        selected = published_page(self.site_root, external.path)
        if selected is None:
            return False
        page_dir, page_root, inside, kind = selected
        if not (page_dir / "events.jsonl").is_file():
            return False

        endpoint, identity, bootstrap, preview = page_binding(page_dir)
        self.page_dir = page_dir
        self.event_endpoint = endpoint
        self.layer = identity["generation"]
        self.layer_identity = identity
        self.bootstrap = bootstrap
        self.preview = preview
        self.publication = {**PUBLICATION, "kind": kind}
        self.page_root = page_root
        self.path = inside + (f"?{external.query}" if external.query else "")
        return True

    def _not_found(self) -> None:
        # An unread POST body makes an HTTP/1.1 connection unsafe to reuse.
        if self.command == "POST":
            self.close_connection = True
        self._json({"error": "not found"}, 404)

    def _select_or_answer(self) -> bool | None:
        try:
            return self._select_page()
        except Exception as error:  # noqa: BLE001 - outer HTTP route boundary
            if self.command == "POST":
                self.close_connection = True
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass
            return None

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok\n")
            return
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._not_found()
            return
        super().do_GET()

    def do_POST(self) -> None:
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._not_found()
            return
        super().do_POST()


def handler_for(site_root: Path) -> type[WebsitePageHandler]:
    """Make one process handler over every page directory in a site build."""
    root = site_root.resolve()
    return type(
        "PublishedPageHandler",
        (WebsitePageHandler,),
        {
            "site_root": root,
            "sitenote": (root / "sitenote.js").read_bytes(),
        },
    )


def main() -> None:
    os.environ.setdefault("LEAF_AGENT", WEBSITE_AGENT)
    os.environ.setdefault("LEAF_SESSION_ID", WEBSITE_AGENT_SESSION)
    site_root = Path(os.environ.get("LEAF_SITE_ROOT", "/app/site"))
    httpd = server_at("0.0.0.0", PORT, handler_for(site_root))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
