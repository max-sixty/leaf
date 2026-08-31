"""The full and compact MCP Apps surfaces and their durable return paths."""

import tempfile
import urllib.request
from urllib.parse import parse_qs, urlsplit

import anyio
from conftest import LEAF_COMMAND
from interact_support import PAGE
from leaf.event_log import read_events
from leaf.mcp_app import (
    COMPACT_APP_RESOURCE,
    COMPACT_FORMAT,
    COMPACT_RESOURCE_URI,
    PAGE_APP_RESOURCE,
    PAGE_FORMAT,
    PAGE_RESOURCE_URI,
    PageServerPool,
    create_server,
    current_compact_state,
    current_page_state,
)
from leaf.revisioning import activate_source
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def options_page(*, multiple=False):
    flags = "choose multiple" if multiple else "choose"
    return PAGE.replace("<lf-options>", f'<lf-options id="plan-choice" {flags}>')


def activate(page_dir, html):
    (page_dir / "index.html").write_text(html, encoding="utf-8")
    active = activate_source(page_dir, read_events(page_dir))
    assert active.error is None
    return active.revision


def call(server, name, arguments):
    async def invoke():
        return await server.call_tool(name, arguments)

    return anyio.run(invoke)


def test_compact_state_projects_the_surface_source_and_declared_action(page_dir):
    revision = activate(page_dir, options_page())

    state = current_compact_state(page_dir)

    assert state["format"] == COMPACT_FORMAT
    assert state["mode"] == "ask"
    assert state["page"] == str(page_dir)
    assert state["ask"] == {
        "surface": "plan-choice-decision",
        "source": "plan-choice",
        "question": "Which plan should lead?",
        "context": "",
        "options": [
            {
                "id": "flag-first",
                "label": "Flag first",
                "summary": "effort: low risk: med Flag first Ship dark.",
            },
            {
                "id": "backfill-first",
                "label": "Backfill first",
                "summary": (
                    "effort: med risk: low Backfill first Verify, then flip. "
                    "My take: do this first."
                ),
            },
        ],
        "submit": {
            "kind": "action",
            "revision": revision,
            "widget": "plan-choice",
            "action": "choose",
        },
    }


def test_nested_markup_in_the_decision_heading_keeps_its_readable_title(page_dir):
    html = options_page().replace(
        "Which plan should lead?",
        "Which <span>plan <span>now</span></span> should lead?",
    )
    activate(page_dir, html)

    assert current_compact_state(page_dir)["ask"]["question"] == (
        "Which plan now should lead?"
    )


def test_context_keeps_direct_prose_without_repeating_the_options(page_dir):
    html = options_page().replace(
        '<lf-options id="plan-choice" choose>',
        "<p>Use the reversible path.<p>Keep the receipt.</p>"
        '<lf-options id="plan-choice" choose>',
    )
    activate(page_dir, html)

    assert current_compact_state(page_dir)["ask"]["context"] == (
        "Use the reversible path. Keep the receipt."
    )


def test_unsupported_or_ambiguous_asks_fall_back_explicitly(page_dir):
    activate(page_dir, options_page(multiple=True))
    state = current_compact_state(page_dir)
    assert (state["mode"], state["reason"], state["ask"]) == (
        "fallback",
        "unsupported-options",
        None,
    )

    second = options_page().replace(
        "</section>",
        """
        <lf-decision id="second-decision">
          <h3>And the second plan?</h3>
          <lf-options id="second-choice" choose>
            <lf-option id="second-a">A</lf-option>
            <lf-option id="second-b">B</lf-option>
          </lf-options>
        </lf-decision>
        </section>
        """,
    )
    activate(page_dir, second)
    state = current_compact_state(page_dir)
    assert state["reason"] == "several-open-asks"
    assert "2 open asks" in state["message"]

    wrapped = options_page().replace(
        '<lf-options id="plan-choice" choose>',
        '<div><lf-options id="plan-choice" choose>',
    )
    wrapped = wrapped.replace("</lf-options>", "</lf-options></div>", 1)
    activate(page_dir, wrapped)
    assert current_compact_state(page_dir)["reason"] == "nested-options"


