"""Version corpus, registry, message, and export tests."""

import copy
import json
import os
import re
import socket
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from interact_support import (
    COMMAND_SUBJECTS,
    FLOW_PAGE,
    PAGE,
    ROOT,
    SHIPPED_PACKAGES,
    STATED_TIMEOUT,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    check,
    check_findings,
    comment,
    fetch,
    found,
    fragment_errors,
    fresh_process,
    live_versions,
    owed,
    page_state,
    publish,
    published,
    refused_on,
    response_reference,
    state_json,
    words,
)
from leaf_dev.example_data import regression_sources
from leaf_dev.page_fixtures import prepare_page, read_fixture

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import files as files_model
from leaf import layer as layer_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import todos as todos_model
from leaf.findings import Finding, Rejected
from leaf.registry import storage as registry_storage
from leaf.registry.contract import element_declarations
from leaf.structure import SourceDocument
from leaf.thread_context import thread_digest
from leaf.validation import composition as validation_model
from leaf.validation.admission import (
    check_markup,
    revision_publication,
)
from leaf.validation.instances import reference_errors

PUBLIC_EXAMPLES = tuple(
    path for path in sorted((ROOT / "examples").glob("*.html")) if path.stem != "corpus"
)
FEATURE_GALLERY = ROOT / "examples" / "developer" / "feature-gallery.html"
DEVELOPER_PAGES = tuple(sorted((ROOT / "examples" / "developer").glob("*.html")))
CORPUS_SOURCES = (*PUBLIC_EXAMPLES, *regression_sources(), *DEVELOPER_PAGES)


def authored_tags(document: SourceDocument) -> set[str]:
    """Every lf-* tag a source authors, its live samples' included."""
    return {element["tag"] for element in document.lf_elements}.union(
        *(authored_tags(sample["document"]) for sample in document.samples)
    )


def run_leaf(*args, input_text=None):
    """One `leaf` command in-process, for `prepare_page`."""
    result = CliRunner().invoke(cli_model.cli, list(args), input=input_text)
    assert result.exit_code == 0, f"leaf {' '.join(args)}: {result.output}"


def test_valid_source_activates_once_and_a_bad_save_keeps_it_live(page_dir):
    source = page_dir / "index.html"
    source.write_text(PAGE)

    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.created and initial.revision == 1
    existing = revisioning_model.activate_source(page_dir)
    assert existing.error is None and not existing.created and existing.revision == 1
    # A page whose reading has not moved answers from its last activation rather than
    # checking the source again.
    assert revisioning_model.activate_source(page_dir) is existing

    changed = PAGE.replace("<title>t</title>", "<title>working</title>")
    source.write_text(changed)
    first = revisioning_model.activate_source(page_dir)
    assert first.error is None and first.created and first.revision == 2
    revision = files_model.revision_path(page_dir, 2)
    from leaf.revision_artifact import artifact_name, read_artifact

    assert revision.name == artifact_name(2, read_artifact(page_dir, 2)) + ".html"
    assert revision.read_text() == changed

    unchanged = revisioning_model.activate_source(page_dir)
    assert not unchanged.created and unchanged.error is None
    assert unchanged.revision == 2 and files_model.list_revisions(page_dir) == [1, 2]

    source.write_text(PAGE.replace("</section>", ""))
    refused = revisioning_model.activate_source(page_dir)
    assert refused.revision == 2 and not refused.created
    assert refused.error and "issue" not in refused.error
    assert files_model.list_revisions(page_dir) == [1, 2]
    assert revision.read_text() == changed
    assert revisioning_model.activate_source(page_dir) is refused

    # Holding the refusal does not hold back the save that repairs it.
    source.write_text(changed.replace("working", "repaired"))
    repaired = revisioning_model.activate_source(page_dir)
    assert repaired.error is None and repaired.created and repaired.revision == 3


def test_later_events_do_not_veto_source_readings(page_dir):
    source = page_dir / "index.html"
    source.write_text(FLOW_PAGE)
    live = revisioning_model.activate_source(page_dir)
    assert live.error is None and live.revision == 1
    live = revisioning_model.activate_source(page_dir)

    # The source is the active revision, so an append leaves the answer in force.
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "flow"},
            "text": "is this still the flow?",
        },
    )
    assert revisioning_model.activate_source(page_dir) is live

    # Removing a thread's target activates immediately and detaches the thread;
    # the original anchor stays in the log.
    source.write_text(PAGE)
    removed = revisioning_model.activate_source(page_dir)
    assert removed.error is None and removed.created and removed.revision == 2
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["c1"]["anchor"] is None
    assert threads["c1"]["root"]["anchor"] == {"section": "flow"}
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c1"}
    )
    released = revisioning_model.activate_source(page_dir)
    assert released.error is None and not released.created and released.revision == 2

    # A tab still showing r1 may anchor a thread on the id r2 dropped. r2 is live
    # and neither activation nor `page check` lets the later event veto it.
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c2",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "flow"},
            "text": "one more on the flow",
        },
    )
    with fresh_process():
        settled = revisioning_model.activate_source(page_dir)
    assert settled.error is None and settled.revision == 2 and not settled.created
    assert check(page_dir).exit_code == 0

    # Events cannot repair an invalid source either; only a corrected save does.
    source.write_text(PAGE.replace("</section>", ""))
    refused = revisioning_model.activate_source(page_dir)
    assert refused.error and refused.revision == 2 and not refused.created
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c2"}
    )
    still_refused = revisioning_model.activate_source(page_dir)
    assert still_refused.error == refused.error and still_refused.revision == 2
    source.write_text(PAGE.replace("<title>t</title>", "<title>repaired</title>"))
    repaired = revisioning_model.activate_source(page_dir)
    assert repaired.error is None and repaired.created and repaired.revision == 3


def test_stamp_assigns_versions_to_the_exact_immutable_revision(page_dir):
    source = page_dir / "index.html"
    source.write_text(PAGE)
    runner = CliRunner()

    first = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "first cut"]
    )
    assert first.exit_code == 0, first.output
    first_note = events_model.read_events(page_dir)[-1]
    assert (first_note["version"], first_note["revision"]) == (1, 1)
    assert files_model.revision_path(page_dir, 1).read_text() == PAGE
    assert not (page_dir / "versions").exists()

    repeated = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "again"]
    )
    assert repeated.exit_code != 0
    assert "already stamped as v1" in repeated.output

    source.write_text(PAGE.replace("</section>", ""))
    refused = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "broken"]
    )
    assert refused.exit_code != 0
    assert files_model.list_revisions(page_dir) == [1]
    assert len(events_model.read_events(page_dir)) == 1

    changed = PAGE.replace("<title>t</title>", "<title>second</title>")
    source.write_text(changed)
    second = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "second cut"]
    )
    assert second.exit_code == 0, second.output
    notes = [
        event for event in events_model.read_events(page_dir) if event["kind"] == "note"
    ]
    assert [(event["version"], event["revision"]) for event in notes] == [
        (1, 1),
        (2, 2),
    ]
    assert files_model.revision_path(page_dir, 2).read_text() == changed
    assert not (page_dir / "versions").exists()


def test_page_events_name_revisions_and_stamps_name_both(page_dir):
    kinds = registry_storage.load_registry(page_dir)["$events"]["kinds"]
    for kind in ("comment", "action", "report"):
        required = kinds[kind]["record"]["required"]
        assert "revision" in required and "version" not in required
    required = kinds["note"]["record"]["required"]
    assert "revision" in required and "version" in required
    result = CliRunner().invoke(cli_model.cli, ["page", "--help"])
    assert result.exit_code == 0
    assert "\n  stamp " in result.output and "\n  publish " not in result.output


def test_choose_requires_an_id(page_dir):
    # Actions name their widget by id, so an interactive group can't go without one.
    registry = registry_storage.load_registry(page_dir)
    errs = fragment_errors(
        '<lf-options choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>',
        registry,
    )
    assert [finding.code for finding in errs] == ["needs-id"]


