"""Click declarations and production command wiring."""

import json
import sys
from pathlib import Path

import click

from leaf.schema import (
    EVENTS_FILE,
    SKILL_ROOT,
    WAIT_BATCH_OUTPUT_INSTRUCTION,
)


def resolve_dir(dir_arg: str, must_exist: bool = True) -> Path:
    page_dir = Path(dir_arg).expanduser().resolve()
    if must_exist and not (page_dir / EVENTS_FILE).is_file():
        sys.exit(
            f"{page_dir} is not an initialized page; run `leaf page init` "
            "to vendor the layer"
        )
    return page_dir


def _leaf_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print the source identity of the Leaf payload running this command."""
    if not value or ctx.resilient_parsing:
        return
    from leaf.layer import payload_provenance

    producer = payload_provenance()
    commit = producer.get("commit")
    identity = (
        f"{commit}{'+' if producer.get('dirty') else ''}" if commit else "unknown"
    )
    click.echo(f"leaf {identity}")
    ctx.exit()


def _leaf_root(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print which copy of leaf this is, and stop.

    A host session runs the payload its plugin cache holds, not the checkout,
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


@cli.command(short_help="Run Leaf's bundled MCP Apps server.")
def mcp() -> None:
    """Serve Leaf tools and its interactive review resource over stdio."""
    from leaf.mcp_server import run_mcp_server

    run_mcp_server()


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
        click.echo(cmd_codex_start(resolve_dir(dir), codex_path, app_server))
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
    read. A package may contain any subset of the package layout, including zero,
    one, or many widgets.
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
def package_check(package_path: Path) -> None:
    """Check the package as one composed unit."""
    from leaf.packages import cmd_package_check

    cmd_package_check(package_path)


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
    from leaf.media import cmd_media

    for src, url in cmd_media(resolve_dir(dir), [Path(f) for f in files]):
        print(f"{url}\t{src}")


@page.command(short_help="List or print composed guidance by audience.")
@click.argument("dir", metavar="PAGE")
@click.argument("audience", required=False, metavar="AUDIENCE")
def guidance(dir: str, audience: str | None) -> None:
    """List audiences, or print the guidance for AUDIENCE."""
    from leaf.page import cmd_guidance

    cmd_guidance(resolve_dir(dir), audience)


@page.command(short_help="Print where the page stands, as JSON.")
@click.argument("dir", metavar="PAGE")
def state(dir: str) -> None:
    """Fold the log onto the active revision and print the result as one JSON
    object: effective content with source and edit addresses, standing state,
    reports, open Asks, conversation summaries, versions, presence, and bound data.
    Content follows the same document projection as the browser."""
    from leaf.agent_state import cmd_page_state

    cmd_page_state(resolve_dir(dir))


@cli.group(short_help="Claim or read input delivered by any Leaf host.")
def delivery() -> None:
    """Handle transport-independent Leaf deliveries."""


@delivery.command("claim", short_help="Mark delivered user input as Working.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
@click.option(
    "--event",
    "event_id",
    metavar="EVENT_ID",
    help="Claim this delivered event instead of the first outstanding user move.",
)
@click.option(
    "--detail",
    default=None,
    help='What the page says the agent is doing (default: "Reading your feedback").',
)
def delivery_claim(delivery_id: str, event_id: str | None, detail: str | None) -> None:
    """Claim one still-outstanding user move from DELIVERY_ID.

    The page and subject come from the immutable delivery. Current page state is
    checked in the same transaction that writes the Working receipt, so a stale
    delivery is a successful no-op rather than a claim on newer input.
    """
    from leaf.session import cmd_delivery_claim

    click.echo(cmd_delivery_claim(delivery_id, detail=detail, event_id=event_id))


@delivery.command("read", short_help="Read one immutable delivery envelope.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
def delivery_read(delivery_id: str) -> None:
    """Print DELIVERY_ID with its complete batches and response requirements."""
    from leaf.delivery import cmd_delivery_read

    cmd_delivery_read(delivery_id)


@cli.group(short_help="Read, name, or summarize a Leaf conversation.")
def conversation() -> None:
    """Read and maintain conversations without selecting delivery work."""


@conversation.command("read", short_help="Read one bounded conversation history.")
@click.argument("dir", metavar="PAGE")
@click.argument("conversation_id", metavar="CONVERSATION_ID")
@click.option(
    "--after",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    metavar="SEQ",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1, max=100),
    default=50,
    show_default=True,
)
def conversation_read(
    dir: str,
    conversation_id: str,
    after: int,
    limit: int,
) -> None:
    """Print one current conversation and a page of its exact event history."""
    from leaf.agent_state import cmd_conversation_read

    cmd_conversation_read(
        resolve_dir(dir),
        conversation_id,
        after=after,
        limit=limit,
    )


@conversation.command("title", short_help="Set or update a short conversation title.")
@click.argument("dir", metavar="PAGE")
@click.argument("conversation_id", metavar="CONVERSATION_ID")
@click.option(
    "--text", required=True, help="short descriptive title (at most 80 characters)"
)
@click.option("--json", "as_json", is_flag=True, help="print the title event")
def conversation_title(
    dir: str, conversation_id: str, text: str, as_json: bool
) -> None:
    """Name the conversation for the thread panel; repeat to rename it.

    Choose a few descriptive words when first handling a conversation. Keep the
    title stable unless its subject changes. This adds no message or reply.
    """
    from leaf.conversation import cmd_title

    accepted = cmd_title(resolve_dir(dir), conversation_id, text)
    if as_json:
        click.echo(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"named conversation {conversation_id}: {accepted['title']}")


@conversation.command("summarize", short_help="Summarize a contiguous message range.")
@click.argument("dir", metavar="PAGE")
@click.argument("conversation_id", metavar="CONVERSATION_ID")
@click.option("--from", "from_message", required=True, metavar="ID")
@click.option("--through", "through_message", required=True, metavar="ID")
@click.option("--text", help="summary Markdown (default: stdin)")
@click.option("--json", "as_json", is_flag=True, help="print the summary event")
def conversation_summarize(
    dir: str,
    conversation_id: str,
    from_message: str,
    through_message: str,
    text: str | None,
    as_json: bool,
) -> None:
    """Replace FROM through THROUGH in the panel with a Markdown summary.

    The original messages remain in the append-only transcript and can always be
    revealed. A later overlapping summary replaces this one.
    """
    from leaf.conversation import cmd_summarize

    accepted = cmd_summarize(
        resolve_dir(dir), conversation_id, from_message, through_message, text
    )
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"summarized {from_message} through {through_message}")


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


@cli.group(short_help="Check, stamp, and export versions.")
def version() -> None:
    """Check, stamp, and export versions."""


@version.command(short_help="Check the mutable page source.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--render", is_flag=True, help="also check the rendered page in the host's browser"
)
def check(dir: str, render: bool) -> None:
    """Check PAGE/index.html.

    Runs deterministic markup checks. --render also checks the drawn page in the
    host's browser: whichever executable LEAF_BROWSER_EXECUTABLE, CHROME_PATH, or
    CHROME_BIN names, else the installed Chrome, else the first browser on PATH.
    """
    from leaf.validation.command import cmd_check

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
@click.option("--json", "as_json", is_flag=True, help="print the note event instead")
def stamp(dir: str, text: str, completes: tuple[str, ...], as_json: bool) -> None:
    """Stamp PAGE/index.html with a changelog.

    Checks the exact source first, then records it as the next public version. Repeat
    --completes for each active widget work claim this version completes. A
    widget claim otherwise survives unrelated versions, and a version cannot
    silently remove its page target.
    """
    from leaf.publishing import cmd_stamp

    accepted = cmd_stamp(resolve_dir(dir), text, completes)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"stamped v{accepted['version']} — {accepted['text']}")


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
@click.option(
    "--interactive",
    is_flag=True,
    help="keep captured local behavior; disable Leaf host commands",
)
def export(dir: str, out: Path, version: int, interactive: bool) -> None:
    """Export a stamped version to one HTML file.

    The default is a rendered, script-free record. --interactive keeps the captured
    local behavior and opens offline without a Leaf server.
    """
    from leaf.exporting import cmd_export

    sys.exit(cmd_export(resolve_dir(dir), out, version, interactive=interactive))


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
    from leaf.detached import StartRefused
    from leaf.hosting import claim_and_start

    try:
        url, note = claim_and_start(resolve_dir(dir), host, standing)
    except StartRefused as error:
        raise SystemExit(str(error)) from None
    print(url)
    print(note, file=sys.stderr)


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
    from leaf.service import starting_claim

    page_dir = resolve_dir(dir)
    if temporary:
        if standing:
            raise click.UsageError("choose --temporary or --standing")
        if host:
            raise click.UsageError("--temporary is loopback-only; omit --host")
        cmd_serve_temporary(page_dir)
        return
    with starting_claim(page_dir, standing=standing):
        cmd_serve(page_dir, host, standing)


@server.command("_serve", hidden=True)
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option("--revive", is_flag=True, hidden=True)
@click.option("--handshake", type=int, required=True, hidden=True)
def _serve(
    dir: str, host: str | None, standing: bool, revive: bool, handshake: int
) -> None:
    """Private child process spawned by server start and Watch revival."""
    from leaf.detached import Handshake
    from leaf.hosting import cmd_serve

    with Handshake(handshake) as answer:
        cmd_serve(resolve_dir(dir), host, standing, revive, handshake=answer)


@server.command(short_help="Stop a page's server.")
@click.argument("dir", metavar="PAGE")
def stop(dir: str) -> None:
    """Stop a page's server."""
    from leaf.hosting import cmd_stop

    print(cmd_stop(resolve_dir(dir)))


