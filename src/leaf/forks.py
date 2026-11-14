"""Forks of a Claude Code session's conversation that answer the user's thread
messages: a line fork, which posts the agent's working line on a thread's waiting
messages at once and sorts them, and, with `LEAF_FORK_WORK=on` in Claude Code's
environment while the design is tried, a working fork with the session's tools, which
does a thread's work and answers it. Both run only in Claude Code, from Leaf's hooks
module (`hooks/claude-code.ts`). `docs/forks.html` is the design's home, diagrams
included; this header holds the rules this module keeps and the choices behind them,
and `holding.py` the rule for which turn holds a message.

On real pages the session's answer to a thread message took a median 48 s when it
was idle and 100 s when it was busy, and the thread showed nothing from the agent
for a median 35 s after a message, until the session's first model call ended
(`notes/fork-replies.md`, "Forks on real pages"). `$.model.fork` resends the
session's last request with one more message, at any moment, mid-command too, and a
fork decided in a median 3 s. The user chose on 2026-10-31 a fork that answers or
hands over. On 2026-11-05 they had the fork post only the agent's working line,
always handing over: a line fork can't call tools (`$.model.fork` denies every one),
and answering is left to a fork that can act. The line fork also judges whether a
working fork could do the work beside the session (`ANSWER`'s `work`): `take` gives
the thread to one, where the module makes them (`_take`), and otherwise Leaf records
the judgment and hands the thread over.

A thread's waiting messages are the user's messages since the agent's last answer in
it, the newest of which owes the thread's answer (`holding.rounds`). Each thread with
waiting messages is in one of these states, which `kept_back` and `holding.py`
compute from the page's log, the session's hand-overs (`HANDED`), its agents' turns
and the forks' lane; nothing stores the state itself:

| State | Means | Entered by |
| --- | --- | --- |
| kept back | Leaf keeps the thread's waiting messages from the main thread while a line fork writes its line | a user message in a thread none of whose waiting messages the session has received or been handed, and which no running fork turn took, while the session's lane is live and has been since the first of them arrived |
| taken | a working fork does the work in a turn of its own, which picked the messages up and holds the thread until another turn takes it (`holding.py`) | the line fork judging `take`, where the module makes working forks (`_take`) |
| with the session | delivered as any input is | a hand-over: the line posted, a failed line fork, or the lane's once `BOUND_S` has passed since the newest waiting message (`look`); the lane going down; a working fork's turn ending with the thread unanswered (`ended`); or the main thread's answer taking the thread from a working fork |

A working fork runs a turn of its own (`state.AGENT_TURNS`), which Leaf opens at the
take: named with the fork's agent id at once for a fork it resumes, and once the
module says which agent it spawned for a new one (`started`). Leaf records
the take as that turn's pickup of the thread's waiting messages, with their receipt,
fenced to the thread still being kept back, so the messages go from kept back to held
with no moment in which neither has them. The fork's `leaf` commands act in its turn
(`hooks.agent_command`), and as its run ends the module says so (`ended`), which
closes the turn and judges each thread by what the turn picked up and wrote. The main
session hears as a fork takes a thread and as its run ends (`clerk.queue`), since
Claude Code tells it nothing of a fork a module made, and it can steer or stop the
fork by the name Leaf gives it. The user chose these lines on 2026-11-11 over the
fork's own SendMessage to the main thread, which would wake it for every answer
(`docs/forks.html`, "How a fork tells the main thread"). A line waits for the
session's next tool boundary or prompt, and Leaf wakes an idle session only for what
a fork's end leaves it owing: a thread given back, whose answer is owed again, and a
to-do the fork opened, whose line wakes it (`ended`).

The user chose on 2026-11-10 that one fork works a thread. While a fork's turn runs,
its thread's further messages are its own, and Leaf keeps none back for another
(`_kept_back`). A later message the line fork judges `take`, in a thread whose last
answer names a fork's turn that has since closed, goes to that fork again, resumed in
a new turn (`_resumable`), with a message (`resume_prompt`) that tells it to read
the page's state, since its transcript lacks what the rest of the session did there
meanwhile. The user chose on 2026-11-12 that reading over a summary Leaf wrote of it,
and that a thread whose fork can't be resumed goes to the main thread rather than to
a new fork.

The line is the agent's progress message in the thread (`thread.post_reply`), which
the thread shows until the session's own words replace it. From the moment Leaf
starts keeping a thread back, and while the line stands, the thread's waiting
messages read On it (`forked`, which `served_state.work` serves as their workflows'
`at_work`, so every surface showing whether the agent is at work agrees), as the user
chose on 2026-11-05. That word is all the line fork changes: as a receipt's progress
the line takes nothing in hand (`thread.Receipt`), so every reader that ages, nudges
or holds a turn reads the message's delivery. A start would read as the session's
turn, renewing it after an interrupt and holding the message at Working before the
session had it, which hid it from the nudge and the overdue count.

The line fork thinks at the session's own effort, and its prompt asks it to reply
straight away without thinking it over, since every second it takes keeps the
thread's messages from the session. A fork at another effort costs a rewrite of the
conversation to the cache on backends without per-message effort, as the clerk's
header says. From 2026-11-09 to 2026-11-14 it asked for `low`. On the eval's seven
cases on 2026-11-14, a fork at xhigh asked to reply straight away passed 7, against
the low fork's 6, writing 1.49 times its output (95% interval 0.91–2.44) in 1.09
times its time (0.94–1.25). On 2026-11-09 low wrote lines as good as xhigh's. On 40
recorded thread messages, each replayed from its session's transcript
(`notes/fork-replies.md`, "How well the fork judges"), a judge blind to the effort
passed 35 lines at each effort and preferred low's on 19, xhigh's on 16 and neither
on 5; `leaf-dev eval 'line-fork*'` passed 35 of 35 at each over five repeats.
Neither effort thought on the recorded messages, so their output and time matched
there (low wrote 1.03 times the tokens, 95% interval 0.97–1.10). On the eval's short
conversations xhigh thought over 5 of its 35 lines, taking up to 3.5 s where a line
took a median 1 s, and low over none, for 0.85 times xhigh's time (0.75–0.95). So
low removed the occasional line xhigh spent seconds thinking over.

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
`leaf-dev timeline` reads them beside the session's transcript.
`leaf-dev eval 'line-fork*' --harness claude-code --base` scores a change to the
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
    agent_held,
    holding_turns,
    last_taken,
    rounds,
    running_threads,
    running_turns,
    taken_by_agent_turns,
    turn_threads,
)
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


def kept_back(page: PageTransaction) -> list[KeptBack]:
    """The page's threads whose waiting messages Leaf keeps back (the module
    header's table), by when the lane hands them over."""
    return _kept_back(page.page_dir, page.events, page.cursor, page.active_claim)


