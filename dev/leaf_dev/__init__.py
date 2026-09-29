"""Leaf's developer tooling: what the suite and the eval harnesses share, and the
`leaf-dev` commands (`cli.py`).

Nothing here ships to a host's environment: the package is a workspace member only
the root dev group installs (`dev/pyproject.toml`).
"""

from pathlib import Path

# The checkout this package was installed from.
ROOT = Path(__file__).resolve().parents[2]
