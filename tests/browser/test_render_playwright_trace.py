"""An external Playwright journey becomes commentable evidence in Leaf."""

import json
import re
from pathlib import Path

import pytest
from leaf_dev.page_fixtures import example_media
from playwright.sync_api import expect
from render_cases_layout import current_location_ring, ring_faults
from render_cases_navigation import source_revision
from render_harness import (
    at_rest,
    holding,
    leaf_page,
    open_page,
    resized,
    still_page,
    told,
)

from leaf import data as data_model
from leaf.render_checks import evaluate_probe, rendered, wait_until_ready

ROOT = Path(__file__).resolve().parents[2]


def test_trace_moments_keep_their_distinguishing_words_on_a_phone(browser, serve):
    """The before/after result names differ at their ends, which must remain readable."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(
        browser, serve(ROOT / "examples/review-a-fix.html"), context=context
    )
    for recording, label in [("before", "Before the fix"), ("after", "After the fix")]:
        page.get_by_role("radio", name=label, exact=True).tap()
        moment = page.locator(f"#fix-{recording} .lf-trace-bookmark").last
        moment.scroll_into_view_if_needed()
        measured = moment.evaluate("""row => {
          const label = row.querySelector('.lf-trace-moment-label');
          const box = row.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(label);
          return {horizontal: label.scrollWidth - label.clientWidth,
            words: [...range.getClientRects()].every(r =>
              r.left >= box.left && r.right <= box.right &&
              r.top >= box.top && r.bottom <= box.bottom)};
        }""")
        assert measured["horizontal"] <= 1, measured
        assert measured["words"], measured


def test_trace_bookmarks_leave_the_image_allocation(browser, serve):
    """Saved moments follow the evidence; their number never consumes its viewport."""
    source = ROOT / "examples/developer/playwright-trace-gallery.data.json"
    record = json.loads(source.read_text())["release-journey"]
    action = next(action for action in record["actions"] if "after" in action["phases"])
    target = f"trace-{record['archive']['sha256']}-phase-{action['id']}-after"
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    viewers = "".join(
        f'<lf-trace id="{name}" label="{name.title()}" source="trace">'
        + "".join(
            f'<lf-trace-bookmark label="Result {index}" target="{target}"></lf-trace-bookmark>'
            for index in range(5)
        )
        + "</lf-trace>"
        for name in ("before", "after")
    )
    url = serve(
        leaf_page(
            "Review recorded evidence",
            "<h1>Compare the same journey</h1>"
            f'<lf-trace-compare id="comparison">{viewers}</lf-trace-compare>'
            "<p>End of the comparison.</p>",
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "trace", record)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    user = open_page(browser, url, context=context)
    widget = user.locator("#before")
    image = widget.locator(".lf-trace-image-viewport").bounding_box()
    controls = widget.locator(".lf-trace-controls").bounding_box()
    stage = widget.locator(".lf-trace-stage").bounding_box()
    assert controls["y"] >= stage["y"] + stage["height"], (controls, stage)
    assert image["height"] > user.viewport_size["height"] / 2, image

    # Ordinary scrolling puts the source chooser in its sticky position. Toggling
    # must preserve both the reader's page position and the evidence rectangle.
    widget.locator(".lf-trace-heading").hover()
    user.mouse.wheel(0, 250)
    user.wait_for_function("scrollY >= 200")
    rendered(user)

    def geometry():
        return user.evaluate("""() => {
          const trace = document.querySelector('lf-trace:not([hidden])');
          const box = trace.querySelector('.lf-trace-image-viewport').getBoundingClientRect();
          return {scroll: scrollY, x: box.x, y: box.y, width: box.width, height: box.height};
        }""")

    before = geometry()
    for label in ("After", "Before", "After"):
        radio = user.get_by_role("radio", name=label, exact=True)
        box = radio.bounding_box()
        # Click where the user sees the sticky chooser; locator.click first asks
        # Chromium to scroll its target into the scroll-padding region.
        user.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(user.locator(f"#{label.lower()}")).to_be_visible()
        rendered(user)
        assert geometry() == pytest.approx(before, abs=1)
    user.get_by_role("radio", name="After", exact=True).press("ArrowLeft")
    expect(user.locator("#before")).to_be_visible()
    rendered(user)
    assert geometry() == pytest.approx(before, abs=1)


def test_trace_parts_carry_the_recording_and_place_they_were_drawn_from(browser, serve):
    """Each drawn part is a datum of the recording that supplied it, at its place in the
    archive, and a replacement recording restamps the same parts."""
    source = ROOT / "examples/developer/playwright-trace-gallery.data.json"
    record = json.loads(source.read_text())["release-journey"]
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Recorded evidence",
            '<h1 id="title">The journey</h1>'
            '<lf-trace id="journey" label="Journey" source="trace"></lf-trace>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "trace", record)
    page = open_page(browser, url)
    parts = page.locator("#journey [data-lf-projection]")

    def stamps():
        return parts.evaluate_all("""nodes => nodes.map(node => ({
          key: node.dataset.lfDatum, identity: node.dataset.lfIdentity,
          revision: node.dataset.lfSourceRevision,
          path: JSON.parse(node.dataset.lfOrigin).path,
        }))""")

    first = stamps()
    assert first, "the recording drew no datum"
    revision = source_revision(serve.page_dir, "trace")
    assert all(
        part["identity"] == part["key"]
        and part["revision"] == revision
        and part["path"][0] in {"actions", "images"}
        for part in first
    ), first

    record["actions"][0]["title"] += " (rerun)"
    data_model.cmd_data_set(serve.page_dir, "trace", record)
    told(page)
    rerun = source_revision(serve.page_dir, "trace")
    assert rerun != revision
    page.wait_for_function(
        "revision => [...document.querySelectorAll('#journey [data-lf-projection]')]"
        ".every(node => node.dataset.lfSourceRevision === revision)",
        arg=rerun,
    )
    assert [{**part, "revision": rerun} for part in first] == stamps()


@pytest.mark.shifts_unsurveyed
def test_trace_viewer_stays_idle_after_initial_presentation(browser, serve):
    """The viewer's disabled transition cannot wake margin layout after readiness."""
    url = serve(ROOT / "examples/developer/playwright-trace-gallery.html")
    assert at_rest(still_page(browser, url)) == []


