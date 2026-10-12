"""Author, revise and read one page-task sample under its explicit condition.

Leaf and ordinary HTML receive the same task, the same width revision and, where the
task declares one, the same user comment on the revised page. Leaf receives the
comment as the user's anchored comment on the page; HTML receives it in chat, naming
the passage in words, which is how its user would send it. Each sample
contains only its selected condition; the HTML child sees no Leaf payload,
instructions or runtime. CC and Codex authors use the shared harness interface.
Each phase records what the author spent and wrote: its trace's time and tokens,
the CSS and script lines in the files it authored, and how many times it wrote and
rendered the page, the measure of its repair iterations.

The sample's output is what a judge needs: the user's request, the author's answer to
the comment, and each version's screenshots by width, written to `shots`, the one
directory its judge may read. `rubrics` are the Promptfoo `agent-rubric` assertions
the judge grades from it, opening the screenshots and reading the answer; the fixed
checks cover execution, the render gate and whether the comment's fact reached the
page.
For a task that asks for a decision, Leaf also seeds a choice after the common
comparison, asks a fresh reader for its current state, and checks that a separate
resumed revision preserves that choice. Readable records have no invented decision.
"""

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import turbohtml
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.passages import SourceReading
from leaf.render_checks import rendered
from leaf.structure import SourceDocument
from leaf.thread import successful_replies

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arms import (
    blocks,
    completed,
    observed_sum,
    read_trace,
    resumed,
    run_agent,
    run_leaf,
    scratch,
    serving,
    trace_summary,
)
from leaf_dev.arms import trace_result as result
from leaf_dev.browser import chrome, load, settle, tab
from leaf_dev.usability_eval import admit, arm_fixture

TASKS = ROOT / "evals"
WIDTHS = {
    "laptop": ((1440, 900), "a 1440px laptop window"),
    "narrow": ((900, 900), "a 900px window"),
    "short": ((900, 600), "a short 900px by 600px window"),
    "phone": ((390, 844), "a 390px phone"),
}
PREFERENCE = (
    '"A standing preference for all my pages from now on: I read them in a window about '
    "900px wide, beside my editor. At that width, keep the page's summary, status, "
    'contents or queue beside the main content rather than stacked above or below it."'
)


@dataclass(frozen=True)
class Comment:
    """The user's comment on the width-revised page, the same in both conditions.

    `target` names the passage in words, as a user writing in chat would. Leaf
    anchors the comment on the first of `quotes` the active revision holds once, and
    otherwise comments on the page whole, naming the target. `applied` names a fact
    only the comment supplies, which the authored files carry once the change is made
    and the answer carries when it tells the user so."""

    target: str
    quotes: tuple[str, ...]
    text: str
    applied: str


@dataclass(frozen=True)
class Scenario:
    choice: bool
    quality: str = ""
    comment: Comment | None = None


