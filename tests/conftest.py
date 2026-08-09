"""Shared fixtures. interact.py is loaded by path because it is a `uv` script,
not an installed module."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

# uv keeps its cache under the developer's home, and the fixture below moves that
# home, so every `bin/colloquy` subprocess would otherwise resolve its
# dependencies from scratch — a second per call. Pinning the cache leaves the
# isolation to the thing it is for, which is the colloquy overlay.
#
# `--color never` because uv colours this path even into a pipe, and a cache
# directory wearing an escape sequence is a relative path starting with one: the
# pinning silently stopped happening, and every run built a second cache inside
# the checkout under a directory named for the escape itself.
UV_CACHE = subprocess.run(
    ["uv", "--color", "never", "cache", "dir"],
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()

# Set on import rather than per test, because a fixture cannot reach what runs before it.
# These two say where uv looks and that it looks no further than there, which is a fact
# about the whole run; `isolated_session` below is about one test's session and is the
# wrong scope for them. It had them, and the higher-scoped fixtures that shell out — the
# `site` fixture, which exports every example — were built first and so went out to the
# index unprotected: seven setups spending 113 to 121 seconds each revalidating an
# unpinned Playwright against PyPI, and erroring outright the day the network was gone.
# The same seven run in 28 seconds against the cache.
#
# `version export` supplies Playwright outside interact.py.lock (bin/colloquy says why),
# leaving its version unpinned, so uv revalidates it whenever the cached answer goes
# stale. The cache already holds what uv.lock pinned, so reading from it is both the fix
# and the faster path.
os.environ["UV_CACHE_DIR"] = UV_CACHE
os.environ["UV_OFFLINE"] = "1"

_spec = importlib.util.spec_from_file_location(
    "interact",
    Path(__file__).parent.parent
    / "plugins"
    / "colloquy"
    / "skills"
    / "colloquy"
    / "scripts"
    / "interact.py",
)
interact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(interact)


# `version export` supplies Playwright outside interact.py.lock (bin/colloquy says
# why), leaving its version unpinned, so uv revalidates it against the index whenever
# the cached answer goes stale — three retries per call, and test_site.py exports every
# example. The cache already holds what uv.lock pinned, so reading from it is both the
# fix and the faster path.
#
# Session-scoped because scope is what decides whether it arrives in time. Set from a
# function-scoped fixture, this reached every test and none of the module-scoped
# fixtures a test asks for: pytest builds those first, so test_site.py's whole site —
# every example exported — was built before the setting existed, and the one module
# that spends the most on this was the one module without it. Nothing said so while the
# index answered; the day it didn't, seven tests failed in setup naming a PyPI timeout,
# with an offline suite around them.
@pytest.fixture(scope="session", autouse=True)
def uv_reads_its_cache():
    """Keep every uv the suite shells out to off the index, whatever fixture ran it."""
    patch = pytest.MonkeyPatch()
    patch.setenv("UV_CACHE_DIR", UV_CACHE)
    patch.setenv("UV_OFFLINE", "1")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def isolated_session(tmp_path_factory, monkeypatch):
    """Keep the developer's session out of every fixture. Their real
    ~/.config/colloquy overlay would otherwise change what init vendors and check
    measures, and a page tagged with the session running the tests is a page the
    loop-guard hook reports as an unattended page at the end of every turn —
    a dozen throwaway fixtures per run. An untagged page is nobody's, which is
    what a fixture should be."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.delenv("COLLOQUY_SESSION_ID", raising=False)
    monkeypatch.delenv("COLLOQUY_SESSION_PID", raising=False)
    monkeypatch.delenv("COLLOQUY_AGENT", raising=False)


@pytest.fixture(scope="module")
def browser():
    """The Chrome already on the machine, driven for the tests a static read
    can't answer: what a widget upgrades into, and what the site fits on."""
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        yield b
        b.close()
