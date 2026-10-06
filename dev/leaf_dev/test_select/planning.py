"""Pure Jev selection questions, conservative byte budgets, and request batches.

A test's complete question and every state chunk must fit the single-question
budget. Preparation selects individual unsendable tests locally; planning still
raises if a caller leaves such a test unresolved. Evidence is never truncated.
"""

import json

REQUEST_BUDGET_BYTES = 144000
SINGLE_QUESTION_BUDGET_BYTES = 110000

TASK = (
    "Select whether this test should run for this code change. Judge whether the change can affect "
    "behaviour exercised by the test, including prerequisites in its setup, fixtures and helpers. "
    "A relevant test should run even if the implementation is correct and the test is expected to pass. "
    "Use the supplied source evidence; test names alone are incomplete. "
    "Do not predict whether the implementation contains a bug."
)
CRITERIA = {
    "relevant": "The changed code can affect a behaviour, setup prerequisite, or assertion exercised by this test; run it to validate the change.",
    "unrelated": "The changed behaviour is independent of this test, its setup and the assumptions its assertions check; this test is unnecessary for this change.",
    "unknown": "Essential evidence about the relationship is missing or ambiguous; relevance cannot be resolved from the supplied input.",
}


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def question(card: dict) -> dict:
    return {
        "type": "choice",
        "instructions": {
            "task": TASK,
            "test_file": card["file"],
            "test_name": card["nodeid"].split("::", 1)[1],
            "evidence": {
                "test_body": {
                    k: card["body"][k] for k in ("path", "start", "end", "code")
                },
                "parameters": card["params"],
                "fixture_names": card["fixturenames"],
                "direct_test_context": card["test_context"],
            },
        },
        "criteria": CRITERIA,
    }


def unresolved(
    cards: list[dict], state_chunks: list[dict], mandatory_ids
) -> list[dict]:
    """Identify nonmandatory tests with at least one oversized complete query."""
    mandatory = set(mandatory_ids)
    result = []
    for card in cards:
        if card["nodeid"] in mandatory:
            continue
        q = question(card)
        max_bytes = max(
            (
                len(encode({"state": portion["state"], "question": q}))
                for portion in state_chunks
            ),
            default=0,
        )
        if max_bytes > SINGLE_QUESTION_BUDGET_BYTES:
            result.append(
                {
                    "nodeid": card["nodeid"],
                    "max_bytes": max_bytes,
                    "budget_bytes": SINGLE_QUESTION_BUDGET_BYTES,
                    "reason": "complete-state-and-test-question-exceeds-context-budget",
                }
            )
    return result


def plan(inputs: dict) -> list[dict]:
    mandatory = set(inputs["mandatory_test_ids"])
    batches = []
    for state_index, portion in enumerate(inputs["states"]["state_chunks"]):
        questions = {}
        for index, card in enumerate(inputs["cards"]):
            if card["nodeid"] in mandatory:
                continue
            name = f"s{state_index}q{index}"
            q = question(card)
            next_questions = {**questions, name: q}
            request = {
                "model": inputs["policy"]["model"],
                "state": portion["state"],
                "questions": next_questions,
            }
            if questions and len(encode(request)) > REQUEST_BUDGET_BYTES:
                batches.append({**request, "questions": questions})
                questions = {name: q}
            else:
                questions = next_questions
            if (
                len(encode({"state": portion["state"], "question": q}))
                > SINGLE_QUESTION_BUDGET_BYTES
            ):
                raise ValueError(
                    "A complete state and test question exceed the conservative context budget"
                )
        if questions:
            batches.append(
                {
                    "model": inputs["policy"]["model"],
                    "state": portion["state"],
                    "questions": questions,
                }
            )
    return batches
