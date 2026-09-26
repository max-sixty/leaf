#!/usr/bin/env python3
"""Compare how promptly a Claude Code agent picks up a Leaf comment, base vs HEAD.

This is a basic, imperfect eval: a starting point that needs work before its numbers
support more than "no obvious regression". Each round launches one headless Claude
Code session per arm and case at the same time, with the plugin from BASE_REF or
from HEAD, so commit what you want measured. Each arm and child is built by
`eval_harness.py`. Each session serves the same page (this checkout's
`examples/triage-board.html`) and starts its background `leaf wait`. The script then
posts real comments over HTTP, at the moments a case names:

- `idle`: after the setup turn ends, so the comment reaches an idle session the way
  it does when a user reads the page before commenting, and it arrives through
  Claude Code's background-task notification; then a second comment once the turn
  that handled the first has ended, which only arrives if the ack re-armed the wait.
- `mid-turn`: as soon as the setup turn's wait is running, so the wait ends while
  the turn is still going and the Stop hook or the notification carries the comment
  into that same turn.

For each comment it reads the page log and the session's stream for:

- seconds from the comment to its `pickup` (the user sees Picked up) and to the
  first agent reply;
- `ack`: seconds from the delivery reaching the agent to that pickup, which is the
  agent's own share of the pickup time;
- `extra`: anything the agent ran between the delivery and `leaf wait --ack` other
  than reading the delivery, which should be nothing;
- any acknowledgement command the agent invented rather than `leaf wait --ack`.

`claude -p` terminates a background shell once the final result is out and stdin has
closed, so each session runs with `--input-format stream-json` and stdin held open
until every comment it was sent has been acked and a turn has ended. Each stream
record is saved with `received_at`, the time the script read it, and each post as an
`eval_comment` record.

Known limits:

- Two rounds, one page, fixed comments. There are no statistics: read the table,
  not the means. A reading within about 3 s of the other arm's is noise.
- The prompt is synthetic and the session is fresh, so the agent reads the skill in
  the same turn it serves the page. A long session with competing context is not
  measured.
- The model is Claude Code's default.
- Timings include model latency and machine load. Launching every session together
  controls load only roughly. The page log stamps whole seconds.
- Scoring matches substrings in shell commands.
- Only the `leaf wait` carrier is covered. `verify_site.py local` covers App Server;
  nothing covers the Codex queue.

It needs a logged-in `claude` on PATH. Each session costs about a dollar. Runs
are written to `.tmp/eval-claude-delivery/<arm>-<case>-<round>/`, with `work-dir`
naming the child's cwd, which holds the page; `arms.json` records each arm's commit.
"""

import http.cookiejar
import json
import re
import shutil
import subprocess
import tempfile
import threading
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
ROUNDS = 2
TURN_LIMIT = 600
PROMPT = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)
# When each of a case's comments is posted: `idle` at the end of a turn, `running`
# once the setup turn's background wait has started.
CASES = {"idle": ("idle", "idle"), "mid-turn": ("running",)}
COMMENTS = (
    {
        "text": "Cut this paragraph to two sentences; the second one repeats the first.",
        "anchor": {"section": "triage-lede"},
    },
    {
        "text": "Rename this heading to ‘Why the migration blocks alone’.",
        "anchor": {"section": "triage-why"},
    },
)
URL = re.compile(r"https?://[^\s\"\\]+\?t=[A-Za-z0-9_-]+")


def attempt(n: int) -> str:
    return f"eval-claude-delivery-{n}"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def post_comment(url: str, n: int) -> None:
    """Post comment `n` the way the page does: keyed, on the served layer and revision."""
    parts = urllib.parse.urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    token = urllib.parse.parse_qs(parts.query)["t"][0]
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    with opener.open(f"{origin}/api/state?t={token}") as response:
        state = json.loads(response.read())
    comment = {
        "kind": "comment",
        "revision": state["active"]["revision"],
        "attempt": attempt(n),
        **COMMENTS[n - 1],
    }
    request = urllib.request.Request(
        f"{origin}/api/event?t={token}",
        data=json.dumps(comment).encode(),
        headers={"Leaf-Layer": state["layer"]["generation"]},
    )
    opener.open(request).close()


def waits_started(record: dict) -> list[str]:
    """Return the ids of the backgrounded `leaf wait` calls one stream record makes."""
    content = (record.get("message") or {}).get("content")
    return [
        block["id"]
        for block in (content if isinstance(content, list) else ())
        if block.get("type") == "tool_use"
        and block["name"] == "Bash"
        and "leaf wait" in block["input"].get("command", "")
        and block["input"].get("run_in_background")
    ]


def commands(record: dict) -> list[str]:
    """Return what each tool call in one stream record runs, or the tool and its file."""
    content = (record.get("message") or {}).get("content")
    return [
        block["input"].get("command")
        or " ".join(filter(None, [block["name"], block["input"].get("file_path")]))
        for block in (content if isinstance(content, list) else ())
        if block.get("type") == "tool_use"
    ]


def stop_blocked(record: dict) -> bool:
    """Whether one stream record is the Stop hook holding a turn open."""
    return (
        record.get("subtype") == "hook_response"
        and record["hook_event"] == "Stop"
        and bool(record["output"])
        and json.loads(record["output"]).get("decision") == "block"
    )


