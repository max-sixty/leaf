"""The arrangement eval: build the arms, author pages, score, shoot, review, summarize.

    uv run notes/arrangement-eval/harness.py <command> ...

Everything lives under `.tmp/arrangement-eval/`, and commands take names:

- `arms-<name>/`: `leaf/` and `plain/`, one Leaf payload each, and `REF`.
- `runs/<batch>/<subject>-<arm>-<n>/`: one run. `arms` names the arms it used;
  `prompt-{1,2}.txt`, `stream-{1,2}.jsonl` (the full trace) and `err-{1,2}.txt` are
  its two phases; `page/` is the page directory, `page-phase1/` a copy of the whole
  directory as phase 1 left it; `work-dir` names the child's
  scratch cwd, `state/` is its state home; `gate-{1,2}.json` and `shots/` are the
  scorer's and the camera's.
- `runs/<batch>/scores.json`, `reviews/` and `reviews-flip/`: one per batch.

Arms. Both are `scripts/eval_harness.py`'s payload at one git ref, so neither carries
the history or the worked corpus that would show an author the other arm's vocabulary.
`plain_arm.build` takes the arrangement vocabulary out of `plain`, and `arms` renders
its smoke page, which uses the plain guide's width hook, so a theme that stops
honouring the hook fails the build rather than every plain run. `skills/` is made
read-only, so no author writes into a payload another run reads.

Runs. A child is `eval_harness.claude_child`, isolated from the user's `CLAUDE.md`,
their memory and the installed Leaf plugin as that module describes. An author reads the
arm's `SKILL.md` by path, as a host that loaded the skill would hand it over, runs the
arm's launcher as `$LEAF`, and keeps its pages and claims under the run's own state
home. Phase 2 resumes the phase-1 session with the standing preference. A round starts
every subject × arm pair at once, so load on the machine lands on both arms alike.

Scoring, per run and phase: turns, output tokens, cost and minutes; `version check`
runs, those with `--render`, those whose output carries a ✗, and page writes; the
references and registry keys read; page CSS lines (`<style>` plus `page/*.css`), style
attributes, JavaScript lines and each arrangement term used; and an independent
`version check --render` with the arm's launcher, cached in `gate-<phase>.json`. A
run's phase counts only when every trace through it reached its result, with `is_error`
false and no auto-memory loaded (`Run.usable`); `score` marks the others, and `review`
and `summarize` leave them out alike.

Review. A fresh child sees only the request and both pages' screenshots, copied under
neutral names (`A-laptop-0.png` …) into a directory holding nothing else, which is all
it may read: never a run's path, its HTML, the scores or the other pass. Which arm is A
is fixed per pair by a hash of the pair's name; `--flip` swaps every side and writes
`reviews-flip/`. A verdict is discarded if the child erred or left a screenshot unread,
and a job whose file holds a verdict is skipped, so a stopped pass resumes. A pair
counts for an arm only when both passes pick it; a pair they disagree on, or either
calls a tie, is a split.
"""

import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
import plain_arm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_harness import build_arm, claude_child, run_leaf, scratch

DATA = ROOT / ".tmp/arrangement-eval"
SUBJECTS = ("document", "dashboard", "queue")
ARMS = ("leaf", "plain")
PHASES = (1, 2)
MODEL = "claude-opus-5-5"
REVIEWERS = 6
# Each width's viewport, and how the reviewer is told of it.
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
    "lf-grid": r"<lf-grid\b",
    "lf-workspace": r"<lf-workspace\b",
    "lf-pane": r"<lf-pane\b",
    "data-width": r"\bdata-width=",
    "panel": r"class=\"[^\"]*\bpanel\b",
    "sidebar": r"class=\"[^\"]*\bsidebar\b",
    "sidenote": r"class=\"[^\"]*\bsidenote\b",
    "data-bound": r"\bdata-bound=",
    "lf-tabs": r"<lf-tabs\b",
}


# Children


