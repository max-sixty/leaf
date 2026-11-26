"""What an agent's writer hands in: message bodies, the HTML in them, and the ids it
names."""

from pathlib import Path

from leaf.base.findings import Finding, Rejected, note
from leaf.base.piped_input import NO_BODY
from leaf.base.refusals import Refused
from leaf.log.events import build_threads
from leaf.log.thread_context import thread_names
from leaf.records.activity import answer_command
from leaf.records.authored_checks.documents import (
    message_markup_findings,
    text_media_errors,
)
from leaf.source.data import read_contracts
from leaf.source.reading import SourceReading
from leaf.source.registry.kernel import kinds_declaring
from leaf.source.revision_artifact import read_revision, revision_history
from leaf.source.structure import SourceDocument
from leaf.source.vocabulary import require_registry


def checked_text(
    page_dir: Path, text: str | None, *, allow_empty: bool = False, html: bool = False
) -> str:
    """Every body an agent writes, checked at the one place they all come through.
    None, where the agent gave none, is refused, and so is an empty body unless
    `allow_empty`.

    Its Markdown can point at a file, and a picture the directory hasn't got is a
    broken image in an append-only log for as long as the page exists. `check_markup`
    asks that of a message's HTML and runs only where the message holds some; this
    asks it of the link and image destinations, which is where the runtime resolves
    one — a path quoted in a sentence stays the author's words. `html` reads the text
    as an agent's message, which draws its HTML (`thread.drawn_markup`), where
    Markdown inside a `<code>` is words."""
    if text is None or not (text or allow_empty):
        raise Refused(f"empty text ({NO_BODY})")
    if errs := text_media_errors(text, page_dir, html=html):
        raise Rejected(errs, "text names media the page won't show")
    return text


def thread_obligation(events: list, responses: dict, message: str) -> dict | None:
    """What the thread holding one message still owes, if anything.

    A thread's response is owed by the thread rather than by the message inside it
    that happens to carry it, so a message with nothing against its own id can still
    sit in a thread waiting on one. Every writer that asks "what does a proactive
    message to this one leave owed?" asks this, because two readings of the same
    question drift: an agent told a message was owed nothing would post to its thread
    and hear the thread still owed an answer.
    """
    names = thread_names(events)
    thread = names.get(message, message)
    return next(
        (
            response
            for response in responses.values()
            if response["kind"] == "reply"
            and names.get(response["parent"], response["parent"]) == thread
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
    itself — a proactive message to a thread that owes a response answers nothing,
    whichever of its messages is owed it — so it is read through
    `thread_obligation`, the same reading `post_reply` notes beside such a message. A
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
    if owed is None and kind in kinds_declaring("message"):
        owed = thread_obligation(events, responses, value)
        if owed is None:
            thread = build_threads(events, {}).get(thread_names(events)[value])
            # The agent's resolve answers for its thread, whatever the user closed
            # after it; the user's settles nothing the agent owes
            # (`events.owed_turns`).
            resolution = thread["answered_by"] if thread else None
            if resolution is not None and (
                resolution["kind"],
                resolution["author"],
            ) == ("resolve", "agent"):
                return (
                    f"{held}; the agent resolved the thread at {resolution['ts']}, "
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


def revision_publication(page_dir: Path, revision: int | None) -> SourceReading:
    """What a message stored at `revision` is published against: that revision, or
    before the page has one, the candidate's vocabulary over an empty document."""
    if revision is not None:
        return read_revision(page_dir, revision)
    return SourceReading(SourceDocument(""), require_registry(page_dir))


def check_markup(
    page_dir: Path,
    kind: str,
    markup: str,
    events: list,
    *,
    publication: SourceReading,
    thread: str | None = None,
    replacing: str | None = None,
) -> SourceDocument:
    """The markup an agent's message holding HTML draws (`passages.message_markup`),
    validated against the registry it is published with — the discussion-side `page
    check`, and the one gate of an agent's HTML: the browser door posts only the
    user's words, which draw no HTML, so none reaches the log unvalidated. Text
    without HTML needs no vocabulary gate, since it can't claim a widget, but its
    Markdown can still point at a file, which `checked_text` asks about wherever a
    body arrives. `thread` is the thread a reply or an edit joins; a
    comment opens one whose id is not yet assigned. `replacing` names the message an
    edit rewrites, whose own ids the markup may keep. Refuses with what's wrong, and
    notes beside the command's result what the check advises, as `page check` reports
    it beside a page that passes (`findings.note`).

    `publication` is the document and registry the message is stored with, which
    its writer decides before the check: the revision it names
    (`revision_publication`), or the candidate where a reply publishes saved edits
    it has checked (`thread.post_reply`). The page's data inventory and `leaf data
    set` read the fragment's bindings under that registry
    (`page_data.page_data_document_readings`), so it is checked here under that
    one; a sample's child that copies the message reads it under its own, and checks
    it there (`documents.initial_sample_events`)."""
    registry, page = publication.registry, publication.document
    frag = SourceDocument(markup)
    found = message_markup_findings(
        page_dir,
        frag,
        events,
        registry,
        page,
        revision_history(page_dir).ids,
        read_contracts(page_dir),
        thread,
        replacing=replacing,
    )
    if errors := [finding for finding in found if finding.refuses]:
        raise Rejected(
            errors, f"the HTML in the {kind} doesn't validate{drawn(markup, errors)}"
        )
    note(*found)
    return frag


def drawn(markup: str, findings: list[Finding]) -> str:
    """The lines the findings name, with one either side, of the HTML a message's
    Markdown draws. A finding counts lines of that drawing, which its writer never
    sees, and the drawing is often the cause, as where Markdown puts a paragraph
    around a widget."""
    named = set()

    def lines_in(value):
        if isinstance(value, dict):
            if isinstance(value.get("line"), int):
                named.add(value["line"])
            for item in value.values():
                lines_in(item)
        elif isinstance(value, list):
            for item in value:
                lines_in(item)

    for finding in findings:
        lines_in(finding.values)
    lines = markup.rstrip("\n").split("\n")
    shown = sorted(
        {n for line in named for n in range(line - 1, line + 2) if 1 <= n <= len(lines)}
    )
    if not shown:
        return ""
    rows = []
    for before, n in zip([None, *shown], shown, strict=False):
        if before is not None and n != before + 1:
            rows.append("     …")
        rows.append(f"{n:>4}  {lines[n - 1]}")
    return (
        ". Its Markdown draws this HTML, where the findings count lines:\n"
        + "\n".join(rows)
        + "\nFindings"
    )
