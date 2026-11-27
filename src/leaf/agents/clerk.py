"""Leaf's clerk: a fork of the agent's conversation, made as each of its turns ends,
that checks the pages the session holds against the conversation. It puts On Me what
the agent left to the user without putting it there, fixes a few out-of-date words on
a page where the fork says how, and passes the agent what else it finds out of date.
It is experimental, and runs only in Claude Code.

An agent does the user's work and Leaf's bookkeeping in one context, and late in long
sessions the bookkeeping slips: sessions holding live pages leave the decisions waiting
on the user only in their chat replies, so On Me reads empty, and rewording the skill
doesn't reliably change that. A fork of the whole conversation reads
what the agent said, so Leaf asks one. The user chose this shape over a digest of the
final reply, an advisor that prompts the agent, and a clerk agent that also rewrites the
page. They split its results by who can act on them: Leaf writes a result only where the
fork's answer settles it and the record is one Leaf keeps for that purpose, an ask On
Me, and everything else reaches the agent as a message, which it acts on or forks off,
so for those findings alone the fork is the advisor they otherwise rejected. Only the
agent opens a to-do on its own list, since that list holds work the user wants done.
They asked that the fork also make small fixes itself, such as a lede that still says
work is running, and tell the agent what it changed, which keeps the agent in control:
it hears the old and new words and changes them back or rewrites them as it would its
own edit. So the fork rewrites the page, which they rejected for a clerk, only for fixes
of a few words; a fix that needs more goes to the agent as a message.

Four principles, the user's, bound what the fork may do:

- It adds attention, not an actor. The fork is the agent looking again at its own
  bookkeeping, and gives the agent reminders; it does none of the user's work.
- The user never meets it. What it writes is the agent's own record, authored by the
  agent's session with nothing marking the fork, and it adds no mark, message, status
  or control of its own: the user rejected marking its to-dos "added by Leaf" as a
  second entity on the page.
- The agent stays sovereign. The agent hears each record at its next step, with its
  id and words, as its own, and keeps, withdraws or replaces it as it would one it
  wrote. Leaf shows the fork the questions On Me no longer holds, answered or
  closed, each with its id, so the fork doesn't word one anew and asks one again
  under its id. It writes no record once a turn
  has opened since the fork read the conversation (`basis`), since that turn's
  agent, or the user who opened it, has the newer reading. A finding still
  reaches the agent then, naming the turn it came from, since the agent judges
  whether it still holds.
- It is a check, not a review. It answers briefly from what it holds:
  the conversation it inherits, which the cache serves, and the page facts Leaf
  hands it. It does no research, so each thing Leaf asks of it must be one those
  two settle, and it leaves out a finding they don't.
  Claude Code's `$.model.fork` already denies every tool call and stops the fork
  after a second request (read in 2.1.325's source), so the rule bounds what Leaf
  asks rather than what the fork can do. Leaf's question is never cached, and an
  uncached token costs ten times a cached one.

What the fork is asked is prose in the shipped skill,
`skills/leaf/references/turn-end-check.md`, which the agent can also read when one of
the clerk's lines puzzles it; `fork_prompt` sends it verbatim with each page's facts and
the answer's form. It asks for two things. Asks: what Leaf's rule for On Me puts there
that the agent left to the user and no On Me item holds. The fork reads that rule, and
the guidance for how a question reads in a thread, as the agent does (`guidance`), since
the user chose that the fork apply Leaf's standard policy rather than a wording of its
own, so a question such as whether a suggested follow-up goes On Me is settled once, by
that rule. They chose the same for how a question reads, since a wording of the
reference's own can give each question as one unbroken paragraph, so the agent's
guidance shapes both. Findings for the agent: anything a page still holds that no
longer fits the work as it now stands, an On Me item already settled elsewhere, work
promised or set running that no page shows, for which the fork sees the items the page
shows started, and an open thread whose agent messages the user would misread
(`overtaken`). The user cut the status line and missed page steps from what the fork is
asked, and has it ask for the asks in Leaf's own words rather than any one user's
markers. They left out an open-ended question about the agent's instructions, which
draws noise findings and loses what it checks against once compaction drops the skill.
What the page state alone settles, such as input not yet delivered, is code's to report
rather than a model's.

The user left status lines out until a session shows a started item's line going stale
while its work runs in the background. The fork can restate a started line the
conversation shows is over and leave current lines alone, but Leaf can't yet write one
truthfully: a start
written after the turn closed keeps the page reading working for the working grace after
the background work stops, since `activity._start_age` dates a start's hold by when it
was written rather than by the turn it names. Restating lines needs that changed first.

The user chose to try findings for what long sessions forget once compaction drops
the rule a reference states, each kept only if replays of the turns where it should
have fired catch it, a replay of ordinary recent turns stays near the noise without
it, and the fork takes no longer. `overtaken` applies the agent's own guidance for
threads (`GUIDANCE`) to two: a correction posted as a new reply to the agent's
unanswered one rather than edited into it, and a thread question or state later
work overtook. Leaf asks for no finding of a section reporting a finding without the
material it rests on: that question misses the case it is for, and on other turns
asks for the run or script behind a count far more often than the user asks for
material.

This module is the fork's one home, shared by every harness: what it is asked
(`fork_prompt`, with each page's On Me and started items as `page_facts` selects them
from the page's agent-facing state, which `agent_state.turn_end_facts` reads), the
answer it must give (`ANSWER`), and what Leaf does with that answer
(`apply_answer`). A harness only makes the fork and carries the two halves: Claude
Code's hooks module reports each main-loop turn the model answered (`turn_ended`),
makes the fork Leaf answers with, and reports its answer (`checked`), as it carries
every instruction (`carrier.py`). Codex would fork with App Server's `thread/fork`
(ephemeral) and Pi's extension by resending its session, each handing the answer back
the same way; neither does yet.

The fork can't author the page, so each ask is the agent's message in a thread,
written as the agent's guidance has it write one (`threads.md`), and Leaf posts its
text as the agent's `leaf thread` command does, drawing the HTML in it. Where the
agent offered answers the user picks among, left them the go-ahead for an action it
takes once they agree, such as a merge, or asked what a step only they can take
showed them, such as whether a build installed, the message usually holds an
`lf-options`, as "Ask for a pick" has the agent write it, so the pick shows as its
state, `1`–`9` answer it, and a reply in words leaves it open, passing it to the
agent until the agent answers. Any other ask, such as what an error the user saw
said, is the message with an obligation: On Me lists it until the user replies or
settles it, and their reply reaches the agent as any reply does. Where Leaf refuses the
message (`check_markup`), the fork has no next attempt, so Leaf asks nothing and hands
the agent the message and why, as a line the agent owes, and the agent asks. An ask
that asks an earlier question again, such as a step the user took that didn't work
or a choice they closed without picking, names it, and Leaf asks it in its thread
(`thread.ask_again`), a question first asked in words under its own id, as the
agent's `--obligation <id>` does (`obligations`), reopening the thread if the user
closed it. Any other opens a thread of its own, on
the passage the ask concerns where the fork names its words, and otherwise on the
page as a whole. The page places those words as it places any quote: where it doesn't
show them once, the thread stands on the element around the one copy the page's files
hold, or in Threads, and the line telling the agent of the ask says so where the files
don't hold them once (`unplaced-quote`). Where the
question's thread still owes the user a reply, the question
waits on that reply and is On Me again once it is given, so Leaf asks nothing and
tells the agent to reply there. An ask Leaf can't otherwise put in its question's
thread, as where its id names no question, is taken as one naming none, since the
fork has no next attempt.

An action the agent takes once the user agrees, such as a merge waiting on their
approval, is usually asked as a choice the user presses, as the user asked, rather than as a
step in words asking for a reply, which users answer with "yes" or the command the
agent told them to run. So whether an action asks for permission or is a step depends
on who takes it once the user agrees, a rule the fork reads in the agent's guidance
(`conversation-loop.md`).

The fork asks a question again as the agent would, under its id in its thread,
rather than asking a second one beside it, as the user asked: a fork that opens every
ask in a new thread, and sees neither a question the user closed nor any way to ask
it again, opens a second thread on the same subject when the agent restates the step
only in chat. A new question on an old subject still opens a thread of its own. Leaf
drops no ask for its title, as the user decided: matching it against the threads the
agent opened to ask dropped, telling no one, a new question that shared an old
one's title, while the ended questions the fork sees with their ids already keep it
from wording a withdrawn one anew. The fork also sees each question that still stands
while its next move is the agent's, as a choice does once the user answers it with a
question of their own. On Me lists none of them, and a fork shown only On Me reads the
agent restating such a choice in chat as an ask nothing holds, and opens a second
thread on it.

The user asked for the routes a question asked well takes, a widget that asks or a
thread, rather than an ask written as a to-do on the user titled from the chat line,
whose long title `m` left cut to half a line in the panel. The user removed to-dos on
the user altogether (`todos`): what is asked of the user is answered through the
widget or thread it stands on, never a Done Leaf adds, so a step is asked in a thread
too. A clarifying reply such as "where do I run it?" answers it, as any reply does,
until the agent's answer reopens it (`obligations`).

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

A line queued with `wake` tells the session of work it now owes, such as a finding
Leaf changed nothing for. Until a hook has
printed it, the watch between turns wakes the session for it once the turn has closed
(`waking`, `session.watch_between_turns`), and a session no watch follows is nudged
(`delivery.nudge_unwatched`). The turn that ends a stretch of work is the one most
likely to leave a page stale, and its next step is otherwise the user's return, by
when they have read the page. A record Leaf wrote and a fix it made need nothing of
the agent, so their lines wait for its next step.

Each fork's outcome goes to the diagnostics of every page the session holds
(`interaction_log`, type `turn_end_check`), as a fork reply's does (`forks.py`): what
the fork named on that page, verbatim, what Leaf wrote, changed and told for it, or
why it wrote no records, with the fork's tokens and time, and what it resent of the
main thread's conversation (`resends` in `hooks/claude-code.ts`, which says where a
replay cuts it), whose `effort` the fork thinks at. A fork that failed, or
gave an answer `ANSWER` refuses, is noted with its reason. Claude Code keeps no copy of a
`$.model.fork` exchange, only its token counts in the debug log, so this record is
what a later replay or audit scores against what the agent did next.

Claude Code's fork reuses the session's cached prefix while its system prompt and
tools match the session's, which `$.model.fork` keeps by resending the main thread's
own last request.

The fork thinks at the session's own effort, and the check's reference asks it to
answer straight away without thinking it over, as Claude Code's `$.model.fork`
documentation suggests for a quick side job. Asking for `low` effort instead can cost
a rewrite of the conversation to the cache (`carrier.fork` says
when), and a fork at xhigh asked to answer straight away does as well as a low fork
on the turn-end cases. The fork runs off the turn's path, but the sooner it answers, the
less often a turn opened meanwhile drops its asks (`basis`).

`leaf-dev eval run 'turn-end-check*' --harness claude-code --base` scores a change to
what the fork is asked, how hard it thinks or how Leaf takes its answer, on a short
constructed conversation for each decision the prompt asks about
(`dev/leaf_dev/fork_eval.py`).
"""

