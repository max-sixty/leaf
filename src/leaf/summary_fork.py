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
back the working line and the thread's handover to the session by seconds.

The hint is the fork's for a thread whose newest delivered message Leaf kept back for
a line fork, since `forks.ask` asked this fork then: the session's delivery leaves it
out (`thread_context.batch_threads`), so the session spends no step on it. A delivery
whose newest message in the thread wasn't kept back, as one arriving while the
session still owed the thread its answer, carries the hint to the session when a
range is suggested.
Where the fork fails, Leaf tells the session the range it suggested (`_handed`), so
the summary has an owner either way. One path leaves it without one until the
thread's next message Leaf keeps back: a line turn that lapses, or whose step fails,
before the module asks its forks, since nothing runs then to hand the range over.

The range is the hint, which is one admission takes (`events.summary_range`), and the
fork writes only the prose, from the whole thread (`forks._thread_data`): the
original messages under any summary the range takes in, which the new summary
replaces. It follows the agent's own guidance for what a summary holds (`GUIDANCE`),
as the clerk follows the agent's guidance for what it writes, so a change to that is
made once, in the reference. The agent's guidance also leaves out of a range the
messages whose wording still matters to the current exchange, which the hint does by
keeping the newest exchange whole. Letting the fork end the range earlier, as the
agent may, is the alternative: offered that, the fork dropped the range's last
question from its prose while still folding it, which leaves the answer after the
summary with no question above it.

Leaf writes the summary as the agent's (`thread.cmd_summarize`), and the user never
meets the fork. It writes nothing once the page is no longer the session's, or where
the summary, had it been written as the fork was asked, would no longer be in force
(`_fence`): a summary written in the thread since replaced it, or an edit or a
take-back of a message in its range cancelled it, by the rules that cancel any
summary (`events.active_summaries`). The agent hears what Leaf wrote at its next step,
with its id, range and words, as its own (`clerk.queue`), and replaces it as it would
a summary it wrote. The page's diagnostics note each outcome (`summary_fork`), with
the fork's usage, time and the request it resent, as `forks` notes the line fork's.
"""

from pathlib import Path

from .clerk import queue, read_answer, reference_paragraph
from .refusals import Refused
from .service import PageTransaction

OPENING = "<leaf-summary-fork>"

# The agent's guidance for what a summary holds, which the fork follows.
GUIDANCE = ("threads.md", "A summary gives the range's")

# What the fork answers: the summary's Markdown.
ANSWER = {
    "type": "object",
    "properties": {"text": {"type": "string", "minLength": 1, "pattern": r"\S"}},
    "required": ["text"],
    "additionalProperties": False,
}

# The id the summary takes while `_fence` asks whether it would still be in force.
# The page readings this module takes are imported where they're read: `forks`,
# which a tool hook with nothing to deliver imports, imports this module, and such a
# hook runs at every turn, so it loads no runtime dependency but `click`.
_WEIGHED = "summary-fork"


def ask(page: PageTransaction, data: dict, basis: dict) -> dict | None:
    """The fork to make beside the line fork for the kept-back thread `basis` names,
    as `{"prompt", "basis"}`, where Leaf suggests a range of it to summarize; else
    None. `data` is the thread whole, as `forks._thread_data` reads it from `page`."""
    from .events import active_summaries, build_threads
    from .forks import thread_json
    from .revision_artifact import active_enclosing
    from .thread_context import summary_hint

    threads = build_threads(page.events, active_enclosing(page.page_dir))
    thread = threads.get(basis["thread"])
    if thread is None:
        return None
    summaries = active_summaries(page.events, threads)[basis["thread"]]
    hint = summary_hint(thread, summaries)
    if hint is None:
        return None
    return {
        "prompt": prompt(thread_json(data), hint),
        "basis": {
            "duty": "summary",
            "page": basis["page"],
            "thread": basis["thread"],
            "from": hint["from"],
            "through": hint["through"],
            "seq": page.events[-1]["seq"],
        },
    }


def prompt(thread: str, hint: dict) -> str:
    """The one message the fork answers: what it is for, the thread whole, the range
    and the agent's guidance for a summary."""
    guidance = "\n".join(
        f"> {line}" if line else ">"
        for line in reference_paragraph(*GUIDANCE).splitlines()
    )
    return f"""{OPENING}
This message comes from Leaf, not the user. The user just wrote in a long thread on a Leaf page this session holds, and the main session is answering them. You are a fork of the session, made meanwhile to fold the thread's earlier discussion into one summary, as the session would, so the user reads one account of it above the current exchange. Every tool call is denied here, so don't call tools.

The whole thread, as Leaf delivers it but with every message; "events" are the user's newest messages, which the main session answers:
{thread}

Summarize the messages from {hint["from"]} through {hint["through"]}, a range that takes in every summary in force among them, which yours replaces. Leaf posts it as the session's own summary: the thread shows it in place of those messages, and the originals stay available to unfold. It answers nothing; the main session answers the newest messages. Write it as the session's guidance has it:
{guidance}

Reply with this JSON alone: {{"text": "<the summary's Markdown>"}}
</leaf-summary-fork>"""


def take_answer(
    session_id: str,
    basis: dict,
    *,
    answer: str | None,
    failed: str | None,
    usage: dict | None = None,
    elapsed_ms: float | None = None,
    request: dict | None = None,
) -> dict:
    """Write the fork's summary as the agent's over the range `basis` names, and tell
    the agent; or nothing, where `_fence` stops it; or tell the agent the range, where
    the fork failed, its answer doesn't fit `ANSWER`, or admission refuses it. What
    came of it is noted in the page's diagnostics."""
    from .forks import note
    from .thread import cmd_summarize

    page_dir = Path(basis["page"])
    outcome: dict
    try:
        if answer is None:
            raise Refused(failed or "no answer")
        text = read_answer(answer, ANSWER)["text"].strip()
        record = cmd_summarize(
            page_dir,
            basis["from"],
            basis["through"],
            text,
            fence=lambda page: _fence(page, session_id, basis, text),
        )
    except (Refused, FileNotFoundError) as error:
        outcome = {"outcome": "failed", "why": str(error)}
        queue(session_id, [_handed(page_dir, basis, str(error))])
    else:
        if record is None:
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
            "from": basis["from"],
            "through": basis["through"],
            **outcome,
            **({"usage": usage} if usage else {}),
            **({"elapsedMs": elapsed_ms} if elapsed_ms is not None else {}),
            **({"request": request} if request else {}),
        },
    )
    return outcome


def _fence(page: PageTransaction, session_id: str, basis: dict, text: str) -> bool:
    """Whether the fork may still write its summary of the range `basis` names: the
    page is still the session's, and the summary, had it been written as the fork
    was asked, would be in force now."""
    from .events import active_summaries, build_threads
    from .revision_artifact import active_enclosing

    claim = page.active_claim
    if claim is None or claim["id"] != session_id:
        return False
    weighed = {
        "kind": "summary",
        "id": _WEIGHED,
        "seq": basis["seq"] + 0.5,
        "thread": basis["thread"],
        "from": basis["from"],
        "through": basis["through"],
        "text": text,
    }
    events = [
        *(event for event in page.events if event["seq"] <= basis["seq"]),
        weighed,
        *(event for event in page.events if event["seq"] > basis["seq"]),
    ]
    threads = build_threads(page.events, active_enclosing(page.page_dir))
    return any(
        summary["id"] == _WEIGHED
        for summary in active_summaries(events, threads).get(basis["thread"], [])
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
