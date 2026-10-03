"""Arrangement comparisons remove one vocabulary and require complete judge evidence."""

import json

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arrangement_eval import capture_reads, valid_verdict
from leaf_dev.harness import PAYLOAD, copy_working, read_trace


def test_plain_arm_removes_vocabulary_without_changing_shipped_instructions(tmp_path):
    original = (ROOT / "skills/leaf/references/page-authoring.md").read_text()
    payload = tmp_path / "payload"
    copy_working(PAYLOAD, payload)
    smoke = arrangement_plain.build(payload)
    skill = payload / "skills/leaf"
    assert (ROOT / "skills/leaf/references/page-authoring.md").read_text() == original
    assert "layout-sidebar" in original
    assert "main { max-width:" in smoke
    assert "your own CSS" in (skill / "references/page-authoring.md").read_text()
    assert "lf-pane" not in json.loads(
        (skill / "packages/default/registry.json").read_text()
    )
    assert (skill / "assets/layouts.css").read_text() == "@layer lf-layouts {}\n"
    assert "lf-tabs" in json.loads(
        (skill / "packages/default/registry.json").read_text()
    )
    assert (skill / "assets/theme.css").read_text() == (
        ROOT / "skills/leaf/assets/theme.css"
    ).read_text()
    arrangement_plain.check_clean(payload)


def test_judge_requires_successful_capture_reads_and_a_complete_comparison(tmp_path):
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
        "winner": "tie",
        "margin": "slight",
        "by_width": {"laptop": "tie", "narrow": "A", "phone": "B"},
        "reasons": ["Both are readable."],
        "defects": {"A": [], "B": []},
    }
    assert valid_verdict(verdict, 1)
    assert not valid_verdict(verdict, 2)
    verdict["preference"] = {"A": False, "B": False, "why": "Both stack at 900px."}
    assert valid_verdict(verdict, 2)
    verdict["by_width"].pop("phone")
    assert not valid_verdict(verdict, 2)
    assert not valid_verdict({"winner": "leaf"}, 1)
