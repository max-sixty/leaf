"""Forks of a Claude Code session's conversation that answer the user's thread
messages: a line fork, which posts the agent's working line on a thread's waiting
messages at once and sorts them, and, with `LEAF_FORK_WORK=on` in Claude Code's
environment while the design is tried, a working fork with the session's tools, which
does a thread's work and answers it. Both run only in Claude Code, from Leaf's hooks
module (`hooks/claude-code.ts`). `docs/forks.html` is the design's home, diagrams
included; this header holds the rules this module keeps and the choices behind them,
and `holding.py` the rule for which turn holds a message.

On real pages the session's answer to a thread message is slow, slower when it is
busy, and the thread shows nothing from the agent after a message until the
session's first model call ends (`notes/fork-replies.md`, "Forks on real pages").
`$.model.fork` resends the session's last request with one more message, at any
moment, mid-command too, and a fork decides in a few seconds. The user had the fork
post only the agent's working line and always hand over, rather than answer or hand
over: a line fork can't call tools (`$.model.fork` denies every one),
and answering is left to a fork that can act. The line fork also judges whether a
working fork could do the work beside the session (`ANSWER`'s `work`): `take` gives
the thread to one, where the module makes them (`_take`), and otherwise Leaf records
the judgment and hands the thread over.

A thread's waiting messages are the user's messages the agent still owes an answer
in it while it stands open (`holding.rounds`). Each thread with
waiting messages is in one of these states, which `kept_back` and `holding.py`
compute from the page's log, the session's hand-overs (`HANDED`), its agents' turns
and the forks' lane; nothing stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| kept back | Leaf keeps the thread's waiting messages from the main thread while a line fork writes its line | a user message in a thread none of whose waiting messages any turn has picked up or the lane has handed over, and which no running fork turn took, while the session's lane is live and has been since the first of them arrived |
| taken | a working fork does the work in a turn of its own, which picked the messages up and holds the thread until another turn takes it (`holding.py`) | the line fork judging `take`, where the module makes working forks (`_take`) |
| with the session | delivered as any input is | a hand-over: the line posted, a failed line fork, or the lane's once `BOUND_S` has passed since the newest waiting message (`look`); the lane going down; a working fork's turn ending with the thread unanswered (`ended`); or the main thread's answer taking the thread from a working fork |

A working fork runs a turn of its own (`state.AGENT_TURNS`), which Leaf opens at the
take: named with the fork's agent id at once for a fork it resumes, and once the
module says which agent it spawned for a new one (`started`). Leaf records
the take as that turn's pickup of the thread's waiting messages, with their receipt,
fenced to the thread still being kept back, so the messages go from kept back to held
with no moment in which neither has them. As the fork's run ends the module says so
(`ended`), which closes the turn and judges each thread by what the turn picked up
and wrote. The main session hears which fork took a thread once the module says the
fork runs (`started`): as it says which agent it spawned for a new one, and once it
has delivered a resumed one's message; and it hears as the fork's run ends
(`clerk.queue`), since Claude Code tells it nothing of a fork a module made. The user
chose these lines over the fork's own SendMessage to the main thread,
which would wake it for every answer (`docs/forks.html`, "How a fork tells the main
thread"). A line waits for the session's next tool boundary or prompt, and Leaf wakes
an idle session only for what a fork's end leaves it owing: a thread given back,
whose answer is owed again, and a to-do the fork opened, whose line wakes it
(`ended`).

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
nothing by a name after `claude --resume` (2.1.325, `notes/fork-replies.md`). So the
module spawns each fork unnamed, leaving the main session no second address that
could move.

The user chose that one fork works a thread. While a fork's turn runs,
its thread's further messages are its own, and Leaf keeps none back for another
(`kept_back`). A later message the line fork judges `take`, in a thread whose last
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
straight away without thinking it over, since every second it takes keeps the
thread's messages from the session; a fork at another effort can cost a rewrite of
the conversation to the cache (`runFork` in `hooks/claude-code.ts` says when). A fork
at `low` writes lines as good as xhigh's (`notes/fork-replies.md`, "How well the fork
judges") and skips the occasional line xhigh spends seconds thinking over, while a
fork at xhigh asked to reply straight away passes the eval's cases as well as a low
one.

Another message while the thread is kept back keeps it back, with a line fork for the
new set, and drops the earlier line fork's line (`route`); a thread with the session
stays there until the session answers it, and a message after that answer is kept
back again. Kept-back input is not `delivery.deliverable`, which the hooks, the watch
and its nudges read, and admission doesn't nudge for it (`event_endpoint`), since
keeping it back has to start before the watch would wake the session.

Each way out of keeping a thread back but the lane going down is a write the
session's waiters already read, made under the page's lock: a hand-over in `HANDED`,
which the watch's reading stamps (`served_state.reading`), and it nudges a session no
watch follows, as admission would have. So the bound is the lane's to keep, for every
page the session holds, and the state needs no clock. The lane going down writes
nothing, so the page's presence reading names the lane (`presence.live_facts`), and a
tab showing On it for a kept-back message re-reads within the reading's cache
interval. Since the lane's lease decides when keeping back ends, the state stays
outside the page log, while a take, which says which turn holds a message, is a
pickup in it (`docs/forks.html`, "The path of one thread message").

The lane is the session's pages follower (`hooks.cmd_pages`) while it holds the
lease at `lane_path`: the follower prints each kept-back thread with the session's
pages (`look`), and the module asks a line fork about each one (`ask`), then hands
its answer back (`route`). Python writes the prompt (`line_prompt`); the module only
carries it and the line, and names the tool calls the session is running, which the
line fork can't see: its last request predates them. A lane keeps back only what
arrived while it ran, so a thread the lane going down gave to the session stays
there when the next lane comes up, and a line fork of the old lane's writes nothing.
A follower that gives up the lane with a thread kept back, as one exiting or finding
a newer follower holding it does, then nudges what it kept back, as a watch does when
it gives up its lease (`session.nudge_pending`); one killed outright nudges nothing,
so after Escape, with no watch, its messages wait for the page's next change.

The line goes in as the agent's own (`thread.post_reply` with the claim's identity),
fenced to the thread being kept back: it writes nothing once the thread is no longer
kept back as the line fork was asked it, checked under the lock the append takes. The
page's diagnostics (`interaction_log`) note why admission kept each thread message
to a Claude Code session from the main thread, kept back or held by a running fork
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
import time
from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple

from .holding import (
    Holding,
    holder,
    not_awaited,
    owed_by,
    reading_of,
)
from .leases import lease_speaks_here, release_lease, take_wait_lease
from .registry.kernel import kinds_declaring
from .service import PageTransaction, owned_pages
from .state import (
    STRING,
    Record,
    agent_turn_stamps,
    agent_turns,
    close_agent_turns,
    described,
    flocked,
    name_agent_turn,
    now_iso,
    object_schema,
    open_agent_turn,
    page_key,
    session_file,
    session_lock_path,
)

# How long Leaf keeps a thread's waiting messages back from the session, counted
# from the newest one's admission, before the lane hands them to it whatever the line
# fork does (`look`). Forks on real pages decided in a median 3 s.
BOUND_S = 30.0

HANDED = Record(
    "forks",
    described(
        "The thread messages a fork of a Claude Code session's conversation handed "
        "to the session, in the state home's `sessions/<digest>.forks` "
        "(`state.session_file`): for each page, by `state.page_key`, the ids of the "
        "messages it handed over that no pickup has taken in yet (`forks`).",
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

# The words that open the line fork's question, which the transcript carries, and
# the working fork's task.
LINE_OPENING = "<leaf-line-fork>"
WORK_OPENING = "<leaf-fork-work>"
# How a fork that took the work ends when the work belongs with the session after all.
HAND_BACK = "HAND BACK:"

# What a line fork answers (`line_prompt`): the agent's working line, and whether a fork
# of the session could do the work beside it (`take`) or the work belongs with the
# session (`hand_over`). Leaf records the judgment, and acts on `take` where the module
# makes working forks (`route`).
ANSWER = {
    "type": "object",
    "properties": {
        "line": {"type": "string", "minLength": 1, "pattern": r"\S"},
        "work": {"enum": ["take", "hand_over"]},
    },
    "required": ["line", "work"],
    "additionalProperties": False,
}


class KeptBack(NamedTuple):
    """A thread whose waiting messages Leaf keeps back: its id, those messages in
    log order, the last of which owes the answer, and when the lane hands them to the
    session (POSIX seconds)."""

    thread: str
    inputs: tuple[str, ...]
    until: float

    def basis(self, page_dir: Path) -> dict:
        """The thread as the module carries it between `ask` and `route`."""
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
    handed = HANDED.read(session_file(session_id, HANDED.kind))
    return set((handed or {"handed": {}})["handed"].get(page_key(page_dir), []))


def kept_back(page: PageTransaction, holding: Holding | None = None) -> list[KeptBack]:
    """The page's threads whose waiting messages Leaf keeps back (the module
    header's table), by when the lane hands each over: those the line fork holds in
    the page's reading (`page_holding`, or `holding` where the caller has it), which
    derived them (`kept_back_of`)."""
    held = page_holding(page) if holding is None else holding
    found = [
        KeptBack(
            thread,
            tuple(event["id"] for event in said),
            _admitted(said[-1]) + BOUND_S,
        )
        for thread, said in held.found.waiting.items()
        if held.threads[thread].holder["kind"] == "line"
    ]
    return sorted(found, key=lambda thread: thread.until)


def kept_back_of(holding: Holding, since: float, handed: set[str]) -> set[str]:
    """The threads Leaf keeps back on a page whose reading by its pickups and
    answers is `holding`, for a lane of the claimant's line forks that came up at
    `since` and has `handed` over the messages it lists (`HANDED`). The reading
    derives them as it reads who holds each thread (`holding.reading_of`), from the
    log alone, never the page's fold, since admission, every hook and every served
    reading ask it, and `ask` hands over a message the fold says owes none.

    It reads which messages any pickup names or the lane handed over
    (`holding.Holding.taken`), not the page's cursor, which a receipt moves past a
    message Leaf keeps back as the main thread takes in the input after it
    (`holding.not_awaited`). A thread a running agent turn took, by a pickup or an
    answer, is never kept back for another fork (`holding.Holding.took`), so one
    fork works a thread at a time: its further messages go to that turn, which holds
    them, or to the main thread where it took the thread over (`holding.py`). A
    thread where the user's rewrite of a message waits stays with whoever holds
    it."""
    worked = {
        thread for turn in holding.running for thread in holding.took.get(turn, ())
    }
    messages = kinds_declaring("message")
    return {
        thread
        for thread, said in holding.found.waiting.items()
        # A lane keeps back only what arrived while it ran, so a thread the lane
        # going down gave to the session never comes back with the next lane; a
        # message in the lane's own first millisecond may have come first, so it stays
        # with the session.
        if _admitted(said[0]) > since
        and thread not in worked
        and all(
            event["kind"] in messages
            and event["id"] not in holding.taken
            and event["id"] not in handed
            for event in said
        )
    }


def page_holding(page: PageTransaction) -> Holding:
    """Who holds each thread of `page`, the one reading every rule asks
    (`holding.py`), from its log, its threads as the fold builds them with the
    page's containment (`events.build_threads`), and its claim
    (`holding.reading_of`, given the claim's facts as a presence reading carries
    them): its session, which is live while the claim is active, its agent turns,
    and its lane of line forks and what they handed over, with each thread Leaf
    keeps back held by the line fork."""
    from .events import build_threads
    from .revision_artifact import active_enclosing

    claim = page.claim
    active = page.active_claim
    return reading_of(
        page.events,
        {
            "claim_session": claim["id"] if claim is not None else None,
            "agent_turns": agent_turn_stamps(claim, page.events) if claim else {},
            "session_alive": active is not None if claim is not None else None,
            "fork_lane": lane_since(active["id"]) if active else None,
            "handed": sorted(handed_inputs(active["id"], page.page_dir))
            if active
            else [],
        },
        now_iso(),
        build_threads(page.events, active_enclosing(page.page_dir)),
    )


def kept_from_main_at_admission(page: PageTransaction, event: dict) -> bool:
    """Whether the input `event`, just admitted, is one the main thread doesn't owe
    (`holding.owed_by`), which keeps it from the main thread's deliveries: one in a
    thread Leaf keeps back for a line fork (`kept_back`) or a running fork holds. For
    a thread message to a Claude Code session, the page's diagnostics note why
    (`fork_admission`): kept back, held by a running fork's turn (`held_by`), or
    neither, with whether the session's lane was up, which is what says why no fork
    took a message up."""
    held = page_holding(page).of(event["id"])
    owes = owed_by(held.holder)
    claim = page.active_claim
    if (
        claim is not None
        and claim["harness"] == "claude-code"
        and event["kind"] in kinds_declaring("message")
    ):
        _note(
            page.page_dir,
            {
                "type": "fork_admission",
                "session": claim["id"],
                "event": event["id"],
                "kept_back": owes["kind"] == "line",
                "held_by": held.turn if owes["kind"] == "fork" else None,
                "lane": lane_since(claim["id"]),
            },
        )
    return owes["kind"] != "main"


def _still_kept_back(
    page: PageTransaction, session_id: str, basis: dict, holding: Holding | None = None
) -> bool:
    """Whether the thread `basis` names is still the line fork's with the waiting
    messages `basis` has, by the page's reading (`page_holding`, or `holding` where
    the caller has it), while the page is `session_id`'s: a session the page has left
    must write nothing on it."""
    claim = page.active_claim
    if claim is None or claim["id"] != session_id:
        return False
    held = page_holding(page) if holding is None else holding
    return (
        held.hold(basis["thread"]).holder["kind"] == "line"
        and [event["id"] for event in held.found.waiting.get(basis["thread"], ())]
        == basis["inputs"]
    )


def look(
    session_id: str, page_dir: Path, *, now: float | None = None
) -> list[KeptBack]:
    """The page's kept-back threads for the lane's holder to fork, while the page is
    its session's, after handing to the session each one whose `BOUND_S` has passed,
    whatever its line fork is doing. `now` defaults to the clock."""
    now = time.time() if now is None else now
    with PageTransaction(page_dir) as page:
        claim = page.active_claim
        threads = kept_back(page) if claim and claim["id"] == session_id else []
        due = [thread for thread in threads if thread.until <= now]
        for thread in due:
            _hand_over_kept_back(page, session_id, thread.inputs)
    for thread in due:
        _record(
            session_id,
            thread.basis(page_dir),
            {"outcome": "hand_over", "why": f"no answer within {BOUND_S:g} s"},
        )
    return [thread for thread in threads if thread.until > now]


def cmd_fork(session_id: str, payload: dict) -> dict | None:
    """One step of a thread's forks, as `leaf hook --fork` hands it over: with the
    kept-back thread in `payload["thread"]` and without `answer` or `failed`, the line
    fork's question (`ask`); with one, what Leaf did with the line fork's answer
    (`route`), giving the work to a working fork where `work_forks` asks for that. The module then says which agent its
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
        return route(
            session_id,
            basis,
            answer=payload.get("answer"),
            failed=payload.get("failed"),
            usage=payload.get("usage"),
            elapsed_ms=payload.get("elapsed_ms"),
            running=payload.get("running") or [],
            request=payload.get("request"),
            work_forks=bool(payload.get("work_forks")),
        )
    return ask(session_id, basis, payload.get("running") or [])


