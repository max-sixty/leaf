"""The bundled MCP server exposes Leaf without becoming another state authority."""

import asyncio
import json
import os
import sys
from pathlib import Path

from leaf import event_log as events_model
from leaf.mcp_app import APP_MIME, APP_URI, ack_delivery, app_snapshot, apply_event
from leaf.mcp_server import make_mcp_server
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_mcp_event_round_trip_is_durable_retryable_and_acknowledged(page_dir):
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
    private = repeated.meta["leaf"]
    delivery = [json.loads(line) for line in private["delivery"].splitlines()]
    assert delivery[0]["page"] == str(page_dir)
    assert delivery[1] == events_model.read_events(page_dir)[0]

    acknowledged = ack_delivery(str(page_dir), private["deliverySeq"])

    assert acknowledged.meta["leaf"]["delivery"] is None
    assert events_model.read_events(page_dir)[0]["text"] == candidate["text"]


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
    assert "data body is its source" in result.content[0].text
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

    capabilities = make_mcp_server()._lowlevel_server.get_capabilities(
        protocol_version="2026-07-28"
    )
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
            resource = await session.read_resource(APP_URI)
            result = await session.call_tool("leaf_present", {"page": str(page_dir)})
            return initialized, tools, resources, resource, result

    initialized, tools, resources, resource, result = asyncio.run(exchange())
    by_name = {tool.name: tool for tool in tools.tools}

    assert initialized.protocol_version == "2025-11-25"
    assert set(by_name) == {
        "leaf_present",
        "leaf_apply_event",
        "leaf_refresh",
        "leaf_delivery_ack",
    }
    assert by_name["leaf_present"].meta == {
        "ui": {"resourceUri": APP_URI, "visibility": ["model"]}
    }
    assert by_name["leaf_present"].annotations.read_only_hint is False
    assert by_name["leaf_apply_event"].meta["ui"] == {
        "resourceUri": APP_URI,
        "visibility": ["app"],
    }
    assert str(resources.resources[0].uri) == APP_URI
    assert resources.resources[0].mime_type == APP_MIME
    assert resource.contents[0].mime_type == APP_MIME
    assert "ui/initialize" in resource.contents[0].text
    assert result.is_error is False
    assert result.structured_content["title"] == "t"
    assert "document" not in result.structured_content
    assert "document" in result.meta["leaf"]
