"""The website route adapter preserves Leaf's canonical served-page contract."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from interact_support import (
    running_http_server,
)
from leaf_dev import journey, startup, verify_site
from process.test_website_server import (
    _no_harness_outlives_its_test_fixture,  # noqa: F401 (fixtures)
    shown_by,
)
from render_harness import (
    consume_browser_errors,
)


def test_a_failed_verifier_page_reports_its_browser_errors(browser):
    page = browser.new_page()
    failures = verify_site.observe_startup(page)
    url = "https://site-verifier.test/broken"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<!doctype html><body><script>
                  console.error('widget resource unavailable');
                  throw new Error('runtime initialization failed');
                </script></body>""",
        ),
    )
    page.goto(url)
    # The document throws before anything could present it, so this wait runs out by
    # design; its length is what the test spends watching nothing arrive.
    never_presents_ms = 100
    with pytest.raises(RuntimeError) as caught:
        verify_site.await_presentation(page, url, failures, timeout=never_presents_ms)
    assert "widget resource unavailable" in str(caught.value)
    assert "runtime initialization failed" in str(caught.value)
    assert "no startup milestone" in str(caught.value)
    # The same two faults the verifier reported are what this page said.
    consume_browser_errors(
        page, "widget resource unavailable", "runtime initialization failed"
    )


def test_the_agent_response_clock_waits_until_the_reply_is_on_screen(browser):
    page = browser.new_page()
    verify_site.observe_startup(page)
    url = "https://site-verifier.test/visible-response"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<div class="lf-threads" style="height: 100px; overflow: auto">
                  <div style="height: 500px"></div>
                  <div class="lf-msg agent" data-mid="answer"><span class="lf-msg-text">Visible reply</span></div>
                </div>""",
        ),
    )
    page.goto(url)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    page.wait_for_timeout(100)
    reply = {"thread": "comment", "id": "answer", "ts": "2026-10-08T09:00:00Z"}
    assert page.evaluate("window.__leafVerifier.replyShownAt", reply) is None
    before = page.evaluate("Date.now()")
    page.locator(".lf-msg.agent").scroll_into_view_if_needed()
    page.wait_for_function(
        "reply => window.__leafVerifier.replyShownAt(reply)", arg=reply
    )
    shown = page.evaluate("window.__leafVerifier.replyShownAt", reply)
    assert shown["by"] == "message" and shown["message"] == shown["at"]
    assert before <= shown["at"] <= page.evaluate("Date.now()")


def test_the_agent_response_clock_ignores_an_earlier_failure_receipt(browser):
    page = browser.new_page()
    verify_site.observe_startup(page)
    url = "https://site-verifier.test/retried-response"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<div class="lf-threads"><div class="lf-msg agent" data-mid="failed">
                      <span class="lf-msg-text">Could not start</span></div>
                    <div class="lf-msg agent" data-mid="answer" style="display: none">
                      <span class="lf-msg-text">Deployment verified</span></div></div>""",
        ),
    )
    page.goto(url)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    assert shown_by(page, "failed")["by"] == "message"
    hidden = {"thread": "comment", "id": "answer", "ts": "2026-10-08T09:00:00Z"}
    assert page.evaluate("window.__leafVerifier.replyShownAt", hidden) is None

    before = page.evaluate("Date.now()")
    page.locator('[data-mid="answer"]').evaluate("node => node.style.display = 'block'")
    shown = shown_by(page, "answer")
    assert shown["by"] == "message" and shown["at"] >= before


def test_the_agent_response_clock_follows_a_stream_into_its_durable_reply(browser):
    page = browser.new_page()
    verify_site.observe_startup(page)
    url = "https://site-verifier.test/completed-stream"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<div class="lf-threads"><div class="lf-msg agent" data-mid="stream:turn">
                      <span class="lf-msg-text">Answer in progress</span></div></div>""",
        ),
    )
    page.goto(url)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    streamed = shown_by(page, "stream:turn")

    page.locator(".lf-msg").evaluate("""node => {
      node.dataset.mid = 'answer';
      node.querySelector('.lf-msg-text').textContent = 'Complete answer';
    }""")
    shown = shown_by(page, "answer")
    assert shown["by"] == "message" and shown["at"] >= streamed["at"]


def test_the_agent_verifier_opens_news_arriving_after_an_earlier_notice(browser):
    """Waiting on a reply, the journey's user opens each notice its thread shows,
    the second arriving once the first is opened, until the reply is in view."""
    page = browser.new_page()
    verify_site.observe_startup(page)
    url = "https://site-verifier.test/held-answer"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<div class="lf-threads"><div class="lf-thread" data-id="comment">
              <button class="lf-thread-news" onclick="this.remove(); setTimeout(() => {
                const next = document.createElement('button');
                next.className = 'lf-thread-news';
                next.textContent = 'Final reply waiting';
                next.onclick = () => {
                  document.querySelector('.lf-msg').dataset.mid = 'answer';
                  next.remove();
                };
                document.querySelector('.lf-thread').append(next);
              }, 0)">Stream update waiting</button>
              <div class="lf-msg agent" data-mid="stream:turn">
                <span class="lf-msg-text">Complete answer</span></div>
              </div></div>""",
        ),
    )
    page.goto(url)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    session = journey.Session(
        None, page, [], url, url, {}, {}, None,
        pause=lambda seconds: page.wait_for_timeout(seconds * 1000),
    )  # fmt: skip
    answer = {"parent": "comment", "id": "answer", "ts": "2026-10-08T09:00:00Z"}
    shown = journey.await_reply_shown(journey.BrowserEnd(session), answer)
    assert shown["by"] == "message"
    assert page.locator(".lf-thread-news").count() == 0


