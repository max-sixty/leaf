"""Leaf's clerk: a fork of the agent's conversation, made as each of its turns ends,
that writes the page bookkeeping the conversation states and the page lacks.

An agent does the user's work and Leaf's bookkeeping in one context, and late in long
sessions the bookkeeping slips: on 2026-10-25 five sessions holding live pages left
the decisions waiting on the user only in their chat replies, so On me read empty, and
rewording the skill changed 0 of 6 replays of such a session. A fork of the whole
conversation reads what the agent said and learned, so Leaf asks one, and writes what
it finds itself rather than prompting the agent, which would cost a turn and invite
rework. The user chose this shape on 2026-10-29 over a digest of the final reply, an
advisor that prompts the agent, and a clerk agent that also rewrites the page.

This module is the fork's one home, shared by every harness: what it is asked
(`fork_prompt`, with each page's state as `page_facts` reads it), the answer it must
give (`ANSWER`), and what Leaf does with that answer (`apply_answer`). A harness only
makes the fork and carries the two halves (`cmd_fork`): Claude Code's hooks module
calls `$.model.fork` from `turn.complete` (`hooks/claude-code.ts`). Codex would fork
with App Server's `thread/fork` (ephemeral) and Pi's extension by resending its
session, each handing the answer back the same way; neither does yet.

The answer is three things, each written where the user or the agent reads it:

- `status`, for each page, the one line its status should show now. Leaf writes it as
  the line of a `waiting` declaration (`events.md`, `status`), and only where the
  page is open and no start of the agent's holds an item, so it never puts down work
  in hand or reopens a closed page, and the agent's own line stands wherever it wrote
  one. A line equal to the one shown writes nothing.
- `on_me`, each decision left to the user that On me doesn't hold: an ask the work
  waits on (🟡), or a call the agent made that the user may reverse (🔵), since the
  user's standing rule is that every decision left to them belongs On me. Leaf opens
  each as a to-do on the user, marked `by: "leaf"`, which the panel shows as added by
  Leaf from the agent's reply, so the user sees where it came from and can drop it.
- `missed`, page bookkeeping the state shows undone: an owed update nobody works on,
  input overdue or never delivered, an open ask nobody will act on, a failed `leaf`
  command, a page left open after its work. Leaf writes nothing for these; the agent
  hears them.

Each thing Leaf wrote, and each missed step, is queued as one line for the agent's
next step (`QUEUED`), which the next prompt or tool-boundary hook adds to its context
(`hook_transport.carry_turn`), so the agent neither repeats nor contradicts the
records and costs no turn of its own. A line the hook handed over leaves the queue
(`heard`); a prompt Escape drops loses it, as it loses nothing else the agent needs.

The fork's reading is of the turn that ended. Where another turn of the session has
opened by the time it answers, the user has spoken since, so the answer is dropped
whole (`basis`): an ask they may be answering that moment would land On me as noise.

Measured on 2026-10-29 by replaying 21 recorded turn ends three times each on Opus
5.5 (`~/.tmp/leaf.agent-channels/replay/`): a fork asked only for asks found 63 of 63
🟡 asks missing from On me with one false finding in 39 clean runs, and none of the
36 🔵 calls, which this question now names; warm, a fork cost $0.11 and 20 s
(medians). Claude Code's fork reuses the session's cached prefix only while its
system prompt, tools and effort match the session's, which `$.model.fork` keeps by
resending the main thread's own last request.
"""

import json
from datetime import datetime
from pathlib import Path

from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    session_file,
    session_lock_path,
    session_record,
)

# The length of a to-do's title (`todo` in the kernel registry), which the fork is
# asked to keep a line under. A model can't count characters, so the answer takes a
# longer line and Leaf shortens a title to fit (`_title`): refusing the answer would
# drop the asks it found with it, as 2 of the first 26 replayed answers were.
TITLE_LIMIT = 80
_LINE = {"type": "string", "minLength": 1, "pattern": r"\S"}

ANSWER = {
    "type": "object",
    "properties": {
        "status": {
            "description": "Each page's status line, by its path.",
            "type": "object",
            "additionalProperties": _LINE,
        },
        "on_me": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "minLength": 1},
                    "title": _LINE,
                    "kind": {"enum": ["ask", "call"]},
                    "quote": {"type": "string"},
                },
                "required": ["page", "title", "kind", "quote"],
                "additionalProperties": False,
            },
        },
        "missed": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
    "required": ["status", "on_me", "missed"],
    "additionalProperties": False,
}

QUEUED = Record(
    "clerk",
    described(
        "The lines Leaf's clerk queued for a session's next step, in the state "
        "home's `sessions/<digest>.clerk` (`state.session_file`): one for each "
        "record it wrote and each step it found missed (`clerk`).",
        object_schema({"lines": {"type": "array", "items": STRING}}),
    ),
    since=36,
)

