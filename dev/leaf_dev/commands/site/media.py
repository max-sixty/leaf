"""Publish content-addressed media used by example pages."""

import tempfile
from pathlib import Path

import click

from leaf.base.schema import MEDIA_DIR
from leaf.serving.media import require_media_type, write_media
from leaf_dev import ROOT
from leaf_dev.leaf_assets import clone, publish
from leaf_dev.page_fixtures import DEFAULT_PACKAGES


@click.command("media")
@click.argument(
    "files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False)
)
def publish_media(files: tuple[str, ...]) -> None:
    """Publish media for the example pages to max-sixty/leaf-assets.

    Each is named by its bytes, as `leaf page media` names it, and added beside the
    catalog's other media; the pin moves to the new revision. Prints the path each
    page names the media by."""
    directory = DEFAULT_PACKAGES.parent.relative_to(ROOT) / "media"
    paths = [Path(file) for file in files]
    for path in paths:
        require_media_type(path)
    with tempfile.TemporaryDirectory(prefix="leaf-assets-") as raw:
        checkout = clone(Path(raw))
        target = checkout / directory
        target.mkdir(parents=True, exist_ok=True)
        named = {
            write_media(target, path.read_bytes(), path.suffix): path for path in paths
        }
        revision = publish(checkout, f"Add {len(named)} example media file(s)")
    for name, path in named.items():
        click.echo(f"/{MEDIA_DIR}/{name}  {path}")
    click.echo(f"  max-sixty/leaf-assets@{revision}")
