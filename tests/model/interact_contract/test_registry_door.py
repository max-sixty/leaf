"""What registry validation refuses in a widget declaration: detail schemas, extensions,
formats, patterns, rendering owners, obligations, retirement and references."""

import json

import pytest
from interact_support import (
    _agent_verb_answers,
    _body_record_with_nested_widget,
    _body_record_with_prose,
    _mutated_registry_check,
    _report_authored_detail,
    _report_body_record,
    _report_no_record,
    _report_position_record,
    _report_says_attr,
    _report_undeclared_attr,
    _report_without_overruled,
    _report_without_upgrade,
    _user_verb_text,
    check,
    check_findings,
    found,
    queue_board_registry,
    registry_refusal,
)

from leaf.registry import contract as registry_contract
from leaf.registry import schema as registry_schema
from leaf.registry import validation as registry_validation


@pytest.mark.parametrize("content", ["markup", "data"])
def test_patchable_children_can_be_native_markup_but_not_data(page_dir, content):
    """Revision patching owns authored child trees, not a renderer's parsed input."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-tabs"]["x-content"] = content
    if content == "markup":
        registry_validation.validate_registry(registry, "test registry")
    else:
        finding = registry_refusal(
            lambda: registry_validation.validate_registry(registry, "test registry")
        )
        assert found([finding], "invalid-extensions", "<lf-tabs>", keyword="enum")


def test_a_custom_units_identity_rule_keeps_the_details_reference_base():
    """A custom verb's unit is held nonempty inside its own declaration, so a
    `#/properties/...` reference in the declared detail still resolves there."""
    spec = {
        "unit": "item",
        "detail": {
            "type": "object",
            "properties": {
                "item": {"type": "string"},
                "also": {"$ref": "#/properties/item"},
            },
            "required": ["item"],
            "additionalProperties": False,
        },
    }
    schema = registry_contract.detail_schema({}, spec)
    assert registry_schema.schema_error(schema, {"item": "a", "also": "b"}) is None
    assert "non-empty" in registry_schema.schema_error(schema, {"item": ""})
    assert spec["detail"]["properties"]["item"] == {"type": "string"}


def test_a_recorded_body_accepts_empty_text_but_not_a_missing_value():
    schema = registry_contract.detail_schema({}, {"record": {"kind": "body"}})
    assert registry_schema.schema_error(schema, {"value": ""}) is None
    assert registry_schema.schema_error(schema, {}) is not None


@pytest.mark.parametrize(
    ("prepaint", "upgrade", "code", "values"),
    [
        ("<span>0 running</span>", False, "prepaint-upgrade", {}),
        ("<span>0</span><span>1</span>", True, "prepaint-shape", {}),
        ("<td>0</td>", True, "prepaint-shape", {}),
        ("<div>", True, "prepaint-shape", {}),
        ("<div><span>0</div>", True, "prepaint-shape", {}),
        (
            '<div><span id="count">0</span></div>',
            True,
            "prepaint-marks",
            {"element": "span"},
        ),
        (
            '<div><lf-gloss tip="Zero">0</lf-gloss></div>',
            True,
            "prepaint-element",
            {"element": "lf-gloss"},
        ),
        ({"as": "lf-nothing"}, True, "prepaint-as", {"as": "lf-nothing"}),
    ],
)
def test_a_prepaint_is_one_plain_element_only_a_module_takes_out(
    page_dir, prepaint, upgrade, code, values
):
    """Delivery copies an x-prepaint into every occurrence for the first paint, and the
    widget's module takes it out, so it must be markup that stays one element where it
    is written and that nothing but that module acts on."""
    registry = json.loads((page_dir / "registry.json").read_text())
    tag = next(
        tag
        for tag, entry in registry.items()
        if not tag.startswith("$") and entry.get("x-upgrade")
    )
    registry[tag].update({"x-prepaint": prepaint, "x-upgrade": upgrade})

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], code, f"<{tag}>", **values)


@pytest.mark.parametrize(
    ("upgrade", "prepaint", "code", "values"),
    [
        (False, None, "requires", {"key": "x-initial", "needs": "x-upgrade"}),
        (True, "<span>Room</span>", "initial-and-prepaint", {}),
    ],
)
def test_initial_rendering_has_one_structure_owner(
    page_dir, upgrade, prepaint, code, values
):
    registry = json.loads((page_dir / "registry.json").read_text())
    tag = next(tag for tag in registry if tag.startswith("lf-"))
    entry = registry[tag]
    entry.update({"x-initial": "/vendor/early.js", "x-upgrade": upgrade})
    if prepaint is None:
        entry.pop("x-prepaint", None)
    else:
        entry["x-prepaint"] = prepaint
    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], code, f"<{tag}>", **values)


@pytest.mark.parametrize(
    ("entry", "code", "values"),
    [
        (None, "declaration-not-object", {"names": ["lf-options"]}),
        ({"type": "not-a-schema-type"}, "declaration-schema", {}),
    ],
)
def test_check_refuses_a_malformed_widget_schema(page_dir, entry, code, values):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"] = entry
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, code, **values), findings


@pytest.mark.parametrize("closed", [None, True])
def test_the_registry_door_refuses_an_open_detail_schema(page_dir, closed):
    """A verb carries only the detail keys it declares, so every reader of a detail
    field reads a declaration rather than whatever a client chose to send."""
    registry = json.loads((page_dir / "registry.json").read_text())
    detail = registry["lf-suggestion"]["x-state"]["decide"]["detail"]
    if closed is None:
        del detail["additionalProperties"]
    else:
        detail["additionalProperties"] = closed
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings,
        "invalid-extensions",
        "<lf-suggestion>",
        keyword="required" if closed is None else "const",
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [("patternProperties", {"^resolv": {"type": "string"}}), ("allOf", [{}])],
)
def test_the_registry_door_holds_a_detail_schema_to_the_keys_it_names(
    page_dir, key, value
):
    """`additionalProperties: false` closes an object only against names
    `properties` does not match, so a `patternProperties` beside it admits a
    field no declaration spells — and `resolves` is a field, which is how a
    per-card verb could come to settle a comment thread with every door that
    reads the name seeing nothing to read. Each of those doors reads the
    declaration rather than the event, so one unnamed key makes all of them
    approximate at once.

    The unrecorded `add` command owns its custom payload and fold unit."""
    registry = json.loads((page_dir / "registry.json").read_text())
    add = registry["lf-options"]["x-state"]["add"]
    add["detail"][key] = value
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "invalid-extensions", "<lf-options>", keyword="additionalProperties"
    )


def test_a_custom_detail_can_be_an_empty_closed_object(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-state"]["empty"] = {
        "unit": "widget",
        "detail": {"type": "object", "additionalProperties": False},
    }
    registry_validation.validate_registry(registry, "test registry")


def test_the_resolves_attribute_belongs_to_a_widget_with_a_local_obligation(page_dir):
    """Admission reads `resolves` off the widget whose obligation an action answers, so the
    name on a widget that asks nothing declares a thread nothing would ever close."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-board"]["properties"]["resolves"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "reserved-resolves", "<lf-board>")


