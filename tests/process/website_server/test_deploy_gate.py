"""How the deploy gate's agent pass reads a deployed page: activating a rolling-out
release, waiting on a hosted turn, and naming why it failed."""

import itertools
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import leaf_website as website_server
import pytest
from click.testing import CliRunner
from interact_support import PAGE, STATED_TIMEOUT
from interact_support import append_carried_log_record as append_event
from leaf.event_log import read_events
from leaf.state import session_record
from leaf_dev import startup
from leaf_dev.commands import journey, verify_site

from process.website_server import (
    ROOT,
    TURN_LOG,
    _Read,
    accept_in_turn,
)


def test_a_turn_that_never_answered_is_reported_before_the_threads_panel():
    """The deployment gate names the turn it read, not the panel it looked at.

    A hosted turn that publishes nothing and replies nothing leaves Threads with no
    reply to draw, so the panel reading is a symptom. The complaint has to carry the
    revision the page reached, the activity it stood under, and the receipts it
    collected, because that reading is the only account of why the turn stopped.
    """
    stalled = journey.TurnReading(
        {
            "active": {"revision": 1},
            "activity": {"kind": "answering"},
            "source_error": None,
        },
        None,
        [],
        None,
    )
    with pytest.raises(RuntimeError) as stopped:
        journey.check_turn_answered(
            "https://leaf.page/examples/triage-board/",
            "446b8fe9",
            stalled,
            1,
            1,
        )
    assert str(stopped.value) == (
        "https://leaf.page/examples/triage-board/ agent did not publish a revision "
        "naming ‘446b8fe9’; it reached revision 1 from 1 "
        "with the page reading answering and did not reply; source validation: no error"
    )

    answered = journey.TurnReading(
        {
            "active": {"revision": 2},
            "activity": {"kind": "listening"},
            "source_error": None,
        },
        {"revision": 2},
        [{"text": "deployment verified"}],
        {"text": "deployment verified"},
    )
    journey.check_turn_answered(
        "https://leaf.page/examples/triage-board/",
        "446b8fe9",
        answered,
        1,
        1,
    )


@pytest.mark.parametrize("invalid_source", [False, True])
def test_a_missing_publication_reports_the_real_source_validation_reading(
    page_dir, invalid_source
):
    """A success reply cannot hide a rejected source or an unchanged valid one."""
    state_service = website_server.PageStateService(page_dir)
    revision = state_service.page_state()["active"]["revision"]
    comment = append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "Change the heading"}
    )
    reply = append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "text": "deployment verified",
        },
    )
    if invalid_source:
        (page_dir / "index.html").write_text(PAGE.replace("</section>", ""))
    state = state_service.page_state()
    assert state["active"]["revision"] == revision
    assert (state["source_error"] is not None) == invalid_source

    with pytest.raises(RuntimeError) as stopped:
        journey.check_turn_answered(
            "https://leaf.page/examples/triage-board/",
            "446b8fe9",
            journey.TurnReading(state, None, [reply], reply),
            1,
            revision,
        )
    assert str(stopped.value) == (
        "https://leaf.page/examples/triage-board/ agent did not publish a revision "
        f"naming ‘446b8fe9’; it reached revision {revision} from {revision} "
        f"with the page reading {state['activity']['kind']}; it replied: deployment verified"
        f"; source validation: {state['source_error'] or 'no error'}"
    )


def test_local_verification_settles_host_network(monkeypatch):
    @contextmanager
    def worker():
        yield verify_site.LocalWorker(
            "http://127.0.0.1:8787", "release", "test-worker", ROOT / ".tmp"
        )

    attempts = []

    def verify(origin, release, *, settle_after_activation=None, worker=None):
        assert worker.origin == origin
        attempts.append(settle_after_activation)
        raise RuntimeError("page did not present: net::ERR_NETWORK_CHANGED")

    monkeypatch.setattr(verify_site, "built_release", lambda: "release")
    monkeypatch.setattr(verify_site, "local_worker", worker)
    monkeypatch.setattr(verify_site, "run_verification", verify)

    result = CliRunner().invoke(verify_site.verify_site, ["website-worker"])

    assert isinstance(result.exception, RuntimeError)
    assert attempts == [verify_site.wait_for_host_network]


def test_host_network_waits_for_addresses_to_stop_changing(monkeypatch):
    now = [0.0]
    readings = itertools.chain(["before", "before"], itertools.repeat("after"))
    monkeypatch.setattr(verify_site.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        verify_site.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds)
    )
    monkeypatch.setattr(verify_site, "host_addresses", lambda: next(readings))

    verify_site.wait_for_host_network()

    # Quiet for 2.5 s from the change at 0.2 s.
    assert now[0] > 2.6


