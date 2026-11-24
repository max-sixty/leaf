"""How a verb's recorded effect and fold unit are declared and admitted, and how member
records compose without claiming each other's state."""

import json
from copy import deepcopy

import model_folds as model
import pytest
from interact_support import (
    ModelPage,
    check_findings,
    element_declaration,
    found,
    model_layer,
    refused_on,
    with_modules,
)

from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf.registry import contract as registry_contract
from leaf.registry import layer as registry_layer
from leaf.registry import validation as registry_validation
from leaf.validation import composition as composition_model
from model.interact_contract import (
    _stateful_page_declaration,
    _value_verb,
    declare_vocabulary,
    vocabulary,
)


def test_unrecorded_fold_units_are_required_strings(page_dir):
    registry = vocabulary(page_dir)
    add = registry["lf-options"]["verbs"]["add"]
    add.pop("creates")
    add["detail"]["properties"]["option"] = {"type": "integer"}
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, "unit-type", "<lf-options>", verb="add", unit="option")


@pytest.mark.parametrize(
    ("tag", "verb", "unit"),
    [
        ("lf-options", "choose", "unit"),
        ("lf-draft", "edit", "unit"),
        ("lf-test-task", "status", "unit"),
        ("lf-board", "move", "widget"),
    ],
)
def test_recorded_effects_fix_their_fold_unit(page_dir, tag, verb, unit):
    registry = vocabulary(page_dir)
    spec = registry[tag]["verbs"][verb]
    spec["unit"] = unit
    registry[tag]["attributes"]["properties"]["restated"] = {"type": "boolean"}
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    required = "unit" if spec["record"]["kind"] == "position" else "widget"
    assert found(
        findings,
        "record-unit",
        f"<{tag}>",
        verb=verb,
        kind=spec["record"]["kind"],
        unit=required,
    ), findings


def test_recorded_effect_payloads_are_validated_at_admission(page_dir):
    """Each effect admits its fixed fields and refuses aliases, extras and wrong types."""
    registry = vocabulary(page_dir)
    source = (
        '<lf-options id="picks"><lf-option id="first">First</lf-option></lf-options>'
        '<lf-draft id="draft"><pre>Initial words</pre></lf-draft>'
        '<lf-board id="board"><lf-column id="todo" label="Todo">'
        '<lf-card id="card">Card</lf-card></lf-column>'
        '<lf-column id="done" label="Done"></lf-column></lf-board>'
    )
    page = ModelPage(source, registry=registry)
    for widget, action, valid, invalid in (
        (
            "picks",
            "choose",
            {"value": ["first"]},
            (
                {},
                {"options": ["first"]},
                {"value": "first"},
                {"value": [1]},
                {"value": ["first"], "animate": True},
                {"value": ["missing"]},
            ),
        ),
        (
            "draft",
            "edit",
            {"value": "New words"},
            (
                {},
                {"text": "New words"},
                {"value": 1},
                {"value": "New words", "text": "news"},
            ),
        ),
        (
            "board",
            "move",
            {"unit": "card", "value": "done", "rank": "0i"},
            (
                {"unit": "card", "value": "done"},
                {"card": "card", "to": "done", "rank": "0i"},
                {"unit": 1, "value": "done", "rank": "0i"},
                {"unit": "card", "value": 1, "rank": "0i"},
                {"unit": "card", "value": "done", "rank": 1},
                {"unit": "card", "value": "done", "rank": "!"},
                {"unit": "missing", "value": "done", "rank": "0i"},
                {"unit": "card", "value": "missing", "rank": "0i"},
            ),
        ),
    ):
        command = {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": widget,
            "action": action,
        }
        admitted = event_contracts_model.admitted_event(
            page, [], {**command, "detail": valid}
        )
        for required in ("widget", "action", "detail", "revision"):
            malformed = {**command, "detail": valid}
            del malformed[required]
            with pytest.raises(events_model.EventRefused) as refused:
                event_contracts_model.admitted_event(page, [], malformed)
            assert refused_on(refused.value).values["rule"] == "required"
        assert admitted["detail"] == valid
        assert admitted["meaning"]["unit"] == (
            valid["unit"] if widget == "board" else widget
        )
        for detail in invalid:
            with pytest.raises(events_model.EventRefused):
                event_contracts_model.admitted_event(
                    page, [], {**command, "detail": detail}
                )


