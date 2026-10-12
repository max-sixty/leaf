"""Shared fixtures, and the address the suite starts a leaf process at."""

import ast
import contextlib
import inspect
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import psutil
import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import harness as harness_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import machine as machine_model
from leaf.render_gate import browser as browser_model
from leaf_dev import LEAF_COMMAND
from leaf_dev.browser import LINUX_FONTCONFIG, require_linux_fonts
from leaf_dev.page_fixtures import package_selection_args
from playwright.sync_api import sync_playwright

__all__ = ["LEAF_COMMAND"]

# The canonical subprocess command. Tests of the installed harness boundary invoke
# that payload's `bin/leaf`; every other process test runs the checkout directly.
# Start every child the way a terminal starts one. A run launched as a shell's
# background job is handed SIGINT set to SIG_IGN, and an inherited SIG_IGN
# survives both Python startup and `exec`, so everything the run spawns ignores
# the signal too: a test that interrupts its own child would pass or fail on how
# the run was launched, and the child would outlive it still serving its page.
# A caught signal is what `exec` resets to the default in each child.
signal.signal(signal.SIGINT, signal.default_int_handler)
# Domain test modules import their assertions explicitly. Register only the modules
# that own fixtures once for the complete suite.
pytest_plugins = ("interact_support", "render_harness")


# The layer a page carries is the same bytes in every fixture, and the file it
# is made of is what a copy costs: an initialized page is 195 files, 158 of them
# runtime modules, and the suite wants one page per test. Measured when a page
# was 146, copying them all made a complete run 2,272 pages and 393,473
# directory entries, which is the number a filesystem event watcher charges for
# — hard links share the bytes but not the entry. So the layer is written once
# per shape and lent, and only what a test actually changed is put back. A
# stamped revision's bundle is immutable too, so a shape's revisions are linked
# like its layer.
LENT_LINKED_DIRS = frozenset({"runtime", "vendor", "revisions"})


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
    the revision it stamped. `reset` reads the
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
        self.shapes = {}  # key -> PageShape
        self.free = {}  # key -> [page]
        self.stamps = {}  # page -> {relative path: identity}

    def _shape(self, key, initialize):
        if key not in self.shapes:
            template = self.root / str(len(self.shapes))
            initialize(template)
            self.shapes[key] = PageShape(
                template,
                directories=frozenset(
                    path.relative_to(template).as_posix()
                    for path in template.rglob("*")
                    if path.is_dir()
                ),
                files=_stamp(template),
            )
            self.free[key] = []
        return self.shapes[key]

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

    def lend(self, key, destination, initialize):
        shape = self._shape(key, initialize)
        if self.free[key]:
            page = self.free[key].pop()
            stamp = self._reset(shape, page)
            os.rename(page, destination)
            del self.stamps[page]
        else:
            shutil.copytree(shape.template, destination, copy_function=shape.compose)
            stamp = _stamp(destination)
        self.stamps[destination] = stamp
        return destination

    def give_back(self, key, page):
        self.free[key].append(page)


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
def initialized_page(_page_pool, tmp_path):
    """Put a page initialized with `packages` at `destination`, from the pool.

    `prepared`, a `(key, step)` pair, runs `step` on the page after `page init`, and
    `key` tells its shape from the bare initialized one: an example's stamped
    versions, or a fixed document. The pool keys a shape by what makes it: the
    selection as recorded, the package directories it resolves to as `page init`
    resolves them, and that key. So no caller names a shape, and two callers that
    make the same page share it.

    A package the test wrote under its own `tmp_path` has new contents under the
    same path in every test, so a selection resolving into it is initialized in
    place rather than pooled. A bundled package, a checkout path, and an installed
    snapshot, which is immutable, hold still for the run.
    A test whose subject is initialization, re-vendoring or an overlay runs
    `page init` itself.

    Runtime and vendor files are hard links shared with the shape, so a test never
    writes through one in place: re-vendoring replaces those files, and the next loan
    rejects an in-place write by name.
    """
    lent = []
    own = tmp_path.resolve()

    def lend(destination, packages, prepared=None):
        destination = Path(destination)
        packages = tuple(packages)
        key, step = prepared or (None, None)

        def initialize(target):
            made = CliRunner().invoke(
                cli_model.cli,
                ["page", "init", *package_selection_args(packages), str(target)],
            )
            assert made.exit_code == 0, made.output
            if step:
                step(target)

        resolved = tuple(
            root.resolve() for root in layer_model.resolve_packages(packages)
        )
        if any(root.is_relative_to(own) for root in resolved):
            initialize(destination)
            return destination
        shape = (packages, resolved, key)
        page = _page_pool.lend(shape, destination, initialize)
        lent.append((shape, page))
        return page

    yield lend
    for key, page in lent:
        _page_pool.give_back(key, page)


