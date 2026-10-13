"""Static document, version, and page-state tests."""

import gc
import hashlib
import json
import math
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import threading
import traceback
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    FLOW_PAGE,
    OPTIONS,
    PAGE,
    SHIPPED_PACKAGES,
    STATED_TIMEOUT,
    X,
    Y,
    _board,
    _decided,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    asks_on_user,
    before_choice,
    check,
    check_findings,
    comment,
    declare_data_input,
    found,
    fresh_process,
    lock_contention,
    model_layer,
    page_state,
    publish,
    read_page_data,
    response_reference,
    stamp,
    state_json,
    write_revision,
)
from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import event_meaning as event_meaning_model
from leaf import files as files_model
from leaf import leases as leases_model
from leaf import page_memory as page_memory_model
from leaf import passages as passages_model
from leaf import projection as projection_model
from leaf import publishing as publishing_model
from leaf import revision_artifact as artifact_model
from leaf import revision_delivery as revision_delivery_model
from leaf import revisioning as revisioning_model
from leaf import samples as samples_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf.refusals import Refused
from leaf.registry.contract import RANK, detail_schema
from leaf.registry.schema import schema_error
from leaf.registry.storage import read_page_registry, require_registry
from leaf.render_gate import readings as render_gate_readings
from leaf.served_state.context import read_page
from leaf.served_state.page import read_served_page
from leaf.served_state.service import LivePage
from leaf.validation import composition as validation_model
from leaf.validation.source import check_source
from leaf.validation.source_history import predecessor_reading
from leaf_dev.example_data import captured_value, patch_manifest


def test_stamp_installs_or_restores_complete_authored_inputs_before_activation(
    page_dir, tmp_path, monkeypatch
):
    """HTTP activation cannot capture a partially installed replacement.

    Hold a valid first module write while another reader reaches the actual page
    transaction. A later missing dependency refuses stamp; the reader must see the
    previous complete input set after rollback, with no intermediate revision.
    """
    authored = page_dir / "page"
    authored.mkdir(exist_ok=True)
    (authored / "a.js").write_text("export const a = 1;")
    (authored / "b.js").write_text("export const b = 1;")
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</head>",
            '<script type="module" src="/page/a.js"></script>'
            '<script type="module" src="/page/b.js"></script></head>',
        )
    )
    publishing_model.cmd_stamp(page_dir, "Original")
    previous = publishing_model.authored_files(page_dir / "index.html", authored)
    expected = publishing_model.authored_digest(previous)
    first = files_model.latest_revision(page_dir)
    log = (page_dir / "events.jsonl").read_bytes()
    candidate = tmp_path / "candidate"
    (candidate / "page").mkdir(parents=True)
    publishing_model.write_authored_files(candidate, previous, {})
    (candidate / "page/a.js").write_text("export const a = 2;")
    (candidate / "page/b.js").write_text("import './missing.js';")
    reached = threading.Event()
    release = threading.Event()
    original_write = Path.write_bytes

    def hold_first_write(path, data):
        result = original_write(path, data)
        if path == authored / "a.js" and data == b"export const a = 2;":
            reached.set()
            assert release.wait(timeout=STATED_TIMEOUT)
        return result

    monkeypatch.setattr(Path, "write_bytes", hold_first_write)
    blocked = lock_contention(monkeypatch, page_dir / "events.jsonl")
    with ThreadPoolExecutor(max_workers=2) as executor:
        replacing = executor.submit(
            publishing_model.cmd_stamp,
            page_dir,
            "Candidate",
            from_directory=candidate,
            if_source=expected,
        )
        try:
            assert reached.wait(timeout=STATED_TIMEOUT)
            activating = executor.submit(revisioning_model.activate_source, page_dir)
            assert blocked.wait(timeout=STATED_TIMEOUT), (
                "source activation did not wait for the complete replacement"
            )
        finally:
            release.set()
        with pytest.raises(Refused, match="missing.js"):
            replacing.result(timeout=STATED_TIMEOUT)
        activated = activating.result(timeout=STATED_TIMEOUT)
    assert activated.revision == first and not activated.created
    assert (
        publishing_model.authored_files(page_dir / "index.html", authored) == previous
    )
    assert (page_dir / "events.jsonl").read_bytes() == log

    (candidate / "page/b.js").write_text("export const b = 2;")
    publishing_model.cmd_stamp(
        page_dir, "Complete", from_directory=candidate, if_source=expected
    )
    assert files_model.latest_revision(page_dir) > first
    assert artifact_model.read_artifact(page_dir, first).resources[
        "/page/a.js"
    ].data == (b"export const a = 1;")
    with pytest.raises(Refused, match="authored inputs changed"):
        publishing_model.cmd_stamp(
            page_dir, "Stale", from_directory=candidate, if_source=expected
        )


def test_a_revision_captures_the_complete_dependency_graph(page_dir):
    authored = page_dir / "page"
    (authored / "nested").mkdir(parents=True)
    (authored / "app.js").write_text(
        'import { value } from "./nested/value.js"; '
        'import "/runtime/widget-api.js"; window.result = value;'
    )
    (authored / "nested" / "value.js").write_text(
        'export { value } from "../value.js";'
    )
    (authored / "value.js").write_text("export const value = 1;")
    (authored / "style.css").write_text('@import "./nested/theme.css";')
    (authored / "nested" / "theme.css").write_text(
        'main { background-image: url("../image.svg"); }'
    )
    (authored / "image.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    html = PAGE.replace(
        "</head>",
        '<script type="module" src="/page/app.js"></script>'
        '<link rel="stylesheet" href="/page/style.css"></head>',
    )
    (page_dir / "index.html").write_text(html)

    first = revisioning_model.activate_source(page_dir)
    assert first.error is None, first.error
    assert first.created
    artifact = artifact_model.read_artifact(page_dir, first.revision)
    assert artifact.html == html.encode()
    assert artifact.resources["/page/app.js"].dependencies == (
        "/page/nested/value.js",
        "/runtime/widget-api.js",
    )
    assert artifact.resources["/page/style.css"].dependencies == (
        "/page/nested/theme.css",
    )
    assert artifact.resources["/page/nested/theme.css"].dependencies == (
        "/page/image.svg",
    )
    assert artifact.resources["/page/image.svg"].mime == "image/svg+xml"
    assert artifact.resources["/page/app.js"].mime == "application/javascript"
    assert artifact.registry == read_page_registry(page_dir).registry
    assert artifact.implementations["lf-options"]["path"] == "/widgets/lf-options.js"
    assert "/vendor/browser-runtime.LICENSES.txt" in artifact.resources
    assert artifact_model.read_artifact(page_dir, first.revision) is artifact
    unchanged = revisioning_model.activate_source(page_dir)
    assert not unchanged.created and unchanged.revision == first.revision

    (authored / "value.js").write_text("export const value = 2;")
    second = revisioning_model.activate_source(page_dir)
    assert second.error is None, second.error
    assert second.created and second.revision == first.revision + 1
    changed = artifact_model.read_artifact(page_dir, second.revision)
    assert changed.digest != artifact.digest
    assert changed.resources["/page/value.js"].data == b"export const value = 2;"
    files_model.replace_files(
        [(page_dir / "leaf.js", b"// replacement runtime", False)]
    )
    third = revisioning_model.activate_source(page_dir)
    assert third.error is None, third.error
    assert third.created and third.revision == second.revision + 1
    replaced = artifact_model.read_artifact(page_dir, third.revision)
    assert replaced.resources["/leaf.js"].data == b"// replacement runtime"
    assert replaced.digest != changed.digest
    historical = artifact_model.read_artifact(page_dir, first.revision)
    assert historical.resources["/page/value.js"].data == b"export const value = 1;"
    assert historical.resources["/leaf.js"].data == artifact.resources["/leaf.js"].data


def test_a_revision_keeps_its_bytes_when_a_layer_file_is_edited_in_place(page_dir):
    """A page's layer files are the user's to edit, in place if their editor does,
    so a revision holds its own copy of each and never shares one's inode."""
    first = revisioning_model.activate_source(page_dir)
    assert first.error is None, first.error
    captured = (
        files_model.revision_path(page_dir, first.revision).with_suffix("")
        / "resources"
    )
    for layer_file in ("leaf.js", "theme.css", "runtime/layer-generation.js"):
        assert (captured / layer_file).stat().st_ino != (
            page_dir / layer_file
        ).stat().st_ino, layer_file
    theme = (captured / "theme.css").read_bytes()
    with (page_dir / "theme.css").open("r+b") as stream:
        stream.write(b"/* edited in place */")
    assert (captured / "theme.css").read_bytes() == theme


def test_a_sample_child_stages_its_revision_without_fsync(page_dir, monkeypatch):
    """A sample's child is Leaf's own and deleted on release, so nothing reads its
    revision after a crash and staging it pays for no fsync, while a page's own
    revision is still made durable."""
    template = (
        '<template id="practice" data-sample><h1>Practice</h1>'
        "<p>Child text.</p></template>"
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", template + "</main>"))
    synced = []
    fsync = os.fsync

    def recording(descriptor):
        if any(
            frame.filename.endswith("revision_artifact.py")
            for frame in traceback.extract_stack()
        ):
            synced.append(descriptor)
        return fsync(descriptor)

    monkeypatch.setattr(os, "fsync", recording)
    parent = revisioning_model.activate_source(page_dir)
    assert parent.error is None, parent.error
    assert synced, "a page's own revision is made durable"

    synced.clear()
    inputs = LivePage(page_dir).sample_inputs(parent.revision)
    samples = samples_model.Samples()
    identity = samples.create(page_dir, inputs, "practice", None, None)
    try:
        child = samples.pages[identity].directory
        assert files_model.latest_revision(child) == 1
        assert synced == []
    finally:
        samples.close()


def test_the_captured_widget_digests_say_which_widgets_a_user_may_keep(page_dir):
    """One digest per declared widget, over what its author wrote.

    A user's open document keeps the widgets a revision did not rewrite, and only the
    capture still holds the markup to say which those are: after upgrade a controller
    owns every widget's children. Digested from the parsed tree, so two revisions of one
    widget differ where the author changed it and nowhere else.
    """
    document = FLOW_PAGE

    def activate():
        (page_dir / "index.html").write_text(document)
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error
        return artifact_model.read_artifact(page_dir, activated.revision)

    base = activate()
    # Every element the vocabulary says carries a module, named the way its author named
    # it or, where they named nothing, by its tag and place among the others of that tag.
    # An unnamed widget is as much the user's as a named one; without a key it could
    # never answer that its markup was unchanged, so every revision rebuilt it.
    assert set(base.widgets) == {"flow", "lf-options#0"}

    document = document.replace("The cutoff lives in", "The cutoff now lives in")
    reworded = activate()
    assert reworded.digest != base.digest, "the prose edit made no new revision"
    assert reworded.widgets == base.widgets

    document = document.replace("Ship dark.", "Ship it dark.")
    rewritten = activate()
    assert rewritten.widgets["lf-options#0"] != base.widgets["lf-options#0"]
    assert rewritten.widgets["flow"] == base.widgets["flow"]


def test_module_capture_reads_javascript_syntax_and_rewrites_only_imports(page_dir):
    authored = page_dir / "page"
    (authored / "value.js").write_text("export const value = 1;")
    module = """// import "https://outside.example/comment.js";
const text = 'import "./missing.js"';
const pattern = /import\\("missing"\\)/;
const template = `import "./missing.js" ${await import('./value.js')}`;
export { value } from "./value.js";
"""
    (authored / "app.js").write_text(module)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</head>", '<script type="module" src="/page/app.js"></script></head>'
        )
    )

    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    artifact = artifact_model.read_artifact(page_dir, activated.revision)
    resource = artifact.resources["/page/app.js"]
    assert resource.dependencies == ("/page/value.js",)
    rewritten = revision_delivery_model.rebase_module(
        resource.data, "/page/app.js", lambda path: "/revisions/captured" + path
    )
    assert rewritten.decode() == module.replace(
        "import('./value.js')", 'import("/revisions/captured/page/value.js")'
    ).replace('from "./value.js"', 'from "/revisions/captured/page/value.js"')


def test_invalid_dependencies_leave_the_previous_revision_active(page_dir, tmp_path):
    authored = page_dir / "page"
    (authored / "data.json").write_text('{"value": 1}')
    outside = tmp_path / "outside.js"
    outside.write_text("export const value = 1;")
    (authored / "escape.js").symlink_to(outside)
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    previous = files_model.latest_revision(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</head>", '<script type="module" src="/page/app.js"></script></head>'
        )
    )
    for source, diagnostic in [
        ('import "./missing.js";', "cannot capture dependency"),
        ('import "ftp://outside.example/module.js";', "http(s) URL"),
        ('import "../../outside.js";', "public layer entry point"),
        ('import "/runtime/events.js";', "public layer entry point"),
        ('import "./data.json";', "JavaScript MIME"),
        ('import "./escape.js";', "symlink"),
        ('import "./data\\u002ejson";', "dependency must be a local URL"),
    ]:
        (authored / "app.js").write_text(source)
        refused = revisioning_model.activate_source(page_dir)
        assert refused.error and diagnostic in refused.error, (source, refused.error)
        assert refused.revision == previous and not refused.created
        assert files_model.latest_revision(page_dir) == previous


def test_an_interrupted_capture_never_publishes_a_partial_revision(
    page_dir, monkeypatch
):
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    previous = files_model.latest_revision(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Revised plan</h2>")
    )
    link = artifact_model.os.link

    def interrupt_commit(source, destination):
        raise OSError("interrupted before the activation marker")

    monkeypatch.setattr(artifact_model.os, "link", interrupt_commit)
    with pytest.raises(OSError, match="activation marker"):
        revisioning_model.activate_source(page_dir)
    assert files_model.latest_revision(page_dir) == previous
    assert artifact_model.read_artifact(page_dir, previous).html == PAGE.encode()

    monkeypatch.setattr(artifact_model.os, "link", link)
    recovered = revisioning_model.activate_source(page_dir)
    assert recovered.error is None and recovered.revision == previous + 1
    assert (
        artifact_model.read_artifact(page_dir, recovered.revision).html
        == (page_dir / "index.html").read_bytes()
    )


def _replace_manifest(page_dir, revision):
    manifest_path = (
        files_model.revision_path(page_dir, revision).with_suffix("") / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["implementations"] = {}
    files_model.replace_files(
        [(manifest_path, json.dumps(manifest, sort_keys=True).encode(), False)]
    )


def test_artifact_read_refuses_a_replaced_immutable_manifest(page_dir):
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    revision = files_model.latest_revision(page_dir)
    _replace_manifest(page_dir, revision)

    with pytest.raises(artifact_model.ArtifactError, match="manifest digest"):
        artifact_model.read_artifact(page_dir, revision)


@pytest.mark.parametrize("manifest", [None, "{", "shared_modules", "widgets"])
def test_revision_inventory_ignores_incomplete_capture_records(page_dir, manifest):
    """Stale captures are absent; current publication and numeric order still work."""
    first = revisioning_model.activate_source(page_dir)
    assert first.error is None and first.revision == 1
    marker = files_model.revision_path(page_dir, 1)
    old = marker.parent / "r9-0123456789abcdef"
    shutil.copytree(marker.with_suffix(""), old)
    metadata = old / "manifest.json"
    if manifest is None:
        metadata.unlink()
    elif manifest == "{":
        metadata.write_text(manifest)
    else:
        record = json.loads(metadata.read_bytes())
        if manifest == "shared_modules":
            # The previous graph omitted lazy layer libraries. It is an obsolete
            # contract even though its manifest contains the earlier graph field.
            record["runtime_modules"] = record.pop(manifest)
        else:
            del record[manifest]
        metadata.write_text(json.dumps(record))
    old.with_suffix(".html").write_bytes(marker.read_bytes())

    assert files_model.list_revisions(page_dir) == [1]
    with pytest.raises(Refused, match="no revision r9"):
        files_model.revision_path(page_dir, 9)
    (page_dir / "index.html").write_text(PAGE.replace("Plan", "Next plan"))
    current = revisioning_model.activate_source(page_dir)
    assert current.error is None and current.revision == 10
    assert artifact_model.read_artifact(page_dir, 10).shared_modules
    assert files_model.list_revisions(page_dir) == [1, 10]


def test_obsolete_capture_identities_are_never_rebound_to_new_publications(page_dir):
    """A fresh stamp cannot inherit the decisions or version of an obsolete capture."""
    first = stamp(page_dir, "Original publication")
    assert first.exit_code == 0, first.output
    marker = files_model.revision_path(page_dir, 1)
    artifact = artifact_model.read_artifact(page_dir, 1)
    metadata = marker.with_suffix("") / "manifest.json"
    manifest = json.loads(metadata.read_bytes())
    del manifest["shared_modules"]
    metadata.write_text(json.dumps(manifest))
    original = events_model.read_events(page_dir)
    assert original[-1]["revision"] == 1 and original[-1]["publication"]

    with fresh_process():
        assert files_model.list_revisions(page_dir) == []
        assert files_model.revision_orders(page_dir) == (1,)
        assert files_model.unfinished_publications(page_dir, original) == []
        with pytest.raises(artifact_model.ArtifactError, match="r1 already exists"):
            artifact_model.stage_artifact(page_dir, 1, artifact)
        (page_dir / "index.html").write_text(PAGE.replace("Plan", "New publication"))
        current = stamp(page_dir, "Current publication")
        assert current.exit_code == 0, current.output
        assert files_model.list_revisions(page_dir) == [2]
        assert artifact_model.read_artifact(page_dir, 2).shared_modules
        events = events_model.read_events(page_dir)
        assert events[: len(original)] == original
        assert events[-1]["revision"] == 2 and events[-1]["version"] == 2


def test_obsolete_capture_with_frozen_reply_is_absent_from_page_state(page_dir):
    """An unavailable publication drops its frozen widget island, not its prose."""
    assert revisioning_model.activate_source(page_dir).revision == 1
    parent = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Choose."},
    )
    reply = thread_model.post_reply(
        page_dir,
        {"to": parent["id"], "for": parent["id"]},
        "The captured choice is here.",
        '<lf-options id="frozen-options" choose>'
        '<lf-option id="frozen-option">Keep</lf-option></lf-options>',
    )
    marker = files_model.revision_path(page_dir, 1)
    (page_dir / "index.html").write_text(PAGE.replace("Plan", "Updated plan"))
    assert revisioning_model.activate_source(page_dir).revision == 2
    marker.unlink()
    assert files_model.list_revisions(page_dir) == [2]
    current_parent = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 2,
            "text": "Keep the current capture.",
        },
    )
    current = thread_model.post_reply(
        page_dir,
        {"to": current_parent["id"], "for": current_parent["id"]},
        "This capture is still available.",
        '<lf-code id="current-capture" language="python"><pre>2</pre></lf-code>',
    )

    with fresh_process():
        state = page_state(page_dir)
        browser = state["browser"]

    threads = {
        thread["id"]: thread
        for thread in browser["views"][str(state["active"]["revision"])]["thread"][
            "threads"
        ]
    }
    obsolete = threads[parent["id"]]
    assert [message["text"] for message in obsolete["msgs"]] == [
        "Choose.",
        "The captured choice is here.",
    ]
    assert "markup" not in obsolete["msgs"][1]
    assert "markup" not in next(
        event for event in state["events"] if event["id"] == reply["id"]
    )
    current_thread = threads[current_parent["id"]]
    current_message = next(
        message for message in current_thread["msgs"] if message["id"] == current["id"]
    )
    assert current_message["markup"] == current["markup"]
    readings = data_contracts_model.page_data_document_readings(
        page_dir, events_model.read_events(page_dir), {}
    )
    assert [
        label for _elements, label, _registry in readings if label.startswith("event ")
    ] == [f"event {current['id']!r} markup"]
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", '<p id="frozen-options">Reused id.</p></main>')
    )
    refused = check(page_dir)
    assert refused.exit_code != 0
    assert 'ids already taken by message markup: ["frozen-options"]' in refused.output


