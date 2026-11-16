"""The activity feed: how it words a pick, holds arrivals until the reader reveals them,
and prints its complete history."""

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    leaf_page,
    open_page,
    round_trip,
    stamp_page,
    told,
    wait_for_revision,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_activity_feed_words_a_pick_in_the_document_it_was_made_in(browser, serve):
    """A later version rewording or removing an option leaves the feed's row as made."""

    def page_with(question):
        return leaf_page(
            "Route",
            f"<h1>Route</h1>{question}"
            '<section id="recent"><h2>Recent</h2>'
            '<lf-activity id="feed"></lf-activity></section>',
        )

    def item(fast, restated=""):
        return f"""<section id="route-ask"><h2>Which route?</h2>
  <lf-options id="route" choose>
    <lf-option id="route-fast"{restated}>{fast}</lf-option>
    <lf-option id="route-slow">Slow path</lf-option>
  </lf-options>
</section>"""

    page = open_page(browser, live_url(serve(page_with(item("Fast path")))))
    page.locator("#route-fast .lf-pick").click()
    round_trip(page)
    page.locator("#feed .lf-activity-news").click()
    row = page.locator("#feed .lf-activity-row", has_text="chose")
    expect(row).to_contain_text("chose “Fast path” in")

    reworded = page_with(item("Quick route", " restated"))
    stamp_page(serve.page_dir, reworded, "reword the option")
    wait_for_revision(page, 2)
    expect(row).to_contain_text("chose “Fast path” in")

    stamp_page(serve.page_dir, page_with(""), "drop the question")
    wait_for_revision(page, 3)
    expect(row).to_contain_text("chose “Fast path” in")


def test_activity_prints_complete_history_even_when_closed_or_held(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "History",
                '<h1>History</h1><lf-activity id="feed"></lf-activity>',
                # Keep the outer boxes fixed so only the feed changes size at each
                # media transition; a shallower resize masks observer re-registration.
                head="<style>body { block-size: 900px !important; padding: 0 !important; }</style>",
            )
        ),
    )
    control = page.locator("#feed .lf-activity-news")
    expect(control).to_have_attribute("aria-expanded", "false")
    # A feed reconnected after the media changed reads its current print mode.
    page.evaluate("""() => {
        window.detachedFeed = document.getElementById('feed');
        window.detachedFeed.remove();
    }""")
    page.emulate_media(media="print")
    page.evaluate("() => document.querySelector('main').append(window.detachedFeed)")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    expect(page.locator("#feed .lf-activity-row")).to_be_visible()
    expect(control).to_be_hidden()
    page.emulate_media(media="screen")
    expect(control).to_be_visible()
    expect(control).to_have_attribute("aria-expanded", "false")
    control.click()
    comment = append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "comment",
            "author": "user",
            "text": "A held record for paper.",
        },
    )
    told(page)
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    page.emulate_media(media="print")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    expect(page.locator("#feed .lf-activity-row").first).to_contain_text(
        "A held record for paper."
    )
    page.emulate_media(media="screen")
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)

    control.click()
    resolution = append_command(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": comment["id"]}
    )
    told(page)
    control.click()
    target = page.locator("#feed .lf-activity-row").first.locator("button")
    control.press("Tab")
    expect(target).to_be_focused()
    append_command(
        serve.page_dir, {"kind": "undo", "author": "user", "undoes": resolution["id"]}
    )
    told(page)
    expect(control).to_have_text("Activity changed")
    page.emulate_media(media="print")
    expect(page.locator("#feed .lf-activity-row").first).to_have_attribute(
        "data-lf-undone", ""
    )
    page.emulate_media(media="screen")
    expect(control).to_have_text("Activity changed")
    expect(target).to_be_focused()