def claude(
    prompt: str, cwd: Path, out: Path, err: Path, *, tools, dirs, env=None, resume=None
):
    """Run one `claude_child` from `cwd`; return its stream-json events.

    `out` receives the trace and `err` the child's stderr."""
    child = claude_child(
        cwd,
        prompt,
        "--model",
        MODEL,
        "--tools",
        tools,
        *(("--resume", resume) if resume else ()),
        dirs=dirs,
        env=env,
    )
    with out.open("w") as stdout, err.open("w") as stderr:
        subprocess.run(
            **child,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    return events(out)


def events(stream: Path) -> list[dict]:
    return [json.loads(line) for line in stream.read_text().splitlines()]


def result(trace: list[dict]) -> dict:
    """The trace's closing `result` event, or {} when the child never finished."""
    return next((d for d in reversed(trace) if d.get("type") == "result"), {})


def blocks(trace: list[dict]):
    """Every content block of every message: tool calls, tool results, text."""
    for d in trace:
        message = d.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        yield from (b for b in content or [] if isinstance(b, dict))


# Runs and batches


def arms_dir(name: str) -> Path:
    return DATA / f"arms-{name}"


@dataclass(frozen=True)
class Run:
    subject: str
    arm: str
    n: int
    dir: Path

    @classmethod
    def at(cls, path: Path) -> "Run":
        subject, arm, n = path.name.rsplit("-", 2)
        return cls(subject, arm, int(n), path)

    @property
    def payload(self) -> Path:
        return arms_dir((self.dir / "arms").read_text().strip()) / self.arm

    @property
    def state(self) -> Path:
        return self.dir / "state"

    def leaf(self, *args: str, **kwargs):
        return run_leaf(self.payload, self.state, *args, **kwargs)

    def page(self, phase: int) -> Path | None:
        """The page directory as it stood after `phase`, or None if there is none."""
        page = self.dir / ("page" if phase == 2 else "page-phase1")
        return page if (page / "index.html").exists() else None

    def usable(self, phase: int) -> bool:
        """Whether the run counts at `phase`: every trace through it reached its result,
        without error and without loading auto-memory. Phase 2 resumes phase 1's
        session, so a void phase 1 voids it too."""
        return all(
            counts(trace_scores(self.dir / f"stream-{p}.jsonl"))
            for p in range(1, phase + 1)
        )

    @contextmanager
    def served(self, page: Path):
        """Serve `page` with the arm's launcher; yield its URL."""
        out = self.leaf("server", "start", "--standing", str(page), check=True).stdout
        try:
            yield re.search(r"https?://\S+", out)[0]
        finally:
            self.leaf("server", "stop", str(page))


@dataclass(frozen=True)
class Batch:
    dir: Path

    def runs(self) -> list[Run]:
        return [
            Run.at(d)
            for d in sorted(self.dir.iterdir())
            if (d / "prompt-1.txt").exists()
        ]

    def pairs(self) -> dict[tuple[str, int], dict[str, Run]]:
        """Runs by (subject, n), each a mapping of arm to run."""
        pairs = {}
        for run in self.runs():
            pairs.setdefault((run.subject, run.n), {})[run.arm] = run
        return dict(sorted(pairs.items()))


def existing_batch(ctx, param, name: str) -> Batch:
    batch = Batch(DATA / "runs" / name)
    if not batch.dir.is_dir():
        raise click.BadParameter(f"no batch at {batch.dir}")
    return batch


@click.group()
def cli():
    """The arrangement eval; see the module docstring and README.md."""


# Arms


@cli.command()
@click.argument("ref")
@click.argument("name")
def arms(ref: str, name: str):
    """Build arms-NAME from git REF: the leaf payload and the plain one."""
    out = arms_dir(name)
    for arm in ARMS:
        sha = build_arm(ref, out / arm)
    smoke = plain_arm.build(out / "plain")
    (out / "REF").write_text(f"{sha}\n")
    with tempfile.TemporaryDirectory() as smoke_dir:
        state, page = Path(smoke_dir) / "state", Path(smoke_dir) / "page"
        run_leaf(out / "plain", state, "page", "init", str(page), check=True)
        (page / "index.html").write_text(smoke)
        run_leaf(
            out / "plain", state, "version", "check", str(page), "--render", check=True
        )
    subprocess.run(
        ["chmod", "-R", "a-w", out / "leaf/skills", out / "plain/skills"], check=True
    )
    click.echo(f"{out}: {sha}, plain smoke page passes")


# Authoring


def first_prompt(payload: Path, page: Path, subject: str) -> str:
    return f"""You have the Leaf skill. Its instructions are in {payload}/skills/leaf/SKILL.md: read
that file first and follow it, resolving the references it names from
{payload}/skills/leaf/. $LEAF is set to its launcher, {payload}/bin/leaf.

Write the page at {page}. This run is non-interactive: nobody will read the page in a
browser or answer in it. Treat the page as a finished record the user will rely on:
write it, run the pre-handover review including `$LEAF version check {page} --render`,
fix what the checks report, and stamp it. Don't start a server, set a status, or wait
for feedback. When the stamped page passes, reply with one line naming its path.

The user's request follows.

{(HERE / "subjects" / f"{subject}.md").read_text()}"""


def second_prompt(page: Path) -> str:
    return f"""The user writes:

{PREFERENCE}

Revise the page at {page} to follow this preference. Check it again with
`$LEAF version check {page} --render`, fix what the checks report, and stamp it. As
before, don't start a server or wait for feedback. When it passes, reply with one line.
"""


def author(arms: str, run: Run) -> None:
    """One run: a fresh agent writes the subject's page with the arm's Leaf, then
    revises it for the standing preference in the same session."""
    shutil.rmtree(run.dir, ignore_errors=True)
    run.state.mkdir(parents=True)
    (run.dir / "arms").write_text(f"{arms}\n")
    work = scratch()
    (run.dir / "work-dir").write_text(f"{work}\n")
    page = run.dir / "page"
    payload = run.payload
    prompts = [first_prompt(payload, page, run.subject), second_prompt(page)]
    for phase, prompt in enumerate(prompts, 1):
        (run.dir / f"prompt-{phase}.txt").write_text(prompt)
    child = {
        "tools": "Bash,Read,Write,Edit,Glob,Grep",
        "dirs": [payload, run.dir],
        "env": {"LEAF": str(payload / "bin/leaf"), "XDG_STATE_HOME": str(run.state)},
    }
    first = claude(
        prompts[0], work, run.dir / "stream-1.jsonl", run.dir / "err-1.txt", **child
    )
    if (page / "index.html").exists():
        shutil.copytree(
            page,
            run.dir / "page-phase1",
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )
    if session := result(first).get("session_id"):
        claude(
            prompts[1],
            work,
            run.dir / "stream-2.jsonl",
            run.dir / "err-2.txt",
            resume=session,
            **child,
        )
    click.echo(f"{run.dir} done")


@cli.command("run")
@click.argument("arms")
@click.argument("batch")
@click.argument("rounds", type=int)
@click.argument("subjects", nargs=-1, type=click.Choice(SUBJECTS))
def run_batch(arms: str, batch: str, rounds: int, subjects: tuple[str, ...]):
    """Author ROUNDS rounds of every subject in both of arms-ARMS' arms into BATCH.

    A round runs all its subject × arm pairs at once and waits for them all."""
    if not (arms_dir(arms) / "REF").exists():
        raise click.BadParameter(f"no arms at {arms_dir(arms)}", param_hint="ARMS")
    root = DATA / "runs" / batch
    for n in range(1, rounds + 1):
        round_ = [
            Run(s, arm, n, root / f"{s}-{arm}-{n}")
            for s in subjects or SUBJECTS
            for arm in ARMS
        ]
        with ThreadPoolExecutor(len(round_)) as pool:
            list(pool.map(lambda run: author(arms, run), round_))


# Scoring


def trace_scores(stream: Path) -> dict:
    if not stream.exists():
        return {"missing": True}
    trace = events(stream)
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
            if "version check" in cmd and "--help" not in cmd:
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
        # A child that loaded auto-memory read the user's notes, so the run is void.
        "memory": any(
            d.get("type") == "system" and d.get("memory_paths") for d in trace
        ),
        "finished": bool(done),
        "turns": done.get("num_turns"),
        "is_error": done.get("is_error"),
        "cost_usd": round(done.get("total_cost_usd", 0), 2),
        "minutes": round(done.get("duration_ms", 0) / 60000, 1),
        "output_tokens": usage.get("output_tokens"),
        "checks": checks,
        "renders": renders,
        "refused": refused,
        "page_writes": writes,
        "reads": sorted(set(reads)),
        "reply": (done.get("result") or "")[-300:],
    }


