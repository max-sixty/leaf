"""Developer tooling checks; run explicitly from dev/tests."""

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    owed_answers,
    page_state,
)
from interact_support import (
    append_carried_log_record as append_event,
)
from playwright.sync_api import BrowserContext, Page
from process.website_server import (  # noqa: F401
    _no_harness_outlives_its_test_fixture,
    accept_in_turn,
    get,
    write_manifest,
)

import leaf_website as website_server
from leaf.event_log import read_events
from leaf.files import revision_path
from leaf.state import session_record
from leaf_dev import ROOT, startup
from leaf_dev.commands import journey, journey_chart, refresh_previews, verify_site
from leaf_dev.reply_phases import turn_phases


class _Read:
    ok = True
    status = 200

    def __init__(
        self,
        payload: dict,
        body: str = "",
        headers: dict | None = None,
        *,
        url: str = "",
        request=None,
    ):
        self.payload = payload
        self.body = body
        self.headers = headers or {}
        self.url = url
        self.request = request

    def json(self) -> dict:
        return self.payload

    def text(self) -> str:
        return self.body


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


class _FailedTurn:
    """A deployed page whose turn ends with a failure receipt."""

    def __init__(self, failure: str = "startup_failed"):
        self.failure = failure
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
        raise AssertionError(f"unexpected document request: {url}")

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
        return {
            "active": {"revision": 1, "url": "revisions/1.html"},
            "activity": {"kind": "away", "obligations": []},
            "events": events,
        }


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
        status: str | None = None,
        follows_revision: bool = False,
        presentation_pending: bool = False,
        initial_presented_at: float | None = None,
    ):
        self.recorded = recorded
        self.revision = revision
        self.presented_at = presented_at
        self.reload_ok = reload_ok
        self.status = status
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

    def remove_listener(self, event: str, handler) -> None:
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
            assert arg is not None
            return self.revision >= arg and not self.presentation_pending
        if script == "window.__leafVerifier.status":
            return self.status
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


def run_browser_journey(website):
    """The release ask at the user's browser end on `website`'s session and release."""
    session, version = website
    return journey.run_journey(journey.BrowserEnd(session), version)


TURN_LOG = [
    {"kind": "comment", "id": "test-comment", "ts": "2026-10-04T12:00:00.000-07:00"},
    {
        "kind": "thread_title",
        "id": "test-title",
        "thread": "test-comment",
        "title": "Deployment heading",
        "ts": "2026-10-04T12:00:02.250-07:00",
    },
    {
        "kind": "reply",
        "id": "test-answer",
        "author": "agent",
        "parent": "test-comment",
        "responds": "test-comment",
        "text": "deployment verified",
        "ts": "2026-10-04T12:00:12.500-07:00",
    },
]


