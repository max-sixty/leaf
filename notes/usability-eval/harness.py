"""The agent-usability baseline: author cold, read a page back, resume a foreign page.

    uv run notes/usability-eval/harness.py arm <ref> <name> [--without-tree]
    uv run notes/usability-eval/harness.py run <arm>[,<arm>] <batch> <rounds> [case ...]
    uv run notes/usability-eval/harness.py score <batch>
    uv run notes/usability-eval/harness.py summarize <batch>
    uv run notes/usability-eval/harness.py show <batch> [case]
    uv run notes/usability-eval/harness.py fixture <case> <arm> <dest>

This is `notes/agent-usability-evals.md`'s first executable slice and the start of
its next paired check. Each case starts a fresh Claude Code with Leaf as the host
installs it and scores what it did. `run` with no case runs `BASELINE`; the paired
check runs `resume` and `constructs` on two arms.

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

`arm --without-tree` builds the paired check's other condition: `WITHOUT_TREE` drops
`content` from `page state` and has the references read the active HTML beside the
compact state.

Choices the note asks for before automating:

- Runner and host: `claude -p` through `eval_harness.claude_child`, with the arm
  loaded by `--plugin-dir`, so the child finds the skill, its launcher on `PATH` and
  its hooks as an installed Claude Code session does. Nothing names a reference or
  the launcher; cold cases do not name Leaf at all.
- Model: Opus 5.5 (`MODEL`), default effort and tools, bypass permissions.
- Isolation: an arm is `eval_harness.build_arm`'s payload at one ref, under
  `.tmp/usability-eval/arms/<name>/` with `skills/` read-only. Each run has its own
  scratch cwd outside any repository, which holds the fixture page, and its own
  `XDG_STATE_HOME`. A round starts every case × arm at once.
- Fixtures: `build_*` writes each fixture with the arm's own launcher and admits
  user moves through the browser's door (`event_endpoint.accept_event`) in the arm's
  own environment, so a fixture is what that arm's server would have written.
- Trace: the child's stream-json, one file per phase.
- Normalization: reading and `constructs` answers are numbered lines, one per
  question; each line is matched case-insensitively against its question's pattern.
  Resume answers lead with `Date:`, `Approach:` and `Next:` lines, matched the same
  way. The patterns are checked by reading every reply (`show`), and
  `notes/agent-usability-evals.md` records the disagreements.
- Retention: traces, pages and scratch stay under `.tmp/usability-eval/runs/<batch>/`
  (gitignored); `score` writes the batch's per-run scores to `results/<batch>.json`,
  which is committed so a later run compares against it.

A run counts only when every trace through its phase completed
(`eval_harness.completed`). The first round of a new case fixes its fixture and
scorer and is not reported.
"""

import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import click

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_harness import (
    blocks,
    build_arm,
    completed,
    environment,
    read_trace,
    run_claude,
    run_leaf,
    scratch,
    trace_result,
)

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


@dataclass(frozen=True)
class Case:
    name: str
    prompts: tuple[str, ...]
    fixture: str | None = None


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
}
BASELINE = ("cold-report", "cold-decision", "near-miss", "reading", "resume")

