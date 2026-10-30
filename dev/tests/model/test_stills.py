"""Stills report failed catalogue states and compare the captures that complete."""

from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from PIL import Image

from leaf_dev.commands import stills


@pytest.fixture
def stills_catalogue(tmp_path, monkeypatch):
    """Replace build/server/browser boundaries, retaining the command, capture,
    drivers, screenshots, crops and style comparison. Image comparison stands in for
    its browser module, and each arm's page computes and declares its name as the
    root's colour, so this tests catalogue orchestration without launching a browser.
    """
    visited = []

    def assertions(page):
        visited.append(("assertions", page.url))
        if page.url == "base":
            raise AssertionError("Missing pasted image\nCall log: waiting for image")
        raise AssertionError

    def partial(page):
        visited.append(("partial", page.url))
        if page.url == "head":
            raise RuntimeError("Driver lost its target")

    def healthy(page):
        visited.append(("healthy", page.url))

    states = (
        stills.State("assertions", "fixture", assertions),
        stills.State("partial", "fixture", partial),
        stills.State("healthy", "fixture", healthy),
    )
    out = tmp_path / "stills"
    out.mkdir()
    arms = {arm: tmp_path / arm for arm in ("base", "head")}
    commits = {"base": "b" * 40, "head": "a" * 40}

    @contextmanager
    def serving_source(arm_dir, source, destination):
        yield arm_dir.name

    @contextmanager
    def tab(browser, viewport, scheme, touch, *, scale):
        page = SimpleNamespace(
            url="",
            screenshot=lambda *, path: Image.new("RGB", (4, 4), "white").save(path),
        )
        page.evaluate = lambda script, properties: {
            "faces": [[page.url, *[""] * (len(properties) - 1)]],
            "elements": {"html": 0},
        }
        yield page

    compared = []
    catalogue = SimpleNamespace(
        out=out,
        states=states,
        visited=visited,
        compared=compared,
        compare=lambda name: {"changed": 1, "regions": []},
    )

    @contextmanager
    def differences(browser, destination):
        def compare(name):
            compared.append(name)
            return catalogue.compare(name)

        yield compare

    monkeypatch.setattr(stills, "STATES", states)
    monkeypatch.setattr(stills, "run_directory", lambda path: out)
    monkeypatch.setattr(stills, "build_pair", lambda base_ref, scratch: (arms, commits))
    monkeypatch.setattr(stills, "serving_source", serving_source)
    monkeypatch.setattr(stills, "headless_shell", lambda: nullcontext("browser"))
    monkeypatch.setattr(stills, "tab", tab)
    monkeypatch.setattr(
        stills, "load", lambda page, address: setattr(page, "url", address)
    )
    monkeypatch.setattr(stills, "settle", lambda page: None)
    monkeypatch.setattr(
        stills,
        "declarations",
        lambda page: lambda key: [f"{key} {{ color: {page.url}; }}"],
    )
    monkeypatch.setattr(stills, "differences", differences)
    return catalogue


def test_a_failed_driver_preserves_other_states_and_both_arm_diagnostics(
    stills_catalogue, monkeypatch
):
    out = stills_catalogue.out
    states = stills_catalogue.states
    visited = stills_catalogue.visited
    compared = stills_catalogue.compared

    result = CliRunner().invoke(stills.stills)

    assert result.exit_code == 0, result.output
    assert visited == [
        (state.name, arm) for state in states for arm in ("base", "head")
    ]
    assert compared == ["healthy"]
    base_error = (out / "assertions" / "base-error.txt").read_text()
    assert "Traceback (most recent call last):" in base_error
    assert (
        "AssertionError: Missing pasted image\nCall log: waiting for image"
        in base_error
    )
    assert (
        (out / "assertions" / "head-error.txt").read_text().endswith("AssertionError\n")
    )
    assert (
        (out / "partial" / "head-error.txt")
        .read_text()
        .endswith("RuntimeError: Driver lost its target\n")
    )
    assert not (out / "partial" / "base-error.txt").exists()
    assert not list((out / "healthy").glob("*-error.txt"))
    assert (out / "partial" / "base.png").is_file()
    assert not (out / "partial" / "head.png").exists()
    assert all(
        (out / "healthy" / name).is_file()
        for name in (
            "base.png",
            "head.png",
            "base-crop.png",
            "head-crop.png",
            "diff.png",
        )
    )
    assert (out / "healthy" / "styles.txt").read_text() == (
        "color: base -> head  x1\n"
        "    html\n"
        "declarations that differ, on each group's first element\n"
        "    html\n"
        "        - html { color: base; }\n"
        "        + html { color: head; }\n"
    )
    assert result.output.replace(str(out), "<stills>") == (
        "base bbbbbbbbbb vs head aaaaaaaaaa\n"
        "  failed  assertions on base: Missing pasted image; on head: AssertionError\n"
        "  failed  partial on head: Driver lost its target\n"
        "  changed healthy: 1 px, 1 styles -> <stills>/healthy\n"
        "0 of 3 states unchanged\n"
        "files in <stills>\n"
    )

    def interrupted(page):
        raise KeyboardInterrupt

    monkeypatch.setattr(
        stills, "STATES", (stills.State("interrupt", "fixture", interrupted),)
    )
    compared.clear()
    result = CliRunner().invoke(stills.stills)
    assert result.exit_code != 0
    assert "Aborted!" in result.output
    assert not compared
    assert not list((out / "interrupt").glob("*-error.txt"))


@pytest.mark.parametrize("phase", ("comparison", "crop"))
def test_a_failed_analysis_preserves_later_comparisons_and_crops(
    stills_catalogue, monkeypatch, phase
):
    out = stills_catalogue.out
    monkeypatch.setattr(
        stills,
        "STATES",
        (
            stills.State("broken", "fixture", stills.at_rest),
            stills_catalogue.states[-1],
        ),
    )
    original_compare = stills_catalogue.compare
    original_crop = stills.crop
    cropped = []

    def compare(name):
        if phase == "comparison" and name == "broken":
            raise RuntimeError("Image decoding failed")
        return original_compare(name)

    def crop(folder, regions, *, framing):
        cropped.append(folder.name)
        if phase == "crop" and folder.name == "broken":
            raise RuntimeError("Crop writing failed")
        return original_crop(folder, regions, framing=framing)

    monkeypatch.setattr(stills_catalogue, "compare", compare)
    monkeypatch.setattr(stills, "crop", crop)

    result = CliRunner().invoke(stills.stills)

    assert result.exit_code == 0, result.output
    assert stills_catalogue.compared == ["broken", "healthy"]
    assert cropped == (["healthy"] if phase == "comparison" else ["broken", "healthy"])
    assert (out / "healthy" / "head-crop.png").is_file()
    assert (out / "healthy" / "diff.png").is_file()
    assert not (out / "broken" / "diff.png").exists()
    message = (
        "Image decoding failed" if phase == "comparison" else "Crop writing failed"
    )
    assert (
        (out / "broken" / "comparison-error.txt")
        .read_text()
        .endswith(f"RuntimeError: {message}\n")
    )
    assert result.output.replace(str(out), "<stills>") == (
        "base bbbbbbbbbb vs head aaaaaaaaaa\n"
        f"  failed  broken on comparison: {message}\n"
        "  changed healthy: 1 px, 1 styles -> <stills>/healthy\n"
        "0 of 2 states unchanged\n"
        "files in <stills>\n"
    )
