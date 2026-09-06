"""The website route adapter preserves Leaf's canonical served-page contract."""

import importlib.util
import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from leaf.event_log import read_events
from leaf.hosting import server_at

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "website_server", ROOT / "worker" / "server.py"
)
website_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(website_server)


def get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(url) as response:
        return response.read(), dict(response.headers)


def post(url: str, body: dict, headers: dict | None = None) -> tuple[dict, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read()), dict(response.headers)


def test_the_website_label_follows_the_script_contract_not_its_formatting():
    document = (
        b'<!doctype html><html><head><script\n type="module" '
        b'src="/leaf.js"></script></head><body></body></html>'
    )
    injected = website_server.with_sitenote(document, "/examples/decision")
    assert injected.index(b"/examples/decision/sitenote.js") < injected.index(
        b'src="/leaf.js"'
    )


def test_a_website_example_uses_the_real_page_server(page_dir, tmp_path, monkeypatch):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("document.body.dataset.site = 'example';\n")

    httpd = server_at(
        "127.0.0.1",
        0,
        website_server.handler_for(site / "examples"),
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert get(f"{root}/health")[0] == b"ok\n"

        document, headers = get(f"{root}/examples/decision/")
        assert b'src="/examples/decision/sitenote.js"' in document
        assert b'data-lf-entry="/examples/decision/leaf.js"' in document
        assert headers["Content-Security-Policy"] == "frame-ancestors 'none'"

        raw_state, headers = get(f"{root}/examples/decision/api/state")
        state = json.loads(raw_state)
        assert state["example"] == {
            "agent": "Leaf guide",
            "install_url": "/#install",
        }
        assert headers["Leaf-Layer"] == state["layer"]["generation"]

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
            obligation["event"]
            for obligation in answer["state"]["activity"]["obligations"]
        }

        captured = []
        monkeypatch.setattr(
            website_server,
            "generate_example_reply",
            lambda turn: captured.append(turn) or "This is the agent's answer.",
        )
        generated, _ = post(
            f"{root}/examples/decision/_leaf/agent/generate",
            {"event": comment["id"]},
        )
        assert generated == {"status": "ready", "text": "This is the agent's answer."}
        assert captured[0]["reply_to"] == comment["id"]
        assert captured[0]["conversation"]["messages"][-1]["text"] == posted["text"]
        assert "Plan" in captured[0]["page"]["visible_text"]

        monkeypatch.setenv("LEAF_AGENT", "Leaf guide")
        monkeypatch.setenv("LEAF_SESSION_ID", "leaf-website-agent")
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        appended, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "text": generated["text"]},
        )
        reply = read_events(published)[-1]
        assert appended == {"status": "appended", "event": reply["id"]}
        assert reply == {
            "kind": "reply",
            "author": "claude",
            "agent": "Leaf guide",
            "session": "leaf-website-agent",
            "parent": comment["id"],
            "text": "This is the agent's answer.",
            "attempt": f"website-agent-{comment['id']}",
            "id": reply["id"],
            "ts": reply["ts"],
            "seq": reply["seq"],
        }
        repeated, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "text": generated["text"]},
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

        assert get(f"{root}/examples/decision/sitenote.js")[0].startswith(
            b"document.body"
        )
        with pytest.raises(urllib.error.HTTPError) as stopped:
            urllib.request.urlopen(f"{root}/examples/missing/")
        assert stopped.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_an_agent_reply_is_dropped_when_a_newer_reader_turn_overtakes_it(
    page_dir, tmp_path
):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site / "examples"))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}/examples/decision"
    try:
        state = json.loads(get(f"{root}/api/state")[0])
        headers = {"Leaf-Layer": state["layer"]["generation"]}
        post(
            f"{root}/api/event",
            {
                "kind": "comment",
                "revision": state["active"]["revision"],
                "text": "First question",
                "attempt": "first-question-01",
            },
            headers,
        )
        first = read_events(published)[-1]
        post(
            f"{root}/api/event",
            {
                "kind": "reply",
                "parent": first["id"],
                "revision": state["active"]["revision"],
                "text": "A more specific follow-up",
                "attempt": "second-question-1",
            },
            headers,
        )

        answer, _ = post(
            f"{root}/_leaf/agent/reply",
            {"event": first["id"], "text": "Now stale"},
        )

        assert answer == {"status": "settled"}
        assert all(event.get("text") != "Now stale" for event in read_events(published))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