@pytest.mark.parametrize(
    ("engine", "width"),
    [("browser", 1400), ("browser", 320), ("firefox_browser", 320)],
)
def test_timeline_tooltips_keep_their_words_above_marks_inside_the_timeline(
    request, serve, engine, width
):
    """Narrow timelines keep a complete hovered label inside their inline room.

    The first lane's tooltip may extend above the timeline. Its horizontal fit must
    still work there, including after zoom changes which marks stand at its edges.
    Firefox also wraps a narrow label without letting its lower lines cover the mark.
    """
    browser = request.getfixturevalue(engine)
    record = json.loads(
        (ROOT / "examples/developer/playwright-trace-gallery.data.json").read_text()
    )["release-journey"]
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Timeline labels",
            '<h1>Inspect recorded input</h1><lf-trace id="journey" source="trace"></lf-trace>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "trace", record)
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = open_page(browser, url, context=context)
    widget = page.locator("#journey")
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.scroll_into_view_if_needed()
    for zoom in (False, True):
        if zoom:
            widget.get_by_role("button", name="Zoom in", exact=True).click()
            rendered(page)
        marks = timeline.locator("[data-tip]")
        visible = marks.evaluate_all("""nodes => nodes.map((node, index) => {
            const box = node.getBoundingClientRect();
            const band = node.closest('.lf-trace-scroller').getBoundingClientRect();
            return {index, left:box.left, shown:box.width > 0
              && box.left >= band.left && box.right <= band.right};
          }).filter(item => item.shown).sort((a,b) => a.left-b.left)
            .map(item => item.index)""")
        assert visible
        for index in (visible[0], visible[-1]):
            mark = marks.nth(index)
            mark.hover()
            tooltip = timeline.get_by_role("tooltip")
            expect(tooltip).to_be_visible()
            rendered(page)
            host, target, tip = (
                locator.bounding_box() for locator in (timeline, mark, tooltip)
            )
            assert tip["y"] + tip["height"] <= target["y"]
            assert tip["x"] >= host["x"] - 1
            assert tip["x"] + tip["width"] <= host["x"] + host["width"] + 1
            assert tooltip.inner_text().replace("\u00a0", " ") == mark.get_attribute(
                "data-tip"
            )
        page.get_by_role("heading", name="Inspect recorded input").hover()
        expect(timeline.get_by_role("tooltip")).to_be_hidden()


def stop_time(record, checkpoint):
    """A checkpoint's stop: its image's capture time, or else its DOM snapshot's."""
    if checkpoint.get("imageId"):
        return next(
            image["timestamp"]
            for image in record["images"]
            if image["id"] == checkpoint["imageId"]
        )
    return checkpoint["timestamp"]


def navigate_at(timeline, index):
    """Walk real keyboard routes to the ordered native checkpoint or frame."""
    timeline.focus()
    timeline.press("Home")
    for _ in range(index):
        timeline.press("ArrowRight")
    rendered(timeline.page)


def navigate_to_phase(timeline, identity):
    """Visit an exact native phase in the full image and checkpoint chronology."""
    timeline.focus()
    timeline.press("Home")
    widget = timeline.locator("xpath=ancestor::lf-trace")
    for _ in range(1000):
        if widget.locator(".lf-trace-phase").get_attribute("data-lf-datum") == identity:
            rendered(timeline.page)
            return
        expect(widget.get_by_role("button", name="Next", exact=True)).to_be_enabled()
        timeline.press("ArrowRight")
    raise AssertionError(f"Native phase not reached: {identity}")


def test_trace_arrows_step_the_way_the_time_scale_runs_in_right_to_left_text(
    browser, serve
):
    """The time scale runs left to right in any text direction, and so do its arrows."""
    source = ROOT / "examples/developer/playwright-trace-gallery.data.json"
    record = json.loads(source.read_text())["release-journey"]
    setup = next(action for action in record["actions"] if not action["input"])
    setup["title"] = f"Setup.phase · {setup['title']}"
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Right-to-left recording",
            '<h1>Recording</h1><div dir="rtl">'
            '<lf-trace id="journey" source="rtl-trace"></lf-trace></div>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "rtl-trace", record)
    user = open_page(browser, url)
    widget = user.locator("#journey")
    call = widget.locator(f'.lf-trace-call-bar[data-id="{setup["id"]}"]')
    expect(call.locator(".lf-trace-call-name")).to_have_text(setup["method"])
    expect(call).to_have_attribute("data-tip", re.compile(re.escape(setup["title"])))
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    position = widget.locator(".lf-trace-position")
    playhead = widget.locator(".lf-trace-playhead")
    scroller = widget.locator(".lf-trace-scroller").bounding_box()
    timeline.focus()
    timeline.press("End")
    expect(position).not_to_have_text("No recorded points")
    last = position.text_content()
    timeline.press("Home")
    expect(position).not_to_have_text(last)
    first = position.text_content()
    # Recording zero stands at the scale's left edge, as in left-to-right text.
    start = playhead.bounding_box()["x"]
    assert start - scroller["x"] < scroller["width"] / 4
    timeline.press("ArrowRight")
    expect(position).not_to_have_text(first)
    # The step went the way its arrow points along the scale.
    assert playhead.bounding_box()["x"] > start
    timeline.press("ArrowLeft")
    expect(position).to_have_text(first)


