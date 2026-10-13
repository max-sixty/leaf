"""Product controls really render ordinary HTML; judges read real screenshots."""

import json

from leaf_dev.arrangement_eval import WIDTHS, phases


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
            (shots / f"p{phases('document')[-1]}-{name}-0.png").write_bytes(b"")
        results.append(
            {
                "provider": {"label": column},
                "response": {
                    "metadata": {
                        "work": str(work),
                        "diagnostics": {
                            "subject": "document",
                            "phases": {
                                "4": {
                                    "observations": {
                                        "narrow": {
                                            "states": [
                                                {"action": "Inspect option: Postgres"}
                                            ],
                                            "limits": [],
                                        }
                                    }
                                }
                            },
                        },
                    }
                },
            }
        )
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))

    def judging(prefer):
        def model(cwd, prompt, *args, out, err, **kwargs):
            brief = (out.parent / "brief.md").read_text()
            assert "Inspect option: Postgres" in brief
            assert "collector inputs, not user decisions" in brief
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


def test_a_live_session_splits_into_its_phases_by_the_harness_marks():
    """Each phase's turns are the records after its mark, so each costs only its
    own turns once `resumed` takes the session's running total apart."""
    from leaf_dev.arms import resumed, trace_summary
    from leaf_dev.arrangement_eval import phase_traces

    def turn(total):
        return {"type": "result", "is_error": False, "total_cost_usd": total}

    trace = [
        {"type": "eval_phase", "phase": 1},
        turn(1.0),
        {"type": "eval_phase", "phase": 2},
        {"type": "eval_send", "text": "revise"},
        turn(1.5),
        turn(2.0),
    ]
    split = phase_traces(trace)
    assert [len(split[1]), len(split[2])] == [1, 3]
    costs = resumed([trace_summary(split[p]) for p in (1, 2)])
    assert [c["cost_usd"] for c in costs] == [1.0, 1.0]


def test_each_decision_chooses_among_its_own_values():
    """A reader is asked for one listed value per item, so a chosen value outside
    its item's list could never be read back as applied."""
    from leaf_dev.arrangement_eval import CASES

    for scenario in CASES.values():
        if decision := scenario.decision:
            assert decision.chosen.keys() == decision.values.keys()
            for item, value in decision.chosen.items():
                assert value in decision.values[item]


def test_applying_a_decision_reads_every_item_and_names_its_route():
    """Only a reading that gives every item its chosen value counts as applied,
    and the reader is held to each item's listed values; the request to apply
    carries the page's copy or the user's words only where the page did not take
    the decision."""
    import json

    from leaf_dev.arrangement_eval import (
        CASES,
        apply_message,
        matches,
        reading_schema,
    )

    decision = CASES["configuration"].decision
    schema = json.loads(reading_schema(decision))
    assert schema["required"] == list(decision.values)
    assert "undecided" in schema["properties"]["webhook-backlog routing"]["enum"]
    exact = dict(decision.chosen)
    assert all(matches(decision, exact).values())
    off = {**exact, "webhook-backlog routing": "off"}
    assert not matches(decision, off)["webhook-backlog routing"]
    assert not any(matches(decision, None).values())
    assert apply_message(decision, "page", None).startswith("I've made my")
    assert "a: 1" in apply_message(decision, "copied", "a: 1")
    assert decision.typed in apply_message(decision, "typed", None)


def test_leaf_checks_its_own_loop_and_html_shares_the_outcomes():
    from leaf_dev.arrangement_eval import expected_checks

    leaf = expected_checks("configuration", condition="leaf")
    html = expected_checks("configuration", condition="html")
    assert set(leaf) - set(html) == {
        "handed-over",
        "comment-delivered",
        "decision-reader-completed",
        "decision-reader-correct",
        "decision-reader-page-unchanged",
    }
    assert set(html) < set(leaf)
    assert {"decision-made", "decision-applied", "phase-4-render"} <= set(html)
