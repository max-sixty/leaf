"""`WorkReading`: the to-dos, obligations, plan and workflows one document and its log hold.

Its readings come from the event log, one revision's document and registry, and
the current validated data publications for record obligations.
Admission builds it against the newest revision, under the registry of the page that
sent the event (`event_meaning.AdmissionReadings`), serving against
the active revision (`served_state.work`), and a view pinned to an older revision
calls `viewing` to read the same log under that revision's registry. It knows
nothing about whether a session is live: `activity` adds that once, in
`served_state.work`, and transports read the result without building the browser's
state. A `WorkReading` lasts for one transaction and is never written to disk.
"""

from functools import cached_property

from .document_reading import read_document
from .events import build_threads
from .obligations import collection, thread_obligation_readings, user_task_obligations
from .plans import plan_reading
from .projection import frozen_thread_reading
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
        data=None,
    ):
        self.events = events
        self.registry = registry
        self.page = page
        self.data = data or {"sources": {}}
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
        own registry, so their decisions, the obligations they answer and the attention those
        obligations give a thread are classified under it, as the page's own are. The threads
        themselves fold as every reading of them does, under the published page's
        containment (`events.build_threads`)."""
        if page is self.page:
            return self
        return WorkReading(
            self.events,
            page.registry,
            page,
            within=self.within,
            log=self.log,
            data=self.data,
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
    def thread_obligations(self) -> dict:
        return thread_obligation_readings(
            self.events,
            self.registry,
            self.threads,
            self.log,
            reading=self.thread,
            data=self.data,
        )

    @cached_property
    def all_obligations(self) -> dict:
        return collection(
            [
                *(self.document.items["all"] if self.document is not None else []),
                *self.thread_obligations["all"],
                *user_task_obligations(self.log, self.thread),
            ]
        )

    @cached_property
    def document(self):
        return (
            read_document(self.page, self.threads, self.log, data=self.data)
            if self.page is not None
            else None
        )

    @cached_property
    def _handover(self):
        from .workflows import handed_over

        return handed_over(
            self.threads,
            self.thread if self.page is not None else None,
            page=self.page,
            events=self.events,
            todo_reading=self.log,
            items=self.all_obligations,
        )

    @property
    def workflows(self) -> list[dict]:
        """Every unsettled update's delivery, each naming the record it serves."""
        return self._handover.workflows

    @property
    def updates(self) -> dict:
        """The obligations the user's updates publish (`workflows.handed_over`), as an
        `obligations.collection`. They are read beside `all_obligations`, which they
        depend on: whether a widget's obligation is answered decides whether an action
        on it is owed."""
        return self._handover.records

    @cached_property
    def plan(self) -> dict | None:
        return plan_reading(
            self.events, self.log.withdrawn, self.log.todos, self.all_obligations["all"]
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