def forked(
    page_dir: Path, events: list[dict], cursor: int, claim: dict | None
) -> set[str]:
    """The waiting messages a fork has taken on, which read On it
    (`served_state.work`): those Leaf keeps back while the line fork writes its
    line, and those the agent's working line came after, until the session answers.
    `claim` is the page's active claim, as `kept_back` reads it: with none, no fork
    speaks for the page."""
    if claim is None:
        return set()
    threads = rounds(events)
    return {
        event["id"]
        for said in threads.waiting.values()
        for event in said
        if event["id"] in threads.lined
    } | {
        input_id
        for thread in _kept_back(page_dir, events, cursor, claim)
        for input_id in thread.inputs
    }


def _kept_back(
    page_dir: Path, events: list[dict], cursor: int, claim: dict | None
) -> list[KeptBack]:
    """`kept_back`, from the log, its cursor and the page's active claim.

    It reads the log, never the page's fold, which costs about 100 ms, since
    admission, every hook and every served reading ask it: a user's message after
    the agent's last answer in its thread owes the thread's answer, and `ask` hands
    over one the fold says owes none.

    A thread a running agent turn took, by a pickup or an answer, is never kept back
    for another fork (`holding.running_threads`), so one fork works a thread at a
    time: its further messages go to that turn, which holds them, or to the main
    thread where it took the thread over (`holding.py`)."""
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
    waiting = rounds(events).waiting
    running = running_turns(claim)
    worked = running_threads(events, claim["id"], running)
    found = [
        KeptBack(
            thread,
            tuple(event["id"] for event in said),
            _admitted(said[-1]) + BOUND_S,
        )
        for thread, said in waiting.items()
        # A lane keeps back only what arrived while it ran, so a thread the lane
        # going down gave to the session never comes back with the next lane; a
        # message in the lane's own first millisecond may have come first, so it stays
        # with the session.
        if _admitted(said[0]) > since
        and thread not in worked
        and all(
            event["id"] in pending
            and event["id"] not in picked
            and event["id"] not in handed
            for event in said
        )
    ]
    return sorted(found, key=lambda thread: thread.until)


