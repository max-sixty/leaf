"""Judge two columns' samples of an authored task side by side.

This supplements the absolute authoring scorer with a model preference judgment.
Samples pair across columns in recorded order at the same recorded phase. Each
pair is judged in both positions; only agreement establishes a preference.
Insufficient evidence and invalid judge execution establish none. Anonymous
frozen packets contain actual user inputs, screenshots and action/state records;
successful native reads and packet integrity are checked. Each invocation writes
a fresh output directory, preserving historical judgments.
"""

import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import click
import jsonschema

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, run_agent, trace_result
from leaf_dev.arrangement_eval import (
    REACHABLE,
    WIDTHS,
)
from leaf_dev.authoring_score import (
    read_packet,
    sample_inputs,
    stage_packet,
    write_json,
)
from leaf_dev.eval_cases import definition
from leaf_dev.eval_judge import validate_reads
from leaf_dev.eval_provenance import files_identity

DEFINITION = definition("eval_pairs")
ASPECTS = tuple(DEFINITION["aspects"])
JUDGE = DEFINITION["prompt"]
VERDICT = DEFINITION["output_schema"]


def samples(runs: list[Path]) -> dict[str, dict[str, list[dict]]]:
    """Each authored task's samples by column, in the order they started."""
    found = defaultdict(lambda: defaultdict(list))
    seen = set()
    for run in runs:
        results = json.loads((run / "results.json").read_text())["results"]["results"]
        for result in results:
            metadata = (result.get("response") or {}).get("metadata") or {}
            subject = (metadata.get("diagnostics") or {}).get("subject")
            if (
                not subject
                or "work" not in metadata
                or not metadata["diagnostics"].get("phases")
            ):
                continue
            work = Path(metadata["work"])
            if work.resolve() in seen:
                raise click.ClickException(f"Sample supplied more than once: {work}")
            seen.add(work.resolve())
            found[subject][result["provider"]["label"]].append(
                {
                    "sample": work.name,
                    "work": work,
                    "diagnostics": metadata["diagnostics"],
                    "checks": metadata.get("checks") or {},
                    "shots": run / "screenshots" / work.name,
                    "started": (work / "prompt-1.txt").stat().st_mtime,
                    "run": run,
                    "metadata": metadata,
                }
            )
    for columns in found.values():
        for column in columns.values():
            column.sort(key=lambda sample: sample["started"])
    return found


def final_shots(sample: dict, subject: str) -> dict[str, list[str]]:
    """The final version's screenshots by width, top to bottom."""
    recorded = sample["diagnostics"].get("phases") or {}
    version = sample.get("phase") or max(map(int, recorded))
    phase = recorded.get(str(version), recorded.get(version))
    if phase.get("captures"):
        return phase["captures"]
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
        DEFINITION["brief_intro"],
    ]
    for label, sample in (("A", a), ("B", b)):
        data = sample["inputs"]
        lines += [
            "",
            f"Page {label}:",
            f"<request>\n{data['request']}\n</request>",
            *[
                f"<user-message>\n{message}\n</user-message>"
                for message in data["messages"]
            ],
            f"Recorded version: {data['phase']}",
            f"Observation record: {sample['packet'] / 'observations.json'}",
        ]
        for width, paths in sample["captures"].items():
            lines += [f"  On {width}:", *[f"    {path}" for path in paths]]
    return "\n".join(lines)


