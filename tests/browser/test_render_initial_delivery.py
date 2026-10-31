"""Authored reading and native interaction precede progressive widget rendering."""

import re

import pytest
from click.testing import CliRunner
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    leaf_page,
    open_page,
    stamp_page,
    told,
)

from leaf import cli
from leaf.render_checks import wait_until_ready


def _source():
    return leaf_page(
        "First presentation",
        '<h1>Report</h1><p><a id="early-link" href="#evidence">Read the evidence</a></p>'
        '<lf-toc id="contents" open></lf-toc>'
        '<section id="evidence"><h2>Evidence</h2><p id="prose">Read the counts.</p>'
        '</section><lf-activity id="feed"></lf-activity>'
        '<p><lf-tally id="left" for="queue" next></lf-tally></p>'
        '<section id="queue"><lf-ask id="decision"><h2>Ship it?</h2>'
        '<lf-options id="choice" choose><lf-option id="yes">Ship it</lf-option>'
        "</lf-options></lf-ask></section>",
    )


def test_reading_precedes_modules_and_widgets_restore_their_view(browser, serve):
    """Reading does not wait for modules; saved disclosure and live counts follow."""
    url = live_url(serve(_source()))
    page = open_page(browser, url)
    page.locator("#feed .lf-activity-news").click()
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    boot = []
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.reload(wait_until="commit")
        expect(page.locator("main")).to_be_visible()
        expect(page.locator("#early-link")).to_be_visible()
        assert boot, "the runtime must remain held while authored text is readable"
        boot.pop().continue_()
        page.unroute("**/leaf.js")
        wait_until_ready(page)

        expect(page.locator("main")).to_be_visible()
        expect(page.locator("#left .lf-tally-words")).to_have_text("1 left to answer")
        expect(page.locator("#left .lf-tally-next")).to_be_enabled()
        expect(page.locator("#feed .lf-activity-row")).to_be_visible()
        expect(page.locator("#feed .lf-activity-news")).to_have_attribute(
            "aria-expanded", "true"
        )
        page.keyboard.press("Tab")
        expect(page.locator("#early-link")).to_be_focused()
        summary = page.locator("#contents summary")
        summary.press("Enter")
        expect(page.locator("#contents details")).not_to_have_attribute("open", "")
        summary.press("Enter")
        expect(page.locator('#contents a[href="#evidence"]')).to_be_visible()
        page.locator("#feed .lf-activity-news").click()
        expect(page.locator("#feed .lf-activity-row")).to_be_hidden()
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.mark.parametrize("failed_file", ["registry.json", "widgets/lf-tabs.js"])
def test_a_required_startup_failure_releases_every_authored_tab(
    browser, serve, failed_file
):
    page = browser.new_page()
    held = []
    page.route("**/" + failed_file, lambda route: held.append(route))
    try:
        source = _source().replace(
            "</main>",
            '<lf-tabs id="fallback-views">'
            '<lf-tab id="first-panel" label="First"><p>First authored panel.</p></lf-tab>'
            '<lf-tab id="second-panel" label="Second"><p>Second authored panel.</p></lf-tab>'
            "</lf-tabs></main>",
        )
        with page.expect_request("**/" + failed_file):
            page.goto(serve(source), wait_until="commit")
        expect(page.locator("main")).to_be_visible()
        assert held, "the required widget must still be waiting"
        held.pop().abort()
        expect(page.locator("#prose")).to_be_visible()
        expect(page.locator("#first-panel")).to_be_visible()
        expect(page.locator("#second-panel")).to_be_visible()
        expect(
            page.get_by_text("Leaf couldn't start. Waiting for Leaf to update.")
        ).to_be_visible()
        expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
        page.keyboard.press("Tab")
        expect(page.locator("#early-link")).to_be_focused()
        consume_browser_errors(page, failed_file, "net::ERR_FAILED", "Failed to fetch")
    finally:
        for route in held:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_source_capture_precedes_authored_scripts_while_registry_loads(browser, serve):
    """One source supplies typed state and revision pairing despite deferred scripts."""
    page = browser.new_page()
    held = []
    page.route("**/registry.json", lambda route: held.append(route))
    script = """<script>
      window.captureProbeRuns = (window.captureProbeRuns || 0) + 1;
      window.captureOption = document.getElementById('yes');
      window.captureOption.setAttribute('chosen', '');
    </script>"""
    source = _source().replace("</body>", script + "</body>")
    try:
        address = live_url(serve(source))
        page.goto(address, wait_until="commit")
        page.wait_for_function("window.captureProbeRuns === 1")
        page.evaluate(
            """window.dispatchEvent(new ErrorEvent('error', {
              message: 'Nonfatal authored capture probe',
              error: new Error('Nonfatal authored capture probe')
            }))"""
        )
        expect(page.locator("html")).to_have_attribute(
            "data-lf-startup-error", re.compile("Nonfatal authored capture probe")
        )
        expect(page.locator("html")).to_have_attribute("data-lf-interactive", "")
        expect(page.locator("main")).to_be_visible()
        assert held, "typed capture must still await its registry"
        for route in held:
            route.continue_()
        held.clear()
        page.unroute("**/registry.json")
        expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
        expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
        expect(page.locator("main")).to_be_visible()
        assert (
            page.evaluate(
                """async () => (await window.__lfCheckApi()).readApplication()
              .document.authored.get('choice').state.choose.value"""
            )
            == []
        )

        stamp_page(
            serve.page_dir,
            source.replace("Read the counts.", "Read the revised counts."),
            "Revise surrounding prose",
        )
        expect(page.locator("#prose")).to_have_text("Read the revised counts.")
        assert page.evaluate(
            "window.captureProbeRuns === 1 && "
            "window.captureOption === document.getElementById('yes')"
        )
        expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
        consume_browser_errors(page, "Nonfatal authored capture probe")
    finally:
        for route in held:
            route.continue_()
        page.unroute_all(behavior="wait")


