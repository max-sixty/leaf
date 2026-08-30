"""Incoming registry and standing-event compatibility validation."""

from pathlib import Path

from leaf import event_contracts
from leaf.files import read_json
from leaf.registry.contract import RegistryError, read_registry_entries
from leaf.registry.layer import merge_layer_entries
from leaf.registry.validation import validate_registry
from leaf.requests import (
    declared_request_error,
    receipt_contract_error,
    request_document,
    request_lifecycle_error,
)
from leaf.structure import parse_revision, parse_structure
from leaf.thread_context import thread_structure

from .instances import fragment_errors, thread_markup_contract_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or (example := entry.get("x-example")) is None:
            continue
        parser = parse_structure(example)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise RegistryError(f"{source}: <{tag}> x-example is invalid: {errors[0]}")
    return registry


def incoming_registry(packages: list) -> dict:
    """The merged registry `page init` will vendor.

    Packages are additive at the top level; merge_layer_entries holds the grain.
    """
    merged = {}
    paths = []
    for package in packages:
        path = package / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_entries(merged, read_registry_entries(path))
    if not paths:
        raise RegistryError("the incoming layer has no registry.json")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    return validate_registry_examples(validate_registry(merged, source), source)


# ---------- the vocabulary stamp ----------
# The registry vendored into a page is also that page's statement of what its
# runtime speaks: $events names the event kinds and the fields each carries,
# x-state (per widget) each tag's verbs and detail schemas. Nothing else on disk
# says so. `page init` refuses a re-vendor that would retire or reshape a contract
# still present in the log.
#
# That refusal is the third door a decision can be lost through, after version-scoping
# and hand-copying: the log is append-only and its verbs are a forever-contract, so
# fifteen of one page's own `decide` events fell silent when the verb was retired under
# them. Only the stamp makes that a refusal rather than a quiet no-op.


def vocabulary_gaps(page_dir: Path, events: list, incoming: dict) -> list:
    """What the page's log says that the *incoming* layer no longer speaks:
    events its $events record schemas reject; reactions on a token its
    $reactions drops; comments whose conversation contract changed; or
    actions and reports whose sending tag, verb, or detail the incoming x-state
    or x-report contract rejects. Empty for a fresh page.
    Counted, because the number is the cost — each is a recorded event that
    would never replay again."""
    if not events:
        return []
    contracts = incoming["$events"]["kinds"]
    tokens = incoming.get("$reactions", {}).get("tokens", {})
    thread = thread_structure(events)
    prior_registry = read_json(page_dir / "registry.json") or {}
    revisions = {}

    def page(revision):
        if revision not in revisions:
            revisions[revision] = parse_revision(page_dir, revision)
        return revisions[revision]

    missing = {}
    prior = []
    for e in events:
        kind = e["kind"]
        key = None
        if kind not in contracts:
            key = f"kind `{kind}`"
        elif error := event_contracts.event_record_error(contracts[kind], e):
            key = f"kind `{kind}` record: {error}"
        elif e.get("token") and e["token"] not in tokens:
            # A token the layer drops has no glyph to paint and no pill to withdraw
            # it by, so a standing reaction on it would fall silent — the verb rule
            # (`declared_action_error`) read for the reaction vocabulary.
            key = f"reaction token `{e['token']}` no longer declared by $reactions"
        elif (
            (
                kind == "comment"
                and e.get("holds")
                and (
                    error := event_contracts.held_comment_error(
                        e, page(e["revision"]).by_id, incoming
                    )
                )
            )
            or (
                kind == "comment"
                and e.get("response")
                and (
                    error := event_contracts.version_response_comment_error(
                        e, page(e["revision"]).by_id, incoming
                    )
                )
            )
            or kind == "comment"
            and (
                error := event_contracts.visual_anchor_error(
                    e, page(e["revision"]).by_id, incoming
                )
            )
        ):
            key = f"comment contract: {error}"
        elif kind == "action" and (
            error := event_contracts.declared_action_error(
                e,
                page(e["revision"]).by_id,
                thread.by_id,
                incoming,
                prior_registry,
            )
        ):
            key = f"action contract: {error}"
        elif kind == "request" and (
            error := declared_request_error(e, page(e["revision"]), thread, incoming)
            or request_lifecycle_error(
                e,
                prior,
                request_document(e, page(e["revision"]), thread)[2],
            )
        ):
            key = f"request contract: {error}"
        elif kind == "receipt" and (error := receipt_contract_error(e, prior)):
            key = f"receipt contract: {error}"
        elif kind == "report" and (
            error := event_contracts.report_contract_error(
                e, page(e["revision"]).by_id, incoming
            )
        ):
            key = f"report contract: {error}"
        elif e.get("markup") and (
            errors := thread_markup_contract_errors(thread.fragments[e["id"]], incoming)
        ):
            key = "thread markup contract: " + "; ".join(errors)
        else:
            key = None
        prior.append(e)
        if key is not None:
            missing[key] = missing.get(key, 0) + 1
    return [
        f"{n} event{'s' if n != 1 else ''} of {key}"
        for key, n in sorted(missing.items())
    ]
