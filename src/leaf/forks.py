"""Forked replies: a fork of a Claude Code session's conversation that answers the
user's waiting messages in a thread at once, or hands them to the session. It runs
only in Claude Code, from Leaf's hooks module (`hooks/claude-code.ts`).

On real pages the session's answer to a thread message took a median 48 s when it
was idle and 100 s when it was busy, long enough that the user leaves the thread
(`notes/leaf-run-sessions.md`, "Waits on real pages"). `$.model.fork` resends the
session's last request with one more message, at any moment, mid-command too. On
recorded thread messages a fork answered in a median 12 s and handed over in 6 s,
most of it thinking at the session's effort (`notes/fork-replies.md` has the
measurements). The user chose on 2026-10-31 a fork that answers or hands over, over
keeping every reply with the session and over a fork that also says the work will
follow, which would commit the session to work it hasn't seen.

A thread's waiting messages are the user's messages since the agent's last answer in
it, the newest of which owes the thread's answer. Each thread with waiting messages
is in one of three states, and `held` is the one function that computes which, from
the page's log, the session's hand-overs (`HANDED`) and the forks' lane; nothing
stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| held | Leaf keeps the thread's waiting messages from the session while a fork decides | a user message in a thread none of whose waiting messages the session has received or been handed, while the session's lane is live and has been since the first of them arrived |
| answered | the fork's reply is posted as the agent's, and the thread owes nothing | the fork's `reply` |
| with the session | delivered as any input is | a hand-over: the fork's `hand_over`, a failed fork, or the lane's once `BOUND_S` has passed since the newest waiting message (`look`); or the lane going down |

Another message while the thread is held keeps it held, with a fork for the new
set, and drops the earlier fork's answer (`take`); a follow-up after an answer makes
the thread held again, its fork seeing the earlier exchange in the log; a thread with
the session stays there until the session answers it. Held input is not
`delivery.deliverable`, which the hooks, the watch and its nudges read, and admission
doesn't nudge for it (`event_endpoint`), since the hold has to start before the watch
would wake the session.

Each way out of the hold but the lane going down is a write the session's waiters
already read, made under the page's lock: the reply goes in the log, and a hand-over
in `HANDED`, which the watch's reading stamps (`served_state.reading`), and it nudges
a session no watch follows, as admission would have. So the bound is the lane's to
keep, for every page the session holds, and the state needs no clock.

The lane is the session's pages follower (`hooks.cmd_pages`) while it holds the
lease at `lane_path`: the follower prints each held thread with the session's pages
(`look`), and the module forks each one (`ask`), then hands the fork's answer back
(`take`). Python writes the prompt (`reply_prompt`) and reads the answer (`ANSWER`);
the module only carries them, and names the tool calls the session is running, which
the fork can't see: its last request predates them. A lane holds only what arrived
while it ran, so a thread the lane going down gave to the session stays there when
the next lane comes up, and a fork of the old lane's writes nothing. A follower that
gives up the lane with a thread held, as one exiting or finding a newer follower
holding it does, then nudges what its holds leave, as a watch does when it gives up
its lease (`session.nudge_pending`); one killed outright nudges nothing, so after
Escape, with no watch, its messages wait for the page's next change.

A reply goes in as the agent's own (`thread.post_reply` with the claim's identity),
fenced to the hold: it writes nothing once the thread is no longer held as the fork
was asked it, checked under the lock the append takes. The main session hears of it
at its next prompt or tool boundary: the settled message arrives in its delivery
with the reply in the thread's digest, and the clerk's queue (`clerk.queue`) adds a
line saying a fork wrote it, for the session to correct where what it knows shows the
reply wrong: replayed on real messages, about one fork reply in eight or more was.
Every outcome goes to the page's diagnostics
(`interaction_log`, type `fork_reply`), with the fork's tokens and time, which is
what a later replay or audit scores.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from .leases import lease_speaks_here, take_wait_lease
from .registry.kernel import kinds_declaring
from .service import PageTransaction, unacknowledged
from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    page_key,
    session_file,
    session_lock_path,
)

# How long Leaf holds a thread's waiting messages from the session, counted from the
# newest one's admission, before the lane hands them to it whatever the fork does
# (`look`). Forks that answered rightly on recorded thread messages took 5–24 s, and
# the follower takes up to a quarter second to see the message.
BOUND_S = 30.0

ANSWER = {
    "oneOf": [
        {
            "type": "object",
            "properties": {"reply": {"type": "string", "pattern": r"\S"}},
            "required": ["reply"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"hand_over": {"type": "string"}},
            "required": ["hand_over"],
            "additionalProperties": False,
        },
    ]
}

HANDED = Record(
    "forks",
    described(
        "The thread messages a fork of a Claude Code session's conversation handed "
        "to the session, in the state home's `sessions/<digest>.forks` "
        "(`state.session_file`): for each page, by `state.page_key`, the ids of the "
        "messages it handed over that the session hasn't yet received (`forks`).",
        object_schema(
            {
                "handed": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": STRING},
                }
            }
        ),
    ),
    since=36,
)

# The words that open the fork's question, which the transcript carries.
OPENING = "<leaf-fork-reply>"


class Held(NamedTuple):
    """A thread in the held state: its id, its waiting messages in log order, the
    last of which owes the answer, and when the lane hands it to the session (POSIX
    seconds)."""

    thread: str
    inputs: tuple[str, ...]
    until: float

    def basis(self, page_dir: Path) -> dict:
        """The thread as the module carries it between `ask` and `take`."""
        return {
            "page": str(page_dir),
            "thread": self.thread,
            "inputs": list(self.inputs),
        }


def lane_path(session_id: str) -> Path:
    return session_file(session_id, "fork-lane")


def take_lane(session_id: str):
    """Hold the session's lane, from any earlier holder, until this process exits."""
    return take_wait_lease(lane_path(session_id), supersede=True)


