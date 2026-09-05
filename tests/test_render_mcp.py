"""The MCP App bridge renders a page and returns durable feedback to its host."""

import json
import shutil

from interact_support import ROOT
from leaf.anchor_capture import capture_anchor
from leaf.event_log import append_event, read_events
from leaf.files import revision_path
from leaf.mcp_app import app_html, app_snapshot, apply_event
from leaf.mcp_page import ProcessPageServer, page_state
from leaf.revisioning import activate_source
from playwright.sync_api import expect
from render_support import leaf_page, live_url, open_page

HOST = """<!doctype html>
<iframe id="app" style="width:100%;height:760px;border:0"></iframe>
<script>
window.calls = [];
window.currentLeaf = null;
window.snapshotLeaf = null;
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
      hostInfo: {name: "Leaf test host", version: "1"},
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
    if (window.toolError) {
      answer(event.source, message.id, {
        content: [{type: "text", text: window.toolError}],
        structuredContent: {ok: false, status: 400},
        isError: true,
      });
      return;
    }
    let leaf = window.currentLeaf;
    if (name === "leaf_snapshot_refresh" && window.snapshotLeaf)
      leaf = window.snapshotLeaf;
    if (name === "leaf_snapshot_apply_event") {
      window.currentLeaf = {
        ...window.currentLeaf,
        eventSeq: window.currentLeaf.eventSeq + 1,
      };
      leaf = window.currentLeaf;
    }
    answer(event.source, message.id, toolResult(leaf));
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
            '<style title="before > after">#plan { background-image: '
            "url(/media/051bee487bfb5d13.png); }</style></head>",
        )
        .replace("<h2>Plan</h2>", "<h2>Plan now</h2>")
        .replace(
            "The cutoff lives in ",
            'Post to "/api/event" before the cutoff in ',
        )
        .replace(
            "</section>",
            '<lf-shot id="mcp-shot" alt="the page before > after" '
            'before="/media/051bee487bfb5d13.png" '
            'after="/media/a99a1b63048502d0.png"></lf-shot></section>',
        ),
        encoding="utf-8",
    )
    activated = activate_source(page_dir, read_events(page_dir))
    assert activated.error is None and activated.revision == 2
    append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Codex",
            "revision": 2,
            "text": "The same comparison in a frozen message.",
            "markup": (
                '<lf-shot id="message-shot" alt="message before > after" '
                'before="/media/051bee487bfb5d13.png" '
                'after="/media/a99a1b63048502d0.png"></lf-shot>'
            ),
        },
    )
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
        page.wait_for_function(
            """() => {
              const images = [...document.querySelectorAll('#message-shot img')];
              return images.length === 2 && images.every(image => image.naturalWidth > 0);
            }"""
        )
        assert page.locator("#message-shot").get_attribute("before") == (
            f"{root}/media/051bee487bfb5d13.png"
        )
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
            page.keyboard.press("ControlOrMeta+Enter")

        saved = read_events(page_dir)[-1]
        assert saved["text"] == "Delivered through the MCP page."
        assert saved["anchor"]["quote"] == 'Post to "/api/event"'
        assert root not in saved["anchor"]["quote"]
        expect(
            page.locator(".lf-thread").filter(
                has_text="Delivered through the MCP page."
            )
        ).to_have_count(1)

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


def test_adaptive_app_renders_the_complete_page_payload(browser, page_dir):
    pages = ProcessPageServer()
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    try:
        _, private = page_state(str(page_dir), pages)
        _, snapshot = app_snapshot(str(page_dir))
        page.set_content(HOST)
        page.evaluate(
            """input => {
              window.currentLeaf = input.leaf;
              window.hostCapabilities = {
                ...window.hostCapabilities,
                sandbox: {csp: {frameDomains: [input.origin]}},
              };
            }""",
            {"leaf": private, "origin": pages.origin},
        )
        page.evaluate("leaf => window.snapshotLeaf = leaf", snapshot)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
        app.locator("#title").wait_for()

        assert app.locator("#title").text_content() == "t"
        assert "Complete page" in app.locator("#meta").text_content()
        assert private["active"]["label"] in app.locator("#meta").text_content()
        assert "undefined" not in app.locator("#app").text_content()
        expect(app.locator("#leaf-page")).to_be_visible()
        expect(app.locator("#comment-page")).to_be_hidden()
        expect(app.locator("#snapshot")).to_be_visible()

        expect(app.locator("#leaf-page")).to_have_attribute(
            "src", private["inline_url"]
        )
        nested = next(frame for frame in page.frames if frame.parent_frame == app)
        nested.wait_for_function(
            "() => document.body.getAttribute('data-lf-presented') === '1'"
        )
        assert nested.url == private["inline_url"]
        assert nested.title() == "t"
        assert "Ship dark" in nested.locator("body").text_content()
        assert "Leaf page loaded" not in app.locator("#status").text_content()
        expect(app.locator("#status")).to_contain_text("Complete Leaf page ready")
        assert not [
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "tools/call"
            and call["params"]["name"] == "leaf_snapshot_refresh"
        ]
        app.locator("#refresh").click()
        page.wait_for_function(
            "() => window.calls.some(call => call.method === 'tools/call' && "
            "call.params.name === 'leaf_refresh')"
        )
        assert not [
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "tools/call"
            and call["params"]["name"] == "leaf_snapshot_apply_event"
        ]
        app.locator("#snapshot").click()
        expect(app.locator("#page-host")).to_be_visible()
        expect(app.locator("#leaf-page")).to_be_hidden()
        assert "Authored snapshot" in app.locator("#meta").text_content()
        assert "Ship dark" in app.locator("#page-host").evaluate(
            "host => host.shadowRoot.textContent"
        )
        assert errors == []

        pages.close()
        page.evaluate(
            """leaf => {
              window.currentLeaf = leaf;
              document.querySelector('#app').contentWindow.postMessage({
                jsonrpc: '2.0',
                method: 'ui/notifications/tool-result',
                params: {
                  content: [{type: 'text', text: 'Leaf result'}],
                  structuredContent: {page: leaf.page},
                  _meta: {leaf},
                  isError: false,
                },
              }, '*');
            }""",
            private,
        )
        expect(app.locator("#meta")).to_contain_text("Complete page")
        expect(app.locator("#page-loading")).to_be_visible()
        expect(app.locator("#leaf-page")).to_be_hidden()
        expect(app.locator("#status")).not_to_contain_text("Complete Leaf page ready")
        expect(app.locator("#meta")).to_contain_text("Authored snapshot", timeout=8000)
        expect(app.locator("#page-host")).to_be_visible()
    finally:
        page.close()
        pages.close()


def test_adaptive_app_skips_a_frame_the_host_did_not_approve(browser, page_dir):
    pages = ProcessPageServer()
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    try:
        _, private = page_state(str(page_dir), pages)
        _, snapshot = app_snapshot(str(page_dir))
        page.set_content(HOST)
        page.evaluate(
            """leaf => {
              window.currentLeaf = leaf;
              window.hostCapabilities = {
                ...window.hostCapabilities,
                sandbox: {csp: {frameDomains: []}},
              };
            }""",
            private,
        )
        page.evaluate("leaf => window.snapshotLeaf = leaf", snapshot)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )

        expect(app.locator("#meta")).to_contain_text("Authored snapshot")
        assert app.locator("#leaf-page").get_attribute("src") in (None, "about:blank")
        assert not [
            frame for frame in page.frames if frame.url.startswith(pages.origin)
        ]
        assert [
            call["params"]["name"]
            for call in page.evaluate("window.calls")
            if call["method"] == "tools/call"
        ] == ["leaf_snapshot_refresh"]
        assert "did not approve" in app.locator("#status").text_content()
    finally:
        page.close()
        pages.close()


def test_adaptive_app_falls_back_when_the_complete_page_never_signals_ready(
    browser, page_dir
):
    pages = ProcessPageServer()
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    try:
        _, private = page_state(str(page_dir), pages)
        private["inline_url"] = f"{pages.origin}/blocked"
        _, snapshot = app_snapshot(str(page_dir))
        page.set_content(HOST)
        page.evaluate("leaf => window.currentLeaf = leaf", private)
        page.evaluate("leaf => window.snapshotLeaf = leaf", snapshot)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
        app.locator("#title").wait_for()

        expect(app.locator("#page-loading")).to_be_visible()
        expect(app.locator("#leaf-page")).to_be_hidden()
        expect(app.locator("#meta")).to_contain_text("Authored snapshot", timeout=8000)
        expect(app.locator("#page-host")).to_be_visible()
        assert [
            call["params"]["name"]
            for call in page.evaluate("window.calls")
            if call["method"] == "tools/call"
        ] == ["leaf_snapshot_refresh"]
        assert "did not become ready" in app.locator("#status").text_content()

        app.locator("#browser").click()
        page.wait_for_function(
            "() => window.calls.some(call => call.method === 'ui/open-link')"
        )
        opened = next(
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "ui/open-link"
        )
        assert opened["params"]["url"] == private["inline_url"]
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
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
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

        app.locator("#refresh").click()
        page.wait_for_function(
            "() => window.calls.some(call => call.method === 'tools/call' && "
            "call.params.name === 'leaf_snapshot_refresh')"
        )

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
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
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


def test_mcp_snapshot_contains_hostile_navigation_and_authored_css(browser, page_dir):
    _, private = app_snapshot(str(page_dir))
    payload = (
        "data:text/html,%3Cscript%3Eparent.postMessage%28%7Bjsonrpc%3A%272.0%27%2C"
        "id%3A91%2Cmethod%3A%27tools%2Fcall%27%2Cparams%3A%7Bname%3A%27"
        "leaf_snapshot_apply_event%27%2Carguments%3A%7B%7D%7D%7D%2C%27%2A%27%29"
        "%3C%2Fscript%3E"
    )
    private["document"] = private["document"].replace(
        "<h2>Plan</h2>",
        (
            '<h2>Plan</h2><style id="hostile-style">'
            ":host { position: fixed !important; inset: 0 !important; }</style>"
            '<a id="hostile-link" href="'
            f'{payload}" target="_self" contenteditable="true">Leave Leaf</a>'
            f'<map><area id="hostile-area" href="{payload}" target="_top"></map>'
            '<form id="hostile-form" action="data:text/html,escaped" target="_top">'
            '<input id="hostile-input" contenteditable="true" '
            'formaction="data:text/html,escaped"></form>'
        ),
    )
    private["authoredCss"] += """
      :root#page-host {
        position: fixed !important;
        inset: 0 !important;
        z-index: 2147483647 !important;
        width: 100vw !important;
        height: 100vh !important;
        margin: -100px !important;
        transform: scale(2) !important;
        background: red;
      }
    """
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    try:
        page.set_content(HOST)
        page.evaluate("leaf => window.currentLeaf = leaf", private)
        page.locator("#app").evaluate(
            "(frame, html) => frame.srcdoc = html", app_html()
        )
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
        app.locator("#title").wait_for()

        sanitized = app.locator("#page-host").evaluate(
            """host => {
              const root = host.shadowRoot;
              const link = root.querySelector('#hostile-link');
              const area = root.querySelector('#hostile-area');
              const form = root.querySelector('#hostile-form');
              const input = root.querySelector('#hostile-input');
              return {
                hasBodyStyle: Boolean(root.querySelector('#hostile-style')),
                linkHref: link.getAttribute('href'),
                linkTarget: link.getAttribute('target'),
                linkEditable: link.getAttribute('contenteditable'),
                areaHref: area.getAttribute('href'),
                areaTarget: area.getAttribute('target'),
                formAction: form.getAttribute('action'),
                formTarget: form.getAttribute('target'),
                inputAction: input.getAttribute('formaction'),
                inputEditable: input.getAttribute('contenteditable'),
                inputDisabled: input.disabled,
              };
            }"""
        )
        assert sanitized == {
            "hasBodyStyle": False,
            "linkHref": None,
            "linkTarget": None,
            "linkEditable": None,
            "areaHref": None,
            "areaTarget": None,
            "formAction": None,
            "formTarget": None,
            "inputAction": None,
            "inputEditable": None,
            "inputDisabled": True,
        }

        original_url = app.url
        app.locator("#page-host").evaluate(
            """(host, href) => {
              const link = host.shadowRoot.querySelector('#hostile-link');
              link.setAttribute('href', href);
              link.click();
            }""",
            payload,
        )
        page.wait_for_timeout(250)
        assert app.url == original_url
        assert not [
            call
            for call in page.evaluate("window.calls")
            if call["method"] == "tools/call"
        ]

        containment = app.locator("#page-host").evaluate(
            """host => {
              const style = getComputedStyle(host.shadowRoot.host);
              const bar = document.querySelector('.bar').getBoundingClientRect();
              const topmost = document.elementFromPoint(bar.left + 4, bar.top + 4);
              return {
                position: style.position,
                zIndex: style.zIndex,
                transform: style.transform,
                topmostInHeader: Boolean(topmost?.closest('.bar')),
              };
            }"""
        )
        assert containment == {
            "position": "relative",
            "zIndex": "0",
            "transform": "none",
            "topmostInHeader": True,
        }
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
        app = next(
            frame for frame in page.frames if frame.parent_frame == page.main_frame
        )
        app.locator("#title").wait_for()

        assert app.locator("#comment-page").is_disabled()
        assert app.locator("#refresh").is_disabled()
        assert app.locator("#browser").is_enabled()
        assert "read-only" in app.locator("#status").text_content()
    finally:
        page.close()


# Three passages a host paints differently from the way the authored document holds them: the
# theme uppercases a table header and an eyebrow, and a <br> puts a line break where the
# page's own words run straight on. Each is ordinary authored markup — every shipped
# example carries an eyebrow — so this is what a reader points at, not an edge case.
SNAPSHOT_READING_PAGE = leaf_page(
    "snapshot reading",
    """