def counts(trace: dict) -> bool:
    """Whether a phase's `trace_scores` count: it reached its result, which says it did
    not fail, and it loaded no auto-memory."""
    return (
        bool(trace.get("finished"))
        and trace["is_error"] is False
        and not trace["memory"]
    )


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
    """An independent `version check --render` of the phase's page, cached per phase."""
    cached = run.dir / f"gate-{phase}.json"
    if not cached.exists():
        proc = run.leaf("version", "check", str(page), "--render", timeout=900)
        out = proc.stdout + proc.stderr
        cached.write_text(
            json.dumps({"passed": proc.returncode == 0, "output": out[-4000:]})
        )
    return json.loads(cached.read_text())


@cli.command()
@click.argument("batch", callback=existing_batch)
@click.option("--no-gate", is_flag=True, help="Skip the independent render check.")
def score(batch: Batch, no_gate: bool):
    """Score every run of BATCH into its scores.json, and print a row per run and phase."""
    rows = []
    for run in batch.runs():
        for phase in PHASES:
            row = {"subject": run.subject, "arm": run.arm, "n": run.n, "phase": phase}
            row["trace"] = trace_scores(run.dir / f"stream-{phase}.jsonl")
            row["usable"] = run.usable(phase)
            page = run.page(phase)
            row["page"] = page and page_scores(page)
            if page and not no_gate:
                row["gate"] = gate(run, phase, page)
            rows.append(row)
    (batch.dir / "scores.json").write_text(json.dumps(rows, indent=2))
    click.echo(f"{'run':24} ph gate turns $    min chk rnd ref wr css js  vocab")
    for r in rows:
        t, p, g = r["trace"], r["page"] or {}, r.get("gate", {})
        click.echo(
            f"{r['subject'] + '-' + r['arm'] + '-' + str(r['n']):24} {r['phase']}"
            f"{' ' if r['usable'] else 'x'} "
            f"{('pass' if g.get('passed') else 'FAIL') if g else '  - ':4} "
            f"{t.get('turns') or 0:5} {t.get('cost_usd') or 0:4.1f} {t.get('minutes') or 0:4.0f} "
            f"{t.get('checks', 0):3} {t.get('renders', 0):3} {t.get('refused', 0):3} "
            f"{t.get('page_writes', 0):2} {p.get('css_lines', 0):3} {p.get('js_lines', 0):3} "
            f"{p.get('vocab', {})}"
        )


