"""Replay Leaf's two conversation forks on short constructed conversations, and score
each answer: the turn-end check (`leaf.clerk`) and the fork that writes the agent's
working line on a thread message before Leaf hands it to the session (`leaf.forks`). Claude Code makes both forks, so
every case runs on that harness alone.

A case in `workflows/fork_eval.yaml` is a conversation written for one decision a
fork's prompt asks about, the page the session holds (an authored source with the
log events the case needs), and labels. Constructed cases are cheap and run
anywhere, but can't show the drift late in a long session that the turn-end check
exists for; a replay of a recorded session measures that.

Each arm's own Leaf writes the question and takes the answer, run as the session's
Claude Code environment runs it: its launcher, and its Python for what has no
command (`Leaf`). The executor builds the page in a throwaway state home, opens a
turn for a fresh session id and claims the page as that session
(`CLAUDE_CODE_SESSION_ID`, with this process as `CLAUDE_PID`). It asks `leaf hook
--fork` for the prompt as `forkStep` in `hooks/claude-code.ts` does, and hands it
the answer the same way. For a line fork, a process of the arm's holds the session's
forks lane (`forks.take_lane`) from before the user's waiting messages are admitted
until the answer is taken, as the pages follower holds it; no follower runs, so no
hold runs out (`forks.BOUND_S`) while the fork thinks. A turn-end case's Leaf line
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
needs no sentence of its own in the prompt. The request keeps Claude Code's tool definitions, as a live fork
resends the session's, with its per-machine sections moved out of the system prompt
so the prefix is cached across cases. One `PreToolUse` hook (`BLOCKED`), the fresh
home's only one, refuses every call, and `--max-turns 1` then ends the fork without
an answer, which fails every check of the case rather than raising a provider
error. Plugins and MCP servers are off.

What the arm's Leaf took is what gets scored. A turn-end answer it refuses fails
`answered`. Its asks are the records it wrote (`wrote`), as the user reads them; its
findings are those its `turn_end_check` note lists for the page, which leaves out
anything named for a page the session doesn't hold. A line fork's line is what
its `fork_outcome` note says Leaf posted. An answer or line Leaf refused fails
`answered` where the note says so (`refused`).

An item is matched to a label by the words it rests on: one of the label's `words`
stands in its quote, passage, title, text or edit words. An `expect` label needs an
item of its kind, and one naming a `thread` needs an ask written in that thread, or
in a new thread where it names null. A stale one's `edit` is either null, as the item's must be, or
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

from leaf.harness import ClaudeCodeHarness
from leaf_dev import ROOT
from leaf_dev.arms import (
    MODELS,
    build_source,
    claude_child,
    environment,
    read_trace,
    trace_result,
)
from leaf_dev.eval_cases import definition
from leaf_dev.page_fixtures import ADMIT, fixture_environment

DEFINITION = definition("fork_eval")
CASES = DEFINITION["cases"]
# A live fork resends the session's model; the replay takes the author model.
MODEL = MODELS[ClaudeCodeHarness.name]
# The effort of the sessions a fork serves, which a fork that names none thinks at.
SESSION_EFFORT = "xhigh"

# The parts of a turn-end answer, with the kinds each holds.
PARTS = {"asks": ("question",), "findings": ("stale", "settled", "unshown")}

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

# Holds the session's forks lane until stdin closes, waiting past the take's
# millisecond, since a message admitted within it stays with the session.
LANE = """
import sys, time
from leaf.forks import lane_since, take_lane
lane = take_lane(sys.argv[1])
while time.time() < lane_since(sys.argv[1]) + 0.002:
    time.sleep(0.0005)
print("held", flush=True)
sys.stdin.read()
"""

# The page's newest diagnostics note of one type, or null.
NOTE = """
import json, sys
from pathlib import Path
from leaf.interaction_log import read_interactions
notes = read_interactions(Path(sys.argv[1]), types=(sys.argv[2],))
print(json.dumps(notes[-1] if notes else None))
"""

# The page's words as the user reads them, as the turn-end check reads them.
PAGE_TEXT = """
import json, sys
from pathlib import Path
from leaf.clerk import _facts
print(json.dumps(_facts(Path(sys.argv[1]))["text"]))
"""

# The line Leaf's clerk queues for a finding, or null on an arm that queues none.
FOUND = """
import json, sys
try:
    from leaf.clerk import _found
