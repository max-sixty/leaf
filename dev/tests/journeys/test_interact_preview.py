"""Preview input readings and the user handoff's harness connection.

`leaf-dev preview` resolves three things from wherever its source sits: the
package layer, the companion media and pinned assets, and the paths a watcher
subscribes to. Input tests exercise those readings and shared page preparation. The user
handoff crosses the real claim and server boundaries, without
opening a browser.
"""

import json
import os
import re
import shutil
import subprocess
from functools import partial
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from interact_support import (
    ROOT,
    STATED_TIMEOUT,
    consume_pending_input,
    fetch,
    fetch_hanging_up,
    wait_for,
)

from leaf.base import server, service
from leaf.commands import cli as cli_model
from leaf.log.interaction_log import read_interactions
from leaf.pages import hosting
from leaf.records import transaction
from leaf.serving.user_views import USER_VIEWS
from leaf.source.registry.storage import layer_record
from leaf_dev.commands import preview
from leaf_dev.page_fixtures import read_fixture, record_run_context

from ..model.test_interact_preview import _ScriptedChanges


def test_preview_publishes_companion_edits_at_its_existing_url(
    tmp_path, monkeypatch, capsys, request
):
    """A custom widget edit publishes exact inputs without erasing feedback.

    Scripted input batches carry real companion edits through the running preview,
    its ordinary stamp door and HTTP delivery. Earlier executable resources retain
    their bytes, and a competing preview edit is refused until reconciled.
    """
    from leaf.base.files import latest_revision

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        '<body><main><h1>Reading</h1><lf-reading id="reading"></lf-reading>'
        "</main></body></html>"
    )
    (tmp_path / "layer.json").write_text("[]")
    companions = source.with_suffix(".page")
    widgets = companions / "widgets"
    widgets.mkdir(parents=True)
    (companions / "registry.json").write_text(
        json.dumps(
            {
                "lf-reading": {
                    "description": "A reading",
                    "attributes": {
                        "properties": {},
                        "required": ["id"],
                    },
                    "content": "empty",
                }
            }
        )
    )
    widget = widgets / "lf-reading.js"
    original = b"export const reading = 'Original';"
    revised = b"export const reading = 'Revised';"
    widget.write_bytes(original)
    page = tmp_path / "preview"

    def changes(watched):
        assert str(widget) in watched.paths
        [context] = [
            row for row in read_interactions(page) if row.get("type") == "run_context"
        ]
        assert context["purpose"] == "author-preview"
        assert context["run"] == str(page)
        assert context["authored_source"] == str(source)
        record_run_context(page, purpose="test", run=tmp_path, test=request.node.nodeid)
        contexts = read_interactions(page, types=("run_context",))
        url = next(
            line
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("http://")
        )

        def at(path):
            return fetch(urlsplit(url)._replace(path=path).geturl(), token=None)

        def resource():
            # Beneath the address the live document names for its resources.
            document = at("/")[1].decode()
            match = re.search(r'data-lf-entry="([^"]+)/leaf\.js"', document)
            assert match is not None
            return f"{match[1]}/page/widgets/lf-reading.js"

        first = latest_revision(page)
        old_resource = resource()
        assert at(old_resource) == (200, original)

        status, body = fetch(
            urlsplit(url)._replace(path="/api/event").geturl(),
            token=None,
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": first,
                    "text": "Keep this feedback",
                    "attempt": "preview-companion",
                }
            ).encode(),
        )
        assert status == 200, body
        before = (page / "events.jsonl").read_bytes()
        widget.write_bytes(revised)
        yield {str(widget)}
        second = latest_revision(page)
        assert second is not None and first is not None
        assert second > first
        assert at("/")[0] == 200
        assert at(resource()) == (200, revised)
        assert at(old_resource) == (200, original)
        assert (page / "events.jsonl").read_bytes().startswith(before)
        assert read_interactions(page, types=("run_context",)) == contexts

        delivered = page / "page/widgets/lf-reading.js"
        delivered.write_text("export const reading = 'Preview edit';")
        widget.write_text("export const reading = 'Another source edit';")
        yield {str(widget)}
        assert latest_revision(page) == second
        assert "Preview edit" in delivered.read_text()
        assert "reconcile" in capsys.readouterr().err

        delivered.write_bytes(revised)
        yield {str(widget)}
        current = latest_revision(page)
        assert current is not None and second is not None
        assert current > second
        assert "Another source edit" in delivered.read_text()

        # Removing a dependency is not published while the widget still imports it.
        helper = companions / "value.js"
        helper.write_text("export const value = 'Dependency';")
        widget.write_text("export { value } from '../value.js';")
        yield {str(widget), str(helper)}
        last = latest_revision(page)
        helper.unlink()
        yield {str(helper)}
        assert latest_revision(page) == last
        assert (page / "page/value.js").is_file()
        widget.write_bytes(revised)
        yield {str(widget)}
        current = latest_revision(page)
        assert current is not None and last is not None
        assert current > last
        assert not (page / "page/value.js").exists()
        assert at(old_resource) == (200, original)

        # A module can replace a directory of modules without stale empty folders.
        group = companions / "components.js"
        group.mkdir()
        (group / "value.js").write_text("export const value = 'Grouped';")
        widget.write_text("export { value } from '../components.js/value.js';")
        yield {str(widget), str(group / "value.js")}
        grouped = latest_revision(page)
        (group / "value.js").unlink()
        group.rmdir()
        group.write_text("export const value = 'Single';")
        widget.write_text("export { value } from '../components.js';")
        yield {str(widget), str(group)}
        current = latest_revision(page)
        assert current is not None and grouped is not None
        assert current > grouped
        assert (page / "page/components.js").is_file()

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_filters_feedback_before_discovering_inputs(tmp_path, monkeypatch):
    """Page-side writes must not rediscover the whole installed layer."""
    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    page = tmp_path / "preview"
    readings = []
    original = preview.watch_paths

    def read_inputs(*args):
        watched = original(*args)
        readings.append(watched)
        return watched

    def changes(_watched):
        count = len(readings)
        for path in (
            page / "observations.jsonl",
            USER_VIEWS.file(page / "user-views.json"),
        ):
            yield {str(path)}
            assert len(readings) == count
        source.write_text(source.read_text().replace("Reading</h1>", "Revised</h1>"))
        yield {str(source)}
        assert "Revised</h1>" in (page / "index.html").read_text()

    monkeypatch.setattr(preview, "watch_paths", read_inputs)
    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_refreshes_replaced_inputs_even_without_a_native_file_batch(
    tmp_path, monkeypatch
):
    """Files can change while the old root watch is revoked before rearming."""
    directory = tmp_path / "source"
    directory.mkdir()
    source = directory / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Original</h1></main></body></html>"
    )
    page = tmp_path / "preview"
    batches = []

    def replaced_input(_changes):
        if not batches:
            original = source.read_text()
            shutil.rmtree(directory)
            directory.mkdir()
            source.write_text(original.replace("Original</h1>", "Revised</h1>"))
            batches.append(True)
            return set()  # Only the bounded lifetime wake survives the replacement.
        assert "Revised</h1>" in (page / "index.html").read_text()
        raise StopIteration

    monkeypatch.setattr(preview.PreviewChanges, "__next__", replaced_input)
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_tracks_committed_layer_across_refused_source_edits(
    tmp_path, monkeypatch
):
    """Real preparation, vendoring and revision publication consume scripted events.

    The scripted filesystem stream batches real edits without relying on timing.
    A committed layer survives a later source refusal without being re-vendored on
    retry. Fixture-history edits do not block a concurrent layer update.
    """
    import os

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        '<body><main><h1>Reading</h1><p id="reading">Original</p></main></body></html>'
    )
    seed = source.with_suffix(".jsonl")
    seed.write_text("")
    package = tmp_path / "package"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    theme = package / "overrides.css"
    theme.write_text(":root { --proof: 1; }")
    (tmp_path / "layer.json").write_text(
        json.dumps(["./" + os.path.relpath(package, ROOT)])
    )
    page = tmp_path / "preview"

    def changes(_watched):
        def layer():
            return layer_record(page)

        before = layer()
        theme.write_bytes(theme.read_bytes())
        yield {str(theme)}
        assert layer()["generation"] == before["generation"]

        original = source.read_text()
        theme.write_text(":root { --proof: 2; }")
        source.write_text(
            original.replace("</main>", "<lf-undefined></lf-undefined></main>")
        )
        yield {str(theme), str(source)}
        committed = layer()
        assert committed["generation"] != before["generation"]
        assert (page / "index.html").read_text() == original

        source.write_bytes(source.read_bytes())
        yield {str(source)}
        assert layer()["generation"] == committed["generation"]

        theme.unlink()
        seed.write_text("\n")
        yield {str(theme), str(seed)}
        removed = layer()
        assert removed["generation"] != committed["generation"]

        seed.write_text("")
        source.write_text(original.replace("Original", "Revised"))
        yield {str(seed), str(source)}
        after = layer()
        assert after["generation"] == removed["generation"]
        assert "Revised" in (page / "index.html").read_text()

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)


