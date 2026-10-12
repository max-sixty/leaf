"""Whole agent usability trajectories, scored by Promptfoo.

Each provider call owns one isolated scenario, including its resumed phases or
live user rounds. Promptfoo owns arms, repetition, concurrency, and reporting;
this module owns fixtures, execution, and what each scenario scores. Evidence
stays in the supplied work directory, and the agent cwd stays outside any repo.

A fact the page states is read the way Leaf reads it: decisions, asks and
workflows from `leaf page state`, markup through Leaf's own parse
(`SourceDocument`, and `SourceReading` for the words an element says). What the
agent says, in a reply or in prose it wrote onto the page, is judged by meaning
through an `llm-rubric` (`JUDGED`), never matched against a pattern. Only the
native trace, the commands the agent ran and the deliveries it was handed, is
matched as text, since it records nothing richer.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from leaf.delivery import DELIVERY_FORMAT, opened_input_ids, pickup_receipts
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.passages import SourceReading, collapse
from leaf.schema import MESSAGE_KINDS
from leaf.service import requires_agent_attention
from leaf.structure import SourceDocument
from leaf.thread import successful_replies
from playwright.sync_api import Browser
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT
from leaf_dev.arms import (
    TURN_LIMIT,
    URL,
    LiveChild,
    PageClient,
    blocks,
    commands,
    completed,
    environment,
    inputs_received,
    now,
    observed_sum,
    progress_start,
    read_page_state,
    read_trace,
    resumed,
    run_agent,
    run_leaf,
    scratch,
    serving,
    trace_result,
    trace_summary,
    waits_started,
)
from leaf_dev.browser import chrome, load, tab

FIXTURES = ROOT / "evals/usability/fixtures"
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
    {"unit": "card-docs", "value": "col-doing", "rank": "0i"},
    {"unit": "card-audit", "value": "col-doing", "rank": "1i"},
    {"unit": "card-rotate", "value": "col-done", "rank": "1"},
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
    "detail": {"value": ["opt-online"]},
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
    "detail": {"unit": "card-lag-alert", "value": "col-done", "rank": "1"},
}
# The edit the `DRY_RUN` comment asks for, as the judge reads the edited paragraph.
DRY_RUN_DONE = "The paragraph says the dry run took 3 hours 10 minutes."
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
    injection: tuple[str, ...] = ()


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
    harness: str = ClaudeCodeHarness.name

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


def arm_fixture(run: Run, action: str, *args: str) -> None:
    """Run the fixture module with the selected arm's Leaf and isolated state."""
    subprocess.run(
        [
            "uv",
            "run",
            "-q",
            "--no-dev",
            "--project",
            str(run.payload),
            "--with",
            str(ROOT / "dev"),
            "python",
            "-m",
            "leaf_dev.usability_fixture",
            action,
            *args,
        ],
        check=True,
        env=environment(XDG_STATE_HOME=str(run.state)),
    )


def admit(run: Run, page: Path, event: dict) -> None:
    """Admit one user move through the arm's browser door."""
    arm_fixture(run, "admit", str(page), json.dumps(event))


def page_events(page: Path) -> list[dict]:
    return read_events(page)


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


def said(html: str) -> dict[str, str]:
    """id → the words the element says, in Leaf's own reading of the markup: the
    text a user selects and an anchor quotes."""
    reading = SourceReading(SourceDocument(html), None)
    return {element: spoken.words for element, spoken in reading.spoken.items()}


