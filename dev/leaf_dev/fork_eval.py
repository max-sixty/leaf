"""Replay Leaf's conversation forks on short constructed conversations, and score
each answer: the turn-end check (`leaf.agents.clerk`), the line fork that writes the agent's
working line on a thread message (`leaf.agents.forks`), and the fork beside it that
summarizes a long thread (`leaf.agents.summary_fork`). Claude
Code makes every fork, so every case runs on that harness alone.

A case in `workflows/fork_eval.yaml` is a conversation written for one decision a
fork's prompt asks about, the page the session holds (an authored source with the
log events the case needs), and labels. Constructed cases are cheap and run
anywhere, but can't show the drift late in a long session that the turn-end check
exists for; a replay of a recorded session measures that.

Each arm's own Leaf writes the question and takes the answer, run as the session's
Claude Code environment runs it: its launcher, and its Python for what has no
command (`Leaf`). The executor builds the page in a throwaway state home, opens a
turn for a fresh session id and claims the page as that session
(`CLAUDE_CODE_SESSION_ID`, with this process as `CLAUDE_PID`). It reports to `leaf
hook --fork` as the hooks module does (`leaf.agents.carrier`): a turn's end, or the report
the pages follower lists for a round that awaits a line, whose answer is the fork to
make, and then that fork's answer. For a line or summary fork, a process of the arm's
holds the session's forks lane (`leases.take_lane`) while the user's waiting messages
are admitted, as the event endpoint admits them, and until the answer is taken, as the
pages follower holds it, and reports the round the follower would list (`forks.look`,
`LOOK`). A turn-end case's Leaf line
(`found`) is rendered by the arm's `clerk._found`, so a change to its wording
reaches the conversation; an arm without it passes no findings on and gets no line.

The conversation is rendered as a Claude Code transcript under the same session id,
in a home and cwd of its own outside the repository (`claude_child`), and resumed
once with `claude -p` and the prompt, on the author model at the effort the arm's
Leaf names for the fork, or at the session's (`SESSION_EFFORT`) where it names none,
as a live fork runs, so `--base` scores a change of effort as it scores one of
wording. The records keep the shapes Claude Code writes, without thinking blocks. A
background command's result records no task id: Claude Code tells a resumed session
that a task it recorded has stopped, which a live fork never hears, so the replay
needs no sentence of its own in the prompt. After its first prompt, where a live
session records it, the transcript carries the prompt snapshot of the newest
interactive Claude Code session on the machine, pinned for the run (`live_prefix`):
the system prompt and tool definitions that session's requests send, which a resume
sends again verbatim. So the fork's request opens as a live fork's does, with Claude
Code's interactive identity line, system prompt and tools, where `claude -p` would
send its headless ones, and it follows each Claude Code update as the sessions do,
which a snapshot kept in the tree would not. One `PreToolUse` hook (`BLOCKED`), the
fresh home's only one, refuses every call, and `--max-turns 1` then ends the fork
without an answer, which fails every check of the case rather than raising a
provider error. Plugins, skills and MCP servers are off.

A live fork's request ends with its prompt, since `$.model.fork` appends the prompt
to the session's last request. A resume instead reads its environment afresh (its
working directory, the tools, agents and skills it lists, the session's context) and
puts each record of it that the transcript lacks after the new prompt, a few
thousand tokens that change how the fork judges the prompt. So a first resume, sent
to an address no API listens on (`UNREACHABLE`), writes those records without a
request, and the transcript carries them after its first prompt, where a live
session's are (`announced`). Today's date stays out of them: a case's conversation
is written on its own dates, some a day apart, and a fork that reads today's date at
the session's start takes the conversation as today's and flags its dates as stale.
The second resume then adds only the line giving today's date after the prompt, which
a live fork's request lacks. Skills are off because the listing a resume reads
offline differs from the one it reads online, which would put a listing after the
prompt.

The replay resumes a transcript because a resume is the only way Claude Code, run as
`claude -p` or by the Agent SDK, takes prewritten turns of both sides; otherwise it
takes a system prompt and the user's messages and writes the assistant's turns
itself. A fork asked in one user message, with the conversation quoted above its
prompt and no tools, passes the same deterministic checks for less, but misses a
judgment live forks make: under a line fork prompt that live forks and the replay
both sometimes answered by handing a read of the page's source to the session, it
took the read every time. Claude Code sends the replay's request itself, on the
login the evals bill (`commands/eval/run.py`). A Messages API client, such as
Promptfoo's `anthropic:messages`, could send the same request only on an API key,
which the runner keeps out of evals, or on the login's token read from Claude Code's
keychain entry, a token Anthropic's terms forbid developers to "collect, store, or
intermediate".

What the arm's Leaf took is what gets scored. A turn-end answer it refuses fails
`answered`. Its asks are the records it wrote (`wrote`), as the user reads them; its
findings are those its `turn_end_check` note lists for the page, which leaves out
anything named for a page the session doesn't hold. A line fork's line is what
its `fork_outcome` note says Leaf posted. An answer or line Leaf refused fails
`answered` where the note's outcome says so (`refused`).

An item is matched to a label by the words it rests on: one of the label's `words`
stands in its quote, passage, title, text or edit words. An `expect` label needs an
item of its kind, and one naming a `thread` needs an ask written in that thread, or
in a new thread where it names null. A question label's `choice` says whether Leaf
asked it with a widget in its text, such as a choice (true), or in words (false). A stale
one's `edit` is either null, as the item's must be, or
the words its fix must remove: Leaf changed the page, and the page as the user reads
it no longer shows them. An item of any kind in the same part of the answer (asks or
findings) matching an `absent` label fails the case, since it names what the case's
guardrail leaves out. Every item and change goes to the text judge
(`metadata.texts.judge`), which reads whether each says the right thing and whether
an unlabelled one is real. A line fork's line is scored on the judge.

Cost is priced from the result's `usage` at the fork model's list prices (`PRICES`).
Its `total_cost_usd` prices the same call, since the rendered records carry no
usage, but bills hour-long cache writes at the five-minute rate.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from leaf.base.harness import ClaudeCodeHarness, claude_code_config
from leaf_dev import ROOT
from leaf_dev.arms import (
    MODELS,
    arm_python,
    blocks,
    build_source,
    claude_child,
    environment,
    read_trace,
    run_leaf,
    trace_result,
)
from leaf_dev.eval_cases import definition
from leaf_dev.page_fixtures import ADMIT
from leaf_dev.reply_phases import transcript_records

DEFINITION = definition("fork_eval")
CASES = DEFINITION["cases"]
# A live fork resends the session's model; the replay takes the author model.
MODEL = MODELS[ClaudeCodeHarness.name]
# The effort of the sessions a fork serves, which a fork that names none thinks at.
SESSION_EFFORT = "xhigh"

# The parts of a turn-end answer, with the kinds each holds.
PARTS = {
    "asks": ("question",),
    "findings": ("stale", "settled", "unshown", "overtaken"),
}

# The fork's settings: a hook that refuses every tool call, keeping the definitions.
BLOCKED = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "echo 'Tools are off in this fork.' >&2; exit 2",
                    }
                ],
            }
        ]
    }
}

# An API address nothing listens on, which ends a resume before its first request.
UNREACHABLE = "http://127.0.0.1:9"

# The identity line an interactive session's prompt snapshot names, where `claude -p`'s
# names the Agent SDK.
INTERACTIVE = "You are Claude Code, Anthropic's official CLI for Claude."

# List prices by model, dollars per million tokens.
PRICES = {
    "claude-opus-5-5": {
        "input": 5.0,
        "write_5m": 6.25,
        "write_1h": 10.0,
        "read": 0.5,
        "output": 25.0,
    }
}

# Holds the session's forks lane until stdin closes.
LANE = """
import sys
from leaf.base.leases import take_lane
lane = take_lane(sys.argv[1])
print("held", flush=True)
sys.stdin.read()
"""

# Admits the user's waiting messages as the event endpoint does, and prints the
# reports the pages follower would list for them (`forks.look`), which lists only
# rounds newer than its first look at the page.
LOOK = """
import json, sys
from pathlib import Path
from leaf.records.event_contracts import append_admitted
from leaf.agents.forks import look
from leaf.records.transaction import PageTransaction

