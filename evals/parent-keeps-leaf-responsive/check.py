"""Check the retained repair and verification independently of the edited fixture."""

import json
import runpy
import sys
from pathlib import Path

snapshot, cutoff = Path(sys.argv[1]), float(sys.argv[2])
rows = json.loads((Path(__file__).parent / "suite_lab/measurements.json").read_text())
assert json.loads((snapshot / "measurements.json").read_text()) == rows
result = runpy.run_path(str(snapshot / "report.py"))["summarize"](rows)
assert result == {
    "total_s": 37,
    "phases": {"browser": 30, "model": 2, "process": 5},
    "tests": [row for row in rows if not row["skipped"]],
}, result
assert any(
    row["operation"] == "verified" and row["at"] <= cutoff
    for row in map(json.loads, (snapshot / "operations.jsonl").read_text().splitlines())
), "No completed verification before the observation cutoff"
print(json.dumps(result))
