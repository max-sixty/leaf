"""Which turn of a session holds each of the user's thread messages, and what a turn
may do about a message another turn holds.

A session works in turns: its main thread's (the session lifecycle record,
`state.py`) and each run of an agent it runs beside the main thread, such as a
working fork that took a thread's work (`state.AGENT_TURNS`, `forks.py`). A pickup in
the page log names the turn that took messages in. The turn whose opened pickup of
any of a thread's waiting messages is newest holds all of them, whether it is the
main thread's turn or an agent's (`holding_turns`), so a turn that picks up a
thread's messages, as a fork's take, a fork's tool boundary or the main thread's
prompt does, takes the whole thread from whichever turn had it. A thread's waiting
messages are the user's messages in it since the agent's last answer there
(`rounds`).

This is the one reading of who holds a message. Delivery (`forks.kept_from_main`),
an agent's tool boundary (`to_carry`), the activity fold and every hook that reads
it (`activity.agent_holds`), the end of an agent's run (`forks.ended`) and an agent
turn's right to act on a message (`refuse_unheld`) all ask it rather than reading
the pickups themselves.

An agent's turn keeps the main thread off the messages it holds only while it runs,
that is while it is open and renewed within the working grace
(`activity.running_agent_turns`): the main thread's deliveries leave them out, and
its pickups leave them out too (`pickable`), so it takes the thread over only once
that turn has closed or lapsed. An agent's turn may pick up, answer or start on only
the messages it holds or no turn holds (`refuse_unheld`). For that rule an answered
message is held by the turn whose opened pickup of it is newest, so a fork may repeat
its own answer but not answer again a message another turn took over and answered.

`docs/forks.html`, "Who holds a message", explains the rule with the rest of the
fork design; `session-lifetime.md`, "Turns and generations", is the contract other
modules rely on.
"""

from datetime import datetime
from typing import NamedTuple

from .registry.kernel import kinds_declaring
from .service import PageTransaction
from .state import agent_turn_stamps


class Rounds(NamedTuple):
    """The page's threads by their current round (`rounds`)."""

    # Each thread's waiting messages in log order, the user's since the agent's last
    # answer in it.
    waiting: dict[str, list[dict]]
    # The ids of the user's messages an agent's working line came after.
    lined: set[str]
    # Each thread's last answer from the agent: its last message that responds to
    # one of the user's, which leaves out a message the agent wrote unasked.
    answers: dict[str, dict]


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
    return Rounds(waiting, lined, answers)


def holding_turns(events: list[dict], session: str) -> dict[str, str]:
    """The turn of `session` that holds each of the user's waiting thread messages:
    the turn of the newest opened pickup, by `session`, of any waiting message in its
    thread (the module header)."""
    newest = newest_pickups(events, session)
    if not newest:
        return {}
    holders = {}
    for said in rounds(events).waiting.values():
        picked = [newest[event["id"]] for event in said if event["id"] in newest]
        if picked:
            turn = max(picked)[1]
            holders.update((event["id"], turn) for event in said)
    return holders


def newest_pickups(events: list[dict], session: str) -> dict[str, tuple[int, str]]:
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
    by the turn whose opened pickup of it is newest. Its pickups (`pickable`), replies
    and starts (`authorize`) all ask this, so a fork that lost its thread to the main
    thread can neither take it back nor answer it nor show itself at work on it.

    The answered messages are this rule's alone: every reader of `holding_turns`
    asks who holds work still owed, which an answered message isn't."""
    from .delivery import ReceiptRefused

    holders = holding_turns(events, session)
    last = {
        input_id: by for input_id, (_seq, by) in newest_pickups(events, session).items()
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


def taken_by_agent_turns(page: PageTransaction) -> set[str]:
    """What whoever records a receipt passes for the page's agent turns
    (`delivery.receive_passed`): what an agent's running turn holds (`agent_held`),
    and each input a turn of an agent picked up, open or closed, which that turn
    received as it picked it up."""
    claim = page.active_claim
    if claim is None:
        return set()
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return set()
    return set(picked_in(page.events, claim["id"], set(stamps))) | agent_held(page)


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
    if claim is None or turn not in running_turns(claim):
        return []
    holders = holding_turns(page.events, claim["id"])
    taken = set(picked_in(page.events, claim["id"], {turn}))
    return [
        event
        for event in page.events
        if holders.get(event["id"]) == turn and event["id"] not in taken
    ]


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
