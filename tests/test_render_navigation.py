"""Comment marks, addresses, and keyboard navigation tests."""

import json
import re

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    ADDRESS_PAGE,
    ADDRESSED_PAGE,
    ASKS_PAGE,
    BOARD_PAGE,
    CHIPS,
    CLIPPED_BY,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    DIFF_PAGE,
    DISCLOSED_PAGE,
    EXAMPLES,
    FEATURE_GALLERY,
    FOOTED_PAGE,
    INLINE_PAGE,
    INSIDE_ITS_OPTION,
    LONG_PAGE,
    NOTED_PAGE,
    OVER_WORDS,
    PANEL_PAGE,
    RENDERED,
    ROOT,
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    SEATED_QUESTION_PAGE,
    TARGETS_PAGE,
    TOKEN,
    WHERE_I_STAND_PAGE,
    _publish,
    address_code,
    address_codes,
    card_body,
    composer_quote,
    go_to_address,
    hold_selection,
    in_threads_scrollport,
    leaf_page,
    live_url,
    mark_point,
    open_page,
    open_versions,
    opened_tab,
    page_at_rest,
    painted,
    panel_comment,
    panel_settled,
    pending_text,
    post_event,
    refuse,
    resized,
    round_trip,
    select,
    sending,
    shortcut_bar_text,
    stamp_page,
    stamp_version_file,
    standing_mark,
    told,
    wait_for_pending_mark,
    wait_for_revision,
    wait_hovered,
    wait_standing,
    watched,
)

pytestmark = pytest.mark.nightly

READING_REGIONS_PAGE = leaf_page(
    "reading region navigation",
    """
<lf-workspace id="reading-workspace">
  <header><h1>Reading workspace</h1></header>
  <lf-split id="reading-split" direction="columns">
    <lf-pane id="left-reading" label="Left reading">
      <header><button id="left-head">Left header</button></header>
      <p id="left-start">Left start with enough words to preserve this landmark.</p>
      <div style="height: 260px"></div>
      <p id="left-landmark">The current left reading has a stable semantic landmark.</p>
      <div style="height: 800px"></div>
      <p id="left-end">Left end</p>
      <footer><button id="left-foot">Left footer</button></footer>
    </lf-pane>
    <lf-pane id="right-reading" label="Right reading">
      <header><button id="right-head">Right header</button></header>
      <p id="right-start">Right start with enough words to preserve this landmark.</p>
      <div style="height: 320px"></div>
      <p id="right-landmark">The current right reading has a stable semantic landmark.</p>
      <div style="height: 740px"></div>
      <p id="right-end"><button id="right-subject">Right subject</button></p>
    </lf-pane>
  </lf-split>
</lf-workspace>
""",
)


def test_reading_keys_follow_the_focused_pane_without_moving_its_sibling(
    browser, serve
):
    page, errors = open_page(browser, serve(READING_REGIONS_PAGE))
    left = page.locator("#left-reading > .lf-pane-content > .lf-pane-body")
    right = page.locator("#right-reading > .lf-pane-content > .lf-pane-body")
    ranges = page.evaluate(
        """() => Object.fromEntries(['left-reading', 'right-reading'].map(id => {
          const body = document.querySelector(`#${id} > .lf-pane-content > .lf-pane-body`);
          return [id, body.scrollHeight - body.clientHeight];
        }))"""
    )
    assert min(ranges.values()) > 300, ranges

    page.locator("#left-head").focus()
    page.keyboard.press("d")
    page.wait_for_function(
        "() => document.querySelector('#left-reading .lf-pane-body').scrollTop > 0"
    )
    page.wait_for_timeout(250)
    assert right.evaluate("el => el.scrollTop") == 0
    left_position = left.evaluate("el => el.scrollTop")

    page.locator("#right-head").focus()
    page.keyboard.press("d")
    page.wait_for_function(
        "() => document.querySelector('#right-reading .lf-pane-body').scrollTop > 0"
    )
    page.wait_for_timeout(250)
    assert left.evaluate("el => el.scrollTop") == left_position

    # Footer focus still names the pane for reading keys; the footer itself does not
    # become content inside the body scroller.
    page.locator("#left-foot").focus()
    page.keyboard.press("u")
    page.wait_for_function(
        f"() => document.querySelector('#left-reading .lf-pane-body').scrollTop < {left_position}"
    )
    assert errors == []
    page.close()


def test_workspace_posture_changes_keep_each_panes_reading(browser, serve):
    page, errors = open_page(browser, serve(READING_REGIONS_PAGE))
    workspace = page.locator("#reading-workspace")
    left = page.locator("#left-reading > .lf-pane-content > .lf-pane-body")
    right = page.locator("#right-reading > .lf-pane-content > .lf-pane-body")
    left.evaluate("el => el.scrollTop = 180")
    right.evaluate("el => el.scrollTop = 380")
    page.locator("#right-subject").focus()
    expect(workspace).to_have_attribute("data-lf-posture", "bounded")

    resized(page, 520, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "flow")
    expect(page.locator("#right-subject")).to_be_focused()
    resized(page, 1200, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "bounded")
    readings = [
        left.evaluate("el => el.scrollTop"),
        right.evaluate("el => el.scrollTop"),
    ]
    assert readings[0] > 100 and readings[1] > 250, readings
    assert abs(readings[0] - readings[1]) > 100, readings
    expect(page.locator("#right-subject")).to_be_focused()
    assert errors == []
    page.close()


def test_a_tall_local_comment_survives_its_panes_posture_and_return(browser, serve):
    source = READING_REGIONS_PAGE.replace(
        '<footer><button id="left-foot">',
        '<footer style="min-height: 220px"><button id="left-foot">',
    )
    page, errors = open_page(browser, serve(source))
    workspace = page.locator("#reading-workspace")
    left = page.locator("#left-reading > .lf-pane-content > .lf-pane-body")
    right = page.locator("#right-reading > .lf-pane-content > .lf-pane-body")
    target = page.locator("#left-end")
    expect(workspace).to_have_attribute("data-lf-posture", "bounded")

    left.evaluate("body => body.scrollTop = body.scrollHeight")
    right.evaluate("body => body.scrollTop = 320")
    target.click(click_count=3)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.click()
    expect(field).to_be_focused()
    wait_for_pending_mark(page)

    sibling_before = right.evaluate(
        "body => ({scroll: body.scrollTop, box: body.getBoundingClientRect().toJSON()})"
    )
    draft = "\n".join(
        f"Line {line}: keep this unsent pane comment available through reflow."
        for line in range(1, 21)
    )
    field.fill(draft)
    expect(field).to_have_value(draft)
    expect(page.get_by_role("button", name="Comment", exact=True)).to_be_visible()
    sibling_after = right.evaluate(
        "body => ({scroll: body.scrollTop, box: body.getBoundingClientRect().toJSON()})"
    )
    assert sibling_after == sibling_before, (
        f"growing the left composer moved its sibling: {sibling_before}, {sibling_after}"
    )
    field.evaluate("box => box.scrollTop = box.scrollHeight")
    assert field.evaluate(
        "box => box.scrollTop + box.clientHeight >= box.scrollHeight - 1"
    ), "the complete multiline draft was not reachable in its field"

    resized(page, 520, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "flow")
    expect(field).to_be_focused()
    expect(field).to_have_value(draft)
    expect(page.get_by_role("button", name="Comment", exact=True)).to_be_visible()

    resized(page, 1200, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "bounded")
    expect(field).to_be_focused()
    expect(field).to_have_value(draft)
    assert right.evaluate("body => body.scrollTop") == pytest.approx(
        sibling_before["scroll"], abs=1
    )

    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator(".lf-notice")).to_have_text("Draft kept — g D returns to it")
    page.keyboard.press("g")
    assert "your draft" in shortcut_bar_text(page)
    page.keyboard.press("Shift+d")
    expect(field).to_be_focused()
    expect(field).to_have_value(draft)
    assert "Left end" in pending_text(page)
    assert errors == []
    page.close()


def test_a_wheel_reading_without_focus_becomes_the_bounded_pane_subject(browser, serve):
    page, errors = open_page(browser, serve(READING_REGIONS_PAGE))
    workspace = page.locator("#reading-workspace")
    resized(page, 520, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "flow")
    right_landmark = page.locator("#right-landmark")
    right_landmark.scroll_into_view_if_needed()
    page.evaluate("() => document.activeElement?.blur()")
    box = right_landmark.bounding_box()
    page.mouse.move(box["x"] + 8, box["y"] + 8)
    before = page.evaluate("() => scrollY")
    page.mouse.wheel(0, 240)
    page.wait_for_function("before => scrollY > before", arg=before)
    relative = right_landmark.evaluate("el => el.getBoundingClientRect().top")

    resized(page, 1200, 900)
    expect(workspace).to_have_attribute("data-lf-posture", "bounded")
    readings = page.evaluate(
        """() => ({
          left: document.querySelector('#left-reading .lf-pane-body').scrollTop,
          right: document.querySelector('#right-reading .lf-pane-body').scrollTop,
          rightRelative: document.querySelector('#right-landmark').getBoundingClientRect().top -
            document.querySelector('#right-reading .lf-pane-body').getBoundingClientRect().top,
        })"""
    )
    assert readings["right"] > readings["left"] + 100, readings
    assert abs(readings["rightRelative"] - relative) < 3, (relative, readings)
    assert errors == []
    page.close()


def test_a_pane_comment_stays_in_its_reading_region(browser, serve):
    source = READING_REGIONS_PAGE.replace(
        '<footer><button id="left-foot">',
        '<footer style="min-height: 220px"><button id="left-foot">',
    )
    url = serve(source, anchored=[("left-start", "enough words to preserve")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": root,
            "revision": 1,
            "text": "\n\n".join(
                f"Pane consideration {i}: enough explanation to require local scrolling."
                for i in range(20)
            ),
        },
    )
    page, errors = open_page(browser, url)
    cluster = page.locator('[data-lf-margin-for="left-start"].lf-margin-cluster')
    expect(cluster).to_have_count(1)
    expect(cluster).to_have_class(re.compile(r"\blf-docked\b"))
    placement = cluster.evaluate(
        """el => ({
          inOwner: document.querySelector('#left-reading .lf-pane-body').contains(el),
          inSibling: document.querySelector('#right-reading').contains(el),
          cluster: el.getBoundingClientRect().toJSON(),
          body: document.querySelector('#left-reading .lf-pane-body')
            .getBoundingClientRect().toJSON(),
        })"""
    )
    assert placement["inOwner"] and not placement["inSibling"], placement
    assert placement["cluster"]["left"] >= placement["body"]["left"], placement
    assert placement["cluster"]["right"] <= placement["body"]["right"], placement

    page.locator("#left-start .lf-mark-note").click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    preview_geometry = preview.evaluate(
        """el => {
          const card = el.getBoundingClientRect();
          const body = document.querySelector('#left-reading .lf-pane-body')
            .getBoundingClientRect();
          return {card: card.toJSON(), body: body.toJSON(),
                  scrollHeight: el.scrollHeight, clientHeight: el.clientHeight};
        }"""
    )
    assert preview_geometry["card"]["top"] >= preview_geometry["body"]["top"], (
        preview_geometry
    )
    assert preview_geometry["card"]["bottom"] <= preview_geometry["body"]["bottom"], (
        preview_geometry
    )
    assert preview_geometry["scrollHeight"] > preview_geometry["clientHeight"], (
        preview_geometry
    )
    preview.evaluate("el => el.scrollTop = el.scrollHeight")
    assert preview.evaluate("el => el.scrollTop") > 0
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    page.keyboard.press("t")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-conversation-thread")).to_be_focused()
    assert errors == []
    page.close()


def test_a_new_revision_restores_each_panes_semantic_landmark(browser, serve):
    url = serve(READING_REGIONS_PAGE)
    page, errors = open_page(browser, live_url(url))
    expect(page.locator("#reading-workspace")).to_have_attribute(
        "data-lf-posture", "bounded"
    )
    left = page.locator("#left-reading > .lf-pane-content > .lf-pane-body")
    right = page.locator("#right-reading > .lf-pane-content > .lf-pane-body")
    left.evaluate("el => el.scrollTop = 300")
    right.evaluate("el => el.scrollTop = 360")
    before = page.evaluate(
        """() => ['left-landmark', 'right-landmark'].map(id => {
          const landmark = document.getElementById(id);
          return landmark.getBoundingClientRect().top -
            landmark.closest('.lf-pane-body').getBoundingClientRect().top;
        })"""
    )

    revised = READING_REGIONS_PAGE.replace(
        '<p id="left-start">',
        '<p>New left material above the saved reading.</p><p id="left-start">',
    ).replace(
        '<p id="right-start">',
        '<p>New right material above the saved reading.</p><p id="right-start">',
    )
    stamp_page(serve.page_dir, revised, "add context above both readings")
    wait_for_revision(page, 2)
    after = page.evaluate(
        """() => ['left-landmark', 'right-landmark'].map(id => {
          const landmark = document.getElementById(id);
          return landmark.getBoundingClientRect().top -
            landmark.closest('.lf-pane-body').getBoundingClientRect().top;
        })"""
    )
    scrolls = [
        left.evaluate("el => el.scrollTop"),
        right.evaluate("el => el.scrollTop"),
    ]
    assert all(abs(old - new) < 2 for old, new in zip(before, after, strict=True)), (
        before,
        after,
        scrolls,
    )
    assert left.evaluate("el => el.scrollTop") > 0
    assert right.evaluate("el => el.scrollTop") > 0
    assert errors == []
    page.close()


def test_review_queue_links_are_its_only_navigator_and_keep_both_readings(
    browser, serve
):
    example = next(e for e in EXAMPLES if e.stem == "review-queue")
    page, errors = open_page(browser, serve(example))
    resized(page, 1100, 520)
    queue = page.locator("#review-queue .lf-pane-body")
    detail = page.locator("#review-detail .lf-pane-body")
    links = queue.locator('nav[aria-label="Review items"] a')
    assert links.count() == 8
    assert page.get_by_role("tab").count() == 0
    assert (
        links.evaluate_all("els => new Set(els.map(el => el.hash)).size")
        == page.locator("#review-items > section").count()
    )

    billing = links.filter(has_text="Billing reconciliation")
    billing.scroll_into_view_if_needed()
    billing.focus()
    queue_before = queue.evaluate("el => el.scrollTop")
    detail_before = detail.evaluate("el => el.scrollTop")
    events_before = events_model.read_events(serve.page_dir)

    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#review-billing$"))
    expect(page.locator("#review-billing")).to_be_in_viewport()
    assert detail.evaluate("el => el.scrollTop") > detail_before
    assert queue.evaluate("el => el.scrollTop") == queue_before
    assert events_model.read_events(serve.page_dir) == events_before
    assert errors == []
    page.close()


def test_thread_travel_reveals_a_review_detail_in_its_pane_only(browser, serve):
    example = next(e for e in EXAMPLES if e.stem == "review-queue")
    page, errors = open_page(
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
    queue = page.locator("#review-queue .lf-pane-body")
    detail = page.locator("#review-detail .lf-pane-body")
    queue.evaluate(
        "el => el.scrollTop = Math.min(120, el.scrollHeight - el.clientHeight)"
    )
    queue_before = queue.evaluate("el => el.scrollTop")
    detail.evaluate("el => el.scrollTop = el.scrollHeight")
    detail_before = detail.evaluate("el => el.scrollTop")
    assert detail_before > 0
    expect(page.locator("#review-cache")).not_to_be_in_viewport()

    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread .lf-quote").click()
    expect(page.locator("#review-cache")).to_be_in_viewport()
    assert detail.evaluate("el => el.scrollTop") < detail_before
    assert queue.evaluate("el => el.scrollTop") == queue_before
    assert errors == []
    page.close()


def test_review_queue_decisions_replay_and_reach_the_next_revision_from_the_keyboard(
    browser, serve
):
    example = next(e for e in EXAMPLES if e.stem == "review-queue")

    seeded = serve(example)
    first = seeded.replace("/versions/v2.html", "/versions/v1.html")
    page, errors = open_page(browser, first)
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/2")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("chosen", "")
    assert errors == []
    page.close()

    newest = serve(example, seed_log=False)
    first = newest.replace("/versions/v2.html", "/versions/v1.html")
    page, errors = open_page(browser, first)
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/2")
    expect(page.locator("#review-cache-auto")).not_to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).not_to_have_attribute("chosen", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "A failed copy leaves the old keys authoritative"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Open difference"
    )
    footer = page.locator("#review-detail > footer")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")
    expect(footer).to_contain_text(
        "submitted answers are incorporated in the next revision"
    )

    page.keyboard.press("a")
    expect(page.locator("#review-cache-decision")).to_be_focused()
    with sending(page, "the cache rollback decision"):
        page.keyboard.press("1")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")

    page.keyboard.press("a")
    expect(page.locator("#review-billing-decision")).to_be_focused()
    with sending(page, "the billing reconciliation decision"):
        page.keyboard.press("1")
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/2")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")

    page.goto(live_url(newest))
    page.wait_for_function(RENDERED)
    expect(page.locator(".lf-version")).to_have_text("v2")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("chosen", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "returns readers to the old keys automatically"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Legacy difference stays on its reporting path"
    )
    expect(page.locator("#review-detail > footer")).to_contain_text(
        "This revision incorporates both answers"
    )
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/0")

    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["options"] for event in actions] == [
        ["review-cache-auto"],
        ["review-billing-legacy"],
    ]
    assert errors == []
    page.close()


def test_a_nested_pane_footer_travels_in_the_outer_region_that_contains_it(
    browser, serve
):
    source = READING_REGIONS_PAGE.replace(
        '<p id="left-end">Left end</p>',
        """<lf-workspace id="nested-workspace">
  <lf-pane id="nested-pane" label="Nested reading">
    <p>Nested body context stays in ordinary flow.</p>
    <footer><p id="nested-footer">Nested footer destination with enough words to anchor.</p></footer>
  </lf-pane>
</lf-workspace>
<p id="left-end">Left end</p>""",
    )
    page, errors = open_page(
        browser,
        serve(source, anchored=[("nested-footer", "footer destination")]),
    )
    outer = page.locator("#left-reading > .lf-pane-content > .lf-pane-body")
    inner = page.locator("#nested-pane > .lf-pane-content > .lf-pane-body")
    sibling = page.locator("#right-reading > .lf-pane-content > .lf-pane-body")
    assert outer.evaluate("el => el.scrollHeight - el.clientHeight") > 300
    assert inner.evaluate("el => el.scrollTop") == 0

    page.keyboard.press("t")
    expect(page.locator("#nested-footer")).to_be_in_viewport()
    assert outer.evaluate("el => el.scrollTop") > 0
    assert inner.evaluate("el => el.scrollTop") == 0
    assert sibling.evaluate("el => el.scrollTop") == 0
    assert errors == []
    page.close()


def test_the_feature_gallery_exercises_the_injected_core_surfaces(
    browser, serve, live_leaf
):
    """Core chrome is a gallery journey, not merely present around its specimens."""
    live_leaf("second", "A second Leaf page")
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1600, 900)

    expect(
        page.get_by_role(
            "heading",
            name="Asks: decisions and answers",
            exact=True,
        )
    ).to_be_visible()
    guide = page.locator("#bg-core-controls-guide")
    for surface in (
        "status line",
        "Threads",
        "Versions menu",
        "Map",
        "All keyboard shortcuts",
        "All leaves",
    ):
        expect(guide).to_contain_text(surface)
    expect(page.locator(".lf-banner-status")).not_to_be_empty()

    page.locator(".lf-asks").click()
    map_ask = page.locator("button.lf-asks-row").filter(
        has_text="Which map should the sample team carry?"
    )
    expect(map_ask).to_have_count(1)
    expect(map_ask.locator(".lf-asks-kind")).to_have_text("ask")
    map_ask.click()
    expect(page.locator("#bg-choice-ask")).to_be_focused()
    page.locator(".lf-asks").click()

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator('[data-filter-value="resolved"]')).not_to_have_text("Resolved")
    page.locator('[data-filter-value="resolved"]').click()
    expect(
        page.locator('.lf-thread[data-resolved="true"]:not([hidden])')
    ).not_to_have_count(0)
    page.locator('[data-filter-value="open"]').click()
    expect(page.locator("#bg-thread-media")).to_contain_text(
        "supplied by its companion thread log"
    )
    media_open = page.locator(
        '.lf-thread[data-id="2be2443f0bb6cc49fc86b52f340e6073"] .lf-message-media'
    )
    expect(media_open).to_be_visible()
    url_before = page.url
    media_open.click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer).to_be_visible()
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    assert page.url == url_before
    page.keyboard.press("w")
    expect(viewer).to_be_visible()
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-drawing\b"))
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(media_open).to_be_focused()
    expect(page.locator(".lf-panel")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(page.locator(".lf-asks")).to_be_focused()

    page.locator(".lf-version").click()
    expect(
        page.locator('.lf-version-menu .lf-version-row[data-lf-version="1"]')
    ).to_be_visible()
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.get_by_role("dialog", name="All keyboard shortcuts")
    expect(reference).to_be_visible()
    resized(page, 320, 900)
    operation = reference.locator("tr").filter(has_text="Restart the sample worker")
    geometry = operation.evaluate(
        """row => {
          const key = row.querySelector('.lf-key-label > kbd');
          const keyBox = key.getBoundingClientRect();
          const action = row.cells[1];
          const actionBox = action.getBoundingClientRect();
          const range = document.createRange(), broken = [];
          const walker = document.createTreeWalker(action, NodeFilter.SHOW_TEXT);
          for (let node = walker.nextNode(); node; node = walker.nextNode())
            for (const match of node.textContent.matchAll(/[A-Za-z]+/g)) {
              range.setStart(node, match.index);
              range.setEnd(node, match.index + match[0].length);
              if (new Set([...range.getClientRects()].map(rect => Math.round(rect.top))).size > 1)
                broken.push(match[0]);
            }
          return {
            broken,
            keyFits: key.scrollWidth <= key.clientWidth && key.scrollHeight <= key.clientHeight,
            keyRight: keyBox.right,
            actionLeft: actionBox.left,
          };
        }"""
    )
    assert geometry["keyFits"], geometry
    assert geometry["keyRight"] <= geometry["actionLeft"], geometry
    assert geometry["broken"] == [], geometry
    resized(page, 1600, 900)
    page.keyboard.press("Escape")

    page.locator(".lf-others").click()
    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row")).to_contain_text("A second Leaf page")
    page.keyboard.press("Escape")

    resized(page, 390, 900)
    page.evaluate("scrollTo(0, 0)")
    expect(page.locator("#bg-sidebar")).to_be_hidden()
    expect(
        page.get_by_role(
            "heading",
            name="Asks: decisions and answers",
            exact=True,
        )
    ).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    header = sheet.locator(".lf-page-map-head")
    close = header.get_by_role("button", name="Close", exact=True)
    header_box, close_box = header.bounding_box(), close.bounding_box()
    assert header_box and close_box
    assert close_box["x"] + close_box["width"] == pytest.approx(
        header_box["x"] + header_box["width"], abs=0.5
    ), (header_box, close_box)
    assert errors == []
    page.close()


def test_the_feature_gallery_keeps_a_choice_when_its_proposal_is_undone(browser, serve):
    """The composed page keeps nested reader work through an outer undo and reload."""
    url = serve(FEATURE_GALLERY)
    page, errors = open_page(browser, url)
    page.locator("#bg-route-river").click()
    round_trip(page)
    controls = page.locator('[data-lf-for="bg-nested-change"]')
    controls.get_by_role("button", name=re.compile("^Accept the ")).click()
    round_trip(page)
    expect(page.locator("#bg-nested-change > lf-old")).to_be_hidden()
    controls.get_by_role("button", name=re.compile("^Undo ")).click()
    round_trip(page)

    expect(page.locator("#bg-nested-change > lf-old")).to_be_visible()
    expect(page.locator("#bg-route lf-option[chosen]")).to_have_attribute(
        "id", "bg-route-river"
    )
    assert errors == []
    page.close()

    page, errors = open_page(browser, url)
    expect(page.locator("#bg-nested-change > lf-old")).to_be_visible()
    expect(page.locator("#bg-route lf-option[chosen]")).to_have_attribute(
        "id", "bg-route-river"
    )
    assert errors == []
    page.close()


def test_the_feature_gallery_sections_are_stable_preview_destinations(browser, serve):
    """A preview can name its subject directly instead of asking the reader to find it."""
    root = live_url(serve(FEATURE_GALLERY))
    destination = "#bg-quoted-and-visual"
    page, errors = open_page(browser, root + destination)

    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    targets = links.evaluate_all(
        """links => links.map(link => {
          const href = link.getAttribute('href');
          const target = document.getElementById(decodeURIComponent(href.slice(1)));
          return {href, tag: target?.localName || null,
                  generated: target?.dataset.lfGen === '1'};
        })"""
    )
    assert targets[0] == {"href": "#bg-title", "tag": "h1", "generated": False}
    assert all(
        target["tag"] == "section" and not target["generated"] for target in targets[1:]
    ), targets
    assert len({target["href"] for target in targets}) == len(targets), targets

    target = page.locator(destination)
    expect(page).to_have_url(root + destination)
    expect(page.locator(":target")).to_have_attribute("id", destination[1:])
    expect(target).to_be_in_viewport()
    assert errors == []
    page.close()


def test_the_feature_gallery_exercises_core_reader_workflows(browser, serve):
    """Sign-off, layer comments, and request outcomes are real gallery journeys."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    resized(page, 1280, 900)

    approve = page.locator(".lf-signoff")
    expect(approve).to_have_text("Approve version")
    approve.click()
    round_trip(page)
    expect(approve).to_have_text("✓ Version approved")
    page.keyboard.press("z")
    round_trip(page)
    expect(approve).to_have_text("Approve version")

    option = page.locator("#bg-choice-street")
    option_box = option.bounding_box()
    assert option_box is not None
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.mouse.click(
        option_box["x"] + option_box["width"] / 2,
        option_box["y"] + option_box["height"] / 2,
    )
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · lf-option · bg-choice-street"
    )
    expect(option).not_to_have_attribute("chosen", "")
    page.locator(".lf-composer textarea").fill("The sample option needs less padding.")
    with sending(page, "the design comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    design_comment = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("about") == "layer"
    ][-1]
    assert design_comment["anchor"] == {"section": "bg-choice-street"}
    page.locator("body").focus()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))

    ready = page.locator("#bg-request-live")
    restart = ready.get_by_role("button", name="Restart the sample worker", exact=True)

    with sending(page, "the restart request"):
        restart.click()
    request = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "request" and event["widget"] == "bg-request-live"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "receipt",
            "author": "claude",
            "request": request["id"],
            "status": "failed",
            "text": "The sample branch is protected by another review",
        },
    )
    told(page)
    expect(ready).to_contain_text(
        "restart failed · The sample branch is protected by another review"
    )
    expect(restart).to_be_enabled()

    with sending(page, "the retried restart request"):
        restart.click()
    retried = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "request" and event["widget"] == "bg-request-live"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "receipt",
            "author": "claude",
            "request": retried["id"],
            "status": "succeeded",
            "text": "Restarted the sample worker",
        },
    )
    told(page)
    expect(ready).to_contain_text("restart succeeded · Restarted the sample worker")
    expect(restart).to_be_disabled()

    def reject(route):
        route.fulfill(
            status=400,
            json={"ok": False, "error": "gallery transport refusal", "final": True},
        )

    page.route("**/api/event", reject)
    change = page.locator('[data-lf-margin-for="bg-replace"]')
    change.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    ).click()
    retry = change.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    expect(change.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(change).to_contain_text("Failed")
    change.get_by_role("button", name="Cancel", exact=True).click()
    expect(retry).to_have_count(0)

    assert errors and all("400" in error for error in errors)
    page.close()


def test_the_feature_gallery_exercises_live_and_snapshotted_external_data(
    browser, serve
):
    """One captured source supplies a following view, a snapshot, and provenance."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    live = page.locator("#bg-source-live")
    frozen = page.locator("#bg-source-snapshot")
    original = (
        '[route]\nname = "covered terrace"\ndistance_km = 1.8\nstatus = "sample"\n'
    )

    expect(live.locator("code")).to_have_text(original)
    expect(frozen.locator("code")).to_have_text(original)
    expect(frozen.locator("figcaption")).to_have_text(
        "feature-gallery-source.toml at sample-1 · lines 1–4 · snapshot 1"
    )

    changed = '[route]\nname = "river path"\ndistance_km = 2.1\nstatus = "updated"\n'
    data_model.cmd_data_set(serve.page_dir, "gallery-source", changed)
    expect(live.locator("code")).to_have_text(changed)
    expect(frozen.locator("code")).to_have_text(original)
    expect(page.locator("#bg-measurement-guide")).to_contain_text(
        "measurement is behind its source"
    )

    assert errors == []
    page.close()


def test_the_feature_gallery_exercises_an_inline_diff_thread(browser, serve):
    """The gallery's diff specimen carries a real line thread through both seats."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    diff = page.locator("#bg-review-diff")
    thread = diff.locator(
        '.lf-conversation-thread[data-thread="8c91ac4c0c9d4e17831f45581a11639a"]'
    )
    expect(thread).to_contain_text(
        "Keep the route choice visible beside the line that changes it."
    )
    send = thread.locator(".primary")
    expect(send).to_be_disabled()
    disabled_palette = send.evaluate(
        """button => {
          const style = getComputedStyle(button);
          const face = getComputedStyle(button, '::before');
          return {
            background: face.backgroundColor,
            opacity: style.opacity,
          };
        }"""
    )
    assert disabled_palette["background"] == "rgba(0, 0, 0, 0)"
    assert disabled_palette["opacity"] == "1"
    send.hover()
    assert (
        send.evaluate("button => getComputedStyle(button, '::before').backgroundColor")
        == disabled_palette["background"]
    )
    markers = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    baseline = markers.count()

    details = diff.locator(".lf-diff-file > details")
    details.evaluate("element => { element.open = false; }")
    expect(thread).to_have_count(0)
    expect(markers).to_have_count(baseline + 1)
    details.evaluate("element => { element.open = true; }")
    expect(thread).to_have_count(1)
    expect(markers).to_have_count(baseline)

    page.locator("body").focus()
    page.keyboard.press("t")
    expect(
        page.locator(
            ".lf-margin-preview .lf-conversation-thread"
            '[data-thread="2be2443f0bb6cc49fc86b52f340e6073"]'
        )
    ).to_be_focused()
    page.keyboard.press("t")
    expect(
        page.locator(
            ".lf-margin-preview .lf-conversation-thread"
            '[data-thread="a554d5e884abffdb6494a2fb90b0634f"]'
        )
    ).to_be_focused()
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    assert errors == []
    page.close()


def test_a_thread_walk_card_keeps_its_margin_until_its_anchor_leaves(browser, serve):
    """A contextual thread has one side and only lives while its anchor is visible."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)

    page.locator("body").focus()
    page.keyboard.press("t")
    card = page.locator(".lf-margin-preview")
    expect(
        card.locator(
            '.lf-conversation-thread[data-thread="2be2443f0bb6cc49fc86b52f340e6073"]'
        )
    ).to_be_focused()
    owner = page.locator(
        '.lf-margin-marker[data-lf-kinds~="comment"]'
        '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
    ).locator("xpath=..")
    expect(owner).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    initial = owner.bounding_box()
    assert initial["y"] + initial["height"] > 50
    assert initial["y"] < 900
    page.evaluate("distance => scrollBy(0, distance)", min(160, initial["y"] - 80))
    page.wait_for_function(
        """() => {
          const owner = document.querySelector(
            '.lf-margin-marker[data-lf-kinds~="comment"]' +
            '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
          )?.parentElement?.getBoundingClientRect();
          return owner && owner.bottom > 50 && owner.top < innerHeight;
        }"""
    )
    expect(card).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    expect(card).to_be_hidden()

    marker = page.locator(
        '.lf-margin-marker[data-lf-kinds~="comment"]:not([hidden])'
    ).first
    marker.scroll_into_view_if_needed()
    marker.click()
    expect(card).to_be_visible()
    page.evaluate("() => scrollTo(0, 0)")
    expect(card).to_be_hidden()

    assert errors == []
    page.close()


def test_opened_tab_replaces_the_native_target_with_one_it_can_control(
    browser, one_reader
):
    """One native target proves the press, then leaves no unreachable tab behind."""
    page = one_reader.new_page()
    destination = "about:blank#expected"
    page.set_content(f'<a id="open" target="_blank" href="{destination}">open</a>')
    browser_session = browser.new_browser_cdp_session()

    def targets():
        return {
            target["targetId"]: target["url"]
            for target in browser_session.send("Target.getTargets")["targetInfos"]
            if target["type"] == "page"
        }

    before = targets()
    presses = 0
    native = {}

    def press():
        nonlocal presses
        presses += 1
        page.locator("#open").click()
        native.update(
            {
                target_id: url
                for target_id, url in targets().items()
                if target_id not in before
            }
        )

    tab = opened_tab(page, destination, press)
    assert presses == 1
    assert len(native) == 1
    assert tab.context is one_reader
    assert tab.url == destination
    after = targets()
    assert not (native.keys() & after.keys())
    assert [url for target_id, url in after.items() if target_id not in before] == [
        destination
    ]
    tab.close()
    assert targets() == before
    browser_session.detach()
    page.close()


def test_an_external_link_says_and_opens_where_it_goes(
    browser, serve, other_leaf, one_reader
):
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={TOKEN}"
    url = serve(
        leaf_page(
            "external link",
            f"""
<h1 id="top">Links</h1>
<p>Read the <a id="external" href="{destination}" aria-label="other leaf documentation"
  aria-describedby="source-note">other leaf</a>.</p>
<span id="source-note" hidden>curated source</span>
<p>Return to <a id="fragment" href="#top">the heading</a>.</p>
<svg viewBox="0 0 40 20" aria-label="map"><a id="svg-external" href="{destination}">
  <text x="0" y="15">map</text>
</a></svg>
""",
        )
    )
    page, errors = open_page(browser, url, context=one_reader)
    external = page.locator("#external")
    mark = external.locator(":scope > .lf-external-mark")

    expect(external).to_have_attribute("target", "_blank")
    expect(external).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source opens in a new tab")
    expect(page.locator("#external + .lf-external-note")).to_be_hidden()
    expect(mark).to_be_visible()
    assert mark.evaluate("node => node.localName") == "svg"
    expect(mark.locator(":scope > path")).to_have_count(1)
    expect(mark).to_have_attribute("aria-hidden", "true")
    expect(page.locator("#fragment > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#fragment")).not_to_have_attribute("target", "_blank")
    expect(page.locator("#svg-external > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#svg-external")).not_to_have_attribute("target", "_blank")

    tab = opened_tab(page, destination, external.click)
    expect(tab).to_have_url(destination)
    expect(page).to_have_url(url)
    tab.close()
    assert errors == []
    page.close()


def test_an_addressed_link_leaves_the_reader_at_its_destination(
    browser, serve, other_leaf, one_reader
):
    """A generated link hint completes the trip it names.

    A fragment lands focus on its target, so the reader does not remain at the place they
    left. An external link keeps its new-tab behavior and names that context change even
    though the sequence activates the link without first moving focus through it."""
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={TOKEN}"
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "addressed links",
                f"""
<h1>Addressed links</h1>
<p><a id="internal" href="#arrival">Read the conclusion</a>.</p>
<p><a id="external" href="{destination}" aria-label="Leaf guide">Open the guide</a>.</p>
<h2 id="arrival">Conclusion</h2>
<p>The internal trip ends here.</p>
""",
            )
        ),
        context=one_reader,
    )

    go_to_address(page, "Link", "internal")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()

    page.keyboard.press("g")
    external_code = address_code(page, "Link", "external")
    tab = opened_tab(page, destination, lambda: page.keyboard.type(external_code))
    expect(tab).to_have_url(destination)
    expect(page.locator(".lf-live")).to_have_text("Opened Leaf guide in a new tab")
    tab.close()
    assert errors == []
    page.close()


