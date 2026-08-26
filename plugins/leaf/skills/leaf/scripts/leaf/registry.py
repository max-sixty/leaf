"""Merged widget vocabulary, validation, and registry-file boundary."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import click
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from leaf.files import file_stamp, read_json
from leaf.schema import (
    ASSETS,
    ATTRIBUTE_KEYS,
    DATA_CONTRACT_NAME,
    DATA_SOURCE_NAME,
    EXTENSION_SCHEMA,
    GUIDANCE_SCHEMA,
    HTML_NAME,
    WIDGET_NAME,
)

FORMAT_CHECKER = FormatChecker()
RFC3339_DATE_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


@FORMAT_CHECKER.checks("date-time")
def is_aware_datetime(value) -> bool:
    """Leaf's self-contained date-time format: one absolute, aware instant."""
    if not isinstance(value, str):
        return True  # the declared JSON Schema owns the type complaint
    if not RFC3339_DATE_TIME.fullmatch(value):
        return False
    normalized = value[:-1] + "+00:00" if value[-1] in "Zz" else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.utcoffset() is not None


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


def visual_part_attribute(entry: dict) -> str | None:
    """The authored token-list attribute behind a part-addressable visual."""
    visual = entry.get("x-visual")
    return visual.get("parts") if isinstance(visual, dict) else None


