"""Shared registry input, schema, and declaration readings."""

import json
import re
from datetime import datetime
from pathlib import Path

import click
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from leaf.files import read_json
from leaf.schema import ELEMENT_ID, EXTENSION_SCHEMA, GUIDANCE_SCHEMA

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
    """One offline schema reader for every authored/event ingress, including formats."""
    _, registry = schema_resource_registry(schema)
    return Draft202012Validator(
        schema,
        format_checker=FORMAT_CHECKER,
        registry=registry,
    )


def schema_error(schema: dict, instance) -> str | None:
    """The first deterministic complaint about an instance, if it is invalid."""
    error = min(json_validator(schema).iter_errors(instance), key=str, default=None)
    return error.message if error else None


# A reader over a schema that never changes is itself a constant. Built where they
# were used, these two were compiled once per widget and once per data contract: a
# layer of twenty-eight widgets built the extension reader twenty-eight times on
# every `page init`, of the ninety-one schema resource graphs an init built at all.
# Every other reader in this codebase reads a schema its caller supplies, so these
# are the whole of the case.
EXTENSION_READER = json_validator(EXTENSION_SCHEMA)
GUIDANCE_READER = json_validator(GUIDANCE_SCHEMA)

CREATED_CHILDREN_DETAIL_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{ELEMENT_ID}$"},
    "additionalProperties": {"type": "string", "minLength": 1},
}


def created_children(event: dict, spec: dict) -> dict:
    """The generated child id-to-words map declared by one validated action."""
    creates = spec.get("creates")
    return event["detail"].get(creates["field"], {}) if creates else {}


def visual_part_attribute(entry: dict) -> str | None:
    """The authored token-list attribute behind a part-addressable visual."""
    visual = entry.get("x-visual")
    return visual.get("parts") if isinstance(visual, dict) else None


def visual_parts(record: dict, registry: dict) -> tuple[str, ...]:
    """Stable visual-part ids declared by one authored widget instance."""
    attribute = visual_part_attribute(registry.get(record.get("tag"), {}))
    value = record.get("attrs", {}).get(attribute) if attribute else None
    return tuple(value.split()) if value else ()


def registry_path(registry: dict, path: str):
    """Resolve a dotted package declaration such as `$command.widgets`."""
    value = registry
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


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


class RegistryError(click.ClickException):
    """A registry that is not a vocabulary, raised rather than exited because two doors
    read one. The CLI prints the message and stops; the page server owes the browser an
    answer, and `sys.exit` inside its request handler killed the connection mid-POST
    while every other rejection beside it returned a 400 — so a page whose vendored
    stamp had fallen behind the running layer met the reader's click with a dead socket
    and no words. Click renders an escaped one bare, at whichever command reached it, so
    a refusal from here reads like every other refusal this CLI writes."""

    def show(self, file=None) -> None:
        if file is None:
            click.echo(self.message, err=True)
        else:
            click.echo(self.message, file=file)


def read_registry_entries(path: Path):
    """Read the top-level entries one registry layer contributes."""
    if (path.exists() or path.is_symlink()) and not path.is_file():
        raise RegistryError(f"{path}: registry.json must be a file")
    try:
        registry = read_json(path)
    except json.JSONDecodeError as error:
        raise RegistryError(f"{path}: invalid JSON ({error.msg}, line {error.lineno})")
    except UnicodeDecodeError:
        raise RegistryError(f"{path} must be UTF-8")
    if registry is None:
        if not path.is_file():
            return None
        raise RegistryError(f"{path}: registry must be a JSON object")
    if not isinstance(registry, dict):
        raise RegistryError(f"{path}: registry must be a JSON object")
    non_objects = [
        name for name, entry in registry.items() if not isinstance(entry, dict)
    ]
    if non_objects:
        raise RegistryError(f"{path}: registry entries must be objects: {non_objects}")
    return registry


def declares_string(field_schema) -> bool:
    """Whether a detail field allows a string and nothing else, however it says so."""
    declared = field_schema.get("type") if isinstance(field_schema, dict) else None
    allowed = {declared} if isinstance(declared, str) else set(declared or [])
    return allowed == {"string"}


def state_specs(entry: dict):
    """The state and report verb declarations on one widget entry."""
    for channel in ("x-state", "x-report"):
        for verb, spec in entry.get(channel, {}).items():
            yield channel, verb, spec
