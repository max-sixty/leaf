"""Developer tooling checks; run explicitly from dev/tests."""

import contextlib
import json
import os
import subprocess
import time

import pytest
from leaf_dev.commands import distribution


def test_compiled_cache_follows_payload_and_compiler_bytes(tmp_path, monkeypatch):
    """Identical saves and authored revisions reuse a kernel; its inputs do not."""
    monkeypatch.setattr(distribution, "ROOT", tmp_path)
    module = tmp_path / "browser/runtime/example.js"
    compiler = tmp_path / "build/runtime-bundle.mjs"
    authored = tmp_path / "examples/page.html"
    for path, content in (
        (module, "export const example = 1;"),
        (compiler, "compileKernel();"),
        (authored, "<p>First draft</p>"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    original = distribution.installation_identity(tmp_path)
    module.touch()
    authored.write_text("<p>Revised draft</p>")
    assert distribution.installation_identity(tmp_path) == original
    module.write_text("export const example = 2;")
    changed_runtime = distribution.installation_identity(tmp_path)
    assert changed_runtime != original
    compiler.write_text("compileKernelDifferently();")
    assert distribution.installation_identity(tmp_path) != changed_runtime


def test_compiled_cache_refreshes_payload_and_git_provenance(tmp_path, monkeypatch):
    """Authored edits and commits publish an installation with current provenance."""
    monkeypatch.setattr(distribution, "ROOT", tmp_path)
    monkeypatch.setenv("LEAF_DEV_CACHE_DIR", str(tmp_path / ".tmp/cache"))

    def git(*args):
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.name=Leaf Test",
                "-c",
                "user.email=leaf@example.test",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    module = tmp_path / "browser/runtime/example.js"
    authored = tmp_path / "examples/page.html"
    for path, content in (
        (module, "export const example = 1;"),
        (authored, "<p>First draft</p>"),
        (tmp_path / ".gitignore", ".tmp/\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git("init")
    git("add", ".")
    git("commit", "-m", "First runtime")

    def prepare(output, runtime):
        # This test owns cache orchestration. The real compiler and page launcher
        # are exercised by the prepared-installation journey.
        bundle = output / "runtime/bundle.js"
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(module.read_bytes())
        (output / "leaf-distribution.json").write_text(
            json.dumps({"producer": distribution.payload_provenance(root=tmp_path)})
        )

    monkeypatch.setattr(distribution, "prepare", prepare)

    def producer(installation):
        return json.loads((installation / "leaf-distribution.json").read_text())[
            "producer"
        ]

    clean = distribution.cached_installation(tmp_path)
    assert producer(clean)["dirty"] is False
    authored.write_text("<p>Revised draft</p>")
    dirty = distribution.cached_installation(tmp_path)
    assert dirty != clean
    assert producer(dirty)["dirty"] is True
    git("add", ".")
    git("commit", "-m", "Revised authored page")
    committed = distribution.cached_installation(tmp_path)
    assert producer(committed)["commit"] != producer(clean)["commit"]
    assert producer(committed)["dirty"] is False
    assert producer(clean)["dirty"] is False
    assert producer(dirty)["dirty"] is True
    module.write_text("export const example = 2;")
    changed = distribution.cached_installation(tmp_path)
    assert (changed / "runtime/bundle.js").read_bytes() == module.read_bytes()


def test_identical_extracted_arms_share_the_compiled_content_identity(tmp_path):
    """A comparison's temporary checkout address is not a compiler input."""
    arms = [tmp_path / name for name in ("first", "second")]
    for arm in arms:
        module = arm / "browser/runtime/example.js"
        module.parent.mkdir(parents=True)
        module.write_text("export const example = 1;")
    assert distribution.installation_identity(
        arms[0]
    ) == distribution.installation_identity(arms[1])


@pytest.mark.parametrize("edit_at", ["lock", "cache-hit"])
def test_cached_installation_reselects_after_an_edit_while_selecting(
    prepared_cache, monkeypatch, edit_at
):
    """A preview waiting for a cached revision returns the edit that woke it."""
    from contextlib import contextmanager

    module, built = prepared_cache
    runtime = distribution.ROOT
    first = module.read_bytes()
    second = b"export const example = 2;"
    previous = distribution.cached_installation(runtime)
    module.write_bytes(second)
    current = distribution.cached_installation(runtime)
    module.write_bytes(first)
    flocked = distribution.flocked
    edited = False

    @contextmanager
    def edit_before_acquisition(path):
        nonlocal edited
        if not edited:
            module.write_bytes(second)
            edited = True
        with flocked(path):
            yield

    if edit_at == "lock":
        monkeypatch.setattr(distribution, "flocked", edit_before_acquisition)
    else:
        is_dir = type(previous).is_dir

        def edit_during_cache_hit(path):
            nonlocal edited
            if path == previous and not edited:
                module.write_bytes(second)
                edited = True
            return is_dir(path)

        monkeypatch.setattr(type(previous), "is_dir", edit_during_cache_hit)
    selected = distribution.cached_installation(runtime)
    assert selected == current != previous
    assert (selected / "runtime/bundle.js").read_bytes() == module.read_bytes()
    assert built == [first, second], "both immutable cache hits must reuse their build"


def test_cached_installation_retries_an_edit_during_compilation(
    prepared_cache, monkeypatch
):
    """A racing edit needs no second filesystem event to get its own kernel."""
    module, built = prepared_cache
    runtime = distribution.ROOT
    first = module.read_bytes()
    second = b"export const example = 2;"
    prepare = distribution.prepare

    def edit_during_compilation(output, runtime):
        prepare(output, runtime)
        if len(built) == 1:
            module.write_bytes(second)

    monkeypatch.setattr(distribution, "prepare", edit_during_compilation)
    selected = distribution.cached_installation(runtime)
    assert (selected / "runtime/bundle.js").read_bytes() == second
    assert built == [first, second]


def test_cached_installation_retries_an_edit_while_staging_publication(
    prepared_cache, monkeypatch
):
    """A staged snapshot overtaken by an edit never becomes a published entry."""
    module, built = prepared_cache
    runtime = distribution.ROOT
    first = module.read_bytes()
    second = b"export const example = 2;"
    write_json = distribution.write_json
    edited = False

    def edit_during_publication(path, record):
        nonlocal edited
        write_json(path, record)
        if not edited:
            module.write_bytes(second)
            edited = True

    monkeypatch.setattr(distribution, "write_json", edit_during_publication)
    selected = distribution.cached_installation(runtime)
    assert (selected / "runtime/bundle.js").read_bytes() == second
    assert built == [first, second]
    publications = [
        path for path in distribution.cache_root().iterdir() if path.is_dir()
    ]
    assert publications == [selected]


def test_cached_installation_rechecks_provenance_before_publication(
    prepared_cache, monkeypatch
):
    """A Git-label change during publication selects the current label."""
    producer = {"commit": "first", "dirty": False}
    monkeypatch.setattr(
        distribution, "payload_provenance", lambda **kwargs: dict(producer)
    )
    write_json = distribution.write_json

    def commit_during_publication(path, record):
        write_json(path, record)
        producer["commit"] = "second"

    monkeypatch.setattr(distribution, "write_json", commit_during_publication)
    selected = distribution.cached_installation(distribution.ROOT)
    assert json.loads((selected / "leaf-distribution.json").read_text())[
        "producer"
    ] == (producer)
    publications = [
        path for path in distribution.cache_root().iterdir() if path.is_dir()
    ]
    assert publications == [selected]


@pytest.fixture
def prepared_cache(tmp_path, monkeypatch):
    """Exercise cache selection with real files and locks, without the compiler."""
    monkeypatch.setattr(distribution, "ROOT", tmp_path)
    monkeypatch.setenv("LEAF_DEV_CACHE_DIR", str(tmp_path / "cache"))
    module = tmp_path / "browser/runtime/example.js"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"export const example = 1;")
    built = []

    def prepare(output, runtime):
        bundle = output / "runtime/bundle.js"
        bundle.parent.mkdir(parents=True)
        source = module.read_bytes()
        built.append(source)
        bundle.write_bytes(source)
        distribution.write_json(
            output / "leaf-distribution.json",
            {"producer": distribution.payload_provenance(root=runtime)},
        )

    monkeypatch.setattr(distribution, "prepare", prepare)
    return module, built


def aged_entries(cache, ages):
    now = time.time()
    for name, age in ages.items():
        (cache / name).mkdir()
        os.utime(cache / name, (now - age, now - age))


def test_eviction_keeps_recent_entries_and_drops_old_ones(tmp_path, monkeypatch):
    """An entry nothing has selected for hours goes, however few entries there are."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path.parent / "state"))
    aged_entries(tmp_path, {"new": 0, "recent": 3600, "old": 4 * 3600})
    distribution.evict(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_dir()) == [
        "new",
        "recent",
    ]


def test_eviction_keeps_an_entry_a_session_launches_from(tmp_path, monkeypatch):
    """A preview left open for days still runs from its entry."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    cache = tmp_path / "cache"
    cache.mkdir()
    aged_entries(cache, {"used": 3 * 86400, "unused": 3 * 86400})
    launcher = cache / "used/bin/leaf"
    launcher.parent.mkdir()
    launcher.touch()
    distribution.state.write_session(
        {
            **distribution.state.new_session("s", {"kind": "test"}),
            "launcher": str(launcher),
        }
    )
    distribution.evict(cache)
    assert sorted(p.name for p in cache.iterdir() if p.is_dir()) == ["used"]


def test_eviction_rechecks_age_after_a_reader_selects_the_entry(tmp_path, monkeypatch):
    """A reader that touches an entry while eviction waits for its lock keeps it."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    aged_entries(tmp_path, {"old": 3 * 86400})
    flocked = distribution.flocked

    @contextlib.contextmanager
    def reader_wins_the_lock(path):
        with flocked(path):
            os.utime(tmp_path / "old")
            yield

    monkeypatch.setattr(distribution, "flocked", reader_wins_the_lock)
    distribution.evict(tmp_path)
    assert (tmp_path / "old").is_dir()
