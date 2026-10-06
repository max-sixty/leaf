"""One user's journey through a Leaf page, run on any harness and timed from the
page's own record.

    uv run leaf-dev journey TARGET [--release RELEASE]

The user opens the triage board in Chrome and tells the agent, through the Threads
composer, that a release passed its deployment checks, asking it to record that on
the board. How the page records it is the agent's call, as with a real user's
request; the journey requires only a reply in Threads and a reload presenting a
published revision that names the release. Every target gets the same ask and the
same checks. TARGET names what answers:

- `cc` or `codex`: an isolated Claude Code or Codex session running this working
  tree's plugin, asked to serve the page and handle its comments (`REQUEST`);
- `local`: the website's adapter on this machine, against the host's Codex login;
- `wrangler`: the built site through the local Worker and its page container;
- an origin such as `https://leaf.page`: the deployed website, at `--release` or
  whichever release it serves.

The timings come from where each step happened. The page server records when it
admitted the comment, titled its thread, activated the published revision and
admitted the reply; `sinceAdmissionMs` reads those from the comment's admission, so
every target is timed on one clock, the page server's. The browser alone sees the
POST's answer and the reply showing in Threads; `sinceSendMs` reads those from the
first send. Where the journey runs the agent itself, `cc` or `codex`, its stream
also splits the turn between those two moments into delivery, model and tool phases
(`turn`), so a slow reply shows where it went. The JSON on stdout carries all of it,
with the code version the journey ran.

A `startup_failed` receipt gets one more ask; any other failure receipt fails on
the first (`worker/README.md` owns that contract).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit

import click
from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT
from leaf_dev.arms import (
    PAYLOAD,
    URL,
    LiveChild,
    build_arm,
    run_directory,
    run_leaf,
    scratch,
)
from leaf_dev.browser import chrome
from leaf_dev.review_scenario import REQUEST, prepare
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
# How long a local harness gets to serve the page and start watching it.
SETUP_LIMIT = 600
HARNESSES = ("cc", "codex")


def samples_path() -> Path:
    """Where this machine keeps every sample, one JSON line each, outside any
    checkout so runs from every worktree accumulate. A stopgap until a store CI can
    write to too (`TODO.md`, "Keep the agent journey's samples")."""
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(state) / "leaf-dev" / "journey.jsonl"


class Session(NamedTuple):
    """One user's open page, with what reaching its state takes: `headers` go with
    each state read, and `after_post` runs once a comment is admitted. `stream` is
    the answering agent's stream where the journey runs that agent itself."""

    context: BrowserContext
    page: Page
    failures: list[str]
    url: str
    state_url: str
    state: dict
    headers: dict[str, str]
    after_post: Callable[[dict], None] | None
    stream: Path | None = None


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
    acknowledgement, the page's activity, when its thread first showed the agent on
    it, and when the reply showed, all from the first send."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.visible_reply_started_ms: float | None = None
        self.acknowledged: list[float] = []
        self.work_visible_s: float | None = None
        self.visible_reply_s: float | None = None
        self.activities: list[tuple[float, str, str]] = []
        self.ask_count = 0
        self.reference: str | None = None
        self.event_ids: list[str] = []

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


def recorded_steps(events: list[dict], comment: dict, published: dict) -> dict:
    """Seconds after `comment`'s admission at which the page server titled its
    thread, activated the `published` revision and admitted the answer, or None for
    a step it never reached."""
    admitted = instant(comment["ts"])
    thread = comment["id"]
    titled = next(
        (
            e["ts"]
            for e in events
            if e["kind"] == "thread_title" and e["thread"] == thread
        ),
        None,
    )
    replied = next(
        (
            e["ts"]
            for e in events
            if e["kind"] == "reply" and e.get("parent") == thread and "failure" not in e
        ),
        None,
    )
    return {
        step: None if at is None else round(instant(at) - admitted, 3)
        for step, at in (
            ("titled", titled),
            ("published", published["activated_at"]),
            ("replied", replied),
        )
    }


def turn_phases(records: list[dict], admitted: str, replied: str) -> list[dict]:
    """The agent's turn from the comment's admission to its reply, as consecutive
    phases in milliseconds from the admission: `delivery` until the turn starts (its
    `init`, or the user record carrying the delivery), then alternating `model`
    (from the last tool result to the next tool call) and `tool` (from that call
    until every call it started has returned), each tool phase naming its calls.
    Times are when the journey received each stream record."""
    start, end = instant(admitted), instant(replied)
    timed = [
        (instant(record["received_at"]), record)
        for record in records
        if start <= instant(record["received_at"]) <= end
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

    began = next(
        at
        for at, record in timed
        if record["type"] == "user" or record.get("subtype") == "init"
    )
    close("delivery", start, began)
    phase, since, pending, calls = "model", began, set(), []
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
            "workVisible": ms(profile.work_visible_s),
            "responseVisible": ms(profile.visible_reply_s),
        },
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


