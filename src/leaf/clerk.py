"""Leaf's clerk: a fork of the agent's conversation, made as each of its turns ends,
that checks the pages the session holds against the conversation. It puts On Me what
the agent left to the user without putting it there, fixes a few out-of-date words on
a page where the fork says how, and passes the agent what else it finds out of date.
It is experimental, and runs only in Claude Code.

An agent does the user's work and Leaf's bookkeeping in one context, and late in long
sessions the bookkeeping slips: on 2026-10-25 five sessions holding live pages left
the decisions waiting on the user only in their chat replies, so On Me read empty, and
rewording the skill changed 0 of 6 replays of such a session. A fork of the whole
conversation reads what the agent said, so Leaf asks one. The user chose this shape on
2026-10-29 over a digest of the final reply, an advisor that prompts the agent, and a
clerk agent that also rewrites the page. On 2026-10-31 they split its results by who
can act on them: Leaf writes a result only where the fork's answer settles it and the
record is one Leaf keeps for that purpose, an ask On Me, and everything else reaches
the agent as a message, which it acts on or forks off. That
reverses the advisor's rejection for those findings alone. Only the agent opens a
to-do on its own list, since that list holds work the user wants done. Later that day
they asked that the fork also make small fixes itself, such as a lede that still says
work is running, and tell the agent what it changed, which keeps the agent in control:
it hears the old and new words and changes them back or rewrites them as it would its
own edit. That reverses the rejection of a clerk that rewrites the page for fixes of a
few words; a fix that needs more goes to the agent as a message.

Three principles, the user's (2026-10-30), bound what the fork may do:

- It adds attention, not an actor. The fork is the agent looking again at its own
  bookkeeping, and gives the agent reminders; it does none of the user's work.
- The user never meets it. What it writes is the agent's own record, authored by the
  agent's session with nothing marking the fork, and it adds no mark, message, status
  or control of its own. A first version marked its to-dos "added by Leaf"; the user
  rejected that as a second entity on the page.
- The agent stays sovereign. The agent hears each record at its next step, with its
  id and words, as its own, and keeps, withdraws or replaces it as it would one it
  wrote. Leaf opens no thread whose title a thread the agent opened on the page to
  ask something already has. It shows the fork the questions On Me no longer holds,
  answered, withdrawn or closed unanswered, each with its id, so the fork doesn't
  word one anew and asks one again under its id. It writes no record once a turn
  has opened since the fork read the conversation (`basis`), since that turn's
  agent, or the user who opened it, has the newer reading. A finding still
  reaches the agent then, naming the turn it came from, since the agent judges
  whether it still holds.

What the fork is asked is prose in the shipped skill,
`skills/leaf/references/turn-end-check.md`, which the agent can also read when one of
the clerk's lines puzzles it; `fork_prompt` sends it verbatim with each page's facts
and the answer's form. It asks for two things. Asks: what Leaf's rule for On Me puts
there that the agent left to the user and no On Me item holds. The fork reads that
rule, and the guidance for how a question reads in a thread, as the agent does
(`guidance`), since the user chose on 2026-10-31 that the fork apply Leaf's standard
policy rather than a wording of its own, so a question such as whether a suggested
follow-up goes On Me is settled once, by that rule. On 2026-11-05 they chose the same
for how a question reads: the reference's own wording for it gave 47 of 47 recorded
questions as one unbroken paragraph, and the agent's guidance now shapes both.
Findings for the agent:
a page that still says what the work or the conversation has since changed, an On Me
item already settled elsewhere, and work promised or set running that no page shows,
for which the fork sees the items the page shows started. A first version also wrote
the status line and named missed page steps; the user narrowed it on 2026-10-29 to
the asks alone, in Leaf's own words rather than any one user's markers, then on
2026-10-31 added back the findings. They left out an open-ended question about the
agent's instructions, which drew 12 noise findings of 63 in the first version's replay
and loses what it checks against once compaction drops the skill. What the page state
alone settles, such as input not yet delivered, is code's to report rather than a
model's.

The same day they left status lines out until a session shows a started item's line
going stale while its work runs in the background. The fork is good at them: replayed
with each started line swapped for one the conversation shows is over (`fork6.py`), it
restated 15 of 15, and it left all 9 runs with current lines alone. But none of the
21 recorded turn ends held a stale line, and Leaf can't yet write one truthfully: a
start written after the turn closed keeps the page reading working for the working
grace after the background work stops, since `activity._start_age` dates a start's
hold by when it was written rather than by the turn it names. Restating lines needs
that changed first.

This module is the fork's one home, shared by every harness: what it is asked
(`fork_prompt`, with each page's On Me and started items as `page_facts` reads them),
the answer it must give (`ANSWER`), and what Leaf does with that answer
(`apply_answer`). A harness only makes the fork and carries the two halves
(`cmd_fork`): Claude Code's hooks module calls `$.model.fork` from `turn.complete`
(`hooks/claude-code.ts`). Codex would fork with App Server's `thread/fork`
(ephemeral) and Pi's extension by resending its session, each handing the answer back
the same way; neither does yet.

The fork can't author the page, so it writes what the agent would write without a
widget (`conversation-loop.md`, "The On lists"): each ask, a step the user takes
included, is the agent's message with an obligation (`threads.md`). The message
holds the whole ask, On Me lists it until the user replies or settles it, and their
reply reaches the agent as any reply does. An ask that asks an earlier question
again, such as a step the user took that didn't work, names it, and Leaf asks it in
its thread under its own id, as the agent's `--obligation <id>` does (`obligations`),
reopening the thread if the user closed it. Any other opens a thread of its own, on
the passage the ask concerns where the fork names words the page shows once, and
otherwise on the page as a whole, which is also where words the page doesn't show
once leave it. An ask Leaf can't put in its question's thread, as where that thread
owes the user a reply, is taken as one naming none, since the fork has no next
attempt.

The fork once opened every ask in a new thread. On 2026-11-11 the user closed a
thread asking them to run `/reload-plugins`, having run it in the wrong session; the
agent restated the step only in chat, and the fork, which saw neither the closed
question nor any way to ask it again, opened a second thread on the same subject.
The user asked why Leaf hadn't reopened the first and continued there, so the fork
now asks a question again as the agent would, under its id in its thread, rather
than asking a second one beside it. A new question on an old subject still opens a
thread of its own. The title check above stays: replayed with this question on
2026-11-11, the real turn ends where it had fired found the fork asking again, in a
new thread under the same title, a question the agent had withdrawn as already asked
on the page, in 4 of 4 runs.

A first version wrote every ask as a to-do on the user on the page, titled from the
chat line, and `m` left a long title cut to half a line in the panel (2026-10-31).
The user asked for the routes a question asked well takes, a widget that asks or a
thread, and for a while let the fork put a step On Me as a to-do on the user, which
the user ended with Done. On 2026-11-03 the user removed to-dos on the user
altogether (`todos`): what is asked of the user is answered through the widget or
thread it stands on, never a Done Leaf adds, so a step is asked in a thread too. A
clarifying reply such as "where do I run it?" answers it, as any reply does, until the
agent's answer reopens it (`obligations`).

The fork reads each page's words as the user reads them, a block to a line
(`page_text`, from the passage reading `leaf thread create` quotes against), so it
sees what a page says now, text written before a compaction included, and can quote
it exactly. A stale finding may carry an edit: the page's words and the words to put
in their place. Leaf makes it (`_fix`) only while no turn has opened since the fork
read the conversation, and only where the page shows the words once. The reading,
not the file's text, says which place in the source the user reads the words that
change from (`_place`), so a copy in the head, a script, a style, a comment or a
draft body the user rewrote is never the one changed. Leaf swaps just those words in
`index.html` (`fixed_source`), keeping the source's whitespace between them so a line
or paragraph break among them stays, checks that the page then reads as before but
for them, and publishes the save as an agent's is checked and published, putting the
source back where the check fails. A fix whose changing words cross markup, whose
new words hold a tag, that would drop a line break, or that Leaf can't otherwise
place reaches the agent as the finding alone. A page the agent builds from another
file loses the fix at its next build, which the agent's line tells it.

Leaf queues one line for each record and finding (`QUEUED`) under the same locks as
its page's write, so a later page's failure loses no earlier page's lines. The next
prompt or tool-boundary hook adds the lines to the agent's context
(`hook_transport.carry_turn`), so the agent knows its records and their words, and
what the fork found, without spending a turn on them. A finding's line carries the
fork's summary, the words from the conversation it rests on and the session they are
in, so the agent can find the original message after a compaction. A line leaves the
queue once a hook has printed it (`heard`), so a prompt that Escape drops loses its
lines: the questions stay On Me and `leaf page state` lists them, but the agent isn't
told. Confirming the lines from the transcript, as `delivery.confirm_entered` does
for input, would close that gap.

Each fork's outcome goes to the diagnostics of every page the session holds
(`interaction_log`, type `turn_end_check`), as a fork reply's does (`forks.py`): what
the fork named on that page, verbatim, what Leaf wrote, changed and told for it, or
why it wrote no records, with the fork's tokens and time, and the main thread's
request it resent (`request` in `hooks/claude-code.ts`, which says where a replay
cuts the conversation; a turn-end fork reads it to `row`), whose `effort` the fork
thinks at. A fork that failed, or
gave an answer `ANSWER` refuses, is noted with its reason. Claude Code keeps no copy of a
`$.model.fork` exchange, only its token counts in the debug log, so this record is
what a later replay or audit scores against what the agent did next.

Measured on 2026-10-29 by replaying 21 recorded turn ends three times each on Opus
5.5 (`~/.tmp/leaf.agent-channels/replay/`, `fork3.py` and `score3.py`), with the asks
alone: the fork found 59 of the 63 labelled asks missing from On Me; 62 of its 64
findings were labelled asks and 2 borderline, none false; 2 of 39 runs at clean turn
ends named anything. Warm, a fork cost $0.08 (median). The same replay of the
reference on 2026-10-31 (`fork4.py`, `score4.py`, `REPORT4.md`) found 63 of the 63
asks, named one at 1 of 39 clean turn ends, and named 87 out-of-date passages, 81 of
them real and 1 false, and 7 pieces of unshown work, 6 real and none false; the
sample held no settled item, and one case added for it found both in 3 of 3 runs.
Warm, a fork cost $0.125 and wrote about seven times
the output. Rewording what failed, measured on those cases (`fork5.py`), cleared the
false and chat-reply findings at the cost of one hedged but true one. With each page's
text in the prompt and edits allowed (`fork8.py`), once on eight turn ends, the fork
named 34 stale passages against 17 without the text, and gave edits for 26, of which
25 read right. Replayed through `fixed_source` on the pages' sources (`place8.py`),
every one quoted words the page shows once, 24 landed where the user reads them and
2, whose changing words cross a link or a code span, were refused; none landed
anywhere else. The text adds about 1,000 to 11,000 input tokens per page. Claude
Code's fork reuses the session's cached prefix while its system prompt and tools
match the session's, which `$.model.fork` keeps by resending the main thread's own
last request.

The fork thinks at the session's own effort, and the check's reference asks it to
answer straight away without thinking it over, as Claude Code's `$.model.fork`
documentation suggests for a quick side job. From 2026-11-04 to 2026-11-14 the fork
asked for `low` effort instead, which kept the cache only where Claude Code's
per-message effort reaches the model. Elsewhere, as on Vertex, a low fork wrote the
whole conversation to the cache again (#5891, #5904), and the hooks module learned
that per backend from each check's usage (#5892, #5907): a stored answer, a rewrite
to learn it and another to check it again each week. On the 15 turn-end cases of
`leaf-dev eval 'turn-end-check*' --base` on 2026-11-14, a fork at xhigh asked to
answer straight away passed all 15, as the low fork did, and wrote 1.62 times its
output (95% interval 1.26–2.09) in 1.23 times its time (1.10–1.38). The measurements
below are of that low fork.

On turns planted in the claude-code journey on 2026-11-04, with the session at
xhigh, which leave an ask in the chat, answer it there,
make the page stale or set work running that no page shows, or leave nothing, the low fork named all 19 planted items and nothing at any
of the 13 quiet turns over five runs, as the session's effort did, with 0.45 times
the output (95% interval 0.31–0.63, 32 turns matched across six runs) and 0.62 times
the time.

A real session's drift is subtler than those plants. The 18 forks that named items
in real sessions at xhigh on 2026-11-04 were each replayed at low three times. The
replays matched all of their unshown work and asks left in the chat, 54% of their
stale passages and none of their offers of bolder work, which put no decision to the
user. Replays vary even at xhigh. Two of those forks, replayed at xhigh as a control,
matched their original findings half the time (7 of 14), and on the longest page the
xhigh and low replays caught the same share of its stale passages. A low replay
wrote a median 283 output tokens in 5.6 s, against 1,140 in 11.5 s at xhigh. The
fork runs off the turn's path, but the sooner it answers, the less often a turn
opened meanwhile drops its asks (`basis`).

`leaf-dev eval 'turn-end-check*' --harness claude-code --base` scores a change to
what the fork is asked, how hard it thinks or how Leaf takes its answer, on a short
constructed
conversation for each decision the prompt asks about (`dev/leaf_dev/fork_eval.py`).
"""

