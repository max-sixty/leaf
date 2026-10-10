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
import weakref
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    OPTIONS,
    PAGE,
    SHIPPED_PACKAGES,
    STATED_TIMEOUT,
    SUGGESTION,
    X,
    Y,
    _board,
    _decided,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    asks_on_you,
    before_choice,
    check,
    comment,
    decide,
    declare_data_input,
    fresh_process,
    lock_contention,
    model_layer,
    publish,
    read_page_data,
    response_reference,
    stamp,
    state_json,
    suggest,
    write_revision,
)
from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import leases as leases_model
from leaf import page_memory as page_memory_model
from leaf import passages as passages_model
from leaf import projection as projection_model
from leaf import publishing as publishing_model
from leaf import revision_artifact as artifact_model
from leaf import revision_delivery as revision_delivery_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf.registry.storage import read_page_registry, require_registry
from leaf.render_gate import readings as render_gate_readings
from leaf.served_state.context import read_page
from leaf.served_state.page import read_served_page
from leaf.validation import compatibility as validation_model
from leaf.validation.source import check_source
from leaf.validation.source_history import predecessor_reading
from leaf_dev.example_data import captured_value, patch_manifest


def test_check_accepts_a_valid_page(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_check_accepts_authored_module_scripts(page_dir):
    version = page_dir / "index.html"
    version.write_text(
        PAGE.replace(
            "</head>",
            '<script type="module">window.authoredModuleRan = true;</script></head>',
        )
    )

    result = check(page_dir)

    assert result.exit_code == 0, result.output


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
        with pytest.raises(SystemExit, match="missing.js"):
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
    with pytest.raises(SystemExit, match="authored inputs changed"):
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


def test_the_captured_executable_digest_separates_code_from_content(page_dir):
    """What a standing document cannot take on in place, and nothing else.

    A user's open document keeps its module graph and its defined elements for as
    long as it lives, so the capture states which revisions can be given to that
    document and which need a new one. Words, styling, and the stamp a vendoring
    run leaves behind can be given to it. The vocabulary that binds elements to
    modules, the module bytes, and the inline module bodies cannot. A re-vendor
    reaches the digest through the modules it replaced, its epoch included.
    """
    authored = page_dir / "page"
    (authored / "widgets").mkdir(parents=True)
    (authored / "app.js").write_text("window.result = 1;")
    (authored / "style.css").write_text("main { color: rebeccapurple; }")
    (authored / "widgets" / "lf-options.js").write_text("export function upgrade() {}")
    source = PAGE.replace(
        "</head>",
        '<script type="module" src="/page/app.js"></script>'
        '<script type="module">window.inlineRan = 1;</script>'
        '<link rel="stylesheet" href="/page/style.css"></head>',
    )

    # Each revision below carries every edit before it, so a comparison is always
    # against the revision immediately before and names one changed input.
    document = source

    def activate():
        (page_dir / "index.html").write_text(document)
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error
        assert activated.created
        return artifact_model.read_artifact(page_dir, activated.revision)

    base = activate()

    document = document.replace("<body>", '<body data-annotations="overlay">')
    explicit_overlay = activate()
    assert explicit_overlay.executable == base.executable

    document = document.replace('data-annotations="overlay"', 'data-annotations="page"')
    page_annotations = activate()
    assert page_annotations.executable != explicit_overlay.executable

    document = document.replace(' data-annotations="page"', "")
    restored_overlay = activate()
    assert restored_overlay.executable == base.executable

    document = document.replace("<h2>Plan</h2>", "<h2>The plan, restated</h2>")
    reworded = activate()
    assert reworded.digest != base.digest
    assert reworded.executable == base.executable

    (authored / "style.css").write_text("main { color: seagreen; }")
    restyled = activate()
    assert restyled.digest != reworded.digest
    assert restyled.executable == base.executable

    (authored / "app.js").write_text("window.result = 2;")
    remoduled = activate()
    assert remoduled.executable != restyled.executable

    (authored / "widgets" / "lf-options.js").write_text(
        "export function upgrade() { return true; }"
    )
    rewidgeted = activate()
    assert rewidgeted.executable != remoduled.executable

    document = document.replace("window.inlineRan = 1;", "window.inlineRan = 2;")
    inlined = activate()
    assert inlined.executable != rewidgeted.executable

    # A script's attributes decide whether it runs, and a src on another server is
    # named nowhere else.
    document = document.replace(
        '<script type="module">window.inlineRan = 2;</script>',
        '<script type="text/plain">window.inlineRan = 2;</script>',
    )
    retyped = activate()
    assert retyped.executable != inlined.executable

    document = document.replace(
        "</head>", '<script defer src="https://esm.sh/chart.js@4"></script></head>'
    )
    linked = activate()
    assert linked.executable != retyped.executable
    document = document.replace("chart.js@4", "chart.js@5")
    relinked = activate()
    assert relinked.executable != linked.executable

    # Scripts run in document order, so moving one past another is new code too.
    chart = '<script defer src="https://esm.sh/chart.js@5"></script>'
    document = document.replace(chart, "").replace(
        '<script type="text/plain">', chart + '<script type="text/plain">'
    )
    reordered = activate()
    assert reordered.executable != relinked.executable

    declaration = json.loads((page_dir / "registry.json").read_text())["lf-options"]
    declaration["description"] = "Options this page declares for itself."
    (authored / "registry.json").write_text(json.dumps({"lf-options": declaration}))
    redeclared = activate()

    files_model.replace_files(
        [(page_dir / "leaf.js", b"// re-vendored runtime", False)]
    )
    revendored = activate()
    assert revendored.executable != redeclared.executable

    # `$layer` records where a vendoring run came from rather than what it
    # installed: the fingerprint identifies the composed layer independently of
    # its epoch, the producer names the checkout that built it, and the epoch
    # itself is a fresh token every `page init` mints. None of the three says
    # what this document would have to evaluate, so a restamp on its own leaves
    # the digest alone.
    layer_path = page_dir / "registry.json"
    vendored = json.loads(layer_path.read_text())
    vendored["$layer"] = {
        **vendored["$layer"],
        "fingerprint": "sha256:" + "b" * 64,
        "producer": {"commit": "abcdef1", "dirty": True},
        "generation": "0123456789abcdef0123456789abcdef",
    }
    files_model.replace_files([(layer_path, json.dumps(vendored).encode(), False)])
    restamped = activate()
    assert restamped.digest != revendored.digest
    assert restamped.executable == revendored.executable

    # Vendoring writes that epoch into `runtime/layer-generation.js`, which every
    # document evaluates, so a real re-vendor reaches the digest through the
    # module rather than through the stamp beside it.
    files_model.replace_files(
        [(page_dir / "runtime" / "layer-generation.js", b"// re-vendored epoch", False)]
    )
    reissued = activate()
    assert reissued.executable != restamped.executable


def test_the_captured_widget_digests_say_which_widgets_a_user_may_keep(page_dir):
    """One digest per declared widget, over what its author wrote.

    A user's open document keeps the widgets a revision did not rewrite, and only the
    capture still holds the markup to say which those are: after upgrade a controller
    owns every widget's children. Digested from the parsed tree, so two revisions of one
    widget differ where the author changed it and nowhere else.
    """
    document = PAGE

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
        ('import "./data\\u002ejson";', "unescaped string literals"),
        ("export const = ;", "invalid JavaScript"),
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


def test_artifact_cache_refuses_a_replaced_immutable_manifest(page_dir):
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    revision = files_model.latest_revision(page_dir)
    first = artifact_model.read_artifact(page_dir, revision)
    assert artifact_model.read_artifact(page_dir, revision) is first
    manifest_path = (
        files_model.revision_path(page_dir, revision).with_suffix("") / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["implementations"] = {}
    files_model.replace_files(
        [(manifest_path, json.dumps(manifest, sort_keys=True).encode(), False)]
    )

    with pytest.raises(artifact_model.ArtifactError, match="manifest digest"):
        artifact_model.read_artifact(page_dir, revision)


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
        ("<script>window.x = 1;</script>", "still parsing"),
        (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
            "still parsing",
        ),
        (
            '<script type="module" async src="https://unpkg.com/d3"></script>',
            "runs whenever it arrives",
        ),
    ],
    ids=["inline-classic", "blocking-classic", "async-module"],
)
def test_check_runs_each_script_after_leaf_reads_the_page(page_dir, authored, expected):
    """A page's scripts are its author's, classic or module, from any server, but
    each runs after Leaf reads the page."""
    version = page_dir / "index.html"
    version.write_text(PAGE.replace("</main>", f"{authored}</main>"))

    result = check(page_dir)

    assert result.exit_code == 1
    assert expected in result.output


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
    json.loads((Path(__file__).parent / "option_markdown_cases.json").read_text()),
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