def test_unavailable_capture_id_stays_reserved_in_selected_sample_threads(page_dir):
    """A carried answer cannot settle a child widget reusing its retired owner id."""
    (page_dir / "index.html").write_text(PAGE)
    assert revisioning_model.activate_source(page_dir).revision == 1
    parent = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Can we use this proposal?",
        },
    )
    thread_model.post_reply(
        page_dir,
        {"to": parent["id"], "for": parent["id"]},
        "Here is the proposal.",
        '<lf-ask id="proposal-ask"><h3>Choose this proposal</h3>'
        '<lf-options id="sug-reserved" choose multiple>'
        '<lf-option id="proposal-copy">Keep this.</lf-option>'
        "</lf-options></lf-ask>",
    )
    registry = require_registry(page_dir)
    answer = append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-reserved",
            "action": "choose",
            "detail": {"value": ["proposal-copy"]},
            "meaning": {
                **event_meaning_model.state_meaning(
                    {
                        "widget": "sug-reserved",
                        "action": "choose",
                        "detail": {"value": ["proposal-copy"]},
                    },
                    registry["lf-options"],
                    "thread",
                    "lf-options",
                ),
                "answer": parent["id"],
            },
        },
    )
    assert answer["meaning"]["answer"] == parent["id"]
    marker = files_model.revision_path(page_dir, 1)
    marker.unlink()
    assert files_model.list_revisions(page_dir) == []
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            f'<template id="practice" data-sample data-sample-threads="{parent["id"]}">'
            '<lf-ask id="child-ask"><h3>Choose</h3>'
            '<lf-options id="sug-reserved" choose multiple>'
            '<lf-option id="child-proposal">A new proposal.</lf-option>'
            "</lf-options></lf-ask></template></main>",
        )
    )

    refused = check(page_dir)

    assert refused.exit_code != 0
    assert (
        "sample 'practice': ids already taken by message markup: [\"sug-reserved\"]"
        in refused.output
    )


def test_revision_inventory_retains_duplicate_current_capture_refusal(page_dir):
    """Ignoring old formats does not choose between two complete current markers."""
    revisioning_model.activate_source(page_dir)
    marker = files_model.revision_path(page_dir, 1)
    duplicate = marker.parent / "r1-0123456789abcdef"
    shutil.copytree(marker.with_suffix(""), duplicate)
    duplicate.with_suffix(".html").write_bytes(marker.read_bytes())
    with pytest.raises(Refused, match="same order"):
        files_model.list_revisions(page_dir)


def test_artifact_cache_holds_a_bundle_by_its_content_addressed_path(page_dir):
    """A revision's name carries its manifest's digest, so a held bundle is read
    once; a later change to its files is not reread."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    revision = files_model.latest_revision(page_dir)
    first = artifact_model.read_artifact(page_dir, revision)
    _replace_manifest(page_dir, revision)

    assert artifact_model.read_artifact(page_dir, revision) is first


def test_stylesheet_dependencies_obey_the_same_capture_boundary(page_dir):
    authored = page_dir / "page"
    (authored / "data.json").write_text('{"value": 1}')
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    (page_dir / "index.html").write_text(
        PAGE.replace("</head>", '<link rel="stylesheet" href="/page/style.css"></head>')
    )
    previous = files_model.latest_revision(page_dir)
    for css, diagnostic in [
        ('@import "ftp://outside.example/style.css";', "http(s) URL"),
        ('@import "./data.json";', "CSS MIME"),
        ('@import url("./data.json");', "CSS MIME"),
        ('main { background: url("../../private.svg"); }', "escapes"),
        ('main { background: url("./missing.svg"); }', "cannot capture"),
    ]:
        (authored / "style.css").write_text(css)
        refused = revisioning_model.activate_source(page_dir)
        assert refused.error and diagnostic in refused.error, (css, refused.error)
        assert refused.revision == previous and not refused.created


def test_an_image_loads_from_any_server(page_dir):
    images = (
        '<p><img src="https://outside.example/a.png?s=40" alt="a">'
        '<img src="//outside.example/b.png" alt="b"></p>\n</section>'
    )
    (page_dir / "index.html").write_text(PAGE.replace("</section>", images, 1))
    assert revisioning_model.activate_source(page_dir).error is None


@pytest.mark.parametrize(
    "authored, expected",
    [
        ("<script>window.x = 1;</script>", "parser-blocking-script"),
        (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
            "parser-blocking-script",
        ),
        (
            '<script type="module" async src="https://unpkg.com/d3"></script>',
            "async-script",
        ),
    ],
    ids=["inline-classic", "blocking-classic", "async-module"],
)
def test_check_runs_each_script_after_leaf_reads_the_page(page_dir, authored, expected):
    """A page's scripts are its author's, classic or module, from any server, but
    each runs after Leaf reads the page."""
    version = page_dir / "index.html"
    version.write_text(PAGE.replace("</main>", f"{authored}</main>"))

    status, findings = check_findings(page_dir)

    assert status == 1
    assert [f.code for f in findings] == [expected]


def test_a_quote_crosses_an_upgraded_verbatim_wrapper(page_dir):
    quote = "jobs/backfill.py:88. Which plan should lead?"

    result = comment(page_dir, "--quote", quote, "--text", "compare these")

    assert result.exit_code == 0, result.output
    anchor = json.loads(result.output)["anchor"]
    assert anchor["quote"] == quote
    assert anchor["section"] == "plan"


def test_an_anchorless_comment_uses_the_last_good_revision_during_an_edit(page_dir):
    """A general comment captures no source, so an unfinished edit cannot block it."""
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    revision = files_model.latest_revision(page_dir)
    (page_dir / "index.html").write_text("<main>unfinished")

    result = comment(page_dir, "--text", "What should change?")

    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["revision"] == revision
    assert "anchor" not in event

    anchored = comment(page_dir, "--quote", "Plan", "--text", "Change this")
    assert anchored.exit_code != 0
    assert "cannot use invalid index.html" in anchored.output


def test_compositional_verbatim_uses_passage_collapse_and_structured_boundaries():
    registry = {
        "lf-shell": {"x-upgrade": True, "x-verbatim": True},
        "lf-piece": {"x-upgrade": True, "x-verbatim": True},
    }
    plain = passages_model.page_passages(
        structure_model.SourceDocument(
            '<lf-shell id="shell"><p>set<em>up</em></p>'
            "<lf-piece>child words</lf-piece><p>after</p></lf-shell>"
        ),
        registry,
    ).verbatim[("page", None, 0)]
    wrapped = passages_model.page_passages(
        structure_model.SourceDocument(
            '<lf-shell id="shell"><p><span>set</span>up</p>'
            "<lf-piece>different child rendering</lf-piece><p>after</p></lf-shell>"
        ),
        registry,
    ).verbatim[("page", None, 0)]
    separated = passages_model.page_passages(
        structure_model.SourceDocument(
            '<lf-shell id="shell"><p>set up</p>'
            "<lf-piece>child words</lf-piece><p>after</p></lf-shell>"
        ),
        registry,
    ).verbatim[("page", None, 0)]
    non_js_whitespace = passages_model.page_passages(
        structure_model.SourceDocument(
            '<lf-shell id="shell">\u0085edge\u0085</lf-shell>'
        ),
        registry,
    ).verbatim[("page", None, 0)]

    assert (
        plain
        == wrapped
        == [
            {"text": "setup"},
            {"boundary": [["page", None, 0], 0, "lf-piece", None]},
            {"text": "after"},
        ]
    )
    assert separated[0] == {"text": "set up"}
    assert non_js_whitespace == [{"text": "\u0085edge\u0085"}]


def test_an_anchor_resolves_by_context_the_browser_keeps():
    """Context is trimmed of the collapse class alone, as the browser trims it, so a
    character only Python calls whitespace stays part of the context the browser
    captured. U+0085 before the first of two equal words is all that tells them apart."""
    passages = passages_model.page_passages(
        structure_model.SourceDocument(f'<p id="p">\u0085repeat {"x" * 40} repeat</p>'),
        {},
    )
    anchor = {"quote": "repeat", "prefix": "\u0085", "suffix": "x" * 24}

    assert anchor_capture_model.resolve_quote(passages, anchor) == 1


def test_file_readings_follow_browser_tree_recovery():
    html = (
        '<main id="page"><table id="grid"><p id="lead">Lead'
        '<tr><td>Cell</table><p id="tail">Tail</main>'
    )

    parsed = structure_model.SourceDocument(html)
    [main] = parsed.content
    assert [node["tag"] for node in main["content"]] == ["p", "table", "p"]
    assert [node["tag"] for node in main["content"][1]["content"]] == ["tr"]

    passages = passages_model.page_passages(parsed)
    assert passages.text == "Lead Cell Tail"
    assert passages.enclosing["lead"] == ("page", "lead")
    assert passages.enclosing["grid"] == ("page", "grid")


@pytest.mark.parametrize(
    ("fragment", "tags", "ids"),
    [
        (
            '<tr id="row"><td id="number">12</td></tr>',
            ["tr", "td"],
            {"row", "number"},
        ),
        (
            (
                '<option id="first">First</option><optgroup id="group">'
                '<option id="second">Second</option></optgroup>'
            ),
            ["option", "optgroup", "option"],
            {"first", "group", "second"},
        ),
    ],
    ids=["table", "select"],
)
def test_example_fragments_retain_context_sensitive_elements(fragment, tags, ids):
    parsed = structure_model.SourceDocument(fragment, fragment=True)
    assert [node["tag"] for node in parsed.nodes] == tags
    assert parsed.ids == ids
    assert parsed.errors == [] and parsed.unclosed == []


def test_option_passages_read_rendered_markdown_words():
    source = structure_model.SourceDocument(
        '<main><lf-options id="choices"><lf-option id="leave">'
        "Can we leave it to the _widget_? <code>Already HTML</code> "
        "[unsafe label](javascript:alert(1)) "
        "![unsafe alt](javascript:alert(1))"
        "</lf-option></lf-options></main>"
    )

    passages = passages_model.page_passages(
        source, {"lf-option": {"x-text-format": "inline-markdown"}}
    )
    assert passages.text == (
        "Can we leave it to the widget? Already HTML unsafe label unsafe alt"
    )


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parents[1] / "option_markdown_cases.json").read_text()),
)
def test_option_markdown_file_words_match_browser_cases(case):
    source = structure_model.SourceDocument(
        f'<main><lf-option id="choice">{case["source"]}</lf-option></main>'
    )
    passages = passages_model.page_passages(
        source, {"lf-option": {"x-text-format": "inline-markdown"}}
    )
    assert passages.text == case["words"]


def test_markdown_body_passages_preserve_source_state_and_read_visible_words():
    """Authored and replayed Markdown share anchors without losing their source value."""
    registry = {
        "lf-draft": {
            "x-content": "data",
            "x-upgrade": True,
            "x-verbatim": True,
            "x-text-format": "markdown",
        }
    }
    source = "**Keep** `--dry-run`.\n\n- First\n- [Second](https://example.com)"
    doc = structure_model.SourceDocument(
        f'<main><lf-draft id="note"><pre>{source}</pre></lf-draft></main>'
    )
    reading = passages_model.SourceReading(doc, registry)
    assert reading.spoken["note"].words == "Keep --dry-run. First Second"
    spec = {"record": {"kind": "body"}}
    assert (
        projection_model.markup_value("note", spec, doc.by_id, reading.spoken, registry)
        == source
    )
    edited = "**Changed** `--dry-run`.\n\n- First\n- [Second](https://example.com)"
    projected = passages_model.page_passages(
        doc, registry, rewrites={"note": ("edit", edited)}
    )
    assert projected.text == "Changed --dry-run. First Second"
    assert projected.verbatim == {("page", None, 0): [{"text": projected.text}]}


def test_structural_errors_distinguish_recovery_from_ambiguous_source():
    optional = structure_model.SourceDocument("<main><p>First<div>Second</div></main>")
    assert optional.errors == [] and optional.unclosed == []

    unclosed = structure_model.SourceDocument("<main><section>Text</main>")
    assert unclosed.unclosed == [("section", 1)]

    caption = structure_model.SourceDocument(
        "<main><table><caption>Title<tbody><tr><td>Cell</table></main>"
    )
    assert caption.unclosed == []

    svg = structure_model.SourceDocument(
        '<main><svg id="plot"><circle cx="5" cy="5" r="4"/></main>'
    )
    assert svg.unclosed == [("svg", 1)]

    duplicate_body = structure_model.SourceDocument(
        "<body><main>Text</main></body><body></body>"
    )
    assert duplicate_body.body_lines == [1, 1]


def construction_nodes(content):
    """Index a thread message's emitted construction by id."""
    nodes = {}
    for node in content:
        if isinstance(node, dict):
            if identity := node["attrs"].get("id"):
                nodes[identity] = node
            nodes.update(construction_nodes(node["content"]))
    return nodes


def folded(page_dir, board="b1"):
    """Each column of `board` in the order the page draws it: the position fold over
    the revision `page state` activates."""
    revision = state_json(page_dir)["active"]["revision"]
    _, reading, _ = read_served_page(
        read_page(page_dir, events_model.read_events(page_dir))
    )
    document = reading.documents[revision]
    registry = require_registry(page_dir)
    return projection_model.folded_positions(
        board,
        "move",
        registry["lf-board"]["x-state"]["move"]["record"],
        document.document.by_id,
        document.spoken,
        registry,
        document.projection,
    )


def test_undoing_one_cards_move_leaves_the_other_cards_order(page_dir):
    """Card d goes to the top, card c right under it, then d's move is undone: c
    keeps its place above a, since the move that put it there still stands. An index
    re-read against the column d's undo left would put c under a."""
    cards = [(c, "", c.upper()) for c in ("a", "b", "c", "d")]
    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", _board(cards, []) + "</main>")
    )
    publish(page_dir)
    moved = [
        append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "b1",
                "action": "move",
                "detail": {"unit": card, "value": "c-todo", "rank": rank},
            },
        )
        # The ranks lf-board sends: d before a's "1", then c between d and a.
        for card, rank in (("d", "0i"), ("c", "0r"))
    ]

    assert folded(page_dir)["c-todo"] == ["d", "c", "a", "b"]
    append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": moved[0]["id"]}
    )
    assert folded(page_dir)["c-todo"] == ["c", "a", "b", "d"]


RANK_CASES = json.loads((Path(__file__).parents[1] / "rank_cases.json").read_text())


def test_rank_rules_match_the_browser_cases():
    """`tests/runtime/board-order.test.mjs` reads the same cases against
    `projection/model.js`, so the two runtimes rank authored units alike and the
    append door admits what a widget computes."""
    assert RANK == RANK_CASES["pattern"]
    for index, rank in RANK_CASES["authored"]:
        assert projection_model.authored_rank(index) == rank
        assert re.fullmatch(RANK, rank)
    assert all(re.fullmatch(RANK, r) for r in RANK_CASES["valid"])
    assert not any(re.fullmatch(RANK, r) for r in RANK_CASES["invalid"])
    # The append door reads the rank through the detail schema, whose `pattern`
    # searches rather than fully matches, so it must refuse the same cases.
    board = model_layer()["lf-board"]
    rank = detail_schema(board, board["x-state"]["move"])["properties"]["rank"]
    assert not any(schema_error(rank, r) is None for r in RANK_CASES["invalid"])
    assert all(schema_error(rank, r) is None for r in RANK_CASES["valid"])


