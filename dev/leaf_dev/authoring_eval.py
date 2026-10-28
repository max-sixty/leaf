"""Short cases that author a real Leaf page with native tools.

Each call owns a scratch cwd, credential home, temp directory and Leaf state.
The arm's launcher initializes a writable page, so registry discovery and media
registration use the same boundary as a real authoring run. The agent may edit,
run commands and check rendering; this executor independently checks the final
page, plain and with `--render`, without repairing it. Existing assertions read
the authored HTML, not a claim in the reply. Page files, prompts, native traces
and both checks' output survive in the sample's evidence directory. The final
render check's screenshots survive alongside the sample. Report captures use the
selected eval viewports, which also reach the author in its request. `check_log`
lists the author's tool calls in order with the output of each page check it ran,
so a grader can tell what the checks told the author and what it did next. Reading
and instruction-only probes stay with native providers.
The shared authoring prompt lives in `evals/workflows/authoring_eval.yaml`.
"""

import hashlib
import json
import shutil
import time
from pathlib import Path

from leaf.media import media_name
from leaf_dev import ROOT
from leaf_dev.arms import (
    blocks,
    completed,
    environment,
    instruction_context,
    run_agent,
    run_leaf,
    scratch,
    trace_summary,
)
from leaf_dev.arrangement_eval import Run, capture_phase, preference
from leaf_dev.eval_cases import DEFAULT_VIEWPORTS, definition
from leaf_dev.leaf_assets import pinned_copy


def capture_evidence(
    page: Path, inputs: Path | None, screens: Path, shots: Path
) -> dict:
    """Keep the judge's captures, page media and rendered screens after scratch exits."""
    sources, media = {}, {}
    shots.mkdir(parents=True, exist_ok=True)
    if inputs is not None and inputs.is_dir():
        shutil.copytree(inputs, shots / "inputs")
        sources = {
            str(path.relative_to(inputs)): str(
                shots / "inputs" / path.relative_to(inputs)
            )
            for path in inputs.rglob("*")
            if path.is_file()
        }
    if (page / "media").is_dir():
        shutil.copytree(page / "media", shots / "media")
        media = {
            f"/media/{path.name}": str(shots / "media" / path.name)
            for path in (page / "media").iterdir()
            if path.is_file()
        }
    source_hashes = {
        name: hashlib.sha256(Path(path).read_bytes()).digest()
        for name, path in sources.items()
    }
    exact_inputs = {}
    for url, path in media.items():
        digest = hashlib.sha256(Path(path).read_bytes()).digest()
        exact_inputs[url] = [
            name
            for name, source_digest in source_hashes.items()
            if source_digest == digest
        ]
    rendered = []
    if screens.is_dir():
        shutil.copytree(screens, shots / "screens")
        rendered = [str(path) for path in sorted((shots / "screens").rglob("*.png"))]
    return {
        "inputs": sources,
        "media": media,
        "exact_inputs": exact_inputs,
        "screens": rendered,
    }


def leaf_command(call: dict) -> str:
    """The command line a tool call ran: a shell's `command`, or the arguments of
    Codex's `leaf` MCP tool, which runs a Leaf command without a shell."""
    return str(call.get("command") or " ".join(map(str, call.get("args", []))))


def check_log(trace: list[dict]) -> list[dict]:
    """Each tool call the author made, in order and whole, with the whole output of
    its page checks, so a reader can tell what a check reported and whether a later
    call changed the page in answer. A call is its tool's name and input as the
    harness recorded them: a shell command, an Edit's strings, a Write's text or a
    Codex patch's `changes`."""
    results = {
        block["tool_use_id"]: block.get("content")
        for block in blocks(trace)
        if block.get("type") == "tool_result"
    }
    log = []
    for block in blocks(trace):
        if block.get("type") != "tool_use":
            continue
        entry = {"tool": block["name"], "input": block["input"]}
        if "page check" in leaf_command(block["input"]):
            output = results.get(block["id"])
            if isinstance(output, list):
                output = "\n".join(part.get("text", "") for part in output)
            entry["output"] = output or ""
        log.append(entry)
    return log