<section id="plan">
<h2>Plan</h2>
<p class="eyebrow">Phase one</p>
<table>
<thead><tr><th>Stage</th><th>Owner</th></tr></thead>
<tbody><tr><td>Backfill</td><td>Ana</td></tr></tbody>
</table>
<p id="wrapped">Ship the flag<br>then backfill.</p>
</section>
<p class="loose">Nothing on the page owns this line.</p>
""",
)


def open_snapshot_app(browser, page_dir):
    """The snapshot resource in a host frame, showing the page's active revision."""
    _, private = app_snapshot(str(page_dir))
    host = browser.new_page(viewport={"width": 1100, "height": 900})
    host.set_content(HOST)
    host.evaluate("leaf => window.currentLeaf = leaf", private)
    host.locator("#app").evaluate("(frame, html) => frame.srcdoc = html", app_html())
    app = next(frame for frame in host.frames if frame.parent_frame == host.main_frame)
    app.locator("#title").wait_for()
    return host, app


def send_selection(host, app, selector, text, sent, phrase=None):
    """Select an element's words in the rendered snapshot and send a comment on them.

    `phrase` picks those exact words out of the element instead of all of it. Answers
    with the event the app asked its host to apply — the whole of what this transport
    contributes to an anchor, the append gate owning everything after it.
    """
    app.evaluate(
        """([selector, phrase]) => {
          const root = document.querySelector('#page-host').shadowRoot;
          const element = root.querySelector(selector);
          const range = document.createRange();
          if (phrase === null) range.selectNodeContents(element);
          else {
            const walk = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
            let found = false;
            for (let node = walk.nextNode(); node && !found; node = walk.nextNode()) {
              const at = node.data.indexOf(phrase);
              if (at === -1) continue;
              range.setStart(node, at);
              range.setEnd(node, at + phrase.length);
              found = true;
            }
            if (!found) throw new Error(`${selector} does not say ${phrase}`);
          }
          const selected = root.getSelection();
          selected.removeAllRanges();
          selected.addRange(range);
          element.dispatchEvent(
            new MouseEvent('mouseup', {bubbles: true, composed: true}),
          );
        }""",
        [selector, phrase],
    )
    app.locator("#comment").fill(text)
    app.locator("#send").click()
    host.wait_for_function(
        "sent => window.calls.filter("
        "  call => call.method === 'tools/call'"
        "    && call.params.name === 'leaf_snapshot_apply_event'"
        ").length === sent",
        arg=sent,
    )
    return host.evaluate(
        """() => window.calls
             .filter(call => call.params?.name === 'leaf_snapshot_apply_event')
             .at(-1).params.arguments.event"""
    )


