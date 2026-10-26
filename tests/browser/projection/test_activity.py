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

from leaf.render_checks import wait_until_ready

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
        return f"""<lf-ask id="route-ask"><h2>Which route?</h2>
  <lf-options id="route" choose>
    <lf-option id="route-fast"{restated}>{fast}</lf-option>
    <lf-option id="route-slow">Slow path</lf-option>
  </lf-options>
</lf-ask>"""

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


def test_activity_holds_arrivals_until_the_reader_reveals_them(browser, serve):
    """News above a visible passage waits; its fixed control never dodges activation.
    The control is a button, worked here by the keyboard; a tap activates the same
    button."""
    html = leaf_page(
        "History",
        '<h1>History</h1><section id="recent"><h2>Recent</h2>'
        '<lf-activity id="feed"></lf-activity></section><section id="policy">'
        '<h2>Policy</h2><p id="reading">Keep this visible line where it stands.</p></section>',
    )
    url = live_url(serve(html))
    page = open_page(browser, url)
    control = page.locator("#feed .lf-activity-news")
    line = page.locator("#reading")
    expect(control).to_have_text("Show activity")
    before = line.bounding_box()
    first = append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "comment",
            "author": "user",
            "anchor": {"section": "policy"},
            "text": "First incoming update",
        },
    )
    told(page)
    expect(control).to_have_text("Show activity · 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(1)
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    control.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(control).to_be_focused()
    control.press("Enter")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    expect(control).to_have_text("Hide activity")
    focused_row = page.locator("#feed .lf-activity-row").first.locator(
        ".lf-activity-target"
    )
    page.keyboard.press("Tab")
    expect(focused_row).to_be_focused()
    before = line.bounding_box()
    trigger = control.bounding_box()
    append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "reply",
            "author": "agent",
            "parent": first["id"],
            "text": "A second arrival with enough words to visibly grow the feed.",
        },
    )
    told(page)
    expect(control).to_have_text("Show 1 new")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(2)
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    assert control.bounding_box() == trigger
    expect(focused_row).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(control).to_be_focused()
    control.press("Space")
    expect(page.locator("#feed .lf-activity-row")).to_have_count(3)
    expect(page.locator("#feed .lf-activity-row").first).to_contain_text(
        "A second arrival"
    )
    assert control.bounding_box() == trigger
    expect(control).to_be_focused()

    # An existing row changing shape is news too, even with no newly added row.
    before = line.bounding_box()
    resolution = append_command(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    told(page)
    control.click()
    before = line.bounding_box()
    append_command(
        serve.page_dir, {"kind": "undo", "author": "user", "undoes": resolution["id"]}
    )
    told(page)
    expect(control).to_have_text("Activity changed")
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    control.click()
    expect(
        page.locator("#feed .lf-activity-row", has_text="Me resolved")
    ).to_have_attribute("data-lf-undone", "")
    assert control.bounding_box() == trigger
    before_revision = line.bounding_box()
    stamp_page(
        serve.page_dir,
        html.replace("Keep this visible", "Still keep this visible"),
        "Revise the policy",
    )
    wait_for_revision(page, 2)
    expect(control).to_have_attribute("aria-expanded", "true")
    expect(control).to_have_text("Show 1 new")
    assert line.bounding_box()["y"] == pytest.approx(before_revision["y"], abs=0.5)
    # Changing executable inputs replaces the document, rather than patching it.
    page.add_init_script("""
      window.activityFrames = [];
      let remaining = 180;
      function readFrame() {
        const line = document.getElementById("reading");
        const control = document.querySelector("#feed .lf-activity-news");
        if (line && control) window.activityFrames.push({
          line: line.getBoundingClientRect().y,
          open: control.getAttribute("aria-expanded")
        });
        if (--remaining) requestAnimationFrame(readFrame);
      }
      requestAnimationFrame(readFrame);
    """)
    before_replacement = line.bounding_box()
    original_document = page.evaluate("performance.timeOrigin")
    expect(control).to_be_focused()
    fresh = html.replace("Keep this visible", "Still keep this visible").replace(
        "</head>", '<script type="module">void 0;</script></head>'
    )
    stamp_page(serve.page_dir, fresh, "Replace executable inputs")
    wait_for_revision(page, 3)
    wait_until_ready(page)
    expect(control).to_have_attribute("aria-expanded", "true")
    assert page.evaluate("performance.timeOrigin") != original_document
    assert line.bounding_box()["y"] == pytest.approx(before_replacement["y"], abs=0.5)
    expect(control).to_be_focused()
    frames = page.evaluate("window.activityFrames")
    assert frames
    assert all(frame["open"] == "true" for frame in frames)
    assert all(
        frame["line"] == pytest.approx(before_replacement["y"], abs=0.5)
        for frame in frames
    )
    # Generated row targets use the same keyed handoff as the notice.
    target = page.locator("#feed .lf-activity-row button.lf-activity-target").first
    control.press("Tab")
    expect(target).to_be_focused()
    stamp_page(serve.page_dir, fresh.replace("void 0", "void 1"), "Replace again")
    wait_for_revision(page, 4)
    wait_until_ready(page)
    expect(target).to_be_focused()
    assert line.bounding_box()["y"] == pytest.approx(before_replacement["y"], abs=0.5)


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
