"""Calibrate the screenshot judge on the authored triage-board example.

The shipped triage board shows seven defect cards and a header count of open
defects. The `seeded` scenario's header claims eight; the `clean` control claims
seven. Each sample shows the judge that grades authored pages one page, and
`rubrics` asks the same question of both: whether the displayed total equals the
cards. Seeded passes only when the judge says no, so a judge that agrees with
the rubric's wording fails one of them. This calibrates count reading, not
general page acceptance or judge reliability.
"""

from pathlib import Path

from leaf_dev import ROOT
from leaf_dev.arms import build_source
from leaf_dev.arrangement_eval import Run, capture_phase, listing

REQUEST = """Make a v2.4 release triage board with these seven defects: migration reruns,
digest email timezone, CSV export quoting, webhook retry delays, logout with an expired
session, HEIC avatar uploads and search missing renamed projects. Only the migration
blocks release because the next migration would apply account credits twice. Keep
all seven defects visible with their priorities, show the total open count, and let
me move cards. The release cut is Thursday, two days away."""

# The open count each scenario's header claims.
CASES = {"seeded": 8, "clean": 7}
COUNT = (
    "Open every screenshot the output lists. A region with its own scroll shows "
    "only its first screen, so count the cards at a width that shows the whole "
    "board. Pass only if the page's displayed total of open defects equals the "
    "number of defect cards on the board."
)


def fixture(total: int) -> str:
    """The actual authored triage example with one controlled header count."""
    source = (ROOT / "examples/triage-board.html").read_text()
    marker = 'id="count-open" value="7"'
    if source.count(marker) != 1:
        raise ValueError("Triage reader calibration needs its declared count metric")
    return source.replace(marker, f'id="count-open" value="{total}"')


def rubrics(scenario: str) -> list[dict]:
    return [
        {
            "type": "agent-rubric" if scenario == "clean" else "not-agent-rubric",
            "metric": "count-control-accepted"
            if scenario == "clean"
            else "count-defect-detected",
            "value": COUNT,
        }
    ]


def expected_checks(case: str, *, condition: str = "leaf") -> list[str]:
    return ["completed"]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    shots: Path,
    harness: str = "cc",
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