@pytest.mark.parametrize(
    "case", RANK_CASES["folds"], ids=[case["name"] for case in RANK_CASES["folds"]]
)
def test_the_position_fold_matches_the_browser_cases(case):
    """`tests/runtime/board-order.test.mjs` folds the same authored containers and
    standing moves through `foldWidgetStates`, so the two runtimes leave every
    container in one order."""
    registry = model_layer()
    columns = "".join(
        f'<lf-column id="{column}" label="{column}">'
        + "".join(f'<lf-card id="{card}">{card}</lf-card>' for card in cards)
        + "</lf-column>"
        for column, cards in case["authored"].items()
    )
    document = structure_model.SourceDocument(
        f'<main><lf-board id="board">{columns}</lf-board></main>'
    )
    spec = registry["lf-board"]["x-state"]["move"]
    desired = {
        ("board", move["card"], "move"): (
            {
                "seq": seq,
                "detail": {
                    "unit": move["card"],
                    "value": move["to"],
                    "rank": move["rank"],
                },
                # A move is absorbed where the markup authors its container unlike
                # the units it was made among.
                "meaning": {"among": []} if move.get("absorbed") else {},
                "widget": "board",
            },
            spec,
        )
        for seq, move in enumerate(case["moves"], start=1)
    }
    projection = projection_model.StateProjection(
        actions={},
        reports={},
        desired=desired,
        report_settlements={},
        classified={},
        absorbed=frozenset(),
        standing=frozenset(),
    )
    order = projection_model.folded_positions(
        "board",
        "move",
        spec["record"],
        document.by_id,
        passages_model.SourceReading(document, registry).spoken,
        registry,
        projection,
    )
    assert order == case["order"]


def test_a_position_is_never_read_as_one_actions_markup_value():
    """A unit's place is read against the whole fold (`recorded_state`); reading it
    the way a pick or a value is read would fall through to the unit's words."""
    spec = {"record": {"kind": "position", "within": "lf-column"}}
    with pytest.raises(ValueError, match="recorded_state"):
        projection_model.markup_value("x", spec, {}, {}, {})


def _todo_order(page_dir):
    return folded(page_dir)["c-todo"]


def _write_board(page_dir, todo, done=()):
    def cards(ids):
        return [(c, "", c.upper()) for c in ids]

    (page_dir / "index.html").write_text(
        PAGE.replace("</main>", _board(cards(todo), cards(done)) + "</main>")
    )


def _move(page_dir, card, to, rank, revision=1):
    return append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "b1",
            "action": "move",
            "detail": {"unit": card, "value": to, "rank": rank},
        },
    )


def _drop_x_between_a_and_b(page_dir):
    """v1 has todo `a b c` and x in done; the user drops x between a and b, at the
    rank lf-board computes between their authored ranks."""
    _write_board(page_dir, "abc", "x")
    publish(page_dir)
    move = _move(page_dir, "x", "c-todo", "1i")
    assert _todo_order(page_dir) == ["a", "x", "b", "c"]
    return move


@pytest.mark.parametrize(
    "todo",
    [
        "baxc",  # a and b swapped: x still right after a
        "naxbmc",  # cards added around the gap
        "xabc",  # x moved to the front
    ],
)
def test_authored_cards_can_move_to_any_gap_after_a_user_move(page_dir, todo):
    """The user put x between a and b: right after a, among the cards both versions
    list. A version that keeps that says what the user said however it arranges or
    adds cards elsewhere."""
    _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, todo)
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_a_move_on_a_replaced_revision_lands_only_where_its_column_held(page_dir):
    """A rank read on r1 lands in another gap on r2 once r2 adds a card to the
    column, so the door refuses that move, with words for the user apart from the
    reason. A newer revision that left the column alone takes it."""
    _write_board(page_dir, "abc", "x")
    publish(page_dir)
    _write_board(page_dir, "nabc", "x")
    publish(page_dir)
    with pytest.raises(
        events_model.EventRefused, match="authors 'c-todo' differently"
    ) as refused:
        _move(page_dir, "x", "c-todo", "1i")
    assert refused.value.user == "The page changed while you moved this; move it again."
    _move(page_dir, "x", "c-todo", "2i", revision=2)
    assert _todo_order(page_dir) == ["n", "a", "x", "b", "c"]

    (page_dir / "index.html").write_text(
        (page_dir / "index.html").read_text().replace("<h2>Plan</h2>", "<h2>Plans</h2>")
    )
    publish(page_dir)
    _move(page_dir, "b", "c-done", "i", revision=2)
    assert _todo_order(page_dir) == ["n", "a", "x", "c"]


def test_page_init_reports_malformed_current_source_after_revendoring(page_dir):
    """A real layer repair reports current declaration errors that block activation."""
    source = page_dir / "index.html"
    source.write_text(PAGE.replace("</main>", '<p id="plan">Duplicate.</p></main>'))
    theme = page_dir / "theme.css"
    theme.write_text(theme.read_text() + "\n/* repair installed edit */\n")
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert "index.html will not activate until" in result.output
    assert "duplicate id" in result.output


def test_page_state_lists_each_user_move_over_the_active_html(page_dir):
    """`page state` names the active revision's HTML and lists every standing move
    over it with the words, choice or place it carries, so a successor reads the page
    as the user sees it without a second copy of the document."""
    markup = PAGE.replace(
        "</main>",
        OPTIONS.format(
            a=" chosen", b="", chip="", shim="Keep the shim.", stage="Stage it."
        )
        + '<lf-draft id="summary"><pre>Ship on Friday.</pre></lf-draft>'
        + _board([X, Y], [])
        + '<p id="explanation"><strong>Keep</strong> <em>spaces</em>.</p></main>',
    )
    (page_dir / "index.html").write_text(markup)
    publish(page_dir)
    actions = [
        ("g1", "add", {"option": "o-user", "text": "Try a canary."}),
        ("g1", "choose", {"value": ["o-user"]}),
        (
            "summary",
            "edit",
            {"value": "  Ship after migration.\n\nKeep  two spaces.\n"},
        ),
        ("b1", "move", {"unit": "card-y", "value": "c-done", "rank": "i"}),
        ("b1", "move", {"unit": "card-x", "value": "c-done", "rank": "9"}),
    ]
    for widget, action, detail in actions:
        append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
    state = state_json(page_dir)
    assert "content" not in state
    active = page_dir / state["active"]["file"]
    assert active.read_text() == markup
    assert sorted(
        (e["widget"], e["action"], json.dumps(e["detail"])) for e in state["state"]
    ) == sorted((w, a, json.dumps(d)) for w, a, d in actions)
    assert folded(page_dir)["c-done"] == ["card-x", "card-y"]

    # A successor edits unrelated wording in index.html and writes the moves where
    # the fold puts them; the other moves stay effective without transcription.
    path = page_dir / state["source"]["file"]
    path.write_text(
        path.read_text()
        .replace("<strong>Keep</strong>", "<strong>Preserve</strong>")
        .replace(_board([X, Y], []), _board([], [X, Y]))
    )
    revised = state_json(page_dir)
    assert revised["source"]["live"], revised["source"]["error"]
    assert (
        "<strong>Preserve</strong>"
        in (page_dir / revised["active"]["file"]).read_text()
    )
    assert {(e["widget"], e["action"]) for e in revised["state"]} >= {
        ("g1", "choose"),
        ("summary", "edit"),
    }

    # A rejected candidate leaves the active revision, and its HTML, as they were.
    path.write_text(
        "\n\n" + path.read_text().replace('id="explanation"', 'id="summary"')
    )
    rejected = state_json(page_dir)
    assert not rejected["source"]["live"] and rejected["source"]["error"]
    assert rejected["active"] == revised["active"]


def test_page_state_names_each_bound_source_and_its_failures(page_dir):
    """`data_bindings` names each source and its consumers; corruption of a stored
    publication's value past its contract reads as that source's error."""
    declare_data_input(
        page_dir, "builds", {"type": "array", "items": {"type": "string"}}
    )
    runner = CliRunner()
    updated = runner.invoke(
        cli_model.cli, ["data", "set", str(page_dir), "builds"], input='["passing"]'
    )
    assert updated.exit_code == 0, updated.output
    stored = data_model.source_file(page_dir, "builds")
    state = state_json(page_dir)
    assert stored == page_dir / state["data"]["dir"] / "builds.json"
    assert json.loads(stored.read_text())["value"] == ["passing"]
    [consumer] = state["data_bindings"]["builds"]["consumers"]
    assert consumer["widget"] == "test-data"
    assert state["data"]["errors"] == []

    publication = json.loads(stored.read_text())
    stored.write_text(json.dumps({**publication, "value": ["passing", 3]}))
    [error] = state_json(page_dir)["data"]["errors"]
    assert "builds" in error


def test_sample_templates_bind_the_parents_producer_sources(page_dir):
    """A disposable child's data consumers remain visible to its parent producer."""
    declare_data_input(page_dir, "builds", {"type": "array"}, activate=False)
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            '<lf-test-data id="test-data" source="builds"></lf-test-data>',
            '<lf-sample id="live-builds" window><template id="builds-page" data-sample>'
            '<lf-test-data id="child-builds" source="builds"></lf-test-data>'
            "</template></lf-sample>",
        )
    )
    publish(page_dir)
    data_model.cmd_data_set(page_dir, "builds", ["passing"])
    state = state_json(page_dir)
    assert read_page_data(page_dir)["sources"]["builds"]["value"] == ["passing"]
    binding = state["data_bindings"]["builds"]
    assert binding["contract"] == "test-data"
    assert binding["consumers"] == [
        {
            "widget": "child-builds",
            "input": "data",
            "document": "revision r1 sample 'builds-page'",
        }
    ]


def test_thread_read_reads_frozen_construction(page_dir):
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Choose a route.",
            "markup": 'Before <lf-options id="frozen" choose><lf-option id="first">First</lf-option><lf-option id="second">Second</lf-option></lf-options> after.',
        },
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "frozen",
            "action": "choose",
            "detail": {"value": ["second"]},
        },
    )
    runner = CliRunner()
    result = runner.invoke(cli_model.cli, ["page", "state", str(page_dir), root["id"]])
    assert result.exit_code == 0, result.output
    reading = json.loads(result.output)
    assert reading["thread"]["id"] == root["id"]
    [message] = reading["content"]
    assert message["text"] == "Choose a route."
    assert message["content"][0] == "Before "
    assert message["content"][-1] == " after."
    frozen = construction_nodes(message["content"])
    assert "chosen" in frozen["second"]["attrs"]
    assert frozen["frozen"]["edit"] == {
        "kind": "thread",
        "thread": root["id"],
    }
    assert message["source"]["event"] == root["id"]
    drawing = {
        "format": "leaf-drawing/3",
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
        "box": [640.5, 96],
        "viewport": [1200, 900],
        "scheme": "light",
    }
    drawn = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "plan-choice-decision"},
            "drawing": drawing,
        },
    )
    result = runner.invoke(cli_model.cli, ["page", "state", str(page_dir), drawn["id"]])
    assert result.exit_code == 0, result.output
    [drawn_message] = json.loads(result.output)["content"]
    assert "text" not in drawn_message
    assert drawn_message["drawing"] == drawing
    refused = runner.invoke(cli_model.cli, ["page", "state", str(page_dir), "missing"])
    assert refused.exit_code != 0 and "names no thread or widget" in refused.output


def test_version_descriptors_select_only_available_stamped_revisions():
    """Public history orders stamps and excludes a note whose revision is absent."""
    events = [
        {"kind": "note", "version": revision, "revision": revision}
        for revision in (4, 2, 3, 1)
    ]
    assert files_model.version_descriptors(events, {1, 2, 3}) == [
        {
            "version": revision,
            "revision": revision,
            "url": f"/versions/v{revision}.html",
        }
        for revision in range(1, 4)
    ]


def test_check_refuses_noscript_words_the_browser_never_renders(page_dir):
    """In a scripting browser noscript is hidden, while the file reader takes its
    content for page words. Refusal prevents anchoring on text no user can see."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2><noscript>Fallback words.</noscript>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "noscript", "<noscript>")


def test_check_admits_a_template_whose_words_no_anchor_reaches(page_dir):
    """A page module may clone a template, so check admits one. The browser and
    the file parser both keep its contents out of the tree, so no anchor reaches
    its words."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><template id="row"><p>Cloned words.</p></template>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    text = passages_model.page_passages(
        structure_model.SourceDocument((page_dir / "index.html").read_text()), {}
    ).text
    assert "Plan" in text
    assert "Cloned words." not in text


def test_check_rejects_widget_violations(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            '<a href="https://example.test/jobs/backfill.py#L88"><code>jobs/backfill.py:88</code></a>',
            '<lf-gloss tip="A short explanation"/>'
            "<figure/>"
            "<lf-bogus></lf-bogus>"
            '<lf-column id="bad-tone" label="S" tone="medium"></lf-column>'
            '<lf-option id="stray"><strong>S</strong></lf-option>'
            '<lf-diagram id="Bad_ID"><pre>graph LR</pre><em>x</em></lf-diagram>'
            '<lf-diagram id="bare-body">graph LR</lf-diagram>',
        ).replace('<lf-option id="flag-first"', "<lf-option")
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    # Both the widget and the plain <figure/>: the slash misleads a browser on
    # any non-void tag, not only on the vocabulary's.
    assert [f.at for f in found(findings, "self-closing")] == ["<lf-gloss>", "<figure>"]
    assert found(findings, "unknown-widget", "<lf-bogus>")
    assert found(findings, "unknown-word", "<lf-column>", attr="tone", value="medium")
    assert found(findings, "not-member", "<lf-option>", owners=["lf-options"])
    assert found(findings, "attribute-schema", "<lf-option>", keyword="required")
    assert found(
        findings, "attribute-schema", "<lf-diagram>", keyword="pattern", path=["id"]
    )
    # A stray element beside the <pre>, and a body that never opened one: both are
    # the same rule, since the <pre> is what carries the whitespace the notation needs.
    assert [f.values["children"] for f in found(findings, "data-body")] == [
        ["pre", "em"],
        [],
    ]
    assert found(findings, "text-outside-pre", "<lf-diagram>")


def test_check_rejects_a_widget_language_nothing_will_color(page_dir):
    """A widget attribute that declares itself a language (x-language) is held to the
    layer's $languages list. A plain <pre><code class="language-…"> claims no
    vocabulary: one the layer can't color stays the ink of an uncolored block."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>\n"
            '<pre><code class="language-pythn">x = 1</code></pre>\n'
            '<lf-code id="walk-bad" language="pythn"><pre>z = 3\n</pre></lf-code>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [(f.at, f.values["value"]) for f in found(findings, "unknown-word")] == [
        ("<lf-code>", "pythn")
    ]


def test_a_widget_that_declares_a_language_is_checked_by_that_alone(page_dir):
    """The list is the layer's fact, not one widget's, so nothing in the lint knows
    which widget takes a language: a tag whose declaration carries x-language is held to
    $languages on the strength of the declaration. A thirteenth widget that colors
    something — a terminal transcript, a diff — is covered without the lint moving."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-gloss"]["properties"]["dialect"] = {"type": "string"}
    registry["lf-gloss"]["x-language"] = "dialect"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<lf-gloss tip="Feeder layout" dialect="lisp">feeders</lf-gloss>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings,
        "unknown-word",
        "<lf-gloss>",
        attr="dialect",
        value="lisp",
        declares="x-language",
    )


def test_every_declared_attribute_and_enum_stands_in_an_example():
    """The corpus floor one level down from tags (examples/AGENTS.md): where an
    attribute or an enum value changes what a user sees, a page shows it. The
    batch that raised the corpus to this line surfaced five real defects on the
    day it landed, so the floor ratchets: the next declared attribute joins the
    corpus by being declared. The exemptions are the log-only names the doc
    enumerates — restated, overruled and resolves each name something the log
    holds, which a one-version corpus cannot earn.

    The floor reads every package the examples select rather than a list written
    here, which is how it followed lf-diagram and lf-diff into their own packages.
    Widening it that way brought pr-review's two widgets under the floor for the
    first time and found one uncovered attribute, exempted below."""
    registry = validation_model.incoming_registry(SHIPPED_PACKAGES)
    used = {}
    for path in (Path(__file__).parents[2] / "examples").glob("*.html"):
        for rec in structure_model.SourceDocument(path.read_text()).lf_elements:
            for attr, value in rec["attrs"].items():
                used.setdefault(rec["tag"], {}).setdefault(attr, set()).add(value)
    missing = []
    for tag, entry in sorted(registry.items()):
        if not tag.startswith("lf-"):
            continue
        for attr, spec in entry.get("properties", {}).items():
            if attr in {"restated", "overruled", "resolves"}:
                continue
            seen = used.get(tag, {}).get(attr)
            if seen is None:
                missing.append(f"{tag}[{attr}]")
            else:
                missing.extend(
                    f'{tag}[{attr}="{value}"]'
                    for value in spec.get("enum", [])
                    if value not in seen
                )
    assert missing == [], missing


