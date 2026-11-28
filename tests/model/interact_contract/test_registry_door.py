"""What registry validation refuses in a widget declaration: detail schemas, extensions,
formats, patterns, rendering owners, obligations, retirement and references."""

from copy import deepcopy

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
    _report_undeclared_attr,
    _report_without_module,
    _user_verb_text,
    check_findings,
    element_declaration,
    found,
    registry_refusal,
)

from leaf.base.schema import DATA_CONTRACT_NAME, DATA_SOURCE_NAME, ELEMENT_ID
from leaf.source.registry import contract as registry_contract
from leaf.source.registry import schema as registry_schema
from leaf.source.registry import validation as registry_validation
from leaf.source.vocabulary import read_page_registry
from model.interact_contract import declare_vocabulary, vocabulary


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
    value_2 = registry_schema.schema_error(schema, {"item": ""})
    assert value_2 is not None
    assert "non-empty" in value_2
    assert spec["detail"]["properties"]["item"] == {"type": "string"}


def test_the_id_of_a_created_child_reads_as_an_element_id(page_dir):
    """A verb that creates a child names it by its fold unit, so the detail field
    carrying it holds an element id, though the declaration spells only a string."""
    entry = vocabulary(page_dir)["lf-options"]
    schema = registry_contract.detail_schema(entry, entry["verbs"]["add"])
    added = {"option": "ship-option-1", "text": "Ship it"}
    assert registry_schema.schema_error(schema, added) is None
    assert registry_schema.schema_error(schema, {**added, "option": "Ship 1"})


def test_a_recorded_body_accepts_empty_text_but_not_a_missing_value():
    schema = registry_contract.detail_schema({}, {"record": {"kind": "body"}})
    assert registry_schema.schema_error(schema, {"value": ""}) is None
    assert registry_schema.schema_error(schema, {}) is not None


@pytest.mark.parametrize(
    ("entry", "code", "values"),
    [
        (None, "declaration-not-object", {"names": ["lf-options"]}),
        (
            {"description": "d", "attributes": {"type": "not-a-schema-type"}},
            "attributes-schema",
            {},
        ),
        # Every declaration says what its element is for.
        ({"attributes": {}}, "invalid-declaration", {"keyword": "required"}),
    ],
)
def test_check_refuses_a_malformed_widget_schema(page_dir, entry, code, values):
    registry = vocabulary(page_dir)
    registry["lf-options"] = entry
    declare_vocabulary(page_dir, registry)
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, code, **values), findings


def test_the_registry_door_refuses_an_open_detail_schema(page_dir):
    """A verb carries only the detail keys it declares, so every reader of a detail
    field reads a declaration rather than whatever a client chose to send. A detail
    that opens itself is refused, where an attribute schema that does is admitted."""
    registry = vocabulary(page_dir)
    registry["lf-suggestion"]["verbs"]["decide"]["detail"]["additionalProperties"] = (
        True
    )
    declare_vocabulary(page_dir, registry)
    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(
        findings, "invalid-declaration", "<lf-suggestion>", keyword="const"
    )
    assert refused.values["path"] == [
        "verbs",
        "decide",
        "detail",
        "additionalProperties",
    ]


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
    registry = vocabulary(page_dir)
    add = registry["lf-options"]["verbs"]["add"]
    add["detail"][key] = value
    declare_vocabulary(page_dir, registry)
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "invalid-declaration", "<lf-options>", keyword="additionalProperties"
    )


def test_a_custom_detail_can_be_an_empty_closed_object(page_dir):
    registry = vocabulary(page_dir)
    registry["lf-suggestion"]["verbs"]["empty"] = {
        "unit": "widget",
        "detail": {"type": "object", "additionalProperties": False},
    }
    registry_validation.validate_registry(registry, "test registry")


