"""An external Playwright journey becomes commentable evidence in Leaf."""

import importlib.util
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
        # The timeline replaces evidence, not the viewport it is read in.
        # Checkpoint metadata and its absence on a frame must not carry the image.
        rendered(user)
        top = widget.locator(".lf-trace-images").bounding_box()["y"]
        top -= widget.locator(".lf-trace-body").bounding_box()["y"]
        if evidence_top is None:
            evidence_top = top
        assert abs(top - evidence_top) <= 1, (index, kind, top, evidence_top)
        raster = widget.locator(".lf-trace-image img")
        if raster.count():
            rect = raster.bounding_box()
            rect["y"] -= widget.locator(".lf-trace-body").bounding_box()["y"]
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
    frame_index = next(
        index for index, point in enumerate(points) if point[1] == "image"
    )
    slider.fill(str(frame_index))
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
    # Following the frame includes it even after the reader hides intermediate
    # frames; a node comment returns to its checkpoint without changing capture.
    user.keyboard.press("Escape")
    body = widget.locator(".lf-trace-body")
    body.hover()
    user.mouse.wheel(0, 80)
    expect(body).not_to_have_js_property("scrollTop", 0)
    frames_toggle.uncheck()
    expect(body).to_have_js_property("scrollTop", 0)
    user.keyboard.press("t")
    expect(frames_toggle).to_be_checked()
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
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(slider).to_have_value("1")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Completion")
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()

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
            '<h1>Navigation review</h1><lf-trace id="journey" source="navigation-trace"></lf-trace>',
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
