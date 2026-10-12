"""Arms, served pages, and isolated CC, Codex and Pi sessions for the commands and eval
harnesses that run a version of Leaf.

An arm is the plugin payload (`PAYLOAD`) at one ref, or as the working tree has it, and
nothing else: no `.git`, examples or notes, so a child cannot read its way to another
arm's version. An A/B's base is the merge base with the local `main` unless the caller
names another ref (`base_ref`).

A child runs from a scratch cwd outside any repository, so no project instructions
load, under a home of its own beside that cwd, so its bypassed permissions write to
that home rather than the user's `~` (children given the user's home once appended to
the user's `~/.claude/CLAUDE.md`). The home carries only the login. A trace is the
child's normalized tool/turn evidence; it counts when its harness turn completed
(`completed`). CC raw stdout and Codex notifications are retained too.
A `LiveChild` keeps its session open across turns, so a driver can post
user moves to a served page (`PageClient`) as a tab would; a `LiveSession` is how
every live driver holds one: it records the stream, sends chat messages, and tells
when the session has gone quiet. On macOS a Claude Code child runs under
`private_tmp`, so concurrent children share no file in `/tmp`.
"""

import base64
import http.cookiejar
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import IO, Self

import click
from leaf.codex import APP_SERVER_ENV
from leaf.delivery import opened_input_ids
from leaf.harness import IDENTITY_VARIABLES, ClaudeCodeHarness, CodexHarness
from leaf.hook_transport import DELIVERY_FIELD
from leaf.tasks import start_reading
from leaf.thread import successful_replies

from leaf_dev import ROOT
from leaf_dev.page_fixtures import prepare_page, read_fixture

# The uv project names this package's `pyproject.toml` as a workspace member, so uv
# needs that file to read the lock. The package itself stays out: the launcher never
# installs the dev group. A ref from before the package has no such file. The root
# `package.json` makes the payload a Pi package.
PAYLOAD = (
    ".claude/skills/developing-leaf",
    ".claude/skills/ui-sweep",
    ".agents/plugins",
    ".claude-plugin",
    ".codex-plugin",
    "LICENSE",
    "bin",
    "hooks",
    "skills",
    "package.json",
    "leaf-distribution.json",
    "pyproject.toml",
    "uv.lock",
    "dev/pyproject.toml",
    "worker/pyproject.toml",
)

# The harnesses an arm's child runs, named as the shipped harness names itself.
HARNESSES = (ClaudeCodeHarness.name, CodexHarness.name)

# The models evals run, pinned so runs on different days compare: each harness's
# agents, the judge behind `llm-rubric` assertions, the screenshot judge, and the
# agent that plays the user in a page's browser.
MODELS = {
    ClaudeCodeHarness.name: "claude-opus-5-5",
    CodexHarness.name: "gpt-6.1-sol",
    "judge": "claude-sonnet-5-5",
    "screenshots": "gpt-6.1-sol",
    "user": "claude-sonnet-5-5",
}


def run_directory(parent: Path) -> Path:
    """Allocate one invocation's evidence without replacing another run's files."""
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="run-", dir=parent))


