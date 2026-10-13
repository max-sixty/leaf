"""Native judge integrity shared by authoring and pairwise grading.

A successful model result is not proof it inspected its evidence. Every required
file must have a successful native Read result, and successful reads outside the
public manifest invalidate a blinded judgment. These checks establish delivery,
not understanding; semantic conclusions remain model judgments. Callers own their
evidence selection and verdict schemas.
"""

from collections.abc import Iterable
from pathlib import Path

from leaf_dev.arms import blocks, completed


def validate_reads(
    trace: list[dict], required: Iterable[Path], allowed: Iterable[Path] | None = None
) -> set[str]:
    """Return successful absolute Read paths, or reject incomplete/unblinded grading.

    ``allowed`` defaults to the required files. An explicit broader manifest may
    permit optional public evidence; it must still include every required file.
    Tool calls without a successful matching result do not establish a read.
    """
    required_paths = {str(path.resolve()) for path in required}
    allowed_paths = (
        required_paths if allowed is None else {str(path.resolve()) for path in allowed}
    )
    if not required_paths <= allowed_paths:
        raise ValueError("Required judge evidence is outside its allowed manifest")
    if not completed(trace):
        raise ValueError("Judge execution did not complete successfully")
    results = {
        block["tool_use_id"]: not block.get("is_error", False)
        for block in blocks(trace)
        if block.get("type") == "tool_result" and block.get("tool_use_id")
    }
    opened = {
        str(Path(block["input"]["file_path"]).resolve())
        for block in blocks(trace)
        if block.get("type") == "tool_use"
        and block.get("name") == "Read"
        and block.get("input", {}).get("file_path")
        and results.get(block.get("id")) is True
    }
    if opened - allowed_paths:
        raise ValueError("Judge read files outside the public evidence manifest")
    missing = required_paths - opened
    if missing:
        raise ValueError(
            f"Judge did not read required public evidence: {sorted(missing)}"
        )
    return opened
