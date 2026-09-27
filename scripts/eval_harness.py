"""Arms and children for evals that run Claude Code against a version of Leaf.

    uv run scripts/eval_harness.py REF DEST

builds one arm at DEST from git REF. `eval_claude_delivery.py`,
`bench_render_check.py`, `bench_page_latency.py`,
`notes/arrangement-eval/harness.py` and `notes/usability-eval/harness.py` import the
rest, and `evals/README.md`'s A/B recipe builds its other arm with the command.

An arm is the plugin payload at one ref (`PAYLOAD`: the manifest, hooks, launcher,
skills and uv project) and nothing else. It has no `.git`, examples, docs or notes, so a
child cannot read its way to another arm's version through history or the worked
corpus. Building runs the launcher once, so uv builds the arm's environment before a
timed run starts.

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

A live child (`live_child`) keeps its session open across turns, so a driver can serve
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
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import click
from leaf.host import IDENTITY_VARIABLES

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = (".claude-plugin", "bin", "hooks", "skills", "pyproject.toml", "uv.lock")


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


def build_arm(ref: str, dest: Path) -> str:
    """Extract PAYLOAD at `ref` into `dest`, replacing any earlier arm there, and
    build its environment; return the commit."""
    if dest.exists():
        # A caller may have made an arm read-only.
        subprocess.run(["chmod", "-R", "u+w", dest], check=True)
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", ROOT, "archive", ref, *PAYLOAD], capture_output=True, check=True
    ).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=archive, check=True)
    with tempfile.TemporaryDirectory() as state:
        run_leaf(dest, Path(state), "--root", check=True)
    return subprocess.run(
        ["git", "-C", ROOT, "rev-parse", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


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


def live_child(
    cwd: Path,
    prompt: str,
    *args: str,
    stderr: Path,
    dirs: Iterable[Path] = (),
    env: dict | None = None,
) -> subprocess.Popen:
    """Start a `claude_child` whose session stays open for later turns, with `prompt`
    as its first message; its stream-json, hook events included, is on stdout.

    A later turn opens when a background task, such as a `leaf wait`, ends. `claude
    -p` terminates its background shells once the final result is out and stdin has
    closed, so the caller holds stdin open while it expects another turn and closes
    it to end the session."""
    proc = subprocess.Popen(
        **claude_child(
            cwd,
            "--input-format",
            "stream-json",
            "--include-hook-events",
            *args,
            dirs=dirs,
            env=env,
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr.open("w"),
        text=True,
    )
    message = {"type": "user", "message": {"role": "user", "content": prompt}}
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    return proc


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


@click.command()
@click.argument("ref")
@click.argument("dest", type=click.Path(path_type=Path))
def main(ref: str, dest: Path) -> None:
    """Build an arm at DEST from git REF."""
    click.echo(f"{dest}: {build_arm(ref, dest.resolve())}")


if __name__ == "__main__":
    main()
