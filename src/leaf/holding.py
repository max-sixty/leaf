"""Which turn of a session holds each of the user's thread messages, and what a turn
may do about a message another turn holds.

A session works in turns: its main thread's (the session lifecycle record,
`state.py`) and each run of an agent it runs beside the main thread, such as a
working fork that took a thread's work (`state.AGENT_TURNS`, `forks.py`). A pickup in
the page log names the turn that took messages in, and an agent's reply names the
turn that posted it (`thread.post_reply`), so the log says which turn took each
message and which answered it. A thread's waiting messages are the user's messages
in it since the agent's last answer there, and that answer ends the thread's round
(`rounds`).

A turn holds a thread from the moment it takes the thread until another turn does:

- A waiting message is held by the turn whose opened pickup of any of the thread's
  waiting messages is newest, whether the main thread's or an agent's
  (`holding_turns`). A turn that picks up a thread's messages, as a fork's take, a
  fork's tool boundary or the main thread's prompt does, takes the whole thread
  from whichever turn had it.
- Where no turn has picked up a waiting message, the turn that last took its
  thread, by a pickup of an earlier message or by an answer, holds it while that
  turn is an agent's still running. So a thread's further messages go to the fork
  working it, even once it has answered, rather than to a second fork or to the
  main thread; and to the main thread once its answer took the thread over.
- An answered message is held by the turn that answered it, the one its thread's
  answer names, so an answer takes the thread as a pickup does. A fork may repeat its
  own answer, but not answer again a message the main thread answered over it.

This is the one reading of who holds a message. An agent's tool boundary
(`to_carry`), the end of an agent's run (`forks.ended`), keeping a thread back for a
line fork (`forks.kept_back`) and an agent turn's right to act on a message
(`refuse_unheld`) all ask it rather than reading the pickups and answers themselves.

`message_holders` names each waiting message's holder for a reader (`holder`): the
session's main thread, or the fork that took the thread, by the name the main thread
reaches it by, with whether its turn runs, closed or lapsed; or, for a message Leaf
keeps back while a line fork judges it (`forks.kept_back`), the line fork. Who owes
its answer now is that holder while it is the line fork or a fork whose turn runs,
and otherwise the main thread (`owed_by`). Delivery (`delivery.deliverable`), admission
(`forks.kept_from_main_at_admission`) and the activity fold, with every hook that
reads it (`activity.agent_holds`), filter that one reading: they keep from the main
thread what it doesn't owe, and hand it what a fork's ended turn left it. `leaf page
state` prints it, giving each answer the agent owes the holder that owes it now
(`activity.canonical_activity`), and each thread the `holder` of the turn that last
took it (`last_taken`). So a main thread recovering what it owes there can leave a
running fork's work, and a message a line fork is judging, to them.

An agent's turn keeps the main thread off the messages it holds only while it runs,
that is while it is open and renewed within the working grace
(`activity.running_agent_turns`). The main thread's deliveries and pickups leave
those messages out (`pickable`), so its prompt takes the thread over only once that
turn has closed or lapsed. The main thread is sovereign all the same: its answer to
a message a running fork holds takes the thread over at once. An agent's turn may
pick up, answer or start on only the messages it holds or no turn holds
(`refuse_unheld`), so a fork whose thread another turn took can neither take it
back, nor answer it, nor show itself at work on it.

`docs/forks.html`, "Who holds a message", explains the rule with the rest of the
fork design; `session-lifetime.md`, "Turns and generations", is the contract other
modules rely on.
"""

from datetime import datetime
from typing import NamedTuple

from .findings import Finding
from .registry.kernel import kinds_declaring
from .service import PageTransaction
from .state import agent_turn_stamps


class Rounds(NamedTuple):
    """The page's threads by their current round (`rounds`)."""

    # Each thread's waiting messages in log order, the user's since the agent's last
    # answer in it.
    waiting: dict[str, list[dict]]
    # The ids of the user's messages an agent's working line came after, which read
    # On it (`forks.forked`).
    lined: set[str]
    # Each thread's last answer from the agent: its last message that responds to
    # one of the user's, which leaves out a message the agent wrote unasked.
    answers: dict[str, dict]
    # The agent's message that ended each answered message's round, by the user's
    # message's id.
    answered: dict[str, dict]


