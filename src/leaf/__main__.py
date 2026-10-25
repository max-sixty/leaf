"""The managed application entry for the console script and `python -m leaf`.

Click parses and dispatches every command here, the harness entries `leaf hook` and
`leaf session-end` included. Loading Click costs a managed hook about 8 ms of CPU
(measured on macOS), which is accepted so that one parser owns every command's
arguments, usage and errors rather than a second hand-rolled one for the hooks.

Two paths stay off this entry and Click: `bin/leaf` runs cold SessionEnd cleanup and
its gate for hooks registered `--if-claimed` through `state.py` without a managed
environment, and runs a sandboxed command through the bridge client (`bridge.py`),
which forwards its arguments to Leaf unparsed.
"""

from leaf.cli import cli


def main() -> None:
    cli(prog_name="leaf")


if __name__ == "__main__":
    main()
