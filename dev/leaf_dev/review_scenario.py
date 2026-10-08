"""The release-review task shared by the live Claude Code, Codex and Pi sessions.

Every harness starts with the same request and one stamped, undecided document. This
scenario uses only the current triage source on the default layer: the catalog's
packages, companion history and prior versions are outside the delivery experiment.
The runners own transport, timing and assertions. The journey's harness steps
(`journey_claude_code`, `journey_codex`, `journey_pi`) also share the comments a
step sends and the reading of what holds between steps.
"""

import shutil
from pathlib import Path

import click
from leaf.event_log import read_events
from leaf.service import page_claim
from leaf.thread import successful_replies

from leaf_dev import ROOT
from leaf_dev.arms import run_leaf

REQUEST = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)

COMMENTS = {
    "mid-turn": "Is the migration the only blocker, or the first?",
    "restart": "Anything else I should check before we ship?",
    "reconnect": "Is the same review still connected?",
    "escape": "Did the interrupted check change anything?",
    "held-escape": "If the migration slips, which work can still ship?",
    "woken": "Which item would you cut if we had to ship today?",
    "after-wake": "And which one would you keep at any cost?",
    "first": "Who owns the migration fix?",
    "ending": "When could that fix land?",
}


def prepare(arm: Path, state: Path, page: Path) -> None:
    """Prepare the same release-review starting state using the harness's Leaf arm."""
    run_leaf(arm, state, "page", "init", str(page), check=True)
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    run_leaf(
        arm, state, "page", "stamp", str(page),
        "--text", "Release triage for review.", check=True,
    )  # fmt: skip


def require(condition: bool, message: str) -> None:
    if not condition:
        raise click.ClickException(message)


def answers(page: Path, comment: str) -> list[dict]:
    """Successful agent replies to one sent comment."""
    return successful_replies(read_events(page), comment)


def settled(page: Path, session: str, sent: dict[str, str]) -> dict:
    """What holds while a task is idle between steps: each comment sent so far
    (`sent`, each step's name and its comment's id) answered once and picked up, and
    the page claimed by the task's session with its turn closed. Returns the claim."""
    events = read_events(page)
    for step, comment in sent.items():
        replies = answers(page, comment)
        require(
            len(replies) == 1,
            f"comment `{step}` has {len(replies)} replies, not one",
        )
        require(
            any(
                event["kind"] == "pickup" and comment in event["events"]
                for event in events
            ),
            f"comment `{step}` has a reply but no pickup",
        )
    claim = page_claim(page)
    require(claim is not None, "the page has no claim")
    require(
        claim["id"] == session,
        f"the page is claimed by {claim['id']}, not the task {session}",
    )
    require(
        claim["turn_closed"] is not None,
        f"turn {claim['turn']} has ended, but the claim holds it open",
    )
    return claim
