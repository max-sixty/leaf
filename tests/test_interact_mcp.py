"""The bundled MCP server exposes Leaf without becoming another state authority."""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from interact_support import PAGE
from leaf import event_log as events_model
from leaf.mcp_app import APP_MIME, SNAPSHOT_FORMAT, app_snapshot, apply_event
from leaf.mcp_page import PAGE_RESOURCE_URI, ProcessPageServer
from leaf.mcp_server import make_mcp_server
from leaf.passages import TEXT_BLOCK_TAGS
from leaf.revisioning import activate_source
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


def test_the_snapshot_door_refuses_a_passage_no_context_identifies(page_dir):
    """The snapshot resolves nothing; the append gate does, and one gesture must name one
    passage. Two copies of the same words are two answers, so the door refuses rather than
    reading document order as identity — and it names the copies, because extending the
    selection is what the reader has to do about it. This is the same rule the browser
    keeps by storing neighbours: neither side ever guesses which copy was meant."""
    twice = PAGE.replace(
        "<h2>Plan</h2>",
        "<h2>Plan</h2>\n  <p>The flag is off. We ship next week.</p>\n"
        "  <p>Later: The flag is off. We hold the release.</p>",
    )
    (page_dir / "index.html").write_text(twice, encoding="utf-8")
    activated = activate_source(page_dir, events_model.read_events(page_dir))
    assert activated.error is None and activated.revision == 2

    def comment(quote, attempt):
        return apply_event(
            str(page_dir),
            {
                "kind": "comment",
                "revision": 2,
                "text": "Which one is this about?",
                "anchor": {"section": "plan", "quote": quote},
                "attempt": attempt,
            },
            2,
        )

    refused = comment("The flag is off", "mcp-ambiguous-passage-1")
    assert refused.is_error is True
    assert "says 'The flag is off' 2 times" in refused.content[0].text
    assert "We hold the release" in refused.content[0].text
    assert [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    ] == []

    accepted = comment("The flag is off. We hold", "mcp-extended-passage-1")
    assert accepted.is_error is False
    stored = events_model.read_events(page_dir)[-1]["anchor"]
    assert stored["quote"] == "The flag is off. We hold"
    assert stored["prefix"].endswith("Later:")


def test_the_snapshot_is_handed_the_block_vocabulary_it_reads_a_selection_with(
    page_dir,
):
    """One space goes wherever the enclosing text block changes, and the file side owns
    which tags those are. The app is sent that vocabulary rather than restating it, so
    there is no third list to keep equal to this one."""
    _, private = app_snapshot(str(page_dir))

    assert set(private["textBlocks"].split(",")) == TEXT_BLOCK_TAGS


def test_mcp_write_requires_attempt_identity(page_dir):
    result = apply_event(
        str(page_dir),
        {"kind": "comment", "revision": 1, "text": "No retry identity."},
        1,
    )

    assert result.is_error is True
    assert "attempt id" in result.content[0].text
    assert events_model.read_events(page_dir) == []


@pytest.mark.parametrize("kind", ["action", "request"])
def test_mcp_snapshot_write_rejects_non_comment_event_kinds(page_dir, kind):
    result = apply_event(
        str(page_dir),
        {"kind": kind, "revision": 1, "attempt": f"mcp-{kind}-one-1"},
        1,
    )

    assert result.is_error is True
    assert result.structured_content == {"ok": False, "status": 400}
    assert "accepts only comment events" in result.content[0].text
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
        "format": SNAPSHOT_FORMAT,
        "mode": "snapshot",
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
    assert {
        name: tool.annotations.read_only_hint for name, tool in by_name.items()
    } == {
        "leaf_present": True,
        "leaf_refresh": True,
        "leaf_present_snapshot": True,
        "leaf_snapshot_apply_event": False,
        "leaf_snapshot_refresh": True,
    }
    assert by_name["leaf_snapshot_apply_event"].meta["ui"] == {
        "resourceUri": PAGE_RESOURCE_URI,
        "visibility": ["app"],
    }
    assert {str(item.uri) for item in resources.resources} == {PAGE_RESOURCE_URI}
    assert resource.contents[0].mime_type == APP_MIME
    assert "ui/initialize" in resource.contents[0].text
    assert result.is_error is False
    assert result.structured_content["title"] == "t"
    assert "document" not in result.structured_content
    assert "inline_url" in result.meta["leaf"]
    assert "inline_url" not in result.structured_content


