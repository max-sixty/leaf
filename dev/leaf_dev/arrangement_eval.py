"""Author, revise and read one page-task sample under its explicit condition.

Leaf and ordinary HTML receive the same task and revision request. Each sample
contains only its selected condition; the HTML child sees no Leaf payload,
instructions or runtime. CC and Codex authors use the shared host interface.

The sample's output is what a judge needs: the user's request and each version's
screenshots by width. `rubrics` are the Promptfoo `agent-rubric` assertions a judge
grades from it, opening the screenshots with its Read tool; the fixed checks cover
execution and the render gate. Leaf also seeds a choice after the common
comparison, asks a fresh reader for its current state, and checks that a separate
resumed revision preserves that choice.
"""

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from leaf.render_checks import rendered
from leaf.structure import SourceDocument

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.browser import chrome, load, settle, tab
from leaf_dev.harness import (
    blocks,
    completed,
    observed_sum,
    read_trace,
    run_agent,
    run_leaf,
    serving,
    token_counts,
)
from leaf_dev.harness import trace_result as result
from leaf_dev.usability_eval import admit

TASKS = ROOT / "evals"
CASES = ("document", "dashboard", "queue")
PHASES = (1, 2)
WIDTHS = {
    "laptop": ((1440, 900), "a 1440px laptop window"),
    "narrow": ((900, 900), "a 900px window"),
    "phone": ((390, 844), "a 390px phone"),
}
PREFERENCE = (
    '"A standing preference for all my pages from now on: I read them in a window about '
    "900px wide, beside my editor. At that width, keep the page's summary, status, "
    'contents or queue beside the main content rather than stacked above or below it."'
)

VOCAB = {
    **{
        f"layout-{kind}": rf"class=\"[^\"]*\blayout-{kind}\b"
        for kind in ("column", "wide", "sidebar", "tiles", "workspace")
    },
    "lf-pane": r"<lf-pane\b",
    "data-width": r"\bdata-width=",
    "data-rail": r"\bdata-rail=",
    "panel": r"class=\"[^\"]*(?<![\w-])panel\b",
    "sidebar": r"class=\"[^\"]*(?<![\w-])sidebar\b",
    "sidenote": r"class=\"[^\"]*(?<![\w-])sidenote\b",
    "data-bound": r"\bdata-bound=",
    "lf-tabs": r"<lf-tabs\b",
}


@dataclass(frozen=True)
class Run:
    subject: str
    payload: Path
    directory: Path
    host: str = "cc"
    condition: str = "leaf"

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
        page = self.directory / ("page" if phase == 2 else "page-phase1")
        return page if (page / "index.html").exists() else None


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
answer in the page. Produce a finished record with readable evidence and usable
choices. You may use the browser tooling available on this machine. Do not start
an agent feedback watcher or wait for input. Reply with one line naming the path.

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


def author(run: Run, cwd: Path) -> None:
    """Author and revise with the same host session, preserving the initial page."""
    cwd.mkdir(parents=True, exist_ok=True)
    (run.directory / "work-dir").write_text(str(cwd))
    run.state.mkdir(parents=True)
    page = run.authored_page
    prompts = [
        first_prompt(run.payload, page, run.subject, run.condition),
        second_prompt(page, run.condition),
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
        "host": run.host,
    }
    first = run_agent(
        cwd,
        prompts[0],
        out=run.directory / "stream-1.jsonl",
        err=run.directory / "err-1.txt",
        **child,
    )
    if page.exists():
        shutil.copytree(
            page,
            run.directory / "page-phase1",
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )
    second = []
    if completed(first) and (session := result(first).get("session_id")):
        second = run_agent(
            cwd,
            prompts[1],
            "--resume",
            session,
            out=run.directory / "stream-2.jsonl",
            err=run.directory / "err-2.txt",
            **child,
        )

    if page.exists():
        shutil.copytree(
            page,
            run.directory / "page",
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )
    if (
        run.condition == "leaf"
        and page.exists()
        and completed(first)
        and completed(second)
    ):
        seed_and_read_choice(run)
        continuation = (
            f"The user has reviewed {page}. Add a short Review status note saying "
            "it has now been reviewed. Preserve their existing decisions. "
            f"Check with `$LEAF page check {page} --render` and stamp the revision. "
            "Do not start a watcher or wait for input. Reply with its path."
        )
        (run.directory / "prompt-3.txt").write_text(continuation)
        run_agent(
            cwd,
            continuation,
            "--resume",
            result(second)["session_id"],
            out=run.directory / "stream-3.jsonl",
            err=run.directory / "err-3.txt",
            **child,
        )
        shutil.copytree(
            page,
            run.directory / "page-continuation",
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )


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
                "detail": {"options": [chosen]},
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
        with tempfile.TemporaryDirectory(prefix="leaf-authored-reader-") as temporary:
            prompt = (
                f"Read the Leaf skill at {run.payload}/skills/leaf/SKILL.md. "
                f"The page at {page} has been reviewed by a user. Read its current "
                f"state: which option ids are selected in {widget}? Don't edit "
                'the page or serve it. Reply only with JSON: {"options":["id"]}.'
            )
            (destination / "prompt.txt").write_text(prompt)
            trace = run_agent(
                Path(temporary),
                prompt,
                out=destination / "stream.jsonl",
                err=destination / "err.txt",
                dirs=[run.payload, page],
                env={
                    "LEAF": str(run.payload / "bin/leaf"),
                    "XDG_STATE_HOME": str(run.state),
                },
                host=run.host,
            )
        raw = result(trace).get("result", "")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            answer = json.loads(match[0]) if match else None
        except json.JSONDecodeError:
            answer = None
        record |= {
            "completed": completed(trace),
            "page_unchanged": source_before == (page / "index.html").read_bytes()
            and events_before == (page / "events.jsonl").read_bytes(),
            "answer": answer,
            "correct": isinstance(answer, dict) and answer.get("options") == [chosen],
            "trace": trace_scores(destination / "stream.jsonl"),
        }
    (run.directory / "choice.json").write_text(json.dumps(record, indent=2))


