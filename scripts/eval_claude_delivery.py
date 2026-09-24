#!/usr/bin/env python3
"""Compare how promptly a Claude Code agent picks up a Leaf comment, base vs checkout.

This is a basic, imperfect eval: a starting point that needs work before its numbers
support more than "no obvious regression". Each round launches two headless Claude
Code sessions at the same time, one with the plugin from BASE_REF and one with this
checkout. Each serves the same page (`examples/triage-board.html`), starts its
background `leaf wait`, and receives one real comment posted over HTTP. The script
then reads the page log and the session's stream for:

- seconds from the comment to its `pickup` (the user sees Picked up) and to the
  first agent reply;
- the agent's actions between the wait's completion notice and its
  `leaf wait --ack`; reading the wait's output file is the one expected;
- any acknowledgement command the agent invented rather than `leaf wait --ack`.

`claude -p` terminates a background shell once the final result is out and stdin has
closed, so each session runs with `--input-format stream-json` and stdin held open
until the turn that handled the comment ends. The comment then arrives through
Claude Code's own background-task notification, as it does in an interactive
session.

Known limits:

- Four rounds, one page, one comment shape. There are no statistics: read the table,
  not the means.
- The prompt is synthetic and the session is fresh, so the agent reads the skill in
  the same turn it serves the page. A long session with competing context is not
  measured.
- `--setting-sources project` keeps the user's own CLAUDE.md and plugins out, so the
  model sees only Leaf's guidance. The model is Claude Code's default.
- Timings include model latency and machine load. Launching both arms together
  controls load only roughly.
- Scoring matches substrings in shell commands.
- Only the `leaf wait` carrier is covered. `verify_site.py local` covers App Server;
  nothing covers the Codex queue.

It needs a logged-in `claude` on PATH. Each session costs about half a dollar. Runs
are written to `.tmp/eval-claude-delivery/<arm>-<round>/`.
"""

import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tmp" / "eval-claude-delivery"
ROUNDS = 4
TURN_LIMIT = 600
PROMPT = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)
COMMENT = {
    "kind": "comment",
    "revision": 1,
    "attempt": "eval-claude-delivery-1",
    "text": "Cut this paragraph to two sentences; the second one repeats the first.",
    "anchor": {"section": "triage-lede"},
}
URL = re.compile(r"https?://[^\s\"\\]+\?t=[A-Za-z0-9_-]+")


def post_comment(url: str) -> None:
    """Post COMMENT the way the page does: keyed, with the served layer."""
    parts = urllib.parse.urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    token = urllib.parse.parse_qs(parts.query)["t"][0]
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    with opener.open(f"{origin}/api/state?t={token}") as response:
        layer = json.loads(response.read())["layer"]["generation"]
    request = urllib.request.Request(
        f"{origin}/api/event?t={token}",
        data=json.dumps(COMMENT).encode(),
        headers={"Leaf-Layer": layer},
    )
    opener.open(request).close()


