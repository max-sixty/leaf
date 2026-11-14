"""HTTP event and service-address tests."""

import http.client
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

from click.testing import CliRunner
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    TOKEN,
    append_carried_log_record,
    check,
    declare,
    declare_work,
    end_work,
    fetch,
    neighbour_page,
    page_packages,
    publish,
    read_record,
    record_claim,
    revision_root,
    wait_for,
    write_record,
)

from leaf import cli as cli_model
from leaf import event_log as event_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import presence as presence_model
from leaf import render_checks as render_checks_model
from leaf import revision_artifact as artifact_model
from leaf import revisioning as revisioning_model
from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf.registry import storage as registry_storage
from leaf_dev.page_fixtures import package_selection_args


def test_authored_recordings_are_served_with_seekable_captured_bytes(
    server, page_dir, tmp_path
):
    """Author admission, MIME and ranges work before and after revision capture.

    The author chooses the type; these deliberately arbitrary bytes exercise transport
    independently from codec support, which the browser playback test owns.
    """
    data = b"0123456789"
    paths = []
    for suffix, mime in {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
    }.items():
        source = tmp_path / ("recording" + suffix.upper())
        source.write_bytes(data)
        path = media_model.cmd_media(page_dir, [source])[0]["path"]
        paths.append((path, mime))
    markup = "".join(f'<audio controls src="{path}"></audio>' for path, _ in paths)
    (page_dir / "index.html").write_text(PAGE.replace("</main>", markup + "</main>"))
    publish(page_dir)
    captured = revision_root(page_dir, 1)
    for path, mime in paths:
        for route in (path, captured + path):
            conn = http.client.HTTPConnection(urllib.parse.urlsplit(server).netloc)
            try:
                for requested, status, expected, content_range in [
                    (None, 200, data, None),
                    ("bytes=2-5", 206, data[2:6], "bytes 2-5/10"),
                ]:
                    headers = {"Range": requested} if requested else {}
                    conn.request("GET", route + f"?t={TOKEN}", headers=headers)
                    answer = conn.getresponse()
                    assert (answer.status, answer.read()) == (status, expected)
                    assert answer.getheader("Content-Type") == mime
                    assert answer.getheader("Accept-Ranges") == "bytes"
                    assert answer.getheader("Content-Range") == content_range
                conn.request(
                    "GET",
                    route + f"?t={TOKEN}",
                    headers={"Range": "bytes=2-5", "If-Range": '"other"'},
                )
                answer = conn.getresponse()
                assert (answer.status, answer.read()) == (200, data)
                conn.request(
                    "HEAD", route + f"?t={TOKEN}", headers={"Range": "bytes=2-5"}
                )
                answer = conn.getresponse()
                assert (
                    answer.status,
                    answer.read(),
                    answer.getheader("Content-Length"),
                ) == (206, b"", "4")
                conn.request("GET", route)
                answer = conn.getresponse()
                assert answer.status == 401
                answer.read()
            finally:
                conn.close()
    # Historical media must use its capture even if the page's mutable file changes.
    path, _ = paths[0]
    (page_dir / path.lstrip("/")).write_bytes(b"changed")
    assert fetch(server + captured + path, headers={"Range": "bytes=2-5"}) == (
        206,
        data[2:6],
    )