def test_composition_gives_a_whole_widget_verb_the_attribute_that_takes_it_back(
    page_dir,
):
    """A version takes back a user's decision on a whole widget with `restated`, and
    an agent's report with `overruled`. The composed vocabulary carries each on a
    widget with such a verb (`registry.contract.stamp_retractions`), so its declaration
    lists neither, and a schema it lists for one is replaced: one that admitted no
    marker would leave a decision no version could take back. A widget whose verb folds
    on its members takes none: the member the verb names carries it."""
    registry = vocabulary(page_dir)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    for tag in ("lf-local", "lf-listed"):
        (widgets / f"{tag}.js").write_text("export function upgrade() {}\n")
        registry[tag] = element_declaration(tag, upgrade=True)
        registry[tag]["attributes"]["properties"]["reading"] = {"type": "string"}
        registry[tag]["verbs"] = {
            "set": {"unit": "widget", "detail": {}},
            "measure": {
                "unit": "widget",
                "writer": "agent",
                "record": {"kind": "value", "attr": "reading"},
            },
        }
    registry["lf-listed"]["attributes"]["properties"]["restated"] = False
    declare_vocabulary(page_dir, registry)

    composed = read_page_registry(page_dir).registry
    for tag in ("lf-local", "lf-listed"):
        properties = composed[tag]["attributes"]["properties"]
        assert properties["restated"] == properties["overruled"] == {"type": "boolean"}
    board = composed["lf-board"]
    assert {spec["unit"] for spec in board["verbs"].values()} == {"unit"}
    assert not {"restated", "overruled"} & set(board["attributes"]["properties"])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("awaits", []),
        ("awaits", {"when": {"settled": True}}),
        ("content", "words"),
        ("owners", []),
        # Each of these names attributes, so an empty one declares nothing while
        # reading as a declaration.
        ("refers", {}),
        ("verbs", []),
        ("verbatim", "false"),
        ("work", []),
        ("work", {"seat": "content"}),
    ],
)
def test_check_refuses_malformed_registry_extensions(page_dir, key, value):
    """Custom registry keywords are executable contracts, not schema comments."""
    registry = vocabulary(page_dir)
    registry["lf-options"][key] = value
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "invalid-declaration", "<lf-options>"), findings


@pytest.mark.parametrize(
    ("mutate", "code", "values"),
    [
        # A report moves declared state only, never body words — the schema is
        # where the paint-only constraint lives, so a body record never parses.
        (_report_body_record, "invalid-declaration", {}),
        # Nor a part's place: the stamped version owns where a unit stands, and a
        # rank is read between the neighbours a widget shows the user.
        (_report_position_record, "invalid-declaration", {}),
        # The gate compares record forms, so a recordless report declares
        # nothing a version could be checked against.
        (_report_no_record, "invalid-declaration", {}),
        (_report_undeclared_attr, "record-undeclared", {"attr": "phase"}),
        # The destination owns the payload schema; a report cannot author another.
        (_report_authored_detail, "invalid-declaration", {}),
        # Reports replay through the widget's render(), so the widget needs a module.
        (_report_without_module, "needs-module", {}),
        # Only an agent verb declares `text`.
        (_user_verb_text, "invalid-declaration", {}),
        # The user answers their own obligation; the agent's news never does.
        (_agent_verb_answers, "awaits-value", {}),
        (_body_record_with_prose, "body-content", {}),
        (_body_record_with_nested_widget, "body-nested", {}),
    ],
)
def test_an_agent_verb_declaration_is_checked_whole(page_dir, mutate, code, values):
    status, findings = _mutated_registry_check(page_dir, mutate)
    assert status != 0
    assert found(findings, code, **values), findings


def _second_document_input(registry):
    inputs = registry["lf-text-document"]["inputs"]
    inputs["notes"] = {**inputs["document"], "source": "notes-source"}


