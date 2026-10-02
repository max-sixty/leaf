"""Compare how a Claude Code agent handles a Leaf comment, base vs HEAD.

    uv run leaf-dev delivery-eval [BASE_REF]

Each of ROUNDS rounds launches one headless Claude Code session per arm and case at
once, with the plugin at BASE_REF (the merge base with `main` by default) or at HEAD,
so commit what you want measured. Each session is asked to serve a copy of
`examples/triage-board.html` and handle its comments; the command posts comments over
the page's API at the moments a case names:

- `idle`: after a turn ends with the page handed over, twice, so the second arrives
  only if the session went on watching;
- `mid-turn`: as soon as the setup turn has the page's URL, so the comment reaches a
  turn still in progress.

For each comment it reports, in seconds from the post, when the delivery reached the
agent (`woken`), the page log's `pickup`, the agent's work claim, its first reply, its
last reply in that turn (`done`) and the turn's end; what carried the comment in
(`route`: a wake or a hook); and what the agent ran between the
delivery and its claim, which should be nothing.

There are no statistics: two rounds, one page, fixed comments, the default model, and
timings that include model latency. Read the table, not the means. Each session costs
about a dollar. Streams, page logs and `results.json` land in `.tmp/delivery-eval/`.
"""

import json
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path

import click
from leaf.event_log import read_events

from leaf_dev import ROOT
from leaf_dev.harness import (
    URL,
    LiveChild,
    PageClient,
    build_pair,
    commands,
    hook_delivered,
    now,
    read_trace,
    run_leaf,
    scratch,
    waits_started,
)
from leaf_dev.review_scenario import REQUEST, prepare

OUT = ROOT / ".tmp" / "delivery-eval"
ROUNDS = 2
TURN_LIMIT = 600
# When each of a case's comments is posted: `idle` at the end of a turn, `running`
# once the setup turn has the page's URL.
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


def attempt(n: int) -> str:
    return f"delivery-eval-{n:04d}-attempt"


def moment(record: dict) -> float:
    return datetime.fromisoformat(record["received_at"]).timestamp()


def post_comment(url: str, n: int) -> None:
    """Post comment `n` as the page does, on its served revision."""
    page = PageClient(url)
    page.post(
        {
            "kind": "comment",
            "revision": page.state()["active"]["revision"],
            "attempt": attempt(n),
            **COMMENTS[n - 1],
        }
    )


def claims(ran: str) -> bool:
    """Whether one command writes a work claim."""
    return bool(re.search(r"\bstatus\b[^|;&]*\bworking\b|delivery claim", ran))


def stop_blocked(record: dict) -> bool:
    """Whether one stream record is the Stop hook holding a turn open: any output
    it gives does, whether through a block or Claude Code's non-error context."""
    return (
        record.get("subtype") == "hook_response"
        and record["hook_event"] == "Stop"
        and bool(record["output"].strip())
    )


def run_session(arm: Path, case: str, run: Path) -> None:
    """One Claude Code session: serve, wait, receive the case's comments, handle them."""
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    work = scratch()
    (run / "work-dir").write_text(f"{work}\n")
    page, state = work / "page", run / "state"
    prepare(arm, state, page)
    leaf = partial(run_leaf, arm, state)
    url, waits, due, posted, received = None, set(), list(CASES[case]), 0, 0
    try:
        with (
            LiveChild(
                work,
                REQUEST,
                "--plugin-dir",
                str(arm),
                stderr=run / "stderr.txt",
                limit=TURN_LIMIT,
                timed_out=run / "timed-out",
                dirs=[arm, state],
                env={"XDG_STATE_HOME": str(state)},
            ) as child,
            (run / "stream.jsonl").open("w") as stream,
        ):

            def post() -> None:
                nonlocal posted
                posted += 1
                post_comment(url, posted)
                marker = {"type": "eval_comment", "n": posted, "received_at": now()}
                stream.write(json.dumps(marker) + "\n")
                due.pop(0)

            for record in child.records():
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
                    if due[:1] == ["running"] and url:
                        # The page is served and the setup turn is not over.
                        post()
                if record.get("type") != "result":
                    continue
                if due[:1] == ["idle"] and url:
                    # A turn is over and the session idles on its page.
                    post()
                elif not due and received >= posted:
                    # Every comment is picked up; a trailing wake may follow.
                    threading.Timer(20, child.close).start()
        (run / "events.jsonl").write_text(
            leaf("page", "events", str(page), check=True).stdout
        )
    finally:
        # The agent's server outlives its session.
        leaf("server", "stop", str(page))


