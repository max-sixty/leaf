"""Author, revise and decide on one page-task sample under its explicit condition,
on the loop a user would run.

Leaf and ordinary HTML receive the same task in one live session (`LiveSession`),
then the same width preference as a chat message, then, where the task declares
them, the same user comment and a decision the user makes on the page. Each
sample contains only its selected condition; the HTML child sees no Leaf payload,
instructions or runtime.

- **Leaf** runs as installed: the arm is the session's plugin, hooks included. The
  agent serves the page and hands it over; the harness comments from a browser
  selection on the served page (`eval_user.comment_on_passage`), and the hook
  delivers the comment.
- **HTML** keeps chat turns, since it has no page to wait on: the comment arrives
  in chat, naming the passage in words.

The decision round is the same in both: a user agent makes the page's decision in
the browser (`eval_user.decide`), then the user asks in chat for it to be applied.
Leaf's agent reads the gestures from the page's log; HTML's user pastes what the
page offered to copy, or types the decision where it offered nothing, and so does
a Leaf user whose page took none of it. A reader then says what the agent applied,
from its answer and the page's final files, and `decision-applied` checks that
against what was chosen. On Leaf a fresh reader also reports the decision from
the page's state, without the conversation. A comment that directs an outcome is
the user's pick for that item, so recording it as chosen is correct; whether the
agent did is recorded, not checked.

Each phase records what the author spent and wrote, from the session's records
between the harness's `eval_phase` marks: time, turns, tokens and cost (`resumed`),
the CSS and script lines in the files it authored, and how many times it wrote and
rendered the page, the measure of its repair iterations. The user agent and the
readers spend too; that is the harness's, recorded apart.

The sample's output is what a judge needs: the user's request, the later messages,
the author's answer to the comment, and each version's screenshots by width,
written to `shots`, the one directory its judge may read. Before screenshotting a version that carries the comment, the
capture opens the commented item (`Scenario.reveal`), so the judge sees the change.
`rubrics` are the Promptfoo `agent-rubric` assertions the judge grades from it;
`eval-pairs` is the quality score, judging a pair's final versions side by side.
"""

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import turbohtml
from leaf.delivery import opened_input_ids
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.passages import SourceReading
from leaf.render_checks import rendered
from leaf.schema import MESSAGE_KINDS
from leaf.service import requires_agent_attention
from leaf.structure import SourceDocument
from leaf.thread import successful_replies

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arms import (
    MODELS,
    TURN_LIMIT,
    LiveChild,
    LiveSession,
    blocks,
    completed,
    now,
    observed_sum,
    read_trace,
    resumed,
    run_agent,
    run_leaf,
    scratch,
    serving,
    trace_result,
    trace_summary,
)
from leaf_dev.browser import chrome, load, settle, tab
from leaf_dev.eval_user import comment_on_passage, decide, reveal

TASKS = ROOT / "evals"
WIDTHS = {
    "laptop": ((1440, 900), "a 1440px laptop window"),
    "narrow": ((900, 900), "a 900px window"),
    "short": ((900, 600), "a short 900px by 600px window"),
    "phone": ((390, 844), "a 390px phone"),
}
PREFERENCE = (
    "A standing preference for all my pages from now on: I read them in a window "
    "about 900px wide, beside my editor. At that width, keep the page's summary, "
    "status, contents or queue beside the main content rather than stacked above "
    "or below it."
)
# Content out of view is reachable through a labeled control, as both judges count
# it.
REACHABLE = (
    "A labeled control whose content is out of view, such as a collapsed section, "
    "an unselected item or a scroll region's remainder, counts as reachable but "
    "costs the user a step; content cut off with no visible way to reach it does "
    "not count."
)
# How long a session that has answered stays quiet before the next phase, and how
# long the harness waits for a turn to start before calling a phase undelivered.
GRACE = 20
WAKE = 15 * 60


@dataclass(frozen=True)
class Comment:
    """The user's comment on the width-revised page, the same in both conditions.

    `target` names the passage in words, as a user writing in chat would. On Leaf the
    user selects the first of `quotes` the page draws, and otherwise comments on
    the page whole, naming the target. `applied` names a fact only the comment
    supplies, which the authored files carry once the change is made and the answer
    carries when it tells the user so."""

    target: str
    quotes: tuple[str, ...]
    text: str
    applied: str


@dataclass(frozen=True)
class Decision:
    """What the user decides on the page once it carries the comment, then asks
    the agent to apply. `task` tells the user agent what to do on the page; `typed`
    is the decision as the user types it in chat. `chosen` is what applying it
    records, item by item, each value one of the item's `values`."""

    task: str
    typed: str
    chosen: dict[str, str]
    values: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Scenario:
    quality: str = ""
    comment: Comment | None = None
    decision: Decision | None = None
    # What a reader clicks to open the item that holds the comment's passage.
    reveal: str = ""


