"""Display widgets on a plain HTML page, which runs none of Leaf's runtime (#3833).

The page maps Leaf's rooted module paths to a Leaf install with an import map of its
own, as a Leaf page does (`layer_import_map`), and gives each widget a block, as any
page does for an element it lays out. Nothing there draws a widget before the first
paint, as Leaf's delivery does, so the page hides each widget until its module defines
it, as a page may any custom element it upgrades, and reserves the room of one that
draws later than its upgrade. Its widgets stand two to a row, aligned at their tops, so
one growing as it draws moves no other: those that draw at upgrade, in the last row,
grow once their modules define them. It holds the motion study's clock, whose words
change as it plays, to one width, as the package's stylesheet does. The install is what Leaf
serves its own pages: this tree's runtime, the compiled kernel where it is current,
beside the composed layer's widgets and vendor modules. A widget that imports only the portable helpers
(`runtime/portable-api.js`) defines itself, draws, and shows a body it cannot draw as
an error box and an `error` event the host may hear, with nothing in the console. What
Leaf adds to a widget it reads off the widget, so here there is none of it: no key
bound or advertised, no Copy control, no quiet word. Its own buttons still work.

It is a landing gate because nothing else would see the guarantee break: every other
test runs a widget on a Leaf page, where an import of a module that reads what Leaf
composes into a page loads as well as any other.
"""

import http.server
import json
import time
from dataclasses import dataclass
from typing import Literal

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
    ships it, one authored occurrence that draws, what it draws, inside it, and which of
    the drawing's sides the host's box sets: both, as a chart's are; its width, as a
    code block's is; or neither, as a diagram keeps its natural size."""

    tag: str
    package: str
    markup: str
    drawn: str
    sized: Literal["box", "width", "natural"]


PORTABLE = [
    Portable(
        "lf-chart",
        "default",
        # The host holds the chart's box, as Leaf's stylesheet does from the height it
        # states, so the drawing arriving moves nothing below it.
        '<lf-chart id="lf-chart" style="height: 240px"><pre>\n{\n'
        '  ariaLabel: "Merged by team: backend 12, frontend 19",\n'
        '  marks: [Plot.barY([{team: "backend", n: 12}, {team: "frontend", n: 19}],'
        ' {x: "team", y: "n"})],\n}\n</pre></lf-chart>',
        "svg[role=img]",
        sized="box",
    ),
    Portable(
        "lf-code",
        "default",
        '<lf-code id="lf-code" language="python" hi="2"><pre>\ndef bracket(temp):\n'
        '    if temp &lt; 0:\n        return "steel"\n</pre></lf-code>',
        # Its lines, coloured, the highlighted one among them.
        "pre:has(> .lf-code-line.hi [data-lf-syn])",
        sized="width",
    ),
    Portable(
        "lf-diagram",
        "diagram",
        # The host reserves the diagram's room, as Leaf's stylesheet does from the
        # height an occurrence states, so the drawing arriving moves nothing below it.
        '<lf-diagram id="lf-diagram" parts="all" style="height: 240px"><pre>\n'
        "flowchart TD\n"
        "  accTitle: Checkout\n  accDescr: A cart reaches payment.\n"
        "  Cart([Cart]) --&gt; Pay{Paid?}\n</pre></lf-diagram>",
        # Its named boxes.
        'svg:has(g.pele-node[data-id="Cart"]):has(g.pele-node[data-id="Pay"])',
        sized="natural",
    ),
    Portable(
        "lf-timeline",
        "timeline",
        '<lf-timeline id="lf-timeline" aria-label="Deploy order">'
        '<lf-lane label="Build"><lf-event id="compile" at="0" end="4000" '
        'label="Compile"></lf-event><lf-event id="artifact" at="4000" '
        'label="Artifact ready"></lf-event></lf-lane></lf-timeline>',
        # Its transport, its symbols drawn, and a row per step.
        ".lf-timeline-view:has(.lf-timeline-next > svg[data-lf-icon])"
        ":has(.lf-timeline-steps > li:nth-child(2))",
        sized="width",
    ),
    Portable(
        "lf-motion",
        "motion",
        '<lf-motion id="lf-motion" duration="300" aria-label="Travel study">'
        '<figure><svg viewBox="0 0 300 60"></svg></figure></lf-motion>',
        ".lf-motion-controls:has(.lf-motion-play > svg[data-lf-icon])"
        ":has(input[type=range])",
        sized="width",
    ),
]

