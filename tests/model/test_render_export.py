"""Preview and offline export tests."""

import base64
import gzip
import json

from click.testing import CliRunner
from interact_support import (
    PAGE,
    append_carried_log_record,
    append_command,
    publish,
    served_state_error,
)
from render_harness import (
    leaf_page,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import exporting as exporting_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import service as service_model
from leaf import session as session_model
from leaf.event_log import read_events
from leaf.files import published_versions
from leaf.served_state.service import PageStateService
from leaf.structure import SourceDocument
from leaf_dev.example_data import patch_manifest


def test_export_refuses_an_unstamped_version_without_replacing_the_destination(
    page_dir, tmp_path
):
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    output = tmp_path / "offline.html"
    output.write_text("Keep the existing export")
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(page_dir), "--version", "9", "--out", str(output)],
    )
    assert result.exit_code != 0
    assert "v9 is not stamped" in result.output
    assert output.read_text() == "Keep the existing export"


def test_export_refuses_server_dependent_samples(serve, tmp_path):
    serve(
        leaf_page(
            "Live sample",
            '<lf-sample id="practice" label="practice">'
            '<template id="practice-source" data-sample><h1>Child</h1></template>'
            "</lf-sample>",
        )
    )
    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "Live samples need a server" in result.output
    assert not output.exists()


def test_export_draft_captures_current_source_without_stamping(page_dir, tmp_path):
    source = page_dir / "index.html"
    source.write_text(
        PAGE.replace("</main>", '<h1 id="export-heading">First</h1></main>')
    )
    output = tmp_path / "offline.html"
    runner = CliRunner()
    args = ["page", "export", str(page_dir), "--out", str(output)]
    result = runner.invoke(cli_model.cli, [*args, "--draft"])
    assert result.exit_code == 0, result.output
    first = json.loads(result.output)
    assert first["version"] is None
    assert first["revision"] == 1
    assert '<h1 id="export-heading">First</h1>' in output.read_text()
    assert published_versions(page_dir, read_events(page_dir)) == []

    publish(page_dir)
    source.write_text(source.read_text().replace(">First</h1>", ">Second</h1>"))
    result = runner.invoke(cli_model.cli, args)
    assert result.exit_code == 0, result.output
    stamped = json.loads(result.output)
    assert stamped["version"] == 1
    assert stamped["revision"] == first["revision"]
    assert '<h1 id="export-heading">First</h1>' in output.read_text()

    result = runner.invoke(cli_model.cli, [*args, "--draft"])
    assert result.exit_code == 0, result.output
    draft = json.loads(result.output)
    assert draft["version"] is None
    assert draft["revision"] > first["revision"]
    assert '<h1 id="export-heading">Second</h1>' in output.read_text()
    assert published_versions(page_dir, read_events(page_dir)) == [1]


def test_export_draft_refuses_invalid_source_and_version_selection(page_dir, tmp_path):
    source = page_dir / "index.html"
    source.write_text(PAGE)
    publish(page_dir)
    output = tmp_path / "offline.html"
    output.write_text("Keep the existing export")
    args = ["page", "export", str(page_dir), "--out", str(output), "--draft"]
    result = CliRunner().invoke(cli_model.cli, [*args, "--version", "1"])
    assert result.exit_code != 0
    assert "--draft" in result.output and "--version" in result.output
    source.write_text("<main><lf-no-such-widget></lf-no-such-widget></main>")
    result = CliRunner().invoke(cli_model.cli, args)
    assert result.exit_code != 0
    assert "lf-no-such-widget" in result.output
    assert output.read_text() == "Keep the existing export"