def ask(session_id: str, basis: dict, running: list[dict]) -> dict | None:
    """What to fork the conversation with for the thread `basis` names, as
    `{"prompt", "thread"}`, or None once the thread is no longer kept back as
    `basis` has it, or the page no longer the session's."""
    page_dir = Path(basis["page"])
    try:
        with PageTransaction(page_dir) as page:
            if not _still_kept_back(page, session_id, basis):
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
    return {"prompt": line_prompt(data, running), "thread": basis}


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


def line_prompt(data: dict, running: list[dict]) -> str:
    """The one message a fork answers: what it is for, the thread as Leaf would
    deliver it (`delivery.batch_data`) and what the session is running."""
    return f"""{LINE_OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, made to acknowledge them at once while the main session carries on. The main session takes the message from here and does what it asks. Every tool call is denied here, so don't call tools, and reply straight away without thinking it over. {_running_line(running)}

The thread, as Leaf delivers it; "events" are the user's messages, oldest first:
{_thread_json(data)}

Leaf posts your line in the thread at once as the agent's working line, until the main session's own words replace it. Write that one line: what the agent will do about the message, in a few of the user's words, as the agent would before starting ("reading the reconnect traces"; "recording your choice and making that change"). Leave the answer to the main session, even where the conversation above holds it.

Then judge who should do what the message asks. "take": a fork of the session with the session's tools could do it start to finish beside the main session, because it needs nothing the main session is changing or about to change (its files and branch, the page's source, its pull requests), settles no question the main session is weighing, and waits on nothing the session is running; answering from reading, a lookup, or research that writes only its own scratch files are such work. "hand_over": it belongs with the main session.

Reply with this JSON alone: {{"line": "<the line>", "work": "take" or "hand_over"}}
</leaf-line-fork>"""


