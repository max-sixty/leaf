"""Grade a retained run's saved outputs again, through Promptfoo.

`leaf-dev eval --from RUN` writes a Promptfoo config whose tests replay saved results
instead of running an author. `replay` is the provider of every column: it returns
the saved response a test names in `metadata.saved`, output and metadata both, so an
assertion reading either grades the sample as it graded the original. By default a
test carries its case's current assertions. A named judgment replaces them:

- `pair` judges two columns' samples of one task on live copies of their saved
  pages, each served by its original runtime. A pair runs as two tests, one per
  presentation order, and a winner counts only where both completed orders name it
  (`eval-report` reads them together). Exploration the judge could not finish is
  insufficient evidence rather than a tie, and a pair whose native author did not
  complete is unscored.
- `discovery` explores one sample's saved pages for observations, choosing its own
  window sizes and interactions; a `focus` variable (Promptfoo's `--var focus=...`)
  can direct it. It neither authors samples nor picks winners: a changed request
  needs fresh matched authoring runs.

A judgment's assertion records the judge's structured output in its metadata under
the judgment's name, beside the judge's response, and keeps the judge's native
evidence in a fresh directory under the `--from` run. Saved task inputs stay
authoritative when the catalog changes; the judge's method comes from this checkout.
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

    A pair's two responses are keyed by their presentation positions, A and B."""
    responses = [
        saved_result(reference)["response"]
        for reference in context["test"]["metadata"]["saved"]
    ]
    if len(responses) == 1:
        return {
            "output": responses[0]["output"],
            "metadata": responses[0].get("metadata") or {},
        }
    return {
        "output": {p: r["output"] for p, r in zip("AB", responses, strict=True)},
        "metadata": {
            p: r.get("metadata") or {} for p, r in zip("AB", responses, strict=True)
        },
    }


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
    if not all(
        (sample.get("checks") or {}).get("completed") for sample in samples.values()
    ):
        return {
            "pass": False,
            "score": 0.0,
            "reason": "unscored: a native author did not complete",
        }
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
        "pair",
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
        "discovery",
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


def graded(name: str, response: dict, reason: Callable[[dict], str]) -> dict:
    """Promptfoo's assertion result for a judge's response, unscored where the
    judge returned no structured output."""
    judged = response.get("output")
    if judged is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"unscored: {response['error']}",
            "metadata": {"judge": response},
        }
    passed = judged["status"] == "complete"
    return {
        "pass": passed,
        "score": float(passed),
        "reason": reason(judged),
        "metadata": {name: judged, "judge": response},
        **({"tokensUsed": response["tokenUsage"]} if "tokenUsage" in response else {}),
    }
