"""Forks of a Claude Code session's conversation that answer the user's thread
messages: a line fork, which posts the agent's working line on a thread's waiting
messages at once and sorts them, and a working fork with the session's tools, which
does a thread's work and answers it. Both run in every Claude Code session, and only
there, from Leaf's hooks module (`hooks/claude-code.ts`). How it works' Forks tab
(`docs/how-it-works.html`) explains the design, diagrams included; this header holds
the rules this module keeps and the choices behind them, and `holding.py` the rule for
which turn holds a message.

On a real page the session's answer to a thread message takes tens of seconds, longer
when it is busy, and the thread shows nothing from the agent after a message until the
session's first model call ends (`notes/fork-replies.md`, "Forks on real pages").
`$.model.fork` resends the session's last request with one more message, at any moment,
mid-command too, and a fork decides in seconds. The user had the fork post only
the agent's working line and hand the thread on, rather than answer it: a line
fork can't call tools (`$.model.fork` denies every one), and answering is left to a fork
that can act. The line fork also judges whether a working fork could do the work beside
the session (`ANSWER`'s `work`): `take` gives the thread to one (`_take`), and
`hand_over` hands the thread to the session; Leaf records the judgment either way.

A thread's waiting messages are the user's messages the agent still owes an answer
in it while it stands open (`holding.rounds`). Each thread with
waiting messages is in one of these states, which `holding.py` reads from the page's
log and its session's agent turns; nothing stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| kept back | a running line turn holds the thread's waiting messages while a line fork writes its line | while the session's lane is up, a user message that is its thread's only waiting message, in a thread no running agent turn took, or any event that joins the waiting turns of a thread a running line turn holds, which it replaces: admission opens the line turn and records its pickup of the thread's waiting messages (`kept_from_main_at_admission`) |
| taken | a working fork does the work in a turn of its own, which holds the thread until another turn takes it (`holding.py`) | the line fork judging `take` (`_take`) |
| with the session | delivered as any input is | the agent turn ending with the thread unanswered: the line posted, a failed line fork, a line turn or an unconfirmed fork's turn lapsing (`activity.STARTING_GRACE`), a working fork's run ending (`ended`); or the main thread's answer taking the thread from either |

Each thread message Leaf keeps back opens an agent turn of its own
(`state.AGENT_TURNS`), the line turn, which admission marks as a line turn as it
opens it (`state.open_agent_turn`) and whose pickup of the thread's waiting messages
it records in the transaction that appends the message, so the watch never sees the
message unheld and admission doesn't nudge for it (`event_endpoint`). That pickup is
`held` (`delivery.record_pickup`): it holds the thread as any pickup does, but
takes nothing in, so no reader of delivery counts it, and the message reads as sent
to the session until a turn opens it. Where the line fork judges `take`, Leaf closes
the line turn and opens the working fork's own turn, which a resumed fork runs under
its agent id from the opening, and a new one once the module says which agent it
spawned (`started`), and records that turn's opened pickup of the thread's waiting
messages, with the delivery's references and its receipt, in one transaction. A
turn's role never changes, and `holding.holder` reports it as `line` or `fork`, so
no reader infers it from what the turn wrote. Each step of a line fork acts only
while its turn is a running line turn (`_line_runs`), so a stale step, as a module
reloaded mid-fork repeats, or one whose turn a later message replaced, writes nothing
and ends no fork's turn. As the fork's
run ends the module says so (`ended`), which closes the turn and judges each thread
by what the turn picked up and wrote. The main session hears which fork took a
thread once the module says the fork runs (`started`): as it says which agent it
spawned for a new one, and once it has delivered a resumed one's message; and it
hears as the fork's run ends (`clerk.queue`), since Claude Code tells it nothing of
a fork a module made. The user chose these lines over the fork's own
SendMessage to the main thread. Leaf writes a line from the log, so it covers a fork
that failed or was stopped before it could write, and wakes the main thread only
where a fork's end leaves it owing something. A fork's SendMessage could say more of
what the fork did, but it starts a turn on an idle main session, so it would wake the
main thread for every answer, and add a second report to the notification Claude Code
sends as a resumed run ends. Claude Code offers no third way: a module starts a fork
only with `$.agent.spawn`, whose first run never notifies the main thread, and the
module's own call to the Agent tool is refused (2.1.322). A line waits for the
session's next tool boundary or prompt, and Leaf wakes an idle session only for what
a fork's end leaves it owing: a thread given back, whose answer is owed again, and a
to-do the fork opened, whose line wakes it (`ended`).

The fork's task names its turn and tells it to begin each `leaf` command with
`leaf --turn` and that turn (`work_prompt`, `resume_prompt`), so the command acts in
the turn from the fork's first command on, and is refused once the turn has closed
(`state.acting_agent_turn`). A fork's command without it acts as the main thread's,
as any command that names no turn does, and says beside its result which fork holds
the thread (`holding.authorize`). The user chose that the fork marks its own
commands, over Leaf's PreToolUse hook rewriting each to name the fork's agent id:
that hook can mark only a `leaf` that leads its Bash call, so it denies every other,
and Leaf learns a new fork's agent id only once Claude Code has spawned it, so until
then it denies every agent's `leaf` command.

These lines, the holder `leaf page state` prints (`holding.holder`) and the advice
beside a command on a fork's thread all name the fork by its agent id, and the main
session steers or stops the fork with a SendMessage to that id. A send to the id
reaches the agent in every run and every generation of the session, resuming an
ended one. A name doesn't:
Claude Code gives a name to the newest agent spawned under it, refuses a send to a
name that has moved from the agent the main session first reached by it, and reaches
nothing by a name after `claude --resume` (2.1.325, `notes/fork-replies.md`). So
Leaf spawns each fork unnamed (`step`), leaving the main session no second address that
could move.

The user chose that one fork works a thread. While a fork's turn runs,
its thread's further messages are its own, and Leaf keeps none back for another
(`_keeps`). A later message the line fork judges `take`, in a thread whose last
answer names a fork's turn that has since closed, goes to that fork again, resumed in
a new turn (`_resumable`), with a message (`resume_prompt`) that tells it to read
the page's state, since its transcript lacks what the rest of the session did there
meanwhile. The user chose that reading over a summary Leaf wrote of it,
and that a thread whose fork can't be resumed goes to the main thread rather than to
a new fork.

The line is the agent's progress message in the thread (`thread.post_reply`), which
the thread shows until the session's own words replace it. From the moment Leaf
starts keeping a thread back, and while the line stands, the thread's waiting
messages read On it (`holding.Holding.forked`, which `served_state.work` serves as their workflows'
`at_work`, so every surface showing whether the agent is at work agrees), as the user
chose. That word is all the line fork changes: as a receipt's progress
the line takes nothing in hand (`thread.Receipt`), so every reader that ages, nudges
or holds a turn reads the message's delivery. A start would read as the session's
turn, renewing it after an interrupt and holding the message at Working before the
session had it, which would hide it from the nudge and the overdue count.

The line fork thinks at the session's own effort, and its prompt asks it to reply
straight away without thinking it over, since every second it takes keeps the thread's
messages from the session; a fork at another effort can cost a rewrite of the
conversation to the cache (`carrier.fork` says when). A fork at
`low` writes lines as good as xhigh's (`notes/fork-replies.md`, "How well the fork
judges") and skips the occasional line xhigh spends seconds thinking over, while a
fork at xhigh asked to reply straight away does as well on the eval's cases.

Any event that joins a thread's waiting turns while a line turn holds the thread,
such as a quick correction or "and also" right after the first message or the
user's rewrite of it, replaces that line turn:
admission closes it and opens a new one whose pickup names every waiting turn of the
thread, so the follower lists the new turn and the module asks a line fork about
them all, and the first line fork's answer, about the turns as they stood, drops,
since its turn no longer runs (`_line_runs`). With the lane down, no follower would
list a new turn, so the event joins the running line turn, whose line then responds
to a turn that no longer carries the thread's answer and goes in nowhere, and the
thread goes to the main thread bare, nudged (`_line`). A thread with the session
stays there until the session answers it, and a message after that answer is kept
back again.

Each way out of a line turn is one every agent turn already has: closing it, which
writes the session's agent turns that the watch's reading stamps
(`served_state.reading`), and nudges a session no watch follows (`_hand_over`), or
opens the working fork's turn in its place (`_take`); or lapsing, a `STARTING_GRACE`
after it opened, since nothing renews a line turn, which the reading's
`next_transition_at` names. A line turn that has ended keeps nothing: its `held`
pickup leaves the thread's messages to whoever owes them now, and the next turn
opened drops its entry (`state.open_agent_turn`). The lane only says, at admission,
that a follower runs to list the line turn for the module; its line fork runs in the
module, so the follower exiting or being killed ends nothing that was listed.

The user chose to hold a kept-back message this way, by the line turn's pickup in the
log as a working fork holds its thread, over a hold of its own: a line holder the
reading gives each thread admitted since the lane came up, a record outside the log
of the messages each line fork handed over, and a bound the follower enforces with a
nudge. Such a hold is a second answer to which turn holds a thread, kept partly
outside the log, so every reader that asks the log would have to ask it too. The
user accepted three rare paths with it:

- A message in a working fork's last moments, which its run never carries, goes to
  the main thread as the run ends rather than to the same fork resumed, since Leaf
  decides whether to keep a message back only as it admits it.
- An agent turn whose start nothing confirms, a working fork's included, lapses after
  `activity.STARTING_GRACE`, which bounds a line turn too.
- A line turn that lapses nudges no one, so an idle session no watch follows finds
  the message at its next prompt.

The lane is the session's pages follower (`hooks.cmd_pages`) while it holds the
lease at `lane_path`: the follower lists a report for each kept-back thread (`look`,
`listed`), whose answer is the line fork's question (`ask`), and the line fork's answer
is routed (`route`), each a step of the instructions the module carries (`step`,
`carrier.py`). Python writes the prompt (`line_prompt`) and decides each step; the
module makes the fork and names the tool calls the session is running, which the line
fork can't see: its last request predates them.

The prompt carries the thread whole, as the user asked, where a delivery to the
session carries a long thread's opening and latest messages and leaves the middle
to `leaf page state` (`thread_context.SHOWN`). The fork can't run that, and the
conversation it inherits may have lost the middle to a compaction, so a bounded
thread would leave it judging a long thread's newest message without the
discussion it continues. Each fork's prompt grows with its thread, so a thread's
forks together grow with its square, which stays small while threads run to
tens of messages.

Leaf may ask for more forks of the conversation at the same moment, beside the line
fork (`ask`'s `beside`), each for a duty the line fork's moment suits, such as
summarizing a long thread's earlier discussion (`summary_fork`). The module makes
each at once and hands its answer back with the basis Leaf gave it, and Leaf writes
what it answered by the duty the basis names (`BESIDE`). Each fork answers on its
own, so none holds back the line or the thread's handover, and a new duty needs
only its module and its entry in `BESIDE`, with no change to the module.

The line goes in as the agent's own (`thread.post_reply` with the claim's identity),
acting in the line turn, so it writes nothing once the turn has closed or lapsed
(`_line_runs`) or another turn holds the thread (`holding.refuse_unheld`). The
page's diagnostics (`interaction_log`) note why admission kept each thread message
to a Claude Code session from the main thread, kept back or held by a running agent
turn, and where neither, whether its lane was up (`fork_admission`); each question as Leaf gives it to the module (`fork_asked`), so a
line fork that never answers shows; and every outcome of a thread's forks
(`fork_outcome`): the line fork's, with its tokens and time, why Leaf refused its
line where it did, and the request
it resent (`request` in `hooks/claude-code.ts`, which says where a replay cuts the
conversation: to `sent` while `running` lists a call, else to `row`; its
`effort` is the fork's), as the clerk's `turn_end_check` notes have it, which is
what a later replay or audit scores; and a working fork's start and end (`step`).
`leaf-dev logs timeline` reads them beside the session's transcript.
`leaf-dev eval run 'line-fork*' --harness claude-code --base` scores a change to the
line fork's prompt on a short constructed conversation for each kind of message
(`dev/leaf_dev/fork_eval.py`).
"""