def deployment_answer(replies: list[dict]) -> dict | None:
    """Return a real agent reply rather than a harness-generated failure receipt."""
    return next((reply for reply in replies if "failure" not in reply), None)


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


def ask_to_record(
    session: Session, marker: str, profile: AgentProfile, ask: int
) -> dict:
    """Send one ask through the user's real composer; return its admitted comment.

    The ask says what happened and leaves how the page shows it to the agent, as a
    user would, so the journey times the agent's own way of working rather than a
    scripted edit."""
    page, url = session.page, session.url
    text = (
        f"Release {marker} passed its deployment checks. Record that on the board, "
        "and tell me when it's done."
    )
    box = page.locator(".lf-general leaf-text")
    box.focus()
    page.keyboard.insert_text(text)
    if ask == 1:
        profile.started = time.monotonic()
        profile.visible_reply_started_ms = page.evaluate(
            "window.__leafVerifier.startVisibleReplyClock"
        )
    with page.expect_response(
        lambda response: (
            response.url.split("?")[0].endswith("/api/event")
            and response.request.method == "POST"
        )
    ) as response_info:
        box.press("ControlOrMeta+Enter")
    posted = response_info.value
    check(posted.ok, f"{url} rejected its journey comment")
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
    check(comment is not None, f"{url} did not return its journey comment")
    profile.event_ids.append(comment["id"])
    if session.after_post is not None:
        session.after_post(comment)
    return comment