def lane_since(session_id: str) -> float | None:
    """When the session's live lane was taken, to the millisecond event times keep
    (POSIX seconds), or None with no lane live. Each take publishes a fresh lease
    file by renaming it into place (`leases.supersede_lease`), and the rename sets
    its status-change time, which nothing after it moves: so a message admitted
    before the lane took the name was admitted before this time."""
    path = lane_path(session_id)
    if not lease_speaks_here(path):
        return None
    try:
        return int(path.stat().st_ctime * 1000) / 1000
    except FileNotFoundError:
        return None


def _admitted(event: dict) -> float:
    return datetime.fromisoformat(event["ts"]).timestamp()


def handed_inputs(session_id: str, page_dir: Path) -> set[str]:
    held = HANDED.read(session_file(session_id, HANDED.kind))
    return set((held or {"handed": {}})["handed"].get(page_key(page_dir), []))


def held(page: PageTransaction) -> list[Held]:
    """The page's threads in the held state (the module header's table), by when
    their holds end.

    It reads the log, never the page's fold, which costs about 100 ms, since
    admission and every hook ask it: a user's message after the agent's last answer
    in its thread owes the thread's answer, and `ask` hands over one the fold says
    owes none."""
    claim = page.active_claim
    if claim is None:
        return []
    since = lane_since(claim["id"])
    if since is None:
        return []
    events = page.events
    pending = {event["id"] for event in unacknowledged(events, page.cursor)}
    messages = kinds_declaring("message")
    if not any(
        event["kind"] in messages and event["author"] == "user"
        for event in events
        if event["id"] in pending
    ):
        return []
    from .events import taken_back
    from .thread_context import thread_names

    picked = {
        input_id
        for event in events
        if event["kind"] == "pickup"
        for input_id in event["events"]
    }
    handed = handed_inputs(claim["id"], page.page_dir)
    names = thread_names(events)
    withdrawn = taken_back(events)
    waiting: dict[str, list[dict]] = {}
    for event in events:
        if event["kind"] not in messages or event["id"] in withdrawn:
            continue
        thread = names.get(event["id"])
        if thread is None:
            continue
        if event["author"] == "user":
            waiting.setdefault(thread, []).append(event)
        elif not event.get("ephemeral"):
            # The agent's answer; its progress lines answer nothing.
            waiting.pop(thread, None)
    found = [
        Held(
            thread,
            tuple(event["id"] for event in said),
            _admitted(said[-1]) + BOUND_S,
        )
        for thread, said in waiting.items()
        # A lane holds only what arrived while it ran, so a hold the lane going down
        # gave to the session never comes back with the next lane; a message in the
        # take's own millisecond may have come first, so it stays with the session.
        if _admitted(said[0]) > since
        and all(
            event["id"] in pending
            and event["id"] not in picked
            and event["id"] not in handed
            for event in said
        )
    ]
    return sorted(found, key=lambda thread: thread.until)


def held_inputs(page: PageTransaction) -> set:
    """Every waiting message of the page's held threads (`held`), which
    `delivery.deliverable` keeps from the session."""
    return {input_id for thread in held(page) for input_id in thread.inputs}


def _held_for(page: PageTransaction, session_id: str) -> list[Held]:
    """The page's held threads while it is `session_id`'s, since `held` reads the
    claimant's and a session the page has left must write nothing on it."""
    claim = page.active_claim
    return held(page) if claim is not None and claim["id"] == session_id else []


