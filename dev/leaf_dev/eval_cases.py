"""Read declarative inputs and native Promptfoo assertions for workflow providers.

The catalog selects a Python executor and scenario. Its YAML definition owns the
authored task and semantic grading; the executor only prepares and drives that
task and extracts structured evidence. Assertions use Promptfoo's schema unchanged.
"""

import yaml

from leaf_dev import ROOT


def definition(name: str) -> dict:
    """The workflow module's YAML, shared by its execution and catalog readers."""
    return yaml.safe_load((ROOT / "evals/workflows" / f"{name}.yaml").read_text())


_EVAL = definition("eval")
DEFAULT_VIEWPORTS = tuple(_EVAL["default_viewports"])
VIEWPORTS = {
    name: (tuple(value["viewport"]), value["description"])
    for name, value in _EVAL["viewports"].items()
}


def selected_viewports(names: tuple[str, ...] = DEFAULT_VIEWPORTS) -> dict:
    """The run's centrally selected sizes, independent of its task cases."""
    return {name: VIEWPORTS[name] for name in names}