import json
import re
from bisect import bisect_right
from html import escape
from itertools import chain, islice
from pathlib import Path

from leaf.base.schema import SKILL_FILE
from leaf.base.state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    session_file,
    session_lock_path,
    session_record,
)
from leaf.source.registry.kernel import title_limit

REFERENCES = SKILL_FILE.parent / "references"
# What the fork is asked, as the skill ships it.
REFERENCE = REFERENCES / "turn-end-check.md"
# The agent's own guidance the fork follows for its asks and its overtaken threads,
# each a paragraph of a reference named by the words that open it: what goes On Me,
# which action asks for permission and which is a step, what a question holds, how
# HTML in a message draws, when it asks with a choice, how a message reads in a
# thread's narrow card, what it links, where a correction to an unanswered reply
# goes, and the reply a thread is owed once the work it discusses is done. The fork
# opens no file, so it can't follow a pointer in one of these paragraphs to another
# reference: what it needs to write the message is in the paragraph, or in the example
# right after it, which it gets with the paragraph and which shows the markup, such
# as `recommended` on the option the agent advises.
GUIDANCE = (
    ("conversation-loop.md", "The user's **On Me** list holds"),
    ("conversation-loop.md", "For an action you take once the user agrees"),
    ("authoring-on-me.md", "Make each question self-contained"),
    ("threads.md", "A message is Markdown, and HTML in it draws"),
    ("threads.md", "When a message asks the user to choose among answers"),
    ("threads.md", "A thread shows in a narrow card"),
    ("page-authoring.md", "Link each pull request"),
    ("threads.md", "While your reply is still the thread's latest message"),
    ("authoring-revisions.md", "The user reads threads to find out"),
)

