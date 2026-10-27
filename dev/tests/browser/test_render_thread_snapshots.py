"""Developer tooling checks; run explicitly from dev/tests."""

import hashlib
import json
import shutil

import pytest
from leaf_dev.commands.thread_snapshots import COMPARED


@pytest.mark.skip(reason="paused: issue #4046, Resume the thread appearance gate")
@pytest.mark.skipif(not COMPARED, reason="thread appearance is reviewed on macOS")
def test_accept_publishes_only_a_successful_unchanged_capture(
    browser, thread_expected_store, tmp_path, monkeypatch
):
    """Publication consumes reviewed bytes; a partial or changed capture cannot publish."""
    from click.testing import CliRunner
    from leaf_dev import leaf_assets
    from leaf_dev.commands import thread_snapshots
    from leaf_dev.commands.thread_snapshots import accept, capture_files, render_profile

    profile = render_profile(browser.version)
    directory = tmp_path / "capture"
    shutil.copytree(thread_expected_store / profile, directory / profile)
    files = capture_files(directory, profile)
    baseline = tmp_path / "reviewed-expectations"
    shutil.copytree(thread_expected_store, baseline)
    (baseline / "another-profile").mkdir()
    retained = baseline / "another-profile/checkpoint.png"
    retained.write_bytes(b"this runtime's reviewed other profile")
    (baseline / profile / "obsolete.png").write_bytes(b"superseded checkpoint")
    monkeypatch.setattr(thread_snapshots, "expected_store", lambda: baseline)
    runner = CliRunner()
    published = []
    monkeypatch.setattr(
        leaf_assets,
        "stage",
        lambda *args, **kwargs: published.append((args, kwargs)) or tmp_path,
    )
    monkeypatch.setattr(
        leaf_assets, "publish", lambda *args: "reviewed-assets-revision"
    )
    assert runner.invoke(accept, [str(directory)]).exit_code != 0
    assert published == []
    (directory / "capture.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "sha256": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in files.items()
                },
            }
        )
    )
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code == 0, result.output
    staged, options = published[0]
    assert staged[0] == "tests/thread-snapshots"
    assert {
        name.removeprefix(f"{profile}/"): data
        for name, data in staged[1].items()
        if name.startswith(f"{profile}/")
    } == files
    assert staged[1]["another-profile/checkpoint.png"] == retained.read_bytes()
    assert f"{profile}/obsolete.png" not in staged[1]
    assert {
        name: data
        for name, data in staged[1].items()
        if not name.startswith(f"{profile}/")
    } == {
        path.relative_to(baseline).as_posix(): path.read_bytes()
        for path in baseline.rglob("*")
        if path.is_file() and path.relative_to(baseline).parts[0] != profile
    }
    assert options == {
        "replace_tree": True,
        "revision_key": "thread_snapshots_revision",
    }
    published.clear()
    image = next((directory / profile).glob("*.png"))
    image.write_bytes(image.read_bytes() + b"changed")
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code != 0 and "changed after" in result.output
    assert published == []
    image.unlink()
    result = runner.invoke(accept, [str(directory)])
    assert result.exit_code != 0 and "missing capture" in result.output
    assert published == []