def kept_from_main(page: PageTransaction) -> set:
    """What `delivery.deliverable` keeps from the session's main thread: every
    message Leaf keeps back (`kept_back`), and every one an agent's running turn holds
    (`holding.agent_held`)."""
    return {
        input_id for thread in kept_back(page) for input_id in thread.inputs
    } | agent_held(page)


def kept_from_main_at_admission(page: PageTransaction, event: dict) -> bool:
    """Whether the input `event`, just admitted, is kept from the main thread
    (`kept_from_main`). For a thread message to a Claude Code session, the page's
    diagnostics note why (`fork_admission`): kept back for a line fork
    (`kept_back`), held by a running agent turn (`held_by`, `holding.agent_held`), or
    neither, with whether the session's lane was up, which is what says why no fork
    took a message up."""
    kept = any(event["id"] in thread.inputs for thread in kept_back(page))
    claim = page.active_claim
    held_by = None
    if not kept and claim is not None and event["id"] in agent_held(page):
        held_by = holding_turns(page.events, claim["id"], running_turns(claim)).get(
            event["id"]
        )
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
                "kept_back": kept,
                "held_by": held_by,
                "lane": lane_since(claim["id"]),
            },
        )
    return kept or held_by is not None


def _kept_back_for(page: PageTransaction, session_id: str) -> list[KeptBack]:
    """The page's kept-back threads while it is `session_id`'s, since `kept_back`
    reads the claimant's and a session the page has left must write nothing on it."""
    claim = page.active_claim
    return kept_back(page) if claim is not None and claim["id"] == session_id else []


def _still_kept_back(page: PageTransaction, session_id: str, basis: dict) -> bool:
    return any(
        thread.thread == basis["thread"] and list(thread.inputs) == basis["inputs"]
        for thread in _kept_back_for(page, session_id)
    )


def look(
    session_id: str, page_dir: Path, *, now: float | None = None
) -> list[KeptBack]:
    """The page's kept-back threads for the lane's holder to fork, after handing to
    the session each one whose `BOUND_S` has passed, whatever its line fork is doing.
    `now` defaults to the clock."""
    now = time.time() if now is None else now
    with PageTransaction(page_dir) as page:
        threads = _kept_back_for(page, session_id)
        due = [thread for thread in threads if thread.until <= now]
        for thread in due:
            _hand_over_kept_back(page, session_id, thread.inputs)
        uncarried = _left_by_agent_turns(page, session_id, due)
    for thread in due:
        _record(
            session_id,
            thread.basis(page_dir),
            {
                "outcome": "hand_over",
                "why": "its fork's turn ended before carrying it"
                if thread.thread in uncarried
                else f"no answer within {BOUND_S:g} s",
            },
        )
    return [thread for thread in threads if thread.until > now]


