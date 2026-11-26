"""Registry-declared markup instance validation."""

import re
from collections.abc import Callable, Iterable

import turbohtml

from leaf.base.findings import Finding, element_at
from leaf.base.schema import INPUT_BINDINGS
from leaf.log.projection import recorded_owner
from leaf.records.markup_checks.markup import (
    document_declaration_errors,
    found_at,
    id_errors,
    markup_advice,
    repair_errors,
    structure_errors,
)
from leaf.source.data_contracts import declared_data_bindings
from leaf.source.obligation_sources import group_tags, widget_groups
from leaf.source.passages import element_name
from leaf.source.registry.contract import (
    authored_inert,
    body_is_data,
    is_element_name,
    matches_when,
    retirement_slots,
    state_specs,
)
from leaf.source.registry.kernel import kernel_marks
from leaf.source.registry.schema import json_validator, schema_reading
from leaf.source.structure import (
    AUTHORED_ALLOCATIONS,
    SourceDocument,
    element_attrs,
    enclosing_widgets,
    layout_boxes,
    layout_names,
    shown_in,
)

# The `command` keywords HTML gives an element itself. Chromium, Firefox and WebKit
# reflect these and `--` names and nothing else (`button.command`), in any case.
_NATIVE_COMMANDS = frozenset(
    {
        "close",
        "hide-popover",
        "request-close",
        "show-modal",
        "show-popover",
        "toggle-popover",
    }
)

_GLOBAL_ATTRIBUTE = re.compile(r"class|style|title|lang|dir|aria-[a-z]+|data-(?!lf-).+")


def message_settlement_advice(parser, registry: dict) -> list[Finding]:
    """Each widget in a message's markup whose decision retires part of it, as a
    suggestion's does, which no version writes into the page (`message-settlement`)."""
    settled = retirement_slots(registry)
    return [
        found_at("message-settlement", rec)
        for rec in parser.lf_elements
        if rec["tag"] in settled
    ]


def widget_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """Validate parsed lf-* elements against the registry: schema over the
    attribute instance, `owners` nesting, and the content model."""
    errors = []
    # Member containers admit exactly the tags that declare them as `owners`.
    members_of = {}
    for tag, entry in registry.items():
        if not is_element_name(tag):
            continue
        for owner in entry.get("owners", []):
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
        attributes = entry["attributes"]
        props = attributes.get("properties", {})
        instance = {}
        for name, value in rec["attrs"].items():
            if name in AUTHORED_ALLOCATIONS or (
                name not in props and _GLOBAL_ATTRIBUTE.fullmatch(name)
            ):
                continue
            prop = props.get(name)
            is_flag = isinstance(prop, dict) and prop.get("type") == "boolean"
            instance[name] = True if value in (None, "") and is_flag else (value or "")
        for err in sorted(json_validator(attributes).iter_errors(instance), key=str):
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
        for input_name, spec in entry.get("inputs", {}).items():
            bound_by = [k for k in INPUT_BINDINGS if rec["attrs"].get(spec.get(k))]
            if len(bound_by) > 1:
                errors.append(found_at("ambiguous-data-binding", rec, input=input_name))
        # A member stands directly in an owner.
        want_owners = entry.get("owners", [])
        if want_owners and rec["parent"] not in want_owners:
            errors.append(
                found_at("not-member", rec, owners=want_owners, parent=rec["parent"])
            )
        # Tags that name this declaration in `owners` are its admissible members
        # under any content model. "data" and "markdown" take one <pre>. Where the
        # declaration has an input (`inputs`) whose property is `value`, the <pre> is
        # that input's text: the element holds none where its markup binds that input,
        # and one or none where it binds only others, since the declaration doesn't say
        # whether they supply the data in the <pre>'s place, as a diff's two compared
        # texts do. A widget without such an input reads its <pre> whatever it binds, as
        # a code block does beside its playhead. "members" takes element members only,
        # and "empty" takes nothing.
        content = entry["content"]
        allowed = members_of.get(tag, set())
        stray = sorted({c for c in rec["children"] if c not in allowed})
        specs = entry.get("inputs", {}).values()
        binds = [
            any(rec["attrs"].get(spec.get(key)) for key in INPUT_BINDINGS)
            for spec in specs
        ]
        texts = [spec.get("property") == "value" for spec in specs]
        bound = any(on and text for on, text in zip(binds, texts, strict=True))
        pres_taken = {0} if bound else {0, 1} if any(texts) and any(binds) else {1}
        if content == "empty" and (rec["children"] or rec["text"]):
            errors.append(found_at("content-empty", rec))
        elif body_is_data(entry):
            others = [c for c in stray if c != "pre"]
            pres = rec["children"].count("pre")
            if pres not in pres_taken or others:
                errors.append(
                    found_at("data-body", rec, children=rec["children"], bound=bound)
                )
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