def rounds(events: list[dict]) -> Rounds:
    """The page's threads by their current round, from the log."""
    from .events import taken_back
    from .thread_context import thread_names

    messages = kinds_declaring("message")
    names = thread_names(events)
    withdrawn = taken_back(events)
    waiting: dict[str, list[dict]] = {}
    lined: set[str] = set()
    answers: dict[str, dict] = {}
    answered: dict[str, dict] = {}
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
            answered.update((said["id"], event) for said in waiting.pop(thread, []))
            if "responds" in event:
                answers[thread] = event
    return Rounds(waiting, lined, answers, answered)


def holding_turns(
    events: list[dict],
    session: str | None,
    running: set[str],
    found: Rounds | None = None,
) -> dict[str, str]:
    """The turn of `session` that holds each of the user's waiting thread messages
    (the module header), where `running` is the set of `session`'s agent turns
    running now (`running_turns`) and `found` the log's `rounds`, where the caller
    has them."""
    newest = newest_pickups(events, session)
    if not newest and not running:
        return {}
    found = rounds(events) if found is None else found
    holders: dict[str, str] = {}
    unpicked = []
    for thread, said in found.waiting.items():
        if picked := [newest[event["id"]] for event in said if event["id"] in newest]:
            newest_turn = max(picked)[1]
            holders.update((event["id"], newest_turn) for event in said)
        else:
            unpicked.append(thread)
    if unpicked and running:
        took = _last_taken(events, newest, found.answers)
        for thread in unpicked:
            if (turn := took.get(thread)) is not None and turn in running:
                holders.update((event["id"], turn) for event in found.waiting[thread])
    return holders


def _last_taken(
    events: list[dict], newest: dict[str, tuple[int, str]], answers: dict[str, dict]
) -> dict[str, str | None]:
    """The turn that last took each thread: the newer of its newest pickup of any of
    the thread's messages (`newest`, as `newest_pickups` reads them) and its last
    answer (`answers`, as `rounds` reads them)."""
    from .thread_context import thread_names

    names = thread_names(events)
    last: dict[str, tuple[int, str | None]] = {
        thread: (answer["seq"], answer.get("turn"))
        for thread, answer in answers.items()
    }
    for input_id, (seq, turn) in newest.items():
        thread = names.get(input_id)
        if thread is not None and seq > last.get(thread, (0, None))[0]:
            last[thread] = (seq, turn)
    return {thread: turn for thread, (_seq, turn) in last.items()}


def last_taken(
    events: list[dict], session: str | None, found: Rounds | None = None
) -> dict[str, str | None]:
    """The turn of `session` that last took each thread, by a pickup or an answer
    (`_last_taken`), where `found` is the log's `rounds`, where the caller has them."""
    found = rounds(events) if found is None else found
    return _last_taken(events, newest_pickups(events, session), found.answers)


def newest_pickups(
    events: list[dict], session: str | None
) -> dict[str, tuple[int, str]]:
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


def fork_name(thread: str) -> str:
    """The name Leaf gives the fork that takes `thread`, by which the main session
    reaches it (`SendMessage`)."""
    return f"leaf-{thread}"


def holder(
    turn: str | None, thread: str | None, stamps: dict[str, dict], running: set[str]
) -> dict:
    """Who `turn` is, as every report of who holds a message or a thread names it.
    `turn` is the turn of the claimant's session that holds a message in `thread`, or
    that last took `thread`; `thread` is None for an input in no thread, which only
    the main thread has.

    One of the session's agent turns (`stamps`, as `state.agent_turn_stamps` gives
    them) is `{"kind": "fork", "name", "state"}`: the fork that took the thread, by
    `fork_name`, and whether its turn is `running` (in `running`, as `holding_turns`
    takes it), `closed` or `lapsed` (`activity.agent_turn_state`). Any other turn, or
    none, is `{"kind": "main"}`, the session's main thread, which has whatever no
    agent's turn holds."""
    # TODO(2026-11-14): the shipped instructions no longer keep a worker subagent off
    # the page, and its `leaf` commands act as the main thread. If workers come to act
    # on pages, give each a turn of its own (`state.acting_turn`) and name it here.
    from .activity import agent_turn_state

    if turn not in stamps:
        return {"kind": "main"}
    assert thread is not None
    return {
        "kind": "fork",
        "name": fork_name(thread),
        "state": agent_turn_state(turn, stamps, running),
    }


MAIN = {"kind": "main"}
# The holder of a message Leaf keeps back while a line fork judges it.
LINE = {"kind": "line"}