def test_the_registry_door_demands_restated_of_a_whole_fold_widget(page_dir):
    """A widget that folds user decisions needs an explicit withdrawal route;
    its closed schema must admit the marker that retracts a decision."""
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["properties"]["restated"]
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "unrestated", "<lf-suggestion>")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("x-awaits", []),
        ("x-awaits", {"when": {"choose": True}}),
        ("x-thread-seat", False),
        ("x-content", "words"),
        ("x-owners", []),
        # Each of these names attributes, so an empty one declares nothing while
        # reading as a declaration.
        ("x-refers", {}),
        ("x-says", []),
        ("x-state", []),
        ("x-thread-surface", False),
        ("x-upgrade", "yes"),
        ("x-verbatim", "false"),
        ("x-work", []),
        ("x-work", {"seat": "content"}),
    ],
)
def test_check_refuses_malformed_registry_extensions(page_dir, key, value):
    """Custom registry keywords are executable contracts, not schema comments."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"][key] = value
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "invalid-extensions", "<lf-options>"), findings


def test_check_refuses_a_vendored_entry_declaring_a_key_this_leaf_does_not_admit(
    page_dir,
):
    """A layer entry declaring an x- key outside this Leaf's set is one this Leaf
    cannot serve (`layer.incompatible_layer`), so the refusal names the re-vendor."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-unknown"] = True
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "x-unknown" in result.output
    assert f"leaf page init {page_dir}" in result.output