def parts_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """A page's parts (`views.parts`) written directly in `main` lay the page out
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
        and registry.get(rec["tag"], {}).get("views", {}).get("parts")
    ]


def question_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """Each widget a page asks with has a question to show on On Me: the label of the
    named group round it (`obligation_sources.widget_groups`), else the widget's own
    `label` (`passages.element_name`), the words On Me lists and the agent hears. Leaf
    reads both from the author's markup and infers neither. A question with no words,
    as where neither the widget nor a group round it has a label that isn't blank, is
    refused (`unnamed-question`). Where the widget's own label alone names it, On Me
    selects and rings only the widget, so a premise written outside the widget is out
    of view (`ungrouped-question`, advice). A widget set among words (`inline`) is
    named by them, so it needs no group. A message's widget needs none either, since
    the message names what it asks, so only a page's documents are checked."""
    # A widget inside SVG keeps its exact source rather than a node, and so is no
    # widget the walk reads.
    groups = {
        id(node): (node, group)
        for node, group in widget_groups(document.authoring.content, registry)
    }
    errors = []
    for rec in document.lf_elements:
        entry = registry.get(rec["tag"]) or {}
        awaits = entry.get("awaits")
        if (
            awaits is None
            or entry.get("inline")
            or not matches_when(rec["attrs"], awaits.get("when"))
            or shown_in(rec, registry)
            or (walked := groups.get(id(document.authoring.node_of(rec)))) is None
        ):
            continue
        node, group = walked
        values = {"line": rec["line"], "groups": group_tags(registry)}
        if not element_name(group or node, registry):
            code = "unnamed-question"
            if group is not None:
                values["group"] = element_at(group["tag"], group["attrs"].get("id", ""))
        elif group is None:
            code = "ungrouped-question"
        else:
            continue
        errors.append(
            Finding(code, element_at(rec["tag"], rec["attrs"].get("id", "")), values)
        )
    return errors


def reference_errors(
    lf_elements: list, registry: dict, ids: set, by_id: dict, *, thread_ids: set[str]
) -> list[Finding]:
    """Validate declared references against the supplied element and thread namespaces.

    A message widget may point into the page beside it, so its caller supplies the
    page's ids alongside the fragment's own.

    A worker's assignment, the attribute its `$work.widgets` entry names in `on`,
    names an element whose tag has the role goal there, since the work reading
    (`runtime/host/work.js`) assigns the worker to nothing else.

    The reserved `resolves` attribute names a thread in the document's history,
    rather than a markup id, on any widget that declares the capability."""
    errors = []
    work = registry.get("$work", {}).get("widgets", {})
    for rec in lf_elements:
        # An undeclared tag is `widget_errors`' to report.
        if (entry := registry.get(rec["tag"])) is None:
            continue
        resolves = rec["attrs"].get("resolves")
        if (
            "resolves" in entry["attributes"].get("properties", {})
            and resolves
            and resolves not in thread_ids
        ):
            errors.append(
                found_at(
                    "unknown-thread", rec, rec["attrs"].get("id", ""), resolves=resolves
                )
            )
        for attr in entry.get("refers", {}):
            target = rec["attrs"].get(attr)
            if not target:
                continue
            reference_to = {"attr": attr, "target": target}
            if target not in ids:
                errors.append(found_at("unknown-reference", rec, **reference_to))
            elif (
                attr == work.get(rec["tag"], {}).get("on")
                and work.get(tag := by_id.get(target, {}).get("tag"), {}).get("role")
                != "goal"
            ):
                errors.append(
                    found_at("work-assignment", rec, **reference_to, target_tag=tag)
                )
        for input_name, spec in registry.get(rec["tag"], {}).get("inputs", {}).items():
            target = rec["attrs"].get(spec.get("reference"))
            if not target or target not in ids:
                continue  # The ordinary relation check names a missing target.
            producer = registry.get(by_id.get(target, {}).get("tag"), {})
            matching = [
                name
                for name, output in producer.get("outputs", {}).items()
                if output["contract"] == spec["contract"]
            ]
            if len(matching) != 1:
                errors.append(
                    found_at(
                        "output-contract",
                        rec,
                        input=input_name,
                        target=target,
                        outputs=matching,
                        contract=spec["contract"],
                    )
                )
    return errors


