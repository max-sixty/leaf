"""How a page composes and caches its registry, reads its candidate vocabulary, and
keeps history and wakeups under each revision's captured vocabulary."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import model_folds as model
import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_carried_log_record,
    append_command,
    check_findings,
    element_declaration,
    fresh_process,
    page_packages,
    publish,
    registry_refusal,
    styled,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import page_view as page_view_model
from leaf import passages as passages_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.registry import contract as registry_contract
from leaf.registry import page as registry_page
from leaf.registry import storage as registry_storage
from model.interact_contract import (
    _stateful_page_declaration,
)


def test_page_registry_composes_declarations_and_implementations_independently(
    page_dir,
):
    layer = registry_storage.load_registry(page_dir)
    package_widget = element_declaration("lf-local", upgrade=True)
    package_widget["properties"]["package-only"] = {"type": "string"}
    layer = {**layer, "lf-local": package_widget}
    page_widget = element_declaration("lf-local", upgrade=True)
    page_widget["properties"]["page-only"] = {"type": "string"}
    declarations = {
        "lf-local": page_widget,
        "lf-page-only": element_declaration("lf-page-only", upgrade=True),
        "$languages": {"paths": {"leaf": "javascript", "py": None}},
    }
    layer_before = deepcopy(layer)
    page_before = deepcopy(declarations)
    layer_2 = registry_storage.layer_record(page_dir)
    assert layer_2 is not None
    widget_paths = {
        *registry_storage.layer_widgets(layer_2, page_dir),
        "widgets/lf-local.js",
        "page/widgets/lf-page-only.js",
        "page/widgets/lf-tabs.js",
    }

    composed = registry_page.compose_page_registry(layer, declarations, widget_paths)

    assert composed.registry["lf-local"] == page_widget
    assert "package-only" not in composed.registry["lf-local"]["properties"]
    assert composed.declaration_sources["lf-local"] == "page"
    assert composed.widget_sources["lf-local"] == "widgets/lf-local.js"
    assert composed.declaration_sources["lf-tabs"] == "layer"
    assert composed.widget_sources["lf-tabs"] == "page/widgets/lf-tabs.js"
    assert composed.declaration_sources["lf-page-only"] == "page"
    assert composed.widget_sources["lf-page-only"] == "page/widgets/lf-page-only.js"
    assert composed.registry["$languages"]["paths"] == {
        **{
            key: value
            for key, value in layer["$languages"]["paths"].items()
            if key != "py"
        },
        "leaf": "javascript",
    }
    assert layer == layer_before and declarations == page_before


def test_a_composed_vocabulary_carries_its_decisions(page_dir):
    """`$decisions` is what the browser reads to know which verb decides a widget and
    which members each outcome takes off the page. Every composition stamps it, so a
    page declaring a member of its own is served a relation that holds it."""
    layer = registry_storage.load_registry(page_dir)
    assert layer["$decisions"] == {
        "lf-suggestion": {
            "verb": "decide",
            "retires": {"accept": ["lf-old"], "reject": ["lf-new"]},
        }
    }
    member = {**deepcopy(layer["lf-old"]), "x-retired-when": "reject"}
    layer_3 = registry_storage.layer_record(page_dir)
    assert layer_3 is not None
    widget_paths = set(registry_storage.layer_widgets(layer_3, page_dir))

    composed = registry_page.compose_page_registry(
        layer, {"lf-gone": member}, widget_paths
    )

    assert composed.registry["$decisions"]["lf-suggestion"]["retires"] == {
        "accept": ["lf-old"],
        "reject": ["lf-new", "lf-gone"],
    }


@pytest.mark.parametrize(("schema", "stamped"), [(True, "words"), (False, False)])
def test_a_boolean_schema_for_a_toned_attribute_is_stamped_with_its_words(
    page_dir, schema, stamped
):
    """An attribute that takes the layer's tones may have `true` for its schema, which
    becomes the tones alone, or `false`, which admits none already."""
    layer = registry_storage.load_registry(page_dir)
    declaration = element_declaration("lf-local")
    declaration["properties"]["tone"] = schema
    declaration["x-tone"] = "tone"
    layer_4 = registry_storage.layer_record(page_dir)
    assert layer_4 is not None
    widget_paths = set(registry_storage.layer_widgets(layer_4, page_dir))

    composed = registry_page.compose_page_registry(
        layer, {"lf-local": declaration}, widget_paths
    ).registry

    assert composed["lf-local"]["properties"]["tone"] == (
        {"enum": layer["$tones"]["names"]} if stamped else False
    )


def test_a_composed_vocabulary_carries_each_verbs_writer_and_definition(page_dir):
    """`$states` is what the browser reads for a verb's writer and the operation an
    admitted event records, so it derives neither. A page's own declaration is stamped
    with the layer's, an unstated writer as the user's."""
    layer = registry_storage.load_registry(page_dir)
    declaration = element_declaration("lf-local", upgrade=True)
    declaration["properties"] |= {
        name: {"type": "boolean"} for name in ("overruled", "restated")
    } | {"reading": {"type": "string"}}
    declaration["x-state"] = {
        "set": {
            "unit": "widget",
            "detail": {"type": "object", "additionalProperties": False},
        },
        "measure": {
            "unit": "widget",
            "writer": "agent",
            "record": {"kind": "value", "attr": "reading"},
        },
    }
    layer_5 = registry_storage.layer_record(page_dir)
    assert layer_5 is not None
    widget_paths = set(registry_storage.layer_widgets(layer_5, page_dir))

    composed = registry_page.compose_page_registry(
        layer, {"lf-local": declaration}, {*widget_paths, "widgets/lf-local.js"}
    ).registry

    assert composed["$states"]["lf-local"] == {
        verb: {
            "writer": writer,
            "definition": registry_contract.state_definition(
                "lf-local", declaration, declaration["x-state"][verb]
            ),
        }
        for verb, writer in (("set", "user"), ("measure", "agent"))
    }
    assert composed["$states"]["lf-suggestion"]["decide"]["writer"] == "user"


@pytest.mark.parametrize(
    ("declarations", "code", "at"),
    [
        ("{broken", "registry-json", ""),
        ("[]", "registry-not-object", ""),
        ('{"lf-local": null}', "declaration-not-object", ""),
        ('{"$layer": {"generation": "authored"}}', "page-layer", ""),
        (
            json.dumps(
                {"lf-local": {**element_declaration("lf-local"), "type": "wrong"}}
            ),
            "declaration-schema",
            "<lf-local>",
        ),
        (
            json.dumps(
                {
                    "lf-local": {
                        **element_declaration("lf-local"),
                        "x-example": '<lf-local id="bad" unknown="bad">Example</lf-local>',
                    }
                }
            ),
            "invalid-example",
            "<lf-local>",
        ),
        (
            json.dumps({"lf-local": element_declaration("lf-local", upgrade=True)}),
            "missing-module",
            "<lf-local>",
        ),
    ],
)
def test_page_registry_rejects_invalid_authored_contracts(
    page_dir, declarations, code, at
):
    authored = page_dir / "page" / "registry.json"
    authored.parent.mkdir(exist_ok=True)
    authored.write_text(declarations)

    finding = registry_refusal(lambda: registry_storage.read_page_registry(page_dir))

    assert (finding.code, finding.at) == (code, at)
    assert finding.values["registry"] == str(authored.absolute())


def _faulty(tag: str, *, upgrade: bool = False, **keys) -> dict:
    return {**element_declaration(tag, upgrade=upgrade), **keys}


@pytest.mark.parametrize(
    ("declarations", "expected"),
    [
        # Faults each declaration shows alone, beside a data contract's.
        (
            {
                "lf-alpha": _faulty("lf-alpha", description=""),
                "lf-beta": _faulty("lf-beta", **{"x-says": ["label"]}),
                "$data": {
                    "contracts": {"bad": {"description": "x", "schema": {"type": 3}}}
                },
            },
            [
                ("contract-schema", ""),
                ("no-description", "<lf-alpha>"),
                ("invalid-extensions", "<lf-beta>"),
            ],
        ),
        # Faults against the other declarations, once every one holds alone.
        (
            {
                "lf-beta": _faulty("lf-beta", **{"x-name": "label"}),
                "lf-eps": _faulty(
                    "lf-eps", **{"x-reading-role": "pane", "x-content": "empty"}
                ),
            },
            [("undeclared-attributes", "<lf-beta>"), ("requires", "<lf-eps>")],
        ),
        # An example and a module, once the vocabulary holds.
        (
            {
                "lf-gamma": _faulty(
                    "lf-gamma",
                    **{"x-example": '<lf-gamma id="g" tone="x">G</lf-gamma>'},
                ),
                "lf-delta": _faulty("lf-delta", upgrade=True),
            },
            [("invalid-example", "<lf-gamma>"), ("missing-module", "<lf-delta>")],
        ),
    ],
)
def test_one_check_reports_the_first_problem_in_each_declaration(
    page_dir, declarations, expected
):
    """An author repairing page declarations reads every independent problem from
    one `page check`, rather than one per run."""
    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "registry.json").write_text(json.dumps(declarations))

    status, findings = check_findings(page_dir)

    assert status != 0
    assert [
        (finding.code, finding.at)
        for finding in findings
        if "registry" in finding.values
    ] == expected
    authored = page_dir / "page"
    authored.mkdir(exist_ok=True)
    source = authored / "registry.json"
    declaration = element_declaration("lf-local")
    source.write_text(json.dumps({"lf-local": declaration}))
    first = registry_storage.read_page_registry(page_dir)
    assert registry_storage.read_page_registry(page_dir) is first
    declaration["description"] = "The next authored declaration."
    source.write_text(json.dumps({"lf-local": declaration}))

    second = registry_storage.read_page_registry(page_dir)

    assert second.registry["lf-local"] == declaration
    assert first.registry["lf-local"]["description"] != declaration["description"]
    assert "lf-local" not in registry_storage.load_registry(page_dir)


def test_a_page_with_no_revision_reads_its_candidate_vocabulary(page_dir):
    """Before the first revision the document is the candidate, so the command
    readers and the append door both read the vocabulary it would be captured under:
    the layer composed with the page's own declarations, not the bare layer."""
    declaration = element_declaration("lf-local")
    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "registry.json").write_text(
        json.dumps({"lf-local": declaration})
    )
    assert files_model.list_revisions(page_dir) == []

    for vocabulary in (
        registry_storage.active_registry(page_dir),
        page_view_model.PageView(page_dir).registry(None),
    ):
        assert vocabulary is not None
        assert vocabulary["lf-local"] == declaration


