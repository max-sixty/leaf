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
directory its judge may read. The YAML case holds native Promptfoo `agent-rubric`
assertions the judge grades from it, opening the screenshots and reading the answer.
Fixed checks cover execution, the render gate and whether the comment's fact reached
the page.
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
from leaf_dev.eval_cases import definition
from leaf_dev.usability_eval import admit, arm_fixture

TASKS = ROOT / "evals"
DEFINITION = definition("arrangement_eval")
WIDTHS = {
    name: (tuple(width["viewport"]), width["description"])
    for name, width in DEFINITION["widths"].items()
}
PREFERENCE = DEFINITION["preference"]


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
    comment: Comment | None = None


CASES = {
    name: Scenario(
        choice=case["inputs"]["choice"],
        comment=(
            Comment(**(comment | {"quotes": tuple(comment["quotes"])}))
            if (comment := case["inputs"].get("comment"))
            else None
        ),
    )
    for name, case in DEFINITION["cases"].items()
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
    return DEFINITION["prompts"]["first"][condition].format(
        payload=payload,
        page=page,
        request=(TASKS / subject / "request.md").read_text(),
    )


def second_prompt(page: Path, condition="leaf") -> str:
    return DEFINITION["prompts"]["second"][condition].format(
        page=page, preference=PREFERENCE
    )


def comment_prompt(page: Path, comment: Comment, condition="leaf") -> str:
    """The turn that carries the user's comment: on the page in Leaf, in chat in HTML."""
    return DEFINITION["prompts"]["comment"][condition].format(
        page=page, target=comment.target, text=comment.text
    )


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
        continuation = DEFINITION["prompts"]["continuation"].format(page=page)
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
            prompt = DEFINITION["prompts"]["choice_reader"].format(
                payload=run.payload, page=page, widget=widget
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
    it (the case's "comment-answered" assertion)."""
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