def test_the_journey_emits_one_json_sample_for_each_website_target(monkeypatch):
    """The gate's agent journey is also the benchmark: stdout is only its JSON sample,
    naming the harness and origin it ran on and the one step a website takes."""
    calls = []
    lifecycle = []

    @contextmanager
    def local():
        lifecycle.append("start")
        try:
            yield "http://127.0.0.1:8080", "a" * 40
        finally:
            lifecycle.append("stop")

    @contextmanager
    def worker():
        lifecycle.append("worker")
        yield verify_site.LocalWorker(
            "http://127.0.0.1:8787", "b" * 40, "test-worker", ROOT / ".tmp"
        )

    @contextmanager
    def browser():
        yield None

    closed = []

    class Context:
        def close(self):
            closed.append(True)

    def session(browser, release, *, origin, direct_agent):
        calls.append((origin, release, direct_agent))
        session = SimpleNamespace(context=Context(), url=origin, pause=time.sleep)
        return session, release or "served"

    monkeypatch.setattr(journey, "local_adapter", local)
    monkeypatch.setattr(journey, "local_worker", worker)
    monkeypatch.setattr(journey, "headless_shell", browser)
    monkeypatch.setattr(journey, "website_session", session)
    monkeypatch.setattr(
        journey,
        "run_journey",
        lambda end, version: {
            "version": version,
            "comment": {"eventIds": ["comment"]},
        },
    )
    runner = CliRunner()
    local_result = runner.invoke(journey.journey, ["website-adapter"])
    assert local_result.exit_code == 0, local_result.output
    sample = json.loads(local_result.stdout)
    [step] = sample.pop("steps")
    assert sample == {
        "target": "website-adapter",
        "harness": "website",
        "origin": "http://127.0.0.1:8080",
        "userEnd": "browser",
        "case": "waiting",
        "version": "a" * 40,
        "comment": {"eventIds": ["comment"]},
    }
    assert (step["step"], step["comments"]) == ("release", {})
    # A harness's options belong to its harness alone.
    refused = runner.invoke(journey.journey, ["website-adapter", "--http"])
    assert refused.exit_code == 2
    assert "a website's journey is its page in a browser" in refused.output
    for target in ("website-adapter", "claude-code", "pi"):
        refused = runner.invoke(journey.journey, [target, "--preview"])
        assert refused.exit_code == 2
        assert "--preview is an option of the codex targets" in refused.output
    # A remote journey needs no local build: the origin names its release.
    remote_result = runner.invoke(journey.journey, ["https://leaf-dev.example/"])
    assert remote_result.exit_code == 0, remote_result.output
    assert {
        key: value
        for key, value in json.loads(remote_result.stdout).items()
        if key in ("target", "harness", "origin", "version")
    } == {
        "target": "https://leaf-dev.example",
        "harness": "website",
        "origin": "https://leaf-dev.example",
        "version": "served",
    }
    # Through the local Worker the journey holds the container to the built release.
    worker_result = runner.invoke(journey.journey, ["website-worker"])
    assert worker_result.exit_code == 0, worker_result.output
    assert lifecycle == ["start", "stop", "worker"]
    # Each journey closes the browser context its session opened.
    assert closed == [True, True, True]
    assert calls == [
        ("http://127.0.0.1:8080", "a" * 40, True),
        ("https://leaf-dev.example", None, False),
        ("http://127.0.0.1:8787", "b" * 40, False),
    ]
    # Each sample is also kept on this machine, outside the checkout.
    kept = journey.samples_path().read_text().splitlines()
    assert [json.loads(line)["origin"] for line in kept] == [
        "http://127.0.0.1:8080",
        "https://leaf-dev.example",
        "http://127.0.0.1:8787",
    ]


def test_the_journey_chart_draws_each_targets_latest_version_from_kept_samples():
    """`journey-chart` charts the samples the journey kept, so a later reading needs
    no transcription: each target's latest version only, each sign a sample saw."""

    def sample(target, version, titled, picked_up, progress, replied, **named):
        comment = {
            "sinceAdmissionMs": {
                "queued": None,
                "pickedUp": picked_up,
                "started": None,
                "titled": titled,
                "progress": progress,
                "published": replied - 500,
                "replied": replied,
            },
            "sinceSendMs": {"responseVisible": replied + 1000},
        }
        return {
            "target": target,
            "harness": target.split("-")[0],
            **named,
            "version": version,
            "comment": comment,
            "steps": [{"step": "release", "seconds": replied / 1000, "comments": {}}],
        }

    old, new = "a" * 40, "b" * 40 + "+working-tree"
    adapter = "website-adapter"
    samples = [
        sample("claude-code", old, 1800, 7000, None, 17500),
        sample("codex-app-server", old, 4700, 200, None, 69600),
        sample("claude-code", new, 1300, 7000, 6900, 18600),
        sample("codex-app-server", old, 4600, 300, None, 102900),
        # A user end over HTTP is a row of its own, at its own latest version.
        sample("claude-code", old, 1300, 7000, 6900, 15000, userEnd="http"),
        # Each local run serves on a port of its own, but is the same target.
        sample(adapter, old, 900, 300, None, 30000, origin="http://127.0.0.1:8080"),
        sample(adapter, new, 800, 300, None, 25000, origin="http://127.0.0.1:9090"),
    ]
    # A sample kept before the journey ran its steps is left out.
    unstepped = sample("codex", new, 900, 300, None, 9000)
    del unstepped["steps"]
    path = journey.samples_path()
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(s) + "\n" for s in [*samples, unstepped]))
    result = CliRunner().invoke(journey_chart.journey_chart)
    assert result.exit_code == 0, result.output
    markup = result.stdout
    assert markup.startswith('<lf-chart id="journey-signs"')
    rows = journey_chart.chart_rows([*samples, unstepped])
    assert {r["row"] for r in rows} == {
        "Claude Code at bbbbbbbb+working-tree",
        "Claude Code over HTTP at aaaaaaaa",
        "Codex App Server at aaaaaaaa",
        "website-adapter at bbbbbbbb+working-tree",
    }
    # Older versions are left out; Codex's two runs of one version stay.
    assert sorted(r["s"] for r in rows if r["sign"] == "reply") == [
        15.0,
        18.6,
        25.0,
        69.6,
        102.9,
    ]
    # A step the run never reached draws no dot.
    assert [r["row"] for r in rows if r["sign"] == "progress"] == [
        "Claude Code at bbbbbbbb+working-tree",
        "Claude Code over HTTP at aaaaaaaa",
    ]
    assert json.dumps(rows) in markup


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


