"""MCP Apps delivery over Leaf's ordinary page and event authorities.

The full-page app frames the ordinary browser interface from a process-scoped
loopback server. The compact view remains a projection for hosts or moments
where the full document is unnecessary. Neither path owns document or event
state: both read the page directory and append through Leaf's event boundary.
"""

from __future__ import annotations

import atexit
import secrets
import threading
from pathlib import Path
from typing import Any, Callable

from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .agent_state import read_page_state
from .decisions import local_decision_entry, quoted_in
from .event_endpoint import EventEndpoint
from .hosting import server_at
from .http import handler_for
from .passages import collapse, spoken
from .registry.storage import require_registry
from .revisioning import activate_source
from .schema import ASSETS
from .server import page_url
from .service import PageTransaction
from .structure import parse_revision

PAGE_RESOURCE_URI = "ui://leaf/page.html"
PAGE_APP_RESOURCE = ASSETS / "vendor" / "mcp-page-app.html"
PAGE_FORMAT = "leaf.page/v1"
COMPACT_RESOURCE_URI = "ui://leaf/compact-ask.html"
COMPACT_APP_RESOURCE = ASSETS / "vendor" / "mcp-compact-app.html"
COMPACT_FORMAT = "leaf.compact-ask/v1"


class PageServerPool:
    """Own ephemeral loopback servers for this MCP process.

    These servers are delivery plumbing rather than page state. They write no
    service record and disappear with the MCP process; the document directory
    and append-only log outlive them.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._servers: dict[Path, tuple[Any, threading.Thread, str]] = {}

    def open(self, page_dir: Path) -> str:
        with self._lock:
            existing = self._servers.get(page_dir)
            if existing is not None:
                return existing[2]
            # The app result has to carry this URL through the host to its iframe.
            # Scope that exposed credential to this page server and MCP process,
            # rather than disclosing Leaf's durable machine-wide host key.
            token = secrets.token_urlsafe(16)
            httpd = server_at(
                "127.0.0.1",
                0,
                handler_for(
                    page_dir,
                    token,
                    protocol_version="HTTP/1.1",
                    cookie_attributes="SameSite=None; Secure; Partitioned",
                ),
            )
            httpd.daemon_threads = True
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            url = page_url("localhost", httpd.server_address[1], token)
            self._servers[page_dir] = (httpd, thread, url)
            return url

    def close(self) -> None:
        with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()
        for httpd, thread, _url in servers:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


def resolve_page(page: str | Path) -> Path:
    """Resolve one initialized page without letting a tool mint its log."""
    page_dir = Path(page).expanduser().resolve()
    if not (page_dir / "comments.jsonl").is_file():
        raise ToolError(
            f"{page_dir} is not an initialized Leaf page; run `leaf page init` first"
        )
    return page_dir


def _inside(record: dict, region: dict) -> bool:
    holder = record.get("holder")
    while holder:
        if holder is region:
            return True
        holder = holder.get("holder")
    return False


def _source_for(region: dict, records: list[dict], registry: dict) -> dict | None:
    candidates = [
        record
        for record in records
        if local_decision_entry(registry.get(record["tag"], {}))
        and not quoted_in(record, registry)
        and _inside(record, region)
    ]
    return candidates[0] if len(candidates) == 1 else None


def _fallback(base: dict, code: str, message: str) -> dict:
    return {**base, "mode": "fallback", "reason": code, "message": message, "ask": None}


def compact_state(
    page_dir: Path, events: list, source_error: str | None = None
) -> dict[str, Any]:
    """Project at most one current single-choice options ask.

    This deliberately covers one shape. A page with several asks, a thread ask,
    a multiple choice, or another vocabulary keeps its canonical full-page
    behavior and receives an honest fallback here.
    """
    state = read_page_state(page_dir, events, source_error)
    server = state.get("server")
    base = {
        "format": COMPACT_FORMAT,
        "page": str(page_dir),
        "title": state["title"],
        "event_seq": state["event_seq"],
        "active": state["active"],
        "source_error": state["source"]["error"],
        "full_page_url": server.get("url") if server else None,
    }
    if base["source_error"]:
        return _fallback(
            base,
            "source-invalid",
            "The authored source did not validate, so compact mode is holding the last good revision.",
        )
    decisions = state["decisions"]
    if not decisions:
        return {
            **base,
            "mode": "empty",
            "reason": "no-open-ask",
            "message": "This page has no open ask.",
            "ask": None,
        }
    if len(decisions) != 1:
        return _fallback(
            base,
            "several-open-asks",
            f"This page has {len(decisions)} open asks; use the full page to keep their context together.",
        )
    decision = decisions[0]
    if decision.get("thread"):
        return _fallback(
            base,
            "thread-ask",
            "This ask belongs to a conversation thread; continue it on the full page.",
        )
    if not state["active"]:
        return _fallback(
            base, "no-active-revision", "This page has no active revision."
        )

    revision = state["active"]["revision"]
    parser = parse_revision(page_dir, revision)
    registry = require_registry(page_dir)
    region = parser.by_id.get(decision["id"])
    if region is None:
        return _fallback(
            base,
            "unresolved-surface",
            "The current ask has no address in the active revision.",
        )
    source = _source_for(region, parser.lf_elements, registry)
    if source is None or source["tag"] != "lf-options":
        return _fallback(
            base,
            "unsupported-ask",
            "This compact surface currently supports a single-choice options ask only.",
        )
    attrs = source["attrs"]
    if not attrs.get("id") or "choose" not in attrs or "multiple" in attrs:
        return _fallback(
            base,
            "unsupported-options",
            "This compact surface currently supports a single-choice options ask only.",
        )
    if source.get("parent") != region["tag"]:
        return _fallback(
            base,
            "nested-options",
            "This compact surface requires the options widget directly inside its decision.",
        )

    html = (page_dir / state["active"]["file"]).read_text(encoding="utf-8")
    said = spoken(html, registry)
    options = [
        record
        for record in parser.lf_elements
        if record["tag"] == "lf-option"
        and record.get("holder") is source
        and record["attrs"].get("id")
    ]
    if not options:
        return _fallback(
            base,
            "empty-options",
            "The current options ask has no addressable choices.",
        )
    headings = [
        child
        for child in region.get("direct_text", [])
        if child["tag"] in {f"h{n}" for n in range(1, 7)}
    ]
    heading = headings[0] if len(headings) == 1 else None
    question = collapse(heading["text"]) if heading else ""
    if not question:
        return _fallback(
            base,
            "untitled-ask",
            "The current ask has no readable title.",
        )
    context = collapse(
        " ".join(
            child["text"]
            for child in region.get("direct_text", [])
            if child is not heading and child["tag"] != source["tag"]
        )
    )
    return {
        **base,
        "mode": "ask",
        "reason": None,
        "message": "Choose one option.",
        "ask": {
            "surface": region["attrs"]["id"],
            "source": attrs["id"],
            "question": question,
            "context": context,
            "options": [
                {
                    "id": record["attrs"]["id"],
                    "label": next(
                        (
                            collapse(child["text"])
                            for child in record.get("direct_text", [])
                            if child["tag"] == "strong" and collapse(child["text"])
                        ),
                        said[record["attrs"]["id"]].words,
                    ),
                    "summary": said[record["attrs"]["id"]].words,
                }
                for record in options
            ],
            "submit": {
                "kind": "action",
                "revision": revision,
                "widget": attrs["id"],
                "action": "choose",
            },
        },
    }


def current_compact_state(page_dir: Path) -> dict[str, Any]:
    """Read and, if valid source changed, activate one transaction-consistent view."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        return compact_state(page_dir, page.events, activation.error)


