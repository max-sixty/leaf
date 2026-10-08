"""Product controls really render ordinary HTML; judges read real screenshots."""

import json
from pathlib import Path

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arrangement_eval import WIDTHS, first_prompt


def test_html_control_uses_browser_without_leaf_payload(tmp_path):
    page = tmp_path / "page"
    page.mkdir()
    (page / "index.html").write_text(
        "<!doctype html><title>Control</title><h1>Report</h1><p>Readable content.</p>"
    )
    prompt = first_prompt(ROOT, page, "document", "html")
    assert str(ROOT) not in prompt
    assert "$LEAF" not in prompt
    assert "ordinary HTML" in prompt
    assert arrangement_plain.gate(page, WIDTHS)["passed"]
    (page / "index.html").write_text(
        "<!doctype html><title>Fault</title><style>body{width:1800px}</style><h1>Report</h1><script>throw Error('seeded fault')</script>"
    )
    reading = arrangement_plain.gate(page, WIDTHS)
    assert not reading["passed"]
    assert any("seeded fault" in item["error"] for item in reading["findings"])
    assert any("overflows" in item["error"] for item in reading["findings"])


def test_comparison_snapshots_exclude_later_leaf_feedback(tmp_path, monkeypatch):
    """Script the external model; real admission and publication preserve user input."""
    from leaf_dev import arrangement_eval
    from leaf_dev.arms import run_leaf

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    run = arrangement_eval.Run("document", ROOT, evidence, evidence / "shots")
    author_turns = 0

    def model(cwd, prompt, *args, out, err, **kwargs):
        nonlocal author_turns
        if cwd == run.work:
            author_turns += 1
            page = run.authored_page
            if author_turns == 1:
                run_leaf(ROOT, run.state, "page", "init", str(page), check=True)
            body = "Reviewed" if author_turns == 3 else f"Author version {author_turns}"
            (page / "index.html").write_text(
                '<!doctype html><html lang="en"><head><title>Decision review</title>'
                '<meta name="description" content="Review evidence."></head><body>'
                '<main class="layout-column"><h1>Decision review</h1>'
                f'<p id="review-status">{body}</p>'
                '<lf-ask id="choice"><h2>Which option?</h2><lf-options id="decision" choose>'
                '<lf-option id="a">A</lf-option><lf-option id="b">B</lf-option>'
                "</lf-options></lf-ask></main></body></html>"
            )
            run_leaf(
                ROOT, run.state, "page", "stamp", str(page), "--text", body, check=True
            )
            response = str(page)
        else:
            state = json.loads(run.leaf("page", "state", str(run.authored_page)).stdout)
            selected = next(
                item["detail"]["value"]
                for item in state["state"]
                if item["widget"] == "decision"
            )
            response = json.dumps({"options": selected})
        trace = [
            {
                "type": "result",
                "is_error": False,
                "session_id": "observed-session",
                "result": response,
            }
        ]
        out.write_text("\n".join(json.dumps(record) for record in trace))
        err.write_text("")
        return trace

    monkeypatch.setattr(arrangement_eval, "run_agent", model)
    arrangement_eval.author(run, tmp_path / "cwd")
    choice = json.loads((evidence / "choice.json").read_text())
    assert choice["seeded"] and choice["correct"] and choice["page_unchanged"]
    assert author_turns == 3
    assert "Author version 1" in (evidence / "page-phase1/index.html").read_text()
    assert "Author version 2" in (evidence / "page/index.html").read_text()
    assert "Reviewed" in (evidence / "page-continuation/index.html").read_text()
    for snapshot in ("page-phase1", "page"):
        assert not any(
            json.loads(line)["kind"] == "action"
            for line in (evidence / snapshot / "events.jsonl").read_text().splitlines()
        )
    state = json.loads(run.leaf("page", "state", str(run.authored_page)).stdout)
    assert state["active"]["revision"] != choice["revision"]
    assert next(
        item["detail"]["value"]
        for item in state["state"]
        if item["widget"] == "decision"
    ) == ["b"]