page, session = Path(sys.argv[1]), sys.argv[2]
_, after = look(session, page, None)
with PageTransaction(page) as transaction:
    for event in json.load(sys.stdin):
        append_admitted(transaction, event)
print(json.dumps(look(session, page, after)[0]))
"""

# The page's newest diagnostics note of one type, or null.
NOTE = """
import json, sys
from pathlib import Path
from leaf.log.interaction_log import read_interactions
notes = read_interactions(Path(sys.argv[1]), types=(sys.argv[2],))
print(json.dumps(notes[-1] if notes else None))
"""

# The text of the summary event with the given id, or null.
SUMMARY = """
import json, sys
from pathlib import Path
from leaf.log.event_log import read_events
found = [e for e in read_events(Path(sys.argv[1])) if e["id"] == sys.argv[2]]
print(json.dumps(found[0]["text"] if found else None))
"""

# The words of the session's one page as the user reads them, as the turn-end check
# is shown them.
PAGE_TEXT = """
import json, sys
from leaf.commands.agent_state import turn_end_facts
[facts] = turn_end_facts(sys.argv[1])
print(json.dumps(facts["text"]))
"""

# The line Leaf's clerk queues for a finding, or null on an arm that queues none.
FOUND = """
import json, sys
try:
    from leaf.agents.clerk import _found