def invoker_errors(parser: SourceDocument, ids: set) -> list[Finding]:
    """Each authored `commandfor` the browser would leave doing nothing, with no error:
    one naming no element, or whose `command` is neither one of HTML's own nor a custom
    one, which starts with `--`. `ids` is the namespace `reference_errors` reads for
    the same document. Whether the target handles a custom command is its module's to
    say, in its description; no declaration lists them.

    The browser finds a `commandfor` target in the button's own tree, the first element
    with that id in tree order, where a `refers` reader looks in its message first and
    then the page (`runtime/readings/references.js`). A message stands in the page's tree, so a
    button in one reaches the page's widgets, and the two readings agree on every id the
    checks admit, since `ids-taken` and `ids-taken-by-messages` keep an id to one element
    across the page and its messages. A live sample's document is its own tree, checked
    here on its own ids."""
    errors = []
    for rec in parser.authoring.invokers:
        target, command = rec["target"], rec["command"]
        if target not in ids:
            errors.append(
                found_at("unknown-reference", rec, attr="commandfor", target=target)
            )
        elif not command.startswith("--") and command.lower() not in _NATIVE_COMMANDS:
            errors.append(found_at("unknown-command", rec, command=command))
    return errors


def addressable_instance_errors(lf_elements: list, registry: dict) -> list[Finding]:
    """A conditional obligation needs an id when it is live.

    A widget whose schema leaves `id` optional may stand without one while its
    predicate fails; checking the declared predicate here gives the runtime exactly
    the addressability it consumes.
    """
    errors = []
    for rec in lf_elements:
        declaration = registry.get(rec["tag"], {}).get("awaits")
        if (
            declaration is not None
            and matches_when(rec["attrs"], declaration.get("when"))
            and not rec["attrs"].get("id")
        ):
            errors.append(found_at("needs-id", rec, role="awaits"))
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


def pane_advice(document: SourceDocument, registry: dict) -> list[Finding]:
    """Each pane (`reading-role: pane`) whose direct children aren't an optional header,
    one body element and an optional footer, in that order, with what its grid does with
    them (`base.css`, "A pane is one task region"). Advice, since a pane holding a
    `<script>`, or blocks a script shows one at a time, works as it is."""
    findings = []
    for rec in document.lf_elements:
        role = registry.get(rec["tag"], {}).get("reading-role")
        if role != "pane":
            continue
        direct = rec["direct"]
        headers = [i for i, child in enumerate(direct) if child == "header"]
        footers = [i for i, child in enumerate(direct) if child == "footer"]
        if len(headers) > 1 or len(footers) > 1:
            findings.append(found_at("pane-ends", rec, role=role))
        if headers and headers[0] != 0:
            findings.append(found_at("pane-header-first", rec, role=role))
        if footers and footers[0] != len(direct) - 1:
            findings.append(found_at("pane-footer-last", rec, role=role))
        body = [child for child in direct if child not in {"header", "footer"}]
        if len(body) > 1 or body == ["#text"]:
            findings.append(found_at("pane-body", rec, role=role, body=body))
    return findings


def _takes_room(element) -> bool:
    """Whether `element` takes room in its parent's flow by HTML's own rules: not a
    script, a style or a template, which draw nothing; not a dialog or a popover, which
    stand above the page or nowhere; and not an element hidden other than until found,
    which keeps its box."""
    attrs = element_attrs(element)
    hidden = "hidden" in attrs and attrs["hidden"] != "until-found"
    return (
        element.tag not in {"script", "style", "template", "dialog"}
        and "popover" not in attrs
        and not hidden
    )


def workspace_advice(document: SourceDocument, registry: dict) -> list[Finding]:
    """Each workspace (`layout-workspace`) holding more than one body that takes room
    beside its header and footer. While it fills the window, its header and footer take
    their own height and its bodies share the rest evenly (layouts.css), so a block
    written beside the regions, such as a list of what waits on the user, takes half the
    window from them and leaves blank space under its own lines. Nothing is out of
    reach, so the render check passes it. Advice, since the page works as written."""
    findings = []
    for box in layout_boxes(document, registry):
        if "workspace" not in layout_names(box):
            continue
        bodies = [
            element_at(child.tag, element_attrs(child).get("id", ""))
            for child in box.children
            if isinstance(child, turbohtml.Element)
            and child.tag not in {"header", "footer"}
            and _takes_room(child)
        ]
        if len(bodies) > 1:
            findings.append(
                Finding(
                    "workspace-bodies",
                    element_at(box.tag, element_attrs(box).get("id", "")),
                    {"line": SourceDocument._position(box)[0], "bodies": bodies},
                )
            )
    return findings


