#!/usr/bin/env python3
"""Repeat the complete-page probe with a measured discovery timeout."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HERE = Path(__file__).parent
source = HERE.parent / "16/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_16_observe", source)
experiment = module_from_spec(spec)
spec.loader.exec_module(experiment)
experiment.HERE = HERE


if __name__ == "__main__":
    experiment.main(tool_timeout=60_000)
