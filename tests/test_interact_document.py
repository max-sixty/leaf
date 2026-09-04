"""Static document, version, and page-state tests."""

import json
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    COMMAND_SUBJECTS,
    OPTIONS,
    PAGE,
    PHRASING_CONTENT,
    SHIPPED_PACKAGES,
    SUGGESTION,
    X,
    Y,
    _balanced,
    _board,
    _decided,
    _marker_for,
    _report,
    _status,
    _tasks_version,
    before_choice,
    check,
    decide,
    declare_data_input,
    fixture_version_path,
    publish,
    stage_fixture_source,
    stamp,
    state_json,
    suggest,
)
from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import conversation as conversation_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import passages as passages_model
from leaf import publishing as publishing_model
from leaf import render_checks as render_checks_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf.validation import compatibility as validation_model


def test_check_accepts_a_valid_page(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def construction_nodes(content):
    """Index the emitted construction without reading its source files again."""
    nodes = {}
    for node in content:
        if isinstance(node, dict):
            if identity := node["attrs"].get("id"):
                nodes[identity] = node
            nodes.update(construction_nodes(node["content"]))
    return nodes


def test_page_inspection_preserves_exact_reader_state_and_its_edit_routes(page_dir):
    markup = PAGE.replace(
        "</main>",
        OPTIONS.format(
            a=" chosen", b="", chip="", shim="Keep the shim.", stage="Stage it."
        )
        + '<lf-draft id="summary"><pre>Ship on Friday.</pre></lf-draft>'
        + _board([X, Y], [])
        + '<p id="explanation"><strong>Keep</strong> <em>spaces</em>.</p></main>',
    )
    fixture_version_path(page_dir, 1).write_text(markup)
    publish(page_dir)
    actions = [
        (
            "g1",
            "choose",
            {"options": ["o-reader"], "additions": {"o-reader": "Try a canary."}},
        ),
        ("summary", "edit", {"text": "  Ship after migration.\n\nKeep  two spaces.\n"}),
        ("b1", "move", {"card": "card-y", "to": "c-done", "index": 0}),
        ("b1", "move", {"card": "card-x", "to": "c-done", "index": 0}),
    ]
    for widget, action, detail in actions:
        events_model.append_event(
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
    nodes = construction_nodes(state["content"])
    draft = nodes["summary"]
    assert draft["content"] == [actions[1][2]["text"]]
    assert draft["authored"]["content"][0]["content"] == ["Ship on Friday."]
    assert draft["edit"]["override_requires"] == "restate"
    assert state["content_source"]["file"] == str(page_dir / state["active"]["file"])
    assert state["content_source"]["edit_file"] == str(page_dir / "index.html")
    assert nodes["o-reader"]["content"] == ["Try a canary."]
    assert "chosen" in nodes["o-reader"]["attrs"]
    assert nodes["o-reader"]["source"]["kind"] == "action"
    assert nodes["o-reader"]["edit"]["owner"] == "g1"
    assert "line" not in nodes["o-reader"]["source"]
    assert "chosen" in nodes["o-shim"]["authored"]["attrs"]
    assert "chosen" not in nodes["o-shim"]["attrs"]
    assert nodes["o-shim"]["authority"] == nodes["o-reader"]["authority"]
    for identity in ("g1", "o-stage"):
        assert "authored" not in nodes[identity]
        assert "authority" not in nodes[identity]
    assert [n["attrs"]["id"] for n in nodes["c-done"]["content"]] == [
        "card-x",
        "card-y",
    ]
    assert nodes["card-x"]["authored"]["placement"] == {"parent": "c-todo"}
    assert nodes["explanation"]["content"][1] == " "

    # A successor uses the emitted source address to change unrelated wording.
    # Reader state remains effective without transcribing any of it into HTML.
    target = nodes["explanation"]["edit"]
    assert target["matches_active"]
    path = Path(state["content_source"]["edit_file"])
    path.write_text(
        path.read_text().replace("<strong>Keep</strong>", "<strong>Preserve</strong>")
    )
    revised = state_json(page_dir)
    again = construction_nodes(revised["content"])
    assert revised["source"]["live"], revised["source"]["error"]
    assert again["summary"]["content"] == draft["content"]
    assert "chosen" in again["o-reader"]["attrs"]
    assert again["explanation"]["content"][0]["content"] == ["Preserve"]

    # Rejected source must not lend its lines to the still-live construction.
    path.write_text(
        "\n\n" + path.read_text().replace('id="explanation"', 'id="summary"')
    )
    rejected = state_json(page_dir)
    current = construction_nodes(rejected["content"])
    assert not rejected["source"]["live"]
    assert rejected["active"] == revised["active"]
    assert current["summary"]["content"] == draft["content"]
    assert "line" not in current["summary"]["edit"]
    assert current["summary"]["source"]["line"] == again["summary"]["source"]["line"]


def test_page_inspection_binds_current_and_captured_data_to_their_construction(
    page_dir,
):
    declare_data_input(
        page_dir,
        "builds",
        {"type": "array", "items": {"type": "string"}},
        snapshot=True,
    )
    runner = CliRunner()
    captured = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "builds", "--capture-label", "reviewed"],
        input='["passing"]',
    )
    assert captured.exit_code == 0, captured.output
    source = page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace('id="test-data"', 'id="test-data" snapshot="1"')
        .replace(
            "</main>",
            '<lf-test-data id="live-builds" source="builds"></lf-test-data></main>',
        )
    )
    state_json(page_dir)
    updated = runner.invoke(
        cli_model.cli, ["data", "set", str(page_dir), "builds"], input='["failing"]'
    )
    assert updated.exit_code == 0, updated.output
    nodes = construction_nodes(state_json(page_dir)["content"])
    pinned = nodes["test-data"]["inputs"]["data"]
    live = nodes["live-builds"]["inputs"]["data"]
    assert pinned["value"] == ["passing"]
    assert live["value"] == ["failing"]
    assert pinned["origin"]["revision"] == 1
    assert live["origin"]["revision"] == 2
    assert pinned["origin"]["data_revision"] == live["origin"]["data_revision"] == 2
    assert pinned["edit"]["pinned"] and not live["edit"]["pinned"]
    assert pinned["edit"]["source"] == "builds"
    assert pinned["edit"]["snapshot_attribute"] == "snapshot"
    assert pinned["edit"]["operation"] == "capture-and-rebind"
    assert live["edit"]["operation"] == "data set"


@pytest.mark.parametrize(
    "outcome,words",
    [("accept", "Use the new wording."), ("reject", "Keep the old wording.")],
)
def test_page_inspection_retires_idless_slots_and_reads_frozen_construction(
    page_dir, outcome, words
):
    markup = '<lf-suggestion id="wording"><lf-old>Keep the old wording.</lf-old><lf-new>Use the new wording.</lf-new></lf-suggestion>'
    fixture_version_path(page_dir, 1).write_text(
        PAGE.replace("</main>", markup + "</main>")
    )
    publish(page_dir)
    decide(page_dir, outcome, widget="wording")
    nodes = construction_nodes(state_json(page_dir)["content"])
    assert [child["content"] for child in nodes["wording"]["content"]] == [[words]]
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "Choose a route.",
            "markup": 'Before <lf-options id="frozen" choose><lf-option id="first">First</lf-option><lf-option id="second">Second</lf-option></lf-options> after.',
        },
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "frozen",
            "action": "choose",
            "detail": {"options": ["second"]},
        },
    )
    runner = CliRunner()
    result = runner.invoke(
        cli_model.cli, ["page", "state", str(page_dir), "--thread", root["id"]]
    )
    assert result.exit_code == 0, result.output
    reading = json.loads(result.output)
    assert reading["selection"] == {"kind": "thread", "id": root["id"]}
    [message] = reading["content"]
    assert message["text"] == "Choose a route."
    assert message["content"][0] == "Before "
    assert message["content"][-1] == " after."
    frozen = construction_nodes(message["content"])
    assert "chosen" in frozen["second"]["attrs"]
    assert frozen["frozen"]["edit"] == {"kind": "conversation", "thread": root["id"]}
    assert message["source"]["event"] == root["id"]
    refused = runner.invoke(
        cli_model.cli, ["page", "state", str(page_dir), "--thread", "missing"]
    )
    assert refused.exit_code != 0 and "unknown thread" in refused.output


def test_page_inspection_routes_frozen_captures_to_a_new_reply(page_dir):
    publish(page_dir)
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "The reviewed instructions and their current replacement.",
            "markup": '<lf-source id="reviewed" source="instructions" snapshot="1"></lf-source>'
            '<lf-source id="current" source="instructions"></lf-source>',
        },
    )
    data_model.cmd_data_set(page_dir, "instructions", "Reviewed wording.", "reviewed")
    data_model.cmd_data_set(page_dir, "instructions", "Current wording.")
    result = CliRunner().invoke(
        cli_model.cli, ["page", "state", str(page_dir), "--thread", root["id"]]
    )
    assert result.exit_code == 0, result.output
    [message] = json.loads(result.output)["content"]
    nodes = construction_nodes(message["content"])
    pinned = nodes["reviewed"]["inputs"]["document"]
    current = nodes["current"]["inputs"]["document"]
    assert pinned["value"] == "Reviewed wording."
    assert pinned["edit"]["operation"] == "capture-and-reply"
    assert pinned["edit"]["thread"] == root["id"]
    assert current["value"] == "Current wording."
    assert current["edit"]["operation"] == "data set"


def test_version_descriptors_scan_the_revision_directory_once(tmp_path, monkeypatch):
    """Mapped revisions define history from one directory snapshot."""
    (tmp_path / "revisions").mkdir()
    events = []
    for revision in range(1, 4):
        (tmp_path / "revisions" / f"r{revision}-{'0' * 16}.html").write_text("revision")
        events.append({"kind": "note", "version": revision, "revision": revision})
    events.append({"kind": "note", "version": 4, "revision": 4})

    native_list_revisions = files_model.list_revisions
    scans = 0

    def counted_list_revisions(page_dir):
        nonlocal scans
        scans += 1
        return native_list_revisions(page_dir)

    monkeypatch.setattr(files_model, "list_revisions", counted_list_revisions)

    assert files_model.version_descriptors(tmp_path, events) == [
        {
            "version": revision,
            "revision": revision,
            "url": f"/versions/v{revision}.html",
        }
        for revision in range(1, 4)
    ]
    assert scans == 1


def test_check_requires_the_layers_one_csp(page_dir):
    """The vendoring promise — an approved page can't change under its user and
    can't phone home — is enforced by the browser only if the page declares the
    layer's CSP, so the gate requires it the way it requires the one script."""
    version = page_dir / ".fixture-versions" / "v1.html"
    stripped = re.sub(
        r'<meta http-equiv="Content-Security-Policy"[^>]*>\n', "", version.read_text()
    )
    version.write_text(stripped)
    result = check(page_dir)
    assert result.exit_code == 1
    assert "the layer's one CSP" in result.output


def test_check_refuses_markup_the_browser_never_renders(page_dir):
    """<template> parses into an inert fragment and <noscript> stays unrendered
    in any scripting browser, while the file's reading would take both for the
    page's words — a comment could anchor on text no reader ever sees."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><template><p id="tp">Ghost words.</p></template>'
            "<noscript>Fallback words.</noscript>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert result.output.count("the browser renders none of its content") == 2


def test_check_rejects_widget_violations(page_dir):
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            '<a href="https://example.test/jobs/backfill.py#L88"><code>jobs/backfill.py:88</code></a>',
            '<lf-metric id="bad-metric" value="1"/>'
            "<figure/>"
            "<lf-bogus></lf-bogus>"
            '<lf-timeline id="bad-timeline">'
            '<lf-event id="stray-event" kind="medium">S</lf-event></lf-timeline>'
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
    assert "'medium' is not one of" in out
    assert "must be a direct child of <lf-options>" in out
    assert "'id' is a required property" in out
    assert "does not match" in out  # id pattern
    # A stray element beside the <pre>, and a body that never opened one: both are
    # the same rule, since the <pre> is what carries the whitespace the notation needs.
    assert out.count("its body is one <pre> holding the text") == 2
    assert "text outside its <pre>" in out


def test_check_rejects_duplicate_attributes_the_browser_reads_differently(page_dir):
    """A file reading cannot silently choose another id than the live DOM.

    HTML keeps the first duplicate attribute, while HTMLParser reports both and
    ``dict(attrs)`` keeps the last. Accepting this would let the action gate map
    a stateful widget under an id its browser can never send.
    """
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"].replace(
        'id="feeder-board"', 'id="browser-board" id="file-board"'
    )
    version = page_dir / ".fixture-versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "duplicate attribute" in result.output


def test_check_rejects_a_language_nothing_will_color(page_dir):
    """A declared language the runtime won't honor renders as a plain block, which is
    exactly what a block with no language renders as — so the user sees nothing
    wrong and the author never finds out. Every way of getting it wrong is the lint's,
    because the author is the only one who can still fix any of them: the class somewhere
    other than <pre><code>, an unknown word on the class, and an unknown word on a
    widget attribute that declares itself a language (x-language). The last is checked
    against the same list as the first two rather than by that widget's own schema,
    which is what keeps a second tag taking a language from needing a second reader."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>\n"
            '<pre><code class="language-pythn">x = 1</code></pre>\n'
            '<div class="note language-python">not a code block</div>\n'
            '<lf-code id="walk-bad" language="pythn"><pre>z = 3\n</pre></lf-code>\n'
            '<pre><code class="language-python">y = 2</code></pre>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    out = result.output
    assert (
        'class="language-pythn"' in out
        and "not a language this page's layer speaks" in out
    )
    assert 'class="language-python"' in out and "only <pre><code> is colored" in out
    assert '<lf-code language="pythn">' in out, out
    # The well-formed block is not among the complaints.
    assert out.count('class="language-python"') == 1


