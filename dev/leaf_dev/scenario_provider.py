"""Native Promptfoo Python provider for a catalog task's complete workflow.

Executors own the steps and fixed checks. The catalog supplies explicit host,
condition, payload and evidence addresses; errors remain provider errors.
"""

import os
from importlib import import_module
from pathlib import Path


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config, variables = options["config"], context["vars"]
    os.environ["CLAUDE_CONFIG_DIR"] = config["claude_config_dir"]
    module = import_module(config["executor"])
    return module.execute_scenario(
        variables["case"],
        Path(config["payload"]),
        Path(variables["work"]),
        host=config["host"],
        condition=config["condition"],
    )
