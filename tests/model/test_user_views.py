"""User-view context remains separate for each document and each check's basis."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from leaf import user_views
from leaf.files import read_json
from leaf.state import write_json


def report(session="a" * 32, sequence=1, revision=1):
    viewport = {"width": 900, "height": 700}
    return {
        "identity": {"delivery": {"runtime": "captured-runtime"}},
        "session": session,
        "sequence": sequence,
        "visible": True,
        "revision": revision,
        "through_seq": 3,
        "viewport": viewport,
        "visual_viewport": {
            **viewport,
            "offset_left": 0,
            "offset_top": 0,
            "scale": 1,
        },
        "shown_window": {"x": 0, "y": 0, **viewport},
        "color_scheme": "light",
        "reduced_motion": False,
        "pointer": "fine",
        "scroll": {"x": 0, "y": 250},
        "visible_regions": ["heading", "comparison"],
        "checks": {
            "identity": {"delivery": {"runtime": "captured-runtime"}},
            "sequence": sequence,
            "revision": revision,
            "through_seq": 3,
            "viewport": deepcopy(viewport),
            "visual_viewport": {
                **viewport,
                "offset_left": 0,
                "offset_top": 0,
                "scale": 1,
            },
            "shown_window": {"x": 0, "y": 0, **viewport},
            "color_scheme": "light",
            "reading": {"checks": {"horizontal_overflow_px": 12}},
        },
    }


def test_each_document_retains_its_view_and_hidden_reports_cannot_be_reordered(
    tmp_path, monkeypatch
):
    instant = datetime(2026, 10, 2, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: instant)
    first = report()
    second = report(session="b" * 32, revision=2)
    second["viewport"] = {"width": 420, "height": 800}
    assert user_views.observe_user_view(tmp_path, first)
    assert user_views.observe_user_view(tmp_path, second)
    visible = user_views.read_user_views(tmp_path, 2)["sessions"]
    assert len(visible) == 2
    assert [value["matches_active_revision"] for value in visible] == [True, False]
    assert [value["viewport"]["width"] for value in visible] == [420, 900]

    instant += timedelta(seconds=10)
    hidden = {**first, "sequence": 2, "visible": False}
    assert user_views.observe_user_view(tmp_path, hidden)
    assert not user_views.observe_user_view(tmp_path, first)
    current = user_views.read_user_views(tmp_path, 2)["sessions"][0]
    assert current["visible"] is False
    assert current["received_at"] == instant.isoformat()

    instant += timedelta(seconds=46)
    assert {
        value["freshness"]
        for value in user_views.read_user_views(tmp_path, 2)["sessions"]
    } == {"stale"}


def test_check_receipt_and_basis_do_not_follow_fresh_context(tmp_path, monkeypatch):
    instant = datetime(2026, 10, 2, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: instant)
    original = report()
    user_views.observe_user_view(tmp_path, original)
    checked_at = instant.isoformat()
    instant += timedelta(seconds=20)
    resized: dict = {
        **original,
        "sequence": 2,
        "viewport": {"width": 420, "height": 800},
    }
    resized["identity"] = {"delivery": {"runtime": "new-runtime"}}
    user_views.observe_user_view(tmp_path, resized)
    value = user_views.read_user_views(tmp_path, 1)["sessions"][0]
    assert value["received_at"] != checked_at
    assert value["checks"]["checked_at"] == checked_at
    assert value["checks"]["viewport"] == original["viewport"]
    assert value["identity"] == resized["identity"]
    assert value["checks"]["identity"] == original["checks"]["identity"]

    user_views.observe_user_view(tmp_path, {**resized, "sequence": 3, "checks": None})
    assert (
        user_views.read_user_views(tmp_path, 1)["sessions"][0]["checks"]
        == value["checks"]
    )
    updated: dict = deepcopy(resized)
    updated["sequence"] = 4
    updated["checks"]["sequence"] = 4
    updated["checks"]["viewport"] = resized["viewport"]
    user_views.observe_user_view(tmp_path, updated)
    value = user_views.read_user_views(tmp_path, 1)["sessions"][0]
    assert value["checks"]["checked_at"] == instant.isoformat()
    assert value["checks"]["viewport"] == resized["viewport"]


def test_ingress_refuses_invalid_context_and_check_provenance(tmp_path):
    alterations = [
        {"session": "not-a-document-id"},
        {"visible": "true"},
        {"revision": 0},
        {"sequence": -1},
        {"pointer": "mouse"},
        {"viewport": {"width": 0, "height": 700}},
        {"visible_regions": ["heading", "heading"]},
        {"received_at": "2026-10-02T00:00:00Z"},
    ]
    for alteration in alterations:
        with pytest.raises(ValueError, match="invalid user view"):
            user_views.observe_user_view(tmp_path, {**report(), **alteration})
    future = report()
    future["checks"]["sequence"] = 2
    with pytest.raises(ValueError, match="checks sequence exceeds"):
        user_views.observe_user_view(tmp_path, future)
    assert user_views.read_user_views(tmp_path, 1)["sessions"] == []


def test_obsolete_records_are_absent_and_inactive_documents_are_pruned_on_write(
    tmp_path, monkeypatch
):
    instant = datetime(2026, 10, 2, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: instant)
    path = tmp_path / user_views.USER_VIEWS_FILE
    write_json(path, {"format": "earlier", "sessions": {"obsolete": {}}})
    assert user_views.read_user_views(tmp_path, 1)["sessions"] == []
    user_views.observe_user_view(tmp_path, report())
    instant += timedelta(days=1, seconds=1)
    assert user_views.read_user_views(tmp_path, 1)["sessions"] == []
    user_views.observe_user_view(tmp_path, report(session="b" * 32))
    assert list(read_json(path)["sessions"]) == ["b" * 32]


def test_viewed_records_the_last_visible_report_and_outlives_pruning(
    tmp_path, monkeypatch
):
    """`viewed` moves only with a report that the page was showing, so a tab opened
    hidden never stamps it, and it survives the day after which its report goes."""
    instant = datetime(2026, 10, 2, tzinfo=UTC)
    monkeypatch.setattr(user_views, "_now", lambda: instant)
    assert user_views.viewed_at(tmp_path) is None
    user_views.observe_user_view(tmp_path, {**report(), "visible": False})
    assert user_views.viewed_at(tmp_path) is None

    user_views.observe_user_view(tmp_path, report(sequence=2))
    shown = instant.timestamp()
    assert user_views.viewed_at(tmp_path) == shown
    instant += timedelta(seconds=10)
    user_views.observe_user_view(tmp_path, {**report(sequence=3), "visible": False})
    assert user_views.viewed_at(tmp_path) == shown

    instant += timedelta(days=1, seconds=1)
    later = {**report(session="b" * 32), "visible": False}
    user_views.observe_user_view(tmp_path, later)
    sessions = user_views.read_user_views(tmp_path, 1)["sessions"]
    assert [view["session"] for view in sessions] == ["b" * 32]
    assert user_views.viewed_at(tmp_path) == shown