STILL = """
  const tree = document.querySelector('#journey .lf-trace-tree');
  // Every scroller stands still for a while, so a late restore has had its turn.
  const where = () => [scrollY, tree.scrollTop].join();
  for (let still = 0, last = where(); still < 30; ) {
    await new Promise(requestAnimationFrame);
    const now = where();
    still = now === last ? still + 1 : 0;
    last = now;
  }
"""
STILL_TREE = f"async () => {{ {STILL} return tree.scrollTop; }}"
LANDED_ROW = (
    "async () => {"
    + STILL
    + """
  const {landingBand} = await window.__lfCheckApi();
  const rows = tree.querySelectorAll('.lf-trace-node');
  const row = rows[rows.length - 1].getBoundingClientRect();
  const box = tree.getBoundingClientRect();
  const band = landingBand(document.scrollingElement);
  const top = Math.max(band.top, box.top + tree.querySelector('summary').offsetHeight);
  const bottom = Math.min(band.bottom, box.top + tree.clientTop + tree.clientHeight);
  return {open: tree.open, row: [row.top, row.bottom], shown: [top, bottom]};
}"""
)


def scrolled_closed_tree(browser, serve, motion):
    """A trace whose checkpoint's tree the reader scrolled, then closed.

    Opening the tree hands its reading region from the point inspector to the tree's
    own scroller, so the opening is a shift with a reading of the tree to restore.
    Returns the reader's page, the trace widget, and where the reader left the tree.
    """
    source = ROOT / "examples/developer/playwright-trace-gallery.data.json"
    record = json.loads(source.read_text())["release-journey"]
    archive = record["archive"]["sha256"]
    action = next(
        action
        for action in reversed(record["actions"])
        if len(action["phases"].get("after", {}).get("tree", {}).get("nodes", ())) > 5
    )
    node = action["phases"]["after"]["tree"]["nodes"][-1]
    phase = f"trace-{archive}-phase-{action['id']}-after"
    members = (
        f'<lf-trace-bookmark label="Checkpoint" target="{phase}"></lf-trace-bookmark>'
        f'<lf-trace-bookmark label="Saved element" '
        f'target="{phase}-node-{node["path"].encode().hex()}"></lf-trace-bookmark>'
    )
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    after = "".join(
        f"<p>Review note {n} on the recording above.</p>" for n in range(40)
    )
    url = serve(
        leaf_page(
            "Saved element",
            "<h1>Saved element</h1>"
            f'<lf-trace id="journey" source="review-trace">{members}</lf-trace>{after}',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "review-trace", record)
    context = browser.new_context(
        viewport={"width": 1280, "height": 500}, reduced_motion=motion
    )
    user = open_page(browser, url, context=context)
    widget = user.locator("#journey")
    moments = widget.locator(".lf-trace-bookmarks")
    moments.get_by_role("button", name=re.compile("Checkpoint")).click()
    expect(widget.locator(".lf-trace-phase")).to_contain_text("After checkpoint")
    tree = widget.locator(".lf-trace-tree")
    summary = tree.locator("summary")
    summary.click()
    expect(tree).to_have_attribute("open", "")
    tree.hover()
    user.mouse.wheel(0, 40)
    user.wait_for_function("document.querySelector('#journey details').scrollTop > 0")
    rendered(user)
    place = user.evaluate(STILL_TREE)
    summary.click()
    expect(tree).not_to_have_attribute("open", "")
    rendered(user)
    return user, widget, place


def assert_row_shown(landed):
    (top, bottom), (shown_top, shown_bottom) = landed["row"], landed["shown"]
    assert shown_top - 1 <= top and bottom <= shown_bottom + 1, landed


@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_trace_moment_lands_its_saved_element_over_the_trees_reading(
    browser, serve, motion
):
    """A Moment naming a saved element shows its row in the tree and the page.

    The reader scrolled this checkpoint's tree and closed it, so opening the tree
    has a reading to restore. The Moment's landing is newer and stands. Its
    checkpoint is already shown, so no image decode delays the landing past the
    restore; that delay is what let this pass on some runs. Smooth motion is cut
    short by any later scroll write, so both motions run. A row inside the window
    but below the tree's own box is not shown either.
    """
    user, widget, _ = scrolled_closed_tree(browser, serve, motion)
    saved = widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name=re.compile("Saved element")
    )
    saved.click()
    landed = user.evaluate(LANDED_ROW)
    assert landed["open"]
    assert_row_shown(landed)

    # The open tree back at its start, its top near the window's: the row is
    # inside the window, below what the tree shows.
    user.set_viewport_size({"width": 1280, "height": 900})
    rendered(user)
    widget.locator(".lf-trace-tree").evaluate(
        "tree => { tree.scrollTop = 0;"
        " scrollBy(0, tree.getBoundingClientRect().top - 120); }"
    )
    rendered(user)
    saved.evaluate("button => button.click()")
    landed = user.evaluate(LANDED_ROW)
    user.context.close()
    assert_row_shown(landed)


def test_trace_tree_opened_by_the_browser_keeps_its_match(browser, serve):
    """The browser's own opening of a closed tree onto a row keeps that row shown.

    Find-in-page opens a closed disclosure onto its match and scrolls the match into
    view itself, in one task and through no landing of Leaf's. That scroll is the
    reader's, and the shift the opening announces a frame later must not return the
    tree to where the reader left it. Headless Chrome has no find bar, and Leaf
    intercepts a fragment navigation to travel there itself, so the page makes the
    find's two moves: it opens the tree and scrolls the row into view natively.
    """
    user, widget, _ = scrolled_closed_tree(browser, serve, "reduce")
    # The reader goes back to reading the page, which takes focus off the summary.
    user.get_by_text("Review note 0 on").click()
    rendered(user)
    widget.locator(".lf-trace-node").last.evaluate(
        "row => { row.closest('details').open = true;"
        " row.scrollIntoView({block: 'nearest'}); }"
    )
    landed = user.evaluate(LANDED_ROW)
    user.context.close()
    assert landed["open"]
    assert_row_shown(landed)