except ImportError:
    print("null")
else:
    print(json.dumps(_found(sys.argv[1], json.load(sys.stdin), sys.argv[2], True)))
"""


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    scenario = CASES[case]
    if scenario["fork"] == "line":
        return ["answered", "lined"]
    if scenario["fork"] == "summary":
        return ["answered", "declined" if scenario.get("declines") else "summarized"]
    expect = scenario.get("labels", {}).get("expect", [])
    return [
        "answered",
        *(["labels-found"] if expect else []),
        *(["edits-land"] if any("edit" in label for label in expect) else []),
        *(["choices-right"] if any("choice" in label for label in expect) else []),
        *(["guardrails-held"] if scenario.get("labels", {}).get("absent") else []),
    ]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    """Build the case's page and session with the arm's Leaf, fork the rendered
    conversation once, and score what the arm's Leaf took of the answer."""
    if harness != ClaudeCodeHarness.name:
        raise ValueError("Leaf's conversation forks run only in Claude Code")
    work.mkdir(parents=True, exist_ok=True)
    session = str(uuid.uuid4())
    page = work / "page"
    # The case's `{page}` and `{session}`, wherever they stand, such as a running call.
    scenario = substitute(CASES[case], {"{page}": str(page), "{session}": session})
    leaf = Leaf(payload, work / "state", session)
    source = work / "source" / "index.html"
    source.parent.mkdir()
    shutil.copy(ROOT / "evals" / scenario["page"], source)
    (source.parent / "layer.json").write_text('["reading"]')
    build_source(payload, work / "state", source, page)
    # After the build, whose closing `page open` writes a status event that would
    # end a start in the log (`todos.item_starts`).
    if scenario.get("log"):
        leaf.python(ADMIT, str(page), "0", "1", stdin=json.dumps(scenario["log"]))
    leaf.run(
        *("hook", "--harness", "claude-code"),
        stdin={"hook_event_name": "UserPromptSubmit", "prompt_id": "p1"},
    )
    leaf.run("page", "claim", str(page))
    turns = conversation(scenario, leaf, page)
    metadata: dict = {"fork": scenario["fork"], "session": session, "harness": harness}
    if scenario["fork"] in ("line", "summary"):
        with leaf.lane():
            [listed] = leaf.python(
                LOOK, str(page), session, stdin=json.dumps(scenario["waiting"])
            )
            reported = leaf.fork(
                {
                    "done": listed["id"],
                    "do": listed["do"],
                    "basis": listed["basis"],
                    "running": scenario.get("running", []),
                }
            )
            # The line fork, or the one Leaf asks for beside it, scored alone.
            [asked] = [
                instruction
                for instruction in reported["do"]
                if (instruction["basis"].get("duty") == "summary")
                == (scenario["fork"] == "summary")
            ]
            run = fork(asked, session, turns, work)
            if run["text"] is not None:
                leaf.fork(answered(asked, run))
    else:
        [asked] = leaf.fork({"turn_end": True})["do"]
        run = fork(asked, session, turns, work)
    (work / "prompt.txt").write_text(asked["request"]["prompt"])
    metadata.update(
        {key: run[key] for key in ("usage", "cost", "wall_s", "tool_calls", "prefix")}
    )
    response = {
        "output": run["text"] or f"(no answer: {run['failed']})",
        "cost": run["cost"],
        "metadata": metadata,
    }
    checks = expected_checks(case)
    if run["text"] is None:
        # A fork that called a tool answered wrongly; one that never ran is an error.
        metadata["checks"] = dict.fromkeys(checks, False)
        if run["tool_calls"]:
            return response
        return {**response, "error": f"the fork gave no answer: {run['failed']}"}
    if scenario["fork"] == "line":
        metadata.update(score_line(leaf, page, scenario, turns))
    elif scenario["fork"] == "summary":
        metadata.update(score_summary(leaf, page, scenario, asked, turns))
    else:
        metadata.update(score_turn_end(leaf, page, scenario, asked, run, turns))
    metadata["checks"] = {name: metadata["checks"].get(name, False) for name in checks}
    return response


