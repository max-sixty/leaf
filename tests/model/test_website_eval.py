"""Hosted response evals require successful exact-input answers and closed turns."""

from leaf_dev.eval import catalog, prepare
from leaf_dev.website_eval import CASES, expected_checks, grade


def test_hosted_response_checks_reject_missing_failed_and_partial_turns():
    replied = {
        "question": "What blocks release?",
        "replies": [{"text": "The migration."}],
    }
    for turns, statuses, accepted in (
        ([replied, replied], ["completed", "completed"], True),
        ([], [], False),
        ([replied], ["completed"], False),
        ([replied, replied], ["completed", "failed"], False),
        ([replied, replied], ["completed"], False),
    ):
        checks = grade("follow-up", turns, statuses, unchanged=True)
        assert set(checks) == set(expected_checks("follow-up"))
        assert checks["completed"] is accepted
    assert not grade("question", [{"replies": []}], ["completed"], unchanged=True)[
        "replied"
    ]
    assert not grade("question", [replied], ["completed"], unchanged=False)[
        "page-unchanged"
    ]


def test_hosted_cases_run_only_on_codex_and_score_shown_openings(tmp_path):
    cases = catalog()
    addresses = [name for name in cases if name.split("/")[0] == "website-replies"]
    assert {
        cases[name]["metadata"]["scenario"]
        for name in addresses
        if "providerOutput" not in cases[name]
    } == set(CASES)
    config = prepare(
        addresses,
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("claude-code", "codex"),
        ("leaf",),
        tmp_path / "samples",
    )
    assert len(config["providers"]) == 1
    for test in config["tests"]:
        if "providerOutput" in test:
            assert test["providerOutput"]
            assert len(test["assert"]) == 1
            assert test["assert"] == cases[test["metadata"]["case"]]["assert"]
            continue
        assert test["providers"] == ["codex:app-server/candidate/workflow"]
        assert [check["metric"] for check in test["assert"]] == [
            "completed",
            "replied",
            "page-unchanged",
            "answers-user",
            "opening-addresses-user",
        ]
        assert "shown reply updates" in test["assert"][-1]["value"]