@pytest.mark.parametrize("writer", ["user", "agent"])
def test_attribute_records_admit_only_sets_of_owned_members(page_dir, writer):
    """Both writers may clear or select authored/generated members, once each."""
    registry = vocabulary(page_dir)
    options = registry["lf-options"]
    if writer == "agent":
        options.pop("awaits")
        options["verbs"]["choose"]["writer"] = "agent"
    registry_validation.validate_registry(registry, "test registry")
    page = ModelPage(
        '<lf-options id="owned" multiple>'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options>'
        '<lf-options id="elsewhere">'
        '<lf-option id="foreign">Foreign</lf-option></lf-options>',
        registry=registry,
    )
    added = event_contracts_model.admitted_event(
        page,
        [],
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "owned",
            "action": "add",
            "detail": {"option": "generated", "text": "Another route"},
        },
    )
    log = [{**added, "seq": 1, "ts": "2026-10-06T12:00:00+00:00"}]
    command = {
        "kind": "action" if writer == "user" else "report",
        "author": writer,
        "revision": 1,
        "widget": "owned",
        "action": "choose",
    }
    for value in ([], ["first"], ["first", "second"], ["generated"]):
        admitted = event_contracts_model.admitted_event(
            page, log, {**command, "detail": {"value": value}}
        )
        assert admitted["detail"] == {"value": value}
        assert set(admitted["meaning"]["depends"]) == {"owned", *value}
    for value in (["foreign"], ["missing"], ["first", "foreign"], ["first", "first"]):
        with pytest.raises(events_model.EventRefused):
            event_contracts_model.admitted_event(
                page, log, {**command, "detail": {"value": value}}
            )


def test_scalar_record_admission_inherits_the_destination_schema(page_dir):
    """A destination constraint is also the event constraint, without a second declaration."""
    registry = vocabulary(page_dir)
    declaration = _stateful_page_declaration(page_dir)
    declaration["attributes"]["properties"]["value"] = {
        "type": "string",
        "enum": ["next", "forbidden"],
        "maxLength": 4,
    }
    with_modules(registry, "lf-local")["lf-local"] = declaration
    registry_validation.validate_registry(registry, "test registry")
    page = ModelPage(
        '<lf-local id="local" value="next">Local</lf-local>', registry=registry
    )
    command = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "local",
        "action": "first",
    }
    admitted = event_contracts_model.admitted_event(
        page, [], {**command, "detail": {"value": "next"}}
    )
    assert admitted["detail"] == {"value": "next"}
    for value in ("forbidden", "other", 1):
        with pytest.raises(events_model.EventRefused):
            event_contracts_model.admitted_event(
                page, [], {**command, "detail": {"value": value}}
            )


@pytest.mark.parametrize(
    "mutation", ["detail", "record-value", "record-rank", "text-field"]
)
def test_recorded_declarations_cannot_override_the_fixed_payload(page_dir, mutation):
    registry = vocabulary(page_dir)
    spec = registry["lf-board"]["verbs"]["move"]
    if mutation == "detail":
        spec["detail"] = {"type": "object", "additionalProperties": False}
    elif mutation == "text-field":
        registry["lf-test-worker"]["verbs"]["state"]["text"] = "doing"
    else:
        spec["record"][mutation.removeprefix("record-")] = "custom"
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, "invalid-declaration"), findings


def test_value_records_use_the_string_type_html_attributes_carry(page_dir):
    registry = vocabulary(page_dir)
    registry["lf-test-worker"]["attributes"]["properties"]["state"] = {
        "type": "integer",
        "minimum": 0,
    }
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, "record-type", "<lf-test-worker>", attr="state")


@pytest.mark.parametrize(
    "binding",
    [{"property": "value"}, {"property": "currentValue", "event": "sl-change"}],
)
def test_a_value_record_may_name_the_property_and_event_the_element_holds_it_by(
    page_dir, binding
):
    """The names bind the element in the browser alone: an action admitted under
    them records the operation of the record without them, so naming another property
    or event later keeps every decision made before."""
    registry = vocabulary(page_dir)
    declaration = _stateful_page_declaration(page_dir)
    unbound = registry_contract.state_definition(
        "lf-local", declaration, declaration["verbs"]["first"]
    )
    declaration["verbs"]["first"]["record"].update(binding)
    with_modules(registry, "lf-local")["lf-local"] = declaration
    registry_validation.validate_registry(registry, "test registry")
    page = ModelPage('<lf-local id="local">Local</lf-local>', registry=registry)
    admitted = event_contracts_model.admitted_event(
        page,
        [],
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "local",
            "action": "first",
            "detail": {"value": "next"},
        },
    )
    assert admitted["meaning"]["state"] == unbound
    assert unbound["record"] == {"kind": "value", "attr": "value"}


