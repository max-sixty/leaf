"""Shared fixtures. interact.py is loaded by path because it is a `uv` script,
not an installed module."""

import importlib.util
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

_spec = importlib.util.spec_from_file_location(
    "interact",
    Path(__file__).parent.parent
    / "plugins"
    / "leaf"
    / "skills"
    / "leaf"
    / "scripts"
    / "interact.py",
)
interact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(interact)


def pytest_addoption(parser):
    parser.addoption(
        "--run-nightly",
        action="store_true",
        default=False,
        help="Also run the tests that reach the package index",
    )


def pytest_runtest_setup(item):
    """Hold back the tests that reach the package index, so an everyday run needs
    no network at all. What earns a test the mark, and what still runs it, is in
    CLAUDE.md beside this file."""
    if "nightly" in item.keywords and not item.config.getoption("--run-nightly"):
        pytest.skip(f"--run-nightly not passed — skipping {item}")


@pytest.fixture(autouse=True)
def isolated_session(tmp_path_factory, monkeypatch):
    """Keep the developer's session out of every fixture. Their real
    ~/.config/leaf overlay would otherwise change what init vendors and check
    measures, and a page tagged with the session running the tests is a page the
    loop-guard hook reports as an unattended page at the end of every turn —
    a dozen throwaway fixtures per run. An untagged page is nobody's, which is
    what a fixture should be.

    Move what leaf reads and nothing else. `config_home` and `state_home` are
    the whole of what it takes from the developer's home, so the two XDG
    directories are the whole of the isolation. Moving HOME instead reaches past
    them and takes uv's cache with it, and every `bin/leaf` subprocess then
    resolves from scratch — the fixtures that export an example spent around two
    minutes each fetching a Playwright the developer already had. What that bought
    back was a pair of env overrides, UV_CACHE_DIR handing the cache back and
    UV_OFFLINE forbidding the index it no longer needed to ask; scripts/site.py
    had already found the shorter way, and says so where it builds its env."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("LEAF_SESSION_ID", raising=False)
    monkeypatch.delenv("LEAF_AGENT", raising=False)


@pytest.fixture(scope="session")
def browser():
    """The Chrome already on the machine, driven for the tests a static read
    can't answer: what a widget upgrades into, and what the site fits on.

    Session-scoped, which under xdist is one Chrome per worker for the run.
    Module scope launched a second whenever a worker crossed between the two
    modules that use this fixture — eleven launches on a two-module slice where
    eight workers need eight. Launches are all it saves: eight Chromes are alive
    at the peak either way, each a browser process, a GPU process, and a handful
    of windows registered with WindowServer, which sat at 130% with five suites
    running at once.

    The scope does not reach isolation, which is per context: `new_page` opens a
    fresh context per call, and a fresh context has empty `localStorage` and
    `sessionStorage` — the state a `goto` inside one would carry over
    (tests/CLAUDE.md, "Reloading is not resetting")."""
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        yield b
        b.close()