CASES = {
    "document": Scenario(
        choice=True,
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
    ),
    "dashboard": Scenario(
        choice=True,
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
    ),
    "queue": Scenario(
        choice=True,
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
    ),
    "configuration": Scenario(
        choice=False,
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
    ),
    "sidebar-page-at-900px": Scenario(
        choice=False,
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

    @property
    def needs_choice(self) -> bool:
        return self.condition == "leaf" and CASES[self.subject].choice

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


def phases(subject: str) -> tuple[int, ...]:
    """Authoring, the width revision, and the comment where the task has one."""
    return (1, 2, 3) if CASES[subject].comment else (1, 2)


def first_prompt(payload: Path, page: Path, subject: str, condition="leaf") -> str:
    request = (TASKS / subject / "request.md").read_text()
    tooling = (
        f"You have the Leaf skill at {payload}/skills/leaf/SKILL.md. Read and follow it, "
        f"resolving references from {payload}/skills/leaf/. $LEAF is {payload}/bin/leaf. "
        f"Check the page with `$LEAF page check {page} --render`, fix findings and stamp it."
        if condition == "leaf"
        else "Build with ordinary HTML, CSS and JavaScript. No Leaf instructions, widgets "
        "or runtime are available. Check your output in the browser and fix findings."
    )
    return f"""{tooling}

Write the page at {page}/index.html. This run is non-interactive: nobody will
answer in the page. Produce a finished record with readable evidence and the
choices or navigation the request needs. You may use the browser tooling available
on this machine. Do not start an agent feedback watcher or wait for input. Reply
with one line naming the path.

The user's request follows.

{request}"""


def second_prompt(page: Path, condition="leaf") -> str:
    check = (
        f"Check it with `$LEAF page check {page} --render`, fix findings and stamp it."
        if condition == "leaf"
        else "Check your output in the browser and fix findings."
    )
    return f"""The user writes:

{PREFERENCE}

Revise the page at {page} to follow this preference. {check}
Do not start an agent feedback watcher or wait for input. Reply with its path.
"""


def comment_prompt(page: Path, comment: Comment, condition="leaf") -> str:
    """The turn that carries the user's comment: on the page in Leaf, in chat in HTML."""
    if condition == "leaf":
        return f"""The user has left a comment on the page at {page}. Handle it.
Check with `$LEAF page check {page} --render`, fix findings and stamp the revision.
Do not start an agent feedback watcher or wait for input. Reply with its path.
"""
    return f"""The user writes about the page at {page}:

"On {comment.target}: {comment.text}"

Handle it. Check your output in the browser and fix findings.
Do not start an agent feedback watcher or wait for input. Reply with its path.
"""


def post_comment(run: Run) -> None:
    """Admit the scenario's comment through the arm's browser door."""
    comment = CASES[run.subject].comment
    arm_fixture(
        run,
        "comment",
        str(run.authored_page),
        json.dumps(
            [
                comment.quotes,
                comment.text,
                f"On {comment.target}: {comment.text}",
                COMMENT_ATTEMPT,
            ]
        ),
    )


COMMENT_ATTEMPT = "arrangement-comment-0001"


def posted_comment(page: Path) -> dict | None:
    return next(
        (e for e in read_events(page) if e.get("attempt") == COMMENT_ATTEMPT), None
    )


def snapshot(page: Path, destination: Path) -> None:
    if page.exists():
        shutil.copytree(
            page,
            destination,
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )


def author(run: Run, cwd: Path) -> None:
    """Author, revise and answer the comment in one harness session, preserving each
    phase's page."""
    cwd.mkdir(parents=True, exist_ok=True)
    (run.directory / "work-dir").write_text(str(cwd))
    run.state.mkdir(parents=True)
    page = run.authored_page
    comment = CASES[run.subject].comment
    prompts = [
        first_prompt(run.payload, page, run.subject, run.condition),
        second_prompt(page, run.condition),
        *([comment_prompt(page, comment, run.condition)] if comment else []),
    ]
    for phase, prompt in enumerate(prompts, 1):
        (run.directory / f"prompt-{phase}.txt").write_text(prompt)
    child = {
        "dirs": [run.payload] if run.condition == "leaf" else [],
        "env": (
            {"LEAF": str(run.payload / "bin/leaf"), "XDG_STATE_HOME": str(run.state)}
            if run.condition == "leaf"
            else {}
        ),
        "harness": run.harness,
    }
    session = None
    for phase, prompt in enumerate(prompts, 1):
        if phase == 3 and run.condition == "leaf":
            post_comment(run)
        trace = run_agent(
            cwd,
            prompt,
            *(("--resume", session) if session else ()),
            out=run.directory / f"stream-{phase}.jsonl",
            err=run.directory / f"err-{phase}.txt",
            **child,
        )
        snapshot(page, run.directory / f"page-phase{phase}")
        session = result(trace).get("session_id") if completed(trace) else None
        if not session or not page.exists():
            return
    if run.needs_choice:
        seed_and_read_choice(run)
        continuation = (
            f"The user has reviewed {page}. Add a short Review status note saying "
            "it has now been reviewed. Preserve their existing decisions. "
            f"Check with `$LEAF page check {page} --render` and stamp the revision. "
            "Do not start a watcher or wait for input. Reply with its path."
        )
        (run.directory / "prompt-continuation.txt").write_text(continuation)
        run_agent(
            cwd,
            continuation,
            "--resume",
            session,
            out=run.directory / "stream-continuation.jsonl",
            err=run.directory / "err-continuation.txt",
            **child,
        )
        snapshot(page, run.directory / "page-continuation")


# The reader's answer, which the harness's structured output holds to this shape.
SELECTED_OPTIONS = {
    "type": "object",
    "properties": {"options": {"type": "array", "items": {"type": "string"}}},
    "required": ["options"],
    "additionalProperties": False,
}


def seed_and_read_choice(run: Run) -> None:
    """Admit a real user choice, then read it without the author's conversation."""
    page = run.authored_page
    record = {"seeded": False}
    elements = SourceDocument((page / "index.html").read_text()).lf_elements
    options = [
        r
        for r in elements
        if r["tag"] == "lf-option"
        and "chosen" not in r["attrs"]
        and r["holder"]
        and "choose" in r["holder"]["attrs"]
    ]
    if options:
        option = options[-1]
        widget, chosen = option["holder"]["attrs"]["id"], option["attrs"]["id"]
        state = json.loads(run.leaf("page", "state", str(page)).stdout)
        admit(
            run,
            page,
            {
                "kind": "action",
                "widget": widget,
                "action": "choose",
                "revision": state["active"]["revision"],
                "detail": {"value": [chosen]},
                "attempt": "authored-choice-0001",
            },
        )
        record = {
            "seeded": True,
            "widget": widget,
            "options": [chosen],
            "revision": state["active"]["revision"],
        }
        source_before = (page / "index.html").read_bytes()
        events_before = (page / "events.jsonl").read_bytes()
        destination = run.directory / "reader"
        destination.mkdir()
        with scratch() as work:
            prompt = (
                f"Read the Leaf skill at {run.payload}/skills/leaf/SKILL.md. "
                f"The page at {page} has been reviewed by a user. Read its current "
                f"state: which option ids are selected in {widget}? Don't edit "
                "the page or serve it."
            )
            (destination / "prompt.txt").write_text(prompt)
            trace = run_agent(
                work,
                prompt,
                "--json-schema",
                json.dumps(SELECTED_OPTIONS),
                out=destination / "stream.jsonl",
                err=destination / "err.txt",
                dirs=[run.payload, page],
                env={
                    "LEAF": str(run.payload / "bin/leaf"),
                    "XDG_STATE_HOME": str(run.state),
                },
                harness=run.harness,
            )
        answer = result(trace).get("structured_output")
        record |= {
            "completed": completed(trace),
            "page_unchanged": source_before == (page / "index.html").read_bytes()
            and events_before == (page / "events.jsonl").read_bytes(),
            "answer": answer,
            "correct": answer == {"options": [chosen]},
            "trace": trace_summary(trace),
        }
    (run.directory / "choice.json").write_text(json.dumps(record, indent=2))


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
    """Screenshot one version at each width, top to bottom, keyed by width."""
    run.shots.mkdir(parents=True, exist_ok=True)
    captures = {name: [] for name in WIDTHS}
    page = page or run.page(phase)
    if page is None:
        return captures
    server = (
        arrangement_plain.serving(page)
        if run.condition == "html"
        else serving(run.payload, run.state, page)
    )
    with server as url, chrome() as browser:
        for name, (viewport, _) in WIDTHS.items():
            with tab(browser, viewport=viewport, touch=name == "phone") as view:
                (arrangement_plain.load if run.condition == "html" else load)(view, url)
                height = view.evaluate("document.documentElement.scrollHeight")
                step = int(viewport[1] * 0.85)
                screens = min(16, 1 + max(0, height - viewport[1] + step - 1) // step)
                for index in range(screens):
                    view.evaluate(
                        "y => window.scrollTo({top: y, behavior: 'instant'})",
                        index * step,
                    )
                    if run.condition == "html":
                        arrangement_plain.settle(view)
                    else:
                        rendered(view)
                        settle(view)
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
    if run.condition == "html":
        return reply
    comment = posted_comment(run.authored_page)
    answers = (
        successful_replies(read_events(run.authored_page), comment["id"])
        if comment
        else []
    )
    return "\n\n".join(
        f"{answer.get('title', '')}\n{answer['text']}".strip() for answer in answers
    )


def listing(captures: dict[str, list[str]]) -> list[str]:
    """A version's screenshot paths as the judge reads them, by width."""
    lines = []
    for name, (_, label) in WIDTHS.items():
        lines.append(f"  On {label}, top to bottom:")
        lines += [f"    {path}" for path in captures[name]]
    return lines


def brief(
    subject: str, captures: dict[int, dict[str, list[str]]], answer: str = ""
) -> str:
    """What the judge reads: the request, the later preference and comment, the
    author's `answer` to the comment, and each version's screenshots."""
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        f"After version 1, the user added a standing preference: {PREFERENCE}",
    ]
    if comment := CASES[subject].comment:
        lines += [
            "",
            f'After version 2, the user commented: "On {comment.target}: {comment.text}"',
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
    "controls are outside the page's content, and a region with its own "
    "scroll shows only its first screen. Judge only what a user sees; don't infer "
    "interaction behavior from an unoperated screenshot. "
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
    """Common outcome checks apply to both tools, without Leaf routing in HTML."""
    if case not in CASES:
        raise ValueError(f"Unknown authored task: {case}")
    return [
        "completed",
        *(
            f"phase-{phase}-{check}"
            for phase in phases(case)
            for check in ("completed", "page", "render", "captures")
        ),
        *(["comment-applied"] if CASES[case].comment else []),
        *(
            [
                "choice-seeded",
                "choice-reader-completed",
                "choice-reader-correct",
                "choice-reader-page-unchanged",
                "choice-continuation-completed",
                "choice-revised",
                "choice-preserved",
            ]
            if condition == "leaf" and CASES[case].choice
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
    diagnostics = {
        "subject": case,
        "harness": harness,
        "condition": condition,
        "phases": {},
    }
    with tempfile.TemporaryDirectory(prefix="leaf-author-") as temporary:
        author(run, Path(temporary) / "cwd")
        # The phases and the continuation are one resumed session.
        turns = [
            *map(str, phases(case)),
            *(["continuation"] if run.needs_choice else []),
        ]
        session = dict(
            zip(
                turns,
                resumed(
                    [
                        trace_summary(read_trace(work / f"stream-{t}.jsonl"))
                        for t in turns
                    ]
                ),
            )
        )
        costs = [turn["cost_usd"] for turn in session.values()]
        if run.needs_choice:
            choice_path = work / "choice.json"
            choice = json.loads(choice_path.read_text()) if choice_path.exists() else {}
            diagnostics["choice"] = choice
            checks["choice-seeded"] = choice.get("seeded") is True
            checks["choice-reader-completed"] = choice.get("completed") is True
            checks["choice-reader-correct"] = choice.get("correct") is True
            checks["choice-reader-page-unchanged"] = (
                choice.get("page_unchanged") is True
            )
            continuation = session["continuation"]
            checks["choice-continuation-completed"] = continuation["completed"]
            diagnostics["continuation"] = continuation
            if choice.get("seeded"):
                state = json.loads(
                    run.leaf("page", "state", str(run.authored_page)).stdout
                )
                checks["choice-revised"] = (
                    state["active"]["revision"] != choice["revision"]
                )
                standing = [
                    s
                    for s in state["state"]
                    if s["widget"] == choice["widget"] and s["action"] == "choose"
                ]
                document = SourceDocument(
                    (run.authored_page / "index.html").read_text()
                )
                authored_choice = [
                    r["attrs"]["id"]
                    for r in document.lf_elements
                    if r["tag"] == "lf-option"
                    and "chosen" in r["attrs"]
                    and r["holder"]
                    and r["holder"]["attrs"].get("id") == choice["widget"]
                ]
                checks["choice-preserved"] = (
                    standing[0]["detail"]["value"] if standing else authored_choice
                ) == choice["options"]
                reader_trace = choice["trace"]
                costs.append(reader_trace["cost_usd"])
        captures = capture(run)
        answer = ""
        for phase in phases(case):
            trace = session[str(phase)]
            checks[f"phase-{phase}-completed"] = trace["completed"]
            page = run.page(phase)
            checks[f"phase-{phase}-page"] = page is not None
            checks[f"phase-{phase}-captures"] = all(captures[phase].values())
            row = {
                "trace": trace,
                "captures": captures[phase],
                **tool_work(
                    read_trace(work / f"stream-{phase}.jsonl"), run.authored_page
                ),
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
                    answer = comment_answer(run, trace["reply"])
            diagnostics["phases"][phase] = row
        if run.condition == "leaf" and CASES[case].comment:
            comment = posted_comment(run.authored_page)
            diagnostics["comment_anchor"] = (comment or {}).get("anchor")
    checks["completed"] = all(
        checks[f"phase-{phase}-completed"] for phase in phases(case)
    )
    return {
        "output": brief(case, captures, answer),
        "metadata": {"checks": checks, "diagnostics": diagnostics},
        **({"cost": cost} if (cost := observed_sum(costs)) is not None else {}),
    }