def score(run: Path) -> list[dict]:
    """Read one run's page log and stream into one reading per comment it was sent."""
    events = read_events(run)
    stream = read_trace(run / "stream.jsonl")
    waits = {wait for r in stream for wait in waits_started(r)}
    timed_out = (run / "timed-out").exists()
    readings = []
    for marker in (r for r in stream if r["type"] == "eval_comment"):
        comment = next(e for e in events if e.get("attempt") == attempt(marker["n"]))
        posted = datetime.fromisoformat(comment["ts"]).timestamp()
        pickup = next(
            (
                datetime.fromisoformat(e["ts"]).timestamp()
                for e in events
                if e["kind"] == "pickup"
                and e["phase"] == "opened"
                and comment["id"] in e["events"]
            ),
            None,
        )
        replies = [
            datetime.fromisoformat(e["ts"]).timestamp()
            for e in events
            if e["kind"] == "reply" and e.get("parent") == comment["id"]
        ]
        # From the post to the turn's end: what carried the comment in, what the
        # agent ran before claiming its work, and the claim.
        delivery, route, before_claim, claimed, ended = None, None, [], None, None
        for record in stream[stream.index(marker) + 1 :]:
            if record["type"] == "result" and delivery:
                ended = moment(record)
                break
            ran = commands(record)
            if delivery and not claimed:
                if any(claims(c) for c in ran):
                    claimed = moment(record)
                else:
                    before_claim += ran
            if (
                record.get("subtype") == "task_notification"
                and record["tool_use_id"] in waits
                and not delivery
            ):
                delivery, route = record, "notification"
            elif (
                (stop_blocked(record) or hook_delivered(record))
                and route in (None, "notification")
                and not claimed
            ):
                # A hook that brings the comment in, or a Stop hook holding the turn
                # open with it unread, carried it, even after a notification.
                delivery, before_claim = record, []
                route = f"{record['hook_event'].lower()} hook".replace(
                    "userpromptsubmit", "prompt"
                )
        start = moment(marker)
        readings.append(
            {
                "comment": marker["n"],
                "timed_out": timed_out,
                "route": route,
                "woken_s": since(delivery and moment(delivery), start),
                # The page log stamps whole seconds.
                "pickup_s": since(pickup, posted),
                "claim_s": since(claimed, start),
                "reply_s": since(replies[0] if replies else None, posted),
                # No reply of a later turn falls at or before this one's end.
                "done_s": since(
                    max((r for r in replies if ended and r <= ended), default=None),
                    posted,
                ),
                "turn_s": since(ended, start),
                "before_claim": [short(c) for c in before_claim],
            }
        )
    return readings or [{"comment": None, "timed_out": timed_out}]


def since(t: float | None, origin: float) -> float | None:
    return None if t is None else round(t - origin, 1)


def short(ran: str) -> str:
    """One command with its directories dropped, so a table can show it."""
    return re.sub(r"(?<![\w$])/[^\s;&|]*/", "", ran)


def report(results: dict) -> None:
    """Print one block per comment."""
    for name, readings in results.items():
        for r in readings:
            flag = "TIMED OUT " if r["timed_out"] else ""
            if r["comment"] is None:
                click.echo(f"{name:18}    {flag or 'posted nothing'}")
                continue
            timings = "  ".join(
                f"{step} " + ("-" if r[f"{step}_s"] is None else f"{r[f'{step}_s']}s")
                for step in ("woken", "pickup", "claim", "reply", "done", "turn")
            )
            click.echo(
                f"{name:18} #{r['comment']} {flag}via {r['route'] or 'no delivery'}  "
                + timings
            )
            click.echo(
                f"{'':22}before claim "
                f"{[c[:40] for c in r['before_claim']] or 'nothing'}"
            )


@click.command()
@click.argument("base_ref", required=False)
def delivery_eval(base_ref: str | None) -> None:
    """Compare how an agent answers comments.

    Compares how a Claude Code agent handles comments on a Leaf page it serves,
    BASE_REF's plugin against HEAD's; BASE_REF defaults to the merge base with
    main. Each round runs a live `claude -p` session per arm and case, about
    a dollar each, and prints per comment how it reached the agent and how long each
    step took; every stream and page log lands in .tmp/delivery-eval/.
    """
    with tempfile.TemporaryDirectory() as built:
        arms, commits = build_pair(base_ref, Path(built))
        OUT.mkdir(parents=True, exist_ok=True)
        runs = []
        for i in range(1, ROUNDS + 1):
            batch = [(arm, case, i) for case in CASES for arm in arms]
            with ThreadPoolExecutor(len(batch)) as pool:
                for future in [
                    pool.submit(run_session, arms[arm], case, OUT / f"{arm}-{case}-{i}")
                    for arm, case, i in batch
                ]:
                    future.result()
            runs += batch
    results = {
        f"{arm}-{case}-{i}": score(OUT / f"{arm}-{case}-{i}")
        for arm, case, i in sorted(runs)
    }
    (OUT / "results.json").write_text(
        json.dumps({"arms": commits, "runs": results}, indent=1)
    )
    click.echo(f"base {commits['base'][:10]} vs head {commits['head'][:10]}")
    report(results)
    click.echo(f"details: {OUT}/results.json")