def pytest_addoption(parser):
    parser.addoption(
        "--run-main",
        action="store_true",
        default=False,
        help="Also run the `main` tier, as a push to main does",
    )
    parser.addoption(
        "--run-nightly",
        action="store_true",
        default=False,
        help="Run every tier, as the daily schedule and a manual dispatch do",
    )
    parser.addoption(
        "--changed-since",
        metavar="REF",
        help="Also run the `browser` and `journeys` tests whose own source changed since REF",
    )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A test body that returns has its last shifts and lost words judged before its
    fixtures end (`render_harness.judge_watches`)."""
    from render_harness import judge_watches

    result = yield
    judge_watches()
    return result


# A test's directory under `tests/` is its tier, which says when CI runs it. The
# first tier, None, runs in every selection: a pull request, `wt merge`, and broad
# discovery. A `main` test can land without running and runs on each push to main
# (`--run-main`); a `nightly` one runs only in the daily schedule and a manual
# dispatch (`--run-nightly`), which run every tier. `leaf_dev.suite_profile.BUDGETS`
# holds what a test in each directory may cost.
TESTS = Path(__file__).parent
TIERS = {
    "model": None,
    "process": None,
    "smoke": None,
    "browser": "main",
    "journeys": "nightly",
}


def run_tier(item):
    """The tier of the directory a test module lives in. A module anywhere else is a
    usage error, so a new file cannot fall outside every tier."""
    directory = item.path.relative_to(TESTS).parts[0]
    if directory not in TIERS:
        raise pytest.UsageError(
            f"{item.path}: a test module lives in tests/<tier>/, one of {', '.join(TIERS)}"
        )
    return TIERS[directory]


def pytest_collection_modifyitems(config, items):
    """Broad discovery runs the tests whose `run_tier` is the first and the tiers its
    flags reach; explicit selections run what they name.

    A change that moves a browser behaviour usually edits the test that holds it, so both
    landing gates add the tests of either later tier whose own source the change
    touches (`--changed-since`): those run before it lands, and CI's `test` job runs
    the rest of each tier when that tier's event comes.

    Selecting by the code a change touches would catch more, but this design makes
    that map coarse. Browser tests reach code through a served page, not imports, so
    the map would have to come from recorded Python and Chrome coverage. Nearly every
    browser test loads the same runtime and server, so a change there, about half of
    recent commits, would select close to the complete suite, and coverage cannot say
    which CSS rules a test relied on."""
    selected = (
        config.getoption("keyword")
        or config.getoption("markexpr")
        or config.getoption("lf")
        or any(_names_tests(Path(arg.split("::", 1)[0])) for arg in config.args)
    )
    # Every collected test names its tier, whatever runs it, so a module outside
    # every tier directory is refused by each selection.
    tiers = [run_tier(item) for item in items]
    if config.getoption("--run-nightly") or selected:
        return
    reached = {"main"} if config.getoption("--run-main") else set()
    changed = None
    if since := config.getoption("--changed-since"):
        changed = _base_sources(config.rootpath, since)
    kept, skipped = [], []
    for item, tiered in zip(items, tiers):
        runs = tiered is None or tiered in reached or _touches(item, changed)
        (kept if runs else skipped).append(item)
    items[:] = kept
    config.hook.pytest_deselected(items=skipped)


def _names_tests(path):
    """Whether an argument names tests inside `tests/`, a tier directory or a file in
    one, rather than the whole suite."""
    path = path.resolve()
    return path.exists() and path.is_relative_to(TESTS) and path != TESTS


def _base_sources(root, since):
    """Each test function's source, decorators included, where `since` and HEAD part,
    keyed by its module's name and its own. A test that moved to another tier directory
    keeps its key, so a move that leaves its source alone is no edit of it."""

    def git(*args, stdin=None):
        run = subprocess.run(
            ["git", *args], cwd=root, input=stdin, capture_output=True, check=False
        )
        if run.returncode:
            raise pytest.UsageError(
                f"--changed-since {since}: {run.stderr.decode().strip()}"
            )
        return run.stdout

    base = git("merge-base", since, "HEAD").decode().strip()
    paths = [
        path
        for path in git("ls-tree", "-r", "--name-only", base, "--", "tests")
        .decode()
        .split()
        if re.fullmatch(r"tests/(\w+/)?test_\w+\.py", path)
    ]
    batch = git(
        "cat-file", "--batch", stdin="".join(f"{base}:{p}\n" for p in paths).encode()
    )
    sources = {}
    for path in paths:
        header, _, batch = batch.partition(b"\n")
        size = int(header.split()[2])
        text, batch = batch[:size].decode(), batch[size + 1 :]
        lines = text.splitlines(keepends=True)
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                sources[Path(path).stem, node.name] = "".join(
                    lines[first - 1 : node.end_lineno]
                )
    return sources


def _touches(item, base):
    """Whether a change edits the test's own function, decorators included."""
    if base is None:
        return False
    source = "".join(inspect.getsourcelines(item.function)[0])
    return base.get((item.path.stem, item.function.__name__)) != source