RANK_CASES = json.loads((Path(__file__).parent / "rank_cases.json").read_text())


def test_rank_rules_match_the_browser_cases():
    """`tests/runtime/board-order.test.mjs` reads the same cases against
    `projection/model.js`, so the two runtimes rank authored units alike and the
    append door admits what a widget computes."""
    assert projection_model.RANK.pattern == RANK_CASES["pattern"]
    for index, rank in RANK_CASES["authored"]:
        assert projection_model.authored_rank(index) == rank
        assert projection_model.RANK.fullmatch(rank)
    assert all(projection_model.RANK.fullmatch(r) for r in RANK_CASES["valid"])
    assert not any(projection_model.RANK.fullmatch(r) for r in RANK_CASES["invalid"])


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


def test_a_version_can_change_the_authored_column_after_a_user_move(page_dir):
    _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, "nabc", "x")
    revised = check(page_dir)
    assert revised.exit_code == 0, revised.output


def test_a_version_that_leaves_the_moves_column_alone_needs_not_write_it(page_dir):
    """While a version authors the move's column as the move's revision did, the rank
    still lands in the gap the user chose, so leaving the move to the log is sound
    and a prose edit or a re-vendor needs no transcription."""
    _drop_x_between_a_and_b(page_dir)
    (page_dir / "index.html").write_text(
        (page_dir / "index.html").read_text().replace("<h2>Plan</h2>", "<h2>Plans</h2>")
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output
    publish(page_dir, 2)
    assert _todo_order(page_dir) == ["a", "x", "b", "c"]


def test_a_version_that_writes_the_move_owns_its_order(page_dir):
    """Once a version writes the move, its markup is where the card stands: the rank
    no longer places it, and the move is no longer the user's to take back, since
    the markup would decide the order an undo restored."""
    move = _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, "naxbc")
    assert check(page_dir).exit_code == 0, check(page_dir).output
    publish(page_dir, 2)
    assert _todo_order(page_dir) == ["n", "a", "x", "b", "c"]
    with pytest.raises(events_model.EventRefused, match="markup now places its unit"):
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": move["id"]}
        )


def test_a_later_version_can_reposition_a_card_without_retracting_its_move(page_dir):
    """Authored placements may change while the original move remains logged."""
    _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, "naxbc")
    publish(page_dir, 2)
    _write_board(page_dir, "naxcb")
    assert check(page_dir).exit_code == 0, check(page_dir).output
    _write_board(page_dir, "nacxb")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "index.html").write_text(
        (page_dir / "index.html")
        .read_text()
        .replace('<lf-card id="x">', '<lf-card id="x" restated>')
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output


def test_a_reorder_the_next_version_wrote_survives_a_later_one(page_dir):
    """A later authored reorder is allowed without implicitly retracting a move."""
    _write_board(page_dir, "abc")
    publish(page_dir)
    _move(page_dir, "c", "c-todo", "0i")
    _write_board(page_dir, "cab")
    publish(page_dir, 2)
    _write_board(page_dir, "abc")
    (page_dir / "index.html").write_text(
        (page_dir / "index.html").read_text().replace("<h2>Plan</h2>", "<h2>Plans</h2>")
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("todo", "passes"),
    [
        ("baxc", True),  # a and b swapped: x still right after a
        ("naxbmc", True),  # cards added around the gap
        ("axc", True),  # b dropped
        ("abxc", True),
        ("abcx", True),
        ("xabc", True),
    ],
)
def test_authored_cards_can_move_to_any_gap_after_a_user_move(page_dir, todo, passes):
    """The user put x between a and b: right after a, among the cards both versions
    list. A version that keeps that says what the user said however it arranges or
    adds cards elsewhere."""
    _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, todo)
    assert (check(page_dir).exit_code == 0) == passes, check(page_dir).output


def test_a_later_authored_reorder_is_allowed_with_a_move_standing(page_dir):
    """A card moved up its own column changes no container, so a reading of the
    column alone would take a version that ignores the move as recording it. At the
    top, no card both versions list precedes it."""
    _write_board(page_dir, "abc")
    publish(page_dir)
    _move(page_dir, "c", "c-todo", "0i")
    assert _todo_order(page_dir) == ["c", "a", "b"]
    _write_board(page_dir, "abcn")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    _write_board(page_dir, "ncab")
    assert check(page_dir).exit_code == 0


def test_a_move_on_a_replaced_revision_lands_only_where_its_column_held(page_dir):
    """A rank read on r1 lands in another gap on r2 once r2 adds a card to the
    column, so the door refuses that move, with words for the user apart from the
    reason. A newer revision that left the column alone takes it."""
    _write_board(page_dir, "abc", "x")
    publish(page_dir)
    _write_board(page_dir, "nabc", "x")
    publish(page_dir, 2)
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
    publish(page_dir, 3)
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
    """`data_bindings` names each bound source and the widgets that read it, whose
    value is `data/<source>.json`, and a file another process rewrote past its
    contract reads as that source's error."""
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
    assert json.loads(stored.read_text()) == ["passing"]
    [consumer] = state["data_bindings"]["builds"]["consumers"]
    assert consumer["widget"] == "test-data"
    assert state["data"]["errors"] == []

    stored.write_text('["passing", 3]')
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


def test_check_leaves_the_documents_encoding_to_delivery(page_dir):
    """One declaration at delivery's first-byte boundary owns document encoding."""
    version = page_dir / "index.html"
    authored = version.read_text().replace("</head>", '<meta charset="utf-8">\n</head>')
    version.write_text(authored)
    result = check(page_dir)
    assert result.exit_code == 1
    assert "<meta charset>" in result.output
    assert "belongs to delivery" in result.output