def _markdown_body_input(registry):
    registry["lf-draft"]["inputs"] = {
        "text": {"contract": "text-document", "source": "source", "property": "value"}
    }


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [(_second_document_input, "inputs"), (_markdown_body_input, "words")],
)
def test_a_data_widget_s_pre_feeds_at_most_one_input(page_dir, mutate, reason):
    """An unbound data widget's <pre> is its `value` input's text, so two `value`
    inputs would share it, and an element whose <pre> is already its words takes
    none."""
    status, findings = _mutated_registry_check(page_dir, mutate)
    assert status != 0
    assert found(findings, "data-input", reason=reason), findings


@pytest.mark.parametrize("tag", ["lf-options[", "LF-options", "lf_options"])
def test_check_refuses_element_schemas_under_selector_names(page_dir, tag):
    registry = vocabulary(page_dir)
    registry[tag] = registry.pop("lf-options")
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    assert [f.values["selector"] for f in findings if f.code.startswith("idiom-")] == [
        tag
    ]


def test_check_refuses_a_format_no_boundary_checks(page_dir):
    """jsonschema skips a format it has no checker for, so a declared one Leaf does
    not check would state a rule nothing enforces."""
    registry = vocabulary(page_dir)
    registry["lf-option"]["attributes"]["properties"]["label"]["format"] = "hostname"
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(findings, "attributes-schema", "<lf-option>", keyword="format")
    assert refused.values["reason"].startswith("format 'hostname'")

    registry["lf-option"]["attributes"]["properties"]["label"].pop("format")
    registry["lf-options"]["verbs"]["add"]["detail"]["properties"]["option"][
        "format"
    ] = "hostname"
    declare_vocabulary(page_dir, registry)
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

    registry = vocabulary(page_dir)
    registry["lf-option"]["attributes"]["properties"]["label"]["pattern"] = (
        "^(?P<id>[a-z]+)$"
    )
    declare_vocabulary(page_dir, registry)
    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "attributes-schema", "<lf-option>", keyword="format")


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("missing-member", "invalid-declaration"),
        ("unknown-child", "creates-unknown"),
        ("optional-words", "creates-detail"),
        ("extra-field", "creates-detail"),
        ("widget-unit", "creates-unit"),
        ("wrong-owner", "creates-owner"),
        ("non-markup", "creates-content"),
        ("extra-required", "creates-required"),
        ("report-creates", "invalid-declaration"),
    ],
)
def test_generated_child_declaration_closes_its_boundary(page_dir, mutation, code):
    registry = vocabulary(page_dir)
    add = registry["lf-options"]["verbs"]["add"]
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
        option["owners"] = ["lf-board"]
    elif mutation == "non-markup":
        option["content"] = "members"
    elif mutation == "extra-required":
        option["attributes"]["required"].append("for")
    elif mutation == "report-creates":
        registry["lf-test-worker"]["verbs"]["state"]["creates"] = {
            "child": "lf-option",
            "words": "doing",
        }
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, code), findings


def test_composition_writes_the_grammar_of_each_name_leaf_looks_up(page_dir):
    """A widget declares only that its data source and its contract attribute are
    strings, and lists no `id`. The composed vocabulary carries Leaf's grammar for each
    (`registry.contract.stamp_grammars`), replacing one the declaration gave, and an
    `id` on every element, first among its attributes and a string whatever the
    declaration lists for it, so validation and an author reading the entry read
    Leaf's. A reference to another element keeps what it declares, since `page check`
    resolves it to its target."""
    registry = vocabulary(page_dir)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    (widgets / "lf-named.js").write_text("export function upgrade() {}\n")
    named = element_declaration("lf-named", upgrade=True)
    named["attributes"]["properties"].update(
        about={"type": "string"},
        source={"type": "string"},
        shape={"type": "string"},
    )
    named["refers"] = {"about": {}}
    named["inputs"] = {"feed": {"contract": "measured-scalar", "source": "source"}}
    named["verbs"] = {
        "submit": {
            "unit": "widget",
            "contract": {"field": "values", "attribute": "shape"},
            "detail": {
                "properties": {"values": {"type": "object"}},
                "required": ["values"],
            },
        }
    }
    registry["lf-named"] = named
    (widgets / "lf-listed.js").write_text("export function upgrade() {}\n")
    registry["lf-listed"] = element_declaration("lf-listed", upgrade=True)
    registry["lf-listed"]["attributes"]["properties"].update(
        label={"type": "string"}, id={"type": "integer", "pattern": "^anything$"}
    )
    declare_vocabulary(page_dir, registry)

    composed = read_page_registry(page_dir).registry
    takes_id = {"type": "string", "pattern": f"^{ELEMENT_ID}$"}
    for tag in ("lf-named", "lf-listed"):
        assert next(iter(composed[tag]["attributes"]["properties"].items())) == (
            "id",
            takes_id,
        )
    properties = composed["lf-named"]["attributes"]["properties"]
    expected = {
        "id": f"^{ELEMENT_ID}$",
        "about": None,
        "source": f"^{DATA_SOURCE_NAME}$",
        "shape": f"^{DATA_CONTRACT_NAME}$",
    }
    assert {attr: properties[attr].get("pattern") for attr in expected} == expected


