"""`leaf-dev`: developer commands loaded only when selected.

Each module in the commands package is a command named after it (`bench.py` for
`leaf-dev bench`), and each package in it is a group of the commands its own modules
are (`suite/flake.py` for `leaf-dev suite flake`), apart from a module whose name
starts with `_`, which is its package's own helper. Help finds the names without
importing a module, and describes each command or group by the first paragraph of its
module's or package's docstring, read from source; a group's line names its commands.
A command module defines the Click command or group of its command's name, which owns
its options and detailed help.
"""

import ast
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules
from types import ModuleType

import click

from leaf_dev import commands


def summary(source: Path) -> str:
    """The first paragraph of a module's docstring, read without importing it."""
    docstring = ast.get_docstring(ast.parse(source.read_text())) or ""
    return " ".join(docstring.split("\n\n")[0].split())


class DeveloperCommands(click.Group):
    """The commands and groups one package of `leaf_dev.commands` holds."""

    def __init__(self, package: ModuleType = commands, **attrs):
        super().__init__(**attrs)
        self.package = package

    def invoke(self, ctx: click.Context):
        """Present a refusal from Leaf's own code as a Click error, as `leaf` does."""
        from leaf.refusals import Refused

        try:
            return super().invoke(ctx)
        except Refused as error:
            raise click.ClickException(str(error)) from error

    def entries(self) -> dict[str, bool]:
        """Each command's name, and whether it is a group."""
        return {
            module.name.replace("_", "-"): module.ispkg
            for module in iter_modules(self.package.__path__)
            if not module.name.startswith("_")
        }

    def list_commands(self, ctx):
        return sorted(self.entries())

    def get_command(self, ctx, cmd_name):
        group = self.entries().get(cmd_name)
        if group is None:
            return None
        module = import_module(f"{self.package.__name__}.{cmd_name.replace('-', '_')}")
        if group:
            return DeveloperCommands(module, name=cmd_name, help=module.__doc__)
        for value in vars(module).values():
            if isinstance(value, click.Command) and value.name == cmd_name:
                return value
        raise click.ClickException(f"{module.__name__} defines no command {cmd_name}")

    def format_commands(self, ctx, formatter):
        def described(name: str) -> str:
            stem = Path(self.package.__path__[0], name.replace("-", "_"))
            if not self.entries()[name]:
                return summary(stem.with_suffix(".py"))
            members = DeveloperCommands(
                import_module(f"{self.package.__name__}.{name.replace('-', '_')}")
            ).list_commands(ctx)
            return f"{summary(stem / '__init__.py')} ({', '.join(members)})"

        names = self.list_commands(ctx)
        groups = self.entries()
        for title, chosen in (("Commands", False), ("Groups", True)):
            rows = [(name, described(name)) for name in names if groups[name] == chosen]
            if rows:
                with formatter.section(title):
                    formatter.write_dl(rows)


@click.group(cls=DeveloperCommands)
def cli() -> None:
    """Leaf's developer tooling. Use COMMAND --help for command options."""
