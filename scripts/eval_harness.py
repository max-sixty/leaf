"""Arms and children for evals that run Claude Code against a version of Leaf.

    uv run scripts/eval_harness.py REF DEST

builds one arm at DEST from git REF. `eval_claude_delivery.py` and
`notes/arrangement-eval/harness.py` import the rest, and `evals/README.md`'s A/B
recipe builds its other arm with the command.

An arm is the plugin payload at one ref (`PAYLOAD`: the manifest, hooks, launcher,
skills and uv project) and nothing else. It has no `.git`, examples, docs or notes, so a
child cannot read its way to another arm's version through history or the worked
corpus. Building runs the launcher once, so uv builds the arm's environment before a
timed run starts.

A child is `claude -p` from a scratch cwd outside any repository, with project-only
settings, no MCP servers, auto-memory off, and none of the variables that identify an
agent session running the harness (`environment`). Claude Code loads every `CLAUDE.md` above its cwd, and under `$HOME` that
includes `~/.claude/CLAUDE.md` as a project file, so a child whose cwd sat in this
checkout read the user's instructions and this checkout's `CLAUDE.md` whatever arm it
ran. With auto-memory on it also read the repository's memory, and saved to it.
`--add-dir` grants reads without loading a directory's `CLAUDE.md`.
The child's `TMPDIR` is inside its cwd, because concurrent children otherwise write the
same `/tmp` names and can read each other's.
"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

import click
from leaf.host import SESSION_VARIABLES

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
        if key not in SESSION_VARIABLES
        and not (key.startswith("CLAUDE") and key != "CLAUDE_CONFIG_DIR")
    }
    return {**env, **extra}


def run_leaf(
    arm: Path,
    state: Path,
    *args: str,
    check: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run an arm's launcher under a state home of its own."""
    proc = subprocess.run(
        [str(arm / "bin/leaf"), *args],
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


@click.command()
@click.argument("ref")
@click.argument("dest", type=click.Path(path_type=Path))
def main(ref: str, dest: Path) -> None:
    """Build an arm at DEST from git REF."""
    click.echo(f"{dest}: {build_arm(ref, dest.resolve())}")


if __name__ == "__main__":
    main()
