"""Version corpus, registry, message, and export tests."""

import json
import os
import re
import socket
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from conftest import hooks_run_this_tree
from interact_support import (
    COMMAND_SUBJECTS,
    FLOW_PAGE,
    PAGE,
    PLAN_OPENING,
    ROOT,
    SHIPPED_PACKAGES,
    STATED_TIMEOUT,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    check,
    check_findings,
    command_notes,
    comment,
    fetch,
    found,
    fresh_process,
    markup_findings,
    owed,
    page_state,
    publish,
    published,
    refused_on,
    response_reference,
    state_json,
    words,
)

from leaf.base import files as files_model
from leaf.base import schema as schema_model
from leaf.base import service as service_model
from leaf.base.findings import Finding, Rejected
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.log import events as event_folds_model
from leaf.log.thread_context import logged_fragment, thread_digest
from leaf.records import revisioning as revisioning_model
from leaf.records import todos as todos_model
from leaf.records import transaction as transaction_model
from leaf.records.authored_checks.admission import (
    check_markup,
    revision_publication,
)
from leaf.records.authored_checks.declarations import declaration_advice
from leaf.records.markup_checks.instances import question_errors, reference_errors
from leaf.source import layer as layer_model
from leaf.source import obligation_sources as obligation_sources_model
from leaf.source import vocabulary as vocabulary_model
from leaf.source.registry.contract import element_declarations
from leaf.source.registry.validation import incoming_registry
from leaf.source.structure import SourceDocument
from leaf_dev.example_data import authored_sources, named_source, page_files


def authored_tags(document: SourceDocument) -> set[str]:
    """Every lf-* tag a source authors, its live samples' included."""
    return {element["tag"] for element in document.lf_elements}.union(
        *(authored_tags(sample["document"]) for sample in document.samples)
    )


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
    from leaf.source.revision_artifact import artifact_name, read_artifact

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
    kinds = vocabulary_model.load_registry(page_dir)["$events"]["kinds"]
    for kind in ("comment", "action", "report"):
        required = kinds[kind]["record"]["required"]
        assert "revision" in required and "version" not in required
    required = kinds["note"]["record"]["required"]
    assert "revision" in required and "version" in required
    result = CliRunner().invoke(cli_model.cli, ["page", "--help"])
    assert result.exit_code == 0
    assert "\n  stamp " in result.output and "\n  publish " not in result.output


def test_options_require_an_id(page_dir):
    # Actions name their widget by id, and every group takes them.
    registry = vocabulary_model.load_registry(page_dir)
    errs = markup_findings(
        '<lf-options><lf-option id="o1" label="A"><strong>A</strong></lf-option></lf-options>',
        registry,
    )
    assert found(errs, "attribute-schema", "<lf-options>", keyword="required")


def test_sample_admits_interactive_widgets(page_dir):
    # The registry marks a sample's content quoted; the runtime leaves the
    # interactive widgets inside unwired. Validation is unchanged by the
    # wrapper: nesting rules (lf-option under lf-options) still hold.
    registry = vocabulary_model.load_registry(page_dir)
    errs = markup_findings(
        '<lf-sample id="sp" label="a decision">'
        '<lf-options id="g"><lf-option id="o1" label="A"><strong>A</strong></lf-option></lf-options>'
        '<lf-board id="b"><lf-column id="c" label="To do">'
        '<lf-card id="k" label="Card"><strong>Card</strong></lf-card></lf-column></lf-board>'
        "</lf-sample>",
        registry,
    )
    assert errs == []