def test_generated_hints_include_links_revealed_by_a_page_widget(browser, serve):
    """A visible page route stays addressable when its widget generated the anchors.

    The roomy table of contents is page navigation even though its links are generated
    chrome. Arming the sequence reveals those labels, gives every visible row a hint, and
    following one lands at the heading through the ordinary link route.
    """
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "generated page links",
                """
<h1>Migration plan</h1>
<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>
<section><h2>Prepare</h2><p>Take a snapshot.</p></section>
<div style="height: 700px"></div>
<section><h2 id="move">Move</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 700px"></div>
<section><h2 id="verify">Verify</h2><p>Compare the totals.</p></section>
""",
            )
        ),
    )
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.get_by_role("link")
    expect(links).to_have_count(4)
    expect(links.first).to_have_css("opacity", "0")

    page.keyboard.press("g")
    chips = page.locator(f'{CHIPS}[data-lf-address-kind="Link"]')
    expect(chips).to_have_count(4)
    first_code = chips.first.get_attribute("data-lf-address")
    assert first_code
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, Migration plan. Press Enter to go there."
    )
    prepare_link = links.nth(1)
    prepare_href = prepare_link.get_attribute("href")
    assert prepare_href
    code = chips.nth(1).get_attribute("data-lf-address")
    assert code
    page.keyboard.type(code)
    page.wait_for_url(re.compile(rf"{re.escape(prepare_href)}$"))
    expect(page.get_by_role("heading", name="Prepare", exact=True)).to_be_focused()
    assert errors == []
    page.close()


def test_an_inline_tab_keeps_its_panel_inside_one_visible_boundary(browser, serve):
    """The strip reads as an index inside the one frame that bounds its workstream.

    The selected name becomes one compact paper face; the tab around it does not grow a
    second frame inside the shared surface. The strip's closing rule keeps the index
    distinct from the panel, whose enclosing frame still answers how far that
    workstream runs.
    """
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "bounded tabs",
                """
<h1 id="heading">Parallel work</h1>
<p id="shared">This context belongs to every workstream.</p>
<lf-tabs id="workstreams">
  <lf-tab id="implementation" label="Implementation">
    <section id="implementation-section">
      <h2 id="implementation-heading">Build the narrow path</h2>
      <p id="implementation-end">This closing line still belongs to Implementation.</p>
    </section>
  </lf-tab>
  <lf-tab id="research" label="Research">
    <section id="research-section">
      <h2 id="research-heading">Test the broad premise</h2>
      <p id="research-end">This closing line still belongs to Research.</p>
    </section>
  </lf-tab>
</lf-tabs>
<section id="next-section"><h2 id="next-heading">Whole-page conclusion</h2></section>
""",
            )
        ),
    )
    boundary = page.evaluate(
        """() => {
          const tabs = document.querySelector('#workstreams');
          const strip = tabs.querySelector('.lf-tabstrip');
          const panel = tabs.querySelector('lf-tab:not([hidden])');
          const selected = strip.querySelector('[aria-selected="true"]');
          const inactive = strip.querySelector('[aria-selected="false"]');
          const opening = panel.querySelector('h2');
          const closing = panel.querySelector('p:last-child');
          const next = document.querySelector('#next-section');
          const box = element => {
            const rect = element.getBoundingClientRect();
            return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom};
          };
          const style = (element, pseudo) => getComputedStyle(element, pseudo);
          const face = tab => {
            const tabStyle = style(tab);
            const label = tab.querySelector('[data-lf-said]');
            const labelStyle = style(label);
            const markStyle = style(label, '::before');
            return {
              ground: tabStyle.backgroundColor,
              border: ['Top', 'Right', 'Bottom', 'Left'].map(
                edge => parseFloat(tabStyle[`border${edge}Width`])),
              shadow: tabStyle.boxShadow,
              tabDecoration: tabStyle.textDecorationLine,
              labelGround: labelStyle.backgroundColor,
              labelInk: labelStyle.color,
              labelDecoration: labelStyle.textDecorationLine,
              labelPadding: ['Top', 'Right', 'Bottom', 'Left'].map(
                edge => parseFloat(labelStyle[`padding${edge}`])),
              beforeContent: markStyle.content,
            };
          };
          return {
            tabs: box(tabs), strip: box(strip), panel: box(panel),
            opening: box(opening), closing: box(closing), next: box(next),
            frame: {
              top: parseFloat(style(tabs).borderTopWidth),
              right: parseFloat(style(tabs).borderRightWidth),
              bottom: parseFloat(style(tabs).borderBottomWidth),
              left: parseFloat(style(tabs).borderLeftWidth),
              color: style(tabs).borderTopColor,
              ground: style(tabs).backgroundColor,
            },
            divider: {
              width: parseFloat(style(strip).borderBottomWidth),
              color: style(strip).borderBottomColor,
            },
            palette: {
              ink: style(document.body).color,
            },
            selected: face(selected),
            inactive: face(inactive),
          };
        }"""
    )

    frame_edges = tuple(
        boundary["frame"][edge] for edge in ("top", "right", "bottom", "left")
    )
    assert min(frame_edges) > 0, (
        f"the tab surface has an open edge: {boundary['frame']}"
    )
    assert boundary["frame"]["color"] != "rgba(0, 0, 0, 0)", boundary
    assert boundary["divider"]["width"] > 0, boundary
    assert boundary["divider"]["color"] != "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["ground"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["inactive"]["ground"] == boundary["selected"]["ground"], boundary
    assert max(boundary["selected"]["border"]) == 0, boundary
    assert max(boundary["inactive"]["border"]) == 0, boundary
    assert boundary["selected"]["shadow"] == "none", boundary
    assert boundary["inactive"]["shadow"] == "none", boundary
    assert boundary["selected"]["tabDecoration"] == "none", boundary
    assert boundary["selected"]["labelGround"] == boundary["frame"]["ground"], boundary
    assert boundary["inactive"]["labelGround"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["labelInk"] == boundary["palette"]["ink"], boundary
    assert (
        boundary["selected"]["labelPadding"] == boundary["inactive"]["labelPadding"]
    ), boundary
    assert boundary["selected"]["labelDecoration"] == "none", boundary
    assert boundary["inactive"]["labelDecoration"] == "none", boundary
    assert boundary["selected"]["beforeContent"] == "none", boundary
    assert boundary["inactive"]["beforeContent"] == "none", boundary
    assert boundary["opening"]["top"] - boundary["strip"]["bottom"] >= 16, boundary
    assert boundary["opening"]["left"] - boundary["tabs"]["left"] >= 16, boundary
    assert boundary["tabs"]["right"] - boundary["opening"]["right"] >= 16, boundary
    assert boundary["tabs"]["bottom"] - boundary["closing"]["bottom"] >= 16, boundary
    assert boundary["next"]["top"] > boundary["tabs"]["bottom"], boundary

    selected = page.locator('#workstreams [aria-selected="true"]')
    selected.focus()
    focus = selected.evaluate(
        """element => {
          const style = getComputedStyle(element);
          return {width: parseFloat(style.outlineWidth), style: style.outlineStyle};
        }"""
    )
    assert focus["width"] > 0 and focus["style"] != "none", focus
    assert errors == []
    page.close()


def test_keys_answer_a_question_from_its_marks(browser, serve):
    """The Ask's digits stay live while a mark adds only its control-local keys.

    One Tab enters the marks, where ↑/↓ walk the options and clamp at the ends.
    Moving focus does not replace the Ask's numeric action context with a widget copy.
    """
    page, errors = open_page(browser, serve(ASKS_PAGE))
    nums = page.locator("#live-question > lf-option > .lf-address")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("a")
    position = page.locator(".lf-walk-position")
    expect(position).to_have_text("Ask 1 of 4 open")
    expect(position).to_have_attribute("aria-hidden", "true")
    expect(position.locator("xpath=parent::*")).to_have_class(re.compile("lf-chrome"))
    marks = page.locator("#live-question .lf-pick")
    # The arrival stands on the Ask, which wears its options' digits; the marks
    # are the next Tab stops.
    expect(
        page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    page.keyboard.press("Tab")
    expect(marks.first).to_be_focused()
    expect(position).to_have_text("Ask 1 of 4 open")
    expect(
        page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    expect(nums.first).to_be_visible()
    expect(nums.nth(1)).to_have_text("2")
    assert marks.first.get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Space 1"
    )
    assert marks.nth(1).get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Space 2"
    )

    page.keyboard.press("ArrowUp")
    expect(marks.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()

    with sending(page, "the numbered pick"):
        page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")
    expect(position).to_be_hidden()
    acts = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"options": ["lq-keep"]}
    assert errors == []
    page.close()


def test_the_ask_walk_position_stays_at_the_page_head(browser, serve):
    """Navigation state keeps one roomy place while its destination and face change."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 390, 780)
    position = page.locator(".lf-walk-position")
    expect(position).to_be_hidden()
    expect(page.locator(".lf-banner-menu > .lf-asks")).to_have_count(1)

    page.keyboard.press("a")
    expect(position).to_have_text("Ask 1 of 4 open")
    expect(position).to_be_hidden()
    resized(page, 1200, 780)
    expect(position).to_be_visible()
    geometry = page.evaluate(
        """() => {
          const box = (selector) => document.querySelector(selector).getBoundingClientRect();
          const position = box('.lf-walk-position');
          const line = box('.lf-shortcut-bar');
          const positionStyle = getComputedStyle(
            document.querySelector('.lf-walk-position'));
          const lineStyle = getComputedStyle(document.querySelector('.lf-shortcut-bar'));
          const banner = box('.lf-banner');
          return {position: {left: position.left, right: position.right,
                             top: position.top, bottom: position.bottom},
                  line: {left: line.left, right: line.right,
                         top: line.top, bottom: line.bottom},
                  banner: {bottom: banner.bottom},
                  first: document.querySelector('.lf-shortcut-bar').firstElementChild
                    .className,
                  parent: document.querySelector('.lf-walk-position').parentElement
                    .className,
                  face: {background: positionStyle.backgroundColor,
                         lineBackground: lineStyle.backgroundColor,
                         border: positionStyle.borderTopWidth,
                         shadow: positionStyle.boxShadow},
                  font: {line: parseFloat(lineStyle.fontSize),
                         position: parseFloat(positionStyle.fontSize)},
                  userSelect: positionStyle.userSelect};
        }"""
    )
    assert "lf-walk-position" not in geometry["first"], geometry
    assert "lf-chrome" in geometry["parent"], geometry
    assert geometry["position"]["left"] == 18, geometry
    assert geometry["position"]["top"] == geometry["banner"]["bottom"] + 14, geometry
    assert geometry["position"]["bottom"] < geometry["line"]["top"], geometry
    assert geometry["font"]["position"] > geometry["font"]["line"], geometry
    assert geometry["face"]["background"] == geometry["face"]["lineBackground"], (
        geometry
    )
    assert geometry["face"]["border"] == "1px", geometry
    assert geometry["face"]["shadow"] == "none", geometry
    assert geometry["userSelect"] == "none", geometry

    for index in range(2, 5):
        page.keyboard.press("a")
        expect(position).to_have_text(f"Ask {index} of 4 open")
    expect(position).not_to_have_attribute("data-lf-boundary", "")
    ordinary = position.evaluate("node => getComputedStyle(node).backgroundColor")
    page.keyboard.press("a")
    expect(position).to_have_text("Ask 4 of 4 open")
    expect(position).to_have_attribute("data-lf-boundary", "")
    assert position.evaluate(
        "node => ({left: node.getBoundingClientRect().left, "
        "top: node.getBoundingClientRect().top})"
    ) == {
        "left": geometry["position"]["left"],
        "top": geometry["position"]["top"],
    }
    assert (
        position.evaluate("node => getComputedStyle(node).backgroundColor") != ordinary
    )
    expect(position).not_to_have_attribute("data-lf-boundary", "")

    page.locator("#h").click()
    expect(position).to_be_hidden()
    assert errors == []
    page.close()


def test_a_questions_digits_are_drawn_whole(browser, serve):
    """An address arrives into room its option is already holding, and lands on nothing.

    Every earlier placement borrowed that room instead, and each borrow showed. On the
    cell's outer corner the chip was half outside a group that clips itself, so no
    address the product drew had ever been whole — seven of its seventeen pixels gone,
    and in a bare-label group the first digit was a sliver.
    Out in the page margin beside the group it was whole and it was in the neighbouring
    card's prose, because a middle column's margin is another cell. Neither showed up
    as a failure: a clipped element still reports its whole box and still answers
    `to_be_visible`, and a chip drawn over words breaks no rule anybody had written.

    So the cell holds a place for it, and this asks the two questions that place
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them. Rows reserve a leading gutter;
    titled cards share their trailing header-state slot with the same Ask-owned address
    that temporarily replaces status.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one 8px it was level with a 15px row, and the day the row went to the
    page's own 17px it was two pixels too high with the gate still green — because what
    the gate read was the number the theme stated, and the claim beside it, that a row's
    digit is level with its words, was checked by nothing.

    How far in it stands is each form's own relation: edge, digit, then prose for a row;
    prose opening, then digit, then edge for a card. The two forms deliberately no longer
    claim one rail, while every option within a form still claims one stable seat."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    seats = {"card": {}, "row": {}}
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "card"),
        (["r-now", "r-later"], "row"),
    ]:
        page.keyboard.press("a")
        # The arrival stands on the Ask; the digits are drawn once a mark holds the
        # focus, one Tab in.
        page.keyboard.press("Tab")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-address")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it, and never in either neighbour's room. Rows put the address in
            # the leading gutter; cards put it in their trailing header-state slot.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            if sitting == "card":
                assert 0 < sits["opens"] < sits["x"] < sits["ends"] < sits["width"], (
                    f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a card whose "
                    f"words open at {sits['opens']} and whose far edge is "
                    f"{sits['width']}, so it is not in the trailing state slot"
                )
                assert round(sits["y"]) == 8, (
                    f"{id_}'s digit sits {sits['y']} down from its option's top, not in "
                    "the card's header-state corner"
                )
            else:
                assert 0 < sits["x"] < sits["ends"] < sits["opens"], (
                    f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a row whose "
                    f"words open at {sits['opens']}, so its leading gutter is holding "
                    "one of the two in the other's room"
                )
                assert abs(sits["level"]) <= 0.5, (
                    f"{id_}'s digit is {sits['level']}px off the middle of its row's own "
                    "words"
                )
            seats[sitting].setdefault(round(sits["x"], 1), []).append(id_)
            assert sits["past"] <= 0, (
                f"{id_}'s digit hangs past its own option and onto the next"
            )
            # Asked of the words rather than of the numbers, because the numbers are
            # only right for as long as the column the theme reserves is.
            on = chip.evaluate(OVER_WORDS, id_)
            assert on is None, f"{id_}'s digit is drawn over the words “{on}”"
    assert all(len(form) == 1 for form in seats.values()), (
        f"the digits move between seats within one form: {seats}"
    )
    assert errors == []
    page.close()


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the reader's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'contents'"
    )

    passage = " ".join(page.locator("#p").inner_text().split())
    quote = composer_quote(page)
    assert pending_text(page) == passage, (
        f"the page marks {pending_text(page)!r}, but the composer is anchored to {quote['text']!r}"
    )
    assert not quote["shown"], (
        f"the passage is marked on the page and the composer prints it as well: {quote['text']!r}"
    )
    # Out of sight, not gone: it is what the box's description resolves to, and a screen
    # reader hears nothing from a painted mark.
    assert quote["text"] == f"“{passage}”", (
        f"the composer's description of its passage says {quote['text']!r}"
    )
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-composer textarea').getAttribute('aria-describedby')"
        )
        == "lf-composer-quote"
    ), "nothing announces what the box is anchored to"
    # Carrying that description costs the node an id, which is what makes it the one piece
    # of injected chrome that could answer "which section of the document is this in" with
    # itself. The reading position rides on that answer, so a reload would scroll to the
    # comment box instead of to the page.
    assert (
        page.evaluate(
            "() => document.getElementById('lf-composer-quote')"
            ".closest('[id]:not(.lf-ui)')?.id ?? null"
        )
        is None
    ), "the composer's own quote offers itself as a landmark in the document"

    # A comment landing from elsewhere re-runs the anchor pass, which splits the text
    # nodes the painted range is pinned to. The reader is mid-sentence; their passage
    # can neither blink out nor come back covering the wrong words.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "arriving mid-sentence",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert pending_text(page) == passage, (
        "a poll landing while the composer is open disturbed the passage"
    )

    page.keyboard.press("Escape")
    assert pending_text(page) == "", "the highlight outlived its composer"

    # A passage with the runtime's own chrome inside it paints around the chrome, the way
    # the search reads around it — one range per segment, not one spanning the lot.
    # Across both options, so a Choose button falls in the middle of the passage rather
    # than after it — where a single range spanning the whole thing would swallow it.
    chrome = page.locator("#opts .lf-pick").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert chrome not in pending_text(page), (
        f"the highlight painted the widget's own {chrome!r} control along with the passage"
    )
    page.keyboard.press("Escape")

    # A diagram has no text to quote, so its anchor is the element and its mark is an
    # outline. That one the anchor pass really does take down, so it has to be redrawn.
    page.locator("#fig svg").click(modifiers=["Alt"])
    page.locator(".lf-fab-input").click()
    page.locator("#fig.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], (
        "the outline is on the figure and the composer names its section as well"
    )
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "revision": 1, "text": "and another"},
    )
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.keyboard.press("Escape")
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the mark outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's mark over no thread"
    )

    # A drag across the caption remains a native selection, so the composer carries the
    # caption's words rather than the enclosing figure's element anchor.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert "specimen" in pending_text(page), (
        "the visual containing the drag replaced its selected passage"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element mark over a live selection"
    )
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_pointer_over_a_page_mark_lights_its_comment_quote(browser, serve):
    """The page and panel are reciprocal views of a thread. Resting on a card lights
    its passage; resting on that passage must identify the bounded quote naming it too.
    Filling the card instead turns a long conversation into a viewport-sized wash. The
    signal follows the pointer from one thread to the next and leaves with it."""
    url = serve(
        INLINE_PAGE,
        anchored=[("p", "bold text"), ("p2", "neighbouring block")],
    )
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id, second_id = (comment["id"] for comment in comments)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    first = page.locator(f'.lf-thread[data-id="{first_id}"]')
    second = page.locator(f'.lf-thread[data-id="{second_id}"]')
    first_quote = first.locator(":scope > .lf-thread-head > .lf-quote")
    resting = first.evaluate("element => getComputedStyle(element).backgroundColor")
    quote_resting = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    page.mouse.move(*mark_point(page, "lf-mark", 0))
    expect(first).to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        first.evaluate("element => getComputedStyle(element).backgroundColor")
        == resting
    ), "pointing at a passage washed the whole thread card instead of its quote"
    quote_lit = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert quote_lit != quote_resting, (
        f"the page named the quote in class but its paint stayed {quote_resting!r}"
    )
    assert first_quote.bounding_box()["height"] < first.bounding_box()["height"]

    page.mouse.move(*mark_point(page, "lf-mark", 1))
    expect(first).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))

    page.mouse.move(2, 2)
    expect(page.locator(".lf-thread.lf-mark-hover")).to_have_count(0)

    # A narrowing can put a different card under a hand that has not moved. The list
    # reconcile is therefore one of the hover's inputs, just like page geometry.
    page.mouse.move(*card_body(page, "About this bit."))
    wait_hovered(page, "bold text")
    page.fill(".lf-find-box", "neighbouring block")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))
    wait_hovered(page, "neighbouring block")
    assert errors == []
    page.close()


def test_a_page_mark_does_not_wash_a_long_thread_card(browser, serve):
    """The reciprocal cue stays at the quote when its conversation is taller than the
    list. A short-card case proves selector routing but cannot reproduce the full-panel
    slab that made direct navigation visually ambiguous."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": root,
            "revision": 1,
            "text": "\n\n".join(
                f"Consideration {i}: this thread needs its full context."
                for i in range(24)
            ),
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    quote = thread.locator(":scope > .lf-thread-head > .lf-quote")
    card_resting = thread.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    quote_resting = quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert (
        thread.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    ), "the card fits in the list, so this does not reproduce the large wash"

    page.mouse.move(*mark_point(page, "lf-mark"))
    expect(thread).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        thread.evaluate("element => getComputedStyle(element).backgroundColor")
        == card_resting
    )
    assert (
        quote.evaluate("element => getComputedStyle(element).backgroundColor")
        != quote_resting
    )
    assert (
        quote.bounding_box()["height"]
        < page.locator(".lf-threads").bounding_box()["height"]
    )
    assert errors == []
    page.close()


def test_a_thread_walk_starts_one_page_trip_and_reveals_its_nested_passage(
    browser, serve
):
    """The range travel has two jobs: reveal a passage inside its nested scrollports,
    then centre it vertically in the document. `scrollIntoView` also moved the document,
    jumping it to the nearest edge synchronously before the intended smooth centred trip
    began. Both local axes must remain immediate, while the page makes only one move."""
    lead = "".join(
        f"<p>Reading context before the passage, line {i}.</p>" for i in range(32)
    )
    tail = "".join(
        f"<p>Reading context after the passage, line {i}.</p>" for i in range(20)
    )
    source = leaf_page(
        "one thread trip",
        f"""
<h1>One thread trip</h1>
{lead}
<div id="local">
  {"".join(f"<p>Local context line {i}.</p>" for i in range(16))}
  <pre id="rail"><code>{"prefix " * 80}Far-side passage to review.</code></pre>
</div>
{tail}
""",
        head=(
            "<style>#local { max-height: 240px; overflow-y: auto; "
            "overflow-x: clip; }</style>"
        ),
    )
    page, errors = open_page(
        browser,
        serve(source, anchored=[("far", "Far-side passage")]),
    )
    page.evaluate(
        """() => {
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
          document.querySelector('#rail').scrollLeft = 0;
          window.lfFirstPageScroll = null;
          document.addEventListener('scroll', (event) => {
            if (event.target === document && window.lfFirstPageScroll === null)
              window.lfFirstPageScroll = document.scrollingElement.scrollTop;
          }, {capture: true});
        }"""
    )

    page.keyboard.press("t")
    page.wait_for_function("() => window.lfFirstPageScroll !== null")
    immediate = page.evaluate(
        """() => ({
          firstPage: window.lfFirstPageScroll,
          rail: document.querySelector('#rail').scrollLeft,
          local: document.querySelector('#local').scrollTop,
          localXFits: document.querySelector('#local').scrollWidth
            <= document.querySelector('#local').clientWidth,
        })"""
    )
    assert immediate["firstPage"] < 100, (
        f"the thread walk jumped the page before its smooth trip began: {immediate}"
    )
    assert immediate["rail"] > 0, (
        f"the passage stayed beyond its own horizontal scroller: {immediate}"
    )
    assert immediate["local"] > 0, (
        f"the passage stayed beyond its own vertical scroller: {immediate}"
    )
    assert immediate["localXFits"], (
        f"the vertical scrollport also overflowed sideways: {immediate}"
    )
    page.wait_for_function(
        """() => {
          const range = [...(CSS.highlights.get('lf-mark-here') ?? [])][0];
          if (!range) return false;
          const rect = range.getBoundingClientRect();
          return Math.abs((rect.top + rect.bottom) / 2 - innerHeight / 2) < 2;
        }"""
    )
    expect(page.locator(".lf-margin-preview .lf-conversation-thread")).to_be_focused()
    assert errors == []
    page.close()


def test_the_thread_walk_stays_inline_until_threads_is_opened(browser, serve):
    """t/T use page-local threads without moving the walk position."""
    page, errors = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": 1200, "height": 844})
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]

    def position_is_front():
        return page.evaluate(
            """() => {
              const readout = document.querySelector('.lf-walk-position');
              const box = readout.getBoundingClientRect();
              readout.style.pointerEvents = 'auto';
              const front = document.elementFromPoint(
                (box.left + box.right) / 2,
                (box.top + box.bottom) / 2,
              ) === readout;
              readout.style.removeProperty('pointer-events');
              return front;
            }"""
        )

    # A panel search belongs to the panel. Closing it keeps that search for the next
    # visit, but must not silently remove a visible page thread from the inline walk.
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page, True)
    page.fill(".lf-find-box", "neighbouring block")
    expect(page.locator(f'.lf-thread[data-id="{roots[0]}"]')).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{roots[1]}"]')).to_be_visible()
    position = page.locator(".lf-walk-position")
    page.locator(".lf-threads").focus()
    page.keyboard.press("n")
    expect(page.locator(f'.lf-thread[data-id="{roots[1]}"]')).to_be_focused()
    expect(position).to_have_text("Thread 1 of 1 shown")
    expect(position.locator("xpath=parent::*")).to_have_class(re.compile("lf-chrome"))
    expect(position.locator("xpath=ancestor::*[@id='lf-shortcut-bar']")).to_have_count(
        0
    )
    panel_position = position.evaluate(
        "node => ({left: node.getBoundingClientRect().left, "
        "top: node.getBoundingClientRect().top, "
        "bottom: node.getBoundingClientRect().bottom})"
    )
    assert position_is_front(), "the open Threads panel painted over its walk position"
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page, False)
    expect(position).to_be_hidden()

    page.keyboard.press("t")
    first = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{roots[0]}"]'
    )
    expect(first).to_be_focused()
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(position).to_have_text("Thread 1 of 2")
    expect(position).to_have_attribute("aria-hidden", "true")
    expect(position.locator("xpath=parent::*")).to_have_class(re.compile("lf-chrome"))
    assert (
        position.evaluate(
            "node => ({left: node.getBoundingClientRect().left, "
            "top: node.getBoundingClientRect().top, "
            "bottom: node.getBoundingClientRect().bottom})"
        )
        == panel_position
    )
    assert position_is_front(), "the margin thread painted over its walk position"

    page.keyboard.press("t")
    second = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{roots[1]}"]'
    )
    expect(second).to_be_focused()
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(position).to_have_text("Thread 2 of 2")

    ordinary = position.evaluate("node => getComputedStyle(node).backgroundColor")
    page.keyboard.press("t")
    expect(second).to_be_focused()
    expect(position).to_have_text("Thread 2 of 2")
    expect(position).to_have_attribute("data-lf-boundary", "")
    assert (
        position.evaluate("node => getComputedStyle(node).backgroundColor") != ordinary
    )
    expect(position).not_to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Shift+t")
    expect(first).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2")

    page.keyboard.press("Shift+t")
    expect(first).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel = page.locator(f'.lf-thread[data-id="{roots[0]}"]')
    expect(panel).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(first).to_be_focused()
    page.keyboard.press("Enter")
    expect(first.locator("textarea")).to_be_focused()
    assert errors == []
    page.close()


def test_an_absent_walk_destination_returns_to_the_callers_fallback(browser, serve):
    """A missing visual destination leaves the caller's announcement path live."""
    url = serve(NOTED_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A page-level thread.",
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page, True)
    page.fill(".lf-find-box", "no matching thread")
    expect(page.locator(".lf-thread")).to_be_hidden()
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page, False)
    page.locator("body").focus()
    fallback = page.evaluate(
        """async () => {
          const {beginWalk, walkPositionLabel} = await import('/runtime/walk-position.js');
          return beginWalk('thread', 'Thread', () => null) ??
            walkPositionLabel('Thread', 1, 1);
        }"""
    )
    assert fallback == "Thread 1 of 1"
    expect(page.locator(".lf-walk-position")).to_be_hidden()

    page.keyboard.press("t")
    expect(page.locator(".lf-live")).to_contain_text("Thread 1 of 1")

    assert errors == []
    page.close()


