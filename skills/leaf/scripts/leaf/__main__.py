"""The one application entry, for `python -m leaf` and the console script.

`bin/leaf` selects the runtime through uv before reaching here, except for cold
SessionEnd cleanup, which runs its standalone stdlib owner directly. A subprocess Leaf
starts has `sys.executable` in hand and needs no launcher or environment manager.

Harnesses call `leaf hook --harness NAME` on every turn, including sessions holding no
page. That invocation, and the same with `--watch` after it, enter the dependency-light
hook owner before importing Click or registering other commands. Help and every other
invocation use the CLI, whose `prog_name` stays `leaf` for both entry forms.
`leaf session-end` delegates to the same cleanup owner in a managed interpreter.

The hook entry ends a refusal (`refusals.Refused`) here, printing its reason and
exiting 1, as the CLI's `LeafGroup` does for every command.
"""

import sys


def main() -> None:
    args = sys.argv[1:]
    if args == ["session-end"]:
        from leaf.state import main as end_session

        end_session()
        return
    if (
        len(args) > 2
        and args[:2] == ["hook", "--harness"]
        and args[3:] in ([], ["--watch"])
    ):
        from leaf.hooks import main as hook
        from leaf.refusals import Refused

        try:
            hook(args[2], watch=args[3:] == ["--watch"])
        except Refused as error:
            sys.exit(str(error))
        return
    from leaf.cli import cli

    cli(prog_name="leaf")


if __name__ == "__main__":
    main()
