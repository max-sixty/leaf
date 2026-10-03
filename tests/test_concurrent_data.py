"""External data replacement and shared validation caching keep complete readings."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Event

from leaf import data as data_model

REGISTRY = {"$data": {"contracts": {"integer": {"schema": {"type": "integer"}}}}}


def test_a_source_read_keeps_the_metadata_of_the_file_it_read(tmp_path, monkeypatch):
    source = data_model.source_file(tmp_path, "numbers")
    source.parent.mkdir()
    source.write_text("1")
    os.utime(source, (1000, 1000))
    replacement = source.with_name("replacement.json")
    replacement.write_text("2")
    os.utime(replacement, (2000, 2000))
    open_path = Path.open

    class ReplacingReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, *args):
            contents = self.stream.read(*args)
            os.replace(replacement, source)
            return contents

        def fileno(self):
            return self.stream.fileno()

    @contextmanager
    def open_before_replacement(path, *args, **kwargs):
        with open_path(path, *args, **kwargs) as stream:
            yield ReplacingReader(stream) if path == source else stream

    with monkeypatch.context() as ordered:
        ordered.setattr(Path, "open", open_before_replacement)
        reading = data_model.read_source(tmp_path, "numbers", "integer", REGISTRY)
    assert reading["value"] == 1
    assert reading["updated"] == datetime.fromtimestamp(1000).astimezone().isoformat(
        timespec="seconds"
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
                assert evicted.wait(10), "second validation did not evict the cache"

    cache = OrderedCache(
        {(str(i), "declaration", "revision"): None for i in range(1023)}
    )
    monkeypatch.setattr(data_model, "_JUDGED", cache)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            data_model._value_error, "first", "integer", 1, "first-revision", REGISTRY
        )
        try:
            assert inserted.wait(10), "first validation did not cache its result"
            assert (
                data_model._value_error(
                    "other", "integer", 2, "other-revision", REGISTRY
                )
                is None
            )
        finally:
            evicted.set()
        assert first.result(timeout=10) is None