def test_trace_tree_opens_at_each_checkpoints_reading(browser, serve):
    """Opening the tree returns the reader to where they left this checkpoint's tree.

    One scroll box shows every checkpoint's tree, and keeps the offset of whichever it
    showed last; the reader's place is each checkpoint's own. Here they leave the After
    tree scrolled and the Action tree at its end, the tree closed between, and open it
    again on the After checkpoint.
    """
    user, widget, place = scrolled_closed_tree(browser, serve, "reduce")
    tree = widget.locator(".lf-trace-tree")
    summary = tree.locator("summary")
    phase = widget.locator(".lf-trace-phase")
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    timeline.press("ArrowLeft")
    expect(widget.locator(".lf-trace-tree-clock")).to_contain_text("Action checkpoint")
    summary.click()
    expect(tree).to_have_attribute("open", "")
    tree.hover()
    user.mouse.wheel(0, 2000)
    user.wait_for_function(
        "(place) => document.querySelector('#journey details').scrollTop > place",
        arg=place,
    )
    rendered(user)
    summary.click()
    expect(tree).not_to_have_attribute("open", "")
    timeline.focus()
    timeline.press("ArrowRight")
    expect(phase).to_contain_text("After checkpoint")
    summary.click()
    expect(tree).to_have_attribute("open", "")
    opened = user.evaluate(STILL_TREE)
    user.context.close()
    assert opened == pytest.approx(place, abs=1)