def await_turn(
    session: Session,
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
        current = read_state(session)
        profile.observe(current)
        replies = [
            event
            for event in current.get("events", [])
            if event.get("kind") == "reply" and event.get("parent") == comment["id"]
        ]
        answer = deployment_answer(replies)
        active = current["active"]
        if published is None and active["revision"] > revision:
            # The turn may publish a checkpoint first, so read the document for the
            # marker rather than taking the first new revision.
            document = session.context.request.get(
                urljoin(session.url, active["url"]), timeout=120_000
            )
            if document.ok and marker in document.text():
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
        time.sleep(2)
    return TurnReading(current, published, replies, answer)


def titled(events: list[dict], thread: str) -> bool:
    return any(e["kind"] == "thread_title" and e["thread"] == thread for e in events)


def await_title(session: Session, thread: str, state: dict) -> dict:
    """Read the page until it titles `thread` or `TITLE_PATIENCE` passes; return the
    last reading. The page server names a thread beside the agent's turn rather than
    within it, so the title can land after the reply that ended the turn."""
    deadline = time.monotonic() + TITLE_PATIENCE
    while not titled(state["events"], thread) and time.monotonic() < deadline:
        time.sleep(1)
        state = read_state(session)
    return state


def ask_until_answered(session: Session, marker: str) -> AgentAsks:
    """Ask the agent to record `marker` until it answers or stops answering.

    A `startup_failed` receipt is retried once while a healthy turn's budget remains;
    any other receipt, or a turn that stops without answering, ends the pass.
    """
    state = session.state
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
        comment = ask_to_record(session, marker, profile, asks)
        state, published, replies, answer = await_turn(
            session, comment, revision, marker, published, deadline, profile
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
            f"↻ {session.url} settled its ask with a startup failure; sending one "
            "new message",
            file=sys.stderr,
        )


def wait_for_visible_reply(page, parent: str, answer_id: str) -> bool:
    """Open held news until the admitted reply is seen within one bounded wait.

    The browser may hold a stream update when the server has already admitted its
    final answer. Opening that notice before the final reading arrives can leave a
    second notice for the answer, so one click does not settle the observation.
    """
    deadline = perf_counter() + VISIBLE_REPLY_PATIENCE / 1000
    while True:
        remaining = max(1, round((deadline - perf_counter()) * 1000))
        if perf_counter() >= deadline:
            return False
        try:
            page.wait_for_function(
                """({parent, id}) => window.__leafVerifier.visibleReplyRecorded(id) ||
                  [...document.querySelectorAll('.lf-threads > .lf-thread')].some(
                    thread => thread.dataset.id === parent &&
                      [...thread.querySelectorAll('.lf-thread-news')].some(
                        notice => notice.checkVisibility()))""",
                arg={"parent": parent, "id": answer_id},
                timeout=remaining,
            )
            if page.evaluate(
                "id => window.__leafVerifier.visibleReplyRecorded(id)", answer_id
            ):
                return True
            page.locator(
                f'.lf-threads > .lf-thread[data-id="{parent}"] .lf-thread-news'
            ).click(timeout=remaining)
        except PlaywrightTimeout:
            return False


def run_journey(session: Session, version: str) -> dict:
    """Tell the agent behind `session` that release `version` passed its checks and
    ask it to record that, then require a reply in Threads and a reload presenting a
    published revision that names the release. Return the journey's profile.

    The page check is a containment of the release's short hash anywhere in the
    page: where and how the agent records it is the agent's call.
    """
    page, url = session.page, session.url
    initial_startup = startup_reading(page)
    marker = version[:8]
    page.locator(".lf-threads-toggle").click()
    turn, asks, revision, profile = ask_until_answered(session, marker)
    check_turn_answered(url, marker, turn, asks, revision)
    published, answer = turn.published, turn.answer
    answered_comment = next(
        event for event in turn.state["events"] if event["id"] == answer["parent"]
    )
    events = await_title(session, answer["parent"], turn.state)["events"]
    steps = recorded_steps(events, answered_comment, published)
    reply_visible = wait_for_visible_reply(page, answer["parent"], answer["id"])
    visible_reply_at = page.evaluate(
        "id => window.__leafVerifier.visibleReplyAt(id)", answer["id"]
    )
    if visible_reply_at is not None:
        profile.visible_reply_s = (
            visible_reply_at - profile.visible_reply_started_ms
        ) / 1000
    # Read before the reload below, which starts a document of its own.
    work_visible_at = page.evaluate(
        "thread => window.__leafVerifier.workVisibleAt(thread)", answer["parent"]
    )
    if work_visible_at is not None:
        profile.work_visible_s = (
            work_visible_at - profile.visible_reply_started_ms
        ) / 1000
    comment = agent_profile(profile, steps)
    if session.stream is not None:
        comment["turn"] = turn_phases(
            [json.loads(line) for line in session.stream.read_text().splitlines()],
            answered_comment["ts"],
            answer["ts"],
        )
    print(json.dumps(comment, indent=2), file=sys.stderr)
    if not reply_visible or visible_reply_at is None:
        debug = page.evaluate("window.__leafVerifier.visibleReplyDebug")
        raise RuntimeError(
            f"{url} reply never became visible in Threads after opening its "
            f"held news; the answer was read out of "
            f"{turn.state['reading']}, and the page reports {json.dumps(debug)}"
        )
    reloaded = page.reload(wait_until="load", timeout=120_000)
    check(
        reloaded is not None and reloaded.ok,
        f"{url} did not reload after its agent turn",
    )
    await_presentation(page, url, session.failures, timeout=TURN_PRESENTATION)
    startup = startup_reading(page)
    # The runtime presents without waiting for its first read, which is what brings
    # the revision back, so that follow gets its own wait and its own timing.
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
    check(not session.failures, f"{url} reported browser errors: {session.failures}")
    shown = page.evaluate("window.__leafVerifier.revision")
    # The banner separates a page whose first read answered with an old revision from
    # one that presented offline and was never told.
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
        f"✓ the agent published revision {published['revision']} and replied: "
        f"{answer['text']}; the reloaded page followed it {followed_in:.0f} ms "
        "after presentation",
        file=sys.stderr,
    )
    return {
        "version": version,
        "page": startup_profile(initial_startup),
        "comment": comment,
        "change": {
            "marker": marker,
            "revision": published["revision"],
            "reply": answer["text"],
        },
        "changedPage": {
            **startup_profile(startup),
            "followedRevisionMs": followed_in,
        },
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


@contextmanager
def harness_session(browser, harness: str) -> Iterator[tuple[Session, str]]:
    """A user's session on a page an isolated `harness` session serves and watches,
    running this working tree's plugin, and the version that plugin is.

    The page is the triage board under a state home of its own (`review_scenario`),
    in a scratch directory outside the repository, so the session reads none of its
    instructions. The harness's stream and stderr, and the page's event log, stay in
    a run directory under `.tmp/journey/`; the scratch directory, which holds a copy
    of the login, is removed. The first comment goes out once the setup turn has
    ended and the page reports a watcher listening."""
    run = run_directory(ROOT / ".tmp" / "journey")
    arm, state, work = run / "arm", run / "state", scratch()
    page_dir = work / "page"
    version = working_version(build_arm(None, arm))
    prepare(arm, state, page_dir)
    found: dict[str, str] = {}
    setup_ended = threading.Event()
    with (
        LiveChild(
            work,
            REQUEST,
            "--plugin-dir",
            str(arm),
            stderr=run / "stderr.txt",
            limit=SETUP_LIMIT + TURN_LIMIT,
            timed_out=run / "timed-out",
            dirs=[arm],
            env={"XDG_STATE_HOME": str(state)},
            harness=harness,
        ) as child,
        (run / "stream.jsonl").open("w") as stream,
    ):

        def record() -> None:
            for line in child.records():
                stream.write(json.dumps(line) + "\n")
                stream.flush()
                if "url" not in found and (served := URL.search(json.dumps(line))):
                    found["url"] = served[0]
                if line.get("type") == "result":
                    setup_ended.set()

        reader = threading.Thread(target=record, daemon=True)
        reader.start()
        deadline = time.monotonic() + SETUP_LIMIT
        try:
            while not (
                setup_ended.is_set()
                and "url" in found
                and page_state(arm, state, page_dir)["listening"]
            ):
                check(
                    reader.is_alive() and time.monotonic() < deadline,
                    f"the {harness} session stopped or ran past {SETUP_LIMIT} s "
                    "before its page had a watcher listening; its stream is "
                    f"{run / 'stream.jsonl'}",
                )
                time.sleep(1)
            session = local_session(browser, found["url"])
            yield session._replace(stream=run / "stream.jsonl"), version
        finally:
            child.close()
            # A turn in progress ends on its own once stdin closes; the context's
            # exit kills whatever outlasts this.
            reader.join(60)
            run_leaf(arm, state, "server", "stop", str(page_dir))
            shutil.copy(page_dir / "events.jsonl", run / "events.jsonl")
            for scratch_dir in (work, work.with_name(f"{work.name}-home")):
                shutil.rmtree(scratch_dir, ignore_errors=True)


def working_version(commit: str) -> str:
    """`commit`, marked when the working tree's plugin differs from it."""
    changed = subprocess.run(
        ["git", "-C", ROOT, "status", "--porcelain", "--", *PAYLOAD],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return f"{commit}+working-tree" if changed else commit


def page_state(arm: Path, state: Path, page_dir: Path) -> dict:
    return json.loads(
        run_leaf(arm, state, "page", "state", str(page_dir), check=True).stdout
    )


def local_session(browser, url: str) -> Session:
    """A user's session on the page a local server serves at its keyed `url`."""
    context = browser.new_context()
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
    browser, target: str, release: str | None
) -> Iterator[tuple[Session, str, dict]]:
    """A user's session on the page TARGET answers, the code version answering it,
    and what names TARGET in the journey's output."""
    if target in HARNESSES:
        with harness_session(browser, target) as (session, version):
            yield session, version, {"harness": target}
    elif target == "local":
        with local_adapter() as (origin, built):
            session, version = website_session(
                browser, built, origin=origin, direct_agent=True
            )
            yield session, version, {"harness": "website", "origin": origin}
    elif target == "wrangler":
        with local_worker() as (origin, built):
            session, version = website_session(
                browser, release or built, origin=origin, direct_agent=False
            )
            yield session, version, {"harness": "website", "origin": origin}
    else:
        origin = target.rstrip("/")
        session, version = website_session(
            browser, release, origin=origin, direct_agent=False
        )
        yield session, version, {"harness": "website", "origin": origin}


@click.command()
@click.argument("target")
@click.option(
    "--release",
    help="At an origin, require this release (default: whichever it serves).",
)
def journey(target: str, release: str | None) -> None:
    """Run the user's journey against TARGET and print its timed profile.

    TARGET is `cc` or `codex` for a session of that harness on this working tree,
    `local` for the website's adapter on this machine, `wrangler` for the built site
    through the local Worker, or a website origin.
    """
    with (
        chrome() as browser,
        target_session(browser, target, release) as (session, version, named),
    ):
        try:
            result = run_journey(session, version)
        finally:
            session.context.close()
    sample = {**named, **result}
    print(json.dumps(sample, indent=2))
    samples = samples_path()
    samples.parent.mkdir(parents=True, exist_ok=True)
    with samples.open("a") as kept:
        kept.write(
            json.dumps({"at": datetime.now().astimezone().isoformat(), **sample}) + "\n"
        )
    print(f"kept in {samples}", file=sys.stderr)
