"""Fresh-reader calibration on the authored triage-board example.

A fixed independent judge gets only the user's original request and neutral
screenshots. The shipped authored triage board has seven cards. Its seeded
header claims eight; the corrected count control claims seven. Count detection and false alarms are
scored independently of other page defects, author activity and expense. This
establishes a narrow count calibration, not general page acceptance or reader
reliability. The same review helper can read an actual authored example.
"""

import json
import re
import tempfile
from pathlib import Path

from leaf_dev import ROOT
from leaf_dev.arrangement_eval import Run, capture_phase, capture_reads, claude, stage
from leaf_dev.harness import build_source, completed, observed_sum, trace_result

REQUEST = """Make a v2.4 release triage board with these seven defects: migration reruns,
digest email timezone, CSV export quoting, webhook retry delays, logout with an expired
session, HEIC avatar uploads and search missing renamed projects. Only the migration
blocks release because the next migration would apply account credits twice. Keep
all seven defects visible with their priorities, show the total open count, and let
me move cards. The release cut is Thursday, two days away."""


def fixture(total: int) -> str:
    """The actual authored triage example with one controlled header count."""
    source = (ROOT / "examples/triage-board.html").read_text()
    marker = 'id="count-open" value="7"'
    if source.count(marker) != 1:
        raise ValueError("Triage reader calibration needs its declared count metric")
    return source.replace(marker, f'id="count-open" value="{total}"')


def review(request: str, run: Run, phase: int, destination: Path) -> dict:
    """Review rendered evidence without access to the author's context or files."""
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="leaf-fresh-reader-") as temporary:
        cwd, shots = Path(temporary) / "cwd", Path(temporary) / "shots"
        cwd.mkdir()
        shots.mkdir()
        captures, expected = stage(run, phase, "page", shots)
        prompt = f"""Read this page as the user who made this request:
<request>
{request}
</request>

Read every screenshot below with the Read tool. They show the same page at laptop,
narrow and phone widths; each width runs top to bottom with overlap. Identify visible
errors or missing content that would stop the page satisfying the request. Judge only
what the request and screenshots establish. State separately whether the displayed total matches the cards and the requested
seven defects. Other defects do not change that count verdict. Reply only with JSON:
{{"satisfies_request": true|false, "count_consistent": true|false, "defects": ["…"], "reasons": ["…"]}}

{chr(10).join(captures)}"""
        (destination / "prompt.txt").write_text(prompt)
        trace = claude(
            prompt,
            cwd,
            destination / "stream.jsonl",
            destination / "err.txt",
            tools="Read",
            dirs=[shots],
        )
    answer = trace_result(trace)
    raw = answer.get("result", "")
    found = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        verdict = json.loads(found[0]) if found else None
    except json.JSONDecodeError:
        verdict = None
    valid = (
        isinstance(verdict, dict)
        and type(verdict.get("satisfies_request")) is bool
        and type(verdict.get("count_consistent")) is bool
        and isinstance(verdict.get("defects"), list)
        and isinstance(verdict.get("reasons"), list)
        and bool(verdict["reasons"])
    )
    record = {
        "completed": completed(trace),
        "captures_read": bool(expected) and expected <= capture_reads(trace),
        "valid_verdict": valid,
        "verdict": verdict,
        "raw": raw,
        "cost_usd": answer.get("total_cost_usd"),
        "cost_known": answer.get("total_cost_usd") is not None,
        "trace": str(destination / "stream.jsonl"),
    }
    (destination / "review.json").write_text(json.dumps(record, indent=2))
    return record


def expected_checks(case: str = "calibration", *, condition: str = "leaf") -> list[str]:
    return [
        "completed",
        "reader-evidence-complete",
        "reader-defect-detected",
        "reader-count-control-accepted",
    ]


def scores(readings: dict[str, dict]) -> dict[str, bool]:
    """Calibrate the count verdict; other usability judgments stay diagnostic."""
    evidence = all(
        readings[name][field]
        for name in ("seeded", "clean")
        for field in ("completed", "captures_read", "valid_verdict")
    )
    if not evidence:
        return dict.fromkeys(expected_checks(), False)
    seeded, clean = readings["seeded"]["verdict"], readings["clean"]["verdict"]
    return {
        "completed": True,
        "reader-evidence-complete": True,
        "reader-defect-detected": not seeded["count_consistent"],
        "reader-count-control-accepted": clean["count_consistent"],
    }


def execute_scenario(
    case: str, payload: Path, work: Path, *, host: str = "cc", condition: str = "leaf"
) -> dict:
    """Calibrate the fixed reader; no author is invoked to construct either control."""
    work.mkdir(parents=True, exist_ok=True)
    readings = {}
    for name, total in (("seeded", 8), ("clean", 7)):
        directory = work / name
        directory.mkdir()
        page = directory / "page"
        source = directory / "source.html"
        source.write_text(fixture(total))
        (directory / "work-dir").write_text(str(directory))
        run = Run("queue", payload, directory)
        build_source(payload, run.state, source, page)
        capture_phase(run, 1, page)
        readings[name] = review(REQUEST, run, 1, directory / "reader")
    diagnostics = {"readings": readings, "author_invocations": 0}
    cost = observed_sum(reading["cost_usd"] for reading in readings.values())
    return {
        "output": json.dumps(diagnostics),
        **({"cost": cost} if cost is not None else {}),
        "metadata": {"checks": scores(readings), "diagnostics": diagnostics},
    }
