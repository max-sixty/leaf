"Initial presentation, polling, presence, and projected-data tests."

import re

import pytest
from interact_support import (
    append_carried_log_record,
)
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    TOKEN,
    consume_browser_errors,
    open_page,
    open_threads,
    told,
)

from leaf import hosting as hosting_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_page_hears_again_when_its_server_comes_back(browser, serve):
    """A server is stopped and started under an open tab whenever its layer is
    re-vendored, and the tab finds the new one on its own: its freshness read fails
    with the old server, and the browser keeps asking. The page says the server is
    gone while it is, and reads again when the server comes back, because the last
    thing it knew about the server is from before the silence."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url)
    status = page.locator(".lf-fp-leaf")
    offline = re.compile("Lost the connection")
    port = serve.httpd.server_address[1]
    next(server for server in serve.servers if server.httpd is serve.httpd).close()
    expect(status).to_have_attribute("aria-label", offline)

    server = hosting_model.TemporaryPageServer(
        serve.page_dir, token=TOKEN, port=port
    ).start()
    serve.servers.append(server)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Back."},
    )
    told(page)
    expect(status).not_to_have_attribute("aria-label", offline)
    open_threads(page)
    expect(page.locator(".lf-fp-thread", has_text="Back.")).to_have_count(1)
    # The requests that failed while the server was down are the one thing the
    # console may hold; a page fault of the runtime's own would say something else.
    consume_browser_errors(page, "net::ERR")
