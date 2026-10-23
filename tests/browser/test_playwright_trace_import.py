"""A native browser trace remains truthful when turned into commentable Leaf evidence."""

import hashlib
import json
from zipfile import ZipFile

from model.test_playwright_trace_import import (  # noqa: F401 (fixtures)
    PACKAGE,
    imported,
    media_page_fixture,
    native_trace_fixture,
)

from leaf.data_contracts import payload_error


def test_native_trace_import_keeps_pixels_pages_action_errors_and_saved_tree_identity(
    native_trace, media_page
):
    original = native_trace.read_bytes()
    value = imported(native_trace, media_page)
    registry = json.loads((PACKAGE / "registry.json").read_text())
    assert payload_error("journey", "playwright-trace", value, registry) is None
    assert native_trace.read_bytes() == original
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
        assert value["archive"] == {
            "sha256": hashlib.sha256(original).hexdigest(),
            "format": native_events[0]["version"],
        }
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
    native_inputs = {
        event["callId"]: event for event in native_events if event["type"] == "input"
    }
    input_viewports = {
        event["snapshot"]["callId"]: event["snapshot"]["viewport"]
        for event in native_events
        if event["type"] == "frame-snapshot"
        and event["snapshot"].get("isMainFrame")
        and event["snapshot"]["phase"] == "action"
    }
    assert native_inputs
    assert {by_call[call_id]["method"] for call_id in native_inputs} >= {
        "click",
        "fill",
        "press",
        "keyboardPress",
    }
    for call_id, native in native_calls.items():
        action = by_call[call_id]
        assert action["method"] == native["method"]
        if call_id not in native_inputs:
            assert action["input"] is None
            continue
        assert action["input"] == {
            "selector": native["params"].get("selector"),
            "key": native["params"].get("key"),
            "point": native_inputs[call_id].get("point"),
            "viewport": input_viewports.get(call_id),
        }
    assert any(
        action["input"] and action["input"]["point"] for action in by_call.values()
    )
    keyboard = next(
        action for action in by_call.values() if action["method"] == "keyboardPress"
    )
    assert keyboard["input"] == {
        "selector": None,
        "key": "Tab",
        "point": None,
        "viewport": input_viewports.get(keyboard["callId"]),
    }
    assert "private-input-value" not in json.dumps(
        [
            {"method": action["method"], "input": action["input"]}
            for action in by_call.values()
        ]
    )
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
    assert "strict mode violation" in failed["error"]
    assert failed["endTime"] >= failed["startTime"]
    assert "private-input-value" not in json.dumps(
        [action["title"] for action in value["actions"]]
    )


def test_multiple_native_streams_and_complete_action_records_keep_distinct_identities(
    native_trace, media_page, tmp_path
):
    """The native complete action shape uses the same facts as before/after.

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
            elif event["type"] == "input" and "point" in event:
                calls[event["callId"]]["point"] = event["point"]
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
    assert all(
        action["method"]
        == next(
            native["method"]
            for native in library
            if native["callId"] == action["callId"]
        )
        for action in runner
    )
    runner_click = next(action for action in runner if action["input"])
    library_click = next(
        action for action in library if action["callId"] == runner_click["callId"]
    )
    assert runner_click["input"] == {
        **library_click["input"],
        "viewport": None,
    }
    assert library_click["input"]["viewport"] == {"width": 640, "height": 480}