def test_preview_follows_a_committed_package_after_a_source_refusal(
    tmp_path, monkeypatch
):
    """A failed source edit cannot hide edits to its newly installed package."""
    import os

    source = tmp_path / "pages/reading.html"
    source.parent.mkdir()
    original = (
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    source.write_text(original)
    manifest = source.parent / "layer.json"
    manifest.write_text("[]")
    package = tmp_path / "elsewhere/package"
    package.mkdir(parents=True)
    (package / "registry.json").write_text("{}")
    theme = package / "overrides.css"
    theme.write_text(":root { --package-proof: 1; }")
    selection = "./" + os.path.relpath(package, ROOT)
    page = tmp_path / "preview"
    subscriptions = []

    def changes(watched):
        subscriptions.append(watched)
        if len(subscriptions) == 1:
            assert str(theme) not in watched.paths
            manifest.write_text(json.dumps([selection]))
            source.write_text(
                original.replace("</main>", "<lf-undefined></lf-undefined></main>")
            )
            yield {str(manifest), str(source)}
            pytest.fail("Committed package did not rebuild the watch subscription")
        else:
            installed = layer_record(page)
            assert installed is not None
            assert installed["packages"] == ["./packages/package"]
            assert (page / "index.html").read_text() == original
            assert str(theme) in watched.paths
            assert any(
                root == package or root in package.parents for root in watched.roots
            )
            theme.write_text(":root { --package-proof: 2; }")
            yield {str(theme)}
            # The page's copy of the package takes the edit.
            assert (
                "--package-proof: 2"
                in (page / "packages" / "package" / "overrides.css").read_text()
            )

    monkeypatch.setattr(
        preview,
        "watch_changes",
        lambda watched: _ScriptedChanges(changes(watched), watched),
    )
    with pytest.raises(StopIteration):
        preview.serve_preview(source, page, ROOT / "bin/leaf", ROOT, False)
    assert len(subscriptions) == 2


def test_user_preview_restart_keeps_feedback_and_authored_progress(
    tmp_path, spawn, monkeypatch, request
):
    """A user slot resumes its durable page rather than replaying its fixture."""
    from leaf.base.files import latest_revision, revision_path
    from leaf.base.harness import session_harness
    from leaf.log.event_log import read_events
    from leaf.source.data import read_data
    from leaf.source.vocabulary import load_registry

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head><body><main>"
        '<h1>Initial reading</h1><lf-text-document id="receipt" source="receipt"></lf-text-document>'
        '<lf-group id="route-q" label="Which route?">'
        '<lf-options id="route"><lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-group>'
        "</main></body></html>"
    )
    source.with_suffix(".data.json").write_text('{"receipt":"Original value"}')
    package = tmp_path / "package"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    theme = package / "overrides.css"
    theme.write_text(":root { --proof: 1; }")
    (tmp_path / "layer.json").write_text(
        json.dumps(["default", "./" + os.path.relpath(package, ROOT)])
    )
    monkeypatch.setenv("LEAF_PREVIEWS_ROOT", str(tmp_path / "previews"))
    page = tmp_path / "previews" / "reading-user"
    valid_initial = source.read_text()
    source.write_text(
        valid_initial.replace("</main>", "<lf-undefined></lf-undefined></main>")
    )
    refused = subprocess.run(
        ["uv", "run", "leaf-dev", "preview", "--user", "--source", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0 and "unknown widget" in refused.stdout
    assert not page.exists()
    source.write_text(valid_initial)

    def start(number):
        log = tmp_path / f"preview-{number}.log"
        with log.open("w") as stream:
            task = spawn(
                ["uv", "run", "leaf-dev", "preview", "--user", "--source", str(source)],
                stdout=stream,
                stderr=subprocess.STDOUT,
            )

        def announced():
            assert task.poll() is None, log.read_text()
            return next(
                (
                    line
                    for line in log.read_text().splitlines()
                    if line.startswith("http://")
                ),
                None,
            )

        url = wait_for(
            announced,
            bool,
            failure=log.read_text,
            timeout=hosting.PORT_WAIT_SECONDS + STATED_TIMEOUT,
        )
        status, body = fetch_hanging_up(url)
        assert status == 200, body
        contexts = [
            row
            for row in read_interactions(page, types=("run_context",))
            if row["purpose"] == "user-review"
        ]
        assert len(contexts) == number
        assert {row["purpose"] for row in contexts} == {"user-review"}
        assert contexts[-1]["run"] == str(page)
        assert contexts[-1]["authored_source"] == str(source)
        record_run_context(page, purpose="test", run=tmp_path, test=request.node.nodeid)
        assert read_interactions(page, types=("run_context",))[-1]["purpose"] == "test"
        return task, url, log

    def stop(task):
        task.terminate()
        task.wait(timeout=STATED_TIMEOUT)

    task, url, _ = start(1)
    endpoint = urlsplit(url)._replace(path="/api/event").geturl()
    for entry in (
        {
            "kind": "comment",
            "revision": 1,
            "text": "Keep this feedback",
            "attempt": "restart-comment-0001",
        },
        {
            "kind": "action",
            "revision": 1,
            "widget": "route",
            "action": "choose",
            "detail": {"value": ["second"]},
            "answered": True,
            "attempt": "restart-choice-0001",
        },
    ):
        status, body = fetch_hanging_up(endpoint, json.dumps(entry).encode())
        assert status == 200, body
    harness = session_harness()
    assert harness is not None
    payload = consume_pending_input(harness.session)
    comment = next(
        event for event in payload["batches"][0]["events"] if event["kind"] == "comment"
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--title",
            "Restart keeps the reply",
            "--done",
            comment["answer"]["ref"],
            "--text",
            "Preserved reply",
        ],
    )
    assert reply.exit_code == 0, reply.output
    status, body = fetch_hanging_up(
        endpoint,
        json.dumps(
            {
                "kind": "comment",
                "revision": 1,
                "text": "Still pending across restart",
                "attempt": "restart-pending-0001",
            }
        ).encode(),
    )
    assert status == 200, body
    pending = read_events(page)[-1]["id"]
    before = (page / "events.jsonl").read_bytes()
    cursor = transaction.acknowledged(read_events(page))
    data = read_data(page, load_registry(page))
    first = latest_revision(page)
    layer = load_registry(page)["$layer"]["generation"]
    media = page / "media" / "retained.svg"
    media.parent.mkdir(exist_ok=True)
    media.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    media_bytes = media.read_bytes()
    stop(task)
    task, resumed, _ = start(2)
    assert resumed == url
    assert (page / "events.jsonl").read_bytes().startswith(before)
    assert transaction.acknowledged(read_events(page)) == cursor
    assert read_data(page, load_registry(page)) == data
    assert latest_revision(page) == first
    assert any(event.get("text") == "Preserved reply" for event in read_events(page))
    harness_2 = session_harness()
    assert harness_2 is not None
    delivered = consume_pending_input(harness_2.session)
    assert any(
        event["id"] == pending
        for batch in delivered["batches"]
        for event in batch["events"]
    )
    before = (page / "events.jsonl").read_bytes()
    cursor = transaction.acknowledged(read_events(page))
    stop(task)

    # A restart updates authored and runtime inputs, but never replays new seeds
    # over the existing log or changes data the page already holds.
    fictional = next(event for event in read_events(page) if event["kind"] == "comment")
    fictional = fictional | {"id": "fictional", "text": "A different fictional seed"}
    source.with_suffix(".jsonl").write_text(json.dumps(fictional) + "\n")
    source.with_suffix(".data.json").write_text('{"receipt":"Replacement seed"}')
    source.write_text(source.read_text().replace("Initial reading", "Revised reading"))
    theme.write_text(":root { --proof: 2; }")
    task, resumed, _ = start(3)
    assert resumed == url
    assert (page / "events.jsonl").read_bytes().startswith(before)
    assert all(event["id"] != "fictional" for event in read_events(page))
    assert transaction.acknowledged(read_events(page)) == cursor
    assert read_data(page, load_registry(page)) == data
    current = latest_revision(page)
    assert current is not None and first is not None
    assert current > first
    assert revision_path(page, first).is_file()
    assert load_registry(page)["$layer"]["generation"] != layer
    assert media.read_bytes() == media_bytes
    assert "Revised reading" in fetch_hanging_up(resumed)[1].decode()
    stop(task)

    # A rejected authored update leaves the old publication and its feedback live.
    valid_source = source.read_text()
    source.write_text(
        valid_source.replace("</main>", "<lf-undefined></lf-undefined></main>")
    )
    task, resumed, log = start(4)
    assert "Preview update refused" in log.read_text()
    assert "lf-undefined" not in (page / "index.html").read_text()
    assert (page / "events.jsonl").read_bytes().startswith(before)
    stop(task)
    source.write_text(valid_source)

    # Fixture progress is not the page's authority: the agent's own revision
    # survives an unchanged fixture and a runtime update while the watcher is away.
    agent_source = (
        (page / "index.html").read_text().replace("Revised reading", "Agent revision")
    )
    (page / "index.html").write_text(agent_source)
    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page), "--text", "Agent revision"]
    )
    assert stamped.exit_code == 0, stamped.output
    agent_revision = latest_revision(page)
    theme.write_text(":root { --proof: 3; }")
    task, resumed, _ = start(5)
    assert (page / "index.html").read_text() == agent_source
    assert agent_revision is not None
    assert revision_path(page, agent_revision).is_file()
    agent_revision = latest_revision(page)
    stop(task)

    # When both authors changed their inputs, restarting refuses the fixture's
    # overwrite and continues serving the agent's committed revision.
    source.write_text(valid_source.replace("Revised reading", "Competing fixture"))
    task, resumed, log = start(6)
    assert "reconcile" in log.read_text()
    assert (page / "index.html").read_text() == agent_source
    assert latest_revision(page) == agent_revision
    assert "Agent revision" in fetch_hanging_up(resumed)[1].decode()
    stop(task)

    # Reconciliation to the already-published page consumes the fixture update
    # without trying to stamp the same immutable revision again.
    source.write_text(agent_source)
    task, _, log = start(7)
    assert "Preview update refused" not in log.read_text()
    assert latest_revision(page) == agent_revision
    assert (page / "events.jsonl").read_bytes().startswith(before)
    stop(task)


