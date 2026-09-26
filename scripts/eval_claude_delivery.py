#!/usr/bin/env python3
"""Compare how promptly a Claude Code agent picks up a Leaf comment, base vs HEAD.

This is a basic, imperfect eval: a starting point that needs work before its numbers
support more than "no obvious regression". Each round launches two headless Claude
Code sessions at the same time, one with the plugin from BASE_REF and one with the
plugin from HEAD, so commit what you want measured. Each arm and child is built by
`eval_harness.py`. Each serves the same page (this checkout's
`examples/triage-board.html`), starts its background `leaf wait`, and receives one
real comment posted over HTTP. The script then reads the page log and the session's
stream for:

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
- The model is Claude Code's default.
- Timings include model latency and machine load. Launching both arms together
  controls load only roughly.
- Scoring matches substrings in shell commands.
- Only the `leaf wait` carrier is covered. `verify_site.py local` covers App Server;
  nothing covers the Codex queue.

It needs a logged-in `claude` on PATH. Each session costs about half a dollar. Runs
are written to `.tmp/eval-claude-delivery/<arm>-<round>/`, with `work-dir` naming the
child's cwd, which holds the page; `arms.json` records each arm's commit.
"""

import http.cookiejar
import json
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
from functools import partial
from pathlib import Path

import click
from eval_harness import build_arm, claude_child, run_leaf, scratch

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


def run_session(arm: Path, run: Path) -> None:
    """One Claude Code session: serve, wait, receive the comment, handle it."""
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    work = scratch()
    (run / "work-dir").write_text(f"{work}\n")
    page = work / "page"
    state = run / "state"
    leaf = partial(run_leaf, arm, state)
    leaf("page", "init", str(page), check=True)
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    leaf(
        "version",
        "stamp",
        str(page),
        "--text",
        "Release triage for review.",
        check=True,
    )
    proc = subprocess.Popen(
        **claude_child(
            work,
            "--input-format",
            "stream-json",
            "--plugin-dir",
            str(arm),
            dirs=[arm, state],
            env={"XDG_STATE_HOME": str(state)},
        ),
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

    def give_up() -> None:
        (run / "timed-out").touch()
        proc.kill()

    # The deadline runs beside the read, so a stream that stops producing lines
    # still ends: the kill closes stdout and the loop below finishes.
    deadline = threading.Timer(TURN_LIMIT, give_up)
    deadline.start()
    try:
        url = None
        waits, posted, arrived, results = set(), False, False, 0
        with (run / "stream.jsonl").open("w") as stream:
            for line in proc.stdout:
                stream.write(line)
                record = json.loads(line)
                if record.get("subtype") == "task_notification":
                    arrived = arrived or (posted and record["tool_use_id"] in waits)
                content = (record.get("message") or {}).get("content")
                for block in content if isinstance(content, list) else ():
                    if block.get("type") == "tool_use" and block["name"] == "Bash":
                        command = block["input"].get("command", "")
                        if "leaf wait" in command and block["input"].get(
                            "run_in_background"
                        ):
                            waits.add(block["id"])
                    elif block.get("type") == "tool_result" and not url:
                        if found := URL.search(json.dumps(block.get("content"))):
                            url = found.group(0)
                if url and waits and not posted:
                    posted = True
                    time.sleep(5)
                    post_comment(url)
                if record.get("type") == "result":
                    results += 1
                    # The first result ends the setup turn, even when the delivery landed
                    # before it did; a later one after the delivery ends a turn it woke.
                    # A trailing wake may follow, hence the grace period.
                    if results > 1 and arrived:
                        threading.Timer(20, close_stdin).start()
        proc.wait(timeout=60)
        (run / "events.jsonl").write_text(leaf("events", str(page), check=True).stdout)
    finally:
        # A failed arm ends as promptly as a stalled one: no timer or child outlives it.
        deadline.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        # The server may already have stopped with its session.
        leaf("server", "stop", str(page))


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
        "timed_out": (run / "timed-out").exists(),
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
    """Run ROUNDS paired sessions: BASE_REF's plugin against HEAD's."""
    refs = {"base": base_ref, "head": "HEAD"}
    with tempfile.TemporaryDirectory() as built:
        arms = {arm: Path(built) / arm for arm in refs}
        commits = {arm: build_arm(ref, arms[arm]) for arm, ref in refs.items()}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "arms.json").write_text(json.dumps(commits, indent=1))
        for i in range(1, ROUNDS + 1):
            with ThreadPoolExecutor(len(arms)) as pool:
                for future in [
                    pool.submit(run_session, path, OUT / f"{arm}-{i}")
                    for arm, path in arms.items()
                ]:
                    future.result()
    results = {
        f"{arm}-{i}": score(OUT / f"{arm}-{i}")
        for arm in arms
        for i in range(1, ROUNDS + 1)
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    for name, r in results.items():
        before = r["actions_before_ack"]
        print(
            f"{name:12} {'TIMED OUT  ' if r['timed_out'] else ''}pickup {r['pickup_s']}s  reply {r['reply_s']}s  "
            f"actions before ack {'never acked' if before is None else len(before)}  "
            f"invented {r['invented_ack'] or 'none'}"
        )
    print(f"details: {OUT}/results.json")


if __name__ == "__main__":
    main()
