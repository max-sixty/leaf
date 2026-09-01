#!/usr/bin/env python3
"""Run experiment 3's browser driver, writing into experiment 4."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HERE = Path(__file__).parent
source = HERE.parent / "3/observe.py"
spec = spec_from_file_location("mcp_apps_experiment_3_observe", source)
driver = module_from_spec(spec)
spec.loader.exec_module(driver)
driver.HERE = HERE
driver.driver.HERE = HERE
driver.main()
