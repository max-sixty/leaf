"""A fork of a Claude Code session's conversation that folds a long thread's earlier
discussion into one summary, written as the agent's own, beside the line fork that
answers the user's newest message in it (`forks.py`). It runs only in Claude Code,
where the line fork does.

Leaf suggests a range of a long thread to summarize (`thread_context.summary_hint`).
The user chose to have a fork write it, rather than leave it to the turn that answers
the user, which often skips it, and to make it at the line fork's moment rather than
at the turn's end with the clerk (`clerk.py`): the user has just written in the
thread, which is changing anyway, and the summary usually lands before the session's
answer does, whereas at the turn's end it would land while the user reads that
answer, and drop once they reply. They also chose that summarizing comes second to
answering. So the summary is a fork of its own, started
beside the line fork (`forks.ask`'s `beside`), rather than a part of the line fork's
answer: a fork's answer arrives whole, and a summary's few hundred words would hold
back the working line by seconds.

The hint is the fork's for a thread whose newest delivered message came to a round
that awaited a line (`events.unlined`) while a follower listed the session's line forks
(`leases.lane_up`), since `forks.ask` asks this fork beside that round's line fork:
the session's delivery leaves it out (`thread_context.batch_threads`), so the session
spends no step on it. A delivery whose newest message in the thread joined a round
the agent had spoken in, as one arriving while the session still owed the thread its
answer, carries the hint to the session when a range is suggested.
Where the fork fails, Leaf tells the session the range it suggested (`_handed`), so
the summary has an owner either way. `forks.ask` asks this fork whether or not the
round still awaits its line, so the agent's own progress in the thread leaves the
summary the fork's. Some paths leave it without one until the thread's next round: a
line fork's report that fails, or finds the round already answered, before the module
asks its forks, and a round older than the follower's first look at the page, since
nothing then asks the fork or hands the range over.

The fork chooses the range, as the agent would from a delivery's hint: the hint is
Leaf's suggestion, and the fork follows the agent's guidance for what to fold
(`RANGE`), weighing which messages compress and which the current exchange still turns
on, the opening message among them, and may fold nothing. The user chose this, as root
`AGENTS.md`'s "Leaf's role" has it. Leaf takes a range of the thread's spoken messages
that ends before the user's newest messages, which the main session answers. A range
Leaf can't take goes to the agent as a failed fork does; a fork that folds nothing
leaves the thread as it is, and the agent hears nothing of it. Taking the hint as the
range, the fork writing only the prose, is the alternative a later change might reach
for, since a fork once offered the range's end dropped its last question from the
prose while still folding it. It fails because a cutoff on the thread's length then
decides what the user reads in full: every long thread folds its opening message
unless an earlier summary left that out. The guidance names that case instead, keeping
in full the question a kept answer replies to.

The fork writes the prose from the whole thread (`forks._thread_data`): the original
messages under any summary the range takes in, which the new summary replaces. It
follows the agent's guidance for what a summary holds (`GUIDANCE`), as the clerk
follows the agent's guidance for what it writes, so a change to either is made once,
in the reference.

Leaf writes the summary as the agent's (`thread.cmd_summarize`), and the user never
meets the fork. It writes nothing once the page is no longer the session's, or where
the summary, had it been written as the fork was asked, would no longer be in force
(`_fence`), as when a summary written in the thread since replaced it
(`events.active_summaries`). The agent hears what Leaf wrote at its next step,
with its id, range and words, as its own (`clerk.queue`), and replaces it as it would
a summary it wrote. The page's diagnostics note each outcome (`summary_fork`), with
the fork's usage, time and what it resent, as `forks` notes the line fork's.
"""

from pathlib import Path

from leaf.agents.clerk import queue, read_answer, reference_paragraph
from leaf.agents.thread import cmd_summarize
from leaf.base.refusals import Refused
from leaf.log.events import active_summaries, build_threads, spoken_turns
from leaf.log.interaction_log import note
from leaf.log.thread_context import summary_hint
from leaf.records.transaction import PageTransaction
from leaf.source.revision_artifact import active_enclosing