def test_composition_closes_an_attribute_schema_that_does_not_say(page_dir):
    """A declaration names its element's attributes and leaves `type` and
    `additionalProperties` out. The composed vocabulary carries both
    (`registry.contract.complete_declarations`), each where the declaration doesn't
    write it, so `page check` refuses an attribute the schema doesn't name, such as a
    misspelt one, in the words it gives where a declaration writes both itself. A
    schema that gives one of its own keeps it, as one that admits any attribute does.
    A declaration with no `attributes` composes to the schema that names none."""
    registry = vocabulary(page_dir)
    named = {"properties": {"tone": {"type": "string"}}}
    written = {"type": "object", **named, "additionalProperties": False}
    for tag, attributes in (
        ("lf-unsaid", named),
        ("lf-typed", {"type": "object", **named}),
        ("lf-written", written),
        ("lf-open", {**named, "additionalProperties": True}),
    ):
        registry[tag] = {"description": "A block.", "attributes": attributes}
    registry["lf-bare"] = {"description": "A block."}
    declare_vocabulary(page_dir, registry)

    composed = read_page_registry(page_dir).registry
    for tag in ("lf-unsaid", "lf-typed"):
        assert composed[tag]["attributes"] == composed["lf-written"]["attributes"]
        assert list(composed[tag]["attributes"]) == list(written)
    assert composed["lf-open"]["attributes"]["additionalProperties"] is True
    bare = composed["lf-bare"]["attributes"]
    assert (bare["type"], bare["additionalProperties"]) == ("object", False)
    assert list(bare["properties"]) == ["id"]

    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            "".join(
                f'<{tag} id="{tag}" tonne="warm">Words.</{tag}>'
                for tag in ("lf-unsaid", "lf-written", "lf-open", "lf-bare")
            )
            + "</main>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status != 0
    refused = {
        finding.at: finding.values for finding in found(findings, "attribute-schema")
    }
    assert refused.keys() == {"<lf-unsaid>", "<lf-written>", "<lf-bare>"}
    assert refused["<lf-unsaid>"]["keyword"] == "additionalProperties"
    assert (
        refused["<lf-unsaid>"]["reason"]
        == refused["<lf-written>"]["reason"]
        == "Additional properties are not allowed ('tonne' was unexpected)"
    )