def trace_scores(stream: Path) -> dict:
    if not stream.exists():
        return {"missing": True}
    trace = read_trace(stream)
    calls, results, reads = {}, {}, []
    for block in blocks(trace):
        if block.get("type") == "tool_use":
            calls[block["id"]] = block
        elif block.get("type") == "tool_result":
            results[block["tool_use_id"]] = block
    checks = renders = refused = writes = 0
    delegations = []
    for cid, call in calls.items():
        name, inp = call["name"], call.get("input", {})
        if name in ("Agent", "Task", "spawn_agent", "spawnAgent"):
            returned = results.get(cid)
            delegations.append(
                {
                    "tool": name,
                    "task": inp,
                    "returned": returned is not None,
                    "successful": returned is not None
                    and not returned.get("is_error", False),
                }
            )
        if name == "Bash":
            cmd = inp.get("command", "")
            if "page check" in cmd and "--help" not in cmd:
                checks += 1
                renders += "--render" in cmd
                # The exit status is often masked by a pipe or a chained command, so
                # read the check's own verdict mark. A `| tail` that cuts the mark off
                # hides a failure, so this is a floor.
                out = results.get(cid, {}).get("content")
                out = (
                    out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                )
                refused += "✗" in out
            elif "index.html" in cmd and re.search(
                r"-pi\b|sed -i|write_text|open\([^)]*['\"]w|>\s*\S*index\.html", cmd
            ):
                writes += 1
            reads += re.findall(r"references/[\w-]+\.md", cmd)
            reads += [f"registry:{k}" for k in re.findall(r'\.\["([^"]+)"\]', cmd)]
        elif name == "Read":
            reads.append(Path(inp.get("file_path", "")).name)
        elif name in ("Write", "Edit") and "index.html" in inp.get("file_path", ""):
            writes += 1
    done = result(trace)
    return {
        "completed": completed(trace),
        "finished": bool(done),
        "turns": done.get("num_turns"),
        "is_error": done.get("is_error"),
        "cost_usd": done.get("total_cost_usd"),
        "cost_known": done.get("total_cost_usd") is not None,
        "minutes": round(done.get("duration_ms", 0) / 60000, 1),
        **token_counts(trace),
        "checks": checks,
        "renders": renders,
        "refused": refused,
        "page_writes": writes,
        "reads": sorted(set(reads)),
        "delegation_invocations": len(delegations),
        "delegations": delegations,
        "reply": (done.get("result") or "")[-300:],
    }


