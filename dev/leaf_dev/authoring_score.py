"""Grade fixed authoring evidence without treating missing observation as a defect.

``stage_packet`` copies a request, its messages through one version, browser
observations and screenshots into an immutable, hash-checked packet. ``evaluate``
uses that packet's frozen rubric and schema with the pinned text judge, retaining
its prompt, native trace and structured answer. It never serves, revises or vendors
the page. Live workflows and ``eval-score`` replay use these same two operations.

Criterion conclusions are model judgments; hashes, input identities and successful
image reads are computed evidence. A supported defect survives unrelated gaps.
Invalid output or failed judge execution is unscored, rather than a page defect.
Packets keep authoring, runtime and evaluator identities separately; missing
historical provenance stays unknown. Replay reads recorded phase keys and prompts,
never current scenario definitions or requests.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import click
import jsonschema
import yaml
from leaf.event_log import read_events
from leaf.service import requires_agent_attention

from leaf_dev import ROOT
from leaf_dev.arms import MODELS, read_trace, run_agent, trace_result
from leaf_dev.eval_judge import validate_reads

RUBRIC = ROOT / "evals/workflows/authoring_score.yaml"
STATUSES = ("pass", "defect", "observation_gap", "not_applicable")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def evaluator_identity() -> dict:
    """The exact scorer sources plus Git context, including uncommitted changes."""
    return {
        "commit": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "files": {
            str(path.relative_to(ROOT)): digest(path)
            for path in (
                Path(__file__),
                RUBRIC,
                ROOT / "dev/leaf_dev/arms.py",
                ROOT / "dev/leaf_dev/eval_judge.py",
            )
        },
        "model": MODELS["judge"],
    }


def grade_schema(criteria: dict, always_applicable: list[str]) -> dict:
    result = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": list(STATUSES)},
            "explanation": {"type": "string", "minLength": 1},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            },
        },
        "required": ["status", "explanation", "evidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            name: {
                **result,
                "properties": {
                    **result["properties"],
                    "status": {
                        "type": "string",
                        "enum": [
                            status
                            for status in STATUSES
                            if name not in always_applicable
                            or status != "not_applicable"
                        ],
                    },
                },
            }
            for name in criteria
        },
        "required": list(criteria),
        "additionalProperties": False,
    }


def evidence_ids(images: list[dict], observations: dict | None) -> list[str]:
    """The public evidence registry, derived only from supplied image/state records."""
    identities = [
        "request",
        "messages",
        "observations",
        *(image["id"] for image in images),
        *(
            state["id"]
            for width in (observations or {}).get("widths", {}).values()
            for state in width["states"]
        ),
    ]
    if any(not isinstance(identity, str) or not identity for identity in identities):
        raise ValueError("Public evidence IDs must be nonempty strings")
    if len(set(identities)) != len(identities):
        raise ValueError("Public evidence IDs must be unique")
    return identities


def validate_grade(
    grade: dict, inputs: dict, observations: dict | None, schema: dict
) -> dict:
    """Validate a saved judgment without model inference or changing its conclusions.

    This also supports audited revalidation after a mechanical validator repair:
    callers keep the original packet, raw answer and failed validation, and write
    the new validation result separately. References are checked against actual
    supplied image and state records, not a judge's claims or a cached ID list.
    Native execution and successful input reads are a separate integrity check.
    """
    jsonschema.validate(grade, schema)
    image_ids = {image["id"] for image in inputs["images"]}
    available = set(evidence_ids(inputs["images"], observations))
    artifact_ids = set(image_ids)
    visual_ids = set(image_ids)
    for width in (observations or {}).get("widths", {}).values():
        for state in width["states"]:
            linked_images = image_ids.intersection(state.get("images", []))
            if linked_images:
                visual_ids.add(state["id"])
            reading = state.get("reading")
            if linked_images or (isinstance(reading, dict) and reading):
                artifact_ids.add(state["id"])
    if artifact_ids - image_ids:
        artifact_ids.add("observations")
    for name, criterion in grade.items():
        cited = set(criterion["evidence"])
        unknown = cited - available
        if unknown:
            raise ValueError(f"{name}: unknown evidence IDs {sorted(unknown)}")
        if criterion["status"] in ("pass", "defect"):
            if name == "legibility" and not cited.intersection(visual_ids):
                raise ValueError(
                    "legibility: a scored conclusion requires a supplied image "
                    "or actual state linked to one"
                )
            if not cited.intersection(artifact_ids):
                raise ValueError(
                    f"{name}: a scored conclusion requires supplied artifact evidence"
                )
    return grade


def validate_execution(trace: list[dict], inputs: dict, packet: Path) -> dict:
    """Check completed native execution and public reads, also for audited replay."""
    required = ("packet.json", "rubric.yaml", "observations.json")
    validate_reads(
        trace,
        [
            packet / name
            for name in (*required, *(image["file"] for image in inputs["images"]))
        ],
    )
    return {
        "opened_images": [image["id"] for image in inputs["images"]],
        "opened_inputs": list(required),
    }


def stage_packet(
    output: Path,
    *,
    request: str,
    messages: list[str],
    captures: dict[str, list[str]],
    observations: dict | None = None,
    provenance: dict | None = None,
    phase: int | None = None,
) -> Path:
    """Copy one version's evidence; ``output`` must not already exist.

    ``packet.json`` declares image IDs and their widths, original sequence and
    hashes. ``observations`` is the capture owner's structured reading; paths
    matching copied images become their IDs. Missing images and absent observations
    are retained as explicit coverage limits, not silently omitted or regenerated.
    ``provenance`` may name authoring/runtime revisions and artifact hashes; unknown
    identities remain null. The evaluator revision is always computed here.
    """
    output = output.resolve()
    output.mkdir(parents=True)
    images = []
    replacements = {}
    limitations = []
    for width, paths in captures.items():
        if not paths:
            limitations.append(f"No screenshots recorded for {width}.")
        for sequence, source in enumerate(paths):
            path = Path(source)
            if not path.is_file():
                limitations.append(f"Recorded screenshot missing: {width}[{sequence}].")
                continue
            identity = f"image-{len(images) + 1:03}"
            target = output / f"{identity}{path.suffix.lower()}"
            shutil.copyfile(path, target)
            replacements[str(path)] = identity
            images.append(
                {
                    "id": identity,
                    "file": target.name,
                    "width": width,
                    "sequence": sequence,
                    "sha256": digest(target),
                }
            )
    if observations is None or not observations.get("widths"):
        limitations.append(
            "No browser observation record. Screenshots show only captured states; "
            "disclosures, selections and internal scroll remainders may be unobserved."
        )

    def normalize(value):
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        return value

    observations = normalize(observations)
    write_json(output / "observations.json", observations)
    shutil.copyfile(RUBRIC, output / "rubric.yaml")
    shutil.copyfile(Path(__file__), output / "evaluator.py")
    shutil.copyfile(ROOT / "dev/leaf_dev/eval_judge.py", output / "eval_judge.py")
    rubric = yaml.safe_load((output / "rubric.yaml").read_text())
    write_json(
        output / "schema.json",
        grade_schema(rubric["criteria"], rubric["always_applicable"]),
    )
    identity = {"authoring": None, "runtime": None, **(provenance or {})}
    identity["evaluator"] = evaluator_identity()
    write_json(output / "provenance.json", identity)
    write_json(
        output / "judge.json", {"harness": "claude-code", "model": MODELS["judge"]}
    )
    packet = {
        "version": 1,
        "phase": phase,
        "request": request,
        "messages": messages,
        "images": images,
        "evidence_ids": evidence_ids(images, observations),
        "observations": "observations.json",
        "limitations": limitations,
    }
    write_json(output / "packet.json", packet)
    write_json(
        output / "hashes.json",
        {
            path.name: digest(path)
            for path in sorted(output.iterdir())
            if path.is_file()
        },
    )
    return output


def read_packet(packet: Path) -> dict:
    """Verify frozen bytes before reading task or judge settings."""
    for name, expected in json.loads((packet / "hashes.json").read_text()).items():
        path = packet / name
        if Path(name).name != name or not path.is_file() or digest(path) != expected:
            raise ValueError(f"Frozen authoring evidence changed: {name}")
    return {
        **json.loads((packet / "packet.json").read_text()),
        "provenance": json.loads((packet / "provenance.json").read_text()),
        "judge": json.loads((packet / "judge.json").read_text()),
    }


def summarize(criteria: dict) -> str:
    """A proven defect remains a defect when a different criterion is unobserved."""
    statuses = {value["status"] for value in criteria.values()}
    if "defect" in statuses:
        return "defect"
    if "observation_gap" in statuses:
        return "observation_gap"
    return "pass"


def evaluate(packet: Path) -> dict:
    """Judge a staged packet once, retaining exact inputs and native evidence.

    Evidence citations use ``request``, ``messages``, ``observations`` or image
    IDs. Defects and passes must cite supplied evidence. All images must have a
    successful Read result in the completed judge trace; a skipped or refused
    image invalidates the grade. This does not prove the model understood it.
    """
    judged = packet / "judgment"
    judged.mkdir()
    result = {"scored": False, "status": "unscored", "packet": str(packet)}
    try:
        inputs = read_packet(packet)
        frozen_evaluator = inputs["provenance"]["evaluator"]
        current_evaluator = evaluator_identity()
        # Git context may move for a documentation-only commit. Actual scorer
        # bytes and model, rather than that context, define this evaluation.
        if any(
            frozen_evaluator[key] != current_evaluator[key]
            for key in ("files", "model")
        ):
            raise ValueError(
                "Evaluator changed after packet freeze; stage a new packet from the same artifacts"
            )
        rubric = yaml.safe_load((packet / "rubric.yaml").read_text())
        schema = json.loads((packet / "schema.json").read_text())
        prompt = rubric["prompt"].format(packet=packet)
        (judged / "prompt.txt").write_text(prompt)
        with tempfile.TemporaryDirectory(prefix="leaf-authoring-judge-") as directory:
            cwd = Path(directory) / "cwd"
            cwd.mkdir()
            trace = run_agent(
                cwd,
                prompt,
                "--tools",
                "Read",
                "--json-schema",
                json.dumps(schema),
                out=judged / "stream.jsonl",
                err=judged / "err.txt",
                dirs=[packet],
                model=inputs["judge"]["model"],
            )
        result |= validate_execution(trace, inputs, packet)
        grade = trace_result(trace).get("structured_output")
        write_json(judged / "raw-grade.json", grade)
        validate_grade(
            grade,
            inputs,
            json.loads((packet / "observations.json").read_text()),
            schema,
        )
        result |= {
            "scored": True,
            "status": summarize(grade),
            "criteria": grade,
            "provenance": inputs["provenance"],
            "judgment": "model",
            "named_scores": {
                name: int(criterion["status"] == "pass")
                for name, criterion in grade.items()
                if criterion["status"] in ("pass", "defect")
            },
        }
    except (
        ValueError,
        OSError,
        subprocess.SubprocessError,
        jsonschema.ValidationError,
    ) as error:
        result["error"] = str(error)
    write_json(judged / "grade.json", result)
    return result


def recorded_messages(work: Path, phase: int) -> tuple[list[str], list[str]]:
    """Only saved prompts/messages through the chosen phase; never reconstruct one."""
    by_phase = {}
    trace = work / "stream.jsonl"
    if trace.is_file():
        current = None
        for record in read_trace(trace):
            if record.get("type") == "eval_phase":
                current = int(record["phase"])
            elif (
                record.get("type") == "eval_send"
                and current is not None
                and 1 < current <= phase
                and record.get("text")
            ):
                by_phase.setdefault(current, []).append(record["text"])
    for number in range(2, phase + 1):
        path = work / f"prompt-{number}.txt"
        if number not in by_phase and path.is_file():
            by_phase[number] = [path.read_text()]
    # A Leaf comment arrives through its page, so the chat prompt may carry only
    # 'handle the comment'. Recover the admitted words, not that scaffold.
    comment = work / "comment.json"
    comment_log = work / "page-phase3/events.jsonl"
    if phase >= 3 and (comment.is_file() or comment_log.is_file()):
        event_id = (
            json.loads(comment.read_text()).get("event") if comment.is_file() else None
        )
        earlier = {event["id"] for event in read_events(work / "page-phase2")}
        found = [
            event["text"]
            for event in read_events(work / "page-phase3")
            if (
                event.get("id") == event_id
                if event_id
                else event.get("id") not in earlier
            )
            and event.get("author") == "user"
            and event.get("kind") == "comment"
            and isinstance(event.get("text"), str)
            and event["text"].strip()
        ]
        if found:
            by_phase.setdefault(3, []).extend(found)
        else:
            by_phase.pop(3, None)
    # Page-route apply messages name no chosen values. The driver retained the
    # admitted user gestures and actual clipboard output in its decision record.
    decision = work / "decision.json"
    additional_limits = []
    if phase >= 4 and decision.is_file():
        record = json.loads(decision.read_text())
        if record.get("route") == "page":
            gestures = record.get("gestures")
            if isinstance(gestures, list) and gestures:
                by_phase.setdefault(4, []).append(
                    "User decision gestures admitted by the page:\n"
                    + json.dumps(gestures, ensure_ascii=False)
                )
            else:
                by_phase.pop(4, None)
    elif phase >= 4:
        earlier = {event["id"] for event in read_events(work / "page-phase3")}
        gestures = [
            event
            for event in read_events(work / "page-phase4")
            if event.get("author") == "user"
            and event.get("id") not in earlier
            and requires_agent_attention(event)
        ]
        if gestures:
            by_phase.setdefault(4, []).append(
                "Admitted user records added before this version:\n"
                + json.dumps(gestures, ensure_ascii=False)
            )
        else:
            additional_limits.append(
                "No page decision record was preserved for phase 4. Saved chat is "
                "available, but any choices it refers to without naming remain unknown."
            )
    messages = [text for number in sorted(by_phase) for text in by_phase[number]]
    missing = sorted(set(range(2, phase + 1)) - by_phase.keys())
    limits = (
        [
            f"User input for phase(s) {missing} was not preserved; revision requirements are unknown."
        ]
        if missing
        else []
    )
    return messages, [*limits, *additional_limits]


def sample_inputs(metadata: dict, run: Path, phase: int | None = None) -> dict:
    """Read one recorded version's exact inputs for grading and comparison.

    ``metadata`` is the provider response's metadata, including ``work`` and
    ``diagnostics.phases``. ``authoring_inputs`` or the saved
    ``work/authoring-inputs.json`` has ``request`` and ``phases[N].messages``:
    the complete applicable user messages through that phase. Older samples fall
    back only to recorded prompts and user records. ``run`` locates that sample's
    screenshot observation JSON. No current case definition enters this path.
    """
    work = Path(metadata["work"])
    phases = metadata["diagnostics"]["phases"]
    selected = phase or max(map(int, phases))
    recorded = phases.get(str(selected), phases.get(selected))
    if recorded is None:
        raise ValueError(f"Sample has no recorded phase {selected}: {work}")
    saved_inputs = work / "authoring-inputs.json"
    authored_inputs = metadata.get("authoring_inputs")
    if authored_inputs is None and saved_inputs.is_file():
        authored_inputs = json.loads(saved_inputs.read_text())
    prompt = work / "prompt-1.txt"
    if authored_inputs is not None:
        request = authored_inputs["request"]
        input_phase = authored_inputs["phases"].get(str(selected))
        messages = input_phase["messages"] if input_phase is not None else []
        limits = (
            [
                f"User input for phase {selected} was not preserved; requirements are unknown."
            ]
            if input_phase is None
            else []
        )
    else:
        request = prompt.read_text().split("The user's request follows.\n\n", 1)[-1]
        messages, limits = recorded_messages(work, selected)
    observation_path = run / "screenshots" / work.name / f"p{selected}-observation.json"
    observations = (
        json.loads(observation_path.read_text()) if observation_path.is_file() else None
    )
    if limits:
        observations = {**(observations or {}), "input_limitations": limits}
    provenance = {
        **(metadata.get("provenance") or {}),
        "runtime": recorded.get(
            "runtime", (metadata.get("provenance") or {}).get("runtime")
        ),
        "authored_artifact": recorded.get("artifact"),
        "source_sample": str(work),
        "source_inputs_sha256": {
            str(path.relative_to(work)): digest(path)
            for path in (
                *sorted(work.glob("prompt-*.txt")),
                saved_inputs,
                work / "stream.jsonl",
                work / "comment.json",
                work / "decision.json",
                work / "page-phase3/events.jsonl",
            )
            if path.is_file()
        },
    }
    if prompt.is_file():
        provenance["source_prompt_text"] = prompt.read_text()
    if (run / "results.json").is_file():
        provenance["source_results_sha256"] = digest(run / "results.json")
    return {
        "request": request,
        "messages": messages,
        "captures": recorded.get("captures") or {},
        "observations": observations,
        "provenance": provenance,
        "phase": selected,
    }


def score_sample(
    metadata: dict, run: Path, output: Path, phase: int | None = None
) -> dict:
    """Grade one recorded version through the same path as the live assertion."""
    inputs = sample_inputs(metadata, run, phase)
    packet = stage_packet(output, **inputs)
    return {
        "sample": Path(metadata["work"]).name,
        "phase": inputs["phase"],
        **evaluate(packet),
    }


@click.command("eval-score")
@click.argument(
    "runs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="New directory for frozen packets and judgments.",
)
@click.option(
    "--phase",
    type=click.IntRange(min=1),
    help="Recorded phase to grade; default is each sample's last phase.",
)
def eval_score(runs: tuple[Path, ...], output: Path, phase: int | None):
    """Grade fixed samples from RUNS without reauthoring or recapturing them."""
    if output.exists():
        raise click.ClickException(f"Output already exists: {output}")
    output.mkdir(parents=True)
    grades = []
    seen = set()
    for run in runs:
        results = json.loads((run / "results.json").read_text())["results"]["results"]
        for row in results:
            metadata = (row.get("response") or {}).get("metadata") or {}
            diagnostics = metadata.get("diagnostics") or {}
            phases = diagnostics.get("phases") or {}
            if not phases or not metadata.get("work"):
                continue
            work = Path(metadata["work"])
            if work.resolve() in seen:
                raise click.ClickException(f"Sample supplied more than once: {work}")
            seen.add(work.resolve())
            if phase is not None and str(phase) not in phases and phase not in phases:
                continue
            grade = score_sample(
                metadata,
                run,
                output / f"sample-{len(grades) + 1:03}",
                phase=phase,
            )
            grades.append(grade)
            click.echo(f"{work.name} phase {grade['phase']}: {grade['status']}")
    write_json(output / "scores.json", grades)
    if not grades:
        raise click.ClickException("No samples contain the requested recorded phase.")
    click.echo(f"grades: {output / 'scores.json'}")