def test_sample_admits_interactive_widgets(page_dir):
    # The registry marks a sample's content quoted; the runtime leaves the
    # interactive widgets inside unwired. Validation is unchanged by the
    # wrapper: nesting rules (lf-option under lf-options) still hold.
    registry = registry_storage.load_registry(page_dir)
    errs = fragment_errors(
        '<lf-sample id="sp" label="a decision">'
        '<lf-options id="g" choose><lf-option id="o1"><strong>A</strong></lf-option></lf-options>'
        '<lf-board id="b"><lf-column id="c" label="To do">'
        '<lf-card id="k"><strong>Card</strong></lf-card></lf-column></lf-board>'
        "</lf-sample>",
        registry,
    )
    assert errs == []


def test_an_enclosing_widget_titles_any_number_of_independent_sources(page_dir):
    """An enclosing widget supplies one title without imposing source count or
    identity."""
    registry = registry_storage.load_registry(page_dir)
    first = (
        '<lf-options id="g-one" choose>'
        '<lf-option id="o-one"><strong>One</strong></lf-option>'
        "</lf-options>"
    )
    second = (
        '<lf-options id="g-two" choose>'
        '<lf-option id="o-two"><strong>Two</strong></lf-option>'
        "</lf-options>"
    )

    assert (
        fragment_errors(
            f'<lf-ask id="decision-one"><h2>Choose</h2><p>Context.</p>{first}</lf-ask>',
            registry,
        )
        == []
    )
    assert fragment_errors(first, registry) == []

    # Evidence can quote another obligation source without giving this obligation a
    # second live source. The runtime already excludes x-exhibit descendants from the
    # obligation list, so the authored boundary must read the same relation.
    with_evidence = (
        '<lf-ask id="decision-with-evidence"><h2>Choose</h2>'
        f'{first}<lf-sample id="quoted-example" label="another question">'
        f"{second}</lf-sample></lf-ask>"
    )
    assert fragment_errors(with_evidence, registry) == []

    # The obligation's title is what the shared name rule reads, so a heading in an
    # hgroup after its eyebrow, a subheading, or context before the heading all
    # name the obligation. A frame whose leading title is not a heading is refused.
    for titled in (
        f'<lf-ask id="d"><hgroup><p class="eyebrow">#5</p><h2>Choose</h2></hgroup>{first}</lf-ask>',
        f'<lf-ask id="d"><p class="eyebrow">#5</p><h2>Choose</h2>{first}</lf-ask>',
        f'<lf-ask id="d"><h2>Choose</h2><h3>Again</h3>{first}<p>After.</p></lf-ask>',
    ):
        assert fragment_errors(titled, registry) == []

    # A frame around another frame holds what that one holds, so a question with
    # parts asks through its inner frames.
    nested = (
        '<lf-ask id="outer"><h2>Choose</h2>'
        f'<lf-ask id="inner"><h3>First part</h3>{first}</lf-ask></lf-ask>'
    )
    assert fragment_errors(nested, registry) == []

    for untitled in (
        f'<lf-ask id="d"><p>Context.</p>{first}</lf-ask>',
        f'<lf-ask id="d"><strong>Choose</strong>{first}</lf-ask>',
    ):
        assert found(fragment_errors(untitled, registry), "untitled-question")

    # A context framing no widget, or only widgets that ask nothing, would show a
    # question the On me list never counts; a question answered in words is a
    # message's obligation instead. A retired source still counts: settling a
    # decision keeps its context.
    for empty in (
        '<lf-ask id="question">Is this enough?</lf-ask>',
        '<lf-ask id="decision-empty"><h2>Nothing to answer</h2></lf-ask>',
    ):
        assert found(fragment_errors(empty, registry), "empty-question", widgets=[])

    def lacking(lacks):
        return [{"at": "<lf-options id=g-one>", "line": 1, "lacks": lacks}]

    unasked = first.replace(" choose", "")
    assert found(
        fragment_errors(
            f'<lf-ask id="decision-unasked"><h2>Choose</h2>{unasked}</lf-ask>',
            registry,
        ),
        "empty-question",
        widgets=lacking({"choose": [True]}),
    )
    settled = first.replace(" choose", " choose settled")
    settled_obligation = (
        f'<lf-ask id="decision-settled"><h2>Chosen</h2>{settled}</lf-ask>'
    )
    assert fragment_errors(settled_obligation, registry) == []
    # The registry's `retired` is what says the flag ended an obligation; a flag
    # that merely stops a widget asking leaves the context framing nothing.
    unretired = copy.deepcopy(registry)
    del unretired["lf-options"]["x-awaits"]["retired"]
    assert found(
        fragment_errors(settled_obligation, unretired),
        "empty-question",
        widgets=lacking({"settled": [False]}),
    )
    # A quoted obligation is a mention, and its widgets ask nothing by design.
    assert (
        fragment_errors(
            '<lf-sample id="quoted-ask" label="an obligation">'
            f'<lf-ask id="decision-quoted"><h2>Choose</h2>{second}</lf-ask>'
            "</lf-sample>",
            registry,
        )
        == []
    )
    assert (
        fragment_errors(
            f'<lf-ask id="decision-crowded"><h2>Two decisions</h2>{first}{second}</lf-ask>',
            registry,
        )
        == []
    )


def test_command_references_preserve_the_package_owned_subject_roles(page_dir):
    """An existing id is insufficient when a typed reference names the wrong role."""
    registry = registry_storage.load_registry(page_dir)
    parser = SourceDocument(
        '<lf-test-plan id="hub" readings="goal">'
        '<lf-test-task id="goal" status="active"><strong>Goal</strong>'
        '<lf-test-worker id="worker" state="waiting" on="tree"><strong>Worker</strong>'
        '<lf-test-tree id="tree" source="project-worktrees"></lf-test-tree>'
        "</lf-test-worker></lf-test-task></lf-test-plan>"
    )

    errors = reference_errors(
        parser.lf_elements, registry, parser.ids, parser.by_id, thread_ids=set()
    )

    assert [(e.code, e.values["via"], e.values["where"]) for e in errors] == [
        ("reference-contract", "$work.widgets", {"role": "readings"}),
        ("reference-contract", "$work.widgets", {"role": "goal"}),
    ]


def test_a_readings_seat_answers_to_one_command(page_dir):
    """A command fills the seat it names, so each seat in a document is named by
    exactly one command: a second command naming it is refused, and so is a seat no
    command names, while each command naming its own seat passes."""
    registry = registry_storage.load_registry(page_dir)
    parser = SourceDocument(
        '<lf-test-plan id="one" readings="seat"></lf-test-plan>'
        '<lf-test-plan id="two" readings="seat"></lf-test-plan>'
        '<lf-test-plan id="three" readings="other"></lf-test-plan>'
        '<lf-test-summary id="seat"></lf-test-summary>'
        '<lf-test-summary id="other"></lf-test-summary>'
        '<lf-test-summary id="orphan"></lf-test-summary>'
    )

    errors = reference_errors(
        parser.lf_elements, registry, parser.ids, parser.by_id, thread_ids=set()
    )

    assert errors == [
        Finding(
            "owned-twice",
            "<lf-test-plan>",
            {
                "line": 1,
                "attr": "readings",
                "target": "seat",
                "first": "<lf-test-plan id=one>",
                "first_line": 1,
            },
        ),
        Finding(
            "unowned",
            "<lf-test-summary>",
            {"line": 1, "referrer": "lf-test-plan", "attr": "readings"},
        ),
    ]


def test_registry_examples_validate(page_dir):
    registry = registry_storage.load_registry(page_dir)
    assert any(
        tag.startswith("lf-") and "x-example" in entry
        for tag, entry in registry.items()
    )
    assert (
        validation_model.validate_registry_examples(registry, "vendored registry")
        is registry
    )


def test_registry_example_ids_are_independent_between_entries(page_dir):
    registry = registry_storage.load_registry(page_dir)
    registry["lf-diff"]["x-example"] = (
        '<lf-diff id="shared"><pre>one changed line</pre></lf-diff>'
    )
    registry["lf-code"]["x-example"] = (
        '<lf-code id="shared"><pre>one/file.py</pre></lf-code>'
    )

    assert (
        validation_model.validate_registry_examples(registry, "independent examples")
        is registry
    )


