"""Data contracts and widget data inputs: what the registry door refuses, run receipts,
and bindings and deferred content across revisions and re-vendors."""

import json
from copy import deepcopy

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_carried_log_record,
    check_findings,
    declare_data_input,
    element_declaration,
    found,
    read_page_data,
    registry_refusal,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import revisioning as revisioning_model
from leaf import thread as thread_model
from leaf.findings import Rejected
from leaf.registry import storage as registry_storage
from leaf.registry import validation as registry_validation
from leaf.structure import SourceDocument
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
                    "schema": {"type": "object"},
                    "records": {"items": "rows", "key": "id", "deferred": "id"},
                }
            },
            "contract-records",
            {"contract": "builds"},
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


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            lambda entry: entry["x-data"]["data"].update(
                {"contract": "missing-contract"}
            ),
            "data-contract",
        ),
        (lambda entry: entry["properties"].pop("source"), "data-source"),
        (
            lambda entry: entry["properties"]["source"].update(
                {"pattern": "^anything$"}
            ),
            "data-source",
        ),
        (lambda entry: entry.update({"x-instructions": ""}), "invalid-extensions"),
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


def test_a_data_source_attribute_can_carry_ordinary_schema_metadata(page_dir):
    """x-data requires the canonical string contract, not one byte-for-byte schema;
    packages remain free to document or further constrain the attribute."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = vocabulary(page_dir)
    registry["lf-test-data"]["properties"]["source"]["description"] = (
        "The page-owned feed id."
    )
    registry["lf-test-data"]["required"].remove("source")

    assert registry_validation.validate_registry(registry, "test registry") is registry


@pytest.mark.parametrize(
    ("change", "code", "values"),
    [
        (
            lambda entry: entry["x-measured"].update({"input": "missing"}),
            "measured-input",
            {"input": "missing"},
        ),
        (
            lambda entry: entry["required"].remove("source"),
            "measured-source",
            {"attr": "source"},
        ),
        (
            lambda entry: entry["required"].remove("run"),
            "measured-run",
            {"attr": "run"},
        ),
        (
            lambda entry: entry["properties"]["run"].pop("minLength"),
            "measured-run",
            {"attr": "run"},
        ),
    ],
)
def test_a_measured_widget_joins_one_data_input_to_one_run_receipt(
    page_dir, change, code, values
):
    """The generic check cannot infer a widget's source or write receipt. Its registry
    declaration names both, and the registry door refuses a half-readable join before
    an authored value can silently miss the freshness advisory."""
    registry = vocabulary(page_dir)
    change(registry["lf-num"])

    finding = registry_refusal(
        lambda: registry_validation.validate_registry(registry, "test registry")
    )
    assert found([finding], code, "<lf-num>", **values)


def test_a_measurement_run_cannot_also_be_replay_writable(page_dir):
    """The run receipt belongs to the authored version. Letting replay write it
    would give the browser a newer freshness boundary than file checks and page state
    read from the immutable document."""
    registry = vocabulary(page_dir)
    widget = registry["lf-num"]
    widget["x-upgrade"] = True
    widget["properties"]["restated"] = {"type": "boolean"}
    widget["x-state"] = {
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
    widget["x-state"] = {
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
    data_model.cmd_data_set(page_dir, "report", "New report.")
    assert files_model.list_revisions(page_dir) == revisions

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    assert data_model.read_contracts(page_dir)["report"] == "text-document"
    assert (
        data_model.read_data(page_dir, registry_storage.load_registry(page_dir))[
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
    data_model.cmd_data_set(page_dir, "report", "Retained report.")
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


def _page_owned_deferred_source(page_dir):
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
        "records": {"items": "files", "key": "key", "deferred": "patch"},
    }
    widget = element_declaration("lf-local-data")
    widget["properties"]["source"] = {
        "type": "string",
        "pattern": "^[a-z][a-z0-9-]*$",
    }
    widget["required"].append("source")
    widget["x-data"] = {"document": {"contract": "local-files", "source": "source"}}
    widget["x-example"] = (
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
    data_model.cmd_data_set(
        page_dir,
        "files",
        {"files": [{"key": "app.py", "patch": "old", "body": "new"}]},
    )
    return authored


def test_a_contracts_item_schema_decides_whether_a_record_has_deferred_content(
    page_dir,
):
    """The item schema owns presence; delivery neither invents nor requires payloads."""
    authored = _page_owned_deferred_source(page_dir)
    with pytest.raises(data_model.DataError, match="'patch' is a required property"):
        data_model.cmd_data_set(
            page_dir,
            "files",
            {"files": [{"key": "metadata", "body": "mode 100644 → 100755"}]},
        )
    declarations = json.loads(authored.read_text())
    contract = declarations["$data"]["contracts"]["local-files"]
    contract["schema"]["properties"]["files"]["items"]["required"] = ["key", "body"]
    authored.write_text(json.dumps(declarations))
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None
    value = {
        "files": [
            {"key": "metadata", "body": "mode 100644 → 100755"},
            {"key": "text", "body": "changed", "patch": "source evidence"},
        ]
    }
    data_model.cmd_data_set(page_dir, "files", value)
    registry = registry_storage.require_registry(page_dir)
    stored = data_model.read_data(page_dir, registry)
    reading = stored["sources"]["files"]
    browser = data_model.browser_data_from(stored, registry)
    assert browser["sources"]["files"]["value"] == {
        "files": [
            value["files"][0],
            {"key": "text", "body": "changed"},
        ]
    }
    assert (
        data_model.deferred_value(
            reading, registry, source="files", revision=reading["revision"], key="text"
        )["value"]
        == "source evidence"
    )
    with pytest.raises(data_model.DataError, match="deferred"):
        data_model.deferred_value(
            reading,
            registry,
            source="files",
            revision=reading["revision"],
            key="metadata",
        )


@pytest.mark.parametrize("change", ["schema", "records", "resources"])
def test_page_owned_data_contracts_can_change_after_publication(page_dir, change):
    """Current declarations can change; old documents retain their captured registry."""
    authored = _page_owned_deferred_source(page_dir)
    old_registry = data_contracts_model.read_revision(
        page_dir, files_model.list_revisions(page_dir)[-1]
    ).registry
    declarations = json.loads(authored.read_text())
    contract = declarations["$data"]["contracts"]["local-files"]
    if change == "records":
        contract["records"]["deferred"] = "body"
    elif change == "resources":
        contract["resources"] = ["optional"]
    else:
        contract["schema"]["properties"]["files"]["minItems"] = 1
    authored.write_text(json.dumps(declarations))

    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None and activation.created
    data_model.cmd_data_set(
        page_dir,
        "files",
        {"files": [{"key": "app.py", "patch": "next", "body": "other"}]},
    )
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    current_registry = registry_storage.require_registry(page_dir)
    current = data_model.read_data(page_dir, current_registry)["sources"]["files"]
    old = data_model.read_data(page_dir, old_registry)["sources"]["files"]
    for registry, reading, field in [
        (old_registry, old, "patch"),
        (current_registry, current, "body" if change == "records" else "patch"),
    ]:
        deferred = data_model.deferred_value(
            reading,
            registry,
            source="files",
            revision=reading["revision"],
            key="app.py",
        )
        assert deferred["value"] == reading["value"]["files"][0][field]


def test_data_binding_inventory_keeps_each_documents_captured_registry(
    page_dir, tmp_path
):
    authored = _page_owned_deferred_source(page_dir)
    declarations = json.loads(authored.read_text())
    inputs = declarations["lf-local-data"]["x-data"]
    inputs["renamed"] = inputs.pop("document")
    authored.write_text(json.dumps(declarations))
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace("</main>", "<p>Next version.</p></main>")
    )
    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None and activation.created
    registry = registry_storage.require_registry(page_dir)
    events = [
        {
            "id": "frozen-feed",
            "revision": 1,
            "markup": '<lf-local-data id="reply-data" source="reply-feed"></lf-local-data>',
        }
    ]

    inventory = data_contracts_model.page_data_binding_inventory(
        page_dir, registry, events
    )
    assert inventory["reply-feed"]["consumers"] == [
        {
            "widget": "reply-data",
            "input": "document",
            "document": "event 'frozen-feed' markup",
        }
    ]
    bootstrap = data_contracts_model.page_data_binding_inventory(
        tmp_path / "bootstrap", registry, [{**events[0], "revision": None}]
    )
    assert bootstrap == {
        "reply-feed": {
            "contract": "local-files",
            "consumers": [
                {
                    "widget": "reply-data",
                    "input": "renamed",
                    "document": "event 'frozen-feed' markup",
                }
            ],
        }
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
    registry["lf-test-other"]["x-data"]["data"]["contract"] = "other-rows"
    declare_vocabulary(page_dir, registry)
    opened = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Show both."}
    )

    with pytest.raises(Rejected) as refused:
        thread_model.post_reply(
            page_dir,
            {"parent": opened["id"], "responds": opened["id"]},
            "Both views of one feed.",
            '<lf-test-data id="rows-view" source="shared"></lf-test-data>'
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
    authored = _page_owned_deferred_source(page_dir)
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
    from leaf.validation.instances import reference_errors, widget_errors

    registry = {
        "lf-producer": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "x-content": "empty",
            "x-output": {"rows": {"contract": "rows"}},
        },
        "lf-consumer": {
            "type": "object",
            "properties": {
                name: {"type": "string"} for name in ("id", "source", "for")
            },
            "x-content": "empty",
            "x-data": {
                "rows": {
                    "contract": "rows",
                    "source": "source",
                    "reference": "for",
                    "output": "rows",
                }
            },
            "x-refers": {"for": {}},
        },
    }

    def errors(binding):
        document = SourceDocument(
            f'<lf-producer id="feed"></lf-producer><lf-consumer id="consumer" {binding}></lf-consumer>'
        )
        records = document.lf_elements
        by_id = {rec["attrs"]["id"]: rec for rec in records}
        return widget_errors(records, registry) + reference_errors(
            records, registry, set(by_id), by_id, thread_ids=set()
        )

    assert errors('for="feed"') == []
    assert errors('source="external"') == []
    assert [finding.code for finding in errors('for="feed" source="external"')] == [
        "ambiguous-data-binding"
    ]
    registry["lf-consumer"]["x-data"]["rows"].pop("source")
    registry["lf-consumer"]["properties"].pop("source")
    assert errors('for="feed"') == []
    registry["lf-producer"]["x-output"]["rows"]["contract"] = "other"
    assert [finding.code for finding in errors('for="feed"')] == ["output-contract"]
    registry["lf-producer"].pop("x-output")
    assert [finding.code for finding in errors('for="feed"')] == ["output-contract"]
