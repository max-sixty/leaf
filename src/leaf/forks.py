"""The line fork: a fork of a Claude Code session's conversation that posts the
agent's working line on a thread's waiting messages at once. It runs in every Claude
Code session, and only there, from Leaf's hooks module (`hooks/claude-code.ts`). How
it works' Forks tab (`docs/how-it-works.html`) explains the design, diagrams
included; this header holds the rules this module keeps and the choices behind them,
and `holding.py` the rule for which turn holds a message.

On a real page the session's answer to a thread message takes tens of seconds, longer
when it is busy, and the thread shows nothing from the agent after a message until the
session's first model call ends (`notes/fork-replies.md`, "Forks on real pages").
`$.model.fork` resends the session's last request with one more message, at any moment,
mid-command too, and a fork decides in seconds. The user had the fork post only
the agent's working line and hand the thread on, rather than answer it: a line
fork can't call tools (`$.model.fork` denies every one), and answering is left to
an agent that can act. Leaf posts the line and hands the thread to the main session
(`_post`), which routes every message: it answers the message itself, gives it to a
new fork of its conversation, a subagent that answers in the thread, or passes it to
the fork already answering that thread (`references/harness-claude-code.md`,
"Subagents").

The user chose that the main session judge every message this way. The line fork
could also judge whether a fork of the session could do the work beside it and tell
the session so, but that only adds a line to what the session reads, and the session
decides anyway, knowing its own work better than a fork judging from a snapshot of
it. What the user accepted with that choice: nothing marks which messages could run
beside the session, so how often it delegates rests on its own judgment. The main
session holds every thread, so one turn holds each and Leaf keeps no record of a
fork's own: no turn, holder, hand-back or end. Claude Code tells the session as a
subagent ends, waking an idle session, so the subagent's report reaches its context.
The distributed approach a later change might reach for is Leaf spawning the fork
itself (`$.agent.spawn`) and sending it the thread's later messages. Its answer comes
sooner, since it waits neither for the main session's next tool call nor on a main
session blocked in a long command; but Leaf would need its own judgment of which
messages to give a fork, and it puts a second holder on each thread it gives one, and
with it the turns, records and hooks that hold a thread for an agent Leaf spawned and
tell the main session what that agent did, since Claude Code tells a session nothing
of an agent a plugin spawned.

A thread's waiting messages are the user's messages the agent still owes an answer
in it while it stands open (`holding.rounds`). Each thread with
waiting messages is in one of these states, which `holding.py` reads from the page's
log and its session's agent turns; nothing stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| kept back | a running line turn holds the thread's waiting messages while a line fork writes its line | while the session's lane is up, a user message that is its thread's only waiting message, or any event that joins the waiting turns of a thread a running line turn holds, which it replaces: admission opens the line turn and records its pickup of the thread's waiting messages (`kept_from_main_at_admission`) |
| with the session | delivered as any input is | the line turn ending: the line posted, a failed line fork, or the line turn lapsing (`activity.STARTING_GRACE`); or the main thread's answer taking the thread |

Each thread message Leaf keeps back opens an agent turn of its own
(`state.AGENT_TURNS`), the line turn, whose pickup of the thread's waiting messages
admission records in the transaction that appends the message, so the watch never
sees the message unheld and admission doesn't nudge for it (`event_endpoint`). That
pickup is `held` (`delivery.record_pickup`): it holds the thread as any pickup does,
but takes nothing in, so no reader of delivery counts it, and the message reads as
sent to the session until a turn opens it. `holding.holder` reports a line turn as
`line`, so no reader infers it from what the turn wrote. Each step of a line fork
acts only while its turn runs (`_line_runs`), so a stale step, as a module reloaded
mid-fork repeats, or one whose turn a later message replaced, writes nothing.

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

A line turn ends by closing, which writes the session's agent turns that the watch's
reading stamps (`served_state.reading`) and nudges a session no watch follows
(`_hand_over`), or by lapsing, a `STARTING_GRACE` after it opened, since nothing
renews a line turn, which the reading's `next_transition_at` names. A line turn that
has ended keeps nothing: its `held` pickup leaves the thread's messages to the main
thread, and the next turn opened drops its entry (`state.open_agent_turn`). The lane
only says, at admission, that a follower runs to list the line turn for the module;
its line fork runs in the module, so the follower exiting or being killed ends
nothing that was listed.

The user chose to hold a kept-back message this way, by the line turn's pickup in the
log, over a hold of its own: a line holder the reading gives each thread admitted
since the lane came up, a record outside the log of the messages each line fork
handed over, and a bound the follower enforces with a nudge. Such a hold is a second
answer to which turn holds a thread, kept partly outside the log, so every reader
that asks the log would have to ask it too. A line turn that lapses nudges no one, so
an idle session no watch follows finds the message at its next prompt.

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
to a Claude Code session from the main thread, kept back or held by a running line
turn, and where neither, whether its lane was up (`fork_admission`); each question as
Leaf gives it to the module (`fork_asked`), so a line fork that never answers shows;
and every outcome of a thread's line fork (`fork_outcome`), with its tokens and time, why Leaf refused its line where it did, and what it
resent of the main thread's conversation (`resends` in `hooks/claude-code.ts`, which
says where a replay cuts it; its `effort` is the fork's), as the clerk's
`turn_end_check` notes have it, which is what a later replay or audit scores.
`leaf-dev logs timeline` reads them beside the session's transcript.
`leaf-dev eval run 'line-fork*' --harness claude-code --base` scores a change to the
line fork's prompt on a short constructed conversation for each kind of message
(`dev/leaf_dev/fork_eval.py`).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from . import summary_fork
from .holding import Hold, Holding, reading_of
from .json_block import json_block
from .leases import lease_speaks_here, take_wait_lease
from .registry.kernel import kinds_declaring
from .service import PageTransaction
from .state import (
    agent_turn_stamps,
    close_agent_turns,
    now_iso,
    open_agent_turn,
    open_agent_turns,
    session_file,
)

# The words that open the line fork's question, which the transcript carries.
LINE_OPENING = "<leaf-line-fork>"

# What a line fork answers (`line_prompt`): the agent's working line, which Leaf posts
# (`route`).
ANSWER = {
    "type": "object",
    "properties": {
        "line": {"type": "string", "minLength": 1, "pattern": r"\S"},
    },
    "required": ["line"],
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
    answer now (`holding.holder`), or None."""
    return hold.turn if hold.holder["kind"] == "line" else None


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
    user's rewrite, stays with whoever holds it."""
    waiting = holding.found.waiting.get(thread, ())
    return [said["id"] for said in waiting] == [event["id"]]


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
            "agent_turns": agent_turn_stamps(claim) if claim else {},
            "session_alive": page.active_claim is not None
            if claim is not None
            else None,
        },
        now_iso(),
        threads,
    )