def test_composition_closes_a_verb_detail_that_does_not_say(page_dir):
    """A verb's `detail` schema names its fields and leaves `type` and
    `additionalProperties` out, as an attribute schema does. The composed vocabulary
    carries both (`registry.contract.complete_declarations`), so the operation an
    admitted event records is the one a declaration writing both gives, and a detail
    holding a field the schema doesn't name is refused."""
    registry = vocabulary(page_dir)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    named = {"properties": {"note": {"type": "string"}}, "required": ["note"]}
    written = {"type": "object", **named, "additionalProperties": False}
    for tag, detail in (("lf-unsaid", named), ("lf-written", written)):
        (widgets / f"{tag}.js").write_text("export function upgrade() {}\n")
        registry[tag] = {
            "description": "A block.",
            "verbs": {"note": {"unit": "widget", "detail": detail}},
        }
    declare_vocabulary(page_dir, registry)

    composed = read_page_registry(page_dir).registry
    unsaid, said = composed["lf-unsaid"], composed["lf-written"]
    assert unsaid["verbs"] == said["verbs"]
    assert list(unsaid["verbs"]["note"]["detail"]) == list(written)
    recorded = [
        composed["$states"][tag]["note"]["definition"] | {"origin": None}
        for tag in ("lf-unsaid", "lf-written")
    ]
    assert recorded[0] == recorded[1]
    schema = registry_contract.detail_schema(unsaid, unsaid["verbs"]["note"])
    assert registry_schema.schema_error(schema, {"note": "kept"}) is None
    assert registry_schema.schema_error(schema, {"note": "kept", "stray": "x"})


def test_action_detail_schemas_match_the_post_object_contract(page_dir):
    registry = vocabulary(page_dir)
    registry["lf-suggestion"]["verbs"]["decide"]["detail"]["type"] = "string"
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(findings, "invalid-declaration", "<lf-suggestion>", keyword="const")


@pytest.mark.parametrize(
    ("tag", "change", "says"),
    [
        (
            "lf-activity",
            lambda entry: entry.update(bound="top"),
            "at `bound`: 'top' is not one of ['start', 'end']",
        ),
        (
            "lf-options",
            lambda entry: entry["verbs"]["answer"]["detail"].pop(
                "additionalProperties"
            ),
            "at `verbs.answer.detail`: 'additionalProperties' is a required property",
        ),
    ],
)
def test_a_declaration_refusal_names_the_fact_it_is_about(page_dir, tag, change, says):
    """The schema's own words name only the value it refused, so the refusal adds where
    in the declaration that value stands."""
    registry = vocabulary(page_dir)
    change(registry[tag])

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert finding.said.endswith(f"<{tag}> is not a valid declaration ($keys) {says}")


def test_registry_cross_entry_checks_wait_for_every_entry_to_validate(page_dir):
    """A child appearing first must not inspect a malformed parent half-validated."""
    registry = vocabulary(page_dir)
    child = registry.pop("lf-old")
    registry["lf-suggestion"]["verbs"] = 42
    registry = {"lf-old": child, **registry}

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], "invalid-declaration", "<lf-suggestion>")


@pytest.mark.parametrize(
    ("tag", "key", "fallback"),
    [
        ("lf-options", "verbs", None),
        ("lf-note", "shadow", True),
        ("lf-card", "inputs", None),
    ],
)
def test_runtime_features_require_a_module(page_dir, tag, key, fallback):
    """A page declares a tag that takes what only a module provides, and holds no
    `page/widgets/<tag>.js` for it."""
    registry = vocabulary(page_dir)
    bare = deepcopy(registry[tag])
    bare[key] = bare.get(key, fallback)
    bare.pop("example", None)
    registry["lf-bare"] = bare
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(findings, "needs-module", "<lf-bare>")
    assert key in refused.values["keys"]


def test_a_fact_read_through_another_names_the_one_it_lacks(page_dir):
    """A retiring member is read through its owners, so a declaration without them
    is refused naming both facts."""
    registry = vocabulary(page_dir)
    del registry["lf-old"]["owners"]
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    [refused] = found(
        findings, "invalid-declaration", "<lf-old>", keyword="dependentRequired"
    )
    assert refused.values["reason"] == "'owners' is a dependency of 'retired-when'"


def test_check_refuses_a_retirement_outcome_its_parent_does_not_decide(page_dir):
    """A retirement outcome is a cross-entry reference, not a free-form label.

    If it names no outcome of the parent widget's deciding verb, the browser's selector can never
    match and the file reading can disagree with what that widget knows how to
    settle. Refuse that vocabulary at its one ingress instead of leaving every
    consumer to rediscover the broken reference.
    """
    registry = vocabulary(page_dir)
    registry["lf-old"]["retired-when"] = "approve"
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "retired-when", "<lf-old>", outcome="approve", owner="lf-suggestion"
    )


