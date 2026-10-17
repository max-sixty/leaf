"""One native contents route across in-flow and margin presentations."""

from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, resized, told


def test_contents_disclosure_keeps_its_links_focus_and_open_state(browser, serve):
    source = leaf_page(
        "adaptive contents",
        '<h1>Report</h1><aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>'
        '<section id="evidence"><h2>Evidence</h2><p>Read the counts.</p></section>'
        '<section id="decision"><h2>Decision</h2><p>Choose the next step.</p></section>',
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 390, 844)
    toc = page.locator("lf-toc")
    disclosure = toc.locator("details")
    summary = toc.locator("summary")
    expect(summary).to_be_visible()
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