def test_pane_grammar_follows_the_declared_role_across_packages(page_dir):
    """A package can supply a pane under its own name without joining a built-in tag
    list: the role its registry entry declares is what the grammar reads, and the page
    arranges both panes in a workspace however it likes."""
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-zone"] = {
        "description": "A project package's differently named pane.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "label": {"type": "string"},
        },
        "required": ["id", "label"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-reading-role": "pane",
        "x-upgrade": False,
    }
    registry_path.write_text(json.dumps(registry))
    version = page_dir / "index.html"
    regions = """<header><h2>Plan</h2></header>
  <div id="regions" style="display: grid; grid-template-columns: 1fr 2fr">
    <lf-zone id="queue" label="Queue"><p>First</p></lf-zone>
    <lf-pane id="detail" label="Detail"><p>Second</p></lf-pane>
  </div>
  <footer><p>Finish</p></footer>"""
    version.write_text(
        PAGE.replace("<main>", '<main class="layout-workspace">').replace(
            PAGE[PAGE.index('<section id="plan">') : PAGE.index("</main>")], regions
        )
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output
    # The same grammar holds the package's pane to one body.
    version.write_text(
        version.read_text().replace(
            "<p>First</p></lf-zone>", "<p>First</p><p>Split</p></lf-zone>"
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "pane-body", "<lf-zone>", body=["p", "p"])


def test_pane_grammar_rejects_misplaced_slots_and_split_content(page_dir):
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            """<h2>Plan</h2>
<lf-pane id="queue" label="Queue"><p>Before.</p><header><h3>Queue</h3></header></lf-pane>
<lf-pane id="detail" label="Detail"><p>First</p><p>Split</p></lf-pane>
<lf-pane id="loose" label="Loose">Loose text</lf-pane>""",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "pane-header-first", "<lf-pane>", line=10)
    # The split body and the loose text, each named by its own line.
    assert [
        (f.values["line"], f.values["body"]) for f in found(findings, "pane-body")
    ] == [(11, ["p", "p"]), (12, ["#text"])]


def test_a_layer_naming_no_languages_refuses_every_word_rather_than_none(page_dir):
    """A layer that names none colors none, so a page declaring one is asking for
    something it cannot get. The list is therefore read and indexed, never tested for
    emptiness: an empty list that stood the check down would be a check retiring itself
    the moment its list moved — and this is the check whose failures the user can't
    see either way, so silence is the one outcome it must not have."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$languages"]["names"] = []
    registry["$languages"]["paths"] = {}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>\n"
            '<lf-code id="walk" language="python"><pre>x = 1\n</pre></lf-code>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "unknown-word", "<lf-code>", value="python", known=[])


def test_check_rejects_loose_content_in_items_container(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", "<lf-options>\nloose text\n<p>stray</p>\n<br/>")
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    # Self-closed strays count as children too.
    assert found(
        findings,
        "stray-members",
        "<lf-options>",
        admits=["lf-option"],
        found=["br", "p"],
    )
    assert found(findings, "loose-text", "<lf-options>")


def test_retired_question_and_recommendation_attributes_are_rejected(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options label="Which plan?">').replace(
            'id="backfill-first">', 'id="backfill-first" recommended>'
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [f.at for f in found(findings, "attribute-schema")] == [
        "<lf-options>",
        "<lf-option>",
    ]
    assert {f.values["keyword"] for f in findings} == {"additionalProperties"}


def test_tabs_reject_structural_violations(page_dir):
    # A label-less panel, a stray panel outside lf-tabs, and loose text between
    # panels are each refused.
    bad = """<lf-tabs id="ws">
  loose text
  <lf-tab id="ws-a"><p>x</p></lf-tab>
</lf-tabs>
<lf-tab id="ws-stray" label="Stray"><p>y</p></lf-tab>
<lf-options>"""
    (page_dir / "index.html").write_text(PAGE.replace("<lf-options>", bad))
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "attribute-schema", "<lf-tab>", keyword="required")
    assert found(findings, "not-member", "<lf-tab>", owners=["lf-tabs"])
    assert found(findings, "loose-text", "<lf-tabs>")


def test_suggestion_rejects_malformed_shapes(page_dir):
    for markup, expected in [
        (
            '<lf-suggestion id="sug-a"></lf-suggestion><lf-options>',
            ("empty-suggestion", "<lf-suggestion id=sug-a>"),
        ),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new><p>x</p></lf-new>'
                "<lf-new><p>y</p></lf-new></lf-suggestion><lf-options>"
            ),
            ("repeated-slot", "<lf-suggestion id=sug-a>"),
        ),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new>'
                '<lf-suggestion id="sug-b"><lf-new>x</lf-new></lf-suggestion>'
                "</lf-new></lf-suggestion><lf-options>"
            ),
            ("nested-suggestion", "<lf-suggestion id=sug-b>"),
        ),
        (
            "<lf-old><p>orphan</p></lf-old><lf-options>",
            ("not-member", "<lf-old>"),
        ),
        (
            (
                '<lf-suggestion id="sug-a" resolves="nosuch"><lf-new><p>x</p></lf-new>'
                "</lf-suggestion><lf-options>"
            ),
            ("unknown-thread", "<lf-suggestion id=sug-a>"),
        ),
    ]:
        (page_dir / "index.html").write_text(PAGE.replace("<lf-options>", markup))
        status, findings = check_findings(page_dir)
        assert status == 1, markup
        assert expected in [(f.code, f.at) for f in findings], markup


def test_reply_refuses_a_suggestion(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Fixed:",
            "--markup",
            '<lf-suggestion id="sug-x"><lf-new><p>fixed</p></lf-new></lf-suggestion>',
        ],
    )
    assert result.exit_code != 0
    assert "frozen in the log" in result.output


def test_response_addresses_one_obligation_and_activates_the_current_source(page_dir):
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [comment],
            session=claim["id"],
            turn=claim["turn"],
        )
    updated = PAGE.replace("<h2>Plan</h2>", "<h2>Updated plan</h2>")
    (page_dir / "index.html").write_text(updated)

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Updated.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["parent"] == "c1"
    assert files_model.list_revisions(page_dir) == [1, 2]
    assert files_model.revision_path(page_dir, 2).read_text() == updated
    reply = events_model.read_events(page_dir)[-1]
    assert reply["parent"] == "c1"
    assert reply["responds"] == "c1"


def test_reply_refuses_an_invalid_current_source(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [comment],
            session=claim["id"],
            turn=claim["turn"],
        )
    (page_dir / "index.html").write_text("<main>unfinished")

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Updated.",
        ],
    )

    assert result.exit_code != 0
    assert "cannot reply while index.html is invalid" in result.output
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )


def test_response_reference_selects_one_of_several_obligations(page_dir):
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    comments = []
    for event_id in ("c1", "c2"):
        comments.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "comment",
                    "id": event_id,
                    "author": "user",
                    "text": f"question {event_id}",
                },
            )
        )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            comments,
            session=claim["id"],
            turn=claim["turn"],
        )
    updated = PAGE.replace("<h2>Plan</h2>", "<h2>Updated plan</h2>")
    (page_dir / "index.html").write_text(updated)

    ambiguous = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", "--done", "--text", "Updated."],
    )
    assert ambiguous.exit_code != 0
    assert "Missing argument" in ambiguous.output
    assert files_model.list_revisions(page_dir) == [1]

    selected = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(page_dir, "c2"),
            "--text",
            "Updated.",
        ],
    )

    assert selected.exit_code == 0, selected.output
    assert files_model.list_revisions(page_dir) == [1, 2]
    reply = events_model.read_events(page_dir)[-1]
    assert reply["parent"] == "c2"
    assert reply["responds"] == "c2"


def test_response_never_settles_a_newer_undelivered_correction(page_dir):
    delivered = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "make it blue"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [delivered],
            session=claim["id"],
            turn=claim["turn"],
        )
    reference = response_reference(page_dir, delivered)
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "r2",
            "author": "user",
            "parent": "c1",
            "text": "actually make it red",
        },
    )

    result = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", "--done", reference, "--text", "Made it blue."],
    )

    assert result.exit_code != 0
    assert "no longer requires a reply" in result.output
    assert not any(
        event["kind"] == "reply" and event["author"] == "agent"
        for event in events_model.read_events(page_dir)
    )


def test_response_belongs_to_the_session_with_the_opened_delivery(
    page_dir, monkeypatch
):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [comment],
            session=claim["id"],
            turn=claim["turn"],
        )
    reference = response_reference(page_dir, "c1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "different-reporter")
    service_model.claim_page(page_dir)

    result = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", "--done", reference, "--text", "Updated."],
    )

    assert result.exit_code != 0
    assert result.stderr.startswith("Error: ")
    assert "claim no longer matches its delivery" in result.stderr


def test_response_address_survives_its_delivery_turn_closing(page_dir):
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [comment],
            session=claim["id"],
            turn=claim["turn"],
        )
        cleanup_model.close_session_turn(claim["id"], claim["turn"])

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            "Updated.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["responds"] == comment["id"]


def test_a_cli_write_is_admitted_through_the_browser_door(page_dir):
    """One door, so a rule is stated once and holds for whoever appends.

    The `leaf` writers used to append with whatever contract each of them
    remembered: four with none at all, and the two that checked reaching two
    different homes. Nothing between them and the log read the event's own
    record schema, so a shape the browser door has always refused could still
    land — and stay, because `page init` re-reads every stored record before it
    will replace a layer, and refuses the re-vendor rather than the event.

    Each arm below is a writer that reaches the log by a different route: a reply
    whose gate is the record contract alone, and a report whose gate belongs to
    `event_contracts`. Both are refused in the writer's own voice.
    """
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "agent", "revision": 1, "text": "?"},
    )
    with pytest.raises(Refused) as refused:
        thread_model.post_reply(page_dir, {"to": "c1"}, "Answered.", attempt="r1")
    assert "'r1' does not match" in str(refused.value)

    with pytest.raises(Refused) as unknown_widget:
        thread_model.cmd_report(page_dir, "no-such-widget", "status", ())
    assert "unknown report widget 'no-such-widget'" in str(unknown_widget.value)

    assert [event["kind"] for event in events_model.read_events(page_dir)] == [
        "note",
        "comment",
    ]


def test_response_attempt_is_idempotent(page_dir):
    """An attempt is an opaque durable key, and the append door holds every
    writer to the record contract's shape for one — the delivery transports mint
    theirs from a digest, so a short hand-written label is not a retry key."""
    attempt = "retry-inferred-reply-1"
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    service_model.claim_page(page_dir)
    with service_model.PageTransaction(page_dir) as page:
        claim = page.active_claim
        delivery_model.record_pickup(
            page,
            [comment],
            session=claim["id"],
            turn=claim["turn"],
        )

    reference = response_reference(page_dir, comment)
    first = thread_model.post_response(reference, "Updated.", attempt=attempt)
    retried = thread_model.post_response(reference, "Updated.", attempt=attempt)

    assert retried["id"] == first["id"]
    assert (
        len(
            [
                event
                for event in events_model.read_events(page_dir)
                if event["kind"] == "reply"
            ]
        )
        == 1
    )


def test_reply_for_a_stale_event_reports_the_failed_fence(page_dir):
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "update it"},
    )
    reference = response_reference(page_dir, "c1")
    thread_model.post_response(reference, "Updated.")

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            reference,
            "--attempt",
            "distinct-retry-attempt",
            "--text",
            "Again.",
        ],
    )

    assert result.exit_code != 0
    assert "no longer requires a reply" in result.output


@pytest.mark.parametrize(
    "asset, expected",
    [
        (
            '<script type="module" src="/leaf.js"></script>',
            ("capture-failed", {"error": "public layer entry point"}),
        ),
        (
            '<link rel="stylesheet" href="/theme.css" media="print">',
            ("capture-failed", {"error": "escapes /page/ and /media/"}),
        ),
        (
            '<base href="https://outside.example/">',
            ("document-declaration", {"at": "<base>"}),
        ),
        (
            '<meta http-equiv="Content-Security-Policy" content="default-src none">',
            ("document-declaration", {"at": "<meta>"}),
        ),
        (
            '<script type="importmap">{"imports": {}}</script>',
            ("document-declaration", {"at": "<script>"}),
        ),
    ],
    ids=["runtime-module", "theme", "base", "policy", "import-map"],
)
def test_check_rejects_authored_delivery_assets(page_dir, asset, expected):
    """Capture refuses a delivery asset the page would load, for its own reason, and
    the markup check a declaration about the whole document."""
    (page_dir / "index.html").write_text(PAGE.replace("</head>", f"{asset}\n</head>"))

    status, findings = check_findings(page_dir)

    assert status == 1
    code, holds = expected
    [finding] = findings
    assert finding.code == code
    # A capture refusal is still its exception's words (`capture-failed`).
    if "error" in holds:
        assert holds["error"] in finding.values["error"]
    else:
        assert finding.at == holds["at"]


@pytest.mark.parametrize(
    "outside, refused",
    [
        ("Authored tail", "outside-main"),
        ('<p id="tail">Authored tail</p>', "outside-main"),
        (
            '<lf-options><lf-option id="tail">Authored tail</lf-option></lf-options>',
            "outside-main",
        ),
        ('<main><p id="tail">Second main</p></main>', "main-count"),
    ],
)
def test_check_confines_authored_content_to_one_direct_main(page_dir, outside, refused):
    """The element the presentation boundary withholds contains the whole page.

    Prose, ordinary elements, widgets, and another main beside the first are all
    visible outside the CSS gate and must be refused at the authoring door.
    """
    (page_dir / "index.html").write_text(PAGE.replace("</main>", f"</main>\n{outside}"))

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, refused)


def test_check_requires_main_to_be_a_direct_body_child(page_dir):
    """A main nested in an authored wrapper is not selected by `body > main`."""
    wrapped = PAGE.replace("<main>", "<div>\n<main>").replace(
        "</main>", "</main>\n</div>"
    )
    (page_dir / "index.html").write_text(wrapped)

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "main-count", direct=0)


def test_check_requires_an_explicit_head_for_delivery(page_dir):
    """Delivery has one validated insertion point for its generated head."""
    source = PAGE.replace("<head>", "").replace("</head>", "")
    (page_dir / "index.html").write_text(source)

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "head-count", tags=0)


def test_check_rejects_an_extra_head_that_html_recovery_ignores(page_dir):
    """The source contract counts tags the recovered browser tree discards."""
    source = PAGE.replace("</html>", "<head></head></html>")
    (page_dir / "index.html").write_text(source)

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "head-count", tags=2)


@pytest.mark.parametrize(
    "html",
    [
        PAGE.replace("</body>", '</body>\n<p id="tail">Authored tail</p>'),
        PAGE.replace("</head>", '<img src="/media/tail.png" alt="tail">\n</head>'),
    ],
)
def test_check_rejects_paintable_markup_the_browser_reparents(page_dir, html):
    """HTML recovery cannot move authored pixels around the main boundary."""
    (page_dir / "index.html").write_text(html)

    status, findings = check_findings(page_dir)

    assert status == 1
    assert found(findings, "outside-main")


def test_check_rejects_an_id_containing_whitespace(page_dir):
    """An id generated from a label (`f"layout-{label}"`) can carry a space. The browser
    still resolves it, so a comment anchors on it and nothing looks wrong until the id
    has a thread to move; the version has to be refused before it goes out."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            '<section id="plan">',
            '<section id="plan"><svg viewBox="0 0 10 10">'
            '<g id="layout-no class"><rect width="4" height="4"/></g></svg>',
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "spaced-ids", ids=["layout-no class"])


def test_any_id_names_one_subject_for_every_command(page_dir):
    """A page widget names itself, and a message, a widget frozen into one, or any
    other event a thread holds names that thread, for `page state`, `status --on`
    and the thread commands alike. Narrowed to a widget, the reading holds what
    stands inside it: the Ask carries the pick on its choice."""
    live = OPTIONS.format(a="", b="", chip="", shim="Keep the old API.", stage="Two.")
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + live)
    )
    publish(page_dir)
    pick = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
        },
    )
    runner = CliRunner()

    def run(*args):
        return runner.invoke(
            cli_model.cli, [args[0], args[1], str(page_dir), *args[2:]]
        )

    for name, widget in (
        ("g1-decision", "g1-decision"),
        ("g1", "g1"),
        (pick["id"], "g1"),
    ):
        narrowed = run("page", "state", name)
        assert narrowed.exit_code == 0, narrowed.output
        reading = json.loads(narrowed.output)
        assert reading["widget"]["id"] == widget
        assert [(r["widget"], r["action"]) for r in reading["state"]] == [
            ("g1", "choose")
        ]
    paged = run("page", "state", "g1", "--after", "1")
    assert paged.exit_code != 0
    assert "is a widget; --after and --limit page a thread" in paged.output

    [opened] = [
        json.loads(line)
        for line in run(
            "thread",
            "open",
            "--text",
            "Which store?",
            "--markup",
            '<lf-ask id="t-ask"><h3>Store?</h3><lf-options id="t-store" choose>'
            '<lf-option id="t-sqlite"><strong>sqlite</strong></lf-option>'
            "</lf-options></lf-ask>",
        ).output.splitlines()
    ]
    [renamed] = [
        json.loads(line)
        for line in run(
            "thread", "edit", "t-ask", "--title", "Store"
        ).output.splitlines()
    ]
    picked = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "t-store",
            "action": "choose",
            "detail": {"value": ["t-sqlite"]},
        },
    )
    undone = append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": picked["id"]}
    )
    for name in ("t-ask", opened["id"], renamed["id"], picked["id"], undone["id"]):
        read = run("page", "state", name)
        assert read.exit_code == 0, read.output
        assert json.loads(read.output)["thread"]["id"] == opened["id"]
    promised = run(
        "thread", "reply", "t-ask", "--text", "Weighing it.", "--todo", "Weigh"
    )
    assert promised.exit_code == 0, promised.output
    [task] = json.loads(run("page", "state").output)["todos"]
    assert (task["id"], task["subject"]) == (
        json.loads(promised.output)["id"],
        {"kind": "thread", "id": opened["id"]},
    )

    not_a_thread = run("thread", "resolve", "g1")
    assert not_a_thread.exit_code != 0
    assert "g1 is a widget on the page, not a thread" in not_a_thread.output
    [closed] = [
        json.loads(line)
        for line in run("thread", "resolve", "t-ask").output.splitlines()
    ]
    assert (closed["kind"], closed["parent"]) == ("resolve", opened["id"])

    # The log mints message ids in this shape, so a page may not author one.
    (page_dir / "index.html").write_text(
        PAGE.replace('id="flag-first"', 'id="20260927"')
    )
    refused = runner.invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert refused.exit_code != 0
    assert "ids shaped like the event ids the log mints" in refused.output


