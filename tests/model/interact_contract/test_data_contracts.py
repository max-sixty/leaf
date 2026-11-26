"""Data contracts and widget data inputs: what the registry door refuses, run receipts,
and bindings across revisions and re-vendors."""

import json
from copy import deepcopy

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    ROOT,
    append_carried_log_record,
    bound_twice,
    check_findings,
    command_notes,
    declare_data_input,
    element_declaration,
    found,
    package_findings,
    package_path,
    published,
    read_page_data,
    registry_refusal,
)

from leaf.agents import thread as thread_model
from leaf.base import files as files_model
from leaf.base.findings import Finding, Rejected
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.pages.page import page_instructions
from leaf.records import page_data as page_data_model
from leaf.records import revisioning as revisioning_model
from leaf.records.authored_checks.declarations import declaration_advice
from leaf.source import data as data_model
from leaf.source import revision_artifact as artifact_model
from leaf.source import vocabulary as vocabulary_model
from leaf.source.registry import contract as registry_contract
from leaf.source.registry import validation as registry_validation
from leaf.source.structure import SourceDocument
from model.interact_contract import declare_vocabulary, vocabulary


@pytest.mark.parametrize(
    ("contracts", "code", "values"),
    [
        (
            {"Bad Name": {"description": "x", "schema": {}}},
            "layer-facts",
            {"keyword": "pattern", "path": ["$data", "contracts"]},
        ),
        (
            {"builds": {"schema": {}}},
            "layer-facts",
            {"keyword": "required", "path": ["$data", "contracts", "builds"]},
        ),
        (
            {"builds": {"description": "Build facts.", "schema": {"type": "nope"}}},
            "contract-schema",
            {"contract": "builds"},
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {"$ref": "https://schemas.example/build.json"},
                }
            },
            "contract-reference",
            {"contract": "builds", "reference": "https://schemas.example/build.json"},
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {"$defs": {}, "$ref": "#/$defs/missing"},
                }
            },
            "contract-reference",
            {"contract": "builds", "reference": "#/$defs/missing"},
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {},
                    "resources": "images[].url",
                }
            },
            "layer-facts",
            {"keyword": "type", "path": ["$data", "contracts", "builds", "resources"]},
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {},
                    "resources": ["images["],
                }
            },
            "contract-resource",
            {"contract": "builds", "expression": "images["},
        ),
    ],
)
def test_the_registry_door_validates_data_contracts(page_dir, contracts, code, values):
    """A contract is executable widget vocabulary: its name carries meaning and its
    schema admits bytes to the browser, so package checking refuses an ambiguous name,
    an undocumented contract, or a schema no boundary can run."""
    registry = vocabulary(page_dir)
    registry["$data"]["contracts"] = contracts
    declare_vocabulary(page_dir, registry)

    status, findings = check_findings(page_dir)

    assert status != 0
    assert found(findings, code, **values), findings


def _also_reads_an_output(entry):
    entry["attributes"]["properties"]["for"] = {"type": "string"}
    entry["refers"] = {"for": {}}
    entry["inputs"]["data"].update({"contract": "missing-contract", "reference": "for"})


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            lambda entry: entry["inputs"]["data"].update(
                {"contract": "missing-contract"}
            ),
            "data-contract",
        ),
        # `leaf data set` validates a source's value against the contract, so an input
        # that can bind a source needs it declared whatever else the input can bind.
        (_also_reads_an_output, "data-contract"),
        # `state` is the widget's reading, which Leaf sets on the same element.
        (
            lambda entry: entry["inputs"]["data"].update({"property": "state"}),
            "invalid-declaration",
        ),
        (
            lambda entry: entry.update(
                {
                    "instructions": "",
                }
            ),
            "invalid-declaration",
        ),
    ],
)
def test_a_widget_data_input_is_one_complete_contract(page_dir, change, code):
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = vocabulary(page_dir)
    change(registry["lf-test-data"])

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert (finding.code, finding.at) == (code, "<lf-test-data>")


