"""Ordinary HTML tooling for the product control, without Leaf in its workspace.

The control authors HTML/CSS/JS from the same user task. Its files are served by
Python's static HTTP server and inspected by the live judge; no Leaf payload is
patched, vended, served, or loaded. Browser completion is the ordinary document's load,
fonts and images, rather than a Leaf presentation publication.
"""

import functools
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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