def visual_parts(record: dict, registry: dict) -> tuple[str, ...]:
    """Stable visual-part ids declared by one authored widget instance."""
    attribute = visual_part_attribute(registry.get(record.get("tag"), {}))
    value = record.get("attrs", {}).get(attribute) if attribute else None
    return tuple(value.split()) if value else ()


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
        click.echo(self.message, file=file or click.get_text_stream("stderr"))


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


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary after its top-level overlays are merged."""
    path = source
    try:
        kinds = registry["$events"]["kinds"]
        names = registry["$languages"]["names"]
        paths = registry["$languages"]["paths"]
        tones = registry["$tones"]["names"]
        data = registry["$data"]
        tokens = registry["$reactions"]["tokens"]
    except (KeyError, TypeError):
        raise RegistryError(
            f"{path}: registry must declare $events.kinds, $languages.names/paths, "
            "$tones.names, $data, and $reactions.tokens"
        )
    if not isinstance(kinds, dict):
        raise RegistryError(f"{path}: $events.kinds must map names to event contracts")
    envelope = {"id", "ts", "author", "kind", "seq"}
    for kind, contract in kinds.items():
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(contract, dict)
            or set(contract) - {"record", "browser"}
            or not isinstance(contract.get("record"), dict)
            or ("browser" in contract and not isinstance(contract["browser"], dict))
        ):
            raise RegistryError(
                f"{path}: $events.kinds must map names to atomic record/browser "
                "contracts"
            )
        for writer, schema in contract.items():
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: $events kind `{kind}` {writer} is not a valid JSON "
                    f"Schema: {error.message}"
                )
        record = contract["record"]
        properties = record.get("properties", {})
        required = record.get("required", [])
        # The record's closed shape, plus the two constraints a kind states over
        # fields it lists — which of two it must carry (comment and reply carry
        # `text` or `token`), and what one field rules out. Both are compared
        # kind for kind below, so a layer cannot loosen the installed contract
        # through them, and both may name only declared fields, checked here.
        constrained = {
            name
            for branch in record.get("oneOf", [])
            for name in branch.get("required", [])
        } | set(record.get("dependentSchemas", {}))
        if (
            not constrained <= set(properties)
            or set(record) - RECORD_CONSTRAINTS
            != {"type", "properties", "required", "additionalProperties"}
            or record.get("type") != "object"
            or not envelope <= set(properties)
            or not envelope <= set(required)
            or properties.get("kind") != {"const": kind}
            or record.get("additionalProperties") is not False
        ):
            raise RegistryError(
                f"{path}: $events kind `{kind}` record must use only type, "
                "properties, required, and additionalProperties (plus oneOf and "
                "dependentSchemas over declared fields) to declare a closed full "
                "event schema with required id/ts/author/kind/seq fields and its "
                "kind const"
            )

    # Compare a vendored or overlaid contract with the installed producers' own.
    # Optional fields may grow; installed fields, requirements, and browser doors
    # may not change.
    current = read_registry_entries(ASSETS / "registry.json")["$events"]["kinds"]
    incompatible = []
    for kind, expected in current.items():
        actual = kinds.get(kind)
        if actual is None:
            incompatible.append(f"kind `{kind}`")
            continue
        expected_record = expected["record"]
        actual_record = actual["record"]
        expected_properties = expected_record["properties"]
        actual_properties = actual_record["properties"]
        changed = sorted(
            name
            for name, schema in expected_properties.items()
            if actual_properties.get(name) != schema
        )
        if changed:
            incompatible.append(f"`{kind}` fields {changed}")
        elif set(actual_record["required"]) != set(expected_record["required"]):
            incompatible.append(f"`{kind}` required fields")
        elif any(
            actual_record.get(key) != expected_record.get(key)
            for key in RECORD_CONSTRAINTS
        ):
            incompatible.append(f"`{kind}` field constraints")
        elif actual.get("browser") != expected.get("browser"):
            incompatible.append(f"`{kind}` browser writer")
    if incompatible:
        raise RegistryError(
            f"{path}: $events.kinds omits or changes contracts the current layer "
            "writes: " + ", ".join(incompatible)
        )
    # $keys documents exactly the x- keys the lint admits, one string per key: the
    # keys are closed here (EXTENSION_SCHEMA), so a member for a key that cannot be
    # declared is documentation of nothing, and a key with no member is one an author
    # reads the catalog for and finds unsaid. `page catalog` prints it and the site's
    # table is generated from it, which is what makes the pin worth keeping.
    keys = registry.get("$keys")
    admitted = set(EXTENSION_SCHEMA["properties"])
    documented = set(keys or {}) - {"description"}
    if (
        not isinstance(keys, dict)
        or not isinstance(keys.get("description"), str)
        or not all(isinstance(text, str) and text for text in keys.values())
        or documented != admitted
    ):
        raise RegistryError(
            f"{path}: $keys must carry a description and one paragraph per x- key the "
            f"lint admits — missing {sorted(admitted - documented)}, "
            f"unadmitted {sorted(documented - admitted)}"
        )
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or len(names) != len(set(names))
    ):
        raise RegistryError(
            f"{path}: $languages.names must be a unique list of strings"
        )
    if not isinstance(paths, dict) or not all(
        isinstance(extension, str) and language in names
        for extension, language in paths.items()
    ):
        raise RegistryError(
            f"{path}: $languages.paths must map extensions to declared languages"
        )
    # Shape, not just presence, because `declared_word_errors` asks a list for membership
    # and a string answers the same question by substring: a layer declaring
    # `"names": "ok"` would pass every one-letter tone and paint none of them, which is
    # exactly the invisible failure the check exists to catch.
    if (
        not isinstance(tones, list)
        or not all(isinstance(tone, str) for tone in tones)
        or len(tones) != len(set(tones))
    ):
        raise RegistryError(f"{path}: $tones.names must be a unique list of strings")
    if (
        not isinstance(data, dict)
        or set(data) != {"description", "contracts"}
        or not isinstance(data.get("description"), str)
        or not data["description"]
        or not isinstance(data.get("contracts"), dict)
    ):
        raise RegistryError(
            f"{path}: $data must carry a description and a contracts object"
        )
    for contract, declaration in data["contracts"].items():
        if (
            not isinstance(contract, str)
            or re.fullmatch(DATA_CONTRACT_NAME, contract) is None
        ):
            raise RegistryError(f"{path}: $data has invalid contract name {contract!r}")
        if (
            not isinstance(declaration, dict)
            or not {"description", "schema"} <= set(declaration)
            or set(declaration) - {"description", "schema", "guidance"}
            or not isinstance(declaration.get("description"), str)
            or not declaration["description"]
            or not isinstance(declaration.get("schema"), dict)
        ):
            raise RegistryError(
                f"{path}: $data contract {contract!r} must carry a description and "
                "schema, with optional guidance"
            )
        guidance_errors = sorted(
            json_validator(GUIDANCE_SCHEMA).iter_errors(
                declaration.get("guidance", {})
            ),
            key=str,
        )
        if guidance_errors:
            raise RegistryError(
                f"{path}: $data contract {contract!r} guidance is invalid: "
                f"{guidance_errors[0].message}"
            )
        try:
            Draft202012Validator.check_schema(declaration["schema"])
        except SchemaError as error:
            raise RegistryError(
                f"{path}: $data contract {contract!r} has an invalid JSON Schema: "
                f"{error.message}"
            )
        if reference := unresolved_schema_reference(declaration["schema"]):
            raise RegistryError(
                f"{path}: $data contract {contract!r} schema reference {reference!r} "
                "does not resolve within the package; data contracts must be "
                "self-contained"
            )
    # Each token whole: every consumer reads the entry directly — the runtime paints
    # `glyph`, `leaf wait` prints `means`, the panel's narrowing reads `settles` — so
    # a missing or misspelled member would be a token that paints nothing or a
    # `settle` that settles nothing, and neither says so anywhere else.
    if not isinstance(tokens, dict) or not all(
        isinstance(name, str)
        and re.fullmatch(HTML_NAME, name)
        and isinstance(entry, dict)
        and not set(entry) - {"glyph", "means", "settles"}
        and isinstance(entry.get("glyph"), str)
        and entry["glyph"].strip()
        and len(entry["glyph"]) <= 4
        and isinstance(entry.get("means"), str)
        and entry["means"]
        and isinstance(entry.get("settles", False), bool)
        for name, entry in tokens.items()
    ):
        raise RegistryError(
            f"{path}: $reactions.tokens must map lowercase token names to entries "
            "with a `glyph` of one or two characters, a non-empty `means`, and "
            "optionally a boolean `settles`"
        )
    invalid_names = [
        tag
        for tag in registry
        if not tag.startswith("$") and re.fullmatch(WIDGET_NAME, tag) is None
    ]
    if invalid_names:
        raise RegistryError(f"{path}: invalid registry entry names: {invalid_names}")
    widgets = {tag: entry for tag, entry in registry.items() if tag.startswith("lf-")}
    # First validate every entry in isolation. Cross-entry checks run only after this
    # pass, so their result cannot depend on which widget happened to be written first.
    for tag, entry in widgets.items():
        try:
            Draft202012Validator.check_schema(entry)
        except SchemaError as error:
            raise RegistryError(
                f"{path}: <{tag}> is not a valid JSON Schema: {error.message}"
            )
        extensions = {
            key: value for key, value in entry.items() if key.startswith("x-")
        }
        errors = sorted(
            json_validator(EXTENSION_SCHEMA).iter_errors(extensions), key=str
        )
        if errors:
            raise RegistryError(
                f"{path}: <{tag}> registry extensions are invalid: {errors[0].message}"
            )
        for channel, verb, spec in state_specs(entry):
            try:
                Draft202012Validator.check_schema(spec["detail"])
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` has an invalid "
                    f"detail schema: {error.message}"
                )
            if spec["detail"].get("type") != "object":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    "must declare an object"
                )
            # A verb carries only the detail keys its entry declares — the
            # premise the layer's own field meanings rest on: both runtimes
            # dispatch thread settlement on `resolves` being present, which
            # is safe exactly because a closed schema makes carrying it a
            # declaration.
            if spec["detail"].get("additionalProperties") is not False:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    "must state additionalProperties: false — a verb carries "
                    "only the detail keys it declares"
                )
            if update := spec.get("update"):
                detail = spec["detail"]
                field = detail.get("properties", {}).get(update)
                if field is None:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` is not declared by its detail schema"
                    )
                if update not in detail.get("required", []):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must be required — every report in the feed "
                        "needs words"
                    )
                if not declares_string(field):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must be a string"
                    )
                if field.get("minLength", 0) < 1:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must set minLength to at least 1"
                    )

    slots = retirement_slots(registry)
    for tag, entry in widgets.items():
        if unknown := sorted(set(entry.get("x-parent", [])) - set(widgets)):
            raise RegistryError(
                f"{path}: <{tag}> x-parent names unknown widgets {unknown}"
            )
        properties = entry.get("properties", {})
        for input_name, spec in entry.get("x-data", {}).items():
            contract = spec["contract"]
            source_attr = spec["source"]
            if contract not in data["contracts"]:
                raise RegistryError(
                    f"{path}: <{tag}> x-data input `{input_name}` names unknown "
                    f"contract {contract!r}"
                )
            source_schema = properties.get(source_attr, {})
            if (
                not isinstance(source_schema, dict)
                or source_schema.get("type") != "string"
                or source_schema.get("pattern") != f"^{DATA_SOURCE_NAME}$"
            ):
                raise RegistryError(
                    f"{path}: <{tag}> x-data input `{input_name}` source attribute "
                    f"`{source_attr}` must be a canonical data source string"
                )
        said = set(entry.get("x-says", {}))
        for role in ("x-awaits", "x-conversation"):
            if entry.get(role) is not None and (
                not isinstance(properties.get("id"), dict)
                or properties["id"].get("type") != "string"
            ):
                raise RegistryError(
                    f"{path}: <{tag}> {role} instances are addressable, so the "
                    "entry must declare a string `id` attribute"
                )
        for key in ATTRIBUTE_KEYS:
            declared = entry.get(key) or ()
            named = {declared} if isinstance(declared, str) else set(declared)
            if unknown := sorted(named - set(properties)):
                raise RegistryError(
                    f"{path}: <{tag}> {key} names undeclared attributes {unknown}"
                )
        if part_attribute := visual_part_attribute(entry):
            if not (
                "id" in entry.get("required", [])
                and isinstance(properties.get("id"), dict)
                and properties["id"].get("type") == "string"
            ):
                raise RegistryError(
                    f"{path}: <{tag}> has addressable visual parts but does not "
                    "require a string `id` for their anchor"
                )
            part_schema = properties.get(part_attribute)
            if not (
                isinstance(part_schema, dict)
                and part_schema.get("type") == "string"
                and part_schema.get("minLength", 0) >= 1
            ):
                raise RegistryError(
                    f"{path}: <{tag}> x-visual parts attribute `{part_attribute}` "
                    "must be a non-empty string"
                )
            if not entry["x-upgrade"]:
                raise RegistryError(
                    f"{path}: <{tag}> declares addressable visual parts but has no "
                    "upgraded handler to resolve them"
                )
        # A drawing's box is the clip around something drawn at a size of its own, and
        # the theme lays it out as a row so the drawing keeps the column's axis and
        # scrolls only past the room. Every child of that element is an item in the row,
        # so a word the layer writes into it stands beside the drawing rather than over
        # it and takes it off the axis by half the word's width — a picture placed
        # slightly wrong, which nothing else on the page has any way to notice. The
        # widget that has words as well as a drawing is a box, which lays out both.
        # (x-paints is the other kind of word and is not this: it renders into the
        # shared clip, which is positioned out of the flow.)
        if entry.get("x-wide") == "drawing" and said:
            raise RegistryError(
                f"{path}: <{tag}> is x-wide: drawing and says {sorted(said)} — a "
                "drawing's box holds what was drawn and lays out nothing beside it, "
                "so a widget that says an attribute as well declares x-wide: box"
            )
        # A predicate names attributes and values the page can actually carry, or its
        # widget silently disappears from every consumer. The value's kind follows the
        # attribute's own schema — a flag is there or it isn't, an enum admits what it
        # lists — and a subschema that states neither contradicts nothing.
        awaits = entry.get("x-awaits", {})
        if entry.get("x-ask"):
            if "id" not in entry.get("required", []):
                raise RegistryError(f"{path}: <{tag}> x-ask does not require an id")
            if entry.get("x-content") != "prose":
                raise RegistryError(
                    f"{path}: <{tag}> x-ask must admit prose around the request it "
                    "frames"
                )
            if awaits:
                raise RegistryError(
                    f"{path}: <{tag}> declares both x-ask and x-awaits — the broader "
                    "Ask frames one nested request; the nested widget owns its state"
                )
        conditions = [
            ("x-awaits", awaits.get("when", {})),
            ("x-awaits", awaits.get("until", {}).get("when", {})),
            ("x-conversation", entry.get("x-conversation", {}).get("when", {})),
            ("x-work", entry.get("x-work", {}).get("when", {})),
        ]
        for declaration, condition in conditions:
            for attr, values in condition.items():
                if attr not in properties:
                    raise RegistryError(
                        f"{path}: <{tag}> {declaration} names undeclared attribute "
                        f"`{attr}`"
                    )
                schema = properties[attr]
                declared = schema if isinstance(schema, dict) else {}
                for value in values:
                    if isinstance(value, bool):
                        # A subschema saying neither a type nor an enum contradicts
                        # nothing; one that says either has told us this attribute
                        # carries a value.
                        if declared.get("type") not in (
                            None,
                            "boolean",
                        ) or declared.get("enum"):
                            raise RegistryError(
                                f"{path}: <{tag}> {declaration} tests `{attr}` as "
                                f"{str(value).lower()}, but that attribute is not a flag"
                            )
                    elif declared.get("type") == "boolean":
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests flag `{attr}` as "
                            f"{value!r}; a flag is there or it isn't"
                        )
                    if (
                        allowed := declared.get("enum")
                    ) is not None and value not in allowed:
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests `{attr}` at "
                            f"{value!r}, which its own enum does not admit"
                        )
                    if errors := sorted(
                        json_validator(schema).iter_errors(value), key=str
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests `{attr}` at "
                            f"{value!r}, which its own schema does not admit: "
                            f"{errors[0].message}"
                        )
        conversation = entry.get("x-conversation", {})
        mutable_values = {
            spec["record"]["attr"]
            for channel in ("x-state", "x-report")
            for spec in entry.get(channel, {}).values()
            if (spec.get("record") or {}).get("kind") == "value"
        }
        if dynamic := sorted(set(conversation.get("when", {})) & mutable_values):
            raise RegistryError(
                f"{path}: <{tag}> x-conversation predicate attributes are authored "
                f"and static, but {dynamic} are written by value records"
            )
        data_sources = {spec["source"] for spec in entry.get("x-data", {}).values()}
        if dynamic := sorted(data_sources & mutable_values):
            raise RegistryError(
                f"{path}: <{tag}> x-data source attributes are authored bindings, "
                f"but {dynamic} are written by value records"
            )
        work = entry.get("x-work")
        if work and work["seat"] == "content":
            if entry.get("x-inline"):
                raise RegistryError(
                    f"{path}: <{tag}> declares a content work seat but is inline; "
                    "local work chrome needs a block slot"
                )
            if entry.get("x-content") != "prose":
                raise RegistryError(
                    f"{path}: <{tag}> declares a content work seat but x-content is "
                    f"{entry.get('x-content')}; generated local chrome may only join "
                    "authored prose"
                )
        if work and work["seat"] == "conversation" and not entry.get("x-conversation"):
            raise RegistryError(
                f"{path}: <{tag}> declares a conversation work seat but declares "
                "no x-conversation"
            )
        # A blanket answer is one of this widget's own verbs, so the log records it
        # the way every other decision is recorded.
        answers = awaits.get("answers", [])
        if unknown := sorted(set(answers) - set(entry.get("x-state", {}))):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits names undeclared answer verbs {unknown}"
            )
        if awaits.get("rollup") and "id" not in entry.get("required", []):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits rollup through descendants does "
                "not require an id"
            )
        if (blanket := awaits.get("all")) and blanket not in entry.get("x-state", {}):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits answers every one at once with "
                f"`{blanket}`, which it does not declare as an x-state verb"
            )
        if blanket and blanket not in answers:
            raise RegistryError(
                f"{path}: <{tag}> x-awaits blanket verb `{blanket}` is not one of "
                "its answer verbs"
            )
        # The until verb closes a thread ask, so it too is one of the widget's own
        # verbs — same rule as `all`, same reason.
        if (until := awaits.get("until")) and until["verb"] not in entry.get(
            "x-state", {}
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits holds asks open until `{until['verb']}`, "
                "which it does not declare as an x-state verb"
            )
        needs_upgrade = [
            key
            for key in (
                "x-state",
                "x-report",
                "x-language",
                "x-verbatim",
                "x-shadow",
                "x-conversation",
            )
            if entry.get(key) and not entry["x-upgrade"]
        ]
        if needs_upgrade:
            raise RegistryError(
                f"{path}: <{tag}> declares {', '.join(needs_upgrade)} "
                "but has no upgraded handler"
            )
        # A version overrules a standing report with `overruled` on the element,
        # so a widget with an agent channel that doesn't declare the attribute is
        # one whose every report contradiction is unpublishable.
        if entry.get("x-report") and not (
            isinstance(properties.get("overruled"), dict)
            and properties["overruled"].get("type") == "boolean"
        ):
            raise RegistryError(
                f"{path}: <{tag}> declares x-report but not the boolean `overruled` "
                "attribute a version overrules a standing report with"
            )
        # The same rule for the other channel: a version that rewrites what a
        # decision rested on must say `restated` on the element ($restated),
        # and a closed schema without the attribute is a widget whose every
        # rewrite is unpublishable — the words gate demands an attribute the
        # widget's own schema refuses. Held only where a verb folds on the
        # widget itself: a verb folding per child (move's "card") rests its
        # decisions on elements this entry doesn't name.
        folds_whole = any(
            spec["unit"] == "widget" for spec in entry.get("x-state", {}).values()
        )
        if folds_whole and not (
            isinstance(properties.get("restated"), dict)
            and properties["restated"].get("type") == "boolean"
        ):
            raise RegistryError(
                f"{path}: <{tag}> declares x-state verbs that fold on the widget "
                "but not the boolean `restated` attribute a version retracts a "
                "decision with"
            )
        # A facet is one independently standing fact. Every way of stating that
        # fact therefore agrees on what it folds over and how authored markup can
        # record it. The name itself remains local to the tag: two widget families
        # may both call a facet `status` without sharing a contract.
        facet_specs: dict[str, tuple[str, str, dict | None]] = {}
        for channel, verb, spec in state_specs(entry):
            facet = spec["facet"]
            previous = facet_specs.get(facet)
            if previous is None:
                facet_specs[facet] = (channel, verb, spec.get("record"))
                continue
            previous_channel, previous_verb, previous_record = previous
            previous_spec = entry[previous_channel][previous_verb]
            if spec["unit"] != previous_spec["unit"]:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` and "
                    f"{previous_channel} verb `{previous_verb}` share facet "
                    f"`{facet}` but declare different fold units "
                    f"(`{spec['unit']}` and `{previous_spec['unit']}`)"
                )
            if spec.get("record") != previous_record:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` and "
                    f"{previous_channel} verb `{previous_verb}` share facet "
                    f"`{facet}` but do not declare identical record forms "
                    "(or both remain recordless)"
                )

        # Eligibility reuses the one standing-request projection. Close the target
        # relation here: self must be an ask, and every holder a child permits must be
        # one. Runtime evaluators then neither guess a widget family nor maintain a
        # second representation of whether the request remains open.
        for verb, spec in entry.get("x-state", {}).items():
            requirement = spec.get("requires")
            if not requirement:
                continue
            target_tags = (
                [tag] if requirement["target"] == "self" else entry.get("x-parent", [])
            )
            if not target_tags:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` requires its parent, "
                    f"but <{tag}> declares no x-parent"
                )
            if not all(
                widgets[target].get("x-awaits") is not None for target in target_tags
            ):
                missing = sorted(
                    target
                    for target in target_tags
                    if widgets[target].get("x-awaits") is None
                )
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` requires "
                    f"{requirement['target']} awaiting state, but {missing} do not "
                    "declare x-awaits"
                )
            idless = sorted(
                target
                for target in target_tags
                if requirement["target"] == "parent"
                and "id" not in widgets[target].get("required", [])
            )
            if idless:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` requires "
                    f"{requirement['target']} awaiting state, but {idless} do not "
                    "require an id"
                )
        # A facet is semantic, but its record writes a physical slot. Body and
        # position have one per unit; value and attribute-set are keyed by attr.
        physical_slots: dict[tuple[str, str, str | None], tuple[str, str, str]] = {}
        for channel, verb, spec in state_specs(entry):
            record = spec.get("record")
            if record is None:
                continue
            kind = record["kind"]
            attr = record.get("attr")
            key = spec["unit"], kind, attr
            previous = physical_slots.setdefault(key, (channel, verb, spec["facet"]))
            previous_channel, previous_verb, previous_facet = previous
            if previous_facet == spec["facet"]:
                continue
            slot = kind + (f" `{attr}`" if attr else "")
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` (facet "
                f"`{spec['facet']}`) and {previous_channel} verb "
                f"`{previous_verb}` (facet `{previous_facet}`) claim the "
                f"same physical record slot (unit `{spec['unit']}`, "
                f"{slot}); distinct facets must record independently"
            )

        # A resolves-bearing widget has one answer fact. Thread history can outlive
        # the markup that declared its verbs, so both thread builders deliberately
        # fold answers by widget id alone; requiring every action verb on that tag
        # to share the answer facet makes that historical key exact rather than a
        # compatibility approximation.
        state = entry.get("x-state", {})
        resolving = [
            (verb, spec)
            for verb, spec in state.items()
            if "resolves" in spec["detail"].get("properties", {})
        ]
        if resolving:
            answer_verb, answer_spec = resolving[0]
            answer_facet = answer_spec["facet"]
            for verb, spec in state.items():
                if spec["facet"] != answer_facet:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` uses facet "
                        f"`{spec['facet']}`, but `{answer_verb}` declares "
                        "`resolves`; every x-state verb on a resolves-bearing "
                        f"widget must share its answer facet `{answer_facet}`"
                    )

        # One rule set for both channels: x-state and x-report differ in
        # precedence, not in how a verb, its facet, unit, and record hang together.
        for channel, verb, spec in state_specs(entry):
            detail_properties = spec["detail"].get("properties", {})
            required = set(spec["detail"].get("required", []))
            unit = spec["unit"]
            fields = [] if unit == "widget" else [unit]
            record = spec.get("record")
            if record:
                fields.append(record["value"])
                if record["kind"] == "position":
                    fields.append(record["order"])
                    if record["within"] not in widgets:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records a "
                            f"position within unknown widget <{record['within']}>"
                        )
                    if spec["unit"] == "widget" and record["within"] not in entry.get(
                        "x-parent", []
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"its own position within <{record['within']}>, which "
                            "its x-parent does not admit"
                        )
                if record["kind"] == "body":
                    if entry.get("x-content") != "data":
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            "its body, so x-content must be data; projection "
                            "states text rather than a prose subtree"
                        )
                    nested = sorted(
                        child
                        for child, child_entry in widgets.items()
                        if tag in child_entry.get("x-parent", [])
                    )
                    if nested:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"its body but admits nested widgets {nested}; a "
                            "text statement cannot reconstruct their state"
                        )
                if record["kind"] == "value":
                    attr = record["attr"]
                    if attr not in properties:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"undeclared attribute `{attr}`"
                        )
                    # Projection rebuilds a refused gesture from authored state.
                    # A required string value gives every baseline an absolute
                    # action detail; absence is represented by an admitted value.
                    if attr not in entry.get("required", []):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"optional attribute `{attr}`; recorded state must be "
                            "required so its authored value can be replayed"
                        )
                    # An x-says value is words the reader sees, and the file's
                    # reading takes them from the markup — replay writing one
                    # would change what the page says while that reading held
                    # still, the desync the fence rules exist to prevent.
                    if attr in said:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` records "
                            f"x-says attribute `{attr}`, whose value is words "
                            "the reader sees — declared state may not move the "
                            "page's words"
                        )
            # `resolves` is a reserved detail field: thread settlement reads it
            # off every action as "the comment thread this action answers"
            # (build_threads, in both runtimes), so a verb spelling the name
            # means that or is refused here — a widget using it otherwise
            # would settle a thread silently.
            if "resolves" in detail_properties:
                # The reader's channel only. Both thread builders read `resolves`
                # off actions, so the name on a report verb declares an answer
                # nothing gives: the report would fold like any other and settle
                # no thread ever — the feature nobody wired up, which this door
                # exists to turn into an error. A thread is the reader's to close,
                # or an action of theirs; the agent's own way is `leaf resolve`.
                if channel != "x-state":
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                        "field `resolves`, a reserved name (the comment thread "
                        "this action answers) — only an x-state verb settles a "
                        "thread, so rename the field"
                    )
                if detail_properties["resolves"] != {"type": "string"}:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                        "field `resolves`, a reserved name (the comment thread "
                        'this action answers) — declare it {"type": "string"} or '
                        "rename the field"
                    )
                # A thread is answered by the ask, and an ask is a widget
                # instance (x-awaits) — so the answer is absolute across the
                # widget, and both thread builders key the standing answer on
                # the widget id, the one key a log outlives its markup with.
                # A per-part verb answering a thread would fold per part and
                # settle per widget, and the disagreement is invisible: the
                # thread reads right until a second part is acted on. Whoever
                # writes that widget needs an ask per part first, and this is
                # where they find that out.
                if unit != "widget":
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` answers a "
                        f"comment thread (`resolves`) but folds per `{unit}` — "
                        "a thread is answered by the ask, and an ask is the "
                        "whole widget"
                    )
            undeclared = [field for field in fields if field not in detail_properties]
            optional = [field for field in fields if field not in required]
            if undeclared or optional:
                problem = (
                    f"does not declare {undeclared}"
                    if undeclared
                    else f"does not require {optional}"
                )
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` reads detail fields "
                    f"its schema {problem}"
                )
            # Undo restores a recorded action from authored markup. That markup
            # can reconstruct exactly the fold unit and the record's value/order;
            # any other required field would make a valid declaration impossible
            # to restore without a widget-specific default hidden in core.
            unrestorable = sorted(required.difference(fields))
            if channel == "x-state" and record and unrestorable:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` requires detail "
                    f"fields {unrestorable} that authored markup cannot restore"
                )
            if unit != "widget" and record and record["kind"] != "position":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` records per-part "
                    "state; only position records support that"
                )

            if unit != "widget" and not declares_string(detail_properties[unit]):
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` fold unit `{unit}` "
                    "must be a string"
                )
            if record:
                value = record["value"]
                schema = detail_properties[value]
                # An attribute record names the set of elements wearing it, so its
                # detail field is a list of ids however many the group allows —
                # nothing downstream has to ask which kind of group it came from.
                if record["kind"] == "attribute":
                    items = schema.get("items") if isinstance(schema, dict) else None
                    if not (
                        isinstance(schema, dict)
                        and schema.get("type") == "array"
                        and isinstance(items, dict)
                        and items.get("type") == "string"
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must be an array of strings"
                        )
                elif record["kind"] == "value":
                    # The record reads and writes the attribute, so its detail
                    # field speaks the attribute's own schema — one vocabulary,
                    # or the log's contract and the markup's drift apart.
                    if schema != properties[record["attr"]]:
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must carry attribute "
                            f"`{record['attr']}`'s own schema"
                        )
                    string_enum = (
                        isinstance(schema, dict)
                        and isinstance(schema.get("enum"), list)
                        and bool(schema["enum"])
                        and all(isinstance(value, str) for value in schema["enum"])
                    )
                    if not (declares_string(schema) or string_enum):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"value `{value}` must be a string or string enum; "
                            "HTML attributes cannot restore another JSON type"
                        )
                elif not declares_string(schema):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
                        f"value `{value}` must be a string"
                    )
                if record["kind"] == "position":
                    order = detail_properties[record["order"]]
                    if not (isinstance(order, dict) and order.get("type") == "integer"):
                        raise RegistryError(
                            f"{path}: <{tag}> {channel} verb `{verb}` record "
                            f"order `{record['order']}` counts the unit's "
                            "siblings, so its detail field must be an integer"
                        )
        # Withdrawal is the author taking an unanswered question back, and the
        # entry says which of its own outcomes that leaves the page in
        # (retirable_ids). A verb no slot of this widget retires under would
        # license nothing but the wrapper, so the withdrawal it promises would
        # fail as "ids dropped" on the version that tried it — the misdeclaration
        # is invisible until then, and this is where its author is standing.
        withdrawn = entry.get("x-withdrawn-as")
        if withdrawn is not None and withdrawn not in slots.get(tag, {}):
            raise RegistryError(
                f"{path}: <{tag}> x-withdrawn-as `{withdrawn}` retires none of its "
                "slots; withdrawing it would leave their ids on the page"
            )
        retired = entry.get("x-retired-when")
        if retired is None:
            continue
        # Every holder, not the first: a slot that retires on its parent's verb has
        # to retire whichever parent it was written in, or it would be settled under
        # one and undecidable under another.
        for parent in entry["x-parent"]:
            parent_state = widgets[parent].get("x-state", {})
            if retired not in parent_state:
                raise RegistryError(
                    f"{path}: <{tag}> x-retired-when `{retired}` is invalid: "
                    f"<{parent}> does not declare that x-state verb"
                )
            if parent_state[retired]["unit"] != "widget":
                raise RegistryError(
                    f"{path}: <{tag}> x-retired-when `{retired}` must fold by widget"
                )
    # A holder's retired slots are halves of one decision; outcomes on different
    # facets could stand at once, leaving no single settlement to render.
    for holder, outcomes in slots.items():
        state = widgets[holder]["x-state"]
        facets = {state[outcome]["facet"] for outcome in outcomes}
        if len(facets) > 1:
            mapping = ", ".join(
                f"`{outcome}` → `{state[outcome]['facet']}`" for outcome in outcomes
            )
            raise RegistryError(
                f"{path}: <{holder}> x-retired-when outcomes span facets "
                f"({mapping}); every retirement outcome for one holder must "
                "share one facet"
            )
    # Asked only after the record and retirement gates above have reported their
    # more fundamental structural errors. An answer closes the whole ask, so its
    # fold coordinate must be the widget rather than one detail-named child.
    for tag, entry in widgets.items():
        answers = (entry.get("x-awaits") or {}).get("answers", [])
        if non_widget := sorted(
            verb for verb in answers if entry["x-state"][verb]["unit"] != "widget"
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits answer verbs {non_widget} must fold on "
                "the widget"
            )
        until = (entry.get("x-awaits") or {}).get("until")
        if until and entry["x-state"][until["verb"]]["unit"] != "widget":
            raise RegistryError(
                f"{path}: <{tag}> x-awaits until verb `{until['verb']}` must fold "
                "on the widget"
            )
    return registry


_registries = {}  # registry.json -> (its stamp, the vocabulary it holds)


def read_registry(path: Path):
    """Read and validate one complete registry vocabulary, once per vendored file.

    `page init` writes a page's registry.json and nothing writes it again, while an
    action POST asks for the whole vocabulary before it can check a single press —
    so every press re-linted forty frozen entries, an order of magnitude more work
    than the contract check it was preparing for."""
    stamp = file_stamp(path)
    if stamp and (held := _registries.get(path)) and held[0] == stamp:
        return held[1]
    entries = read_registry_entries(path)
    registry = None if entries is None else validate_registry(entries, path)
    if stamp:
        _registries[path] = (stamp, registry)
    return registry


def load_registry(page_dir: Path):
    """The page's complete vendored vocabulary, or None before `page init`."""
    return read_registry(page_dir / "registry.json")