# A body the chart cannot draw: the box and the event are the shared upgrade
# lifecycle's (`failSoft`), so one widget answers for every portable one.
REFUSED = '<lf-chart id="refused"><pre>\n{ marks: [ }\n</pre></lf-chart>'
ROOT = "/leaf"


def install() -> dict[str, Resource]:
    """What Leaf serves a page of these widgets' packages, by rooted path: the layer
    they compose and the runtime beside it."""
    layer = compose_layer(
        layer_inputs(tuple(sorted({widget.package for widget in PORTABLE})))
    )
    files = {
        f"/{sub}/{name}": Resource(data, resource_type(name))
        for sub in BROWSER_DIRS
        for name, data in layer.directory_files[sub].items()
    }
    return read_runtime().resources(files, {})


def plain_page() -> str:
    imports = "".join(f'import "/widgets/{widget.tag}.js";\n' for widget in PORTABLE)
    tags = ", ".join(sorted({widget.tag for widget in PORTABLE}))
    sections = "".join(
        f"<section>{markup}</section>"
        for markup in [REFUSED, *(widget.markup for widget in PORTABLE)]
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Plain page</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
<style>main {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start; gap: 16px; }}
{tags} {{ display: flow-root; }}
:is({tags}):not(:defined) {{ visibility: hidden; }}
.lf-motion-clock {{ display: inline-block; inline-size: 9ch; }}</style>
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
            # A drawing module a widget fetches only off Leaf arrives after the page has
            # painted, as on a slow network, so the widgets that draw at upgrade grow
            # under the shift watch.
            if path.endswith("-view.js"):
                time.sleep(0.5)
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
                assert box["width"] > 0 and box["height"] > 0, box
                # Drawn for the room the host gave it, or at its own size inside it.
                if widget.sized == "natural":
                    assert box["width"] <= room["width"], (box, room)
                    assert box["height"] <= room["height"], (box, room)
                else:
                    assert box["width"] == pytest.approx(room["width"], abs=1), (
                        box,
                        room,
                    )
                if widget.sized == "box":
                    assert box["height"] == pytest.approx(room["height"], abs=1), (
                        box,
                        room,
                    )
        # A widget's own buttons work without Leaf: Next steps the timeline, and Play
        # runs the study's clock to its end, drawing each frame.
        current = page.locator("#lf-timeline [aria-current=step]")
        page.locator("#lf-timeline .lf-timeline-next").click()
        expect(current).to_contain_text("Artifact ready")
        # Previous and Next are native buttons: Tab reaches each, and Enter and Space
        # press them, with no key of Leaf's.
        previous = page.locator("#lf-timeline .lf-timeline-previous")
        previous.focus()
        page.keyboard.press("Enter")
        expect(current).to_contain_text("Compile")
        page.keyboard.press("Tab")
        expect(page.locator("#lf-timeline .lf-timeline-next")).to_be_focused()
        page.keyboard.press("Space")
        expect(current).to_contain_text("Artifact ready")
        page.keyboard.press("Shift+Tab")
        expect(previous).to_be_focused()
        page.evaluate(
            """() => { window.drawnAt = [];
            document.querySelector("#lf-motion").renderFrame = (t) => drawnAt.push(t); }"""
        )
        page.locator("#lf-motion .lf-motion-play").click()
        expect(page.locator("#lf-motion .lf-motion-clock")).to_have_text("300 ms")
        assert page.evaluate("drawnAt.at(-1)") == 300
        # Leaf binds a widget's keys, adds its Copy control and writes its quiet words
        # from declarations only Leaf reads.
        assert (
            page.locator("[aria-keyshortcuts], .lf-code-copy, .lf-quiet").count() == 0
        )

        refusal = page.locator("#refused .lf-error")
        expect(refusal).to_contain_text("<lf-chart> failed: Unexpected token")
        expect(refusal.locator("pre")).to_have_text("{ marks: [ }")
        heard = page.evaluate("heard")
        assert [event["target"] for event in heard] == ["refused"], heard
        assert "Unexpected token" in heard[0]["message"], heard
        # The refusal is the page's to show, and nothing of it, or of any widget,
        # reaches the console of a page that runs no Leaf.
        assert console == [], console