def test_a_refused_answer_carries_what_the_server_said_about_it():
    """A status alone cannot separate one 500 from another, so the body travels with
    it, bounded so a page of HTML served by mistake does not become the run log."""
    url = "https://leaf.page/examples/triage-board/api/state"
    assert verify_site.answered(_answered(200), url).status == 200

    fault = json.dumps({"error": "KeyError: 'browser'"})
    with pytest.raises(RuntimeError) as faulted:
        verify_site.answered(_answered(500, body=fault), url)
    assert str(faulted.value) == f"{url} returned 500: {fault}"

    with pytest.raises(RuntimeError) as refused:
        verify_site.answered(_answered(502, body="b" * 4000), url)
    assert len(str(refused.value)) < len(url) + 600


def test_the_deploy_gate_waits_on_the_page_rather_than_its_own_clock(page_dir):
    """A hosted turn's pace is the model's, so the wait reads the page's own account.

    `publish-site` failed three deployments in one morning with `agent published but
    did not reply` — a turn that had edited the page and was still working when the
    gate's fixed five minutes ran out. The gate now extends its wait only while the
    page still names an outstanding obligation and a turn on it, so a slow turn is
    given the time and a settled one ends the wait whatever the clock says.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    accept_in_turn("hosted-thread")

    handling = website_server.full_state(page_dir, read_events(page_dir))
    assert handling["activity"]["kind"] == "working"
    assert journey.still_answering(handling, comment["id"])
    # Another page's comment is not this gate's turn, whatever this page is doing.
    assert not journey.still_answering(handling, "another-event")

    website_server.WebsiteCodexHarness("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        {"id": "app-server-turn", "status": "completed", "error": None},
        expected=session_record("hosted-thread"),
    )

    stopped = website_server.full_state(page_dir, read_events(page_dir))
    assert [
        obligation["input"] for obligation in stopped["activity"]["obligations"]
    ] == [comment["id"]]
    assert not journey.still_answering(stopped, comment["id"])


def test_the_deploy_gate_stops_waiting_on_a_page_with_no_agent_on_the_comment():
    """The other half of the same reading: nothing is coming, so do not wait it out.

    A container that dropped its session leaves the obligation open with no turn
    behind it. Extending the wait there would spend the step's whole budget to raise
    the failure it could already raise.
    """
    obligation = {"input": "comment-id", "dropped": False}
    for kind in ("away", "unheld", "stalled", "closed", "listening"):
        state = {"activity": {"kind": kind, "obligations": [obligation]}}
        assert not journey.still_answering(state, "comment-id")
    dropped = {
        "activity": {
            "kind": "working",
            "obligations": [{"input": "comment-id", "dropped": True}],
        }
    }
    assert not journey.still_answering(dropped, "comment-id")
    assert not journey.still_answering({}, "comment-id")


@pytest.mark.parametrize("failure", ["startup_failed", "rate_limited"])
def test_the_deploy_gate_reads_a_durable_harness_failure(page_dir, failure):
    from leaf.event_contracts import event_record_error
    from leaf.registry.storage import load_registry

    harness = website_server.WebsiteCodexHarness("codex")
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    reply = harness.failure_receipt(page_dir, comment["id"], failure)
    state = website_server.full_state(page_dir, read_events(page_dir))
    replies = [event for event in state["events"] if event["kind"] == "reply"]
    assert [event["id"] for event in replies] == [reply["id"]]
    contract = load_registry(page_dir)["$events"]["kinds"]["reply"]
    assert event_record_error(contract, replies[0]) is None
    assert journey.turn_failed(replies)
    assert journey.startup_failed(replies) == (failure == "startup_failed")
    assert journey.deployment_answer(replies, comment["id"]) is None
    assert not state["activity"]["obligations"]
    assert harness.attach(page_dir, comment["id"]) is None


class _PostedHeaders(_Read):
    """An intercepted browser POST whose body must remain the browser's to consume."""

    def json(self) -> dict:
        raise AssertionError("the verifier re-read the browser's POST response body")


class _StateReads:
    """One Playwright request context standing in for a page that is being read."""

    def __init__(self, states: list[dict]):
        self.states = states
        self.reads = 0
        self.request = self

    def get(self, url: str, **kwargs):
        state = self.states[min(self.reads, len(self.states) - 1)]
        self.reads += 1
        return _Read(state)