def _left_by_agent_turns(
    page: PageTransaction, session_id: str, threads: list[KeptBack]
) -> set[str]:
    """Which of `threads` an agent turn of the session last took, by a pickup or an
    answer, and ended or lapsed only after the thread's bound had passed: a fork's
    thread whose further messages its turn held past their bound and ended before
    carrying, which Leaf keeps back only once the turn has ended. A message sent
    after the turn ended, or late enough in it that its bound was still running, is
    one a line fork was asked about."""
    from .activity import agent_turn_end

    claim = page.active_claim
    if not threads or claim is None:
        return set()
    stamps = agent_turn_stamps(claim)
    if not stamps:
        return set()
    took = last_taken(page.events, session_id)
    return {
        thread.thread
        for thread in threads
        if (stamp := stamps.get(took.get(thread.thread))) is not None
        and thread.until <= agent_turn_end(stamp).timestamp()
    }


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


def work_prompt(delivery: dict, agent: str) -> str:
    """The task of the fork that does a thread's work: what it is for, the delivery
    of the thread Leaf recorded as its turn's (`_take`), and the three ways it ends:
    an answer, an answer that opens a to-do for work bigger than a message, which the
    main thread schedules, or `HAND_BACK` for a message the main thread has to act on
    now (`docs/forks.html`, "To-dos")."""
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user just wrote in a thread on a Leaf page this session holds, and you are a fork of the session, named {agent}, made to do what the message asks beside the main session, which carries on with its own work and leaves this thread to you. You have the session's tools. Change nothing the main session is changing or about to change: its files and branch, the page's source, its pull requests.

Leaf's delivery of the thread to you; "events" are the user's messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Do the work, then answer the user in the thread yourself, as the session would, with the `leaf thread reply` the delivery's `answer` names. Run each `leaf` command as a Bash call of its own that begins with `leaf` and has no other `leaf` in it, which is how Leaf knows it is yours; give a reply's text with `--text`, or, where the text names a `leaf` command, with `--file` naming a file you wrote first with the Write tool. Leaf hands you anything else the user writes in the thread at your next tool call, and your answer then goes to their newest message.

If the work proves bigger than a message, such as a change to the session's files, branch, page or pull requests, or research long enough to need progress of its own, do what you can without changing those, then answer with what you found and add `--todo "<the rest of the work, in a few words>"` to that reply. The to-do is the session's: the main session takes it up in its own order, after its current work. If instead the main session has to act on the message now, because it answers a question the session asked, steers its current work, or would settle a question it is weighing, don't answer: end your turn with "{HAND_BACK}" and one line saying why, and Leaf gives the thread to the main session. Leaf tells the main session what you did either way.
</leaf-fork-work>"""


def resume_prompt(delivery: dict) -> str:
    """The message that resumes the fork that answered a thread, for the user's
    further messages in it (`_take`): what Leaf gives it, that it reads the page's
    state for what the rest of the session did there since its last turn, which its
    transcript lacks, and the delivery Leaf recorded as its new turn's. The fork's
    first task (`work_prompt`) stays in its transcript, so this repeats only how it
    answers."""
    page = shlex.quote(delivery["batches"][0]["page"])
    return f"""{WORK_OPENING}
This message comes from Leaf, not the user. The user wrote again in the thread you answered, and Leaf gives it to you in a new turn of your own. Your transcript lacks what the rest of the session has done on the page since your last turn, so read where the page stands with `leaf page state {page}` before you answer.

Leaf's delivery of the thread to you; "events" are the user's new messages, oldest first, and the one that owes the thread's answer carries its `answer`:
{json.dumps(delivery, ensure_ascii=False)}

Answer as before: do the work, then reply with the `leaf thread reply` the delivery's `answer` names, run as a Bash call of its own that begins with `leaf` and has no other `leaf` in it, adding `--todo` where the rest of the work is bigger than a message; or, if the main session has to act on the message now, end your turn with "{HAND_BACK}" and one line saying why.
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


