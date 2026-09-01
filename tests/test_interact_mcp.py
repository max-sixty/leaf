"""The bundled MCP server exposes Leaf without becoming another state authority."""

import asyncio
import json
import os
import sys
from pathlib import Path

from leaf import event_log as events_model
from leaf.mcp_app import APP_MIME, APP_URI, app_snapshot, apply_event
from leaf.mcp_page import PAGE_RESOURCE_URI, ProcessPageServer
from leaf.mcp_server import make_mcp_server
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_snapshot_event_round_trip_is_durable_retryable_and_canonical(page_dir):
    candidate = {
        "kind": "comment",
        "revision": 1,
        "text": "Keep the verification ahead of the flip.",
        "anchor": {"section": "plan", "quote": "The cutoff lives in"},
        "attempt": "mcp-comment-one-1",
    }

    first = apply_event(str(page_dir), candidate, 1)
    repeated = apply_event(str(page_dir), candidate, 1)

    assert first.is_error is False
    assert repeated.is_error is False
    assert len(events_model.read_events(page_dir)) == 1
    accepted = first.structured_content["accepted"]
    assert accepted["attempt"] == "mcp-comment-one-1"
    stored = events_model.read_events(page_dir)[0]
    assert stored["text"] == candidate["text"]
    assert stored["anchor"]["quote"] == "The cutoff lives in"
    assert stored["anchor"]["section"] == "plan"
    assert stored["anchor"]["suffix"]


def test_mcp_write_requires_attempt_identity(page_dir):
    result = apply_event(
        str(page_dir),
        {"kind": "comment", "revision": 1, "text": "No retry identity."},
        1,
    )

    assert result.is_error is True
    assert "attempt id" in result.content[0].text
    assert events_model.read_events(page_dir) == []


def test_mcp_refuses_an_anchor_on_static_widget_source(page_dir):
    result = apply_event(
        str(page_dir),
        {
            "kind": "comment",
            "revision": 1,
            "text": "This source is not the widget's rendered reading.",
            "anchor": {"section": "flow", "quote": "graph LR A --> B"},
            "attempt": "mcp-static-widget-source-1",
        },
        1,
    )

    assert result.is_error is True
    # A person selecting text in the panel reads this refusal, and they have no flags,
    # so it names the recourse rather than a `leaf comment` option.
    refusal = result.content[0].text
    assert "data body is its source" in refusal
    assert "--quote" not in refusal and "--section" not in refusal
    assert events_model.read_events(page_dir) == []


def test_mcp_snapshot_is_authored_source_with_current_cursors_and_private_bytes(
    page_dir,
):
    summary, private = app_snapshot(str(page_dir))

    assert summary == {
        "page": str(page_dir),
        "title": "t",
        "revision": 1,
        "eventSeq": 0,
        "pending": 0,
        "url": None,
    }
    assert "<main>" in private["document"]
    assert "<style>" in private["document"]
    assert private["authoredCss"] == ""
    assert "--paper: #191815" in private["darkTheme"]
    assert "prefers-color-scheme: dark" not in private["theme"]
    assert private["eventSeq"] == 0


def test_codex_manifest_launches_the_bundled_server():
    root = Path(__file__).parent.parent
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text())
    launch = json.loads((root / ".codex-plugin" / "mcp.json").read_text())

    assert plugin["mcpServers"] == "./.codex-plugin/mcp.json"
    assert launch == {
        "mcpServers": {"leaf": {"command": "./bin/leaf", "args": ["mcp"], "cwd": "."}}
    }

    pages = ProcessPageServer()
    try:
        capabilities = make_mcp_server(pages)._lowlevel_server.get_capabilities(
            protocol_version="2026-07-28"
        )
    finally:
        pages.close()
    assert capabilities.extensions == {
        "io.modelcontextprotocol/ui": {"mimeTypes": [APP_MIME]}
    }


def test_stdio_protocol_carries_the_app_resource_and_private_tool_result(page_dir):
    async def exchange():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "leaf", "mcp"],
            env=dict(os.environ),
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(
                reader,
                writer,
                extensions={"io.modelcontextprotocol/ui": {"mimeTypes": [APP_MIME]}},
            ) as session,
        ):
            initialized = await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            resource = await session.read_resource(PAGE_RESOURCE_URI)
            result = await session.call_tool("leaf_present", {"page": str(page_dir)})
            return initialized, tools, resources, resource, result

    initialized, tools, resources, resource, result = asyncio.run(exchange())
    by_name = {tool.name: tool for tool in tools.tools}

    assert initialized.protocol_version == "2025-11-25"
    assert set(by_name) == {
        "leaf_present",
        "leaf_refresh",
        "leaf_present_snapshot",
        "leaf_snapshot_apply_event",
        "leaf_snapshot_refresh",
    }
    assert by_name["leaf_present"].meta == {
        "ui": {"resourceUri": PAGE_RESOURCE_URI, "visibility": ["model"]}
    }
    assert by_name["leaf_present"].annotations.read_only_hint is False
    assert by_name["leaf_snapshot_apply_event"].meta["ui"] == {
        "resourceUri": APP_URI,
        "visibility": ["app"],
    }
    assert {str(item.uri) for item in resources.resources} == {
        PAGE_RESOURCE_URI,
        APP_URI,
    }
    assert resource.contents[0].mime_type == APP_MIME
    assert "ui/initialize" in resource.contents[0].text
    assert result.is_error is False
    assert result.structured_content["title"] == "t"
    assert "document" not in result.structured_content
    assert "inline_url" in result.meta["leaf"]
    assert "inline_url" not in result.structured_content
