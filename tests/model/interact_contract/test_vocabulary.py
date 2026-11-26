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
    append_command,
    check_findings,
    element_declaration,
    fresh_process,
    model_layer,
    page_packages,
    publish,
    registry_refusal,
    styled,
)

from leaf.base import files as files_model
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import page_view as page_view_model
from leaf.records import revisioning as revisioning_model
from leaf.records import transaction as transaction_model
from leaf.source import layer as layer_model
from leaf.source import reading as reading_model
from leaf.source import revision_artifact as artifact_model
from leaf.source import runtime_selection as runtime_model
from leaf.source import structure as structure_model
from leaf.source import vocabulary as vocabulary_model
from leaf.source.registry import contract as registry_contract
from leaf.source.registry import layer as registry_layer
from leaf.source.registry import page as registry_page
from leaf.source.registry import storage as registry_storage
from leaf.source.registry import validation as registry_validation
from model.interact_contract import (
    _stateful_page_declaration,
)


def layer_widget_paths(page_dir) -> set[str]:
    """The widget modules the page's layer serves (`layer.layer_widgets`)."""
    record = registry_storage.layer_record(page_dir)
    assert record is not None
    vocabulary = layer_model.selected_vocabulary(record, page_dir)
    return set(layer_model.layer_widgets(vocabulary))


def test_page_registry_composes_declarations_and_implementations_independently(
    page_dir,
):
    layer = vocabulary_model.load_registry(page_dir)
    package_widget = element_declaration("lf-local", upgrade=True)
    package_widget["attributes"]["properties"]["package-only"] = {"type": "string"}
    layer = {**layer, "lf-local": package_widget}
    page_widget = element_declaration("lf-local", upgrade=True)
    page_widget["attributes"]["properties"]["page-only"] = {"type": "string"}
    declarations = {
        "lf-local": page_widget,
        "lf-page-only": element_declaration("lf-page-only", upgrade=True),
        "$languages": {"paths": {"leaf": "javascript", "py": None}},
    }
    layer_before = deepcopy(layer)
    page_before = deepcopy(declarations)
    widget_paths = {
        *layer_widget_paths(page_dir),
        "widgets/lf-local.js",
        "page/widgets/lf-page-only.js",
        "page/widgets/lf-tabs.js",
    }

    composed = registry_page.compose_page_registry(layer, declarations, widget_paths)

    assert composed.registry["lf-local"]["attributes"]["properties"].keys() == {
        "id",
        "page-only",
    }
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
    layer = vocabulary_model.load_registry(page_dir)
    assert layer["$decisions"] == {
        "lf-suggestion": {
            "verb": "decide",
            "retires": {"accept": ["lf-old"], "reject": ["lf-new"]},
        }
    }
    member = deepcopy(layer["lf-old"])
    member["retired-when"] = "reject"
    widget_paths = layer_widget_paths(page_dir)

    composed = registry_page.compose_page_registry(
        layer, {"lf-gone": member}, widget_paths
    )

    assert composed.registry["$decisions"]["lf-suggestion"]["retires"] == {
        "accept": ["lf-old"],
        "reject": ["lf-new", "lf-gone"],
    }


@pytest.mark.parametrize(
    "order", [("lf-moved", "lf-struck"), ("lf-struck", "lf-moved")]
)
def test_two_layers_each_add_a_member_one_decision_retires(order):
    """A layer adds a retiring member to a widget another layer declares by declaring
    the member alone, so two layers that each add one compose in either order and the
    decision retires both. Named on the owner's verb instead, each layer restated the
    owner's entry whole, and the later layer's dropped the earlier one's member with
    no refusal."""
    outcome = {"lf-moved": "accept", "lf-struck": "reject"}
    registry = deepcopy(model_layer())
    for tag in order:
        member = deepcopy(registry["lf-old"])
        member["retired-when"] = outcome[tag]
        registry_layer.merge_layer_declarations(registry, {tag: member})
    registry_validation.validate_registry(registry, "two layers")
    registry_layer.stamp_composition(registry)

    assert registry["$decisions"]["lf-suggestion"]["retires"] == {
        "accept": ["lf-old", "lf-moved"],
        "reject": ["lf-new", "lf-struck"],
    }