def test_server_round_trip(server, page_dir):
    registry = registry_storage.load_registry(page_dir)
    initial = revisioning_model.activate_source(page_dir)
    assert initial.error is None and initial.revision == 1
    source = page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace("</section>", registry["lf-board"]["x-example"] + "\n</section>")
        .replace(
            "</head>",
            '<style>.probe::before { content: "</head>"; }</style>\n</head>',
        )
    )
    # A valid save is live immediately, while no public stamp exists yet.
    status, draft = fetch(f"{server}/")
    assert status == 200 and b"lf-board" in draft
    status, _ = fetch(f"{server}/versions/v1.html")
    assert status == 404
    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "cut"]
    )
    assert stamped.exit_code == 0, stamped.output
    # The handover address is the live page, not a pinned revision address.
    # It stays put while the browser adopts later versions, so the first response
    # must contain the version itself rather than redirecting the address away.
    peer = http.client.HTTPConnection(
        urllib.parse.urlsplit(server).netloc, timeout=STATED_TIMEOUT
    )
    peer.request("GET", f"/?t={TOKEN}")
    arrived = peer.getresponse()
    body = arrived.read()
    assert arrived.status == 200 and arrived.getheader("Location") is None
    assert arrived.getheader("Content-Security-Policy") == "frame-ancestors 'self'"
    assert arrived.getheader("X-Content-Type-Options") == "nosniff"
    peer.close()
    status = arrived.status
    assert status == 200 and b"lf-options" in body
    artifact = artifact_model.read_artifact(page_dir, 2)
    marker = (
        '<meta name="lf-revision" content="2" data-lf-runtime>'
        f'<meta name="lf-executable" content="{artifact.executable}" data-lf-runtime>'
        '<meta name="lf-version" content="1" data-lf-runtime>'
    ).encode()
    artifact_root = revision_root(page_dir, 2)
    entry = (
        f'<script type="module" src="{artifact_root}/leaf.js" data-lf-runtime></script>'
    ).encode()
    assert marker in body
    assert body.index(marker) < body.index(entry) < body.index(b"<style>.probe::before")
    # Historical source remains delivery-free; today's boundary is applied when read.
    with urllib.request.urlopen(f"{server}/versions/v1.html?t={TOKEN}") as response:
        pinned = response.read()
        assert response.status == 200
        assert response.headers["Content-Security-Policy"] == "frame-ancestors 'self'"
    assert b"lf-board" in pinned and marker in pinned
    assert not (page_dir / "versions").exists()
    # The vocabulary and the runtime's probes serve; the log and directory paths
    # don't.
    for path in [
        "/registry.json",
        *render_checks_model.PROBE_SOURCES,
    ]:
        assert fetch(server + path)[0] == 200, path
    for path in [
        "/events.jsonl",
        "/vendor/..",
        "/stream.json",
        "/../secret",
    ]:
        assert fetch(server + path)[0] == 404, path
    outside = page_dir.parent / "outside.js"
    outside.write_text("not part of the page")
    (page_dir / "vendor").mkdir(exist_ok=True)
    (page_dir / "vendor" / "escape.js").symlink_to(outside)
    for path in ["/vendor/../../outside.js", "/vendor/escape.js"]:
        peer = http.client.HTTPConnection(
            urllib.parse.urlsplit(server).netloc, timeout=STATED_TIMEOUT
        )
        peer.request("GET", f"{path}?t={TOKEN}")
        refused = peer.getresponse()
        refused.read()
        assert refused.status == 404, path
        peer.close()
    # A browser-posted comment lands stamped author=user, with a server-minted id
    # (client ids are dropped — a reused one would re-root an existing thread).
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "id": "c9",
                "author": "agent",
                "agent": "Codex",
                "session": "s-forged",
                "ts": "1900-01-01T00:00:00Z",
                "seq": 99,
                "revision": 2,
                "text": "hm",
            }
        ).encode(),
    )
    assert status == 200, body
    posted = event_model.read_events(page_dir)[-1]
    assert posted["author"] == "user" and posted["id"] != "c9"
    assert "agent" not in posted and "session" not in posted
    assert posted["ts"] != "1900-01-01T00:00:00Z"
    assert posted["seq"] != 99
    status, body = fetch(f"{server}/api/state")
    state = json.loads(body)
    assert state["versions"] == [
        {"version": 1, "revision": 2, "url": "/versions/v1.html"}
    ]
    assert state["cursor"] == 0  # no user event acknowledged yet
    assert state["events"][-1]["id"] == posted["id"]
    # A widget action rides the same channel; half-formed ones are refused at the edge.
    # A move is made on the newest revision, which the vendored file above made r3.
    newest = files_model.list_revisions(page_dir)[-1]
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": newest,
                "widget": "feeder-board",
                "action": "move",
                "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
            }
        ).encode(),
    )
    assert status == 200
    moved = event_model.read_events(page_dir)[-1]
    assert moved["author"] == "user" and moved["detail"]["value"] == "col-doing"
    # A design comment names the control the press landed on beside the widget it is
    # about. The door takes its design intent as posted.
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "revision": 2,
                "text": "the grip reads dim",
                "about": "design",
                "anchor": {"section": "feeder-board", "part": "grip"},
            }
        ).encode(),
    )
    assert status == 200
    design = event_model.read_events(page_dir)[-1]
    assert design["about"] == "design" and design["anchor"]["part"] == "grip"
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "revision": 2,
                "text": "Keep this control readable",
                "about": "design",
                "anchor": {
                    "section": "feeder-board",
                    "part": "grip",
                    "quote": "Remove",
                },
            }
        ).encode(),
    )
    assert status == 200
    quoted = event_model.read_events(page_dir)[-1]["anchor"]
    assert (quoted["quote"], quoted["part"]) == ("Remove", "grip")
    drawing = {
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
        "box": [640.5, 96],
        "frame": {
            "root": "figure",
            "path": [{"tag": "svg", "index": 0, "siblings": 1}],
        },
        "says": "to reap every process … before exporting",
        "viewport": [1280, 720],
        "scheme": "dark",
    }
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "revision": 2,
                "anchor": {"section": "feeder-board"},
                "drawing": drawing,
            }
        ).encode(),
    )
    assert status == 200
    drawn = event_model.read_events(page_dir)[-1]
    assert drawn["drawing"] == drawing
    assert "text" not in drawn
    for bad in [
        {"kind": []},
        {"kind": "action", "action": "move"},  # no widget
        {"kind": "action", "widget": "", "action": "move", "detail": {}, "revision": 2},
        {"kind": "action", "widget": "b", "action": "move", "revision": 2},  # no detail
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": None,
            "revision": 2,
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "revision": "2",
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "revision": True,
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "revision": 0,
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "revision": 3,
        },
        {"kind": "comment", "revision": 2},  # no text, token, or drawing
        {
            "kind": "comment",
            "revision": 2,
            "token": "keep",
            "anchor": {"section": "feeder-board"},
            "drawing": drawing,
        },
        {"kind": "comment", "revision": 2, "text": "x", "anchor": "intro"},
        {"kind": "comment", "revision": 2, "text": "x", "anchor": {"quote": 7}},
        {"kind": "comment", "revision": 2, "text": "x", "anchor": {}},
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"datum": "row-1", "quote": "x"},
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"quote": "x", "extra": "y"},
        },
        {"kind": "comment", "revision": 2, "text": "x", "suggestion": "yes"},
        {"kind": "comment", "revision": 2, "text": "x", "attempt": "short"},
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {
                "strokes": [[[10, 60]]],
            },
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {
                "strokes": [[[10], [50, 20]]],
            },
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {
                "strokes": [[[10, 60], [33554433, 20]]],
            },
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"quote": "this passage"},
            "drawing": drawing,
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board", "part": "Move"},
            "drawing": drawing,
        },
        {
            "kind": "comment",
            "revision": 2,
            "anchor": {"section": "feeder-board"},
            "drawing": {
                **drawing,
                "frame": {"root": "figure", "path": [{"tag": "svg", "index": 0}]},
            },
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {**drawing, "strokes": [[[0.1, 0.2]] * 257]},
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {**drawing, "strokes": []},
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {**drawing, "strokes": drawing["strokes"] * 33},
        },
        {
            "kind": "comment",
            "revision": 2,
            "text": "x",
            "anchor": {"section": "feeder-board"},
            "drawing": {**drawing, "strokes": [[[float("nan"), 0.2], [0.5, 0.2]]]},
        },
        # Every drawing stands on an element, whose box its offsets are measured in.
        {"kind": "comment", "revision": 2, "drawing": drawing},
        # The box and the window are sizes, the words are bounded and the scheme is one
        # of two: all come off the rendered page, so their shape is all the door can
        # hold them to. The box and the window are always recorded, since the agent
        # reads the strokes against the one and its picture is laid out in the other.
        *(
            {
                "kind": "comment",
                "revision": 2,
                "text": "x",
                "anchor": {"section": "feeder-board"},
                "drawing": {**drawing, **wrong},
            }
            for wrong in (
                {"box": [640.5, 0]},
                {"box": [640.5]},
                {"box": [640.5, 96, 1]},
                {"says": ""},
                {"says": "x" * 501},
                {"says": ["to reap"]},
                {"viewport": [1280, 0]},
                {"viewport": [1280]},
                {"scheme": "sepia"},
            )
        ),
        *(
            {
                "kind": "comment",
                "revision": 2,
                "text": "x",
                "anchor": {"section": "feeder-board"},
                "drawing": {
                    key: value for key, value in drawing.items() if key != missing
                },
            }
            for missing in ("box", "viewport", "scheme")
        ),
        # Design is the field's only subject: the retired ownership alias and a browser
        # inventing a second subject are both refused at the door.
        {"kind": "comment", "revision": 2, "text": "x", "about": "layer"},
        {"kind": "comment", "revision": 2, "text": "x", "about": "page"},
        {"kind": "comment", "revision": 2, "text": "x", "about": True},
        {
            "kind": "reply",
            "parent": posted["id"],
            "revision": 2,
            "text": "hi",
            "suggestion": True,
        },
        {
            "kind": "reply",
            "parent": posted["id"],
            "revision": 2,
            "text": "hi",
            "anchor": {"section": "plan"},
        },
        {"kind": "reply", "parent": "nope", "revision": 2, "text": "hi"},
        {"kind": "resolve", "parent": "nope"},
        # A report is agent-authored: its one door is `leaf page report`,
        # so the browser door refuses the kind outright rather than minting user
        # events that outrank nothing.
        {
            "kind": "report",
            "widget": "feeder-board",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-doing", "rank": "0i"},
            "revision": 2,
        },
        # A revision names a message the log holds.
        {
            "kind": "edit",
            "message": "no-such-message",
            "text": "rewritten in the browser",
        },
        ["not", "an", "object"],
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, bad
        answer = json.loads(body)
        assert answer["ok"] is False and answer["final"] is True, bad

    status, body = fetch(f"{server}/api/event", data=b"{")
    assert status == 400, body
    assert json.loads(body) == {
        "ok": False,
        "error": "invalid JSON",
        "findings": [],
        "final": True,
    }