def _status_line(state: str, detail: str, on: str | None) -> str:
    """Read the transition back, so a silent success cannot pass for a no-op."""
    subject = f" on {on}" if on else ""
    said = f" — {detail}" if detail else ""
    return f"{state}{subject}{said}"


@cli.command(short_help="Set the agent's banner state.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["working", "waiting", "idle"]))
@click.argument("detail", required=False, default="")
@click.option(
    "--on",
    "on",
    metavar="SUBJECT",
    help="The open conversation or local page widget this work is about.",
)
def status(dir: str, state: str, detail: str, on: str | None) -> None:
    """Set the agent's banner state.

    Use working with DETAIL naming your current work, or waiting with the answer
    you want from the user. Waiting without DETAIL invites text comments.
    Use idle when finished; unacknowledged input and unanswered user moves
    prevent it.

    With working, --on names an open conversation or page widget and requires
    DETAIL. The user sees it beside that subject as well as in the banner.
    Your next reply ends a thread claim; a version stamp with --completes ends
    a widget claim. Renew the status as work changes: a claim left after your
    turn ends, or without updates, eventually reads as stalled.
    """
    from leaf.activity import unanswered
    from leaf.session import cmd_idle, cmd_status

    page_dir = resolve_dir(dir)
    owed = []
    if state == "idle":
        cmd_idle(page_dir, detail, on)
    else:
        owed = cmd_status(page_dir, state, detail, on=on)
    click.echo(_status_line(state, detail, on))
    if state == "waiting" and owed:
        click.echo(f"{unanswered(owed)}; the page reads waiting once each has one")


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


@cli.command(short_help="Open an agent thread — on a passage, or on the page whole.")
@click.argument("dir", metavar="PAGE")
@click.option("--quote", help="passage text from the active revision")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--part", metavar="ID", help="declared visual part within --section")
@click.option("--text", help="comment text (default: stdin)")
@click.option("--markup", help="widget markup to render after the text, validated here")
@click.option("--json", "as_json", is_flag=True, help="print the comment event instead")
def comment(
    dir: str,
    quote: str,
    section: str,
    part: str,
    text: str,
    markup: str,
    as_json: bool,
) -> None:
    """Open a thread as the agent (--text or stdin): anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    The user answers it in the browser. Refuses a quote the active revision does
    not hold, or holds more than once.
    """
    from leaf.conversation import cmd_comment

    accepted = cmd_comment(resolve_dir(dir), quote, section, part, text, markup)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"opened thread {accepted['id']}")
    click.echo(
        f"name it: leaf conversation title {dir} {accepted['id']} "
        '--text "<a few words>"'
    )