def test_a_question_on_a_page_stands_in_a_group_its_author_names(page_dir):
    """A widget that asks on a page stands in a named group, an `lf-group`: the group is
    where going to the obligation starts and its `label` the obligation's prompt, read
    from the markup with no heading or ARIA read. `page check` refuses a question with
    no words, as where no group holds a widget without a label of its own or the group's
    label is blank, and advises on one its own label alone names; the registry refuses
    a group without a label or an id. A message's widget, a mention in a sample, a
    widget that asks nothing and one set among words need none."""
    registry = vocabulary_model.load_registry(page_dir)
    first = (
        '<lf-options id="g-one">'
        '<lf-option id="o-one" label="One"><strong>One</strong></lf-option>'
        "</lf-options>"
    )
    second = first.replace("one", "two").replace("One", "Two")

    def refused(body):
        document = SourceDocument(f"<main>{body}</main>")
        return [(f.code, f.at) for f in question_errors(document, registry)]

    def prompts(body):
        document = SourceDocument(f"<main>{body}</main>")
        return obligation_sources_model.obligation_sources(document, registry).prompts

    # The label names the question, wherever the widget stands in the group; several
    # widgets in one group share it.
    group = '<lf-group id="d" label="Choose">{}</lf-group>'
    for named in (
        group.format(f"<p>Context.</p>{first}"),
        group.format(f"<div><p>Context.</p>{first}</div>"),
    ):
        assert refused(named) == [], named
        assert prompts(named)["g-one"] == {"text": "Choose", "target": "d"}, named
    shared = group.format(f"{first}{second}")
    assert prompts(shared)["g-two"] == prompts(shared)["g-one"]
    # The innermost group is the question.
    nested = group.format(f'<lf-group id="part" label="First part">{first}</lf-group>')
    assert prompts(nested)["g-one"] == {"text": "First part", "target": "part"}

    # A section opened by a heading, a group ARIA names and a fieldset are no question:
    # Leaf reads neither a heading nor ARIA to find one.
    for ungrouped in (
        first,
        f'<section id="d"><h2>Choose</h2>{first}</section>',
        f'<section id="d" role="group" aria-label="Choose">{first}</section>',
        f'<fieldset id="d"><legend>Choose</legend>{first}</fieldset>',
    ):
        assert refused(ungrouped) == [("unnamed-question", "<lf-options id=g-one>")], (
            ungrouped
        )
    assert prompts(first)["g-one"] == {"text": "", "target": "g-one"}
    (finding,) = question_errors(SourceDocument(f"<main>{first}</main>"), registry)
    assert finding.refuses and '<lf-group id="…" label="…">' in str(finding)
    # A blank label names nothing either, and the finding names the group to fix.
    blank = f'<lf-group id="d" label=" ">{first}</lf-group>'
    (finding,) = question_errors(SourceDocument(f"<main>{blank}</main>"), registry)
    assert (finding.code, finding.values["group"]) == (
        "unnamed-question",
        "<lf-group id=d>",
    )
    assert prompts(blank)["g-one"] == {"text": "", "target": "d"}
    # A widget whose own label names its question stands outside the region On Me
    # selects, which is advice.
    labelled = {
        **registry,
        "lf-options": {
            **registry["lf-options"],
            "attributes": {
                **registry["lf-options"]["attributes"],
                "properties": {
                    **registry["lf-options"]["attributes"]["properties"],
                    "label": {"type": "string"},
                },
            },
        },
    }
    named = first.replace('id="g-one"', 'id="g-one" label="Which one?"')
    (finding,) = question_errors(SourceDocument(f"<main>{named}</main>"), labelled)
    assert (finding.code, finding.refuses) == ("ungrouped-question", False)

    # A settled group, which asks nothing, a sample's widgets, which ask nothing beyond
    # the sample, and a suggestion, which its sentence names, need no group.
    assert refused(first.replace('id="g-one"', 'id="g-one" settled')) == []
    for mode in ("", " interactive"):
        assert (
            refused(f'<lf-sample id="s" label="a question"{mode}>{first}</lf-sample>')
            == []
        )
    suggestion = (
        '<lf-suggestion id="s"><lf-old>daily</lf-old><lf-new>weekly</lf-new>'
        "</lf-suggestion>"
    )
    assert refused(f"<p>Refill {suggestion}.</p>") == []
    # A message's widget is named by the message, so its markup needs no group.
    assert markup_findings(first, registry) == []


def test_a_worker_is_assigned_only_to_a_goal(page_dir):
    """The work reading assigns a worker only to the goal its `on` names, so an id of
    an element with another role is refused, while a goal's passes."""
    registry = vocabulary_model.load_registry(page_dir)
    parser = SourceDocument(
        '<lf-test-plan id="hub">'
        '<lf-test-task id="goal" status="active"><strong>Goal</strong>'
        '<lf-test-worker id="worker" state="waiting" on="tree"><strong>Worker</strong>'
        '<lf-test-tree id="tree" source="project-worktrees"></lf-test-tree>'
        "</lf-test-worker>"
        '<lf-test-worker id="assigned" state="working" on="goal">'
        "<strong>Assigned</strong></lf-test-worker>"
        "</lf-test-task></lf-test-plan>"
    )

    errors = reference_errors(
        parser.lf_elements, registry, parser.ids, parser.by_id, thread_ids=set()
    )

    assert errors == [
        Finding(
            "work-assignment",
            "<lf-test-worker>",
            {"line": 1, "attr": "on", "target": "tree", "target_tag": "lf-test-tree"},
        )
    ]


def test_registry_examples_validate(page_dir):
    registry = vocabulary_model.load_registry(page_dir)
    assert any(
        tag.startswith("lf-") and "example" in entry for tag, entry in registry.items()
    )
    assert declaration_advice(registry, registry, "vendored registry") == []


def test_registry_example_ids_are_independent_between_entries(page_dir):
    registry = vocabulary_model.load_registry(page_dir)
    registry["lf-diff"]["example"] = (
        '<lf-diff id="shared"><pre>one changed line</pre></lf-diff>'
    )
    registry["lf-code"]["example"] = (
        '<lf-code id="shared"><pre>one/file.py</pre></lf-code>'
    )

    assert (
        declaration_advice(
            {"lf-diff": {}, "lf-code": {}}, registry, "independent examples"
        )
        == []
    )


def test_every_path_a_diff_resolves_names_a_language_the_bundles_carry(page_dir):
    """The language vocabulary has two halves and they have to agree. `names` is the half
    an author writes and the half both language bundles are built from;
    `paths` is what a filename means, which is how a diff colours a file nobody declared
    a language for. A path resolving outside `names` would resolve to a language neither
    bundle is required to carry."""
    reg = vocabulary_model.load_registry(page_dir)
    names = set(reg["$languages"]["names"])
    paths = reg["$languages"]["paths"]
    assert (
        paths
    )  # a table with nothing in it would pass the check below and colour nothing
    assert set(paths.values()) <= names, (
        f"no bundle for {sorted(set(paths.values()) - names)}"
    )


PAGE_FIXTURES = (
    *authored_sources(),
    *sorted((ROOT / "notes").glob("**/*.html")),
)


