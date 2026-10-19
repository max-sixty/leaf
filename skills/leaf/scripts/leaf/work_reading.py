"""`WorkReading`: the to-dos, asks, plan and workflows one document and its log hold.

Its readings come from the event log and one revision's document and registry.
Admission builds it against the newest revision, under the registry of the page that
sent the event (`event_meaning.AdmissionReadings`), serving against
the active revision (`served_state.work`), and a view pinned to an older revision
calls `viewing` to read the same log under that revision's registry. It knows
nothing about whether a session is live: `activity` adds that once, in
`served_state.work`, and transports read the result without building the browser's
state. A `WorkReading` lasts for one transaction and is never written to disk.
"""

from functools import cached_property

from .items import collection, replied, thread_item_readings
from .document_reading import read_document
from .events import approvals_in_force, build_threads
from .plans import plan_reading
from .projection import frozen_thread_reading
from .read_state import content_version
from .todos import TodoReading


class WorkReading:
    def __init__(
        self,
        events: list,
        registry: dict,
        page=None,
        *,
        within=None,
        thread=None,
        log=None,
    ):
        self.events = events
        self.registry = registry
        self.page = page
        # The published page's containment, which every fold of the threads takes,
        # whichever revision's document this reading reads them beside.
        self.within = (
            within if within is not None else page.within if page is not None else {}
        )
        self.log = log or TodoReading(events)
        self._thread = thread

    def viewing(self, page) -> "WorkReading":
        """This log read beside another revision's document, as a view pinned to that
        revision shows it. That revision captured its frozen thread widgets under its
        own registry, so their decisions, the asks they answer and the attention those
        asks give a thread are classified under it, as the page's own are. The threads
        themselves fold as every reading of them does, under the published page's
        containment (`events.build_threads`)."""
        if page is self.page:
            return self
        return WorkReading(
            self.events, page.registry, page, within=self.within, log=self.log
        )

    @cached_property
    def threads(self) -> dict:
        return build_threads(self.events, self.within, withdrawn=self.log.withdrawn)

    @cached_property
    def thread(self):
        return (
            self._thread
            if self._thread is not None
            else frozen_thread_reading(
                self.events, self.registry, withdrawn=self.log.withdrawn
            )
        )

    @cached_property
    def widget_items(self) -> dict:
        return thread_item_readings(
            self.events,
            self.registry,
            self.threads,
            self.log.ends,
            reading=self.thread,
        )

    @property
    def items(self) -> dict:
        return self.widget_items

    @cached_property
    def prompts(self) -> dict:
        """Each thread's question the user owes words to: the latest open
        reply-answered ask on them there, by its message and that message's content
        version, which the thread's head marks Waiting on me."""
        prompts = {}
        for item in self.widget_items["user"]:
            if not replied(self.registry[item["source"]["tag"]]):
                continue
            message = next(
                message
                for message in self.threads[item["thread"]]["msgs"]
                if message["id"] == item["message"]
            )
            held = prompts.get(item["thread"])
            if held is None or held[0]["seq"] < message["seq"]:
                prompts[item["thread"]] = (message, item)
        return {
            thread: {"message": message["id"], "version": content_version(message)}
            for thread, (message, _item) in prompts.items()
        }

    @cached_property
    def all_items(self) -> dict:
        return collection(
            [
                *(self.document.items["all"] if self.document is not None else []),
                *self.items["all"],
            ]
        )

    @cached_property
    def approvals(self) -> list[dict]:
        return approvals_in_force(self.events, withdrawn=self.log.withdrawn)

    @cached_property
    def document(self):
        return (
            read_document(self.page, self.threads, self.log.ends)
            if self.page is not None
            else None
        )

    @cached_property
    def workflows(self) -> list[dict]:
        from .workflows import canonical_workflows

        return canonical_workflows(
            self.threads,
            self.thread if self.page is not None else None,
            page=self.page,
            events=self.events,
            todo_reading=self.log,
            items=self.all_items,
        )

    @cached_property
    def plan(self) -> dict | None:
        return plan_reading(
            self.events, self.log.withdrawn, self.log.todos, self.all_items["all"]
        )

    def page_todos(self, aged: list[dict]) -> list[dict]:
        """Every to-do, open and ended, with its thread, and an open one's activity
        as `aged` (`activity._canonical_todos`) reads it."""
        by_id = {todo["id"]: todo for todo in aged}
        return [
            {
                **by_id.get(todo["id"], todo),
                "thread": self.thread.subject_thread(todo["subject"]),
            }
            for todo in self.log.todos
        ]
