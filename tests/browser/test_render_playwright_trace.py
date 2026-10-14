"""An external Playwright journey becomes commentable evidence in Leaf."""

import json
import re
from pathlib import Path

import pytest
from leaf import data as data_model
from leaf.render_checks import evaluate_probe, rendered, wait_until_ready
from leaf_dev.page_fixtures import example_media
from playwright.sync_api import expect
from render_harness import (
    at_rest,
    holding,
    leaf_page,
    open_page,
    resized,
    sending,
    still_page,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.shifts_unsurveyed
def test_trace_viewer_stays_idle_after_initial_presentation(browser, serve):
    """The viewer's disabled transition cannot wake margin layout after readiness."""
    url = serve(ROOT / "examples/developer/playwright-trace-gallery.html")
    assert at_rest(still_page(browser, url)) == []


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
    # Its peer had no data when the reader chose the result.
    data_model.cmd_data_set(serve.page_dir, "after-trace", record)
    user.get_by_role("radio", name="After", exact=True).click()
    after = user.locator("#after")
    expect(after.locator(".lf-trace-phase")).to_have_attribute(
        "data-lf-datum", targets[1]
    )
    expect(after.locator(".lf-trace-bookmark")).to_have_attribute(
        "aria-current", "true"
    )
    wait_until_ready(user)
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


def test_trace_replaces_captures_without_blank_pixels_or_layout_displacement(
    browser, serve
):
    """Delayed native media keeps the old pixels and exact identity until an atomic swap."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    last = [image for image in record["images"] if image["kind"] == "frame"][-1]
    url = serve(source)
    user = browser.new_page()
    held = []
    armed = False

    def gate(route):
        if armed and route.request.url.endswith(last["url"]):
            held.append(route)
        else:
            route.continue_()

    user.route("**/media/**", gate)
    user.goto(url)
    wait_until_ready(user)
    widget = user.locator("lf-trace")
    raster = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )
    widget.get_by_role("button", name="Actual size", exact=True).click()
    canvas = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .lf-trace-canvas"
    )
    canvas.focus()
    canvas.press("ArrowLeft")
    canvas.press("ArrowUp")

    def image_view():
        return raster.evaluate("""image => {
          const r = image.getBoundingClientRect();
          const c = image.closest('.lf-trace-canvas').getBoundingClientRect();
          return {x: r.x - c.x, y: r.y - c.y, width: r.width};
        }""")

    before_view = image_view()
    before_id = raster.get_attribute("data-lf-datum")
    raster.click(modifiers=["Alt"])
    expect(user.locator(".lf-fab-input")).to_be_visible()
    user.keyboard.insert_text("Keep this original captured image.")
    with sending(user, "a comment on the original captured image"):
        user.keyboard.press("Enter")
    user.keyboard.press("Escape")
    target = f"trace-{record['archive']['sha256']}-image-{last['id']}"
    assert before_id != target
    before_caption = widget.locator(".lf-trace-caption").inner_text()
    before_height = widget.locator(".lf-trace-images").bounding_box()["height"]
    user.evaluate("""() => {
      window.captureFrames = [];
      window.watchCapture = true;
      const sample = () => {
        const w = document.querySelector('lf-trace');
        const host = w.querySelector('.lf-trace-images');
        const images = [...host.querySelectorAll('.viewer-canvas img')].filter(i => {
          const style = getComputedStyle(i);
          return style.visibility === 'visible' && i.complete && i.getBoundingClientRect().width > 0;
        });
        window.captureFrames.push({visible: images.length, height: host.getBoundingClientRect().height,
          ids: images.map(i => i.getAttribute('data-lf-datum'))});
        if (window.watchCapture) requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    }""")
    armed = True
    widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="Last filmstrip image"
    ).click()
    holding(user, held, 1, "next captured image")
    # Zooming and panning time must not restore the old image's position while
    # media prepares.
    position = widget.locator(".lf-trace-position")
    requested_position = position.inner_text()
    widget.get_by_role("button", name="Zoom in", exact=True).click()
    rail = widget.locator(".lf-trace-scroller")
    rail.scroll_into_view_if_needed()
    box = rail.bounding_box()
    user.mouse.move(box["x"] + box["width"] * 0.6, box["y"] + box["height"] / 2)
    user.mouse.wheel(-120, 0)
    expect(position).to_have_text(requested_position)
    expect(raster).to_have_attribute("data-lf-datum", before_id)
    expect(widget.locator(".lf-trace-caption")).to_have_text(before_caption)
    assert widget.locator(".lf-trace-images").bounding_box()["height"] == before_height
    user.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    # Following a comment while its pixels remain visible must cancel the
    # pending replacement too; current inventory alone cannot settle navigation.
    user.keyboard.press("t")
    expect(widget.locator(".lf-trace-image-pending")).to_have_count(0)
    armed = False
    for route in held:
        route.continue_()
    rendered(user)
    expect(raster).to_have_attribute("data-lf-datum", before_id)
    user.keyboard.press("Escape")
    widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="Last filmstrip image"
    ).click()
    expect(raster).to_have_attribute("data-lf-datum", target)
    rendered(user)
    after_view = image_view()
    assert all(abs(after_view[key] - value) <= 1 for key, value in before_view.items())
    frames = user.evaluate(
        "() => {window.watchCapture = false; return window.captureFrames}"
    )
    assert len(frames) >= 2
    assert all(
        frame["visible"] == 1 and frame["ids"][0] in (before_id, target)
        for frame in frames
    ), frames
    assert (
        max(frame["height"] for frame in frames)
        - min(frame["height"] for frame in frames)
        <= 1
    ), frames
    expect(widget.locator(".viewer-container")).to_have_count(1)


def test_trace_frames_retain_saved_elements_and_disclosure_stays_closable(
    browser, serve
):
    """A filmstrip capture changes pixels without clearing the last saved tree."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    user = open_page(browser, serve(source))
    widget = user.locator("lf-trace")
    timeline = widget.locator(".lf-trace-timeline")
    action = next(
        action
        for action in record["actions"]
        if action["phases"].get("after", {}).get("tree", {}).get("nodes")
    )
    inputs = [action for action in record["actions"] if action["input"]]
    expect(widget.locator(".lf-trace-input-bar")).to_have_count(len(inputs))
    pointer = next(
        action
        for action in inputs
        if action["input"]["point"] and action["input"]["viewport"]
    )
    navigate_to_phase(
        timeline, f"trace-{record['archive']['sha256']}-phase-{pointer['id']}-after"
    )
    # The After checkpoint names the input it follows rather than suggesting a
    # click is happening; the Input checkpoint precedes its dispatch.
    assert (
        stop_time(record, pointer["phases"]["after"])
        > pointer["phases"]["action"]["timestamp"]
    )
    expect(widget.locator(".lf-trace-input-badge")).to_have_text(
        re.compile(r"^\d+\.\d{3} s · after Click$")
    )
    after = stop_time(record, pointer["phases"]["after"])
    following = min(
        (action for action in inputs if action["startTime"] > after),
        key=lambda action: action["startTime"],
    )
    sent = pointer["phases"]["action"]["timestamp"]
    widget.get_by_role("button", name="Zoom in", exact=True).click()
    widget.get_by_role("button", name="Zoom in", exact=True).click()
    bar = widget.locator(f'.lf-trace-input-bar[data-id="{following["id"]}"]')
    bar.scroll_into_view_if_needed()
    rendered(user)
    first, last = (
        widget.locator(f'.lf-trace-input-bar[data-id="{action["id"]}"]').bounding_box()
        for action in (pointer, following)
    )
    scale = (last["x"] - first["x"]) / (following["startTime"] - pointer["startTime"])
    ruler = widget.locator(".lf-trace-ruler").bounding_box()
    origin = record["streams"][0]["monotonicTime"]

    def stand_at(time):
        user.mouse.click(
            first["x"] + (time - pointer["startTime"]) * scale, ruler["y"] + 8
        )
        rendered(user)
        at = float(widget.locator(".lf-trace-position").inner_text().removesuffix(" s"))
        return at * 1000 + origin

    # Inside the call, before it sends the click, the click is still to come: the
    # image marks nothing, though the Input lane's bar says one is under way.
    assert pointer["startTime"] < stand_at((pointer["startTime"] + sent) / 2) < sent
    expect(widget.locator(".lf-trace-input-badge")).to_be_hidden()
    expect(widget.locator(".lf-trace-input-point")).to_be_hidden()
    # Past the call, the sent click stays marked a moment, so playback at recorded
    # pace shows where it landed.
    gap = (max(after, pointer["endTime"]) + following["startTime"]) / 2
    assert gap < sent + 500
    assert max(after, pointer["endTime"]) < stand_at(gap) < following["startTime"]
    expect(widget.locator(".lf-trace-input-badge")).to_have_text(
        re.compile(r"^\d+\.\d{3} s · after Click$")
    )
    expect(widget.locator(".lf-trace-input-point")).to_be_visible()
    navigate_to_phase(
        timeline, f"trace-{record['archive']['sha256']}-phase-{pointer['id']}-action"
    )
    expect(widget.locator(".lf-trace-input-badge")).to_have_text(
        re.compile(r"^\d+\.\d{3} s · next: Click$")
    )
    expect(widget.locator(".lf-trace-input-point")).to_be_visible()

    def lands_on_its_point(input_action):
        """The recorded pointer's mark stands at its point in the shown capture,
        which scales the viewport by its width whatever its own height."""
        # One read of both: a landing may still be scrolling the page.
        point_box, image_box = widget.evaluate("""widget => [
          widget.querySelector('.lf-trace-input-point'),
          widget.querySelector(
            '.lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img'),
        ].map(node => node.getBoundingClientRect().toJSON())""")
        scale = image_box["width"] / input_action["input"]["viewport"]["width"]
        for axis, size in (("x", "width"), ("y", "height")):
            assert point_box[axis] + point_box[size] / 2 == pytest.approx(
                image_box[axis] + input_action["input"]["point"][axis] * scale, abs=1
            ), (axis, point_box, image_box)

    lands_on_its_point(pointer)
    # Playing, the badge names the input alone: whether the shown image is next to,
    # during or after the call changes faster than it can be read.
    widget.evaluate("""widget => {
      const badge = widget.querySelector('.lf-trace-input-badge');
      window.badgeTexts = [];
      window.badgeWatch = new MutationObserver(() => {
        if (!badge.hidden && widget.querySelector('[data-playing]'))
          window.badgeTexts.push(badge.textContent);
      });
      window.badgeWatch.observe(badge, {
        attributes: true, childList: true, characterData: true, subtree: true,
      });
    }""")
    widget.get_by_role("button", name="Play", exact=True).click()
    expect(widget.locator(".lf-trace-input-badge")).to_have_text("Click")
    user.wait_for_timeout(300)
    widget.get_by_role("button", name="Pause", exact=True).click()
    texts = user.evaluate(
        "() => { window.badgeWatch.disconnect(); return window.badgeTexts }"
    )
    assert texts and set(texts) == {"Click"}, texts
    expect(widget.locator(".lf-trace-input-badge")).to_have_text(
        re.compile(r"^(\d+\.\d{3} s · (during|after) Click)?$")
    )
    # A screencast frame crops the viewport's foot: its height is not the
    # viewport's scaled by its width.
    last_frame = max(
        (image for image in record["images"] if image["kind"] == "frame"),
        key=lambda image: image["timestamp"],
    )
    viewport = pointer["input"]["viewport"]
    assert last_frame["height"] / last_frame["width"] < (
        viewport["height"] / viewport["width"] - 0.05
    )
    widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="Last filmstrip image"
    ).click()
    rendered(user)
    expect(widget.locator(".lf-trace-input-point")).to_be_visible()
    lands_on_its_point(
        max(
            (
                action
                for action in inputs
                if action["input"]["point"]
                and action["phases"]["action"]["timestamp"] <= last_frame["timestamp"]
            ),
            key=lambda action: action["phases"]["action"]["timestamp"],
        )
    )
    phase_id = f"trace-{record['archive']['sha256']}-phase-{action['id']}-after"
    navigate_to_phase(timeline, phase_id)
    summary = widget.locator(".lf-trace-tree summary")
    details = widget.locator(".lf-trace-tree")
    summary.click()
    expect(details).to_have_attribute("open", "")
    count = widget.locator(".lf-trace-node").count()
    assert count > 0
    # Step to a filmstrip frame after this captured tree. Its identity remains
    # the checkpoint that produced it, and the disclosure label never changes.
    timeline.focus()
    for _ in range(100):
        timeline.press("ArrowRight")
        # A frame of another size reads "Image from …" until its Viewer commits.
        if (
            widget.locator(".lf-trace-selection")
            .inner_text()
            .endswith("Captured frame")
        ):
            break
    else:
        raise AssertionError("No captured frame after the populated checkpoint")
    expect(summary).to_have_text("Saved elements")
    assert widget.locator(".lf-trace-node").count() > 0
    summary.click()
    expect(details).not_to_have_attribute("open", "")
    summary.focus()
    user.keyboard.press("Enter")
    expect(details).to_have_attribute("open", "")
    user.keyboard.press("Enter")
    expect(details).not_to_have_attribute("open", "")
    # A stored reading from a scrolled tree must not reopen its disclosure when
    # the user returns to an empty early checkpoint and deliberately closes it.
    timeline.focus()
    timeline.press("End")
    summary.click()
    details.hover()
    user.mouse.wheel(0, 400)
    user.wait_for_function("document.querySelector('lf-trace details').scrollTop > 0")
    rendered(user)
    widget.get_by_role("button", name="Start", exact=True).click()
    rendered(user)
    summary.click()
    rendered(user)
    expect(details).not_to_have_attribute("open", "")
    expect(widget.locator(".lf-trace-caption")).to_contain_text(
        "First capture after this point"
    )


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


def test_trace_play_press_belongs_to_its_pointer_click(browser, serve):
    """A held Pause keeps its meaning; a canceled press leaves keyboard Play free."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    user = browser.new_page()
    user.goto(serve(source))
    wait_until_ready(user)
    widget = user.locator("lf-trace")
    play = widget.get_by_role("button", name="Play", exact=True)
    pause = widget.get_by_role("button", name="Pause", exact=True)
    # Hold the recording clock first: on the wall clock, playback can end before
    # a loaded runner's next click reaches Pause.
    user.clock.install(time=0)
    user.clock.pause_at(1)
    play.click()
    pause.click()
    for canceled in (True, False):
        widget.get_by_role("button", name="Start", exact=True).click()
        play.click()
        expect(pause).to_be_visible()
        box = pause.bounding_box()
        user.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        user.mouse.down()
        if canceled:
            user.mouse.move(box["x"] + box["width"] + 60, box["y"] + 100)
            user.mouse.up()
        # Playback may wait for an image to decode. Let its clock continue after
        # that asynchronous work instead of advancing a fixed span while paused.
        user.clock.resume()
        expect(play).to_be_visible()
        user.clock.pause_at(user.evaluate("() => Date.now() / 1000") + 1)
        if not canceled:
            user.mouse.up()
            expect(play).to_be_visible()
        play.focus()
        play.press("Enter")
        expect(pause).to_be_visible()
        pause.click()


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
    widget.get_by_role("button", name="Actual size", exact=True).click()
    canvas = widget.locator(".lf-trace-canvas").filter(visible=True)
    canvas.focus()
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
    assert canvas.evaluate("""node => {
      const style = getComputedStyle(node);
      return node.matches(':focus-visible') && parseFloat(style.outlineOffset) < 0;
    }""")


def test_trace_comparison_prepaint_shows_only_its_opening_recording(browser, serve):
    """Holding the chooser module cannot expose a second recording before upgrade."""
    source = ROOT / "tests/fixtures/pages/playwright-paired-results.html"
    url = serve(source, packages=("playwright",))
    user = browser.new_page()
    held = []
    user.route("**/widgets/lf-trace-compare.js", lambda route: held.append(route))
    with user.expect_request("**/widgets/lf-trace-compare.js"):
        user.goto(url, wait_until="commit")
    workspace = user.locator("lf-trace-compare")
    user.wait_for_function("() => document.querySelector('lf-trace[data-lf-opening]')")
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
    for route in held:
        route.continue_()
    wait_until_ready(user)
    user.locator("lf-trace-compare wa-radio").filter(has_text="After").click()
    expect(user.locator("#paired-after")).to_be_visible()
    expect(user.locator("#paired-before")).to_be_hidden()
    wait_until_ready(user)


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
    assert evaluate_probe(user, "reachabilityReading")["clipped"] == []
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