def test_check_refuses_noscript_words_the_browser_never_renders(page_dir):
    """In a scripting browser noscript is hidden, while the file reader takes its
    content for page words. Refusal prevents anchoring on text no user can see."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2><noscript>Fallback words.</noscript>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "<noscript>" in result.output
    assert "the browser renders none of its content" in result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    out = result.output
    # Both the widget and the plain <figure/>: the slash misleads a browser on
    # any non-void tag, not only on the vocabulary's.
    assert out.count("self-closing") == 2
    assert "unknown widget" in out
    assert '<lf-column tone="medium">' in out
    assert "not a tone this page's layer paints" in out
    assert "must be a direct member of <lf-options>" in out
    assert "'id' is a required property" in out
    assert "does not match" in out  # id pattern
    # A stray element beside the <pre>, and a body that never opened one: both are
    # the same rule, since the <pre> is what carries the whitespace the notation needs.
    assert out.count("its body is one <pre> holding the text") == 2
    assert "text outside its <pre>" in out


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<lf-code language="pythn">' in result.output, result.output
    assert 'class="language-pythn"' not in result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<lf-gloss dialect="lisp">' in result.output
    assert "not a language this page's layer speaks" in result.output


EXCERPT = """<lf-code id="walk" language="rust" lines="{lines}" hi="{hi}"><pre>
fn merge_sort()
{{
    while end &gt; 0 {{
        start -= 1;
}}
</pre>
<lf-note at="{at}">The loop.</lf-note>
</lf-code>"""


@pytest.mark.parametrize(
    ("lines", "hi", "at", "refusals"),
    [
        # A snippet: no numbering, so its five lines are 1..5.
        ("", "2-3", "5", []),
        # An excerpt: two stretches of the file, referenced by the file's numbers,
        # a range free to span the gap between them, and a left-out line addressing
        # the elided row that stands for it.
        ("1505-1506,1550-1552", "1506-1550", "1552", []),
        ("1505-1506,1550-1552", "1520-1530", "1507", []),
        (
            "1505-1506,1550-1552",
            "3",
            "1553",
            [
                'hi="3"> (line 10): line 3 is outside the body\'s lines="1505-1506,1550-1552"',
                'at="1553"> (line 17): line 1553 is outside the body\'s lines=',
            ],
        ),
        (
            "1505-1506,1550-1553",
            "1505",
            "1505",
            [
                'lines="1505-1506,1550-1553"> (line 10): numbers 6 lines, but the body has 5'
            ],
        ),
        # A range is counted, never expanded, so a huge one is a quick refusal.
        (
            "1-1000000000",
            "1",
            "1",
            ["numbers 1000000000 lines, but the body has 5"],
        ),
        # Source lines count from 1, so no excerpt quotes a line 0.
        ("0-4", "1", "1", ["<lf-code> (line 10): '0-4' does not match"]),
        (
            "1550-1552,1505-1506",
            "1505",
            "1505",
            [
                (
                    'lines="1550-1552,1505-1506"> (line 10): '
                    "range 1505-1506 does not follow line 1552"
                )
            ],
        ),
    ],
)
def test_an_excerpt_is_referenced_by_the_numbers_it_quotes(
    page_dir, lines, hi, at, refusals
):
    """`lines` gives a code block's body the numbers it has in its source file, and
    every line reference into the block — its `hi`, a note's `at` — names lines by
    them. The check holds the numbering to one ascending number per body line. A line
    the excerpt leaves out is still in it, as the elided row standing for its stretch,
    so only a reference past either end, which the module would silently paint
    nowhere, is refused."""
    block = EXCERPT.format(lines=lines, hi=hi, at=at)
    if not lines:
        block = block.replace(' lines=""', "")
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", f"<h2>Plan</h2>\n{block}")
    )
    result = check(page_dir)
    for refusal in refusals:
        assert refusal in result.output, result.output
    assert (result.exit_code == 1) == bool(refusals), result.output
    assert result.output.count("\n  - ") == len(refusals), result.output


BODY_TEXT_CASES = json.loads(
    (Path(__file__).parent / "body_text_cases.json").read_text()
)["cases"]


def test_a_numbering_counts_the_lines_lf_code_draws(page_dir):
    """`tests/runtime/body-text.test.mjs` reads the same bodies against `bodyText`, the
    text lf-code draws and numbers. Each block here numbers exactly those lines, so
    the gate passes them all only if it trims a body as the module does — the browser's
    whitespace at the edges, where Python's own `\\s` would count U+FEFF as a line and
    U+0085 or U+001C as none."""
    blocks = "\n".join(
        # The newline after <pre> is the parser's to drop, leaving the body as written.
        f'<lf-code id="c{i}" lines="1-{text.count(chr(10)) + 1}"><pre>\n{body}</pre>'
        "</lf-code>"
        for i, (body, text) in enumerate(BODY_TEXT_CASES)
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", f"<h2>Plan</h2>\n{blocks}")
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_the_collapse_class_is_one_set_on_both_sides():
    """COLLAPSE_CHARS (the file side) and the passage reader's COLLAPSE regex
    (the browser side) are two spellings of one set, and everything quote-shaped
    rests on their agreement: a character one side collapses and the other keeps
    is a quote captured in the browser that the file's reading can never confirm.
    The next edit to either spelling meets this test, not a detached comment."""
    js = (schema_model.ASSETS / "runtime" / "collapse.js").read_text()
    found = re.search(r"const COLLAPSE =\n\s*/\[(.*?)\]\+/g;", js)
    assert found, "the browser passage reader lost its COLLAPSE regex"
    js_class = re.compile(f"[{found.group(1)}]")
    js_set = {chr(c) for c in range(0x10000) if js_class.match(chr(c))}
    assert js_set == passages_model.COLLAPSE_CHARS


def _runtime_modules():
    """Every module the runtime is composed of, whichever file each fact lives in today.

    Named as a set rather than as paths because the runtime is being split by owner: a
    reading that names one file goes red on the split that moves the thing it reads,
    which says the fact changed when what changed is where it is written."""
    return [schema_model.ASSETS / "leaf.js"] + sorted(
        (schema_model.ASSETS / "runtime").rglob("*.js")
    )


def _without_comments(js: str) -> str:
    """A module's code with its comments taken out.

    The sibling reading below strips them for the reason that applies here too: a
    pattern simple enough to find a definition is simple enough for a comment to
    satisfy. `re.search` takes the first match in a file, so a commented-out copy above
    the real one is read instead of it, and the test then holds Python to a sentence
    while the constant it names drifts — green, and about nothing. Across files the same
    comment reads as a second module stating the fact, which is a red naming the wrong
    one.

    The line-comment pattern steps over `://` so a URL in a string keeps its second
    half; nothing here reads a URL, and a `//` inside a string is left alone at the cost
    of nothing this asks."""
    return re.sub(r"(?<!:)//[^\n]*", "", re.sub(r"/\*.*?\*/", "", js, flags=re.DOTALL))


def _sole_definition(pattern: str, what: str):
    """The one runtime module matching `pattern`, and the match — so a fact that grows a
    second spelling is caught here rather than by whichever side happened to be read."""
    found = [
        (js, m)
        for js in _runtime_modules()
        if (m := re.search(pattern, _without_comments(js.read_text())))
    ]
    assert len(found) == 1, (
        f"{len(found)} runtime modules state {what} ({[js.name for js, _ in found]}), "
        "and this reading asks one of them"
    )
    return found[0]


def test_the_block_a_text_node_sits_in_is_one_list_on_both_sides():
    """TEXT_BLOCK_TAGS (the file side) and the passage reader's TEXT_BLOCK selector are
    two spellings of one list, and the collapsed reading of a page rests on their
    agreement: one space goes wherever two runs of text sit in different blocks and none
    where they share one, so a tag one side calls a block and the other does not gives
    the two sides different text. Every quote-shaped thing is then a quote the browser
    captured that the file's reading cannot confirm, or the reverse.

    The Python comment already said the list matches the runtime's. A comment saying so
    is not a thing that fails when it stops being true; this is."""
    _, found = _sole_definition(
        r"const TEXT_BLOCK =\s*\n?\s*\"([^\"]+)\";", "TEXT_BLOCK"
    )
    assert set(found.group(1).split(",")) == passages_model.TEXT_BLOCK_TAGS


def test_anchor_capture_starts_with_the_same_context_on_both_sides():
    """Unique quotes share the initial width; repeated browser selections may grow it.

    File capture requires a unique quote. The browser knows which occurrence the user
    selected, so it widens context to identify that span, up to semantic fences.
    """
    _, found = _sole_definition(r"const CONTEXT = (\d+);", "the captured context width")
    assert int(found.group(1)) == anchor_capture_model.CONTEXT


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
    for path in (Path(__file__).parent.parent / "examples").glob("*.html"):
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


def test_a_tone_the_layer_cannot_paint_is_refused_where_the_author_can_still_fix_it(
    page_dir,
):
    """The same failure a misspelt language has, and caught for the same reason: a
    tone nothing matches paints nothing, so the column renders neutral on a page that
    otherwise looks perfectly well. The user cannot see it — they never knew it
    was meant to be red — so the only party who can still fix it is whoever wrote
    the word, and the lint is where they are told. This is the whole difference
    between the attribute and a class, which nothing checks.

    Every widget taking a tone reads it from the one list."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            '<lf-board id="board"><lf-column id="blocked" label="Blocked"'
            ' tone="dangre"></lf-column></lf-board></section>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    output = result.output.replace('"', "'")
    refused = [
        line
        for line in output.splitlines()
        if "not a tone this page's layer paints" in line
    ]
    assert len(refused) == 1
    assert any("<lf-column" in line for line in refused)
    assert "'ok', 'warn', 'danger'" in output

    # The list is the layer's, so a layer that adds one accepts it with no widget
    # touched — which is the point of $tones over an enum on each widget.
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$tones"]["names"].append("dangre")
    (page_dir / "registry.json").write_text(json.dumps(registry))
    assert check(page_dir).exit_code == 0


def test_a_member_is_admissible_in_each_declared_owner(page_dir):
    """A package member can belong to different families without validator changes."""
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-label"] = {
        "description": "A package's shared label.",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": False,
        "x-owners": ["lf-option", "lf-card"],
    }
    registry_path.write_text(json.dumps(registry))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<lf-board id="labels"><lf-column id="labels-column" label="Ideas">'
            '<lf-card id="labels-card"><lf-label>cheap</lf-label>A</lf-card>'
            "</lf-column></lf-board><lf-options>",
        ).replace(
            '<lf-option id="flag-first">',
            '<lf-option id="flag-first"><lf-label>small</lf-label>',
        )
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output

    # And refused where neither holder is its parent, naming both.
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2><lf-label>stray</lf-label>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "must be a direct member of <lf-option> or <lf-card>" in result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert "<lf-zone> (line" in result.output, result.output
    assert "x-reading-role pane must contain exactly one direct body element" in (
        result.output
    )


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert "x-reading-role pane direct <header> must be first" in result.output
    body = "x-reading-role pane must contain exactly one direct body element"
    # The split body and the loose text, each named by its own line.
    for line in (11, 12):
        assert f"<lf-pane> (line {line}): {body}" in result.output, result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<lf-code language="python">' in result.output, result.output