def test_every_widget_in_the_vocabulary_stands_in_a_corpus_source():
    """Eight sweeps in test_render.py read a widget inside a whole page, and their
    corpus is examples/, so a widget no example holds is one none of the eight has ever
    seen — a gap that reads as coverage, since the widget's own tests are green.
    examples/AGENTS.md carries the rest, including the shapes this floor doesn't
    reach."""
    registry = incoming_registry(SHIPPED_PACKAGES)
    # The corpus is generated from the others, so it can only repeat their coverage.
    authored = set().union(
        *(
            authored_tags(SourceDocument(path.read_text()))
            for path in authored_sources()
        )
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
        SourceDocument(named_source("feature-gallery").read_text(encoding="utf-8"))
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
    gallery = named_source("feature-gallery")
    authored = gallery.read_text(encoding="utf-8")
    gallery_registry = json.loads(
        (page_files(gallery) / "registry.json").read_text(encoding="utf-8")
    )
    apparatus = {tag for tag, entry in gallery_registry.items() if entry.get("exhibit")}
    assert apparatus
    eyebrows = re.findall(
        r'<p class="bg-feature-elements">(.*?)</p>',
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
    registry = incoming_registry(SHIPPED_PACKAGES)
    titled = [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and "title" in entry
    ]
    assert not titled, f"widget purposes are duplicated in title: {', '.join(titled)}"


def test_a_widget_takes_the_attributes_any_element_takes():
    """`class` and `style`, the page's styling hooks, and the attributes that describe
    any element and record nothing, stand on a widget as on any element; Leaf's own
    `data-lf-` namespace and `hidden` still meet its schema."""
    registry = incoming_registry(SHIPPED_PACKAGES)

    def refused(attributes):
        # What the widget's attribute schema says; `data-lf-` names are the runtime's
        # markers too, which `reserved-markers` refuses beside this.
        return [
            (e.code, e.values["keyword"], e.values["path"])
            for e in markup_findings(
                '<lf-group id="kind-ask" label="Choose a route"><h2 id="kind-ask-h">Choose a route</h2>'
                '<lf-options id="kind-options">'
                f'<lf-option id="route" {attributes}>Page</lf-option>'
                '<lf-option id="other">Ticket</lf-option>'
                "</lf-options></lf-group>",
                registry,
            )
            if e.code == "attribute-schema"
        ]

    # A value, like an id, may start with a digit: an alert called 5xx keeps its name.
    assert not refused('value="5xx-pages"')
    assert not refused('class="route"')
    assert not refused('style="grid-column: 2"')
    assert not refused(
        'title="Route" lang="en" dir="ltr" aria-describedby="route-note"'
        ' data-group="routing" data-test_id="r.1"'
    )
    assert refused('data-lf-said="x"') == [
        ("attribute-schema", "additionalProperties", [])
    ]
    assert refused("hidden") == [("attribute-schema", "additionalProperties", [])]


def test_a_message_refuses_a_playground_preset_without_an_id(
    tmp_path, initialized_page
):
    """A preset carries the id a comment on it records, since without one the comment
    lands on the whole playground. Message markup refuses a preset without one before
    any browser draws it, where a reply's playground otherwise reaches the user with
    only a static check."""
    page_dir = initialized_page(tmp_path / "page", ("playground",))

    def playground(preset):
        return (
            '<lf-group id="ask" label="Which?"><h2 id="ask-h">Which?</h2><lf-playground id="a">'
            '<aside><input type="range" name="size" max="4" value="2" /></aside>'
            f"{preset}"
            "<lf-playground-output>Use it.</lf-playground-output>"
            "</lf-playground></lf-group>"
        )

    def preset(ident):
        return (
            f'<lf-playground-preset{ident} label="Loud">'
            '<lf-playground-setting for="size" value="4"></lf-playground-setting>'
            "</lf-playground-preset>"
        )

    def reply(markup):
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

    assert reply(playground(preset(' id="preset-loud"'))) == []
    assert found(
        reply(playground(preset(""))),
        "attribute-schema",
        "<lf-playground-preset>",
        keyword="required",
    )


def test_a_message_admits_an_option_that_leads_with_a_strong_and_no_label(page_dir):
    """An option with no `label` that leads with a <strong> is a compact option the
    registry allows. A message holding it is admitted as written, and its command
    advises a `label` beside its result, as `page check` does on a page."""
    published(page_dir)
    noted = command_notes(
        "thread",
        "create",
        page_dir,
        "--text",
        '<lf-group id="ask" label="Which?">\n<h2 id="ask-h">Which?</h2>'
        '<lf-options id="pick"><lf-option id="a"><strong>A</strong> first.</lf-option>'
        '<lf-option id="b"><strong>B</strong> second.</lf-option></lf-options></lf-group>',
        "--title",
        "Agent thread",
    )
    assert [(f.code, f.at) for f in noted] == [
        ("unnamed-card", "<lf-option id=a>"),
        ("unnamed-card", "<lf-option id=b>"),
    ]


def test_reply_assigns_a_worker_to_a_goal_on_the_page(page_dir):
    """A worker in reply markup may work on a goal on the page beside it, and one
    naming a page element that isn't a goal never enters the log."""
    subjects = (
        '<lf-test-plan id="hub"><lf-test-task id="goal" status="active">'
        "<strong>Goal</strong>" + COMMAND_SUBJECTS + "</lf-test-task></lf-test-plan>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</section>", subjects + "</section>")
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "Act?"}
    )

    def reply(on):
        return CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, "c1"),
                "--text",
                "Assigned:\n\n"
                f'<lf-test-plan id="quoted"><lf-test-worker id="quoted-worker"'
                f' state="working" on="{on}"><strong>Worker</strong>'
                "</lf-test-worker></lf-test-plan>",
                "--title",
                "Thread title",
            ],
        )

    misassigned = reply("tree")
    assert misassigned.exit_code != 0
    assert 'on="tree" must name a goal' in words(misassigned.output)

    assigned = reply("goal")
    assert assigned.exit_code == 0, assigned.output


