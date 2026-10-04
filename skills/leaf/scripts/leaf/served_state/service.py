"""Transport-neutral reads of one page's browser projection."""

from contextlib import contextmanager
from pathlib import Path

from .. import presence as presence_model
from ..files import missing_revision
from ..revisioning import activate_source
from ..service import PageTransaction
from . import browser as served_browser
from . import page as served_page
from . import reading as served_reading
from .context import read_page


class PageStateService:
    """The state transaction every page route reads through.

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

    @contextmanager
    def _read(self, *, with_token: bool = False):
        if self.page_snapshot is not None:
            yield self.page_snapshot.context, self.page_snapshot.reading, None
        else:
            with PageTransaction(self.page_dir) as page:
                activation = activate_source(self.page_dir, transaction=page)
                # Only the complete state response carries a news token. Take it
                # after activation and before the facts it names.
                reading = (
                    served_reading.page_reading(self.page_dir) if with_token else None
                )
                yield (
                    read_page(
                        self.page_dir, page.events, layer_identity=self.layer_identity
                    ),
                    reading,
                    activation.error,
                )

    def page_state(self, view_revision: int | None = None) -> dict:
        with self._read(with_token=True) as (context, reading, source_error):
            state = served_page.read_served_page(
                context,
                preview=self.preview,
                publication=self.publication,
                source_error=source_error,
                view_revision=view_revision,
            ).state
        state["others"] = (
            list(self.page_snapshot.others)
            if self.page_snapshot is not None
            else presence_model.other_leaves(self.page_dir)
        )
        state["reading"] = (
            reading
            if self.page_snapshot is not None
            else served_reading.join_reading(
                reading, presence_model.presence_fingerprint(state, state["others"])
            )
        )
        return state

    def activity_row(self) -> tuple[dict, str, dict]:
        """Compact delivery output of the same transaction and fold as the banner.

        No neighboring-page discovery runs here. The reading and live facts
        name the inputs the publisher keeps, so a concurrent writer invalidates
        this publication on its next look. Owed moves and reply bodies stay in
        the page's projection; the row carries their counts, never their copies.
        """
        from ..server_rows import compact_activity

        with self._read(with_token=True) as (context, reading, source_error):
            state = served_page.read_served_page(
                context, source_error=source_error
            ).state
            title = (
                context.revision(context.active["revision"]).document.title
                if context.active is not None
                else ""
            )
            row = {
                "title": title or self.page_dir.name,
                "session_cwd": state["session_cwd"],
                "activity": compact_activity(state["activity"]),
            }
            live = {
                key: state[key] for key in ("listening", "session_alive", "live_turn")
            }
        return row, reading, live

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        with self._read() as (context, _reading, _source_error):
            if context.active is None:
                raise ValueError(missing_revision(self.page_dir))
            projected = served_browser.project_browser_state(
                context.through(through_seq),
                view_revision,
                include_active_view=False,
            )
            if projected is None:
                raise ValueError("page registry cannot be projected")
            view, _reading = projected
        # Activity belongs to complete state, not a historical document fetch.
        view.pop("activity", None)
        return view