@pytest.mark.parametrize("failure", ["prepare", "publish"])
@pytest.mark.parametrize("claimed", [False, True])
def test_fresh_preview_preparation_cannot_remove_a_successor(
    tmp_path, monkeypatch, failure, claimed
):
    """A complete private fixture can fail or lose its slot without owning it."""
    from leaf.base.harness import IDENTITY_VARIABLES

    source = tmp_path / "reading.html"
    source.write_text(
        "<!doctype html><html><head><title>Reading</title></head>"
        "<body><main><h1>Reading</h1></main></body></html>"
    )
    (tmp_path / "layer.json").write_text("[]")
    page = tmp_path / "preview"
    successor = preview.PreviewService(page, user=True)
    prepare = preview.prepare_page
    held = {}

    def prepare_before_successor(*args, **kwargs):
        result = prepare(*args, **kwargs)
        with monkeypatch.context() as context:
            if not claimed:
                for name in IDENTITY_VARIABLES:
                    context.delenv(name, raising=False)
            prepare(
                page,
                read_fixture(source),
                partial(preview.leaf, ROOT / "bin/leaf", ROOT),
            )
            with successor.starting() as url:
                held["url"] = url
            held["claim"] = service.page_claim(page)
            held["log"] = (page / "events.jsonl").read_bytes()
        if failure == "prepare":
            raise ValueError("fixture preparation refused")
        return result

    monkeypatch.setattr(preview, "prepare_page", prepare_before_successor)
    try:
        with pytest.raises(ValueError if failure == "prepare" else OSError):
            preview.run_preview(source, page, ROOT / "bin/leaf", ROOT, True)
        assert service.page_claim(page) == held["claim"]
        assert (page / "events.jsonl").read_bytes() == held["log"]
        assert (current := server.running_server(page)) is not None
        assert current["url"] == held["url"]
        assert fetch(held["url"], token=None)[0] == 200
    finally:
        successor.stop()
