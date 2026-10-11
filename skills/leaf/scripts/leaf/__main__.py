"""The one application entry, for `python -m leaf` and the console script.

`bin/leaf` selects the runtime through uv before reaching here, except for cold
SessionEnd cleanup, which runs its standalone stdlib owner directly. A subprocess Leaf
starts has `sys.executable` in hand and needs no launcher or environment manager.

Harnesses call `leaf hook --harness NAME` on every turn, including sessions holding no
page, and `leaf session-end` as a session ends. Both are `HARNESS_ENTRIES`, routed
here without importing Click, and this is their only route: `hook`, alone or with
`--watch` after it, enters the dependency-light hook owner, and `session-end`
delegates to the same cleanup owner `bin/leaf` runs cold, in a managed interpreter.
Any other argv after one of their names is refused with its usage line. Help and
every other invocation use the CLI, whose `prog_name` stays `leaf` for both entry
forms.

A refusal (`refusals.Refused`) from the hook ends here, with its reason on stderr and
exit status 1.
"""

import sys


def _hook(args: list[str]) -> None:
    if len(args) < 2 or args[0] != "--harness" or args[2:] not in ([], ["--watch"]):
        sys.exit("usage: leaf hook --harness NAME [--watch]")
    from leaf.hooks import main as hook
    from leaf.refusals import Refused

    try:
        hook(args[1], watch=args[2:] == ["--watch"])
    except Refused as error:
        sys.exit(str(error))


def _session_end(args: list[str]) -> None:
    if args:
        sys.exit("usage: leaf session-end")
    from leaf.state import main as end_session

    end_session()


# The commands harness registrations run, by name, each given the argv after it.
HARNESS_ENTRIES = {"hook": _hook, "session-end": _session_end}


def main() -> None:
    args = sys.argv[1:]
    if args and (entry := HARNESS_ENTRIES.get(args[0])):
        entry(args[1:])
        return
    from leaf.cli import cli

    cli(prog_name="leaf")


if __name__ == "__main__":
    main()