def anchor(html: str, element: str, quote: str) -> dict:
    """A comment anchor on `quote` inside the element with id `element`."""
    text = said(html)[element]
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
    arm_fixture(
        run,
        "answer",
        str(page),
        rerun,
        "Reran it on 18 September after the mapping change: 4.3 million documents in 3 h 05 min. The page shows the new figure.",
    )
    run.leaf(
        "status", str(page), "waiting", "Pick how traffic moves to the new index",
        check=True,
    )  # fmt: skip
    admit(run, page, {"kind": "resolve", "parent": rerun})
    admit(run, page, {
        "kind": "action", "revision": 2, "widget": "rollout", "action": "choose",
        "detail": {'value': ["opt-per-tenant"]},
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
    receipt = json.loads(measured)["run"]
    (page / "index.html").write_text(
        re.sub(r'\brun="[^"]*"', f'run="{receipt}"', template)
    )
    run.leaf("page", "stamp", str(page), "--text", "Release 4.2 review", check=True)
    run.leaf("status", str(page), "waiting", "Edit the release note", check=True)
    admit(run, page, {
        "kind": "action", "revision": 1, "widget": "release-note", "action": "edit",
        "detail": {'value': CONSTRUCTS_DRAFT},
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
    run.leaf(
        "page",
        "init",
        "--package",
        "./" + os.path.relpath(ROOT / "examples/command-hub.page", Path.cwd()),
        str(page),
        check=True,
    )
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
    as the CLI and hooks, under their one transaction lease.
    """
    state, document = active_document(run, page)
    arm_fixture(
        run,
        "history",
        str(page),
        json.dumps(
            [
                ELIDED_THREAD,
                anchor(document.html, "window", "in the maintenance window"),
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


def execute(run: Run, work: Path) -> None:
    """One run: build the case's fixture, then run each phase, resuming the first
    phase's session, or the live session. The caller keeps `work` alive through
    scoring; this function archives pages before returning or raising."""
    case = CASES[run.case]
    run.state.mkdir(parents=True)
    (run.dir / "work-dir").write_text(f"{work}\n")
    page = work / "page"
    try:
        if case.fixture:
            build_fixture(run, case.fixture, page)
            shutil.copytree(page, run.dir / "fixture", ignore=ignore)
        if case.rounds:
            execute_live(run, case, work, page)
        else:
            execute_phases(run, case, work, page)
    finally:
        for found in pages(work, run.state):
            shutil.copytree(found, run.dir / "pages" / found.name, ignore=ignore)


# How long a finished session stays open for a trailing turn.
GRACE = 20


def execute_live(run: Run, case: Case, work: Path, page: Path) -> None:
    """Serve the case's page from a live session and play its user.

    Each round retains its admitted inputs until delivery is confirmed. The next
    round goes out at a turn's end, or during work for a declared running injection.
    An idle injection pauses so Leaf's watcher can take its lease. The session closes
    once the last round's turn ends or the session reaches TURN_LIMIT. Each turn's
    end records the page's status."""
    prompt = case.prompts[0].replace("{page}", str(page))
    (run.dir / "prompt-1.txt").write_text(prompt)
    closing: threading.Timer | None = None
    url, posted, delivered = None, 0, 0
    observed_tool_round = 0
    pending_events: set[str] = set()
    attempts: set[str] = set()
    try:
        with (
            LiveChild(
                work,
                prompt,
                "--plugin-dir",
                str(run.payload),
                stderr=run.dir / "err-1.txt",
                limit=TURN_LIMIT,
                timed_out=run.dir / "timed-out",
                dirs=[run.payload],
                env={"XDG_STATE_HOME": str(run.state)},
                harness=run.harness,
            ) as child,
            (run.dir / "stream-1.jsonl").open("w") as stream,
            ExitStack() as deadlines,
        ):

            def note(record: dict) -> None:
                stream.write(json.dumps(record) + "\n")
                stream.flush()

            for record in child.records():
                if delivered < posted:
                    events = page_events(page)
                    if inputs_received(
                        events, attempts
                    ) and pending_events <= opened_input_ids(events):
                        delivered = posted
                        note(
                            {
                                "type": "eval_received",
                                "round": posted,
                                "events": sorted(pending_events),
                                "received_at": now(),
                            }
                        )
                note(record)
                if delivered > observed_tool_round and any(
                    block.get("type") == "tool_use" for block in blocks([record])
                ):
                    observed_tool_round = delivered
                    note(
                        {
                            "type": "eval_first_tool_state",
                            "round": delivered,
                            "workflows": page_state(run, page)["workflows"],
                            "received_at": now(),
                        }
                    )
                if not url and record.get("type") in ("user", "result"):
                    server = page_state(run, page)["server"]
                    if server:
                        url = server["url"]
                        note({"type": "eval_served", "url": url, "received_at": now()})
                if record.get("type") == "result":
                    state = page_state(run, page)
                    note(
                        {
                            "type": "eval_status",
                            "status": state.get("status"),
                            "listening": state["listening"],
                            "received_at": now(),
                        }
                    )
                # Posting the next running round cannot replace an undelivered
                # round's evidence.
                if delivered < posted:
                    continue
                if not url or posted == len(case.rounds):
                    if record.get("type") == "result":
                        if closing is not None:
                            closing.cancel()
                        closing = threading.Timer(GRACE, child.close)
                        deadlines.callback(closing.join)
                        deadlines.callback(closing.cancel)
                        closing.start()
                    continue
                injection = "idle" if record.get("type") == "result" else "running"
                if (
                    injection == "running"
                    and (case.injection[posted] if case.injection else "idle")
                    != "running"
                ):
                    continue
                if injection == "idle":
                    time.sleep(3)
                active_turn = observed_active_turn(run, page, child)
                if run.case == "elided" and posted == 0:
                    append_elided_history(run, page)
                pending_events = post_round(
                    run, page, PageClient(url), case.rounds[posted], posted
                )
                attempts.update(
                    move.get("attempt", attempt_key(posted, i))
                    for i, move in enumerate(case.rounds[posted])
                    if move["kind"] != "error"
                )
                posted += 1
                note(
                    {
                        "type": "eval_post",
                        "round": posted,
                        "injection": injection,
                        "events": sorted(pending_events),
                        "active_turn": active_turn,
                        "received_at": now(),
                    }
                )
    finally:
        if closing is not None:
            closing.cancel()
        run.leaf("server", "stop", str(page))


def observed_active_turn(run: Run, page: Path, child) -> str | None:
    """Read the arm's canonical claimant turn inside this run's isolated home.

    Claim enrichment joins its session lifecycle, which lives in the same state
    home. The native Codex parent turn must also still run at the injection edge.
    """
    state = page_state(run, page)
    turn = state["claim_turn"] if state["turn_closed"] is None else None
    if run.harness == "codex" and turn not in child.task.running:
        return None
    return turn


def post_round(
    run: Run, page: Path, client: PageClient, moves: tuple[dict, ...], n: int
) -> set[str]:
    """Post one round's moves as the user's tab would, resolving each placeholder
    against the page as it is served now. Return the admitted attention-bearing
    identities, including the page's native error rather than giving it a retry key."""
    admitted = []
    served = page_state(run, page)
    html = (page / served["active"]["file"]).read_text()
    for i, move in enumerate(moves):
        event = dict(move)
        if move["kind"] != "error":
            event["attempt"] = move.get("attempt", attempt_key(n, i))
        if "anchor" in move and not isinstance(move["anchor"], dict):
            event["anchor"] = anchor(html, *move["anchor"])
        if move.get("undoes") == "previous":
            event["undoes"] = posted_event(page, attempt_key(n, i - 1))["id"]
        if move.get("parent") == "latest":
            event["parent"] = [
                e for e in page_events(page) if e["kind"] in MESSAGE_KINDS
            ][-1]["id"]
        if "text" in move:
            event["text"] = move["text"].format(
                origin=client.origin,
                line=html[: html.find("replaceAll(")].count("\n") + 1,
            )
        if move["kind"] != "undo":
            event["revision"] = served["active"]["revision"]
        before = {e["id"] for e in page_events(page)}
        client.post(event)
        if event["kind"] == "error":
            admitted.append(
                next(
                    e
                    for e in page_events(page)
                    if e["id"] not in before
                    and e["kind"] == "error"
                    and e["text"] == event["text"]
                )
            )
        else:
            admitted.append(posted_event(page, event["attempt"]))
    return {e["id"] for e in admitted if requires_agent_attention(e)}


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
        trace = run_agent(
            work,
            prompt,
            "--plugin-dir",
            str(run.payload),
            *(("--resume", session) if session else ()),
            out=run.dir / f"stream-{phase}.jsonl",
            err=run.dir / f"err-{phase}.txt",
            dirs=[run.payload],
            env={"XDG_STATE_HOME": str(run.state)},
            harness=run.harness,
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


def text_of(content) -> str:
    return content if isinstance(content, str) else json.dumps(content)


def trace_scores(trace: list[dict]) -> dict:
    calls, results = {}, {}
    for block in blocks(trace):
        if block.get("type") == "tool_use":
            calls[block["id"]] = block
        elif block.get("type") == "tool_result":
            results[block["tool_use_id"]] = block
    skills = [
        c["input"].get("skill", "") for c in calls.values() if c["name"] == "Skill"
    ]
    return {
        **trace_summary(trace),
        "leaf_skill": any("leaf" in s for s in skills)
        or any(
            "skills/leaf/SKILL.md" in json.dumps(c["input"])
            and results.get(cid, {}).get("is_error") is False
            for cid, c in calls.items()
        ),
        "calls": [command for record in trace for command in commands(record)],
    }


def page_state(run: Run, page: Path) -> dict:
    return read_page_state(run.payload, run.state, page)


def active_document(run: Run, page: Path) -> tuple[dict, SourceDocument]:
    """The page's state and Leaf's parse of the markup it serves: the active
    revision's, or `index.html` before a first stamp."""
    state = page_state(run, page)
    active = state.get("active") or {"file": "index.html"}
    return state, SourceDocument((page / active["file"]).read_text())


def column_cards(document: SourceDocument, column: str) -> list[str]:
    return [card.attrs.get("id") for card in document.tree.select(f"#{column} lf-card")]


def score_cold(run: Run, calls: list[str]) -> dict:
    found = pages(run.work, run.state)
    out = {"pages": len(found)}
    if run.case == "near-miss" or not found:
        return out
    page = found[0]
    checked = run.leaf("page", "check", str(page))
    state, document = active_document(run, page)
    tags = [record["tag"] for record in document.lf_elements]
    groups = [r["attrs"] for r in document.lf_elements if r["tag"] == "lf-options"]
    return out | {
        "valid": checked.returncode == 0,
        "agent_checked": any("page check" in c for c in calls),
        "stamped": len(state.get("versions", [])),
        "not_served": not any(re.search(r"\bserver (start|run)\b", c) for c in calls),
        "status": (state.get("status") or {}).get("state"),
        "asks": tags.count("lf-ask"),
        "choose_groups": sum("choose" in attrs for attrs in groups),
        "options": tags.count("lf-option"),
        "single_choice": not any("multiple" in attrs for attrs in groups),
        "no_sign_off": not any(
            meta["name"] == "lf-review" and meta["content"] == "sign-off"
            for meta in document.named_metas
        ),
    }


def reading_questions(case: str) -> list[dict]:
    surface = case.removeprefix("reading").removeprefix("-") or None
    return [
        q for q in ANSWERS["questions"] if surface is None or q["surface"] == surface
    ]


GESTURE = (
    "The message tells the user how to make the decision on the page: by picking, "
    "choosing or selecting one of its options."
)

# What each scenario judges by meaning: text → metric → passing reading. The text
# names an entry of the response's `metadata.texts`; `reply-N` is phase N's final
# message, and a scorer adds what it read off the page or the log. The judge reads
# that text alone, so each criterion stands without the scenario around it.
JUDGED = {
    "cold-decision": {"reply-1": {"names_gesture": GESTURE}},
    "resume": {
        "reply-1": {
            "date": "The message reports 21 October as the cutover date the page "
            "currently shows. Reporting 3 November as the current date fails; "
            "mentioning it as an unsaved or proposed change is fine.",
            "approach": "The message says traffic moves to the new index tenant by "
            "tenant, in groups of tenants.",
            "next_batch": "Among what needs doing next, the message includes the "
            "request to drop the batch size from 500 to 200.",
            "next_pick": "Among what needs doing next, the message includes taking in "
            "the user's pick of the tenant-by-tenant approach, such as marking it "
            "chosen on the page. Treating how traffic moves as still undecided fails.",
        },
    },
    "constructs": {
        "reply-1": {
            "draft_read": 'Answer 1, to "What does the release note say?", gives '
            "the note as the user edited it, which says merchants need no code "
            "changes.",
            "p95_read": 'Answer 2, to "What p95 does the latency sentence state, and '
            'what is the latest measurement?", says the sentence states 184 ms and '
            "the latest measurement is 231 ms.",
            "chart_read": 'Answer 3, to "Which region has the most errors in the '
            'chart?", is us-east.',
        },
        "release-note": {
            "draft_date": "The release note gives the rollout start as 19 November "
            "and does not say 12 November.",
            "draft_kept_user_words": "The release note says merchants need no code "
            "changes.",
        },
        "chart": {"chart_85": "In the data this chart plots, sa-east has 85 errors."},
    },
    "board": {
        "reply-1": {
            "doing_read": 'Answer 1, to "List the cards in the Doing column, top to '
            'bottom", is Update runbook, Inventory services, Audit key usage, Expiry '
            "alerts: those four cards in that order.",
            "undo_read": 'Answer 2, to "Which column is \\"Rotate signing keys\\" '
            'in?", is To do.',
        },
    },
    "shared-source": {
        "reply-1": {
            "finch_branch": "Answer 1, to which branch finch's worktree is on and "
            "whether its tests pass, gives the branch as finch/cdata-escapes. Giving "
            "finch/cdata-escapes-v1 fails.",
            "finch_failing": "Answer 1, to which branch finch's worktree is on and "
            "whether its tests pass, says its tests are failing.",
            "wren_ahead": "Answer 2, to how many commits ahead of its base wren's "
            "worktree is, is 4.",
        },
    },
    "handoff": {
        "status": {
            "detail_names_ask": "This status, shown while the page waits on the user, "
            "says what it waits for: their choice of how the backfill copy runs.",
        },
        "handover": {"gesture_named": GESTURE},
        "dry-run": {"edit_done": DRY_RUN_DONE},
        "answers": {
            "question_answered": "The answer says the snapshot restore option needs a "
            "write freeze, and that the freeze lasts 40 minutes.",
        },
    },
    "mixed": {"dry-run": {"comment_done": DRY_RUN_DONE}},
    "elided": {
        "answers": {
            "answer_right": "The answer says the copy starts at 22:00 UTC each night. "
            "Answering 01:00 UTC fails.",
        },
    },
}


def rubrics(case: str) -> list[dict]:
    """Promptfoo `llm-rubric`s: each reading question's answer, and each judged text
    of a scenario."""
    if case.startswith("reading"):
        return [
            {
                "type": "llm-rubric",
                "metric": f"answer_{q['surface']}",
                "value": f"Question {n}: {q['question']}\n"
                f"Expected answer: {q['answer']}\n"
                "Pass only if the answer to this question conveys the expected "
                "meaning. Equivalent wording is fine; contradicting the expected "
                "answer fails, even when its words occur in the reply."
                + (
                    " For viewer state, acknowledge uncertainty and do not identify a "
                    "currently open tab."
                    if q["surface"] == "view"
                    else ""
                ),
            }
            for n, q in enumerate(reading_questions(case), 1)
        ]
    return [
        {
            "type": "llm-rubric",
            "metric": metric,
            "value": criterion,
            # A text the run never produced reaches the judge empty, and fails.
            "transform": f"context.metadata.texts?.[{json.dumps(text)}] ?? ''",
        }
        for text, criteria in JUDGED.get(case, {}).items()
        for metric, criterion in criteria.items()
    ]


def score_constructs(run: Run) -> dict:
    page = run.work / "page"
    state, document = active_document(run, page)
    if len(state["versions"]) < 2:
        return {"stamped": False}
    draft = document.by_id.get("release-note")
    standing = next(
        (s["detail"]["value"] for s in state["state"] if s["widget"] == "release-note"),
        None,
    )
    chart = document.by_id.get("region-errors")
    return {
        "stamped": True,
        "texts": {
            # What the user now reads: their edit where it still stands, else the
            # markup.
            "release-note": standing
            if standing is not None
            else (draft["body"] if draft else ""),
            "chart": chart["body"] if chart else "",
        },
        "draft_restated": "release-note" in document.restated,
        "p95_text": "231" in said(document.html).get("p95-figure", ""),
        "p95_current": state["measurement_lag"] == [],
        # The figure's owner is the markup; its source keeps the measurement.
        "source_kept": (page / "data/checkout-p95.json").read_bytes()
        == (run.dir / "fixture/data/checkout-p95.json").read_bytes(),
    }


def score_board(run: Run) -> dict:
    state, document = active_document(run, run.work / "page")
    if len(state["versions"]) < 2:
        return {"stamped": False}
    todo = column_cards(document, "col-todo")
    return {
        "stamped": True,
        "doing_order": column_cards(document, "col-doing") == BOARD_DOING,
        "todo_kept": todo[:1] == ["card-rotate"] and len(todo) == 2,
        "done_empty": column_cards(document, "col-done") == [],
        "renamed": "key expiry alerts"
        in said(document.html).get("card-alerts", "").lower(),
        "no_restated": not document.restated,
    }


def pick_owed(state: dict, pick: str) -> bool:
    """Whether the user's pick still waits on the agent to take it into the markup,
    in Leaf's own reading of the page's workflows."""
    return any(w["input"] == pick for w in state["workflows"])


def score_resume(run: Run) -> dict:
    page = run.work / "page"
    state, document = active_document(run, page)
    events = page_events(page)
    batch_comment = next(
        e["id"]
        for e in events
        if e.get("kind") == "comment" and e["anchor"]["section"] == "batch-size"
    )
    pick = next(e["id"] for e in events if e.get("widget") == "rollout")
    batch = said(document.html).get("batch-size")
    return {
        "versions": len(state["versions"]),
        "source_valid": not (state.get("source") or {}).get("error"),
        "batch_200": batch is not None and "200" in batch,
        "batch_in_place": batch is not None,
        "pick_taken_in": not pick_owed(state, pick),
        "pick_standing": any(
            s["widget"] == "rollout" and s["detail"]["value"] == ["opt-per-tenant"]
            for s in state["state"]
        ),
        "no_restated": not document.restated,
        "replied": bool(successful_replies(events, batch_comment)),
    }


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
    state, document = active_document(run, page)
    if len(state["versions"]) < 2:
        return out | {"stamped": False}
    burn = document.tree.select_one("#checkout lf-burn")
    attrs = burn.attrs if burn else {}
    return out | {
        "stamped": True,
        "valid": run.leaf("page", "check", str(page)).returncode == 0,
        "widget_used": burn is not None,
        "objective": attrs.get("objective") == "99.9",
        "window": attrs.get("window") == "28d",
        "consumed": attrs.get("consumed") in ("0.62", ".62"),
    }


def score_shared_source(run: Run, traces: list[list[dict]]) -> dict:
    """Each widget's record edited through its authored id, nothing else in the
    snapshot touched, and the renderer left unread."""
    page = run.work / "page"
    before = json.loads((FIXTURES / "hub-worktrees.json").read_text())
    after = json.loads((page / "data/project-worktrees.json").read_text())["value"]
    finch = after.get("tree-finch", {})
    # The working markup, stamped or not: a data update needs no new version.
    document = SourceDocument((page / "index.html").read_text())
    return {
        # The join from widget to record came from the declarations: no look at
        # the renderer in either phase.
        "source_unread": not any(
            "lf-atlas-tree.js" in c for t in traces for d in t for c in commands(d)
        ),
        "finch_updated": finch.get("head", "").startswith("3f0a6be")
        and finch.get("ahead") == 7
        and finch.get("tests") == "passing",
        "others_kept": {k: after.get(k) for k in ("tree-finch-old", "tree-wren")}
        == {k: before[k] for k in ("tree-finch-old", "tree-wren")},
        "markup_kept": "3f0a6be" not in document.html
        and len(document.tree.select('[source="project-worktrees"]')) == 2,
        "source_valid": not (page_state(run, page).get("source") or {}).get("error"),
    }


def live_rounds(trace: list[dict]) -> list[dict]:
    """Each posted round's confirmed-input window and completed response turn.

    The driver emits eval_received only after admitted attention inputs have
    opened pickups. A window begins at the post so it includes the ACK and claim
    operations whose tool result first lets the driver observe that receipt.
    Hook output text does not prove receipt on either inline or pointer deliveries.
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


def progress_shown(trace: list[dict], events: list[dict], thread: str) -> bool:
    """Progress on the exact input while the agent is handling it.

    Work starts come from the scenario's admitted page log and exact input.
    Command spelling, stdout and stream observation times do not set the cutoff.
    Native commentary counts only when the canonical workflow confirms that
    the exact input has an active response with text during tool handling.
    A chat message alone cannot establish that the page showed progress.
    """
    first_tool = next(
        (
            i
            for i, record in enumerate(trace)
            if any(b.get("type") == "tool_use" for b in blocks([record]))
        ),
        len(trace),
    )
    opening = any(
        b.get("type") == "text" and b.get("text")
        for record in trace[:first_tool]
        if record.get("type") == "assistant"
        for b in blocks([record])
    )
    observation = next((r for r in trace if r["type"] == "eval_first_tool_state"), None)
    if opening and observation is not None:
        for workflow in observation["workflows"]:
            response = workflow["response"]
            if (
                workflow["input"] == thread
                and response is not None
                and response["state"] == "active"
                and response["has_text"]
            ):
                return True
    return progress_start(events, thread) is not None


def handed_page_url(trace: list[dict], reply: str) -> bool:
    """The final message links the exact server this live run observed."""
    served = next((r["url"] for r in trace if r["type"] == "eval_served"), None)
    return served is not None and served in URL.findall(reply)


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
        f"{name}_url": handed_page_url(trace, end.get("result") or ""),
    }


def score_handoff(run: Run, trace: list[dict]) -> dict:
    page = run.work / "page"
    events = page_events(page)
    first_end = next(
        (i for i, d in enumerate(trace) if d["type"] == "result"), len(trace)
    )
    handover = trace[first_end].get("result") or "" if first_end < len(trace) else ""
    status = (
        next((d["status"] for d in trace if d["type"] == "eval_status"), None) or {}
    )
    out = {
        "texts": {"handover": handover, "status": status.get("detail") or ""},
        "served": handed_page_url(trace, handover),
        "checked": any("page check" in c for c in ran_between(trace, 0, first_end)),
        "handoff_waiting": status.get("state") == "waiting",
        "watch_left_to_leaf": not any(waits_started(d) for d in trace[:first_end]),
    }
    rounds = live_rounds(trace)
    if rounds:
        r = rounds[0]
        comment = posted_event(page, attempt_key(0, 0))
        _, document = active_document(run, page)
        out["texts"]["dry-run"] = said(document.html).get("dry-run", "")
        out |= round_scores(trace, r, "edit") | {
            "edit_claimed": r["delivery"] is not None
            and r["end"] is not None
            and progress_shown(trace[r["delivery"] : r["end"]], events, comment["id"]),
            "edit_replied": bool(successful_replies(events, comment["id"])),
        }
    if len(rounds) > 1:
        question = posted_event(page, attempt_key(1, 0))
        out["texts"]["answers"] = answers(events, question["id"])
        out |= round_scores(trace, rounds[1], "question")
    return out


def answers(events: list[dict], message: str) -> str:
    """The agent's successful replies to one message, for the judge."""
    return "\n\n".join(e["text"] for e in successful_replies(events, message))


def score_mixed(run: Run, trace: list[dict], browser: Browser) -> dict:
    page = run.work / "page"
    events = page_events(page)
    rounds = live_rounds(trace)
    if not rounds:
        return {"batch_delivered": False}
    r = rounds[0]
    # The error carries no retry key, as the runtime sends none.
    posted = [posted_event(page, attempt_key(0, i)) for i in range(5)]
    comment, pick, reaction, _, _ = posted
    post_ids = set(trace[r["post"]]["events"])
    batches = [
        e
        for e in pickup_receipts(events, phase="opened")
        if post_ids.intersection(e["events"])
    ]
    fixture_words = len(said((FIXTURES / "mixed.html").read_text())["why-now"].split())
    state, document = active_document(run, page)
    words = said(document.html)
    # Each suggestion's (old, new) words, and the comment its acceptance resolves.
    suggestions = [
        (
            [collapse(old.text) for old in suggestion.select(":scope > lf-old")],
            [collapse(new.text) for new in suggestion.select(":scope > lf-new")],
            suggestion.attrs.get("resolves"),
        )
        for suggestion in document.tree.select("lf-suggestion")
    ]
    return round_scores(trace, r, "batch") | {
        "texts": {"dry-run": words.get("dry-run", "")},
        # One delivery carried the whole round, including the page-authored error.
        "one_delivery": r["delivery"] is not None
        and len(batches) == 1
        and post_ids <= set(batches[0]["events"]),
        "comment_claimed": r["delivery"] is not None
        and r["end"] is not None
        and progress_shown(trace[r["delivery"] : r["end"]], events, comment["id"]),
        "comment_replied": bool(successful_replies(events, comment["id"])),
        "stamped": len(state["versions"]) >= 2,
        # Leaf's own reading: the pick owes nothing more, and the ask still shows it
        # answered with the user's option.
        "pick_answered": not pick_owed(state, pick["id"])
        and any(
            ask["source"]["id"] == "copy-mode"
            and (ask["answer"] or {}).get("value") == PICK["detail"]["value"]
            for ask in state["asks"]
        ),
        # The reaction is acted on, by shortening the paragraph in place or by
        # proposing a shorter one as a suggestion, and closed, by the agent or by the
        # suggestion that `resolves` it once the user decides.
        "reaction_handled": (
            0 < len(words.get("why-now", "").split()) < 0.7 * fixture_words
            or any(
                any("every dashboard that reads" in o for o in old)
                and new
                and all(len(n.split()) < 0.7 * fixture_words for n in new)
                for old, new, _ in suggestions
            )
        )
        and (
            any(
                e["kind"] == "resolve"
                and e["author"] == "agent"
                and e["parent"] == reaction["id"]
                for e in events
            )
            or any(resolves == reaction["id"] for _, _, resolves in suggestions)
        ),
        "reaction_unreplied": not successful_replies(events, reaction["id"]),
        "undo_kept": "card-lag-alert" in column_cards(document, "col-open")
        and column_cards(document, "col-done") == [],
        "error_fixed": copy_summary_works(run, page, browser),
    }


def copy_summary_works(run: Run, page: Path, browser: Browser) -> bool:
    """Exercise the repaired control; deleting its behavior cannot pass."""
    with (
        serving(run.payload, run.state, page) as url,
        tab(browser) as view,
    ):
        view.context.grant_permissions(["clipboard-read", "clipboard-write"])
        load(view, url)
        expected = " ".join(view.locator("#summary").inner_text().split())
        view.evaluate("() => navigator.clipboard.writeText('leaf-eval-unwritten')")
        try:
            view.locator("#copy-summary").click()
            return view.evaluate(
                """async expected => {
                    const deadline = performance.now() + 5000;
                    do {
                        if (await navigator.clipboard.readText() === expected) return true;
                        await new Promise(requestAnimationFrame);
                    } while (performance.now() < deadline);
                    return false;
                }""",
                expected,
            )
        except PlaywrightTimeout:
            return False


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
    deliveries = [
        text
        for record in trace[r["post"] : r["end"]]
        for text in [
            record.get("output", ""),
            *[
                text_of(block.get("content", ""))
                for block in blocks([record])
                if block.get("type") == "tool_result"
            ],
        ]
        if DELIVERY_FORMAT in text
    ]
    replying = next(
        (
            i
            for i in range(r["delivery"], len(trace))
            if any(
                re.search(r"\b(?:thread|response) reply\b", c)
                for c in commands(trace[i])
            )
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
    return out | {
        "texts": {"answers": answers(events, question["id"])},
        # Validity: the delivery shortened the thread, as the case assumes.
        "shown_elided": any(
            re.search(r'\\?"elided\\?":\s*\{\\?"messages\\?":\s*[1-9]', delivery)
            and PREMISE not in delivery
            for delivery in deliveries
        ),
        "middle_read": premise is not None and r["post"] < premise < replying,
        "premise_read_in": None
        if premise is None
        else "resume"
        if premise < r["post"]
        else "delivery",
        "titled": any(
            item["id"] == thread and item["title"] is not None
            for item in page_state(run, page)["threads"]
        ),
        "summarized": any(
            e["kind"] == "summary" and e.get("thread") == thread for e in events
        ),
    }


LIVE_SCORES = {"handoff": score_handoff, "elided": score_elided}

# These declarations remain complete when a scorer exits early or a round never
# arrives. Missing observations fail instead of silently shrinking the assertion set.
# What a scenario judges by meaning is in `JUDGED` instead.
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
    ),
    "near-miss": ("no_page", "leaf_skill_quiet"),
    "resume": (
        "stamped",
        "source_valid",
        "batch_200",
        "batch_in_place",
        "pick_taken_in",
        "pick_standing",
        "no_restated",
        "replied",
    ),
    "constructs": (
        "stamped",
        "draft_restated",
        "p95_text",
        "p95_current",
        "source_kept",
    ),
    "board": (
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
        "watch_left_to_leaf",
        "edit_delivered",
        "edit_watch_left_to_leaf",
        "edit_waiting",
        "edit_url",
        "edit_claimed",
        "edit_replied",
        "question_delivered",
        "question_watch_left_to_leaf",
        "question_waiting",
        "question_url",
    ),
    "mixed": (
        "batch_delivered",
        "batch_watch_left_to_leaf",
        "batch_waiting",
        "batch_url",
        "one_delivery",
        "comment_claimed",
        "comment_replied",
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
        "titled",
        "summarized",
    ),
}


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    """The fixed assertion set for one complete scenario."""
    CASES[case]
    checks = [] if case.startswith("reading") else list(CHECKS[case])
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
    elif case == "resume":
        values["stamped"] = score.get("versions", 0) >= 3
    return {
        name: usable if name == "completed" else values.get(name) is True
        for name in expected_checks(case)
    }


def score_run(run: Run, traces: list[list[dict]], calls: list[str]) -> dict:
    """Apply the scenario's semantic reading to its complete native trajectory."""
    if run.case == "mixed":
        with chrome() as browser:
            return score_mixed(run, traces[0], browser)
    if run.case in LIVE_SCORES:
        return LIVE_SCORES[run.case](run, traces[0])
    if run.case == "package":
        return score_package(run, traces[0])
    if run.case == "shared-source":
        return score_shared_source(run, traces)
    if run.case in COLD:
        return score_cold(run, calls)
    if run.case.startswith("reading"):
        return {}
    if run.case == "board":
        return score_board(run)
    if run.case == "constructs":
        return score_constructs(run)
    return score_resume(run)


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    """One Promptfoo provider call owns all phases, live rounds, and evidence.

    `metadata.checks` answers each fixed check; `metadata.texts` holds each text a
    `rubrics` judge reads: every phase's final message, and what the scorer read."""
    run = Run(case, payload, work, harness)
    with scratch() as child_work:
        execute(run, child_work)
        traces = run.traces()
        phases = resumed([trace_scores(t) for t in traces])
        replies = [p["reply"] for p in phases]
        calls = [c for p in phases for c in p["calls"]]
        usable = run.usable()
        score = score_run(run, traces, calls) if usable else {}
    texts = {f"reply-{n}": reply for n, reply in enumerate(replies, 1)}
    texts |= score.pop("texts", {})
    checks = checks_for(case, score, phases, usable)
    usage = {
        field: count
        for field, key in (("prompt", "input_tokens"), ("completion", "output_tokens"))
        if (count := observed_sum(phase[key] for phase in phases)) is not None
    }
    return {
        "output": "\n\n".join(replies),
        **(
            {"cost": cost}
            if (cost := observed_sum(p["cost_usd"] for p in phases)) is not None
            else {}
        ),
        **({"tokenUsage": usage} if usage else {}),
        "metadata": {
            "checks": checks,
            "texts": texts,
            "diagnostics": {"score": score, "phases": phases},
        },
    }