DISPOSITIONS = ("refund", "fix", "escalate to engineering", "close")
QUEUE = {
    "ESC-4107": "fix",
    "ESC-4108": "close",
    "ESC-4109": "fix",
    "ESC-4111": "escalate to engineering",
    "ESC-4112": "escalate to engineering",
    "ESC-4113": "refund",
    "ESC-4114": "escalate to engineering",
}
QUEUE_DECISIONS = "; ".join(f"{ticket}: {action}" for ticket, action in QUEUE.items())

ACTIONS = ("pages", "opens a ticket", "off")
# Each alert's candidate thresholds as the request lists them, and the user's setting.
ALERTS = {
    "payments-5xx-rate": (
        ("over 0.5%", "over 1%", "over 2%", "over 5%"),
        ("over 2%", "pages"),
    ),
    "payments-p99-latency": (
        ("over 600 ms", "over 800 ms", "over 1,200 ms", "over 2,000 ms"),
        ("over 1,200 ms", "opens a ticket"),
    ),
    "card-auth-decline-spike": (
        ("over 1.5×", "over 2×", "over 3×"),
        ("over 3×", "opens a ticket"),
    ),
    "webhook-backlog": (
        ("over 1,000", "over 5,000", "over 20,000"),
        ("over 20,000", "pages"),
    ),
    "ledger-reconciliation-lag": (
        ("over 60 min", "over 90 min", "over 180 min"),
        ("over 180 min", "pages"),
    ),
    "gateway-cert-expiry": (
        ("under 30 days", "under 14 days", "under 7 days"),
        ("under 30 days", "opens a ticket"),
    ),
}
SETTINGS = "; ".join(
    f"{alert}: {threshold}, {action}"
    for alert, (_, (threshold, action)) in ALERTS.items()
)


CASES = {
    "document": Scenario(
        comment=Comment(
            target="the recommendation's ask of the database owners",
            quotes=(
                "the database owners to say whether 55% peak CPU is acceptable",
                "whether 55% peak CPU is acceptable",
                "55% peak CPU",
            ),
            text="The database owners are Mei Tanaka's team. Name them here and ask "
            "for their answer by Wednesday, the day before the decision.",
            applied=r"Mei Tanaka",
        ),
        decision=Decision(
            task="As the platform team, decide the review's question: choose "
            "option 1, staying on managed Redis and shortening the TTL to 7 days.",
            typed="We've decided: stay on managed Redis and shorten the TTL to 7 days.",
            chosen={"option": "stay on managed Redis, 7-day TTL"},
            values={
                "option": (
                    "stay on managed Redis, 7-day TTL",
                    "Postgres",
                    "stateless tokens with a revocation list",
                )
            },
        ),
    ),
    "dashboard": Scenario(
        comment=Comment(
            target="the follow-up to confirm the timeout change with the payments team",
            quotes=(
                "Confirm the timeout change with the payments team (Dana).",
                "Confirm the timeout change with the payments team",
                "timeout change with the payments team",
            ),
            text="Dana confirmed at 15:52 that 7.2's 3 s connect timeout is the cause. "
            "Mark this follow-up done and say so where the page explains the cause.",
            applied=r"15:52",
        ),
        decision=Decision(
            task="Decide eu-west: roll it back to 4.11 and ship 4.12.1 with the old "
            "timeout.",
            typed="Roll eu-west back to 4.11 and ship 4.12.1 with the old timeout.",
            chosen={
                "eu-west": "roll back to 4.11",
                "next release": "4.12.1 with the old timeout",
            },
            values={
                "eu-west": ("resume to 100%", "hold at 50%", "roll back to 4.11"),
                "next release": ("4.12.1 with the old timeout", "none"),
            },
        ),
    ),
    "queue": Scenario(
        comment=Comment(
            target="ESC-4110 (Brightline Dental)'s suggested action",
            quotes=(
                "point to the feature request board, already planned for Q4",
                "point to the feature request board",
                "feature request board",
            ),
            text="Brightline is on a Team trial that converts next week, so don't just "
            "close it: route it to their account manager, Sam Okafor, with the Q4 plan.",
            applied=r"Sam Okafor",
        ),
        decision=Decision(
            task="Work through the queue and decide each ticket: "
            f"{QUEUE_DECISIONS}. ESC-4110 is settled by your earlier comment; "
            "leave it as it is.",
            typed=f"My decisions: {QUEUE_DECISIONS}. ESC-4110 as I said in my comment.",
            chosen=QUEUE,
            values=dict.fromkeys(QUEUE, DISPOSITIONS),
        ),
        reveal="ESC-4110",
    ),
    "configuration": Scenario(
        comment=Comment(
            target="the ledger-reconciliation-lag alert",
            quotes=(
                "minutes since the last successful ledger reconciliation run",
                "last successful ledger reconciliation run",
                "ledger-reconciliation-lag",
            ),
            text="Finance owns this alert. If it pages, it pages the finance-ops "
            "rotation, not payments on-call; show that beside its routing.",
            applied=r"finance-ops",
        ),
        decision=Decision(
            task=f"Set each alert's threshold and routing: {SETTINGS}.",
            typed=f"Final settings: {SETTINGS}.",
            chosen={
                f"{alert} {part}": value
                for alert, (_, setting) in ALERTS.items()
                for part, value in zip(("threshold", "routing"), setting)
            },
            values={
                f"{alert} {part}": values
                for alert, (thresholds, _) in ALERTS.items()
                for part, values in (("threshold", thresholds), ("routing", ACTIONS))
            },
        ),
        reveal="ledger-reconciliation-lag",
    ),
    "sidebar-page-at-900px": Scenario(
        quality=(
            "The completed rollout's forty entries must remain readable in the "
            "document's scroll, rather than showing only one screen of a separate "
            "listing. At both 900px window heights, all six checks and their failing "
            "result stay accessible beside the log as it scrolls. Page navigation "
            "and any supporting sidebar content remain reachable; a sticky box must "
            "not hold them below the window. On a phone, the regions stack without covering "
            "the log or hiding its entries."
        ),
    ),
}