class _FailedFirstTurn:
    """A deployed page whose first startup fails and whose second ask succeeds."""

    def __init__(self, recorded: str, failure: str = "startup_failed"):
        self.failure = failure
        self.recorded = recorded
        self.request = self
        self.keyboard = self
        self.comments: list[dict] = []
        self.draft = ""
        self.last_response = None

    def locator(self, selector: str):
        assert selector in {
            ".lf-floating-panel[data-open]",
            ".lf-fp-close",
            ".lf-fp-field leaf-text",
        }
        return self

    def count(self) -> int:
        """A send opens its thread over the panel's field, which the next ask
        closes."""
        return int(bool(self.comments))

    def click(self) -> None:
        pass

    def focus(self) -> None:
        pass

    def insert_text(self, text: str) -> None:
        self.draft = text

    def evaluate(self, script: str) -> float:
        assert script == "window.__leafVerifier.startVisibleReplyClock"
        return 100.0

    def press(self, key: str) -> None:
        assert key == "ControlOrMeta+Enter"
        attempt = f"attempt-{len(self.comments) + 1}"
        self.last_response = self.post(
            "https://leaf.page/examples/triage-board/api/event",
            {
                "kind": "comment",
                "revision": 1,
                "text": self.draft,
                "attempt": attempt,
            },
        )

    def expect_response(self, predicate):
        owner = self

        class ResponseInfo:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                assert predicate(owner.last_response)

            @property
            def value(self):
                return owner.last_response

        return ResponseInfo()

    def post(self, url: str, data: dict, **kwargs) -> _Read:
        comment = {
            "kind": "comment",
            "author": "user",
            "id": f"comment-{len(self.comments) + 1}",
            "attempt": data["attempt"],
            "revision": data["revision"],
        }
        self.comments.append(comment)
        request = SimpleNamespace(method="POST", post_data_json=data)
        return _PostedHeaders(
            {"state": {"events": [comment]}},
            url=url,
            request=request,
        )

    def get(self, url: str, **kwargs) -> _Read:
        if url.endswith("/api/state"):
            return _Read(self.state())
        return _Read({}, f"<main><h1>{self.recorded}</h1></main>")

    def state(self) -> dict:
        events = [
            *self.comments,
            {
                "kind": "reply",
                "parent": "comment-1",
                "author": "agent",
                "responds": "comment-1",
                "text": "The harness could not start this task.",
                "failure": self.failure,
            },
        ]
        if len(self.comments) < 2:
            return {
                "active": {"revision": 1, "url": "revisions/1.html"},
                "activity": {"kind": "away", "obligations": []},
                "events": events,
            }
        events.append(
            {
                "kind": "reply",
                "author": "agent",
                "parent": "comment-2",
                "responds": "comment-2",
                "text": "deployment verified",
            }
        )
        return {
            "active": {"revision": 2, "url": "revisions/2.html"},
            "activity": {"kind": "away", "obligations": []},
            "events": events,
        }


@pytest.mark.parametrize("failure", ["startup_failed", "rate_limited"])
def test_the_deploy_gate_retries_only_startup_failures(failure):
    """A startup retry gets a fresh attempt; a rate limit ends the pass immediately."""
    context = _FailedFirstTurn("Deployment abcd1234 verified", failure)
    session = journey.Session(
        context,
        context,
        [],
        "https://leaf.page/examples/triage-board/",
        "https://leaf.page/examples/triage-board/api/state",
        {"active": {"revision": 1, "url": "revisions/1.html"}},
        {"Leaf-Layer": "layer", "Leaf-Release": "release"},
        None,
    )
    asked = journey.ask_until_answered(journey.BrowserEnd(session), "abcd1234")
    if failure == "rate_limited":
        assert asked.asks == 1
        assert asked.turn.answer is None
        assert len(context.comments) == 1
        return
    assert asked.asks == 2
    assert asked.turn.answer["text"] == "deployment verified"
    assert asked.turn.published["revision"] == 2
    first, second = context.comments
    assert first["attempt"] != second["attempt"]
    # The second ask continues the page the first turn left rather than an older one.
    assert second["revision"] == 1


def test_the_deploy_gate_reads_outcomes_independently_of_reply_wording():
    """`failure` decides, so the wording may change and old pages still read right."""
    for text in (
        "deployment verified",
        *website_server.FAILURE_RECEIPTS.values(),
        # Wordings this adapter has already written into pages that outlive it.
        "I couldn’t generate a reply just now. Please send a new message to try again.",
        "I finished without posting a reply. Please send a new message to try again.",
        "This public demo is busy right now. Please wait a minute, then send a new message.",
    ):
        answer = {
            "kind": "reply",
            "author": "agent",
            "parent": "root",
            "responds": "comment",
            "text": text,
        }
        assert journey.deployment_answer([answer], "comment") is answer
        assert not journey.turn_failed([answer])
        for failure in ("startup_failed", "rate_limited"):
            receipt = {**answer, "failure": failure}
            assert journey.deployment_answer([receipt], "comment") is None
            assert journey.turn_failed([receipt])