def test_a_widget_that_declares_a_language_is_checked_by_that_alone(page_dir):
    """The list is the layer's fact, not one widget's, so nothing in the lint knows
    which widget takes a language: a tag whose entry declares x-language is held to
    $languages on the strength of the declaration. A thirteenth widget that colors
    something — a terminal transcript, a diff — is covered without the lint moving."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-tree"]["properties"]["dialect"] = {"type": "string"}
    registry["lf-tree"]["x-language"] = "dialect"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<lf-tree id="t" dialect="lisp"><pre>\nfeeders/\n</pre></lf-tree>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<lf-tree dialect="lisp">' in result.output
    assert "not a language this page's layer speaks" in result.output


def test_a_misplaced_class_is_offered_whatever_tag_takes_a_language(page_dir):
    """The other way to color a block is read from the layer, not written into the
    lint: the tags whose entries declare an attribute for a language (x-language) are
    the ones the misplaced class is offered, under the attribute each declares. The
    widget that colors a walkthrough is the layer's rather than core's, so a lint that
    named it would be core knowing a content widget — and would keep offering it to a
    layer that dropped it, spelt its attribute differently, or added a second."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<div class="note language-python">not a code block</div>',
        )
    )
    registry_file = page_dir / "registry.json"
    registry = json.loads(registry_file.read_text())
    declaring = {
        tag: entry["x-language"]
        for tag, entry in registry.items()
        if tag.startswith("lf-") and "x-language" in entry
    }
    assert declaring, "the shipped layer declares one; the offer below is its reading"
    out = check(page_dir).output
    for tag, attr in declaring.items():
        assert f"<{tag} {attr}=…>" in out, out

    # A second tag taking one joins the offer under the attribute it declares.
    registry["lf-tree"]["properties"]["dialect"] = {"type": "string"}
    registry["lf-tree"]["x-language"] = "dialect"
    registry_file.write_text(json.dumps(registry))
    out = check(page_dir).output
    assert "<lf-tree dialect=…>" in out, out

    # A layer whose tags declare none has nothing to offer, and the placement rule —
    # which never rested on any widget — is stated on its own.
    for tag in [*declaring, "lf-tree"]:
        registry[tag].pop("x-language")
    registry_file.write_text(json.dumps(registry))
    out = check(page_dir).output
    assert "only <pre><code> is colored" in out and "— move it" in out, out
    assert "or use" not in out, out


def test_the_block_content_lists_are_the_platform_set_and_the_inline_marker():
    """Two selectors in the theme decide what counts as block content — the
    suggestion slots' blockization and lf-compare's stacked-variant trigger
    (lf-options stacks on the title alone, so it asks no block question) — by the
    platform's closed set inverted: any child that is not phrasing content is block.
    The enumeration this replaced named every shipped widget, which is the closed
    list the norms forbid: the first project-layer widget staged in a slot rendered
    inline and the fold dropped it in the frame of the press.

    So each list is held to what it claims to be, in both of its halves. The platform
    half is HTML's phrasing content entire, stated above, which is the half the two
    copies could never check: agreeing with each other says nothing about a name
    dropped from both, and a missing one blockizes a slot holding the element it
    names. The widget half is the inversion's one wrong answer — an inline widget is
    a custom element like any other — and it is a marker rather than tag names,
    because which widgets those are is the registry's to say (x-inline) and a
    stylesheet cannot read it. Four names stood here, one of them a standard chip's
    inside the integrated theme, and no layer could join them; the runtime paints the
    declaration instead and an inline widget joins by declaring it.

    The marker is held to what markDeclared paints for x-inline, because a selector
    naming an attribute nothing writes matches nothing and says so nowhere — it reads
    as the ordinary case of a page with no inline widget in a slot. Being a name the
    runtime is allowed to paint is not that: the wiring is a declaration's entry in
    one of markDeclared's tables, and _marker_for is what follows it. And it is held
    to :where(), which is what keeps an answer about content
    from becoming a claim on the cascade: :not() takes the specificity of the most
    specific thing in it, so a bare attribute selector lifts the whole rule a column
    above the type names beside it, over the marks the layer paints on top of the
    result. Bare, it beat [data-lf-retired] and a decided suggestion kept the slot
    it had just retired."""
    theme = layer_model.composed_theme(
        [schema_model.ASSETS, schema_model.DEFAULT_PACKAGE]
    )
    lists = [_balanced(theme, found.end()) for found in re.finditer(r":not\(", theme)]
    lists = [found for found in lists if found.startswith("a, abbr")]
    assert len(lists) == 2, (
        "expected the suggestion-slot list and lf-compare's stacked-variant trigger"
    )
    registry = validation_model.incoming_registry(
        [schema_model.ASSETS, schema_model.DEFAULT_PACKAGE]
    )
    assert [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and entry.get("x-inline")
    ], "no widget declares x-inline, so the marker in these lists stands for nothing"
    for found in lists:
        tags = {t.strip() for t in found.split(",")}
        markers = {t for t in tags if not t.isalpha()}
        assert tags - markers == PHRASING_CONTENT, (
            "the platform half of a block-content list is not HTML's phrasing "
            "content: a name dropped from it stacks a slot holding that element, "
            "one added to it leaves a block child laid out inline, and a widget "
            "named in either half re-closes the inversion"
        )
        assert markers == {":where([data-lf-inline])"}, (
            "the widget half of a block-content list is the inline marker the "
            "runtime paints from x-inline, in :where() so the question does not "
            "outrank the marks painted over its answer"
        )
        for marker in markers:
            attribute = marker[len(":where([") : -len("])")]
            assert _marker_for("x-inline") == attribute, (
                f"{marker} is not what the runtime paints for x-inline, so the "
                "list's widget half matches nothing on any page"
            )


def test_the_collapse_class_is_one_set_on_both_sides():
    """COLLAPSE_CHARS (the file side) and the passage reader's COLLAPSE regex
    (the browser side) are two spellings of one set, and everything quote-shaped
    rests on their agreement: a character one side collapses and the other keeps
    is a quote captured in the browser that the file's reading can never confirm.
    The next edit to either spelling meets this test, not a detached comment."""
    js = (schema_model.ASSETS / "runtime" / "passages.js").read_text()
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


def test_the_context_an_anchor_stores_is_one_number_on_both_sides():
    """CONTEXT (the file side) and the capture's own CONTEXT are how much of a passage's
    surroundings an anchor writes down, and both sides must mean the same by it: the
    browser writes the prefix and suffix, and `leaf comment` writes them from a version
    file, so a file-side capture storing a different amount makes an anchor the browser
    would never have made — and the resolver demands a full contextual match before it
    calls two identical quotes apart.

    The quote itself is uncapped on both sides. This is the neighbourhood only."""
    _, found = _sole_definition(r"const CONTEXT = (\d+);", "the captured context width")
    assert int(found.group(1)) == anchor_capture_model.CONTEXT


def test_the_render_viewport_is_wide_enough_to_have_margins():
    """The corpus viewport reaches the CSS shell query that grants one margin."""
    theme = (schema_model.ASSETS / "theme.css").read_text()
    found = re.search(r"@container\s+lf-shell\s*\(min-width:\s*(\d+)px\)", theme)
    assert found, "the theme states no container floor for a margin"
    floor = int(found.group(1))
    assert render_checks_model.RENDER_VIEWPORT["width"] >= floor, (
        f"the corpus is read at {render_checks_model.RENDER_VIEWPORT['width']}px and the "
        f"margins only exist above {floor}px, so every reading the sweeps make of a "
        "sidenote, a suggestion's controls or a wide exhibit's reach is being made "
        "against a page the theme has already taken the margins off"
    )


def test_the_ancestor_exclusions_ask_for_a_marker_and_not_a_tag():
    """A choose group's affordance rules stand down inside an exhibit in their own
    selectors, because a stylesheet cannot read the registry the runtime's quoted()
    dispatches on. What they exclude is the paint that declaration leaves on the
    page (data-lf-exhibit, markDeclared) rather than the widgets declaring it, so
    the layer that ships an exhibit and the layer whose rules withhold the hand need
    not be the same one — the shape a tag list cannot have.

    Every ancestor exclusion in the rules of the composed theme is read, not the
    exhibit ones alone: a tag name in one is a closed vocabulary wherever it appears,
    and the failure it causes is a project's own widget silently outside the answer.
    Comments come off first, because two of them quote this very selector — left in,
    the set could be satisfied with every rule that carries the exclusion deleted.

    The marker is then held to what `markDeclared` actually paints for x-exhibit and
    to a widget declaring it: either missing leaves every one of those rules excluding
    nothing on any page, which renders as a quoted group offering the pick it exists
    to withhold. Not the pick itself, which quoted() refuses at the layer's own door:
    what is lost is that a mention stops looking like a mention. Which of
    markDeclared's two tables the declaration sits in is a different question — where
    the fact holds — and the browser answers it, in a reply as well as in the
    document.

    What this cannot see is one rule of ten dropping its exclusion while the others
    keep theirs: a set does not count. That reading is the browser's."""
    theme = re.sub(
        r"/\*.*?\*/",
        "",
        layer_model.composed_theme([schema_model.ASSETS, schema_model.DEFAULT_PACKAGE]),
        flags=re.DOTALL,
    )
    excluded = {
        inside.removesuffix(" *")
        for found in re.finditer(r":not\(", theme)
        if (inside := _balanced(theme, found.end())).endswith(" *")
    }
    assert excluded == {":where([data-lf-exhibit])"}, (
        f"the theme's ancestor exclusions are {excluded}, and the thing an affordance "
        "may stand down inside is a painted exhibit. A tag spelled here answers for "
        "the layer that ships it and no other; a second marker is a second question, "
        "and belongs to the test that owns it"
    )
    assert _marker_for("x-exhibit") == "data-lf-exhibit", (
        "the theme excludes data-lf-exhibit and markDeclared paints "
        f"{_marker_for('x-exhibit')!r} for x-exhibit, so nothing puts that mark on a "
        "page and an exhibit keeps every affordance these rules meant to withhold"
    )
    registry = validation_model.incoming_registry(
        [schema_model.ASSETS, schema_model.DEFAULT_PACKAGE]
    )
    assert [
        tag
        for tag, entry in registry.items()
        if tag.startswith("lf-") and entry.get("x-exhibit")
    ], "no widget declares x-exhibit, so the marker in these rules stands for nothing"


def test_every_declared_attribute_and_enum_stands_in_an_example():
    """The corpus floor one level down from tags (examples/CLAUDE.md): where an
    attribute or an enum value changes what a reader sees, a page shows it. The
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
        for rec in structure_model.parse_structure(path.read_text()).lf_elements:
            for attr, value in rec["attrs"].items():
                used.setdefault(rec["tag"], {}).setdefault(attr, set()).add(value)
    # An example pins a snapshot by writing the data revision a capture retained, and
    # a source that only ever takes `data set` retains none: examples/*.data.json can
    # attach a capture label to a `$captures` file and not to a set value, so
    # pr-review-facts has no revision for lf-pull-request to name. The manifest, not
    # this floor, is where that is fixed.
    unreachable = {("lf-pull-request", "snapshot")}
    missing = []
    for tag, entry in sorted(registry.items()):
        if not tag.startswith("lf-"):
            continue
        for attr, spec in entry.get("properties", {}).items():
            if attr in {"restated", "overruled", "resolves"}:
                continue
            if (tag, attr) in unreachable:
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
    tone nothing matches paints nothing, so the chip renders neutral on a page that
    otherwise looks perfectly well. The user cannot see it — they never knew it
    was meant to be red — so the only party who can still fix it is whoever wrote
    the word, and the lint is where they are told. This is the whole difference
    between the attribute and a class, which nothing checks."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            '<lf-option id="flag-first">',
            '<lf-option id="flag-first"><lf-chip tone="dangre">risk: high</lf-chip>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "not a tone this page's layer paints" in result.output
    assert "'ok', 'warn', 'danger'" in result.output.replace('"', "'")

    # The list is the layer's, so a layer that adds one accepts it with no widget
    # touched — which is the point of $tones over an enum on lf-chip.
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$tones"]["names"].append("dangre")
    (page_dir / "registry.json").write_text(json.dumps(registry))
    assert check(page_dir).exit_code == 0


def test_a_chip_is_admissible_in_both_its_holders(page_dir):
    """x-parent is a list because one element can belong to two holders, and a chip
    is written in a lf-option and in a lf-variant — the same shape either side of the
    decision. Neither is special-cased anywhere: the nesting check reads the list."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<lf-compare id="cmp"><lf-variant id="v-a"><lf-chip tone="ok">cheap</lf-chip>'
            "<strong>A</strong> One.</lf-variant></lf-compare>\n  <lf-options>",
        )
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output

    # And refused where neither holder is its parent, naming both.
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2><lf-chip>stray</lf-chip>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "must be a direct child of <lf-option> or <lf-variant>" in result.output


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
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2>\n<pre><code class="language-python">x = 1</code></pre>\n'
            '<div class="note language-python">not a code block</div>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "not a language this page's layer speaks" in result.output
    # The placement rule never rested on the list, so it reports here too.
    assert "only <pre><code> is colored" in result.output