OPENING = "<leaf-summary-fork>"

# The agent's guidance for what a summary folds and what it holds, which the fork
# follows.
RANGE = ("threads.md", "Fold what compresses most")
GUIDANCE = ("threads.md", "A summary is what the user reads")

# What the fork answers: the range it folds and the summary's Markdown, or that it
# folds nothing.
ANSWER = {
    "anyOf": [
        {
            "type": "object",
            "properties": {
                "from": {"type": "string", "minLength": 1},
                "through": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1, "pattern": r"\S"},
            },
            "required": ["from", "through", "text"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"fold": {"const": False}},
            "required": ["fold"],
            "additionalProperties": False,
        },
    ]
}

# The id the summary takes while `_fence` asks whether it would still be in force.
_WEIGHED = "summary-fork"


def due(page: PageTransaction, basis: dict) -> dict | None:
    """The basis of the fork to make beside the line fork for the round `basis`
    names on `page`, where Leaf suggests a range of its thread to summarize (`from`,
    `through`); else None."""
    threads = build_threads(page.events, active_enclosing(page.page_dir))
    thread = threads.get(basis["thread"])
    if thread is None:
        return None
    summaries = active_summaries(page.events, threads)[basis["thread"]]
    hint = summary_hint(thread, summaries)
    if hint is None:
        return None
    return {
        "duty": "summary",
        "page": basis["page"],
        "thread": basis["thread"],
        "from": hint["from"],
        "through": hint["through"],
        "inputs": basis["inputs"],
        "seq": page.events[-1]["seq"],
    }


def prompt(thread: str, hint: dict) -> str:
    """The one message the fork answers: what it is for, the thread whole as
    `forks.thread_json` renders it (`thread`), the range Leaf suggests (`hint`'s
    `from` and `through`, as `due` gives them) and the agent's guidance for choosing
    a range and writing its summary."""
    folds, holds = (
        "\n".join(
            f"> {line}" if line else ">"
            for line in reference_paragraph(*passage).splitlines()
        )
        for passage in (RANGE, GUIDANCE)
    )
    return f"""{OPENING}
This message comes from Leaf, not the user. The user just wrote in a long thread on a Leaf page this session holds, and the main session is answering them. You are a fork of the session, made meanwhile to fold the thread's earlier discussion into one summary, as the session would, so the user reads one account of it above the current exchange. Every tool call is denied here, so don't call tools.

The whole thread, as Leaf delivers it but with every message; "events" are the user's newest messages, which the main session answers:

{thread}

Leaf suggests folding the messages from {hint["from"]} through {hint["through"]}, a range that takes in every summary in force among them, which yours replaces. Choose the range yourself, as the session's guidance has it:
{folds}

The range runs forward from one spoken message of the thread through another and ends before the user's newest messages in "events"; Leaf takes no other. Leaf posts your summary as the session's own: the thread shows it in place of the range, and the originals stay available to unfold. It answers nothing; the main session answers the newest messages. Write it as the session's guidance has it:
{holds}

Reply with this JSON alone: {{"from": "<the range's first message id>", "through": "<its last message id>", "text": "<the summary's Markdown>"}}, or {{"fold": false}} where nothing in the thread compresses without losing wording the current exchange still turns on.
</leaf-summary-fork>"""