def test_the_preview_generator_uses_the_live_website_route(page_dir, tmp_path):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    with refresh_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/decision/api/state")[0])

    assert state["publication"] == {
        "kind": "example",
        "agent": "Agent",
        "install_url": "/#install",
    }


def test_local_verification_settles_host_network(monkeypatch):
    @contextmanager
    def worker():
        yield verify_site.LocalWorker(
            "http://127.0.0.1:8787", "release", "test-worker", ROOT / ".tmp"
        )

    attempts = []

    def verify(origin, release, *, settle_after_activation=None, worker=None):
        assert worker is not None
        assert worker.origin == origin
        attempts.append(settle_after_activation)
        raise RuntimeError("page did not present: net::ERR_NETWORK_CHANGED")

    monkeypatch.setattr(verify_site, "built_release", lambda: "release")
    monkeypatch.setattr(verify_site, "local_worker", worker)
    monkeypatch.setattr(verify_site, "run_verification", verify)

    result = CliRunner().invoke(verify_site.verify_site, ["website-worker"])

    assert isinstance(result.exception, RuntimeError)
    assert attempts == [verify_site.wait_for_host_network]


def test_local_worker_name_is_valid_when_run_suffix_starts_with_underscore(
    monkeypatch, tmp_path
):
    run = tmp_path / "run-_up9yvbg"
    monkeypatch.setattr(verify_site, "run_directory", lambda parent: run)

    def stop_before_build(*args, **kwargs):
        raise RuntimeError("stop before building")

    calls = []

    def docker(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args[0], 0, stdout="")

    monkeypatch.setattr(verify_site, "copy_working", stop_before_build)
    monkeypatch.setattr(verify_site.subprocess, "run", docker)

    with (
        pytest.raises(RuntimeError, match="stop before building"),
        verify_site.local_worker(),
    ):
        pass

    name = calls[0][-1].removeprefix("name=^workerd-").removesuffix("-")
    assert re.fullmatch(r"[a-z0-9]+(?:[._]|__|[-]+[a-z0-9]+)*", name)


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

    handling = page_state(page_dir)
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

    stopped = page_state(page_dir)
    assert stopped["activity"]["obligations"] == [f"update:{comment['id']}"]
    assert not journey.still_answering(stopped, comment["id"])


def test_the_deploy_gate_stops_waiting_on_a_page_with_no_agent_on_the_comment():
    """The other half of the same reading: nothing is coming, so do not wait it out.

    A container that dropped its session leaves the obligation open with no turn
    behind it. Extending the wait there would spend the step's whole budget to raise
    the failure it could already raise.
    """
    for kind in ("away", "unheld", "stalled", "closed", "listening"):
        state = {"activity": {"kind": kind, "obligations": ["update:comment-id"]}}
        assert not journey.still_answering(state, "comment-id")
    working = {"activity": {"kind": "working", "obligations": ["update:comment-id"]}}
    assert journey.still_answering(working, "comment-id")
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
    state = page_state(page_dir)
    replies = [event for event in state["events"] if event["kind"] == "reply"]
    assert reply is not None
    assert [event["id"] for event in replies] == [reply["id"]]
    contract = load_registry(page_dir)["$events"]["kinds"]["reply"]
    assert event_record_error(contract, replies[0]) is None
    assert journey.turn_failed(replies)
    assert journey.deployment_answer(replies, comment["id"]) is None
    assert not owed_answers(page_dir)
    assert harness.attach(page_dir, comment["id"]) is None