@pytest.mark.parametrize(
    ("mutate", "code", "at", "values"),
    [
        (
            lambda registry: registry["lf-gloss"].update({"x-work": True}),
            "work-inline",
            "<lf-gloss>",
            {},
        ),
        (
            lambda registry: registry["lf-diagram"].update({"x-work": True}),
            "work-content",
            "<lf-diagram>",
            {"content": "data"},
        ),
    ],
)
def test_a_work_seat_declaration_is_checked_whole(page_dir, mutate, code, at, values):
    registry = json.loads((page_dir / "registry.json").read_text())
    mutate(registry)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, code, at, **values), findings


@pytest.mark.parametrize(
    ("mutate", "code", "values"),
    [
        # A report moves declared state only, never body words — the schema is
        # where the paint-only constraint lives, so a body record never parses.
        (_report_body_record, "invalid-extensions", {}),
        # Nor a part's place: the stamped version owns where a unit stands, and a
        # rank is read between the neighbours a widget shows the user.
        (_report_position_record, "invalid-extensions", {}),
        # The gate compares record forms, so a recordless report declares
        # nothing a version could be checked against.
        (_report_no_record, "invalid-extensions", {}),
        (_report_undeclared_attr, "record-undeclared", {"attr": "phase"}),
        # An x-says value is the page's words: replay writing one would change
        # what the page says while the file's reading held still.
        (_report_says_attr, "record-says", {"attr": "owner"}),
        # The destination owns the payload schema; a report cannot author another.
        (_report_authored_detail, "invalid-extensions", {}),
        # `overruled` is how a version keeps its state over a report; without it
        # every contradiction is unpublishable.
        (_report_without_overruled, "unoverruled", {}),
        # Reports replay through the widget's render(), so the widget must upgrade.
        (_report_without_upgrade, "needs-upgrade", {}),
        # Only an agent verb declares `text`.
        (_user_verb_text, "invalid-extensions", {}),
        # The user answers their own obligation; the agent's news never does.
        (_agent_verb_answers, "awaits-verbs", {}),
        (_body_record_with_prose, "body-content", {}),
        (_body_record_with_nested_widget, "body-nested", {}),
    ],
)
def test_an_agent_verb_declaration_is_checked_whole(page_dir, mutate, code, values):
    status, findings = _mutated_registry_check(page_dir, mutate)
    assert status != 0
    assert found(findings, code, **values), findings


@pytest.mark.parametrize("tag", ["lf-options[", "LF-options", "lf_options"])
def test_check_refuses_element_schemas_under_selector_names(page_dir, tag):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag] = registry.pop("lf-options")
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert [f.values["selector"] for f in findings if f.code.startswith("idiom-")] == [
        tag
    ]


def test_check_refuses_an_invalid_action_detail_schema(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["add"]["detail"]["properties"]["option"][
        "type"
    ] = "not-a-type"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "verb-detail-schema", "<lf-options>", verb="add")