@pytest.mark.parametrize(("schema", "stamped"), [(True, "words"), (False, False)])
def test_a_boolean_schema_for_a_toned_attribute_is_stamped_with_its_words(
    page_dir, schema, stamped
):
    """An attribute that takes the layer's tones may have `true` for its schema, which
    becomes the tones alone, or `false`, which admits none already."""
    layer = vocabulary_model.load_registry(page_dir)
    declaration = element_declaration("lf-local")
    declaration["attributes"]["properties"]["tone"] = schema
    widget_paths = layer_widget_paths(page_dir)

    composed = registry_page.compose_page_registry(
        layer, {"lf-local": declaration}, widget_paths
    ).registry

    assert composed["lf-local"]["attributes"]["properties"]["tone"] == (
        {"enum": layer["$tones"]["names"]} if stamped else False
    )


def test_a_module_that_goes_is_refused_by_a_composition_validated_with_it(page_dir):
    """A module's file decides whether its tag is upgraded, so a declaration can stand
    unchanged while what it relies on goes. A composition reusing the validation of
    the same declarations still refuses it, where it would otherwise serve a stateful
    widget with nothing to draw or send its state."""
    layer = vocabulary_model.load_registry(page_dir)
    declarations = {"lf-local": _stateful_page_declaration(page_dir)}
    layer_paths = layer_widget_paths(page_dir)

    held = registry_page.compose_page_registry(
        layer, declarations, {*layer_paths, "page/widgets/lf-local.js"}
    )
    assert held.widget_sources["lf-local"] == "page/widgets/lf-local.js"

    finding = registry_refusal(
        lambda: registry_page.compose_page_registry(
            layer, declarations, layer_paths, validated=(layer, declarations)
        )
    )
    assert (finding.code, finding.at) == ("needs-module", "<lf-local>")


def test_a_page_widget_module_no_tag_names_is_refused(page_dir):
    """A page's widget module is loaded by its tag's name alone, so one under a name
    no declaration has is refused where the page is checked."""
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True)
    (widgets / "lf-locl.js").write_text("export {};\n")
    (page_dir / "page" / "registry.json").write_text(
        json.dumps({"lf-local": element_declaration("lf-local")})
    )

    finding = registry_refusal(lambda: vocabulary_model.read_page_registry(page_dir))

    assert finding.code == "unnamed-module"
    assert finding.values["modules"] == ["page/widgets/lf-locl.js"]