import json
import shlex
from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from . import summary_fork
from .holding import (
    Hold,
    Holding,
    holder,
    not_awaited,
    owed_by,
    reading_of,
)
from .leases import lease_speaks_here, take_wait_lease
from .registry.kernel import kinds_declaring
from .service import PageTransaction, owned_pages
from .state import (
    agent_turn_stamps,
    agent_turns,
    close_agent_turns,
    name_agent_turn,
    now_iso,
    open_agent_turn,
    open_agent_turns,
    session_file,
)

# The words that open the line fork's question, which the transcript carries, and
# the working fork's task.
LINE_OPENING = "<leaf-line-fork>"
WORK_OPENING = "<leaf-fork-work>"
# How a fork that took the work ends when the work belongs with the session after all.
HAND_BACK = "HAND BACK:"

# What a line fork answers (`line_prompt`): the agent's working line, and whether a fork
# of the session could do the work beside it (`take`) or the work belongs with the
# session (`hand_over`). Leaf records the judgment and acts on it (`route`).
ANSWER = {
    "type": "object",
    "properties": {
        "line": {"type": "string", "minLength": 1, "pattern": r"\S"},
        "work": {"enum": ["take", "hand_over"]},
    },
    "required": ["line", "work"],
    "additionalProperties": False,
}


