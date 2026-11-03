"""Serve and load ordinary HTML, with no Leaf payload, server or runtime.

The plain-HTML control of the authoring evals and the UI review fixtures are files a
browser opens as written. `serving` is the one static file server for them: Python's
own, on a thread, so a command holds it open around its work.
It serves the directory's files and nothing else: a directory listing would show a
blinded reviewer every candidate, so it answers 404. A browser's own favicon request
answers 204 when the page brings none, so a page's request failures are its own.
Browser completion is the ordinary document's load, fonts and images, rather than a
Leaf presentation publication.
"""

import functools
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class StaticHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if (
            self.path == "/favicon.ico"
            and not Path(self.translate_path(self.path)).exists()
        ):
            self.send_response(204)
            self.end_headers()
        else:
            super().do_GET()

    def list_directory(self, path):
        self.send_error(404)

    def log_message(self, format, *args):
        pass


@contextmanager
def serving(directory: Path):
    """Serve `directory` until the block exits; yields its root URL, ending in `/`."""
    handler = functools.partial(StaticHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            thread.join()


def settle(view) -> None:
    """Wait for resources the ordinary HTML document declares, without Leaf APIs."""
    view.evaluate("() => document.fonts.ready")
    view.wait_for_function("Array.from(document.images).every(image => image.complete)")


def load(view, url: str) -> None:
    view.goto(url, wait_until="load")
    settle(view)