import json
import re
from bisect import bisect_right
from html import escape
from itertools import chain, islice
from pathlib import Path

from .registry.kernel import title_limit
from .schema import SKILL_FILE
from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    session_file,
    session_lock_path,
    session_record,
)

REFERENCES = SKILL_FILE.parent / "references"
# What the fork is asked, as the skill ships it.
REFERENCE = REFERENCES / "turn-end-check.md"
# The agent's own guidance the fork follows for its asks, each a paragraph of a
# reference named by the words that open it: what goes On Me, what a question holds,
# how a message reads in a thread's narrow card, and what it links.
GUIDANCE = (
    ("conversation-loop.md", "The user's **On Me** list holds"),
    ("authoring-on-me.md", "Make each question self-contained"),
    ("threads.md", "A thread shows in a narrow card"),
    ("page-authoring.md", "Link each pull request"),
)

_WORDS = {"type": "string", "minLength": 1, "pattern": r"\S"}

ANSWER = {
    "type": "object",
    "properties": {
        "asks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "minLength": 1},
                    "title": _WORDS,
                    # The message that asks it.
                    "text": _WORDS,
                    # The page's words the ask concerns, or "" for the page as a whole.
                    "passage": {"type": "string"},
                    # The earlier question it asks again (`message:<id>`), or "".
                    "again": {"type": "string"},
                    # The agent's words, which ground the ask in the conversation;
                    # Leaf writes only the title, text and passage.
                    "quote": {"type": "string"},
                },
                "required": ["page", "title", "text", "passage", "again", "quote"],
                "additionalProperties": False,
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"enum": ["stale", "settled", "unshown"]},
                    "page": {"type": "string", "minLength": 1},
                    "summary": _WORDS,
                    # The agent's or the user's words, which the agent finds the
                    # original message by.
                    "quote": {"type": "string"},
                    # A stale passage's fix where a few words make it: the page's
                    # words and the words to put in their place (`_fix`). Optional,
                    # since a fork that leaves it off another kind of finding would
                    # otherwise lose the whole answer.
                    "edit": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "properties": {
                                    "words": _WORDS,
                                    "replacement": {"type": "string"},
                                },
                                "required": ["words", "replacement"],
                                "additionalProperties": False,
                            },
                        ]
                    },
                },
                "required": ["kind", "page", "summary", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["asks", "findings"],
    "additionalProperties": False,
}