def test_widget_ids_are_one_universe_across_page_and_replies(page_dir):
    """The runtime resolves actions document-wide by id, so a reply widget must not
    reuse a page id — and a later version must not take a reply's."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )

    def reply(markup, *, for_event=None, to="c1"):
        route = (
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, for_event),
                "--title",
                "Thread title",
            ]
            if for_event
            else ["thread", "reply", str(page_dir), to, "--title", "Thread title"]
        )
        return CliRunner().invoke(
            cli_model.cli,
            [
                *route,
                "--text",
                f"Pick:\n\n{markup}",
            ],
        )

    def question(decision_id, markup):
        return f'<section id="{decision_id}"><h2>Pick?</h2>{markup}</section>'

    # `flag-first` is an option on the page (PAGE fixture) — refused.
    clash = reply(
        question(
            "o-decision",
            '<lf-options id="o"><lf-option id="flag-first" label="A"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event="c1",
    )
    assert clash.exit_code != 0 and "flag-first" in clash.output
    fresh = reply(
        question(
            "q1-decision",
            '<lf-options id="q1"><lf-option id="q1-a" label="A"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event="c1",
    )
    assert fresh.exit_code == 0, fresh.output
    # A second reply can't reuse the first reply's ids either, nor its own within itself.
    again = reply(
        question(
            "q1-decision",
            '<lf-options id="q1"><lf-option id="q1-b" label="B"><strong>B</strong></lf-option></lf-options>',
        )
    )
    assert again.exit_code != 0 and "q1" in again.output
    selfdup = reply(
        question(
            "q2-decision",
            '<lf-options id="q2"><lf-option id="q2" label="B"><strong>B</strong></lf-option></lf-options>',
        )
    )
    assert selfdup.exit_code != 0 and "duplicate ids" in selfdup.output
    # A user's text claims no ids however it quotes a tag — only an agent's message
    # holding HTML does, and a user's message never carries `html` (the log is append-only; a false claim
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
            '<lf-options id="quoted"><lf-option id="quoted-a" label="A"><strong>A</strong></lf-option></lf-options>',
        ),
        for_event=follow_up["id"],
        to=follow_up["id"],
    )
    assert ok.exit_code == 0, ok.output
    # And a new version taking the reply's id fails check.
    (page_dir / "index.html").write_text(
        PAGE.replace(PLAN_OPENING, PLAN_OPENING + '<p id="q1">stolen</p>')
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
        PAGE.replace(PLAN_OPENING, PLAN_OPENING + '<p id="lf-msg-7">mine</p>')
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
            (
                "Pick:\n\n"
                '<lf-group id="pick-decision" label="Pick?">\n<h2 id="pick-decision-h">Pick?</h2>'
                '<lf-options id="lf-pick">'
                '<lf-option id="o1" label="A"><strong>A</strong></lf-option>'
                "</lf-options></lf-group>"
            ),
            "--title",
            "Thread title",
        ],
    )
    assert reply.exit_code != 0
    assert "lf- namespace" in reply.output and "lf-pick" in reply.output


# ---------- messages: text is Markdown for the browser, markup is the gate's ----------


def test_agent_messages_preserve_a_single_space(page_dir):
    """Only the zero-length string is empty; every typed character reaches the log."""
    empty = CliRunner().invoke(
        cli_model.cli,
        ["thread", "create", str(page_dir), "--text", "", "--title", "Agent thread"],
    )
    assert empty.exit_code != 0
    assert json.loads(empty.stdout)["error"] == (
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
    assert "not both" in json.loads(both.stdout)["error"]
    renamed = runner.invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), opened["id"], "--title", "Label row"],
        input="Not the text.",
    )
    assert renamed.exit_code == 0, renamed.output
    assert [record["kind"] for record in json.loads(renamed.stdout)["records"]] == [
        "thread_title"
    ]

    planned = runner.invoke(
        cli_model.cli,
        ["task", "plan", str(page_dir), "--text"]
        + ['[{"depth": 0, "todo": "Check the rows"}]'],
    )
    assert planned.exit_code == 0, planned.output


def test_each_agent_session_posts_as_its_own_voice(page_dir, monkeypatch):
    """Several worker sessions report to one page. Each agent-authored event
    carries its poster's display name and session id from the poster's own
    environment, so the log tells the voices apart by id; the claim — the
    watcher the panel names — and every publication stay the hub's, untouched
    by a worker's post."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "hub")
    hooks_run_this_tree("hub")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    monkeypatch.setenv("LEAF_AGENT", "Hub")
    _tasks_version(page_dir, "active")
    transaction_model.claim_page(page_dir)
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
    hooks_run_this_tree("worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    assert _report(page_dir, "t-parser", "status", "value=review").exit_code == 0
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "The work is ready.",
            "--title",
            "Thread title",
        ],
    )
    assert answered.exit_code == 0, answered.output
    assert json.loads(answered.output)["responds"] == "c1"

    indexed = reply("indexing done")
    assert indexed.exit_code == 0, indexed.output
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-2")
    hooks_run_this_tree("worker-2")
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
    assert session is not None
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
            ["thread", "reply", str(claimed), root["id"], "--title", "Thread title"]
            if proactive
            else ["thread", "reply", reference, "--title", "Thread title"]
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
    assert start is not None
    assert (start["item"], start["text"]) == (root["id"], "Checking the camera.")
    assert events_model.read_events(claimed)[-1] == update
    [working] = page_state(claimed)["workflows"]
    assert (working["state"], working["detail"]) == ("running", "Checking the camera.")
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
            "--title",
            "Thread title",
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
    hooks_run_this_tree("worker-1")
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
            "--title",
            "Thread title",
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
        [revision] = json.loads(result.output)["records"]
        revisions.append(revision)

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
        == {
            "id",
            "title",
            "anchor",
            "detached_from",
            "rewritten_from",
            "resolved",
            "unread",
            "attention",
        }
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
    hooks_run_this_tree("worker-2")
    monkeypatch.setenv("LEAF_AGENT", "Crawler")
    foreign = CliRunner().invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), root["id"], "--text", "Taken over."],
    )
    assert foreign.exit_code == 0, foreign.output
    [replacement] = json.loads(foreign.output)["records"]
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
    [unidentified_edit] = json.loads(unidentified.output)["records"]
    assert unidentified_edit["message"] == sessionless["id"]


