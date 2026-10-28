"""The website's HTTP routes over the real page server: example, product and sample
pages, crawler metadata, layer and protocol refusals, and what the container logs."""

import json
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import replace

import leaf_website as website_server
import pytest
from interact_support import comment as open_thread
from interact_support import (
    owed_answers,
    publish,
    revision_root,
    running_http_server,
)
from leaf_dev.commands import journey, verify_site

from leaf.event_log import read_events
from leaf.files import revision_path
from leaf.hosting import LeafHTTPServer
from leaf.http import page_delivery
from leaf.registry.storage import LAYER, layer_record, load_registry
from leaf.revision_artifact import capture_artifact
from leaf.revision_delivery import compose_document
from leaf.runtime_selection import executing, serving_runtime
from leaf.schema import LAYER_FILE
from leaf.served_state import page as served_page
from leaf.structure import SourceDocument
from process.website_server import (
    FakeCodexHarness,
    get,
    post,
    write_manifest,
)

PAGE_SOURCE = """<!doctype html>
<html lang="en">
  <head>
    <title>Choose the next fix</title>
    <meta name="description" content="Pick one." />
  </head>
  <body>
    <main><h1>Choose</h1></main>
  </body>
</html>
"""


@pytest.mark.parametrize(
    ("page_root", "kind", "url"),
    (
        ("", "product", "https://leaf.page/"),
        ("/examples/decision", "example", "https://leaf.page/examples/decision/"),
    ),
)
def test_a_published_document_names_its_page_to_a_crawler(
    page_dir, page_root, kind, url
):
    """An unfurler reads absolute URLs, and reads them from inside the head.

    Leaf owns the canonical address; publication adds what needs the site's origin.
    """
    page = {
        "kind": kind,
        "title": 'Choose the "next" fix',
        "description": "Pick one.",
        "image": "/media/card.png",
    }
    addition = website_server.site_metadata(page_root, page)
    resources = executing(
        capture_artifact(
            page_dir,
            SourceDocument(PAGE_SOURCE),
            load_registry(page_dir),
        )
    ).resources
    delivery = page_delivery(
        resources, server_id="server", layer_id="layer", page_root=page_root
    )
    served = compose_document(
        PAGE_SOURCE,
        1,
        1,
        executable="sha256:executable",
        widgets={},
        resources=resources,
        registry={},
        delivery=replace(delivery, head=addition),
    )
    head = served[: served.index("</head>")]
    assert f'<link rel="canonical" href="{page_root}/" data-lf-runtime>' in head
    assert f'<meta property="og:url" content="{url}" data-lf-runtime>' in head
    assert (
        '<meta property="og:image" content="https://leaf.page/media/card.png"'
        " data-lf-runtime>" in head
    )
    assert (
        '<meta property="og:title" content="Choose the &quot;next&quot; fix"'
        " data-lf-runtime>" in head
    )
    assert (
        '<meta name="twitter:card" content="summary_large_image" data-lf-runtime>'
        in head
    )
    assert "sitenote.js" not in served
    runtime = f'src="{page_root}/leaf.js"' if page_root else 'src="/leaf.js"'
    assert head.index("theme.css") < head.index('property="og:type"')
    assert head.index('property="og:type"') < head.index(runtime)


def test_agent_logs_are_structured_and_content_free(capsys):
    website_server.log_agent(
        "container_start_completed",
        eventId="user-event",
        durationMs=125,
    )

    assert json.loads(capsys.readouterr().out) == {
        "component": "leaf-agent",
        "event": "container_start_completed",
        "eventId": "user-event",
        "durationMs": 125,
    }


def test_agent_logs_keep_every_event_in_a_batched_turn_searchable(capsys):
    website_server.log_agent(
        "turn_start_acknowledged",
        **website_server.agent_event_fields(("event-1", "event-2")),
        turnId="turn-1",
    )

    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {
            "component": "leaf-agent",
            "event": "turn_start_acknowledged",
            "turnId": "turn-1",
            "eventId": "event-1",
        },
        {
            "component": "leaf-agent",
            "event": "turn_start_acknowledged",
            "turnId": "turn-1",
            "eventId": "event-2",
        },
    ]


