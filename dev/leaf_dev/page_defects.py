"""Grade an authored page by the defects its user would notice, beside the checks.

A Promptfoo `python` assertion for short authoring cases. One Codex agent uses a
live copy of the final page at each width in `evals/workflows/page_defects.yaml`
and lists the defects it finds, without seeing any check. A second, text-only
turn then reads `page check`'s output on the final page, plain and with
`--render`, and the author's own checks with what it did after each, and says
for each defect whether a check reported it and whether the author acted. The
judge stays blind to the checks so that what they report can't steer what it
looks for, which would inflate their measured recall.

The assertion passes when the judge finds no defect. Its metadata carries the
defects with their check readings and the findings the author's checks raised,
so a run's defect rate and the checks' recall read from `results.json`.
"""

import json
from pathlib import Path

from leaf_dev.arms import run_agent, scratch, trace_result
from leaf_dev.arrangement_eval import judge_pages
from leaf_dev.eval_cases import definition

DEFINITION = definition("page_defects")
SKILL_PREFIX = definition("eval")["skill_prefix"]


def match(defects: list[dict], response: dict, evidence: Path) -> dict:
    """Set each defect beside what the final and in-session checks reported."""
    metadata = response["metadata"]
    prompt = DEFINITION["match"].format(
        defects=json.dumps(list(enumerate(defects)), indent=1),
        plain=metadata["check_output"]["plain"],
        render=metadata["check_output"]["render"],
        log=json.dumps(metadata["check_log"], indent=1),
    )
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "prompt.txt").write_text(prompt)
    with scratch() as cwd:
        trace = run_agent(
            cwd,
            prompt,
            "--json-schema",
            json.dumps(DEFINITION["schemas"]["match"]),
            out=evidence / "stream.jsonl",
            err=evidence / "err.txt",
            harness="codex",
        )
    output = trace_result(trace).get("structured_output")
    if output is None:
        raise RuntimeError(f"the check matcher returned no reading; see {evidence}")
    return output


def get_assert(output: str, context: dict) -> dict:
    response = context["providerResponse"]
    if response.get("error"):
        return unscored(response["error"])
    metadata = response["metadata"]
    work = Path(metadata["work"])
    judged = judge_pages(
        {
            "final": {
                "page": str(work / "page"),
                "payload": metadata["payload"],
                "condition": "leaf",
            }
        },
        DEFINITION["widths"],
        DEFINITION["judge"].format(
            request=context["vars"]["prompt"].removeprefix(SKILL_PREFIX)
        ),
        DEFINITION["schemas"]["defects"],
        work / "defects" / "judge",
    )
    if "error" in judged:
        return unscored(judged["error"])
    verdict = judged["output"]
    if verdict["status"] == "insufficient_evidence":
        return unscored(verdict["reason"])
    readings = match(verdict["defects"], response, work / "defects" / "match")
    by_index = {reading.pop("index"): reading for reading in readings["defects"]}
    defects = [
        defect | {"checks": by_index.get(index)}
        for index, defect in enumerate(verdict["defects"])
    ]
    passed = not defects
    return {
        "pass": passed,
        "score": float(passed),
        "reason": f"{verdict['status']}: {verdict['reason']}",
        "metadata": {
            "page_defects": {
                "defects": defects,
                "session_findings": readings["session_findings"],
                "judge": judged["metadata"]["trace"],
            }
        },
    }


def unscored(reason: str) -> dict:
    return {"pass": False, "score": 0.0, "reason": f"unscored: {reason}"}
