"""The durable work reading of one document and admitted log.

To-dos, frozen thread asks, and exact-input workflows share one event basis.
Admission constructs it under the sending vocabulary; serving constructs it under
its active document, and each view of a pinned revision under that revision's
(`viewing`). Neither adds claim liveness: activity enriches these facts
once, and transports select that enriched reading without constructing a browser.
This object is transaction-scoped and never written to disk.
"""

from functools import cached_property

from .asks import collection, thread_ask_readings, thread_asks
from .document_reading import read_document
from .events import build_threads, standing_approvals
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
    def widget_asks(self) -> dict:
        return thread_ask_readings(
            self.events,
            self.registry,
            {identity for identity, held in self.threads.items() if held["resolved"]},
            reading=self.thread,
        )

    @cached_property
    def thread_asks(self) -> dict:
        open_widget_threads = {ask["thread"] for ask in self.widget_asks["user"]}
        return {
            identity: thread_asks(
                identity,
                held,
                self.registry,
                self.thread.structure,
                open_widget_threads,
                self.log.ends,
            )
            for identity, held in self.threads.items()
        }

    @cached_property
    def asks(self) -> dict:
        return collection(
            [
                *self.widget_asks["all"],
                *(ask for reading in self.thread_asks.values() for ask in reading.asks),
            ]
        )

    @cached_property
    def all_asks(self) -> dict:
        return collection(
            [
                *(self.document.asks["all"] if self.document is not None else []),
                *self.asks["all"],
            ]
        )

    @property
    def prompts(self) -> dict:
        return {
            identity: reading.prompt
            for identity, reading in self.thread_asks.items()
            if reading.prompt is not None
        }

    @cached_property
    def approvals(self) -> list[dict]:
        return standing_approvals(self.events, withdrawn=self.log.withdrawn)

    @cached_property
    def document(self):
        return read_document(self.page, self.threads) if self.page is not None else None

    @cached_property
    def workflows(self) -> list[dict]:
        from .workflows import canonical_workflows

        return canonical_workflows(
            self.threads,
            self.thread if self.page is not None else None,
            page=self.page,
            events=self.events,
            todo_reading=self.log,
            asks=self.all_asks,
        )

    def page_todos(self, aged: list[dict] = ()) -> tuple[list[dict], list[dict]]:
        """To-dos enriched with their thread and current activity."""
        by_id = {todo["id"]: todo for todo in aged}
        log = [
            {
                **by_id.get(todo["id"], todo),
                "thread": self.thread.subject_thread(todo["subject"]),
            }
            for todo in self.log.todos
        ]
        return (
            [todo for todo in log if todo["state"] == "open"],
            [todo for todo in log if todo["state"] != "open"],
        )
