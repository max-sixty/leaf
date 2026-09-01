#!/usr/bin/env python3
"""Probe the shipped MCP server across its real stdio process boundary."""

import hashlib
import json
import sys
from pathlib import Path

import anyio
from leaf.event_log import read_events
from leaf.mcp_app import APP_RESOURCE, RESOURCE_URI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[4]


async def session(page_dir: Path, *, settle: bool) -> dict:
    params = StdioServerParameters(
        command=str(REPO / "bin/leaf"),
        args=["mcp", "run"],
        cwd=REPO,
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as client,
    ):
        initialized = await client.initialize()
        tools = await client.list_tools()
        resources = await client.list_resources()
        resource = await client.read_resource(RESOURCE_URI)
        opened = await client.call_tool("leaf_open_page", {"page": str(page_dir)})
        state = opened.structured_content["state"]
        result = {
            "initialize": initialized.model_dump(by_alias=True),
            "tools": [tool.model_dump(by_alias=True) for tool in tools.tools],
            "resources": [
                item.model_dump(by_alias=True) for item in resources.resources
            ],
            "resource": {
                "uri": str(resource.contents[0].uri),
                "mime_type": resource.contents[0].mime_type,
                "length": len(resource.contents[0].text),
                "sha256": hashlib.sha256(
                    resource.contents[0].text.encode("utf-8")
                ).hexdigest(),
            },
            "opened": state,
        }
        if settle:
            submit = state["ask"]["submit"]
            posted = await client.call_tool(
                "leaf_post_event",
                {
                    "page": str(page_dir),
                    "event": {
                        **submit,
                        "detail": {"options": ["opt-redis"]},
                        "attempt": "mcp-app-stdio-0001",
                    },
                },
            )
            result["posted"] = posted.structured_content
        return result


async def main(page_dir: Path) -> None:
    first = await session(page_dir, settle=True)
    second = await session(page_dir, settle=False)
    shipped = APP_RESOURCE.read_bytes()
    print(
        json.dumps(
            {
                "first_process": first,
                "second_process": second,
                "shipped_resource": {
                    "length": len(shipped),
                    "sha256": hashlib.sha256(shipped).hexdigest(),
                },
                "log": read_events(page_dir),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    anyio.run(main, Path(sys.argv[1]).resolve())
