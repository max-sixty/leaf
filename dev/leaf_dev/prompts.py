"""The prompts Leaf sends a model in Claude Code, for How it works to show beside the
prose that describes each (`docs.compose`, `lf-text-document[data-prompt]`).

Each entry of `PROMPTS` calls the function that writes its prompt, so the page shows
Leaf's text, and the references it quotes, as the code has them now. This module
supplies only the values a prompt is written around. The messages of a fork journey
(`line`, `delivery`), which How it works' "Anatomy of a fork journey" shows
beside the timings and Claude Code's text of one recorded run, are written around that
run's own values (`JOURNEY`). The rest come from one
illustrative scenario: a page, a thread on it, the user's newest message there and a
page's facts. A delivery's handling clauses and envelope are derived from its batch
(`delivery`). The values take the shapes Leaf gives them, and
`test_how_it_works_shows_each_prompt_as_leaf_writes_it` holds each delivery to the
schema a stored one meets (`delivery.DELIVERY`).

Leaf's other model requests carry text a page supplies, such as a widget's
instructions (`llm.py`), which the page leaves out.
"""

import json
from pathlib import Path

from leaf.agents import clerk, forks, inference, summary_fork, thread_titles
from leaf.agents.delivery import DELIVERY, envelope, handled, inline_context
from leaf.base.state import kernel_registry

# The values Leaf wrote each of its messages around in the 10:55 PT run of the
# claude-code agent journey on 20 November 2026 (`leaf-dev journey run claude-code`),
# under Claude Code 2.1.329: the batch the line fork read and what the session was
# running (`line`), and the id, time and batch of the delivery that gave the session
# the message, with the line already among its thread's messages (`delivery`). Each
# batch is the page's events as `delivery.batch_data` captured them, with no
# handling, which `delivery` derives.
JOURNEY = json.loads(Path(__file__).with_name("fork-journey.json").read_text())

PAGE = "/home/you/.local/state/leaf/pages/importer-review"
SESSION = "0c7e4b1e-5d2a-4f6b-9a31-2f8d64c1b7a9"
THREAD = "9d3c8e8c"


def message(seq: int, identity: str, author: str, text: str, **more) -> dict:
    """A thread message as a delivery's thread digest carries it."""
    return {
        "id": identity,
        "seq": seq,
        "ts": f"2026-11-18T09:{seq:02d}:00.000-08:00",
        "author": author,
        **({"agent": "Claude"} if author == "agent" else {}),
        "text": text,
        **more,
    }


# A thread, in log order: the user's question, the agent's answer, the user's
# follow-up and the working line a line fork wrote for it, the agent's answer to it,
# and the user's next message, with its own working line.
SAID = [
    message(1, THREAD, "user", "Why does the importer poll every 2 seconds?"),
    message(
        2,
        "5129dca6",
        "agent",
        "It matches the lease's renewal interval, so a worker that dies is noticed "
        "within one poll.",
    ),
    message(
        3, "6dfe00c2", "user", "Could it poll less often? Check what the lease allows."
    ),
    message(4, "515ced89", "agent", "checking what the lease allows", ephemeral=True),
    message(
        5,
        "a41f09d2",
        "agent",
        "The lease allows 10 s between renewals, so a 5 s poll still notices a dead "
        "worker within one renewal.",
    ),
    message(6, "e2b85c17", "user", "What happens to a worker that renews late?"),
    message(
        7, "70c4b9e3", "agent", "checking how a late renewal is handled", ephemeral=True
    ),
]
# A longer run of the same discussion, for the fork that summarizes a long thread.
LONG = [
    *SAID,
    message(
        8,
        "c90d4e61",
        "agent",
        "Its lease lapses and another worker takes its batch; the late worker's "
        "writes are refused.",
    ),
    message(9, "3b72f0a8", "user", "Then 5 s it is. Does the backfill job poll too?"),
    message(10, "d58e1c36", "agent", "Yes, every 2 s, from the same setting."),
    message(11, "f6a39b25", "user", "Move both to 5 s and show the load on the page."),
]


