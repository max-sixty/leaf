"""The one application entry, for `python -m leaf` and the console script.

`bin/leaf` selects the runtime through uv before reaching here, except for cold
SessionEnd cleanup, which runs its standalone stdlib owner directly. A subprocess Leaf
starts has `sys.executable` in hand and needs no launcher or environment manager.

Harnesses call `leaf hook --harness NAME` on every turn, including sessions holding no
page. That invocation, and the same with `--watch` after it, enter the dependency-light
hook owner without importing Click; they are the only route to it, so any other `hook`
argv is refused with its usage line. `leaf session-end` delegates to the same cleanup
owner in a managed interpreter. Help and every other invocation use the CLI, whose
`prog_name` stays `leaf` for both entry forms.
"""

import sys


def main() -> None:
    args = sys.argv[1:]
    if args == ["session-end"]:
        from leaf.state import main as end_session

        end_session()
        return
    if args[:1] == ["hook"]:
        if len(args) < 3 or args[1] != "--harness" or args[3:] not in ([], ["--watch"]):
            sys.exit("usage: leaf hook --harness NAME [--watch]")
        from leaf.hooks import main as hook

        hook(args[2], watch=args[3:] == ["--watch"])
        return
    from leaf.cli import cli

    cli(prog_name="leaf")


if __name__ == "__main__":
    main()
