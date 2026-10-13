"""Click declarations and production command wiring."""

import json
import shlex
import sys
from pathlib import Path

import click

from leaf.schema import SKILL_ROOT, WAIT_BATCH_OUTPUT_INSTRUCTION
from leaf.state import EVENTS_FILE


def resolve_dir(dir_arg: str, must_exist: bool = True) -> Path:
    page_dir = Path(dir_arg).expanduser().resolve()
    if must_exist and not (page_dir / EVENTS_FILE).is_file():
        raise click.ClickException(
            f"{page_dir} is not an initialized page; "
            f"run `leaf page init {shlex.quote(str(page_dir))}`"
        )
    return page_dir


def _print_records(*records: dict | None) -> None:
    """Print what a write appended, each record as `page events` prints it."""
    from leaf.event_log import jsonl_line

    for record in records:
        if record is not None:
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


# Where a command's `--json` says the caller reads JSON, in the context every
# command's context shares (`click.Context.meta`).
JSON_REQUESTED = "leaf.json"


def _json_requested(ctx: click.Context, _param: click.Parameter, value: bool) -> bool:
    ctx.meta[JSON_REQUESTED] = value
    return value


def json_option(help: str, *, expose_value: bool = True):
    """A command's `--json`: what it prints becomes JSON, a refusal included
    (`LeafGroup`)."""
    return click.option(
        "--json",
        "as_json",
        is_flag=True,
        expose_value=expose_value,
        callback=_json_requested,
        help=help,
    )


class LeafGroup(click.Group):
    """Present a domain refusal (`refusals.Refused`) as a Click error.

    This is the command line's one translation of a refusal: its words on stderr, or,
    where the command was given `--json` (`json_option`), one JSON object on stdout,
    `Refused.json`, whose `findings` carry each refusal's code and fields. Either way
    the command exits 1. Exit statuses (including a package script's) keep their
    meaning and output, and any other exception surfaces with its traceback.
    """

    def invoke(self, ctx: click.Context):
        from leaf.refusals import Refused

        try:
            return super().invoke(ctx)
        except Refused as error:
            if ctx.meta.get(JSON_REQUESTED):
                click.echo(json.dumps(error.json(), ensure_ascii=False))
                ctx.exit(1)
            raise click.ClickException(str(error)) from error


class RecordsCommand(click.Command):
    """A write that prints each record it appended as one JSON line, as `page
    events` prints it, and with `--json` its refusal as one JSON object."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        json_option(
            "print a refusal as one JSON object: its error and the findings it rests on",
            expose_value=False,
        )(self)


class RecordsGroup(click.Group):
    """A group of `RecordsCommand` writes."""

    command_class = RecordsCommand


@click.group(cls=LeafGroup)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_leaf_version,
    help="Print the commit this Leaf runs from, with its commit or install date.",
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
    """Launch Codex or run Leaf's delivery adapter."""


@codex.command("launch", short_help="Launch an experimental streaming Codex terminal.")
@click.option("--codex-path", hidden=True)
def codex_launch(codex_path: str | None) -> None:
    """Run Codex with a private local App Server for Leaf delivery and activity.

    This integration is experimental.
    """
    from leaf.codex_adapter import cmd_codex_launch

    sys.exit(cmd_codex_launch(codex_path))


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
    """Start one task-wide delivery adapter and claim PAGE for it."""
    from leaf.codex_adapter import cmd_codex_start

    print(json.dumps(cmd_codex_start(resolve_dir(dir), codex_path, app_server)))