def answer_form() -> str:
    """The answer's form, which follows the pages' facts in the fork's question. A
    title over `title_limit` is fitted rather than refused (`thread.fit_title`)."""
    return (
        "Reply with only this JSON object, no code fence, with empty lists where there "
        f"is nothing, and each title under {title_limit()} characters:\n"
        '{"asks": [{"page": "<page path>", "title": "<title>", "text": '
        '"<message>", "passage": "<the page\'s words, or empty>", "again": "<the '
        'id of the question it asks again, or empty>", "quote": "<the agent\'s '
        'words>"}], "findings": [{"kind": '
        '"stale" or "settled" or "unshown", "page": "<page path>", "summary": '
        '"<summary>", "quote": "<the words it rests on>", "edit": {"words": "<the '
        'page\'s words>", "replacement": "<the new words>"} or null}]}'
    )


# What each kind of finding is, as the agent's line names it.
FOUND = {
    "stale": "the page saying what has since changed",
    "settled": "an On Me item already settled",
    "unshown": "work no page shows",
}

QUEUED = Record(
    "clerk",
    described(
        "The lines Leaf queued for a session's next step, in the state home's "
        "`sessions/<digest>.clerk` (`state.session_file`): one for each record the "
        "clerk wrote and each finding it passes on (`clerk`), and one for each reply "
        "a fork of the conversation posted (`forks`).",
        object_schema({"lines": {"type": "array", "items": STRING}}),
    ),
    since=36,
)

