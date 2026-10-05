"""A native browser trace remains truthful when turned into commentable Leaf evidence."""

import hashlib
import json
import runpy
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.testing import CliRunner
from leaf.cli import cli
from leaf.data_contracts import payload_error
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills/leaf/packages/playwright"
PRODUCER = runpy.run_path(str(PACKAGE / "scripts/import_trace.py"))


@pytest.fixture
def native_trace(tmp_path, browser):
    """Capture ordinary web pages with duplicate controls and a moving control.

    Transform motion does not change layout. Capture checkpoints and accessibility
    trees are real browser readings with independent times, rather than synthesized
    geometry. A failed click supplies a native completion error.
    """
    trace = tmp_path / "trace.zip"
    context = browser.new_context(viewport={"width": 640, "height": 480})
    context.tracing.start(
        screenshots=True, snapshots=True, screen_snapshots=True, aria_snapshots=True
    )
    context.tracing.group("Review docs")
    first = context.new_page()
    first.set_content(
        """<style>@keyframes move {to {transform:translateX(180px)}}
        #moving {animation:move 2s infinite alternate linear}</style>
        <button onclick="this.textContent='Done'">Review</button>
        <button>Review</button><button id="moving">Moving</button><input>"""
    )
    context.tracing.group("Finish review")
    first.get_by_role("button", name="Review", exact=True).first.click()
    expect(first.get_by_role("button", name="Done")).to_be_visible()
    context.tracing.group_end()
    first.locator("input").fill("private-input-value")
    context.tracing.group_end()
    second = context.new_page()
    second.set_content("<button>Review</button><button>Review</button>")
    second.get_by_role("button", name="Review", exact=True).nth(1).click()
    with pytest.raises(Exception, match="Timeout"):
        second.get_by_role("button", name="Missing", exact=True).click(timeout=100)
    context.tracing.stop(path=trace)
    context.close()
    return trace


@pytest.fixture
def media_page(tmp_path):
    page = tmp_path / "leaf-page"
    result = CliRunner().invoke(cli, ["page", "init", "--no-packages", str(page)])
    assert result.exit_code == 0, result.output
    return page


def imported(trace, page):
    return PRODUCER["import_trace"](
        trace,
        page=page,
        launcher=ROOT / "bin/leaf",
        viewer_url="http://127.0.0.1:63819/",
    )