def _fork_name(thread: str) -> str:
    """The name Leaf gives the fork that takes `thread`, by which the main session
    reaches it (`SendMessage`)."""
    return f"leaf-{thread}"


def _resumable(page: PageTransaction, session_id: str, thread: str) -> str | None:
    """The agent id of the fork whose turn gave `thread`'s last answer, the turn the
    answer names (`thread.post_reply`), which Leaf gives the thread's waiting
    messages to again. A message the main thread wrote in the thread unasked, such
    as a correction of the fork's answer, answers nothing, so the thread stays the
    fork's. None where the main thread answered last, or the
    fork's turn still runs or was opened in an earlier generation of the session,
    whose agents ended with it, or the fork runs another turn, as one resumed for a
    message the user then took back does, since an agent runs one turn at a time
    (`state.agent_turn_of`)."""
    from .state import agent_turn_of, agent_turns

    claim = page.active_claim
    answer = rounds(page.events).answers.get(thread)
    if claim is None or answer is None or "turn" not in answer:
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
    `{"outcome": "take", "agent", "turn", "prompt"}`, the fork's name, its turn and
    its task carrying that delivery, which the module spawns it with; the main
    session hears which fork has the thread, so it can steer or stop it
    (`clerk.queue`).

    Where a fork's turn gave the thread's last answer and has closed (`_resumable`),
    the outcome adds `resume`, that fork's agent id, which runs the new turn from
    its opening, and its `prompt` is the message that resumes it (`resume_prompt`),
    so one fork works the thread however many messages the user sends it; a resume
    that fails ends the turn (`ended`), which gives the thread to the main thread.
    A new fork's turn no agent runs until the module has spawned it and says which
    agent that is (`started`)."""
    from .clerk import queue
    from .delivery import batch_refs, freeze_delivery, receive_passed, record_pickup

    page_dir = Path(basis["page"])
    agent = _fork_name(basis["thread"])
    posted = _line(session_id, basis, line)
    if "line" not in posted:
        return posted
    try:
        with PageTransaction(page_dir) as page:
            if not _still_kept_back(page, session_id, basis):
                return {"outcome": "dropped", **posted}
            data = _thread_data(page, basis["inputs"])
            if data is None:
                # Only the session can settle what owes no reply in the thread.
                _hand_over_kept_back(page, session_id, basis["inputs"])
                return {"outcome": "hand_over", **posted}
            resumed = _resumable(page, session_id, basis["thread"])
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
            receive_passed(page, taken_by_agent_turns(page))
    except FileNotFoundError:
        return {"outcome": "dropped", **posted}
    queue(
        session_id,
        [
            f"Leaf gave the user's message in thread {basis['thread']} on {page_dir} "
            f"to a fork of this conversation named {agent}, which is doing what it "
            "asks beside you and will answer there; Leaf tells you when it has. Leave "
            f"that thread to it; to steer or stop it, SendMessage {agent}. An answer "
            "of your own there takes the thread from it."
        ],
        turn=turn,
    )
    return {
        "outcome": "take",
        **posted,
        "agent": agent,
        "turn": turn,
        **(
            {"prompt": work_prompt(delivery, agent)}
            if resumed is None
            else {"prompt": resume_prompt(delivery), "resume": resumed}
        ),
    }


def started(session_id: str, basis: dict, turn: str, agent: str) -> dict:
    """Record that the agent its harness names `agent` runs the fork turn `turn`
    Leaf opened for the thread `basis` names (`state.name_agent_turn`), so its
    commands act in that turn and its tool boundaries carry the thread's further
    messages: the fork the module spawned or the one it resumed. A turn that ended first, as its session's may have, is
    left closed: a fork Leaf never named then acts as any subagent of the session
    does, and one it named before, as a resumed fork is, has its commands refused
    (`state.acting_agent_turn`)."""
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


# What came of a thread an agent's turn took, as `ended` judges it once the turn's
# run ends.
Ending = Literal["answer", "todo", "hand_back", "taken_over"]


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
    (`todos`). A message the user took back counts for nothing. The main session
    hears of an answer, a to-do or a thread given back (`clerk.queue`), and that the
    thread owes nothing only where nothing waits in it and no to-do on it is open;
    the take's line, if it hasn't heard it yet, leaves the queue (`clerk.unqueue`).
    A thread given back is the main thread's input again, which its next delivery
    hands over (`holding.left_by_agent_turns`). An idle session is woken for what it
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
                found = rounds(page.events)
                # Read after the close, so the closed turn holds only what it
                # picked up.
                holders = holding_turns(
                    page.events, session_id, running_turns(claim), found
                )
                # The ids of the replies the closed turn wrote.
                own = {e["id"] for e in page.events if e.get("turn") in closed}
                owed = TodoReading(page.events).owed
                # What came of each thread on the page, what the main session hears
                # of it, and the lines that tell it of a to-do it now owes, which
                # wake it while it is idle.
                here, told, wakes = [], [], []
                for thread, picked in turn_threads(
                    page.events, session_id, closed
                ).items():
                    inputs = [i for i in picked if i in holders or i in found.answered]
                    if not inputs:
                        continue
                    name = _fork_name(thread)
                    subject = {"kind": "thread", "id": thread}
                    owing = [t for t in owed if t["subject"] == subject]
                    todos = [t for t in owing if t["id"] in own]
                    answered = [found.answered[i] for i in inputs if i not in holders]
                    ending: Ending = (
                        "hand_back"
                        if any(holders.get(i) in closed for i in inputs)
                        else "taken_over"
                        if len(answered) < len(inputs)
                        or any(answer["id"] not in own for answer in answered)
                        else "todo"
                        if todos
                        else "answer"
                    )
                    outcome: dict = {"outcome": ending}
                    if ending == "taken_over":
                        outcome["why"] = _taken_by(
                            {holders[i] for i in inputs if i in holders}
                            | {a.get("turn") for a in answered if a["id"] not in own},
                            agent_turn_stamps(claim),
                        )
                    elif ending == "hand_back":
                        outcome["why"] = why
                        told.append(
                            f"Your fork {name} gave thread {thread} on {page_dir} "
                            f"back to you, which now owes the user its answer: {why}"
                        )
                    elif ending != "taken_over":
                        if todos:
                            outcome["todos"] = [t["id"] for t in todos]
                        (wakes if todos else told).append(
                            _answered(
                                name,
                                f"thread {thread} on {page_dir}",
                                todos,
                                owing=bool(owing),
                                waiting=bool(found.waiting.get(thread)),
                            )
                        )
                    _record(
                        session_id,
                        {"page": str(page_dir), "thread": thread, "inputs": inputs},
                        {"step": "end", "agent": name, **outcome, **elapsed},
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


def _taken_by(turns: set, agents: dict) -> str:
    """Why a fork's thread ended as `taken_over`: which turns took it, the main
    thread's or another agent's (`agents`, the session's agent turns), as the page's
    diagnostics note it."""
    takers = sorted(
        f"agent turn {turn}" if turn in agents else "the main thread" for turn in turns
    )
    return f"{' and '.join(dict.fromkeys(takers))} took the thread"


def _answered(
    name: str, where: str, todos: list[dict], *, owing: bool, waiting: bool
) -> str:
    """The line telling the main session that its fork `name` answered the user's
    message in the thread `where` names, and opened `todos` there, which the session
    now owes; and that the thread owes nothing, unless the user has written there
    since (`waiting`) or a to-do on it is open (`owing`)."""
    listed = " and ".join(f"the to-do “{t['title']}” ({t['id']})" for t in todos)
    return (
        f"Your fork {name} answered the user's message in {where}"
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
