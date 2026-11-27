"""The gate each authored document passes, whichever door it comes through: a page's
own document (`authored_document_checks`), the HTML in an agent's message
(`message_markup_findings`) and the Markdown around it (`text_media_errors`), and the
child page of each live sample a page or a message declares (`sample_errors`), checked
against the history allocation builds for it (`initial_sample_events`).

The gates recurse into one another: a message's HTML may declare samples, a sample's
history may hold messages, and a child may declare samples of its own. So they live
here together, below the doors that call them: the source check
(`source.check_source`), the writer of an agent's message (`admission.check_markup`,
`admission.checked_text`), and a sample's allocation (`serving.samples`).

A template's holder is the markup it is written in: its parent page's document, or
the markup of a message holding HTML in that page's log. A template imports live parent
thread closures with `data-sample-threads`, or names an inert JSON script in its
holder with `data-sample-events`. The latter is an array of ordinary event
commands, admitted against the child's initial document and vocabulary before
allocation. It never writes the parent log. Source validation, message admission
and allocation use this same construction. Fixtures are history, not a second
state store: subsequent gestures use the ordinary log.
"""

import json
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from copy import deepcopy
from pathlib import Path

import turbohtml

from leaf.base.findings import Finding, Rejected
from leaf.base.schema import MEDIA_DIR
from leaf.base.state import aware_instant, now_iso
from leaf.log.event_log import EventRefused, logged_ids
from leaf.log.events import logged_fragment, thread_structure
from leaf.log.projection import generated_children, logged_words
from leaf.log.thread_context import sample_events, thread_ids, thread_names
from leaf.records.event_contracts import admitted_event, command_error
from leaf.records.event_meaning import AdmissionReadings
from leaf.records.markup_checks.instances import (
    inert_allocation_advice,
    invoker_errors,
    markup_findings,
    message_settlement_advice,
    question_errors,
    reference_errors,
    suggestion_errors,
)
from leaf.records.markup_checks.markup import (
    authored_allocation_errors,
    fragment_style_errors,
    page_boundary_errors,
)
from leaf.records.page_view import InitialPageView
from leaf.source.anchor_capture import capture_anchor
from leaf.source.data_contracts import declared_data_bindings
from leaf.source.passages import JOINS_WORDS_TAGS, markdown_dialect
from leaf.source.registry.kernel import kernel_event_kinds
from leaf.source.revision_artifact import (
    document_drops,
    unanswered_media,
    uncaptured_errors,
)
from leaf.source.structure import SourceDocument


def _page_errors(
    events: list,
    parser,
    registry: dict | None,
    thread_ids: set[str],
) -> list[Finding]:
    """What a page's document alone is checked for beyond its markup
    (`markup_checks.instances.markup_findings`): its shell and allocations, and its
    instances against its event and id namespace."""
    errors = [*page_boundary_errors(parser), *authored_allocation_errors(parser)]
    if registry is None:
        return errors
    errors.extend(question_errors(parser, registry))
    errors.extend(inert_allocation_advice(parser, registry))
    errors.extend(
        reference_errors(
            parser.lf_elements,
            registry,
            parser.ids,
            parser.by_id,
            thread_ids=thread_ids,
        )
    )
    errors.extend(invoker_errors(parser, parser.ids))
    errors.extend(suggestion_errors(parser.lf_elements, registry))
    taken = sorted(parser.ids & thread_structure(events).holders.keys())
    if taken:
        errors.append(Finding("ids-taken-by-messages", values={"ids": taken}))
    if logged := sorted(parser.ids & logged_ids(events)):
        errors.append(Finding("ids-taken-by-events", values={"ids": logged}))
    return errors