def test_a_fault_record_keeps_the_end_of_an_oversized_message():
    """A boundary that raises with a whole file does not get to fill the log.

    `_wait_for_app_server` raises with App Server's entire log as the message when a
    spawn never becomes ready, and a record is not where a log file belongs. The
    reason a process exited is at the end of its log, so that is the part kept.
    """
    short = website_server.fault_fields(RuntimeError("no thread by that id"))
    assert short == {"error": "RuntimeError", "detail": "no thread by that id"}

    log = "noise\n" * 400 + "fatal: the reason it exited"
    assert len(log) > website_server.FAULT_DETAIL_LIMIT
    bounded = website_server.fault_fields(RuntimeError(log))
    assert bounded["error"] == "RuntimeError"
    assert bounded["detail"].endswith("fatal: the reason it exited")
    assert bounded["detail"].startswith("\u2026")
    assert len(bounded["detail"]) == website_server.FAULT_DETAIL_LIMIT + 1

    # The other boundary that writes a `detail` is App Server reporting its own turn
    # failed, and the record's size contract is the record's, not one writer's.
    reported = website_server.terminal_fault({"error": {"message": log}})
    assert reported == {"detail": bounded["detail"]}


def test_a_page_fault_is_recorded_where_an_operator_reads_it(
    page_dir, tmp_path, monkeypatch, capsys
):
    """The 500 answers the browser; the container's log is what diagnoses it.

    Cloudflare's own record of a refused request carries its route and its status
    and nothing about the boundary that refused, so a fault this adapter answers
    for is unreadable unless the adapter says it on the stream Cloudflare drains.
    """
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
    )
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"

    def faulting_state(*_args, **_kwargs):
        raise RuntimeError("the projection could not be read")

    monkeypatch.setattr(served_page, "read_served_page", faulting_state)
    with running_http_server(httpd):
        with pytest.raises(urllib.error.HTTPError) as refused:
            get(f"{origin}/examples/decision/api/state")
        assert refused.value.code == 500
        told = json.loads(refused.value.read())

    assert told == {"error": "RuntimeError: the projection could not be read"}
    [recorded] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if '"page_fault"' in line
    ]
    assert recorded == {
        "component": "leaf-agent",
        "event": "page_fault",
        "route": "/examples/decision",
        "method": "GET",
        "path": "/api/state",
        "error": "RuntimeError",
        "detail": "the projection could not be read",
    }


def test_a_child_page_fault_is_recorded_like_the_page_it_was_opened_from(
    page_dir, tmp_path, monkeypatch, capsys
):
    """A sample is a page, and its 500 is as unreadable as any other page's.

    The kernel builds the child endpoint itself, so a host that keeps a copy of its
    faults only keeps it for the routes it built the parent for unless the child is
    told where that copy goes. The record names the address the browser asked at,
    which is the parent's, because that is the request the operator is looking for.
    """
    source = (page_dir / "index.html").read_text()
    template = (
        '<template id="practice" data-sample><h1>Practice</h1>'
        '<p id="child-text">A private child page.</p></template>'
    )
    (page_dir / "index.html").write_text(
        source.replace("</main>", template + "</main>")
    )
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
    )
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"

    def faulting_state(*_args, **_kwargs):
        raise RuntimeError("the child projection could not be read")

    with running_http_server(httpd):
        parent = f"{origin}/examples/decision/"
        state = json.loads(get(f"{parent}api/state")[0])
        child, _ = post(
            f"{parent}api/samples",
            {"template": "practice"},
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        capsys.readouterr()
        monkeypatch.setattr(served_page, "read_served_page", faulting_state)
        with pytest.raises(urllib.error.HTTPError) as refused:
            get(f"{origin}{child['url']}api/state")
        assert refused.value.code == 500
        told = json.loads(refused.value.read())

    assert told == {"error": "RuntimeError: the child projection could not be read"}
    [recorded] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if '"page_fault"' in line
    ]
    sample = child["url"].removeprefix("/examples/decision")
    assert recorded == {
        "component": "leaf-agent",
        "event": "page_fault",
        "route": "/examples/decision",
        "method": "GET",
        "path": f"{sample}api/state",
        "error": "RuntimeError",
        "detail": "the child projection could not be read",
    }


