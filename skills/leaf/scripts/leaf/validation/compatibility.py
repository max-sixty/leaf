"""Registry composition and candidate-revision compatibility validation."""

from pathlib import Path

from leaf import event_contracts
from leaf.event_meaning import stored_meaning_error
from leaf.events import taken_back
from leaf.registry.contract import RegistryError, read_registry_declarations
from leaf.registry.layer import merge_layer_declarations
from leaf.registry.validation import validate_registry
from leaf.requests import (
    declared_request_error,
)
from leaf.revision_artifact import read_artifact
from leaf.structure import SourceDocument, parse_revision
from leaf.thread_context import thread_structure

from .instances import fragment_errors, thread_markup_contract_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or (example := entry.get("x-example")) is None:
            continue
        parser = SourceDocument(example)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise RegistryError(f"{source}: <{tag}> x-example is invalid: {errors[0]}")
    return registry


def incoming_registry(packages: list) -> dict:
    """The merged registry `page init` will vendor.

    Packages are additive at the top level; merge_layer_declarations holds the grain.
    """
    merged = {}
    paths = []
    for package in packages:
        path = package / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_declarations(merged, read_registry_declarations(path))
    if not paths:
        raise RegistryError("the incoming layer has no registry.json")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    return validate_registry_examples(validate_registry(merged, source), source)


def candidate_vocabulary_gaps(
    page_dir: Path,
    events: list,
    document: SourceDocument,
    incoming: dict,
    through_revision: int,
) -> list[str]:
    """Contracts the candidate would drop from its page or frozen-thread projection.

    Page events participate only while their sender exists in this candidate. Older
    documents use their captured registries. Frozen thread markup has no revision
    boundary, so its markup and commands remain part of every candidate. Every action
    that can be classified is checked, rather than only the current winner, because
    undoing a later action exposes its predecessor.
    """
    if not events:
        return []
    tokens = incoming.get("$reactions", {}).get("tokens", {})
    thread = thread_structure(events)
    revisions = {}
    registries = {}

    def page(revision):
        if revision not in revisions:
            revisions[revision] = parse_revision(page_dir, revision)
        return revisions[revision]

    def registry(revision):
        if revision not in registries:
            registries[revision] = read_artifact(page_dir, revision).registry
        return registries[revision]

    def page_event_participates(event):
        return (
            event["revision"] <= through_revision and event["widget"] in document.by_id
        )

    def anchor_participates(event):
        target = event.get("holds") or (event.get("anchor") or {}).get("section")
        return target in document.by_id

    missing = {}
    withdrawn = taken_back(events)
    for e in events:
        kind = e["kind"]
        key = None
        if e.get("token") and e["id"] not in withdrawn and e["token"] not in tokens:
            key = f"reaction token `{e['token']}` no longer declared by $reactions"
        elif anchor_participates(e) and (
            (
                kind == "comment"
                and e.get("holds")
                and (
                    error := event_contracts.held_comment_error(
                        e, document.by_id, incoming
                    )
                )
            )
            or (
                kind == "comment"
                and e.get("response")
                and (
                    error := event_contracts.version_response_comment_error(
                        e, document.by_id, incoming
                    )
                )
            )
            or (
                kind == "comment"
                and (
                    error := event_contracts.visual_anchor_error(
                        e, document.by_id, incoming
                    )
                )
            )
        ):
            key = f"comment contract: {error}"
        elif (
            kind == "reply"
            and (e.get("anchor") or {}).get("visual")
            and anchor_participates(e)
            and (
                error := event_contracts.visual_anchor_error(
                    e, document.by_id, incoming
                )
            )
        ):
            key = f"reply contract: {error}"
        elif e.get("markup") and (
            errors := thread_markup_contract_errors(thread.fragments[e["id"]], incoming)
        ):
            key = "thread markup contract: " + "; ".join(errors)
        elif kind in {"action", "report", "request"}:
            scope = e["meaning"]["document"]["kind"]
            participates = scope == "thread" or (
                kind in {"action", "report"} and page_event_participates(e)
            )
            if participates:
                original_page = page(e["revision"])
                candidate_page = document if scope == "page" else SourceDocument("")
                if kind == "action":
                    error = event_contracts.declared_action_error(
                        e, candidate_page.by_id, thread.by_id, incoming
                    )
                elif kind == "report":
                    error = event_contracts.report_contract_error(
                        e, candidate_page, incoming, resolve_references=False
                    )
                else:
                    error = declared_request_error(e, document, thread, incoming)
                if error:
                    key = f"{kind} contract: {error}"
                elif error := stored_meaning_error(
                    e,
                    candidate_page,
                    thread,
                    incoming,
                    registry(e["revision"]),
                    recorded_page=original_page,
                ):
                    key = f"admitted meaning: {error}"
        if key is not None:
            missing[key] = missing.get(key, 0) + 1
    return [
        f"{n} event{'s' if n != 1 else ''} of {key}"
        for key, n in sorted(missing.items())
    ]