def test_report_validates_at_the_door_and_stamps_identity(page_dir, monkeypatch):
    """`leaf page report` is the report event's one door, so the widget,
    verb, and detail are held to the widget's agent verb there — the CLI mirror of the
    POST door's action gate — and the event leaves stamped with the posting
    session's voice and the exact revision the user is looking at."""
    _tasks_version(page_dir, "active")
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("<lf-options>", '<lf-options id="choice">')
    )
    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None and activation.revision == 1
    draft_report = _report(page_dir, "t-parser", "status", "value=review")
    assert draft_report.exit_code == 0, draft_report.output

    publish(page_dir)
    reports_before = len(
        [
            event
            for event in events_model.read_events(page_dir)
            if event["kind"] == "report"
        ]
    )
    for args, message in [
        (("nope", "status", "value=review"), "unknown report widget"),
        (("tree", "status", "value=review"), "does not declare report verb"),
        (("t-parser", "finish", "value=done"), "does not declare report verb"),
        (
            ("choice", "choose", "option=flag-first"),
            "'choose' is a verb the user writes; this report came from the agent",
        ),
        (("t-parser", "status", "value=shipping"), "detail is invalid"),
        (("t-parser", "status", "status"), "name=value"),
        (("t-parser", "status"), "'value' is a required property"),
    ]:
        refused = _report(page_dir, *args)
        assert refused.exit_code == 1, args
        assert message in refused.output, args
    assert (
        len(
            [
                event
                for event in events_model.read_events(page_dir)
                if event["kind"] == "report"
            ]
        )
        == reports_before
    )

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    sent = _report(page_dir, "t-parser", "status", "value=review")
    assert sent.exit_code == 0, sent.output
    event = events_model.read_events(page_dir)[-1]
    assert event["kind"] == "report" and event["author"] == "agent"
    assert (event["agent"], event["session"]) == ("Indexer", "worker-1")
    assert event["widget"] == "t-parser" and event["action"] == "status"
    assert event["detail"] == {"value": "review"} and event["revision"] == 1

    # A call prints the event it appended, whose coordinate is the one it moved.
    named = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(page_dir), "t-parser", "status", "value=done"],
    )
    assert named.exit_code == 0, named.output
    printed = json.loads(named.output)
    assert (printed["widget"], printed["action"]) == ("t-parser", "status")
    assert printed == events_model.read_events(page_dir)[-1]


def test_stamp_and_report_choose_one_log_order(page_dir, monkeypatch):
    """Report revisioning and stamp-note calculation are one transaction each."""
    _tasks_version(page_dir, "active")
    publish(page_dir)
    _tasks_version(page_dir, "review")
    at_commit = threading.Event()
    resume = threading.Event()
    original_append_record = service_model.PageTransaction._append_record

    def held_append_record(page, event):
        if event.get("kind") == "note" and event.get("version") == 2:
            at_commit.set()
            assert resume.wait(timeout=STATED_TIMEOUT), (
                "the report did not enter the publish gap"
            )
        return original_append_record(page, event)

    monkeypatch.setattr(
        service_model.PageTransaction, "_append_record", held_append_record
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        publishing = executor.submit(publishing_model.cmd_stamp, page_dir, "absorb")
        assert at_commit.wait(timeout=STATED_TIMEOUT), (
            "publish never reached its note commit"
        )
        serialized = leases_model.lock_is_held(page_dir / "events.jsonl")
        reporting = executor.submit(
            thread_model.cmd_report,
            page_dir,
            "t-parser",
            "status",
            ("value=review",),
        )
        # This branch only prevents the test harness from deadlocking in the
        # correct implementation: a transaction-holding publish must finish
        # before the report can derive its version; the current unlocked publish
        # lets the report finish first and exposes the inconsistent order.
        if serialized:
            resume.set()
            publishing.result(timeout=STATED_TIMEOUT)
            reporting.result(timeout=STATED_TIMEOUT)
        else:
            reporting.result(timeout=STATED_TIMEOUT)
            resume.set()
            publishing.result(timeout=STATED_TIMEOUT)

    events = events_model.read_events(page_dir)
    report = [event for event in events if event["kind"] == "report"][-1]
    note = [event for event in events if event["kind"] == "note"][-1]
    assert serialized, "publish calculated mutable log state outside its transaction"
    assert note["version"] == 2 and "settles" not in note
    assert report["revision"] == 2


def test_page_state_folds_the_log_onto_the_published_page(page_dir):
    """`page state` is /api/state folded for the agent: the banner's decision list,
    the standing state replay paints, as one queryable
    object — the position a session picking up a standing page would otherwise
    re-derive from the raw log."""
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    state = state_json(page_dir)
    assert state["versions"] == [
        {"version": 1, "revision": 1, "url": "/versions/v1.html"}
    ]
    assert state["active"]["revision"] == 1 and state["active"]["version"] == 1
    assert state["active"]["file"].startswith("revisions/r1-")
    assert state["source"] == {
        "file": "index.html",
        "live": True,
        "error": None,
    }
    assert state["data"] == {"file": "data.json", "dir": "data", "errors": []}
    assert state["event_seq"] == events_model.read_events(page_dir)[-1]["seq"]
    # The one asking group: PAGE's own bare <lf-options> takes no `choose`. The ask
    # names the region the user is sent to and the group that answers it.
    assert asks_on_user(state) == [
        {
            "id": "widget:g1",
            "tag": "lf-options",
            "widget": "g1",
            "widget_tag": "lf-options",
            "thread": None,
        }
    ]
    assert {"g1", "o-shim", "o-stage"} <= {el["id"] for el in state["elements"]}
    assert state["state"] == []

    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
        },
    )
    state = state_json(page_dir)
    assert asks_on_user(state) == []
    assert state["state"] == [
        {
            "widget": "g1",
            "unit": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
            "revision": 1,
            "seq": 2,
            # On every entry, and null for a page widget: the key names which of the
            # page's two documents the decision was made in, as each task's `thread`
            # does.
            "thread": None,
        }
    ]
    assert state["pending"] == 1 and state["unacked"] == 1

    # Completion is an independent fact on the same widget. It stands beside
    # selection instead of superseding it, and both are visible to the agent.
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "answer",
            "detail": {},
        },
    )
    assert [item["action"] for item in state_json(page_dir)["state"]] == [
        "answer",
        "choose",
    ]


def test_package_data_is_validated_replaced_and_indexed_in_page_state(page_dir):
    """One CLI boundary writes complete source values. A rejected replacement leaves
    the accepted revision untouched. `page state` identifies the canonical store and
    its freshness without copying arbitrary package values into the semantic index."""
    declare_data_input(
        page_dir,
        "deployments",
        {
            "type": "array",
            "items": {"type": "string"},
        },
        contract="deployment-rows",
    )
    runner = CliRunner()

    written = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "deployments"],
        input='["api", "worker"]',
    )

    assert written.exit_code == 0, written.output
    standing = state_json(page_dir)
    first = read_page_data(page_dir)
    stored = data_model.source_file(page_dir, "deployments")
    assert first["sources"]["deployments"] == {
        "contract": "deployment-rows",
        "revision": hashlib.sha256(
            cleanup_model.json_bytes(["api", "worker"])
        ).hexdigest()[:16],
        "run": json.loads(written.output)["run"],
        "updated": first["sources"]["deployments"]["updated"],
        "value": ["api", "worker"],
    }
    assert data_model.read_contracts(page_dir) == {"deployments": "deployment-rows"}
    assert standing["data"] == {"file": "data.json", "dir": "data", "errors": []}
    assert standing["data_bindings"] == {
        "deployments": {
            "contract": "deployment-rows",
            "consumers": [
                {
                    "widget": "test-data",
                    "input": "data",
                    "document": "revision r1",
                }
            ],
        }
    }

    for invalid in [{"api": "ready"}, None, True, [False]]:
        encoded = json.dumps(invalid)
        rejected = runner.invoke(
            cli_model.cli,
            ["data", "set", str(page_dir), "deployments"],
            input=encoded,
        )
        assert rejected.exit_code != 0
        assert rejected.output.startswith("Error: ")
        assert "source 'deployments' value is invalid" in rejected.output
        assert ("false" if isinstance(invalid, list) else encoded) in rejected.output
        assert read_page_data(page_dir) == first

    non_json = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "deployments"],
        input="NaN",
    )
    assert non_json.exit_code != 0
    assert "value is not JSON" in non_json.output
    assert read_page_data(page_dir) == first

    # Any process may rewrite the value file, so a reading judges what it finds.
    stored.write_text('{"api": "ready"}')
    [error] = state_json(page_dir)["data"]["errors"]
    assert "deployments" in error
    broken = read_page_data(page_dir)["sources"]["deployments"]
    assert broken["error"] == error and "value" not in broken

    cleared = runner.invoke(
        cli_model.cli, ["data", "clear", str(page_dir), "deployments"]
    )
    assert cleared.exit_code == 0, cleared.output
    assert not stored.exists()
    assert state_json(page_dir)["data"] == {
        "file": "data.json",
        "dir": "data",
        "errors": [],
    }
    assert read_page_data(page_dir)["sources"] == {
        "deployments": {"contract": "deployment-rows"}
    }

    unbound = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "package-guessed-name"],
        input="[]",
    )
    assert unbound.exit_code != 0
    assert (
        "not bound by the page source, a version, or a thread widget" in unbound.output
    )


def test_a_patch_piped_through_the_diff_script_sets_one_deferred_row_per_file(
    page_dir,
):
    """The diff package's producer script turns a Git patch into the contract's
    manifest on stdout, which `leaf data set` stores as it would any value."""
    declare_data_input(
        page_dir,
        "review-patch",
        {"type": "object"},
        contract="unified-diff",
    )
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def run():
-    return 1
+    return 2
diff --git a/old.py b/new.py
similarity index 78%
rename from old.py
rename to new.py
--- a/old.py
+++ b/new.py
@@ -1 +1 @@
-OLD = True
+NEW = True
diff --git a/docs/old.md b/docs/new.md
similarity index 100%
rename from docs/old.md
rename to docs/new.md
diff --git "a/caf\\303\\2512026 notes.py" "b/caf\\303\\2512026 notes.py"
--- "a/caf\\303\\2512026 notes.py"
+++ "b/caf\\303\\2512026 notes.py"
@@ -1 +1 @@
-OLD = True
+NEW = True
diff --git a/src/second file.py b/src/second file.py
--- a/src/second file.py\t
+++ b/src/second file.py\t
@@ -1 +1 @@
-OLD = True
+NEW = True
"""

    result = CliRunner().invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "review-patch"],
        input=json.dumps(patch_manifest(patch)),
    )

    assert result.exit_code == 0, result.output
    source = read_page_data(page_dir)["sources"]["review-patch"]
    assert [
        {key: value for key, value in file.items() if key != "patch"}
        for file in source["value"]["files"]
    ] == [
        {
            "path": "app.py",
            "operation": "modify",
            "hunkCount": 1,
            "binary": False,
            "additions": 1,
            "deletions": 1,
        },
        {
            "path": "new.py",
            "previousPath": "old.py",
            "operation": "rename",
            "hunkCount": 1,
            "binary": False,
            "additions": 1,
            "deletions": 1,
        },
        {
            "path": "docs/new.md",
            "previousPath": "docs/old.md",
            "operation": "rename",
            "hunkCount": 0,
            "binary": False,
            "additions": 0,
            "deletions": 0,
        },
        {
            "path": "café2026 notes.py",
            "operation": "modify",
            "hunkCount": 1,
            "binary": False,
            "additions": 1,
            "deletions": 1,
        },
        {
            "path": "src/second file.py",
            "operation": "modify",
            "hunkCount": 1,
            "binary": False,
            "additions": 1,
            "deletions": 1,
        },
    ]
    assert all(
        file["patch"].startswith("diff --git ") for file in source["value"]["files"]
    )


def test_native_git_file_operations_survive_capture_without_invented_hunks(
    page_dir, tmp_path
):
    """Git owns operation evidence, including copies it can detect from unchanged files."""
    repository = tmp_path / "native"
    repository.mkdir()

    def git(*arguments):
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    git("init", "-q")
    original = {
        "mode.sh": b"echo ready\n",
        "binary.dat": b"old\0blob\n",
        "deleted-empty": b"",
        "copy-source.txt": "".join(f"line {index}\n" for index in range(30)).encode(),
        "old name.txt": b"same text\n",
        "old-mode.txt": b"same mode\n",
        "changed-type": b"before\n",
        "same-type-content": b"target",
        "binary-type": b"old\0binary\n",
    }
    for name, content in original.items():
        (repository / name).write_bytes(content)
    (repository / "removed-link").symlink_to("old-target")
    git("add", ".")
    git(
        "-c",
        "user.name=Leaf test",
        "-c",
        "user.email=leaf@example.invalid",
        "commit",
        "-qm",
        "Original",
    )
    for name, target in [
        ("changed-type", "new-target"),
        ("same-type-content", "target"),
        ("binary-type", "binary-target"),
    ]:
        (repository / name).unlink()
        (repository / name).symlink_to(target)
    (repository / "removed-link").unlink()
    (repository / "removed-link").write_text("after\n")
    (repository / "mode.sh").chmod(0o755)
    (repository / "binary.dat").write_bytes(b"new\0blob\n")
    (repository / "deleted-empty").unlink()
    (repository / "added-empty").write_text("")
    (repository / "copy-pure.txt").write_bytes(original["copy-source.txt"])
    (repository / "copy-edited.txt").write_bytes(
        original["copy-source.txt"] + b"extra line\n"
    )
    (repository / "old name.txt").rename(repository / "new name.txt")
    (repository / "old-mode.txt").rename(repository / "new-mode.txt")
    (repository / "new-mode.txt").chmod(0o755)
    git("add", ".")
    patch = git("diff", "--cached", "-M", "-C", "--find-copies-harder")
    manifest = patch_manifest(patch)
    files = {file["path"]: file for file in manifest["files"]}
    assert files["copy-pure.txt"]["operation"] == "copy"
    assert files["copy-edited.txt"]["operation"] == "copy"
    assert files["copy-edited.txt"]["previousPath"] == "copy-source.txt"
    assert files["copy-edited.txt"]["hunkCount"] == 1
    assert files["copy-edited.txt"]["additions"] == 1
    assert files["new name.txt"]["operation"] == "rename"
    for path in ("mode.sh", "new-mode.txt"):
        assert files[path]["oldMode"] == "100644"
        assert files[path]["newMode"] == "100755"
    assert files["binary.dat"]["binary"] is True
    for path in ("changed-type", "same-type-content", "binary-type", "removed-link"):
        assert files[path]["operation"] == "modify"
        assert files[path]["hunkCount"] == 1
        assert files[path]["oldMode"] != files[path]["newMode"]
        assert files[path]["patch"].count("diff --git ") == 2
    assert (
        files["same-type-content"]["additions"]
        == files["same-type-content"]["deletions"]
        == 1
    )
    assert files["binary-type"]["binary"] is True
    opaque = patch_manifest(git("diff", "--cached", "--binary", "--", "binary-type"))[
        "files"
    ][0]
    assert opaque["binary"] and "literal " not in opaque["patch"]
    assert opaque["patch"].startswith("diff --git ")
    assert all(file["patch"].startswith("diff --git ") for file in files.values())
    binary = patch_manifest(git("diff", "--cached", "--binary", "--", "binary.dat"))
    assert [
        {key: value for key, value in file.items() if key != "patch"}
        for file in binary["files"]
    ] == [{key: value for key, value in files["binary.dat"].items() if key != "patch"}]
    assert "literal " not in binary["files"][0]["patch"]
    empty = patch_manifest(
        git("diff", "--cached", "--no-renames", "--", "added-empty", "deleted-empty")
    )
    assert [
        (file["operation"], file["hunkCount"], file["binary"])
        for file in empty["files"]
    ] == [
        ("add", 0, False),
        ("delete", 0, False),
    ]
    declare_data_input(
        page_dir, "native-patch", {"type": "object"}, contract="unified-diff"
    )
    for value in (manifest, empty, binary):
        data_model.cmd_data_set(page_dir, "native-patch", value)
        assert read_page_data(page_dir)["sources"]["native-patch"]["value"] == value


@pytest.mark.parametrize(
    "patch_text",
    [
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old
+GIT binary patch
""",
        """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
--- a/old.py
+++ b/new.py
-before
+after
""",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-before
+after
+lost
""",
        """diff --git a/app.py b/app.py
@@ -1 +1 @@
--- bogus-old
+++ bogus-new
""",
        """diff --git a/app.py b/app.py
--- a/other.py
+++ b/other.py
@@ -1 +1 @@
-before
+after
""",
        """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +3 @@
+partial
""",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-before
+after
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-before
+after
""",
    ],
)
def test_the_diff_script_preserves_evidence_for_the_widget_to_judge(patch_text):
    manifest = patch_manifest(patch_text)
    assert "".join(file["patch"] for file in manifest["files"]) == patch_text


DIFF_PATCH_CASES = json.loads(
    (Path(__file__).parents[1] / "diff_patch_cases.json").read_text()
)["cases"]


@pytest.mark.parametrize(
    "case",
    [case for case in DIFF_PATCH_CASES if "files" in case],
    ids=lambda case: case["id"],
)
def test_the_manifest_reads_the_diff_patch_table(case):
    """A patch lf-diff accepts has two readers in two languages: the widget parses a
    patch text in the browser, and `patch_manifest.py` builds the file manifest from a
    Git patch. Both read the paths of each `files` row of `diff_patch_cases.json`
    alike; `test_render_anchors.py` reads it for the widget, which alone refuses the
    rest."""
    files = patch_manifest(case["patch"])["files"]
    assert [file["path"] for file in files] == case["files"]


def test_data_set_reads_a_structured_value_from_a_file(page_dir, tmp_path):
    declare_data_input(page_dir, "builds", {"type": "object"}, contract="build-map")
    payload = tmp_path / "builds.json"
    payload.write_text('{"main":"passing"}')

    result = CliRunner().invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "builds", "--file", str(payload)],
    )

    assert result.exit_code == 0, result.output
    source = read_page_data(page_dir)["sources"]["builds"]
    # The printed run receipt is the one an author pins, so it is the stored one;
    # the value is the writer's own, so it does not come back.
    assert json.loads(result.output) == {
        "source": "builds",
        **{key: source[key] for key in ("contract", "revision", "run", "updated")},
    }
    assert source["value"] == {"main": "passing"}
    assert json.loads(data_model.source_file(page_dir, "builds").read_text())[
        "value"
    ] == {"main": "passing"}