# What Leaf does with the answer of each fork it makes beside a line fork, by the
# duty its basis names (`ask`'s `beside`).
BESIDE = {"summary": summary_fork.take_answer}


class KeptBack(NamedTuple):
    """A thread a line turn holds: its id, its waiting messages in log order, the
    last of which owes the answer, and the line turn."""

    thread: str
    inputs: tuple[str, ...]
    turn: str

    def basis(self, page_dir: Path) -> dict:
        """The thread as the module carries it between `ask` and `route`."""
        return {
            "page": str(page_dir),
            "thread": self.thread,
            "inputs": list(self.inputs),
            "turn": self.turn,
        }


def listed(kept: KeptBack, page_dir: Path) -> dict:
    """The instruction the pages follower lists for the kept-back thread `kept`: a
    report, whose answer is its line fork (`step`)."""
    return {
        "id": f"line:{kept.turn}",
        "do": "report",
        "basis": {"kind": "line", "thread": kept.basis(page_dir)},
    }


def lane_path(session_id: str) -> Path:
    return session_file(session_id, "fork-lane")


def take_lane(session_id: str):
    """Hold the session's lane, which tells admission that a follower runs to list
    each line turn it opens for the module (`kept_from_main_at_admission`)."""
    return take_wait_lease(lane_path(session_id), supersede=True)


def lane_up(session_id: str) -> bool:
    """Whether a follower holds the session's lane."""
    return lease_speaks_here(lane_path(session_id))


def _line_turn(hold: Hold) -> str | None:
    """The running line turn that holds the thread `hold` names, which owes its
    answer now (`holding.owed_by`), or None."""
    return hold.turn if owed_by(hold.holder)["kind"] == "line" else None


def kept_back(page: PageTransaction) -> list[KeptBack]:
    """The page's threads a running line turn holds (the module header's table), by
    the page's reading (`page_holding`)."""
    held = page_holding(page)
    return [
        KeptBack(thread, tuple(event["id"] for event in said), turn)
        for thread, said in held.found.waiting.items()
        if (turn := _line_turn(held.threads[thread])) is not None
    ]


def _keeps(holding: Holding, thread: str, event: dict) -> bool:
    """Whether the message `event`, just admitted in `thread`, opens a line turn: it
    is the thread's only waiting message, so a message already with the session, or a
    user's rewrite, stays with whoever holds it, and no running agent turn took the
    thread, by a pickup or an answer (`holding.Holding.took`), so one fork works a
    thread at a time."""
    worked = {taken for turn in holding.running for taken in holding.took.get(turn, ())}
    waiting = holding.found.waiting.get(thread, ())
    return thread not in worked and [said["id"] for said in waiting] == [event["id"]]


def page_holding(page: PageTransaction, threads: dict | None = None) -> Holding:
    """Who holds each thread of `page`, the one reading every rule asks
    (`holding.py`), from its log, its threads as the fold builds them with the
    page's containment (`events.build_threads`), and its claim
    (`holding.reading_of`, given the claim's facts as a presence reading carries
    them): its session, which is live while the claim is active, and its agent
    turns. `threads` are those an earlier reading in this transaction built, where
    only the session's agent turns have changed since, as when admission replaces a
    line turn, which spares the fold of the log."""
    from .events import build_threads
    from .revision_artifact import active_enclosing

    if threads is None:
        threads = build_threads(page.events, active_enclosing(page.page_dir))
    claim = page.claim
    return reading_of(
        page.events,
        {
            "claim_session": claim["id"] if claim is not None else None,
            "agent_turns": agent_turn_stamps(claim, page.events) if claim else {},
            "session_alive": page.active_claim is not None
            if claim is not None
            else None,
        },
        now_iso(),
        threads,
    )


def kept_from_main_at_admission(page: PageTransaction, event: dict) -> bool:
    """Whether the input `event`, just admitted, is one the main thread doesn't owe
    (`holding.owed_by`), which keeps it from the main thread's deliveries: one in a
    thread a running agent turn holds, a working fork's or a line turn's, or, while
    a Claude Code session's lane is up, a thread message in a thread `_keeps` gives
    a line turn, or any event that joins the waiting turns of a thread a running
    line turn holds, which this replaces; for such an event it opens a line turn
    and records its pickup of the thread's waiting turns. The page's reading this takes once serves both the decision and the
    pickup's (`delivery.record_pickup`), since admission is on the path of every
    message the user sends. For a thread message to a Claude Code session, or an
    event that replaces a line turn, the page's diagnostics note why (`fork_admission`): kept back, held by a running
    agent turn (`held_by`), or neither, with whether the session's lane was up,
    which is what says why no fork took a message up."""
    from .delivery import record_pickup

    holding = page_holding(page)
    held = holding.of(event["id"])
    owes = owed_by(held.holder)
    claim = page.active_claim
    if claim is None or claim["harness"] != "claude-code":
        return owes["kind"] != "main"
    message = event["kind"] in kinds_declaring("message")
    thread = holding.found.names.get(event["id"])
    replaced = None if thread is None else _line_turn(holding.hold(thread))
    # A line fork answers the thread's waiting turns as they stood when its turn
    # opened, so any event that joins them, whatever its kind (a further message or
    # a rewrite), replaces its turn.
    joins = replaced is not None and any(
        said["id"] == event["id"] for said in holding.found.waiting.get(thread, ())
    )
    lane = (message or joins) and lane_up(claim["id"])
    turn = None
    if (
        lane
        and thread is not None
        and (joins or (message and _keeps(holding, thread, event)))
    ):
        if replaced is not None:
            # The line fork writing about the thread's earlier messages would answer
            # without this one, so a new line turn takes them all and the old one's
            # answer drops (`_line_runs`).
            close_agent_turns(claim["id"], turn=replaced)
        turn = open_agent_turn(claim["id"], "line")
        if turn is not None:
            # Admission's reading predates the new line turn, which
            # `holding.pickable` then reads as the main thread's: both may take only
            # what no running agent turn holds, as `_keeps` found of this thread. A
            # replaced line turn still runs in that reading, so the pickup reads the
            # session's turns again, though not the log's fold.
            record_pickup(
                page,
                holding.found.waiting[thread],
                phase="held",
                session=claim["id"],
                turn=turn,
                holding=holding
                if replaced is None
                else page_holding(page, holding.found.threads),
            )
    if message or joins:
        note(
            page.page_dir,
            {
                "type": "fork_admission",
                "session": claim["id"],
                "event": event["id"],
                "kept_back": turn is not None,
                "held_by": held.turn if owes["kind"] != "main" else None,
                "lane": lane,
            },
        )
    return turn is not None or owes["kind"] != "main"


