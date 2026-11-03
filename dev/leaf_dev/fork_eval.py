"""Replay Leaf's two conversation forks on short constructed conversations, and score
each answer: the turn-end check (`leaf.clerk`) and the fork that answers a thread
message or hands it to the session (`leaf.forks`). Claude Code makes both forks, so
every case runs on that harness alone.

A case in `workflows/fork_eval.yaml` is a conversation written for one decision a
fork's prompt asks about, the page the session holds (an authored source with the
log events the case needs), and labels. Constructed cases are cheap and run
anywhere, but can't show the drift late in a long session that the turn-end check
exists for; a replay of a recorded session measures that.

Each arm's own Leaf writes the question and reads the answer. The executor builds the
page in a throwaway state home, opens a turn for a fresh session id and claims the
page as that session, as Claude Code's environment would (`CLAUDE_CODE_SESSION_ID`,
with this process as `CLAUDE_PID`). It then asks the arm's `leaf hook --fork` for the
fork's prompt, as `forkStep` in `hooks/claude-code.ts` does: with the session alone
for the turn-end check, and with the held thread for a reply. For a reply a process
of the arm's holds the session's forks lane (`forks.take_lane`) while the user's
waiting messages are admitted after it, as the pages follower holds it; no follower
runs, so no hold runs out (`forks.BOUND_S`) while the fork thinks.

The conversation is rendered as a Claude Code transcript under the same session id,
in a home (`claude_home`) and cwd of its own outside the repository, and resumed once
with `claude -p` and the prompt, on the case's model and effort as a live fork has
them (`$.model.fork` resends the session's own). The records keep the shapes Claude
Code writes, without thinking blocks. A background command's result records no task
id: Claude Code tells a resumed session that a task it recorded has stopped, which a
live fork never hears, so the replay needs no sentence of its own in the prompt. The
fork runs with `--tools ""`, so nothing can run and its request carries no tool
definitions, where a live fork resends the session's tools and is told not to call
them. Hooks, plugins and MCP servers are off.

The answer goes back to the arm's Leaf. A turn-end answer goes through `leaf hook
--fork` as the module hands it back (`clerk.take_answer`), so a refused answer fails
`answered`, its asks go On me, and a stale passage's edit is placed by the arm's
`clerk.fixed_source`, checked and published. A reply is read with the arm's
`clerk.read_answer(text, forks.ANSWER)`.

A turn-end item is matched to a label by the words it rests on: one of the label's
`words` stands in the item's quote, passage or edit words. An `expect` label needs a
matching item of its kind, and a stale one's `edit` either landed over the labelled
words or, where the label says null, was left null. An item of any kind in the same
part of the answer (`asks` or `findings`) matching an `absent` label fails the case,
since it names what the case's guardrail leaves out. Every other item, with each change
Leaf made, goes to the text judge (`metadata.texts.judge`): a real finding nobody
labelled is no false alarm. A reply is scored on its decision, and a reply's words
on the judge.

Cost is priced from the result's `usage`, the resumed call's own tokens, at Opus 5.5's
list prices; `total_cost_usd` counts the resumed history too.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from leaf.harness import ClaudeCodeHarness
from leaf_dev import ROOT
from leaf_dev.arms import build_source, claude_environment, claude_home, environment
from leaf_dev.commands.distribution import current_kernel
from leaf_dev.eval_cases import definition
from leaf_dev.page_fixtures import admit_events, fixture_environment

DEFINITION = definition("fork_eval")
DEFINITION_FILE = ROOT / "evals/workflows/fork_eval.yaml"
CASES = DEFINITION["cases"]

# The parts of a turn-end answer, with the kinds each holds.
PARTS = {"asks": ("question", "step"), "findings": ("stale", "settled", "unshown")}

# Opus 5.5 list prices, dollars per million tokens.
PRICES = {"input": 5.0, "write_5m": 6.25, "write_1h": 10.0, "read": 0.5, "output": 25.0}

# Holds the session's forks lane in the arm's Python until stdin closes, and waits
# past the take's millisecond, since a message admitted in it stays with the session.
LANE = """
import sys, time
from leaf.forks import lane_since, take_lane
lane = take_lane(sys.argv[1])
since = lane_since(sys.argv[1])
while time.time() < since + 0.002:
    time.sleep(0.0005)
