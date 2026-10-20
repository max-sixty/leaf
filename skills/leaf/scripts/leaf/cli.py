"""Click declarations and production command wiring.

Every command speaks JSON, since agents are its only readers: its result on stdout,
one JSON value (a record per line for a write), and anything said beside it on
stderr, one JSON object per line. That is a note, a finding (`findings.note`), or a
refusal ending the command, `{"error", "findings"}` (`LeafGroup`). So a reader that
merges the streams still parses every line, one that pipes stdout alone still sees
what was said beside it, and a refusal never reads as a result. `--help`, `--version`
and `--root` print text, as `page transcript` prints Markdown and `package run` prints
what its script does.

A command returns its result and never prints it: `LeafGroup.main` prints what it
returns, so every result has one presentation and a `cmd_*` function answers its
caller directly. Only output that cannot wait for the command to end prints where it
arises: a stream such as `page events`, the URL a foreground server prints before
serving, a hook's answer, and a wait's delivery, printed while the wait still holds
its watch.
"""

import json
import shlex
import sys
from pathlib import Path
from typing import NamedTuple, TextIO

import click

from leaf.schema import SKILL_ROOT, WAIT_BATCH_OUTPUT_INSTRUCTION
from leaf.state import EVENTS_FILE


class Reported(NamedTuple):
    """A result that also sets the exit status, as a check's report does."""

    result: dict
    status: int


def resolve_dir(dir_arg: str, must_exist: bool = True, *, renew: bool = True) -> Path:
    """The page a command names. An initialized one this Leaf cannot serve, as a
    plugin update that bumps the page protocol leaves it, is re-vendored first for
    the session running the command (`vendoring.renew_layer`), whose finding on what
    still holds it back is noted; `renew` is off for a command that would undo the
    re-vendor's restart."""
    from leaf.locations import canonical_path

    page_dir = canonical_path(Path(dir_arg).expanduser())
    if not must_exist:
        return page_dir
    if page_dir.is_file():
        raise click.ClickException(
            f"{page_dir} is a file; a page command takes the page's directory"
        )
    if not (page_dir / EVENTS_FILE).is_file():
        raise click.ClickException(
            f"{page_dir} is not an initialized page; "
            f"run `leaf page init {shlex.quote(str(page_dir))}`"
        )
    if not renew:
        return page_dir
    from leaf.findings import note
    from leaf.harness import session_harness
    from leaf.vendoring import renew_layer

    if unready := renew_layer(page_dir, session_harness()):
        note(unready)
    return page_dir


def body_options(subject: str):
    """Declare the options a command takes its body by, such as a reply's text or a
    plan's JSON: `--text` inline, or `--file` naming a file, `-` for stdin. With
    neither, the body is what a pipe or heredoc gives stdin (`read_body`)."""

    def decorate(command):
        command = click.option(
            "--file",
            "body_file",
            type=click.File("r", encoding="utf-8"),
            metavar="PATH",
            help=f"read {subject} from PATH, - for stdin; with neither option, "
            "from piped stdin",
        )(command)
        return click.option("--text", help=subject)(command)

    return decorate


def read_body(text: str | None, body_file: TextIO | None) -> str | None:
    """The body `body_options` took: `--text`, the file `--file` named, or what was
    piped to stdin (`piped_input`); None when none of them gave one."""
    if text is not None and body_file is not None:
        raise click.UsageError("give the body as --text or --file, not both")
    if body_file is not None:
        return body_file.read()
    if text is not None:
        return text
    from leaf.piped_input import piped_stdin

    return piped_stdin() or None


def _print_result(result) -> None:
    """Print what a command returned: text as it is, a dict as one JSON line, and
    each item of a list, such as the records a write appended, as a line of its own,
    the way `page events` prints a record."""
    from leaf.event_log import jsonl_line

    if result is None:
        return
    if isinstance(result, str):
        click.echo(result)
        return
    for value in result if isinstance(result, list) else [result]:
        click.echo(jsonl_line(value))


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


