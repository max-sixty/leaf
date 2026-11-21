"""Prepare an installation tree with a compiled kernel (`_distribution`)."""

from pathlib import Path

import click

from leaf_dev.commands.site._distribution import prepare


@click.command()
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="New installation-tree directory; must not already exist.",
)
def distribution(output: Path) -> None:
    """Build a prepared, compiler-free plugin installation tree."""
    prepare(output.resolve())
    click.echo(f"✓ Prepared installation → {output}")
