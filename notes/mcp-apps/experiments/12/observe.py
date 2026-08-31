#!/usr/bin/env python3
"""Repeat the evidence-bearing app after its two CSS corrections."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HERE = Path(__file__).parent
source = HERE.parent / "11/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_11_observe", source)
experiment = module_from_spec(spec)
spec.loader.exec_module(experiment)
experiment.HERE = HERE
experiment.base.HERE = HERE


if __name__ == "__main__":
    experiment.main()