# A harness session states its identity in the environment, under names of its own
# (`harness.IDENTITY_VARIABLES`). The suite is a Claude Code session, and
# `session_harness` answers with it wherever no nearer harness's process runs above
# the command, so a test about a Codex session takes this away, and a test about
# no session at all takes the whole set (`sessionless`).
CLAUDE_IDENTITY = harness_model.ClaudeCodeHarness.identity_variables
# The Claude Code sessions `isolated_session` marks as hooked: the worker's own
# and the id lifecycle fixtures claim under (`record_claim`).
HOOKED_SESSIONS = (f"pytest-{os.getpid()}", "s1")


@pytest.fixture(scope="session", autouse=True)
def failing_harness_programs(tmp_path_factory):
    """Put a `claude` and a `codex` that fail at once ahead of the developer's own on
    PATH, for the entire worker lifetime, before any fixture starts a server.
    Page servers ask the claimant's harness to name user threads (`thread_titles`);
    a test about titling puts its own program first."""
    programs = tmp_path_factory.mktemp("harness-programs")
    for name in ("claude", "codex"):
        program = programs / name
        program.write_text("#!/bin/sh\nexit 1\n")
        program.chmod(0o755)
    os.environ["PATH"] = f"{programs}{os.pathsep}{os.environ['PATH']}"


