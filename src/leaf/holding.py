"""Which turn of a session holds each thread of a page, and what a turn may do about a
thread another turn holds.

A session works in turns: its main thread's (the session lifecycle record,
`state.py`) and each line turn, in which a line fork writes the agent's working line
on a thread beside the main thread (`state.AGENT_TURNS`, `forks.py`). A pickup in the
page log names the turn that took messages in, and an agent's reply names the turn
that posted it (`thread.post_reply`), so the log says which turn took each message
and which answered it. A thread's waiting messages are the user's turns in it the
agent still owes an answer while it stands open, as the fold reads them
(`events.awaits_agent`, `events.unanswered_turns`), so a thread the user resolved has
none: an answer that responds to the newest of them settles them all and ends the
thread's round, one that responds to an older one settles only that, and a message of
the agent's that responds to nothing settles nothing (`rounds`). A user's rewrite of
a message waits as a turn of its own, held as the thread's other messages are.

The thread is the unit: a turn holds a thread, with all its waiting messages, from
the moment it takes the thread until another turn does (`Hold`).

- The turn whose opened or held pickup of one of the thread's waiting messages is
  newest holds it. A turn that picks up a thread's messages, as the main thread's
  prompt or tool boundary does, takes the whole thread from whichever turn had it.
- Where no turn has picked up a waiting message, the turn that last took the
  thread, by a pickup of an earlier message or by an answer, holds it.
- A thread Leaf keeps back while a line fork judges its waiting messages is held by
  the line turn admission opened for it, by that turn's `held` pickup, which takes
  nothing in and keeps nothing once the turn ends, so the thread is then the main
  thread's (`forks.py`).
- An answered message is held by the turn that answered it, the one its thread's
  answer names, so an answer takes the thread as a pickup does.

A subagent the session spawns names no turn of its own: its commands act as the main
thread's, whose thread it was given (`authorize`).

`reading_of` reads this once for a page, from its log, or the threads the fold built
from it, and the claimant's line turns (`forks.page_holding`, `served_state.work`),
and every rule asks that one `Holding` rather than reading the pickups and answers
itself: delivery (`delivery.deliverable`) and admission
(`forks.kept_from_main_at_admission`) keep from the main thread what a line turn
holds; the activity fold reads it once (`activity.canonical_activity`), as every hook
that reads the fold does (`activity.agent_holds`); and the receipts that pass what
the main thread doesn't await (`not_awaited`), listing the threads line turns hold
(`forks.kept_back`) and every writer's right to act on a thread (`authorize`,
`pickable`) ask it too.

A thread's holder, for a reader (`holder`), is the session's main thread or a
running line turn, and the holder owes the answer to the thread's waiting messages.
`leaf page state` prints it for each thread and on each answer the agent owes, so a
main thread recovering what it owes there can leave a message a line fork is judging
to it.

A line turn keeps the main thread off the messages it holds only while it runs, that
is while it is open and not yet lapsed (`activity.running_agent_turns`). The main
thread's deliveries and pickups leave those messages out (`pickable`), so its prompt
takes the thread over only once that turn has closed or lapsed. The main thread is
sovereign all the same: its answer to a message a line turn holds takes the thread
over at once. A line turn may pick up, answer or start on only the messages it holds
or no turn holds (`refuse_unheld`), so a line fork whose thread another turn took
writes nothing there.

How it works' Forks tab (`docs/how-it-works.html`), "Who holds a message",
explains the rule with the rest of the fork design; `session-lifetime.md`, "Turns and
generations", is the contract other modules rely on.
"""

from collections.abc import Callable
from datetime import datetime
from typing import NamedTuple

from .findings import Finding
from .service import PageTransaction


class Rounds(NamedTuple):
    """The page's threads by their current round (`rounds`)."""

    # Each thread's waiting turns in log order (the module header): the user's
    # messages and rewrites the agent still owes an answer.
    waiting: dict[str, list[dict]]
    # The ids of the waiting turns an agent's working message came after, which read
    # On it (`Holding.forked`).
    lined: set[str]
    # Each thread's last answer from the agent: its last message that responds to
    # one of the user's, which leaves out a message the agent wrote unasked.
    answers: dict[str, dict]
    # The thread each name reaches: each message's (`thread_context.thread_names`)
    # and each of the user's rewrites.
    names: dict[str, str]
    # Each thread's history, its messages and the user's rewrites, as the fold reads
    # them (`events.build_threads`).
    threads: dict[str, dict]

    def answer_to(self, input_id: str) -> dict | None:
        """The answer that settled the user's turn `input_id`, as its thread's history
        keeps it (`events.settlements`), or None for a turn no answer settled. Only a
        line turn acting on a message asks, so it reads the one thread then."""
        from .events import settlements

        thread = self.threads.get(self.names.get(input_id, ""))
        if thread is None:
            return None
        return next(
            (
                settled.answer
                for settled in settlements(thread)
                if any(turn["id"] == input_id for turn in settled.turns)
            ),
            None,
        )


