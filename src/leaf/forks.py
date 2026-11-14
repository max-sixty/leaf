"""Forked working lines: a fork of a Claude Code session's conversation that posts
the agent's working line on the user's waiting messages in a thread at once, then
hands them to the session. It runs only in Claude Code, from Leaf's hooks module
(`hooks/claude-code.ts`).

On real pages the session's answer to a thread message took a median 48 s when it
was idle and 100 s when it was busy, and the thread showed nothing from the agent
for a median 35 s after a message, until the session's first model call ended
(`notes/fork-replies.md`, "Forks on real pages"). `$.model.fork` resends the
session's last request with one more message, at any moment, mid-command too, and a
fork decided in a median 3 s. The user chose on 2026-10-31 a fork that answers or
hands over. On 2026-11-05 they had a fork that hands over post the agent's working
line, and then had the fork post only that line, always handing over: a fork can't
call tools (`$.model.fork` denies every one), and answering is left to a fork that
can act.

The line is the agent's progress message in the thread (`thread.post_reply`), which
the thread shows until the session's own words replace it. From the moment the hold
starts, and while the line stands, the thread's waiting messages read On it
(`forked`, which `served_state.work` serves as their workflows' `at_work`, so every
surface showing whether the agent is at work agrees), as the user chose
on 2026-11-05. That word is all the fork changes: as a receipt's progress the line
takes nothing in hand (`thread.Receipt`), so every reader that ages, nudges or holds
a turn reads the message's delivery. A start would read as the session's turn,
renewing it after an interrupt and holding the message at Working before the
session had it, which hid it from the nudge and the overdue count.

The fork thinks at the session's own effort, and its prompt asks it to reply
straight away without thinking it over, since every second it takes keeps the
thread's messages from the session. A fork at another effort costs a rewrite of the
conversation to the cache on backends without per-message effort, as the clerk's
header says. From 2026-11-09 to 2026-11-14 it asked for `low`. On the eval's seven
cases on 2026-11-14, a fork at xhigh asked to reply straight away passed 7, against
the low fork's 6, writing 1.49 times its output (95% interval 0.91–2.44) in 1.09
times its time (0.94–1.25). On 2026-11-09 low wrote
lines as good as xhigh's. On 40 recorded thread messages, each replayed from its
session's transcript (`notes/fork-replies.md`, "How well the fork judges"), a judge
blind to the effort passed 35 lines at each effort and preferred low's on 19, xhigh's
on 16 and neither on 5; `leaf-dev eval 'fork-reply*'` passed 35 of 35 at each over
five repeats. Neither effort thought on the recorded messages, so their output and
time matched there (low wrote 1.03 times the tokens, 95% interval 0.97–1.10). On the
eval's short conversations xhigh thought over 5 of its 35 lines, taking up to 3.5 s
where a line took a median 1 s, and low over none, for 0.85 times xhigh's time
(0.75–0.95). So low removed the occasional line xhigh spent seconds thinking over.

A thread's waiting messages are the user's messages since the agent's last answer in
it, the newest of which owes the thread's answer. Each thread with waiting messages
is in one of two states, and `held` is the one function that computes which, from
the page's log, the session's hand-overs (`HANDED`) and the forks' lane; nothing
stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| held | Leaf keeps the thread's waiting messages from the session while a fork writes its line | a user message in a thread none of whose waiting messages the session has received or been handed, while the session's lane is live and has been since the first of them arrived |
| with the session | delivered as any input is | a hand-over: the fork's line posted, a failed fork, or the lane's once `BOUND_S` has passed since the newest waiting message (`look`); or the lane going down |

Another message while the thread is held keeps it held, with a fork for the new
set, and drops the earlier fork's line (`take`); a thread with the session stays
there until the session answers it, and a message after that answer makes the
thread held again. Held input is not `delivery.deliverable`, which the hooks, the
watch and its nudges read, and admission doesn't nudge for it (`event_endpoint`),
since the hold has to start before the watch would wake the session.

Each way out of the hold but the lane going down is a write the session's waiters
already read, made under the page's lock: a hand-over in `HANDED`, which the
watch's reading stamps (`served_state.reading`), and it nudges a session no watch
follows, as admission would have. So the bound is the lane's to keep, for every page
the session holds, and the state needs no clock. The lane going down writes nothing,
so the page's presence reading names the lane (`presence.live_facts`), and a tab
showing On it for a held message re-reads within the reading's cache interval.

The lane is the session's pages follower (`hooks.cmd_pages`) while it holds the
lease at `lane_path`: the follower prints each held thread with the session's pages
(`look`), and the module forks each one (`ask`), then hands the fork's line back
(`take`). Python writes the prompt (`reply_prompt`); the module only carries it and
the line, and names the tool calls the session is running, which the fork can't see:
its last request predates them. A lane holds only what arrived while it ran, so a
thread the lane going down gave to the session stays there when the next lane comes
up, and a fork of the old lane's writes nothing. A follower that gives up the lane
with a thread held, as one exiting or finding a newer follower holding it does, then
nudges what its holds leave, as a watch does when it gives up its lease
(`session.nudge_pending`); one killed outright nudges nothing, so after Escape, with
no watch, its messages wait for the page's next change.

The line goes in as the agent's own (`thread.post_reply` with the claim's identity),
fenced to the hold: it writes nothing once the thread is no longer held as the fork
was asked it, checked under the lock the append takes. The page's diagnostics
(`interaction_log`) note whether admission held each thread message to a Claude Code
session, and where not, whether its lane was up (`fork_hold`); each question as Leaf
gives it to the module (`fork_asked`), so a fork that never answers shows; and every
outcome (`fork_reply`), with the fork's tokens and time, why Leaf refused its line
where it did, and the request
it resent (`request` in `hooks/claude-code.ts`, which says where a replay cuts the
conversation: to `sent` while `running` lists a call, else to `row`; its
`effort` is the fork's), as the clerk's `turn_end_check` notes have it, which is
what a later replay or audit scores. `leaf-dev timeline` reads them beside the
session's transcript.
`leaf-dev eval 'fork-reply*' --harness claude-code --base` scores a change to the
prompt on a short constructed conversation for each kind of message
(`dev/leaf_dev/fork_eval.py`).
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from .leases import lease_speaks_here, release_lease, take_wait_lease
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
# (`look`). Forks on real pages decided in a median 3 s.
BOUND_S = 30.0

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
    since=37,
)

LANE_START = Record(
    "fork-lane-start",
    described(
        "The admission cutoff of a session's fork lane. Its live lease alone "
        "proves that lane is running (`forks.take_lane`).",
        object_schema({"since": {"type": "number"}}),
    ),
    since=37,
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


def lane_lock_path(session_id: str) -> Path:
    return session_file(session_id, "fork-lane.lock")


def take_lane(session_id: str):
    """Hold the session's lane and record its cutoff after taking the name.

    The lane lock serializes publication and readers' decisions, so an input is
    never exposed to the session while waiting for a cutoff that would hold it.
    It is innermost: neither this writer nor `lane_since` takes a page or session
    lock while holding it. Filesystem timestamps cannot order the take against
    the admission clock, since they may be coarser.
    """
    with flocked(lane_lock_path(session_id)):
        lease = take_wait_lease(lane_path(session_id), supersede=True)
        try:
            LANE_START.write(
                session_file(session_id, LANE_START.kind),
                {"since": time.time()},
            )
        except BaseException:
            release_lease(lease)
            raise
        return lease


def lane_since(session_id: str) -> float | None:
    """The live lane's published admission cutoff, waiting for a take in progress.

    Delivery can already hold the session lock, so publication has its own lock.
    A crashed or ended writer's record is not live without its kernel lease.
    """
    with flocked(lane_lock_path(session_id)):
        if not lease_speaks_here(lane_path(session_id)):
            return None
        start = LANE_START.read(session_file(session_id, LANE_START.kind))
        return start["since"] if start is not None else None


def _admitted(event: dict) -> float:
    return datetime.fromisoformat(event["ts"]).timestamp()


def handed_inputs(session_id: str, page_dir: Path) -> set[str]:
    held = HANDED.read(session_file(session_id, HANDED.kind))
    return set((held or {"handed": {}})["handed"].get(page_key(page_dir), []))


def held(page: PageTransaction) -> list[Held]:
    """The page's threads in the held state (the module header's table), by when
    their holds end."""
    return _held(page.page_dir, page.events, page.cursor, page.active_claim)


def forked(
    page_dir: Path, events: list[dict], cursor: int, claim: dict | None
) -> set[str]:
    """The waiting messages a fork has taken on, which read On it
    (`served_state.work`): those of the page's held threads while the fork writes
    its line, and those the agent's working line came after, until the session
    answers. `claim` is the page's active claim, as `held` reads it: with none, no
    fork speaks for the page."""
    if claim is None:
        return set()
    waiting, lined = _waiting(events)
    return {
        event["id"]
        for said in waiting.values()
        for event in said
        if event["id"] in lined
    } | {
        input_id
        for thread in _held(page_dir, events, cursor, claim)
        for input_id in thread.inputs
    }


def _waiting(events: list[dict]) -> tuple[dict[str, list[dict]], set[str]]:
    """Each thread's waiting messages in log order, the user's since the agent's
    last answer in it, and the ids of the user's messages an agent's working line
    came after."""
    from .events import taken_back
    from .thread_context import thread_names

    messages = kinds_declaring("message")
    names = thread_names(events)
    withdrawn = taken_back(events)
    waiting: dict[str, list[dict]] = {}
    lined: set[str] = set()
    for event in events:
        if event["kind"] not in messages or event["id"] in withdrawn:
            continue
        thread = names.get(event["id"])
        if thread is None:
            continue
        if event["author"] == "user":
            waiting.setdefault(thread, []).append(event)
        elif event.get("ephemeral"):
            # The agent's working line answers nothing, and speaks for what waits.
            lined.update(said["id"] for said in waiting.get(thread, []))
        else:
            waiting.pop(thread, None)
    return waiting, lined


def _held(
    page_dir: Path, events: list[dict], cursor: int, claim: dict | None
) -> list[Held]:
    """`held`, from the log, its cursor and the page's active claim.

    It reads the log, never the page's fold, which costs about 100 ms, since
    admission, every hook and every served reading ask it: a user's message after
    the agent's last answer in its thread owes the thread's answer, and `ask` hands
    over one the fold says owes none."""
    if claim is None:
        return []
    since = lane_since(claim["id"])
    if since is None:
        return []
    pending = {event["id"] for event in unacknowledged(events, cursor)}
    messages = kinds_declaring("message")
    if not any(
        event["kind"] in messages and event["author"] == "user"
        for event in events
        if event["id"] in pending
    ):
        return []
    picked = {
        input_id
        for event in events
        if event["kind"] == "pickup"
        for input_id in event["events"]
    }
    handed = handed_inputs(claim["id"], page_dir)
    waiting, _lined = _waiting(events)
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


def held_at_admission(page: PageTransaction, event: dict) -> bool:
    """Whether the input `event`, just admitted, is held for a fork. For a thread
    message to a Claude Code session, the page's diagnostics note the answer, and
    where it is no, whether the session's lane was up (`fork_hold`), which is what
    says why no fork took a message up."""
    held = event["id"] in held_inputs(page)
    claim = page.active_claim
    if (
        claim is not None
        and claim["harness"] == "claude-code"
        and event["kind"] in kinds_declaring("message")
    ):
        _note(
            page.page_dir,
            {
                "type": "fork_hold",
                "session": claim["id"],
                "event": event["id"],
                "held": held,
                "lane": lane_since(claim["id"]),
            },
        )
    return held


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
            request=payload.get("request"),
        )
    return ask(session_id, basis, payload.get("running") or [])


def ask(session_id: str, basis: dict, running: list[dict]) -> dict | None:
    """What to fork the conversation with for the thread `basis` names, as
    `{"prompt", "thread"}`, or None once the thread is no longer held as
    `basis` has it, or the page no longer the session's."""
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
    _note(
        page_dir,
        {
            "type": "fork_asked",
            "session": session_id,
            "thread": basis["thread"],
            "inputs": basis["inputs"],
            "running": [call["tool"] for call in running],
        },
    )
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
    deliver it (`delivery.batch_data`) and what the session is running."""
    thread = {
        "page": data["page"],
        "threads": data["threads"],
        "events": [
            {key: value for key, value in event.items() if key != "answer"}
            for event in data["events"]
        ],
    }
    return f"""{OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to acknowledge them at once while the main session carries on. The main session takes the message from here and does what it asks. Every tool call is denied here, so don't call tools, and reply straight away without thinking it over. {_running_line(running)}

The thread, as Leaf delivers it; "events" are the user's messages, oldest first:
{json.dumps(thread, ensure_ascii=False, indent=1)}

Leaf posts your reply in the thread at once as the agent's working line, until the main session's own words replace it. Write that one line: what the agent will do about the message, in a few of the user's words, as the agent would before starting ("reading the reconnect traces"; "recording your choice and making that change"). Leave the answer to the main session, even where the conversation above holds it. Reply with the line alone.
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
    request: dict | None = None,
) -> dict:
    """Post the fork's answer as the agent's working line and hand the thread to the
    session, or hand it over bare where the fork failed (`failed`, its reason); what
    came of it, recorded in the page's diagnostics."""
    line = (answer or "").strip()
    # TODO: where the message is self-contained, a fork that can act could do the
    # work itself rather than hand it over ("A fork that takes the work" in
    # notes/fork-replies.md).
    outcome = (
        _post(session_id, basis, line)
        if line
        else _hand_over(session_id, basis, f"the fork failed: {failed or 'no line'}")
    )
    _record(
        session_id,
        basis,
        {
            **outcome,
            "running": running or [],
            **({"usage": usage} if usage else {}),
            **({"elapsedMs": elapsed_ms} if elapsed_ms is not None else {}),
            **({"request": request} if request else {}),
        },
    )
    return outcome