def authored_document_checks(document, events, registry, thread_ids):
    """The same authored-page gate for the root and each isolated child document.

    The stylesheets a document's delivery rewrites, its children's among them, and
    the files it names are read once for the whole document: by the capture
    (`revision_artifact.capture_artifact`) and `source.check_source`'s
    `document_drops`, or for a message no capture reads, by its gate
    (`message_markup_findings`)."""

    return markup_findings(
        document, registry, lambda: _page_errors(events, document, registry, thread_ids)
    )


def text_media_errors(
    text: str, page_dir: Path, *, html: bool = False
) -> list[Finding]:
    """Each `/media/` reference in a message's Markdown that the page won't answer
    (`revision_artifact.unanswered_media`).

    Markup names a picture in an attribute or a stylesheet, where the parsed reading
    finds it (`revision_artifact.uncaptured_errors`); a message names one as a
    Markdown destination, which that reading cannot see — so a screenshot an agent
    sends that way would come through the one door that never asks.
    `admission.check_markup` runs only on a message holding HTML, and text without it
    would reach the log unread.

    A reference is a rendered link or image destination, never a scan of the words.
    Parsing the Markdown resolves referenced definitions and leaves fenced examples
    and unused definitions as text, so neither asks for a file the page will not load."""
    refs = {
        url
        for token in markdown_dialect(True, html=html).parse(text)
        for child in token.children or ()
        if child.type in {"link_open", "image"}
        if (url := child.attrGet("href" if child.type == "link_open" else "src"))
        and url.startswith(f"/{MEDIA_DIR}/")
    }
    return unanswered_media(refs, page_dir)


def split_preformatted(frag: SourceDocument) -> list[Finding]:
    """Each `<pre>` holding a block, such as a `<p>`, `<ul>` or `<h1>`, which HTML's
    content model keeps out of a `<pre>` and only a message's Markdown draws there: a
    blank line inside a block of HTML ends the block, a `<pre>` within it included,
    and Markdown reads the lines after it as its own blocks. The text loses its blank
    lines, its indents and any list marks, `#` or asterisks, and the HTML stays well
    formed, so no other check reports it. A block is any HTML element outside phrasing
    content (`$passages.phrasing`); a custom element is phrasing content."""
    findings = []
    for pre in frag.tree.descendants:
        if not (isinstance(pre, turbohtml.Element) and pre.tag == "pre"):
            continue
        block = next(
            (
                inner
                for inner in pre.descendants
                if isinstance(inner, turbohtml.Element)
                and inner.namespace is turbohtml.Namespace.HTML
                and inner.tag not in JOINS_WORDS_TAGS
                and "-" not in inner.tag
            ),
            None,
        )
        if block is not None:
            line = SourceDocument._position(block)[0]
            findings.append(
                Finding("split-pre", "<pre>", {"line": line, "block": block.tag})
            )
    return findings


def message_markup_findings(
    page_dir: Path,
    frag: SourceDocument,
    events: list,
    registry: dict,
    page: SourceDocument,
    prior_ids: AbstractSet[str],
    contracts: dict,
    thread_id: str | None,
    *,
    replacing: str | None = None,
) -> list[Finding]:
    """The shared message-fragment gate for a stored or newly constructed page.

    The fragment's structure, vocabulary, data bindings, presentation, media, ids,
    references and live sample children have one gate regardless of whether its page
    has been allocated yet. `thread_id` is the thread the message joins, where known,
    and `replacing` the message an edit rewrites: its markup leaves the page as this
    takes its place, and an id any of its wordings held is its own to keep
    (`events.thread_structure`). Each stage reads only a fragment the stages
    before it accept, so the gate gives the findings of the first stage that refuses
    the fragment, or where none does, what every stage advises.
    """
    advice = []
    for found in _message_stages(
        page_dir,
        frag,
        events,
        registry,
        page,
        prior_ids,
        contracts,
        thread_id,
        replacing,
    ):
        if any(finding.refuses for finding in found):
            return found
        advice += found
    return advice


