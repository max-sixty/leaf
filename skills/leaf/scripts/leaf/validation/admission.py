"""What an agent's writer hands in: message markup, bodies, and the ids it names."""

import sys
from pathlib import Path

from leaf.activity import answer_command
from leaf.data import read_contracts
from leaf.data_contracts import data_binding_errors
from leaf.events import build_threads
from leaf.files import list_revisions
from leaf.findings import Finding, Rejected
from leaf.passages import SourceReading
from leaf.registry.storage import require_registry
from leaf.revision_artifact import read_revision
from leaf.schema import MESSAGE_KINDS
from leaf.structure import SourceDocument
from leaf.thread_context import (
    effective_thread_events,
    thread_names,
    thread_structure,
)

from ..refusals import Refused
from .instances import (
    reference_errors,
    thread_markup_contract_errors,
)
from .markup import (
    document_declaration_errors,
    fragment_style_errors,
    id_errors,
    media_errors,
    text_media_errors,
)


def read_text_arg(page_dir: Path, text, *, allow_empty: bool = False) -> str:
    """Every body an agent writes, read at the one place they all come through.

    Prose needs no vocabulary gate — the runtime escapes every tag in it, so it
    cannot claim a widget — but its Markdown can point at a file, and a picture the
    directory hasn't got is a broken image in an append-only log for as long as the
    page exists. `check_markup` asks that of `--markup` and runs only when one is
    given; this asks it of the link and image destinations beside it, which is where
    the runtime resolves one — a path quoted in a sentence stays the author's words."""
    body = text if text is not None else sys.stdin.read()
    if not body and not allow_empty:
        raise Refused("empty text (pass --text or pipe via stdin)")
    if errs := text_media_errors(body, page_dir):
        raise Rejected(errs, "text names media the page won't show")
    return body


def thread_obligation(events: list, responses: dict, message: str) -> dict | None:
    """What the thread holding one message still owes, if anything.

    A thread's response is owed by the thread rather than by the message inside it
    that happens to carry it, so a message with nothing against its own id can still
    sit in a thread waiting on one. Every writer that asks "may a new message
    go to this one as a proactive message?" asks this, because two readings of the same
    question drift: a refusal that sent an agent to name a thread for a message owed
    nothing sent it to a writer refusing it on the thread's obligation, which is the
    dead end a refusal is supposed to end.
    """
    names = thread_names(events)
    thread = names.get(message, message)
    return next(
        (
            response
            for response in responses.values()
            if response["kind"] == "reply"
            and names.get(response["to"], response["to"]) == thread
        ),
        None,
    )


def logged_id(page_dir: Path, events: list, value: str, responses: dict) -> str | None:
    """Say what the page's log holds a bare id as, and which writer takes it now.

    The CLI names several kinds of id with bare strings — an element id anchors a
    thread, a message id answers one, and a delivered event id addresses the response
    it owes — and nothing about a value says which namespace it came from. An agent
    holding the id of the update it was handed reaches for whichever writer it is using,
    and a refusal that only repeats the value leaves it nothing to change but the
    guess. So every writer that refuses an id says what the log holds it as, and where
    it goes instead.

    Where it goes is what the log still owes, which is `current_responses`: a
    user's press is answered through its delivery reference until it is answered and not after, and
    a resolve or an undo is owed nothing at all. A
    message is the one id whose writer turns on its thread rather than on
    itself — naming the thread for a proactive message is refused while the thread owes a
    response, whichever of its messages is owed it — so it is read through
    `thread_obligation`, the same reading `post_reply`'s guard refuses on. A
    thread's id is its opening comment's, so an agent holding a thread id names it
    as a message.
    """
    event = next((event for event in events if event.get("id") == value), None)
    if event is None:
        return None
    kind = event["kind"]
    article = "an" if kind[:1] in "aeiou" else "a"
    held = f"{value} is {article} {kind} in this page's log"
    owed = responses.get(value)
    if owed is None and kind in MESSAGE_KINDS:
        owed = thread_obligation(events, responses, value)
        if owed is None:
            thread = build_threads(events, {}).get(thread_names(events)[value])
            resolution = thread["resolved"] if thread else None
            if resolution is not None and resolution["kind"] == "resolve":
                actor = "the user" if resolution["author"] == "user" else "the agent"
                return (
                    f"{held}; {actor} resolved the thread at {resolution['ts']}, "
                    "so no reply is owed"
                )
            return (
                f"{held}, and nothing is owed for it — "
                f"`leaf thread reply <page> {value}` replies to it"
            )
        return (
            f"{held}, and its thread is owed a reply — "
            f"{answer_command(owed, page_dir)} answers it"
        )
    if owed is None:
        return f"{held}, and nothing is owed for it"
    return f"{held} — {answer_command(owed, page_dir)} answers it"


