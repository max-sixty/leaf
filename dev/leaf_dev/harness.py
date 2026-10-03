"""Arms, served pages, and isolated CC and Codex sessions for the commands and eval
harnesses that run a version of Leaf.

An arm is the plugin payload (`PAYLOAD`) at one ref, or as the working tree has it, and
nothing else: no `.git`, examples or notes, so a child cannot read its way to another
arm's version. An A/B's base is the merge base with the local `main` unless the caller
names another ref (`base_ref`).

A child runs from a scratch cwd outside any repository, so no project instructions
load, under a home of its own beside that cwd, so its bypassed permissions write to
that home rather than the user's `~` (children given the user's home once appended to
the user's `~/.claude/CLAUDE.md`). The home carries only the login. A trace is the
child's normalized tool/turn evidence; it counts when its actual host turn
completed without error (`completed`). Codex raw notifications are retained too.
A `LiveChild` keeps its session open across turns, so a driver can post
user moves to a served page (`PageClient`) as a tab would.
"""

import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Self

import click
from leaf.host import IDENTITY_VARIABLES

from leaf_dev import ROOT
from leaf_dev.page_fixtures import prepare_page, read_fixture

# The uv project names this package's `pyproject.toml` as a workspace member, so uv
# needs that file to read the lock. The package itself stays out: the launcher never
# installs the dev group. A ref from before the package has no such file.
PAYLOAD = (
    ".agents/plugins",
    ".claude-plugin",
    ".codex-plugin",
    "bin",
    "hooks",
    "skills",
    "pyproject.toml",
    "uv.lock",
    "dev/pyproject.toml",
    "worker/pyproject.toml",
)


def environment(**extra: str) -> dict[str, str]:
    """This process's environment without the agent session it may be running in.

    A harness run from a Claude Code or Codex session inherits that session's
    identity: its id, job directory and effort level. A `leaf` command would sign
    events as that session, and a child would take its settings. `CLAUDE_CONFIG_DIR`
    stays, since it names where the login lives."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in IDENTITY_VARIABLES
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
    )
    try:
        yield re.search(r"https?://[^\s\"]+", server.stdout.readline())[0]
    finally:
        server.terminate()
        server.wait(10)


def build_source(arm: Path, state: Path, source: Path, page: Path) -> None:
    """Build the authored `source` into the page directory `page` with the arm's own
    launcher under the state home `state`. The checkout is an arm too: `ROOT` runs
    its working tree."""
    prepare_page(page, read_fixture(source), partial(run_leaf, arm, state, check=True))


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


def extract_payload(dest: Path, ref: str | None = None) -> None:
    """Write PAYLOAD at git `ref`, or as the working tree has it when `ref` is None
    (`copy_working`), into `dest`, replacing whatever was there."""
    if dest.exists():
        # A caller may have made an arm read-only.
        subprocess.run(["chmod", "-R", "u+w", dest], check=True)
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if ref is not None:
        # An older ref lacks some of PAYLOAD, which `git archive` would refuse.
        present = subprocess.run(
            ["git", "-C", ROOT, "ls-tree", "--name-only", ref, *PAYLOAD],
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
    else:
        copy_working(PAYLOAD, dest)


def build_arm(ref: str | None, dest: Path) -> str:
    """Extract PAYLOAD at `ref`, or as the working tree has it when `ref` is None,
    into `dest`, replacing any earlier arm there, and build its environment; return
    the commit, HEAD's for the working tree."""
    extract_payload(dest, ref)
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


def scratch() -> Path:
    """A fresh directory for a child's cwd, outside any repository."""
    return Path(tempfile.mkdtemp(prefix="leaf-eval-"))


def claude_child(
    cwd: Path, *args: str, dirs: Iterable[Path] = (), env: dict | None = None
) -> dict:
    """The `subprocess` arguments for one isolated `claude -p` child in `cwd`.

    `args` follow `-p`, so a prompt goes first. `dirs` are what the child may read
    beyond `cwd`, and `env` adds to `environment()`. Output is verbose stream-json."""
    (cwd / "tmp").mkdir(exist_ok=True)
    # The home may hold a copy of the user's login, so no one else may enter it.
    home = cwd.with_name(f"{cwd.name}-home")
    home.mkdir(mode=0o700, exist_ok=True)
    home.chmod(0o700)
    keychains = Path.home() / "Library/Keychains"
    if keychains.is_dir() and not (home / "Library/Keychains").is_symlink():
        (home / "Library").mkdir(parents=True, exist_ok=True)
        (home / "Library/Keychains").symlink_to(keychains)
    credentials = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        / ".credentials.json"
    )
    if credentials.is_file():
        (home / ".claude").mkdir(parents=True, exist_ok=True)
        shutil.copy(credentials, home / ".claude/.credentials.json")
    command = [
        "claude", "-p", *args, "--strict-mcp-config",
        "--permission-mode", "bypassPermissions", "--output-format", "stream-json",
        "--verbose", *(arg for d in dirs for arg in ("--add-dir", str(d))),
    ]  # fmt: skip
    child_env = environment(
        HOME=str(home),
        UV_CACHE_DIR=os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache/uv")),
        CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
        TMPDIR=str(cwd / "tmp"),
        **(env or {}),
    )
    child_env.pop("CLAUDE_CONFIG_DIR", None)
    return {"args": command, "cwd": cwd, "env": child_env}