@pytest.mark.parametrize(
    "change",
    [
        lambda entry: entry["attributes"]["properties"].update({"source": True}),
        lambda entry: entry["attributes"]["properties"].update(
            {"source": {"type": "number"}}
        ),
    ],
)
def test_a_data_source_attribute_not_declared_a_string_is_advice(page_dir, change):
    """A source attribute the declaration gives a schema other than a string's draws
    advice to declare it a string, not a refusal of the declaration."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = vocabulary(page_dir)
    change(registry["lf-test-data"])

    registry_validation.validate_registry(registry, "test registry")
    said = declaration_advice(
        {"lf-test-data": registry["lf-test-data"]}, registry, "test registry"
    )
    assert [(f.code, f.at, f.severity) for f in said] == [
        ("data-source", "<lf-test-data>", "advice")
    ]


def test_a_data_source_attribute_can_carry_ordinary_schema_metadata(page_dir):
    """`inputs` requires the source attribute to be a string, not one byte-for-byte
    schema: a package may describe it or make it optional, and Leaf supplies its
    grammar."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = vocabulary(page_dir)
    registry["lf-test-data"]["attributes"]["properties"]["source"]["description"] = (
        "The page-owned feed id."
    )
    registry["lf-test-data"]["attributes"]["required"].remove("source")

    assert registry_validation.validate_registry(registry, "test registry") is registry


@pytest.mark.parametrize(
    ("change", "code", "values"),
    [
        (
            lambda entry: entry["attributes"]["required"].remove("source"),
            "measured-source",
            {"input": "measurement", "attr": "source"},
        ),
        (
            lambda entry: entry["attributes"]["required"].remove("run"),
            "measured-run",
            {"input": "measurement", "attr": "run"},
        ),
        (
            lambda entry: entry["attributes"]["properties"]["run"].pop("minLength"),
            "measured-run",
            {"input": "measurement", "attr": "run"},
        ),
    ],
)
def test_a_measured_input_joins_its_source_to_one_run_receipt(
    page_dir, change, code, values
):
    """The generic check cannot infer a widget's source or write receipt. Its measured
    input names both, and the registry door advises on a half-readable join, since an
    instance missing either is only never compared with its source's latest run."""
    registry = vocabulary(page_dir)
    change(registry["lf-num"])

    registry_validation.validate_registry(registry, "test registry")
    said = declaration_advice({"lf-num": registry["lf-num"]}, registry, "test registry")
    [advice] = found(said, code, "<lf-num>", **values)
    assert advice.severity == "advice"


@pytest.mark.parametrize("samples", [(), ("practice",)])
def test_an_example_binding_one_source_two_ways_is_invalid(page_dir, samples):
    """An example is read as a page would hold it, the child of each live sample it
    declares included, so its author learns that a page copying it would be refused."""
    registry = vocabulary(page_dir)
    example = bound_twice("shared")
    if samples:
        example = f'<template id="practice" data-sample>{example}</template>'
    registry["lf-num"]["example"] = example

    said = declaration_advice({"lf-num": registry["lf-num"]}, registry, "test registry")
    [advice] = found(said, "invalid-example", "<lf-num>")
    refused = Finding.loads(advice.values["finding"])
    assert (refused.code, refused.samples) == ("contract-conflict", samples)


def test_a_measurement_run_cannot_also_be_replay_writable(page_dir):
    """The run receipt belongs to the authored version. Letting replay write it
    would give the browser a newer freshness boundary than file checks and page state
    read from the immutable document."""
    registry = vocabulary(page_dir)
    widget = registry["lf-num"]
    registry["$modules"]["lf-num"] = "widgets/lf-num.js"
    widget["attributes"]["properties"]["restated"] = {"type": "boolean"}
    widget["verbs"] = {
        "repin": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "run"},
        }
    }

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], "run-written", "<lf-num>", attr="run")