def version_ids(page_dir: Path) -> set:
    ids = set()
    for revision in list_revisions(page_dir):
        ids.update(read_revision(page_dir, revision).inventory.ids)
    return ids


def check_markup(
    page_dir: Path,
    kind: str,
    markup: str,
    events: list,
    *,
    reading: SourceReading | None = None,
    thread: str | None = None,
) -> SourceDocument:
    """A message's HTML fragment, validated against its captured publication
    reading — the discussion-side `page check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no vocabulary gate — the runtime renders it with every tag
    escaped, so it cannot claim a widget — but its Markdown can still point at a file,
    which `read_text_arg` asks about wherever a body arrives. `thread` is the thread
    a reply joins; a comment opens one whose id is not yet assigned. Refuses with
    what's wrong."""
    frag = SourceDocument(markup)
    revisions = list_revisions(page_dir)
    effective_events = effective_thread_events(events, revisions)
    if reading is None:
        reading = (
            read_revision(page_dir, revisions[-1])
            if revisions
            else SourceReading(SourceDocument(""), require_registry(page_dir))
        )
    registry = reading.registry
    page = reading.document
    extra_errors = data_binding_errors(
        page_dir,
        registry,
        effective_events,
        incoming=[(frag, f"incoming {kind} markup")],
    )
    if errors := message_markup_errors(
        page_dir,
        frag,
        events,
        registry,
        page,
        version_ids(page_dir),
        extra_errors,
        read_contracts(page_dir),
        thread,
        effective_events=effective_events,
    ):
        raise Rejected(errors, f"{kind} markup doesn't validate")
    return frag


def message_markup_errors(
    page_dir: Path,
    frag: SourceDocument,
    events: list,
    registry: dict,
    page: SourceDocument,
    prior_ids: set[str],
    extra_errors: list[Finding],
    contracts: dict,
    thread_id: str | None,
    *,
    effective_events: list | None = None,
) -> list[Finding]:
    """The shared message-fragment gate for a stored or newly constructed page.

    Callers supply their lifetime binding checks. Fragment structure, vocabulary,
    presentation, media, ids, references and live sample children have one gate,
    whether or not its page is allocated. `thread_id` names the joined thread.
    Each stage reads only a fragment the stages before it accept, so it gives the
    first stage's findings, or none.
    """
    if errs := (
        thread_markup_contract_errors(frag, registry)
        + extra_errors
        + fragment_style_errors(frag)
        + document_declaration_errors(frag)
        + media_errors(frag, page_dir)
    ):
        return errs
    if names := id_errors(frag):
        return names
    thread = thread_structure(
        effective_events if effective_events is not None else events
    )
    reserved = thread_structure(events)
    clash = sorted(frag.ids & (prior_ids | page.ids | reserved.ids))
    if clash:
        return [Finding("ids-taken", values={"ids": clash})]
    if reference_errs := reference_errors(
        frag.lf_elements,
        registry,
        page.ids | thread.ids | frag.ids,
        {**page.by_id, **thread.by_id, **frag.by_id},
    ):
        return reference_errs
    # A child selecting the thread this message joins would hold this sample again,
    # and its child the same, without end.
    if looping := sorted(
        sample["attrs"].get("id", "<unnamed>")
        for sample in frag.samples
        if thread_id in sample["attrs"].get("data-sample-threads", "").split()
    ):
        return [
            Finding("sample-loop", values={"samples": looping, "thread": thread_id})
        ]
    # A live sample's child is a page of its own, built from this message once it is
    # logged. Imported here because checking a child calls this gate back for each
    # fixture message in its history.
    from .source import sample_errors

    return sample_errors(page_dir, page, events, frag, registry, contracts)
