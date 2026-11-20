"""The line fork: a fork of a Claude Code session's conversation that posts the
agent's working line on a thread's waiting messages as the user writes them. It runs
in every Claude Code session, and only there, from Leaf's hooks module
(`hooks/claude-code.ts`). How it works' Forks tab (`docs/how-it-works.html`) explains
the design, diagrams included; this header holds the rules this module keeps and the
choices behind them.

On a real page the session's answer to a thread message takes tens of seconds, longer
when it is busy, and the thread shows nothing from the agent after a message until the
session's first model call ends (`notes/fork-replies.md`, "Forks on real pages").
`$.model.fork` resends the session's last request with one more message, at any moment,
mid-command too, and a fork answers in seconds. The user had the fork post only
the agent's working line, rather than answer the thread: a line fork can't call tools
(`$.model.fork` denies every one), and answering is left to an agent that can act. The
main session gets every thread message as it gets any input, and routes it: it answers
the message itself, gives it to a new fork of its conversation, a subagent that
answers in the thread, or passes it to the fork already answering that thread
(`references/harness-claude-code.md`, "Subagents").

The user chose that the main session judge every message this way. The line fork
could also judge whether a fork of the session could do the work beside it and tell
the session so, but that only adds a line to what the session reads, and the session
decides anyway, knowing its own work better than a fork judging from a snapshot of
it. What the user accepted with that choice: nothing marks which messages could run
beside the session, so how often it delegates rests on its own judgment. Claude Code
tells the session as a subagent ends, waking an idle session, so the subagent's report
reaches its context. The distributed approach a later change might reach for is Leaf
spawning the fork itself (`$.agent.spawn`) and sending it the thread's later messages.
Its answer comes sooner, since it waits neither for the main session's next tool call
nor on a main session blocked in a long command; but Leaf would need its own judgment
of which messages to give a fork, and it puts a second holder on each thread it gives
one, and with it the turns, records and hooks that hold a thread for an agent Leaf
spawned and tell the main session what that agent did, since Claude Code tells a
session nothing of an agent a plugin spawned.

The user also chose that the line fork run beside the session's delivery rather than
ahead of it: Leaf delivers a thread message, and nudges a session nothing watches for
it, as it does in every harness, and the line goes in when the line fork answers. The
alternative a later change might reach for is holding the message from the session
until the line goes in, so the line always stands before the session's own words. That
hold needs a holder of its own for each thread, a bound for a line fork that never
answers and a wake when the bound runs out, and all it buys is the line's order: the
session judges every message itself, so nothing waits on the line fork's answer. What
the user accepted: the session sometimes speaks in the thread before the line fork
answers, and that line then goes in nowhere.

A thread awaits a line while it stands open and the user's turns waiting in it, its
messages and rewrites the agent still owes an answer (`events.unanswered_turns`), have
nothing of the agent's after the oldest of them, neither a message nor a rewrite of one
(`unlined`): a round the user started that no line or answer has reached. A turn that joins such a round before its line goes
in, such as a quick correction or "and also" right after the first message or the
user's rewrite of it, gets a line fork of its own about all of them. A turn that joins
a round the agent has spoken in, by its line or otherwise, gets none, since the agent's
words already stand after the round's first message.

The line is the agent's progress message in the thread (`thread.post_reply`), which
the thread shows until the session's own words replace it. It goes in only while its
round still awaits it (`_awaits_line`): while the thread's waiting turns are the ones
its line fork was asked about and the agent has said nothing in the thread since the
oldest of them. Leaf asks this under the page's lock as it appends the line
(`thread.Receipt`'s `fence`), so a line never lands after the session's own words in
its thread or speaks for a round a later turn joined. A line that fails it drops, and
the page's diagnostics say so.

While the line stands, the waiting messages before it read On it, as they do before
any progress message of the agent's (`served_state.work`, which serves it as their
workflows' `at_work`, so every surface showing whether the agent is at work agrees), as
the user chose. That word is all the line changes: as a receipt's progress it takes
nothing in hand (`thread.Receipt`), so every reader that ages, nudges or holds a turn
reads the message's delivery. A start would read as the session's turn, renewing it
after an interrupt and holding the message at Working before the session had taken it
in, which would hide it from the nudge and the overdue count.

The line fork thinks at the session's own effort, and its prompt asks it to reply
straight away without thinking it over, since its line is worth most in the seconds
before the session's own words reach the thread, and goes in nowhere after them; a
fork at another effort can cost a rewrite of the conversation to the cache
(`carrier.fork` says when). A fork at `low` writes lines as good as xhigh's
(`notes/fork-replies.md`, "How well the fork judges") and skips the occasional line
xhigh spends seconds thinking over, while a fork at xhigh asked to reply straight away
does as well on the eval's cases.

The session's pages follower (`hooks.cmd_pages`) lists a report for each round that
awaited a line as its newest turn arrived (`look`, `listed`) while it holds the
session's lane, a lease each new follower takes from the last (`take_lane`), so one
follower lists for a session at a time. It lists only rounds whose newest turn came after it first read the page, and
the module runs each listed id once (`carrier.py`), so each round, named by its newest
turn, gets at most one line fork, even where a module reload starts a follower again.
A round whose newest turn came before any follower read the page gets no line; its
messages reach the session all the same. The report's answer is the line fork's question (`ask`), and the line
fork's answer is posted (`route`), each a step of the instructions the module carries
(`step`, `carrier.py`). Python writes the prompt (`line_prompt`) and decides each step;
the module makes the fork and names the tool calls the session is running, which the
line fork can't see: its last request predates them.

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
own, so none holds back the line, and a new duty needs only its module and its entry
in `BESIDE`, with no change to the module.

The line goes in as the agent's own (`thread.post_reply` with the claim's identity),
and nothing once the page is no longer the session's. The page's diagnostics
(`interaction_log`) note each question as Leaf gives it to the module (`fork_asked`),
so a line fork that never answers shows; and every outcome of a line fork
(`fork_outcome`): its line posted, dropped and why, refused by the message's checks, or
the fork failed, with its tokens and time and what it resent of the main thread's
conversation (`resends` in `hooks/claude-code.ts`, which says where a replay cuts it;
its `effort` is the fork's), as the clerk's `turn_end_check` notes have it, which is
what a later replay or audit scores. `leaf-dev logs timeline` reads them beside the
session's transcript. `leaf-dev eval run 'line-fork*' --harness claude-code --base`
scores a change to the line fork's prompt on a short constructed conversation for each
kind of message (`dev/leaf_dev/fork_eval.py`).
"""