def test_startup_line_distinguishes_an_unobserved_state_request():
    startup = {
        "first_byte": 20,
        "document": 30,
        "paint": {"first-contentful-paint": 40},
        "shifts": [],
        "upgraded": {"at": 50},
        "presented": {
            "at": 60,
            "js_loaded": 45,
            "state_loaded": None,
            "requests": 3,
            "bytes": 3072,
            "code_requests": 2,
            "code_bytes": 2048,
            "js_requests": 1,
            "js_bytes": 1024,
        },
    }

    line = verify_site.startup_line("page", startup)

    assert "JS fetched 45 ms" in line
    assert "state answered not observed" in line
    assert "state answered 0 ms" not in line


def test_startup_line_distinguishes_an_unobserved_first_paint():
    startup = {
        "first_byte": 20,
        "document": 30,
        "paint": {},
        "shifts": [],
        "upgraded": {"at": 50},
        "presented": {
            "at": 60,
            "js_loaded": 45,
            "state_loaded": 55,
            "requests": 3,
            "bytes": 3072,
            "code_requests": 2,
            "code_bytes": 2048,
            "js_requests": 1,
            "js_bytes": 1024,
        },
    }

    line = verify_site.startup_line("page", startup)

    assert "first contentful paint not observed" in line
    assert "first contentful paint 0 ms" not in line


@pytest.mark.parametrize(
    "failure",
    ["startup_failed", "rate_limited"],
)
def test_the_deploy_gate_stops_reading_a_turn_the_container_has_closed(
    failure,
):
    """A harness failure receipt is terminal, so the wait ends where it lands.

    Every other reading the wait takes is one a live turn can still be passing
    through, which is why they run to `TURN_PATIENCE`. This one is posted from where
    the container closes the turn, and waiting the budget out on it would spend five
    minutes before the second ask that follows it could even start.
    """
    comment = {"id": "comment-id"}
    working = {
        "active": {"revision": 1, "url": "revisions/1.html"},
        "activity": {
            "kind": "working",
            "obligations": [{"input": "comment-id", "dropped": False}],
        },
        "events": [
            {
                "kind": "reply",
                "parent": "comment-id",
                "author": "agent",
                "responds": "comment-id",
                "text": "A newly worded harness failure.",
                "failure": failure,
            }
        ],
    }
    context = _StateReads([working])
    profile = journey.AgentProfile()
    session = journey.Session(
        context,
        None,
        [],
        "https://leaf.page/examples/triage-board/",
        "https://leaf.page/examples/triage-board/api/state",
        working,
        {"Leaf-Layer": "layer", "Leaf-Release": "release"},
        None,
    )
    turn = journey.await_turn(
        journey.BrowserEnd(session),
        comment,
        1,
        "abcd1234",
        None,
        # The suite's deadline rather than `TURN_LIMIT`: a wait that stopped
        # reading this reply comes back on the next assertion within it.
        time.monotonic() + STATED_TIMEOUT,
        profile,
    )
    # One read, though the page still names a turn on the comment: the wait ended on
    # the reply rather than on `still_answering` or a clock.
    assert context.reads == 1
    assert journey.still_answering(working, "comment-id")
    assert turn.answer is None
    assert journey.turn_failed(turn.replies)


class _PresentationWait:
    def __init__(self, waits: list[int]):
        self.waits = waits

    def wait_for(self, timeout: int) -> None:
        self.waits.append(timeout)


class _Text:
    def __init__(self, text: str):
        self.text = text

    def inner_text(self) -> str:
        return self.text