def page_scores(page: Path) -> dict:
    html = (page / "index.html").read_text()
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
    css_lines = [line for s in styles for line in s.splitlines() if line.strip()]
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    js_lines = [line for s in scripts for line in s.splitlines() if line.strip()]
    linked = 0
    if (page / "page").is_dir():
        for f in (page / "page").rglob("*.css"):
            linked += sum(1 for line in f.read_text().splitlines() if line.strip())
        for f in (page / "page").rglob("*.js"):
            js_lines += [line for line in f.read_text().splitlines() if line.strip()]
    return {
        "css_lines": len(css_lines) + linked,
        "css_bytes": sum(len(s) for s in styles),
        "style_attrs": len(re.findall(r'\sstyle="[^"]*"', html)),
        "js_lines": len(js_lines),
        "vocab": {
            k: len(re.findall(p, html)) for k, p in VOCAB.items() if re.search(p, html)
        },
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
    """Screenshot one version at each width, top to bottom, keyed by width."""
    shots = run.directory / "shots"
    shots.mkdir(exist_ok=True)
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
                    path = shots / f"p{phase}-{name}-{index}.png"
                    view.screenshot(path=path)
                    captures[name].append(str(path))
    return captures


def capture(run: Run) -> dict[int, dict[str, list[str]]]:
    """Capture the initial and width-revised page phases."""
    return {phase: capture_phase(run, phase) for phase in PHASES}


def listing(captures: dict[str, list[str]]) -> list[str]:
    """A version's screenshot paths as the judge reads them, by width."""
    lines = []
    for name, (_, label) in WIDTHS.items():
        lines.append(f"  On {label}, top to bottom:")
        lines += [f"    {path}" for path in captures[name]]
    return lines


def brief(subject: str, captures: dict[int, dict[str, list[str]]]) -> str:
    """What the judge reads: the request, the later preference, each version's screenshots."""
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        f"After version 1, the user added a standing preference: {PREFERENCE}",
    ]
    for phase in PHASES:
        lines += ["", f"Version {phase} screenshots:", *listing(captures[phase])]
    return "\n".join(lines)


JUDGING = (
    "Read every screenshot the output lists for version {phase} with the Read tool "
    "before judging. Each width's screenshots run top to bottom with overlap. Fixed "
    "viewer controls are outside the page's content, and a region with its own "
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
                "provides the decisions or navigation the request needs.",
            }
            for phase in PHASES
        ),
        {
            "type": "agent-rubric",
            "metric": "phase-2-preference",
            "value": JUDGING.format(phase=2)
            + "Pass only if version 2 follows the standing width preference the "
            "output quotes.",
        },
    ]


def expected_checks(case: str, *, condition="leaf") -> list[str]:
    """Common outcome checks apply to both tools, without Leaf routing in HTML."""
    if case not in CASES:
        raise ValueError(f"Unknown authored task: {case}")
    return [
        "completed",
        *(
            f"phase-{phase}-{check}"
            for phase in PHASES
            for check in ("completed", "page", "render", "captures")
        ),
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
            if condition == "leaf"
            else []
        ),
    ]


def execute_scenario(
    case: str, payload: Path, work: Path, *, host="cc", condition="leaf"
) -> dict:
    """Execute only the selected condition; Promptfoo owns the condition matrix."""
    work.mkdir(parents=True, exist_ok=True)
    checks = dict.fromkeys(expected_checks(case, condition=condition), False)
    run = Run(case, payload, work, host, condition)
    diagnostics = {
        "subject": case,
        "host": host,
        "condition": condition,
        "phases": {},
    }
    costs = []
    with tempfile.TemporaryDirectory(prefix="leaf-author-") as temporary:
        author(run, Path(temporary) / "cwd")
        if condition == "leaf":
            choice_path = work / "choice.json"
            choice = json.loads(choice_path.read_text()) if choice_path.exists() else {}
            diagnostics["choice"] = choice
            checks["choice-seeded"] = choice.get("seeded") is True
            checks["choice-reader-completed"] = choice.get("completed") is True
            checks["choice-reader-correct"] = choice.get("correct") is True
            checks["choice-reader-page-unchanged"] = (
                choice.get("page_unchanged") is True
            )
            continuation = trace_scores(work / "stream-3.jsonl")
            checks["choice-continuation-completed"] = (
                continuation.get("completed") is True
            )
            diagnostics["continuation"] = continuation
            costs.append(continuation.get("cost_usd"))
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
                    standing[0]["detail"]["options"] if standing else authored_choice
                ) == choice["options"]
                reader_trace = choice["trace"]
                costs.append(reader_trace["cost_usd"])
        captures = capture(run)
        for phase in PHASES:
            trace = trace_scores(work / f"stream-{phase}.jsonl")
            costs.append(trace.get("cost_usd"))
            checks[f"phase-{phase}-completed"] = bool(trace.get("completed"))
            page = run.page(phase)
            checks[f"phase-{phase}-page"] = page is not None
            checks[f"phase-{phase}-captures"] = all(captures[phase].values())
            row = {"trace": trace, "captures": captures[phase]}
            if page:
                reading = gate(run, phase, page)
                checks[f"phase-{phase}-render"] = reading["passed"]
                row |= {
                    "page": str(page),
                    "page_scores": page_scores(page),
                    "gate": reading,
                }
            diagnostics["phases"][phase] = row
    checks["completed"] = all(checks[f"phase-{phase}-completed"] for phase in PHASES)
    return {
        "output": brief(case, captures),
        "metadata": {"checks": checks, "diagnostics": diagnostics},
        **({"cost": cost} if (cost := observed_sum(costs)) is not None else {}),
    }