def judge(subject: str, a: dict, b: dict, evidence: Path) -> dict | None:
    """One judgment of A against B, or None when the judge gives no verdict."""
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "evals/workflows/eval_pairs.yaml", evidence / "rubric.yaml")
    write_json(evidence / "schema.json", VERDICT)
    write_json(
        evidence / "provenance.json",
        {
            "judgment": "model",
            "judge_model": MODELS["claude-code"],
            "evaluator": files_identity(
                [
                    Path(__file__),
                    ROOT / "evals/workflows/eval_pairs.yaml",
                    ROOT / "dev/leaf_dev/arms.py",
                    ROOT / "dev/leaf_dev/eval_judge.py",
                    ROOT / "dev/leaf_dev/authoring_score.py",
                    ROOT / "dev/leaf_dev/eval_provenance.py",
                    ROOT / "pnpm-lock.yaml",
                    ROOT / "uv.lock",
                ],
                ROOT,
            ),
        },
    )
    prepared = []
    for label, sample in (("A", a), ("B", b)):
        inputs = sample_inputs(sample["metadata"], sample["run"], sample.get("phase"))
        packet = stage_packet(evidence / f"page-{label}", **inputs)
        public = json.loads((packet / "packet.json").read_text())
        captures = {
            width: [
                str(packet / image["file"])
                for image in public["images"]
                if image["width"] == width
            ]
            for width in inputs["captures"]
        }
        if any(not paths for paths in captures.values()) or not captures:
            write_json(
                evidence / "integrity.json",
                {
                    "status": "unscored",
                    "error": f"Page {label} lacks recorded captures",
                },
            )
            return None
        prepared.append(
            {**sample, "inputs": inputs, "packet": packet, "captures": captures}
        )
    a, b = prepared
    (evidence / "brief.md").write_text(brief(subject, a, b))
    (evidence / "prompt.txt").write_text(
        JUDGE.format(brief=evidence / "brief.md", reachable=REACHABLE)
    )
    try:
        with tempfile.TemporaryDirectory(prefix="leaf-pairs-") as directory:
            cwd = Path(directory) / "cwd"
            cwd.mkdir()
            trace = run_agent(
                cwd,
                (evidence / "prompt.txt").read_text(),
                "--tools",
                "Read",
                "--json-schema",
                json.dumps(VERDICT),
                out=evidence / "stream.jsonl",
                err=evidence / "err.txt",
                dirs=[evidence],
                model=MODELS["claude-code"],
            )
        required = [
            evidence / "brief.md",
            *[sample["packet"] / "observations.json" for sample in (a, b)],
            *[
                Path(path)
                for sample in (a, b)
                for paths in sample["captures"].values()
                for path in paths
            ],
        ]
        opened = validate_reads(trace, required)
        verdict = trace_result(trace).get("structured_output")
        write_json(evidence / "raw-verdict.json", verdict)
        jsonschema.validate(verdict, VERDICT)
        for sample in (a, b):
            read_packet(sample["packet"])
        write_json(
            evidence / "integrity.json",
            {"opened": sorted(opened), "status": "scored", "judgment": "model"},
        )
        return verdict
    except (
        ValueError,
        OSError,
        subprocess.SubprocessError,
        jsonschema.ValidationError,
    ) as error:
        write_json(
            evidence / "integrity.json", {"status": "unscored", "error": str(error)}
        )
        return None


def by_column(verdict: dict | None, columns: dict[str, str]) -> dict | None:
    """A verdict's winners named by column rather than position, or None where the
    judge gave no verdict."""
    if verdict is None:
        return None
    named = {**columns, "tie": "tie", "insufficient_evidence": "insufficient_evidence"}
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
@click.option(
    "--phase",
    type=click.IntRange(min=1),
    help="Compare this recorded version; default is each sample's last version.",
)
@click.option(
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    help="New directory for judgments; never replaces historical verdicts.",
)
def eval_pairs(runs: tuple[Path, ...], phase: int | None, output: Path | None):
    """Judge each authored task's samples across two columns of RUNS, pairwise.

    RUNS are run directories under `.tmp/eval/` whose authored tasks ran in two
    columns, such as `--condition both` or `--base`. The Nth sample of a task in
    one column pairs with the Nth in the other, so run them the same number of
    times. Each pair is judged with each column in each position."""
    if output is not None:
        if output.exists():
            raise click.ClickException(f"Output already exists: {output}")
        output.mkdir(parents=True)
    else:
        parent = runs[0] / "pairs"
        parent.mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
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
            x, y = ({**sample, "phase": phase} for sample in (x, y))
            selected = [
                sample_inputs(sample["metadata"], sample["run"], phase)["phase"]
                for sample in (x, y)
            ]
            if selected[0] != selected[1]:
                raise click.ClickException(
                    f"{subject} {n}: recorded versions differ ({selected}); select a matched --phase"
                )
            if (
                sample_inputs(x["metadata"], x["run"], phase)["request"]
                != sample_inputs(y["metadata"], y["run"], phase)["request"]
            ):
                raise click.ClickException(
                    f"{subject} {n}: recorded user requests differ; not a matched pair"
                )
            orders = []
            for order, (a, b, names) in enumerate(
                ((x, y, {"A": first, "B": second}), (y, x, {"A": second, "B": first})),
                1,
            ):
                evidence = output / f"{subject}-{n}-order-{order}"
                orders.append(by_column(judge(subject, a, b, evidence), names))
            winners = {
                o["overall"]
                for o in orders
                if o and o["overall"] != "insufficient_evidence"
            }
            pairs.append(
                {
                    "subject": subject,
                    "pair": n,
                    "samples": {first: x["sample"], second: y["sample"]},
                    "phase": selected[0],
                    "orders": orders,
                    "winner": winners.pop()
                    if len(winners) == 1
                    and all(orders)
                    and all(o["overall"] != "insufficient_evidence" for o in orders)
                    else None,
                }
            )
            click.echo(
                f"{subject} {n}: "
                + " / ".join(o["overall"] if o else "no verdict" for o in orders)
                + f" -> {pairs[-1]['winner'] or 'split'}"
            )
    write_json(output / "pairs.json", pairs)
    click.echo(f"verdicts: {output / 'pairs.json'}")
