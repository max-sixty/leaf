"""Short cases that author a real Leaf page with native tools.

Each call owns a scratch cwd, credential home, temp directory and Leaf state.
The arm's launcher initializes a writable page, so registry discovery and media
registration use the same boundary as a real authoring run. The agent may edit,
run commands and check rendering; this executor independently checks the final
page without repairing it. Existing assertions read the authored HTML, not a
claim in the reply. Page files, prompts and native traces survive in the sample's
evidence directory. Reading and instruction-only probes stay with native providers.
"""

import hashlib
import json
import shutil
import time
from pathlib import Path

from leaf.media import media_name

from leaf_dev import ROOT
from leaf_dev.arms import completed, run_agent, run_leaf, scratch, trace_summary
from leaf_dev.leaf_assets import pinned_copy


def capture_evidence(page: Path, inputs: Path | None, shots: Path) -> dict:
    """Give the visual judge original captures and actual page media, without traces."""
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
    return {"inputs": sources, "media": media, "exact_inputs": exact_inputs}


def execute(
    prompt: str,
    payload: Path,
    evidence: Path,
    metadata: dict,
    *,
    harness: str,
    shots: Path | None = None,
) -> dict:
    started = time.monotonic()
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
        request = (
            f"{prompt}\n\n"
            f"Author the page in {page}/index.html. The page is initialized and writable. "
            f"Your working directory is {cwd}; cited capture files are relative to it. "
            f"$LEAF is {payload}/bin/leaf. You can use native tools to read the registry, "
            "edit files, register or prepare media, and check the page."
        )
        (evidence / "prompt.txt").write_text(request)
        try:
            trace = run_agent(
                cwd,
                request,
                "--plugin-dir",
                str(payload),
                out=evidence / "stream.jsonl",
                err=evidence / "err.txt",
                dirs=[payload],
                env={"LEAF": str(payload / "bin/leaf"), "XDG_STATE_HOME": str(state)},
                harness=harness,
            )
            check = run_leaf(payload, state, "page", "check", str(page), "--render")
            (evidence / "check.txt").write_text(check.stdout + check.stderr)
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
                    "setup_seconds": setup_seconds,
                    "input_media": inputs,
                    **(
                        {"capture_evidence": capture_evidence(page, images, shots)}
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