def test_a_data_source_attribute_cannot_also_be_replay_writable(page_dir):
    """The authored document owns a widget's binding for that element lifetime. A
    value record on the same attribute would make replay paint a source that the
    already-mounted watcher correctly does not consume."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = vocabulary(page_dir)
    widget = registry["lf-test-data"]
    widget["verbs"] = {
        "rebind": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "source"},
        }
    }

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], "binding-written", "<lf-test-data>", attrs=["source"])


def test_revendoring_keeps_a_new_binding_before_its_first_revision(page_dir):
    """An edit can bind data before it activates. Re-vendoring compares that same
    working document under both layers, so an unchanged contract is not a loss.
    """
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-text-document id="report" source="report"></lf-text-document></main>',
        )
    )
    revisions = files_model.list_revisions(page_dir)
    page_data_model.cmd_data_set(page_dir, "report", "New report.")
    assert files_model.list_revisions(page_dir) == revisions

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    assert data_model.read_contracts(page_dir)["report"] == "text-document"
    assert (
        data_model.read_data(page_dir, vocabulary_model.load_registry(page_dir))[
            "sources"
        ]["report"]["value"]
        == "New report."
    )


def test_revendoring_an_unreadable_edit_does_not_require_historical_bindings(page_dir):
    """A runtime refresh is independent of an unreadable candidate's source error."""
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-text-document id="report" source="report"></lf-text-document></main>',
        )
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.created
    page_data_model.cmd_data_set(page_dir, "report", "Retained report.")
    revisions = files_model.list_revisions(page_dir)
    source.write_bytes(b"\xff")

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    assert data_model.read_contracts(page_dir)["report"] == "text-document"
    assert read_page_data(page_dir)["sources"]["report"]["value"] == "Retained report."
    assert files_model.list_revisions(page_dir) == revisions
    assert source.read_bytes() == b"\xff"
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [f.code for f in findings] == ["not-utf8"]


def _page_owned_files_source(page_dir):
    schema = {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "patch": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["key", "patch", "body"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["files"],
        "additionalProperties": False,
    }
    contract = {
        "description": "Page-owned file payloads.",
        "schema": schema,
        "records": {"items": "files", "key": "key"},
    }
    widget = element_declaration("lf-local-data")
    widget["attributes"]["properties"]["source"] = {"type": "string"}
    widget["attributes"]["required"].append("source")
    widget["inputs"] = {"document": {"contract": "local-files", "source": "source"}}
    widget["example"] = (
        '<lf-local-data id="example-local-data" source="example"></lf-local-data>'
    )
    authored = page_dir / "page" / "registry.json"
    authored.parent.mkdir(exist_ok=True)
    authored.write_text(
        json.dumps(
            {
                "$data": {"contracts": {"local-files": contract}},
                "lf-local-data": widget,
            }
        )
    )
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</section>",
            '<lf-local-data id="local-data" source="files"></lf-local-data></section>',
        )
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.created
    page_data_model.cmd_data_set(
        page_dir,
        "files",
        {"files": [{"key": "app.py", "patch": "old", "body": "new"}]},
    )
    return authored


@pytest.mark.parametrize("change", ["schema", "records", "resources"])
def test_page_owned_data_contracts_can_change_after_publication(page_dir, change):
    """Current declarations can change; old documents retain their captured registry."""
    authored = _page_owned_files_source(page_dir)
    old_registry = artifact_model.read_revision(
        page_dir, files_model.list_revisions(page_dir)[-1]
    ).registry
    declarations = json.loads(authored.read_text())
    contract = declarations["$data"]["contracts"]["local-files"]
    if change == "records":
        contract["records"]["key"] = "body"
    elif change == "resources":
        contract["resources"] = ["optional"]
    else:
        contract["schema"]["properties"]["files"]["minItems"] = 1
    authored.write_text(json.dumps(declarations))

    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None and activation.created
    value = {"files": [{"key": "app.py", "patch": "next", "body": "other"}]}
    if change == "records":
        # Rows the new key tells apart and the old one doesn't.
        value["files"].append({"key": "app.py", "patch": "next", "body": "more"})
    page_data_model.cmd_data_set(page_dir, "files", value)
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    current = vocabulary_model.require_registry(page_dir)
    assert data_model.read_data(page_dir, current)["sources"]["files"]["value"] == value
    old = data_model.read_data(page_dir, old_registry)["sources"]["files"]
    if change == "records":
        assert 'repeated ["app.py"]' in old["error"]
    else:
        assert old["value"] == value