def test_check_rejects_loose_content_in_items_container(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", "<lf-options>\nloose text\n<p>stray</p>\n<br/>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert 'admits only ["lf-option"] members' in result.output
    assert '"br"' in result.output  # self-closed strays count as children too
    assert "loose text" in result.output


def test_flag_attribute_accepts_both_html_spellings(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first">', 'id="backfill-first" chosen="">')
    )
    assert check(page_dir).exit_code == 0
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first">', 'id="backfill-first" chosen="yes">')
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert 'is not of type "boolean"' in result.output


def test_retired_question_and_recommendation_attributes_are_rejected(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options label="Which plan?">').replace(
            'id="backfill-first">', 'id="backfill-first" recommended>'
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "Additional properties are not allowed" in result.output
    assert "'label' was unexpected" in result.output
    assert "'recommended' was unexpected" in result.output


def test_tabs_validate_and_compose(page_dir):
    tabs = """<lf-tabs id="ws">
  <lf-tab id="ws-ingest" label="Ingest"><p>Pipeline notes.</p></lf-tab>
  <lf-tab id="ws-search" label="Search">
    <dl id="k-lat" class="panel"><dt></dt><dd><strong>118 ms</strong></dd></dl>
  </lf-tab>
</lf-tabs>
<lf-options>"""
    (page_dir / "index.html").write_text(PAGE.replace("<lf-options>", tabs))
    result = check(page_dir)
    assert result.exit_code == 0, result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert "'label' is a required property" in result.output
    assert "must be a direct member of <lf-tabs>" in result.output
    assert "loose text" in result.output


def test_suggestion_validates(page_dir):
    suggest(page_dir)
    assert check(page_dir).exit_code == 0, check(page_dir).output


def test_suggestion_rejects_malformed_shapes(page_dir):
    for markup, expected in [
        ('<lf-suggestion id="sug-a"></lf-suggestion><lf-options>', "needs a <lf-old>"),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new><p>x</p></lf-new>'
                "<lf-new><p>y</p></lf-new></lf-suggestion><lf-options>"
            ),
            "one at most",
        ),
        (
            (
                '<lf-suggestion id="sug-a"><lf-new>'
                '<lf-suggestion id="sug-b"><lf-new>x</lf-new></lf-suggestion>'
                "</lf-new></lf-suggestion><lf-options>"
            ),
            "don't nest",
        ),
        (
            "<lf-old><p>orphan</p></lf-old><lf-options>",
            "must be a direct member of <lf-suggestion>",
        ),
        (
            (
                '<lf-suggestion id="sug-a" resolves="nosuch"><lf-new><p>x</p></lf-new>'
                "</lf-suggestion><lf-options>"
            ),
            "names no thread in this document",
        ),
    ]:
        (page_dir / "index.html").write_text(PAGE.replace("<lf-options>", markup))
        result = check(page_dir)
        assert result.exit_code == 1, markup
        assert expected in result.output, f"{markup}\n{result.output}"


def test_suggestion_resolves_accepts_a_real_comment(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    markup = '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p>x</p></lf-new></lf-suggestion>'
    (page_dir / "index.html").write_text(before_choice(PAGE, markup))
    assert check(page_dir).exit_code == 0


def test_suggestion_resolves_a_thread_whose_opening_comment_was_lost(page_dir):
    """`resolves` names a thread by its id, which is the page state's `threads[].id`.
    A torn line can lose the comment that opened a thread while its reply survives,
    and the thread keeps the lost comment's id, so the suggestion an agent writes
    from that id validates."""
    append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "agent", "parent": "c0ffee", "text": "kept"},
    )
    markup = '<lf-suggestion id="sug-a" resolves="c0ffee"><lf-new><p>x</p></lf-new></lf-suggestion>'
    (page_dir / "index.html").write_text(before_choice(PAGE, markup))
    assert check(page_dir).exit_code == 0, check(page_dir).output


def test_revising_suggestion_markup_preserves_its_recorded_answer(page_dir):
    # v2 honors the accept: the old paragraph and the wrapper are gone, the
    # proposal inlined. Nothing but a logged accept makes that legal.
    suggest(page_dir)
    honored = PAGE.replace(
        "<lf-options>",
        '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
    )
    (page_dir / "index.html").write_text(honored)
    result = check(page_dir)
    assert result.exit_code == 0, result.output

    decide(page_dir, "accept")
    assert check(page_dir).exit_code == 0, check(page_dir).output


def test_the_live_source_can_honor_the_latest_revision_decision(page_dir):
    """Source checking is about the next live revision, not a historical stamp."""
    suggest(page_dir)
    (page_dir / "index.html").write_text(
        (page_dir / "index.html")
        .read_text()
        .replace("<title>t</title>", "<title>t · v2</title>")
    )
    publish(page_dir, 2)
    (page_dir / "index.html").write_text(
        before_choice(
            PAGE.replace("<title>t</title>", "<title>t · v3</title>"), SUGGESTION
        )
    )
    publish(page_dir, 3)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 3,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )

    # Once staged as index.html, these bytes are a new live revision after r3;
    # the standing decision on r3 therefore licenses the honoring rewrite.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_an_unanswered_proposal_may_become_authored_content(page_dir):
    # Self-accepting: the wrapper goes but its proposal stays, presented as
    # ordinary prose the user never agreed to. Withdrawal is whole or not.
    insert = """<lf-suggestion id="sug-thistle">
  <lf-new><p id="thistle-plan">Switch the north feeder to thistle in autumn.</p></lf-new>
</lf-suggestion>
    """
    suggest(page_dir, markup=insert)
    kept = PAGE.replace(
        "<lf-options>",
        '<p id="thistle-plan">Switch the north feeder to thistle in autumn.</p><lf-options>',
    )
    (page_dir / "index.html").write_text(kept)
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    # Source checks do not publish. Removing or incorporating the same authored
    # proposal remains allowed before and after its explicit answer.
    (page_dir / "index.html").write_text(PAGE)
    assert check(page_dir).exit_code == 0
    decide(page_dir, "accept", widget="sug-thistle")
    (page_dir / "index.html").write_text(kept)
    assert check(page_dir).exit_code == 0


