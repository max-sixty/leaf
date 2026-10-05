"""Native Promptfoo Python provider for a catalog task's complete workflow.

The test's metadata names the executor and its scenario, a key of the executor's
`CASES`; the provider column names the harness, condition and arm. Each call gets a
fresh evidence directory, so repetitions never share one, and the response's
`metadata.work` names it. An executor that declares `rubrics` also gets `shots`,
the sample's directory under the run's screenshot tree, which is all its judge may
read. Both are named by the case but not the column, so no path the judge sees
tells the arm or condition. Errors remain provider errors.
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
    executor = import_module(metadata["executor"])
    judged = (
        {"shots": Path(config["screenshots"]) / work.name}
        if hasattr(executor, "rubrics")
        else {}
    )
    response = executor.execute_scenario(
        metadata["scenario"],
        Path(config["payload"]),
        work,
        **judged,
        harness=config["harness"],
        condition=config["condition"],
    )
    response.setdefault("metadata", {})["work"] = str(work)
    return response
