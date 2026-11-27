"""The release-review task shared by the live Claude Code, Codex and Pi sessions.

Every harness starts with the same request and one stamped, undecided document. This
scenario uses only the current triage source on the default layer: the catalog's
packages, companion history and prior versions are outside the delivery experiment.
The runners own transport, timing and assertions. The journey's harness steps
(`_journey.Terminal` and each harness's own) also share the comments a step sends,
and the readings of the page they check: its claim, the turns that picked up a
comment, its status, and what holds between steps.
"""

import shutil
from pathlib import Path

import click

from leaf.agents.delivery import pickup_receipts
from leaf.agents.thread import successful_replies
from leaf.base.service import page_claim
from leaf.base.state import turn_closed
from leaf.commands.agent_state import cmd_page_state
from leaf.log.event_log import read_events
from leaf_dev import ROOT
from leaf_dev.arms import PageClient, run_leaf
from leaf_dev.eval_cases import definition

REQUEST = definition("delivery_eval")["prompts"]["initial"]

# Each step's comment, on the section it is posted on. A Claude Code session does a
# request for a change to the page itself, and may give a question it could answer by
# reading to a subagent (`references/harness-claude-code.md`, "Subagents"), so each
# of the claude-code journey's delivery steps asks to reword one phrase, and so do
# `mid-turn` and `escape` on the other harnesses, which share them. A rewording keeps
# the page's meaning and shape, which leaves the session and Claude Code's turn-end
# check (`leaf.agents.clerk`) nothing more to raise with the user. Each quotes words found
# once in its section of `examples/triage-board.html`, and no two steps touch the
# same words.
COMMENTS = {
    "mid-turn": ("triage-why", "In this section, change “a no-op” to “harmless”."),
    "restart": ("triage-lede", "Anything else I should check before we ship?"),
    "reconnect": ("triage-lede", "Is the same review still connected?"),
    "escape": ("triage-why", "In this section, change “exits non-zero” to “fails”."),
    "resume": ("triage-why", "Did resuming the check change anything?"),
    "unload": ("triage-lede", "Who signs off once the migration is fixed?"),
    "held-escape": (
        "triage-lede",
        "If the migration slips, which work can still ship?",
    ),
    "woken": (
        "triage-lede",
        "In this paragraph, change “Once 0042 ships” to “When 0042 ships”.",
    ),
    "after-wake": (
        "triage-why",
        "In this section, change “billed twice in March” to “double-billed in March”.",
    ),
    "dropped": (
        "triage-why",
        "In this section, change “it pays twice” to “it pays out twice”.",
    ),
    "deferred": (
        "triage-lede",
        "In this paragraph, change “the same failure” to “that same failure”.",
    ),
    "first-wake": (
        "triage-lede",
        "In this paragraph, change “ship differently” to “ship another way”.",
    ),
    "boundary": (
        "triage-why",
        "In this section, change “by waiting a week” to “if it waits a week”.",
    ),
    "first": (
        "triage-lede",
        "In this paragraph, change “Today that is harmless.” to “Today that does no "
        "harm.”",
    ),
    "ending": (
        "triage-why",
        "In this section, change “has few reports” to “has few reports so far”.",
    ),
    "compacting": (
        "triage-lede",
        "In this paragraph, change “the only release blocker” to “the one release "
        "blocker”.",
    ),
    # A question answered by reading the page's source, sent while the session runs
    # the user's own turn, which the session gives a subagent, and which the user
    # follows up in its thread once it is answered (`FOLLOW_UP`). The session judges
    # whether a lookup is worth a fork, and does a one-step count itself, so the user
    # asks for this beside its work.
    "fork-busy": (
        "triage-lede",
        "Look into this beside your own work, no rush: read the cards in this page's "
        "source and tell me which one a release manager would ask about first, and "
        "why.",
    ),
    # A question the agent asks with choices, which the user then answers twice
    # (`_journey.Terminal.answered_twice`).
    "answered-twice": (
        "triage-lede",
        "Should we ship now or wait for the migration fix? Ask me in this thread, "
        "with two clickable choices.",
    ),
    # Real author intent exercises the rich interface without naming its commands.
    "rich-choice": (
        "triage-lede",
        (
            "I need to decide whether to ship or wait. Give me two clickable choices "
            "inside this thread, not on the page. Explain the decision in a short "
            "question, and move this thread to the release rationale section."
        ),
    ),
    "rich-question": (
        "triage-lede",
        (
            "Ask me whether I can own the release check, as a question in this "
            "thread. Keep it waiting for my answer and move the thread to the release "
            "rationale section."
        ),
    ),
}