def _still_held(page: PageTransaction, session_id: str, basis: dict) -> bool:
    return any(
        thread.thread == basis["thread"] and list(thread.inputs) == basis["inputs"]
        for thread in _held_for(page, session_id)
    )


def look(session_id: str, page_dir: Path, *, now: float | None = None) -> list[Held]:
    """The page's held threads for the lane's holder to fork, after handing to the
    session each one whose `BOUND_S` has passed, whatever its fork is doing. `now`
    defaults to the clock."""
    now = time.time() if now is None else now
    with PageTransaction(page_dir) as page:
        threads = _held_for(page, session_id)
        due = [thread for thread in threads if thread.until <= now]
        for thread in due:
            _hand_over_held(page, session_id, thread.inputs)
    for thread in due:
        _record(
            session_id,
            thread.basis(page_dir),
            {"outcome": "hand_over", "why": f"no answer within {BOUND_S:g} s"},
        )
    return [thread for thread in threads if thread.until > now]


def cmd_reply(session_id: str, payload: dict) -> dict | None:
    """One step of a forked reply, as `leaf hook --fork` hands it over with the
    held thread in `payload["thread"]`: without `answer` or `failed`, the question
    (`ask`); with one, what Leaf did with it (`take`)."""
    basis = payload["thread"]
    if "answer" in payload or "failed" in payload:
        return take(
            session_id,
            basis,
            answer=payload.get("answer"),
            failed=payload.get("failed"),
            usage=payload.get("usage"),
            elapsed_ms=payload.get("elapsed_ms"),
            running=payload.get("running") or [],
        )
    return ask(session_id, basis, payload.get("running") or [])


def ask(session_id: str, basis: dict, running: list[dict]) -> dict | None:
    """What to fork the conversation with for the thread `basis` names, as
    `{"prompt", "thread"}`, or None once the thread is no longer held as `basis`
    has it, or the page no longer the session's."""
    from .delivery import batch_data, current_responses

    page_dir = Path(basis["page"])
    try:
        with PageTransaction(page_dir) as page:
            if not _still_held(page, session_id, basis):
                return None
            responses = current_responses(page_dir, page.events)
            owed = responses.get(basis["inputs"][-1])
            by_id = {event["id"]: event for event in page.events}
            if owed is not None and owed["kind"] == "reply":
                data = batch_data(
                    page_dir,
                    page,
                    [by_id[i] for i in basis["inputs"]],
                    responses=responses,
                )
    except FileNotFoundError:
        return None
    if owed is None or owed["kind"] != "reply":
        # Only the session can settle what owes no reply in the thread.
        _hand_over(session_id, basis, "the message owes no reply")
        return None
    return {"prompt": reply_prompt(data, running), "thread": basis}


def _running_line(running: list[dict]) -> str:
    if not running:
        return (
            "The conversation above ends where the session last sent it to the model."
        )
    calls = "; ".join(
        call["tool"]
        + "".join(
            f" {name}: {json.dumps(value, ensure_ascii=False)}"
            for name, value in call.get("input", {}).items()
        )
        for call in running
    )
    return (
        "The session is running a tool now, which the conversation above doesn't "
        f"show, and whose result you can't see: {calls}."
    )


def reply_prompt(data: dict, running: list[dict]) -> str:
    """The one message a fork answers: what it is for, the thread as Leaf would
    deliver it (`delivery.batch_data`), what the session is running, and the
    answer's form (`ANSWER`)."""
    thread = {
        "page": data["page"],
        "threads": data["threads"],
        "events": [
            {key: value for key, value in event.items() if key != "answer"}
            for event in data["events"]
        ],
    }
    return f"""{OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to answer them at once while the main session carries on. Every tool call is denied here, so don't call tools. Leaf posts your reply in the thread as the agent's own and tells the main session at its next step; the main session never sees this exchange otherwise. {_running_line(running)}

The thread, as Leaf delivers it; "events" are the user's messages your reply answers, oldest first:
{json.dumps(thread, ensure_ascii=False, indent=1)}

Answer the user yourself only when the conversation above already holds the answer, as when they ask what the session did, found, decided or plans, why, or what something means. Hand the thread to the main session when you would have to work the answer out, from code or details the conversation shows or from how you expect something to behave, for a case the session never looked at. Hand it over too when an answer needs anything you can't see from here: a look at a file or the page, a command's output, or the result of work still running; when the user asks for work or a change, however small; when the user answers or decides something the session asked them, since the main session records it and acts on it; and when the answer would settle something the main session is still deciding. Don't promise work, since only the main session can do it.

Write a reply as the agent would answer in the thread: Markdown for a narrow column, short paragraphs, plain words, answering the message directly.

Reply with only one JSON object, no code fence: {{"reply": "<the reply, in Markdown>"}} to answer, or {{"hand_over": "<why, in one line>"}} to hand the thread to the main session.
</leaf-fork-reply>"""