def test_a_composed_vocabulary_carries_each_verbs_writer_and_definition(page_dir):
    """`$states` is what the browser reads for a verb's writer and the operation an
    admitted event records, so it derives neither. A page's own declaration is stamped
    with the layer's, an unstated writer as the user's."""
    layer = vocabulary_model.load_registry(page_dir)
    declaration = element_declaration("lf-local", upgrade=True)
    declaration["attributes"]["properties"]["reading"] = {"type": "string"}
    declaration["verbs"] = {
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
    widget_paths = layer_widget_paths(page_dir)

    composed = registry_page.compose_page_registry(
        layer, {"lf-local": declaration}, {*widget_paths, "widgets/lf-local.js"}
    ).registry

    assert composed["$states"]["lf-local"] == {
        verb: {
            "writer": writer,
            "definition": registry_contract.state_definition(
                "lf-local", declaration, declaration["verbs"][verb]
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
                {
                    "lf-local": {
                        **element_declaration("lf-local"),
                        "attributes": {"type": "wrong"},
                    }
                }
            ),
            "attributes-schema",
            "<lf-local>",
        ),
        (
            json.dumps({"lf-local": element_declaration("lf-local", upgrade=True)}),
            "needs-module",
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

    finding = registry_refusal(lambda: vocabulary_model.read_page_registry(page_dir))

    assert (finding.code, finding.at) == (code, at)
    assert finding.values["registry"] == str(authored.absolute())


def _faulty(tag: str, *, upgrade: bool = False, **keys) -> dict:
    return {**element_declaration(tag, upgrade=upgrade), **keys}


def test_one_check_advises_on_each_example_a_page_could_not_hold(page_dir):
    """An example is documentation no reader the user relies on needs valid, so
    `page check` passes a page whose declarations' examples break and names each, by
    the first refusal a page holding it would meet."""
    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "registry.json").write_text(
        json.dumps(
            {
                "lf-gamma": _faulty(
                    "lf-gamma", example='<lf-gamma id="g" tone="x">G</lf-gamma>'
                ),
                "lf-delta": _faulty(
                    "lf-delta", example='<lf-delta id="d" tone="x">D</lf-delta>'
                ),
            }
        )
    )

    status, findings = check_findings(page_dir)

    assert status == 0
    assert [
        (finding.code, finding.at, finding.values["registry"])
        for finding in findings
        if "registry" in finding.values
    ] == [
        ("invalid-example", "<lf-gamma>", str(page_dir / "page" / "registry.json")),
        ("invalid-example", "<lf-delta>", str(page_dir / "page" / "registry.json")),
    ]


@pytest.mark.parametrize(
    ("declarations", "expected"),
    [
        # Faults each declaration shows alone, beside a data contract's.
        (
            {
                "lf-alpha": _faulty("lf-alpha", description=""),
                "lf-beta": _faulty(
                    "lf-beta",
                    **{
                        "refers": [],
                    },
                ),
                "$data": {
                    "contracts": {"bad": {"description": "x", "schema": {"type": 3}}}
                },
            },
            [
                ("contract-schema", ""),
                ("invalid-declaration", "<lf-alpha>"),
                ("invalid-declaration", "<lf-beta>"),
            ],
        ),
        # Faults against the other declarations, once every one holds alone.
        (
            {
                "lf-beta": _faulty(
                    "lf-beta",
                    **{
                        "refers": {"label": {}},
                    },
                ),
                "lf-eps": _faulty(
                    "lf-eps",
                    **{
                        "content": "empty",
                        "reading-role": "pane",
                    },
                ),
                # What only a module provides, with no module for the tag.
                "lf-delta": _faulty("lf-delta", upgrade=True),
            },
            [
                ("undeclared-attributes", "<lf-beta>"),
                ("requires", "<lf-eps>"),
                ("needs-module", "<lf-delta>"),
            ],
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
    first = vocabulary_model.read_page_registry(page_dir)
    assert vocabulary_model.read_page_registry(page_dir) is first
    declaration["description"] = "The next authored declaration."
    source.write_text(json.dumps({"lf-local": declaration}))

    second = vocabulary_model.read_page_registry(page_dir)

    assert second.registry["lf-local"]["description"] == declaration["description"]
    assert first.registry["lf-local"]["description"] != declaration["description"]
    assert "lf-local" not in vocabulary_model.load_registry(page_dir)


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
        vocabulary_model.active_registry(page_dir),
        page_view_model.PageView(page_dir).registry(None),
    ):
        assert vocabulary is not None
        assert vocabulary["lf-local"]["description"] == declaration["description"]


@pytest.mark.parametrize("active_attention", [True, False])
@pytest.mark.parametrize("declaration", ["obligation", "attention"])
def test_late_gesture_wakes_for_the_active_vocabulary(
    page_dir, active_attention, declaration
):
    """An old tab validates under its capture and changes the current page's
    obligations and requested input. The page's own widget changes between the two
    revisions, as its author's declarations do."""
    from leaf.base.state import write_json

    def publish_choice(needs_attention):
        pick = _stateful_page_declaration(page_dir, "lf-pick")
        if needs_attention and declaration == "obligation":
            pick["awaits"] = {
                "value": "first",
                "answered": {"first": {}},
            }
        elif needs_attention:
            pick["verbs"]["first"]["attention"] = True
        write_json(page_dir / "page" / "registry.json", {"lf-pick": pick})
        (page_dir / "index.html").write_text(
            model.leaf_page(
                "Choice",
                '<lf-group id="ask" label="Which pick?">'
                '<lf-pick id="choice" value="author">Pick</lf-pick></lf-group>',
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
    assert transaction_model.unacknowledged(events_model.read_events(page_dir), 0) == (
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
            "emoji": "✂️",
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
    assert transaction_model.unacknowledged(
        events_model.read_events(page_dir), fresh["seq"] - 1
    ) == [fresh]


def test_page_registry_cache_follows_layer_and_widget_files(page_dir):
    first = vocabulary_model.read_page_registry(page_dir)
    assert vocabulary_model.read_page_registry(page_dir) is first

    assert "lf-diff" in first.registry
    vendoring_model.cmd_init(page_dir, selected=page_packages()[:-1])
    revendored = vocabulary_model.read_page_registry(page_dir)
    assert revendored is not first
    assert "lf-diff" not in revendored.registry

    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    implementation = widgets / "lf-options.js"
    implementation.write_text("export function upgrade() {}\n")
    overlaid = vocabulary_model.read_page_registry(page_dir)
    assert overlaid is not revendored
    assert overlaid.widget_sources["lf-options"] == "page/widgets/lf-options.js"

    implementation.write_text("export function upgrade() { return true; }\n")
    changed = vocabulary_model.read_page_registry(page_dir)
    assert changed is not overlaid
    assert changed.widget_sources == overlaid.widget_sources


def test_page_registry_cache_does_not_outlive_a_page_at_the_same_path(tmp_path):
    page = tmp_path / "reused"
    runner = CliRunner()
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    first = vocabulary_model.read_page_registry(page)

    shutil.rmtree(page)
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    second = vocabulary_model.read_page_registry(page)

    assert second is not first
    assert (
        second.registry["$layer"]["generation"]
        != first.registry["$layer"]["generation"]
    )


@pytest.mark.parametrize(
    "read",
    [
        pytest.param(
            lambda page: vocabulary_model.read_page_registry(page).registry,
            id="candidate",
        ),
        pytest.param(
            lambda page: artifact_model.read_revision(page, 1).registry, id="revision"
        ),
        pytest.param(
            lambda page: json.loads(
                runtime_model.executing(artifact_model.read_artifact(page, 1))
                .resources["/registry.json"]
                .data
            ),
            id="execution",
        ),
    ],
)
def test_a_reading_composes_one_installation_of_a_package(tmp_path, monkeypatch, read):
    """`package install` points an installed name at another snapshot while pages
    read it (`layer.named_package`), so each reading of a page's vocabulary resolves
    the page's selection once and takes the registry, the widget modules and, where it
    serves them, the layer's files from that one snapshot. A reading that resolved the
    selection for each of them could pair one snapshot's declarations with another's
    modules: it would refuse the page, or serve a registry naming modules its files
    lack. Here an install of the other snapshot follows every resolution of the
    package's name."""
    monkeypatch.chdir(tmp_path)
    installed = []
    for tag in ("lf-first", "lf-second"):
        snapshot = tmp_path / tag / "swapped"
        (snapshot / "widgets").mkdir(parents=True)
        (snapshot / "widgets" / f"{tag}.js").write_text("export {};\n")
        (snapshot / "registry.json").write_text(
            json.dumps({tag: element_declaration(tag, upgrade=True)})
        )
        installed.append(snapshot)
    resolve = layer_model.named_package
    monkeypatch.setattr(
        layer_model,
        "named_package",
        lambda name: installed[0] if name == "swapped" else resolve(name),
    )
    page = tmp_path / "page"
    init = ["page", "init", "--package", "swapped", str(page)]
    made = CliRunner().invoke(cli_model.cli, init)
    assert made.exit_code == 0, made.output
    (page / "index.html").write_text(
        "<!doctype html><html><head><title>t</title></head>"
        "<body><main><p>words</p></main></body></html>"
    )
    assert revisioning_model.activate_source(page).error is None

    def resolving(name):
        if name != "swapped":
            return resolve(name)
        root = installed[0]
        installed.reverse()
        return root

    monkeypatch.setattr(layer_model, "named_package", resolving)
    # What a newly started server holds: no reading of the page.
    with fresh_process():
        registry = read(page)

    assert {"lf-first", "lf-second"} & registry.keys() == {"lf-first"}


def test_candidate_vocabulary_changes_leave_old_actions_in_captured_history(page_dir):
    """A superseded action can become the winner again if the later action is undone."""
    from leaf.log.projection import page_reading
    from leaf.source.revision_artifact import read_artifact

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
        reading_model.SourceReading(
            structure_model.SourceDocument(source), historical.registry
        ),
        after_undo,
        revision,
    )
    assert next(iter(projected.projection.desired.values()))[0]["id"] == first["id"]

    declaration["verbs"]["second"] = declaration["verbs"].pop("first")
    authored.write_text(json.dumps({"lf-local": declaration}))
    refused = revisioning_model.activate_source(page_dir)

    assert refused.error is None and refused.created
    assert refused.revision == revision + 1


def test_candidate_vocabulary_leaves_removed_page_widgets_to_captured_history(page_dir):
    """A retracted action on a removed sender is interpreted only in its old revision."""
    from leaf.log.projection import page_reading
    from leaf.source.revision_artifact import read_revision

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
    # A module no declared tag names is refused, so the widget's module goes with
    # its declaration.
    (page_dir / "page" / "widgets" / "lf-local.js").unlink()
    (page_dir / "index.html").write_text(PAGE)
    events = events_model.read_events(page_dir)
    activated = revisioning_model.activate_source(page_dir)

    assert activated.error is None and activated.created
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    assert first_revision is not None
    historical = page_reading(
        reading_model.SourceReading(
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


@pytest.mark.parametrize("declares", [False, True])
def test_a_fresh_server_does_not_revalidate_the_active_revisions_inputs(
    page_dir, monkeypatch, declares
):
    """A revision's vocabulary was validated when it activated, so a process reading
    the page anew does not validate the unchanged candidate again, and no check
    parses the layer's sheets: together they were most of a cold first read. A page
    declaring its own widget has the revision's own composition validated once under
    this Leaf's layer, though its candidate's authored entry is unstamped where the
    revision's composed one is stamped."""
    from leaf.source import styles

    if declares:
        (page_dir / "page").mkdir(exist_ok=True)
        (page_dir / "page" / "registry.json").write_text(
            json.dumps({"lf-local": element_declaration("lf-local")})
        )
    (page_dir / "index.html").write_text(styled("main { color: red; }"))
    assert revisioning_model.activate_source(page_dir).error is None
    validated, linted = [], []
    real_validate = registry_validation.validate_registry
    real_lint = styles.dropped_css
    monkeypatch.setattr(
        registry_validation,
        "validate_registry",
        lambda registry, source: (
            validated.append(source) or real_validate(registry, source)
        ),
    )
    # The source check reads the document's sheets and each file under page/.
    monkeypatch.setattr(
        styles,
        "dropped_css",
        lambda css, where, **kw: linted.append(where) or real_lint(css, where, **kw),
    )

    # What a newly started server holds: none of this test's readings.
    with fresh_process():
        assert revisioning_model.activate_source(page_dir).error is None
    # The revision composes with the default source; the candidate names its file.
    assert validated == (["page/registry.json"] if declares else [])
    assert linted == ["page <style> (line 5)"]


@pytest.mark.parametrize(
    "change", ["slot", "enum", "pattern", "description", "broaden"]
)
def test_revised_state_definitions_keep_original_history_and_admit_new_typed_state(
    page_dir, change
):
    from interact_support import state_json

    from leaf.log.projection import page_reading
    from leaf.source.revision_artifact import read_revision

    declaration = _stateful_page_declaration(page_dir)
    declaration["attributes"]["properties"]["value"] = {
        "type": "string",
        "enum": ["old", "new"],
        "description": "Original meaning.",
    }
    declaration["attributes"]["properties"]["target"] = {"type": "string"}
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
        declaration["verbs"]["first"]["record"]["attr"] = "target"
    elif change == "enum":
        declaration["attributes"]["properties"]["value"]["enum"] = ["new"]
    elif change == "broaden":
        declaration["attributes"]["properties"]["value"]["enum"].append("later")
    elif change == "pattern":
        declaration["attributes"]["properties"]["value"] = {
            "type": "string",
            "pattern": "^new$",
        }
    else:
        declaration["attributes"]["properties"]["value"]["description"] = (
            "Clarified explanation."
        )
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
    from leaf.source.registry.contract import same_state_definition, state_definition

    definitions = [
        state_definition("lf-local", {}, {"unit": "widget", "detail": case[key]})
        for key in ("before", "after")
    ]
    assert same_state_definition(*definitions) is case["same"]