@dataclass(frozen=True)
class Run:
    subject: str
    payload: Path
    directory: Path
    shots: Path
    harness: str = ClaudeCodeHarness.name
    condition: str = "leaf"
    phase_starts: dict = field(default_factory=dict, compare=False)

    @property
    def leaf_condition(self) -> bool:
        return self.condition == "leaf"

    @property
    def work(self) -> Path:
        return Path((self.directory / "work-dir").read_text())

    @property
    def authored_page(self) -> Path:
        return self.work / "page"

    @property
    def state(self) -> Path:
        return self.work / "state"

    def leaf(self, *args: str, **kwargs):
        return run_leaf(self.payload, self.state, *args, **kwargs)

    def page(self, phase: int) -> Path | None:
        page = self.directory / f"page-phase{phase}"
        return page if (page / "index.html").exists() else None

    def record(self, name: str, value: dict) -> None:
        (self.directory / f"{name}.json").write_text(json.dumps(value, indent=2))

    def recorded(self, name: str) -> dict:
        path = self.directory / f"{name}.json"
        return json.loads(path.read_text()) if path.exists() else {}


def phases(subject: str) -> tuple[int, ...]:
    """Authoring, the width revision, the comment and the decision, as the task has
    them."""
    scenario = CASES[subject]
    return (
        1,
        2,
        *((3,) if scenario.comment else ()),
        *((4,) if scenario.decision else ()),
    )


def first_prompt(payload: Path, page: Path, subject: str, condition="leaf") -> str:
    request = (TASKS / subject / "request.md").read_text()
    if condition == "leaf":
        tooling = (
            "Use the Leaf skill ($leaf in Codex; leaf:leaf in Claude Code) for this "
            f"page. $LEAF is its launcher, {payload}/bin/leaf. Check the page with "
            f"`$LEAF page check {page} --render`, fix findings and stamp it."
        )
        handover = (
            f"Write the page at {page}/index.html and hand it over to me in my browser."
        )
    else:
        tooling = (
            "Build with ordinary HTML, CSS and JavaScript. No Leaf instructions, "
            "widgets or runtime are available. Check your output in the browser and "
            "fix findings."
        )
        handover = (
            f"Write the page at {page}/index.html; I'll open it in my browser. "
            "Reply with one line naming the path, and I'll answer here."
        )
    return f"""{tooling}

{handover} Produce a finished record with readable evidence and the choices or
navigation the request needs. You may use the browser tooling available on this
machine.

The user's request follows.

{request}"""


def preference_message() -> str:
    return f"{PREFERENCE} Please revise the page to follow it."


def comment_message(comment: Comment) -> str:
    """The comment as a user writes it in chat, or on a page whole."""
    return f"On {comment.target}: {comment.text}"


# What applying a decision means here, where no system takes it but the page.
APPLY = "Apply them: update the page so it records them as final."


def apply_message(decision: Decision, route: str, copied: str | None) -> str:
    """The user's request to apply the decision: made on the page, pasted from what
    the page offered to copy, or typed."""
    if route == "page":
        return f"I've made my decisions on the page. {APPLY}"
    if route == "copied":
        return (
            "I've made my decisions on the page, and this is what it gave me to "
            f"copy:\n\n{copied}\n\n{APPLY}"
        )
    return f"{decision.typed}\n\n{APPLY}"


