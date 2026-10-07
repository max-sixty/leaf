"""An external Playwright journey becomes commentable evidence in Leaf."""

import importlib.util
import json
from pathlib import Path

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf.render_checks import rendered, wait_until_ready
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, resized, sending, told

ROOT = Path(__file__).resolve().parents[1]


def test_trace_comments_restore_an_exact_image_and_duplicate_named_element(
    browser, serve, tmp_path
):
    """Capture and review are independent; a draft keeps its original evidence."""
    url = serve(
        leaf_page(
            "Release journey",
            '<h1>Release review</h1><lf-trace id="journey" source="release-trace"></lf-trace>',
            layout="wide",
        ),
        packages=("playwright",),
    )
    directory = serve.page_dir
    context = browser.new_context(viewport={"width": 390, "height": 520})
    context.tracing.start(
        screenshots=True, snapshots=True, screen_snapshots=True, aria_snapshots=True
    )
    capture = context.new_page()
    capture.set_content(
        "<h1>Release</h1><section><h2>Docs</h2>"
        "<button onclick=\"this.nextElementSibling.textContent='Done'\">Review</button>"
        "<output>Pending</output></section><section><h2>API</h2>"
        "<button onclick=\"this.nextElementSibling.textContent='Done'\">Review</button>"
        "<output>Pending</output></section>"
    )
    capture.get_by_role("button", name="Review").nth(0).click()
    capture.get_by_role("button", name="Review").nth(1).click()
    archive = tmp_path / "trace.zip"
    context.tracing.stop(path=archive)
    context.close()

    script = ROOT / "skills/leaf/packages/playwright/scripts/import_trace.py"
    spec = importlib.util.spec_from_file_location("trace_import", script)
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    record = importer.import_trace(
        archive,
        page=directory,
        launcher=ROOT / "bin/leaf",
        viewer_url="https://trace.example/release/",
    )
    data_model.cmd_data_set(directory, "release-trace", record)
    user = open_page(browser, url)
    resized(user, 1440, 900)
    widget = user.locator("#journey")
    expect(widget.get_by_role("link", name="Open in Playwright")).to_have_attribute(
        "href", record["viewerUrl"]
    )
    # A portrait recording retains its native extent on desktop rather than
    # enlarging one heading beyond the evidence viewport.
    raster = widget.locator(".lf-trace-image img")
    expect(raster).to_have_attribute("width", "390")
    assert raster.bounding_box()["width"] <= 390
    # The index keeps native driver times, while the review shows the elapsed
    # stream clock used by Playwright's viewer for this same captured checkpoint.
    first_page = record["pages"][0]
    action = next(
        action for action in record["actions"] if action["pageId"] == first_page["id"]
    )
    checkpoints = sorted(
        [
            (checkpoint["timestamp"], candidate, name)
            for candidate in record["actions"]
            for name, checkpoint in candidate["phases"].items()
            if checkpoint["pageId"] == first_page["id"]
        ],
        key=lambda point: point[0],
    )
    slider = widget.get_by_role("slider", name="Timeline position")
    expect(slider).to_have_attribute("max", str(len(checkpoints) - 1))
    # Navigation walks the native checkpoints rather than calls whose phase
    # has to be selected separately. Choose After for the saved-element comment.
    after_index = next(
        index
        for index, (_, candidate, name) in enumerate(checkpoints)
        if candidate["id"] == action["id"] and name == "after"
    )
    slider.fill(str(after_index))
    # Buttons and native activation use the command's single navigation path.
    # Each gesture must advance exactly once, including at the keyboard.
    next_button = widget.get_by_role("button", name="Next", exact=True)
    previous_button = widget.get_by_role("button", name="Previous", exact=True)
    for activation in ("click", "Enter", "Space"):
        if activation == "click":
            next_button.click()
        else:
            next_button.focus()
            user.keyboard.press(activation)
        expect(slider).to_have_value(str(after_index + 1))
        previous_button.click()
        expect(slider).to_have_value(str(after_index))
    phase = action["phases"]["after"]
    image = next(image for image in record["images"] if image["id"] == phase["imageId"])
    stream = next(
        stream for stream in record["streams"] if stream["id"] == action["stream"]
    )
    # This real capture supplies the context's start clock, before any API call
    # or image. It is the viewer's origin; do not derive expected output from
    # the widget's display helper.
    origin = stream["monotonicTime"]
    assert origin is not None
    elapsed = f"{(image['timestamp'] - origin) / 1000:.3f} s"
    expect(widget.locator(".lf-trace-readout")).to_contain_text(f"checkpoint {elapsed}")
    expect(widget.locator(".lf-trace-phase")).to_have_text(
        f"After · {(phase['timestamp'] - origin) / 1000:.3f} s"
    )
    expect(widget.locator(".lf-trace-clock")).to_have_text(
        "Elapsed since recording started"
    )
    widget.locator(".lf-trace-tree summary").click()
    rendered(user)
    nodes = widget.locator(".lf-trace-node").filter(has_text="button · Review")
    expect(nodes).to_have_count(2)
    second = nodes.nth(1)
    target = second.get_attribute("data-lf-datum")
    second.click(modifiers=["Alt"])
    editor = user.locator(".lf-fab-input")
    expect(editor).to_be_visible()
    user.keyboard.insert_text("The API review button needs explanation.")
    widget.get_by_role("button", name="Next", exact=True).click()
    user.keyboard.press("Escape")
    user.keyboard.press("g")
    user.keyboard.press("i")
    with sending(user, "a comment on the saved API control"):
        user.keyboard.press("Enter")
    comment = next(
        e for e in events_model.read_events(directory) if e["kind"] == "comment"
    )
    assert comment["anchor"]["visual"] == target
    user.keyboard.press("Escape")
    widget.get_by_role("button", name="Next", exact=True).click()
    user.keyboard.press("t")
    expect(widget.locator(f'[data-lf-datum="{target}"]')).to_be_visible()
    expect(widget.locator(".lf-trace-phase")).to_have_text(
        f"After · {(phase['timestamp'] - origin) / 1000:.3f} s"
    )
    user.keyboard.press("Escape")

    frames_toggle = widget.get_by_role("checkbox", name="Show intermediate frames")
    frames_toggle.check()
    points = [
        (time, "phase", candidate["id"], name) for time, candidate, name in checkpoints
    ]
    frames = [
        frame
        for frame in record["images"]
        if frame["kind"] == "frame" and frame["pageId"] == first_page["id"]
    ]
    assert frames, (
        "The native trace must supply intermediate images for this regression"
    )
    points.extend((frame["timestamp"], "image", frame["id"], None) for frame in frames)
    points.sort(key=lambda point: point[0])
    expect(slider).to_have_attribute("max", str(len(points) - 1))
    slider.focus()
    user.keyboard.press("Home")
    # Native range arrows walk both types of evidence in one chronology; each
    # commentable coordinate must be the exact recorded checkpoint or image.
    archive_id = record["archive"]["sha256"]
    slider.fill("0")
    stepper = widget.locator(".lf-trace-stepper")
    readout = widget.locator(".lf-trace-readout")
    caption_top = None
    evidence_top = None
    image_rect = None
    for index, (_, kind, identity, name) in enumerate(points):
        if index:
            user.keyboard.press("ArrowRight")
        expect(slider).to_have_value(str(index))
        coordinate = f"trace-{archive_id}-{kind}-{identity}"
        if kind == "phase":
            coordinate += f"-{name}"
        expect(widget.locator(f'[data-lf-datum="{coordinate}"]')).to_be_visible()
        # The timeline replaces evidence, not the viewport it is read in: neither
        # the image nor the stepper move on screen. Checkpoint metadata and its
        # absence on a frame must not carry the image, and frames and checkpoints
        # share one image box, so what follows the image stands still too.
        rendered(user)
        top = widget.locator(".lf-trace-images").bounding_box()["y"]
        if evidence_top is None:
            evidence_top = top
            stepper_top = stepper.bounding_box()["y"]
        assert abs(top - evidence_top) <= 1, (index, kind, top, evidence_top)
        assert abs(stepper.bounding_box()["y"] - stepper_top) <= 1, (index, kind)
        raster = widget.locator(".lf-trace-image img")
        if raster.count():
            if caption_top is None:
                caption_top = readout.bounding_box()["y"]
            assert abs(readout.bounding_box()["y"] - caption_top) <= 1, (index, kind)
            rect = raster.bounding_box()
            if image_rect is None:
                image_rect = rect
            # JPEG filmstrip dimensions round the native aspect ratio; at the
            # same display width that can change the height by up to two pixels.
            assert all(
                abs(rect[key] - image_rect[key]) <= (2 if key == "height" else 1)
                for key in rect
            ), (
                index,
                kind,
                rect,
                image_rect,
            )
    # At the page's end, a step onto a frame, which has no action or saved elements
    # beneath its image, would shorten the page under the reader. The evidence still
    # starts at the stepper's foot and the stepper stays where it stands.
    actions = {candidate["id"]: candidate for candidate in record["actions"]}
    tall = next(
        index
        for index, (_, kind, identity, name) in enumerate(points[:-1])
        if kind == "phase"
        and actions[identity]["phases"][name]["tree"]["nodes"]
        and points[index + 1][1] == "image"
    )
    user.keyboard.press("Home")
    for _ in range(tall):
        user.keyboard.press("ArrowRight")
    expect(slider).to_have_value(str(tall))
    # Saved elements folded, so the page's end still shows the evidence's foot.
    widget.locator(".lf-trace-tree summary").click()
    expect(widget.locator(".lf-trace-tree")).not_to_have_attribute("open", "")
    slider.focus()
    held = widget.locator(".lf-trace-held")
    user.evaluate("document.scrollingElement.scrollTop = 1e6")
    rendered(user)
    stuck = stepper.bounding_box()
    user.keyboard.press("ArrowRight")
    expect(slider).to_have_value(str(tall + 1))
    rendered(user)
    assert held.bounding_box()["height"] > 0, (
        "the frame must shorten the page at its end for this regression"
    )
    assert stepper.bounding_box()["y"] == pytest.approx(stuck["y"], abs=1)
    assert widget.locator(".lf-trace-images").bounding_box()["y"] == pytest.approx(
        stuck["y"] + stuck["height"], abs=1
    )
    # A later step that doesn't need that room gives it back: no gap stays below
    # the evidence once the reader is elsewhere.
    user.evaluate("document.scrollingElement.scrollTop = 0")
    rendered(user)
    user.keyboard.press("ArrowLeft")
    expect(slider).to_have_value(str(tall))
    rendered(user)
    assert held.bounding_box()["height"] == 0
    frame_index = next(
        index for index, point in enumerate(points) if point[1] == "image"
    )
    user.keyboard.press("Home")
    for _ in range(frame_index):
        user.keyboard.press("ArrowRight")
    expect(slider).to_have_value(str(frame_index))
    image = widget.locator(".lf-trace-image img")
    captured = image.get_attribute("data-lf-datum")
    image.click(modifiers=["Alt"])
    expect(editor).to_be_visible()
    user.keyboard.insert_text("This exact captured frame.")
    with sending(user, "a comment on the original frame"):
        user.keyboard.press("Enter")
    user.keyboard.press("Escape")
    slider.focus()
    user.keyboard.press("End")
    user.keyboard.press("t")
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()
    expect(frames_toggle).to_be_checked()
    user.keyboard.press("Escape")
    # Following the frame includes it even after the reader hides intermediate
    # frames; a node comment returns to its checkpoint without changing capture.
    frames_toggle.uncheck()
    user.keyboard.press("t")
    expect(frames_toggle).to_be_checked()
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()
    # The page is the recording's only scroller: the widget takes its evidence's
    # height, and its stepper sticks over the evidence while the page scrolls
    # through the saved elements beneath it. A thread followed above stands open over
    # the page, wherever its target shows, until a press elsewhere.
    user.locator("h1").click()
    expect(user.locator(".lf-msg:visible")).to_have_count(0)
    frames_toggle.uncheck()
    slider.focus()
    user.keyboard.press("Home")
    for _ in range(after_index):
        user.keyboard.press("ArrowRight")
    expect(slider).to_have_value(str(after_index))
    expect(widget.locator(".lf-trace-node")).not_to_have_count(0)
    widget.locator(".lf-trace-tree summary").click()
    expect(widget.locator(".lf-trace-tree")).to_have_attribute("open", "")
    user.locator("h1").click()
    expect(user.locator(".lf-msg:visible")).to_have_count(0)
    reading = """() => {
      const trace = document.querySelector("#journey");
      const box = (el) => el.getBoundingClientRect();
      const press = box(trace.querySelector(".lf-trace-previous"));
      const hit = document.elementFromPoint(press.x + press.width / 2, press.y + press.height / 2);
      return {
        scrollers: [trace, trace.querySelector(".lf-trace-body")]
          .filter((el) => el.scrollHeight > el.clientHeight + 1
            || /auto|scroll/.test(getComputedStyle(el).overflowY)).length,
        stepper: [box(trace.querySelector(".lf-trace-stepper")).top,
                  box(trace.querySelector(".lf-trace-stepper")).bottom],
        evidence: [box(trace.querySelector(".lf-trace-images")).top,
                   box(trace.querySelector(".lf-trace-images")).bottom],
        pressable: !!hit?.closest(".lf-trace-previous"),
      };
    }"""
    # A landing in the evidence (anchor travel, a thread's target) arrives below the
    # stuck stepper rather than under it, at the layer's own landing operation.
    landing = """async () => {
      const {scrollIntoReadingBand} =
        await window.__lfRuntimeImport("/runtime/landing-scroll.js");
      const trace = document.querySelector("#journey");
      const stepper = trace.querySelector(".lf-trace-stepper");
      const heading = trace.querySelector(".lf-trace-phase");
      const page = document.scrollingElement;
      page.scrollTop += heading.getBoundingClientRect().top
        - stepper.getBoundingClientRect().top - 4;
      const covered =
        heading.getBoundingClientRect().top < stepper.getBoundingClientRect().bottom;
      scrollIntoReadingBand(heading, heading, "start", "instant");
      const landed = heading.getBoundingClientRect();
      const hit = document.elementFromPoint(landed.left + 4, landed.top + 2);
      return {covered, top: landed.top, foot: stepper.getBoundingClientRect().bottom,
              shown: heading.contains(hit)};
    }"""

    def stuck_over_saved_elements():
        widget.locator(".lf-trace-node").last.scroll_into_view_if_needed()
        rendered(user)
        below = user.evaluate(reading)
        assert below["scrollers"] == 0, below
        assert below["pressable"], below
        assert below["evidence"][1] <= below["stepper"][1], (
            "the saved elements must run past the evidence for this regression",
            below,
        )
        landed = user.evaluate(landing)
        assert landed["covered"], landed
        assert landed["top"] >= landed["foot"] - 1, landed
        assert landed["shown"], landed

    # Narrow, too, where the choices above the stepper wrap and scroll away.
    resized(user, 390, 600)
    stuck_over_saved_elements()
    resized(user, 1440, 600)
    stuck_over_saved_elements()
    # Stepping from below the evidence brings the new point's evidence back to the
    # stepper's foot, without moving the stepper under the press.
    widget.locator(".lf-trace-node").last.scroll_into_view_if_needed()
    rendered(user)
    below = user.evaluate(reading)
    widget.get_by_role("button", name="Previous", exact=True).click()
    rendered(user)
    returned = user.evaluate(reading)
    assert returned["stepper"] == pytest.approx(below["stepper"], abs=1), returned
    assert returned["evidence"][0] == pytest.approx(returned["stepper"][1], abs=1), (
        returned
    )
    # Focus moving through the stuck stepper leaves the page where it is: each of
    # its controls counts as shown where it sticks.
    slider.focus()
    user.evaluate("document.scrollingElement.scrollTop += 200")
    rendered(user)
    page_place = user.evaluate("document.scrollingElement.scrollTop")
    for key in ("Tab", "Shift+Tab", "Tab", "Shift+Tab"):
        user.keyboard.press(key)
        assert user.evaluate(
            "document.activeElement.closest('.lf-trace-stepper') !== null"
        ), key
        assert user.evaluate("document.scrollingElement.scrollTop") == page_place, key
    resized(user, 1440, 900)
    # Folding the saved elements at the page's end keeps their summary under the press.
    summary = widget.locator(".lf-trace-tree summary")
    user.evaluate("document.scrollingElement.scrollTop = 1e6")
    rendered(user)
    pressed = summary.bounding_box()["y"]
    summary.click()
    expect(widget.locator(".lf-trace-tree")).not_to_have_attribute("open", "")
    rendered(user)
    assert summary.bounding_box()["y"] == pytest.approx(pressed, abs=1)
    # The room held for that place is given back once the reader scrolls away from it.
    held = widget.locator(".lf-trace-held")
    kept = held.bounding_box()["height"]
    assert kept > 0, "folding at the page's end must hold room for this regression"
    user.evaluate("document.scrollingElement.scrollTop -= 200")
    user.wait_for_function(
        """(kept) => {
          const held = document.querySelector('#journey .lf-trace-held');
          const page = document.scrollingElement;
          const room = held.getBoundingClientRect().height;
          return room < kept
            && (room === 0 || page.scrollHeight - page.clientHeight - page.scrollTop < 1);
        }""",
        arg=kept,
    )
    frames_toggle.check()
    slider.focus()
    user.keyboard.press("Home")
    for _ in range(frame_index):
        user.keyboard.press("ArrowRight")
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()

    # A replacement of the index for the same recording preserves local navigation.
    data_model.cmd_data_set(
        directory,
        "release-trace",
        record | {"viewerUrl": "https://trace.example/updated/"},
    )
    told(user)
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()
    # A trace stream without its context start exposes that its clock begins
    # at the first saved event, rather than claiming the recording's start.
    data_model.cmd_data_set(
        directory,
        "release-trace",
        record
        | {
            "streams": [
                stream | {"monotonicTime": None} for stream in record["streams"]
            ]
        },
    )
    told(user)
    expect(widget.locator(".lf-trace-clock")).to_have_text(
        "Elapsed from first captured event"
    )
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()
    user.keyboard.press("Escape")
    # Ink belongs to the image pixels, not its full-width figure and caption.
    raster.scroll_into_view_if_needed()
    box = raster.bounding_box()
    user.mouse.move(box["x"] + box["width"] * 0.3, box["y"] + box["height"] * 0.3)
    user.keyboard.press("w")
    expect(user.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    user.mouse.down()
    user.mouse.move(
        box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5, steps=8
    )
    user.mouse.up()
    expect(user.locator(".lf-drawing-pending")).to_have_count(1)

    def ink_shares():
        rendered(user)
        return user.evaluate(
            """() => {
              const mark = document.querySelector('.lf-drawing-pending').getBoundingClientRect();
              const image = document.querySelector('.lf-trace-image img').getBoundingClientRect();
              return [(mark.x-image.x)/image.width, (mark.y-image.y)/image.height,
                      mark.width/image.width, mark.height/image.height];
            }"""
        )

    wide_ink = ink_shares()
    assert wide_ink == pytest.approx([0.3, 0.3, 0.2, 0.2], abs=0.01)
    resized(user, 390, 844)
    assert ink_shares() == pytest.approx(wide_ink, abs=0.01)
    user.keyboard.press("Escape")
    assert user.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert (
        raster.bounding_box()["width"]
        <= widget.locator(".lf-trace-body").bounding_box()["width"]
    )
    assert (
        widget.get_by_role("button", name="Next", exact=True).bounding_box()["height"]
        >= 44
    )

    # Native PNG checkpoints are usable without a filmstrip. Conversely a page
    # with only captured frames starts with its actual evidence on screen.
    pngs = [image for image in record["images"] if image["kind"] == "checkpoint"]
    assert pngs
    user.close()
    data_model.cmd_data_set(directory, "release-trace", record | {"images": pngs})
    user = open_page(browser, url)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    frames_toggle = widget.get_by_role("checkbox", name="Show intermediate frames")
    raster = widget.locator(".lf-trace-image img")
    expect(frames_toggle).to_be_disabled()
    expect(slider).to_have_attribute("max", str(len(checkpoints) - 1))
    slider.focus()
    user.keyboard.press("End")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("After")
    expect(raster).to_have_js_property("naturalWidth", 390)

    user.close()
    data_model.cmd_data_set(
        directory, "release-trace", record | {"actions": [], "images": frames}
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    frames_toggle = widget.get_by_role("checkbox", name="Show intermediate frames")
    raster = widget.locator(".lf-trace-image img")
    expect(slider).to_have_attribute("max", str(len(frames) - 1))
    expect(frames_toggle).to_be_disabled()
    expect(widget.locator(".lf-trace-readout")).to_contain_text("Captured frame")
    expect(raster).to_have_js_property("naturalWidth", 390)

    # A frame captured after the last included call is still a useful arrival.
    # Show it as its own timeline point instead of borrowing future pixels for
    # either of that call's earlier Start/Completion stops.
    early_call = action | {"phases": {}}
    late_frame = max(frames, key=lambda frame: frame["timestamp"])
    assert late_frame["timestamp"] > early_call["endTime"]
    user.close()
    data_model.cmd_data_set(
        directory,
        "release-trace",
        record | {"actions": [early_call], "images": [late_frame]},
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    expect(slider).to_have_value("2")
    expect(
        widget.get_by_role("checkbox", name="Show intermediate frames")
    ).to_be_checked()
    expect(widget.locator(".lf-trace-readout")).to_contain_text("Captured frame")
    readout_top = widget.locator(".lf-trace-readout").bounding_box()["y"]
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(slider).to_have_value("1")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Completion")
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    # A stop with no image keeps the image's box and caption row, so what follows
    # stands where it stood beside the frame.
    rendered(user)
    assert widget.locator(".lf-trace-readout").bounding_box()["y"] == pytest.approx(
        readout_top, abs=1
    )

    # Calls without snapshots get their real start/completion stops, without
    # fabricating checkpoint captures or borrowing a future frame.
    fallback_actions = [action | {"phases": {}} for action in record["actions"]]
    user.close()
    data_model.cmd_data_set(
        directory,
        "release-trace",
        record | {"actions": fallback_actions, "images": []},
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    selected_calls = [
        action for action in fallback_actions if action["pageId"] == first_page["id"]
    ]
    stop_count = sum(1 if action["endTime"] is None else 2 for action in selected_calls)
    assert stop_count > 1
    expect(slider).to_have_attribute("max", str(stop_count - 1))
    slider.focus()
    user.keyboard.press("Home")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Start")
    user.keyboard.press("End")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Completion")
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()

    user.close()
    data_model.cmd_data_set(directory, "release-trace", record)
    exported = tmp_path / "recording.html"
    exporting_model.cmd_export(directory, exported, None)
    offline = browser.new_page()
    offline.goto(exported.as_uri(), wait_until="load")
    wait_until_ready(offline)
    expect(offline.locator(".lf-trace-image img")).to_have_js_property(
        "naturalWidth", 390
    )


def test_trace_initial_selection_opens_evidence_and_keeps_earlier_empty_stops(
    browser, serve, tmp_path
):
    """A navigation's empty Before remains reachable, but is not the review's arrival."""
    url = serve(
        leaf_page(
            "Navigation review",
            '<h1>Navigation review</h1><lf-trace id="journey" source="navigation-trace"></lf-trace>'
            + "<section><h2>After the recording</h2>"
            + "<p>The review goes on below the recording.</p>" * 40
            + "</section>",
        ),
        packages=("playwright",),
    )
    directory = serve.page_dir
    context = browser.new_context(viewport={"width": 390, "height": 520})
    context.tracing.start(screenshots=True, snapshots=True, aria_snapshots=True)
    capture = context.new_page()
    capture.goto("data:text/html,<h1>Recorded completion</h1><button>Review</button>")
    archive = tmp_path / "navigation.zip"
    context.tracing.stop(path=archive)
    context.close()

    script = ROOT / "skills/leaf/packages/playwright/scripts/import_trace.py"
    spec = importlib.util.spec_from_file_location("trace_import", script)
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    record = importer.import_trace(
        archive,
        page=directory,
        launcher=ROOT / "bin/leaf",
        viewer_url="https://trace.example/navigation/",
    )
    action = next(action for action in record["actions"] if "goto" in action["title"])
    before = action["phases"]["before"]
    after = action["phases"]["after"]
    assert not before["imageId"] and not before["tree"]["nodes"]
    assert after["tree"]["nodes"], (
        "Navigation completion must supply real review evidence"
    )
    data_model.cmd_data_set(directory, "navigation-trace", record)
    user = open_page(browser, url)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    expect(slider).to_have_value("1")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("After")
    widget.locator(".lf-trace-tree summary").click()
    rendered(user)
    expect(
        widget.locator(".lf-trace-node").filter(has_text="Recorded completion")
    ).to_be_visible()
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(slider).to_have_value("0")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Before")
    earlier_frames = [
        image
        for image in record["images"]
        if image["pageId"] == before["pageId"]
        and image["stream"] == action["stream"]
        and image["timestamp"] <= before["timestamp"]
    ]
    if earlier_frames:
        latest = max(earlier_frames, key=lambda image: image["timestamp"])
        expect(widget.locator(".lf-trace-image img")).to_have_attribute(
            "data-lf-datum", f"trace-{record['archive']['sha256']}-image-{latest['id']}"
        )
    else:
        expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    expect(widget.locator(".lf-trace-nodes li")).to_have_count(0)
    widget.get_by_role("button", name="Next", exact=True).click()
    expect(slider).to_have_value("1")
    expect(
        widget.locator(".lf-trace-node").filter(has_text="Recorded completion")
    ).to_be_visible()
    # A step from the keyboard after the reader has scrolled past the recording
    # leaves the page where they are reading: the stepper parked at the recording's
    # foot covers no evidence.
    slider.focus()
    user.evaluate("document.scrollingElement.scrollTop = 1e6")
    rendered(user)
    assert widget.bounding_box()["y"] + widget.bounding_box()["height"] < 0
    page_place = user.evaluate("document.scrollingElement.scrollTop")
    user.keyboard.press("ArrowLeft")
    expect(slider).to_have_value("0")
    rendered(user)
    assert user.evaluate("document.scrollingElement.scrollTop") == page_place


def test_trace_filmstrip_shares_its_checkpoints_box(browser, serve):
    """Playwright encodes a page's filmstrip at sizes, and even shapes, of its own:
    the gallery's frames are 692x461 and 800x461 between 960x640 checkpoints of one
    viewport. The checkpoints say which viewport the page had, so every frame draws at
    their zoom in their box, and stepping between them moves nothing beneath the
    image."""
    example = ROOT / "examples/developer/playwright-trace-gallery.html"
    data = json.loads(example.with_name(example.stem + ".data.json").read_text())
    images = data["release-journey"]["images"]
    shapes = {round(image["width"] / image["height"], 2) for image in images}
    checkpoint_shapes = {
        round(image["width"] / image["height"], 2)
        for image in images
        if image["kind"] == "checkpoint"
    }
    assert len(checkpoint_shapes) == 1 and len(shapes) > 1, (
        "the gallery's frames must differ in shape from its one viewport's checkpoints"
    )
    user = open_page(browser, serve(example))
    resized(user, 1440, 900)
    widget = user.locator("#release-trace")
    widget.get_by_role("checkbox", name="Show intermediate frames").check()
    slider = widget.get_by_role("slider", name="Timeline position")
    slider.focus()
    user.keyboard.press("Home")
    readout = widget.locator(".lf-trace-readout")
    raster = widget.locator(".lf-trace-image img")
    stops = int(slider.get_attribute("max")) + 1
    first = None
    seen = set()
    for index in range(stops):
        if index:
            user.keyboard.press("ArrowRight")
        expect(slider).to_have_value(str(index))
        rendered(user)
        if not raster.count():
            continue
        seen.add(
            round(
                int(raster.get_attribute("width"))
                / int(raster.get_attribute("height")),
                2,
            )
        )
        reading = (readout.bounding_box()["y"], raster.bounding_box()["width"])
        first = first or reading
        assert reading == pytest.approx(first, abs=1), (index, reading, first)
    assert seen == shapes, "the review must reach frames of every shape"


def test_trace_viewport_change_takes_a_box_of_its_own(browser, serve, tmp_path):
    """A page whose viewport really changes shape mid-recording draws each viewport in a
    box of its own, so a portrait capture never leaves a landscape one standing in
    blank room."""
    url = serve(
        leaf_page(
            "Resized journey",
            '<h1>Resized journey</h1><lf-trace id="journey" source="resized-trace"></lf-trace>',
            layout="wide",
        ),
        packages=("playwright",),
    )
    directory = serve.page_dir
    context = browser.new_context(viewport={"width": 390, "height": 600})
    context.tracing.start(
        screenshots=True, snapshots=True, screen_snapshots=True, aria_snapshots=True
    )
    capture = context.new_page()
    capture.set_content(
        "<h1>Resize</h1><button onclick=\"this.textContent='Done'\">Go</button>"
    )
    capture.get_by_role("button").click()
    capture.set_viewport_size({"width": 900, "height": 450})
    capture.get_by_role("button").click()
    archive = tmp_path / "resized.zip"
    context.tracing.stop(path=archive)
    context.close()
    script = ROOT / "skills/leaf/packages/playwright/scripts/import_trace.py"
    spec = importlib.util.spec_from_file_location("trace_import", script)
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    record = importer.import_trace(
        archive,
        page=directory,
        launcher=ROOT / "bin/leaf",
        viewer_url="https://trace.example/resized/",
    )
    checkpoint_shapes = {
        round(image["width"] / image["height"], 1)
        for image in record["images"]
        if image["kind"] == "checkpoint"
    }
    assert len(checkpoint_shapes) == 2, checkpoint_shapes
    data_model.cmd_data_set(directory, "resized-trace", record)
    user = open_page(browser, url)
    resized(user, 1440, 900)
    widget = user.locator("#journey")
    slider = widget.get_by_role("slider", name="Timeline position")
    slider.focus()
    user.keyboard.press("Home")
    raster = widget.locator(".lf-trace-image img")
    widths = set()
    for index in range(int(slider.get_attribute("max")) + 1):
        if index:
            user.keyboard.press("ArrowRight")
        expect(slider).to_have_value(str(index))
        rendered(user)
        if not raster.count():
            continue
        box = raster.locator("xpath=..").bounding_box()
        widths.add(round(box["width"]))
        assert box["height"] - raster.bounding_box()["height"] <= 2, (index, box)
    assert len(widths) == 2, widths