def execute(
    prompt: str,
    payload: Path,
    evidence: Path,
    metadata: dict,
    *,
    harness: str,
    shots: Path | None = None,
    viewports: tuple[str, ...] = DEFAULT_VIEWPORTS,
) -> dict:
    started = time.monotonic()
    context = (
        instruction_context(payload, metadata["instructions"])
        if metadata.get("instructions")
        else None
    )
    instructions = ("--append-system-prompt", context) if context is not None else ()
    if context is not None:
        (evidence / "instructions.txt").write_text(context)
    with scratch(payload) as cwd:
        page, state = cwd / "page", cwd / "state"
        task = metadata["case"].split("/", 1)[0]
        images = pinned_copy(ROOT / "evals" / task)
        inputs = {}
        if images is not None and images.is_dir():
            destination = cwd / "evals" / task
            shutil.copytree(images, destination)
            inputs = {
                str(
                    path.relative_to(cwd)
                ): f"/media/{media_name(path.read_bytes(), path.suffix)}"
                for path in destination.rglob("*")
                if path.is_file()
            }
        run_leaf(payload, state, "page", "init", str(page), check=True)
        setup_seconds = time.monotonic() - started
        brief = f"{prompt}\n\n{preference(viewports)}"
        request = definition("authoring_eval")["prompt"].format(
            prompt=brief, page=page, cwd=cwd, payload=payload
        )
        (evidence / "prompt-1.txt").write_text(request)
        try:
            trace = run_agent(
                cwd,
                request,
                *instructions,
                "--plugin-dir",
                str(payload),
                out=evidence / "stream.jsonl",
                err=evidence / "err.txt",
                dirs=[payload],
                env={
                    "PATH": environment(payload=payload)["PATH"],
                    "XDG_STATE_HOME": str(state),
                },
                harness=harness,
            )
            plain = run_leaf(payload, state, "page", "check", str(page))
            (evidence / "check-plain.txt").write_text(plain.stdout + plain.stderr)
            check = run_leaf(payload, state, "page", "check", str(page), "--render")
            (evidence / "check.txt").write_text(check.stdout + check.stderr)
            run = Run(
                metadata["case"],
                payload,
                evidence,
                shots or evidence / "screens",
                harness=harness,
                viewports=viewports,
            )
            captures = capture_phase(run, 1, page) if plain.returncode == 0 else {}
            document = page / "index.html"
            output = document.read_text() if document.is_file() else ""
            summary = trace_summary(trace)
            response = {
                "output": output,
                "metadata": {
                    "checks": {
                        "completed": completed(trace),
                        "page-valid": check.returncode == 0,
                    },
                    "trace": summary,
                    "diagnostics": {
                        "subject": metadata["case"],
                        "harness": harness,
                        "condition": "leaf",
                        "payload": str(payload),
                        "comparison": {
                            "brief": brief,
                            "decision_task": None,
                            "phases": {"": "1"},
                            "author_phases": [1],
                            "widths": {
                                name: list(viewport)
                                for name, (viewport, _) in run.widths.items()
                            },
                        },
                        "phases": {
                            "1": {
                                "page": str(evidence / "page"),
                                "trace": summary,
                                "captures": captures,
                            }
                        },
                    },
                    "check_output": {
                        "plain": plain.stdout + plain.stderr,
                        "render": check.stdout + check.stderr,
                    },
                    "check_log": check_log(trace),
                    "payload": str(payload),
                    "setup_seconds": setup_seconds,
                    "input_media": inputs,
                    **(
                        {
                            "capture_evidence": capture_evidence(
                                page, images, state / "leaf" / "screens", shots
                            )
                        }
                        if shots is not None
                        else {}
                    ),
                },
                "tokenUsage": {
                    "prompt": summary["input_tokens"],
                    "completion": summary["output_tokens"],
                },
            }
        finally:
            stopped = run_leaf(payload, state, "server", "stop", str(page))
            (evidence / "stop.txt").write_text(stopped.stdout + stopped.stderr)
            if page.is_dir():
                shutil.copytree(page, evidence / "page")
    (evidence / "result.json").write_text(json.dumps(response, indent=2))
    return response