def snapshot(page: Path, destination: Path) -> None:
    if page.exists():
        shutil.copytree(
            page,
            destination,
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )


def latest_seq(page: Path) -> int:
    events = read_events(page) if (page / "events.jsonl").exists() else []
    return max((e["seq"] for e in events), default=0)


def author(run: Run, cwd: Path) -> None:
    """Run the sample's live session through its phases, preserving each phase's
    page, and stop any server it left running."""
    cwd.mkdir(parents=True, exist_ok=True)
    (run.directory / "work-dir").write_text(str(cwd))
    run.state.mkdir(parents=True)
    page = run.authored_page
    leaf = run.leaf_condition
    prompt = first_prompt(run.payload, page, run.subject, run.condition)
    (run.directory / "prompt-1.txt").write_text(prompt)
    child = LiveChild(
        cwd,
        prompt,
        *(("--plugin-dir", str(run.payload)) if leaf else ()),
        stderr=run.directory / "err.txt",
        limit=TURN_LIMIT,
        timed_out=run.directory / "timed-out",
        dirs=[run.payload] if leaf else [],
        env=(
            {"LEAF": str(run.payload / "bin/leaf"), "XDG_STATE_HOME": str(run.state)}
            if leaf
            else {}
        ),
        harness=run.harness,
    )
    try:
        with LiveSession(
            child,
            run.directory / "stream.jsonl",
            watch=(run.payload, run.state, page) if leaf else None,
        ) as live:
            for phase in phases(run.subject):
                live.note({"type": "eval_phase", "phase": phase, "received_at": now()})
                since = live.answered
                run.phase_starts[phase] = latest_seq(page)
                before = None
                if phase == 2:
                    live.send(preference_message())
                elif phase == 3:
                    before = comment(run, live)
                elif phase == 4:
                    decision_round(run, live)
                settled = live.settle(since, grace=GRACE, wake=WAKE, before=before)
                snapshot(page, run.directory / f"page-phase{phase}")
                if not settled or not (page / "index.html").exists():
                    break
                if leaf and not live.url:
                    break
    finally:
        if leaf:
            run.leaf("server", "stop", str(page))


def comment(run: Run, live: LiveSession):
    """Send the scenario's comment: from a selection on the served Leaf page, or
    in chat. On Leaf, record its delivery, `eval_received`, if it has arrived, and
    return the check that records it ahead of the record that shows it."""
    scenario = CASES[run.subject]
    remark = scenario.comment
    if not run.leaf_condition:
        live.send(comment_message(remark))
        return None
    posted = live.during(
        lambda: comment_on_passage(
            live.url,
            remark.quotes,
            remark.text,
            comment_message(remark),
            scenario.reveal,
        )
    )
    live.note({"type": "eval_post", **posted, "received_at": now()})
    event = next(
        e
        for e in read_events(run.authored_page)
        if e.get("attempt") == posted["attempt"]
    )
    run.record(
        "comment", {**posted, "event": event["id"], "anchor": event.get("anchor")}
    )
    delivered = False

    def received(record: dict | None = None) -> None:
        nonlocal delivered
        if not delivered and event["id"] in opened_input_ids(
            read_events(run.authored_page)
        ):
            delivered = True
            live.note(
                {"type": "eval_received", "event": event["id"], "received_at": now()}
            )

    # The hook may have delivered it while the browser was still posting.
    received()
    return received


def decision_round(run: Run, live: LiveSession) -> None:
    """Make the scenario's decision on the page as its user, then ask for it to be
    applied, recording the route the request took: what the page gave to copy
    where it offered that, the page itself where it sent the decision to the
    agent's log, and otherwise the decision typed."""
    decision = CASES[run.subject].decision
    page = run.authored_page
    before = latest_seq(page)

    def deciding():
        if run.leaf_condition:
            return decide(live.url, decision.task, run.directory / "user")
        with arrangement_plain.serving(page) as url:
            return decide(url, decision.task, run.directory / "user")

    made = live.during(deciding)
    # What the page sent the agent: the user's inputs admission marked as owing it
    # attention, rather than bookkeeping such as a read receipt.
    gestures = [
        {k: e.get(k) for k in ("kind", "widget", "action", "detail", "text")}
        for e in (read_events(page) if run.leaf_condition else [])
        if e["seq"] > before
        and e.get("author") == "user"
        and requires_agent_attention(e)
    ]
    copied = (made["copies"] or [None])[-1] or made["copied"]
    # The user copies only where the page has no way to send the decision, so
    # what it copied is the handover even beside inputs the page sent.
    if made["made"] and copied:
        route = "copied"
    elif made["made"] and gestures:
        route = "page"
    else:
        route = "typed"
    message = apply_message(decision, route, copied)
    run.record(
        "decision",
        {**made, "gestures": gestures, "route": route, "message": message},
    )
    live.send(message)


