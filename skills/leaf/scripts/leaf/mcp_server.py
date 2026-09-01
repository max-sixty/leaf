"""Bundled stdio MCP server and MCP Apps resource."""

from mcp.server.apps import APP_MIME_TYPE, Apps, ResourceCsp
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .mcp_app import APP_URI, ack_delivery, app_html, apply_event, result_for_page


class LeafApps(Apps):
    """The stable MCP Apps extension with Leaf's supported content type."""

    def settings(self) -> dict:
        return {"mimeTypes": [APP_MIME_TYPE]}


def make_mcp_server() -> MCPServer:
    apps = LeafApps()
    apps.add_html_resource(
        APP_URI,
        app_html(),
        name="Leaf review (experimental)",
        description="Experimental interactive review and anchored feedback for a Leaf page.",
        csp=ResourceCsp(connect_domains=[], resource_domains=[]),
        prefers_border=False,
    )

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["model"],
        name="leaf_present",
        title="Present Leaf page (experimental)",
        description=(
            "Present an initialized Leaf page in the experimental compact review. Use "
            "the absolute page directory created by `leaf page init`. The text result "
            "remains useful when this client cannot render MCP Apps UI."
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
        return result_for_page(page)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["app"],
        name="leaf_apply_event",
        title="Apply Leaf reader event",
        description="Validate and durably append one reader event from the Leaf app.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_apply_event(page: str, event: dict, view_revision: int | None = None):
        return apply_event(page, event, view_revision)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["app"],
        name="leaf_refresh",
        title="Refresh Leaf page",
        description="Read the current authoritative Leaf page projection.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_refresh(page: str):
        return result_for_page(page)

    @apps.tool(
        resource_uri=APP_URI,
        visibility=["app"],
        name="leaf_delivery_ack",
        title="Acknowledge Leaf delivery",
        description="Acknowledge a complete Leaf batch after the host accepts its follow-up.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def leaf_delivery_ack(page: str, seq: int):
        return ack_delivery(page, seq)

    return MCPServer(
        "leaf",
        title="Leaf",
        description="Present and continue experimental interactive Leaf review pages.",
        version="1",
        extensions=[apps],
    )


def run_mcp_server() -> None:
    make_mcp_server().run(transport="stdio")
