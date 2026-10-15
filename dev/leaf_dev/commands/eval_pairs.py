"""Judge two columns' samples of an authored task side by side.

This command pairs each task's samples across its two columns in the order they
ran, and lets a judge explore disposable live copies of their final pages. Each
copy uses its original runtime payload. Both orders are judged; only a winner
both completed judgments name counts. Incomplete exploration is recorded as
insufficient evidence, rather than a tie or a quality result. Model judgments
and their native browser/agent traces are retained separately from execution checks.
Verdicts go to `pairs.json` in the first run's directory.
"""

import json
import tempfile
from collections import defaultdict
from pathlib import Path

import click

from leaf_dev.arrangement_eval import (
    CASES,
    REACHABLE,
    TASKS,
    WIDTHS,
    judge_pages,
    later_messages,
    phases,
)
from leaf_dev.eval_cases import definition

DEFINITION = definition("eval_pairs")
ASPECTS = tuple(DEFINITION["aspects"])
JUDGE = DEFINITION["prompt"]
VERDICT = DEFINITION["output_schema"]


def samples(runs: list[Path]) -> dict[str, dict[str, list[dict]]]:
    """Each authored task's samples by column, in the order they started."""
    found = defaultdict(lambda: defaultdict(list))
    for run in runs:
        results = json.loads((run / "results.json").read_text())["results"]["results"]
        for result in results:
            metadata = (result.get("response") or {}).get("metadata") or {}
            subject = (metadata.get("diagnostics") or {}).get("subject")
            if subject not in CASES or "work" not in metadata:
                continue
            work = Path(metadata["work"])
            found[subject][result["provider"]["label"]].append(
                {
                    "sample": work.name,
                    "work": work,
                    "diagnostics": metadata["diagnostics"],
                    "checks": metadata.get("checks") or {},
                    "shots": run / "screenshots" / work.name,
                    "started": (work / "prompt-1.txt").stat().st_mtime,
                }
            )
    for columns in found.values():
        for column in columns.values():
            column.sort(key=lambda sample: sample["started"])
    return found


def brief(subject: str) -> str:
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        *later_messages(subject, "the first version"),
    ]
    lines += [
        "",
        DEFINITION["brief_intro"],
    ]
    return "\n".join(lines)


def judge(subject: str, a: dict, b: dict, evidence: Path) -> dict | None:
    """One judgment of A against B, or None when the judge gives no verdict."""
    evidence.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="judge-", dir=evidence))
    version = str(phases(subject)[-1])
    if any(
        not sample["diagnostics"]["phases"].get(version, {}).get("page")
        or not sample["diagnostics"].get("payload")
        for sample in (a, b)
    ):
        (evidence / "response.json").write_text(
            json.dumps(
                {
                    "error": "Comparison lacks a saved final page or its original runtime.",
                    "metadata": {"evidence": str(attempt)},
                },
                indent=2,
            )
        )
        return None
    response = judge_pages(
        {
            label: {
                "page": Path(sample["diagnostics"]["phases"][version]["page"]),
                "payload": Path(sample["diagnostics"]["payload"]),
                "condition": sample["diagnostics"]["condition"],
            }
            for label, sample in (("A", a), ("B", b))
        },
        {name: viewport for name, (viewport, _) in WIDTHS.items()},
        JUDGE.format(brief=brief(subject), reachable=REACHABLE),
        VERDICT,
        attempt,
    )
    (evidence / "response.json").write_text(json.dumps(response, indent=2))
    return response.get("output")


def by_column(verdict: dict | None, columns: dict[str, str]) -> dict | None:
    """A verdict's winners named by column rather than position, or None where the
    judge gave no verdict."""
    if verdict is None:
        return None
    named = {**columns, "tie": "tie"}
    return {
        "status": verdict["status"],
        **{key: named[verdict[key]] for key in (*ASPECTS, "overall")},
        "margin": verdict["margin"],
        "defects": {columns[p]: verdict[f"defects_{p}"] for p in ("A", "B")},
        "reason": verdict["reason"],
    }


@click.command()
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True, path_type=Path),
)
def eval_pairs(runs: tuple[Path, ...]):
    """Judge each authored task's samples across two columns of RUNS, pairwise.

    RUNS are run directories under `.tmp/eval/` whose authored tasks ran in two
    columns, such as `--condition both` or `--base`. The Nth sample of a task in
    one column pairs with the Nth in the other, so run them the same number of
    times. Each pair is judged with each column in each position."""
    pairs = []
    for subject, columns in sorted(samples(list(runs)).items()):
        if len(columns) != 2:
            click.echo(f"{subject}: {len(columns)} columns, not 2; skipped")
            continue
        (first, firsts), (second, seconds) = sorted(columns.items())
        if len(firsts) != len(seconds):
            raise click.ClickException(
                f"{subject}: {first} has {len(firsts)} samples and {second} has "
                f"{len(seconds)}; run each column the same number of times"
            )
        for n, (x, y) in enumerate(zip(firsts, seconds), 1):
            orders = []
            for order, (a, b, names) in enumerate(
                ((x, y, {"A": first, "B": second}), (y, x, {"A": second, "B": first})),
                1,
            ):
                evidence = runs[0] / "pairs" / f"{subject}-{n}-order-{order}"
                orders.append(by_column(judge(subject, a, b, evidence), names))
            complete = all(o and o["status"] == "complete" for o in orders)
            winners = {o["overall"] for o in orders if o}
            status = (
                "unscored"
                if not all(orders)
                else "insufficient_evidence"
                if not complete
                else "split"
                if len(winners) != 1
                else "tie"
                if winners == {"tie"}
                else "complete"
            )
            pairs.append(
                {
                    "subject": subject,
                    "pair": n,
                    "samples": {first: x["sample"], second: y["sample"]},
                    "orders": orders,
                    "status": status,
                    "winner": winners.pop() if status == "complete" else None,
                }
            )
            click.echo(
                f"{subject} {n}: "
                + " / ".join(o["overall"] if o else "no verdict" for o in orders)
                + f" -> {pairs[-1]['winner'] or status}"
            )
    (runs[0] / "pairs.json").write_text(json.dumps(pairs, indent=2) + "\n")
    click.echo(f"verdicts: {runs[0] / 'pairs.json'}")