def test_startup_resources_outlive_the_browser_timing_buffer(browser):
    """The real verifier counts every response, including beyond Chrome's 250 entries."""
    count = 260
    script = b"/* startup resource */"
    document = (
        "<!doctype html><html><head><title>Startup resources</title></head><body>"
        + "".join(f'<script src="/resource-{n}.js"></script>' for n in range(count))
        + "<script>document.body.setAttribute('data-lf-upgraded', '');"
        "document.body.setAttribute('data-lf-presented', '');</script></body></html>"
    ).encode()

    class Resources(BaseHTTPRequestHandler):
        def do_GET(self):
            body = script if self.path.endswith(".js") else document
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Content-Type",
                "text/javascript" if self.path.endswith(".js") else "text/html",
            )
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_arguments):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Resources)
    with running_http_server(httpd):
        page = browser.new_page()
        verify_site.observe_startup(page)
        page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/")
        reading = page.evaluate("window.__leafStartup.reading")
        for milestone in ("upgraded", "presented"):
            assert reading[milestone]["code_requests"] == count
            assert reading[milestone]["code_bytes"] == count * len(script)
        names = page.evaluate("window.__leafStartup.resourceNames")
        assert sum("/resource-" in name for name in names) == count


def test_startup_shifts_are_attributed_diagnostics_not_failures(browser):
    """A painted startup move is recorded, while quiet and later frames add none."""
    page = browser.unwatched.new_page()
    failures = verify_site.observe_startup(page)
    page.route(
        "http://startup.test/",
        lambda route: route.fulfill(
            content_type="text/html",
            body="<!doctype html><title>Startup shifts</title><body style='display:flow-root;margin:0'>"
            "<p id='moving'>A passage painted before widgets upgrade.</p>"
            "<p id='quiet' style='position:fixed;right:0;top:0'>A fixed control.</p>",
        ),
    )
    page.goto("http://startup.test/")
    page.wait_for_function(
        "performance.getEntriesByType('paint').some(e => e.name === 'first-contentful-paint')"
    )
    page.evaluate("document.querySelector('#moving').style.marginTop = '80px'")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r))))"
    )
    first = startup.startup_reading(page)
    assert first["shifts"], first
    assert {shift["phase"] for shift in first["shifts"]} == {"before-upgrade"}
    page.evaluate("document.body.setAttribute('data-lf-upgraded', '')")
    page.evaluate("document.querySelector('#moving').style.marginTop = '140px'")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r))))"
    )
    upgraded = startup.startup_reading(page)
    assert any(shift["phase"] == "before-presentation" for shift in upgraded["shifts"])
    page.evaluate("document.body.setAttribute('data-lf-presented', '')")
    reading = startup.startup_reading(page)
    moved = [
        (shift, source)
        for shift in reading["shifts"]
        for source in shift["sources"]
        if source["node"] and "#moving" in source["node"]
    ]
    assert {shift["phase"] for shift, _ in moved} == {
        "before-upgrade",
        "before-presentation",
    }, reading["shifts"]
    assert all(shift["value"] > 0 for shift, _ in moved)
    assert all(not shift["hadRecentInput"] for shift, _ in moved)
    assert all(
        source["currentRect"]["y"] > source["previousRect"]["y"] for _, source in moved
    )
    assert not any(
        source["node"] and "#quiet" in source["node"]
        for shift in reading["shifts"]
        for source in shift["sources"]
    )
    page.evaluate("document.querySelector('#moving').style.marginTop = '220px'")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    assert startup.startup_reading(page)["shifts"] == reading["shifts"]
    assert "initial layout shifts (diagnostic)" in verify_site.startup_line(
        "page", reading
    )
    assert "#moving" in verify_site.startup_line("page", reading)
    assert failures == []


def test_release_verifier_waits_for_the_revision_to_finish_presenting(browser):
    """The revision marker can advance while the live document patch is pending."""
    page = browser.unwatched.new_page()
    page.route(
        "http://release-verifier.test/",
        lambda route: route.fulfill(
            content_type="text/html",
            body=(
                "<!doctype html><head><meta name='lf-revision' content='2'>"
                "<script data-lf-entry></script></head><body data-lf-presented='1'>"
                "<main>Previous release</main></body>"
            ),
        ),
    )
    page.add_init_script(path=verify_site.VERIFIER_SCRIPT)
    page.goto("http://release-verifier.test/")
    page.evaluate(
        "document.querySelector('script[data-lf-entry]').lfReadiness = "
        "() => 'presented'"
    )
    assert not page.evaluate("window.__leafVerifier.revisionAtLeast(2)")
    page.evaluate(
        "document.querySelector('main').textContent = 'Release 3531f4e6'; "
        "document.querySelector('script[data-lf-entry]').lfReadiness = () => null"
    )
    assert page.evaluate("window.__leafVerifier.revisionAtLeast(2)")