# The words that open the fork's question, which the replay and the transcript carry.
OPENING = "<leaf-fork-check>"


def _clock(ts: str | None) -> str:
    return datetime.fromisoformat(ts).strftime("%H:%M") if ts else "?"


def _said(event: dict | None) -> str:
    """What an update the user sent says, in one line of up to 300 characters."""
    if event is None:
        return ""
    words = event.get("text") or event.get("token") or ""
    if not words and event["kind"] == "action":
        words = f"a {event['action']} on {event['widget']}"
    if not words and event.get("drawing"):
        words = "a drawing"
    return " ".join(str(words).split())[:300]


def page_facts(state: dict, events: list) -> dict:
    """What the fork is shown of one page: `state` as `leaf page state` prints it, and
    `events`, the log it was read from, for the words of the user's updates."""
    by_id = {event["id"]: event for event in events}
    threads = {thread["id"]: thread for thread in state["threads"]}
    obligations = {item["id"]: item for item in state["obligations"]}
    todos = {todo["id"]: todo for todo in state["todos"]}
    workflows = {item["input"]: item for item in state["workflows"]}

    def thread_name(thread: str | None) -> str:
        title = (threads.get(thread) or {}).get("title") if thread else None
        return f'"{title}"' if title else "an untitled thread"

    on_me = []
    for row in state["queues"]["on_user"]:
        if row["kind"] == "todo":
            todo = todos[row["id"]]
            on_me.append(f"to-do: {todo['title']}")
            continue
        record = obligations[row["id"]]
        text = " ".join((record["prompt"].get("text") or "").split())[:300]
        if row["kind"] == "message":
            on_me.append(
                f"a reply to your message in {thread_name(row['thread'])}: {text}"
            )
        elif row["kind"] == "update":
            on_me.append(
                f"the user's update to send again in {thread_name(row['thread'])}"
            )
        else:
            on_me.append(
                f"decision ({record['source'].get('tag', row['kind'])}): {text}"
            )

    on_agent, undelivered = [], []
    for row in state["queues"]["on_agent"]:
        if row["kind"] == "todo":
            todo = todos[row["id"]]
            running = todo["running"]
            on_agent.append(
                f"your to-do: {todo['title']} ("
                + (f'started: "{running["text"]}"' if running else "not started")
                + ")"
            )
            continue
        flow = workflows.get(row["id"].removeprefix("update:"))
        said = _said(by_id.get(flow["input"])) if flow else ""
        where = thread_name(row["thread"]) if row["thread"] else "the page"
        condition = (flow or {}).get("condition") or {}
        stage = (flow or {}).get("stage")
        if (
            stage in {"sending", "sent", "queued"}
            or condition.get("operation") == "delivery"
        ):
            undelivered.append(
                f"the user's update in {where} at {_clock(flow and flow['ts'])}, not yet "
                f"delivered to you: {said}"
            )
        elif condition.get("kind") in {"ended", "interrupted"}:
            on_agent.append(
                f"an answer you owe in {where}, picked up in a turn that ended "
                f"without it: {said}"
            )
        else:
            on_agent.append(f"an answer you owe in {where}: {said}")

    listed = {row["id"] for row in state["queues"]["on_user"]} | {
        row["id"] for row in state["queues"]["on_agent"]
    }
    stranded = [
        f"decision ({record['source'].get('tag', record['source']['kind'])}): "
        + " ".join((record["prompt"].get("text") or "").split())[:300]
        for record in state["obligations"]
        if record["status"] == "open"
        and record["next_actor"] is None
        and record["id"] not in listed
    ]
    # What Leaf added from the agent's replies and the user has since ended or
    # dropped, so a later fork doesn't add it again.
    settled = [
        f"to-do: {record['prompt']['text']} ("
        + ("dropped" if record["status"] == "withdrawn" else "done")
        + ")"
        for record in state["obligations"]
        if record["source"]["kind"] == "todo"
        and record["source"].get("by") == "leaf"
        and record["status"] != "open"
    ]
    activity = state["activity"]
    return {
        "title": state["title"],
        "path": state["page"],
        "status": status_words(state["status"], activity),
        "on_me": on_me,
        "on_agent": on_agent,
        "undelivered": undelivered,
        "stranded": stranded,
        "settled": settled,
    }


def status_words(status: dict, activity: dict) -> str:
    """The page's status as the fork reads it: its kind, and the line it shows."""
    words = {
        "working": "working",
        "listening": "open, waiting for the user",
        "stalled": "your turn ended with work in hand",
        "away": "nothing is taking the user's input",
        "closed": "closed: done with this page",
        "unheld": "no session holds it",
    }.get(activity["kind"], activity["kind"])
    line = activity["detail"]
    return f'{words}; line: "{line}"' if line else f"{words}; no line"