@pytest.mark.parametrize(
    "record",
    [
        # An event with no property to read on it.
        {"kind": "value", "attr": "value", "event": "change"},
        # A property is a script's name for it, never an attribute's.
        {"kind": "value", "attr": "value", "property": "aria-valuenow"},
        # Only a value record is one scalar an element's property can hold.
        {"kind": "body", "property": "value"},
    ],
)
def test_only_a_value_record_names_a_property_and_an_event_needs_one(page_dir, record):
    registry = vocabulary(page_dir)
    declaration = _stateful_page_declaration(page_dir)
    declaration["verbs"]["first"]["record"] = record
    with_modules(registry, "lf-local")["lf-local"] = declaration
    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_validation.validate_registry(registry, "test registry")
    assert refused.value.findings[0].code == "invalid-declaration"


def test_report_text_is_required_only_when_declared(page_dir):
    """`text: true` requires non-empty text; reports without it carry just their value."""
    registry = vocabulary(page_dir)
    page = ModelPage(
        '<lf-test-worker id="agent" state="working">Agent</lf-test-worker>',
        registry=registry,
    )
    command = {
        "kind": "report",
        "author": "agent",
        "revision": 1,
        "widget": "agent",
        "action": "state",
    }
    detail = {"value": "waiting", "text": "Ready for review."}
    admitted = event_contracts_model.admitted_event(
        page, [], {**command, "detail": detail}
    )
    assert admitted["detail"] == detail
    for invalid in (
        {"value": "waiting"},
        {"value": "waiting", "text": ""},
        {"value": "waiting", "text": None},
    ):
        with pytest.raises(events_model.EventRefused):
            event_contracts_model.admitted_event(
                page, [], {**command, "detail": invalid}
            )
    with pytest.raises(events_model.EventRefused):
        event_contracts_model.admitted_event(
            page, [], {**command, "kind": "action", "author": "user", "detail": detail}
        )

    del registry["lf-test-worker"]["verbs"]["state"]["text"]
    page = ModelPage(
        '<lf-test-worker id="agent" state="working">Agent</lf-test-worker>',
        registry=registry,
    )
    admitted = event_contracts_model.admitted_event(
        page, [], {**command, "detail": {"value": "waiting"}}
    )
    assert admitted["detail"] == {"value": "waiting"}
    with pytest.raises(events_model.EventRefused):
        event_contracts_model.admitted_event(page, [], {**command, "detail": detail})


@pytest.mark.parametrize(
    ("tag", "verb", "field"),
    [
        ("lf-suggestion", "decide", "unit"),
        ("lf-test-task", "status", "unit"),
    ],
)
def test_every_fold_verb_declares_its_coordinate(page_dir, tag, verb, field):
    registry = vocabulary(page_dir)
    del registry[tag]["verbs"][verb][field]
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    [refused] = found(findings, "invalid-declaration", f"<{tag}>", keyword="required")
    assert field in refused.values["reason"]


@pytest.mark.parametrize(
    ("tag", "verb", "kind", "attr"),
    [
        ("lf-draft", "edit", "body", None),
        ("lf-board", "move", "position", None),
        ("lf-test-task", "status", "value", "status"),
        ("lf-options", "choose", "attribute", "selected"),
    ],
)
def test_distinct_verbs_cannot_claim_one_physical_record_slot(
    page_dir, tag, verb, kind, attr
):
    registry = vocabulary(page_dir)
    declared = registry[tag]["verbs"][verb]
    parallel = json.loads(json.dumps(declared))
    registry[tag]["verbs"]["parallel"] = parallel
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(
        findings,
        "shared-slot",
        f"<{tag}>",
        verbs=["parallel", verb],
        unit=parallel["unit"],
        kind=kind,
        attr=attr,
    ), findings


def test_a_position_record_places_a_part_and_never_the_widget(page_dir):
    """A rank lies between the unit's neighbours, which only the widget holding the
    container can read, so a widget cannot record its own position."""
    registry = vocabulary(page_dir)
    registry["lf-options"]["verbs"]["move"] = {
        "unit": "widget",
        "record": {"kind": "position", "within": "lf-column"},
    }
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(
        findings,
        "record-unit",
        "<lf-options>",
        verb="move",
        kind="position",
        unit="unit",
    )


