#!/usr/bin/env python3
"""Call from the selected tool value, then run the complete-page probe."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HERE = Path(__file__).parent
source = HERE.parent / "16/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_16_observe", source)
experiment = module_from_spec(spec)
spec.loader.exec_module(experiment)
experiment.HERE = HERE


if __name__ == "__main__":
    experiment.main(tool_timeout=60_000, wait_for_options=False)