def test_data_binding_inventory_keeps_each_documents_captured_registry(
    page_dir, tmp_path
):
    authored = _page_owned_files_source(page_dir)
    declarations = json.loads(authored.read_text())
    inputs = declarations["lf-local-data"]["inputs"]
    inputs["renamed"] = inputs.pop("document")
    authored.write_text(json.dumps(declarations))
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace("</main>", "<p>Next version.</p></main>")
    )
    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None and activation.created
    registry = vocabulary_model.require_registry(page_dir)
    events = [
        {
            "id": "feed-reply",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "text": '<lf-local-data id="reply-data" source="reply-feed"></lf-local-data>',
        }
    ]

    inventory = page_data_model.page_data_binding_inventory(page_dir, registry, events)
    assert inventory["reply-feed"]["consumers"] == [
        {
            "widget": "reply-data",
            "input": "document",
            "document": "event 'feed-reply' markup",
        }
    ]
    bootstrap = page_data_model.page_data_binding_inventory(
        tmp_path / "bootstrap", registry, [{**events[0], "revision": None}]
    )
    assert bootstrap == {
        "reply-feed": {
            "contract": "local-files",
            "consumers": [
                {
                    "widget": "reply-data",
                    "input": "renamed",
                    "document": "event 'feed-reply' markup",
                }
            ],
        }
    }


def test_a_message_is_refused_only_for_its_own_bindings(page_dir):
    """A conflicting binding lies within one document, so a message's gate reads the
    message's bindings alone: an unsaved edit that binds one source twice is the
    source check's to refuse, and the agent can still post a message meanwhile."""
    published(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", bound_twice("shared") + "</main>")
    )
    assert found(check_findings(page_dir)[1], "contract-conflict", source="shared")
    message = "The plan:\n\n<p><strong>Flag first</strong></p>"
    command_notes(
        "thread", "create", str(page_dir), "--text", message, "--title", "Plan"
    )
    [posted] = [e for e in events_model.read_events(page_dir) if e["kind"] == "comment"]
    assert posted["text"] == message


def test_a_binding_conflict_names_each_widget_reading_the_source(page_dir):
    """An author finds every consumer of a source bound two ways, so each conflicting
    widget gets its own finding by its id, even where all of them share a line."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            bound_twice("shared")
            + '<lf-text-document id="more" source="shared"></lf-text-document></main>',
        )
    )
    assert [
        (conflict.values["first"]["tag"], conflict.values["then"].get("widget"))
        for conflict in found(check_findings(page_dir)[1], "contract-conflict")
    ] == [("lf-num", "shared-text"), ("lf-num", "more")]


def test_a_sample_checks_the_messages_it_copies_under_its_own_registry(page_dir):
    """A sample's child reads each message it copies from a thread under its own
    registry, the page's current one, whatever the message was posted under. Two
    widgets that shared a contract when the message was posted, and no longer do,
    would bind one source two ways in the child, whose data then can't be read, so
    the sample is refused, naming the copied message."""
    declare_data_input(
        page_dir, "shared", {"type": "array"}, contract="rows", activate=False
    )
    registry = vocabulary(page_dir)
    registry["lf-test-other"] = deepcopy(registry["lf-test-data"])
    registry["$data"]["contracts"]["other-rows"] = deepcopy(
        registry["$data"]["contracts"]["rows"]
    )
    declare_vocabulary(page_dir, registry)
    (page_dir / "index.html").write_text(PAGE)
    assert revisioning_model.activate_source(page_dir).error is None
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "aabb0011",
            "author": "agent",
            "revision": 1,
            "text": "Both views of one feed.\n\n"
            '<lf-test-data id="rows-view" source="shared"></lf-test-data>\n'
            '<lf-test-other id="other-view" source="shared"></lf-test-other>',
        },
    )
    registry["lf-test-other"]["inputs"]["data"]["contract"] = "other-rows"
    declare_vocabulary(page_dir, registry)
    sample = (
        '<template id="practice" data-sample data-sample-threads="aabb0011">'
        "<h1>Child</h1></template>"
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", sample + "</main>"))

    [conflict] = found(check_findings(page_dir)[1], "contract-conflict")
    assert conflict.samples == ("practice",)
    assert conflict.values["then"] == {
        "contract": "other-rows",
        "document": "copied message 'aabb0011'",
        "tag": "lf-test-other",
        "widget": "other-view",
        "input": "data",
        "line": 3,
    }


@pytest.mark.parametrize(
    "publishing",
    [{"validate_source": True}, {"section": "plan"}],
    ids=["check", "move"],
)
def test_a_reply_publishing_saved_edits_checks_its_markup_under_their_registry(
    page_dir, publishing
):
    """A reply that publishes saved edits, whether it checks them first or moves
    its thread onto them, is stored against the revision they make, so its markup is
    checked under that revision's registry. Checked under the active one, a contract
    the edits changed let one fragment bind a source under two contracts, and
    nothing reads it for that again: a conflict lies within one document, so no
    later check rereads the log's fragments."""
    declare_data_input(
        page_dir, "shared", {"type": "array"}, contract="rows", activate=False
    )
    registry = vocabulary(page_dir)
    registry["lf-test-other"] = deepcopy(registry["lf-test-data"])
    registry["$data"]["contracts"]["other-rows"] = deepcopy(
        registry["$data"]["contracts"]["rows"]
    )
    declare_vocabulary(page_dir, registry)
    (page_dir / "index.html").write_text(PAGE)
    assert revisioning_model.activate_source(page_dir).error is None
    # The saved edit moves one widget type to another contract and uses neither.
    registry["lf-test-other"]["inputs"]["data"]["contract"] = "other-rows"
    declare_vocabulary(page_dir, registry)
    opened = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Show both."}
    )

    with pytest.raises(Rejected) as refused:
        thread_model.post_reply(
            page_dir,
            {"parent": opened["id"], "responds": opened["id"]},
            "Both views of one feed.\n\n"
            '<lf-test-data id="rows-view" source="shared"></lf-test-data>\n'
            '<lf-test-other id="other-view" source="shared"></lf-test-other>',
            **publishing,
        )
    assert [finding.code for finding in refused.value.findings] == ["contract-conflict"]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )


@pytest.mark.parametrize("change", ["description", "empty-resources"])
def test_page_owned_data_contract_can_change_without_changing_source_meaning(
    page_dir, change
):
    authored = _page_owned_files_source(page_dir)
    declarations = json.loads(authored.read_text())
    contract = declarations["$data"]["contracts"]["local-files"]
    if change == "description":
        contract["description"] = "A clearer description of the same file payloads."
    else:
        contract["resources"] = []
    authored.write_text(json.dumps(declarations))

    activation = revisioning_model.activate_source(page_dir)

    assert activation.error is None and activation.created


def test_widget_data_inputs_accept_typed_outputs_and_refuse_ambiguous_bindings():
    from leaf.records.markup_checks.instances import reference_errors, widget_errors

    registry = {
        "lf-producer": {
            "attributes": {"properties": {}},
            "content": "empty",
            "outputs": {"rows": {"contract": "rows"}},
        },
        "lf-consumer": {
            "content": "empty",
            "inputs": {
                "rows": {
                    "contract": "rows",
                    "source": "source",
                    "reference": "for",
                }
            },
        },
    }
    # As composing a layer leaves it: the consumer's input names `source` and `for`,
    # which declares each an attribute and `for` an element relation, and every element
    # takes an `id`.
    registry_contract.stamp_grammars(registry_contract.complete_declarations(registry))

    def errors(binding):
        document = SourceDocument(
            '<lf-producer id="feed"></lf-producer><p id="plain">Words</p>'
            f'<lf-consumer id="consumer" {binding}></lf-consumer>'
        )
        records = document.lf_elements
        by_id = {rec["attrs"]["id"]: rec for rec in records}
        return widget_errors(records, registry) + reference_errors(
            records, registry, document.ids, by_id, thread_ids=set()
        )

    assert errors('for="feed"') == []
    assert errors('source="external"') == []
    assert [finding.code for finding in errors('for="feed" source="external"')] == [
        "ambiguous-data-binding"
    ]
    registry["lf-consumer"]["inputs"]["rows"].pop("source")
    assert errors('for="feed"') == []
    # The input reads the one output of its contract, whatever the producer names it.
    registry["lf-producer"]["outputs"]["more"] = {"contract": "other"}
    assert errors('for="feed"') == []
    registry["lf-producer"]["outputs"]["more"]["contract"] = "rows"
    several = errors('for="feed"')
    assert [finding.code for finding in several] == ["output-contract"]
    assert "'rows', 'more'" in str(several[0])
    registry["lf-producer"]["outputs"] = {"rows": {"contract": "other"}}
    assert [finding.code for finding in errors('for="feed"')] == ["output-contract"]
    registry["lf-producer"].pop("outputs")
    assert [finding.code for finding in errors('for="feed"')] == ["output-contract"]
    assert [finding.code for finding in errors('for="plain"')] == ["output-contract"]
    assert [finding.code for finding in errors('for="gone"')] == ["unknown-reference"]


