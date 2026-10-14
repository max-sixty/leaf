"""Live authoring judges inspect disposable pages; reports preserve arrival only."""

from contextlib import contextmanager

from leaf_dev import ROOT, arrangement_eval


def test_capture_preserves_arrival_without_operating_page(
    browser, tmp_path, monkeypatch
):
    original = tmp_path / "page"
    original.mkdir()
    source = """<!doctype html><main><h1>Saved page</h1>
      <details><summary>Evidence</summary><p>Required fact.</p></details></main>"""
    (original / "index.html").write_text(source)

    @contextmanager
    def existing_browser():
        yield browser

    monkeypatch.setattr(arrangement_eval, "chrome", existing_browser)
    monkeypatch.setattr(
        arrangement_eval,
        "WIDTHS",
        {
            "narrow": ((900, 600), "desktop"),
            "phone": ((390, 600), "phone"),
        },
    )
    run = arrangement_eval.Run(
        "document", ROOT, tmp_path, tmp_path / "shots", condition="html"
    )
    captured = arrangement_eval.capture_phase(run, 1, original)
    assert all(len(images) == 1 for images in captured.values())
    assert not (run.shots / "p1-observations.json").exists()
    assert (original / "index.html").read_text() == source
    assert list(original.iterdir()) == [original / "index.html"]