# The words that open the fork's question, which the replay and the transcript carry.
OPENING = "<leaf-fork-check>"


def page_facts(state: dict, events: list) -> dict:
    """What the fork is shown of one page, from `state` as `leaf page state` prints
    it and the page's `events`: its On Me; the questions asked in words that On Me no
    longer holds, each with its id, its thread and how it ended (answered, dropped,
    or its thread closed unanswered), which the fork words anew only to ask one again
    under its id; and each item the agent has started with the line its start gives
    it (`todos.item_starts`)."""
    from .todos import item_starts

    threads = {thread["id"]: thread for thread in state["threads"]}
    obligations = {item["id"]: item for item in state["obligations"]}
    todos = {todo["id"]: todo for todo in state["todos"]}
    updates = {workflow["id"]: workflow for workflow in state["workflows"]}

    # What each message asking a question says now, edits included: a question asked
    # again stands on its newest message, while its record keeps the first one's words.
    said = {}
    for event in events:
        if event["kind"] == "edit" and event["message"] in said and "text" in event:
            said[event["message"]] = event["text"]
        elif event.get("obligation"):
            said[event["id"]] = event.get("text")

    def words(record: dict) -> str:
        text = said.get(record.get("message")) or record["prompt"].get("text") or ""
        return " ".join(text.split())[:300]

    def thread_named(thread: str) -> str:
        title = (threads.get(thread) or {}).get("title")
        return f'"{title}"' if title else "an untitled thread"

    on_me = []
    for row in state["queues"]["on_user"]:
        record = obligations[row["id"]]
        if row["kind"] == "message":
            on_me.append(
                f"a reply to the agent's message in {thread_named(row['thread'])}: "
                f"{words(record)}"
            )
        elif row["kind"] == "update":
            on_me.append("an update of the user's to send again")
        else:
            on_me.append(f"decision: {words(record)}")

    def ended(record: dict) -> str | None:
        """How a question On Me no longer holds ended, or None while it stands."""
        if record["status"] == "withdrawn":
            return "dropped"
        if record["status"] != "open":
            return "answered"
        if closer := (threads.get(record["thread"]) or {}).get("resolved"):
            return f"closed by the {closer} unanswered"
        return None

    asked = [
        f"{record['id']}, in {thread_named(record['thread'])}, {how}: " + words(record)
        for record in state["obligations"]
        if record["source"]["kind"] == "message" and (how := ended(record))
    ]
    started = []
    for item, start in item_starts(events).items():
        if todos.get(item, {}).get("state") == "open":
            about = f'the agent\'s to-do "{todos[item]["title"]}"'
        elif item in updates:
            subject = updates[item]["subject"]
            about = (
                "the user's message in "
                + thread_named(subject["id"]).replace('"', 'thread "', 1)
                if subject["kind"] == "thread"
                else f"the user's answer on {subject['kind']} {subject['id']}"
            )
        else:
            continue
        started.append({"item": item, "about": about, "line": start["text"]})
    return {
        "title": state["title"],
        "path": state["page"],
        "on_me": on_me,
        "asked": asked,
        "started": started,
    }


def _block(facts: dict) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "(none)"

    parts = [
        f'Page "{facts["title"]}" ({facts["path"]})',
        f"On Me, what the page lists as waiting on the user:\n{lines(facts['on_me'])}",
    ]
    if facts.get("asked"):
        parts.append(
            "Asked on the page and no longer On Me; don't word one anew, and give "
            "the id of one an ask asks again:\n" + lines(facts["asked"])
        )
    parts.append(
        "Started items, which the page shows as under way, each with its line:\n"
        + lines(
            [
                f'{item["item"]}, {item["about"]}: "{item["line"]}"'
                for item in facts["started"]
            ]
        )
    )
    if facts.get("text"):
        parts.append(
            "What the page says now, as the user reads it, one block per line:\n"
            + facts["text"]
        )
    return "\n".join(parts)


def guidance() -> list[str]:
    """The agent's guidance the fork follows (`GUIDANCE`), each paragraph as the
    agent reads it."""

    def paragraph(name: str, opening: str) -> str:
        text = (REFERENCES / name).read_text()
        start = text.index(f"\n\n{opening}") + 2
        end = text.find("\n\n", start)
        return text[start:] if end < 0 else text[start:end]

    return [paragraph(*passage) for passage in GUIDANCE]