def current_page_state(
    page_dir: Path, page_url_for: Callable[[Path], str]
) -> dict[str, Any]:
    """Activate the source, then address its ordinary browser interface."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        state = read_page_state(page_dir, page.events, activation.error)
    active = state["active"]
    if not active:
        return {
            "format": PAGE_FORMAT,
            "mode": "fallback",
            "page": str(page_dir),
            "title": state["title"],
            "event_seq": state["event_seq"],
            "active": None,
            "source_error": state["source"]["error"],
            "url": None,
            "message": "This page has no valid revision to display.",
        }
    source_error = state["source"]["error"]
    return {
        "format": PAGE_FORMAT,
        "mode": "page",
        "page": str(page_dir),
        "title": state["title"],
        "event_seq": state["event_seq"],
        "active": active,
        "source_error": source_error,
        "url": page_url_for(page_dir),
        "message": (
            "Opening the last valid revision; the current authored source is invalid."
            if source_error
            else "Opening the complete Leaf page."
        ),
    }


def _result(text: str, payload: dict[str, Any]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=text)], structured_content=payload
    )


def _compact_summary(state: dict[str, Any]) -> str:
    ask = state.get("ask")
    if not ask:
        return f"{state['title'] or 'Leaf page'}: {state['message']}"
    choices = "; ".join(option["label"] for option in ask["options"])
    return f"{state['title'] or 'Leaf page'}: {ask['question']} Options: {choices}"


def _page_summary(state: dict[str, Any]) -> str:
    return f"{state['title'] or 'Leaf page'}: {state['message']}"


def create_server(
    compact_html: str | None = None,
    page_html: str | None = None,
    page_url_for: Callable[[Path], str] | None = None,
) -> MCPServer:
    """Create the stdio server; every tool call names its durable page."""
    apps = Apps()
    endpoints: dict[Path, EventEndpoint] = {}
    pool = None
    if page_url_for is None:
        pool = PageServerPool()
        page_url_for = pool.open
        atexit.register(pool.close)

    def endpoint(page_dir: Path) -> EventEndpoint:
        return endpoints.setdefault(page_dir, EventEndpoint(page_dir))

    @apps.tool(
        resource_uri=PAGE_RESOURCE_URI,
        visibility=["model"],
        name="leaf_open_page",
        title="Open a Leaf page",
        description=(
            "Open the complete browser interface for one initialized Leaf page "
            "inside the conversation."
        ),
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
    )
    def leaf_open_page(page: str) -> CallToolResult:
        state = current_page_state(resolve_page(page), page_url_for)
        return _result(_page_summary(state), {"ok": True, "state": state})

    @apps.tool(
        resource_uri=PAGE_RESOURCE_URI,
        visibility=["app"],
        name="leaf_read_page",
        description="Refresh the complete interface for an initialized Leaf page.",
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
    )
    def leaf_read_page(page: str) -> CallToolResult:
        state = current_page_state(resolve_page(page), page_url_for)
        return _result(_page_summary(state), {"ok": True, "state": state})

    @apps.tool(
        resource_uri=COMPACT_RESOURCE_URI,
        visibility=["model"],
        name="leaf_open_compact_ask",
        title="Open a compact Leaf ask",
        description=(
            "Open one initialized Leaf page as a compact inline ask when a small "
            "single-choice surface is preferable to the complete page."
        ),
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
    )
    def leaf_open_compact_ask(page: str) -> CallToolResult:
        state = current_compact_state(resolve_page(page))
        return _result(_compact_summary(state), {"ok": True, "state": state})

    @apps.tool(
        resource_uri=COMPACT_RESOURCE_URI,
        visibility=["app"],
        name="leaf_read_compact_ask",
        description="Read the current compact projection of an initialized Leaf page.",
        annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
    )
    def leaf_read_compact_ask(page: str) -> CallToolResult:
        state = current_compact_state(resolve_page(page))
        return _result(_compact_summary(state), {"ok": True, "state": state})

    @apps.tool(
        resource_uri=COMPACT_RESOURCE_URI,
        visibility=["app"],
        name="leaf_post_event",
        description=(
            "Validate and append one browser-shaped event to an initialized Leaf page."
        ),
        annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False),
    )
    def leaf_post_event(page: str, event: dict[str, Any]) -> CallToolResult:
        page_dir = resolve_page(page)
        status, answer = endpoint(page_dir).accept(
            dict(event), lambda: current_compact_state(page_dir)
        )
        payload = {**answer, "status": status}
        text = (
            "Leaf event accepted."
            if answer.get("ok")
            else f"Leaf event refused: {answer.get('error', 'unknown error')}"
        )
        return _result(text, payload)

    compact_resource = (
        compact_html
        if compact_html is not None
        else COMPACT_APP_RESOURCE.read_text(encoding="utf-8")
    )
    apps.add_html_resource(
        COMPACT_RESOURCE_URI,
        compact_resource,
        title="Leaf compact ask",
        description="A disposable inline projection of one current Leaf options ask.",
        prefers_border=True,
    )
    page_resource = (
        page_html
        if page_html is not None
        else PAGE_APP_RESOURCE.read_text(encoding="utf-8")
    )
    apps.add_html_resource(
        PAGE_RESOURCE_URI,
        page_resource,
        title="Leaf page",
        description="The complete Leaf browser interface in an MCP App.",
        csp=ResourceCsp(frame_domains=["http://localhost:*"]),
        prefers_border=False,
    )
    return MCPServer(
        "Leaf",
        version="0.1.0",
        description="Open complete Leaf pages and compact asks backed by the ordinary page log.",
        extensions=[apps],
    )


def run_server() -> None:
    create_server().run(transport="stdio")
