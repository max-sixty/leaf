"""Initial drawings stay coherent when HTML arrives across separate parser tasks."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event

import pytest
from interact_support import running_http_server
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import displayed, leaf_page, open_page

from leaf.layer import stylesheet
from leaf.render_checks import wait_until_ready
from leaf.render_gate.scheme import collect_page_exceptions
from leaf.revision_artifact import Resource
from leaf.revision_delivery import Delivery, compose_document


def test_initial_lit_drawings_keep_the_readers_nodes_through_upgrade(browser, serve):
    """Initial and live drawing share nodes, including restored activity rows.

    Generated controls stay hidden until upgrade. The reader can already focus an
    authored link; upgrade must retain that place and adopt the initial drawing,
    after which both the native disclosure and the activity control work. Pending
    package frames keep their first boxes; the tally starts with no count or available
    action. Empty tree and editor frames need no initial nodes, and the recording's
    waiting line is reserved by CSS before its live template owns the message.
    """
    url = live_url(
        serve(
            leaf_page(
                "Early drawings",
                '<h1>Report</h1><p><a id="early-link" href="#evidence">Read the evidence</a></p>'
                '<lf-toc id="contents" open></lf-toc>'
                '<section id="evidence"><h2>Evidence</h2><p>Read the counts.</p>'
                '</section><lf-activity id="feed"></lf-activity>'
                '<p><lf-tally id="left" for="queue" next></lf-tally></p>'
                '<section id="queue"><lf-ask id="decision"><h2>Ship it?</h2>'
                '<lf-options id="choice" choose><lf-option id="yes">Ship it</lf-option>'
                "</lf-options></lf-ask></section>"
                '<lf-file-tree id="files" source="files"></lf-file-tree>'
                '<lf-file-editor id="editor" binding="notes"></lf-file-editor>'
                '<lf-trace id="recording" source="recording">'
                f'<lf-trace-bookmark target="trace-{"0" * 64}-image-result" '
                'label="Authored result" key="result"></lf-trace-bookmark></lf-trace>',
            ),
            packages=("file-tree", "file-editor", "playwright"),
        )
    )
    context = browser.new_context(viewport={"width": 740, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator("#feed .lf-activity-news").click()
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    boot = []
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.reload(wait_until="commit")
        displayed(page)
        expect(page.locator("#feed .lf-activity-row")).to_be_visible()
        expect(page.locator("#feed .lf-activity-news")).to_have_attribute(
            "aria-expanded", "true"
        )
        expect(page.locator("#left .lf-tally-words")).to_have_text("")
        expect(page.locator("#left .lf-tally-next")).to_be_disabled()
        assert (
            page.locator("#left .lf-tally-face").evaluate(
                "node => getComputedStyle(node).visibility"
            )
            == "hidden"
        )
        # Static pending frames need no parser-owned nodes or rendering lifecycle.
        expect(page.locator("#files > *, #editor > *")).to_have_count(0)
        expect(page.locator("#recording .lf-trace-waiting")).to_have_count(0)
        boxes = {
            name: page.locator(f"#{name}").bounding_box()
            for name in ("left", "files", "editor", "recording")
        }
        page.keyboard.press("Tab")
        expect(page.locator("#early-link")).to_be_focused()
        early = page.evaluate_handle(
            "[...document.querySelectorAll('#contents *, #feed *, #left *, #files *, #recording *')]"
        )
        assert boot, "the runtime must remain held while the reader acts"
        boot.pop().continue_()
        page.unroute("**/leaf.js")
        wait_until_ready(page)
        assert page.evaluate("nodes => nodes.every(node => node.isConnected)", early)
        assert page.locator("#files .lf-file-tree-empty").evaluate(
            "node => node.getRootNode() === document.getElementById('files').shadowRoot"
        )
        expect(page.locator("#left .lf-tally-words")).to_have_text("1 left to answer")
        expect(page.locator("#left .lf-tally-next")).to_be_enabled()
        expect(page.locator("#editor .cm-editor")).to_be_visible()
        for name, before in boxes.items():
            after = page.locator(f"#{name}").bounding_box()
            assert all(abs(after[key] - before[key]) <= 1 for key in before), (
                name,
                before,
                after,
            )
        expect(page.locator("#early-link")).to_be_focused()
        expect(page.locator("#contents details")).to_have_attribute("open", "")
        expect(page.locator("#feed .lf-activity-news")).to_have_attribute(
            "aria-expanded", "true"
        )
        assert page.evaluate("globalThis.litHtmlVersions.length") == 1
        # The adopted drawing responds to both native and live controls.
        summary = page.locator("#contents summary")
        summary.press("Enter")
        expect(page.locator("#contents details")).not_to_have_attribute("open", "")
        summary.press("Enter")
        expect(page.locator('#contents a[href="#evidence"]')).to_be_visible()
        page.locator("#feed .lf-activity-news").click()
        expect(page.locator("#feed .lf-activity-row")).to_be_hidden()
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_streamed_initial_host_first_shows_its_complete_drawing(
    engine, request, compiled_checkout
):
    """A pause inside a nested widget must not expose source layout before its drawing,
    and the drawn host stands among its authored siblings with no delivery script left.

    The same nodes then reach the behavior module, with tab memory already drawn and
    the original nested source still available for semantic intake and revisions.
    Firefox reparses a document after an unbalanced `document.write` and warns of it,
    so its run holds delivery to writing none.
    """
    browser = request.getfixturevalue(engine)
    assets = compiled_checkout / "browser"
    host_source = (
        '<lf-initial-outer id="outer"><aside data-lf-exhibit="">'
        '<lf-initial-inner id="inner"><p>Original nested prose</p>'
        "</lf-initial-inner></aside></lf-initial-outer>"
    )
    source = (
        "<!DOCTYPE html><html><head><title>Streamed initial drawing</title></head><body><main>"
        '<p id="already-reading">A paragraph already available to read.</p>'
        + host_source
        + '<p id="after">After the complete drawing.</p></main></body></html>'
    )
    producer = b"""
        const initial = document.documentElement.lfInitial;
        const {html, ref} = initial.lit;
        initial.register('lf-initial-inner', (host, {tabStore}) => {
            const authored = [...host.childNodes];
            host.replaceChildren();
            const view = {reading: null};
            view.render = () => html`${authored}<p ${ref(node => {
                if (node) view.reading = node;
            })}>${tabStore.get('restored-reading')}</p>`;
            return view;
        });
        initial.register('lf-initial-outer', (host, {authoredBody}) => {
            const frame = authoredBody(document.createElement('div'));
            frame.className = 'initial-frame';
            return {frame, render: () => html`${frame}`};
        });
    """
    # The kernel's modules over the source ones, as a vendored page has them.
    resources = {
        **{
            "/" + path.relative_to(root).as_posix(): Resource(
                path.read_bytes(), "application/javascript"
            )
            for root in (assets, compiled_checkout / "dist/kernel")
            for path in root.rglob("*.js")
        },
        "/leaf.js": Resource(
            b"""
                import {initialRender} from '/runtime/widget-api.js';
                const host = document.getElementById('outer');
                const frame = host.querySelector('.initial-frame');
                const adopted = initialRender(host);
                host.dataset.adopted = String(adopted.frame === frame);
            """,
            "application/javascript",
        ),
        "/vendor/initial.js": Resource(producer, "application/javascript"),
        **{
            path: Resource(b"", "text/css")
            for path in (
                "/runtime/annotation-overlay/annotation-theme.css",
                "/runtime/chrome.css",
                "/runtime/marks.css",
                "/runtime/annotation-overlay/annotation-chrome.css",
                "/runtime/annotation-overlay/annotation-marks.css",
            )
        },
    }
    registry = {
        tag: {"x-upgrade": True, "x-initial": "/vendor/initial.js"}
        for tag in ("lf-initial-outer", "lf-initial-inner")
    }
    delivered = compose_document(
        source,
        1,
        None,
        executable="sha256:fixture",
        resources=resources,
        registry=registry,
        delivery=Delivery(
            address=lambda path: path if path in resources else None,
            runtime="",
            # The theme holds the arriving host out of the page.
            inline_stylesheet=lambda _: (
                stylesheet(assets / "base.css", assets)
                + "lf-initial-outer{display:block;margin-block:16px}"
                ".initial-frame{padding:24px;border:1px solid black}"
            ),
        ),
    )
    boundary = delivered.index("</lf-initial-inner>")
    release_source = Event()
    release_module = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html" if self.path == "/" else "application/javascript",
            )
            self.end_headers()
            if self.path == "/":
                self.wfile.write(delivered[:boundary].encode())
                self.wfile.flush()
                release_source.wait()
                self.wfile.write(delivered[boundary:].encode())
            elif self.path == "/leaf.js":
                release_module.wait()
                self.wfile.write(resources[self.path].data)
            elif self.path in resources:
                self.wfile.write(resources[self.path].data)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    with running_http_server(server):
        context = browser.new_context()
        context.add_init_script(
            "sessionStorage.setItem('restored-reading', 'Restored value');"
        )
        page = context.new_page()
        errors = []
        collect_page_exceptions(page, errors)
        try:
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="commit")
            page.wait_for_function(
                "performance.getEntriesByType('paint').some(p => p.name === 'first-contentful-paint')"
            )
            assert page.locator("#already-reading").is_visible()
            assert page.evaluate("document.readyState") == "loading"
            assert page.evaluate("""() => {
                const host = document.getElementById('outer');
                return !host || !host.getBoundingClientRect().height ||
                    !!host.querySelector('.initial-frame');
            }"""), "the incomplete source painted before its initial drawing"

            release_source.set()
            page.wait_for_selector("#after")
            assert page.locator("#outer .initial-frame").count() == 1, page.evaluate(
                "document.body.innerHTML"
            )
            # The delivery's scripts leave, so a page rule for a first, last or next
            # child finds the host among its authored siblings alone.
            assert page.evaluate(
                "[...document.querySelector('main').children].map(child => child.id)"
            ) == ["already-reading", "outer", "after"]
            assert (
                page.locator("#inner").inner_text()
                == "Original nested prose\n\nRestored value"
            )
            assert (
                page.evaluate(
                    "document.documentElement.lfInitial.authoredCopy(document.getElementById('outer')).outerHTML"
                )
                == host_source
            )
            restored, authored = page.evaluate(
                """([delivered, authored]) => {
                    const parser = new DOMParser();
                    const revision = parser.parseFromString(delivered, 'text/html');
                    document.documentElement.lfInitial.restoreSource(revision);
                    return [revision.querySelector('main').outerHTML,
                        parser.parseFromString(authored, 'text/html').querySelector('main').outerHTML];
                }""",
                [delivered, source],
            )
            assert restored == authored
            archive = page.evaluate(
                """() => {
                    const initial = document.documentElement.lfInitial;
                    let constructed = 0, connected = 0;
                    for (const tag of ['lf-initial-outer', 'lf-initial-inner']) {
                        customElements.define(tag, class extends HTMLElement {
                            constructor() { super(); constructed++; }
                            connectedCallback() { connected++; }
                        });
                    }
                    const before = [constructed, connected];
                    const copy = initial.authoredCopy(document);
                    const copiedHost = copy.getElementById('outer');
                    return {
                        before, after: [constructed, connected],
                        source: copiedHost.outerHTML,
                        connected: copiedHost.isConnected,
                        origin: initial.origin(copiedHost) === document.getElementById('outer'),
                    };
                }"""
            )
            assert archive["before"] == [2, 2]
            assert archive["after"] == archive["before"]
            assert archive["source"] == host_source
            assert archive["connected"] and archive["origin"]
            before = page.locator("#outer").bounding_box()
            page.evaluate(
                "window.initialFrame = document.querySelector('#outer .initial-frame')"
            )
            release_module.set()
            page.wait_for_selector('#outer[data-adopted="true"]')
            assert page.evaluate(
                "window.initialFrame === document.querySelector('#outer .initial-frame')"
            )
            assert page.locator("#outer").bounding_box() == before
            assert errors == []

            fallback = browser.new_context(java_script_enabled=False)
            reader = fallback.new_page()
            reader.goto(f"http://127.0.0.1:{server.server_port}/")
            assert reader.locator("#inner").is_visible()
            assert reader.locator("#inner").inner_text() == "Original nested prose"
        finally:
            release_source.set()
            release_module.set()
