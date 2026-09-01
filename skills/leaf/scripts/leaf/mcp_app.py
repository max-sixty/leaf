"""Leaf's MCP Apps projection and durable feedback tools."""

import copy
from pathlib import Path

from mcp.types import CallToolResult, TextContent
from tinycss2 import parse_stylesheet, serialize

from .event_endpoint import EventEndpoint
from .exporting import inline_assets, inline_css_assets
from .files import revision_path
from .mcp_page import (
    PAGE_APP_RESOURCE,
    require_active_revision,
    resolve_page,
    unpresentable_layer_error,
)
from .registry.contract import RegistryError
from .registry.storage import layer_generation
from .served_state.service import PageStateService
from .structure import parse_structure

APP_MIME = "text/html;profile=mcp-app"
SNAPSHOT_FORMAT = "leaf.snapshot/v1"

_ENDPOINTS: dict[tuple[Path, str], EventEndpoint] = {}


def split_theme(theme: str) -> tuple[str, str]:
    """Separate the OS-dark block so the MCP host's declared theme can select it."""
    base = []
    dark = []
    for rule in parse_stylesheet(theme):
        if (
            rule.type == "at-rule"
            and rule.lower_at_keyword == "media"
            and serialize(rule.prelude).strip() == "(prefers-color-scheme: dark)"
            and rule.content is not None
        ):
            dark.append(serialize(rule.content))
        else:
            base.append(serialize([rule]))
    return "".join(base), "".join(dark)


def state_service(page_dir: Path) -> PageStateService:
    return PageStateService(page_dir)


def app_snapshot(page: str) -> tuple[dict, dict]:
    page_dir = resolve_page(page)
    try:
        state = state_service(page_dir).page_state()
    except RegistryError as error:
        raise unpresentable_layer_error(page_dir, str(error)) from error
    active = require_active_revision(page_dir, state)
    if state["browser"] is None:
        detail = state["source_error"] or "the page registry cannot be projected"
        raise unpresentable_layer_error(page_dir, detail)
    revision = active["revision"]
    source = revision_path(page_dir, revision).read_text(encoding="utf-8")
    parsed = parse_structure(source)
    document = inline_assets(source, page_dir)
    title = parsed.title.strip() or page_dir.name
    theme, dark_theme = split_theme(
        (page_dir / "theme.css").read_text(encoding="utf-8")
    )
    server = state.get("server") or {}
    summary = {
        "format": SNAPSHOT_FORMAT,
        "mode": "snapshot",
        "page": str(page_dir),
        "title": title,
        "revision": revision,
        "eventSeq": state["browser"]["basis"]["through_seq"],
        "pending": state.get("pending", 0),
        "url": server.get("url"),
    }
    private = {
        **summary,
        "document": document,
        "authoredCss": inline_css_assets(parsed.css, page_dir),
        "theme": theme,
        "darkTheme": dark_theme,
    }
    return summary, private


def result_for_page(page: str, *, message: str | None = None) -> CallToolResult:
    summary, private = app_snapshot(page)
    text = message or (
        f"Leaf page {summary['title']!r} is ready at revision r{summary['revision']}."
    )
    if summary["url"]:
        text += f" Full browser view: {summary['url']}"
    text += " The page directory and append-only event log remain authoritative."
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=summary,
        _meta={"leaf": private},
    )


def apply_event(page: str, event: dict, view_revision: int | None) -> CallToolResult:
    candidate = copy.deepcopy(event)
    if candidate.get("kind") != "comment":
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="Leaf snapshot feedback accepts only comment events.",
                )
            ],
            structuredContent={"ok": False, "status": 400},
            isError=True,
        )
    page_dir = resolve_page(page)
    if not candidate.get("attempt"):
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text="A Leaf reader event needs a stable non-empty attempt id.",
                )
            ],
            structuredContent={"ok": False, "status": 400},
            isError=True,
        )
    layer = layer_generation(page_dir)
    # The app renders the authored source with no runtime behind it, so a selection
    # here names a passage nothing has resolved yet. The door captures it against the
    # page under the same lease that appends it.
    endpoint = _ENDPOINTS.setdefault(
        (page_dir, layer), EventEndpoint(page_dir, capture_anchors=True)
    )
    service = PageStateService(page_dir)
    status, answer = endpoint.accept(
        candidate, lambda: service.page_state(view_revision)
    )
    if status != 200:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Leaf refused the reader event: {answer.get('error', 'invalid event')}",
                )
            ],
            structuredContent={"ok": False, "status": status, **answer},
            isError=True,
        )
    attempt = candidate["attempt"]
    receipt = next(
        (
            logged
            for logged in answer["state"]["events"]
            if logged.get("attempt") == attempt
        ),
        None,
    )
    result = result_for_page(
        str(page_dir),
        message="Leaf durably recorded the reader event.",
    )
    result.structured_content["accepted"] = receipt
    result.structured_content["ok"] = True
    return result


def app_html() -> str:
    return PAGE_APP_RESOURCE.read_text(encoding="utf-8")