def _message_stages(
    page_dir: Path,
    frag: SourceDocument,
    events: list,
    registry: dict,
    page: SourceDocument,
    prior_ids: AbstractSet[str],
    contracts: dict,
    thread_id: str | None,
    replacing: str | None,
) -> Iterator[list[Finding]]:
    """The findings of each stage of `message_markup_findings`, in order, each read
    only once the gate asks for it."""
    yield split_preformatted(frag)
    yield markup_findings(
        frag,
        registry,
        lambda: [
            *message_settlement_advice(frag, registry),
            *fragment_style_errors(frag),
            *uncaptured_errors(frag, page_dir),
        ],
    )
    thread = thread_structure(events)
    held = {
        identity for identity, message in thread.holders.items() if message != replacing
    }
    clash = sorted(frag.ids & (prior_ids | page.ids | held))
    yield [Finding("ids-taken", values={"ids": clash})] if clash else []
    logged = sorted(frag.ids & logged_ids(events))
    yield [Finding("ids-taken-by-events", values={"ids": logged})] if logged else []
    # A reference reads the message's own document and then the page
    # (`runtime/readings/references.js`), so an id in another message would resolve to nothing.
    ids = page.ids | frag.ids
    yield reference_errors(
        frag.lf_elements,
        registry,
        ids,
        {**page.by_id, **frag.by_id},
        thread_ids=thread_ids(events),
    ) + invoker_errors(frag, ids)
    # A child selecting the thread this message joins would hold this sample again,
    # and its child the same, without end.
    looping = sorted(
        sample["attrs"].get("id", "<unnamed>")
        for sample in frag.samples
        if thread_id in sample["attrs"].get("data-sample-threads", "").split()
    )
    yield (
        [Finding("sample-loop", values={"samples": looping, "thread": thread_id})]
        if looping
        else []
    )
    # A live sample's child is a page of its own, built from this message once it is
    # logged.
    yield [
        *sample_errors(page_dir, page, events, frag, registry, contracts),
        *uncaptured_sample_errors(page_dir, frag),
        *document_drops(frag),
    ]


def sample_errors(
    page_dir: Path,
    parent: SourceDocument,
    events: list,
    holder: SourceDocument,
    registry: dict | None,
    contracts: dict,
) -> list[Finding]:
    """Check each live sample `holder` declares as allocation would build it.

    `holder` is `parent` for a page's own templates, or a message in `events`, the
    log of `parent`. Each child is checked as a page against its initial history,
    and then the samples it declares in turn."""
    errors = []
    pending = [(parent, events, holder, ())]
    for document, document_events, declaring, outer in pending:
        for sample in declaring.samples:
            samples = (*outer, sample["attrs"].get("id"))
            child = sample["document"]
            selected = set(sample["attrs"].get("data-sample-threads", "").split())
            # A template may precede its seed log, and the selection reads against
            # whatever the log holds — so the child checked here is the child
            # allocation would build from this document and this history.
            try:
                child_events, notes = (
                    initial_sample_events(
                        page_dir,
                        document,
                        document_events,
                        declaring,
                        sample,
                        registry,
                        contracts,
                    )
                    if registry is not None
                    else ([], [])
                )
                errors.extend(found.but(samples=samples) for found in notes)
            except Rejected as error:
                errors.extend(found.but(samples=samples) for found in error.findings)
                child_events = []
            pending.append((child, child_events, child, samples))
            child_errors = authored_document_checks(
                child,
                child_events,
                registry,
                selected | thread_ids(child_events),
            )
            errors.extend(error.but(samples=samples) for error in child_errors)
    return errors