class Leaf:
    """The arm's launcher and Python under the case's state home, as the session's
    Claude Code environment runs them."""

    def __init__(self, payload: Path, state: Path, session: str):
        self.payload, self.session = payload, session
        self.env = environment(
            XDG_STATE_HOME=str(state),
            CLAUDE_CODE_SESSION_ID=session,
            CLAUDE_PID=str(os.getpid()),
        )

    def run(self, *args: str, stdin: dict | None = None, check: bool = True):
        return run_leaf(
            self.payload,
            None,
            *args,
            env=self.env,
            check=check,
            error=RuntimeError,
            input_text=json.dumps({"session_id": self.session, **stdin})
            if stdin
            else None,
        )

    def fork(self, payload: dict):
        """One report to the arm's Leaf, as the hooks module makes it
        (`leaf.agents.carrier`), and what Leaf answered."""
        ran = self.run(
            *("hook", "--harness", "claude-code", "--if-claimed", "--fork"),
            stdin={"hook_event_name": "Fork", "running": [], **payload},
        )
        if not ran.stdout.strip():
            raise RuntimeError("leaf hook --fork printed nothing")
        return json.loads(ran.stdout)

    def python(self, program: str, *args: str, stdin: str = "") -> Any:
        """What `program` prints, as JSON, run by the arm's Python."""
        result = subprocess.run(
            [*arm_python(self.payload), "-c", program, *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"the arm's Python failed: {result.stderr.strip()}")
        return json.loads(result.stdout)

    @contextmanager
    def lane(self):
        """Hold the session's forks lane, as its pages follower does."""
        holder = subprocess.Popen(
            [*arm_python(self.payload), "-c", LANE, self.session],
            env=self.env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        assert holder.stdin is not None and holder.stdout is not None
        try:
            if holder.stdout.readline().strip() != "held":
                raise RuntimeError("the forks lane was not taken")
            yield
        finally:
            holder.stdin.close()
            holder.wait(timeout=30)


def answered(asked: dict, run: dict) -> dict:
    """The report of the fork `asked`, Leaf's instruction, with its answer, as the
    module makes it."""
    return {
        "done": asked["id"],
        "do": asked["do"],
        "basis": asked["basis"],
        "answer": run["text"],
        "usage": run["usage"],
        "elapsed_ms": run["elapsed_ms"],
    }


def conversation(scenario: dict, leaf: Leaf, page: Path) -> list[dict]:
    """The case's turns: each `from` item replaced by the named conversation's,
    `{page}` and `{session}` by the case's, and each `found` by the line the arm's
    clerk queues for that finding, or by nothing where it queues none."""
    values = {"{page}": str(page), "{session}": leaf.session}
    turns = []
    for turn in scenario["conversation"]:
        for each in (
            DEFINITION["conversations"][turn["from"]] if "from" in turn else [turn]
        ):
            each = substitute(each, values)
            if "found" in each:
                line = leaf.python(
                    FOUND, str(page), leaf.session, stdin=json.dumps(each["found"])
                )
                if line is not None:
                    turns.append({"leaf": line})
            else:
                turns.append(each)
    return turns


def substitute(value, values: dict):
    """`value` with each placeholder in its strings replaced."""
    if isinstance(value, str):
        for name, replacement in values.items():
            value = value.replace(name, replacement)
        return value
    if isinstance(value, list):
        return [substitute(item, values) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, values) for key, item in value.items()}
    return value


def live_prefix(run: Path) -> dict:
    """The prompt snapshot record the run's forks resend (`newest_snapshot`), pinned
    in `run`, the samples directory every arm's samples share (`scenario_provider`),
    by the first fork to ask, so that every arm resends the same one."""
    pinned = run / "live-prefix.json"
    if not pinned.exists():
        candidate = run / f"live-prefix-{uuid.uuid4().hex}.json"
        candidate.write_text(json.dumps(newest_snapshot()))
        try:
            os.link(candidate, pinned)
        except FileExistsError:
            pass
        candidate.unlink()
    return json.loads(pinned.read_text())


def newest_snapshot() -> dict:
    """The last prompt snapshot record of the newest Claude Code session whose last
    snapshot an interactive session recorded with its tools, as its requests resend
    it."""
    transcripts = sorted(
        (claude_code_config() / "projects").glob("*/*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in transcripts:
        snapshots = [
            record
            for record in transcript_records(path)
            if record.get("type") == "attachment"
            and record["attachment"].get("type") == "prompt_snapshot"
        ]
        last = snapshots[-1]["attachment"] if snapshots else {}
        if last.get("cliPrefix") == INTERACTIVE and "tools" in last:
            return snapshots[-1]
    raise RuntimeError(
        "no interactive Claude Code session on this machine recorded a prompt "
        "snapshot for the fork to resend"
    )


def transcript(
    turns: list[dict], session: str, cwd: Path, start: datetime, snapshot: dict
) -> list:
    """The conversation as Claude Code's transcript records: a user's prompt, Leaf's
    hook line (`leaf`, in the context of the prompt or tool result it follows), the
    assistant's text, and a tool call (`tool`, `input`) with its `result`. A
    response's blocks share a message id and its stop reason, from the first block
    after a prompt or tool result to the last. The prompt `snapshot` follows the first
    prompt."""
    records: list[dict] = []
    clock = (start + timedelta(seconds=7 * n) for n in range(10_000))
    common = {
        "isSidechain": False,
        "userType": "external",
        "entrypoint": "cli",
        "cwd": str(cwd),
        "sessionId": session,
        "version": "2.1.317",
        "gitBranch": "",
    }
    parent: str | None = None
    message: str | None = None
    prompt = None

    def add(record: dict) -> dict:
        nonlocal parent
        record = {
            "parentUuid": parent,
            **record,
            "uuid": str(uuid.uuid4()),
            "timestamp": next(clock).isoformat().replace("+00:00", "Z"),
            **common,
        }
        records.append(record)
        parent = record["uuid"]
        return record

    def respond(block: dict, stop: str) -> dict:
        nonlocal message
        if message is None:
            message = f"msg_{uuid.uuid4().hex[:24]}"
        for record in records:
            if record.get("message", {}).get("id") == message:
                record["message"]["stop_reason"] = stop
        return add(
            {
                "type": "assistant",
                "message": {
                    "model": MODEL,
                    "id": message,
                    "type": "message",
                    "role": "assistant",
                    "content": [block],
                    "stop_reason": stop,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
                "requestId": f"req_{message[4:]}",
            }
        )

    for turn in turns:
        if "user" in turn:
            message, prompt = None, str(uuid.uuid4())
            add(
                {
                    "type": "user",
                    "promptId": prompt,
                    "message": {"role": "user", "content": turn["user"]},
                }
            )
            if len(records) == 1:
                add({"type": "attachment", "attachment": snapshot})
        elif "leaf" in turn:
            follows = next(
                record for record in reversed(records) if "message" in record
            )
            event = (
                "UserPromptSubmit"
                if isinstance(follows["message"]["content"], str)
                else "PostToolBatch"
            )
            add(
                {
                    "type": "attachment",
                    "attachment": {
                        "type": "hook_additional_context",
                        "content": [turn["leaf"]],
                        "hookName": event,
                        "toolUseID": f"hook-{uuid.uuid4()}",
                        "hookEvent": event,
                    },
                    "rendered": [
                        {
                            "content": f"<system-reminder>\n{event} hook additional "
                            f"context: {turn['leaf']}\n</system-reminder>"
                        }
                    ],
                    "renderedRole": "system",
                }
            )
        elif "assistant" in turn:
            respond({"type": "text", "text": turn["assistant"]}, "end_turn")
        else:
            tool = f"toolu_{uuid.uuid4().hex[:24]}"
            call = respond(
                {
                    "type": "tool_use",
                    "id": tool,
                    "name": turn["tool"],
                    "input": turn["input"],
                },
                "tool_use",
            )
            message = None
            add(
                {
                    "type": "user",
                    "promptId": prompt,
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool,
                                "content": turn["result"],
                                "is_error": bool(turn.get("error")),
                            }
                        ],
                    },
                    "toolUseResult": {"stdout": turn["result"], "stderr": ""},
                    "sourceToolAssistantUUID": call["uuid"],
                }
            )
    return records


def fork(asked: dict, session: str, turns: list, work: Path) -> dict:
    """Resume the rendered conversation, under a live session's prompt snapshot
    (`live_prefix`), with the prompt the arm's Leaf `asked` for, at the effort it
    names or the session's, as `$.model.fork` forks it, in a home and cwd of its own
    outside the repository, once a resume that reaches no API has written the
    environment the transcript carries (the module header says why), keeping its
    stream and transcript under `work`; its answer, or why it gave none."""
    stream = work / "fork.jsonl"
    effort = asked["request"].get("effort", SESSION_EFFORT)
    with tempfile.TemporaryDirectory(prefix="leaf-fork-") as directory:
        cwd = Path(directory).resolve() / "cwd"
        cwd.mkdir()

        def resume(**env: str) -> dict:
            return claude_child(
                cwd,
                *("--resume", session, "--effort", effort, "--max-turns", "1"),
                *("--disable-slash-commands", "--settings", json.dumps(BLOCKED)),
                env=env,
                model=MODEL,
                sandbox=False,
            )

        child = resume()
        project = Path(child["env"]["HOME"]) / ".claude/projects"
        project /= re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
        project.mkdir(parents=True)
        kept = project / f"{session}.jsonl"
        prefix = live_prefix(work.parent)
        records = transcript(
            turns,
            session,
            cwd,
            datetime.fromisoformat(DEFINITION["start"]),
            prefix["attachment"],
        )
        kept.write_text("".join(json.dumps(record) + "\n" for record in records))
        # The environment a resume announces, written by one that reaches no API.
        offline = resume(ANTHROPIC_BASE_URL=UNREACHABLE, CLAUDE_CODE_MAX_RETRIES="0")
        calibrated = subprocess.run(
            offline["args"],
            cwd=offline["cwd"],
            env=offline["env"],
            input=".",
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        written = [json.loads(line) for line in kept.read_text().splitlines()]
        seeded = announced(records, written[len(records) :])
        if len(seeded) == len(records):
            # Without them the fork would read its environment after the prompt.
            raise RuntimeError(
                "the offline resume wrote no environment: "
                f"{calibrated.stderr or calibrated.stdout}"
            )
        kept.write_text("".join(json.dumps(record) + "\n" for record in seeded))
        started = time.monotonic()
        with stream.open("w") as out:
            ran = subprocess.run(
                ["nice", "-n", "10", *child["args"]],
                cwd=child["cwd"],
                env=child["env"],
                input=asked["request"]["prompt"],
                stdout=out,
                stderr=subprocess.PIPE,
                text=True,
                timeout=900,
                check=False,
            )
        wall = time.monotonic() - started
        shutil.copy(kept, work / "transcript.jsonl")
    trace = read_trace(stream)
    result = trace_result(trace)
    calls = [
        block["name"] for block in blocks(trace) if block.get("type") == "tool_use"
    ]
    text = result.get("result") if result.get("subtype") == "success" else None
    failed = (
        f"called {', '.join(calls)}"
        if calls
        else None
        if text is not None
        else result.get("subtype") or f"claude exited {ran.returncode}: {ran.stderr}"
    )
    usage = result.get("usage") or {}
    return {
        "text": None if failed else text,
        "failed": failed,
        "usage": usage,
        "cost": price(usage, MODEL),
        "wall_s": round(wall, 1),
        "elapsed_ms": result.get("duration_ms"),
        "tool_calls": calls,
        "prefix": {key: prefix[key] for key in ("sessionId", "version")},
    }


def announced(records: list[dict], written: list[dict]) -> list[dict]:
    """The transcript `records` with the attachments a resume `written` after them,
    which describe the session's environment, moved after its first prompt, where a
    live session's carry them; all but today's date (the module header says why)."""
    found = [
        record
        for record in written
        if record.get("type") == "attachment" and record["attachment"]["type"] != "date"
    ]
    first, *rest = records
    parent = first["uuid"]
    for record in found:
        record["parentUuid"], parent = parent, record["uuid"]
    if rest:
        rest[0]["parentUuid"] = parent
    return [first, *found, *rest]


def price(usage: dict, model: str) -> float:
    """What one call's `usage` costs at `model`'s `PRICES`, which must hold it."""
    if model not in PRICES:
        raise KeyError(f"no list prices for {model}; add them to fork_eval.PRICES")
    rates = PRICES[model]
    written = usage.get("cache_creation") or {}
    hour = written.get("ephemeral_1h_input_tokens", 0)
    minutes = written.get(
        "ephemeral_5m_input_tokens", usage.get("cache_creation_input_tokens", 0) - hour
    )
    dollars = (
        usage.get("input_tokens", 0) * rates["input"]
        + minutes * rates["write_5m"]
        + hour * rates["write_1h"]
        + usage.get("cache_read_input_tokens", 0) * rates["read"]
        + usage.get("output_tokens", 0) * rates["output"]
    )
    return round(dollars / 1e6, 5)


def words_of(text: str) -> str:
    """`text` as its lowercase words and numbers, each between single spaces."""
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.casefold())) + " "


