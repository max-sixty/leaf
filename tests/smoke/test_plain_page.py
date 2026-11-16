"""Display widgets on a plain HTML page, which runs none of Leaf's runtime (#3833).

The page maps Leaf's rooted module paths to a Leaf install with an import map of its
own, as a Leaf page does (`layer_import_map`), links the layer's portable.css for the
widgets' look, and gives each widget a block, as any page does for an element it lays
out. Nothing there draws a widget before the first paint, as Leaf's delivery does, so
the page hides each widget until its module defines it, as a page may any custom
element it upgrades, and reserves the room of one that draws later than its upgrade.
Its widgets stand two to a row, aligned at their tops, so one growing as it draws moves
no other: those that draw at upgrade, in the last row, grow once their modules define
them. The install is what Leaf serves its own pages: this tree's runtime, the compiled
kernel where it is current, beside the composed layer's sheets, widgets and vendor
modules. A widget that imports only the portable helpers (`runtime/portable-api.js`)
defines itself, draws in the theme's look, and shows a body it cannot draw as an error
box and an `error` event the host may hear, with nothing in the console, while the
host's own markup keeps the look the host gave it. What Leaf adds to a widget it reads
off the widget, so here there is none of it: no widget key bound or advertised, no
Copy control, no quiet word. Its own buttons still work, and so do its spans offered
as buttons, by Enter and Space too.

It is a landing gate because nothing else would see the guarantee break: every other
test runs a widget on a Leaf page, where an import of a module that reads what Leaf
composes into a page loads as well as any other.
"""

import http.server
import json
import time
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

import pytest
from interact_support import running_http_server
from playwright.sync_api import expect
from render_harness import consume_browser_errors, leaf_page, open_page

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
        "pre:has(> .lf-code-line[data-lf-hi] [data-lf-syn])",
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
        # Its named boxes, and its `accTitle` as its name with no `<title>`, which the
        # browser would show as a tooltip over the whole drawing.
        'svg[aria-label="Checkout"]:not(:has(> title))'
        ':has(g.pele-node[data-id="Cart"]):has(g.pele-node[data-id="Pay"])',
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
# Two widgets to a row, aligned at their tops, so one growing as it draws moves no other.
GRID = (
    "display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));"
    " align-items: start; gap: 16px;"
)
# The host's own markup beside the widgets, a row of its own above them so their drawing
# moves none of it, which portable.css leaves as the host drew it: none of its rules
# reaches past the widgets, so a host's `data-room`, a Leaf page's attribute idiom, and
# its own `.button`, `.choice` and `.field`, names Leaf styles nowhere, keep the host's
# look.
HOST = (
    '<section id="host" style="grid-column: 1 / -1"><p>Words</p><button>Press</button>'
    '<button class="button">Go</button><a class="button" href="#host">Link</a>'
    '<label class="choice"><input type="checkbox"> Pick</label>'
    '<input class="field" value="typed">'
    '<span data-room="longer words"><span>short</span></span>'
    "<details><summary>More</summary></details><pre>code</pre>"
    "<select><option>One</option></select>"
    '<svg width="20" height="20" viewBox="0 0 10 10"></svg></section>'
)
# The faces the readings compare: what an element looks like, and its size.
FACE = (
    "background-color",
    "background-image",
    "block-size",
    "border-block-start-color",
    "border-block-start-style",
    "border-block-start-width",
    "border-inline-start-color",
    "border-inline-start-style",
    "border-inline-start-width",
    "border-start-start-radius",
    "box-shadow",
    "color",
    "cursor",
    "display",
    "fill",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "gap",
    "inline-size",
    "letter-spacing",
    "line-height",
    "list-style-type",
    "margin-block-start",
    "margin-inline-start",
    "opacity",
    "outline-style",
    "padding-block-start",
    "padding-inline-start",
    "stroke",
    "text-align",
    "text-decoration-line",
    "visibility",
    "white-space",
)
# Every element below each widget's root, keyed by its path of tags and classes, with
# its faces. Leaf adds parts of its own to a widget, such as a Copy control, which the
# host lacks and the comparison skips by key.
FACES_BELOW = """([ids, names]) => Object.fromEntries(ids.map(id => {
  const root = document.getElementById(id), faces = {};
  const visit = (node, path) => {
    const seen = {};
    for (const child of node.children) {
      const sign = child.localName + [...child.classList].filter(c => c.startsWith("lf-"))
        .sort().map(c => "." + c).join("");
      const key = `${path}/${sign}:${seen[sign] = (seen[sign] ?? 0) + 1}`;
      const style = getComputedStyle(child);
      faces[key] = Object.fromEntries(names.map(name => [name, style.getPropertyValue(name)]));
      visit(child, key);
    }
  };
  visit(root, "");
  return [id, faces];
}))"""
# What each widget's root inherits from the page around it, the same on both pages.
STAGE = (
    "inline-size: 860px; font: 16px/1.5 Georgia, serif; color: rgb(28, 27, 24);"
    " --lf-ground: rgb(250, 249, 245)"
)


