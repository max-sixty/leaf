#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8", "jsonschema>=4", "tinycss2>=1.4"]
# ///

# Operating contract: ../references/operating-contract.md
# TODO: Retarget its four docstring-local phrases and split it by owner.

from leaf_interact.cli import cli

if __name__ == "__main__":
    # `leaf` is the name the skill hands an agent and the name on PATH, so it is
    # the name the usage lines have to say back, whichever way the script was reached.
    cli(prog_name="leaf")
