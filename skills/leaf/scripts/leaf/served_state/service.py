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
        preview_source: dict | None = None,
        layer_identity: dict | None = None,
        preview: dict | None = None,
        example: dict | None = None,
    ):
        self.page_dir = page_dir
        self.preview_source = preview_source
        self.layer_identity = layer_identity
        self.preview = preview
        self.example = example

    def _full_state(
        self,
        events: list,
        source_error: str | None = None,
        view_revision: int | None = None,
    ) -> dict:
        active_override = None
        source_overrides = None
        if self.preview_source is not None:
            active_override = self.preview_source["active"]
            source_overrides = {
                active_override["revision"]: self.preview_source["data"].decode("utf-8")
            }
        return served_page.full_state(
            self.page_dir,
            events,
            layer_identity=self.layer_identity,
            preview=self.preview,
            example=self.example,
            source_error=source_error,
            view_revision=view_revision,
            active_override=active_override,
            source_overrides=source_overrides,
        )

    def page_state(
        self,
        view_revision: int | None = None,
    ) -> dict:
        with PageTransaction(self.page_dir) as page:
            if self.preview_source is None:
                activation = activate_source(self.page_dir, page.events)
                reading = served_reading.page_reading(self.page_dir)
                state = self._full_state(
                    page.events, activation.error, view_revision=view_revision
                )
            else:
                reading = served_reading.page_reading(self.page_dir)
                state = self._full_state(page.events, view_revision=view_revision)
        state["others"] = presence_model.other_leaves(self.page_dir)
        state["reading"] = (
            reading
            + "."
            + presence_model.presence_fingerprint(
                state["listening"], state["session_alive"], state["others"]
            )
        )
        return state

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        with PageTransaction(self.page_dir) as page:
            if self.preview_source is None:
                activate_source(self.page_dir, page.events)
                active = active_descriptor(self.page_dir, page.events)
                if active is None:
                    raise ValueError(missing_revision(self.page_dir))
                source_overrides = None
            else:
                active = self.preview_source["active"]
                source_overrides = {
                    active["revision"]: self.preview_source["data"].decode("utf-8")
                }
            latest_seq = page.events[-1]["seq"] if page.events else 0
            if through_seq > latest_seq:
                raise ValueError(
                    f"view sequence {through_seq} is newer than log sequence {latest_seq}"
                )
            events = [event for event in page.events if event["seq"] <= through_seq]
            present = presence_model.presence(self.page_dir, events)
            projected = served_browser.project_browser_state(
                self.page_dir,
                events,
                view_revision,
                active,
                present,
                now_iso(),
                source_overrides=source_overrides,
                include_active_view=False,
            )
        if projected is None:
            raise ValueError("page registry cannot be projected")
        # Activity belongs to the complete state reading, not a historical
        # document-view fetch. Keep one public route for the canonical answer.
        projected.pop("activity", None)
        return projected