def test_an_inline_thread_uses_surface_focus_until_its_reply_takes_over(browser, serve):
    """A thread is a current region; its reply is the control taking the next press."""
    page, errors = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text")]),
    )
    thread = page.locator(".lf-margin-preview .lf-conversation-thread")
    note = page.locator("#p .lf-mark-note")

    note.click()
    expect(thread).to_be_focused()
    assert not thread.evaluate("el => el.matches(':focus-visible')")
    pointer = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
          outline: s.outlineStyle, background: s.backgroundColor,
          shadow: s.boxShadow,
        }; }"""
    )
    # The preview builds the thread when it opens it, and opening it from the mark
    # makes it current, so the resting tint is only readable from the same element
    # once the region gives the focus back.
    resting = thread.evaluate(
        "el => { el.blur(); return getComputedStyle(el).backgroundColor; }"
    )
    assert pointer["outline"] == "none"
    assert pointer["background"] != resting
    assert pointer["shadow"] == "none"

    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    current = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
          outline: s.outlineStyle, background: s.backgroundColor,
          shadow: s.boxShadow,
        }; }"""
    )
    assert current["outline"] == "none"
    assert current == pointer

    page.keyboard.press("Enter")
    reply = thread.locator("textarea")
    expect(reply).to_be_focused()
    writing = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
          outline: s.outlineStyle, background: s.backgroundColor,
          shadow: s.boxShadow,
        }; }"""
    )
    reply_ring = reply.evaluate(
        """el => { const s = getComputedStyle(el); return {
          style: s.outlineStyle, width: s.outlineWidth, offset: s.outlineOffset,
          border: s.borderColor,
        }; }"""
    )
    assert writing == current
    # One ring and no accented border: the reply wears the text box's band, which
    # replaces the resting border rather than standing off it. `theme.css` states
    # that inside `.lf-conversation-thread` so a thread seated in a widget's shadow
    # tree wears the same band, and the chrome text-box rule states it for the
    # document; both say the same thing, so this reading is the same either way.
    assert reply_ring == {
        "style": "solid",
        "width": "2px",
        "offset": "0px",
        "border": "rgba(0, 0, 0, 0)",
    }
    assert errors == []
    page.close()


def test_forced_colors_keep_inline_thread_focus_visible(browser, serve):
    """The system focus outline replaces the surface paint high contrast removes."""
    url = serve(SEATED_QUESTION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    context = browser.new_context(forced_colors="active")
    try:
        page, errors = open_page(
            browser,
            url,
            context=context,
        )
        thread = page.locator(f'#jobs .lf-conversation-thread[data-thread="{root}"]')

        reply = thread.locator("textarea")
        reply.click()
        expect(reply).to_be_focused()
        assert thread.evaluate("el => el.matches(':focus-within')")
        focus = thread.evaluate(
            """el => { const s = getComputedStyle(el); return {
              style: s.outlineStyle, width: s.outlineWidth,
              offset: s.outlineOffset, shadow: s.boxShadow,
            }; }"""
        )
        assert focus == {
            "style": "solid",
            "width": "2px",
            "offset": "-2px",
            "shadow": "none",
        }
        assert errors == []
    finally:
        context.close()


def test_inline_thread_surface_has_room_without_focus_reflow(browser, serve):
    """The region owns the breathing room its current surface requires."""
    url = serve(SEATED_QUESTION_PAGE)
    panel_comment(serve.page_dir, "First job note", {"section": "jobs"})
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    page, errors = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-conversation-thread[data-thread="{root}"]')
    expect(page.locator("#jobs .lf-conversation-thread")).to_have_count(2)

    resting = thread.evaluate(
        "el => ({width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})"
    )
    reply = thread.locator("textarea")
    reply.click()
    expect(reply).to_be_focused()
    focused = thread.evaluate(
        "el => ({width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})"
    )
    assert focused == resting, (
        "the current surface changed the inline thread's geometry"
    )

    frame = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
          padding: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft],
          borderTop: s.borderTopWidth,
        }; }"""
    )
    assert len(set(frame["padding"])) == 1, (
        f"a later inline thread inherited an asymmetric current edge: {frame}"
    )
    assert frame["borderTop"] == "0px", (
        f"a sibling separator remained inside the current region: {frame}"
    )

    separator = thread.evaluate(
        """el => { const s = getComputedStyle(el, '::before'); return {
          content: s.content, borderTop: s.borderTopWidth,
        }; }"""
    )
    assert separator == {"content": '""', "borderTop": "1px"}, (
        f"the gap between inline threads lost its separator: {separator}"
    )

    resolve = thread.locator(":scope > .lf-resolve")
    expect(resolve).to_have_css("position", "absolute")
    placement = thread.evaluate(
        """el => {
          const own = el.getBoundingClientRect();
          const inset = parseFloat(getComputedStyle(el).paddingTop);
          const control = el.querySelector(':scope > .lf-resolve').getBoundingClientRect();
          const headNode = el.querySelector(
            ':scope > .lf-conversation-msg:first-of-type > .lf-conversation-head'
          );
          const head = headNode.getBoundingClientRect();
          const author = headNode.querySelector('b').getBoundingClientRect();
          const bodyNode = el.querySelector(
            ':scope > .lf-conversation-msg:first-of-type > .lf-conversation-body'
          );
          const body = bodyNode.getBoundingClientRect();
          return {controlTop: control.top, expectedTop: own.top + inset,
                  controlBottom: control.bottom, headTop: head.top,
                  headBottom: head.bottom, authorBottom: author.bottom,
                  bodyTop: body.top,
                  bodyMargin: parseFloat(getComputedStyle(bodyNode).marginTop)};
        }"""
    )
    assert placement["controlTop"] == pytest.approx(placement["expectedTop"], abs=1)
    assert placement["controlBottom"] <= placement["headBottom"], (
        f"Resolve hung below the first inline message's row: {placement}"
    )
    assert placement["headTop"] < placement["controlBottom"], (
        f"Resolve took a row above the first inline message: {placement}"
    )
    assert placement["bodyTop"] - placement["authorBottom"] == pytest.approx(
        placement["bodyMargin"], abs=1
    ), f"the first inline message has extra space below its author: {placement}"

    clearances = thread.evaluate(
        """el => {
          const root = el.getBoundingClientRect();
          return [...el.children]
            .filter(child => child.getClientRects().length && getComputedStyle(child).display !== 'none')
            .flatMap(child => {
              const box = child.getBoundingClientRect();
              return [box.left - root.left, root.right - box.right,
                      box.top - root.top, root.bottom - box.bottom];
            });
        }"""
    )
    assert clearances and min(clearances) >= 3, (
        f"the current surface landed on inline thread content: {clearances}"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("long_thread", [False, True], ids=["short", "long"])
def test_pressing_a_page_mark_stands_in_the_thread_it_opens(
    browser, serve, long_thread
):
    """Pointer arrival opens one layer directly in its reply box. A thread reached by
    t opens on its card, so c or Enter adds a second layer and Escape returns through
    each one. The Page-map fallback remains live at the same time: this proves declaration
    order cannot move it ahead of the causal frame. The page mark follows both focus modes."""
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    if long_thread:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "claude",
                "parent": root,
                "revision": 1,
                "text": "\n\n".join(
                    f"Consideration {i}: the response needs room for its explanation."
                    for i in range(18)
                ),
            },
        )
    page, errors = open_page(browser, url)
    threads = page.locator(".lf-threads > .lf-thread:not([hidden])")
    first_id = threads.first.get_attribute("data-id")
    second_id = threads.nth(1).get_attribute("data-id")
    thread = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{first_id}"]'
    )
    second = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{second_id}"]'
    )
    reply = thread.locator("textarea")

    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))

    expect(reply).to_be_focused()
    expect(reply).to_be_visible()
    wait_standing(page, "bold text")
    assert "close thread" in shortcut_bar_text(page)
    page.keyboard.press("t")
    expect(reply).to_have_value("t")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    assert "reply" in shortcut_bar_text(page)
    # The walk itself made no return frame. Its Page-map fallback is still live, but a
    # sequence armed afterwards is an inner mode and Escape cancels that mode first.
    page.keyboard.press("g")
    assert "cancel" in shortcut_bar_text(page)
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(second).to_be_focused()
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Enter")
    expect(second.locator("textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("Shift+t")
    expect(second).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_be_visible()

    # With Threads already open, the same page mark takes the indexed route and keeps
    # the panel's long-thread landing guarantees.
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel_thread = threads.first
    panel_reply = panel_thread.locator(":scope > .lf-compose textarea")
    if long_thread:
        # Opening the mark focuses its reply before native smooth placement finishes.
        # Arm the list itself immediately before that gesture. A prior scrollend cannot
        # pass without a causal move, and a preliminary one is withdrawn if a later frame
        # continues the same arrival.
        page.evaluate(
            """() => {
              const list = document.querySelector('.lf-threads');
              const rest = window.__lfThreadScrollRest = {
                at: null, event: 0, moved: false, start: list.scrollTop,
              };
              list.addEventListener('scroll', () => {
                rest.at = null;
                rest.moved ||= list.scrollTop !== rest.start;
              }, {passive: true});
              list.addEventListener('scrollend', () => {
                const event = ++rest.event;
                const at = list.scrollTop;
                requestAnimationFrame(() => {
                  if (rest.event === event && list.scrollTop === at) rest.at = at;
                });
              });
            }"""
        )
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(panel_reply).to_be_focused()
    in_threads_scrollport(page, ".lf-threads > .lf-thread:first-of-type .lf-compose")
    if long_thread:
        page.wait_for_function(
            """() => {
              const list = document.querySelector('.lf-threads');
              const rest = window.__lfThreadScrollRest;
              return rest.moved && rest.at === list.scrollTop;
            }"""
        )
        landing = page.evaluate(
            """() => {
              const list = document.querySelector('.lf-threads');
              const thread = list.querySelector('.lf-thread:first-of-type');
              const compose = thread.querySelector(':scope > .lf-compose');
              const view = list.getBoundingClientRect();
              const target = compose.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(list).scrollPaddingTop) || 0;
              const start = view.top + clear;
              const head = list.querySelector('.lf-pinned').getBoundingClientRect();
              const blocks = [...thread.querySelectorAll(
                ':scope > .lf-msg, :scope > .lf-msg .lf-msg-body > *, ' +
                ':scope > .lf-msg .lf-msg-text > *'), compose]
                .map((block) => ({
                  name: block.className || block.tagName,
                  top: block.getBoundingClientRect().top,
                }));
              const lines = [];
              const walker = document.createTreeWalker(thread, NodeFilter.SHOW_TEXT);
              for (let text; text = walker.nextNode();) {
                if (!text.data.trim()) continue;
                for (let i = 0; i < text.length; i++) {
                  const range = document.createRange();
                  range.setStart(text, i);
                  range.setEnd(text, Math.min(i + 1, text.length));
                  const line = range.getBoundingClientRect();
                  if (line.width && line.top < head.bottom && line.bottom > head.bottom)
                    lines.push(line.toJSON());
                }
              }
              return {target: target.toJSON(), listBottom: view.bottom, start, blocks,
                      crossedLines: lines};
            }"""
        )
        assert landing["target"]["bottom"] <= landing["listBottom"]
        assert any(
            block["top"] == pytest.approx(landing["start"], abs=2)
            for block in landing["blocks"]
        ), f"the long arrival cut through a content block: {landing}"
        assert not landing["crossedLines"], (
            f"the pinned heading cut through a text line: {landing}"
        )
    assert errors == []
    page.close()


def test_the_page_marks_the_comment_the_reader_is_standing_in(browser, serve):
    """A reader sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike. The page says which one they asked for too: the
    thread holding the focus paints its own passage apart from the rest for as long as
    the reader remains in that thread.

    Read off the focus rather than off the travel, so it answers where the reader *is*.
    The walk moves it, a reply box keeps it — standing in a comment is standing in it
    while writing back — and leaving the thread takes it down, rather than leaving a
    page wearing "you are here" about a comment nobody is in."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    assert standing_mark(page) == {
        "text": "",
        "elements": [],
    }, "a page nobody has opened a comment on is already saying the reader is in one"

    page.keyboard.press("t")
    wait_standing(page, "bold text")

    # The four readings of a marked passage have to stay in this order, or one of them
    # stops being visible where they overlap: the posted mark, the hover over it, the
    # standing comment's own ink, and above all three the draft the reader is writing.
    # Asked with the pointer actually resting on the standing mark, because that is the
    # overlap the order exists for and because nothing registers the hover until a mouse
    # has been over a passage. A higher highlight supplies only the properties it states,
    # so this is what lets one mark say "clickable" and "you are here" at once.
    # Opening the inline card moves the document to the passage; settle it before
    # reading pointer geometry.
    page_at_rest(page)
    page.mouse.move(*mark_point(page, "lf-mark-here"))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark-hover')?.size ?? 0) > 0")
    ranks = page.evaluate(
        """() => ['lf-mark', 'lf-mark-hover', 'lf-mark-here', 'lf-pending']
            .map(n => CSS.highlights.get(n)?.priority ?? null)"""
    )
    assert all(r is not None for r in ranks) and ranks == sorted(set(ranks)), (
        f"the marks' paint order is not strictly increasing: {ranks}"
    )
    assert standing_mark(page)["text"] == "bold text", (
        "the pointer resting on the standing mark took its own ink away"
    )

    page.keyboard.press("t")
    wait_standing(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("t")
    wait_standing(page, "", ["fig"])
    page.keyboard.press("t")
    expect(
        page.locator(
            f'.lf-margin-preview .lf-conversation-thread[data-thread="{roots[2]}"]'
        )
    ).to_be_focused()
    wait_standing(page, "", ["fig"])
    page.keyboard.press("Shift+t")
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Shift+t")
    wait_standing(page, "bold text")
    page.keyboard.press("Shift+t")
    first = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{roots[0]}"]'
    )
    expect(first).to_be_focused()
    wait_standing(page, "bold text")

    # Standing in a comment while writing back to it is still standing in it: the reply
    # box is inside the thread, and knowing which passage it is on is worth most there.
    first.locator("textarea").focus()
    wait_standing(page, "bold text")

    # And leaving the thread takes it down. A mark that outlived the reader's attention
    # would be a page insisting on a comment nobody is in.
    page.evaluate("() => document.activeElement.blur()")
    wait_standing(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the standing one"
    )
    assert errors == []
    page.close()


def test_a_hovered_thread_rebinds_to_a_replaced_anchor(browser, serve):
    """A live version replaces the authored nodes but keeps the thread and its anchor.
    With the pointer parked on that card, the semantic hover id does not change; its
    Range still must move from the detached v1 text node onto the connected v2 one."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    point = card_body(page, "About this bit.")
    page.mouse.move(*point)
    wait_hovered(page, "bold text")
    page.evaluate(
        "() => { window.__lfOldHoverNode = "
        "[...CSS.highlights.get('lf-mark-hover')][0].startContainer; }"
    )
    # Keep the same live card under the pointer throughout the swap. This isolates the
    # anchor pass's record replacement from the view transition's temporary snapshots.
    page.evaluate("() => { document.startViewTransition = undefined; }")

    v2 = INLINE_PAGE.replace(
        "<strong>bold text</strong>", '<span data-v2="true">bold text</span>'
    )
    _publish(serve.page_dir, 2, v2, "kept the passage while replacing its markup")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.wait_for_selector('[data-v2="true"]')
    wait_hovered(page, "bold text")
    state = page.evaluate("""() => {
        const range = [...CSS.highlights.get('lf-mark-hover')][0];
        return {
            oldConnected: window.__lfOldHoverNode.isConnected,
            text: range?.toString() ?? null,
            rebound: Boolean(range && range.startContainer !== window.__lfOldHoverNode),
            connected: Boolean(range?.startContainer.isConnected),
            card: document.querySelector('.lf-thread')?.classList.contains('lf-mark-hover'),
        };
    }""")
    assert state == {
        "oldConnected": False,
        "text": "bold text",
        "rebound": True,
        "connected": True,
        "card": True,
    }, f"the parked hover did not move from the detached v1 anchor to v2: {state}"
    expect(page.locator(".lf-thread")).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert errors == []
    page.close()


def test_the_pointer_over_a_comment_lights_the_passage_it_is_about(browser, serve):
    """A reader scanning a full panel asks the same thing of every card — which of these
    is about what — and pressing one to find out spends a travel they may not want. The
    pointer resting on the card answers it: a card is the thread's view in the list the
    way a mark is its view in the prose, so the same wash lights the same passage from
    either side. The standing mark answers the question for the comment the reader chose;
    this answers it for the one under their hand.

    Read in the frame that already answers the page's own hover, because the pointer is
    in one place and the two readings are one answer: markAt refuses a point that lands
    in the chrome, so a card's reading and a mark's cannot both name a thread, and a
    second writer to this highlight would be overwritten by whichever frame ran last.

    The cursor stays behind on the page. It is the promise that pressing here opens
    something, and over a card the press on offer is the card's own."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")

    assert painted(page, "lf-mark-hover") == "", (
        "a page whose pointer has touched nothing is already lighting a passage"
    )

    # Three things a mark can be — posted, indicated, stood in — are three steps of one
    # wash, and the middle one exists because this gesture puts the pointer over the panel
    # by construction: a hover sharing the standing wash left the two lit identically
    # whenever a hand rested where it had just clicked, with a 2px underline hue the only
    # thing between them.
    #
    # Measured as composited pixels rather than as declarations, because a rule full of
    # var() and color-mix reads back non-empty whatever it resolves to, and two alphas of
    # one hue is exactly the pair a string comparison calls different and the eye does
    # not. So the wash is painted over the page's own ground and the result compared in
    # Lab: ordering by distance from that ground, which holds in both colour schemes
    # because the wash is darker than the page in one and lighter in the other, and a
    # floor under each step, because ordering alone passes a middle set one alpha unit
    # from its neighbour. The floor is 4, against a just noticeable difference near 2.3
    # and the palette's own 6.4 and 6.5 in light, 7.4 and 7.2 in dark.
    ramp = page.evaluate("""() => {
        // The marks' rules are adopted, not linked (runtime/marks.css).
        const rules = [...document.styleSheets, ...document.adoptedStyleSheets].flatMap(s => {
            try { return [...s.cssRules] } catch { return [] }
        });
        const probe = document.createElement('div');
        document.body.append(probe);
        const declared = (name) => {
            const r = rules.find(r => (r.selectorText ?? '') === `::highlight(${name})`);
            if (!r?.style?.backgroundColor) return null;
            probe.style.backgroundColor = r.style.backgroundColor;
            return getComputedStyle(probe).backgroundColor;
        };
        const paper = getComputedStyle(document.body).backgroundColor;
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        const over = (css) => {
            ctx.fillStyle = paper; ctx.fillRect(0, 0, 1, 1);
            if (css !== null) { ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1); }
            return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
        };
        const lab = (px) => {
            const [r, g, b] = px.map(v => {
                const c = v / 255;
                return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
            const f = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
            const x = f((r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047);
            const y = f(r * 0.2126 + g * 0.7152 + b * 0.0722);
            const z = f((r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883);
            return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
        };
        const de = (a, b) => Math.hypot(...lab(a).map((v, i) => v - lab(b)[i]));
        const ground = over(null);
        const steps = {};
        for (const [step, name] of [['posted', 'lf-mark'], ['pointed', 'lf-mark-hover'],
                                    ['standing', 'lf-mark-here']]) {
            const css = declared(name);
            steps[step] = css === null ? null : over(css);
        }
        probe.remove();
        if (Object.values(steps).some(v => v === null)) return {missing: steps};
        return {
            fromGround: Object.fromEntries(
                Object.entries(steps).map(([k, v]) => [k, +de(v, ground).toFixed(2)])),
            apart: {
                'posted→pointed': +de(steps.posted, steps.pointed).toFixed(2),
                'pointed→standing': +de(steps.pointed, steps.standing).toFixed(2),
            },
        };
    }""")
    assert "missing" not in ramp, (
        f"a step of the mark ramp has no wash rule at all: {ramp['missing']}"
    )
    order = ramp["fromGround"]
    assert order["posted"] < order["pointed"] < order["standing"], (
        "the three things a mark can be are not three steps away from the page's own"
        f" ground, so the wash does not rank them: {order}"
    )
    assert min(ramp["apart"].values()) >= 4, (
        "two steps of the mark ramp are too close for a reader to tell apart without one"
        f" of the other beside it: {ramp['apart']}"
    )

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")
    # The wash is the page's, and the cursor is not: body wears lf-over-mark only while
    # the pointer is on the page's own mark, or every card in the panel would promise a
    # press the page does not make — the quote inside the card makes its own.
    assert not page.evaluate(
        "() => document.body.classList.contains('lf-over-mark')"
    ), "resting on a card told the page the pointer was on a mark"

    # It follows the pointer along the list, so a sweep down the panel reads out what
    # each comment is about in turn.
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")

    # An element anchor answers too, in the chrome projection above its descendants.
    # ::highlight paints glyphs and a box has none, so the contour gains weight for the
    # middle step. Without it the pointer over an element-anchored card did nothing at
    # all, which from the panel reads as a broken hover rather than as a passage with no
    # words.
    hovered_el = page.locator("#fig")
    hovered_el.scroll_into_view_if_needed()
    page.mouse.move(*card_body(page, "on the figure"))
    wait_hovered(page, "")
    expect(hovered_el).to_have_class(re.compile(r"\blf-mark-hover\b"))
    hovered_mark = page.locator('.lf-visual-mark[data-for="fig"]')
    expect(hovered_mark).to_have_class(re.compile(r"\blf-visual-mark-hover\b"))
    hovered_width = hovered_mark.evaluate("el => getComputedStyle(el).borderLeftWidth")
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")
    assert (
        hovered_mark.evaluate("el => getComputedStyle(el).borderLeftWidth")
        != hovered_width
    )

    # Standing in one comment while pointing at another says both, because they answer
    # different questions and rank apart: the standing mark keeps its ink above the wash.
    page.locator(".lf-thread").filter(has_text="on the first").first.focus()
    wait_standing(page, "bold text")
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")
    assert standing_mark(page)["text"] == "bold text", (
        "pointing at another comment's card took the standing comment's mark away"
    )

    # And the pointer leaving the panel puts it down, while what the page posted stays.
    page.mouse.move(2, 2)
    wait_hovered(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the pointer's"
    )
    assert errors == []
    page.close()


def test_closing_the_panel_puts_down_the_card_it_was_lighting(browser, serve):
    """The panel going away is the card going out from under the pointer, and the wash it
    was lighting has to go with it. Escape closes the panel from wherever the reader is
    standing, so the pointer never moves and nothing else asks the hover question again —
    the page is left washing a passage with no card, no pointer on it, and nothing on the
    screen that says why."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the first",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")

    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.body.hasAttribute('data-lf-panel')")
    wait_hovered(page, "")
    assert errors == []
    page.close()


def test_a_commented_block_says_so_to_a_screen_reader(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. No ARIA relation reaches a
    block that isn't focusable, so the pass says it in the one thing every screen reader
    announces — text — counting up per block, riding in on a sent comment's round trip,
    and leaving with its thread. Having put words on the page, it then has to keep them
    out of the document's own: out of a selection, out of the next quote, and out of the
    mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    comment({"section": "fig"}, "The figure too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one line rather than two.
    assert "2 comments" in page.locator("#p1").aria_snapshot(), (
        "a screen reader reading the block hears nothing about the comments on it"
    )
    assert page.locator("#p1 .lf-mark-note").count() == 1, "one block, one line"
    # Hidden means hidden from the eye, not the tree: a line that paints is the runtime
    # writing visible prose into the author's paragraph.
    assert page.locator("#p1 .lf-mark-note").evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the hidden line is painting on screen"
    note = page.locator("#p1 .lf-mark-note")
    inline1 = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{c1}"]'
    )
    inline2 = page.locator(
        f'.lf-margin-preview .lf-conversation-thread[data-thread="{c2}"]'
    )
    assert note.evaluate("el => getComputedStyle(el).opacity") == "0"
    expect(note).to_have_role("button")
    note.click()
    expect(inline1).to_be_focused()
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard reader reached it"
    )
    assert note.evaluate("el => getComputedStyle(el).opacity") == "1"
    note.press("Enter")
    expect(inline1).to_be_focused()
    page.keyboard.press("t")
    expect(inline2).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c1})
    told(page)
    expect(note).to_have_text("1 comment")
    note.press("Enter")
    expect(inline2).to_be_focused()
    # An element anchor has no text to paint, and the element it names holds the line.
    assert "1 comment" in page.locator("#fig").aria_snapshot()

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'),
                     {childList: true, characterData: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 4")
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The line belongs to the runtime, not the document: a user dragging across it
    # neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the hidden line came along in the user's own selection"
    )
    page.locator(".lf-fab-input").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the hidden line came along in the quote the comment would store"
    )
    page.keyboard.press("Escape")

    # The gesture's own comment reaches the line once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'contents'"
    )
    page.locator(".lf-composer textarea").fill("Too short.")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    c4 = [e for e in events_model.read_events(d) if e.get("kind") == "comment"][-1][
        "id"
    ]

    # A resolved thread takes its line with it: the pass owns what it wrote.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(0)
    assert "1 comment" in page.locator("#p1").aria_snapshot()

    # A passage crossing two blocks says so in both: a reader landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    assert "2 comments" in page.locator("#p1").aria_snapshot()
    assert "1 comment" in page.locator("#p2").aria_snapshot()
    assert errors == []
    page.close()


def test_generated_hints_fit_the_visible_screen(browser, serve):
    """Every opaque route fits at viewport edges, including below the banner."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "addresses at the edges",
                """
<h1 id="top">Addresses at the edges</h1>
<nav id="edges" aria-label="Edge links">
  <a id="left" href="#top">Left</a>
  <a id="right" href="#top">Right</a>
  <a id="bottom" href="#top">Bottom</a>
  <a id="below-banner" href="#top">Below the banner</a>
  <a id="under-banner" href="#top">Under the banner</a>
  <a id="crowded-left" href="#top">Crowded left</a>
  <a id="crowded-neighbor" href="#top">Crowded neighbor</a>
</nav>
""",
                head="""<style>
  #edges a { position: fixed; display: block; width: 1px; height: 20px;
    overflow: hidden; white-space: nowrap; }
  #left { left: 1px; top: 200px; }
  #right { left: calc(100vw - 1px); top: 280px; }
  #bottom { left: 70vw; top: calc(100vh - 1px); }
  #below-banner { left: 45vw; top: calc(var(--lf-banner-h) + 1px); }
  #under-banner { left: 60vw; top: calc(var(--lf-banner-h) - 8px); }
  #crowded-left { left: 1px; top: 400px; }
  #crowded-neighbor { left: 80px; top: 400px; }
</style>""",
            )
        ),
    )
    under_banner = page.locator("#under-banner")
    under_banner.evaluate(
        """link => {
          const covered = document.querySelector('.lf-banner').getBoundingClientRect().bottom;
          link.style.top = `${covered - 18}px`;
          link.addEventListener('click', () => { link.dataset.activated = 'true'; });
        }"""
    )
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    reading = page.evaluate(
        """() => ({
          width: document.documentElement.clientWidth,
          height: document.documentElement.clientHeight,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          chips: [...document.querySelectorAll(
            '.lf-goto-targets > .lf-sequence-address[data-lf-address]')]
            .map(chip => ({
            route: chip.textContent,
            code: chip.dataset.lfAddress,
            ...chip.getBoundingClientRect().toJSON(),
          })),
        })"""
    )
    assert len(reading["chips"]) == 7, reading
    for chip in reading["chips"]:
        assert 0 <= chip["left"] < chip["right"] <= reading["width"], reading
        assert reading["banner"] <= chip["top"] < chip["bottom"] <= reading["height"], (
            reading
        )
        assert chip["route"] == chip["code"], chip
    under_code = address_code(page, "Link", "under-banner")
    under_index = page.locator(CHIPS).evaluate_all(
        """(chips, code) => chips.findIndex(chip => chip.dataset.lfAddress === code)""",
        under_code,
    )
    for _ in range(under_index + 1):
        page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {under_code}: Link, Under the banner. Press Enter to go there."
    )
    page.keyboard.press("Enter")
    expect(under_banner).to_have_attribute("data-activated", "true")
    expect(page.locator("#top")).to_be_focused()

    page.keyboard.press("g")
    code = address_code(page, "Link", "crowded-neighbor")
    page.keyboard.type(code)
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator("#top")).to_be_focused()
    assert errors == []
    page.close()


def test_target_mnemonics_filter_the_generated_map_without_renumbering_hints(
    browser, serve
):
    """Semantic prefixes narrow the current generated map instead of replacing it.

    A filtered map preserves the codes its members had in the complete map. Its chips
    show only those generated suffixes; the complete route remains in the shortcut bar.
    """
    url = serve(ADDRESSED_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A visible thread.",
            "anchor": {"section": "opts-decision"},
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1280, 800)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")

    page.keyboard.press("?")
    page.keyboard.press("?")
    goto = page.locator(
        ".lf-shortcut-reference-section", has=page.get_by_role("heading", name="Go to")
    )
    filters = goto.locator('tr[data-lf-command^="navigation.target.filter."]')
    assert filters.evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          keys: [...row.querySelectorAll('kbd')].map(key => key.textContent),
          action: row.querySelector('td:last-child').textContent,
        }))"""
    ) == [
        {
            "command": "navigation.target.filter.margin-elements",
            "keys": ["g", "m"],
            "action": "Show only visible margin controls and status indicators",
        },
        {
            "command": "navigation.target.filter.threads",
            "keys": ["g", "t"],
            "action": "Show only visible Thread controls",
        },
        {
            "command": "navigation.target.filter.asks",
            "keys": ["g", "a"],
            "action": "Show only visible Ask controls",
        },
        {
            "command": "navigation.target.filter.hyperlinks",
            "keys": ["g", "h"],
            "action": "Show only visible hyperlinks",
        },
        {
            "command": "navigation.target.filter.folds",
            "keys": ["g", "f"],
            "action": "Show only visible folds",
        },
    ]
    target_help = goto.locator('tr[data-lf-command="navigation.target"]')
    expect(target_help.locator("kbd")).to_have_text(["g", "letters"])
    expect(target_help).to_contain_text("Type a visible target's hint")
    expect(target_help).not_to_contain_text("filter first")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page.keyboard.press("g")
    chips = page.locator(CHIPS)
    expect(chips.first).to_be_visible()
    initial_kinds = set(
        chips.evaluate_all("els => els.map(el => el.dataset.lfAddressKind)")
    )
    assert {"Link", "Fold", "Control"} <= initial_kinds, initial_kinds
    assert chips.evaluate_all(
        "els => els.every(el => el.textContent === el.dataset.lfAddress)"
    ), "an inline hint repeated the sequence context"

    mixed = page.locator(
        f'{CHIPS}[data-lf-address-kind="Margin control or status indicator"]'
        '[data-lf-address-for="opts-decision"]'
    )
    expect(mixed).to_have_count(2)
    mixed_codes = mixed.evaluate_all(
        "els => Object.fromEntries(els.map(el => "
        "[el.dataset.lfAddressMarginElement, el.dataset.lfAddress]))"
    )
    thread_code = mixed_codes["reading:threadList"]
    ask_key = next(key for key in mixed_codes if key != "reading:threadList")
    ask_code = mixed_codes[ask_key]

    page.keyboard.press("m")
    filtered = page.locator(CHIPS)
    expect(filtered).to_have_count(2)
    assert address_codes(page) == list(mixed_codes.values())
    page.keyboard.press("Escape")
    shortcut_bar_text(page)

    page.keyboard.press("t")
    expect(filtered).to_have_count(1)
    assert address_codes(page) == [thread_code]
    target_route = page.locator(
        '.lf-shortcut-bar .lf-key[data-lf-commands~="navigation.target"]'
    )
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => key.textContent)"
    ) == ["g", "t", "letters"]
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "pressed", "neutral"]
    expect(target_route).not_to_contain_text("filter")

    page.keyboard.type(thread_code)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    page.keyboard.press("Escape")

    page.keyboard.press("g")
    shortcut_bar_text(page)
    expect(page.locator("body")).to_have_attribute("data-lf-goto", "")
    assert (
        set(
            page.locator(CHIPS).evaluate_all(
                "els => els.map(el => el.dataset.lfAddressKind)"
            )
        )
        == initial_kinds
    )

    page.keyboard.press("a")
    expect(filtered).to_have_count(1)
    assert address_codes(page) == [ask_code]
    expect(page.locator(".lf-live")).to_have_text(
        "1 visible Ask controls; type a hint or press Tab to hear them."
    )
    page.keyboard.type(ask_code)
    expect(page.locator("#opts-decision")).to_be_focused()
    expect(page.locator("#opts-decision")).to_have_attribute("data-lf-ask", "1")

    # A filter with no members stays empty through the same resize refresh that
    # regenerates a populated map. Escape still restores the complete map.
    page.locator("#opt-a").click()
    round_trip(page)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="ask"]')).to_have_count(0)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("a")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(".lf-live")).to_have_text("No visible Ask controls.")
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    expect(page.locator("body")).to_have_attribute("data-lf-goto", "")
    expect(page.locator(".lf-live")).to_have_text(
        "No hint d. The current hints are unchanged."
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    resized(page, 1200, 800)
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS).first).to_be_visible()

    page.keyboard.press("h")
    links = page.locator(f'{CHIPS}[data-lf-address-kind="Link"]')
    expect(links).to_have_count(2)
    expect(page.locator(f'{CHIPS}:not([data-lf-address-kind="Link"])')).to_have_count(0)
    resized(page, 1180, 800)
    expect(links).to_have_count(2)
    expect(page.locator(f'{CHIPS}:not([data-lf-address-kind="Link"])')).to_have_count(0)
    page.keyboard.type(address_code(page, "Link", "lk2"))
    page.wait_for_url(re.compile(r"#p2$"))
    expect(page.locator("#p2")).to_be_focused()
    assert errors == []
    page.close()


def test_generated_hints_spread_without_hiding_a_crowded_target(browser, serve):
    """Crowded opaque routes are separated; none can be inferred if its face is dropped."""
    page, errors = open_page(browser, serve(CROWDED_PAGE))
    resized(page, 1280, 800)
    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_count(5)

    piles = page.evaluate(
        """() => {
             const boxes = [...document.querySelectorAll(
               '.lf-goto-targets > .lf-sequence-address[data-lf-address]')]
               .map(chip => ({
                 code: chip.dataset.lfAddress,
                 r: chip.getBoundingClientRect(),
               }));
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const found = [];
             for (let i = 0; i < boxes.length; i++)
               for (let j = i + 1; j < boxes.length; j++)
                 if (hit(boxes[i].r, boxes[j].r))
                   found.push(boxes[i].code + ' under ' + boxes[j].code);
             return {found, drawn: boxes.map(b => b.code)};
           }"""
    )
    assert piles["found"] == [], (
        f"addresses are drawn on top of each other: {piles['found']} "
        f"(drawn: {piles['drawn']})"
    )
    assert len(piles["drawn"]) == 5, piles
    page.keyboard.type(address_code(page, "Link", "fn1"))
    page.wait_for_url(re.compile(r"#s1$"))
    assert errors == []
    page.close()


def test_a_generated_hint_is_never_drawn_on_the_key_line(browser, serve):
    """The sequence's own legend remains clear while visible hints follow a scroll."""
    page, errors = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once. The line's whole band is reserved at the document's foot,
    # so the end of the page is exactly where this cannot happen; what puts a member in the
    # corner is an ordinary scroll position with a link resting on the bottom edge. Each
    # step waits for the runtime's own paint frame, since the chips follow a scroll on a
    # frame of their own and boxes read in the same turn are the positions it just left.
    fouled = page.evaluate(
        f"""async () => {{
             const line = () => document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const out = [];
             const room = document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight;
             for (let i = 0; i <= 20; i++) {{
               document.scrollingElement.scrollTo(0, Math.round((room * i) / 20));
               await ({RENDERED})();
               const bar = line();
               for (const chip of document.querySelectorAll(
                 '.lf-goto-targets > .lf-sequence-address[data-lf-address]'))
                 if (hit(chip.getBoundingClientRect(), bar))
                   out.push(chip.textContent + ' at ' + Math.round(document.scrollingElement.scrollTop));
             }}
             return out;
           }}"""
    )
    assert fouled == [], (
        f"addresses are drawn over the shortcut bar that explains them: {fouled}"
    )
    assert errors == []
    page.close()