@cli.command(short_help="Reply to a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--to",
    metavar="ID",
    help="conversation message ID for --initiates; inferred when answering --for",
)
@click.option(
    "--for",
    "for_event",
    metavar="EVENT_ID",
    help="delivery event whose current reply obligation this answers",
)
@click.option(
    "--initiates",
    is_flag=True,
    help="start an agent turn only when this conversation owes no reply",
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
@click.option("--json", "as_json", is_flag=True, help="print the reply event instead")
def reply(
    dir: str,
    to: str,
    for_event: str | None,
    initiates: bool,
    quote: str,
    section: str,
    part: str,
    detach: bool,
    text: str,
    markup: str,
    awaits: bool,
    as_json: bool,
) -> None:
    """Post a threaded reply as the agent (--text or stdin).

    Answer user input with --for EVENT_ID. With exactly one outstanding reply
    in this turn's opened delivery, omit it to select that reply. To add a new
    agent message when no reply is owed, use --to ID --initiates.

    --quote, --section, and --part move the thread's current anchor; --detach
    removes it when the subject leaves the page. The original anchor stays in
    the log. A reply validates and activates any changed source before posting.
    """
    from leaf.conversation import cmd_reply, thread_of

    page_dir = resolve_dir(dir)
    accepted = cmd_reply(
        page_dir,
        to,
        text,
        markup,
        awaits,
        for_event=for_event,
        initiates=initiates,
        quote=quote,
        section=section,
        part=part,
        detach=detach,
        validate_source=True,
    )
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"replied in {thread_of(page_dir, accepted['id'])}")


