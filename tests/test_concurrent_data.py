"""External data replacement and shared validation caching keep complete readings."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event

from interact_support import STATED_TIMEOUT
from leaf import data as data_model

REGISTRY = {"$data": {"contracts": {"integer": {"schema": {"type": "integer"}}}}}


def test_data_delivery_tracks_contract_and_validity_without_revising_the_bytes(
    tmp_path,
):
    source = data_model.source_file(tmp_path, "numbers")
    source.parent.mkdir()
    source.write_text(
        json.dumps({"run": "1" * 32, "updated": "2026-01-01T00:00:00Z", "value": 1})
    )
    index = tmp_path / "data.json"
    index.write_text(json.dumps({"sources": {"numbers": {"contract": "integer"}}}))
    original = data_model.read_data(tmp_path, REGISTRY)
    revision = original["sources"]["numbers"]["revision"]

    replacement = source.with_name("replacement.json")
    replacement.write_text(
        json.dumps({"run": "2" * 32, "updated": "2026-01-01T00:00:00Z", "value": 1})
    )
    os.replace(replacement, source)
    refreshed = data_model.read_data(tmp_path, REGISTRY)
    assert refreshed["sources"]["numbers"]["revision"] == revision
    assert (
        refreshed["sources"]["numbers"]["updated"]
        == original["sources"]["numbers"]["updated"]
    )
    assert (
        refreshed["sources"]["numbers"]["run"] != original["sources"]["numbers"]["run"]
    )
    assert refreshed["version"] != original["version"]

    index.write_text(json.dumps({"sources": {"numbers": {"contract": "count"}}}))
    registry = {"$data": {"contracts": {"count": {"schema": {"type": "integer"}}}}}
    rebound = data_model.read_data(tmp_path, registry)
    assert rebound["sources"]["numbers"] == {
        **refreshed["sources"]["numbers"],
        "contract": "count",
        "updated": "2026-01-01T00:00:00Z",
    }
    assert rebound["version"] != original["version"]

    registry["$data"]["contracts"]["count"]["schema"] = {"type": "string"}
    invalid = data_model.read_data(tmp_path, registry)
    assert invalid["sources"]["numbers"]["revision"] == revision
    assert "error" in invalid["sources"]["numbers"]
    assert "value" not in invalid["sources"]["numbers"]
    assert invalid["version"] != rebound["version"]

    registry["$data"]["contracts"]["count"]["schema"] = {"type": "integer"}
    assert data_model.read_data(tmp_path, registry) == rebound


def test_a_source_read_keeps_one_complete_publication(tmp_path, monkeypatch):
    source = data_model.source_file(tmp_path, "numbers")
    source.parent.mkdir()
    source.write_text(
        json.dumps({"run": "1" * 32, "updated": "2026-01-01T00:00:00Z", "value": 1})
    )
    replacement = source.with_name("replacement.json")
    replacement.write_text(
        json.dumps({"run": "2" * 32, "updated": "2026-01-02T00:00:00Z", "value": 2})
    )
    open_path = Path.open

    class ReplacingReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, *args):
            contents = self.stream.read(*args)
            os.replace(replacement, source)
            return contents

    @contextmanager
    def open_before_replacement(path, *args, **kwargs):
        with open_path(path, *args, **kwargs) as stream:
            yield ReplacingReader(stream) if path == source else stream

    with monkeypatch.context() as ordered:
        ordered.setattr(Path, "open", open_before_replacement)
        reading = data_model.read_source(tmp_path, "numbers", "integer", REGISTRY)
    assert reading["value"] == 1
    assert reading["updated"] == "2026-01-01T00:00:00Z"
    assert reading["run"] == "1" * 32
    assert (
        reading["run"]
        != data_model.read_source(tmp_path, "numbers", "integer", REGISTRY)["run"]
    )
    assert (
        data_model.read_source(tmp_path, "numbers", "integer", REGISTRY)["value"] == 2
    )


def test_cache_eviction_during_a_validation_keeps_its_result(monkeypatch):
    inserted = Event()
    evicted = Event()

    class OrderedCache(dict):
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            if key[0] == "first":
                inserted.set()
                assert evicted.wait(STATED_TIMEOUT), (
                    "second validation did not evict the cache"
                )

    cache = OrderedCache(
        {(str(i), "declaration", "revision"): None for i in range(1023)}
    )
    monkeypatch.setattr(data_model, "_JUDGED", cache)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            data_model._value_error, "first", "integer", 1, "first-revision", REGISTRY
        )
        try:
            assert inserted.wait(STATED_TIMEOUT), (
                "first validation did not cache its result"
            )
            assert (
                data_model._value_error(
                    "other", "integer", 2, "other-revision", REGISTRY
                )
                is None
            )
        finally:
            evicted.set()
        assert first.result(timeout=STATED_TIMEOUT) is None