print("held", flush=True)
sys.stdin.read()
"""

# Reads a reply fork's answer with the arm's own reader.
READ_REPLY = """
import json, sys
from leaf.clerk import read_answer
from leaf.forks import ANSWER
from leaf.refusals import Refused
try:
    print(json.dumps({"answer": read_answer(sys.stdin.read(), ANSWER)}))
except Refused as error:
    print(json.dumps({"refused": str(error)}))
"""


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    scenario = CASES[case]
    if scenario["fork"] == "reply":
        return ["answered", "decision"]
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
    conversation once, and hand the answer back to the arm's Leaf for scoring."""
    if harness != ClaudeCodeHarness.name:
        raise ValueError("Leaf's conversation forks run only in Claude Code")
    scenario = CASES[case]
    payload = current_kernel(payload)
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
        admit_events(
            payload,
            page,
            scenario["log"],
            log=DEFINITION_FILE,
            env=leaf.env,
            acknowledge=True,
        )
    leaf.run(
        "hook",
        *("--harness", "claude-code"),
        stdin={"hook_event_name": "UserPromptSubmit", "prompt_id": "p1"},
    )
    leaf.run("page", "claim", str(page))
    turns = substitute(
        conversation(scenario), {"{page}": str(page), "{session}": session}
    )
    asked = (
        reply_question(leaf, page, scenario)
        if scenario["fork"] == "reply"
        else leaf.fork({})
    )
    (work / "prompt.txt").write_text(asked["prompt"])
    run = fork(asked["prompt"], scenario, session, turns, work)
    metadata = {
        "fork": scenario["fork"],
        "session": session,
        "harness": harness,
        **{key: run[key] for key in ("model", "effort", "usage", "wall_s")},
        "cost_usd": run["cost"],
        "tool_calls": run["tool_calls"],
    }
    response = {
        "output": run["text"] or f"(no answer: {run['failed']})",
        "cost": run["cost"],
        "metadata": metadata,
    }
    checks = expected_checks(case)
    if run["text"] is None:
        metadata["checks"] = dict.fromkeys(checks, False)
        return {**response, "error": f"the fork gave no answer: {run['failed']}"}
    if scenario["fork"] == "reply":
        metadata.update(score_reply(leaf, scenario, run["text"], turns))
    else:
        metadata.update(score_turn_end(leaf, scenario, asked, run, turns, work))
    metadata["checks"] = {name: metadata["checks"][name] for name in checks}
    return response


class Leaf:
    """The arm's launcher and Python under the case's state home, as the session's
    Claude Code environment would run them."""

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
        """One step of a fork, as `forkStep` in `hooks/claude-code.ts` runs it: the
        question it printed, or with `check` False the finished process."""
        ran = self.run(
            *("hook", "--harness", "claude-code", "--if-claimed", "--fork"),
            stdin={"hook_event_name": "Fork", **payload},
            check=check,
        )
        if not check:
            return ran
        if not ran.stdout.strip():
            raise RuntimeError("leaf hook --fork asked no question")
        return json.loads(ran.stdout)

    def python(self, program: str, *args: str, **kwargs) -> subprocess.Popen:
        return subprocess.Popen(
            [str(self.payload / ".venv/bin/python"), "-I", "-c", program, *args],
            env=self.env,
            text=True,
            **kwargs,
        )


def reply_question(leaf: Leaf, page: Path, scenario: dict) -> dict:
    """The held thread's question: hold the lane, admit the user's waiting messages
    after it, and ask for the thread as the pages follower would list it."""
    holder = leaf.python(
        LANE, leaf.session, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    assert holder.stdin is not None and holder.stdout is not None
    try:
        if holder.stdout.readline().strip() != "held":
            raise RuntimeError("the forks lane was not taken")
        waiting = scenario["waiting"]
        admit_events(leaf.payload, page, waiting, log=DEFINITION_FILE, env=leaf.env)
        thread = {
            "page": str(page),
            "thread": scenario["thread"],
            "inputs": [message["id"] for message in waiting],
        }
        return leaf.fork({"thread": thread, "running": scenario.get("running", [])})
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)


def conversation(scenario: dict) -> list[dict]:
    """The case's turns, each `from` item replaced by the named conversation's."""
    return [
        expanded
        for turn in scenario["conversation"]
        for expanded in (
            DEFINITION["conversations"][turn["from"]] if "from" in turn else [turn]
        )
    ]


