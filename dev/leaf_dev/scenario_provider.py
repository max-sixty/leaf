"""Promptfoo's native Python provider for a complete Leaf scenario trajectory.

The runner supplies explicit suite, case, payload and evidence addresses. Scenario
modules own authoring, resumed turns and live feedback; Promptfoo owns scheduling,
assertions, repetitions and reports. Exceptions remain provider errors.
"""

import os
from importlib import import_module
from pathlib import Path


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config, variables = options["config"], context["vars"]
    # claude_child copies login files, then removes this from each CLI child.
    os.environ["CLAUDE_CONFIG_DIR"] = config["claude_config_dir"]
    module = import_module(f"leaf_dev.{config['suite']}_eval")
    return module.execute_scenario(
        variables["case"], Path(config["payload"]), Path(variables["work"])
    )
