"""Leaf's clerk: a fork of the agent's conversation, made as each of its turns ends,
that finds what the agent left to the user without putting it On me, and puts it
there on the agent's behalf. It is experimental, and runs only in Claude Code.

An agent does the user's work and Leaf's bookkeeping in one context, and late in long
sessions the bookkeeping slips: on 2026-10-25 five sessions holding live pages left
the decisions waiting on the user only in their chat replies, so On me read empty, and
rewording the skill changed 0 of 6 replays of such a session. A fork of the whole
conversation reads what the agent said, so Leaf asks one, and writes what it finds
rather than prompting the agent, which would cost a turn and invite rework. The user
chose this shape on 2026-10-29 over a digest of the final reply, an advisor that
prompts the agent, and a clerk agent that also rewrites the page.

Three principles, the user's (2026-10-30), bound what the fork may do:

- It adds attention, not an actor. The fork is the agent looking again at its own
  bookkeeping, and gives the agent reminders; it does none of the user's work.
- The user never meets it. What it writes is the agent's own record, authored by the
  agent's session with nothing marking the fork, and it adds no mark, message, status
  or control of its own. A first version marked its to-dos "added by Leaf"; the user
  rejected that as a second entity on the page.
- The agent stays sovereign. The agent hears each record at its next step, with its
  id and words, as its own, and keeps, withdraws or replaces it as it would one it
  wrote. Leaf opens no thread whose title a thread the agent opened on the page to
  ask something already has, and shows the fork the questions already answered or
  withdrawn so it doesn't word one anew. It writes nothing once a turn has opened
  since the fork read the conversation (`basis`), since that turn's agent, or the
  user who opened it, has the newer reading.

It asks about one thing: decisions, answers, permissions or steps the agent left to
the user that no On me item holds. A first version also wrote the status line and
named missed page steps; the user narrowed it on 2026-10-29 to start from this one
class, in Leaf's own words rather than any one user's markers, and what the page state
alone settles, such as input not yet delivered, is code's to report rather than a
model's.

This module is the fork's one home, shared by every harness: what it is asked
(`fork_prompt`, with each page's On me as `page_facts` reads it), the answer it must
give (`ANSWER`), and what Leaf does with that answer (`apply_answer`). A harness only
makes the fork and carries the two halves (`cmd_fork`): Claude Code's hooks module
calls `$.model.fork` from `turn.complete` (`hooks/claude-code.ts`). Codex would fork
with App Server's `thread/fork` (ephemeral) and Pi's extension by resending its
session, each handing the answer back the same way; neither does yet.

The fork can't author the page, so it writes what the agent would write without a
widget, choosing per ask as the agent does (`conversation-loop.md`, "The On lists").
A question goes in a thread of its own, opened by the agent's message with an
obligation (`threads.md`): the message holds the whole question, On me lists it until
the user replies or settles it, and their reply reaches the agent as any reply does.
A step the user takes and confirms with Done, such as running a command, goes On me
as the agent's to-do on the user, titled as the action. Each stands on the passage
the ask concerns where the fork names words the page shows once, a to-do on the
element holding them, and otherwise on the page as a whole, which is also where words
the page doesn't show once leave it, since the fork has no next attempt.

A first version wrote every ask as a to-do on the user on the page, titled from the
chat line, and `m` left a long title cut to half a line in the panel (2026-10-31).
The user asked for the routes a question asked well takes, a widget that asks or a
thread, then declined to mandate one placement or form, and chose to let the fork
pick a to-do for a step once `m` opened On me on a to-do, where its title reads whole
(queue-walk.js). A step asked as a thread question had a cost: a clarifying reply
such as "where do I run it?" answers it, and the agent has to ask again.

Leaf queues one line for each record (`QUEUED`) under the same locks as its page's
write, so a later page's failure loses no earlier page's lines. The next prompt or
tool-boundary hook adds the lines to the agent's context
(`hook_transport.carry_turn`), so the agent knows its records and their words,
neither repeats nor contradicts them, and spends no turn on them. A line leaves the
queue once a hook has printed it (`heard`), so a prompt that Escape drops loses its
lines: the questions stay On me and `leaf page state` lists them, but the agent isn't
told. Confirming the lines from the transcript, as `delivery.confirm_entered` does
for input, would close that gap.

Measured on 2026-10-29 by replaying 21 recorded turn ends three times each on Opus
5.5 (`~/.tmp/leaf.agent-channels/replay/`, `fork3.py` and `score3.py`): the fork
found 59 of the 63 labelled asks missing from On me; 62 of its 64 findings were
labelled asks and 2 borderline, none false; 2 of 39 runs at clean turn ends named
anything. Warm, a fork cost $0.08 (median). Claude Code's fork reuses the session's
cached prefix only while its
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

# The length of a thread's or to-do's title (`comment` and `todo` in the kernel
# registry), which the fork is asked to keep a title under. A model can't count characters, so the answer takes a
# longer title and Leaf shortens it to fit (`_title`) rather than refusing the answer
# and every ask it found.
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
                    "kind": {"enum": ["question", "step"]},
                    "title": {"type": "string", "minLength": 1, "pattern": r"\S"},
                    # A question's message; a step has none, its title being all
                    # the user reads of its to-do.
                    "text": {"type": "string"},
                    # The page's words the ask concerns, or "" for the page as a whole.
                    "passage": {"type": "string"},
                    # The agent's words, which ground the ask in the conversation;
                    # Leaf writes only the title, text and passage.
                    "quote": {"type": "string"},
                },
                "required": ["page", "kind", "title", "text", "passage", "quote"],
                "additionalProperties": False,
                "if": {"properties": {"kind": {"const": "question"}}},
                "then": {"properties": {"text": {"minLength": 1, "pattern": r"\S"}}},
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
        "question or step it put On me (`clerk`).",
        object_schema({"lines": {"type": "array", "items": STRING}}),
    ),
    since=36,
)

# The words that open the fork's question, which the replay and the transcript carry.
OPENING = "<leaf-fork-check>"


def page_facts(state: dict) -> dict:
    """What the fork is shown of one page, from `state` as `leaf page state` prints
    it: its On me, and the questions and to-dos on the user that are answered, ended
    or withdrawn, which the fork must not ask again."""
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
        f"{words(record)} ("
        + ("dropped" if record["status"] == "withdrawn" else "answered")
        + ")"
        for record in state["obligations"]
        if record["source"]["kind"] in {"todo", "message"}
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
            "Answered or withdrawn on the page; don't ask these again:\n"
            + lines(facts["settled"])
        )
    return "\n".join(parts)


def fork_prompt(pages: list[dict]) -> str:
    """The one message a fork answers: what it is for, each page's facts
    (`page_facts`), the question and the answer's form (`ANSWER`)."""
    blocks = "\n\n".join(_block(facts) for facts in pages)
    return f"""{OPENING}
This message comes from Leaf, not the user. You are a fork of this session, made as the agent's turn ended, to keep the user's On me list complete. The main session carries on separately and never reads this exchange: Leaf puts each ask you write On me as the agent's own, a question in a new thread and a step as a to-do, and tells the agent at its next step, which takes the user's answer or withdraws the ask. Don't call tools and don't continue the work; answer from the conversation above and the page state below.

{blocks}

On me is where the user finds everything waiting on them. Name each decision, answer, permission or step the agent left to the user, in its replies or anywhere in the conversation, that no On me item above holds and the user hasn't answered since. Leave out what the agent will settle itself. Give each:
- "page": the page's path.
- "kind": "step" for an action the user takes and then confirms with Done, such as running a command or trying a build; "question" for anything they answer, decide or permit.
- "title": for a question, a few words naming its thread's subject ("Merging the two mark styles"); for a step, the action itself, whole, as the only words the user reads of it ("Run /reload-plugins in this Claude session"). Keep it under {TITLE_LIMIT} characters.
- "text": for a question, the message that asks it, as the agent would write it. The user reads it on the page, perhaps days later and without the chat, so say what is waiting, why it arises and what each answer leads to, naming things as the page does, and end with the question. It shows in a narrow card, so keep it to three or four short sentences of Markdown; link a pull request or commit by its URL where the conversation gives one. For a step, "".
- "passage": where the ask concerns one passage of the page, a few of its words, exactly as the page shows them and found nowhere else on it, which the ask then stands on; else "", and it stands on the page as a whole.
- "quote": the agent's words that leave it to the user.

Reply with only this JSON object, no code fence, with "asks": [] if there are none:
{{"asks": [{{"page": "<page path>", "kind": "question", "title": "<subject>", "text": "<message>", "passage": "<page words or empty>", "quote": "<words>"}}]}}
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
    `asked`, its `basis` (`apply_answer`)."""
    return apply_answer(session_id, read_answer(text), asked)


