"""Assemble the published site (https://leaf.page/) into .tmp/site (`_build`).

    uv run leaf-dev site build

`pnpm run site:dev` builds and then serves the result through `wrangler dev`.
"""

from pathlib import Path

import click

from leaf_dev.commands.site._build import build_site
from leaf_dev.website import SITE, asset_site


@click.command("build")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=SITE,
    help="Build destination (default: .tmp/site).",
)
def site(output: Path) -> None:
    """Build leaf.page and its edge assets."""
    output = output.resolve()
    build_site(output)
    click.echo(
        f"✓ {len(list(output.rglob('*.html')))} pages → {output} and {asset_site(output)}"
    )
