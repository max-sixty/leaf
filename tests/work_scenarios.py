"""The work-state scenarios: S1–S15 of `notes/what-needs-you/research.md`, each built
as a real page log through the commands and doors a session uses.

A scenario is a generator over a `Stage`, the page one Claude Code session (`s1`)
holds. It makes its moves and yields a `Checkpoint` at each moment the user would
look, so a reader takes the page's reading there: the served state, the Stop hook's
hold, the words each surface says. A checkpoint's `after` reads the page that long
after its last move, which is how a start goes quiet or an update stays undelivered
without a test waiting.

`SCENARIOS` lists them; a builder's docstring says what its real log leaves out of
its story. `L` holds the liveness cases the research's catalogue has none of
(`notes/threads.md`, "Shared evidence"): an update nobody delivered, a turn that
stopped over one, a start gone quiet, a dialog in the agent's own window, and work a
session leaves running in the background.
"""

import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple
from unittest import mock

from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_command,
    delivered_ref,
    last_deliverable_seq,
    neighbour_page,
    publish,
    receive_through,
    serving,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import leases as leases_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as state_model
from leaf.served_state.page import full_state

SESSION = "s1"


class Checkpoint(NamedTuple):
    """One moment the user would look at the page: `name` within its scenario, `story`
    what just happened in the user's terms, `after` how long after the last move the
    page is read, and `pages` any further pages the moment spans."""

    name: str
    story: str
    after: timedelta = timedelta()
    pages: tuple[Path, ...] = ()


def clock(after: timedelta) -> str | None:
    """The moment a checkpoint is read at: now, or `after` from now."""
    if not after:
        return None
    return (datetime.now().astimezone() + after).isoformat(timespec="milliseconds")


def served(page: Path, after: timedelta = timedelta()) -> dict:
    """The reading `/api/state` serves of `page`, `after` from now."""
    return full_state(page, events_model.read_events(page), now=clock(after))


class Scenario(NamedTuple):
    key: str
    title: str
    build: Callable[["Stage"], Iterator[Checkpoint]]


def _ask(identity: str, question: str, first: str, second: str) -> str:
    return (
        f'<div id="{identity}-decision"><h3>{question}</h3>'
        f'<lf-options id="{identity}" choose>'
        f'<lf-option id="{identity}-a"><strong>{first}</strong></lf-option>'
        f'<lf-option id="{identity}-b"><strong>{second}</strong></lf-option>'
        "</lf-options></div>"
    )


NOTES = '<section id="notes"><h2>Notes</h2><p>Working notes.</p></section>'


def page_with(*asks: str, chosen: tuple[str, ...] = ()) -> str:
    """The fixture page with `asks` in place of its options, each an `_ask`, and a
    Notes section after them: a comment on a section that holds an Ask is about that
    Ask (`obligations.thread_topics`), so a comment about anything else goes on
    `notes`. `chosen` names the options a version records as picked."""
    body = "\n".join(asks)
    for option in chosen:
        body = body.replace(
            f'<lf-option id="{option}">', f'<lf-option id="{option}" chosen>'
        )
    start = PAGE.index('  <div id="plan-choice-decision">')
    end = PAGE.index("</section>") + len("</section>")
    return PAGE[:start] + body + "\n</section>\n" + NOTES + PAGE[end:]