def test_retiring_suggestion_markup_is_independent_of_its_answer(page_dir):
    # A reject is consent to drop the proposal, so it retires even while a
    # thread about it is open — the user has already answered.
    suggest(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "cameras aren't reliable yet",
        },
    )
    assert check(page_dir).exit_code == 0
    decide(page_dir, "reject")
    assert check(page_dir).exit_code == 0
    # The answer does not prohibit a later edit of either authored slot.
    (page_dir / "index.html").write_text(PAGE)
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_an_unanswered_deletion_may_leave_the_page(page_dir):
    # The mirror of self-accepting an insertion: dropping the markup a pending
    # deletion wraps, without the accept that consents to losing it.
    delete = """<lf-suggestion id="sug-drop">
  <lf-old><p id="hand-log">The manual sightings log.</p></lf-old>
</lf-suggestion>
"""
    suggest(page_dir, markup=delete)
    (page_dir / "index.html").write_text(PAGE)
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    decide(page_dir, "accept", widget="sug-drop")
    assert check(page_dir).exit_code == 0


def test_withdrawing_an_unanswered_suggestion_needs_no_consent(page_dir):
    # Nothing was decided, so Claude may take the proposal back — but not while
    # an unresolved thread is anchored in it.
    suggest(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    assert check(page_dir).exit_code == 0
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "why the camera?",
        },
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c1"}
    )
    assert check(page_dir).exit_code == 0


def test_reply_refuses_a_suggestion(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
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
        ["response", "reply", response_reference(page_dir, "c1"), "--text", "Updated."],
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
        ["response", "reply", response_reference(page_dir, "c1"), "--text", "Updated."],
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
        ["response", "reply", "--text", "Updated."],
    )
    assert ambiguous.exit_code != 0
    assert "Missing argument" in ambiguous.output
    assert files_model.list_revisions(page_dir) == [1]

    selected = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", response_reference(page_dir, "c2"), "--text", "Updated."],
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
        ["response", "reply", reference, "--text", "Made it blue."],
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
        ["response", "reply", reference, "--text", "Updated."],
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
        page.close_turn(claim["id"], claim["turn"])

    result = CliRunner().invoke(
        cli_model.cli,
        ["response", "reply", response_reference(page_dir, "c1"), "--text", "Updated."],
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
    with pytest.raises(SystemExit) as refused:
        thread_model.post_reply(
            page_dir,
            "c1",
            "Answered.",
            "",
            for_event=None,
            attempt="r1",
        )
    assert "'r1' does not match" in str(refused.value)

    with pytest.raises(SystemExit) as unknown_widget:
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
            "public layer entry point",
        ),
        (
            '<link rel="stylesheet" href="/theme.css" media="print">',
            "escapes /page/ and /media/",
        ),
        ('<base href="https://outside.example/">', "<base> (line"),
        (
            '<meta http-equiv="Content-Security-Policy" content="default-src none">',
            "<meta> (line",
        ),
        ('<script type="importmap">{"imports": {}}</script>', "<script> (line"),
    ],
    ids=["runtime-module", "theme", "base", "policy", "import-map"],
)
def test_check_rejects_authored_delivery_assets(page_dir, asset, expected):
    (page_dir / "index.html").write_text(PAGE.replace("</head>", f"{asset}\n</head>"))

    result = check(page_dir)

    assert result.exit_code == 1
    assert expected in result.output


def test_check_rejects_inline_importance_over_the_presentation_boundary(page_dir):
    """Inline importance outranks stylesheet layers, so the authoring door owns it."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<main>", '<main style="visibility: visible !important">')
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "protected presentation property visibility important" in result.output


@pytest.mark.parametrize(
    "outside",
    [
        "Authored tail",
        '<p id="tail">Authored tail</p>',
        '<lf-options><lf-option id="tail">Authored tail</lf-option></lf-options>',
        '<main><p id="tail">Second main</p></main>',
    ],
)
def test_check_confines_authored_content_to_one_direct_main(page_dir, outside):
    """The element the presentation boundary withholds contains the whole page.

    Prose, ordinary elements, widgets, and another main beside the first are all
    visible outside the CSS gate and must be refused at the authoring door.
    """
    (page_dir / "index.html").write_text(PAGE.replace("</main>", f"</main>\n{outside}"))

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_requires_main_to_be_a_direct_body_child(page_dir):
    """A main nested in an authored wrapper is not selected by `body > main`."""
    wrapped = PAGE.replace("<main>", "<div>\n<main>").replace(
        "</main>", "</main>\n</div>"
    )
    (page_dir / "index.html").write_text(wrapped)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_requires_an_explicit_head_for_delivery(page_dir):
    """Delivery has one validated insertion point for its generated head."""
    source = PAGE.replace("<head>", "").replace("</head>", "")
    (page_dir / "index.html").write_text(source)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one explicit <head> directly under <html>" in result.output


def test_check_rejects_an_extra_head_that_html_recovery_ignores(page_dir):
    """The source contract counts tags the recovered browser tree discards."""
    source = PAGE.replace("</html>", "<head></head></html>")
    (page_dir / "index.html").write_text(source)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "found 2 head tags" in result.output


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

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_owns_the_lf_meta_vocabulary(page_dir):
    # The sign-off declaration: valid on its one value, rejected on a misspelled
    # value or name — either would silently declare nothing in the browser.
    signoff = PAGE.replace(
        "<title>t</title>",
        '<title>t</title>\n<meta name="lf-review" content="sign-off">',
    )
    (page_dir / "index.html").write_text(signoff)
    assert check(page_dir).exit_code == 0

    (page_dir / "index.html").write_text(signoff.replace("sign-off", "approve"))
    result = check(page_dir)
    assert result.exit_code == 1
    assert "content must be one of [\"sign-off\"], found 'approve'" in result.output

    (page_dir / "index.html").write_text(signoff.replace("lf-review", "lf-signoff"))
    result = check(page_dir)
    assert result.exit_code == 1
    assert "unknown lf- meta" in result.output
    assert "lf-review" in result.output  # the error names the known vocabulary


def test_check_leaves_the_pages_own_address_to_delivery(page_dir):
    """An authored canonical is not an extra hint; it is a competing answer.

    The served document names the page root at every address the page answers, so a
    second one in the head leaves a crawler choosing, and the usual outcome is that it
    honours neither. The words a page owes a search result are its title and
    description, which it writes; the address is the server's.
    """
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<title>t</title>",
            '<title>t</title>\n<link rel="canonical" href="https://example.com/p">',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "the served document names the page root itself" in result.output


def test_check_rejects_duplicate_ids(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="flag-first"')
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "duplicate ids" in result.output


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
    result = check(page_dir)
    assert result.exit_code == 1
    assert "whitespace" in result.output and '"layout-no class"' in result.output


def test_unreferenced_ids_and_widget_items_may_leave_the_page(page_dir):
    publish(page_dir)
    without_item = PAGE.replace(
        '      <lf-option id="backfill-first"><small class="tag">effort: med</small><small class="tag">risk: low</small>\n'
        "        <strong>Backfill first</strong> Verify, then flip. <em>My take: do this first.</em>\n"
        "      </lf-option>\n",
        "",
    )
    (page_dir / "index.html").write_text(
        without_item.replace('<section id="plan">', "<section>")
    )

    result = check(page_dir)

    assert result.exit_code == 0, result.output
    assert 'ids dropped from revision r1: ["backfill-first", "plan"]' in result.output


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
    opened_task = runner.invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), "t-ask", "Weigh it"],
    )
    assert opened_task.exit_code == 0, opened_task.output
    assert json.loads(opened_task.output)["subject"] == {
        "kind": "thread",
        "id": opened["id"],
    }

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


def test_an_answered_ask_moves_into_a_collapsed_section_with_its_pick_standing(
    page_dir,
):
    """The route `authoring-revisions.md` gives finished work: the answered Ask goes
    to a collapsed section whole, under the words the user picked it under."""
    live = OPTIONS.format(a="", b="", chip="", shim="Keep the old API.", stage="Two.")
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + live)
    )
    publish(page_dir)
    append_command(
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

    def complete(ask):
        return PAGE.replace(
            "</section>\n</main>",
            '</section>\n<section id="complete"><h2>Complete</h2><details>'
            f"<summary>Migration order chosen</summary>{ask}</details></section>\n</main>",
        )

    settled = live.replace('id="g1" choose', 'id="g1" choose settled')
    (page_dir / "index.html").write_text(complete(settled))
    moved = check(page_dir)
    assert moved.exit_code == 0, moved.output

    (page_dir / "index.html").write_text(
        complete(settled.replace("Keep the old API.", "Merged: keep the old API."))
    )
    reworded = check(page_dir)
    assert reworded.exit_code == 0, reworded.output


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


def test_publishing_records_typed_settlements_for_provisional_agent_facts(page_dir):
    """One durable relation ends both kinds of provisional agent information.
    Its typed targets keep report-event ids and widget-work ids distinct without
    growing one note field for each channel."""

    def add_board() -> None:
        path = page_dir / "index.html"
        path.write_text(
            path.read_text().replace(
                '<lf-diagram id="flow">',
                '<lf-board id="rollout"><lf-column id="now" label="Now">'
                '<lf-card id="rollout-card"><strong>Ship</strong></lf-card>'
                '</lf-column></lf-board><lf-diagram id="flow">',
            )
        )

    _tasks_version(page_dir, "active")
    add_board()
    assert stamp(page_dir, "cut").exit_code == 0
    sent = _report(page_dir, "t-parser", "status", "value=review")
    assert sent.exit_code == 0
    report_id = json.loads(sent.output)["id"]
    opened = CliRunner().invoke(
        cli_model.cli,
        ["task", "open", str(page_dir), "rollout-card", "Check the rollout"],
    )
    assert opened.exit_code == 0, opened.output
    task = json.loads(opened.output)

    _tasks_version(page_dir, "review")
    add_board()
    published = stamp(page_dir, "absorb", completes=("rollout-card",))
    assert published.exit_code == 0, published.output
    note = [e for e in events_model.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["settles"] == [
        {"kind": "report", "id": report_id},
        {"kind": "task", "id": task["id"]},
    ]

    # The report ended at v2, so v3 owes it nothing.
    _tasks_version(page_dir, "done")
    add_board()
    assert check(page_dir).exit_code == 0

    # Carrying an explicit transition attribute forward does not block edits.
    _tasks_version(page_dir, "done", " overruled")
    stale = check(page_dir)
    assert stale.exit_code == 0, stale.output

    # Reusing older source creates a new revision and the next public stamp. If
    # those current bytes state the reported value, that new stamp absorbs it.
    sent = _report(page_dir, "t-parser", "status", "value=review")
    assert sent.exit_code == 0, sent.output
    future_report = json.loads(sent.output)["id"]
    _tasks_version(page_dir, "review")
    add_board()
    old_cut = page_dir / "index.html"
    old_cut.write_text(
        old_cut.read_text().replace("<title>t</title>", "<title>t · reissued</title>")
    )
    republished = stamp(page_dir, "reissued old cut")
    assert republished.exit_code == 0, republished.output
    note = [e for e in events_model.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["version"] == 3
    assert {"kind": "report", "id": future_report} in note.get("settles", [])


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


def test_absorption_is_by_id_never_inferred_from_markup(page_dir):
    """Editing a report's target preserves its recorded news until settlement."""
    _tasks_version(page_dir, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "value=review").exit_code == 0
    _tasks_version(page_dir, "review")
    publish(page_dir, version=2)
    _tasks_version(page_dir, "done")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert state_json(page_dir)["updates"][0]["disposition"] == "effective"