def test_invalid_mutable_source_does_not_silently_present_the_last_good_ask(page_dir):
    activate(page_dir, options_page())
    (page_dir / "index.html").write_text(
        options_page().replace("<h3>Which plan should lead?</h3>", ""),
        encoding="utf-8",
    )

    state = current_compact_state(page_dir)

    assert state["mode"] == "fallback"
    assert state["reason"] == "source-invalid"
    assert state["source_error"]
    assert state["ask"] is None


def test_full_page_state_addresses_the_ordinary_browser_interface(page_dir):
    revision = activate(page_dir, options_page())

    state = current_page_state(
        page_dir, lambda _page: "http://127.0.0.1:41234/?t=test"
    )

    assert {key: value for key, value in state.items() if key != "active"} == {
        "format": PAGE_FORMAT,
        "mode": "page",
        "page": str(page_dir),
        "title": "t",
        "event_seq": 0,
        "source_error": None,
        "url": "http://127.0.0.1:41234/?t=test",
        "message": "Opening the complete Leaf page.",
    }
    assert state["active"]["revision"] == revision
    assert state["active"]["label"] == "Draft"


def test_process_scoped_page_server_uses_an_ephemeral_page_token(
    page_dir, monkeypatch
):
    activate(page_dir, options_page())
    monkeypatch.setattr(
        "leaf.mcp_app.secrets.token_urlsafe", lambda _size: "mcp-page-token"
    )
    pool = PageServerPool()
    try:
        url = pool.open(page_dir)
        with urllib.request.urlopen(url) as response:
            html = response.read().decode("utf-8")
            cookie = response.headers["Set-Cookie"]
        assert "<title>t</title>" in html
        assert '<script type="module" src="/leaf.js"></script>' in html
        assert urlsplit(url).hostname == "localhost"
        assert parse_qs(urlsplit(url).query) == {"t": ["mcp-page-token"]}
        assert "SameSite=None" in cookie
        assert "Secure" in cookie
        assert "Partitioned" in cookie
        assert pool.open(page_dir) == url
        assert not (page_dir / "service.json").exists()
    finally:
        pool.close()


def test_mcp_tools_bind_each_surface_and_hide_the_return_tools_from_model():
    server = create_server(
        "<!doctype html><title>compact app</title>",
        "<!doctype html><title>page app</title>",
        lambda _page: "http://127.0.0.1:41234/?t=test",
    )

    async def inspect():
        return await server.list_tools(), await server.list_resources()

    tools, resources = anyio.run(inspect)
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "leaf_open_page",
        "leaf_read_page",
        "leaf_open_compact_ask",
        "leaf_read_compact_ask",
        "leaf_post_event",
    }
    assert by_name["leaf_open_page"].meta["ui"] == {
        "resourceUri": PAGE_RESOURCE_URI,
        "visibility": ["model"],
    }
    assert by_name["leaf_open_page"].annotations.read_only_hint is False
    assert by_name["leaf_read_page"].meta["ui"]["visibility"] == ["app"]
    assert by_name["leaf_read_page"].annotations.read_only_hint is False
    assert by_name["leaf_open_compact_ask"].meta["ui"] == {
        "resourceUri": COMPACT_RESOURCE_URI,
        "visibility": ["model"],
    }
    assert by_name["leaf_read_compact_ask"].meta["ui"]["visibility"] == ["app"]
    assert by_name["leaf_post_event"].meta["ui"]["visibility"] == ["app"]
    by_uri = {str(resource.uri): resource for resource in resources}
    assert set(by_uri) == {PAGE_RESOURCE_URI, COMPACT_RESOURCE_URI}
    assert by_uri[COMPACT_RESOURCE_URI].mime_type == "text/html;profile=mcp-app"
    assert by_uri[COMPACT_RESOURCE_URI].meta == {"ui": {"prefersBorder": True}}
    assert by_uri[PAGE_RESOURCE_URI].meta == {
        "ui": {
            "csp": {"frameDomains": ["http://localhost:*"]},
            "prefersBorder": False,
        }
    }