def take_answer(
    session_id: str,
    basis: dict,
    *,
    answer: str | None,
    failed: str | None,
    run: dict | None = None,
) -> dict:
    """Write the fork's summary as the agent's over the range it chose, and tell the
    agent; or nothing, where the fork folds nothing or `_fence` stops it; or tell the
    agent the range `basis` suggested, where the fork failed, its answer doesn't fit
    `ANSWER`, or Leaf can't take its range (`_fence`, admission). What came of it is
    noted in the page's diagnostics, with what `carrier.run_facts` read of the fork's
    run (`run`)."""
    page_dir = Path(basis["page"])
    outcome: dict
    chosen: dict = {}
    record = None
    try:
        if answer is None:
            raise Refused(failed or "no answer")
        chosen = read_answer(answer, ANSWER)
        if "fold" not in chosen:
            chosen["text"] = chosen["text"].strip()
            record = cmd_summarize(
                page_dir,
                chosen["from"],
                chosen["through"],
                chosen["text"],
                fence=lambda page: _fence(page, session_id, basis, chosen),
            )
    except (Refused, FileNotFoundError) as error:
        outcome = {"outcome": "failed", "why": str(error)}
        queue(session_id, [_handed(page_dir, basis, str(error))])
    else:
        if "fold" in chosen:
            outcome = {"outcome": "declined"}
        elif record is None:
            outcome = {"outcome": "dropped"}
        else:
            queue(session_id, [_told(page_dir, record)])
            outcome = {"outcome": "summarized", "summary": record["id"]}
    note(
        page_dir,
        {
            "type": "summary_fork",
            "session": session_id,
            "thread": basis["thread"],
            "suggested": {"from": basis["from"], "through": basis["through"]},
            **{key: chosen[key] for key in ("from", "through") if key in chosen},
            **outcome,
            **(run or {}),
        },
    )
    return outcome


def _fence(page: PageTransaction, session_id: str, basis: dict, chosen: dict) -> bool:
    """Whether the fork may still write its summary `chosen` of the thread `basis`
    names: the page is still the session's, and the summary, had it been written as
    the fork was asked, would be in force now. A range that isn't spoken messages of
    the thread in order, ending before the user's newest messages (`inputs`) that
    still stand, is refused."""
    claim = page.active_claim
    if claim is None or claim["id"] != session_id:
        return False
    threads = build_threads(page.events, active_enclosing(page.page_dir))
    thread = threads.get(basis["thread"])
    if thread is None:
        return False
    at = {message["id"]: index for index, message in enumerate(spoken_turns(thread))}
    start, end = at.get(chosen["from"]), at.get(chosen["through"])
    newest = min((at[i] for i in basis["inputs"] if i in at), default=len(at))
    if start is None or end is None or not start <= end < newest:
        raise Refused(
            f"its range, {chosen['from']} through {chosen['through']}, isn't spoken "
            "messages of the thread in order, ending before the user's newest"
        )
    weighed = {
        "kind": "summary",
        "id": _WEIGHED,
        "seq": basis["seq"] + 0.5,
        "thread": basis["thread"],
        **chosen,
    }
    events = [
        *(event for event in page.events if event["seq"] <= basis["seq"]),
        weighed,
        *(event for event in page.events if event["seq"] > basis["seq"]),
    ]
    return any(
        summary["id"] == _WEIGHED
        for summary in active_summaries(events, threads)[basis["thread"]]
    )


def _told(page_dir: Path, record: dict) -> str:
    """The line telling the agent of the summary Leaf wrote as its own."""
    quoted = "\n".join(f"> {line}" for line in record["text"].splitlines())
    return (
        f"Leaf summarized the earlier discussion in thread {record['thread']} on "
        f"{page_dir} for you, as your summary {record['id']} of {record['from']} "
        f"through {record['through']}:\n{quoted}\nIt is yours like any summary you "
        "write: to change it, summarize that range again with `leaf thread "
        "summarize`, which replaces it."
    )


def _handed(page_dir: Path, basis: dict, why: str) -> str:
    """The line handing the agent the summary Leaf's fork couldn't write."""
    return (
        f"Leaf's fork couldn't summarize the earlier discussion in thread "
        f"{basis['thread']} on {page_dir} ({why}). Summarize it as you would for a "
        f"delivery's `summary_hint` of {basis['from']} through {basis['through']}."
    )