def test_completed_record_has_a_render_correction_loop_without_a_seeded_decision(
    tmp_path, monkeypatch
):
    """Script only the model; actual checks reject, repair and render its page."""
    from leaf_dev import arrangement_eval

    calls = []

    def model(cwd, prompt, *args, out, err, **kwargs):
        calls.append(prompt)
        page = cwd / "page"
        state = Path(kwargs["env"]["XDG_STATE_HOME"])

        def leaf(*arguments):
            return arrangement_eval.run_leaf(ROOT, state, *arguments)

        assert f"page check {page} --render" in prompt
        if not page.exists():
            assert leaf("page", "init", str(page)).returncode == 0
        (page / "index.html").write_text("<!doctype html><p>Incomplete record</p>")
        refused = leaf("page", "check", str(page), "--render")
        assert refused.returncode != 0
        (page / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Completed rollout</title>'
            '<meta name="description" content="A completed rollout record."></head>'
            '<body><main class="layout-sidebar"><header><h1>Completed rollout</h1>'
            f'<p id="version">Version {len(calls)}</p>'
            '</header><aside id="checks" style="align-self:stretch">'
            '<div style="position:sticky;top:var(--lf-top)"><h2>Checks</h2>'
            '<p>Five passed. One failed.</p><lf-toc id="contents"></lf-toc></div></aside>'
            '<section id="log"><h2>Rollout log</h2>'
            + "<p>Completed rollout entry.</p>" * 40
            + "</section></main></body></html>"
        )
        accepted = leaf("page", "check", str(page), "--render")
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert leaf("page", "stamp", str(page), "--text", "Repaired").returncode == 0
        trace = []
        for index, checked in enumerate((refused, accepted)):
            cid = f"check-{index}"
            trace += [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": cid,
                                "name": "Bash",
                                "input": {
                                    "command": f"$LEAF page check {page} --render"
                                },
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
                                "tool_use_id": cid,
                                "content": checked.stdout + checked.stderr,
                                "is_error": checked.returncode != 0,
                            }
                        ]
                    },
                },
            ]
        trace.append(
            {
                "type": "result",
                "is_error": False,
                "session_id": "record-session",
                "result": str(page),
            }
        )
        out.write_text("\n".join(json.dumps(record) for record in trace))
        err.write_text("")
        return trace

    monkeypatch.setattr(arrangement_eval, "run_agent", model)
    evidence = tmp_path / "evidence"
    response = arrangement_eval.execute_scenario(
        "sidebar-page-at-900px", ROOT, evidence, shots=evidence / "shots"
    )
    assert len(calls) == 2
    assert all(response["metadata"]["checks"].values())
    assert not (evidence / "choice.json").exists()
    assert not any(key.startswith("choice-") for key in response["metadata"]["checks"])
    for phase in response["metadata"]["diagnostics"]["phases"].values():
        assert phase["trace"]["renders"] == 2
        assert phase["trace"]["refused"] == 1
        assert phase["captures"]["short"]
        assert all(Path(path).is_file() for path in phase["captures"]["short"])


def test_reader_calibration_shows_the_judge_its_page_at_every_width(tmp_path):
    """No model runs: the seeded triage page renders, and the output lists every
    capture under its width, which is all the count rubric reads."""
    from leaf_dev import reader_eval

    response = reader_eval.execute_scenario(
        "seeded", ROOT, tmp_path, shots=tmp_path / "shots"
    )
    assert response["metadata"]["checks"] == {"completed": True}
    output = response["output"]
    widths = [line for line in output.splitlines() if line.startswith("  On ")]
    assert widths == [f"  On {label}, top to bottom:" for _, label in WIDTHS.values()]
    listed = [
        Path(line.strip())
        for line in output.splitlines()
        if line.strip().endswith(".png")
    ]
    assert listed and all(path.is_file() for path in listed)
    assert 'value="8"' in (tmp_path / "source.html").read_text()