def test_a_user_revision_is_a_turn_the_agent_answers(page_dir, monkeypatch):
    """The user rewriting their message speaks again, under the edit's id.

    The thread shows the new wording in place of the old, and the agent owes it an
    answer as it would a reply: addressed to the message the edit rewrote, delivered
    with the wording it replaced, settled by a reply naming the edit, and reopening a
    thread the user had closed. Only the words the user wrote are theirs to revise.
    """
    from leaf.agents import delivery as delivery_model
    from leaf.log.event_log import EventRefused

    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    hooks_run_this_tree("worker-1")

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
                "--title",
                "Thread title",
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
    with transaction_model.PageTransaction(page_dir) as page:
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
    assert thread["attention"] == f"message:{json.loads(asking.output)['id']}"
    assert [item[0] for item in owed_answers()] == [typo["id"]]

    # No words at all delete the message. It keeps its place, beneath the answers
    # given to it, the agent owes the deletion an answer, and it is told what the
    # message said and nothing about rewritten words.
    gone = append_command(
        page_dir,
        {"kind": "edit", "author": "user", "message": asked["id"], "text": ""},
    )
    assert [item[0] for item in owed_answers()] == [gone["id"]]
    with transaction_model.PageTransaction(page_dir) as page:
        stored = next(event for event in page.events if event["id"] == gone["id"])
        delivered = delivery_model.freeze_delivery(
            [delivery_model.batch_data(page_dir, page, [stored])]
        )
    [batch] = delivered["batches"]
    [event] = batch["events"]
    assert (event["text"], event["was"]) == ("", "Chart both!")
    told = [batch["handling"][ref] for ref in event["handling"]]
    assert any("deleted" in clause for clause in told), told
    assert not any("rewrote" in clause for clause in told), told
    [thread] = batch["threads"]
    assert thread["messages"][0]["id"] == asked["id"]
    assert thread["messages"][0]["text"] == ""

    reaction = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": answer["id"], "emoji": "👍"},
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


