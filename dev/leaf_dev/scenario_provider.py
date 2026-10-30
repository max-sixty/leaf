"""Native Promptfoo Python provider for isolated authoring and complete workflows.

A short authoring case grades its saved page with native assertions. A complete
workflow names its executor and scenario in that executor's YAML definition;
the provider column names the harness, condition and arm. Each call gets a fresh
evidence directory, so repetitions never share one, and the response's
`metadata.work` names it. Authoring cases and executors declaring a `shots`
parameter get a directory under the run's screenshot tree, independently of their
grading assertions. That tree is all a screenshot judge may read. Both directories
are named by the case but not the column, so no path the judge sees
tells the arm or condition. Errors remain provider errors.
"""

import os
import tempfile
from importlib import import_module
from inspect import signature
from pathlib import Path


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config, metadata = options["config"], context["test"]["metadata"]
    from leaf_dev.arms import MODELS

    MODELS[config["harness"]] = config["model"]
    os.environ["CLAUDE_CONFIG_DIR"] = config["claude_config_dir"]
    samples = Path(config["samples"])
    samples.mkdir(parents=True, exist_ok=True)
    work = Path(
        tempfile.mkdtemp(prefix=f"{metadata['case'].replace('/', '-')}-", dir=samples)
    )
    if metadata.get("authoring"):
        from leaf_dev.authoring_eval import execute

        response = execute(
            prompt,
            Path(config["payload"]),
            work,
            metadata,
            harness=config["harness"],
            condition=config["condition"],
            shots=Path(config["screenshots"]) / work.name,
            viewports=tuple(config["viewports"]),
        )
        response.setdefault("metadata", {})["work"] = str(work)
        return response
    executor = import_module(metadata["executor"])
    parameters = signature(executor.execute_scenario).parameters
    inputs: dict = (
        {"shots": Path(config["screenshots"]) / work.name}
        if "shots" in parameters
        else {}
    )
    if "viewports" in parameters:
        inputs["viewports"] = tuple(config["viewports"])
    response = executor.execute_scenario(
        metadata["scenario"],
        Path(config["payload"]),
        work,
        **inputs,
        harness=config["harness"],
        condition=config["condition"],
    )
    response.setdefault("metadata", {})["work"] = str(work)
    return response
