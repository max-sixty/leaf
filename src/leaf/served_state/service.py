"""Transport-neutral reads of one page: its sources and its browser projection.

A page server reads either the page directory as it stands (`LivePage`) or a capture
frozen for a browser check or an export (`page_snapshot.PageSnapshot`). Both answer
the questions in `PageSource`. Every route and the state service read the page's
revisions, log, data and presence only through the source their server was given.
Files the page directory serves beside them, such as the vendored layer and media
outside a captured data value, are still read from the directory under either source.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from .. import presence as presence_model
from ..data import read_data, read_source
from ..event_log import read_events
from ..files import (
    latest_revision,
    missing_revision,
    published_versions,
    revision_names,
    stamped_version,
)
from ..passages import SourceReading
from ..registry.storage import require_registry
from ..revision_artifact import Resource, RevisionArtifact, read_artifact, read_revision
from ..revisioning import activate_source
from ..service import PageTransaction
from . import browser as served_browser
from . import page as served_page
from . import reading as served_reading
from .context import PageRead, read_page
from .thread import thread_counts


class PageSource(Protocol):
    """What a page server reads about its page."""

    # Whether the page takes writes: file saves, user views, events and media.
    writable: bool
    # Each revision's immutable file name, in revision order.
    revision_names: Mapping[int, str]
    # Served bytes beside the revisions, by path, that the page directory may no
    # longer hold.
    data_resources: Mapping[str, Resource]

    def active_revision(self) -> int | None: ...
    def artifact(self, revision: int) -> RevisionArtifact: ...
    def revision(self, revision: int) -> SourceReading: ...
    def active_registry(self) -> dict: ...
    def data_source(self, source: str, registry: dict) -> dict | None: ...
    def events(self) -> list[dict]: ...
    def published_versions(self, events: list[dict]) -> set[int]: ...

    def served_document(self) -> tuple[RevisionArtifact, int, int | None] | None:
        """The active revision as the root serves it, or None before the first."""

    def sample_inputs(self, revision: int) -> tuple[RevisionArtifact, list, dict]:
        """A revision's artifact with the log and data a sample's child starts
        from, read together."""

    def news(self) -> str:
        """The freshness token a visible tab polls (`PageEndpoint._news`)."""

    def other_pages(self) -> list[dict]: ...

    def state_read(
        self, *, with_token: bool = False
    ) -> Iterator[tuple[PageRead, str | None, str | None]]:
        """A context yielding the fold inputs, the news token when asked for, and
        the source error activation met."""

    def state_reading(self, reading: str, state: dict) -> str:
        """Finalize the state's source-specific refresh facts and return its token,
        from `state_read`'s."""


class LivePage:
    """The page directory, read anew for each question."""

    writable = True
    data_resources: Mapping[str, Resource] = MappingProxyType({})

    def __init__(self, page_dir: Path, layer_identity: dict | None = None) -> None:
        self.page_dir = page_dir
        self.layer_identity = layer_identity

    @property
    def revision_names(self) -> dict[int, str]:
        return revision_names(self.page_dir)

    def active_revision(self) -> int | None:
        return latest_revision(self.page_dir)

    def artifact(self, revision: int) -> RevisionArtifact:
        return read_artifact(self.page_dir, revision)

    def revision(self, revision: int) -> SourceReading:
        return read_revision(self.page_dir, revision)

    def active_registry(self) -> dict:
        return require_registry(self.page_dir)

    def data_source(self, source: str, registry: dict) -> dict | None:
        return read_source(self.page_dir, source, registry)

    def events(self) -> list[dict]:
        return read_events(self.page_dir)

    def published_versions(self, events: list[dict]) -> set[int]:
        return set(published_versions(self.page_dir, events))

    def served_document(self) -> tuple[RevisionArtifact, int, int | None] | None:
        with PageTransaction(self.page_dir) as page:
            activate_source(self.page_dir, transaction=page)
            revision = latest_revision(self.page_dir)
            if revision is None:
                return None
            return (
                read_artifact(self.page_dir, revision),
                revision,
                stamped_version(page.events, revision),
            )

    def sample_inputs(self, revision: int) -> tuple[RevisionArtifact, list, dict]:
        with PageTransaction(self.page_dir) as page:
            artifact = read_artifact(self.page_dir, revision)
            return artifact, page.events, read_data(self.page_dir, artifact.registry)

    def news(self) -> str:
        """The token naming the page's current reading."""
        files = served_reading.page_reading(self.page_dir)
        return served_reading.join_reading(
            files, presence_model.presence_reading(self.page_dir, files)
        )

    def other_pages(self) -> list[dict]:
        return presence_model.neighbor_reading(self.page_dir)

    @contextmanager
    def state_read(self, *, with_token: bool = False):
        with PageTransaction(self.page_dir) as page:
            activation = activate_source(self.page_dir, transaction=page)
            # Only the complete state response carries a news token. Take it
            # after activation and before the facts it names.
            reading = (
                served_reading.held_page_reading(self.page_dir) if with_token else None
            )
            yield (
                read_page(
                    self.page_dir, page.events, layer_identity=self.layer_identity
                ),
                reading,
                activation.error,
            )

    def state_reading(self, reading: str, state: dict) -> str:
        return served_reading.join_reading(
            reading, presence_model.presence_fingerprint(state, state["others"])
        )


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
        source: PageSource | None = None,
        preview: dict | None = None,
        publication: dict | None = None,
    ):
        self.page_dir = page_dir
        self.source = source if source is not None else LivePage(page_dir)
        self.preview = preview
        self.publication = publication

    def page_state(self, view_revision: int | None = None) -> dict:
        with self.source.state_read(with_token=True) as (
            context,
            reading,
            source_error,
        ):
            state = served_page.read_served_page(
                context,
                preview=self.preview,
                publication=self.publication,
                source_error=source_error,
                view_revision=view_revision,
            ).state
        state["others"] = self.source.other_pages()
        state["reading"] = self.source.state_reading(reading, state)
        return state

    def activity_row(self) -> tuple[dict, str, dict]:
        """Compact delivery output of the same transaction and fold as the page's status.

        No neighboring-page discovery runs here. The reading and live facts
        name the inputs the publisher keeps, so a concurrent writer invalidates
        this publication on its next look. Owed updates and reply bodies stay in
        the page's projection; the row carries their counts, never their copies.
        The user's counts are the active view's, as the Leaf panel's marks count
        them: its On me list, and its threads by `thread_counts`.
        """
        from ..server_rows import compact_activity

        with self.source.state_read(with_token=True) as (
            context,
            reading,
            _source_error,
        ):
            work = context.work
            projected = served_browser.project_browser_state(context)
            view = (
                projected[0]["views"][str(context.active["revision"])]
                if projected is not None
                else None
            )
            threads = view["thread"]["threads"] if view is not None else []
            title = (
                context.revision(context.active["revision"]).document.authoring.title
                if context.active is not None
                else ""
            )
            row = {
                "title": title or self.page_dir.name,
                "session_cwd": context.presence["session_cwd"],
                "activity": compact_activity(work.activity),
                "on_user": len(view["queues"]["on_user"]) if view is not None else 0,
                "threads": thread_counts(threads),
            }
            live = {key: context.presence[key] for key in presence_model.LIVE_FACTS}
        return row, reading, live

    def page_browser_view(self, view_revision: int, through_seq: int) -> dict:
        with self.source.state_read() as (context, _reading, _source_error):
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
        return view
