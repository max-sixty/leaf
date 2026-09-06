#!/usr/bin/env python3
"""Record docs/demo.gif, and the landing page's two session stills, by driving the
shipped runtime through one round.

The stills used to be shot by hand, which meant nothing regenerated them and nothing
noticed when they stopped being true: a theme change left the landing page arguing for
a product whose picture showed the previous one. They come off the same staged scene as
the GIF because that scene is already the one the page's alt text describes — a comment
anchored to a marked passage, Claude's reply in the thread, the answered round latest in
the picker — so shooting them here costs two more browser contexts and gives them
something to re-run."""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from leaf.render_gate.browser import launch_browser
from PIL import Image
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "bin" / "leaf"
DEFAULT_OUTPUT = ROOT / "docs" / "demo.gif"
GIF_SIZE = (1120, 700)
# The viewport used for the landing page's representative stills.
STILL_SIZE = (1280, 953)


# The board as the document first states it, and the words each card carries. Kept as
# data rather than as markup so the reader's recorded move can be written back into the
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


def absorbed(board: dict[str, list[str]], move: dict) -> dict[str, list[str]]:
    """The board with one recorded `move` written into the authored arrangement."""
    placed = {
        column: [card for card in cards if card != move["card"]]
        for column, cards in board.items()
    }
    placed[move["to"]].insert(move["index"], move["card"])
    return placed


