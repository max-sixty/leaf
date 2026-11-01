"""One user's journey through a Leaf page, run on any harness, each step timed from
the page's own record and checked.

    uv run leaf-dev journey TARGET [--browser | --http] [--release RELEASE]
                                   [--sandbox] [--preview]

The user tells the agent that a release passed its deployment checks, asking it to
record that on the board. How the page records it is the agent's call, as with a
real user's request; this `release` step requires a reply and a published revision
that names the release. Every target gets the same ask and the same checks. TARGET
names what answers:

- `claude-code`: an interactive Claude Code session in a tmux pane
  (`journey_claude_code`);
- `codex-app-server` or `codex-queue`: a Codex task reaching Leaf through that
  transport (`journey_codex`): App Server's, as `leaf codex launch` and leaf.page run
  Codex, or the queue, as the desktop app and IDE extension do;
- `pi`: a Pi session in RPC mode (`journey_pi`);
- `website-adapter`: the website's adapter on this machine, against the host's
  Codex login, with no Worker, container limits, credential proxy or Docker;
- `website-worker`: the built site through the local Worker and its page container;
- an origin such as `https://leaf.page`: the deployed website, at `--release` or
  whichever release it serves.

A harness target runs this working tree's plugin in a session of its own, under a
throwaway home holding only the host's login, and the journey is also the terminal:
it asks for the page to be served (`setup`), types the user's turns, presses Escape,
and kills what a crash would. Around `release` each harness module runs the steps
its harness can take, and checks, between steps, that every comment so far has one
reply and entered the session's context, and that the page's claim names the session
with its turn closed. A website target runs `release` alone, since only a terminal
can start a turn or interrupt one. What the harnesses share lives here: their
isolation and its evidence (`isolated`), the session the journey hears through every
wait (`Terminal`), and the user (`User`). `--sandbox` runs the session's shell
commands in its harness's sandbox; `--preview` has Codex serve the page with the
canonical `leaf-dev preview --user`; `--forks` lets forks of Claude Code's
conversation answer the user's thread messages, and runs the steps that test them
in place of the delivery steps (`journey_claude_code`). The journey stops at the
first check that fails and keeps no sample.

Where the user is, every step alike, is the journey's one axis (`User.end`):

- over HTTP (`--http`, a harness's default): no browser starts. Every comment, the
  release ask's included, is posted as the page's tab posts one, on its section
  (`HttpEnd`). This is the journey for the agent and its harness: what each step
  checks, and every milestone a step is timed by, is on the page server's clock in
  the log;
- in Chrome (`--browser`, a website's only end): every comment is typed as a user types it,
  a page comment in the floating panel's field and an anchored one on its selected passage, each reply's showing is timed by the
  page, and the release ask's reload is checked and profiled (`BrowserEnd`). This is
  the whole journey, what the page shows the user included.

Both ends share every check: the release ask waits on the same turn, title and answer
(`run_journey`), and each end only sends the user's comments and says what it saw of
them (`reading`), the browser alone reloading the page and timing what it shows.

The timings come from where each step happened. The page server records when it
admitted a comment, recorded its pickup, titled its thread, activated the published
revision and admitted the reply; `sinceAdmissionMs` reads those from the comment's
admission, so every target and either end is timed on one clock, the page server's.
In Chrome the browser also sees the POST's answer and the reply showing, in the
floating panel's view of its thread or on its card at its passage, which the page
records itself (`shown_reply`); `sinceSendMs` reads those from the
send. Where the journey runs the agent itself, its record of the session (Claude
Code's transcript, Codex's App Server notifications, Pi's RPC events) also splits each
reply (`reply`, `reply_phases.reply_breakdown`): it attributes the whole reply to
Leaf, the harness and the model, so a slow reply shows where it went.

The release ask, a small page change and each session's first comment, reaches the
harness in one of two cases (`--case`, a harness target's option): `waiting`, idle
until Leaf's watch or hook wakes it, or `working` on the user's own turn, which
runs a 25 s shell command (`Terminal.work`) the harness finishes before it takes
the comment at that tool boundary. Each journey runs one case in a session of its
own, so both start from the same page and context. The JSON on stdout carries all
of it: the user's end (`userEnd`), the `case`, `comment` for the release ask,
`steps` for each step's duration and its comments' timings, and the code version
the journey ran. A comment whose step held a permission prompt the user answered
says so (`approved`), since the prompt held the session for as long as it stood. A
comment a fork of the conversation decided on carries the fork's outcome, time and
tokens (`fork`); one the fork answered has no `reply` breakdown, since the session
spent nothing on it.

A failure receipt ends the journey on the first ask
(`worker/README.md` owns that contract).

Each sample is also kept on the machine that ran it (`samples_path`), and
`leaf-dev journey-chart` draws when each milestone came, from the kept samples of
the latest version each target ran at each end, as an `lf-chart` element for a
page.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, NamedTuple
from urllib.parse import urljoin

import click
import psutil
from playwright.sync_api import BrowserContext, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf import inference, thread_titles
from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.files import revision_path
from leaf.findings import Finding
from leaf.interaction_log import read_interactions
from leaf.server import running_server
from leaf.service import page_claim
from leaf.structure import SourceDocument
from leaf.thread import successful_replies
from leaf.todos import start_reading
from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, PageClient, extract_payload, run_directory, run_leaf
from leaf_dev.browser import DESKTOP, headless_shell
from leaf_dev.commands.verify_site import (
    LocalWorker,
    agent_session,
    answered,
    await_presentation,
    check,
    local_adapter,
    local_worker,
    observe_startup,
    said,
    start_direct_agent,
    startup_profile,
)
from leaf_dev.page_fixtures import record_run_context
from leaf_dev.reply_phases import instant, reply_breakdown
from leaf_dev.review_scenario import COMMENTS, post
from leaf_dev.startup import startup_reading

# A turn's wait ends at `TURN_PATIENCE` unless the page says a turn is still working on
# the comment, which holds it to `TURN_LIMIT`. `TURN_LIMIT` bounds the whole pass, so
# raising it means raising `publish-site.yaml`'s `timeout-minutes` too.
TURN_PATIENCE = 300
TURN_LIMIT = 600
# The reload after the turn gets this long to present, then as long again to follow
# the published revision: its container may take seconds to answer the first read.
TURN_PRESENTATION = 120_000
# How long the page gets to draw a reply the container has admitted; the runtime's own
# quiet-stream bound (`SILENCE_MS` in `runtime/state-feed.js`) is the same 30 s.
VISIBLE_REPLY_PATIENCE = 30_000
# How long a reply first shown by its notice gets for its own message to come into
# view, which in an open thread is the next frame or two.
VISIBLE_MESSAGE_PATIENCE = 2
# How long the page server gets to title the thread after the turn ends: as long as
# it asks again after a refusal, then the last request's own limit.
TITLE_PATIENCE = thread_titles.RETRY_FOR + inference.TIMEOUT
# How long a harness journey's step waits for the session, and how long a session
# must stay idle with a step's outcome before the step counts it settled.
STEP_LIMIT = 300
QUIET = 10
# The harness targets, each named in a sample by its harness and, where the harness
# has more than one, the Leaf transport its turns take.
HARNESS_TARGETS = {
    "claude-code": {"harness": "claude-code"},
    "codex-app-server": {"harness": "codex", "transport": "app-server"},
    "codex-queue": {"harness": "codex", "transport": "queue"},
    "pi": {"harness": "pi"},
}
# Where the harness is when the release ask reaches it (`--case`).
CASES = ("waiting", "working")


def samples_path() -> Path:
    """Where this machine keeps every sample, one JSON line each, outside any
    checkout so runs from every worktree accumulate. A stopgap until a store CI can
    write to too (issue #4048, "Keep the agent journey's samples")."""
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(state) / "leaf-dev" / "journey.jsonl"


class Session(NamedTuple):
    """One user's open page, with what reaching its state takes: `headers` go with
    each state read, and `after_post` runs once a comment is admitted. `pause`
    waits, hearing the answering agent's session where the journey runs it."""

    context: BrowserContext
    page: Page
    failures: list[Finding]
    url: str
    state_url: str
    state: dict
    headers: dict[str, str]
    after_post: Callable[[dict], None] | None
    pause: Callable[[float], None] = time.sleep


def still_answering(state: dict, event_id: str) -> bool:
    """Whether the page's `activity` says a turn is working while the comment's own
    obligation is still on the agent, which a wall clock cannot tell."""
    activity = state.get("activity") or {}
    return activity.get("kind") == "working" and f"update:{event_id}" in (
        activity.get("obligations") or ()
    )


class TurnReading(NamedTuple):
    """What one ask reached before its turn stopped answering it."""

    state: dict
    published: dict | None
    replies: list[dict]
    answer: dict | None


class AgentProfile:
    """What the browser observed of one request: each ask's admitted comment and
    acknowledgement, the page's activity, and when the reply showed, all from the
    first send. Transport and authored work milestones come from the event log."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.visible_reply_started_ms: float | None = None
        self.acknowledged: list[float] = []
        self.visible_reply_s: float | None = None
        self.visible_reply_by: str | None = None
        self.visible_message_s: float | None = None
        self.activities: list[tuple[float, str, str]] = []
        self.ask_count = 0
        self.reference: str | None = None
        self.event_ids: list[str] = []

    def show(self, shown: dict) -> None:
        """Time the reply to the page's reading of when and how it showed it."""
        self.visible_reply_s = (shown["at"] - self.visible_reply_started_ms) / 1000
        self.visible_reply_by = shown["by"]
        if shown["message"] is not None:
            self.visible_message_s = (
                shown["message"] - self.visible_reply_started_ms
            ) / 1000

    def acknowledge(self) -> None:
        self.acknowledged.append(time.monotonic() - self.started)

    def observe(self, state: dict) -> None:
        activity = state.get("activity") or {}
        reading = (activity.get("kind") or "unknown", activity.get("detail") or "")
        if self.activities and self.activities[-1][1:] == reading:
            return
        self.activities.append((time.monotonic() - self.started, *reading))


class AgentAsks(NamedTuple):
    """The reading the pass ended on, with the asks and revision behind it."""

    turn: TurnReading
    asks: int
    revision: int
    profile: AgentProfile


def title(events: list[dict], thread: str) -> str | None:
    """The title `events` give `thread`, if any."""
    return build_threads(events, {}).get(thread, {}).get("title")


def pickup_at(
    events: list[dict], comment: str, phase: Literal["queued", "opened", "failed"]
) -> str | None:
    """When the harness first recorded `comment` picked up in `phase`: `queued` held
    by the harness, `opened` in its context (`leaf.delivery.pickup_receipts`)."""
    return next(
        (e["ts"] for e in pickup_receipts(events, phase=phase, input_id=comment)),
        None,
    )


def recorded_steps(events: list[dict], comment: dict, published: dict | None) -> dict:
    """Seconds after `comment`'s admission for its recorded milestones.

    Pickup records name exact inputs: queued is held by the harness, opened is in
    its context. A start is an authored work claim for this input. Neither implies
    visible feedback or that the model has begun reasoning. Title, explicit progress,
    publication and answer retain their server timestamps; absent steps are None,
    as is publication for a comment that asked for no revision.
    """
    admitted = instant(comment["ts"])
    thread = comment["id"]
    started = next(
        (
            e["ts"]
            for e in events
            if (start := start_reading(e)) and start["item"] == thread
        ),
        None,
    )
    titled = next(
        (
            event["ts"]
            for index, event in enumerate(events)
            if title(events[: index + 1], thread) is not None
        ),
        None,
    )
    replies = [e for e in events if e["kind"] == "reply" and e.get("parent") == thread]
    progress = next((e["ts"] for e in replies if e.get("ephemeral")), None)
    replied = deployment_answer(events, comment["id"])
    return {
        step: None if at is None else round(instant(at) - admitted, 3)
        for step, at in (
            ("queued", pickup_at(events, thread, "queued")),
            ("pickedUp", pickup_at(events, thread, "opened")),
            ("started", started),
            ("titled", titled),
            ("progress", progress),
            ("published", published["activated_at"] if published is not None else None),
            ("replied", replied["ts"] if replied is not None else None),
        )
    }


def agent_profile(profile: AgentProfile, steps: dict) -> dict:
    """One comment-to-answer profile in milliseconds: the page server's `steps` from
    the answered comment's admission, and the browser's observations from the first
    send."""

    def ms(seconds: float | None) -> float | None:
        return None if seconds is None else seconds * 1000

    return {
        "sessionReference": profile.reference,
        "eventIds": profile.event_ids,
        "asks": profile.ask_count,
        "sinceAdmissionMs": {step: ms(seconds) for step, seconds in steps.items()},
        "sinceSendMs": {
            "acknowledged": [ms(at) for at in profile.acknowledged],
            "responseVisible": ms(profile.visible_reply_s),
            # The reply's own message in view, which a notice holding it precedes.
            "responseMessageVisible": ms(profile.visible_message_s),
        },
        "responseShownBy": profile.visible_reply_by,
        "activity": [
            {"atMs": at * 1000, "kind": kind, "detail": detail}
            for at, kind, detail in profile.activities
        ],
    }


def turn_failed(replies: list[dict]) -> bool:
    """Whether the harness closed the turn with one of its failure receipts."""
    return any("failure" in reply for reply in replies)


def deployment_answer(events: list[dict], for_event: str) -> dict | None:
    """Return the first successful agent answer to this exact input."""
    return next(iter(successful_replies(events, for_event)), None)


def check_turn_answered(
    url: str, marker: str, turn: TurnReading, asks: int, revision: int
) -> tuple[dict, dict]:
    """Require the turn to have published a revision naming `marker` and answered,
    reading only what the server admitted. A missing publication includes the
    source-validation reading, distinguishing a rejected source from a valid source
    that never names the marker."""
    state, published, replies, answer = turn
    tried = f" to {asks} asks" if asks > 1 else ""
    reading = (state.get("activity") or {}).get("kind") or "no activity"
    said = "; it replied: " + " / ".join(event["text"] for event in replies)
    published = check(
        published,
        f"{url} agent did not publish a revision naming ‘{marker}’{tried}; it "
        f"reached revision "
        f"{state['active']['revision']} from {revision} with the page "
        f"reading {reading}"
        + (said if replies else " and did not reply")
        + f"; source validation: {state['source_error'] or 'no error'}",
    )
    check(
        replies != [],
        f"{url} agent published but did not reply{tried}; the page read {reading}",
    )
    answer = check(
        answer,
        f"{url} agent returned an unexpected reply{tried}{said}",
    )
    return published, answer


def read_state(session: Session) -> dict:
    """Read the page's authoritative state, as this session reaches it."""
    response = answered(
        session.context.request.get(
            session.state_url, headers=session.headers, timeout=120_000
        ),
        session.state_url,
    )
    return response.json()


def release_ask(marker: str) -> str:
    """What the user tells the agent: release `marker` passed its checks. It says what
    happened and leaves how the page shows it to the agent, as a user would, so the
    journey times the agent's own way of working rather than a scripted edit."""
    return (
        f"Release {marker} passed its deployment checks. Record that on the board, "
        "and tell me when it's done."
    )


def board_names_release(html: str, marker: str) -> bool:
    """Read board text and widget labels, excluding release-scoped resource URLs."""
    main = SourceDocument(html).tree.select_one("main")
    return main is not None and (
        marker in main.to_text()
        or any(
            marker in (element.attrs.get("label") or "")
            for element in main.find_all(True)
        )
    )


def ask_to_record(
    session: Session, marker: str, profile: AgentProfile, ask: int
) -> dict:
    """Send one ask through the user's real composer; return its admitted comment."""
    clock = "window.__leafVerifier.startVisibleReplyClock" if ask == 1 else None
    return send_comment(session, release_ask(marker), profile, clock)


def select_passage(page: Page, passage: str) -> None:
    """Triple-click the words of the element `passage` selects, where a user aims:
    the first of its drawn words that nothing covers, which its box's centre may not
    be."""
    page.locator(passage).scroll_into_view_if_needed()
    point = uncovered_word(page, passage)
    point = check(point, f"no word of {passage} is uncovered to select")
    page.mouse.click(*point, click_count=3)


def uncovered_word(page: Page, passage: str) -> list[float] | None:
    """Where the first word of `passage` that nothing covers is drawn, if one is."""
    return page.locator(passage).evaluate(
        """element => {
          const range = element.ownerDocument.createRange();
          range.selectNodeContents(element);
          for (const line of range.getClientRects()) {
            const y = line.top + line.height / 2;
            for (let x = line.left + 4; x < line.right; x += 8) {
              const hit = element.ownerDocument.elementFromPoint(x, y);
              if (hit && element.contains(hit)) return [x, y];
            }
          }
          return null;
        }"""
    )


def write_comment(session: Session, text: str, passage: str | None = None) -> Locator:
    """Write `text`, unsent, and return the box holding it: on the page, in the floating
    panel's field, or on the element with id `passage`, by selecting its words and
    commenting on the selection."""
    page = session.page
    if passage is None:
        # The field writes a page comment while no view stands open over it. A send
        # opens its thread there, the field becoming its reply box, so a later page
        # comment closes that view first.
        if page.locator(".lf-floating-panel[data-open]").count():
            page.locator(".lf-fp-close").click()
        box = page.locator(".lf-fp-field leaf-text")
        box.click()
    else:
        select_passage(page, f"#{passage}")
        page.locator(".lf-fab-input").click()
        box = page.locator(".lf-composer leaf-text")
    box.focus()
    page.keyboard.insert_text(text)
    return box


def send_comment(
    session: Session,
    text: str,
    profile: AgentProfile,
    clock: str | None,
    passage: str | None = None,
) -> dict:
    """Write `text` (`write_comment`), send it, and return the admitted comment."""
    box = write_comment(session, text, passage)
    return send_written(session, box, text, profile, clock)


def send_written(
    session: Session, box: Locator, text: str, profile: AgentProfile, clock: str | None
) -> dict:
    """Send the comment `text` written in `box` and return it, admitted. The send is
    timed from `clock`, a page expression returning the time, where one is given;
    `profile` records it."""
    page, url = session.page, session.url
    box.focus()
    if clock is not None:
        profile.started = time.monotonic()
        profile.visible_reply_started_ms = page.evaluate(clock)
    with page.expect_response(
        lambda response: (
            response.url.split("?")[0].endswith("/api/event")
            and response.request.method == "POST"
        )
    ) as response_info:
        box.press("ControlOrMeta+Enter")
    posted = response_info.value
    check(posted.ok, f"{url} rejected the comment ‘{text}’")
    profile.reference = posted.headers.get("leaf-session-reference")
    profile.acknowledge()
    # Read the admitted event from state rather than the intercepted response body,
    # which Playwright can wait on forever once the page has consumed it.
    accepted = read_state(session)
    profile.observe(accepted)
    assert posted.request.post_data_json is not None
    attempt = posted.request.post_data_json["attempt"]
    comment = next(
        (
            event
            for event in accepted.get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    comment = check(comment, f"{url} did not return the comment ‘{text}’")
    profile.event_ids.append(comment["id"])
    if session.after_post is not None:
        session.after_post(comment)
    return comment


def await_turn(
    end: HttpEnd | BrowserEnd,
    comment: dict,
    revision: int,
    marker: str,
    published: dict | None,
    deadline: float,
    profile: AgentProfile,
) -> TurnReading:
    """Read the page until this ask is answered or nothing is answering it."""
    started = time.monotonic()
    replies: list[dict] = []
    answer = None
    current: dict = {}
    while True:
        current = end.state()
        profile.observe(current)
        replies = [
            event
            for event in current.get("events", [])
            if event.get("kind") == "reply" and event.get("parent") == comment["id"]
        ]
        answer = deployment_answer(current.get("events", []), comment["id"])
        active = current["active"]
        # The turn may publish a checkpoint first, so read the document for the
        # marker rather than taking the first new revision.
        if (
            published is None
            and active["revision"] > revision
            and end.names(active, marker)
        ):
            published = active
        if published is not None and answer is not None:
            break
        # A harness failure receipt closes the turn; otherwise either half of a success
        # can arrive first, so one waits for the other.
        if turn_failed(replies):
            break
        if time.monotonic() >= deadline:
            break
        waited = time.monotonic() - started
        if waited >= TURN_PATIENCE and not still_answering(current, comment["id"]):
            break
        end.pause(2)
    return TurnReading(current, published, replies, answer)


def await_title(end: HttpEnd | BrowserEnd, thread: str, state: dict) -> dict:
    """Read the page until it titles `thread` or `TITLE_PATIENCE` passes; return the
    last reading. The page server names a thread beside the agent's turn rather than
    within it, so the title can land after the reply that ended the turn."""
    deadline = time.monotonic() + TITLE_PATIENCE
    while title(state["events"], thread) is None and time.monotonic() < deadline:
        end.pause(1)
        state = end.state()
    return state


def ask_until_answered(end: HttpEnd | BrowserEnd, marker: str) -> AgentAsks:
    """Ask the agent once, ending on its answer or first failure receipt."""
    state = end.state()
    revision = state["active"]["revision"]
    profile = AgentProfile()
    profile.ask_count = 1
    deadline = time.monotonic() + TURN_LIMIT
    comment = end.ask(marker, profile, 1)
    turn = await_turn(end, comment, revision, marker, None, deadline, profile)
    return AgentAsks(turn, 1, revision, profile)


def open_news(page: Page, thread: str) -> None:
    """Open the news `thread` holds back, if it shows any, as a reader waiting on it
    does: in the floating panel's view of the thread or on its card at its passage.
    The page times what it then shows, so when this runs changes no reading."""
    news = page.locator(
        f':is(.lf-thread[data-id="{thread}"],'
        f' [data-lf-thread-view][data-thread="{thread}"])'
        " .lf-thread-news"
    )
    if news.count() and news.first.is_visible():
        try:
            news.first.click(timeout=1000)
        except PlaywrightTimeout:
            # The notice went, its news shown, between the look and the click.
            pass


def shown_reply(page: Page, answer: dict) -> dict | None:
    """When the page first showed the user `answer`, and by which sign, as the page
    itself recorded it however the journey was occupied then
    (`verify_site_browser.js`), or None where it has not."""
    return page.evaluate(
        "window.__leafVerifier.replyShownAt",
        {"thread": answer["parent"], "id": answer["id"]},
    )


def await_reply_shown(end: BrowserEnd, answer: dict) -> dict:
    """Hear the session until the page shows the user `answer`, opening any news its
    thread holds back, within `VISIBLE_REPLY_PATIENCE`; return when and how. A reply
    its notice showed first is heard a little longer, within
    `VISIBLE_MESSAGE_PATIENCE`, for when its own message came into view."""
    page = end.session.page
    deadline = time.monotonic() + VISIBLE_REPLY_PATIENCE / 1000
    while (shown := shown_reply(page, answer)) is None:
        if time.monotonic() >= deadline:
            debug = page.evaluate("window.__leafVerifier.visibleReplyDebug")
            raise RuntimeError(
                f"{end.url} reply {answer['id']} never showed, its news opened; "
                f"the page reports {json.dumps(debug)}"
            )
        open_news(page, answer["parent"])
        end.pause(0.5)
    if shown["message"] is None:
        deadline = time.monotonic() + VISIBLE_MESSAGE_PATIENCE
        while shown["message"] is None and time.monotonic() < deadline:
            end.pause(0.1)
            next_shown = shown_reply(page, answer)
            assert next_shown is not None
            shown = next_shown
    return shown


def run_journey(end: HttpEnd | BrowserEnd, version: str) -> dict:
    """Tell the agent that release `version` passed its checks and ask it to record
    that, at the user's `end`, then require a published revision naming the release
    and an answer, and in a browser a reload presenting it. Return the journey's
    reading of the ask; a harness's user breaks its reply down once the session
    ends (`User.sample`).

    The page check finds the release's short hash in the authored board markup:
    where on the board the agent records it is the agent's call.
    """
    marker = version[:8]
    opening = end.opening()
    turn, asks, revision, profile = ask_until_answered(end, marker)
    published, answer = check_turn_answered(end.url, marker, turn, asks, revision)
    answered_comment = next(
        event for event in turn.state["events"] if event["id"] == answer["parent"]
    )
    events = await_title(end, answer["parent"], turn.state)["events"]
    comment = end.reading(
        profile, recorded_steps(events, answered_comment, published), answer
    )
    print(json.dumps(comment, indent=2), file=sys.stderr)
    print(
        f"✓ the agent published revision {published['revision']} and replied: "
        f"{answer['text']}",
        file=sys.stderr,
    )
    return {
        "version": version,
        **opening,
        "comment": comment,
        "change": {
            "marker": marker,
            "revision": published["revision"],
            "reply": answer["text"],
        },
        **end.closing(published, answer, marker),
    }


def website_session(
    browser, release: str | None, *, origin: str, direct_agent: bool
) -> tuple[Session, str]:
    """A user's session on the website at `origin`, and the release it serves."""
    context, page, failures, url, state_url, state = agent_session(
        browser, release, origin=origin, direct_agent=direct_agent
    )
    if release is None:
        release = state.get("release")
        if not isinstance(release, str):
            raise RuntimeError(f"{state_url} returned no release")
    # The comment is posted under the layer its own container holds, not the edge's.
    headers = {"Leaf-Layer": state["layer"]["generation"], "Leaf-Release": release}
    after_post = (
        (lambda comment: start_direct_agent(context, url, comment))
        if direct_agent
        else None
    )
    session = Session(
        context, page, failures, url, state_url, state, headers, after_post
    )
    return session, release


class Terminal:
    """A harness session the journey types into as the user at its terminal.

    Every wait in a harness journey goes through `hear`, the release ask's included
    (`Session.pause`), so whatever the user at the terminal answers is answered
    whichever wait meets it, and a session that has gone fails the wait. `records`
    is the session's tool and turn record, stamped `received_at`, which a harness
    that reports it as it goes keeps in `trace`; `approved` holds the
    permission prompts answered since the last step; `running_commands` and `commands` are the shell commands it is
    running and has run, where the harness reports them."""

    def __init__(self) -> None:
        self.trace: list[dict] = []
        self.approved: list[str] = []
        self.running_commands: dict[str, str] = {}
        self.commands: list[str] = []

    def hear(self, seconds: float) -> None:
        """Hear the session for `seconds`."""
        raise NotImplementedError

    def idle(self) -> bool:
        """Whether no turn of the session is running."""
        raise NotImplementedError

    def work(self) -> object:
        """Type the user's own turn (`review_scenario.USER_TURN`) and return once its
        shell command runs, with what names the turn where the harness says."""
        raise NotImplementedError

    def records(self) -> list[dict]:
        """The session's tool and turn record so far."""
        return self.trace

    def failure(self, what: str, limit: float) -> click.ClickException:
        """A wait for `what` that ran out at `limit`, with the session's last
        commands."""
        return click.ClickException(
            f"{what} within {limit:.0f} s. The agent's last commands:\n"
            + "\n".join(f"  {command}" for command in self.commands[-8:])
        )

    def until(
        self, done: Callable[[], object], what: str, limit: float = STEP_LIMIT
    ) -> None:
        """Hear the session until `done`."""
        deadline = time.monotonic() + limit
        while not done():
            if time.monotonic() >= deadline:
                raise self.failure(what, limit)
            self.hear(0.5)

    def settle(self, done: Callable[[], object], what: str) -> None:
        """Hear the session until it is idle with `done` true through QUIET."""
        deadline = time.monotonic() + STEP_LIMIT
        while time.monotonic() < deadline:
            self.hear(0.5)
            if self.idle() and done():
                self.hear(QUIET)
                if self.idle() and done():
                    return
        raise self.failure(what, STEP_LIMIT)

    def page_server_title(self, page: Path, thread: str) -> dict | None:
        """The record `page`'s server made in its diagnostics of the title it
        generated for `thread`, hearing the session for as long as the request may
        take, or None where it made none. A thread's title says nothing of who made
        it; this says the page server did."""
        deadline = time.monotonic() + TITLE_PATIENCE
        while True:
            for record in read_interactions(page, types=("thread_title_generated",)):
                if record.get("thread") == thread:
                    return record
            if time.monotonic() > deadline:
                return None
            self.hear(0.5)

    def await_command(self, text: str, what: str) -> None:
        """Hear the session until it runs a shell command containing `text`."""
        self.until(
            lambda: any(text in command for command in self.running_commands.values()),
            what,
        )


class Isolation(NamedTuple):
    """Where one harness journey's session lives: a temporary `root`, outside any
    repository so the session loads no project instructions, holding its `state`
    home, its cwd `work`, the `page` it serves and the plugin `payload`; and the
    `evidence` directory under `.tmp/journey/` that outlives it."""

    root: Path
    state: Path
    work: Path
    page: Path
    payload: Path
    evidence: Path


def stop_left_running(state: Path) -> list[str]:
    """Stop every process running with `state` as its state home, which only the
    journey's session and what it started have, and name each. One outlives the
    session by design: the sandbox bridge, which Claude Code's hooks start and
    which retires on its next sweep after the last session it serves ends
    (`leaf.bridge`), writing the state home as it goes. Each gets 10 s to exit on
    SIGTERM before SIGKILL. The system hides its own binaries' environments, such
    as `sleep`'s, but not Leaf's Python or a harness's, which are what write the
    state home."""
    left = []
    for process in psutil.process_iter():
        try:
            if process.environ().get("XDG_STATE_HOME") == str(state):
                left.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    commands = []
    for process in left:
        try:
            # A process's arguments can carry a credential, so its name and id say
            # what was stopped.
            commands.append(f"{process.name()} (pid {process.pid})")
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(left, timeout=10)
    for process in alive:
        process.kill()
    psutil.wait_procs(alive, timeout=10)
    return commands


@contextmanager
def isolated(
    target: str, environment: Callable[[Isolation], dict[str, str]]
) -> Generator[Isolation]:
    """A harness journey's isolation, with this process's environment replaced by
    `environment`'s while it lasts, so the page, claim and session records it reads
    in process are the ones the session writes, and every child inherits the
    throwaway home rather than the session running this.

    Every run keeps the page's log in its evidence directory, beside whatever the
    harness module writes there (`trace.jsonl`, its screen or log). Before reading
    the log, it stops every process the session left running (`stop_left_running`),
    since one that writes the state home later would race the copy and the removal.
    The root, which holds a copy of the login, is removed when every check passes
    and kept, with its path printed, when one fails."""
    evidence = run_directory(ROOT / ".tmp" / "journey")
    # Claude Code records trust by the resolved path.
    root = Path(tempfile.mkdtemp(prefix=f"leaf-journey-{target}-")).resolve()
    place = Isolation(
        root, root / "state", root / "work", root / "work" / "page", root / "plugin",
        evidence,
    )  # fmt: skip
    place.work.mkdir()
    extract_payload(place.payload)
    inherited = dict(os.environ)
    replaced = environment(place)
    os.environ.clear()
    os.environ.update(replaced)
    passed = False
    try:
        yield place
        passed = True
    finally:
        run_leaf(ROOT, place.state, "server", "stop", str(place.page))
        if left := stop_left_running(place.state):
            click.echo(
                "Stopped what the session left running:\n"
                + "\n".join(f"  {command}" for command in left),
                err=True,
            )
        for name in ("events.jsonl", "observations.jsonl"):
            if (place.page / name).exists():
                shutil.copy(place.page / name, evidence / name)
        os.environ.clear()
        os.environ.update(inherited)
        if passed:
            shutil.rmtree(root)
        else:
            click.echo(
                f"Kept the session, its page and its state home in {root}", err=True
            )
        click.echo(f"The run's evidence is in {evidence}", err=True)


@contextmanager
def user_at(
    browser, place: Isolation, terminal: Terminal, started: float
) -> Generator[User]:
    """The user at the page `terminal`'s session serves, at the end `browser` gives
    them: in Chrome where there is one (`BrowserEnd`), else posting as the page's tab
    does (`HttpEnd`). Records the setup step, begun at `started`, and keeps the
    session's trace as evidence however the journey ends."""
    record_run_context(place.page, purpose="automated", run=place.evidence)
    server = running_server(place.page)
    assert server is not None
    url = server["url"]
    end = (
        HttpEnd(url, place.page, terminal.hear)
        if browser is None
        else BrowserEnd(local_session(browser, url)._replace(pause=terminal.hear))
    )

    def commands() -> list[dict]:
        claim = page_claim(place.page)
        assert claim is not None
        return [
            command
            for command in read_interactions(place.page, types=("leaf_command",))
            if command["session"] == claim["id"]
        ]

    def forks() -> list[dict]:
        # The reader's own gap records come whatever type is asked for.
        return [
            record
            for record in read_interactions(place.page, types=("fork_reply",))
            if record["type"] == "fork_reply"
        ]

    user = User(
        end,
        checkout_version(),
        lambda: read_events(place.page),
        terminal,
        commands,
        forks,
    )
    try:
        user.passed("setup", started)
        yield user
    finally:
        with (place.evidence / "trace.jsonl").open("w") as trace:
            trace.writelines(json.dumps(record) + "\n" for record in terminal.records())


class HttpEnd:
    """The user's end with no browser: every comment, the release ask's included, is
    posted to the page served at `url` as its tab posts one (`review_scenario.post`),
    and read back from the page's state and directory `page`. This times the agent
    and its harness from the page server's clock alone, which every milestone is on.
    `pause` waits while hearing the session."""

    name = "http"

    def __init__(self, url: str, page: Path, pause: Callable[[float], None]) -> None:
        self.url, self.page, self.pause = url, page, pause

    def state(self) -> dict:
        return PageClient(self.url).state()

    def names(self, active: dict, marker: str) -> bool:
        """Whether the `active` revision names `marker`."""
        return board_names_release(
            revision_path(self.page, active["revision"]).read_text(), marker
        )

    def ask(self, marker: str, profile: AgentProfile, ask: int) -> dict:
        """Post the release ask, the `ask`th time; return its admitted comment."""
        profile.started = time.monotonic()
        step = "release" if ask == 1 else f"release-{ask}"
        posted = post(self.url, step, release_ask(marker))
        state = self.state()
        profile.observe(state)
        profile.event_ids.append(posted)
        return next(event for event in state["events"] if event["id"] == posted)

    def opening(self) -> dict:
        """What the release ask reads before it: nothing, with no page drawn."""
        return {}

    def closing(self, published: dict, answer: dict, marker: str) -> dict:
        """What the release ask reads after it: nothing, with no page to reload."""
        return {}

    def write(self, name: str) -> Callable[[], tuple[str, AgentProfile]]:
        """What posts step `name`'s comment, which takes no writing first."""

        def send() -> tuple[str, AgentProfile]:
            profile = AgentProfile()
            profile.ask_count = 1
            profile.started = time.monotonic()
            profile.event_ids.append(post(self.url, name))
            return profile.event_ids[0], profile

        return send

    def wait(self, comment: str) -> None:
        """Nothing: no page shows the reply."""

    def reading(self, profile: AgentProfile, steps: dict, answer: dict) -> dict:
        """A comment's reading: its milestones on the page server's clock, with
        nothing a browser would have seen."""
        reading = agent_profile(profile, steps)
        del reading["sinceSendMs"], reading["responseShownBy"]
        return reading

    def close(self) -> None:
        """Nothing to close."""


class BrowserEnd:
    """The user's end in Chrome: every comment typed as a user types it, a page comment
    in the floating panel's field and an anchored one on its selected passage, its send and its reply showing timed by the page
    (`shown_reply`), and the release ask's reload checked and profiled. This is the
    whole journey, what the page shows included."""

    name = "browser"

    def __init__(self, session: Session) -> None:
        self.session, self.url = session, session.url
        self.pause = session.pause

    def state(self) -> dict:
        return read_state(self.session)

    def names(self, active: dict, marker: str) -> bool:
        """Whether the served revision's authored board names `marker`."""
        document = self.session.context.request.get(
            urljoin(self.url, active["url"]), timeout=120_000
        )
        return document.ok and board_names_release(document.text(), marker)

    def ask(self, marker: str, profile: AgentProfile, ask: int) -> dict:
        return ask_to_record(self.session, marker, profile, ask)

    def opening(self) -> dict:
        """The page's startup profile as the user found it."""
        return {"page": startup_profile(startup_reading(self.session.page))}

    def closing(self, published: dict, answer: dict, marker: str) -> dict:
        """Require a reload to present the published revision naming `marker`, and
        return the reloaded page's profile."""
        page, url, failures = self.session.page, self.url, self.session.failures
        reloaded = page.reload(wait_until="load", timeout=120_000)
        check(
            reloaded is not None and reloaded.ok,
            f"{url} did not reload after its agent turn",
        )
        await_presentation(page, url, failures, timeout=TURN_PRESENTATION)
        startup = startup_reading(page)
        # Startup can present the offline authored fallback when its first read fails.
        # A later answer brings the revision back, with its own wait and timing.
        # The revision marker advances as the patch begins; its presentation proof
        # must finish before the text below is a reading of that revision.
        followed_at = time.monotonic()
        try:
            page.wait_for_function(
                "window.__leafVerifier.revisionAtLeast",
                arg=published["revision"],
                timeout=TURN_PRESENTATION,
            )
        except PlaywrightTimeout:
            pass
        followed_in = (time.monotonic() - followed_at) * 1000
        # After the wait, so an error on the way there is reported rather than the
        # revision it never reached.
        check(not failures, f"{url} reported browser errors: {said(failures)}")
        shown = page.evaluate("window.__leafVerifier.revision")
        # The page's status separates a page whose first read answered with an old
        # revision from one that presented offline and was never told.
        status = page.evaluate("window.__leafVerifier.status")
        check(
            (shown or "").isdigit() and int(shown) >= published["revision"],
            f"{url} stands on revision {shown} rather than following the published "
            f"{published['revision']}, with its status reading ‘{status}’",
        )
        check(
            page.evaluate(
                "window.__leafVerifier.revisionAtLeast", published["revision"]
            ),
            f"{url} reached revision {shown} but did not finish presenting it, "
            f"with its status reading ‘{status}’",
        )
        # `inner_text` applies the theme's text-transform, so a release recorded in
        # an uppercase eyebrow or panel heading reads `35B36571`. Compare ignoring case.
        rendered = page.locator("main").inner_text()
        check(
            marker.casefold() in rendered.casefold(),
            f"{url} rendered a page that never names ‘{marker}’, which the agent's "
            "published revision did",
        )
        print(
            f"  the reloaded page followed it {followed_in:.0f} ms after presentation",
            file=sys.stderr,
        )
        return {
            "changedPage": {
                **startup_profile(startup),
                "followedRevisionMs": followed_in,
            }
        }

    def write(self, name: str) -> Callable[[], tuple[str, AgentProfile]]:
        """Write step `name`'s comment (`COMMENTS`) on its passage, unsent, as a user
        does before the moment they mean it for; return what sends it."""
        section, text = COMMENTS[name]
        box = write_comment(self.session, text, section)

        def send() -> tuple[str, AgentProfile]:
            profile = AgentProfile()
            profile.ask_count = 1
            comment = send_written(self.session, box, text, profile, "Date.now()")
            return comment["id"], profile

        return send

    def wait(self, comment: str) -> None:
        """Open any news the comment's thread holds back, as a reader waiting on it
        does. The page times what it shows, so when this runs changes no reading."""
        open_news(self.session.page, comment)

    def reading(self, profile: AgentProfile, steps: dict, answer: dict) -> dict:
        """A comment's reading: its milestones on the page server's clock, and from
        its send, its acknowledgement and its reply showing, which must."""
        if profile.visible_reply_by is None:
            profile.show(await_reply_shown(self, answer))
        return agent_profile(profile, steps)

    def close(self) -> None:
        self.session.context.close()


class User:
    """The user across a journey's steps, at one end (`HttpEnd` or `BrowserEnd`):
    the release ask, each later step's comment, and how long each step took. A
    harness module drives the steps and checks them; `events` reads the page's log,
    `commands` the `leaf_command` records Leaf's commands left in the page's diagnostics,
    `forks` the `fork_reply` records its forks left there (`leaf.forks.take`), and
    `terminal` is the session, where the journey runs them."""

    def __init__(
        self,
        end: HttpEnd | BrowserEnd,
        version: str,
        events: Callable[[], list[dict]] | None = None,
        terminal: Terminal | None = None,
        commands: Callable[[], list[dict]] | None = None,
        forks: Callable[[], list[dict]] | None = None,
    ) -> None:
        self.end, self.version = end, version
        self.events, self.terminal, self.commands = events, terminal, commands
        self.forks = forks
        self.records = terminal.records if terminal is not None else None
        self.case = "waiting"
        self.ids: dict[str, str] = {}
        self.profiles: dict[str, AgentProfile] = {}
        self.sent: list[str] = []
        self.steps: list[dict] = []
        self.release_reading: dict = {}

    def release(self) -> None:
        """The ask every target answers, timed (`run_journey`), in the journey's
        `case`: in the working one, while the user's turn runs its command."""
        if self.case == "working":
            assert self.terminal is not None
            self.terminal.work()
        self.release_reading = run_journey(self.end, self.version)
        self.ids["release"] = self.release_reading["comment"]["eventIds"][-1]

    def release_alone(self) -> None:
        """A website's steps: the release ask alone, since only a terminal can start
        a turn or interrupt one."""
        started = time.monotonic()
        self.release()
        self.passed("release", started)

    def comment(self, name: str) -> str:
        """Send step `name`'s comment (`COMMENTS`) on its passage; return its id."""
        return self.write(name)()

    def write(self, name: str) -> Callable[[], str]:
        """Make step `name`'s comment ready to send, as a user writes one before the
        moment they mean it for; return what sends it, which returns its id."""
        send = self.end.write(name)

        def sent() -> str:
            self.ids[name], self.profiles[name] = send()
            self.sent.append(name)
            return self.ids[name]

        return sent

    def answered(self, name: str) -> bool:
        """Whether the agent has answered step `name`'s comment, the user meanwhile
        opening any news its thread holds back where a page shows it."""
        self.end.wait(self.ids[name])
        assert self.events is not None
        return deployment_answer(self.events(), self.ids[name]) is not None

    def fork(self, name: str) -> dict | None:
        """The record of the last fork of the session's conversation that decided on
        step `name`'s comment, if one has."""
        if self.forks is None:
            return None
        return next(
            (
                record
                for record in reversed(self.forks())
                if self.ids[name] in record["inputs"]
            ),
            None,
        )

    def passed(self, name: str, started: float, *details: str) -> None:
        """Record step `name`, begun at `started`, with the comments sent during it
        and the permission prompts the user answered, and print it with `details`. A
        prompt holds the session for as long as it stands, so a step's readings with
        one are not like those without, and say so (`sample`)."""
        approved = self.terminal.approved if self.terminal is not None else []
        seconds = time.monotonic() - started
        step: dict = {"step": name, "seconds": round(seconds, 1), "comments": self.sent}
        if approved:
            step["approved"] = list(approved)
            approved.clear()
        self.steps.append(step)
        timings = [self.timing(sent) for sent in self.sent]
        self.sent = []
        click.echo(
            f"{name}: passed in {seconds:.0f} s"
            + "".join(f"\n  approved: {prompt}" for prompt in step.get("approved", []))
            + "".join(f"\n  {line}" for line in [*timings, *details]),
            err=True,
        )

    def timing(self, name: str) -> str:
        """When step `name`'s comment was picked up and answered, after its
        admission (`recorded_steps`), and what a fork that decided on it did."""
        assert self.events is not None
        events = self.events()
        comment = next(e for e in events if e["id"] == self.ids[name])
        steps = recorded_steps(events, comment, None)
        picked = steps["pickedUp"]
        fork = self.fork(name)
        return (
            f"`{name}` "
            + (
                "never picked up"
                if picked is None
                else f"picked up after {picked:.1f} s"
            )
            + f", answered after {steps['replied']:.1f} s"
            + (f"; {fork_summary(fork)}" if fork is not None else "")
        )

    def sample(self) -> dict:
        """The journey's reading: the user's end, the release ask's, and each step's
        duration and the timings of the comments it sent (`end.reading`), each marked
        with the permission prompts answered during its step. Each reply is broken
        down here, from the session's whole record: the call that replied ends after
        the reply does, and a record read while the session writes it can end in a
        partial line."""
        events = (
            self.events()
            if self.events is not None and (self.profiles or self.records)
            else []
        )

        def replied(name: str, comment: dict, answer: dict) -> dict:
            """What a fork that decided on step `name`'s `comment` did, and where the
            session's reply to it went, from its record. A reply the fork wrote
            took nothing of the session's, which picks the comment up only later."""
            fork = self.fork(name)
            reading: dict[str, dict | None] = (
                {}
                if fork is None
                else {"fork": {key: fork[key] for key in FORK_READING if key in fork}}
            )
            if self.records is not None and (
                fork is None or fork["outcome"] != "reply"
            ):
                assert self.commands is not None
                reading["reply"] = reply_breakdown(
                    self.records(),
                    self.commands(),
                    comment["ts"],
                    pickup_at(events, comment["id"], "opened"),
                    answer["ts"],
                )
            return reading

        comments = {}
        for name, profile in self.profiles.items():
            comment = next(e for e in events if e["id"] == self.ids[name])
            answer = deployment_answer(events, comment["id"])
            answer = check(answer, f"`{name}` has no answer")
            reading = self.end.reading(
                profile, recorded_steps(events, comment, None), answer
            )
            comments[name] = {**reading, **replied(name, comment, answer)}
        release = self.release_reading
        if self.records is not None and "release" in self.ids:
            asked = next(e for e in events if e["id"] == self.ids["release"])
            answer = deployment_answer(events, asked["id"])
            assert answer is not None
            release = {
                **release,
                "comment": {**release["comment"], **replied("release", asked, answer)},
            }
        for step in self.steps:
            for name in step["comments"]:
                if "approved" in step:
                    comments[name]["approved"] = step["approved"]
            if step["step"] == "release" and "approved" in step:
                release = {
                    **release,
                    "comment": {**release["comment"], "approved": step["approved"]},
                }
        steps = [
            {**step, "comments": {name: comments[name] for name in step["comments"]}}
            for step in self.steps
        ]
        return {"userEnd": self.end.name, "case": self.case, **release, "steps": steps}


# What a sample keeps of a fork's `fork_reply` record (`leaf.forks.take`).
FORK_READING = ("outcome", "why", "elapsedMs", "usage")
# The usage counts a fork reports, as a step prints them.
FORK_TOKENS = (
    ("input_tokens", "in"),
    ("output_tokens", "out"),
    ("cache_read_input_tokens", "cache read"),
    ("cache_creation_input_tokens", "cache written"),
)


def fork_summary(record: dict) -> str:
    """A fork's `fork_reply` record as a step prints it: what the fork did, in how
    long, on how many tokens, and why it handed the thread over."""
    usage = record.get("usage") or {}
    tokens = ", ".join(
        f"{usage[key]} {name}" for key, name in FORK_TOKENS if key in usage
    )
    return (
        f"a fork's {record['outcome']}"
        + (f" after {record['elapsedMs']:.0f} ms" if "elapsedMs" in record else "")
        + (f" on {tokens} tokens" if tokens else "")
        + (f": {record['why']}" if "why" in record else "")
    )


def checkout_version() -> str:
    """The commit this working tree's plugin is, marked where the working tree
    differs from it."""
    head = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return working_version(head)


def working_version(commit: str) -> str:
    """`commit`, marked when the working tree's plugin differs from it."""
    changed = subprocess.run(
        ["git", "-C", ROOT, "status", "--porcelain", "--", *PAYLOAD],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return f"{commit}+working-tree" if changed else commit


def local_session(browser, url: str) -> Session:
    """A user's session, in a desktop window, on the page a local server serves at
    its keyed `url`."""
    context = browser.new_context(viewport={"width": DESKTOP[0], "height": DESKTOP[1]})
    page = context.new_page()
    failures = observe_startup(page)
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load")
    await_presentation(page, url, failures)
    state_url = PageClient(url).state_url
    state = answered(context.request.get(state_url), state_url).json()
    return Session(context, page, failures, url, state_url, state, {}, None)


@contextmanager
def target_session(
    browser,
    target: str,
    release: str | None,
    *,
    sandbox: bool,
    preview: bool,
    forks: bool,
) -> Generator[tuple[User, dict, Callable[[], None]]]:
    """The user at the page TARGET answers, what names TARGET in the journey's
    output (`target` the same across runs, as a local server's `origin` is not), and
    the journey's steps."""
    if target in HARNESS_TARGETS:
        named: dict = {"target": target, **HARNESS_TARGETS[target]}
        if target == "claude-code":
            from leaf_dev.journey_claude_code import answering

            harness = answering(browser, sandbox=sandbox, forks=forks)
            named |= {"sandbox": True} if sandbox else {}
            named |= {"forks": True} if forks else {}
        elif target == "pi":
            from leaf_dev.journey_pi import answering

            harness = answering(browser)
        else:
            from leaf_dev.journey_codex import answering

            harness = answering(
                browser, named["transport"], preview=preview, sandbox=sandbox
            )
            named |= {"preview": True} if preview else {}
            named |= {"sandbox": True} if sandbox else {}
        with harness as (user, run):
            yield user, named, run
        return
    if target == "website-adapter":
        serving = local_adapter()
    elif target == "website-worker":
        serving = local_worker()
    else:
        origin = target.rstrip("/")
        session, version = website_session(
            browser, release, origin=origin, direct_agent=False
        )
        user = User(BrowserEnd(session), version)
        yield (
            user,
            {"target": origin, "harness": "website", "origin": origin},
            user.release_alone,
        )
        return
    with serving as hosted:
        origin, built = (
            (hosted.origin, hosted.release)
            if isinstance(hosted, LocalWorker)
            else hosted
        )
        session, version = website_session(
            browser,
            built if target == "website-adapter" else release or built,
            origin=origin,
            direct_agent=target == "website-adapter",
        )
        user = User(BrowserEnd(session), version)
        yield (
            user,
            {"target": target, "harness": "website", "origin": origin},
            user.release_alone,
        )


@click.command()
@click.argument("target")
@click.option(
    "--release",
    help="At an origin, require this release (default: whichever it serves).",
)
@click.option(
    "--sandbox",
    is_flag=True,
    help="On claude-code or a codex target, run the session's shell commands in its "
    "harness's sandbox, configured as the README says.",
)
@click.option(
    "--preview",
    is_flag=True,
    help="On a codex target, serve the page with `leaf-dev preview --user`.",
)
@click.option(
    "--forks",
    is_flag=True,
    help="On claude-code, let forks of the session's conversation answer the user's "
    "thread messages, and run the steps that test them in place of the delivery steps.",
)
@click.option(
    "--case",
    type=click.Choice(CASES),
    default="waiting",
    help="On a harness, whether the release ask reaches it waiting or working on the "
    "user's own turn.",
)
@click.option(
    "--browser/--http",
    default=None,
    help="Where the user is: in Chrome, every comment typed as a user types it and what the "
    "page shows timed (a website's only end), or posting as the page's tab does, with "
    "no browser (a harness's default).",
)
def journey(
    target: str,
    release: str | None,
    sandbox: bool,
    preview: bool,
    forks: bool,
    case: str,
    browser: bool | None,
) -> None:
    """Run the user's journey against TARGET, checking each step, and print its
    timed sample.

    TARGET is `claude-code`, `codex-app-server`, `codex-queue` or `pi` for a session
    of that harness on this working tree, `website-adapter` for the website's adapter
    on this machine, `website-worker` for the built site through the local Worker,
    or a website origin. A harness's user posts its comments over HTTP unless
    `--browser` puts them in Chrome.
    """
    if sandbox and HARNESS_TARGETS.get(target, {}).get("harness") not in (
        "claude-code",
        "codex",
    ):
        raise click.UsageError("--sandbox is an option of claude-code and codex")
    if preview and HARNESS_TARGETS.get(target, {}).get("harness") != "codex":
        raise click.UsageError("--preview is an option of the codex targets")
    if preview and sandbox:
        raise click.UsageError("--preview runs leaf-dev, which a sandbox refuses")
    if forks and target != "claude-code":
        raise click.UsageError("--forks is an option of claude-code")
    website = target not in HARNESS_TARGETS
    if website and case == "working":
        raise click.UsageError("a website's journey has no terminal to start a turn")
    if website and browser is False:
        raise click.UsageError(
            "a website's journey is its page in a browser, so it has no --http"
        )
    with ExitStack() as stack:
        chromium = stack.enter_context(headless_shell()) if website or browser else None
        user, named, run = stack.enter_context(
            target_session(
                chromium,
                target,
                release,
                sandbox=sandbox,
                preview=preview,
                forks=forks,
            )
        )
        user.case = case
        try:
            run()
            sample = {**named, **user.sample()}
        finally:
            user.end.close()
    print(json.dumps(sample, indent=2))
    samples = samples_path()
    samples.parent.mkdir(parents=True, exist_ok=True)
    with samples.open("a") as kept:
        kept.write(
            json.dumps({"at": datetime.now().astimezone().isoformat(), **sample}) + "\n"
        )
    print(f"kept in {samples}", file=sys.stderr)