def test_check_rejects_loose_content_in_items_container(page_dir):
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", "<lf-options>\nloose text\n<p>stray</p>\n<br/>")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "admits only ['lf-option'] children" in result.output
    assert "'br'" in result.output  # self-closed strays count as children too
    assert "loose text" in result.output


def test_flag_attribute_accepts_both_html_spellings(page_dir):
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace('id="backfill-first">', 'id="backfill-first" chosen="">')
    )
    assert check(page_dir).exit_code == 0
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace('id="backfill-first">', 'id="backfill-first" chosen="yes">')
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "is not of type 'boolean'" in result.output


def test_retired_question_and_recommendation_attributes_are_rejected(page_dir):
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options label="Which plan?">').replace(
            'id="backfill-first">', 'id="backfill-first" recommended>'
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "Additional properties are not allowed" in result.output
    assert "'label' was unexpected" in result.output
    assert "'recommended' was unexpected" in result.output


def test_milestones_compose(page_dir):
    nested = """<lf-milestones>
    <lf-milestone id="m-one" status="done" when="week 1"><strong>Survey</strong> Sites.</lf-milestone>
    <lf-milestone id="m-two" status="active" tags="wood,solar"><strong>Build</strong></lf-milestone>
  </lf-milestones>
<lf-options>"""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", nested)
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<lf-milestone id="m-stray" status="done"><strong>X</strong></lf-milestone><lf-options>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "must be a direct child of <lf-milestones>" in result.output


def test_tabs_validate_and_compose(page_dir):
    tabs = """<lf-tabs id="ws">
  <lf-tab id="ws-ingest" label="Ingest"><p>Pipeline notes.</p></lf-tab>
  <lf-tab id="ws-search" label="Search">
    <lf-metrics><lf-metric id="k-lat" value="118 ms"></lf-metric></lf-metrics>
  </lf-tab>
</lf-tabs>
<lf-options>"""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", tabs)
    )
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
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<lf-options>", bad)
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "'label' is a required property" in result.output
    assert "must be a direct child of <lf-tabs>" in result.output
    assert "loose text" in result.output


def test_suggestion_validates(page_dir):
    suggest(page_dir)
    assert check(page_dir, version=1).exit_code == 0, check(page_dir, version=1).output


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
            "must be a direct child of <lf-suggestion>",
        ),
        (
            (
                '<lf-suggestion id="sug-a" resolves="nosuch"><lf-new><p>x</p></lf-new>'
                "</lf-suggestion><lf-options>"
            ),
            "names no comment in the log",
        ),
    ]:
        (page_dir / ".fixture-versions" / "v1.html").write_text(
            PAGE.replace("<lf-options>", markup)
        )
        result = check(page_dir, version=1)
        assert result.exit_code == 1, markup
        assert expected in result.output, f"{markup}\n{result.output}"


def test_suggestion_resolves_accepts_a_real_comment(page_dir):
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    markup = '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p>x</p></lf-new></lf-suggestion>'
    (page_dir / ".fixture-versions" / "v1.html").write_text(before_choice(PAGE, markup))
    assert check(page_dir, version=1).exit_code == 0


def test_accepting_licenses_retiring_the_replaced_markup(page_dir):
    # v2 honors the accept: the old paragraph and the wrapper are gone, the
    # proposal inlined. Nothing but a logged accept makes that legal.
    suggest(page_dir)
    honored = PAGE.replace(
        "<lf-options>",
        '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
    )
    (page_dir / ".fixture-versions" / "v2.html").write_text(honored)
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "refill-rule" in result.output

    decide(page_dir, "accept")
    assert check(page_dir, version=2).exit_code == 0, check(page_dir, version=2).output


def test_the_live_source_can_honor_the_latest_revision_decision(page_dir):
    """Source checking is about the next live revision, not a historical stamp."""
    suggest(page_dir)
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        (page_dir / ".fixture-versions" / "v2.html")
        .read_text()
        .replace("<title>t</title>", "<title>t · v2</title>")
    )
    publish(page_dir, 2)
    (page_dir / ".fixture-versions" / "v3.html").write_text(
        before_choice(
            PAGE.replace("<title>t</title>", "<title>t · v3</title>"), SUGGESTION
        )
    )
    publish(page_dir, 3)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 3,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )

    # Once staged as index.html, these bytes are a new live revision after r3;
    # the standing decision on r3 therefore licenses the honoring rewrite.
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-camera">Refill when the camera shows it half-empty.</p><lf-options>',
        )
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 0, result.output


def test_an_unanswered_proposal_cant_be_kept_as_settled_content(page_dir):
    # Self-accepting: the wrapper goes but its proposal stays, presented as
    # ordinary prose the user never agreed to. Withdrawal is whole or not.
    insert = """<lf-suggestion id="sug-thistle">
  <lf-new><p id="thistle-plan">Switch the north feeder to thistle in autumn.</p></lf-new>
</lf-suggestion>
"""
    suggest(page_dir, markup=insert)
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="thistle-plan">Switch the north feeder to thistle in autumn.</p><lf-options>',
        )
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "sug-thistle" in result.output
    # A refused version never published, so it is nobody's baseline: v3 stands
    # against v1 — the page the user was actually looking at — and there a
    # whole withdrawal is fine. So is honoring a logged accept.
    (page_dir / ".fixture-versions" / "v3.html").write_text(PAGE)
    assert check(page_dir, version=3).exit_code == 0
    decide(page_dir, "accept", widget="sug-thistle")
    assert check(page_dir, version=2).exit_code == 0


def test_rejecting_licenses_retiring_the_proposal(page_dir):
    # A reject is consent to drop the proposal, so it retires even while a
    # thread about it is open — the user has already answered.
    suggest(page_dir)
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "cameras aren't reliable yet",
        },
    )
    assert check(page_dir, version=2).exit_code == 1
    decide(page_dir, "reject")
    assert check(page_dir, version=2).exit_code == 0
    # The other slot is not licensed: dropping the markup a reject kept is refused.
    (page_dir / ".fixture-versions" / "v3.html").write_text(PAGE)
    result = check(page_dir, version=3)
    assert result.exit_code == 1
    assert "refill-rule" in result.output


def test_an_unanswered_deletion_cant_delete(page_dir):
    # The mirror of self-accepting an insertion: dropping the markup a pending
    # deletion wraps, without the accept that consents to losing it.
    delete = """<lf-suggestion id="sug-drop">
  <lf-old><p id="hand-log">The manual sightings log.</p></lf-old>
</lf-suggestion>
"""
    suggest(page_dir, markup=delete)
    (page_dir / ".fixture-versions" / "v2.html").write_text(PAGE)
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "hand-log" in result.output
    decide(page_dir, "accept", widget="sug-drop")
    assert check(page_dir, version=2).exit_code == 0


def test_withdrawing_an_unanswered_suggestion_needs_no_consent(page_dir):
    # Nothing was decided, so Claude may take the proposal back — but not while
    # an unresolved thread is anchored in it.
    suggest(page_dir)
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "<lf-options>",
            '<p id="refill-rule">Refill every feeder each morning.</p><lf-options>',
        )
    )
    assert check(page_dir, version=2).exit_code == 0
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "refill-camera"},
            "text": "why the camera?",
        },
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "refill-camera" in result.output
    events_model.append_event(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c1"}
    )
    assert check(page_dir, version=2).exit_code == 0


def test_reply_refuses_a_suggestion(page_dir):
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "Fixed:",
            "--markup",
            '<lf-suggestion id="sug-x"><lf-new><p>fixed</p></lf-new></lf-suggestion>',
        ],
    )
    assert result.exit_code != 0
    assert "frozen in the log" in result.output


def test_check_rejects_wrong_scaffold(page_dir):
    html = PAGE.replace('<script type="module" src="/leaf.js"></script>', "").replace(
        '<link rel="stylesheet" href="/theme.css">', ""
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(html)
    result = check(page_dir)
    assert result.exit_code == 1
    assert "exactly one external <script src>" in result.output
    assert "exactly one stylesheet" in result.output


@pytest.mark.parametrize(
    "html",
    [
        PAGE.replace('<script type="module" src="/leaf.js"></script>', "").replace(
            "</main>",
            '</main>\n<script type="module" src="/leaf.js"></script>',
        ),
        PAGE.replace('<link rel="stylesheet" href="/theme.css">', "").replace(
            "<main>", '<main>\n<link rel="stylesheet" href="/theme.css">'
        ),
        PAGE.replace('<link rel="stylesheet" href="/theme.css">', "")
        .replace('<script type="module" src="/leaf.js"></script>', "")
        .replace(
            "</main>",
            """</main>
<head>
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>""",
        ),
    ],
    ids=["module-after-main", "stylesheet-inside-main", "assets-in-late-head"],
)
def test_check_requires_presentation_assets_in_head(page_dir, html):
    """The gate must exist before the browser can paint the body it withholds."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(html)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "must be in <head> before <body>" in result.output


@pytest.mark.parametrize(
    "asset, changed",
    [
        (
            '<link rel="stylesheet" href="/theme.css">',
            '<link rel="stylesheet" href="/theme.css" media="print">',
        ),
        (
            '<script type="module" src="/leaf.js"></script>',
            '<script type="module" src="/leaf.js" async></script>',
        ),
    ],
    ids=["print-only-theme", "noncanonical-module"],
)
def test_check_requires_always_applicable_canonical_assets(page_dir, asset, changed):
    """An asset whose URL is right but applicability differs is not the boundary."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(asset, changed)
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "exactly" in result.output


def test_check_rejects_inline_importance_over_the_presentation_boundary(page_dir):
    """Inline importance outranks stylesheet layers, so the authoring door owns it."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<main>", '<main style="opacity: 1 !important">')
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "protected presentation property opacity important" in result.output


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
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("</main>", f"</main>\n{outside}")
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


def test_check_requires_main_to_be_a_direct_body_child(page_dir):
    """A main nested in an authored wrapper is not selected by `body > main`."""
    wrapped = PAGE.replace("<main>", "<div>\n<main>").replace(
        "</main>", "</main>\n</div>"
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(wrapped)

    result = check(page_dir)

    assert result.exit_code == 1
    assert "one <main> directly under <body>" in result.output


@pytest.mark.parametrize(
    "html",
    [
        PAGE.replace("</body>", '</body>\n<p id="tail">Authored tail</p>'),
        PAGE.replace("</head>", '<img src="/media/tail.png" alt="tail">\n</head>'),
    ],
)
def test_check_rejects_paintable_markup_the_browser_reparents(page_dir, html):
    """HTML recovery cannot move authored pixels around the main boundary."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(html)

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
    (page_dir / ".fixture-versions" / "v1.html").write_text(signoff)
    assert check(page_dir).exit_code == 0

    (page_dir / ".fixture-versions" / "v1.html").write_text(
        signoff.replace("sign-off", "approve")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "content must be one of ['sign-off'], found 'approve'" in result.output

    (page_dir / ".fixture-versions" / "v1.html").write_text(
        signoff.replace("lf-review", "lf-signoff")
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "unknown lf- meta" in result.output
    assert "lf-review" in result.output  # the error names the known vocabulary


def test_check_rejects_duplicate_ids(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="flag-first"')
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "duplicate ids" in result.output


def test_unreferenced_ids_and_widget_items_may_leave_the_page(page_dir):
    publish(page_dir)
    without_item = PAGE.replace(
        '      <lf-option id="backfill-first"><lf-chip>effort: med</lf-chip><lf-chip>risk: low</lf-chip>\n'
        "        <strong>Backfill first</strong> Verify, then flip. <em>My take: do this first.</em>\n"
        "      </lf-option>\n",
        "",
    )
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        without_item.replace('<section id="plan">', "<section>")
    )

    result = check(page_dir, version=2)

    assert result.exit_code == 0, result.output
    assert "ids dropped from revision r1: ['backfill-first', 'plan']" in result.output


def test_an_unresolved_anchor_protects_its_id_until_the_thread_resolves(page_dir):
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "anchor": {"section": "flow"},
            "text": "Keep this diagram addressable.",
        },
    )
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            '  <lf-diagram id="flow"><pre>\n'
            "graph LR\n"
            "  A --> B\n"
            "  </pre></lf-diagram>\n",
            "",
        )
    )

    unresolved = check(page_dir, version=2)
    assert unresolved.exit_code == 1
    assert "protected ids" in unresolved.output and "'flow'" in unresolved.output

    events_model.append_event(
        page_dir, {"kind": "resolve", "author": "user", "parent": "c1"}
    )
    resolved = check(page_dir, version=2)
    assert resolved.exit_code == 0, resolved.output
    assert "ids dropped from revision r1: ['flow']" in resolved.output