def test_a_source_can_change_contract_without_an_immutable_document(page_dir):
    """The mutable-only bootstrap and a published page use the same write boundary."""
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
    data_model.cmd_data_set(page_dir, "project-feed", [])
    data_model.cmd_data_clear(page_dir, "project-feed")
    for revision in files_model.list_revisions(page_dir):
        files_model.revision_path(page_dir, revision).unlink()

    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$data"]["contracts"]["other-rows"] = {
        "description": "Another meaning.",
        "schema": {"type": "array"},
    }
    registry["lf-test-data"]["x-data"]["data"]["contract"] = "other-rows"
    registry_path.write_text(json.dumps(registry))

    data_model.cmd_data_set(page_dir, "project-feed", [])
    assert data_model.read_contracts(page_dir) == {"project-feed": "other-rows"}
    assert data_model.source_file(page_dir, "project-feed").exists()


def test_a_source_bound_only_by_frozen_reply_markup_can_be_set(page_dir):
    """A widget sent by an agent is still a data consumer. Its binding enters the
    page-lifetime index even though no authored version contains its seat."""
    declare_data_input(
        page_dir, "reply-feed", {"type": "array"}, contract="rows", activate=False
    )
    version = page_dir / "index.html"
    version.write_text(
        re.sub(r"<lf-test-data[^>]*></lf-test-data>\n?", "", version.read_text())
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "data-question",
            "author": "user",
            "revision": 1,
            "text": "Show the feed here.",
        },
    )
    reply = thread_model.post_reply(
        page_dir,
        {"to": "data-question", "for": "data-question"},
        "Here it is.",
        '<lf-test-data id="reply-data" source="reply-feed"></lf-test-data>',
    )
    assert reply["revision"] == 1

    data_model.cmd_data_set(page_dir, "reply-feed", [])
    standing = state_json(page_dir)
    assert standing["data"] == {"file": "data.json", "dir": "data", "errors": []}
    reading = read_page_data(page_dir)["sources"]["reply-feed"]
    assert (reading["contract"], reading["value"]) == ("rows", [])
    assert standing["data_bindings"]["reply-feed"]["consumers"] == [
        {
            "widget": "reply-data",
            "input": "data",
            "document": f"event {reply['id']!r} markup",
        }
    ]


def test_thread_markup_can_use_a_different_binding_from_a_page_source(page_dir):
    """A later frozen thread does not redirect the active page's producer contract.
    Its incompatible reading cannot become the page's valid payload.
    """
    declare_data_input(
        page_dir, "project-feed", {"type": "array"}, contract="rows", activate=False
    )
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$data"]["contracts"]["other-rows"] = {
        "description": "Another meaning.",
        "schema": {"type": "object"},
    }
    registry["lf-other-data"] = {
        **registry["lf-test-data"],
        "description": "A differently typed test input.",
        "x-data": {"data": {"contract": "other-rows", "source": "source"}},
    }
    registry_path.write_text(json.dumps(registry))
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "data-question",
            "author": "user",
            "revision": 1,
            "text": "Show another feed here.",
        },
    )

    reply = thread_model.post_reply(
        page_dir,
        {"to": "data-question", "for": "data-question"},
        "Here it is.",
        '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>',
    )

    assert (
        reply["markup"]
        == '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>'
    )

    binding = state_json(page_dir)["data_bindings"]["project-feed"]
    assert binding == {
        "contract": "rows",
        "consumers": [
            {"widget": "test-data", "input": "data", "document": "revision r1"}
        ],
    }
    data_model.cmd_data_set(page_dir, "project-feed", ["active page"])
    assert data_model.read_contracts(page_dir)["project-feed"] == "rows"
    active = read_page_data(page_dir)["sources"]["project-feed"]
    assert active["contract"] == "rows" and active["value"] == ["active page"]
    captured = artifact_model.read_revision(page_dir, reply["revision"]).registry
    thread_bindings, errors = data_contracts_model.declared_data_bindings(
        structure_model.SourceDocument(reply["markup"]).lf_elements, captured
    )
    assert errors == [] and thread_bindings == {"project-feed": "other-rows"}
    frozen = data_model.read_source(
        page_dir, "project-feed", thread_bindings["project-feed"], captured
    )
    assert "error" in frozen and "value" not in frozen
    with pytest.raises(data_model.DataError, match="value is invalid"):
        data_model.cmd_data_set(page_dir, "project-feed", {"thread": "wrong producer"})
    assert read_page_data(page_dir)["sources"]["project-feed"] == active


def test_thread_markup_can_use_a_different_binding_from_a_draft_only_page_source(
    page_dir,
):
    """Independent documents retain their own binding declarations."""
    declare_data_input(
        page_dir, "project-feed", {"type": "array"}, contract="rows", activate=False
    )
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$data"]["contracts"]["other-rows"] = {
        "description": "Another meaning.",
        "schema": {"type": "array"},
    }
    registry["lf-other-data"] = {
        **registry["lf-test-data"],
        "description": "A differently typed test input.",
        "x-data": {"data": {"contract": "other-rows", "source": "source"}},
    }
    registry_path.write_text(json.dumps(registry))
    source = page_dir / "index.html"
    draft = source.read_text()
    source.write_text(
        draft.replace(
            '<lf-test-data id="test-data" source="project-feed"></lf-test-data>\n', ""
        )
    )
    activation = revisioning_model.activate_source(page_dir)
    assert activation.error is None
    source.write_text(draft)
    documents = data_contracts_model.page_data_document_readings(
        page_dir, events_model.read_events(page_dir), registry
    )
    immutable, errors = data_contracts_model.merge_data_document_readings(documents)
    assert errors == [] and "project-feed" not in immutable
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "draft-data-question",
            "author": "user",
            "revision": 1,
            "text": "Show another feed here.",
        },
    )

    thread_model.post_reply(
        page_dir,
        {"to": "draft-data-question", "for": "draft-data-question"},
        "Here it is.",
        '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>',
    )


def test_data_set_validates_the_json_value_it_writes(page_dir):
    """The Python facade and CLI share one boundary. A caller may hand the facade a
    mapping key that json.dumps coerces, but the schema must judge the resulting JSON,
    not a Python-only shape that can never reach the browser."""
    declare_data_input(
        page_dir,
        "builds",
        {
            "type": "object",
            "propertyNames": {"pattern": "^[a-z]+$"},
        },
        contract="build-map",
    )

    with pytest.raises(data_contracts_model.DataError, match="value is invalid"):
        data_model.cmd_data_set(page_dir, "builds", {1: "passing"})

    assert read_page_data(page_dir)["sources"] == {}


def test_data_set_wraps_an_unproductive_recursive_schema(page_dir):
    """Recursive schemas can describe trees, but a reference cycle that never moves
    into a child instance cannot answer for any value. It is a package-contract error,
    not a recursion failure the producer or re-vendor should have to catch."""
    declare_data_input(
        page_dir,
        "loop",
        {
            "$id": "https://example.invalid/loop",
            "$ref": "https://example.invalid/loop",
        },
        contract="loop",
    )
    with pytest.raises(
        data_contracts_model.DataError, match="recursive reference did not terminate"
    ):
        data_model.cmd_data_set(page_dir, "loop", {})

    # A value another process wrote is judged on reading by the same validator.
    (page_dir / "data.json").write_text('{"sources":{"loop":{"contract":"loop"}}}')
    (page_dir / "data").mkdir(exist_ok=True)
    data_model.source_file(page_dir, "loop").write_text(
        json.dumps(
            {
                "run": "1" * 32,
                "updated": "2026-01-01T00:00:00Z",
                "value": {},
            }
        )
    )
    assert read_page_data(page_dir)["sources"]["loop"]["error"] == (
        "source 'loop' contract 'loop' could not validate its value: "
        "a recursive reference did not terminate"
    )


def test_a_value_an_earlier_leaf_wrote_reads_as_that_sources_error(page_dir):
    """A Leaf before publications wrote the bare value, so a page it fed names the
    rewrite rather than reading that value as a publication."""
    declare_data_input(page_dir, "builds", {"type": "array"}, contract="build-map")
    data_model.cmd_data_set(page_dir, "builds", [])
    data_model.source_file(page_dir, "builds").write_bytes(b"[]")

    source = read_page_data(page_dir)["sources"]["builds"]
    assert "value" not in source
    assert source["error"] == (
        "source 'builds' holds no publication; write it again with leaf data set"
    )


def test_page_state_names_the_ask_region_but_keeps_state_on_its_request(page_dir):
    """A Question retains its source identity under an authored context wrapper.
    The nested widget remains the canonical answer owner."""
    opts = """<lf-options id="g1" choose>
      <lf-option id="o-shim"><strong>Shim it</strong> Fastest to ship.</lf-option>
      <lf-option id="o-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
    </lf-options>"""
    ask = (
        '<lf-ask id="plan-decision"><h2>Plan</h2>'
        "<p>Choose after reading this framing.</p>"
        f"{opts}</lf-ask>"
    )
    (page_dir / "index.html").write_text(PAGE.replace("<h2>Plan</h2>", ask))
    publish(page_dir)

    state = state_json(page_dir)
    assert asks_on_user(state) == [
        {
            "id": "widget:g1",
            "tag": "lf-options",
            "widget": "g1",
            "widget_tag": "lf-options",
            "thread": None,
        },
    ]

    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
        },
    )
    state = state_json(page_dir)
    assert asks_on_user(state) == []
    assert state["state"][0]["widget"] == "g1"


def test_page_state_reads_an_authored_answer_with_no_log(page_dir):
    """A version that honors a pick in its markup reads as answered with no log
    at all — the shipped examples arrive that way."""
    opts = OPTIONS.format(a=" chosen", b="", chip="", shim="s.", stage="t.")
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    assert asks_on_user(state_json(page_dir)) == []


def test_page_state_keeps_thread_history_out_of_its_current_reading(page_dir):
    """State stays flat as a thread grows; the exact-id event lookup owns its
    history while the append-only log remains the one copy of its prose."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    opened = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "cameras are flaky",
            "anchor": {"section": "s-1", "quote": "Ship dark"},
        },
    )
    answered = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Indexer",
            "parent": opened["id"],
            "text": "two of them share a power rail",
        },
    )

    assert state_json(page_dir)["threads"] == [
        {
            "id": opened["id"],
            "anchor": {"section": "s-1", "quote": "Ship dark"},
            "title": None,
            "detached_from": None,
            "resolved": None,
            "unread": [answered["id"]],
            # The reply names no `responds`, so the comment is still owed an answer.
            "attention": {
                "kind": "waiting",
                "reason": "workflow",
                "workflow": opened["id"],
            },
        }
    ]
    history = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), opened["id"]]
    )
    assert history.exit_code == 0, history.output
    assert [m["message"] for m in json.loads(history.output)["content"]] == [
        opened["id"],
        answered["id"],
    ]
    opening_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == opened["id"]
    )
    continued = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "state",
            str(page_dir),
            opened["id"],
            "--after",
            str(opening_seq),
        ],
    )
    assert continued.exit_code == 0, continued.output
    assert [m["message"] for m in json.loads(continued.output)["content"]] == [
        answered["id"]
    ]
    unknown = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), "not-a-thread"]
    )
    assert unknown.exit_code != 0
    assert "'not-a-thread' names no thread or widget" in unknown.output


def test_a_reader_that_closes_the_pipe_ends_page_events_quietly(page_dir):
    """`page events | head` is an ordinary way to stop reading, so the command exits
    0 and prints nothing past what the reader took. The log outgrows a pipe's buffer,
    or the write that finds the reader gone never happens."""
    record = {"kind": "comment", "author": "user", "text": "x" * 200}
    (page_dir / cleanup_model.EVENTS_FILE).write_text(
        "".join(json.dumps({**record, "id": f"e{n}"}) + "\n" for n in range(2000))
    )
    for follow in ([], ["--follow"]):
        piped = subprocess.run(
            " ".join(
                [
                    *map(shlex.quote, [*LEAF_COMMAND, "page", "events", str(page_dir)]),
                    *follow,
                    "| head -1",
                ]
            ),
            shell=True,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=True,
        )
        assert json.loads(piped.stdout)["seq"] == 1
        assert piped.stderr == ""


class Follower:
    """`leaf page events --follow` in its own process, its lines read as they arrive."""

    def __init__(self, spawn, page_dir, *args):
        self.process = spawn(
            [*LEAF_COMMAND, "page", "events", str(page_dir), "--follow", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.lines = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)

    def next(self) -> dict:
        return json.loads(self.lines.get(timeout=STATED_TIMEOUT))

    def stop(self, signum):
        self.process.send_signal(signum)
        _, stderr = self.process.communicate(timeout=STATED_TIMEOUT)
        return self.process.returncode, stderr


def test_events_follow_prints_each_admitted_event_as_it_lands(page_dir, spawn):
    """Another process follows the log: the stored records already there, then each
    one another writer admits through the append door, `meaning` included, one line
    each and each as it lands. A stop from its consumer is the ordinary end."""
    _tasks_version(page_dir, "active")
    publish(page_dir)
    follower = Follower(spawn, page_dir)
    standing = events_model.read_events(page_dir)
    assert [follower.next() for _ in standing] == standing

    reported = _report(page_dir, "t-parser", "status", "value=review")
    assert reported.exit_code == 0, reported.output
    opened = comment(page_dir, "--text", "Is review the right stage?")
    assert opened.exit_code == 0, opened.output

    followed = [follower.next(), follower.next()]
    assert followed == events_model.read_events(page_dir)[len(standing) :]
    assert followed[0]["id"] == json.loads(reported.output)["id"]
    assert followed[0]["meaning"]["unit"] == "t-parser"
    assert followed[1]["id"] == json.loads(opened.output)["id"]
    assert follower.stop(signal.SIGTERM) == (0, "")


def test_events_follow_resumes_after_the_last_seq_its_reader_saw(page_dir, spawn):
    """`seq` is the cursor: a follower restarted with `--after` the last seq it
    printed starts at the next event, whether that was admitted while it was away
    or after it came back."""
    _tasks_version(page_dir, "active")
    publish(page_dir)
    seen = events_model.read_events(page_dir)[-1]["seq"]
    missed = comment(page_dir, "--text", "Written while nobody followed.")
    assert missed.exit_code == 0, missed.output

    follower = Follower(spawn, page_dir, "--after", str(seen))
    assert follower.next()["id"] == json.loads(missed.output)["id"]
    later = comment(page_dir, "--text", "Written after the follower came back.")
    assert later.exit_code == 0, later.output
    resumed = follower.next()
    assert resumed["id"] == json.loads(later.output)["id"]
    assert resumed["seq"] == seen + 2
    assert follower.stop(signal.SIGINT) == (0, "")


def test_events_follow_ends_when_its_log_is_replaced(page_dir, spawn):
    """A follower's position is an offset into the file it opened. A log renamed
    into its place is another file, whose same offset is the middle of a different
    history under the wrong seqs, so the follower ends with the error a removed
    log gets rather than stalling or printing from there."""
    _tasks_version(page_dir, "active")
    publish(page_dir)
    follower = Follower(spawn, page_dir)
    for _ in events_model.read_events(page_dir):
        follower.next()

    log = page_dir / "events.jsonl"
    replacement = page_dir / "events.jsonl.new"
    replacement.write_bytes(log.read_bytes() + log.read_bytes())
    os.replace(replacement, log)

    follower.process.wait(timeout=STATED_TIMEOUT)
    assert follower.stop(signal.SIGTERM) == (1, f"Error: {log} is gone\n")


def test_page_state_points_to_a_users_suggestion_record(page_dir):
    """`suggestion: true` is the user proposing exact replacement words rather
    than describing a change, and the loop owes that a different answer — taken
    verbatim, or declined with a reason. State supplies the semantic membership and
    `events` supplies that raw flag without maintaining a second message shape."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    suggestion = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Ship dark behind the importer flag.",
            "anchor": {"section": "plan", "quote": "Ship dark"},
            "suggestion": True,
        },
    )

    [thread] = state_json(page_dir)["threads"]
    history = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), thread["id"]]
    )
    assert history.exit_code == 0, history.output
    assert [m["message"] for m in json.loads(history.output)["content"]] == [
        suggestion["id"]
    ]
    [record] = [
        event
        for event in events_model.read_events(page_dir)
        if event["id"] == suggestion["id"]
    ]
    assert record["suggestion"] is True


