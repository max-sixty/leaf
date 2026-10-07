"""Initial drawings stay coherent when HTML arrives across separate parser tasks."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event

from interact_support import running_http_server
from leaf.revision_artifact import Resource
from leaf.revision_delivery import Delivery, compose_document


def test_a_streamed_initial_host_first_shows_its_complete_drawing(browser):
    """A pause inside a nested widget must not expose source layout before its drawing.

    The same nodes then reach the behavior module, with tab memory already drawn and
    the original nested source still available for semantic intake and revisions.
    """
    assets = Path(__file__).resolve().parents[1] / "skills/leaf/assets"
    host_source = (
        '<lf-initial-outer id="outer"><aside data-lf-exhibit="">'
        '<lf-initial-inner id="inner"><p>Original nested prose</p>'
        "</lf-initial-inner></aside></lf-initial-outer>"
    )
    source = (
        "<html><head><title>Streamed initial drawing</title></head><body><main>"
        '<p id="already-reading">A paragraph already available to read.</p>'
        + host_source
        + '<p id="after">After the complete drawing.</p></main></body></html>'
    )
    producer = b"""
        const initial = document.documentElement.lfInitial;
        initial.register('lf-initial-inner', (host, {tabStore}) => {
            const reading = document.createElement('p');
            reading.textContent = tabStore.get('restored-reading');
            host.append(reading);
            return {reading};
        });
        initial.register('lf-initial-outer', (host) => {
            const frame = document.createElement('div');
            frame.className = 'initial-frame';
            frame.append(...host.childNodes);
            host.append(frame);
            return {frame};
        });
    """
    resources = {
        "/leaf.js": Resource(
            b"""
                import {initialRender} from '/runtime/initial-render.js';
                const host = document.getElementById('outer');
                const frame = host.querySelector('.initial-frame');
                const adopted = initialRender(host);
                host.dataset.adopted = String(adopted.frame === frame);
            """,
            "application/javascript",
        ),
        "/runtime/prepaint.js": Resource(
            (assets / "runtime/prepaint.js").read_bytes(), "application/javascript"
        ),
        "/vendor/initial.js": Resource(producer, "application/javascript"),
        "/runtime/initial-render.js": Resource(
            (assets / "runtime/initial-render.js").read_bytes(),
            "application/javascript",
        ),
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
        executable=None,
        widgets={},
        resources=resources,
        registry=registry,
        delivery=Delivery(
            address=lambda path: path if path in resources else None,
            runtime="",
            inline_stylesheet=lambda _: (
                "lf-initial-outer{display:block;margin-block:16px}"
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

        def log_message(self, *args):
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
        page.on("pageerror", lambda error: errors.append(str(error)))
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
            try:
                reader = fallback.new_page()
                reader.goto(f"http://127.0.0.1:{server.server_port}/")
                assert reader.locator("#inner").is_visible()
                assert reader.locator("#inner").inner_text() == "Original nested prose"
            finally:
                fallback.close()
        finally:
            release_source.set()
            release_module.set()
            context.close()
