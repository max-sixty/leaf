"""Judge two columns' samples of an authored task side by side.

`leaf-dev eval` grades each `arrangement_eval` sample alone, against a rubric strict
enough that the plain HTML comparison of 2026-10-12 failed almost every version in
both conditions. This command reads finished runs, pairs each task's samples across
its two columns in the order they ran, and asks a judge which final version serves
the request better. A judge favors one position, so each pair is judged in both
orders and only a winner both orders name counts; a disagreement is recorded as
such. The judge is a Claude Code child that can use only Read, shown the request,
the later messages, and each page's screenshots as A and B.
Verdicts go to `pairs.json` in the first run's directory.
"""

import json
import tempfile
from collections import defaultdict
from pathlib import Path

import click

from leaf_dev.arms import run_agent, trace_result
from leaf_dev.arrangement_eval import (
    CASES,
    REACHABLE,
    TASKS,
    WIDTHS,
    later_messages,
    listing,
    phases,
)

ASPECTS = ("evidence", "decisions", "width", "phone", "comment", "applied")

JUDGE = """You are judging two web pages built for the same user request. Read the
brief at {brief}, then open every screenshot it lists with the Read tool before
judging. Open no other file.

Judge as the user who made the request would, from what the screenshots show.
{reachable} Ignore which tool or framework made a page and any fixed viewer chrome
outside the page's content; judge the content, its arrangement and its legibility.

Compare A and B on:
- evidence: the request's substantive facts are present and readable
- decisions: the user can see and take the decisions or navigation the request asks for
- width: at the 900px windows, the page follows the standing preference
- phone: the page is usable at 390px
- comment: the final page carries the change the comment asked for where a reader
  of that passage would find it
- applied: the final page records the decisions the user made, as they made them

Name the better page on each, and overall with its margin; list each page's
defects; give your reason in two or three sentences."""

WINNER = {"type": "string", "enum": ["A", "B", "tie"]}
DEFECTS = {"type": "array", "items": {"type": "string"}}
# The verdict's shape, which the judge's structured output holds it to.
VERDICT = {
    "type": "object",
    "properties": {
        **dict.fromkeys((*ASPECTS, "overall"), WINNER),
        "margin": {"type": "string", "enum": ["slight", "clear", "strong"]},
        "defects_A": DEFECTS,
        "defects_B": DEFECTS,
        "reason": {"type": "string"},
    },
    "required": [*ASPECTS, "overall", "margin", "defects_A", "defects_B", "reason"],
    "additionalProperties": False,
}


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


def final_shots(sample: dict, subject: str) -> dict[str, list[str]]:
    """The final version's screenshots by width, top to bottom."""
    version = phases(subject)[-1]
    return {
        name: [
            str(path)
            for path in sorted(
                sample["shots"].glob(f"p{version}-{name}-*.png"),
                key=lambda path: int(path.stem.rsplit("-", 1)[1]),
            )
        ]
        for name in WIDTHS
    }


def brief(subject: str, a: dict, b: dict) -> str:
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        *later_messages(subject, "the first version"),
    ]
    lines += [
        "",
        (
            "Pages A and B were each built for this request, then revised for each "
            "later message. Below are screenshots of each final page at four window "
            "sizes, top to bottom with overlap."
        ),
    ]
    for label, sample in (("A", a), ("B", b)):
        lines += ["", f"Page {label}:", *listing(final_shots(sample, subject))]
    return "\n".join(lines)


def judge(subject: str, a: dict, b: dict, evidence: Path) -> dict | None:
    """One judgment of A against B, or None when the judge gives no verdict."""
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "brief.md").write_text(brief(subject, a, b))
    with tempfile.TemporaryDirectory(prefix="leaf-pairs-") as directory:
        cwd = Path(directory) / "cwd"
        cwd.mkdir()
        trace = run_agent(
            cwd,
            JUDGE.format(brief=evidence / "brief.md", reachable=REACHABLE),
            "--tools",
            "Read",
            "--json-schema",
            json.dumps(VERDICT),
            out=evidence / "stream.jsonl",
            err=evidence / "err.txt",
            dirs=[evidence, a["shots"], b["shots"]],
        )
    return trace_result(trace).get("structured_output")


def by_column(verdict: dict | None, columns: dict[str, str]) -> dict | None:
    """A verdict's winners named by column rather than position, or None where the
    judge gave no verdict."""
    if verdict is None:
        return None
    named = {**columns, "tie": "tie"}
    return {
        **{key: named[verdict[key]] for key in (*ASPECTS, "overall")},
        "margin": verdict["margin"],
        "defects": {columns[p]: verdict[f"defects_{p}"] for p in ("A", "B")},
        "reason": verdict["reason"],
    }


@click.command("eval-pairs")
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
            winners = {o["overall"] for o in orders if o}
            pairs.append(
                {
                    "subject": subject,
                    "pair": n,
                    "samples": {first: x["sample"], second: y["sample"]},
                    "orders": orders,
                    "winner": winners.pop()
                    if len(winners) == 1 and all(orders)
                    else None,
                }
            )
            click.echo(
                f"{subject} {n}: "
                + " / ".join(o["overall"] if o else "no verdict" for o in orders)
                + f" -> {pairs[-1]['winner'] or 'split'}"
            )
    (runs[0] / "pairs.json").write_text(json.dumps(pairs, indent=2) + "\n")
    click.echo(f"verdicts: {runs[0] / 'pairs.json'}")
