"""Run usability tasks and give one Promptfoo agent their canonical evidence.

This module owns fixture setup, continuous native sessions and user-input
injection. It retains page state, active markup, data, events, delivery envelopes
and the full native trace for the judge, less the images the agent read. Task
correctness belongs to one YAML llm-rubric per case, not a parallel Python grader or
markup-shape rules.
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

from leaf.delivery import opened_input_ids
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.passages import SourceReading
from leaf.registry.kernel import kinds_declaring
from leaf.service import requires_agent_attention
from leaf.structure import SourceDocument
from leaf_dev import ROOT
from leaf_dev.arms import (
    TURN_LIMIT,
    LiveChild,
    LiveSession,
    PageClient,
    blocks,
    completed,
    environment,
    inputs_received,
    now,
    observed_sum,
    read_page_state,
    read_trace,
    resumed,
    run_leaf,
    scratch,
    trace_summary,
)
from leaf_dev.eval_cases import definition

FIXTURES = ROOT / "evals/usability/fixtures"
READING_FIXTURE = json.loads((FIXTURES / "reading-answers.json").read_text())
DEFINITION = definition("usability_eval")
FIXTURE_INPUTS = DEFINITION["fixtures"]
ELIDED_THREAD = json.loads((FIXTURES / "elided-thread.json").read_text())


@dataclass(frozen=True)
class Case:
    name: str
    prompts: tuple[str, ...]
    fixture: str | None = None
    # A live case's user moves, one tuple per round (`execute_live`).
    rounds: tuple[tuple[dict, ...], ...] = ()
    injection: tuple[str, ...] = ()


CASES = {
    name: Case(
        name,
        tuple(case["inputs"]["prompts"]),
        fixture=case["inputs"].get("fixture"),
        rounds=tuple(tuple(round) for round in case["inputs"].get("rounds", [])),
        injection=tuple(case["inputs"].get("injection", [])),
    )
    for name, case in DEFINITION["cases"].items()
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
        """Keep each chat phase distinct within the continuous native session."""
        phases = []
        for path in sorted(self.dir.glob("stream-*.jsonl")):
            phase = []
            for record in read_trace(path):
                if record["type"] == "eval_phase" and phase:
                    phases.append(phase)
                    phase = []
                phase.append(record)
            if phase:
                phases.append(phase)
        return phases

    def usable(self) -> bool:
        """Whether the native author finished the requested phases."""
        traces = self.traces()
        return (
            len(traces) == len(CASES[self.case].prompts)
            and all(completed(trace) for trace in traces)
            and not (self.dir / "timed-out").exists()
        )


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
            q["section"]
            for q in READING_FIXTURE["questions"]
            if q["surface"] == surface
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
            input_text=json.dumps(READING_FIXTURE["data"]["copier-config"]), check=True,
        )  # fmt: skip
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["reading"]["stamp"],
        check=True,
    )
    if 'id="cutover-mode"' in html:
        for move in READING_FIXTURE["moves"]:
            if move.get("undoes") == "previous":
                move = {**move, "undoes": page_events(page)[-1]["id"]}
            admit(run, page, move)


def build_diagnostics_report(run: Run, page: Path) -> None:
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "diagnostics-report.html").read_text())
    run.leaf(
        "page", "stamp", str(page), "--text",
        FIXTURE_INPUTS["diagnostics-report"]["stamp"], check=True,
    )  # fmt: skip


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
    inputs = FIXTURE_INPUTS["resume"]
    v1 = (FIXTURES / "resume-v1.html").read_text()
    v2 = (FIXTURES / "resume-v2.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(v1)
    run.leaf("page", "stamp", str(page), "--text", inputs["initial_stamp"], check=True)
    admit(run, page, {
        "kind": "comment", "revision": 1,
        "text": inputs["rerun_comment"],
        "anchor": anchor(v1, "rehearsal-result", inputs["rerun_quote"]),
    })  # fmt: skip
    rerun = page_events(page)[-1]["id"]
    (page / "index.html").write_text(v2)
    run.leaf(
        "page", "stamp", str(page), "--text",
        inputs["rerun_stamp"], check=True,
    )  # fmt: skip
    arm_fixture(
        run,
        "answer",
        str(page),
        rerun,
        inputs["rerun_answer"],
    )
    admit(run, page, {"kind": "resolve", "parent": rerun})
    admit(run, page, {
        "kind": "action", "revision": 2, "widget": "rollout", "action": "choose",
        "detail": {'value': ["opt-per-tenant"]},
    })  # fmt: skip
    admit(run, page, {
        "kind": "comment", "revision": 2,
        "text": inputs["batch_comment"],
        "anchor": anchor(v2, "batch-size", inputs["batch_quote"]),
    })  # fmt: skip
    # The previous session's last save: an unexplained date change, and a paragraph
    # inside the options that makes the save invalid, so the live page stays at v2.
    candidate = v2.replace(inputs["original_date"], inputs["unsaved_date"])
    candidate = candidate.replace(
        '<lf-options id="rollout" choose>',
        '<lf-options id="rollout" choose>\n' + inputs["invalid_child"],
    )
    assert candidate.count("3 November") == 1 and "approach-deadline" in candidate
    (page / "index.html").write_text(candidate)


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
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["constructs"]["stamp"],
        check=True,
    )
    admit(run, page, {
        "kind": "action", "revision": 1, "widget": "release-note", "action": "edit",
        "detail": {'value': FIXTURE_INPUTS["constructs"]["draft"]},
    })  # fmt: skip
    run.leaf("data", "set", str(page), "checkout-p95", input_text="231", check=True)


def build_board(run: Run, page: Path) -> None:
    """A board whose cards the user moved, one move undone."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "board.html").read_text())
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["board"]["stamp"],
        check=True,
    )
    for detail in FIXTURE_INPUTS["board"]["moves"]:
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
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["package"]["stamp"],
        check=True,
    )


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
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["shared-source"]["stamp"],
        check=True,
    )


