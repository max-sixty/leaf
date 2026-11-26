"""Tests scheduled by the measured cost of their boundary."""

import os
from pathlib import Path

import pytest
from interact_support import (
    STATED_TIMEOUT,
    record_claim,
)
from model.test_native_watch import DIAGNOSTIC_QUIET_WINDOW_S, _subscriber

from leaf.base import state as cleanup_model
from leaf.serving.user_views import USER_VIEWS


@pytest.mark.parametrize("owner", ["page", "session"])
def test_a_page_subscription_hears_every_input_its_reading_reads(
    page_dir, tmp_path, monkeypatch, owner
):
    """A page's subscription watches only the directories its reading reads
    (`page_inputs.page_roots`), none with its tree, so the history beneath
    `revisions/` costs it no watch and a process watching pages needs no recursive
    watcher.
    Each path the reading stamps, found by recording its stamps rather than from a
    list, is written in turn: every write wakes the subscription and moves the
    reading. A write beneath a revision, to a diagnostic or to a staging file does
    neither."""
    from leaf.base import files
    from leaf.source import file_bindings, page_inputs
    from leaf.source.file_bindings import bind_file

    record_claim(page_dir, id="reading-owner")
    cleanup_model.ensure_session("reading-owner", {"pid": os.getpid()})
    bound = tmp_path / "notes.txt"
    bound.write_text("hello\n")
    bind_file(page_dir, "notes", bound)
    for tree in page_inputs.TREES:
        (page_dir / tree / "nested").mkdir(parents=True, exist_ok=True)
        (page_dir / tree / "nested" / "input.txt").write_text("authored")
    revision = page_dir / "revisions" / "r1-history"
    (revision / "resources").mkdir(parents=True)
    (revision / "index.html").write_text("history")
    (revision / "resources" / "module.js").write_text("history")

    stamped = []
    stamp = files.file_stamp

    def recording(path, **options):
        stamped.append(Path(path))
        return stamp(path, **options)

    with monkeypatch.context() as stamps:
        stamps.setattr(files, "file_stamp", recording)
        stamps.setattr(page_inputs, "file_stamp", recording)
        stamps.setattr(file_bindings, "file_stamp", recording)
        page_inputs.page_reading(page_dir)
    inputs = sorted({path for path in stamped if path.exists()})
    assert bound in inputs and page_dir / "revisions" in inputs

    def moving(path):
        # A directory's stamp moves when an entry arrives; a file's when it is
        # written, even with the bytes it held.
        if path.is_dir():
            return lambda: (path / "arrived").write_text("new entry")
        return lambda: path.write_bytes(path.read_bytes())

    with _subscriber(owner, page_dir) as subscribe:
        changes, _generation = subscribe()
        assert not any(changes.roots.values()), "a page's subscription takes a tree"
        assert not any(revision in (root, *root.parents) for root in changes.roots), (
            "a revision's own tree is subscribed"
        )

        def classified(write, timeout):
            changes, generation = subscribe()
            while changes.wait(generation, DIAGNOSTIC_QUIET_WINDOW_S):
                changes, generation = subscribe()
            before = page_inputs.page_reading(page_dir)
            write()
            return (
                changes.wait(generation, timeout),
                page_inputs.page_reading(page_dir) != before,
            )

        unheard = [
            path
            for path in inputs
            if classified(moving(path), STATED_TIMEOUT) != (True, True)
        ]
        assert unheard == [], "the reading reads these, but they woke nothing"
        for path in (
            revision / "index.html",
            revision / "resources" / "module.js",
            USER_VIEWS.file(page_dir / "user-views.json"),
            page_dir / ".leaf-staging.tmp",
        ):
            path.touch()
            assert classified(moving(path), DIAGNOSTIC_QUIET_WINDOW_S) == (
                False,
                False,
            ), path
