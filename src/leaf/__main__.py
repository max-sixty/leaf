"""The managed application entry for the console script and `python -m leaf`.

Click owns argument parsing and dispatch. Cold SessionEnd cleanup and the launcher's
unclaimed-hook gate run `state.py` directly without a managed environment.
"""

from leaf.cli import cli


def main() -> None:
    cli(prog_name="leaf")


if __name__ == "__main__":
    main()
