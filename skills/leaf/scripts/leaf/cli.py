"""Click declarations and production command wiring."""

import json
import sys
from pathlib import Path

import click

from leaf.schema import SKILL_ROOT, WAIT_BATCH_OUTPUT_INSTRUCTION
from leaf.state import EVENTS_FILE


def resolve_dir(dir_arg: str, must_exist: bool = True) -> Path:
    page_dir = Path(dir_arg).expanduser().resolve()
    if must_exist and not (page_dir / EVENTS_FILE).is_file():
        sys.exit(
            f"{page_dir} is not an initialized page; run `leaf page init` "
            "to vendor the layer"
        )
    return page_dir


def _print_records(*records: dict) -> None:
    """Print what a write appended, each record as `page events` prints it."""
    from leaf.event_log import jsonl_line

    for record in records:
        print(jsonl_line(record))


def _leaf_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print the source identity of the Leaf payload running this command."""
    if not value or ctx.resilient_parsing:
        return
    from leaf.layer import payload_provenance, provenance_label

    click.echo(f"leaf {provenance_label(payload_provenance())}")
    ctx.exit()


def _leaf_root(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print which copy of leaf this is, and stop.

    A harness session runs the payload its plugin cache holds, not the checkout,
    and the two are only ever the same by accident: the cache is a snapshot from
    whenever the marketplace last swept, and `bin/leaf` is identical across
    versions, so a stale copy answers exactly like a current one. The payload
    directory is what tells them apart, so that is what this prints — the
    version string says nothing, because a plugin is keyed on its commit rather
    than on a number anyone bumps.
    """
    if not value or ctx.resilient_parsing:
        return
    click.echo(SKILL_ROOT.parent.parent)
    ctx.exit()


@click.group()
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_leaf_version,
    help="Print this running Leaf payload's source version.",
)
@click.option(
    "--root",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_leaf_root,
    help="Print the payload directory this leaf runs from.",
)
def cli() -> None:
    """Build and run interactive pages a session shares with its user."""


@cli.group(short_help="Launch Codex and connect Leaf pages to its tasks.")
def codex() -> None:
    """Launch Codex or run Leaf's detached delivery carrier."""


@codex.command("launch", short_help="Launch an experimental streaming Codex terminal.")
@click.option("--codex-path", hidden=True)
def codex_launch(codex_path: str | None) -> None:
    """Run Codex with a private local App Server for Leaf delivery and activity.

    This integration is experimental.
    """
    from leaf.codex_adapter import cmd_codex_launch

    try:
        sys.exit(cmd_codex_launch(codex_path))
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error


@codex.command("start", short_help="Keep PAGE connected after this turn ends.")
@click.argument("dir", metavar="PAGE")
@click.option("--codex-path", hidden=True)
@click.option(
    "--app-server",
    metavar="ENDPOINT",
    help="deliver input and observe activity through this local App Server; `codex launch` supplies it",
)
def codex_start(
    dir: str,
    codex_path: str | None,
    app_server: str | None,
) -> None:
    """Start one task-wide delivery carrier and claim PAGE for it."""
    from leaf.codex_adapter import cmd_codex_start

    try:
        print(json.dumps(cmd_codex_start(resolve_dir(dir), codex_path, app_server)))
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error


@codex.command("run", hidden=True)
@click.option("--codex-path", required=True)
@click.option("--handshake", type=int)
@click.option("--app-server", hidden=True)
def codex_run(
    codex_path: str,
    handshake: int | None,
    app_server: str | None,
) -> None:
    """Run the detached carrier child."""
    from contextlib import nullcontext

    from leaf.codex_adapter import run_adapter
    from leaf.detached import Handshake
    from leaf.leases import release_on_termination

    release_on_termination()

    # Tests run the carrier in the foreground, where nobody waits on a handshake.
    with Handshake(handshake) if handshake is not None else nullcontext() as answer:
        sys.exit(run_adapter(codex_path, answer, app_server))


@cli.group(short_help="Create, check, stamp, and read pages.")
def page() -> None:
    """Create, check, stamp, and read pages."""


