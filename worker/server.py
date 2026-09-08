"""Serve leaf.page through Leaf's canonical HTTP handler.

The Cloudflare Worker selects one container filesystem per browser session. This
adapter selects the product or example page directory behind a clean public route,
then hands the request to the same Handler and event admission as a locally served Leaf.
Agent input comes from Leaf's shared projections; this adapter owns no parallel state
store or event semantics.
"""

from __future__ import annotations

import json
import os
import re
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from leaf.conversation import cmd_reply
from leaf.document_reading import read_document
from leaf.events import build_threads, spoken_turns
from leaf.files import latest_revision, revision_path
from leaf.hosting import server_at
from leaf.http import Handler, canonical_script_offset, scope_page_urls
from leaf.projection import page_reading
from leaf.registry.storage import layer_metadata, require_registry
from leaf.revisioning import activate_source
from leaf.served_state.service import PageStateService
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
SITE_MANIFEST = "_leaf/site.json"
PAGE_RESOURCE = re.compile(
    r"^/(?:api|guidance|media|revisions|runtime|vendor|versions|widgets)(?:/|$)"
    r"|^/(?:icon\.svg|leaf\.js|registry\.json|sitenote\.js|theme\.css)$"
)
AGENT_EVENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
AGENT_TURN_PATH = "/_leaf/agent/turn"
AGENT_REPLY_PATH = "/_leaf/agent/reply"


@cache
def page_binding(page_dir: Path) -> tuple[dict, str, dict | None]:
    """Read immutable delivery metadata once per published page and process."""
    return (
        layer_metadata(page_dir),
        (page_dir / "runtime" / "bootstrap.js").read_text(encoding="utf-8"),
        preview_metadata(page_dir),
    )


def with_sitenote(
    document: bytes, page_root: str, *, asset_root: str | None = None
) -> bytes:
    """Insert website chrome at the canonical runtime boundary."""
    source = document.decode()
    assets = asset_root if asset_root is not None else page_root
    offset = canonical_script_offset(source, assets)
    site_script = (
        f'<script type="module" src="{assets}/sitenote.js" data-lf-site></script>'
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
        prepared = page_reading(html, events, registry, revision)
        threads = build_threads(events, prepared.within)
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

        document = read_document(prepared, threads)
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


def published_page(
    site_root: Path, pages: dict, path: str
) -> tuple[Path, str, str, str] | None:
    """Resolve a public URL through the build's generated page manifest."""
    for public_root, page in sorted(
        pages.items(), key=lambda item: len(item[0]), reverse=True
    ):
        page_root = "" if public_root == "/" else public_root
        if path in {page_root, f"{page_root}/"}:
            inside = "/"
        elif path.startswith(f"{page_root}/"):
            inside = path[len(page_root) :]
            if not (PAGE_RESOURCE.match(inside) or inside.startswith("/_leaf/agent/")):
                continue
        else:
            continue
        directory = page.get("directory")
        kind = page.get("kind")
        if not isinstance(directory, str) or kind not in {"product", "example"}:
            raise ValueError(f"invalid site manifest entry for {public_root}")
        page_dir = (site_root / directory).resolve()
        if not page_dir.is_relative_to(site_root):
            raise ValueError(f"site manifest path escapes its root: {directory}")
        return page_dir, page_root, inside, kind
    return None


class WebsitePageHandler(Handler):
    """Bind every clean website route to one initialized page directory."""

    site_root: Path
    pages: dict
    sitenote: bytes
    protocol_version = "HTTP/1.1"
    layer = ""

    def page_state(self, view_revision: int | None = None) -> dict:
        state = super().page_state(view_revision)
        state["release"] = self.release
        return state

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

    def _select_page(self) -> bool | None:
        external = urlsplit(self.path)
        if self.command == "GET" and external.path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok\n")
            return None
        selected = published_page(self.site_root, self.pages, external.path)
        if selected is None:
            return False
        page_dir, page_root, inside, kind = selected
        if not (page_dir / "events.jsonl").is_file():
            return False

        identity, bootstrap, preview = page_binding(page_dir)
        self.page_dir = page_dir
        self.layer = identity["generation"]
        self.layer_identity = identity
        self.bootstrap = bootstrap
        self.preview = preview
        self.publication = {**PUBLICATION, "kind": kind}
        self.page_root = page_root
        self.path = inside + (f"?{external.query}" if external.query else "")
        return True


def handler_for(site_root: Path) -> type[WebsitePageHandler]:
    """Make one process handler over every page directory in a site build."""
    root = site_root.resolve()
    manifest = json.loads((root / SITE_MANIFEST).read_text(encoding="utf-8"))
    return type(
        "PublishedPageHandler",
        (WebsitePageHandler,),
        {
            "site_root": root,
            "pages": manifest["pages"],
            "sitenote": (root / "sitenote.js").read_bytes(),
            "release": manifest["release"],
        },
    )


def initial_state(
    page_dir: Path,
    page_root: str,
    kind: str,
    release: str,
    view_revision: int | None = None,
) -> dict:
    """Build the canonical state shared by readers before any private mutation."""
    state = PageStateService(
        page_dir,
        layer_identity=layer_metadata(page_dir),
        preview=preview_metadata(page_dir),
        publication={**PUBLICATION, "kind": kind},
    ).page_state(view_revision)
    state["release"] = release
    return scope_page_urls(state, page_root)


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
