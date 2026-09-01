"""Bundled stdio MCP server and Leaf's MCP Apps resources."""

from __future__ import annotations

import atexit

from mcp.server.apps import APP_MIME_TYPE, Apps, ResourceCsp
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .mcp_app import APP_URI, app_html, apply_event, result_for_page
from .mcp_page import (
    PAGE_RESOURCE_URI,
    ProcessPageServer,
    page_app_html,
    page_result,
)


class LeafApps(Apps):
    """The stable MCP Apps extension with Leaf's supported content type."""

    def settings(self) -> dict:
        return {"mimeTypes": [APP_MIME_TYPE]}


def make_mcp_server(
    pages: ProcessPageServer | None = None,
    *,
    page_html: str | None = None,
    snapshot_html: str | None = None,
) -> MCPServer:
    """Build one registered server over the canonical page and a small fallback."""
    pages = pages or ProcessPageServer()
    atexit.register(pages.close)
    apps = LeafApps()
    apps.add_html_resource(
        PAGE_RESOURCE_URI,
        page_html if page_html is not None else page_app_html(),
        name="Leaf page",
        description="The complete canonical Leaf browser interface in an MCP App.",
        csp=ResourceCsp(
            connect_domains=[],
            resource_domains=[],
            frame_domains=[pages.origin],
        ),
        prefers_border=False,
    )
    apps.add_html_resource(
        APP_URI,
        snapshot_html if snapshot_html is not None else app_html(),
        name="Leaf review snapshot",
        description="A compact authored snapshot for hosts that cannot frame the page.",
        csp=ResourceCsp(connect_domains=[], resource_domains=[]),
        prefers_border=False,
    )

    @apps.tool(
        resource_uri=PAGE_RESOURCE_URI,
        visibility=["model"],
        name="leaf_present",
        title="Present Leaf page (experimental)",
        description=(
            "Present the complete canonical interface for an initialized Leaf page. "
            "Use the absolute page directory created by `leaf page init`. The text "
            "result remains useful when this client cannot render MCP Apps UI."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_present(page: str):
        return page_result(page, pages)

    @apps.tool(
        resource_uri=PAGE_RESOURCE_URI,
        visibility=["app"],
        name="leaf_refresh",
        title="Refresh Leaf page",
        description="Read the current canonical Leaf page address and summary.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_refresh(page: str):
        return page_result(page, pages)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["model"],
        name="leaf_present_snapshot",
        title="Present Leaf snapshot (fallback)",
        description=(
            "Present an authored, comments-only Leaf snapshot when the complete page "
            "cannot be framed by this host. Prefer leaf_present."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_present_snapshot(page: str):
        return result_for_page(page)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["app"],
        name="leaf_snapshot_apply_event",
        title="Apply Leaf snapshot comment",
        description="Validate and durably append one reader comment from the snapshot.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_snapshot_apply_event(
        page: str, event: dict, view_revision: int | None = None
    ):
        return apply_event(page, event, view_revision)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["app"],
        name="leaf_snapshot_refresh",
        title="Refresh Leaf snapshot",
        description="Read the current authored Leaf snapshot.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_snapshot_refresh(page: str):
        return result_for_page(page)

    server = MCPServer(
        "leaf",
        title="Leaf",
        description="Present and continue complete Leaf review pages.",
        version="1",
        extensions=[apps],
    )
    return server


def run_mcp_server() -> None:
    pages = ProcessPageServer()
    try:
        make_mcp_server(pages).run(transport="stdio")
    finally:
        pages.close()