@pytest.mark.parametrize("failure", ["startup_failed", "rate_limited"])
def test_the_deploy_gate_stops_on_the_first_failure(failure):
    """Failure receipts are evidence; the verifier sends no second model task."""
    context = _FailedTurn(failure)
    session = journey.Session(
        cast(BrowserContext, context),
        cast(Page, context),
        [],
        "https://leaf.page/examples/triage-board/",
        "https://leaf.page/examples/triage-board/api/state",
        {"active": {"revision": 1, "url": "revisions/1.html"}},
        {"Leaf-Layer": "layer", "Leaf-Release": "release"},
        None,
    )
    asked = journey.ask_until_answered(journey.BrowserEnd(session), "abcd1234")
    assert asked.asks == 1
    assert asked.turn.answer is None
    assert asked.turn.replies[0]["failure"] == failure
    assert len(context.comments) == 1


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
    """A failure receipt ends the wait without spending a live turn's patience."""
    comment = {"id": "comment-id"}
    working = {
        "active": {"revision": 1, "url": "revisions/1.html"},
        "activity": {"kind": "working", "obligations": ["update:comment-id"]},
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
        cast(BrowserContext, context),
        cast(Page, None),
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


def test_a_title_written_after_the_reply_is_still_timed(tmp_path):
    """The page server titles a thread beside the agent's turn, so the title can land
    after the reply that ended the turn's wait; the journey reads on for it rather
    than reporting the title as never written. The state it reads is the one a page
    server serves, since the journey reads titles from it."""
    from leaf.event_log import append_event
    from leaf.thread import title_event
    from leaf_dev.arms import PageClient, serving
    from leaf_dev.review_scenario import prepare

    state, page_dir = tmp_path / "state", tmp_path / "page"
    prepare(ROOT, state, page_dir)
    with serving(ROOT, state, page_dir) as url:
        client = PageClient(url)
        client.post(
            {
                "kind": "comment",
                "revision": client.state()["active"]["revision"],
                "attempt": "journey-title-wait",
                "text": "Is the release recorded?",
            }
        )
        untitled = client.state()
        [comment] = [
            e for e in untitled["events"] if e.get("attempt") == "journey-title-wait"
        ]
        assert journey.title(untitled["events"], comment["id"]) is None
        paused = []

        def pause(seconds):
            # The title lands while the journey waits on, as the page server's does.
            if not paused:
                append_event(
                    page_dir,
                    title_event(
                        comment["id"],
                        "Release recorded",
                        {"agent": "Agent", "session": "journey-title"},
                    ),
                )
            paused.append(seconds)

        class Context:
            request = SimpleNamespace(get=lambda *args, **kwargs: _Read(client.state()))

        session = journey.Session(
            cast(BrowserContext, Context()),
            cast(Page, None),
            [],
            url,
            url,
            untitled,
            {},
            None,
            pause=pause,
        )
        events = journey.await_title(
            journey.BrowserEnd(session), comment["id"], untitled
        )["events"]
    assert paused == [1]
    assert journey.title(events, comment["id"]) == "Release recorded"
    steps = journey.recorded_steps(events, comment, None)
    assert steps["titled"] is not None and steps["titled"] > 0
    assert steps["published"] is None


def test_a_progress_update_is_timed_apart_from_the_answer():
    """Transport and work milestones name this exact input; unrelated earlier
    pickups and starts cannot count. Ephemeral progress is timed separately from
    the durable reply that answers."""
    comment, _title, reply = TURN_LOG
    progress = {
        "kind": "reply",
        "author": "agent",
        "id": "test-progress",
        "parent": comment["id"],
        "text": "Recording the release on the board.",
        "ephemeral": True,
        "ts": "2026-10-04T12:00:03.000-07:00",
    }
    assert journey.deployment_answer([progress], comment["id"]) is None
    assert journey.deployment_answer([progress, reply], comment["id"]) is reply
    published = {"activated_at": "2026-10-04T19:00:12+00:00"}
    transport = [
        {
            "kind": "pickup",
            "events": ["other-input"],
            "phase": "opened",
            "ts": "2026-10-04T12:00:00.500-07:00",
        },
        {"kind": "start", "item": "other-input", "ts": "2026-10-04T12:00:00.750-07:00"},
        {
            "kind": "pickup",
            "events": [comment["id"]],
            "phase": "queued",
            "ts": "2026-10-04T12:00:01.000-07:00",
        },
        {
            "kind": "pickup",
            "events": [comment["id"]],
            "phase": "opened",
            "ts": "2026-10-04T12:00:02.000-07:00",
        },
        {"kind": "start", "item": comment["id"], "ts": "2026-10-04T12:00:02.500-07:00"},
    ]
    for index, event in enumerate(transport):
        event["id"] = f"transport-{index}"
    assert journey.recorded_steps(
        [comment, *transport, progress, reply], comment, published
    ) == {
        "queued": 1.0,
        "pickedUp": 2.0,
        "started": 2.5,
        "titled": None,
        "progress": 3.0,
        "published": 12.0,
        "replied": 12.5,
    }

    # Addressed progress takes the input in hand atomically in the current log.
    inline = {**progress, "start": {"item": comment["id"]}}
    # Progress on another input, in that input's own thread.
    other = {**comment, "id": "other-input", "ts": "2026-10-04T12:00:00.900-07:00"}
    unrelated = {
        **inline,
        "id": "other-progress",
        "parent": "other-input",
        "start": {"item": "other-input"},
        "ts": "2026-10-04T12:00:01.000-07:00",
    }
    assert journey.recorded_steps(
        [comment, other, unrelated, inline, reply], comment, published
    ) == {
        "queued": None,
        "pickedUp": None,
        "started": 3.0,
        "titled": None,
        "progress": 3.0,
        "published": 12.0,
        "replied": 12.5,
    }


def test_an_agent_turn_splits_into_delivery_model_and_tool_phases():
    """A harness journey splits the turn it ran into the phases a reader adds up:
    the wait for the turn to start, each model call, and each tool phase with its
    calls, which end only when every call started together has returned."""

    def at(seconds: float) -> str:
        return f"2026-10-04T12:00:{seconds:06.3f}-07:00"

    def call(seconds: float, *uses: tuple[str, str]) -> dict:
        content = [
            {"type": "tool_use", "id": id, "name": "Bash", "input": {"command": cmd}}
            for id, cmd in uses
        ]
        return {
            "type": "assistant",
            "message": {"content": content},
            "received_at": at(seconds),
        }

    def result(seconds: float, id: str) -> dict:
        content = [{"type": "tool_result", "tool_use_id": id}]
        return {
            "type": "user",
            "message": {"content": content},
            "received_at": at(seconds),
        }

    comment, _, reply = TURN_LOG
    stream = [
        {"type": "system", "subtype": "hook_response", "received_at": at(0.2)},
        result(0.3, "running"),
        {"type": "system", "subtype": "init", "received_at": at(0.5)},
        {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": ""}]},
            "received_at": at(2.0),
        },
        call(
            4.0, ("start", "leaf task start . c1 --text x"), ("read", "cat threads.md")
        ),
        result(4.1, "read"),
        result(5.0, "start"),
        call(7.0, ("edit", "leaf page check .")),
        result(8.0, "edit"),
        call(12.0, ("reply", "leaf thread reply 62af9e31:0:test-comment")),
    ]
    # Delivery ends at the opened pickup, not at the first record the harness sends
    # after admission: a tool result of a turn already running is no delivery.
    assert turn_phases(stream, comment["ts"], at(0.5), reply["ts"]) == [
        {"phase": "delivery", "startMs": 0, "ms": 500},
        {"phase": "model", "startMs": 500, "ms": 3500},
        {
            "phase": "tool",
            "startMs": 4000,
            "ms": 1000,
            "calls": ["leaf task start . c1 --text x", "cat threads.md"],
        },
        {"phase": "model", "startMs": 5000, "ms": 2000},
        {"phase": "tool", "startMs": 7000, "ms": 1000, "calls": ["leaf page check ."]},
        {"phase": "model", "startMs": 8000, "ms": 4000},
        {
            "phase": "tool",
            "startMs": 12000,
            "ms": 500,
            "calls": ["leaf thread reply 62af9e31:0:test-comment"],
        },
    ]
    assert turn_phases(stream, comment["ts"], None, reply["ts"]) == []


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


def test_the_agent_pass_retries_a_reset_activation_on_a_fresh_session(monkeypatch):
    release = "a471af1a" + "0" * 56
    page = _DeployedPage("", revision=1, presented_at=900.0)

    class Resetting(_RollingOutContainer):
        def get(self, url: str, headers: dict | None = None, **kwargs):
            if "api/view" in url:
                raise verify_site.PlaywrightError(
                    "APIRequestContext.get: read ECONNRESET"
                )
            return super().get(url, headers=headers, **kwargs)

    resetting = Resetting(release, page)
    ready = _DeployedContainer(release, page)
    slept: list[float] = []
    _rolling_clock(monkeypatch, [0.0, 12.0], slept)

    site = _RollingSite([resetting, ready])
    session = verify_site.agent_session(site, release, origin="https://leaf.page")

    assert session.context is ready
    assert resetting.closed and not ready.closed
    assert site.opened == [resetting, ready]
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
                    "activity": {"kind": "away", "obligations": []},
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


def test_a_reload_that_presented_offline_reports_the_status_it_presented_under(
    monkeypatch,
):
    """A stale revision has two causes, and the message has to separate them.

    `publish-site` failed on release `5b6be522…` with `stands on revision 1 rather than
    following the published 2` and nothing else, which reads the same whether the
    container answered the reload's first state read with revision 1 or never answered
    it at all. The gate cannot watch that read, but the page says which it was: an
    answer it never got leaves the offline status standing over the authored document.
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
                    "activity": {"kind": "away", "obligations": []},
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
        status="Server offline — reconnecting",
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
    # Reported after the gate's own patience ran out, not at presentation: the status is
    # quoted for a read that never answered rather than for one a second slower than the
    # runtime's wait.
    assert offline.revision_waits == [(2, journey.TURN_PRESENTATION)]

    # A page whose read answered is standing under an ordinary activity line rather
    # than an empty status — a presented page always has one — so the two causes are
    # separated by what the message quotes rather than by whether it quotes anything.
    told = _DeployedPage(
        recorded,
        revision=1,
        presented_at=1_400.0,
        status="Claude is handling 1 update",
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


def test_journey_reads_and_times_inline_message_title():
    comment, _title, reply = TURN_LOG
    titled_reply = {**reply, "title": "Release recorded"}
    assert journey.title([comment, titled_reply], comment["id"]) == "Release recorded"
    assert (
        journey.recorded_steps(
            [comment, titled_reply], comment, {"activated_at": reply["ts"]}
        )["titled"]
        == 12.5
    )
    titled_comment = {**comment, "title": "Initial release"}
    assert (
        journey.recorded_steps(
            [titled_comment, titled_reply],
            titled_comment,
            {"activated_at": reply["ts"]},
        )["titled"]
        == 0
    )


def test_journey_title_timing_accepts_admitted_action_dependencies():
    comment, _title, reply = TURN_LOG
    action = {
        "kind": "action",
        "id": "test-pick",
        "widget": "options",
        "action": "choose",
        "revision": 1,
        "ts": "2026-10-04T12:00:01.000-07:00",
        "meaning": {"unit": "options", "depends": ["child"], "scope": "page"},
    }
    events = [comment, action, {**reply, "title": "Release recorded"}]
    assert (
        journey.recorded_steps(events, comment, {"activated_at": reply["ts"]})["titled"]
        == 12.5
    )


def test_saved_state_verifier_fixture_returns_the_admitted_event_ids(
    page_dir, tmp_path, monkeypatch
):
    """Run the exact container fixture through its real admission API."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="heat-first" choose>').replace(
            'id="backfill-first"', 'id="heat-opt-window"'
        )
    )
    site = tmp_path / "site"
    private = site / "page"
    shutil.copytree(page_dir, private)
    write_manifest(site, {"/examples/heat-loss": ("page", "example")})
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site))
    monkeypatch.delenv("LEAF_PAGE_COMMIT", raising=False)
    result = subprocess.run(
        [sys.executable, "-c", verify_site.SAVED_STATE_FIXTURE],
        check=False,
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
    )
    assert result.returncode == 0, result.stderr
    seeded = json.loads(result.stdout)
    events = {event["id"]: event for event in read_events(private)}
    assert events[seeded["choice"]]["detail"]["value"] == ["heat-opt-window"]
    assert events[seeded["comment"]]["text"] == "Saved before the container stopped."
    assert seeded["revision_name"] == revision_path(private, seeded["revision"]).name
    assert (private / "page/saved-state-recall.css").read_text() == seeded["stylesheet"]