def test_check_refuses_a_format_no_boundary_checks(page_dir):
    """jsonschema skips a format it has no checker for, so a declared one Leaf does
    not check would state a rule nothing enforces."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["properties"]["id"]["format"] = "hostname"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(findings, "declaration-schema", "<lf-options>", keyword="format")
    assert refused.values["reason"].startswith("format 'hostname'")

    registry["lf-options"]["properties"]["id"].pop("format")
    registry["lf-options"]["x-state"]["add"]["detail"]["properties"]["option"][
        "format"
    ] = "hostname"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "verb-detail-schema", "<lf-options>", keyword="format")


DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


def test_patterns_read_as_the_browser_reads_them(page_dir):
    """A schema pattern is an ECMAScript regular expression wherever Leaf reads it, so
    `$` ends the string rather than also matching before a final newline, and a
    pattern only Python's `re` reads, such as a `(?P<name>…)` group, is refused when
    the registry is checked."""
    name = {"type": "string", "pattern": "^[a-z]+$"}
    assert registry_schema.schema_error(name, "keep") is None
    assert registry_schema.schema_error(name, "keep\n") is not None
    # A subschema naming the 2020-12 dialect keeps the same reading, and so do the
    # keywords that classify an object's keys by pattern.
    nested = {"properties": {"id": {"$schema": DRAFT_2020_12, **name}}}
    assert registry_schema.schema_error(nested, {"id": "keep\n"}) is not None
    for closed in ("additionalProperties", "unevaluatedProperties"):
        keyed = {"patternProperties": {"^[a-z]+$": {}}, closed: False}
        assert registry_schema.schema_error(keyed, {"keep": 1}) is None
        assert registry_schema.schema_error(keyed, {"keep\n": 1}) is not None
    # ECMAScript a Python `re` would refuse reads as the browser reads it.
    letters = {"type": "string", "pattern": r"^\p{L}+$"}
    registry_schema.check_schema(letters)
    assert registry_schema.schema_error(letters, "héllo") is None
    # So does a value a schema declares a regular expression.
    regex = {"type": "string", "format": "regex"}
    assert registry_schema.schema_error(regex, r"^\p{L}+$") is None
    assert registry_schema.schema_error(regex, "(?P<id>a)") is not None

    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["properties"]["id"]["pattern"] = "^(?P<id>[a-z]+)$"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "declaration-schema", "<lf-options>", keyword="format")


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing-member", "invalid-extensions"),
        ("unknown-child", "creates-unknown"),
        ("optional-words", "creates-detail"),
        ("extra-field", "creates-detail"),
        ("widget-unit", "creates-unit"),
        ("wrong-owner", "creates-owner"),
        ("non-markup", "creates-content"),
        ("extra-required", "creates-required"),
        ("wrong-id", "creates-id"),
        ("report-creates", "invalid-extensions"),
    ],
)
def test_generated_child_declaration_closes_its_boundary(page_dir, mutation, code):
    registry = json.loads((page_dir / "registry.json").read_text())
    add = registry["lf-options"]["x-state"]["add"]
    option = registry["lf-option"]
    if mutation == "missing-member":
        del add["creates"]["child"]
    elif mutation == "unknown-child":
        add["creates"]["child"] = "lf-missing"
    elif mutation == "optional-words":
        add["detail"]["required"] = ["option"]
    elif mutation == "extra-field":
        add["detail"]["properties"]["note"] = {"type": "string"}
    elif mutation == "widget-unit":
        add["unit"] = "widget"
    elif mutation == "wrong-owner":
        option["x-owners"] = ["lf-board"]
    elif mutation == "non-markup":
        option["x-content"] = "members"
    elif mutation == "extra-required":
        option["required"].append("for")
    elif mutation == "wrong-id":
        option["properties"]["id"]["pattern"] = "^option-.+$"
    elif mutation == "report-creates":
        registry["lf-test-worker"]["x-state"]["state"]["creates"] = {
            "child": "lf-option",
            "words": "doing",
        }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, code), findings


@pytest.mark.parametrize("kind", [None, "string"])
def test_action_detail_schemas_match_the_post_object_contract(page_dir, kind):
    registry = json.loads((page_dir / "registry.json").read_text())
    detail = registry["lf-suggestion"]["x-state"]["decide"]["detail"]
    if kind is None:
        del detail["type"]
    else:
        detail["type"] = kind
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings,
        "invalid-extensions",
        "<lf-suggestion>",
        keyword="required" if kind is None else "const",
    )


def test_registry_cross_entry_checks_wait_for_every_entry_to_validate(page_dir):
    """A child appearing first must not inspect a malformed parent half-validated."""
    registry = json.loads((page_dir / "registry.json").read_text())
    child = registry.pop("lf-old")
    registry["lf-suggestion"]["x-state"] = 42
    registry = {"lf-old": child, **registry}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "invalid-extensions", "<lf-suggestion>")


@pytest.mark.parametrize(
    ("tag", "key", "fallback"),
    [
        ("lf-options", "x-state", None),
        ("lf-note", "x-thread-seat", {"when": {"id": ["note"]}}),
        ("lf-diff", "x-thread-surface", True),
    ],
)
def test_runtime_features_require_an_upgraded_widget(page_dir, tag, key, fallback):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = registry[tag].get(key, fallback)
    registry[tag]["x-upgrade"] = False
    # An initial renderer needs an upgrade too, but answers through its own finding.
    registry[tag].pop("x-initial", None)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(findings, "needs-upgrade", f"<{tag}>")
    assert key in refused.values["keys"]


def test_retirement_requires_an_owner(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-old"]["x-owners"]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "invalid-extensions", "<lf-old>")


def test_check_refuses_a_retirement_outcome_its_parent_does_not_decide(page_dir):
    """A retirement outcome is a cross-entry reference, not a free-form label.

    If it names no outcome of the parent widget's deciding verb, the browser's selector can never
    match and the file reading can disagree with what that widget knows how to
    settle. Refuse that vocabulary at its one ingress instead of leaving every
    consumer to rediscover the broken reference.
    """
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-old"]["x-retired-when"] = "approve"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "retired-when", "<lf-old>", outcome="approve", owner="lf-suggestion"
    )


@pytest.mark.parametrize("fault", ["per-part", "agent-written"])
def test_retirement_verbs_fold_by_the_parent_widget(page_dir, fault):
    """The deciding verb is the user's whole-widget decision: a verb folding per part,
    or one the agent writes, cannot say which members leave the page."""
    registry = json.loads((page_dir / "registry.json").read_text())
    suggestion = registry["lf-suggestion"]
    decide = suggestion["x-state"]["decide"]
    if fault == "per-part":
        decide["detail"]["properties"]["part"] = {"type": "string"}
        decide["detail"]["required"].append("part")
        decide["unit"] = "part"
    else:
        # An agent verb never answers an obligation, so the suggestion stops asking one.
        suggestion.pop("x-awaits")
        suggestion.pop("x-withdrawn-as")
        suggestion["properties"].pop("resolves")
        decide["writer"] = "agent"
        suggestion["properties"]["outcome"] = decide.pop("detail")["properties"][
            "outcome"
        ]
        decide["record"] = {"kind": "value", "attr": "outcome"}
        suggestion["properties"]["overruled"] = {"type": "boolean"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    if fault == "per-part":
        assert found(findings, "deciding-verb", "<lf-suggestion>", verb="decide")
    else:
        assert found(findings, "invalid-extensions", "<lf-suggestion>")


@pytest.mark.parametrize(
    ("tag", "key", "declaration", "code", "values"),
    [
        (
            "lf-options",
            "x-awaits",
            {"when": {"pick": [True]}},
            "predicate-attribute",
            {"key": "x-awaits", "attr": "pick"},
        ),
        (
            "lf-options",
            "x-thread-seat",
            {"when": {"pick": [True]}},
            "predicate-attribute",
            {"key": "x-thread-seat", "attr": "pick"},
        ),
        (
            "lf-options",
            "x-awaits",
            {"when": {"choose": ["yes"]}},
            "predicate-schema",
            {"key": "x-awaits", "attr": "choose", "value": "yes"},
        ),
        (
            "lf-options",
            "x-awaits",
            {"when": {"id": [True]}},
            None,
            {"key": "x-awaits", "attr": "id", "value": True},
        ),
        (
            "lf-test-task",
            "x-awaits",
            {"when": {"status": ["reviewing"]}},
            "predicate-schema",
            {"key": "x-awaits", "attr": "status", "value": "reviewing"},
        ),
        (
            "lf-options",
            "x-thread-seat",
            {"when": {"id": ["NOT-VALID"]}},
            "predicate-schema",
            {"key": "x-thread-seat", "attr": "id", "value": "NOT-VALID"},
        ),
        (
            "lf-options",
            "x-awaits",
            {"answered": {"answer": {"when": {"batch": [True]}}}},
            "predicate-attribute",
            {"key": "x-awaits", "attr": "batch"},
        ),
        (
            "lf-options",
            "x-awaits",
            {"answered": {"submit": {}}},
            "awaits-verbs",
            {"verbs": ["submit"]},
        ),
        (
            "lf-suggestion",
            "x-awaits",
            {"answered": {"decide": {}}, "all": "approve"},
            "awaits-blanket",
            {"outcome": "approve"},
        ),
        (
            "lf-options",
            "x-awaits",
            {"when": {"choose": [True]}, "retired": "settled"},
            "awaits-retired",
            {"flag": "settled"},
        ),
    ],
)
def test_check_holds_predicates_to_presence_or_declared_attribute_values(
    page_dir, tag, key, declaration, code, values
):
    """Booleans test attribute presence; strings must be values the widget can hold.

    A predicate naming an impossible value silently omits the widget from every
    consumer. An undeclared answering verb leaves its obligation open forever."""
    registry = json.loads((page_dir / "registry.json").read_text())
    if key == "x-awaits":
        declaration = {
            "value": next(iter(registry[tag]["x-state"])),
            "answered": {"choose": {}},
            **declaration,
        }
    registry[tag][key] = declaration
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    if code is None:
        assert status == 0, findings
    else:
        assert status != 0
        assert found(findings, code, f"<{tag}>", **values), findings


def test_a_local_obligation_declares_its_answered_condition(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-test-task"]["x-awaits"] = {"value": "answer"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status != 0
    [refused] = found(
        findings, "invalid-extensions", "<lf-test-task>", keyword="required"
    )
    assert "answered" in refused.values["reason"]


def test_a_part_scoped_answering_verb_needs_an_empty_condition(page_dir):
    """A part record does not answer its whole obligation merely by being in force."""
    registry = queue_board_registry(
        json.loads((page_dir / "registry.json").read_text())
    )
    registry["lf-board"]["x-awaits"]["answered"]["move"].pop("empty")

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], "answering-part", "<lf-board>", verb="move")


@pytest.mark.parametrize(
    ("tag", "key", "value", "missing"),
    [
        (
            "lf-gloss",
            "x-says",
            {"tip": "after", "colour": "after"},
            "colour",
        ),
        ("lf-option", "x-refers", {"for": {}, "about": {}}, "about"),
        ("lf-option", "x-unique", {"label": "lf-options"}, "label"),
        ("lf-code", "x-language", "dialect", "dialect"),
        ("lf-column", "x-tone", "shade", "shade"),
    ],
)
def test_check_refuses_a_key_naming_an_attribute_the_widget_has_not_got(
    page_dir, tag, key, value, missing
):
    """These keys point at attributes rather than declaring them — the words a widget
    shows, the ones that name another element, the ones no two members of an owner
    share, and the two carrying a word its layer
    has to know —
    and each is read by a pass that finds the attribute absent and does nothing. That
    is the never-closed vocabulary's own failure mode: no error anywhere, the widget
    simply missing from the pass, and a page that looks authored correctly because it
    was. The door is the only place the mistake is visible, so it refuses here.

    Every one of them parametrized rather than three, because it is one rule
    (ATTRIBUTE_KEYS) and the case that would go wrong is a key left off the tuple —
    which no test of the three that were written by hand could ever see. The shapes
    differ and the rule does not: a mapping keyed by the names, or one name."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = value
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "undeclared-attributes", f"<{tag}>", key=key, names=[missing]
    ), findings