def test_trace_comparison_pairs_authored_results_across_delayed_sources(browser, serve):
    """A shared semantic result resolves each archive's own target, even on late arrival."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    actions = [action for action in record["actions"] if "click" in action["title"]]
    targets = [
        f"trace-{record['archive']['sha256']}-phase-{action['id']}-after"
        for action in actions[:2]
    ]
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    viewers = "".join(
        f'<lf-trace id="{name}" label="{name.title()}" source="{name}-trace">'
        f'<lf-trace-bookmark key="settled" label="{name.title()} result" target="{target}"></lf-trace-bookmark>'
        "</lf-trace>"
        for name, target in zip(("before", "after"), targets, strict=True)
    )
    url = serve(
        leaf_page(
            "Matched results",
            f'<h1>Matched results</h1><lf-trace-compare id="feeds">{viewers}</lf-trace-compare>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "before-trace", record)
    user = open_page(browser, url)
    before = user.locator("#before")
    before.locator(".lf-trace-bookmark").click()
    expect(before.locator(".lf-trace-phase")).to_have_attribute(
        "data-lf-datum", targets[0]
    )
    before.get_by_role("button", name="Image scale", exact=True).click()
    before.get_by_role("button", name="Actual size", exact=True).click()
    canvas = before.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .lf-trace-canvas"
    )
    canvas.focus()
    canvas.press("ArrowLeft")

    def image_view(widget):
        return widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        ).evaluate("""image => {
          const r = image.getBoundingClientRect();
          const c = image.closest('.lf-trace-canvas').getBoundingClientRect();
          return {x: r.x - c.x, y: r.y - c.y, width: r.width};
        }""")

    inspected = image_view(before)
    # Both the semantic result and image inspection reach a peer selected before
    # it has any data or an archive-specific scope in which to save that view.
    user.get_by_role("radio", name="After", exact=True).click()
    after = user.locator("#after")
    data_model.cmd_data_set(serve.page_dir, "after-trace", record)
    expect(after.locator(".lf-trace-phase")).to_have_attribute(
        "data-lf-datum", targets[1]
    )
    expect(after.locator(".lf-trace-bookmark")).to_have_attribute(
        "aria-current", "true"
    )
    wait_until_ready(user)
    assert image_view(after) == pytest.approx(inspected, abs=1)
    expect(after.locator(".lf-trace-position")).to_be_visible()
    origin = record["streams"][0]["monotonicTime"]
    expected_positions = [
        f"{(stop_time(record, action['phases']['after']) - origin) / 1000:.3f} s"
        for action in actions[:2]
    ]
    assert expected_positions[0] != expected_positions[1]
    # The inactive recording keeps its semantic point while its stage is hidden.
    assert [
        before.locator(".lf-trace-position").text_content(),
        after.locator(".lf-trace-position").inner_text(),
    ] == expected_positions
    after.get_by_role("button", name="Start", exact=True).click()
    user.get_by_role("radio", name="Before", exact=True).click()
    wait_until_ready(user)
    expect(before.locator(".lf-trace-phase")).to_be_visible()
    expect(before.locator(".lf-trace-phase")).to_have_attribute(
        "data-lf-datum", targets[0]
    )


def test_trace_initial_moment_uses_capture_order_and_skips_unavailable_targets(
    browser, serve
):
    """Review opens the first stream with a resolvable Moment, at its earliest one."""
    source = ROOT / "examples/developer/playwright-trace-gallery.data.json"
    record = json.loads(source.read_text())["release-journey"]
    # An earlier recording stream has no authored Moments or saved captures.
    record["streams"].insert(0, record["streams"][0] | {"id": "empty-stream"})
    # Native archives can contain images and actions without any saved ARIA tree.
    for action in record["actions"]:
        for phase in action["phases"].values():
            phase["tree"] = None
    archive = record["archive"]["sha256"]
    # A captured checkpoint image whose phase no longer names it has no exact stop.
    orphan = next(image for image in record["images"] if image["kind"] == "checkpoint")
    orphan_action = next(
        action for action in record["actions"] if action["callId"] == orphan["callId"]
    )
    orphan_action["phases"][orphan["phase"]]["imageId"] = None
    frames = sorted(
        (image for image in record["images"] if image["kind"] == "frame"),
        key=lambda image: image["timestamp"],
    )
    earlier, later = frames[-2:]
    assert earlier["timestamp"] < later["timestamp"]
    earlier_target = f"trace-{archive}-image-{earlier['id']}"
    members = (
        f'<lf-trace-bookmark label="Missing capture" target="trace-{archive}-image-absent"></lf-trace-bookmark>'
        f'<lf-trace-bookmark label="Orphaned checkpoint" target="trace-{archive}-image-{orphan["id"]}"></lf-trace-bookmark>'
        f'<lf-trace-bookmark label="Later" target="trace-{archive}-image-{later["id"]}"></lf-trace-bookmark>'
        f'<lf-trace-bookmark label="Review begins" target="{earlier_target}"></lf-trace-bookmark>'
    )
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Review entry",
            f'<h1>Review entry</h1><lf-trace id="journey" source="review-trace">{members}</lf-trace>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "review-trace", record)
    user = open_page(browser, url)
    widget = user.locator("#journey")
    expect(widget.get_by_role("radio", name="Stream 2", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(
        widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
    ).to_have_attribute("data-lf-datum", earlier_target)
    moments = widget.locator(".lf-trace-bookmarks")
    expect(
        moments.get_by_role("button", name=re.compile("Missing capture"))
    ).to_be_disabled()
    expect(
        moments.get_by_role("button", name=re.compile("Review begins"))
    ).to_have_attribute("aria-current", "true")
    expect(
        moments.get_by_role("button", name=re.compile("Orphaned checkpoint"))
    ).to_be_disabled()
    expect(widget.locator(".lf-trace-tree-clock")).to_have_text(
        "No accessibility tree was saved at this point."
    )
    # A manual scope choice is retained instead of reopening the authored Moment.
    widget.get_by_role("radio", name="Stream 1", exact=True).click()
    expect(widget.get_by_role("radio", name="Stream 1", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(widget.locator(".lf-trace-position")).to_have_text("No recorded points")
    widget.get_by_role("radio", name="Stream 2", exact=True).click()
    expect(
        moments.get_by_role("button", name=re.compile("Review begins"))
    ).to_have_attribute("aria-current", "true")
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    timeline.press("Home")
    first_call = min(record["actions"], key=lambda action: action["startTime"])
    expect(widget.locator(".lf-trace-action")).to_have_text(first_call["title"])
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Start")


def test_hidden_recording_prepares_when_shown_without_blocking_page(browser, serve):
    """A native visibility toggle must not leave unrelated reading behind redraw proof."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "A recording tab",
            '<h1>Review when ready</h1><input type="checkbox" id="show-recording">'
            '<label for="show-recording">Show recording</label>'
            '<div id="recording-tab"><lf-trace id="journey" source="hidden-trace"></lf-trace></div>',
            head="<style>#recording-tab { display: none; } "
            "#show-recording:checked ~ #recording-tab { display: block; }</style>",
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "hidden-trace", record)
    user = open_page(browser, url)
    widget = user.locator("#journey")
    expect(widget).to_be_hidden()
    expect(widget.locator(".viewer-container")).to_have_count(0)
    toggle = user.get_by_role("checkbox", name="Show recording", exact=True)
    toggle.check()
    wait_until_ready(user)
    raster = widget.locator(".viewer-canvas img")
    expect(raster).to_be_visible()
    capture = raster.get_attribute("data-lf-datum")
    toggle.uncheck()
    wait_until_ready(user)
    resized(user, 390, 844)
    toggle.check()
    wait_until_ready(user)
    expect(raster).to_have_attribute("data-lf-datum", capture)
    canvas = widget.locator(".lf-trace-canvas").bounding_box()
    viewer = widget.locator(".viewer-container").bounding_box()
    assert abs(canvas["width"] - viewer["width"]) <= 2
    assert abs(canvas["height"] - viewer["height"]) <= 2
    assert user.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_trace_metadata_inspection_preserves_pending_checkpoint(browser, serve):
    """Reading current action details never selects an older displayed image."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    user = browser.new_page()
    held = []
    armed = False

    def gate(route):
        if armed:
            held.append(route)
        else:
            route.continue_()

    user.route("**/media/**", gate)
    user.goto(serve(source))
    wait_until_ready(user)
    widget = user.locator("lf-trace")
    armed = True
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    timeline.press("End")
    holding(user, held, 1, "next checkpoint image")
    phase = widget.locator(".lf-trace-phase")
    requested_phase = phase.inner_text()
    assert requested_phase
    summary = widget.locator(".lf-trace-tree summary")
    requested_tree = summary.inner_text()
    assert "unavailable" not in requested_tree
    position = widget.locator(".lf-trace-position")
    requested_position = position.inner_text()
    metadata = widget.get_by_role("group", name="Selected point details")
    metadata.scroll_into_view_if_needed()
    box = metadata.bounding_box()
    user.mouse.move(box["x"] + box["width"] / 2, box["y"] + 30)
    user.mouse.wheel(0, 100)
    metadata.focus()
    metadata.press("End")
    summary.click()
    expect(phase).to_have_text(requested_phase)
    expect(summary).to_have_text(requested_tree)
    expect(position).to_have_text(requested_position)
    armed = False
    for route in held:
        route.continue_()
    rendered(user)
    expect(phase).to_have_text(requested_phase)
    expect(position).to_have_text(requested_position)


def test_trace_playback_frames_stand_over_the_capture_they_replace(browser, serve):
    """A frame played over a fitted capture covers it exactly, so playback shows one
    image and the recorded pointer lands on the frame it marks."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    user = context.new_page()
    user.goto(serve(ROOT / "examples/developer/playwright-trace-gallery.html"))
    wait_until_ready(user)
    widget = user.locator("lf-trace")
    widget.get_by_role("button", name="Start", exact=True).click()
    rendered(user)
    # The fitted capture is narrower than its canvas, where centering rules would
    # otherwise reach the playback layer.
    assert widget.evaluate("""widget => {
      const image = widget.querySelector(
        '.lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img');
      return image.parentElement.closest('.lf-trace-image').getBoundingClientRect().width
        - image.getBoundingClientRect().width > 20;
    }""")
    widget.get_by_role("button", name="Play", exact=True).click()
    # Read both in one task while the frame shows: the Viewer takes over again once
    # playback stops.
    shown, under = user.wait_for_function("""() => {
      const layer = document.querySelector('.lf-trace-playback-image:not([hidden])');
      const under = layer?.parentElement.querySelector('.viewer-canvas img');
      return under && [layer, under].map(image => image.getBoundingClientRect().toJSON());
    }""").json_value()
    assert all(abs(shown[key] - under[key]) <= 1 for key in shown), (shown, under)