def test_every_path_a_diff_resolves_names_a_language_the_bundles_carry(page_dir):
    """The language vocabulary has two halves and they have to agree. `names` is the half
    an author writes and the half both language bundles are built from;
    `paths` is what a filename means, which is how a diff colours a file nobody declared
    a language for. A path resolving outside `names` would resolve to a language neither
    bundle is required to carry."""
    reg = json.loads((page_dir / "registry.json").read_text())
    names = set(reg["$languages"]["names"])
    paths = reg["$languages"]["paths"]
    assert (
        paths
    )  # a table with nothing in it would pass the check below and colour nothing
    assert set(paths.values()) <= names, (
        f"no bundle for {sorted(set(paths.values()) - names)}"
    )


PAGE_FIXTURES = (
    *CORPUS_SOURCES,
    *sorted((ROOT / "notes").glob("**/*.html")),
)


def test_the_fixture_check_reaches_the_developer_pages():
    """A moved `examples/developer/` would leave the check above with nothing to say
    about it rather than failing."""
    assert FEATURE_GALLERY in PAGE_FIXTURES


def test_every_widget_in_the_vocabulary_stands_in_a_corpus_source():
    """Eight sweeps in test_render.py read a widget inside a whole page, and their
    corpus is examples/, so a widget no example holds is one none of the eight has ever
    seen — a gap that reads as coverage, since the widget's own tests are green.
    lf-shot and lf-sample were outside them from the day each was written.
    examples/AGENTS.md carries the rest, including the shapes this floor doesn't
    reach."""
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    # The corpus is generated from the others, so it can only repeat their coverage.
    authored = set().union(
        *(authored_tags(SourceDocument(path.read_text())) for path in CORPUS_SOURCES)
    )
    tags = element_declarations(registry)
    assert tags, "no widgets read — an empty vocabulary demonstrates itself"
    undemonstrated = [tag for tag in tags if tag not in authored]
    assert not undemonstrated, (
        f"no corpus source holds {', '.join(undemonstrated)} — see examples/AGENTS.md"
    )


def test_every_default_widget_stands_in_the_feature_gallery():
    """The developer surface owns default presentation coverage directly.

    A public example may incidentally render the same widget, but that does not give a
    leaf developer one feature-indexed place to find and exercise it.
    """
    registry = json.loads(
        (schema_model.DEFAULT_PACKAGE / "registry.json").read_text(encoding="utf-8")
    )
    authored = authored_tags(
        SourceDocument(FEATURE_GALLERY.read_text(encoding="utf-8"))
    )
    tags = [tag for tag in registry if tag.startswith("lf-")]
    assert tags, "the default package declares no widgets"
    missing = [tag for tag in tags if tag not in authored]
    assert not missing, (
        f"the feature gallery has no focused sample for {', '.join(missing)} — "
        "see examples/AGENTS.md"
    )


def test_the_feature_gallery_eyebrows_index_literal_code_names():
    """Every showcased element is indexed by a code name, never descriptive prose."""
    authored = FEATURE_GALLERY.read_text(encoding="utf-8")
    gallery_registry = json.loads(
        (FEATURE_GALLERY.with_suffix(".page") / "registry.json").read_text(
            encoding="utf-8"
        )
    )
    apparatus = {
        tag for tag, entry in gallery_registry.items() if entry.get("x-exhibit")
    }
    assert apparatus
    eyebrows = re.findall(
        r'<p class="eyebrow bg-feature-elements">(.*?)</p>',
        authored,
        flags=re.DOTALL,
    )
    eyebrow_entries = [
        [entry.strip() for entry in eyebrow.split("·")] for eyebrow in eyebrows
    ]
    entries = [entry for eyebrow in eyebrow_entries for entry in eyebrow]
    assert entries
    assert all(re.fullmatch(r"[a-z][a-z0-9-]*", entry) for entry in entries), entries
    assert all(len(eyebrow) == len(set(eyebrow)) for eyebrow in eyebrow_entries), (
        "a feature eyebrow repeats a code name"
    )
    indexed = set(entries)
    assert apparatus.isdisjoint(indexed), (
        f"feature eyebrows expose gallery apparatus: {', '.join(sorted(apparatus & indexed))}"
    )
    tags = set(re.findall(r"<(lf-[a-z0-9-]+)[\s>]", authored)) - apparatus
    assert tags
    assert tags <= indexed, f"feature eyebrows omit {', '.join(sorted(tags - indexed))}"


def test_shipped_widget_purposes_live_in_their_descriptions():
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    titled = [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and "title" in entry
    ]
    assert not titled, f"widget purposes are duplicated in title: {', '.join(titled)}"


def test_a_playground_control_value_fits_its_kind_at_the_markup_boundary():
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)

    def errors(attributes, name="setting"):
        return fragment_errors(
            '<lf-ask id="kind-ask"><h2>Choose a setting</h2>'
            '<lf-playground id="kind-playground">'
            f'<lf-playground-control name="{name}" label="Setting" {attributes}>'
            "</lf-playground-control>"
            "<lf-playground-preview><p>Preview</p></lf-playground-preview>"
            "<lf-playground-output>Use this setting.</lf-playground-output>"
            "</lf-playground></lf-ask>",
            registry,
        )

    def refused(attributes):
        return [
            (e.code, e.values["keyword"], e.values["path"]) for e in errors(attributes)
        ]

    assert not errors('kind="range" value="-1.5" max="24"')
    assert not errors('kind="toggle" value="false"')
    assert not errors('kind="color" value="#A0b1c2"')
    assert not errors('kind="text" value="yes"')
    # A name, like an id, may start with a digit: an alert called 5xx keeps its name.
    assert not errors('kind="toggle" value="false"', name="5xx-pages")
    # A control is a Leaf element a user points at, so it takes a stable id.
    assert not errors('kind="toggle" value="false" id="setting-control"')
    # `class` and `style` are the page's styling hooks on a widget as on any element.
    assert not errors('kind="toggle" value="false" class="route"')
    assert not errors('kind="toggle" value="false" style="grid-column: 2"')
    # So are the attributes that describe any element and record nothing.
    assert not errors(
        'kind="toggle" value="false" title="Route" lang="en" dir="ltr"'
        ' aria-describedby="route-note" data-group="routing"'
    )
    # Leaf's own data-lf- namespace and `hidden` still validate.
    assert refused('kind="toggle" value="false" data-lf-said="x"') == [
        ("attribute-schema", "additionalProperties", [])
    ]
    assert refused('kind="toggle" value="false" hidden') == [
        ("attribute-schema", "additionalProperties", [])
    ]
    assert refused('kind="range" value="12"') == [("attribute-schema", "required", [])]
    assert refused('kind="range" value="twelve" max="24"') == [
        ("attribute-schema", "pattern", ["value"])
    ]
    assert refused('kind="toggle" value="yes"') == [
        ("attribute-schema", "enum", ["value"])
    ]
    assert refused('kind="color" value="red"') == [
        ("attribute-schema", "pattern", ["value"])
    ]