import json
from pathlib import Path

from . import summary_fork
from .json_block import json_block
from .leases import lease_speaks_here, take_wait_lease
from .service import PageTransaction
from .state import page_key, session_file

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


def lane_path(session_id: str) -> Path:
    return session_file(session_id, "fork-lane")


def take_lane(session_id: str):
    """Hold the session's lane, from any earlier holder, while this follower lists
    the session's line forks (`hooks.cmd_pages`)."""
    return take_wait_lease(lane_path(session_id), supersede=True)


def lane_up(session_id: str) -> bool:
    """Whether a follower holds the session's lane, and so lists a line fork, and the
    forks beside it, for each round that awaits a line."""
    return lease_speaks_here(lane_path(session_id))


def unlined(thread: dict, through: int | None = None) -> list[dict]:
    """The user's turns waiting in `thread` (`events.unanswered_turns`), oldest
    first, while the thread stands open and the agent has said nothing in it since
    the oldest of them, by a message or a rewrite of one: a round that awaits a line
    (the module header); else none. `through` reads the round as it stood at that
    seq, as the follower reads it as its newest turn arrived (`look`) and a delivery
    as the message it carries did (`thread_context.batch_threads`)."""
    from .events import spoken_turns, unanswered_turns

    if thread["resolved"]:
        return []
    waiting = [
        turn
        for turn in unanswered_turns(thread)
        if through is None or turn["seq"] <= through
    ]
    if not waiting or any(
        waiting[0]["seq"] < said and (through is None or said <= through)
        for message in spoken_turns(thread)
        if message["author"] == "agent"
        for said in (message["seq"], message.get("edited", {}).get("seq", 0))
    ):
        return []
    return waiting


def _threads(page: PageTransaction) -> dict[str, dict]:
    """The page's threads as the fold builds them, with the page's containment
    (`events.build_threads`)."""
    from .events import build_threads
    from .revision_artifact import active_enclosing

    return build_threads(page.events, active_enclosing(page.page_dir))


def _round(basis: dict) -> str:
    """The round `basis` names, by its page and newest turn, which no other round of
    the session's shares."""
    return f"{page_key(Path(basis['page']))}:{basis['inputs'][-1]}"


def listed(page_dir: Path, thread: str, waiting: list[dict]) -> dict:
    """The instruction the pages follower lists for the round `waiting` of `thread`:
    a report, whose answer is its line fork and the forks beside it (`step`). Its id
    names the round by its newest turn, so a turn that joins the round lists it
    again."""
    basis = {
        "page": str(page_dir),
        "thread": thread,
        "inputs": [turn["id"] for turn in waiting],
    }
    return {
        "id": f"line:{_round(basis)}",
        "do": "report",
        "basis": {"kind": "line", "thread": basis},
    }