def run_session(leaf_root: Path, run: Path) -> None:
    """One Claude Code session: serve, wait, receive the comment, handle it."""
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    page = run / "page"
    leaf = str(leaf_root / "bin" / "leaf")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["XDG_STATE_HOME"] = str(run / "state")
    subprocess.run(
        [leaf, "page", "init", page], env=env, check=True, capture_output=True
    )
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    subprocess.run(
        [leaf, "version", "stamp", page, "--text", "Release triage for review."],
        env=env,
        check=True,
        capture_output=True,
    )
    proc = subprocess.Popen(
        [
            "claude",
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--setting-sources",
            "project",
            "--permission-mode",
            "bypassPermissions",
            "--plugin-dir",
            str(leaf_root),
        ],
        cwd=run,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=(run / "stderr.txt").open("w"),
        text=True,
    )
    message = {"type": "user", "message": {"role": "user", "content": PROMPT}}
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()

    def close_stdin() -> None:
        if not proc.stdin.closed:
            proc.stdin.close()

    url = None
    waiting = posted = False
    started = time.time()
    with (run / "stream.jsonl").open("w") as stream:
        for line in proc.stdout:
            stream.write(line)
            record = json.loads(line)
            content = (record.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else ():
                if block.get("type") == "tool_use" and block["name"] == "Bash":
                    command = block["input"].get("command", "")
                    if "leaf wait" in command and block["input"].get(
                        "run_in_background"
                    ):
                        waiting = True
                elif block.get("type") == "tool_result" and not url:
                    if found := URL.search(json.dumps(block.get("content"))):
                        url = found.group(0)
            if url and waiting and not posted:
                posted = True
                time.sleep(5)
                post_comment(url)
            if record.get("type") == "result" and posted:
                # The turn that handled the comment has ended; a trailing wake may follow.
                threading.Timer(20, close_stdin).start()
            if time.time() - started > TURN_LIMIT:
                close_stdin()
                break
    proc.wait(timeout=60)
    events = subprocess.run(
        [leaf, "events", page], env=env, check=True, capture_output=True, text=True
    ).stdout
    (run / "events.jsonl").write_text(events)
    # The server may already have stopped with its session.
    subprocess.run(
        [leaf, "server", "stop", page], env=env, check=False, capture_output=True
    )


def score(run: Path) -> dict:
    """Read one run's page log and stream into the compared readings."""
    events = [
        json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()
    ]
    at = {}
    for event in events:
        at.setdefault(event["kind"], datetime.fromisoformat(event["ts"]))
    comment = at.get("comment")

    def since_comment(kind: str) -> float | None:
        return (
            round((at[kind] - comment).total_seconds())
            if kind in at and comment
            else None
        )

    actions, waits, arrived = [], set(), False
    for line in (run / "stream.jsonl").read_text().splitlines():
        record = json.loads(line)
        if record.get("subtype") == "task_notification":
            arrived = arrived or record["tool_use_id"] in waits
        content = (record.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else ():
            if block.get("type") != "tool_use":
                continue
            command = block["input"].get("command", "")
            if "leaf wait" in command and block["input"].get("run_in_background"):
                waits.add(block["id"])
            if arrived:
                actions.append(command or block["name"])
    ack = next((i for i, a in enumerate(actions) if "leaf wait --ack" in a), None)
    return {
        "pickup_s": since_comment("pickup"),
        "reply_s": since_comment("reply"),
        "actions_before_ack": actions[:ack] if ack is not None else None,
        "invented_ack": [
            a for a in actions if re.search(r"\back\b", a) and "wait --ack" not in a
        ],
    }


@click.command()
@click.argument("base_ref", default="main")
def main(base_ref: str) -> None:
    """Run ROUNDS paired sessions: BASE_REF's plugin against this checkout's."""
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch) / "base"
        subprocess.run(
            ["git", "-C", ROOT, "worktree", "add", "--detach", base, base_ref],
            check=True,
            capture_output=True,
        )
        try:
            subprocess.run(
                [base / "bin" / "leaf", "--root"], check=True, capture_output=True
            )
            arms = {"base": base, "checkout": ROOT}
            for i in range(1, ROUNDS + 1):
                with ThreadPoolExecutor(len(arms)) as pool:
                    for future in [
                        pool.submit(run_session, root, OUT / f"{arm}-{i}")
                        for arm, root in arms.items()
                    ]:
                        future.result()
        finally:
            subprocess.run(
                ["git", "-C", ROOT, "worktree", "remove", "--force", base], check=True
            )
    results = {
        f"{arm}-{i}": score(OUT / f"{arm}-{i}")
        for arm in arms
        for i in range(1, ROUNDS + 1)
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    for name, r in results.items():
        before = r["actions_before_ack"]
        print(
            f"{name:12} pickup {r['pickup_s']}s  reply {r['reply_s']}s  "
            f"actions before ack {'never acked' if before is None else len(before)}  "
            f"invented {r['invented_ack'] or 'none'}"
        )
    print(f"details: {OUT}/results.json")


if __name__ == "__main__":
    main()
