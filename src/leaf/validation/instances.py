"""Registry-declared markup instance validation."""

import re

from leaf.findings import Finding, element_at
from leaf.gesture_words import leading_title_node
from leaf.obligations import (
    encloses,
    local_obligation_entry,
)
from leaf.projection import enclosing_widgets, recorded_owner
from leaf.registry.contract import (
    exhibits,
    is_element_name,
    matches_when,
    registry_path,
    retirement_slots,
    state_specs,
)
from leaf.registry.schema import json_validator, schema_reading
from leaf.shown_answers import shown_errors
from leaf.structure import AUTHORED_ALLOCATIONS, SourceDocument

from .markup import found_at, structure_errors

_GLOBAL_ATTRIBUTE = re.compile(r"class|style|title|lang|dir|aria-[a-z]+|data-(?!lf-).+")


def member_holders(rec: dict, registry: dict):
    """An element's enclosing widgets within its quotation, innermost first.

    A quotation cannot supply members to an owner outside it. An owner quoted as
    a whole still holds its own members, since they reach it before the boundary.
    """
    for node in enclosing_widgets(rec):
        if exhibits(node["attrs"], registry.get(node["tag"], {})):
            break
        yield node


def thread_markup_contract_errors(parser, registry: dict) -> list[Finding]:
    """Registry-derived errors shared by admission and `page init`."""
    errors = fragment_errors(parser, registry)
    settled = retirement_slots(registry)
    errors.extend(
        found_at("frozen-settlement", rec)
        for rec in parser.lf_elements
        if rec["tag"] in settled
    )
    return errors


def widget_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """Validate parsed lf-* elements against the registry: schema over the
    attribute instance, x-owners nesting, and the x-content model."""
    errors = []
    # Member containers admit exactly the tags that declare them as x-owners.
    members_of = {}
    for tag, entry in registry.items():
        if not is_element_name(tag):
            continue
        for owner in entry.get("x-owners", []):
            members_of.setdefault(owner, set()).add(tag)

    for rec in lf_elements:
        tag = rec["tag"]
        entry = registry.get(tag)
        if entry is None:
            errors.append(found_at("unknown-widget", rec))
            continue
        # The element validates as the instance built from its attributes:
        # values as strings, flag attributes as True. HTML's two flag spellings
        # (bare and ="") both mean true; a literal value on a flag stays a string
        # so it fails loudly rather than silently meaning true. HTML's global
        # attributes that say nothing a widget records stand outside every schema
        # unless the entry declares one: `class` and `style` are the page's styling
        # hooks (the runtime sets its own classes and custom properties beside the
        # author's, and Leaf's own `lf-` classes are refused as markers), and `title`,
        # `lang`, `dir`, `aria-*` and the page's own `data-*` describe the element as
        # on any other. `data-lf-*` stays Leaf's; `hidden` and `inert` still validate,
        # since either could hide what the widget asks of the user.
        props = entry.get("properties", {})
        instance = {}
        for name, value in rec["attrs"].items():
            if name in AUTHORED_ALLOCATIONS or (
                name not in props and _GLOBAL_ATTRIBUTE.fullmatch(name)
            ):
                continue
            prop = props.get(name)
            is_flag = isinstance(prop, dict) and prop.get("type") == "boolean"
            instance[name] = True if value in (None, "") and is_flag else (value or "")
        for err in sorted(json_validator(entry).iter_errors(instance), key=str):
            errors.append(found_at("attribute-schema", rec, **schema_reading(err)))
        for verb, spec in state_specs(entry):
            binding = spec.get("contract")
            if not binding or not (name := rec["attrs"].get(binding["attribute"])):
                continue
            if name not in registry["$data"]["contracts"]:
                errors.append(
                    found_at(
                        "instance-contract", rec, verb=verb, contract=name, **binding
                    )
                )
        for input_name, spec in entry.get("x-data", {}).items():
            if rec["attrs"].get(spec.get("source")) and rec["attrs"].get(
                spec.get("reference")
            ):
                errors.append(found_at("ambiguous-data-binding", rec, input=input_name))
        # A member stands directly in an owner; one declaring x-within may also stand
        # at any depth inside one of the regions it names. It belongs to its nearest
        # owner, so going outward it must meet such a region before any owner.
        want_owners = entry.get("x-owners", [])
        within = entry.get("x-within", [])
        nearest = next(
            (
                node["tag"]
                for node in member_holders(rec, registry)
                if node["tag"] in within or node["tag"] in want_owners
            ),
            None,
        )
        if want_owners and rec["parent"] not in want_owners and nearest not in within:
            errors.append(
                found_at(
                    "not-member",
                    rec,
                    owners=want_owners,
                    parent=rec["parent"],
                    within=within,
                )
            )
        # Tags that name this declaration in x-owners are its admissible members under
        # any content model. "data" takes one <pre>, "members" takes element members
        # only, and "empty" takes nothing at all.
        content = entry["x-content"]
        allowed = members_of.get(tag, set())
        stray = sorted({c for c in rec["children"] if c not in allowed})
        if content == "empty" and (rec["children"] or rec["text"]):
            errors.append(found_at("content-empty", rec))
        elif content == "data":
            others = [c for c in stray if c != "pre"]
            if rec["children"].count("pre") != 1 or others:
                errors.append(found_at("data-body", rec, children=rec["children"]))
            if rec["text"]:
                errors.append(found_at("text-outside-pre", rec))
        elif content == "members":
            if stray:
                errors.append(
                    found_at("stray-members", rec, admits=sorted(allowed), found=stray)
                )
            if rec["text"]:
                errors.append(found_at("loose-text", rec))
    byid = {rec["attrs"]["id"]: rec for rec in lf_elements if rec["attrs"].get("id")}
    return errors + attribute_slot_errors(lf_elements, byid, registry)