def rests_on(item: dict, label: dict) -> bool:
    """Whether one of `label`'s words stands in `item`'s quote, passage, title, text
    or edit."""
    held = "|".join(
        words_of(text or "")
        for text in (
            *(item.get(field) for field in ("quote", "passage", "title", "text")),
            (item.get("edit") or {}).get("words"),
        )
    )
    return any(words_of(phrase) in held for phrase in label["words"])


def match(items: list[dict], labels: dict) -> dict:
    """Each item matched to the first label it rests on: the item each expected
    label of its kind found, by the label's index, in the label's `thread` where it
    names one; each item naming an absent label in its part, of whatever kind; and
    the rest, among them a second item of a found label's kind on its words."""
    part = {kind: name for name, kinds in PARTS.items() for kind in kinds}
    found: dict[int, dict] = {}
    named, extra = [], []
    for item in items:
        expect = [
            index
            for index, label in enumerate(labels.get("expect", []))
            if label["kind"] == item["kind"]
            and rests_on(item, label)
            and label.get("thread", item.get("thread")) == item.get("thread")
        ]
        absent = [
            label
            for label in labels.get("absent", [])
            if part[label["kind"]] == part[item["kind"]] and rests_on(item, label)
        ]
        if expect and expect[0] not in found:
            found[expect[0]] = item
        elif absent:
            named.append({"item": item, "label": absent[0]})
        else:
            extra.append({**item, "repeats_an_item": True} if expect else item)
    return {"found": found, "named": named, "extra": extra}