_WORDS = {"type": "string", "minLength": 1, "pattern": r"\S"}

# Each kind of finding, as the agent's line names it: the one list of kinds, which
# the answer's schema and form read.
FOUND = {
    "stale": "the page holding what no longer fits the work",
    "settled": "an On Me item already settled",
    "unshown": "work no page shows",
    "overtaken": "a thread of yours the user would misread",
}

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
                    # The message that asks it, with any choice in it (`_ask`).
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
                    "kind": {"enum": list(FOUND)},
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
        + " or ".join(f'"{kind}"' for kind in FOUND)
        + ', "page": "<page path>", "summary": "<summary>", "quote": "<the words it '
        'rests on>", "edit": {"words": "<the page\'s words>", "replacement": "<the '
        'new words>"} or null}]}'
    )


QUEUED = Record(
    "clerk",
    described(
        "The lines Leaf queued for a session's next step, in the state home's "
        "`sessions/<digest>.clerk` (`state.session_file`): one for each record the "
        "clerk wrote and each finding it passes on (`clerk`), and one for each "
        "summary a summary fork wrote or left to the agent (`summary_fork`). "
        "Each says whether it wakes the session (`wake`): a "
        "line that tells it of work it now owes wakes it while it is idle, until a "
        "hook has printed the line.",
        object_schema(
            {
                "lines": {
                    "type": "array",
                    "items": object_schema(
                        {"line": STRING, "wake": {"type": "boolean"}},
                    ),
                }
            }
        ),
    ),
    since=52,
)