def _line_runs(session_id: str, turn: str) -> bool:
    """Whether `turn` is a running line turn of the session: open, a line fork's, and
    not lapsed (`activity.agent_turn_end`). Each step of a line fork asks this first
    (`ask`, `route`), so a stale step writes nothing and closes nothing: one a module
    reloaded mid-fork repeats after the turn's take or hand-over closed it, or one
    that comes after the turn lapsed, whose message is the main thread's."""
    from .activity import agent_turn_end

    stamp = open_agent_turns(session_id).get(turn)
    return (
        stamp is not None
        and stamp["role"] == "line"
        and datetime.now().astimezone() < agent_turn_end(stamp)
    )


def _line_holds(page: PageTransaction, session_id: str, basis: dict) -> bool:
    """Whether the line turn `basis` names still holds its thread as a running line
    turn, while the page is `session_id`'s: a session the page has left must write
    nothing on it."""
    claim = page.active_claim
    if claim is None or claim["id"] != session_id:
        return False
    return _line_turn(page_holding(page).hold(basis["thread"])) == basis["turn"]


def look(session_id: str, page_dir: Path) -> list[KeptBack]:
    """The page's kept-back threads for the lane's holder to list, while the page is
    its session's."""
    with PageTransaction(page_dir) as page:
        claim = page.active_claim
        return kept_back(page) if claim and claim["id"] == session_id else []


def step(session_id: str, payload: dict) -> dict | None:
    """Leaf's answer to the module's report of one of a thread's instructions
    (`carrier.step`), by its basis's `kind`. For a kept-back thread (`line`), the
    follower's report asks the line fork's question (`ask`), with the forks to make
    beside it, and the line fork's answer, or a failed step, is routed (`route`), giving
    the work to a working fork where the fork judged `take`: a new fork
    of the conversation with the session's tools, spawned unnamed for the reason this
    module's header gives, or the fork that answered the thread before, resumed by a
    send to its agent id. For a fork beside it (`beside`), Leaf writes what it
    answered by the duty its basis names (`BESIDE`). For a working fork (`work`), the
    module's first report says which agent runs the fork's turn (`started`), and one
    with `ended` or `failed` closes the turn (`ended`), naming the agent where one
    started."""
    from .carrier import fork

    basis = payload["basis"]
    kind = basis["kind"]
    if kind == "beside":
        outcome = BESIDE[basis["duty"]](
            session_id,
            basis,
            answer=payload.get("answer"),
            failed=payload.get("failed"),
            usage=payload.get("usage"),
            elapsed_ms=payload.get("elapsed_ms"),
            request=payload.get("resent"),
        )
        duty, thread = basis["duty"], basis["thread"]
        log = f"the {duty} fork for thread {thread}: {outcome['outcome']}"
        return {**outcome, "log": log}
    if kind == "work":
        if "ended" in payload or "failed" in payload:
            run = payload.get("ended") or {"failed": payload["failed"]}
            ended(
                session_id,
                agent=payload.get("agent"),
                turn=basis["turn"],
                answer=run.get("answer"),
                failed=run.get("failed"),
                elapsed_ms=payload.get("elapsed_ms"),
            )
        else:
            started(session_id, basis["thread"], basis["turn"], payload["agent"])
        return None
    thread = basis["thread"]
    if payload["do"] == "report" and "failed" not in payload:
        running = payload.get("running") or []
        question = ask(session_id, thread, running)
        if question is None:
            return None
        turn = thread["turn"]
        forked = {"kind": "line", "thread": thread, "running": running}
        return {
            "do": [
                fork(f"fork:{turn}", question["prompt"], forked),
                *(
                    fork(
                        f"{beside['basis']['duty']}:{turn}",
                        beside["prompt"],
                        {"kind": "beside", **beside["basis"]},
                    )
                    for beside in question.get("beside", [])
                ),
            ]
        }
    outcome = route(
        session_id,
        thread,
        answer=payload.get("answer"),
        failed=payload.get("failed"),
        usage=payload.get("usage"),
        elapsed_ms=payload.get("elapsed_ms"),
        # The calls the line fork's prompt named, which a failed report lacks.
        running=basis["running"]
        if "running" in basis
        else payload.get("running") or [],
        request=payload.get("resent"),
    )
    log = f"the line fork for thread {thread['thread']}: {outcome['outcome']}"
    if outcome["outcome"] != "take":
        return {**outcome, "log": log}
    work = {
        "id": f"work:{outcome['turn']}",
        "basis": {"kind": "work", "thread": thread, "turn": outcome["turn"]},
    }
    return {
        **{name: value for name, value in outcome.items() if name != "prompt"},
        "do": [
            {
                **work,
                "do": "send",
                "request": {
                    "to": {"agentId": outcome["resume"]},
                    "text": outcome["prompt"],
                },
            }
            if "resume" in outcome
            else {
                **work,
                "do": "spawn",
                "request": {
                    "prompt": outcome["prompt"],
                    "subagentType": "fork",
                    "description": f"Leaf: {outcome['text']}",
                },
            }
        ],
        "log": log,
    }


