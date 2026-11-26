"""Event, registry, replay-contract, and media tests."""

import json
import re

import pytest
import tinycss2
import tinycss2.parser
from click.testing import CliRunner
from interact_support import (
    PAGE,
    PAGE_GROUP,
    append_carried_log_record,
    assert_revendor_serializes_writer,
    check,
    check_findings,
    declare_data_input,
    declare_on_page,
    element_declaration,
    fetch,
    found,
    page_packages,
    publish,
    read_page_data,
)
from model.interact_contract import _value_verb

from leaf.agents import thread as thread_model
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import page_data as page_data_model
from leaf.records import revisioning as revisioning_model
from leaf.source import data as data_model
from leaf.source import data_contracts as data_contracts_model
from leaf.source import revision_artifact as artifact_model
from leaf.source import structure as structure_model
from leaf.source import vocabulary as vocabulary_model
from leaf_dev.page_fixtures import package_selection_args


def test_revendoring_serializes_with_thread_markup_entering_the_log(
    page_dir, monkeypatch
):
    # The re-selection the writer races adds an empty project package.
    (page_dir.parent / ".leaf").mkdir()
    local = element_declaration("lf-local-thread")
    declare_on_page(
        page_dir, lambda registry: registry.__setitem__("lf-local-thread", local)
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    markup = '<lf-local-thread id="thread-local">Choose locally.</lf-local-thread>'
    _, refusal = assert_revendor_serializes_writer(
        page_dir,
        monkeypatch,
        "reply",
        lambda: thread_model.post_reply(
            page_dir, {"responds": "c1"}, "Pick one:" + "\n\n" + markup
        ),
    )

    assert refusal is None


@pytest.mark.parametrize(
    "schema",
    [
        {"const": {"$ref": "https://example.invalid/literal-value"}},
        {
            "$defs": {"row": {"type": "string"}},
            "type": "array",
            "items": {"$ref": "#/$defs/row"},
        },
    ],
)
def test_package_data_schema_allows_literal_refs_and_resolved_local_refs(
    page_dir, schema
):
    declare_on_page(
        page_dir,
        lambda registry: registry["$data"]["contracts"].update(
            builds={"description": "Build facts.", "schema": schema}
        ),
    )

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_revendoring_can_drop_a_historical_data_binding(page_dir):
    """Incoming layers are not constrained by old bindings, even with a live value."""
    declare_data_input(
        page_dir, "builds", {"type": "array"}, contract="builds", activate=False
    )
    # A project package declares the contract and its widget, so a selection
    # without the package drops them.
    package = page_dir.parent / ".leaf"
    package.mkdir()
    (page_dir / "page" / "registry.json").rename(package / "registry.json")
    vendoring_model.cmd_init(page_dir, (*page_packages(), "./.leaf"))
    # Revision 1 is the document read under the package's binding.
    assert revisioning_model.activate_source(page_dir).error is None
    page_data_model.cmd_data_set(page_dir, "builds", [])

    refreshed = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", *package_selection_args(page_packages()), str(page_dir)],
    )

    assert refreshed.exit_code == 0, refreshed.output
    historical = artifact_model.read_revision(page_dir, 1).registry
    assert (
        data_model.read_data(page_dir, historical)["sources"]["builds"]["value"] == []
    )
    current = read_page_data(page_dir)["sources"]["builds"]
    assert "error" in current and "value" not in current
    page_data_model.cmd_data_clear(page_dir, "builds")
    refreshed = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert refreshed.exit_code == 0, refreshed.output


@pytest.mark.parametrize(("subschema", "exit_code"), [(True, 0), (False, 1)])
def test_boolean_attribute_subschemas_validate_without_crashing(
    page_dir, subschema, exit_code
):
    declare_on_page(
        page_dir,
        lambda registry: registry["lf-options"]["attributes"]["properties"].update(
            pinned=subschema
        ),
    )
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(PAGE_GROUP, '<lf-options id="opts" pinned>')
    )

    result = check(page_dir)
    assert result.exit_code == exit_code, result.output
    assert not isinstance(result.exception, AttributeError)
    if subschema is False:
        assert "schema does not allow" in result.output, result.output
        assert "None" not in result.output