def test_page_state_holds_a_thread_ask_open_until_its_verb(page_dir):
    """A widget in thread markup presents an Ask like one on the page; `until` holds a
    `multiple` group open across picks, and only the named verb closes it."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which mitigations?",
            "markup": '<lf-ask id="gm-decision"><h2>Which mitigations?</h2>'
            '<lf-options id="gm" choose multiple>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            '<lf-option id="m-alert"><strong>Alert</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    assert asks_on_user(state_json(page_dir)) == [
        {
            "id": "widget:gm",
            "tag": "lf-options",
            "widget": "gm",
            "widget_tag": "lf-options",
            "thread": root["id"],
        },
    ]
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"value": ["m-cap"]},
        },
    )
    assert asks_on_user(state_json(page_dir)) == [
        {
            "id": "widget:gm",
            "tag": "lf-options",
            "widget": "gm",
            "widget_tag": "lf-options",
            "thread": root["id"],
        },
    ]
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "answer",
            "detail": {},
        },
    )
    assert asks_on_user(state_json(page_dir)) == []


def test_tasks_roll_up_explicit_requests_without_asking_themselves(page_dir):
    tasks = """<lf-test-tasks id="work">
      <lf-test-task id="vendor" status="blocked"><strong>Vendor fix</strong></lf-test-task>
      <lf-test-task id="copy" status="review"><strong>Copy review</strong></lf-test-task>
      <lf-test-task id="future" status="active"><strong>Future review</strong>
        <lf-ask id="future-decision"><h3>Review it now?</h3>
          <lf-options id="future-review" choose>
            <lf-option id="future-yes">Yes</lf-option><lf-option id="future-no">No</lf-option>
          </lf-options>
        </lf-ask>
      </lf-test-task>
      <lf-test-task id="decision" status="blocked"><strong>User decision</strong>
        <lf-ask id="decision-decision"><h3>Which way out?</h3>
          <lf-options id="decision-options" choose>
            <lf-option id="decision-a">A</lf-option><lf-option id="decision-b">B</lf-option>
          </lf-options>
        </lf-ask>
      </lf-test-task>
      <lf-test-task id="release" status="review"><strong>Release review</strong>
        <lf-test-task id="release-build" status="done"><strong>Build release</strong></lf-test-task>
      </lf-test-task>
    </lf-test-tasks>"""
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)

    assert asks_on_user(state_json(page_dir)) == [
        {
            "id": "widget:future-review",
            "tag": "lf-options",
            "widget": "future-review",
            "widget_tag": "lf-options",
            "thread": None,
        },
        {
            "id": "widget:decision-options",
            "tag": "lf-options",
            "widget": "decision-options",
            "widget_tag": "lf-options",
            "thread": None,
        },
    ]


def test_page_state_carries_a_report_until_a_version_answers_it(page_dir):
    """An unsettled report changes task status without creating user work, appears
    in the canonical report feed, and remains there as settled history when a note
    absorbs it."""
    tasks = (
        '<lf-test-tasks id="work"><lf-test-task id="t-parser" status="review">'
        "<strong>Parser</strong> Ready for eyes.</lf-test-task></lf-test-tasks>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)
    assert asks_on_user(state_json(page_dir)) == []
    rep = append_command(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "agent": "worker",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"value": "done"},
        },
    )
    state = state_json(page_dir)
    assert asks_on_user(state) == []
    assert state["reports"] == [
        {
            "id": rep["id"],
            "target": {"kind": "widget", "id": "t-parser"},
            "source": "report",
            "action": "status",
            "detail": {"value": "done"},
            "text": None,
            "ts": rep["ts"],
            "revision": 1,
            "seq": 2,
            "agent": "worker",
            "session": None,
            "disposition": "effective",
        }
    ]
    # The absorbing version writes the status and its note names the report.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", "<h2>Plan</h2>" + tasks.replace('"review"', '"done"')
        )
    )
    write_revision(
        page_dir,
        2,
        (page_dir / "index.html").read_bytes(),
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "absorbed",
            "settles": [{"kind": "report", "id": rep["id"]}],
        },
    )
    state = state_json(page_dir)
    assert state["reports"] == [
        {
            "id": rep["id"],
            "target": {"kind": "widget", "id": "t-parser"},
            "source": "report",
            "action": "status",
            "detail": {"value": "done"},
            "text": None,
            "ts": rep["ts"],
            "revision": 1,
            "seq": 2,
            "agent": "worker",
            "session": None,
            "disposition": "settled",
        }
    ]
    assert asks_on_user(state) == []


def test_report_feed_orders_clock_ties_by_log_causality(page_dir, monkeypatch):
    """Reports are ordered by the log, so equal second-precision timestamps cannot
    reverse their known causal order."""
    task = (
        '<lf-test-tasks id="work"><lf-test-task id="t-parser" status="review">'
        "<strong>Parser</strong></lf-test-task></lf-test-tasks>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + task)
    )
    publish(page_dir)
    tied = "2026-08-24T12:00:00-07:00"
    monkeypatch.setattr(events_model, "now_iso", lambda: tied)
    first = append_command(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"value": "done"},
        },
    )
    second = append_command(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"value": "done"},
        },
    )

    reports = state_json(page_dir)["reports"]
    assert [(report["source"], report["id"]) for report in reports] == [
        ("report", first["id"]),
        ("report", second["id"]),
    ]


def test_page_state_before_first_stamp(page_dir):
    """An unstamped draft is still the live reading and has no public version."""
    state = state_json(page_dir)
    assert state["versions"] == []
    assert state["active"]["revision"] == 1
    assert state["active"]["version"] is None
    assert state["active"]["label"] == "Draft"
    assert state["elements"] and asks_on_user(state) == []
    assert state["title"] == "t"


def test_a_quoted_ask_does_not_hide_a_real_request_in_the_same_goal(page_dir):
    markup = (
        '<lf-test-plan id="hub">'
        '<lf-test-task id="goal" status="blocked"><strong>Blocked goal</strong>'
        '<lf-sample id="sample"><lf-options id="example" choose>'
        '<lf-option id="example-a"><strong>Example only</strong></lf-option>'
        "</lf-options></lf-sample>"
        '<lf-ask id="real-decision"><h3>What next?</h3>'
        '<lf-options id="real" choose><lf-option id="real-a">A</lf-option>'
        '<lf-option id="real-b">B</lf-option></lf-options></lf-ask>'
        "</lf-test-task></lf-test-plan>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</section>", markup + "</section>")
    )
    publish(page_dir)
    assert asks_on_user(state_json(page_dir)) == [
        {
            "id": "widget:real",
            "tag": "lf-options",
            "widget": "real",
            "widget_tag": "lf-options",
            "thread": None,
        },
    ]


def test_page_state_and_browser_share_a_conditional_edit_decision(page_dir):
    """A draft uses the ordinary x-awaits fold: its edit discharges the decision,
    and an honoring version can clear the authored condition without reviving it."""

    def command(status, needed, body):
        flag = " needed" if needed else ""
        return (
            '<lf-test-plan id="hub">'
            f'<lf-test-task id="goal" status="{status}"><strong>Import</strong>'
            f'<lf-draft id="cargo"{flag}><pre>\n{body}\n</pre></lf-draft>'
            "</lf-test-task></lf-test-plan>"
        )

    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace("</section>", command("active", True, "paste") + "</section>")
    )
    publish(page_dir)
    assert asks_on_user(state_json(page_dir)) == [
        {
            "id": "widget:cargo",
            "tag": "lf-draft",
            "widget": "cargo",
            "widget_tag": "lf-draft",
            "thread": None,
        },
    ]

    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "cargo",
            "action": "edit",
            "detail": {"value": "ledger_id,amount\n7,42"},
        },
    )
    assert asks_on_user(state_json(page_dir)) == []

    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            command("active", False, "ledger_id,amount\n7,42") + "</section>",
        )
    )
    publish(page_dir)
    assert asks_on_user(state_json(page_dir)) == []


# The colour-vision maths the series palette is stepped against, written out here because
# nothing else in the payload needs it. Machado, Oliveira & Fernandes (2009) at severity
# 1.0 in linear sRGB, and OKLab for the distance — the pair the field uses, so the numbers
# below are the ones a reader of the literature would expect.
_CVD = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
}


def _linear(hex_colour):
    raw = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in raw]


def _oklab(rgb):
    r, g, b = rgb
    lms_l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * lms_l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * lms_l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * lms_l + 0.7827717662 * m - 0.8086757660 * s,
    )


def _contrast(a, b):
    def luminance(colour):
        r, g, bl = _linear(colour)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _apart(a, b, vision=None):
    def seen(colour):
        rgb = _linear(colour)
        if vision is None:
            return _oklab(rgb)
        return _oklab([sum(w * c for w, c in zip(row, rgb)) for row in _CVD[vision]])

    return math.dist(seen(a), seen(b)) * 100


def _palette(theme, half):
    """The series steps and the paper they sit on: `half` 0 or 1 of each `light-dark()`."""
    pair = r"light-dark\(\s*(#[0-9a-f]{6})\s*,\s*(#[0-9a-f]{6})\s*\)"
    steps = {
        number: colours[half]
        for number, *colours in re.findall(rf"--series-(\d+):\s*{pair}", theme)
    }
    paper = re.search(rf"--paper:\s*{pair}", theme)[half + 1]
    assert steps, "no series tokens in the theme"
    return [steps[str(n)] for n in range(1, len(steps) + 1)], paper


def test_the_series_palette_clears_the_floors_it_claims_to():
    """The theme's comment beside these tokens tells the next editor to check them rather
    than look at them, and until this test there was nothing to check them with — the
    syntax roles have UNREAD_SYNTAX in the render gate and the series steps had the
    honour system. What made the argument was the first attempt at the line, chosen by
    eye: its blue and its plum came out 0.3 apart under simulated deuteranopia, which is
    one colour to a user who has no way to tell us.

    Every pair rather than the neighbours, because a stacked bar puts any two of them
    edge to edge, and both palettes, because the dark steps are stepped against a
    brown-black rather than lightened from the light ones. The registry's $series.steps
    is counted against the tokens in the same breath: it is how many series an author is
    told a chart can colour apart, and a palette one step longer than the number it
    publishes would hold a colour nobody is told to use."""
    theme = (schema_model.ASSETS / "theme.css").read_text()
    declared = json.loads((schema_model.ASSETS / "registry.json").read_text())[
        "$series"
    ]["steps"]

    for scheme, half in (("light", 0), ("dark", 1)):
        steps, paper = _palette(theme, half)
        assert len(steps) == declared, (
            f"{scheme} paints {len(steps)} series and $series.steps says {declared}"
        )
        faint = [c for c in steps if _contrast(c, paper) < 3.0]
        assert not faint, f"{scheme}: {faint} under 3:1 against {paper}"
        pairs = [(a, b) for i, a in enumerate(steps) for b in steps[i + 1 :]]
        blind = min(
            (min(_apart(a, b, "protan"), _apart(a, b, "deutan")), a, b)
            for a, b in pairs
        )
        assert blind[0] >= 8.0, (
            f"{scheme}: {blind[1]} and {blind[2]} are {blind[0]:.1f} apart to a dichromat"
        )
        seen = min((_apart(a, b), a, b) for a, b in pairs)
        assert seen[0] >= 15.0, (
            f"{scheme}: {seen[1]} and {seen[2]} are {seen[0]:.1f} apart"
        )


def test_page_inspection_places_cards_among_identified_siblings(page_dir):
    """A layer can add idless column content without changing card indexes."""
    registry_file = page_dir / "registry.json"
    registry = json.loads(registry_file.read_text())
    registry["lf-label"] = {
        "description": "An inline label.",
        "type": "object",
        "properties": {},
        "x-content": "markup",
        "x-upgrade": False,
        "x-owners": ["lf-column"],
    }
    registry_file.write_text(json.dumps(registry))
    board = (
        '<lf-board id="reading-board">'
        '<lf-column id="reading-todo" label="To do">'
        '<lf-card id="reading-a">A</lf-card></lf-column>'
        '<lf-column id="reading-done" label="Done">'
        "<lf-label>Already reviewed</lf-label>"
        '<lf-card id="reading-b">B</lf-card></lf-column></lf-board>'
    )
    (page_dir / "index.html").write_text(before_choice(PAGE, board))
    initial = state_json(page_dir)
    assert initial["source"]["live"], initial["source"]["error"]
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": initial["active"]["revision"],
            "widget": "reading-board",
            "action": "move",
            "detail": {"unit": "reading-a", "value": "reading-done", "rank": "0i"},
        },
    )
    assert folded(page_dir, "reading-board")["reading-done"] == [
        "reading-a",
        "reading-b",
    ]


def test_page_inspection_fragments_only_the_manifest_branch_of_a_data_contract(
    page_dir,
):
    """A declared split does not turn the contract's inline text into a manifest."""
    (page_dir / "index.html").write_text(
        before_choice(
            PAGE,
            '<lf-diff id="reading-diff" source="reading-patch"><pre></pre></lf-diff>',
        )
    )
    initial = state_json(page_dir)
    assert initial["source"]["live"], initial["source"]["error"]
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-before\n+after\n"
    file = {
        "path": "a.py",
        "operation": "modify",
        "hunkCount": 1,
        "binary": False,
        "additions": 1,
        "deletions": 1,
        "patch": patch,
    }
    manifest = {"files": [file]}
    for value in (patch, manifest, patch):
        written = CliRunner().invoke(
            cli_model.cli,
            ["data", "set", str(page_dir), "reading-patch"],
            input=json.dumps(value),
        )
        assert written.exit_code == 0, written.output
        stored = read_page_data(page_dir)
        delivered = data_model.browser_data_from(stored, require_registry(page_dir))
        reading = delivered["sources"]["reading-patch"]
        if isinstance(value, str):
            assert reading["value"] == patch
        else:
            assert reading["value"] == {
                "files": [{key: field for key, field in file.items() if key != "patch"}]
            }
        assert stored["sources"]["reading-patch"]["value"] == value


@pytest.mark.parametrize(
    ("files", "refusal"),
    [
        ([], "does not satisfy minItems: 1"),
        (
            [{"path": "b.py", "operation": "rename", "additions": 0, "deletions": 0}],
            "'previousPath' is a required property",
        ),
        (
            [{"path": "a.py", "operation": "modify", "additions": 1, "deletions": 1}]
            * 2,
            "record keys must be unique",
        ),
    ],
)
def test_data_set_refuses_a_diff_manifest_the_widget_cannot_list(
    page_dir, files, refusal
):
    """A diff manifest lists each file once, by its path, and a rename names the path
    it came from, so the widget renders what `data set` accepted."""
    (page_dir / "index.html").write_text(
        before_choice(
            PAGE,
            '<lf-diff id="reading-diff" source="reading-patch"><pre></pre></lf-diff>',
        )
    )
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-before\n+after\n"
    written = CliRunner().invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "reading-patch"],
        input=json.dumps(
            {
                "files": [
                    {**file, "hunkCount": 1, "binary": False, "patch": patch}
                    for file in files
                ]
            }
        ),
    )
    assert written.exit_code == 1
    assert refusal in written.output