def test_stdio_snapshot_write_boundary_accepts_only_comments(page_dir):
    async def exchange():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "leaf", "mcp"],
            env=dict(os.environ),
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            rejected = [
                await session.call_tool(
                    "leaf_snapshot_apply_event",
                    {
                        "page": str(page_dir),
                        "view_revision": 1,
                        "event": {
                            "kind": kind,
                            "revision": 1,
                            "attempt": f"stdio-{kind}-one-1",
                        },
                    },
                )
                for kind in ("action", "request")
            ]
            accepted = await session.call_tool(
                "leaf_snapshot_apply_event",
                {
                    "page": str(page_dir),
                    "view_revision": 1,
                    "event": {
                        "kind": "comment",
                        "revision": 1,
                        "text": "Keep the write boundary narrow.",
                        "attempt": "stdio-comment-one-1",
                    },
                },
            )
            return rejected, accepted

    rejected, accepted = asyncio.run(exchange())

    assert all(result.is_error is True for result in rejected)
    assert all(
        "accepts only comment events" in result.content[0].text for result in rejected
    )
    assert accepted.is_error is False
    assert accepted.structured_content["accepted"]["kind"] == "comment"
    assert [event["kind"] for event in events_model.read_events(page_dir)] == [
        "comment"
    ]


def test_stdio_presentation_tools_explain_a_stale_page_layer(page_dir):
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    del registry["$events"]["kinds"]["pickup"]
    registry_path.write_text(json.dumps(registry))

    async def exchange():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "leaf", "mcp"],
            env=dict(os.environ),
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            return [
                await session.call_tool(name, {"page": str(page_dir)})
                for name in ("leaf_present", "leaf_present_snapshot")
            ]

    results = asyncio.run(exchange())

    for result in results:
        assert result.is_error is True
        assert "cannot be presented with its vendored layer" in result.content[0].text
        assert "kind `pickup`" in result.content[0].text
        assert f"leaf page init {page_dir}" in result.content[0].text


def test_stdio_presentation_tools_explain_every_page_precondition(page_dir, tmp_path):
    uninitialized = tmp_path / "uninitialized"
    uninitialized.mkdir()

    no_active = tmp_path / "no-active"
    shutil.copytree(page_dir, no_active)
    (no_active / "index.html").unlink()
    for revision in (no_active / "revisions").glob("*.html"):
        revision.unlink()

    missing_registry = tmp_path / "missing-registry"
    shutil.copytree(page_dir, missing_registry)
    (missing_registry / "registry.json").unlink()

    malformed_registry = tmp_path / "malformed-registry"
    shutil.copytree(page_dir, malformed_registry)
    (malformed_registry / "registry.json").write_text("{not json")

    cases = {
        "uninitialized": (
            uninitialized,
            ["not an initialized Leaf page", "leaf page init"],
        ),
        "no_active": (
            no_active,
            ["has no active revision", "write a valid index.html first"],
        ),
        "missing_registry": (
            missing_registry,
            ["cannot be presented with its vendored layer", "registry.json"],
        ),
        "malformed_registry": (
            malformed_registry,
            ["cannot be presented with its vendored layer", "invalid JSON"],
        ),
    }

    async def exchange():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "leaf", "mcp"],
            env=dict(os.environ),
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            return {
                name: [
                    await session.call_tool(tool, {"page": str(path)})
                    for tool in ("leaf_present", "leaf_present_snapshot")
                ]
                for name, (path, _) in cases.items()
            }

    results = asyncio.run(exchange())

    for name, (path, expected) in cases.items():
        details = []
        for tool, result in zip(
            ("leaf_present", "leaf_present_snapshot"), results[name], strict=True
        ):
            assert result.is_error is True
            message = result.content[0].text
            prefix = f"Error executing tool {tool}: "
            assert message.startswith(prefix)
            details.append(message.removeprefix(prefix))
            assert str(path) in message
            assert "UnexpectedToolError" not in message
            for phrase in expected:
                assert phrase in message
            if "registry" in name:
                assert "leaf page init" in message
        assert details[0] == details[1]
