"""The evaluator observes real controls without inventing access to clipped text."""

from leaf_dev.authoring_observation import observe


def test_disclosure_and_nested_scroll_are_observed_but_hidden_overflow_is_not(
    browser, tmp_path
):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.set_content("""<!doctype html><meta name="viewport" content="width=device-width">
      <details><summary>Daily measurements</summary><p>Tuesday latency: 7 ms.</p></details>
      <div id="readable" style="width:250px;overflow-x:auto">
        <div style="width:600px">Start<span style="float:right">Reachable end</span></div>
      </div>
      <div id="clipped" style="width:250px;overflow-x:hidden">
        <div style="width:600px">Start<span style="float:right">Unreachable end</span></div>
      </div>""")
    reading = observe(
        page, tmp_path, "phone", lambda _: None, destinations=["Daily measurements"]
    )
    arrival = reading["states"][0]
    assert "Tuesday latency" not in arrival["reading"]["accessibility"]
    opened = next(
        s
        for s in reading["states"]
        if s["action"].get("target") == "Daily measurements"
        and s["action"].get("outcome") == "operation_completed"
    )
    assert "Tuesday latency: 7 ms" in opened["reading"]["accessibility"]
    moved = next(s for s in reading["states"] if s["action"].get("owner") == "readable")
    assert (
        next(s for s in moved["reading"]["scrollers"] if s["id"] == "readable")["left"]
        > 0
    )
    assert any(s["id"] == "clipped" for s in arrival["reading"]["clipped"])
    positions = [
        next(o for o in s["reading"]["scrollers"] if o["id"] == "readable")["left"]
        for s in reading["states"]
        if s["action"].get("owner") == "readable"
    ]
    assert 0 < positions[0] < positions[-1] == 350
    assert page.locator("#clipped").evaluate("el => el.scrollLeft") == 0
    assert not reading["limitations"]


def test_task_destination_retains_its_revealed_below_fold_evidence(browser, tmp_path):
    page = browser.new_page(viewport={"width": 390, "height": 600})
    page.set_content("""<!doctype html>
      <details><summary>Measurements</summary>
        <p style="margin-top:650px">Required tail evidence</p>
      </details>""")
    reading = observe(
        page, tmp_path, "phone", lambda _: None, destinations=["Measurements"]
    )
    inspected = [s for s in reading["states"] if s["action"]["type"] == "destination"]
    assert any(s["reading"]["document"]["top"] > 0 for s in inspected)
    bounds = page.get_by_text("Required tail evidence").bounding_box()
    assert 0 <= bounds["y"] < bounds["y"] + bounds["height"] <= 600


def test_select_dependent_evidence_and_broken_tab_keep_their_observed_outcomes(
    browser, tmp_path
):
    page = browser.new_page(viewport={"width": 900, "height": 600})
    page.set_content("""<!doctype html><label>Threshold <select id="threshold"
      onchange="document.querySelector('#warning').hidden=this.value!=='5%'">
      <option value="1">1%</option><option>5%</option></select></label>
      <p id="warning" hidden>5% misses the September outage.</p>
      <button role="tab" aria-selected="false">Second ticket</button>
      <section role="tabpanel">First ticket detail.</section>""")
    reading = observe(page, tmp_path, "narrow", lambda _: None)
    selected = next(s for s in reading["states"] if s["action"]["type"] == "select")
    assert "5% misses the September outage" in selected["reading"]["accessibility"]
    assert page.locator("#threshold").input_value() == "1"
    clicked = next(
        s for s in reading["states"] if s["action"].get("label") == "Second ticket"
    )
    assert "First ticket detail" in clicked["reading"]["accessibility"]
    assert 'tab "Second ticket" [selected]' not in clicked["reading"]["accessibility"]
    assert clicked["action"]["outcome"] == "operation_completed"


def test_reobservation_preserves_recorded_inputs_and_original_artifact(
    browser, tmp_path, monkeypatch
):
    import json
    from contextlib import contextmanager

    from click.testing import CliRunner
    from leaf_dev import arrangement_eval, eval_observe
    from leaf_dev.authoring_score import sample_inputs
    from leaf_dev.eval_provenance import tree_identity

    run = tmp_path / "original"
    work = run / "samples" / "saved-sample"
    saved = work / "page-phase2"
    saved.mkdir(parents=True)
    (saved / "index.html").write_text(
        '<!doctype html><meta name="viewport" content="width=device-width">'
        "<details><summary>Historical evidence</summary><p>Original fact.</p></details>"
    )
    (work / "prompt-1.txt").write_text("Original recorded author turn.")
    (work / "authoring-inputs.json").write_text(
        json.dumps(
            {
                "request": "An archived request absent from today's case catalog.",
                "phases": {
                    "2": {"messages": ["Keep this historical preference."]},
                    "4": {"messages": ["A future decision; not applicable at 2."]},
                },
            }
        )
    )
    metadata = {
        "work": str(work),
        "provenance": None,
        "diagnostics": {
            "subject": "historical-custom",
            "phases": {
                "1": {"trace": {"minutes": 1, "cost_usd": 1, "turns": 1}},
                "2": {
                    "captures": {},
                    "trace": {"minutes": 2, "cost_usd": 2, "turns": 1},
                },
                "4": {},
            },
        },
    }
    original = {
        "results": {
            "results": [
                {
                    "provider": {"label": "html"},
                    "response": {"metadata": metadata},
                    "gradingResult": {"pass": False},
                    "success": False,
                }
            ]
        }
    }
    (run / "results.json").write_text(json.dumps(original))
    before = tree_identity(run)

    @contextmanager
    def existing_browser():
        yield browser

    monkeypatch.setattr(arrangement_eval, "chrome", existing_browser)
    output = tmp_path / "observed"
    result = CliRunner().invoke(
        eval_observe.eval_observe,
        [
            str(run),
            "--phase",
            "2",
            "--output",
            str(output),
            "--destination",
            "Historical evidence",
        ],
    )
    assert result.exit_code == 0, result.output
    assert tree_identity(run) == before
    row = json.loads((output / "results.json").read_text())["results"]["results"][0]
    assert "gradingResult" not in row and "success" not in row
    updated = row["response"]["metadata"]
    assert set(updated["diagnostics"]["phases"]) == {"1", "2"}
    # Future source edits cannot change the task the observed packet answers.
    (work / "authoring-inputs.json").write_text("{}")
    inputs = sample_inputs(updated, output)
    assert inputs["request"] == "An archived request absent from today's case catalog."
    assert inputs["messages"] == ["Keep this historical preference."]
    assert inputs["provenance"]["reobservation"]["server_payload"] is None
    assert (
        inputs["provenance"]["reobservation"]["server"]["kind"] == "python-static-http"
    )
    for width in inputs["observations"]["widths"].values():
        assert width["states"][0]["origin"] == "authored_arrival"
        assert "Original fact" not in width["states"][0]["reading"]["accessibility"]
        assert any(
            "Original fact" in s["reading"]["accessibility"] for s in width["states"]
        )
    assert all(str(output) in p for paths in inputs["captures"].values() for p in paths)
    from leaf_dev.eval_pairs import samples
    from leaf_dev.eval_report import measures

    archived = samples([output])["historical-custom"]["html"][0]
    assert measures(archived, "historical-custom")["cost"] == 3
