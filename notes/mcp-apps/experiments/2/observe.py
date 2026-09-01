#!/usr/bin/env python3
"""Run experiment 1's unchanged browser driver, writing into experiment 2."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HERE = Path(__file__).parent
source = HERE.parent / "1/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_1_observe", source)
driver = module_from_spec(spec)
spec.loader.exec_module(driver)
driver.HERE = HERE
driver.main()
