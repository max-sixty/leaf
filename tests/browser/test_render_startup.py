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


import pytest
from render_harness import (
    leaf_page,
    page_comment,
    refuse,
    round_trip,
    select_words,
    watched,
    write,
)

from leaf.render_checks import wait_until_ready


@pytest.mark.shifts_unsurveyed
def test_offline_reaction_waits_for_its_saved_state(browser, serve):
    """An unknown saved state cannot invent an add; recovery toggles the actual saved event."""
    source = leaf_page(
        "Saved reaction", '<h1>Saved reaction</h1><button id="target">A target</button>'
    )
    saved = {
        "id": "saved-reaction",
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "keep",
        "anchor": {"section": "target"},
    }
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    posts = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            else None
        ),
    )
    page.route("**/api/state*", refuse)
    page.goto(serve(source, events=[saved]), wait_until="load")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile("Lost the connection")
    )
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    assert posts == []
    select_words(page, "#target")
    page.keyboard.press("c")
    page.keyboard.press("Tab")
    chip = page.locator('.lf-response-options .lf-react[data-token="keep"]')
    expect(chip).to_have_attribute("aria-disabled", "true")
    chip.dispatch_event("click")
    chip.focus()
    page.keyboard.press("Space")
    assert posts == []
    page.keyboard.press("Escape")
    page.unroute("**/api/state*")
    wait_until_ready(page)
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    round_trip(page)
    assert [(post["kind"], post.get("undoes")) for post in posts] == [
        ("undo", "saved-reaction")
    ]


@pytest.mark.shifts_unsurveyed
def test_opt_in_page_interface_joins_initial_widget_settlement(browser, serve):
    """Page interface preparation holds the first widget upgrade."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.add_init_script(
        """
        document.addEventListener('lf-page-interface', event => {
          event.detail.present(new Promise(resolve => {
            window.releaseHeldPageInterface = resolve;
          }));
        });
        """
    )
    page.goto(
        serve(leaf_page("Held interface", "<h1>Held interface</h1>")),
        wait_until="load",
    )
    page.wait_for_function("() => window.releaseHeldPageInterface !== undefined")
    page.evaluate(
        """async () => {
          const {nextFrame} = await window.__lfWidgetApi();
          await new Promise(resolve => nextFrame(() => nextFrame(resolve)));
        }"""
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-upgraded", "1")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    page.evaluate("releaseHeldPageInterface()")
    wait_until_ready(page)


@pytest.mark.shifts_unsurveyed
@pytest.mark.parametrize("answer", ["ready", "offline"])
@pytest.mark.parametrize("focus", ["sample", "chrome"])
def test_first_history_answer_keeps_an_open_quote_draft(browser, serve, answer, focus):
    """Presentation applies saved facts without re-deciding the user's open composer."""
    source = leaf_page(
        "Uninterrupted draft",
        '<h1>Uninterrupted draft</h1><p id="passage">The prototype needs a mobile check.</p>'
        '<lf-sample id="practice" label="Practice" window>'
        '<template id="practice-source" data-sample>'
        '<h1>Practice</h1><button id="inspect">Inspect</button>'
        "</template></lf-sample>",
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(source), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    select_words(page, "#passage")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "Keep these words.")
    field.evaluate("field => field.setSelectionRange(7, 7)")
    if focus == "sample":
        child = page.locator("#practice iframe").element_handle().content_frame()
        child.locator("#inspect").click()
    else:
        page.locator(".lf-fp-leaf").focus()
        page.evaluate("getSelection().removeAllRanges()")
    expect(field).to_be_visible()
    page.unroute("**/api/state*")
    for route in held:
        if answer == "ready":
            route.continue_()
        else:
            route.abort("internetdisconnected")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", "Keep these words.")
    assert field.evaluate("field => [field.selectionStart, field.selectionEnd]") == [
        7,
        7,
    ]
    expect(page.get_by_role("status").filter(has_text="Draft kept")).to_have_count(0)
    if answer == "offline":
        consume_browser_errors(page, "net::ERR_INTERNET_DISCONNECTED")


@pytest.mark.shifts_unsurveyed
def test_bad_shadow_words_after_upgrade_keep_the_page_usable(browser, serve):
    entry = {
        "description": "Late shadow words.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-shadow": True,
        "x-example": '<lf-probe id="probe"></lf-probe>',
    }
    widget = """import {once, shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-probe',class extends HTMLElement {connectedCallback(){if(!once(this))return;const p=document.createElement('p');p.textContent='Good words';shadowStage(this,[p]);}});"""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/api/state*", lambda r: held.append(r))
    page.goto(
        serve(
            leaf_page(
                "Late shadow", '<h1>Late shadow</h1><lf-probe id="probe"></lf-probe>'
            ),
            layer_registry={"lf-probe": entry},
            layer_widgets={"lf-probe.js": widget},
        ),
        wait_until="load",
    )
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    page.evaluate(
        """async()=>{const host=document.querySelector('lf-probe');host.shadowRoot.append(document.createTextNode('Broken author words'));const {textNodesUnder}=await window.__lfCheckApi();[...textNodesUnder(document.body)];}"""
    )
    assert page.evaluate("document.documentElement.hasAttribute('data-lf-interactive')")
    expect(
        page.get_by_role("status").filter(has_text="Leaf couldn't start")
    ).to_have_count(0)
    consume_browser_errors(page, "staged bare text")
    page.unroute("**/api/state*")
    for r in held:
        r.continue_()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    select_words(page, "h1")
    page.keyboard.press("c")
    write(page_comment(page), "Still usable.")
    expect(page_comment(page)).to_have_js_property("value", "Still usable.")