class Stage:
    """The page session `s1` holds, with the moves a scenario makes on it. Every move
    goes through the door its real writer uses: the user's through admission
    (`append_command`), the agent's through `leaf`, delivery through a received
    delivery, and a turn's edges through the session record its hooks write."""

    def __init__(self, page: Path, tmp_path: Path):
        self.page = page
        self.tmp_path = tmp_path
        self._leases: list = []
        self._revisions = 0
        serving(page, 1)

    # ---------- the page ----------
    def publish(self, markup: str | None = None, text: str = "published") -> dict:
        if markup is not None:
            (self.page / "index.html").write_text(markup)
        return publish(self.page, text)

    def revise(self, text: str) -> dict:
        """Stamp a version whose markup differs from the last by one paragraph."""
        source = self.page / "index.html"
        self._revisions += 1
        markup = source.read_text().replace(
            "</section>", f"<p>Revision {self._revisions}.</p>\n</section>", 1
        )
        return self.publish(markup, text)

    def publish_row(self, *pages: Path) -> None:
        """Publish each page's row for All pages, as its server does on its clock."""
        for page in (self.page, *pages):
            server_rows_model.RowPublisher(page, "fixture-server").refresh()

    def events(self) -> list:
        return events_model.read_events(self.page)

    # ---------- the user ----------
    def user(self, event: dict) -> dict:
        return append_command(self.page, {"author": "user", "revision": 1, **event})

    def comment(self, text: str, section: str | None = None) -> dict:
        anchor = {"anchor": {"section": section}} if section else {}
        return self.user({"kind": "comment", "text": text, **anchor})

    def answer(self, parent: dict | str, text: str) -> dict:
        root = parent["id"] if isinstance(parent, dict) else parent
        return self.user({"kind": "reply", "parent": root, "text": text})

    def pick(self, widget: str, option: str) -> dict:
        return self.user(
            {
                "kind": "action",
                "widget": widget,
                "action": "choose",
                "detail": {"value": [option]},
            }
        )

    def resolve(self, thread: dict | str) -> dict:
        root = thread["id"] if isinstance(thread, dict) else thread
        return append_command(
            self.page, {"kind": "resolve", "author": "user", "parent": root}
        )

    def read(self, *messages: dict) -> dict:
        return append_command(
            self.page,
            {
                "kind": "read",
                "author": "user",
                "messages": [
                    {"message": message["id"], "version": message["id"]}
                    for message in messages
                ],
            },
        )

    # ---------- the agent ----------
    def leaf(self, *args) -> dict:
        result = CliRunner().invoke(cli_model.cli, [str(arg) for arg in args])
        assert result.exit_code == 0, result.output
        return json.loads(result.output.splitlines()[-1])

    def ref(self, update: dict) -> str:
        return delivered_ref(self.page, update["id"])

    def reply(self, update: dict, text: str, *flags: str) -> dict:
        """Answer a delivered update with `leaf thread reply <answer.ref>`."""
        return self.leaf("thread", "reply", self.ref(update), "--text", text, *flags)

    def say(self, message: dict, text: str, *flags: str) -> dict:
        """Add an agent message under `message`, which answers no update."""
        return self.leaf(
            "thread", "reply", self.page, message["id"], "--text", text, *flags
        )

    def ask(self, text: str, section: str | None = None) -> dict:
        where = ("--section", section) if section else ()
        return self.leaf(
            "thread", "create", self.page, "--text", text, "--obligation", *where
        )

    def todo(self, subject: str, title: str) -> dict:
        return self.leaf("task", "create", self.page, subject, "--title", title)

    def start(self, item: dict | str, line: str) -> dict:
        identity = item["id"] if isinstance(item, dict) else item
        return self.leaf("task", "start", self.page, identity, "--text", line)

    def end(self, item: dict | str, outcome: str, text: str) -> dict:
        identity = item["id"] if isinstance(item, dict) else item
        return self.leaf("task", "end", self.page, identity, outcome, "--text", text)

    def page_open(self) -> dict:
        """`leaf page open`: the handoff that puts down every start."""
        return session_model.cmd_waiting(self.page)

    @contextmanager
    def as_session(self, session: str):
        """Run the moves inside as another Claude Code session, such as a delegate."""
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": session}):
            yield

    # ---------- delivery and the turn ----------
    def deliver(self) -> None:
        """Hand every pending update into the session's turn, opening one."""
        receive_through(self.page, last_deliverable_seq(self.page))

    def turn_opens(self) -> None:
        state_model.open_session_turn(SESSION)

    def turn_ends(self) -> None:
        """The Stop hook closed the turn."""
        state_model.close_session_turn(SESSION)

    def watch(self) -> None:
        """The watch Claude Code's Stop hook leaves between turns holds its lease."""
        path = leases_model.waiter_lease_path(self.page, SESSION)
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = leases_model.take_wait_lease(path)
        assert lease
        self._leases.append(lease)

    def unwatch(self) -> None:
        while self._leases:
            self._leases.pop().close()

    def harness_says(self, status: str) -> None:
        """Claude Code's own session record: `busy`, `waiting` on a dialog, or `idle`."""
        registry = harness_model.claude_code_sessions()
        registry.mkdir(parents=True, exist_ok=True)
        state_model.write_json(
            registry / f"{os.getpid()}.json",
            {
                "pid": os.getpid(),
                "sessionId": SESSION,
                "status": status,
                "statusUpdatedAt": int(time.time() * 1000),
            },
        )

    def close(self) -> None:
        self.unwatch()


