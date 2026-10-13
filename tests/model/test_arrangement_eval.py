"""Product controls really render ordinary HTML; judges read real screenshots."""

import json
from pathlib import Path

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
            (shots / f"p3-{name}-0.png").write_bytes(column.encode())
        (work / "prompt-1.txt").write_text(
            "The user's request follows.\n\nCompare this task."
        )
        results.append(
            {
                "provider": {"label": column},
                "response": {
                    "metadata": {
                        "work": str(work),
                        "diagnostics": {
                            "subject": "document",
                            "phases": {
                                "3": {
                                    "captures": {
                                        name: [str(shots / f"p3-{name}-0.png")]
                                        for name in WIDTHS
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
            a = brief.split("Page A:")[1].split("Page B:")[0]
            pixels = Path(
                next(
                    line.strip()
                    for line in a.splitlines()
                    if line.strip().endswith(".png")
                )
            ).read_bytes()
            winner = prefer(pixels)
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
            files = [out.parent / "brief.md"]
            for line in brief.splitlines():
                if line.startswith("Observation record: "):
                    files.append(Path(line.split(": ", 1)[1]))
                elif line.strip().endswith(".png"):
                    files.append(Path(line.strip()))
            trace = []
            for index, path in enumerate(files):
                identity = f"read-{index}"
                trace.extend(
                    [
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "id": identity,
                                        "name": "Read",
                                        "input": {"file_path": str(path)},
                                    }
                                ]
                            },
                        },
                        {
                            "type": "user",
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": identity,
                                        "content": "recorded file",
                                    }
                                ]
                            },
                        },
                    ]
                )
            return [
                *trace,
                {"type": "result", "is_error": False, "structured_output": verdict},
            ]

        return model

    monkeypatch.setattr(eval_pairs, "run_agent", judging(lambda a: "A"))
    first = CliRunner().invoke(
        eval_pairs.eval_pairs, [str(run), "--output", str(run / "judgment-1")]
    )
    assert first.exit_code == 0, first.output
    assert json.loads((run / "judgment-1/pairs.json").read_text())[0]["winner"] is None
    monkeypatch.setattr(
        eval_pairs, "run_agent", judging(lambda a: "A" if b"html" in a else "B")
    )
    second = CliRunner().invoke(
        eval_pairs.eval_pairs, [str(run), "--output", str(run / "judgment-2")]
    )
    assert second.exit_code == 0, second.output
    pair = json.loads((run / "judgment-2/pairs.json").read_text())[0]
    assert pair["winner"] == "claude-code/html/workflow"

    def unread_image(*args, **kwargs):
        # A structured preference is still unscored when one native image Read
        # has no successful result. The external model alone is replaced here.
        trace = judging(lambda _: "A")(*args, **kwargs)
        image_read = next(
            block["id"]
            for record in trace
            for block in record.get("message", {}).get("content", [])
            if block.get("type") == "tool_use"
            and block["input"]["file_path"].endswith(".png")
        )
        return [
            record
            for record in trace
            if not any(
                block.get("tool_use_id") == image_read
                for block in record.get("message", {}).get("content", [])
            )
        ]

    monkeypatch.setattr(eval_pairs, "run_agent", unread_image)
    unsupported = CliRunner().invoke(
        eval_pairs.eval_pairs, [str(run), "--output", str(run / "judgment-unread")]
    )
    assert unsupported.exit_code == 0, unsupported.output
    pair = json.loads((run / "judgment-unread/pairs.json").read_text())[0]
    assert pair["winner"] is None and pair["orders"] == [None, None]
    integrity = json.loads(
        (run / "judgment-unread/document-1-order-1/integrity.json").read_text()
    )
    assert integrity["status"] == "unscored"
    assert "required public evidence" in integrity["error"]
    results.append({**results[0]})
    (run / "results.json").write_text(json.dumps({"results": {"results": results}}))
    refused = CliRunner().invoke(eval_pairs.eval_pairs, [str(run)])
    assert refused.exit_code != 0 and "more than once" in refused.output


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
        reading_values,
    )

    decision = CASES["configuration"].decision
    schema = json.loads(reading_schema(decision))
    assert len(schema["required"]) == len(decision.values)
    assert all(key.replace("_", "").isalnum() for key in schema["properties"])
    routing = next(
        p
        for p in schema["properties"].values()
        if p["description"] == "webhook-backlog routing"
    )
    assert "undecided" in routing["enum"]
    exact = dict(decision.chosen)
    wire = {
        key: exact[prop["description"]] for key, prop in schema["properties"].items()
    }
    assert reading_values(decision, {"structured_output": wire}) == exact
    assert all(matches(decision, exact).values())
    off = {**exact, "webhook-backlog routing": "off"}
    assert not matches(decision, off)["webhook-backlog routing"]
    assert not any(matches(decision, None).values())
    assert reading_values(decision, {}) is None
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