def fork_prompt(pages: list[dict]) -> str:
    """The one message a fork answers: the skill's account of the check
    (`REFERENCE`), the agent's guidance for asking (`guidance`), each page's facts
    (`page_facts`) and the answer's form (`answer_form`, `ANSWER`)."""
    blocks = "\n\n".join(_block(facts) for facts in pages)
    rules = "\n\n".join(guidance())
    return (
        f"{OPENING}\n{REFERENCE.read_text().strip()}\n\n## Leaf's guidance for asking\n\n"
        f"{rules}\n\n## Page state\n\n{blocks}\n\n{answer_form()}\n</leaf-fork-check>"
    )


def read_answer(text: str) -> dict:
    """A fork's reply as an answer `ANSWER` takes, or `Refused` saying why not. A
    fenced or prefaced object is read from its first `{` to its last `}`."""
    from .refusals import Refused
    from .registry.schema import json_validator

    start, end = text.find("{"), text.rfind("}")
    if start < 0:
        raise Refused("the fork's answer holds no JSON object")
    try:
        answer = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise Refused(f"the fork's answer is not JSON ({error.msg})") from error
    errors = sorted(json_validator(ANSWER).iter_errors(answer), key=str)
    if errors:
        raise Refused(f"the fork's answer doesn't fit its schema: {errors[0].message}")
    return answer


def basis(session_id: str) -> dict | None:
    """The turn a fork reads, as the session's lifecycle names it."""
    record = session_record(session_id)
    return record and {"turn": record["turn"], "opened": record["turn_opened"]}


def cmd_fork(session_id: str, payload: dict) -> dict | None:
    """One half of a fork for `session_id`, as `leaf hook --fork` hands it over:
    with neither `answer` nor `failed` in `payload`, the `question`; with either,
    `take_answer`, and the fork's `usage`, `elapsed_ms` and `request`
    where the harness gives them."""
    if not session_id:
        return None
    if "answer" in payload or "failed" in payload:
        run = {
            "usage": payload.get("usage"),
            "elapsedMs": payload.get("elapsed_ms"),
            "request": payload.get("request"),
            "failed": payload.get("failed"),
        }
        return take_answer(
            session_id,
            payload.get("answer"),
            payload.get("basis"),
            {name: value for name, value in run.items() if value is not None},
        )
    return question(session_id)


def question(session_id: str) -> dict | None:
    """What to fork `session_id`'s conversation with, as `{"prompt", "basis"}`, or
    None where it holds no page."""
    from .service import owned_pages

    facts = [
        facts for page in owned_pages(session_id) if (facts := _facts(page)) is not None
    ]
    if not facts:
        return None
    return {"prompt": fork_prompt(facts), "basis": basis(session_id)}


def take_answer(
    session_id: str, text: str | None, asked: dict | None, run: dict | None = None
) -> dict:
    """What Leaf wrote and told from `text`, the fork's reply to the question asked at
    `asked`, its `basis` (`apply_answer`); `run` holds the fork's usage and time, and
    why it failed where `text` is None. A fork that failed, or whose answer `ANSWER`
    refuses, writes only its note in each page's diagnostics."""
    from .refusals import Refused
    from .service import owned_pages

    run = run or {}

    def note(outcome: dict) -> None:
        for page_dir in owned_pages(session_id):
            _note(page_dir, session_id, asked, outcome)

    if text is None:
        note(run)
        return {"wrote": [], "changed": [], "told": []}
    try:
        answer = read_answer(text)
    except Refused as error:
        note({**run, "refused": str(error), "answer": text})
        raise
    return apply_answer(session_id, answer, asked, run)


def _note(page_dir: Path, session_id: str, asked: dict | None, outcome: dict) -> None:
    """Note what came of a turn-end fork in `page_dir`'s diagnostics."""
    from .interaction_log import append_interactions

    record = {
        "source": "cli",
        "type": "turn_end_check",
        "session": session_id,
        "turn": asked and asked["turn"],
        **outcome,
    }
    try:
        append_interactions(page_dir, [record])
    except OSError:
        pass


def _facts(page_dir: Path) -> dict | None:
    from .agent_state import page_state
    from .files import latest_revision
    from .service import PageTransaction

    try:
        with PageTransaction(page_dir) as page:
            facts = page_facts(page_state(page_dir, page.events), page.events)
            revision = latest_revision(page_dir)
            if revision is None:
                return {**facts, "text": ""}
            passages = _reading(page_dir, page.events, revision).passages()
            return {**facts, "text": page_text(passages)}
    except FileNotFoundError:
        return None


def _reading(page_dir: Path, events: list, revision: int):
    """The page at `revision` under the log, whose `passages` are its words as the
    user reads them, which `leaf thread create` quotes against."""
    from .projection import page_reading
    from .registry.storage import require_registry
    from .revision_artifact import read_revision

    reading = read_revision(page_dir, revision).under(require_registry(page_dir))
    return page_reading(reading, events, revision)


def page_text(passages) -> str:
    """`passages`' words with each block's on a line of its own."""
    chars = list(passages.text)
    for index in passages.breaks:
        chars[index] = "\n"
    return "".join(chars)


