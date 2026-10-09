"""An external Playwright journey becomes commentable evidence in Leaf."""

import importlib.util
import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urljoin

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.page_fixtures import example_media
from playwright.sync_api import expect
from render_harness import holding, leaf_page, open_page, resized, sending, told

ROOT = Path(__file__).resolve().parents[1]


def navigate_at(timeline, index):
    """Walk real keyboard routes to the ordered native checkpoint or frame."""
    timeline.focus()
    timeline.press("Home")
    for _ in range(index):
        timeline.press("ArrowRight")
    rendered(timeline.page)


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
    second_capture = context.new_page()
    second_capture.set_content("<h1>Another recorded page</h1>")
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
    raster = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )
    expect(raster).to_have_attribute("width", "390")
    assert raster.bounding_box()["width"] <= 390
    # A recording overview contains context calls and both browser pages.
    # Only actual pages are filters; context calls never become a fake page.
    sources = widget.get_by_role("radiogroup", name="Recording scope")
    expect(sources).to_be_visible()
    overview = widget.get_by_role("radio", name="All pages", exact=True)
    page_source = widget.get_by_role("radio", name="Page 1", exact=True)
    second_page_source = widget.get_by_role("radio", name="Page 2", exact=True)
    expect(overview).to_have_attribute("aria-checked", "true")
    expect(widget.get_by_role("radio")).to_have_count(3)
    timeline = widget.locator(".lf-trace-timeline")
    timeline.focus()
    timeline.press("Home")
    context_call = min(record["actions"], key=lambda action: action["startTime"])
    assert context_call["pageId"] is None
    expect(widget.locator(".lf-trace-action")).to_have_text(context_call["title"])
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    overview.focus()
    overview.press("ArrowRight")
    expect(page_source).to_be_focused()
    expect(page_source).to_have_attribute("aria-checked", "true")
    page_source.press("ArrowRight")
    expect(second_page_source).to_be_focused()
    expect(second_page_source).to_have_attribute("aria-checked", "true")
    expect(
        widget.locator(".lf-trace-node").filter(has_text="Another recorded page")
    ).to_have_count(1)
    page_source.click()
    expect(page_source).to_have_attribute("aria-checked", "true")
    expect(raster).to_have_attribute("width", "390")
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
    timeline = widget.locator(".lf-trace-timeline")
    expect(
        widget.get_by_role("group", name="Recording timeline", exact=True)
    ).to_be_visible()

    # Navigation walks the native checkpoints rather than calls whose phase
    # has to be selected separately. Choose After for the saved-element comment.
    after_index = next(
        index
        for index, (_, candidate, name) in enumerate(checkpoints)
        if candidate["id"] == action["id"] and name == "after"
    )
    navigate_at(timeline, after_index)
    # Buttons and native activation use the command's single navigation path.
    # Each gesture must advance exactly once, including at the keyboard.
    next_button = widget.get_by_role("button", name="Next", exact=True)
    previous_button = widget.get_by_role("button", name="Previous", exact=True)
    for activation in ("click", "Enter", "Space", "ArrowRight"):
        if activation == "click":
            next_button.click()
        elif activation == "ArrowRight":
            timeline.focus()
            user.keyboard.press(activation)
        else:
            next_button.focus()
            user.keyboard.press(activation)
        expect(widget.locator(".lf-trace-position")).to_have_text(
            f"{((checkpoints[after_index + 1][0]) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
        )
        previous_button.click()
        expect(widget.locator(".lf-trace-position")).to_have_text(
            f"{((checkpoints[after_index][0]) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
        )
    # Each source retains its own checkpoint in the composed viewer.
    second_page_source.click()
    expect(second_page_source).to_have_attribute("aria-checked", "true")
    page_source.click()
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((checkpoints[after_index][0]) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
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
    expect(widget.locator(".lf-trace-caption")).to_contain_text(
        f"After checkpoint · {elapsed}"
    )
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
    second_page_source.click()
    user.keyboard.press("t")
    expect(page_source).to_have_attribute("aria-checked", "true")
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

    timeline_control = widget.get_by_role(
        "group", name="Recording timeline", exact=True
    )
    timeline_control.focus()
    expect(timeline_control).to_be_focused()
    user.keyboard.press("Home")
    # Native range arrows walk both types of evidence in one chronology; each
    # commentable coordinate must be the exact recorded checkpoint or image.
    archive_id = record["archive"]["sha256"]
    navigate_at(timeline, 0)
    evidence_top = None
    image_rect = None
    for index, (timestamp, kind, identity, name) in enumerate(points):
        if index:
            user.keyboard.press("ArrowRight")
        expect(widget.locator(".lf-trace-position")).to_have_text(
            f"{((timestamp) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
        )
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
        raster = widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
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
    navigate_at(timeline, frame_index)
    image = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )
    captured = image.get_attribute("data-lf-datum")
    image.click(modifiers=["Alt"])
    expect(editor).to_be_visible()
    user.keyboard.insert_text("This exact captured frame.")
    with sending(user, "a comment on the original frame"):
        user.keyboard.press("Enter")
    user.keyboard.press("Escape")
    timeline_control = widget.get_by_role(
        "group", name="Recording timeline", exact=True
    )
    timeline_control.focus()
    expect(timeline_control).to_be_focused()
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
    rendered(user)
    assert body.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    expect(body).to_have_js_property("scrollTop", 0)
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
              const image = document.querySelector('.lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img').getBoundingClientRect();
              return [(mark.x-image.x)/image.width, (mark.y-image.y)/image.height,
                      mark.width/image.width, mark.height/image.height];
            }"""
        )

    wide_ink = ink_shares()
    assert wide_ink == pytest.approx([0.3, 0.3, 0.2, 0.2], abs=0.01)
    resized(user, 390, 844)
    assert ink_shares() == pytest.approx(wide_ink, abs=0.01)
    user.keyboard.insert_text("Keep this mark on this exact image.")
    with sending(user, "an image drawing comment"):
        user.keyboard.press("ControlOrMeta+Enter")
    drawing = events_model.read_events(directory)[-1]
    assert drawing["kind"] == "comment" and drawing["drawing"]
    assert drawing["anchor"]["visual"] == captured
    posted = user.locator(f'.lf-drawing-posted[data-thread="{drawing["id"]}"]')
    expect(posted).to_have_count(1)
    user.keyboard.press("Escape")
    other_index = next(
        index
        for index, point in enumerate(points)
        if point[1] == "image"
        and f"trace-{record['archive']['sha256']}-image-{point[2]}" != captured
    )
    navigate_at(timeline, other_index)
    expect(
        widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
    ).not_to_have_attribute("data-lf-datum", captured)
    expect(posted).to_have_count(0)
    user.keyboard.press("t")
    expect(widget.locator(f'[data-lf-datum="{captured}"]')).to_be_visible()
    expect(posted).to_have_count(1)
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
    timeline = widget.locator(".lf-trace-timeline")
    frames_toggle = widget.get_by_role("checkbox", name="Show intermediate frames")
    raster = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )
    expect(frames_toggle).to_be_disabled()

    timeline_control = widget.get_by_role(
        "group", name="Recording timeline", exact=True
    )
    timeline_control.focus()
    expect(timeline_control).to_be_focused()
    user.keyboard.press("End")
    expect(widget.locator(".lf-trace-phase")).to_contain_text("After")
    expect(raster).to_have_js_property("naturalWidth", 390)

    user.close()
    data_model.cmd_data_set(
        directory, "release-trace", record | {"actions": [], "images": frames}
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    timeline = widget.locator(".lf-trace-timeline")
    frames_toggle = widget.get_by_role("checkbox", name="Show intermediate frames")
    raster = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )

    expect(frames_toggle).to_be_disabled()
    expect(widget.locator(".lf-trace-selection")).to_contain_text("Captured frame")
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
    timeline = widget.locator(".lf-trace-timeline")
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((late_frame['timestamp']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(
        widget.get_by_role("checkbox", name="Show intermediate frames")
    ).to_be_checked()
    expect(widget.locator(".lf-trace-selection")).to_contain_text("Captured frame")
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((early_call['endTime']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
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
    timeline = widget.locator(".lf-trace-timeline")
    selected_calls = [
        action for action in fallback_actions if action["pageId"] == first_page["id"]
    ]
    stop_count = sum(1 if action["endTime"] is None else 2 for action in selected_calls)
    assert stop_count > 1

    timeline_control = widget.get_by_role(
        "group", name="Recording timeline", exact=True
    )
    timeline_control.focus()
    expect(timeline_control).to_be_focused()
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
    expect(
        offline.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
    ).to_have_js_property("naturalWidth", 390)

    # A terminal capture failure must leave the review and comments usable.
    # Corrupt actual image responses, rather than manufacturing Viewer state.
    broken = browser.new_page()
    broken.route(
        "**/media/**",
        lambda route: route.fulfill(
            status=200, content_type="image/png", body="invalid captured pixels"
        ),
    )
    broken.goto(url)
    wait_until_ready(broken)
    broken_widget = broken.locator("#journey")
    expect(broken_widget.locator(".lf-trace-image-status")).to_be_visible()
    expect(broken_widget.locator(".lf-trace-image-status")).to_have_text(
        "Captured image could not load."
    )
    expect(broken_widget.locator(".viewer-container")).to_have_count(0)
    broken_widget.get_by_role("button", name="Next", exact=True).click()
    rendered(broken)


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
    expect(widget.get_by_role("radiogroup", name="Recording scope")).to_be_hidden()
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((after['timestamp']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(widget.locator(".lf-trace-phase")).to_contain_text("After")
    widget.locator(".lf-trace-tree summary").click()
    rendered(user)
    expect(
        widget.locator(".lf-trace-node").filter(has_text="Recorded completion")
    ).to_be_visible()
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((before['timestamp']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
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
        expect(
            widget.locator(
                ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
            )
        ).to_have_attribute(
            "data-lf-datum", f"trace-{record['archive']['sha256']}-image-{latest['id']}"
        )
    else:
        expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    expect(widget.locator(".lf-trace-nodes li")).to_have_count(0)
    before_height = widget.locator(".lf-trace-images").bounding_box()["height"]
    widget.get_by_role("button", name="Next", exact=True).click()
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((after['timestamp']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(
        widget.locator(".lf-trace-node").filter(has_text="Recorded completion")
    ).to_be_visible()
    rendered(user)
    assert (
        abs(widget.locator(".lf-trace-images").bounding_box()["height"] - before_height)
        <= 1
    )

    # Context operations remain reachable before the page has pixels.
    timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    timeline.press("Home")
    first_call = min(record["actions"], key=lambda candidate: candidate["startTime"])
    assert first_call["pageId"] is None
    expect(widget.locator(".lf-trace-action")).to_have_text(first_call["title"])
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Start")
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    # A trace with no browser page still exposes its real driver-call stops.
    user.close()
    data_model.cmd_data_set(
        directory,
        "navigation-trace",
        record | {"pages": [], "actions": [first_call], "images": []},
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    expect(widget.get_by_role("radiogroup", name="Recording scope")).to_be_hidden()
    expect(widget.locator(".lf-trace-action")).to_have_text(first_call["title"])
    expect(widget.locator(".lf-trace-phase")).to_contain_text("Start")
    widget.get_by_role("button", name="Next", exact=True).click()
    expect(widget.locator(".lf-trace-phase")).to_have_text(
        f"Completion · {(first_call['endTime'] - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()

    # Separate native streams own separate clocks and retained selections.
    # Their times must never be merged into one enormous recording range.
    second_stream = record["streams"][0] | {
        "id": "second-stream",
        "monotonicTime": 100000,
    }
    second_call = first_call | {
        "id": "second-call",
        "stream": second_stream["id"],
        "startTime": 100015,
        "endTime": 100030,
    }
    user.close()
    data_model.cmd_data_set(
        directory,
        "navigation-trace",
        record
        | {
            "streams": [record["streams"][0], second_stream],
            "pages": [],
            "actions": [first_call, second_call],
            "images": [],
        },
    )
    user = open_page(browser, url)
    widget = user.locator("#journey")
    expect(widget.get_by_role("radiogroup", name="Recording scope")).to_be_visible()
    expect(widget.get_by_role("radio")).to_have_count(2)
    first_scope = widget.get_by_role("radio", name="Stream 1", exact=True)
    second_scope = widget.get_by_role("radio", name="Stream 2", exact=True)
    expect(first_scope).to_have_attribute("aria-checked", "true")
    widget.get_by_role("button", name="Next", exact=True).click()
    first_position = widget.locator(".lf-trace-position").inner_text()
    first_scope.focus()
    first_scope.press("ArrowRight")
    expect(second_scope).to_be_focused()
    expect(widget.locator(".lf-trace-position")).to_have_text("0.015 s")
    widget.get_by_role("button", name="Next", exact=True).click()
    expect(widget.locator(".lf-trace-position")).to_have_text("0.030 s")
    first_scope.click()
    expect(widget.locator(".lf-trace-position")).to_have_text(first_position)
    second_scope.click()
    expect(widget.locator(".lf-trace-position")).to_have_text("0.030 s")


def test_trace_bookmarks_jump_to_exact_evidence_in_page_flow(browser, serve):
    """Authored destinations reach phases and filmstrip frames by mouse, key and touch."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    url = serve(source)
    user = open_page(browser, url)
    widget = user.locator("lf-trace")
    actions = [action for action in record["actions"] if "click" in action["title"]]
    origin = record["streams"][0]["monotonicTime"]
    for index, label in enumerate(("Documentation reviewed", "API reviewed")):
        action = actions[index]
        elapsed = (action["phases"]["after"]["timestamp"] - origin) / 1000
        if index:
            button = widget.locator(".lf-trace-bookmarks").get_by_role(
                "button", name=re.compile(re.escape(label))
            )
            button.focus()
            user.keyboard.press("Enter")
        else:
            widget.locator(".lf-trace-markers").get_by_role(
                "button", name=re.compile(re.escape(label))
            ).click()
        expect(widget.locator(".lf-trace-phase")).to_have_text(
            f"After · {elapsed:.3f} s"
        )
        expect(widget.locator(".lf-trace-action")).to_have_text(action["title"])
        coordinate = f"trace-{record['archive']['sha256']}-phase-{action['id']}-after"
        expect(widget.locator(f'[data-lf-datum="{coordinate}"]')).to_be_visible()
    frame = [image for image in record["images"] if image["kind"] == "frame"][-1]
    widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="Last filmstrip image"
    ).click()
    expect(
        widget.get_by_role("checkbox", name="Show intermediate frames")
    ).to_be_checked()
    expect(
        widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
    ).to_have_attribute(
        "data-lf-datum", f"trace-{record['archive']['sha256']}-image-{frame['id']}"
    )
    # The native-resolution view opens the exact selected capture, preserving
    # the timeline cursor and its comment coordinate in the review page.
    raster = widget.locator(
        ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
    )
    native_url = urljoin(user.url, raster.get_attribute("src"))
    full_size = widget.get_by_role("link", name="Open full-size image")
    expect(full_size).to_have_attribute("href", raster.get_attribute("src"))
    with user.expect_popup() as opened:
        full_size.click()
    native_image = opened.value
    native_image.wait_for_load_state("load")
    assert native_image.url == native_url
    expect(native_image.locator("img")).to_have_js_property(
        "naturalWidth", frame["width"]
    )
    expect(native_image.locator("img")).to_have_js_property(
        "naturalHeight", frame["height"]
    )
    expect(raster).to_have_attribute(
        "data-lf-datum", f"trace-{record['archive']['sha256']}-image-{frame['id']}"
    )
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((frame['timestamp']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    native_image.close()
    body = widget.locator(".lf-trace-body")
    assert body.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    phone = open_page(browser, url, context=context)
    phone.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="API reviewed"
    ).tap()
    api_elapsed = (actions[-1]["phases"]["after"]["timestamp"] - origin) / 1000
    expect(phone.locator(".lf-trace-phase")).to_have_text(
        f"After · {api_elapsed:.3f} s"
    )
    assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_trace_transport_scrubs_plays_and_freezes_review_evidence(browser, serve):
    """Mouse and touch transport browse captures; a review gesture freezes its pixels."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    checkpoints = [
        phase["timestamp"]
        for action in record["actions"]
        for phase in action["phases"].values()
        if phase["pageId"] == record["pages"][0]["id"]
    ]
    duration = max(checkpoints) - min(
        action["startTime"] for action in record["actions"]
    )
    url = serve(source)
    for touch in (False, True):
        context = browser.new_context(
            viewport={"width": 390 if touch else 1440, "height": 900},
            has_touch=touch,
            is_mobile=touch,
        )
        user = context.new_page()
        user.goto(url)
        wait_until_ready(user)
        widget = user.locator("lf-trace")
        timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
        position = widget.locator(".lf-trace-position")
        play = widget.get_by_role("button", name="Play", exact=True)
        pause = widget.get_by_role("button", name="Pause", exact=True)
        rendered(user)
        # Navigation stays adjacent to the pixels it changes at either width.
        rail_box = timeline.bounding_box()
        capture_box = widget.locator(".lf-trace-images").bounding_box()
        assert 0 <= capture_box["y"] - (rail_box["y"] + rail_box["height"]) <= 16
        timeline.focus()
        timeline.press("End")
        end = position.inner_text()
        timeline.press("Home")
        beginning = position.inner_text()
        rendered(user)
        user.evaluate("""() => {
          window.startFrames = [];
          window.watchStart = true;
          const sample = () => {
            const w = document.querySelector('lf-trace');
            const host = w.querySelector('.lf-trace-images').getBoundingClientRect();
            const tools = w.querySelector('.lf-trace-image-tools').getBoundingClientRect();
            startFrames.push({height: host.height, tools: tools.top + scrollY});
            if (watchStart) lfWatchPlatform.frame(sample);
          };
          sample();
        }""")
        # Hold product time while native input is delivered. A slow runner cannot
        # turn the Pause the test aims at into Replay before the press arrives.
        user.clock.install(time=0)
        user.clock.pause_at(1)
        play.tap() if touch else play.click()
        expect(pause).to_be_visible()
        user.clock.run_for(round(duration * 0.75))
        expect(position).not_to_have_text(beginning)
        expect(
            widget.locator(
                ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
            )
        ).to_be_visible()
        pause.tap() if touch else pause.click()
        expect(play).to_be_visible()
        user.clock.resume()
        rendered(user)
        paused = position.inner_text()
        frames = user.evaluate("() => {watchStart = false; return startFrames}")
        assert len(frames) >= 2
        for key in ("height", "tools"):
            values = [frame[key] for frame in frames]
            assert max(values) - min(values) <= 1, frames
        expect(position).to_have_text(paused)
        play.tap() if touch else play.click()
        expect(play).to_be_visible()
        expect(position).to_have_text(end)
        user.clock.pause_at(user.evaluate("Date.now() / 1000") + 1)
        play.tap() if touch else play.click()
        expect(pause).to_be_visible()
        user.clock.run_for(round(duration * 0.75))
        widget.get_by_role("button", name="Next", exact=True).click()
        expect(play).to_be_visible()
        user.clock.resume()

        # The visible handle, rather than blank-space pan, changes evidence.
        timeline.press("Home")
        widget.get_by_role("button", name="Whole recording", exact=True).click()
        timeline.scroll_into_view_if_needed()
        handle = widget.locator(".vis-custom-time.selection > div").bounding_box()
        rail = widget.locator(".vis-panel.vis-center").bounding_box()
        before_scrub = position.inner_text()
        start = {
            "x": handle["x"] + handle["width"] / 2,
            "y": handle["y"] + handle["height"] / 2,
        }
        finish = {"x": rail["x"] + rail["width"] * 0.75, "y": start["y"]}
        if touch:
            cdp = context.new_cdp_session(user)
            cdp.send(
                "Input.dispatchTouchEvent",
                {"type": "touchStart", "touchPoints": [start]},
            )
            for index in range(1, 11):
                point = {
                    "x": start["x"] + (finish["x"] - start["x"]) * index / 10,
                    "y": start["y"],
                }
                cdp.send(
                    "Input.dispatchTouchEvent",
                    {"type": "touchMove", "touchPoints": [point]},
                )
            cdp.send(
                "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}
            )
            cdp.detach()
        else:
            user.mouse.move(**start)
            user.mouse.down()
            user.mouse.move(**finish, steps=10)
            user.mouse.up()
        expect(position).not_to_have_text(before_scrub)
        rendered(user)
        expect(play).to_be_visible()

        # Wheel engagement with the point inspector freezes its contents while
        # leaving the browser responsible for scrolling its saved-element tree.
        if not touch:
            user.clock.pause_at(user.evaluate("Date.now() / 1000") + 1)
            play.click()
            expect(pause).to_be_visible()
            metadata = widget.get_by_role("group", name="Selected point details")
            metadata.scroll_into_view_if_needed()
            box = metadata.bounding_box()
            user.mouse.move(box["x"] + box["width"] / 2, box["y"] + 30)
            user.mouse.wheel(0, 100)
            expect(play).to_be_visible()
            user.clock.resume()
            rendered(user)
            frozen = position.inner_text()
            rendered(user)
            expect(position).to_have_text(frozen)

        # Starting a drawing with the ordinary W route freezes the captured image
        # before ink samples arrive; comments keep that immutable image identity.
        timeline.focus()
        timeline.press("Home")
        user.clock.pause_at(user.evaluate("Date.now() / 1000") + 1)
        play.tap() if touch else play.click()
        expect(pause).to_be_visible()
        pause.press("w")
        expect(play).to_be_visible()
        user.clock.resume()
        rendered(user)
        frozen = position.inner_text()
        rendered(user)
        expect(position).to_have_text(frozen)
        user.keyboard.press("Escape")


def test_trace_inspection_survives_playback_gaps_and_scope_changes(browser, serve):
    """Playback, empty points and renderer replacement retain the user's inspection."""
    from render_harness import scroll_settled

    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    # A second recorded tab has no captured calls yet. It still distinguishes
    # the overview from the first page for the inspection restoration journey.
    first_page = record["pages"][0]
    record["pages"].append(
        first_page | {"id": first_page["id"] + "-second", "pageId": "page@second"}
    )
    # Native traces can have a saved tree before any screenshot. Keep this real
    # recording's clocks and media, but leave that checkpoint without its PNG.
    first = next(action for action in record["actions"] if action["phases"])
    first["phases"]["before"]["imageId"] = None
    url = serve(source)
    data_model.cmd_data_set(serve.page_dir, "release-journey", record)
    for touch in (False, True):
        context = browser.new_context(
            viewport={"width": 390 if touch else 1440, "height": 900},
            has_touch=touch,
            is_mobile=touch,
        )
        user = open_page(browser, url, context=context)
        widget = user.locator("lf-trace")
        # Exercise classic scrollbars' real inner-width loss on macOS too,
        # in both the bounded point inspector and its expanded saved tree.
        user.add_style_tag(
            content=".lf-trace-metadata::-webkit-scrollbar, "
            ".lf-trace-tree::-webkit-scrollbar {width: 15px; height: 15px}"
        )
        timeline = widget.get_by_role("group", name="Recording timeline", exact=True)
        widget.get_by_role("checkbox", name="Show intermediate frames").check()
        timeline.focus()
        timeline.press("End")
        rendered(user)
        for _ in range(2):
            widget.get_by_role("button", name="Zoom image in", exact=True).click()
        canvas = widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .lf-trace-canvas"
        )
        canvas.focus()
        canvas.press("ArrowLeft")
        canvas.press("ArrowUp")
        for _ in range(3):
            widget.get_by_role("button", name="Zoom in", exact=True).click()
        rendered(user)
        user.evaluate("""() => {
          window.inspectionFrames = [];
          window.inspectionWindows = [];
          window.inspectionDisclosures = [];
          window.inspectionTargets = [];
          window.inspectionReadouts = [];
          window.inspectionGapTargets = [];
          window.watchInspection = true;
          window.inspectionWindow = () => {
            const w = document.querySelector('lf-trace');
            const rail = w.querySelector('.vis-panel.vis-center').getBoundingClientRect();
            const ticks = [...w.querySelectorAll('.vis-text.vis-minor:not(.vis-measure)')]
              .map(e => ({time: parseFloat(e.textContent), x: e.getBoundingClientRect().x}))
              .sort((a, b) => a.x - b.x);
            const unit = (ticks[1].time - ticks[0].time) / (ticks[1].x - ticks[0].x);
            return {start: ticks[0].time + (rail.x - ticks[0].x) * unit,
              span: rail.width * unit};
          };
          window.inspectionView = () => {
            const w = document.querySelector('lf-trace');
            const canvas = w.querySelector('.lf-trace-image:not(.lf-trace-image-pending) .lf-trace-canvas');
            const image = canvas?.querySelector('.viewer-canvas img');
            if (!image) return null;
            const r = image.getBoundingClientRect(), c = canvas.getBoundingClientRect();
            return {width: r.width / canvas.clientWidth,
              x: (r.x - c.x - canvas.clientLeft) / canvas.clientWidth,
              y: (r.y - c.y - canvas.clientTop) / canvas.clientWidth};
          };
          const sample = () => {
            inspectionFrames.push(inspectionView());
            inspectionWindows.push(inspectionWindow());
            const summary = document.querySelector('lf-trace .lf-trace-tree summary');
            const inspector = summary.closest('.lf-trace-metadata');
            inspectionDisclosures.push({
              visible: summary.checkVisibility(),
              top: summary.getBoundingClientRect().top - inspector.getBoundingClientRect().top
                + inspector.scrollTop,
            });
            const action = inspector.querySelector('.lf-trace-action');
            const phase = inspector.querySelector('.lf-trace-phase');
            inspectionReadouts.push(inspector.querySelector('.lf-trace-readout')
              .getBoundingClientRect().height);
            if (action.checkVisibility({visibilityProperty: true})
              && phase.checkVisibility({visibilityProperty: true})) {
              const top = node => node.getBoundingClientRect().top
                - inspector.getBoundingClientRect().top + inspector.scrollTop;
              inspectionTargets.push({
                actionTop: top(action), phaseTop: top(phase),
                actionViewTop: top(action) - inspector.scrollTop,
                phaseViewTop: top(phase) - inspector.scrollTop,
                treeHeight: inspector.querySelector('.lf-trace-tree')
                  .getBoundingClientRect().height,
                treeNodes: inspector.querySelectorAll('.lf-trace-node').length,
                action: action.getAttribute('data-lf-datum'),
                phase: phase.getAttribute('data-lf-datum'),
                title: action.textContent,
                runtimeOwned: !!action.closest('[data-lf-runtime]')
                  || !!phase.closest('[data-lf-runtime]'),
              });
            } else {
              inspectionGapTargets.push([
                action.getAttribute('data-lf-datum'),
                phase.getAttribute('data-lf-datum'),
              ]);
            }
            if (watchInspection) requestAnimationFrame(sample);
          };
          window.sampleInspection = sample;
          sample();
        }""")
        before = user.evaluate("inspectionView()")
        before_window = user.evaluate("inspectionWindow()")
        assert before["width"] > 1.4
        user.evaluate("window.dispatchEvent(new Event('resize'))")
        rendered(user)
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        user.evaluate("() => {inspectionFrames.length = 0; inspectionWindows.length = 0}")
        play = widget.get_by_role("button", name="Play", exact=True)
        play.tap() if touch else play.click()
        expect(widget.get_by_role("button", name="Pause", exact=True)).to_be_visible()
        expect(play).to_be_visible()
        rendered(user)
        samples = user.evaluate(
            "() => {watchInspection = false; return inspectionFrames}"
        )
        assert any(sample is None for sample in samples), (
            "Replay must cross the empty first point"
        )
        assert all(
            sample == pytest.approx(before, abs=0.003) for sample in samples if sample
        )
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        assert all(
            window == pytest.approx(before_window, abs=0.005)
            for window in user.evaluate("inspectionWindows")
        )
        disclosures = user.evaluate("inspectionDisclosures")
        assert all(sample["visible"] for sample in disclosures)
        assert all(
            sample["top"] == pytest.approx(disclosures[0]["top"], abs=1)
            for sample in disclosures
        ), "Saved elements must keep its place through frame and checkpoint stops"
        targets = user.evaluate("inspectionTargets")
        assert len({sample["phase"] for sample in targets}) > 1
        assert all(
            (sample["actionTop"], sample["phaseTop"])
            == pytest.approx((targets[0]["actionTop"], targets[0]["phaseTop"]), abs=1)
            for sample in targets
        ), "Timeline changes must not move commentable action/phase targets"
        readouts = user.evaluate("inspectionReadouts")
        assert all(
            height == pytest.approx(readouts[0], abs=1) for height in readouts
        ), "Point counters must keep their extent through frames and checkpoints"
        gaps = user.evaluate("inspectionGapTargets")
        assert gaps and all(targets == [None, None] for targets in gaps), (
            "Filmstrip gaps must not expose retained action/phase semantic targets"
        )
        archive = record["archive"]["sha256"]
        actions = {
            f"trace-{archive}-action-{action['id']}": action
            for action in record["actions"]
        }
        assert all(
            sample["action"] in actions
            and sample["title"] == actions[sample["action"]]["title"]
            and sample["phase"].startswith(
                f"trace-{archive}-phase-{actions[sample['action']]['id']}-"
            )
            and not sample["runtimeOwned"]
            for sample in targets
        ), (
            "Imported evidence must retain its archive target rather than runtime ownership"
        )

        # An expanded tree owns its scrolling. Replacing the zero-node Before
        # tree with the populated After tree must not carry the same action's
        # comment target down the outer inspector.
        tree = widget.locator(".lf-trace-tree")
        summary = tree.locator("summary")
        summary.click()
        summary.focus()
        summary.press("PageDown")
        user.wait_for_function(
            "document.querySelector('lf-trace .lf-trace-tree').scrollTop > 0"
        )
        scroll_settled(user, ".lf-trace-tree")
        rendered(user)
        widget.locator(".lf-trace-phase").scroll_into_view_if_needed()
        rendered(user)
        tree_place = tree.evaluate("node => node.scrollTop")
        tree_phase = widget.locator(".lf-trace-phase").get_attribute("data-lf-datum")
        user.evaluate("""() => {
          inspectionTargets = [];
          watchInspection = false;
          sampleInspection();
        }""")
        # Real-time playback can skip a short checkpoint between frames. Visit
        # both saved trees explicitly so their layout comparison always runs.
        frames = widget.get_by_role("checkbox", name="Show intermediate frames")
        frames.uncheck()
        navigate_at(timeline, 0)
        for phase in ("before", "after"):
            target = f"trace-{archive}-phase-{first['id']}-{phase}"
            # The overview also contains browser setup calls. Walk the native
            # points until this saved tree, rather than assuming page-only indices.
            while (
                widget.locator(".lf-trace-phase").get_attribute("data-lf-datum")
                != target
            ):
                expect(
                    widget.get_by_role("button", name="Next", exact=True)
                ).to_be_enabled()
                timeline.press("ArrowRight")
                rendered(user)
            expect(widget.locator(".lf-trace-phase")).to_have_attribute(
                "data-lf-datum", target
            )
            expect(tree.locator(".lf-trace-node")).to_have_count(
                len(first["phases"][phase]["tree"]["nodes"])
            )
            user.evaluate("sampleInspection()")
        timeline.press("End")
        frames.check()
        rendered(user)
        user.evaluate("() => {watchInspection = true; sampleInspection()}")
        # Keep the inspected viewport while pressing the visible sticky Play
        # control; locator activation can scroll before it delivers input.
        box = play.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        assert play.evaluate(
            "(node, point) => node.contains(document.elementFromPoint(...point))",
            [x, y],
        )
        user.touchscreen.tap(x, y) if touch else user.mouse.click(x, y)
        expect(widget.get_by_role("button", name="Pause", exact=True)).to_be_visible()
        expect(play).to_be_visible()
        rendered(user)
        expanded = user.evaluate(
            "() => {watchInspection = false; return inspectionTargets}"
        )
        expect(widget.locator(".lf-trace-phase")).to_have_attribute(
            "data-lf-datum", tree_phase
        )
        assert tree.evaluate("node => node.scrollTop") == pytest.approx(
            tree_place, abs=1
        ), "Returning to the same saved tree must restore its inspected scroll position"
        assert all(
            (sample["actionViewTop"], sample["phaseViewTop"], sample["treeHeight"])
            == pytest.approx(
                (
                    expanded[0]["actionViewTop"],
                    expanded[0]["phaseViewTop"],
                    expanded[0]["treeHeight"],
                ),
                abs=1,
            )
            for sample in expanded
        ), (
            "Expanded saved trees must not move adjacent commentable targets: "
            f"{sorted({(s['actionViewTop'], s['phaseViewTop'], s['treeHeight']) for s in expanded})}"
        )
        assert any(
            len(
                {
                    sample["treeNodes"]
                    for sample in expanded
                    if sample["action"] == action
                }
            )
            > 1
            for action in {sample["action"] for sample in expanded}
        ), (
            "Expanded inspection must replace differently sized trees for the same action"
        )
        summary.click()
        rendered(user)

        # Rendering empty time, returning from the overview and resizing the page
        # cannot redefine the inspection. Fit is an explicit user action.
        timeline.focus()
        timeline.press("Home")
        expect(widget.locator(".viewer-canvas img")).to_have_count(0)
        timeline.press("End")
        rendered(user)
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        # A panned window also survives metadata redraws and scope replacement.
        rail = widget.locator(".vis-panel.vis-center").bounding_box()
        user.mouse.move(rail["x"] + rail["width"] * 0.6, rail["y"] + 12)
        user.mouse.down()
        user.mouse.move(rail["x"] + rail["width"] * 0.35, rail["y"] + 12, steps=8)
        user.mouse.up()
        rendered(user)
        panned = user.evaluate("inspectionWindow()")
        widget.locator(".lf-trace-tree summary").click()
        rendered(user)
        assert user.evaluate("inspectionWindow()") == pytest.approx(panned, abs=0.005)
        ticks = widget.locator(
            ".vis-text.vis-minor:not(.vis-measure)"
        ).all_text_contents()
        widget.get_by_role("radio", name="Page 1", exact=True).click()
        widget.get_by_role("radio", name="All pages", exact=True).click()
        rendered(user)
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        assert (
            widget.locator(".vis-text.vis-minor:not(.vis-measure)").all_text_contents()
            == ticks
        )
        assert user.evaluate("inspectionWindow()") == pytest.approx(panned, abs=0.005)
        timeline.focus()
        timeline.press("Home")
        rendered(user)
        handle = widget.locator(".vis-custom-time").bounding_box()
        rail = widget.locator(".vis-panel.vis-center").bounding_box()
        assert rail["x"] <= handle["x"] <= rail["x"] + rail["width"]
        timeline.press("End")
        rendered(user)
        resized(user, 390 if touch else 1440, 650)
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        resized(user, 500 if touch else 1000, 900)
        assert user.evaluate("inspectionView()") == pytest.approx(before, abs=0.003)
        widget.get_by_role("button", name="Fit image", exact=True).click()
        rendered(user)
        fitted = user.evaluate("inspectionView()")
        assert fitted["width"] == pytest.approx(1, abs=0.01)
        timeline.focus()
        timeline.press("Home")
        timeline.press("End")
        rendered(user)
        assert user.evaluate("inspectionView()") == pytest.approx(fitted, abs=0.003)


