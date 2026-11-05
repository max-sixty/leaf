"""Short cases that author a real Leaf page with native tools.

Each call owns a scratch cwd, credential home, temp directory and Leaf state.
The arm's launcher initializes a writable page, so registry discovery and media
registration use the same boundary as a real authoring run. The agent may edit,
run commands and check rendering; this executor independently checks the final
page, plain and with `--render`, without repairing it. Existing assertions read
the authored HTML, not a claim in the reply. Authors' render checks follow the
viewed window as in normal use; evaluator-owned checks keep the fixed viewport.
Page files, prompts, native traces
and both checks' output survive in the sample's evidence directory. The final
render check's screenshots survive alongside the sample. Report captures use the
selected eval viewports, which also reach the author in its request. `check_log`
lists the author's tool calls in order with the output of each page check it ran,
so a grader can tell what the checks told the author and what it did next. Reading
and instruction-only probes stay with native providers.
The plain HTML control gets the same request with no Leaf in reach, writes
`index.html` itself, and is captured and judged from a static server.
The shared authoring prompt lives in `evals/workflows/authoring_eval.yaml`.
"""

import hashlib
import json
import shutil
import time
from pathlib import Path

from leaf.media import media_name
from leaf.render_gate import command as render_command_model
from leaf_dev import ROOT
from leaf_dev.arms import (
    author_failure,
    blocks,
    completed,
    environment,
    instruction_context,
    run_agent,
    run_leaf,
    scratch,
    trace_summary,
)
from leaf_dev.arrangement_eval import Run, capture_phase, is_leaf, preference
from leaf_dev.browser import shell_executable
from leaf_dev.eval_cases import DEFAULT_VIEWPORTS, definition
from leaf_dev.leaf_assets import pinned_copy


def capture_evidence(
    page: Path,
    inputs: Path | None,
    screens: Path | None,
    shots: Path,
    arrival: list[str],
) -> dict:
    """Keep the judge's captures, page media and rendered screens after scratch exits.

    The rendered screens are `arrival`, the page on arrival at each selected
    viewport, which every condition has, then the render check's sweep in `screens`
    where the caller passes one."""
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
    rendered = list(arrival)
    if screens is not None and screens.is_dir():
        shutil.copytree(screens, shots / "screens")
        rendered += [str(path) for path in sorted((shots / "screens").rglob("*.png"))]
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
    condition: str = "leaf",
    shots: Path | None = None,
    viewports: tuple[str, ...] = DEFAULT_VIEWPORTS,
) -> dict:
    started = time.monotonic()
    # Leaf authors with the arm's plugin; the plain HTML control authors ordinary
    # files with no Leaf in reach.
    leaf = is_leaf(condition)
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
        if leaf:
            run_leaf(payload, state, "page", "init", str(page), check=True)
        else:
            page.mkdir()
        setup_seconds = time.monotonic() - started
        brief = f"{prompt}\n\n{preference(viewports)}"
        request = definition("authoring_eval")["prompt"].format(
            prompt=brief, page=page, cwd=cwd, payload=payload
        )
        if condition == "html":
            request += (
                "\n\nBuild it with HTML, CSS and JavaScript. Use headless browser "
                "tooling for your own inspection. Installed headless Chrome "
                f"executable: {shell_executable()}"
            )
        (evidence / "prompt-1.txt").write_text(request)

        try:
            author_started = time.monotonic()
            trace = run_agent(
                cwd,
                request,
                *instructions,
                *(("--plugin-dir", str(payload)) if leaf else ()),
                out=evidence / "stream.jsonl",
                err=evidence / "err.txt",
                dirs=[payload] if leaf else [],
                env={
                    "PATH": environment(payload=payload if leaf else None)["PATH"],
                    "XDG_STATE_HOME": str(state),
                    render_command_model.PIN_VARIABLE: "",
                },
                harness=harness,
            )
            author_seconds = time.monotonic() - author_started
            run = Run(
                metadata["case"],
                payload,
                evidence,
                shots or evidence / "screens",
                harness=harness,
                condition=condition,
                viewports=viewports,
            )
            if leaf:
                plain = run_leaf(payload, state, "page", "check", str(page))
                check = run_leaf(payload, state, "page", "check", str(page), "--render")
                plain_output = plain.stdout + plain.stderr
                render_output = check.stdout + check.stderr
                page_valid = check.returncode == 0
                operable = plain.returncode == 0 and (page / "index.html").is_file()
            else:
                from leaf_dev.browser import headless_shell, tab
                from leaf_dev.plain_html import load, serving

                errors = []
                with (
                    serving(page) as url,
                    headless_shell() as browser,
                    tab(browser) as view,
                ):
                    view.on("pageerror", lambda error: errors.append(str(error)))
                    load(view, url)
                    rendered = view.locator("body > *").count() > 0
                plain_output = "Plain HTML has no source check\n"
                render_output = (
                    "\n".join(errors)
                    if errors
                    else "Browser loaded the rendered page\n"
                )
                page_valid = (page / "index.html").is_file() and rendered and not errors
                operable = page_valid
            captures = capture_phase(run, 1, page) if operable else {}
            (evidence / "check-plain.txt").write_text(plain_output)
            (evidence / "check.txt").write_text(render_output)

            document = page / "index.html"
            output = document.read_text() if document.is_file() else ""
            summary = trace_summary(trace)
            response = {
                "output": output,
                "metadata": {
                    "checks": {
                        "completed": completed(trace),
                        "page-valid": page_valid,
                    },
                    "trace": summary,
                    "diagnostics": {
                        "subject": metadata["case"],
                        "harness": harness,
                        "condition": condition,
                        "payload": str(payload),
                        "comparison": {
                            # The user's task, which pair judges hold equal across
                            # conditions, without Leaf's instruction to use its skill.
                            "brief": brief.removeprefix(
                                definition("eval")["skill_prefix"]
                            ),
                            "decision_task": None,
                            "phases": {"": "1"},
                            "author_phases": [1],
                            "widths": {
                                name: list(window.size)
                                for name, window in run.windows.items()
                            },
                        },
                        "phases": {
                            "1": {
                                "page": str(evidence / "page"),
                                "trace": summary,
                                **captures,
                            }
                        },
                    },
                    "check_output": {
                        "plain": plain_output,
                        "render": render_output,
                    },
                    "condition": condition,
                    "check_log": check_log(trace),
                    "payload": str(payload),
                    "setup_seconds": setup_seconds,
                    "author_seconds": author_seconds,
                    "input_media": inputs,
                    **(
                        {
                            "capture_evidence": capture_evidence(
                                page,
                                images,
                                # A case that compares conditions judges each on
                                # what all of them have, so Leaf's sweep stays the
                                # author's feedback and isn't extra evidence.
                                state / "leaf" / "screens"
                                if metadata.get("conditions", ["leaf"]) == ["leaf"]
                                else None,
                                shots,
                                [
                                    image
                                    for paths in captures.get("captures", {}).values()
                                    for image in paths
                                ],
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
            if error := author_failure(trace):
                response["error"] = error
        finally:
            if leaf:
                stopped = run_leaf(payload, state, "server", "stop", str(page))
                (evidence / "stop.txt").write_text(stopped.stdout + stopped.stderr)
            if page.is_dir():
                shutil.copytree(page, evidence / "page")
    (evidence / "result.json").write_text(json.dumps(response, indent=2))
    return response
