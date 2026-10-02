"""`leaf-dev`: the commands Leaf's developers run, and agents run for them.

A command belongs here once agents keep rewriting it as a throwaway script, or once
CI, a hook or an alias runs it. Each lives in the module that owns its mechanism and
is registered below; `python -m leaf_dev` runs the same group (`__main__.py`).
"""

import click

from leaf_dev.bench_check import bench_check
from leaf_dev.bench_latency import bench_latency
from leaf_dev.bugback import bugback
from leaf_dev.corpus import corpus
from leaf_dev.delivery_eval import delivery_eval
from leaf_dev.example_previews import refresh_previews
from leaf_dev.flake import flake
from leaf_dev.instructions_eval import instructions_eval
from leaf_dev.keydocs import keydocs
from leaf_dev.leaf_assets import fetch_assets
from leaf_dev.page_fixtures import publish_media
from leaf_dev.preview import preview
from leaf_dev.probe import probe
from leaf_dev.profile import profile
from leaf_dev.record_demo import record_demo
from leaf_dev.site import site
from leaf_dev.stills import stills
from leaf_dev.verify_codex_task import verify_codex_task
from leaf_dev.verify_site import verify_site


@click.group()
def cli() -> None:
    """Leaf's developer tooling."""


cli.add_command(preview)
cli.add_command(corpus)
cli.add_command(keydocs)
cli.add_command(bugback)
cli.add_command(flake)
cli.add_command(instructions_eval)
cli.add_command(probe)
cli.add_command(stills)
cli.add_command(site)
cli.add_command(verify_site)
cli.add_command(fetch_assets)
cli.add_command(publish_media)
cli.add_command(refresh_previews)
cli.add_command(record_demo)
cli.add_command(bench_latency)
cli.add_command(profile)
cli.add_command(bench_check)
cli.add_command(delivery_eval)
cli.add_command(verify_codex_task)