def test_a_standing_action_protects_its_id_until_it_is_retracted(page_dir):
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    (page_dir / ".fixture-versions" / "v2.html").write_text(PAGE)

    standing = check(page_dir, version=2)
    assert standing.exit_code == 1
    assert "protected ids" in standing.output and "'d1'" in standing.output

    v2("Ship the flag dark, then backfill. Roll back with one flag.", attrs=" restated")
    retracted = stamp(page_dir, 2, "replace the draft")
    assert retracted.exit_code == 0, retracted.output
    (page_dir / ".fixture-versions" / "v3.html").write_text(PAGE)

    dropped = check(page_dir, version=3)
    assert dropped.exit_code == 0, dropped.output
    assert "ids dropped from revision r2: ['d1']" in dropped.output


def test_a_standing_action_protects_its_fold_unit_until_undone(page_dir):
    def write(version, todo):
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _board(todo, []))
        )

    write(1, [X])
    publish(page_dir)
    moved = events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "b1",
            "action": "move",
            "detail": {"card": "card-x", "to": "c-done", "index": 0},
        },
    )
    write(2, [])

    standing = check(page_dir, version=2)
    assert standing.exit_code == 1
    assert "protected ids" in standing.output and "'card-x'" in standing.output

    events_model.append_event(
        page_dir, {"kind": "undo", "author": "user", "undoes": moved["id"]}
    )
    undone = check(page_dir, version=2)
    assert undone.exit_code == 0, undone.output
    assert "ids dropped from revision r1: ['card-x']" in undone.output


def test_an_effective_report_protects_detail_ids_its_record_needs(page_dir):
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-board"]["properties"]["overruled"] = {"type": "boolean"}
    registry["lf-board"]["x-report"] = registry["lf-board"]["x-state"]
    registry_path.write_text(json.dumps(registry))

    board = _board([X], [])
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + board)
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "revision": files_model.latest_revision(page_dir),
            "widget": "b1",
            "action": "move",
            "detail": {"card": "card-x", "to": "c-done", "index": 0},
        },
    )

    without_destination = board.replace(
        '<lf-column id="c-done" label="Done"></lf-column>', ""
    )
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + without_destination)
    )

    standing = check(page_dir, version=2)
    assert standing.exit_code == 1
    assert "protected ids" in standing.output and "'c-done'" in standing.output

    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "b1",
            "action": "move",
            "detail": {"card": "card-x", "to": "c-todo", "index": 0},
        },
    )
    outranked = check(page_dir, version=2)
    assert outranked.exit_code == 0, outranked.output
    assert "ids dropped from revision r1: ['c-done']" in outranked.output


def test_a_version_may_not_quietly_rewrite_what_the_user_decided(page_dir):
    """The runtime replays a recorded action onto every later version, so the
    user's edit stands over whatever v2's markup says about that widget.
    Which makes a rewritten widget a version talking to nobody — its new words
    could never reach the reader. `restated` is how a version says it means to
    take the decision back, and this is the gate that makes it say so."""
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    assert check(page_dir).exit_code == 0

    # Re-emitting what v1 said is the ordinary republish, and costs nothing:
    # the user's edit is already on screen over it.
    v2("Ship the flag dark, then backfill.")
    assert check(page_dir, version=2).exit_code == 0, (
        "a republish that changes nothing must pass"
    )

    # Writing their own words back is the other quiet case, and the commoner
    # one: the version agrees with the edit rather than overruling it. A gate
    # that fired here would fire on almost every version an author writes, and
    # a gate that fires on correct work is one they learn to silence.
    v2("Cut the flag; backfill first.")
    assert check(page_dir, version=2).exit_code == 0, "honoring an edit must pass"

    # Rewriting the words under the edit is the case that needs a decision.
    v2("Ship the flag dark, then backfill. Roll back with one flag.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "its words changed" in result.output
    assert "edit on r1" in result.output
    assert "restated" in result.output

    # Said out loud, the same version publishes.
    v2("Ship the flag dark, then backfill. Roll back with one flag.", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0, "a restated rewrite is allowed"


def test_restating_on_the_first_version_is_refused(page_dir):
    """There is nothing before v1 to take back, so `restated` there can only be
    a misreading of what the word does — and one that would record a retraction
    of nothing into the log."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1" restated><pre>Words.</pre></lf-draft>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "nothing to retract" in result.output
    assert "recorded nothing on it" in result.output


def test_restating_a_widget_that_kept_its_words_is_refused(page_dir):
    """`restated` discards what the user recorded, so a version may only
    spend it where there is a rewrite to justify it. Unpoliced, it is the one
    word that turns the gate back into the silence it replaced."""
    v2 = _decided(page_dir, "Ship the flag dark, then backfill.")
    v2("Ship the flag dark, then backfill.", attrs=" restated")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "nothing to retract" in result.output
    assert "unchanged since r1" in result.output


def test_report_validates_at_the_door_and_stamps_identity(page_dir, monkeypatch):
    """`leaf report` is the report event's one door, so the widget, verb, and
    detail are held to the x-report declaration there — the CLI mirror of the
    POST door's action gate — and the event leaves stamped with the posting
    session's voice and the exact revision the reader is looking at."""
    _tasks_version(page_dir, 1, "active")
    stage_fixture_source(page_dir, 1)
    activation = revisioning_model.activate_source(page_dir, [])
    assert activation.error is None and activation.revision == 1
    draft_report = _report(page_dir, "t-parser", "status", "status=review")
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
        (("nope", "status", "status=review"), "unknown report widget"),
        (("tree", "status", "status=review"), "does not declare report verb"),
        (("t-parser", "finish", "status=done"), "does not declare report verb"),
        (("t-parser", "status", "status=shipping"), "detail is invalid"),
        (("t-parser", "status", "status"), "name=value"),
        (("t-parser", "status"), "'status' is a required property"),
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
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0, sent.output
    event = events_model.read_events(page_dir)[-1]
    assert event["kind"] == "report" and event["author"] == "claude"
    assert (event["agent"], event["session"]) == ("Indexer", "worker-1")
    assert event["widget"] == "t-parser" and event["action"] == "status"
    assert event["detail"] == {"status": "review"} and event["revision"] == 1


def test_receipt_settles_one_known_request_once(page_dir, monkeypatch):
    """The host's result names the exact request it executed. A second terminal
    account would make one side effect have two outcomes, so the CLI door refuses it."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-decision id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-decision></lf-task></lf-command>"
    )
    version = page_dir / ".fixture-versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", operation + "</section>")
    )
    publish(page_dir)
    request = events_model.append_event(
        page_dir,
        {
            "kind": "request",
            "author": "user",
            "revision": 1,
            "widget": "commands",
            "action": "restart",
            "detail": {"target": "goal", "worker": "worker", "worktree": "tree"},
        },
    )
    pending = state_json(page_dir)["requests"]
    assert len(pending) == 1
    lifecycle = pending[0]
    assert lifecycle["seat"] == {
        "document": {"kind": "page", "revision": 1},
        "widget": "commands",
    }
    assert lifecycle["phase"] == "pending"
    assert lifecycle["latest"]["request"]["id"] == request["id"]
    assert lifecycle["latest"]["receipt"] is None
    unknown = CliRunner().invoke(
        cli_model.cli,
        ["receipt", str(page_dir), "missing", "failed", "--text", "No request"],
    )
    assert unknown.exit_code == 1
    assert "unknown request 'missing'" in unknown.output

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "coordinator-1")
    monkeypatch.setenv("LEAF_AGENT", "Atlas lead")
    accepted = CliRunner().invoke(
        cli_model.cli,
        [
            "receipt",
            str(page_dir),
            request["id"],
            "succeeded",
            "--text",
            "Started w-9 on the preserved branch",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    receipt = events_model.read_events(page_dir)[-1]
    assert (receipt["kind"], receipt["request"], receipt["status"]) == (
        "receipt",
        request["id"],
        "succeeded",
    )
    assert receipt["text"] == "Started w-9 on the preserved branch"
    assert (receipt["agent"], receipt["session"]) == (
        "Atlas lead",
        "coordinator-1",
    )
    projected = state_json(page_dir)["requests"][0]
    assert projected["phase"] == "completed"
    assert projected["latest"]["receipt"]["id"] == receipt["id"]
    assert (
        projected["latest"]["receipt"]["text"] == "Started w-9 on the preserved branch"
    )

    duplicate = CliRunner().invoke(
        cli_model.cli,
        ["receipt", str(page_dir), request["id"], "failed", "--text", "Again"],
    )
    assert duplicate.exit_code == 1
    assert "already has receipt" in duplicate.output
    assert (
        len(
            [
                event
                for event in events_model.read_events(page_dir)
                if event["kind"] == "receipt"
            ]
        )
        == 1
    )


def test_page_state_groups_failed_retry_as_one_request_lifecycle(page_dir):
    """Attempts belong to the seat that admits them. A failed attempt leaves that
    lifecycle ready, and the retry becomes its latest attempt rather than a second
    partly joined request record."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-decision id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-decision></lf-task></lf-command>"
    )
    version = page_dir / ".fixture-versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", operation + "</section>")
    )
    publish(page_dir)
    ready_decisions = {decision["id"] for decision in state_json(page_dir)["decisions"]}
    assert "commands-decision" in ready_decisions
    assert "goal" not in ready_decisions
    first = events_model.append_event(
        page_dir,
        {
            "kind": "request",
            "author": "user",
            "revision": 1,
            "widget": "commands",
            "action": "restart",
            "detail": {"target": "goal", "worker": "worker", "worktree": "tree"},
        },
    )
    assert "commands-decision" not in {
        decision["id"] for decision in state_json(page_dir)["decisions"]
    }
    failure = events_model.append_event(
        page_dir,
        {
            "kind": "receipt",
            "author": "claude",
            "request": first["id"],
            "status": "failed",
            "text": "Worker lease disappeared",
        },
    )
    assert "commands-decision" in {
        decision["id"] for decision in state_json(page_dir)["decisions"]
    }
    retry = events_model.append_event(
        page_dir,
        {
            "kind": "request",
            "author": "user",
            "revision": 1,
            "widget": "commands",
            "action": "restart",
            "detail": {"target": "goal", "worker": "worker", "worktree": "tree"},
        },
    )

    lifecycles = state_json(page_dir)["requests"]
    assert len(lifecycles) == 1
    lifecycle = lifecycles[0]
    assert lifecycle["phase"] == "pending"
    assert len(lifecycle["attempts"]) == 2
    assert lifecycle["attempts"][0]["receipt"]["id"] == failure["id"]
    assert lifecycle["latest"]["request"]["id"] == retry["id"]
    assert lifecycle["latest"]["receipt"] is None
    assert "commands-decision" not in {
        decision["id"] for decision in state_json(page_dir)["decisions"]
    }