def _block(facts: dict) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "(none)"

    parts = [
        f'Page "{facts["title"]}" ({facts["path"]})',
        f"Status: {facts['status']}",
        f"On me, what the page lists as waiting on the user:\n{lines(facts['on_me'])}",
    ]
    if facts.get("on_agent"):
        parts.append(
            f"On you, what the page lists as waiting on you:\n{lines(facts['on_agent'])}"
        )
    if facts.get("undelivered"):
        parts.append(
            f"The user's input that hasn't reached you:\n{lines(facts['undelivered'])}"
        )
    if facts.get("stranded"):
        parts.append(
            "Open on the page, waiting on nobody:\n" + lines(facts["stranded"])
        )
    if facts.get("settled"):
        parts.append(
            "Added by Leaf from the agent's replies and since settled by the user; "
            "don't add these again:\n" + lines(facts["settled"])
        )
    return "\n".join(parts)


def fork_prompt(pages: list[dict]) -> str:
    """The one message a fork answers: what it is for, each page's facts
    (`page_facts`), the three questions and the answer's form (`ANSWER`)."""
    blocks = "\n\n".join(_block(facts) for facts in pages)
    return f"""{OPENING}
This message comes from Leaf, not the user. You are a fork of this session, made as the agent's turn ended, to keep the page's records current. The main session carries on separately and never reads this exchange: Leaf writes what you answer onto the page, where the user sees it, and tells the agent in one line. Don't call tools and don't continue the work; answer from the conversation above and the page state below.

{blocks}

The user's standing rule is that every decision left to them belongs on their On me list, where they see it and can withdraw it. Answer three things:

status: for each page, the one line its status should show now, under {TITLE_LIMIT} characters, in the agent's voice with no name in front: whether the agent is working (on what), waiting on the user (for what) or done (with what). Write it even where the line above still holds.

on_me: each decision left to the user, in the agent's replies or anywhere in the conversation, that no On me item above holds. Two kinds count:
- "ask": a decision, answer, permission or step only the user can take, that the work waits on or that the agent asked for, marked (🟡) or not ("let me know", "say if", "want me to").
- "call": a choice the agent made on its own that the user may want to reverse: a default it picked, something it kept, dropped or left as it was, a reversible step it took on their behalf (🔵, "I went with", "I kept", "unless you'd rather").
Leave out what the user has since answered, what an On me item already covers, and what the agent will settle itself. Give each: "page", the page's path; "title", what the user decides, under {TITLE_LIMIT} characters, as a line on their list ("Merge the two mark styles, or keep both?"); "kind"; "quote", the agent's words that leave it to the user.

missed: page bookkeeping the state above or the conversation shows undone, one line each naming the page: an update the agent owes with nobody working on it; the user's input overdue or never delivered; an open ask the conversation has superseded or that nobody will act on; a leaf command that failed and was not run again; a page left open after its work is done. [] if none.

Reply with only this JSON object, no code fence:
{{"status": {{"<page path>": "<line>"}}, "on_me": [{{"page": "<page path>", "title": "<line>", "kind": "ask" or "call", "quote": "<words>"}}], "missed": ["<line>"]}}
</leaf-fork-check>"""


def read_answer(text: str) -> dict:
    """The fork's reply as an answer `ANSWER` takes, or `Refused` saying why not. A
    fenced or prefaced object is read from its first `{` to its last `}`."""
    from .refusals import Refused
    from .registry.schema import json_validator

    start, end = text.find("{"), text.rfind("}")
    if start < 0:
        raise Refused("the fork's answer holds no JSON object")
    try:
        answer = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise Refused(f"the fork's answer is not JSON ({error.msg})") from error
    errors = sorted(json_validator(ANSWER).iter_errors(answer), key=str)
    if errors:
        raise Refused(f"the fork's answer doesn't fit its schema: {errors[0].message}")
    return answer


def basis(session_id: str) -> dict | None:
    """The turn a fork reads, as the session's lifecycle names it."""
    record = session_record(session_id)
    return record and {"turn": record["turn"], "opened": record["turn_opened"]}


def cmd_fork(session_id: str, payload: dict) -> dict | None:
    """One half of a fork for `session_id`, as `leaf hook --fork` hands it over:
    without `answer` in `payload`, the `question`; with one, `take_answer`."""
    if not session_id:
        return None
    if "answer" in payload:
        return take_answer(session_id, payload["answer"], payload.get("basis"))
    return question(session_id)