def message_holders(
    events: list[dict],
    session: str | None,
    stamps: dict[str, dict],
    running: set[str],
    kept: set[str],
    found: Rounds | None = None,
) -> dict[str, dict]:
    """The holder of each of the user's waiting thread messages that the main thread
    doesn't hold (the module header), for the claimant's `session`, whose agent turns
    are `stamps` and `running` as `holder` takes them: the line fork (`LINE`) for each
    message in `kept`, which Leaf keeps back while a line fork judges it
    (`forks.kept_back`), and otherwise the fork whose turn holds it
    (`holding_turns`), named. Any other message is the main thread's (`MAIN`).
    `found` is the log's `rounds`, where the caller has them."""
    if not stamps and not kept:
        return {}
    found = rounds(events) if found is None else found
    turns = holding_turns(events, session, running, found)
    return {
        event["id"]: held
        for thread, said in found.waiting.items()
        for event in said
        if (
            held := LINE
            if event["id"] in kept
            else holder(turns.get(event["id"]), thread, stamps, running)
        )["kind"]
        != "main"
    }


def owed_by(held: dict) -> dict:
    """Who owes the answer to a message whose holder is `held` (`message_holders`):
    that holder while it is the line fork or a fork whose turn runs, and otherwise
    the main thread, which owes what a fork's ended turn left."""
    return held if held["kind"] == "line" or held.get("state") == "running" else MAIN


def taken_over(input_ids) -> str:
    """What an agent's turn is told as it acts on messages another turn of its
    session now holds (`refuse_unheld`)."""
    return (
        f"this agent's turn no longer holds {', '.join(input_ids)}: another turn of "
        "the session took its thread over, so leave it and end your turn"
    )


def refuse_unheld(
    events: list[dict],
    session: str,
    turn: str,
    input_ids: list[str],
    running: set[str],
) -> None:
    """The one rule for an agent's turn acting on messages: it may act only on the
    messages it holds or that no turn holds, a waiting one by `holding_turns` and an
    answered one by the turn that answered it, and is refused the rest
    (`taken_over`). Its pickups (`pickable`), replies and starts (`authorize`) all ask
    this, so a fork whose thread another turn took can neither take it back nor
    answer it nor show itself at work on it. `running` is as `holding_turns` takes
    it.

    The answered messages are this rule's alone: every other reader of
    `holding_turns` asks who holds work still owed, which an answered message
    isn't."""
    from .delivery import ReceiptRefused

    found = rounds(events)
    holders = holding_turns(events, session, running, found)

    def held_by(input_id: str) -> str | None:
        if input_id in holders:
            return holders[input_id]
        answer = found.answered.get(input_id)
        return None if answer is None else answer.get("turn")

    if taken := [i for i in input_ids if held_by(i) not in (None, turn)]:
        raise ReceiptRefused(taken_over(taken))


def authorize(
    page: PageTransaction,
    session: str | None,
    input_ids: list[str],
    thread: str | None = None,
    *,
    answers: bool = False,
) -> Finding | None:
    """Refuse a write a command of `session` makes about the messages `input_ids` on
    `page`, a reply to one or a start on one, or a message in `thread` that answers
    none, where its actor may not make it: an agent whose turn has ended
    (`state.acting_agent_turn`), or an agent's turn acting on a message another turn
    holds (`refuse_unheld`). A message that answers none is held to the thread's round
    (`round_of`), so a fork can't write in a thread another turn took from it; a
    session that doesn't hold the page is no agent's.

    The main thread acts on whatever its session owes, and its answer (`answers`)
    takes the thread from any turn that held it. A command no agent id marks acts as
    the main thread, whoever ran it: the main thread itself, a fork's script, a
    worker or the user's terminal (`state.acting_turn`). The user chose on 2026-11-14
    that such a command goes through rather than being refused, and says beside its
    result which fork it acted beside: the note this returns (`fork-holds-thread`),
    where a running fork holds the write's thread, by the holder `leaf page state`
    gives the thread (`last_taken`, `holder`)."""
    from .state import acting_agent_turn

    claim = page.claim
    if session is None or claim is None or claim["id"] != session:
        return None
    if (turn := acting_agent_turn(session)) is not None:
        if thread is not None and not input_ids:
            input_ids = round_of(page.events, thread)
        refuse_unheld(page.events, session, turn, input_ids, running_turns(claim))
        return None
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return None
    from .thread_context import thread_names

    names = thread_names(page.events)
    threads = (
        [thread] if thread is not None else [names[i] for i in input_ids if i in names]
    )
    running = running_turns(claim)
    took = last_taken(page.events, session)
    for name in threads:
        held = holder(took.get(name), name, stamps, running)
        if held["kind"] == "fork" and held["state"] == "running":
            return Finding(
                "fork-holds-thread",
                values={"fork": held["name"], "answers": answers},
                severity="advice",
            )
    return None


