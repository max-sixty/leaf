"""Static document, version, and page-state tests."""

import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    PAGE_GROUP,
    _report,
    _tasks_version,
    append_carried_log_record,
    append_command,
    check,
    check_findings,
    decide,
    declare_data_input,
    declare_on_page,
    found,
    fresh_process,
    page_packages,
    publish,
    read_page_data,
    refused_on,
    stamp,
    state_json,
    suggest,
)
from model.test_interact_document import (
    _drop_x_between_a_and_b,
    _move,
    _todo_order,
    _write_board,
)

from leaf.base import files as files_model
from leaf.commands import agent_state as agent_state_model
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import page_data as page_data_model
from leaf.records import revisioning as revisioning_model
from leaf.source import data as data_model
from leaf.source import data_contracts as data_contracts_model
from leaf.source import revision_artifact as artifact_model
from leaf.source.vocabulary import load_registry


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
    """What the current document cannot take on in place, and nothing else.

    A user's open document keeps its module graph and its defined elements for as
    long as it lives, so the capture states which revisions can be given to that
    document and which need a new one. Words and styling can be given to it. The
    vocabulary that binds elements to modules, the module bytes, and the inline
    module bodies cannot. A new layer selection reaches the digest through its
    generation.
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
        assert activated.revision is not None
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

    declaration = load_registry(page_dir)["lf-options"]
    declaration["description"] = "Options this page declares for itself."
    (authored / "registry.json").write_text(json.dumps({"lf-options": declaration}))
    redeclared = activate()

    # The generation is what a tab speaks to the server (`runtime/transport/layer-client.js`),
    # so a new selection's gives the document a new executable. The re-selection
    # activates the source itself.
    extra = page_dir.parent / "extra"
    extra.mkdir()
    (extra / "overrides.css").write_text("/* another selection */\n")
    vendoring_model.cmd_init(page_dir, (*page_packages(), "./extra"))
    revision_2 = files_model.latest_revision(page_dir)
    assert revision_2 is not None
    reissued = artifact_model.read_artifact(page_dir, revision_2)
    assert reissued.digest != redeclared.digest
    assert reissued.executable != redeclared.executable


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
    with pytest.raises(events_model.EventRefused) as refused:
        append_command(
            page_dir, {"kind": "undo", "author": "user", "undoes": move["id"]}
        )
    assert refused_on(refused.value).code == "absorbed-move"


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


def test_a_later_authored_reorder_is_allowed_with_a_move_in_force(page_dir):
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
    status, findings = check_findings(page_dir)
    assert status == 1
    assert [(f.code, f.at, f.values["keyword"]) for f in findings] == [
        ("attribute-schema", "<lf-column>", "enum")
    ]
    assert "['ok', 'warn', 'danger']" in findings[0].values["reason"]

    # The list is the layer's, so a layer that adds one accepts it with no widget
    # touched — which is the point of $tones over an enum on each widget.
    declare_on_page(
        page_dir, lambda registry: registry["$tones"]["names"].append("dangre")
    )
    assert check(page_dir).exit_code == 0


def test_a_member_is_admissible_in_each_declared_owner(page_dir):
    """A package member can belong to different families without validator changes."""
    label = {
        "description": "A package's shared label.",
        "attributes": {"properties": {}},
        "content": "markup",
        "owners": ["lf-option", "lf-card"],
    }
    declare_on_page(page_dir, lambda registry: registry.__setitem__("lf-label", label))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            PAGE_GROUP,
            '<lf-board id="labels"><lf-column id="labels-column" label="Ideas">'
            '<lf-card id="labels-card"><lf-label>cheap</lf-label>A</lf-card>'
            "</lf-column></lf-board>" + PAGE_GROUP,
        ).replace(
            '<lf-option id="flag-first" label="Flag first">',
            '<lf-option id="flag-first" label="Flag first"><lf-label>small</lf-label>',
        )
    )
    assert check(page_dir).exit_code == 0, check(page_dir).output

    # And refused where neither holder is its parent, naming both.
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2><lf-label>stray</lf-label>")
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "not-member", "<lf-label>", owners=["lf-option", "lf-card"])


def test_flag_attribute_accepts_both_html_spellings(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="backfill-first" selected=""')
    )
    assert check(page_dir).exit_code == 0
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="backfill-first" selected="yes"')
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(
        findings, "attribute-schema", "<lf-option>", keyword="type", path=["selected"]
    )


def test_an_unanswered_proposal_may_become_authored_content(page_dir):
    # Self-accepting: the wrapper goes but its proposal stays, presented as
    # ordinary prose the user never agreed to. Withdrawal is whole or not.
    insert = """<lf-suggestion id="sug-thistle">
  <lf-new><p id="thistle-plan">Switch the north feeder to thistle in autumn.</p></lf-new>
