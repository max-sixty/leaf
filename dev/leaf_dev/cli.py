"""`leaf-dev`: developer commands loaded only when selected.

Root help discovers names from the commands package without importing its modules,
and describes each command by the first paragraph of its module's docstring, read
from source. Each command owns its options and detailed help.
"""

import ast
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

import click

from leaf_dev import commands


def summary(cmd_name: str) -> str:
    """The first paragraph of a command module's docstring, without importing it."""
    source = Path(commands.__path__[0], f"{cmd_name.replace('-', '_')}.py")
    docstring = ast.get_docstring(ast.parse(source.read_text())) or ""
    return " ".join(docstring.split("\n\n")[0].split())


class DeveloperCommands(click.Group):
    def invoke(self, ctx: click.Context):
        """Present a refusal from Leaf's own code as a Click error, as `leaf` does."""
        from leaf.refusals import Refused

        try:
            return super().invoke(ctx)
        except Refused as error:
            raise click.ClickException(str(error)) from error

    def list_commands(self, ctx):
        return sorted(
            module.name.replace("_", "-") for module in iter_modules(commands.__path__)
        )

    def get_command(self, ctx, cmd_name):
        if cmd_name not in self.list_commands(ctx):
            return None
        name = cmd_name.replace("-", "_")
        module = import_module(f"{commands.__name__}.{name}")
        return getattr(module, name)

    def format_commands(self, ctx, formatter):
        with formatter.section("Commands"):
            formatter.write_dl(
                (name, summary(name)) for name in self.list_commands(ctx)
            )


@click.group(cls=DeveloperCommands)
def cli() -> None:
    """Leaf's developer tooling. Use COMMAND --help for command options."""