@pytest.mark.parametrize("active_attention", [True, False])
@pytest.mark.parametrize("declaration", ["obligation", "attention"])
def test_late_gesture_wakes_for_the_active_vocabulary(
    page_dir, active_attention, declaration
):
    """An old tab validates under its capture and changes the current page's
    obligations and requested input. The page's own widget changes between the two
    revisions, as its author's declarations do."""
    from leaf.state import write_json

    def publish_choice(needs_attention):
        pick = _stateful_page_declaration(page_dir, "lf-pick")
        if needs_attention and declaration == "obligation":
            pick["x-awaits"] = {"value": "first", "answered": {"first": {}}}
        elif needs_attention:
            pick["x-state"]["first"]["attention"] = True
        write_json(page_dir / "page" / "registry.json", {"lf-pick": pick})
        (page_dir / "index.html").write_text(
            model.leaf_page(
                "Choice", '<lf-pick id="choice" value="author">Pick</lf-pick>'
            )
        )
        publish(page_dir)

    publish_choice(not active_attention)
    original = files_model.latest_revision(page_dir)
    publish_choice(active_attention)
    value_2 = files_model.latest_revision(page_dir)
    assert value_2 is not None
    assert original is not None
    assert value_2 > original

    action = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": original,
            "widget": "choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    assert action["attention"] is active_attention
    assert ("answer" in action["meaning"]) is (
        not active_attention and declaration == "obligation"
    )
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == (
        [action] if active_attention else []
    )