def layer_generation(page_dir: Path) -> str:
    """The epoch shared by this page's vendored runtime and server contract."""
    registry = read_registry_entries(page_dir / "registry.json")
    generation = (registry or {}).get("$layer", {}).get("generation")
    if not isinstance(generation, str) or not generation:
        raise RegistryError(
            f"{page_dir / 'registry.json'}: vendored registry lacks $layer.generation; "
            "run `leaf page init`"
        )
    return generation


def require_registry(page_dir: Path) -> dict:
    """The vendored vocabulary, for a command that has nothing to do without one."""
    registry = load_registry(page_dir)
    if registry is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    return registry


# The record keys that constrain declared fields rather than list them.
RECORD_CONSTRAINTS = frozenset({"oneOf", "dependentSchemas"})


def merge_layer_entries(merged: dict, entries: dict) -> None:
    """Fold one layer's top-level registry entries into the merge.

    A tag entry replaces the earlier one whole; schemas never deep-merge,
    because a half-old, half-new contract is no layer's vocabulary. A $ entry
    merges by member: it is not a contract but the layer's namespace of shared
    facts. Under replace-whole, a project declaring its one idiom vendored a
    $idioms holding exactly that idiom — its theme rules kept styling,
    theme.css concatenating where the registry did not, while `page catalog`
    silently dropped the shipped ten. A member that is itself a map merges by
    its own keys for the same reason one level down: $languages.paths is
    indexed by extension, and a layer adding `.svelte` must not silently drop
    every shipped extension with it. Scalar and list members replace whole —
    a names list is one statement — and the grain here decides nothing the
    gates don't re-check: validation and the vocabulary stamp read the merged
    result, whichever layer each piece came from.

    Inside a map member the merge is JSON merge-patch: a later layer's value
    replaces the key, a new key joins, and `null` removes one — which is the
    only way a project can take a shipped reaction token off its bar, or a user
    an extension off `$languages.paths`, without restating the whole map.
    """
    for name, entry in entries.items():
        earlier = merged.get(name)
        if not (name.startswith("$") and earlier is not None):
            merged[name] = entry
            continue
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {
                    k: v for k, v in {**earlier[key], **value}.items() if v is not None
                }
        merged[name] = {k: v for k, v in combined.items() if v is not None}


def reaction_tokens(registry: dict | None) -> dict:
    """The merged reaction vocabulary, token → entry, in declared order."""
    return (registry or {}).get("$reactions", {}).get("tokens", {})


def described(event: dict, registry: dict | None) -> dict:
    """A reaction event with its token's `means` beside it, so whoever reads the
    line — `leaf wait`'s consumer, `page state`'s — meets a custom token
    already explained. A token the vendored layer no longer declares keeps its
    word and says nothing more. Any other event passes through as it is."""
    token = event.get("token")
    if not token:
        return event
    entry = reaction_tokens(registry).get(token)
    return {**event, "means": entry["means"]} if entry else event


def retirement_slots(registry: dict) -> dict:
    """holder tag → {outcome verb → the tags that leave the page under it}: every
    holder/slot pair `x-retired-when` relates, the slot naming the outcome and
    `x-parent` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or not entry.get("x-retired-when"):
            continue
        outcome = entry["x-retired-when"]
        for holder in entry["x-parent"]:
            slots.setdefault(holder, {}).setdefault(outcome, []).append(tag)
    return slots