def test_a_position_record_s_container_stands_inside_the_widget(page_dir):
    """The browser finds a position's containers among the widget's descendants, so a
    record naming the widget's own tag as its container passes nothing a drop can
    find, and the check refuses it before a drop throws."""
    registry = vocabulary(page_dir)
    registry["lf-board"]["verbs"]["move"]["record"]["within"] = "lf-board"
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(
        findings, "record-within", "<lf-board>", verb="move", within="lf-board"
    )


@pytest.mark.parametrize(
    ("within", "containers"),
    [
        # A holder the board's structure never reaches: <lf-options> sits only in
        # a card's markup, if anywhere, so the board's own drops all fail.
        ("lf-options", ["lf-column"]),
        # The moved units' tag, which holds no members.
        ("lf-card", ["lf-column"]),
    ],
)
def test_a_position_container_the_declarations_never_place_is_advice(
    within, containers
):
    """A `within` that no declared membership places inside the widget leaves every
    drop the widget's own structure offers refused at admission, where nothing tells
    the agent. Another package could still declare the membership, so the registry
    advises, naming the containers the declarations do place there."""
    registry = deepcopy(model_layer())
    assert composition_model.declaration_advice(registry, registry, "test") == []

    registry["lf-board"]["verbs"]["move"]["record"]["within"] = within
    registry_validation.validate_registry(registry, "test registry")
    said = composition_model.declaration_advice(
        {"lf-board": registry["lf-board"]}, registry, "test"
    )
    assert [(f.code, f.at, f.severity, f.values) for f in said] == [
        (
            "position-container",
            "<lf-board>",
            "advice",
            {
                "verb": "move",
                "within": within,
                "containers": containers,
                "registry": "test",
            },
        )
    ]


def _independent_member_records():
    """An unfamiliar package composes selection, positions and scalar member state."""
    registry = deepcopy(model_layer())
    for tag in ("lf-audit-board", "lf-audit-zone", "lf-audit-card"):
        with_modules(registry, tag)[tag] = element_declaration(tag, upgrade=True)
        registry[tag]["attributes"]["properties"]["restated"] = {"type": "boolean"}
        registry[tag].pop("example", None)
    board, zone, card = (
        registry[tag] for tag in ("lf-audit-board", "lf-audit-zone", "lf-audit-card")
    )
    board["content"] = "members"
    board["verbs"] = {
        "move": {
            "unit": "unit",
            "record": {"kind": "position", "within": "lf-audit-zone"},
        }
    }
    zone["owners"] = ["lf-audit-board"]
    zone["content"] = "members"
    zone["verbs"] = {
        "choose": {
            "unit": "widget",
            "record": {"kind": "attribute", "attr": "selected"},
        },
    }
    card["owners"] = ["lf-audit-zone"]
    card["attributes"]["properties"].update(
        selected={"type": "boolean"}, phase={"type": "string"}
    )
    card["verbs"] = {
        "phase": {"unit": "widget", "record": {"kind": "value", "attr": "phase"}}
    }
    registry_layer.stamp_composition(
        registry_validation.validate_registry(registry, "independent member records")
    )
    markup = """<lf-audit-board id="outer">
<lf-audit-zone id="one"><lf-audit-card id="card" selected phase="idle">
<lf-audit-board id="inner"><lf-audit-zone id="inner-zone">
<lf-audit-card id="inner-card" selected phase="idle">Inner</lf-audit-card>
</lf-audit-zone></lf-audit-board></lf-audit-card></lf-audit-zone>
<lf-audit-zone id="two"></lf-audit-zone></lf-audit-board>"""
    return ModelPage(markup, registry=registry)


def test_member_records_compose_without_claiming_each_others_state(tmp_path):
    from leaf.construction import constructed_content
    from leaf.projection import page_reading, retirement_outcomes

    page = _independent_member_records()
    reading = page.reading(1, page.registry(1))
    commands = [
        {
            "kind": "action",
            "widget": "one",
            "action": "choose",
            "detail": {"value": ["card"]},
        },
        {
            "kind": "action",
            "widget": "card",
            "action": "phase",
            "detail": {"value": "running"},
        },
        {
            "kind": "action",
            "widget": "outer",
            "action": "move",
            "detail": {"unit": "card", "value": "two", "rank": "1"},
        },
    ]

    def card_attributes(commands):
        events = model.served_reading(
            reading.document.html, commands, registry=reading.registry
        )["events"]
        projection = page_reading(reading, events, 1).projection
        pending = constructed_content(
            reading.document,
            projection,
            reading.spoken,
            reading.registry,
            {"sources": {}},
            tmp_path,
            outcomes=retirement_outcomes(projection.actions),
            retired=set(),
            thread="thread",
        )
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if node["attrs"].get("id") == "card":
                    return node["attrs"]
                pending.extend(node["content"])
        pytest.fail("The moved card disappeared")

    # The destination's unchanged empty selection clears the incoming member;
    # its unrelated scalar state survives both moving and undoing the move.
    assert card_attributes(commands) == {"id": "card", "phase": "running"}
    assert card_attributes([*commands, {"kind": "undo", "undoes": "e3"}]) == {
        "id": "card",
        "selected": "",
        "phase": "running",
    }
    with pytest.raises(events_model.EventRefused) as refused:
        card_attributes(
            [
                *commands,
                {
                    "kind": "action",
                    "widget": "one",
                    "action": "choose",
                    "detail": {"value": ["card"]},
                },
            ]
        )
    assert refused_on(refused.value).code == "unknown-members"