# The words that open the fork's question, which the replay and the transcript carry.
OPENING = "<leaf-fork-check>"


def page_facts(page_dir: Path, state: dict, events: list) -> dict:
    """What the fork is shown of the page at `page_dir`, from `state` as `leaf page
    state` prints it and the page's `events`, both read in one open transaction.

    It is shown the page's On Me, and the questions the agent asked that still stand
    while the next move is the agent's, as a choice does once the user answers it with
    a question of their own (`obligations`). On Me lists such a question again once
    the agent has answered or ended the work its answer took on, so the fork asks
    none of them. It is shown the
    questions the agent asked in a thread message, in words or by a widget, that On Me
    no longer holds, each with the id `thread.ask_again` takes, its thread and how it
    ended (answered, or its thread closed), so it words one anew only to ask it again
    under its id. A message of the user's, which an update records, asks the user
    nothing and is in neither list. It is also shown each item the agent has started,
    with the line its start gives it (`todos.item_starts`), and last the page's words
    as the user reads them, a block to a line (`page_text`)."""
    from leaf.agents.thread import widget_question
    from leaf.base.files import latest_revision
    from leaf.records.todos import item_starts

    threads = {thread["id"]: thread for thread in state["threads"]}
    obligations = {item["id"]: item for item in state["obligations"]}
    updates = {workflow["id"]: workflow for workflow in state["workflows"]}

    # What each message asking a question says now, edits included: a question asked
    # again stands on its newest message, while its record keeps the first one's
    # words.
    asking = {record.get("message") for record in state["obligations"]}
    said = {}
    for event in events:
        if event["kind"] == "edit" and event["message"] in said and "text" in event:
            said[event["message"]] = event["text"]
        elif event["id"] in asking:
            said[event["id"]] = event.get("text")

    def words(record: dict) -> str:
        """A question's words: a question asked in words reads as its message now
        does, and a widget's as its own prompt, or where it has none, such as a
        choice under the message that asks it, as its message."""
        prompt, message = record["prompt"].get("text"), said.get(record.get("message"))
        in_words = record["source"]["kind"] == "message"
        text = ((message or prompt) if in_words else (prompt or message)) or ""
        return " ".join(text.split())[:300]

    def thread_named(thread: str) -> str:
        title = (threads.get(thread) or {}).get("title")
        return f'"{title}"' if title else "an untitled thread"

    def question(record: dict) -> str:
        """A question the agent asked, as the fork reads it: in words, by a widget in
        a thread message, or by a widget on the page."""
        if record["source"]["kind"] == "message":
            return (
                f"a reply to the agent's message in {thread_named(record['thread'])}: "
                f"{words(record)}"
            )
        if record.get("message"):
            return (
                f"decision in the agent's message in "
                f"{thread_named(record['thread'])}: {words(record)}"
            )
        return f"decision: {words(record)}"

    # A row stands for its thread, which may hold more than one question (`also`).
    on_me = [
        question(record)
        if (record := obligations[identity])["source"]["kind"] in ("message", "widget")
        else "an update of the user's to send again"
        for row in state["queues"]["on_user"]
        for identity in (row["id"], *row["also"])
    ]
    # The agent's questions alone: an update or a to-do asks the user nothing.
    asking_user = [
        record
        for record in state["obligations"]
        if record["source"]["kind"] in ("message", "widget")
    ]
    held = [
        question(record)
        for record in asking_user
        if record["state"] != "done" and record["next_actor"] == "agent"
    ]

    def ended(record: dict) -> str | None:
        """How a question On Me no longer holds ended, or None while it stands: the
        user's answer, or a resolve of its thread (`obligations`), by whoever the
        thread stands resolved by where it still does."""
        if record["state"] == "done":
            return "answered"
        if record["next_actor"] is not None:
            return None
        closer = (threads.get(record["thread"]) or {}).get("resolved")
        return f"closed by the {closer}" if closer else "closed"

    asked: dict[str, str] = {}
    for record in asking_user:
        if record.get("message") and (how := ended(record)):
            # By the id `thread.ask_again` takes: a question asked in words by its
            # own, and a widget's by the message holding it.
            name = (
                record["id"]
                if record["source"]["kind"] == "message"
                else widget_question(record["message"])
            )
            asked.setdefault(
                name,
                f"{name}, in {thread_named(record['thread'])}, {how}: {words(record)}",
            )
    started = []
    for item, start in item_starts(events).items():
        todo = obligations.get(item)
        if todo and todo["source"]["kind"] == "todo" and todo["state"] != "done":
            about = f'the agent\'s to-do "{todo["prompt"]["text"]}"'
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
    revision = latest_revision(page_dir)
    return {
        "title": state["title"],
        "path": state["page"],
        "on_me": on_me,
        "held": held,
        "asked": list(asked.values()),
        "started": started,
        "text": ""
        if revision is None
        else page_text(_reading(page_dir, events, revision).passages()),
    }