# Screenshots


@cli.command()
@click.argument("batch", callback=existing_batch)
def shoot(batch: Batch):
    """Screenshot each run's page after each phase into <run>/shots/.

    p<phase>-<width>-<k>.png counts screens down the page: the viewport as first seen,
    then scrolled by 85% of the window each time, up to sixteen. Scrolling the window
    rather than resizing it to the content keeps a layout that holds the window at its
    real size and shows the fixed chrome where a reader meets it. What scrolls inside a
    region is shown as first drawn."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for run in batch.runs():
            shots = run.dir / "shots"
            shutil.rmtree(shots, ignore_errors=True)
            shots.mkdir()
            for phase in PHASES:
                if not (page := run.page(phase)):
                    continue
                with run.served(page) as url:
                    for name, ((w, h), _) in WIDTHS.items():
                        ctx = browser.new_context(
                            viewport={"width": w, "height": h},
                            device_scale_factor=1,
                            is_mobile=name == "phone",
                            has_touch=name == "phone",
                        )
                        tab = ctx.new_page()
                        tab.goto(url)
                        tab.wait_for_function(
                            "document.body.hasAttribute('data-lf-presented')",
                            timeout=30000,
                        )
                        tab.wait_for_timeout(600)
                        height = tab.evaluate("document.documentElement.scrollHeight")
                        step = int(h * 0.85)
                        for k in range(
                            min(16, 1 + max(0, height - h + step - 1) // step)
                        ):
                            tab.evaluate(f"window.scrollTo(0, {k * step})")
                            tab.wait_for_timeout(250)
                            tab.screenshot(path=shots / f"p{phase}-{name}-{k}.png")
                        ctx.close()
            click.echo(f"{run.dir.name} shot")
        browser.close()


# Review


def stage(run: Run, phase: int, side: str, into: Path) -> list[str]:
    """Copy one page's screenshots into `into` under neutral names; return the listing."""
    lines = []
    for key, (_, label) in WIDTHS.items():
        files = sorted(
            (run.dir / "shots").glob(f"p{phase}-{key}-*.png"),
            key=lambda f: int(f.stem.rsplit("-", 1)[1]),
        )
        lines.append(f"  On {label}, top to bottom:")
        for k, f in enumerate(files):
            target = into / f"{side}-{key}-{k}.png"
            shutil.copyfile(f, target)
            lines.append(f"    {target}")
    return lines


def review_prompt(subject: str, a: list[str], b: list[str], phase: int) -> str:
    request = (HERE / "subjects" / f"{subject}.md").read_text()
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
the bar fixed across the top, the shortcut band at the foot, and the column of small
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


