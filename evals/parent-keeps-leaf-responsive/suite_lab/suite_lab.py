"""Inspect or verify the suite-cost report; verification models a 40 s service."""

import json
import sys
import time
from pathlib import Path

from report import summarize

root = Path(__file__).parent
rows = json.loads((root / "measurements.json").read_text())


def record(operation):
    with (root / "operations.jsonl").open("a") as stream:
        stream.write(json.dumps({"at": time.time(), "operation": operation}) + "\n")


record(sys.argv[1])
if sys.argv[1] == "inspect":
    print(json.dumps({"measurements": rows, "report": summarize(rows)}, indent=2))
elif sys.argv[1] == "verify":
    time.sleep(40)
    record("waited")
    result = summarize(rows)
    assert result["total_s"] == 37, result
    assert result["phases"] == {"browser": 30, "model": 2, "process": 5}, result
    record("verified")
    print("Verification passed")
else:
    raise SystemExit("Use inspect or verify")