PROGRESSIVE_WIDGET = """import {LeafElement,html} from '/runtime/widget-api.js';
customElements.define('lf-progressive-proof',class extends LeafElement {
 render(){return html`<button class="proof-control">${this.getAttribute('label')}</button><slot></slot>`;}
});"""
PROGRESSIVE_REGISTRY = {
    "lf-progressive-proof": {
        "description": "A progressive widget retaining native authored children.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "label": {"type": "string"},
        },
        "additionalProperties": False,
        "required": ["id"],
        "x-content": "markup",
        "x-upgrade": True,
        "x-shadow": True,
        "x-patch": "members",
    }
}


def test_native_input_survives_progressive_render_revision_and_export(
    browser, serve, tmp_path
):
    """Upgrade keeps native focus; explicit revision activation preserves edits."""
    source = leaf_page(
        "Progressive rendering",
        '<h1>Readable first</h1><lf-progressive-proof id="proof" label="first">'
        '<p id="prose">Authored evidence.</p>'
        '<details id="early-details"><summary>Early options</summary><p>Native reading</p></details>'
        '<label>Early draft <input id="early-draft" value="authored"></label>'
        '<label><input id="early-tick" type="checkbox"> Early choice</label>'
        '<pre id="leading-code">\n\nAuthored code</pre>'
        '<label>Authored area <textarea id="authored-area">\n\nAuthored area</textarea></label>'
        '<details id="authored-default"><summary>Authored default</summary><p>Default reading</p></details>'
        "</lf-progressive-proof>",
    )
    url = live_url(
        serve(
            source,
            layer_registry=PROGRESSIVE_REGISTRY,
            layer_widgets={"lf-progressive-proof.js": PROGRESSIVE_WIDGET},
        )
    )
    page = browser.new_page()
    held = []
    page.route("**/leaf.js", lambda route: held.append(route))
    try:
        page.goto(url, wait_until="commit")
        expect(page.locator("h1")).to_be_visible()
        expect(page.locator("#proof .proof-control")).to_have_count(0)
        page.locator("#early-details summary").click()
        page.locator("#early-tick").check()
        page.locator("#early-draft").fill("Typed before upgrade")
        page.locator("#early-draft").evaluate(
            "e => {e.setSelectionRange(2,7);window.earlyInput=e;}"
        )
        assert held, "the widget must remain unupgraded during native input"
        for route in held:
            route.continue_()
        held.clear()
        page.unroute("**/leaf.js")
        wait_until_ready(page)

        expect(page.locator("#proof .proof-control")).to_have_text("first")
        expect(page.locator("#early-details")).to_have_attribute("open", "")
        assert page.evaluate("earlyInput===document.getElementById('early-draft')")
        assert page.locator("#early-draft").evaluate(
            "e => e.value==='Typed before upgrade' && e.selectionStart===2 && "
            "e.selectionEnd===7 && document.activeElement===e"
        )
        expect(page.locator("#early-tick")).to_be_checked()
        assert page.locator("#leading-code").text_content() == "\nAuthored code"
        expect(page.locator("#authored-area")).to_have_value("\nAuthored area")

        # The first revision replaces the owner: no intervening patch may refresh
        # the authored baseline and hide a preboot edit copied into that baseline.
        revised = (
            source.replace('label="first"', 'label="revised"')
            .replace(
                '<details id="authored-default">',
                '<details id="authored-default" open>',
            )
            .replace("\n\nAuthored area", "\n\nRevised area")
        )
        stamp_page(serve.page_dir, revised, "Revise widget inputs and defaults")
        told(page)
        latest = page.locator("button.lf-fp-row-notice-press")
        expect(latest).to_contain_text("Latest")
        latest.click()
        expect(page.locator("#proof .proof-control")).to_have_text("revised")
        expect(page.locator("#early-details")).to_have_attribute("open", "")
        expect(page.locator("#authored-default")).to_have_attribute("open", "")
        expect(page.locator("#early-draft")).to_have_value("Typed before upgrade")
        expect(page.locator("#early-tick")).to_be_checked()
        assert page.locator("#leading-code").text_content() == "\nAuthored code"
        expect(page.locator("#authored-area")).to_have_value("\nRevised area")

        page.evaluate(
            "window.proofButton=document.getElementById('proof').shadowRoot.querySelector('button')"
        )
        page.locator("#early-draft").click()
        page.locator("#early-draft").evaluate("e => e.setSelectionRange(2,7)")

        # A member-only revision keeps the generated control and native editor
        # nodes, including the caret, after explicit Latest activation.
        revised = revised.replace("Authored evidence.", "Revised evidence.")
        stamp_page(serve.page_dir, revised, "Revise the slotted evidence")
        told(page)
        expect(latest).to_contain_text("Latest")
        latest.click()
        expect(page.locator("#prose")).to_have_text("Revised evidence.")
        assert page.evaluate(
            "proofButton===document.getElementById('proof').shadowRoot.querySelector('button')"
        )
        assert page.locator("#early-draft").evaluate(
            "e => e.value==='Typed before upgrade' && e.selectionStart===2 && e.selectionEnd===7"
        )

        # Export keeps the stamped document over a newer working copy, and takes
        # the same ordinary render path without carrying this tab's native edits.
        (serve.page_dir / "index.html").write_text(
            revised.replace('label="revised"', 'label="unstamped"')
        )
        export = tmp_path / "proof.html"
        result = CliRunner().invoke(
            cli.cli, ["page", "export", str(serve.page_dir), "--out", str(export)]
        )
        assert result.exit_code == 0, result.output
        offline = browser.new_page()
        offline.goto(export.as_uri())
        wait_until_ready(offline)
        expect(offline.locator("#proof .proof-control")).to_have_text("revised")
        expect(offline.locator("#prose")).to_have_text("Revised evidence.")
        expect(offline.locator("#early-draft")).to_have_value("authored")
        expect(offline.locator("#early-tick")).not_to_be_checked()
    finally:
        for route in held:
            route.continue_()
        page.unroute_all(behavior="wait")