def test_an_agent_edit_rewrites_its_messages_html(page_dir):
    """An agent may rewrite the HTML in its own message, as it may its words: Leaf
    checks the new markup as it checks a new message's, and every reading of the
    message's elements takes the latest wording. A user's answer stays keyed to the
    widget's ids, so the edit goes in and Leaf tells the agent where that answer now
    shows. An id any wording held stays the message's own, so no other message
    takes it and inherits the user's answer."""
    from leaf.log.thread_context import thread_structure

    published(page_dir)

    def options(name, *picks):
        return (
            f'<lf-options id="{name}">'
            + "".join(
                f'<lf-option id="{name}-{pick}">{pick}</lf-option>' for pick in picks
            )
            + "</lf-options>"
        )

    def edit(message, text):
        return CliRunner().invoke(
            cli_model.cli, ["thread", "edit", str(page_dir), message, "--text", text]
        )

    asked = comment(page_dir, "--text", "Ship it?\n\n" + options("ship", "now"))
    assert asked.exit_code == 0, asked.output
    asked = json.loads(asked.stdout)
    chosen = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "ship",
            "action": "choose",
            "detail": {"value": ["ship-now"]},
        },
    )

    def said():
        """What the user's choice says, in the words they chose it in."""
        from leaf.log.gesture_words import GestureWords
        from leaf.source.vocabulary import require_registry

        events = events_model.read_events(page_dir)
        words = GestureWords(events, require_registry(page_dir), {}.__getitem__)
        return words.gesture(next(e for e in events if e["id"] == chosen["id"]))

    # The page moves on to a second revision, which the edit is checked against.
    (page_dir / "index.html").write_text(
        PAGE.replace("<title>t</title>", "<title>Second</title>")
    )
    publish(page_dir)
    relabel = options("ship", "tonight", "later").replace("ship-tonight", "ship-now")
    relabelled = edit(asked["id"], "Ship it?\n\n" + relabel)
    assert relabelled.exit_code == 0, relabelled.output
    told = json.loads(relabelled.stdout)
    assert told["records"][0]["revision"] == 2
    assert [(f["code"], f["values"]["kept"]) for f in told["findings"]] == [
        ("edit-answered-widget", True)
    ]
    drawn = thread_structure(events_model.read_events(page_dir))
    assert "ship-later" in drawn.by_id
    assert said() == {"form": "choice", "chosen": ["now"]}

    # An option the user wrote lives in the log, so their pick of it shows on any
    # wording that keeps the widget.
    route = comment(page_dir, "--text", "Which route?\n\n" + options("route", "a"))
    route = json.loads(route.stdout)
    for action, detail in [
        ("add", {"option": "route-mine", "text": "Mine"}),
        ("choose", {"value": ["route-mine"]}),
    ]:
        append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 2,
                "widget": "route",
                "action": action,
                "detail": detail,
            },
        )
    reworded = edit(route["id"], "Which route, then?\n\n" + options("route", "a"))
    assert reworded.exit_code == 0, reworded.output
    assert {
        (f["at"], f["values"]["kept"]) for f in json.loads(reworded.stdout)["findings"]
    } == {("<lf-options id=route>", True)}

    # Keeping the widget but not the option the user chose leaves their answer
    # showing nowhere.
    replaced = edit(asked["id"], "Ship it?\n\n" + options("ship", "later"))
    assert replaced.exit_code == 0, replaced.output
    told = json.loads(replaced.stdout)
    assert [(f["code"], f["values"]["kept"]) for f in told["findings"]] == [
        ("edit-answered-widget", False)
    ]

    withdrawn = edit(asked["id"], "Withdrawn: the plan changed.")
    assert withdrawn.exit_code == 0, withdrawn.output
    told = json.loads(withdrawn.stdout)
    assert [(f["code"], f["values"]["kept"]) for f in told["findings"]] == [
        ("edit-answered-widget", False)
    ]
    drawn = thread_structure(events_model.read_events(page_dir))
    assert asked["id"] not in drawn.fragments and "ship" not in drawn.ids
    assert said() == {"form": "choice", "chosen": ["now"]}

    # Its ids stay the message's: another message can't take them, and it can.
    taken = comment(page_dir, "--text", "Ship it?\n\n" + options("ship", "now"))
    assert taken.exit_code != 0 and "ids-taken" in taken.output
    restored = edit(asked["id"], "Ship it?\n\n" + options("ship", "now"))
    assert restored.exit_code == 0, restored.output

    plain = comment(page_dir, "--text", "Which store?")
    plain = json.loads(plain.stdout)
    widened = edit(plain["id"], "Which store?\n\n" + options("store", "redis"))
    assert widened.exit_code == 0, widened.output
    assert json.loads(widened.stdout).get("findings") is None
    drawn = thread_structure(events_model.read_events(page_dir))
    assert "store" in drawn.fragments[plain["id"]].by_id

    # The new markup meets the gate a new message's does.
    before = events_model.read_events(page_dir)
    clash = edit(plain["id"], "Which store?\n\n" + options("ship", "redis"))
    assert clash.exit_code != 0 and "ids-taken" in clash.output
    assert events_model.read_events(page_dir) == before


def test_a_rewrite_is_delivered_with_the_words_it_replaced_then(page_dir):
    """A rewrite replaced the words its message had when the user made it, and
    taking back an earlier rewrite later changes nothing it replaced."""
    from leaf.agents import delivery as delivery_model

    publish(page_dir)
    asked = append_command(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "text": "A."}
    )

    def rewrite(text):
        return append_command(
            page_dir,
            {"kind": "edit", "author": "user", "message": asked["id"], "text": text},
        )

    second = rewrite("B.")
    third = rewrite("C.")
    append_command(page_dir, {"kind": "undo", "author": "user", "undoes": second["id"]})
    with transaction_model.PageTransaction(page_dir) as page:
        stored = next(event for event in page.events if event["id"] == third["id"])
        delivered = delivery_model.freeze_delivery(
            [delivery_model.batch_data(page_dir, page, [stored])]
        )
    [batch] = delivered["batches"]
    [event] = batch["events"]
    assert (event["text"], event["was"]) == ("C.", "B.")


