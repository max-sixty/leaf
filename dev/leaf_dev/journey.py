"""One user's journey through a Leaf page, run on any harness, each step timed from
the page's own record and checked.

    uv run leaf-dev journey TARGET [--browser | --http] [--release RELEASE]
                                   [--hooks-module] [--preview]

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
wait (`Terminal`), and the user (`User`). `--hooks-module` turns on Claude Code's
opt-in hooks module; `--preview` has Codex serve the page with the canonical
`leaf-dev preview --user`. The journey stops at the first check that fails and keeps
no sample.

Where the user is, every step alike, is the journey's one axis (`User.end`):

- over HTTP (`--http`, a harness's default): no browser starts. Every comment, the
  release ask's included, is posted as the page's tab posts one, on its section
  (`HttpEnd`). This is the journey for the agent and its harness: what each step
  checks, and every milestone a step is timed by, is on the page server's clock in
  the log;
- in Chrome (`--browser`, a website's only end): every comment is typed as a user types it,
  a page comment in the banner's card and an anchored one on its selected passage, each reply's showing is timed by the
  page, and the release ask's reload is checked and profiled (`BrowserEnd`). This is
  the whole journey, what the page shows the user included.

Both ends share every check: the release ask waits on the same turn, title and answer
(`run_journey`), and each end only sends the user's comments and says what it saw of
them (`reading`), the browser alone reloading the page and timing what it shows.

The timings come from where each step happened. The page server records when it
admitted a comment, recorded its pickup, titled its thread, activated the published
revision and admitted the reply; `sinceAdmissionMs` reads those from the comment's
admission, so every target and either end is timed on one clock, the page server's.
In Chrome the browser also sees the POST's answer and the reply showing in Threads,
which the page records itself (`shown_reply`); `sinceSendMs` reads those from the
send. Where the journey runs the agent itself, its record of the session (Claude
Code's transcript, Codex's App Server notifications, Pi's RPC events) also splits the
agent's work from the comment's admission to its reply into delivery (until it is
picked up), model and tool phases (`turn`), so a slow reply shows where it went. The
JSON on stdout carries all of it: the user's end (`userEnd`), `comment` for the
release ask, `steps` for each step's duration and its comments' timings, and the
code version the journey ran. A comment whose step held a permission prompt the user
answered says so (`approved`), since the prompt held the session for as long as it
stood.

A `startup_failed` receipt gets one more ask; any other failure receipt fails on
the first (`worker/README.md` owns that contract).

Each sample is also kept on the machine that ran it (`samples_path`), and
`leaf-dev journey-chart` draws when each milestone came, from the kept samples of
the latest version each target ran at each end, as an `lf-chart` element for a
page.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit

import click
from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.files import revision_path
from leaf.server import running_server
from leaf.tasks import start_reading
from leaf.thread import successful_replies
from playwright.sync_api import BrowserContext, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT
from leaf_dev.arms import PAYLOAD, PageClient, extract_payload, run_directory, run_leaf
from leaf_dev.browser import DESKTOP, chrome
from leaf_dev.review_scenario import COMMENTS, post
from leaf_dev.startup import startup_reading
from leaf_dev.verify_site import (
    agent_session,
    answered,
    await_presentation,
    check,
    local_adapter,
    local_worker,
    observe_startup,
    start_direct_agent,
    startup_profile,
)

# A turn's wait ends at `TURN_PATIENCE` unless the page says a turn is still working on
# the comment, which holds it to `TURN_LIMIT`. `TURN_LIMIT` bounds the whole pass, so
# raising it means raising `publish-site.yaml`'s `timeout-minutes` too.
TURN_PATIENCE = 300
TURN_LIMIT = 600
TURN_ASKS = 2
# The reload after the turn gets this long to present, then as long again to follow
# the published revision: its container may take seconds to answer the first read.
TURN_PRESENTATION = 120_000
# How long Threads gets to draw a reply the container has admitted; the runtime's own
# quiet-stream bound (`SILENCE_MS` in `runtime/state-feed.js`) is the same 30 s.
VISIBLE_REPLY_PATIENCE = 30_000
# How long the page server gets to title the thread after the turn ends: its title
# request's own limit (`TIMEOUT` in `thread_titles.py`).
TITLE_PATIENCE = 60
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


def samples_path() -> Path:
    """Where this machine keeps every sample, one JSON line each, outside any
    checkout so runs from every worktree accumulate. A stopgap until a store CI can
    write to too (`TODO.md`, "Keep the agent journey's samples")."""
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(state) / "leaf-dev" / "journey.jsonl"


class Session(NamedTuple):
    """One user's open page, with what reaching its state takes: `headers` go with
    each state read, and `after_post` runs once a comment is admitted. `pause`
    waits, hearing the answering agent's session where the journey runs it."""

    context: BrowserContext
    page: Page
    failures: list[str]
    url: str
    state_url: str
    state: dict
    headers: dict[str, str]
    after_post: Callable[[dict], None] | None
    pause: Callable[[float], None] = time.sleep


