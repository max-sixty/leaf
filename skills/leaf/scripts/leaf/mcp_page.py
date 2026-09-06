"""Canonical Leaf pages delivered through one process-scoped MCP App origin."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from .event_endpoint import EventEndpoint
from .files import revision_path
from .hosting import server_at
from .http import Handler
from .registry.contract import RegistryError
from .registry.storage import layer_metadata
from .schema import EVENTS_FILE, MCP_APP
from .served_state.service import PageStateService
from .server import preview_metadata, running_server
from .structure import parse_structure

PAGE_RESOURCE_URI = "ui://leaf/page/v1.html"
PAGE_APP_RESOURCE = MCP_APP / "page-app.html"
PAGE_FORMAT = "leaf.page/v1"
_READY_PATH = "/mcp-ready.js"
_READY_SCRIPT = (
    b"if(window.parent!==window){const ready=()=>{if(document.body?.dataset."
    b'lfPresented!=="1")return false;window.parent.postMessage({type:'
    b'"leaf:mcp-page-ready"},"*");return true};if(!ready()){const observer='
    b"new MutationObserver(()=>{if(ready())observer.disconnect()});observer.observe("
    b"document.documentElement,{attributes:true,subtree:true,attributeFilter:"
    b'["data-lf-presented"]})}}\n'
)


def _with_ready_signal(body: bytes, page_root: str) -> bytes:
    """Let the parent App distinguish a loaded page from a browser error document."""
    closing = body.lower().rfind(b"</body>")
    if closing < 0:
        return body
    source = f"{page_root}{_READY_PATH}"
    script = f'<script type="module" src="{source}" data-lf-runtime></script>'.encode()
    return body[:closing] + script + body[closing:]


@dataclass
class _PageSession:
    page_dir: Path
    capability: str
    endpoint: EventEndpoint
    layer_identity: dict
    bootstrap: str
    preview: dict | None


class _RoutedPageHandler(Handler):
    """Select a page from an unguessable path before entering the HTTP boundary."""

    router: ProcessPageServer
    protocol_version = "HTTP/1.1"
    layer = ""
    # This transport exists to sit in a cross-origin MCP App frame. The host approves
    # the exact process origin, while the unguessable, process-lived path authorizes
    # the page; the server cannot name the host-assigned parent origin in a response.
    frame_ancestors_policy = None

    def authorized(self) -> bool:
        # `_select_page` already proved possession of the process-scoped capability.
        return True

    def _select_page(self) -> bool:
        external = urlsplit(self.path)
        parts = external.path.split("/", 3)
        if len(parts) < 3 or parts[1] != "p" or not parts[2]:
            return False
        session = self.router.session(parts[2])
        if session is None:
            return False
        inside = f"/{parts[3]}" if len(parts) == 4 and parts[3] else "/"
        self.page_dir = session.page_dir
        self.event_endpoint = session.endpoint
        self.layer = session.layer_identity["generation"]
        self.layer_identity = session.layer_identity
        self.bootstrap = session.bootstrap
        self.preview = session.preview
        self.page_root = f"/p/{session.capability}"
        self.path = inside + (f"?{external.query}" if external.query else "")
        return True

    def _unknown_capability(self) -> None:
        # A POST body has not been consumed yet, so this HTTP/1.1 connection cannot
        # safely be reused after the refusal.
        if self.command == "POST":
            self.close_connection = True
        self._json({"error": "not found"}, 404)

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        if status == 200 and ctype.startswith("text/html"):
            body = _with_ready_signal(body, self.page_root)
        super()._send(status, ctype, body)

    def _get(self):
        if urlsplit(self.path).path == _READY_PATH:
            self._send(200, "text/javascript; charset=utf-8", _READY_SCRIPT)
            return
        super()._get()

    def _select_or_answer(self) -> bool | None:
        """Select a page, answering route faults before the shared handler exists."""
        try:
            return self._select_page()
        except Exception as error:  # noqa: BLE001 - this is the outer route boundary
            if self.command == "POST":
                self.close_connection = True
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass
            return None

    def do_GET(self):
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._unknown_capability()
            return
        super().do_GET()

    def do_POST(self):
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._unknown_capability()
            return
        super().do_POST()


class ProcessPageServer:
    """Serve every page opened by one MCP process from one exact local origin.

    The HTTP server is transport plumbing only. Each page remains a directory plus
    append-only log, while its random path is a bearer capability that expires with
    this process and is never written into the page.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_capability: dict[str, _PageSession] = {}
        self._by_page: dict[Path, _PageSession] = {}
        handler = type("MCPPageHandler", (_RoutedPageHandler,), {"router": self})
        self._httpd = server_at("127.0.0.1", 0, handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self._closed = False

    @property
    def origin(self) -> str:
        return f"http://localhost:{self._httpd.server_address[1]}"

    def open(self, page_dir: Path) -> str:
        page_dir = page_dir.resolve()
        with self._lock:
            session = self._by_page.get(page_dir)
            if session is None:
                capability = secrets.token_urlsafe(24)
                identity = layer_metadata(page_dir)
                session = _PageSession(
                    page_dir=page_dir,
                    capability=capability,
                    endpoint=EventEndpoint(page_dir),
                    layer_identity=identity,
                    bootstrap=(page_dir / "runtime" / "bootstrap.js").read_text(
                        encoding="utf-8"
                    ),
                    preview=preview_metadata(page_dir),
                )
                self._by_page[page_dir] = session
                self._by_capability[capability] = session
            return f"{self.origin}/p/{session.capability}/"

    def session(self, capability: str) -> _PageSession | None:
        with self._lock:
            session = self._by_capability.get(capability)
            if session is None:
                return None
            current_identity = layer_metadata(session.page_dir)
            if current_identity != session.layer_identity:
                session.layer_identity = current_identity
                session.bootstrap = (
                    session.page_dir / "runtime" / "bootstrap.js"
                ).read_text(encoding="utf-8")
                session.endpoint = EventEndpoint(session.page_dir)
            return session

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._by_capability.clear()
            self._by_page.clear()
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2)