</lf-suggestion>
    """
    suggest(page_dir, markup=insert)
    kept = PAGE.replace(
        PAGE_GROUP,
        '<p id="thistle-plan">Switch the north feeder to thistle in autumn.</p>'
        + PAGE_GROUP,
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
            PAGE_GROUP,
            '<p id="refill-rule">Refill every feeder each morning.</p>' + PAGE_GROUP,
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


def test_check_rejects_duplicate_ids(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace('id="backfill-first"', 'id="flag-first"')
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "duplicate-ids", ids=["flag-first"])


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
                '<lf-card id="rollout-card" label="Ship"><strong>Ship</strong></lf-card>'
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
        [
            "task",
            "create",
            str(page_dir),
            "rollout-card",
            "--title",
            "Check the rollout",
        ],
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
    status, findings = check_findings(page_dir)
    assert status == 0
    assert not found(findings, "measurement-lag")
    assert state_json(page_dir)["measurement_lag"] == []

    copied = page_dir.with_name("copied-measurement")
    shutil.copytree(page_dir, copied, copy_function=shutil.copy2)
    assert state_json(copied)["measurement_lag"] == []
    assert read_page_data(copied) == read_page_data(page_dir)

    later = measure()
    assert later != captured
    status, findings = check_findings(page_dir)
    assert status == 0
    assert found(
        findings,
        "measurement-lag",
        "<lf-num id=p95>",
        line=captured_line,
        source="import-latency",
        run=captured,
        current_run=later,
    )
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
    status, findings = check_findings(page_dir)
    assert status == 0
    assert not found(findings, "measurement-lag")
    assert state_json(page_dir)["measurement_lag"] == []

    write("")
    malformed = check(page_dir)
    assert malformed.exit_code != 0
    assert "non-empty" in malformed.output or "too short" in malformed.output


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
    page_data_model.cmd_data_set(page_dir, "project-feed", [])

    shared = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert shared.exit_code == 0, shared.output

    declare_other_rows(page_dir, "array")
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


def declare_other_rows(page_dir, kind):
    """Declare a second contract of `kind` and a test input bound to it."""

    def declare(registry):
        registry["$data"]["contracts"]["other-rows"] = {
            "description": "Another meaning.",
            "schema": {"type": kind},
        }
        registry["lf-other-data"] = {
            **registry["lf-test-data"],
            "description": "A differently typed test input.",
            "inputs": {"data": {"contract": "other-rows", "source": "source"}},
        }

    declare_on_page(page_dir, declare)


@pytest.mark.parametrize("clear", [False, True])
def test_a_later_version_can_reuse_a_source(page_dir, clear):
    """A changed binding replaces the publication's contract and value in one write.
    Captured old versions retain their own declaration and cannot accept new payloads.
    """
    declare_data_input(page_dir, "project-feed", {"type": "array"}, contract="rows")
    publish(page_dir)
    page_data_model.cmd_data_set(page_dir, "project-feed", [])
    if clear:
        page_data_model.cmd_data_clear(page_dir, "project-feed")

    declare_other_rows(page_dir, "object")
    first = (page_dir / "index.html").read_text()
    (page_dir / "index.html").write_text(first.replace("lf-test-data", "lf-other-data"))

    result = check(page_dir)
    assert result.exit_code == 0, result.output
    old_registry = artifact_model.read_revision(page_dir, 1).registry
    with pytest.raises(data_contracts_model.DataError, match="value is invalid"):
        page_data_model.cmd_data_set(page_dir, "project-feed", [])
    # A cleared source keeps no contract either.
    assert data_model.read_contracts(page_dir) == (
        {} if clear else {"project-feed": "rows"}
    )
    stored = data_model.PUBLICATION.file(
        data_model.source_file(page_dir, "project-feed")
    )
    assert (
        not stored.exists() if clear else json.loads(stored.read_text())["value"] == []
    )
    page_data_model.cmd_data_set(page_dir, "project-feed", {"ready": True})
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
    a table) already gives the aim something to hold. One id around several such
    blocks holds none of them: a comment aimed at one screenshot in a table of
    them lands on the table."""
    drawing = '<svg viewBox="0 0 8 8" role="img" aria-label="{}"><rect width="8" height="8" /></svg>'
    blocks = (
        "<pre><code>uv run backfill --check</code></pre>"
        "<aside>The retry path is deliberately separate.</aside>"
        '<figure id="fig"><table><tr><td>1</td></tr></table></figure>'
        '<table id="shots"><tr>'
        f"<td>{drawing.format('Before')}</td>"
        f"<td><figure>{drawing.format('After')}<figcaption>After</figcaption></figure></td>"
        '<td><figure><div id="named">A widget with an id</div></figure></td>'
        '<td><svg viewBox="0 0 8 8" aria-hidden="true"><rect width="8" height="8" /></svg>'
        '<img alt="" /></td>'
        "</tr></table>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("<main>", "<main><h1>Report</h1><p>The standalone summary.</p>")
        .replace("<h2>Plan</h2>", "<h2>Plan</h2>" + blocks)
        .replace("</main>", "<section><p>Unnamed aside.</p></section>\n</main>")
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    # One finding for each reason, listing its blocks in document order. The
    # figure's id is aim enough for its <table>. Two drawings in #shots share its aim.
    # A figure is left to what it holds, a drawing to name or something with an id,
    # and an icon or an image with an empty alt is no block a reader points at.
    assert sorted(
        (f.code, [(e["tag"], e.get("enclosing")) for e in f.values["elements"]])
        for f in findings
        if f.code.startswith("unpointable")
    ) == [
        ("unpointable", [("h1", None), ("p", None), ("p", None)]),
        ("unpointable-section", [("section", None)]),
        (
            "unpointable-wide",
            [("pre", "plan"), ("aside", "plan"), ("svg", "shots"), ("svg", "shots")],
        ),
    ]

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
            '<aside id="retry-note">The retry path is deliberately '
            "separate.</aside>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    assert not [f for f in findings if f.code.startswith("unpointable")]


def test_a_state_read_never_materializes_a_revision_bundle(page_dir, monkeypatch):
    """One request must not re-read the whole page history to answer.

    `GET /api/state` activates the source under the page's exclusive lock and then
    asks every revision in the history what its own document and registry said, for
    the ids, obligations and data bindings it declared. A revision bundle holds a couple of
    hundred resource files, so answering through `read_artifact` made one request
    cost the revision count times the bundle: seconds per request where the page
    directory is on a network filesystem, with every other reader queued behind the
    lock.

    The active revision is no exception: whether the source is that revision is a
    question for its manifest's digest, not its bundle. So each revision opens the
    files its reading asks for and no more: the document and registry, plus the
    active revision's manifest for its executable identity. The bounded metadata
    budget and filenames rule out materializing resource bodies, including after
    the bundle descriptor cache has evicted them.
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
        state = agent_state_model.cmd_page_state(page_dir)
    monkeypatch.undo()
    assert state["source"]["error"] is None, state["source"]
    assert state["active"]["revision"] == revisions[-1]

    *history, active = revisions
    for revision in history:
        metadata = {
            name: count for (order, name), count in opens.items() if order == revision
        }
        marker = files_model.revision_path(page_dir, revision).name
        # Its document, and its manifest for the vocabulary it selects.
        assert set(metadata) == {marker, "manifest.json"}
        assert metadata[marker] == metadata["manifest.json"] == 1
    active_metadata = {
        name: count for (order, name), count in opens.items() if order == active
    }
    marker = files_model.revision_path(page_dir, active).name
    assert set(active_metadata) == {marker, "manifest.json"}
    assert active_metadata[marker] == 1


import gc

from leaf.base import page_memory as page_memory_model
from leaf.serving import samples as samples_model


def test_a_page_keeps_its_readings_while_its_samples_live(page_dir):
    """A page serving samples keeps its readings while they live, so its own samples,
    each a page of their own, cannot push them out and leave every state answer to
    check and capture the whole source again."""
    template = '<template id="practice" data-sample><p>Child text.</p></template>'
    (page_dir / "index.html").write_text(PAGE.replace("</main>", template + "</main>"))
    revision = revisioning_model.activate_source(page_dir).revision
    with fresh_process():
        assert revision is not None
        held = artifact_model.read_revision(page_dir, revision)
        samples = samples_model.Samples()
        artifact = artifact_model.read_artifact(page_dir, revision)
        for _ in range(page_memory_model.PageMemories.LIMIT):
            samples.create(
                page_dir, artifact, held.document, [], {"sources": {}},
                "practice", None, None,
            )  # fmt: skip
        gc.collect()
        assert artifact_model.read_revision(page_dir, revision) is held


def test_check_advises_on_a_language_class_nothing_will_colour(page_dir):
    """Every block of code names its language one way, a `language-…` class, and one
    check reads every such class, a widget's as a native block's: a name the layer
    can't colour, a misspelling or a language it has no grammar for, is reported
    beside the page and refuses nothing, since the class still names the code truly.
    A grammar's alias, such as `py`, colours as its name does, and `math` names a
    formula, which the browser typesets."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2>\n"
            '<pre><code class="language-pythn">x = 1</code></pre>\n'
            '<pre><code class="language-py">y = 2</code></pre>\n'
            '<p>Its area is <code class="language-math">\\pi r^2</code>.</p>\n'
            '<lf-code id="walk-bad"><pre><code class="language-pythn">z = 3\n'
            "</code></pre></lf-code>\n"
            '<lf-text-document id="notes" source="notes" class="language-haskell">'
            "</lf-text-document>",
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    assert [
        (f.at, f.values["language"], f.severity)
        for f in found(findings, "uncoloured-language")
    ] == [
        ("<code>", "pythn", "advice"),
        ("<code>", "pythn", "advice"),
        ("<lf-text-document>", "haskell", "advice"),
    ]