def look(session_id: str, page_dir: Path, after: int | None) -> tuple[list[dict], int]:
    """The reports for the lane's holder to list for the page while it is its
    session's (`listed`): one for each round that awaited a line as its newest turn
    arrived (`unlined`), where that turn came after the seq `after`; and the `after`
    to pass next. A round stays listed once the agent speaks in it, since the forks
    beside its line fork are due all the same (`ask`), and a delivery leaves their
    work to them by the same reading. A follower's first look at the page passes
    None, and takes the log's last seq, so it lists no round older than itself."""
    from .events import unanswered_turns

    with PageTransaction(page_dir) as page:
        if after is None:
            return [], page.events[-1]["seq"] if page.events else 0
        claim = page.active_claim
        if claim is None or claim["id"] != session_id:
            return [], after
        threads = _threads(page)
    reports = []
    for thread, held in threads.items():
        owed = unanswered_turns(held)
        if (
            owed
            and owed[-1]["seq"] > after
            and (waiting := unlined(held, through=owed[-1]["seq"]))
        ):
            reports.append(listed(page_dir, thread, waiting))
    return reports, after


def _awaits_line(page: PageTransaction, basis: dict) -> bool:
    """Whether the round `basis` names still awaits its line on `page`: its thread's
    waiting turns are the ones its line fork was asked about, and the agent has said
    nothing in the thread since the oldest of them (`unlined`)."""
    thread = _threads(page).get(basis["thread"])
    return thread is not None and [turn["id"] for turn in unlined(thread)] == list(
        basis["inputs"]
    )


def step(session_id: str, payload: dict) -> dict | None:
    """Leaf's answer to the module's report of one of a thread's instructions
    (`carrier.step`), by its basis's `kind`. For a round that awaits a line (`line`),
    the follower's report asks the line fork's question (`ask`), with the forks to
    make beside it, and the line fork's answer, or a failed step, is posted or
    recorded (`route`). For a fork beside it (`beside`), Leaf writes what it answered
    by the duty its basis names (`BESIDE`)."""
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
        named = _round(thread)
        forked = {"kind": "line", "thread": thread, "running": running}
        return {
            "do": [
                *(
                    [fork(f"fork:{named}", question["prompt"], forked)]
                    if "prompt" in question
                    else []
                ),
                *(
                    fork(
                        f"{beside['basis']['duty']}:{named}",
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
    """What to fork the conversation with for the round `basis` names, as
    `{"thread"}` with the line fork's `prompt` while the round still awaits its line
    (`_awaits_line`), and `beside` listing the forks to make beside it, each
    `{"prompt", "basis"}`, where any is due. A fork beside the line fork is due
    whether or not the agent has spoken in the thread since, as by its own progress,
    since the round's delivery left its work to that fork. None where neither is due,
    as for a repeated step once the line went in, where the page is no longer the
    session's, or where the round's newest turn owes no reply, which only the session
    can settle."""
    page_dir = Path(basis["page"])
    try:
        with PageTransaction(page_dir) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                return None
            awaits = _awaits_line(page, basis)
            data = _thread_data(page, basis["inputs"])
            beside = [
                fork
                for fork in ([summary_fork.ask(page, data, basis)] if data else [])
                if fork is not None
            ]
    except FileNotFoundError:
        return None
    if data is None or not (awaits or beside):
        return None
    if not awaits:
        return {"thread": basis, "beside": beside}
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
    """Post the line fork's answer as the agent's working line on the round `basis`
    names (`_line`), or say why there is none: the line fork failed (`failed`, its
    reason), or its answer doesn't fit `ANSWER`. What came of it is recorded in the
    page's diagnostics."""
    from .clerk import read_answer
    from .refusals import Refused

    read = None
    if answer is not None:
        try:
            read = read_answer(answer, ANSWER)
        except Refused as error:
            failed = str(error)
    outcome = (
        {"outcome": "failed", "why": f"the fork failed: {failed or 'no answer'}"}
        if read is None
        else _line(session_id, basis, read["line"].strip())
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
    """Note what came of a round's line fork in its page's diagnostics."""
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


def _line(session_id: str, basis: dict, text: str) -> dict:
    """Post `text` as the agent's working line on the round `basis` names, while it
    still awaits one (`_awaits_line`, asked as the line is appended): `{"outcome":
    "posted", "text", "line"}` with the posted message's id, or why Leaf posted
    nothing."""
    from .delivery import ReceiptRefused
    from .findings import Rejected
    from .refusals import Refused
    from .thread import Receipt, post_reply

    try:
        record = post_reply(
            Path(basis["page"]),
            {"responds": basis["inputs"][-1]},
            text,
            settlement=Receipt(fence=lambda page: _awaits_line(page, basis)),
            claimed_session=session_id,
            ephemeral=True,
        )
    except (FileNotFoundError, ReceiptRefused) as error:
        return {"outcome": "dropped", "why": str(error), "text": text}
    except (Rejected, Refused) as error:
        why = f"the message was refused: {error}"
        return {"outcome": "refused", "why": why, "text": text}
    if record is None:
        why = "the agent spoke in the thread, or a turn joined its round, first"
        return {"outcome": "dropped", "why": why, "text": text}
    return {"outcome": "posted", "text": text, "line": record["id"]}