def test_trace_zoom_and_pan_stay_within_the_fitted_recording(browser, serve):
    """Repeated buttons, wheel zoom and drags cannot lose a short recording."""
    url = serve(ROOT / "examples/developer/playwright-trace-gallery.html")
    user = open_page(browser, url)
    widget = user.locator("lf-trace")
    rail = widget.locator(".vis-panel.vis-center")

    def visible_ticks():
        return widget.locator(".vis-text.vis-minor:not(.vis-measure)").evaluate_all(
            """nodes => nodes.filter(node => {
                const box = node.getBoundingClientRect();
                const rail = node.closest('.vis-timeline').getBoundingClientRect();
                return box.left >= rail.left && box.left < rail.right;
            }).map(node => Number.parseFloat(node.textContent))"""
        )

    for width in (1440, 390):
        resized(user, width, 900)
        widget.get_by_role("button", name="Whole recording", exact=True).click()
        rendered(user)
        overview = visible_ticks()
        overview_labels = widget.locator(
            ".vis-text.vis-minor:not(.vis-measure)"
        ).all_text_contents()
        assert len(overview) > 1
        assert min(overview) == 0, "The whole recording starts at zero"
        overview_span = max(overview) - min(overview)
        widget.get_by_role("button", name="Zoom in", exact=True).click()
        rendered(user)
        detail = visible_ticks()
        assert max(detail) - min(detail) < overview_span

        selection = widget.locator(".lf-trace-position").inner_text()
        rail.scroll_into_view_if_needed()
        box = rail.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] - 10
        panned = False
        for direction in (-1, 1):
            before_pan = visible_ticks()
            user.mouse.move(x, y)
            user.mouse.down()
            user.mouse.move(x + direction * box["width"] / 3, y, steps=20)
            user.mouse.up()
            rendered(user)
            panned |= visible_ticks() != before_pan
            expect(widget.locator(".lf-trace-position")).to_have_text(selection)
        assert panned, "Detail dragging must pan without selecting another capture"

        for _ in range(16):
            widget.get_by_role("button", name="Zoom out", exact=True).click()
            rendered(user)
        assert visible_ticks() == overview

        for _ in range(8):
            widget.get_by_role("button", name="Zoom in", exact=True).click()
            rendered(user)
        close_labels = widget.locator(
            ".vis-text.vis-minor:not(.vis-measure)"
        ).all_text_contents()
        assert len(close_labels) == len(set(close_labels)), (
            "Close zoom must distinguish millisecond ticks"
        )
        widget.get_by_role("button", name="Whole recording", exact=True).click()
        rendered(user)

        # Zoom can change tick spacing without changing which seconds are
        # labelled, particularly on a narrow ruler starting exactly at zero.
        tick = widget.locator(".vis-text.vis-minor:not(.vis-measure)").nth(1)
        overview_tick_style = tick.get_attribute("style")
        overview_tick_width = tick.bounding_box()["width"]
        box = rail.bounding_box()
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] - 10
        user.mouse.move(x, y)
        user.keyboard.down("Control")
        user.mouse.wheel(0, -500)
        expect(tick).not_to_have_attribute("style", overview_tick_style)
        user.keyboard.up("Control")
        rendered(user)
        # An oversized reverse gesture must stop at the whole recording.
        user.mouse.move(x, y)
        user.keyboard.down("Control")
        user.mouse.wheel(0, 10000)
        expect(widget.locator(".vis-text.vis-minor:not(.vis-measure)")).to_have_text(
            overview_labels
        )
        user.keyboard.up("Control")
        rendered(user)
        assert abs(tick.bounding_box()["width"] - overview_tick_width) < 1
        assert visible_ticks() == overview

        for direction in (-1, 1):
            user.mouse.move(x, y)
            user.mouse.down()
            user.mouse.move(x + direction * box["width"] * 3, y, steps=5)
            user.mouse.up()
            rendered(user)
            assert visible_ticks() == overview
        pins = widget.locator(".lf-trace-marker")
        expect(pins).to_have_count(3)
        assert sorted(pins.all_text_contents()) == ["1", "2", "3"]
        widget.locator(".lf-trace-markers").get_by_role(
            "button", name=re.compile(r"^Moment 3 ·")
        ).click()
        expect(widget.locator(".lf-trace-selection")).to_contain_text("Moment 3")


