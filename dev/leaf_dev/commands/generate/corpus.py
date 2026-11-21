"""Generate examples/corpus.html: the composable authored fixtures on one page
(`leaf_dev.corpus`).

    uv run leaf-dev generate corpus
"""

import click

from leaf_dev.corpus import generate


@click.command()
def corpus() -> None:
    """Generate the ignored examples/corpus.html snapshot and its companions."""
    try:
        click.echo(generate())
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from None
