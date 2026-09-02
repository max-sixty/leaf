"""The canonical Leaf page delivered through the registered MCP server."""

import json
import shutil
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from interact_support import PAGE, run_async
from leaf.event_log import append_event, read_events
from leaf.mcp_page import (
    PAGE_APP_RESOURCE,
    PAGE_FORMAT,
    PAGE_RESOURCE_URI,
    ProcessPageServer,
    page_state,
)
from leaf.mcp_server import make_mcp_server
from leaf.revisioning import activate_source


def activate(page_dir, html=PAGE):
    (page_dir / "index.html").write_text(html, encoding="utf-8")
    active = activate_source(page_dir, read_events(page_dir))
    assert active.error is None
    return active.revision


def call(server, name, arguments):
    async def invoke():
        return await server.call_tool(name, arguments)

    return run_async(invoke)


def test_process_server_multiplexes_pages_on_one_exact_origin(page_dir, tmp_path):
    activate(page_dir)
    append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
            "version": 1,
            "revision": 1,
            "text": "published",
        },
    )
    second = tmp_path / "second"
    shutil.copytree(page_dir, second)
    pages = ProcessPageServer()
    try:
        first_url = pages.open(page_dir)
        second_url = pages.open(second)

        assert urlsplit(first_url).scheme == "http"
        assert urlsplit(first_url).hostname == "localhost"
        assert urlsplit(first_url).netloc == urlsplit(second_url).netloc
        assert urlsplit(first_url).path != urlsplit(second_url).path
        assert urlsplit(first_url).query == ""
        assert pages.open(page_dir) == first_url

        with urllib.request.urlopen(first_url) as response:
            html = response.read().decode()
            assert response.headers.get("Set-Cookie") is None
        root = urlsplit(first_url).path.rstrip("/")
        assert f'src="{root}/leaf.js"' in html
        assert f'href="{root}/theme.css"' in html
        assert f'src="{root}/mcp-ready.js"' in html

        with urllib.request.urlopen(f"{pages.origin}{root}/mcp-ready.js") as response:
            ready = response.read().decode()
        assert 'type:"leaf:mcp-page-ready"' in ready

        with urllib.request.urlopen(
            f"{pages.origin}{root}/runtime/layer-client.js"
        ) as response:
            runtime = response.read().decode()
        assert f'fetch("{root}/api/event"' in runtime

        with urllib.request.urlopen(
            f"{pages.origin}{root}/widgets/lf-options.js"
        ) as response:
            widget = response.read().decode()
        assert f'from "{root}/runtime/widget-api.js"' in widget

        with urllib.request.urlopen(f"{pages.origin}{root}/api/state") as response:
            state = json.load(response)
        assert state["active"]["url"].startswith(f"{root}/revisions/")
        assert state["versions"] == [
            {"version": 1, "revision": 1, "url": f"{root}/versions/v1.html"}
        ]
        with urllib.request.urlopen(
            f"{pages.origin}{state['versions'][0]['url']}"
        ) as response:
            assert f'src="{root}/leaf.js"' in response.read().decode()

        try:
            urllib.request.urlopen(f"{pages.origin}/api/state")
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:  # pragma: no cover - the assertion explains the capability boundary
            raise AssertionError("unscoped page route was reachable")

        assert not (page_dir / "service.json").exists()
        assert not (second / "service.json").exists()

        (page_dir / "registry.json").unlink()
        try:
            urllib.request.urlopen(f"{pages.origin}{root}/api/state")
        except urllib.error.HTTPError as error:
            assert error.code == 500
            assert "vendored registry lacks" in error.read().decode()
        else:  # pragma: no cover - the assertion explains the fault boundary
            raise AssertionError("a route-selection fault dropped the connection")
    finally:
        pages.close()


def test_page_result_keeps_the_capability_private(page_dir):
    activate(page_dir)
    pages = ProcessPageServer()
    try:
        summary, private = page_state(str(page_dir), pages)
        server = make_mcp_server(
            pages,
            presentation_html="<!doctype html><title>Leaf app</title>",
        )
        result = call(server, "leaf_present", {"page": str(page_dir)})
    finally:
        pages.close()

    assert summary == result.structured_content
    assert summary["format"] == PAGE_FORMAT
    assert summary["mode"] == "page"
    assert summary["active"]["revision"] == 1
    assert "inline_url" not in summary
    assert "browser_url" not in summary
    assert private["inline_url"].startswith("http://localhost:")
    assert result.meta["leaf"]["inline_url"] == private["inline_url"]


def test_registered_server_uses_one_adaptive_resource_for_every_presentation():
    pages = ProcessPageServer()
    try:
        server = make_mcp_server(
            pages,
            presentation_html="<!doctype html><title>Leaf app</title>",
        )

        async def inspect():
            return await server.list_tools(), await server.list_resources()

        tools, resources = run_async(inspect)
    finally:
        pages.close()

    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "leaf_present",
        "leaf_refresh",
        "leaf_present_snapshot",
        "leaf_snapshot_apply_event",
        "leaf_snapshot_refresh",
    }
    assert by_name["leaf_present"].meta["ui"] == {
        "resourceUri": PAGE_RESOURCE_URI,
        "visibility": ["model"],
    }
    assert by_name["leaf_refresh"].meta["ui"]["visibility"] == ["app"]
    assert by_name["leaf_present_snapshot"].meta["ui"] == {
        "resourceUri": PAGE_RESOURCE_URI,
        "visibility": ["model"],
    }
    assert by_name["leaf_snapshot_apply_event"].meta["ui"]["visibility"] == ["app"]
    assert {tool.meta["ui"]["resourceUri"] for tool in by_name.values()} == {
        PAGE_RESOURCE_URI
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
    assert "leaf_delivery_ack" not in by_name
    assert "leaf_open_compact_ask" not in by_name

    by_uri = {str(resource.uri): resource for resource in resources}
    assert set(by_uri) == {PAGE_RESOURCE_URI}
    assert by_uri[PAGE_RESOURCE_URI].meta == {
        "ui": {
            "csp": {
                "connectDomains": [],
                "resourceDomains": [],
                "frameDomains": [pages.origin],
            },
            "prefersBorder": False,
        }
    }


def test_shipped_adaptive_app_is_one_self_contained_html_blob():
    page = PAGE_APP_RESOURCE.read_text(encoding="utf-8")

    assert "LEAF_MCP_STYLE" not in page
    assert "LEAF_MCP_SCRIPT" not in page
    assert "LEAF_MCP_ICON" not in page
    assert "@modelcontextprotocol/ext-apps 1.7.5" in page
    assert '<script src="' not in page
    assert '<link rel="stylesheet"' not in page
    assert "leaf_refresh" in page
    assert "leaf_snapshot_refresh" in page
    assert "leaf_snapshot_apply_event" in page
    assert 'id="leaf-page"' in page
    assert 'id="page-host"' in page