class _Refusal(click.ClickException):
    """A domain refusal on its way out of `LeafGroup.main`, carrying its JSON."""

    def __init__(self, said: dict):
        super().__init__(said["error"])
        self.said = said


class LeafGroup(click.Group):
    """Print what a command returns (`_print_result`) and exit 0, or exit with the
    status it returns as an integer or as a `Reported` beside its result. End a
    command that cannot do what it was asked with one JSON object on stderr,
    `{"error", "findings"}`, and its exit status.

    A domain refusal (`refusals.Refused`) gives `Refused.json`, whose `findings` carry
    each refusal's code and fields; Click's own refusals, a usage error among them,
    give their message, with the command's usage line as `usage`. An agent's sandbox
    refusing the command a file or socket, directly or as the cause of a refusal,
    adds what the agent does about it (`machine.sandbox_refusal`). Exit statuses
    (including a package script's) keep their meaning and output, a bare group
    prints its help, and any other exception surfaces with its traceback.
    """

    def invoke(self, ctx: click.Context):
        from leaf.machine import sandbox_refusal
        from leaf.refusals import Refused

        try:
            return super().invoke(ctx)
        except Refused as error:
            reason = sandbox_refusal(error) or str(error)
            raise _Refusal(error.json() | {"error": reason}) from error
        except OSError as error:
            if (reason := sandbox_refusal(error)) is None:
                raise
            raise click.ClickException(reason) from error

    def main(
        self,
        args=None,
        prog_name=None,
        complete_var=None,
        standalone_mode=True,
        **extra,
    ):
        if not standalone_mode:
            return super().main(args, prog_name, complete_var, False, **extra)
        try:
            result = super().main(args, prog_name, complete_var, False, **extra)
        except click.exceptions.NoArgsIsHelpError as error:
            error.show()
            sys.exit(error.exit_code)
        except click.ClickException as error:
            said = getattr(error, "said", None) or {
                "error": error.format_message(),
                "findings": [],
            }
            if isinstance(error, click.UsageError) and error.ctx is not None:
                said["usage"] = error.ctx.get_usage().removeprefix("Usage: ")
            print(json.dumps(said, ensure_ascii=False), file=sys.stderr)
            sys.exit(error.exit_code)
        except click.Abort:
            print(json.dumps({"error": "interrupted", "findings": []}), file=sys.stderr)
            sys.exit(1)
        status = 0
        if isinstance(result, Reported):
            result, status = result
        elif isinstance(result, int):
            result, status = None, result
        _print_result(result)
        sys.exit(status)


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
def codex_launch(codex_path: str | None) -> int:
    """Run Codex with a private local App Server for Leaf delivery and activity.

    This integration is experimental.
    """
    from leaf.codex_adapter import cmd_codex_launch

    return cmd_codex_launch(codex_path)


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
) -> dict:
    """Start one task-wide delivery adapter and claim PAGE for it."""
    from leaf.codex_adapter import cmd_codex_start

    return cmd_codex_start(resolve_dir(dir), codex_path, app_server)


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
    # Exiting inside the handshake tells a parent still waiting on it the status.
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
def init(dir: str, selected: tuple[str, ...], no_packages: bool, dry_run: bool) -> dict:
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
    return cmd_init(resolve_dir(dir, must_exist=False), selections, dry_run=dry_run)


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
def package_init(package_path: Path, widget: str | None) -> dict:
    """Create the package layout without replacing existing files.

    With --widget, add one checked upgraded content widget starter.
    """
    from leaf.packages import cmd_package_init

    return cmd_package_init(package_path, widget)


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
def package_check(package_path: Path, render: bool) -> Reported:
    """Check the package as one composed unit.

    --render also draws each worked example the package's own widgets declare in
    the host's browser, the one `page check --render` finds, and reports what the
    widget quality checks find there. A finding is advice for the widgets' author
    and leaves the exit status alone. Prints one object, in the shape `page check`
    prints.
    """
    from leaf.packages import cmd_package_check

    report = cmd_package_check(package_path, render)
    return Reported(report, report["status"])