def _record(session_id: str, basis: dict, outcome: dict) -> None:
    """Note what came of a held thread in its page's diagnostics."""
    _note(
        Path(basis["page"]),
        {
            "type": "fork_reply",
            "session": session_id,
            "thread": basis["thread"],
            "inputs": basis["inputs"],
            **outcome,
        },
    )


def _note(page_dir: Path, record: dict) -> None:
    """Append `record` to the page's diagnostics, dropped where the page can't be
    written, as every diagnostic is (`interaction_log`)."""
    from .interaction_log import append_interactions

    try:
        append_interactions(page_dir, [{"source": "cli", **record}])
    except OSError:
        pass


def _post(session_id: str, basis: dict, text: str) -> dict:
    """The fork's working line, posted as the agent's while the thread is still held
    as `basis` has it, and the thread handed to the session after it; or why
    nothing was."""
    from .delivery import ReceiptRefused
    from .findings import Rejected
    from .refusals import Refused
    from .thread import Receipt, post_reply

    try:
        record = post_reply(
            Path(basis["page"]),
            {"responds": basis["inputs"][-1]},
            text,
            settlement=Receipt(fence=lambda page: _still_held(page, session_id, basis)),
            claimed_session=session_id,
            ephemeral=True,
        )
    except (FileNotFoundError, ReceiptRefused):
        return {"outcome": "dropped", "text": text}
    except (Rejected, Refused) as error:
        # The line's own checks refused it, so the thread goes to the session bare,
        # and the note says why.
        why = f"the line was refused: {error}"
        return {**_hand_over(session_id, basis, why), "text": text, "refused": why}
    if record is None:
        return {"outcome": "dropped", "text": text}
    return {**_hand_over(session_id, basis, None), "text": text, "line": record["id"]}


def _hand_over(session_id: str, basis: dict, why: str | None) -> dict:
    """Hand the thread `basis` names to the session, while it is still held as
    `basis` has it (`_hand_over_held`); `why` is Leaf's reason, where the fork
    didn't choose it."""
    reason = {} if why is None else {"why": why}
    try:
        with PageTransaction(Path(basis["page"])) as page:
            if not _still_held(page, session_id, basis):
                return {"outcome": "dropped", **reason}
            _hand_over_held(page, session_id, basis["inputs"])
    except FileNotFoundError:
        return {"outcome": "dropped", **reason}
    return {"outcome": "hand_over", **reason}


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
