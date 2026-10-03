"""Whole Claude Code usability trajectories, scored by Promptfoo.

Each provider call owns one isolated scenario, including its resumed phases or
live user rounds. Promptfoo owns arms, repetition, concurrency, and reporting;
this module owns fixtures, execution, and fixed semantic check sets. Evidence
stays in the supplied work directory, and the agent cwd stays outside any repo.
"""

import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path

import click

from leaf_dev import ROOT
from leaf_dev.harness import (
    URL,
    LiveChild,
    PageClient,
    accepted_thread_claims,
    blocks,
    commands,
    completed,
    environment,
    inputs_received,
    now,
    read_trace,
    run_claude,
    run_leaf,
    scratch,
    trace_result,
    waits_started,
)

FIXTURES = ROOT / "evals/usability/fixtures"
MODEL = "claude-opus-5-5"
ANSWERS = json.loads((FIXTURES / "reading-answers.json").read_text())
SURFACES = [q["surface"] for q in ANSWERS["questions"]]

HEADLESS = (
    "This session is headless: nobody can open a browser or answer you during it. "
    "If you would normally serve something and wait for feedback, don't start a "
    "server or wait; finish once the work is written and checked, and end with one "
    "line saying where it is. Keep every file you create inside {work}."
)
QUIET = (
    "This session is headless: nobody can open a browser or answer you during it, so "
    "don't start a server or wait for feedback."
)

COLD = {
    "cold-report": """Write up these findings from yesterday's load test so I can skim them
and leave comments before tomorrow's standup. We'll probably drop it after that.

1. Throughput: the checkout service held 1,850 requests/s at a p99 of 240 ms. The
   database connection pool saturated at 2,100 requests/s.
2. Errors: 0.4% of requests failed, almost all 503s from the inventory service once
   its thread pool reached 200 threads.
3. Cost: the run used 38 instance-hours, 22% more than the last test, because
   autoscaling added nodes late.""",
    "cold-decision": """Show me the options for where to cache product prices, with the
evidence, so I can pick one. Last week's measurements:

- In-process LRU in each pod: 0.2 ms median read; 9% of reads were stale at a 60 s
  TTL; no new infrastructure.
- Shared Redis: 1.1 ms median read; 0.3% stale reads; about $410 a month.
- CDN edge cache: 0.05 ms median read, but only for anonymous traffic (68% of
  requests); a price purge takes up to 90 s to reach every edge.

We'll run exactly one of these.""",
    "near-miss": """Explain the difference between optimistic and pessimistic locking in a
relational database. A short answer is fine.""",
}

READING = """The directory {page} is a Leaf page I've been working on with an agent.
Answer these questions from what the page currently shows me. Reply with one numbered
line per question, each a short answer, and nothing else.

{questions}

{quiet}"""

RESUME = [
    """Another session was working with me on the Leaf page at {page}, and it has
ended. You're picking the page up. Don't change anything yet: first tell me where it
stands. Start your reply with these three lines, then add anything else I should
know:

Date: <the cutover date the page shows me now>
Approach: <how traffic will move to the new index>
Next: <what needs doing next>

{quiet}""",
    """Go ahead and do what needs doing next. Check the page and stamp the new version
when it's ready. {quiet}""",
]

CONSTRUCTS = [
    """The directory {page} is a Leaf page I've been working on with an agent. Before
we change it, answer from what the page currently shows me, one numbered line each:

1. What does the release note say?
2. What p95 does the latency sentence state, and what is the latest measurement?
3. Which region has the most errors in the chart?

Don't change anything yet. {quiet}""",
    """Now update the page: the rollout starts 19 November, not 12 November; the latency
sentence should state the latest p95 measurement; and sa-east's error count was
miscounted, it is 85. Check the page and stamp the new version. {quiet}""",
]

BOARD = [
    """The directory {page} is a Leaf page I've been working on with an agent. Before
we change it, answer from what the page currently shows me, one numbered line each:

1. List the cards in the Doing column, top to bottom.
2. Which column is "Rotate signing keys" in?

Don't change anything yet. {quiet}""",
    """Now add a card "Revoke old keys" at the bottom of To do, and rename "Expiry
alerts" to "Key expiry alerts". Check the page and stamp the new version. {quiet}""",
]
# The user's moves, in order: two cards into Doing at ranks around the authored "1"
# and "2", and one into Done that they then undid.
BOARD_MOVES = [
    {"card": "card-docs", "to": "col-doing", "rank": "0i"},
    {"card": "card-audit", "to": "col-doing", "rank": "1i"},
    {"card": "card-rotate", "to": "col-done", "rank": "1"},
]
BOARD_DOING = ["card-docs", "card-inventory", "card-audit", "card-alerts"]

PACKAGE = """The Leaf page at {page} is a reliability review I'm writing with an agent.
It uses our team's `slo` package, which has a widget for error budgets. Add checkout's
error budget to the Checkout section: the objective is 99.9% availability over 28 days,
and 62% of the budget is spent so far. Check the page and stamp the new version.
{quiet}"""

SHARED_SOURCE = [
    """The directory {page} is a Leaf page I've been working on with an agent. Before
we change it, answer from what the page currently shows me, one numbered line each:

1. Which branch is finch's worktree on, and are its tests passing?
2. How many commits ahead of its base is wren's worktree?

Don't change anything yet. {quiet}""",
    """finch just pushed a fix: its worktree's head is now 3f0a6be, 7 commits ahead of
main, and its tests pass. Update the page to show that. {quiet}""",
]

# The live cases' first messages. Each names the page; none names a reference.
HANDOFF = """I've drafted a Leaf page at {page} comparing three ways to run the
order-history backfill. Hand it over so I can pick one in my browser and leave
comments, and handle what I send you."""
REOPEN = """The Leaf page at {page} is one I've been reviewing with another agent
session, which has ended. Serve it again so I can keep working on it in my browser,
and handle what I send you."""

# What a live case's user does, one list of moves per round. `anchor` is an
# (element, quote) pair in the served HTML; `undoes: "previous"` names the move posted
# just before it; `parent: "latest"` the page's newest message; `{origin}` in text is
# the served origin. Every document-bound move names the served revision.
DRY_RUN = {
    "kind": "comment",
    "text": "Add how long the dry run took: 3 h 10 min.",
    "anchor": ("dry-run", "finished without errors"),
}
FREEZE_QUESTION = {
    "kind": "comment",
    "text": "Which option needs a write freeze, and for how long?",
    "anchor": ("lede", "Pick how the copy runs."),
}
PICK = {
    "kind": "action",
    "widget": "copy-mode",
    "action": "choose",
    "detail": {"options": ["opt-online"]},
}
SHORTEN = {
    "kind": "comment",
    "token": "shorten",
    "anchor": ("why-now", "The reporting team moves its dashboards"),
}
CARD_MOVE = {
    "kind": "action",
    "widget": "follow-board",
    "action": "move",
    "detail": {"card": "card-lag-alert", "to": "col-done", "rank": "1"},
}
# The duration the `DRY_RUN` comment asks for, as the edited paragraph may write it.
DRY_RUN_DONE = r"3\s*h(ours?)?\s*(and\s*)?10"
UNDO = {"kind": "undo", "undoes": "previous"}
SUMMARY_ERROR = {
    "kind": "error",
    "text": "Uncaught TypeError: replaceAll must be called with a global RegExp "
    "({origin}/:{line})",
}
START_QUESTION = {
    "kind": "reply",
    "parent": "latest",
    "text": "Remind me what time the copy starts each night, in UTC? I'm putting it "
    "in the on-call calendar.",
}
# The thread another session held on the elided page: the user's messages and its
# answers, alternating. The fifth settles the window; the delivery of a new message
# shows the first and the latest seven, so the premise is in the part it leaves out.
ELIDED_THREAD = json.loads((FIXTURES / "elided-thread.json").read_text())