def apply_answer(
    session_id: str, answer: dict, asked: dict | None, run: dict | None = None
) -> dict:
    """Act on `answer` for each page `session_id` holds: put its asks On Me
    (`_ask`) and make each stale passage's fix (`_fix`) while the session's turn is
    still the one `asked` names, and pass each other finding to the agent whatever
    turn has opened since, queueing a line for each for the agent's next step; what
    it wrote, changed and told, and why it wrote no records if it didn't. Each page's
    diagnostics note what the fork named there and what came of it, with `run`."""
    from .leases import page_locked
    from .service import PageTransaction, owned_pages

    wrote: list[dict] = []
    changed: list[dict] = []
    told: list[str] = []
    dropped = None
    for page_dir in owned_pages(session_id):
        path = str(page_dir)
        mine = {
            part: [item for item in answer[part] if item["page"] == path]
            for part in ("asks", "findings")
        }
        if not any(mine.values()):
            _note(page_dir, session_id, asked, {**mine, **(run or {})})
            continue
        here = {"wrote": [], "changed": [], "told": 0}
        # The page as a command's write takes it (`leases.contract_writer`), then the
        # session, in the lifecycle's lock order (`PageTransaction.publishing_claim`),
        # so no turn opens between reading the turn and queueing what it wrote.
        try:
            with (
                page_locked(page_dir),
                PageTransaction(page_dir) as page,
                flocked(session_lock_path(session_id)),
            ):
                claim = page.active_claim
                if claim is None or claim["id"] != session_id:
                    continue
                identity = {"agent": claim["agent"], "session": claim["id"]}
                current = basis(session_id) == asked
                lines = []
                # A record refused partway leaves those before it on the page, so the
                # agent hears of each record written, whatever stops the rest.
                try:
                    if mine["asks"] and not current:
                        dropped = "another turn opened since the fork was made"
                        here["dropped"] = dropped
                    elif mine["asks"]:
                        for record, line in _ask(
                            page_dir, page, mine["asks"], identity
                        ):
                            wrote.append(record)
                            here["wrote"].append(record["id"])
                            lines.append(line)
                    # After the asks, which stand on the words the fork read.
                    for item in mine["findings"]:
                        edit = item.get("edit")
                        fixed = (
                            _fix(page_dir, page, edit)
                            if current and item["kind"] == "stale" and edit
                            else None
                        )
                        if fixed:
                            changed.append({"page": path, **fixed})
                            here["changed"].append(fixed)
                        lines.append(_found(path, item, session_id, current, fixed))
                except Exception as error:
                    here["error"] = str(error)
                    raise
                finally:
                    _append(session_id, lines)
                    told.extend(lines)
                    here["told"] = len(lines)
                    _note(page_dir, session_id, asked, {**mine, **here, **(run or {})})
        except FileNotFoundError:
            continue
    return {
        "wrote": wrote,
        "changed": changed,
        "told": told,
        **({"dropped": dropped} if dropped else {}),
    }


def _ask(page_dir: Path, page, asks: list[dict], identity: dict):
    """Each of `asks` put On Me as the agent's own in `page`, an open transaction,
    with the line telling the agent: the agent's message asking it, with an
    obligation. One that asks an earlier question `again` asks it under its id in its
    thread, which the message reopens if it was closed; any other opens a thread of
    its own, none whose title a thread the agent opened there to ask something
    already has. Where Leaf can't ask the question again, as where its thread owes
    the user a reply, the ask is taken as one naming none."""
    from .findings import Rejected
    from .thread import ask_again, fit_title
    from .validation.admission import checked_text

    # The asks the agent made there, by title: the threads it opened to ask something.
    asked_in = {
        event["title"].casefold()
        for event in page.events
        if event["kind"] == "comment"
        and event["author"] == "agent"
        and event.get("obligation")
        and "title" in event
    }
    # Every message is checked before the first is written, so a refused one leaves
    # the page as the fork found it.
    messages = [
        (
            fit_title(item["title"]),
            checked_text(page_dir, item["text"]),
            item["passage"].strip(),
            item["again"].strip(),
        )
        for item in asks
    ]
    for title, text, passage, again in messages:
        if again:
            try:
                record = ask_again(page, again, text, identity)
            except Rejected:
                pass
            else:
                yield record, _told(str(page_dir), title, text, passage, record)
                continue
        if title.casefold() in asked_in:
            continue
        asked_in.add(title.casefold())
        ask = (page_dir, page, title, text, identity)
        try:
            record = _put(*ask, passage)
        except Rejected:
            if not passage:
                raise
            record = _put(*ask, "")
        yield record, _told(str(page_dir), title, text, passage, record)


def _found(
    path: str, item: dict, session_id: str, current: bool, fixed: dict | None = None
) -> str:
    """The line passing one finding to the agent: what the fork found, which turn it
    read, `current` where no turn has opened since, the words it rests on, so the
    agent can find the original message, and what Leaf changed for it, if anything."""
    turn = "your last turn" if current else "a turn before the user's latest message"
    quoted = "\n".join(f"> {line}" for line in item["quote"].splitlines())
    rests = (
        f"\nIt rests on these words in this session's transcript (session "
        f"{session_id}):\n{quoted}"
        if quoted
        else ""
    )
    done = (
        f'Leaf changed "{fixed["old"]}" to "{fixed["new"]}" in {path}/index.html and '
        "published it. The change is yours like any edit you make: change it back or "
        "rewrite it if it's wrong, and if you build this page from another file, carry "
        "the change there."
        if fixed
        else "Leaf changed nothing for this; act on it if it still holds."
    )
    return (
        f"Leaf's turn-end check read {turn} and found {FOUND[item['kind']]} on "
        f"{path}: {item['summary']}{rests}\n{done}"
    )