def last_move(page_dir: Path) -> dict:
    """The detail of the last board move the reader made on this page."""
    moves = []
    for line in (page_dir / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["kind"] == "action" and event.get("action") == "move":
            moves.append(event["detail"])
    if not moves:
        raise RuntimeError("the demo recorded no board move to answer")
    return moves[-1]


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
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Migration plan</title>
<meta name="lf-review" content="sign-off">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'none'; form-action 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<header id="top">
<p class="eyebrow">demo · migration rehearsal</p>
<h1>Migrating billing to the new service</h1>
<p class="lede" id="demo-lede">The rehearsal is running now. This page follows each
new version as the checks finish.</p>
</header>

<lf-metrics id="demo-metrics">
  <lf-metric id="demo-progress" value="{progress}"{delta}>checks complete</lf-metric>
  <lf-metric id="demo-errors" value="0.08%">error rate</lf-metric>
  <lf-metric id="demo-p95" value="181 ms">p95 latency</lf-metric>
</lf-metrics>

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
<p id="work-note">Drag a card to change the plan; the move reaches the agent directly.</p>
<lf-board id="punch-list">
{board_markup(board or BOARD)}
</lf-board>
</section>
</main>
</body>
</html>
"""


def run_leaf(*args: str) -> str:
    """A leaf command's own stdout, or a failure carrying what it said.

    Not `check=True`: the CalledProcessError it raises names the command and the
    exit status, and the streams it captured — the only thing that says what went
    wrong — die with it, because nothing prints them. Every step of staging the
    recording is one of these, so that is what the suite gets to report."""
    done = subprocess.run(
        [str(LEAF), *args], text=True, capture_output=True, check=False
    )
    if done.returncode:
        raise RuntimeError(
            f"leaf {' '.join(args)} exited {done.returncode}\n"
            f"{done.stdout}{done.stderr}".rstrip()
        )
    return done.stdout.strip()


def stop_server(page_dir: Path) -> None:
    """Bring a recording's server down. Silent and best-effort because both
    callers are clearing something away rather than doing the work: in the
    teardown a cleanup that failed loudly would be reporting over the failure it
    is cleaning up after, and on a leftover there is nothing to say about a
    server that had already gone."""
    subprocess.run(
        [str(LEAF), "server", "stop", str(page_dir)],
        check=False,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_comment(page_dir: Path) -> str:
    deadline = time.monotonic() + 10
    log = page_dir / "events.jsonl"
    while time.monotonic() < deadline:
        events = [
            json.loads(line) for line in log.read_text().splitlines() if line.strip()
        ]
        comments = [event for event in events if event["kind"] == "comment"]
        if comments:
            return comments[0]["id"]
        time.sleep(0.05)
    raise RuntimeError("the demo comment never reached the event log")


def select_text(page: Page, selector: str, text: str) -> None:
    selected = page.evaluate(
        """([selector, text]) => {
            const walker = document.createTreeWalker(
                document.querySelector(selector), NodeFilter.SHOW_TEXT
            );
            let node;
            while ((node = walker.nextNode())) {
                const at = node.data.indexOf(text);
                if (at < 0) continue;
                const range = document.createRange();
                range.setStart(node, at);
                range.setEnd(node, at + text.length);
                const selection = getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                return selection.toString();
            }
            return null;
        }""",
        [selector, text],
    )
    if selected != text:
        raise RuntimeError(f"could not select {text!r} in {selector}")
    page.dispatch_event("body", "mouseup")


class DemoWaiter:
    """Own the one waiting process as wait delivery hands off to ack."""

    def __init__(self, page_dir: Path) -> None:
        self.page_dir = page_dir
        self.process = subprocess.Popen(
            [str(LEAF), "wait", str(page_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def receive(self) -> list[dict]:
        """Read one complete result and re-arm after it reaches this driver.

        Every way a wait ends without user events is one it has already explained
        on stderr — a page closed under it, a server it can't reach and won't
        restart twice — so the empty result is the symptom and that line is the
        reason."""
        stdout, stderr = self.process.communicate(timeout=10)
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
        if not events:
            raise RuntimeError(
                f"the demo waiter exited {self.process.returncode} with no user events\n"
                f"{stderr}".rstrip()
            )
        self.process = subprocess.Popen(
            [str(LEAF), "ack", str(self.page_dir), str(events[-1]["seq"])],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return events

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
        image = Image.open(io.BytesIO(png)).convert("RGB")
        if image.size != GIF_SIZE:
            image = image.resize(GIF_SIZE, Image.Resampling.LANCZOS)
        frames.append(image)
        durations.append(duration)

    # All three stamps, which is what "the page is ready" means here and what
    # `shoot_stills` below already waits for: the document's own stamp says nothing
    # about the log, so a gesture taken on it alone reads a page replay has not
    # finished writing (runtime/presentation.js on the three readiness stamps). The
    # first thing this does is read `#p2`'s words back.
    page.wait_for_function(
        "() => document.body.dataset.lfUpgraded === '1'"
        " && document.body.dataset.lfApplied !== undefined"
        " && document.body.dataset.lfPresented === '1'"
    )
    page.wait_for_function(
        "() => document.querySelector('.lf-status-text').textContent.includes('awaits')"
    )
    live_url = page.url
    shot(1600)

    select_text(page, "#p2", "Backfill history")
    # The selection raises the response bar with its field already open and focused,
    # so the demo types into it directly and sends with the durable editors' shared
    # Mod+Enter chord. The Comment button the bar used to show is now one Tab away, and
    # the composer around the field draws nothing of its own.
    field = page.locator(".lf-fab-input")
    field.fill("Can the backfill stay online?")
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

    comment_id = wait_for_comment(page_dir)
    waiter.receive()
    run_leaf(
        "status",
        str(page_dir),
        "working",
        "answering the backfill question",
    )
    page.wait_for_function(
        "() => document.querySelector('.lf-status-text').textContent.includes('answering')"
    )
    shot(900)

    run_leaf(
        "reply",
        str(page_dir),
        "--to",
        comment_id,
        "--text",
        "Yes. The fixed rate limit keeps the backfill online.",
    )
    (page_dir / "index.html").write_text(demo_page(2), encoding="utf-8")
    run_leaf(
        "version",
        "stamp",
        str(page_dir),
        "--text",
        "Backfill stays online; rehearsal progress is now 3 of 4",
    )
    run_leaf("status", str(page_dir), "waiting")
    page.wait_for_function(
        "() => document.querySelector('meta[name=lf-revision][data-lf-runtime]')"
        "?.content === '2'",
        timeout=15_000,
    )
    if page.url != live_url:
        raise RuntimeError(f"the live page navigated from {live_url} to {page.url}")
    page.wait_for_function(
        "() => document.body.dataset.lfUpgraded === '1'"
        " && document.querySelectorAll('.lf-thread .lf-msg.claude').length > 0"
    )
    shot(2300)

    page.get_by_role("button", name="Close threads").click()
    page.locator("#top").scroll_into_view_if_needed()
    shot(2100)

    page.locator("#work").scroll_into_view_if_needed()
    shot(1000)
    grip = page.locator("#card-oncall .lf-grip").bounding_box()
    destination = page.locator("#col-during").bounding_box()
    if not grip or not destination:
        raise RuntimeError("the demo board did not render")
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
    waiter.receive()
    return frames, durations


def shoot_stills(
    browser,
    url: str,
    page_dir: Path,
    into: Path,
) -> None:
    """The landing page's two session stills, off the scene `record` has just left,
    written beside the GIF rather than to a path of their own.

    `--output` redirects the whole recording, and the stills have to go with it: the
    suite records into a tmp directory to prove the journey still drives, and stills
    that ignored the flag rewrote docs/session-{light,dark}.png on every run of the
    tests. A test that leaves the working tree dirty is one whose next reader has to
    work out whether the diff is theirs.

    By this point the log holds the whole round — a comment on a marked passage, the
    reply, the revision stamped for it, the reader's board move and the revision that
    answers it, the state back to waiting — so a fresh context loading the page arrives
    at exactly the picture docs/index.html describes in its alt text.
    Fresh is the point: the panel's open state lives in localStorage, so a reused
    context would restore whatever the last gesture left rather than the shot's own
    setup.

    One shot per color scheme, because the page states both and the landing page
    serves whichever the reader's OS asks for. A scheme is a context-level setting,
    not something to toggle on a live page: the vendored diagram palette is read once
    at load, so a flipped page would carry the other scheme's diagrams.

    Getting the banner to say "Claude awaits" takes answering the round and then
    stating both halves of attendance. `record` has received the board action, and
    receipt is not an answer: a page action stands until the authored document says
    what the reader's move said, so the document is written with the card where they
    dropped it. Only then is `waiting` true, which is the order
    `references/conversation-loop.md` asks of any turn. Ack has already re-armed the
    wait, whose held lease is the proof the browser renders."""
    (page_dir / "index.html").write_text(
        demo_page(2, absorbed(BOARD, last_move(page_dir))), encoding="utf-8"
    )
    run_leaf(
        "version",
        "stamp",
        str(page_dir),
        "--text",
        "On-call staffing moved into During, as the board now reads",
    )
    run_leaf("status", str(page_dir), "waiting")
    # The user's board move has to have landed in each shot, or it shows a page
    # mid-replay — the same wait `version export` takes for the same reason. Counted
    # once: neither shot posts anything, so the log is the same for both.
    actions = sum(
        json.loads(line)["kind"] == "action"
        for line in (page_dir / "events.jsonl").read_text().splitlines()
        if line.strip()
    )

    for scheme in ("light", "dark"):
        context = browser.new_context(
            viewport={"width": STILL_SIZE[0], "height": STILL_SIZE[1]},
            color_scheme=scheme,
            reduced_motion="reduce",
        )
        page = context.new_page()
        page.goto(url)
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        page.wait_for_function(
            f"() => Number(document.body.dataset.lfApplied ?? -1) >= {actions}"
        )
        page.wait_for_function(
            "() => document.querySelector('.lf-status-text')"
            ".textContent.includes('awaits')"
        )
        page.locator(".lf-banner .lf-threads-toggle").click()
        page.wait_for_selector(".lf-thread .lf-msg.claude")
        page.locator("#top").scroll_into_view_if_needed()
        # Ask the shared motion lifecycle rather than waiting a duration: a finished move
        # has left the list, and this context asks for reduced motion, so the carried
        # column move is omitted and the wait returns at once.
        page.wait_for_function(
            "() => document.querySelector('body > main').getAnimations().length === 0"
        )
        page.screenshot(
            path=into / f"session-{scheme}.png", animations="disabled", caret="hide"
        )
        context.close()


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
    with Image.open(output) as recorded:
        if recorded.n_frames != len(frames):
            raise RuntimeError(
                f"recorded {recorded.n_frames} frames; expected {len(frames)}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="GIF path (default: docs/demo.gif)",
    )
    args = parser.parse_args()
    output = args.output.resolve()

    # The page is staged beside the recording it produces, so `--output` keeps two
    # runs apart without a second thing to keep unique. A fixed directory under the
    # repo was shared by every concurrent run, and two recordings sharing a page
    # directory drive one page: `server run` finds the other's server.json and
    # serves that page rather than starting, both read one event log, and whichever
    # finishes first deletes the directory out from under the other. That last one
    # is how it surfaced — `page init` vendoring a widget into a path that stopped
    # existing between the write and the rename. Two runs recording to one output
    # are already one recording run twice, over a GIF and two stills with fixed
    # names, so nothing is left for staging to disambiguate.
    page_dir = output.parent / "demo-recording"
    # Only a recording killed outright leaves one of these, since the teardown
    # below covers every other exit — but `page init` re-vendors an existing page
    # rather than refusing it, so the next recording would replay the last one's
    # events off a log it never wrote. The stop is for that run's server, which
    # outlived it holding this page's port. Anything else on the path is somebody
    # else's, and `--output` puts this one wherever they asked, so say so rather
    # than delete it.
    if page_dir.exists():
        if not (page_dir / "registry.json").is_file():
            raise SystemExit(
                f"{page_dir} is not a staged page; move it or record elsewhere"
            )
        stop_server(page_dir)
        shutil.rmtree(page_dir)
    # Makes the output directory too, so `--output` into somewhere new works and
    # `write_gif` has a directory to write into.
    page_dir.mkdir(parents=True)
    # The recording gets a state home of its own, staged beside the page for the same
    # reason the page is. The banner's `All leaves` control lists the live pages
    # the state home knows about, so recording on a machine with pages open puts a
    # control in the picture that the staged scene never had — and one that takes its
    # width out of everything left of it, so the whole row lands somewhere else than
    # the alt text describes. The host's open pages and agent identity are not facts
    # about the product. Set both before any leaf command so each command and its server
    # inherit the staged values.
    state_dir = page_dir.parent / f"{page_dir.name}-state"
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir()
    os.environ["XDG_STATE_HOME"] = str(state_dir)
    os.environ["LEAF_AGENT"] = "Claude"

    # Two scopes because there are two things to give back and they start at
    # different moments: the staging directory exists from here on, the processes
    # only once the server is up.
    try:
        run_leaf("page", "init", str(page_dir))
        (page_dir / "index.html").write_text(demo_page(1), encoding="utf-8")
        run_leaf(
            "version",
            "stamp",
            str(page_dir),
            "--text",
            "Migration rehearsal started; 2 of 4 checks complete",
        )
        run_leaf("status", str(page_dir), "waiting")
        # `server start` returns once the server holds its port and has printed
        # the URL, so there is nothing to poll for here and no second child to
        # hold: the recording's one long-running process is the waiter.
        url = run_leaf("server", "start", str(page_dir))
        waiter: DemoWaiter | None = None
        try:
            waiter = DemoWaiter(page_dir)
            with sync_playwright() as playwright:
                browser, _ = launch_browser(playwright)
                context = browser.new_context(
                    viewport={"width": GIF_SIZE[0], "height": GIF_SIZE[1]},
                    color_scheme="light",
                    reduced_motion="reduce",
                )
                page = context.new_page()
                page.goto(url)
                frames, durations = record(page, waiter, page_dir)
                # The GIF is written before the stills are shot, so a still that
                # can't be staged costs only itself. The other order lost a good
                # recording to a timeout in the shot after it.
                write_gif(frames, durations, output)
                shoot_stills(browser, url, page_dir, output.parent)
                browser.close()
        finally:
            if waiter is not None:
                waiter.stop()
            stop_server(page_dir)
    finally:
        shutil.rmtree(page_dir)
        shutil.rmtree(state_dir)
    try:
        shown = output.relative_to(ROOT)
    except ValueError:
        shown = output
    print(f"Recorded {shown}")


if __name__ == "__main__":
    main()