@package.command("install", short_help="Install a package for selection by name.")
@click.argument(
    "package_path",
    type=click.Path(path_type=Path, file_okay=False),
    metavar="SOURCE",
)
def package_install(package_path: Path) -> dict:
    """Check SOURCE and copy it into this user's package store.

    `page init --package NAME` then selects it by its directory name, on the
    same terms as a package Leaf ships.
    """
    from leaf.packages import cmd_package_install

    return cmd_package_install(package_path)


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
def check(dir: str, render: bool) -> Reported:
    """Check PAGE/index.html.

    Runs deterministic markup checks. --render also checks the drawn page in the
    host's browser: whichever executable LEAF_BROWSER_EXECUTABLE, CHROME_PATH, or
    CHROME_BIN names, else the installed Chrome, else the first browser on PATH.
    A host with no browser is told why in place of each browser check. Prints one
    object: the exit status, every finding with its code, element, measured values,
    severity and words, and what each browser check ran in.
    """
    from leaf.validation.command import cmd_check

    report = cmd_check(resolve_dir(dir), render)
    return Reported(report, report["status"])


@page.command()
@click.argument("dir", metavar="PAGE")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    metavar="FILE...",
)
def media(dir: str, files) -> list[dict]:
    """Add images, video, or audio and print their page paths.

    Copies each file into the page under a content-addressed name and prints
    one JSON line per file: its page `path` and its `source` file.
    """
    from leaf.media import cmd_media

    return [
        {"path": url, "source": str(src)}
        for src, url in cmd_media(resolve_dir(dir), [Path(f) for f in files])
    ]


@page.command(short_help="Read selected-component instructions by audience as JSON.")
@click.argument("dir", metavar="PAGE")
@click.option("--use", "entries", multiple=True, metavar="ENTRY")
@click.option("--contract", "contracts", multiple=True, metavar="ID")
def instructions(
    dir: str, entries: tuple[str, ...], contracts: tuple[str, ...]
) -> dict[str, str]:
    """Print a JSON object mapping each audience, such as `author`, to its instructions.

    Alone, it prints the packages' shared instructions. Before writing markup, name
    each element or idiom you will use with --use, and each data contract with
    --contract; the output then adds their instructions, and those of the entries
    their examples use.
    """
    from leaf.page import page_instructions

    return page_instructions(resolve_dir(dir), entries=entries, contracts=contracts)


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
def state(dir: str, target: str | None, after: int | None, limit: int | None) -> dict:
    """Print the page as it is now, as one JSON object: the active revision's
    file, the current widget actions and workers' reports, the user's On me list and
    yours, thread summaries, versions, presence, and bound data. Read the active
    revision's HTML beside it for the document.

    ID narrows the output to what it names. A message, or a widget frozen into
    one, names its thread: the output is that thread with a page of its messages,
    their frozen markup, and the state of its widgets, paged by --after and
    --limit. A widget on the page names itself: its element, its current actions
    and reports, its obligations and to-dos, and its workflows."""
    from leaf.agent_state import cmd_page_state

    if target is None and (after is not None or limit is not None):
        raise click.UsageError("--after and --limit page a thread; name one as ID")
    return cmd_page_state(resolve_dir(dir), target, after=after, limit=limit)


