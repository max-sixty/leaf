"""Warm the pinned asset cache for developer builds."""

import click

from leaf_dev.leaf_assets import pinned_assets


@click.command()
def fetch_assets() -> None:
    """Fetch the generated images leaf-assets.json pins."""
    for revision_key in ("revision", "thread_snapshots_revision"):
        click.echo(f"✓ {pinned_assets(revision_key=revision_key)}")