def test_trace_overview_shows_every_row_and_preserves_page_scrolling(browser, serve):
    """The initial overview exposes every mark and lane without inner scrolling."""
    url = serve(ROOT / "examples/developer/playwright-trace-gallery.html")
    for width, height in ((1440, 600), (480, 520)):
        context = browser.new_context(
            viewport={"width": width, "height": height}, color_scheme="dark"
        )
        user = context.new_page()
        user.goto(url)
        wait_until_ready(user)
        widget = user.locator("lf-trace")
        stage = widget.locator(".lf-trace-stage")
        tools = widget.locator(".lf-trace-image-tools")
        metadata = widget.locator(".lf-trace-metadata")
        assert (
            widget.locator(".lf-trace-image-viewport").bounding_box()["height"] >= 180
        )
        assert tools.bounding_box()["y"] + tools.bounding_box()["height"] <= (
            stage.bounding_box()["y"] + stage.bounding_box()["height"] + 1
        )
        assert metadata.bounding_box()["y"] >= (
            tools.bounding_box()["y"] + tools.bounding_box()["height"]
        )
        timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
        timeline.scroll_into_view_if_needed()
        marks = widget.locator(
            ".lf-trace-moment-pin, .lf-trace-input-label, .lf-trace-bar"
        )
        assert marks.count() > 0
        # Every mark fits inside the timeline and is directly pointable; the
        # timeline scrolls only sideways, and only when zoomed.
        hidden = marks.evaluate_all("""marks => marks.flatMap(mark => {
          const r = mark.getBoundingClientRect();
          const c = mark.closest('.lf-trace-scroller').getBoundingClientRect();
          const hit = document.elementFromPoint(r.x + Math.min(r.width / 2, 3),
            r.y + r.height / 2);
          return r.top >= c.top && r.bottom <= c.bottom
            && r.left >= c.left && r.right <= c.right + 0.5
            && (hit === mark || mark.contains(hit)) ? [] : [{
              label: mark.dataset.tip, bounds: r.toJSON(), coveredBy: hit?.className,
            }];
        })""")
        assert hidden == [], hidden
        assert widget.locator(".lf-trace-scroller").evaluate(
            "node => node.scrollHeight <= node.clientHeight && node.scrollWidth <= node.clientWidth"
        )
        before_scroll = user.evaluate("scrollY")
        timeline.hover()
        user.mouse.wheel(0, 300)
        user.wait_for_function("before => scrollY >= before + 250", arg=before_scroll)
        rendered(user)
        widget.get_by_role("button", name="Image scale", exact=True).click()
        actual = widget.get_by_role("button", name="Actual size", exact=True)
        assert actual.evaluate("""button => {
          const r = button.getBoundingClientRect();
          const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return hit === button || button.contains(hit);
        }""")
        box = actual.bounding_box()
        user.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        # Keyboard stepping moves the playhead, not the whole-recording window.
        timeline.focus()
        ruler_reading = "nodes => nodes.map(node => [node.textContent, node.getBoundingClientRect().x])"
        ruler = widget.locator(".lf-trace-tick-major")
        time_window = ruler.evaluate_all(ruler_reading)
        position = widget.locator(".lf-trace-position")
        for _ in range(4):
            before = position.inner_text()
            user.keyboard.press("ArrowRight")
            expect(position).not_to_have_text(before)
            rendered(user)
            assert ruler.evaluate_all(ruler_reading) == time_window
        assert widget.locator(".lf-trace-caption").evaluate(
            "node => parseFloat(getComputedStyle(node).fontSize) >= 12"
        )
        assert ruler.first.evaluate(
            "node => parseFloat(getComputedStyle(node).fontSize) >= 12"
        )
        assert ruler.first.evaluate(
            "node => getComputedStyle(node).color"
        ) == widget.locator(".lf-trace-caption").evaluate(
            "node => getComputedStyle(node).color"
        )