def test_a_version_may_not_quietly_contradict_a_standing_report(page_dir):
    """A report is provisional news with the reviewer precedence reversed:
    silence leaves it painting, writing the reported state absorbs it, and a
    version that writes something else must say so with `overruled` — the gate
    refuses the silent contradiction, which would otherwise drop a worker's
    news without anyone adjudicating it."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0

    # Unchanged markup leaves the report provisional without a copying warning.
    _tasks_version(page_dir, 2, "active")
    silent = check(page_dir, version=2)
    assert silent.exit_code == 0
    assert "record behind the log" not in silent.output
    assert state_json(page_dir)["updates"][0]["disposition"] == "effective"

    # Honoring: writing the reported state.
    _tasks_version(page_dir, 2, "review")
    assert check(page_dir, version=2).exit_code == 0, "honoring a report must pass"

    # Contradiction, unnamed: refused, naming the report and both states.
    _tasks_version(page_dir, 2, "done")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "contradicts a standing report" in result.output
    assert "'done'" in result.output and "'review'" in result.output
    assert "overruled" in result.output

    # Said out loud, the same version publishes — including back to the state
    # the report tried to move (rejecting the news without changing the page).
    _tasks_version(page_dir, 2, "done", " overruled")
    assert check(page_dir, version=2).exit_code == 0
    _tasks_version(page_dir, 2, "active", " overruled")
    assert check(page_dir, version=2).exit_code == 0


def test_publishing_records_typed_settlements_for_provisional_agent_facts(page_dir):
    """One durable relation ends both kinds of provisional agent information.
    Its typed targets keep report-event ids and widget-work ids distinct without
    growing one note field for each channel."""

    def add_board(version: int) -> None:
        path = page_dir / ".fixture-versions" / f"v{version}.html"
        path.write_text(
            path.read_text().replace(
                '<lf-diagram id="flow">',
                '<lf-board id="rollout"><lf-column id="now" label="Now">'
                '<lf-card id="rollout-card"><strong>Ship</strong></lf-card>'
                '</lf-column></lf-board><lf-diagram id="flow">',
            )
        )

    _tasks_version(page_dir, 1, "active")
    add_board(1)
    assert stamp(page_dir, 1, "cut").exit_code == 0
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0
    report_id = json.loads(sent.output)["id"]
    claimed = _status(
        page_dir, "working", "checking the rollout", "--on", "rollout-card"
    )
    assert claimed.exit_code == 0, claimed.output

    _tasks_version(page_dir, 2, "review")
    add_board(2)
    published = stamp(page_dir, 2, "absorb", completes=("rollout-card",))
    assert published.exit_code == 0, published.output
    note = [e for e in events_model.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["settles"] == [
        {"kind": "report", "id": report_id},
        {"kind": "work", "id": "rollout-card"},
    ]

    # The report ended at v2, so v3 owes it nothing.
    _tasks_version(page_dir, 3, "done")
    add_board(3)
    assert check(page_dir, version=3).exit_code == 0

    # And a repeated `overruled` after the answer is the carried-forward
    # attribute, refused the way a repeated `restated` is.
    _tasks_version(page_dir, 3, "done", " overruled")
    stale = check(page_dir, version=3)
    assert stale.exit_code == 1
    assert "r2 already answered" in stale.output

    # Reusing older source creates a new revision and the next public stamp. If
    # those current bytes state the reported value, that new stamp absorbs it.
    sent = _report(page_dir, "t-parser", "status", "status=review")
    assert sent.exit_code == 0, sent.output
    future_report = json.loads(sent.output)["id"]
    _tasks_version(page_dir, 1, "review")
    add_board(1)
    old_cut = page_dir / ".fixture-versions" / "v1.html"
    old_cut.write_text(
        old_cut.read_text().replace("<title>t</title>", "<title>t · reissued</title>")
    )
    republished = stamp(page_dir, 1, "reissued old cut")
    assert republished.exit_code == 0, republished.output
    note = [e for e in events_model.read_events(page_dir) if e["kind"] == "note"][-1]
    assert note["version"] == 3
    assert {"kind": "report", "id": future_report} in note.get("settles", [])


def test_stamp_and_report_choose_one_log_order(page_dir, monkeypatch):
    """Report revisioning and stamp-note calculation are one transaction each."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    _tasks_version(page_dir, 2, "review")
    stage_fixture_source(page_dir, 2)

    at_commit = threading.Event()
    resume = threading.Event()
    original_append_event = service_model.PageTransaction.append_event

    def held_append_event(page, event):
        if event.get("kind") == "note" and event.get("version") == 2:
            at_commit.set()
            assert resume.wait(timeout=10), "the report did not enter the publish gap"
        return original_append_event(page, event)

    monkeypatch.setattr(
        service_model.PageTransaction, "append_event", held_append_event
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        publishing = executor.submit(publishing_model.cmd_stamp, page_dir, "absorb")
        assert at_commit.wait(timeout=10), "publish never reached its note commit"
        serialized = leases_model.lock_is_held(page_dir / "events.jsonl")
        reporting = executor.submit(
            conversation_model.cmd_report,
            page_dir,
            "t-parser",
            "status",
            ("status=review",),
        )
        # This branch only prevents the test harness from deadlocking in the
        # correct implementation: a transaction-holding publish must finish
        # before the report can derive its version; the current unlocked publish
        # lets the report finish first and exposes the inconsistent order.
        if serialized:
            resume.set()
            publishing.result(timeout=10)
            reporting.result(timeout=10)
        else:
            reporting.result(timeout=10)
            resume.set()
            publishing.result(timeout=10)

    events = events_model.read_events(page_dir)
    report = [event for event in events if event["kind"] == "report"][-1]
    note = [event for event in events if event["kind"] == "note"][-1]
    assert serialized, "publish calculated mutable log state outside its transaction"
    assert note["version"] == 2 and "settles" not in note
    assert report["revision"] == 2


def test_absorption_is_by_id_never_inferred_from_markup(page_dir):
    """The bug put back: a v2 that writes the reported state but whose note
    names no report ids (the shape a hand-built note has) leaves the report
    standing, so a v3 that moves the state again is refused. Without the
    id-explicit record the gate would infer absorption from v2's markup and let
    the report die silently."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0
    _tasks_version(page_dir, 2, "review")
    publish(page_dir, version=2)  # a bare note: honoring markup, nothing named

    _tasks_version(page_dir, 3, "done")
    result = check(page_dir, version=3)
    assert result.exit_code == 1
    assert "contradicts a standing report" in result.output


def test_an_unearned_overruled_is_refused(page_dir):
    """`overruled` discards a worker's news, so a version may only spend it
    where a disagreement justifies it — agreeing with the report, or wearing it
    with no report standing, is the reflex that would hollow the gate out."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)

    # Nothing standing at all.
    _tasks_version(page_dir, 2, "active", " overruled")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "nothing to overrule" in result.output

    # Standing, but the markup writes the reported state: that is absorption.
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0
    _tasks_version(page_dir, 2, "review", " overruled")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "writes the reported state" in result.output


def test_an_effective_report_protects_its_unit_until_a_stamp_settles_it(page_dir):
    """An effective report keeps its unit addressable until a stamp settles it."""
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "status=review").exit_code == 0

    (page_dir / ".fixture-versions" / "v2.html").write_text(PAGE)
    standing = check(page_dir, version=2)
    assert standing.exit_code == 1
    assert "protected ids" in standing.output and "'t-parser'" in standing.output
    assert "ids dropped from revision r1: ['tree']" in standing.output

    _tasks_version(page_dir, 2, "review")
    settled = stamp(page_dir, 2, "absorb the report")
    assert settled.exit_code == 0, settled.output
    (page_dir / ".fixture-versions" / "v3.html").write_text(PAGE)

    dropped = check(page_dir, version=3)
    assert dropped.exit_code == 0, dropped.output
    assert "ids dropped from revision r2: ['t-parser', 'tree']" in dropped.output


def test_the_gate_asks_about_the_card_that_was_moved_and_not_the_board(page_dir):
    """A `move` names the board, but what the user decided about is the card:
    where it belongs. Holding the version to the board's whole contents would
    refuse it for editing an untouched card or adding a new one — a rule that
    fires on innocent versions is one authors learn to silence.

    So the subject is the card, and `restated` on it retracts that card's moves
    alone. The rest of the board stays where the user put it, which is what
    keeps a typo fix from costing them an afternoon's arrangement."""

    def write(version, todo, done):
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _board(todo, done))
        )

    write(1, [X, Y], [])
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "b1",
            "action": "move",
            "detail": {"card": "card-x", "to": "c-done", "index": 0},
        },
    )
    assert check(page_dir).exit_code == 0

    # An untouched card rewritten, the moved card's own words left alone.
    write(2, [X, ("card-y", "", "Wire the importer and its backfill")], [])
    assert check(page_dir, version=2).exit_code == 0, (
        "an untouched card is not the gate's business"
    )

    # The card written where the user put it. Redundant now that replay
    # carries the move, but a version that does it anyway is not wrong.
    write(2, [Y], [X])
    assert check(page_dir, version=2).exit_code == 0, (
        "relocating the moved card must pass"
    )

    # The moved card's own words rewritten: now the decision is in question.
    write(2, [("card-x", "", "Guard the delete behind the flag"), Y], [])
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "card-x" in result.output and "move on r1" in result.output
    assert "card-y" not in result.output, (
        "the gate named a card nobody had decided about"
    )

    write(2, [("card-x", " restated", "Guard the delete behind the flag"), Y], [])
    assert check(page_dir, version=2).exit_code == 0

    # And the board itself never takes the attribute: every move names a card, so
    # a board is never what a decision rests on, and offering `restated` there
    # would be a door onto an error message about retracting nothing.
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        (page_dir / ".fixture-versions" / "v2.html")
        .read_text()
        .replace('<lf-board id="b1">', '<lf-board id="b1" restated>')
    )
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "restated" in result.output and "lf-board" in result.output


def test_the_gate_reads_a_pick_the_same_way_it_reads_an_edit(page_dir):
    """The rule was built on drafts and boards; a pick is the case it was not
    built on. It lands the same way because nothing in it is per-widget: the
    subject is what the detail names, so a pick rests on the option picked. What
    the other options say is then free to change, and marking the pick `chosen`
    — the one thing every version does after a pick — says nothing, so it is
    invisible to the comparison.

    A chip is content rather than a mark, so writing one onto a picked option is
    changing what they picked and lands in the same comparison its prose does.
    The gate reads the version the way the anchor pass does, which is what keeps
    that true without anything here knowing a chip from a paragraph."""

    def write(version, **kw):
        opts = OPTIONS.format(
            **{
                "a": "",
                "b": "",
                "chip": "",
                "shim": "Fastest to ship.",
                "stage": "Table by table.",
                **kw,
            }
        )
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write(1)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )
    assert check(page_dir).exit_code == 0

    # A version may also incorporate the standing pick into authored markup.
    write(2, a=" chosen")
    assert check(page_dir, version=2).exit_code == 0, (
        "marking the pick is not a rewrite"
    )

    # An option nobody picked, rewritten freely.
    write(2, a=" chosen", stage="One table at a time, behind a flag.")
    assert check(page_dir, version=2).exit_code == 0, (
        "an unpicked option is free to change"
    )

    # The picked one, rewritten — the user chose those words.
    write(2, a=" chosen", shim="Fastest to ship, and we own the shim forever.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "o-shim" in result.output and "choose on r1" in result.output

    write(2, a=" chosen restated", shim="Fastest to ship, and we own the shim forever.")
    assert check(page_dir, version=2).exit_code == 0

    # A chip is a word on the page: one appearing on the option they picked reads
    # to them as the option changing, and is caught the same way its prose is.
    write(2, a=" chosen", chip="<lf-chip>effort: high</lf-chip>")
    result = check(page_dir, version=2)
    assert result.exit_code == 1, "a chip is words the user read"
    assert "o-shim" in result.output

    write(2, a=" chosen restated", chip="<lf-chip>effort: high</lf-chip>")
    assert check(page_dir, version=2).exit_code == 0

    # A later pick on the same coordinate releases the old option's words.
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-stage"]},
            "generated": [],
        },
    )
    write(2, b=" chosen", shim="The shim now has a bounded removal date.")
    assert check(page_dir, version=2).exit_code == 0


def test_a_later_pick_keeps_a_reader_added_option_live(page_dir):
    """An option generated by the reader survives without authored markup.
    The standing choice continues to carry its id and words in
    ``additions`` even after the reader picks a different option.  That mapped
    coordinate is therefore as live as an id named directly by ``options``:
    removing or silently rewriting it is refused until a version explicitly
    retracts it."""

    added = "g1-option-reader-route"

    def write(
        version, *, added_words="Use the reader's route.", attrs="", pick=" chosen"
    ):
        opts = OPTIONS.format(
            a="",
            b=pick,
            chip="",
            shim="Fastest to ship.",
            stage="Table by table.",
        )
        if added_words is not None:
            opts = opts.replace(
                "</lf-options>",
                f'<lf-option id="{added}"{attrs}>{added_words}</lf-option>'
                "</lf-options>",
            )
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write(1, added_words=None, pick="")
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {
                "options": [added],
                "additions": {added: "Use the reader's route."},
            },
            "generated": [added],
        },
    )
    # A subsequent ordinary pick supersedes the selection, but it carries the
    # complete generated-option set so those reader-authored words remain live.
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {
                "options": ["o-stage"],
                "additions": {added: "Use the reader's route."},
            },
            "generated": [added],
        },
    )

    assert state_json(page_dir)["state"][0]["detail"]["additions"] == {
        added: "Use the reader's route."
    }
    write(2, added_words=None)
    unchanged = check(page_dir, version=2)
    assert unchanged.exit_code == 0, unchanged.output

    # Reusing the id elsewhere is not carrying the generated option. Neither an
    # ordinary element elsewhere in the document nor a nested element inside the
    # group is the direct option unit the action says this widget owns.
    misplaced_markup = (
        ("</main>", f'<p id="{added}">Use the reader\'s route.</p></main>'),
        (
            "</lf-options>",
            f'<span id="{added}">Use the reader\'s route.</span></lf-options>',
        ),
    )
    for needle, replacement in misplaced_markup:
        write(2, added_words=None)
        source = page_dir / ".fixture-versions" / "v2.html"
        source.write_text(source.read_text().replace(needle, replacement))
        misplaced = check(page_dir, version=2)
        assert misplaced.exit_code == 1
        assert "direct children of their sending widgets" in misplaced.output
        assert added in misplaced.output

    write(2)
    carried = check(page_dir, version=2)
    assert carried.exit_code == 0, carried.output

    write(2, added_words="Use a rewritten route.")
    rewritten = check(page_dir, version=2)
    assert rewritten.exit_code == 1
    assert added in rewritten.output and "choose on r1" in rewritten.output

    write(2, added_words="Use a rewritten route.", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0
    assert stamp(page_dir, 2, "replace the reader-added option").exit_code == 0

    write(3, added_words=None)
    released = check(page_dir, version=3)
    assert released.exit_code == 0, released.output
    assert f"ids dropped from revision r2: ['{added}']" in released.output


def test_reader_added_words_do_not_become_liveness_coordinates(page_dir):
    """Prose that spells a sibling id remains prose.

    The additions map's keys are generated coordinates and its values are the words
    to carry.  Rewriting the unrelated option whose id those words happen to spell
    must therefore remain legal.
    """
    added = "g1-option-reader-route"

    def write(version, shim):
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
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    # The generated option is absent from the action's authored revision.
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {
                "options": ["o-stage"],
                "additions": {added: "o-shim"},
            },
            "generated": [added],
        },
    )

    write(2, "The shim now has a bounded removal date.")
    result = check(page_dir, version=2)
    assert result.exit_code == 0, result.output