def ask(session_id: str, basis: dict, running: list[dict]) -> dict | None:
    """What to fork the conversation with for the thread `basis` names, as
    `{"prompt", "thread"}`, with `beside` listing the forks to make beside it, each
    `{"prompt", "basis"}`, where any is due; or None once its line turn no longer
    runs (`_line_runs`), or no longer holds the thread or the page is no longer the
    session's, which ends the turn."""
    if not _line_runs(session_id, basis["turn"]):
        return None
    page_dir = Path(basis["page"])
    try:
        with PageTransaction(page_dir) as page:
            if not _line_holds(page, session_id, basis):
                close_agent_turns(session_id, turn=basis["turn"])
                return None
            data = _thread_data(page, basis["inputs"])
            beside = [
                fork
                for fork in ([summary_fork.ask(page, data, basis)] if data else [])
                if fork is not None
            ]
    except FileNotFoundError:
        return None
    if data is None:
        # Only the session can settle what owes no reply in the thread.
        _hand_over(session_id, basis, "the message owes no reply")
        return None
    note(
        page_dir,
        {
            "type": "fork_asked",
            "session": session_id,
            "thread": basis["thread"],
            "inputs": basis["inputs"],
            "running": [call["tool"] for call in running],
        },
    )
    return {
        "prompt": line_prompt(data, running),
        "thread": basis,
        **({"beside": beside} if beside else {}),
    }


def _thread_data(page: PageTransaction, inputs: list[str]) -> dict | None:
    """The thread's waiting messages `inputs` as Leaf delivers them
    (`delivery.batch_data`), with the thread whole, or None where the newest owes
    no reply."""
    from .delivery import batch_data, current_responses

    responses = current_responses(page.page_dir, page.events)
    owed = responses.get(inputs[-1])
    if owed is None or owed["kind"] != "reply":
        return None
    by_id = {event["id"]: event for event in page.events}
    return batch_data(
        page.page_dir,
        page,
        [by_id[i] for i in inputs],
        responses=responses,
        whole=True,
    )


def thread_json(data: dict) -> str:
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


def line_prompt(data: dict, running: list[dict]) -> str:
    """The one message a fork answers: what it is for, the thread as Leaf would
    deliver it (`delivery.batch_data`) but whole, and what the session is running."""
    return f"""{LINE_OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to acknowledge them at once while the main session carries on. The main session takes the message from here and does what it asks. Every tool call is denied here, so don't call tools, and reply straight away without thinking it over. {_running_line(running)}

The whole thread, as Leaf delivers it; "events" are the user's messages, oldest first:
{thread_json(data)}

Leaf posts your line in the thread at once as the agent's working line, until the main session's own words replace it. Write that one line: what the agent will do about the message, in a few of the user's words, as the agent would before starting ("reading the reconnect traces"; "recording your choice and making that change"). Leave the answer to the main session, even where the conversation above holds it.

Then judge who should do what the message asks. "take": a fork of the session with the session's tools could do it start to finish beside the main session: it changes nothing the main session works on (its files and branch, the page's source, its pull requests), settles no question the main session is weighing, and waits on nothing the session has under way, such as a command it is running or a change it has started and not finished. Reading, a lookup, or research that writes only its own scratch files is such work, in the session's files and the page's source too. "hand_over": it belongs with the main session.

Reply with this JSON alone: {{"line": "<the line>", "work": "take" or "hand_over"}}
</leaf-line-fork>"""


def work_prompt(delivery: dict, turn: str) -> str:
    """The task of the fork that does a thread's work: what it is for, the delivery
    of the thread Leaf recorded as its turn's (`_take`), the turn `turn` each of its
    `leaf` commands names, which is how Leaf tells them from the main thread's
    (`state.acting_agent_turn`), and the three ways it ends: an answer, an answer
    that opens a to-do for work bigger than a message, which the main thread
    schedules, or `HAND_BACK` for a message the main thread has to act on now
    (`docs/how-it-works.html`, "The main thread stays in charge")."""
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to do what the message asks beside the main session, which carries on with its own work and leaves this thread to you. You have the session's tools. Change nothing the main session is changing or about to change: its files and branch, the page's source, its pull requests.

Leaf's delivery of the thread to you; "events" are the user's messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Do the work, then answer the user in the thread yourself, as the session would, with the `leaf thread reply` the delivery's `answer` names. Leaf runs your work in a turn of its own, {turn}. Begin every `leaf` command you run with `leaf --turn {turn}`, as in `leaf --turn {turn} thread reply …`. Leaf takes a command as yours only where it names your turn; one without it acts as the main session's. Leaf hands you anything else the user writes in the thread at your next tool call, and your answer then goes to their newest message.

If the work proves bigger than a message, such as a change to the session's files, branch, page or pull requests, or research long enough to need progress of its own, do what you can without changing those, then answer with what you found and add `--todo "<the rest of the work, in a few words>"` to that reply. The to-do is the session's: the main session takes it up in its own order, after its current work. If instead the main session has to act on the message now, because it answers a question the session asked, steers its current work, or would settle a question it is weighing, don't answer: end your turn with "{HAND_BACK}" and one line saying why, and Leaf gives the thread to the main session. Leaf tells the main session what you did either way.
</leaf-fork-work>"""


def resume_prompt(delivery: dict, turn: str) -> str:
    """The message that resumes the fork that answered a thread, for the user's
    further messages in it (`_take`): what Leaf gives it, its new turn `turn`, which
    its `leaf` commands name in place of the one its transcript names, that it reads
    the page's state for what the rest of the session did there since its last turn,
    which its transcript lacks, and the delivery Leaf recorded as its new turn's. The
    fork's first task (`work_prompt`) stays in its transcript, so this repeats only
    how it answers."""
    page = shlex.quote(delivery["batches"][0]["page"])
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user wrote again in the thread you answered, and Leaf gives it to you in a new turn of your own, {turn}, in place of your last one: begin every `leaf` command you run from now on with `leaf --turn {turn}`. Your transcript lacks what the rest of the session has done on the page since your last turn, so read where the page stands with `leaf --turn {turn} page state {page}` before you answer.

Leaf's delivery of the thread to you; "events" are the user's new messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Answer as before: do the work, then reply with `leaf --turn {turn} thread reply` and the reference the delivery's `answer` names, adding `--todo` where the rest of the work is bigger than a message; or, if the main session has to act on the message now, end your turn with "{HAND_BACK}" and one line saying why.
</leaf-fork-work>"""