def test_physical_record_slots_remain_local_to_the_coordinate(page_dir):

    def owned(registry):
        # A different host attribute is a different value slot on the same unit.
        task = registry["lf-test-task"]
        owner = json.loads(json.dumps(task["verbs"]["status"]))
        owner["record"] = {"kind": "value", "attr": "owner"}
        task["attributes"]["properties"]["owner"] = {"type": "string"}
        task["attributes"].setdefault("required", []).append("owner")
        task["verbs"]["owner"] = owner

    declare_on_page(page_dir, owned)

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_withdrawal_may_name_an_outcome_that_retires_no_slots(trial_page):

    def withdraws(outcome):
        declare_on_page(
            trial_page,
            lambda registry: registry["lf-trial"]["verbs"]["decide"].update(
                {"withdraws": outcome}
            ),
        )

    withdraws("pause")
    result = check(trial_page)
    assert result.exit_code == 0, result.output
    withdraws("missing")
    status, findings = check_findings(trial_page)
    assert status != 0
    assert found(findings, "withdraws-outcome", "<lf-trial>", outcome="missing")


@pytest.mark.parametrize("arrangement", ["own-verb", "recording-column-value"])
def test_the_widget_that_records_a_parts_position_is_the_one_that_places_it(
    server, page_dir, arrangement
):
    """A card's place belongs to the nearest ancestor recording that position slot.

    Scalar records on the card or its column coexist with the board's position
    record. A nearer widget recording the same slot takes it from the board
    (`test_nested_member_records_refuse_foreign_selection_and_position`)."""
    card_verbs = {"flag": _value_verb("flag")}
    recorders = {"lf-card": ("flag", card_verbs)}
    if arrangement.startswith("recording-column"):
        recorders["lf-column"] = ("tint", {"tint": _value_verb("tint")})
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)

    def record(registry):
        registry["lf-column"]["attributes"]["properties"]["tint"] = {"type": "string"}
        for tag, (attr, verbs) in recorders.items():
            entry = registry[tag]
            entry["attributes"]["properties"] |= {
                attr: {"type": "string"},
            }
            entry["verbs"] = verbs
            (widgets / f"{tag}.js").write_text("export default class {}\n")

    declare_on_page(page_dir, record)
    result = check(page_dir)
    assert result.exit_code == 0, result.output

    board = (
        '<lf-board id="board"><lf-column id="todo" label="To do" tint="plain">'
        '<lf-card id="card" flag="no">Card</lf-card></lf-column>'
        '<lf-column id="done" label="Done" tint="plain"></lf-column></lf-board>'
    )
    html = re.sub(r"<main>.*?</main>", f"<main>{board}</main>", PAGE, flags=re.DOTALL)
    (page_dir / "index.html").write_text(html)
    publish(page_dir)
    revision = events_model.read_events(page_dir)[-1]["revision"]

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": revision,
                "widget": "board",
                "action": "move",
                "detail": {"unit": "card", "value": "done", "rank": "0i"},
            }
        ).encode(),
    )
    assert status == 200, body