def substitute(value, values: dict):
    """`value` with each placeholder (`{page}`, `{session}`) in its strings replaced."""
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
                    "model": "claude-opus-5-5",
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


def fork(prompt: str, scenario: dict, session: str, turns: list, work: Path) -> dict:
    """Resume the rendered conversation once with `prompt`, as `$.model.fork` forks
    it, in a home and cwd of its own outside the repository, and keep its stream and
    transcript under `work`."""
    model = scenario.get("model", DEFINITION["model"])
    effort = scenario.get("effort", DEFINITION["effort"])
    with tempfile.TemporaryDirectory(prefix="leaf-fork-") as directory:
        cwd = Path(directory).resolve() / "cwd"
        cwd.mkdir()
        home = claude_home(cwd.with_name("home"))
        project = home / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
        project.mkdir(parents=True)
        start = datetime.fromisoformat(DEFINITION["start"])
        kept = project / f"{session}.jsonl"
        kept.write_text(
            "".join(
                json.dumps(record) + "\n"
                for record in transcript(turns, session, cwd, start)
            )
        )
        settings = {"disableAllHooks": True}
        command = [
            *("nice", "-n", "10", "claude", "-p", "--resume", session),
            *("--model", model, "--effort", effort, "--max-turns", "2"),
            *("--tools", "", "--strict-mcp-config", "--settings", json.dumps(settings)),
            *("--output-format", "stream-json", "--verbose"),
        ]
        started = time.monotonic()
        ran = subprocess.run(
            command,
            input=prompt,
            cwd=cwd,
            env=claude_environment(home),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        wall = time.monotonic() - started
        shutil.copy(kept, work / "transcript.jsonl")
    (work / "fork.jsonl").write_text(ran.stdout)
    (work / "fork.stderr").write_text(ran.stderr)
    stream = [json.loads(line) for line in ran.stdout.splitlines() if line.strip()]
    result = next((r for r in reversed(stream) if r.get("type") == "result"), {})
    usage = result.get("usage") or {}
    text = result.get("result") if result.get("subtype") == "success" else None
    return {
        "text": text,
        "failed": None
        if text is not None
        else result.get("subtype") or f"claude exited {ran.returncode}",
        "model": model,
        "effort": effort,
        "usage": usage,
        "cost": price(usage),
        "wall_s": round(wall, 1),
        "elapsed_ms": result.get("duration_ms"),
        "tool_calls": [
            block["name"]
            for record in stream
            if record.get("type") == "assistant"
            for block in record["message"].get("content", [])
            if block.get("type") == "tool_use"
        ],
    }


def price(usage: dict) -> float:
    """What one call's `usage` costs at `PRICES`."""
    written = usage.get("cache_creation") or {}
    hour = written.get("ephemeral_1h_input_tokens", 0)
    minutes = written.get(
        "ephemeral_5m_input_tokens", usage.get("cache_creation_input_tokens", 0) - hour
    )
    dollars = (
        usage.get("input_tokens", 0) * PRICES["input"]
        + minutes * PRICES["write_5m"]
        + hour * PRICES["write_1h"]
        + usage.get("cache_read_input_tokens", 0) * PRICES["read"]
        + usage.get("output_tokens", 0) * PRICES["output"]
    )
    return round(dollars / 1e6, 5)


def words_of(text: str) -> str:
    """`text` as its lowercase words and numbers, each between single spaces."""
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.casefold())) + " "


def rests_on(item: dict, label: dict) -> bool:
    """Whether one of `label`'s words stands in `item`'s quote, passage or edit."""
    held = "|".join(
        words_of(text or "")
        for text in (
            item.get("quote"),
            item.get("passage"),
            (item.get("edit") or {}).get("words"),
        )
    )
    words = label["words"] if isinstance(label["words"], list) else [label["words"]]
    return any(words_of(phrase) in held for phrase in words)


def match(answer: dict, labels: dict) -> dict:
    """Each answer item matched to the first label it rests on: the item each
    expected label of its kind found, by the label's index; each item naming an
    absent label in its part, of whatever kind; and the rest, among them a second
    item of a found label's kind on its words."""
    found: dict[int, dict] = {}
    named, extra = [], []
    for part, kinds in PARTS.items():
        for item in answer.get(part, []):
            item = {**item, "part": part}
            expect = [
                index
                for index, label in enumerate(labels.get("expect", []))
                if label["kind"] == item["kind"] and rests_on(item, label)
            ]
            absent = [
                label
                for label in labels.get("absent", [])
                if label["kind"] in kinds and rests_on(item, label)
            ]
            if expect and expect[0] not in found:
                found[expect[0]] = item
            elif absent:
                named.append({"item": item, "label": absent[0]})
            else:
                extra.append(
                    {**item, "repeats_a_labelled_item": True} if expect else item
                )
    return {"found": found, "named": named, "extra": extra}