def answers_in_phase(run: Run, phase: int) -> list[str]:
    """The agent's page messages from `phase` on, which a Leaf agent may answer
    in rather than in chat."""
    start = run.phase_starts.get(phase, 0)
    return [
        f"{e.get('title') or ''} {e.get('text') or ''}".strip()
        for e in read_events(run.authored_page)
        if e["seq"] > start
        and e.get("author") == "agent"
        and e["kind"] in MESSAGE_KINDS
    ]


READING = """{situation} For each item below, give one of its listed values, or
"undecided" where nothing says.

{items}"""


def items(decision: Decision) -> str:
    return "\n".join(
        f"- {item}: {' | '.join(values)}" for item, values in decision.values.items()
    )


def reading_schema(decision: Decision) -> str:
    """The reader's answer, which the harness's structured output holds to each
    item's listed values."""
    return json.dumps(
        {
            "type": "object",
            "properties": {
                item: {"type": "string", "enum": [*values, "undecided"]}
                for item, values in decision.values.items()
            },
            "required": list(decision.values),
            "additionalProperties": False,
        }
    )


def matches(decision: Decision, reading: dict | None) -> dict[str, bool]:
    """Each item, and whether the reading gives its chosen value."""
    return {
        item: reading is not None and reading[item] == chosen
        for item, chosen in decision.chosen.items()
    }


def read_applied(run: Run, reply: str) -> dict:
    """What the agent applied, read by a judge from the final page's authored
    files, with its answers in the decision phase only to point the way."""
    decision = CASES[run.subject].decision
    evidence = run.directory / "applied"
    files = evidence / "page"
    page = run.authored_page
    for found in authored_files(page, run.condition):
        target = files / found.relative_to(page)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(found, target)
    answer = evidence / "answer.txt"
    answer.write_text(
        "\n\n".join([reply, *answers_in_phase(run, 4)]) if run.leaf_condition else reply
    )
    listed = "\n".join(
        f"- {path}" for path in sorted(files.rglob("*")) if path.is_file()
    )
    prompt = READING.format(
        situation="A user had an assistant build a page, made decisions on it and "
        "asked the assistant to update the page so it records them as final. Read "
        f"the page's files:\n{listed}\n\nand the assistant's answers at {answer}. "
        "Say what the page's files now record as the final decision. The answers "
        "may tell you where to look, but what they claim counts only where the "
        "files show it.",
        items=items(decision),
    )
    (evidence / "prompt.txt").write_text(prompt)
    with scratch() as cwd:
        trace = run_agent(
            cwd,
            prompt,
            "--tools",
            "Read",
            "--json-schema",
            reading_schema(decision),
            out=evidence / "stream.jsonl",
            err=evidence / "err.txt",
            dirs=[evidence],
            model=MODELS["judge"],
        )
    reading = trace_result(trace).get("structured_output")
    return {
        "reading": reading,
        "items": matches(decision, reading),
        "trace": trace_summary(trace),
    }


def read_decision(run: Run) -> dict:
    """The user's decision as a fresh Leaf reader reports it from the page's state,
    without the author's conversation."""
    decision = CASES[run.subject].decision
    page = run.authored_page
    destination = run.directory / "reader"
    destination.mkdir()
    source_before = (page / "index.html").read_bytes()
    events_before = (page / "events.jsonl").read_bytes()
    prompt = READING.format(
        situation=f"Read the Leaf skill at {run.payload}/skills/leaf/SKILL.md. The "
        f"page at {page} has been reviewed by a user who made decisions on it. Read "
        "its current state: what did the user decide? Don't edit the page or serve "
        "it.",
        items=items(decision),
    )
    (destination / "prompt.txt").write_text(prompt)
    with scratch() as work:
        trace = run_agent(
            work,
            prompt,
            "--json-schema",
            reading_schema(decision),
            out=destination / "stream.jsonl",
            err=destination / "err.txt",
            dirs=[run.payload, page],
            env={
                "LEAF": str(run.payload / "bin/leaf"),
                "XDG_STATE_HOME": str(run.state),
            },
            harness=run.harness,
        )
    reading = trace_result(trace).get("structured_output")
    return {
        "completed": completed(trace),
        "page_unchanged": source_before == (page / "index.html").read_bytes()
        and events_before == (page / "events.jsonl").read_bytes(),
        "reading": reading,
        "items": matches(decision, reading),
        "trace": trace_summary(trace),
    }


def chosen_options(page: Path | None) -> set[str]:
    """The `lf-option`s a Leaf page's markup marks chosen."""
    if page is None:
        return set()
    return {
        r["attrs"]["id"]
        for r in SourceDocument((page / "index.html").read_text()).lf_elements
        if r["tag"] == "lf-option" and "chosen" in r["attrs"] and "id" in r["attrs"]
    }