def route(
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
    """Route a kept-back thread by its line fork's answer: post the line as the
    agent's working line and hand the thread to the session, or, where the line fork
    judged the work a fork's (`take`), give the thread to a working fork (`_take`);
    or hand it over bare where the line fork failed (`failed`, its reason) or its
    answer doesn't fit `ANSWER`; or do nothing where the line turn no longer runs
    (`_line_runs`). What came of it, with
    the fork's judgment of who should do the work (`work`), is recorded in the page's
    diagnostics."""
    from .clerk import read_answer
    from .refusals import Refused

    read = None
    if answer is not None:
        try:
            read = read_answer(answer, ANSWER)
        except Refused as error:
            failed = str(error)
    if not _line_runs(session_id, basis["turn"]):
        outcome = {
            "outcome": "dropped",
            "why": "its line turn no longer runs",
            **(
                {"text": read["line"].strip(), "work": read["work"]}
                if read is not None
                else {}
            ),
        }
    elif read is None:
        outcome = _hand_over(
            session_id, basis, f"the fork failed: {failed or 'no answer'}"
        )
    elif read["work"] == "take":
        outcome = {**_take(session_id, basis, read["line"].strip()), "work": "take"}
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
            **({"request": request} if request else {}),
        },
    )
    return outcome


def _record(session_id: str, basis: dict, outcome: dict) -> None:
    """Note what came of a kept-back thread in its page's diagnostics."""
    note(
        Path(basis["page"]),
        {
            "type": "fork_outcome",
            "session": session_id,
            "thread": basis["thread"],
            "inputs": basis["inputs"],
            **outcome,
        },
    )


def note(page_dir: Path, record: dict) -> None:
    """Append `record` to the page's diagnostics, dropped where the page can't be
    written, as every diagnostic is (`interaction_log`)."""
    from .interaction_log import append_interactions

    try:
        append_interactions(page_dir, [{"source": "cli", **record}])
    except OSError:
        pass


def _post(session_id: str, basis: dict, text: str) -> dict:
    """The line fork's working line, posted as the agent's in its line turn, and the
    thread handed to the session after it; or why nothing was."""
    posted = _line(session_id, basis, text)
    if "line" not in posted:
        return posted
    return {**_hand_over(session_id, basis, None), **posted}


def _line(session_id: str, basis: dict, text: str) -> dict:
    """Post `text` as the agent's working line in the line turn `basis` names, which
    `route` found running: `{"text", "line"}` with the posted message's id, or the
    outcome where Leaf posted nothing, which ends the turn."""
    from .delivery import ReceiptRefused
    from .findings import Rejected
    from .refusals import Refused
    from .state import acting_in
    from .thread import Receipt, post_reply

    try:
        with acting_in(basis["turn"]):
            record = post_reply(
                Path(basis["page"]),
                {"responds": basis["inputs"][-1]},
                text,
                settlement=Receipt(),
                claimed_session=session_id,
                ephemeral=True,
            )
    except (FileNotFoundError, ReceiptRefused):
        close_agent_turns(session_id, turn=basis["turn"])
        return {"outcome": "dropped", "text": text}
    except (Rejected, Refused) as error:
        if not _line_runs(session_id, basis["turn"]):
            # An event that joined the thread replaced the line turn as the line
            # went in, so the line is stale, as `route` finds of a later step.
            why = "its line turn no longer runs"
            return {"outcome": "dropped", "why": why, "text": text}
        # The message's own checks refused it, so the thread goes to the session
        # bare, and the note says why.
        why = f"the message was refused: {error}"
        return {**_hand_over(session_id, basis, why), "text": text, "refused": why}
    if record is None:
        # The message the line responds to owes no reply now, as when a newer one in
        # the thread carries its answer, so the thread goes to the session bare.
        why = "the line's message owes no reply now"
        return {**_hand_over(session_id, basis, why), "text": text}
    return {"text": text, "line": record["id"]}


def _resumable(
    holding: Holding, claim: dict, session_id: str, thread: str
) -> str | None:
    """The agent id of the fork whose turn gave `thread`'s last answer, the turn the
    answer names (`thread.post_reply`), which Leaf gives the thread's waiting
    messages to again. A message the main thread wrote in the thread unasked, such
    as a correction of the fork's answer, answers nothing, so the thread stays the
    fork's. None where the main thread answered last, or the
    fork's turn still runs or was opened in an earlier generation of the session,
    whose agents ended with it, or the fork runs another turn, as one resumed for a
    message the user then took back does, since an agent runs one turn at a time
    (`state.agent_turn_of`). `holding` is the page's, and `claim` its active claim."""
    from .state import agent_turn_of, agent_turns

    answer = holding.found.answers.get(thread)
    if answer is None or "turn" not in answer:
        return None
    turn = answer["turn"]
    entry = agent_turns(session_id).get(turn)
    if (
        entry is None
        or entry["agent"] is None
        or entry["closed"] is None
        or entry["generation"] != claim["generation"]
        or agent_turn_of(session_id, entry["agent"]) is not None
    ):
        return None
    return entry["agent"]


