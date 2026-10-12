"""Static document, version, and page-state tests."""

import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    OPTIONS,
    PAGE,
    SUGGESTION,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    asks_on_user,
    before_choice,
    check,
    decide,
    declare_data_input,
    fresh_process,
    publish,
    read_page_data,
    stamp,
    state_json,
    suggest,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import data_contracts as data_contracts_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import revision_artifact as artifact_model
from leaf import revisioning as revisioning_model
from model.test_interact_document import (
    _drop_x_between_a_and_b,
    _move,
    _todo_order,
    _write_board,
)


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
    publish(page_dir)
    assert _todo_order(page_dir) == ["a", "x", "b", "c"]


def test_a_version_that_writes_the_move_owns_its_order(page_dir):
    """Once a version writes the move, its markup is where the card stands: the rank
    no longer places it, and the move is no longer the user's to take back, since
    the markup would decide the order an undo restored."""
    move = _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, "naxbc")
    assert check(page_dir).exit_code == 0, check(page_dir).output
    publish(page_dir)
    assert _todo_order(page_dir) == ["n", "a", "x", "b", "c"]
    with pytest.raises(events_model.EventRefused, match="markup now places its unit"):
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": move["id"]}
        )


def test_a_later_version_can_reposition_a_card_without_retracting_its_move(page_dir):
    """Authored placements may change while the original move remains logged."""
    _drop_x_between_a_and_b(page_dir)
    _write_board(page_dir, "naxbc")
    publish(page_dir)
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
    publish(page_dir)
    _write_board(page_dir, "abc")
    (page_dir / "index.html").write_text(
        (page_dir / "index.html").read_text().replace("<h2>Plan</h2>", "<h2>Plans</h2>")
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


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


def test_suggestion_validates(page_dir):
    suggest(page_dir)
    assert check(page_dir).exit_code == 0, check(page_dir).output


def test_suggestion_resolves_accepts_a_real_comment(page_dir):
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    markup = '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p>x</p></lf-new></lf-suggestion>'
    (page_dir / "index.html").write_text(before_choice(PAGE, markup))
    assert check(page_dir).exit_code == 0


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
    publish(page_dir)
    (page_dir / "index.html").write_text(
        before_choice(
            PAGE.replace("<title>t</title>", "<title>t · v3</title>"), SUGGESTION
        )
    )
    publish(page_dir)
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


def test_publishing_records_typed_settlements_for_provisional_agent_facts(page_dir):
    """One durable relation ends both kinds of provisional agent information.
    Its typed targets keep report-event ids and widget-work ids distinct without
    growing one note field for each channel."""

    def add_board() -> None:
        path = page_dir / "index.html"
        path.write_text(
            path.read_text().replace(
                "</section>",
                '<lf-board id="rollout"><lf-column id="now" label="Now">'
                '<lf-card id="rollout-card"><strong>Ship</strong></lf-card>'
                "</lf-column></lf-board></section>",
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
        {"kind": "todo", "id": task["id"]},
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


def test_absorption_is_by_id_never_inferred_from_markup(page_dir):
    """A report whose value the stamped markup already shows stays news until a
    stamp settles it by id, and editing its target does not change that."""
    _tasks_version(page_dir, "review")
    publish(page_dir)
    assert _report(page_dir, "t-parser", "status", "value=review").exit_code == 0
    _tasks_version(page_dir, "done")
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert state_json(page_dir)["reports"][0]["disposition"] == "effective"


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
    assert asks_on_user(state) == []

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
    """A source write supplies an opaque run receipt, independent of the clock.
    The authored number is current when pinned to that receipt and stale after
    another write, even when the measured value is unchanged."""

    def write(run):
        measured = (
            '<p>The import takes <lf-num id="p95" source="import-latency" '
            f'run="{run}" via="uv run bench-import">184 ms</lf-num> at p95.</p>'
        )
        html = PAGE.replace("</main>", measured + "\n</main>")
        (page_dir / "index.html").write_text(html)
        return html[: html.index("<lf-num")].count("\n") + 1

    write("not-yet-measured")
    runner = CliRunner()

    def measure():
        result = runner.invoke(
            cli_model.cli,
            ["data", "set", str(page_dir), "import-latency"],
            input="184",
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.output)["run"]

    captured = measure()
    captured_line = write(captured)
    current = check(page_dir)
    assert current.exit_code == 0, current.output
    assert "measurement behind its source" not in current.output
    assert state_json(page_dir)["measurement_lag"] == []

    copied = page_dir.with_name("copied-measurement")
    shutil.copytree(page_dir, copied, copy_function=shutil.copy2)
    assert state_json(copied)["measurement_lag"] == []
    assert read_page_data(copied) == read_page_data(page_dir)

    later = measure()
    assert later != captured
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "measurement behind its source" in result.output
    assert captured in result.output and later in result.output
    assert state_json(page_dir)["measurement_lag"] == [
        {
            "tag": "lf-num",
            "widget": "p95",
            "line": captured_line,
            "source": "import-latency",
            "run": captured,
            "current_run": later,
        }
    ]

    rejected = runner.invoke(
        cli_model.cli,
        ["data", "set", str(page_dir), "import-latency"],
        input='{"value": 183}',
    )
    assert rejected.exit_code != 0
    assert "value is invalid" in rejected.output
    assert read_page_data(page_dir)["sources"]["import-latency"]["run"] == later

    write(later)
    current = check(page_dir)
    assert current.exit_code == 0, current.output
    assert "measurement behind its source" not in current.output
    assert state_json(page_dir)["measurement_lag"] == []

    write("")
    malformed = check(page_dir)
    assert malformed.exit_code != 0
    assert "non-empty" in malformed.output or "too short" in malformed.output


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
    assert (
        not stored.exists() if clear else json.loads(stored.read_text())["value"] == []
    )
    data_model.cmd_data_set(page_dir, "project-feed", {"ready": True})
    assert data_model.read_contracts(page_dir) == {"project-feed": "other-rows"}
    assert read_page_data(page_dir)["sources"]["project-feed"]["value"] == {
        "ready": True
    }
    historical = data_model.read_data(page_dir, old_registry)["sources"]["project-feed"]
    assert "error" in historical and "value" not in historical
    publish(page_dir)
    assert (
        state_json(page_dir)["data_bindings"]["project-feed"]["contract"]
        == "other-rows"
    )


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
        PAGE.replace("<main>", "<main><h1>Report</h1><p>The standalone summary.</p>")
        .replace("<h2>Plan</h2>", "<h2>Plan</h2>" + blocks)
        .replace("</main>", "<section><p>Unnamed aside.</p></section>\n</main>")
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    advice = [line for line in result.output.splitlines() if "unpointable" in line]
    assert len(advice) == 6, result.output
    assert any(
        "<h1>" in line and "nor anything enclosing it" in line for line in advice
    )
    assert (
        sum("<p>" in line and "nor anything enclosing it" in line for line in advice)
        == 2
    )
    assert any("<pre>" in line and "#plan" in line for line in advice)
    assert any("<aside>" in line and "#plan" in line for line in advice)
    assert any("<section>" in line for line in advice)
    assert not any(
        "<table>" in line for line in advice
    )  # the figure's id is aim enough

    # Prose inside an identified section needs no id of its own. Standalone
    # prose can be named directly or through a wrapper.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<main>",
            '<main><h1 id="title">Report</h1>'
            '<div id="summary"><p>The standalone summary.</p></div>',
        ).replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><pre id="cmd"><code>uv run backfill --check</code></pre>'
            '<aside class="sidenote" id="retry-note">The retry path is deliberately '
            "separate.</aside>",
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "unpointable" not in result.output


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
    files its reading asks for and no more: the document, registry and manifest.
    Inventory reads the manifest to exclude stale captures; active identity also
    reads it. The bounded metadata budget and filenames rule out materializing
    resource bodies, including after the bundle descriptor cache has evicted them.
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
            opens[int(found.group(1)), self.name] += 1
        return native_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    # A server started now: it holds none of this test's readings.
    with fresh_process():
        activated = revisioning_model.activate_source(page_dir)
    monkeypatch.undo()
    assert activated.error is None, activated.error
    assert not activated.created

    for revision in revisions:
        metadata = {
            name: count for (order, name), count in opens.items() if order == revision
        }
        marker = files_model.revision_path(page_dir, revision).name
        assert set(metadata) == {marker, "registry.json", "manifest.json"}
        assert metadata[marker] == metadata["registry.json"] == 1
        assert 1 <= metadata["manifest.json"] <= 2