def test_a_cleared_pick_rests_on_the_group_that_holds_it(page_dir):
    """Clearing a pick names no option (`{"options": []}`), so there is no part
    of the widget for the decision to rest on and it rests on the group. That
    falls out of the subject rule rather than being written for this case — which
    is why the group takes `restated` and a board, whose every move names a card,
    does not."""

    def write(version, shim="Fastest to ship.", attrs=""):
        opts = OPTIONS.format(a="", b="", chip="", shim=shim, stage="Table by table.")
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace(
                "<h2>Plan</h2>",
                "<h2>Plan</h2>"
                + opts.replace(
                    '<lf-options id="g1" choose>', f'<lf-options id="g1" choose{attrs}>'
                ),
            )
        )

    write(1)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": []},
            "generated": [],
        },
    )
    write(2, shim="Fastest to ship, and we own the shim forever.")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "lf-options id='g1'" in result.output

    write(2, shim="Fastest to ship, and we own the shim forever.", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0


def test_a_version_may_not_quietly_move_the_pick(page_dir):
    """The words gate can't see `chosen` — the attribute says nothing — so this
    is the state gate's own case: a version marking a different option than the
    user picked is overruling them as surely as a rewrite is, and says so
    with the group's `restated` or not at all. After the retraction the state is
    the author's again: the next version moves the pick freely, because a unit
    with no surviving folded action is exempt — that exemption is what keeps
    the retract-and-decision-again flow from deadlocking one version later."""

    def write(version, a="", b="", attrs="", shim="Fastest to ship."):
        opts = OPTIONS.format(a=a, b=b, chip="", shim=shim, stage="Table by table.")
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace(
                "<h2>Plan</h2>",
                "<h2>Plan</h2>"
                + opts.replace(
                    '<lf-options id="g1" choose>', f'<lf-options id="g1" choose{attrs}>'
                ),
            )
        )

    write(1)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )

    # The author's markup contradicting the recorded pick, words untouched.
    write(2, b=" chosen")
    result = check(page_dir, version=2)
    assert result.exit_code == 1
    assert "its state changed" in result.output
    assert "'o-stage'" in result.output and "'o-shim'" in result.output

    # Said out loud — on the group, the unit the fold keys the pick by.
    write(2, b=" chosen", attrs=" restated")
    assert check(page_dir, version=2).exit_code == 0, check(page_dir, version=2).output
    result = stamp(page_dir, 2, "moved the default")
    assert result.exit_code == 0, result.output

    # The retraction handed the state back: v3 owns it, no ritual to repeat.
    write(3, a=" chosen")
    assert check(page_dir, version=3).exit_code == 0, check(page_dir, version=3).output

    # And the words gate agrees the pick is dead: the group's retraction floors
    # everything resting inside it, so rewriting the once-picked option's words
    # is free — one key space for liveness, or the gate would demand a second
    # `restated` for a decision the browser already dropped.
    publish(page_dir, 3)
    write(4, a=" chosen", shim="Fastest to ship, and the shim is ours to keep.")
    assert check(page_dir, version=4).exit_code == 0, check(page_dir, version=4).output


def test_reader_state_survives_without_source_copying(page_dir):
    """An unchanged authored choice needs no transcription into a later revision.
    Validation stays quiet while state and the transcript preserve the answer."""

    def write(version, a=""):
        opts = OPTIONS.format(
            a=a, b="", chip="", shim="Fastest to ship.", stage="Table by table."
        )
        (page_dir / ".fixture-versions" / f"v{version}.html").write_text(
            PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
        )

    write(1)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )
    write(2)
    result = check(page_dir, version=2)
    assert result.exit_code == 0
    assert "record behind the log" not in result.output
    state = state_json(page_dir)
    assert state["state"][0]["detail"] == {"options": ["o-shim"]}
    assert state["decisions"] == []

    # Explicit incorporation is permitted but unnecessary for correctness.
    write(2, a=" chosen")
    result = check(page_dir, version=2)
    assert result.exit_code == 0
    assert "record behind the log" not in result.output

    result = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
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
        fixture_version_path(page_dir, 1).write_text(html)
        files_model.revision_path(page_dir, 1).write_text(html)
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
    stored = data_model.read_data(page_dir)
    updated = stored["sources"]["import-latency"]["updated"]

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
    """The file-side facet is the runtime's same ownership reading. An inner chosen
    option is not part of the outer group's record; a nested decision does not
    change the outer reader choice."""
    nested = """<lf-decision id="outer-decision"><h3>Which outer choices?</h3>
  <lf-options id="outer" choose multiple>
    <lf-option id="outer-a" chosen><strong>Outer A</strong>
      <lf-decision id="inner-decision"><h4>Which inner choice?</h4>
        <lf-options id="inner" choose>
          <lf-option id="inner-a" chosen>Inner A</lf-option>
          <lf-option id="inner-b">Inner B</lf-option>
        </lf-options>
      </lf-decision>
    </lf-option>
    <lf-option id="outer-b"><strong>Outer B</strong></lf-option>
  </lf-options>
</lf-decision>"""
    html = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + nested)
    (page_dir / ".fixture-versions" / "v1.html").write_text(html)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "outer",
            "action": "choose",
            "detail": {"options": ["outer-a"]},
            "generated": [],
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
    (page_dir / ".fixture-versions" / "v1.html").write_text(
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
    assert state["data"] == {"file": "data.json", "revision": 0}
    assert files_model.read_json(page_dir / state["data"]["file"]) == {
        "revision": 0,
        "sources": {},
    }
    assert state["event_seq"] == events_model.read_events(page_dir)[-1]["seq"]
    # The one asking group: PAGE's own bare <lf-options> takes no `choose`.
    assert state["decisions"] == [
        {"id": "g1-decision", "tag": "lf-decision", "thread": None}
    ]
    assert {"g1", "o-shim", "o-stage"} <= {el["id"] for el in state["elements"]}
    assert state["state"] == []

    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )
    state = state_json(page_dir)
    assert state["decisions"] == []
    assert state["state"] == [
        {
            "widget": "g1",
            "unit": "g1",
            "facet": "selection",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "revision": 1,
            "seq": 2,
            # On every entry, and null for a page widget: the key names which of the
            # page's two documents the decision was made in, and `asks` above has
            # carried it exactly this way all along.
            "thread": None,
        }
    ]
    assert state["pending"] == 1 and state["unacked"] == 1

    # Completion is an independent fact on the same widget. It stands beside
    # selection instead of superseding it, and both are visible to the agent.
    events_model.append_event(
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
    assert [
        (item["facet"], item["action"]) for item in state_json(page_dir)["state"]
    ] == [
        ("completion", "answer"),
        ("selection", "choose"),
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
    first = data_model.read_data(page_dir)
    assert first["revision"] == 1
    assert first["sources"]["deployments"]["contract"] == "deployment-rows"
    assert first["sources"]["deployments"]["revision"] == 1
    assert first["sources"]["deployments"]["value"] == ["api", "worker"]
    assert standing["data"] == {"file": "data.json", "revision": 1}
    assert "sources" not in standing["data"]
    assert standing["data_bindings"] == {
        "deployments": {
            "contract": "deployment-rows",
            "consumers": [
                {
                    "widget": "test-data",
                    "input": "data",
                    "document": "revision r2",
                }
            ],
        }
    }

    rejected = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "deployments"],
        input='{"api": "ready"}',
    )
    assert rejected.exit_code != 0
    assert "source 'deployments' value is invalid" in rejected.output
    assert state_json(page_dir)["data"] == {"file": "data.json", "revision": 1}
    assert data_model.read_data(page_dir) == first

    non_json = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "deployments"],
        input="NaN",
    )
    assert non_json.exit_code != 0
    assert "value is not JSON" in non_json.output
    assert state_json(page_dir)["data"] == {"file": "data.json", "revision": 1}
    assert data_model.read_data(page_dir) == first

    cleared = runner.invoke(
        cli_model.cli, ["data", "clear", str(page_dir), "deployments"]
    )
    assert cleared.exit_code == 0, cleared.output
    assert state_json(page_dir)["data"] == {"file": "data.json", "revision": 2}
    assert data_model.read_data(page_dir) == {
        "revision": 2,
        "sources": {"deployments": {"contract": "deployment-rows"}},
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


def test_text_capture_keeps_selected_snapshots_when_the_current_value_is_cleared(
    page_dir, tmp_path
):
    """Capture admits file text through the existing typed source boundary. The data
    revision names the immutable selection, while clear drops the replaceable value and
    any capture no immutable document selects."""
    declare_data_input(
        page_dir,
        "leaf-skill",
        {"type": "string"},
        contract="text-document",
        snapshot=True,
    )
    text_file = tmp_path / "SKILL.md"
    text_file.write_bytes(b"one\r\ntwo\r\nthree")
    runner = CliRunner()

    captured = runner.invoke(
        cli_model.cli,
        [
            "data",
            "capture",
            str(page_dir),
            "leaf-skill",
            "--file",
            str(text_file),
            "--lines",
            "2:3",
            "--label",
            "Leaf skill",
        ],
    )
    assert captured.exit_code == 0, captured.output
    assert "as snapshot 1" in captured.output
    stored = data_model.read_data(page_dir)
    source = stored["sources"]["leaf-skill"]
    assert source["value"] == "two\nthree"
    assert source["snapshots"] == {
        "1": {
            "updated": source["updated"],
            "value": "two\nthree",
            "label": "Leaf skill",
            "lines": "2:3",
        }
    }

    wrong_shape = runner.invoke(
        cli_model.cli,
        [
            "data",
            "capture",
            str(page_dir),
            "leaf-skill",
            "--file",
            str(text_file),
            "--format",
            "unified-diff",
            "--lines",
            "1:1",
        ],
    )
    assert wrong_shape.exit_code != 0
    assert "lines can only select part of a text capture" in wrong_shape.output
    assert data_model.read_data(page_dir) == stored

    index = page_dir / "index.html"
    index.write_text(
        index.read_text().replace(
            'source="leaf-skill"', 'source="leaf-skill" snapshot="1"'
        )
    )
    activated = revisioning_model.activate_source(
        page_dir, events_model.read_events(page_dir)
    )
    assert activated.error is None
    consumers = state_json(page_dir)["data_bindings"]["leaf-skill"]["consumers"]
    assert any(consumer.get("snapshot") == "1" for consumer in consumers)
    text_file.write_text("unreferenced")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)
    assert (
        data_model.read_data(page_dir)["sources"]["leaf-skill"]["snapshots"]["2"][
            "label"
        ]
        == "SKILL.md"
    )
    data_model.cmd_data_set(page_dir, "leaf-skill", "new current value")
    data_model.cmd_data_clear(page_dir, "leaf-skill")

    assert data_model.read_data(page_dir) == {
        "revision": 4,
        "sources": {
            "leaf-skill": {
                "contract": "text-document",
                "snapshots": source["snapshots"],
            }
        },
    }
    assert check(page_dir).exit_code == 0


