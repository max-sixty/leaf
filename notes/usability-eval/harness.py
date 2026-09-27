"""The agent-usability baseline: author cold, read a page back, resume a foreign page.

    uv run notes/usability-eval/harness.py arm <ref> <name>
    uv run notes/usability-eval/harness.py run <arm>[,<arm>] <batch> <rounds> [case ...]
    uv run notes/usability-eval/harness.py score <batch>
    uv run notes/usability-eval/harness.py summarize <batch>
    uv run notes/usability-eval/harness.py show <batch> [case]
    uv run notes/usability-eval/harness.py fixture <case> <arm> <dest>

This is `notes/agent-usability-evals.md`'s first executable slice and the start of
its next paired check. Each case starts a fresh Claude Code with Leaf as the host
installs it and scores what it did. `run` with no case runs `BASELINE`; the paired
check runs `resume`, `constructs` and `board` on two arms.

Cases (`CASES`):

- `cold-report`, `cold-decision`, `near-miss`: a user request with no page. The first
  should become a quick informational page, the second a page with one Ask, and the
  third an ordinary chat answer with no page, which measures whether the skill stays
  quiet.
- `reading`: a page whose facts each sit on a different surface (plain prose, a
  closed disclosure, an inactive tab, a chart's data, external data, a user's
  standing pick, and which tab the user has open, which no page file records). The
  agent answers one question per fact, scored against `fixtures/reading-answers.json`.
  `reading-<surface>` is the same page cut down to that one surface, to isolate a
  failure the combined page shows.
- `resume`: a page directory another session left: two stamped versions, a resolved
  and an open thread, a user's pick no markup records yet, and an invalid
  `index.html` candidate. Phase 1 asks where it stands; phase 2, resuming the same
  session, asks for the next step.
- `constructs`: a draft the user rewrote, a figure stated at one measurement whose
  source has since run again, and a chart. Phase 1 asks what each says; phase 2 asks
  for one change to each, whose owners differ.
- `board`: a board whose cards the user moved into a column at ranks between the
  authored cards, with one move undone. Phase 1 asks for the column's order; phase 2
  asks for a change that obliges the version to write the moved cards in place.
- `package`: a page that selects a package the base layer lacks, whose one widget
  (`fixtures/slo/`) the agent is asked to use without being told its tag or contract.
- `shared-source`: two `lf-worktree` widgets reading one source whose value file also
  holds an unrelated record, listed first and resembling one widget's. Phase 1 asks
  what each widget shows; phase 2 asks for one worker's new state.

The live cases, those with `rounds`, serve a page from the child's own session and
post user moves through the served page as a tab does, one round each time a turn
ends with the earlier rounds delivered (`execute_live`):

- `handoff`: a drafted page to hand over, then an edit request and, after that turn,
  a question. Each turn is scored for the status it leaves and the wait it re-arms.
- `mixed`: a comment, an Ask's pick, a reaction, a card move and its undo, and a page
  error, posted together so one delivery carries them.
- `elided`: a thread of twenty-four messages another session answered and the user
  closed, whose middle holds the premise a new question in it turns on. The delivery
  shows the thread's first and latest messages only.

The paired check's arms were the payload at 387dfed45, whose `page state` carried a
construction tree of the document, and the same payload with the tree dropped and the
references reading the active HTML beside the compact state (`results/*.json` name
them `main` and `notree`). The tree has since gone, so an A/B builds its arms from two
refs.

Choices the note asks for before automating:

- Runner and host: `claude -p` through `leaf_dev.harness.claude_child`, with the arm
  loaded by `--plugin-dir`, so the child finds the skill, its launcher on `PATH` and
  its hooks as an installed Claude Code session does. Nothing names a reference or
  the launcher; cold cases do not name Leaf at all.
- Model: Opus 5.5 (`MODEL`), default effort and tools, bypass permissions.
- Isolation: an arm is `leaf_dev.harness.build_arm`'s payload at one ref, under
  `.tmp/usability-eval/arms/<name>/` with `skills/` read-only. Each run has its own
  scratch cwd outside any repository, which holds the fixture page, and its own
  `XDG_STATE_HOME`. A round starts every case × arm at once.
- Fixtures: `build_*` writes each fixture with the arm's own launcher and admits
  user moves through the browser's door (`event_endpoint.accept_event`) in the arm's
  own environment, so a fixture is what that arm's server would have written.
- Trace: the child's stream-json, one file per phase; a live case's one file also
  holds each post (`eval_post`) and the page's status at each turn's end
  (`eval_status`).
- Normalization: reading and `constructs` answers are numbered lines, one per
  question; each line is matched case-insensitively against its question's pattern.
  Resume answers lead with `Date:`, `Approach:` and `Next:` lines, matched the same
  way. The patterns are checked by reading every reply (`show`), and
  `notes/agent-usability-evals.md` records the disagreements.
- Retention: traces, pages and scratch stay under `.tmp/usability-eval/runs/<batch>/`
  (gitignored); `score` writes the batch's per-run scores to `results/<batch>.json`,
  which is committed so a later run compares against it.

A run counts only when every trace through its phase completed
(`leaf_dev.harness.completed`), and a live run only when every turn did and the session
ended before its deadline. The first round of a new case fixes its fixture and
scorer and is not reported.
"""