def test_mcp_command_negotiates_and_serves_the_shipped_resource(page_dir):
    activate(page_dir, options_page())

    async def inspect(errors):
        params = StdioServerParameters(
            command=LEAF_COMMAND[0],
            args=[*LEAF_COMMAND[1:], "mcp", "run"],
        )
        async with (
            stdio_client(params, errlog=errors) as (reader, writer),
            ClientSession(reader, writer) as client,
        ):
            initialized = await client.initialize()
            tools = await client.list_tools()
            resources = await client.list_resources()
            page_resource = await client.read_resource(PAGE_RESOURCE_URI)
            compact_resource = await client.read_resource(COMPACT_RESOURCE_URI)
            opened = await client.call_tool("leaf_open_page", {"page": str(page_dir)})
            compact = await client.call_tool(
                "leaf_open_compact_ask", {"page": str(page_dir)}
            )
            return (
                initialized,
                tools,
                resources,
                page_resource,
                compact_resource,
                opened,
                compact,
            )

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        (
            initialized,
            tools,
            resources,
            page_resource,
            compact_resource,
            opened,
            compact,
        ) = anyio.run(inspect, errors)
        errors.seek(0)
        server_errors = errors.read()

    assert initialized.server_info.name == "Leaf"
    assert {tool.name for tool in tools.tools} == {
        "leaf_open_page",
        "leaf_read_page",
        "leaf_open_compact_ask",
        "leaf_read_compact_ask",
        "leaf_post_event",
    }
    assert {str(item.uri) for item in resources.resources} == {
        PAGE_RESOURCE_URI,
        COMPACT_RESOURCE_URI,
    }
    assert page_resource.contents[0].mime_type == "text/html;profile=mcp-app"
    assert page_resource.contents[0].text == PAGE_APP_RESOURCE.read_text(
        encoding="utf-8"
    )
    assert compact_resource.contents[0].text == COMPACT_APP_RESOURCE.read_text(
        encoding="utf-8"
    )
    assert opened.structured_content["state"]["mode"] == "page"
    assert opened.structured_content["state"]["url"].startswith("http://localhost:")
    assert compact.structured_content["state"]["mode"] == "ask"
    assert server_errors == ""


def test_shipped_app_resource_is_one_self_contained_html_blob():
    compact = COMPACT_APP_RESOURCE.read_text(encoding="utf-8")
    page = PAGE_APP_RESOURCE.read_text(encoding="utf-8")

    for html in (compact, page):
        assert "LEAF_MCP_STYLE" not in html
        assert "LEAF_MCP_SCRIPT" not in html
        assert "LEAF_MCP_ICON" not in html
        assert "@modelcontextprotocol/ext-apps 1.7.5" in html
        assert '<script src="' not in html
        assert '<link rel="stylesheet"' not in html
    assert "leaf_read_compact_ask" in compact
    assert "leaf_post_event" in compact
    assert "leaf_read_page" in page
    assert 'id="leaf-page"' in page


def test_app_tool_posts_through_the_event_door_and_a_fresh_server_replays_it(page_dir):
    revision = activate(page_dir, options_page())
    server = create_server("<!doctype html><title>test app</title>")
    opened = call(server, "leaf_open_compact_ask", {"page": str(page_dir)})
    assert opened.structured_content["state"]["mode"] == "ask"

    event = {
        "kind": "action",
        "revision": revision,
        "widget": "plan-choice",
        "action": "choose",
        "detail": {"options": ["backfill-first"]},
        "attempt": "mcp-app-test-0001",
    }
    posted = call(
        server,
        "leaf_post_event",
        {"page": str(page_dir), "event": event},
    )

    assert posted.structured_content["ok"] is True
    assert posted.structured_content["status"] == 200
    assert posted.structured_content["state"]["mode"] == "empty"
    assert read_events(page_dir)[-1]["detail"] == {"options": ["backfill-first"]}

    reopened = call(
        create_server("<!doctype html><title>fresh app</title>"),
        "leaf_read_compact_ask",
        {"page": str(page_dir)},
    )
    assert reopened.structured_content["state"]["mode"] == "empty"
    assert reopened.structured_content["state"]["event_seq"] == 1


def test_app_tool_refuses_an_invalid_choice_without_appending(page_dir):
    revision = activate(page_dir, options_page())
    server = create_server("<!doctype html><title>test app</title>")

    refused = call(
        server,
        "leaf_post_event",
        {
            "page": str(page_dir),
            "event": {
                "kind": "action",
                "revision": revision,
                "widget": "plan-choice",
                "action": "not-declared",
                "detail": {"options": ["backfill-first"]},
                "attempt": "mcp-app-test-0002",
            },
        },
    )

    assert refused.structured_content["ok"] is False
    assert refused.structured_content["status"] == 400
    assert "not-declared" in refused.structured_content["error"]
    assert read_events(page_dir) == []
