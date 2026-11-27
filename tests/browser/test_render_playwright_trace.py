"""An external Playwright journey becomes commentable evidence in Leaf."""

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import (
    PREVIEW,
    holding,
    leaf_page,
    open_page,
    preview_text,
    resized,
    told,
)

from leaf.records import page_data as page_data_model
from leaf.source.render_checks import evaluate_probe, rendered, wait_until_ready
from leaf_dev.example_data import named_source
from leaf_dev.page_fixtures import example_media
from leaf_dev.rings import current_location_ring, ring_faults, rings_drawn

ROOT = Path(__file__).resolve().parents[2]


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
    page_data_model.cmd_data_set(serve.page_dir, "trace", record)
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
    page_data_model.cmd_data_set(serve.page_dir, "trace", record)
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
    page_data_model.cmd_data_set(serve.page_dir, "trace", record)
    told(page)
    rerun = source_revision(serve.page_dir, "trace")
    assert rerun != revision
    page.wait_for_function(
        "revision => [...document.querySelectorAll('#journey [data-lf-projection]')]"
        ".every(node => node.dataset.lfSourceRevision === revision)",
        arg=rerun,
    )
    assert [{**part, "revision": rerun} for part in first] == stamps()


# The marks under `[data-test-tip]` the preview covers, each by where the timeline's
# scroller shows it, since one scrolled out of the band stands under nothing: whether it
# covers `pointed`, and which others. Two boxes at one edge can report a hair apart, so
# an overlap thinner than half a layout unit is none.
COVERED_MARKS = """([timeline, pointed]) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  const over = (a, b) => b - a > 1 / 128;
  const covered = [...timeline.querySelectorAll('[data-test-tip]')].filter((mark) => {
    const box = mark.getBoundingClientRect();
    const band = mark.closest('.lf-trace-scroller').getBoundingClientRect();
    const left = Math.max(box.left, band.left), right = Math.min(box.right, band.right);
    return box.width > 0 && over(left, right) && over(left, tip.right)
      && over(tip.left, right) && over(box.top, tip.bottom) && over(tip.top, box.bottom);
  });
  return {own: covered.includes(pointed),
    others: covered.filter((mark) => mark !== pointed).map((mark) => mark.className)};
}"""


