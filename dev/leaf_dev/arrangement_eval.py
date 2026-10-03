"""One arrangement comparison for Promptfoo: author, revise, render and judge.

Both vocabulary arms come from the supplied Leaf payload. The plain arm removes
arrangement declarations but keeps Leaf widgets, theme and feedback; this is a
vocabulary comparison, not a whole-product comparison with ordinary HTML.
Each Claude author resumes its initial session for the 900px preference. Two
fresh judges see only neutral captures, with each arm shown on each side.
Completion, render checks and judge evidence are assertions. Preferences and
visual winners remain diagnostics; a tie is a valid result.
"""

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from leaf.render_checks import rendered

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.browser import chrome, load, settle, tab
from leaf_dev.harness import (
    blocks,
    completed,
    read_trace,
    run_claude,
    run_leaf,
    serving,
)
from leaf_dev.harness import trace_result as result

SUBJECTS = ROOT / "evals/arrangement/subjects"
CASES = ("document", "dashboard", "queue")
ARMS = ("leaf", "plain")
PHASES = (1, 2)
MODEL = "claude-opus-5-5"
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


def claude(
    prompt: str, cwd: Path, out: Path, err: Path, *, tools, dirs, env=None, resume=None
):
    """Run one isolated Claude turn and retain its complete trace."""
    return run_claude(
        cwd,
        prompt,
        "--model",
        MODEL,
        "--tools",
        tools,
        *(("--resume", resume) if resume else ()),
        out=out,
        err=err,
        dirs=dirs,
        env=env,
    )


@dataclass(frozen=True)
class Run:
    subject: str
    payload: Path
    directory: Path

    @property
    def state(self) -> Path:
        return self.directory / "state"

    def leaf(self, *args: str, **kwargs):
        return run_leaf(self.payload, self.state, *args, **kwargs)

    def page(self, phase: int) -> Path | None:
        page = self.directory / ("page" if phase == 2 else "page-phase1")
        return page if (page / "index.html").exists() else None


def first_prompt(payload: Path, page: Path, subject: str) -> str:
    return f"""You have the Leaf skill. Its instructions are in {payload}/skills/leaf/SKILL.md: read
that file first and follow it, resolving the references it names from
{payload}/skills/leaf/. $LEAF is set to its launcher, {payload}/bin/leaf.

Write the page at {page}. This run is non-interactive: nobody will read the page in a
browser or answer in it. Treat the page as a finished record the user will rely on:
write it, run the pre-handover review including `$LEAF page check {page} --render`,
fix what the checks report, and stamp it. Don't start a server, set a status, or wait
for feedback. When the stamped page passes, reply with one line naming its path.

The user's request follows.

{(SUBJECTS / f"{subject}.md").read_text()}"""


def second_prompt(page: Path) -> str:
    return f"""The user writes:

{PREFERENCE}

Revise the page at {page} to follow this preference. Check it again with
`$LEAF page check {page} --render`, fix what the checks report, and stamp it. As
before, don't start a server or wait for feedback. When it passes, reply with one line.
"""