class _DeployedPage:
    """The page the agent pass opens, reloads after its turn, and reads back."""

    def __init__(
        self,
        recorded: str,
        revision: int,
        presented_at: float,
        reload_ok: bool = True,
        banner: str | None = None,
        follows_revision: bool = False,
        presentation_pending: bool = False,
        initial_presented_at: float | None = None,
    ):
        self.recorded = recorded
        self.revision = revision
        self.presented_at = presented_at
        self.reload_ok = reload_ok
        self.banner = banner
        self.follows_revision = follows_revision
        self.presentation_pending = presentation_pending
        self.initial_presented_at = (
            presented_at if initial_presented_at is None else initial_presented_at
        )
        self.init_scripts: list[Path] = []
        self.presentation_waits: list[int] = []
        self.revision_waits: list[tuple[int, int]] = []

    def add_init_script(self, *, path: Path) -> None:
        self.init_scripts.append(path)

    def on(self, event: str, handler) -> None:
        pass

    def goto(self, url: str, **kwargs) -> _Read:
        return _Read({})

    def reload(self, **kwargs) -> _Read:
        answered = _Read({})
        answered.ok = self.reload_ok
        return answered

    def wait_for_function(
        self, expression: str, *, arg: int | None = None, timeout: int
    ) -> None:
        assert expression == "window.__leafVerifier.revisionAtLeast" and arg is not None
        self.revision_waits.append((arg, timeout))
        if self.revision >= arg and not self.presentation_pending:
            return
        if self.follows_revision:
            self.revision = arg
            return
        raise verify_site.PlaywrightTimeout("revision did not arrive")

    def locator(self, selector: str):
        if selector == "main":
            return _Text(self.recorded)
        assert selector == "body[data-lf-presented]"
        return _PresentationWait(self.presentation_waits)

    def evaluate(self, script: str, arg=None):
        if script == "window.__leafVerifier.startVisibleReplyClock":
            return 100.0
        if script == "window.__leafVerifier.replyShownAt":
            return {"at": 12_600.0, "by": "message", "message": 12_600.0}
        if script == "window.__leafStartup.reading":
            presented_at = (
                self.presented_at
                if len(self.presentation_waits) > 1
                else self.initial_presented_at
            )
            return {
                "first_byte": 100.0,
                "document": 200.0,
                "paint": {"first-contentful-paint": 250.0},
                "shifts": [],
                "upgraded": {"at": 300.0},
                "presented": {
                    "at": presented_at,
                    "js_loaded": 275.0,
                    "state_loaded": presented_at - 100.0,
                    "js_requests": 16,
                    "js_bytes": 150 * 1024,
                    "code_requests": 20,
                    "code_bytes": 330 * 1024,
                    "requests": 24,
                    "bytes": 335 * 1024,
                },
            }
        if "presented?.at" in script:
            return self.presented_at
        if script == "window.__leafVerifier.revision":
            return str(self.revision)
        if script == "window.__leafVerifier.revisionAtLeast":
            return self.revision >= arg and not self.presentation_pending
        if script == "window.__leafVerifier.status":
            return self.banner
        return []


class _DeployedContainer:
    """The private container one activated user session reaches, serving `release`."""

    def __init__(self, release: str, page: _DeployedPage):
        self.release = release
        self.page = page
        self.request = self
        self.closed = False

    def new_page(self) -> _DeployedPage:
        return self.page

    def get(self, url: str, headers: dict | None = None, **kwargs) -> _Read:
        answered = {"leaf-session": "active", "leaf-release": self.release}
        return _Read(
            {
                "active": {"revision": 1, "url": "revisions/1.html"},
                "layer": {"generation": "generation-1"},
                "release": self.release,
                "events": [],
            },
            headers=answered,
        )

    def close(self) -> None:
        self.closed = True


class _DeployedSite:
    def __init__(self, context: _DeployedContainer):
        self.context = context

    def new_context(self) -> _DeployedContainer:
        return self.context


class _RollingOutContainer:
    """An allocation the image rollout has not reached, so the edge answers for it."""

    def __init__(self, release: str, page: _DeployedPage):
        self.release = release
        self.page = page
        self.request = self
        self.closed = False

    def new_page(self) -> _DeployedPage:
        return self.page

    def get(self, url: str, headers: dict | None = None, **kwargs) -> _Read:
        if "api/view" not in url:
            return _Read(
                {
                    "active": {"revision": 1, "url": "revisions/1.html"},
                    "layer": {"generation": "generation-1"},
                    "release": self.release,
                    "events": [],
                },
                headers={"leaf-release": self.release, "leaf-session": "passive"},
            )
        # What `rollingOut` in `worker/src/index.ts` sends: the deployed release
        # rather than this container's, no session at all, and `Retry-After` naming
        # the rollout as the reason there is nothing to compare.
        starting = _Read(
            {},
            "this release is still starting",
            headers={"retry-after": "5", "leaf-release": self.release},
        )
        starting.ok = False
        starting.status = 503
        return starting

    def close(self) -> None:
        self.closed = True


class _RollingSite:
    """Successive allocations, so the gate's retry gets a fresh one each time."""

    def __init__(self, contexts: list):
        self.contexts = list(contexts)
        self.opened: list = []

    def new_context(self):
        context = self.contexts.pop(0) if len(self.contexts) > 1 else self.contexts[0]
        self.opened.append(context)
        return context


def _rolling_clock(monkeypatch, samples: list[float], slept: list[float]) -> None:
    readings = iter(samples)
    monkeypatch.setattr(
        verify_site,
        "time",
        SimpleNamespace(monotonic=readings.__next__, sleep=slept.append),
    )


