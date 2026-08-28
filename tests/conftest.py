"""Shared fixtures for payload modules exposed through pytest's source root."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import host as host_model
from playwright.sync_api import sync_playwright

INTERACT_SCRIPT = (
    Path(__file__).parent.parent
    / "plugins"
    / "leaf"
    / "skills"
    / "leaf"
    / "scripts"
    / "interact.py"
)
# Domain test modules import their assertions explicitly; these two support modules
# own the shared fixtures and register them once for the complete suite.
pytest_plugins = ("interact_support", "render_support")


@pytest.fixture(scope="session")
def clone_initialized_page(tmp_path_factory):
    """Clone one initialized page shape without recomposing its layer per test.

    Runtime and vendor files are immutable inputs for tests whose subject starts
    after initialization. Hard links keep those large bytes shared; page state,
    the registry, theme, entry module, and widget modules remain private copies.
    A re-vendor replaces linked files atomically, so it also stays private.
    """
    templates = {}
    root = tmp_path_factory.mktemp("page-templates")

    def clone(name, destination, initialize):
        if name not in templates:
            template = root / name
            initialize(template)
            templates[name] = template
        template = templates[name]

        def copy_fixture_file(source, target):
            relative = Path(source).relative_to(template)
            if relative.parts[0] in {"runtime", "vendor"}:
                os.link(source, target)
                return target
            return shutil.copy2(source, target)

        shutil.copytree(template, destination, copy_function=copy_fixture_file)
        status_path = destination / "status.json"
        status = files_model.read_json(status_path)
        status["ts"] = events_model.now_iso()
        files_model.write_json(status_path, status)

    return clone


def pytest_addoption(parser):
    parser.addoption(
        "--run-nightly",
        action="store_true",
        default=False,
        help="Also run the complete browser and published-site integration suites",
    )


def pytest_collection_modifyitems(config, items):
    """Broad discovery stays cheap; explicit selections run what they name."""
    selected = (
        config.getoption("keyword")
        or config.getoption("markexpr")
        or config.getoption("lf")
        or any(Path(arg.split("::", 1)[0]).is_file() for arg in config.args)
    )
    if config.getoption("--run-nightly") or selected:
        return
    nightly = [item for item in items if "nightly" in item.keywords]
    items[:] = [item for item in items if "nightly" not in item.keywords]
    config.hook.pytest_deselected(items=nightly)


# A host session states its identity in the environment, under names of its own.
# The suite is a Claude Code session, and `host_identity` reads that set first, so
# a test about a Codex session, or about no session at all, takes it away.
CLAUDE_IDENTITY = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDE_JOB_DIR")
CODEX_IDENTITY = ("CODEX_THREAD_ID", "LEAF_SESSION_ID", "LEAF_AGENT")


@pytest.fixture(autouse=True)
def isolated_session(tmp_path_factory, monkeypatch):
    """The run is an agent session of its own, in state directories of its own.

    Keep the developer's session out of every fixture. Their real
    ~/.config/leaf overlay would otherwise change what init vendors and check
    measures, and a page tagged with the session running the tests is a page the
    loop-guard hook reports as an unattended page at the end of every turn —
    a dozen throwaway fixtures per run.

    Move what leaf reads and nothing else. `config_home` and `state_home` are
    the whole of what it takes from the developer's home, so the two XDG
    directories are the whole of the isolation. Moving HOME instead reaches past
    them and takes uv's cache with it, and every `bin/leaf` subprocess then
    resolves from scratch — the fixtures that export an example spent around two
    minutes each fetching a Playwright the developer already had. What that bought
    back was a pair of env overrides, UV_CACHE_DIR handing the cache back and
    UV_OFFLINE forbidding the index it no longer needed to ask; scripts/site.py
    had already found the shorter way, and says so where it builds its env.

    The session the tests run as is this worker: a synthetic id, so nothing of
    the developer's answers for it, and the worker's own pid. Every page a test
    serves is claimed under that pid, and leaf stops a claimed page's server once
    its claimant is gone — the one reaper that reaches a server spawned into a
    session of its own, and so the only thing that ends one when a run is killed
    outright (tests/CLAUDE.md, "A process the suite starts ends with the run"). A
    run started from a background job leaves that job's directory behind too, as
    it would any other fact about the developer's session. A test about a
    command run from outside a host session strips the identity:
    `sessionless`.

    The state home is the fixture's value, for `_no_page_outlives_its_test`:
    the sweep takes its root from here rather than from the environment, which
    it would read before this fixture sets it and after `monkeypatch` unsets it
    (tests/CLAUDE.md, "A process the suite starts ends with the run")."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("config")))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", f"pytest-{os.getpid()}")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    for name in CODEX_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    return host_model.state_home()


@pytest.fixture
def sessionless(monkeypatch):
    """A command run from outside any host session: a terminal, a login item."""
    for name in CLAUDE_IDENTITY + CODEX_IDENTITY:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def codex_env():
    """The environment a Codex session's commands run in, for the tests that put
    a real one above a leaf: everything this process holds but the Claude Code
    identity, which `host_identity` would answer with instead."""
    return {k: v for k, v in os.environ.items() if k not in CLAUDE_IDENTITY}


@pytest.fixture
def spawn():
    """A process the test starts, ended when the test ends — the ones it expects
    to have exited already included, since a run that fails before its own
    assertion is exactly the one that would leave a process behind."""
    started = []

    def start(*args, **kwargs) -> subprocess.Popen:
        process = subprocess.Popen(*args, **kwargs)
        started.append(process)
        return process

    yield start
    for process in reversed(started):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


@pytest.fixture
def dead_pid(spawn):
    """A pid that is certainly not running, for a record whose writer — a
    session, a server — has gone."""
    spent = spawn([sys.executable, "-c", ""])
    spent.wait(timeout=5)
    return spent.pid


@pytest.fixture(scope="session")
def browser():
    """Playwright's pinned Chromium headless shell, driven for the tests a static
    read can't answer: what a widget upgrades into, and what the site fits on.

    With no channel named, Playwright uses its separate headless shell rather than
    installed Chrome's platform-window path. Session scope gives xdist one browser
    per worker that requests it; the everyday smoke requests one, and the complete
    run can occupy all eight.

    The scope does not reach isolation, which is per context: `new_page` opens a
    fresh context per call, and a fresh context has empty `localStorage` and
    `sessionStorage` — the state a `goto` inside one would carry over
    (tests/CLAUDE.md, "Reloading is not resetting")."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()