def score_turn_end(
    leaf: Leaf, scenario: dict, asked: dict, run: dict, turns: list, work: Path
) -> dict:
    """Hand the answer to the arm's Leaf as the module does, then score its items
    against the case's labels, and pack what the labels don't settle for the judge."""
    taken = leaf.fork(
        {
            "basis": asked["basis"],
            "answer": run["text"],
            "usage": run["usage"],
            "elapsed_ms": run["elapsed_ms"],
        },
        check=False,
    )
    if taken.returncode:
        return {
            "checks": dict.fromkeys(
                ("answered", "labels-found", "edits-land", "guardrails-held"), False
            ),
            "refused": taken.stderr.strip(),
        }
    applied = json.loads(taken.stdout)
    (work / "applied.json").write_text(json.dumps(applied, indent=1))
    # The arm's reader took the answer, so it holds one object, read as it reads it.
    answer = json.loads(run["text"][run["text"].find("{") : run["text"].rfind("}") + 1])
    labels = scenario.get("labels", {})
    matched = match(answer, labels)
    found, changed = matched["found"], applied.get("changed", [])
    expect = labels.get("expect", [])

    def landed(label: dict, item: dict) -> bool:
        """The item's edit is null where the label's is, or else a change Leaf made
        covers the label's words or lies within them."""
        if label["edit"] is None:
            return item.get("edit") is None
        stale = words_of(label["edit"]["words"])
        return any(
            words_of(change["old"]) in stale or stale in words_of(change["old"])
            for change in changed
        )

    return {
        "checks": {
            "answered": True,
            "labels-found": all(
                index in found and found[index]["kind"] == label["kind"]
                for index, label in enumerate(expect)
            ),
            "edits-land": all(
                index in found and landed(label, found[index])
                for index, label in enumerate(expect)
                if "edit" in label
            ),
            "guardrails-held": not matched["named"],
        },
        "answer": answer,
        "found": {str(index): item for index, item in found.items()},
        "named": matched["named"],
        "extra": matched["extra"],
        "changed": changed,
        "told": applied.get("told", []),
        "texts": {
            "judge": judge_text(turns, asked["prompt"], matched["extra"], changed)
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


def judge_text(turns: list, prompt: str, extra: list, changed: list) -> str:
    """What the judge reads: the conversation, the question the fork was asked, and
    the items no label settles, with each change Leaf made."""
    if not extra and not changed:
        return "No unlabelled items and no changes."

    def listed(items: list) -> str:
        return json.dumps(items, indent=1, ensure_ascii=False) if items else "none"

    return (
        f"<conversation>\n{conversation_text(turns)}\n</conversation>\n\n"
        f"<question>\n{prompt}\n</question>\n\n"
        f"<unlabelled-items>\n{listed(extra)}\n</unlabelled-items>\n\n"
        f"<changes>\n{listed(changed)}\n</changes>"
    )


def score_reply(leaf: Leaf, scenario: dict, text: str, turns: list) -> dict:
    """Read a reply fork's answer with the arm's reader and score its decision."""
    reader = leaf.python(READ_REPLY, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    read = json.loads(reader.communicate(text, timeout=60)[0])
    if "refused" in read:
        return {
            "checks": {"answered": False, "decision": False},
            "refused": read["refused"],
        }
    answer = read["answer"]
    decision = "reply" if "reply" in answer else "hand_over"
    thread = json.dumps(scenario["waiting"], indent=1, ensure_ascii=False)
    return {
        "checks": {"answered": True, "decision": decision == scenario["decision"]},
        "answer": answer,
        "decision": decision,
        "texts": {
            "reply": f"<conversation>\n{conversation_text(turns)}\n</conversation>\n\n"
            f"<thread>\n{thread}\n</thread>\n\n"
            f"<reply>\n{answer.get('reply', '(handed over)')}\n</reply>"
        },
    }