def attribute_slot_errors(
    elements, byid: dict, registry: dict, *, holders: dict | None = None
) -> list[Finding]:
    """Scalar records cannot share their node's attribute with a parent's selection.

    Declarations remain reusable in unrelated compositions. Ownership follows the
    canonical physical-slot reading, including holder overrides for a proposed move.
    Callers select the elements whose composition they are validating.
    """
    errors = []
    for rec in elements:
        identity = rec["attrs"].get("id")
        if identity is None:
            continue
        for verb, spec in state_specs(registry.get(rec["tag"], {})):
            record = spec.get("record") or {}
            if record.get("kind") != "value":
                continue
            attribute = {"kind": "attribute", "attr": record["attr"]}
            owner = recorded_owner(identity, attribute, byid, registry, holders=holders)
            if owner is None:
                continue
            owner_verb = next(
                verb
                for verb, spec in state_specs(registry[byid[owner]["tag"]])
                if spec.get("record") == attribute
            )
            errors.append(
                found_at(
                    "member-record-slot",
                    rec,
                    id=identity,
                    attr=record["attr"],
                    value_verb=verb,
                    owner=owner,
                    owner_verb=owner_verb,
                )
            )
    return errors


def layout_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """Validate the direct grammar of registry-declared structural elements: a pane is an
    optional header, exactly one body element, and an optional footer."""
    errors = []
    for rec in lf_elements:
        role = registry.get(rec["tag"], {}).get("x-reading-role")
        if role is None:
            continue
        direct = rec["direct"]
        headers = [i for i, child in enumerate(direct) if child == "header"]
        footers = [i for i, child in enumerate(direct) if child == "footer"]
        if len(headers) > 1 or len(footers) > 1:
            errors.append(found_at("pane-ends", rec, role=role))
        if headers and headers[0] != 0:
            errors.append(found_at("pane-header-first", rec, role=role))
        if footers and footers[0] != len(direct) - 1:
            errors.append(found_at("pane-footer-last", rec, role=role))
        body = [child for child in direct if child not in {"header", "footer"}]
        if len(body) != 1 or body[0] == "#text":
            errors.append(found_at("pane-body", rec, role=role, body=body))
    return errors