def test_the_live_root_places_its_delivery_at_the_parsers_head_boundary(
    server, page_dir
):
    """A Unicode separator and indented close must not shift head insertion."""
    # Keep the separator escaped so normalization cannot silently weaken the fixture.
    source = PAGE.replace(
        "<title>t</title>", "<title>Backfill plan\u2028Q3</title>"
    ).replace("</head>", "  </head>")
    (page_dir / "index.html").write_text(source, encoding="utf-8")
    assert check(page_dir).exit_code == 0
    publish(page_dir)

    body = fetch(f"{server}/")[1].decode()

    artifact = artifact_model.read_artifact(page_dir, 1)
    marker = (
        '<meta name="lf-revision" content="1" data-lf-runtime>'
        f'<meta name="lf-executable" content="{artifact.executable}" data-lf-runtime>'
        '<meta name="lf-version" content="1" data-lf-runtime>'
    )
    assert body.count(marker) == 1
    assert '<head><meta charset="utf-8" data-lf-runtime>' + marker in body
    assert "Backfill plan\u2028Q3" in body
    assert "<title>Backfill plan\u2028Q3</title>" in body
    # The old splice corrupted this tag while leaving the page renderable.
    artifact_root = revision_root(page_dir, 1)
    theme = structure_model.SourceDocument(body).tree.find(
        "link", attrs={"href": f"{artifact_root}/theme.css"}
    )
    assert theme is not None
    assert theme.attrs["rel"] == ["stylesheet"]
    assert "data-lf-runtime" in theme.attrs


