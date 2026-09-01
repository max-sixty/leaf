"""The MCP App bridge renders a page and returns durable feedback to its host."""

import shutil

from interact_support import ROOT
from leaf.event_log import append_event, read_events
from leaf.mcp_app import app_html, app_snapshot, apply_event
from leaf.mcp_page import ProcessPageServer
from leaf.revisioning import activate_source
from playwright.sync_api import expect

HOST = """<!doctype html>
<iframe id="app" style="width:100%;height:760px;border:0"></iframe>
<script>
window.calls = [];
window.currentLeaf = null;
window.hostCapabilities = {openLinks: {}, serverTools: {}};
const answer = (target, id, result) => target.postMessage(
  {jsonrpc: "2.0", id, result}, "*"
);
const refuse = (target, id, message) => target.postMessage(
  {jsonrpc: "2.0", id, error: {code: -32000, message}}, "*"
);
window.releaseMessage = () => {
  const held = window.heldMessage;
  window.heldMessage = null;
  if (held) answer(held.target, held.id, {});
};
const toolResult = (leaf) => ({
  content: [{type: "text", text: "Leaf result"}],
  structuredContent: {page: leaf.page, revision: leaf.revision},
  _meta: {leaf},
  isError: false,
});
window.addEventListener("message", (event) => {
  const message = event.data;
  if (!message || message.jsonrpc !== "2.0" || !message.method) return;
  window.calls.push({method: message.method, params: message.params});
  if (message.method === "ui/initialize") {
    answer(event.source, message.id, {
      protocolVersion: "2026-01-26",
      hostCapabilities: window.hostCapabilities,
      hostContext: {
        theme: "light",
        locale: "en",
        availableDisplayModes: ["inline", "fullscreen"],
        displayMode: "inline",
      },
    });
    setTimeout(() => event.source.postMessage({
      jsonrpc: "2.0",
      method: "ui/notifications/tool-result",
      params: toolResult(window.currentLeaf),
    }, "*"));
    return;
  }
  if (message.method === "tools/call") {
    const name = message.params.name;
    if (name === "leaf_snapshot_apply_event") {
      window.currentLeaf = {
        ...window.currentLeaf,
        eventSeq: window.currentLeaf.eventSeq + 1,
      };
    }
    answer(event.source, message.id, toolResult(window.currentLeaf));
    return;
  }
  if (message.method === "ui/message") {
    if (!Array.isArray(message.params.content)) {
      refuse(event.source, message.id, "Message content must be an array");
      return;
    }
    answer(event.source, message.id, {});
    return;
  }
  if (message.id !== undefined) answer(event.source, message.id, {});
});
</script>
"""