@pytest.fixture(autouse=True)
def isolated_session(tmp_path_factory, monkeypatch):
    """The run is an agent session of its own, in state directories of its own.

    Keep the developer's session and machine state out of every fixture. A page
    tagged with the session running the tests is otherwise reported as unattended
    by the loop guard. Isolate XDG_STATE_HOME, where Leaf stores claims and installed
    packages, and CODEX_HOME, where Codex reads its configuration and sessions,
    while retaining HOME so subprocesses share the host's uv cache. Clear the
    developer's App Server endpoint and host launcher override so a fake task
    cannot use them.

    The session the tests run as is this worker: a synthetic id, so nothing of
    the developer's answers for it, and the worker's own pid. Every page a test
    serves is claimed under that pid, and leaf stops a claimed page's server once
    its claimant is gone — the one reaper that reaches a server spawned into a
    session of its own, and so the only thing that ends one when a run is killed
    outright (tests/AGENTS.md, "Processes and servers"). A
    run started from a background job leaves that job's directory behind too, as
    it would any other fact about the developer's session. A test about a
    command run from outside a harness session strips the identity:
    `sessionless`.

    The state home is the fixture's value, for `_no_page_outlives_its_test`:
    the sweep takes its root from here rather than from the environment, which
    it would read before this fixture sets it and after `monkeypatch` unsets it
    (tests/AGENTS.md, "Processes and servers")."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path_factory.mktemp("codex")))
    monkeypatch.delenv(codex_model.APP_SERVER_ENV, raising=False)
    monkeypatch.delenv("LEAF_HOST_LAUNCHER", raising=False)
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    # Claude Code's session registry, where a live turn is read
    # (`harness.claude_code_session_records`): empty, so no session of the developer's
    # answers for a test's.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("claude")))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", f"pytest-{os.getpid()}")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    # A Claude Code session whose harness runs Leaf's hooks, as the plugin installs
    # them, supplying capability evidence to hook transport and turn activity.
    for session in HOOKED_SESSIONS:
        leases_model.mark_hooks(session)
    return machine_model.state_home()


@pytest.fixture
def sessionless(monkeypatch):
    """A command run from outside any harness session: a terminal, a login item."""
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def codex_env():
    """The environment a Codex session's commands run in, for the tests that put
    a real one above a leaf: everything this process holds but the Claude Code
    identity, which `session_harness` answers with wherever no codex runs above
    the command, as for a process the Codex task detaches."""
    return {k: v for k, v in os.environ.items() if k not in CLAUDE_IDENTITY}


def _retire(process: subprocess.Popen) -> None:
    """End one started process and everything still in the group it leads.

    The handle a test keeps often names a launcher rather than the process doing
    the work: `leaf-dev preview` re-executes into `uv run`, which holds the
    watcher as a child, and `under_codex`'s fake host holds the shell that runs
    the command. Ending the handle alone leaves those running past the test and
    the run, serving pages or watching the checkout. Closing the stdin a test
    piped ends what waits on it, as a held `under_codex` shell does, even where
    the test already ended the leader itself.
    """
    # Imported here: `interact_support` imports this module, and is loaded as the
    # plugin `pytest_plugins` names so that its assertions are rewritten.
    from interact_support import STATED_TIMEOUT

    if process.stdin:
        with contextlib.suppress(BrokenPipeError):
            process.stdin.close()
    # The group outlives a leader that exits before its children. A pid is not
    # reused while a group bears it, so a reaped leader whose pid nothing holds
    # still names this group, and one whose pid a process holds again names a
    # group that has already ended. A group left with only zombies, as when the
    # leader exits during the signal, is one macOS refuses to signal.
    if process.poll() is None or not psutil.pid_exists(process.pid):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=STATED_TIMEOUT)


@pytest.fixture
def spawn():
    """A process the test starts, ended with everything it started when the test
    ends — the ones it expects to have exited already included, since a run that
    fails before its own assertion is exactly the one that would leave a process
    behind. Each leads a session of its own, so `_retire` can end it and the
    descendants still in its group without signalling the worker running the test.
    A descendant that starts a session of its own, as a detached server does, is
    left to the fixture that owns it."""
    started = []

    def start(*args, **kwargs) -> subprocess.Popen:
        process = subprocess.Popen(*args, start_new_session=True, **kwargs)
        started.append(process)
        return process

    yield start
    for process in reversed(started):
        _retire(process)


@pytest.fixture
def dead_pid(spawn):
    """A pid that is certainly not running, for a record whose writer — a
    session, a server — has gone."""
    from interact_support import STATED_TIMEOUT

    spent = spawn([sys.executable, "-c", ""])
    spent.wait(timeout=STATED_TIMEOUT)
    return spent.pid


@pytest.fixture(scope="session")
def _playwright():
    """The one Playwright driver a worker may hold; every browser engine launches from it."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def _browser(_playwright):
    """Playwright's pinned Chromium headless shell, driven for the tests a static
    read can't answer: what a widget upgrades into, and what the site fits on.

    With no channel named, Playwright uses its separate headless shell rather than
    installed Chrome's platform-window path. Session scope gives xdist one browser
    per worker that requests it; the broad selection's smoke requests one, and the complete
    run can occupy all eight.

    Each test receives this process through the function-scoped `browser` fixture,
    which closes any contexts the test leaves open."""
    b = _playwright.chromium.launch()
    yield b
    b.close()


@pytest.fixture
def browser(_browser, request):
    """The shared browser process, with context ownership scoped to one test.

    `Browser.new_page` opens a fresh context, so local and session storage remain
    isolated. Rejecting browser problems and then closing every remaining context at
    teardown makes health and lifetime fixture guarantees instead of conventions
    repeated at the end of each journey. Closing may itself cancel outstanding requests,
    so it happens after the health reading.

    Handed over wrapped, because the health half of that guarantee has to be installed
    on each page before it navigates: a test that makes its own page gets one already
    reporting to the collector this reads (`render_harness.WatchedBrowser`).
    """
    from render_harness import WatchedBrowser, clean_browser

    try:
        with clean_browser(request.node):
            yield WatchedBrowser(_browser)
    finally:
        for context in reversed(_browser.contexts):
            context.close()