def test_server_admits_an_action_using_its_captured_vocabulary_after_revendoring(
    server, page_dir
):
    """An open old tab may outlive the selection of the package that upgraded its
    widget."""
    shipped = registry_storage.load_registry(page_dir)
    overlay = page_dir.parent / ".leaf"
    (overlay / "widgets").mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-local-draft": shipped["lf-draft"]})
    )
    (overlay / "widgets" / "lf-local-draft.js").write_text(
        "customElements.define('lf-local-draft', class extends HTMLElement {});"
    )
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "page",
                "init",
                *package_selection_args((*page_packages(), "./.leaf")),
                str(page_dir),
            ],
        )
        .exit_code
        == 0
    )
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-local-draft id="local-draft"><pre>Words.</pre>'
            "</lf-local-draft>",
        )
    )
    noted = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "stamp",
            str(page_dir),
            "--text",
            "custom widget",
        ],
    )
    assert noted.exit_code == 0, noted.output

    # The explicit re-selection is allowed because no recorded action rests on this
    # tag yet. A browser that loaded it before can still send one.
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "page",
                "init",
                *package_selection_args(page_packages()),
                str(page_dir),
            ],
        )
        .exit_code
        == 0
    )

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": files_model.latest_revision(page_dir),
                "widget": "local-draft",
                "action": "edit",
                "detail": {"value": "New words."},
            }
        ).encode(),
    )

    assert status == 200, body
    event = json.loads(body)["state"]["events"][-1]
    assert event["widget"] == "local-draft"
    assert event["detail"] == {"value": "New words."}


