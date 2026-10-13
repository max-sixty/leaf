"""Approved appearance across a real message delivery journey.

Run
``uv run pytest -n0 tests/*/test_render_thread_snapshots.py``. Baselines are
reviewed PNG images pinned in leaf-assets; run evidence stays in .tmp.
``leaf-dev thread-snapshots --help`` owns snapshot review and acceptance.
"""

import hashlib
import json
import shutil
import sys

import pytest
from leaf_dev.thread_snapshots import COMPARED
from render_harness import leaf_page, open_page


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux's fixed native font contract"
)
def test_linux_browser_resolves_the_fixed_fonts(browser, serve):
    """Native UI, serif and mono styles all use the faces the fixed fontconfig names."""
    faces = {
        "system-ui": ("DejaVu Sans", "DejaVuSans", "Oblique"),
        "serif": ("DejaVu Serif", "DejaVuSerif", "Italic"),
        "monospace": ("DejaVu Sans Mono", "DejaVuSansMono", "Oblique"),
    }
    styles = (
        ("normal", "normal"),
        ("bold", "normal"),
        ("normal", "italic"),
        ("bold", "italic"),
    )
    readings = {
        f"{name}-{weight}-{style}": (
            family,
            base
            + ("-" if weight == "bold" or style == "italic" else "")
            + ("Bold" if weight == "bold" else "")
            + (italic if style == "italic" else ""),
        )
        for name, (family, base, italic) in faces.items()
        for weight, style in styles
    }
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Font contract",
                "".join(
                    f'<p id="{name}">Native Leaf words 0123</p>' for name in readings
                ),
                head="<style>"
                + "".join(
                    f"#{name}-{weight}-{style} {{ font-family: {name}; "
                    f"font-weight: {weight}; font-style: {style}; }}"
                    for name in faces
                    for weight, style in styles
                )
                + "</style>",
            )
        ),
    )
    session = page.context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    root = session.send("DOM.getDocument")["root"]["nodeId"]
    for name, (family, postscript) in readings.items():
        node = session.send(
            "DOM.querySelector", {"nodeId": root, "selector": f"#{name}"}
        )["nodeId"]
        fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        assert {font["familyName"] for font in fonts} == {family}, (
            fonts,
            page.locator(f"#{name}").evaluate(
                "node => getComputedStyle(node).fontFamily"
            ),
        )
        assert all(not font["isCustomFont"] for font in fonts), fonts
        assert {font["postScriptName"] for font in fonts} == {postscript}, fonts
    session.detach()


@pytest.mark.skip(reason="paused: TODO.md, Resume the thread appearance gate")
@pytest.mark.skipif(not COMPARED, reason="thread appearance is reviewed on macOS")
def test_accept_publishes_only_a_successful_unchanged_capture(
    browser, thread_expected_store, tmp_path, monkeypatch
):
    """Publication consumes reviewed bytes; a partial or changed capture cannot publish."""
    from click.testing import CliRunner
    from leaf_dev import leaf_assets, thread_snapshots
    from leaf_dev.thread_snapshots import accept, capture_files, render_profile

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