def parts_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """A page's parts (`x-views: "parts"`) written directly in `main` lay the page out
    themselves, each part's child carrying its own Layout, so the `main` holding them
    carries none. With one, its Layout and the parts' both arrange the page, and the
    page renders with nothing out of reach, so the render check passes it."""
    main = document.tree.select_one("body > main")
    classes = (main.attrs.get("class") or []) if main else []
    layouts = [token for token in classes if token.startswith("layout-")]
    if not layouts:
        return []
    return [
        found_at("parts-in-layout", rec, rec["attrs"].get("id", ""), layout=layouts[0])
        for rec in document.lf_elements
        if rec["parent"] == "main"
        and registry.get(rec["tag"], {}).get("x-views") == "parts"
    ]


def unasked(rec: dict, entry: dict) -> dict:
    """The `x-awaits.when` conditions a widget never met, as attribute and the values
    it would ask at, or none where it asks, was asked, or can be made to ask.

    The flag `x-awaits.retired` names is how an author ends an obligation already
    asked, such as a settled decision kept with its context, so failing on it alone
    leaves the widget counted. A condition a recorded value writes can still be met
    by a gesture."""
    awaits = entry["x-awaits"]
    when = awaits.get("when") or {}
    recorded = {
        (spec.get("record") or {}).get("attr")
        for spec in entry.get("x-state", {}).values()
        if (spec.get("record") or {}).get("kind") == "value"
    }
    return {
        attr: values
        for attr, values in when.items()
        if attr != awaits.get("retired")
        and attr not in recorded
        and not matches_when(rec["attrs"], {attr: values})
    }


def enclosing_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """An enclosing widget (`x-encloses`) supplies a leading title and
    arrival region for the obligations inside it.

    It never owns obligation identity or registration. Any number of sources can select
    it, and each source retains its independent answer and lifecycle. An enclosing
    widget whose widgets none ask shows a question the On me list never counts and
    the user can't answer, so the error names what each enclosed widget lacks to
    ask (`unasked`), or that it holds none.
    """

    lf_elements = document.lf_elements
    regions = [rec for rec in lf_elements if encloses(registry.get(rec["tag"], {}))]
    framed = {id(region): [] for region in regions}
    # A widget asks inside every frame around it, so a frame holding only a nested frame
    # is as full as that one; the nearest still gives the obligation its prompt. A
    # sample's widgets ask nothing beyond it (obligations.py, `shown_in`), so the walk
    # stops there and a frame inside the sample still counts them.
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        if not local_obligation_entry(entry):
            continue
        for holder in enclosing_widgets(rec):
            holder_entry = registry.get(holder["tag"], {})
            if holder_entry.get("x-exhibit"):
                break
            if encloses(holder_entry):
                framed[id(holder)].append((rec, unasked(rec, entry)))
    errors = []
    for region in regions:
        held = framed[id(region)]
        # The obligation's title is what the shared name rule reads, so this asks that rule
        # rather than restating a shape it accepts. It must be a heading as well, the
        # question's place in the outline and in heading navigation.
        node = document.authoring.node_of(region)
        assert node is not None
        title = leading_title_node(node)
        titled = bool(title) and title["tag"] in {f"h{n}" for n in range(1, 7)}
        if all(lacks for _, lacks in held):
            widgets = [
                {
                    "at": element_at(rec["tag"], rec["attrs"].get("id", "")),
                    "line": rec["line"],
                    "lacks": lacks,
                }
                for rec, lacks in framed[id(region)]
            ]
            errors.append(found_at("empty-question", region, widgets=widgets))
        if not titled:
            errors.append(found_at("untitled-question", region))
    return errors


def relation_mismatch(
    reference: dict, target_record: dict | None, registry: dict
) -> dict | None:
    """How one resolved target fails a package-declared relation, if it does: the
    relation, its predicate, and what the target declares of it."""
    via = reference.get("via")
    if via is None:
        return None
    relation = registry_path(registry, via)
    declaration = (
        relation.get(target_record["tag"])
        if isinstance(relation, dict) and target_record is not None
        else None
    )
    predicate = reference["where"]
    if isinstance(declaration, dict) and all(
        declaration.get(key) == value for key, value in predicate.items()
    ):
        return None
    return {
        "via": via,
        "where": predicate,
        "target_tag": target_record["tag"] if target_record is not None else None,
        "found": {key: declaration.get(key) for key in predicate}
        if isinstance(declaration, dict)
        else None,
    }