def still_answering(state: dict, event_id: str) -> bool:
    """Whether the page's `activity` says a working turn still owes this comment a
    reply, which a wall clock cannot tell."""
    activity = state.get("activity") or {}
    if activity.get("kind") != "working":
        return False
    return any(
        obligation.get("input") == event_id and not obligation.get("dropped")
        for obligation in activity.get("obligations") or ()
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
        self.activities: list[tuple[float, str, str]] = []
        self.ask_count = 0
        self.reference: str | None = None
        self.event_ids: list[str] = []

    def show(self, shown: dict) -> None:
        """Time the reply to the page's reading of when and how it showed it."""
        self.visible_reply_s = (shown["at"] - self.visible_reply_started_ms) / 1000
        self.visible_reply_by = shown["by"]

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


def instant(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def title(events: list[dict], thread: str) -> str | None:
    """The title `events` give `thread`, if any."""
    return build_threads(events, {}).get(thread, {}).get("title")


def pickup_at(events: list[dict], comment: str, phase: str) -> str | None:
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
            ("published", published and published["activated_at"]),
            ("replied", replied and replied["ts"]),
        )
    }


def turn_phases(
    records: list[dict], admitted: str, picked_up: str | None, replied: str
) -> list[dict]:
    """The agent's work on a comment from its admission to its reply, as consecutive
    phases in milliseconds from the admission: `delivery` until the comment is in the
    agent's context (`picked_up`, its opened pickup), whether that opened a turn or
    entered a running one, then alternating `model` (from the last tool result to the
    next tool call) and `tool` (from that call until every call it started has
    returned), each tool phase naming its calls. A comment that enters a running turn
    while a call is out, as one sent mid-turn does, starts in a tool phase from its
    pickup until those calls return. A record's time is when it was written or heard:
    Claude Code's transcript stamps each record itself, and the journey stamps Codex's
    notifications and Pi's events as it hears them. A comment never picked up has no
    phases."""
    if picked_up is None:
        return []
    start, began, end = instant(admitted), instant(picked_up), instant(replied)
    timed = [
        (instant(record["received_at"]), record)
        for record in records
        if instant(record["received_at"]) <= end
    ]
    phases: list[dict] = []

    def close(phase: str, since: float, until: float, **detail) -> None:
        phases.append(
            {
                "phase": phase,
                "startMs": round((since - start) * 1000),
                "ms": round((until - since) * 1000),
                **detail,
            }
        )

    close("delivery", start, began)
    # The calls still out when the comment was picked up.
    out: dict[str, str] = {}
    for at, record in timed:
        if at > began or record["type"] not in ("assistant", "user"):
            continue
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                out[part["id"]] = part["input"].get("command", part["name"])[:200]
            elif part["type"] == "tool_result":
                out.pop(part["tool_use_id"], None)
    phase = "tool" if out else "model"
    since, pending, calls = began, set(out), list(out.values())
    for at, record in timed:
        if at <= began or record["type"] not in ("assistant", "user"):
            continue
        for part in record["message"]["content"]:
            if part["type"] == "tool_use":
                if phase == "model":
                    close("model", since, at)
                    phase, since, calls = "tool", at, []
                pending.add(part["id"])
                calls.append(part["input"].get("command", part["name"])[:200])
            elif part["type"] == "tool_result" and part["tool_use_id"] in pending:
                pending.remove(part["tool_use_id"])
                if not pending:
                    close("tool", since, at, calls=calls)
                    phase, since = "model", at
    if phase == "tool":
        close("tool", since, end, calls=calls)
    else:
        close("model", since, end)
    return phases


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
        },
        "responseShownBy": profile.visible_reply_by,
        "activity": [
            {"atMs": at * 1000, "kind": kind, "detail": detail}
            for at, kind, detail in profile.activities
        ],
    }