def test_a_rewritten_message_stays_out_of_the_suggested_summary(page_dir, monkeypatch):
    """The newest exchange stays verbatim when the user rewrites its words.

    A long thread's digest suggests folding all but its last two messages; rewriting
    the newest user message is a turn the agent owes, and it moves no message into
    that range."""
    from leaf.log.thread_context import batch_threads
    from leaf.source.revision_artifact import active_enclosing

    publish(page_dir)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    hooks_run_this_tree("worker-1")
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
                "--title",
                "Thread title",
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
        with transaction_model.PageTransaction(page_dir) as page:
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
    no rewrite. Undoing a rewrite gives the message back the words it replaced, and the
    rewrite before it is the one the next lands on. A rewrite the agent has answered
    is taken back too, and the agent is told, since it may have acted on its words."""
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

    append_command(page_dir, {"kind": "undo", "author": "user", "undoes": west["id"]})
    thread = event_folds_model.build_threads(events_model.read_events(page_dir), {})[
        said["id"]
    ]
    assert [message["text"] for message in thread["msgs"]] == ["South."]
    assert thread["msgs"][0]["edited"] == {
        "id": south["id"],
        "seq": south["seq"],
        "ts": south["ts"],
        "was": "North.",
    }
    with pytest.raises(events_model.EventRefused):
        rewrite("East.", west["id"])

    def answer(turn, text):
        append_command(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": said["id"],
                "responds": turn["id"],
                "text": text,
            },
        )

    # Answered either way, the undo leaves nothing owed, and still reaches the agent.
    answer(south, "Heading south.")
    east = rewrite("East.", south["id"])
    answer(east, "Heading east.")
    took_back = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": east["id"]}
    )
    assert took_back["attention"] is True
    thread = event_folds_model.build_threads(events_model.read_events(page_dir), {})[
        said["id"]
    ]
    assert [message["text"] for message in thread["msgs"]] == [
        "South.",
        "Heading south.",
        "Heading east.",
    ]
    assert event_folds_model.unanswered_turns(thread) == []


def test_edit_uses_the_captured_contract_when_the_candidate_registry_is_invalid(
    page_dir, monkeypatch
):
    """An edit uses the active revision's contract, not a broken candidate."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    hooks_run_this_tree("worker-1")
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
    (page_dir / "page").mkdir()
    (page_dir / "page" / "registry.json").write_text("{")
    before = events_model.read_events(page_dir)

    result = CliRunner().invoke(
        cli_model.cli,
        ["thread", "edit", str(page_dir), message["id"], "--text", "Revised."],
    )

    assert result.exit_code == 0, result.output
    assert events_model.read_events(page_dir)[:-1] == before
    assert events_model.read_events(page_dir)[-1]["text"] == "Revised."


def test_html_the_user_types_stays_words(server, page_dir):
    """Only an agent's message draws its HTML, and every one has been through
    `check_markup`, which is what lets the thread structure and the panel index it
    unasked. A tag the user types through the browser door is words: the message
    holds no markup."""
    publish(page_dir)
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "revision": 1,
                "text": 'hi\n\n<lf-diagram id="m">\n<pre>graph LR\n  A --> B</pre></lf-diagram>',
            }
        ).encode(),
    )
    assert status == 200, body
    message = events_model.read_events(page_dir)[-1]
    assert (message["author"], logged_fragment(message)) == ("user", None)