def judge(
    out: Path, flipped: bool, subject: str, n: int, phase: int, pair: dict[str, Run]
) -> dict:
    done = out / f"{subject}-{n}-p{phase}.json"
    if done.exists() and json.loads(done.read_text())["verdict"]:
        return json.loads(done.read_text())
    flip = (
        int(hashlib.sha256(f"{subject}-{n}-{phase}".encode()).hexdigest(), 16) % 2
        ^ flipped
    )
    order = ["plain", "leaf"] if flip else ["leaf", "plain"]
    with tempfile.TemporaryDirectory() as scratch:
        cwd, shots = Path(scratch) / "cwd", Path(scratch) / "shots"
        cwd.mkdir()
        shots.mkdir()
        a = stage(pair[order[0]], phase, "A", shots)
        b = stage(pair[order[1]], phase, "B", shots)
        expected = {
            Path(line.strip()).name for line in a + b if line.strip().endswith(".png")
        }
        trace = claude(
            review_prompt(subject, a, b, phase),
            cwd,
            Path(scratch) / "stream.jsonl",
            Path(scratch) / "err.txt",
            tools="Read",
            dirs=[shots],
        )
    answer = result(trace) or {"is_error": True}
    read = {
        Path(block["input"].get("file_path", "")).name
        for block in blocks(trace)
        if block.get("type") == "tool_use"
    }
    raw = answer.get("result", "")
    found = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        verdict = json.loads(found[0]) if found else None
    except json.JSONDecodeError:
        verdict = None
    unread = sorted(expected - read)
    if answer.get("is_error") or unread:
        verdict = None
    record = {
        "subject": subject,
        "n": n,
        "phase": phase,
        "A": order[0],
        "B": order[1],
        "is_error": answer.get("is_error"),
        "shots": len(expected),
        "unread": unread,
        "verdict": verdict,
        "raw": raw,
    }
    done.write_text(json.dumps(record, indent=2))
    return record


@cli.command()
@click.argument("batch", callback=existing_batch)
@click.option(
    "--flip", is_flag=True, help="Swap every pair's sides; write reviews-flip/."
)
def review(batch: Batch, flip: bool):
    """Judge each pair's pages, blind, per phase; print each verdict by arm."""
    out = batch.dir / ("reviews-flip" if flip else "reviews")
    out.mkdir(exist_ok=True)
    jobs = [
        (subject, n, phase, pair)
        for (subject, n), pair in batch.pairs().items()
        if set(ARMS) <= pair.keys()
        for phase in PHASES
        if all(
            pair[arm].usable(phase)
            and (pair[arm].dir / f"shots/p{phase}-laptop-0.png").exists()
            for arm in ARMS
        )
    ]
    with ThreadPoolExecutor(REVIEWERS) as pool:
        records = list(pool.map(lambda job: judge(out, flip, *job), jobs))
    for r in records:
        v = r["verdict"] or {}
        names = {"A": r["A"], "B": r["B"]}
        winner = names.get(v.get("winner"), v.get("winner"))
        widths = {k: names.get(x, x) for k, x in (v.get("by_width") or {}).items()}
        pref = v.get("preference")
        pref = {r["A"]: pref["A"], r["B"]: pref["B"]} if pref else ""
        note = f" UNREAD {len(r['unread'])}/{r['shots']}" if r["unread"] else ""
        click.echo(
            f"{r['subject']}-{r['n']} p{r['phase']}: {winner} ({v.get('margin')}) {widths} {pref}{note}"
        )


# Summary


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else float("nan")


def outcomes(folder: Path) -> dict:
    """Each pair's pick in one review pass: the arm, 'tie', or None when discarded."""
    picks = {}
    for f in folder.glob("*.json"):
        r = json.loads(f.read_text())
        v = r["verdict"]
        names = {"A": r["A"], "B": r["B"], "tie": "tie"}
        picks[(r["subject"], r["phase"], r["n"])] = v and {
            "overall": names[v["winner"]],
            **{w: names.get(x, x) for w, x in (v.get("by_width") or {}).items()},
            **(
                {
                    "pref " + names[k]: bool(x)
                    for k, x in v["preference"].items()
                    if k in "AB"
                }
                if v.get("preference")
                else {}
            ),
        }
    return picks


