"""What Leaf derives about a logged event beyond its stored fields, read the same
way wherever an event is reported.

A delivery adds these facts to each event it carries, and `leaf page state` adds
them to each event it prints: every action in force, and every message in a
thread it reads, as the message now reads. So a session that missed a delivery,
or compacted after it, reads what the delivery told the agent, under the same
names (root `AGENTS.md`, "Validate once and share readings"). What a delivery asks
of the agent at the time, its `answer`, `handling`, `waiting` and `settled`, is the
delivery's own.

- `subject`: what the event changes, a widget, a thread or the page.
- `threads`: every thread whose history the event changes
  (`thread_context.thread_memberships`).
- `says` and `names`: the elements a gesture names, in the words and names of the
  document it was made in (`GestureWords`).
- `was`, with `suggestion` where it applies: on the user's rewrite of their own
  message, the words it replaced, as the message read when the user made it
  (`message_at`). A message read as it now reads keeps its latest rewrite's in
  `edited` instead.
- `unsent`: on the user's message or rewrite about a widget, the work they hadn't
  sent there when they wrote (`thread_context.unsent_at_messages`). A message read
  as it now reads takes it from its latest rewrite.

`threads` and `unsent` read which widgets sit inside which in the live page, so
a later version that moves a playground's preview out of the playground changes
what an earlier message about the preview was about.

A message as its thread held it at an earlier place in the log (`message_at`) is
read here too, for a reader that reports the message as it was then: the line saying
which messages a version was saved after (`provenance.saved_after`).

`_DELIVERED_EVENT` in `delivery.py` declares each field. A page whose registry
doesn't load still has its events reported, without the facts that need the
registry: `says`, `names` and `unsent`.
"""

from functools import cached_property
from pathlib import Path
from typing import Any

from .events import message_reading, rewritten
from .gesture_words import GestureWords, revisions_on_disk
from .read_state import content_version
from .registry.kernel import verb_writers
from .revision_artifact import active_enclosing
from .thread_context import (
    thread_memberships,
    thread_names,
    thread_structure,
    thread_widgets,
    unsent_at_messages,
)


def _subject(event: dict, threads: list[str], by_id: dict[str, dict]) -> dict:
    """Name what one event changes without using prose as an identifier."""
    if event["kind"] in verb_writers():
        return {"kind": "widget", "id": event["widget"]}
    if event["kind"] == "undo":
        original = by_id.get(event["undoes"])
        if original is not None:
            return _subject(original, threads, by_id)
    if threads:
        return {"kind": "thread", "id": threads[0]}
    return {"kind": "page"}


class EventFacts:
    """The facts of any events of one page's log, sharing the readings they take.

    Call it with events of `events`, or messages `build_threads` folded from them,
    for their facts by id. `registry` is the page's active one, or None where it
    doesn't load. A reader that already holds the log's `thread_memberships`, such as
    the served state, passes them rather than have them walked again."""

    def __init__(
        self,
        page_dir: Path,
        events: list[dict],
        registry: dict | None,
        memberships: dict[str, list[str]] | None = None,
    ):
        self.page_dir = page_dir
        self.events = events
        self.registry = registry
        self.by_id = {event["id"]: event for event in events}
        if memberships is not None:
            self._memberships = memberships

    @cached_property
    def within(self) -> dict:
        """The published page's containment, which threads anchored on the page
        read their widgets by."""
        return active_enclosing(self.page_dir)

    @cached_property
    def _memberships(self) -> dict[str, list[str]]:
        names = thread_names(self.events)
        return thread_memberships(
            self.events,
            names,
            thread_widgets(thread_structure(self.events), names),
            self.within,
        )

    @cached_property
    def _rewrites(self) -> dict[str, list[dict]]:
        """Each message's rewrites, in log order."""
        found: dict[str, list[dict]] = {}
        for event in self.events:
            if event["kind"] == "edit":
                found.setdefault(event["message"], []).append(event)
        return found

    @cached_property
    def _undos(self) -> dict[str, dict]:
        """Each gesture taken back, and the undo that took it."""
        return {event["undoes"]: event for event in self.events if event.get("undoes")}

    def message_at(self, message: str, place: int) -> dict:
        """The message `message` as its thread held it just before the log's `place`
        (`events.message_reading`): taken back, if it was by then, else as sent with
        each rewrite of it made before that place and not taken back by then
        (`events.rewritten`), a rewrite to no words leaving it deleted. Whatever came
        of it since, its thread reads it so there, as a fold of the log up to that
        place does (`events.build_threads`)."""

        def before(identity: str) -> dict | None:
            undo = self._undos.get(identity)
            return undo if undo is not None and undo["seq"] < place else None

        if (undo := before(message)) is not None:
            return message_reading(self.by_id[message], undo)
        reading = message_reading(self.by_id[message], None)
        for edit in self._rewrites.get(message, ()):
            if edit["seq"] >= place:
                break
            if before(edit["id"]) is None:
                reading |= rewritten(reading, edit)
        return reading

    @cached_property
    def _words(self) -> GestureWords | None:
        # What an element says is a registry's word, and a page whose active layer
        # does not read is not read for its words at all.
        if self.registry is None:
            return None
        return GestureWords(
            self.events, self.registry, revisions_on_disk(self.page_dir)
        )

    def __call__(self, inputs: list[dict]) -> dict[str, dict[str, Any]]:
        words = self._words
        unsent = (
            unsent_at_messages(
                self.events,
                [self.by_id[content_version(event)] for event in inputs],
                self.within,
                words.records_unsent,
            )
            if words is not None
            else {}
        )
        found = {}
        for event in inputs:
            threads = self._memberships.get(event["id"], [])
            facts: dict[str, Any] = {
                "subject": _subject(event, threads, self.by_id),
                "threads": threads,
            }
            if words is not None and (says := words.says(event)):
                facts["says"] = says
                facts["names"] = {
                    identity: words.name(event, identity) for identity in says
                }
            # The agent answering a rewrite needs to see what it replaced, the words
            # its message had as the user made it, and whether those words are a
            # suggestion's exact replacement text.
            if (
                event["kind"] == "edit"
                and event["author"] != "agent"
                and "withdrawn"
                not in (replaced := self.message_at(event["message"], event["seq"]))
            ):
                facts["was"] = replaced["text"]
                if replaced.get("suggestion"):
                    facts["suggestion"] = True
            if work := unsent.get(content_version(event)):
                facts["unsent"] = work
            found[event["id"]] = facts
        return found
