"""The website container's routes and Codex harness, with the helpers its product
test modules share."""

import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import leaf_website as website_server
import pytest
from interact_support import route_answer_error

from leaf.codex import accept_codex_delivery, delivery_records
from leaf.codex_state import delivery_lock_path
from leaf.state import flocked, open_session_turn, session_record, start_session_turn

ROOT = Path(__file__).parents[3]


def accept_in_turn(thread_id: str, turn: str = "app-server-turn") -> None:
    """Open the provider turn and accept the offered delivery into it, as
    `HostedTurn.begin` does."""
    assert start_session_turn(thread_id, turn, session_record(thread_id))
    assert open_session_turn(thread_id, turn)
    with flocked(delivery_lock_path(thread_id)):
        [(path, _)] = [
            (path, record)
            for path, record in delivery_records(thread_id)
            if record.state == "offering"
        ]
    accept_codex_delivery(thread_id, path.stem, turn)


@pytest.fixture(name="_no_harness_outlives_its_test", autouse=True)
def _no_harness_outlives_its_test_fixture(monkeypatch):
    """Close every website harness a test made, as `_no_page_outlives_its_test` stops
    every page server.

    Closing stops the App Server a harness started and releases the waiter lease it
    holds over a Codex thread. The harness is the subject here, built in each test
    body with the paths that test needs, so the sweep takes every construction
    rather than routing them through a fixture. `close` is idempotent, so a test
    whose subject is closing still closes where its assertion reads the result.
    """
    made = []

    class Swept(website_server.WebsiteCodexHarness):
        def __init__(self, *arguments, **named):
            super().__init__(*arguments, **named)
            made.append(self)

    monkeypatch.setattr(website_server, "WebsiteCodexHarness", Swept)
    yield
    for harness in made:
        harness.close()


# The response headers as the message, not a plain dict: header names are
# case-insensitive and arrive lowercased, as they do in a browser.
def get(url: str) -> tuple[bytes, Message]:
    with urllib.request.urlopen(url) as response:
        return response.read(), response.headers


def post(url: str, body: dict, headers: dict | None = None) -> tuple[dict, Message]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request) as response:
        raw = response.read()
    if error := route_answer_error(url, raw):
        raise AssertionError(f"{url} answered outside its schema: {error}")
    return json.loads(raw), response.headers


def write_manifest(site: Path, pages: dict[str, tuple[str, str]]) -> None:
    """Give a focused server fixture the same generated routing authority as a build."""
    manifest = {
        "release": "0" * 64,
        "pages": {
            route: {
                "directory": directory,
                "assets": f"/_leaf-release/{'0' * 64}/{route.strip('/').replace('/', '--') or 'root'}",
                "states": {},
                "kind": kind,
                "title": f"The {route} page",
                "description": f"What a user does at {route}.",
                "image": "/media/card.png",
            }
            for route, (directory, kind) in pages.items()
        },
    }
    target = site / website_server.SITE_MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest), encoding="utf-8")


def hosted_follower(
    harness,
    page_dir,
    prepared,
    socket=None,
    *,
    turn_id: str = "app-server-turn",
    thread_id: str = "hosted-thread",
    reply_target=None,
):
    """Build the follower a dispatch builds, for a delivery a test prepared.

    A follower is made from one `turn/start` answer on one connection, so a test
    gives it the same three things the dispatch does: the delivery it sent, the
    turn App Server named for it, and the connection that named it. Opening the
    Leaf turn stays the follower's own first step.
    """
    admitted = start_session_turn(thread_id, turn_id, session_record(thread_id))
    assert admitted is not None
    return website_server.HostedTurn(
        harness,
        page_dir,
        thread_id,
        prepared.payload["id"],
        tuple(
            event["id"]
            for batch in prepared.payload["batches"]
            for event in batch["events"]
        ),
        turn_id,
        socket,
        reply_target=(
            website_server.stream_reply_target(prepared.payload)
            if reply_target is None
            else reply_target
        ),
        lifecycle=admitted,
    )


class FakeCodexHarness:
    def __init__(self):
        self.attached = []

    def attach(self, page_dir: Path, event_id: str) -> str | None:
        inputs = website_server.pending_agent_inputs(page_dir)
        if event_id not in inputs:
            return None
        thread_id = inputs[event_id]
        if thread_id is not None:
            return thread_id
        self.attached.append(page_dir)
        return "codex-thread"

    def failure_receipt(
        self, page_dir: Path, event_id: str, failure: str
    ) -> dict | None:
        return website_server.WebsiteCodexHarness("codex").failure_receipt(
            page_dir, event_id, failure
        )
