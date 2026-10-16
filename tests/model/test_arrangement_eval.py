"""Authoring comparisons judge live copies and preserve incomplete observations."""

import json
from pathlib import Path

import pytest
from leaf_dev.arrangement_eval import WIDTHS, comparison_inputs, phases


def test_pairwise_counts_only_a_winner_both_orders_name(tmp_path, monkeypatch):
    """No model runs: a judge that always prefers position A splits every pair, and
    one that prefers a column's page wins it in both orders."""
    from click.testing import CliRunner
    from leaf_dev.arrangement_eval import CASES, apply_message
    from leaf_dev.commands import eval_pairs

    final_request = apply_message(CASES["document"].decision, "typed", None)
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
                            "payload": "/original/runtime",
                            "condition": "html" if "html" in column else "leaf",
                            "comparison": comparison_inputs("document"),
                            "phases": {
                                "3": {"page": str(work / "page-phase3")},
                                "4": {
                                    "page": str(work / "page-phase4"),
                                },
                            },
                        },
                    }
                },
            }
        )
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))

    def judging(prefer, status="complete"):
        def model(pages, widths, prompt, schema, evidence):
            evidence.mkdir(parents=True, exist_ok=True)
            assert set(pages) == {"A", "B", "A_before_decision", "B_before_decision"}
            for label in ("A", "B"):
                assert pages[label]["page"].name == "page-phase4"
                assert pages[label + "_before_decision"]["page"].name == "page-phase3"
                assert (
                    pages[label]["page"].parent
                    == pages[label + "_before_decision"]["page"].parent
                )
            assert all(
                p["payload"] == Path("/original/runtime") for p in pages.values()
            )
            assert final_request in prompt
            assert widths.keys() == WIDTHS.keys()
            assert "screenshots" not in prompt
            winner = prefer(str(pages["A"]["page"]))
            verdict = {
                "status": status,
                **dict.fromkeys(eval_pairs.ASPECTS, "tie"),
                "overall": winner,
                "margin": "clear",
                "defects_A": [],
                "defects_B": [],
                "reason": "",
            }
            assert set(verdict) == set(schema["required"])
            return {"output": verdict}

        return model

    monkeypatch.setattr(eval_pairs, "judge_pages", judging(lambda a: "A"))
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    pair = json.loads((run / "pairs.json").read_text())[0]
    assert pair["winner"] is None and pair["status"] == "split"
    monkeypatch.setattr(
        eval_pairs, "judge_pages", judging(lambda a: "A" if "html" in a else "B")
    )
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    pair = json.loads((run / "pairs.json").read_text())[0]
    assert pair["winner"] == "claude-code/html/workflow"
    monkeypatch.setattr(
        eval_pairs, "judge_pages", judging(lambda a: "A", "insufficient_evidence")
    )
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    pair = json.loads((run / "pairs.json").read_text())[0]
    assert pair["winner"] is None and pair["status"] == "insufficient_evidence"
    from leaf_dev.commands.eval_report import outcome, verdict_line

    assert verdict_line(pair) == "Insufficient evidence for comparison"
    assert "split 0" in outcome("document", [pair])
    monkeypatch.setattr(eval_pairs, "judge_pages", judging(lambda a: "tie"))
    assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
    pair = json.loads((run / "pairs.json").read_text())[0]
    assert pair["winner"] is None and pair["status"] == "tie"
    assert verdict_line(pair) == "Both orders judged the pages equal"
    for version in ("3", "4"):
        recorded = results[0]["response"]["metadata"]["diagnostics"]["phases"]
        missing = recorded.pop(version)
        (run / "results.json").write_text(json.dumps({"results": {"results": results}}))
        assert CliRunner().invoke(eval_pairs.eval_pairs, [str(run)]).exit_code == 0
        pair = json.loads((run / "pairs.json").read_text())[0]
        assert pair["winner"] is None and pair["status"] == "unscored"
        assert verdict_line(pair) == "Comparison unscored"
        recorded[version] = missing

    # A task without decisions requires only its final revision.
    def navigation(pages, widths, prompt, schema, evidence):
        assert "No browser decision task applies to these pages." in prompt
        assert set(pages) == {"A", "B"}
        assert all(page["page"].name == "page-phase2" for page in pages.values())
        assert all(
            page["payload"] == Path("/original/runtime") for page in pages.values()
        )
        return {}

    monkeypatch.setattr(eval_pairs, "judge_pages", navigation)
    navigation_sample = {
        "diagnostics": {
            "phases": {"2": {"page": "/saved/page-phase2"}},
            "payload": "/original/runtime",
            "condition": "leaf",
            "comparison": comparison_inputs("sidebar-page-at-900px"),
        }
    }
    assert navigation_sample["diagnostics"]["comparison"]["decision_task"] is None
    eval_pairs.judge(
        navigation_sample,
        navigation_sample,
        tmp_path / "navigation",
    )
    results.append({**results[0]})
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))
    refused = CliRunner().invoke(eval_pairs.eval_pairs, [str(run)])
    assert refused.exit_code != 0 and "2 samples" in refused.output


