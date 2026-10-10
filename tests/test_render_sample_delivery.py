"""Opaque samples use ordinary native delivery and reconnect after a reload."""

import re
from urllib.parse import urlsplit

import pytest
from leaf.render_checks import HANDOVER_DEADLINE_MS, rendered, wait_until_ready
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    open_page,
    page_comment,
    sending,
    take_browser_errors,
    watched,
    write,
)
from test_render_controls import leaf_page


@pytest.mark.parametrize("touch", [False, True])
def test_a_sample_loads_inside_its_allocation_after_the_parent_is_usable(
    browser, serve, touch
):
    """Parent interaction and layout settle before its contained documents."""
    source = leaf_page(
        "Independent sample arrival",
        """<h1>Containing page</h1>
<lf-sample id="practice" label="Practice">
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <p>Read the whole example by scrolling inside this frame.</p>
    """
        + "<p>A longer passage in the practice page.</p>" * 15
        + """<button id="last-control">Last control</button>
  </template>
</lf-sample>
<p id="following">The surrounding page keeps its place.</p>""",
    )
    page = browser.new_page(
        viewport={"width": 390 if touch else 1200, "height": 900}, has_touch=touch
    )
    watched(page)
    allocations = []
    histories = []
    page.route("**/api/samples", lambda route: allocations.append(route))
    history = re.compile(r"/api/samples/[^/]+/api/state(?:\?.*)?$")
    page.route(history, lambda route: histories.append(route))
    page.goto(serve(source), wait_until="load")
    holding(page, allocations, 1, "the sample's allocation")
    wait_until_ready(page, through="arrived")
    assert (
        page.evaluate(
            "document.querySelector('script[data-lf-entry]').lfReadiness(null)"
        )
        == "contained"
    )
    sample = page.locator("#practice")
    expect(sample.locator(".lf-sample-status")).to_have_text("Loading sample…")
    expect(sample.get_by_role("button", name="Reset", exact=True)).to_have_attribute(
        "aria-disabled", "true"
    )
    draft = page_comment(page)
    write(draft, "The surrounding page already accepts comments.")
    with sending(page, "the parent comment while its sample waits"):
        draft.press("ControlOrMeta+Enter")
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-thread")).to_contain_text(
        "The surrounding page already accepts comments."
    )
    page.keyboard.press("Escape")

    frame = sample.locator("iframe")
    sample.scroll_into_view_if_needed()
    before = frame.bounding_box()
    following = page.locator("#following").bounding_box()
    allocations.pop().continue_()
    holding(page, histories, 1, "the child's private history")
    child = frame.element_handle().content_frame()
    expect(child.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(sample.locator(".lf-sample-status")).to_have_text("Loading sample…")
    wait_until_ready(page, through="arrived")
    assert (
        page.evaluate(
            "document.querySelector('script[data-lf-entry]').lfReadiness(null)"
        )
        == "contained"
    )
    assert frame.bounding_box() == before
    assert page.locator("#following").bounding_box() == following

    page.unroute(history)
    for route in histories:
        route.continue_()
    wait_until_ready(page)
    rendered(page)
    expect(sample.locator(".lf-sample-status")).to_be_empty()
    assert frame.bounding_box() == before
    assert page.locator("#following").bounding_box() == following
    child.get_by_role("button", name="Last control").click()
    assert child.evaluate("scrollY") > 0
    assert frame.bounding_box() == before

    full = sample.get_by_role("button", name="Full view", exact=True)
    if touch:
        full.tap()
    else:
        sample.get_by_role("button", name="Reset", exact=True).focus()
        page.keyboard.press("Tab")
        expect(full).to_be_focused()
        page.keyboard.press("Enter")
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    expect(child.locator("html")).not_to_have_attribute("data-lf-sample-block", "")
    rendered(page)
    rendered(child)
    assert frame.bounding_box()["height"] > before["height"]
    if touch:
        back.tap()
    else:
        page.keyboard.press("Escape")
    expect(full).to_be_focused()
    expect(child.locator("html")).to_have_attribute("data-lf-sample-block", "")
    rendered(page)
    rendered(child)
    assert frame.bounding_box()["height"] == before["height"]


@pytest.mark.parametrize("as_window,zoom", [(False, 0.8), (True, 1.25)])
def test_sample_inspection_restores_its_embedded_reading_at_css_zoom(
    browser, serve, as_window, zoom
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Inspect a practice reading",
                f'<h1>Containing page</h1><div id="sample-allocation"><lf-sample id="practice" {"window" if as_window else ""}>'
                '<template id="practice-source" data-sample><h1>Practice</h1>'
                + "".join(
                    f"<p>Passage {index}. A longer passage in the practice page.</p>"
                    for index in range(30)
                )
                + '<lf-draft id="practice-notes"><pre>Practice notes.</pre></lf-draft>'
                '<button id="last-control">Last control</button></template></lf-sample></div>'
                '<p id="following">The following passage keeps its place.</p>'
                '<button id="outside-control">Keep reading the page</button>',
                head=f"<style>main {{ zoom: {zoom}; }} #sample-allocation {{ display: flow-root; }}"
                + ("" if as_window else "#practice .lf-sample-frame { height: 20rem; }")
                + "</style>",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    if not as_window:
        assert (
            sample.locator("iframe").evaluate("frame => getComputedStyle(frame).height")
            == "320px"
        )
    child = sample.locator("iframe").element_handle().content_frame()
    if as_window:
        child.get_by_role("button", name="Last control").focus()
        child.get_by_role("button", name="Last control").press("Enter")
    else:
        edit = child.locator('#practice-notes [data-lf-draft-action="edit"]')
        edit.focus()
        edit.press("Enter")
        editor = child.get_by_role("textbox", name="Edit practice-notes", exact=True)
        write(editor, "Unsent practice notes.")
        child.get_by_role("button", name="Last control").scroll_into_view_if_needed()
        expect(editor).to_be_focused()
    rendered(child)
    embedded_scroll = child.evaluate("scrollY")
    assert embedded_scroll > 500
    full = sample.get_by_role("button", name="Full view", exact=True)
    full.focus()
    following = page.locator("#following").bounding_box()["y"]
    page.keyboard.press("Enter")
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    assert abs(page.locator("#following").bounding_box()["y"] - following) <= 1
    back.click()
    expect(full).to_be_focused()
    child.wait_for_function("y => Math.abs(scrollY - y) <= 1", arg=embedded_scroll)

    assert abs(page.locator("#following").bounding_box()["y"] - following) <= 1
    if not as_window:
        expect(editor).to_have_js_property("value", "Unsent practice notes.")

    if as_window:
        return
    # This fixture varies the child's allocation independently of its containing
    # page, so keep the already-drawn outer sample allocation unchanged.
    page.locator("#sample-allocation").evaluate(
        "holder => holder.style.height = getComputedStyle(holder).height"
    )
    # Change the allocation while Return is crossing the private port. Native
    # resize and command delivery can arrive in either order; the child owns
    # completing its reading against the viewport it actually receives.
    original_height = child.evaluate("innerHeight")
    page.evaluate("""() => {
      const port = document.querySelector('script[data-lf-entry]').lfDocumentPort;
      const send = port.postMessage;
      port.postMessage = function(message, ...args) {
        if (message.method === 'inspection' && !message.detail.opening) {
          const frame = document.querySelector('#practice iframe');
          window.returnAllocation = true;
          frame.style.height = '10rem';
          port.postMessage = send;
        }
        return send.call(this, message, ...args);
      };
    }""")
    full.click()
    expect(back).to_be_focused()
    back.click()
    expect(full).to_be_focused()
    page.wait_for_function("returnAllocation !== undefined")
    child.wait_for_function("height => innerHeight < height", arg=original_height)
    child.wait_for_function("y => Math.abs(scrollY - y) <= 1", arg=embedded_scroll)
    sample.locator("iframe").evaluate("frame => frame.style.removeProperty('height')")
    child.wait_for_function("height => innerHeight === height", arg=original_height)
    rendered(child)

    # A return's late acknowledgement must not clear the place captured by a
    # subsequent inspection. Hold only the reply, leaving both documents live.
    page.evaluate("""() => {
      const port = document.querySelector('script[data-lf-entry]').lfDocumentPort;
      const send = port.postMessage;
      const receive = port.onmessage;
      window.returnReply = {port, receive, holding:true, method:'window', id:null, message:null};
      port.postMessage = function(message, ...args) {
        if (returnReply.holding && message.method === returnReply.method &&
            (message.detail.opening || message.detail.window === false))
          returnReply.id = message.id;
        return send.call(this, message, ...args);
      };
      port.onmessage = function(event) {
        if (returnReply.holding && event.data.id === returnReply.id) {
          returnReply.message = event.data;
          return;
        }
        return receive.call(this, event);
      };
    }""")
    full.click()
    expect(back).to_be_focused()
    back.click()
    expect(full).to_be_focused()
    page.wait_for_function("returnReply.message !== null")
    full.click()
    expect(back).to_be_focused()
    page.evaluate("""() => {
      returnReply.holding = false;
      returnReply.receive.call(returnReply.port, new MessageEvent('message', {
        data:returnReply.message,
      }));
    }""")
    back.click()
    expect(full).to_be_focused()
    child.wait_for_function("y => Math.abs(scrollY - y) <= 1", arg=embedded_scroll)

    # Repeated Full view presses renew the pending action, without enlarging
    # the viewport before the child has captured its original reading.
    page.evaluate("""() => Object.assign(returnReply, {
      holding:true, method:'inspection', id:null, message:null,
    })""")
    full.click()
    page.wait_for_function("returnReply.message !== null")
    expect(full).to_be_focused()
    full.click()
    expect(back).not_to_be_visible()
    expect(full).to_be_focused()
    assert child.evaluate("innerHeight") == original_height
    page.evaluate("""() => {
      returnReply.holding = false;
      returnReply.receive.call(returnReply.port, new MessageEvent('message', {
        data:returnReply.message,
      }));
    }""")
    expect(back).to_be_focused()
    back.click()
    expect(full).to_be_focused()
    child.wait_for_function("y => Math.abs(scrollY - y) <= 1", arg=embedded_scroll)

    # A different parent action supersedes a waiting Full view press. Its late
    # capture reply must not open the dialog or take that action's focus.
    page.evaluate("""() => Object.assign(returnReply, {
      holding:true, method:'inspection', id:null, message:null,
    })""")
    full.click()
    page.wait_for_function("returnReply.message !== null")
    outside = page.get_by_role("button", name="Keep reading the page", exact=True)
    outside.click()
    page.evaluate("""() => {
      returnReply.holding = false;
      returnReply.receive.call(returnReply.port, new MessageEvent('message', {
        data:returnReply.message,
      }));
    }""")
    rendered(page)
    expect(back).not_to_be_visible()
    expect(outside).to_be_focused()

    # Hold an expanded native allocation through the initial Return paint.
    # A newer child key action owns its reading; the later compact resize
    # must not reapply Return's superseded bookmark.
    page.evaluate("""() => {
      const port = document.querySelector('script[data-lf-entry]').lfDocumentPort;
      const send = port.postMessage;
      port.postMessage = function(message, ...args) {
        if (message.method === 'inspection' && !message.detail.opening) {
          document.querySelector('#practice iframe').style.height = '1000px';
          port.postMessage = send;
        }
        return send.call(this, message, ...args);
      };
    }""")
    full.click()
    expect(back).to_be_focused()
    back.click()
    child.wait_for_function("height => innerHeight > height", arg=original_height)
    rendered(child)
    child.get_by_role("button", name="Last control").press("Enter")
    newer_scroll = child.evaluate("scrollY")
    assert abs(newer_scroll - embedded_scroll) > 1
    sample.locator("iframe").evaluate("frame => frame.style.height = '10rem'")
    child.wait_for_function("height => innerHeight < height", arg=original_height)
    rendered(child)
    assert abs(child.evaluate("scrollY") - newer_scroll) <= 1
    # That newer reading also becomes the next inspection's own bookmark.
    full.click()
    expect(back).to_be_focused()
    back.click()
    child.wait_for_function("y => Math.abs(scrollY - y) <= 1", arg=newer_scroll)


def test_samples_keep_native_loaders_forms_and_reload(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native sample delivery",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <link rel="stylesheet" href="/page/native.css">
    <img src="/page/native.svg" alt="Native resource">
    <form id="form"><button id="submit">Submit</button></form>
    <button id="popup">Open window</button>
    <lf-sample id="nested" label="Nested practice" window>
      <template id="nested-source" data-sample><h1>Nested page</h1></template>
    </lf-sample>
    <script type="module" src="/page/native.js"></script>
  </template>
</lf-sample>
""",
            ),
            page_files={
                "native.css": "h1 { color: rgb(12, 34, 56); }",
                "native.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20"/></svg>',
                "native.js": """
window.nativeModuleUrl = import.meta.url;
window.nativeXhr = () => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', new URL('native.css', import.meta.url));
  xhr.onload = () => resolve({status: xhr.status, text: xhr.responseText});
  xhr.onerror = reject;
  xhr.send();
});
window.nativeImage = () => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image.naturalWidth);
  image.onerror = reject;
  image.src = new URL('native.svg', import.meta.url);
});
document.querySelector('#form').addEventListener('submit', event => {
  event.preventDefault();
  window.submitted = true;
});
document.querySelector('#popup').addEventListener('click', () => {
  window.open('about:blank', '_blank');
});
""",
            },
        ),
    )
    sample = page.locator("#practice")
    sample.locator("iframe").wait_for(state="attached")
    child = sample.locator("iframe").element_handle().content_frame()
    child.wait_for_function(
        "document.body?.hasAttribute('data-lf-presented')", timeout=HANDOVER_DEADLINE_MS
    )
    sample.evaluate("async sample => await sample.ready")
    child.wait_for_function("!!window.nativeXhr")
    assert child.evaluate("nativeModuleUrl").startswith("http:")
    assert child.evaluate("nativeXhr()") == {
        "status": 200,
        "text": "h1 { color: rgb(12, 34, 56); }",
    }
    assert child.evaluate("nativeImage()") == 20
    expect(child.locator("h1").first).to_have_css("color", "rgb(12, 34, 56)")
    child.locator("#submit").click()
    assert child.evaluate("submitted")
    with page.expect_popup() as popup:
        child.locator("#popup").click()
    popup.value.close()
    nested = child.locator("#nested")
    nested.evaluate("async sample => await sample.ready")
    grandchild = nested.locator("iframe").element_handle().content_frame()
    expect(grandchild.locator("h1")).to_have_text("Nested page")
    child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      const response = await fetch('api/event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'Leaf-Layer': state.layer.generation},
        body: JSON.stringify({kind: 'comment', revision: 1, text: 'Keep through reload', attempt: 'native-reload-comment'}),
      });
      if (!response.ok) throw new Error(await response.text());
    }""")
    # Reload again as soon as parsing finishes, before waiting for presentation.
    for _ in range(2):
        with child.expect_navigation(wait_until="domcontentloaded"):
            child.evaluate("location.reload()")
    child.wait_for_function("document.body?.hasAttribute('data-lf-presented')")
    expect(child.locator("h1").first).to_have_text("Practice page")
    child.wait_for_function("!!window.nativeXhr")
    sample.evaluate("async sample => await sample.ready")
    assert child.evaluate("nativeXhr()")["status"] == 200
    assert child.evaluate("""async () => {
      const state = await (await fetch('api/state')).json();
      return state.events.some(event => event.text === 'Keep through reload');
    }""")


