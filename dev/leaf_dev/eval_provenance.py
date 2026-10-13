"""Content identities for authoring arms, runtime bytes and evaluator sources.

A Git commit identifies the checkout's context, not an uncommitted payload. File
hashes identify the actual bytes. Authoring instructions, the vendored browser
runtime, and evaluation code are recorded separately; historical unknowns stay
unknown rather than being filled from today's checkout.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from leaf.schema import BROWSER_DIRS, VENDORED_FILES

from leaf_dev import ROOT


def files_identity(paths: list[Path], root: Path) -> dict:
    """Hash exactly the supplied files, with paths relative to their owner."""
    files = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(set(paths))
        if path.is_file()
    }
    return {
        "sha256": hashlib.sha256(
            json.dumps(files, sort_keys=True).encode()
        ).hexdigest(),
        "files": files,
    }


def tree_identity(root: Path) -> dict:
    return files_identity(list(root.rglob("*")), root)


def runtime_identity(page: Path) -> dict:
    """Pin saved vendored runtime bytes, or the standalone HTML artifact."""
    if not (page / "leaf.js").exists():
        return {"kind": "native-html", **tree_identity(page)}
    # The vendoring owner declares the browser layer. Author inputs and process
    # records are part of the complete artifact, never this layer's identity.
    files = [
        *(page / name for name in VENDORED_FILES),
        *(path for name in BROWSER_DIRS for path in (page / name).rglob("*")),
    ]
    return {"kind": "vendored-leaf", **files_identity(files, page)}


def run_identity(arms: dict[str, Path], commits: dict[str, str]) -> dict:
    """Record evaluator bytes and each authoring arm before temporary arms leave."""
    evaluator = [
        *(ROOT / "dev/leaf_dev").glob("*.py"),
        *(ROOT / "evals/workflows").glob("*.yaml"),
        *(ROOT / "evals").glob("*/request.md"),
        ROOT / "package.json",
        ROOT / "pnpm-lock.yaml",
        ROOT / "uv.lock",
    ]
    return {
        "evaluator": {
            "commit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            **files_identity(evaluator, ROOT),
        },
        "arms": {
            name: {
                "commit_context": commits[name],
                **files_identity(
                    [
                        path
                        for path in root.rglob("*")
                        if ".venv" not in path.relative_to(root).parts
                        and "__pycache__" not in path.relative_to(root).parts
                    ],
                    root,
                ),
            }
            for name, root in arms.items()
        },
    }