@pytest.mark.parametrize(
    ("reference", "code", "values"),
    [
        (
            {"via": "$missing.widgets", "where": {"role": "goal"}},
            "refers-unknown-map",
            {"via": "$missing.widgets"},
        ),
        (
            {"via": "$work.widgets", "where": {"role": "imaginary"}},
            "refers-unmatched",
            {"via": "$work.widgets", "where": {"role": "imaginary"}},
        ),
        (
            {"tag": "lf-ghost", "key": "name"},
            "refers-unknown-member",
            {"member": "lf-ghost"},
        ),
        (
            {"tag": "lf-option", "key": "id"},
            "refers-unkeyed",
            {"member": "lf-option", "key": "id"},
        ),
    ],
)
def test_a_typed_reference_names_a_reachable_package_role(
    page_dir, reference, code, values
):
    """A bad package relation fails at the registry door, not on every instance. A
    keyed relation names its member by a key the member declares unique, so one
    reference never stands for two members."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-option"]["x-refers"]["for"] = reference

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], code, "<lf-option>", attr="for", **values)


def test_an_obligation_role_declares_an_addressable_instance(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-idless-decision"] = {
        "description": "A decision without an address.",
        "type": "object",
        "properties": {"open": {"type": "boolean"}},
        "additionalProperties": False,
        "x-content": "markup",
        "x-awaits": {
            "when": {"open": [True]},
            "value": "answer",
            "answered": {"answer": {}},
        },
        "x-state": {
            "answer": {
                "detail": {"type": "object", "additionalProperties": False},
                "unit": "widget",
            }
        },
        "x-upgrade": False,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "addressable-id", "<lf-idless-decision>", key="x-awaits")


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2026-08-21T08:00:00Z", True),
        ("2026-08-21t08:00:00z", True),
        ("2026-08-21T08:00:00+01:30", True),
        ("2026-08-21T08:00:00", False),
        ("2026-08-21 08:00:00+00:00", False),
    ],
)
def test_date_time_format_is_an_absolute_rfc3339_instant(value, valid):
    schema = {"type": "string", "format": "date-time"}

    assert registry_schema.json_validator(schema).is_valid(value) is valid


def test_uri_format_checks_absolute_urls_with_browser_syntax():
    validator = registry_schema.json_validator({"type": "string", "format": "uri"})

    for value in (
        "https://example.org/path?q=1#section",
        "https:example.org",
        "https://Bücher.example/",
        "mailto:reader@example.org",
    ):
        assert validator.is_valid(value), value
    for value in (
        "relative/path",
        "http://a.test:99999/",
        "http://256.0.0.1/",
        "http://exa%mple.org/",
    ):
        assert not validator.is_valid(value), value


def test_x_awaits_names_the_verbs_that_answer_it(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-awaits"]["answered"] = {"missing": {}}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "awaits-verbs", "<lf-suggestion>", verbs=["missing"])


@pytest.mark.parametrize(
    ("tag", "mutate", "code"),
    [
        # The view names its widget by id, the one relation it resolves.
        (
            "lf-card",
            lambda r: r["lf-card"]["x-refers"].update(
                shows={"tag": "lf-option", "key": "value"}
            ),
            "shows-reference",
        ),
        # Its owners name the answer they hold, or no view stands anywhere.
        (
            "lf-card",
            lambda r: r["lf-column"]["properties"].pop("value"),
            "shows-value",
        ),
        # Members unique by the key, or a value names no one member.
        ("lf-options", lambda r: r["lf-option"].pop("x-unique"), "awaits-key"),
    ],
)
def test_a_view_relation_names_attributes_both_sides_have(page_dir, tag, mutate, code):
    registry = json.loads((page_dir / "registry.json").read_text())
    mutate(registry)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, code, f"<{tag}>"), findings