def test_user_added_words_do_not_become_liveness_coordinates(page_dir):
    """Prose that spells a sibling id remains prose.

    An ``add`` names its option by id and carries its words beside it. Rewriting the
    unrelated option whose id those words happen to spell must therefore remain legal.
    """
    added = "g1-option-user-route"

    def write(shim):
        opts = OPTIONS.format(
            a="",
            b=" chosen",
            chip="",
            shim=shim,
            stage="Table by table.",
        ).replace(
            "</lf-options>",
            f'<lf-option id="{added}">o-shim</lf-option></lf-options>',
        )
        (page_dir / "index.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    # The generated option is absent from the action's authored revision.
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "add",
            "detail": {"option": added, "text": "o-shim"},
        },
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"value": ["o-stage"]},
        },
    )

    write("The shim now has a bounded removal date.")
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_user_state_survives_without_source_copying(page_dir):
    """An unchanged authored choice needs no transcription into a later revision.
    Validation stays quiet while state and the transcript preserve the answer."""

    def write(a=""):
        opts = OPTIONS.format(
            a=a, b="", chip="", shim="Fastest to ship.", stage="Table by table."
        )
        (page_dir / "index.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write()
    publish(page_dir)
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
    write()
    result = check(page_dir)
    assert result.exit_code == 0
    assert "record behind the log" not in result.output
    state = state_json(page_dir)
    assert state["state"][0]["detail"] == {"value": ["o-shim"]}
    assert asks_on_you(state) == []

    # Explicit incorporation is permitted but unnecessary for correctness.
    write(a=" chosen")
    result = check(page_dir)
    assert result.exit_code == 0
    assert "record behind the log" not in result.output

    result = CliRunner().invoke(cli_model.cli, ["page", "transcript", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert "record behind the log" not in result.output
    assert "g1" in result.output and "o-shim" in result.output


def test_check_reports_a_measurement_whose_source_ran_again(page_dir):
    """A version keeps the scalar it stated; the replaceable source contributes only
    evidence that its measurement ran later. The same generic reading appears as
    passing check advice and structured page state, and disappears once the authored
    capture instant catches up."""

    def write(at):
        measured = (
            '<p>The import takes <lf-num id="p95" source="import-latency" '
            f'at="{at}" via="uv run bench-import">184 ms</lf-num> at p95.</p>'
        )
        html = PAGE.replace("</main>", measured + "\n</main>")
        (page_dir / "index.html").write_text(html)
        return html[: html.index("<lf-num")].count("\n") + 1

    captured = "2026-08-01T12:00:00Z"
    captured_line = write(captured)
    runner = CliRunner()
    set_result = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "import-latency"],
        input="184",
    )
    assert set_result.exit_code == 0, set_result.output
    updated = read_page_data(page_dir)["sources"]["import-latency"]["updated"]

    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "measurement behind its source" in result.output
    assert "import-latency" in result.output
    assert captured in result.output and updated in result.output
    assert state_json(page_dir)["measurement_lag"] == [
        {
            "tag": "lf-num",
            "widget": "p95",
            "line": captured_line,
            "source": "import-latency",
            "at": captured,
            "updated": updated,
        }
    ]

    rejected = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "import-latency"],
        input='{"value": 183}',
    )
    assert rejected.exit_code != 0
    assert "value is invalid" in rejected.output

    write(updated)
    current = check(page_dir)
    assert current.exit_code == 0, current.output
    assert "measurement behind its source" not in current.output
    assert state_json(page_dir)["measurement_lag"] == []

    write("yesterday")
    malformed = check(page_dir)
    assert malformed.exit_code != 0
    assert "is not a 'date-time'" in malformed.output