@pytest.mark.parametrize(
    ("engine", "width"),
    [
        ("browser", 1400),
        ("firefox_browser", 1400),
        ("browser", 320),
        ("firefox_browser", 320),
    ],
)
def test_timeline_marks_say_their_words_beside_them_inside_the_window(
    request, serve, engine, width
):
    """A timeline's marks each say their whole words when pointed at, in a preview
    whole inside the window that never covers its own mark, at a desktop width and a
    phone's, and after zoom changes which marks stand at the timeline's edges. Each
    mark's preview is about the lane it stands in (timeline.js), so it covers none of
    the lane's other marks, which are thinner than the owner's hit tests are apart. It
    covers another mark only where no side holds a line clear of them, as at the end of
    a phone's input lane, and then says so and lets the pointer through to them
    (annotations/preview.js, `data-lf-covers`).
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
    page_data_model.cmd_data_set(serve.page_dir, "trace", record)
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = open_page(browser, url, context=context)
    widget = page.locator("#journey")
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.scroll_into_view_if_needed()
    # Whether each preview read covers another mark.
    covers = []
    for zoom in (False, True):
        if zoom:
            widget.get_by_role("button", name="Zoom in", exact=True).click()
            rendered(page)
        # Every mark that says something when pointed at (annotations/preview.js).
        timeline.evaluate("""node => [...node.querySelectorAll('*')]
            .forEach((el) => el.toggleAttribute('data-test-tip',
              typeof el.lfPreview === 'function'))""")
        marks = timeline.locator("[data-test-tip]")
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
            tooltip = page.locator(PREVIEW)
            expect(tooltip).to_be_visible()
            rendered(page)
            tip = tooltip.bounding_box()
            assert tip["x"] >= 0
            assert tip["x"] + tip["width"] <= page.viewport_size["width"]
            covered = page.evaluate(
                COVERED_MARKS, [timeline.element_handle(), mark.element_handle()]
            )
            assert not covered["own"], tip
            if covered["others"]:
                expect(tooltip).to_have_attribute("data-lf-covers", "")
                expect(tooltip).to_have_css("pointer-events", "none")
            covers.append(bool(covered["others"]))
            assert tooltip.text_content().strip()
            page.mouse.move(0, 0)
            expect(tooltip).to_be_hidden()
        page.get_by_role("heading", name="Inspect recorded input").hover()
        expect(page.locator(PREVIEW)).to_be_hidden()
    # A desktop width gives every mark's preview a side clear of the other marks.
    if width > 320:
        assert not any(covers), covers


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
        expect(
            widget.get_by_role("button", name="Next capture", exact=True)
        ).to_be_enabled()
        timeline.press("ArrowRight")
    raise AssertionError(f"Native phase not reached: {identity}")


def press_scale(widget, name):
    """Press the choice `name` in `widget`'s open Image scale menu, where it stands.

    The menu hangs from its trigger by CSS anchor positioning, which Chromium moves for
    a scroll only at the page's next rendering update. Below image tools near the
    window's foot, the menu reaches into the root's foot padding (panel/floating-panel.js,
    `followBox`), so Playwright's click scrolls the choice into view and then presses
    where the menu stood before that update. On a slower runner the update comes first,
    the press lands on the page, and the menu closes, as any press outside it does. So
    the choice comes into view, and the page renders the menu there, before the press."""
    choice = widget.get_by_role("button", name=name, exact=True)
    choice.scroll_into_view_if_needed()
    rendered(widget.page)
    choice.click()


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
    page_data_model.cmd_data_set(serve.page_dir, "rtl-trace", record)
    user = open_page(browser, url)
    widget = user.locator("#journey")
    call = widget.locator(f'.lf-trace-call-bar[data-lf-id="{setup["id"]}"]')
    expect(call.locator(".lf-trace-call-name")).to_have_text(setup["method"])
    assert setup["title"] in preview_text(call).replace("\u00a0", " ")
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
    page_data_model.cmd_data_set(serve.page_dir, "review-trace", record)
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


def test_trace_tree_opened_by_the_browser_keeps_its_match(browser, serve):
    """The browser's own opening of a closed tree onto a row keeps that row shown.

    Find-in-page opens a closed disclosure onto its match and scrolls the match into
    view itself, in one task and through no landing of Leaf's. That scroll is the
    reader's, and the shift the opening announces a frame later must not return the
    tree to where the reader left it. Headless Chrome has no find bar, and Leaf
    intercepts a fragment navigation to travel there itself, so the page makes the
    find's two moves: it opens the tree and scrolls the row into view natively. The
    browser's reveal stops at the window's foot rather than above the floating panel,
    as Leaf's landings do, so the row is shown where the browser put it.

    Those two moves are no input of the reader's, so the shift watch judges what they
    move as moving by itself, once the reader's last input has finished rendering. The
    closed tree stands below the window, as a find's match often does, so the opening
    moves nothing the reader sees and the find scrolls the page to the match.
    """
    user, widget, _ = scrolled_closed_tree(browser, serve, "reduce")
    # The reader goes back to the top of the page, which takes focus off the summary.
    user.get_by_role("heading", name="Saved element", level=1).click()
    rendered(user)
    assert widget.locator(".lf-trace-tree").evaluate(
        "tree => tree.getBoundingClientRect().top >= innerHeight"
    )
    user.wait_for_function("() => !lfInputRenderingOpen()")
    revealed = widget.locator(".lf-trace-node").last.evaluate(
        "row => { row.closest('details').open = true;"
        " row.scrollIntoView({block: 'nearest'});"
        " const {top, bottom} = row.getBoundingClientRect(); return [top, bottom]; }"
    )
    landed = user.evaluate(LANDED_ROW)
    user.context.close()
    assert landed["open"]
    assert landed["row"] == pytest.approx(revealed, abs=1), (landed, revealed)


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
    source = named_source("playwright-trace-gallery")
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
    page_data_model.cmd_data_set(serve.page_dir, "before-trace", record)
    user = open_page(browser, url)
    before = user.locator("#before")
    before.locator(".lf-trace-bookmark").click()
    expect(before.locator(".lf-trace-phase")).to_have_attribute(
        "data-lf-datum", targets[0]
    )
    before.get_by_role("button", name=re.compile(r"^Image scale, ")).click()
    press_scale(before, "Actual size")
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
    page_data_model.cmd_data_set(serve.page_dir, "after-trace", record)
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
    page_data_model.cmd_data_set(serve.page_dir, "review-trace", record)
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
    source = named_source("playwright-trace-gallery")
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
    page_data_model.cmd_data_set(serve.page_dir, "hidden-trace", record)
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
    source = named_source("playwright-trace-gallery")
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
    context = browser.new_context(viewport={"width": 1440, "height": 828})
    user = context.new_page()
    user.goto(serve(named_source("playwright-trace-gallery")))
    wait_until_ready(user)
    widget = user.locator("lf-trace")
    widget.get_by_role("button", name="Start", exact=True).click()
    rendered(user)
    # The fitted capture is narrower than its canvas, where centering rules would
    # otherwise reach the playback layer: the window is short enough for the stage's
    # height, not its width, to bound the capture.
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


def test_trace_pointer_annotation_stays_inside_the_panned_image_viewport(
    browser, serve
):
    """Image inspection clips recorded pointer paint at the capture boundary."""
    user = open_page(browser, serve(named_source("playwright-trace-gallery")))
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
    scale = widget.get_by_role("button", name=re.compile(r"^Image scale, "))
    expect(scale).to_have_text("Fit")
    scale.focus()
    scale.press("Enter")
    expect(widget.get_by_role("button", name="Fit image", exact=True)).to_be_focused()
    press_scale(widget, "Actual size")
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


def test_the_selected_input_s_name_wears_its_whole_band(browser, serve):
    """The band around the selected input's name stands whole, read with the timeline
    holding keyboard focus, though the label holding the name clips a long one to an
    ellipsis."""
    user = open_page(browser, serve(named_source("playwright-trace-gallery")))
    widget = user.locator("lf-trace").first
    widget.locator(".lf-trace-input-label").filter(has_text="Click").first.click()
    expect(
        widget.locator(".lf-trace-input-label .lf-trace-word[data-lf-current]")
    ).to_be_visible()
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    user.keyboard.press("Tab")
    user.keyboard.press("Shift+Tab")
    expect(timeline).to_be_focused()
    drawn = rings_drawn(user)
    assert drawn, "the timeline draws no focus mark"
    assert not (faults := ring_faults(drawn, "on the selected input")), "\n".join(
        faults
    )


def test_trace_comparison_shows_each_wrapped_recording_in_one_place(browser, serve):
    """The recording the chooser shows stands where the one it replaced stood, and the
    workspace ends at its foot. A hidden wrapper that kept its margins would move the
    recording down by them as After is chosen, and the sticky chooser would hang over a
    blank band below the workspace."""
    url = serve(
        named_source("playwright-paired-results"),
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
    # before hiding the old one would scroll that chooser above a short phone.
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
        serve(named_source("playwright-trace-gallery")),
        context=context,
    )
    widget = user.locator("lf-trace")
    for _ in range(3):
        widget.get_by_role("button", name="Zoom in", exact=True).click()
    rendered(user)
    ruler = widget.locator(".lf-axis-tick[data-lf-major]")

    def time_window():
        return ruler.evaluate_all("""nodes => nodes.map(node => ({
          text: node.textContent, x: node.getBoundingClientRect().x
        }))""")

    before = time_window()
    # Marks outside the zoomed window are drawing, not controls hidden by a clip.
    assert evaluate_probe(user, "clippedControls") == []
    assert time_window() == before
    # The capture fits its resized viewport before that update paints. A later
    # settled reading hides an old-width image clipped by the new viewport.
    original_width = widget.locator(".lf-trace-canvas").evaluate(
        "node => node.clientWidth"
    )
    widget.evaluate("""node => {
        window.traceFits = [];
        window.traceSize = new ResizeObserver(() => {
            const canvas = node.querySelector('.lf-trace-canvas');
            const viewer = node.querySelector('.viewer-container');
            traceFits.push({canvas: canvas.clientWidth, viewer: viewer.clientWidth});
        });
        traceSize.observe(node.querySelector('.lf-trace-image-viewport'));
    }""")
    resized(user, 390, 520)
    fits = user.evaluate("""() => {
        traceSize.disconnect();
        return traceFits;
    }""")
    assert any(fit["canvas"] < original_width for fit in fits), fits
    assert fits and all(abs(fit["canvas"] - fit["viewer"]) <= 2 for fit in fits), fits


def test_trace_images_stand_at_their_own_capture_times(browser, serve):
    """The image on screen is never captured after the playhead, and calls that
    overlap keep their own rows through every redraw."""
    source = named_source("playwright-trace-gallery")
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
    page_data_model.cmd_data_set(serve.page_dir, "timed-trace", record)
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
    source = named_source("playwright-trace-gallery")
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
    page_data_model.cmd_data_set(serve.page_dir, "recording", record)
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
    after.get_by_role("button", name=re.compile(r"^Image scale, ")).click()
    press_scale(after, "Actual size")
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


def test_trace_reveal_of_a_part_it_lacks_draws_playback_stopped(browser, serve):
    """Travel to a part the recording doesn't hold stops playback, and the Play
    control says so, so its next press starts playback rather than stopping it."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    user = context.new_page()
    user.goto(serve(named_source("playwright-trace-gallery")))
    wait_until_ready(user)
    widget = user.locator("lf-trace").first
    widget.get_by_role("button", name="Start", exact=True).click()
    rendered(user)
    widget.get_by_role("button", name="Play", exact=True).click()
    play = widget.locator(".lf-trace-play")
    expect(play).to_have_attribute("data-lf-playing", "")
    widget.evaluate("widget => widget.lfParts.reveal('trace-0000-action-missing')")
    expect(play).not_to_have_attribute("data-lf-playing", "")
    expect(play).to_have_attribute("aria-label", "Play")
