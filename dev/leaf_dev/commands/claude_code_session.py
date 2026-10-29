"""A real Claude Code session in a tmux pane that loads this working tree as its
plugin and holds a served page, left running for a developer to look at what Leaf's
hooks module draws there, such as the band above the prompt.

    uv run leaf-dev claude-code-session [--stop]

The session runs as the `claude-code` journey's does (`journey_claude_code`), under a
throwaway home holding only the host's login and a state home of its own, but its
plugin is the working tree itself (`--plugin-dir`), not a copy, so an edit to
`hooks/claude-code.ts` reloads in the running session. Claude Code reloads a quiet
plugin folder on a poll, up to 30 s after the edit (measured at 2.1.306); the
session's debug log says `reloaded` when it has. The command asks the session to
serve the journey's page (`review_scenario.prepare`), waits until the session holds
it and its turn has ended, prints where everything is as JSON, and returns with the
session still running. `tmux capture-pane -p -e -t PANE` reads the screen with its
colors and links. Running it again replaces the previous session; `--stop` ends it.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from leaf.server import running_server
from leaf.service import page_claim
from leaf_dev import ROOT
from leaf_dev.arms import claude_environment, claude_home
from leaf_dev.commands.journey import Isolation, stop_left_running
from leaf_dev.journey_claude_code import ClaudeCode
from leaf_dev.review_scenario import REQUEST, prepare

# The model answers only setup and the developer's turns, so a fast one does.
MODEL = "claude-sonnet-5-5"
# Where the running session is recorded, for the next run and `--stop`.
RECORD = ROOT / ".tmp" / "claude-code-session.json"


def stop() -> None:
    """End the recorded session, what it left running, and its home."""
    if not RECORD.exists():
        return
    recorded = json.loads(RECORD.read_text())
    subprocess.run(["tmux", "kill-session", "-t", recorded["pane"]], check=False)
    stop_left_running(Path(recorded["state"]))
    shutil.rmtree(recorded["root"], ignore_errors=True)
    RECORD.unlink()


@click.command(name="claude-code-session")
@click.option("--stop", "stopping", is_flag=True, help="End the running session.")
def claude_code_session(stopping: bool) -> None:
    """Start a Claude Code session in tmux with this working tree as its live plugin,
    holding a served page, and print where it is."""
    stop()
    if stopping:
        return
    # Outside any repository, so the session loads no project instructions; Claude
    # Code records trust by the resolved path.
    root = Path(tempfile.mkdtemp(prefix="leaf-claude-code-session-")).resolve()
    place = Isolation(
        root, root / "state", root / "work", root / "work" / "page", ROOT, root,
    )  # fmt: skip
    place.work.mkdir()
    home = claude_home(root / "home")
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "hasCompletedOnboarding": True,
                "theme": "dark",
                "projects": {str(place.work): {"hasTrustDialogAccepted": True}},
            }
        )
    )
    env = claude_environment(
        home, XDG_STATE_HOME=str(place.state), TERM="tmux-256color"
    )
    # This process reads the session's claim and Claude Code's record of its turns.
    os.environ.clear()
    os.environ.update(env)
    prepare(ROOT, place.state, place.page)
    debug_log = root / "debug.log"
    argv = [
        "claude", "--model", MODEL,
        "--plugin-dir", str(ROOT), "--strict-mcp-config",
        "--permission-mode", "default", "--add-dir", str(ROOT),
        "--allowedTools", "Bash Read Write Edit Glob Grep Skill",
        "--debug-file", str(debug_log),
    ]  # fmt: skip
    cc = ClaudeCode(place, argv, env)
    RECORD.parent.mkdir(exist_ok=True)
    RECORD.write_text(
        json.dumps({"pane": cc.pane, "root": str(root), "state": str(place.state)})
    )
    cc.say(REQUEST)
    cc.until(lambda: page_claim(place.page) is not None, "the page was not claimed")
    claim = page_claim(place.page)
    assert claim is not None
    cc.session = claim["id"]
    cc.until(
        lambda: running_server(place.page) is not None and cc.idle(),
        "the page was not served with the session idle",
    )
    server = running_server(place.page)
    assert server is not None
    click.echo(
        json.dumps(
            {
                "pane": cc.pane,
                "attach": f"tmux attach -t {cc.pane}",
                "page": str(place.page),
                "url": server["url"],
                "state_home": str(place.state),
                "debug_log": str(debug_log),
            },
            indent=2,
        )
    )