def test_process_page_route_runs_the_complete_leaf_interface(browser, page_dir):
    append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
            "version": 1,
            "revision": 1,
            "text": "published",
        },
    )
    media = page_dir / "media"
    media.mkdir(exist_ok=True)
    for filename in ("051bee487bfb5d13.png", "a99a1b63048502d0.png"):
        shutil.copy2(ROOT / "examples" / "media" / filename, media / filename)
    source = page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace(
            "</head>",
            "<style>#plan { background-image: "
            "url(/media/051bee487bfb5d13.png); }</style></head>",
        )
        .replace("<h2>Plan</h2>", "<h2>Plan now</h2>")
        .replace(
            "The cutoff lives in ",
            'Post to "/api/event" before the cutoff in ',
        )
        .replace(
            "</section>",
            '<lf-shot id="mcp-shot" alt="the page before and after" '
            'before="/media/051bee487bfb5d13.png" '
            'after="/media/a99a1b63048502d0.png"></lf-shot></section>',
        ),
        encoding="utf-8",
    )
    activated = activate_source(page_dir, read_events(page_dir))
    assert activated.error is None and activated.revision == 2
    pages = ProcessPageServer()
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    errors = []
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    try:
        url = pages.open(page_dir)
        root = url.removeprefix(pages.origin).rstrip("/")
        page.goto(url)
        page.wait_for_function(
            "() => document.body.getAttribute('data-lf-presented') === '1'"
        )

        assert page.title() == "t"
        assert page.locator(".lf-banner").is_visible()
        assert page.evaluate(
            "() => performance.getEntriesByType('resource').map(r => r.name)"
        )
        assert all(
            urlsplit.startswith(f"{pages.origin}{root}/")
            for urlsplit in page.evaluate(
                "() => performance.getEntriesByType('resource').map(r => r.name)"
            )
            if urlsplit.startswith(pages.origin)
        )

        assert 'Post to "/api/event"' in page.locator("#plan > p").inner_text()
        assert root not in page.locator("#plan > p").inner_text()
        page.locator("#plan > p").evaluate(
            """paragraph => {
              const text = paragraph.firstChild;
              const range = document.createRange();
              range.setStart(text, 0);
              range.setEnd(text, 'Post to "/api/event"'.length);
              const selected = window.getSelection();
              selected.removeAllRanges();
              selected.addRange(range);
              paragraph.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            }"""
        )
        expect(page.locator(".lf-fab-input")).to_be_visible()
        page.locator(".lf-fab-input").click()
        page.locator(".lf-composer textarea").fill("Delivered through the MCP page.")
        with page.expect_response(lambda response: response.url.endswith("/api/event")):
            page.keyboard.press("Enter")

        saved = read_events(page_dir)[-1]
        assert saved["text"] == "Delivered through the MCP page."
        assert saved["anchor"]["quote"] == 'Post to "/api/event"'
        assert root not in saved["anchor"]["quote"]
        expect(page.locator(".lf-thread")).to_contain_text(
            "Delivered through the MCP page."
        )

        source.write_text(
            source.read_text().replace(
                "</section>",
                '<p><img id="late" src="/media/051bee487bfb5d13.png" '
                'alt="late revision"></p></section>',
                1,
            ),
            encoding="utf-8",
        )
        revised = activate_source(page_dir, read_events(page_dir))
        assert revised.error is None and revised.revision == 3
        page.locator("#late").wait_for()
        page.wait_for_function("() => document.querySelector('#late').naturalWidth > 0")
        assert page.locator("#late").get_attribute("src") == (
            f"{root}/media/051bee487bfb5d13.png"
        )
        assert all(
            resource.startswith(f"{pages.origin}{root}/")
            for resource in page.evaluate(
                "() => performance.getEntriesByType('resource').map(r => r.name)"
            )
            if resource.startswith(pages.origin)
        )

        page.locator(".lf-version").click()
        page.locator('.lf-version-row[data-lf-version="1"]').click()
        page.wait_for_function(
            "() => document.body.getAttribute('data-lf-presented') === '1'"
        )
        assert page.url.startswith(f"{pages.origin}{root}/versions/v1.html")
        assert page.locator("#plan > h2").inner_text() == "Plan"
        assert errors == []
    finally:
        page.close()
        pages.close()


def test_snapshot_app_renders_general_and_anchored_feedback_without_claiming_delivery(
    browser, page_dir
):
    apply_event(
        str(page_dir),
        {
            "kind": "comment",
            "revision": 1,
            "text": "A standing thread already belongs to the durable page.",
            "attempt": "mcp-standing-thread-1",
        },
        1,
    )
    _, private = app_snapshot(str(page_dir))
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    try:
        page.set_content(HOST)
        page.evaluate("leaf => window.currentLeaf = leaf", private)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = page.frames[-1]
        app.locator("#title").wait_for()
        assert app.locator("#title").text_content() == "t"
        assert (
            "Authored snapshot · comments only" in app.locator("#meta").text_content()
        )
        assert app.locator(".stage").text_content() == "Experimental"
        assert "Ship dark" in app.locator("#page-host").evaluate(
            "host => host.shadowRoot.textContent"
        )

        app.locator("#comment-page").click()
        app.locator("#comment").fill("Explain the migration boundary.")
        app.locator("#send").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'tools/call').length === 1"
        )
        assert "Feedback saved in the Leaf log" in app.locator("#status").text_content()
        assert not [
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "ui/message"
        ]

        app.evaluate(
            """() => {
              const root = document.querySelector('#page-host').shadowRoot;
              const text = root.querySelector('#plan p').firstChild;
              const range = document.createRange();
              range.setStart(text, 0);
              range.setEnd(text, 20);
              const selected = root.getSelection();
              selected.removeAllRanges();
              selected.addRange(range);
              root.querySelector('#plan p').dispatchEvent(
                new MouseEvent('mouseup', {bubbles: true, composed: true})
              );
            }"""
        )
        assert "The cutoff lives in" in app.locator("#quote").text_content()
        app.locator("#comment").fill(
            "\n".join(f"Long review line {number}" for number in range(20))
        )
        assert (
            app.locator("#comment").evaluate(
                "field => field.getBoundingClientRect().height"
            )
            == 240
        )
        app.evaluate("scrollBy(0, 300)")
        composer_bottom = app.locator("#composer").evaluate(
            "form => form.getBoundingClientRect().bottom"
        )
        assert abs(composer_bottom - app.evaluate("innerHeight")) < 1
        app.locator("#comment").fill("Keep this near the decision.")
        assert (
            app.locator("#comment").evaluate(
                "field => field.getBoundingClientRect().height"
            )
            == 66
        )
        before = app.locator("#page-host").evaluate(
            "host => getComputedStyle(host.shadowRoot.querySelector('main')).color"
        )
        page.evaluate(
            """() => document.querySelector('#app').contentWindow.postMessage({
              jsonrpc: '2.0',
              method: 'ui/notifications/host-context-changed',
              params: {theme: 'dark'},
            }, '*')"""
        )
        app.locator("#page-host").evaluate(
            "host => new Promise(resolve => requestAnimationFrame(() => resolve()))"
        )
        after = app.locator("#page-host").evaluate(
            "host => getComputedStyle(host.shadowRoot.querySelector('main')).color"
        )
        assert before != after
        assert app.locator("#composer").evaluate(
            "form => form.classList.contains('open')"
        )
        assert app.locator("#comment").input_value() == "Keep this near the decision."

        app.locator("#send").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'tools/call').length === 2"
        )

        calls = page.evaluate("window.calls")
        applies = [
            call
            for call in calls
            if call["method"] == "tools/call"
            and call["params"]["name"] == "leaf_snapshot_apply_event"
        ]
        assert "anchor" not in applies[0]["params"]["arguments"]["event"]
        anchor = applies[1]["params"]["arguments"]["event"]["anchor"]
        assert anchor["quote"] == "The cutoff lives in"
        assert anchor["section"] == "plan"
        assert "prefix" not in anchor
        assert "suffix" not in anchor
        assert not [
            call for call in calls if call["method"] == "ui/update-model-context"
        ]
        assert "Feedback saved in the Leaf log" in app.locator("#status").text_content()

        assert app.locator("#browser").inner_text() == "Full page"
        app.locator("#browser").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'ui/message').length === 1"
        )
        full_page = [
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "ui/message"
        ][-1]
        assert "active widget controls" in full_page["params"]["content"][0]["text"]
        assert str(page_dir) in full_page["params"]["content"][0]["text"]
        assert "Asked Codex to open" in app.locator("#status").text_content()

        page.emulate_media(media="print")
        assert (
            app.locator(".bar").evaluate("bar => getComputedStyle(bar).display")
            == "none"
        )
        assert app.locator("#page-host").is_visible()
    finally:
        page.close()


