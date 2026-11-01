"""Explore one retained authoring sample without changing its comparison score.

The agent chooses useful variations and follows observations into nearby cases.
This command supplies the frozen task and disposable before/after pages through
the same live browser engine as pair judging. It neither authors new samples nor
selects winners: changed requests need fresh matched authoring runs. Each attempt
retains its observations, uncertainty and native evidence independently of pairs.
"""

import json
import tempfile
from pathlib import Path

import click

from leaf_dev.arrangement_eval import judge_pages
from leaf_dev.commands.eval_pairs import (
    comparison_handovers,
    comparison_pages,
    samples,
    saved_comparison,
)
from leaf_dev.eval_cases import definition

DEFINITION = definition("eval_discover")


@click.command()
@click.argument(
    "run",
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
@click.argument("sample")
@click.option("--focus", default="", help="A question or observation to explore.")
def eval_discover(run: Path, sample: str, focus: str):
    """Explore SAMPLE from RUN for interesting behavior, mainly on desktop.

    SAMPLE is the directory name under RUN/samples, also recorded in results.json.
    The agent chooses window sizes and interactions; --focus can direct a phone
    check, a suspected failure or a task variation worth investigating next.
    Observations and traces go under RUN/discovery/SAMPLE/attempt-*/response.json.
    """
    members = [
        member
        for columns in samples([run]).values()
        for column in columns.values()
        for member in column
        if member["sample"] == sample
    ]
    if len(members) != 1:
        raise click.ClickException(f"Expected one saved sample named {sample!r}.")
    try:
        comparison = saved_comparison(members)
        pages = comparison_pages({"page": members[0]}, comparison)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    directory = run / "discovery" / sample
    directory.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=directory))
    response = judge_pages(
        pages,
        comparison["widths"],
        DEFINITION["prompt"].format(
            comparison=json.dumps(comparison, indent=2),
            focus=focus or "Find useful observations about completing the user's task.",
        ),
        DEFINITION["output_schema"],
        attempt,
        handovers=comparison_handovers({"page": members[0]}, comparison),
    )
    result = attempt / "response.json"
    result.write_text(
        json.dumps(
            {"sample": sample, "comparison": comparison, "focus": focus, **response},
            indent=2,
        )
        + "\n"
    )
    click.echo(result)
    if error := response.get("error"):
        raise click.ClickException(error)