def gate(run: Run, phase: int, page: Path) -> dict:
    """Independently check the authored page, retaining the check's output."""
    if run.condition == "html":
        reading = arrangement_plain.gate(page, WIDTHS)
    else:
        proc = run.leaf("page", "check", str(page), "--render", timeout=900)
        reading = {"passed": proc.returncode == 0, "output": proc.stdout + proc.stderr}
    (run.directory / f"gate-{phase}.json").write_text(json.dumps(reading, indent=2))
    return reading


def capture_phase(
    run: Run, phase: int, page: Path | None = None
) -> dict[str, list[str]]:
    """Screenshot one version at each width, top to bottom, keyed by width, with
    the commented item open once the version carries the comment."""
    run.shots.mkdir(parents=True, exist_ok=True)
    captures = {name: [] for name in WIDTHS}
    page = page or run.page(phase)
    if page is None:
        return captures
    html = run.condition == "html"
    scenario = CASES[run.subject]
    opening = scenario.reveal if phase >= 3 and scenario.comment else ""
    server = (
        arrangement_plain.serving(page)
        if html
        else serving(run.payload, run.state, page)
    )

    def settled(view):
        if html:
            arrangement_plain.settle(view)
        else:
            rendered(view)
            settle(view)

    with server as url, chrome() as browser:
        for name, (viewport, _) in WIDTHS.items():
            with tab(browser, viewport=viewport, touch=name == "phone") as view:
                (arrangement_plain.load if html else load)(view, url)
                if opening:
                    reveal(view, opening, scenario.comment.applied, settled)
                height = view.evaluate("document.documentElement.scrollHeight")
                step = int(viewport[1] * 0.85)
                screens = min(16, 1 + max(0, height - viewport[1] + step - 1) // step)
                for index in range(screens):
                    view.evaluate(
                        "y => window.scrollTo({top: y, behavior: 'instant'})",
                        index * step,
                    )
                    settled(view)
                    path = run.shots / f"p{phase}-{name}-{index}.png"
                    view.screenshot(path=path)
                    captures[name].append(str(path))
    return captures


def capture(run: Run) -> dict[int, dict[str, list[str]]]:
    """Capture every phase's page."""
    return {phase: capture_phase(run, phase) for phase in phases(run.subject)}


AUTHORED = (".html", ".css", ".js", ".mjs", ".json")


def authored_files(page: Path, condition: str) -> list[Path]:
    """The text files the author wrote: all of an HTML page's; a Leaf page's
    document, its page-specific inputs and its data, leaving out what Leaf vendors."""
    if condition == "html":
        found = page.rglob("*")
    else:
        found = [
            page / "index.html",
            *(page / "page").rglob("*"),
            *(page / "data").rglob("*"),
        ]
    return sorted(f for f in found if f.is_file() and f.suffix in AUTHORED)


def authored_lines(page: Path, condition: str) -> dict[str, int]:
    """Non-blank CSS and script lines across the authored files, inline or separate,
    and the count of `style` attributes."""
    counts = {"css_lines": 0, "script_lines": 0, "style_attributes": 0}

    def lines(text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip())

    for file in authored_files(page, condition):
        if file.suffix == ".css":
            counts["css_lines"] += lines(file.read_text())
        elif file.suffix in (".js", ".mjs"):
            counts["script_lines"] += lines(file.read_text())
        elif file.suffix == ".html":
            # The parsed tree, template contents included, so a live sample's code
            # counts as the author's too.
            tree = turbohtml.parse(file.read_text())
            counts["css_lines"] += sum(lines(e.text) for e in tree.select("style"))
            counts["script_lines"] += sum(
                lines(e.text) for e in tree.select("script:not([src])")
            )
            counts["style_attributes"] += len(tree.select("[style]"))
    return counts


# A shell command that writes the page, and one that renders it in a browser. Both
# read command text, so they approximate: a write through some other program, or a
# browser run under another name, goes uncounted.
SHELL_WRITE = re.compile(
    r"sed -i|perl -\w*i|\.write\(|write_text\(|(>|tee)\s*\S*index\.html"
)
RENDER = re.compile(r"page check|playwright|chrom|puppeteer|screenshot", re.IGNORECASE)


def tool_work(trace: list[dict], page: Path) -> dict[str, int]:
    """The phase's writes to the page, its first draft plus each repair iteration,
    and the times it rendered the page to check it."""
    writes = renders = 0
    for block in blocks(trace):
        if block.get("type") != "tool_use":
            continue
        given = block.get("input", {})
        if block.get("name") in ("Write", "Edit", "MultiEdit"):
            writes += str(given.get("file_path", "")).startswith(f"{page}/")
        elif command := given.get("command"):
            writes += bool(
                SHELL_WRITE.search(command)
                and (str(page) in command or "index.html" in command)
            )
            renders += bool(RENDER.search(command))
    return {"page_writes": writes, "renders": renders}


def comment_applied(run: Run, page: Path) -> bool:
    """Whether the authored files carry the fact only the comment supplied: what an
    HTML file says (`SourceReading`), any other file whole."""
    text = " ".join(
        SourceReading(SourceDocument(f.read_text()), {}).passages.text
        if f.suffix == ".html"
        else f.read_text()
        for f in authored_files(page, run.condition)
    )
    return (
        re.search(CASES[run.subject].comment.applied, " ".join(text.split()))
        is not None
    )


def comment_answer(run: Run, reply: str) -> str:
    """What the author told the user about their comment, where it was asked: its
    replies on the comment's thread in Leaf, its chat reply in HTML. The judge reads
    it (`rubrics`, "comment-answered")."""
    if not run.leaf_condition:
        return reply
    thread = run.recorded("comment").get("event")
    answers = (
        successful_replies(read_events(run.authored_page), thread) if thread else []
    )
    return "\n\n".join(
        f"{answer.get('title', '')}\n{answer['text']}".strip() for answer in answers
    )


def phase_traces(trace: list[dict]) -> dict[int, list[dict]]:
    """The session's records split at the harness's `eval_phase` marks."""
    split: dict[int, list[dict]] = {}
    current = None
    for record in trace:
        if record.get("type") == "eval_phase":
            current = record["phase"]
            split[current] = []
        elif current is not None:
            split[current].append(record)
    return split


def replies(trace: list[dict]) -> str:
    """Every turn's closing message in a phase, in order."""
    return "\n\n".join(
        r.get("result") or "" for r in trace if r.get("type") == "result"
    ).strip()


def listing(captures: dict[str, list[str]]) -> list[str]:
    """A version's screenshot paths as the judge reads them, by width."""
    lines = []
    for name, (_, label) in WIDTHS.items():
        lines.append(f"  On {label}, top to bottom:")
        lines += [f"    {path}" for path in captures[name]]
    return lines


def later_messages(subject: str, first: str = "version 1") -> list[str]:
    """The user's messages after the first version, as both judges read them."""
    scenario = CASES[subject]
    lines = [f'After {first}, the user added a standing preference: "{PREFERENCE}"']
    if comment := scenario.comment:
        lines += ["", f'Then the user commented: "{comment_message(comment)}"']
    if decision := scenario.decision:
        lines += [
            "",
            (
                "Then the user made these decisions on the page and asked for them "
                f'to be applied: "{decision.typed}"'
            ),
        ]
    return lines


def brief(
    subject: str, captures: dict[int, dict[str, list[str]]], answer: str = ""
) -> str:
    """What the judge reads: the request, the later messages, the author's `answer`
    to the comment, and each version's screenshots."""
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        *later_messages(subject),
        "",
        "Each message after the request produced the next version.",
    ]
    if CASES[subject].comment:
        lines += [
            "",
            "The author answered the comment:",
            f"<answer>\n{answer or '(no answer)'}\n</answer>",
        ]
    for phase in phases(subject):
        lines += ["", f"Version {phase} screenshots:", *listing(captures[phase])]
    return "\n".join(lines)


