"""Inspect or verify the suite-cost report; verification models a 12 s service."""

import json
import sys
import time
from pathlib import Path

from report import summarize

root = Path(__file__).parent
rows = json.loads((root / "measurements.json").read_text())
with (root / "operations.jsonl").open("a") as stream:
    stream.write(json.dumps({"at": time.time(), "operation": sys.argv[1]}) + "\n")
if sys.argv[1] == "inspect":
    print(json.dumps({"measurements": rows, "report": summarize(rows)}, indent=2))
elif sys.argv[1] == "verify":
    time.sleep(12)
    result = summarize(rows)
    assert result["total_s"] == 37, result
    assert result["phases"] == {"browser": 30, "model": 2, "process": 5}, result
    with (root / "operations.jsonl").open("a") as stream:
        stream.write(json.dumps({"at": time.time(), "operation": "verified"}) + "\n")
    print("Verification passed")
else:
    raise SystemExit("Use inspect or verify")
