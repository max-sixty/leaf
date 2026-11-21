"""Tests scheduled by the measured cost of their boundary."""

from urllib.parse import urlparse

import pytest
from browser.startup.test_hosting import (
    NESTED,
    SAMPLE_DOCUMENT,
    held_sample_page,
    readiness,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    holding,
    is_problem,
    leaf_page,
    open_page,
)

from leaf import server as server_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_live_page_admits_only_leaf_parents_under_its_key(browser, serve, live_leaf):
    """SameSite cookies do not isolate ports, so any server on the host can
    authenticate a frame of a live page without knowing its key. CSP keeps every
    other origin from disguising its controls, and admits another live Leaf server
    under the same key, whose page then shows the framed page live."""
    child_url, _ = live_leaf("child", "Child")
    parent_url, _ = live_leaf("parent", "Parent")
    key = server_model.host_key()
    context = browser.new_context()
    # One keyed arrival earns the cookie every same-key frame below goes out under.
    open_page(browser, f"{child_url}/?t={key}", context=context)
    foreign = open_page(
        browser,
        live_url(serve(leaf_page("Foreign", '<h1 id="foreign">Foreign</h1>'))),
        context=context,
    )
    leaf = open_page(browser, f"{parent_url}/?t={key}", context=context)
    for parent in (foreign, leaf):
        assert urlparse(parent.url).port != urlparse(child_url).port
        with parent.expect_response(f"{child_url}/") as loaded:
            parent.locator("body").evaluate(
                """async (body, url) => {
                    const frame = document.createElement('iframe');
                    frame.id = 'framed-leaf';
                    frame.src = url;
                    const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
                    body.append(frame);
                    await loaded;
                }""",
                f"{child_url}/",
            )
        response = loaded.value
        assert response.status == 200
        assert key in response.request.all_headers()["cookie"]
    errors = consume_browser_errors(foreign, "Content Security Policy")
    assert any(is_problem(error, "frame-ancestors 'self'") for error in errors), errors
    assert foreign.locator("#framed-leaf").evaluate(
        "frame => frame.contentDocument === null"
    )
    framed = leaf.frame_locator("#framed-leaf")
    expect(framed.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(framed.locator("#t")).to_have_text("Long")


def test_a_sample_counts_each_document_its_frame_loads(browser, serve):
    """A sample's child counts as arrived only once its own samples have, so the page
    holding it reads as arriving until then. A departure to a page that is not Leaf's
    ends the count of the document that left, whose inner sample never comes. Reset
    begins a document the page counts as arriving until it, and the samples inside
    it, have arrived."""
    page, _ = held_sample_page(browser, serve, NESTED, hold_first=False)
    page.locator("#outer").evaluate("sample => sample.ready")
    child = page.locator("#outer iframe").content_frame
    expect(child.locator("body")).to_have_attribute("data-lf-presented", "1")
    assert readiness(page) == "arrived"
    child.locator("#leave").click()
    wait_until_ready(page)

    # The departed document's inner sample is never answered; from here every sample
    # document waits until the step releases it. Each new document starts with its
    # admission.
    page.unroute(SAMPLE_DOCUMENT)
    admissions = []
    page.on(
        "request",
        lambda request: request.method == "HEAD" and admissions.append(request),
    )

    held = []
    page.route(SAMPLE_DOCUMENT, lambda route: held.append(route))
    page.locator("#outer").get_by_role("button", name="Reset").click()
    holding(page, admissions, 1, "the new document's sample admission")
    assert readiness(page) == "arrived"
    page.unroute(SAMPLE_DOCUMENT)
    for each in held:
        each.continue_()
    wait_until_ready(page)
