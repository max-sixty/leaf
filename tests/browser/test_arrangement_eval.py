"""Authoring captures show arrival, task inspection and real scrolling routes."""

from contextlib import contextmanager

from leaf_dev import ROOT, arrangement_eval


def test_capture_operates_disclosure_select_and_real_scroll_owners(browser, tmp_path):
    page = browser.new_page(viewport={"width": 390, "height": 600})
    page.set_content("""<!doctype html><style>html {scroll-behavior:smooth}</style><main>
      <details><summary>Evidence</summary><p style="margin-top:650px">Required tail.</p></details>
      <select id="threshold" onchange="document.querySelector('#note').hidden=this.value!=='5%'">
        <option>2%</option><option>5%</option></select><p id="note" hidden>Missed outage.</p>
      <div id="scroll" style="width:250px;overflow:auto"><div style="width:600px">Reachable end</div></div>
      <div id="clip" style="width:250px;overflow:clip"><div style="width:600px">Clipped end</div></div>
    </main>""")
    reading = arrangement_eval.capture_views(page, tmp_path, "p1-phone", lambda _: None)
    arrival = reading["states"][0]
    assert "Required tail" not in arrival["accessibility"]
    assert "Required tail" in arrival["reading"]["dom_text"]
    opened = [s for s in reading["states"] if s["action"] == "Open: Evidence"]
    assert any(s["reading"]["scroll_y"] > 0 for s in opened)
    assert any(
        "Missed outage" in s["accessibility"]
        for s in reading["states"]
        if s["action"] == "Inspect option: 5%"
    )
    assert page.locator("#threshold").input_value() == "2%"
    assert page.locator("#scroll").evaluate("el => el.scrollLeft") == 350
    assert page.locator("#clip").evaluate("el => el.scrollLeft") == 0
    assert not reading["limits"]


def test_capture_records_a_selection_that_cannot_be_restored(browser, tmp_path):
    page = browser.new_page(viewport={"width": 390, "height": 600})
    page.set_content("""<!doctype html><main>
      <select onchange="this.disabled=true"><option>A</option><option>B</option></select>
      <p>The page remains inspectable after the choice.</p></main>""")
    reading = arrangement_eval.capture_views(page, tmp_path, "p1-phone", lambda _: None)
    assert any("Restore original selection" in limit for limit in reading["limits"])
    assert any(s["action"] == "Restore original selection" for s in reading["states"])


def test_capture_preserves_original_and_each_viewport_arrival(
    browser, tmp_path, monkeypatch
):
    original = tmp_path / "page"
    original.mkdir()
    source = """<!doctype html><main><h1>Saved page</h1>
      <button aria-pressed="false" onclick="this.setAttribute('aria-pressed','true')">Inspect choice</button>
      <details><summary>Evidence</summary><p>Required fact.</p></details></main>"""
    (original / "index.html").write_text(source)

    @contextmanager
    def existing_browser():
        yield browser

    monkeypatch.setattr(arrangement_eval, "chrome", existing_browser)
    monkeypatch.setattr(
        arrangement_eval,
        "WIDTHS",
        {"narrow": ((900, 600), "desktop"), "phone": ((390, 600), "phone")},
    )
    run = arrangement_eval.Run(
        "document", ROOT, tmp_path, tmp_path / "shots", condition="html"
    )
    captured = arrangement_eval.capture_phase(run, 1, original)
    assert (original / "index.html").read_text() == source
    assert list(original.iterdir()) == [original / "index.html"]
    import json

    observations = json.loads((run.shots / "p1-observations.json").read_text())
    for width, reading in observations.items():
        assert reading["images"] == captured[width]
        assert "Required fact" not in reading["states"][0]["accessibility"]
        assert "[pressed]" not in reading["states"][0]["accessibility"]
        assert any("Required fact" in s["accessibility"] for s in reading["states"])