def test_nested_member_records_refuse_foreign_selection_and_position():
    page = _independent_member_records()
    for widget, action, detail in (
        ("one", "choose", {"value": ["inner-card"]}),
        ("outer", "move", {"unit": "inner-card", "value": "two", "rank": "1"}),
        ("outer", "move", {"unit": "card", "value": "inner-zone", "rank": "1"}),
    ):
        with pytest.raises(events_model.EventRefused):
            event_contracts_model.admitted_event(
                page,
                [],
                {
                    "kind": "action",
                    "author": "user",
                    "revision": 1,
                    "widget": widget,
                    "action": action,
                    "detail": detail,
                },
            )


def test_member_scalar_and_parent_selection_cannot_share_an_attribute():
    from leaf.validation.instances import widget_errors

    page = _independent_member_records()
    registry = page.registry(1)
    registry["lf-audit-zone"]["verbs"]["choose"]["record"]["attr"] = "phase"
    registry_validation.validate_registry(registry, "reusable record declarations")
    reading = page.reading(1, registry)
    findings = widget_errors(reading.document.lf_elements, registry)
    assert {finding.code for finding in findings} == {"member-record-slot"}

    # These declarations are valid until a move changes their actual composition.
    zone = registry["lf-audit-zone"]
    zone.pop("verbs")
    zone["owners"] = ["lf-audit-left", "lf-audit-right"]
    for tag, attr in (("lf-audit-left", "selected"), ("lf-audit-right", "phase")):
        holder = element_declaration(tag, upgrade=True)
        holder["content"] = "members"
        holder["owners"] = ["lf-audit-board"]
        holder["attributes"]["properties"]["restated"] = {"type": "boolean"}
        holder["verbs"] = {
            "choose": {"unit": "widget", "record": {"kind": "attribute", "attr": attr}}
        }
        with_modules(registry, tag)[tag] = holder
    registry_layer.stamp_composition(
        registry_validation.validate_registry(registry, "movable record compositions")
    )
    page = ModelPage(
        '<lf-audit-board id="board"><lf-audit-left id="left">'
        '<lf-audit-zone id="one"><lf-audit-card id="card" phase="idle">Card</lf-audit-card>'
        '</lf-audit-zone></lf-audit-left><lf-audit-right id="right">'
        '<lf-audit-zone id="two"></lf-audit-zone></lf-audit-right></lf-audit-board>',
        registry=registry,
    )
    assert widget_errors(page.document(1).lf_elements, registry) == []
    with pytest.raises(events_model.EventRefused) as refused:
        model.reading(
            page.document(1).html,
            [
                {
                    "kind": "action",
                    "widget": "board",
                    "action": "move",
                    "detail": {"unit": "card", "value": "two", "rank": "1"},
                }
            ],
            registry=registry,
        )
    finding = refused_on(refused.value)
    assert finding.code == "member-record-slot"
    assert finding.values["owner"] == "right"


def test_creates_targets_are_members_while_authored_widgets_keep_owner_capabilities():
    registry = deepcopy(model_layer())
    child = registry["lf-option"]
    child.update(
        {
            "shadow": True,
            "visual": "whole",
        }
    )
    with_modules(registry, "lf-option")
    registry_validation.validate_registry(registry, "presentation members")
    child["attributes"]["properties"].update(
        phase={"type": "string"}, restated={"type": "boolean"}
    )
    child["verbs"] = {"phase": _value_verb("phase")}
    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_validation.validate_registry(registry, "independent created owner")
    assert refused.value.findings[0].code == "creates-semantic-owner"

    del registry["lf-options"]["verbs"]["add"]
    registry_validation.validate_registry(registry, "independent authored owner")
