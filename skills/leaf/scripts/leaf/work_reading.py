"""The durable work reading of one document and admitted log.

Tasks, frozen thread questions, and exact-input workflows share one event basis.
Admission constructs it under the sending vocabulary; serving constructs it under
its active document. Neither adds claim liveness: activity enriches these facts
once, and transports select that enriched reading without constructing a browser.
This object is transaction-scoped and never written to disk.
"""

from functools import cached_property

from .document_reading import read_document
from .events import build_threads, standing_approvals
from .projection import frozen_thread_reading
from .questions import collection, thread_question_readings, thread_questions
from .tasks import TaskReading


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
    def widget_questions(self) -> dict:
        return thread_question_readings(
            self.events,
            self.registry,
            {identity for identity, held in self.threads.items() if held["resolved"]},
            reading=self.thread,
        )

    @cached_property
    def thread_questions(self) -> dict:
        open_widget_threads = {
            question["thread"] for question in self.widget_questions["user"]
        }
        return {
            identity: thread_questions(
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
    def questions(self) -> dict:
        return collection(
            [
                *self.widget_questions["all"],
                *(
                    question
                    for reading in self.thread_questions.values()
                    for question in reading.questions
                ),
            ]
        )

    @cached_property
    def all_questions(self) -> dict:
        return collection(
            [
                *(self.document.questions["all"] if self.document is not None else []),
                *self.questions["all"],
            ]
        )

    @property
    def prompts(self) -> dict:
        return {
            identity: reading.prompt
            for identity, reading in self.thread_questions.items()
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
            task_reading=self.log,
            questions=self.all_questions,
        )

    def page_tasks(self, aged: list[dict] = ()) -> tuple[list[dict], list[dict]]:
        """Explicit tasks enriched with their thread and current activity."""
        by_id = {task["id"]: task for task in aged}
        log = [
            {
                **by_id.get(task["id"], task),
                "thread": self.thread.subject_thread(task["subject"]),
            }
            for task in self.log.tasks
        ]
        selected = [
            {**task, "ends": "agent" if task["owner"] == "agent" else "done"}
            for task in log
        ]
        return (
            [task for task in selected if task["state"] == "open"],
            [task for task in selected if task["state"] != "open"],
        )