def test_trace_pointer_annotation_stays_inside_the_panned_image_viewport(
    browser, serve
):
    """Image inspection clips recorded pointer paint at the capture boundary."""
    user = open_page(
        browser, serve(ROOT / "examples/developer/playwright-trace-gallery.html")
    )
    widget = user.locator("lf-trace")
    widget.locator(".lf-trace-input-label").filter(has_text="Click").first.click()
    point = widget.locator(".lf-trace-input-point")
    expect(point).to_be_visible()
    # The intrinsic timeline can put this image below the fold. Bring the
    # recorded pointer into the document viewport before inspecting its clip.
    point.scroll_into_view_if_needed()
    # Make the decorative marker hit-testable to observe the browser's paint clip.
    # Its normal pointer-events:none deliberately lets input reach the capture.
    point.evaluate("node => node.style.pointerEvents = 'auto'")
    assert point.evaluate("""node => {
      const r = node.getBoundingClientRect();
      return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === node;
    }""")
    scale = widget.get_by_role("button", name="Image scale", exact=True)
    expect(scale).to_have_text("Fit")
    scale.focus()
    scale.press("Enter")
    expect(widget.get_by_role("button", name="Fit image", exact=True)).to_be_focused()
    widget.get_by_role("button", name="Actual size", exact=True).click()
    expect(scale).to_have_text("100%")
    expect(scale).to_be_focused()
    scale.press("Enter")
    expect(widget.get_by_role("button", name="Actual size", exact=True)).to_be_focused()
    widget.get_by_role("button", name="Actual size", exact=True).press("Escape")
    expect(scale).to_be_focused()
    canvas = widget.locator(".lf-trace-canvas").filter(visible=True)
    canvas.focus()
    # Leave window above the capture, where the marker goes once panned out of it;
    # focusing the canvas scrolls it to the window's top.
    user.evaluate(
        "() => scrollBy(0, document.querySelector('lf-trace .lf-trace-image-viewport')"
        ".getBoundingClientRect().top - 160)"
    )
    for _ in range(20):
        canvas.press("ArrowUp")
        if point.evaluate("""node => {
          const r = node.getBoundingClientRect();
          const host = node.closest('.lf-trace-image-viewport').getBoundingClientRect();
          return r.bottom < host.top;
        }"""):
            break
    assert point.evaluate("""node => {
      const r = node.getBoundingClientRect();
      const host = node.closest('.lf-trace-image-viewport').getBoundingClientRect();
      const x = r.x + r.width / 2, y = r.y + r.height / 2;
      return r.bottom < host.top && y >= 0 && y < innerHeight
        && document.elementFromPoint(x, y) !== node;
    }""")
    expect(canvas).to_be_focused()
    ring = current_location_ring(user)
    assert ring, "the canvas has no focus ring"
    assert not (faults := ring_faults([ring], "the panned trace canvas")), "\n".join(
        faults
    )


def test_trace_comparison_prepaint_shows_only_its_opening_recording(browser, serve):
    """Holding the chooser module cannot expose a second recording before upgrade.
    A recording in a wrapper, here a <figure> with its caption and no id, shows and
    hides with it, before upgrade, after, and across a reload, which tells the two
    anonymous wrappers apart by the recording inside."""
    source = ROOT / "tests/fixtures/pages/playwright-paired-results.html"
    url = serve(source, packages=("playwright",))
    user = browser.new_page()
    held = []
    user.route("**/widgets/lf-trace-compare.js", lambda route: held.append(route))
    with user.expect_request("**/widgets/lf-trace-compare.js"):
        user.goto(url, wait_until="commit")
    workspace = user.locator("lf-trace-compare")
    user.wait_for_function(
        "() => document.querySelector('lf-trace-compare > [data-lf-opening]')"
    )
    before = workspace.evaluate("""node => ({
        children: [...node.children].map(child => ({
            opening: child.hasAttribute('data-lf-opening'),
            drawn: child.checkVisibility()
        })),
        reserved: parseFloat(getComputedStyle(node, '::before').height)
    })""")
    assert len(before["children"]) == 2
    assert [child["drawn"] for child in before["children"]] == [
        child["opening"] for child in before["children"]
    ]
    assert before["reserved"] >= 44
    assert held
    user.unroute("**/widgets/lf-trace-compare.js")
    for route in held:
        route.continue_()
    wait_until_ready(user)
    user.locator("lf-trace-compare wa-radio").filter(has_text="After").click()
    wrapper = user.locator("figure:has(#paired-after)")
    expect(wrapper.locator("figcaption")).to_be_visible()
    expect(user.locator("#paired-after")).to_be_visible()
    expect(user.locator("#paired-before")).to_be_hidden()
    wait_until_ready(user)
    # Neither wrapper has an id; a reload reopens the chosen one by its recording.
    user.reload()
    wait_until_ready(user)
    expect(wrapper.locator("figcaption")).to_be_visible()
    expect(user.locator("#paired-before")).to_be_hidden()
    user.locator("lf-trace-compare wa-radio").filter(has_text="Before").click()
    expect(wrapper).to_be_hidden()


def test_trace_comparison_shows_each_wrapped_recording_in_one_place(browser, serve):
    """The recording the chooser shows stands where the one it replaced stood, and the
    workspace ends at its foot. A hidden wrapper kept its margins, so choosing After
    moved the recording down by them and the sticky chooser hung over a blank band
    below the workspace."""
    url = serve(
        ROOT / "tests/fixtures/pages/playwright-paired-results.html",
        packages=("playwright",),
    )
    user = open_page(browser, url)
    workspace = user.locator("lf-trace-compare")

    def shown():
        return workspace.evaluate("""node => {
            const view = node.querySelector(':scope > figure:not([hidden])');
            const box = view.getBoundingClientRect();
            return {top: box.top, foot: box.bottom, end: node.getBoundingClientRect().bottom};
        }""")

    before = shown()
    user.get_by_role("radio", name="After", exact=True).click()
    expect(user.locator("#paired-after")).to_be_visible()
    wait_until_ready(user)
    after = shown()
    assert after["top"] == before["top"], (before, after)
    assert [before["end"], after["end"]] == [before["foot"], after["foot"]]

    # A source switch after inspecting a moment must keep the chooser reachable
    # when its controls wrap. Moving its focused native radio into the other view
    # before hiding the old one once scrolled that chooser above a short phone.
    resized(user, 320, 520)
    user.locator("#paired-after .lf-trace-bookmark").click()
    wait_until_ready(user)
    before_radio = user.get_by_role("radio", name="Before", exact=True)
    before_radio.click()
    expect(user.locator("#paired-before")).to_be_visible()
    expect(before_radio).to_be_focused()
    expect(workspace.locator(".lf-trace-compare-controls")).to_be_in_viewport()
    before_radio.press("ArrowRight")
    expect(user.locator("#paired-after")).to_be_visible()
    expect(user.get_by_role("radio", name="After", exact=True)).to_be_focused()
    expect(workspace.locator(".lf-trace-compare-controls")).to_be_in_viewport()