def test_the_g_chord_reaches_named_surfaces_and_visible_targets(browser, serve):
    """Mnemonics reach global surfaces; generated hints reach the visible scene.

    Threads, Asks, Page map, and page edges keep stable named routes. margin controls and status indicators,
    tabs, links, folds, and the presses a widget built instead share one viewport-local
    letter namespace."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "passage under discussion"}, "Sharpen this.")
    comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    line = page.locator(".lf-shortcut-bar")

    # The page's own key is the letter alone: what it opens is a table, and a range on the
    # line here could only ever have counted one of the lists in it.
    expect(line).to_contain_text("go to")
    expect(line).not_to_contain_text("1–3")

    # Wide enough that the panel will stand beside the page rather than over it, which is
    # where a box in the fixed chrome and the page's flow part company: body is narrowed
    # as the layout shell, the panel is fixed and is not inside it, and a chip placed by
    # walking the page's clips came back with the whole reply box clipped away.
    resized(page, 1280, 800)

    # The complete reference and the armed line are two projections of the register. Keep
    # the command identities from the reference so the assertion below fails when a new
    # live continuation reaches dispatch and help but not the visible sequence menu.
    page.keyboard.press("?")
    page.keyboard.press("?")
    goto = page.locator(
        ".lf-shortcut-reference-section", has=page.get_by_role("heading", name="Go to")
    )
    reference_commands = set(
        goto.locator("tr[data-lf-command]").evaluate_all(
            "rows => rows.map(row => row.dataset.lfCommand)"
        )
    )
    assert reference_commands, "the page must contribute live Go to commands"
    overlaps = goto.locator("tr[data-lf-command]").evaluate_all(
        """rows => rows.flatMap(row => {
          const [key, action] = row.querySelectorAll(':scope > td');
          const amount = key.firstElementChild.getBoundingClientRect().right
            - action.getBoundingClientRect().left;
          return amount > 0.5 ? [{command: row.dataset.lfCommand, amount}] : [];
        })"""
    )
    assert overlaps == [], f"a complete route overlaps its action: {overlaps}"
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Armed, the line names the available global routes and visible-target map. Every destination
    # keeps its complete route, with the leader painted as already pressed.
    page.keyboard.press("g")
    shortcut_bar_text(page)
    visible_sequence = line.locator(".lf-key:not([hidden])")
    visible_commands = set(
        visible_sequence.evaluate_all(
            """hints => hints.flatMap(hint =>
              (hint.dataset.lfCommands || '').split(' ').filter(Boolean))"""
        )
    )
    assert visible_commands == reference_commands, (
        "the armed line and live Go to register diverged: "
        f"line={sorted(visible_commands)}, reference={sorted(reference_commands)}"
    )
    for command, steps, states, words in [
        (
            "navigation.panel.threads",
            ["g", "T"],
            ["pressed", "neutral"],
            "Threads panel",
        ),
        (
            "navigation.panel.asks",
            ["g", "A"],
            ["pressed", "neutral"],
            "Asks panel",
        ),
        (
            "navigation.page-map",
            ["g", "M"],
            ["pressed", "neutral"],
            "Page map",
        ),
        (
            "navigation.target",
            ["g", "letters"],
            ["pressed", "neutral"],
            "visible target",
        ),
        (
            "navigation.target.filter.threads",
            ["g", "kind"],
            ["pressed", "neutral"],
            "filter by kind",
        ),
        (
            "navigation.page.top",
            ["g", "g / G"],
            ["pressed", "neutral"],
            "top / bottom",
        ),
        (
            "navigation.address.back",
            ["esc"],
            ["neutral"],
            "cancel",
        ),
    ]:
        hint = line.locator(f'.lf-key:not([hidden])[data-lf-commands~="{command}"]')
        expect(hint).to_have_count(1)
        sequence = hint.locator(".lf-key-sequence")
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.textContent)"
            )
            == steps
        )
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.dataset.lfKeyState)"
            )
            == states
        )
        expect(sequence).to_have_attribute(
            "aria-label", " then ".join(step.replace(" / ", " or ") for step in steps)
        )
        expect(hint).to_contain_text(words)
    assert "navigation.panel.leaves" not in reference_commands

    # The visible More control and its registered `?` command are one route. An unmatched
    # key first disarms the sequence and keeps its ordinary meaning; a pointer press must enter
    # the same shelf rather than inspecting the still-armed stack and skipping to the full
    # reference.
    def disclosure_state():
        return page.evaluate(
            """() => ({
              help: document.querySelector('.lf-shortcut-reference').open,
              expanded: document.querySelector('.lf-shortcut-bar').dataset.lfExpanded,
              pressed: document.querySelectorAll(
                '.lf-shortcut-bar kbd[data-lf-key-state="pressed"]'
              ).length,
              commands: [...document.querySelectorAll('.lf-shortcut-bar .lf-key:not([hidden])')]
                .flatMap(hint => (hint.dataset.lfCommands || '').split(' ').filter(Boolean)),
            })"""
        )

    page.get_by_role("button", name="? more", exact=True).click()
    page.evaluate(RENDERED)
    pointer_disclosure = disclosure_state()
    page.reload()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    resized(page, 1280, 800)
    page.keyboard.press("g")
    page.keyboard.press("?")
    page.evaluate(RENDERED)
    key_disclosure = disclosure_state()
    assert pointer_disclosure == key_disclosure, (
        "the visible More control and its ? binding diverged: "
        f"pointer={pointer_disclosure}, key={key_disclosure}"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("g")

    for width in (1280, 420):
        resized(page, width, 800)
        page.wait_for_function(
            """() => {
              const line = document.querySelector('.lf-shortcut-bar');
              const chrome = document.querySelector('.lf-chrome');
              return parseFloat(chrome.style.paddingBottom) >= line.offsetHeight + 19;
            }"""
        )
        geometry = line.evaluate(
            """node => {
              const visible = [...node.children].filter(el => el.checkVisibility());
              const tops = [];
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              for (const el of visible)
                if (tops.every(top => Math.abs(top - el.offsetTop) > tolerance))
                  tops.push(el.offsetTop);
              const box = node.getBoundingClientRect();
              return {
                rows: tops.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                left: box.left,
                right: box.right,
                viewport: innerWidth,
                height: box.height,
              };
            }"""
        )
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["left"] >= 0 and geometry["right"] <= geometry["viewport"], (
            geometry
        )
        assert geometry["rows"] <= (2 if width == 1280 else 4), geometry
        assert geometry["height"] <= 800 * 0.2, geometry
    resized(page, 1280, 800)
    expect(page.locator(CHIPS).first).to_be_visible()
    # The chips are the eye's copy of a mode; a reader who cannot see them is told the
    # window opened and what it holds, off the same rows the line just drew.
    expect(page.locator(".lf-live")).to_contain_text("visible targets")
    expect(page.locator(".lf-live")).to_contain_text("type a hint")
    expect(page.locator(".lf-live")).to_contain_text("Shift+t Threads panel")

    # A panel mnemonic completes the sequence and leaves the reader inside that panel, where
    # its own scoped keys are immediately available.
    expect(page.locator(".lf-panel")).not_to_be_visible()
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")

    # The Asks sequence follows the same contract: show the panel and land on its first row.
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    expect(page.locator(".lf-asks-row").first).to_be_focused()
    # A row is the reader standing at the ask it names, so the banner's count says
    # which of how many from the tray as it does from the page.
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    expect(page.locator(CHIPS)).to_have_count(0)

    # A direct destination also remembers the workspace it displaced. Threads replaces
    # Asks while it stands; one Escape restores both that tray and its exact focused row.
    ask = page.locator(".lf-asks-row").first
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-asks-panel")).not_to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_be_visible()
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    expect(ask).to_be_focused()

    # Page map has its own close step, but that does not waive the same workspace
    # contract: leaving it restores the Asks row it stood over. Its door is the one that
    # can forget, because a dialog delivers `close` in a task of its own — a frame after
    # the dispatcher has already put the reader back — so the door's own return route has
    # to stand down for the press that is unwinding it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page map"
        )
    ).to_be_focused()
    page.evaluate(
        """() => {
          window.__lfPageMapClosed = false;
          document.querySelector('dialog.lf-page-map-sheet').addEventListener(
            'close',
            () => { window.__lfPageMapClosed = true; },
            {once: true},
          );
        }"""
    )
    page.keyboard.press("Escape")
    page.wait_for_function("() => window.__lfPageMapClosed")
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    expect(ask).to_be_focused()

    page.keyboard.press("?")
    page.keyboard.press("?")
    asks_help = page.locator(".lf-shortcut-reference-section").filter(
        has=page.get_by_role("heading", name="In the Asks tray", exact=True)
    )
    expect(asks_help.get_by_text("Previous ask", exact=True)).to_have_count(1)
    expect(asks_help.get_by_text("Next ask", exact=True)).to_have_count(1)
    expect(asks_help).not_to_contain_text(re.compile(r"decision", re.IGNORECASE))
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-asks-panel")).not_to_be_visible()

    # Uppercase M opens the complete Page map rather than the numbered prefix.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-group")).to_have_count(3)
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page map"
        )
    ).to_be_focused()
    page.keyboard.press("Escape")

    # A visible Margin control or status indicator shares the generated target map. Activating the hint
    # opens the same thread preview as its marker.
    go_to_address(page, "Margin control or status indicator", "p1")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread textarea").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("Escape")

    # The hyperlinks, from the head of the page where both are on screen. A hint is centred on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # route's visible start rather than on the inline's wide union box.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-address-kind="Link"]')).to_have_count(2)
    assert page.evaluate(
        """() => {
             const links = [...document.querySelectorAll('#refs a[href]')];
             const chips = links.map(link => document.querySelector(
               `.lf-goto-targets > .lf-sequence-address[data-lf-address-for="${link.id}"]`));
             return {wrapped: links[0].getClientRects().length > 1,
                     on: chips.map((chip, i) => {
                       const c = chip.getBoundingClientRect();
                       const first = links[i].getClientRects()[0];
                       return Math.abs(c.left + c.width / 2 - first.left) < 2
                           && Math.abs(c.top + c.height / 2 - first.top) < 2;
                     })};
           }"""
    ) == {
        "wrapped": True,
        "on": [True, True],
    }, "a chip is not on the corner its link starts at"
    page.keyboard.press("Escape")

    # At the foot of the page neither hyperlink is visible, so neither receives a route.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-address-kind="Link"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # Resolved is panel chrome rather than an authored fold. Read of the document at
    # large, `f` must not offer a digit for the panel's own state selector.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(page.locator("details.lf-details")).to_have_count(0)
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-address-kind="Fold"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # The folds, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the reader
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    fold_code = address_code(page, "Fold", "dsc-head")
    assert page.evaluate(
        """() => {
             const c = document.querySelector(
               '.lf-goto-targets > .lf-sequence-address[data-lf-address-for="dsc-head"]')
                        .getBoundingClientRect();
             const first = document.getElementById('dsc-head').getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.top + c.height / 2 - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary starts at"
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.type(fold_code)
    expect(page.locator("#dsc-head")).to_be_focused()
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # Standing there, the line says which way the next press goes and names every key that
    # goes that way: Space as well as Enter, where a link takes Enter alone and Space under
    # one is the page's own scroll, and the one arrow with somewhere to go. Both cells are
    # read where they are painted — a word fixed at declaration could say only one of the
    # two directions, and a binding set fixed there would name an arrow that does nothing.
    # What the arrows do is the test below this one; here they are what the line offers.
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"
    expect(line).to_contain_text(re.compile(opened + r"\s*close"))
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    # Read once rather than waited for. Opening a disclosure is the one change in what the
    # next press does that no writer in the runtime reports, so the word stood at "close"
    # until a poll came past — and an assertion that retries reads a stale line as an
    # eventually right one, going green on whichever poll happens to land inside its
    # budget. The attribute watch has answered by the time the press returns or nothing
    # has.
    said = shortcut_bar_text(page)
    assert re.search(shut + r"\s*open", said), said
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")
    said = shortcut_bar_text(page)
    assert re.search(opened + r"\s*close", said), said

    # A press a widget built joins the same namespace, declared by the constructor that
    # made it rather than by an entry here. A pick spends no page letter of its own — the
    # register holds capabilities, and a control is a route to one — so before this the
    # only keyboard way to it was Tab. The arrival is the press, so the option is chosen.
    page.evaluate(
        """() => document.scrollingElement.scrollTo(
             0, document.getElementById('opts-decision').offsetTop - 80)"""
    )
    page.keyboard.press("g")
    controls = page.locator(f'{CHIPS}[data-lf-address-kind="Control"]')
    expect(controls).not_to_have_count(0)
    pick_code = page.evaluate(
        """() => {
             const mark = document.querySelector('#opt-a .lf-pick').getBoundingClientRect();
             const chip = [...document.querySelectorAll(
               '.lf-goto-targets > .lf-sequence-address[data-lf-address-kind="Control"]')]
               .find(c => {
                 const r = c.getBoundingClientRect();
                 return Math.abs(r.left + r.width / 2 - mark.left) < 2
                     && Math.abs(r.top + r.height / 2 - mark.top) < 2;
               });
             return chip ? chip.dataset.lfAddress : null;
           }"""
    )
    assert pick_code, "the pick mark the widget built got no address"
    page.keyboard.type(pick_code)
    expect(page.locator("#opt-a")).to_have_attribute("chosen", "")

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key completes the route — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    expect(line).to_contain_text("top / bottom")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.scrollingElement.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.scrollingElement.scrollTop === 0")

    # A panel mnemonic completes the sequence directly wherever the reader is on the page.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Typing contexts are untouched: in a box, the whole sequence is text.
    page.keyboard.press("t")
    page.keyboard.press("Enter")
    ta1 = page.locator(f'.lf-thread[data-id="{c1}"] textarea')
    expect(ta1).to_be_focused()
    page.keyboard.type("gc1")
    expect(ta1).to_have_value("gc1")
    expect(ta1).to_be_focused()
    assert errors == []
    page.close()


def test_the_g_chord_reaches_the_all_leaves_panel(browser, serve, live_leaf):
    """All leaves is the third panel destination and follows the same focus contract."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(ADDRESSED_PAGE))

    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("All leaves panel")
    leaves_hint = page.locator(
        '.lf-goto-targets > [data-lf-address-command="navigation.panel.leaves"]'
    )
    expect(leaves_hint).to_have_attribute("data-lf-address-sequence", "g L")
    assert leaves_hint.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
    ) == [["g", "pressed"], ["L", "neutral"]]
    # A live control label may change while the sequence stands. The detached overlay is
    # owned by the address layer, so a routine poll cannot erase it.
    live_leaf("third", "A third leaf")
    round_trip(page)
    expect(page.locator(".lf-others")).to_contain_text("All leaves (3)")
    assert leaves_hint.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
    ) == [["g", "pressed"], ["L", "neutral"]]
    page.keyboard.press("Shift+l")

    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    assert errors == []
    page.close()


def test_clamped_leaf_lists_share_the_walk_position(browser, serve, live_leaf):
    """Leaf-owned lists use one ordinal and one boundary face."""
    live_leaf("second", "A second leaf")
    live_leaf("third", "A third leaf")
    page, errors = open_page(browser, serve(ASKS_PAGE))
    position = page.locator(".lf-walk-position")

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text("Leaf 2 of 2")
    leaves_boxes = page.evaluate(
        """() => {
          const tray = document.querySelector('.lf-others-panel').getBoundingClientRect();
          const position = document.querySelector('.lf-walk-position')
            .getBoundingClientRect();
          return {trayRight: tray.right, positionLeft: position.left};
        }"""
    )
    assert leaves_boxes["positionLeft"] >= leaves_boxes["trayRight"] + 18, leaves_boxes
    page.keyboard.press("ArrowDown")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    asks = page.locator("button.lf-asks-row")
    expect(asks.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text(f"Ask 2 of {asks.count()}")
    page.keyboard.press("ArrowUp")
    expect(position).to_have_text(f"Ask 1 of {asks.count()}")
    page.keyboard.press("ArrowUp")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Escape")
    markers = page.locator(".lf-margin-marker:visible")
    assert markers.count() > 1
    markers.first.focus()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text(re.compile(r"^Marker 2 of \d+$"))

    assert errors == []
    page.close()


def test_a_g_panel_destination_survives_a_completed_asks_tray(browser, serve):
    """An open panel remains reachable after working its last row completes it."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
            )
        ),
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-asks-row")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#only-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("button.lf-asks-row")).to_have_count(1)
    expect(page.locator(".lf-asks-answer")).to_have_text("First")
    expect(page.locator(".lf-asks-panel")).to_have_class(re.compile(r"\bopen\b"))

    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Asks panel")
    page.keyboard.press("Shift+a")
    expect(page.locator(".lf-asks-row")).to_be_focused()
    assert errors == []
    page.close()


# What the shortcut bar is saying, chip by chip. The word is the chip's own trailing span —
# `keySequence` builds the keycaps into a classed element and the word is the unclassed
# one beside it — and the commands are what the row projects, so a duplicate can be
# reported as the pair of rows that made it rather than as a word said twice.
KEY_LINE_HINTS = """() => [...document.querySelectorAll('.lf-shortcut-bar .lf-key')]
  .filter(chip => !chip.hidden)
  .map(chip => ({
    commands: chip.dataset.lfCommands,
    word: [...chip.children].filter(c => !c.className).map(c => c.textContent).join(''),
  }))"""


def test_no_two_hints_on_the_key_line_say_the_same_word(browser, serve):
    """The line is a row of words with keycaps over them, and the word is what is read.

    Two rows sharing one leaves the keycaps to carry the whole difference, which is the
    line failing at the one thing it is for. The versions menu once called both Tab
    directions "leave versions"; a keyboard-opened menu now has its precise Escape return
    beside the remaining directional handoff. The page's `c` says "comment on the page",
    distinct from the t/T thread walk.

    Both scenes are read, and each is asserted to hold the rows at issue first: a line
    that had stopped showing them would report a clean result about a page the reader
    never sees. The words are the register's, which is where the fix goes — the line
    prints what the rows say, and inventing a difference here would be this projection
    disagreeing with the reference and the announcements.
    """
    url = serve(LONG_PAGE, comments=2)
    _publish(serve.page_dir, 2, LONG_PAGE, "two")
    page, errors = open_page(browser, url)

    # The shelf, because the ordinary shortlist shows the first live row and little else:
    # what this is about is two words a reader can see at one time, and the shelf is where
    # the page's own scene is all of it.
    page.keyboard.press("?")
    page.evaluate(RENDERED)
    standing = page.evaluate(KEY_LINE_HINTS)
    assert {"comment.create", "thread.next thread.previous"} <= {
        hint["commands"] for hint in standing
    }, f"the line no longer offers both the comments and the thread walk: {standing}"

    # The registered return frame is nearer than the menu's native Tab handoffs, so the
    # shortlist contains the actual Escape return and the version walk.
    page.keyboard.press("Escape")
    open_versions(page)
    page.evaluate(RENDERED)
    versions = page.evaluate(KEY_LINE_HINTS)
    assert {"navigation.return", "version.previous version.next"} <= {
        hint["commands"] for hint in versions
    }, f"the versions menu no longer offers its two visible ways out: {versions}"

    for scene, hints in (("the page", standing), ("the versions menu", versions)):
        said = {}
        for hint in hints:
            said.setdefault(hint["word"], []).append(hint["commands"])
        twice = {word: rows for word, rows in said.items() if len(rows) > 1}
        assert not twice, (
            f"on {scene} the shortcut bar says one word for two capabilities, so the "
            f"keycaps are the whole difference: {twice}"
        )
    assert errors == []
    page.close()


def test_a_completed_asks_tray_keeps_the_answer_visible(browser, serve):
    """Finishing a page preserves the tray's route back through the answer."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
            )
        ),
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-asks-row")).to_have_count(1)
    # Enter travels to the ask and Tab steps onto a mark, whose digit answers it. Tab
    # rather than the digit straight off the arrival, because where an arrival lands is
    # not this test's subject and it should not go red when that moves.
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("button.lf-asks-row")).to_have_count(1)
    expect(page.locator(".lf-asks-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-asks-answer")).to_have_text("First")
    assert errors == []
    page.close()


def test_an_asks_tray_says_when_a_revision_removes_its_last_ask(browser, serve):
    """An empty inventory says the tray rendered, rather than looking broken."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
        '<lf-options id="only" choose>'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
    )
    url = serve(source)
    page, errors = open_page(browser, live_url(url))
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-asks-row")).to_have_count(1)
    note = page.locator(".lf-asks-panel .lf-empty")
    expect(note).to_have_count(0)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last ask",
    )
    wait_for_revision(page, 2)
    expect(page.locator("button.lf-asks-row")).to_have_count(0)
    expect(page.locator(".lf-asks-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(note).to_be_visible()
    expect(note).to_contain_text("Nothing is waiting on you")
    assert errors == []
    page.close()


def test_the_g_chord_opens_an_empty_page_map(browser, serve):
    """A destination with no locations still shows that the command worked."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Empty page map", "<h1>Empty page map</h1><p>No activity yet.</p>"
            )
        ),
    )

    expect(page.locator(".lf-page-map-action")).to_have_count(0)
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Page map")
    page.keyboard.press("Shift+m")

    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page map"
        )
    ).to_be_focused()
    expect(sheet).to_contain_text(
        "No margin controls, status indicators, or locations yet"
    )
    expect(sheet.locator(".lf-page-map-action")).to_have_count(0)
    assert errors == []
    page.close()


def test_generated_hints_refresh_to_the_visible_scene_after_scroll(browser, serve):
    """Scroll changes the map at rest without letting an old letter act elsewhere."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Scrolling hints",
                """
<h1 id="top">Scrolling hints</h1>
<p><a id="top-link-one" href="#top">First top destination</a></p>
<p><a id="top-link-two" href="#top">Second top destination</a></p>
<p><a id="top-link-three" href="#top">Third top destination</a></p>
<div style="height: 1600px" aria-hidden="true"></div>
<p><a id="bottom-link" href="#bottom">Bottom destination</a></p>
<h2 id="bottom">Bottom</h2>
<div style="height: 1200px" aria-hidden="true"></div>
""",
            )
        ),
    )

    page.keyboard.press("g")
    old_code = address_code(page, "Link", "top-link-two")
    assert old_code == "d"
    expect(page.locator(f'{CHIPS}[data-lf-address-for="bottom-link"]')).to_have_count(0)
    page.keyboard.press("Tab")
    expect(page.locator(f'{CHIPS}[data-lf-address-for="top-link-one"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    page.evaluate(
        "() => document.querySelector('#bottom-link').scrollIntoView({block: 'start'})"
    )
    expect(page.locator(f'{CHIPS}[data-lf-address-for="bottom-link"]')).to_have_count(1)
    expect(page.locator(f'{CHIPS}[data-lf-address-for="top-link-one"]')).to_have_count(
        0
    )
    expect(page.locator(f"{CHIPS}.lf-current")).to_have_count(0)

    # `d` named the third link in the old scene. It is also the page-down command, so
    # letting it fall through after the remap would move the page with no visible reason.
    # The armed hint alphabet owns the miss and leaves the current map intact.
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press(old_code)
    expect(page.locator(".lf-live")).to_have_text(
        f"No hint {old_code}. The current hints are unchanged."
    )
    expect(page.locator(f'{CHIPS}[data-lf-address-for="bottom-link"]')).to_have_count(1)
    page_at_rest(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    bottom_code = address_code(page, "Link", "bottom-link")
    page.keyboard.type(bottom_code)
    page.wait_for_url(re.compile(r"#bottom$"))
    expect(page.locator("#bottom")).to_be_focused()
    assert errors == []
    page.close()


def test_inflight_native_paging_hides_hints_until_the_scene_settles(browser, serve):
    """A reader can arm the spatial map immediately after a page-down press."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Map after travel",
                '<h1>Map after travel</h1><p><a id="near" href="#arrival">Near</a></p>'
                '<div style="height: 600px" aria-hidden="true"></div>'
                '<p><a id="middle" href="#arrival">Middle</a></p>'
                '<div style="height: 1200px" aria-hidden="true"></div>'
                '<h2 id="arrival">Arrival</h2>',
            )
        ),
    )

    page.keyboard.press("PageDown")
    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(CHIPS)).to_have_count(1)
    codes = address_codes(page)
    mapped_at = page.evaluate("() => document.scrollingElement.scrollTop")
    page_at_rest(page)

    assert page.evaluate("() => document.scrollingElement.scrollTop") == mapped_at
    assert address_codes(page) == codes
    expect(page.locator(CHIPS)).to_have_count(1)
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_only_controls_and_boxes_with_something_out_of_sight_take_a_tab_stop(
    browser, serve
):
    """Anything a mouse can scroll a keyboard has to reach, and the reference is a list
    long enough to scroll — but its rows carry no control, so nothing put the reader in it
    and they could read the first screenful of the key reference and no more.

    The sweep that fixes that asks the box whether it may scroll, and the theme says every
    table may (`table { display: block; overflow-x: auto }`). So pointing it at the
    reference tagged all fourteen of its tables, none of which overflows: leaving the
    reference by Tab went from its native controls to fifteen extra stops, each wearing
    the browser's own ring rather than the layer's. A rule saying a box *could* scroll is
    not the same fact as a box that *has* something out of sight, and only the second is
    somewhere a reader needs to be able to stand.

    Asserted as the whole set rather than a count, because the count was right before and
    the members were wrong: every stop in the overlay has to be a control the reference
    offers or a box that really scrolls."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).to_be_visible()

    stops = page.evaluate(
        """() => [...document.querySelector('.lf-shortcut-reference').querySelectorAll('*')]
                 .filter(e => e.tabIndex >= 0)
                 .map(e => ({
                    tag: e.tagName,
                    scrolls: e.scrollWidth > e.clientWidth
                          || e.scrollHeight > e.clientHeight,
                 }))"""
    )
    assert stops, "the reference offers no tab stop at all, not even its search box"
    controls = {"BUTTON", "INPUT"}
    dead = [s for s in stops if s["tag"] not in controls and not s["scrolls"]]
    assert dead == [], f"tab stops on boxes with nothing out of sight: {dead}"
    assert [s["tag"] for s in stops if s["tag"] in controls] == [
        "BUTTON",
        "INPUT",
        "BUTTON",
    ]

    # And the box that does have something out of sight is one of those stops, which is
    # the whole point of the sweep. Its reachability is what is asserted here and not the
    # scroll itself: the headless shell does not move a focused div for an arrow or a
    # PageDown where Chrome does, so a motion assertion would be measuring the harness.
    # What this can say, and what the defect was, is that the box overflows and that a
    # reader can be put on it.
    results = page.locator(".lf-shortcut-reference-results")
    assert page.evaluate(
        "() => { const r = document.querySelector('.lf-shortcut-reference-results');"
        "        return r.scrollHeight > r.clientHeight; }"
    ), (
        "this reference fits its box, so it proves nothing about reaching one that does not"
    )
    results.focus()
    expect(results).to_be_focused()
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_keeps_its_complete_keyboard_layer(browser, serve):
    """The reference has a visible close control and keeps Tab inside the surface.

    It claims the keyboard while open, so letting native Tab fall through to the page
    behind it makes the visible scope and the focus scope disagree. Forward and reverse
    Tab use the same registered walk, while Escape closes and restores the opener."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    opener = page.get_by_role("button", name="? more", exact=True)
    opener.click()
    opener = page.get_by_role("button", name="? all shortcuts", exact=True)
    opener.click()
    help_el = page.locator(".lf-shortcut-reference")
    close = page.get_by_role("button", name="Back to more shortcuts")
    expect(close).to_be_visible()
    for command in [
        "response.reaction.choose",
        "response.tab",
        "response.move",
        "response.activate",
        "response.close",
    ]:
        expect(
            help_el.locator(
                f'.lf-shortcut-reference-command[data-lf-command="{command}"]'
            )
        ).to_have_count(1)

    seen = set()
    for _ in range(6):
        page.keyboard.press("Tab")
        active = page.evaluate(
            """() => {
              const e = document.activeElement;
              return {inside: document.querySelector('.lf-shortcut-reference').contains(e),
                      name: e.getAttribute('aria-label') || e.className || e.tagName};
            }"""
        )
        assert active["inside"], f"Tab left the keyboard reference for {active['name']}"
        seen.add(active["name"])
    assert "Back to more shortcuts" in seen, seen

    page.keyboard.press("Shift+Tab")
    assert page.evaluate(
        "() => document.querySelector('.lf-shortcut-reference').contains(document.activeElement)"
    )
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()

    # The native modal makes the page behind it inert. Its reachable light-dismiss gesture
    # is the backdrop, which closes the reference and returns to the door rather than
    # pretending a page control can be pressed through the modal layer.
    opener.click()
    page.mouse.click(2, 2)
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()
    assert errors == []
    page.close()


def test_the_reference_runs_available_commands_and_explains_the_rest(browser, serve):
    """The reference is the command register made usable, not a second list of prose.

    Search narrows that register, arrows choose a result, and Enter runs it through the
    same scoped command route as its key. A command outside the reader's current scope
    stays selectable, but explains the scope it needs instead of closing and doing
    nothing. Stable command IDs are exposed on the results so words can change without
    breaking this route or tooling built on it."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    help_el = page.locator(".lf-shortcut-reference")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")

    page.keyboard.press("?")
    page.keyboard.press("?")
    commands = help_el.locator(".lf-shortcut-reference-command:visible")
    assert commands.count() > 1, "the command grid has no pair of rows to walk"
    # The head's hint and the rows share their verbs: "choose" and "run" here, and on
    # the expanded shortcut bar as "choose next" and "run", one register for one press.
    expect(help_el.locator(".lf-shortcut-reference-meta")).to_have_text(
        re.compile(r"^\d+ commands · ↑↓ choose · ⏎ run$")
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(commands.first).to_have_attribute("data-lf-selected", "true")
    expect(help_el.locator(".lf-shortcut-reference-meta")).to_have_text(
        re.compile(r" · ⏎ run$")
    )
    first_row = commands.first.locator("xpath=ancestor::tr")
    expect(search).to_have_attribute(
        "aria-activedescendant", first_row.get_attribute("id")
    )
    page.keyboard.press("ArrowUp")
    expect(commands.first).to_have_attribute("data-lf-selected", "true")

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    commands = help_el.locator(".lf-shortcut-reference-command:visible")
    page.keyboard.press("ArrowUp")
    expect(search).to_be_focused()
    expect(commands.last).to_have_attribute("data-lf-selected", "true")
    last_row = commands.last.locator("xpath=ancestor::tr")
    expect(search).to_have_attribute(
        "aria-activedescendant", last_row.get_attribute("id")
    )
    page.keyboard.press("ArrowDown")
    expect(commands.last).to_have_attribute("data-lf-selected", "true")

    # On a phone, every complete binding stays in its own key column. Search adds a
    # scope to each match; that context takes a second line rather than squeezing the
    # action down to one word or painting over it.
    resized(page, 390, 800)
    geometry = help_el.evaluate(
        """help => ({
          tables: [...help.querySelectorAll('table')].filter(table => table.offsetWidth)
            .map(table => ({client: table.clientWidth, scroll: table.scrollWidth})),
          keys: [...help.querySelectorAll('tr:not([hidden]) .lf-key-sequence')]
            .map(key => ({
              top: key.getBoundingClientRect().top,
              right: key.getBoundingClientRect().right,
              actionTop: key.closest('tr').querySelector('.lf-shortcut-reference-action')
                .getBoundingClientRect().top,
              cellRight: key.closest('td').getBoundingClientRect().right,
            })),
        })"""
    )
    assert all(table["scroll"] <= table["client"] for table in geometry["tables"]), (
        geometry
    )
    assert all(key["right"] <= key["cellRight"] for key in geometry["keys"]), geometry
    assert all(abs(key["top"] - key["actionTop"]) <= 3 for key in geometry["keys"]), (
        geometry
    )
    search.fill("space")
    matches = help_el.locator(
        ".lf-shortcut-reference-binding-matches tr[data-lf-command]:visible"
    ).evaluate_all(
        """rows => rows.map(row => {
          const cell = row.cells[1].getBoundingClientRect();
          const scope = row.querySelector('.lf-shortcut-reference-scope').getBoundingClientRect();
          const key = row.querySelector('.lf-key-sequence').getBoundingClientRect();
          return {cellLeft: cell.left, scopeLeft: scope.left,
                  keyTop: key.top,
                  actionTop: row.querySelector('.lf-shortcut-reference-action')
                    .getBoundingClientRect().top,
                  keyRight: key.right,
                  keyCellRight: row.cells[0].getBoundingClientRect().right};
        })"""
    )
    assert matches
    assert all(item["keyRight"] <= item["keyCellRight"] for item in matches), matches
    assert all(abs(item["keyTop"] - item["actionTop"]) <= 3 for item in matches), (
        matches
    )
    assert all(
        item["scopeLeft"] == pytest.approx(item["cellLeft"], abs=0.5)
        for item in matches
    ), matches
    resized(page, 1200, 800)

    # A key query may also occur in command ids and prose. Actual bindings lead the
    # filtered DOM, which is both the visual order and the Arrow-key command rail. A
    # trailing separator asks for continuations, and case puts the shifted face first.
    search.fill("g ")
    ranked = help_el.locator("tr[data-lf-command]:visible").evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          binding: [...row.querySelectorAll('kbd')].map(key => key.textContent).join(' '),
        }))"""
    )
    assert ranked and ranked[0]["binding"].startswith("g "), ranked
    first_other = next(
        (
            index
            for index, row in enumerate(ranked)
            if not row["binding"].startswith("g ")
        ),
        len(ranked),
    )
    assert first_other > 0, ranked
    assert not any(row["binding"].startswith("g ") for row in ranked[first_other:]), (
        ranked
    )
    search.fill("g t")
    assert (
        help_el.locator("tr[data-lf-command]:visible").first.get_attribute(
            "data-lf-command"
        )
        == "navigation.target.filter.threads"
    )
    search.fill("g T")
    assert (
        help_el.locator("tr[data-lf-command]:visible").first.get_attribute(
            "data-lf-command"
        )
        == "navigation.panel.threads"
    )
    page.keyboard.press("ArrowDown")
    expect(
        help_el.locator(
            '.lf-shortcut-reference-command[data-lf-command="navigation.panel.threads"]'
        )
    ).to_have_attribute("data-lf-selected", "true")
    search.fill("Tab")
    tab_matches = help_el.locator(
        ".lf-shortcut-reference-binding-matches tr[data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "reference.focus.walk" in tab_matches, tab_matches
    search.fill("w")
    w_results = help_el.locator("tr[data-lf-command]:visible").evaluate_all(
        "rows => rows.map(row => row.dataset.lfCommand)"
    )
    assert w_results.index("drawing.leave") < w_results.index("page.down"), w_results
    w_matches = help_el.locator(
        ".lf-shortcut-reference-binding-matches tr[data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "drawing.leave" in w_matches, w_matches
    assert "thread.waiting.toggle" in w_matches, w_matches
    assert w_results.index("page.down") >= len(w_matches), w_results

    search.fill("resolve it")
    result = help_el.locator(
        '.lf-shortcut-reference-command[data-lf-command="thread.resolve"]'
    )
    expect(result).to_have_count(1)
    expect(result).to_have_attribute("data-lf-command", "thread.resolve")
    expect(search).to_have_attribute("aria-haspopup", "grid")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result.locator("xpath=ancestor::tr")).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.type("!")
    expect(search).to_have_value("resolve it!")
    expect(help_el.locator(".lf-shortcut-reference-empty")).to_be_visible()
    page.keyboard.press("Backspace")
    page.keyboard.press("ArrowDown")
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_visible()
    expect(help_el.locator(".lf-shortcut-reference-meta")).to_have_text(
        "Available on a thread's Resolve button"
    )
    search.fill("close response choices")
    cancel_reaction = help_el.locator(
        '.lf-shortcut-reference-command[data-lf-command="reaction.cancel"]'
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(cancel_reaction).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el.locator(".lf-shortcut-reference-meta")).to_have_text(
        "Available with reactions open"
    )

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    search.fill("previous open thread")
    previous = help_el.locator(
        '.lf-shortcut-reference-command[data-lf-command="thread.previous"]'
    )
    expect(previous).to_have_count(1)
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(previous).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    thread = page.locator(".lf-thread").last
    expect(thread).to_be_focused()
    thread.get_by_role("button", name="Resolve thread", exact=True).focus()
    page.keyboard.press("?")
    page.keyboard.press("?")
    search.fill("resolve it")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_hidden()
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    assert errors == []
    page.close()


def test_the_reference_runs_the_exact_numbered_ask_action(browser, serve):
    """Each Ask digit is a distinct command when invoked without a keydown."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    page.keyboard.press("a")
    page.keyboard.press("?")
    page.keyboard.press("?")

    first = page.locator(
        '.lf-shortcut-reference-command[data-lf-command="option.choose-1"]'
    )
    second = page.locator(
        '.lf-shortcut-reference-command[data-lf-command="option.choose-2"]'
    )
    expect(first).to_have_text("Activate the “Keep the store” action")
    expect(second).to_have_text("Activate the “Signed tokens” action")
    expect(
        page.locator(
            '.lf-shortcut-reference-command[data-lf-command="ask.activate-nth"]'
        )
    ).to_have_count(0)

    second.click()
    expect(page.locator("#lq-token")).to_have_attribute("chosen", "")
    expect(page.locator("#lq-keep")).not_to_have_attribute("chosen", "")
    round_trip(page)

    assert errors == []
    page.close()


