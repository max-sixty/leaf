#!/usr/bin/env python3
"""Compare how a Claude Code agent handles a Leaf comment, base vs HEAD.

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
  that handled the first has ended, which only arrives if the agent restarted the
  wait.
- `mid-turn`: as soon as the setup turn's wait is running, so the wait ends while
  the turn is still going and the comment reaches that same turn, at a tool result or
  as the turn tries to end.

For each comment it reads the page log and the session's stream for:

- `woken`: seconds from the post to the delivery reaching the agent;
- seconds from the comment to its `pickup` (the user sees Picked up), to the first
  agent reply, which settles the comment's workflow, and to the last reply in its
  thread before the turn ends (`done`);
- `turn`: seconds from the post to the end of the turn that handled it, with the
  time from the delivery to that end split into time inside tool calls and the rest
  (`model`: model latency, hooks, and harness), and the slowest single call;
- `route`: what brought the comment in: the wait's notification, whose output the
  agent reads, or a hook that put the delivery in context (`prompt hook`, `stop
  hook`); a Stop hook that only said input was waiting counts as `stop hook` too;
- `receipt`: seconds from the delivery reaching the agent to that pickup, which is
  the agent's own share of the pickup time, none where a hook confirms it;
- `before claim`: what the agent ran after the delivery and before the message that
  claims its work (`leaf status … working`), which should be nothing: a read of the
  wait's output and `leaf wait --ack` show here where the protocol asks for them;
- any acknowledgement command the agent invented rather than `leaf wait --ack`.

It also samples what the page tells the user, as an open tab reads it: from the
served URL onward it reads `/api/state` every SAMPLE_EVERY seconds and saves each
change of the banner (`activity.kind` and its sentence) and of each workflow's
stage and condition (`working/stale`) to `states.jsonl`, keyed by its input, or by
`claim:` and its subject for a claim that grew from no input. For each comment, from
its post to LINGER seconds after its turn ends, it reports the values the comment's
workflow and the banner took and when; how long after the delivery the page first
showed the comment Picked up, and a work claim on the comment or its thread, beside
the budgets `notes/user-feedback-responsiveness.md` sets (1 s and 2 s); and two
disagreements with the stream:

- `quiet`: seconds between the delivery and the agent's last reply in that turn
  during which the banner did not say `working`, though the agent was;
- `late`: seconds after the turn ended during which the banner still said
  `working`.

`claude -p` terminates a background shell once the final result is out and stdin has
closed, so each session runs with `--input-format stream-json` and stdin held open
until every comment it was sent has been received and a turn has ended. Each stream
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
- Sampling reads what the page serves, not what a browser draws: a tab derives its
  labels from these values in `runtime/thread/workflow.js`. Each change is placed
  within SAMPLE_EVERY seconds, and each read counts as the page being viewed, as an
  open tab's does.
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
from collections.abc import Callable
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
SAMPLE_EVERY = 0.25
LINGER = 10
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


def moment(record: dict) -> float:
    return datetime.fromisoformat(record["received_at"]).timestamp()


class PageClient:
    """The served page's API, reached the way a tab reaches it: token and cookies."""

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

    def post_comment(self, n: int) -> None:
        """Post comment `n` as the page does: keyed, on the served layer and revision."""
        state = self.state()
        comment = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "attempt": attempt(n),
            **COMMENTS[n - 1],
        }
        request = urllib.request.Request(
            f"{self.origin}/api/event?t={self.token}",
            data=json.dumps(comment).encode(),
            headers={"Leaf-Layer": state["layer"]["generation"]},
        )
        self.opener.open(request).close()