def _take(session_id: str, basis: dict, line: str) -> dict:
    """Post the line fork's working line and give the thread to a working fork: close
    the line turn, open the fork's own turn (`state.open_agent_turn`) and record that
    turn's pickup of the thread's waiting messages, with their references and
    receipt, from a delivery frozen for it, all in one page transaction, so no other
    turn takes the thread between them. Returns `{"outcome": "take", "turn",
    "prompt"}`, the fork's turn and its task carrying that delivery, which the module
    spawns it with.

    Where a fork's turn gave the thread's last answer and has closed (`_resumable`),
    the new turn runs under that fork's agent id from its opening, unconfirmed, and
    the outcome adds `resume`, that id, and its `prompt` is the message that resumes
    it (`resume_prompt`), so one fork works the thread however many messages the user
    sends it; a resume that fails ends the turn (`ended`), which gives the thread to
    the main thread. A new fork has no id until the module has spawned it
    (`started`). Either way the module confirms the start once the fork runs
    (`started`), which tells the main session which fork has the thread; a turn whose
    start nothing confirms lapses a `STARTING_GRACE` after the take
    (`activity.agent_turn_end`)."""
    from .delivery import batch_refs, freeze_delivery, receive_passed, record_pickup
    from .presence import nudge_unwatched

    page_dir = Path(basis["page"])
    line_turn = basis["turn"]
    posted = _line(session_id, basis, line)
    if "line" not in posted:
        return posted
    try:
        with PageTransaction(page_dir) as page:
            holding = page_holding(page)
            if _line_turn(holding.hold(basis["thread"])) != line_turn:
                # The line turn no longer holds the thread: another turn took it
                # since the line went in, as the main thread's answer does, or the
                # line turn lapsed meanwhile.
                close_agent_turns(session_id, turn=line_turn)
                return {"outcome": "dropped", **posted}
            data = _thread_data(page, basis["inputs"])
            if data is None:
                # Only the session can settle what owes no reply in the thread.
                close_agent_turns(session_id, turn=line_turn)
                nudge_unwatched(page)
                return {"outcome": "hand_over", **posted}
            claim = page.active_claim
            assert claim is not None
            resumed = _resumable(holding, claim, session_id, basis["thread"])
            # A closed line turn's `held` pickup keeps nothing, so the fork's own
            # pickup takes the thread (`holding.pickable`), read after the close.
            close_agent_turns(session_id, turn=line_turn)
            turn = open_agent_turn(session_id, "fork", resumed)
            if turn is None:
                return {"outcome": "dropped", **posted}
            delivery = freeze_delivery([data])
            by_id = {event["id"]: event for event in page.events}
            record_pickup(
                page,
                [by_id[input_id] for input_id in basis["inputs"]],
                session=session_id,
                turn=turn,
                refs=batch_refs(delivery["batches"][0]),
            )
            receive_passed(page, not_awaited(page_holding(page)))
    except FileNotFoundError:
        return {"outcome": "dropped", **posted}
    return {
        "outcome": "take",
        **posted,
        "turn": turn,
        **(
            {"prompt": work_prompt(delivery, turn)}
            if resumed is None
            else {"prompt": resume_prompt(delivery, turn), "resume": resumed}
        ),
    }


def _given(session_id: str, basis: dict, turn: str, agent: str) -> None:
    """Tell the main session that Leaf gave the thread `basis` names to the fork
    `agent`, in the turn `turn`, by the agent id it reaches the fork by (the module
    header), so it leaves the thread to the fork and can steer or stop it
    (`clerk.queue`). A line it hasn't heard by the turn's end leaves the queue
    (`ended`)."""
    from .clerk import queue

    queue(
        session_id,
        [
            f"Leaf gave the user's message in thread {basis['thread']} on "
            f"{basis['page']} to a fork of this conversation, agent id {agent}, which "
            "is doing what it asks beside you and will answer there; Leaf tells you "
            "when it has. Leave that thread to it; to steer or stop it, SendMessage "
            f"{agent}. An answer of your own there takes the thread from it."
        ],
        turn=turn,
    )


def started(session_id: str, basis: dict, turn: str, agent: str) -> dict:
    """Record that the agent its harness names `agent` runs the fork turn `turn`
    Leaf opened for the thread `basis` names (`state.name_agent_turn`), so its tool
    boundaries carry the thread's further messages and its turn is believed for the
    working grace, and tell the main session which fork has the thread (`_given`):
    the fork the module spawned, whose id Leaf learns only now, or resumed, once the
    module has sent it the thread's messages. A turn that ended first, as its
    session's may have, is left closed, and the main session hears of it only by
    that end (`ended`); the fork's commands naming it are refused
    (`state.acting_agent_turn`)."""
    named = name_agent_turn(session_id, turn, agent)
    if named:
        _given(session_id, basis, turn, agent)
    outcome = {
        "step": "start",
        "outcome": "start" if named else "dropped",
        "agent": agent,
        "turn": turn,
    }
    _record(session_id, basis, outcome)
    return outcome