def test_numbered_ask_routes_follow_replaced_controls(browser, serve):
    """A widget can replace its action controls without defining another keymap."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "draft ask",
                """
<h1 id="h">Release note</h1>
<lf-ask id="note-decision"><h2>How should the note read?</h2>
  <lf-draft id="note" needed><pre>Keep this text editable.</pre></lf-draft>
</lf-ask>
""",
            )
        ),
    )

    page.keyboard.press("a")
    expect(page.locator("#note-decision")).to_be_focused()
    assert "1\nEdit" in shortcut_bar_text(page)

    page.keyboard.press("?")
    page.keyboard.press("?")
    edit = page.locator('.lf-shortcut-reference-command[data-lf-command="draft.edit"]')
    expect(edit).to_have_text("Activate the “Edit…” action")
    edit.click()
    expect(page.locator("#note textarea")).to_be_focused()

    save = page.locator(".lf-draft-controls [data-lf-margin-element-key='save']")
    save.focus()
    expect(save).to_be_focused()
    page.keyboard.press("?")
    assert re.search(r"(⌘⏎|Ctrl\+⏎) / 1\nSave / Cancel", shortcut_bar_text(page))
    expect(save).to_have_attribute("aria-keyshortcuts", "Meta+Enter Control+Enter")
    page.keyboard.press("?")
    cancel = page.locator(
        '.lf-shortcut-reference-command[data-lf-command="draft.cancel"]'
    )
    expect(cancel).to_have_text("Activate the “Cancel” action")
    cancel.click()
    expect(page.locator("#note textarea")).to_have_count(0)

    assert errors == []
    page.close()


def test_registered_shortcuts_are_exposed_to_assistive_technology(browser, serve):
    """The same declarations that paint help expose their active keys through ARIA."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-keyshortcuts", "?"
    )
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter"
    )
    expect(page.locator("#live-question .lf-another textarea")).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter"
    )
    assert page.locator(".lf-version-menu").get_attribute("aria-keyshortcuts") is None

    page.keyboard.press("a")
    mark = page.locator("#live-question .lf-pick").first
    expect(mark).to_have_attribute("aria-keyshortcuts", "ArrowUp ArrowDown Space 1")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(mark).to_have_attribute("aria-keyshortcuts", "ArrowUp ArrowDown Space")
    expect(
        page.locator(
            ".lf-shortcut-reference tr",
            has_text="Next ask this page is waiting on you for",
        ).locator("kbd")
    ).to_have_text("a")
    expect(
        page.locator(
            ".lf-shortcut-reference tr",
            has_text="Previous ask this page is waiting on you for",
        ).locator("kbd")
    ).to_have_text("A")
    page.keyboard.press("Escape")

    assert page.locator(".lf-asks").get_attribute("aria-keyshortcuts") is None
    page.locator(".lf-asks").click()
    expect(page.locator(".lf-asks-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown"
    )
    expect(page.locator(".lf-asks-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter Space"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_reads_the_same_way_twice(browser, serve):
    """A widget registers its scope at upgrade, and the set the reference walks is
    insertion-ordered, so the sections came out in whatever order the modules happened to
    finish in. The same build read twice put "On a tab" above "On a card grip" once and
    below it the next time. A reference whose headings move between loads is one a reader
    cannot learn the shape of, and any assertion on it flakes rather than fails — which is
    how it was found, a reviewer taking a reordering for fallout from an unrelated change.

    So the widgets' sections read in the order the page holds them. Asserted twice over:
    the same page loaded twice gives the same list, and that list is the document's own
    order rather than any order at all — a stable-but-wrong order would pass the first
    check alone."""
    url = serve(CONTROL_LABEL_PAGE)
    seen = []
    for _ in range(2):
        page, errors = open_page(browser, url)
        page.keyboard.press("?")
        page.keyboard.press("?")
        expect(page.locator(".lf-shortcut-reference")).to_be_visible()
        seen.append(
            page.evaluate(
                "() => [...document.querySelectorAll('.lf-shortcut-reference h3')].map(h => h.textContent)"
            )
        )
        assert errors == []
        page.close()

    assert seen[0] == seen[1], f"the reference reordered between loads: {seen}"
    assert "On a tab" in seen[0], seen[0]


def test_a_widget_that_renames_its_role_keeps_the_press_offer_gave_it(browser, serve):
    """A tab is built by `offer("button", …)` and then wears `role="tab"`, because that is
    what its strip is. The press it keeps is the strip's own row, declared beside the
    arrows and Home/End that walk it, and it is the only thing that consumes Space —
    which is otherwise the page's scroll.

    That row is what a page-wide control scope used to supply, and the scope was the wrong
    place for it: read off the role it stopped seeing tabs, so Enter did nothing and Space
    threw the reader down the page from a control that looked like it had answered; read
    off the tabindex it claimed every focus target `offer` builds and led with a press over
    a conversation thread that answers nothing. Declared where the strip is, the press
    cannot be lost to a rename or promised where nothing runs it, and the word on the line
    is the strip's own — it names the tab rather than the control.

    Asserted from the state where the press is the only way back: the tab strip is walked
    with arrows, so a focused tab is usually the selected one. Revealing the *other* panel
    leaves focus on a tab that is not selected, which is exactly when Enter has work to
    do."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)

    tabs.first.focus()
    # Reveal the second panel without moving focus, so the focused tab is not the selected
    # one and Enter has something to do.
    page.evaluate(
        """() => document.querySelector('#tab-bath')
                 .dispatchEvent(new CustomEvent('lf-reveal',
                   {bubbles: true, detail: {target: document.querySelector('#tab-bath')}}))"""
    )
    expect(tabs.first).to_be_focused()
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")

    # The line names the press, and the press re-selects the tab the reader is standing on.
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("open the tab")
    page.keyboard.press("Enter")
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # And Space is consumed rather than scrolling the page out from under the press.
    page.evaluate("() => document.querySelector('#tab-bath').click()")
    tabs.first.focus()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press(" ")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "Space scrolled the page instead of working the control it was promised on"
    )
    assert errors == []
    page.close()


def test_the_g_chord_selects_a_visible_tab_hint(browser, serve):
    """A tab can be selected from elsewhere on the page through its generated hint.

    Arrow keys serve a reader already standing in the tab strip. The page-level route
    names every visible tab, then selects and focuses the requested one so its
    local keyboard pattern is immediately available."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # Tabs need no separate kind mnemonic to remain directly reachable: the complete
    # generated map keeps their activation and focus behavior.
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-address-kind="Tab"]')).to_have_count(2)
    page.keyboard.type(address_code(page, "Tab", "tab-bath"))

    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(1)).to_be_focused()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", re.compile(".*"))
    expect(page.locator("#tab-feeders")).to_have_attribute("hidden", re.compile(".*"))
    assert errors == []
    page.close()


def test_the_g_chord_reaches_a_checkbox_a_widget_built(browser, serve):
    """A native press joins the generated route through the same offer that styles it."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    checkbox = page.locator("#patch .lf-diff-wrap")
    expect(checkbox).to_be_visible()
    checkbox.evaluate("node => { node.id = 'soft-wrap'; }")

    page.keyboard.press("g")
    chip = page.locator(f'{CHIPS}[data-lf-address-for="soft-wrap"]')
    code = address_code(page, "Control", "soft-wrap")
    index = chip.evaluate(
        "node => [...node.parentElement.children]"
        ".filter(candidate => candidate.dataset.lfAddress).indexOf(node)"
    )
    assert index >= 0
    for _ in range(index + 1):
        page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {code}: Control, Soft wrap. Press Enter to go there."
    )
    page.keyboard.press("Enter")

    expect(checkbox).to_be_checked()
    expect(checkbox).to_be_focused()
    assert errors == []
    page.close()


def test_generated_hints_branch_after_the_single_letter_alphabet(browser, serve):
    """A dense visible scene gets one prefix-free namespace with two-letter tails."""
    links = "".join(
        f'<a id="link-{n}" href="#link-{n}">link {n}</a>' for n in range(1, 24)
    )
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Dense links",
                f'<h1>Dense links</h1><nav id="links">{links}</nav>',
                head="""<style>
                  #links { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
                  #links a { display: block; padding: 6px; }
                </style>""",
            )
        ),
    )
    line = page.locator(".lf-shortcut-bar")

    page.keyboard.press("g")
    codes = address_codes(page)
    assert len(codes) == len(set(codes)) == 23
    assert all(code.isalpha() and code.islower() for code in codes)
    assert all(
        not other.startswith(code) for code in codes for other in codes if code != other
    )
    assert not set("afghjkmpt") & {code for code in codes if len(code) == 1}
    assert sum(len(code) == 1 for code in codes) == 16
    branched = [code for code in codes if len(code) == 2]
    assert len(branched) == 7 and len({code[0] for code in branched}) == 1

    prefix = branched[0][0]
    page.keyboard.press(prefix)
    assert address_codes(page) == branched, {
        "codes": address_codes(page),
        "errors": errors,
        "line": shortcut_bar_text(page),
        "live": page.locator(".lf-live").text_content(),
    }
    expect(page.locator(".lf-live")).to_have_text("7 targets remain.")
    expect(line).to_contain_text("back one letter")
    target_route = line.locator(
        '.lf-key:not([hidden])[data-lf-commands~="navigation.target"]'
    )
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
    ) == [["g", "pressed"], [prefix, "pressed"], ["…", "neutral"]]
    browse_route = line.locator(
        '.lf-key:not([hidden])[data-lf-commands~="navigation.target.next"]'
    )
    browse_faces = browse_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
    )
    assert [state for _, state in browse_faces] == ["pressed", "neutral"], browse_faces
    assert browse_faces[0][0] == "g", browse_faces
    assert re.fullmatch(r"⇥ / (⇧|Shift\+)⇥", browse_faces[1][0]), browse_faces
    continued_hint = page.locator(
        f'{CHIPS}[data-lf-address="{branched[0]}"] .lf-key-sequence'
    )
    assert continued_hint.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
    ) == [[prefix, "pressed"], [branched[0][1], "neutral"]]
    expect(continued_hint).to_have_css("gap", "1px")

    # Escape removes only the opaque prefix; the same visible scene returns. A complete
    # two-letter code then activates immediately, with no timeout or terminator.
    page.keyboard.press("Escape")
    assert address_codes(page) == codes
    page.keyboard.type(branched[-1])
    page.wait_for_url(re.compile(r"#link-23$"))
    expect(page.locator(CHIPS)).to_have_count(0)
    assert errors == []
    page.close()


def test_generated_hints_are_browsable_without_entering_the_paint_layer(browser, serve):
    """Tab speaks the visual map, Shift-Tab reverses it, and Enter activates it."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Browsable hints",
                """
<h1 id="top">Browsable hints</h1>
<p><a id="first" href="#top">First destination</a></p>
<p><a id="second" href="#arrival">Second destination</a></p>
<h2 id="arrival">Arrival</h2>
""",
            )
        ),
    )
    line = page.locator(".lf-shortcut-bar")

    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_count(2)
    expect(page.locator(".lf-goto-targets")).to_have_attribute("aria-hidden", "true")
    expect(page.locator(".lf-live")).to_contain_text("2 visible targets")
    expect(line).to_contain_text("browse hints")
    expect(line).to_contain_text("cancel")
    expect(line.locator('[data-lf-commands="navigation.address.back"]')).to_have_class(
        re.compile(r"\blf-sequence-control\b")
    )

    page.keyboard.press("Tab")
    first_code = address_code(page, "Link", "first")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, First destination. Press Enter to go there."
    )
    expect(page.locator(f'{CHIPS}[data-lf-address-for="first"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    page.keyboard.press("Tab")
    second_code = address_code(page, "Link", "second")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {second_code}: Link, Second destination. Press Enter to go there."
    )
    page.keyboard.press("Shift+Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, First destination. Press Enter to go there."
    )
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    assert errors == []
    page.close()


def test_the_arrows_say_which_way_the_section_under_the_reader_goes(browser, serve):
    """⏎ and space toggle a disclosure; → opens it and ← closes it. A direction and not a
    second toggle, which is the whole of what they add: → over a section already open
    leaves it open, where a toggle would have shut it. Only the direction with somewhere
    to go is bound, so the line names ← over an open section and → over a shut one and
    every key it names is a key that works — and each press that must change nothing
    follows one that changed something, since a box nobody has touched passes that
    assertion however dead the scope is.

    Both spellings of a folded section, because a reader standing on one cannot see which
    it is: the platform's <details>, and a settled option group, which is a span the
    widget wrote `aria-expanded` onto. One scope answers for both, and the press goes
    through the element's own click either way, so the keyboard leaves the page in the
    state the pointer would have left it in.

    The word follows either spelling within the press, not within the poll. Neither
    reports itself — an aria-expanded write fires no event at all — so what the line says
    about the key under the reader's finger rests on the attribute watch rather than on
    the two-second poll behind it. Both readings of it are taken once, through
    `shortcut_bar_text`: an assertion that retries cannot tell the watch from a poll that lands
    inside its budget, and the first version of this test went green with the watch
    broken.

    Shift+← is the last thing this holds to: a summary's words are the page's, and
    extending a selection through them must not shut the section they are in."""
    page, errors = open_page(browser, serve(DISCLOSED_PAGE))
    line = page.locator(".lf-shortcut-bar")
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"

    dsc = page.locator("#dsc")
    head = page.locator("#dsc-head")
    head.focus()
    expect(dsc).not_to_have_attribute("open", "")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))

    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # The press does not move the reader off what they pressed it on, so the next one
    # lands on the same section.
    expect(head).to_be_focused()
    said = shortcut_bar_text(page)
    assert re.search(opened + r"\s*close", said), said

    # A direction and not a toggle, which is the one thing ⏎ cannot say: this press
    # follows one that is proven live, so a scope answering nothing at all could not pass
    # it, and a toggle bound to the arrows would have shut the section here.
    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # Shift+← is a reader extending a selection through the summary's own words. A named
    # key asks for its modifiers exactly, so it is not this row's binding.
    page.keyboard.press("Shift+ArrowLeft")
    expect(dsc).to_have_attribute("open", "")

    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")
    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")

    # And the platform's own pair still toggles, once each: the row owns its whole binding
    # set, so the runtime makes the press the browser was going to make.
    page.keyboard.press("Enter")
    expect(dsc).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(dsc).not_to_have_attribute("open", "")

    # The other spelling, which keeps its state in ARIA's own attribute rather than in
    # `open`, and whose press is the widget's own handler rather than the platform's.
    row = page.locator("#settled .lf-settled")
    row.focus()
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#st-keep")).to_be_visible()
    # Nothing reports this one at all — an aria-expanded write fires no event anywhere —
    # so read once: the word is the attribute watch's answer by the time the press
    # returns, or it is the poll's two seconds later, and only an assertion that refuses
    # to retry can tell those apart.
    said = shortcut_bar_text(page)
    assert re.search(opened + r"\s*close", said), said
    # The line is one of two surfaces naming this row's keys, and the other is read by
    # somebody who cannot see the first. A row whose bindings answer from its own state
    # has to repaint both when the state moves, and only the line had a watch: the
    # attribute kept whichever way the row was standing when the scope was declared, so
    # it went on promising the arrow that no longer moves this section and withholding
    # the one that does.
    #
    # Read once for the reason the line is, and by the same clock: the heartbeat repaints
    # scopes too, so a retrying assertion goes green on the tick that lands inside its
    # budget and the fix it is meant to hold has nothing to fail against.
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowLeft"
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowLeft")
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#st-keep")).to_be_hidden()
    page.evaluate(RENDERED)
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowRight"

    # A disclosure in a message, where the disclosure scope does not reach: thread markup
    # is a second document beside the version, and the arrows are the page's. A diff,
    # because what is being asked is what a widget's own row names — a widget re-wording
    # this press reads its bindings from DISCLOSE, which answers for where the element
    # stands as well as which way it is standing, so the row cannot offer a key that
    # nothing there runs. The platform's pair still works it, so what differs is the
    # offer rather than the capability.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "claude",
            "revision": 1,
            "text": "The patch, for the record.",
            "markup": '<lf-diff id="msg-diff"><pre>'
            "diff --git a/gateway/limits.py b/gateway/limits.py\n"
            "--- a/gateway/limits.py\n"
            "+++ b/gateway/limits.py\n"
            "@@ -38,2 +38,2 @@ class Limiter:\n"
            "     def bucket_key(self, request):\n"
            "-        return request.remote_addr\n"
            "+        return request.token.id\n"
            "</pre></lf-diff>",
        },
    )
    told(page)
    # Opened, because standing somewhere is where focus is and a shut panel has nowhere to
    # stand: without this the summary took no focus, the reader was still on the page's own
    # row, and the line went on describing that one — an assertion that would have passed
    # for the wrong reason had the two been in the same state.
    page.get_by_role("button", name=re.compile("Threads")).click()
    staged = page.locator("#msg-diff summary").first
    expect(staged).to_be_visible()
    staged.focus()
    expect(staged).to_be_focused()
    # Every live row rather than the two hints that fit: the panel's own rows win the line
    # where the reader is standing in it, and what is asked here is what the register
    # answers, not which two chips got the room.
    shortcut_bar_text(page)  # the repaint's own frame, as everywhere else here
    chips = page.evaluate(
        "() => [...document.querySelectorAll('.lf-shortcut-bar .lf-key')]"
        ".map(c => c.textContent)"
    )
    assert any("⏎ / space" in c for c in chips), chips
    assert not any("←" in c or "→" in c for c in chips), chips
    # And the press, which is the half that would matter if no surface said anything: the
    # arrow is the page's here and moves nothing, where the platform's pair still folds it.
    opened_now = staged.evaluate("el => el.parentElement.open")
    page.keyboard.press("ArrowLeft")
    assert staged.evaluate("el => el.parentElement.open") is opened_now
    page.keyboard.press("Enter")
    assert staged.evaluate("el => el.parentElement.open") is not opened_now
    assert errors == []
    page.close()


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The shortcut bar and dispatcher read one return frame for each keyboard entry."""
    url = serve(NOTED_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-shortcut-bar")

    # Page scope: the standing verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("more")
    expect(line.locator("kbd").filter(has_text=re.compile(r"^esc$"))).to_have_count(0)

    # Armed with the panel closed: the direct panel destination and its way out are visible.
    page.keyboard.press("g")
    expect(line).to_contain_text("Threads panel")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("Threads panel")
    # The blue prefix is gone with the sequence; the ordinary line may reuse the same words.
    expect(
        page.locator('.lf-shortcut-bar kbd[data-lf-key-state="pressed"]')
    ).to_have_count(0)

    # c is comment everywhere. From the page it enters the page composer directly, and
    # one Escape undoes the one entry: field, panel, and focus origin together.
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(line).to_contain_text("send")
    expect(line).to_contain_text("back")
    # A send key on an empty box is answered, not swallowed — silence reads as a
    # send that happened.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-notice")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(line).not_to_contain_text("close threads")
    assert page.evaluate("() => document.activeElement === document.body")

    # g T is navigation to Threads. Its one completed sequence enters one surface, and one
    # Escape restores the page instead of stranding focus on the panel toggle.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-shortcut-reference")
    expect(help_el).to_be_visible()
    returning = help_el.locator(
        "section",
        has=page.get_by_role("heading", name="After entering a surface", exact=True),
    )
    expect(returning.locator('[data-lf-command="navigation.return"]')).to_contain_text(
        "Return from Threads panel"
    )
    expect(help_el.locator('[data-lf-command="navigation.back"]')).to_have_count(0)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    # The fast rung: t opens the inline thread, and Esc from it is one press out.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-conversation-thread")).to_be_focused()
    expect(line).to_contain_text("close thread")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_comments_quoted_passage_is_in_the_keyboard_journey(browser, serve):
    """The pointer's return-to-passage action is a focusable, named control too."""
    lead = "".join(f"<p>Earlier reading context, line {n}.</p>" for n in range(14))
    tail = "".join(f"<p>Later reading context, line {n}.</p>" for n in range(14))
    noted_page = NOTED_PAGE.replace('<p id="p1">', f'{lead}<p id="p1">').replace(
        '<figure id="fig">', f'{tail}<figure id="fig">'
    )
    url = serve(noted_page)
    d = serve.page_dir
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check this wording.",
            "anchor": {"section": "p1", "quote": "first passage"},
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(".lf-thread")).to_be_focused()
    page.keyboard.press("Tab")
    quote = page.locator(".lf-thread .lf-quote")
    expect(quote).to_be_focused()
    expect(quote).to_have_attribute("role", "button")
    expect(quote).to_have_attribute("aria-keyshortcuts", "Enter Space")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("return to the passage")

    quote.evaluate(
        """node => node.addEventListener('click', () => {
          node.dataset.keyboardActivations =
            String(Number(node.dataset.keyboardActivations || 0) + 1);
        })"""
    )
    passage = page.locator("#p1")
    passage.scroll_into_view_if_needed()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, passage.top - banner.bottom - 96);
        }"""
    )
    before = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert before["top"] > before["banner"] + 48
    assert before["bottom"] < before["height"] - 48
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    expect(quote).to_have_attribute("data-keyboard-activations", "2")
    after = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
        })"""
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=0.5)
    assert after["top"] == pytest.approx(before["top"], abs=0.5)

    # One painted pixel is not a readable arrival. Carry the passage almost entirely
    # behind the fixed banner, then the same quote must bring it back into view.
    page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, passage.bottom - banner.bottom - 1);
        }"""
    )
    sliver = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom};
        }"""
    )
    assert sliver["top"] < sliver["banner"] < sliver["bottom"]
    page.keyboard.press("Enter")
    returned = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
        })"""
    )
    assert returned["scroll"] != pytest.approx(sliver["scroll"], abs=0.5)
    assert returned["top"] > returned["banner"]

    # A resolved thread keeps its page placement even though its quote has no live
    # mark. On a covering phone panel, that retained destination remains an enabled
    # keyboard action, spends the sheet, and returns to the passage.
    page.get_by_role("button", name="Resolve thread", exact=True).click()
    round_trip(page)
    resized(page, 390, 800)
    page.locator('[data-filter-value="resolved"]').click()
    resolved_quote = page.locator(".lf-thread:not([hidden]) .lf-quote")
    expect(resolved_quote).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "false")
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    placed_before = page.evaluate("() => document.scrollingElement.scrollTop")
    resolved_quote.focus()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("return to the passage")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-panel")).to_be_hidden()
    placed_after = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert placed_after["scroll"] != placed_before
    assert placed_after["top"] > placed_after["banner"]
    assert placed_after["bottom"] < placed_after["height"]

    # When a later version removes the passage altogether, the same resolved quote is an
    # informative disabled stop. A pointer press has no destination to spend the sheet on,
    # so the covering panel and the page behind it both stay where the reader left them.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    without_passage = re.sub(r'<p id="p1">.*?</p>', "", noted_page, flags=re.DOTALL)
    (d / ".fixture-versions" / "v2.html").write_text(without_passage)
    stamp_version_file(d, 2, "remove the quoted passage")
    wait_for_revision(page, 2)
    resolved_quote = page.locator(".lf-thread:not([hidden]) .lf-quote")
    expect(resolved_quote).to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "true")
    assert resolved_quote.get_attribute("aria-keyshortcuts") is None
    expect(page.locator(".lf-panel")).to_be_visible()
    stranded_before = page.evaluate("() => document.scrollingElement.scrollTop")
    quote_box = resolved_quote.bounding_box()
    assert quote_box is not None
    page.mouse.click(
        quote_box["x"] + quote_box["width"] / 2,
        quote_box["y"] + quote_box["height"] / 2,
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == stranded_before
    resolved_quote.focus()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text(
        "return to the passage"
    )
    assert errors == []
    page.close()


def test_a_text_box_keeps_its_keys_from_the_widget_around_it(browser, serve):
    """A widget scope may contain a text box, but its bare keys still type there.

    The focused element's own rows remain nearer so a draft can keep its specific Escape
    and a wired composer can send with Mod+Enter. The text-entry scope then claims the
    characters and editing keys before an ancestor widget can see them."""
    url = serve(NOTED_PAGE)
    _publish(serve.page_dir, 2, NOTED_PAGE, "two")
    page, errors = open_page(browser, url)
    page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const host = document.createElement('section');
          host.id = 'key-owning-widget';
          const box = document.createElement('textarea');
          host.append(box);
          document.querySelector('main').append(host);
          commands(host, 'Around a text box', [
            {id: 'test.widget',
             keys: ['a', 'Enter', 'Shift+ArrowLeft', 'Mod+z', 'Escape'],
             does: 'Work the widget', line: 'work widget',
             run: (binding) => host.dataset.fired = binding},
          ]);
          box.focus();
        }"""
    )

    page.keyboard.press("a")
    page.keyboard.press("Enter")
    expect(page.locator("#key-owning-widget textarea")).to_have_value("a\n")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None
    page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.press("Control+z")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None

    # An unrelated core layer may stand at the same time. The widget ancestor remains
    # nearer for keys the text-entry shield does not claim; only editing stays native.
    page.locator(".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.locator("#key-owning-widget textarea").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#key-owning-widget")).to_have_attribute("data-fired", "Escape")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    assert errors == []
    page.close()


def test_native_top_layers_bound_the_keyboard_stack(browser, serve):
    """Native layer ownership blocks ancestors and survives nesting and light dismiss."""
    url = serve(NOTED_PAGE)
    _publish(serve.page_dir, 2, NOTED_PAGE, "two")
    page, errors = open_page(browser, url)
    page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const { shadowStage } = await import('/runtime/shadow-stage.js');
          const host = document.createElement('section');
          host.id = 'around-native-layer';
          const dialog = document.createElement('dialog');
          dialog.id = 'nested-modal';
          const shadowHost = document.createElement('div');
          const trigger = document.createElement('button');
          trigger.textContent = 'Open nested popover';
          const popover = document.createElement('div');
          popover.id = 'shadow-popover';
          popover.popover = 'auto';
          popover.textContent = 'Nested popover';
          trigger.popoverTargetElement = popover;
          shadowStage(shadowHost, [trigger, popover]);
          dialog.append(shadowHost);
          host.append(dialog);
          document.querySelector('main').append(host);
          commands(host, 'Around a native layer', [
            {id: 'test.outer-escape', keys: ['Escape'], does: 'Work the outer widget',
             line: 'work outer', run: () => { host.dataset.fired = 'Escape'; }},
          ]);
          dialog.showModal();
          trigger.focus();
          trigger.click();
        }"""
    )
    modal = page.locator("#nested-modal")
    popover = page.locator("#shadow-popover")
    expect(modal).to_be_visible()
    expect(popover).to_be_visible()

    # The popover is nonmodal, but the modal below it remains a hard floor. A page
    # command and the widget ancestor outside the dialog are both unreachable.
    page.keyboard.press("l")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    page.keyboard.press("Escape")
    expect(popover).to_be_hidden()
    expect(modal).to_be_visible()
    assert page.locator("#around-native-layer").get_attribute("data-fired") is None
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    assert page.locator("#around-native-layer").get_attribute("data-fired") is None

    # Native focusing steps may synchronously open a newer modal. Recording the first
    # opening before those steps preserves that order, while an idempotent call on the
    # older dialog does not move it back to the top.
    assert page.evaluate(
        """async () => {
          const { currentNativeLayer } = await import('/runtime/native-layers.js');
          const first = document.createElement('dialog');
          const second = document.createElement('dialog');
          const focus = document.createElement('button');
          focus.autofocus = true;
          focus.textContent = 'Focus opens the second modal';
          first.append(focus);
          document.body.append(first, second);
          focus.addEventListener('focus', () => second.showModal(), {once: true});
          first.showModal();
          const nested = currentNativeLayer() === second;
          first.showModal();
          const idempotent = currentNativeLayer() === second;
          second.close();
          first.close();
          return nested && idempotent;
        }"""
    )

    # A newer modal temporarily removes an auto popover from the native top layer. Its
    # keyboard return frame remains suspended and belongs to the restored popover.
    open_versions(page)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    assert page.evaluate(
        """async () => {
          const { current } = await import('/runtime/keyboard/return-stack.js');
          return current()?.root === document.querySelector('.lf-version-menu');
        }"""
    )
    page.locator(".lf-version").click()

    # A closed inner layer is retired rather than mistaken for a frame covered by the
    # older modal now visible beneath it. The outer frame consequently owns Escape.
    current = page.evaluate(
        """async () => {
          const { invoke, current } = await import('/runtime/keyboard/return-stack.js');
          const outer = document.createElement('dialog');
          const inner = document.createElement('dialog');
          outer.id = 'return-outer';
          inner.id = 'return-inner';
          document.body.append(outer, inner);
          const row = (id, dialog) => ({
            id,
            returnFrame: () => ({
              active: () => true,
              close: () => {
                dialog.close();
                document.body.dataset.closedFrame = id;
              },
              does: `Close ${id}`,
              line: `close ${id}`,
            }),
          });
          invoke(row('outer', outer), 'x', () => outer.showModal());
          invoke(row('inner', inner), 'x', () => inner.showModal());
          inner.close();
          return current().does;
        }"""
    )
    assert current == "Close outer"
    page.keyboard.press("Escape")
    expect(page.locator("#return-outer")).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-closed-frame", "outer")
    assert errors == []
    page.close()


def test_a_scope_cannot_give_one_live_key_two_meanings(browser, serve):
    """An ambiguous row set is refused at the scope's first paint, gated or not.

    A declaration's shape is still refused where it is written, but what its rows mean
    is read only once every module has evaluated, so the ambiguity surfaces at that
    paint and takes the scope down with it. Reusing a key in mutually exclusive states
    remains valid; a card grip relies on that to make Enter and Space mean grab before
    the move and drop during it."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    answers = page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const { activeRows, answers: bindingAnswers, canonicalBinding } =
            await import('/runtime/keyboard/bindings.js');
          const { invoke } = await import('/runtime/keyboard/return-stack.js');
          const { paintKeys } = await import('/runtime/keyboard/scopes.js');
          const declare = (id, rows) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            try {
              commands(button, id, rows);
              return 'declared';
            } catch (error) {
              return error.message;
            } finally {
              button.remove();
            }
          };
          const conflicts = (rows) => {
            try {
              activeRows(rows, 'Alias meanings');
              return 'accepted';
            } catch (error) {
              return error.message;
            }
          };
          const firstPaint = (id, rows, when) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            let declaration = 'declared';
            try {
              commands(button, id, rows, when);
            } catch (error) {
              declaration = error.message;
            }
            const declared = button.getAttribute('aria-keyshortcuts');
            const paints = [];
            for (let i = 0; i < 2; i++) {
              try {
                paintKeys();
                paints.push('painted');
              } catch (error) {
                paints.push(error.message);
              }
            }
            const painted = button.getAttribute('aria-keyshortcuts');
            button.remove();
            return {declaration, declared, paints, painted};
          };
          const atTheFrame = async (id, rows) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            commands(button, id, rows);
            const declared = button.getAttribute('aria-keyshortcuts');
            await new Promise((settle) =>
              requestAnimationFrame(() => requestAnimationFrame(settle)));
            const framed = button.getAttribute('aria-keyshortcuts');
            button.remove();
            return {declared, framed};
          };
          // Declared twice before any paint: the first declaration ambiguous, the second
          // sound. Only the frame reads the superseded one, so this is the case a paintKeys
          // call cannot reach.
          const redeclaredAtTheFrame = async (id, first, second) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            commands(button, id, first);
            commands(button, id, second);
            await new Promise((settle) =>
              requestAnimationFrame(() => requestAnimationFrame(settle)));
            const framed = button.getAttribute('aria-keyshortcuts');
            const standing = Boolean(
              (await import('/runtime/keyboard/scopes.js')).elementScopes.get(button));
            button.remove();
            return {framed, standing};
          };
          const malformedFrame = () => {
            try {
              invoke(
                {id: 'test.bad-frame', returnFrame: () => ({active: () => true})},
                'F8',
                () => {},
              );
              return 'accepted';
            } catch (error) {
              return error.message;
            }
          };
          return {
            ambiguous: firstPaint('ambiguous', [
              {id: 'test.first', keys: ['F2'], does: 'First meaning', line: 'first', run: () => {}},
              {id: 'test.second', keys: ['F2'], does: 'Second meaning', line: 'second', run: () => {}},
            ]),
            gatedAmbiguous: firstPaint('gated-ambiguous', [
              {id: 'test.gated-first', keys: ['F4'], does: 'First gated meaning', line: 'first', run: () => {}},
              {id: 'test.gated-second', keys: ['F4'], does: 'Second gated meaning', line: 'second', run: () => {}},
            ], () => true),
            exclusive: firstPaint('exclusive', [
              {id: 'test.first-state', keys: ['F2'], does: 'First state', line: 'first',
               when: () => true, run: () => {}},
              {id: 'test.second-state', keys: ['F2'], does: 'Second state', line: 'second',
               when: () => false, run: () => {}},
            ]),
            missingIdentity: declare('missing-identity', [
              {keys: ['F5'], does: 'Anonymous command', line: 'anonymous', run: () => {}},
            ]),
            malformedIdentity: declare('malformed-identity', [
              {id: 'Sentence shaped identity', keys: ['F5'], does: 'Named badly',
               line: 'bad identity', run: () => {}},
            ]),
            duplicateIdentity: declare('duplicate-identity', [
              {id: 'test.same', keys: ['F5'], does: 'First route', line: 'first', run: () => {}},
              {id: 'test.same', keys: ['F6'], does: 'Second route', line: 'second', run: () => {}},
            ]),
            modifierAlias: conflicts([
              {keys: ['Mod+Shift+x'], does: 'First alias'},
              {keys: ['Shift+Mod+x'], does: 'Second alias'},
            ]),
            caseAlias: conflicts([
              {keys: ['a'], does: 'Lowercase alias'},
              {keys: ['A'], does: 'Uppercase alias'},
            ]),
            punctuationAlias: conflicts([
              {keys: ['?'], does: 'Layout-owned punctuation'},
              {keys: ['Shift+?'], does: 'Shifted alias'},
            ]),
            spacePair: conflicts([
              {keys: [' '], does: 'Read down'},
              {keys: ['Shift+ '], does: 'Read up'},
            ]),
            spaceIdentity: [canonicalBinding(' '), canonicalBinding('Shift+ ')],
            spaceAnswers: {
              down: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
              downFromShift: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              up: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              upWithoutShift: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
            },
            noncanonical: declare('noncanonical', [
              {id: 'test.noncanonical', keys: ['Shift+Mod+x'], does: 'Noncanonical binding',
               line: 'work', run: () => {}},
            ]),
            namedSpace: declare('named-space', [
              {id: 'test.named-space', keys: ['Space'], does: 'Named space binding',
               line: 'work', run: () => {}},
            ]),
            invalidDecision: declare('invalid-decision', [
              {id: 'test.invalid-decision', keys: [], control: document.body,
               decision: true, does: 'Invalid decision role'},
            ]),
            invalidDecisionRoute: declare('invalid-decision-route', [
              {id: 'test.invalid-decision-family', keys: ['ArrowLeft'],
               control: document.body, does: 'Invalid decision route', routes: [{
                 id: 'test.invalid-decision-route', binding: 'ArrowLeft',
                 decision: true, does: 'Invalid decision route',
               }]},
            ]),
            emptyDecision: declare('empty-decision', [
              {id: 'test.empty-decision', keys: [], control: document.body,
               decision: '  ', does: 'Empty decision action name'},
            ]),
            invalidReturnFrame: declare('invalid-return-frame', [
              {id: 'test.invalid-return-frame', keys: ['F8'], does: 'Enter badly',
               line: 'enter', returnFrame: {}, run: () => {}},
            ]),
            returnWithoutCommand: declare('return-without-command', [
              {id: 'test.return-without-command', keys: ['F8'], does: 'Enter nowhere',
               line: 'enter', returnFrame: () => ({})},
            ]),
            malformedFrame: malformedFrame(),
            atFrame: await atTheFrame('frame-painted', [
              {id: 'test.frame-painted', keys: ['F7'], does: 'Painted at the frame',
               line: 'frame', run: () => {}},
            ]),
            redeclared: await redeclaredAtTheFrame('redeclared', [
              {id: 'test.stale-first', keys: ['F9'], does: 'First stale meaning',
               line: 'first', run: () => {}},
              {id: 'test.stale-second', keys: ['F9'], does: 'Second stale meaning',
               line: 'second', run: () => {}},
            ], [
              {id: 'test.replacing', keys: ['F9'], does: 'The declaration that stands',
               line: 'stands', run: () => {}},
            ]),
          };
        }"""
    )
    for name, binding in (("ambiguous", "F2"), ("gatedAmbiguous", "F4")):
        refused = answers[name]
        assert refused["declaration"] == "declared", answers
        assert refused["declared"] is None, answers
        assert f"two live meanings for {binding}" in refused["paints"][0], answers
        assert refused["paints"][1] == "painted", answers
        assert refused["painted"] is None, answers
    assert answers["exclusive"] == {
        "declaration": "declared",
        "declared": None,
        "paints": ["painted", "painted"],
        "painted": "F2",
    }, answers
    assert "has no stable command id" in answers["missingIdentity"], answers
    assert "is not a stable command id" in answers["malformedIdentity"], answers
    assert "declares test.same twice" in answers["duplicateIdentity"], answers
    assert "two live meanings for Shift+Mod+x" in answers["modifierAlias"], answers
    assert "two live meanings for A" in answers["caseAlias"], answers
    assert "two live meanings for Shift+?" in answers["punctuationAlias"], answers
    assert answers["spacePair"] == "accepted", answers
    assert answers["spaceIdentity"] == [" ", "Shift+ "], answers
    assert answers["spaceAnswers"] == {
        "down": True,
        "downFromShift": False,
        "up": True,
        "upWithoutShift": False,
    }, answers
    assert "write the canonical Mod+Shift+x" in answers["noncanonical"], answers
    assert 'write the canonical " "' in answers["namedSpace"], answers
    expected_decision_error = (
        "invalid Decision action name true; expected a non-empty string or function "
        "returning one"
    )
    assert expected_decision_error in answers["invalidDecision"], answers
    assert expected_decision_error in answers["invalidDecisionRoute"], answers
    assert "invalid Decision action name" in answers["emptyDecision"], answers
    assert "returnFrame that is not a function" in answers["invalidReturnFrame"], (
        answers
    )
    assert (
        "declares a return frame but runs no entry" in answers["returnWithoutCommand"]
    ), answers
    assert "must return active, close, does, and line" in answers["malformedFrame"], (
        answers
    )
    # Nobody repaints the register for this one. The repaint frame the declaration itself
    # asks for is the first paint, so the projection lands there without a state change.
    assert answers["atFrame"] == {"declared": None, "framed": "F7"}, answers
    # The superseded declaration is owed no reading: read at the frame, its refusal
    # would have retracted the one that replaced it.
    assert answers["redeclared"] == {"framed": "F9", "standing": True}, answers

    # Help merges instances with the same title for presentation. Repeated keys there
    # belong to separate focus locations, so they are not a conflict in either scope.
    page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          let first;
          for (const label of ['First', 'Second']) {
            const button = document.createElement('button');
            button.textContent = label;
            document.querySelector('main').append(button);
            if (!first) first = button;
            commands(button, 'Repeated controls', [
              {id: 'test.repeated', keys: ['F3'], does: () => `Work ${label}`,
               line: 'work', run: () => button.dataset.fired = '1'},
              ...(label === 'Second' ? [{
                id: 'test.second-only', keys: ['F6'], does: 'Work only the second',
                line: 'second only', reach: 'on the second control',
                run: () => button.dataset.secondFired = '1',
              }] : []),
            ]);
          }
          first.focus();
        }"""
    )
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="All keyboard shortcuts")).to_be_visible()
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    search.fill("work only the second")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-shortcut-reference-meta")).to_have_text(
        "Available on the second control"
    )
    search.fill("work first")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="First", exact=True)).to_have_attribute(
        "data-fired", "1"
    )
    expect(page.get_by_role("button", name="Second", exact=True)).not_to_have_attribute(
        "data-fired", "1"
    )
    assert errors == []
    page.close()