@cli.command()
@click.argument("batch", callback=existing_batch)
def summarize(batch: Batch):
    """Print BATCH's scores and both review passes as Markdown tables.

    Per subject, phase and arm: median turns, cost, checks, checks reporting a ✗, CSS
    and JavaScript lines, and gate passes; per arm and phase, totals; per subject and
    phase, pairs won in both passes, overall and at each width, and how often each arm
    was judged to honour the preference."""
    rows = [
        r for r in json.loads((batch.dir / "scores.json").read_text()) if r["usable"]
    ]
    cells = defaultdict(list)
    for r in rows:
        cells[(r["subject"], r["phase"], r["arm"])].append(r)

    click.echo(
        "| subject | phase | arm | n | gate pass | turns | $ | checks | ✗ reports | CSS lines | JS lines |"
    )
    click.echo("|---|---|---|---|---|---|---|---|---|---|---|")
    for (subject, phase, arm), rs in sorted(cells.items()):
        t = [r["trace"] for r in rs]
        p = [r["page"] or {} for r in rs]
        passed = sum(bool(r.get("gate", {}).get("passed")) for r in rs)
        click.echo(
            f"| {subject} | {phase} | {arm} | {len(rs)} | {passed}/{len(rs)} "
            f"| {median([x['turns'] for x in t]):g} | {median([x['cost_usd'] for x in t]):.2f} "
            f"| {median([x['checks'] for x in t]):g} | {median([x['refused'] for x in t]):g} "
            f"| {median([x.get('css_lines') for x in p]):g} | {median([x.get('js_lines') for x in p]):g} |"
        )

    click.echo()
    click.echo("| arm | phase | turns | $ | CSS lines | JS lines | ✗ reports |")
    click.echo("|---|---|---|---|---|---|---|")
    for arm in ARMS:
        for phase in PHASES:
            rs = [r for r in rows if r["arm"] == arm and r["phase"] == phase]
            click.echo(
                f"| {arm} | {phase} | {sum(r['trace']['turns'] for r in rs)} "
                f"| {sum(r['trace']['cost_usd'] for r in rs):.2f} "
                f"| {sum((r['page'] or {}).get('css_lines', 0) for r in rs)} "
                f"| {sum((r['page'] or {}).get('js_lines', 0) for r in rs)} "
                f"| {sum(r['trace']['refused'] for r in rs)} |"
            )

    # A pair counts for an arm only when both passes, one with each arm as page A,
    # pick it; a pair the passes disagree on, or either calls a tie, is a split.
    first = outcomes(batch.dir / "reviews")
    second = outcomes(batch.dir / "reviews-flip")
    # A verdict saved before a run stopped counting stays on disk, so the tally takes
    # only pairs whose runs both count, as the score tables do.
    usable = {(r["subject"], r["phase"], r["n"], r["arm"]) for r in rows}
    tally = defaultdict(Counter)
    for key in sorted(first.keys() | second.keys()):
        if any((*key, arm) not in usable for arm in ARMS):
            continue
        a, b = first.get(key), second.get(key)
        cell = tally[key[:2]]
        if not (a and b):
            cell["discarded"] += 1
            continue
        for field in ("overall", *WIDTHS):
            won = a[field] if a[field] == b[field] != "tie" else "split"
            cell[f"{field} {won}"] += 1
        for arm in ARMS:
            cell[f"pref {arm}"] += sum(x.get(f"pref {arm}", False) for x in (a, b))
    click.echo()
    click.echo("Pairs won in both passes, leaf/plain/split:")
    click.echo()
    click.echo(
        "| subject | phase | overall | 1440px | 900px | 390px "
        "| preference met, leaf and plain, of 2 per pair | discarded |"
    )
    click.echo("|---|---|---|---|---|---|---|---|")
    for (subject, phase), c in sorted(tally.items()):
        trio = {
            field: f"{c[field + ' leaf']}/{c[field + ' plain']}/{c[field + ' split']}"
            for field in ("overall", *WIDTHS)
        }
        pairs = sum(c[f"overall {x}"] for x in ("leaf", "plain", "split"))
        pref = (
            f"{c['pref leaf']}/{2 * pairs}, {c['pref plain']}/{2 * pairs}"
            if phase == 2
            else ""
        )
        click.echo(
            f"| {subject} | {phase} | {trio['overall']} | {trio['laptop']} "
            f"| {trio['narrow']} | {trio['phone']} | {pref} | {c['discarded']} |"
        )


if __name__ == "__main__":
    cli()