@page.command(short_help="Stamp the current source as the next version.")
@click.argument("dir", metavar="PAGE")
@body_options("the changelog")
@click.option(
    "--from-directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="replace index.html and page/ together from this candidate directory",
)
@click.option(
    "--if-source",
    help="the page's current index.html and page/ digest "
    "(leaf.publishing.authored_digest), required with --from-directory",
)
@click.option(
    "--completes",
    multiple=True,
    metavar="WIDGET",
    help="a widget whose open to-dos this version completes (repeatable)",
)
def stamp(
    dir: str,
    text: str | None,
    body_file,
    completes: tuple[str, ...],
    from_directory: Path | None,
    if_source: str | None,
) -> dict:
    """Stamp PAGE/index.html with a changelog.

    Checks the source first, then records it as the next public version. Repeat
    --completes for each widget whose open to-dos this version completes; it ends
    them done, citing the version. Other to-dos stay open, even when the version
    removes their widget.

    --from-directory replaces index.html and the whole page/ tree and stamps them in
    one step. Pass --if-source with the digest of the files you started from; if
    they have changed since, the stamp is refused and the page is left as it was.
    """
    from leaf.publishing import cmd_stamp

    return cmd_stamp(
        resolve_dir(dir),
        read_body(text, body_file),
        completes,
        from_directory=from_directory,
        if_source=if_source,
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
def export(dir: str, out: Path, version: int) -> dict:
    """Export a stamped version to one HTML file that opens offline.

    The file runs the page's own runtime against its captured state, with no Leaf
    server or host behind it.
    """
    from leaf.exporting import cmd_export

    return cmd_export(resolve_dir(dir), out, version)


@page.command(short_help="Picture a drawing comment as the user saw it.")
@click.argument("dir", metavar="PAGE")
@click.argument("message", metavar="ID")
def picture(dir: str, message: str) -> dict:
    """Draw comment ID's drawing over the page as the user saw it, and print the
    PNG's path as `file`.

    Opens the comment's revision in the host's browser, with the log applied
    through the comment, at the window size and color scheme the drawing was
    made in, and crops to the ink and the page around it. Bound data is read as
    it stands now, and the host's fonts may differ from the user's.
    """
    from leaf.render_gate.picture import cmd_picture

    return cmd_picture(resolve_dir(dir), message)


@page.command(
    short_help="Report a state change onto a page widget, as a worker.",
)
@click.argument("dir", metavar="PAGE")
@click.argument("widget", metavar="WIDGET")
@click.argument("verb", metavar="VERB")
@click.argument("fields", metavar="[NAME=VALUE]...", nargs=-1)
def report(dir: str, widget: str, verb: str, fields: tuple) -> dict:
    """Report a state change onto a page widget, as a worker.

    VERB is one of the widget's agent-written x-state verbs, and each NAME=VALUE one of
    its fields: `leaf page report <page> t-parser status value=review text="Ready for
    review"` moves a task. The page shows the report at once, marked provisional,
    until a stamped version writes it into the markup or overrules it. The page's
    watcher wakes so the agent can do that.
    """
    from leaf.thread import cmd_report

    return cmd_report(resolve_dir(dir), widget, verb, fields)


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
def interactions(
    dir: str,
    session: str | None,
    since: str | None,
    until: str | None,
    types: tuple[str, ...],
) -> list[dict]:
    """Read diagnostics chronologically, one JSON record per line, without
    acknowledging user input.

    Retries are deduplicated and sequence gaps remain visible even with a type
    filter. Stored timestamps use the host clock.
    """
    from leaf.interaction_log import interaction_time, read_interactions

    try:
        start = interaction_time(since) if since else None
        stop = interaction_time(until) if until else None
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if start is not None and stop is not None and start >= stop:
        raise click.ClickException("--since must precede --until")
    return read_interactions(
        resolve_dir(dir), session=session, since=start, until=stop, types=types
    )


@page.command(short_help="Take a page this session did not serve.")
@click.argument("dir", metavar="PAGE")
def claim(dir: str) -> None:
    """Make PAGE this session's, so the user's updates on it come to this session.
    A watch another session runs on PAGE stops watching it."""
    from leaf.service import claim_page

    if not claim_page(resolve_dir(dir)):
        raise click.ClickException("only an agent harness session can claim a page")


@page.command(short_help="Print the page's exchange as Markdown.")
@click.argument("dir", metavar="PAGE")
def transcript(dir: str) -> str:
    """Print the page's exchange as Markdown."""
    from leaf.transcript import cmd_transcript

    return cmd_transcript(resolve_dir(dir))


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
def delivery_read(delivery_id: str, part: int) -> dict:
    """Print DELIVERY_ID, or one part of a large one, without confirming it.

    Each part except the last gives the command for the next part in `next`; the
    last gives in `acknowledge` how to confirm the delivery."""
    from leaf.delivery import cmd_delivery_read

    return cmd_delivery_read(delivery_id, part=part)


@delivery.command("ack", short_help="Confirm you have read a whole delivery.")
@click.argument("delivery_id", metavar="DELIVERY_ID")
def delivery_ack(delivery_id: str) -> None:
    """Confirm that every part of DELIVERY_ID is in your context, so its updates
    read Picked up. Reread any part whose output is missing first."""
    from leaf.delivery import cmd_delivery_ack

    cmd_delivery_ack(delivery_id)


@cli.group(short_help="Open, answer, edit, summarize, or resolve a thread.")
def thread() -> None:
    """Open and answer threads as the agent, and maintain them.

    Every write prints the records it appended, one JSON line each, as `page
    events` prints them. `page state PAGE ID` reads one thread."""


@thread.command("summarize", short_help="Summarize a contiguous message range.")
@click.argument("dir", metavar="PAGE")
@click.option("--from", "from_message", required=True, metavar="MESSAGE")
@click.option("--through", "through_message", required=True, metavar="MESSAGE")
@body_options("the summary's Markdown")
@click.option("--label", help="disclosure label (default: Earlier discussion)")
def thread_summarize(
    dir: str,
    from_message: str,
    through_message: str,
    text: str | None,
    body_file,
    label: str | None,
) -> dict:
    """Replace --from through --through in the panel with a Markdown summary.

    Both name messages in one thread, which is the thread summarized. An empty
    summary, such as `--text ''`, folds them without prose. The original messages
    remain in the append-only transcript and can always be revealed. A later
    overlapping summary replaces this one.
    """
    from leaf.thread import cmd_summarize

    return cmd_summarize(
        resolve_dir(dir),
        from_message,
        through_message,
        read_body(text, body_file),
        label=label,
    )


@cli.group(short_help="Bind existing local files for editing on a page.")
def file() -> None:
    """Grant a page access to an explicitly chosen local text file."""


@file.command("bind", short_help="Grant a page read/write access to one file.")
@click.argument("dir", metavar="PAGE")
@click.argument("binding", metavar="ID")
@click.argument("path", type=click.Path(path_type=Path), metavar="PATH")
def file_bind(dir: str, binding: str, path: Path) -> dict:
    """Use ID in <lf-file-editor binding=\"ID\"> to edit PATH. Prints the binding,
    the file it grants, and its size in bytes."""
    from leaf.file_bindings import bind_file, bound_paths

    page_dir = resolve_dir(dir)
    snapshot = bind_file(page_dir, binding, path)
    return {
        "binding": binding,
        "path": str(bound_paths(page_dir)[binding]),
        "bytes": snapshot["bytes"],
    }


def json_body(text: str | None, body_file: TextIO | None):
    """The JSON value a command's body holds (`read_body`)."""
    text = read_body(text, body_file)
    if text is None or not text.strip():
        from leaf.piped_input import NO_BODY

        raise click.ClickException(f"no JSON given ({NO_BODY})")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise click.ClickException(
            f"invalid JSON ({error.msg}, line {error.lineno})"
        ) from error


@cli.group(short_help="Set or clear page-bound external data.")
def data() -> None:
    """Manage each bound source's current value, one JSON file per source."""


@data.command("set", short_help="Replace one bound source value.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
@body_options("the JSON value")
def data_set(dir: str, source: str, text: str | None, body_file) -> dict:
    """Validate and replace SOURCE with one complete JSON value."""
    from leaf.data import cmd_data_set

    value = json_body(text, body_file)
    return cmd_data_set(resolve_dir(dir), source, value)


@data.command("clear", short_help="Remove one source's current value.")
@click.argument("dir", metavar="PAGE")
@click.argument("source", metavar="SOURCE")
def data_clear(dir: str, source: str) -> dict:
    """Remove SOURCE's current value; its next write uses the current binding."""
    from leaf.data import cmd_data_clear

    return cmd_data_clear(resolve_dir(dir), source)


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
def start(dir: str, host: str | None, persistent: bool) -> dict:
    """Start a page's server and print its URL.

    Returns once the server and this harness's watcher are ready; the server
    itself keeps running in a session of its own. `leaf server stop` takes one
    down, and a session server goes down with the session that claimed it
    besides. A page already served reconnects delivery and prints that server's
    URL. `--persistent` claims no page and prepares no agent delivery. Beside the
    URL it prints the server's lifetime, the page's layer and the Leaf serving it.
    """
    from leaf.hosting import claim_and_start, started_server

    page_dir = resolve_dir(dir)
    with claim_and_start(page_dir, host, persistent) as started:
        pass
    return started_server(page_dir, started.url)


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
            # A re-vendor here would restart the server this process is becoming.
            resolve_dir(dir, renew=False),
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
def stop(dir: str) -> dict:
    """Stop a page's server."""
    from leaf.hosting import cmd_stop

    return {"stopped": cmd_stop(resolve_dir(dir, renew=False))}


@cli.command(short_help="Say the page waits on its user, or is done.")
@click.argument("dir", metavar="PAGE")
@click.argument("state", type=click.Choice(["waiting", "idle"]))
@click.argument("detail", required=False, default="")
def status(dir: str, state: str, detail: str) -> dict:
    """Say the page waits on its user, or that you are done with it.

    Use waiting with DETAIL naming the answer you want from the user; waiting
    without DETAIL invites text comments. Use idle when you are finished; it is
    refused while the page has updates, workers' reports or page errors nobody has
    picked up, updates you owe an answer, or to-dos of yours still open. Either one clears every
    `leaf task start` you made, so no update or to-do reads Working; your to-dos
    stay open. Status has no working state: to show what you are working on, run
    `leaf task start`.
    """
    from leaf.activity import answer_command
    from leaf.findings import Finding, note
    from leaf.session import cmd_idle, cmd_waiting

    page_dir = resolve_dir(dir)
    owed = []
    if state == "idle":
        written = cmd_idle(page_dir, detail)
    else:
        written, owed = cmd_waiting(page_dir, detail)
    if owed:
        answers = [answer_command(item["answer"], page_dir) for item in owed]
        note(Finding("waiting-owes", values={"answers": answers}, severity="advice"))
    return written


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
def wait(dir: str | None, ack: str | None) -> int:
    """Confirm a delivery, if given, then wait for the next batch."""
    from leaf.leases import release_on_termination
    from leaf.session import cmd_wait

    if dir is not None and ack is not None:
        raise click.UsageError("PAGE and --ack cannot be used together")
    release_on_termination()
    return cmd_wait(resolve_dir(dir) if dir else None, ack=ack)


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
@body_options("the comment's text")
@click.option("--markup", help="HTML fragment after the text, validated here")
@_title_option
def thread_open(
    dir: str,
    quote: str,
    section: str,
    part: str,
    text: str | None,
    body_file,
    markup: str,
    title: str | None,
) -> dict:
    """Open a thread as the agent: anchored where --quote or
    --section points at a passage, general where neither does — a question about
    the work as a whole.

    The user answers it in the browser; a question in an `<lf-ask>` in --markup
    waits on them until they do. Refuses a quote the active revision does not
    hold, or holds more than once. The comment's id is the thread's.
    """
    from leaf.thread import cmd_comment

    return cmd_comment(
        resolve_dir(dir),
        quote,
        section,
        part,
        read_body(text, body_file),
        markup,
        title=title,
    )


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
        body_options("the reply's text"),
        click.option(
            "--markup", default="", help="frozen HTML fragment after the text"
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


@cli.group(short_help="Reply to an update by the reference its delivery gave.")
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
) -> dict | None:
    """Reply to the update REFERENCE names: the `answer.ref` its delivery printed.

    Mark every answer with --done (it delivers what the message asked for) or
    --todo TITLE (it promises work it doesn't deliver, which stays on you as a
    to-do), or ask the user something back with an `<lf-ask>` in its --markup,
    which waits on them until their next message in the thread. A progress line
    (--ephemeral) or a failure (--failure) takes none of them.

    The reply can also set frozen HTML, the thread's title and a new anchor. It
    publishes your saved page edits with it, checking them as `page check` does
    without a browser: an error refuses the reply, and the first reply on a revision
    notes the advice `page check` gives on its source. Nothing runs in a browser,
    where `page check` runs a page's scripts and data widgets; one that fails for
    the user arrives as an `error` event. After an answer posts,
    your turn's final message is not posted as a second reply; an --ephemeral line
    does not change that. Rerunning a reply that already posted prints the earlier
    one; give a retried --ephemeral line an --attempt so it posts once.
    """
    from leaf.thread import post_response

    declared = [
        flag
        for flag, given in (
            ("--done", done),
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
    if not declared and answers and not options["markup"]:
        raise click.UsageError(
            "say what the answer leaves: --done when it delivers what was asked, "
            "--todo TITLE when it promises work it doesn't deliver, or a question "
            "for the user as an <lf-ask> in --markup"
        )
    options["asks_back"] = not declared and answers
    if attempt is not None:
        options["attempt"] = attempt
    text = read_body(options.pop("text"), options.pop("body_file"))
    return post_response(reference, text, failure=failure, **options)


@thread.command("reply", short_help="Add an agent-initiated reply to a thread.")
@click.argument("dir", metavar="PAGE")
@click.argument("thread", metavar="THREAD")
@_reply_options
def thread_reply(dir: str, thread: str, **options) -> dict | None:
    """Post a new agent message to THREAD.

    A message is refused while the thread owes a response; answer it with
    `leaf response reply <answer.ref>`. --ephemeral posts progress. Saved page
    edits are checked and published as `leaf response reply` says.
    """
    from leaf.thread import post_reply

    text = read_body(options.pop("text"), options.pop("body_file"))
    return post_reply(
        resolve_dir(dir), {"parent": thread}, text, validate_source=True, **options
    )


@thread.command("edit", short_help="Edit a message's text, or its thread's title.")
@click.argument("dir", metavar="PAGE")
@click.argument("message", metavar="MESSAGE")
@body_options("the replacement text")
@click.option(
    "--title",
    help="rename MESSAGE's thread for the panel: a few words, at most 80 characters",
)
def thread_edit(
    dir: str, message: str, text: str | None, body_file, title: str | None
) -> list[dict]:
    """Replace the visible text of MESSAGE, an agent-authored comment or reply,
    or with --title rename the thread MESSAGE is in, whoever opened it. --title
    alone leaves the text as it is.

    The original and every revision remain in the append-only event log. Frozen
    markup is not editable. Keep a title stable unless the thread's
    subject changes.
    """
    from leaf.thread import cmd_edit

    renames_only = title is not None and text is None and body_file is None
    body = None if renames_only else read_body(text, body_file)
    return cmd_edit(resolve_dir(dir), message, body, title=title)


@thread.command("resolve", short_help="Close a thread as the agent.")
@click.argument("dir", metavar="PAGE")
@click.argument("thread", metavar="THREAD")
def thread_resolve(dir: str, thread: str) -> dict:
    """Close THREAD, by any message in it, as the agent.

    The user ordinarily closes a thread; the Leaf skill's
    references/threads.md says when the agent does. Refuses a thread
    that asked for a version until a stamped version answers it. The panel names
    who resolved it.
    """
    from leaf.thread import cmd_resolve

    return cmd_resolve(resolve_dir(dir), thread)


@cli.group(short_help="Open or end to-dos, start work on your list, and plan.")
def task() -> None:
    """Open and end to-dos, say which item on your list you are working on, and
    lay out your plan.

    Your list, which the user sees as On <your name>, holds each user update you owe
    an answer, named by the update's event id, and each to-do you opened. Before
    working on one, run `leaf task start` with a line saying what you are doing:
    the item reads Working with that line, beside it and in Leaf's panel. A to-do
    stays on your list through replies, resolutions, versions and the end of the
    session that opened it, until `leaf task end` or a stamp that `--completes` its
    widget ends it. A to-do you open `--on user` goes on the user's On me list
    instead, until they press its Done or you end it. `leaf task plan` arranges
    to-dos, obligations and plain steps into one outline of the work. Every write prints
    the record it appended, one JSON line, as `page events` prints it.
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
def task_open(dir: str, subject: str, title: str, owner: str) -> dict:
    """Open a to-do titled TITLE on SUBJECT and print it; its `id` names it later.

    SUBJECT is an element's id, such as a section's, or `page` for the whole page.
    Your own to-do on a widget needs a widget that declares x-work or holds an
    unsettled update. With `--on user` the to-do is the user's: their Done ends it,
    and you can end it too. In a thread, open a to-do with `leaf response reply
    --todo`, and ask the user something with an `<lf-ask>` in the reply's
    `--markup`."""
    from leaf.todos import cmd_open

    return cmd_open(resolve_dir(dir), subject, title, owner)


@task.command(
    "start", short_help="Start work on an update or to-do, with its status line."
)
@click.argument("dir", metavar="PAGE")
@click.argument("item", metavar="ID")
@click.argument("text", metavar="LINE")
def task_start(dir: str, item: str, text: str) -> dict:
    """Mark ID Working for this turn, with LINE saying what you are doing.

    ID is the event id of a user update you owe, as its delivery names it, or an
    open to-do's id. LINE names the work and its subject in one sentence; it shows
    beside the update or to-do and in Leaf's panel. Your answer to the update, or the
    to-do's end, ends the start. If your turn ends first, the update or to-do reads stalled
    until you answer it or start it again."""
    from leaf.todos import cmd_start

    return cmd_start(resolve_dir(dir), item, text)


@task.command("end", short_help="End a to-do: done, failed, or dropped.")
@click.argument("dir", metavar="PAGE")
@click.argument("task_id", metavar="TODO")
@click.argument("outcome", type=click.Choice(["done", "failed", "dropped"]))
@click.argument("detail", metavar="[DETAIL]", required=False)
def task_end(dir: str, task_id: str, outcome: str, detail: str | None) -> dict:
    """End TODO with OUTCOME. DETAIL says where the result is, such as the
    version or reply holding it, or why there is none. TODO may be yours or the
    user's.

    TODO may also be the id of a question the user answers in words, such as an
    `lf-ask` in a reply (`widget:<id>`): `done` records that the user answered it
    elsewhere, DETAIL saying where, and `dropped` withdraws it. Neither records an
    answer from the user. An obligation a widget's state answers ends through that state
    or an authored withdrawal."""
    from leaf.todos import cmd_end

    return cmd_end(resolve_dir(dir), task_id, outcome, detail)


@task.command("plan", short_help="Write your plan for the page's work as one outline.")
@click.argument("dir", metavar="PAGE")
@body_options("the JSON outline")
def task_plan(dir: str, text: str | None, body_file) -> dict:
    """Replace the page's plan with the JSON list of steps given, in order.

    Each step has a `depth`, 0 for a goal and one more for each level under it.
    A plain step has a `title` and a `state`: open, working, done or dropped.
    A step can instead name an `item`, a to-do's id or an obligation's id, and shows
    that item's title and state, so work that stays owed past your turn is a
    to-do the plan names:

    \b
    [{"depth": 0, "title": "Review the pull request", "state": "working"},
     {"depth": 1, "title": "Check the snapshot diffs", "state": "done"},
     {"depth": 1, "item": "<to-do id>"},
     {"depth": 1, "item": "widget:<widget-id>"}]

    Write the whole plan each time it changes. Leaving out an open to-do ends
    nothing; it stays on its list. `[]` clears the plan."""
    from leaf.plans import cmd_plan

    steps = json_body(text, body_file)
    return cmd_plan(resolve_dir(dir), steps)