TURN_LIMIT = 1200


def run_agent(
    cwd: Path,
    *args: str,
    out: Path,
    err: Path,
    dirs: Iterable[Path] = (),
    env: dict | None = None,
    host: str = "cc",
) -> list[dict]:
    """Run an isolated host turn, optionally resuming its preceding session.

    `out` is normalized evidence; `err` is stderr. Codex's complete App Server
    notifications live beside `err` with a `.codex.jsonl` suffix. Both hosts
    have the same TURN_LIMIT; a timeout retains their partial native evidence and
    marks `out.with_suffix(".timed-out")` without fabricating completion.
    """
    if host == "codex":
        with (
            LiveChild(
                cwd,
                args[0],
                *args[1:],
                host=host,
                stderr=err,
                limit=TURN_LIMIT,
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
    if host != "cc":
        raise ValueError(f"unknown eval host: {host}")
    with out.open("w") as stdout, err.open("w") as stderr:
        try:
            subprocess.run(
                **claude_child(cwd, *args, dirs=dirs, env=env),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=False,
                timeout=TURN_LIMIT,
            )
        except subprocess.TimeoutExpired:
            out.with_suffix(".timed-out").touch()
    return read_trace(out)


class LiveChild:
    """An isolated host session kept open for delivery and later turns.

    `prompt` is its first message. `records` yields actual tool, hook and turn
    evidence stamped `received_at`; Codex retains its raw notifications too.

    `claude -p` terminates its background shells, such as a `leaf wait`, once stdin
    closes, so stdin stays open until the caller calls `close`. A session still
    running `limit` seconds after it started is killed and `timed_out` touched."""

    def __new__(cls, *args, host="cc", **kwargs):
        if host == "codex":
            from leaf_dev.eval_codex import CodexChild

            return CodexChild(*args, **kwargs)
        if host != "cc":
            raise ValueError(f"unknown eval host: {host}")
        return super().__new__(cls)

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
        host: str = "cc",
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

    def __enter__(self) -> Self:
        self.proc = subprocess.Popen(
            **self.popen,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr.open("w"),
            text=True,
        )
        message = {"type": "user", "message": {"role": "user", "content": self.prompt}}
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        self.deadline.start()
        return self

    def records(self):
        """Each stream record until the child exits."""
        for line in self.proc.stdout:
            yield {**json.loads(line), "received_at": now()}
        self.proc.wait(timeout=60)

    def close(self) -> None:
        """End the session once the turn in progress, if any, has ended."""
        if not self.proc.stdin.closed:
            self.proc.stdin.close()

    def _give_up(self) -> None:
        self.timed_out.touch()
        self.proc.kill()

    def __exit__(self, *exc) -> None:
        self.deadline.cancel()
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()


def now() -> str:
    """The time a live driver stamps on each record as `received_at`."""
    return datetime.now().astimezone().isoformat()


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

    def state(self) -> dict:
        with self.opener.open(f"{self.origin}/api/state?t={self.token}") as response:
            return json.loads(response.read())

    def post(self, event: dict) -> None:
        """Post one move as the page does: keyed, on the served layer. The caller
        names the revision and the retry key, as the browser does."""
        request = urllib.request.Request(
            f"{self.origin}/api/event?t={self.token}",
            data=json.dumps(event).encode(),
            headers={"Leaf-Layer": self.state()["layer"]["generation"]},
        )
        try:
            self.opener.open(request).close()
        except urllib.error.HTTPError as error:
            raise click.ClickException(
                f"posting {event}: HTTP {error.code} {error.read().decode()}"
            ) from error


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
    """Whether one stream record is a Leaf hook handing a delivery to the turn."""
    return record.get("subtype") == "hook_response" and "leaf-delivery-v" in (
        record.get("output") or ""
    )


def read_trace(stream: Path) -> list[dict]:
    return [json.loads(line) for line in stream.read_text().splitlines()]


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


def accepted_thread_claims(trace: list[dict], thread: str) -> dict[str, int]:
    """Bash call ids whose successful status result declares work on THREAD.

    Status writes one JSON line. Compound Bash output may contain other lines;
    only its canonical `work` subjects count, never an attempted command or a
    page-wide declaration. Values are the result's trace index.
    """
    calls = {
        block["id"]
        for block in blocks(trace)
        if block.get("type") == "tool_use"
        and block["name"] == "Bash"
        and re.search(
            r"\bstatus\b[^|;&]*\bworking\b", block["input"].get("command", "")
        )
    }
    accepted = {}
    for index, record in enumerate(trace):
        for block in blocks([record]):
            if (
                block.get("type") != "tool_result"
                or block.get("is_error") is not False
                or block["tool_use_id"] not in calls
            ):
                continue
            content = block["content"]
            text = (
                content
                if isinstance(content, str)
                else "\n".join(
                    part["text"] for part in content if part.get("type") == "text"
                )
            )
            for line in text.splitlines():
                try:
                    status = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(status, dict)
                    and status.get("state") == "working"
                    and any(
                        work["subject"] == {"kind": "thread", "id": thread}
                        for work in status.get("work", [])
                    )
                ):
                    accepted[block["tool_use_id"]] = index
    return accepted