def test_an_export_holds_each_data_value_once_outside_its_documents(serve, tmp_path):
    """A source's value and each deferred field are one gzipped body apiece, so no
    value rides the composed document through its parsers or reaches the file twice."""
    serve(
        leaf_page(
            "Data once",
            '<lf-text-document id="notes" source="notes" label="notes.md">'
            '</lf-text-document><lf-diff id="patch" source="review-patch"></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "notes", "NOTES_SENTINEL\n")
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        patch_manifest(
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            "@@ -1 +1 @@\n-PATCH_SENTINEL_OLD\n+PATCH_SENTINEL_NEW\n"
        ),
    )
    out = tmp_path / "data.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    exported = out.read_text(encoding="utf-8")
    package = SourceDocument(exported).tree.select_one("script[data-lf-export]")
    assert package is not None
    # gzip reads a run of gzipped bodies as one stream.
    bodies = "".join(
        gzip.decompress(base64.b64decode(resource["base64"])).decode()
        for resource in json.loads(package.text)["resources"].values()
        if resource["mime"] == "application/gzip"
    )
    for sentinel in ("NOTES_SENTINEL", "PATCH_SENTINEL_NEW"):
        # Counted, so a failure doesn't make pytest diff a file of megabytes.
        assert (exported.count(sentinel), bodies.count(sentinel)) == (0, 1)


def test_an_export_holds_the_page_and_nothing_of_the_conversation(claimed, tmp_path):
    """Whoever opens the file reads the page and the decisions on it, and no word of what
    the user and the agent said to each other, on screen or in its source.

    The passage a comment quotes is gone from the version exported, so it is in the file
    only if the conversation is. Everything planted stands in the page's live reading,
    which is what makes each absence mean something, and the attachment's bytes or a
    source only a message binds would be in an embedded body, so the search covers
    those decoded. A choice recorded on the page's widget stays, one the user took back
    stays taken back, and so does the data the page itself binds."""
    decisions = (
        '<lf-options id="picks"><lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options>'
        '<lf-options id="taken-back"><lf-option id="keep">Keep</lf-option>'
        '<lf-option id="drop">Drop</lf-option></lf-options>'
    )
    page_notes = (
        '<lf-text-document id="notes" source="page-notes" label="notes.md">'
        "</lf-text-document>"
    )
    source = claimed / "index.html"
    source.write_text(
        leaf_page(
            "Decisions",
            f'<h1>Decisions</h1><p id="passage">Words QUOTEDWORD here.</p>{decisions}'
            f"{page_notes}",
        )
    )
    publish(claimed, "FIRSTCHANGELOGWORD")

    attachment = tmp_path / "evidence.svg"
    attachment.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        "<text>ATTACHMENTWORD</text></svg>"
    )
    attached = media_model.cmd_media(claimed, [attachment])[0]["path"]
    choice = {"kind": "action", "author": "user", "revision": 1, "action": "choose"}
    chosen = append_command(
        claimed, {**choice, "widget": "picks", "detail": {"value": ["second"]}}
    )
    taken_back = append_command(
        claimed, {**choice, "widget": "taken-back", "detail": {"value": ["drop"]}}
    )
    append_command(
        claimed, {"kind": "undo", "author": "user", "undoes": taken_back["id"]}
    )
    comment = append_command(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": f"COMMENTWORD ![ALTWORD]({attached})",
            "anchor": {"section": "passage", "quote": "QUOTEDWORD"},
        },
    )
    said = {"author": "agent", "revision": 1, "parent": comment["id"]}
    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            **said,
            "text": "REPLYWORD",
            "markup": '<lf-options id="frozen"><lf-option id="yes">FROZENWORD'
            '</lf-option><lf-option id="PICKWORD">No</lf-option></lf-options>'
            '<lf-text-document id="in-thread" source="thread-notes" label="notes.md">'
            "</lf-text-document>",
        },
    )
    data_model.cmd_data_set(claimed, "thread-notes", "BOUNDINTHREADWORD\n")
    data_model.cmd_data_set(claimed, "page-notes", "PAGEDATAWORD\n")
    append_command(
        claimed, {**choice, "widget": "frozen", "detail": {"value": ["PICKWORD"]}}
    )
    append_carried_log_record(
        claimed,
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": comment["id"],
            "title": "TITLEWORD",
        },
    )
    todo = append_carried_log_record(
        claimed,
        {
            "kind": "todo",
            "author": "agent",
            "subject": {"kind": "page"},
            "title": "TODOWORD",
        },
    )
    append_carried_log_record(
        claimed,
        {"kind": "start", "author": "agent", "item": todo["id"], "text": "STATUSWORD"},
    )
    append_carried_log_record(
        claimed,
        {
            "kind": "plan",
            "author": "agent",
            "steps": [{"depth": 0, "title": "PLANWORD", "state": "working"}],
        },
    )
    source.write_text(
        leaf_page("Decisions", f"<h1>Decisions</h1>{decisions}{page_notes}")
    )
    publish(claimed, "SECONDCHANGELOGWORD")
    # What the agent is doing as the user exports reaches the live reading while its
    # wait lease stands.
    session_model.cmd_waiting(claimed)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path is not None
    lease = leases_model.take_wait_lease(lease_path)
    assert lease
    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "OBSERVEDWORD"}
        )

    words = [
        "QUOTEDWORD",
        "COMMENTWORD",
        "ALTWORD",
        "REPLYWORD",
        "FROZENWORD",
        "PICKWORD",
        "BOUNDINTHREADWORD",
        "TITLEWORD",
        "TODOWORD",
        "STATUSWORD",
        "PLANWORD",
        "OBSERVEDWORD",
        "FIRSTCHANGELOGWORD",
        "SECONDCHANGELOGWORD",
        # Where the agent's session works.
        str(tmp_path),
        attached,
    ]
    served = json.dumps(PageStateService(claimed).page_state(2))
    assert [word for word in words if word not in served] == []

    out = tmp_path / "shared.html"
    exporting_model.cmd_export(claimed, out, None)
    leases_model.release_lease(lease)
    exported = out.read_text(encoding="utf-8")
    package_script = SourceDocument(exported).tree.select_one("script[data-lf-export]")
    assert package_script is not None
    package = json.loads(package_script.text)
    bodies = [exported.encode()]
    for resource in package["resources"].values():
        body = base64.b64decode(resource["base64"])
        bodies.append(
            gzip.decompress(body) if resource["mime"] == "application/gzip" else body
        )
    held = b"\n".join(bodies)
    # Listed, so a failure doesn't make pytest diff a file of megabytes.
    assert [word for word in [*words, "ATTACHMENTWORD"] if word.encode() in held] == []
    assert b"PAGEDATAWORD" in held

    marker = SourceDocument(package["document"]).tree.select_one(
        "script[data-lf-offline]"
    )
    assert marker is not None
    state = json.loads(marker.text)["state"]
    assert {served_state_error(event, "Event") for event in state["events"]} == {None}
    projection = state["browser"]["views"]["2"]["document"]["projection"]
    assert projection["desired"] == [chosen["id"]]
    assert state["browser"]["views"]["2"]["thread"]["threads"] == []
