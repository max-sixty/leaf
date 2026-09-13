"""Shared fixtures, and the address the suite starts a leaf process at."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import host as host_model
from playwright.sync_api import sync_playwright

# The leaf a test runs as a process of its own. There is no script to name any
# more: the payload is a distribution this environment installs, so `python -m
# leaf` under this interpreter is the CLI's only address that does not go
# through a launcher — and it is the one leaf uses for its own children, in
# `hosting.start_server` and `cmd_codex_start`. Use it wherever the subject is
# what a command does. Where the subject is what a host actually runs — the
# launcher's own resolution, or a process chain that has to look like one an
# agent started — a test runs `PLUGIN_ROOT / "bin" / "leaf"` instead, and gets
# uv, the payload project and the environment uv syncs for it along with it.
LEAF_COMMAND = [sys.executable, "-m", "leaf"]
# Domain test modules import their assertions explicitly. Register only the modules
# that own fixtures once for the complete suite.
pytest_plugins = (
    "interact_support",
    "render_harness",
    "render_cases_layout",
    "render_cases_navigation",
)


# The layer a page carries is the same bytes in every fixture, and the file it
# is made of is what a copy costs: an initialized page is 146 files, 99 of them
# runtime modules, and the suite wants one page per test. Copying them all makes
# a complete nightly run 2,272 pages and 393,473 directory entries, which is the
# number a filesystem event watcher charges for — hard links share the bytes but
# not the entry. So the layer is written once per shape and lent, and only what
# a test actually changed is put back.
LENT_LINKED_DIRS = frozenset({"runtime", "vendor"})


class PagePool:
    """One initialized page per shape, lent to a test and reset for the next.

    A page directory is leaf's deployment unit, and the server enforces that:
    `http` serves a file only where `path_is_within` puts it inside the page it
    is serving, and `path_location` resolves symlinks first, so a layer symlinked
    to a shared copy is a page that 404s its own runtime. `page init` refuses one
    outright. The layer therefore has to be real files in the page, and the only
    way to stop paying for them per test is to stop making a page per test.

    What a test leaves behind is small: a served page differs from the shape it
    was made from in `index.html`, `events.jsonl`, `status.json`, `viewed.json`,
    the revision it stamped and its `.fixture-versions`. `reset` reads the
    difference off the filesystem rather than a list — every file whose identity,
    size or modification time moved is put back from the shape, every file and
    directory the test added is removed — so a page a test changed in some way
    nobody anticipated still comes back as the shape, and a new page-owned file
    needs nothing here.

    The lent page is moved to the caller's own path, not handed over where it
    lies: a test that selects a fixture package beside its page reaches it as
    `page_dir.parent / ".leaf"`, and `_no_page_outlives_its_test` sweeps
    `tmp_path` for a server still standing. It is left there when the test ends
    and moved again on the next loan, so the sweep runs while the page is still
    under the root it walks.
    """

    def __init__(self, root):
        self.root = root
        self.shapes = {}  # name -> PageShape
        self.free = {}  # name -> [page]
        self.stamps = {}  # page -> {relative path: identity}

    def _shape(self, name, initialize):
        if name not in self.shapes:
            template = self.root / name
            initialize(template)
            self.shapes[name] = PageShape(
                template,
                directories=frozenset(
                    path.relative_to(template).as_posix()
                    for path in template.rglob("*")
                    if path.is_dir()
                ),
                files=_stamp(template),
            )
            self.free[name] = []
        return self.shapes[name]

    def _reset(self, shape, page):
        """Make the page the shape again, from what the filesystem says moved."""
        stamp = self.stamps[page]
        kept = {}
        for path in sorted(page.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            relative = path.relative_to(page).as_posix()
            # A symlink is whatever a test made it; it is never one of the shape's
            # own files, so it goes as a file rather than as the tree it points at.
            if path.is_dir() and not path.is_symlink():
                if relative not in shape.directories:
                    shutil.rmtree(path)
            elif relative not in stamp:
                path.unlink()
            elif (identity := _identity(path)) == stamp[relative]:
                kept[relative] = identity
            else:
                path.unlink()
        for relative in shape.directories:
            (page / relative).mkdir(parents=True, exist_ok=True)
        for relative in stamp:
            if relative not in kept:
                kept[relative] = shape.restore(page, relative)
        return kept

    def lend(self, name, destination, initialize):
        shape = self._shape(name, initialize)
        if self.free[name]:
            page = self.free[name].pop()
            stamp = self._reset(shape, page)
            os.rename(page, destination)
            del self.stamps[page]
        else:
            shutil.copytree(shape.template, destination, copy_function=shape.compose)
            stamp = _stamp(destination)
        self.stamps[destination] = stamp
        return destination

    def give_back(self, name, page):
        self.free[name].append(page)


class PageShape(NamedTuple):
    """A composed layer, what a page holding it looks like, and how one is made."""

    template: Path
    directories: frozenset[str]
    files: dict[str, tuple[int, int, int]]

    def compose(self, source, target):
        if Path(source).relative_to(self.template).parts[0] in LENT_LINKED_DIRS:
            os.link(source, target)
            return target
        return shutil.copy2(source, target)

    def restore(self, page, relative):
        source = self.template / relative
        if relative.split("/", 1)[0] in LENT_LINKED_DIRS:
            # A linked file and its source are one inode, so a test that wrote
            # through the link changed the shape itself, and every page made from
            # it after would carry that. Nothing writes a page's layer in place —
            # vendoring replaces — so a mismatch here is the sharing rule broken.
            assert _identity(source) == self.files[relative], (
                f"{relative} was written through the hard link it shares with "
                f"{self.template}"
            )
            os.link(source, page / relative)
        else:
            shutil.copy2(source, page / relative)
        return _identity(page / relative)


def _identity(path):
    """What tells one state of a file from the next, without reading it.

    `lstat`, so a symlink a test left where a file belongs answers as itself —
    a different inode from the file it replaced, and an answer at all where it
    points nowhere."""
    info = path.lstat()
    return (info.st_ino, info.st_size, info.st_mtime_ns)


def _stamp(page):
    """Every file in a page as it stands, which is what the next reset asks it."""
    return {
        path.relative_to(page).as_posix(): _identity(path)
        for path in page.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="session")
def _page_pool(tmp_path_factory):
    return PagePool(tmp_path_factory.mktemp("page-templates"))


@pytest.fixture
def initialized_page(_page_pool):
    """Put an initialized page of the named shape at the caller's path.

    The shape is composed once per worker by the caller's own `initialize`, so a
    test whose subject is initialization, re-vendoring or an overlay still
    crosses the real `page init` boundary by calling this with a shape of its
    own — or by not calling it at all.
    """
    lent = []

    def lend(name, destination, initialize):
        page = _page_pool.lend(name, Path(destination), initialize)
        lent.append((name, page))
        status_path = page / "status.json"
        status = files_model.read_json(status_path)
        status["ts"] = events_model.now_iso()
        files_model.write_json(status_path, status)
        return page

    yield lend
    for name, page in lent:
        _page_pool.give_back(name, page)


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

    Keep the developer's session and machine state out of every fixture. A page
    tagged with the session running the tests is otherwise reported as unattended
    by the loop guard. Isolate XDG_STATE_HOME, where Leaf stores claims and installed
    packages, while retaining HOME so subprocesses share the host's uv cache.

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
def _browser():
    """Playwright's pinned Chromium headless shell, driven for the tests a static
    read can't answer: what a widget upgrades into, and what the site fits on.

    With no channel named, Playwright uses its separate headless shell rather than
    installed Chrome's platform-window path. Session scope gives xdist one browser
    per worker that requests it; the everyday smoke requests one, and the complete
    run can occupy all eight.

    Each test receives this process through the function-scoped `browser` fixture,
    which closes any contexts the test leaves open."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def browser(_browser):
    """The shared browser process, with context ownership scoped to one test.

    `Browser.new_page` opens a fresh context, so local and session storage remain
    isolated. Closing every remaining context at teardown makes that lifetime a
    fixture guarantee instead of a convention repeated at the end of each journey.
    """
    yield _browser
    for context in reversed(_browser.contexts):
        context.close()


