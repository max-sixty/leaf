"""Promptfoo adapter for the canonical frozen-evidence authoring scorer.

One assertion makes one criterion-level judgment, using the same packet and grader
as `eval-score`. Promptfoo retains its detailed status and only measured criteria
become numeric metrics. Observation gaps and grader failures are never counted as
authored defects by the accompanying authoring summary.
"""

import json
import tempfile
from pathlib import Path

from leaf_dev.authoring_score import score_sample


def get_assert(output, context):
    metadata = context["providerResponse"]["metadata"]
    work = Path(metadata["work"])
    run = work.parent.parent
    grades = run / "authoring-grades" / work.name
    grades.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="grade-", dir=grades)) / "packet"
    grade = score_sample(metadata, run, destination)
    status = grade["status"]
    reasons = [
        f"{key}: {value['explanation']}"
        for key, value in grade.get("criteria", {}).items()
        if value["status"] in ("defect", "observation_gap")
    ]
    return {
        "pass": status == "pass",
        "score": int(status == "pass"),
        "reason": "; ".join(
            [f"Authoring: {status}", grade.get("error", ""), *reasons]
        ).strip("; "),
        "namedScores": grade.get("named_scores", {}),
        "metadata": {"authoring_grade": grade},
    }


def summarize_run(run: Path) -> dict:
    """Separate product judgments, unobserved criteria and execution failures."""
    rows = json.loads((run / "results.json").read_text())["results"]["results"]
    grades = []
    for row in rows:
        components = (row.get("gradingResult") or {}).get("componentResults") or []
        recorded = [
            (component.get("metadata") or {})["authoring_grade"]
            for component in components
            if "authoring_grade" in (component.get("metadata") or {})
        ]
        grades.extend(recorded)
        if (
            not recorded
            and (row.get("testCase") or {}).get("metadata", {}).get("executor")
            == "leaf_dev.arrangement_eval"
        ):
            grades.append(
                {
                    "scored": False,
                    "status": "unscored",
                    "error": row.get("error") or "Authoring judgment was not produced",
                }
            )
    result = {
        "samples": len(grades),
        **{
            status: sum(g["status"] == status for g in grades)
            for status in ("pass", "defect", "observation_gap", "unscored")
        },
        "judgment": "model",
        "grades": grades,
    }
    (run / "authoring-summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