def test_report_keeps_compared_version_evidence_spend_and_decisions_together(
    tmp_path, monkeypatch
):
    from click.testing import CliRunner
    from leaf_dev import eval_report
    from leaf_dev.eval_pairs import final_shots

    columns = {}
    for arm in ("base", "candidate"):
        work = tmp_path / arm
        work.mkdir()
        column = f"claude-code/{arm}/workflow"
        phases = {
            str(number): {
                "trace": {"minutes": number, "cost_usd": number, "turns": 1},
                "css_lines": number,
                "script_lines": 0,
                "captures": {
                    width: [f"{arm}-version-{number}-{width}.png"] for width in WIDTHS
                },
            }
            for number in (1, 2, 4)
        }
        metadata = {
            "work": str(work),
            "diagnostics": {"phases": phases},
            "authoring_inputs": {
                "request": "Compare this task.",
                "phases": {
                    "2": {"messages": ["Earlier width preference."]},
                    "4": {"messages": ["Future final decision."]},
                },
            },
        }
        columns[column] = [
            {
                "sample": arm,
                "diagnostics": metadata["diagnostics"],
                "metadata": metadata,
                "run": tmp_path,
                "checks": {"decision-applied": True},
            }
        ]
    pair = {
        "subject": "document",
        "pair": 1,
        "phase": 2,
        "samples": {
            column: members[0]["sample"] for column, members in columns.items()
        },
        "winner": "tie",
        "orders": [{"overall": "tie", "defects": {}}] * 2,
    }
    # Media registration is a separate CLI boundary; retain the report's actual
    # recorded-version selection and HTML composition without starting a process.
    monkeypatch.setattr(
        eval_report,
        "screens",
        lambda page, sample, subject: final_shots(sample, subject),
    )
    report = eval_report.task_section(tmp_path, "document", columns, [pair])
    overview = eval_report.overview({"document": columns}, [pair])
    assert "Version 2:" in report and "Earlier width preference." in report
    assert "Future final decision." not in report
    assert "version-2-laptop.png" in report and "version-4-" not in report
    assert "Decision applied" not in report
    assert report.count("$3.00") == overview.count("$3.00") == 2
    assert "$7.00" not in report + overview
    sample = next(iter(columns.values()))[0]
    assert eval_report.measures({**sample, "phase": 2}, "document")["applied"] is None
    assert eval_report.measures(sample, "document")["applied"] is True
    # Exercise the command's common validation before it aggregates or composes
    # the report. Only sample loading and media registration are substituted.
    page = tmp_path / "report"
    page.mkdir()
    (page / "events.jsonl").write_text("")
    verdicts = tmp_path / "pairs.json"
    verdicts.write_text(json.dumps([pair]))
    report_columns = columns
    monkeypatch.setattr(
        eval_report, "samples", lambda runs: {"document": report_columns}
    )
    args = [str(page), str(tmp_path), "--pairs", str(verdicts)]
    valid = CliRunner().invoke(eval_report.eval_report, args)
    assert valid.exit_code == 0, valid.output

    # A verdict from a larger run selection must not count toward a report that
    # cannot display or validate the corresponding authored samples.
    extra = {**pair, "pair": 2, "samples": dict.fromkeys(columns, "other-sample")}
    verdicts.write_text(json.dumps([pair, extra]))
    unmatched = CliRunner().invoke(eval_report.eval_report, args)
    assert unmatched.exit_code != 0, unmatched.output

    verdicts.write_text(json.dumps([pair]))
    report_columns = {column: list(members) for column, members in columns.items()}
    candidate = "claude-code/candidate/workflow"
    report_columns[candidate].append(
        {**report_columns[candidate][0], "sample": "candidate-extra"}
    )
    unequal = CliRunner().invoke(eval_report.eval_report, args)
    assert unequal.exit_code != 0, unequal.output