def kept_from_main_at_admission(page: PageTransaction, event: dict) -> bool:
    """Whether the input `event`, just admitted, is one the main thread doesn't owe
    (`holding.holder`), which keeps it from the main thread's deliveries: one in a
    thread a running line turn holds, or, while a Claude Code session's lane is up, a
    thread message in a thread `_keeps` gives a line turn, or any event that joins the
    waiting turns of a thread a running line turn holds, which this replaces; for
    such an event it opens a line turn and records its pickup of the thread's waiting
    turns. The page's reading this takes once serves both the decision and the
    pickup's (`delivery.record_pickup`), since admission is on the path of every
    message the user sends. For a thread message to a Claude Code session, or an
    event that replaces a line turn, the page's diagnostics note why
    (`fork_admission`): kept back, held by a running line turn (`held_by`), or
    neither, with whether the session's lane was up, which is what says why no line
    fork took a message up."""
    from .delivery import record_pickup

    holding = page_holding(page)
    held = holding.of(event["id"])
    owes = held.holder
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
        turn = open_agent_turn(claim["id"])
        if turn is not None:
            # Admission's reading predates the new line turn, which
            # `holding.pickable` then reads as the main thread's: both may take only
            # what no running line turn holds, as `_keeps` found of this thread. A
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
    """Whether `turn` is a running line turn of the session: open and not lapsed
    (`activity.agent_turn_end`). Each step of a line fork asks this first (`ask`,
    `route`), so a stale step writes nothing and closes nothing: one a module reloaded
    mid-fork repeats after the turn's hand-over closed it, or one that comes after the
    turn lapsed, whose message is the main thread's."""
    from .activity import agent_turn_end

    stamp = open_agent_turns(session_id).get(turn)
    return stamp is not None and datetime.now().astimezone() < agent_turn_end(stamp)


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
    beside it, and the line fork's answer, or a failed step, is routed (`route`). For a
    fork beside it (`beside`), Leaf writes what it answered by the duty its basis names
    (`BESIDE`)."""
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
    return {**outcome, "log": log}


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
    return json_block(
        {
            "page": data["page"],
            "threads": data["threads"],
            "events": [
                {key: value for key, value in event.items() if key != "answer"}
                for event in data["events"]
            ],
        }
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
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds. You are a fork of the session, and Leaf asks you for the working line it posts in the thread at once, saying what the agent will do about the message.

Every tool call is denied here, so don't call tools, and reply straight away without thinking it over.

{_running_line(running)} The whole thread, as Leaf delivers it; "events" are the user's messages, oldest first:

{thread_json(data)}

The line stands in the thread as the agent's until the agent's answer replaces it. Write what the agent will do about the message, in a few of the user's words, as the agent would before starting ("reading the reconnect traces"; "recording your choice and making that change"). Leave the answer out of the line, even where the conversation above holds it.

Reply with this JSON alone: {{"line": "<the line>"}}
</leaf-line-fork>"""


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
    agent's working line and hand the thread to the session (`_post`); or hand it
    over bare where the line fork failed (`failed`, its reason) or its answer doesn't
    fit `ANSWER`; or do nothing where the line turn no longer runs (`_line_runs`).
    What came of it is recorded in the page's diagnostics."""
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
            **({"text": read["line"].strip()} if read is not None else {}),
        }
    elif read is None:
        outcome = _hand_over(
            session_id, basis, f"the fork failed: {failed or 'no answer'}"
        )
    else:
        outcome = _post(session_id, basis, read["line"].strip())
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


def _hand_over(session_id: str, basis: dict, why: str | None) -> dict:
    """Hand the thread `basis` names to the session by ending its line turn, which
    leaves the thread's waiting messages the main thread's (`holding.holder`), and
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