def build_handoff(run: Run, page: Path) -> None:
    """A drafted page nobody has checked, served or stamped."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "backfill.html").read_text())


def build_cutover(run: Run, page: Path) -> None:
    """A drafted status page nobody has checked, served or stamped, whose card grid
    runs out of narrow windows and whose chart's labels shrink below reading size:
    readings only `page check --render` takes."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "cutover.html").read_text())


def render_findings(run: Run, page: Path, n: int) -> str | None:
    """What a render pass run when the version went live would deliver: the
    findings `page check --render` reports on the page as served and plain `page
    check` doesn't, in the check's own words, or None where it reports none. Both
    readings are kept beside the run."""
    readings = {}
    for name, flags in (("plain", ()), ("render", ("--render",))):
        out = run.leaf("page", "check", str(page), *flags).stdout
        readings[name] = json.loads(out[out.find('{"status"') :])
    (run.dir / f"render-round-{n}.json").write_text(json.dumps(readings, indent=1))
    plain = {(f["code"], f.get("text")) for f in readings["plain"]["findings"]}
    found = [
        f
        for f in readings["render"]["findings"]
        if (f["code"], f.get("text")) not in plain
    ]
    if not found:
        return None
    lines = "\n".join(f"- {f['severity']}: {f['text']}" for f in found)
    return f"`leaf page check --render` on the version you handed over:\n{lines}"