def _facts(page_dir: Path) -> dict | None:
    from .agent_state import page_state
    from .service import PageTransaction

    try:
        with PageTransaction(page_dir) as page:
            return page_facts(page_state(page_dir, page.events))
    except FileNotFoundError:
        return None


def _title(words: str) -> str:
    """`words` as a thread's title: on one line, and cut at a word to fit
    `TITLE_LIMIT`, ending in an ellipsis where it was cut."""
    title = " ".join(words.split())
    if len(title) <= TITLE_LIMIT:
        return title
    return title[: TITLE_LIMIT - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def apply_answer(session_id: str, answer: dict, asked: dict | None) -> dict:
    """Put each of `answer`'s asks On me as the agent's own, on the page it names among
    those `session_id` holds: a question in a thread of its own, opened by the agent's
    message with an obligation, and a step as a to-do on the user; skip one whose
    title an ask the agent made there already has, and queue a line for each for the
    agent's next step, while the session's turn is still the one `asked` names; what
    it wrote, and why it stopped if it did."""
    from .findings import Rejected
    from .leases import page_locked
    from .service import PageTransaction, owned_pages
    from .todos import TodoReading
    from .validation.admission import checked_text

    wrote: list[dict] = []
    told: list[str] = []
    for page_dir in owned_pages(session_id):
        path = str(page_dir)
        asks = [item for item in answer["asks"] if item["page"] == path]
        if not asks:
            continue
        # The page as a command's write takes it (`leases.contract_writer`), then the
        # session, in the lifecycle's lock order (`PageTransaction.publishing_claim`),
        # so no turn opens between reading the turn and queueing what it wrote.
        try:
            with (
                page_locked(page_dir),
                PageTransaction(page_dir) as page,
                flocked(session_lock_path(session_id)),
            ):
                if basis(session_id) != asked:
                    return {
                        "wrote": wrote,
                        "told": told,
                        "dropped": "another turn opened since the fork was made",
                    }
                claim = page.active_claim
                if claim is None or claim["id"] != session_id:
                    continue
                identity = {"agent": claim["agent"], "session": claim["id"]}
                # The asks the agent made there, by title: the threads it opened to
                # ask something and its to-dos on the user, open or ended.
                asked_in = {
                    event["title"].casefold()
                    for event in page.events
                    if event["kind"] == "comment"
                    and event["author"] == "agent"
                    and event.get("obligation")
                    and "title" in event
                } | {
                    todo["title"].casefold()
                    for todo in TodoReading(page.events).todos
                    if todo["owner"] == "user"
                }
                # Every message is checked before the first is written, so a refused
                # one leaves the page as the fork found it.
                messages = [
                    (
                        item["kind"],
                        _title(item["title"]),
                        checked_text(page_dir, item["text"])
                        if item["kind"] == "question"
                        else "",
                        item["passage"].strip(),
                    )
                    for item in asks
                ]
                lines = []
                for kind, title, text, passage in messages:
                    if title.casefold() in asked_in:
                        continue
                    asked_in.add(title.casefold())

                    ask = (page_dir, page, kind, title, text, identity)
                    try:
                        record = _put(*ask, passage)
                    except Rejected:
                        if not passage:
                            raise
                        record = _put(*ask, "")
                    wrote.append(record)
                    lines.append(_told(path, kind, title, text, passage, record))
                if lines:
                    queue_path = session_file(session_id, QUEUED.kind)
                    held = QUEUED.read(queue_path) or {"lines": []}
                    QUEUED.write(queue_path, {"lines": [*held["lines"], *lines]})
                told.extend(lines)
        except FileNotFoundError:
            continue
    return {"wrote": wrote, "told": told}


def _put(page_dir, page, kind, title, text, identity, passage) -> dict:
    """The record putting one ask On me as the agent's own in `page`, an open
    transaction: a question's thread, or a step's to-do on the user, on `passage` where
    it names one; refused, as `thread create --quote` is, where the page doesn't show
    `passage` once."""
    from .thread import current_anchor, open_thread
    from .todos import open_todo

    if kind == "question":
        return open_thread(
            page_dir,
            page,
            text,
            passage,
            title=title,
            obligation=True,
            identity=identity,
        )
    _, anchor = current_anchor(page_dir, page.events, passage, "", "", transaction=page)
    section = (anchor or {}).get("section")
    subject = {"kind": "element", "id": section} if section else {"kind": "page"}
    return open_todo(page, subject, title, "user", identity)


def _told(path: str, kind: str, title: str, text: str, passage: str, record: dict):
    """The line telling the agent what Leaf put On me as its own, and where."""
    placed = "anchor" in record or record.get("subject", {}).get("kind") == "element"
    where = f'the words "{passage}" in {path}' if placed else f"{path} as a whole"
    if kind == "step":
        withdraw = f"leaf task end {path} {record['id']} dropped"
        return (
            f'From your last reply, Leaf put the step "{title}" On me as your to-do '
            f"{record['id']} on the user, on {where}. It is yours like any to-do you "
            f"write: if it isn't the user's to do, end it with `{withdraw}`, and ask "
            "it another way if you'd rather."
        )
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    withdraw = f"leaf task end {path} message:{record['id']} dropped"
    return (
        f'From your last reply, Leaf asked the user "{title}" On me, in a new thread '
        f"on {where}, opened by your message {record['id']}:\n{quoted}\nIt is yours "
        "like any message you write: the user's reply reaches you as any reply does, "
        f"and if it isn't theirs to decide, withdraw it with `{withdraw}`, and ask it "
        "another way if you'd rather."
    )


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
