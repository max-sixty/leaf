"""Tests scheduled by the measured cost of their boundary."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
    delivered,
    page_packages,
    publish,
    serving,
)
from model.interact_contract import vocabulary

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import vendoring as vendoring_model
from leaf.registry import storage as registry_storage
from leaf_dev.page_fixtures import package_selection_args


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


def test_init_allows_changed_generated_child_semantics(page_dir):
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

    del registry["lf-options"]["x-state"]["add"]["creates"]
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text(
        json.dumps({"lf-options": registry["lf-options"]})
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