def enclosing(rec: dict, tag: str, registry: dict) -> dict | None:
    """The nearest member owner of `tag` within `rec`'s quotation, if any."""
    return next(
        (node for node in member_holders(rec, registry) if node["tag"] == tag), None
    )


def keyed_members(lf_elements: list, registry: dict) -> dict:
    """Every member a keyed reference may name, as `(id(owner), tag, key, value)` mapped
    to the members holding it, in document order; the owner is the member's nearest
    enclosing element of the tag its x-unique declaration names for that key. A member
    standing in no such owner is left out: x-owners reports where it stands."""
    members = {}
    for rec in lf_elements:
        for key, scope_tag in registry.get(rec["tag"], {}).get("x-unique", {}).items():
            value = rec["attrs"].get(key)
            scope = enclosing(rec, scope_tag, registry)
            if value is not None and scope is not None:
                members.setdefault((id(scope), rec["tag"], key, value), []).append(rec)
    return members


def unique_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """Each member whose x-unique attribute repeats an earlier member's value within
    their shared owner: two playground controls with one name, or two choices of one
    control with one value. Asked of one document, since an owner and its members
    always stand in the same one."""
    return [
        found_at(
            "repeated-key",
            extra,
            key=key,
            value=value,
            first_line=first["line"],
            scope=registry[tag]["x-unique"][key],
        )
        for (_, tag, key, value), (first, *extras) in keyed_members(
            lf_elements, registry
        ).items()
        for extra in extras
    ]


def reference_errors(
    lf_elements: list, registry: dict, ids: set, by_id: dict, *, thread_ids: set[str]
) -> list[Finding]:
    """Validate declared references against the supplied element and thread namespaces.

    A message widget may point into the page beside it, so its caller supplies the
    page's ids alongside the fragment's own.

    An `owns` reference is narrower, since its referrer fills the target and the
    browser looks for that target in the referrer's own document: each names an
    element of `lf_elements`' own document, and each element there that the
    contract's predicate selects is named by exactly one referrer, as each readings
    seat is filled by one command.

    A keyed reference names a member rather than an id: the `tag` member, inside the
    referrer's own nearest owner of the tag its `key` is unique within (x-unique),
    whose `key` attribute holds the value, as a playground preset's setting names a
    control of the same playground.

    The reserved `resolves` attribute names a thread in the document's history,
    rather than a markup id, on any widget that declares the capability."""
    errors = []
    own = {rec["attrs"].get("id") for rec in lf_elements}
    owners = {}
    keyed = None
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        resolves = rec["attrs"].get("resolves")
        if (
            "resolves" in entry.get("properties", {})
            and resolves
            and resolves not in thread_ids
        ):
            errors.append(
                found_at(
                    "unknown-thread", rec, rec["attrs"].get("id", ""), resolves=resolves
                )
            )
        for attr, reference in entry.get("x-refers", {}).items():
            target = rec["attrs"].get(attr)
            if not target:
                continue
            reference_to = {"attr": attr, "target": target}
            if member := reference.get("tag"):
                if keyed is None:
                    keyed = keyed_members(lf_elements, registry)
                key = reference["key"]
                scope_tag = registry[member]["x-unique"][key]
                scope = enclosing(rec, scope_tag, registry)
                if (id(scope), member, key, target) not in keyed:
                    errors.append(
                        found_at(
                            "unmatched-member",
                            rec,
                            **reference_to,
                            member=member,
                            key=key,
                            scope=scope_tag,
                        )
                    )
            elif target not in ids:
                errors.append(found_at("unknown-reference", rec, **reference_to))
            elif mismatch := relation_mismatch(reference, by_id.get(target), registry):
                errors.append(
                    found_at("reference-contract", rec, **reference_to, **mismatch)
                )
            elif reference.get("owns") and target not in own:
                errors.append(found_at("outside-reference", rec, **reference_to))
            elif attr == entry.get("x-shows", {}).get("attr") and target not in own:
                # A view and the answer it shows travel in one document, so a board
                # in a reply shows widgets frozen in the same reply (`shown_answers`).
                errors.append(found_at("shows-outside", rec, **reference_to))
            elif reference.get("owns"):
                owners.setdefault((rec["tag"], attr, target), []).append(rec)
        for input_name, spec in registry.get(rec["tag"], {}).get("x-data", {}).items():
            target = rec["attrs"].get(spec.get("reference"))
            producer = by_id.get(target)
            if not target or not producer:
                continue  # The ordinary relation check names a missing target.
            output = (
                registry.get(producer["tag"], {})
                .get("x-output", {})
                .get(spec["output"])
            )
            if output is None or output["contract"] != spec["contract"]:
                errors.append(
                    found_at(
                        "output-contract",
                        rec,
                        input=input_name,
                        target=target,
                        output=spec["output"],
                        contract=spec["contract"],
                    )
                )
    owned = [
        (tag, attr, reference)
        for tag, entry in registry.items()
        if is_element_name(tag)
        for attr, reference in entry.get("x-refers", {}).items()
        if reference.get("owns")
    ]
    for rec in lf_elements:
        for tag, attr, reference in owned:
            if relation_mismatch(reference, rec, registry):
                continue
            target = rec["attrs"].get("id")
            named = owners.get((tag, attr, target), [])
            if not named:
                errors.append(found_at("unowned", rec, referrer=tag, attr=attr))
            if len(named) > 1:
                first = named[0]
                errors.extend(
                    found_at(
                        "owned-twice",
                        extra,
                        attr=attr,
                        target=target,
                        first=element_at(first["tag"], first["attrs"].get("id", "")),
                        first_line=first["line"],
                    )
                    for extra in named[1:]
                )
    return errors