def test_the_snapshot_posts_the_passage_the_version_holds_not_the_one_it_paints(
    browser, serve
):
    """A selection's own toString() is the rendered reading, and the rendering is not the
    page's words: the theme uppercases a table header and an eyebrow, and a <br> breaks a
    run the file holds unbroken. An anchor written from it names a passage no reading of
    the version can find, so the reader is told the page never said the words in front of
    them. The app therefore reads the document's own text nodes, posts that and nothing
    else, and the append gate — the one resolver — writes the neighbours and stores the
    same anchor `leaf comment` would. The full page then paints those exact passages."""
    url = serve(SNAPSHOT_READING_PAGE)
    page_dir = serve.page_dir
    source = revision_path(page_dir, 1).read_text(encoding="utf-8")
    registry = json.loads((page_dir / "registry.json").read_text())
    cases = [
        ("p.eyebrow", "Phase one", "plan"),
        ("th", "Stage", "plan"),
        ("#wrapped", "Ship the flagthen backfill.", "wrapped"),
    ]

    host, app = open_snapshot_app(browser, page_dir)
    try:
        for sent, (selector, quote, section) in enumerate(cases, 1):
            posted = send_selection(host, app, selector, f"on {quote}", sent)
            assert posted["anchor"] == {"quote": quote, "section": section}, (
                f"{selector} posted {posted['anchor']}"
            )
            result = apply_event(str(page_dir), posted, posted["revision"])
            assert result.is_error is False, result.content[0].text
            stored = [
                event["anchor"]
                for event in read_events(page_dir)
                if event["kind"] == "comment"
            ][-1]
            assert stored == capture_anchor(source, registry, quote, section), (
                f"{selector} stored {stored}"
            )
    finally:
        host.close()

    page, errors = open_page(browser, live_url(url))
    try:
        expect(page.locator(".lf-thread")).to_have_count(3)
        expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)
        landed = page.evaluate("""() => {
            // The paint pass writes a hidden line into every commented text block, so a
            // block's own words are its text-node children rather than its childNodes.
            const words = (selector) => [
              ...document.querySelector(selector).childNodes,
            ].filter(node => node.nodeType === Node.TEXT_NODE);
            const wrapped = words('#wrapped');
            const wanted = [
              [words('#plan p.eyebrow')[0], null],
              [words('#plan th')[0], null],
              [wrapped[0], wrapped.at(-1)],
            ].map(([head, tail]) => {
              const range = document.createRange();
              range.setStart(head, 0);
              range.setEnd(tail ?? head, (tail ?? head).data.length);
              return range;
            });
            // A passage running across an element boundary paints one range per text
            // node, so each end is asked for separately.
            const painted = [...CSS.highlights.get('lf-mark')];
            const at = (want, how) => painted.filter(
              mark => mark.compareBoundaryPoints(how, want) === 0
            ).length;
            return wanted.map(want => [
              at(want, Range.START_TO_START), at(want, Range.END_TO_END),
            ]);
        }""")
        assert landed == [[1, 1], [1, 1], [1, 1]], (
            f"the marks did not land on the passages ({landed})"
        )
        assert errors == []
    finally:
        page.close()