@codex.command("run", hidden=True)
@click.option("--codex-path", required=True)
@click.option("--handshake", type=int, required=True)
@click.option("--app-server", hidden=True)
def codex_run(
    codex_path: str,
    handshake: int,
    app_server: str | None,
) -> None:
    """Run the detached adapter child."""
    from leaf.codex_adapter import run_adapter
    from leaf.detached import Handshake
    from leaf.leases import release_on_termination

    release_on_termination()
    with Handshake(handshake) as answer:
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
@click.option(
    "--dry-run",
    is_flag=True,
    help="report whether re-vendoring would change an initialized page",
)
def init(dir: str, selected: tuple[str, ...], no_packages: bool, dry_run: bool) -> None:
    """Create or re-vendor a page directory.

    Creates PAGE/revisions/, then vendors the widget layer.
    The author writes PAGE/index.html. Re-running preserves the page's explicit packages unless --package or
    --no-packages replaces them, and validates the current vocabulary and markup.
    A changed layer restarts its server at the same URL; identical initialization
    leaves it running. --dry-run reports the planned change without writing it.
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
    cmd_init(resolve_dir(dir, must_exist=False), selections, dry_run=dry_run)


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
@json_option("print the findings as one JSON object instead of lines")
def package_check(package_path: Path, render: bool, as_json: bool) -> None:
    """Check the package as one composed unit.

    --render also draws each worked example the package's own widgets declare in
    the host's browser, the one `page check --render` finds, and prints what the
    widget quality checks find there. A finding is advice for the widgets' author
    and leaves the exit status alone. --json prints one object instead, in the
    shape `page check --json` prints.
    """
    from leaf.packages import cmd_package_check

    sys.exit(cmd_package_check(package_path, render, as_json))


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
@json_option("print the findings as one JSON object instead of lines")
def check(dir: str, render: bool, as_json: bool) -> None:
    """Check PAGE/index.html.

    Runs deterministic markup checks. --render also checks the drawn page in the
    host's browser: whichever executable LEAF_BROWSER_EXECUTABLE, CHROME_PATH, or
    CHROME_BIN names, else the installed Chrome, else the first browser on PATH.
    A host with no browser gets a note in place of each browser check. --json prints
    one object instead: the exit status, every finding with its code, element,
    measured values and severity, and what each browser check ran in.
    """
    from leaf.validation.command import cmd_check

    sys.exit(cmd_check(resolve_dir(dir), render, as_json))


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


@page.command(short_help="Read selected-component instructions by audience as JSON.")
@click.argument("dir", metavar="PAGE")
@click.option("--use", "entries", multiple=True, metavar="ENTRY")
@click.option("--contract", "contracts", multiple=True, metavar="ID")
def instructions(
    dir: str, entries: tuple[str, ...], contracts: tuple[str, ...]
) -> None:
    """Print a JSON object mapping each audience to its composed instructions.

    With no component selection, read only shared package instructions. Select
    vocabulary entries before writing markup; their examples and data
    contracts bring their own instructions into the same reading.
    """
    from leaf.page import cmd_instructions

    cmd_instructions(resolve_dir(dir), entries=entries, contracts=contracts)


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
    """Print the page as it is now, as one JSON object: the active revision's
    file, the current widget actions and workers' reports, the user's On me list and
    yours, thread summaries, versions, presence, and bound data. Read the active
    revision's HTML beside it for the document.

    ID narrows the output to what it names. A message, or a widget frozen into
    one, names its thread: the output is that thread with a page of its messages,
    their frozen markup, and the state of its widgets, paged by --after and
    --limit. A widget on the page names itself: its element, its current actions
    and reports, its asks and to-dos, and its workflows."""
    from leaf.agent_state import cmd_page_state

    if target is None and (after is not None or limit is not None):
        raise click.UsageError("--after and --limit page a thread; name one as ID")
    cmd_page_state(resolve_dir(dir), target, after=after, limit=limit)


@page.command(
    cls=RecordsCommand, short_help="Stamp the current source as the next version."
)
@click.argument("dir", metavar="PAGE")
@click.option("--text", help="changelog text (default: stdin)")
@click.option(
    "--from-directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="replace index.html and page/ together from this candidate directory",
)
@click.option(
    "--if-source",
    help="expected authored-input digest, required with --from-directory",
)
@click.option(
    "--completes",
    multiple=True,
    metavar="WIDGET",
    help="a widget whose open to-dos this version completes (repeatable)",
)
def stamp(
    dir: str,
    text: str,
    completes: tuple[str, ...],
    from_directory: Path | None,
    if_source: str | None,
) -> None:
    """Stamp PAGE/index.html with a changelog.

    Checks the exact source first, then records it as the next public version. Repeat
    --completes for each widget whose open to-dos this version completes, which ends
    them done, citing the version. A to-do otherwise remains open, including when a
    revision removes its widget. --from-directory replaces index.html and the
    complete page/ tree atomically with stamping; --if-source is the authored-input
    digest read through leaf.publishing, refusing a competing edit.
    """
    from leaf.publishing import cmd_stamp

    _print_records(
        cmd_stamp(
            resolve_dir(dir),
            text,
            completes,
            from_directory=from_directory,
            if_source=if_source,
        )
    )


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


@page.command(
    cls=RecordsCommand,
    short_help="Report a state change onto a page widget, as a worker.",
)
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(dir: str, widget: str, verb: str, fields: tuple) -> None:
    """Report a state change onto a page widget, as a worker.

    The verb and its fields are the widget's own agent-written x-state verb —
    `leaf page report <page> t-parser status value=review text="Ready for review"`
    moves a task. The page paints the report live as provisional news; it stands until a
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