def environment(**extra: str) -> dict[str, str]:
    """This process's environment without the agent session it may be running in.

    A harness run from a Claude Code or Codex session inherits that session's
    identity: its id, job directory, effort level and App Server endpoint. A `leaf`
    command would sign events as that session, and a child would use its transport
    and settings. `CLAUDE_CONFIG_DIR`
    stays, since it names where the login lives."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in (*IDENTITY_VARIABLES, APP_SERVER_ENV)
        and not (key.startswith("CLAUDE") and key != "CLAUDE_CONFIG_DIR")
    }
    return {**env, **extra}


def run_leaf(
    arm: Path,
    state: Path,
    *args: str,
    check: bool = False,
    timeout: float | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """Run an arm's launcher under a state home of its own."""
    proc = subprocess.run(
        [str(arm / "bin/leaf"), *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=environment(XDG_STATE_HOME=str(state)),
    )
    if check and proc.returncode:
        raise click.ClickException(
            f"leaf {' '.join(args)} exited {proc.returncode}:\n{proc.stdout}{proc.stderr}"
        )
    return proc


@contextmanager
def serving(arm: Path, state: Path, page: Path):
    """Serve `page` with the arm's `leaf server run --temporary` under the state home
    `state`, and yield the tokened URL it prints."""
    server = subprocess.Popen(
        [str(arm / "bin" / "leaf"), "server", "run", "--temporary", str(page)],
        env=environment(XDG_STATE_HOME=str(state)),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        yield json.loads(server.stdout.readline())["url"]
    finally:
        # A loaded host can take longer than this to wind a server down; its page is
        # scratch, so a server still running then is killed rather than failing the run.
        # The launcher is uv, which cannot pass a kill on, so the kill takes the group.
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)
            server.wait()


def build_source(arm: Path, state: Path, source: Path, page: Path) -> None:
    """Build the authored `source` into the page directory `page` with the arm's own
    launcher under the state home `state`. The checkout is an arm too: `ROOT` runs
    its working tree."""
    prepare_page(
        page,
        read_fixture(source, runtime=arm, env=environment(XDG_STATE_HOME=str(state))),
        partial(run_leaf, arm, state, check=True),
    )


@contextmanager
def serving_source(arm: Path, source: Path, scratch: Path):
    """Build `source` into a page under `scratch` (`build_source`), serve it
    (`serving`), and yield the address."""
    state, page = scratch / "state", scratch / "page"
    build_source(arm, state, source, page)
    with serving(arm, state, page) as address:
        yield address


def merge_base(ref: str = "HEAD") -> str:
    """The commit `ref` branched from the local `main`: the base an A/B command
    compares HEAD against unless it is handed another."""
    return subprocess.run(
        ["git", "-C", ROOT, "merge-base", ref, "main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def copy_working(paths: Iterable[str], dest: Path) -> None:
    """Copy the files under `paths` into `dest` as the working tree has them: tracked
    and unignored untracked files, the ones an install copies, with edits included
    and links kept as links."""
    listed = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z", "--cached", "--others"]
        + ["--exclude-standard", "--", *paths],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    # A conflicted file is listed once per stage; a deleted one is still in the index.
    for name in dict.fromkeys(filter(None, listed)):
        source, target = ROOT / name, dest / name
        if source.is_symlink() or source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)


def copy_committed(paths: Iterable[str], dest: Path, ref: str) -> None:
    """Extract the requested paths present at `ref` into an existing destination."""
    present = subprocess.run(
        ["git", "-C", ROOT, "ls-tree", "--name-only", ref, *paths],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    archive = subprocess.run(
        ["git", "-C", ROOT, "archive", ref, *present],
        capture_output=True,
        check=True,
    ).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=archive, check=True)


def extract_payload(
    dest: Path, ref: str | None = None, *, paths: Iterable[str] = PAYLOAD
) -> None:
    """Write `paths` at git `ref`, or as the working tree has it when `ref` is None
    (`copy_working`), into `dest`, replacing whatever was there."""
    if dest.exists():
        # A caller may have made an arm read-only.
        subprocess.run(["chmod", "-R", "u+w", dest], check=True)
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if ref is not None:
        copy_committed(paths, dest, ref)
    else:
        copy_working(paths, dest)


def build_arm(ref: str | None, dest: Path, *, paths: Iterable[str] = PAYLOAD) -> str:
    """Extract `paths` at `ref`, or as the working tree has it when `ref` is None,
    into `dest`, replacing any earlier arm there, and build its environment; return
    the commit, HEAD's for the working tree."""
    extract_payload(dest, ref, paths=paths)
    with tempfile.TemporaryDirectory() as state:
        run_leaf(dest, Path(state), "--root", check=True)
    return subprocess.run(
        ["git", "-C", ROOT, "rev-parse", f"{ref or 'HEAD'}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def base_ref(ref: str | None) -> str:
    """The ref an A/B command compares HEAD against: the one it was handed, else
    `merge_base()`."""
    return ref or merge_base()


def build_pair(base: str | None, dest: Path) -> tuple[dict[str, Path], dict[str, str]]:
    """Build an A/B's arms under `dest`: `base` at `base_ref(base)` and `head` at
    HEAD. Return each arm's directory and its commit, both keyed `base` and `head`."""
    refs = {"base": base_ref(base), "head": "HEAD"}
    arms = {arm: dest / arm for arm in refs}
    return arms, {arm: build_arm(ref, arms[arm]) for arm, ref in refs.items()}


def load_average() -> str:
    """The machine's 1, 5 and 15 minute load averages."""
    return " ".join(f"{value:.1f}" for value in os.getloadavg())


def codex_program() -> Path:
    """Resolve the host CLI used to install plugins and run isolated Codex tasks."""
    if (installed := shutil.which("codex")) is None:
        raise click.ClickException("Codex tasks require the Codex CLI; install it")
    return Path(installed).resolve()


def install_codex_plugin(
    codex: Path,
    payload: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    output: IO[str] | None = None,
) -> None:
    """Install a complete Leaf payload through Codex's native marketplace commands.

    Callers supply the isolated task's environment and its CLI. Output is captured
    on subprocess failures, or streamed whole to `output` when the caller keeps a
    log; native installer JSON documents are separate from task JSON-lines logs.
    """
    streams = (
        {"stdout": output, "stderr": subprocess.STDOUT}
        if output is not None
        else {"capture_output": True, "text": True}
    )
    for arguments in (
        ("plugin", "marketplace", "add", str(payload), "--json"),
        ("plugin", "add", "leaf@leaf", "--json"),
    ):
        subprocess.run(
            [str(codex), *arguments], cwd=cwd, env=env, check=True, **streams
        )


def codex_home(path: Path, config: str = "") -> Path:
    """Make `path` a Codex home holding a copy of the host's login and `config` as its
    `config.toml`, so a Codex child run with `CODEX_HOME=path` reads none of the
    host's settings, plugins, hooks or task history. Codex still reads the user's
    `~/.agents/skills`, which `CODEX_HOME` does not move."""
    path.mkdir(mode=0o700)
    host = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth = path / "auth.json"
    shutil.copyfile(host / "auth.json", auth)
    auth.chmod(0o600)
    (path / "config.toml").write_text(config)
    return path


def pi_home(path: Path) -> Path:
    """Make `path` a Pi home (`PI_CODING_AGENT_DIR`) whose only login is the host's
    Codex login, as Pi's `openai-codex` provider, which uses the Codex CLI's OAuth
    client and so takes its access token as is.

    The copy leaves out the refresh token: refreshing it rotates it, which would log
    the host's Codex out. A login that expires within the hour is refused, since the
    copy cannot outlive it."""
    host = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    tokens = json.loads((host / "auth.json").read_text())["tokens"]
    claims = tokens["access_token"].split(".")[1]
    expires = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))[
        "exp"
    ]
    if expires - time.time() < 3600:
        raise click.ClickException(
            "The Codex login expires within the hour; run `codex` once to refresh it."
        )
    path.mkdir(mode=0o700)
    auth = path / "auth.json"
    auth.write_text(
        json.dumps(
            {
                "openai-codex": {
                    "type": "oauth",
                    "access": tokens["access_token"],
                    "refresh": "",
                    "expires": expires * 1000,
                    "accountId": tokens["account_id"],
                }
            }
        )
    )
    auth.chmod(0o600)
    return path


def claude_home(path: Path) -> Path:
    """Make `path` a home (`HOME`) holding the host's Claude Code login, so a Claude
    Code child run under it reads none of the host's settings, plugins, hooks,
    instructions or sessions. A macOS login is in the keychain, which the home
    links to; elsewhere it is a copy of the host's credentials."""
    # The home may hold a copy of the user's login, so no one else may enter it.
    path.mkdir(mode=0o700, exist_ok=True)
    path.chmod(0o700)
    keychains = Path.home() / "Library/Keychains"
    if keychains.is_dir() and not (path / "Library/Keychains").is_symlink():
        (path / "Library").mkdir(parents=True, exist_ok=True)
        (path / "Library/Keychains").symlink_to(keychains)
    credentials = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        / ".credentials.json"
    )
    if credentials.is_file():
        (path / ".claude").mkdir(parents=True, exist_ok=True)
        shutil.copy(credentials, path / ".claude/.credentials.json")
    return path


def claude_environment(home: Path, **extra: str) -> dict[str, str]:
    """The environment of a Claude Code child under `home` (`claude_home`): its
    config is the home's, never one `CLAUDE_CONFIG_DIR` names, and it shares the
    host's uv cache and keeps no memory."""
    env = environment(
        HOME=str(home),
        UV_CACHE_DIR=os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache/uv")),
        CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
        **extra,
    )
    env.pop("CLAUDE_CONFIG_DIR", None)
    return env


@contextmanager
def scratch():
    """Own a scenario's cwd and sibling credential home until scoring ends."""
    with tempfile.TemporaryDirectory(prefix="leaf-eval-") as directory:
        work = Path(directory) / "cwd"
        work.mkdir()
        yield work


def private_tmp(*owned: Path) -> str:
    """The macOS sandbox profile a Claude Code child runs under, so that two
    children never share a file under `/tmp`.

    Its `TMPDIR` is already its own (`claude_child`), but authoring agents also
    write fixed names there, such as `/tmp/chk.py`, which a concurrent sample would
    overwrite. Writes to `/tmp` are refused except under `owned`, the child's own
    directories, wherever they are, and the names Claude Code and Leaf give their
    own machine-local files there: Claude Code's per-user directory and each
    shell's cwd file and socket, and Leaf's per-user package locks and each App
    Server's socket directory. The sandbox resolves `/tmp` to `/private/tmp`, so
    the rules name that."""
    uid = os.getuid()
    names = (
        rf"claude-{uid}(/|$)|claude-[0-9a-f]+-cwd$|cc-socks(/|$)"
        rf"|leaf-package-locks-{uid}(/|$)|leaf-codex-[^/]+(/|$)"
    )
    return "\n".join(
        [
            "(version 1)",
            "(allow default)",
            '(deny file-write* (subpath "/private/tmp"))',
            f'(allow file-write* (regex #"^/private/tmp/({names})"))',
            *(
                f"(allow file-write* (subpath {json.dumps(str(path.resolve()))}))"
                for path in owned
            ),
            "",
        ]
    )


def claude_child(
    cwd: Path,
    *args: str,
    dirs: Iterable[Path] = (),
    env: dict | None = None,
    model: str = MODELS[ClaudeCodeHarness.name],
    sandbox: bool = True,
) -> dict:
    """The `subprocess` arguments for one isolated `claude -p` child in `cwd`.

    `args` follow `-p`, so a prompt goes first. `dirs` are what the child may read
    beyond `cwd`, and `env` adds to `environment()`. Output is verbose stream-json.
    On macOS the child runs under `private_tmp`, owning `cwd`, its home and
    `dirs`, unless `sandbox` is False, as a child that drives the harness's own
    browser is."""
    dirs = list(dirs)
    (cwd / "tmp").mkdir(exist_ok=True)
    home = claude_home(cwd.with_name(f"{cwd.name}-home"))
    command = [
        "claude", "-p", *args, "--model", model,
        "--strict-mcp-config", "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
        "--verbose", *(arg for d in dirs for arg in ("--add-dir", str(d))),
    ]  # fmt: skip
    if sandbox and shutil.which("sandbox-exec"):
        profile = private_tmp(cwd, home, *dirs)
        command = ["sandbox-exec", "-p", profile, *command]
    child_env = claude_environment(home, TMPDIR=str(cwd / "tmp"), **(env or {}))
    return {"args": command, "cwd": cwd, "env": child_env}


# Duration is evidence to diagnose, not a task's correctness criterion. Allow
# hours for a native turn and a day for workflows that contain several turns.
TURN_LIMIT = 6 * 60 * 60
WORKFLOW_LIMIT = 24 * 60 * 60


def run_agent(
    cwd: Path,
    *args: str,
    out: Path,
    err: Path,
    dirs: Iterable[Path] = (),
    env: dict | None = None,
    harness: str = ClaudeCodeHarness.name,
    limit: float = TURN_LIMIT,
    **options: str | bool,
) -> list[dict]:
    """Run an isolated harness turn, optionally resuming its preceding session.

    `out` is normalized evidence; `err` is stderr. Codex's complete App Server
    notifications live beside `err` with a `.codex.jsonl` suffix. Both harnesses
    have the same `limit`, TURN_LIMIT unless the caller bounds its turn more
    tightly; a timeout retains their partial native evidence and
    marks `out.with_suffix(".timed-out")` without fabricating completion. `options`
    passes a Claude Code child's `model` and `sandbox` (`claude_child`).
    """
    if harness == CodexHarness.name:
        with (
            LiveChild(
                cwd,
                args[0],
                *args[1:],
                harness=harness,
                stderr=err,
                limit=limit,
                timed_out=out.with_suffix(".timed-out"),
                dirs=dirs,
                env=env,
            ) as child,
            out.open("w") as stream,
        ):
            for record in child.records():
                stream.write(json.dumps(record) + "\n")
                if record.get("type") == "result":
                    break
        return read_trace(out)
    if harness != ClaudeCodeHarness.name:
        raise ValueError(f"unknown eval harness: {harness}")
    with out.open("w") as stdout, err.open("w") as stderr:
        try:
            subprocess.run(
                **claude_child(cwd, *args, dirs=dirs, env=env, **options),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=True,
                timeout=limit,
            )
        except subprocess.TimeoutExpired:
            out.with_suffix(".timed-out").touch()
    return read_trace(out)


def LiveChild(*args, harness=ClaudeCodeHarness.name, **kwargs):
    """Open the harness's native live session for automatic Leaf delivery."""
    return child_class(harness)(*args, **kwargs)


class ClaudeSession:
    """Keep a native session open while the driver exercises Leaf feedback.

    The driver closes the session after observing the required page outcome.
    Close sends SIGTERM so Claude retires its watcher and runs SessionEnd; neither
    a final model reply nor a zero exit status is required after intentional close.
    One timer bounds the whole session. Native output is retained beside stderr.
    """

    transport: str | None = None

    def __init__(
        self,
        cwd: Path,
        prompt: str,
        *args: str,
        stderr: Path,
        limit: float,
        timed_out: Path,
        dirs: Iterable[Path] = (),
        env: dict | None = None,
    ) -> None:
        self.prompt, self.stderr, self.timed_out = prompt, stderr, timed_out
        self.popen = claude_child(
            cwd,
            "--input-format",
            "stream-json",
            "--include-hook-events",
            *args,
            dirs=dirs,
            env=env,
        )
        self.deadline = threading.Timer(limit, self._give_up)
        self.closing = False

    def __enter__(self) -> Self:
        self.raw = self.stderr.with_suffix(".cc.jsonl").open("w")
        self.stderr_stream = self.stderr.open("w")
        try:
            self.proc = subprocess.Popen(
                **self.popen,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.stderr_stream,
                start_new_session=True,
                text=True,
            )
        except BaseException:
            self.raw.close()
            self.stderr_stream.close()
            raise
        self.deadline.start()
        try:
            self.send(self.prompt)
        except BaseException:
            self.__exit__()
            raise
        return self

    def send(self, text: str) -> None:
        """Send the user's next chat message; a turn still running takes it next."""
        message = {"type": "user", "message": {"role": "user", "content": text}}
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def records(self):
        """The native stream; malformed output and unexpected exits raise."""
        for line in self.proc.stdout:
            self.raw.write(line)
            self.raw.flush()
            yield {**json.loads(line), "received_at": now()}
        code = self.proc.wait()
        if code and not self.closing:
            raise subprocess.CalledProcessError(code, self.popen["args"])

    def close(self) -> None:
        """Stop the native session once the driver has its required outcome."""
        if self.closing:
            return
        self.closing = True
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._kill_group()
                self.proc.wait()
        self._kill_group()

    abort = close

    def _kill_group(self) -> None:
        self.proc.poll()
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _give_up(self) -> None:
        self.timed_out.touch()
        self._kill_group()

    def __exit__(self, *exc) -> None:
        self.deadline.cancel()
        self.deadline.join()
        try:
            self.close()
            # The caller joins its sole observer before leaving this context.
            shutil.copyfileobj(self.proc.stdout, self.raw)
        finally:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
            self.proc.stdout.close()
            self.stderr_stream.close()
            self.raw.close()


def child_class(harness: str) -> type:
    """The live session class that runs `harness`, and so the transport it takes."""
    if harness == CodexHarness.name:
        from leaf_dev.eval_codex import CodexChild

        return CodexChild
    if harness != ClaudeCodeHarness.name:
        raise ValueError(f"unknown eval harness: {harness}")
    return ClaudeSession


def now() -> str:
    """The time a live driver stamps on each record as `received_at`."""
    return datetime.now().astimezone().isoformat()


# What a `LiveSession`'s reader hands over once its child's records end.
_ENDED = object()
# How long a `LiveSession` leaving its context lets a closed child's records end.
CLOSING = 30


class LiveSession:
    """A `LiveChild` as a driver plays its user, the one mechanism every live eval
    driver shares.

    The child's native records go to the file `stream`, each written before the
    driver sees it, with the driver's own records (`note`) between them where it
    makes them. A thread reads the child in lockstep with the driver: it reads the
    next record only once the driver asks for it, so whatever the driver does on a
    record happens before anything the child does after it. Reading with `idle`
    yields None each time that long passes without a record, so a driver can tell
    a quiet session from one still working (`settle`).

    `watch` names the arm, its state home and the page the session serves. Once
    the page is served the session records `eval_served` with its keyed URL, which
    `url` holds, and at each turn's end `eval_status` with the page's status, from
    the time the page exists."""

    def __init__(
        self, child, stream: Path, watch: tuple[Path, Path, Path] | None = None
    ) -> None:
        self.child, self.path, self.watch = child, stream, watch
        self.url: str | None = None
        self.handed = queue.Queue()
        self.taken = threading.Event()
        self.stopping = False
        # The turns ended so far, whether one is running, and when the last record
        # arrived.
        self.answered, self.running, self.heard = 0, False, time.monotonic()

    def __enter__(self) -> Self:
        self.stream = self.path.open("w")
        try:
            self.child = self.child.__enter__()
        except BaseException:
            self.stream.close()
            raise
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        return self

    def _read(self) -> None:
        try:
            for record in self.child.records():
                self.handed.put(record)
                self.taken.wait()
                self.taken.clear()
                if self.stopping:
                    return
        # The driver's thread raises what the child's records raised.
        except BaseException as error:  # noqa: BLE001
            self.handed.put(error)
            return
        self.handed.put(_ENDED)

    def note(self, record: dict) -> None:
        """Write one of the driver's own records into the stream."""
        self.stream.write(json.dumps(record) + "\n")
        self.stream.flush()

    def records(self, idle: float | None = None, before=None):
        """The child's native records, each written to the stream first, until it
        ends. `before`, given each record, runs before it is written, so what it
        notes precedes the record. With `idle`, None stands for each `idle`
        seconds without a record."""
        while True:
            try:
                item = self.handed.get(timeout=idle)
            except queue.Empty:
                yield None
                continue
            if item is _ENDED:
                return
            if isinstance(item, BaseException):
                raise item
            try:
                if before is not None:
                    before(item)
                self.note(item)
                self._observe(item)
                self.heard = time.monotonic()
                if item.get("type") == "result":
                    self.answered, self.running = self.answered + 1, False
                elif item.get("type") in ("assistant", "user"):
                    self.running = True
                yield item
            finally:
                self.taken.set()

    def _observe(self, record: dict) -> None:
        # An agent authoring the page has not made it yet.
        if self.watch is None or not (self.watch[2] / "events.jsonl").exists():
            return
        if not self.url and record.get("type") in ("user", "result"):
            server = read_page_state(*self.watch)["server"]
            if server:
                self.url = server["url"]
                self.note(
                    {"type": "eval_served", "url": self.url, "received_at": now()}
                )
        if record.get("type") == "result":
            state = read_page_state(*self.watch)
            self.note(
                {
                    "type": "eval_status",
                    "status": state.get("status"),
                    "listening": state["listening"],
                    "received_at": now(),
                }
            )

    def send(self, text: str) -> None:
        """Send the user's next chat message, recording it as `eval_send`."""
        self.note({"type": "eval_send", "text": text, "received_at": now()})
        self.child.send(text)

    def settle(self, since: int, *, grace: float, wake: float, before=None) -> bool:
        """Read until the session has answered and gone quiet: more than `since`
        turns have ended (`answered`), none is running, and `grace` seconds have
        passed without a record. A turn runs from its first message to its result,
        however long a tool call inside it takes. Return False when, before that
        answer, `wake` seconds pass with no turn running and no record, as when
        nothing reached the session."""
        self.heard = time.monotonic()
        for record in self.records(idle=1, before=before):
            if record is not None:
                continue
            quiet = time.monotonic() - self.heard
            if self.answered <= since and not self.running and quiet >= wake:
                return False
            if self.answered > since and not self.running and quiet >= grace:
                return True
        return self.answered > since

    def during(self, action, before=None):
        """Run `action` while the session's records keep being read, so the child
        never waits on its output, and return what it returns."""
        done: queue.Queue = queue.Queue()

        def run():
            try:
                done.put((True, action()))
            # Raised again in the driver's thread.
            except BaseException as error:  # noqa: BLE001
                done.put((False, error))

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            for _ in self.records(idle=0.5, before=before):
                if not worker.is_alive():
                    break
        finally:
            # The action owns a browser and children of its own, which end with it
            # even when the session's records fail first.
            worker.join()
        succeeded, value = done.get()
        if not succeeded:
            raise value
        return value

    def close(self) -> None:
        """End the session; its remaining records still reach `records`."""
        self.child.close()

    def __exit__(self, *exc) -> None:
        self.stopping = True
        self.taken.set()
        try:
            self.child.close()
            # A closed Claude Code child's output ends at once. A Codex child's
            # records wait out a running turn, which only leaving its context, and
            # so its socket, interrupts.
            self.reader.join(timeout=CLOSING)
            self.child.__exit__(*exc)
            self.reader.join()
        finally:
            self.stream.close()


# A served page's keyed URL, as `leaf server start` prints it.
URL = re.compile(r"https?://[^\s\"\\]+\?t=[A-Za-z0-9_-]+")


class PageClient:
    """A served page's API, reached the way a tab reaches it: token and cookies."""

    def __init__(self, url: str) -> None:
        parts = urllib.parse.urlsplit(url)
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.token = urllib.parse.parse_qs(parts.query)["t"][0]
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    @property
    def state_url(self) -> str:
        return f"{self.origin}/api/state?t={self.token}"

    def state(self) -> dict:
        with self.opener.open(self.state_url, timeout=20) as response:
            return json.loads(response.read())

    def post(self, event: dict) -> dict:
        """Post one move as the page does: keyed, on the served layer, and return the
        state the server answers with, which shows the move. The caller names the
        revision and the retry key, as the browser does.

        An answer naming another layer than the one posted on admitted nothing: the
        page was re-vendored between the state read and the post. A tab reloads onto
        that layer and the user moves again, so the move is posted again under it.
        """
        layer = self.state()["layer"]["generation"]
        while True:
            request = urllib.request.Request(
                f"{self.origin}/api/event?t={self.token}",
                data=json.dumps(event).encode(),
                headers={"Leaf-Layer": layer},
            )
            try:
                with self.opener.open(request, timeout=20) as response:
                    answered = response.headers["Leaf-Layer"]
                    answer = json.loads(response.read())
            except urllib.error.HTTPError as error:
                raise click.ClickException(
                    f"posting {event}: HTTP {error.code} {error.read().decode()}"
                ) from error
            if answered == layer:
                return answer["state"]
            layer = answered


def read_page_state(arm: Path, state: Path, page: Path) -> dict:
    """Read this arm's canonical page, including its keyed server address.

    Live drivers choose their write destination here. Agent text and tool output
    can name other pages and remain only evidence of what the agent handed over.
    """
    return json.loads(
        run_leaf(arm, state, "page", "state", str(page), check=True).stdout
    )


def commands(record: dict) -> list[str]:
    """What each tool call in one stream record runs, or the tool and its file."""
    content = (record.get("message") or {}).get("content")
    return [
        block["input"].get("command")
        or " ".join(filter(None, [block["name"], block["input"].get("file_path")]))
        for block in (content if isinstance(content, list) else ())
        if block.get("type") == "tool_use"
    ]


def waits_started(record: dict) -> list[str]:
    """The ids of the backgrounded `leaf wait` calls one stream record makes, however
    the command spells the launcher: `leaf`, its path, or a variable holding it."""
    content = (record.get("message") or {}).get("content")
    return [
        block["id"]
        for block in (content if isinstance(content, list) else ())
        if block.get("type") == "tool_use"
        and block["name"] == "Bash"
        and re.search(r"(\bleaf|\$\{?\w+\}?) wait\b", block["input"].get("command", ""))
        and block["input"].get("run_in_background")
    ]


def hook_delivered(record: dict) -> bool:
    """Whether one stream record is a Leaf hook handing a delivery to the turn: its
    output, the hook's whole stdout, names one in `DELIVERY_FIELD`. Other hooks in
    the same trace, such as the background watch, print text that is not JSON."""
    if record.get("subtype") != "hook_response":
        return False
    try:
        output = json.loads(record.get("output") or "")
    except json.JSONDecodeError:
        return False
    return isinstance(output, dict) and DELIVERY_FIELD in output


def inputs_received(events: list[dict], attempts: set[str]) -> bool:
    """Whether a posted round is admitted and its attention inputs are received.

    Inline context, pointer reads, and attempted ACK commands are presentations,
    not acceptance. Every attempt must be admitted; only attention-marked inputs
    require the opened pickups that name exactly what the reader received.
    Page-authored errors carry no user attempt and do not advance user rounds.
    """
    posted = [e for e in events if e.get("attempt") in attempts]
    inputs = {e["id"] for e in posted if e["attention"]}
    return len(posted) == len(attempts) and inputs <= opened_input_ids(events)


def read_trace(stream: Path) -> list[dict]:
    """An unrun phase has no trace; malformed retained evidence still raises."""
    return (
        [json.loads(line) for line in stream.read_text().splitlines()]
        if stream.exists()
        else []
    )


def trace_result(trace: list[dict]) -> dict:
    """The trace's closing `result` event, or {} when the child never finished."""
    return next((d for d in reversed(trace) if d.get("type") == "result"), {})


def blocks(trace: list[dict]):
    """Every content block of every message: tool calls, tool results, text."""
    for d in trace:
        message = d.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        yield from (b for b in content or [] if isinstance(b, dict))


def completed(trace: list[dict]) -> bool:
    """Whether a trace counts: its model call reached a result that is not an
    error."""
    return trace_result(trace).get("is_error") is False


def observed_sum(values: Iterable[int | float | None]) -> int | float | None:
    """Sum complete measurements; absent or incomplete evidence stays unknown."""
    observed = list(values)
    return sum(observed) if observed and all(v is not None for v in observed) else None


def token_counts(trace: list[dict]) -> dict[str, int | None]:
    """Count observed completed turns, preserving unknown counters independently.

    CC reports cache input separately; Codex includes it in input_tokens. Optional
    cache subdivisions add to a reported input counter, never stand in for one.
    A missing result or missing usage cannot establish zero consumption.
    """
    usage = [
        record.get("usage") or {} for record in trace if record.get("type") == "result"
    ]
    return {
        "input_tokens": observed_sum(
            observed_sum(
                [
                    counts.get("input_tokens"),
                    counts.get("cache_creation_input_tokens", 0),
                    counts.get("cache_read_input_tokens", 0),
                ]
            )
            for counts in usage
        ),
        "output_tokens": observed_sum(counts.get("output_tokens") for counts in usage),
    }


def trace_summary(trace: list[dict]) -> dict:
    """Native completion and observed accounting, with unknown values left unknown."""
    done = trace_result(trace)
    ended = [r for r in trace if r.get("type") == "result"]
    cost = done.get("total_cost_usd")
    return {
        "completed": completed(trace),
        "turns": sum(r.get("num_turns", 0) for r in ended),
        "cost_usd": round(cost, 3) if cost is not None else None,
        "minutes": round(sum(r["duration_ms"] for r in ended) / 60000, 1)
        if ended and all("duration_ms" in r for r in ended)
        else None,
        **token_counts(trace),
        "reply": done.get("result") or "",
    }


def resumed(summaries: list[dict]) -> list[dict]:
    """The summaries of one session's successive phases, each costing only its own work.

    Claude Code's `total_cost_usd` covers the whole session, so a phase resumed with
    `--resume` reports its predecessors' cost too; its own is the difference. A Codex
    turn reports no cost, which stays unknown."""
    before = 0
    phases = []
    for summary in summaries:
        cost = summary["cost_usd"]
        phases.append(
            {**summary, "cost_usd": None if cost is None else round(cost - before, 3)}
        )
        before = cost if cost is not None else before
    return phases


def progress_start(events: list[dict], for_event: str) -> dict | None:
    """The admitted start on this exact input before its first successful answer.

    Score the page log, independent of command spelling, stdout and when the
    native stream was read. A later log reading cannot invent or reorder work.
    """
    final = next(iter(successful_replies(events, for_event)), None)
    return next(
        (
            start
            for event in events
            if (start := start_reading(event)) is not None
            and start["item"] == for_event
            and (final is None or start["seq"] < final["seq"])
        ),
        None,
    )
