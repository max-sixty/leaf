"""Ordinary HTML tooling for the product control, without Leaf in its workspace.

The control authors HTML/CSS/JS from the same user task. Its files are served by
Python's static HTTP server and checked in Chrome; no Leaf payload is patched,
vended, served, or loaded. Browser completion is the ordinary document's load,
fonts and images, rather than a Leaf presentation publication.
"""

import functools
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from leaf_dev.browser import chrome, tab


class StaticHandler(SimpleHTTPRequestHandler):
    """Browser-owned favicon requests need no authored icon; report only page faults."""

    def do_GET(self):
        if (
            self.path == "/favicon.ico"
            and not Path(self.translate_path(self.path)).exists()
        ):
            self.send_response(204)
            self.end_headers()
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass


@contextmanager
def serving(page: Path):
    """Serve only the HTML output directory, shutting down the server on exit."""
    handler = functools.partial(StaticHandler, directory=str(page))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def settle(view) -> None:
    """Wait for resources the ordinary HTML document declares, without Leaf APIs."""
    view.evaluate("() => document.fonts.ready")
    view.wait_for_function("Array.from(document.images).every(image => image.complete)")


def load(view, url: str) -> None:
    view.goto(url, wait_until="load")
    settle(view)


def gate(page: Path, widths: dict) -> dict:
    """Check actual browser errors and root overflow at each comparison width."""
    findings = []
    with serving(page) as url, chrome() as browser:
        for name, (viewport, _) in widths.items():
            with tab(browser, viewport=viewport, touch=name == "phone") as view:
                errors = []
                view.on(
                    "pageerror", lambda error, errors=errors: errors.append(str(error))
                )
                view.on(
                    "console",
                    lambda message, errors=errors: (
                        errors.append(message.text) if message.type == "error" else None
                    ),
                )
                load(view, url)
                overflow = view.evaluate(
                    "document.documentElement.scrollWidth > innerWidth + 1"
                )
                findings.extend({"width": name, "error": error} for error in errors)
                if overflow:
                    findings.append(
                        {"width": name, "error": "page overflows the viewport"}
                    )
    return {"passed": not findings, "findings": findings}