def test_native_trace_import_keeps_pixels_pages_action_errors_and_saved_tree_identity(
    native_trace, media_page
):
    original = native_trace.read_bytes()
    value = imported(native_trace, media_page)
    registry = json.loads((PACKAGE / "registry.json").read_text())
    assert payload_error("journey", "playwright-trace", value, registry) is None
    assert native_trace.read_bytes() == original
    assert value["archive"] == {
        "sha256": hashlib.sha256(original).hexdigest(),
        "format": 9,
    }
    assert len(value["pages"]) == 2
    assert any(action["title"] == "Review docs" for action in value["actions"])
    assert all(
        value["archive"]["sha256"] in row["id"]
        for row in value["actions"] + value["images"]
    )
    assert {image["kind"] for image in value["images"]} == {"frame", "checkpoint"}
    with ZipFile(native_trace) as archive:
        originals = {
            archive.read(name)
            for name in archive.namelist()
            if name.endswith((".jpeg", ".png"))
        }
        for image in value["images"]:
            assert (media_page / image["url"].lstrip("/")).read_bytes() in originals
        native_events = [
            json.loads(line) for line in archive.read("trace.trace").splitlines()
        ]
        saved_trees = {
            event["file"]: json.loads(archive.read(event["file"]))
            for event in native_events
            if event["type"] == "aria-snapshot"
        }
    trees = [event for event in native_events if event["type"] == "aria-snapshot"]
    checkpoints = [event for event in native_events if event["type"] == "screenshot"]
    native_calls = {
        event["callId"]: event for event in native_events if event["type"] == "before"
    }
    by_call = {action["callId"]: action for action in value["actions"]}
    nested_group = next(
        event
        for event in native_calls.values()
        if event.get("title") == "Finish review"
    )
    assert by_call[nested_group["callId"]]["title"] == "Finish review"
    nested_calls = [
        event
        for event in native_calls.values()
        if event.get("parentId") == nested_group["callId"]
    ]
    assert {by_call[event["callId"]]["title"] for event in nested_calls} == {
        "Review docs · Finish review · Frame.click",
        'Review docs · Finish review · Expect "to_be_visible"',
    }
    assert all(by_call[event["callId"]]["pageId"] for event in nested_calls)
    assert any(
        action["title"] == "Review docs · Frame.fill" for action in value["actions"]
    )
    by_image = {image["id"]: image for image in value["images"]}
    for action in value["actions"]:
        assert "params" not in action
        for phase_name, phase in action["phases"].items():
            if phase["tree"]:
                original_tree = next(
                    event
                    for event in trees
                    if (event["callId"], event["phase"])
                    == (action["callId"], phase_name)
                )
                assert phase["tree"]["timestamp"] == original_tree["timestamp"]
                for node in phase["tree"]["nodes"]:
                    saved_node = saved_trees[original_tree["file"]]
                    for part in node["path"].split("/"):
                        saved_node = (
                            saved_node[int(part)]
                            if isinstance(saved_node, list)
                            else saved_node[part]
                        )
                    assert node["box"] == (
                        saved_node.get("box") if isinstance(saved_node, dict) else None
                    )
            if phase["imageId"]:
                original_image = next(
                    event
                    for event in checkpoints
                    if (event["callId"], event["phase"])
                    == (action["callId"], phase_name)
                )
                assert (
                    by_image[phase["imageId"]]["timestamp"]
                    == original_image["timestamp"]
                )
    duplicated = next(
        phase["tree"]["nodes"]
        for action in value["actions"]
        for phase in action["phases"].values()
        if phase["tree"]
        and sum(
            node["role"] == "button" and node["name"] == "Review"
            for node in phase["tree"]["nodes"]
        )
        == 2
    )
    buttons = [
        node
        for node in duplicated
        if node["role"] == "button" and node["name"] == "Review"
    ]
    assert buttons[0]["path"] != buttons[1]["path"]
    assert any(
        node["name"] == "Moving" and node["box"]
        for action in value["actions"]
        for phase in action["phases"].values()
        if phase["tree"]
        for node in phase["tree"]["nodes"]
    )
    failed = next(action for action in value["actions"] if action["error"])
    assert "Timeout" in failed["error"]
    assert failed["endTime"] >= failed["startTime"]
    assert "private-input-value" not in json.dumps(
        [action["title"] for action in value["actions"]]
    )


def test_multiple_native_streams_and_complete_action_records_keep_distinct_identities(
    native_trace, media_page, tmp_path
):
    """Format-9's complete action shape uses the same facts as before/after.

    Playwright's loader accepts both shapes. Build complete records from the native
    capture's own action facts and combine two streams, rather than storing binary
    fixtures or mocking browser snapshots.
    """
    combined = tmp_path / "combined.zip"
    with ZipFile(native_trace) as source, ZipFile(combined, "w") as output:
        for name in source.namelist():
            output.writestr(name, source.read(name))
        events = [json.loads(line) for line in source.read("trace.trace").splitlines()]
        context = {**events[0], "origin": "testRunner"}
        calls = {
            event["callId"]: event for event in events if event["type"] == "before"
        }
        for event in events:
            if event["type"] == "after":
                calls[event["callId"]] = {
                    **calls[event["callId"]],
                    **event,
                    "type": "action",
                }
        output.writestr(
            "test.trace",
            "\n".join(json.dumps(event) for event in [context, *calls.values()]),
        )
    value = imported(combined, media_page)
    assert {stream["origin"] for stream in value["streams"]} == {
        "library",
        "testRunner",
    }
    runner = [
        action
        for action in value["actions"]
        if action["stream"] == value["streams"][0]["id"]
    ]
    library = [
        action
        for action in value["actions"]
        if action["stream"] == value["streams"][1]["id"]
    ]
    assert {action["callId"] for action in runner} == {
        action["callId"] for action in library
    }
    assert {action["id"] for action in runner}.isdisjoint(
        action["id"] for action in library
    )
    assert all(action["pageId"] is None for action in runner)
    assert any(action["error"] for action in runner)
    assert any(action["title"] == "Review docs" for action in runner)


