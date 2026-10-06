"""The local selector CLI: collect, prepare, then select inspectable node IDs."""

import json
import time
from pathlib import Path

import click

from leaf_dev.test_select.inputs import (
    POLICY,
    collect,
    commit,
    digest,
    prepare,
    validate_manifest,
    write_json,
)
from leaf_dev.test_select.model import Classification, Client, api_key
from leaf_dev.test_select.planning import encode, plan
from leaf_dev.test_select.timing import cpu_time


def planned(inputs: dict) -> tuple[list[dict], str | None]:
    """One planning policy for offline inspection and paid selection."""
    if inputs["states"]["forced_all_tests"]:
        return [], "unknown-generated-provenance"
    if len(inputs["states"]["state_chunks"]) > 32:
        return [], "diff-exceeds-32-complete-portions"
    return plan(inputs), None


def preview(prepared: Path, output: Path) -> None:
    """Expose complete planned requests offline; selection owns paid execution."""
    inputs = json.loads(prepared.read_text())
    try:
        batches, reason = planned(inputs)
    except ValueError as error:
        batches, reason = [], str(error)
    for name in ("planned-first-request.json", "planned-single-query.json"):
        (output / name).unlink(missing_ok=True)
    if batches:
        first = batches[0]
        write_json(output / "planned-first-request.json", first)
        write_json(
            output / "planned-single-query.json",
            {**first, "questions": dict(list(first["questions"].items())[:1])},
        )
    write_json(
        output / "plan-summary.json",
        {
            "prepared_sha256": digest(prepared.read_bytes()),
            "requests": len(batches),
            "questions": sum(len(b["questions"]) for b in batches),
            "wire_bytes": sum(len(encode(b)) for b in batches),
            "full_suite_reason": reason,
            "api_requests_sent": 0,
        },
    )


def select(prepared: Path, output: Path) -> dict:
    """Select validated inputs; token refusals retain their tests, other failures retain all."""
    started, cpu = time.perf_counter(), cpu_time()
    inputs = json.loads(prepared.read_text())
    binding = json.loads(prepared.with_name("prepared-binding.json").read_text())
    if digest(prepared.read_bytes()) != binding["sha256"]:
        raise ValueError("Prepared input binding is stale; prepare the selection again")
    root = Path(inputs["root"])
    for ref in (inputs["base"], inputs["candidate"]):
        if commit(root, ref) != ref:
            raise ValueError("Prepared refs must name immutable commits")
    if inputs["policy"] != POLICY:
        raise ValueError("Prepared selection policy differs from this command")
    manifest = Path(inputs["manifest_file"])
    source_binding = Path(inputs["manifest_binding_file"])
    tests = validate_manifest(root, inputs["candidate"], manifest, source_binding)
    if (
        digest(manifest.read_bytes()) != inputs["manifest_sha256"]
        or digest(source_binding.read_bytes()) != inputs["binding_sha256"]
    ):
        raise ValueError("Prepared collection binding has changed")
    if (
        len(inputs["cards"]) != len(tests)
        or tests != inputs["manifest"]
        or {c["nodeid"] for c in inputs["cards"]} != {t["nodeid"] for t in tests}
    ):
        raise ValueError("Prepared cards differ from the collected inventory")
    mandatory = set(inputs["mandatory_test_ids"])
    if not mandatory <= {t["nodeid"] for t in tests}:
        raise ValueError("Mandatory selection contains uncollected identities")
    if any(
        c["provenance"]
        != {k: inputs[k] for k in ("base", "candidate", "manifest_sha256")}
        for c in inputs["cards"]
    ):
        raise ValueError("Prepared cards have stale source provenance")
    output.mkdir(parents=True, exist_ok=True)
    fallback, classified, client = None, Classification({}, {}), None
    try:
        batches, fallback = planned(inputs)
        if batches:
            first = batches[0]
            write_json(
                output / "single-query.json",
                {**first, "questions": dict(list(first["questions"].items())[:1])},
            )
            client = Client(api_key(), output)
            classified = client.run(batches)
    except (ValueError, KeyError, TypeError, OSError) as error:
        fallback = str(error) or type(error).__name__
    verdicts = []
    for index, card in enumerate(inputs["cards"]):
        nodeid = card["nodeid"]
        names = [f"s{s}q{index}" for s in range(len(inputs["states"]["state_chunks"]))]
        refusals = [
            {"question": name, **classified.context_refusals[name]}
            for name in names
            if name in classified.context_refusals
        ]
        raw = (
            []
            if nodeid in mandatory or fallback
            else [
                classified.answers[name]
                for name in names
                if name not in classified.context_refusals
            ]
        )
        relevance = (
            None
            if refusals
            else max(
                (1 - answer["probabilities"]["unrelated"] for answer in raw),
                default=None,
            )
        )
        verdicts.append(
            {
                "nodeid": nodeid,
                "nightly": card["nightly"],
                "mandatory": nodeid in mandatory,
                "relevance": relevance,
                "model_scored": bool(raw) and not refusals,
                "raw": raw,
                "context_refusals": refusals,
                "selected": bool(
                    fallback
                    or nodeid in mandatory
                    or refusals
                    or relevance is not None
                    and relevance >= POLICY["cutoff"]
                ),
            }
        )
    result = {
        "schema": "leaf-test-selection/v1",
        "base": inputs["base"],
        "candidate": inputs["candidate"],
        "prepared_sha256": digest(prepared.read_bytes()),
        "policy": POLICY,
        "fallback": fallback,
        "total": len(tests),
        "selected": sum(t["selected"] for t in verdicts),
        "nightly_selected": sum(t["selected"] and t["nightly"] for t in verdicts),
        "model_scored": sum(t["model_scored"] for t in verdicts),
        "preparation": inputs["preparation"],
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": cpu_time() - cpu,
        "spent": client.metrics() if client else None,
        "tests": verdicts,
    }
    write_json(output / "result.json", result)
    selected = [t["nodeid"] for t in verdicts if t["selected"]]
    (output / "nodeids.txt").write_text(
        "\n".join(selected) + ("\n" if selected else "")
    )
    return result