def rounds(events: list[dict], threads: dict[str, dict]) -> Rounds:
    """The page's threads by their current round, from its log `events` and its
    `threads` as the fold builds them with the page's containment
    (`events.build_threads`): by the fold's own rule for what an answer settles and
    what is still owed (`events.settlements`, `events.unanswered_turns`), in a thread
    that stands open, so a thread the user resolved, or a choice's answer closed, has
    nothing waiting (`events.awaits_agent`). Each waiting turn is the logged event,
    as every delivery hands it over, not the thread's reading of it, which carries a
    rewrite's words in its message."""
    from .events import unanswered_turns
    from .thread_context import thread_names

    names = dict(thread_names(events))
    logged: dict[str, dict] | None = None
    waiting: dict[str, list[dict]] = {}
    lined: set[str] = set()
    answers: dict[str, dict] = {}
    for thread, held in threads.items():
        for revision in held["revisions"]:
            names[revision["id"]] = thread
        if not held["resolved"] and (said := unanswered_turns(held)):
            if logged is None:
                logged = {event["id"]: event for event in events}
            said = waiting[thread] = [logged[turn["id"]] for turn in said]
            # The seq of the newest working message of the agent's in the thread.
            working = max(
                (
                    message["seq"]
                    for message in held["msgs"]
                    if message["author"] == "agent"
                    and message.get("ephemeral")
                    and "withdrawn" not in message
                ),
                default=0,
            )
            lined.update(turn["id"] for turn in said if turn["seq"] < working)
        if answer := next(
            (
                turn
                for turn in reversed(held["turns"])
                if turn["author"] == "agent" and "responds" in turn
            ),
            None,
        ):
            answers[thread] = answer
    return Rounds(waiting, lined, answers, names, threads)


MAIN = {"kind": "main"}
LINE = {"kind": "line"}


def holder(turn: str | None, running: set[str]) -> dict:
    """Who `turn` is, as every report of who holds a thread names it, and so who owes
    the answer to its waiting messages now. `turn` is the turn of the claimant's
    session that holds a thread: one of its running line turns (`running`,
    `activity.running_agent_turns`) is `LINE`, and any other turn, or none, the
    session's main thread (`MAIN`). A line turn holds a thread only by its `held`
    pickup, which counts only while the turn runs (`reading`), so a line turn that
    has ended holds nothing."""
    return LINE if turn in running else MAIN


class Hold(NamedTuple):
    """Who holds one thread (the module header)."""

    # The turn of the claimant's session that holds the thread: the one whose pickup
    # of one of its waiting messages is newest, or, where no turn picked one up, the
    # one that last took the thread, by a pickup of an earlier message or an
    # answer; None where no turn of the session took it.
    turn: str | None
    # Whether `turn` holds the thread's waiting messages by a pickup of one of them:
    # an opened one, or a running line turn's `held` one (`reading`).
    picked: bool
    # Who holds it, for a reader: `turn` named (`holder`).
    holder: dict


UNHELD = Hold(None, False, MAIN)


class Holding(NamedTuple):
    """Who holds each thread of a page, as `reading` reads it once for every rule
    that asks: the claimant's `session`, whether it is `live`, holding the page by an
    active claim, its line turns `stamps` and those of them running now `running`
    (`activity.running_agent_turns`), the log's `rounds`, what the log's pickups took
    in, and each thread's `Hold`.

    A session that has ended still names the turns that held its threads, which
    `leaf page state` prints, but holds nothing for a rule that acts: delivery hands
    nothing on for it (`delivery.deliverable`), and no pickup or receipt of its turns
    moves a thread (`pickable`, `not_awaited`)."""

    session: str | None
    live: bool
    stamps: dict[str, dict]
    running: set[str]
    found: Rounds
    # Every input any pickup of the log took in, of any session, turn or phase but a
    # line turn's `held`: what some consumer took in, as a harness's queue does
    # (`codex.finish_codex_batch`).
    taken: set[str]
    threads: dict[str, Hold]

    def hold(self, thread: str | None) -> Hold:
        """Who holds `thread`; an input in no thread is the main thread's."""
        return UNHELD if thread is None else self.threads.get(thread, UNHELD)

    def of(self, input_id: str) -> Hold:
        """Who holds the thread the input `input_id` stands in."""
        return self.hold(self.found.names.get(input_id))

    def keeper(self, input_id: str) -> str | None:
        """The turn that holds the waiting message `input_id`: its thread's, where
        that turn picked up one of the thread's waiting messages; None for a message
        no turn holds or that isn't waiting."""
        thread = self.found.names.get(input_id)
        if thread is None or all(
            event["id"] != input_id for event in self.found.waiting.get(thread, ())
        ):
            return None
        held = self.threads[thread]
        return held.turn if held.picked else None

    def waiting(self, keep: Callable[[Hold], bool]) -> list[dict]:
        """The waiting messages, in log order, of each thread whose `Hold` `keep`
        accepts."""
        return sorted(
            (
                event
                for thread, said in self.found.waiting.items()
                if keep(self.threads[thread])
                for event in said
            ),
            key=lambda event: event["seq"],
        )

    def forked(self) -> set[str]:
        """The waiting messages a line fork has taken on, which read On it
        (`served_state.work`): those of a thread a running line turn holds, and those
        the agent's working message came after, until the session answers."""
        return {
            event["id"]
            for event in self.waiting(lambda held: held.holder["kind"] == "line")
        } | {
            event["id"]
            for said in self.found.waiting.values()
            for event in said
            if event["id"] in self.found.lined
        }


