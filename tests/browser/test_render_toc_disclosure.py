"""One native contents route across in-flow and margin presentations."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, resized, told

from leaf.render_checks import rendered, wait_until_ready


def test_an_open_outline_first_paints_with_its_complete_reading_scope(browser, serve):
    """Later headings must not grow an open index above text already being read."""
    source = leaf_page(
        "initially open contents",
        """<h1 id="page-title">Field guide</h1>
<lf-tabs id="topics"><lf-tab id="topic" label="Preparation">
  <lf-toc id="contents" open></lf-toc>
  <h2 id="first">Take inventory</h2><p>Read the current counts.</p>
  <!--pause-parsing-->
  <h2 id="second">Save a snapshot</h2><p>Keep a reference.</p>
</lf-tab></lf-tabs>""",
    )
    context = browser.new_context(viewport={"width": 390, "height": 844})
    held = []
    context.route("**/parse-pause.js", lambda route: held.append(route))
    url = serve(source)

    def pause_delivery(route):
        # Authored scripts defer until parsing finishes. Interrupt the delivered
        # stream instead, to make a paint between incoming headings deterministic.
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace(
                "<!--pause-parsing-->", '<script src="/parse-pause.js"></script>'
            ),
        )

    context.route(url, pause_delivery)
    page = context.new_page()
    try:
        page.goto(url, wait_until="commit")
        page.locator("#first").wait_for(state="attached")
        page.evaluate("() => new Promise(requestAnimationFrame)")
        assert page.evaluate("document.readyState") == "loading"
        expect(page.locator("#page-title")).to_be_visible()
        expect(page.locator("#first")).to_be_hidden()
        assert page.locator("#contents li").count() == 0

        held.pop().fulfill(status=200, content_type="text/javascript", body="")
        wait_until_ready(page)
        expect(page.locator("#first")).to_be_visible()
        expect(page.locator("#second")).to_be_visible()
        expect(page.locator("#contents li a")).to_have_text(
            ["Take inventory", "Save a snapshot"]
        )
        expect(page.locator("#contents li a").first).to_be_visible()
    finally:
        for route in held:
            route.abort()


@pytest.mark.parametrize("initially_open", [False, True])
def test_contents_disclosure_keeps_its_links_focus_and_open_state(
    browser, serve, initially_open
):
    source = leaf_page(
        "adaptive contents",
        '<h1>Report</h1><aside class="sidebar"><lf-toc id="contents"'
        + (" open" if initially_open else "")
        + "></lf-toc></aside>"
        '<section id="evidence"><h2>Evidence</h2><p>Read the counts.</p></section>'
        '<section id="decision"><h2>Decision</h2><p>Choose the next step.</p></section>',
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 390, 844)
    toc = page.locator("lf-toc")
    disclosure = toc.locator("details")
    summary = toc.locator("summary")
    expect(summary).to_be_visible()
    if initially_open:
        expect(toc.get_by_role("link", name="Evidence", exact=True)).to_be_visible()
        summary.click()
    expect(disclosure).not_to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(0)
    summary.focus()
    page.keyboard.press("Enter")
    link = toc.get_by_role("link", name="Evidence", exact=True)
    expect(link).to_be_visible()
    link.focus()
    (serve.page_dir / "index.html").write_text(
        source.replace("Read the counts.", "Read the revised counts."), encoding="utf-8"
    )
    told(page)
    rendered(page)
    expect(link).to_be_focused()
    expect(disclosure).to_have_attribute("open", "")
    resized(page, 1440, 900)
    expect(summary).to_be_hidden()
    expect(link).to_be_focused()
    resized(page, 390, 844)
    expect(link).to_be_visible()
    expect(link).to_be_focused()
    summary.click()
    resized(page, 1440, 900)
    # Margin exposure is native open state, so every engine exposes the links.
    expect(disclosure).to_have_attribute("open", "")
    expect(toc.get_by_role("link", name="Evidence", exact=True)).to_be_visible()
    first_link = toc.get_by_role("link", name="Report", exact=True)
    first_link.focus()
    expect(first_link).to_be_focused()
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    resized(page, 390, 844)
    expect(disclosure).to_have_attribute("open", "")
    expect(link).to_be_focused()
    page.emulate_media(media="print")
    expect(toc.get_by_role("link", name="Report", exact=True)).to_be_visible()
    expect(link).to_be_visible()

    page.emulate_media(media="screen")
    rendered(page)
    expect(disclosure).to_have_attribute("open", "")
    summary.click()
    resized(page, 1440, 900)
    expect(disclosure).to_have_attribute("open", "")
    resized(page, 390, 844)
    expect(disclosure).not_to_have_attribute("open", "")
    page.emulate_media(media="print")
    expect(disclosure).to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(3)
    page.emulate_media(media="screen")
    expect(disclosure).not_to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(0)
