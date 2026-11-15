"""Grade a retained run's saved outputs again, through Promptfoo.

`leaf-dev eval run --from RUN` writes a Promptfoo config whose tests replay saved results
instead of running an author. `replay` is the provider of every column: it returns
the saved response a test names in `metadata.saved`, output, metadata and error, so
an assertion reading either grades the sample as it graded the original, and a
response that failed, such as an author that did not complete, fails again without
being graded. By default a test carries its case's current assertions. A named
judgment replaces them:

- `pair` judges two columns' samples of one task on live copies of their saved
  pages, each served by its original runtime. A pair runs as two tests, one per
  presentation order, and a winner counts only where both completed orders name it
  (`eval report` reads them together). Exploration the judge could not finish is
  insufficient evidence rather than a tie, and a pair with a failed response is
  unscored.
- `discovery` explores one sample's saved pages for observations, choosing its own
  window sizes and interactions; a `focus` variable (Promptfoo's `--var focus=...`)
  can direct it. It neither authors samples nor picks winners: a changed request
  needs fresh matched authoring runs.

A judgment's assertion keeps the judge's response, its structured output included,
as `metadata.judge`, and the judge's native evidence in a fresh directory under the
grading run's `judgments/`. Saved task inputs stay authoritative when the catalog
changes; the judge's method comes from this checkout.
"""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from leaf_dev.arrangement_eval import REACHABLE, judge_pages
from leaf_dev.eval_cases import definition
from leaf_dev.eval_records import saved_result

REPLAY = f"file://{Path(__file__)}:replay"
DEFINITION = definition("regrade")
ASPECTS = tuple(DEFINITION["pair"]["aspects"])
FOCUS = "Find useful observations about completing the user's task."


def replay(prompt: str, options: dict, context: dict) -> dict:
    """The saved response the test names, in place of a new author turn.

    A pair's two responses are keyed by their presentation positions, A and B, and
    fail together where either failed."""
    responses = [
        saved_result(reference).get("response") or {}
        for reference in context["test"]["metadata"]["saved"]
    ]
    errors = [r["error"] for r in responses if r.get("error")]
    if len(responses) == 1:
        replayed = {key: responses[0].get(key) for key in ("output", "metadata")}
    else:
        replayed = {
            key: {p: r.get(key) for p, r in zip("AB", responses, strict=True)}
            for key in ("output", "metadata")
        }
    return replayed | ({"error": "; ".join(errors)} if errors else {})


def judgment(name: str, evidence: Path) -> dict:
    """The assertion making the named judgment, with its evidence under EVIDENCE."""
    return {
        "type": "python",
        "value": f"file://{Path(__file__)}:{name}",
        "config": {"evidence": str(evidence)},
        "metric": name,
    }


def saved_comparison(members: list[dict]) -> dict:
    """The saved task is the contract; unlike tasks are not comparable."""
    comparison = members[0]["diagnostics"]["comparison"]
    if any(sample["diagnostics"]["comparison"] != comparison for sample in members[1:]):
        raise ValueError("Compared samples have different saved task inputs.")
    return comparison


def comparison_pages(samples: dict[str, dict], comparison: dict) -> dict:
    """Original-runtime page roles from the captured task, shared by live judges."""
    return {
        label + suffix: {
            "page": Path(sample["diagnostics"]["phases"][version]["page"]),
            "payload": Path(sample["diagnostics"]["payload"]),
            "condition": sample["diagnostics"]["condition"],
            "author_reply": sample["diagnostics"]["phases"][version]["trace"]["reply"],
        }
        for label, sample in samples.items()
        for suffix, version in comparison["phases"].items()
    }


def comparison_handovers(samples: dict[str, dict], comparison: dict) -> dict:
    """Actual inputs by final page, retaining missing decision evidence as unknown."""
    return {
        label: sample["diagnostics"].get("decision")
        for label, sample in samples.items()
        if comparison["decision_task"] is not None
    }


def pair(output, context: dict) -> dict:
    """Judge the test's two saved samples, A and B, side by side."""
    samples = context["providerResponse"]["metadata"]
    comparison = saved_comparison(list(samples.values()))
    columns = {
        position: reference["column"]
        for position, reference in zip(
            "AB", context["test"]["metadata"]["saved"], strict=True
        )
    }
    prompt = DEFINITION["pair"]["prompt"].format(
        brief=comparison["brief"] + "\n\n" + DEFINITION["pair"]["brief_intro"],
        decision_task=comparison["decision_task"]
        if comparison["decision_task"] is not None
        else "No browser decision task applies to these pages.",
        reachable=REACHABLE,
    )
    return graded(
        judge_pages(
            comparison_pages(samples, comparison),
            comparison["widths"],
            prompt,
            DEFINITION["pair"]["output_schema"],
            evidence(context, "pair"),
            handovers=comparison_handovers(samples, comparison),
        ),
        lambda verdict: (
            f"{verdict['status']}: "
            f"{({'tie': 'tie'} | columns)[verdict['overall']]}, {verdict['margin']}. "
            f"{verdict['reason']}"
        ),
    )


def discovery(output, context: dict) -> dict:
    """Explore the test's saved sample for observations; its pass means only that the
    exploration finished."""
    sample = context["providerResponse"]["metadata"]
    comparison = saved_comparison([sample])
    prompt = DEFINITION["discovery"]["prompt"].format(
        comparison=json.dumps(comparison, indent=2),
        focus=context["vars"].get("focus") or FOCUS,
    )
    return graded(
        judge_pages(
            comparison_pages({"page": sample}, comparison),
            comparison["widths"],
            prompt,
            DEFINITION["discovery"]["output_schema"],
            evidence(context, "discovery"),
            handovers=comparison_handovers({"page": sample}, comparison),
        ),
        lambda found: (
            f"{found['status']}: {len(found['observations'])} "
            f"observations. {found['explored']}"
        ),
    )


def evidence(context: dict, name: str) -> Path:
    """A fresh directory for one judgment's native evidence."""
    root = Path(context["config"]["evidence"])
    root.mkdir(parents=True, exist_ok=True)
    subject = context["test"]["metadata"]["subject"].replace("/", "-")
    return Path(tempfile.mkdtemp(prefix=f"{subject}-{name}-", dir=root))


def graded(response: dict, reason: Callable[[dict], str]) -> dict:
    """Promptfoo's assertion result for a judge's response, unscored where the
    judge returned no structured output."""
    judged = response.get("output")
    passed = judged is not None and judged["status"] == "complete"
    return {
        "pass": passed,
        "score": float(passed),
        "reason": f"unscored: {response['error']}"
        if judged is None
        else reason(judged),
        "metadata": {"judge": response},
        **({"tokensUsed": response["tokenUsage"]} if "tokenUsage" in response else {}),
    }
