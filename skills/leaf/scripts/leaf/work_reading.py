"""The durable work reading of one document and admitted log.

Tasks, frozen thread questions, and exact-input workflows share one event basis.
Admission constructs it under the sending vocabulary; serving constructs it under
its active document, and each view of a pinned revision under that revision's
(`viewing`). Neither adds claim liveness: activity enriches these facts
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
        self,
        events: list,
        registry: dict,
        page=None,
        *,
        within=None,
        thread=None,
        log=None,
        document=None,
    ):
        self.events = events
        self.registry = registry
        self.page = page
        # The published page's containment, which every fold of the threads takes,
        # whichever revision's document this reading reads them beside.
        self.within = (
            within if within is not None else page.within if page is not None else {}
        )
        self.log = log or TaskReading(events)
        self._thread = thread
        self._document = document

    def supposing(self, gestures: list[dict]) -> "WorkReading":
        """This reading with `gestures` appended to its log, for asking what they would
        leave in the threads they stand in. They carry no markup and name no task, so
        the frozen thread document is this reading's own, and so is the task log
        unless one takes a message back, which changes what the log has withdrawn.
        The page document is this reading's own too: what they could change there, a
        page Ask seated in a thread they reopen, stands in no thread's reading."""
        events = [*self.events, *gestures]
        return WorkReading(
            events,
            self.registry,
            self.page,
            within=self.within,
            thread=self.thread,
            log=self.log
            if not any(gesture.get("undoes") for gesture in gestures)
            else TaskReading(events),
            document=self.document,
        )

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
        if self._document is not None:
            return self._document
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
        return (
            [task for task in log if task["state"] == "open"],
            [task for task in log if task["state"] != "open"],
        )