def test_the_agent_pass_waits_out_an_allocation_the_rollout_has_not_reached(
    monkeypatch,
):
    """A rollout answered by the edge is the same wait as one read off a container.

    `publish-site` deployed release `a471af1a…` and its release pass verified
    leaf.page in Chrome; six seconds later the agent pass failed outright on
    `https://leaf.page/examples/triage-board/api/view?revision=1&through_seq=1
    returned 503` (run 35320758891). `api/view` activates a session, and until the
    container image rollout reaches the allocation it gets, the Worker unseats the
    session and answers `503` rather than handing a foreign release on. That is the
    condition this loop already waits out when the container answers for itself, so
    it has to end in the same retry rather than in a red deploy.
    """
    release = "a471af1a" + "0" * 56
    starting = _RollingOutContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    ready = _DeployedContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    slept: list[float] = []
    _rolling_clock(monkeypatch, [0.0, 12.0], slept)

    site = _RollingSite([starting, ready])
    session = verify_site.agent_session(site, release, origin="https://leaf.page")

    assert session.context is ready
    # The unseated allocation is dropped rather than carried into the turn.
    assert starting.closed and not ready.closed
    assert site.opened == [starting, ready]
    assert slept == [10]


def test_a_rollout_that_never_lands_ends_the_agent_pass_naming_it(monkeypatch):
    """The bound still holds, and the message says which reading ran it out."""
    release = "a471af1a" + "0" * 56
    starting = _RollingOutContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    slept: list[float] = []
    _rolling_clock(monkeypatch, [0.0, 400.0], slept)

    with pytest.raises(RuntimeError) as failure:
        verify_site.agent_session(
            _RollingSite([starting]), release, origin="https://leaf.page"
        )

    assert "reached no container able to admit its agent's turn" in str(failure.value)
    assert verify_site.STILL_STARTING in str(failure.value)
    assert slept == []


class _Allocation:
    """One activating read, answering as the edge or as the container it reached."""

    def __init__(self, answer: _Read):
        self.answer = answer
        self.request = self
        self.asked: list[str] = []

    def get(self, url: str, **kwargs) -> _Read:
        self.asked.append(url)
        return self.answer


def _answered(status: int, headers: dict | None = None, body: str = "") -> _Read:
    answer = _Read({}, body, headers=headers)
    answer.ok = status < 400
    answer.status = status
    return answer


ACTIVATION = "https://leaf.page/examples/triage-board/api/view?revision=1&through_seq=1"


def test_the_rollout_answer_is_the_one_503_the_activating_read_waits_on():
    """Both passes make this request, so one function reads what comes back.

    Run 35320758891 printed `...api/view?revision=1&through_seq=1 returned 503` seven
    times: six inside the release pass's `until` loop, then the seventh in the agent
    pass, which ended the deploy. Every one was the Worker's own `rollingOut` answer,
    which says the deployment is still landing. A bare status cannot say that, and
    two investigations went to Cloudflare's control plane instead.
    """
    rolling = _Allocation(
        _answered(
            503,
            {"retry-after": "5", "leaf-release": "a" * 64},
            "this release is still starting",
        )
    )

    assert verify_site.activation_read(rolling, ACTIVATION) is None
    assert rolling.asked == [ACTIVATION]


def test_a_503_the_worker_did_not_write_is_this_release_failing():
    """`Retry-After` separates the Worker's rollout answer from a container's own 503.

    A container answering `503` for itself comes back through the pass-through path
    without the header, and waiting that out would sit on a broken release until the
    workflow's deadline instead of reporting it.
    """
    broken = _Allocation(
        _answered(503, {"leaf-session": "active"}, "the page has no revision 1")
    )

    with pytest.raises(RuntimeError) as failure:
        verify_site.activation_read(broken, ACTIVATION)

    assert str(failure.value) == (
        f"{ACTIVATION} returned 503: the page has no revision 1"
    )


# The page's log for a turn that titled its thread at 2.25 s and replied at 12.5 s,
# each from the comment's admission.
def run_browser_journey(website):
    """The release ask at the user's browser end on `website`'s session and release."""
    session, version = website
    return journey.run_journey(journey.BrowserEnd(session), version)


