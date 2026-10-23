"""Leaf's developer tooling: what the suite and the eval harnesses share, and the
`leaf-dev` commands (`cli.py`).

Nothing here ships to a harness's environment: the package is a workspace member only
the root dev group installs (`dev/pyproject.toml`).
"""

import sys
from pathlib import Path

# The checkout this package was installed from.
ROOT = Path(__file__).resolve().parents[2]
# Children of this environment reuse its interpreter; another checkout uses its launcher.
LEAF_COMMAND = (sys.executable, "-m", "leaf")


def declared_records() -> dict:
    """Every `state.Record` by its kind, read once each module of `leaf` and
    `leaf_website` that could declare one is imported. The Data structures page
    (`docs.py`) and the browser build's protocol check (`contract-types.mjs`) both
    read them here. It lives in this package because only the dev group installs
    `leaf_website`."""
    import importlib
    import pkgutil

    import leaf_website

    import leaf
    from leaf.state import RECORDS

    for package in (leaf, leaf_website):
        for module in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
            if not module.name.endswith(".__main__"):
                importlib.import_module(module.name)
    return dict(sorted(RECORDS.items()))