@page.command(short_help="Create or re-vendor a page directory.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--package",
    "selected",
    multiple=True,
    metavar="PACKAGE",
    help="include an installed or bundled name, or an explicit "
    "project-relative/~ path; repeat for more",
)
@click.option(
    "--no-packages",
    is_flag=True,
    help="remove all explicit packages from an existing page",
)
def init(dir: str, selected: tuple[str, ...], no_packages: bool) -> None:
    """Create or re-vendor a page directory.

    Creates PAGE/revisions/, then vendors the widget layer.
    The author writes PAGE/index.html. Re-running preserves the page's explicit packages unless --package or
    --no-packages replaces them, and refuses vocabulary the page log can no longer
    read. A served page's server restarts around the re-vendor, at the same URL.
    A package may contain any subset of the package layout, including zero, one,
    or many widgets.
    """
    from leaf.vendoring import cmd_init

    if selected and no_packages:
        raise click.UsageError("--package and --no-packages cannot be used together")
    if any(not selection for selection in selected):
        raise click.UsageError("--package selections cannot be empty")
    if len(set(selected)) != len(selected):
        raise click.UsageError("each --package selection may appear only once")
    selections = () if no_packages else selected or None
    cmd_init(resolve_dir(dir, must_exist=False), selections)


@cli.group(short_help="Create, check, install, and run packages.")
def package() -> None:
    """Create, check, install, and run packages."""


@package.command("init", short_help="Create a package directory.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="PACKAGE",
)
@click.option(
    "--widget",
    metavar="TAG",
    help="add one upgraded content widget starter",
)
def package_init(package_path: Path, widget: str | None) -> None:
    """Create the package layout without replacing existing files.

    With --widget, add one checked upgraded content widget starter.
    """
    from leaf.packages import cmd_package_init

    cmd_package_init(package_path, widget)


@package.command("check", short_help="Check a package as one unit.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="PACKAGE",
)
@click.option(
    "--render",
    is_flag=True,
    help="also report on the package's widgets as its worked examples render",
)
def package_check(package_path: Path, render: bool) -> None:
    """Check the package as one composed unit.

    --render also draws each worked example the package's own widgets declare in
    the host's browser, the one `page check --render` finds, and prints what the
    widget quality checks find there. A finding is advice for the widgets' author
    and leaves the exit status alone.
    """
    from leaf.packages import cmd_package_check

    sys.exit(cmd_package_check(package_path, render))


@package.command("install", short_help="Install a package for selection by name.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="SOURCE",
)
def package_install(package_path: Path) -> None:
    """Check SOURCE and copy it into this user's package store.

    `page init --package NAME` then selects it by its directory name, on the
    same terms as a package Leaf ships.
    """
    from leaf.packages import cmd_package_install

    cmd_package_install(package_path)


@package.command(
    "run",
    short_help="Run one of a package's scripts.",
    context_settings={"ignore_unknown_options": True, "allow_interspersed_args": False},
)
@click.argument("name", metavar="PACKAGE")
@click.argument("script", metavar="SCRIPT")
@click.argument("arguments", nargs=-1, type=click.UNPROCESSED, metavar="[ARGS]...")
def package_run(name: str, script: str, arguments: tuple[str, ...]) -> None:
    """Run SCRIPT from PACKAGE's scripts/ with ARGS.

    PACKAGE is a bundled or installed package's name, as `page init --package`
    takes it. The script reads and writes stdin and stdout itself, so it sits
    in a pipeline as printed, and its exit status is the command's.
    """
    from leaf.packages import cmd_package_run

    cmd_package_run(name, script, arguments)


@page.command(short_help="Check the mutable page source.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--render", is_flag=True, help="also check the rendered page in the host's browser"
)
def check(dir: str, render: bool) -> None:
    """Check PAGE/index.html.

    Runs deterministic markup checks. --render also checks the drawn page in the
    host's browser: whichever executable LEAF_BROWSER_EXECUTABLE, CHROME_PATH, or
    CHROME_BIN names, else the installed Chrome, else the first browser on PATH.
    A host with no browser gets a note in place of each browser check.
    """
    from leaf.validation.command import cmd_check

    sys.exit(cmd_check(resolve_dir(dir), render))


