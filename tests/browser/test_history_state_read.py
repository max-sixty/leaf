"""A document Chrome loads from its history reads the server's current state."""

from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, stamp_page, wait_for_revision


def test_a_page_loaded_from_history_reads_state_from_the_server(browser, serve):
    """A tab that held readings stores tail answers to them; Back must not hand the
    fresh document, which holds none, one of those answers from the HTTP cache."""
    source = leaf_page("History", "<h1>History</h1><p>First.</p>")
    url = live_url(serve(source))
    page = open_page(browser, url)
    for revision, sentence in enumerate(("Second.", "Third.", "Fourth."), start=2):
        stamp_page(serve.page_dir, source.replace("First.", sentence), sentence)
        wait_for_revision(page, revision)
    page.goto(url.split("?")[0].rsplit("/", 1)[0] + "/api/news")
    page.go_back()
    wait_for_revision(page, 4)