def test_file_state_scopes_a_nested_pick_to_its_nearest_recorded_owner(page_dir):
    """The file-side record is the runtime's same ownership reading. An inner chosen
    option is not part of the outer group's record; a nested decision does not
    change the outer user choice."""
    nested = """<lf-ask id="outer-decision"><h3>Which outer choices?</h3>
  <lf-options id="outer" choose multiple>
    <lf-option id="outer-a" chosen><strong>Outer A</strong>
      <lf-ask id="inner-decision"><h4>Which inner choice?</h4>
        <lf-options id="inner" choose>
          <lf-option id="inner-a" chosen>Inner A</lf-option>
          <lf-option id="inner-b">Inner B</lf-option>
        </lf-options>
      </lf-ask>
    </lf-option>
    <lf-option id="outer-b"><strong>Outer B</strong></lf-option>
  </lf-options>
</lf-ask>"""
    html = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + nested)
    (page_dir / "index.html").write_text(html)
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "outer",
            "action": "choose",
            "detail": {"value": ["outer-a"]},
        },
    )

    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "record behind the log" not in result.output


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
    assert asks_on_you(state) == [
        {
            "id": "g1-decision",
            "tag": "lf-ask",
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
    assert asks_on_you(state) == []
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
        "revision": hashlib.sha256(stored.read_bytes()).hexdigest()[:16],
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
            "key": "app.py",
            "path": "app.py",
            "kind": "patch",
            "additions": 1,
            "deletions": 1,
        },
        {
            "key": "new.py",
            "path": "new.py",
            "previousPath": "old.py",
            "kind": "patch",
            "additions": 1,
            "deletions": 1,
        },
        {
            "key": "docs/new.md",
            "path": "docs/new.md",
            "previousPath": "docs/old.md",
            "kind": "rename",
            "additions": 0,
            "deletions": 0,
        },
        {
            "key": "café2026 notes.py",
            "path": "café2026 notes.py",
            "kind": "patch",
            "additions": 1,
            "deletions": 1,
        },
        {
            "key": "src/second file.py",
            "path": "src/second file.py",
            "kind": "patch",
            "additions": 1,
            "deletions": 1,
        },
    ]
    assert all(
        file["patch"].startswith("diff --git ") for file in source["value"]["files"]
    )


@pytest.mark.parametrize("escaped", [r"bad\x41.py", r"bad\400.py", r"bad\q.py"])
def test_unified_diff_rejects_c_escapes_git_does_not_use(escaped):
    patch = f"""diff --git "a/{escaped}" "b/{escaped}"
--- "a/{escaped}"
+++ "b/{escaped}"
@@ -1 +1 @@
-old
+new
"""

    with pytest.raises(ValueError, match="invalid quoted Git path"):
        patch_manifest(patch)


@pytest.mark.parametrize(
    ("patch_text", "message"),
    [
        (
            """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
--- a/old.py
+++ b/new.py
-before
+after
""",
            "unsupported hunkless diff",
        ),
        (
            """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-before
+after
+lost
""",
            "hunk line counts",
        ),
        (
            """diff --git a/app.py b/app.py
@@ -1 +1 @@
--- bogus-old
+++ bogus-new
""",
            "no ---/+++ file-header pair before its first hunk",
        ),
        (
            """diff --git a/app.py b/app.py
--- a/other.py
+++ b/other.py
@@ -1 +1 @@
-before
+after
""",
            "---/+++ paths disagree",
        ),
    ],
)
def test_the_diff_script_refuses_evidence_the_widget_cannot_render(patch_text, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        patch_manifest(patch_text)


def test_data_set_names_the_producer_when_nothing_arrives(page_dir, tmp_path):
    """A producer that refuses its input writes nothing, and `data set` downstream
    of it says so, pointing back at the producer's error rather than adding a JSON
    parse error of its own. Nothing is stored."""
    declare_data_input(page_dir, "builds", {"type": "object"}, contract="build-map")
    empty = tmp_path / "builds.json"
    empty.write_text("\n")

    piped = CliRunner().invoke(
        cli_model.cli, ["data", "set", str(page_dir), "builds"], input=""
    )
    filed = CliRunner().invoke(
        cli_model.cli, ["data", "set", str(page_dir), "builds", "--file", str(empty)]
    )

    assert piped.exit_code == 1
    assert piped.output == (
        "Error: no value arrived on stdin; if a command piped into this one, it "
        "likely failed, and its error above says why\n"
    )
    assert filed.exit_code == 1
    assert f"{empty} is empty" in filed.output
    assert "builds" not in read_page_data(page_dir)["sources"]


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
    # The printed instant is the one an author pins in `at`, so it is the stored one;
    # the value is the writer's own, so it does not come back.
    assert json.loads(result.output) == {
        "source": "builds",
        **{key: source[key] for key in ("contract", "revision", "updated")},
    }
    assert source["value"] == {"main": "passing"}
    assert json.loads(data_model.source_file(page_dir, "builds").read_text()) == {
        "main": "passing"
    }


def test_a_page_source_can_be_shared_but_needs_one_simultaneous_contract(page_dir):
    """One document cannot tell two consuming widgets to read different contracts
    from the same current source value."""
    declare_data_input(
        page_dir,
        "project-feed",
        {"type": "array"},
        contract="rows",
    )
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-test-data id="test-data-two" source="project-feed"></lf-test-data>\n'
            "</main>",
        )
    )
    data_model.cmd_data_set(page_dir, "project-feed", [])

    shared = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert shared.exit_code == 0, shared.output

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
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-other-data id="other-data" source="project-feed"></lf-other-data>\n'
            "</main>",
        )
    )

    conflict = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert conflict.exit_code != 0
    assert "bound to both contract 'rows'" in conflict.output
    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state.exit_code == 0, state.output
    reading = json.loads(state.output)
    assert reading["source"]["file"] == "index.html"
    assert reading["source"]["live"] is False
    assert "bound to both contract 'rows'" in reading["source"]["error"]
    assert reading["active"]["revision"] == 1


@pytest.mark.parametrize("clear", [False, True])
def test_a_later_version_can_reuse_a_source(page_dir, clear):
    """A changed binding replaces the index's contract and value in one write.
    Captured old versions retain their own declaration and cannot accept new payloads.
    """
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
    publish(page_dir)
    data_model.cmd_data_set(page_dir, "project-feed", [])
    if clear:
        data_model.cmd_data_clear(page_dir, "project-feed")

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
    first = (page_dir / "index.html").read_text()
    (page_dir / "index.html").write_text(first.replace("lf-test-data", "lf-other-data"))

    result = check(page_dir)
    assert result.exit_code == 0, result.output
    old_registry = data_contracts_model.read_revision(page_dir, 1).registry
    with pytest.raises(data_model.DataError, match="value is invalid"):
        data_model.cmd_data_set(page_dir, "project-feed", [])
    assert data_model.read_contracts(page_dir) == {"project-feed": "rows"}
    stored = data_model.source_file(page_dir, "project-feed")
    assert not stored.exists() if clear else json.loads(stored.read_text()) == []
    data_model.cmd_data_set(page_dir, "project-feed", {"ready": True})
    assert data_model.read_contracts(page_dir) == {"project-feed": "other-rows"}
    assert read_page_data(page_dir)["sources"]["project-feed"]["value"] == {
        "ready": True
    }
    historical = data_model.read_data(page_dir, old_registry)["sources"]["project-feed"]
    assert "error" in historical and "value" not in historical
    publish(page_dir, version=2)
    assert (
        state_json(page_dir)["data_bindings"]["project-feed"]["contract"]
        == "other-rows"
    )


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
        "data-question",
        "Here it is.",
        '<lf-test-data id="reply-data" source="reply-feed"></lf-test-data>',
        for_event="data-question",
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
        "data-question",
        "Here it is.",
        '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>',
        for_event="data-question",
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
    thread_bindings, _seats, errors = data_contracts_model.declared_data_bindings(
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
        "draft-data-question",
        "Here it is.",
        '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>',
        for_event="draft-data-question",
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
    data_model.source_file(page_dir, "loop").write_text("{}")
    assert read_page_data(page_dir)["sources"]["loop"]["error"] == (
        "source 'loop' contract 'loop' could not validate its value: "
        "a recursive reference did not terminate"
    )


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        ("null", "data must be an object with only sources"),
        ('{"revision":1,"sources":{}}', "data must be an object with only sources"),
        (
            '{"sources":{"builds":{"contract":"Bad Contract"}}}',
            "source 'builds' must record only a contract",
        ),
        (
            '{"sources":{"builds":{"contract":"build-map","revision":1}}}',
            "source 'builds' must record only a contract",
        ),
    ],
)
def test_the_contract_index_refuses_anything_but_contracts(page_dir, stored, message):
    """data.json records only which contract each source id was bound to."""
    (page_dir / "data.json").write_text(stored)

    with pytest.raises(data_contracts_model.DataError, match=message):
        read_page_data(page_dir)


