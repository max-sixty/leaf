"""Independent packages compose behavior, typed data and nested presentation."""

from pathlib import Path

from playwright.sync_api import expect
from render_harness import open_page, round_trip

from leaf.event_log import read_events

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_independent_packages_keep_their_actions_data_and_nested_styles(browser, serve):
    page = open_page(
        browser,
        serve(
            (FIXTURES / "composition.html").read_text(),
            packages=(
                "diff",
                "file-tree",
                FIXTURES / "packages/composition",
                FIXTURES / "packages/composition-theme",
            ),
        ),
    )
    expect(page.get_by_role("treeitem", name="session.py", exact=True)).to_be_visible()
    expect(
        page.get_by_role("treeitem", name="test_session.py", exact=True)
    ).to_be_visible()
    styles = page.evaluate("""() => Object.fromEntries(
      ['composition-owned-note', 'composition-nested-note'].map(id =>
        [id, getComputedStyle(document.getElementById(id)).borderInlineStartWidth]))""")
    page.locator("#composition-details summary").click()
    page.get_by_role("button", name="Pass review", exact=True).click()
    round_trip(page)
    expect(page.locator("#composition-review .review-result")).to_have_text(
        "Passed review"
    )
    action = next(e for e in read_events(serve.page_dir) if e.get("action") == "review")
    assert action["detail"] == {"outcome": "pass"}
    assert not action["meaning"]["state"].get("decides")
    expect(page.locator("#composition-details")).to_have_attribute("open", "")
    assert styles["composition-owned-note"] != "0px"
    assert styles["composition-nested-note"] == "0px"
    # The code viewport owns both the thread's width and the overlay scrollbar
    # clearance. Its inline-size containment must preserve the shared scroll-state
    # query, otherwise the last line's comment control sits beneath the track.
    page.set_viewport_size({"width": 400, "height": 844})
    viewport = page.locator("#composition-patch code[data-code]").first
    page.wait_for_function(
        """el => el.scrollHeight - (
      Math.max(...[...el.querySelectorAll('button')].map(button =>
        button.getBoundingClientRect().bottom)) - el.getBoundingClientRect().top)
      >= 15""",
        arg=viewport.element_handle(),
    )