@pytest.mark.parametrize("fault", ["per-part", "agent-written"])
def test_retirement_verbs_fold_by_the_parent_widget(page_dir, fault):
    """The deciding verb is the user's whole-widget decision: a verb folding per part,
    or one the agent writes, cannot say which members leave the page."""
    registry = vocabulary(page_dir)
    suggestion = registry["lf-suggestion"]
    decide = suggestion["verbs"]["decide"]
    if fault == "per-part":
        decide["detail"]["properties"]["part"] = {"type": "string"}
        decide["detail"]["required"].append("part")
        decide["unit"] = "part"
    else:
        # An agent verb never answers an obligation, so the suggestion stops asking one.
        suggestion.pop("awaits")
        suggestion["attributes"]["properties"].pop("resolves")
        decide["writer"] = "agent"
        suggestion["attributes"]["properties"]["outcome"] = decide.pop("detail")[
            "properties"
        ]["outcome"]
        decide["record"] = {"kind": "value", "attr": "outcome"}
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    if fault == "per-part":
        assert found(findings, "deciding-verb", "<lf-suggestion>", verb="decide")
    else:
        assert found(findings, "invalid-declaration", "<lf-suggestion>")


@pytest.mark.parametrize("schema", [False, True])
def test_a_boolean_attribute_schema_is_refused_beside_a_layer_fault(page_dir, schema):
    """JSON Schema admits `true` or `false` as an attribute's schema, neither naming a
    type, so a pane whose `label` is one is refused for it, in the same run as a layer
    fact's problem."""
    registry = deepcopy(read_page_registry(page_dir).registry)
    registry["lf-pane"]["attributes"]["properties"]["label"] = schema
    registry["$languages"]["paths"][".zz"] = "unnamed"

    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_validation.validate_registry(registry, "test registry")

    assert [(f.code, f.at) for f in refused.value.findings] == [
        ("undeclared-language", ""),
        ("reading-role-attr", "<lf-pane>"),
    ]


def test_a_deciding_verb_without_outcomes_is_reported_by_each_reader(page_dir):
    """The parent and the children retiring under it are checked in one run, so each
    reads the parent's decision before its own check holds it to an outcome."""

    def drop_outcome(registry):
        detail = registry["lf-suggestion"]["verbs"]["decide"]["detail"]
        del detail["properties"]["outcome"]
        detail["required"].remove("outcome")

    status, findings = _mutated_registry_check(page_dir, drop_outcome)

    assert status != 0
    assert found(findings, "awaits-blanket", "<lf-suggestion>")
    assert found(findings, "retired-when", "<lf-old>", owner="lf-suggestion")