def round_of(events: list[dict], thread: str) -> list[str]:
    """The user's messages in `thread`'s round: those waiting, or where none waits,
    those the thread's last answer ended the round of (`rounds`)."""
    found = rounds(events)
    if said := found.waiting.get(thread):
        return [event["id"] for event in said]
    if (answer := found.answers.get(thread)) is None:
        return []
    return [i for i, ender in found.answered.items() if ender["id"] == answer["id"]]


def pickable(
    page: PageTransaction, input_ids: list[str], session: str, turn: str | None
) -> list[str]:
    """Which of `input_ids` the turn `turn` of `session` may record an opened pickup
    of, under the page's transaction (`delivery.record_pickup`, which every pickup
    goes through), so no pickup moves a thread against this module's rule. An
    agent's turn picks up only what `refuse_unheld` lets it act on: its take, its
    tool boundary and its acknowledgement of a pointer; a late acknowledgement of a
    thread another turn has since taken over is refused, and records nothing. Any
    other turn's pickup of a message an agent's running turn holds would take the
    thread over, which waits until that turn has closed or lapsed, so it leaves those
    messages out."""
    claim = page.active_claim
    if claim is None or claim["id"] != session:
        return input_ids
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return input_ids
    running = running_turns(claim)
    if turn in stamps:
        refuse_unheld(page.events, session, turn, input_ids, running)
        return input_ids
    holders = holding_turns(page.events, session, running)
    return [i for i in input_ids if holders.get(i) not in running]


def taken_by_agent_turns(page: PageTransaction) -> set[str]:
    """What whoever records a receipt passes for the page's agent turns
    (`delivery.receive_passed`): each input a turn of an agent picked up, open or
    closed, which that turn received as it picked it up, and each waiting message a
    running agent turn holds through its pickup of the thread's round, which goes to
    it at its tool boundary. A message a running turn holds only as the last to take
    its thread stays pending, since no turn has taken it in: should that turn end
    without picking it up, Leaf keeps it back for a line fork as it does any new
    message (`forks.kept_back`), and a receipt that passed it would have handed it to
    the main thread instead."""
    claim = page.active_claim
    if claim is None:
        return set()
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return set()
    running = running_turns(claim)
    by_pickup = holding_turns(page.events, claim["id"], set())
    return set(picked_in(page.events, claim["id"], set(stamps))) | {
        input_id for input_id, turn in by_pickup.items() if turn in running
    }


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


def picked_in(events: list[dict], session: str, turns: set[str]) -> dict[str, str]:
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


def to_carry(page: PageTransaction, turn: str) -> list[dict]:
    """The waiting messages the running agent turn `turn` holds that it hasn't yet
    picked up, in log order: the user's further messages in the threads it holds,
    which its tool boundary hands it (`hook_transport.carry_agent_turn`)."""
    claim = page.active_claim
    if claim is None:
        return []
    running = running_turns(claim)
    if turn not in running:
        return []
    holders = holding_turns(page.events, claim["id"], running)
    taken = set(picked_in(page.events, claim["id"], {turn}))
    return [
        event
        for event in page.events
        if holders.get(event["id"]) == turn and event["id"] not in taken
    ]


def running_threads(events: list[dict], session: str, running: set[str]) -> set[str]:
    """The threads a running agent turn of `session` took, by a pickup of any of
    their messages or an answer, which Leaf keeps back for no other fork
    (`forks.kept_back`); `running` is as `holding_turns` takes it."""
    if not running:
        return set()
    from .thread_context import thread_names

    names = thread_names(events)
    return set(turn_threads(events, session, running)) | {
        names[event["id"]]
        for event in events
        if "responds" in event and event.get("turn") in running and event["id"] in names
    }


def turn_threads(
    events: list[dict], session: str, turns: set[str]
) -> dict[str, list[str]]:
    """The threads whose messages an opened pickup of `session` in one of `turns`
    names, each with those messages."""
    from .thread_context import thread_names

    names = thread_names(events)
    threads: dict[str, list[str]] = {}
    for input_id in picked_in(events, session, turns):
        if (thread := names.get(input_id)) is not None:
            threads.setdefault(thread, []).append(input_id)
    return threads