def take(
    session_id: str,
    basis: dict,
    *,
    answer: str | None,
    failed: str | None,
    usage: dict | None = None,
    elapsed_ms: float | None = None,
    running: list[dict] | None = None,
) -> dict:
    """Post the fork's reply, or hand the thread to the session where it handed
    over, failed (`failed`, its reason) or gave an answer `ANSWER` refuses; what came
    of it, recorded in the page's diagnostics."""
    from .clerk import read_answer
    from .refusals import Refused

    decided: dict
    if answer is None:
        decided = {"hand_over": f"the fork failed: {failed}"}
    else:
        try:
            decided = read_answer(answer, ANSWER)
        except Refused as error:
            decided = {"hand_over": str(error)}
    outcome: dict
    if "reply" in decided:
        outcome = _post(session_id, basis, decided["reply"])
    else:
        outcome = _hand_over(session_id, basis, decided["hand_over"])
    _record(
        session_id,
        basis,
        {
            **outcome,
            "running": running or [],
            **({"usage": usage} if usage else {}),
            **({"elapsedMs": elapsed_ms} if elapsed_ms is not None else {}),
        },
    )
    return outcome


def _record(session_id: str, basis: dict, outcome: dict) -> None:
    """Note what came of a held thread in its page's diagnostics."""
    from .interaction_log import append_interactions

    record = {
        "source": "cli",
        "type": "fork_reply",
        "session": session_id,
        "thread": basis["thread"],
        "inputs": basis["inputs"],
        **outcome,
    }
    try:
        append_interactions(Path(basis["page"]), [record])
    except OSError:
        pass


def _post(session_id: str, basis: dict, text: str) -> dict:
    """The fork's reply, posted as the agent's while the thread is still held as
    `basis` has it, and the clerk's line telling the session; or why nothing was."""
    from .clerk import queue
    from .delivery import ReceiptRefused
    from .findings import Rejected
    from .refusals import Refused
    from .thread import Receipt, post_reply

    page_dir = Path(basis["page"])
    try:
        record = post_reply(
            page_dir,
            {"responds": basis["inputs"][-1]},
            text,
            settlement=Receipt(fence=lambda page: _still_held(page, session_id, basis)),
            claimed_session=session_id,
        )
    except (FileNotFoundError, ReceiptRefused):
        return {"outcome": "dropped", "text": text}
    except (Rejected, Refused) as error:
        # The reply's own checks refused it, so the session answers instead.
        handed = _hand_over(session_id, basis, f"the reply was refused: {error}")
        return {**handed, "text": text}
    if record is None:
        return {"outcome": "dropped", "text": text}
    queue(
        session_id,
        [
            f"Leaf answered the user's message {basis['inputs'][-1]} in thread "
            f"{basis['thread']} on {page_dir} from a fork of this conversation, and "
            f"posted the reply as yours ({record['id']}). Read it in the thread: "
            "where what you know shows it wrong, correct it there; otherwise the "
            "thread owes nothing."
        ],
    )
    return {"outcome": "reply", "text": text, "reply": record["id"]}


def _hand_over(session_id: str, basis: dict, why: str) -> dict:
    """Hand the thread `basis` names to the session, while it is still held as
    `basis` has it (`_hand_over_held`)."""
    try:
        with PageTransaction(Path(basis["page"])) as page:
            if not _still_held(page, session_id, basis):
                return {"outcome": "dropped", "why": why}
            _hand_over_held(page, session_id, basis["inputs"])
    except FileNotFoundError:
        return {"outcome": "dropped", "why": why}
    return {"outcome": "hand_over", "why": why}


def _hand_over_held(page: PageTransaction, session_id: str, inputs) -> None:
    """Record in `HANDED` that the held messages `inputs` go to the session, keeping
    only the ids it hasn't yet received, and nudge a session no watch follows, as
    admission would have."""
    from .presence import nudge_unwatched

    pending = {event["id"] for event in unacknowledged(page.events, page.cursor)}
    path = session_file(session_id, HANDED.kind)
    key = page_key(page.page_dir)
    with flocked(session_lock_path(session_id), deadline=page.deadline):
        record = HANDED.read(path) or {"handed": {}}
        kept = [i for i in record["handed"].get(key, []) if i in pending]
        record["handed"][key] = list(dict.fromkeys([*kept, *inputs]))
        HANDED.write(path, record)
    nudge_unwatched(page)