def reading(
    events: list[dict],
    session: str | None,
    stamps: dict[str, dict],
    running: set[str],
    *,
    live: bool,
    found: Rounds,
) -> Holding:
    """Who holds each thread of a page by its pickups and answers (the module header),
    from its log `events`, for the claimant's `session`, whose line turns are
    `stamps` and `running`, and which is `live`, as `Holding` holds them, where
    `found` is the log's `rounds`. A line turn's `held` pickup holds a thread as an
    opened one does while that turn runs, but takes nothing in
    (`delivery.record_pickup`), and counts for nothing once the turn has ended, so
    the thread is whoever's it would be without it. Every reading goes through
    `reading_of`."""
    newest: dict[str, tuple[int, str]] = {}
    taken: set[str] = set()
    for event in events:
        if event["kind"] == "pickup" and event["phase"] != "held":
            taken.update(event["events"])
        if (
            event["kind"] == "pickup"
            and (
                event["phase"] == "opened"
                or (event["phase"] == "held" and event["turn"] in running)
            )
            and event["session"] == session
            and event["turn"]
        ):
            for input_id in event["events"]:
                newest[input_id] = (event["seq"], event["turn"])
    # The turn that last took each thread: the newer of its newest pickup of any of
    # the thread's messages and its last answer.
    last: dict[str, tuple[int, str | None]] = {
        thread: (answer["seq"], answer.get("turn"))
        for thread, answer in found.answers.items()
    }
    for input_id, (seq, turn) in newest.items():
        thread = found.names.get(input_id)
        if thread is not None and seq > last.get(thread, (0, None))[0]:
            last[thread] = (seq, turn)
    threads = {}
    for thread in {*found.waiting, *last}:
        pickups = [
            newest[event["id"]]
            for event in found.waiting.get(thread, ())
            if event["id"] in newest
        ]
        turn = max(pickups)[1] if pickups else last.get(thread, (0, None))[1]
        threads[thread] = Hold(turn, bool(pickups), holder(turn, running))
    return Holding(session, live, stamps, running, found, taken, threads)


def reading_of(
    events: list[dict], present: dict, now_iso: str, threads: dict[str, dict]
) -> Holding:
    """Who holds each thread of a page, the one builder every reading goes through:
    from its log `events` (`reading`) and its `threads` (`rounds`), and the facts a
    presence reading carries of its claim
    (`presence.presence_with_activity`): the claimant's session (`claim_session`)
    and its line turns (`agent_turns`), which may run only while the session is
    alive (`session_alive`) at `now_iso`. The fold reads it from the page's presence
    and the threads it built, and `forks.page_holding` from the claim it holds the
    page's transaction under."""
    from .activity import running_agent_turns

    live = present["session_alive"] is True
    stamps = present["agent_turns"]
    return reading(
        events,
        present.get("claim_session"),
        stamps,
        running_agent_turns(stamps, live, datetime.fromisoformat(now_iso)),
        live=live,
        found=rounds(events, threads),
    )


def taken_over(input_ids) -> str:
    """Why a line turn's write about messages another turn of its session now holds
    is refused (`refuse_unheld`)."""
    return (
        f"this line turn no longer holds {', '.join(input_ids)}: another turn of "
        "the session took its thread over"
    )