def test_a_server_keeps_its_row_fresh_without_browser_visits(page_dir, spawn):
    """Own file changes, watcher and agent lifetime reach other pages with no tab.

    The agent exits normally while the persistent server continues. Releasing the
    server lease then removes its row from the next reading, which retires the file.
    """
    neighbor = cleanup_model.state_home() / "pages" / "invisible"
    neighbour_page(neighbor, title="Invisible", dead=True, port=0)
    agent = spawn(
        [sys.executable, "-c", "input()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    record_claim(neighbor, id="invisible", pid=agent.pid, cwd="/work/invisible")
    declare(neighbor)
    declare_work(neighbor, "measuring", ts=cleanup_model.now_iso())
    hosting_model.start_server(neighbor, persistent=True, harness=None)

    def rows():
        return presence_model.other_leaves(page_dir)

    def await_row(accepts):
        return wait_for(
            rows,
            lambda values: len(values) == 1 and accepts(values[0]),
            failure="the invisible page's canonical row did not refresh",
        )[0]

    row = await_row(lambda row: row["activity"]["state"] == "running")
    assert row["session_cwd"] == "/work/invisible"
    source = neighbor / "index.html"
    source.write_text(
        source.read_text().replace(
            "<title>Invisible</title>", "<title>Revised unseen</title>"
        )
    )
    append_carried_log_record(
        neighbor, {"kind": "comment", "author": "user", "text": "why?"}
    )
    await_row(
        lambda row: (
            row["title"] == "Revised unseen"
            and row["activity"]["counts"]["unseen"] == 1
        )
    )
    end_work(neighbor)
    declare(neighbor, "waiting")
    session = cleanup_model.session_record("invisible")
    assert session is not None
    cleanup_model.write_session({**session, "turn_closed": cleanup_model.now_iso()})
    await_row(lambda row: row["activity"]["presence"] == "away")
    # The harness's dialog changes outside the page, with no lifecycle rewrite.
    harness_record = harness_model.claude_code_sessions() / f"{agent.pid}.json"
    harness_record.parent.mkdir(parents=True, exist_ok=True)
    cleanup_model.write_json(
        harness_record,
        {
            "pid": agent.pid,
            "sessionId": "invisible",
            "status": "waiting",
            "statusUpdatedAt": int((time.time() + 1) * 1000),
        },
    )
    await_row(lambda row: row["activity"]["observed_kind"] == "awaiting_user")
    harness_record.unlink()
    await_row(lambda row: row["activity"]["presence"] == "away")
    lease_path = leases_model.waiter_lease_path(neighbor, "invisible")
    assert lease_path is not None
    waiter = leases_model.take_wait_lease(lease_path)
    try:
        await_row(lambda row: row["activity"]["presence"] == "here")
    finally:
        leases_model.release_lease(waiter)
    await_row(lambda row: row["activity"]["presence"] == "away")
    agent.stdin.write(b"done\n")
    agent.stdin.flush()
    agent.wait(timeout=STATED_TIMEOUT)
    await_row(lambda row: row["activity"]["kind"] == "unheld")
    assert server_model.running_server(neighbor)
    hosting_model.cmd_stop(neighbor)
    assert rows() == []
    assert not server_rows_model.row_path(neighbor).exists()


def test_state_ships_the_machines_other_live_leaves(page_dir, server, tmp_path):
    """Both discovery homes supply compact publications of live server owners.

    Dead servers stay out; a corrupt neighbor cannot make this page parse its
    source. The retained output of that neighbor is independently readable.
    """
    pages = cleanup_model.state_home() / "pages"
    live_url = neighbour_page(pages / "live", title="The other page")
    declare(pages / "live", ts="2026-01-01T00:00:00-08:00")
    declare_work(pages / "live", "measuring", ts="2026-01-01T00:00:00-08:00")
    record_claim(
        pages / "live",
        id="s9",
        agent="Codex",
        cwd="/work/api",
        turn_opened="2026-01-01T00:00:00-08:00",
    )
    # A server that died leaves its record behind and its lock with the kernel:
    # the file says served and nothing holds it, which is what reads as stale.
    neighbour_page(pages / "dead", title="A dead server's page", dead=True)
    draft_url = neighbour_page(
        pages / "unpublished", title="Nothing to link", published=False
    )
    # A neighbour something corrupted: its log no longer parses, and the fault
    # stays its own — skipped, rather than 500ing every other page's poll.
    corrupt_url = neighbour_page(pages / "corrupt", title="A corrupted page")
    (pages / "corrupt" / "events.jsonl").write_text('{"kind": "note", "author"')
    # Presence belongs to the same isolation boundary as the log and version. A
    # stream record carrying a field no version reads, as an older leaf's work list,
    # must not make this page's poll fail: the field is ignored.
    malformed = pages / "malformed-stream"
    neighbour_page(malformed, title="Malformed stream")
    declare(malformed)
    write_record(malformed / "stream.json", {"work": [{}]})
    # A page served from a session's scratch directory, plus the asking page
    # itself: the claim index finds the first, and the second stays out of its own
    # list. Untitled, so the title falls back to the directory's name.
    scratch = tmp_path / "scratch"
    claimed_url = neighbour_page(scratch)
    record_claim(scratch, turn_opened="2026-01-01T00:00:00-08:00")

    for directory in (pages / "live", malformed, scratch):
        server_rows_model.RowPublisher(directory, "fixture-server").refresh()
    state = json.loads(fetch(f"{server}/api/state")[1])
    rows = {row["title"]: row for row in state["others"]}
    assert list(rows) == [
        "A corrupted page",
        "Malformed stream",
        "Nothing to link",
        "scratch",
        "The other page",
    ]
    assert rows["A corrupted page"]["url"] == corrupt_url
    assert rows["Nothing to link"]["url"] == draft_url
    assert rows["scratch"]["url"] == claimed_url
    assert rows["The other page"]["url"] == live_url
    assert rows["The other page"]["session_cwd"] == "/work/api"
    assert rows["The other page"]["activity"]["kind"] == "away"
    assert rows["Malformed stream"]["activity"]["kind"] == "away"
    assert all("obligations" not in row["activity"] for row in rows.values())


def test_neighbours_follow_their_servers_and_ignore_deleted_pages(page_dir, tmp_path):
    """A neighbour leaves on the read after its server stops, though nothing moves
    a file the candidate set is keyed on, and that read retires its row until the
    next server publishes one. A page whose directory is gone disappears on the
    next scan, whether it went before the first scan or after one had listed it."""
    stopped = tmp_path / "stopped"
    neighbour_page(stopped, title="Starts later", dead=True)
    record_claim(stopped, id="later")
    scratch = tmp_path / "scratch"
    neighbour_page(scratch, title="Scratch")
    record_claim(scratch, id="scratch")
    deleted = tmp_path / "deleted"
    neighbour_page(deleted, title="Deleted", dead=True)
    record_claim(deleted, id="deleted")
    shutil.rmtree(deleted)

    def titles():
        return [entry["title"] for entry in presence_model.other_leaves(page_dir)]

    assert titles() == ["Scratch"]
    assert service_model.claim_path(deleted).exists()
    assert service_model.claim_path(stopped).exists()

    lease = leases_model.take_lease(stopped / "server.lock")
    lease.write(read_record(stopped / "service.json")["server_id"].encode())
    lease.flush()
    assert titles() == ["Scratch"]
    server_rows_model.RowPublisher(stopped, "fixture-server").refresh()
    assert titles() == ["Scratch", "Starts later"]
    leases_model.release_lease(lease)
    assert titles() == ["Scratch"]

    shutil.rmtree(stopped)
    assert titles() == ["Scratch"]
    assert service_model.claim_path(stopped).exists()


def test_concurrent_posts_never_tear_the_log(server, page_dir):
    publish(page_dir)

    def post(i):
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "revision": 1, "text": f"c{i} " + "x" * 500}
            ).encode(),
        )

    threads = [threading.Thread(target=post, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events = [e for e in event_model.read_events(page_dir) if e["kind"] == "comment"]
    assert {e["text"].split()[0] for e in events} == {f"c{i}" for i in range(20)}
    assert len({e["id"] for e in events}) == 20  # server-minted, all distinct


import shlex
import socket
from contextlib import contextmanager

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    release_codex_command,
    retire_test_services,
    vendored_at_another_protocol,
)

from leaf import codex_adapter as codex_adapter_model
from leaf import schema as schema_model


def test_a_failed_row_producer_retires_and_revives_with_its_service(page_dir):
    """A failed fold cannot leave a live lease advertising stale canonical output.

    Repairing the invalid input then uses the existing enabled-service revival,
    with a new serving identity and a newly computed row.
    """
    neighbor = cleanup_model.state_home() / "pages" / "broken-row"
    neighbour_page(neighbor, title="Repairable", dead=True, port=0)
    hosting_model.start_server(neighbor, persistent=True, harness=None)
    wait_for(
        lambda: (
            (current := server_model.running_server(neighbor))
            and server_rows_model.read_row(neighbor, current)
        ),
        bool,
        failure="the server did not publish a row",
    )
    original = server_model.running_server(neighbor)
    assert original is not None
    (neighbor / "stream.json").write_text("{invalid")
    wait_for(
        lambda: server_model.running_server(neighbor),
        lambda service: service is None,
        failure="the failed producer left a live server lease",
    )
    assert presence_model.other_leaves(page_dir) == []
    assert read_record(neighbor / "service.json")["enabled"]
    write_record(neighbor / "stream.json", {})
    declare_work(neighbor, "repaired", ts=cleanup_model.now_iso())
    hosting_model.start_server(neighbor, persistent=True, revive=True, harness=None)
    renewed = server_model.running_server(neighbor)
    assert renewed is not None
    assert renewed["server_id"] != original["server_id"]
    [row] = wait_for(
        lambda: presence_model.other_leaves(page_dir),
        lambda rows: len(rows) == 1 and rows[0]["activity"]["detail"] == "repaired",
        failure="the revived service did not regenerate its row",
    )
    assert row["activity"]["kind"] == "working"


def test_a_stated_host_serve_says_nothing_about_loopback(page_dir, monkeypatch):
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    runner = CliRunner()
    started = runner.invoke(
        cli_model.cli,
        [
            "server",
            "start",
            "--lifetime",
            "persistent",
            "--host",
            "localhost",
            str(page_dir),
        ],
    )
    try:
        assert started.exit_code == 0, started.output
        assert started.stderr == ""
    finally:
        stopped = runner.invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        assert stopped.exit_code == 0, stopped.output


def test_server_start_names_the_running_payload(page_dir):
    runner = CliRunner()
    started = runner.invoke(
        cli_model.cli, ["server", "start", "--lifetime", "persistent", str(page_dir)]
    )
    try:
        assert started.exit_code == 0, started.output
        reading = json.loads(started.stdout)
        assert (reading["page"], reading["lifetime"]) == (str(page_dir), "persistent")
        assert reading["stop"] == f"leaf server stop {page_dir}"
        assert reading["runtime"]["path"] == str(schema_model.PLUGIN_ROOT)

        state = runner.invoke(cli_model.cli, ["page", "state", str(page_dir)])
        assert state.exit_code == 0, state.output
        server = json.loads(state.output)["server"]
        assert server["runtime"]["path"] == str(schema_model.PLUGIN_ROOT)
        assert server["url"] == reading["url"]
    finally:
        stopped = runner.invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        assert stopped.exit_code == 0, stopped.output


def test_a_server_start_re_vendors_an_older_page_and_refuses_a_newer_one(page_dir):
    """A server speaks the contract of the Leaf that started it, and the page's log
    the protocol its last `page init` recorded. Served across the two, the page breaks in
    the browser on every read. A page an older Leaf vendored the start re-vendors
    first, as the plugin update that left it there calls for. One a newer Leaf
    vendored, which this Leaf does not take back, is refused before the start claims
    the page or records a service, and the refusal names the newer Leaf that would
    serve it. A server already running over such a page is refused the same way
    rather than handed out as this Leaf's."""
    from leaf.event_contracts import write_refusal

    runner = CliRunner()
    stamp = page_dir / schema_model.LAYER_FILE
    vendored = stamp.read_text(encoding="utf-8")
    vendored_at_another_protocol(page_dir, newer=True)

    refused = runner.invoke(cli_model.cli, ["server", "start", str(page_dir)])

    assert refused.exit_code != 0, refused.output
    assert "Use a newer Leaf" in refused.output
    assert not service_model.claim_path(page_dir).exists()
    assert read_record(page_dir / "service.json") is None
    assert not leases_model.lock_is_held(page_dir / "server.lock")

    # A newer Leaf may record more in the layer record than this Leaf knows, and
    # the protocol is still what decides.
    newer = json.loads(stamp.read_text(encoding="utf-8"))
    stamp.unlink()
    stamp.write_text(json.dumps({**newer, "future": 1}), encoding="utf-8")
    reshaped = runner.invoke(
        cli_model.cli, ["server", "start", "--lifetime", "persistent", str(page_dir)]
    )
    assert reshaped.exit_code != 0, reshaped.output
    assert "Use a newer Leaf" in reshaped.output

    stamp.unlink()
    stamp.write_text(vendored, encoding="utf-8")
    vendored_at_another_protocol(page_dir)
    started = runner.invoke(cli_model.cli, ["server", "start", str(page_dir)])
    try:
        assert started.exit_code == 0, started.output
        assert server_model.running_server(page_dir)
        assert write_refusal(page_dir) is None
        vendored_at_another_protocol(page_dir, newer=True)
        reused = runner.invoke(cli_model.cli, ["server", "start", str(page_dir)])
        assert reused.exit_code != 0, reused.output
        assert "Use a newer Leaf" in reused.output
    finally:
        stopped = runner.invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        assert stopped.exit_code == 0, stopped.output


@pytest.mark.parametrize("accepted", [False, True])
def test_private_revival_cannot_advertise_the_previous_serving_row(
    page_dir, spawn, accepted
):
    """The held reservation cannot impersonate a dead committed incarnation."""
    neighbor = cleanup_model.state_home() / "pages" / "private-revival"
    neighbour_page(neighbor, title="Private revival", dead=True, port=0)
    record_claim(neighbor, id="private-revival")
    hosting_model.start_server(neighbor, persistent=True, harness=None)
    previous = server_model.running_server(neighbor)
    assert previous is not None
    wait_for(
        lambda: server_rows_model.read_row(neighbor, previous),
        bool,
        failure="the original server did not publish its row",
    )
    hosting_model.cmd_stop(neighbor)
    desired = {**read_record(neighbor / "service.json"), "enabled": True}
    write_record(neighbor / "service.json", desired)
    assert presence_model.other_leaves(page_dir) == []
    # The stopped incarnation's row is retired by that reading, so a row present
    # later is one the reservation published.
    assert not server_rows_model.row_path(neighbor).exists()
    caller, end = socket.socketpair()
    child = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "_serve",
            str(neighbor),
            "--lifetime",
            "persistent",
            "--revive",
            "--harness",
            "null",
            "--handshake",
            str(end.fileno()),
        ],
        pass_fds=(end.fileno(),),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    end.close()
    caller.settimeout(STATED_TIMEOUT)
    try:
        with caller.makefile("rb") as announcements:
            assert json.loads(announcements.readline())["url"] == previous["url"]
            assert leases_model.lock_is_held(neighbor / "server.lock")
            assert read_record(neighbor / "service.json") == desired
            assert not server_rows_model.row_path(neighbor).exists()
            assert server_model.running_server(neighbor) is None
            assert presence_model.other_leaves(page_dir) == []
            if accepted:
                caller.sendall(b"\n")
                assert json.loads(announcements.readline())["url"] == previous["url"]
                rows = wait_for(
                    lambda: presence_model.other_leaves(page_dir),
                    lambda rows: len(rows) == 1,
                    failure="the accepted revival did not publish its own row",
                )
                assert rows[0]["title"] == "Private revival"
                current = server_model.running_server(neighbor)
                assert current is not None
                assert current["server_id"] != previous["server_id"]
                assert (
                    files_model.read_json(server_rows_model.row_path(neighbor))[
                        "server_id"
                    ]
                    == current["server_id"]
                )
        if not accepted:
            caller.close()
            assert child.wait(timeout=STATED_TIMEOUT) == 0
            assert read_record(neighbor / "service.json") == desired
            assert not server_rows_model.row_path(neighbor).exists()
            assert presence_model.other_leaves(page_dir) == []
    finally:
        caller.close()
        hosting_model.cmd_stop(neighbor)
        assert child.wait(timeout=STATED_TIMEOUT) == 0


