"""Tests scheduled by the measured cost of their boundary."""

from urllib.parse import urlparse

import pytest
from browser.startup.test_hosting import (
    CHOICE,
    NESTED,
    SAMPLE_DOCUMENT,
    held_sample_page,
    live_sample,
    readiness,
    rolling_out,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    holding,
    http_error_console,
    is_problem,
    leaf_page,
    open_page,
    watched,
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


def test_a_sample_waits_out_a_release_still_rolling_out(browser, serve):
    """A sample allocated while the rollout lasts reads as loading through the wait
    the answer names, asks again, and arrives. It is in view as the page opens, where
    its load would hold the page's presentation, but the page doesn't wait with it: it
    comes up and takes a choice meanwhile, and the sample arrives as one below the
    window does, its frame keeping its height until the reader acts in it."""
    page = browser.new_page(viewport={"width": 1200, "height": 1200})
    watched(page)
    asked, end = rolling_out(page)
    page.goto(
        serve(leaf_page("Rollout", "<h1>Rollout</h1>" + CHOICE + live_sample("s"))),
        wait_until="commit",
    )
    holding(page, asked, 2, "the allocation asked again")
    assert asked[1][0] - asked[0][0] >= 1
    status = page.locator("#s .lf-sample-status")
    expect(status).to_have_text("Loading sample…")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    page.locator("#yes").click()
    expect(page.locator("#yes")).to_have_attribute("chosen", "")
    frame = page.locator("#s iframe")
    height = "frame => frame.getBoundingClientRect().height"
    waiting_height = frame.evaluate(height)
    end()
    page.locator("#s").evaluate("sample => sample.ready")
    wait_until_ready(page)
    expect(status).to_have_text("")
    assert frame.evaluate(height) == waiting_height
    consume_browser_errors(page, http_error_console(503))


def test_a_sample_queued_behind_a_rollout_leaves_the_page_live(browser, serve):
    """A page loads three samples at once, so a fourth waits for a slot and asks the
    server nothing while the rollout lasts. It hears that the loads ahead of it are
    waiting, so four samples in view still let the page come up and take a choice."""
    page = browser.new_page(viewport={"width": 1200, "height": 3600})
    watched(page)
    asked, end = rolling_out(page)
    samples = "".join(live_sample(f"s{each}") for each in range(4))
    page.goto(
        serve(leaf_page("Four", "<h1>Four</h1>" + CHOICE + samples)),
        wait_until="commit",
    )
    holding(page, asked, 3, "the three allocations a page makes at once")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    page.locator("#yes").click()
    expect(page.locator("#yes")).to_have_attribute("chosen", "")
    expect(page.locator(".lf-sample-status")).to_have_text(["Loading sample…"] * 4)
    # Whichever sample mounted last is the one queued.
    assert len({template for _, template in asked}) == 3
    end()
    wait_until_ready(page)
    expect(page.locator(".lf-sample-status")).to_have_text([""] * 4)
    consume_browser_errors(page, http_error_console(503))


def test_a_sample_removed_during_a_rollout_stops_asking(browser, serve):
    """A sample removed while it waits out the rollout asks the server no more, so it
    allocates nothing when the rollout ends."""
    page = browser.new_page(viewport={"width": 1200, "height": 1800})
    watched(page)
    asked, end = rolling_out(page)
    page.goto(
        serve(
            leaf_page(
                "Removed",
                "<h1>Removed</h1>" + live_sample("gone") + live_sample("kept"),
            )
        ),
        wait_until="commit",
    )
    holding(page, asked, 2, "both samples' first allocations")
    page.locator("#gone").evaluate("sample => sample.remove()")
    removed = len(asked)
    # Each sample asks again a second after its answer, so the kept sample's second ask
    # after the removal comes after the removed one's next would have.
    kept = []
    page.on(
        "request",
        lambda request: (
            request.url.endswith("/api/samples")
            and request.post_data_json["template"] == "kept-source"
            and kept.append(request)
        ),
    )
    holding(page, kept, 2, "the kept sample asking twice after the removal")
    assert [template for _, template in asked[removed:]].count("gone-source") == 0
    end()
    page.locator("#kept").evaluate("sample => sample.ready")
    wait_until_ready(page)
    assert [template for _, template in asked[removed:]].count("gone-source") == 0
    consume_browser_errors(page, http_error_console(503))