@click.group("test-select")
def test_select() -> None:
    """Research test selection with source processing and Jev.

    Collect the complete pytest inventory, prepare immutable source inputs, then
    select tests. Output contains code-bearing prompts, probabilities, request
    costs and nodeids.txt. Token refusals retain their tests; other external
    uncertainty has an explicit full-suite fallback. This
    local experiment does not change CI's gates.
    """


@test_select.command("collect")
@click.argument("root", type=click.Path(exists=True, path_type=Path))
@click.argument("output", type=click.Path(path_type=Path))
def collect_command(root: Path, output: Path) -> None:
    """Collect all tests and bind metadata to the clean checkout HEAD."""
    try:
        click.echo(str(collect(root, output)))
    except (ValueError, KeyError) as error:
        raise click.ClickException(str(error)) from error


@test_select.command("prepare")
@click.argument("root", type=click.Path(exists=True, path_type=Path))
@click.argument("base")
@click.argument("candidate")
@click.argument("manifest", type=click.Path(exists=True, path_type=Path))
@click.argument("output", type=click.Path(path_type=Path))
@click.option(
    "--binding",
    type=click.Path(exists=True, path_type=Path),
    help="Defaults to manifest-binding.json beside MANIFEST.",
)
@click.option(
    "--regeneration-proof",
    type=click.Path(exists=True, path_type=Path),
    help="Immutable-ref rebuild evidence; generated output remains literal without verified source/output hashes.",
)
def prepare_command(
    root: Path,
    base: str,
    candidate: str,
    manifest: Path,
    output: Path,
    binding: Path | None,
    regeneration_proof: Path | None,
) -> None:
    """Prepare source and an offline complete planned query.

    OUTPUT contains prepared.json, planned-single-query.json (one complete
    question with its diff), planned-first-request.json (the entire first batch)
    and plan-summary.json. No API request or credential read occurs. If input
    limits require the full suite, the summary records that reason instead.
    """
    try:
        prepared = prepare(
            root,
            base,
            candidate,
            manifest,
            binding or manifest.with_name("manifest-binding.json"),
            output,
            regeneration_proof=regeneration_proof,
        )
        preview(prepared, output)
        click.echo(str(prepared))
    except (ValueError, KeyError) as error:
        raise click.ClickException(str(error)) from error


@test_select.command("select")
@click.argument("prepared", type=click.Path(exists=True, path_type=Path))
@click.argument("output", type=click.Path(path_type=Path))
def select_command(prepared: Path, output: Path) -> None:
    """Ask Jev and write nodeids.txt, result.json and credential-free requests."""
    try:
        result = select(prepared, output)
    except (ValueError, KeyError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps({k: v for k, v in result.items() if k != "tests"}, indent=2))