def _block(facts: dict) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) or "(none)"

    parts = [
        f'Page "{facts["title"]}" ({facts["path"]})',
        f"On Me, what the page lists as waiting on the user:\n{lines(facts['on_me'])}",
    ]
    if facts.get("held"):
        parts.append(
            "Asked on the page and still open, each waiting on the agent before "
            "On Me lists it again; ask none of these again:\n" + lines(facts["held"])
        )
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
    agent reads it, with its example."""
    return [reference_paragraph(*passage) for passage in GUIDANCE]


def reference_paragraph(name: str, opening: str) -> str:
    """The paragraph of the skill's reference `name` that opens with `opening`, with
    any fenced example right after it, as the agent reads it, for a fork that follows
    the agent's guidance."""
    text = (REFERENCES / name).read_text()
    start = text.find(f"\n\n{opening}") + 2
    if start < 2:
        raise ValueError(f"{name} has no paragraph opening {opening!r}")
    end = text.find("\n\n", start)
    while end >= 0 and text.startswith("```", end + 2):
        closed = text.find("\n```", text.find("\n", end + 2))
        end = text.find("\n\n", closed + 4)
    return text[start:] if end < 0 else text[start:end]


def fork_prompt(pages: list[dict]) -> str:
    """The one message a fork answers: the skill's account of the check
    (`REFERENCE`), the agent's guidance for asking and for threads (`guidance`), each
    page's facts (`page_facts`) and the answer's form (`answer_form`, `ANSWER`)."""
    blocks = "\n\n".join(_block(facts) for facts in pages)
    rules = "\n\n".join(guidance())
    return (
        f"{OPENING}\n{REFERENCE.read_text().strip()}\n\n## Leaf's guidance for asking "
        "and for threads\n\n"
        f"{rules}\n\n## Page state\n\n{blocks}\n\n{answer_form()}\n</leaf-fork-check>"
    )


def read_answer(text: str, schema: dict = ANSWER) -> dict:
    """A fork's reply as an answer `schema` takes, the clerk's `ANSWER` unless
    another fork's, or `Refused` saying why not. A fenced or prefaced object is read
    from its first `{` to its last `}`."""
    from leaf.base.refusals import Refused
    from leaf.source.registry.schema import json_validator

    start, end = text.find("{"), text.rfind("}")
    if start < 0:
        raise Refused("the fork's answer holds no JSON object")
    try:
        answer = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        raise Refused(f"the fork's answer is not JSON ({error.msg})") from error
    errors = sorted(json_validator(schema).iter_errors(answer), key=str)
    if errors:
        raise Refused(f"the fork's answer doesn't fit its schema: {errors[0].message}")
    return answer


def basis(session_id: str) -> dict | None:
    """The turn a fork reads, as the session's lifecycle names it."""
    record = session_record(session_id)
    return record and {"turn": record["turn"], "opened": record["turn_opened"]}


def turn_ended(session_id: str, pages: list[dict]) -> dict | None:
    """Leaf's answer to the end of a main-loop turn the model answered
    (`hooks.cmd_fork`): the fork to make with the turn-end check's question about
    `pages`, what the fork is shown of each page the session holds (`page_facts`),
    or None where there are none. Its basis is the turn the fork reads (`basis`),
    which its answer comes back with (`checked`)."""
    import uuid

    from leaf.agents.carrier import fork

    if not pages:
        return None
    turn = {"kind": "check", **(basis(session_id) or {})}
    return {"do": [fork(f"check:{uuid.uuid4().hex}", fork_prompt(pages), turn)]}


def checked(session_id: str, payload: dict) -> dict:
    """What Leaf wrote and told from the turn-end check's fork as the module reports
    it (`hooks.cmd_fork`): its `answer`, or why there is none (`failed`), with its
    `usage`, `elapsed_ms` and what it resent of the main thread's conversation
    (`resent`, noted as `request`) where the harness gives them (`take_answer`), and a
    line for the module's debug log saying what came of it. An answer `ANSWER` refuses
    writes nothing, and says why (`refused`)."""
    from leaf.agents.carrier import run_facts
    from leaf.base.refusals import Refused

    basis = payload["basis"]
    asked = (
        {"turn": basis["turn"], "opened": basis["opened"]} if "turn" in basis else None
    )
    failed = payload.get("failed")
    run = run_facts(payload) | ({"failed": failed} if failed is not None else {})
    text = payload.get("answer")
    try:
        applied = take_answer(session_id, text, asked, run)
    except Refused as error:
        return {
            "wrote": [],
            "changed": [],
            "told": [],
            "refused": str(error),
            "log": f"the clerk wrote nothing: {error}",
        }
    if text is None:
        return {**applied, "log": f"the clerk's fork gave no answer ({failed})"}
    counts = [
        f"{len(applied[part])} {noun}{'' if len(applied[part]) == 1 else 's'}"
        for part, noun in (
            ("wrote", "record"),
            ("changed", "passage"),
            ("told", "line"),
        )
    ]
    dropped = (
        f", and wrote no records on a page where {applied['dropped']}"
        if applied.get("dropped")
        else ""
    )
    return {
        **applied,
        "log": f"the clerk wrote {counts[0]}, changed {counts[1]} and told the agent "
        f"{counts[2]}{dropped}",
    }