def install(*packages: str) -> Mapping[str, Resource]:
    """What Leaf serves a page of these widgets' packages, by rooted path: the layer
    they compose and the runtime beside it."""
    layer = compose_layer(
        layer_inputs(
            tuple(sorted({widget.package for widget in PORTABLE} | set(packages)))
        )
    )
    files = {
        f"/{sub}/{name}": Resource(data, resource_type(name))
        for sub in BROWSER_DIRS
        for name, data in layer.directory_files[sub].items()
    } | {
        f"/{name}": Resource(data, resource_type(name))
        for name, data in layer.top_files.items()
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
<link rel="stylesheet" href="{ROOT}/portable.css">
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
<style>main {{ {GRID} }}
{tags} {{ display: flow-root; }}
:is({tags}):not(:defined) {{ visibility: hidden; }}</style>
<script>
  window.heard = [];
  addEventListener("error", (event) => heard.push({{
    target: event.target.id, message: event.error?.message ?? null,
  }}));
</script>
<script type="module">{imports}</script>
</head><body><main>{HOST}{sections}</main></body></html>"""


@contextmanager
def host_page(markup: str, resources: Mapping[str, Resource]):
    """Serve ordinary host markup beside the install, without Leaf delivery."""
    page_bytes = markup.encode()

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

        def log_message(self, format, *_):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Host)
    with running_http_server(httpd):
        yield f"http://127.0.0.1:{httpd.server_port}/"


def test_a_display_widget_draws_on_a_page_without_leaf(browser, subtests):
    with host_page(plain_page(), install()) as url:
        page = browser.new_page(viewport={"width": 900, "height": 1200})
        console = []
        page.on(
            "console", lambda message: console.append(f"{message.type}: {message.text}")
        )
        page.goto(url)
        assert page.evaluate("() => !window.lfRootState"), (
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
        # A step row is a span, so its words stay selectable, with a button's role:
        # Enter and Space press it as they do a button, with no key of Leaf's.
        rows = page.locator("#lf-timeline .lf-timeline-step")
        rows.first.focus()
        page.keyboard.press("Enter")
        expect(current).to_contain_text("Compile")
        page.keyboard.press("Tab")
        expect(rows.nth(1)).to_be_focused()
        page.keyboard.press("Space")
        expect(current).to_contain_text("Artifact ready")
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

        # The stylesheet styles nothing of the host's own markup: read without it, in
        # the same task, so nothing paints between, no element of the host's changes.
        linked, bare = page.evaluate(
            f"""parts => lfUnwatched(() => {{
              const read = {FACES_BELOW};
              const sheet = document.querySelector('link[rel="stylesheet"]').sheet;
              const linked = read(parts);
              sheet.disabled = true;
              const bare = read(parts);
              sheet.disabled = false;
              return [linked, bare];
            }})""",
            [["host"], list(FACE)],
        )
        assert len(linked["host"]) == HOST.count("<") - HOST.count("</") - 1, linked
        changed = {
            key: {
                name: (faces[name], bare["host"][key][name])
                for name in FACE
                if faces[name] != bare["host"][key][name]
            }
            for key, faces in linked["host"].items()
        }
        assert not any(changed.values()), changed


def test_a_host_draws_each_widget_as_a_leaf_page_does(browser, serve):
    """With portable.css linked, every element below a widget's root takes the faces it
    takes on a Leaf page that takes no theme, given the same markup and the same text
    and ground inherited at the root. Leaf's faces stand nested under the layer's tags
    there, so this holds that they still reach every part below the root and still rank
    below a package's rule of equal weight, as on a Leaf page. The parts only Leaf adds,
    such as a Copy control and a quiet word, the comparison skips by key."""
    ids = {"refused": "refused"} | {w.tag: w.tag.replace("lf-", "w-") for w in PORTABLE}
    sections = [REFUSED, *(widget.markup for widget in PORTABLE)]
    markup = "".join(f"<section>{part}</section>" for part in sections)
    leaf = open_page(
        browser,
        serve(
            leaf_page(
                "Parity",
                f'<div class="stage" style="{STAGE}">'
                + markup.replace('id="lf-', 'id="w-')
                + "</div>",
                head=f"<style>.stage {{ {GRID} }}</style>",
                layout=None,
            ),
            packages=tuple(sorted({w.package for w in PORTABLE} - {"default"})),
            theme=False,
        ),
    )
    for widget in PORTABLE:
        expect(leaf.locator(f"#{ids[widget.tag]} {widget.drawn}")).to_be_visible()
    expect(leaf.locator("#refused .lf-error")).to_be_visible()
    on_leaf = leaf.evaluate(FACES_BELOW, [list(ids.values()), list(FACE)])
    consume_browser_errors(leaf, '<lf-chart id="refused"> failed')
    with host_page(
        plain_page().replace("<main>", f'<main style="{STAGE}">'), install()
    ) as url:
        page = browser.new_page(viewport={"width": 1280, "height": 1200})
        page.goto(url)
        for widget in PORTABLE:
            expect(page.locator(f"#{widget.tag} {widget.drawn}")).to_be_visible()
        hosted = page.evaluate(FACES_BELOW, [list(ids), list(FACE)])
    differ = {}
    for host_id, leaf_id in ids.items():
        here, there = hosted[host_id], on_leaf[leaf_id]
        assert here and not here.keys() - there.keys(), (host_id, here.keys() - there)
        for key, faces in here.items():
            for name in FACE:
                if faces[name] != there[key][name]:
                    differ.setdefault(f"#{host_id} {key}", {})[name] = (
                        there[key][name],
                        faces[name],
                    )
    assert not differ, json.dumps(differ, indent=1)


def test_a_host_sets_a_diff_value_and_reads_its_drawn_marks(browser):
    """A host owns the value; drawn hands it the marks of that exact drawing."""

    def patch(path, word):
        return (
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n+++ b/{path}\n"
            f"@@ -1 +1 @@\n-old\n+{word}\n"
        )

    first = patch("first.txt", "first value")
    second = patch("second.txt", "second value")
    markup = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Host-owned diff</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
</head><body><button id="show-both">Show both files</button><lf-diff id="diff"></lf-diff>
<script type="module">
const diff = document.querySelector("lf-diff");
window.drawings = [];
// Read synchronously: the marks must stand when the widget reports its drawing.
diff.addEventListener("drawn", event => drawings.push({{
  value: event.detail.value,
  marks: [...diff.shadowRoot.querySelectorAll("[data-lf-datum]")].map(node => ({{
    key: node.dataset.lfDatum, text: node.textContent,
  }})),
}}));
try {{
  await import("/widgets/lf-diff.js");
  diff.value = {json.dumps(first)};
  document.querySelector("#show-both").onclick = () => {{
    diff.value = {json.dumps(first + second)};
  }};
}} catch (error) {{
  document.querySelector("#failure").textContent = error.stack;
}} finally {{
  window.hostReady = true;
}}
</script><pre id="failure"></pre></body></html>"""
    with host_page(markup, install("diff")) as url:
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("window.hostReady")
        assert page.locator("#failure").inner_text() == ""
        expect(page.locator("#diff .lf-diff-file")).to_be_visible()
        page.wait_for_function(
            "value => drawings.some(drawing => drawing.value === value)", arg=first
        )
        drawn = page.evaluate("drawings.at(-1)")
        assert drawn["value"] == first
        assert drawn["marks"], drawn
        expect(
            page.get_by_role("button", name="Comment on", exact=False)
        ).to_have_count(0)
        expect(page.locator("#diff .lf-diff-line-number").first).to_have_text("1")
        assert any("first value" in mark["text"] for mark in drawn["marks"])
        first_keys = {mark["key"] for mark in drawn["marks"]}

        page.evaluate(
            "value => { document.querySelector('#diff').value = value; }", second
        )
        page.wait_for_function(
            "value => drawings.some(drawing => drawing.value === value)", arg=second
        )
        drawn = page.evaluate("drawings.at(-1)")
        assert drawn["value"] == second
        assert drawn["marks"], drawn
        expect(
            page.get_by_role("button", name="Comment on", exact=False)
        ).to_have_count(0)
        expect(page.locator("#diff .lf-diff-line-number").first).to_have_text("1")
        assert any("second value" in mark["text"] for mark in drawn["marks"])
        assert first_keys.isdisjoint(mark["key"] for mark in drawn["marks"])
        assert all("first value" not in mark["text"] for mark in drawn["marks"])
        # The same portable input/focus helpers let a reader filter the host's value
        # and retain their search while a matching file's drawing is replaced.
        page.get_by_role("button", name="Show both files").click()
        search = page.get_by_role("searchbox", name="Filter diff files")
        search.fill("second")
        expect(page.locator("#diff .lf-diff-file:visible")).to_have_count(1)
        expect(page.locator("#diff .lf-diff-file:visible")).to_contain_text(
            "second.txt"
        )
        replacement = first + patch("second.txt", "updated value")
        page.evaluate(
            "value => { document.querySelector('#diff').value = value; }", replacement
        )
        expect(page.locator("#diff .lf-diff-file:visible")).to_contain_text(
            "updated value"
        )
        expect(search).to_be_focused()
        expect(search).to_have_value("second")
        assert page.evaluate(
            "!window.lfRootState && !window.lfDocumentLifetime && !window.lfViews"
        )


def test_a_host_builds_named_controls_without_leaf(browser):
    """Control construction and generated labels need no page services."""
    markup = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Host controls</title>
<style>svg {{ width: 1em; height: 1em; }}</style>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
</head><body><main></main><pre id="failure"></pre>
<script type="module">
try {{
  const {{offer, nameAction, generatedElement, keepsText, searchField}} =
    await import("/runtime/portable-api.js");
  await import("/vendor/webawesome.esm.js");
  const button = offer("button");
  nameAction(button, "close", {{label: "Close evidence"}});
  const label = offer("span");
  generatedElement(label, {{says: "echo"}});
  keepsText(label, "Evidence");
  const search = searchField("host-search", {{name: "files", label: "Find files"}});
  document.querySelector("main").append(button, label, search);
}} catch (error) {{ document.querySelector("#failure").textContent = error.stack; }}
finally {{ window.hostReady = true; }}
</script></body></html>"""
    with host_page(markup, install()) as url:
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("window.hostReady")
        assert page.locator("#failure").inner_text() == ""
        button = page.get_by_role("button", name="Close evidence")
        expect(button.locator("svg")).to_be_visible()
        expect(button).to_have_attribute("title", "Close evidence")
        expect(page.locator("span[data-lf-echo]")).to_have_text("Evidence")
        search = page.get_by_role("searchbox", name="Find files")
        search.fill("patch")
        expect(search).to_have_value("patch")
        button.focus()
        page.keyboard.press("Tab")
        expect(search).to_be_focused()
        assert page.evaluate(
            "!window.lfRootState && !window.lfDocumentLifetime && !window.lfViews"
        )