def test_unified_diff_capture_builds_one_lazy_fragment_per_file(page_dir, tmp_path):
    declare_data_input(
        page_dir,
        "review-patch",
        {"type": "object"},
        contract="unified-diff",
        snapshot=True,
    )
    patch = tmp_path / "review.patch"
    patch.write_text(
        """diff --git a/app.py b/app.py
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
diff --git "a/caf\\303\\251 notes.py" "b/caf\\303\\251 notes.py"
--- "a/caf\\303\\251 notes.py"
+++ "b/caf\\303\\251 notes.py"
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
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "data",
            "capture",
            str(page_dir),
            "review-patch",
            "--file",
            str(patch),
            "--format",
            "unified-diff",
        ],
    )

    assert result.exit_code == 0, result.output
    source = data_model.read_data(page_dir)["sources"]["review-patch"]
    assert source["label"] == "review.patch"
    assert source["snapshots"]["1"]["label"] == "review.patch"
    assert source["snapshots"]["1"]["value"] == source["value"]
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
            "key": "café notes.py",
            "path": "café notes.py",
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


@pytest.mark.parametrize(
    ("patch_text", "message"),
    [
        (
            """diff --git a/logo.png b/logo.png
index 1234567..89abcde 100644
Binary files a/logo.png and b/logo.png differ
""",
            "unsupported hunkless diff",
        ),
        (
            """diff --git a/run.sh b/run.sh
old mode 100644
new mode 100755
""",
            "unsupported hunkless diff",
        ),
        (
            """diff --git a/source.py b/copied.py
similarity index 100%
copy from source.py
copy to copied.py
""",
            "unsupported copy diff",
        ),
        (
            """diff --git a/empty.txt b/empty.txt
new file mode 100644
index 0000000..e69de29
""",
            "unsupported hunkless diff",
        ),
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
def test_unified_diff_capture_rejects_evidence_the_widget_cannot_render(
    page_dir, tmp_path, patch_text, message
):
    declare_data_input(
        page_dir,
        "review-patch",
        {"type": "object"},
        contract="unified-diff",
    )
    patch = tmp_path / "unsupported.patch"
    patch.write_text(patch_text)

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "data",
            "capture",
            str(page_dir),
            "review-patch",
            "--file",
            str(patch),
            "--format",
            "unified-diff",
        ],
    )

    assert result.exit_code != 0
    assert message in result.output
    assert data_model.read_data(page_dir) == {"revision": 0, "sources": {}}


def test_a_document_cannot_select_a_missing_data_snapshot(page_dir):
    declare_data_input(
        page_dir,
        "leaf-skill",
        {"type": "string"},
        contract="text-document",
        snapshot=True,
    )
    index = page_dir / "index.html"
    index.write_text(
        index.read_text().replace(
            'source="leaf-skill"', 'source="leaf-skill" snapshot="17"'
        )
    )

    result = CliRunner().invoke(cli_model.cli, ["version", "check", str(page_dir)])

    assert result.exit_code != 0
    assert "selects snapshot '17'" in result.output
    assert "data.json does not contain it" in result.output


def test_data_set_can_capture_a_structured_value(page_dir, tmp_path):
    declare_data_input(
        page_dir,
        "builds",
        {"type": "object"},
        contract="build-map",
        snapshot=True,
    )
    payload = tmp_path / "builds.json"
    payload.write_text('{"main":"passing"}')

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "data",
            "set",
            str(page_dir),
            "builds",
            "--file",
            str(payload),
            "--capture-label",
            "release candidate",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "captured data source 'builds' at revision 1" in result.output
    source = data_model.read_data(page_dir)["sources"]["builds"]
    assert source["revision"] == 1
    assert source["value"] == {"main": "passing"}
    assert source["snapshots"]["1"] == {
        "updated": source["updated"],
        "value": {"main": "passing"},
        "label": "release candidate",
    }


def test_a_page_source_can_be_shared_but_cannot_change_contract_silently(page_dir):
    """The page owns concrete source identity. Seats may share one typed feed, while
    binding that id to a different meaning is refused before either the browser or a
    producer can reinterpret its standing value."""
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

    shared = CliRunner().invoke(cli_model.cli, ["version", "check", str(page_dir)])
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

    conflict = CliRunner().invoke(cli_model.cli, ["version", "check", str(page_dir)])
    assert conflict.exit_code != 0
    assert "bound to both contract 'rows'" in conflict.output
    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state.exit_code == 0, state.output
    reading = json.loads(state.output)
    assert reading["source"]["file"] == "index.html"
    assert reading["source"]["live"] is False
    assert "bound to both contract 'rows'" in reading["source"]["error"]
    assert reading["active"]["revision"] == 2


def test_clearing_a_value_does_not_let_a_later_version_reuse_its_source(page_dir):
    """Pinned versions share the page's current data store. Clearing removes a value,
    not the meaning of the source id that a stamped version still consumes."""
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
    publish(page_dir)
    data_model.cmd_data_set(page_dir, "project-feed", [])
    data_model.cmd_data_clear(page_dir, "project-feed")

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
    first = (page_dir / ".fixture-versions" / "v1.html").read_text()
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        first.replace("lf-test-data", "lf-other-data")
    )

    result = check(page_dir, 2)
    assert result.exit_code != 0
    assert "use a new source id for the new meaning" in result.output


def test_clear_keeps_source_identity_without_an_immutable_document(page_dir):
    """A mutable-only bootstrap can be cleared before its first reviewed version.
    The data tombstone still prevents the page-owned source id changing meaning."""
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

    with pytest.raises(data_contracts_model.DataError, match="standing snapshot uses"):
        data_model.cmd_data_set(page_dir, "project-feed", [])
    assert data_model.read_data(page_dir)["sources"]["project-feed"] == {
        "contract": "rows"
    }


def test_a_source_bound_only_by_frozen_reply_markup_can_be_set(page_dir):
    """A widget sent by an agent is still a data consumer. Its binding enters the
    page-lifetime index even though no authored version contains its seat."""
    declare_data_input(page_dir, "reply-feed", {"type": "array"}, contract="rows")
    version = page_dir / ".fixture-versions" / "v1.html"
    version.write_text(
        re.sub(r"<lf-test-data[^>]*></lf-test-data>\n?", "", version.read_text())
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "data-question",
            "author": "user",
            "revision": 1,
            "text": "Show the feed here.",
        },
    )
    reply = conversation_model.cmd_reply(
        page_dir,
        "data-question",
        "Here it is.",
        '<lf-test-data id="reply-data" source="reply-feed"></lf-test-data>',
    )

    data_model.cmd_data_set(page_dir, "reply-feed", [])
    standing = state_json(page_dir)
    assert standing["data"] == {"file": "data.json", "revision": 1}
    assert data_model.read_data(page_dir)["sources"]["reply-feed"]["contract"] == "rows"
    assert standing["data_bindings"]["reply-feed"]["consumers"] == [
        {
            "widget": "reply-data",
            "input": "data",
            "document": f"event {reply['id']!r} markup",
        }
    ]


def test_thread_markup_cannot_rebind_a_page_source(page_dir):
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
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
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "data-question",
            "author": "user",
            "revision": 1,
            "text": "Show another feed here.",
        },
    )

    with pytest.raises(SystemExit, match="use a new source id for the new meaning"):
        conversation_model.cmd_reply(
            page_dir,
            "data-question",
            "Here it is.",
            '<lf-other-data id="reply-data" source="project-feed"></lf-other-data>',
        )


def test_thread_markup_cannot_rebind_a_draft_only_page_source(page_dir):
    """The mutable source participates in the page currently being authored even before
    its binding reaches an immutable revision. A reply becomes immutable immediately, so
    admitting a different meaning there would leave set, clear, and source check reading
    a conflict the reply door itself allowed."""
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
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
    for revision in files_model.list_revisions(page_dir):
        path = files_model.revision_path(page_dir, revision)
        path.write_text(
            path.read_text().replace(
                '<lf-test-data id="test-data" source="project-feed"></lf-test-data>\n',
                "",
            )
        )
    documents = data_contracts_model.page_data_documents(
        page_dir, events_model.read_events(page_dir)
    )
    immutable, errors = data_contracts_model.merge_data_bindings(documents, registry)
    assert errors == [] and "project-feed" not in immutable
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "draft-data-question",
            "author": "user",
            "revision": 1,
            "text": "Show another feed here.",
        },
    )

    with pytest.raises(SystemExit, match="use a new source id for the new meaning"):
        conversation_model.cmd_reply(
            page_dir,
            "draft-data-question",
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

    assert data_model.read_data(page_dir) == {"revision": 0, "sources": {}}


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
    registry = json.loads((page_dir / "registry.json").read_text())

    with pytest.raises(
        data_contracts_model.DataError, match="recursive reference did not terminate"
    ):
        data_model.cmd_data_set(page_dir, "loop", {})

    assert data_contracts_model.data_contract_errors(
        {
            "revision": 1,
            "sources": {
                "loop": {
                    "contract": "loop",
                    "updated": "2026-08-25T12:00:00-07:00",
                    "value": {},
                }
            },
        },
        registry,
    ) == [
        (
            "source 'loop' contract 'loop' could not validate its value: "
            "a recursive reference did not terminate"
        )
    ]


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        ("null", "object with only revision and sources"),
        (
            (
                '{"revision":1,"sources":{"builds":{"contract":"build-map",'
                '"revision":1,"updated":"2026-08-25T12:00:00-07:00",'
                '"value":NaN}}}'
            ),
            "value is not JSON",
        ),
        (
            (
                '{"revision":1,"sources":{"builds":{"contract":"Bad Contract",'
                '"updated":"2026-08-25T12:00:00-07:00","value":[]}}}'
            ),
            "must contain a contract and only current value or snapshot fields",
        ),
        ('{"revision":-1,"sources":{}}', "revision must be a non-negative integer"),
        (
            (
                '{"revision":1,"sources":{"leaf-skill":{"contract":"text-document",'
                '"snapshots":{"2":{"updated":"2026-08-25T12:00:00-07:00",'
                '"value":"text","label":"SKILL.md"}}}}}'
            ),
            "invalid snapshot id '2'",
        ),
    ],
)
def test_the_data_store_refuses_non_contract_json(page_dir, stored, message):
    """A file on disk still crosses a structural boundary before it reaches the wire.

    Python's JSON reader admits `NaN`, and a JSON `null` is easy to confuse with a
    missing file. Neither can become a browser snapshot.
    """
    (page_dir / "data.json").write_text(stored)

    with pytest.raises(data_contracts_model.DataError, match=message):
        data_model.read_data_store(page_dir)


def test_the_data_store_wraps_invalid_utf8_at_its_boundary(page_dir):
    (page_dir / "data.json").write_bytes(b"\xff")

    with pytest.raises(data_contracts_model.DataError, match="invalid JSON"):
        data_model.read_data_store(page_dir)


def test_page_state_names_the_ask_region_but_keeps_state_on_its_request(page_dir):
    """The Decision list names the whole reading the reader arrives at. Its nested
    request remains the action owner, so answering it closes the broader Decision without
    moving the standing decision onto a wrapper that declares no state."""
    opts = """<lf-options id="g1" choose>
      <lf-option id="o-shim"><strong>Shim it</strong> Fastest to ship.</lf-option>
      <lf-option id="o-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
    </lf-options>"""
    ask = (
        '<lf-decision id="plan-decision"><h2>Plan</h2>'
        "<p>Choose after reading this framing.</p>"
        f"{opts}</lf-decision>"
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", ask)
    )
    publish(page_dir)

    state = state_json(page_dir)
    assert state["decisions"] == [
        {"id": "plan-decision", "tag": "lf-decision", "thread": None}
    ]

    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )
    state = state_json(page_dir)
    assert state["decisions"] == []
    assert state["state"][0]["widget"] == "g1"


def test_page_state_prefers_a_reader_action_over_a_report_on_the_same_facet(page_dir):
    """A report remains live for later absorption, but the reader's action is
    the effective state on their shared coordinate."""
    registry = json.loads((page_dir / "registry.json").read_text())
    options = registry["lf-options"]
    options["properties"]["overruled"] = {"type": "boolean"}
    report_choose = dict(options["x-state"]["choose"])
    report_choose.pop("creates")
    options["x-report"] = {"choose": report_choose}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    opts = OPTIONS.format(
        a="", b="", chip="", shim="Fastest to ship.", stage="Table by table."
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-stage"]},
            "generated": [],
        },
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "g1",
            "action": "choose",
            "detail": {"options": ["o-shim"]},
            "generated": [],
        },
    )

    state = state_json(page_dir)
    assert state["state"][0]["detail"] == {"options": ["o-shim"]}
    report = next(update for update in state["updates"] if update["source"] == "report")
    assert report["detail"] == {"options": ["o-stage"]}
    assert report["disposition"] == "standing"


def test_page_state_reads_an_authored_answer_with_no_log(page_dir):
    """A version that honors a pick in its markup reads as answered with no log
    at all — the shipped examples arrive that way."""
    opts = OPTIONS.format(a=" chosen", b="", chip="", shim="s.", stage="t.")
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + opts)
    )
    publish(page_dir)
    assert state_json(page_dir)["decisions"] == []


def test_page_state_keeps_thread_history_out_of_its_current_reading(page_dir):
    """State stays flat as a conversation grows; the exact-id event lookup owns its
    history while the append-only log remains the one copy of its prose."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    opened = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "cameras are flaky",
            "anchor": {"section": "s-1", "quote": "Ship dark"},
        },
    )
    answered = events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Indexer",
            "parent": opened["id"],
            "text": "two of them share a power rail",
        },
    )

    assert state_json(page_dir)["threads"] == [
        {
            "id": opened["id"],
            "anchor": {"section": "s-1", "quote": "Ship dark"},
            "resolved": None,
        }
    ]
    history = CliRunner().invoke(
        cli_model.cli, ["events", str(page_dir), "--thread", opened["id"]]
    )
    assert history.exit_code == 0, history.output
    assert [json.loads(line)["id"] for line in history.output.splitlines()] == [
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
            "events",
            str(page_dir),
            "--thread",
            opened["id"],
            "--after",
            str(opening_seq),
        ],
    )
    assert continued.exit_code == 0, continued.output
    assert [json.loads(line)["id"] for line in continued.output.splitlines()] == [
        answered["id"]
    ]
    unknown = CliRunner().invoke(
        cli_model.cli, ["events", str(page_dir), "--thread", "not-a-thread"]
    )
    assert unknown.exit_code != 0
    assert "unknown thread id 'not-a-thread'" in unknown.output