def score_turn_end(
    leaf: Leaf,
    page: Path,
    scenario: dict,
    asked: dict,
    run: dict,
    turns: list,
) -> dict:
    """Hand the answer to the arm's Leaf as the module does, score what it took
    against the case's labels, and pack every item and change for the judge."""
    applied = leaf.fork(answered(asked, run))
    if "refused" in applied:
        return {"checks": {"answered": False}, "refused": applied["refused"]}
    note = leaf.python(NOTE, str(page), "turn_end_check") or {}

    def titled(record: dict) -> str:
        """The title the user reads over an ask: a follow-up's is its thread's."""
        if "parent" not in record:
            return record["title"]
        shown = leaf.run("page", "state", str(page), record["parent"]).stdout
        return json.loads(shown)["thread"]["title"]

    items = [
        *(
            {
                "kind": "question",
                "title": titled(record),
                "text": record.get("text", ""),
                "passage": (record.get("anchor") or {}).get("quote", ""),
                # The thread a follow-up replies in; an ask in a new thread has none.
                "thread": record.get("parent"),
                # Asked by a widget in its text, such as a choice, rather than in
                # words, which an obligation declares.
                "choice": not record.get("obligation"),
            }
            for record in applied["wrote"]
        ),
        *note.get("findings", []),
    ]
    labels = scenario.get("labels", {})
    matched = match(items, labels)
    found, changed = matched["found"], applied.get("changed", [])
    shown = words_of(leaf.python(PAGE_TEXT, leaf.session)) if changed else ""

    def landed(label: dict, item: dict) -> bool:
        if label["edit"] is None:
            return item.get("edit") is None
        return bool(changed) and words_of(label["edit"]["words"]) not in shown

    expect = enumerate(labels.get("expect", []))
    return {
        "checks": {
            "answered": True,
            "labels-found": len(found) == len(labels.get("expect", [])),
            "edits-land": all(
                index in found and landed(label, found[index])
                for index, label in expect
                if "edit" in label
            ),
            "guardrails-held": not matched["named"],
            "choices-right": all(
                index in found and found[index]["choice"] == label["choice"]
                for index, label in enumerate(labels.get("expect", []))
                if "choice" in label
            ),
        },
        "items": items,
        "found": {str(index): item for index, item in found.items()},
        "named": matched["named"],
        "changed": changed,
        "told": applied.get("told", []),
        "texts": {
            "judge": judge_text(
                turns, asked["request"]["prompt"], items, matched, changed
            )
        },
    }