def test_comparison_inputs_are_saved_before_authoring(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from leaf_dev import arrangement_eval

    expected = comparison_inputs("document")
    work = tmp_path / "sample"

    def author(run, cwd):
        assert json.loads((work / "comparison.json").read_text()) == expected
        raise RuntimeError("author boundary reached")

    monkeypatch.setattr(
        arrangement_eval, "scratch", lambda payload: nullcontext(tmp_path)
    )
    monkeypatch.setattr(arrangement_eval, "author", author)
    with pytest.raises(RuntimeError, match="author boundary reached"):
        arrangement_eval.execute_scenario(
            "document", tmp_path, work, shots=tmp_path / "shots"
        )


def test_pairwise_uses_saved_inputs_after_case_rotation(tmp_path, monkeypatch):
    """Only the live model is replaced: retained samples survive source rotation,
    but missing evidence and unlike task contracts never reach that model.
    """
    from copy import deepcopy

    from click.testing import CliRunner
    from leaf_dev import arrangement_eval
    from leaf_dev.commands import eval_pairs

    monkeypatch.setattr(arrangement_eval, "WIDTHS", {"desk": ((817, 611), "desk")})
    prescribed = arrangement_eval.CASES["queue"].decision.task
    captured = comparison_inputs("queue")
    assert captured["decision_task"] == prescribed
    assert prescribed not in captured["brief"]
    results = []
    for condition in ("leaf", "html"):
        work = tmp_path / condition
        work.mkdir()
        (work / "prompt-1.txt").write_text("retained prompt")
        shots = tmp_path / "screenshots" / work.name
        shots.mkdir(parents=True)
        for phase in (3, 4):
            (shots / f"p{phase}-desk-0.png").write_bytes(b"saved capture")
        results.append(
            {
                "provider": {"label": f"codex/{condition}/workflow"},
                "response": {
                    "metadata": {
                        "work": str(work),
                        "diagnostics": {
                            "subject": "queue",
                            "comparison": deepcopy(captured),
                            "payload": "/original/runtime",
                            "condition": condition,
                            "phases": {
                                str(phase): {
                                    "page": str(work / f"page-phase{phase}"),
                                    "trace": {
                                        "completed": True,
                                        "minutes": phase,
                                        "input_tokens": phase * 100,
                                        "cost_usd": None,
                                        "turns": 1,
                                    },
                                }
                                for phase in captured["author_phases"]
                            },
                        },
                    }
                },
            }
        )

    # Rotate every live source the old reader used, including removing the case.
    monkeypatch.setattr(arrangement_eval, "TASKS", tmp_path / "removed-catalog")
    monkeypatch.setattr(arrangement_eval, "CASES", {})
    monkeypatch.setattr(arrangement_eval, "PREFERENCE", "a different width preference")
    monkeypatch.setattr(arrangement_eval, "WIDTHS", {})
    observed = []

    def model(pages, widths, prompt, schema, evidence):
        observed.append(prompt)
        assert captured["brief"] in prompt
        assert prompt.count(prescribed) == 1
        assert widths == captured["widths"]
        assert {p["page"].name for p in pages.values()} == {
            "page-phase3",
            "page-phase4",
        }
        return {
            "output": {
                "status": "complete",
                **dict.fromkeys(eval_pairs.ASPECTS, "tie"),
                "overall": "tie",
                "margin": "slight",
                "defects_A": [],
                "defects_B": [],
                "reason": "same task",
            }
        }

    monkeypatch.setattr(eval_pairs, "judge_pages", model)

    def compare():
        (tmp_path / "results.json").write_text(
            json.dumps({"results": {"results": results}})
        )
        result = CliRunner().invoke(eval_pairs.eval_pairs, [str(tmp_path)])
        assert result.exit_code == 0, result.output
        return json.loads((tmp_path / "pairs.json").read_text())[0]

    assert compare()["status"] == "tie"
    assert len(observed) == 2
    saved = results[0]["response"]["metadata"]["diagnostics"]
    for key in ("brief", "decision_task", "phases", "author_phases", "widths"):
        changed = deepcopy(captured)
        changed[key] = (
            "a different request"
            if key in {"brief", "decision_task"}
            else {"different": "value"}
        )
        saved["comparison"] = changed
        assert compare()["status"] == "unscored"
        changed.pop(key)
        assert compare()["status"] == "unscored"
    saved.pop("comparison")
    assert compare()["status"] == "unscored"
    assert len(observed) == 2


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


def test_routine_desktop_and_focused_sidebar_keep_their_own_work_environment():
    from leaf_dev.arrangement_eval import DEFINITION, case_widths, preference_message

    assert comparison_inputs("document")["widths"] == {"desktop": [1600, 1000]}
    assert "fullscreen" in preference_message("document")
    focused = comparison_inputs("sidebar-page-at-900px")
    assert focused["widths"] == {"short": [900, 600], "phone": [390, 844]}
    assert "beside my editor" in preference_message("sidebar-page-at-900px")
    for subject, case in DEFINITION["cases"].items():
        for assertion in case["assert"]:
            required = assertion.get("config", {}).get("required_widths", [])
            assert set(required) <= case_widths(subject).keys()


def test_report_keeps_candidate_identity_and_the_saved_task(tmp_path, monkeypatch):
    """Base/candidate results stay distinct after the catalog rotates away."""
    from leaf_dev.commands import eval_report

    base, candidate = "claude-code/base/workflow", "claude-code/candidate/workflow"
    pair = {
        "subject": "retired-task",
        "pair": 1,
        "samples": {base: "base-sample", candidate: "candidate-sample"},
        "status": "complete",
        "winner": candidate,
        "orders": [],
    }
    outcome = eval_report.outcome("retired-task", [pair])
    assert f"Leaf · {base} 0" in outcome
    assert f"Leaf · {candidate} 1" in outcome
    captured = {
        "brief": "<request>Original task, since removed.</request>",
        "decision_task": "Choose the second alternative.",
        "phases": {"": "8", "_before_decision": "6"},
        "author_phases": [1, 6, 8],
        "widths": {"saved-desk": [1234, 765]},
    }
    columns = {
        column: [
            {
                "sample": name,
                "checks": {},
                "diagnostics": {
                    "comparison": captured,
                    "phases": {
                        str(phase): {"trace": {"completed": True, "minutes": phase}}
                        for phase in captured["author_phases"]
                    },
                },
            }
        ]
        for column, name in pair["samples"].items()
    }
    observed = []

    def screens(page, sample, version):
        observed.append((sample["sample"], version))
        return {"saved-desk": []}

    monkeypatch.setattr(eval_report, "screens", screens)
    rendered = eval_report.task_section(tmp_path, "retired-task", columns, [pair])
    assert "Original task, since removed." in rendered
    assert 'label="1234 × 765"' in rendered
    assert "final saved revision (phase 8)" in rendered
    assert "earlier screenshots below show phase 6" in rendered
    assert set(observed) == {
        (sample, phase) for sample in pair["samples"].values() for phase in ("6", "8")
    }


def test_discovery_report_embeds_exact_screenshot_evidence(tmp_path, monkeypatch):
    """Only declared evidence paths become media; missing and other files stay explicit."""
    from leaf_dev.commands import eval_report
    from PIL import Image

    run = tmp_path / "run"
    attempt = run / "discovery" / "sample" / "attempt-one"
    attempt.mkdir(parents=True)
    absolute = tmp_path / "absolute.png"
    relative = attempt / "relative.png"
    prose_only = attempt / "not-declared.png"
    for image in (absolute, relative, prose_only):
        Image.new("RGB", (320, 200)).save(image)
    (attempt / "response.json").write_text(
        json.dumps(
            {
                "sample": "sample",
                "output": {
                    "status": "complete",
                    "explored": "The desktop decision route.",
                    "unverified": [],
                    "observations": [
                        {
                            "kind": "strength",
                            "summary": "Evidence remains alongside the decision.",
                            "impact": f"Other prose mentions {prose_only}.",
                            "viewport": [1600, 1000],
                            "steps": ["Open the evidence panel."],
                            "evidence": [
                                str(absolute),
                                "relative.png",
                                "missing.png",
                                "response.json",
                            ],
                            "next": "Check a shorter window.",
                        }
                    ],
                },
            }
        )
    )
    imported = []

    def media(*args):
        import shutil

        assert args[:2] == ("page", "media")
        imported.extend(args[3:])
        destination = Path(args[2]) / "media"
        destination.mkdir(parents=True, exist_ok=True)
        for path in args[3:]:
            shutil.copyfile(path, destination / Path(path).name)
        return "\n".join(
            json.dumps({"source": path, "path": f"media/{Path(path).name}"})
            for path in args[3:]
        )

    monkeypatch.setattr(eval_report, "leaf", media)
    rendered = eval_report.discovery_section(tmp_path / "page", (run,))
    assert set(imported) == {str(absolute), str(relative)}
    for name in ("absolute.png", "relative.png"):
        assert f'href="media/{name}"' in rendered
        assert f'src="media/{name}"' in rendered
    assert 'width="320" height="200" loading="lazy"' in rendered
    assert "File is missing" in rendered and "missing.png" in rendered
    assert "Supplementary evidence; not an image" in rendered
    assert "response.json" in rendered
    assert str(prose_only) in rendered