def test_a_start_waits_for_uncommitted_preparation_before_reusing(page_dir, spawn):
    """Another start cannot adopt a listener its caller has not accepted."""
    caller, end = socket.socketpair()
    child = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "_serve",
            str(page_dir),
            "--lifetime",
            "persistent",
            "--harness",
            "null",
            "--handshake",
            str(end.fileno()),
        ],
        pass_fds=(end.fileno(),),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    end.close()
    caller.settimeout(STATED_TIMEOUT)
    successor = []
    attempting = threading.Event()

    def start():
        attempting.set()
        successor.append(
            hosting_model.start_server(page_dir, persistent=True, harness=None)
        )

    starting = threading.Thread(target=start, daemon=True)
    try:
        assert "url" in json.loads(caller.makefile("rb").readline())
        assert read_record(page_dir / "service.json") is None
        assert not server_rows_model.row_path(page_dir).exists()
        starting.start()
        assert attempting.wait(STATED_TIMEOUT), (
            "the successor never attempted the held server lease"
        )
        assert leases_model.lock_is_held(page_dir / "server.lock")
        caller.close()  # Abandon the private listener; the successor must bind its own.
        assert child.wait(timeout=STATED_TIMEOUT) == 0
        starting.join(timeout=STATED_TIMEOUT)
        assert not starting.is_alive(), "the successor's start never returned"
        assert len(successor) == 1
        assert fetch(successor[0].url)[0] == 200
        wait_for(
            lambda: (
                (current := server_model.running_server(page_dir))
                and server_rows_model.read_row(page_dir, current)
            ),
            bool,
            failure="the accepted successor did not publish its own serving row",
        )
    finally:
        caller.close()
        starting.join(timeout=STATED_TIMEOUT)
        hosting_model.cmd_stop(page_dir)