@page.command()
@click.argument("dir", metavar="PAGE")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    metavar="FILE...",
)
def media(dir: str, files) -> None:
    """Add images, video, or audio and print their page paths.

    Copies each file into the page under a content-addressed name and prints
    one JSON line per file: its page `path` and its `source` file.
    """
    from leaf.media import cmd_media

    for src, url in cmd_media(resolve_dir(dir), [Path(f) for f in files]):
        print(json.dumps({"path": url, "source": str(src)}, ensure_ascii=False))


@page.command(short_help="Read instructions for selected components and audience.")
@click.argument("dir", metavar="PAGE")
@click.argument("audience", required=False, metavar="AUDIENCE")
@click.option("--widget", "widgets", multiple=True, metavar="TAG")
@click.option("--contract", "contracts", multiple=True, metavar="ID")
def instructions(
    dir: str, audience: str | None, widgets: tuple[str, ...], contracts: tuple[str, ...]
) -> None:
    """List audiences, or print AUDIENCE's selected-component instructions.

    With no component selection, read only shared package instructions. Select
    widgets before writing markup; their examples, required members, and data
    contracts bring their own instructions into the same reading.
    """
    from leaf.page import cmd_instructions

    cmd_instructions(resolve_dir(dir), audience, widgets=widgets, contracts=contracts)


@page.command(short_help="Print where the page, a thread, or a widget stands.")
@click.argument("dir", metavar="PAGE")
@click.argument("target", metavar="[ID]", required=False)
@click.option(
    "--after",
    type=click.IntRange(min=0),
    metavar="SEQ",
    help="a thread's history after this sequence (default: from its start)",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1, max=100),
    help="how many of a thread's messages to print (default: 50)",
)
def state(dir: str, target: str | None, after: int | None, limit: int | None) -> None:
    """Fold the log onto the active revision and print the result as one JSON
    object: the active revision's file, standing state, reports, open Asks,
    thread summaries, versions, presence, and bound data. Read the active
    revision's HTML beside it for the document.

    ID narrows the reading to what it names. A message, or a widget frozen into
    one, names its thread: the reading is that thread with a page of its messages,
    their frozen markup, and the state on its widgets, paged by --after and
    --limit. A widget on the page names itself: its element, the moves and reports
    standing on it, its Asks, and its workflows."""
    from leaf.agent_state import cmd_page_state

    if target is None and (after is not None or limit is not None):
        raise click.UsageError("--after and --limit page a thread; name one as ID")
    cmd_page_state(resolve_dir(dir), target, after=after, limit=limit)


@page.command(short_help="Stamp the current source as the next version.")
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
    silently remove its page target.
    """
    from leaf.publishing import cmd_stamp

    _print_records(cmd_stamp(resolve_dir(dir), text, completes))


@page.command(short_help="Export a stamped version to one HTML file.")
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
    """Export a stamped version to one HTML file that opens offline.

    The file runs the page's own runtime against its captured state, with no Leaf
    server or host behind it.
    """
    from leaf.exporting import cmd_export

    sys.exit(cmd_export(resolve_dir(dir), out, version))


@page.command(short_help="Picture a drawing comment as the user saw it.")
@click.argument("dir", metavar="PAGE")
@click.argument("message", metavar="ID")
def picture(dir: str, message: str) -> None:
    """Draw comment ID's drawing over the page as the user saw it, and print the
    path of the PNG.

    Opens the comment's revision in the host's browser, with the log applied
    through the comment, at the window size and color scheme the drawing was
    made in, and crops to the ink and the page around it. Bound data is read as
    it stands now, and the host's fonts may differ from the user's.
    """
    from leaf.render_gate.picture import cmd_picture

    sys.exit(cmd_picture(resolve_dir(dir), message))


@page.command(short_help="Report a state change onto a page widget, as a worker.")
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(dir: str, widget: str, verb: str, fields: tuple) -> None:
    """Report a state change onto a page widget, as a worker.

    The verb and its fields are the widget's own agent-written x-state verb —
    `leaf page report <page> t-parser status status=review` moves a
    task. The page paints the report live as provisional news; it stands until a
    version absorbs or overrules it, and the page's watcher wakes to fold it in.
    """
    from leaf.thread import cmd_report

    _print_records(cmd_report(resolve_dir(dir), widget, verb, fields))


@page.command(short_help="Print the event log as JSON lines.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--after",
    type=int,
    default=0,
    metavar="SEQ",
    help="print events after this sequence",
)
@click.option(
    "--follow",
    is_flag=True,
    help="keep printing each event as it is appended, until stopped",
)
def events(dir: str, after: int, follow: bool) -> None:
    """Print the event log as JSON lines.

    Each line is one stored event record; `seq` is its position, and `--after`
    resumes from the last one a reader saw. This is read-only and does not
    acknowledge user events. `page state PAGE ID` reads one thread or widget.
    """
    from leaf.event_log import cmd_events

    cmd_events(resolve_dir(dir), after, follow=follow)


@page.command(short_help="Take a page this session did not serve.")
@click.argument("dir", metavar="PAGE")
def claim(dir: str) -> None:
    """Make PAGE this session's, as a named `leaf wait PAGE` does before it
    watches, for a harness whose own hook watches between turns. A watch another
    session runs stops watching it."""
    from leaf.service import claim_page

    if not claim_page(resolve_dir(dir)):
        sys.exit("only an agent harness session can claim a page")


@page.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> None:
    """Print the page's exchange as Markdown."""
    from leaf.transcript import cmd_transcript

    cmd_transcript(resolve_dir(dir))