def uncaptured_sample_errors(page_dir: Path, holder: SourceDocument) -> list[Finding]:
    """Each /media/ file the page won't answer that an attribute names in a live
    sample child of the message `holder`, or a child of one, which the message's own
    reading leaves out. Its stylesheets, those in its samples included, the message
    gate reads whole (`revision_artifact.uncaptured_errors`). A page's own children
    are captured with it; no capture reads a message."""
    errors = []
    pending = [(holder, ())]
    for declaring, outer in pending:
        for sample in declaring.samples:
            samples = (*outer, sample["attrs"].get("id"))
            pending.append((sample["document"], samples))
            errors.extend(
                error.but(samples=samples)
                for error in unanswered_media(
                    sample["document"].authoring.media_refs, page_dir
                )
            )
    return errors


def _non_json_number(value: str):
    raise ValueError(f"{value} is not a JSON number")


def _refused(code: str, reference: str, **values) -> Rejected:
    """The refusal of a sample's history, as the one finding that says why:
    `reference` is the script its template names, and `values` what was read there."""
    return Rejected([Finding(code, values={"reference": reference, **values})])


def _fixture_anchor(
    anchor: dict, readings: AdmissionReadings
) -> tuple[dict, Finding | None]:
    """Capture an authored target in the child's current page or thread markup, with
    the note on where the child shows a quote its files don't hold once.

    Browser admission receives targets already captured in a rendered document.
    A fixture has no such observation, so the file-side capture checks its section
    against the same current projection instead (`anchor_capture.capture_anchor`).
    Context the fixture gives is its own choice of copy (`findQuote`), so it replaces
    the capture's, and no note says the thread stands on its section.
    """
    page = readings.page(1)
    document, projection = page.document, page.projection
    section = anchor.get("section") or ""
    thread = readings.thread
    created_in_thread = {
        child["id"]: owner
        for owner, children in generated_children(
            thread.projection.desired, thread.structure.ids
        ).items()
        for child in children
    }
    target = created_in_thread.get(section, section)
    if target in thread.structure.ids:
        document = next(
            fragment
            for fragment in thread.structure.fragments.values()
            if target in fragment.ids
        )
        projection = thread.projection
    captured, found = capture_anchor(
        document,
        readings.registry,
        # A datum's displayed words come from its module, not authored text.
        # Its section is still captured here; admission checks its data binding.
        "" if "datum" in anchor else anchor.get("quote", ""),
        section,
        part=anchor.get("visual"),
        **logged_words(projection, document.ids),
    )
    if not ({"prefix", "suffix"} & anchor.keys()):
        return {**anchor, **captured}, found
    # The capture's sides are another copy's wherever the fixture means a copy the
    # files don't hold once, so a side the fixture leaves out stays unknown.
    sides = ("prefix", "suffix")
    return {**anchor, **{k: v for k, v in captured.items() if k not in sides}}, None


