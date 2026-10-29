"""Structured widget inference through the page's logged-in agent harness.

The page's active claimant selects the host's inference transport; credentials stay
with that transport. Callers supply only input, instructions and a required JSON
Schema, never a model, executable, tools or provider parameters. The host can select
its cheap model: Luna for Codex, Haiku for Claude; Pi runs the model its user
configured.

Results return to the caller without collecting data or writing page state. Leaf
makes one harness request and adds no retries. The harness owns its own transport
retry behavior. Issue #4020 owns the deferred allowance and accounting work: this
endpoint does not bound cumulative usage.
"""

import json
import subprocess
from pathlib import Path

from jsonschema.exceptions import SchemaError, ValidationError
from referencing.exceptions import Unresolvable
from websockets.exceptions import WebSocketException

from .harness import claim_harness
from .refusals import Refused
from .registry.schema import check_schema, unresolved_schema_reference
from .service import PageTransaction

MAX_INPUT_BYTES = 64 * 1024


class LLMError(Refused):
    """A request the inference endpoint cannot fulfill."""

    def __init__(self, reason: str, status: int = 400):
        super().__init__(reason)
        self.status = status


def generate(page_dir: Path, request: dict) -> dict:
    """Validate the widget request and ask the claimant's inference capability."""
    if request.keys() - {"input", "instructions", "schema"}:
        raise LLMError("LLM requests accept only input, instructions and schema.")
    if not isinstance(request.get("input"), str):
        raise LLMError("LLM input must be text.")
    if "instructions" in request and not isinstance(request["instructions"], str):
        raise LLMError("LLM instructions must be text.")
    if not isinstance(request.get("schema"), dict):
        raise LLMError("LLM requests require a JSON Schema object.")
    if len(json.dumps(request, ensure_ascii=False).encode()) > MAX_INPUT_BYTES:
        raise LLMError("LLM input, instructions and schema exceed 64 KiB.")

    try:
        check_schema(request["schema"])
        if reference := unresolved_schema_reference(request["schema"]):
            raise LLMError(f"LLM schema has an unresolved reference: {reference}")
    except SchemaError as error:
        raise LLMError(f"Invalid LLM schema: {error.message}") from error

    with PageTransaction(page_dir) as page:
        claim = page.active_claim
    inference = claim_harness(claim).inference_generator() if claim else None
    if inference is None:
        raise LLMError(
            "LLM access needs a page claimed by Codex, Claude Code or Pi.", 503
        )
    try:
        return inference(
            request["input"],
            page_dir,
            schema=request["schema"],
            instructions=request.get("instructions", ""),
        )
    except (
        OSError,
        Refused,
        WebSocketException,
        RuntimeError,
        TimeoutError,
        subprocess.TimeoutExpired,
        ValueError,
        ValidationError,
        Unresolvable,
    ) as error:
        raise LLMError(str(error), 502) from error