def test_a_playground_names_its_controls_within_itself(tmp_path, initialized_page):
    """A preset's setting and an instruction's value slot name a control of their
    own playground by `name` (a keyed x-refers), and names, choice values and a
    preset's settings are unique within their owner (x-unique). Both doors refuse a
    break before any browser draws it: message markup, where a reply's playground
    otherwise reaches the user with only a static check, and the page's own source."""
    page_dir = initialized_page(tmp_path / "page", ("playground",))

    def playground(ident, controls, presets="", output=""):
        return (
            f'<lf-playground id="{ident}">{controls}{presets}'
            "<lf-playground-preview><p>Preview</p></lf-playground-preview>"
            f"<lf-playground-output>Use {output}.</lf-playground-output>"
            "</lf-playground>"
        )

    tone = (
        '<lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">'
        '<lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>'
        '<lf-playground-choice value="bold" label="Bold"></lf-playground-choice>'
        "</lf-playground-control>"
    )
    size = (
        '<lf-playground-control name="size" label="Size" kind="range" value="2" '
        'max="4"></lf-playground-control>'
    )

    def preset(*names):
        return (
            '<lf-playground-preset label="Loud">'
            + "".join(
                f'<lf-playground-setting for="{name}" value="bold"></lf-playground-setting>'
                for name in names
            )
            + "</lf-playground-preset>"
        )

    def slot(name):
        return f'<lf-playground-value for="{name}"></lf-playground-value>'

    def reply(*playgrounds):
        markup = f'<lf-ask id="ask"><h2>Which?</h2>{"".join(playgrounds)}</lf-ask>'
        try:
            check_markup(
                page_dir,
                "reply",
                markup,
                [],
                publication=revision_publication(
                    page_dir, files_model.latest_revision(page_dir)
                ),
            )
        except Rejected as refused:
            return refused.findings
        return []

    def unmatched(name):
        return {
            "attr": "for",
            "target": name,
            "member": "lf-playground-control",
            "key": "name",
            "scope": "lf-playground",
        }

    # A value slot may stand inside the output's prose, as within a <strong>.
    assert (
        reply(playground("a", tone, preset("tone"), f"<strong>{slot('tone')}</strong>"))
        == []
    )
    assert found(
        reply(playground("a", tone, preset("tine"))),
        "unmatched-member",
        "<lf-playground-setting>",
        **unmatched("tine"),
    )
    # The name of a control in the playground beside it answers nothing here.
    assert found(
        reply(playground("a", tone, output=slot("size")), playground("b", size)),
        "unmatched-member",
        **unmatched("size"),
    )
    assert found(
        reply(playground("a", tone + tone.replace("Tone", "Again"))),
        "repeated-key",
        "<lf-playground-control>",
        key="name",
        value="tone",
    )
    assert found(
        reply(playground("a", tone.replace('"quiet" label', '"bold" label'))),
        "repeated-key",
        "<lf-playground-choice>",
        key="value",
        value="bold",
    )
    assert found(
        reply(playground("a", tone, preset("tone", "tone"))),
        "repeated-key",
        "<lf-playground-setting>",
        key="for",
        value="tone",
    )

    main = (
        '<lf-ask id="ask"><h2>Which?</h2>'
        + playground("a", tone + tone, output=slot("tone"))
        + "</lf-ask>"
    )
    (page_dir / "index.html").write_text(
        re.sub(r"<main>.*?</main>", f"<main>{main}</main>", PAGE, flags=re.DOTALL)
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings, "repeated-key", "<lf-playground-control>", key="name", value="tone"
    )


def test_a_playground_control_stands_in_the_rail_or_inside_its_preview():
    """A control may stand at any depth in the preview beside the item it changes
    (x-within) and still belongs to its playground: its name is unique there and a
    preset's setting names it. One outside every playground, or inside the
    instruction it would be read into, is refused, naming where it may stand."""
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    tone = (
        '<lf-playground-control name="{name}" label="Tone" kind="choice" value="quiet">'
        '<lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>'
        '<lf-playground-choice value="bold" label="Bold"></lf-playground-choice>'
        "</lf-playground-control>"
    )

    def errors(rail, beside_item, before="", in_output=""):
        return fragment_errors(
            f'<lf-ask id="placed-ask"><h2>Which tone?</h2>{before}'
            f'<lf-playground id="placed-playground">{rail}'
            '<lf-playground-preset label="Bold">'
            '<lf-playground-setting for="item-tone" value="bold">'
            "</lf-playground-setting></lf-playground-preset>"
            '<lf-playground-preview><div class="item"><p>Item</p>'
            f'<section class="item-settings">{beside_item}</section></div>'
            "</lf-playground-preview>"
            f"<lf-playground-output>Use these tones.{in_output}</lf-playground-output>"
            "</lf-playground></lf-ask>",
            registry,
        )

    assert not errors(tone.format(name="page-tone"), tone.format(name="item-tone"))
    assert not errors("", tone.format(name="item-tone"))
    assert [
        (e.code, e.values["key"])
        for e in errors(tone.format(name="item-tone"), tone.format(name="item-tone"))
    ] == [("repeated-key", "name")]
    (stray,) = errors(
        tone.format(name="page-tone"),
        tone.format(name="item-tone"),
        before=tone.format(name="stray"),
    )
    assert (stray.code, stray.values["within"]) == (
        "not-member",
        ["lf-playground-preview"],
    )
    (read_out,) = errors(
        tone.format(name="page-tone"),
        tone.format(name="item-tone"),
        in_output=tone.format(name="output-tone"),
    )
    assert read_out.code == "not-member"
    # Inside a nested playground's instruction, the outer preview around it is not
    # the control's own: its nearest playground is the inner one.
    inner = (
        '<lf-playground id="inner-playground">'
        '<lf-playground-control name="inner-tone" label="Tone" kind="toggle" '
        'value="false"></lf-playground-control>'
        "<lf-playground-preview><p>Inner</p></lf-playground-preview>"
        "<lf-playground-output>Use it."
        + tone.format(name="lost-tone")
        + "</lf-playground-output></lf-playground>"
    )
    (nested,) = errors(tone.format(name="page-tone"), inner)
    assert nested.code == "not-member"

    # A quotation cannot supply a control to the surrounding playground, even if
    # its preview surrounds the quotation. Its names neither collide nor resolve.
    quoted = (
        '<lf-sample id="quoted-control" label="Control example">'
        + tone.format(name="item-tone")
        + "</lf-sample>"
    )
    assert [e.code for e in fragment_errors(quoted, registry)] == ["not-member"]
    assert [e.code for e in errors(tone.format(name="page-tone"), quoted)] == [
        "not-member"
    ]
    quoted_records = SourceDocument(
        f'<lf-playground id="quoted-member-scope">{quoted}'
        '<lf-playground-output><lf-playground-value for="item-tone">'
        "</lf-playground-value></lf-playground-output></lf-playground>"
    ).lf_elements
    assert [
        e.code
        for e in reference_errors(quoted_records, registry, set(), {}, thread_ids=set())
    ] == ["unmatched-member"]
    assert [
        e.code
        for e in errors(
            tone.format(name="item-tone"), tone.format(name="page-tone") + quoted
        )
    ] == ["not-member"]
    # The quoted playground itself still owns the controls written inside it.
    assert not errors(
        tone.format(name="item-tone"),
        '<lf-sample id="quoted-playground" label="Playground example">'
        + inner.replace(tone.format(name="lost-tone"), "")
        + "</lf-sample>",
    )


def test_reply_validates_widget_markup(page_dir):
    """The current layer checks replies; older layers do not constrain their markup."""
    path = page_dir / "registry.json"
    current = path.read_text()
    earlier = json.loads(current)
    del earlier["lf-diagram"]
    path.write_text(json.dumps(earlier))
    publish(page_dir)
    path.write_text(current)
    publish(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, "c1"),
                "--text",
                "See:",
                "--markup",
                markup,
            ],
        )

    bad = reply('<lf-diagram id="f"><pre>graph LR</pre><b>x</b></lf-diagram>')
    assert bad.exit_code != 0
    assert "its body is one <pre> holding the text" in bad.output
    good = reply('<lf-diagram id="f"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>')
    assert good.exit_code == 0, good.output
    event = events_model.read_events(page_dir)[-1]
    assert event["kind"] == "reply"
    assert event["author"] == "agent"
    assert event["text"] == "See:"
    assert event["markup"].startswith("<lf-diagram")


def test_a_reply_drawn_before_posting_runs_no_script_its_thread_would_not(page_dir):
    """A thread inserts a message's markup through `template.innerHTML`, which runs no
    script in it, so the browser run that draws the message's widgets before it posts
    leaves its scripts unrun too, rather than refusing it for code the user never runs."""
    publish(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "See:",
            "--markup",
            (
                '<lf-diagram id="f"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>'
                '<script type="module">throw new Error("inert-message-script")</script>'
            ),
        ],
    )
    assert posted.exit_code == 0, posted.output
    assert "inert-message-script" in events_model.read_events(page_dir)[-1]["markup"]


