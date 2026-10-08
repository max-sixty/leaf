"""The durable work reading of one document and admitted log.

Tasks, frozen thread questions, and exact-input workflows share one event basis.
Admission constructs it under the sending vocabulary; serving constructs it under
its active document. Neither adds claim liveness: activity enriches these facts
once, and transports select that enriched reading without constructing a browser.
This object is transaction-scoped and never written to disk.
"""

from functools import cached_property

from .asks import thread_ask_readings, thread_awaits_user
from .document_reading import read_document
from .events import build_threads
from .projection import frozen_thread_reading
from .tasks import TaskReading, page_tasks


class WorkReading:
    def __init__(
        self, events: list, registry: dict, page=None, *, thread=None, log=None
    ):
        self.events = events
        self.registry = registry
        self.page = page
        self.log = log or TaskReading(events)
        self._thread = thread

    @cached_property
    def threads(self) -> dict:
        return build_threads(
            self.events,
            self.page.within if self.page is not None else {},
            withdrawn=self.log.withdrawn,
        )

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
    def asks(self) -> dict:
        return thread_ask_readings(
            self.events,
            self.registry,
            {identity for identity, held in self.threads.items() if held["resolved"]},
            reading=self.thread,
        )

    @cached_property
    def questions(self) -> dict:
        open_asks = {ask["thread"] for ask in self.asks["user"]}
        ended = set(self.log.ends)
        return {
            identity: thread_awaits_user(
                identity,
                held,
                self.registry,
                self.asks["awaiting"],
                self.thread.structure,
                open_asks,
                ended,
            )
            for identity, held in self.threads.items()
        }

    @property
    def prompts(self) -> dict:
        return {
            identity: prompt
            for identity, (_awaiting, prompt) in self.questions.items()
            if prompt is not None
        }

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
            task_reading=self.log,
        )

    def page_tasks(self, aged: list[dict] = ()) -> tuple[list[dict], list[dict]]:
        """Tasks beside document Asks; activity may supply the aged agent tasks."""
        by_id = {task["id"]: task for task in aged}
        log = [
            {
                **by_id.get(task["id"], task),
                "thread": self.thread.subject_thread(task["subject"]),
            }
            for task in self.log.tasks
        ]
        return page_tasks(
            log,
            self.asks,
            self.threads,
            self.prompts,
            self.log.ends,
            self.registry.get("$reactions", {}).get("tokens", {}),
        )