def test_signoff_uses_its_visible_button_and_g_l_never_falls_through(browser, serve):
    """Approval is a button action; a dead sequence destination cannot turn into it."""
    html = NOTED_PAGE.replace(
        '<script type="module" src="/leaf.js"></script>',
        '<meta name="lf-review" content="sign-off">\n'
        '<script type="module" src="/leaf.js"></script>',
    )
    page, errors = open_page(browser, serve(html))
    approve = page.locator(".lf-signoff")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    # All leaves is conditional. With no neighbouring leaf, its sequence must not be
    # reinterpreted as a page action carrying the same final key.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(approve).to_have_text("Approve version")
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"
    ]

    approve.focus()
    with sending(page, "the approval"):
        page.keyboard.press("Enter")
    expect(approve).to_have_text("✓ Version approved")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    assert "(L)" not in approve.get_attribute("title")
    done = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"]
    assert len(done) == 1, done
    assert done[0]["text"] == "Looks good"
    assert errors == []
    page.close()


def test_banner_destinations_use_transient_target_overlays(browser, serve):
    """The g sequence labels visible banner controls without changing their layout."""
    url = serve(ASKS_PAGE)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A note."},
    )
    page, errors = open_page(browser, url)
    resized(page, 1600, 900)
    more = page.locator(".lf-key-more")
    expect(more).to_have_attribute("aria-label", "? more")
    key_faces = page.evaluate(
        """() => ['.lf-key-more kbd', '.lf-shortcut-bar .lf-key:not([hidden]) kbd']
          .map(sel => { const s = getComputedStyle(document.querySelector(sel));
            return {height: s.height, padding: s.padding, border: s.borderTopWidth,
                    radius: s.borderRadius, font: s.fontFamily};
          })"""
    )
    assert key_faces[0] == key_faces[1], key_faces
    version = page.locator(".lf-version")
    banner_destinations = {
        "navigation.panel.threads": (page.locator(".lf-threads-toggle"), "T"),
        "navigation.panel.asks": (page.locator(".lf-asks"), "A"),
    }
    for control, suffix in banner_destinations.values():
        expect(control).to_have_attribute("title", re.compile(rf"\(g {suffix}\)$"))
        expect(control.locator(".lf-target-hint")).to_have_count(0)
    expect(page.locator(".lf-goto-targets > [data-lf-address-command]")).to_have_count(
        0
    )
    expect(version).to_be_disabled()
    expect(version).to_have_attribute("title", "v1")
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    # Put an ordinary page destination where the Threads hint will first stand. The
    # second placement pass must treat the already-seated control hint as occupied.
    threads_box = page.locator(".lf-threads-toggle").bounding_box()
    page.evaluate(
        """box => {
          const probe = document.createElement('a');
          probe.id = 'hint-collision-probe';
          probe.href = '#hint-collision-probe';
          probe.textContent = 'Collision probe';
          const bannerBottom = document.querySelector('.lf-banner')
            .getBoundingClientRect().bottom;
          Object.assign(probe.style, {
            position: 'fixed', left: `${box.x}px`, top: `${bannerBottom + 4}px`,
          });
          document.querySelector('main').append(probe);
        }""",
        threads_box,
    )

    before = page.locator(".lf-banner").bounding_box()
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("visible target")
    expect(
        page.locator(f'{CHIPS}[data-lf-address-for="hint-collision-probe"]')
    ).to_be_visible()
    for command, (control, suffix) in banner_destinations.items():
        hint = page.locator(
            f'.lf-goto-targets > .lf-target-hint[data-lf-address-command="{command}"]'
        )
        expect(hint).to_be_visible()
        assert hint.locator("kbd").evaluate_all(
            "keys => keys.map(key => [key.textContent, key.dataset.lfKeyState])"
        ) == [["g", "pressed"], [suffix, "neutral"]]
        expect(control.locator(".lf-target-hint")).to_have_count(0)
        hint_box, control_box = control.evaluate(
            """(control, command) => [
              document.querySelector(
                `.lf-goto-targets > [data-lf-address-command="${command}"]`
              ).getBoundingClientRect().toJSON(),
              control.getBoundingClientRect().toJSON(),
            ]""",
            command,
        )
        assert hint_box["y"] - control_box["y"] - control_box[
            "height"
        ] == pytest.approx(2, abs=0.5), (
            command,
            hint_box,
            control_box,
        )
        assert hint_box["x"] + hint_box["width"] / 2 == pytest.approx(
            control_box["x"] + control_box["width"] / 2, abs=0.5
        ), (command, hint_box, control_box)
    all_hints = page.locator(".lf-goto-targets > .lf-target-hint:visible")
    boxes = all_hints.evaluate_all(
        """hints => hints.map(hint => {
          const box = hint.getBoundingClientRect();
          return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
        })"""
    )
    assert all(
        not (
            left["left"] < right["right"]
            and right["left"] < left["right"]
            and left["top"] < right["bottom"]
            and right["top"] < left["bottom"]
        )
        for index, left in enumerate(boxes)
        for right in boxes[index + 1 :]
    ), boxes
    assert page.locator(".lf-banner").bounding_box() == before

    # A narrow banner folds less-used controls away. The surviving controls also have
    # open space above, but each destination hint belongs immediately below its control.
    resized(page, 390, 800)
    for command, control in (
        ("navigation.panel.threads", page.locator(".lf-threads-toggle")),
    ):
        hint = page.locator(
            f'.lf-goto-targets > .lf-target-hint[data-lf-address-command="{command}"]'
        )
        expect(hint).to_be_visible()
        hint_box, control_box = control.evaluate(
            """(control, command) => [
              document.querySelector(
                `.lf-goto-targets > [data-lf-address-command="${command}"]`
              ).getBoundingClientRect().toJSON(),
              control.getBoundingClientRect().toJSON(),
            ]""",
            command,
        )
        assert hint_box["y"] - control_box["y"] - control_box[
            "height"
        ] == pytest.approx(2, abs=0.5), (
            command,
            hint_box,
            control_box,
        )
        assert hint_box["x"] + hint_box["width"] / 2 == pytest.approx(
            control_box["x"] + control_box["width"] / 2, abs=0.5
        ), (command, hint_box, control_box)
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-goto-targets > [data-lf-address-command]")).to_have_count(
        0
    )

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).not_to_contain_text(
        "Letter, number & punctuation shortcuts"
    )
    expect(page.locator(".lf-shortcut-reference-meta")).to_be_visible()
    assert errors == []
    page.close()


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per binding, and every surface is a projection of it. The d/u
    reading-page pair is the case that named this: a runtime key must be visible wherever
    the keyboard vocabulary is projected.

    Where it is projected is the shelf and the reference, not the resting line, which
    holds two chips and spends neither on scrolling. So the line is asked for the row it
    holds rather than the row it paints, and the reference below is read for the words —
    a key named on no surface at all is what this refuses.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")
    movement = line.locator('.lf-key[data-lf-commands~="page.down"]')
    expect(movement).to_have_count(1)
    expect(movement).to_have_attribute("data-lf-commands", re.compile(r"\bpage\.up\b"))
    expect(movement.locator("kbd")).to_have_text("d / u")
    expect(movement).to_contain_text("page down / up")
    # Declared and worded, and painted where the reader asks rather than on the resting
    # glance. The reference below is the surface that names it, and this is the pair of
    # counts that tells a row the line declined to paint from a row that says nothing.
    expect(
        line.locator('.lf-key:not([hidden])[data-lf-commands~="page.down"]')
    ).to_have_count(0)
    resized(page, 420, 800)
    compact = line.evaluate(
        """node => {
          const visible = [...node.children].filter(el => el.checkVisibility());
          const tops = [];
          const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
          for (const el of visible)
            if (tops.every(top => Math.abs(top - el.offsetTop) > tolerance))
              tops.push(el.offsetTop);
          return {
            rows: tops.length,
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert compact["rows"] <= 2, compact
    assert compact["scrollWidth"] <= compact["clientWidth"], compact
    assert compact["scrollHeight"] <= compact["clientHeight"], compact

    # Linux's wider system face wraps this line at the smallest supported window, and the
    # disclosure is the one control on it: whatever the face costs, More stays painted and
    # the line stays inside its own box rather than clipping the way out of itself.
    resized(page, 320, 800)
    page.evaluate(RENDERED)
    smallest = line.evaluate(
        """node => {
          const more = node.querySelector('.lf-key-more');
          return {
            moreShown: more.checkVisibility(),
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert smallest["moreShown"], smallest
    assert smallest["scrollWidth"] <= smallest["clientWidth"], smallest
    assert smallest["scrollHeight"] <= smallest["clientHeight"], smallest
    resized(page, 1280, 800)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).to_contain_text(
        "Move 60% of a page down"
    )
    expect(page.locator(".lf-shortcut-reference")).to_contain_text(
        "Move 60% of a page up"
    )
    expect(page.locator(".lf-shortcut-reference")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("F7")

    refused = page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.no-line', keys: ['F2'],
                does: 'a press with nothing to say for itself',
                run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "no word for the shortcut bar" in refused, refused

    # The other half of what this gate is for, and the quieter failure. `answers` asks
    # after Mod, Alt and Shift by name and reads every other prefix as absent, so a
    # binding written `Ctrl+k` is not a key that never fires — it is `k`, which fires on
    # a bare press while both surfaces spell the chip "Ctrl+k" and the press the chip
    # names does nothing. A declaration that means a different key than it says is the
    # one thing no surface can project, so it is refused where declarations enter.
    modified = page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.bad-modifier', keys: ['Ctrl+k'],
                does: 'a modifier the matcher never asks about',
                line: 'a key that is really just k', run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "Ctrl is no modifier" in modified, modified
    assert "Mod, Alt, Shift" in modified, modified

    # Routes split one compact row into separately addressable commands. Every declared
    # binding therefore needs exactly one route: otherwise dispatch can gain a press that
    # both the reference and shortcut bar omit from their shared presentation projection.
    routed = page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const declare = row => {
            try {
              commands(document.body, 'A routed project scope', [row]);
              return 'declared';
            } catch (e) {
              return e.message;
            }
          };
          return {
            missing: declare({
              id: 'test.missing-route', keys: ['F2', 'F3'],
              does: 'Move either way', line: 'move either way', run: () => {},
              routes: [{
                id: 'test.missing-route.first', binding: 'F2',
                does: 'Move one way', line: 'move one way',
              }],
            }),
            duplicate: declare({
              id: 'test.duplicate-route', keys: ['F4'],
              does: 'Move once', line: 'move once', run: () => {},
              routes: [
                {
                  id: 'test.duplicate-route.first', binding: 'F4',
                  does: 'Move first', line: 'move first',
                },
                {
                  id: 'test.duplicate-route.second', binding: 'F4',
                  does: 'Move second', line: 'move second',
                },
              ],
            }),
          };
        }"""
    )
    assert "has no route for F3" in routed["missing"], routed
    assert "routes F4 twice" in routed["duplicate"], routed

    # A registered result may deliberately precede the platform's own half of a press.
    # It still enters through the same register — and therefore the same surfaces and
    # scoping — but the dispatcher must not cancel that native result. The versions menu
    # uses this for the Tab that closes it before the browser moves focus past its door.
    native = page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const owner = document.createElement('div');
          owner.tabIndex = -1;
          document.body.append(owner);
          owner.focus();
          let ran = 0;
          commands(owner, 'A native companion', [
            { id: 'test.native-companion', keys: ['F2'],
              does: 'Run before the browser', line: 'run first',
              native: true, run: () => ran++ },
          ]);
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          owner.dispatchEvent(event);
          owner.remove();
          return {ran, prevented: event.defaultPrevented};
        }"""
    )
    assert native == {"ran": 1, "prevented": False}, native
    assert errors == []
    page.close()


def test_a_partially_shadowed_row_keeps_each_other_live_binding(browser, serve):
    """Shadowing is per binding, so one local `d` must not hide the page row's live `u`.

    Multi-key rows keep related commands compact, but presentation cannot treat that visual
    grouping as dispatch ownership. The effective row retains the unshadowed route, its own
    direction word, and the same command identity the reference exposes."""
    html = NOTED_PAGE.replace("</main>", '<div style="height: 2400px"></div></main>')
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { commands } = await import('/runtime/widget-api.js');
          const target = document.createElement('button');
          target.id = 'local-down';
          target.textContent = 'Local down';
          document.querySelector('main').prepend(target);
          commands(target, 'On local down', [{
            id: 'test.local-down', keys: ['d'], does: 'Local down', line: 'local down',
            run: () => { target.dataset.pressed = '1'; },
          }]);
          target.focus();
        }"""
    )

    # The row the line holds rather than the one it paints. Both are the same projection —
    # renderLine builds every live row and then hides what it has no room for — and the
    # The resting line spends both chips on Comment and target selection, so asking for
    # a painted chip would be asking about the width instead of the shadowing.
    line = page.locator(".lf-shortcut-bar")
    up = line.locator('.lf-key[data-lf-commands="page.up"]')
    expect(up).to_have_count(1)
    expect(up.locator("kbd")).to_have_text("u")
    expect(up).to_contain_text("page up")
    expect(line.locator('[data-lf-commands~="page.down"]')).to_have_count(0)

    before = page.evaluate("() => { scrollTo(0, 1000); return scrollY; }")
    assert before > 0
    page.keyboard.press("u")
    page.wait_for_function("before => scrollY < before", arg=before)
    assert page.locator("#local-down").get_attribute("data-pressed") is None
    assert errors == []
    page.close()


def test_the_register_is_the_only_way_a_key_enters_the_runtime():
    """Every surface that names a key is a projection of the register, which holds only if
    nothing binds a key behind its back. That is not a property a rendered page can be
    asked about — a listener nobody declared looks exactly like no listener at all until
    the press it eats goes missing — so it is pinned in the source, the way the
    document-level class surface is.

    Two are allowed and both are named here. The dispatcher is the register's own. The aim
    latch is not a binding at all: holding ⌥ arms nothing and answers no press, it paints
    what a click would take, and its keyup half has no place in a table of presses. A third
    is how every drift this register replaced began — a `keydown` beside a display list,
    the two of them free to disagree about which keys the widget answers."""
    layer = ROOT / "skills/leaf"
    sources = [
        layer / "assets/leaf.js",
        *sorted((layer / "assets/runtime").rglob("*.js")),
        *sorted((layer / "packages").glob("*/widgets/*.js")),
        *sorted((ROOT / "examples/packages").glob("*/widgets/*.js")),
    ]
    listeners = [
        f"{src.name}:{n}"
        for src in sources
        for n, line in enumerate(src.read_text().splitlines(), 1)
        if 'addEventListener("keydown"' in line
    ]
    assert len(listeners) == 2, (
        f"the runtime's keydown listeners changed: {listeners}. A key belongs in the "
        "register (keys(el, title, rows)), which is what lets a surface promise it."
    )


def test_native_controls_need_no_generic_space_binding(browser, serve):
    """The reference has no synthetic generic-control command. Specialized controls
    such as a board grip still declare the Space meaning that belongs to their widget."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-shortcut-reference")
    expect(help_el).not_to_contain_text("On a control")
    expect(help_el.locator("tr", has_text="Grab the card")).to_contain_text("space")
    page.keyboard.press("Escape")

    # And the key does what the reference says it does.
    grip = page.locator("lf-board .lf-grip").first
    grip.focus()
    page.keyboard.press(" ")
    expect(page.locator(".lf-lift")).to_have_count(1)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("drop")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-lift")).to_have_count(0)
    assert errors == []
    page.close()


def test_holding_a_key_repeats_only_where_the_press_is_a_walk(
    browser, serve, live_leaf
):
    """A held key repeats keydown where a real button fires once. A walk wants that — t
    down threads, a down Asks, arrows down the tray — and a press that toggles or navigates
    does not: a held `]` was a page navigation per repeat, and a held pick a `choose` per
    repeat, each of them one decision the reader made once. So a row says whether it
    repeats and the default is no, where before only `offer`'s own listener had thought
    about it and the global table had not.

    No gesture Playwright makes carries the repeat flag, so the press is dispatched with
    it set. That is the event a held key sends and the handler under test is the one the
    page installed; the tap below it, dispatched the same way and answered, is what says
    so rather than leaving the held press to pass for want of reaching anything."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(ASKS_PAGE, comments=3))
    press = """([key, repeat, shiftKey = false]) => document.dispatchEvent(
        new KeyboardEvent('keydown',
          {key, repeat, shiftKey, bubbles: true, cancelable: true}))"""

    page.keyboard.press("t")
    expect(page.locator(".lf-thread").first).to_be_focused()
    page.evaluate(press, ["t", True])  # a walk repeats
    expect(page.locator(".lf-thread").nth(1)).to_be_focused()

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision[data-lf-ask]")).to_have_count(1)
    page.evaluate(press, ["a", True])  # the same grammar repeats for asks
    expect(page.locator("#sug-refill[data-lf-ask]")).to_have_count(1)

    tray = page.locator(".lf-others-panel")
    page.keyboard.press("g")
    page.evaluate(press, ["l", True, True])  # a panel destination does not repeat
    expect(tray).to_be_hidden()
    page.evaluate(press, ["l", False, True])  # the same event, answered
    expect(tray).to_be_visible()
    assert errors == []
    page.close()


def test_the_ask_walk_measures_from_chrome_only_where_the_chrome_holds_an_ask(
    browser, serve
):
    """The reader's place has to be a place in the walk's own ordered space. The chrome is
    appended after the whole page, so a reader standing on a thread in the panel measures
    as past every ask there is, and a walk clamped at its edges sends both `a` and `A` to
    the last one rather than to the first.

    The route runs through the chrome all the same: a widget frozen into a reply is an ask
    the walk visits, and a reader working its controls is standing in the space the step
    measures. So the question is which asks the layer holds and not whether the layer is
    chrome.

    The backward press is made after walking off the reply's ask and down to the first, so
    `landed` names a page ask. A walk that cannot read where the reader is answers from it
    instead, and answers plausibly."""
    url = serve(
        leaf_page(
            "asks over a panel",
            """
<h1 id="h">Open questions</h1>
<lf-ask id="first-decision"><h2>Where should the feeders go?</h2>
<lf-options id="first" choose>
  <lf-option id="fi-hedge"><strong>Along the hedge</strong></lf-option>
  <lf-option id="fi-lawn"><strong>Out on the lawn</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="second-decision"><h2>Who fills them?</h2>
<lf-options id="second" choose>
  <lf-option id="se-rota"><strong>A rota</strong></lf-option>
  <lf-option id="se-camera"><strong>Whoever the camera calls</strong></lf-option>
