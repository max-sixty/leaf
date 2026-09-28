"""`leaf-dev`: the commands Leaf's developers run, and agents run for them.

A command belongs here once agents keep rewriting it as a throwaway script, or once
CI, a hook or an alias runs it. Each lives in the module that owns its mechanism and
is registered below; `python -m leaf_dev` runs the same group (`__main__.py`).
"""

import click

from leaf_dev.bench_check import bench_check
from leaf_dev.bench_latency import bench_latency
from leaf_dev.bugback import bugback
from leaf_dev.ci_failures import ci_failures
from leaf_dev.delivery_ab import delivery_ab
from leaf_dev.example_assets import fetch_previews
from leaf_dev.example_previews import refresh_previews
from leaf_dev.flake import flake
from leaf_dev.guidance_ab import guidance_ab
from leaf_dev.probe import probe
from leaf_dev.profile import profile
from leaf_dev.record_demo import record_demo
from leaf_dev.site import site
from leaf_dev.stills import stills


@click.group()
def cli() -> None:
    """Leaf's developer tooling."""


cli.add_command(bugback)
cli.add_command(flake)
cli.add_command(guidance_ab)
cli.add_command(probe)
cli.add_command(stills)
cli.add_command(site)
cli.add_command(fetch_previews)
cli.add_command(refresh_previews)
cli.add_command(record_demo)
cli.add_command(bench_latency)
cli.add_command(profile)
cli.add_command(bench_check)
cli.add_command(delivery_ab)
cli.add_command(ci_failures)