def test_reobserved_run_preserves_authoring_inputs_cost_and_historical_subject(
    tmp_path, monkeypatch
):
    from leaf_dev import ROOT, eval_observe, eval_pairs, eval_report
    from leaf_dev.authoring_score import sample_inputs

    source = tmp_path / "source"
    work = source / "samples" / "archived-sample"
    page = work / "page-phase2"
    page.mkdir(parents=True)
    (page / "index.html").write_text("<!doctype html><p>Original evidence.</p>")
    (work / "prompt-1.txt").write_text("Original task.")
    saved_inputs = work / "authoring-inputs.json"
    saved_inputs.write_text(
        json.dumps(
            {
                "request": "Original task.",
                "phases": {
                    "2": {"messages": ["Historical preference."]},
                    "4": {"messages": ["Future decision."]},
                },
            }
        )
    )
    metadata = {
        "work": str(work),
        "checks": {},
        "diagnostics": {
            "subject": "archived-custom",
            "phases": {
                str(number): {
                    "trace": {"minutes": number, "cost_usd": number, "turns": 1},
                    "captures": {},
                }
                for number in (1, 2, 4)
            },
        },
    }
    (source / "results.json").write_text("{}")
    observed = tmp_path / "observed"
    observed.mkdir()

    # The browser capture is exercised in the owning browser test. Keep this
    # regression on the replay metadata consumed by scoring, pairing and reports.
    def capture(run, phase, *args, **kwargs):
        run.shots.mkdir(parents=True)
        (run.shots / f"p{phase}-observation.json").write_text(
            json.dumps({"version": 1, "phase": phase, "widths": {}})
        )
        return {}

    monkeypatch.setattr(eval_observe, "capture_phase", capture)
    replayed = eval_observe.observe_sample(metadata, source, observed, ROOT, 2, ())
    (observed / "results.json").write_text(
        json.dumps(
            {
                "results": {
                    "results": [
                        {
                            "provider": {"label": "claude-code/base/workflow"},
                            "response": {"metadata": replayed},
                        }
                    ]
                }
            }
        )
    )
    found = eval_pairs.samples([observed])
    assert "archived-custom" in found
    sample = found["archived-custom"]["claude-code/base/workflow"][0]
    assert eval_report.measures(sample, "archived-custom")["cost"] == 3
    assert "4" not in replayed["diagnostics"]["phases"]

    saved_inputs.write_text(
        json.dumps({"request": "Changed later.", "phases": {"2": {"messages": []}}})
    )
    inputs = sample_inputs(replayed, observed)
    assert inputs["request"] == "Original task."
    assert inputs["messages"] == ["Historical preference."]

    saved_inputs.write_text(json.dumps({"request": "Original task.", "phases": {}}))
    original_limits = sample_inputs(metadata, source, 2)["observations"][
        "input_limitations"
    ]
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    replayed = eval_observe.observe_sample(metadata, source, incomplete, ROOT, 2, ())
    inputs = sample_inputs(replayed, incomplete)
    assert inputs["messages"] == []
    assert inputs["observations"]["input_limitations"] == original_limits


def test_runtime_identity_tracks_vendored_bytes_separately_from_authored_state(
    tmp_path,
):
    from leaf.schema import (
        BROWSER_DIRS,
        CURSOR_FILE,
        INTERACTIONS_FILE,
        USER_VIEWS_FILE,
        VENDORED_FILES,
    )
    from leaf_dev.eval_provenance import runtime_identity, tree_identity

    for name in VENDORED_FILES:
        (tmp_path / name).write_text(f"Vendored {name}")
    for name in BROWSER_DIRS:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "part.js").write_text(f"Vendored {name} module")
    (tmp_path / "index.html").write_text("<!doctype html><p>Initial page.</p>")
    runtime = runtime_identity(tmp_path)
    artifact = tree_identity(tmp_path)

    (tmp_path / "index.html").write_text("<!doctype html><p>Revised page.</p>")
    for name in (CURSOR_FILE, INTERACTIONS_FILE, USER_VIEWS_FILE):
        (tmp_path / name).write_text("New process or user state")
    authored = tmp_path / "page"
    authored.mkdir()
    (authored / "chart.js").write_text("New authored chart")
    assert tree_identity(tmp_path) != artifact
    assert runtime_identity(tmp_path) == runtime

    (tmp_path / BROWSER_DIRS[0] / "part.js").write_text(
        "Changed vendored implementation"
    )
    assert runtime_identity(tmp_path) != runtime
