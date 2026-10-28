"""What `page init` lets a re-vendor change under a logged page, and how it serializes
with previews, browser actions and worker reports."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    FLOW_PAGE,
    PAGE,
    _tasks_version,
    append_carried_log_record,
    append_command,
    assert_revendor_serializes_writer,
    comment,
    delivered,
    element_declaration,
    fetch,
    page_packages,
    publish,
    serving,
)
from leaf_dev.page_fixtures import package_selection_args

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import reports as reports_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.page_snapshot import capture_page_snapshot
from leaf.registry import storage as registry_storage
from leaf.render_gate import preview as render_gate_model
from model.interact_contract import _stateful_page_declaration, vocabulary


def test_init_allows_a_log_the_incoming_layer_no_longer_speaks(page_dir):
    """Retiring a verb leaves its original events intact in the append-only log."""
    # This models a page made under an older registry where lf-draft declared
    # `decide`: the tag and widget id survive, but the incoming verb does not.
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>A decision.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "d1",
            "action": "decide",
            "detail": {"decision": "approved"},
            "meaning": {
                "scope": "page",
                "unit": "d1",
                "depends": ["d1"],
                "answer": None,
            },
        },
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_init_allows_a_log_holding_a_token_the_incoming_layer_dropped(
    page_dir, monkeypatch
):
    """Removing a reaction token leaves its recorded gestures in history."""
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)]).exit_code
        == 0
    )
    layer = page_dir.parent / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(
        json.dumps({"$reactions": {"tokens": {"shorten": None}}})
    )
    monkeypatch.chdir(page_dir.parent)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_init_revendors_over_a_record_the_running_contract_would_not_admit(
    page_dir,
):
    """A record shape is not a gap re-vendoring creates, unlike the dropped token and
    retired verb above: admission is the schema's only reader, and the logged event
    replays the same either way."""
    publish(page_dir)
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "mood": "uncertain",
            "revision": 1,
            "text": "Does this still mean anything?",
        },
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    after = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), comment["id"]]
    )
    assert after.exit_code == 0, after.output
    assert "Does this still mean anything?" in after.output


def test_init_allows_retiring_a_logged_widgets_verb(page_dir):
    """A layer can remove one widget's verb while keeping another's same-named verb."""
    registry = vocabulary(page_dir)
    board = registry["lf-board"]["x-example"]
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
        },
    )

    move_spec = registry["lf-board"]["x-state"]["move"]
    board_entry = registry["lf-board"]
    board_entry.pop("x-state")
    # Reusing the generic verb on another widget leaves the global verb set
    # unchanged, but cannot make an old lf-board action meaningful there.
    registry["lf-draft"]["x-state"]["move"] = move_spec
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "lf-board": board_entry,
                "lf-draft": registry["lf-draft"],
            }
        )
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_init_allows_a_destination_schema_that_rejects_recorded_values(page_dir):
    """Re-vendoring allows a new payload domain without rewriting old events."""
    declaration = _stateful_page_declaration(page_dir)
    authored = page_dir / "page" / "registry.json"
    authored.write_text(json.dumps({"lf-local": declaration}))
    source = PAGE.replace(
        "</section>", '<lf-local id="local-choice" value="a">Local</lf-local></section>'
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "first"},
        },
    )
    declaration["properties"]["value"]["maxLength"] = 1
    authored.write_text(json.dumps({"lf-local": declaration}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


@pytest.mark.parametrize("mutation", ["drop", "words", "child"])
def test_init_allows_changed_generated_child_semantics(page_dir, mutation):
    registry = vocabulary(page_dir)
    options = (
        '<lf-ask id="route-decision"><h2>Which route?</h2>'
        '<lf-options id="route" choose>'
        '<lf-option id="route-authored">Authored route</lf-option>'
        "</lf-options></lf-ask>"
    )
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", options + "</section>")
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "route",
            "action": "add",
            "detail": {"option": "route-user", "text": "User route"},
        },
    )

    add = registry["lf-options"]["x-state"]["add"]
    overlay_entries = {"lf-options": registry["lf-options"]}
    if mutation == "drop":
        del add["creates"]
    elif mutation == "words":
        add["creates"]["words"] = "words"
        fields = add["detail"]["properties"]
        fields["words"] = fields.pop("text")
        add["detail"]["required"] = ["option", "words"]
    else:
        registry["lf-option-alt"] = registry["lf-option"]
        add["creates"]["child"] = "lf-option-alt"
        overlay_entries["lf-option-alt"] = registry["lf-option-alt"]
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text(json.dumps(overlay_entries))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_init_allows_a_logged_report_the_incoming_layer_no_longer_speaks(page_dir):
    """An agent verb can be retired while its original reports stay in the log."""
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "</section>",
            '<lf-test-tasks id="tree"><lf-test-task id="t1" status="active">'
            "<strong>Parse</strong></lf-test-task></lf-test-tasks></section>",
        )
    )
    publish(page_dir)
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            ["page", "report", str(page_dir), "t1", "status", "value=done"],
        )
        .exit_code
        == 0
    )

    registry = vocabulary(page_dir)
    task = registry["lf-test-task"]
    task.pop("x-state")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-test-task": task}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_init_allows_to_orphan_a_logged_visual_anchor(page_dir):
    """A provider can remove a visual target without deleting its original comment."""
    (page_dir / "index.html").write_text(
        FLOW_PAGE.replace(
            '<lf-diagram id="flow">',
            '<lf-diagram id="flow" parts="all">',
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "flow", "visual": "node:A"},
            "text": "keep this target",
        },
    )

    registry = vocabulary(page_dir)
    diagram = registry["lf-diagram"]
    diagram.pop("x-visual")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-diagram": diagram}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


@pytest.mark.parametrize("valid_source", [True, False])
def test_revendoring_activates_current_delivery_handling_only_for_valid_source(
    page_dir, capsys, valid_source
):
    """A re-vendor to another selection replaces the active revision's vocabulary
    before a wait can deliver again, without an intervening state read or markup
    edit. The composed package clauses survive; invalid source keeps the last good
    revision, read under the selection it captured, and reports why."""
    package = page_dir.parent / ".leaf"
    package.mkdir()
    package_handling = "Keep the package's authored comment instructions."
    (package / "registry.json").write_text(
        json.dumps({"$events": {"handling": {"comment": [{"text": package_handling}]}}})
    )
    vendoring_model.cmd_init(page_dir, selected=(*page_packages(), "./.leaf"))
    reply = registry_storage.load_registry(page_dir)["$events"]["answering"]["reply"]
    older = reply[0]["text"]
    current = "Answer with the newer package's leaf thread reply command."
    revised = page_dir.parent / ".revised"
    revised.mkdir()
    (revised / "registry.json").write_text(
        json.dumps(
            {
                "$events": {
                    "answering": {"reply": [{**reply[0], "text": current}, *reply[1:]]}
                }
            }
        )
    )
    captured = revisioning_model.activate_source(page_dir)
    assert captured.error is None
    source = page_dir / "index.html"
    if not valid_source:
        source.write_text(
            source.read_text().replace("</main>", '<p id="plan">Duplicate</p></main>')
        )
    unchanged_markup = source.read_bytes()

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf", "./.revised")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert source.read_bytes() == unchanged_markup
    assert ("unready-reinit" in result.output) is not valid_source
    capsys.readouterr()
    serving(page_dir, 1)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    assert service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, batch, _ = delivered(capsys)
    clauses = list(batch["handling"].values())
    assert package_handling in clauses
    assert (current if valid_source else older) in clauses
    assert (older if valid_source else current) not in clauses


def test_a_preview_keeps_its_contract_while_revendoring_completes(page_dir):
    before = registry_storage.layer_metadata(page_dir)["generation"]
    snapshot = capture_page_snapshot(
        page_dir,
        structure_model.SourceDocument((page_dir / "index.html").read_text()),
        1,
        url="/",
    )
    with render_gate_model.preview_server(page_dir, snapshot) as url:
        status, captured = fetch(url, token=None)
        assert status == 200
        vendoring_model.cmd_init(page_dir, page_packages()[:-1])
        assert registry_storage.layer_metadata(page_dir)["generation"] != before
        assert fetch(url, token=None) == (200, captured)
    assert snapshot.context.registry["$layer"]["generation"] == before


def test_revendoring_serializes_with_a_browser_action_entering_the_log(
    page_dir, server, monkeypatch
):
    registry = vocabulary(page_dir)
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "</section>", registry["lf-board"]["x-example"] + "\n</section>"
        )
    )
    publish(page_dir)
    board = registry["lf-board"]
    board["x-state"]["move"]["record"]["within"] = "lf-options"
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-board": board}))
    action = json.dumps(
        {
            "kind": "action",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
        }
    ).encode()
    (status, body), refusal = assert_revendor_serializes_writer(
        page_dir, monkeypatch, "action", lambda: fetch(f"{server}/api/event", action)
    )

    assert status == 200, body
    assert refusal is None


def test_revendoring_serializes_with_a_worker_report_entering_the_log(
    page_dir, monkeypatch
):
    _tasks_version(page_dir, "active")
    publish(page_dir)
    registry = vocabulary(page_dir)
    task = registry["lf-test-task"]
    task.pop("x-state")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-test-task": task}))
    _, refusal = assert_revendor_serializes_writer(
        page_dir,
        monkeypatch,
        "report",
        lambda: reports_model.cmd_report(
            page_dir, "t-parser", "status", ("value=review",)
        ),
    )

    assert refusal is None
    assert events_model.read_events(page_dir)[-1]["kind"] == "report"
    assert "x-state" not in registry_storage.load_registry(page_dir)["lf-test-task"]


@pytest.mark.parametrize("in_sample", [False, True])
def test_message_markup_uses_the_current_layer(page_dir, in_sample):
    """Current markup admission does not inventory old document vocabularies."""
    publish(page_dir)
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    local = element_declaration("lf-local-thread")
    (overlay / "registry.json").write_text(json.dumps({"lf-local-thread": local}))
    vendoring_model.cmd_init(page_dir, selected=(*page_packages(), "./.leaf"))
    publish(page_dir)
    markup = '<lf-local-thread id="local">Choose locally.</lf-local-thread>'
    if in_sample:
        markup = f'<template id="practice" data-sample>{markup}</template>'
    result = comment(page_dir, "--text", "Try it:", "--markup", markup)
    assert result.exit_code == 0, result.output
    assert events_model.read_events(page_dir)[-1]["markup"] == markup


def test_revendoring_can_change_frozen_thread_widget_vocabulary(
    page_dir,
):
    """Re-vendoring can change a frozen widget's current declaration."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    markup = (
        '<lf-ask id="thread-choice-decision"><h3>Which option?</h3>'
        '<lf-options id="thread-choice" choose>'
        '<lf-option id="thread-a">A</lf-option>'
        "</lf-options></lf-ask>"
    )
    thread_model.post_reply(
        page_dir, {"parent": "c1", "responds": "c1"}, "Pick one:", markup
    )

    registry = vocabulary(page_dir)
    options = registry["lf-options"]
    options["x-state"]["decide"] = {
        "decides": True,
        "detail": {
            "type": "object",
            "properties": {"outcome": {"enum": ["keep"]}},
            "required": ["outcome"],
            "additionalProperties": False,
        },
        "unit": "widget",
    }
    option = registry["lf-option"]
    option["x-retired-when"] = "keep"
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-options": options, "lf-option": option})
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    assert events_model.read_events(page_dir)


def test_revendoring_checks_the_effective_page_owned_vocabulary(page_dir):
    """An unchanged page declaration remains part of the candidate after re-vendoring."""
    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            '<lf-local id="local-choice" value="author">Local</lf-local></section>',
        )
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )

    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert revendored.exit_code == 0, revendored.output