def test_trace_render_gate_restores_the_zoomed_time_window(browser, serve):
    """A zoomed timeline offers no clipped control, and reading it moves nothing."""
    context = browser.new_context(viewport={"width": 480, "height": 520})
    user = open_page(
        browser,
        serve(ROOT / "examples/developer/playwright-trace-gallery.html"),
        context=context,
    )
    widget = user.locator("lf-trace")
    for _ in range(3):
        widget.get_by_role("button", name="Zoom in", exact=True).click()
    rendered(user)
    ruler = widget.locator(".lf-trace-tick-major")

    def time_window():
        return ruler.evaluate_all("""nodes => nodes.map(node => ({
          text: node.textContent, x: node.getBoundingClientRect().x
        }))""")

    before = time_window()
    # Marks outside the zoomed window are drawing, not controls hidden by a clip.
    assert evaluate_probe(user, "clippedControls") == []
    assert time_window() == before


def test_trace_images_stand_at_their_own_capture_times(browser, serve):
    """The image on screen is never captured after the playhead, and calls that
    overlap keep their own rows through every redraw."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    # Make the context's first call overlap the next one.
    calls = sorted(
        (action for action in record["actions"] if not action["input"]),
        key=lambda action: action["startTime"],
    )
    calls[0]["endTime"] = calls[1]["startTime"] + 100
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Capture times",
            '<h1>Capture times</h1><lf-trace id="journey" source="timed-trace"></lf-trace>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "timed-trace", record)
    user = open_page(browser, url)
    resized(user, 1280, 900)
    widget = user.locator("#journey")
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    position = widget.locator(".lf-trace-position")
    selection = widget.locator(".lf-trace-selection")
    rows = "nodes => nodes.map(node => Math.round(node.getBoundingClientRect().top))"
    bars = widget.locator(".lf-trace-call-bar")
    first_rows = bars.evaluate_all(rows)
    assert len(set(first_rows)) == 2, first_rows
    # Step through every stop: a stop shows the image captured at its time or the
    # latest one before it, never a later one.
    timeline.focus()
    timeline.press("Home")
    for _ in range(40):
        rendered(user)
        shown = re.match(r"Image from ([0-9.]+) s", selection.inner_text())
        at = float(position.inner_text().removesuffix(" s"))
        preview = (
            "First capture after this point"
            in widget.locator(".lf-trace-caption").inner_text()
        )
        if shown and not preview:
            assert float(shown[1]) <= at, (shown[1], at)
        before = position.inner_text()
        timeline.press("ArrowRight")
        if position.inner_text() == before:
            break
    assert bars.evaluate_all(rows) == first_rows, "Rows hold through redraws"
    # Scrubbing anywhere shows the latest image at or before the pointer.
    ruler = widget.locator(".lf-trace-ruler").bounding_box()
    for fraction in (0.2, 0.45, 0.6, 0.75, 0.9):
        user.mouse.click(ruler["x"] + ruler["width"] * fraction, ruler["y"] + 8)
        rendered(user)
        shown = re.match(r"Image from ([0-9.]+) s", selection.inner_text())
        at = float(position.inner_text().removesuffix(" s"))
        preview = (
            "First capture after this point"
            in widget.locator(".lf-trace-caption").inner_text()
        )
        if shown and not preview:
            assert float(shown[1]) <= at + 0.0005, (fraction, shown[1], at)


def test_trace_comparison_keeps_native_playback_and_shares_image_inspection(
    browser, serve
):
    """Source switches pause native clocks, while explicit results and image zoom pair."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    actions = [action for action in record["actions"] if action["input"]]
    targets = [
        f"trace-{record['archive']['sha256']}-phase-{action['id']}-after"
        for action in actions
    ]
    bookmarks = "".join(
        f'<lf-trace-bookmark key="result-{index}" label="Result {index + 1}" target="{target}"></lf-trace-bookmark>'
        for index, target in enumerate(targets)
    )
    viewers = "".join(
        f'<lf-trace id="{name}" label="{name.title()}" source="recording">{bookmarks}</lf-trace>'
        for name in ("before", "after")
    )
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Matched progress",
            f'<h1>Matched progress</h1><lf-trace-compare id="pair">{viewers}</lf-trace-compare>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "recording", record)
    user = open_page(browser, url)
    before = user.locator("#before")
    after = user.locator("#after")
    expect(before.get_by_role("button", name="Play", exact=True)).to_be_visible()
    expect(before.locator(".lf-trace-position")).to_be_visible()
    before.get_by_role("button", name="Start", exact=True).click()
    before.get_by_role("button", name="Play", exact=True).click()
    expect(before.get_by_role("button", name="Pause", exact=True)).to_be_visible()
    user.get_by_role("radio", name="After", exact=True).click()
    expect(before.get_by_role("button", name="Pause", exact=True)).to_have_count(0)
    expect(after.get_by_role("button", name="Play", exact=True)).to_be_visible()
    after.locator(".lf-trace-bookmark").last.click()
    for label in ("Before", "After"):
        user.get_by_role("radio", name=label, exact=True).click()
        expect(user.locator(f"#{label.lower()} .lf-trace-phase")).to_have_attribute(
            "data-lf-datum", targets[-1]
        )
    after.get_by_role("button", name="Image scale", exact=True).click()
    after.get_by_role("button", name="Actual size", exact=True).click()
    canvas = after.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .lf-trace-canvas"
    )
    canvas.focus()
    canvas.press("ArrowLeft")

    def image_view(widget):
        return widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        ).evaluate("""image => {
          const r = image.getBoundingClientRect();
          const c = image.closest('.lf-trace-canvas').getBoundingClientRect();
          return {x: r.x - c.x, y: r.y - c.y, width: r.width};
        }""")

    inspected = image_view(after)
    user.get_by_role("radio", name="Before", exact=True).click()
    wait_until_ready(user)
    assert image_view(before) == pytest.approx(inspected, abs=1)
