"""Arms, served pages, and agent-host children for evals and probes that run a
version of Leaf.

    uv run leaf-dev arm REF DEST

builds one arm at DEST from git REF; `evals/README.md`'s A/B recipe builds its other
arm with it. `leaf-dev stills` and `leaf-dev probe`, `eval_claude_delivery.py`, the
two `bench_*.py` scripts, `verify_codex_task.py`, `verify_site.py`,
`notes/arrangement-eval/harness.py` and `notes/usability-eval/harness.py` import the
rest.

An arm is the plugin payload at one ref (`PAYLOAD`: both hosts' manifests, hooks,
launcher, skills and uv project) and nothing else. It has no `.git`, examples, docs or
notes, so a child cannot read its way to another arm's version through history or the
worked corpus. Building runs the launcher once, so uv builds the arm's environment
before a timed run starts. `extract_payload` alone also copies the working tree's
payload, which a Codex home (`codex_home`) installs as its plugin.

A child is `claude -p` from a scratch cwd outside any repository, with project-only
settings, no MCP servers, auto-memory off, and none of the variables that identify an
agent session running the harness (`environment`). Claude Code loads project
instructions above its cwd, so a child whose cwd sat in this checkout read its
`AGENTS.md` whatever arm it ran. With auto-memory on it also read the repository's
memory, and saved to it. `--add-dir` grants reads without loading a directory's
project instructions.
The child's `TMPDIR` is inside its cwd, because concurrent children otherwise write the
same `/tmp` names and can read each other's.

A trace is the child's stream-json. It counts only when its model call completed: it
reached a `result` that is not an error, and it loaded no auto-memory (`completed`).

A live child (`LiveChild`) keeps its session open across turns, so a driver can serve
it a page and post user moves through the page's API (`PageClient`) as a tab would;
the stream readers below find its backgrounded waits and the deliveries Leaf's hooks
hand it.
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
    `state`, and yield the tokened `url` it prints; a first load of that address
    sets the page's cookie. An arm is any revision, and one from before the CLI
    printed JSON prints the bare URL, so the URL is found in the line either way."""
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


def merge_base() -> str:
    """The commit HEAD branched from `main`: the base an A/B script compares HEAD
    against unless it is handed another."""
    return subprocess.run(
        ["git", "-C", ROOT, "merge-base", "HEAD", "main"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def extract_payload(dest: Path, ref: str | None = None) -> None:
    """Write PAYLOAD at git `ref`, or as the working tree has it when `ref` is None,
    into `dest`, replacing whatever was there. The working tree's payload is its
    tracked and unignored files, the ones an install copies."""
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
        return
    listed = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z", "--cached", "--others"]
        + ["--exclude-standard", "--", *PAYLOAD],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for name in filter(None, listed.split("\0")):
        # A tracked file deleted from the working tree is still listed.
        if (ROOT / name).exists():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, dest / name)


def build_arm(ref: str, dest: Path) -> str:
    """Extract PAYLOAD at `ref` into `dest`, replacing any earlier arm there, and
    build its environment; return the commit."""
    extract_payload(dest, ref)
    with tempfile.TemporaryDirectory() as state:
        run_leaf(dest, Path(state), "--root", check=True)
    return subprocess.run(
        ["git", "-C", ROOT, "rev-parse", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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
    command = [
        "claude", "-p", *args, "--setting-sources", "project", "--strict-mcp-config",
        "--permission-mode", "bypassPermissions", "--output-format", "stream-json",
        "--verbose", *(arg for d in dirs for arg in ("--add-dir", str(d))),
    ]  # fmt: skip
    return {
        "args": command,
        "cwd": cwd,
        "env": environment(
            CLAUDE_CODE_DISABLE_AUTO_MEMORY="1", TMPDIR=str(cwd / "tmp"), **(env or {})
        ),
    }


def run_claude(
    cwd: Path,
    *args: str,
    out: Path,
    err: Path,
    dirs: Iterable[Path] = (),
    env: dict | None = None,
) -> list[dict]:
    """Run one `claude_child` to its end; return its trace.

    `out` receives the stream-json trace and `err` the child's stderr."""
    with out.open("w") as stdout, err.open("w") as stderr:
        subprocess.run(
            **claude_child(cwd, *args, dirs=dirs, env=env),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    return read_trace(out)


class LiveChild:
    """A `claude_child` whose session stays open for later turns, as a context
    manager: `prompt` is its first message, and `records` yields its stream-json,
    hook events included, each stamped `received_at`.

    A later turn opens when a background task, such as a `leaf wait`, ends. `claude
    -p` terminates its background shells once the final result is out and stdin has
    closed, so the caller holds stdin open while it expects another turn and calls
    `close` to end the session. A session still running `limit` seconds after it
    started is killed and `timed_out` touched; the deadline runs beside the read, so
    a stream that stops producing lines still ends. Leaving the block, however it is
    left, cancels the deadline and kills a child still running, so no timer or child
    outlives a failed driver."""

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


def tool_calls(record: dict) -> list[tuple[str, str]]:
    """Each tool call in one stream record: its id, and what it runs, or the tool
    and its file."""
    content = (record.get("message") or {}).get("content")
    return [
        (
            block["id"],
            block["input"].get("command")
            or " ".join(filter(None, [block["name"], block["input"].get("file_path")])),
        )
        for block in (content if isinstance(content, list) else ())
        if block.get("type") == "tool_use"
    ]


def commands(record: dict) -> list[str]:
    return [ran for _, ran in tool_calls(record)]


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


def loaded_memory(trace: list[dict]) -> bool:
    """Whether the child loaded auto-memory, which reads the user's notes and voids
    the run."""
    return any(d.get("type") == "system" and d.get("memory_paths") for d in trace)


def completed(trace: list[dict]) -> bool:
    """Whether a trace counts: its model call reached a result that is not an
    error, without auto-memory."""
    return trace_result(trace).get("is_error") is False and not loaded_memory(trace)