def take_answer(
    session_id: str, text: str | None, asked: dict | None, run: dict | None = None
) -> dict:
    """What Leaf wrote and told from `text`, the fork's reply to the question asked at
    `asked`, its `basis` (`apply_answer`); `run` holds the fork's usage and time, and
    why it failed where `text` is None. A fork that failed, or whose answer `ANSWER`
    refuses, writes only its note in each page's diagnostics."""
    from leaf.base.refusals import Refused
    from leaf.records.transaction import owned_pages

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
    from leaf.log.interaction_log import note

    note(
        page_dir,
        {
            "type": "turn_end_check",
            "session": session_id,
            "turn": asked and asked["turn"],
            **outcome,
        },
    )


def _reading(page_dir: Path, events: list, revision: int):
    """The page at `revision` under the log, whose `passages` are its words as the
    user reads them, which `leaf thread create` quotes against."""
    from leaf.log.projection import page_reading
    from leaf.source.revision_artifact import read_revision
    from leaf.source.vocabulary import require_registry

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
    turn has opened since, queueing a line for each for the agent's next step. A
    finding Leaf changed nothing for is work the agent owes before the user next
    reads the page, so its line wakes an idle session (`waking`), and a session no
    watch follows is nudged for it, once, if no turn has opened since; a record Leaf
    wrote or a fix it made only tells.
    Returns what it wrote, changed and told, and why it wrote no records if it
    didn't. Each page's diagnostics note what the fork named there and what came of
    it, with `run`."""
    from leaf.agents.delivery import nudge_unwatched
    from leaf.base.leases import page_locked
    from leaf.records.transaction import PageTransaction, owned_pages

    wrote: list[dict] = []
    changed: list[dict] = []
    told: list[str] = []
    dropped = None
    nudged = False
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
                lines, owed = [], []
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
                            if record is None:
                                owed.append(line)
                                continue
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
                        (lines if fixed else owed).append(
                            _found(path, item, session_id, current, fixed)
                        )
                except Exception as error:
                    here["error"] = str(error)
                    raise
                finally:
                    _append(session_id, lines)
                    _append(session_id, owed, wake=True)
                    told.extend([*lines, *owed])
                    here["told"] = len(lines) + len(owed)
                    _note(page_dir, session_id, asked, {**mine, **here, **(run or {})})
                # After the lines are queued, so the turn a nudge starts hears them;
                # once, since that turn hears every page's lines; and only for the
                # turn the fork read, which ended on its answer, so a later turn the
                # user stopped with Escape waits for their next prompt.
                if owed and current and not nudged:
                    nudge_unwatched(page)
                    nudged = True
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
    with the line telling the agent: the agent's message asking it, posted as the
    agent's `leaf thread` command posts its text, so the HTML in it draws
    (`drawn_markup`). A widget in it that asks, such as a choice (`threads.md`, "Ask
    for a pick"), asks the question, and otherwise the message asks with an
    obligation. Where Leaf refuses the message, as for HTML that doesn't validate or
    a picture the page hasn't got, nothing is posted for it: the record is None, and
    the line, which the agent owes, hands the agent the ask and why, so it asks the
    user itself. One that asks an earlier question `again` asks it in its
    thread (`ask_again`), which the message reopens if it was closed; any other opens
    a thread of its own. Where that thread still owes the user a reply, the question
    waits on the reply and is On Me again once it is given, so nothing is posted and
    the line, which the agent owes, says to give it. Where Leaf can't otherwise ask
    the question again, as where the id names no question, the ask is taken as one
    naming none."""
    from leaf.agents.thread import OwedAnswer, fit_title
    from leaf.base.findings import Rejected
    from leaf.records.authored_checks.admission import checked_text
    from leaf.source.vocabulary import require_registry

    registry = require_registry(page_dir)
    for item in asks:
        title, text = fit_title(item["title"]), item["text"]
        passage, again = item["passage"].strip(), item["again"].strip()
        ask = (page_dir, page, title, text, passage, again, identity, registry)
        try:
            checked_text(page_dir, text, html=True)
            record, found = _ask_one(*ask)
        except Rejected as error:
            yield None, _unasked(str(page_dir), title, text, error)
            continue
        except OwedAnswer as owed:
            yield None, _owed(str(page_dir), title, again, owed)
            continue
        yield record, _told(str(page_dir), title, text, passage, record, again, found)