def test_a_state_read_walks_an_unchanged_revision_once(page_dir, monkeypatch):
    """A revision is immutable, so what its words say is read once while its page
    is held.

    Every state read folds the log against the active revision's words, and
    walking a large page for them was most of what a read cost. The first read
    after the revision is taken up is the control: it walks, so a counter that
    never saw a walk cannot pass the second assertion on its own."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    walks = []
    native = passages_model.page_passages

    def counted(*args, **kwargs):
        walks.append(args)
        return native(*args, **kwargs)

    monkeypatch.setattr(passages_model, "page_passages", counted)
    with fresh_process():
        read_served_page(read_page(page_dir, events_model.read_events(page_dir)))
        assert walks
        walks.clear()
        read_served_page(read_page(page_dir, events_model.read_events(page_dir)))
    assert walks == []


def test_a_crlf_source_rechecked_unchanged_is_the_active_revision(page_dir):
    """A revision's document carries the exact bytes it captured, line endings
    included, so a CRLF source checked again unchanged is the active revision and
    no transition is judged for it."""
    (page_dir / "index.html").write_bytes(PAGE.replace("\n", "\r\n").encode())
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    events = events_model.read_events(page_dir)
    with fresh_process():
        checked = check_source(page_dir, events)
        data = (page_dir / "index.html").read_bytes()
        assert b"\r\n" in data
        reading = artifact_model.read_revision(page_dir, activated.revision)
        assert reading.document.data == data
        assert predecessor_reading(page_dir, data, events, checked.artifact).unchanged


def test_an_activated_revision_adopts_the_reading_its_check_took(page_dir, monkeypatch):
    """The revision activation writes is the candidate the check just read, so it
    holds that reading — the captured bytes, CRLF included, and the words the
    transition check walked — rather than parsing and walking the file it wrote."""
    source = PAGE.replace("</main>", "<p>A next version.</p></main>")
    (page_dir / "index.html").write_bytes(source.replace("\n", "\r\n").encode())
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.created, activated.error

    def no_parse(_source):
        raise AssertionError("the activated revision was parsed again")

    walks = []
    native = passages_model.page_passages

    def counted(*args, **kwargs):
        walks.append(args)
        return native(*args, **kwargs)

    monkeypatch.setattr(artifact_model, "SourceDocument", no_parse)
    monkeypatch.setattr(passages_model, "page_passages", counted)
    reading = artifact_model.read_revision(page_dir, activated.revision)
    marker = files_model.revision_path(page_dir, activated.revision)
    assert reading.document.data == marker.read_bytes()
    assert b"\r\n" in reading.document.data
    assert reading.spoken
    assert len(walks) == 1
    assert reading.spoken
    assert len(walks) == 1


def test_held_revision_readings_stay_within_their_source_budget(page_dir, monkeypatch):
    """Held readings are charged their source size and the least recently read go
    first, so resident parses stay bounded however long a history grows; the reading
    just asked for is always kept."""
    for edit in range(4):
        (page_dir / "index.html").write_text(
            PAGE.replace("</main>", f"<p>edit {edit}</p></main>")
        )
        assert revisioning_model.activate_source(page_dir).error is None
    revisions = files_model.list_revisions(page_dir)
    size = files_model.revision_path(page_dir, revisions[-1]).stat().st_size
    monkeypatch.setattr(artifact_model._Readings, "BUDGET", 2 * size + size // 2)
    with fresh_process():
        readings = [artifact_model.read_revision(page_dir, r) for r in revisions]
        kept = page_memory_model.memo(page_dir, artifact_model._Readings)
        assert [reading for _stamp, reading in kept.held.values()] == readings[-2:]
        assert kept.size <= kept.BUDGET
        # Reading an evicted revision again takes a fresh reading, and one still
        # held answers with the same object.
        assert artifact_model.read_revision(page_dir, revisions[-1]) is readings[-1]
        assert artifact_model.read_revision(page_dir, revisions[0]) is not readings[0]


def test_question_history_survives_parse_eviction_and_new_revisions(
    page_dir, monkeypatch
):
    """A retry or new version reuses completed historical registration work.

    A history larger than the parse cache used to parse every predecessor on every
    read. Count parses rather than time, so contention cannot change the result.
    """
    from leaf.work_reading import WorkReading

    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    for edit in range(4):
        (page_dir / "index.html").write_text(
            (source if edit == 0 else source.replace(" choose", "")).replace(
                "</main>", f"<p>edit {edit}</p></main>"
            )
        )
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error

    monkeypatch.setattr(artifact_model._Readings, "BUDGET", 1)
    parsed = []
    native = artifact_model.SourceDocument

    def counted(data):
        parsed.append(data)
        return native(data)

    monkeypatch.setattr(artifact_model, "SourceDocument", counted)

    def read():
        revisions = files_model.list_revisions(page_dir)
        events = events_model.read_events(page_dir)
        reading = artifact_model.read_revision(page_dir, revisions[-1])
        page = projection_model.page_reading(
            reading,
            events,
            revisions[-1],
            revisions=revisions,
            revision_reader=lambda revision: artifact_model.read_revision(
                page_dir, revision
            ),
        )
        return WorkReading(
            events,
            reading.registry,
            page,
            registry_for_revision=lambda revision: (
                artifact_model.read_revision(page_dir, revision).registry
            ),
            available_revisions=revisions,
        ).document.questions

    with fresh_process():
        initial = read()
        assert len(parsed) == 4
        assert initial["all"][0]["status"] == "withdrawn"
        parsed.clear()
        assert read() == initial
        assert len(parsed) <= 1  # the active revision may have been evicted
        (page_dir / "index.html").write_text(
            source.replace(" choose", "").replace("</main>", "<p>new</p></main>")
        )
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error
        parsed.clear()
        assert read() == initial
        assert len(parsed) <= 1
        kept = page_memory_model.memo(page_dir, artifact_model._CompactReadings)
        assert kept.size <= kept.BUDGET


def test_data_history_survives_parse_eviction_with_captured_scopes_and_contracts(
    page_dir, monkeypatch
):
    """Repeated source checks reuse history without changing binding identity.

    Nested samples retain their own id spaces, old layers retain their contracts,
    and a newly captured layer owns the current producer's binding.
    """
    declare_data_input(
        page_dir, "project-feed", {"type": "array"}, contract="rows", activate=False
    )
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    source = (
        (page_dir / "index.html")
        .read_text()
        .replace(
            "</main>",
            '<lf-sample id="outer" window><template id="outer-page" data-sample>'
            '<lf-sample id="inner" window><template id="inner-page" data-sample>'
            '<lf-test-data id="test-data" source="project-feed"></lf-test-data>'
            "</template></lf-sample></template></lf-sample></main>",
        )
    )
    for revision in range(1, 4):
        write_revision(page_dir, revision, source.encode())
    registry["$data"]["contracts"]["current-rows"] = registry["$data"]["contracts"][
        "rows"
    ]
    registry["lf-test-data"]["x-data"]["data"]["contract"] = "current-rows"
    registry_path.write_text(json.dumps(registry))
    write_revision(page_dir, 4, source.encode())
    append_command(
        page_dir,
        {
            "kind": "comment",
            "id": "frozen-data",
            "revision": 1,
            "author": "agent",
            "text": "The captured feed.",
            "markup": '<lf-test-data id="reply-data" source="project-feed"></lf-test-data>',
        },
    )
    events = events_model.read_events(page_dir)
    monkeypatch.setattr(artifact_model._Readings, "BUDGET", 1)
    parsed = []
    native = artifact_model.SourceDocument

    def counted(data):
        parsed.append(data)
        return native(data)

    monkeypatch.setattr(artifact_model, "SourceDocument", counted)

    def read():
        """The same immutable binding readings serve checks and producer inventory."""
        documents = data_contracts_model.page_data_document_readings(
            page_dir, events, registry
        )
        bindings, errors = data_contracts_model.merge_data_document_readings(documents)
        return documents, bindings, errors

    with fresh_process():
        documents, bindings, errors = read()
        assert len(parsed) == 4
        assert bindings == {"project-feed": "current-rows"} and errors == []
        assert [
            data_contracts_model.declared_data_bindings(records, captured)[0][
                "project-feed"
            ]
            for records, label, captured in documents
            if label in {"revision r1", "revision r4", "event 'frozen-data' markup"}
        ] == ["rows", "rows", "current-rows"]
        expected = {
            "project-feed": {
                "contract": "current-rows",
                "consumers": [
                    {"widget": "test-data", "input": "data", "document": label}
                    for label in (
                        "revision r4 sample 'outer-page' sample 'inner-page'",
                        "revision r4",
                    )
                ],
            }
        }
        parsed.clear()
        assert read() == (documents, bindings, errors)
        assert (
            data_contracts_model.page_data_binding_inventory(page_dir, registry, events)
            == expected
        )
        assert parsed == []
        write_revision(page_dir, 5, source.encode())
        parsed.clear()
        assert read()[1:] == (bindings, errors)
        expected["project-feed"]["consumers"].extend(
            {**consumer, "document": consumer["document"].replace("r4", "r5")}
            for consumer in expected["project-feed"]["consumers"][:]
        )
        assert (
            data_contracts_model.page_data_binding_inventory(page_dir, registry, events)
            == expected
        )
        assert len(parsed) <= 1


def test_a_process_keeps_the_pages_it_read_most_recently(page_dir):
    """A process keeps what it read of the last few pages it read, so one that reads
    many, such as the website or a test worker, holds a bounded amount however many
    it has read. A page read again while kept answers with the same reading; one
    dropped is read afresh and its old reading is freed. A memory something still
    holds, as a sample holds its own, outlives being pushed out."""
    revision = revisioning_model.activate_source(page_dir).revision
    held_page = page_dir.parent / "held"
    shutil.copytree(page_dir, held_page)
    with fresh_process():
        held = artifact_model.read_revision(page_dir, revision)
        assert artifact_model.read_revision(page_dir, revision) is held
        kept = weakref.ref(held)
        del held
        holder = page_memory_model.memory_of(held_page)
        sample_reading = artifact_model.read_revision(held_page, revision)
        for n in range(page_memory_model.PageMemories.LIMIT):
            other = page_dir.parent / f"other-{n}"
            shutil.copytree(page_dir, other)
            artifact_model.read_revision(other, revision)
        gc.collect()
        assert kept() is None
        assert artifact_model.read_revision(page_dir, revision).document.title
        assert artifact_model.read_revision(held_page, revision) is sample_reading
        assert page_memory_model.memory_of(held_page) is holder


def test_a_reading_under_outcomes_is_the_walk_under_them():
    """`decided_passages` answers for `page_passages` with the same outcomes.

    Outcomes naming no element the document carries cannot move any field of the
    walk, so the authored reading answers for them; an outcome on an element it
    does carry retires that element's losing slot, or empties a widget it leaves
    showing nothing, exactly as the walk given it does."""
    registry = {
        "lf-old": {"x-retired-when": "accepted"},
        "lf-new": {"x-retired-when": "rejected"},
    }
    document = structure_model.SourceDocument(
        '<main><lf-suggestion id="edit"><lf-old><p>Old words.</p></lf-old>'
        "<lf-new><p>New words.</p></lf-new></lf-suggestion>"
        '<lf-suggestion id="cut"><lf-old><p>Cut words.</p></lf-old></lf-suggestion>'
        '<p id="after">After.</p></main>'
    )
    reading = passages_model.SourceReading(document, registry)

    elsewhere = {"not-here": "accepted"}
    assert reading.decided_passages(elsewhere) is reading.passages
    assert reading.passages == passages_model.page_passages(
        document, registry, elsewhere
    )

    decided = {"edit": "accepted", "cut": "accepted", "not-here": "rejected"}
    retired = reading.decided_passages(decided)
    assert retired == passages_model.page_passages(document, registry, decided)
    assert retired.text == "New words. After."
    assert retired.gone == {"cut": "accepted"}


def test_projected_verbatim_scopes_page_state_to_here_and_thread_state_to_its_log():
    from leaf.registry.contract import state_definition

    registry = {
        "lf-draft": {
            "x-upgrade": True,
            "x-verbatim": True,
            "x-state": {
                "edit": {
                    "unit": "widget",
                    "record": {"kind": "body"},
                }
            },
        }
    }
    page = '<lf-draft id="page-draft"><pre>Page authored.</pre></lf-draft>'
    frozen = '<lf-draft id="frozen-draft"><pre>Frozen authored.</pre></lf-draft>'

    def action(identity, text, seq):
        return {
            "kind": "action",
            "id": f"a-{identity}",
            "author": "user",
            "revision": 2,
            "widget": identity,
            "action": "edit",
            "detail": {"value": text},
            "meaning": {
                "unit": identity,
                "depends": [identity],
                "answer": None,
                "scope": "page",
                "state": state_definition(
                    "lf-draft",
                    registry["lf-draft"],
                    registry["lf-draft"]["x-state"]["edit"],
                ),
            },
            "seq": seq,
        }

    events = [
        {
            "kind": "comment",
            "id": "c-scope",
            "author": "user",
            "revision": 1,
            "text": "Keep the frozen answer current.",
            "seq": 1,
        },
        {
            "kind": "reply",
            "id": "r-scope",
            "author": "agent",
            "parent": "c-scope",
            "revision": 1,
            "text": "Here it is:",
            "markup": frozen,
            "seq": 2,
        },
        action("page-draft", "Page future.", 3),
        action("frozen-draft", "Frozen standing.", 4),
    ]

    expected = render_gate_readings._expected_verbatim(
        page,
        events,
        registry,
        here=1,
        registry_for_revision=lambda revision: registry,
        available_revisions={1},
    )

    assert expected == {
        ("page", None, 0): [{"text": "Page authored."}],
        ("event", "r-scope", 0): [{"text": "Frozen standing."}],
    }


def test_projected_verbatim_includes_generated_children():
    registry = {
        "lf-list": {
            "x-upgrade": True,
            "x-verbatim": True,
            "x-state": {
                "add": {
                    "detail": {"type": "object"},
                    "unit": "item",
                    "creates": {"child": "lf-item", "words": "text"},
                }
            },
        },
        "lf-item": {"x-upgrade": False},
    }
    markup = '<lf-list id="list">Authored item.</lf-list>'
    event = {
        "kind": "action",
        "id": "a-add",
        "author": "user",
        "revision": 1,
        "widget": "list",
        "action": "add",
        "detail": {"item": "new-item", "text": "Generated item."},
        "meaning": {
            "unit": "new-item",
            "depends": ["list", "new-item"],
            "creates": "lf-item",
            "scope": "page",
        },
        "seq": 1,
    }

    from leaf.registry.contract import state_definition

    event["meaning"]["state"] = state_definition(
        "lf-list", registry["lf-list"], registry["lf-list"]["x-state"]["add"]
    )
    expected = render_gate_readings._expected_verbatim(
        markup,
        [event],
        registry,
        here=1,
        registry_for_revision=lambda revision: registry,
        available_revisions={1},
    )

    assert expected == {("page", None, 0): [{"text": "Authored item. Generated item."}]}


def test_a_unified_diff_capture_refuses_a_line_range(tmp_path):
    """A patch is captured whole: a `lines` range beside `"format": "unified-diff"`
    is refused rather than silently dropped, and the same range on text applies."""
    source = tmp_path / "change.patch"
    source.write_text("one\ntwo\nthree\n")
    with pytest.raises(ValueError, match="takes the whole patch"):
        captured_value(source, {"format": "unified-diff", "lines": "1:2"})
    assert captured_value(source, {"lines": "2:3"}) == "two\nthree\n"


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parents[1] / "markdown_body_cases.json").read_text()),
)
def test_markdown_body_file_words_match_the_shared_browser_dialect(case):
    from html import escape

    import turbohtml

    document = structure_model.SourceDocument(
        f'<main><lf-draft id="note"><pre>{escape(case["source"])}</pre></lf-draft></main>'
    )
    registry = {
        "lf-draft": {
            "x-content": "data",
            "x-text-format": "markdown",
            "x-verbatim": True,
        }
    }
    assert passages_model.page_passages(document, registry).text == case["words"]
    rendered = turbohtml.parse(passages_model.markdown_markup(case["source"]))
    assert [
        {"text": link.text, "href": link.attrs["href"]} for link in rendered.select("a")
    ] == case["links"]


@pytest.mark.parametrize("source", ["    code", "A ", "A\n", "A  \nB", "\nA"])
def test_exact_markdown_body_retains_saved_whitespace_across_revision(page_dir, source):
    """Pre indentation and edge whitespace are content, including code and hard breaks."""

    def write(words):
        # HTML pre removes one opening newline, so encode an intended first newline twice.
        encoded = ("\n" + words) if words.startswith("\n") else words
        (page_dir / "index.html").write_text(
            PAGE.replace(
                "<h2>Plan</h2>",
                f'<h2>Plan</h2><lf-draft id="exact"><pre>{encoded}</pre></lf-draft>',
            )
        )

    write("Original.")
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "exact",
            "action": "edit",
            "detail": {"value": source},
        },
    )
    write(source)
    errors = check_source(page_dir, events_model.read_events(page_dir)).errors
    assert errors == []
    assert stamp(page_dir, "take in exact Markdown source").exit_code == 0
    [edit] = [
        item for item in state_json(page_dir)["state"] if item["action"] == "edit"
    ]
    assert edit["detail"] == {"value": source}


def test_revisions_change_decision_words_labels_and_defaults_without_retracting(
    page_dir,
):
    """Edits remain free while the original user action keeps its recorded meaning."""
    live = OPTIONS.format(a="", b="", chip="", shim="Fastest to ship.", stage="Two.")
    source = page_dir / "index.html"
    source.write_text(PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + live))
    publish(page_dir)
    picked = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
        },
    )
    edited = live.replace(
        "Fastest to ship.",
        'A revised recommendation. <small class="tag">Recommended</small>',
    ).replace('id="o-stage"', 'id="o-stage" chosen')
    source.write_text(PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + edited))
    assert stamp(page_dir, "revise recommendation").exit_code == 0
    [standing] = [
        item for item in state_json(page_dir)["state"] if item["action"] == "choose"
    ]
    assert standing["detail"] == {"value": ["o-shim"]}
    source.write_text(PAGE)
    assert stamp(page_dir, "retire answered ask").exit_code == 0
    assert picked in events_model.read_events(page_dir)
    assert not any(
        event.get("restated") for event in events_model.read_events(page_dir)
    )


def test_a_decision_stands_when_an_earlier_leaf_recorded_its_operation(page_dir):
    """An action admitted by an earlier Leaf keeps standing, and keeps its Question
    answered, under a Leaf that records the same operation's definition with other
    fields. Before #2329 the definition carried `update`, the verb flag now
    named `text`; matching every recorded field dropped each decision on a page
    that Leaf version had served."""
    source = page_dir / "index.html"
    source.write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>"
            + OPTIONS.format(a="", b="", chip="", shim="Fast.", stage="Two."),
        )
    )
    publish(page_dir)
    picked = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-shim"]},
        },
    )
    log = page_dir / "events.jsonl"
    earlier = []
    for line in log.read_text().splitlines():
        event = json.loads(line)
        if event["id"] == picked["id"]:
            recorded = event["meaning"]["state"]
            recorded["update"] = False
        earlier.append(json.dumps(event))
    log.write_text("\n".join(earlier) + "\n")

    reading = state_json(page_dir)
    [standing] = [item for item in reading["state"] if item["action"] == "choose"]
    assert standing["detail"] == {"value": ["o-shim"]}
    [question] = reading["asks"]
    assert question["status"] == "answered"
    assert question["answer"]["event"]["id"] == picked["id"]


def test_revisions_change_edited_drafts_without_retracting_the_user_edit(page_dir):
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    v2("A new authored draft.")
    assert stamp(page_dir, "revise draft").exit_code == 0
    [edit] = [
        item for item in state_json(page_dir)["state"] if item["action"] == "edit"
    ]
    assert edit["detail"] == {"value": "Cut the flag; backfill first."}
    v2("Another authored draft.", attrs=" restated")
    assert stamp(page_dir, "explicitly retract edit").exit_code == 0
    assert not [
        item for item in state_json(page_dir)["state"] if item["action"] == "edit"
    ]


def test_revisions_can_move_rewrite_or_remove_authored_generated_children(page_dir):
    added = "g1-option-user-route"
    live = OPTIONS.format(a="", b="", chip="", shim="Fastest to ship.", stage="Two.")
    source = page_dir / "index.html"
    source.write_text(PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + live))
    publish(page_dir)
    event = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "add",
            "detail": {"option": added, "text": "My route."},
        },
    )
    for authored in (
        live.replace(
            "</lf-options>",
            f'<lf-option id="{added}">Revised route.</lf-option></lf-options>',
        ),
        live + f'<p id="{added}">Relocated explanation.</p>',
        live,
    ):
        source.write_text(PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + authored))
        checked = check_source(page_dir, events_model.read_events(page_dir))
        assert checked.errors == []
        assert stamp(page_dir, "revise generated child").exit_code == 0
        assert event in events_model.read_events(page_dir)


def test_transition_attributes_do_not_require_earned_or_first_version_retractions(
    page_dir,
):
    source = page_dir / "index.html"
    source.write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1" restated><pre>Words.</pre></lf-draft>',
        )
    )
    for _ in range(2):
        checked = check_source(page_dir, events_model.read_events(page_dir))
        assert checked.errors == []
        assert stamp(page_dir, "explicit declaration").exit_code == 0
        source.write_text(source.read_text().replace("Words.", "New words."))
    _tasks_version(page_dir, "active", " overruled")
    checked = check_source(page_dir, events_model.read_events(page_dir))
    assert checked.errors == []


def test_revisions_drop_anchored_sections_and_relocate_lost_visual_parts(page_dir):
    source = page_dir / "index.html"
    source.write_text(
        FLOW_PAGE.replace(
            '<lf-diagram id="flow">', '<lf-diagram id="flow" parts="node:A node:B">'
        )
    )
    publish(page_dir)
    root = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "flow", "visual": "node:A"},
            "text": "Explain this node.",
        },
    )
    source.write_text(
        source.read_text().replace('parts="node:A node:B"', 'parts="node:B"')
    )
    assert stamp(page_dir, "revise drawing").exit_code == 0
    [thread] = state_json(page_dir)["threads"]
    assert thread["anchor"] == {"section": "flow"}
    source.write_text(FLOW_PAGE.replace('id="flow"', 'id="new-flow"'))
    assert stamp(page_dir, "replace drawing").exit_code == 0
    [thread] = state_json(page_dir)["threads"]
    assert thread["anchor"] is None
    assert root in events_model.read_events(page_dir)