except ImportError:
    print("null")
else:
    print(json.dumps(_found(sys.argv[1], json.load(sys.stdin), sys.argv[2], True)))
"""


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    scenario = CASES[case]
    if scenario["fork"] == "line":
        return ["answered", "lined", "judged"]
    expect = scenario.get("labels", {}).get("expect", [])
    return [
        "answered",
        *(["labels-found"] if expect else []),
        *(["edits-land"] if any("edit" in label for label in expect) else []),
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
    scenario = CASES[case]
    work.mkdir(parents=True, exist_ok=True)
    session = str(uuid.uuid4())
    page = work / "page"
    leaf = Leaf(payload, work / "state", session)
    source = work / "source" / "index.html"
    source.parent.mkdir()
    shutil.copy(ROOT / "evals" / scenario["page"], source)
    (source.parent / "layer.json").write_text("[]")
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
    if scenario["fork"] == "line":
        with leaf.lane():
            leaf.python(
                ADMIT, str(page), "0", "0", stdin=json.dumps(scenario["waiting"])
            )
            thread = {
                "page": str(page),
                "thread": scenario["thread"],
                "inputs": [message["id"] for message in scenario["waiting"]],
            }
            kept = {"thread": thread, "running": scenario.get("running", [])}
            asked = leaf.fork(kept)
            run = fork(asked, session, turns, work)
            if run["text"] is not None:
                leaf.fork({**kept, **taken(run)})
    else:
        asked = leaf.fork({})
        run = fork(asked, session, turns, work)
    (work / "prompt.txt").write_text(asked["prompt"])
    metadata.update(
        {key: run[key] for key in ("usage", "cost", "wall_s", "tool_calls")}
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
    else:
        metadata.update(score_turn_end(leaf, page, scenario, asked, run, turns))
    metadata["checks"] = {name: metadata["checks"].get(name, False) for name in checks}
    return response


class Leaf:
    """The arm's launcher and Python under the case's state home, as the session's
    Claude Code environment runs them."""

    def __init__(self, payload: Path, state: Path, session: str):
        self.payload, self.session = payload, session
        self.env = fixture_environment(
            environment(
                XDG_STATE_HOME=str(state),
                CLAUDE_CODE_SESSION_ID=session,
                CLAUDE_PID=str(os.getpid()),
            )
        )

    def run(self, *args: str, stdin: dict | None = None, check: bool = True):
        result = subprocess.run(
            [str(self.payload / "bin/leaf"), *args],
            input=json.dumps({"session_id": self.session, **stdin}) if stdin else None,
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        if check and result.returncode:
            raise RuntimeError(
                f"leaf {' '.join(args)} exited {result.returncode}: "
                + result.stderr.strip()
            )
        return result

    def fork(self, payload: dict, *, check: bool = True):
        """One step of a fork, as `forkStep` runs it: what it printed, or with
        `check` False the finished process."""
        ran = self.run(
            *("hook", "--harness", "claude-code", "--if-claimed", "--fork"),
            stdin={"hook_event_name": "Fork", **payload},
            check=check,
        )
        if not check:
            return ran
        if not ran.stdout.strip():
            raise RuntimeError("leaf hook --fork printed nothing")
        return json.loads(ran.stdout)

    def python(self, program: str, *args: str, stdin: str = "") -> Any:
        """What `program` prints, as JSON, run by the arm's Python."""
        result = subprocess.run(
            [str(self.payload / ".venv/bin/python"), "-I", "-c", program, *args],
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
            [str(self.payload / ".venv/bin/python"), "-I", "-c", LANE, self.session],
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


def taken(run: dict) -> dict:
    """The fork's answer as the module hands it back to Leaf."""
    return {
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


def transcript(turns: list[dict], session: str, cwd: Path, start: datetime) -> list:
    """The conversation as Claude Code's transcript records: a user's prompt, Leaf's
    hook line (`leaf`, in the context of the prompt or tool result it follows), the
    assistant's text, and a tool call (`tool`, `input`) with its `result`. A
    response's blocks share a message id and its stop reason, from the first block
    after a prompt or tool result to the last."""
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
        elif "leaf" in turn:
            event = (
                "UserPromptSubmit"
                if isinstance(records[-1]["message"]["content"], str)
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
    """Resume the rendered conversation once with the prompt the arm's Leaf `asked`
    for, at the effort it names or the session's, as `$.model.fork` forks it, in a
    home and cwd of its own outside the repository, keeping its stream and transcript
    under `work`; its answer, or why it gave none."""
    stream = work / "fork.jsonl"
    effort = asked.get("effort", SESSION_EFFORT)
    with tempfile.TemporaryDirectory(prefix="leaf-fork-") as directory:
        cwd = Path(directory).resolve() / "cwd"
        cwd.mkdir()
        child = claude_child(
            cwd,
            *("--resume", session, "--effort", effort, "--max-turns", "1"),
            *("--exclude-dynamic-system-prompt-sections", "--settings"),
            json.dumps(BLOCKED),
            model=MODEL,
            sandbox=False,
        )
        project = Path(child["env"]["HOME"]) / ".claude/projects"
        project /= re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
        project.mkdir(parents=True)
        kept = project / f"{session}.jsonl"
        start = datetime.fromisoformat(DEFINITION["start"])
        kept.write_text(
            "".join(
                json.dumps(record) + "\n"
                for record in transcript(turns, session, cwd, start)
            )
        )
        started = time.monotonic()
        with stream.open("w") as out:
            ran = subprocess.run(
                ["nice", "-n", "10", *child["args"]],
                cwd=child["cwd"],
                env=child["env"],
                input=asked["prompt"],
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
        block["name"]
        for record in trace
        if record.get("type") == "assistant"
        for block in record["message"].get("content", [])
        if block.get("type") == "tool_use"
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
    }


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
    ran = leaf.fork({"basis": asked["basis"], **taken(run)}, check=False)
    if ran.returncode:
        return {"checks": {"answered": False}, "refused": ran.stderr.strip()}
    applied = json.loads(ran.stdout)
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
            }
            for record in applied["wrote"]
        ),
        *note.get("findings", []),
    ]
    labels = scenario.get("labels", {})
    matched = match(items, labels)
    found, changed = matched["found"], applied.get("changed", [])
    shown = words_of(leaf.python(PAGE_TEXT, str(page))) if changed else ""

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
        },
        "items": items,
        "found": {str(index): item for index, item in found.items()},
        "named": matched["named"],
        "changed": changed,
        "told": applied.get("told", []),
        "texts": {"judge": judge_text(turns, asked["prompt"], items, matched, changed)},
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


def score_line(leaf: Leaf, page: Path, scenario: dict, turns: list) -> dict:
    """Score the working line the arm's Leaf posted from a line fork's answer, as its
    `fork_outcome` note records it."""
    note = leaf.python(NOTE, str(page), "fork_outcome") or {}
    if note.get("refused") or not note:
        return {"checks": {"answered": False}, "refused": note.get("refused")}
    thread = json.dumps(scenario["waiting"], indent=1, ensure_ascii=False)
    conversation = f"<conversation>\n{conversation_text(turns)}\n</conversation>\n\n"
    running = json.dumps(scenario.get("running", []), indent=1, ensure_ascii=False)
    line = note.get("text") if "line" in note else None
    return {
        "checks": {
            "answered": True,
            "lined": line is not None,
            # Who should do the work: `take` where a fork of the session could do it
            # beside the session, the case's label.
            "judged": note.get("work") == scenario["labels"]["work"],
        },
        "outcome": note["outcome"],
        "note": note,
        "texts": {
            "line": f"{conversation}<running>\n{running}\n</running>\n\n"
            f"<thread>\n{thread}\n</thread>\n\n<line>\n{line or '(no line)'}\n</line>",
        },
    }
