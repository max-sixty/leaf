"""Message markup and text admission boundaries."""

import sys
from pathlib import Path

from leaf.data import data_binding_errors, read_data_store
from leaf.files import list_revisions
from leaf.registry import require_registry
from leaf.structure import _StructParser, parse_revision, parse_structure
from leaf.thread_context import thread_structure

from .instances import thread_markup_contract_errors
from .markup import (
    fragment_style_errors,
    media_errors,
    reserved_ids_error,
    reserved_marker_errors,
)


def read_text_arg(text) -> str:
    body = text if text is not None else sys.stdin.read()
    if not body.strip():
        sys.exit("empty text (pass --text or pipe via stdin)")
    return body.strip()


def version_ids(page_dir: Path) -> set:
    ids = set()
    for revision in list_revisions(page_dir):
        ids |= parse_revision(page_dir, revision).ids
    return ids


def check_markup(page_dir: Path, kind: str, markup: str, events: list) -> _StructParser:
    """A message's widget markup, validated against the vendored registry at post
    time — the discussion-side `version check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no gate at all — the runtime renders it with every tag
    escaped, so it cannot claim a widget. Exits with what's wrong."""
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
            [(frag.lf_elements, f"incoming {kind} markup")],
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
    clash = sorted(frag.ids & (version_ids(page_dir) | thread_structure(events).ids))
    if clash:
        sys.exit(
            f"{kind} widget ids already taken by the page or an earlier message: {clash}"
        )
    return frag