def _ask_one(
    page_dir, page, title, text, passage, again, identity, registry
) -> tuple[dict, list]:
    """The message putting one ask On Me, and what Leaf noted beside it: in the
    thread of the question it asks `again` where Leaf can ask it there, and otherwise
    in a thread of its own, on `passage` where it names one. A refusal of its HTML
    reaches the caller from either thread (`_ask`)."""
    from leaf.agents.thread import ask_again, drawn_markup, markup_asks

    if again and (record := ask_again(page, again, text, identity)):
        return record, []
    asks = markup_asks(drawn_markup(text), registry)
    return _put(page_dir, page, title, text, identity, not asks, passage)


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
    from leaf.base.files import require_revision
    from leaf.base.refusals import Refused
    from leaf.records.publishing import authored_files, replaced_authored_files
    from leaf.records.revisioning import activate_source

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
    from leaf.source.anchor_capture import occurrences
    from leaf.source.passages import COLLAPSE, collapse, page_passages
    from leaf.source.structure import SourceDocument

    def read(html: str):
        return page_passages(SourceDocument(html), registry, **logged)

    words, put = collapse(edit["words"]), collapse(edit["replacement"])
    passages = read(source)
    found = [at for at, _ in occurrences(passages, words, 0, len(passages.text))]
    if words == put or len(found) != 1:
        return None
    start, end, new = _changed(words, put)
    if _TAG.search(new):
        return None
    old, target = words[start:end], found[0] + start
    placed = _place(SourceDocument(source), old, target, passages, read)
    if placed is None:
        return None
    place, preformatted = placed
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
    swapped = [escape(part, quote=False) for part in parts[:1]]
    for part, gap in zip(parts[1:], spaces, strict=True):
        swapped += [gap, escape(part, quote=False)]
    fixed = source[: place.start()] + "".join(swapped) + source[place.end() :]
    reading = read(fixed)
    shown = collapse(passages.text[:target] + new + passages.text[found[0] + end :])
    if reading.text != shown or len(reading.breaks) != len(passages.breaks):
        return None
    return fixed, {"old": old, "new": new}


