"""Native Promptfoo Python provider for a catalog task's complete workflow.

The test's metadata names the executor and its case; the provider column names the
host, condition and arm. Each call gets a fresh evidence directory under the
column's samples, so repetitions never share one. Errors remain provider errors.
"""

import os
import tempfile
from importlib import import_module
from pathlib import Path


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config, metadata = options["config"], context["test"]["metadata"]
    os.environ["CLAUDE_CONFIG_DIR"] = config["claude_config_dir"]
    samples = Path(config["samples"])
    samples.mkdir(parents=True, exist_ok=True)
    work = Path(
        tempfile.mkdtemp(prefix=f"{metadata['case'].replace('/', '-')}-", dir=samples)
    )
    return import_module(metadata["executor"]).execute_scenario(
        metadata["scenario"],
        Path(config["payload"]),
        work,
        host=config["host"],
        condition=config["condition"],
    )