@cli.command(short_help="Edit one of this agent session's messages.")
@click.argument("dir", metavar="PAGE")
@click.option("--to", required=True, metavar="ID", help="comment or reply ID to edit")
@click.option("--text", help="replacement text (default: stdin)")
@click.option("--json", "as_json", is_flag=True, help="print the edit event instead")
def edit(dir: str, to: str, text: str, as_json: bool) -> None:
    """Replace the visible text of an agent-authored comment or reply.

    The original and every revision remain in the append-only event log. Frozen
    widget markup is not editable.
    """
    from leaf.conversation import cmd_edit, thread_of

    page_dir = resolve_dir(dir)
    accepted = cmd_edit(page_dir, to, text)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"edited {to} in {thread_of(page_dir, to)}")


@cli.command(short_help="Close a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--to", required=True, metavar="ID", help="a message in the thread to close"
)
@click.option("--json", "as_json", is_flag=True, help="print the resolve event instead")
def resolve(dir: str, to: str, as_json: bool) -> None:
    """Close a thread as the agent.

    The user ordinarily closes a thread; the Leaf skill's
    references/conversation-threads.md says when the agent does. Refuses a thread
    that asked for a version until a stamped version answers it. The panel names
    who resolved it.
    """
    from leaf.conversation import cmd_resolve, thread_of

    page_dir = resolve_dir(dir)
    accepted = cmd_resolve(page_dir, to)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"resolved {thread_of(page_dir, to)}")


@cli.command(short_help="Report a state change onto a page widget, as a worker.")
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
@click.option("--json", "as_json", is_flag=True, help="print the report event instead")
def report(
    dir: str,
    widget: str,
    verb: str,
    fields: tuple,
    as_json: bool,
) -> None:
    """Report a state change onto a page widget, as a worker.

    The verb and its fields are the widget's own agent-written x-state verb —
    `leaf report <page> t-parser status status=review` moves a task. The
    page paints the report live as provisional news; it stands until a version
    absorbs or overrules it, and the page's watcher wakes to fold it in.
    """
    from leaf.conversation import cmd_report

    accepted = cmd_report(resolve_dir(dir), widget, verb, fields)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"reported {verb} on {widget}")


@cli.command(short_help="Record the terminal outcome of a user request.")
@click.argument("dir", metavar="PAGE")
@click.argument("request", metavar="REQUEST")
@click.argument(
    "status",
    type=click.Choice(["succeeded", "failed"]),
    metavar="succeeded|failed",
)
@click.option("--text", help="host outcome (default: stdin)")
@click.option("--json", "as_json", is_flag=True, help="print the receipt event instead")
def receipt(dir: str, request: str, status: str, text: str, as_json: bool) -> None:
    """Record exactly one terminal host outcome for REQUEST."""
    from leaf.requests import cmd_receipt

    accepted = cmd_receipt(resolve_dir(dir), request, status, text)
    if as_json:
        print(json.dumps(accepted, ensure_ascii=False))
        return
    click.echo(f"settled request {request} as {status}")


@cli.command(short_help="Print the event log as JSON lines.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--after",
    type=int,
    default=0,
    metavar="SEQ",
    help="print events after this sequence",
)
@click.option(
    "--conversation",
    metavar="CONVERSATION",
    help="print only events belonging to this exact conversation id",
)
@click.option(
    "--follow",
    is_flag=True,
    help="keep printing each event as it is appended, until stopped",
)
def events(dir: str, after: int, conversation: str | None, follow: bool) -> None:
    """Print the event log as JSON lines.

    Each line is one stored event record; `seq` is its position, and `--after`
    resumes from the last one a reader saw. CONVERSATION is an exact identity
    lookup, not a general event filter. This is read-only and does not
    acknowledge user events.
    """
    from leaf.transcript import cmd_events, cmd_follow_events

    if follow and conversation is not None:
        raise click.UsageError("--follow and --conversation cannot be used together")
    if follow:
        cmd_follow_events(resolve_dir(dir), after)
        return
    cmd_events(resolve_dir(dir), after, conversation)


@cli.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> None:
    """Print the page's exchange as Markdown."""
    from leaf.transcript import cmd_transcript

    cmd_transcript(resolve_dir(dir))


@cli.command(hidden=True)
def hook() -> None:
    """Answer an agent-host hook on stdin."""
    from leaf.hooks import cmd_hook

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        sys.exit(f"hook expects the host's JSON payload on stdin ({error.msg})")
    cmd_hook(payload)