@pytest.mark.parametrize("published_revision", [False, True])
def test_website_samples_serve_private_pages_without_starting_an_agent(
    page_dir, tmp_path, published_revision
):
    source = (page_dir / "index.html").read_text()
    template = '<template id="practice" data-sample><h1>Practice</h1><p id="child-text">A private child page.</p></template>'
    (page_dir / "index.html").write_text(
        source.replace("</main>", template + "</main>")
    )
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    harness = FakeCodexHarness()
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    if published_revision:
        manifest["pages"]["/examples/decision"]["states"] = {
            "1": "/_leaf/state/decision--r1.json"
        }
    manifest_path.write_text(json.dumps(manifest))
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, harness)
    )
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        parent = origin + "/examples/decision/"
        state = json.loads(get(parent + "api/state")[0])
        child, _ = post(
            parent + "api/samples",
            {"template": "practice"},
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        url = origin + child["url"]
        document, headers = get(url)
        assert b"A private child page." in document
        if published_revision:
            asset_root = manifest["pages"]["/examples/decision"]["assets"]
            expected = f"{asset_root}/revisions/{revision_path(published, 1).stem}"
            assert f'data-lf-entry="{expected}/leaf.js"'.encode() in document
        else:
            entry = re.search(rb'data-lf-entry="([^"]+)"', document)[1].decode()
            assert entry.startswith(child["url"] + "revisions/")
            assert get(origin + entry)[0]
        assert f'data-lf-page-root="{child["url"].rstrip("/")}"'.encode() in document
        assert b"sitenote.js" not in document
        assert b"data-lf-release=" not in document
        assert headers.get("Content-Security-Policy") is None
        assert headers["Cache-Control"] == "no-store"
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["Leaf-Layer"] == state["layer"]["generation"]
        accepted, _ = post(
            url + "api/event",
            {
                "kind": "comment",
                "revision": 1,
                "text": "Try this here",
                "anchor": {"section": "child-text"},
            },
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        assert accepted["state"]["events"][-1]["text"] == "Try this here"
        assert read_events(published) == []
        assert harness.attached == []


def test_the_website_refuses_a_page_initialized_at_another_protocol(page_dir, tmp_path):
    """The container serves only pages initialized at its own Leaf's protocol, as
    every page server does; a site built across a breaking change breaks in the
    browser otherwise."""
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    record = layer_record(published)
    (published / LAYER_FILE).unlink()
    LAYER.write(published / LAYER_FILE, {**record, "protocol": 999})
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = LeafHTTPServer(("127.0.0.1", 0), website_server.site_endpoint(site))
    root = f"http://127.0.0.1:{httpd.server_address[1]}/examples/decision"
    with (
        running_http_server(httpd),
        pytest.raises(urllib.error.HTTPError) as refused,
    ):
        get(f"{root}/api/state")
    assert refused.value.code == 500
    told = json.loads(refused.value.read())["error"]
    assert "page protocol 999" in told


def test_a_website_example_uses_the_real_page_server(page_dir, tmp_path, monkeypatch):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    # The session that wrote the page left its voice in the log; the copy is still
    # answered by the host's agent.
    monkeypatch.setenv("LEAF_AGENT", "Claude")
    monkeypatch.setenv("LEAF_SESSION_ID", "authoring-session")
    opened = open_thread(published, "--text", "Which plan reads best?")
    assert opened.exit_code == 0, opened.output
    monkeypatch.delenv("LEAF_AGENT")
    monkeypatch.delenv("LEAF_SESSION_ID")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    agent_harness = FakeCodexHarness()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_harness)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        assert get(f"{root}/health")[0] == b"ok\n"

        document, headers = get(f"{root}/examples/decision/")
        assert b"sitenote.js" not in document
        served = revision_root(published, 1)
        assert (
            f'data-lf-entry="/examples/decision{served}/leaf.js"'.encode() in document
        )
        assert headers["Content-Security-Policy"] == "frame-ancestors 'self'"
        assert headers["Leaf-Session"] == "active"
        # A visitor's private page stays out of the browser's disk cache.
        assert headers["Cache-Control"] == "no-store"

        # A released document sends the public startup beacon, which the deployed site
        # answers at the edge. Nothing stands in front of this adapter, so it owes the
        # browser the same empty acknowledgement — a 404 here is a console error on
        # every page the site serves.
        assert b'data-lf-release="' in document
        beacon = urllib.request.Request(
            f"{root}/examples/decision/api/performance",
            data=json.dumps({"version": 1, "outcome": "presented"}).encode(),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )
        with urllib.request.urlopen(beacon) as recorded:
            assert recorded.status == 204
            assert recorded.read() == b""

        raw_state, headers = get(f"{root}/examples/decision/api/state")
        state = json.loads(raw_state)
        assert state["publication"] == {
            "kind": "example",
            "agent": "Agent",
            "install_url": "/#install",
        }
        assert state["agent"] == "Agent"
        assert headers["Leaf-Layer"] == state["layer"]["generation"]
        assert headers["Leaf-Session"] == "active"
        assert headers["Cache-Control"] == "no-store"

        raw_view, _ = get(
            verify_site.activation_url(f"{root}/examples/decision/", state)
        )
        view = json.loads(raw_view)
        revision = state["active"]["revision"]
        assert view["browser"]["views"][str(revision)]["basis"] == {
            "revision": revision,
            "through_seq": state["events"][-1]["seq"] if state["events"] else 0,
        }
        # The comparison base carries its own obligation records, because the browser reads
        # which obligations a revision holds rather than folding the declarations again.
        assert isinstance(view["browser"]["views"][str(revision)]["obligations"], list)

        posted = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "text": "This came through the public example.",
            "anchor": {"section": "plan"},
            "attempt": "website-example-01",
        }
        answer, _ = post(
            f"{root}/examples/decision/api/event",
            posted,
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        assert answer["ok"] is True
        comment = read_events(published)[-1]
        assert comment["text"] == posted["text"]
        assert (
            next(
                event
                for event in answer["state"]["events"]
                if event.get("attempt") == posted["attempt"]
            )["id"]
            == comment["id"]
        )
        assert comment["id"] in {
            obligation["input"] for obligation in owed_answers(published)
        }

        started, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_harness.attached == [published]

        with pytest.raises(urllib.error.HTTPError) as forged:
            post(
                f"{root}/examples/decision/api/event",
                {
                    "kind": "reply",
                    "parent": comment["id"],
                    "revision": revision,
                    "text": "Forged harness failure",
                    "failure": "startup_failed",
                    "attempt": "forged-harness-failure",
                },
                {"Leaf-Layer": state["layer"]["generation"]},
            )
        assert forged.value.code == 400
        monkeypatch.setenv("LEAF_AGENT", "Agent")
        monkeypatch.setenv("LEAF_SESSION_ID", "leaf-website-agent")
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        appended, _ = post(
            f"{root}/examples/decision/_leaf/agent/fail",
            {"event": comment["id"], "failure": "startup_failed"},
        )
        reply = read_events(published)[-1]
        assert appended == {"status": "appended", "event": reply["id"]}
        assert reply == {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "session": "leaf-website-agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": website_server.FAILURE_RECEIPTS["startup_failed"],
            "failure": "startup_failed",
            "attempt": f"website-agent-{comment['id']}",
            "attention": False,
            "id": reply["id"],
            "ts": reply["ts"],
            "seq": reply["seq"],
        }
        served, _ = get(f"{root}/examples/decision/api/state")
        failures = [
            event for event in json.loads(served)["events"] if "failure" in event
        ]
        assert [event["id"] for event in failures] == [reply["id"]]
        assert journey.turn_failed(failures)
        assert journey.deployment_answer(failures, comment["id"]) is None
        repeated, _ = post(
            f"{root}/examples/decision/_leaf/agent/fail",
            {"event": comment["id"], "failure": "startup_failed"},
        )
        assert repeated == appended
        assert (
            len(
                [
                    event
                    for event in read_events(published)
                    if event.get("attempt") == f"website-agent-{comment['id']}"
                ]
            )
            == 1
        )

        with pytest.raises(urllib.error.HTTPError) as stopped:
            urllib.request.urlopen(f"{root}/examples/missing/")
        assert stopped.value.code == 404


def test_a_stale_layer_is_answered_with_the_generation_the_container_holds(
    page_dir, tmp_path
):
    """What a user posting into a draining rollout gets back.

    A container carries the layer of the image it runs, so a session allocated on a
    previous image answers a newer generation with its own rather than with state.
    The website deploy gate reads that answer, so it has to be the shape it names.
    """
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        state = json.loads(get(f"{root}/examples/decision/api/state")[0])
        before = read_events(published)
        answer, headers = post(
            f"{root}/examples/decision/api/event",
            {
                "kind": "comment",
                "revision": state["active"]["revision"],
                "text": "Posted under a layer this container does not speak.",
                "attempt": "stale-layer-01",
            },
            {"Leaf-Layer": "a-layer-from-another-release"},
        )
        generation = state["layer"]["generation"]
        assert answer == {"layer": generation}
        assert headers["Leaf-Layer"] == generation
        assert read_events(published) == before


def test_the_adapter_serves_a_published_revision_at_its_release_address(
    page_dir, tmp_path
):
    """A published revision's document loads its layer and runtime from the release
    (`_leaf-release/<release>/<page>`), which the Worker serves from the build's
    static tree. The adapter, with no Worker in front of it, serves the same bytes at
    the same addresses, so a published page starts there as it does at the edge."""
    publish(page_dir)
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    manifest_path = site / website_server.SITE_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    page = manifest["pages"]["/examples/decision"]
    page["states"] = {"1": "unused"}
    manifest_path.write_text(json.dumps(manifest))
    release = f"{page['assets']}/revisions/{revision_path(published, 1).stem}"
    # A revision a session saved after the release is the container's, never the
    # release's: no address under the release names it.
    (published / "index.html").write_text(
        (published / "index.html")
        .read_text()
        .replace("</main>", "<p>Private.</p></main>")
    )
    assert website_server.activate_source(published).revision == 2
    private = revision_path(published, 2)

    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHarness())
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        name = revision_path(published, 1).name
        document, _ = get(f"{root}/examples/decision/revisions/{name}")
        assert f'data-lf-entry="{release}/leaf.js"'.encode() in document
        current, _ = get(f"{root}/examples/decision/")
        assert (
            f'data-lf-entry="/examples/decision/revisions/{private.stem}/'.encode()
            in current
        )
        runtime = serving_runtime().resources({}, {})
        for logical in ("/leaf.js", "/runtime/widget-api.js"):
            body, headers = get(f"{root}{release}{logical}")
            assert body == runtime[logical].data, logical
            assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
            assert headers["Access-Control-Allow-Origin"] == "*"
        registry, headers = get(f"{root}{release}/registry.json")
        assert json.loads(registry)["$layer"] == load_registry(published)["$layer"]
        assert headers["Leaf-Release"] == manifest["release"]
        for missing in (
            f"{release}/api/state",
            f"{page['assets']}/revisions/r9-x/a.js",
            f"{page['assets']}/revisions/{private.name}",
            f"{page['assets']}/revisions/{private.stem}/leaf.js",
        ):
            with pytest.raises(urllib.error.HTTPError) as refused:
                get(f"{root}{missing}")
            assert refused.value.code == 404, missing


