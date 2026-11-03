import pytest

"""Tests scheduled by the measured cost of their boundary."""


from browser.navigation.test_panes import only_thread, travel_to_passage
from playwright.sync_api import expect
from render_harness import (
    CORPUS_SOURCES,
    open_page,
    pane_scroll_behavior,
    resized,
)


@pytest.mark.shifts_unsurveyed
def test_thread_travel_reveals_a_review_detail_in_its_pane_only(browser, serve):
    example = next(e for e in CORPUS_SOURCES if e.stem == "review-queue")
    page = open_page(
        browser,
        serve(
            example,
            anchored=[
                (
                    "review-cache",
                    "The deploy copies active entries to the new key format before readers",
                )
            ],
        ),
    )
    resized(page, 1400, 900)
    pane_scroll_behavior(page, page.locator("#review-detail"), "bounded")
    queue = page.locator("#review-queue > :not(header, footer)")
    detail = page.locator("#review-detail > :not(header, footer)")
    queue.evaluate(
        "el => el.scrollTop = Math.min(120, el.scrollHeight - el.clientHeight)"
    )
    queue_before = queue.evaluate("el => el.scrollTop")
    detail.evaluate("el => el.scrollTop = el.scrollHeight")
    detail_before = detail.evaluate("el => el.scrollTop")
    assert detail_before > 0
    expect(page.locator("#review-cache")).not_to_be_in_viewport()

    travel_to_passage(page, only_thread(serve.page_dir))
    expect(page.locator("#review-cache")).to_be_in_viewport()
    assert detail.evaluate("el => el.scrollTop") < detail_before
    assert queue.evaluate("el => el.scrollTop") == queue_before