@pytest.mark.parametrize("status", [404, 200])
@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_sample_document_without_bootstrap_retires_and_can_reset(
    request, serve, status, engine
):
    """Initial admission rejects a non-Leaf response and permits immediate Reset."""
    url = serve(
        leaf_page(
            "Sample document failure",
            '<h1>Sample document failure</h1><lf-sample id="practice">'
            '<template id="practice-source" data-sample><h1>Practice</h1></template>'
            "</lf-sample>",
        )
    )
    page = request.getfixturevalue(engine).new_page()
    held = []
    navigation = re.compile(r"/api/samples/[^/]+/$")
    page.route(navigation, lambda route: held.append(route))
    page.goto(url, wait_until="domcontentloaded")
    sample = page.locator("#practice")
    holding(page, held, 1, "the failed sample document")
    failed_url = held[0].request.url
    held[0].fulfill(
        status=status,
        content_type="text/html",
        body="<html><body>Unavailable</body></html>",
    )
    expect(sample.locator(".lf-sample-status")).to_have_text(
        "The sample document did not start Leaf"
    )
    assert (
        sample.evaluate(
            "sample => sample.ready.then(() => null, error => error.message)"
        )
        == "The sample document did not start Leaf"
    )
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    assert page.request.get(failed_url + "api/state").status == 404
    sample.get_by_role("button", name="Full view", exact=True).click()
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    back.click()
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    page.unroute(navigation)
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice"
    )
    if status == 404:
        consume_browser_errors(page, "404", "The sample document did not start Leaf")


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
@pytest.mark.parametrize("navigation", ["form", "script"])
def test_sample_native_departure_keeps_destination_and_reset(
    request, serve, engine, navigation
):
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Native departure",
                """
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1>
    <form action="https://docs.example.invalid/reference.html" method="get">
      <input name="q" value="term"><button>Search docs</button>
    </form>
  </template>
</lf-sample>
""",
            )
        ),
    )
    page.route(
        "https://docs.example.invalid/**",
        lambda route: route.fulfill(
            content_type="text/html", body="<!doctype html><h1>External reference</h1>"
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    previous = child.url
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
      registerSampleCommand('thread', () => {
        window.waitingCommand = true;
        return new Promise(() => {});
      });
    }""")
    sample.evaluate("""sample => {
      window.departedCall = sample.showThread('pending').then(
        () => 'completed', error => error.name);
    }""")
    child.wait_for_function("window.waitingCommand")
    assert take_browser_errors(page) == []
    # Exercise departure while the real feed has a native read outstanding.
    # WebKit stops the old document's loads when navigation starts, before
    # pagehide. Reads during that interval are logged as access-control refusals.
    held = []
    page.route(previous + "api/news", lambda route: held.append(route))
    holding(page, held, 1, "the departing document's freshness read")
    with page.expect_event(
        "requestfailed", predicate=lambda request: request == held[0].request
    ):
        if navigation == "form":
            child.get_by_role("button", name="Search docs").click()
        else:
            child.evaluate(
                "location.assign('https://docs.example.invalid/reference.html')"
            )
    expect(child.get_by_role("heading")).to_have_text("External reference")
    assert page.evaluate("window.departedCall") == "AbortError"
    assert (
        sample.evaluate(
            "sample => sample.ready.then(() => 'ready', error => error.name)"
        )
        == "AbortError"
    )
    assert (
        sample.evaluate(
            "sample => sample.showThread('departed').then(() => 'completed', error => error.name)"
        )
        == "AbortError"
    )
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    sample.get_by_role("button", name="Full view", exact=True).click()
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    expect(child.get_by_role("heading")).to_have_text("External reference")
    back.click()
    reset.click()
    sample.evaluate("async sample => await sample.ready")
    expect(sample.frame_locator("iframe").get_by_role("heading")).to_have_text(
        "Practice page"
    )
    replacement = sample.locator("iframe").element_handle().content_frame()
    # Only account for teardown refusals from the proven departing capability.
    # The replacement and the fresh revoked-capability probe below stay strict.
    departed = urlsplit(previous)
    cancellation_error = re.compile(
        rf".*{re.escape(departed.netloc + departed.path)}\S*"
        r" due to access control checks\."
    )
    departure_errors = take_browser_errors(page)
    assert all(cancellation_error.fullmatch(error) for error in departure_errors), (
        departure_errors
    )
    # A fresh header forces a new native preflight rather than reusing the old
    # document's cached one. Revocation must remain an HTTP refusal in both engines.
    assert (
        replacement.evaluate(
            """async previous => {
          const response = await fetch(new URL('api/state', previous), {
            headers: {'X-Leaf-Revocation-Probe': 'fresh'},
          });
          return response.status;
        }""",
            previous,
        )
        == 404
    )
    consume_browser_errors(page, "404 " + previous + "api/state")


@pytest.mark.parametrize("action", ["departure", "reset", "parent"])
def test_sample_pending_full_view_survives_departure_only_under_its_press(
    browser, serve, action
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Pending inspection",
                """<h1>Containing page</h1>
<button id="outside">Keep reading the page</button>
<lf-sample id="practice" label="Practice">
  <template id="practice-source" data-sample><h1>Practice page</h1></template>
</lf-sample>""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
      registerSampleCommand('inspection', () => {
        window.waitingCapture = true;
        return new Promise(() => {});
      });
    }""")
    full = sample.get_by_role("button", name="Full view", exact=True)
    back = sample.get_by_role("button", name="Return to page", exact=True)
    full.click()
    child.wait_for_function("window.waitingCapture")
    expect(back).not_to_be_visible()
    if action == "reset":
        reset = sample.get_by_role("button", name="Reset", exact=True)
        reset.click()
        sample.evaluate("async sample => await sample.ready")
        expect(back).not_to_be_visible()
        expect(reset).to_be_focused()
    else:
        outside = page.get_by_role("button", name="Keep reading the page", exact=True)
        if action == "parent":
            outside.click()
        page.route(
            "https://docs.example.invalid/**",
            lambda route: route.fulfill(
                content_type="text/html",
                body="<!doctype html><h1>External reference</h1>",
            ),
        )
        child.evaluate("location.assign('https://docs.example.invalid/reference.html')")
        expect(child.get_by_role("heading")).to_have_text("External reference")
        rendered(page)
        if action == "departure":
            expect(back).to_be_focused()
            back.click()
            expect(full).to_be_focused()
        else:
            expect(back).not_to_be_visible()
            expect(outside).to_be_focused()