def test_trace_dense_moments_keep_the_axis_usable_and_page_scoped(browser, serve):
    """Long and coincident labels disclose in page flow without enlarging the time axis."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    record = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    first_page = record["pages"][0]
    record["pages"].append(
        first_page | {"id": first_page["id"] + "-second", "pageId": "page@second"}
    )
    archive = record["archive"]["sha256"]
    page = record["pages"][0]
    checkpoints = [
        (f"trace-{archive}-phase-{action['id']}-{name}", phase["timestamp"])
        for action in record["actions"]
        for name, phase in action["phases"].items()
        if phase["pageId"] == page["id"]
    ]
    frames = [
        image
        for image in record["images"]
        if image["kind"] == "frame" and image["pageId"] == page["id"]
    ]
    assert checkpoints and frames
    last_frame = max(frames, key=lambda image: image["timestamp"])
    frame_target = f"trace-{archive}-image-{last_frame['id']}"
    labels = [
        f"Review condition {chr(65 + index)}: inspect the documentation and API evidence with a long explanatory label"
        for index in range(20)
    ]
    # Several separately authored moments share one exact native point. Their
    # labels must remain independently reachable through separate native buttons.
    targets = [checkpoints[index % len(checkpoints)][0] for index in range(19)]
    targets.append(frame_target)
    api = next(
        action
        for action in record["actions"]
        if action["pageId"] is None and not action["phases"]
    )
    api_target = f"trace-{archive}-phase-{api['id']}-end"
    members = "".join(
        f'<lf-trace-bookmark label="{escape(label, quote=True)}" target="{target}"></lf-trace-bookmark>'
        for label, target in zip(labels, targets, strict=True)
    )
    members += f'<lf-trace-bookmark label="Recording setup complete" target="{api_target}"></lf-trace-bookmark>'
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Dense trace review",
            f'<h1>Dense trace review</h1><lf-trace id="journey" source="dense-trace">{members}</lf-trace>',
            layout="wide",
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "dense-trace", record)
    user = open_page(browser, url)
    resized(user, 1440, 900)
    widget = user.locator("#journey")
    widget.get_by_role("radio", name="Page 1", exact=True).click()
    summary = widget.locator(".lf-trace-moments-heading")
    expect(summary).to_have_text("Moments (20)")
    lane = widget.locator(".lf-trace-markers")

    def bounded_marks():
        rendered(user)
        # The ruler, dedicated 44px scrub row, and space for three moment rows
        # stay bounded despite twenty moments (244px plus rounding tolerance).
        assert lane.locator(".vis-timeline").bounding_box()["height"] <= 246
        boxes = widget.locator(".lf-trace-marker").evaluate_all(
            "nodes => nodes.map(node => {const box = node.getBoundingClientRect(); return {x: box.x, y: box.y, width: box.width, height: box.height};}).filter(box => box.width && box.height)"
        )
        assert boxes, "Dense authored moments must remain present on the time axis"
        assert all(box["width"] >= 43.99 and box["height"] >= 43.99 for box in boxes), [
            box for box in boxes if box["width"] < 43.99 or box["height"] < 43.99
        ]
        assert (
            max(box["width"] for box in boxes) - min(box["width"] for box in boxes) <= 1
        )
        assert all(
            left["x"] + left["width"] <= right["x"] + 1
            or right["x"] + right["width"] <= left["x"] + 1
            or left["y"] + left["height"] <= right["y"] + 1
            or right["y"] + right["height"] <= left["y"] + 1
            for at, left in enumerate(boxes)
            for right in boxes[at + 1 :]
        ), boxes
        assert user.evaluate("document.documentElement.scrollWidth <= innerWidth")

    bounded_marks()
    # Native buttons keep identical-time moments separately reachable.
    lane.locator(".lf-trace-marker").first.click()
    expect(widget.locator(".lf-trace-bookmark:visible")).to_have_count(20)
    expect(
        widget.locator(".lf-trace-bookmark:visible .lf-trace-moment-number")
    ).to_have_text([str(number) for number in range(2, 22)])
    native_times = dict(checkpoints) | {frame_target: last_frame["timestamp"]}
    authored_times = [native_times[target] for target in targets]
    assert authored_times != sorted(authored_times), (
        "The fixture must challenge authored ordering"
    )
    origin = record["streams"][0]["monotonicTime"]
    expect(
        widget.locator(".lf-trace-bookmark:visible .lf-trace-moment-time")
    ).to_have_text(
        [f"{(timestamp - origin) / 1000:.3f} s" for timestamp in sorted(authored_times)]
    )
    represented = [
        int(label)
        for label in widget.locator(".lf-trace-marker span").all_text_contents()
    ]
    assert sorted(represented) == list(range(2, 22))
    widget.locator(".lf-trace-bookmarks").get_by_role("button", name=labels[-1]).click()
    expect(
        widget.locator(
            ".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img"
        )
    ).to_have_attribute("data-lf-datum", frame_target)
    # Page selection is the scope of both the axis pins and their labels.
    expect(widget.get_by_role("radiogroup", name="Recording scope")).to_be_visible()
    before_scope = widget.locator(".lf-trace-position").inner_text()
    before_origin = widget.locator(".lf-trace-body").evaluate(
        "e => e.getBoundingClientRect().top + scrollY"
    )
    widget.get_by_role("radio", name="All pages", exact=True).click()
    expect(summary).to_have_text("Moments (21)")
    expect(widget.locator(".lf-trace-bookmark:visible")).to_have_count(21)
    expect(
        widget.locator(".lf-trace-bookmark:visible .lf-trace-moment-number")
    ).to_have_text([str(number) for number in range(1, 22)])
    # An exact target already included in the overview does not narrow it.
    widget.locator(".lf-trace-bookmarks").get_by_role("button", name=labels[-1]).click()
    expect(widget.get_by_role("radio", name="All pages", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(widget.locator(f'[data-lf-datum="{frame_target}"]')).to_be_visible()

    widget.locator(".lf-trace-bookmarks").get_by_role(
        "button", name="Recording setup complete"
    ).click()
    expect(widget.locator(f'[data-lf-datum="{api_target}"]')).to_be_visible()
    expect(widget.get_by_role("radio", name="All pages", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(
        widget.get_by_role("button", name="Zoom image in", exact=True)
    ).to_be_disabled()
    expect(widget.locator(".lf-trace-missing-image")).to_be_visible()
    widget.get_by_role("radio", name="Page 1", exact=True).click()
    expect(widget.locator(".lf-trace-position")).to_have_text(before_scope)
    assert (
        widget.locator(".lf-trace-body").evaluate(
            "e => e.getBoundingClientRect().top + scrollY"
        )
        == before_origin
    )
    expect(summary).to_have_text("Moments (20)")
    resized(user, 390, 844)
    bounded_marks()
    # Walk every native moment by keyboard before resizing. Alignment changes
    # must retain the exact focused control, not send keyboard users to the body.
    widget.get_by_role("group", name="Recording timeline", exact=True).focus()
    for _ in range(20):
        user.keyboard.press("Tab")
        rendered(user)
        expect(widget.locator(".lf-trace-marker:focus-visible")).to_have_count(1)
    focused_pin_id = widget.locator(".lf-trace-marker:focus-visible").get_attribute(
        "id"
    )
    resized(user, 320, 844)
    expect(widget.locator(f"#{focused_pin_id}:focus-visible")).to_have_count(1)
    bounded_marks()
    body = widget.locator(".lf-trace-body")
    assert body.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    phone = open_page(browser, url, context=context)
    phone.get_by_role("radio", name="Page 1", exact=True).tap()
    phone.locator(".lf-trace-bookmarks").get_by_role("button", name=labels[-1]).tap()
    expect(
        phone.locator(".lf-trace-image:not(.lf-trace-image-pending) .viewer-canvas img")
    ).to_have_attribute("data-lf-datum", frame_target)
    phone.locator(".lf-trace-marker").first.tap()
    first_target = min(targets, key=native_times.__getitem__)
    expect(phone.locator(f'[data-lf-datum="{first_target}"]')).to_be_visible()
    expect(phone.locator(".lf-trace-selection")).to_contain_text(
        f"Moment 2 · {labels[targets.index(first_target)]}"
    )
    expect(phone.locator(".lf-trace-bookmark-list")).to_be_visible()
    assert phone.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_trace_numbered_moments_share_a_recording_zero_without_a_zero_stop(
    browser, serve
):
    """Equal-time and zero-boundary moments stay independently reachable."""
    source = ROOT / "examples/developer/playwright-trace-gallery.html"
    native = json.loads(source.with_suffix(".data.json").read_text())["release-journey"]
    archive = native["archive"]["sha256"]
    page = native["pages"][0]
    actions = [action for action in native["actions"] if action["pageId"] == page["id"]]
    first = min(actions, key=lambda action: action["startTime"])
    origin = first["startTime"] - 15
    # A call without snapshots still supplies its actual Start. Declare a clock
    # beginning 15 ms before it; do not create a synthetic event at recording zero.
    record = native | {
        "streams": [stream | {"monotonicTime": origin} for stream in native["streams"]],
        "actions": [
            action | {"phases": {}} if action["id"] == first["id"] else action
            for action in actions
        ],
    }
    clicks = [action for action in actions if "click" in action["title"]]
    docs = f"trace-{archive}-phase-{clicks[0]['id']}-after"
    api = f"trace-{archive}-phase-{clicks[1]['id']}-after"
    labels = ["Inspect documentation", "Recheck that checkpoint", "Inspect the API"]
    members = "".join(
        f'<lf-trace-bookmark label="{label}" target="{target}"></lf-trace-bookmark>'
        for label, target in zip(labels, (docs, docs, api), strict=True)
    )
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    url = serve(
        leaf_page(
            "Numbered trace moments",
            f'<h1>Numbered trace moments</h1><lf-trace id="journey" source="numbered-trace">{members}</lf-trace>'
            f'<lf-sample id="quoted-recording" label="Recording example"><lf-trace id="quoted-journey" source="numbered-trace">{members}</lf-trace></lf-sample>',
            layout="wide",
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "numbered-trace", record)
    user = open_page(browser, url)
    resized(user, 1440, 900)
    widget = user.locator("#journey")
    timeline = widget.locator(".lf-trace-timeline")
    # Vis keeps an offscreen tick before its window. The visible zero sits at
    # the left boundary, with no navigable time before the recording.
    zero = widget.locator(".vis-text.vis-minor:not(.vis-measure)").filter(
        has_text=re.compile(r"^0 s$")
    )
    expect(zero).to_have_count(1)
    zero_box = zero.bounding_box()
    axis_box = widget.locator(".vis-panel.vis-center").bounding_box()
    assert axis_box["x"] <= zero_box["x"] < axis_box["x"] + axis_box["width"]
    assert zero_box["x"] - axis_box["x"] < 6
    timeline_control = widget.get_by_role(
        "group", name="Recording timeline", exact=True
    )
    timeline_control.focus()
    expect(timeline_control).to_be_focused()
    user.keyboard.press("Home")
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((first['startTime']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(widget.locator(".lf-trace-phase")).to_have_text("Start · 0.015 s")
    coordinate = f"trace-{archive}-phase-{first['id']}-start"
    expect(widget.locator(f'[data-lf-datum="{coordinate}"]')).to_be_visible()
    navigate_at(timeline, 0)
    expect(widget.locator(".lf-trace-position")).to_have_text(
        f"{((first['startTime']) - record['streams'][0]['monotonicTime']) / 1000:.3f} s"
    )
    expect(widget.locator(f'[data-lf-datum="{coordinate}"]')).to_be_visible()
    pins = widget.locator(".lf-trace-marker")
    expect(pins).to_have_text(["1", "2", "3"])
    cluster = pins.nth(0)
    expect(cluster).to_have_attribute(
        "aria-label",
        f"Moment 1 · {labels[0]} · {(clicks[0]['phases']['after']['timestamp'] - origin) / 1000:.3f} s",
    )
    docs_time = (clicks[0]["phases"]["after"]["timestamp"] - origin) / 1000
    cluster_tip = widget.locator(".lf-trace-tooltip").first
    expect(cluster_tip).to_have_text(f"1 · {labels[0]} · {docs_time:.3f} s")
    for color_scheme in ("light", "dark"):
        user.emulate_media(color_scheme=color_scheme)
        cluster.hover()
        tooltip_body = cluster_tip.locator('[part="body"]')
        expect(tooltip_body).to_be_visible()
        reading = tooltip_body.evaluate(
            """node => {
              const canvas = document.createElement('canvas');
              canvas.width = canvas.height = 1;
              const context = canvas.getContext('2d', {willReadFrequently: true});
              const luminance = color => {
                context.clearRect(0, 0, 1, 1);
                context.fillStyle = color;
                context.fillRect(0, 0, 1, 1);
                return [...context.getImageData(0, 0, 1, 1).data.slice(0, 3)]
                  .map(channel => channel / 255)
                  .map(channel => channel <= .04045
                    ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4)
                  .reduce((sum, channel, index) =>
                    sum + channel * [.2126, .7152, .0722][index], 0);
              };
              const style = getComputedStyle(node);
              const [light, dark] = [luminance(style.color), luminance(style.backgroundColor)]
                .sort((a, b) => b - a);
              return {color: style.color, background: style.backgroundColor,
                contrast: (light + .05) / (dark + .05)};
            }"""
        )
        assert reading["contrast"] >= 4.5, (color_scheme, reading)
    user.emulate_media(color_scheme="light")
    expect(widget.locator(f'[data-lf-datum="{coordinate}"]')).to_be_visible()
    user.mouse.move(0, 0)
    expect(cluster_tip.locator('[part="body"]')).to_be_hidden()
    cluster.focus()
    expect(cluster).to_be_focused()
    assert cluster.evaluate("node => node.matches(':focus-visible')")
    expect(cluster_tip.locator('[part="body"]')).to_be_visible()
    user.keyboard.press("Enter")
    rows = widget.locator(".lf-trace-bookmarks")
    expect(rows.locator(".lf-trace-bookmark-list")).to_be_visible()
    expect(widget.locator(f'[data-lf-datum="{docs}"]')).to_be_visible()
    expect(widget.locator(".lf-trace-selection")).to_contain_text(
        f"Moment 1 · {labels[0]}"
    )
    expect(rows.locator(".lf-trace-moment-number")).to_have_text(["1", "2", "3"])
    # Hovering a stacked neighbor cannot turn its tooltip into a shield over
    # another moment. A raw pointer click must land immediately, without retries.
    first_pin = widget.locator('.lf-trace-marker[aria-label^="Moment 1 ·"]')
    second_pin = widget.locator('.lf-trace-marker[aria-label^="Moment 2 ·"]')
    widget.locator('.lf-trace-marker[aria-label^="Moment 3 ·"]').click()
    expect(widget.locator('.lf-trace-marker[aria-label^="Moment 3 ·"]')).to_be_focused()
    first_pin.hover()
    expect(cluster_tip.locator('[part="body"]')).to_be_visible()
    second_pin.hover()
    expect(
        widget.locator(".lf-trace-tooltip").nth(1).locator('[part="body"]')
    ).to_be_visible()
    box = first_pin.bounding_box()
    user.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(widget.locator(".lf-trace-selection")).to_contain_text(
        f"Moment 1 · {labels[0]}"
    )

    for index, (label, target) in enumerate(
        zip(labels, (docs, docs, api), strict=True)
    ):
        row = rows.get_by_role("button", name=re.compile(re.escape(label)))
        expect(row.locator(".lf-trace-moment-number")).to_have_text(str(index + 1))
        row.click()
        expect(widget.locator(f'[data-lf-datum="{target}"]')).to_be_visible()
        expect(widget.locator(".lf-trace-selection")).to_contain_text(
            f"Moment {index + 1}"
        )
    expect(pins.filter(has_text="3")).to_have_attribute("aria-current", "true")
    api_time = (clicks[1]["phases"]["after"]["timestamp"] - origin) / 1000
    solo_tip = widget.locator(".lf-trace-tooltip").last
    pins.filter(has_text="3").hover()
    expect(solo_tip).to_have_text(f"3 · {labels[2]} · {api_time:.3f} s")
    expect(solo_tip.locator('[part="body"]')).to_be_visible()
    expect(widget.locator(f'[data-lf-datum="{api}"]')).to_be_visible()
    user.mouse.move(0, 0)
    expect(solo_tip.locator('[part="body"]')).to_be_hidden()
    cluster.click()
    expect(rows.locator(".lf-trace-bookmark-list")).to_be_visible()
    expect(widget.locator(f'[data-lf-datum="{docs}"]')).to_be_visible()
    expect(widget.locator(".lf-trace-selection")).to_contain_text(
        f"Moment 1 · {labels[0]}"
    )
    quoted = user.locator("#quoted-journey")
    expect(quoted.locator(".lf-trace-marker")).to_have_text(["1", "2", "3"])
    expect(quoted.locator(".lf-trace-marker").first).to_be_disabled()
    expect(quoted.locator(".lf-trace-marker").last).to_be_disabled()
    expect(quoted.locator(".lf-trace-timeline")).to_have_js_property("tabIndex", -1)
    expect(quoted.locator(".lf-trace-bookmark .lf-trace-moment-number")).to_have_text(
        ["1", "2", "3"]
    )
    for index in range(3):
        expect(quoted.locator(".lf-trace-bookmark").nth(index)).to_be_disabled()

    # A real recording may begin with a bookmarked call at zero, followed by
    # another in the first millisecond. Neither its number nor the scrub handle
    # may disappear beyond the zero boundary, including after a narrow resize.
    user.close()
    setup = min(native["actions"], key=lambda action: action["startTime"])
    start = setup["startTime"]
    nearby = setup | {
        "id": setup["id"] + "-nearby",
        "startTime": start + 1,
        "endTime": start + 2,
    }
    middle = setup | {
        "id": setup["id"] + "-middle",
        "startTime": (start + setup["endTime"]) / 2,
        "endTime": None,
    }
    boundary_record = native | {
        "streams": [stream | {"monotonicTime": start} for stream in native["streams"]],
        "pages": [],
        "actions": [setup, nearby, middle],
        "images": [],
    }
    boundary_targets = [
        f"trace-{archive}-phase-{action['id']}-start"
        for action in (setup, nearby, middle)
    ]
    boundary_members = "".join(
        f'<lf-trace-bookmark label="Boundary {index}" target="{target}"></lf-trace-bookmark>'
        for index, target in enumerate(boundary_targets)
    )
    boundary_url = serve(
        leaf_page(
            "Recording boundary",
            f'<h1>Recording boundary</h1><lf-trace id="boundary" source="boundary-trace">{boundary_members}</lf-trace>',
            layout="wide",
        ),
        packages=("playwright",),
    )
    data_model.cmd_data_set(serve.page_dir, "boundary-trace", boundary_record)
    user = open_page(browser, boundary_url)
    widget = user.locator("#boundary")
    for width in (1440, 390, 1440):
        resized(user, width, 900)
        widget.get_by_role("button", name="Whole recording", exact=True).click()
        rendered(user)
        rail_box = widget.locator(".vis-panel.vis-center").bounding_box()
        for index, target in enumerate(boundary_targets[:2]):
            pin = widget.locator(
                f'.lf-trace-marker[aria-label^="Moment {index + 1} ·"]'
            )
            box = pin.bounding_box()
            assert box["width"] == pytest.approx(44)
            assert box["x"] >= rail_box["x"]
            assert box["x"] + box["width"] <= rail_box["x"] + rail_box["width"]
            pin.click()
            expect(widget.locator(f'[data-lf-datum="{target}"]')).to_be_visible()
            handle = widget.locator(".vis-custom-time > div").bounding_box()
            assert handle["width"] == pytest.approx(44)
            assert handle["x"] >= rail_box["x"] - 0.01
            assert handle["x"] + handle["width"] <= rail_box["x"] + rail_box["width"]
            zero = (
                widget.locator(".vis-text.vis-minor:not(.vis-measure)")
                .filter(has_text=re.compile(r"^0 s$"))
                .bounding_box()
            )
            # Vis rounds its axis height to integer pixels; the text's line
            # box can retain a fractional pixel beyond that border.
            assert handle["y"] >= zero["y"] + zero["height"] - 1
            assert handle["y"] + handle["height"] <= box["y"]


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
    expect(widget.locator(".vis-timeline, .viewer-container")).to_have_count(0)
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
    # Panning time must not restore the old image's position while media prepares.
    position = widget.locator(".lf-trace-position")
    requested_position = position.inner_text()
    rail = widget.locator(".lf-trace-markers")
    rail.scroll_into_view_if_needed()
    box = rail.bounding_box()
    x, y = box["x"] + box["width"] * 0.6, box["y"] + box["height"] - 8
    user.mouse.move(x, y)
    user.mouse.down()
    user.mouse.move(x - 70, y, steps=6)
    user.mouse.up()
    expect(position).to_have_text(requested_position)
    expect(raster).to_have_attribute("data-lf-datum", before_id)
    expect(widget.locator(".lf-trace-caption")).to_have_text(before_caption)
    assert widget.locator(".lf-trace-images").bounding_box()["height"] == before_height
    user.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    armed = False
    for route in held:
        route.continue_()
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