@pytest.fixture
def firefox_browser(_playwright, request):
    """Desktop Firefox, including its compositor's inherited-colour painting."""
    from render_harness import WatchedBrowser, clean_browser

    firefox = _playwright.firefox.launch()
    try:
        with clean_browser(request.node):
            yield WatchedBrowser(firefox)
    finally:
        firefox.close()


@pytest.fixture
def webkit_browser(_playwright, request):
    """Desktop WebKit, where wheel gestures can exercise nested scroll boundaries."""
    from render_harness import WatchedBrowser, clean_browser

    webkit = _playwright.webkit.launch()
    try:
        with clean_browser(request.node):
            yield WatchedBrowser(webkit)
    finally:
        webkit.close()


@pytest.fixture
def iphone(_playwright, request):
    """A WebKit context shaped like an iPhone: its viewport, pixel ratio, touch, and
    user agent. WebKit is the engine iPhone browsers run on, so this is what a phone
    user meets whichever browser they open the page in. Browser problems are rejected
    as in `browser`, and its pages arrive readable for the same reason."""
    from render_harness import WatchedContext, clean_browser

    webkit = _playwright.webkit.launch()
    try:
        with clean_browser(request.node):
            yield WatchedContext(webkit.new_context(**_playwright.devices["iPhone 15"]))
    finally:
        webkit.close()


@pytest.fixture
def scrollbar_browser(_playwright, request):
    """The Chromium shell with its scrollbars shown. The shared `browser` launches with
    Playwright's default `--hide-scrollbars`, under which the root's scrollbar takes no
    width, so nothing that turns on a classic scrollbar's gutter can be read there. A
    page still draws overlay scrollbars on some hosts; one that styles
    `::-webkit-scrollbar` gets a classic bar everywhere. Browser problems are rejected
    as in `browser`, and its pages arrive readable for the same reason."""
    from render_harness import WatchedBrowser, clean_browser

    shown = _playwright.chromium.launch(ignore_default_args=["--hide-scrollbars"])
    try:
        with clean_browser(request.node):
            yield WatchedBrowser(shown)
    finally:
        shown.close()


@pytest.fixture(scope="session", autouse=True)
def headless_shell():
    """Name the pinned headless shell as the host's browser for the rest of the run,
    and return its path.

    The run is a host, and names its browser the way one does, through
    LEAF_BROWSER_EXECUTABLE, so every leaf it runs draws with the build the `_browser`
    fixture drives. Left unnamed, each `page check` that runs a page's code or takes
    `--render` would launch the installed Google Chrome afresh: about three seconds
    apiece, and on macOS about a second of the keychain daemon's CPU for each new
    process, where the shell costs neither. A test whose subject is how a host that
    named no browser gets one clears every variable (`test_render_commands`,
    `unnamed_browser`).

    Playwright reports where its full Chromium build would be whether or not that
    build is installed, and the documented setup installs the shell alone
    (tests/AGENTS.md, "Run what the change needs"). Both sit under one
    registry root at one build number, so the shell's path follows from Chromium's;
    where a developer installed the full build instead, that is the browser to hand
    over and the same tests hold on it. The `chromium-<build>` directory is found by
    name rather than by depth, because macOS nests the executable inside an app
    bundle and Linux does not.

    Asked in a subprocess because the answer is a path and the question is not free
    here: a second `sync_playwright()` inside this process raises where the
    session's `browser` fixture already holds one open, so which tests had run
    first would decide whether the fixture worked."""
    if sys.platform == "linux":
        require_linux_fonts()
        os.environ["FONTCONFIG_FILE"] = str(LINUX_FONTCONFIG)
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
    executable = next(
        (str(c) for c in (*shell_executables, chromium) if c.is_file()), None
    )
    if executable is None:
        raise AssertionError(
            f"no Playwright Chromium under {root}; run `uv run playwright install "
            "chromium --only-shell` (tests/AGENTS.md)"
        )
    os.environ[browser_model.VARIABLE] = executable
    return executable