def sample_page(url: str, path: Path, stop: threading.Event) -> None:
    """Save each change in what the page tells the user until `stop` is set."""
    page, last = PageClient(url), None
    with path.open("w") as out:
        while not stop.wait(SAMPLE_EVERY):
            try:
                state = page.state()
            except OSError:
                # The server stops with its session, which may be before `stop`.
                shown = {"banner": "unreachable", "detail": "", "stages": {}}
            else:
                shown = {
                    "banner": state["activity"]["kind"],
                    "detail": state["activity"]["detail"],
                    "stages": {
                        (w["input"] or f"claim:{w['subject']['id']}"): "/".join(
                            [w["stage"]]
                            + ([w["condition"]["kind"]] if w["condition"] else [])
                        )
                        for w in state["workflows"]
                    },
                }
            if shown != last:
                out.write(json.dumps({**shown, "received_at": now()}) + "\n")
                out.flush()
                last = shown


def spans(
    samples: list[dict], read: Callable[[dict], object], start: float, end: float
) -> list[tuple[object, float, float]]:
    """The values `read` took over [start, end], as (value, from, to) in seconds after
    `start`; None before the first sample."""
    before = [s for s in samples if moment(s) <= start]
    runs = [[read(before[-1]) if before else None, start, end]]
    for sample in samples:
        if start < moment(sample) < end and read(sample) != runs[-1][0]:
            runs[-1][2] = moment(sample)
            runs.append([read(sample), moment(sample), end])
    return [(value, begun - start, ended - start) for value, begun, ended in runs]


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


def tool_calls(record: dict) -> list[tuple[str, str]]:
    """Return each tool call in one stream record: its id, and what it runs, or the
    tool and its file."""
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