</lf-options></lf-ask>
""",
        ),
        comments=2,
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "And one for you in here.",
            "markup": '<lf-ask id="reply-decision"><h3>Which baffle?</h3>'
            '<lf-options id="reply-ask" choose>'
            '<lf-option id="re-dome"><strong>A dome</strong></lf-option>'
            '<lf-option id="re-cone"><strong>A cone</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    page, errors = open_page(browser, live_url(url))

    # A thread is chrome holding no ask, so the walk starts from the page.
    page.keyboard.press("t")
    expect(page.locator(".lf-thread").first).to_be_focused()
    page.keyboard.press("a")
    expect(page.locator("#first-decision")).to_be_focused()

    # The reply's ask is in the route. Walking off it and back down to the first leaves
    # `landed` on a page ask, which is what the last press below must not answer from.
    page.keyboard.press("a")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("a")
    expect(page.locator("#reply-decision")).to_be_focused()
    page.keyboard.press("Shift+a")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("Shift+a")
    expect(page.locator("#first-decision")).to_be_focused()

    # Standing in that ask is standing in the space, so the step measures from it.
    pick = page.locator("#reply-decision .lf-pick").first
    pick.focus()
    expect(pick).to_be_focused()
    page.keyboard.press("Shift+a")
    expect(page.locator("#second-decision")).to_be_focused()
    assert errors == []
    page.close()


def test_the_key_line_keeps_local_and_page_hints_and_progressively_reveals_the_rest(
    browser, serve
):
    """The short line is a glance, not the keyboard reference. It keeps the first
    innermost live action and the way out when the current scene has one. One `? more`
    unfolds a bounded shelf of current commands; `? all shortcuts` then opens the
    complete searchable register.

    The panel's general box is the causal contrast for the cap. A full page row crosses
    into the panel and paints over the box; the bounded shortlist ends before it. The
    overlap is tested before opening the reference so a searchable popup cannot make the
    symptom disappear merely by covering both surfaces."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.set_viewport_size({"width": 1200, "height": 800})
    page.get_by_role("button", name=re.compile("^Threads")).click()

    line = page.locator(".lf-shortcut-bar")
    visible_hints = line.locator(".lf-key:not([hidden])")
    assert visible_hints.count() == 2, page.evaluate(
        """() => { const line = document.querySelector('.lf-shortcut-bar'); return {
          client: line.clientWidth, scroll: line.scrollWidth,
          max: getComputedStyle(line).maxWidth,
          hints: [...line.querySelectorAll('.lf-key')].map(el => ({
            text: el.textContent, hidden: el.hidden
          }))
        }; }"""
    )
    assert not page.evaluate(
        """() => {
          const a = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          const b = document.querySelector('.lf-general').getBoundingClientRect();
          return a.left < b.right && a.right > b.left &&
                 a.top < b.bottom && a.bottom > b.top;
        }"""
    ), "the shortcut bar covers the general comment box"

    # Moving into the box changes both contextual hints without introducing a second
    # shortlist: the same scope order the dispatcher uses supplies them, so what the line
    # says is what the innermost live scope answers and not a list kept beside it.
    #
    # Stand on the list directly: the banner button that opened the panel is chrome, and
    # its `c` meaning is deliberately outside this key-line projection test.
    page.locator(".lf-threads").focus()
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(visible_hints.nth(0)).not_to_contain_text("send")
    page.keyboard.press("c")
    expect(visible_hints).to_have_count(2)
    expect(visible_hints.nth(0)).to_contain_text("send")
    expect(visible_hints.nth(1)).to_contain_text("back to threads")

    # The pointer route remains while this text box owns `?`; the key face and
    # accessible shortcut return when pressing the button moves focus out of the box.
    more = page.get_by_role("button", name="More keyboard shortcuts", exact=True)
    expect(more).to_have_attribute("aria-expanded", "false")
    expect(more.locator("kbd")).to_be_hidden()
    expect(more).not_to_have_attribute("aria-keyshortcuts", re.compile(r".+"))
    more.click()
    help_el = page.locator(".lf-shortcut-reference")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(page.locator(".lf-live")).to_contain_text(
        "More keyboard shortcuts shown. Press question mark again for all shortcuts"
    )
    assert visible_hints.count() > 2
    expect(line).to_contain_text("less")
    for width in (1200, 420):
        page.set_viewport_size({"width": width, "height": 800})
        page.evaluate(RENDERED)
        geometry = line.evaluate(
            """node => {
              const visible = [...node.children].filter(el => el.checkVisibility());
              const boxes = visible.map(el => el.getBoundingClientRect());
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              const rows = [];
              for (const el of visible)
                if (rows.every(top => Math.abs(top - el.offsetTop) > tolerance))
                  rows.push(el.offsetTop);
              return {
                rows: rows.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                bandHeight: Math.max(...boxes.map(box => box.bottom))
                          - Math.min(...boxes.map(box => box.top)),
                maxItemHeight: Math.max(...boxes.map(box => box.height)),
              };
            }"""
        )
        assert geometry["rows"] <= 2, geometry
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["bandHeight"] <= geometry["maxItemHeight"] * 2 + 8, geometry
    page.set_viewport_size({"width": 1200, "height": 800})
    page.evaluate(RENDERED)
    more = page.get_by_role("button", name="? all shortcuts", exact=True)
    expect(more).to_have_attribute("aria-expanded", "true")
    more.click()
    expect(help_el).to_be_visible()
    expect(search).to_be_focused()
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_be_visible()
    expect(help_el).not_to_contain_text("With more keyboard shortcuts")

    search.fill("Cancel item selection")
    expect(help_el.locator("tr:not([hidden])")).to_have_count(1)
    expect(help_el.locator("tr:not([hidden])").first).to_contain_text(
        "Cancel item selection"
    )

    search.fill("thread panel")
    expect(
        help_el.get_by_role("heading", name="In the thread panel", exact=True)
    ).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).not_to_have_count(0)

    search.fill("no such shortcut")
    expect(help_el.locator(".lf-shortcut-reference-empty")).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(
        page.get_by_role("button", name="? all shortcuts", exact=True)
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(page.locator(".lf-live")).to_contain_text("Fewer keyboard shortcuts shown")
    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(visible_hints).to_have_count(2)
    assert errors == []
    page.close()


def test_the_resting_key_line_leads_from_the_page_to_target_selection(browser, serve):
    """The sentence a reader reads before they have pressed anything.

    The two Comment routes identify their targets directly. Whole-page search and page
    movement remain in the complete reference.

    Read off `:not([hidden])`, because renderLine leaves every live row in the DOM and
    hides the ones it will not paint: `to_contain_text` on the line answers about the
    register and would pass over a chip nobody can see."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")
    shown = line.locator(".lf-key:not([hidden])")
    expect(shown).to_have_count(2)
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    # One settled read, which pins the count, the order, the keys and the words together.
    assert (
        shortcut_bar_text(page) == "c\ncomment on the page\ns\ncomment on item\n?\nmore"
    ), shortcut_bar_text(page)

    # Search and page movement are still declared but off the glance nobody asked for.
    # React has no row at all until a target makes that capability live.
    for command in ("page.search.open", "page.down"):
        expect(line.locator(f'.lf-key[data-lf-commands~="{command}"]')).to_have_count(1)
        expect(
            line.locator(f'.lf-key:not([hidden])[data-lf-commands~="{command}"]')
        ).to_have_count(0)
    expect(line.locator('[data-lf-commands~="reaction.open"]')).to_have_count(0)

    # And named in full by the reference, which lists every live capability rather than
    # the ones the current width has room for.
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-shortcut-reference")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("Search all the text on the page")
    expect(help_el).to_contain_text("Comment on a visible item by hint")
    expect(help_el).not_to_contain_text("Open reactions")
    expect(help_el).to_contain_text("Move 60% of a page down")
    expect(help_el).to_contain_text("Move 60% of a page up")
    assert errors == []
    page.close()


def test_a_coarse_pointer_gets_only_active_navigation_context(browser, serve):
    """A phone drops both key hints and the active navigation position.

    Neither hidden surface reserves a band at the document's foot."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    try:
        page, errors = open_page(browser, serve(ASKS_PAGE), context=context)
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
            "the touch fixture never reached Leaf's coarse-pointer rules"
        )
        expect(page.locator(".lf-shortcut-bar")).to_be_hidden()
        room = page.evaluate(
            """() => {
              const line = document.querySelector('.lf-shortcut-bar');
              const chrome = document.querySelector('.lf-chrome');
              return {
                display: getComputedStyle(line).display,
                height: line.getBoundingClientRect().height,
                reserved: getComputedStyle(chrome).paddingBottom,
                moreShown: document.querySelector('.lf-key-more').checkVisibility(),
              };
            }"""
        )
        assert room == {
            "display": "none",
            "height": 0,
            "reserved": "0px",
            "moreShown": False,
        }, room

        # And the page is still whole underneath. Everything that asks how far down the
        # page reaches asks it of the line's box, and a line with no box answers 0 — the
        # top of the window — which reads as "all of it is covered". Item hints and the
        # search's own highlight are drawn for boxes above that answer, so a tablet got
        # `s` naming nothing and `/` painting no match, with the page itself intact and
        # nothing on screen saying why.
        page.keyboard.press("s")
        expect(page.locator(".lf-target-hint").first).to_be_visible()
        page.keyboard.press("Escape")

        page.keyboard.press("a")
        line = page.locator(".lf-shortcut-bar")
        expect(line).to_be_hidden()
        position = page.locator(".lf-walk-position")
        expect(position).to_have_text("Ask 1 of 4 open")
        expect(position).to_be_hidden()
        active_room = page.evaluate(
            """() => ({
              height: document.querySelector('.lf-walk-position')
                .getBoundingClientRect().height,
              reserved: parseFloat(getComputedStyle(
                document.querySelector('.lf-chrome')).paddingBottom),
            })"""
        )
        assert active_room["height"] == 0, active_room
        assert active_room["reserved"] == 0, active_room

        page.locator("#h").click()
        expect(line).to_be_hidden()
        assert errors == []
        page.close()
    finally:
        context.close()
    # The control the reading above needs, because `paddingBottom` computes to "0px" on a
    # chrome root syncLayout never wrote to: the same page at the same size under a fine
    # pointer has to reserve a band, or "reserved nothing" and "reserved nowhere" are the
    # same green.
    fine, errors = open_page(browser, serve(NOTED_PAGE))
    resized(fine, 390, 844)
    fine.evaluate(RENDERED)
    reserved = fine.evaluate(
        "() => getComputedStyle(document.querySelector('.lf-chrome')).paddingBottom"
    )
    assert reserved != "0px" and float(reserved.removesuffix("px")) > 20, reserved
    assert errors == []
    fine.close()


FOOT_CONTROL_PAGE = NOTED_PAGE.replace(
    "</main>",
    '<div style="height: 2400px"></div>'
    '<lf-ask id="foot-d"><h2 id="foot-h">The last question</h2>'
    '<lf-options id="foot-o" choose>'
    '<lf-option id="foot-keep">Keep it</lf-option>'
    '<lf-option id="foot-change">Change it</lf-option>'
    "</lf-options></lf-ask></main>",
)

# The band the line stands in, and the room the document keeps for it. `footprint` is the
# whole of what the line takes at the foot of the window — its height plus every inset
# holding it off that foot — and `reserved` is what syncLayout gives up for it.
FOOT_ROOM = """() => {
  const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
  const box = document.getElementById('foot-change').getBoundingClientRect();
  const chrome = document.querySelector('.lf-chrome');
  const s = document.scrollingElement;
  return {
    atEnd: s.scrollTop + s.clientHeight >= s.scrollHeight - 1,
    lineHeight: line.height,
    footprint: document.documentElement.clientHeight - line.top,
    reserved: parseFloat(getComputedStyle(chrome).paddingBottom),
    clearance: line.top - box.bottom,
  };
}"""

# Where the line's chips are, and where its one real control is. The band is the whole
# fixed box; More is the only part of it that answers a press, so a hit test aimed at the
# page has to be aimed past it. Both are read from the rendered boxes rather than stated,
# because the chips' width is the register's answer for the current scene.
UNDER_THE_LINE = """(id) => {
  const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
  const more = document.querySelector('.lf-key-more').getBoundingClientRect();
  const el = document.getElementById(id);
  const box = el.getBoundingClientRect();
  const left = Math.max(line.left, box.left);
  const right = Math.min(more.left, box.right);
  const x = (left + right) / 2;
  const y = line.top + line.height / 2;
  const at = document.elementFromPoint(x, y);
  return {
    band: right - left,
    covered: Math.min(line.bottom, box.bottom) - Math.max(line.top, box.top),
    reaches: Boolean(at) && (el === at || el.contains(at)),
    hit: at ? at.tagName + "." + (at.className || "") : null,
    aim: {x, y}, line: {left: line.left, top: line.top, bottom: line.bottom},
    more: {left: more.left}, box: {left: box.left, right: box.right,
      top: box.top, bottom: box.bottom},
  };
}"""


def test_the_key_line_stands_in_a_band_of_its_own(browser, serve):
    """The line is fixed at the foot of the window, so what it owes the page is a band:
    room of its own where the document ends, and no press taken from what it stands over
    on the way there.

    The room was measured as the line's height alone. Its own 14px inset came out of the
    20px of air that was supposed to be left over, so the document's last line cleared the
    line by five pixels rather than twenty; over a covering sheet, which lifts the line by
    the whole height of the panel's foot, the reservation was short by that lift. The band
    from the line's top to a region's own foot is one measurement and covers every inset.

    The press is the other half. The line and its chips take no pointer events, so a
    control the line stands over on some scroll position is still a control. Its More
    button does take them, and deliberately: it is the only pointer route to the keyboard
    reference. The band is aimed past it here for that reason."""
    page, errors = open_page(browser, serve(FOOT_CONTROL_PAGE))
    control = page.locator("#foot-change")
    expect(control).to_be_visible()

    page.evaluate(
        "() => { const s = document.scrollingElement; s.scrollTo({top: s.scrollHeight}); }"
    )
    page.evaluate(RENDERED)
    ended = page.evaluate(FOOT_ROOM)
    assert ended["atEnd"] and ended["lineHeight"] > 0, ended
    # The band, and the air over it. Reserving the height alone spent 14 of the 20px on
    # the line's own inset and left five, which clears and says nothing about whether the
    # reservation knows what it is reserving for.
    assert ended["reserved"] >= ended["footprint"] + 20, ended
    assert ended["clearance"] >= 20, (
        f"the document's last control ends in the shortcut bar's band: {ended}"
    )

    # A covering sheet lifts the line over the whole of its own foot, and the band grows
    # by that lift. This is where a reservation counting only the line's height parts
    # company with the line: 148px of footprint standing on 51px of reserved room.
    resized(page, 420, 900)
    page.get_by_role("button", name=re.compile("^Threads")).click()
    page.evaluate(RENDERED)
    covered = page.evaluate(FOOT_ROOM)
    # The lift is what this phase is about, so it has to have happened: without it the
    # footprint is the resting one and the reservation below is the resting question again.
    assert covered["footprint"] > ended["footprint"] + 20, (
        f"the sheet never lifted the line, so the reservation is untested here: {covered}"
    )
    assert covered["reserved"] >= covered["footprint"] + 20, (
        f"the sheet lifted the line off a reservation that never heard about it: {covered}"
    )
    page.keyboard.press("Escape")

    # And where the reader is not at the end, the line is standing over the page. The
    # control keeps the press: the chips are painted, not pressable. Narrow, because that
    # is where the chips and the reading column share room at all — at 1200 the column
    # starts to the right of them and it is More that overhangs its first few pixels.
    resized(page, 520, 800)
    page.evaluate(
        """() => {
          const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          const box = document.getElementById('foot-change').getBoundingClientRect();
          scrollBy(0, box.top + box.height / 2 - (line.top + line.height / 2));
        }"""
    )
    page.evaluate(RENDERED)
    under = page.evaluate(UNDER_THE_LINE, "foot-change")
    assert under["band"] > 8 and under["covered"] > 0, (
        f"the aim never reached page under the line's chips, so it proves nothing: {under}"
    )
    assert under["reaches"], (
        f"the shortcut bar took a press aimed at the control underneath it: {under}"
    )

    # More is the exception, and the one that has to stay: it is the pointer route to the
    # reference. Asked as a press rather than as a declaration, the same way the chips
    # above were.
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    assert page.evaluate(
        """() => {
          const more = document.querySelector('.lf-key-more');
          const box = more.getBoundingClientRect();
          const at = document.elementFromPoint(box.left + box.width / 2,
                                               box.top + box.height / 2);
          return more === at || more.contains(at);
        }"""
    ), "the line's own control stopped answering a press"
    assert errors == []
    page.close()


def test_the_expanded_key_line_stands_down_for_a_page_press_and_another_command(
    browser, serve
):
    """The shelf is transient help, so either kind of onward motion folds it. The
    page-click owner handles presses outside the line, while the dispatcher folds it
    before a registered command runs."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.locator("#t").click()
    expect(line).to_have_attribute("data-lf-expanded", "false")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.keyboard.press("g")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(line.locator('kbd[data-lf-key-state="pressed"]').first).to_have_text("g")
    assert errors == []
    page.close()


def test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted(browser, serve):
    """A frame passes between one Tab and the next for every reader, and none for a test.

    `renderLine` runs under `paintHere`'s frame, so it repaints the shortcut bar just after
    focus lands somewhere — including on More, the line's own button. Clearing the line
    with `textContent = ""` took More out of the document, and removing a focused element
    blurs it; it came straight back as the same node, connected, with the reader dropped
    to `body`. The button was never gone to look at and never gone from the DOM to assert
    on, so nothing but standing on it one frame later could see it.

    That is why the frame is the whole of this test. Pressed back to back the walk is
    whole, because the repaint has not run yet between the presses — the failure hid
    behind the one habit every browser test has. So each press waits two frames, and the
    contrast is against the same walk pressed fast: they have to agree.

    Reaching More is the claim, and going on past it is the other half — a walk that
    loses focus to `body` does not stop, it silently restarts, and a reader tabbing
    through their own page never gets past the banner."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    who = """() => {
      let e = document.activeElement;
      while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
      return e === document.body ? 'body' : (e?.className || e?.tagName || 'null');
    }"""

    walks = {}
    for settled in (False, True):
        # Start each walk from the page rather than from the last control in the
        # previous walk. Blurring preserves that control as the sequential focus
        # starting point, which only happened to wrap before the page gained a visual
        # reaction proxy as its first Tab stop.
        page.evaluate("() => document.body.focus()")
        trail = []
        for _ in range(24):
            page.keyboard.press("Tab")
            if settled:
                page.evaluate(RENDERED)
            trail.append(page.evaluate(who))
        walks["frame" if settled else "fast"] = trail

    # The two walks have to be the same walk. A count of lost stops would need a
    # threshold, and there is no honest one: this page's order is three controls and a
    # wrap, so a `body` every fourth press is the walk working. What says focus was lost
    # is that waiting changed where the presses went.
    assert walks["fast"] == walks["frame"], (
        "a frame between presses changed the tab order:\n"
        f"  fast  {walks['fast']}\n  frame {walks['frame']}"
    )
    for how, trail in walks.items():
        assert any("lf-key-more" in at for at in trail), (
            f"tabbing {how}, the walk never stood on More in 24 presses: {trail}"
        )

    # Standing on More, the repaint must leave the reader on it.
    page.evaluate("() => document.activeElement?.blur()")
    for _ in range(24):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.classList?.contains('lf-key-more')"
        ):
            break
    expect(page.locator(".lf-key-more")).to_be_focused()
    page.evaluate(RENDERED)
    expect(page.locator(".lf-key-more")).to_be_focused()

    assert errors == []
    page.close()


def test_a_page_at_rest_repaints_the_key_line_only_when_the_state_moves(browser, serve):
    """A repaint that schedules the next one is a loop no surface reports.

    `paintCoreControls` runs inside `paintHere` and writes what the More control
    currently says, `aria-expanded` among it. The runtime watches `open` and
    `aria-expanded` over the whole document, because those two attributes are how both
    spellings of a disclosure keep which way they stand, and it repaints the line for
    either. So the paint delivered its own write back to itself and asked for another
    frame, and the page went on repainting for as long as it was open — every browser
    test on every page paying for it, which is where it showed: the nightly suite ran
    half again as long and the run went over its bound with a fifth of the tests unread.

    Nothing on screen says so, which is why the reading is the page's own frames against
    its own state applications. Every application repaints the line and says so through
    `lf-actions`, the heartbeat's re-application of state the page already holds
    included, so a line that repaints more often than the state moves is repainting for
    a reason the page has not got."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.evaluate(
        """() => {
          const probe = { frames: 0, paints: 0, applied: 0 };
          window.__lfProbe = probe;
          document.addEventListener("lf-actions", () => { probe.applied += 1; });
          new MutationObserver(() => { probe.paints += 1; }).observe(
            document.querySelector(".lf-shortcut-bar"),
            { attributes: true, childList: true, subtree: true },
          );
          const tick = () => { probe.frames += 1; requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
    )
    # The window is the page's own frames rather than a duration: a loop of this shape
    # repaints once per frame whatever the machine's speed, so counting frames is what
    # makes the contrast the same size on a loaded runner as on a desk.
    page.wait_for_function("() => window.__lfProbe.frames >= 90")
    probe = page.evaluate("() => window.__lfProbe")

    assert probe["paints"] <= probe["applied"] + 1, (
        "the shortcut bar repainted without the state moving over "
        f"{probe['frames']} frames: {probe}"
    )
    assert errors == []
    page.close()


def test_escape_backs_out_from_a_control_nothing_is_typed_into(browser, serve):
    """A scope takes the keys it uses, so a control that has no Escape of its own
    leaves the rung standing behind it. The banner's version chooser swallowed it,
    so the panel could not be closed by key right after the user worked it; the
    fix's first attempt was a two-item denylist, which an authored slider walked
    straight past. The chooser is a button now, so what holds the rule is the
    page's own controls — which is where it always mattered, a page being free to
    author any of them.

    A slider and a select answer here for the two sides of the claim. The slider
    types nothing, so the typing scope never stands over it at all; the select's
    letters jump its options, so it stands and takes them — and takes only them,
    which is what leaves this press to the page. Reaching the rung used to be a
    branch inside the typing scope's own row, restating another scope's word.

    Which rung the press reaches is the ladder's own business, and it unwinds from
    where the reader is: standing out on the page, the first thing they are in is
    the control they are standing on, and the panel behind them is a layer they are
    not in. So the press takes two — and the panel closing on the second is the
    whole of what this test is about, the control having had every chance to
    swallow the first."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<input id="zoom" type="range">'
        '<select id="pick"><option>one</option><option>two</option></select></main>',
    )
    page, errors = open_page(browser, serve(html))
    # The mouse opens between rounds because c is the select's own letter, and the
    # press has to be made the same way on both to be comparing anything.
    for control in ("#zoom", "#pick"):
        page.get_by_role("button", name=re.compile("^Threads")).click()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.locator(control).focus()
        expect(page.locator(".lf-shortcut-bar")).to_contain_text("let go")
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")
        expect(page.locator(".lf-shortcut-bar")).to_contain_text("close threads")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_control_that_types_nothing_keeps_the_pages_keyboard(browser, serve):
    """A scope claims the keys it uses and leaves the rest standing. This one used to
    claim the lot: the typing scope stood wherever focus was in a form control, on the
    reading that a letter is a keystroke there — true of a text box, false of a radio, a
    checkbox and a slider, none of which the platform ever hands a letter. So a reader
    standing on a screenshot's before/after switch lost c, the walks, the version keys and
    the reference itself, and the line went blank rather than wrong, which is how it
    reaches its author as "the keyboard stopped working".

    One key had already been rescued from that swallow by hand, in a branch inside the
    typing scope's own row. Every other key it took stayed taken, and that is what says the
    swallow was the wrong shape rather than one key short.

    The claim has to hold in both directions or it has bought nothing, so the control's
    own key is asserted beside the page's: a page whose keyboard stands over a radio must
    not be taking Space off it. The permanent More control is part of that same projection:
    it keeps its pointer route in a text box but cannot show or expose `?` when that press
    types into the box."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<label><input id="flip" type="radio" name="frame"> after</label>'
        '<input id="note" type="text"></main>',
    )
    page, errors = open_page(browser, serve(html))
    line = page.locator(".lf-shortcut-bar")
    # Two page rows, because the claim is the whole keyboard rather than one key: `c` is
    # painted at rest, and the movement row is one `?` further in. A scope that swallowed
    # the page would take both, and the box below is where both go.
    comment = line.locator('.lf-key:not([hidden])[data-lf-commands~="comment.create"]')
    movement = line.locator('.lf-key:not([hidden])[data-lf-commands~="page.down"]')

    page.locator("#flip").focus()
    expect(comment).to_have_count(1)
    page.keyboard.press("?")
    expect(movement).to_have_count(1)
    expect(movement).to_have_attribute("data-lf-commands", re.compile(r"\bpage\.up\b"))
    page.keyboard.press("Escape")
    expect(page.locator("#flip")).to_be_focused()
    page.keyboard.press("Space")
    expect(page.locator("#flip")).to_be_checked()
    # The letter reaches the page, which is the whole claim; where it then goes is the
    # standing's business — a reader on the radio is standing on it, so the box that
    # opens is about it rather than about the page. Named in full, because "comment on
    # the" matches every destination this key has and would assert nothing about which.
    expect(line).to_contain_text("comment on the control")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("flip")
    page.keyboard.press("Escape")
    expect(page.locator("#flip")).to_be_focused()

    # The box beside it, where every one of those letters is the reader's. The line
    # names none of them, which is the same register saying so.
    page.locator("#note").focus()
    expect(comment).to_have_count(0)
    expect(movement).to_have_count(0)
    more = line.locator(".lf-key-more")
    expect(more.locator("kbd")).to_be_hidden()
    expect(more).to_have_attribute("aria-label", "More keyboard shortcuts")
    expect(more).not_to_have_attribute("aria-keyshortcuts", re.compile(r".+"))
    page.keyboard.press("c")
    expect(page.locator("#note")).to_have_value("c")
    expect(page.locator(".lf-shortcut-reference")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator("#note")).to_have_value("c?")
    expect(page.locator(".lf-shortcut-reference")).to_be_hidden()

    page.evaluate("() => document.body.focus()")
    expect(more.locator("kbd")).to_be_visible()
    expect(more).to_have_attribute("aria-label", "? more")
    expect(more).to_have_attribute("aria-keyshortcuts", "?")
    assert errors == []
    page.close()


def test_a_label_press_keeps_the_controls_keyboard_standing(browser, serve):
    """Leaf treats a label's native activation as one keyboard standing.

    Chromium moves focus through body between mousedown and native label activation.
    That intermediate state must not repaint focus-derived surfaces. The native click
    and text selection must still work."""
    html = leaf_page(
        "label focus",
        """
<h1 id="frames">Choose a frame</h1>
<lf-ask id="first-question-decision"><h2>Which first frame?</h2>
<lf-options id="first-question" choose>
  <lf-option id="first-frame"><strong>First</strong>
    <label><input id="first" type="radio" name="first-frame">
      <span>first state</span></label>
  </lf-option>
  <lf-option id="neither-first-frame"><strong>Neither</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="frame-question-decision"><h2>Which next frame?</h2>
<lf-options id="frame-question" choose>
  <lf-option id="after-frame"><strong>After</strong>
    <label id="frame-label"><input id="frame" type="radio" name="frame">
      <span>after state</span></label>
  </lf-option>
  <lf-option id="before-frame"><strong>Before</strong></lf-option>
</lf-options></lf-ask>
""",
    )
    page, errors = open_page(
        browser, serve(html, anchored=[("frames", "Choose a frame")])
    )
    first = page.locator("#first")
    control = page.locator("#frame")
    words = page.locator("#frame-label span")
    first.focus()
    standing = shortcut_bar_text(page)
    assert "let go" in standing
    expect(page.locator("#first-question-decision[data-lf-ask]")).to_have_count(1)

    # A secondary contact does not drive native label activation, so it must not
    # start the logical transaction either.
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 98,
                        pointerType: 'touch', isPrimary: false, button: 0};
          document.querySelector('#frame-label').dispatchEvent(
            new PointerEvent('pointerdown', init)
          );
          document.activeElement.blur();
        }"""
    )
    assert "let go" not in shortcut_bar_text(page)
    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointerup', {
          bubbles: true, composed: true, pointerId: 98,
          pointerType: 'touch', isPrimary: false, button: 0
        }))"""
    )
    first.focus()
    assert shortcut_bar_text(page) == standing

    bounds = words.bounding_box()
    assert bounds is not None
    middle = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 99,
                        pointerType: 'touch', isPrimary: true, button: 0};
          document.body.dispatchEvent(new PointerEvent('pointerdown', init));
          dispatchEvent(new PointerEvent('pointerup', init));
        }"""
    )
    assert shortcut_bar_text(page) == standing
    held_ask = page.locator("#first-question-decision[data-lf-ask]")
    expect(held_ask).to_have_count(1)
    expect(held_ask).to_have_css("--lf-here-ring", "ask")
    page.mouse.up()
    expect(control).to_be_checked()
    expect(control).to_be_focused()
    expect(page.locator("#frame-question-decision[data-lf-ask]")).to_have_count(1)

    # The press has its own frame and the drag comes after it, so the line's only route
    # to the word is the selection the drag makes: the reader is taking words out of a
    # label, and from the first glyph Escape clears that selection rather than letting
    # go of the control. Framed the other way round the press's frame painted the line
    # after the drag had already run, and the word arrived whether or not anything
    # followed the selection.
    hold_selection(
        page,
        (bounds["x"] + 2, middle[1]),
        (bounds["x"] + bounds["width"] - 2, middle[1]),
        steps=10,
        frame_the_press=True,
    )
    assert "after state" in page.evaluate("() => getSelection().toString()")
    assert "unselect" in shortcut_bar_text(page)
    page.mouse.up()
    assert "let go" not in shortcut_bar_text(page)

    # A focused thread has a runtime-owned scope outside the generic control register.
    # It reads the same logical focus while the press moves toward the label's control.
    page.evaluate("() => getSelection().removeAllRanges()")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    resting_thread = thread.evaluate(
        "thread => { const s = getComputedStyle(thread); return {"
        "background: s.backgroundColor}; }"
    )
    thread.focus()
    thread_standing = shortcut_bar_text(page)
    assert "reply" in thread_standing
    bounds = words.bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.down()
    assert shortcut_bar_text(page) == thread_standing
    current_thread = thread.evaluate(
        "thread => { const s = getComputedStyle(thread); return {"
        "background: s.backgroundColor, outline: s.outlineStyle}; }"
    )
    assert current_thread["outline"] == "none"
    assert current_thread["background"] != resting_thread["background"]
    page.mouse.up()
    assert "reply" not in shortcut_bar_text(page)
    assert errors == []
    page.close()


def test_reactionless_other_responses_can_turn_the_compact_field_into_a_suggestion(
    browser, serve
):
    """A reactionless layer keeps Suggest in the compact response fallback."""
    registry = json.loads(
        (ROOT / "skills/leaf/packages/default/registry.json").read_text()
    )
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page, errors = open_page(
        browser,
        serve(INLINE_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )
    page.locator("#p").click(click_count=3)
    box = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(box).not_to_be_focused()
    expect(box).to_have_attribute("placeholder", "Comment… · c")
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", "Comment on the page"
    )
    page.keyboard.press("c")
    expect(box).to_be_focused()
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Comment… .*(⌘⏎|Ctrl\+⏎)$")
    )
    send = page.locator(".lf-composer > .lf-compose-field > button")
    expect(send.locator('svg[data-lf-icon="send"]')).to_have_count(1)
    expect(page.locator(".lf-composer-row")).to_have_count(0)
    field_box = box.bounding_box()
    send_box = send.bounding_box()
    assert (
        field_box["x"]
        < send_box["x"]
        < send_box["x"] + send_box["width"]
        < (field_box["x"] + field_box["width"])
    )
    assert (
        field_box["y"]
        < send_box["y"]
        < send_box["y"] + send_box["height"]
        < (field_box["y"] + field_box["height"])
    )
    expect(send).to_have_attribute("title", re.compile(r"^Comment \((⌘⏎|Ctrl\+⏎)\)$"))

    page.keyboard.press("Tab")
    choices = page.locator(".lf-fab-bar")
    suggest = choices.locator(".lf-fab-suggest")
    expect(choices).to_be_visible()
    expect(suggest).to_be_focused()

    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Replacement text .*(⌘⏎|Ctrl\+⏎)$")
    )
    expect(send).to_have_attribute("title", re.compile(r"^Suggest \((⌘⏎|Ctrl\+⏎)\)$"))
    expect(box).to_have_value(
        re.compile("A paragraph carrying bold text and emphasis inside it")
    )
    page.evaluate(RENDERED)
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Replacement text .*(⌘⏎|Ctrl\+⏎)$")
    )
    assert errors == []
    page.close()


def test_a_passage_selection_keeps_native_copy_and_context_menu(browser, serve):
    """Leaf may offer a response without taking the browser's selection gestures."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    try:
        page, errors = open_page(browser, serve(INLINE_PAGE), context=context)
        paragraph = page.locator("#p")
        paragraph.click(click_count=3)
        expect(page.locator(".lf-fab-bar")).to_be_visible()

        selected = page.evaluate("() => getSelection().toString()")
        assert "A paragraph carrying" in selected
        is_mac = page.evaluate(
            "() => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)"
        )
        page.keyboard.press("Meta+c" if is_mac else "Control+c")
        assert page.evaluate("() => navigator.clipboard.readText()") == selected

        page.evaluate(
            """() => {
              window.lfContextMenu = null;
              document.addEventListener('contextmenu', event => {
                setTimeout(() => {
                  window.lfContextMenu = {
                    prevented: event.defaultPrevented,
                    selection: getSelection().toString(),
                  };
                });
              }, {capture: true, once: true});
            }"""
        )
        paragraph.click(button="right")
        page.wait_for_function("() => window.lfContextMenu !== null")
        assert page.evaluate("() => window.lfContextMenu") == {
            "prevented": False,
            "selection": selected,
        }
        assert errors == []
        page.close()
    finally:
        context.close()


def test_focus_paint_releases_every_text_box_crossed_before_a_frame(browser, serve):
    """A synchronous input sync cannot hide an intermediate focus from repaint."""
    page, errors = open_page(browser, serve(INLINE_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    general = page.locator(".lf-general textarea")
    replies = page.locator(".lf-thread textarea")
    assert general.get_attribute("placeholder") == "Comment on the page · c"
    page.locator(".lf-find-box").focus()
    shortcut_bar_text(page)
    assert general.get_attribute("placeholder") == "Comment on the page"
    general.focus()
    shortcut_bar_text(page)
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", general.get_attribute("placeholder"))
    assert general.get_attribute("aria-label") == "Comment on the page"

    # Cross A -> B (and sync B) -> C in one turn, before the coalesced focus paint.
    replies.evaluate_all(
        """boxes => {
          boxes[0].focus();
          boxes[0].dispatchEvent(new Event('input', {bubbles: true}));
          boxes[1].focus();
        }"""
    )
    shortcut_bar_text(page)
    assert general.get_attribute("placeholder") == "Comment on the page"
    assert general.get_attribute("aria-label") == "Comment on the page"
    assert replies.nth(0).get_attribute("placeholder") == "Reply"
    assert replies.nth(0).get_attribute("aria-label") == "Reply"
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", replies.nth(1).get_attribute("placeholder"))
    assert replies.nth(1).get_attribute("aria-label") == "Reply"

    replies.nth(1).evaluate(
        "box => box.closest('.lf-thread, .lf-conversation-thread').focus()"
    )
    shortcut_bar_text(page)
    assert replies.nth(1).get_attribute("placeholder") == "Reply · c"
    page.keyboard.press("c")
    expect(replies.nth(1)).to_be_focused()
    shortcut_bar_text(page)
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", replies.nth(1).get_attribute("placeholder"))
    assert errors == []
    page.close()


def test_the_key_line_names_the_selected_comment_and_its_other_responses(
    browser, serve
):
    """Comment enters a selected passage's field; the line names send and Tab exit."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    line = page.locator(".lf-shortcut-bar")
    help_el = page.locator(".lf-shortcut-reference")

    # Nothing in hand: c names and enters the page comment directly.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the page")
    page.keyboard.press("Escape")

    # A real selection keeps the browser selection until Comment explicitly enters its
    # field. Once there, letters and `?` belong to the comment rather than falling through
    # to page shortcuts.
    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    expect(line).to_contain_text("comment")
    expect(line).to_contain_text("other responses")
    page.keyboard.type("?")
    expect(field).to_have_value("?")
    page.keyboard.press("Escape")

    # An explicit visual target follows the same contract, but its accessible field name
    # identifies the item rather than a quoted passage.
    page.locator("#fig svg").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-label", re.compile("figure"))
    expect(line).to_contain_text("other responses")
    page.keyboard.press("Escape")

    assert errors == []
    page.close()