# What came of a thread an agent's turn took, as `ended` judges it once the turn's
# run ends.
Ending = Literal["answer", "todo", "hand_back", "taken_over", "resolved"]


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
    harness names `agent`, or `turn`, and say what came of each thread it took,
    judged by the messages the turn picked up itself and what the turn wrote
    (`holding.py`): a message still waiting that the closed turn holds means it gave
    the thread back (`hand_back`), as its last words did (`HAND_BACK`), it failed
    (`failed`) or it ended without answering, and the main thread owes it now
    (`activity.agent_holds`); otherwise a message another turn holds or answered
    means that turn took the thread over (`taken_over`); otherwise the turn answered
    every one (`answer`), and opened a to-do on the thread with a reply of its own
    that is still open (`todo`), which the main thread now owes and schedules
    (`todos`). A message the user took back counts for nothing, and so does one in
    a thread the user resolved, which owes nothing and ends as `resolved`. The main session
    hears of an answer, a to-do or a thread given back (`clerk.queue`), and that the
    thread owes nothing only where nothing waits in it and no to-do on it is open;
    the take's line, if it hasn't heard it yet, leaves the queue (`clerk.unqueue`).
    A thread given back is the main thread's input again, which its next delivery
    hands over (`delivery.deliverable`). An idle session is woken for what it
    now owes: the watch wakes it for that input, and for a to-do, whose line wakes it
    (`clerk.waking`); a session no watch follows is nudged for either. The page's
    diagnostics note each outcome, with who took a thread taken over; the outcomes,
    one for each thread. An agent with no open turn, as most of a session's are,
    ends nothing."""
    from .clerk import queue, unqueue
    from .presence import nudge_unwatched
    from .todos import TodoReading

    closed = set(close_agent_turns(session_id, turn=turn, agent=agent))
    if not closed:
        return []
    unqueue(session_id, closed)
    # The agent that ran the closed turns, all of one agent's, by the id the main
    # session reaches it by; None for a fork whose harness never started it.
    entries = agent_turns(session_id)
    [ran] = {entries[closing]["agent"] for closing in closed}
    fork = "Your fork" if ran is None else f"Your fork {ran}"
    text = (answer or "").strip()
    why = (
        text.removeprefix(HAND_BACK).strip()
        if text.startswith(HAND_BACK)
        else f"the fork failed: {failed}"
        if failed
        else "the fork ended without answering"
    )
    elapsed = {} if elapsed_ms is None else {"elapsedMs": elapsed_ms}
    outcomes = []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim is None or claim["id"] != session_id:
                    continue
                # Read after the close, so the closed turn holds only what it
                # picked up.
                holding = page_holding(page)
                found = holding.found
                # The ids of the replies the closed turn wrote.
                own = {e["id"] for e in page.events if e.get("turn") in closed}
                owed = TodoReading(page.events).owed
                # What came of each thread on the page, what the main session hears
                # of it, and the lines that tell it of a to-do it now owes, which
                # wake it while it is idle.
                here, told, wakes = [], [], []
                # The messages the closed turn picked up, by thread.
                taken: dict[str, dict[str, None]] = {}
                for turn in closed:
                    for input_id in holding.picked.get(turn, {}):
                        if (thread := found.names.get(input_id)) is not None:
                            taken.setdefault(thread, {})[input_id] = None
                for thread, picked in taken.items():
                    keepers = {i: holding.keeper(i) for i in picked}
                    settled = {
                        i: answer
                        for i in picked
                        if keepers[i] is None
                        and (answer := found.answer_to(i)) is not None
                    }
                    inputs = [
                        i for i in picked if keepers[i] is not None or i in settled
                    ]
                    outcome: dict
                    if not inputs:
                        # A thread the user resolved, or a choice's answer closed,
                        # owes nothing, which ends the fork's work on it; one the
                        # user took back is gone.
                        if (found.threads.get(thread) or {}).get("resolved") is None:
                            continue
                        outcome = {"outcome": "resolved"}
                        _record(
                            session_id,
                            {
                                "page": str(page_dir),
                                "thread": thread,
                                "inputs": list(picked),
                            },
                            {"step": "end", "agent": ran, **outcome, **elapsed},
                        )
                        here.append(
                            {"page": str(page_dir), "thread": thread, **outcome}
                        )
                        continue
                    subject = {"kind": "thread", "id": thread}
                    owing = [t for t in owed if t["subject"] == subject]
                    todos = [t for t in owing if t["id"] in own]
                    answered = [settled[i] for i in inputs if i in settled]
                    ending: Ending = (
                        "hand_back"
                        if any(keepers[i] in closed for i in inputs)
                        else "taken_over"
                        if len(answered) < len(inputs)
                        or any(answer["id"] not in own for answer in answered)
                        else "todo"
                        if todos
                        else "answer"
                    )
                    outcome = {"outcome": ending}
                    if ending == "taken_over":
                        outcome["why"] = _taken_by(
                            {keepers[i] for i in inputs if keepers[i] is not None}
                            | {a.get("turn") for a in answered if a["id"] not in own},
                            holding,
                        )
                    elif ending == "hand_back":
                        outcome["why"] = why
                        told.append(
                            f"{fork} gave thread {thread} on {page_dir} back to "
                            f"you, which now owes the user its answer: {why}"
                        )
                    elif ending != "taken_over":
                        if todos:
                            outcome["todos"] = [t["id"] for t in todos]
                        (wakes if todos else told).append(
                            _answered(
                                fork,
                                f"thread {thread} on {page_dir}",
                                todos,
                                owing=bool(owing),
                                waiting=bool(found.waiting.get(thread)),
                            )
                        )
                    _record(
                        session_id,
                        {"page": str(page_dir), "thread": thread, "inputs": inputs},
                        {"step": "end", "agent": ran, **outcome, **elapsed},
                    )
                    here.append({"page": str(page_dir), "thread": thread, **outcome})
                queue(session_id, told)
                queue(session_id, wakes, wake=True)
                # After the lines are queued, so the turn a nudge starts hears them.
                if {"hand_back", "todo"} & {item["outcome"] for item in here}:
                    nudge_unwatched(page)
                outcomes.extend(here)
        except FileNotFoundError:
            continue
    return outcomes


def _taken_by(turns: set, holding: Holding) -> str:
    """Why a fork's thread ended as `taken_over`: which turns took it, the main
    thread, a line turn, or another run of a fork, by its agent id
    (`holding.holder`), by the page's `holding`, as the page's diagnostics note it."""
    named = {turn: holder(turn, holding.stamps, holding.running) for turn in turns}
    takers = sorted(
        "the main thread"
        if named[turn]["kind"] == "main"
        else f"line turn {turn}"
        if named[turn]["kind"] == "line"
        else f"fork {named[turn]['agent'] or 'not yet started'}'s turn {turn}"
        for turn in turns
    )
    return f"{' and '.join(dict.fromkeys(takers))} took the thread"


def _answered(
    fork: str, where: str, todos: list[dict], *, owing: bool, waiting: bool
) -> str:
    """The line telling the main session that its fork, as `fork` names it, answered
    the user's message in the thread `where` names, and opened `todos` there, which
    the session now owes; and that the thread owes nothing, unless the user has
    written there since (`waiting`) or a to-do on it is open (`owing`)."""
    listed = " and ".join(f"the to-do “{t['title']}” ({t['id']})" for t in todos)
    return (
        f"{fork} answered the user's message in {where}"
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
            "; the user has written there since, which Leaf passes on as any new "
            "message."
            if waiting
            else "; otherwise the thread owes nothing."
            if not owing
            else "."
        )
    )


def _hand_over(session_id: str, basis: dict, why: str | None) -> dict:
    """Hand the thread `basis` names to the session by ending its line turn, which
    leaves the thread's waiting messages the main thread's (`holding.owed_by`), and
    nudge a session no watch follows, as admission would have; `why` is Leaf's
    reason, where the fork didn't choose it."""
    from .presence import nudge_unwatched

    reason = {} if why is None else {"why": why}
    try:
        with PageTransaction(Path(basis["page"])) as page:
            if not close_agent_turns(session_id, turn=basis["turn"]):
                return {"outcome": "dropped", **reason}
            nudge_unwatched(page)
    except FileNotFoundError:
        return {"outcome": "dropped", **reason}
    return {"outcome": "hand_over", **reason}