def test_reply_validates_typed_references_against_the_page(page_dir):
    """Reply markup naming a page element of the wrong role never freezes, nor does
    a command naming the page's seat, which it would fill from another document."""
    subjects = (
        '<lf-test-plan id="hub" readings="seat"><lf-test-task id="goal" status="active">'
        "<strong>Goal</strong>" + COMMAND_SUBJECTS + "</lf-test-task></lf-test-plan>"
        '<lf-test-summary id="seat"></lf-test-summary>'
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</section>", subjects + "</section>")
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "Act?"}
    )

    def reply(markup):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, "c1"),
                "--text",
                "Choose:",
                "--markup",
                markup,
            ],
        )

    swapped = reply('<lf-test-plan id="quoted" readings="goal"></lf-test-plan>')
    assert swapped.exit_code != 0
    assert 'where role="readings"' in words(swapped.output)

    borrowed = reply('<lf-test-plan id="quoted" readings="seat"></lf-test-plan>')
    assert borrowed.exit_code != 0
    assert "outside its own document" in borrowed.output

    valid = reply(
        '<lf-test-plan id="quoted" readings="quoted-seat"></lf-test-plan>'
        '<lf-test-summary id="quoted-seat"></lf-test-summary>'
    )
    assert valid.exit_code == 0, valid.output


def test_widget_ids_are_one_universe_across_page_and_replies(page_dir):
    """The runtime resolves actions document-wide by id, so a reply widget must not
    reuse a page id — and a later version must not take a reply's."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup, *, for_event=None, to="c1"):
        route = (
            ["thread", "reply", "--done", response_reference(page_dir, for_event)]
            if for_event
            else ["thread", "reply", str(page_dir), to]
        )
        return CliRunner().invoke(
            cli_model.cli,
            [
                *route,
                "--text",
                "Pick:",
                "--markup",
                markup,
            ],
        )

    def question(decision_id, markup):
        return f'<lf-ask id="{decision_id}"><h2>Pick?</h2>{markup}</lf-ask>'

    # `flag-first` is an option on the page (PAGE fixture) — refused.
    clash = reply(
        question(
            "o-decision",
            '<lf-options id="o" choose><lf-option id="flag-first"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event="c1",
    )
    assert clash.exit_code != 0 and "flag-first" in clash.output
    fresh = reply(
        question(
            "q1-decision",
            '<lf-options id="q1" choose><lf-option id="q1-a"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event="c1",
    )
    assert fresh.exit_code == 0, fresh.output
    # A second reply can't reuse the first reply's ids either, nor its own within itself.
    again = reply(
        question(
            "q1-decision",
            '<lf-options id="q1" choose><lf-option id="q1-b"><strong>B</strong></lf-option></lf-options>',
        )
    )
    assert again.exit_code != 0 and "q1" in again.output
    selfdup = reply(
        question(
            "q2-decision",
            '<lf-options id="q2" choose><lf-option id="q2"><strong>B</strong></lf-option></lf-options>',
        )
    )
    assert selfdup.exit_code != 0 and "duplicate ids" in selfdup.output
    # Text claims no ids however it quotes a tag — only the `markup` field does, and
    # a user's message never carries one (the log is append-only; a false claim
    # would deadlock every future version).
    follow_up = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": "c1",
            "text": 'why not <lf-diagram id="quoted"> here?',
        },
    )
    ok = reply(
        question(
            "quoted-decision",
            '<lf-options id="quoted" choose><lf-option id="quoted-a"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event=follow_up["id"],
        to=follow_up["id"],
    )
    assert ok.exit_code == 0, ok.output
    # And a new version taking the reply's id fails check.
    (page_dir / "index.html").write_text(
        PAGE.replace('<section id="plan">', '<section id="plan"><p id="q1">stolen</p>')
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "ids-taken-by-messages", ids=["q1"])


def test_the_runtimes_lf_id_namespace_is_off_limits(page_dir):
    """leaf.js coins document ids under lf- for its own chrome — lf-composer-quote —
    and points ARIA at them. An authored id there would aim those references at the page
    instead, silently. One rule over both places an id can be authored: a version, and
    the widget markup in Claude's reply."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            '<section id="plan">', '<section id="plan"><p id="lf-msg-7">mine</p>'
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "reserved-ids", ids=["lf-msg-7"])
    (page_dir / "index.html").write_text(PAGE)

    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Pick:",
            "--markup",
            (
                '<lf-ask id="pick-decision"><h2>Pick?</h2>'
                '<lf-options id="lf-pick" choose>'
                '<lf-option id="o1"><strong>A</strong></lf-option>'
                "</lf-options></lf-ask>"
            ),
        ],
    )
    assert reply.exit_code != 0
    assert "lf- namespace" in reply.output and "lf-pick" in reply.output


# ---------- messages: text is Markdown for the browser, markup is the gate's ----------


def test_agent_messages_preserve_a_single_space(page_dir):
    """Only the zero-length string is empty; every typed character reaches the log."""
    empty = CliRunner().invoke(
        cli_model.cli, ["thread", "create", str(page_dir), "--text", ""]
    )
    assert empty.exit_code != 0
    assert json.loads(empty.stderr)["error"] == (
        "empty text (pass --text, --file PATH or a pipe on stdin; --file - reads"
        " any stdin)"
    )

    opened = comment(page_dir, "--text", " ")
    assert opened.exit_code == 0, opened.output
    root = json.loads(opened.output)

    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--text",
            " ",
        ],
    )
    assert replied.exit_code == 0, replied.output
    messages = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] in {"comment", "reply"}
    ]
    assert [message["text"] for message in messages] == [" ", " "]


def test_a_body_reads_only_piped_stdin(monkeypatch):
    """A body given by neither --text nor --file comes from a pipe or file; a socket
    the caller keeps open, as Claude Code hands a command spanning lines, gives none
    at once rather than being waited on."""
    held, caller = socket.socketpair()
    with held, caller:
        # A regression waits on the socket; the timeout turns that into a failure.
        held.settimeout(STATED_TIMEOUT)
        monkeypatch.setattr(sys, "stdin", held.makefile("r"))
        assert cli_model.read_body(None, None) is None

    read, write = os.pipe()
    os.write(write, b"Checked the label row.")
    os.close(write)
    with open(read) as piped:
        monkeypatch.setattr(sys, "stdin", piped)
        assert cli_model.read_body(None, None) == "Checked the label row."


def _commands(group, path=()):
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            yield from _commands(command, (*path, name))
        else:
            yield (
                " ".join((*path, name)),
                {
                    param.name
                    for param in command.params
                    if isinstance(param, click.Option)
                },
            )


def test_every_body_takes_text_and_file():
    """Every command that takes a body takes it the same ways: `--text` inline,
    `--file` naming a file or `-` for stdin, else a pipe on stdin
    (`cli.body_options`)."""
    bodies = {
        name: params & {"text", "body_file"}
        for name, params in _commands(cli_model.cli)
        if params & {"text", "body_file"}
    }
    assert "thread reply" in bodies
    assert {name for name, given in bodies.items() if len(given) < 2} == set()


def test_a_body_comes_from_text_a_file_or_stdin(page_dir, tmp_path):
    """One reply's text, and one plan's JSON, by each route the convention offers;
    giving both options is refused before anything is written."""
    reply = tmp_path / "reply.md"
    reply.write_text("Checked the **label** row.\n", encoding="utf-8")
    runner = CliRunner()
    opened = json.loads(comment(page_dir, "--text", "Opening.").output)

    def posted(*body, stdin=None):
        result = runner.invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), opened["id"], *body],
            input=stdin,
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)["text"]

    assert posted("--file", str(reply)) == "Checked the **label** row.\n"
    assert posted("--file", "-", stdin="From stdin.") == "From stdin."
    assert posted(stdin="Piped.") == "Piped."
    both = runner.invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), opened["id"], "--text", "a"]
        + ["--file", str(reply)],
    )
    assert both.exit_code == 2
    assert "not both" in json.loads(both.stderr)["error"]
    renamed = runner.invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), opened["id"], "--title", "Label row"],
        input="Not the text.",
    )
    assert renamed.exit_code == 0, renamed.output
    assert [
        record["kind"] for record in map(json.loads, renamed.stdout.split("\n")[:-1])
    ] == ["thread_title"]

    planned = runner.invoke(
        cli_model.cli,
        ["task", "plan", str(page_dir), "--text"]
        + ['[{"depth": 0, "title": "Check the rows", "state": "working"}]'],
    )
    assert planned.exit_code == 0, planned.output