def test_failed_row_preparation_preserves_the_previous_desired_service(
    page_dir, monkeypatch
):
    """A producer constructor failure publishes neither service nor acquisition."""
    hosting_model.start_server(page_dir, persistent=True, harness=None)
    previous = server_model.running_server(page_dir)
    assert previous is not None
    wait_for(
        lambda: server_rows_model.read_row(page_dir, previous),
        bool,
        failure="the original server did not publish its row",
    )
    hosting_model.cmd_stop(page_dir)
    desired = {**read_record(page_dir / "service.json"), "enabled": True}
    write_record(page_dir / "service.json", desired)
    row_before = server_rows_model.row_path(page_dir).read_bytes()

    def failed_constructor(*_args):
        assert server_model.running_server(page_dir) is None
        raise RuntimeError("row producer cannot be prepared")

    monkeypatch.setattr(server_rows_model, "RowPublisher", failed_constructor)
    with pytest.raises(RuntimeError, match="row producer cannot be prepared"):
        hosting_model.cmd_serve(page_dir, persistent=True, revive=True, harness=None)
    assert read_record(page_dir / "service.json") == desired
    assert server_rows_model.row_path(page_dir).read_bytes() == row_before
    assert not leases_model.lock_is_held(page_dir / "server.lock")
    assert server_model.running_server(page_dir) is None