def test_an_element_anchor_names_the_page_and_never_the_apps_own_shell(browser, serve):
    """A double press asks for the element under it, and the composed path it arrives on
    runs out through this app's shell — whose ids belong to the app, not to any version of
    the page. Reaching one would post a section the append gate can only refuse."""
    serve(SNAPSHOT_READING_PAGE)
    host, app = open_snapshot_app(browser, serve.page_dir)
    try:
        press = """(selector) => {
          const root = document.querySelector('#page-host').shadowRoot;
          root.querySelector(selector).dispatchEvent(
            new MouseEvent('dblclick', {bubbles: true, composed: true}),
          );
        }"""
        app.evaluate(press, "p.loose")
        assert not app.locator("#composer").evaluate(
            "form => form.classList.contains('open')"
        )

        app.evaluate(press, "#wrapped")
        expect(app.locator("#composer")).to_have_class("composer open")
        assert app.locator("#quote").text_content() == "On § wrapped"
    finally:
        host.close()


TWICE_PAGE = leaf_page(
    "twice",
    """
<section id="plan">
<p>The flag is off. We ship next week.</p>
<p>Later: The flag is off. We hold the release.</p>
</section>
""",
)


def test_a_refused_anchor_reaches_the_reader_with_their_draft_intact(browser, serve):
    """The gate refuses a quote no context identifies, and the reader is the one who can
    still fix it by selecting more. So the app has to hand back what the gate said —
    occurrences and all — and leave the comment where they typed it."""
    serve(TWICE_PAGE)
    page_dir = serve.page_dir
    ambiguous = {"section": "plan", "quote": "The flag is off"}
    refusal = apply_event(
        str(page_dir),
        {
            "kind": "comment",
            "revision": 1,
            "text": "Which one?",
            "anchor": ambiguous,
            "attempt": "mcp-render-ambiguous-1",
        },
        1,
    )
    assert refusal.is_error is True
    assert [
        event for event in read_events(page_dir) if event["kind"] == "comment"
    ] == []

    host, app = open_snapshot_app(browser, page_dir)
    try:
        host.evaluate("text => window.toolError = text", refusal.content[0].text)
        posted = send_selection(
            host,
            app,
            "#plan p:last-of-type",
            "Which one?",
            1,
            phrase="The flag is off",
        )
        # The app posted the very anchor the gate turned down above, so the message the
        # host is handing back is that event's own answer.
        assert posted["anchor"] == ambiguous
        expect(app.locator("#status")).to_have_class("status show error")
        status = app.locator("#status").text_content()
        assert "says 'The flag is off' 2 times" in status
        assert status.count("\n  - ") == 2
        expect(app.locator("#composer")).to_have_class("composer open")
        assert app.locator("#comment").input_value() == "Which one?"
    finally:
        host.close()