def _place(document, words: str, target: int, passages, read):
    """Where `document`'s source writes the `words` the user reads at `target` in
    `passages`, its page's reading, as the match and whether it stands in a `<pre>`;
    or None. Each place in the source's text that may write them gets a character of
    its own just before it, and the marked page's reading (`read`) says which mark
    stands at `target`. A copy in a script, a style, the head, a comment or a body
    the user rewrote shows nowhere, so it is never the one found.

    A place writes whole words, may write each character that isn't a letter or
    digit as a character reference, and the words' spaces as any whitespace; one
    that crosses markup is no place, since a fix of a word or two swaps words within
    one run of text. The marks are private-use characters neither the source nor
    the reading holds, and a page with more places than those is refused."""
    from leaf.source.passages import COLLAPSE

    source = document.html
    tags, preformatted = [], []
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
    tags.sort()

    def free(place: re.Match) -> bool:
        """Whether a place stands in the source's text rather than inside a tag."""
        index = bisect_right(tags, (place.start(), len(source))) - 1
        return index < 0 or tags[index][1] <= place.start()

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
        place
        for place in re.finditer(edges[0] + pattern + edges[1], source)
        if free(place)
    ]
    held = set(source) | set(passages.text)
    private = chain(range(0xF0000, 0xFFFFE), range(0x100000, 0x10FFFE))
    marks = list(
        islice((mark for mark in map(chr, private) if mark not in held), len(places))
    )
    if len(marks) < len(places):
        return None
    marked, last = [], 0
    for mark, place in zip(marks, places, strict=True):
        marked += [source[last : place.start()], mark]
        last = place.start()
    by_mark = dict(zip(marks, places, strict=True))
    seen = 0
    for found in _PRIVATE.finditer(read("".join([*marked, source[last:]])).text):
        if found.group() not in by_mark:
            continue
        if found.start() - seen == target:
            place = by_mark[found.group()]
            return (
                place,
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


def queue(session_id: str, lines: list[str], *, wake: bool = False) -> None:
    """Queue `lines` for the session's next step (`queued`), lines that wake an idle
    session where they tell it of work it now owes (`wake`, `waking`)."""
    if lines:
        with flocked(session_lock_path(session_id)):
            _append(session_id, lines, wake=wake)


def _append(session_id: str, lines: list[str], *, wake: bool = False) -> None:
    """`queue`, for a caller already holding the session's lock."""
    if lines:
        path = session_file(session_id, QUEUED.kind)
        held = QUEUED.read(path) or {"lines": []}
        added = [{"line": line, "wake": wake} for line in lines]
        QUEUED.write(path, {"lines": [*held["lines"], *added]})


def _put(page_dir, page, title, text, identity, obligation, passage) -> tuple:
    """The thread putting one ask On Me as the agent's own in `page`, an open
    transaction, on `passage` where it names one, with an obligation where no widget
    in it asks, and what Leaf noted beside it, as `thread create --quote` notes where
    the page's files don't show `passage` once; refused as the agent's message is,
    where its HTML doesn't validate (`check_markup`)."""
    from leaf.agents.thread import open_thread

    return open_thread(
        page_dir,
        page,
        text,
        passage,
        title=title,
        obligation=obligation,
        identity=identity,
    )


def _unasked(path: str, title: str, text: str, error: Exception) -> str:
    """The line handing the agent an ask whose message Leaf refused, which the agent
    owes: the message and why, so it asks the user itself."""
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    return (
        f'From your last reply, Leaf would have asked the user "{title}" On Me in '
        f"{path} with this message:\n{quoted}\nIt refused the message, so nothing "
        f"was asked: {error}\nIf it is still theirs to decide, ask it yourself "
        "(`references/threads.md`)."
    )


def _owed(path: str, title: str, again: str, owed: Exception) -> str:
    """The line telling the agent that the question an ask names `again` waits on the
    agent's reply in its thread, which the agent owes, so Leaf asked nothing."""
    question = f"message:{again.removeprefix('message:')}"
    return (
        f'From your last reply, Leaf would have asked the user "{title}" On Me again, '
        f"in the thread of {question} on {path}, but that thread waits on your reply: "
        f"{owed}. The question is On Me again once you reply there, so Leaf asked "
        "nothing."
    )


def _told(
    path: str,
    title: str,
    text: str,
    passage: str,
    record: dict,
    again: str,
    found: list,
) -> str:
    """The line telling the agent what Leaf put On Me as its own, where (a new
    thread, or the thread of the question `again` it asks again), what Leaf noted
    beside it (`found`), and whether a widget in it asks or the user's reply answers
    it."""
    from leaf.log.obligations import question_ids

    if record["kind"] == "reply":
        if "obligation" in record:
            # In words: under the question's own id, or the reply's where it asks a
            # choice's question anew.
            [question] = question_ids(record)
            put = (
                f" again, as {question}, with your message {record['id']} in its thread"
            )
        else:
            question = f"message:{again.removeprefix('message:')}"
            put = (
                f" again, with your message {record['id']} in the thread of {question}"
            )
        put += f" on {path}, which reopens the thread if it was closed"
    else:
        where = f'"{passage}" in {path}' if "anchor" in record else f"{path} as a whole"
        put = (
            f", in a new thread {'quoting' if 'anchor' in record else 'on'} {where}, "
            f"opened by your message {record['id']}"
        )
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    answer = (
        "the user's reply reaches you as any reply does"
        if record.get("obligation")
        else "the user's answer in its widget reaches you as any answer does"
    )
    withdraw = f"leaf thread resolve {path} {record['id']}"
    noted = "".join(f"{finding}.\n" for finding in found)
    return (
        f'From your last reply, Leaf asked the user "{title}" On Me{put}:\n{quoted}\n'
        f"{noted}It is yours like any message you write: {answer}, and if it isn't "
        f"theirs to decide, resolve its thread with `{withdraw}`, and ask it another "
        "way if you'd rather."
    )


def _held(session_id: str) -> list[dict]:
    held = QUEUED.read(session_file(session_id, QUEUED.kind))
    return held["lines"] if held else []


def queued(session_id: str) -> list[str]:
    """The lines queued for the session's next step (`QUEUED`)."""
    return [held["line"] for held in _held(session_id)]


def waking(session_id: str) -> list[str]:
    """The queued lines that tell the session of work it now owes, which wake it
    while it is idle (`queue`'s `wake`)."""
    return [held["line"] for held in _held(session_id) if held["wake"]]


def heard(session_id: str, lines: list[str]) -> None:
    """Take `lines`, which a hook handed the agent, off the queue, each once; lines
    queued since stay for the next step."""
    if not lines:
        return
    path = session_file(session_id, QUEUED.kind)
    with flocked(session_lock_path(session_id)):
        held = QUEUED.read(path) or {"lines": []}
        rest = list(held["lines"])
        for line in lines:
            at = next(
                (i for i, entry in enumerate(rest) if entry["line"] == line), None
            )
            if at is not None:
                del rest[at]
        if rest:
            QUEUED.write(path, {"lines": rest})
        else:
            QUEUED.remove(path)
