"""Offline JSON Schema validation shared by registry, markup, and event admission.

Each validator owns a self-contained resource graph and is cached by schema content.
Leaf's date-time format admits only absolute, timezone-aware RFC3339 instants.
"""

import functools
import json
import re
from datetime import datetime

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

FORMAT_CHECKER = FormatChecker()
RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


@FORMAT_CHECKER.checks("date-time")
def is_aware_datetime(value) -> bool:
    """Leaf's self-contained date-time format: one absolute, aware instant."""
    if not isinstance(value, str):
        return True  # the declared JSON Schema owns the type complaint
    return aware_instant(value) is not None


def aware_instant(value: str):
    """The one parse of Leaf's date-time format, or None where the spelling fails."""
    if not RFC3339_DATE_TIME.fullmatch(value):
        return None
    normalized = value[:-1] + "+00:00" if value[-1] in "Zz" else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def schema_resource_registry(schema: dict):
    """One self-contained resource graph for a vendored JSON Schema."""
    resource = DRAFT202012.create_resource(schema)
    registry = Registry().with_resource("", resource).crawl()
    return resource, registry


def json_validator(schema: dict) -> Draft202012Validator:
    """One offline schema reader for every authored/event ingress, including formats.

    Readers are shared by schema content: a read re-validates every stored event
    against the handful of schemas its registry declares, and building the resource
    graph costs far more than validating one small instance against it.
    """
    return _validator(json.dumps(schema, sort_keys=True))


@functools.lru_cache(maxsize=1024)
def _validator(canonical: str) -> Draft202012Validator:
    # Built from its own parse of the key, so a caller that later mutates the dict
    # it passed cannot change the reader that key names.
    schema = json.loads(canonical)
    _, registry = schema_resource_registry(schema)
    return Draft202012Validator(
        schema,
        format_checker=FORMAT_CHECKER,
        registry=registry,
    )


def schema_error(schema: dict, instance) -> str | None:
    """The first deterministic complaint about an instance, if it is invalid."""
    error = min(json_validator(schema).iter_errors(instance), key=str, default=None)
    return schema_error_message(error) if error else None


def json_value(value) -> str:
    """One reader-facing rendering of a structured JSON value."""
    return json.dumps(value, ensure_ascii=False)


def schema_error_message(error) -> str:
    """Render invalid JSON values as JSON, from the validator's structured reading.

    jsonschema's default messages use Python repr for JSON arrays, objects,
    booleans and null. Keep its property/pattern diagnoses, which name text,
    and render value-bearing constraints from their declared keyword and value.
    """
    actual = json_value(error.instance)
    if error.schema is False:
        return f"schema does not allow {actual}"
    expected = json_value(error.validator_value)
    messages = {
        "type": f"{actual} is not of type {expected}",
        "enum": f"{actual} is not one of {expected}",
        "const": f"expected {expected}, got {actual}",
        "anyOf": f"{actual} is not valid under any of the given schemas",
        "oneOf": f"{actual} must match exactly one of the given schemas",
        "not": f"{actual} must not match {expected}",
        "uniqueItems": f"{actual} has non-unique elements",
    }
    if error.validator in messages:
        return messages[error.validator]
    if (
        isinstance(error.instance, (dict, list, bool)) or error.instance is None
    ) and error.validator not in {
        "required",
        "additionalProperties",
        "dependentRequired",
    }:
        return f"{actual} does not satisfy {error.validator}: {expected}"
    return error.message


def unresolved_schema_reference(schema: dict) -> str | None:
    """Return the first operative ref not supplied by this schema resource graph.

    Draft 2020-12 decides which members contain subschemas. Walking those resources
    avoids mistaking literal instance data under `const`, `enum`, or `default` for a
    reference while still checking refs behind properties, combinators, and $defs.
    """
    resource, registry = schema_resource_registry(schema)

    def visit(current, resolver) -> str | None:
        contents = current.contents
        if isinstance(contents, dict):
            for keyword in ("$ref", "$dynamicRef"):
                reference = contents.get(keyword)
                if not isinstance(reference, str):
                    continue
                try:
                    resolver.lookup(reference)
                except Unresolvable:
                    return reference
        for subcontents in DRAFT202012.subresources_of(contents):
            subresource = DRAFT202012.create_resource(subcontents)
            if reference := visit(
                subresource,
                resolver.in_subresource(subresource),
            ):
                return reference
        return None

    return visit(resource, registry.resolver_with_root(resource))