def conversation_text(turns: list[dict]) -> str:
    """The conversation as a judge reads it, one block per turn."""
    lines = []
    for turn in turns:
        if "user" in turn:
            lines.append(f"USER: {turn['user']}")
        elif "leaf" in turn:
            lines.append(f"LEAF (hook context the agent received): {turn['leaf']}")
        elif "assistant" in turn:
            lines.append(f"ASSISTANT: {turn['assistant']}")
        else:
            lines.append(
                f"ASSISTANT calls {turn['tool']} {json.dumps(turn['input'])}\n"
                f"RESULT: {turn['result']}"
            )
    return "\n\n".join(lines)


def judge_text(
    turns: list, prompt: str, items: list, matched: dict, changed: list
) -> str:
    """What the judge reads: the conversation, the question the fork was asked,
    each item Leaf took, marked where a label expects it, and each change."""
    if not items and not changed:
        return "No items and no changes."
    labelled = [id(item) for item in matched["found"].values()]
    marked = [{**item, "labelled": id(item) in labelled} for item in items]

    def listed(entries: list) -> str:
        return json.dumps(entries, indent=1, ensure_ascii=False) if entries else "none"

    return (
        f"<conversation>\n{conversation_text(turns)}\n</conversation>\n\n"
        f"<question>\n{prompt}\n</question>\n\n"
        f"<items>\n{listed(marked)}\n</items>\n\n"
        f"<changes>\n{listed(changed)}\n</changes>"
    )


