"""A native browser trace remains truthful when turned into commentable Leaf evidence."""

import json
import runpy
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.testing import CliRunner
from playwright.sync_api import expect

from leaf.cli import cli

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "packages/playwright"
PRODUCER = runpy.run_path(str(PACKAGE / "scripts/import_trace.py"))


@pytest.fixture(name="native_trace")
def native_trace_fixture(tmp_path, browser):
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
    first.locator("input").press("ArrowLeft")
    first.keyboard.press("Tab")
    context.tracing.group_end()
    second = context.new_page()
    second.set_content("<button>Review</button><button>Review</button>")
    second.get_by_role("button", name="Review", exact=True).nth(1).click()
    with pytest.raises(Exception, match="strict mode violation"):
        second.get_by_role("button", name="Review", exact=True).click()
    context.tracing.stop(path=trace)
    context.close()
    return trace


@pytest.fixture(name="media_page")
def media_page_fixture(tmp_path):
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


@pytest.mark.parametrize(
    ("versions", "message"),
    [([11], "unsupported trace format 11"), ([9, 10], "one format")],
)
def test_unsupported_or_mixed_trace_formats_refuse(
    media_page, tmp_path, versions, message
):
    trace = tmp_path / "unsupported.zip"
    with ZipFile(trace, "w") as archive:
        for index, version in enumerate(versions):
            archive.writestr(
                f"{index}.trace",
                json.dumps(
                    {"type": "context-options", "version": version, "origin": "library"}
                ),
            )
    with pytest.raises(PRODUCER["TraceError"], match=message):
        imported(trace, media_page)


@pytest.mark.parametrize("version", [9, 10])
def test_native_call_identity_connects_input_and_phase_captures(
    media_page, tmp_path, version
):
    """Both formats use native callId edges, irrespective of separate stepId."""
    trace = tmp_path / "identity.zip"
    events = [
        {"type": "context-options", "version": version, "origin": "library"},
        {
            "type": "before",
            "callId": "step@group",
            "class": "Tracing",
            "method": "tracingGroup",
            "title": "Review",
            "startTime": 1,
        },
        {
            "type": "before",
            "callId": "step@click",
            "parentId": "step@group",
            "class": "Frame",
            "method": "click",
            "startTime": 2,
            "params": {"selector": "#approve"},
        },
        {"type": "input", "callId": "step@click", "point": {"x": 20, "y": 30}},
        {
            "type": "frame-snapshot",
            "snapshot": {
                "callId": "step@click",
                "phase": "action",
                "pageId": "page@one",
                "isMainFrame": True,
                "timestamp": 3,
                "viewport": {"width": 640, "height": 480},
            },
        },
        {
            "type": "aria-snapshot",
            "callId": "step@click",
            "phase": "action",
            "pageId": "page@one",
            "timestamp": 4,
            "file": "aria/click.json",
        },
        {"type": "after", "callId": "step@click", "endTime": 5},
        {"type": "after", "callId": "step@group", "endTime": 6},
    ]
    if version == 9:
        events[1]["stepId"] = "separate-step@group"
        events[2]["stepId"] = "separate-step@click"
    with ZipFile(trace, "w") as archive:
        archive.writestr("trace.trace", "\n".join(map(json.dumps, events)))
        archive.writestr(
            "aria/click.json",
            json.dumps(
                [
                    {"role": "button", "name": "Approve"},
                ]
            ),
        )
    value = imported(trace, media_page)
    action = next(
        action for action in value["actions"] if action["callId"] == "step@click"
    )
    assert value["archive"]["format"] == version
    assert action["title"] == "Review · Frame.click"
    assert action["endTime"] == 5
    assert action["pageId"] == value["pages"][0]["id"]
    assert action["input"] == {
        "selector": "#approve",
        "key": None,
        "point": {"x": 20, "y": 30},
        "viewport": {"width": 640, "height": 480},
    }
    phase = action["phases"]["action"]
    assert phase["pageId"] == action["pageId"]
    assert phase["timestamp"] == 3
    assert phase["tree"]["timestamp"] == 4
    assert phase["tree"]["nodes"][0]["name"] == "Approve"


def test_native_parent_graph_omits_missing_labels_and_refuses_cycles(
    media_page, tmp_path
):
    """External action records may reference another chunk, but cannot contain cycles."""
    context = {"type": "context-options", "version": 10, "origin": "library"}
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

    write(child, {**group, "parentId": "child"})
    with pytest.raises(PRODUCER["TraceError"], match="parentId cycle"):
        imported(trace, media_page)
    write({**child, "parentId": "child"})
    with pytest.raises(PRODUCER["TraceError"], match="parentId cycle"):
        imported(trace, media_page)
    assert not list((media_page / "media").glob("*"))