def test_the_wire_ships_a_message_as_logged(page_dir):
    """The wire adds nothing to the log: text is Markdown the page's vendored runtime
    renders (test_render holds that side), markup is the fragment the CLI gate
    validated, and the only vocabulary a page's frozen layer has to keep speaking is
    the log's own, which $events stamps."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "text": "two things:\n\n- one\n- **two**",
        },
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Fixed in `poll()`.",
            "--markup",
            '<lf-diagram id="fix"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>',
        ],
    )
    assert result.exit_code == 0, result.output
    wire = {e["kind"]: e for e in page_state(page_dir)["events"]}
    assert wire["comment"]["text"] == "two things:\n\n- one\n- **two**"
    assert "html" not in wire["comment"] and "html" not in wire["reply"]
    assert wire["reply"]["markup"].startswith("<lf-diagram")


def test_each_agent_session_posts_as_its_own_voice(page_dir, monkeypatch):
    """Several worker sessions report to one page. Each agent-authored event
    carries its poster's display name and session id from the poster's own
    environment, so the log tells the voices apart by id; the claim — the
    watcher the panel names — and every publication stay the hub's, untouched
    by a worker's post."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "hub")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    monkeypatch.setenv("LEAF_AGENT", "Hub")
    _tasks_version(page_dir, "active")
    service_model.claim_page(page_dir)
    published(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "status?"}
    )

    reference = response_reference(page_dir, "c1")

    def reply(text):
        return CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), "c1", "--text", text],
        )

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    assert _report(page_dir, "t-parser", "status", "value=review").exit_code == 0
    answered = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", "--done", reference, "--text", "The work is ready."],
    )
    assert answered.exit_code == 0, answered.output
    assert json.loads(answered.output)["responds"] == "c1"

    indexed = reply("indexing done")
    assert indexed.exit_code == 0, indexed.output
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-2")
    monkeypatch.setenv("LEAF_AGENT", "Crawler")
    assert reply("crawl running").exit_code == 0

    events = events_model.read_events(page_dir)
    notes = [e for e in events if e["kind"] == "note"]
    assert [(e["agent"], e["session"]) for e in notes] == [("Hub", "hub")]
    report = next(e for e in events if e["kind"] == "report")
    assert (report["agent"], report["session"]) == ("Indexer", "worker-1")
    replies = [e for e in events if e["kind"] == "reply"]
    assert [(e["agent"], e["session"]) for e in replies] == [
        ("Indexer", "worker-1"),
        ("Indexer", "worker-1"),
        ("Crawler", "worker-2"),
    ]
    session = service_model.page_claim(page_dir)
    assert session["id"] == "hub" and session["agent"] == "Hub"
    assert page_state(page_dir)["agent"] == "Hub"


def test_ephemeral_reply_takes_the_move_in_hand_and_leaves_it_owed(claimed):
    """Progress on a move the agent owes is the user's first sign it is handled: one
    write posts it in the thread and takes the move in hand, Working with the update's text as its line,
    while the answer stays owed. The line is the status's, so the update is one line."""
    published(claimed)
    root = append_command(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check the schedule.",
        },
    )

    reference = response_reference(claimed, root)

    def progress(text, *, proactive=False):
        route = (
            ["thread", "reply", str(claimed), root["id"]]
            if proactive
            else ["thread", "reply", reference]
        )
        return CliRunner().invoke(
            cli_model.cli,
            [
                *route,
                "--ephemeral",
                "--text",
                text,
            ],
        )

    refused = progress("Checking the camera.\n\nThen the clock.")
    assert refused.exit_code != 0 and "reply event is invalid" in refused.output

    posted = progress("Checking the camera.")
    assert posted.exit_code == 0, posted.output
    update = json.loads(posted.output)
    assert update["ephemeral"] is True and "responds" not in update
    start = todos_model.start_reading(update)
    assert (start["item"], start["text"]) == (root["id"], "Checking the camera.")
    assert events_model.read_events(claimed)[-1] == update
    [working] = page_state(claimed)["workflows"]
    assert (working["stage"], working["detail"]) == ("working", "Checking the camera.")
    assert working["obligation"] == f"update:{root['id']}"
    # The same exact input remains owed; newer progress replaces the Working line.
    again = progress("Checking the clock.")
    assert again.exit_code == 0, again.output
    [working] = page_state(claimed)["workflows"]
    assert working["detail"] == "Checking the clock."

    answer = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "The schedule works.",
        ],
    )
    assert answer.exit_code == 0, answer.output
    completed = json.loads(answer.output)
    assert completed["responds"] == root["id"]
    state = page_state(claimed)
    assert state["workflows"] == []
    # Once nothing is owed, an update takes nothing in hand, so it may run long.
    later = progress("The clock drifts.\n\nWatching it overnight.", proactive=True)
    assert later.exit_code == 0, later.output
    assert [json.loads(line)["kind"] for line in later.output.splitlines()] == ["reply"]


def test_an_agent_reply_asks_the_user_only_through_a_declared_obligation(page_dir):
    """A reply leaves the user something to answer only by declaring an obligation,
    such as `--obligation` on a question asked in words; its words alone ask
    nothing."""
    published(page_dir)
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "status?"},
    )

    def reply(*options):
        return CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), root["id"], *options],
        )

    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, root["id"]),
            "--text",
            "Complete.",
        ],
    )
    assert answered.exit_code == 0, answered.output
    worded = reply("--text", "Which store?")
    assert worded.exit_code == 0, worded.output
    asking = reply("--text", "Which store?", "--obligation")
    assert asking.exit_code == 0, asking.output
    assert [item["id"] for item in state_json(page_dir)["queues"]["on_user"]] == [
        f"message:{json.loads(asking.output)['id']}"
    ]


def test_an_agent_edits_predecessor_messages_without_rewriting_history(
    page_dir, monkeypatch
):
    """An edit changes what the thread says, not what the log said before it.

    Roots and replies are both messages, and the posting session is their authoring
    identity. The raw log therefore keeps each original and the revision as separate
    events, while user-facing folded readings show the latest words with an edited
    marker. Exact thread event selection returns the original and edit records without
    copying either into page state. A successor agent may revise predecessor agent
    speech; user-authored messages remain outside the author edit operation.
    """
    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")

    opened = comment(page_dir, "--text", "The index is still pending.")
    assert opened.exit_code == 0, opened.output
    root = json.loads(opened.output)
    user = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "user-thread",
            "author": "user",
            "revision": 1,
            "text": "What about the crawl?",
        },
    )
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, user["id"]),
            "--text",
            "The crawl is paused.",
        ],
    )
    assert answered.exit_code == 0, answered.output
    reply = json.loads(answered.output)

    revisions = []
    for message, text in [
        (root, "The index is complete."),
        (root, "The index is complete and verified."),
        (reply, "The crawl is running."),
    ]:
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(page_dir),
                message["id"],
                "--text",
                text,
            ],
        )
        assert result.exit_code == 0, result.output
        revisions.append(json.loads(result.output))

    history_result = CliRunner().invoke(
        cli_model.cli, ["page", "events", str(page_dir)]
    )
    assert history_result.exit_code == 0, history_result.output
    events = [json.loads(line) for line in history_result.output.splitlines()]
    originals = {
        event["id"]: event for event in events if event["kind"] in {"comment", "reply"}
    }
    assert originals[root["id"]]["text"] == "The index is still pending."
    assert originals[reply["id"]]["text"] == "The crawl is paused."
    assert [(event["message"], event["text"]) for event in revisions] == [
        (root["id"], "The index is complete."),
        (root["id"], "The index is complete and verified."),
        (reply["id"], "The crawl is running."),
    ]

    state_result = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state_result.exit_code == 0, state_result.output
    state = json.loads(state_result.output)
    assert all(
        set(thread)
        == {"id", "title", "anchor", "detached_from", "resolved", "unread", "attention"}
        for thread in state["threads"]
    )
    expected = {root["id"]: [root["id"]], user["id"]: [user["id"], reply["id"]]}
    shown = {}
    for thread, ids in expected.items():
        selected = CliRunner().invoke(
            cli_model.cli, ["page", "state", str(page_dir), thread]
        )
        assert selected.exit_code == 0, selected.output
        content = json.loads(selected.output)["content"]
        assert [message["message"] for message in content] == ids
        shown |= {message["message"]: message for message in content}
    # A reading shows each edited message in its latest words, marked edited.
    assert shown[root["id"]]["text"] == "The index is complete and verified."
    assert shown[reply["id"]]["text"] == "The crawl is running."
    assert shown[root["id"]].get("edited") and shown[reply["id"]].get("edited")

    before = events_model.read_events(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-2")
    monkeypatch.setenv("LEAF_AGENT", "Crawler")
    foreign = CliRunner().invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), root["id"], "--text", "Taken over."],
    )
    assert foreign.exit_code == 0, foreign.output
    replacement = json.loads(foreign.output)
    assert replacement["session"] == "worker-2"
    assert replacement["message"] == root["id"]
    before = events_model.read_events(page_dir)
    user_edit = CliRunner().invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), user["id"], "--text", "Changed."],
    )
    assert user_edit.exit_code != 0
    assert "is not agent-authored" in user_edit.output
    assert events_model.read_events(page_dir) == before
    sessionless = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "No recorded session owns this.",
        },
    )
    before_unidentified_edit = events_model.read_events(page_dir)
    unidentified = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "edit",
            str(page_dir),
            sessionless["id"],
            "--text",
            "Changed.",
        ],
    )
    assert unidentified.exit_code == 0, unidentified.output
    assert before_unidentified_edit[-1]["id"] == sessionless["id"]
    assert json.loads(unidentified.output)["message"] == sessionless["id"]


