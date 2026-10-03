"""Product controls really render ordinary HTML; judges require actual evidence."""

import json

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arrangement_eval import WIDTHS, capture_reads, first_prompt, valid_verdict
from leaf_dev.harness import read_trace


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


def test_judge_requires_successful_capture_reads_and_complete_quality_verdict(tmp_path):
    calls = [
        {
            "type": "tool_use",
            "id": name,
            "name": "Read",
            "input": {"file_path": f"/captures/{name}.png"},
        }
        for name in ("read", "denied", "empty", "attempted")
    ]
    returns = [
        {
            "type": "tool_result",
            "tool_use_id": "read",
            "content": [{"type": "image", "data": "capture"}],
        },
        {
            "type": "tool_result",
            "tool_use_id": "denied",
            "is_error": True,
            "content": "denied",
        },
        {"type": "tool_result", "tool_use_id": "empty", "content": []},
    ]
    path = tmp_path / "stream.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"type": "assistant", "message": {"content": calls}},
                {"type": "user", "message": {"content": returns}},
                {"type": "result", "is_error": False},
            ]
        )
    )
    assert capture_reads(read_trace(path)) == {"read.png"}
    verdict = {
        "task_complete": True,
        "readable": True,
        "usable": True,
        "preference": False,
        "defects": [],
        "reasons": ["The task is complete."],
    }
    assert valid_verdict(verdict, 1)
    assert valid_verdict(verdict, 2)
    verdict.pop("usable")
    assert not valid_verdict(verdict, 2)
    assert not valid_verdict({"winner": "leaf"}, 1)


def test_comparison_snapshots_exclude_later_leaf_feedback(tmp_path, monkeypatch):
    """Script the external model; real admission and publication preserve user input."""
    from leaf_dev import arrangement_eval
    from leaf_dev.harness import run_leaf

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    run = arrangement_eval.Run("document", ROOT, evidence)
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
                item["detail"]["options"]
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
        item["detail"]["options"]
        for item in state["state"]
        if item["widget"] == "decision"
    ) == ["b"]


def test_native_judges_keep_unknown_cost_distinct_from_observed_zero(
    tmp_path, monkeypatch
):
    from leaf_dev import arrangement_eval, reader_eval

    # Replace the external CC judge invocation with native result records. Both
    # real review helpers parse the result and write their ordinary diagnostics.
    verdict = {
        "task_complete": True,
        "readable": True,
        "usable": True,
        "preference": False,
        "satisfies_request": True,
        "count_consistent": True,
        "defects": [],
        "reasons": ["The request is satisfied."],
    }
    for index, cost in enumerate((None, 0, 0.125)):
        record = {"type": "result", "is_error": False, "result": json.dumps(verdict)}
        if cost is not None:
            record["total_cost_usd"] = cost

        def native_judge(*args, record=record, **kwargs):
            return [record]

        monkeypatch.setattr(arrangement_eval, "claude", native_judge)
        monkeypatch.setattr(reader_eval, "claude", native_judge)
        run = arrangement_eval.Run("document", ROOT, tmp_path, "cc", "html")
        reviews = [
            arrangement_eval.judge_output(run, 1, tmp_path / f"arrangement-{index}"),
            reader_eval.review("Read this page", run, 1, tmp_path / f"reader-{index}"),
        ]
        for review in reviews:
            assert review["completed"] and review["valid_verdict"]
            assert review["cost_usd"] == cost
            assert review["cost_known"] is (cost is not None)
