"""Leaf's clerk: a fork of the agent's conversation, made as each of its turns ends,
that finds what the agent left to the user without putting it On me, and puts it
there.

An agent does the user's work and Leaf's bookkeeping in one context, and late in long
sessions the bookkeeping slips: on 2026-10-25 five sessions holding live pages left
the decisions waiting on the user only in their chat replies, so On me read empty, and
rewording the skill changed 0 of 6 replays of such a session. A fork of the whole
conversation reads what the agent said, so Leaf asks one, and writes what it finds
itself rather than prompting the agent, which would cost a turn and invite rework.
The user chose this shape on 2026-10-29 over a digest of the final reply, an advisor
that prompts the agent, and a clerk agent that also rewrites the page.

It asks about one thing: decisions, answers, permissions or steps the agent left to
the user that no On me item holds. A first version also wrote the status line and
named missed page steps; the user narrowed it on 2026-10-29 to start from this one
class, in Leaf's own words, and what the page state alone settles, such as input not
yet delivered, is code's to report rather than a model's.

This module is the fork's one home, shared by every harness: what it is asked
(`fork_prompt`, with each page's On me as `page_facts` reads it), the answer it must
give (`ANSWER`), and what Leaf does with that answer (`apply_answer`). A harness only
makes the fork and carries the two halves (`cmd_fork`): Claude Code's hooks module
calls `$.model.fork` from `turn.complete` (`hooks/claude-code.ts`). Codex would fork
with App Server's `thread/fork` (ephemeral) and Pi's extension by resending its
session, each handing the answer back the same way; neither does yet.

Leaf opens each ask as a to-do on the user, marked `by: "leaf"`, which the panel shows
as added by Leaf from the agent's reply, so the user sees where it came from and can
drop it. One the user has settled is shown to later forks, so it isn't added again.
Each to-do written is queued as one line for the agent's next step (`QUEUED`), which
the next prompt or tool-boundary hook adds to its context (`hook_transport.carry_turn`),
so the agent neither repeats nor contradicts it and spends no turn on it. A line the
hook handed over leaves the queue (`heard`); a prompt Escape drops loses it.

The fork's reading is of the turn that ended. Where another turn of the session has
opened by the time it answers, the user has spoken since, so the answer is dropped
whole (`basis`): an ask they may be answering that moment would land On me as noise.

Measured by replaying 21 recorded turn ends three times each on Opus 5.5
(`~/.tmp/leaf.agent-channels/replay/`, `fork3.py` and `score3.py` for this
question). Claude Code's fork reuses the session's cached prefix only while its
system prompt, tools and effort match the session's, which `$.model.fork` keeps by
resending the main thread's own last request.
"""

import json
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
# longer line and Leaf shortens a title to fit (`_title`) rather than refusing the
# answer and every ask it found.
TITLE_LIMIT = 80

