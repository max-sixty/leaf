"""`leaf-dev`: the commands Leaf's developers run, and agents run for them.

A command belongs here once agents keep rewriting it as a throwaway script. Each
lives in the module that owns its mechanism and is registered below.
"""

from pathlib import Path

import click

from leaf_dev.bench_check import bench_check
from leaf_dev.bench_latency import bench_latency
from leaf_dev.delivery_ab import delivery_ab
from leaf_dev.harness import build_arm
from leaf_dev.probe import probe
from leaf_dev.profile import profile
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
cli.add_command(bench_latency)
cli.add_command(profile)
cli.add_command(bench_check)
cli.add_command(delivery_ab)
