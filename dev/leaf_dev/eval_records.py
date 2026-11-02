"""Read execution identity from the retained Promptfoo result and its provider.

The saved provider configuration owns the requested author model, condition and
viewport names, including when execution fails before producing diagnostics.
Native provider IDs identify their harness; workflow configurations
name it explicitly. A result's provider label joins that configuration;
the provider id alone is shared by multiple arms and models. The saved test metadata
owns the execution kind. Actual capture dimensions remain in the result's diagnostics,
and judge responses own their own model, so neither is inferred from the author.

This is a report reading of the existing records, not a second persisted schema.
Copied run indexes must retain the provider configurations their results name.
"""


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
