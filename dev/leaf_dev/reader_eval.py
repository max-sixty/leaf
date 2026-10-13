"""Calibrate the screenshot judge on the authored triage-board example.

The shipped triage board shows seven defect cards and a status tile counting open
defects. The `seeded` scenario's status tile claims eight; the `clean` control claims
seven. Each sample shows the judge that grades authored pages one page, and
the YAML case asks the same question of both: whether the displayed total equals the
cards. Seeded passes only when the judge says no, so a judge that agrees with
the rubric's wording fails one of them. This calibrates count reading, not
general page acceptance or judge reliability.
"""

from pathlib import Path

import turbohtml
from leaf.harness import ClaudeCodeHarness

from leaf_dev import ROOT
from leaf_dev.arms import build_source
from leaf_dev.arrangement_eval import Run, capture_phase, listing
from leaf_dev.eval_cases import definition

DEFINITION = definition("reader_eval")
REQUEST = DEFINITION["request"]

# The open count each scenario's status tile claims.
CASES = {name: case["inputs"]["total"] for name, case in DEFINITION["cases"].items()}


def fixture(total: int) -> str:
    """The actual authored triage example with one controlled open count."""
    document = turbohtml.parse((ROOT / "examples/triage-board.html").read_text())
    counts = document.select("#count-open dd strong")
    if len(counts) != 1:
        raise ValueError(
            "Triage reader calibration needs its native open-count reading"
        )
    counts[0].set_text(str(total))
    return document.serialize()


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    return ["completed"]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    shots: Path,
    harness: str = ClaudeCodeHarness.name,
    condition: str = "leaf",
) -> dict:
    """Render the scenario's page; no author is invoked to construct it."""
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source.html"
    source.write_text(fixture(CASES[case]))
    (work / "work-dir").write_text(str(work))
    run = Run("dashboard", payload, work, shots)
    build_source(payload, run.state, source, work / "page")
    captures = capture_phase(run, 1, work / "page")
    return {
        "output": "\n".join(
            [
                f"<request>\n{REQUEST}\n</request>",
                "",
                "Screenshots:",
                *listing(captures),
            ]
        ),
        "metadata": {"checks": {"completed": all(captures.values())}},
    }