def test_typing_in_a_selected_comment_wins_over_page_shortcuts(browser, serve):
    """Once Comment focuses a selected passage's field, shortcut letters are text."""
    url = serve(TARGETS_PAGE)
    _publish(serve.page_dir, 2, TARGETS_PAGE, "two")
    page, errors = open_page(browser, url)

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    fab = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(fab).not_to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_have_value("c")
    page.keyboard.press("Escape")
    page.evaluate("() => document.body.focus()")

    version = page.locator(".lf-version")
    version.evaluate(
        """control => control.addEventListener('click', () => {
          control.dataset.shortcutClicks =
            String(Number(control.dataset.shortcutClicks || 0) + 1);
        })"""
    )
    open_versions(page)
    expect(page.locator(".lf-version-menu")).to_be_visible()
    expect(version).to_have_attribute("data-shortcut-clicks", "1")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-shortcut-reference")
    close = page.locator(".lf-shortcut-reference-close")
    expect(reference).to_be_visible()
    close.evaluate(
        """control => control.addEventListener('click', () => {
          control.dataset.shortcutClicks =
            String(Number(control.dataset.shortcutClicks || 0) + 1);
        })"""
    )
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(close).to_have_attribute("data-shortcut-clicks", "1")

    assert errors == []
    page.close()


def test_submit_shortcuts_activate_the_controls_that_promise_the_action(browser, serve):
    """Every durable editor inserts a newline with Enter and sends with Mod+Enter."""
    html = TARGETS_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    page, errors = open_page(browser, serve(html))

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    composer = page.locator(".lf-composer")
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    send = composer.locator(".lf-compose-field .primary")
    send.evaluate(
        """control => control.addEventListener('click', () => {
          document.body.dataset.composerShortcutClicks =
            String(Number(document.body.dataset.composerShortcutClicks || 0) + 1);
        })"""
    )
    field.fill("Send through the compact control.")
    page.keyboard.press("Enter")
    assert page.locator("body").get_attribute("data-composer-shortcut-clicks") is None
    expect(field).to_have_value("Send through the compact control.\n")
    expect(field).to_have_attribute("aria-keyshortcuts", "Meta+Enter Control+Enter")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("body")).to_have_attribute("data-composer-shortcut-clicks", "1")
    expect(composer).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    controls = page.locator(".lf-draft-controls[data-lf-for='plan']")
    controls.get_by_role("button", name="Edit").click()
    editor = page.locator("#plan textarea")
    editor.fill("Save through the visible control.")
    save = controls.get_by_role("button", name="Save")
    save.evaluate(
        """control => control.addEventListener('click', () => {
          document.body.dataset.draftShortcutClicks =
            String(Number(document.body.dataset.draftShortcutClicks || 0) + 1);
        })"""
    )
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("body")).to_have_attribute("data-draft-shortcut-clicks", "1")
    expect(page.locator("#plan .lf-draft-body")).to_have_text(
        "Save through the visible control."
    )

    round_trip(page)
    assert errors == []
    page.close()


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every surface naming a key promises the press does something now. One table
    kept the words from drifting and not the surfaces: the shortcut bar asked `when`,
    the ? overlay didn't, and a shortcut could hold its liveness where no surface
    could ask — inside its own run — so the overlay offered g 1–9 with no thread to
    reply to, and named a walk through a list of one. Liveness is one declaration,
    and the dispatcher, the line, and the overlay all ask it. The sequence's lists are
    where that division earns its keep twice over: a list the page hasn't got is a
    row the reference must not name, and the section holds only what this page can
    answer — the edges always among them, every page having a top. Its rows carry the
    complete sequence, so no heading has to supply a key the row itself omits."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    help_el = page.locator(".lf-shortcut-reference")

    # No open threads, one version: the reference names only what a press would do.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    # Nothing is selected and the reader is standing nowhere, so c's own row names the
    # page comment it enters. Threads navigation remains the separate g T command.
    expect(help_el).to_contain_text("Comment on the page")
    # The sequence's section stands on every page — the edges need no list — but holds
    # no row for a list this page hasn't got. Each row says the whole press from the
    # standing page rather than asking its heading to supply the first g.
    expect(help_el.get_by_role("heading", name="Go to", exact=True)).to_be_visible()
    expect(
        help_el.locator("tr", has_text="top of the page").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "g"])
    expect(
        help_el.locator("tr", has_text="bottom of the page").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "G"])
    expect(
        help_el.locator("tr", has_text="bottom of the page").locator(".lf-key-sequence")
    ).to_have_attribute("aria-label", "g then Shift+g")
    expect(help_el.locator('tr[data-lf-command="version.open"]')).to_have_count(0)
    sequence_control = help_el.locator('tr[data-lf-command="navigation.address.back"]')
    expect(sequence_control).to_have_class(re.compile(r"\blf-sequence-control\b"))
    expect(sequence_control.locator("td").first).to_have_css(
        "border-top-style", "solid"
    )
    expect(help_el).not_to_contain_text("open comment's reply box")
    # And no link scope: this page holds none, while the machine's own tray is full of
    # them — a scope asked about the document at large was had by every page there is.
    expect(help_el).not_to_contain_text("On a link")
    expect(help_el).not_to_contain_text("Next open thread")
    expect(help_el).not_to_contain_text("Previous open thread")
    expect(help_el).not_to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("waiting on you for")
    # A first version is passive orientation, so neither a chooser nor a walk is offered.
    expect(help_el).not_to_contain_text("The versions, and what each one changed")
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()

    # The dispatcher asks the same declaration: neither half of the pair runs while
    # there is no thread to walk.
    page.keyboard.press("t")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_hidden()
    line = page.locator(".lf-shortcut-bar")
    expect(line).not_to_contain_text("t / T")

    # Threads arrive, making both the category walk and the Threads panel useful.
    for text in ["A thread.", "Another."]:
        events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    # The shortcut bar repaints on the same render that made them live — no focus
    # change to lean on, so the repaint is the thread render's own.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    expect(
        help_el.locator("tr", has_text="Go to the Threads panel").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "T"])
    expect(
        help_el.locator("tr", has_text="Go to the Threads panel").locator(
            ".lf-key-sequence"
        )
    ).to_have_attribute("aria-label", "g then Shift+t")
    expect(help_el).not_to_contain_text("link on screen")
    expect(help_el).not_to_contain_text("waiting on you for")
    expect(help_el).to_contain_text("Next open thread")
    expect(help_el).to_contain_text("Previous open thread")
    expect(
        help_el.locator("tr", has_text="Next open thread").locator("kbd")
    ).to_have_text("t")
    expect(
        help_el.locator("tr", has_text="Previous open thread").locator("kbd")
    ).to_have_text("T")
    expect(help_el).to_contain_text("On a focused thread")
    # Still one version, so neither the chooser nor its walk is advertised.
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A v2 lands and the live page follows it; on v2 the menu's own keys are
    # live, having a list to walk and a base to walk onto.
    (d / ".fixture-versions" / "v2.html").write_text(NOTED_PAGE)
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_count(1)
    expect(page.locator(".lf-version-menu")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Enter Space v"
    )
    page.keyboard.press("?")
    expect(help_el).to_contain_text("In the versions menu")
    expect(help_el).to_contain_text("Previous version")
    expect(help_el).to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A resolved thread stays focusable after the last open one is gone, and the
    # scene branch that restates the t/T row over it asks the same liveness.
    page.keyboard.press("c")
    for n in [1, 2]:
        page.locator(".lf-threads > .lf-thread:not([hidden])").first.get_by_role(
            "button", name="Resolve"
        ).click()
        expect(page.locator('[data-filter-value="resolved"]')).to_have_text(
            f"Resolved ({n})"
        )
    page.locator('[data-filter-value="resolved"]').click()
    expect(
        page.locator('.lf-thread[data-resolved="true"]:not([hidden])')
    ).to_have_count(2)
    resolved = page.locator('.lf-thread[data-resolved="true"]:not([hidden])').first
    resolved.focus()
    expect(resolved).to_be_focused()
    expect(line).to_contain_text("show all")
    expect(line).to_contain_text("t / T")

    # The state is an ordinary panel filter, with no disclosure scope added beside it.
    expect(page.locator(".lf-details")).to_have_count(0)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("On a disclosure")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_resolution_uses_its_control_while_x_remains_a_close_symbol(browser, serve):
    """A focused thread does not overload the close symbol as a resolution key.

    Resolve and Reopen remain keyboard actions through their controls. Enter on a
    focused open thread still reaches its reply box."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-shortcut-bar")

    def tab_to(target, limit=40):
        for _ in range(limit):
            page.keyboard.press("Tab")
            if target.evaluate("node => node === document.activeElement"):
                return
        raise AssertionError("Tab did not reach the expected control")

    # The thread scope does not advertise Resolve before or after focus. Its visible
    # control owns the keyboard route.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).to_contain_text(
        "On a focused thread"
    )
    focused_section = page.locator(".lf-shortcut-reference-section").filter(
        has=page.get_by_role("heading", name="On a focused thread", exact=True)
    )
    expect(focused_section.get_by_text("Resolve it", exact=True)).to_have_count(0)
    page.keyboard.press("Escape")

    # x leaves the focused thread open. Tab and Enter on the visible control resolve it,
    # with the button's existing landing taking focus to the next thread.
    page.keyboard.press("t")
    first = page.locator(f'.lf-thread[data-id="{c1}"]')
    expect(first).to_be_focused()
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("x")
    expect(first).to_be_visible()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    resolve_control = first.get_by_role("button", name="Resolve thread", exact=True)
    tab_to(resolve_control)
    expect(resolve_control).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("x")
    expect(first).to_be_visible()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # The Resolved state and Reopen control put a settled thread in the ordinary Tab
    # journey. Enter performs the control's named action.
    page.locator('[data-filter-value="resolved"]').click()
    resolved = page.locator(f'.lf-thread[data-id="{c1}"]:not([hidden])')
    reopen_control = resolved.get_by_role("button", name="Reopen")
    tab_to(reopen_control)
    expect(reopen_control).to_be_focused()
    expect(line).to_contain_text("reopen")
    page.keyboard.press("Enter")
    round_trip(page)
    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    expect(reopened.locator(":scope > .lf-compose textarea")).to_be_focused()
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(reopened).to_be_focused()
    expect(line).to_contain_text("reply")

    assert errors == []
    page.close()


def test_escape_on_a_declaring_control_does_exactly_what_it_says(browser, serve):
    """One press is one action: the rung is the innermost scope in reach that binds
    Escape, and the dispatcher runs that one and no other. The draft editor's Esc used
    to be two — the edit cancelled and the runtime's ladder closed the panel behind it
    — and the cancel discarded the user's words against the never-lose-text norm. Each
    control kept that by hand once and the stack keeps it now, so this is the test that
    says the structure holds. The editor closes keeping the edit, the panel stands, and
    a grabbed card's Esc cancels the move and nothing else."""
    html = BOARD_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    url = serve(html)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A thread."},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    page.keyboard.press("c")  # panel open, so the old second action would show
    expect(page.locator(".lf-panel")).to_be_visible()

    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    ta = page.locator("lf-draft textarea")
    expect(ta).to_be_focused()
    ta.fill("Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator(".lf-panel")).to_be_visible()  # …and only the editor
    # The edit was set aside, not discarded: reopening resumes it.
    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    expect(page.locator("lf-draft textarea")).to_have_value("Ship it — but louder.")
    page.keyboard.press("Escape")

    # A grabbed card: Esc cancels the move, and the panel it would have closed stands.
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("cancel the move")
    # The contract's flip side: the sequence refuses to arm over a control that has
    # claimed Escape, or one press would have two owners — the grip consuming it,
    # the sequence promising its cancel.
    page.keyboard.press("g")
    # No blue pressed key appears, which proves the sequence refused to arm even if the
    # ordinary line happens to reuse one of its words.
    expect(
        page.locator('.lf-shortcut-bar kbd[data-lf-key-state="pressed"]')
    ).to_have_count(0)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("cancel the move")
    page.keyboard.press("Escape")
    # The grab is over (an uncancelled one would also leave the card in Todo),
    # the line is back to the resting grip, and the panel the ladder would have
    # closed stands.
    expect(page.locator(".lf-lift")).to_have_count(0)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("grab the card")
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator(".lf-panel")).to_be_visible()
    assert errors == []
    page.close()


def test_c_comments_on_what_the_reader_is_standing_in(browser, serve):
    """Focus supplies an element anchor. `c` once read the 💬 alone, so a reader
    working from the keys had two destinations where explicit pointer targeting had
    three: an item, a quote, or the whole page. A
    focused link put them on an option and the box that opened still said "Comment on the
    page" — the ⌥ aim's "the item under the pointer" with no twin for the cursor.

    Where they are standing is the unanswered decision first, because that is what the page
    has already told them: markHere rings the whole ask when a/A lands on its control.
    Below a decision it is the innermost item, which is the aim's own reading — so a focused
    link speaks for the paragraph holding it, no id of its own being what an anchor needs.

    One box either way: `commentOnTarget` writes `{section: item.id}`, which is the anchor a
    widget's own conversation seat collects, so a remark made here lands in that seat's
    conversation rather than beside it. Reaching for the seat directly instead was five
    questions — escaping an author's id, whether the box can take focus, which box when
    the seat holds several, what design mode files, where the reader already stood — for
    a focus landing.

    The control is the same press from the same page with the reader standing nowhere in
    it, where `c` opens the page-comment box rather than this item's composer. Without it a
    green here would follow just as well from a composer that opened on everything.

    Focus is dropped between the phases rather than backed out of, because each press
    lands the reader in a box and the typing scope owns the letter there."""
    page, errors = open_page(browser, serve(WHERE_I_STAND_PAGE))
    line = page.locator(".lf-shortcut-bar")

    def drop():
        if (
            page.locator(".lf-composer[data-lf-open]").count()
            or page.locator(".lf-general textarea:focus").count()
        ):
            page.keyboard.press("Escape")
        page.evaluate("() => document.activeElement?.blur()")

    # Standing nowhere in the page: the page itself is the contextual target.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    drop()

    # A decision: the composer opens on the question rather than on the option the
    # walk happens to stand the reader on, and rather than on the page.
    page.keyboard.press("a")
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the ask")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("ask")
    drop()

    # A settled group: not a decision at all, and the conversation seat it still holds is
    # inside `hidden="until-found"`, so a press that reached into the seat focused a box
    # that cannot take focus and did nothing at all. Named by its own words rather than by
    # "options", which the composer standing open from the phase above already says — an
    # assertion true before the press is no assertion about the press.
    page.locator("#settled .lf-settled").focus()
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("Decided last week")
    drop()

    # A decision with no seat: focus on its action names the rewrite, and the composer
    # anchors there rather than on the page.
    page.evaluate(RENDERED)
    rewrite_action = page.locator('[data-lf-margin-for="sug-window"] .lf-sug-accept')
    rewrite_action.focus()
    expect(rewrite_action).to_be_focused()
    expect(page.locator("#sug-window")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the rewrite")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("rewrite")
    drop()

    # A link inside a question, open and settled: the same markup, and the same answer.
    # Standing in a decision is not working one — a reader who focused a link has named
    # something more particular than the question around it, and answering the question
    # there both overrode what they named and made the reply turn on whether that question
    # happened to be open. The settled one is the contrast that shows it was the openness
    # doing it: it always said "option", and the open one used to say "options".
    for expected_id in ("sh-steel", "st-keep"):
        drop()
        page.evaluate(RENDERED)
        if expected_id == "st-keep":
            settled = page.locator("#settled .lf-settled")
            settled.click()
            expect(settled).to_have_attribute("aria-expanded", "true")
        link = page.locator(f"#{expected_id} a")
        link.focus()
        expect(link).to_be_focused()
        expect(line).to_contain_text("comment on the option")
        page.keyboard.press("c")
        expect(page.locator(".lf-composer")).to_be_visible()
        assert page.evaluate(
            "() => document.querySelector('.lf-composer blockquote')?.textContent ?? ''"
        ).startswith("§ option · "), "the box named the question, not the option"
        drop()

    # Below any ask, the innermost item: the paragraph the focused link sits in.
    page.evaluate(RENDERED)
    passage_link = page.locator("#p1 a")
    passage_link.focus()
    expect(passage_link).to_be_focused()
    expect(line).to_contain_text("comment on the paragraph")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("paragraph")

    assert errors == []
    page.close()


def test_the_ring_holds_on_a_seat_the_agent_has_still_to_answer(browser, serve):
    """Where the reader is standing and what the reader still owes are two facts, and a
    widget mid-conversation with the agent is where they part. Its seat holds the words
    the reader just wrote, its answer is unmade and its controls are live, and it has left
    the banner and the tray because the next word there is the agent's — but the reader
    is standing in it all the same, and it is still the question they are working.

    Read off the reader's list, both the ring and `c` went with the count: the moment the
    remark was sent the ring left from under the reader, and `c` fell through from the
    question to whichever item their focus happened to rest in. That is a different
    conversation, not a shorter way into the same one — a remark on the widget is filed
    where a remark on the question the widget stands as is not — so the next line of a
    remark landed somewhere the first line was not. The agent's reply moved both back.
    Nothing the reader did moved either, which is the whole of the complaint; the reply
    phase here is what says the ring has stopped tracking the count rather than merely
    tracking it late.

    A picked group is the control on the other side. It is answered, so it is off both
    readings and must stay off: the switch is about a seat the reader is mid-sentence in,
    not about reopening what a pick has closed.

    The seat and the ask are the project widget SEATED_ASK_ENTRY declares, for the reason
    test_a_seat_conversation_leaves_the_pick_it_is_about_live gives: the split is between
    two declarations, and since 292de9c no shipped entry carries both."""
    url = serve(
        leaf_page(
            "mid-sentence",
            """
<h1 id="t">Mid-sentence</h1>
<lf-ask id="shape-decision"><h2>Galvanised steel for the frame?</h2>
<lf-verdict id="shape" asks>Drop-in, and it needs no sealing.</lf-verdict></lf-ask>
<lf-ask id="picked-decision"><h2>Should we keep it?</h2>
<lf-options id="picked" choose>
  <lf-option id="pk-keep" chosen><strong>Keep it</strong> Settled by a pick.</lf-option>
  <lf-option id="pk-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options></lf-ask>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
    )
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Steel, unless the sealing is quick?",
            "anchor": {"section": "shape"},
        },
    )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-shortcut-bar")
    decisions = page.locator(".lf-asks")

    # The completion count includes every active Ask: the authored pick is complete;
    # the seated Ask and suggestion are not.
    expect(decisions).to_have_text("Asks 1/3")
    decisions.click()
    expect(page.locator("button.lf-asks-row")).to_have_count(3)
    expect(page.locator('.lf-asks-row[data-lf-at="shape-decision"]')).to_have_count(1)
    expect(page.locator('.lf-asks-row[data-lf-at="picked-decision"]')).to_have_count(1)
    expect(page.locator('.lf-asks-row[data-lf-at="sug-window"]')).to_have_count(1)

    # The reader is standing in it all the same — and first with the tray still open, the
    # one state where the ring has a second surface to reach: the inventory row.
    page.locator("#shape .lf-settle").focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("button.lf-asks-row")).to_have_count(3)
    expect(page.locator('.lf-asks-row[data-lf-at="shape-decision"]')).to_have_attribute(
        "data-lf-ask", "1"
    )
    page.evaluate("() => document.activeElement?.blur()")
    decisions.click()

    # And with it shut, which is every other reading below.
    page.locator("#shape .lf-settle").focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the ask")
    # The count is completion, not the open walk's position, so focus leaves it stable.
    expect(decisions).to_have_text("Asks 1/3")

    # Answering hands the question back, and the count moves while the ring does not.
    # Focus is not touched again from here, so the ring read below is the one painted
    # above: blurring and coming back would re-derive it and repeat the phase instead of
    # measuring that it stayed through the news.
    #
    # The source is the reader's again once the conversation in its answer control has
    # been answered.
    for root in [
        e["id"] for e in events_model.read_events(d) if e.get("kind") == "comment"
    ]:
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": root,
                "text": "Sealing is an afternoon.",
            },
        )
    told(page)
    # Back on the reader's open list, the same Ask is still incomplete, so the
    # completion count remains stable.
    expect(decisions).to_have_text("Asks 1/3")
    expect(page.locator("#shape .lf-settle")).to_be_focused()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the ask")
    page.evaluate("() => document.activeElement?.blur()")

    # The picked group is the control on the other side: answered, so off both readings,
    # and the switch leaves it there. Read through the shortcut bar, because `markHere` paints
    # inside `paintHere`'s frame — an absence read in the same round trip as the focus is
    # the frame before the paint, and stays green while a ring lands here a frame later.
    # The word is the other half of the same fact: with `standingIn` null the reading falls
    # through to the innermost item, which from a pick is the option and not the question.
    page.locator("#picked .lf-pick").first.focus()
    expect(line).to_contain_text(re.compile(r"comment on the option(?!s)"))
    assert page.locator("[data-lf-ask]").count() == 0, (
        "an answered group wears the ring the switch was not about"
    )

    assert errors == []
    page.close()


def test_c_in_a_thread_reaches_that_threads_own_box(browser, serve):
    """The panel's open list is the one part of the chrome that holds a conversation of
    its own, so a press meaning "say something about this" belongs to that box rather
    than to the page the panel stands over. `conversationBox` states the same rule from
    the other side when it declines to seat a widget standing inside a thread, and the
    asks and the `a`/`A` walk include the ones an agent sent — without this the same
    question answered one way on the page and another in the panel.

    A resolved thread is the case that has to be asked separately, and the reason this
    test exists at all: it is built by the same `threadNode` and wears the same class,
    under the Resolved state, where it keeps a tab stop and a Reopen button. Reading
    the class alone put the reader in a thread whose reply box is not there, and the press
    died on the null with the panel's own `c` never reached. Whether there is a box is what
    tells them apart — `standingConversation` asks for one rather than for the class — so
    the resolved thread falls through to the general box, which is the honest answer for a
    thread with no box of its own to offer."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    live = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    gone = panel_comment(d, "Settled already.", {"section": "how-cap"})
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": gone})

    page, errors = open_page(browser, url)
    line = page.locator(".lf-shortcut-bar")

    # Threads navigation is g T; page c is reserved for the page comment.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Standing in the open thread, it means that thread's reply box. `t` walks on from
    # where the press above left the reader, no backing out of a box first.
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(
        page.locator(f'.lf-thread[data-id="{live}"] > .lf-compose textarea')
    ).to_be_focused()

    # And Esc gives that press back: the thread, then the panel. In the panel the old
    # class-only reading and the new climb agree, so this is the consistency half rather
    # than the gate — test_c_in_a_seated_conversation_reaches_the_thread_it_is_in is what
    # actually goes red if the climb regresses, the page being where they diverge.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("back")
    page.evaluate("() => document.activeElement?.blur()")

    # A resolved thread has no box, so the press falls through to the general box rather
    # than reaching for one that is not there. The panel's own row answers it, saying so in
    # the panel's words; what matters is that the thread is not named, which is the phase
    # above's answer and would be the wrong one here.
    page.locator('[data-filter-value="resolved"]').click()
    page.locator(f'.lf-thread[data-id="{gone}"]:not([hidden])').focus()
    expect(line).not_to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()

    assert errors == []
    page.close()


def test_c_in_a_seated_conversation_reaches_the_thread_it_is_in(browser, serve):
    """The page side of the same question. A widget that seats its own conversation
    (`x-conversation`) holds one thread per exchange, each with its own box, and the
    reader can stand in any of them — so "say something about this" means the box of the
    thread they are in, exactly as it does in the panel. One reading answers both, because
    a rule for the panel and a different one for the page is two answers to one question:
    read off the panel's class alone, the page side sent every thread on a seat to the
    oldest one's box.

    Two threads, and the reader in the second: with one there is no wrong answer to give,
    so the pair is what makes the assertion mean anything. The first phase is the control
    — a decision beside the seat, where standing on the widget opens the composer on that
    widget, so a green below is the standing being read and not every press landing in a
    conversation.

    The agent has answered both remarks, so each thread here is a whole exchange. Nothing
    in this test turns on that: the press reads where the reader is standing rather than
    the reader's list, so the seat answers the same way before a reply and after one."""
    url = serve(
        leaf_page(
            "seated",
            """
<h1 id="t">Seated</h1>
<lf-ask id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-ask>
<lf-command id="hub" label="The rail">
  <lf-task id="fitting" status="active" talk><strong>Who fits the rail?</strong>
  Either crew can take it, and neither has said which week.</lf-task>
</lf-command>
""",
        )
    )
    d = serve.page_dir
    said = []
    for text in ("First remark.", "Second remark."):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "fitting"},
            },
        )
        said.append(events_model.read_events(d)[-1]["id"])
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": said[-1],
                "text": "Noted.",
            },
        )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-shortcut-bar")
    threads = page.locator(".lf-conversation-thread")
    expect(threads).to_have_count(2)

    # The control: standing on a widget that seats nothing, so the press has no thread
    # to prefer and opens the composer on the widget itself.
    page.locator("#shape .lf-pick").first.focus()
    expect(line).to_contain_text("comment on the ask")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement?.blur()")

    # Standing in the second thread, the press means that thread's box.
    second = page.locator(f'.lf-conversation-thread[data-thread="{said[1]}"]')
    second.focus()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(second.locator("> .lf-say textarea")).to_be_focused()

    # And Esc hands back the press that got them there, which is the keyboard-is-a-stack
    # rule read on the page rather than in the panel. The box asked for `.lf-thread` and
    # the panel alone, so out here the rung fell through to the page's own "let go": one
    # press in from the thread, one press out to body, with the thread they had been
    # standing in two feet away and no key back to it. Both ends read one climb now, so
    # the word going in ("comment on the thread") and the word coming out are about the
    # same element.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    # One rung, not two: the page's own way out is the press after this one.
    expect(line).to_contain_text("let go")
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")

    assert errors == []
    page.close()


def test_c_travels_to_an_item_its_own_scroller_has_taken_away(browser, serve):
    """What the press asks is whether the item is in front of the reader, and only the
    page shows that. An item's own box is the box it would have — unclipped — so a card
    carried out of a board's sideways scroller still reports one inside the window, and a
    gate reading that called it visible and opened the box on something entirely off
    screen. `shownRect` is the reading the ⌥ aim's own paint takes, and this press is its
    keyboard twin: the two decide "in front of the reader" alike or they are not twins.

    The control is the same board with the scroller left alone, where the card is really
    in front of the reader and nothing moves — the pointer's answer on the same card. A
    test with only the scrolled case would pass just as well on a press that always
    travelled, which is the behaviour this replaced."""
    url = serve(
        leaf_page(
            "carried",
            """
<h1 id="t">Carried</h1>
<lf-board id="b">
"""
            + "\n".join(
                f'<lf-column id="col{i}" label="Column {i}">'
                f'<lf-card id="card{i}">Card {i} with a '
                f'<a href="https://example.invalid/{i}">link {i}</a> inside it.</lf-card>'
                "</lf-column>"
                for i in range(8)
            )
            + """
</lf-board>
""",
        )
    )
    seen = """() => {
      const r = document.querySelector('#card0').getBoundingClientRect();
      return {left: Math.round(r.left), onScreen: r.right > 0 && r.left < innerWidth};
    }"""

    # The control: nothing scrolled, so the card is in front of the reader and stays put.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    was = page.evaluate(seen)
    assert was["onScreen"], "the control needs the card visible to begin with"
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["left"] == was["left"], (
        "the page moved under a reader who could already see the card"
    )
    page.close()

    # Carried out of its own scroller after the reader stood on it — focus first, because
    # focusing a card is itself a scroll and would undo the carrying it is meant to survive.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        "() => { const b = document.querySelector('#b'); b.scrollLeft = b.scrollWidth; }"
    )
    assert not page.evaluate(seen)["onScreen"], (
        "the board did not carry the card off screen, so this proves nothing"
    )
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["onScreen"], (
        "the box opened on a card the board had carried out of sight"
    )
    assert errors == []
    page.close()


def test_c_comments_and_g_t_navigates_to_threads(browser, serve):
    """c is contextual comment; g T is the one route into the Threads list."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("c")  # page: straight into its comment box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # panel context: the same page comment box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    assert errors == []
    page.close()


def test_the_panels_own_c_answers_a_page_whose_log_has_not_arrived(browser, serve):
    """A page whose first poll cannot reach the server is a page the reader still writes
    on: the general box stands, its placeholder names the key that reaches it, and the
    banner says only that a comment will not send yet. What it has not got is a thread
    list, so narrowing by what awaits the reader is dead. Find remains available as the
    panel's empty search, and the scope used to take `c` down with the missing list.

    The page's c enters the box directly. g T independently reaches the empty Threads
    list, where the panel's own search remains available.

    Offline rather than mid-load, because it is the state that stays: a loading page
    answers a moment later, and a page whose server has stopped is where a reader sits."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/api/state*", refuse)
    try:
        page.goto(serve(NOTED_PAGE), wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        expect(page.locator(".lf-status-text")).to_have_text(
            "Server offline — reconnecting. Keep this page open so pending changes can send."
        )

        page.keyboard.press("c")
        expect(page.locator(".lf-general textarea")).to_be_focused()
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        expect(page.locator(".lf-threads")).to_be_focused()

        # The missing list takes away its waiting filter, but not the panel's own search:
        # a search over nothing still belongs to the scope in front of the page.
        line = page.locator(".lf-shortcut-bar")
        expect(line).not_to_contain_text("waiting on you")
        expect(line).to_contain_text("find")

        assert errors == []
    finally:
        page.close()


# Where the reader is standing, in the terms the next Tab is decided by: the document
# position of the focused element, and whether it is the first stop in the document.
STANDING = """() => {
  const at = document.activeElement;
  const first = document.querySelector('.lf-skip');
  return {
    name: at?.className || at?.tagName || 'nothing',
    isFirstStop: at === first,
    top: at ? at.getBoundingClientRect().top : null,
    inChrome: Boolean(at?.closest?.('.lf-chrome')),
  };
}"""


def test_the_reference_hands_the_reader_back_to_the_page_they_were_reading(
    browser, serve
):
    """Closing a mode gives back the press that opened it, and the reader's place with it.

    A reader working from the page stands on `body`: `letGo` puts them there so Space and
    PageDown reach the document's own scroll box. `?` from there recorded `body` as the
    door and closing handed focus back to it — and focusing `body` resets the browser's
    sequential focus navigation starting point, so the next Tab began at the top of the
    document. A reader who opened the reference four screens down to look a key up was
    charged the whole page to get back to where they had been.

    The reading is the next Tab rather than the focused element, because that is the fact
    that was wrong: the restore itself looked fine both before and after, focus being on
    nothing either way. The skip link is the document's first stop, so landing on it is
    exactly the failure written down.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.evaluate("() => document.getElementById('p40').scrollIntoView()")
    page_at_rest(page)
    reading = page.evaluate(
        "() => document.getElementById('p40').getBoundingClientRect().top"
    )
    # Twice: the first press unfolds the shelf, the second opens the reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-reference")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-shortcut-reference")).to_be_hidden()

    page.keyboard.press("Tab")
    standing = page.evaluate(STANDING)
    assert not standing["isFirstStop"], (
        f"after the reference closed, the reader's next Tab went to the first stop in "
        f"the document ({standing}) rather than on from the words they were reading at "
        f"{reading:.0f}px"
    )
    # And nothing of the borrow is left on the author's paragraph: `tabindex` is not in
    # PAGE_PAINT_ATTRIBUTES, so a stop left standing would be runtime paint the replay
    # signature has no vocabulary for.
    assert (
        page.evaluate("() => document.querySelectorAll('main [tabindex]').length") == 0
    )
    assert errors == []
    page.close()


def test_a_reader_at_the_top_of_the_document_is_one_press_from_the_chrome(
    browser, serve
):
    """The runtime's layer follows `main`, so reaching it by Tab meant reaching it last.

    Document order is right for reading — the page is what the reader came for — and it
    is the whole tab order too, so on a page of any length the banner, the panel and the
    shortcut bar stood behind every link, fold and control the author wrote. A keyboard reader
    arriving at the top of the document had no way to the layer that is not the page.

    The press is what is asserted rather than the link's presence: a skip link that is in
    the DOM and does not land anybody is the failure this is about, one step later.

    On the corpus, because a page of plain paragraphs would put the chrome one Tab away
    on its own and this would pass with the link taken out.
    """
    example = next(e for e in EXAMPLES if e.stem == "corpus")
    page, errors = open_page(browser, serve(example))
    page.evaluate("() => document.body.focus()")
    page.keyboard.press("Tab")
    standing = page.evaluate(STANDING)
    assert standing["isFirstStop"], (
        f"the first Tab from the top of the document landed on {standing['name']}, so "
        f"the layer is still behind the whole page"
    )
    assert standing["top"] >= 0, (
        f"the skip link takes focus and is not on screen: {standing}"
    )
    page.keyboard.press("Enter")
    landed = page.evaluate(STANDING)
    assert landed["inChrome"], (
        f"the skip link's press left the reader on {landed['name']}, outside the layer "
        f"it names"
    )
    assert errors == []
    page.close()
