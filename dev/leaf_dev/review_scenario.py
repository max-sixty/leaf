"""The release-review task shared by the live Claude Code, Codex and Pi journeys.

Every harness starts with the same request and one stamped, undecided document. This
scenario uses only the current triage source on the default layer: the catalog's
packages, companion history and prior versions are outside the delivery experiment.
The runners own transport, timing and assertions. The verifiers of a real task
(`verify_claude_code_task`, `verify_codex_task`, `verify_pi_task`) also share the comments a step posts, as the
page's tab posts them, and the reading of the replies that answer each.
"""

import shutil
from pathlib import Path

import click
from leaf.event_log import read_events
from leaf.server import running_server
from leaf.service import page_claim
from leaf.thread import successful_replies

from leaf_dev import ROOT
from leaf_dev.arms import PageClient, run_leaf

REQUEST = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)

COMMENTS = {
    "idle": ("triage-lede", "Which of these items actually blocks the release?"),
    "mid-turn": ("triage-why", "Is the migration the only blocker, or the first?"),
    "restart": ("triage-lede", "Anything else I should check before we ship?"),
    "reconnect": ("triage-lede", "Is the same review still connected?"),
    "escape": ("triage-why", "Did the interrupted check change anything?"),
    "held-escape": (
        "triage-lede",
        "If the migration slips, which work can still ship?",
    ),
    "woken": ("triage-lede", "Which item would you cut if we had to ship today?"),
    "after-wake": ("triage-why", "And which one would you keep at any cost?"),
    "first": ("triage-lede", "Who owns the migration fix?"),
    "ending": ("triage-why", "When could that fix land?"),
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


def attempt(step: str) -> str:
    """The retry key a step's comment is posted under, as long as the log requires."""
    return f"verify-task-{step}"


def comment_id(page: Path, step: str) -> str:
    return next(
        event["id"]
        for event in read_events(page)
        if event["kind"] == "comment" and event.get("attempt") == attempt(step)
    )


def answers(page: Path, step: str) -> list[dict]:
    """Successful agent replies to one posted comment."""
    return successful_replies(read_events(page), comment_id(page, step))


def settled(page: Path, session: str, posted: list[str]) -> dict:
    """What holds while a task is idle between steps: each comment posted so far
    answered once and picked up, and the page claimed by the task's session with its
    turn closed. Returns the claim."""
    events = read_events(page)
    for step in posted:
        replies = answers(page, step)
        require(
            len(replies) == 1,
            f"comment `{step}` has {len(replies)} replies, not one",
        )
        posted_id = comment_id(page, step)
        require(
            any(
                event["kind"] == "pickup" and posted_id in event["events"]
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


def post(page: Path, step: str) -> None:
    """Post a step's comment as the page's tab does."""
    section, text = COMMENTS[step]
    client = PageClient(running_server(page)["url"])
    client.post(
        {
            "kind": "comment",
            "revision": client.state()["active"]["revision"],
            "attempt": attempt(step),
            "text": text,
            "anchor": {"section": section},
        }
    )
