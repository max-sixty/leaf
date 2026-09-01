"""The MCP App bridge renders a page and returns durable feedback to its host."""

from leaf.mcp_app import ack_delivery, app_html, app_snapshot, apply_event

HOST = """<!doctype html>
<iframe id="app" style="width:100%;height:760px;border:0"></iframe>
<script>
window.calls = [];
window.currentLeaf = null;
window.failContextClear = false;
window.holdNextMessage = false;
window.heldMessage = null;
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
    if (name === "leaf_apply_event") {
      window.currentLeaf = {
        ...window.currentLeaf,
        eventSeq: window.currentLeaf.eventSeq + 1,
        delivery: '{"page":"test"}\\n{"kind":"comment","seq":1}',
        deliverySeq: window.currentLeaf.eventSeq + 1,
      };
    }
    if (name === "leaf_delivery_ack") {
      window.currentLeaf = {...window.currentLeaf, delivery: null, deliverySeq: null};
    }
    answer(event.source, message.id, toolResult(window.currentLeaf));
    return;
  }
  if (["ui/update-model-context", "ui/message"].includes(message.method)) {
    if (message.method === "ui/update-model-context" &&
        message.params.content?.length === 0 && window.failContextClear) {
      refuse(event.source, message.id, "Context clear denied");
      return;
    }
    if (message.method === "ui/message" &&
        !Array.isArray(message.params.content)) {
      refuse(event.source, message.id, "Message content must be an array");
      return;
    }
    if (message.method === "ui/message" && window.holdNextMessage) {
      window.holdNextMessage = false;
      window.heldMessage = {target: event.source, id: message.id};
      return;
    }
    answer(event.source, message.id, {});
    return;
  }
  if (message.id !== undefined) answer(event.source, message.id, {});
});
</script>
"""


def test_mcp_app_renders_general_and_anchored_feedback_and_hands_it_off(
    browser, page_dir
):
    standing = apply_event(
        str(page_dir),
        {
            "kind": "comment",
            "revision": 1,
            "text": "A standing thread already belongs to the durable page.",
            "attempt": "mcp-standing-thread-1",
        },
        1,
    )
    ack_delivery(str(page_dir), standing.meta["leaf"]["deliverySeq"])
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
        page.evaluate("window.holdNextMessage = true")
        app.locator("#send").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'ui/message').length === 1"
        )
        calls = page.evaluate("window.calls")
        assert not [
            call
            for call in calls
            if call["method"] == "tools/call"
            and call["params"]["name"] == "leaf_delivery_ack"
        ]
        page.evaluate("window.releaseMessage()")
        page.wait_for_function(
            """() => window.calls.filter(call =>
              call.method === 'tools/call' &&
              call.params.name === 'leaf_delivery_ack'
            ).length === 1"""
        )

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

        page.evaluate("window.failContextClear = true")
        app.locator("#send").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'ui/message').length === 2"
        )

        calls = page.evaluate("window.calls")
        applies = [
            call
            for call in calls
            if call["method"] == "tools/call"
            and call["params"]["name"] == "leaf_apply_event"
        ]
        assert "anchor" not in applies[0]["params"]["arguments"]["event"]
        anchor = applies[1]["params"]["arguments"]["event"]["anchor"]
        assert anchor["quote"] == "The cutoff lives in"
        assert anchor["section"] == "plan"
        assert "prefix" not in anchor
        assert "suffix" not in anchor
        assert (
            len(
                [
                    call
                    for call in calls
                    if call["method"] == "tools/call"
                    and call["params"]["name"] == "leaf_delivery_ack"
                ]
            )
            == 2
        )
        context_updates = [
            call for call in calls if call["method"] == "ui/update-model-context"
        ]
        assert len(context_updates) == 4
        assert context_updates[-1]["params"] == {"content": []}
        messages = [call for call in calls if call["method"] == "ui/message"]
        assert all(isinstance(call["params"]["content"], list) for call in messages)
        assert "Feedback sent to Codex" in app.locator("#status").text_content()

        assert app.locator("#browser").inner_text() == "Full page"
        app.locator("#browser").click()
        page.wait_for_function(
            "() => window.calls.filter(call => call.method === 'ui/message').length === 3"
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
