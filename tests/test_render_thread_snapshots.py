"""Approved appearance across a real message delivery journey.

Prepare with ``leaf-dev thread-snapshots prepare``, then run
``uv run pytest -n0 tests/test_render_thread_snapshots.py``. Baselines are
rendered from explicitly approved source; run evidence stays in .tmp.
``leaf-dev thread-snapshots --help`` owns snapshot review and acceptance.
"""

import json
import shutil
from datetime import datetime, timezone

import pytest
from leaf import event_log
from leaf.served_state import context as served_context
from leaf_dev import ROOT
from leaf_dev.thread_journey import NEXT_WORDS, WORDS, delivery_journey
from leaf_dev.thread_snapshots import CASES, SnapshotRun
from render_harness import consume_browser_errors, open_page


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_message_delivery_appearance_and_first_frame(
    browser, serve, image_snapshot, request, case, monkeypatch, thread_expected_store
):
    """One journey supplies both the contract observations and reviewed pixels."""
    now = datetime(2026, 9, 7, 18, tzinfo=timezone.utc)
    monkeypatch.setattr(event_log, "now_iso", lambda: now.isoformat())
    monkeypatch.setattr(served_context, "now_iso", lambda: now.isoformat())
    context = browser.new_context(
        viewport={"width": case.viewport[0], "height": case.viewport[1]},
        color_scheme=case.scheme,
        reduced_motion=case.motion,
        device_scale_factor=1,
        locale="en-US",
        timezone_id="UTC",
    )
    context.clock.set_fixed_time(now)
    page = open_page(browser, serve(ROOT / case.source), context=context)
    page.evaluate("() => document.fonts.ready")
    run = SnapshotRun(
        browser.version,
        case,
        image_snapshot,
        output=ROOT
        / ".tmp/thread-snapshots/runs"
        / request.getfixturevalue("testrun_uid"),
        store=thread_expected_store,
        updating=request.config.getoption("--image-snapshot-update"),
    )
    try:
        observed = delivery_journey(page, case.surface, run.capture)
        admitted = [
            event
            for event in event_log.read_events(serve.page_dir)
            if event.get("text") == WORDS
        ]
        assert len(admitted) == 1, f"expected one admitted send, got {admitted!r}"
        assert {
            key: admitted[0].get(key) for key in ("kind", "parent", "anchor")
        } == observed["drafted"]["intent"]
        assert {
            stage: {key: reading[key] for key in ("draft", "messages_added", "pending")}
            for stage, reading in observed.items()
        } == {
            "drafted": {"draft": WORDS, "messages_added": 0, "pending": 0},
            "pending": {"draft": "", "messages_added": 1, "pending": 1},
            "refused": {"draft": WORDS, "messages_added": 0, "pending": 0},
            "retry-pending": {"draft": "", "messages_added": 1, "pending": 1},
            "newer-draft-pending": {
                "draft": NEXT_WORDS,
                "messages_added": 1,
                "pending": 1,
            },
            "accepted": {"draft": NEXT_WORDS, "messages_added": 1, "pending": 0},
        }
        assert observed["accepted"]["opacity"] == 1
        for stage in ("newer-draft-pending", "accepted"):
            assert observed[stage]["focused"]
            assert observed[stage]["caret"] == [len(NEXT_WORDS) - 3] * 2
        consume_browser_errors(page, "400")
        run.finish()
    finally:
        (run.output / "observations.json").write_text(
            json.dumps(run.observations, indent=2) + "\n", encoding="utf-8"
        )


@pytest.mark.parametrize(
    "corruption",
    ["missing_png", "poisoned_png", "null_hash", "null_inventory", "malformed_marker"],
)
def test_approved_cache_rejects_missing_or_changed_bytes(
    browser, tmp_path, monkeypatch, corruption
):
    """A completion claim cannot replace required bytes from a real approved render."""
    from leaf_dev import thread_snapshot_source as source

    store = source.approved_store(browser.version)
    cache = tmp_path / "approved"
    copied = cache / store.parent.name
    shutil.copytree(store.parent, copied)
    monkeypatch.setattr(source, "CACHE", cache)
    assert source.approved_store(browser.version) == copied / "images"
    png = next((copied / "images").rglob("*.png"))
    marker = copied / "complete.json"
    if corruption == "poisoned_png":
        png.write_bytes(png.read_bytes() + b"poison")
    elif corruption == "malformed_marker":
        marker.write_text("{")
    else:
        png.unlink()
        if corruption == "null_hash":
            recorded = json.loads(marker.read_text())
            recorded[str(png.relative_to(copied / "images"))] = None
            marker.write_text(json.dumps(recorded))
        elif corruption == "null_inventory":
            marker.write_text("null")
    with pytest.raises(RuntimeError, match="incomplete or changed"):
        source.approved_store(browser.version)