JUDGING = (
    "Open every screenshot the output lists for version {phase} before judging. "
    "Each width's screenshots run top to bottom with overlap. Fixed viewer "
    f"controls are outside the page's content. {REACHABLE} Judge only what a user "
    "sees; don't infer interaction behavior from an unoperated screenshot. "
)


def rubrics(scenario: str) -> list[dict]:
    """The judged quality of each version, and of the revision against the preference.

    Splitting quality into separate verdicts would have the judge read every
    screenshot once per verdict; its reason names what failed."""
    return [
        *(
            {
                "type": "agent-rubric",
                "metric": f"phase-{phase}-quality",
                "value": JUDGING.format(phase=phase)
                + f"Pass only if, at every width, version {phase} keeps the request's "
                "substantive information, lets the user find and read the evidence, and "
                "provides the decisions or navigation the request needs. "
                + CASES[scenario].quality,
            }
            for phase in phases(scenario)
        ),
        {
            "type": "agent-rubric",
            "metric": "phase-2-preference",
            "value": JUDGING.format(phase=2)
            + "Pass only if version 2 follows the standing width preference the "
            "output quotes.",
        },
        *(
            [
                {
                    "type": "agent-rubric",
                    "metric": "comment-answered",
                    "value": "Pass only if the author's answer to the user's comment, "
                    "which the output quotes, tells the user that the change the "
                    "comment asked for is made.",
                }
            ]
            if CASES[scenario].comment
            else []
        ),
    ]


