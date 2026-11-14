"""Grade an authored page by the defects its user would notice, beside the checks.

A Promptfoo `python` assertion for short authoring cases. One Codex agent uses a
live copy of the final page at each width in `evals/workflows/page_defects.yaml`
and lists the defects it finds, without seeing any check. A second, text-only
turn then reads `page check`'s output on the final page, plain and with
`--render`, and the author's own checks with what it did after each, and says
for each defect whether a check reported it and whether the author acted. The
judge stays blind to the checks so that what they report can't steer what it
looks for, which would inflate their measured recall.

The assertion passes when the judge finds no defect. Its metadata carries a
status and reason for every outcome, including an unscored run, and on completion
the defects with their check readings and the findings the author's checks raised,
so a run's defect rate and the checks' recall read from `results.json`. Each
grading keeps its evidence in a fresh `defects-*` directory under the sample, so
grading the sample again with `eval run --from` keeps the earlier judge's.
"""

import json
import tempfile
from pathlib import Path

from leaf_dev.arms import observed_sum, run_agent, scratch, trace_result, trace_summary
from leaf_dev.arrangement_eval import judge_pages
from leaf_dev.browser import WINDOWS
from leaf_dev.eval_cases import definition

DEFINITION = definition("page_defects")
SKILL_PREFIX = definition("eval")["skill_prefix"]
# Each window the judge uses the page in, as its instructions describe it.
WIDTHS = {
    name: {
        "viewport": list(WINDOWS[name].size),
        "description": WINDOWS[name].description,
    }
    for name in DEFINITION["widths"]
}


def match(defects: list[dict], response: dict, evidence: Path) -> tuple[dict, dict]:
    """Set each defect beside what the final and in-session checks reported, with
    the turn's accounting."""
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
    return output, trace_summary(trace)


def get_assert(output: str, context: dict) -> dict:
    response = context["providerResponse"]
    if response.get("error"):
        return unscored(response["error"])
    metadata = response["metadata"]
    work = Path(metadata["work"])
    if not (work / "page" / "index.html").is_file():
        return unscored(
            f"No authored page to inspect at {work / 'page' / 'index.html'}"
        )
    evidence = Path(tempfile.mkdtemp(prefix="defects-", dir=work))
    judged = judge_pages(
        {
            "final": {
                "page": str(work / "page"),
                "payload": metadata["payload"],
                "condition": "leaf",
            }
        },
        WIDTHS,
        DEFINITION["judge"].format(
            request=context["vars"]["prompt"].removeprefix(SKILL_PREFIX)
        ),
        DEFINITION["schemas"]["defects"],
        evidence / "judge",
    )
    if "error" in judged:
        return unscored(judged["error"], evidence)
    verdict = judged["output"]
    if verdict["status"] == "insufficient_evidence":
        return unscored(verdict["reason"], evidence)
    readings, matching = match(verdict["defects"], response, evidence / "match")
    indices = [reading.pop("index") for reading in readings["defects"]]
    if sorted(indices) != list(range(len(verdict["defects"]))):
        return unscored(
            f"the check matcher read defects {sorted(indices)} of "
            f"{len(verdict['defects'])}; see {evidence / 'match'}",
            evidence,
        )
    by_index = dict(zip(indices, readings["defects"], strict=True))
    defects = [
        defect | {"checks": by_index[index]}
        for index, defect in enumerate(verdict["defects"])
    ]
    turns = [judged["metadata"]["trace"], matching]
    tokens = {
        key: observed_sum(turn[f"{key}_tokens"] for turn in turns)
        for key in ("input", "output")
    }
    passed = not defects
    return {
        "pass": passed,
        "score": float(passed),
        "reason": f"{verdict['status']}: {verdict['reason']}",
        "tokensUsed": {
            "prompt": tokens["input"],
            "completion": tokens["output"],
            "total": observed_sum(tokens.values()),
        },
        "metadata": {
            "page_defects": {
                "status": verdict["status"],
                "reason": verdict["reason"],
                "defects": defects,
                "session_findings": readings["session_findings"],
                "judge": judged["metadata"]["trace"],
                "matcher": matching,
                "evidence": str(evidence),
            }
        },
    }


def unscored(reason: str, evidence: Path | None = None) -> dict:
    return {
        "pass": False,
        "score": 0.0,
        "reason": f"unscored: {reason}",
        "metadata": {
            "page_defects": {
                "status": "unscored",
                "reason": reason,
                **({"evidence": str(evidence)} if evidence else {}),
            }
        },
    }