def test_a_user_revision_is_a_turn_the_agent_answers(page_dir, monkeypatch):
    """The user rewriting their message speaks again, under the edit's id.

    The thread shows the new wording in place of the old, and the agent owes it an
    answer as it would a reply: addressed to the message the edit rewrote, delivered
    with the wording it replaced, settled by a reply naming the edit, and reopening a
    thread the user had closed. Only the words the user wrote are theirs to revise.
    """
    from leaf import delivery as delivery_model
    from leaf.event_log import EventRefused

    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")

    def reply_for(event_id, text):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, event_id),
                "--text",
                text,
            ],
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    def owed_answers():
        return [
            (item["input"], item["message"], item["answer"])
            for item in owed(state_json(page_dir))
        ]

    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Chart 2024."},
    )
    answer = reply_for(asked["id"], "Charted 2024.")
    assert owed_answers() == []

    edit = append_command(
        page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": asked["id"],
            "text": "Chart 2025.",
        },
    )
    assert edit["attention"] is True
    assert owed_answers() == [
        (
            edit["id"],
            asked["id"],
            {"kind": "reply", "parent": asked["id"], "responds": edit["id"]},
        )
    ]
    with service_model.PageTransaction(page_dir) as page:
        stored = next(event for event in page.events if event["id"] == edit["id"])
        delivered = delivery_model.freeze_delivery(
            [delivery_model.batch_data(page_dir, page, [stored])]
        )
    [batch] = delivered["batches"]
    [event] = batch["events"]
    assert (event["text"], event["was"]) == ("Chart 2025.", "Chart 2024.")
    assert any("rewrote" in batch["handling"][ref] for ref in event["handling"])
    [thread] = batch["threads"]
    assert [m["text"] for m in thread["messages"]] == ["Chart 2025.", "Charted 2024."]

    settled = reply_for(edit["id"], "Charted 2025 instead.")
    assert (settled["parent"], settled["responds"]) == (asked["id"], edit["id"])
    assert owed_answers() == []

    append_command(
        page_dir, {"kind": "resolve", "author": "user", "parent": asked["id"]}
    )
    again = append_command(
        page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": asked["id"],
            "text": "Chart both.",
        },
    )
    [thread] = state_json(page_dir)["threads"]
    assert thread["resolved"] is None
    assert [item[0] for item in owed_answers()] == [again["id"]]

    # A question asked after the rewritten words stays the user's: a rewrite up the
    # thread is owed an answer, and answers nothing asked since.
    asking = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            response_reference(page_dir, again["id"]),
            "--text",
            "Which year goes first?",
            "--obligation",
        ],
    )
    assert asking.exit_code == 0, asking.output
    typo = append_command(
        page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": asked["id"],
            "text": "Chart both!",
        },
    )
    [thread] = state_json(page_dir)["threads"]
    assert thread["attention"]["kind"] == "needs_user", thread["attention"]
    assert [item[0] for item in owed_answers()] == [typo["id"]]

    reaction = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": answer["id"], "token": "keep"},
    )
    before = events_model.read_events(page_dir)
    for target, refusal in [
        (answer["id"], "foreign-message"),
        (reaction["id"], "wordless-message"),
        ("no-such-message", "unknown-message"),
    ]:
        with pytest.raises(EventRefused) as refused:
            append_command(
                page_dir,
                {"kind": "edit", "author": "user", "message": target, "text": "x"},
            )
        assert refused_on(refused.value).code == refusal
    assert events_model.read_events(page_dir) == before


def test_a_rewritten_message_stays_out_of_the_suggested_summary(page_dir, monkeypatch):
    """The newest exchange stays verbatim when the user rewrites its words.

    A long thread's digest suggests folding all but its last two messages; rewriting
    the newest user message is a turn the agent owes, and it moves no message into
    that range."""
    from leaf.revision_artifact import active_enclosing
    from leaf.thread_context import batch_threads

    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    opened = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "U1"},
    )
    said = opened
    for n in (1, 2, 3):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, said["id"]),
                "--text",
                f"A{n}",
            ],
        )
        assert result.exit_code == 0, result.output
        if n < 3:
            said = append_command(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user",
                    "parent": opened["id"],
                    "text": f"U{n + 1}",
                },
            )

    def suggested(event):
        with service_model.PageTransaction(page_dir) as page:
            [digest] = batch_threads(page.events, [event], active_enclosing(page_dir))
            text = {item["id"]: item.get("text") for item in page.events}
        hint = digest["summary_hint"]
        return text[hint["from"]], text[hint["through"]]

    assert suggested(said) == ("U1", "A2")
    rewrite = append_command(
        page_dir,
        {"kind": "edit", "author": "user", "message": said["id"], "text": "U3 again"},
    )
    assert suggested(rewrite) == ("U1", "A2")


def test_a_rewrite_lands_only_on_the_words_it_was_written_over(page_dir):
    """A tab still drawing a message's old words opened its rewrite on them, and its
    save silently replaced the newer rewrite another tab had made. A rewrite names the
    revision it was written over, and the door refuses it once that revision is not the
    message's latest, telling the user to edit again. Words the message already says are
    no rewrite."""
    publish(page_dir)
    said = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "North."},
    )

    def rewrite(text, base):
        return append_command(
            page_dir,
            {
                "kind": "edit",
                "author": "user",
                "message": said["id"],
                "text": text,
                "base": base,
            },
        )

    south = rewrite("South.", said["id"])
    with pytest.raises(events_model.EventRefused) as stale:
        rewrite("East.", said["id"])
    assert stale.value.user == "The message changed while I edited it; edit it again."
    west = rewrite("West.", south["id"])
    with pytest.raises(events_model.EventRefused):
        rewrite("West.", west["id"])
    thread = event_folds_model.build_threads(events_model.read_events(page_dir), {})[
        said["id"]
    ]
    assert [message["text"] for message in thread["msgs"]] == ["West."]
    assert thread["msgs"][0]["edited"]["was"] == "South."


