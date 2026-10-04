"""Record the README's demo GIF and two session stills, and the site's card, by
driving the shipped runtime through one round.

The stills come off the same staged scene as the GIF, the one the README's alt text
describes, so a theme change regenerates them rather than leaving them stale. The
four files are published under `demo/` in max-sixty/leaf-assets
(`leaf_dev.leaf_assets`), which moves Leaf's pin and the README's image URLs.

    uv run leaf-dev record-demo [--output DIR]

`--output` writes the four files into DIR instead of publishing them.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import click
from leaf.delivery import freeze_delivery, pending_batches, receive_delivery
from leaf.hook_carrier import hook_acknowledgement
from leaf.host import session_harness
from leaf.hosting import claim_and_start, cmd_stop
from leaf.projection import folded_positions
from leaf.publishing import cmd_stamp
from leaf.render_checks import wait_until_ready
from leaf.render_gate.scheme import rendered_revision, served
from leaf.served_state.context import read_page
from leaf.served_state.page import read_served_page
from leaf.service import PageTransaction
from leaf.session import cmd_status
from leaf.thread import cmd_reply
from leaf.vendoring import cmd_init
from PIL import Image
from playwright.sync_api import Page

from leaf_dev import LEAF_COMMAND
from leaf_dev.browser import chrome, settle, tab
from leaf_dev.leaf_assets import publish, stage

GIF_SIZE = (1120, 700)
# The viewport used for the README's representative stills.
STILL_SIZE = (1280, 953)
# The card a shared link unfurls into, shot at the 1.91:1 an unfurler draws rather
# than cropped from a still, which cut off the banner.
CARD_SIZE = (1200, 630)
# What one staged scene is photographed as: the README's light and dark stills,
# and the card.
STILLS = (
    ("session-light", STILL_SIZE, "light"),
    ("session-dark", STILL_SIZE, "dark"),
    ("session-card", CARD_SIZE, "light"),
)


# The board as the document first states it, and the words each card carries. Kept as
# data rather than as markup so the user's recorded move can be written back into the
# document the way an agent answers one: same page, the card where they put it.
CARDS = {
    "card-dryrun": "Dry-run the backfill",
    "card-oncall": "Staff the on-call rota",
    "card-flip": "Flip reads",
    "card-retire": "Retire the old store",
}
COLUMNS = (("col-before", "Before"), ("col-during", "During"), ("col-after", "After"))
BOARD = {
    "col-before": ["card-dryrun", "card-oncall"],
    "col-during": ["card-flip"],
    "col-after": ["card-retire"],
}


def board_markup(board: dict[str, list[str]]) -> str:
    return "\n".join(
        f'  <lf-column id="{column}" label="{label}">\n'
        + "".join(
            f'    <lf-card id="{card}"><strong>{CARDS[card]}</strong></lf-card>\n'
            for card in board[column]
        )
        + "  </lf-column>"
        for column, label in COLUMNS
    )


def folded_board(page_dir: Path) -> dict[str, list[str]]:
    """The board with the user's move folded in, as the page draws it: the order an
    agent writes into its next version."""
    with PageTransaction(page_dir) as page:
        context = read_page(page_dir, page.events)
        state, reading, _ = read_served_page(context)
        document = reading.documents[state["active"]["revision"]]
        registry = context.registry
        order = folded_positions(
            "punch-list",
            "move",
            registry["lf-board"]["x-state"]["move"]["record"],
            document.document.by_id,
            document.spoken,
            registry,
            document.projection,
        )
        return {column: order[column] for column, _label in COLUMNS}


def demo_page(version: int, board: dict[str, list[str]] | None = None) -> str:
    progressed = version == 2
    progress = "3 of 4" if progressed else "2 of 4"
    delta = ' delta="+1" direction="up-good"' if progressed else ""
    shadow_status = "done" if progressed else "active"
    rollback_status = "active" if progressed else "planned"
    shadow_copy = (
        "Backfill stayed online behind a fixed rate limit; read parity held."
        if progressed
        else "Backfill is running behind a fixed rate limit; read parity is being sampled."
    )
    rollback_copy = (
        "Traffic is back on the old service; order counts are being compared."
        if progressed
        else "Return traffic to the old service and compare order counts."
    )
    phase_two = (
        "Backfill history online behind a fixed rate limit, then flip reads to the new store."
        if progressed
        else "Backfill history, then flip reads to the new store."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<title>Migration plan</title>
<meta name="lf-review" content="sign-off">
</head>
<body>
<main class="layout-column">
<header id="top">
<p class="eyebrow">demo · migration rehearsal</p>
<h1>Migrating billing to the new service</h1>
<p class="lede" id="demo-lede">The rehearsal is running now. This page follows each
new version as the checks finish.</p>
</header>

<div id="demo-metrics" class="layout-tiles">
  <lf-metric id="demo-progress" value="{progress}"{delta}>checks complete</lf-metric>
  <lf-metric id="demo-errors" value="0.08%">error rate</lf-metric>
  <lf-metric id="demo-p95" value="181 ms">p95 latency</lf-metric>
</div>

<section id="phases">
<h2>Phases</h2>
<ol class="steps">
  <li id="p1">Dual-write to old and new stores behind a flag.</li>
  <li id="p2">{phase_two}</li>
  <li id="p3">Use an online traffic swap, then retire the old store.</li>
</ol>
</section>

<section id="rehearsal">
<h2>Rehearsal progress</h2>
<lf-milestones id="demo-milestones">
  <lf-milestone id="demo-ms-baseline" status="done" when="14:02">
    <strong>Capture the baseline</strong> Counts and guardrails recorded.
  </lf-milestone>
  <lf-milestone id="demo-ms-shadow" status="{shadow_status}" when="14:08">
    <strong>Shadow and backfill</strong> {shadow_copy}
  </lf-milestone>
  <lf-milestone id="demo-ms-rollback" status="{rollback_status}" when="next">
    <strong>Prove rollback</strong> {rollback_copy}
  </lf-milestone>
  <lf-milestone id="demo-ms-report" status="planned" when="last">
    <strong>Publish the rehearsal report</strong>
  </lf-milestone>
</lf-milestones>
</section>

<section id="work">
<h2>Cutover punch list</h2>
<p id="work-note">Drag a card to change the plan; your arrangement is saved on this page.</p>
<lf-board id="punch-list">
{board_markup(board or BOARD)}
</lf-board>
</section>
</main>
</body>
</html>
"""


