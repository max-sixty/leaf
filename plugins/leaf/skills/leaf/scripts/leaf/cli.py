"""Click declarations and production command wiring."""

import json
import sys
from pathlib import Path

import click

from leaf.checking import cmd_check
from leaf.conversation import cmd_comment, cmd_edit, cmd_reply, cmd_report, cmd_resolve
from leaf.data import cmd_data_clear, cmd_data_set
from leaf.hooks import cmd_hook, unanswered_asks
from leaf.hosting import cmd_serve, cmd_stop, start_server
from leaf.layer import cmd_init, cmd_package_check, cmd_package_init
from leaf.media import cmd_media
from leaf.page import cmd_catalog, cmd_guidance, cmd_page_state
from leaf.passages import active_enclosing
from leaf.publishing import cmd_stamp
from leaf.rendering import cmd_export
from leaf.schema import (
    ACK_BATCH_INSTRUCTION,
    ANSWER_ASK_INSTRUCTION,
    WAIT_BATCH_OUTPUT_INSTRUCTION,
)
from leaf.service import (
    PageTransaction,
    host_identity,
    restore_page_claim,
    take_page_claim,
    unacknowledged,
)
from leaf.session import cmd_ack, cmd_status, cmd_wait
from leaf.transcript import cmd_events, cmd_transcript


def resolve_dir(dir_arg: str, must_exist: bool = True) -> Path:
    page_dir = Path(dir_arg).expanduser().resolve()
    if must_exist and not (page_dir / "comments.jsonl").is_file():
        sys.exit(
            f"{page_dir} is not an initialized page; run `leaf page init` "
            "to vendor the layer"
        )
    return page_dir


@click.group()
def cli() -> None:
    """Build and run interactive pages a session shares with its user."""


@cli.group(short_help="Create pages and add media.")
def page() -> None:
    """Create pages and add media."""


@page.command(short_help="Create or re-vendor a page directory.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--package",
    "selected",
    multiple=True,
    metavar="PACKAGE",
    help="include a project-relative or ~ package path; repeat for more",
)
@click.option(
    "--no-packages",
    is_flag=True,
    help="remove all explicit packages from an existing page",
)
def init(dir: str, selected: tuple[str, ...], no_packages: bool) -> None:
    """Create or re-vendor a page directory.

    Creates PAGE/revisions/ and PAGE/versions/, then vendors the widget layer.
    The author writes PAGE/index.html. Re-running preserves the page's explicit packages unless --package or
    --no-packages replaces them, and refuses vocabulary the page log can no longer
    read. A package may contain any subset of the package layout, including zero,
    one, or many widgets.
    """
    if selected and no_packages:
        raise click.UsageError("--package and --no-packages cannot be used together")
    if any(not selection for selection in selected):
        raise click.UsageError("--package paths cannot be empty")
    if len(set(selected)) != len(selected):
        raise click.UsageError("each --package path may appear only once")
    selections = () if no_packages else selected or None
    cmd_init(resolve_dir(dir, must_exist=False), selections)


@cli.group(short_help="Create and check packages.")
def package() -> None:
    """Create and check packages."""


@package.command("init", short_help="Create a package directory.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="PACKAGE",
)
def package_init(package_path: Path) -> None:
    """Create the canonical package layout without replacing existing files."""
    cmd_package_init(package_path)


@package.command("check", short_help="Check a package as one unit.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="PACKAGE",
)
def package_check(package_path: Path) -> None:
    """Check the package as one composed unit."""
    cmd_package_check(package_path)


@page.command(short_help="Add images and print their page paths.")
@click.argument("dir", metavar="PAGE")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    metavar="IMAGE...",
)
def media(dir: str, files) -> None:
    """Add images and print their page paths.

    Copies each image into the page under a content-addressed name and prints
    its page path followed by its source file.
    """
    for src, url in cmd_media(resolve_dir(dir), [Path(f) for f in files]):
        print(f"{url}\t{src}")


@page.command(short_help="Print the widget and theme vocabulary.")
@click.argument("dir", metavar="PAGE")
def catalog(dir: str) -> None:
    """Print the page's widget and theme vocabulary."""
    cmd_catalog(resolve_dir(dir))


@page.command(short_help="List or print composed guidance by audience.")
@click.argument("dir", metavar="PAGE")
@click.argument("audience", required=False, metavar="AUDIENCE")
def guidance(dir: str, audience: str | None) -> None:
    """List audiences, or print the guidance for AUDIENCE."""
    cmd_guidance(resolve_dir(dir), audience)


