"""Run the transport test's three start commands under one Codex ancestor.

The parent supplies the commands as JSON and a result path. Publish the complete
result atomically so the parent can observe completion before releasing the host.
"""

import json
import subprocess
import sys
from pathlib import Path

from leaf.state import write_json

commands = json.loads(sys.argv[1])
results = []
for command in commands:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    results.append([result.returncode, result.stdout, result.stderr])

write_json(Path(sys.argv[2]), results)