def refuse_unheld(
    holding: Holding, turn: str, input_ids: list[str], thread: str | None = None
) -> None:
    """The one rule for a line turn acting on messages and threads: it may act only
    on the messages it holds or that no turn holds, a waiting one by its thread's
    keeper (`Holding.keeper`) and an answered one by the turn that answered it, and
    in a `thread` it holds or no turn holds (`Holding.hold`), and is refused the rest
    (`taken_over`). Its held pickup (`pickable`) and its line (`authorize`) both ask
    this, so a line fork whose thread another turn took writes nothing there.

    The answered messages are this rule's alone: every other reader of `Holding`
    asks who holds work still owed, which an answered message isn't."""
    from .delivery import ReceiptRefused

    def held_by(input_id: str) -> str | None:
        if (kept := holding.keeper(input_id)) is not None:
            return kept
        answer = holding.found.answer_to(input_id)
        return None if answer is None else answer.get("turn")

    taken = [i for i in input_ids if held_by(i) not in (None, turn)]
    if thread is not None and holding.hold(thread).turn not in (None, turn):
        taken.append(thread)
    if taken:
        raise ReceiptRefused(taken_over(taken))


def authorize(
    page: PageTransaction,
    holding: Holding,
    session: str | None,
    input_ids: list[str],
    thread: str | None = None,
) -> Finding | None:
    """Refuse a write a command of `session` makes about the messages `input_ids` on
    `page`, whose `Holding` is `holding`, a reply to one or a start on one, or a
    message in `thread` that answers none, where its actor may not make it: a line
    naming a line turn that has ended (`state.acting_agent_turn`), or a line turn
    acting on a message, or in a thread, another turn holds (`refuse_unheld`).

    Any other writer, one naming no turn, acts as the main thread, whoever runs it:
    the main thread itself, a subagent it spawned, the user's terminal or another
    session (`state.acting_turn`). It may write anywhere, and its answer may take the
    thread from the turn that held it, by the module header's rule. The user chose
    that such a write goes through on a thread a line turn holds, rather than being
    refused, and says so beside its result: the advice this returns
    (`fork-holds-thread`), where a line turn holds the thread (`holder`). `thread`,
    where given, names the write's thread, as a reply's parent or a to-do's subject
    does, which an answer to a thread widget names by no message of its own;
    otherwise each of `input_ids` names its own."""
    from .state import acting_agent_turn

    claim = page.claim
    if (
        session is not None
        and claim is not None
        and claim["id"] == session
        and (turn := acting_agent_turn(session)) is not None
    ):
        refuse_unheld(holding, turn, input_ids, thread)
        return None
    names = holding.found.names
    threads = (
        [thread] if thread is not None else [names[i] for i in input_ids if i in names]
    )
    for name in threads:
        if (owes := holding.hold(name).holder)["kind"] != "main":
            return Finding(
                "fork-holds-thread",
                values={"holder": owes},
                severity="advice",
            )
    return None


def pickable(
    holding: Holding, input_ids: list[str], session: str, turn: str | None
) -> list[str]:
    """Which of `input_ids` the turn `turn` of `session` may record an opened pickup
    of, on a page whose `Holding` is `holding`, under the page's transaction
    (`delivery.record_pickup`, which every pickup goes through), so no pickup moves a
    thread against this module's rule. A line turn's held pickup takes only what
    `refuse_unheld` lets it act on. Any other turn is the main thread's, which picks
    up only the waiting messages it owes (`holder`): one a running line turn holds
    is its, and a pickup of it would take the thread from it, so it leaves those
    messages out. The main thread's turn takes such a thread once the line turn has
    let it go, or by answering it."""
    if not holding.live or holding.session != session:
        return input_ids
    if turn in holding.stamps:
        refuse_unheld(holding, turn, input_ids)
        return input_ids
    elsewhere = {
        event["id"]
        for event in holding.waiting(lambda held: held.holder["kind"] != "main")
    }
    return [i for i in input_ids if i not in elsewhere]


def not_awaited(holding: Holding) -> set[str]:
    """The inputs of a page whose `Holding` is `holding` that its main thread doesn't
    await, which whoever records a receipt passes beside what the main thread took
    in (`delivery.receive_passed`): each waiting message of a thread a running line
    turn holds (`holder`). The page keeps one cursor for all of them, so a message
    only the line turn has would otherwise keep every later input the main thread
    took in from its receipt, to be handed over again once that turn ends.

    The cursor passing such a message hands it to nobody. Once the main thread owes
    it, having never taken it in, it is the main thread's input again
    (`delivery.deliverable`)."""
    if not holding.live:
        return set()
    return {
        event["id"]
        for event in holding.waiting(lambda held: held.holder["kind"] != "main")
    }


def running_turns(stamps: dict[str, dict]) -> set[str]:
    """The line turns of `stamps`, the stamps of an active claim's
    (`state.agent_turn_stamps`), believed running now (`activity.running_agent_turns`).
    What a line turn holds moves with this set as the turn closes or lapses, which no
    file records, so a cache of what the session owes keys on it
    (`session.watch_between_turns`)."""
    if not stamps:
        return set()
    # The fold's module, which a session with no line turns never loads here, as a
    # quiet page's tool hook doesn't (`delivery.deliverable`).
    from .activity import running_agent_turns

    return running_agent_turns(stamps, True, datetime.now().astimezone())