def test_page_state_points_to_a_readers_suggestion_record(page_dir):
    """`suggestion: true` is the reader proposing exact replacement words rather
    than describing a change, and the loop owes that a different answer — taken
    verbatim, or declined with a reason. State supplies the semantic membership and
    `events` supplies that raw flag without maintaining a second message shape."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    suggestion = events_model.append_event(
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
        cli_model.cli, ["events", str(page_dir), "--thread", thread["id"]]
    )
    assert history.exit_code == 0, history.output
    records = [json.loads(line) for line in history.output.splitlines()]
    assert [record["id"] for record in records] == [suggestion["id"]]
    assert records[0]["suggestion"] is True


def test_page_state_holds_a_thread_decision_open_until_its_verb(page_dir):
    """A widget in thread markup presents a Decision like one on the page; `until` holds a
    `multiple` group open across picks, and only the named verb closes it."""
    (page_dir / ".fixture-versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "Which mitigations?",
            "markup": '<lf-decision id="gm-decision"><h2>Which mitigations?</h2>'
            '<lf-options id="gm" choose multiple>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            '<lf-option id="m-alert"><strong>Alert</strong></lf-option>'
            "</lf-options></lf-decision>",
        },
    )
    assert state_json(page_dir)["decisions"] == [
        {"id": "gm-decision", "tag": "lf-decision", "thread": root["id"]}
    ]
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"options": ["m-cap"]},
            "generated": [],
        },
    )
    assert state_json(page_dir)["decisions"] == [
        {"id": "gm-decision", "tag": "lf-decision", "thread": root["id"]}
    ]
    events_model.append_event(
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
    assert state_json(page_dir)["decisions"] == []


def test_tasks_roll_up_explicit_requests_without_asking_themselves(page_dir):
    tasks = """<lf-tasks id="work">
      <lf-task id="vendor" status="blocked"><strong>Vendor fix</strong></lf-task>
      <lf-task id="copy" status="review"><strong>Copy review</strong></lf-task>
      <lf-task id="future" status="active"><strong>Future review</strong>
        <lf-decision id="future-decision"><h3>Review it now?</h3>
          <lf-options id="future-review" choose>
            <lf-option id="future-yes">Yes</lf-option><lf-option id="future-no">No</lf-option>
          </lf-options>
        </lf-decision>
      </lf-task>
      <lf-task id="decision" status="blocked"><strong>Reader decision</strong>
        <lf-decision id="decision-decision"><h3>Which way out?</h3>
          <lf-options id="decision-options" choose>
            <lf-option id="decision-a">A</lf-option><lf-option id="decision-b">B</lf-option>
          </lf-options>
        </lf-decision>
      </lf-task>
      <lf-task id="release" status="review"><strong>Release review</strong>
        <lf-task id="release-build" status="done"><strong>Build release</strong></lf-task>
      </lf-task>
    </lf-tasks>"""
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)

    assert state_json(page_dir)["decisions"] == [
        {"id": "future-decision", "tag": "lf-decision", "thread": None},
        {"id": "decision-decision", "tag": "lf-decision", "thread": None},
    ]


def test_page_state_carries_a_report_until_a_version_answers_it(page_dir):
    """A standing report updates task status without creating reader work, stands in
    the canonical update feed, and remains there as settled history when a note
    absorbs it."""
    tasks = (
        '<lf-tasks id="work"><lf-task id="t-parser" status="review">'
        "<strong>Parser</strong> Ready for eyes.</lf-task></lf-tasks>"
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + tasks)
    )
    publish(page_dir)
    assert state_json(page_dir)["decisions"] == []
    rep = events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "worker",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"status": "done"},
        },
    )
    state = state_json(page_dir)
    assert state["decisions"] == []
    assert state["updates"] == [
        {
            "id": rep["id"],
            "target": {"kind": "widget", "id": "t-parser"},
            "source": "report",
            "action": "status",
            "detail": {"status": "done"},
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
    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", "<h2>Plan</h2>" + tasks.replace('"review"', '"done"')
        )
    )
    files_model.write_revision(
        page_dir,
        2,
        (page_dir / ".fixture-versions" / "v2.html").read_bytes(),
    )
    (page_dir / "index.html").write_bytes(
        (page_dir / ".fixture-versions" / "v2.html").read_bytes()
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
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
            "detail": {"status": "done"},
            "text": None,
            "ts": rep["ts"],
            "revision": 1,
            "seq": 2,
            "agent": "worker",
            "session": None,
            "disposition": "settled",
        }
    ]
    assert state["decisions"] == []


def test_update_feed_orders_clock_ties_by_log_causality(page_dir, monkeypatch):
    """A claim sits after the log floor it observed and before the next event.
    Equal second-precision timestamps cannot reverse that known causal order."""
    task = (
        '<lf-tasks id="work"><lf-task id="t-parser" status="review">'
        "<strong>Parser</strong></lf-task></lf-tasks>"
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + task)
    )
    publish(page_dir)
    tied = "2026-08-24T12:00:00-07:00"
    monkeypatch.setattr(events_model, "now_iso", lambda: tied)
    first = events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"status": "done"},
        },
    )
    thread = events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    assert _status(page_dir, "working", "checking", "--on", thread["id"]).exit_code == 0
    claim_id = files_model.read_json(page_dir / "status.json")["work"][0]["id"]
    second = events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "revision": 1,
            "widget": "t-parser",
            "action": "status",
            "detail": {"status": "done"},
        },
    )

    updates = state_json(page_dir)["updates"]
    assert [(update["source"], update["id"]) for update in updates] == [
        ("report", first["id"]),
        ("claim", claim_id),
        ("report", second["id"]),
    ]


def test_page_state_before_first_stamp(page_dir):
    """An unstamped draft is still the live reading and has no public version."""
    state = state_json(page_dir)
    assert state["versions"] == []
    assert state["active"]["revision"] == 1
    assert state["active"]["version"] is None
    assert state["active"]["label"] == "Draft"
    assert state["elements"] and state["decisions"] == []
    assert state["title"] == "t"


def test_check_advises_where_a_users_aim_has_nothing_to_land_on(page_dir):
    """A block a user points at whole needs an id, or the aim falls through to
    the enclosing section — the failure item anchoring's own page shipped. Advice
    on a passing run, not a gate, and quiet where a tight wrapper (a figure around
    a table) already gives the aim something to hold."""
    blocks = (
        "<pre><code>uv run backfill --check</code></pre>"
        '<aside class="sidenote">The retry path is deliberately separate.</aside>'
        '<figure id="fig"><table><tr><td>1</td></tr></table></figure>'
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
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
    (page_dir / ".fixture-versions" / "v1.html").write_text(
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
        '<lf-command id="hub">'
        '<lf-task id="goal" status="blocked"><strong>Blocked goal</strong>'
        '<lf-specimen id="sample"><lf-options id="example" choose>'
        '<lf-option id="example-a"><strong>Example only</strong></lf-option>'
        "</lf-options></lf-specimen>"
        '<lf-decision id="real-decision"><h3>What next?</h3>'
        '<lf-options id="real" choose><lf-option id="real-a">A</lf-option>'
        '<lf-option id="real-b">B</lf-option></lf-options></lf-decision>'
        "</lf-task></lf-command>"
    )
    (page_dir / ".fixture-versions" / "v1.html").write_text(
        PAGE.replace("</section>", markup + "</section>")
    )
    publish(page_dir)
    assert state_json(page_dir)["decisions"] == [
        {"id": "real-decision", "tag": "lf-decision", "thread": None}
    ]


def test_page_state_and_browser_share_a_conditional_edit_decision(page_dir):
    """A draft uses the ordinary x-awaits fold: its edit discharges the decision,
    and an honoring version can clear the authored condition without reviving it."""

    def command(status, needed, body):
        flag = " needed" if needed else ""
        return (
            '<lf-command id="hub">'
            f'<lf-task id="goal" status="{status}"><strong>Import</strong>'
            f'<lf-draft id="cargo"{flag}><pre>\n{body}\n</pre></lf-draft>'
            "</lf-task></lf-command>"
        )

    version = page_dir / ".fixture-versions" / "v1.html"
    version.write_text(
        PAGE.replace("</section>", command("active", True, "paste") + "</section>")
    )
    publish(page_dir)
    assert state_json(page_dir)["decisions"] == [
        {"id": "cargo", "tag": "lf-draft", "thread": None}
    ]

    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "cargo",
            "action": "edit",
            "detail": {"text": "ledger_id,amount\n7,42"},
        },
    )
    assert state_json(page_dir)["decisions"] == []

    (page_dir / ".fixture-versions" / "v2.html").write_text(
        PAGE.replace(
            "</section>",
            command("active", False, "ledger_id,amount\n7,42") + "</section>",
        )
    )
    publish(page_dir, 2)
    assert state_json(page_dir)["decisions"] == []


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


def _palette(theme, block):
    """The series steps and the paper they sit on, read out of one scheme's token block."""
    steps = dict(re.findall(r"--series-(\d+):\s*(#[0-9a-f]{6})", block))
    paper = re.search(r"--paper:\s*(#[0-9a-f]{6})", block)[1]
    assert steps, "no series tokens in this block"
    return [steps[str(n)] for n in range(1, len(steps) + 1)], paper


def test_the_series_palette_clears_the_floors_it_claims_to():
    """The theme's comment beside these tokens tells the next editor to check them rather
    than look at them, and until this test there was nothing to check them with — the
    syntax roles have UNREAD_SYNTAX in the render gate and the series steps had the
    honour system. What made the argument was the first attempt at the line, chosen by
    eye: its blue and its plum came out 0.3 apart under simulated deuteranopia, which is
    one colour to a reader who has no way to tell us.

    Every pair rather than the neighbours, because a stacked bar puts any two of them
    edge to edge, and both palettes, because the dark steps are stepped against a
    brown-black rather than lightened from the light ones. The registry's $series.steps
    is counted against the tokens in the same breath: it is what a chart refuses a series
    past, and a palette one step longer than the number it publishes would refuse a
    series it has a colour for."""
    theme = (schema_model.ASSETS / "theme.css").read_text()
    light, dark = theme.split("prefers-color-scheme: dark")
    declared = json.loads((schema_model.ASSETS / "registry.json").read_text())[
        "$series"
    ]["steps"]

    for scheme, block in (("light", light), ("dark", dark)):
        steps, paper = _palette(theme, block)
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
    registry["lf-chip"]["x-parent"].append("lf-column")
    registry_file.write_text(json.dumps(registry))
    board = (
        '<lf-board id="reading-board">'
        '<lf-column id="reading-todo" label="To do">'
        '<lf-card id="reading-a">A</lf-card></lf-column>'
        '<lf-column id="reading-done" label="Done">'
        "<lf-chip>Already reviewed</lf-chip>"
        '<lf-card id="reading-b">B</lf-card></lf-column></lf-board>'
    )
    (page_dir / "index.html").write_text(before_choice(PAGE, board))
    initial = state_json(page_dir)
    assert initial["source"]["live"], initial["source"]["error"]
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": initial["active"]["revision"],
            "widget": "reading-board",
            "action": "move",
            "detail": {"card": "reading-a", "to": "reading-done", "index": 0},
        },
    )
    nodes = construction_nodes(state_json(page_dir)["content"])
    assert [
        (child["tag"], child["attrs"].get("id"))
        for child in nodes["reading-done"]["content"]
    ] == [("lf-chip", None), ("lf-card", "reading-a"), ("lf-card", "reading-b")]


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
        node = construction_nodes(state_json(page_dir)["content"])["reading-diff"]
        reading = node["inputs"]["document"]
        if isinstance(value, str):
            assert reading["value"] == patch
            assert "fragments" not in reading
        else:
            assert reading["value"] == {
                "files": [{key: field for key, field in file.items() if key != "patch"}]
            }
            assert reading["fragments"]["path"] == ["sources", "reading-patch", "value"]
        assert (
            data_model.read_data(page_dir)["sources"]["reading-patch"]["value"] == value
        )