# A turn of the user's own that runs a shell command long enough to comment, or press
# Escape, during it. Each harness finds the command among its own session's: Claude
# Code's journey among its pane's processes, Codex's and Pi's in what the session
# reports running.
SLEEP = "time.sleep(25.17)"
USER_TURN = (
    f"Run `python3 -c 'import time; {SLEEP}'` in the shell, in the foreground. Then, "
    "in a separate tool call, run `printf 'verified\\n'`. Then reply with the single "
    "word done."
)


def prepare(arm: Path, state: Path, page: Path) -> None:
    """Prepare the same release-review starting state using the harness's Leaf arm."""
    run_leaf(arm, state, "page", "init", "--package", "reading", str(page), check=True)
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    run_leaf(
        arm, state, "page", "stamp", str(page),
        "--text", "Release triage for review.", check=True,
    )  # fmt: skip


def attempt(step: str) -> str:
    """The retry key a step's comment is posted under, as long as the log requires."""
    return f"journey-step-{step}"


def post(url: str, step: str, text: str | None = None) -> str:
    """Post step `step`'s comment to the page served at its keyed `url`, as the page's
    tab posts one, and return its admitted id: the scenario's (`COMMENTS`) on its
    section, or `text` on the page as a whole."""
    section, text = COMMENTS[step] if text is None else (None, text)
    return PageClient(url).post(
        {
            "kind": "comment",
            "attempt": attempt(step),
            "text": text,
            **({"anchor": {"section": section}} if section else {}),
        }
    )["id"]


def require[T](condition: T | None, message: str) -> T:
    if not condition:
        raise click.ClickException(message)
    return condition


def answers(page: Path, comment: str) -> list[dict]:
    """Successful agent replies to one sent comment."""
    return successful_replies(read_events(page), comment)


def picked_up(page: Path, comment: str) -> list[str]:
    """The turns whose opened pickups took one sent comment into the harness's
    context."""
    return [
        event["turn"]
        for event in pickup_receipts(
            read_events(page), phase="opened", input_id=comment
        )
    ]


def claimed(page: Path) -> dict:
    """The page's claim, which a session has held since setup."""
    return require(page_claim(page), "the page has no claim")


def activity(page: Path) -> tuple[str, str]:
    """What the page's status reads (`leaf.records.activity`): whether anyone is there to
    take input, and where the agent's work stands."""
    reading = cmd_page_state(page)["activity"]
    return reading["presence"], reading["state"]


def settled(page: Path, session: str, sent: dict[str, str]) -> dict:
    """What holds while a task is idle between steps: each comment sent so far
    (`sent`, each step's name and its comment's id) answered once and picked up, and
    the page claimed by the task's session with its turn closed. Returns the claim."""
    for step, comment in sent.items():
        replies = answers(page, comment)
        require(
            len(replies) == 1,
            f"comment `{step}` has {len(replies)} replies, not one",
        )
        require(
            bool(picked_up(page, comment)),
            f"comment `{step}` has a reply but never entered the harness context",
        )
    claim = claimed(page)
    require(
        claim["id"] == session,
        f"the page is claimed by {claim['id']}, not the task {session}",
    )
    require(
        turn_closed(claim),
        f"turn {claim['turn']} has ended, but the claim holds it open",
    )
    return claim