def test_wakeup_uses_the_recorded_identity_after_an_undo(page_dir):
    publish(page_dir)
    reaction = append_command(
        page_dir,
        {
            "id": "pending",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "shorten",
        },
    )
    append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": reaction["id"]}
    )
    fresh = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Fresh input"},
    )
    assert fresh["id"] != reaction["id"]
    assert fresh["attention"]
    assert service_model.unacknowledged(
        events_model.read_events(page_dir), fresh["seq"] - 1
    ) == [fresh]


def test_page_registry_cache_follows_layer_and_widget_files(page_dir):
    first = registry_storage.read_page_registry(page_dir)
    assert registry_storage.read_page_registry(page_dir) is first

    assert "lf-diff" in first.registry
    vendoring_model.cmd_init(page_dir, selected=page_packages()[:-1])
    revendored = registry_storage.read_page_registry(page_dir)
    assert revendored is not first
    assert "lf-diff" not in revendored.registry

    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    implementation = widgets / "lf-options.js"
    implementation.write_text("export function upgrade() {}\n")
    overlaid = registry_storage.read_page_registry(page_dir)
    assert overlaid is not revendored
    assert overlaid.widget_sources["lf-options"] == "page/widgets/lf-options.js"

    implementation.write_text("export function upgrade() { return true; }\n")
    changed = registry_storage.read_page_registry(page_dir)
    assert changed is not overlaid
    assert changed.widget_sources == overlaid.widget_sources


