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
_previews_spec = importlib.util.spec_from_file_location(
    "example_previews", ROOT / "scripts" / "example-previews.py"
)
example_previews = importlib.util.module_from_spec(_previews_spec)
_previews_spec.loader.exec_module(example_previews)


def get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(url) as response:
        return response.read(), dict(response.headers)


def test_the_website_label_follows_the_script_contract_not_its_formatting():
    document = (
        b'<!doctype html><html><head><script\n type="module" '
        b'src="/leaf.js"></script></head><body></body></html>'
    )
    injected = website_server.with_sitenote(document, "/examples/decision")
    assert injected.index(b"/examples/decision/sitenote.js") < injected.index(
        b'src="/leaf.js"'
    )


def test_a_website_example_uses_the_real_page_server(page_dir, tmp_path):
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
        assert state["example"] == {"install_url": "/#install"}
        assert headers["Leaf-Layer"] == state["layer"]["generation"]

        posted = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "text": "This came through the public example.",
            "anchor": {"section": "plan"},
        }
        request = urllib.request.Request(
            f"{root}/examples/decision/api/event",
            data=json.dumps(posted).encode(),
            headers={
                "Content-Type": "application/json",
                "Leaf-Layer": state["layer"]["generation"],
            },
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
        assert read_events(published)[-1]["text"] == posted["text"]

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


def test_the_preview_generator_uses_the_live_website_route(page_dir, tmp_path):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("document.body.dataset.site = 'example';\n")

    with example_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/decision/api/state")[0])

    assert state["example"] == {"install_url": "/#install"}