def test_the_page_a_turn_has_just_written_waits_for_its_revision_after_presentation(
    monkeypatch, capsys
):
    """One bound cannot serve both pages this gate reads, so the reload states its own.

    `publish-site` deployed release `4ef93dd9…` and then failed on the reload after a
    healthy turn: `never presented, reaching no startup milestone`. The pages the
    release pass walks come from the edge and present in about a second, which is what
    the default bound is for. The reloaded one is answered by a container that has just
    run a hosted model turn, whose first `/api/state` read costs seconds rather than
    milliseconds — measured against the live deployment, 123 ms before a turn and
    2252-3918 ms after one, on the same session and page.

    The gate gives the reload that bound both to present and, after presentation, to
    follow the revision its first read brings back. The second wait is required now that
    presentation no longer implies the read has answered.
    """
    release = "4ef93dd9" + "0" * 56
    recorded = f"Deployment {release[:8]} verified"
    page = _DeployedPage(
        recorded,
        revision=1,
        presented_at=28444.0,
        follows_revision=True,
        initial_presented_at=1400.0,
    )
    container = _DeployedContainer(release, page)
    # Activated 12 s after the comment's admission, on the page server's clock.
    published = {
        "revision": 2,
        "url": "revisions/2.html",
        "activated_at": "2026-10-04T19:00:12+00:00",
    }
    profile = journey.AgentProfile()
    profile.visible_reply_started_ms = 100.0
    profile.ask_count = 1
    profile.acknowledged = [0.250]
    profile.event_ids = ["test-comment"]
    profile.activities = [
        (0.250, "queued", ""),
        (1.0, "working", "Editing the page"),
        (12.5, "away", ""),
    ]
    monkeypatch.setattr(
        journey,
        "ask_until_answered",
        lambda *args, **kwargs: journey.AgentAsks(
            journey.TurnReading(
                {
                    "active": {"revision": 2},
                    "activity": {"kind": "away"},
                    "source_error": None,
                    "events": TURN_LOG,
                    "browser": {
                        "thread": {
                            "threads": [
                                {"id": "test-comment", "title": "Deployment heading"}
                            ]
                        }
                    },
                },
                published,
                [{"kind": "reply", "text": "deployment verified"}],
                {
                    "kind": "reply",
                    "id": "test-answer",
                    "parent": "test-comment",
                    "text": "deployment verified",
                    "ts": "2026-10-04T12:00:12.500-07:00",
                },
            ),
            1,
            1,
            profile,
        ),
    )
    # One sample sets `agent_session`'s rollout deadline; in the journey, one bounds
    # the wait for the title the log already holds, one the wait for the reply the
    # page has already shown, and two surround the revision wait this case measures.
    with monkeypatch.context() as timing:
        timing.setattr(verify_site, "time", SimpleNamespace(monotonic=lambda: 0.0))
        timing.setattr(
            journey,
            "time",
            SimpleNamespace(monotonic=iter([39.0, 39.5, 40.0, 42.5]).__next__),
        )
        benchmark = run_browser_journey(
            journey.website_session(
                _DeployedSite(container),
                None,
                origin="https://leaf.page",
                direct_agent=False,
            )
        )

    # The ordinary first load uses the edge-page presentation bound. The post-turn
    # reload gets its own bound for both presentation and the later revision follow.
    assert page.presentation_waits == [30_000, journey.TURN_PRESENTATION]
    assert page.revision_waits == [(2, journey.TURN_PRESENTATION)]
    assert journey.TURN_PRESENTATION > 30_000
    # The stamps the message needs to say which stall it was. Without them a page that
    # upgraded and stalled on its first state read reports the same "no startup
    # milestone" as one whose modules never arrived.
    assert page.init_scripts == [startup.SCRIPT, verify_site.VERIFIER_SCRIPT]
    # A green run reports startup and the post-presentation revision follow separately.
    reported = capsys.readouterr().err
    assert "followed it 2500 ms after presentation" in reported
    assert '"responseVisible": 12500.0' in reported
    assert benchmark == {
        "version": release,
        "page": {
            "htmlFirstByteMs": 100.0,
            "htmlCompleteMs": 200.0,
            "firstContentfulPaintMs": 250.0,
            "javascriptFetchedMs": 275.0,
            "upgradedMs": 300.0,
            "stateAnsweredMs": 1300.0,
            "presentedMs": 1400.0,
            "requestsAtPresentation": 24,
            "bytesAtPresentation": 335 * 1024,
            "javascriptRequestsAtPresentation": 16,
            "javascriptBytesAtPresentation": 150 * 1024,
            "codeRequestsAtPresentation": 20,
            "codeBytesAtPresentation": 330 * 1024,
            "layoutShifts": [],
        },
        "comment": {
            "sessionReference": None,
            "eventIds": ["test-comment"],
            "asks": 1,
            "sinceAdmissionMs": {
                "queued": None,
                "pickedUp": None,
                "started": None,
                "titled": 2250.0,
                "progress": None,
                "published": 12000.0,
                "replied": 12500.0,
            },
            "sinceSendMs": {
                "acknowledged": [250.0],
                "responseVisible": 12500.0,
                "responseMessageVisible": 12500.0,
            },
            "responseShownBy": "message",
            "activity": [
                {"atMs": 250.0, "kind": "queued", "detail": ""},
                {
                    "atMs": 1000.0,
                    "kind": "working",
                    "detail": "Editing the page",
                },
                {"atMs": 12500.0, "kind": "away", "detail": ""},
            ],
        },
        "change": {
            "marker": release[:8],
            "revision": 2,
            "reply": "deployment verified",
        },
        "changedPage": {
            "htmlFirstByteMs": 100.0,
            "htmlCompleteMs": 200.0,
            "firstContentfulPaintMs": 250.0,
            "javascriptFetchedMs": 275.0,
            "upgradedMs": 300.0,
            "stateAnsweredMs": 28344.0,
            "presentedMs": 28444.0,
            "requestsAtPresentation": 24,
            "bytesAtPresentation": 335 * 1024,
            "javascriptRequestsAtPresentation": 16,
            "javascriptBytesAtPresentation": 150 * 1024,
            "codeRequestsAtPresentation": 20,
            "codeBytesAtPresentation": 330 * 1024,
            "layoutShifts": [],
            "followedRevisionMs": 2500.0,
        },
    }

    # A reload the container never answered is its own reading, taken before the wait.
    # Left unchecked it arrives as a presentation timeout, which is the message this
    # branch is here to stop conflating with a slow read.
    refused = _DeployedPage(recorded, revision=2, presented_at=28444.0, reload_ok=False)
    with pytest.raises(RuntimeError, match="did not reload after its agent turn"):
        run_browser_journey(
            journey.website_session(
                _DeployedSite(_DeployedContainer(release, refused)),
                release,
                origin="https://leaf.page",
                direct_agent=False,
            )
        )
    assert refused.presentation_waits == [30_000]
    assert refused.revision_waits == []

    pending = _DeployedPage(
        recorded, revision=2, presented_at=28444.0, presentation_pending=True
    )
    with pytest.raises(RuntimeError, match="did not finish presenting it"):
        run_browser_journey(
            journey.website_session(
                _DeployedSite(_DeployedContainer(release, pending)),
                release,
                origin="https://leaf.page",
                direct_agent=False,
            )
        )
    assert pending.revision_waits == [(2, journey.TURN_PRESENTATION)]