@dataclass(frozen=True)
class Case:
    name: str
    prompts: tuple[str, ...]
    fixture: str | None = None
    # A live case's user moves, one tuple per round (`execute_live`).
    rounds: tuple[tuple[dict, ...], ...] = ()


def reading_case(surface: str | None) -> Case:
    questions = [
        q for q in ANSWERS["questions"] if surface is None or q["surface"] == surface
    ]
    lines = "\n".join(f"{n}. {q['question']}" for n, q in enumerate(questions, 1))
    prompt = READING.replace("{questions}", lines)
    name = "reading" if surface is None else f"reading-{surface}"
    return Case(name, (prompt,), fixture=name)


CASES = {
    **{name: Case(name, (f"{prompt}\n\n{HEADLESS}",)) for name, prompt in COLD.items()},
    "reading": reading_case(None),
    **{f"reading-{s}": reading_case(s) for s in SURFACES},
    "resume": Case("resume", tuple(RESUME), fixture="resume"),
    "constructs": Case("constructs", tuple(CONSTRUCTS), fixture="constructs"),
    "board": Case("board", tuple(BOARD), fixture="board"),
    "package": Case("package", (PACKAGE,), fixture="package"),
    "shared-source": Case(
        "shared-source", tuple(SHARED_SOURCE), fixture="shared-source"
    ),
    "handoff": Case(
        "handoff",
        (HANDOFF,),
        fixture="handoff",
        rounds=((DRY_RUN,), (FREEZE_QUESTION,)),
    ),
    "mixed": Case(
        "mixed",
        (REOPEN,),
        fixture="mixed",
        rounds=((DRY_RUN, PICK, SHORTEN, CARD_MOVE, UNDO, SUMMARY_ERROR),),
    ),
    "elided": Case("elided", (REOPEN,), fixture="elided", rounds=((START_QUESTION,),)),
}


@dataclass(frozen=True)
class Run:
    case: str
    payload: Path
    dir: Path

    @property
    def state(self) -> Path:
        return self.dir / "state"

    @property
    def work(self) -> Path:
        return Path((self.dir / "work-dir").read_text().strip())

    def leaf(self, *args: str, **kwargs):
        return run_leaf(self.payload, self.state, *args, **kwargs)

    def traces(self) -> list[list[dict]]:
        return [read_trace(path) for path in sorted(self.dir.glob("stream-*.jsonl"))]

    def usable(self) -> bool:
        traces = self.traces()
        case = CASES[self.case]
        if (
            len(traces) != len(case.prompts)
            or not all(completed(t) for t in traces)
            or any(
                d.get("is_error") is not False
                for t in traces
                for d in t
                if d.get("type") == "result"
            )
            or (self.dir / "timed-out").exists()
        ):
            return False
        rounds = live_rounds(traces[0]) if case.rounds else []
        if len(rounds) != len(case.rounds) or any(r["end"] is None for r in rounds):
            return False
        if not case.rounds:
            return True
        attempts = {
            attempt_key(n, i)
            for n, moves in enumerate(case.rounds)
            for i, move in enumerate(moves)
            if move["kind"] != "error"
        }
        return inputs_received(page_events(self.work / "page"), attempts)


# Fixtures


def arm_python(run: Run, code: str, *args: str) -> None:
    """Run `code` with the arm's own `leaf` package, in the run's state home."""
    proc = subprocess.run(
        ["uv", "run", "-q", "--no-dev", "--project", str(run.payload), "python", "-c"]
        + [code, *args],
        capture_output=True,
        text=True,
        check=False,
        env=environment(XDG_STATE_HOME=str(run.state)),
    )
    if proc.returncode:
        raise click.ClickException(f"{code.splitlines()[-1]} {args}: {proc.stderr}")


def admit(run: Run, page: Path, event: dict) -> None:
    """Admit one user move through the arm's browser door."""
    arm_python(
        run,
        "import json, sys\nfrom pathlib import Path\nfrom leaf import event_endpoint\n"
        "status, body = event_endpoint.accept_event(Path(sys.argv[1]), "
        "json.loads(sys.argv[2]), dict)\n"
        "assert status == 200, body",
        str(page),
        json.dumps(event),
    )