def test_the_local_adapter_owns_its_process_and_disposable_codex_home(
    tmp_path, monkeypatch
):
    """Exercise real build/process/file ownership with a stand-in for the hosted agent."""
    root = tmp_path / "checkout"
    (root / "worker").mkdir(parents=True)
    host_home = tmp_path / "host-codex"
    host_home.mkdir()
    (host_home / "auth.json").write_text('{"test": "login"}')
    (host_home / "auth.json").chmod(0o600)
    (root / "worker" / "codex-config.toml").write_text('model = "test"')
    # Each invocation builds directly into its private site destination.
    build_site = tmp_path / "build_site.py"
    build_site.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "site = Path(sys.argv[sys.argv.index('--output') + 1]) / '_leaf'\n"
        "site.mkdir(parents=True)\n"
        "(site / 'site.json').write_text('{\"release\": \"' + 'a' * 40 + '\"}')\n"
        "install = site.parent.with_name(site.parent.name + '-install')\n"
        "(install / '.agents/plugins').mkdir(parents=True)\n"
        "(install / '.agents/plugins/marketplace.json').write_text('{\"name\": \"leaf\"}')\n"
        "(install / '.venv').mkdir()\n"
        "print('built the site')\n"
    )
    codex = tmp_path / "codex"
    codex.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "home = Path(os.environ['CODEX_HOME'])\n"
        "assert (home / 'auth.json').read_text() == '{\"test\": \"login\"}'\n"
        "assert (home / 'config.toml').read_text() == 'model = \"test\"'\n"
        "assert os.environ.get('LEAF_CODEX_APP_SERVER') is None\n"
        "record = home / 'plugin-install.jsonl'\n"
        "args = sys.argv[1:]\n"
        "if args[:3] == ['plugin', 'marketplace', 'add']:\n"
        "    assert args[-1] == '--json'\n"
        "    plugin = Path(args[3])\n"
        "    assert plugin.parent == home.parent\n"
        "    assert json.loads((plugin / '.agents/plugins/marketplace.json').read_text())['name'] == 'leaf'\n"
        "    assert not (plugin / '.venv').exists()\n"
        "    assert not record.exists()\n"
        "    response = {}\n"
        "else:\n"
        "    assert args == ['plugin', 'add', 'leaf@leaf', '--json']\n"
        "    assert len(record.read_text().splitlines()) == 1\n"
        "    response = {'installedPath': str(home / 'plugins/cache/leaf/leaf/local')}\n"
        "    launcher = Path(response['installedPath']) / 'bin/leaf'\n"
        "    launcher.parent.mkdir(parents=True)\n"
        "    launcher.write_text('#!/bin/sh\\nexit 0\\n')\n"
        "    launcher.chmod(0o755)\n"
        "with record.open('a') as output:\n"
        "    output.write(json.dumps(args) + '\\n')\n"
        "print(json.dumps(response, indent=2))\n"
    )
    codex.chmod(0o755)
    serve_site = tmp_path / "serve_site.py"
    serve_site.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "assert len((Path(os.environ['CODEX_HOME']) / 'plugin-install.jsonl').read_text().splitlines()) == 2\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.end_headers()\n"
        "        self.wfile.write(json.dumps(dict(pid=os.getpid(), home=os.environ['CODEX_HOME'], site=os.environ['LEAF_SITE_ROOT'], endpoint=os.environ.get('LEAF_CODEX_APP_SERVER'))).encode())\n"
        "server = HTTPServer(('127.0.0.1', 0), Handler)\n"
        "print(json.dumps(dict(event='container_http_ready', port=server.server_port)), flush=True)\n"
        "server.serve_forever()\n"
    )
    monkeypatch.setattr(verify_site, "ROOT", root)
    monkeypatch.setattr(verify_site, "BUILD_SITE", [sys.executable, str(build_site)])
    monkeypatch.setattr(
        verify_site, "serve_site", lambda install: [sys.executable, str(serve_site)]
    )
    monkeypatch.setenv("CODEX_HOME", str(host_home))
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("LEAF_CODEX_APP_SERVER", "unix:///another-session.sock")
    with (
        pytest.raises(RuntimeError, match="journey failed"),
        verify_site.local_adapter() as (origin, release),
        verify_site.local_adapter() as (other_origin, other_release),
    ):
        assert release == "a" * 40
        assert other_release == release
        assert origin != other_origin
        body, _ = get(f"{origin}/health")
        running = json.loads(body)
        other_body, _ = get(f"{other_origin}/health")
        other = json.loads(other_body)
        assert running["endpoint"] is None
        assert other["endpoint"] is None
        assert other["pid"] != running["pid"]
        assert other["home"] != running["home"]
        assert other["site"] != running["site"]
        private_home = Path(running["home"])
        private_site = Path(running["site"])
        assert private_home != host_home
        assert (private_home / "auth.json").read_bytes() == (
            host_home / "auth.json"
        ).read_bytes()
        assert (private_home / "auth.json").stat().st_mode & 0o777 == 0o600
        # A refresh in one isolated child must reach the host and other children.
        (private_home / "auth.json").write_text('{"test": "refreshed"}')
        assert (host_home / "auth.json").read_text() == '{"test": "refreshed"}'
        assert (Path(other["home"]) / "auth.json").read_text() == (
            '{"test": "refreshed"}'
        )
        assert (private_home / "config.toml").read_text() == 'model = "test"'
        installed = [
            json.loads(line)
            for line in (private_home / "plugin-install.jsonl").read_text().splitlines()
        ]
        assert installed == [
            [
                "plugin",
                "marketplace",
                "add",
                str(private_home.parent / "leaf-plugin"),
                "--json",
            ],
            ["plugin", "add", "leaf@leaf", "--json"],
        ]
        assert private_site != root / ".tmp" / "site"
        assert (private_site / "_leaf" / "site.json").exists()
        raise RuntimeError("journey failed")
    assert not private_home.exists()
    assert not private_site.exists()
    assert not Path(other["home"]).exists()
    assert not Path(other["site"]).exists()
    assert (
        len(list((root / ".tmp" / "verify-site").glob("run-*/website-adapter.log")))
        == 2
    )
    assert (host_home / "auth.json").read_text() == '{"test": "refreshed"}'
    with pytest.raises(ProcessLookupError):
        os.kill(running["pid"], 0)


def test_the_direct_agent_handoff_runs_the_local_adapter_workflow():
    class Requests:
        def __init__(self):
            self.request = self
            self.posts = []

        def post(self, url, data, **options):
            self.posts.append((url, data))
            return _Read({"status": "started"})

    context = Requests()
    verify_site.start_direct_agent(
        context,
        "http://127.0.0.1:8080/examples/triage-board/",
        {"id": "comment-id"},
    )

    assert context.posts == [
        (
            "http://127.0.0.1:8080/examples/triage-board/_leaf/agent/start",
            {"event": "comment-id"},
        ),
    ]