def batch(earlier: list[dict], newest: dict) -> dict:
    """The page batch Leaf captures for the user's `newest` message in the thread,
    whose other messages are `earlier` (`delivery.batch_data`, `whole`)."""
    return {
        "page": PAGE,
        "claim": SESSION,
        "through_seq": newest["seq"],
        "threads": [
            {
                "id": THREAD,
                "title": "Poll interval",
                "anchor": None,
                "detached_from": None,
                "rewritten_from": None,
                "resolved": None,
                "elided": {"messages": 0, "actions": 0},
                "messages": earlier,
                "summaries": [],
                "actions": [],
            }
        ],
        "events": [
            {
                "attention": True,
                "kind": "reply",
                "parent": THREAD,
                "author": "user",
                "text": newest["text"],
                "id": newest["id"],
                "ts": newest["ts"],
                "seq": newest["seq"],
                "subject": {"kind": "thread", "id": THREAD},
                "threads": [THREAD],
                "answer": {
                    "kind": "reply",
                    "parent": newest["id"],
                    "responds": newest["id"],
                },
            }
        ],
    }


def delivery(identity: str, captured: dict, created: float = 1795050000.0) -> dict:
    """The delivery `identity`, made at `created`, that Leaf freezes from the batch
    `captured` (`delivery.freeze_delivery`), with the handling the kernel registry
    gives its events."""
    handling = handled(captured, kernel_registry(), identity, 0, turn_replies=False)
    return DELIVERY.stored(envelope(identity, created, [handling]))


def journey_delivery() -> dict:
    """The delivery that gave the recorded journey's session its message
    (`JOURNEY`)."""
    step = JOURNEY["delivery"]
    return delivery(step["id"], step["batch"], step["created_at"])


# The batch the summary fork reads.
FOLDED = batch(LONG[:-1], LONG[-1])


def line() -> str:
    return forks.line_prompt(
        forks.thread_json(JOURNEY["line"]["batch"]), JOURNEY["line"]["running"]
    )


def delivery_context() -> str:
    return inline_context(journey_delivery())


def summary() -> str:
    # The range Leaf suggests (`thread_context.summary_hint`): all but the newest
    # exchange.
    hint = {"from": THREAD, "through": LONG[-3]["id"]}
    return summary_fork.prompt(forks.thread_json(FOLDED), hint)


def turn_end() -> str:
    return clerk.fork_prompt(
        [
            {
                "title": "Importer poll interval",
                "path": PAGE,
                "on_me": [
                    'a reply to the agent\'s message in "Poll interval": Keep the '
                    "2 s poll, or move the importer and the backfill job to 5 s?"
                ],
                "asked": [
                    'f0b6d913, in "Lease length", answered: Should the lease stay '
                    "at 10 s?"
                ],
                "started": [
                    {
                        "item": "7d1e9a40",
                        "about": "the agent's to-do \"Measure the importer's load\"",
                        "line": "Running the load test at a 5 s poll",
                    }
                ],
                "text": "Importer poll interval\n"
                "The importer polls every 2 s, matching the lease's renewal.\n"
                "Load at 2 s: 340 requests a minute.\n"
                "Next: measure the load at 5 s.",
            }
        ]
    )


def title_system() -> str:
    return inference.answering(thread_titles.INSTRUCTIONS, thread_titles.OUTPUT_SCHEMA)


def title_request() -> str:
    return thread_titles.title_text(
        "The importer polls every 2 s, matching the lease's renewal.", SAID[0]["text"]
    )


def references() -> list[Path]:
    """The shipped references the prompts quote, which a preview follows."""
    quoted = (*clerk.GUIDANCE, summary_fork.RANGE, summary_fork.GUIDANCE)
    names = sorted({name for name, _ in quoted})
    return [clerk.REFERENCE, *(clerk.REFERENCES / name for name in names)]


# Each prompt by the name its slot on How it works gives (`data-prompt`).
PROMPTS = {
    "line": line,
    "delivery": delivery_context,
    "summary": summary,
    "turn-end": turn_end,
    "title-system": title_system,
    "title-request": title_request,
}
