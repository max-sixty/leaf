"""`leaf-dev`: the commands Leaf's developers run, and agents run for them.

A command belongs here once agents keep rewriting it as a throwaway script, or once
CI, a hook or an alias runs it. Each lives in the module that owns its mechanism and
is registered below; `python -m leaf_dev` runs the same group (`__main__.py`).
"""

from pathlib import Path

import click

from leaf_dev.example_assets import fetch_previews
from leaf_dev.example_previews import refresh_previews
from leaf_dev.harness import build_arm
from leaf_dev.probe import probe
from leaf_dev.record_demo import record_demo
from leaf_dev.site import site
from leaf_dev.stills import stills


@click.group()
def cli() -> None:
    """Leaf's developer tooling."""


@cli.command()
@click.argument("ref")
@click.argument("dest", type=click.Path(path_type=Path))
def arm(ref: str, dest: Path) -> None:
    """Build an arm, the plugin payload at git REF, at DEST."""
    click.echo(f"{dest}: {build_arm(ref, dest.resolve())}")


cli.add_command(probe)
cli.add_command(stills)
cli.add_command(site)
cli.add_command(fetch_previews)
cli.add_command(refresh_previews)
cli.add_command(record_demo)
