"""Message markup and text admission boundaries."""

import sys
from pathlib import Path

from leaf.data import read_data_store
from leaf.data_contracts import data_binding_errors
from leaf.files import list_revisions
from leaf.registry.storage import require_registry
from leaf.structure import _StructParser, parse_revision, parse_structure
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
    if not body.strip():
        sys.exit("empty text (pass --text or pipe via stdin)")
    body = body.strip()
    if errs := text_media_errors(body, page_dir):
        sys.exit(
            "text names media the page directory hasn't got:\n"
            + "\n".join(f"  - {e}" for e in errs)
        )
    return body


def version_ids(page_dir: Path) -> set:
    ids = set()
    for revision in list_revisions(page_dir):
        ids |= parse_revision(page_dir, revision).ids
    return ids


def check_markup(page_dir: Path, kind: str, markup: str, events: list) -> _StructParser:
    """A message's widget markup, validated against the vendored registry at post
    time — the discussion-side `version check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no vocabulary gate — the runtime renders it with every tag
    escaped, so it cannot claim a widget — but its Markdown can still point at a file,
    which `read_text_arg` asks about wherever a body arrives. Exits with what's
    wrong."""
    registry = require_registry(page_dir)
    frag = parse_structure(markup)
    # Two gates beside the vocabulary contract rather than inside it. That contract is
    # what re-vendoring asks of every fragment already in the log — can this layer still
    # speak it — and neither a presentation rule nor the presence of a file is any part
    # of the answer. Put there, a page whose log held a <style> from before the rule
    # existed could never be re-vendored again: the log is append-only, so it would have
    # failed `page init` for good, with a message about replay that had nothing to do
    # with what was wrong. Here they are asked of what is arriving, at the one moment
    # anything can still be done about it.
    errs = (
        thread_markup_contract_errors(frag, registry)
        + fragment_style_errors(frag)
        + media_errors(frag, page_dir)
        + data_binding_errors(
            page_dir,
            registry,
            read_data_store(page_dir),
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
    clash = sorted(frag.ids & (version_ids(page_dir) | thread.ids))
    if clash:
        sys.exit(
            f"{kind} widget ids already taken by the page or an earlier message: {clash}"
        )
    revisions = list_revisions(page_dir)
    page = parse_revision(page_dir, revisions[-1]) if revisions else parse_structure("")
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