def inert_allocation_advice(document: SourceDocument, registry: dict) -> list[Finding]:
    """A page's allocations that mean nothing where they stand
    (`registry.contract.authored_inert`), which delivery leaves unpainted, so nothing on
    the page shows the author the width or height they asked for is missing. Advice,
    since the page works as it is; the words say where the allocation would hold. A
    message has its own rule for the room (`$marks`, `message`), so this reads only
    a page's documents."""
    marks = {
        mark["authored"]: key
        for key, mark in kernel_marks().items()
        if "authored" in mark
    }
    findings = []
    for item in document.authoring.authored_allocations:
        key = marks.get(item["attr"])
        if key is None or item["in_template"]:
            continue
        tag = item["tag"]
        declaration = registry.get(tag, {}) if is_element_name(tag) else {}
        if holds := authored_inert(
            key, declaration, item["attrs"], content=item["content"]
        ):
            findings.append(
                Finding(
                    "inert-allocation",
                    element_at(tag, item["id"]),
                    {
                        "line": item["line"],
                        "attr": item["attr"],
                        "value": item["value"],
                        "holds": holds,
                    },
                )
            )
    return findings


def unnamed_card_advice(document: SourceDocument, registry: dict) -> list[Finding]:
    """Each widget that takes its name in `label` but has none, and holds a <strong>
    before any words of its own, whatever elements come first. The <strong> is a title
    only the page shows, so Leaf names the widget by all its words, and an option draws
    as a bare label of bold words. Advice, since bold words may open a label's own
    words."""
    findings = []
    for rec in document.lf_elements:
        properties = (registry.get(rec["tag"]) or {}).get("attributes", {})
        if "label" not in properties.get("properties", {}) or "label" in rec["attrs"]:
            continue
        node = document.authoring.node_of(rec)
        for child in node["content"] if node else ():
            if isinstance(child, str):
                if child.strip():
                    break
                continue
            if child["tag"] == "strong":
                findings.append(
                    Finding(
                        "unnamed-card",
                        element_at(rec["tag"], rec["attrs"].get("id", "")),
                        {"line": rec["line"]},
                    )
                )
                break
    return findings


def instance_errors(document: SourceDocument, registry: dict) -> list[Finding]:
    """Every instance check that needs only the registry, no id namespace, what it
    refuses and what it advises, so a new check of that kind reaches page source and
    message markup alike."""
    lf_elements = document.lf_elements
    return (
        widget_errors(lf_elements, registry)
        + parts_errors(document, registry)
        + addressable_instance_errors(lf_elements, registry)
        + declared_data_bindings(lf_elements, registry)[1]
        + pane_advice(document, registry)
        + workspace_advice(document, registry)
        + unnamed_card_advice(document, registry)
    )


def markup_findings(
    document: SourceDocument,
    registry: dict | None,
    own: Callable[[], Iterable[Finding]] = tuple,
) -> list[Finding]:
    """What every gate finds in one authored document, a page's source, a sample's
    child, a message's HTML or a registry example alike, reading only its markup and
    the registry it is checked under (None where none composes): what refuses it and
    what it advises, so a new check of that kind reaches each. `own` gives the gate's
    own checks of the document, such as its id namespace and the references into it.

    A document the HTML parser had to repair gets only the parser's findings, and
    neither these checks nor the gate's run, since each would read the repaired tree:
    a `<pre>` that closes the paragraph Markdown drew around a one-line `<lf-code>`
    leaves that widget with no body. The sheets delivery rewrites are read once for a
    document and its samples (`revision_artifact.document_drops`), so they are each
    gate's whole document's to read."""
    structural = structure_errors(document)
    if repair_errors(document):
        return structural
    return [
        *structural,
        *document_declaration_errors(document),
        *id_errors(document),
        *(instance_errors(document, registry) if registry is not None else ()),
        *markup_advice(document),
        *own(),
    ]