def _fix(page_dir: Path, page, edit: dict) -> dict | None:
    """Make a stale passage's fix in `page`, an open transaction (`fixed_source`), and
    publish the page as an agent's save is checked and published; `{"old", "new"}`
    once made, or None, writing nothing, where Leaf can't make it."""
    from .files import require_revision
    from .publishing import authored_files, replaced_authored_files
    from .refusals import Refused
    from .revisioning import activate_source

    if activate_source(page_dir, transaction=page).error:
        return None
    view = _reading(page_dir, page.events, require_revision(page_dir))
    previous = authored_files(page_dir / "index.html", page_dir / "page")
    made = fixed_source(
        previous["index.html"].decode(), view.registry, view.logged_words, edit
    )
    if made is None:
        return None
    fixed, change = made
    try:
        with replaced_authored_files(
            page_dir, {**previous, "index.html": fixed.encode()}, previous
        ):
            if error := activate_source(page_dir, transaction=page).error:
                raise Refused(error)
    except Refused:
        return None
    return change


def fixed_source(source: str, registry: dict, logged: dict, edit: dict):
    """`source` with `edit`'s replacement in place of the words that change, where
    its page, read under `registry` and the log's changes (`logged_words`), shows the
    edit's words once, with `{"old", "new"}`; or None.

    The page's reading says where the words stand (`_place`) and checks the result:
    the page must read as before but for those words, with as many blocks. Only the
    words that change are swapped, and the source's own whitespace between them
    stays, so a line or paragraph break among them survives the swap. In a `<pre>`,
    where a line break shows, a fix that changes how many words stand beside or
    among one is refused, since which line each word belongs on is a guess. So is
    one whose new words hold a tag (`_TAG`): Leaf writes them as text, so a link the
    fork wrote would show as its markup, and the agent, told the words with the tag,
    wouldn't see that it does."""
    from .anchor_capture import occurrences
    from .passages import COLLAPSE, collapse, page_passages
    from .structure import SourceDocument

    def read(html: str):
        return page_passages(SourceDocument(html), registry, **logged)

    words, put = collapse(edit["words"]), collapse(edit["replacement"])
    passages = read(source)
    # Spelled as the page spells them: the change is placed by its offsets in `words`.
    found = [
        at
        for at, end in occurrences(passages, words, 0, len(passages.text))
        if passages.text[at:end] == words
    ]
    if words == put or len(found) != 1:
        return None
    start, end, new = _changed(words, put)
    if _TAG.search(new):
        return None
    old, target = words[start:end], found[0] + start
    placed = _place(SourceDocument(source), registry, old, target, passages, read)
    if placed is None:
        return None
    place, attribute, preformatted = placed
    parts = new.split(" ") if new else []
    gaps = COLLAPSE.findall(place.group())
    before, after = source[: place.start()], source[place.end() :]
    beside = [
        *gaps,
        before[len(before.rstrip()) :],
        after[: len(after) - len(after.lstrip())],
    ]
    if (
        preformatted
        and len(parts) != len(gaps) + 1
        and any("\n" in gap or "\r" in gap for gap in beside)
    ):
        return None
    spaces = [*gaps, *[" "] * len(parts)][: max(len(parts) - 1, 0)]
    swapped = [escape(part, quote=attribute) for part in parts[:1]]
    for part, gap in zip(parts[1:], spaces, strict=True):
        swapped += [gap, escape(part, quote=attribute)]
    fixed = source[: place.start()] + "".join(swapped) + source[place.end() :]
    reading = read(fixed)
    shown = collapse(passages.text[:target] + new + passages.text[found[0] + end :])
    if reading.text != shown or len(reading.breaks) != len(passages.breaks):
        return None
    return fixed, {"old": old, "new": new}


def _place(document, registry: dict, words: str, target: int, passages, read):
    """Where `document`'s source writes the `words` the user reads at `target` in
    `passages`, its page's reading, as the match, whether it stands in an attribute
    and whether in a `<pre>`; or None. Each place the source may write them, in its text or in
    the value of an attribute a widget shows (`x-says`), gets a character of its
    own just before it, and the marked page's reading (`read`) says which mark
    stands at `target`. A copy in a script, a style, the head, a comment or a body
    the user rewrote shows nowhere, so it is never the one found.

    A place writes whole words, may write each character that isn't a letter or
    digit as a character reference, and the words' spaces as any whitespace; one
    that crosses markup is no place, since a fix of a word or two swaps words within
    one run of text. The marks are private-use characters neither the source nor
    the reading holds, and a page with more places than those is refused."""
    from .passages import COLLAPSE

    source = document.html
    tags, values, preformatted = [], [], []
    for element in document.tree.find_all(True):
        location = element.source_location
        if location is None:
            continue
        tags += [
            document.offsets(span)
            for span in (location.start_tag, location.end_tag)
            if span is not None
        ]
        if element.tag == "pre" and location.end_tag is not None:
            preformatted.append(
                (
                    document.offsets(location.start_tag)[1],
                    document.offsets(location.end_tag)[0],
                )
            )
        for name in (registry.get(element.tag) or {}).get("x-says") or {}:
            if name in location.attrs:
                start, end = document.offsets(location.attrs[name])
                _, equals, value = source[start:end].partition("=")
                value = value.lstrip()
                quoted = value[:1] in {'"', "'"}
                if equals:
                    values.append((end - len(value) + quoted, end - quoted))
    tags.sort()
    values.sort()

    def within(spans: list, place: re.Match) -> bool:
        index = bisect_right(spans, (place.start(), len(source))) - 1
        return index >= 0 and place.end() <= spans[index][1]

    def free(place: re.Match) -> bool | None:
        """Whether a place may be the one, in text (False) or an attribute (True)."""
        if within(values, place):
            return True
        index = bisect_right(tags, (place.start(), len(source))) - 1
        return False if index < 0 or tags[index][1] <= place.start() else None

    pattern = COLLAPSE.pattern.join(
        "".join(
            re.escape(ch) if ch.isalnum() else f"(?:&#?\\w+;|{re.escape(ch)})"
            for ch in word
        )
        for word in words.split(" ")
    )
    # Whole words: no letter or digit just outside them, where `_` may stand as
    # Markdown emphasis.
    edges = (
        "(?<![^\\W_])" if words[0].isalnum() else "",
        "(?![^\\W_])" if words[-1].isalnum() else "",
    )
    places = [
        (place, inside)
        for place in re.finditer(edges[0] + pattern + edges[1], source)
        if (inside := free(place)) is not None
    ]
    held = set(source) | set(passages.text)
    private = chain(range(0xF0000, 0xFFFFE), range(0x100000, 0x10FFFE))
    marks = list(
        islice((mark for mark in map(chr, private) if mark not in held), len(places))
    )
    if len(marks) < len(places):
        return None
    marked, last = [], 0
    for mark, (place, _) in zip(marks, places, strict=True):
        marked += [source[last : place.start()], mark]
        last = place.start()
    by_mark = dict(zip(marks, places, strict=True))
    seen = 0
    for found in _PRIVATE.finditer(read("".join([*marked, source[last:]])).text):
        if found.group() not in by_mark:
            continue
        if found.start() - seen == target:
            place, attribute = by_mark[found.group()]
            return (
                place,
                attribute,
                any(a <= place.start() and place.end() <= b for a, b in preformatted),
            )
        seen += 1
    return None