def build_mixed(run: Run, page: Path) -> None:
    """A stamped page another session handed over; its copy button's script
    throws on a click."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "mixed.html").read_text())
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["mixed"]["stamp"],
        check=True,
    )


def build_elided(run: Run, page: Path) -> None:
    """Start without the history, so setup cannot preload the hidden premise.

    The answered history is admitted after initial handover, before the question.
    """
    html = (FIXTURES / "elided.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(html)
    run.leaf(
        "page",
        "stamp",
        str(page),
        "--text",
        FIXTURE_INPUTS["elided"]["stamp"],
        check=True,
    )


def build_plan(run: Run, page: Path) -> None:
    """A stamped rollout page whose work the user is about to lay out: a table to
    refresh, a choice of first region, and a schedule still to write."""
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text((FIXTURES / "rollout.html").read_text())
    run.leaf(
        "page", "stamp", str(page), "--text", FIXTURE_INPUTS["plan"]["stamp"],
        check=True,
    )  # fmt: skip


def build_plan_resume(run: Run, page: Path) -> None:
    """The rollout page midway through another session's plan: the table refreshed,
    the user's first-region choice in, and the schedule and rollback steps still open,
    recorded nowhere but the plan."""
    inputs = FIXTURE_INPUTS["plan-resume"]
    html = (FIXTURES / "rollout.html").read_text()
    for old, new in inputs["latency"].items():
        html = html.replace(old, new)
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(html)
    run.leaf("page", "stamp", str(page), "--text", inputs["stamp"], check=True)
    run.leaf(
        "task", "plan", str(page), input_text=json.dumps(inputs["plan"]), check=True
    )
    admit(run, page, {
        "kind": "action", "revision": 1, "widget": "first-region", "action": "choose",
        "detail": {"value": [inputs["choice"]]},
    })  # fmt: skip


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
    "diagnostics-report": build_diagnostics_report,
    "board": build_board,
    "constructs": build_constructs,
    "resume": build_resume,
    "package": build_package,
    "shared-source": build_shared_source,
    "handoff": build_handoff,
    "cutover": build_cutover,
    "mixed": build_mixed,
    "elided": build_elided,
    "plan": build_plan,
    "plan-resume": build_plan_resume,
}


def build_fixture(run: Run, name: str, page: Path) -> None:
    if name in BUILDERS:
        BUILDERS[name](run, page)
    else:
        build_reading(run, page, name.removeprefix("reading").removeprefix("-") or None)


# Running


def execute(run: Run, work: Path) -> None:
    """One run: build the case's fixture, then play chat or page inputs in a live
    session. The caller keeps `work` alive through
    evidence capture; this function archives pages before returning or raising."""
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
            run.leaf("server", "stop", str(found))


# How long a finished session stays open for a trailing turn.
GRACE = 20


def execute_live(run: Run, case: Case, work: Path, page: Path) -> None:
    """Serve the case's page from a live session and play its user.

    Each round retains its admitted inputs until delivery is confirmed. The next
    round goes out at a turn's end, or during work for a declared running injection.
    An idle injection pauses so Leaf's watcher can take its lease. The session closes
    once the last round's turn ends or the session reaches TURN_LIMIT. Each turn's
    end records the page's status."""
    prompt = case.prompts[0].replace("{page}", str(page)).replace("{work}", str(work))
    (run.dir / "prompt-1.txt").write_text(prompt)
    closing: threading.Timer | None = None
    posted, delivered = 0, 0
    observed_tool_round = 0
    pending_events: set[str] = set()
    attempts: set[str] = set()
    try:
        with (
            LiveSession(
                LiveChild(
                    work,
                    prompt,
                    "--plugin-dir",
                    str(run.payload),
                    stderr=run.dir / "err-1.txt",
                    limit=TURN_LIMIT,
                    timed_out=run.dir / "timed-out",
                    dirs=[run.payload],
                    env={
                        "PATH": environment(payload=run.payload)["PATH"],
                        "XDG_STATE_HOME": str(run.state),
                    },
                    harness=run.harness,
                ),
                run.dir / "stream-1.jsonl",
                watch=(run.payload, run.state, page),
            ) as live,
            ExitStack() as deadlines,
        ):

            def received(record: dict) -> None:
                """Record a posted round's receipt ahead of the record that shows it."""
                nonlocal delivered
                if delivered < posted:
                    events = page_events(page)
                    if inputs_received(
                        events, attempts
                    ) and pending_events <= opened_input_ids(events):
                        delivered = posted
                        live.note(
                            {
                                "type": "eval_received",
                                "round": posted,
                                "events": sorted(pending_events),
                                "received_at": now(),
                            }
                        )

            for record in live.records(before=received):
                if delivered > observed_tool_round and any(
                    block.get("type") == "tool_use" for block in blocks([record])
                ):
                    observed_tool_round = delivered
                    live.note(
                        {
                            "type": "eval_first_tool_state",
                            "round": delivered,
                            "workflows": page_state(run, page)["workflows"],
                            "received_at": now(),
                        }
                    )
                url = live.url
                # Posting the next running round cannot replace an undelivered
                # round's evidence.
                if delivered < posted:
                    continue
                if not url or posted == len(case.rounds):
                    if record.get("type") == "result":
                        if closing is not None:
                            closing.cancel()
                        closing = threading.Timer(GRACE, live.close)
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
                active_turn = observed_active_turn(run, page, live.child)
                if run.case == "elided" and posted == 0:
                    append_elided_history(run, page)
                pending_events = post_round(
                    run, page, PageClient(url), case.rounds[posted], posted
                )
                attempts.update(
                    move.get("attempt", attempt_key(posted, i))
                    for i, move in enumerate(case.rounds[posted])
                    if move["kind"] not in ("error", "render")
                )
                posted += 1
                # A round that posted nothing, a render pass that found nothing, wakes
                # no turn, so the session closes as it would after that turn's end.
                if (
                    not pending_events
                    and posted == len(case.rounds)
                    and {m["kind"] for m in case.rounds[-1]} == {"render"}
                ):
                    closing = threading.Timer(GRACE, live.close)
                    deadlines.callback(closing.join)
                    deadlines.callback(closing.cancel)
                    closing.start()
                live.note(
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
        # A render pass's findings reach the agent as the page's error, the channel
        # a failure the browser saw takes; a clean pass delivers nothing.
        if move["kind"] == "render":
            if (text := render_findings(run, page, n)) is None:
                continue
            move = {"kind": "error", "text": text.replace("{", "{{").replace("}", "}}")}
        event = dict(move)
        if move["kind"] != "error":
            event["attempt"] = move.get("attempt", attempt_key(n, i))
        if "anchor" in move and not isinstance(move["anchor"], dict):
            event["anchor"] = anchor(html, *move["anchor"])
        if move.get("undoes") == "previous":
            event["undoes"] = posted_event(page, attempt_key(n, i - 1))["id"]
        if move.get("parent") == "latest":
            event["parent"] = [
                e for e in page_events(page) if e["kind"] in kinds_declaring("message")
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
    """Send ordinary chat turns through one session, allowing normal page handoff.

    The driver ends after the last answer settles; the author need not suppress
    serving or change its handoff to make the experiment finish.
    """
    prompts = [
        template.replace("{page}", str(page)).replace("{work}", str(work))
        for template in case.prompts
    ]
    for phase, prompt in enumerate(prompts, 1):
        (run.dir / f"prompt-{phase}.txt").write_text(prompt)
    with LiveSession(
        LiveChild(
            work,
            prompts[0],
            "--plugin-dir",
            str(run.payload),
            stderr=run.dir / "err-1.txt",
            limit=TURN_LIMIT,
            timed_out=run.dir / "timed-out",
            dirs=[run.payload],
            env={
                "PATH": environment(payload=run.payload)["PATH"],
                "XDG_STATE_HOME": str(run.state),
            },
            harness=run.harness,
        ),
        run.dir / "stream-1.jsonl",
        watch=(run.payload, run.state, page),
    ) as live:
        for phase, prompt in enumerate(prompts, 1):
            live.note({"type": "eval_phase", "phase": phase, "received_at": now()})
            since = live.answered
            if phase > 1:
                live.send(prompt)
            if not live.settle(since, grace=GRACE, wake=TURN_LIMIT):
                break


def ignore(directory, names):
    """Leave layer and service files out of a run's copy of a page."""
    return {
        n
        for n in names
        if n in ("runtime", "vendor", "widgets", "instructions", "service.json")
        or n.endswith((".lock", ".js", ".css"))
    }


def pages(*roots: Path) -> list[Path]:
    """Every page directory under `roots`."""
    return sorted(p.parent for root in roots for p in root.rglob("events.jsonl"))


# Canonical evidence


def page_state(run: Run, page: Path) -> dict:
    return read_page_state(run.payload, run.state, page)


def active_document(run: Run, page: Path) -> tuple[dict, SourceDocument]:
    """The page's state and Leaf's parse of the markup it serves: the active
    revision's, or `index.html` before a first stamp."""
    state = page_state(run, page)
    active = state.get("active") or {"file": "index.html"}
    return state, SourceDocument((page / active["file"]).read_text())


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    """One completion smoke check; Promptfoo's agent judges the task."""
    return ["completed"]


def evidence(run: Run, traces: list[list[dict]]) -> dict:
    """Give the judge canonical artifacts without a second per-case grading engine.

    Page state is Leaf's own reading; HTML/data/events retain the evidence behind
    it. Driver records expose native injection, delivery and first-tool progress
    observations as facts, without converting them into task-specific pass flags.
    """
    found = []
    for page in pages(run.work, run.state):
        state = page_state(run, page)
        active = state.get("active") or {"file": "index.html"}
        found.append(
            {
                "path": str(page),
                "state": state,
                "document": (page / active["file"]).read_text(),
                "data": {
                    str(path.relative_to(page)): json.loads(path.read_text())
                    for path in sorted((page / "data").rglob("*.json"))
                },
                "events": page_events(page),
            }
        )
    fixture = run.dir / "fixture"
    return {
        "pages": found,
        "fixture": {
            str(path.relative_to(fixture)): path.read_text()
            for path in sorted(fixture.rglob("*"))
            if path.is_file() and path.suffix in (".html", ".json", ".jsonl")
        },
        "delivery_envelopes": [
            json.loads(path.read_text())
            for path in sorted((run.state / "leaf/deliveries").glob("*.json"))
        ],
        "driver": [
            record
            for trace in traces
            for record in trace
            if record["type"].startswith("eval_")
        ],
        "trace": [
            {"phase": phase, "records": without_images(trace)}
            for phase, trace in enumerate(traces, 1)
        ],
    }


def without_images(value):
    """`value` with each image block the agent read reduced to a marker. The text
    judge reads no images, and a few screenshots' base64 overflow its prompt."""
    if isinstance(value, dict):
        if value.get("type") in ("image", "input_image"):
            return {"type": value["type"], "omitted": True}
        return {key: without_images(item) for key, item in value.items()}
    if isinstance(value, list):
        return [without_images(item) for item in value]
    return value


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    """One Promptfoo provider call owns all phases, live rounds, and evidence.

    The one completion check covers execution; the YAML agent rubric receives
    the final canonical artifacts and complete native trajectory."""
    run = Run(case, payload, work, harness)
    with scratch(payload, state=run.state) as child_work:
        execute(run, child_work)
        traces = run.traces()
        phases = resumed([trace_summary(t) for t in traces])
        replies = [p["reply"] for p in phases]
        usable = run.usable()
        artifacts = evidence(run, traces)
    texts = {"evidence": json.dumps(artifacts, ensure_ascii=False)}
    checks = {"completed": usable}
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
            "diagnostics": {"phases": phases, "driver": artifacts["driver"]},
        },
    }
