"""Discovery reuses frozen authoring evidence without changing benchmark results."""

import json

from click.testing import CliRunner

from leaf_dev.arrangement_eval import comparison_inputs
from leaf_dev.commands import eval_discover


def test_discovery_retains_observations_and_gaps_without_scoring(tmp_path, monkeypatch):
    """Only the model is replaced: selection, frozen roles and output storage are real.

    A rotated catalog name remains explorable, repeated attempts preserve their
    own evidence, and a native failure cannot become a completed observation.
    """
    run = tmp_path / "run"
    work = run / "samples" / "saved-document"
    work.mkdir(parents=True)
    (work / "prompt-1.txt").write_text("Original request")
    comparison = comparison_inputs("document-live-status", ("phone",))
    record = {
        "provider": {"label": "codex/candidate/workflow"},
        "response": {
            "metadata": {
                "work": str(work),
                "diagnostics": {
                    "subject": "retired-catalog-case",
                    "comparison": comparison,
                    "payload": "/original/runtime",
                    "condition": "leaf",
                    "phases": {
                        version: {
                            "page": str(work / f"page-phase{version}"),
                            "trace": {"reply": f"Delivered phase {version}"},
                        }
                        for version in comparison["phases"].values()
                    },
                },
            }
        },
    }
    (run / "results.json").write_text(json.dumps({"results": {"results": [record]}}))
    pairs = run / "pairs.json"
    pairs.write_text("Existing benchmark verdicts\n")
    original = (run / "results.json").read_bytes()

    response = {
        "output": {
            "status": "insufficient_evidence",
            "explored": "Desktop navigation; phone recording remains unsettled.",
            "observations": [
                {
                    "kind": "strength",
                    "summary": "Evidence remains beside the decision.",
                    "impact": "The reader can verify the premise while choosing.",
                    "viewport": [1600, 1000],
                    "steps": ["Open the decision."],
                    "evidence": ["desktop.png"],
                    "next": "Try a longer premise.",
                }
            ],
            "unverified": ["Phone recording did not complete."],
        },
        "metadata": {"trace": {"completed": True}},
    }

    def model(pages, widths, prompt, schema, evidence, *, handovers):
        assert set(pages) == {"page", "page_before_decision", "page_before_revision"}
        assert pages["page_before_decision"]["page"] == work / "page-phase3"
        assert pages["page_before_revision"]["page"] == work / "page-phase4"
        assert pages["page"]["page"] == work / "page-phase5"
        assert pages["page"]["payload"].as_posix() == "/original/runtime"
        assert pages["page"]["author_reply"] == "Delivered phase 5"
        assert pages["page_before_revision"]["author_reply"] == "Delivered phase 4"
        assert pages["page_before_decision"]["author_reply"] == "Delivered phase 3"
        assert widths == comparison["widths"]
        assert json.dumps(comparison, indent=2) in prompt
        assert "Investigate long decision premises" in prompt
        assert "overall" not in schema["properties"]
        assert evidence.is_dir()
        assert handovers == {"page": None}
        return response

    monkeypatch.setattr(eval_discover, "judge_pages", model)
    args = [str(run), work.name, "--focus", "Investigate long decision premises"]
    result = CliRunner().invoke(eval_discover.eval_discover, args)
    assert result.exit_code == 0, result.output
    saved = json.loads(next((run / "discovery").rglob("response.json")).read_text())
    assert saved["comparison"] == comparison
    assert saved["output"] == response["output"]

    response = {"error": "Native transport failed", "metadata": {"trace": {}}}
    result = CliRunner().invoke(eval_discover.eval_discover, args)
    assert result.exit_code != 0 and "Native transport failed" in result.output
    attempts = list((run / "discovery").rglob("response.json"))
    assert len(attempts) == 2
    assert any(json.loads(p.read_text()).get("error") for p in attempts)
    assert pairs.read_text() == "Existing benchmark verdicts\n"
    assert (run / "results.json").read_bytes() == original
