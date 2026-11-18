"""Assemble the published site (https://leaf.page/) into .tmp/site (`_build`).

    uv run leaf-dev site build

`pnpm run site:dev` builds and then serves the result through `wrangler dev`.
"""

from pathlib import Path

import click

from leaf_dev.commands.site._build import build, bundle_published_runtime, prepared_leaf
from leaf_dev.website import SITE, asset_site, site_lock


@click.command("build")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=SITE,
    help="Build destination (default: .tmp/site).",
)
def site(output: Path) -> None:
    """Build leaf.page and its edge assets."""
    from leaf.state import flocked

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # One destination is one publication; independent builds use separate outputs.
    with flocked(site_lock(output)):
        build(output, prepared_leaf(output))
        bundle_published_runtime(output)
    click.echo(
        f"✓ {len(list(output.rglob('*.html')))} pages → {output} and {asset_site(output)}"
    )