def initial_sample_events(
    page_dir: Path,
    parent: SourceDocument,
    parent_events: list,
    holder: SourceDocument,
    template: dict,
    registry: dict,
    contracts: dict,
) -> tuple[list[dict], list[Finding]]:
    """Construct the child's admitted log without mutating any captured input, and
    what its capture of fixture anchors noted (`_fixture_anchor`).

    `parent` is the document `parent_events` is the log of, and `holder` the markup
    declaring `template`: `parent` itself, or one of its log's messages. `registry`
    is the child's, and the child reads every message in this log under it, whatever
    registry a copied message was posted with. So a fixture's message is checked
    under it as it is admitted, and a copied message's bindings as it is copied."""
    attrs = template["attrs"]
    reference = attrs.get("data-sample-events")
    if "data-sample-events" not in attrs:
        selected = set(attrs.get("data-sample-threads", "").split())
        copied = [
            {**event, "seq": seq}
            for seq, event in enumerate(
                sample_events(parent, parent_events, selected), 1
            )
        ]
        if conflicts := [
            conflict
            for message, fragment in thread_structure(copied).fragments.items()
            for conflict in declared_data_bindings(
                fragment.lf_elements, registry, f"copied message {message!r}"
            )[1]
        ]:
            raise Rejected(conflicts)
        return copied, []
    if "data-sample-threads" in attrs:
        raise Rejected([Finding("sample-source-both")])
    scripts = [
        script
        for script in [
            *holder.authoring.inline_scripts,
            *holder.authoring.external_scripts,
        ]
        if script["attrs"].get("id") == reference
    ]
    if not reference or len(scripts) != 1:
        raise _refused("sample-script", reference)
    script = scripts[0]
    if (
        script["attrs"].get("type", "").strip().lower() != "application/json"
        or "src" in script["attrs"]
    ):
        raise _refused("sample-script-type", reference)
    try:
        commands = json.loads(script["body"], parse_constant=_non_json_number)
    except ValueError as error:
        reason = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
        raise _refused("sample-json", reference, error=reason) from error
    if not isinstance(commands, list) or any(
        not isinstance(item, dict) for item in commands
    ):
        raise _refused("sample-array", reference)
    child = template["document"]
    view = InitialPageView(child, registry, contracts)
    events, notes = [], []
    kinds = kernel_event_kinds()
    constructed_at = now_iso()
    for seq, command in enumerate(commands, 1):
        try:
            event = deepcopy(command)
            # The door refuses an unknown kind and a publication in its own words
            # (`command_error`, `fixture-event`); the defaults below need the kind.
            kind = event.get("kind")
            known = isinstance(kind, str) and kind in kinds
            spec = kinds[kind]["record"] if known else {"properties": {}}
            event.setdefault("id", f"{seq:08x}")
            event.setdefault("ts", constructed_at)
            event.setdefault("author", "user")
            event["seq"] = seq
            if "revision" in spec["properties"]:
                event["revision"] = 1
            if error := command_error(event, kinds):
                raise _refused(
                    "fixture-event",
                    reference,
                    event=seq,
                    findings=[error.json(text=False)],
                )
            if aware_instant(event["ts"]) is None:
                raise _refused("fixture-ts", reference, event=seq)
            if any(logged["id"] == event["id"] for logged in events):
                raise _refused(
                    "fixture-id-repeated", reference, event=seq, id=event["id"]
                )
            if event["id"] in child.ids | thread_structure(events).holders.keys():
                raise _refused("fixture-id-taken", reference, event=seq, id=event["id"])
            if event.get("anchor"):
                event["anchor"], found = _fixture_anchor(
                    event["anchor"], AdmissionReadings(view, events, registry)
                )
                notes.extend([found] if found else [])
            fragment = logged_fragment(event)
            if "text" in event and (
                errors := text_media_errors(
                    event["text"], page_dir, html=fragment is not None
                )
            ):
                raise _refused(
                    "fixture-media",
                    reference,
                    event=seq,
                    findings=[found.json(text=False) for found in errors],
                )
            if fragment:
                found = message_markup_findings(
                    page_dir,
                    fragment,
                    events,
                    registry,
                    child,
                    set(),
                    contracts,
                    event["id"]
                    if kind == "comment"
                    else thread_names(events).get(
                        event.get("parent", event.get("message"))
                    ),
                    replacing=event.get("message"),
                )
                if errors := [f for f in found if f.refuses]:
                    raise _refused(
                        "fixture-markup",
                        reference,
                        event=seq,
                        kind=kind,
                        findings=[found.json(text=False) for found in errors],
                    )
                if collision := fragment.ids & (
                    {logged["id"] for logged in events} | {event["id"]}
                ):
                    raise _refused(
                        "fixture-ids-taken", reference, event=seq, ids=sorted(collision)
                    )
            events.append(admitted_event(view, events, event))
        except EventRefused as error:
            raise _refused(
                "fixture-event",
                reference,
                event=seq,
                findings=[found.json(text=False) for found in error.findings],
            ) from error
        except ValueError as error:
            # The anchor capture's own refusal, in its words.
            raise _refused(
                "fixture-refused", reference, event=seq, error=str(error)
            ) from error
    return events, notes