def run_session(arm: Path, case: str, run: Path) -> None:
    """One Claude Code session: serve, wait, receive the case's comments, handle them."""
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
            "--include-hook-events",
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
        url, waits, due, posted, acks = None, set(), list(CASES[case]), 0, 0
        with (run / "stream.jsonl").open("w") as stream:

            def post() -> None:
                nonlocal posted
                posted += 1
                post_comment(url, posted)
                marker = {"type": "eval_comment", "n": posted, "received_at": now()}
                stream.write(json.dumps(marker) + "\n")
                due.pop(0)

            for line in proc.stdout:
                record = {**json.loads(line), "received_at": now()}
                stream.write(json.dumps(record) + "\n")
                waits.update(waits_started(record))
                acks += sum("leaf wait --ack" in c for c in commands(record))
                content = (record.get("message") or {}).get("content")
                for block in content if isinstance(content, list) else ():
                    if block.get("type") != "tool_result":
                        continue
                    if not url and (
                        found := URL.search(json.dumps(block.get("content")))
                    ):
                        url = found.group(0)
                    if due[:1] == ["running"] and url and block["tool_use_id"] in waits:
                        # The wait is running and the setup turn is not over.
                        post()
                if record.get("type") != "result":
                    continue
                if due[:1] == ["idle"] and url and waits:
                    # A turn is over and the session idles on its wait.
                    post()
                elif not due and acks >= posted:
                    # Every comment is picked up. A trailing wake may follow,
                    # hence the grace period.
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


def score(run: Path) -> list[dict]:
    """Read one run's page log and stream into one reading per comment it was sent."""
    events = [
        json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()
    ]
    stream = [
        json.loads(line) for line in (run / "stream.jsonl").read_text().splitlines()
    ]
    waits = {wait for r in stream for wait in waits_started(r)}
    outputs = {
        r["output_file"]
        for r in stream
        if r.get("subtype") == "task_notification" and r["tool_use_id"] in waits
    }
    readings = []
    for marker in (r for r in stream if r["type"] == "eval_comment"):
        comment = next(e for e in events if e.get("attempt") == attempt(marker["n"]))
        posted_at = datetime.fromisoformat(comment["ts"])
        pickup = next(
            (
                datetime.fromisoformat(e["ts"])
                for e in events
                if e["kind"] == "pickup"
                and e["phase"] == "opened"
                and comment["id"] in e["events"]
            ),
            None,
        )
        reply = next(
            (
                datetime.fromisoformat(e["ts"])
                for e in events
                if e["kind"] == "reply" and e.get("parent") == comment["id"]
            ),
            None,
        )
        # What followed the post up to the ack: what carried the comment in, and
        # what the agent ran once it had.
        notified, blocked, before_ack = None, None, []
        for record in stream[stream.index(marker) + 1 :]:
            ran = commands(record)
            if any("leaf wait --ack" in c for c in ran):
                break
            if (
                record.get("subtype") == "task_notification"
                and record["tool_use_id"] in waits
            ):
                notified = notified or record
            elif stop_blocked(record) and not blocked:
                # The Stop hook blocks only a turn ending with the comment unread,
                # so when it fires, it and not the notification carried it in.
                blocked, before_ack = record, []
            elif notified or blocked:
                before_ack += ran
        delivery = blocked or notified
        readings.append(
            {
                "comment": marker["n"],
                "route": "stop hook"
                if blocked
                else "notification"
                if notified
                else None,
                "pickup_s": pickup and round((pickup - posted_at).total_seconds()),
                "reply_s": reply and round((reply - posted_at).total_seconds()),
                "ack_s": pickup
                and delivery
                and round(
                    (
                        pickup - datetime.fromisoformat(delivery["received_at"])
                    ).total_seconds()
                ),
                # Reading the wait's output is the one expected step.
                "extra_before_ack": [
                    c for c in before_ack if not any(o in c for o in outputs)
                ]
                if delivery
                else None,
            }
        )
    ran = [c for r in stream for c in commands(r)]
    return [
        {
            **reading,
            "timed_out": (run / "timed-out").exists(),
            "invented_ack": [
                a for a in ran if re.search(r"\back\b", a) and "wait --ack" not in a
            ],
        }
        for reading in readings
    ] or [{"comment": None, "timed_out": (run / "timed-out").exists()}]


@click.command()
@click.argument("base_ref", default="main")
def main(base_ref: str) -> None:
    """Run ROUNDS rounds of every case: BASE_REF's plugin against HEAD's."""
    refs = {"base": base_ref, "head": "HEAD"}
    runs = [
        (arm, case, i) for i in range(1, ROUNDS + 1) for case in CASES for arm in refs
    ]
    with tempfile.TemporaryDirectory() as built:
        arms = {arm: Path(built) / arm for arm in refs}
        commits = {arm: build_arm(ref, arms[arm]) for arm, ref in refs.items()}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "arms.json").write_text(json.dumps(commits, indent=1))
        for i in range(1, ROUNDS + 1):
            with ThreadPoolExecutor(len(arms) * len(CASES)) as pool:
                for future in [
                    pool.submit(run_session, arms[arm], case, OUT / f"{arm}-{case}-{i}")
                    for arm, case, j in runs
                    if j == i
                ]:
                    future.result()
    results = {
        f"{arm}-{case}-{i}": score(OUT / f"{arm}-{case}-{i}")
        for arm, case, i in sorted(runs)
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    for name, readings in results.items():
        for r in readings:
            if r["comment"] is None:
                print(
                    f"{name:18}    {'TIMED OUT' if r['timed_out'] else 'posted nothing'}"
                )
                continue
            print(
                f"{name:18} #{r['comment']} {'TIMED OUT  ' if r['timed_out'] else ''}"
                f"pickup {r['pickup_s']}s  reply {r['reply_s']}s  "
                f"ack {r['ack_s']}s after {r['route'] or 'no delivery'}  "
                f"extra {r['extra_before_ack'] or 'none'}  "
                f"invented {r['invented_ack'] or 'none'}"
            )
    print(f"details: {OUT}/results.json")


if __name__ == "__main__":
    main()
