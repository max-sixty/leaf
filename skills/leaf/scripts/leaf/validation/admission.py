"""What an agent's writer hands in: message markup, bodies, and the ids it names."""

import sys
from pathlib import Path

from leaf.data import read_data
from leaf.data_contracts import data_binding_errors
from leaf.files import list_revisions
from leaf.registry.storage import require_registry
from leaf.revision_artifact import read_registry
from leaf.schema import MESSAGE_KINDS
from leaf.structure import SourceDocument, parse_revision
from leaf.thread_context import thread_structure

from .instances import reference_errors, thread_markup_contract_errors
from .markup import (
    fragment_style_errors,
    media_errors,
    reserved_ids_error,
    reserved_marker_errors,
    text_media_errors,
)


def read_text_arg(page_dir: Path, text) -> str:
    """Every body an agent writes, read at the one place they all come through.

    Prose needs no vocabulary gate — the runtime escapes every tag in it, so it
    cannot claim a widget — but its Markdown can point at a file, and a picture the
    directory hasn't got is a broken image in an append-only log for as long as the
    page exists. `check_markup` asks that of `--markup` and runs only when one is
    given; this asks it of the link and image destinations beside it, which is where
    the runtime resolves one — a path quoted in a sentence stays the author's words."""
    body = text if text is not None else sys.stdin.read()
    if not body:
        sys.exit("empty text (pass --text or pipe via stdin)")
    if errs := text_media_errors(body, page_dir):
        sys.exit(
            "text names media the page directory hasn't got:\n"
            + "\n".join(f"  - {e}" for e in errs)
        )
    return body


def logged_id_route(events: list, value: str) -> str | None:
    """Say what the page's log holds a bare id as, and which command takes it.

    The CLI names several kinds of id with bare strings — an element id anchors a
    thread, a message id answers one, a request id takes its receipt, and a delivered
    event id addresses the response it owes — and nothing about a value says which
    namespace it came from. An agent holding the id of the move it was handed reaches
    for whichever of them it is writing, and a refusal that only repeats the value
    leaves it nothing to change but the guess. The log settles the question, so every
    writer that refuses an id asks this, and says where the value belongs.

    `--for` takes every kind the log holds but a request, not only a message: a
    reader's press on a widget frozen into a reply owes its answer through the event's
    own id and nowhere else. A message answers to `--to` as well, and a request ends in
    its receipt instead.
    """
    event = next((event for event in events if event.get("id") == value), None)
    if event is None:
        return None
    kind = event["kind"]
    if kind == "request":
        route = "`leaf receipt <page> <id> succeeded|failed` settles a request"
    elif kind in MESSAGE_KINDS:
        route = (
            "`leaf reply <page> --to <id>` answers a message and `--for <event-id>` "
            "addresses a delivered move"
        )
    else:
        route = "`leaf reply <page> --for <event-id>` addresses a delivered move"
    article = "an" if kind[:1] in "aeiou" else "a"
    return f"{value} is {article} {kind} in this page's log — {route}"


def version_ids(page_dir: Path) -> set:
    ids = set()
    for revision in list_revisions(page_dir):
        ids |= parse_revision(page_dir, revision).ids
    return ids


def pinned_thread_markup_errors(page_dir: Path, fragment: SourceDocument) -> list[str]:
    """Refuse thread markup an immutable page cannot render.

    Conversation markup has no revision boundary: every open historical document
    receives it.  Admission against only the active registry can therefore freeze a
    newly introduced widget into the log even though an older pinned document has no
    declaration or implementation for it.  Ask every captured registry at the append
    door, while the message can still be refused, and group equal failures so a long
    page history does not produce one copy per revision.
    """
    failures: dict[str, list[int]] = {}
    revisions = list_revisions(page_dir)
    for revision in revisions[:-1]:
        registry = read_registry(page_dir, revision)
        for error in thread_markup_contract_errors(fragment, registry):
            failures.setdefault(error, []).append(revision)
    return [
        "pinned revision"
        + ("s " if len(revisions) > 1 else " ")
        + ", ".join(f"r{revision}" for revision in revisions)
        + f" cannot render this thread markup: {error}"
        for error, revisions in failures.items()
    ]


def check_markup(
    page_dir: Path,
    kind: str,
    markup: str,
    events: list,
    *,
    page: SourceDocument | None = None,
) -> SourceDocument:
    """A message's widget markup, validated against the vendored registry at post
    time — the discussion-side `version check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no vocabulary gate — the runtime renders it with every tag
    escaped, so it cannot claim a widget — but its Markdown can still point at a file,
    which `read_text_arg` asks about wherever a body arrives. Exits with what's
    wrong."""
    registry = require_registry(page_dir)
    frag = SourceDocument(markup)
    # Two gates beside the vocabulary contract rather than inside it. That contract is
    # what re-vendoring asks of every fragment already in the log — can this layer still
    # speak it — and neither a presentation rule nor the presence of a file is any part
    # of the answer. Put there, a page whose log held a <style> from before the rule
    # existed could never be re-vendored again: the log is append-only, so it would have
    # failed `page init` for good, with a message about replay that had nothing to do
    # with what was wrong. Here they are asked of what is arriving, at the one moment
    # anything can still be done about it.
    pinned_errors = pinned_thread_markup_errors(page_dir, frag)
    errs = (
        thread_markup_contract_errors(frag, registry)
        + pinned_errors
        + (
            [
                (
                    "thread markup must use vocabulary shared by the active registry "
                    "and every pinned revision; otherwise ask with --text (and "
                    "--awaits for a reply)"
                )
            ]
            if pinned_errors
            else []
        )
        + fragment_style_errors(frag)
        + media_errors(frag, page_dir)
        + data_binding_errors(
            page_dir,
            registry,
            read_data(page_dir),
            events,
            incoming=[(frag.lf_elements, f"incoming {kind} markup")],
        )
    )
    if errs:
        sys.exit(
            f"{kind} markup doesn't validate:\n" + "\n".join(f"  - {e}" for e in errs)
        )
    if not frag.lf_elements:
        sys.exit("--markup carries no widget; put prose in --text")
    if frag.duplicate_ids:
        sys.exit(
            f"{kind} widget markup reuses an id within itself: {frag.duplicate_ids}"
        )
    if frag.reserved_ids:
        sys.exit(f"{kind} widget markup takes " + reserved_ids_error(frag.reserved_ids))
    if marker_errors := reserved_marker_errors(frag):
        sys.exit(f"{kind} widget markup: " + "; ".join(marker_errors))
    thread = thread_structure(events)
    revisions = list_revisions(page_dir)
    if page is None:
        page = (
            parse_revision(page_dir, revisions[-1]) if revisions else SourceDocument("")
        )
    clash = sorted(frag.ids & (version_ids(page_dir) | page.ids | thread.ids))
    if clash:
        sys.exit(
            f"{kind} widget ids already taken by the page or an earlier message: {clash}"
        )
    if reference_errs := reference_errors(
        frag.lf_elements,
        registry,
        page.ids | thread.ids | frag.ids,
        {**page.by_id, **thread.by_id, **frag.by_id},
    ):
        sys.exit(
            f"{kind} markup doesn't validate:\n"
            + "\n".join(f"  - {error}" for error in reference_errs)
        )
    return frag