@pytest.fixture(scope="session")
def headless_shell():
    """The path of a browser that is not installed Chrome, for the tests that hand
    one to a leaf process through LEAF_BROWSER_EXECUTABLE.

    Playwright reports where its full Chromium build would be whether or not that
    build is installed, and the documented setup installs the shell alone
    (tests/CLAUDE.md, "Run the narrowest useful surface"). Both sit under one
    registry root at one build number, so the shell's path follows from Chromium's;
    where a developer installed the full build instead, that is the browser to hand
    over and the same tests hold on it. The `chromium-<build>` directory is found by
    name rather than by depth, because macOS nests the executable inside an app
    bundle and Linux does not.

    Asked in a subprocess because the answer is a path and the question is not free
    here: a second `sync_playwright()` inside this process raises where the
    session's `browser` fixture already holds one open, so which tests had run
    first would decide whether the fixture worked."""
    read = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from playwright.sync_api import sync_playwright\n"
                "with sync_playwright() as p: print(p.chromium.executable_path)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    chromium = Path(read.stdout.strip())
    versioned = next(
        (p for p in chromium.parents if p.name.startswith("chromium-")), None
    )
    if versioned is None:
        raise AssertionError(f"{chromium} is not under a Playwright chromium build")
    root, build = versioned.parent, versioned.name.rsplit("-", 1)[1]
    shell = root / f"chromium_headless_shell-{build}"
    shell_executables = sorted(shell.glob("*/chrome-headless-shell*")) + sorted(
        shell.glob("*/headless_shell")
    )
    for candidate in (*shell_executables, chromium):
        if candidate.is_file():
            return str(candidate)
    raise AssertionError(
        f"no Playwright Chromium under {root}; run `uv run playwright install "
        "chromium --only-shell` (tests/CLAUDE.md)"
    )