@pytest.mark.parametrize(
    "owned,same_session", [(False, False), (True, False), (True, True)]
)
def test_stop_does_not_wait_forever_on_a_server_started_after_its_transition(
    page_dir, monkeypatch, owned, same_session
):
    """Explicit stops retire a later start; owner cleanup yields to a successor."""
    assert service_model.claim_page(page_dir)
    owner = service_model.page_claim(page_dir) if owned else None
    assert hosting_model.start_server(page_dir, persistent=True, harness=None)
    transitioned = threading.Event()
    resume = threading.Event()
    original_page_locked = hosting_model.page_locked
    stopping = None

    @contextmanager
    def pause_after_transition(locked):
        with original_page_locked(locked):
            yield
        if threading.current_thread() is stopping and locked == page_dir:
            transitioned.set()
            assert resume.wait(STATED_TIMEOUT)

    monkeypatch.setattr(hosting_model, "page_locked", pause_after_transition)
    stopped = []
    stopping = threading.Thread(
        target=lambda: stopped.append(
            hosting_model.cmd_stop(page_dir, owner=owner)
            if owned
            else hosting_model.cmd_stop(page_dir)
        ),
        daemon=True,
    )
    try:
        stopping.start()
        assert transitioned.wait(STATED_TIMEOUT), "the stop never made its transition"
        wait_for(
            lambda: not leases_model.lock_is_held(page_dir / "server.lock"),
            bool,
            failure="the first server did not release its lease",
        )
        if owned:
            with service_model.PageTransaction(page_dir) as transaction:
                transaction.take_claim(
                    harness_model.session_harness()
                    if same_session
                    else harness_model.ClaudeCodeHarness("successor", "Claude")
                )
        assert hosting_model.start_server(page_dir, persistent=True, harness=None)
        resume.set()
        stopping.join(timeout=STATED_TIMEOUT)
        assert not stopping.is_alive(), "the stop never returned once resumed"
        assert stopped == [True]
        assert bool(server_model.running_server(page_dir)) == owned
    finally:
        resume.set()
        write_record(
            page_dir / "service.json",
            {**read_record(page_dir / "service.json"), "enabled": False},
        )
        stopping.join(timeout=STATED_TIMEOUT)


def test_test_teardown_ends_detached_delivery_before_removing_state(
    codex_claimed_page, under_codex, codex_env, codex_queue, tmp_path, isolated_session
):
    """Stopping the page alone leaves delivery watching its still-owned claim.

    Teardown ends the synthetic harness while coordination files remain, so
    its detached adapter releases its leases before temporary state disappears.
    """
    page = codex_claimed_page
    finished = tmp_path / "codex-start-finished"
    started = under_codex(
        shlex.join([*LEAF_COMMAND, "page", "claim", str(page)]),
        codex_env | codex_queue | {"CODEX_THREAD_ID": "codex-thread"},
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    release_codex_command(page, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    assert started.returncode == 0, f"{out}{err}"
    assert codex_adapter_model.adapter_is_live("codex-thread")

    hosting_model.cmd_stop(page)
    assert not server_model.running_server(page)
    assert codex_adapter_model.adapter_is_live("codex-thread")

    retire_test_services(tmp_path, isolated_session)
    turn_record = cleanup_model.session_record("codex-thread")
    assert turn_record is not None
    assert turn_record["ended"] is not None
    assert not codex_adapter_model.adapter_is_live("codex-thread")