def resolve_page(page: str | Path) -> Path:
    """Resolve one initialized page without letting presentation mint its log."""
    page_dir = Path(page).expanduser().resolve()
    if not (page_dir / EVENTS_FILE).is_file():
        raise ToolError(
            f"{page_dir} is not an initialized Leaf page; run `leaf page init` first"
        )
    return page_dir


def unpresentable_layer_error(page_dir: Path, detail: str) -> ToolError:
    """Explain a page layer that the MCP presentation boundary cannot read."""
    message = (
        f"{page_dir} cannot be presented with its vendored layer: {detail.rstrip('.')}"
    )
    if "leaf page init" not in detail:
        message += f". Run `leaf page init {page_dir}` to re-vendor the page"
    return ToolError(f"{message}.")


def require_active_revision(page_dir: Path, state: dict) -> dict:
    """Return the active revision or explain the source the page still needs."""
    active = state.get("active")
    if active is None:
        raise ToolError(
            f"{page_dir} has no active revision; write a valid index.html first"
        )
    return active


def page_state(page: str | Path, pages: ProcessPageServer) -> tuple[dict, dict]:
    """Return a model-sized summary and the app-private canonical page address."""
    page_dir = resolve_page(page)
    try:
        state = PageStateService(
            page_dir,
            layer_identity=layer_metadata(page_dir),
            preview=preview_metadata(page_dir),
        ).page_state()
    except RegistryError as error:
        raise unpresentable_layer_error(page_dir, str(error)) from error
    active = require_active_revision(page_dir, state)
    if state["browser"] is None:
        detail = state["source_error"] or "the page registry cannot be projected"
        raise unpresentable_layer_error(page_dir, detail)
    server = running_server(page_dir) or {}
    source = revision_path(page_dir, active["revision"]).read_text(encoding="utf-8")
    title = parse_structure(source).title.strip() or page_dir.name
    summary = {
        "format": PAGE_FORMAT,
        "mode": "page",
        "page": str(page_dir),
        "title": title,
        "active": active,
        "event_seq": state["browser"]["basis"]["through_seq"],
        "source_error": state["source_error"],
    }
    try:
        inline_url = pages.open(page_dir)
    except RegistryError as error:
        raise unpresentable_layer_error(page_dir, str(error)) from error
    private = {
        **summary,
        "inline_url": inline_url,
        "browser_url": server.get("url"),
        "message": (
            "Opening the last valid revision; the current authored source is invalid."
            if summary["source_error"]
            else "Opening the complete Leaf page."
        ),
    }
    return summary, private


def page_result(page: str | Path, pages: ProcessPageServer) -> CallToolResult:
    summary, private = page_state(page, pages)
    text = (
        f"Leaf page {summary['title']!r} is ready at "
        f"{summary['active']['label']}. The page directory and append-only event "
        "log remain authoritative."
    )
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=summary,
        _meta={"leaf": private},
    )