def test_edit_uses_the_captured_contract_when_the_candidate_registry_is_invalid(
    page_dir, monkeypatch
):
    """An edit uses the active revision's contract, not a broken candidate."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    message = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Indexer",
            "session": "worker-1",
            "revision": 1,
            "text": "The old layer can render this message.",
        },
    )
    registry = files_model.read_json(page_dir / "registry.json")
    del registry["$events"]["kinds"]["edit"]
    cleanup_model.write_json(page_dir / "registry.json", registry)
    before = events_model.read_events(page_dir)

    result = CliRunner().invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), message["id"], "--text", "Revised."],
    )

    assert result.exit_code == 0, result.output
    assert events_model.read_events(page_dir)[:-1] == before
    assert events_model.read_events(page_dir)[-1]["text"] == "Revised."


def test_markup_enters_only_through_the_cli_gate(server, page_dir):
    """The browser door refuses the field rather than silently dropping it: everything
    the log holds under `markup` has been through `check_markup`, which is what lets
    the thread structure and the panel index it unasked."""
    publish(page_dir)
    before = events_model.read_events(page_dir)
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "revision": 1,
                "text": "hi",
                "markup": '<lf-diagram id="m"><pre>graph LR\n  A --> B</pre></lf-diagram>',
            }
        ).encode(),
    )
    assert status == 400
    assert "markup" in json.loads(body)["error"]
    assert events_model.read_events(page_dir) == before


@pytest.mark.parametrize(
    "markup", ["", '<lf-diagram id="f"><pre>graph LR\n  A --> B</pre></lf-diagram>']
)
def test_reply_refuses_a_missing_current_layer(page_dir, markup):
    """An addressed reply validates current source, even when its text needs no widget."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    (page_dir / "registry.json").unlink()
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    reference = response_reference(page_dir, "c1")
    before = events_model.read_events(page_dir)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "See:",
            "--markup",
            markup,
        ],
    )
    assert result.exit_code != 0, result.output
    assert "registry.json missing" in result.output
    assert "run `leaf page init`" in result.output
    assert events_model.read_events(page_dir) == before


def test_comment_requires_the_registry_its_runtime_reads(page_dir):
    published(page_dir)
    (page_dir / "registry.json").unlink()
    before = events_model.read_events(page_dir)
    result = comment(page_dir, "--quote", "Ship dark", "--text", "Still posts")
    assert result.exit_code != 0
    assert (
        "registry.json missing" in result.output
        and "run `leaf page init`" in result.output
    )
    assert events_model.read_events(page_dir) == before


def test_note_refuses_a_version_that_fails_check(page_dir):
    (page_dir / "index.html").write_text(PAGE.replace("</section>", ""))
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "stamp", str(page_dir), "--text", "broken"],
    )
    assert result.exit_code != 0
    assert "refusing to stamp" in result.output
    assert live_versions(page_dir) == []


def test_example_layer_selects_existing_packages(tmp_path, monkeypatch):
    examples = ROOT / "examples"
    packages = json.loads((examples / "layer.json").read_text(encoding="utf-8"))
    monkeypatch.chdir(tmp_path)

    assert packages
    assert all(not Path(name).is_absolute() for name in packages)
    # The manifest is what every corpus floor reads, so it has to be the whole
    # directory rather than whichever packages someone remembered to add.
    assert sorted(packages) == sorted(
        entry.name
        for entry in schema_model.BUNDLED_PACKAGES.iterdir()
        if entry.is_dir() and entry != schema_model.DEFAULT_PACKAGE
    )
    resolved = layer_model.resolve_packages(tuple(packages))
    assert resolved == [schema_model.BUNDLED_PACKAGES / name for name in packages]
    assert layer_model.checked_inputs(resolved) == resolved


def test_a_seed_no_writer_could_send_stops_the_page_it_seeds(tmp_path, monkeypatch):
    """An example's companion log enters through the append door, so a seed in a
    shape no real page holds fails the build that lays it in, rather than reaching
    the site and every sweep. A line copied from a stored log is that shape: it
    carries what admission derives, which goes stale as the contract moves."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    source = tmp_path / "seeded.html"
    source.write_text(PAGE)
    stored = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Why this plan?",
        "anchor": {"section": "plan"},
        "attention": True,
    }
    source.with_suffix(".jsonl").write_text(json.dumps(stored) + "\n")
    with pytest.raises(RuntimeError, match="attention"):
        prepare_page(
            tmp_path / "page", read_fixture(source), run_leaf, final_status=None
        )
    del stored["attention"]
    source.with_suffix(".jsonl").write_text(json.dumps(stored) + "\n")
    page = tmp_path / "admitted"
    prepare_page(page, read_fixture(source), run_leaf, final_status=None)
    [seeded] = [e for e in events_model.read_events(page) if e["kind"] == "comment"]
    assert seeded["attention"] is True


def test_page_state_reads_reactions_as_marks(page_dir):
    """`page state` lists every reaction in force, beside threads that
    leave a bare one out — paint on the page is not a thread — and takes a
    reaction back in once someone answers it, as the panel does. Its durable token
    is enough; packages may add an explanation, but the default layer does not
    prescribe one."""
    published(page_dir)
    bare = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "shorten",
            "anchor": {"section": "plan", "quote": "Ship dark"},
        },
    )
    answered = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "token": "change"},
    )
    # A bare reaction owes no response; adding speech to it is proactive.
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            answered["id"],
            "--text",
            "Which part?",
        ],
    )
    assert posted.exit_code == 0, posted.output
    reply = json.loads(posted.output)
    state = state_json(page_dir)
    assert [t["id"] for t in state["threads"]] == [answered["id"]]
    selected = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), answered["id"]]
    )
    assert selected.exit_code == 0, selected.output
    assert [m["message"] for m in json.loads(selected.output)["content"]] == [
        answered["id"],
        reply["id"],
    ]
    assert [(r["token"], r["thread"]) for r in state["reactions"]] == [
        ("shorten", bare["id"]),
        ("change", answered["id"]),
    ]
    assert state["reactions"][0]["anchor"]["quote"] == "Ship dark"


def test_an_agent_names_and_renames_a_thread_without_changing_its_speech(
    page_dir,
):
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "I was wondering whether the workshop should use the terrace.",
        },
    )
    runner = CliRunner()
    assert state_json(page_dir)["threads"][0]["title"] is None
    named = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, root),
            "--text",
            "The terrace works.",
            "--title",
            "Workshop venue",
        ],
    )
    assert named.exit_code == 0, named.output
    reply = json.loads(named.output)
    assert reply["title"] == "Workshop venue"
    assert events_model.read_events(page_dir)[-1] == reply
    assert state_json(page_dir)["threads"][0]["title"] == "Workshop venue"

    # A later inline suggestion preserves the first name. Renaming is explicit.
    followed = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--text",
            "Check the access route.",
            "--title",
            "Access route",
        ],
    )
    assert followed.exit_code == 0, followed.output
    followup = json.loads(followed.output)
    assert state_json(page_dir)["threads"][0]["title"] == "Workshop venue"
    renamed = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "edit",
            str(page_dir),
            root["id"],
            "--title",
            "Terrace accessibility",
        ],
    )
    assert renamed.exit_code == 0, renamed.output
    title = json.loads(renamed.output)
    assert (title["kind"], title["thread"], title["title"]) == (
        "thread_title",
        root["id"],
        "Terrace accessibility",
    )
    thread = event_folds_model.build_threads(events_model.read_events(page_dir), {})[
        root["id"]
    ]
    assert thread_digest(thread)["title"] == "Terrace accessibility"
    assert [message["text"] for message in thread["msgs"]] == [
        root["text"],
        reply["text"],
        followup["text"],
    ]

    selected = runner.invoke(
        cli_model.cli, ["page", "state", str(page_dir), root["id"]]
    )
    assert selected.exit_code == 0, selected.output
    reading = json.loads(selected.output)
    assert [m["message"] for m in reading["content"]] == [
        root["id"],
        reply["id"],
        followup["id"],
    ]
    assert reading["thread"]["title"] == "Terrace accessibility"


def test_thread_titles_require_an_existing_thread_and_short_agent_prose(page_dir):
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Where should we meet?",
        },
    )
    command = {
        "kind": "thread_title",
        "author": "agent",
        "agent": "Codex",
        "session": "title-test",
        "thread": root["id"],
        "title": "Meeting venue",
    }
    before = events_model.read_events(page_dir)
    for invalid in (
        {"title": ""},
        {"title": "   "},
        {"title": "Two\nlines"},
        {"title": "Trailing newline\n"},
        {"title": "Two\rlines"},
        {"thread": "missing-thread"},
        {"author": "user"},
    ):
        with pytest.raises(events_model.EventRefused):
            append_command(page_dir, {**command, **invalid})
    assert events_model.read_events(page_dir) == before