@pytest.mark.parametrize(
    ("declared", "properties", "refers"),
    [
        # Named by the input alone: each is a string attribute, and `for` a relation.
        (
            {},
            {"source": {"type": "string"}, "for": {"type": "string"}},
            {"for": {}},
        ),
        # A schema or a relation the entry writes stands beside what composition writes.
        (
            {
                "attributes": {"properties": {"for": {"minLength": 2}}},
                "refers": {"about": {}},
            },
            {"for": {"minLength": 2}, "source": {"type": "string"}},
            {"about": {}, "for": {}},
        ),
        # An entry that writes the input's attributes out as well declares each once.
        (
            {
                "attributes": {
                    "properties": {"source": {"type": "string"}, "for": True}
                },
                "refers": {"for": {}},
            },
            {"source": {"type": "string"}, "for": True},
            {"for": {}},
        ),
        # A declaration of another shape is left as written, for validation to name.
        ({"attributes": {"properties": ["for"]}, "refers": ["for"]}, ["for"], ["for"]),
        ({"inputs": {"rows": {"contract": "rows", "reference": ["for"]}}}, None, None),
        ({"inputs": ["rows"]}, None, None),
    ],
)
def test_composing_declares_the_attributes_an_input_binds_by(
    declared, properties, refers
):
    entry = {
        "inputs": {"rows": {"contract": "rows", "source": "source", "reference": "for"}}
    } | declared

    composed = registry_contract.complete_declarations({"lf-reader": entry})

    assert composed["lf-reader"]["attributes"].get("properties") == properties
    assert composed["lf-reader"].get("refers") == refers


SHORTLIST, FINALISTS = (
    ROOT / "tests" / "fixtures" / "packages" / name
    for name in ("shortlist", "finalists")
)


def test_a_package_reads_another_packages_output_by_the_contracts_name(
    initialized_page, tmp_path
):
    """The finalists fixture reads a `shortlist` only from the widget its `for` names
    and declares no contract. The shortlist fixture, written apart from it, declares
    the one both name. So the finalists package checks alone, and on a page that
    selects both, `page check` matches the input to the output by that name. The
    contract's instructions reach the reader's author on that page, and a page that
    selects the reader alone returns the reader's own."""
    status, findings = package_findings(FINALISTS)
    assert status == 0, findings

    page_dir = initialized_page(
        tmp_path / "page", (package_path(SHORTLIST), package_path(FINALISTS))
    )

    def checked(target):
        (page_dir / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Final round</title></head>'
            '<body><main><lf-shortlist id="hires"><ul><li><button type="button"'
            ' commandfor="hires" command="--toggle" value="ada">Ada Lovelace</button>'
            '</li></ul></lf-shortlist><p id="plain">No shortlist here.</p>'
            f'<lf-finalists id="finalists" for="{target}"></lf-finalists>'
            "</main></body></html>"
        )
        status, findings = check_findings(page_dir)
        return status, [
            (finding.at, finding.values)
            for finding in found(findings, "output-contract")
        ]

    assert checked("hires") == (0, [])
    assert checked("plain") == (
        1,
        [
            (
                "<lf-finalists>",
                {
                    "line": 1,
                    "input": "shortlist",
                    "target": "plain",
                    "outputs": [],
                    "contract": "shortlist",
                },
            )
        ],
    )

    def audiences(page):
        return set(page_instructions(page, entries=("lf-finalists",)))

    assert audiences(page_dir) == {"author", "producer"}
    alone = initialized_page(tmp_path / "alone", (package_path(FINALISTS),))
    assert audiences(alone) == {"author"}
