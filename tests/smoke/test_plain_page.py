"""Display widgets on a plain HTML page, which runs none of Leaf's runtime (#3833).

The page maps Leaf's rooted module paths to a Leaf install with an import map of its
own, as a Leaf page does (`layer_import_map`), and gives each widget a block, as any
page does for an element it lays out. The install is what Leaf serves its own pages:
this tree's runtime, the compiled kernel where it is current, beside the composed
layer's widgets and vendor modules. A widget that imports only the portable helpers
(`runtime/portable-api.js`) defines itself, draws, and shows a body it cannot draw as
an error box and an `error` event the host may hear, with nothing in the console.

It is a landing gate because nothing else would see the guarantee break: every other
test runs a widget on a Leaf page, where an import of a module that reads what Leaf
composes into a page loads as well as any other.
"""

import http.server
import json
from dataclasses import dataclass

import pytest
from interact_support import running_http_server
from playwright.sync_api import expect

from leaf.layer import compose_layer, layer_inputs
from leaf.revision_artifact import Resource, resource_type
from leaf.revision_delivery import layer_import_map
from leaf.runtime_selection import read_runtime
from leaf.schema import BROWSER_DIRS


@dataclass(frozen=True)
class Portable:
    """A widget that loads and draws with no Leaf runtime: the bundled package that
    ships it, one authored occurrence that draws, and what it draws, inside it."""

    tag: str
    package: str
    markup: str
    drawn: str


PORTABLE = [
    Portable(
        "lf-chart",
        "default",
        '<lf-chart id="lf-chart" data-lf-height="240"><pre>\n{\n'
        '  ariaLabel: "Merged by team: backend 12, frontend 19",\n'
        '  marks: [Plot.barY([{team: "backend", n: 12}, {team: "frontend", n: 19}],'
        ' {x: "team", y: "n"})],\n}\n</pre></lf-chart>',
        "svg[role=img]",
    ),
]

# A body the chart cannot draw: the box and the event are the shared upgrade
# lifecycle's (`failSoft`), so one widget answers for every portable one.
REFUSED = (
    '<lf-chart id="refused" data-lf-height="120"><pre>\n{ marks: [ }\n</pre></lf-chart>'
)
ROOT = "/leaf"


def install() -> dict[str, Resource]:
    """What Leaf serves a page of these widgets' packages, by rooted path: the layer
    they compose and the runtime beside it."""
    layer = compose_layer(
        layer_inputs(tuple(sorted({widget.package for widget in PORTABLE})))
    )
    captured = {
        f"/{sub}/{name}": Resource(data, resource_type(name))
        for sub in BROWSER_DIRS
        for name, data in layer.directory_files[sub].items()
    }
    return read_runtime().resources(captured)


def plain_page() -> str:
    imports = "".join(f'import "/widgets/{widget.tag}.js";\n' for widget in PORTABLE)
    tags = ", ".join(sorted({widget.tag for widget in PORTABLE}))
    sections = "".join(
        f"<section>{markup}</section>"
        for markup in [*(widget.markup for widget in PORTABLE), REFUSED]
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Plain page</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
<style>{tags} {{ display: block; }}</style>
<script>
  window.heard = [];
  addEventListener("error", (event) => heard.push({{
    target: event.target.id, message: event.error?.message ?? null,
  }}));
</script>
<script type="module">{imports}</script>
</head><body><main>{sections}</main></body></html>"""


def test_a_display_widget_draws_on_a_page_without_leaf(browser, subtests):
    resources = install()
    page_bytes = plain_page().encode()

    class Host(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            found = (
                Resource(page_bytes, "text/html")
                if path == "/"
                else resources.get(path.removeprefix(ROOT))
                if path.startswith(f"{ROOT}/")
                else None
            )
            if found is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", found.mime)
            self.send_header("Content-Length", str(len(found.data)))
            self.end_headers()
            self.wfile.write(found.data)

        def log_message(self, *_):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Host)
    with running_http_server(httpd):
        page = browser.new_page(viewport={"width": 900, "height": 1200})
        console = []
        page.on(
            "console", lambda message: console.append(f"{message.type}: {message.text}")
        )
        page.goto(f"http://127.0.0.1:{httpd.server_port}/")
        assert page.evaluate("() => !document.documentElement.lfInitial"), (
            "the page must run none of Leaf's runtime"
        )
        for widget in PORTABLE:
            with subtests.test(widget=widget.tag):
                drawn = page.locator(f"#{widget.tag} {widget.drawn}")
                expect(drawn).to_be_visible()
                box = drawn.bounding_box()
                room = page.locator(f"#{widget.tag}").bounding_box()
                # Drawn for the room the host gave it, not at a size of its own.
                assert box["width"] == pytest.approx(room["width"], abs=1), (box, room)
                assert box["height"] > 0, box

        refusal = page.locator("#refused .lf-error")
        expect(refusal).to_contain_text("<lf-chart> failed: Unexpected token")
        expect(refusal.locator("pre")).to_have_text("{ marks: [ }")
        heard = page.evaluate("heard")
        assert [event["target"] for event in heard] == ["refused"], heard
        assert "Unexpected token" in heard[0]["message"], heard
        # The refusal is the page's to show, and nothing of it, or of any widget,
        # reaches the console of a page that runs no Leaf.
        assert console == [], console