# ---------- S1–S15 ----------


def s1(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    stage.watch()
    request = stage.comment("Make the banner quieter.", "plan")
    yield Checkpoint("requested", "The user asked; the agent is between turns.")
    stage.deliver()
    yield Checkpoint("delivered", "The request reached the agent's turn.")
    promise = stage.reply(
        request, "Building now…", "--todo", "Rebuild the banner quieter"
    )
    stage.start(promise, "rebuilding the banner")
    yield Checkpoint("promised", "The agent promised the work and started it.")
    stage.turn_ends()
    yield Checkpoint(
        "turn-ended",
        "The agent's turn ended with a worker still building; nothing says so.",
    )
    yield Checkpoint(
        "turn-ended-later",
        "Twenty minutes on, the work is still out and nothing has renewed it.",
        after=timedelta(minutes=20),
    )
    stage.turn_opens()
    stage.revise("Quieter banner")
    stage.end(promise, "done", "Done — see §3")
    stage.say(promise, "Done — see §3.")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("result", "The result came back in the thread, in a later turn.")


def s2(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    stage.watch()
    question = stage.comment("Why does this use a set?", "plan")
    yield Checkpoint("asked", "The user asked a question.")
    stage.deliver()
    stage.reply(question, "Reading the dedupe step", "--ephemeral")
    yield Checkpoint("in-hand", "The agent said what it is doing about it.")
    answer = stage.reply(
        question, "Order doesn't matter and lookups are O(1).", "--done"
    )
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("answered", "The agent answered; the user hasn't read it.")
    stage.read(answer)
    yield Checkpoint("read", "The user read the answer and left the thread open.")


def s3(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out the answer's way back: no command re-attaches a resolved request to an
    answer, so the agent keeps the work as a to-do it opens on the thread by hand."""
    stage.publish()
    stage.page_open()
    stage.watch()
    request = stage.comment("Ensure we're clear about this in our CLAUDE.md.", "plan")
    yield Checkpoint("requested", "The user asked for something.")
    stage.resolve(request)
    yield Checkpoint(
        "resolved",
        "Nine seconds later they resolved the thread to take it off their list.",
    )
    stage.deliver()
    yield Checkpoint("delivered", "The request and its resolve reached the agent.")
    kept = stage.todo(request["id"], "Say so in CLAUDE.md")
    stage.start(kept, "editing CLAUDE.md")
    yield Checkpoint("kept", "The agent kept the work as a to-do on the thread.")
    stage.end(kept, "done", "CLAUDE.md, “Review” section")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("result", "The work is done; the thread stays resolved.")


def s4(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out the other session's own page and where its result lands: the delegate
    is a second session id starting and ending the to-do."""
    stage.publish()
    stage.page_open()
    stage.watch()
    request = stage.comment("/dispatch -- fix this bug", "plan")
    stage.deliver()
    promise = stage.reply(
        request,
        "Dispatched to its own session.",
        "--todo",
        "Fix the bug (dispatched)",
    )
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("dispatched", "The agent handed the work to another session.")
    with stage.as_session("s2"):
        stage.start(promise, "reproducing the bug")
    yield Checkpoint("delegate-running", "The other session started on it.")
    yield Checkpoint(
        "delegate-quiet",
        "Twenty minutes on, the other session has said nothing more.",
        after=timedelta(minutes=20),
    )
    with stage.as_session("s2"):
        stage.end(promise, "done", "Fixed in its own pull request")
    yield Checkpoint("delegate-done", "The other session finished and ended the to-do.")


def s5(stage: Stage) -> Iterator[Checkpoint]:
    asks = [
        _ask("q1", "Ship the flag first?", "Yes", "No"),
        _ask("q2", "Keep the old export?", "Keep", "Retire"),
        _ask("q3", "Name the job?", "backfill", "replay"),
        _ask("q4", "Notify the team?", "Now", "After"),
    ]
    stage.publish(page_with(*asks))
    stage.page_open()
    stage.watch()
    yield Checkpoint("asked", "The agent raised four questions.")
    stage.pick("q2", "q2-a")
    stage.pick("q3", "q3-b")
    yield Checkpoint("two-answered", "The user answered two: “start with #2 & #3”.")
    stage.deliver()
    stage.publish(page_with(*asks, chosen=("q2-a", "q3-b")), "Took in #2 and #3")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("taken-in", "The agent took those two in; two stay open.")


def s6(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out the reading of one message as three moves, which is the agent's: the
    log holds one comment, one reply with a to-do and one version."""
    ask = _ask("ring", "Add the focus ring?", "Yes", "No")
    stage.publish(page_with(ask))
    stage.page_open()
    stage.watch()
    bundle = stage.comment(
        "ok, yes, let's have the ring; and add a TODO that it may be too strong",
        "ring-decision",
    )
    yield Checkpoint("sent", "One message: a decision, a request and a deferral.")
    stage.deliver()
    stage.reply(
        bundle,
        "Recorded the ring; I've noted that it may be too strong.",
        "--todo",
        "Revisit whether the ring is too strong",
    )
    stage.publish(page_with(ask, chosen=("ring-a",)), "Ring on")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint(
        "read-by-agent",
        "The agent recorded the pick, did the request and kept the deferral.",
    )
    stage.resolve(bundle)
    yield Checkpoint("resolved", "The user resolved the thread; the deferral stays.")


def s7(stage: Stage) -> Iterator[Checkpoint]:
    asks = [
        _ask("a", "Which layout?", "Rail", "Tabs"),
        _ask("b", "Which default?", "Compact", "Roomy"),
        _ask("c", "Which empty state?", "Sketch", "Words"),
    ]
    stage.publish(page_with(*asks))
    stage.page_open()
    stage.watch()
    tradeoffs = stage.comment("what are the tradeoffs?", "a-decision")
    yield Checkpoint("a-asked", "(a) The user asked about an Ask before choosing.")
    stage.deliver()
    stage.reply(tradeoffs, "Rail keeps context; tabs save width.", "--done")
    yield Checkpoint(
        "a-answered", "(a) The agent answered; the Ask is the user's again."
    )
    prose = stage.comment("#1 is fine", "b-decision")
    yield Checkpoint("b-prose", "(b) The user answered an Ask in words.")
    stage.deliver()
    stage.reply(prose, "I've marked the Ask with that choice.", "--done")
    stage.publish(page_with(*asks, chosen=("b-a",)), "Compact by default")
    yield Checkpoint("b-recorded", "(b) The agent recorded the pick for them.")
    sketch = stage.comment("show me a sketch", "c-decision")
    stage.deliver()
    promise = stage.reply(
        sketch, "Drawing both.", "--todo", "Sketch the two empty states"
    )
    stage.start(promise, "sketching the empty states")
    yield Checkpoint("c-promised", "(c) The Ask is blocked on the agent's sketch.")
    stage.end(promise, "done", "Both sketches are under the question")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint(
        "c-delivered", "(c) The sketch landed; the Ask is the user's again."
    )


def s8(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out seven of the ten results: three threads."""
    stage.publish()
    stage.page_open()
    stage.watch()
    answers = []
    for text in ("Tighten the lede.", "Is the cutoff right?", "Drop the appendix."):
        asked = stage.comment(text, "plan")
        stage.deliver()
        answers.append(stage.reply(asked, f"Done: {text.lower()}", "--done"))
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("results", "Three results came back; the user hasn't looked.")
    stage.read(*answers)
    yield Checkpoint("skimmed", "The user skimmed all three and left.")
    yield Checkpoint(
        "three-weeks-later",
        "Three weeks later the threads are as they were left.",
        after=timedelta(days=21),
    )


def s9(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    stage.watch()
    request = stage.comment("Can the export run nightly?", "plan")
    stage.deliver()
    prose = stage.reply(
        request, "It can. Want me to build it on this branch?", "--done"
    )
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint(
        "asked-in-prose", "The agent's reply asks a question it never registered."
    )
    stage.turn_opens()
    stage.say(prose, "Want me to build it on this branch?", "--obligation")
    stage.turn_ends()
    yield Checkpoint("asked", "The same question, registered for the user.")
    stage.answer(request, "yes, go ahead")
    yield Checkpoint("answered", "The user said yes.")


def s10(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    stage.watch()
    asked = stage.ask("Should I rename `tmp` to `scratch`?", "plan")
    stage.turn_ends()
    yield Checkpoint("asked", "The agent asked something that didn't need the user.")
    complaint = stage.answer(asked, "this sort of thing does not need a question!")
    yield Checkpoint("complained", "The user said so.")
    stage.deliver()
    stage.reply(complaint, "Understood, renamed it.", "--done")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("settled", "The agent went ahead.")


def s11(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out eight of the twelve threads: four, one of each kind."""
    stage.publish()
    stage.page_open()
    stage.watch()
    result = stage.comment("Tighten the lede.", "plan")
    stage.deliver()
    stage.reply(result, "Tightened.", "--done")
    promised = stage.comment("Add a glossary.", "plan")
    stage.deliver()
    stage.reply(promised, "Building it next.", "--todo", "Add a glossary")
    question = stage.ask("Merge or abandon the old branch?", "plan")
    unanswered = stage.comment("And fix the footer link.", "plan")
    stage.deliver()
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint(
        "before",
        "Four threads: a result, a promise, a question to the user, a request "
        "the agent has seen and not answered.",
    )
    for thread in (result, promised, question, unanswered):
        stage.resolve(thread)
    yield Checkpoint("swept", "The user resolved all four within three minutes.")


def s12(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out the answer itself: the terminal's words are not in the log."""
    stage.publish()
    stage.page_open()
    stage.watch()
    asked = stage.ask("Should I go ahead with the migration?", "plan")
    stage.turn_ends()
    yield Checkpoint("asked", "The agent asked in a thread.")
    stage.turn_opens()
    stage.end(f"message:{asked['id']}", "done", "Answered in the session: go ahead.")
    stage.turn_ends()
    yield Checkpoint(
        "answered-elsewhere",
        "The user answered in the terminal; the agent recorded it.",
    )


def s13(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    stage.watch()
    request = stage.comment("Move the caveats up.", "plan")
    stage.deliver()
    result = stage.reply(request, "Moved them under the summary.", "--done")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("result", "The agent reported the work done.")
    stage.read(result)
    stage.answer(request, "I thought we agreed to move these up here??")
    yield Checkpoint("rejected", "The user rejected the result.")
    stage.deliver()
    yield Checkpoint("rejection-delivered", "The rejection reached the agent.")


def s14(stage: Stage) -> Iterator[Checkpoint]:
    approve = _ask("approve", "Approve the rollout plan?", "Approve", "Hold")
    stage.publish(page_with(approve))
    stage.page_open()
    stage.watch()
    question = stage.comment("Is the rollback tested?", "notes")
    stage.deliver()
    check = stage.todo("page", "Run the rollback drill")
    stage.start(check, "running the rollback drill")
    yield Checkpoint(
        "open",
        "Approval waits on the user while the agent owes a reply and a drill.",
    )
    stage.reply(question, "Yes, the drill passed just now.", "--done")
    stage.end(check, "done", "Drill log in §4")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("clear", "Only the approval is left.")
    stage.pick("approve", "approve-a")
    yield Checkpoint("approved", "The user approved.")
    stage.deliver()
    stage.publish(page_with(approve, chosen=("approve-a",)), "Approved")
    stage.page_open()
    stage.turn_ends()
    yield Checkpoint("recorded", "The agent recorded the approval.")


def s15(stage: Stage) -> Iterator[Checkpoint]:
    """Leaves out a list across pages: each page serves its neighbours' rows, and the
    second page is a quiet one the same session holds."""
    approve = _ask("approve", "Approve the plan?", "Approve", "Hold")
    stage.publish(page_with(approve))
    stage.page_open()
    stage.watch()
    request = stage.comment("Tighten the lede.", "notes")
    stage.deliver()
    stage.reply(request, "tightening the lede", "--ephemeral")
    other = stage.tmp_path / "other-page"
    neighbour_page(other, title="Billing export")
    service_model.claim_page(other)
    yield Checkpoint(
        "two-pages",
        "One page needs the user and has work under way; a second is quiet.",
        pages=(other,),
    )
    stage.turn_ends()
    stage.unwatch()
    yield Checkpoint(
        "one-stopped",
        "The first page's turn ended over the request, with nothing watching.",
        pages=(other,),
    )


def liveness(stage: Stage) -> Iterator[Checkpoint]:
    stage.publish()
    stage.page_open()
    request = stage.comment("Tighten the lede.", "plan")
    yield Checkpoint(
        "undelivered",
        "Five minutes on, nothing has picked the update up.",
        after=timedelta(minutes=5),
    )
    stage.deliver()
    stage.turn_ends()
    yield Checkpoint("stopped", "The turn that took the update ended over it.")
    stage.turn_opens()
    stage.start(request, "cutting the lede")
    yield Checkpoint("running", "A later turn started it.")
    yield Checkpoint(
        "quiet",
        "Twenty minutes on, the turn has said nothing more.",
        after=timedelta(minutes=20),
    )
    stage.start(request, "cutting the lede")
    stage.answer(request, "Keep the first sentence.")
    yield Checkpoint(
        "follow-up",
        "The user added a message while the first is in hand.",
    )
    stage.deliver()
    stage.harness_says("waiting")
    yield Checkpoint("dialog", "The agent's own window holds an approval dialog.")
    stage.harness_says("busy")
    stage.page_open()
    yield Checkpoint("put-down", "The agent handed the page over with the work parked.")
    stage.start(request, "cutting the lede")
    stage.harness_says("busy")
    stage.turn_ends()
    yield Checkpoint(
        "background",
        "The turn ended while the session's background workers run on.",
    )
    stage.harness_says("idle")
    yield Checkpoint("background-ended", "The workers finished; nobody answered.")


SCENARIOS = {
    scenario.key: scenario
    for scenario in (
        Scenario("S1", "Request → promise → result", s1),
        Scenario("S2", "Question → answer", s2),
        Scenario("S3", "Hand-off resolve", s3),
        Scenario("S4", "Dispatch", s4),
        Scenario("S5", "Multi-question, partial answer", s5),
        Scenario("S6", "Bundle", s6),
        Scenario("S7", "Thread around an Ask", s7),
        Scenario("S8", "Read-and-leave, return later", s8),
        Scenario("S9", "Agent-initiated question in prose", s9),
        Scenario("S10", "Over-asking", s10),
        Scenario("S11", "Sweep", s11),
        Scenario("S12", "Answer in another channel", s12),
        Scenario("S13", "Misunderstanding", s13),
        Scenario("S14", "Sign-off", s14),
        Scenario("S15", "Many pages", s15),
        Scenario("L", "Liveness", liveness),
    )
}