def test_the_contract_index_wraps_invalid_utf8_at_its_boundary(page_dir):
    (page_dir / "data.json").write_bytes(b"\xff")

    with pytest.raises(data_contracts_model.DataError, match="invalid JSON"):
        read_page_data(page_dir)


@pytest.mark.parametrize(
    ("value", "message"), [(b"\xff", "is not JSON"), (b"[NaN]", "NaN is not JSON")]
)
def test_a_value_file_that_is_not_json_reads_as_that_sources_error(
    page_dir, value, message
):
    """Python's JSON reader admits `NaN`, which no browser can parse, and a value
    file is anyone's to write, so each reading refuses what JSON cannot carry."""
    declare_data_input(page_dir, "builds", {"type": "array"}, contract="build-map")
    data_model.cmd_data_set(page_dir, "builds", [])
    data_model.source_file(page_dir, "builds").write_bytes(value)

    source = read_page_data(page_dir)["sources"]["builds"]
    assert "value" not in source
    assert message in source["error"]


def test_page_state_names_the_ask_region_but_keeps_state_on_its_request(page_dir):
    """The Ask list names the whole reading the user arrives at. Its nested
    request remains the action owner, so answering it closes the broader Ask without
    moving the standing Ask onto a wrapper that declares no state."""
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
    assert asks_on_you(state) == [
        {
            "id": "plan-decision",
            "tag": "lf-ask",
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
    assert asks_on_you(state) == []
    assert state["state"][0]["widget"] == "g1"


def test_page_state_reads_an_authored_answer_with_no_log(page_dir):
    """A version that honors a pick in its markup reads as answered with no log
    at all — the shipped examples arrive that way."""
    opts = OPTIONS.format(a=" chosen", b="", chip="", shim="s.", stage="t.")
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    assert asks_on_you(state_json(page_dir)) == []


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
    assert asks_on_you(state_json(page_dir)) == [
        {
            "id": "gm-decision",
            "tag": "lf-ask",
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
    assert asks_on_you(state_json(page_dir)) == [
        {
            "id": "gm-decision",
            "tag": "lf-ask",
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
    assert asks_on_you(state_json(page_dir)) == []


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

    assert asks_on_you(state_json(page_dir)) == [
        {
            "id": "future-decision",
            "tag": "lf-ask",
            "widget": "future-review",
            "widget_tag": "lf-options",
            "thread": None,
        },
        {
            "id": "decision-decision",
            "tag": "lf-ask",
            "widget": "decision-options",
            "widget_tag": "lf-options",
            "thread": None,
        },
    ]


def test_page_state_carries_a_report_until_a_version_answers_it(page_dir):
    """A standing report updates task status without creating user work, stands in
    the canonical update feed, and remains there as settled history when a note
    absorbs it."""
    tasks = (
        '<lf-test-tasks id="work"><lf-test-task id="t-parser" status="review">'
        "<strong>Parser</strong> Ready for eyes.</lf-test-task></lf-test-tasks>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)
    assert asks_on_you(state_json(page_dir)) == []
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
    assert asks_on_you(state) == []
    assert state["updates"] == [
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
    assert state["updates"] == [
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
    assert asks_on_you(state) == []


def test_update_feed_orders_clock_ties_by_log_causality(page_dir, monkeypatch):
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

    updates = state_json(page_dir)["updates"]
    assert [(update["source"], update["id"]) for update in updates] == [
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
    assert state["elements"] and asks_on_you(state) == []
    assert state["title"] == "t"


def test_check_advises_where_a_users_aim_has_nothing_to_land_on(page_dir):
    """A block a user points at whole needs an id, or the aim falls through to
    the enclosing section — the failure addressable-element anchoring's own page shipped. Advice
    on a passing run, not a gate, and quiet where a tight wrapper (a figure around
    a table) already gives the aim something to hold."""
    blocks = (
        "<pre><code>uv run backfill --check</code></pre>"
        '<aside class="sidenote">The retry path is deliberately separate.</aside>'
        '<figure id="fig"><table><tr><td>1</td></tr></table></figure>'
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + blocks).replace(
            "</main>", "<section><p>Unnamed aside.</p></section>\n</main>"
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    advice = [line for line in result.output.splitlines() if "unpointable" in line]
    assert len(advice) == 3, result.output
    assert any("<pre>" in line and "#plan" in line for line in advice)
    assert any("<aside>" in line and "#plan" in line for line in advice)
    assert any("<section>" in line for line in advice)
    assert not any(
        "<table>" in line for line in advice
    )  # the figure's id is aim enough

    # Ids minted, debt gone.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><pre id="cmd"><code>uv run backfill --check</code></pre>'
            '<aside class="sidenote" id="retry-note">The retry path is deliberately '
            "separate.</aside>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "unpointable" not in result.output


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
    assert asks_on_you(state_json(page_dir)) == [
        {
            "id": "real-decision",
            "tag": "lf-ask",
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
    assert asks_on_you(state_json(page_dir)) == [
        {
            "id": "cargo",
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
    assert asks_on_you(state_json(page_dir)) == []

    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            command("active", False, "ledger_id,amount\n7,42") + "</section>",
        )
    )
    publish(page_dir, 2)
    assert asks_on_you(state_json(page_dir)) == []


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
        "key": "a.py",
        "path": "a.py",
        "kind": "patch",
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


def test_a_state_read_never_materializes_a_revision_bundle(page_dir, monkeypatch):
    """One request must not re-read the whole page history to answer.

    `GET /` and `GET /api/state` both activate the source under the page's exclusive
    lock, and that validation asks every revision in the history what its own
    document and registry said. A revision bundle holds a couple of hundred resource
    files, so answering through `read_artifact` made one request cost the revision
    count times the bundle: seconds per request where the page directory is on a
    network filesystem, with every other reader queued behind the lock.

    The active revision is no exception: whether the source is that revision is a
    question for its manifest's digest, not its bundle. So each revision opens the
    files its reading asks for and no more — the document and the registry, and the
    active revision its manifest besides. Exact counts are the control: a counter
    that never saw a revision file would read zero for each.
    """
    for edit in range(12):
        (page_dir / "index.html").write_text(
            PAGE.replace("</main>", f"<p>edit {edit}</p></main>")
        )
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error
    revisions = files_model.list_revisions(page_dir)
    assert len(revisions) == 12  # more revisions than any bundle cache retains

    opens = Counter()
    native_open = Path.open

    def counted_open(self, *args, **kwargs):
        if found := re.search(r"/revisions/r([1-9][0-9]*)-", str(self)):
            opens[int(found.group(1))] += 1
        return native_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    # A server started now: it holds none of this test's readings.
    with fresh_process():
        activated = revisioning_model.activate_source(page_dir)
    monkeypatch.undo()
    assert activated.error is None, activated.error
    assert not activated.created

    *history, active = revisions
    assert opens[active] == 3
    # One document and one registry apiece: the only two resources this reading reads.
    assert {revision: opens[revision] for revision in history} == {
        revision: 2 for revision in history
    }


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

    expected = render_gate_readings._expected_verbatim(page, events, registry, here=1)

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
        markup, [event], registry, here=1
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
    "case", json.loads((Path(__file__).parent / "markdown_body_cases.json").read_text())
)
def test_markdown_body_file_words_match_the_shared_browser_dialect(case):
    from html import escape

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
        PAGE.replace(
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
    source.write_text(PAGE.replace('id="flow"', 'id="new-flow"'))
    assert stamp(page_dir, "replace drawing").exit_code == 0
    [thread] = state_json(page_dir)["threads"]
    assert thread["anchor"] is None
    assert root in events_model.read_events(page_dir)