def test_a_reload_that_presented_offline_reports_the_banner_it_presented_under(
    monkeypatch,
):
    """A stale revision has two causes, and the message has to separate them.

    `publish-site` failed on release `5b6be522…` with `stands on revision 1 rather than
    following the published 2` and nothing else, which reads the same whether the
    container answered the reload's first state read with revision 1 or never answered
    it at all. The gate cannot watch that read, but the page says which it was: an
    answer it never got leaves the offline banner standing over the authored document.
    """
    release = "5b6be522" + "0" * 56
    recorded = f"Deployment {release[:8]} verified"
    published = {
        "revision": 2,
        "url": "revisions/2.html",
        "activated_at": "2026-10-04T19:00:12+00:00",
    }
    profile = journey.AgentProfile()
    profile.visible_reply_started_ms = 100.0
    monkeypatch.setattr(
        journey,
        "ask_until_answered",
        lambda *args, **kwargs: journey.AgentAsks(
            journey.TurnReading(
                {
                    "active": {"revision": 2},
                    "activity": {"kind": "away"},
                    "source_error": None,
                    "events": TURN_LOG,
                    "browser": {
                        "thread": {
                            "threads": [
                                {"id": "test-comment", "title": "Deployment heading"}
                            ]
                        }
                    },
                },
                published,
                [{"kind": "reply", "text": "deployment verified"}],
                {
                    "kind": "reply",
                    "id": "test-answer",
                    "parent": "test-comment",
                    "text": "deployment verified",
                    "ts": "2026-10-04T12:00:12.500-07:00",
                },
            ),
            1,
            1,
            profile,
        ),
    )

    offline = _DeployedPage(
        recorded,
        revision=1,
        presented_at=11_000.0,
        banner="Server offline — reconnecting",
    )
    with pytest.raises(RuntimeError) as reported:
        run_browser_journey(
            journey.website_session(
                _DeployedSite(_DeployedContainer(release, offline)),
                release,
                origin="https://leaf.page",
                direct_agent=False,
            )
        )
    assert "stands on revision 1" in str(reported.value)
    assert "Server offline — reconnecting" in str(reported.value)
    # Reported after the gate's own patience ran out, not at presentation: the banner is
    # quoted for a read that never answered rather than for one a second slower than the
    # runtime's wait.
    assert offline.revision_waits == [(2, journey.TURN_PRESENTATION)]

    # A page whose read answered is standing under an ordinary activity line rather
    # than an empty banner — a presented page always has one — so the two causes are
    # separated by what the message quotes rather than by whether it quotes anything.
    told = _DeployedPage(
        recorded,
        revision=1,
        presented_at=1_400.0,
        banner="Claude is handling 1 update",
    )
    with pytest.raises(RuntimeError) as named:
        run_browser_journey(
            journey.website_session(
                _DeployedSite(_DeployedContainer(release, told)),
                release,
                origin="https://leaf.page",
                direct_agent=False,
            )
        )
    assert "stands on revision 1" in str(named.value)
    assert "Claude is handling 1 update" in str(named.value)
    assert "Server offline" not in str(named.value)
    assert told.revision_waits == [(2, journey.TURN_PRESENTATION)]