def test_unreadable_archive_refuses_before_importing_media(media_page, tmp_path):
    for filename, entries, expected in [
        (
            "new.zip",
            {"trace.trace": json.dumps({"type": "context-options", "version": 10})},
            "unsupported trace format 10",
        ),
        ("unsafe.zip", {"../escape.png": "invalid"}, "unsafe archive entry"),
        (
            "missing.zip",
            {
                "trace.trace": json.dumps(
                    {"type": "context-options", "version": 9, "origin": "library"}
                )
                + "\n"
                + json.dumps({"type": "screencast-frame", "file": "missing.jpeg"})
            },
            "missing resource",
        ),
    ]:
        trace = tmp_path / filename
        with ZipFile(trace, "w") as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        with pytest.raises(PRODUCER["TraceError"], match=expected):
            imported(trace, media_page)
    assert not list((media_page / "media").iterdir())


def test_native_parent_graph_omits_missing_labels_and_refuses_invalid_edges(
    media_page, tmp_path
):
    """External action records may reference another chunk, but cannot contain cycles."""
    context = {"type": "context-options", "version": 9, "origin": "library"}
    group = {
        "type": "action",
        "callId": "group",
        "parentId": "outside-this-stream",
        "class": "Tracing",
        "method": "tracingGroup",
        "title": "Review docs",
        "startTime": 1,
        "endTime": 2,
    }
    child = {
        "type": "action",
        "callId": "child",
        "parentId": "group",
        "class": "Frame",
        "method": "click",
        "startTime": 3,
        "endTime": 4,
    }
    trace = tmp_path / "parents.zip"

    def write(*events):
        with ZipFile(trace, "w") as archive:
            archive.writestr(
                "trace.trace",
                "\n".join(json.dumps(event) for event in (context, *events)),
            )

    # Native IDs determine nesting even if complete records arrive child-first.
    write(child, group)
    value = imported(trace, media_page)
    assert [action["title"] for action in value["actions"]] == [
        "Review docs · Frame.click",
        "Review docs",
    ]
    write({**child, "parentId": "outside-this-stream"})
    assert imported(trace, media_page)["actions"][0]["title"] == "Frame.click"
    write({**child, "title": "Review docs"}, group)
    assert imported(trace, media_page)["actions"][0]["title"] == "Review docs"

    for invalid in (None, "", 1, [], {}):
        write({**child, "parentId": invalid})
        with pytest.raises(PRODUCER["TraceError"], match="child parentId"):
            imported(trace, media_page)
    for parent, expected in [
        (None, "child parentId"),
        ("other", "conflicting parentId"),
    ]:
        write(
            {**child, "type": "before"},
            {"type": "after", "callId": "child", "parentId": parent, "endTime": 4},
        )
        with pytest.raises(PRODUCER["TraceError"], match=expected):
            imported(trace, media_page)
    write(child, {**group, "parentId": "child"})
    with pytest.raises(PRODUCER["TraceError"], match="parentId cycle"):
        imported(trace, media_page)
    write({**child, "parentId": "child"})
    with pytest.raises(PRODUCER["TraceError"], match="parentId cycle"):
        imported(trace, media_page)
    assert not list((media_page / "media").iterdir())