import json
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import unescape
from pathlib import Path

import click
from leaf_dev.harness import (
    URL,
    LiveChild,
    PageClient,
    blocks,
    build_arm,
    commands,
    completed,
    environment,
    hook_delivered,
    now,
    read_trace,
    run_claude,
    run_leaf,
    scratch,
    trace_result,
    waits_started,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / ".tmp/usability-eval"
FIXTURES = HERE / "fixtures"
RESULTS = HERE / "results"
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
BASELINE = ("cold-report", "cold-decision", "near-miss", "reading", "resume")

# Arms, runs and batches


def arm_dir(name: str) -> Path:
    return DATA / "arms" / name


@dataclass(frozen=True)
class Run:
    case: str
    arm: str
    n: int
    dir: Path

    @classmethod
    def at(cls, path: Path) -> "Run":
        case, arm, n = path.name.rsplit("-", 2)
        return cls(case, arm, int(n), path)

    @property
    def payload(self) -> Path:
        return arm_dir(self.arm)

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
        return (
            len(traces) == len(CASES[self.case].prompts)
            and all(completed(t) for t in traces)
            # A live trace holds a result per turn, and every turn must complete.
            and all(
                d.get("is_error") is False
                for t in traces
                for d in t
                if d.get("type") == "result"
            )
            and not (self.dir / "timed-out").exists()
        )


def batch_runs(batch: str) -> list[Run]:
    root = DATA / "runs" / batch
    if not root.is_dir():
        raise click.BadParameter(f"no batch at {root}")
    return [Run.at(d) for d in sorted(root.iterdir()) if (d / "work-dir").exists()]


@click.group()
def cli():
    """The agent-usability baseline; see the module docstring."""


@cli.command()
@click.argument("ref")
@click.argument("name")
def arm(ref: str, name: str):
    """Build arm NAME from git REF."""
    if not re.fullmatch(r"[a-z0-9]+", name):
        raise click.BadParameter("an arm name is lowercase letters and numbers")
    out = arm_dir(name)
    sha = build_arm(ref, out)
    subprocess.run(["chmod", "-R", "a-w", out / "skills"], check=True)
    (out.parent / f"{name}.REF").write_text(f"{sha}\n")
    click.echo(f"{out}: {sha}")


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
    run.leaf("version", "stamp", str(page), "--text", "Plan as authored", check=True)
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
    run.leaf("version", "stamp", str(page), "--text", "First plan", check=True)
    admit(run, page, {
        "kind": "comment", "revision": 1,
        "text": "These rehearsal numbers are from before the mapping change. Rerun it and update the figure.",
        "anchor": anchor(v1, "rehearsal-result", "4.1 million documents in 3 h 20 min"),
    })  # fmt: skip
    rerun = page_events(page)[-1]["id"]
    (page / "index.html").write_text(v2)
    run.leaf(
        "version", "stamp", str(page), "--text",
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
    at = re.search(r"updated (\S+)", measured)[1]
    (page / "index.html").write_text(re.sub(r'\bat="[^"]*"', f'at="{at}"', template))
    run.leaf("version", "stamp", str(page), "--text", "Release 4.2 review", check=True)
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
    run.leaf("version", "stamp", str(page), "--text", "Key rotation board", check=True)
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
    run.leaf("version", "stamp", str(page), "--text", "September review", check=True)


def build_shared_source(run: Run, page: Path) -> None:
    """Two worktree widgets on one source, whose snapshot lists an unrelated record
    first."""
    run.leaf("page", "init", "--package", "command-hub", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "hub.html").read_text())
    run.leaf(
        "data", "set", str(page), "project-worktrees",
        input_text=(FIXTURES / "hub-worktrees.json").read_text(), check=True,
    )  # fmt: skip
    run.leaf("version", "stamp", str(page), "--text", "Parser workers", check=True)


def build_handoff(run: Run, page: Path) -> None:
    """A drafted page nobody has checked, served or stamped."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "backfill.html").read_text())


def build_mixed(run: Run, page: Path) -> None:
    """A stamped page another session handed over; its copy button's script
    throws on a click."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "mixed.html").read_text())
    run.leaf("version", "stamp", str(page), "--text", "Backfill plan", check=True)
    run.leaf("status", str(page), "waiting", "Pick how the copy runs", check=True)


def build_elided(run: Run, page: Path) -> None:
    """A stamped page whose thread another session answered to the end and the user
    then closed, with every delivery acknowledged. A closed thread is no open work,
    so a session picking the page up has no call to read it."""
    html = (FIXTURES / "elided.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(html)
    run.leaf("version", "stamp", str(page), "--text", "Backfill schedule", check=True)
    run.leaf("status", str(page), "waiting", "", check=True)
    first, *rest = ELIDED_THREAD
    admit(run, page, {
        "kind": "comment", "revision": 1, "text": first,
        "anchor": anchor(html, "window", "in the maintenance window"),
    })  # fmt: skip
    thread = page_events(page)[-1]["id"]
    for n, text in enumerate(rest):
        latest = page_events(page)[-1]["id"]
        if n % 2 == 0:
            run.leaf("thread", "reply", str(page), "--for", latest, "--text", text,
                     check=True)  # fmt: skip
        else:
            admit(run, page, {
                "kind": "reply", "revision": 1, "parent": latest, "text": text,
            })  # fmt: skip
    admit(run, page, {"kind": "resolve", "parent": thread})
    acknowledge(run, page)


def acknowledge(run: Run, page: Path) -> None:
    """Confirm every pending event as the session that answered them did, through
    a delivery its wait would have printed."""
    arm_python(
        run,
        "import sys\nfrom pathlib import Path\n"
        "from leaf.delivery import batch_data, freeze_delivery\n"
        "from leaf.service import PageTransaction, unacknowledged\n"
        "from leaf.session import receive\n"
        "page_dir = Path(sys.argv[1])\n"
        "with PageTransaction(page_dir) as page:\n"
        "    batch = batch_data(page_dir, page, unacknowledged(page.events, page.cursor))\n"
        "receive(freeze_delivery([batch], carrier='wait'), None)",
        str(page),
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


@cli.command()
@click.argument("case", type=click.Choice([c for c in CASES if CASES[c].fixture]))
@click.argument("arm_name")
@click.argument("dest", type=click.Path(path_type=Path))
def fixture(case: str, arm_name: str, dest: Path):
    """Build CASE's fixture page with ARM_NAME at DEST/page, to inspect it."""
    dest = dest.resolve()
    shutil.rmtree(dest, ignore_errors=True)
    run = Run(case, arm_name, 0, dest)
    run.state.mkdir(parents=True)
    build_fixture(run, CASES[case].fixture, dest / "page")
    click.echo(dest / "page")


# Running


def execute(run: Run) -> None:
    """One run: build the case's fixture, then run each phase, resuming the first
    phase's session, or the live session."""
    case = CASES[run.case]
    shutil.rmtree(run.dir, ignore_errors=True)
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
    click.echo(f"{run.dir} done")


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
    url, posted, delivered = None, 0, 0
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
                note(record)
                arrived = hook_delivered(record) + sum(
                    "wait --ack" in c or "delivery read" in c for c in commands(record)
                )
                if arrived:
                    delivered += arrived
                    waiting.cancel()
                if not url and (found := URL.search(json.dumps(record))):
                    url = found[0]
                if record.get("type") != "result":
                    continue
                status = page_state(run, page).get("status")
                note({"type": "eval_status", "status": status, "received_at": now()})
                if delivered < posted:
                    continue
                if url and posted < len(case.rounds):
                    time.sleep(3)
                    post_round(run, page, PageClient(url), case.rounds[posted], posted)
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
        if n in ("runtime", "vendor", "widgets", "guidance", "service.json")
        or n.endswith((".lock", ".js", ".css"))
    }


def pages(*roots: Path) -> list[Path]:
    """Every page directory under `roots`."""
    return sorted(p.parent for root in roots for p in root.rglob("events.jsonl"))


@cli.command("run")
@click.argument("arms")
@click.argument("batch")
@click.argument("rounds", type=int)
@click.argument("cases", nargs=-1, type=click.Choice(list(CASES)))
@click.option("--start", default=1, help="number of the first round")
def run_batch(arms: str, batch: str, rounds: int, cases: tuple[str, ...], start: int):
    """Run ROUNDS rounds of CASES (default: the baseline) for each comma-separated
    arm in ARMS into BATCH. A round starts every case × arm at once."""
    names = arms.split(",")
    for name in names:
        if not (arm_dir(name) / "bin/leaf").exists():
            raise click.BadParameter(f"no arm at {arm_dir(name)}", param_hint="ARMS")
    root = DATA / "runs" / batch
    for n in range(start, start + rounds):
        round_ = [
            Run(c, a, n, root / f"{c}-{a}-{n}")
            for c in cases or BASELINE
            for a in names
        ]
        with ThreadPoolExecutor(len(round_)) as pool:
            list(pool.map(execute, round_))


# Scoring


# The first match names a shell call; a call that reads several things counts as the
# first, so `output_bytes` is a rough split.
BASH_KINDS = {
    "reference": r"references/|SKILL\.md",
    "page state": r"\bpage state\b",
    "events": r"\bleaf events\b|/leaf events\b",
    "thread read": r"\bthread read\b",
    "transcript": r"\btranscript\b",
    "version check": r"\bversion check\b",
    "version stamp": r"\bversion stamp\b",
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
    checked = run.leaf("version", "check", str(page))
    state = page_state(run, page)
    out |= {
        "valid": checked.returncode == 0,
        "agent_checked": "version check" in calls,
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
        "chart_85": bool(chart and re.search(r"sa-east,\s*85\b", chart[0])),
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
        "valid": run.leaf("version", "check", str(page)).returncode == 0,
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
    """Each posted round: where it went out, the delivery that carried it, the end of
    the turn that took it, and the status recorded at that end."""
    rounds = []
    for n, post in enumerate(
        i for i, d in enumerate(trace) if d["type"] == "eval_post"
    ):
        arrived = next(
            (i for i in range(post, len(trace)) if hook_delivered(trace[i])), None
        )
        end = arrived and next(
            (i for i in range(arrived, len(trace)) if trace[i]["type"] == "result"),
            None,
        )
        rounds.append(
            {
                "round": n + 1,
                "post": post,
                "delivery": arrived,
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


def first_index(ran: list[str], pattern: str) -> int | None:
    return next((i for i, c in enumerate(ran) if re.search(pattern, c)), None)


def claimed_first(ran: list[str]) -> bool:
    """Whether a `working` claim on a thread or widget precedes the first reply."""
    claim = first_index(ran, r"\bstatus\b[^|;&]*\bworking\b[^|;&]*--on\b")
    reply = first_index(ran, r"\bthread reply\b")
    return claim is not None and (reply is None or claim < reply)


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
    """What every live round is held to: delivered, a wait re-armed in the turn
    that took it, and that turn ending on a waiting page whose URL it repeats."""
    if r["delivery"] is None or r["end"] is None:
        return {f"{name}_delivered": False}
    end = trace[r["end"]]
    return {
        f"{name}_delivered": True,
        f"{name}_rearmed": any(
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
        "checked": any("version check" in c for c in ran_between(trace, 0, first_end)),
        "handoff_waiting": status.get("state") == "waiting",
        "detail_names_ask": check(
            r"cop(y|ies)|backfill|approach|option|how .*run", status.get("detail") or ""
        ),
        "wait_started": any(waits_started(d) for d in trace[:first_end]),
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
            and claimed_first(
                ran_between(trace, r["delivery"], r["end"] or len(trace))
            ),
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
    picked = {i for e in events if e["kind"] == "pickup" for i in e.get("events", [])}
    fixture_words = len(
        element_text((FIXTURES / "mixed.html").read_text(), "why-now").split()
    )
    state, html = active_html(run, page)
    ran = ran_between(trace, r["delivery"] or 0, r["end"] or len(trace))
    out = round_scores(trace, r, "batch") | {
        # One delivery carried every user move, and nothing else arrived in its turn.
        "one_delivery": r["delivery"] is not None
        and sum(hook_delivered(d) for d in trace[r["post"] : r["end"] or len(trace)])
        == 1
        and {e["id"] for e in posted if e["author"] == "user"} <= picked,
        "comment_claimed": claimed_first(ran),
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
        "middle_read": premise is not None and premise < replying,
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


@cli.command()
@click.argument("batch")
def score(batch: str):
    """Score BATCH, print one row per run, and write results/BATCH.json."""
    rows = []
    for run in batch_runs(batch):
        traces = [trace_scores(t) for t in run.traces()]
        replies = [t["reply"] for t in traces]
        calls = [k for t in traces for k in t["calls"]]
        row = {
            "case": run.case,
            "arm": run.arm,
            "n": run.n,
            "usable": run.usable(),
            "phases": [
                {k: v for k, v in t.items() if k not in ("reply", "calls")}
                | {"calls": t["calls"]}
                for t in traces
            ],
        }
        if run.case in LIVE_SCORES:
            row["score"] = LIVE_SCORES[run.case](run, run.traces()[0])
        elif run.case == "package":
            row["score"] = score_package(run, run.traces()[0])
        elif run.case == "shared-source":
            row["score"] = score_shared_source(run, run.traces(), replies)
        elif run.case in COLD:
            row["score"] = score_cold(run, replies[-1] if replies else "", calls)
        elif run.case.startswith("reading"):
            row["score"] = score_reading(run, replies[-1] if replies else "")
        elif run.case == "board":
            row["score"] = score_board(run, replies)
        elif run.case == "constructs":
            row["score"] = score_constructs(run, replies)
        else:
            row["score"] = score_resume(run, replies)
        rows.append(row)
        skill = any(p["leaf_skill"] for p in row["phases"])
        click.echo(
            f"{run.dir.name:32} usable={row['usable']!s:5} skill={skill!s:5} "
            f"${sum(p['cost_usd'] for p in row['phases']):.2f} "
            f"in={sum(p['input_tokens'] for p in row['phases']):>8} "
            f"{json.dumps(row['score'])}"
        )
    RESULTS.mkdir(exist_ok=True)
    refs = {
        name: (arm_dir(name).parent / f"{name}.REF").read_text().strip()
        for name in sorted({r["arm"] for r in rows})
    }
    (RESULTS / f"{batch}.json").write_text(
        json.dumps({"model": MODEL, "arms": refs, "runs": rows}, indent=1) + "\n"
    )


@cli.command()
@click.argument("batch")
@click.argument("case", required=False)
def show(batch: str, case: str | None):
    """Print each run's prompts' replies, for checking the scorer by reading."""
    for run in batch_runs(batch):
        if case and run.case != case:
            continue
        for n, trace in enumerate(run.traces(), 1):
            click.echo(
                f"=== {run.dir.name} phase {n}\n{trace_result(trace).get('result')}\n"
            )


@cli.command()
@click.argument("batch")
def summarize(batch: str):
    """Tabulate results/BATCH.json by case and arm: each check's passes (a true
    value) over the usable runs, and the mean cost, input tokens and bytes of `page
    state` output."""
    rows = json.loads((RESULTS / f"{batch}.json").read_text())["runs"]
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["case"], row["arm"]), []).append(row)
    for (case, arm_name), runs in sorted(groups.items()):
        usable = [r for r in runs if r["usable"]]
        n = len(usable)
        phases = [p for r in usable for p in r["phases"]]

        def mean(values, n=n):
            return sum(values) / n if n else 0

        click.echo(
            f"{case} / {arm_name}: {n} of {len(runs)} usable; "
            f"${mean(p['cost_usd'] for p in phases):.2f}, "
            f"{mean(p['input_tokens'] for p in phases):,.0f} input tokens, "
            f"{mean(p['output_bytes'].get('page state', 0) for p in phases):,.0f} "
            f"bytes of page state per run; "
            f"skill loaded {sum(any(p['leaf_skill'] for p in r['phases']) for r in usable)}"
        )
        checks = [k for k, v in usable[0]["score"].items() if isinstance(v, bool)]
        for key in checks:
            click.echo(f"  {key}: {sum(bool(r['score'].get(key)) for r in usable)}/{n}")
        if case.startswith("reading"):
            for surface in usable[0]["score"]["answers"]:
                passed = sum(r["score"]["answers"][surface] for r in usable)
                click.echo(f"  {surface}: {passed}/{n}")


if __name__ == "__main__":
    cli()