def test_page_registry_cache_does_not_outlive_a_page_at_the_same_path(tmp_path):
    page = tmp_path / "reused"
    runner = CliRunner()
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    first = registry_storage.read_page_registry(page)

    shutil.rmtree(page)
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    second = registry_storage.read_page_registry(page)

    assert second is not first
    assert (
        second.registry["$layer"]["generation"]
        != first.registry["$layer"]["generation"]
    )


def test_candidate_vocabulary_changes_leave_old_actions_in_captured_history(page_dir):
    """A superseded action can become the winner again if the later action is undone."""
    from leaf.projection import page_reading
    from leaf.revision_artifact import read_artifact

    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    source = PAGE.replace(
        "</section>",
        '<lf-local id="local-choice" value="author">Local</lf-local></section>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    first = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "first"},
        },
    )
    second = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "second"},
        },
    )
    events = events_model.read_events(page_dir)
    assert revision is not None
    historical = read_artifact(page_dir, revision)
    after_undo = [
        *events,
        {
            "kind": "undo",
            "id": "undo-second",
            "author": "user",
            "undoes": second["id"],
        },
    ]
    projected = page_reading(
        passages_model.SourceReading(
            structure_model.SourceDocument(source), historical.registry
        ),
        after_undo,
        revision,
    )
    assert next(iter(projected.projection.desired.values()))[0]["id"] == first["id"]

    declaration["x-state"]["second"] = declaration["x-state"].pop("first")
    authored.write_text(json.dumps({"lf-local": declaration}))
    refused = revisioning_model.activate_source(page_dir)

    assert refused.error is None and refused.created
    assert refused.revision == revision + 1


def test_an_action_an_earlier_runtime_logged_is_left_out_of_the_fold(page_dir):
    """A pick logged before admission recorded its state operation, in the payload
    shape of its day, folds as absent: `leaf page state` reads on with the current
    pick in force instead of failing on the old record."""
    source = PAGE.replace(
        "</section>",
        '<lf-options id="picks" choose><lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></section>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    current = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["first"]},
        },
    )
    # The shape a runtime before recorded state operations logged a pick in.
    earlier = {
        "kind": "action",
        "revision": revision,
        "widget": "picks",
        "action": "choose",
        "detail": {"options": ["second"]},
        "author": "user",
        "id": "earlier-pick",
        "meaning": {
            "scope": "page",
            "unit": "picks",
            "depends": ["picks", "second"],
            "answer": None,
        },
        "attention": True,
        "ts": "2026-10-06T20:14:37.092-07:00",
    }
    with (page_dir / schema_model.EVENTS_FILE).open("a") as log:
        log.write(json.dumps(earlier) + "\n")

    out = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])

    assert out.exit_code == 0, out.output
    assert [(s["widget"], s["detail"]) for s in json.loads(out.stdout)["state"]] == [
        ("picks", current["detail"])
    ]


