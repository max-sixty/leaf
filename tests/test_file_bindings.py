"""Explicit local-file grants, lossless saves, and the authenticated HTTP door."""

import hashlib
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
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
    MAX_FILE_BYTES,
    FileBindingError,
    StaleFileError,
    bind_file,
    read_file,
    save_file,
)
from leaf.state import state_home_path


def test_explicit_cli_binding_and_lossless_save(page_dir, tmp_path):
    target = tmp_path / "notes.md"
    target.write_bytes("# café\r\n\r\nhello\r\n".encode())
    target.chmod(0o640)
    result = CliRunner().invoke(
        cli, ["file", "bind", str(page_dir), "notes", str(target)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads((page_dir / "files.json").read_text()) == {
        "bindings": {"notes": str(target.resolve())}
    }
    original = read_file(page_dir, "notes")
    assert original["text"] == "# café\n\nhello\n"
    assert original["newline"] == "CRLF"
    saved = save_file(
        page_dir,
        "notes",
        {"revision": original["revision"], "text": "# café\nchanged\n"},
    )
    assert target.read_bytes() == "# café\r\nchanged\r\n".encode()
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert saved == read_file(page_dir, "notes")
    assert saved["bytes"] == len(target.read_bytes())
    assert saved["revision"] != original["revision"]
    target.write_text("external\n")
    with pytest.raises(StaleFileError) as stale:
        save_file(page_dir, "notes", {"revision": saved["revision"], "text": "mine\n"})
    assert stale.value.current["text"] == "external\n"
    assert target.read_text() == "external\n"


def test_file_saves_preserve_special_permission_bits(page_dir, tmp_path):
    target = tmp_path / "executable"
    target.write_text("original\n")
    snapshot = bind_file(page_dir, "executable", target)
    for mode in (0o2755, 0o6755, 0o1755):
        target.chmod(mode)
        assert stat.S_IMODE(target.stat().st_mode) == mode
        text = f"saved {mode:o}\n"
        snapshot = save_file(
            page_dir, "executable", {"revision": snapshot["revision"], "text": text}
        )
        assert target.read_text() == text
        assert stat.S_IMODE(target.stat().st_mode) == mode


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
        read_file(page_dir, str(target))
    with pytest.raises(FileBindingError):
        bind_file(page_dir, "../notes", target)
    snapshot = bind_file(page_dir, "notes", target)
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
    with pytest.raises(FileBindingError):
        read_file(page_dir, "notes")
    with pytest.raises(FileBindingError):
        save_file(
            page_dir, "notes", {"revision": snapshot["revision"], "text": "overwrite\n"}
        )
    assert substitute.read_bytes() == b"private\n"


def test_rebinding_cannot_apply_an_old_buffer_to_an_identical_other_file(
    page_dir, tmp_path
):
    first, second = tmp_path / "first.txt", tmp_path / "second.txt"
    first.write_text("same\n")
    second.write_text("same\n")
    original = bind_file(page_dir, "notes", first)
    rebound = bind_file(page_dir, "notes", second)
    assert rebound["revision"] != original["revision"]
    with pytest.raises(StaleFileError):
        save_file(
            page_dir,
            "notes",
            {"revision": original["revision"], "text": "old buffer\n"},
        )
    assert second.read_text() == "same\n"


def test_two_pages_share_one_target_write_lock(tmp_path, monkeypatch):
    from leaf import file_bindings

    target = tmp_path / "shared.txt"
    target.write_text("original\n")
    pages = [tmp_path / "one", tmp_path / "two"]
    for page in pages:
        page.mkdir()
        bind_file(page, "notes", target)
    revision = read_file(pages[0], "notes")["revision"]
    key = hashlib.sha256(os.fsencode(target)).hexdigest()
    waiting = lock_contention(monkeypatch, state_home_path() / "files" / f"{key}.lock")
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
    original = bind_file(page_dir, "notes", target)
    url = f"{server}/api/files/notes"
    assert fetch(url, token=None)[0] == 401
    assert json.loads(fetch(url)[1]) == original
    assert fetch(f"{server}/files.json")[0] == 404
    assert fetch(f"{server}/api/files/unbound")[0] == 400
    posted = json.dumps({"revision": original["revision"], "text": "edited\n"}).encode()
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
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 200, raw
    assert json.loads(raw) == read_file(page_dir, "notes")
    assert target.read_text() == "edited\n"
    status, raw = fetch(url, data=posted, headers={"Origin": server})
    assert status == 409
    assert json.loads(raw)["current"]["text"] == "edited\n"

    target.unlink()
    for operation in ({}, {"data": posted, "headers": {"Origin": server}}):
        status, raw = fetch(url, **operation)
        assert status == 400
        assert json.loads(raw)["error"].startswith("Could not access the bound file:")
        assert str(target.parent).encode() not in raw

    from leaf.files import latest_revision
    from leaf.hosting import LeafHTTPServer
    from leaf.http import page_endpoint
    from leaf.page_snapshot import capture_page_snapshot
    from leaf.revision_artifact import read_artifact, read_revision

    revision = latest_revision(page_dir)
    artifact = read_revision(page_dir, revision)
    assert "/files.json" not in read_artifact(page_dir, revision).resources
    snapshot = capture_page_snapshot(page_dir, artifact.document, revision, url="/")
    preview = LeafHTTPServer(
        ("127.0.0.1", 0), page_endpoint(page_dir, TOKEN, page_snapshot=snapshot)
    )
    with running_http_server(preview):
        address = f"http://127.0.0.1:{preview.server_address[1]}"
        assert fetch(f"{address}/files.json")[0] == 404
        assert fetch(f"{address}/api/files/notes")[0] == 403
        assert (
            fetch(
                f"{address}/api/files/notes", data=posted, headers={"Origin": address}
            )[0]
            == 403
        )