@pytest.mark.parametrize(
    ("tag", "key", "declaration", "code", "values"),
    [
        (
            "lf-options",
            "awaits",
            {"when": {"pick": [True]}},
            "predicate-attribute",
            {"key": "awaits", "attr": "pick"},
        ),
        (
            "lf-options",
            "exhibit",
            {"when": {"pick": [True]}},
            "predicate-attribute",
            {"key": "exhibit", "attr": "pick"},
        ),
        (
            "lf-options",
            "flow",
            {"when": {"pick": [True]}},
            "predicate-attribute",
            {"key": "flow", "attr": "pick"},
        ),
        (
            "lf-options",
            "awaits",
            {"when": {"settled": ["yes"]}},
            "predicate-schema",
            {"key": "awaits", "attr": "settled", "value": "yes"},
        ),
        (
            "lf-options",
            "awaits",
            {"when": {"id": [True]}},
            None,
            {"key": "awaits", "attr": "id", "value": True},
        ),
        (
            "lf-test-task",
            "awaits",
            {"when": {"status": ["reviewing"]}},
            "predicate-schema",
            {"key": "awaits", "attr": "status", "value": "reviewing"},
        ),
        (
            "lf-options",
            "exhibit",
            {"when": {"id": ["NOT-VALID"]}},
            "predicate-schema",
            {"key": "exhibit", "attr": "id", "value": "NOT-VALID"},
        ),
        (
            "lf-suggestion",
            "awaits",
            {"all": "approve"},
            "awaits-blanket",
            {"outcome": "approve"},
        ),
        (
            "lf-options",
            "awaits",
            {"when": {"multiple": [True]}, "retired": "settled"},
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
    consumer."""
    registry = vocabulary(page_dir)
    if key == "awaits":
        declaration = {"value": next(iter(registry[tag]["verbs"])), **declaration}
    registry[tag][key] = declaration
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    if code is None:
        assert status == 0, findings
    else:
        assert status != 0
        assert found(findings, code, f"<{tag}>", **values), findings


def test_a_local_obligation_names_the_verb_that_answers_it(page_dir):
    """`awaits` needs its `value`, and one that names none is refused for that."""
    registry = vocabulary(page_dir)
    registry["lf-options"]["awaits"] = {"when": {"settled": [False]}}
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    [refused] = found(
        findings, "invalid-declaration", "<lf-options>", keyword="required"
    )
    assert "'value'" in refused.values["reason"]


def test_check_refuses_a_reference_naming_an_attribute_the_widget_has_not_got(
    page_dir,
):
    """`refers` points at attributes rather than declaring them, and each pass that
    reads it finds the attribute absent and does nothing. That is the never-closed
    vocabulary's own failure mode: no error anywhere, the widget simply missing from
    the pass, and a page that looks authored correctly because it was. The door is the
    only place the mistake is visible, so it refuses here."""
    registry = vocabulary(page_dir)
    registry["lf-option"]["refers"] = {"for": {}, "about": {}}
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)
    assert status != 0
    assert found(
        findings, "undeclared-attributes", "<lf-option>", key="refers", names=["about"]
    ), findings


@pytest.mark.parametrize(
    "reference",
    [
        {"via": "$work.widgets", "where": {"role": "goal"}},
        {"owns": True},
        {"tag": "lf-option", "key": "id"},
    ],
)
def test_a_reference_names_an_element_and_nothing_more(page_dir, reference):
    """A reference maps its attribute to an empty object, which accepts any element
    id: a role table, an owned target or a keyed member is refused at the registry
    door."""
    registry = vocabulary(page_dir)
    registry["lf-option"]["refers"]["for"] = reference

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found(
        [finding], "invalid-declaration", "<lf-option>", keyword="additionalProperties"
    ), finding


def test_an_asking_instance_needs_the_id_its_declaration_leaves_optional(page_dir):
    """A widget that asks only where an attribute says so may leave `id` out of
    `required`, since an instance that doesn't ask needs none. `page check` refuses an
    instance that asks without one, where it stands."""
    registry = vocabulary(page_dir)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    (widgets / "lf-idless-decision.js").write_text("export function upgrade() {}\n")
    registry["lf-idless-decision"] = {
        "description": "A decision without an address.",
        "attributes": {"properties": {"open": {"type": "boolean"}}},
        "content": "markup",
        "awaits": {
            "when": {"open": [True]},
            "value": "answer",
        },
        "verbs": {"answer": {"detail": {}, "unit": "widget"}},
    }
    declare_vocabulary(page_dir, registry)
    source = page_dir / "index.html"
    authored = source.read_text()

    def check_with(decision: str) -> tuple[int, list]:
        source.write_text(authored.replace("</main>", f"{decision}</main>"))
        return check_findings(page_dir)

    status, findings = check_with("<lf-idless-decision>Shipped.</lf-idless-decision>")
    assert status == 0, findings
    status, findings = check_with("<lf-idless-decision open>Ship?</lf-idless-decision>")
    assert status != 0
    assert found(findings, "needs-id", "<lf-idless-decision>", role="awaits")


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
