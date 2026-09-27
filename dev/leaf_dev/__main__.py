"""`python -m leaf_dev`: the `leaf-dev` CLI, for a caller that holds an interpreter
rather than the environment's entry point, such as a subprocess spawned from the
suite.
"""

from leaf_dev.cli import cli

cli()