def addressable_instance_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """Conditional obligations and thread seats need an id when they are live.

    Requiring every instance globally would outlaw inert option groups; checking the
    declared predicate here gives the runtime exactly the addressability it consumes.
    """
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        for role in ("x-awaits", "x-thread-seat"):
            declaration = entry.get(role)
            if (
                declaration is not None
                and matches_when(rec["attrs"], declaration.get("when"))
                and not rec["attrs"].get("id")
            ):
                errors.append(found_at("needs-id", rec, role=role))
    return errors


def suggestion_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """What the registry's schema can't say about a suggestion: it holds at most
    one of each slot and at least one of them, and it doesn't nest. A family lint, named
    for its family — and it reads even its own slots out of the merged registry,
    so a layer that adds one to the family is linted for it rather than around it."""
    tags = {
        tag
        for slot_tags in retirement_slots(registry).get("lf-suggestion", {}).values()
        for tag in slot_tags
    }
    errors = []
    for rec in lf_elements:
        if rec["tag"] != "lf-suggestion":
            continue
        own = rec["attrs"].get("id", "")
        if any(w["tag"] == "lf-suggestion" for w in enclosing_widgets(rec)):
            errors.append(found_at("nested-suggestion", rec, own))
        carried = [tag for tag in rec["children"] if tag in tags]
        if not carried:
            errors.append(found_at("empty-suggestion", rec, own))
        for tag in sorted(tags):
            if carried.count(tag) > 1:
                errors.append(
                    found_at(
                        "repeated-slot", rec, own, slot=tag, count=carried.count(tag)
                    )
                )
    return errors


def instance_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """Every instance check that needs only the registry, no id namespace, so a new
    check of that kind reaches page source and message markup alike."""
    lf_elements = document.lf_elements
    return (
        widget_errors(lf_elements, registry)
        + layout_errors(lf_elements, registry)
        + parts_errors(document, registry)
        + addressable_instance_errors(lf_elements, registry)
        + enclosing_errors(document, registry)
        + unique_errors(lf_elements, registry)
        + shown_errors(document, registry)
    )


def fragment_errors(parser: SourceDocument, registry: dict) -> list[Finding]:
    """Structural + registry validation of an HTML fragment:
    the discussion-side analog of `page check`."""
    return structure_errors(parser) + instance_errors(parser, registry)