def startup_failed(replies: list[dict]) -> bool:
    """Whether the container settled this ask by reporting a turn that never ran."""
    return any(reply.get("failure") == "startup_failed" for reply in replies)


def turn_failed(replies: list[dict]) -> bool:
    """Whether the harness closed the turn with one of its failure receipts."""
    return any("failure" in reply for reply in replies)


def deployment_answer(events: list[dict], for_event: str) -> dict | None:
    """Return the first successful agent answer to this exact input."""
    return next(iter(successful_replies(events, for_event)), None)


def check_turn_answered(
    url: str, marker: str, turn: TurnReading, asks: int, revision: int
) -> None:
    """Require the turn to have published a revision naming `marker` and answered,
    reading only what the server admitted. A missing publication includes the
    source-validation reading, distinguishing a rejected source from a valid source
    that never names the marker."""
    state, published, replies, answer = turn
    tried = f" to {asks} asks" if asks > 1 else ""
    reading = (state.get("activity") or {}).get("kind") or "no activity"
    said = "; it replied: " + " / ".join(event["text"] for event in replies)
    check(
        published is not None,
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
    check(
        answer is not None,
        f"{url} agent returned an unexpected reply{tried}{said}",
    )


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
    check(point is not None, f"no word of {passage} is uncovered to select")
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
    """Write `text`, unsent, and return the box holding it: on the page, in the page
    comment card under the banner, or on the element with id `passage`, by selecting its words and
    commenting on the selection."""
    page = session.page
    if passage is None:
        # The page comment card under the banner is where a page thread starts; a
        # send leaves it open, so an open card's box is pressed instead.
        box = page.locator(".lf-page-comment-card leaf-text")
        if page.locator(".lf-page-comment-card:popover-open").count():
            box.click()
        else:
            page.locator(".lf-banner-actions > .lf-page-comment").click()
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
    attempt = posted.request.post_data_json["attempt"]
    comment = next(
        (
            event
            for event in accepted.get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    check(comment is not None, f"{url} did not return the comment ‘{text}’")
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
    """Ask the agent to record `marker` until it answers or stops answering.

    A `startup_failed` receipt is retried once while a healthy turn's budget remains;
    any other receipt, or a turn that stops without answering, ends the pass.
    """
    state = end.state()
    published = None
    asks = 0
    profile = AgentProfile()
    deadline = time.monotonic() + TURN_LIMIT
    while True:
        asks += 1
        profile.ask_count = asks
        # A second ask continues the revision the first left, and keeps what it
        # published.
        revision = state["active"]["revision"]
        comment = end.ask(marker, profile, asks)
        state, published, replies, answer = await_turn(
            end, comment, revision, marker, published, deadline, profile
        )
        if answer is not None or not (
            asks < TURN_ASKS
            and startup_failed(replies)
            and deadline - time.monotonic() >= TURN_PATIENCE
        ):
            return AgentAsks(
                TurnReading(state, published, replies, answer),
                asks,
                revision,
                profile,
            )
        print(
            f"↻ {end.url} settled its ask with a startup failure; sending one "
            "new message",
            file=sys.stderr,
        )


def open_news(page: Page, thread: str) -> None:
    """Open the news `thread` holds back, if it shows any, as a reader waiting on it
    does. The page times what it then shows, so when this runs changes no reading."""
    news = page.locator(f'.lf-thread[data-id="{thread}"] .lf-thread-news')
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
        {"thread": answer["parent"], "id": answer["id"], "ts": answer["ts"]},
    )


def await_reply_shown(end: BrowserEnd, answer: dict) -> dict:
    """Hear the session until the page shows the user `answer`, opening any news its
    thread holds back, within `VISIBLE_REPLY_PATIENCE`; return when and how."""
    page = end.session.page
    deadline = time.monotonic() + VISIBLE_REPLY_PATIENCE / 1000
    while (shown := shown_reply(page, answer)) is None:
        if time.monotonic() >= deadline:
            debug = page.evaluate("window.__leafVerifier.visibleReplyDebug")
            raise RuntimeError(
                f"{end.url} reply {answer['id']} never showed in Threads, its "
                f"news opened; the page reports {json.dumps(debug)}"
            )
        open_news(page, answer["parent"])
        end.pause(0.5)
    return shown


def run_journey(
    end: HttpEnd | BrowserEnd,
    version: str,
    records: Callable[[], list[dict]] | None = None,
) -> dict:
    """Tell the agent that release `version` passed its checks and ask it to record
    that, at the user's `end`, then require a published revision naming the release
    and an answer, and in a browser a reload presenting it. Return the journey's
    reading of the ask, its agent's work split into phases where `records` reads the
    session.

    The page check is a containment of the release's short hash anywhere in the
    page: where and how the agent records it is the agent's call.
    """
    marker = version[:8]
    opening = end.opening()
    turn, asks, revision, profile = ask_until_answered(end, marker)
    check_turn_answered(end.url, marker, turn, asks, revision)
    published, answer = turn.published, turn.answer
    answered_comment = next(
        event for event in turn.state["events"] if event["id"] == answer["parent"]
    )
    events = await_title(end, answer["parent"], turn.state)["events"]
    comment = end.reading(
        profile, recorded_steps(events, answered_comment, published), answer
    )
    if records is not None:
        comment["turn"] = turn_phases(
            records(),
            answered_comment["ts"],
            pickup_at(events, answered_comment["id"], "opened"),
            answer["ts"],
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
        check(isinstance(release, str), f"{state_url} returned no release")
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


@contextmanager
def isolated(
    target: str, environment: Callable[[Isolation], dict[str, str]]
) -> Iterator[Isolation]:
    """A harness journey's isolation, with this process's environment replaced by
    `environment`'s while it lasts, so the page, claim and session records it reads
    in process are the ones the session writes, and every child inherits the
    throwaway home rather than the session running this.

    Every run keeps the page's log in its evidence directory, beside whatever the
    harness module writes there (`trace.jsonl`, its screen or log). The root, which
    holds a copy of the login, is removed when every check passes and kept, with its
    path printed, when one fails."""
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
        if (place.page / "events.jsonl").exists():
            shutil.copy(place.page / "events.jsonl", evidence / "events.jsonl")
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
) -> Iterator[User]:
    """The user at the page `terminal`'s session serves, at the end `browser` gives
    them: in Chrome where there is one (`BrowserEnd`), else posting as the page's tab
    does (`HttpEnd`). Records the setup step, begun at `started`, and keeps the
    session's trace as evidence however the journey ends."""
    url = running_server(place.page)["url"]
    end = (
        HttpEnd(url, place.page, terminal.hear)
        if browser is None
        else BrowserEnd(local_session(browser, url)._replace(pause=terminal.hear))
    )
    user = User(end, checkout_version(), lambda: read_events(place.page), terminal)
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
        return marker in revision_path(self.page, active["revision"]).read_text()

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
    in the banner's card and an anchored one on its selected passage, its send and its reply showing timed by the page
    (`shown_reply`), and the release ask's reload checked and profiled. This is the
    whole journey, what the page shows included."""

    name = "browser"

    def __init__(self, session: Session) -> None:
        self.session, self.url = session, session.url
        self.pause = session.pause

    def state(self) -> dict:
        return read_state(self.session)

    def names(self, active: dict, marker: str) -> bool:
        """Whether the `active` revision's document, as the page serves it, names
        `marker`."""
        document = self.session.context.request.get(
            urljoin(self.url, active["url"]), timeout=120_000
        )
        return document.ok and marker in document.text()

    def ask(self, marker: str, profile: AgentProfile, ask: int) -> dict:
        return ask_to_record(self.session, marker, profile, ask)

    def opening(self) -> dict:
        """The page's startup profile as the user found it, and Threads opened."""
        page = startup_profile(startup_reading(self.session.page))
        self.session.page.locator(".lf-threads-toggle").click()
        return {"page": page}

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
        # The runtime presents without waiting for its first read, which is what
        # brings the revision back, so that follow gets its own wait and timing.
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
        check(not failures, f"{url} reported browser errors: {failures}")
        shown = page.evaluate("window.__leafVerifier.revision")
        # The banner separates a page whose first read answered with an old revision
        # from one that presented offline and was never told.
        banner = page.evaluate("window.__leafVerifier.status")
        check(
            (shown or "").isdigit() and int(shown) >= published["revision"],
            f"{url} stands on revision {shown} rather than following the published "
            f"{published['revision']}, with the banner reading ‘{banner}’",
        )
        rendered = page.locator("main").inner_text()
        check(
            marker in rendered,
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
        page = self.session.page
        # Every reply is read in Threads, which the release step's reload may shut.
        if page.locator('.lf-threads-toggle[aria-expanded="false"]').count():
            page.locator(".lf-threads-toggle").click()
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
        its send, its acknowledgement and its reply showing in Threads, which must."""
        if profile.visible_reply_by is None:
            profile.show(await_reply_shown(self, answer))
        return agent_profile(profile, steps)

    def close(self) -> None:
        self.session.context.close()


class User:
    """The user across a journey's steps, at one end (`HttpEnd` or `BrowserEnd`):
    the release ask, each later step's comment, and how long each step took. A
    harness module drives the steps and checks them; `events` reads the page's log
    and `terminal` is the session, where the journey runs both."""

    def __init__(
        self,
        end: HttpEnd | BrowserEnd,
        version: str,
        events: Callable[[], list[dict]] | None = None,
        terminal: Terminal | None = None,
    ) -> None:
        self.end, self.version = end, version
        self.events, self.terminal = events, terminal
        self.records = terminal.records if terminal is not None else None
        self.ids: dict[str, str] = {}
        self.profiles: dict[str, AgentProfile] = {}
        self.sent: list[str] = []
        self.steps: list[dict] = []
        self.release_reading: dict = {}

    def release(self) -> None:
        """The ask every target answers, timed (`run_journey`)."""
        self.release_reading = run_journey(self.end, self.version, self.records)
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
        return deployment_answer(self.events(), self.ids[name]) is not None

    def passed(self, name: str, started: float, *details: str) -> None:
        """Record step `name`, begun at `started`, with the comments sent during it
        and the permission prompts the user answered, and print it with `details`. A
        prompt holds the session for as long as it stands, so a step's readings with
        one are not like those without, and say so (`sample`)."""
        approved = self.terminal.approved if self.terminal is not None else []
        seconds = time.monotonic() - started
        step = {"step": name, "seconds": round(seconds, 1), "comments": self.sent}
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
        admission (`recorded_steps`)."""
        events = self.events()
        comment = next(e for e in events if e["id"] == self.ids[name])
        steps = recorded_steps(events, comment, None)
        picked = steps["pickedUp"]
        return (
            f"`{name}` "
            + (
                "never picked up"
                if picked is None
                else f"picked up after {picked:.1f} s"
            )
            + f", answered after {steps['replied']:.0f} s"
        )

    def sample(self) -> dict:
        """The journey's reading: the user's end, the release ask's, and each step's
        duration and the timings of the comments it sent (`end.reading`), each marked
        with the permission prompts answered during its step."""
        events = self.events() if self.profiles else []
        comments = {}
        for name, profile in self.profiles.items():
            comment = next(e for e in events if e["id"] == self.ids[name])
            answer = deployment_answer(events, comment["id"])
            check(answer is not None, f"`{name}` has no answer")
            reading = self.end.reading(
                profile, recorded_steps(events, comment, None), answer
            )
            if self.records is not None:
                reading["turn"] = turn_phases(
                    self.records(),
                    comment["ts"],
                    pickup_at(events, comment["id"], "opened"),
                    answer["ts"],
                )
            comments[name] = reading
        release = self.release_reading
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
        return {"userEnd": self.end.name, **release, "steps": steps}


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
    its keyed `url`. In the window's width Threads stands beside the page rather than
    over the passages the user selects to comment on."""
    context = browser.new_context(viewport={"width": DESKTOP[0], "height": DESKTOP[1]})
    page = context.new_page()
    failures = observe_startup(page)
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load")
    await_presentation(page, url, failures)
    parts = urlsplit(url)
    token = re.search(r"[?&]t=([^&]+)", url)[1]
    state_url = f"{parts.scheme}://{parts.netloc}/api/state?t={token}"
    state = answered(context.request.get(state_url), state_url).json()
    return Session(context, page, failures, url, state_url, state, {}, None)


@contextmanager
def target_session(
    browser, target: str, release: str | None, *, hooks_module: bool, preview: bool
) -> Iterator[tuple[User, dict, Callable[[], None]]]:
    """The user at the page TARGET answers, what names TARGET in the journey's
    output (`target` the same across runs, as a local server's `origin` is not), and
    the journey's steps."""
    if target in HARNESS_TARGETS:
        named = {"target": target, **HARNESS_TARGETS[target]}
        if target == "claude-code":
            from leaf_dev.journey_claude_code import answering

            harness = answering(browser, hooks_module=hooks_module)
            named |= {"hooksModule": True} if hooks_module else {}
        elif target == "pi":
            from leaf_dev.journey_pi import answering

            harness = answering(browser)
        else:
            from leaf_dev.journey_codex import answering

            harness = answering(browser, named["transport"], preview=preview)
            named |= {"preview": True} if preview else {}
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
            (hosted.origin, hosted.release) if target == "website-worker" else hosted
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
    "--hooks-module",
    is_flag=True,
    help="On claude-code, turn the plugin's hooks module on.",
)
@click.option(
    "--preview",
    is_flag=True,
    help="On a codex target, serve the page with `leaf-dev preview --user`.",
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
    hooks_module: bool,
    preview: bool,
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
    if hooks_module and target != "claude-code":
        raise click.UsageError("--hooks-module is an option of claude-code")
    if preview and HARNESS_TARGETS.get(target, {}).get("harness") != "codex":
        raise click.UsageError("--preview is an option of the codex targets")
    website = target not in HARNESS_TARGETS
    if website and browser is False:
        raise click.UsageError(
            "a website's journey is its page in a browser, so it has no --http"
        )
    with ExitStack() as stack:
        chromium = stack.enter_context(chrome()) if website or browser else None
        user, named, run = stack.enter_context(
            target_session(
                chromium, target, release, hooks_module=hooks_module, preview=preview
            )
        )
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


# Exact-input milestones on the page server's clock, from comment admission.
SIGNS = (
    ("title", "sinceAdmissionMs", "titled", "var(--series-2)"),
    ("picked up", "sinceAdmissionMs", "pickedUp", "var(--series-5)"),
    ("work started", "sinceAdmissionMs", "started", "var(--series-1)"),
    ("progress", "sinceAdmissionMs", "progress", "var(--series-4)"),
    ("reply", "sinceAdmissionMs", "replied", "var(--series-3)"),
)
TARGET_NAMES = {
    "claude-code": "Claude Code",
    "codex-app-server": "Codex App Server",
    "codex-queue": "Codex queue",
    "pi": "Pi",
}
TICKS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500)
# Plot sizes no margin to its labels: about this many px a character at its font.
LABEL_PX = 5.5


def chart_target(sample: dict) -> str:
    """What a chart row names: the target, with the options it ran under and its
    user's end where that is not a browser."""
    return (
        TARGET_NAMES.get(sample["target"], sample["target"])
        + (" with the hooks module" if sample.get("hooksModule") else "")
        + (" through a preview" if sample.get("preview") else "")
        + (" over HTTP" if sample.get("userEnd") == "http" else "")
    )


def chart_rows(samples: list[dict]) -> list[dict]:
    """One dot per sign each sample's release ask saw, for the latest version each
    target ran, with its options. A release ask the user answered a permission
    prompt during has a row of its own, since the prompt held the session for as
    long as it stood. Samples kept before the journey ran its steps (`steps`) are
    left out: their targets had other names, and their Claude Code ran headless."""
    samples = [sample for sample in samples if "steps" in sample]
    latest = {chart_target(sample): sample["version"] for sample in samples}
    rows = []
    for sample in samples:
        name = chart_target(sample)
        if sample["version"] != latest[name]:
            continue
        version = re.sub(r"[0-9a-f]{32,}", lambda sha: sha[0][:8], sample["version"])
        prompted = (
            " after a permission prompt" if sample["comment"].get("approved") else ""
        )
        row = f"{name}{prompted} at {version}"
        for sign, clock, step, _ in SIGNS:
            if (ms := sample["comment"][clock].get(step)) is not None:
                rows.append({"row": row, "sign": sign, "s": round(ms / 1000, 2)})
    return rows


def chart_markup(rows: list[dict]) -> str:
    """An `lf-chart` element drawing `rows` on a log axis of seconds."""
    seconds = [r["s"] for r in rows]
    domain = [min(seconds) / 1.5, max(seconds) * 1.5]
    shown = [entry for entry in SIGNS if any(r["sign"] == entry[0] for r in rows)]
    described = "; ".join(
        f"{row}: "
        + ", ".join(f"{r['sign']} {r['s']} s" for r in rows if r["row"] == row)
        for row in dict.fromkeys(r["row"] for r in rows)
    )
    # Plot's options are JavaScript, so the tick format can be a function: its log
    # axis otherwise labels in SI units, 100m for 0.1 s.
    body = f"""{{
  ariaLabel: {json.dumps(f"Seconds after the comment until each sign. {described}.")},
  x: {{
    type: "log",
    domain: {json.dumps(domain)},
    ticks: {json.dumps([t for t in TICKS if domain[0] <= t <= domain[1]])},
    tickFormat: (d) => String(d),
    grid: true,
    label: "seconds after the comment (log scale)",
  }},
  y: {{label: null}},
  color: {{
    legend: true,
    domain: {json.dumps([sign for sign, *_ in shown])},
    range: {json.dumps([color for *_, color in shown])},
  }},
  symbol: {{domain: {json.dumps([sign for sign, *_ in shown])}}},
  marginLeft: {LABEL_PX * max(len(r["row"]) for r in rows) + 16},
  marks: [
    Plot.dot({json.dumps(rows)}, {{x: "s", y: "row", fill: "sign", symbol: "sign", r: 6}}),
  ],
}}"""
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<lf-chart id="journey-signs" data-height="240"><pre>\n{escaped}\n</pre></lf-chart>'


@click.command("journey-chart")
def journey_chart() -> None:
    """Print an `lf-chart` of recorded delivery and work milestones, for
    the latest code version each target ran in this machine's kept samples."""
    path = samples_path()
    if not path.exists():
        raise click.ClickException(f"no samples kept in {path}; run `leaf-dev journey`")
    lines = path.read_text().splitlines()
    print(chart_markup(chart_rows([json.loads(line) for line in lines])))