def test_check_names_a_media_reference_the_directory_cannot_answer(page_dir):
    """A broken image is silent in the file and obvious on the page. The render gate
    would see the 404, but it runs once; this runs on every version, and whether a
    file is there is as deterministic as whether an id is."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p><img alt="x" src="/media/deadbeefdeadbeef.png"></p>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "missing-media", ref="/media/deadbeefdeadbeef.png")

    # A mention is not a reference: a page explaining leaf writes one of these
    # paths in its prose, and reading the markup rather than the attributes would
    # send its author hunting for a screenshot the page never asks for.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p>Write it as <code>"/media/deadbeefdeadbeef.png"</code>.</p>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_sample_body_declarations_use_the_child_document_boundary(page_dir):
    """A practice page selects its own mode; invalid values stay child diagnostics."""
    for declarations, valid, mode in (
        ('data-annotations="page" data-rail="none"', True, "page"),
        ("", True, "overlay"),
        ('data-annotations="unknown"', False, None),
    ):
        source = PAGE.replace(
            "</main>",
            f'<template id="practice" data-sample {declarations}>'
            "<h1>Child page</h1></template></main>",
        )
        (page_dir / "index.html").write_text(source)
        parser = structure_model.SourceDocument(source)
        [sample] = parser.samples
        status, findings = check_findings(page_dir)
        if valid:
            assert status == 0, findings
            assert structure_model.annotation_mode(sample["document"]) == mode
            assert structure_model.annotation_mode(parser) == "overlay"
        else:
            assert status == 1
            assert [(f.code, f.samples, f.values["value"]) for f in findings] == [
                ("allocation-value", ("practice",), "unknown")
            ]


def test_check_keeps_parent_and_sibling_sample_ids_independent(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            '<p id="shared">Parent</p>'
            '<template id="first" data-sample><h1 id="shared">First</h1></template>'
            '<template id="second" data-sample><h1 id="shared">Second</h1></template></main>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_sample_data_bindings_use_copied_data_but_not_parent_history(page_dir):
    declare_data_input(
        page_dir, "shared", {"type": "string"}, contract="parent", tag="lf-parent-data"
    )
    source = (page_dir / "index.html").read_text()
    declare_data_input(
        page_dir,
        "shared",
        {"type": "number"},
        contract="child",
        tag="lf-child-data",
        activate=False,
    )
    child = '<lf-child-data id="test-data" source="shared"></lf-child-data>'
    markup = source.replace(
        "</main>", f'<template id="practice" data-sample>{child}</template></main>'
    )
    (page_dir / "index.html").write_text(markup)
    result = check(page_dir)
    assert result.exit_code == 0, result.output

    # A child may rebind the copied source. An incompatible current value is an
    # error under its declaration, never passed off as a valid child payload.
    page_data_model.cmd_data_set(page_dir, "shared", "parent value")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    registry = vocabulary_model.require_registry(page_dir)
    source_record = data_model.read_source(page_dir, "shared", registry)
    assert source_record is not None
    value = source_record["value"]
    assert data_contracts_model.payload_error("shared", "child", value, registry)
    assert data_model.read_contracts(page_dir)["shared"] == "parent"


# Selection alone decides: a thread the log holds is out of reach unless selected,
# a selected one need not be held, and a nested sample reads the same way.
@pytest.mark.parametrize(
    ("seeded", "available", "nested"),
    [
        (False, True, False),
        (True, False, False),
        (False, True, True),
        (True, False, True),
    ],
)
def test_sample_references_see_only_selected_threads(
    page_dir, seeded, available, nested
):
    if available:
        append_carried_log_record(
            page_dir,
            {
                "kind": "comment",
                "id": "aabb0011",
                "author": "user",
                "text": "A question",
            },
        )
    selection = ' data-sample-threads="aabb0011"' if seeded else ""
    child = '<lf-suggestion id="answer" resolves="aabb0011"><lf-new>Answer</lf-new></lf-suggestion>'
    if nested:
        child = f'<template id="nested" data-sample{selection}>{child}</template>'
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            f'<template id="practice" data-sample{selection}>{child}</template></main>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0, findings
    if not seeded:
        samples = ("practice", "nested") if nested else ("practice",)
        assert [(f.code, f.samples) for f in findings] == [("unknown-thread", samples)]


def test_check_tokenizes_only_the_page_stylesheet(page_dir, monkeypatch):
    """A version's CSS is what its <style> blocks and style="" attributes hold.
    Reading the whole file as one stylesheet made a megabyte of base64 (one
    screenshot as a data: URI) into CSS to tokenize, and the hand-written rule
    scanner that read it backtracked quadratically across the long brace-free run,
    which took the better part of an hour. tinycss2 now owns the CSS grammar and
    its linear cost, so what leaf owns is what it hands the tokenizer: every string
    any check stage tokenizes is recorded, and none may carry the data URI."""
    blob = "A" * 1_000_000
    html = PAGE.replace(
        "<h2>Plan</h2>",
        f'<h2>Plan</h2><p style="color: rebeccapurple"><img alt="shot" '
        f'src="data:image/png;base64,{blob}"></p>',
    )
    (page_dir / "index.html").write_text(html)
    tokenized = []
    tokenize = tinycss2.parse_component_value_list

    def recording(css, *args, **kwargs):
        tokenized.append(css)
        return tokenize(css, *args, **kwargs)

    # Every tinycss2 entry point tokenizes a string through this one function.
    monkeypatch.setattr(tinycss2.parser, "parse_component_value_list", recording)
    monkeypatch.setattr(tinycss2, "parse_component_value_list", recording)

    assert check(page_dir).exit_code == 0
    assert "color: rebeccapurple" in tokenized
    assert not [len(css) for css in tokenized if blob in css]


def test_sample_fixture_accepts_native_message_markup(page_dir):
    history = json.dumps(
        [
            {
                "kind": "comment",
                "id": "aabb0011",
                "author": "agent",
                "text": 'Results:\n\n<table id="results"><tr><td>Passed</td></tr></table>',
            },
            {
                "kind": "reply",
                "parent": "aabb0011",
                "author": "agent",
                "revision": 1,
                "text": 'Log:\n\n<pre id="log">Ready\nDone</pre>',
            },
        ]
    )
    source = (
        f'<script id="fixture" type="application/json">{history}</script>'
        '<template id="practice" data-sample data-sample-events="fixture">'
        '<h1 id="child">Child</h1></template>'
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", source + "</main>"))
    result = check(page_dir)
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("anchor", "valid", "complaint"),
    [
        ({"section": "outer-only"}, False, "no element id 'outer-only'"),
        (
            {"section": "child", "quote": "Words only in the parent"},
            True,
            "finds 'Words only in the parent' nowhere in § child",
        ),
        ({"section": "child", "quote": "Child passage"}, True, ""),
        ({"section": "generated-option", "quote": "Generated passage"}, True, ""),
        ({"section": "message-widget"}, True, ""),
        (None, True, ""),
    ],
)
def test_sample_fixture_anchors_are_captured_in_the_child_reading(
    page_dir, anchor, valid, complaint
):
    history = [
        {
            "kind": "comment",
            "author": "agent",
            "text": "A widget example\n\n"
            '<lf-group id="message-ask" label="Route">\n<h2 id="message-ask-h">Route</h2><lf-options id="message-widget"><lf-option id="message-option">Existing</lf-option></lf-options></lf-group>',
        },
        {
            "kind": "comment",
            "text": "A fixture question",
            **({"anchor": anchor} if anchor is not None else {}),
        },
    ]
    if anchor and anchor.get("section") == "generated-option":
        history.insert(
            1,
            {
                "kind": "action",
                "widget": "message-widget",
                "action": "add",
                "detail": {"option": "generated-option", "text": "Generated passage"},
            },
        )
    source = (
        '<p id="outer-only">Words only in the parent</p>'
        f'<script id="fixture" type="application/json">{json.dumps(history)}</script>'
        '<template id="practice" data-sample data-sample-events="fixture">'
        '<h1>Sample</h1><p id="child">Child passage</p></template>'
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", source + "</main>"))
    result = check(page_dir)
    assert (result.exit_code == 0) == valid, result.output
    if not valid:
        assert "sample 'practice'" in result.output
    assert complaint in result.output