@pytest.mark.parametrize(
    "markup", ["", '<lf-diagram id="f"><pre>graph LR\n  A --> B</pre></lf-diagram>']
)
def test_reply_refuses_a_missing_current_layer(page_dir, markup):
    """An addressed reply validates current source, even when its text needs no widget."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    (page_dir / schema_model.LAYER_FILE).unlink()
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
            f"See:\n\n{markup}" if markup else "See:",
            "--title",
            "Thread title",
        ],
    )
    assert result.exit_code != 0, result.output
    assert "has no layer.json" in result.output
    assert "run `leaf page init`" in result.output
    assert events_model.read_events(page_dir) == before


def test_comment_requires_the_registry_its_runtime_reads(page_dir):
    published(page_dir)
    (page_dir / schema_model.LAYER_FILE).unlink()
    before = events_model.read_events(page_dir)
    result = comment(page_dir, "--quote", "Ship dark", "--text", "Still posts")
    assert result.exit_code != 0
    assert (
        "has no layer.json" in result.output and "run `leaf page init`" in result.output
    )
    assert events_model.read_events(page_dir) == before


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
    resolved = layer_model.resolve_packages(tuple(packages), Path.cwd())
    assert resolved == [schema_model.BUNDLED_PACKAGES / name for name in packages]
    assert layer_model.checked_inputs(resolved) == resolved


def test_page_state_reads_a_reaction_as_a_message(page_dir):
    """`page state` lists a thread a reaction opened as any other, answered or not, and
    the thread's history reads the reaction's emoji where a message reads its words;
    the agent reads it as the user meant it."""
    published(page_dir)
    bare = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "emoji": "✂️",
            "anchor": {"section": "plan", "quote": "Ship dark"},
        },
    )
    answered = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "emoji": "❌"},
    )
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            answered["id"],
            "--text",
            "Which part?",
            "--title",
            "Thread title",
        ],
    )
    assert posted.exit_code == 0, posted.output
    reply = json.loads(posted.output)
    state = state_json(page_dir)
    assert [t["id"] for t in state["threads"]] == [bare["id"], answered["id"]]
    selected = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), answered["id"]]
    )
    assert selected.exit_code == 0, selected.output
    assert [
        (m["message"], m.get("emoji"), m.get("text"))
        for m in json.loads(selected.output)["content"]
    ] == [(answered["id"], "❌", None), (reply["id"], None, "Which part?")]


def test_the_agent_answers_with_an_emoji_as_with_words(page_dir):
    """`thread reply --emoji` is the agent's reaction: one emoji in place of words,
    which answers the update its reference names and declares what it leaves as
    words do, and is refused beside words or as anything but one emoji."""
    published(page_dir)
    thanks = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Thanks!"},
    )
    reference = response_reference(page_dir, thanks)

    def reply(*options):
        return CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", reference, *options, "--title", "Thanks"],
        )

    both = reply("--done", "--emoji", "👍", "--text", "Glad it helps.")
    assert both.exit_code != 0 and "--emoji" in both.output
    assert reply("--done", "--emoji", "ok").exit_code != 0
    nod = reply("--done", "--emoji", "👍")
    assert nod.exit_code == 0, nod.output
    record = json.loads(nod.output)
    assert record["emoji"] == "👍" and "text" not in record
    assert record["responds"] == thanks["id"]
    [thread] = event_folds_model.build_threads(
        events_model.read_events(page_dir), {}
    ).values()
    assert event_folds_model.owed_turns(thread) == []


def test_a_reaction_something_answered_is_taken_back_into_its_place(page_dir):
    """A reaction is the user's to take back however far the agent has got with it, as a
    rewrite is. The withdrawal leaves what answered it its context: the thread stays,
    the reaction's place reads Deleted with what it said, the mark paints nothing, and
    nothing is owed to it. A reaction on a message keeps its place the same way, and one
    nothing stands on still leaves every reading. The agent hears of each withdrawal
    as it heard of the reaction."""
    published(page_dir)
    mark = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "emoji": "✂️",
            "anchor": {"section": "plan", "quote": "Ship dark"},
        },
    )

    def reply(target, text):
        posted = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                str(page_dir),
                target,
                "--text",
                text,
                "--title",
                "Thread title",
            ],
        )
        assert posted.exit_code == 0, posted.output
        return json.loads(posted.output)

    answer = reply(mark["id"], "Which part is long?")
    nod = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": answer["id"],
            "emoji": "👍",
        },
    )
    kept = reply(nod["id"], "Keeping that part.")
    loose = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": kept["id"],
            "emoji": "👍",
        },
    )
    # The agent closes the thread by the reaction it acted on.
    resolved = CliRunner().invoke(
        cli_model.cli, ["thread", "resolve", str(page_dir), loose["id"]]
    )
    assert resolved.exit_code == 0, resolved.output
    undos = [
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": gesture["id"]}
        )
        for gesture in (loose, nod, mark)
    ]
    assert [undo["attention"] for undo in undos] == [True, True, True]

    thread = event_folds_model.build_threads(events_model.read_events(page_dir), {})[
        mark["id"]
    ]
    assert [message["id"] for message in thread["msgs"]] == [
        mark["id"],
        answer["id"],
        nod["id"],
        kept["id"],
    ]
    for gesture, undo, said in ((mark, undos[2], "✂️"), (nod, undos[1], "👍")):
        placed = next(m for m in thread["msgs"] if m["id"] == gesture["id"])
        assert "emoji" not in placed and placed["text"] == ""
        assert placed["withdrawn"] == {"id": undo["id"], "ts": undo["ts"], "was": said}
    assert not event_folds_model.bare_reaction(thread)
    assert event_folds_model.unanswered_turns(thread) == []
    # Taking back the reaction the resolve named leaves the thread closed.
    assert thread["resolved"]["kind"] == "resolve"
    state = state_json(page_dir)
    assert [t["id"] for t in state["threads"]] == [mark["id"]]


def test_a_message_the_user_sent_is_taken_back_into_its_place(page_dir):
    """A message with words is the user's to take back as a reaction is. One the agent
    answered keeps its place, Deleted, with the words it was sent with; one nothing
    answered leaves every reading, and nothing is owed to it; a comment nothing answered
    takes its thread with it. The agent hears of each withdrawal as it heard of the
    message, and a rewrite of a message taken back is refused."""
    published(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Too long?"},
    )
    answer = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            response_reference(page_dir, asked),
            "--obligation",
            "--text",
            "Which part?",
            "--title",
            "Thread title",
        ],
    )
    assert answer.exit_code == 0, answer.output
    answer = json.loads(answer.output)
    said = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": answer["id"],
            "text": "The rollout section.",
        },
    )
    kept = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            response_reference(page_dir, said),
            "--done",
            "--text",
            "Cutting it.",
        ],
    )
    assert kept.exit_code == 0, kept.output
    kept = json.loads(kept.output)
    loose = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "revision": 1,
            "parent": kept["id"],
            "text": "And the appendix.",
        },
    )
    lone = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Typo here."},
    )
    undos = [
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": gesture["id"]}
        )
        for gesture in (lone, loose, said)
    ]
    assert [undo["attention"] for undo in undos] == [True, True, True]

    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert list(threads) == [asked["id"]]
    thread = threads[asked["id"]]
    assert [message["id"] for message in thread["msgs"]] == [
        asked["id"],
        answer["id"],
        said["id"],
        kept["id"],
    ]
    placed = thread["msgs"][2]
    assert placed["text"] == ""
    assert placed["withdrawn"] == {
        "id": undos[2]["id"],
        "ts": undos[2]["ts"],
        "was": "The rollout section.",
    }
    assert event_folds_model.unanswered_turns(thread) == []
    state = state_json(page_dir)
    assert [t["id"] for t in state["threads"]] == [asked["id"]]
    assert owed(state) == []

    with pytest.raises(Rejected) as refused:
        append_command(
            page_dir,
            {
                "kind": "edit",
                "author": "user",
                "message": said["id"],
                "text": "The rollout.",
            },
        )
    assert refused.value.findings[0].code == "withdrawn-message"


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
    [title] = json.loads(renamed.output)["records"]
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