@pytest.mark.parametrize(
    ("page_root", "name"), [("", "index"), ("/examples", "examples")]
)
def test_a_product_route_uses_the_same_real_page_server(
    page_dir, tmp_path, page_root, name
):
    site = tmp_path / "site"
    published = site / "_leaf" / "pages" / name
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {page_root or "/": (f"_leaf/pages/{name}", "product")})

    agent_harness = FakeCodexHarness()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_harness)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        document, _ = get(f"{root}{page_root}/")
        assert b"data-lf-site" not in document
        assert b"data-lf-share-url" not in document
        served = revision_root(published, 1)
        assert f'data-lf-entry="{page_root}{served}/leaf.js"'.encode() in document
        state = json.loads(get(f"{root}{page_root}/api/state")[0])
        assert state["publication"] == {
            "kind": "product",
            "agent": "Agent",
            "install_url": "/#install",
        }
        posted = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "text": "Can the product-page agent read this?",
            "anchor": {"section": "plan"},
            "attempt": f"website-product-{name}",
        }
        answer, _ = post(
            f"{root}{page_root}/api/event",
            posted,
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        comment = next(
            event
            for event in answer["state"]["events"]
            if event.get("attempt") == posted["attempt"]
        )
        started, _ = post(
            f"{root}{page_root}/_leaf/agent/start", {"event": comment["id"]}
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_harness.attached == [published]