@cli.group(short_help="Read input delivered by any Leaf harness.")
def delivery() -> None:
    """Handle transport-independent Leaf deliveries."""


@delivery.command("ack", short_help="Confirm one delivery you have read in full.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
def delivery_ack(delivery_id: str) -> None:
    """Confirm DELIVERY_ID once all of it is in your context, so the user's moves
    read Picked up. Confirm nothing whose output was cut off; `leaf wait --ack`
    confirms the same way and then waits for the next delivery."""
    from leaf.delivery import receive_delivery

    receive_delivery(delivery_id)


@delivery.command("read", short_help="Read one immutable delivery envelope.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
def delivery_read(delivery_id: str) -> None:
    """Print DELIVERY_ID with its complete batches and response requirements."""
    from leaf.delivery import cmd_delivery_read

    cmd_delivery_read(delivery_id)


@cli.group(short_help="Open, answer, edit, summarize, or resolve a thread.")
def thread() -> None:
    """Open and answer threads as the agent, and maintain them.

    Every write prints the records it appended, one JSON line each, as `page
    events` prints them. `page state PAGE ID` reads one thread."""


@thread.command("summarize", short_help="Summarize a contiguous message range.")
@click.argument("dir", metavar="PAGE")
@click.option("--from", "from_message", required=True, metavar="MESSAGE")
@click.option("--through", "through_message", required=True, metavar="MESSAGE")
@click.option(
    "--text", help="summary Markdown; pass '' to fold without prose (default: stdin)"
)
@click.option("--label", help="disclosure label (default: Earlier discussion)")
def thread_summarize(
    dir: str,
    from_message: str,
    through_message: str,
    text: str | None,
    label: str | None,
) -> None:
    """Replace --from through --through in the panel with a Markdown summary.

    Both name messages in one thread, which is the thread summarized. The original
    messages remain in the append-only transcript and can always be revealed. A
    later overlapping summary replaces this one.
    """
    from leaf.thread import cmd_summarize

    _print_records(
        cmd_summarize(
            resolve_dir(dir), from_message, through_message, text, label=label
        )
    )


@cli.group(short_help="Set or clear page-bound external data.")
def data() -> None:
    """Manage each bound source's current value, one JSON file per source."""


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
    from leaf.data import cmd_data_set

    text = input_file.read()
    if not text.strip():
        # Usually a producer upstream in the pipe failed and wrote nothing, and
        # its own error is the one to read; a JSON parse error would bury it.
        raise click.ClickException(
            "no value arrived on stdin; if a command piped into this one, it "
            "likely failed, and its error above says why"
            if input_file.name == "<stdin>"
            else f"{input_file.name} is empty; it holds no JSON value"
        )
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise click.ClickException(
            f"invalid JSON ({error.msg}, line {error.lineno})"
        ) from error
    cmd_data_set(resolve_dir(dir), source, value)


@data.command("clear", short_help="Remove one source's current value.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
def data_clear(dir: str, source: str) -> None:
    """Remove SOURCE's value; the id keeps the contract it was recorded with."""
    from leaf.data import cmd_data_clear

    cmd_data_clear(resolve_dir(dir), source)


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

    Returns once the server and this harness's feedback route are ready; the server itself keeps running in a
    session of its own. `leaf server stop` takes one down, and a session server
    goes down with the session that claimed it besides. A page already served
    reconnects delivery and prints that server's URL. `--standing` claims no
    page and prepares no agent delivery.
    """
    from leaf.hosting import claim_and_start

    try:
        with claim_and_start(resolve_dir(dir), host, standing) as started:
            pass
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    print(json.dumps({"url": started.url}))
    print(started.note, file=sys.stderr)


@server.command(short_help="Serve a page in the foreground until stopped.")
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option(
    "--temporary",
    is_flag=True,
    help="serve on loopback for this command only, without claiming the page",
)
def run(dir: str, host: str | None, standing: bool, temporary: bool) -> None:
    """Serve a page in the foreground, printing its URL and running until stopped.

    Run this in a terminal of your own to hold a page up where you can watch it.
    Browser harnesses use `--temporary`; a user page in an agent session uses
    `server start`. A page already served prints that server's URL and exits.
    """
    from leaf.hosting import cmd_serve, cmd_serve_temporary

    page_dir = resolve_dir(dir)
    if temporary:
        if standing:
            raise click.UsageError("choose --temporary or --standing")
        if host:
            raise click.UsageError("--temporary is loopback-only; omit --host")
        cmd_serve_temporary(page_dir)
        return
    try:
        cmd_serve(page_dir, host, standing, acquire=True)
    except RuntimeError as error:
        raise SystemExit(str(error)) from None


@server.command("_serve", hidden=True)
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option("--revive", is_flag=True, hidden=True)
@click.option("--acquire", is_flag=True, hidden=True)
@click.option("--claim", hidden=True)
@click.option("--handshake", type=int, required=True, hidden=True)
def _serve(
    dir: str,
    host: str | None,
    standing: bool,
    revive: bool,
    acquire: bool,
    claim: str | None,
    handshake: int,
) -> None:
    """Private child process spawned by server start and Watch revival."""
    from leaf.detached import Handshake
    from leaf.hosting import cmd_serve

    with Handshake(handshake) as answer:
        cmd_serve(
            resolve_dir(dir),
            host,
            standing,
            revive,
            handshake=answer,
            acquire=acquire,
            prepared_claim=json.loads(claim) if claim is not None else None,
        )


@server.command(short_help="Stop a page's server.")
@click.argument("dir", metavar="PAGE")
def stop(dir: str) -> None:
    """Stop a page's server."""
    from leaf.hosting import cmd_stop

    print(json.dumps({"stopped": cmd_stop(resolve_dir(dir))}))


@cli.command(short_help="Set the agent's banner state.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["working", "waiting", "idle"]))
@click.argument("detail", required=False, default="")
@click.option(
    "--on",
    "on",
    metavar="SUBJECT",
    help="The open thread or widget this work is about.",
)
def status(dir: str, state: str, detail: str, on: str | None) -> None:
    """Set the agent's banner state.

    Use working with DETAIL, required, naming your current work and its
    subject, or waiting with the answer you want from the user. Waiting without
    DETAIL invites text comments. Use idle when finished; unacknowledged input
    and unanswered user moves prevent it.

    With working, --on names an open thread, by any message in it, or a widget:
    whatever a delivered event gives as its address, which then reads Working.
    The user sees DETAIL beside that subject as well as in the banner.
    Your next reply ends a thread claim; `leaf page stamp --completes` ends
    a widget claim. Renew the status as work changes: a claim left after your
    turn ends, or without updates, eventually reads as stalled.
    """
    from leaf.activity import unanswered
    from leaf.session import cmd_idle, cmd_status

    page_dir = resolve_dir(dir)
    owed = []
    if state == "idle":
        written = cmd_idle(page_dir, detail, on)
    else:
        written, owed = cmd_status(page_dir, state, detail, on=on)
    print(json.dumps(written, ensure_ascii=False))
    if state == "waiting" and owed:
        click.echo(
            f"{unanswered(owed)}; the page reads waiting once each has one", err=True
        )


@cli.command(
    short_help="Confirm a delivery, if given, then wait for the next batch.",
    help=(
        "Watch every page this session holds — plus PAGE, claimed first, when "
        "given.\n\n" + WAIT_BATCH_OUTPUT_INSTRUCTION
    ),
)
@click.argument("dir", metavar="PAGE", required=False)
@click.option(
    "--ack",
    metavar="DELIVERY_ID",
    help="Confirm receipt of this complete delivery before waiting.",
)
def wait(dir: str | None, ack: str | None) -> None:
    """Confirm a delivery, if given, then wait for the next batch."""
    from leaf.leases import release_on_termination
    from leaf.session import cmd_wait

    if dir is not None and ack is not None:
        raise click.UsageError("PAGE and --ack cannot be used together")
    release_on_termination()
    try:
        outcome = cmd_wait(resolve_dir(dir) if dir else None, ack=ack)
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error
    sys.exit(outcome)


def _title_option(command):
    return click.option(
        "--title",
        help=(
            "name the thread for the panel unless it has a name: a few words, at "
            "most 80 characters"
        ),
    )(command)


def _name(page_dir: Path, message: str, title: str | None) -> None:
    """Name the thread a posted message is in, unless something named it first."""
    from leaf.thread import cmd_name

    if title is None:
        return
    if record := cmd_name(page_dir, message, title):
        _print_records(record)
    else:
        print(
            "the thread already has a title, which stands; "
            f"`leaf thread edit {page_dir} {message} --title` renames it",
            file=sys.stderr,
        )


def _titled(page_dir: Path, title: str | None) -> None:
    """Refuse a title admission would refuse before its command posts anything.
    Past this the title can fail only with the page itself, and then the message
    stands, already printed, for the refusal that follows it to be read against."""
    from leaf.thread import title_refusal

    if title is not None and (refusal := title_refusal(page_dir, title)):
        sys.exit(refusal)


@thread.command(
    "open", short_help="Open an agent thread — on a passage, or on the page whole."
)
@click.argument("dir", metavar="PAGE")
@click.option("--quote", help="passage text from the active revision")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--part", metavar="ID", help="declared visual part within --section")
@click.option("--text", help="comment text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
@_title_option
def thread_open(
    dir: str,
    quote: str,
    section: str,
    part: str,
    text: str,
    markup: str,
    title: str | None,
) -> None:
    """Open a thread as the agent (--text or stdin): anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    The user answers it in the browser. Refuses a quote the active revision does
    not hold, or holds more than once. The comment's id is the thread's.
    """
    from leaf.thread import cmd_comment

    page_dir = resolve_dir(dir)
    _titled(page_dir, title)
    accepted = cmd_comment(page_dir, quote, section, part, text, markup)
    _print_records(accepted)
    _name(page_dir, accepted["id"], title)


@thread.command("reply", short_help="Reply to a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.argument("thread", metavar="[THREAD]", required=False)
@click.option(
    "--for",
    "for_event",
    metavar="EVENT_ID",
    help="delivery event whose current reply obligation this answers",
)
@click.option("--quote", help="new passage text to move this thread onto")
@click.option("--section", metavar="ID", help="new element ID, or scope for --quote")
@click.option("--part", metavar="ID", help="new declared visual part within --section")
@click.option(
    "--detach",
    is_flag=True,
    help="remove the current page target when its subject leaves the page",
)
@click.option("--text", help="reply text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
@click.option(
    "--awaits", is_flag=True, help="the reply's prose asks the user a question"
)
@click.option(
    "--ephemeral",
    is_flag=True,
    help="progress update; folds when the next ordinary agent reply arrives",
)
@_title_option
def thread_reply(
    dir: str,
    thread: str | None,
    for_event: str | None,
    quote: str,
    section: str,
    part: str,
    detach: bool,
    text: str,
    markup: str,
    awaits: bool,
    ephemeral: bool,
    title: str | None,
) -> None:
    """Post a threaded reply as the agent (--text or stdin).

    Answer user input with --for EVENT_ID. With exactly one outstanding reply
    in this turn's opened delivery, omit it to select that reply. THREAD, by
    any message in it, posts a new agent message there instead, refused while
    that thread owes a reply.

    --quote, --section, and --part move the thread's current anchor; --detach
    removes it when the subject leaves the page. The original anchor stays in
    the log. A reply validates and activates any changed source before posting.
    """
    from leaf.thread import cmd_reply

    if thread is not None and for_event is not None:
        raise click.UsageError("THREAD and --for cannot be used together")
    page_dir = resolve_dir(dir)
    _titled(page_dir, title)
    accepted = cmd_reply(
        page_dir,
        thread,
        text,
        markup,
        awaits,
        for_event=for_event,
        quote=quote,
        section=section,
        part=part,
        detach=detach,
        validate_source=True,
        ephemeral=ephemeral,
    )
    _print_records(accepted)
    _name(page_dir, accepted["id"], title)


@thread.command("edit", short_help="Edit a message's text, or its thread's title.")
@click.argument("dir", metavar="PAGE")
@click.argument("message", metavar="MESSAGE")
@click.option("--text", help="replacement text (default: stdin, unless --title)")
@click.option(
    "--title",
    help="rename MESSAGE's thread for the panel: a few words, at most 80 characters",
)
def thread_edit(dir: str, message: str, text: str | None, title: str | None) -> None:
    """Replace the visible text of MESSAGE, an agent-authored comment or reply,
    or with --title rename the thread MESSAGE is in, whoever opened it.

    The original and every revision remain in the append-only event log. Frozen
    widget markup is not editable. Keep a title stable unless the thread's
    subject changes.
    """
    from leaf.thread import cmd_edit, cmd_title

    page_dir = resolve_dir(dir)
    _titled(page_dir, title)
    records = []
    if text is not None or title is None:
        records.append(cmd_edit(page_dir, message, text))
    if title is not None:
        records.append(cmd_title(page_dir, message, title))
    _print_records(*records)


@thread.command("resolve", short_help="Close a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.argument("thread", metavar="THREAD")
def thread_resolve(dir: str, thread: str) -> None:
    """Close THREAD, by any message in it, as the agent.

    The user ordinarily closes a thread; the Leaf skill's
    references/threads.md says when the agent does. Refuses a thread
    that asked for a version until a stamped version answers it. The panel names
    who resolved it.
    """
    from leaf.thread import cmd_resolve

    _print_records(cmd_resolve(resolve_dir(dir), thread))


@cli.group(short_help="Open or end a task the agent has taken on.")
def task() -> None:
    """Hold work the agent owes on the page until it ends.

    A task stays on the agent's queue through replies, resolutions, versions and
    the end of the session that opened it; only `leaf task end` ends it. Every
    write prints the record it appended, one JSON line, as `page events` prints it.
    """


@task.command("open", short_help="Take on work a thread asked for.")
@click.argument("dir", metavar="PAGE")
@click.argument("subject", metavar="SUBJECT")
@click.argument("title", metavar="TITLE")
def task_open(dir: str, subject: str, title: str) -> None:
    """Open a task titled TITLE on the open thread SUBJECT names, by any message in
    it or a widget its messages carry. Its id is the printed record's `id`."""
    from leaf.tasks import cmd_open

    _print_records(cmd_open(resolve_dir(dir), subject, title))


@task.command("end", short_help="End a task: done, failed, or dropped.")
@click.argument("dir", metavar="PAGE")
@click.argument("task_id", metavar="TASK")
@click.argument("outcome", type=click.Choice(["done", "failed", "dropped"]))
@click.argument("detail", metavar="[DETAIL]", required=False)
def task_end(dir: str, task_id: str, outcome: str, detail: str | None) -> None:
    """End TASK with OUTCOME. DETAIL says where the result is, such as the
    version or reply holding it, or why there is none."""
    from leaf.tasks import cmd_end

    _print_records(cmd_end(resolve_dir(dir), task_id, outcome, detail))


@cli.command(hidden=True)
@click.option(
    "--harness",
    required=True,
    help="The harness whose registration runs this hook.",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch the session's pages until input, printing what wakes the session.",
)
def hook(harness: str, watch: bool) -> None:
    """Answer an agent-harness hook on stdin."""
    from leaf.hooks import main

    main(harness, watch=watch)


@cli.command(hidden=True)
def session_end() -> None:
    """Release ownership for the harness's SessionEnd payload on stdin."""
    from leaf.state import main

    main()