def page_events(page: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (page / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]


def build_reading(run: Run, page: Path, surface: str | None) -> None:
    html = (FIXTURES / "reading.html").read_text()
    if surface is not None:
        keep = next(
            q["section"] for q in ANSWERS["questions"] if q["surface"] == surface
        )
        html = re.sub(
            r'\n *<section id="([\w-]+)">.*?</section>\n',
            lambda m: m[0] if m[1] == keep else "\n",
            html,
            flags=re.DOTALL,
        )
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(html)
    if 'source="copier-config"' in html:
        run.leaf(
            "data", "set", str(page), "copier-config",
            input_text=json.dumps(ANSWERS["data"]["copier-config"]), check=True,
        )  # fmt: skip
    run.leaf("page", "stamp", str(page), "--text", "Plan as authored", check=True)
    run.leaf("status", str(page), "waiting", "Pick a cutover mode", check=True)
    if 'id="cutover-mode"' in html:
        for move in ANSWERS["moves"]:
            if move.get("undoes") == "previous":
                move = {**move, "undoes": page_events(page)[-1]["id"]}
            admit(run, page, move)


def anchor(html: str, element: str, quote: str) -> dict:
    """A comment anchor on `quote` inside the element with id `element`."""
    # The rendered text, whose whitespace the browser collapses.
    text = " ".join(re.search(rf'id="{element}">(.*?)</', html, re.DOTALL)[1].split())
    at = text.index(quote)
    return {
        "section": element,
        "quote": quote,
        "prefix": text[max(0, at - 24) : at],
        "suffix": text[at + len(quote) : at + len(quote) + 24],
    }


def build_resume(run: Run, page: Path) -> None:
    v1 = (FIXTURES / "resume-v1.html").read_text()
    v2 = (FIXTURES / "resume-v2.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(v1)
    run.leaf("page", "stamp", str(page), "--text", "First plan", check=True)
    admit(run, page, {
        "kind": "comment", "revision": 1,
        "text": "These rehearsal numbers are from before the mapping change. Rerun it and update the figure.",
        "anchor": anchor(v1, "rehearsal-result", "4.1 million documents in 3 h 20 min"),
    })  # fmt: skip
    rerun = page_events(page)[-1]["id"]
    (page / "index.html").write_text(v2)
    run.leaf(
        "page", "stamp", str(page), "--text",
        "Rehearsal rerun after the mapping change; ask how traffic moves", check=True,
    )  # fmt: skip
    run.leaf(
        "thread", "reply", str(page), "--for", rerun, "--text",
        "Reran it on 18 September after the mapping change: 4.3 million documents in 3 h 05 min. The page shows the new figure.",
        check=True,
    )  # fmt: skip
    run.leaf(
        "status", str(page), "waiting", "Pick how traffic moves to the new index",
        check=True,
    )  # fmt: skip
    admit(run, page, {"kind": "resolve", "parent": rerun})
    admit(run, page, {
        "kind": "action", "revision": 2, "widget": "rollout", "action": "choose",
        "detail": {"options": ["opt-per-tenant"]},
    })  # fmt: skip
    admit(run, page, {
        "kind": "comment", "revision": 2,
        "text": "Batches of 500 saturate the replica's disk queue. Drop to 200 and say why on the page.",
        "anchor": anchor(v2, "batch-size", "batches of 500"),
    })  # fmt: skip
    # The previous session's last save: an unexplained date change, and a paragraph
    # inside the options that makes the save invalid, so the live page stays at v2.
    candidate = v2.replace("scheduled for 21 October", "scheduled for 3 November")
    candidate = candidate.replace(
        '<lf-options id="rollout" choose>',
        '<lf-options id="rollout" choose>\n<p id="approach-deadline">Decide by Friday.</p>',
    )
    assert candidate.count("3 November") == 1 and "approach-deadline" in candidate
    (page / "index.html").write_text(candidate)


CONSTRUCTS_DRAFT = (
    "Release 4.2 moves card tokenization to the new vault. Merchants need no code "
    "changes. Rollout starts 12 November.\n"
)


def build_constructs(run: Run, page: Path) -> None:
    """The draft the user rewrote, the p95 stated at one measurement with a later one
    in its source, and the chart."""
    template = (FIXTURES / "constructs.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(template)
    measured = run.leaf(
        "data", "set", str(page), "checkout-p95", input_text="184", check=True
    ).stdout
    at = json.loads(measured)["updated"]
    (page / "index.html").write_text(re.sub(r'\bat="[^"]*"', f'at="{at}"', template))
    run.leaf("page", "stamp", str(page), "--text", "Release 4.2 review", check=True)
    run.leaf("status", str(page), "waiting", "Edit the release note", check=True)
    admit(run, page, {
        "kind": "action", "revision": 1, "widget": "release-note", "action": "edit",
        "detail": {"text": CONSTRUCTS_DRAFT},
    })  # fmt: skip
    run.leaf("data", "set", str(page), "checkout-p95", input_text="231", check=True)


def build_board(run: Run, page: Path) -> None:
    """A board whose cards the user moved, one move undone."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "board.html").read_text())
    run.leaf("page", "stamp", str(page), "--text", "Key rotation board", check=True)
    run.leaf("status", str(page), "waiting", "Move cards as work changes", check=True)
    for detail in BOARD_MOVES:
        admit(run, page, {
            "kind": "action", "revision": 1, "widget": "work-board",
            "action": "move", "detail": detail,
        })  # fmt: skip
    admit(run, page, {"kind": "undo", "undoes": page_events(page)[-1]["id"]})


def build_package(run: Run, page: Path) -> None:
    """A stamped page that selects the `slo` package, installed in the run's own
    state home as a team's package would be on its machine."""
    run.leaf("package", "install", str(FIXTURES / "slo"), check=True)
    run.leaf("page", "init", "--package", "slo", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "slo.html").read_text())
    run.leaf("page", "stamp", str(page), "--text", "September review", check=True)


def build_shared_source(run: Run, page: Path) -> None:
    """Two worktree widgets on one source, whose snapshot lists an unrelated record
    first."""
    run.leaf("page", "init", "--package", "command-hub", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "hub.html").read_text())
    run.leaf(
        "data", "set", str(page), "project-worktrees",
        input_text=(FIXTURES / "hub-worktrees.json").read_text(), check=True,
    )  # fmt: skip
    run.leaf("page", "stamp", str(page), "--text", "Parser workers", check=True)


def build_handoff(run: Run, page: Path) -> None:
    """A drafted page nobody has checked, served or stamped."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "backfill.html").read_text())


def build_mixed(run: Run, page: Path) -> None:
    """A stamped page another session handed over; its copy button's script
    throws on a click."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "mixed.html").read_text())
    run.leaf("page", "stamp", str(page), "--text", "Backfill plan", check=True)
    run.leaf("status", str(page), "waiting", "Pick how the copy runs", check=True)


def build_elided(run: Run, page: Path) -> None:
    """Start without the history, so setup cannot preload the hidden premise.

    The answered history is admitted after initial handover, before the question.
    """
    html = (FIXTURES / "elided.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(html)
    run.leaf("page", "stamp", str(page), "--text", "Backfill schedule", check=True)
    run.leaf("status", str(page), "waiting", "", check=True)


def append_elided_history(run: Run, page: Path) -> None:
    """Admit and acknowledge the historical conversation in one transaction.

    The wait cannot capture half the history before its acknowledgement. Nothing
    rewrites the log: this fixture uses the same admission and receipt boundaries
    as the CLI and carriers, under their one transaction lease.
    """
    state, html = active_html(run, page)
    arm_python(
        run,
        "import json, sys\nfrom pathlib import Path\n"
        "from leaf.event_contracts import append_admitted\n"
        "from leaf.delivery import batch_data, receive_batch, record_pickup\n"
        "from leaf.service import PageTransaction, unacknowledged\n"
        "page_dir = Path(sys.argv[1])\n"
        "history, anchor, revision = json.loads(sys.argv[2])\n"
        "with PageTransaction(page_dir) as page:\n"
        "    first = append_admitted(page, dict(kind='comment', author='user', "
        "revision=revision, anchor=anchor, text=history[0]))\n"
        "    latest = first\n"
        "    for n, text in enumerate(history[1:]):\n"
        "        latest = append_admitted(page, dict(kind='reply', "
        "author='agent' if n % 2 == 0 else 'user', "
        "parent=latest['id'], text=text, revision=revision))\n"
        "    append_admitted(page, dict(kind='resolve', author='user', parent=first['id']))\n"
        "    batch = batch_data(page_dir, page, unacknowledged(page.events, page.cursor))\n"
        "    claim = page.active_claim\n"
        "    session = claim['id'] if claim else None\n"
        "    with receive_batch(page, batch, session_id=session) as events:\n"
        "        record_pickup(page, events, session=session)\n",
        str(page),
        json.dumps(
            [
                ELIDED_THREAD,
                anchor(html, "window", "in the maintenance window"),
                state["active"]["revision"],
            ]
        ),
    )


BUILDERS = {
    "board": build_board,
    "constructs": build_constructs,
    "resume": build_resume,
    "package": build_package,
    "shared-source": build_shared_source,
    "handoff": build_handoff,
    "mixed": build_mixed,
    "elided": build_elided,
}


def build_fixture(run: Run, name: str, page: Path) -> None:
    if name in BUILDERS:
        BUILDERS[name](run, page)
    else:
        build_reading(run, page, name.removeprefix("reading").removeprefix("-") or None)


# Running


def execute(run: Run) -> None:
    """One run: build the case's fixture, then run each phase, resuming the first
    phase's session, or the live session."""
    case = CASES[run.case]
    run.state.mkdir(parents=True)
    work = scratch()
    (run.dir / "work-dir").write_text(f"{work}\n")
    page = work / "page"
    if case.fixture:
        build_fixture(run, case.fixture, page)
        shutil.copytree(page, run.dir / "fixture", ignore=ignore)
    if case.rounds:
        execute_live(run, case, work, page)
    else:
        execute_phases(run, case, work, page)
    for found in pages(work, run.state):
        shutil.copytree(found, run.dir / "pages" / found.name, ignore=ignore)


# How long a live session may run, how long a posted round may wait for the delivery
# that carries it, and how long a finished session stays open for a trailing turn.
LIVE_LIMIT = 1500
DELIVERY_LIMIT = 300
GRACE = 20


def execute_live(run: Run, case: Case, work: Path, page: Path) -> None:
    """Serve the case's page from a live session and play its user.

    Each time a turn ends with every posted round delivered, the next round goes out
    through the served page, a few seconds later so that a wait the turn started has
    taken its lease. The session closes once the last round's turn has ended, when a
    round waits past DELIVERY_LIMIT, or at LIVE_LIMIT, which voids the run. At each
    turn's end the stream records the page's status."""
    prompt = case.prompts[0].replace("{page}", str(page))
    (run.dir / "prompt-1.txt").write_text(prompt)
    # The deadline for the posted round's delivery; unstarted until the first post.
    waiting = threading.Timer(DELIVERY_LIMIT, lambda: None)
    url, posted, confirmed = None, 0, 0
    attempts = set()
    try:
        with (
            LiveChild(
                work,
                prompt,
                "--model",
                MODEL,
                "--plugin-dir",
                str(run.payload),
                stderr=run.dir / "err-1.txt",
                limit=LIVE_LIMIT,
                timed_out=run.dir / "timed-out",
                dirs=[run.payload],
                env={"XDG_STATE_HOME": str(run.state)},
            ) as child,
            (run.dir / "stream-1.jsonl").open("w") as stream,
        ):

            def note(record: dict) -> None:
                stream.write(json.dumps(record) + "\n")
                stream.flush()

            for record in child.records():
                if not url and (found := URL.search(json.dumps(record))):
                    url = found[0]
                received = not posted or inputs_received(page_events(page), attempts)
                if received:
                    waiting.cancel()
                    if confirmed < posted:
                        confirmed = posted
                        note(
                            {
                                "type": "eval_received",
                                "round": posted,
                                "received_at": now(),
                            }
                        )
                note(record)
                if record.get("type") != "result":
                    continue
                status = page_state(run, page).get("status")
                note({"type": "eval_status", "status": status, "received_at": now()})
                if not received:
                    continue
                if url and posted < len(case.rounds):
                    time.sleep(3)
                    if run.case == "elided" and posted == 0:
                        append_elided_history(run, page)
                    post_round(run, page, PageClient(url), case.rounds[posted], posted)
                    attempts.update(
                        attempt_key(posted, i)
                        for i, move in enumerate(case.rounds[posted])
                        if move["kind"] != "error"
                    )
                    posted += 1
                    note({"type": "eval_post", "round": posted, "received_at": now()})
                    waiting = threading.Timer(DELIVERY_LIMIT, child.close)
                    waiting.start()
                else:
                    threading.Timer(GRACE, child.close).start()
    finally:
        waiting.cancel()
        run.leaf("server", "stop", str(page))


def post_round(
    run: Run, page: Path, client: PageClient, moves: tuple[dict, ...], n: int
) -> None:
    """Post one round's moves as the user's tab would, resolving each placeholder
    against the page as it is served now."""
    served = page_state(run, page)
    html = (page / served["active"]["file"]).read_text()
    for i, move in enumerate(moves):
        event = dict(move)
        if move["kind"] != "error":
            event["attempt"] = attempt_key(n, i)
        if "anchor" in move:
            event["anchor"] = anchor(html, *move["anchor"])
        if move.get("undoes") == "previous":
            event["undoes"] = posted_event(page, attempt_key(n, i - 1))["id"]
        if move.get("parent") == "latest":
            event["parent"] = [
                e for e in page_events(page) if e["kind"] in ("comment", "reply")
            ][-1]["id"]
        if "text" in move:
            event["text"] = move["text"].format(
                origin=client.origin,
                line=html[: html.find("replaceAll(")].count("\n") + 1,
            )
        if move["kind"] != "undo":
            event["revision"] = served["active"]["revision"]
        client.post(event)


def attempt_key(n: int, i: int) -> str:
    """The retry key of round `n`'s move `i`, which finds its event in the log."""
    return f"usability-eval-{n}-{i}"


def posted_event(page: Path, key: str) -> dict:
    return next(e for e in page_events(page) if e.get("attempt") == key)


def execute_phases(run: Run, case: Case, work: Path, page: Path) -> None:
    """Run each of the case's prompts as a headless phase, resuming the first
    phase's session."""
    session = None
    for phase, template in enumerate(case.prompts, 1):
        prompt = (
            template.replace("{page}", str(page))
            .replace("{work}", str(work))
            .replace("{quiet}", QUIET)
        )
        (run.dir / f"prompt-{phase}.txt").write_text(prompt)
        trace = run_claude(
            work,
            prompt,
            "--model",
            MODEL,
            "--plugin-dir",
            str(run.payload),
            *(("--resume", session) if session else ()),
            out=run.dir / f"stream-{phase}.jsonl",
            err=run.dir / f"err-{phase}.txt",
            dirs=[run.payload],
            env={"XDG_STATE_HOME": str(run.state)},
        )
        session = trace_result(trace).get("session_id")
        if not session:
            break


def ignore(directory, names):
    """Leave the vendored layer and service files out of a run's copy of a page."""
    return {
        n
        for n in names
        if n in ("runtime", "vendor", "widgets", "instructions", "service.json")
        or n.endswith((".lock", ".js", ".css"))
    }


def pages(*roots: Path) -> list[Path]:
    """Every page directory under `roots`."""
    return sorted(p.parent for root in roots for p in root.rglob("events.jsonl"))


# Scoring


# The first match names a shell call; a call that reads several things counts as the
# first, so `output_bytes` is a rough split.
BASH_KINDS = {
    "reference": r"references/|SKILL\.md",
    # A thread's or widget's reading: `page state PAGE ID`.
    "page state ID": r"\bpage state\s+\S+\s+[^-\s|;&>]",
    "page state": r"\bpage state\b",
    "events": r"\bpage events\b",
    "transcript": r"\btranscript\b",
    "page check": r"\bpage check\b",
    "page stamp": r"\bpage stamp\b",
    "thread reply": r"\bthread reply\b",
    "server": r"\bserver (start|run)\b",
    "wait": r"\bleaf wait\b",
    "registry": r"registry\.json",
    "events.jsonl": r"events\.jsonl",
    "index.html": r"index\.html",
    "data/": r"\bdata/",
}


def call_kind(call: dict) -> str:
    """What a tool call read or ran, for the context-cost breakdown."""
    name, inp = call["name"], call.get("input", {})
    if name == "Skill":
        return "skill"
    if name == "Bash":
        cmd = inp.get("command", "")
        return next((k for k, p in BASH_KINDS.items() if re.search(p, cmd)), "bash")
    path = inp.get("file_path", "") or inp.get("path", "")
    if "/references/" in path:
        return "reference"
    if path.endswith("SKILL.md"):
        return "skill"
    for kind in ("registry.json", "events.jsonl", "index.html", "/data/"):
        if path.endswith(kind) or kind in path:
            return kind.strip("/")
    return name.lower()


def text_of(content) -> str:
    return content if isinstance(content, str) else json.dumps(content)


def trace_scores(trace: list[dict]) -> dict:
    calls, results = {}, {}
    for block in blocks(trace):
        if block.get("type") == "tool_use":
            calls[block["id"]] = block
        elif block.get("type") == "tool_result":
            results[block["tool_use_id"]] = block
    kinds, output = [], {}
    for cid, call in calls.items():
        kind = call_kind(call)
        kinds.append(kind)
        size = len(text_of(results.get(cid, {}).get("content", "")))
        output[kind] = output.get(kind, 0) + size
    skills = [
        c["input"].get("skill", "") for c in calls.values() if c["name"] == "Skill"
    ]
    references = sorted(
        {
            m
            for c in calls.values()
            for m in re.findall(r"references/[\w-]+\.md", json.dumps(c.get("input")))
        }
    )
    done = trace_result(trace)
    # A live trace ends each turn with a result: its usage, turns and duration are
    # that turn's, and its cost is the session's so far.
    ended = [d for d in trace if d.get("type") == "result"]
    usage = [d.get("usage", {}) for d in ended]
    return {
        "completed": completed(trace),
        "turns": sum(d.get("num_turns", 0) for d in ended),
        "cost_usd": round(done.get("total_cost_usd", 0), 3),
        "minutes": round(sum(d.get("duration_ms", 0) for d in ended) / 60000, 1),
        "input_tokens": sum(
            u.get(k, 0)
            for u in usage
            for k in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        ),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "denials": len(done.get("permission_denials") or []),
        "leaf_skill": any("leaf" in s for s in skills),
        "references": references,
        "calls": kinds,
        "output_bytes": dict(sorted(output.items(), key=lambda kv: -kv[1])),
        "reply": done.get("result") or "",
    }


def page_state(run: Run, page: Path) -> dict:
    proc = run.leaf("page", "state", str(page))
    return json.loads(proc.stdout) if proc.returncode == 0 else {}


def answered_lines(reply: str) -> dict[int, str]:
    return {
        int(m[1]): m[2].strip()
        for m in re.finditer(r"^\s*\**(\d)[.)]\**\s*(.*)$", reply, re.MULTILINE)
    }


def labelled(reply: str, label: str) -> str:
    m = re.search(rf"^\W*{label}\W*:?\**\s*(.*)$", reply, re.MULTILINE | re.IGNORECASE)
    return m[1] if m else ""


def check(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def score_cold(run: Run, reply: str, calls: list[str]) -> dict:
    found = pages(run.work, run.state)
    out = {"pages": len(found)}
    if run.case == "near-miss" or not found:
        return out
    page = found[0]
    html = (page / "index.html").read_text()
    checked = run.leaf("page", "check", str(page))
    state = page_state(run, page)
    out |= {
        "valid": checked.returncode == 0,
        "agent_checked": "page check" in calls,
        "stamped": len(state.get("versions", [])),
        "not_served": "server" not in calls,
        "status": (state.get("status") or {}).get("state"),
        "asks": len(re.findall(r"<lf-ask\b", html)),
        "choose_groups": len(re.findall(r"<lf-options\b[^>]*\bchoose\b", html)),
        "options": len(re.findall(r"<lf-option\b", html)),
        "single_choice": not re.search(r"<lf-options\b[^>]*\bmultiple\b", html),
        "no_sign_off": 'content="sign-off"' not in html,
    }
    if run.case == "cold-decision":
        ask = re.search(r"<lf-ask\b.*?</lf-ask>", html, re.DOTALL)
        body = re.sub(r"<[^>]+>", " ", ask[0]) if ask else ""
        # The measurements the prompt gave, as the Ask shows them.
        evidence = ["0.2", "1.1", "0.05", "9%", "0.3%", "410", "68%", "90"]
        out["evidence_in_ask"] = sum(e in body for e in evidence)
        out["names_gesture"] = check(r"\b(pick|choose|select|click)", reply)
    return out


def score_reading(run: Run, reply: str) -> dict:
    surface = run.case.removeprefix("reading").removeprefix("-") or None
    questions = [
        q for q in ANSWERS["questions"] if surface is None or q["surface"] == surface
    ]
    lines = answered_lines(reply)
    return {
        "answers": {
            q["surface"]: check(q["pattern"], lines.get(n, ""))
            for n, q in enumerate(questions, 1)
        },
        "correct": sum(
            check(q["pattern"], lines.get(n, "")) for n, q in enumerate(questions, 1)
        ),
        "of": len(questions),
    }


def score_constructs(run: Run, replies: list[str]) -> dict:
    lines = answered_lines(replies[0] if replies else "")
    out = {
        "draft_read": check(r"no code changes", lines.get(1, "")),
        "p95_read": check(r"\b184\b", lines.get(2, ""))
        and check(r"\b231\b", lines.get(2, "")),
        "chart_read": check(r"us-east", lines.get(3, "")),
    }
    page = run.work / "page"
    state = page_state(run, page)
    if not state or len(state["versions"]) < 2:
        return out | {"stamped": False}
    html = (page / state["active"]["file"]).read_text()
    draft = re.search(r"<lf-draft\b([^>]*)>(.*?)</lf-draft>", html, re.DOTALL)
    standing = next(
        (s["detail"]["text"] for s in state["state"] if s["widget"] == "release-note"),
        None,
    )
    # What the user now reads: their edit where it still stands, else the markup.
    effective = standing if standing is not None else (draft[2] if draft else "")
    figure = re.search(r'<lf-num\b[^>]*id="p95-figure"[^>]*>(.*?)</lf-num>', html)
    chart = re.search(r'id="region-errors".*?</lf-chart>', html, re.DOTALL)
    return out | {
        "stamped": True,
        "draft_date": check(r"19 nov", effective) and not check(r"12 nov", effective),
        "draft_kept_user_words": check(r"no code changes", effective),
        "draft_restated": bool(draft and "restated" in draft[1]),
        "p95_text": bool(figure and check(r"\b231\b", figure[1])),
        "p95_current": state["measurement_lag"] == [],
        # The figure's owner is the markup; its source keeps the measurement.
        "source_kept": (page / "data/checkout-p95.json").read_bytes()
        == (run.dir / "fixture/data/checkout-p95.json").read_bytes(),
        # The row as an object, its keys in whatever order and quoting the agent left
        # them.
        "chart_85": bool(
            chart
            and any(
                re.search(r"[\"']sa-east[\"']", row)
                and re.search(r"\berrors[\"']?\s*:\s*85\b", row)
                for row in re.findall(r"\{[^{}]*\}", chart[0])
            )
        ),
    }


def column_cards(html: str, column: str) -> list[str]:
    body = re.search(rf'<lf-column\b[^>]*id="{column}".*?</lf-column>', html, re.DOTALL)
    return re.findall(r'<lf-card\b[^>]*id="([\w-]+)"', body[0]) if body else []


def score_board(run: Run, replies: list[str]) -> dict:
    # The first answer is a list of its own, so split at the second answer's number
    # at the start of a line rather than reading numbered lines.
    parts = re.split(
        r"^\**2[.)]", replies[0] if replies else "", maxsplit=1, flags=re.MULTILINE
    )
    second = parts[1].split("\n", 1)[0] if len(parts) > 1 else ""
    titles = ["runbook", "inventory", "audit", "alerts"]
    at = [parts[0].lower().find(t) for t in titles]
    out = {
        "doing_read": -1 not in at and at == sorted(at),
        "undo_read": check(r"\bto ?do\b", second),
    }
    page = run.work / "page"
    state = page_state(run, page)
    if not state or len(state["versions"]) < 2:
        return out | {"stamped": False}
    html = (page / state["active"]["file"]).read_text()
    todo = column_cards(html, "col-todo")
    return out | {
        "stamped": True,
        "doing_order": column_cards(html, "col-doing") == BOARD_DOING,
        "todo_kept": todo[:1] == ["card-rotate"] and len(todo) == 2,
        "done_empty": column_cards(html, "col-done") == [],
        "renamed": check(r"key expiry alerts", html),
        "no_restated": "restated" not in html,
    }


def score_resume(run: Run, replies: list[str]) -> dict:
    first = replies[0] if replies else ""
    out = {
        # The first date the line names is the one it reports as current.
        "date": check(r"^\W*(21\s*oct|oct\w*\.?\s*21)", labelled(first, "date")),
        "approach": check(r"tenant", labelled(first, "approach")),
        "next_batch": check(r"\b200\b|batch", labelled(first, "next") + first),
        "next_pick": check(
            r"tenant|pick|chose|choice|chosen|answer", labelled(first, "next")
        ),
    }
    page = run.work / "page"
    state = page_state(run, page)
    if not state:
        return out
    active = page / state["active"]["file"]
    html = active.read_text()
    batch = re.search(r'id="batch-size"[^>]*>(.*?)</p>', html, re.DOTALL)
    events = page_events(page)
    batch_comment = next(
        e["id"]
        for e in events
        if e.get("kind") == "comment" and e["anchor"]["section"] == "batch-size"
    )
    out |= {
        "versions": len(state.get("versions", [])),
        "source_valid": not (state.get("source") or {}).get("error"),
        "batch_200": bool(batch and re.search(r"\b200\b", batch[1])),
        "batch_in_place": batch is not None,
        "chosen_marked": bool(
            re.search(r'<lf-option[^>]*id="opt-per-tenant"[^>]*\bchosen', html)
            or re.search(r'<lf-option[^>]*\bchosen[^>]*id="opt-per-tenant"', html)
        ),
        "pick_standing": any(
            s.get("widget") == "rollout"
            and s.get("detail", {}).get("options") == ["opt-per-tenant"]
            for s in state.get("state", [])
        ),
        "no_restated": "restated" not in html,
        "replied": any(
            e.get("kind") == "reply"
            and e.get("author") == "agent"
            and e.get("parent") == batch_comment
            for e in events
        ),
        "date_final": (
            re.search(r'id="cutover-date"[^>]*>(.*?)</p>', html, re.DOTALL)
            or [None, ""]
        )[1],
    }
    return out


def active_html(run: Run, page: Path) -> tuple[dict, str]:
    """The page's state and the HTML of its active revision."""
    state = page_state(run, page)
    return state, (page / state["active"]["file"]).read_text() if state else ""


def element_html(html: str, element: str) -> str:
    """The markup of the element with id `element`, up to its first closing tag of
    the same name."""
    found = re.search(
        rf'<(\w[\w-]*)\b[^>]*\bid="{element}"[^>]*>.*?</\1>', html, re.DOTALL
    )
    return found[0] if found else ""


def element_text(html: str, element: str) -> str:
    """The text of the element with id `element`, as `text` reads it."""
    return text(element_html(html, element))


def text(markup: str) -> str:
    """Markup's text: tags dropped, entities decoded and space collapsed."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", markup)).split())


# A tool call that writes `index.html`: the Write or Edit tool, a shell redirect or
# in-place edit, or a script fed through a heredoc that names the file.
WRITES_PAGE = (
    r"^(Write|Edit)\b.*index\.html|>\s*\S*index\.html|sed -i.*index\.html"
    r"|(?s:<<.*index\.html|index\.html.*<<)"
)


def score_package(run: Run, trace: list[dict]) -> dict:
    """The widget used from its registry entry, with the contract's values."""
    ran = [c for record in trace for c in commands(record)]
    wrote = next((i for i, c in enumerate(ran) if re.search(WRITES_PAGE, c)), len(ran))
    out = {
        # The markup comes from the entry: read before the first write that uses it,
        # with no look at the widget's source before that write.
        "entry_read": any("registry.json" in c for c in ran[:wrote]),
        "source_unread": not any(
            re.search(r"lf-burn\.js|packages/slo", c) for c in ran[:wrote]
        ),
    }
    page = run.work / "page"
    state, html = active_html(run, page)
    if not state or len(state["versions"]) < 2:
        return out | {"stamped": False}
    burn = re.search(r"<lf-burn\b([^>]*)>", element_html(html, "checkout"))
    attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', burn[1])) if burn else {}
    return out | {
        "stamped": True,
        "valid": run.leaf("page", "check", str(page)).returncode == 0,
        "widget_used": burn is not None,
        "objective": attrs.get("objective") == "99.9",
        "window": attrs.get("window") == "28d",
        "consumed": attrs.get("consumed") in ("0.62", ".62"),
    }


def score_shared_source(run: Run, traces: list[list[dict]], replies: list[str]) -> dict:
    """Each widget's record read and edited through its authored id, and nothing
    else in the snapshot touched."""
    lines = answered_lines(replies[0] if replies else "")
    out = {
        # The first branch the answer names is finch's; it may go on to name the
        # stale record's.
        "finch_branch": (
            re.findall(r"cdata-escapes(-v1)?", lines.get(1, "")) or ["missing"]
        )[0]
        == "",
        "finch_failing": check(r"fail|not passing|no\b", lines.get(1, "")),
        "wren_ahead": check(r"\b4\b|\bfour\b", lines.get(2, "")),
        # The join from widget to record came from the declarations: no look at
        # the renderer in either phase.
        "source_unread": not any(
            "lf-worktree.js" in c for t in traces for d in t for c in commands(d)
        ),
    }
    page = run.work / "page"
    before = json.loads((FIXTURES / "hub-worktrees.json").read_text())
    after = json.loads((page / "data/project-worktrees.json").read_text())
    finch = after.get("tree-finch", {})
    html = (page / "index.html").read_text()
    return out | {
        "finch_updated": finch.get("head", "").startswith("3f0a6be")
        and finch.get("ahead") == 7
        and finch.get("tests") == "passing",
        "others_kept": {k: after.get(k) for k in ("tree-finch-old", "tree-wren")}
        == {k: before[k] for k in ("tree-finch-old", "tree-wren")},
        "markup_kept": "3f0a6be" not in html
        and html.count('source="project-worktrees"') == 2,
        "source_valid": not page_state(run, page).get("source", {}).get("error"),
    }


def live_rounds(trace: list[dict]) -> list[dict]:
    """Each posted round's confirmed-input window and completed response turn.

    The driver emits eval_received only after admitted attention inputs have
    opened pickups. A window begins at the post so it includes the ACK and claim
    operations whose tool result first lets the driver observe that receipt.
    Hook output text does not prove receipt on either inline or pointer routes.
    """
    rounds = []
    for n, post in enumerate(
        i for i, d in enumerate(trace) if d["type"] == "eval_post"
    ):
        received = next(
            (
                i
                for i in range(post, len(trace))
                if trace[i]["type"] == "eval_received" and trace[i]["round"] == n + 1
            ),
            None,
        )
        end = (
            next(
                (
                    i
                    for i in range(received, len(trace))
                    if trace[i]["type"] == "result"
                ),
                None,
            )
            if received is not None
            else None
        )
        rounds.append(
            {
                "round": n + 1,
                "post": post,
                "delivery": post if received is not None else None,
                "end": end,
                "status": end is not None
                and next(
                    (d["status"] for d in trace[end:] if d["type"] == "eval_status"),
                    None,
                ),
            }
        )
    return rounds


def ran_between(trace: list[dict], start: int, end: int) -> list[str]:
    return [c for record in trace[start:end] for c in commands(record)]


def claimed_first(trace: list[dict], thread: str) -> bool:
    """An accepted claim for this thread before the turn's first reply call."""
    reply = next(
        (
            index
            for index, record in enumerate(trace)
            if any(re.search(r"\bthread reply\b", c) for c in commands(record))
        ),
        len(trace),
    )
    return any(
        index < reply for index in accepted_thread_claims(trace, thread).values()
    )


def answered(events: list[dict], event_id: str) -> list[dict]:
    """The agent's replies to one event."""
    return [
        e
        for e in events
        if e["kind"] == "reply"
        and e["author"] == "agent"
        and event_id in (e.get("parent"), e.get("responds"))
    ]


def round_scores(trace: list[dict], r: dict, name: str) -> dict:
    """Confirmed input, watch ownership left to Leaf, and a waiting handover URL."""
    if r["delivery"] is None or r["end"] is None:
        return {f"{name}_delivered": False}
    end = trace[r["end"]]
    return {
        f"{name}_delivered": True,
        f"{name}_watch_left_to_leaf": not any(
            waits_started(d) for d in trace[r["delivery"] : r["end"]]
        ),
        f"{name}_waiting": (r["status"] or {}).get("state") == "waiting",
        f"{name}_url": bool(URL.search(end.get("result") or "")),
    }


def score_handoff(run: Run, trace: list[dict]) -> dict:
    events = page_events(run.work / "page")
    first_end = next(
        (i for i, d in enumerate(trace) if d["type"] == "result"), len(trace)
    )
    handover = trace[first_end] if first_end < len(trace) else {}
    status = (
        next((d["status"] for d in trace if d["type"] == "eval_status"), None) or {}
    )
    out = {
        "served": bool(URL.search(handover.get("result") or "")),
        "checked": any("page check" in c for c in ran_between(trace, 0, first_end)),
        "handoff_waiting": status.get("state") == "waiting",
        "detail_names_ask": check(
            r"cop(y|ies)|backfill|approach|option|how .*run", status.get("detail") or ""
        ),
        "watch_left_to_leaf": not any(waits_started(d) for d in trace[:first_end]),
        "gesture_named": check(
            r"\b(pick|choose|select|click)", handover.get("result") or ""
        ),
    }
    rounds = live_rounds(trace)
    if rounds:
        r = rounds[0]
        comment = posted_event(run.work / "page", attempt_key(0, 0))
        _, html = active_html(run, run.work / "page")
        out |= round_scores(trace, r, "edit") | {
            "edit_claimed": r["delivery"] is not None
            and r["end"] is not None
            and claimed_first(trace[r["delivery"] : r["end"]], comment["id"]),
            "edit_replied": bool(answered(events, comment["id"])),
            "edit_done": check(DRY_RUN_DONE, element_text(html, "dry-run")),
        }
    if len(rounds) > 1:
        question = posted_event(run.work / "page", attempt_key(1, 0))
        replies = answered(events, question["id"])
        out |= round_scores(trace, rounds[1], "question") | {
            "question_answered": any(
                check(r"snapshot", e.get("text", ""))
                and check(r"\b40\b", e.get("text", ""))
                for e in replies
            ),
        }
    return out


def score_mixed(run: Run, trace: list[dict]) -> dict:
    page = run.work / "page"
    events = page_events(page)
    rounds = live_rounds(trace)
    if not rounds:
        return {"batch_delivered": False}
    r = rounds[0]
    # The error carries no retry key, as the runtime sends none.
    posted = [posted_event(page, attempt_key(0, i)) for i in range(5)]
    comment, pick, reaction, _, _ = posted
    inputs = {e["id"] for e in posted if e["attention"]}
    receipts = [
        e
        for e in events
        if e["kind"] == "pickup"
        and e["phase"] == "opened"
        and inputs.intersection(e["events"])
    ]
    fixture_words = len(
        element_text((FIXTURES / "mixed.html").read_text(), "why-now").split()
    )
    state, html = active_html(run, page)
    out = round_scores(trace, r, "batch") | {
        # One confirmed batch carries every admitted attention input; quiet
        # reactions and local moves neither require nor create reader receipts.
        "one_delivery": r["delivery"] is not None
        and len(receipts) == 1
        and inputs_received(events, {e["attempt"] for e in posted}),
        "comment_claimed": r["delivery"] is not None
        and r["end"] is not None
        and claimed_first(trace[r["delivery"] : r["end"]], comment["id"]),
        "comment_replied": bool(answered(events, comment["id"])),
        "comment_done": check(DRY_RUN_DONE, element_text(html, "dry-run")),
        "stamped": len(state.get("versions", [])) >= 2,
        # Leaf's own reading: the pick owes nothing more, and the user still sees it,
        # as the markup's `chosen` or as their standing move.
        "pick_answered": not any(
            w.get("input") == pick["id"] for w in state.get("workflows", [])
        )
        and (
            bool(re.search(r'<lf-option\b[^>]*\bid="opt-online"[^>]*\bchosen', html))
            or any(
                s["widget"] == "copy-mode" and s["detail"] == PICK["detail"]
                for s in state.get("state", [])
            )
        ),
        # The reaction is acted on, by shortening the paragraph in place or by
        # proposing a shorter one as a suggestion, and closed, by the agent or by the
        # suggestion that `resolves` it once the user decides.
        "reaction_handled": (
            0 < len(element_text(html, "why-now").split()) < 0.7 * fixture_words
            or any(
                "every dashboard that reads" in text(old)
                and len(text(new).split()) < 0.7 * fixture_words
                for old, new in re.findall(
                    r"<lf-old\b.*?>(.*?)</lf-old\s*>\s*<lf-new\b.*?>(.*?)</lf-new\s*>",
                    html,
                    re.DOTALL,
                )
            )
        )
        and (
            any(
                e["kind"] == "resolve"
                and e["author"] == "agent"
                and e["parent"] == reaction["id"]
                for e in events
            )
            or f'resolves="{reaction["id"]}"' in html
        ),
        "reaction_unreplied": not answered(events, reaction["id"]),
        "undo_kept": "card-lag-alert" in column_cards(html, "col-open")
        and column_cards(html, "col-done") == [],
        # Every regular expression the page's script passes to replaceAll is global.
        "error_fixed": all(
            "g" in flags
            for flags in re.findall(r"replaceAll\(\s*/(?:[^/\\\n]|\\.)+/([a-z]*)", html)
        ),
    }
    return out


PREMISE = "the vacuum job now owns the ops window"


def score_elided(run: Run, trace: list[dict]) -> dict:
    page = run.work / "page"
    events = page_events(page)
    rounds = live_rounds(trace)
    if not rounds:
        return {"question_delivered": False}
    r = rounds[0]
    question = posted_event(page, attempt_key(0, 0))
    thread = next(e["id"] for e in events if e["kind"] == "comment")
    out = round_scores(trace, r, "question")
    if r["delivery"] is None:
        return out
    delivery = trace[r["delivery"]].get("output", "")
    replying = next(
        (
            i
            for i in range(r["delivery"], len(trace))
            if any("thread reply" in c for c in commands(trace[i]))
        ),
        len(trace),
    )
    # Where the premise first reached the agent: a tool result carrying its words,
    # which the delivery leaves out. The agent can write them nowhere before that.
    premise = next(
        (
            i
            for i, d in enumerate(trace)
            if any(
                b.get("type") == "tool_result" and PREMISE in text_of(b.get("content"))
                for b in blocks([d])
            )
        ),
        None,
    )
    replies = answered(events, question["id"])
    return out | {
        # Validity: the delivery shortened the thread, as the case assumes.
        "shown_elided": bool(
            re.search(r'\\?"elided\\?":\s*\{\\?"messages\\?":\s*[1-9]', delivery)
        )
        and PREMISE not in delivery,
        "middle_read": premise is not None and r["post"] < premise < replying,
        "premise_read_in": None
        if premise is None
        else "resume"
        if premise < r["post"]
        else "delivery",
        "answer_right": any(
            check(r"\b22[:.]?00\b|\b10\s*p\.?m\b", e.get("text", "")) for e in replies
        ),
        "titled": any(
            e["kind"] == "thread_title" and e.get("thread") == thread for e in events
        ),
        "summarized": any(
            e["kind"] == "summary" and e.get("thread") == thread for e in events
        ),
    }


LIVE_SCORES = {"handoff": score_handoff, "mixed": score_mixed, "elided": score_elided}

# These declarations remain complete when a scorer exits early or a round never
# arrives. Missing observations fail instead of silently shrinking the assertion set.
CHECKS = {
    "cold-report": (
        "leaf_skill",
        "one_page",
        "valid",
        "agent_checked",
        "unstamped",
        "not_served",
        "no_ask",
        "no_sign_off",
    ),
    "cold-decision": (
        "leaf_skill",
        "one_page",
        "valid",
        "agent_checked",
        "not_served",
        "one_ask",
        "one_choice_group",
        "three_options",
        "single_choice",
        "no_sign_off",
        "names_gesture",
    ),
    "near-miss": ("no_page", "leaf_skill_quiet"),
    "resume": (
        "date",
        "approach",
        "next_batch",
        "next_pick",
        "stamped",
        "source_valid",
        "batch_200",
        "batch_in_place",
        "chosen_marked",
        "pick_standing",
        "no_restated",
        "replied",
    ),
    "constructs": (
        "draft_read",
        "p95_read",
        "chart_read",
        "stamped",
        "draft_date",
        "draft_kept_user_words",
        "draft_restated",
        "p95_text",
        "p95_current",
        "source_kept",
        "chart_85",
    ),
    "board": (
        "doing_read",
        "undo_read",
        "stamped",
        "doing_order",
        "todo_kept",
        "done_empty",
        "renamed",
        "no_restated",
    ),
    "package": (
        "entry_read",
        "source_unread",
        "stamped",
        "valid",
        "widget_used",
        "objective",
        "window",
        "consumed",
    ),
    "shared-source": (
        "finch_branch",
        "finch_failing",
        "wren_ahead",
        "source_unread",
        "finch_updated",
        "others_kept",
        "markup_kept",
        "source_valid",
    ),
    "handoff": (
        "served",
        "checked",
        "handoff_waiting",
        "detail_names_ask",
        "watch_left_to_leaf",
        "gesture_named",
        "edit_delivered",
        "edit_watch_left_to_leaf",
        "edit_waiting",
        "edit_url",
        "edit_claimed",
        "edit_replied",
        "edit_done",
        "question_delivered",
        "question_watch_left_to_leaf",
        "question_waiting",
        "question_url",
        "question_answered",
    ),
    "mixed": (
        "batch_delivered",
        "batch_watch_left_to_leaf",
        "batch_waiting",
        "batch_url",
        "one_delivery",
        "comment_claimed",
        "comment_replied",
        "comment_done",
        "stamped",
        "pick_answered",
        "reaction_handled",
        "reaction_unreplied",
        "undo_kept",
        "error_fixed",
    ),
    "elided": (
        "question_delivered",
        "question_watch_left_to_leaf",
        "question_waiting",
        "question_url",
        "shown_elided",
        "middle_read",
        "answer_right",
        "titled",
        "summarized",
    ),
}


def expected_checks(case: str) -> list[str]:
    """The fixed assertion set for one complete scenario."""
    CASES[case]
    if case.startswith("reading"):
        surface = case.removeprefix("reading").removeprefix("-") or None
        checks = [
            f"answer_{q['surface']}"
            for q in ANSWERS["questions"]
            if surface is None or q["surface"] == surface
        ]
    else:
        checks = list(CHECKS[case])
    return ["completed", *checks]


def checks_for(case: str, score: dict, phases: list[dict], usable: bool) -> dict:
    """Turn scored observations into every declared boolean, including absences."""
    values = dict(score)
    if case in COLD:
        skill = any(p["leaf_skill"] for p in phases)
        if phases:
            values |= {"leaf_skill": skill, "leaf_skill_quiet": not skill}
        if "pages" in score:
            values |= {"one_page": score["pages"] == 1, "no_page": score["pages"] == 0}
        for name, field, count in (
            ("unstamped", "stamped", 0),
            ("no_ask", "asks", 0),
            ("one_ask", "asks", 1),
            ("one_choice_group", "choose_groups", 1),
            ("three_options", "options", 3),
        ):
            if field in score:
                values[name] = score[field] == count
    elif case.startswith("reading"):
        values |= {
            f"answer_{name}": passed
            for name, passed in score.get("answers", {}).items()
        }
    elif case == "resume":
        values["stamped"] = score.get("versions", 0) >= 3
    return {
        name: usable if name == "completed" else values.get(name) is True
        for name in expected_checks(case)
    }


def score_run(
    run: Run, traces: list[list[dict]], replies: list[str], calls: list[str]
) -> dict:
    """Apply the scenario's semantic reading to its complete native trajectory."""
    if run.case in LIVE_SCORES:
        return LIVE_SCORES[run.case](run, traces[0])
    if run.case == "package":
        return score_package(run, traces[0])
    if run.case == "shared-source":
        return score_shared_source(run, traces, replies)
    if run.case in COLD:
        return score_cold(run, replies[-1] if replies else "", calls)
    if run.case.startswith("reading"):
        return score_reading(run, replies[-1] if replies else "")
    if run.case == "board":
        return score_board(run, replies)
    if run.case == "constructs":
        return score_constructs(run, replies)
    return score_resume(run, replies)


def execute_scenario(case: str, payload: Path, work: Path) -> dict:
    """One Promptfoo provider call owns all phases, live rounds, and evidence."""
    run = Run(case, payload, work)
    execute(run)
    traces = run.traces()
    phases = [trace_scores(t) for t in traces]
    replies = [p["reply"] for p in phases]
    calls = [c for p in phases for c in p["calls"]]
    usable = run.usable()
    score = score_run(run, traces, replies, calls) if usable else {}
    checks = checks_for(case, score, phases, usable)
    return {
        "output": "\n\n".join(replies),
        "cost": sum(p["cost_usd"] for p in phases),
        "tokenUsage": {
            "prompt": sum(p["input_tokens"] for p in phases),
            "completion": sum(p["output_tokens"] for p in phases),
        },
        "metadata": {
            "checks": checks,
            "diagnostics": {"score": score, "phases": phases, "work": str(work)},
        },
    }