def expected_checks(case: str, *, condition="leaf") -> list[str]:
    """Common outcome checks apply to both tools; the hand-over, the comment's
    delivery and the fresh reader are Leaf's own."""
    if case not in CASES:
        raise ValueError(f"Unknown authored task: {case}")
    scenario, leaf = CASES[case], condition == "leaf"
    return [
        "completed",
        *(
            f"phase-{phase}-{check}"
            for phase in phases(case)
            for check in ("completed", "page", "render", "captures")
        ),
        *(["handed-over"] if leaf else []),
        *(["comment-delivered"] if leaf and scenario.comment else []),
        *(["comment-applied"] if scenario.comment else []),
        *(["decision-made", "decision-applied"] if scenario.decision else []),
        *(
            [
                "decision-reader-completed",
                "decision-reader-correct",
                "decision-reader-page-unchanged",
            ]
            if leaf and scenario.decision
            else []
        ),
    ]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    shots: Path,
    harness=ClaudeCodeHarness.name,
    condition="leaf",
) -> dict:
    """Execute only the selected condition; Promptfoo owns the condition matrix."""
    work.mkdir(parents=True, exist_ok=True)
    checks = dict.fromkeys(expected_checks(case, condition=condition), False)
    run = Run(case, payload, work, shots, harness, condition)
    scenario = CASES[case]
    diagnostics = {
        "subject": case,
        "harness": harness,
        "condition": condition,
        "phases": {},
    }
    harness_costs = []
    with scratch(payload) as child_work:
        author(run, child_work)
        trace = read_trace(work / "stream.jsonl")
        split = phase_traces(trace)
        order = list(phases(case))
        session = dict(
            zip(order, resumed([trace_summary(split.get(p, [])) for p in order]))
        )
        if run.leaf_condition:
            served = next((r["url"] for r in trace if r["type"] == "eval_served"), None)
            checks["handed-over"] = served is not None and served in replies(
                split.get(1, [])
            )
            if scenario.comment:
                checks["comment-delivered"] = any(
                    r["type"] == "eval_received" for r in trace
                )
                remark = run.recorded("comment")
                diagnostics["comment"] = remark
                # A comment that directs an outcome may be recorded as the user's
                # pick, which is right; record whether it was.
                diagnostics["comment_recorded_pick"] = sorted(
                    chosen_options(run.page(3)) - chosen_options(run.page(2))
                )
        if scenario.decision:
            made = run.recorded("decision")
            harness_costs.append((made.get("trace") or {}).get("cost_usd"))
            checks["decision-made"] = made.get("made") is True
            decision = {"made": made}
            if (run.authored_page / "index.html").exists() and 4 in split:
                applied = read_applied(run, replies(split[4]))
                harness_costs.append(applied["trace"]["cost_usd"])
                decision["applied"] = applied
                checks["decision-applied"] = all(applied["items"].values())
                if run.leaf_condition:
                    reader = read_decision(run)
                    harness_costs.append(reader["trace"]["cost_usd"])
                    decision["reader"] = reader
                    checks["decision-reader-completed"] = reader["completed"]
                    checks["decision-reader-correct"] = all(reader["items"].values())
                    checks["decision-reader-page-unchanged"] = reader["page_unchanged"]
            diagnostics["decision"] = decision
        captures = capture(run)
        answer = ""
        for phase in order:
            summary = session[phase]
            checks[f"phase-{phase}-completed"] = summary["completed"]
            page = run.page(phase)
            checks[f"phase-{phase}-page"] = page is not None
            checks[f"phase-{phase}-captures"] = all(captures[phase].values())
            row = {
                "trace": summary,
                "captures": captures[phase],
                **tool_work(split.get(phase, []), run.authored_page),
            }
            if page:
                reading = gate(run, phase, page)
                checks[f"phase-{phase}-render"] = reading["passed"]
                row |= {
                    "page": str(page),
                    "gate": reading,
                    **authored_lines(page, condition),
                }
                if phase == 3:
                    checks["comment-applied"] = comment_applied(run, page)
                    answer = comment_answer(run, summary["reply"])
            diagnostics["phases"][phase] = row
    checks["completed"] = all(checks[f"phase-{phase}-completed"] for phase in order)
    authoring = [session[p]["cost_usd"] for p in order]
    diagnostics["cost"] = {
        "author": observed_sum(authoring),
        "harness": observed_sum(harness_costs),
    }
    return {
        "output": brief(case, captures, answer),
        "metadata": {"checks": checks, "diagnostics": diagnostics},
        **(
            {"cost": cost}
            if (cost := observed_sum([*authoring, *harness_costs])) is not None
            else {}
        ),
    }