def author(run: Run, cwd: Path) -> None:
    """Author and revise in one isolated session, preserving phase one's page."""
    run.state.mkdir(parents=True)
    cwd.mkdir()
    page = run.directory / "page"
    prompts = [first_prompt(run.payload, page, run.subject), second_prompt(page)]
    for phase, prompt in enumerate(prompts, 1):
        (run.directory / f"prompt-{phase}.txt").write_text(prompt)
    child = {
        "tools": "Bash,Read,Write,Edit,Glob,Grep",
        "dirs": [run.payload, run.directory],
        "env": {
            "LEAF": str(run.payload / "bin/leaf"),
            "XDG_STATE_HOME": str(run.state),
        },
    }
    first = claude(
        prompts[0],
        cwd,
        run.directory / "stream-1.jsonl",
        run.directory / "err-1.txt",
        **child,
    )
    if page.exists():
        shutil.copytree(
            page,
            run.directory / "page-phase1",
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )
    if completed(first) and (session := result(first).get("session_id")):
        claude(
            prompts[1],
            cwd,
            run.directory / "stream-2.jsonl",
            run.directory / "err-2.txt",
            resume=session,
            **child,
        )


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
    for cid, call in calls.items():
        name, inp = call["name"], call.get("input", {})
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
    usage = done.get("usage", {})
    return {
        "completed": completed(trace),
        "finished": bool(done),
        "turns": done.get("num_turns"),
        "is_error": done.get("is_error"),
        "cost_usd": done.get("total_cost_usd", 0),
        "minutes": round(done.get("duration_ms", 0) / 60000, 1),
        "output_tokens": usage.get("output_tokens"),
        "checks": checks,
        "renders": renders,
        "refused": refused,
        "page_writes": writes,
        "reads": sorted(set(reads)),
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


def review_prompt(subject: str, a: list[str], b: list[str], phase: int) -> str:
    request = (SUBJECTS / f"{subject}.md").read_text()
    revised = (
        f"\nAfter the first version, the user added this standing preference, and both "
        f"pages below were revised for it:\n\n{PREFERENCE}\n"
        if phase == 2
        else ""
    )
    preference_field = (
        ', "preference": {"A": true|false, "B": true|false, "why": "…"}'
        if phase == 2
        else ""
    )
    return f"""Two pages were built for the same user request. You have not seen how either
was made, and you judge only what the user sees. Both run inside the same page viewer:
the bar fixed across the top, the bottom bar at the foot, and the column of small
markers at the right edge are the viewer's, identical on both, and not part of either
page. A region with a scroll of its own shows only its first screen here; in the real
page the user can scroll it, so judge whether what it shows first is the right part and
enough of it, not whether everything inside it is visible.

The user's request:

<request>
{request}
</request>
{revised}
Read every screenshot below with the Read tool before judging; a judgment that skips
one is discarded. Each width's screens run top to bottom through the page, overlapping
a little.

Page A:
{chr(10).join(a)}

Page B:
{chr(10).join(b)}

Judge as this user: which page would they rather have for this task? Consider whether
they can find what they need at a glance, read it comfortably, and act on it, and
whether anything is cut off, overlapping, cramped, misaligned, or wasting the room,
at each width.

Reply with only a JSON object:
{{"winner": "A"|"B"|"tie", "margin": "clear"|"slight", "by_width": {{"laptop": "A"|"B"|"tie", "narrow": "A"|"B"|"tie", "phone": "A"|"B"|"tie"}}, "reasons": ["…", "…", "…"], "defects": {{"A": ["…"], "B": ["…"]}}{preference_field}}}"""


def gate(run: Run, phase: int, page: Path) -> dict:
    """Independently check the authored page, retaining the check's output."""
    proc = run.leaf("page", "check", str(page), "--render", timeout=900)
    reading = {"passed": proc.returncode == 0, "output": proc.stdout + proc.stderr}
    (run.directory / f"gate-{phase}.json").write_text(json.dumps(reading, indent=2))
    return reading


def capture(run: Run) -> dict[int, list[str]]:
    """Capture settled viewports down each phase's page, including fixed chrome."""
    shots = run.directory / "shots"
    shots.mkdir()
    captures = {}
    with chrome() as browser:
        for phase in PHASES:
            captures[phase] = []
            if not (page := run.page(phase)):
                continue
            with serving(run.payload, run.state, page) as url:
                for name, (viewport, _) in WIDTHS.items():
                    with tab(browser, viewport=viewport, touch=name == "phone") as view:
                        load(view, url)
                        height = view.evaluate("document.documentElement.scrollHeight")
                        step = int(viewport[1] * 0.85)
                        screens = min(
                            16, 1 + max(0, height - viewport[1] + step - 1) // step
                        )
                        for index in range(screens):
                            view.evaluate(
                                "y => window.scrollTo({top: y, behavior: 'instant'})",
                                index * step,
                            )
                            rendered(view)
                            settle(view)
                            path = shots / f"p{phase}-{name}-{index}.png"
                            view.screenshot(path=path)
                            captures[phase].append(str(path))
    return captures


def stage(run: Run, phase: int, side: str, into: Path) -> tuple[list[str], set[str]]:
    """Stage captures under neutral names, with no source or arm names nearby."""
    lines, expected = [], set()
    for name, (_, label) in WIDTHS.items():
        files = sorted(
            (run.directory / "shots").glob(f"p{phase}-{name}-*.png"),
            key=lambda file: int(file.stem.rsplit("-", 1)[1]),
        )
        lines.append(f"  On {label}, top to bottom:")
        for index, source in enumerate(files):
            target = into / f"{side}-{name}-{index}.png"
            shutil.copyfile(source, target)
            lines.append(f"    {target}")
            expected.add(target.name)
    return lines, expected


def capture_reads(trace: list[dict]) -> set[str]:
    """Capture filenames whose Read call returned nonempty successful output."""
    content = list(blocks(trace))
    successful = {
        block["tool_use_id"]
        for block in content
        if block.get("type") == "tool_result"
        and not block.get("is_error", False)
        and block.get("content")
    }
    return {
        Path(block["input"]["file_path"]).name
        for block in content
        if block.get("type") == "tool_use"
        and block.get("name") == "Read"
        and block["id"] in successful
    }


def valid_verdict(value, phase: int) -> bool:
    """Require the blind judge's declared comparison, including every width."""
    picks = ("A", "B", "tie")
    if not isinstance(value, dict) or value.get("winner") not in picks:
        return False
    if value.get("margin") not in ("clear", "slight"):
        return False
    widths = value.get("by_width")
    if not isinstance(widths, dict) or any(
        widths.get(width) not in picks for width in WIDTHS
    ):
        return False
    if not isinstance(value.get("reasons"), list) or not value["reasons"]:
        return False
    defects = value.get("defects")
    if not isinstance(defects, dict) or any(
        not isinstance(defects.get(side), list) for side in ("A", "B")
    ):
        return False
    if phase == 2:
        preference = value.get("preference")
        if not isinstance(preference, dict) or any(
            type(preference.get(side)) is not bool for side in ("A", "B")
        ):
            return False
    return True


def judge(
    subject: str, phase: int, flipped: bool, pair: dict[str, Run], directory: Path
) -> dict:
    """Judge one phase in one side order, retaining the evidence for acceptance."""
    directory.mkdir(parents=True)
    flip = (
        int(hashlib.sha256(f"{subject}-{phase}".encode()).hexdigest(), 16) % 2 ^ flipped
    )
    order = ["plain", "leaf"] if flip else ["leaf", "plain"]
    with tempfile.TemporaryDirectory(prefix="leaf-arrangement-judge-") as temporary:
        cwd, shots = Path(temporary) / "cwd", Path(temporary) / "shots"
        cwd.mkdir()
        shots.mkdir()
        a, expected_a = stage(pair[order[0]], phase, "A", shots)
        b, expected_b = stage(pair[order[1]], phase, "B", shots)
        expected = expected_a | expected_b
        prompt = review_prompt(subject, a, b, phase)
        (directory / "prompt.txt").write_text(prompt)
        trace = claude(
            prompt,
            cwd,
            directory / "stream.jsonl",
            directory / "err.txt",
            tools="Read",
            dirs=[shots],
        )
    answer = result(trace)
    raw = answer.get("result", "")
    found = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        verdict = json.loads(found[0]) if found else None
    except json.JSONDecodeError:
        verdict = None
    unread = sorted(expected - capture_reads(trace))
    record = {
        "phase": phase,
        "flipped": flipped,
        "A": order[0],
        "B": order[1],
        "completed": completed(trace),
        "captures_read": bool(expected_a and expected_b) and not unread,
        "valid_verdict": valid_verdict(verdict, phase),
        "shots": len(expected),
        "unread": unread,
        "verdict": verdict,
        "raw": raw,
        "cost_usd": answer.get("total_cost_usd", 0),
        "trace": str(directory / "stream.jsonl"),
    }
    (directory / "verdict.json").write_text(json.dumps(record, indent=2))
    return record


def expected_checks(case: str) -> list[str]:
    """The fixed assertions required by one complete arrangement comparison."""
    if case not in CASES:
        raise ValueError(f"Unknown arrangement case: {case}")
    return [
        "completed",
        *(
            f"{arm}-phase-{phase}-{check}"
            for arm in ARMS
            for phase in PHASES
            for check in ("completed", "page", "render", "captures")
        ),
        *(
            f"judge-phase-{phase}-{order}-{check}"
            for phase in PHASES
            for order in ("forward", "flipped")
            for check in ("completed", "captures-read", "valid-verdict")
        ),
    ]


def execute_scenario(case: str, payload: Path, work: Path) -> dict:
    """Run one whole comparison; Promptfoo owns repetition, scheduling and reports."""
    checks = dict.fromkeys(expected_checks(case), False)
    diagnostics = {"subject": case, "authors": {}, "judgments": []}
    cost = 0
    with tempfile.TemporaryDirectory(prefix="leaf-arrangement-") as temporary:
        staging = Path(temporary)
        pair = {}
        for arm in ARMS:
            staged = staging / arm
            shutil.copytree(
                payload, staged, ignore=shutil.ignore_patterns(".venv", "__pycache__")
            )
            if arm == "plain":
                smoke = arrangement_plain.build(staged)
                smoke_page, smoke_state = staging / "smoke", staging / "smoke-state"
                run_leaf(
                    staged, smoke_state, "page", "init", str(smoke_page), check=True
                )
                (smoke_page / "index.html").write_text(smoke)
                run_leaf(
                    staged,
                    smoke_state,
                    "page",
                    "check",
                    str(smoke_page),
                    "--render",
                    check=True,
                )
            run = Run(case, staged, work / arm)
            pair[arm] = run
        for arm, run in pair.items():
            author(run, staging / f"{arm}-cwd")
            captures = capture(run)
            rows = {}
            for phase in PHASES:
                trace = trace_scores(run.directory / f"stream-{phase}.jsonl")
                cost += trace.get("cost_usd", 0)
                checks[f"{arm}-phase-{phase}-completed"] = bool(trace.get("completed"))
                page = run.page(phase)
                checks[f"{arm}-phase-{phase}-page"] = page is not None
                checks[f"{arm}-phase-{phase}-captures"] = all(
                    any(
                        Path(path).name.startswith(f"p{phase}-{width}-")
                        for path in captures[phase]
                    )
                    for width in WIDTHS
                )
                row = {
                    "trace": trace,
                    "trace_path": str(run.directory / f"stream-{phase}.jsonl"),
                    "captures": captures[phase],
                }
                if page:
                    reading = gate(run, phase, page)
                    checks[f"{arm}-phase-{phase}-render"] = reading["passed"]
                    row |= {
                        "page": str(page),
                        "page_scores": page_scores(page),
                        "gate": reading,
                    }
                rows[phase] = row
            diagnostics["authors"][arm] = rows
        for phase in PHASES:
            if not all(checks[f"{arm}-phase-{phase}-captures"] for arm in ARMS):
                continue
            for flipped in (False, True):
                order = "flipped" if flipped else "forward"
                record = judge(
                    case,
                    phase,
                    flipped,
                    pair,
                    work / "judges" / f"phase-{phase}-{order}",
                )
                cost += record["cost_usd"]
                for check, field in (
                    ("completed", "completed"),
                    ("captures-read", "captures_read"),
                    ("valid-verdict", "valid_verdict"),
                ):
                    checks[f"judge-phase-{phase}-{order}-{check}"] = record[field]
                diagnostics["judgments"].append(record)
    checks["completed"] = all(
        value for name, value in checks.items() if name.endswith("-completed")
    )
    return {
        "output": json.dumps(diagnostics),
        "metadata": {"checks": checks, "diagnostics": diagnostics},
        "cost": cost,
    }