def calls_within(
    stream: list[dict], start: float, end: float
) -> list[tuple[float, float, str]]:
    """Each tool call's part of [start, end], as (from, to, what it ran)."""
    opened, calls = {}, []
    for record in stream:
        for call, ran in tool_calls(record):
            opened[call] = (moment(record), ran)
        content = (record.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else ():
            if block.get("type") == "tool_result" and block["tool_use_id"] in opened:
                begun, ran = opened.pop(block["tool_use_id"])
                if begun < end and moment(record) > start:
                    calls.append((max(begun, start), min(moment(record), end), ran))
    return calls


def tool_time(
    calls: list[tuple[float, float, str]], start: float
) -> tuple[float, tuple[float, str] | None]:
    """Seconds spent inside `calls`, overlapping calls counted once, and the slowest
    call as (seconds, what it ran)."""
    inside, reach = 0.0, start
    for begun, ended, _ in sorted(calls):
        inside += max(0.0, ended - max(begun, reach))
        reach = max(reach, ended)
    slowest = max(calls, key=lambda c: c[1] - c[0], default=None)
    return inside, slowest and (slowest[1] - slowest[0], slowest[2])


def hook_delivered(record: dict) -> bool:
    """Whether one stream record is a Leaf hook handing a delivery to the turn."""
    return record.get("subtype") == "hook_response" and "leaf-delivery-v" in (
        record.get("output") or ""
    )


def claims(ran: str) -> bool:
    """Whether one command writes a work claim."""
    return bool(re.search(r"\bstatus\b[^|;&]*\bworking\b|delivery claim", ran))


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
    # The sampler runs in a pool so that its failure raises here, not in a thread.
    sampled, sampling, sampler = threading.Event(), ThreadPoolExecutor(1), None
    try:
        url, waits, due, posted, received = None, set(), list(CASES[case]), 0, 0
        with (run / "stream.jsonl").open("w") as stream:

            def post() -> None:
                nonlocal posted
                posted += 1
                PageClient(url).post_comment(posted)
                marker = {"type": "eval_comment", "n": posted, "received_at": now()}
                stream.write(json.dumps(marker) + "\n")
                due.pop(0)

            for line in proc.stdout:
                record = {**json.loads(line), "received_at": now()}
                stream.write(json.dumps(record) + "\n")
                waits.update(waits_started(record))
                received += hook_delivered(record) + sum(
                    "leaf wait --ack" in c for c in commands(record)
                )
                content = (record.get("message") or {}).get("content")
                for block in content if isinstance(content, list) else ():
                    if block.get("type") != "tool_result":
                        continue
                    if not url and (
                        found := URL.search(json.dumps(block.get("content")))
                    ):
                        url = found.group(0)
                        sampler = sampling.submit(
                            sample_page, url, run / "states.jsonl", sampled
                        )
                    if due[:1] == ["running"] and url and block["tool_use_id"] in waits:
                        # The wait is running and the setup turn is not over.
                        post()
                if record.get("type") != "result":
                    continue
                if due[:1] == ["idle"] and url and waits:
                    # A turn is over and the session idles on its wait.
                    post()
                elif not due and received >= posted:
                    # Every comment is picked up. A trailing wake may follow,
                    # hence the grace period.
                    threading.Timer(20, close_stdin).start()
        proc.wait(timeout=60)
        if sampler:
            sampled.set()
            sampler.result()
        (run / "events.jsonl").write_text(leaf("events", str(page), check=True).stdout)
    finally:
        # A failed arm ends as promptly as a stalled one: no timer or child outlives it.
        deadline.cancel()
        sampled.set()
        sampling.shutdown()
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
    sampled = run / "states.jsonl"
    samples = (
        [json.loads(line) for line in sampled.read_text().splitlines()]
        if sampled.exists()
        else []
    )
    markers = [r for r in stream if r["type"] == "eval_comment"]
    waits = {wait for r in stream for wait in waits_started(r)}
    readings = []
    for i, marker in enumerate(markers):
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
        replies = [
            datetime.fromisoformat(e["ts"])
            for e in events
            if e["kind"] == "reply" and e.get("parent") == comment["id"]
        ]
        # What followed the post up to the message claiming its work: what carried
        # the comment in, and what the agent ran once it had.
        notified, carried, before_claim = None, None, []
        for record in stream[stream.index(marker) + 1 :]:
            ran = commands(record)
            if (notified or carried) and any(claims(c) for c in ran):
                break
            if record["type"] == "result" and (notified or carried):
                break
            if (
                record.get("subtype") == "task_notification"
                and record["tool_use_id"] in waits
            ):
                notified = notified or record
            elif (stop_blocked(record) or hook_delivered(record)) and not carried:
                # A hook that brings the comment in, or a Stop hook blocking a turn
                # from ending with it unread, carried it rather than the
                # notification.
                carried, before_claim = record, []
            elif notified or carried:
                before_claim += ran
        delivery = carried or notified
        # The turn that handled the comment ends at the first result after it came in.
        ended = delivery and next(
            (
                moment(r)
                for r in stream[stream.index(delivery) :]
                if r["type"] == "result"
            ),
            None,
        )
        # The page log stamps whole seconds, so no reply of a later turn falls at or
        # before this one's end.
        done = max(
            (r for r in replies if ended and r.timestamp() <= ended), default=None
        )
        readings.append(
            {
                "comment": marker["n"],
                "route": f"{carried['hook_event'].lower()} hook".replace(
                    "userpromptsubmit", "prompt"
                )
                if carried
                else "notification"
                if notified
                else None,
                "pickup_s": pickup and round((pickup - posted_at).total_seconds()),
                "woken_s": delivery and round(moment(delivery) - moment(marker), 1),
                "reply_s": replies and round((replies[0] - posted_at).total_seconds()),
                "done_s": done and round((done - posted_at).total_seconds()),
                "receipt_s": pickup
                and delivery
                and round(
                    (
                        pickup - datetime.fromisoformat(delivery["received_at"])
                    ).total_seconds()
                ),
                "before_claim": [short(c) for c in before_claim] if delivery else None,
                **(
                    turn_reading(
                        stream,
                        samples,
                        comment["id"],
                        moment(marker),
                        moment(delivery),
                        ended,
                        min(
                            [
                                ended + LINGER,
                                *(moment(m) for m in markers[i + 1 : i + 2]),
                            ]
                        ),
                    )
                    if ended
                    else {}
                ),
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


def turn_reading(
    stream: list[dict],
    samples: list[dict],
    comment: str,
    posted: float,
    woken: float,
    ended: float,
    until: float,
) -> dict:
    """One comment's turn from the stream beside what the page showed meanwhile."""
    calls = calls_within(stream, woken, ended)
    inside, slowest = tool_time(calls, woken)
    # The agent works on the comment until its last reply; what follows in the turn
    # is its handoff, which the banner rightly reads as listening.
    answered = max((to for _, to, ran in calls if "thread reply" in ran), default=ended)

    def banner(sample: dict) -> str:
        return sample["banner"]

    def stage(sample: dict, key: str = comment) -> str | None:
        shown = sample["stages"].get(key)
        return shown and shown.split("/")[0]

    def claimed(sample: dict) -> bool:
        # A claim matched to the comment makes its own workflow `working`; one made
        # after the reply that settles it stands on the thread, which the comment
        # roots. The banner is no witness: it can carry an earlier claim.
        return "working" in {stage(sample), stage(sample, f"claim:{comment}")}

    def first(read: Callable[[dict], object], wanted: Callable[[object], bool]):
        """Seconds from the delivery until `read` first shows a wanted value."""
        return next(
            (
                round(begun, 1)
                for value, begun, _ in spans(samples, read, woken, until)
                if wanted(value)
            ),
            None,
        )

    after = spans(samples, banner, ended, until)
    return {
        "shown_pickup_s": first(stage, lambda v: v in {"picked_up", "working"}),
        "shown_claim_s": first(claimed, bool),
        "turn_s": round(ended - posted, 1),
        "model_s": round(ended - woken - inside, 1),
        "tools_s": round(inside, 1),
        "slowest": slowest and [round(slowest[0], 1), short(slowest[1])],
        "stages": [
            [value, round(begun, 1)]
            for value, begun, _ in spans(
                samples, lambda s: s["stages"].get(comment), posted, until
            )
        ],
        "banner": [
            [value, round(begun, 1)]
            for value, begun, _ in spans(samples, banner, posted, until)
        ],
        "quiet_s": round(
            sum(
                ended - begun
                for value, begun, ended in spans(samples, banner, woken, answered)
                if value != "working"
            ),
            1,
        ),
        "late_s": round(after[0][2] - after[0][1], 1)
        if after[0][0] == "working"
        else 0,
    }


def short(ran: str) -> str:
    """One command with its directories dropped, so a table can show it."""
    return re.sub(r"(?<![\w$])/[^\s;&|]*/", "", ran)


def shown(runs: list[list]) -> str:
    return " ".join(f"{value or '-'}@{begun:g}" for value, begun in runs)


def report(results: dict) -> None:
    """Print one block per comment."""
    for name, readings in results.items():
        for r in readings:
            if r["comment"] is None:
                print(
                    f"{name:18}    {'TIMED OUT' if r['timed_out'] else 'posted nothing'}"
                )
                continue
            print(
                f"{name:18} #{r['comment']} {'TIMED OUT  ' if r['timed_out'] else ''}"
                f"woken {r['woken_s']}s  pickup {r['pickup_s']}s  "
                f"reply {r['reply_s']}s  done {r['done_s']}s  turn {r.get('turn_s')}s"
            )
            indent = " " * 22
            if "turn_s" in r:
                seconds, ran = r["slowest"] or (None, "")
                print(
                    f"{indent}model {r['model_s']}s  tools {r['tools_s']}s  "
                    f"slowest {seconds}s {ran[:70]!r}"
                )
            print(
                f"{indent}receipt {r['receipt_s']}s via {r['route'] or 'no delivery'}  "
                f"before claim {[c[:40] for c in r['before_claim'] or []] or 'nothing'}  "
                f"invented {r['invented_ack'] or 'none'}"
            )
            if "turn_s" in r:
                print(
                    f"{indent}after delivery: Picked up shown "
                    f"+{r['shown_pickup_s']}s (goal 1s)  claim shown "
                    f"+{r['shown_claim_s']}s (goal 2s)"
                )
                print(
                    f"{indent}workflow {shown(r['stages'])}  "
                    f"banner {shown(r['banner'])}  "
                    f"quiet {r['quiet_s']}s  late {r['late_s']}s"
                )


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
    report(results)
    print(f"details: {OUT}/results.json")


if __name__ == "__main__":
    main()