def score_summary(
    leaf: Leaf, page: Path, scenario: dict, asked: dict, turns: list
) -> dict:
    """Score the summary the arm's Leaf wrote from a summary fork's answer, as its
    `summary_fork` note records it, against the conversation and the thread as the
    case's log holds it."""
    note = leaf.python(NOTE, str(page), "summary_fork") or {}
    written = leaf.python(SUMMARY, str(page), note.get("summary") or "")
    thread = json.dumps(
        [*scenario["log"], *scenario["waiting"]], indent=1, ensure_ascii=False
    )
    basis = asked["basis"]
    # The range the summary folds, as the note records it: the fork's choice, or on a
    # Leaf whose fork folds the suggestion, the suggestion itself.
    folded = note if "from" in note else basis
    return {
        "checks": {
            "answered": bool(note) and note.get("outcome") != "failed",
            "summarized": note.get("outcome") == "summarized",
            "declined": note.get("outcome") == "declined",
        },
        "outcome": note.get("outcome"),
        "note": note,
        "texts": {
            "summary": f"<conversation>\n{conversation_text(turns)}\n"
            f"</conversation>\n\n<thread>\n{thread}\n</thread>\n\n"
            f"<suggested>\n{basis['from']} through {basis['through']}\n</suggested>"
            f"\n\n<range>\n{folded['from']} through {folded['through']}\n</range>"
            f"\n\n<summary>\n{written or '(no summary)'}\n</summary>",
        },
    }


def score_line(leaf: Leaf, page: Path, scenario: dict, turns: list) -> dict:
    """Score the working line the arm's Leaf posted from a line fork's answer, as its
    `fork_outcome` note records it."""
    note = leaf.python(NOTE, str(page), "fork_outcome") or {}
    if not note or note["outcome"] == "refused":
        return {"checks": {"answered": False}, "refused": note.get("why")}
    thread = json.dumps(scenario["waiting"], indent=1, ensure_ascii=False)
    conversation = f"<conversation>\n{conversation_text(turns)}\n</conversation>\n\n"
    running = json.dumps(scenario.get("running", []), indent=1, ensure_ascii=False)
    line = note.get("text") if "line" in note else None
    return {
        "checks": {
            "answered": True,
            "lined": line is not None,
        },
        "outcome": note["outcome"],
        "note": note,
        "texts": {
            "line": f"{conversation}<running>\n{running}\n</running>\n\n"
            f"<thread>\n{thread}\n</thread>\n\n<line>\n{line or '(no line)'}\n</line>",
        },
    }