def test_candidate_vocabulary_leaves_removed_page_widgets_to_captured_history(page_dir):
    """A retracted action on a removed sender is interpreted only in its old revision."""
    from leaf.projection import page_reading
    from leaf.revision_artifact import read_revision

    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    original = PAGE.replace(
        "</section>",
        '<lf-local id="local-choice" value="author">Local</lf-local></section>',
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    first_revision = files_model.latest_revision(page_dir)
    action = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": first_revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    restated = original.replace('value="author"', 'value="author-next" restated')
    (page_dir / "index.html").write_text(restated)
    assert publish(page_dir, "Retract the local choice.")["restated"] == [
        "local-choice"
    ]

    authored.write_text("{}")
    (page_dir / "index.html").write_text(PAGE)
    events = events_model.read_events(page_dir)
    activated = revisioning_model.activate_source(page_dir)

    assert activated.error is None and activated.created
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    assert first_revision is not None
    historical = page_reading(
        passages_model.SourceReading(
            structure_model.SourceDocument(original),
            read_revision(page_dir, first_revision).registry,
        ),
        events,
        first_revision,
    )
    assert (
        historical.projection.desired["local-choice", "local-choice", "first"][0]["id"]
        == action["id"]
    )


def test_candidate_vocabulary_can_change_after_frozen_thread_actions(page_dir):
    """A thread widget keeps the contract under which its user command was admitted."""
    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir, "lf-thread-local")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "Choose."},
    )
    thread_model.post_reply(
        page_dir,
        {"parent": "c1", "responds": "c1"},
        "Use this control.",
        '<lf-thread-local id="thread-choice" value="author">Local</lf-thread-local>',
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "thread-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    declaration["x-state"]["second"] = declaration["x-state"].pop("first")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))

    refused = revisioning_model.activate_source(page_dir)

    assert refused.error is None and refused.created
    assert revision is not None
    assert refused.revision == revision + 1


def test_a_fresh_server_does_not_revalidate_the_active_revisions_inputs(
    page_dir, monkeypatch
):
    """A revision's vocabulary was validated when it activated, so a process reading
    the page anew does not validate it again while it stands unchanged, and no check
    parses the layer's sheets: together they were most of a cold first read."""
    from leaf import revision_artifact, styles

    (page_dir / "index.html").write_text(styled("main { color: red; }"))
    assert revisioning_model.activate_source(page_dir).error is None
    validated, linted = [], []
    real_validate = registry_page.validate_registry
    real_lint = styles.dropped_css
    monkeypatch.setattr(
        registry_page,
        "validate_registry",
        lambda registry, source: (
            validated.append(source) or real_validate(registry, source)
        ),
    )
    # The source check reads the document's sheets and each file under page/.
    monkeypatch.setattr(
        revision_artifact,
        "dropped_css",
        lambda css, where, **kw: linted.append(where) or real_lint(css, where, **kw),
    )

    # What a newly started server holds: none of this test's readings.
    with fresh_process():
        assert revisioning_model.activate_source(page_dir).error is None
    assert validated == []
    assert linted == ["page <style> (line 5)"]


@pytest.mark.parametrize(
    "change", ["slot", "enum", "pattern", "description", "broaden"]
)
def test_revised_state_definitions_keep_original_history_and_admit_new_typed_state(
    page_dir, change
):
    from interact_support import state_json

    from leaf.projection import page_reading
    from leaf.revision_artifact import read_revision

    declaration = _stateful_page_declaration(page_dir)
    declaration["properties"]["value"] = {
        "type": "string",
        "enum": ["old", "new"],
        "description": "Original meaning.",
    }
    declaration["properties"]["target"] = {"type": "string"}
    authored = page_dir / "page" / "registry.json"
    source = page_dir / "index.html"
    authored.write_text(json.dumps({"lf-local": declaration}))
    source.write_text(
        PAGE.replace(
            "</section>",
            '<lf-local id="local-choice" value="old" target="new">Local</lf-local></section>',
        )
    )
    publish(page_dir)
    original = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "old"},
        },
    )
    assert original["meaning"]["state"]["record"] == {"kind": "value", "attr": "value"}
    next_value = "new"
    if change == "slot":
        declaration["x-state"]["first"]["record"]["attr"] = "target"
    elif change == "enum":
        declaration["properties"]["value"]["enum"] = ["new"]
    elif change == "broaden":
        declaration["properties"]["value"]["enum"].append("later")
    elif change == "pattern":
        declaration["properties"]["value"] = {"type": "string", "pattern": "^new$"}
    else:
        declaration["properties"]["value"]["description"] = "Clarified explanation."
    authored.write_text(json.dumps({"lf-local": declaration}))
    source.write_text(
        source.read_text().replace('value="old"', f'value="{next_value}"')
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    current = state_json(page_dir)["state"]
    assert bool(current) == (change in {"description", "broaden"})
    historical = page_reading(
        read_revision(page_dir, 1), events_model.read_events(page_dir), 1
    )
    assert (
        historical.projection.desired["local-choice", "local-choice", "first"][0]["id"]
        == original["id"]
    )
    revised = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": activated.revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": next_value},
        },
    )
    [chosen] = state_json(page_dir)["state"]
    assert chosen["detail"] == {"value": next_value}
    assert (
        revised["meaning"]["state"] != original["meaning"]["state"]
        or change == "description"
    )
    assert original in events_model.read_events(page_dir)


@pytest.mark.parametrize(
    "case",
    json.loads(
        (Path(__file__).parents[2].joinpath("state_definition_cases.json")).read_text()
    ),
    ids=lambda case: case["id"],
)
def test_state_definition_identity_ignores_only_annotations(case):
    from leaf.registry.contract import same_state_definition, state_definition

    definitions = [
        state_definition("lf-local", {}, {"unit": "widget", "detail": case[key]})
        for key in ("before", "after")
    ]
    assert same_state_definition(*definitions) is case["same"]