# The arm without `page state`'s construction tree: `content` goes from the page
# reading, and the references read the active HTML with the compact state instead.
# Each pair is (file, text in it, replacement); `arm --without-tree` stops when a text
# no longer matches the ref's guidance.
WITHOUT_TREE = [
    (
        "skills/leaf/scripts/leaf/agent_state.py",
        "    print(json.dumps(state, indent=2, ensure_ascii=False))",
        (
            '    if thread_id is None:\n        state.pop("content", None)\n'
            "    print(json.dumps(state, indent=2, ensure_ascii=False))"
        ),
    ),
    (
        "skills/leaf/references/authoring-revisions.md",
        """Run `leaf page state <page>` and read its `content` tree. Each node joins its
effective words, attributes, standing state, and data inputs with their origin.
`content_source` names the active file, mutable `edit_file`, and vocabulary file.
An authored node's `source` gives its line and column; `edit` identifies who can change it.
The tree is a reading, so effective content may differ from authored HTML. Look up
the node's `vocabulary` tag in the shared vocabulary file when needed.

When `edit.matches_active` is false, the candidate in `index.html` differs from
the live revision. Its source locations still refer to the active file; reconcile
the candidate by stable id and content before editing. `inputs` names external
values and the source file that holds each; change one with `leaf data set` or by
rewriting that file.""",
        """Run `leaf page state <page>`, and read the active revision's HTML, the file
`content_source.file` names, beside it. The HTML is what you authored; `state` lists
each user move that stands over it, by widget, with the words or choice it carries,
so where the two differ the page shows the move. `content_source` names the active
file, mutable `edit_file`, and vocabulary file; look up a widget's tag in the
vocabulary file when needed.

When `content_source.matches_active` is false, the candidate in `index.html` differs
from the live revision; reconcile the candidate by stable id and content before
editing. `data_bindings` names each external source and the widgets that read it,
and `data/<source>.json` holds its value; change one with `leaf data set` or by
rewriting that file.""",
    ),
    (
        "skills/leaf/references/serving-pages.md",
        "Read `content` for the current document and its construction origins, then the active\nrevision,",
        "Read the active revision's HTML and the standing `state` over it, then the active\nrevision,",
    ),
    (
        "skills/leaf/references/page-authoring.md",
        "read `leaf page state <page>`'s\n`content` and `asks` alongside the source",
        "read `leaf page state <page>`'s\n`state` and `asks` alongside the active HTML",
    ),
]


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
        return len(traces) == len(CASES[self.case].prompts) and all(
            completed(t) for t in traces
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
@click.option("--without-tree", is_flag=True, help="drop page state's `content` tree")
def arm(ref: str, name: str, without_tree: bool):
    """Build arm NAME from git REF."""
    if not re.fullmatch(r"[a-z0-9]+", name):
        raise click.BadParameter("an arm name is lowercase letters and numbers")
    out = arm_dir(name)
    sha = build_arm(ref, out)
    for relative, old, new in WITHOUT_TREE if without_tree else ():
        path = out / relative
        text = path.read_text()
        if old not in text:
            raise click.ClickException(f"{relative} no longer holds {old[:60]!r}")
        path.write_text(text.replace(old, new))
    subprocess.run(["chmod", "-R", "a-w", out / "skills"], check=True)
    (out.parent / f"{name}.REF").write_text(f"{sha}\n")
    click.echo(f"{out}: {sha}")


# Fixtures


def admit(run: Run, page: Path, event: dict) -> None:
    """Admit one user move through the arm's browser door."""
    code = (
        "import json, sys\nfrom pathlib import Path\nfrom leaf import event_endpoint\n"
        "status, body = event_endpoint.accept_event(Path(sys.argv[1]), "
        "json.loads(sys.argv[2]), dict)\n"
        "assert status == 200, body\n"
    )
    proc = subprocess.run(
        ["uv", "run", "-q", "--no-dev", "--project", str(run.payload), "python", "-c"]
        + [code, str(page), json.dumps(event)],
        capture_output=True,
        text=True,
        check=False,
        env=environment(XDG_STATE_HOME=str(run.state)),
    )
    if proc.returncode:
        raise click.ClickException(f"admitting {event}: {proc.stderr}")


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
    (page / "index.html").write_text((FIXTURES / "resume-candidate.html").read_text())


CONSTRUCTS_DRAFT = (
    "Release 4.2 moves card tokenization to the new vault. Merchants need no code "
    "changes. Rollout starts 12 November.\n"
)


def build_constructs(run: Run, page: Path) -> None:
    """The draft the user rewrote, the p95 stated at one measurement with a later one
    in its source, and the chart."""
    template = (FIXTURES / "constructs.html").read_text()
    run.leaf("page", "init", str(page), check=True)
    (page / "index.html").write_text(template.replace("{at}", "2026-09-20T09:00:00Z"))
    measured = run.leaf(
        "data", "set", str(page), "checkout-p95", input_text="184", check=True
    ).stdout
    at = re.search(r"updated (\S+)", measured)[1]
    (page / "index.html").write_text(template.replace("{at}", at))
    run.leaf("version", "stamp", str(page), "--text", "Release 4.2 review", check=True)
    run.leaf("status", str(page), "waiting", "Edit the release note", check=True)
    admit(run, page, {
        "kind": "action", "revision": 1, "widget": "release-note", "action": "edit",
        "detail": {"text": CONSTRUCTS_DRAFT},
    })  # fmt: skip
    run.leaf("data", "set", str(page), "checkout-p95", input_text="231", check=True)


def build_fixture(run: Run, name: str, page: Path) -> None:
    if name == "constructs":
        build_constructs(run, page)
    elif name == "resume":
        build_resume(run, page)
    elif name == "reading":
        build_reading(run, page, None)
    else:
        build_reading(run, page, name.removeprefix("reading-"))


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
    phase's session."""
    case = CASES[run.case]
    shutil.rmtree(run.dir, ignore_errors=True)
    run.state.mkdir(parents=True)
    work = scratch()
    (run.dir / "work-dir").write_text(f"{work}\n")
    page = work / "page"
    if case.fixture:
        build_fixture(run, case.fixture, page)
        shutil.copytree(page, run.dir / "fixture", ignore=ignore)
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
    for found in pages(work, run.state):
        shutil.copytree(found, run.dir / "pages" / found.name, ignore=ignore)
    click.echo(f"{run.dir} done")


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
    usage = done.get("usage", {})
    return {
        "completed": completed(trace),
        "turns": done.get("num_turns"),
        "cost_usd": round(done.get("total_cost_usd", 0), 3),
        "minutes": round(done.get("duration_ms", 0) / 60000, 1),
        "input_tokens": sum(
            usage.get(k, 0)
            for k in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        ),
        "output_tokens": usage.get("output_tokens"),
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
        "served": "server" in calls,
        "status": (state.get("status") or {}).get("state"),
        "asks": len(re.findall(r"<lf-ask\b", html)),
        "choose_groups": len(re.findall(r"<lf-options\b[^>]*\bchoose\b", html)),
        "options": len(re.findall(r"<lf-option\b", html)),
        "multiple": bool(re.search(r"<lf-options\b[^>]*\bmultiple\b", html)),
        "sign_off": 'content="sign-off"' in html,
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
        "chart_85": bool(chart and re.search(r"sa-east,\s*85\b", chart[0])),
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
        "batch_edit_elsewhere": bool(batch is None),
        "chosen_marked": bool(
            re.search(r'<lf-option[^>]*id="opt-per-tenant"[^>]*\bchosen', html)
            or re.search(r'<lf-option[^>]*\bchosen[^>]*id="opt-per-tenant"', html)
        ),
        "pick_standing": any(
            s.get("widget") == "rollout"
            and s.get("detail", {}).get("options") == ["opt-per-tenant"]
            for s in state.get("state", [])
        ),
        "restated": "restated" in html,
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
        if run.case in COLD:
            row["score"] = score_cold(run, replies[-1] if replies else "", calls)
        elif run.case.startswith("reading"):
            row["score"] = score_reading(run, replies[-1] if replies else "")
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
    """Tabulate results/BATCH.json by case and arm: each check's passes over the usable
    runs, and the mean cost, input tokens and bytes of `page state` output."""
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