@page.command(short_help="Read browser interactions and request diagnostics.")
@click.argument("dir", metavar="PAGE")
@click.option(
    "--session", help="Select one browser tab; excludes unassociated server requests."
)
@click.option(
    "--since",
    metavar="ISO_TIME",
    help="Include observations at or after this time, with timezone offset.",
)
@click.option(
    "--until",
    metavar="ISO_TIME",
    help="Exclude observations at or after this time, with timezone offset.",
)
@click.option(
    "--type",
    "types",
    multiple=True,
    help="Select an observation type; repeat to select several.",
)
@json_option("Print complete reconstructed records as JSON lines.")
def interactions(
    dir: str,
    session: str | None,
    since: str | None,
    until: str | None,
    types: tuple[str, ...],
    as_json: bool,
) -> None:
    """Read diagnostics chronologically, without acknowledging user input.

    Times print in the local timezone. Retries are deduplicated, split records
    are reconstructed, and gaps remain visible even with a type filter.
    """
    from leaf.interaction_log import (
        format_interaction,
        interaction_time,
        read_interactions,
    )

    try:
        start = interaction_time(since) if since else None
        stop = interaction_time(until) if until else None
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if start is not None and stop is not None and start >= stop:
        raise click.ClickException("--since must precede --until")
    rows = read_interactions(
        resolve_dir(dir), session=session, since=start, until=stop, types=types
    )
    for row in rows:
        click.echo(
            json.dumps(row, ensure_ascii=False) if as_json else format_interaction(row)
        )


@page.command(short_help="Take a page this session did not serve.")
@click.argument("dir", metavar="PAGE")
def claim(dir: str) -> None:
    """Make PAGE this session's, for a harness whose own hook watches between
    turns. A watch another session runs stops watching it."""
    from leaf.service import claim_page

    if not claim_page(resolve_dir(dir)):
        raise click.ClickException("only an agent harness session can claim a page")


@page.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> None:
    """Print the page's exchange as Markdown."""
    from leaf.transcript import cmd_transcript

    cmd_transcript(resolve_dir(dir))


@cli.group(short_help="Read a delivery by its id, and confirm you received it.")
def delivery() -> None:
    """Read a delivery that Leaf names by its id instead of printing it, as a
    `<leaf-delivery>` pointer, and confirm you received it.

    Run `leaf delivery read <id>`, and each part's `next` command until none is
    left, then follow the `acknowledge` instruction the last part carries.
    Confirming a delivery marks its updates Picked up for the user."""