def question(session_id: str) -> dict | None:
    """What to fork `session_id`'s conversation with, as `{"prompt", "basis"}`, or
    None where it holds no page."""
    from .service import owned_pages

    facts = [
        facts for page in owned_pages(session_id) if (facts := _facts(page)) is not None
    ]
    if not facts:
        return None
    return {"prompt": fork_prompt(facts), "basis": basis(session_id)}


def take_answer(session_id: str, text: str, asked: dict | None) -> dict:
    """What Leaf wrote from `text`, the fork's reply to the question asked at
    `asked`, its `basis` (`apply_answer`), or why it wrote nothing."""
    if basis(session_id) != asked:
        return {"dropped": "another turn opened since the fork was made"}
    return apply_answer(session_id, read_answer(text))


def _facts(page_dir: Path) -> dict | None:
    from .agent_state import page_state
    from .service import PageTransaction

    try:
        with PageTransaction(page_dir) as page:
            return page_facts(page_state(page_dir, page.events), page.events)
    except FileNotFoundError:
        return None


def _title(words: str) -> str:
    """`words` as an On me to-do's title: on one line, and cut at a word to fit
    `TITLE_LIMIT`, ending in an ellipsis where it was cut."""
    title = " ".join(words.split())
    if len(title) <= TITLE_LIMIT:
        return title
    return title[: TITLE_LIMIT - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def apply_answer(session_id: str, answer: dict) -> dict:
    """Write `answer`'s status lines and On me items onto the pages `session_id` holds,
    and queue a line for each, and for each missed step, for the agent's next step;
    what it wrote."""
    from .event_contracts import append_admitted
    from .service import PageTransaction, owned_pages

    pages = {str(page): page for page in owned_pages(session_id)}
    wrote: list[dict] = []
    told: list[str] = []
    for path, page_dir in pages.items():
        items = [item for item in answer["on_me"] if item["page"] == path]
        line = answer["status"].get(path)
        if not items and line is None:
            continue
        with PageTransaction(page_dir) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                continue
            identity = {"agent": claim["agent"], "session": claim["id"]}
            from .agent_state import page_state

            state = page_state(page_dir, page.events)
            listed = {
                " ".join(todo["title"].casefold().split())
                for todo in state["todos"]
                if todo["owner"] == "user"
            }
            for item in items:
                title = _title(item["title"])
                if title.casefold() in listed:
                    continue
                record, _ = append_admitted(
                    page,
                    {
                        "kind": "todo",
                        "author": "agent",
                        **identity,
                        "owner": "user",
                        "subject": {"kind": "page"},
                        "title": title,
                        "by": "leaf",
                    },
                )
                wrote.append(record)
                told.append(
                    f'Leaf added "{record["title"]}" to On me on {path} from your '
                    f"reply, as to-do {record['id']}; leave it, or end it with "
                    f"`leaf task end {path} {record['id']} --outcome dropped` if it "
                    "isn't the user's to decide."
                )
            activity = state["activity"]
            if (
                line is not None
                and state["status"]["state"] == "waiting"
                and activity["detail_source"] is None
                and activity["kind"] not in {"closed", "unheld"}
                and " ".join(line.split()) != activity["detail"]
            ):
                record, _ = append_admitted(
                    page,
                    {
                        "kind": "status",
                        "author": "agent",
                        **identity,
                        "state": "waiting",
                        "text": " ".join(line.split()),
                    },
                )
                wrote.append(record)
                told.append(f'Leaf set the status on {path} to "{record["text"]}".')
    told += [f"Leaf: {step}" for step in answer["missed"]]
    queue(session_id, told)
    return {"wrote": wrote, "told": told}


def queue(session_id: str, lines: list[str]) -> None:
    """Add `lines` to what the session's next step hears."""
    if not lines:
        return
    path = session_file(session_id, QUEUED.kind)
    with flocked(session_lock_path(session_id)):
        held = QUEUED.read(path) or {"lines": []}
        QUEUED.write(path, {"lines": [*held["lines"], *lines]})


def queued(session_id: str) -> list[str]:
    """What the session's next step hears from the clerk."""
    held = QUEUED.read(session_file(session_id, QUEUED.kind))
    return held["lines"] if held else []


def heard(session_id: str, lines: list[str]) -> None:
    """Take `lines`, which a hook handed the agent, off the queue; lines queued since
    stay for the next step."""
    if not lines:
        return
    path = session_file(session_id, QUEUED.kind)
    with flocked(session_lock_path(session_id)):
        held = QUEUED.read(path) or {"lines": []}
        rest = (
            held["lines"][len(lines) :]
            if held["lines"][: len(lines)] == lines
            else held["lines"]
        )
        if rest:
            QUEUED.write(path, {"lines": rest})
        else:
            path.unlink(missing_ok=True)