def select_text(page: Page, selector: str, text: str) -> None:
    selected = page.evaluate(
        """([selector, text]) => {
            const walker = document.createTreeWalker(
                document.querySelector(selector), NodeFilter.SHOW_TEXT);
            for (let node; (node = walker.nextNode()); ) {
                const at = node.data.indexOf(text);
                if (at < 0) continue;
                const range = document.createRange();
                range.setStart(node, at);
                range.setEnd(node, at + text.length);
                getSelection().removeAllRanges();
                getSelection().addRange(range);
                return getSelection().toString();
            }
            return null;
        }""",
        [selector, text],
    )
    if selected != text:
        raise RuntimeError(f"could not select {text!r} in {selector}")
    page.dispatch_event("body", "mouseup")


class DemoWaiter:
    """One background `leaf wait`, taking each delivery the way this host's agent
    does: it reads a complete delivery, explicitly acknowledges it, and
    rearms the wait. The demo itself stands in for the reader."""

    def __init__(self, page_dir: Path) -> None:
        self.process = subprocess.Popen(
            [*LEAF_COMMAND, "wait", str(page_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def receive(self) -> list[dict]:
        """The user events of one delivery. A wait that ends without them has said
        why on stderr, so the failure carries it."""
        stdout, stderr = self.process.communicate(timeout=10)
        harness = session_harness()
        hooked = harness is not None and harness.hooks_carry()
        if not stdout.strip():
            payload = {}
        elif hooked:
            payload = freeze_delivery(
                pending_batches(harness.session),
                carrier="hook",
                acknowledge=hook_acknowledgement,
            )
            receive_delivery(payload["id"])
        else:
            payload = json.loads(stdout)
        batches = payload.get("batches", [])
        if len(batches) != 1 or not batches[0]["events"]:
            raise RuntimeError(
                f"the demo waiter exited {self.process.returncode} without one batch "
                f"of user events\n{stderr}".rstrip()
            )
        self.process = subprocess.Popen(
            [*LEAF_COMMAND, "wait", *([] if hooked else ["--ack", payload["id"]])],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return batches[0]["events"]

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)


def record(
    page: Page, waiter: DemoWaiter, page_dir: Path
) -> tuple[list[Image.Image], list[int]]:
    frames: list[Image.Image] = []
    durations: list[int] = []

    def shot(duration: int) -> None:
        png = page.screenshot(animations="disabled", caret="hide")
        frames.append(Image.open(io.BytesIO(png)).convert("RGB"))
        durations.append(duration)

    # The page's own readiness, not the document's stamp: a gesture taken before the
    # log's replay finishes reads a half-written page.
    wait_until_ready(page)
    page.wait_for_function(
        "() => document.querySelector('.lf-status-text').textContent.includes('awaits')"
    )
    live_url = page.url
    shot(1600)

    select_text(page, "#p2", "Backfill history")
    # The selection raises the response bar with its field open and focused, so the
    # demo types into it and sends with Mod+Enter.
    field = page.locator(".lf-fab-input")
    field.focus()
    page.keyboard.insert_text("Can the backfill stay online?")
    page.wait_for_function(
        """() => document.querySelector('.lf-composer').style.display === 'contents'
            && (CSS.highlights.get('lf-pending')?.size ?? 0) > 0
            && document.getElementById('lf-composer-quote').classList.contains('lf-unseen')"""
    )
    shot(2300)

    field.press("ControlOrMeta+Enter")
    page.wait_for_selector(".lf-margin-thread")
    shot(1500)
    page.locator(".lf-threads-toggle").click()
    page.wait_for_selector(".lf-thread")

    comment_id = next(
        event["id"] for event in waiter.receive() if event["kind"] == "comment"
    )
    cmd_status(page_dir, "working", "answering the backfill question", on=comment_id)
    page.wait_for_function(
        "() => document.querySelector('.lf-status-detail').textContent.includes('answering')"
    )
    shot(900)

    cmd_reply(
        page_dir,
        None,
        "Yes. The fixed rate limit keeps the backfill online.",
        None,
        for_event=comment_id,
        validate_source=True,
    )
    (page_dir / "index.html").write_text(demo_page(2), encoding="utf-8")
    cmd_stamp(page_dir, "Backfill stays online; rehearsal progress is now 3 of 4")
    cmd_status(page_dir, "waiting", "")
    page.wait_for_function(
        "() => document.querySelector('meta[name=lf-revision][data-lf-runtime]')"
        "?.content === '2'"
    )
    if page.url != live_url:
        raise RuntimeError(f"the live page navigated from {live_url} to {page.url}")
    wait_until_ready(page)
    page.locator(".lf-thread").get_by_role(
        "button", name="1 new reply", exact=True
    ).click()
    page.wait_for_selector(".lf-thread .lf-msg.agent")
    shot(2300)

    page.get_by_role("button", name="Close threads").click()
    page.locator("#top").scroll_into_view_if_needed()
    shot(2100)

    page.locator("#work").scroll_into_view_if_needed()
    shot(1000)
    applied_before_move = page.locator("body").get_attribute("data-lf-applied")
    grip = page.locator("#card-oncall .lf-grip").bounding_box()
    destination = page.locator("#col-during").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        destination["x"] + destination["width"] / 2,
        destination["y"] + destination["height"] / 2,
        steps=15,
    )
    page.mouse.up()
    page.wait_for_selector("#col-during #card-oncall")
    page.wait_for_function(
        "() => document.querySelector('.lf-notice').classList.contains('show')"
    )
    shot(2400)
    page.wait_for_function(
        "before => document.body.getAttribute('data-lf-applied') !== before",
        arg=applied_before_move,
    )
    if "card-oncall" not in folded_board(page_dir)["col-during"]:
        raise RuntimeError("the board move did not reach the page's standing log")
    return frames, durations


def shoot_stills(browser, url: str, page_dir: Path, into: Path) -> None:
    """The README's session stills and the site's card, off the scene `record`
    has just left, written into `into` beside the GIF.

    Write the saved board arrangement into the document and stamp it before
    `waiting`, so the stills show the revised plan. The comment watcher remains
    armed and the banner invites input. Each shot is a fresh context: viewport and
    color scheme are context settings, and the diagram palette is read once at load."""
    (page_dir / "index.html").write_text(
        demo_page(2, folded_board(page_dir)), encoding="utf-8"
    )
    cmd_stamp(page_dir, "On-call staffing moved into During, as the board now reads")
    cmd_status(page_dir, "waiting", "")

    for name, size, scheme in STILLS:
        with tab(browser, size, scheme) as page:
            page.goto(url)
            # Hold the server's state and authored revision before taking the still.
            state = served(page, url, "/api/state").json()
            wait_until_ready(page, state)
            revision = rendered_revision(url, state)
            page.wait_for_function(
                "revision => document.querySelector("
                "'meta[name=\"lf-revision\"][data-lf-runtime]'"
                ")?.content === String(revision)",
                arg=revision,
            )
            page.wait_for_function(
                "() => document.querySelector('.lf-status-text')"
                ".textContent.includes('awaits')"
            )
            page.locator(".lf-banner .lf-threads-toggle").click()
            page.locator(".lf-thread-summary").click()
            page.wait_for_selector(".lf-thread .lf-msg.agent")
            page.locator("#top").scroll_into_view_if_needed()
            settle(page)
            page.screenshot(
                path=into / f"{name}.png", animations="disabled", caret="hide"
            )


def write_gif(frames: list[Image.Image], durations: list[int], output: Path) -> None:
    palette_frames = [
        frame.quantize(colors=192, method=Image.Quantize.MEDIANCUT) for frame in frames
    ]
    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )


@click.command("record-demo")
@click.option(
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Write the recording into this directory instead of publishing it.",
)
def record_demo(output: Path | None) -> None:
    """Record the demo GIF, README stills and site card, and publish them."""
    with tempfile.TemporaryDirectory(prefix="leaf-demo-") as scratch:
        recording = Path(scratch) / "demo"
        recording.mkdir()
        page_dir = Path(scratch) / "page"
        # A state home of its own, so the host's open pages stay out of the banner's
        # `All leaves`. Set before any leaf command so each inherits it. The agent's
        # name shows only under a host session, which the recording keeps.
        os.environ["XDG_STATE_HOME"] = f"{scratch}/state"
        os.environ["LEAF_AGENT"] = "Claude"
        with redirect_stdout(io.StringIO()):
            cmd_init(page_dir)
        (page_dir / "index.html").write_text(demo_page(1), encoding="utf-8")
        cmd_stamp(page_dir, "Migration rehearsal started; 2 of 4 checks complete")
        cmd_status(page_dir, "waiting", "")
        with claim_and_start(page_dir) as started:
            pass
        url = started.url
        waiter = DemoWaiter(page_dir)
        try:
            with chrome() as browser, tab(browser, GIF_SIZE) as page:
                page.goto(url)
                frames, durations = record(page, waiter, page_dir)
                write_gif(frames, durations, recording / "demo.gif")
                shoot_stills(browser, url, page_dir, recording)
        finally:
            waiter.stop()
            cmd_stop(page_dir)
        files = {path.name: path.read_bytes() for path in recording.iterdir()}
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (output / name).write_bytes(content)
        click.echo(f"Recorded {output}")
        return
    with tempfile.TemporaryDirectory(prefix="leaf-assets-") as raw:
        revision = publish(stage("demo", files, Path(raw)), "Record the demo")
    click.echo(f"Recorded max-sixty/leaf-assets@{revision}")