def work_prompt(delivery: dict, turn: str) -> str:
    """The task of the fork that does a thread's work: what it is for, the delivery
    of the thread Leaf recorded as its turn's (`_take`), the turn `turn` each of its
    `leaf` commands names, which is how Leaf tells them from the main thread's
    (`state.acting_agent_turn`), and the three ways it ends: an answer, an answer
    that opens a to-do for work bigger than a message, which the main thread
    schedules, or `HAND_BACK` for a message the main thread has to act on now
    (`docs/forks.html`, "To-dos")."""
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
    work_forks: bool = False,
) -> dict:
    """Route a kept-back thread by its line fork's answer: post the line as the
    agent's working line and hand the thread to the session, or, where the line fork
    judged the work a fork's (`take`) and the module makes such forks (`work_forks`),
    give the thread to a working fork (`_take`); or hand it over bare where the line
    fork failed (`failed`, its reason) or its answer doesn't fit `ANSWER`. What
    came of it, with the fork's judgment of who should do the work (`work`), is
    recorded in the page's diagnostics."""
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
    _note(
        Path(basis["page"]),
        {
            "type": "fork_outcome",
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
    """The line fork's working line, posted as the agent's while the thread is still
    kept back as `basis` has it, and the thread handed to the session after it; or why
    nothing was."""
    posted = _line(session_id, basis, text)
    if "line" not in posted:
        return posted
    return {**_hand_over(session_id, basis, None), **posted}


def _line(session_id: str, basis: dict, text: str) -> dict:
    """Post `text` as the agent's working line, while the thread is still kept back
    as `basis` has it: `{"text", "line"}` with the posted message's id, or the
    outcome where Leaf posted nothing."""
    from .delivery import ReceiptRefused
    from .findings import Rejected
    from .refusals import Refused
    from .thread import Receipt, post_reply

    try:
        record = post_reply(
            Path(basis["page"]),
            {"responds": basis["inputs"][-1]},
            text,
            settlement=Receipt(
                fence=lambda page: _still_kept_back(page, session_id, basis)
            ),
            claimed_session=session_id,
            ephemeral=True,
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
    """Post the line fork's working line and give the thread to a working fork:
    fenced to the thread still being kept back, open a turn for it
    (`state.open_agent_turn`) and record that turn's pickup of the thread's waiting
    messages, with their receipt, from a delivery frozen for it. Returns
    `{"outcome": "take", "turn", "prompt"}`, the fork's turn and its task carrying
    that delivery, which the module spawns it with.

    Where a fork's turn gave the thread's last answer and has closed (`_resumable`),
    the outcome adds `resume`, that fork's agent id, which runs the new turn from
    its opening, and its `prompt` is the message that resumes it (`resume_prompt`),
    so one fork works the thread however many messages the user sends it; a resume
    that fails ends the turn (`ended`), which gives the thread to the main thread.
    A new fork has no id until the module has spawned it, and its turn no agent runs
    until the module says which agent that is (`started`). Either way the module
    confirms the start once the fork runs (`started`), which tells the main session
    which fork has the thread; a turn whose start nothing confirms lapses within a
    minute (`activity.agent_turn_end`)."""
    from .delivery import batch_refs, freeze_delivery, receive_passed, record_pickup

    page_dir = Path(basis["page"])
    posted = _line(session_id, basis, line)
    if "line" not in posted:
        return posted
    try:
        with PageTransaction(page_dir) as page:
            holding = page_holding(page)
            if not _still_kept_back(page, session_id, basis, holding):
                return {"outcome": "dropped", **posted}
            data = _thread_data(page, basis["inputs"])
            if data is None:
                # Only the session can settle what owes no reply in the thread.
                _hand_over_kept_back(page, session_id, basis["inputs"])
                return {"outcome": "hand_over", **posted}
            claim = page.active_claim
            assert claim is not None
            resumed = _resumable(holding, claim, session_id, basis["thread"])
            turn = open_agent_turn(session_id, resumed)
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
    thread or another run of a fork, by its agent id (`holding.holder`), by the
    page's `holding`, as the page's diagnostics note it."""
    takers = sorted(
        "the main thread"
        if (named := holder(turn, holding.stamps, holding.running))["kind"] == "main"
        else f"fork {named['agent'] or 'not yet started'}'s turn {turn}"
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
    """Hand the thread `basis` names to the session, while it is still kept back as
    `basis` has it (`_hand_over_kept_back`); `why` is Leaf's reason, where the fork
    didn't choose it."""
    reason = {} if why is None else {"why": why}
    try:
        with PageTransaction(Path(basis["page"])) as page:
            if not _still_kept_back(page, session_id, basis):
                return {"outcome": "dropped", **reason}
            _hand_over_kept_back(page, session_id, basis["inputs"])
    except FileNotFoundError:
        return {"outcome": "dropped", **reason}
    return {"outcome": "hand_over", **reason}


def _hand_over_kept_back(page: PageTransaction, session_id: str, inputs) -> None:
    """Record in `HANDED` that the kept-back messages `inputs` go to the session, keeping
    of those handed over before only the ids that still wait with no pickup naming
    them, by the page's reading (`page_holding`): one a turn took in, or that settled
    first, as when the user resolved its thread, goes. Nudge a session no watch
    follows, as admission would have."""
    from .presence import nudge_unwatched

    held = page_holding(page)
    owed = {
        event["id"]
        for said in held.found.waiting.values()
        for event in said
        if event["id"] not in held.taken
    }
    path = session_file(session_id, HANDED.kind)
    key = page_key(page.page_dir)
    with flocked(session_lock_path(session_id), deadline=page.deadline):
        record = HANDED.read(path) or {"handed": {}}
        kept = [i for i in record["handed"].get(key, []) if i in owed]
        record["handed"][key] = list(dict.fromkeys([*kept, *inputs]))
        HANDED.write(path, record)
    nudge_unwatched(page)
