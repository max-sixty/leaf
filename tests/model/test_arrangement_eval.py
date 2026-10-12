"""Product controls really render ordinary HTML; judges read real screenshots."""

import json

from leaf_dev.arrangement_eval import WIDTHS


def test_pairwise_counts_only_a_winner_both_orders_name(tmp_path, monkeypatch):
    """No model runs: a judge that always prefers position A splits every pair, and
    one that prefers a column's page wins it in both orders."""
    from click.testing import CliRunner
    from leaf_dev import eval_pairs

    run = tmp_path / "run"
    results = []
    for column in ("claude-code/candidate/workflow", "claude-code/html/workflow"):
        work = run / "samples" / f"document-{column.split('/')[1]}"
        work.mkdir(parents=True)
        (work / "prompt-1.txt").write_text("")
        shots = run / "screenshots" / work.name
        shots.mkdir(parents=True)
        for name in WIDTHS:
            (shots / f"p3-{name}-0.png").write_bytes(b"")
        results.append(
            {
                "provider": {"label": column},
                "response": {
                    "metadata": {
                        "work": str(work),
                        "diagnostics": {"subject": "document"},
                    }
                },
            }
        )
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))

    def judging(prefer):
        def model(cwd, prompt, *args, out, err, **kwargs):
            brief = (out.parent / "brief.md").read_text()
            a = brief.split("Page A:")[1].split("Page B:")[0]
            winner = prefer(a)
            schema = json.loads(args[args.index("--json-schema") + 1])
            verdict = {
                **dict.fromkeys(eval_pairs.ASPECTS, "tie"),
                "overall": winner,
                "margin": "clear",
                "defects_A": [],
                "defects_B": [],
                "reason": "",
            }
            assert set(verdict) == set(schema["required"])
            return [{"type": "result", "structured_output": verdict}]

        return model

    monkeypatch.setattr(eval_pairs, "run_agent", judging(lambda a: "A"))
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    assert json.loads((run / "pairs.json").read_text())[0]["winner"] is None
    monkeypatch.setattr(
        eval_pairs, "run_agent", judging(lambda a: "A" if "html" in a else "B")
    )
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    pair = json.loads((run / "pairs.json").read_text())[0]
    assert pair["winner"] == "claude-code/html/workflow"
    results.append({**results[0]})
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))
    refused = CliRunner().invoke(eval_pairs.eval_pairs, [str(run)])
    assert refused.exit_code != 0 and "2 samples" in refused.output


def test_a_resumed_phase_costs_only_its_own_work():
    """Claude Code reports the session's total; Codex reports none."""
    from leaf_dev.arms import resumed

    totals = [{"cost_usd": 1.0}, {"cost_usd": 1.5}, {"cost_usd": 2.25}]
    assert [p["cost_usd"] for p in resumed(totals)] == [1.0, 0.5, 0.75]
    assert [p["cost_usd"] for p in resumed([{"cost_usd": None}] * 2)] == [None, None]
