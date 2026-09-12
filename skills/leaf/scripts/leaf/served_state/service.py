"""Transport-neutral reads of one page's browser projection."""

from pathlib import Path

from .. import presence as presence_model
from ..event_log import now_iso
from ..files import active_descriptor, missing_revision
from ..revisioning import activate_source
from ..service import PageTransaction
from . import browser as served_browser
from . import page as served_page
from . import reading as served_reading


class PageStateService:
    """The state transaction shared by HTTP and MCP transports.

    Activation, the reading token, and the projected state are taken under one
    page transaction. Neighbour discovery follows after the transaction because
    other pages are independent authorities and must not hold this page's writers.
    """

    def __init__(
        self,
        page_dir: Path,
        *,
        page_snapshot=None,
        layer_identity: dict | None = None,
        preview: dict | None = None,
        publication: dict | None = None,
    ):
        self.page_dir = page_dir
        self.page_snapshot = page_snapshot
        self.layer_identity = layer_identity
        self.preview = preview
        self.publication = publication

    def _full_state(
        self,
        events: list,
        source_error: str | None = None,
        view_revision: int | None = None,
    ) -> dict:
        active_override = None
        snapshot = self.page_snapshot
        if snapshot is not None:
            active_override = snapshot.active
        return served_page.full_state(
            self.page_dir,
            events,
            layer_identity=self.layer_identity,
            preview=self.preview,
            publication=self.publication,
            source_error=source_error,
            view_revision=view_revision,
            active_override=active_override,
            documents_override=snapshot.documents if snapshot is not None else None,
            registry_override=snapshot.registry if snapshot is not None else None,
            data_override=snapshot.browser_data if snapshot is not None else None,
            versions_override=snapshot.versions if snapshot is not None else None,
            presence_override=snapshot.presence if snapshot is not None else None,
            live_stream_override=snapshot.live_stream if snapshot is not None else None,
            now_override=snapshot.now if snapshot is not None else None,
            taken_override=snapshot.taken if snapshot is not None else None,
        )

    def page_state(
        self,
        view_revision: int | None = None,
    ) -> dict:
        if self.page_snapshot is None:
            with PageTransaction(self.page_dir) as page:
                activation = activate_source(self.page_dir, page.events)
                reading = served_reading.page_reading(self.page_dir)
                state = self._full_state(
                    page.events, activation.error, view_revision=view_revision
                )
        else:
            reading = self.page_snapshot.reading
            state = self._full_state(
                list(self.page_snapshot.events), view_revision=view_revision
            )
        state["others"] = (
            list(self.page_snapshot.others)
            if self.page_snapshot is not None
            else presence_model.other_leaves(self.page_dir)
        )
        state["reading"] = (
            self.page_snapshot.reading
            if self.page_snapshot is not None
            else reading
            + "."
            + presence_model.presence_fingerprint(
                state["listening"], state["session_alive"], state["others"]
            )
        )
        return state

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        if self.page_snapshot is None:
            with PageTransaction(self.page_dir) as page:
                activate_source(self.page_dir, page.events)
                active = active_descriptor(self.page_dir, page.events)
                if active is None:
                    raise ValueError(missing_revision(self.page_dir))
                events = page.events
                documents_override = None
                registry_override = None
        else:
            active = self.page_snapshot.active
            events = list(self.page_snapshot.events)
            documents_override = self.page_snapshot.documents
            registry_override = self.page_snapshot.registry
        latest_seq = events[-1]["seq"] if events else 0
        if through_seq > latest_seq:
            raise ValueError(
                f"view sequence {through_seq} is newer than log sequence {latest_seq}"
            )
        events = [event for event in events if event["seq"] <= through_seq]
        present = (
            self.page_snapshot.presence
            if self.page_snapshot is not None
            else presence_model.presence(self.page_dir, events)
        )
        projected = served_browser.project_browser_state(
            self.page_dir,
            events,
            view_revision,
            active,
            present,
            now_iso(),
            documents_override=documents_override,
            registry_override=registry_override,
            include_active_view=False,
        )
        if projected is None:
            raise ValueError("page registry cannot be projected")
        # Activity belongs to the complete state reading, not a historical
        # document-view fetch. Keep one public route for the canonical answer.
        projected.pop("activity", None)
        return projected