@delivery.command("read", short_help="Print a delivery, one part at a time.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
@click.option(
    "--part",
    type=click.IntRange(min=1),
    default=1,
    help="Read this numbered part of a large delivery.",
)
def delivery_read(delivery_id: str, part: int) -> None:
    """Print DELIVERY_ID, or one part of a large one, without confirming it.

    Each part except the last gives the command for the next part in `next`; the
    last gives in `acknowledge` how to confirm the delivery."""
    from leaf.delivery import cmd_delivery_read

    cmd_delivery_read(delivery_id, part=part)


@delivery.command("ack", short_help="Confirm you have read a whole delivery.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
def delivery_ack(delivery_id: str) -> None:
    """Confirm that every part of DELIVERY_ID is in your context, so its updates
    read Picked up. Reread any part whose output is missing first."""
    from leaf.delivery import cmd_delivery_ack

    cmd_delivery_ack(delivery_id)


@cli.group(
    cls=RecordsGroup, short_help="Open, answer, edit, summarize, or resolve a thread."
)
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


@cli.group(short_help="Bind existing local files for editing on a page.")
def file() -> None:
    """Grant a page access to an explicitly chosen local text file."""


@file.command("bind", short_help="Grant a page read/write access to one file.")
@click.argument("dir", metavar="PAGE")
@click.argument("binding", metavar="ID")
@click.argument("path", type=click.Path(path_type=Path), metavar="PATH")
def file_bind(dir: str, binding: str, path: Path) -> None:
    """Use ID in <lf-file-editor binding=\"ID\"> to edit PATH."""
    from leaf.file_bindings import bind_file

    snapshot = bind_file(resolve_dir(dir), binding, path)
    click.echo(
        f"Bound {binding} to {path.expanduser().resolve()} ({snapshot['bytes']} bytes)."
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

    try:
        value = json.loads(input_file.read())
    except json.JSONDecodeError as error:
        raise click.ClickException(
            f"invalid JSON ({error.msg}, line {error.lineno})"
        ) from error
    cmd_data_set(resolve_dir(dir), source, value)


@data.command("clear", short_help="Remove one source's current value.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
def data_clear(dir: str, source: str) -> None:
    """Remove SOURCE's current value; its next write uses the current binding."""
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
            "--persistent",
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
def start(dir: str, host: str | None, persistent: bool) -> None:
    """Start a page's server and print its URL.

    Returns once the server and this harness's watcher are ready; the server
    itself keeps running in a session of its own. `leaf server stop` takes one
    down, and a session server goes down with the session that claimed it
    besides. A page already served reconnects delivery and prints that server's
    URL. `--persistent` claims no page and prepares no agent delivery.
    """
    from leaf.hosting import claim_and_start

    with claim_and_start(resolve_dir(dir), host, persistent) as started:
        pass
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
def run(dir: str, host: str | None, persistent: bool, temporary: bool) -> None:
    """Serve a page in the foreground, printing its URL and running until stopped.

    Run this in a terminal of your own to hold a page up where you can watch it.
    Browser harnesses use `--temporary`; a user page in an agent session uses
    `server start`. A page already served prints that server's URL and exits.
    """
    from leaf.harness import session_harness
    from leaf.hosting import cmd_serve, cmd_serve_temporary
    from leaf.leases import release_on_termination

    # As for `_serve`: a SIGTERM or a closed terminal's SIGHUP unwinds.
    release_on_termination()
    page_dir = resolve_dir(dir)
    if temporary:
        if persistent:
            raise click.UsageError("choose --temporary or --persistent")
        if host:
            raise click.UsageError("--temporary is loopback-only; omit --host")
        cmd_serve_temporary(page_dir)
        return
    cmd_serve(page_dir, host, persistent, harness=session_harness(), acquire=True)


@server.command("_serve", hidden=True)
@click.argument("dir", metavar="PAGE")
@serve_flags
@click.option("--revive", is_flag=True, hidden=True)
@click.option("--acquire", is_flag=True, hidden=True)
@click.option("--claim", hidden=True)
@click.option("--harness", required=True, hidden=True)
@click.option("--handshake", type=int, required=True, hidden=True)
def _serve(
    dir: str,
    host: str | None,
    persistent: bool,
    revive: bool,
    acquire: bool,
    claim: str | None,
    harness: str,
    handshake: int,
) -> None:
    """Private child process spawned by server start and Watch revival."""
    from leaf.detached import Handshake
    from leaf.harness import harness_from_argument
    from leaf.hosting import cmd_serve
    from leaf.leases import release_on_termination

    # Uvicorn answers SIGTERM by stopping, then raises it again under the handler
    # it found, so this exit unwinds and runs the exit handlers, which stop a
    # title request's App Server (`codex.private_app_server`).
    release_on_termination()
    with Handshake(handshake) as answer:
        cmd_serve(
            resolve_dir(dir),
            host,
            persistent,
            revive,
            harness=harness_from_argument(harness),
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


@cli.command(short_help="Say the page waits on its user, or is done.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["waiting", "idle"]))
@click.argument("detail", required=False, default="")
def status(dir: str, state: str, detail: str) -> None:
    """Say the page waits on its user, or that you are done with it.

    Use waiting with DETAIL naming the answer you want from the user; waiting
    without DETAIL invites text comments. Use idle when you are finished; it is
    refused while the page has updates, workers' reports or page errors nobody has
    picked up, updates you owe an answer, or to-dos of yours still open. Either one clears every
    `leaf task start` you made, so no update or to-do reads Working; your to-dos
    stay open. Status has no working state: to show what you are working on, run
    `leaf task start`.
    """
    from leaf.activity import unanswered
    from leaf.session import cmd_idle, cmd_waiting

    page_dir = resolve_dir(dir)
    owed = []
    if state == "idle":
        written = cmd_idle(page_dir, detail)
    else:
        written, owed = cmd_waiting(page_dir, detail)
    print(json.dumps(written, ensure_ascii=False))
    if state == "waiting" and owed:
        click.echo(
            f"{unanswered(owed, page_dir)}; the page reads waiting once each has one",
            err=True,
        )


@cli.command(
    short_help="Confirm a delivery, if given, then wait for the next batch.",
    help=(
        "Watch every page this session holds, or observe PAGE without taking "
        "ownership. Claim a foreign page explicitly with `leaf page claim`.\n\n"
        + WAIT_BATCH_OUTPUT_INSTRUCTION
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
    sys.exit(cmd_wait(resolve_dir(dir) if dir else None, ack=ack))


def _title_option(command):
    return click.option(
        "--title",
        help=(
            "name the thread for the panel unless it has a name: a few words, at "
            "most 80 characters"
        ),
    )(command)


@thread.command(
    "open", short_help="Open an agent thread — on a passage, or on the page whole."
)
@click.argument("dir", metavar="PAGE")
@click.option("--quote", help="passage text from the active revision")
@click.option("--section", metavar="ID", help="element ID to anchor or scope --quote")
@click.option("--part", metavar="ID", help="declared visual part within --section")
@click.option("--text", help="comment text (default: stdin)")
@click.option("--markup", help="HTML fragment after the text, validated here")
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
    accepted = cmd_comment(page_dir, quote, section, part, text, markup, title=title)
    _print_records(accepted)


def _reply_options(command):
    """The one complete author interface for addressed and proactive replies."""
    for option in (
        click.option("--quote", help="new passage text to move this thread onto"),
        click.option(
            "--section", metavar="ID", help="new element ID, or scope for --quote"
        ),
        click.option(
            "--part", metavar="ID", help="new declared visual part within --section"
        ),
        click.option("--detach", is_flag=True, help="remove the thread's page target"),
        click.option("--text", help="reply text (default: stdin)"),
        click.option(
            "--markup", default="", help="frozen HTML fragment after the text"
        ),
        click.option(
            "--ask",
            is_flag=True,
            help="the reply asks the user something, which waits on them as an ask",
        ),
        click.option(
            "--todo",
            metavar="TITLE",
            help="the reply promises work it doesn't deliver; opens that to-do on the "
            "thread, ended by `leaf task end` with the reply's id",
        ),
        click.option(
            "--ephemeral", is_flag=True, help="one-line progress, without answering"
        ),
        _title_option,
    ):
        command = option(command)
    return command


@cli.group(
    cls=RecordsGroup,
    short_help="Reply to an update by the reference its delivery gave.",
)
def response() -> None:
    """Reply to a user update with the reference its delivery printed as
    `answer.ref`."""


@response.command("reply", short_help="Reply to the update a reference names.")
@click.argument("reference", metavar="REFERENCE")
@click.option(
    "--attempt",
    help="retry key: a rerun with the same key posts nothing new (default: the "
    "reference, except with --ephemeral)",
)
@click.option(
    "--failure",
    help="failure code when no answer is coming; refused while your turn's final "
    "message is to be the reply",
)
@click.option(
    "--done", is_flag=True, help="the reply delivers what the message asked for"
)
@_reply_options
def response_reply(
    reference: str, attempt: str | None, failure: str | None, done: bool, **options
) -> None:
    """Reply to the update REFERENCE names: the `answer.ref` its delivery printed.

    An answer says what it leaves the thread with: --done when it delivers what the
    message asked for, --ask when it asks the user something back, or --todo
    TITLE when it promises work it doesn't deliver, which stays on you as a to-do.
    Progress (--ephemeral) and failure receipts (--failure) take none of them.

    The same command sets text, frozen HTML, the thread's title and a new anchor.
    It validates and activates saved page edits, then posts the reply at once. Once
    an answer posts, your turn's final message is not posted as a second reply;
    progress (--ephemeral) does not stop that. Rerunning a reply
    that posted prints the earlier reply instead of posting again; give a retried
    --ephemeral progress line an --attempt so it posts once.
    """
    from leaf.thread import post_response

    declared = [
        flag
        for flag, given in (
            ("--done", done),
            ("--ask", options["ask"]),
            ("--todo", options["todo"] is not None),
        )
        if given
    ]
    if len(declared) > 1:
        raise click.UsageError(f"{' and '.join(declared)} cannot be used together")
    answers = not options["ephemeral"] and failure is None
    if declared and not answers:
        raise click.UsageError(
            f"{declared[0]} declares what an answer leaves; progress and failure "
            "receipts answer nothing"
        )
    if not declared and answers:
        raise click.UsageError(
            "say what the answer leaves: --done when it delivers what was asked, "
            "--ask when it asks the user something back, or --todo TITLE when "
            "it promises work it doesn't deliver"
        )
    if attempt is not None:
        options["attempt"] = attempt
    _print_records(post_response(reference, failure=failure, **options))


@thread.command("reply", short_help="Add an agent-initiated reply to a thread.")
@click.argument("dir", metavar="PAGE")
@click.argument("thread", metavar="THREAD")
@_reply_options
def thread_reply(dir: str, thread: str, **options) -> None:
    """Post a new agent message to THREAD (--text or stdin).

    A message is refused while the thread owes a response; answer it with
    `leaf response reply <answer.ref>`. --ephemeral posts progress.
    Saved page edits are validated and activated before posting.
    """
    from leaf.thread import post_reply

    _print_records(
        post_reply(resolve_dir(dir), {"to": thread}, validate_source=True, **options)
    )


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
    markup is not editable. Keep a title stable unless the thread's
    subject changes.
    """
    from leaf.thread import cmd_edit

    _print_records(*cmd_edit(resolve_dir(dir), message, text, title=title))


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


@cli.group(
    cls=RecordsGroup, short_help="Open or end to-dos, and start work on your list."
)
def task() -> None:
    """Open and end to-dos, and say which item on your list you are working on.

    Your list, which the user sees as On <your name>, holds each user update you owe
    an answer, named by the update's event id, and each to-do you opened. Before
    working on one, run `leaf task start` with a line saying what you are doing:
    the item reads Working with that line, beside it and in the banner. A to-do
    stays on your list through replies, resolutions, versions and the end of the
    session that opened it, until `leaf task end` or a stamp that `--completes` its
    widget ends it. A to-do you open `--on user` goes on the user's On me list
    instead, until they press its Done or you end it. Every write prints the record
    it appended, one JSON line, as `page events` prints it.
    """


@task.command("open", short_help="Open a to-do, yours or the user's.")
@click.argument("dir", metavar="PAGE")
@click.argument("subject", metavar="SUBJECT")
@click.argument("title", metavar="TITLE")
@click.option(
    "--on",
    "owner",
    type=click.Choice(["agent", "user"]),
    default="agent",
    show_default=True,
    help="Whose list the to-do is on: yours, or the user's On me.",
)
def task_open(dir: str, subject: str, title: str, owner: str) -> None:
    """Open a to-do titled TITLE on SUBJECT: a page widget, which for your own to-do
    must declare x-work or hold an unsettled update; any other element of the page by
    its id, such as a section; or `page` for the page as a whole. With `--on user`
    the to-do is on the user: it ends at their Done, and you can end it too. Its id is
    the printed record's `id`. In a thread, the reply that promises work opens it
    (`--todo`), and one that asks the user is their ask (`--ask`)."""
    from leaf.todos import cmd_open

    _print_records(cmd_open(resolve_dir(dir), subject, title, owner))


@task.command(
    "start", short_help="Start work on an update or to-do, with the banner's line."
)
@click.argument("dir", metavar="PAGE")
@click.argument("item", metavar="ID")
@click.argument("text", metavar="LINE")
def task_start(dir: str, item: str, text: str) -> None:
    """Mark ID Working for this turn, with LINE saying what you are doing.

    ID is the event id of a user update you owe, as its delivery names it, or an
    open to-do's id. LINE names the work and its subject in one sentence; it shows
    beside the update or to-do and in the banner. Your answer to the update, or the
    to-do's end, ends the start. If your turn ends first, the item reads stalled
    until you answer it or start it again."""
    from leaf.todos import cmd_start

    _print_records(cmd_start(resolve_dir(dir), item, text))


@task.command("end", short_help="End a to-do: done, failed, or dropped.")
@click.argument("dir", metavar="PAGE")
@click.argument("task_id", metavar="TODO")
@click.argument("outcome", type=click.Choice(["done", "failed", "dropped"]))
@click.argument("detail", metavar="[DETAIL]", required=False)
def task_end(dir: str, task_id: str, outcome: str, detail: str | None) -> None:
    """End TODO with OUTCOME. DETAIL says where the result is, such as the
    version or reply holding it, or why there is none. TODO may be a to-do on
    either side. A prose ask's id (`reply:<message-id>`) ends that request
    without creating a user answer: `done` records it answered elsewhere, DETAIL
    saying where, and `dropped` records it withdrawn. Widget asks end through
    their declared state or an authored withdrawal."""
    from leaf.todos import cmd_end

    _print_records(cmd_end(resolve_dir(dir), task_id, outcome, detail))
