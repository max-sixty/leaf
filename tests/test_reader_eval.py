"""Fresh-reader calibration distinguishes detected defects from false alarms."""

from leaf_dev.reader_eval import expected_checks, scores


def test_reader_calibration_requires_evidence_and_clean_control():
    readings = {
        "seeded": {
            "completed": True,
            "captures_read": True,
            "valid_verdict": True,
            "verdict": {
                "satisfies_request": False,
                "count_consistent": False,
                "defects": ["Eight claimed defects but only seven cards."],
            },
        },
        "clean": {
            "completed": True,
            "captures_read": True,
            "valid_verdict": True,
            "verdict": {
                "satisfies_request": True,
                "count_consistent": True,
                "defects": [],
            },
        },
    }
    assert scores(readings) == dict.fromkeys(expected_checks(), True)
    readings["seeded"]["verdict"]["count_consistent"] = True
    assert not scores(readings)["reader-defect-detected"]
    readings["seeded"]["verdict"]["count_consistent"] = False
    readings["clean"]["verdict"]["satisfies_request"] = False
    readings["clean"]["verdict"]["defects"] = ["Unrelated phone layout defect"]
    assert scores(readings)["reader-count-control-accepted"]
    readings["clean"]["verdict"]["count_consistent"] = False
    assert not scores(readings)["reader-count-control-accepted"]
    readings["seeded"]["captures_read"] = False
    assert scores(readings) == dict.fromkeys(expected_checks(), False)
