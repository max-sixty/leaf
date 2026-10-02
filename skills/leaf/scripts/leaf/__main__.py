"""The one application entry, for `python -m leaf` and the console script.

`bin/leaf` selects the runtime through uv before reaching here, except for cold
SessionEnd cleanup, which runs its standalone stdlib owner directly. A subprocess Leaf
starts has `sys.executable` in hand and needs no launcher or environment manager.

Hosts call `leaf hook` on every turn, including sessions holding no page. Its two
protocol invocations enter the dependency-light hook owner before importing Click
or registering other commands. Help and every other invocation use the CLI, whose
`prog_name` stays `leaf` for both entry forms.
`leaf session-end` delegates to the same cleanup owner in a managed interpreter.

A process here is one command, and keeps what it reads of the pages it read most
recently until it ends (`page_memory.PageMemories`), however long it runs: `leaf
wait`, a hook's watch and the Codex carrier read the pages they own for hours. A
server's requests keep their page's memory instead (`http.page_endpoint`).
"""

import sys

from leaf.page_memory import PageMemories, holding_pages


def main() -> None:
    args = sys.argv[1:]
    if args == ["session-end"]:
        from leaf.session_cleanup import main as end_session

        end_session()
        return
    with holding_pages(PageMemories()):
        if args in (["hook"], ["hook", "--watch"]):
            from leaf.hooks import main as hook

            hook(watch=args == ["hook", "--watch"])
            return
        from leaf.cli import cli

        cli(prog_name="leaf")


if __name__ == "__main__":
    main()