ANSWER = {
    "type": "object",
    "properties": {
        "asks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1, "pattern": r"\S"},
                    # The agent's words, which ground the ask in the conversation;
                    # Leaf writes only the title.
                    "quote": {"type": "string"},
                },
                "required": ["page", "title", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["asks"],
    "additionalProperties": False,
}

QUEUED = Record(
    "clerk",
    described(
        "The lines Leaf's clerk queued for a session's next step, in the state "
        "home's `sessions/<digest>.clerk` (`state.session_file`): one for each "
        "to-do it added On me (`clerk`).",
        object_schema({"lines": {"type": "array", "items": STRING}}),
    ),
    since=36,
)

# The words that open the fork's question, which the replay and the transcript carry.
OPENING = "<leaf-fork-check>"


def page_facts(state: dict) -> dict:
    """What the fork is shown of one page, from `state` as `leaf page state` prints
    it: its On me, and the to-dos Leaf added that the user has since settled."""
    threads = {thread["id"]: thread for thread in state["threads"]}
    obligations = {item["id"]: item for item in state["obligations"]}
    todos = {todo["id"]: todo for todo in state["todos"]}

    def words(record: dict) -> str:
        return " ".join((record["prompt"].get("text") or "").split())[:300]

    on_me = []
    for row in state["queues"]["on_user"]:
        if row["kind"] == "todo":
            on_me.append(f"to-do: {todos[row['id']]['title']}")
            continue
        record = obligations[row["id"]]
        if row["kind"] == "message":
            title = (threads.get(row["thread"]) or {}).get("title")
            where = f'"{title}"' if title else "an untitled thread"
            on_me.append(f"a reply to the agent's message in {where}: {words(record)}")
        elif row["kind"] == "update":
            on_me.append("an update of the user's to send again")
        else:
            on_me.append(f"decision: {words(record)}")
    settled = [
        f"{record['prompt']['text']} ("
        + ("dropped" if record["status"] == "withdrawn" else "done")
        + ")"
        for record in state["obligations"]
        if record["source"]["kind"] == "todo"
        and record["source"].get("by") == "leaf"
        and record["status"] != "open"
    ]
    return {
        "title": state["title"],
        "path": state["page"],
        "on_me": on_me,
        "settled": settled,
    }


def _block(facts: dict) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "(none)"

    parts = [
        f'Page "{facts["title"]}" ({facts["path"]})',
        f"On me, what the page lists as waiting on the user:\n{lines(facts['on_me'])}",
    ]
    if facts.get("settled"):
        parts.append(
            "Added by Leaf from earlier replies and since settled by the user; "
            "don't add these again:\n" + lines(facts["settled"])
        )
    return "\n".join(parts)


def fork_prompt(pages: list[dict]) -> str:
    """The one message a fork answers: what it is for, each page's facts
    (`page_facts`), the question and the answer's form (`ANSWER`)."""
    blocks = "\n\n".join(_block(facts) for facts in pages)
    return f"""{OPENING}
This message comes from Leaf, not the user. You are a fork of this session, made as the agent's turn ended, to keep the user's On me list complete. The main session carries on separately and never reads this exchange: Leaf adds what you name to On me, where the user sees it, and tells the agent in one line. Don't call tools and don't continue the work; answer from the conversation above and the page state below.

{blocks}

On me is where the user finds everything waiting on them. Name each decision, answer, permission or step the agent left to the user, in its replies or anywhere in the conversation, that no On me item above holds and the user hasn't answered since. Leave out what the agent will settle itself. Give each: "page", the page's path; "title", the ask as a line on the user's list, under {TITLE_LIMIT} characters ("Merge the two mark styles, or keep both?"); "quote", the agent's words that leave it to the user.

Reply with only this JSON object, no code fence, with "asks": [] if there are none:
{{"asks": [{{"page": "<page path>", "title": "<line>", "quote": "<words>"}}]}}
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
            return page_facts(page_state(page_dir, page.events))
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
    """Open each of `answer`'s asks as a to-do on the user, on the page it names among
    those `session_id` holds, unless an open to-do there has its title, and queue a
    line for each for the agent's next step; what it wrote."""
    from .event_contracts import append_admitted
    from .leases import page_locked
    from .service import PageTransaction, owned_pages
    from .todos import TodoReading

    wrote: list[dict] = []
    told: list[str] = []
    for page_dir in owned_pages(session_id):
        path = str(page_dir)
        asks = [item for item in answer["asks"] if item["page"] == path]
        if not asks:
            continue
        # As a command's write takes them (`leases.contract_writer`).
        with page_locked(page_dir), PageTransaction(page_dir) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                continue
            identity = {"agent": claim["agent"], "session": claim["id"]}
            listed = {
                todo["title"].casefold()
                for todo in TodoReading(page.events).todos
                if todo["owner"] == "user" and todo["state"] == "open"
            }
            for item in asks:
                title = _title(item["title"])
                if title.casefold() in listed:
                    continue
                listed.add(title.casefold())
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
                    f"`leaf task end {path} {record['id']} dropped` if it "
                    "isn't the user's to decide."
                )
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
