"""Event, registry, replay-contract, and media tests."""

import json
import re
import shutil

import pytest
import tinycss2
import tinycss2.parser
from click.testing import CliRunner
from interact_support import (
    ADOPTED,
    COMMAND_HUB_PACKAGE,
    PAGE,
    PILOT_PURGE,
    SHELVED,
    TRIAL_CACHE,
    TRIAL_LOG,
    append_carried_log_record,
    assert_revendor_serializes_writer,
    check,
    check_findings,
    decide,
    declare_data_input,
    element_declaration,
    fetch,
    found,
    live_versions,
    page_packages,
    publish,
    read_page_data,
    stamp,
    trial_version,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import event_log as events_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.registry import storage as registry_storage
from model.test_interact_contract import _value_verb


def test_revendoring_serializes_with_thread_markup_entering_the_log(
    page_dir, monkeypatch
):
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    local = element_declaration("lf-local-thread")
    (overlay / "registry.json").write_text(json.dumps({"lf-local-thread": local}))
    vendoring_model.cmd_init(page_dir, selected=(*page_packages(), "./.leaf"))
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    (overlay / "registry.json").unlink()
    markup = '<lf-local-thread id="thread-local">Choose locally.</lf-local-thread>'
    _, refusal = assert_revendor_serializes_writer(
        page_dir,
        monkeypatch,
        "reply",
        lambda: thread_model.post_reply(
            page_dir, {"to": "c1", "for": "c1"}, "Pick one:", markup
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
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$data"]["contracts"]["builds"] = {
        "description": "Build facts.",
        "schema": schema,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_revendoring_can_drop_a_historical_data_binding(page_dir):
    """Incoming layers are not constrained by old bindings, even with a live value."""
    declare_data_input(page_dir, "builds", {"type": "array"}, contract="builds")
    data_model.cmd_data_set(page_dir, "builds", [])

    refreshed = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert refreshed.exit_code == 0, refreshed.output
    historical = data_contracts_model.read_revision(page_dir, 1).registry
    assert (
        data_model.read_data(page_dir, historical)["sources"]["builds"]["value"] == []
    )
    current = read_page_data(page_dir)["sources"]["builds"]
    assert "error" in current and "value" not in current
    data_model.cmd_data_clear(page_dir, "builds")
    refreshed = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert refreshed.exit_code == 0, refreshed.output


def test_space_capacity_is_independent_of_the_widgets_internal_layout(page_dir):
    """A capacity declaration says how much room core grants. It does not constrain the
    package's internal layout, including whether the widget also renders an attribute."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-board"]["properties"]["caption"] = {"type": "string"}
    registry["lf-board"]["x-says"] = {"caption": "before"}
    registry["lf-board"]["x-space"] = "available"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(("subschema", "exit_code"), [(True, 0), (False, 1)])
def test_boolean_attribute_subschemas_validate_without_crashing(
    page_dir, subschema, exit_code
):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["properties"]["choose"] = subschema
    (page_dir / "registry.json").write_text(json.dumps(registry))
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("<lf-options>", '<lf-options id="opts" choose>')
    )

    result = check(page_dir)
    assert result.exit_code == exit_code, result.output
    assert not isinstance(result.exception, AttributeError)
    if subschema is False:
        assert "schema does not allow" in result.output, result.output
        assert "None" not in result.output


def test_physical_record_slots_remain_local_to_the_coordinate(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())

    # A different host attribute is a different value slot on the same unit.
    task = registry["lf-test-task"]
    owner = json.loads(json.dumps(task["x-state"]["status"]))
    owner["record"] = {"kind": "value", "attr": "owner"}
    task["properties"]["owner"] = {"type": "string"}
    task.setdefault("required", []).append("owner")
    task["x-state"]["owner"] = owner

    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_custom_retirement_holders_can_be_revised_without_an_answer(trial_page):
    """The same free editing applies to a layer's own outcome widgets."""
    for source in (
        trial_version(ADOPTED, TRIAL_LOG, PILOT_PURGE),
        trial_version(TRIAL_CACHE, SHELVED, PILOT_PURGE),
        trial_version(TRIAL_CACHE, PILOT_PURGE),
        trial_version(TRIAL_CACHE, TRIAL_LOG),
    ):
        (trial_page / "index.html").write_text(source)
        revised = check(trial_page)
        assert revised.exit_code == 0, revised.output
    decide(trial_page, "shelve", widget="pilot-purge")
    honored = stamp(trial_page, "answered")
    assert honored.exit_code == 0, honored.output
    assert live_versions(trial_page) == [1, 2]


def test_withdrawal_may_name_an_outcome_that_retires_no_slots(trial_page):
    registry = json.loads((trial_page / "registry.json").read_text())
    registry["lf-trial"]["x-withdrawn-as"] = "pause"
    (trial_page / "registry.json").write_text(json.dumps(registry))
    result = check(trial_page)
    assert result.exit_code == 0, result.output
    registry["lf-trial"]["x-withdrawn-as"] = "missing"
    (trial_page / "registry.json").write_text(json.dumps(registry))
    invalid = check(trial_page)
    assert invalid.exit_code != 0
    assert "not a deciding outcome" in invalid.output


@pytest.mark.parametrize(
    ("arrangement", "refusal"),
    [
        ("own-verb", None),
        ("recording-column", "'card' is not owned by action widget 'board'"),
    ],
)
def test_the_widget_that_records_a_parts_position_is_the_one_that_places_it(
    server, page_dir, arrangement, refusal
):
    """A card has one place and the nearest recording widget above it records it. A
    verb the card records of its own is a coordinate of the card's, so the board still
    moves it. A column that records stands between the board and the card."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-column"]["properties"]["tint"] = {"type": "string"}
    card_verbs = {"flag": _value_verb("flag")}
    recorders = {"lf-card": ("flag", card_verbs)}
    if arrangement == "recording-column":
        recorders["lf-column"] = ("tint", {"tint": _value_verb("tint")})
    for tag, (attr, verbs) in recorders.items():
        entry = registry[tag]
        entry["properties"] |= {
            attr: {"type": "string"},
            "restated": {"type": "boolean"},
        }
        entry["required"] = sorted({*entry["required"], attr})
        entry["x-state"] = verbs
        entry["x-upgrade"] = True
        (page_dir / "widgets" / f"{tag}.js").write_text("export default class {}\n")
    (page_dir / "registry.json").write_text(json.dumps(registry))
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
    if refusal is None:
        assert status == 200, body
    else:
        assert status == 400, body
        assert refusal in json.loads(body)["error"]


def test_a_widget_nobody_has_touched_is_not_the_gate_s_business(page_dir):
    """The gate is about decisions, so it holds nothing against a version that
    rewrites a widget the user never acted on."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>First words.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>Quite different words.</pre></lf-draft>',
        )
    )
    assert check(page_dir).exit_code == 0


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
    data_model.cmd_data_set(page_dir, "shared", "parent value")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    registry = registry_storage.require_registry(page_dir)
    reading = data_model.read_source(page_dir, "shared", "child", registry)
    assert "error" in reading and "value" not in reading
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
    assert (status == 0) == seeded, findings
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


def test_init_allows_to_drop_the_contract_of_a_held_comment(page_dir):
    """A hold is recorded against the declaration that admitted it."""
    package = page_dir.parent / "mutable-command-hub"
    shutil.copytree(COMMAND_HUB_PACKAGE, package)
    selected = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "./mutable-command-hub", str(page_dir)],
    )
    assert selected.exit_code == 0, selected.output
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace(
            "</section>",
            '<lf-test-tasks id="work"><lf-test-task id="goal" status="active" talk>'
            "<strong>Goal</strong></lf-test-task></lf-test-tasks></section>",
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Pause after this pass.",
            "anchor": {"section": "goal"},
            "holds": "goal",
        },
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    del registry["lf-test-task"]["x-thread-seat"]["hold"]
    registry_path.write_text(json.dumps(registry))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_sample_fixture_accepts_native_message_markup(page_dir):
    history = json.dumps(
        [
            {
                "kind": "comment",
                "id": "aabb0011",
                "author": "agent",
                "text": "Results:",
                "markup": '<table id="results"><tr><td>Passed</td></tr></table>',
            },
            {
                "kind": "reply",
                "parent": "aabb0011",
                "author": "agent",
                "text": "Log:",
                "markup": '<pre id="log">Ready\nDone</pre>',
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
            False,
            "doesn't say",
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
            "text": "A widget example",
            "markup": '<lf-ask id="message-ask"><h2>Route</h2><lf-options id="message-widget" choose><lf-option id="message-option">Existing</lf-option></lf-options></lf-ask>',
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
