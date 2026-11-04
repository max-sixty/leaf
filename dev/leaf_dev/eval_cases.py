"""Read declarative inputs and native Promptfoo assertions for workflow providers.

The catalog selects a Python executor and scenario. Its YAML definition owns the
authored task and semantic grading; the executor only prepares and drives that
task and extracts structured evidence. Assertions use Promptfoo's schema unchanged.
"""

import yaml

from leaf_dev import ROOT
from leaf_dev.browser import WINDOWS, Window


def definition(name: str) -> dict:
    """The workflow module's YAML, shared by its execution and catalog readers."""
    return yaml.safe_load((ROOT / "evals/workflows" / f"{name}.yaml").read_text())


DEFAULT_VIEWPORTS = tuple(definition("eval")["default_viewports"])


def selected_viewports(names: tuple[str, ...] = DEFAULT_VIEWPORTS) -> dict[str, Window]:
    """The run's centrally selected windows, independent of its task cases."""
    return {name: WINDOWS[name] for name in names}
