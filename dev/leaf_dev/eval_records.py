"""Read retained Promptfoo runs: their samples, judgments and execution identity.

A run's `results.json` is its record. `run_samples` reads every authored result in
it, for `eval report` and for `eval run --from`, which grades those samples again. A
test `eval run --from` writes names the saved results it replays in `metadata.saved`; a
pair or discovery test also names its kind in `metadata.judgment`, and `judgments`
reads those, since they judge samples rather than being samples.

The saved provider configuration owns the requested author model, condition and
viewport names, including when execution fails before producing diagnostics.
Native provider IDs identify their harness; workflow configurations
name it explicitly. A result's provider label joins that configuration;
the provider id alone is shared by multiple arms and models. The saved test metadata
owns the execution kind. A regraded result was authored by the result it replays,
so its identity and screenshots are read from that result's run. Actual capture
dimensions remain in the result's diagnostics, and judge responses own their own
model, so neither is inferred from the author.

This is a reading of the existing records, not a second persisted schema.
Copied run indexes must retain the provider configurations their results name.
"""

import hashlib
import json
from collections import defaultdict
from functools import cache
from pathlib import Path


@cache
def run_record(run: Path) -> dict:
    """A run's `results.json`; retained runs don't change once Promptfoo writes it."""
    return json.loads((run / "results.json").read_text())


def saved_result(reference: dict) -> dict:
    """The saved result a regrade names."""
    results = run_record(Path(reference["run"]))["results"]["results"]
    return {result["id"]: result for result in results}[reference["result"]]


def origin(run: Path, result: dict) -> tuple[Path, dict]:
    """The run and result that recorded an output's author. A regrade names the saved
    result it replays, which may itself be a regrade."""
    while saved := result.get("testCase", {}).get("metadata", {}).get("saved"):
        run, result = Path(saved[0]["run"]), saved_result(saved[0])
    return run, result


def execution_metadata(result: dict, providers: list[dict]) -> dict:
    """Read the selected author and inputs without consulting current model pins."""
    label = result["provider"]["label"]
    config = {provider["label"]: provider["config"] for provider in providers}[label]
    test = result["testCase"]["metadata"]
    return {
        "kind": "authoring"
        if test.get("authoring")
        else "workflow"
        if test.get("executor")
        else "probe",
        "author": {
            "harness": config["harness"]
            if "harness" in config
            else {
                "anthropic:claude-agent-sdk": "claude-code",
                "openai:codex-app-server": "codex",
            }[result["provider"]["id"]],
            "model": config["model"],
        },
        "requested_viewports": config.get("viewports", []),
        "condition": config.get("condition"),
    }


def execution_status(response: dict) -> str:
    """Read native completion before interpreting checks on its authored output."""
    metadata = response.get("metadata") or {}
    checks = metadata.get("checks") or {}
    if (
        checks.get("completed") is False
        or (metadata.get("trace") or {}).get("completed") is False
    ):
        return "incomplete"
    if response.get("error"):
        return "error"
    if checks.get("page") is False or not response.get("output"):
        return "empty"
    return "complete"


def run_samples(runs: tuple[Path, ...]) -> dict:
    """Every authored result by subject and column, including failed attempts with
    no saved page."""
    found = defaultdict(lambda: defaultdict(list))
    retained: dict[str, dict] = {}
    for run in runs:
        for index, result in enumerate(run_record(run)["results"]["results"]):
            if result.get("testCase", {}).get("metadata", {}).get("judgment"):
                continue
            # A copied native result is reusable; a revised grade is a new record.
            identity = hashlib.sha256(
                json.dumps(result, sort_keys=True).encode()
            ).hexdigest()
            if identity in retained:
                retained[identity]["runs"].append(run)
                continue
            authored, original = origin(run, result)
            test = original.get("testCase", {})
            response = result.get("response") or {}
            metadata = response.get("metadata") or {}
            diagnostics = metadata.get("diagnostics") or {}
            subject = (
                diagnostics.get("subject")
                or test.get("metadata", {}).get("case")
                or test.get("description")
                or "Unfinished attempts"
            )
            work = (
                Path(metadata["work"])
                if metadata.get("work")
                else run / f"unsaved-{index}"
            )
            sample = {
                "result_id": result["id"],
                "result": result,
                "identity": identity,
                "sample": work.name,
                "subject": subject,
                "title": test.get("description") or subject,
                "work": work,
                "diagnostics": diagnostics,
                "execution_metadata": execution_metadata(
                    original, run_record(authored)["config"]["providers"]
                ),
                "checks": metadata.get("checks") or {},
                "assertions": result.get("testCase", {}).get("assert", []),
                "execution": execution_status(response),
                "execution_error": response.get("error"),
                "shots": authored / "screenshots" / work.name,
                "runs": [run],
                "gradingResult": result.get("gradingResult"),
                "error": result.get("error")
                or response.get("error")
                or (result.get("gradingResult") or {}).get("reason"),
            }
            retained[identity] = sample
            found[subject][result["provider"]["label"]].append(sample)
    for columns in found.values():
        for members in columns.values():
            for number, sample in enumerate(members, 1):
                sample["attempt"] = number
    return found


def judgments(runs: tuple[Path, ...], kind: str) -> list[tuple[Path, dict, dict]]:
    """The `eval run --from` judgments of one kind in RUNS: each result with the run
    holding it and its one assertion's result, empty where no assertion ran."""
    return [
        (
            run,
            result,
            ((result.get("gradingResult") or {}).get("componentResults") or [{}])[0],
        )
        for run in runs
        for result in run_record(run)["results"]["results"]
        if result.get("testCase", {}).get("metadata", {}).get("judgment") == kind
    ]
