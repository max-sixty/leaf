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
can act. The fork also judges whether such a fork could do the work beside the
session (`ANSWER`'s `work`). Where the module makes forks that act, which it does only
with `LEAF_FORK_WORK=on` while the design is tried, a thread judged `take` goes to a
fork spawned from the conversation, which does the work and answers the user itself
(`_give`); otherwise Leaf records the judgment and hands the thread over
(`notes/fork-replies.md`, "A fork that takes the work").

A fork that takes a thread runs a turn of its own (`state.AGENT_TURNS`), and Leaf
records the take as that turn's pickup of the thread's waiting messages, with the
receipt, under the hold's fence: the page log then says who has the message, so every
reader of received input agrees on it. While the fork's turn runs, the activity fold
reads the pickup and the fork's starts as work in hand (`activity.agent_holds`), the
main thread is neither handed the thread's messages nor reminded of them
(`held_inputs`, `delivery.deliverable`), and the user's further messages in the thread
go to the fork at its tool boundaries (`hook_transport.carry_agent_turn`). Leaf's
PreToolUse hook marks the fork's `leaf` commands with its agent id
(`hooks.agent_command`), so the fork answers with `leaf thread reply` from the delivery
Leaf gave it, writing as the agent, in its own turn (`state.acting_turn`). As its run
ends the module says so (`ended`), which closes the turn. An answered thread is done,
though a to-do the fork opened with its answer stays open for the main thread to
schedule. A thread still owed, which the fork gave back (`HAND_BACK`) or left, is the
main thread's like any update it received, whose hooks and watch then remind it with
the fork's answer reference.

The user chose on 2026-11-10 that one fork works a thread: a later message the line's
fork judges `take`, in a thread whose last answer came from a fork's turn, goes to
that fork again, in a new turn under the same agent id (`_resumable`), rather than to
a new fork. Leaf's message resuming it (`resume_prompt`) carries the thread's delivery
and names what the rest of the session did on the page since the fork's last turn
began (`_since`), which the fork's transcript lacks. A thread whose fork ran in an
earlier generation of the session goes to a new fork, and so does one whose fork the
module fails to resume; that new fork takes over the turn Leaf opened for the old one
(`started`).

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

The fork thinks at `EFFORT` whatever the session's own effort, since every second it
takes keeps the thread's messages from the session. The turn-end check's fork has an
effort of its own (`clerk.EFFORT`), measured on its own work. On 2026-11-09 low wrote
lines as good as xhigh's. On 40 recorded thread messages, each replayed from its
session's transcript (`notes/fork-replies.md`, "How well the fork judges"), a judge
blind to the effort passed 35 lines at each effort and preferred low's on 19, xhigh's
on 16 and neither on 5; `leaf-dev eval 'fork-reply*'` passed 35 of 35 at each over
five repeats. Neither effort thought on the recorded messages, so their output and
time matched there (low wrote 1.03 times the tokens, 95% interval 0.97–1.10). On the
eval's short conversations xhigh thought over 5 of its 35 lines, taking up to 3.5 s
where a line took a median 1 s, and low over none, for 0.85 times xhigh's time
(0.75–0.95). So low removes the occasional line xhigh spends seconds thinking over,
and the line's time no longer depends on the session's effort.

A thread's waiting messages are the user's messages since the agent's last answer in
it, the newest of which owes the thread's answer. Each thread with waiting messages
is in one of these states, which `held` and `agent_inputs` compute from the page's
log, the session's hand-overs (`HANDED`), its agents' turns and the forks' lane;
nothing stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| held | Leaf keeps the thread's waiting messages from the session while a fork writes its line | a user message in a thread none of whose waiting messages the session has received or been handed, while the session's lane is live and has been since the first of them arrived |
| taken | a fork that acts does the work in a turn of its own, which picked the messages up; the user's further messages in the thread go to that fork while the turn runs, and once it has ended, one the line's fork judges a fork's goes to the same fork, resumed | the line's fork judging the work a fork's, where the module makes such forks (`take`) |
| with the session | delivered as any input is | a hand-over: the fork's line posted, a failed fork, or the lane's once `BOUND_S` has passed since the newest waiting message (`look`); the lane going down; or a taken thread's fork turn ending without answering it (`ended`) |

The main session hears as a fork takes a thread and as it answers or gives it back
(`clerk.queue`), since Claude Code tells it nothing of a fork a module made, and it
can steer or stop the fork by the name Leaf gives it.

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
outcome (`fork_reply`), with the fork's tokens and time, the effort Claude Code
reports it sent (`effort`), why Leaf refused its line where it did, and the request
it resent (`request` in `hooks/claude-code.ts`, which says where a replay cuts the
conversation: to `sent` while `running` lists a call, else to `row`; its own
`effort` is the session's), as the clerk's `turn_end_check` notes have it, which is
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
from .service import PageTransaction, owned_pages, unacknowledged
from .state import (
    STRING,
    Record,
    agent_turn_stamps,
    close_agent_turns,
    described,
    flocked,
    name_agent_turn,
    object_schema,
    open_agent_turn,
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

# The words that open the fork's question, which the transcript carries, and the
# question of a fork that does the work.
OPENING = "<leaf-fork-reply>"
WORK_OPENING = "<leaf-fork-work>"
# How a fork that took the work ends when the work belongs with the session after all.
HAND_BACK = "HAND BACK:"

# What a fork answers (`reply_prompt`): the agent's working line, and whether a fork
# of the session could do the work beside it (`take`) or the work belongs with the
# session (`hand_over`). Leaf records that judgment and hands every thread over.
ANSWER = {
    "type": "object",
    "properties": {
        "line": {"type": "string", "minLength": 1, "pattern": r"\S"},
        "work": {"enum": ["take", "hand_over"]},
    },
    "required": ["line", "work"],
    "additionalProperties": False,
}

# How hard the fork thinks, whatever the session's effort (the header says why).
EFFORT = "low"


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
    threads = _threads(events)
    return {
        event["id"]
        for said in threads.waiting.values()
        for event in said
        if event["id"] in threads.lined
    } | {
        input_id
        for thread in _held(page_dir, events, cursor, claim)
        for input_id in thread.inputs
    }


class _Threads(NamedTuple):
    """What a fork's states read of the page's threads (`_threads`)."""

    # Each thread's waiting messages in log order, the user's since the agent's last
    # answer in it.
    waiting: dict[str, list[dict]]
    # The ids of the user's messages an agent's working line came after.
    lined: set[str]
    # Each thread's last answer from the agent: its last message that responds to
    # one of the user's, which leaves out a message the agent wrote unasked.
    answers: dict[str, dict]


def _threads(events: list[dict]) -> _Threads:
    """The page's threads as a fork's states read them, from the log."""
    from .events import taken_back
    from .thread_context import thread_names

    messages = kinds_declaring("message")
    names = thread_names(events)
    withdrawn = taken_back(events)
    waiting: dict[str, list[dict]] = {}
    lined: set[str] = set()
    answers: dict[str, dict] = {}
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
            if "responds" in event:
                answers[thread] = event
    return _Threads(waiting, lined, answers)


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
    waiting = _threads(events).waiting
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
    """What `delivery.deliverable` keeps from the session's main thread: every
    waiting message of the page's held threads (`held`), and every one an agent's
    running turn holds (`agent_held`)."""
    return {
        input_id for thread in held(page) for input_id in thread.inputs
    } | agent_held(page)


def holding_turns(events: list[dict], session: str) -> dict[str, str]:
    """The turn of `session` that holds each of the user's waiting thread messages:
    the turn of the newest opened pickup, by `session`, of any waiting message in its
    thread, whether the main thread's or an agent's (`state.AGENT_TURNS`). A turn
    that picks up a thread's messages, as a fork's take, a fork's tool boundary or
    the main thread's prompt does, takes the whole thread from whichever turn had it.

    This is the one reading of who holds a message: delivery (`held_inputs`), an
    agent's tool boundary (`agent_turn_inputs`), the activity fold and every hook
    that reads it (`activity.agent_holds`), the end of an agent's run (`ended`) and an
    agent turn's right to act on a message (`refuse_unheld`) all ask it rather than
    filtering the pickups themselves."""
    newest = _newest_pickups(events, session)
    if not newest:
        return {}
    waiting = _threads(events).waiting
    holders = {}
    for said in waiting.values():
        picked = [newest[event["id"]] for event in said if event["id"] in newest]
        if picked:
            turn = max(picked)[1]
            holders.update((event["id"], turn) for event in said)
    return holders


def _newest_pickups(events: list[dict], session: str) -> dict[str, tuple[int, str]]:
    """The seq and turn of the newest opened pickup, by `session`, of each message
    one names."""
    newest: dict[str, tuple[int, str]] = {}
    for event in events:
        if (
            event["kind"] == "pickup"
            and event["phase"] == "opened"
            and event["session"] == session
            and event["turn"]
        ):
            for input_id in event["events"]:
                newest[input_id] = (event["seq"], event["turn"])
    return newest


def taken_over(input_ids) -> str:
    """What an agent's turn is told as it acts on messages another turn of its
    session now holds (`holding_turns`)."""
    return (
        f"this agent's turn no longer holds {', '.join(input_ids)}: another turn of "
        "the session took its thread over and answers it, so leave it and end your "
        "turn"
    )


def refuse_unheld(
    events: list[dict], session: str, turn: str, input_ids: list[str]
) -> None:
    """The one rule for an agent's turn acting on messages: it may act only on the
    messages it holds or that no turn holds, and is refused the rest (`taken_over`).
    A waiting message is held by the turn `holding_turns` names, and an answered one
    by the turn whose opened pickup of it is newest, so a fork may repeat its own
    answer but not answer again a message another turn took over and answered. Its
    pickups (`pickable`), replies and starts (`authorize`) all ask this, so a fork
    that lost its thread to the main thread can neither take it back nor answer it
    nor show itself at work on it.

    The answered messages are this rule's alone: every reader of `holding_turns`
    asks who holds work still owed, which an answered message isn't."""
    from .delivery import ReceiptRefused

    holders = holding_turns(events, session)
    last = {
        input_id: by
        for input_id, (_seq, by) in _newest_pickups(events, session).items()
    }
    if taken := [
        i for i in input_ids if holders.get(i, last.get(i)) not in (None, turn)
    ]:
        raise ReceiptRefused(taken_over(taken))


def authorize(page: PageTransaction, session: str | None, input_ids: list[str]) -> None:
    """Refuse a write a command of `session` makes about the messages `input_ids` on
    `page`, a reply to one or a start on one, where its actor may not make it: an
    agent whose turn has ended (`state.acting_agent_turn`), or an agent's turn acting
    on a message another turn holds (`refuse_unheld`). The main thread acts on
    whatever its session owes, and a session that doesn't hold the page is no
    agent's."""
    from .state import acting_agent_turn

    claim = page.claim
    if session is None or claim is None or claim["id"] != session:
        return
    if (turn := acting_agent_turn(session)) is not None:
        refuse_unheld(page.events, session, turn, input_ids)


def pickable(
    page: PageTransaction, input_ids: list[str], session: str, turn: str | None
) -> list[str]:
    """Which of `input_ids` the turn `turn` of `session` may record an opened pickup
    of, under the page's transaction (`delivery.record_pickup`, which every pickup
    goes through), so no pickup moves a thread against this rule. An agent's turn
    picks up only what `refuse_unheld` lets it act on: its take, its tool boundary
    and its acknowledgement of a pointer; a late acknowledgement of a thread another
    turn has since taken over is refused, and records nothing. Any other turn's
    pickup of a message an agent's running turn holds would take the thread over,
    which waits until that turn has closed or lapsed, so it leaves those messages
    out."""
    claim = page.active_claim
    if claim is None or claim["id"] != session:
        return input_ids
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return input_ids
    if turn in stamps:
        refuse_unheld(page.events, session, turn, input_ids)
        return input_ids
    holders = holding_turns(page.events, session)
    running = running_turns(claim)
    return [i for i in input_ids if holders.get(i) not in running]


def agent_held(page: PageTransaction) -> set[str]:
    """The waiting messages an agent's running turn holds (`holding_turns`), which
    go to that agent at its tool boundary rather than to the main thread. With no
    active claim, no agent speaks for the page."""
    claim = page.active_claim
    if claim is None:
        return set()
    running = running_turns(claim)
    if not running:
        return set()
    return {
        input_id
        for input_id, turn in holding_turns(page.events, claim["id"]).items()
        if turn in running
    }


def agent_inputs(page: PageTransaction) -> set[str]:
    """What whoever records a receipt passes for the page's agents
    (`delivery.receive_passed`): what an agent's running turn holds (`agent_held`),
    and each input a turn of an agent picked up, open or closed, which that turn
    received as it picked it up."""
    claim = page.active_claim
    if claim is None:
        return set()
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return set()
    return set(_picked_in(page.events, claim["id"], set(stamps))) | agent_held(page)


def running_turns(claim: dict) -> set[str]:
    """The turns of the agents running beside the main thread of the session that
    holds a page by `claim`, an active claim, believed running now
    (`activity.running_agent_turns`). What an agent holds moves with this set as a
    turn closes or lapses, which no file records, so a cache of what the session owes
    keys on it (`session.watch_between_turns`)."""
    from .activity import running_agent_turns

    stamps = agent_turn_stamps(claim)
    if not stamps:
        return set()
    return running_agent_turns(stamps, True, datetime.now().astimezone())


def _picked_in(events: list[dict], session: str, turns: set[str]) -> dict[str, str]:
    """Each input an opened pickup of `session` names in one of `turns`, with the
    newest such turn."""
    return {
        input_id: event["turn"]
        for event in events
        if event["kind"] == "pickup"
        and event["phase"] == "opened"
        and event["session"] == session
        and event["turn"] in turns
        for input_id in event["events"]
    }


def agent_turn_inputs(page: PageTransaction, turn: str) -> list[dict]:
    """The waiting messages the running agent turn `turn` holds that it hasn't yet
    picked up, in log order: the user's further messages in the threads it holds,
    which its tool boundary hands it (`hook_transport.carry_agent_turn`)."""
    claim = page.active_claim
    if claim is None or turn not in running_turns(claim):
        return []
    holders = holding_turns(page.events, claim["id"])
    taken = set(_picked_in(page.events, claim["id"], {turn}))
    return [
        event
        for event in page.events
        if holders.get(event["id"]) == turn and event["id"] not in taken
    ]


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
    """One step of a forked reply, as `leaf hook --fork` hands it over: with the
    held thread in `payload["thread"]` and without `answer` or `failed`, the
    question (`ask`); with one, what Leaf did with it (`take`), giving the work to a
    fork where `work_forks` asks for that. The module then says which agent its
    harness started for that fork's turn (`started`), and, as any agent of the
    session's run ends, what it ended with (`ended`)."""
    if "ended" in payload:
        run = payload["ended"]
        return {
            "ended": ended(
                session_id,
                agent=run.get("agent"),
                turn=run.get("turn"),
                answer=run.get("answer"),
                failed=run.get("failed"),
                elapsed_ms=payload.get("elapsed_ms"),
            )
        }
    basis = payload["thread"]
    if "started" in payload:
        return started(
            session_id, basis, payload["started"]["turn"], payload["started"]["agent"]
        )
    if "answer" in payload or "failed" in payload:
        return take(
            session_id,
            basis,
            answer=payload.get("answer"),
            failed=payload.get("failed"),
            usage=payload.get("usage"),
            elapsed_ms=payload.get("elapsed_ms"),
            effort=payload.get("effort"),
            running=payload.get("running") or [],
            request=payload.get("request"),
            work_forks=bool(payload.get("work_forks")),
        )
    return ask(session_id, basis, payload.get("running") or [])


def ask(session_id: str, basis: dict, running: list[dict]) -> dict | None:
    """What to fork the conversation with for the thread `basis` names, as
    `{"prompt", "thread", "effort"}`, or None once the thread is no longer held as
    `basis` has it, or the page no longer the session's."""
    page_dir = Path(basis["page"])
    try:
        with PageTransaction(page_dir) as page:
            if not _still_held(page, session_id, basis):
                return None
            data = _thread_data(page, basis["inputs"])
    except FileNotFoundError:
        return None
    if data is None:
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
    return {"prompt": reply_prompt(data, running), "thread": basis, "effort": EFFORT}


def _thread_data(page: PageTransaction, inputs: list[str]) -> dict | None:
    """The thread's waiting messages `inputs` as Leaf delivers them
    (`delivery.batch_data`), or None where the newest owes no reply."""
    from .delivery import batch_data, current_responses

    responses = current_responses(page.page_dir, page.events)
    owed = responses.get(inputs[-1])
    if owed is None or owed["kind"] != "reply":
        return None
    by_id = {event["id"]: event for event in page.events}
    return batch_data(
        page.page_dir, page, [by_id[i] for i in inputs], responses=responses
    )


def _thread_json(data: dict) -> str:
    return json.dumps(
        {
            "page": data["page"],
            "threads": data["threads"],
            "events": [
                {key: value for key, value in event.items() if key != "answer"}
                for event in data["events"]
            ],
        },
        ensure_ascii=False,
        indent=1,
    )


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
    return f"""{OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to acknowledge them at once while the main session carries on. The main session takes the message from here and does what it asks. Every tool call is denied here, so don't call tools. {_running_line(running)}

The thread, as Leaf delivers it; "events" are the user's messages, oldest first:
{_thread_json(data)}

Leaf posts your line in the thread at once as the agent's working line, until the main session's own words replace it. Write that one line: what the agent will do about the message, in a few of the user's words, as the agent would before starting ("reading the reconnect traces"; "recording your choice and making that change"). Leave the answer to the main session, even where the conversation above holds it.

Then judge who should do what the message asks. "take": a fork of the session with the session's tools could do it start to finish beside the main session, because it needs nothing the main session is changing or about to change (its files and branch, the page's source, its pull requests), settles no question the main session is weighing, and waits on nothing the session is running; answering from reading, a lookup, or research that writes only its own scratch files are such work. "hand_over": it belongs with the main session.

Reply with this JSON alone: {{"line": "<the line>", "work": "take" or "hand_over"}}
</leaf-fork-reply>"""


def work_prompt(delivery: dict, agent: str) -> str:
    """The task of the fork that does a thread's work: what it is for, the delivery
    of the thread Leaf recorded as its turn's (`_give`), and how it ends."""
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, named {agent}, made to do what the message asks beside the main session, which carries on with its own work and leaves this thread to you. You have the session's tools. Change nothing the main session is changing or about to change: its files and branch, the page's source, its pull requests.

Leaf's delivery of the thread to you; "events" are the user's messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Do the work, then answer the user in the thread yourself, as the session would, with the `leaf thread reply` the delivery's `answer` names. Run each `leaf` command as a command of its own that begins with `leaf`, which is how Leaf knows it is yours; give a reply's text with `--text`, or with `--file` naming a file an earlier command wrote. Leaf hands you anything else the user writes in the thread at your next tool call, and your answer then goes to their newest message. If the work turns out to belong with the main session, because it would change what the session is changing or settle a question it is weighing, don't answer: end your turn with "{HAND_BACK}" and one line saying why, and Leaf gives the thread to the main session. Leaf tells the main session what you did either way.
</leaf-fork-work>"""


def resume_prompt(delivery: dict, since: str) -> str:
    """The message that resumes the fork that answered a thread, for the user's
    further messages in it (`_give`): what Leaf gives it, what the rest of the session
    did on the page since the fork's last turn began (`_since`), which its transcript
    lacks, and the delivery Leaf recorded as its new turn's. The fork's first task
    (`work_prompt`) stays in its transcript, so this repeats only how it answers."""
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user wrote again in the thread you answered, and Leaf gives it to you in a new turn of your own. {since} To ask the main session about anything it did, SendMessage main.

Leaf's delivery of the thread to you; "events" are the user's new messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Answer as before: do the work, then reply with the `leaf thread reply` the delivery's `answer` names, run as a command of its own that begins with `leaf`; or, if the work belongs with the main session, end your turn with "{HAND_BACK}" and one line saying why.
</leaf-fork-work>"""


def take(
    session_id: str,
    basis: dict,
    *,
    answer: str | None,
    failed: str | None,
    usage: dict | None = None,
    elapsed_ms: float | None = None,
    effort: str | None = None,
    running: list[dict] | None = None,
    request: dict | None = None,
    work_forks: bool = False,
) -> dict:
    """Post the fork's line as the agent's working line and hand the thread to the
    session, or, where the fork judged the work a fork's (`take`) and the module
    makes such forks (`work_forks`), give the thread to one (`_give`); or hand it
    over bare where the fork failed (`failed`, its reason) or its answer doesn't fit
    `ANSWER`. What came of it, with the fork's judgment of who should do the work
    (`work`), is recorded in the page's diagnostics with the effort Claude Code
    reports it sent the fork at (`effort`)."""
    from .clerk import read_answer
    from .refusals import Refused

    read = None
    if answer is not None:
        try:
            read = read_answer(answer, ANSWER)
        except Refused as error:
            failed = str(error)
    if read is None:
        outcome = _hand_over(
            session_id, basis, f"the fork failed: {failed or 'no answer'}"
        )
    elif read["work"] == "take" and work_forks:
        outcome = {**_give(session_id, basis, read["line"].strip()), "work": "take"}
    else:
        outcome = {
            **_post(session_id, basis, read["line"].strip()),
            "work": read["work"],
        }
    _record(
        session_id,
        basis,
        {
            **outcome,
            "running": running or [],
            **({"usage": usage} if usage else {}),
            **({"elapsedMs": elapsed_ms} if elapsed_ms is not None else {}),
            **({"effort": effort} if effort is not None else {}),
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
    posted = _say(session_id, basis, text, ephemeral=True)
    if "line" not in posted:
        return posted
    return {**_hand_over(session_id, basis, None), **posted}


def _say(session_id: str, basis: dict, text: str, *, ephemeral: bool) -> dict:
    """Post `text` as the agent's, its working line where `ephemeral`, else its
    answer, while the thread is still held as `basis` has it: `{"text", "line"}`
    with the posted message's id, or the outcome where Leaf posted nothing."""
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
            ephemeral=ephemeral,
        )
    except (FileNotFoundError, ReceiptRefused):
        return {"outcome": "dropped", "text": text}
    except (Rejected, Refused) as error:
        # The message's own checks refused it, so the thread goes to the session
        # bare, and the note says why.
        why = f"the message was refused: {error}"
        return {**_hand_over(session_id, basis, why), "text": text, "refused": why}
    if record is None:
        return {"outcome": "dropped", "text": text}
    return {"text": text, "line": record["id"]}


def _fork_name(thread: str) -> str:
    """The name Leaf gives the fork that takes `thread`, by which the main session
    reaches it (`SendMessage`)."""
    return f"leaf-{thread}"


def _resumable(
    page: PageTransaction, session_id: str, thread: str
) -> tuple[str, dict] | None:
    """The fork turn that gave `thread`'s last answer, by its id and as
    `agent_turns` keeps it, whose fork Leaf gives the thread's waiting messages to
    again. The turn whose opened pickup of the answered message is newest gave the
    answer if it posted before that turn closed, since an agent whose turn has ended
    can't post (`state.acting_agent_turn`); an answer after then, such as the main
    thread's to a message the fork gave back, is the main thread's. A message the
    main thread wrote in the thread unasked, such as a correction of the fork's
    answer, answers nothing, so the thread stays the fork's. None where the main
    thread answered last, or the fork's turn still runs or was opened in an earlier
    generation of the session, whose agents ended with it."""
    from .state import agent_turns

    claim = page.active_claim
    answer = _threads(page.events).answers.get(thread)
    if claim is None or answer is None:
        return None
    picked = _newest_pickups(page.events, session_id).get(answer["responds"])
    if picked is None:
        return None
    turn = picked[1]
    entry = agent_turns(session_id).get(turn)
    if (
        entry is None
        or entry["agent"] is None
        or entry["closed"] is None
        or entry["generation"] != claim["generation"]
        or datetime.fromisoformat(answer["ts"])
        > datetime.fromisoformat(entry["closed"])
    ):
        return None
    return turn, entry


def _since(
    events: list[dict], session_id: str, turn: str, entry: dict, thread: str
) -> str:
    """What the rest of the session did on the page from when the fork's last turn
    `turn` opened, as `agent_turns` keeps it (`entry`), which the fork is told on its
    resume (`resume_prompt`): the threads it wrote in, the revisions it published,
    and the to-dos it opened or ended, each named so the fork can look it up. The
    fork's transcript holds what the session had done when that turn opened, from
    the conversation it was forked from or Leaf's earlier messages, and nothing it
    did while the fork ran. The fork's own answers from that turn are left out, each
    a reply to a message the turn picked up, posted before it closed, with the
    to-dos they opened. The delivery carries the thread's own messages, so this
    names only where the session wrote."""
    from .events import taken_back
    from .thread_context import thread_names
    from .todos import TodoReading

    opened, closed = (
        datetime.fromisoformat(entry["opened"]),
        datetime.fromisoformat(entry["closed"]),
    )
    picked = set(_picked_in(events, session_id, {turn}))
    own = {
        event["id"]
        for event in events
        if event.get("responds") in picked
        and datetime.fromisoformat(event["ts"]) <= closed
    }

    def theirs(event: dict) -> bool:
        return event["id"] not in own and datetime.fromisoformat(event["ts"]) > opened

    messages = kinds_declaring("message")
    names = thread_names(events)
    withdrawn = taken_back(events)
    wrote = dict.fromkeys(
        "this thread"
        if names[event["id"]] == thread
        else f"thread {names[event['id']]}"
        for event in events
        if event["kind"] in messages
        and event["author"] == "agent"
        and not event.get("ephemeral")
        and event["id"] not in withdrawn
        and event["id"] in names
        and theirs(event)
    )
    revisions = [
        event["revision"]
        for event in events
        if "publication" in event and theirs(event)
    ]
    done = []
    if wrote:
        done.append(f"wrote in {', '.join(wrote)}")
    if revisions:
        done.append(
            f"published revision {revisions[0]}"
            if len(revisions) == 1
            else f"published revisions {revisions[0]} to {revisions[-1]}"
        )
    for todo in TodoReading(events).todos:
        if theirs(todo):
            done.append(f"opened the to-do “{todo['title']}” ({todo['id']})")
        if todo["outcome"] is not None and theirs(todo["outcome"]):
            done.append(
                f"ended the to-do “{todo['title']}” ({todo['id']}) as {todo['state']}"
            )
    began = "Since your last turn began, the rest of the session"
    if not done:
        return f"{began} has done nothing on the page."
    return f"{began} {'; '.join(done)}."


def _give(session_id: str, basis: dict, line: str) -> dict:
    """Post the fork's working line and give the thread to a fork that does its
    work: under the hold's fence, open a turn for it (`state.open_agent_turn`) and
    record that turn's pickup of the thread's waiting messages, with their receipt,
    from a delivery frozen for it. Returns `{"outcome": "take", "agent", "turn",
    "prompt"}`, the fork's name, its turn and its task carrying that delivery, which
    the module spawns it with; the main session hears which fork has the thread, so
    it can steer or stop it (`clerk.queue`).

    Where a fork's turn gave the thread's last answer and has closed (`_resumable`),
    the turn is that fork's, named with its agent id from the start, and the outcome
    adds `resume`, `{"agentId", "prompt"}`, the message that resumes it
    (`resume_prompt`), so one fork works the thread however many messages the user
    sends it. The module resumes it, or, where the resume fails, spawns a fork with
    `prompt`, and then says which agent runs the turn (`started`)."""
    from .clerk import queue
    from .delivery import batch_refs, freeze_delivery, receive_passed, record_pickup

    page_dir = Path(basis["page"])
    agent = _fork_name(basis["thread"])
    posted = _say(session_id, basis, line, ephemeral=True)
    if "line" not in posted:
        return posted
    try:
        with PageTransaction(page_dir) as page:
            if not _still_held(page, session_id, basis):
                return {"outcome": "dropped", **posted}
            data = _thread_data(page, basis["inputs"])
            if data is None:
                # Only the session can settle what owes no reply in the thread.
                _hand_over_held(page, session_id, basis["inputs"])
                return {"outcome": "hand_over", **posted}
            answered = _resumable(page, session_id, basis["thread"])
            resumed = None if answered is None else answered[1]["agent"]
            turn = open_agent_turn(session_id, resumed)
            if turn is None:
                return {"outcome": "dropped", **posted}
            since = (
                None
                if answered is None
                else _since(page.events, session_id, *answered, basis["thread"])
            )
            delivery = freeze_delivery([data])
            by_id = {event["id"]: event for event in page.events}
            record_pickup(
                page,
                [by_id[input_id] for input_id in basis["inputs"]],
                session=session_id,
                turn=turn,
                refs=batch_refs(delivery["batches"][0]),
            )
            receive_passed(page, agent_inputs(page))
    except FileNotFoundError:
        return {"outcome": "dropped", **posted}
    queue(
        session_id,
        [
            f"Leaf gave the user's message in thread {basis['thread']} on {page_dir} "
            f"to a fork of this conversation named {agent}, which is doing what it "
            "asks beside you and will answer there; Leaf tells you when it has. Leave "
            f"that thread to it; to steer or stop it, SendMessage {agent}."
        ],
    )
    return {
        "outcome": "take",
        **posted,
        "agent": agent,
        "turn": turn,
        "prompt": work_prompt(delivery, agent),
        **(
            {}
            if since is None
            else {
                "resume": {"agentId": resumed, "prompt": resume_prompt(delivery, since)}
            }
        ),
    }


def started(session_id: str, basis: dict, turn: str, agent: str) -> dict:
    """Record that the agent its harness names `agent` runs the fork turn `turn`
    Leaf opened for the thread `basis` names (`state.name_agent_turn`), so its
    commands act in that turn and its tool boundaries carry the thread's further
    messages: the fork the module spawned, or the one it resumed, whose name the
    turn already had. A fork spawned where a resume failed takes the turn over from
    the agent it was opened for. A turn that ended first, as its session's may have,
    is left closed, and the fork then acts as any subagent of the session does."""
    named = name_agent_turn(session_id, turn, agent)
    outcome = {
        "step": "start",
        "outcome": "start" if named else "dropped",
        "agent": _fork_name(basis["thread"]),
        "agentId": agent,
        "turn": turn,
    }
    _record(session_id, basis, outcome)
    return outcome


def ended(
    session_id: str,
    *,
    agent: str | None,
    turn: str | None,
    answer: str | None,
    failed: str | None,
    elapsed_ms: float | None = None,
) -> list[dict]:
    """Close the turn of an agent of the session whose run ended, the one its
    harness names `agent`, or `turn` where it never started, and say what came of
    each thread it took, judged by the messages the turn picked up itself: none of
    them still waiting, it answered (`answer`), whatever the user has written since,
    or answered and opened a to-do on the thread that is still open (`todo`), which
    the main thread now owes and schedules (`todos`); still waiting and held by the
    closed turn (`holding_turns`), it gave the thread back (`hand_over`), as its last
    words did (`HAND_BACK`), it failed (`failed`) or it ended without answering, and
    the main thread owes it now (`activity.agent_holds`); still waiting and held by
    another turn, that turn took it over (`taken_over`). The main session hears of
    an answer, a to-do or a hand-over (`clerk.queue`), and that the thread owes
    nothing only where nothing waits in it and no to-do on it is open. A session no
    watch follows is nudged for a thread it now owes, and the page's diagnostics
    note each outcome; the outcomes, one for each thread. An agent with no open
    turn, as most of a session's are, ends nothing."""
    from .clerk import queue
    from .presence import nudge_unwatched
    from .todos import TodoReading

    closed = set(close_agent_turns(session_id, turn=turn, agent=agent))
    if not closed:
        return []
    text = (answer or "").strip()
    why = (
        text.removeprefix(HAND_BACK).strip()
        if text.startswith(HAND_BACK)
        else f"the fork failed: {failed}"
        if failed
        else "the fork ended without answering"
    )
    outcomes, told = [], []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim is None or claim["id"] != session_id:
                    continue
                threads = _turn_threads(page.events, session_id, closed)
                waiting = _threads(page.events).waiting
                holders = holding_turns(page.events, session_id)
                seqs = {event["id"]: event["seq"] for event in page.events}
                owed = TodoReading(page.events).owed
                judged, owing, opened = {}, {}, {}
                # The threads where the user wrote again after the fork's answer.
                since = {thread for thread in threads if waiting.get(thread)}
                for thread, inputs in threads.items():
                    subject = {"kind": "thread", "id": thread}
                    owing[thread] = [t for t in owed if t["subject"] == subject]
                    # The open to-dos opened after the messages the fork took.
                    taken = min(seqs[input_id] for input_id in inputs)
                    opened[thread] = [t for t in owing[thread] if t["seq"] > taken]
                    waits = {event["id"] for event in waiting.get(thread, [])}
                    still = [input_id for input_id in inputs if input_id in waits]
                    judged[thread] = (
                        ("todo" if opened[thread] else "answer")
                        if not still
                        else "hand_over"
                        if holders.get(still[0]) in closed
                        else "taken_over"
                    )
                if "hand_over" in judged.values():
                    nudge_unwatched(page)
        except FileNotFoundError:
            continue
        for thread, inputs in threads.items():
            name = _fork_name(thread)
            if judged[thread] == "taken_over":
                outcome = {"outcome": "taken_over"}
            elif judged[thread] == "hand_over":
                outcome = {"outcome": "hand_over", "why": why}
                told.append(
                    f"Your fork {name} gave thread {thread} on {page_dir} back to "
                    f"you, which now owes the user its answer: {why}"
                )
            else:
                todos = opened[thread]
                outcome = {
                    "outcome": judged[thread],
                    **({"todos": [t["id"] for t in todos]} if todos else {}),
                }
                listed = " and ".join(
                    f"the to-do “{t['title']}” ({t['id']})" for t in todos
                )
                told.append(
                    f"Your fork {name} answered the user's message in thread "
                    f"{thread} on {page_dir}"
                    + (
                        f" and opened {listed}, which you now owe: schedule "
                        f"{'it' if len(todos) == 1 else 'each'} with your other "
                        "work, and end it with `leaf task end` once it is done"
                        if todos
                        else ""
                    )
                    + ". Read its answer there: where what you know shows it wrong, "
                    "correct it there"
                    + (
                        "; the user's message there since reaches you as any new "
                        "one does."
                        if thread in since
                        else "; otherwise the thread owes nothing."
                        if not owing[thread]
                        else "."
                    )
                )
            _record(
                session_id,
                {"page": str(page_dir), "thread": thread, "inputs": inputs},
                {
                    "step": "join",
                    "agent": name,
                    **outcome,
                    **({"elapsedMs": elapsed_ms} if elapsed_ms is not None else {}),
                },
            )
            outcomes.append({"page": str(page_dir), "thread": thread, **outcome})
    if told:
        queue(session_id, told)
    return outcomes


def _turn_threads(
    events: list[dict], session: str, turns: set[str]
) -> dict[str, list[str]]:
    """The threads whose messages an opened pickup of `session` in one of `turns`
    names, each with those messages."""
    from .thread_context import thread_names

    names = thread_names(events)
    threads: dict[str, list[str]] = {}
    for input_id in _picked_in(events, session, turns):
        if (thread := names.get(input_id)) is not None:
            threads.setdefault(thread, []).append(input_id)
    return threads


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
