"""Explicit local-file grants, the files a state answer carries, lossless saves, and
the authenticated HTTP door."""

import json
import shutil
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    TOKEN,
    fetch,
    lock_contention,
    running_http_server,
)

from leaf.cli import cli
from leaf.file_bindings import (
    BINDINGS,
    MAX_FILE_BYTES,
    FileBindingError,
    StaleFileError,
    bind_file,
    bound_files,
    labels,
    save_file,
)
from leaf.locations import PATH_LOCKS, path_lock_key
from leaf.served_state.reading import page_reading


def test_explicit_cli_binding_and_lossless_save(page_dir, tmp_path):
    target = tmp_path / "notes.md"
    target.write_bytes("# café\r\n\r\nhello\r\n".encode())
    target.chmod(0o640)
    result = CliRunner().invoke(
        cli, ["file", "bind", str(page_dir), "notes", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "binding": "notes",
        "path": str(target.resolve()),
        "label": "notes.md",
        "bytes": target.stat().st_size,
    }
    assert BINDINGS.read(page_dir / "files.json") == {
        "bindings": {"notes": str(target.resolve())}
    }
    original = bound_files(page_dir)["notes"]
    assert original["text"] == "# café\n\nhello\n"
    saved = save_file(
        page_dir,
        "notes",
        {"revision": original["revision"], "text": "# café\nchanged\n"},
    )
    assert target.read_bytes() == "# café\r\nchanged\r\n".encode()
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    current = bound_files(page_dir)["notes"]
    assert (saved["text"], saved["revision"]) == (current["text"], current["revision"])
    assert saved["revision"] != original["revision"]
    target.write_text("external\n")
    with pytest.raises(StaleFileError) as stale:
        save_file(page_dir, "notes", {"revision": saved["revision"], "text": "mine\n"})
    assert stale.value.current["text"] == "external\n"
    assert target.read_text() == "external\n"


def test_each_bound_file_is_named_by_its_path_among_the_pages_files(page_dir, tmp_path):
    """One file reads as its name; several read as one tree below the deepest folder
    holding them all, which a navigator lists, and never as a host path."""
    for folder in ("deploy", "docs"):
        (tmp_path / folder).mkdir()
    values = tmp_path / "deploy" / "values.yaml"
    values.write_text("replicas: 3\n")
    runbook = tmp_path / "docs" / "runbook.md"
    runbook.write_text("# Runbook\n")
    assert bind_file(page_dir, "values", values)["label"] == "values.yaml"
    assert bind_file(page_dir, "runbook", runbook)["label"] == "docs/runbook.md"
    assert {
        binding: file["label"] for binding, file in bound_files(page_dir).items()
    } == {
        "values": "deploy/values.yaml",
        "runbook": "docs/runbook.md",
    }
    assert labels(
        {
            "a": Path("/home/ana/proj/README.md"),
            "b": Path("/srv/site/README.md"),
            "c": Path("/srv/site/notes.md"),
            "d": Path("/srv/site/notes.md"),
        }
    ) == {
        "a": "proj/README.md",
        "b": "site/README.md",
        "c": "notes.md",
        "d": "notes.md",
    }


def test_page_state_names_each_bound_file_for_the_agent(page_dir, tmp_path):
    """A later session finds the files a page's editors edit in `leaf page state`,
    by binding, under the name the page shows and the path to write."""
    (tmp_path / "deploy").mkdir()
    values = tmp_path / "deploy" / "values.yaml"
    values.write_text("replicas: 3\n")
    runbook = tmp_path / "runbook.md"
    runbook.write_text("# Runbook\n")
    bind_file(page_dir, "values", values)
    bind_file(page_dir, "runbook", runbook)
    result = CliRunner().invoke(cli, ["page", "state", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["files"] == {
        "runbook": {"label": "runbook.md", "path": str(runbook.resolve())},
        "values": {"label": "deploy/values.yaml", "path": str(values.resolve())},
    }


def test_a_file_in_the_page_directory_moves_with_the_page(page_dir, tmp_path):
    """A grant inside the page names its file from there, so a copy of the page,
    such as a published example in its visitor's container, edits its own copy. The
    copy's file reads as the same revision, so a save from the state the site
    published at build time lands in the container."""
    target = page_dir / "files" / "deploy" / "values.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("replicas: 3\n")
    bind_file(page_dir, "values", target)
    assert BINDINGS.read(page_dir / "files.json") == {
        "bindings": {"values": "files/deploy/values.yaml"}
    }
    published = bound_files(page_dir)["values"]
    copy = tmp_path / "copy"
    shutil.copytree(page_dir, copy)
    save_file(
        copy, "values", {"revision": published["revision"], "text": "replicas: 4\n"}
    )
    assert (copy / "files" / "deploy" / "values.yaml").read_text() == "replicas: 4\n"
    assert target.read_text() == "replicas: 3\n"


def test_file_saves_preserve_special_permission_bits(page_dir, tmp_path):
    target = tmp_path / "executable"
    target.write_text("original\n")
    bind_file(page_dir, "executable", target)
    snapshot = bound_files(page_dir)["executable"]
    for mode in (0o2755, 0o6755, 0o1755):
        target.chmod(mode)
        assert stat.S_IMODE(target.stat().st_mode) == mode
        text = f"saved {mode:o}\n"
        snapshot = save_file(
            page_dir, "executable", {"revision": snapshot["revision"], "text": text}
        )
        assert target.read_text() == text
        assert stat.S_IMODE(target.stat().st_mode) == mode


def test_cli_unbinding_revokes_open_editor_access_only_for_its_grant(
    server, page_dir, tmp_path
):
    target = tmp_path / "notes.txt"
    target.write_text("saved work\n")
    bind_file(page_dir, "notes", target)
    bind_file(page_dir, "other", target)
    state_url = f"{server}/api/state"
    files = json.loads(fetch(state_url)[1])["files"]
    assert set(files) == {"notes", "other"}
    original = files["notes"]
    before = page_reading(page_dir)

    for _ in range(2):
        result = CliRunner().invoke(cli, ["file", "unbind", str(page_dir), "notes"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {"binding": "notes", "bound": False}
    assert page_reading(page_dir) != before
    files = json.loads(fetch(state_url)[1])["files"]
    assert set(files) == {"other"}
    posted = json.dumps(
        {"revision": original["revision"], "text": "old draft\n"}
    ).encode()
    url = f"{server}/api/files/notes"
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 400
    assert json.loads(raw)["error"] == "No file is bound as 'notes'."
    assert target.read_text() == "saved work\n"
    assert files["other"]["text"] == original["text"]


def test_only_bound_supported_files_can_be_read_or_saved(page_dir, tmp_path):
    target = tmp_path / "file.txt"
    for content in (
        b"\xff",
        b"binary\0",
        b"mixed\r\nnew\n",
        b"old\r",
        b"x" * (MAX_FILE_BYTES + 1),
    ):
        target.write_bytes(content)
        with pytest.raises(FileBindingError):
            bind_file(page_dir, "notes", target)
    target.write_bytes(b"original\n")
    with pytest.raises(FileBindingError):
        bind_file(page_dir, "../notes", target)
    bind_file(page_dir, "notes", target)
    snapshot = bound_files(page_dir)["notes"]
    with pytest.raises(FileBindingError):
        save_file(page_dir, str(target), {"revision": snapshot["revision"], "text": ""})
    for body in (
        {},
        {"revision": snapshot["revision"], "text": 5},
        {"revision": "old", "text": ""},
        {"revision": snapshot["revision"], "text": "x", "path": str(target)},
        {"revision": snapshot["revision"], "text": "binary\0"},
        {"revision": snapshot["revision"], "text": "x" * (MAX_FILE_BYTES + 1)},
    ):
        with pytest.raises(FileBindingError):
            save_file(page_dir, "notes", body)
    assert target.read_bytes() == b"original\n"
    with pytest.raises(FileBindingError):
        bind_file(page_dir, "grants", page_dir / "files.json")
    substitute = tmp_path / "other.txt"
    substitute.write_bytes(b"private\n")
    target.unlink()
    target.symlink_to(substitute)
    swapped = bound_files(page_dir)["notes"]
    assert "text" not in swapped
    assert (
        swapped["error"] == "The bound file path now contains a symlink; bind it again."
    )
    with pytest.raises(FileBindingError):
        save_file(
            page_dir, "notes", {"revision": snapshot["revision"], "text": "overwrite\n"}
        )
    assert substitute.read_bytes() == b"private\n"


def test_two_pages_share_one_target_write_lock(tmp_path, monkeypatch):
    from leaf import file_bindings

    target = tmp_path / "shared.txt"
    target.write_text("original\n")
    pages = [tmp_path / "one", tmp_path / "two"]
    for page in pages:
        page.mkdir()
        bind_file(page, "notes", target)
    revision = bound_files(pages[0])["notes"]["revision"]
    waiting = lock_contention(monkeypatch, PATH_LOCKS / f"{path_lock_key(target)}.lock")
    replacing = Event()
    replace = file_bindings.replace_bytes

    def held_replace(writes):
        replacing.set()
        assert waiting.wait(STATED_TIMEOUT), (
            "second page did not wait on the target lock"
        )
        replace(writes)

    monkeypatch.setattr(file_bindings, "replace_bytes", held_replace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            save_file, pages[0], "notes", {"revision": revision, "text": "first\n"}
        )
        assert replacing.wait(STATED_TIMEOUT)
        second = executor.submit(
            save_file, pages[1], "notes", {"revision": revision, "text": "second\n"}
        )
        assert first.result(timeout=STATED_TIMEOUT)["text"] == "first\n"
        with pytest.raises(StaleFileError):
            second.result(timeout=STATED_TIMEOUT)
    assert target.read_text() == "first\n"


def test_http_file_door_requires_key_origin_and_current_revision(
    server, page_dir, tmp_path
):
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")
    bind_file(page_dir, "notes", target)
    original = bound_files(page_dir)["notes"]
    url = f"{server}/api/files/notes"
    assert fetch(url, data=b"{}", token=None)[0] == 401
    assert fetch(f"{server}/files.json")[0] == 404
    posted = json.dumps({"revision": original["revision"], "text": "edited\n"}).encode()
    assert (
        fetch(f"{server}/api/files/unbound", data=posted, headers={"Origin": server})[0]
        == 400
    )
    assert fetch(url, data=posted, headers={})[0] == 403
    assert (
        fetch(url, data=posted, headers={"Origin": "https://untrusted.example"})[0]
        == 403
    )
    assert (
        fetch(
            url, data=posted, headers={"Origin": server, "Leaf-View-Revision": "999"}
        )[0]
        == 403
    )
    assert fetch(url, data=b"[]", headers={"Origin": server})[0] == 400
    # A tab from before a restart under another runtime saves nothing: the answer
    # names this server's runtime, which the tab refuses and reloads on.
    status, raw = fetch(
        url, data=posted, headers={"Origin": server, "Leaf-Runtime": "0123456789abcdef"}
    )
    assert status == 200 and "layer" in json.loads(raw), raw
    assert target.read_text() == "hello\n"
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 200, raw
    assert json.loads(raw)["revision"] == bound_files(page_dir)["notes"]["revision"]
    assert target.read_text() == "edited\n"
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 409
    assert json.loads(raw)["current"]["text"] == "edited\n"

    target.unlink()
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 400
    assert json.loads(raw)["error"].startswith("Could not access the bound file:")
    assert str(target.parent).encode() not in raw
    error = json.loads(fetch(f"{server}/api/state")[1])["files"]["notes"]["error"]
    assert error.startswith("Could not access the bound file:")
    assert str(target.parent) not in error

    from leaf.files import latest_revision
    from leaf.hosting import LeafHTTPServer
    from leaf.http import page_endpoint
    from leaf.page_snapshot import capture_page_snapshot
    from leaf.revision_artifact import read_artifact, read_revision

    revision = latest_revision(page_dir)
    assert revision is not None
    artifact = read_revision(page_dir, revision)
    assert "/files.json" not in read_artifact(page_dir, revision).resources
    snapshot = capture_page_snapshot(page_dir, artifact.document, revision, url="/")
    preview = LeafHTTPServer(
        ("127.0.0.1", 0), page_endpoint(page_dir, TOKEN, page_snapshot=snapshot)
    )
    with running_http_server(preview):
        address = f"http://127.0.0.1:{preview.server_address[1]}"
        assert fetch(f"{address}/files.json")[0] == 404
        assert json.loads(fetch(f"{address}/api/state")[1])["files"] == {}
        assert (
            fetch(
                f"{address}/api/files/notes", data=posted, headers={"Origin": address}
            )[0]
            == 403
        )


def test_a_bound_file_write_moves_the_page_reading_and_the_file_in_state(
    server, page_dir, tmp_path
):
    """An editor takes its file from the page's state, so a write outside Leaf moves
    the reading a visible tab polls, and the state carries the new text, read again
    where the file's stamp moved. A write that puts back bytes the state carried
    before reads as the revision it carried then."""
    target = tmp_path / "notes.txt"
    target.write_text("hello\n")
    bind_file(page_dir, "notes", target)

    def files():
        return json.loads(fetch(f"{server}/api/state")[1])["files"]

    # The first state read activates the page, which moves its reading once.
    first = files()
    reading = page_reading(page_dir)
    assert set(first) == {"notes"}
    assert first["notes"]["text"] == "hello\n"
    assert (files(), page_reading(page_dir)) == (first, reading)

    target.write_text("edited outside Leaf\n")
    assert page_reading(page_dir) != reading
    assert files()["notes"]["text"] == "edited outside Leaf\n"

    target.write_text("hello\n")
    assert files() == first