# What opens a tag in HTML's tokenizer: `<` before a letter, `/`, `!` or `?`. Words
# the page shows as text may hold one too, as code does, and a fix to them is
# refused alike, leaving the finding to the agent.
_TAG = re.compile("<[A-Za-z/!?]")

# The supplementary private use areas, which `_place` draws its marks from.
_PRIVATE = re.compile("[\U000f0000-\U0010fffd]")


def _changed(words: str, put: str) -> tuple[int, int, str]:
    """Where in `words` the words `put` changes stand, and what replaces them, each
    widened to whole words: the span between the longest prefix and suffix the two
    share."""
    prefix = 0
    while prefix < min(len(words), len(put)) and words[prefix] == put[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(words), len(put)) - prefix
        and words[-1 - suffix] == put[-1 - suffix]
    ):
        suffix += 1
    start = words.rfind(" ", 0, prefix) + 1
    end = words.find(" ", len(words) - suffix)
    end = len(words) if end < 0 else end
    return start, end, put[start : len(put) - (len(words) - end)].strip()


def _append(session_id: str, lines: list[str]) -> None:
    """Queue `lines` for the session's next step (`queued`), for a caller holding
    the session's lock."""
    if lines:
        path = session_file(session_id, QUEUED.kind)
        held = QUEUED.read(path) or {"lines": []}
        QUEUED.write(path, {"lines": [*held["lines"], *lines]})


def _put(page_dir, page, title, text, identity, passage) -> dict:
    """The thread putting one ask On Me as the agent's own in `page`, an open
    transaction, on `passage` where it names one; refused, as `thread create --quote`
    is, where the page doesn't show `passage` once."""
    from .thread import open_thread

    return open_thread(
        page_dir,
        page,
        text,
        passage,
        title=title,
        obligation=True,
        identity=identity,
    )


def _told(path: str, title: str, text: str, passage: str, record: dict) -> str:
    """The line telling the agent what Leaf put On Me as its own, and where: a new
    thread, or the thread of the question `record` asks again."""
    question = f"message:{record['id']}"
    if record["kind"] == "reply":
        [question] = record["obligation"]
        put = (
            f" again, as {question}, with your message {record['id']} in its thread "
            f"on {path}, which reopens the thread if it was closed"
        )
    else:
        where = (
            f'the words "{passage}" in {path}'
            if "anchor" in record
            else f"{path} as a whole"
        )
        put = f", in a new thread on {where}, opened by your message {record['id']}"
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    withdraw = f"leaf task end {path} {question} dropped"
    return (
        f'From your last reply, Leaf asked the user "{title}" On Me{put}:\n'
        f"{quoted}\nIt is yours "
        "like any message you write: the user's reply reaches you as any reply does, "
        f"and if it isn't theirs to decide, withdraw it with `{withdraw}`, and ask it "
        "another way if you'd rather."
    )


def queued(session_id: str) -> list[str]:
    """What the session's next step hears from the clerk."""
    held = QUEUED.read(session_file(session_id, QUEUED.kind))
    return held["lines"] if held else []


def heard(session_id: str, lines: list[str]) -> None:
    """Take `lines`, which a hook handed the agent, off the queue; lines queued since
    stay for the next step."""
    if not lines:
        return
    path = session_file(session_id, QUEUED.kind)
    with flocked(session_lock_path(session_id)):
        held = QUEUED.read(path) or {"lines": []}
        rest = (
            held["lines"][len(lines) :]
            if held["lines"][: len(lines)] == lines
            else held["lines"]
        )
        if rest:
            QUEUED.write(path, {"lines": rest})
        else:
            path.unlink(missing_ok=True)