def test_mcp_app_keeps_authored_css_without_running_authored_code(browser, page_dir):
    media = page_dir / "media"
    media.mkdir(exist_ok=True)
    (media / "0123456789abcdef.png").write_bytes(b"leaf")
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</head>",
            "<style>#plan h2 { color: rgb(12, 34, 56); "
            "background-image: url(/media/0123456789abcdef.png); }</style></head>",
        )
    )
    _, private = app_snapshot(str(page_dir))
    assert "#plan h2 { color: rgb(12, 34, 56);" in private["authoredCss"]
    assert "url(data:image/png;base64," in private["authoredCss"]
    private["document"] = private["document"].replace(
        "<h2>Plan</h2>",
        "<h2>Plan</h2><script>window.authoredCodeRan = true</script>",
    )
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    try:
        page.set_content(HOST)
        page.evaluate("leaf => window.currentLeaf = leaf", private)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = page.frames[-1]
        app.locator("#title").wait_for()

        assert (
            app.locator("#page-host").evaluate(
                "host => getComputedStyle(host.shadowRoot.querySelector('#plan h2')).color"
            )
            == "rgb(12, 34, 56)"
        )
        assert (
            app.locator("#page-host")
            .evaluate(
                "host => getComputedStyle(host.shadowRoot.querySelector('#plan h2')).backgroundImage"
            )
            .startswith('url("data:image/png;base64,')
        )
        assert (
            app.locator("#page-host").evaluate(
                "host => host.shadowRoot.querySelectorAll('script').length"
            )
            == 0
        )
        assert app.evaluate("window.authoredCodeRan") is None
    finally:
        page.close()


def test_mcp_app_is_read_only_when_the_host_cannot_proxy_server_tools(
    browser, page_dir
):
    _, private = app_snapshot(str(page_dir))
    page = browser.new_page(viewport={"width": 900, "height": 700})
    try:
        page.set_content(HOST)
        page.evaluate(
            "leaf => { window.currentLeaf = leaf; window.hostCapabilities = {}; }",
            private,
        )
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = page.frames[-1]
        app.locator("#title").wait_for()

        assert app.locator("#comment-page").is_disabled()
        assert app.locator("#refresh").is_disabled()
        assert app.locator("#browser").is_enabled()
        assert "read-only" in app.locator("#status").text_content()
    finally:
        page.close()