@page.command(short_help="Print where the page stands, as JSON.")
@click.argument("dir", metavar="PAGE")
def state(dir: str) -> None:
    """Fold the log onto the active revision and print the result as one JSON
    object: elements, standing state and reports, record lag, open asks,
    threads, versions, presence, external data and its page bindings."""
    cmd_page_state(resolve_dir(dir))


@cli.group(short_help="Set or clear page-bound external data.")
def data() -> None:
    """Manage replaceable external or derived page data."""


@data.command("set", short_help="Replace one bound source value.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
@click.option(
    "--file",
    "input_file",
    type=click.File("r", encoding="utf-8"),
    default="-",
    help="JSON value to read (default: stdin)",
)
def data_set(dir: str, source: str, input_file) -> None:
    """Validate and replace SOURCE with one complete JSON value."""
    try:
        value = json.load(input_file)
    except json.JSONDecodeError as error:
        raise click.ClickException(
            f"invalid JSON ({error.msg}, line {error.lineno})"
        ) from error
    cmd_data_set(resolve_dir(dir), source, value)


@data.command("clear", short_help="Remove one source snapshot.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
def data_clear(dir: str, source: str) -> None:
    """Remove SOURCE, including a value its current schema rejects."""
    cmd_data_clear(resolve_dir(dir), source)


@cli.group(short_help="Check, stamp, and export versions.")
def version() -> None:
    """Check, stamp, and export versions."""


@version.command(short_help="Check the mutable page source.")
@click.argument("dir", metavar="PAGE")
@click.option("--render", is_flag=True, help="also check the rendered page in Chrome")
def check(dir: str, render: bool) -> None:
    """Check PAGE/index.html.

    Runs deterministic markup checks. --render also checks the drawn page in
    the installed Chrome.
    """
    sys.exit(cmd_check(resolve_dir(dir), render))


@version.command(short_help="Stamp the current source as the next version.")
@click.argument("dir", metavar="PAGE")
@click.option("--text", help="changelog text (default: stdin)")
@click.option(
    "--completes",
    multiple=True,
    metavar="WIDGET",
    help="active widget work this version completes (repeatable)",
)
def stamp(dir: str, text: str, completes: tuple[str, ...]) -> None:
    """Stamp PAGE/index.html with a changelog.

    Checks the exact source first, then records it as the next public version. Repeat
    --completes for each active widget work claim this version completes. A
    widget claim otherwise survives unrelated versions, and a version cannot
    silently remove its local seat.
    """
    cmd_stamp(resolve_dir(dir), text, completes)


@version.command(short_help="Export a stamped version to one HTML file.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "-o",
    "--out",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="output HTML file",
)
@click.option(
    "--version",
    type=int,
    metavar="N",
    help="stamped version to export (default: latest)",
)
def export(dir: str, out: Path, version: int) -> None:
    """Export a stamped version to one HTML file.

    Renders the version in Chrome, then writes a standalone copy.
    """
    sys.exit(cmd_export(resolve_dir(dir), out, version))


@cli.group(short_help="Start, run, or stop the local server.")
def server() -> None:
    """Start, run, or stop the local server."""


def serve_flags(command):
    """The two statements a serve takes, worn by the launcher and by the process
    it launches alike: `server start` forwards them verbatim to the `server run`
    it spawns, so one spelling is what keeps the pair from drifting."""
    for option in (
        click.option(
            "--standing",
            is_flag=True,
            help="decline the session claim, so the server outlives this session "
            "and only `leaf server stop` ends it — for a page kept up across "
            "sessions",
        ),
        click.option(
            "--host",
            metavar="NAME",
            help="bind every interface and put NAME in the URL, for a user the "
            "derived address can't reach; recorded in service.json",
        ),
    ):
        command = option(command)
    return command


@server.command(short_help="Start a page's server and print its URL.")
@click.argument("dir", metavar="PAGE")
@serve_flags
def start(dir: str, host: str | None, standing: bool) -> None:
    """Start a page's server and print its URL.

    Returns as soon as the server is up; the server itself keeps running in a
    session of its own. `leaf server stop` takes one down, and a session server
    goes down with the session that claimed it besides. A page already served
    prints that server's URL and is left alone.
    """
    page_dir = resolve_dir(dir)
    claim_transition = None if standing else take_page_claim(page_dir)
    if claim_transition:
        # Check the claim after taking it. The child checks it again under its
        # own transaction, so SessionEnd winning the spawn gap makes startup
        # fail instead of reviving a released page.
        with PageTransaction(page_dir) as page:
            if not page.owned_by(host_identity()):
                raise SystemExit(
                    f"this session no longer owns {page_dir}; the server was not started"
                )
    started = start_server(page_dir, host, standing)
    if not started:
        # A refusal or failed bind never transfers the page. Restore the prior
        # provenance only if nobody replaced this startup's exact claim.
        restore_page_claim(page_dir, claim_transition)
        raise SystemExit(1)
    url, note = started
    print(url)
    print(note, file=sys.stderr)


@server.command(short_help="Serve a page in the foreground until stopped.")
@click.argument("dir", metavar="PAGE")
@serve_flags
def run(dir: str, host: str | None, standing: bool) -> None:
    """Serve a page in the foreground, printing its URL and running until stopped.

    Run this in a terminal of your own to hold a page up where you can watch it.
    From an agent session use `server start`. A page already served prints that
    server's URL and exits.
    """
    page_dir = resolve_dir(dir)
    claim_transition = None if standing else take_page_claim(page_dir)
    try:
        cmd_serve(page_dir, host, standing)
    except BaseException:
        restore_page_claim(page_dir, claim_transition)
        raise


@server.command("_serve", hidden=True)
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option("--revive", is_flag=True, hidden=True)
def _serve(dir: str, host: str | None, standing: bool, revive: bool) -> None:
    """Private child process spawned by server start and Watch revival."""
    cmd_serve(resolve_dir(dir), host, standing, revive)


@server.command(short_help="Stop a page's server.")
@click.argument("dir", metavar="PAGE")
def stop(dir: str) -> None:
    """Stop a page's server."""
    print(cmd_stop(resolve_dir(dir)))


@cli.command(short_help="Set the agent's banner state.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["working", "waiting", "idle"]))
@click.argument("detail", required=False, default="")
@click.option(
    "--on",
    "on",
    metavar="SUBJECT",
    help="The open comment thread or local page widget this work is about.",
)
def status(dir: str, state: str, detail: str, on: str | None) -> None:
    """Set the agent's banner state.

    DETAIL is what the banner says after the state: what you are doing while
    `working`, and what you want back from the reader while `waiting` ("pick a
    storage engine"). A waiting page that declares none falls back to the
    standing "select text to comment".

    --on names the open comment thread or local page widget that detail is about,
    and the reader sees it beside that subject as well as in the banner. Thread
    work stands until your next reply there. Widget work stands until a later
    version stamp explicitly names it with --completes. Work in flight — a
    delegate, a long tool run — therefore reads as picked up rather than as
    silence. A `working` claim is believed while the turn that wrote it is open;
    the page is told when that turn ends, so something has to renew the claim
    within a couple of minutes of the ending, and one nobody renews at all goes
    quiet after about a quarter of an hour — on the banner and each local line.
    """
    page_dir = resolve_dir(dir)
    # Idling over an event nobody has answered ends the leaf on a user still
    # owed one — unread, or read and left. The watcher's whole batch, not the
    # reader-facing count, so a worker's report cannot be left standing as
    # provisional state forever either. Here rather than in cmd_status because
    # the log lock gives the check and the transition one order with an event
    # arriving or an acknowledgement advancing the cursor.
    if state != "idle":
        cmd_status(page_dir, state, detail, on=on)
        return
    with PageTransaction(page_dir) as page:
        events = page.events
        cursor = page.cursor
        pending = len(unacknowledged(events, cursor))
        unanswered = unanswered_asks(events, cursor, active_enclosing(page_dir))
        if pending:
            prefix = (
                f"{pending} update{'s' if pending != 1 else ''} nobody has picked up; "
                "idling ends the leaf over them; "
            )
            sys.exit(
                prefix + "`leaf wait` prints them and returns at once when events are "
                "already waiting. The wait owner must finish the delivery contract "
                "before idling. " + ACK_BATCH_INSTRUCTION
            )
        if unanswered:
            ids = ", ".join(t["id"] for t in unanswered)
            sys.exit(
                f"{len(unanswered)} acknowledged "
                f"comment{'s' if len(unanswered) != 1 else ''} with no answer "
                f"({ids}); idling ends the leaf over them. " + ANSWER_ASK_INSTRUCTION
            )
        page.set_status(state, detail)


@cli.command(
    short_help="Print one page's unacknowledged events and reports, then exit.",
    help=(
        "Watch every page this session holds — plus PAGE, claimed first, when "
        "given.\n\n" + WAIT_BATCH_OUTPUT_INSTRUCTION + "\n\n" + ACK_BATCH_INSTRUCTION
    ),
)
@click.argument("dir", metavar="PAGE", required=False)
def wait(dir: str | None) -> None:
    """Print one page's unacknowledged events and reports, then exit."""
    sys.exit(cmd_wait(resolve_dir(dir) if dir else None))


@cli.command(
    short_help="Acknowledge one batch, then wait for the next.",
    help=WAIT_BATCH_OUTPUT_INSTRUCTION + "\n\n" + ACK_BATCH_INSTRUCTION,
)
@click.argument("dir", metavar="PAGE")
@click.argument("seq", type=click.IntRange(min=1), metavar="SEQ")
def ack(dir: str, seq: int) -> None:
    """Acknowledge one complete batch and wait for the next one."""
    page_dir = resolve_dir(dir)
    cmd_ack(page_dir, seq)
    # Ack already succeeded, so ignore the following wait's delivery/end code.
    # The delivering wait established ownership; re-arm observes a successor
    # instead of reclaiming the page.
    cmd_wait(page_dir, claim_named=False)


@cli.command(short_help="Open an agent thread — on a passage, or on the page whole.")
@click.argument("dir", metavar="PAGE")
@click.option("--quote", help="passage text from the active revision")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--part", metavar="ID", help="declared visual part within --section")
@click.option("--text", help="comment text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
def comment(
    dir: str, quote: str, section: str, part: str, text: str, markup: str
) -> None:
    """Open a thread as the agent (--text or stdin): anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    The user answers it in the browser and resolves it there. Refuses a quote the
    active revision does not hold, or holds more than once.
    """
    cmd_comment(resolve_dir(dir), quote, section, part, text, markup)


@cli.command(short_help="Reply to a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option("--to", required=True, metavar="ID", help="comment or reply ID to answer")
@click.option("--text", help="reply text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
@click.option("--awaits", is_flag=True, help="mark this reply as waiting on the reader")
def reply(dir: str, to: str, text: str, markup: str, awaits: bool) -> None:
    """Post a threaded reply as the agent (--text or stdin)."""
    print(
        json.dumps(
            cmd_reply(resolve_dir(dir), to, text, markup, awaits), ensure_ascii=False
        )
    )


@cli.command(short_help="Edit one of this agent session's messages.")
@click.argument("dir", metavar="PAGE")
@click.option("--to", required=True, metavar="ID", help="comment or reply ID to edit")
@click.option("--text", help="replacement text (default: stdin)")
def edit(dir: str, to: str, text: str) -> None:
    """Replace the visible text of an agent-authored comment or reply.

    The original and every revision remain in the append-only event log. Frozen
    widget markup is not editable.
    """
    print(json.dumps(cmd_edit(resolve_dir(dir), to, text), ensure_ascii=False))


@cli.command(short_help="Close a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--to", required=True, metavar="ID", help="a message in the thread to close"
)
def resolve(dir: str, to: str) -> None:
    """Close a thread as the agent.

    The reader's own ✓ Resolve is the ordinary way a thread closes, so this is for
    the cases where waiting on them says nothing: they asked for it closed, or the
    thread is plainly moot — what it was about has left the page, or the work has
    since answered the question it put. Reply first where the thread asked something —
    closing is not an answer, and the panel names the agent that did it.
    """
    cmd_resolve(resolve_dir(dir), to)


@cli.command(short_help="Report a state change onto a page widget, as a worker.")
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(dir: str, widget: str, verb: str, fields: tuple) -> None:
    """Report a state change onto a page widget, as a worker.

    The verb and its fields are the widget's own x-report declaration —
    `leaf report <page> t-parser status status=review` moves a task. The
    page paints the report live as provisional news; it stands until a version
    absorbs or overrules it, and the page's watcher wakes to fold it in.
    """
    cmd_report(resolve_dir(dir), widget, verb, fields)


@cli.command(short_help="Print the event log as JSON lines.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--after",
    type=int,
    default=0,
    metavar="SEQ",
    help="print events after this sequence",
)
def events(dir: str, after: int) -> None:
    """Print the event log as JSON lines.

    This is read-only and does not acknowledge user events.
    """
    cmd_events(resolve_dir(dir), after)


@cli.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> None:
    """Print the page's exchange as Markdown."""
    cmd_transcript(resolve_dir(dir))


@cli.command(hidden=True)
def hook() -> None:
    """Answer an agent-host hook on stdin."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        sys.exit(f"hook expects the host's JSON payload on stdin ({error.msg})")
    cmd_hook(payload)
